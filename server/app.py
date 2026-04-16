#!/usr/bin/env python3
import csv
import errno
import glob
import json
import mimetypes
import os
import re
import secrets
import shutil
import smtplib
import subprocess
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JOBS_ROOT = PROJECT_ROOT / "server" / "jobs"
DIST_ROOT = PROJECT_ROOT / "dist"
RUNTIME_ROOT = Path(os.getenv("DEEPHPI_RUNTIME_ROOT", PROJECT_ROOT / "runtime")).resolve()
PREDICTOR_SCRIPT = RUNTIME_ROOT / "DeepSeqHPI" / "mainPred.py"
PYTHON_BIN = os.getenv("DEEPHPI_PYTHON_BIN", sys.executable or "python3")
TRANSDECODER_LONGORFS = os.getenv("DEEPHPI_TRANSDECODER_LONGORFS", "TransDecoder.LongOrfs")
TRANSDECODER_PREDICT = os.getenv("DEEPHPI_TRANSDECODER_PREDICT", "TransDecoder.Predict")
DIAMOND_BIN = os.getenv("DEEPHPI_DIAMOND_BIN", "diamond")
DEFAULT_DIAMOND_DB = PROJECT_ROOT / "DiamondDB" / "swissprot_dec2019.dmnd"
LEGACY_DIAMOND_DB = PROJECT_ROOT.parent / "deepHPI-old" / "DiamondDB" / "swissprot_dec2019.dmnd"
DIAMOND_DB = Path(
    os.getenv(
        "DEEPHPI_DIAMOND_DB",
        str(DEFAULT_DIAMOND_DB if DEFAULT_DIAMOND_DB.exists() else LEGACY_DIAMOND_DB),
    )
).resolve()
SWISSPROT_TAB = Path(
    os.getenv("DEEPHPI_SWISSPROT_TAB", str(PROJECT_ROOT / "annotations" / "swissprot.tab"))
).resolve()
HOST = os.getenv("DEEPHPI_HOST", "127.0.0.1")
PORT = int(os.getenv("DEEPHPI_PORT", "8000"))
APP_URL = os.getenv("DEEPHPI_APP_URL", "http://127.0.0.1:5173").rstrip("/")
SMTP_HOST = os.getenv("DEEPHPI_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("DEEPHPI_SMTP_PORT", "587"))
SMTP_USER = os.getenv("DEEPHPI_SMTP_USER", "").strip()
SMTP_PASS = os.getenv("DEEPHPI_SMTP_PASS", "").strip()
MAIL_FROM = os.getenv(
    "DEEPHPI_MAIL_FROM",
    os.getenv("DEEPHPI_SMTP_FROM", "no-reply-deepHPI@bioinfo.usu.edu"),
).strip()
SMTP_USE_TLS = os.getenv("DEEPHPI_SMTP_TLS", "true").strip().lower() not in {"0", "false", "no"}
SMTP_USE_SSL = os.getenv("DEEPHPI_SMTP_SSL", "false").strip().lower() in {"1", "true", "yes"}
SENDMAIL_BIN = os.getenv("DEEPHPI_SENDMAIL_BIN", shutil.which("sendmail") or "").strip()

FASTA_HEADER = re.compile(r"^>")
PROTEIN_LINE = re.compile(r"^[ARNDCQEGHILKMFPSTWYVXBZU\-\*]+$", re.IGNORECASE)
NUCLEOTIDE_LINE = re.compile(r"^[ATGCUN]+$", re.IGNORECASE)
SWISSPROT_INDEX = None
REQUIRED_MODEL_FILES = [
    "Best_PP.pth",
    "Fast_PP.pth",
    "Best_HBP.pth",
    "Fast_HBP.pth",
    "Best_HVP.pth",
    "Fast_HVP.pth",
    "Best_AP.pth",
    "Fast_AP.pth",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def smtp_configured():
    return bool(SMTP_HOST and MAIL_FROM)


def sendmail_configured():
    return bool(SENDMAIL_BIN)


def result_url(job_id):
    return f"{APP_URL}/results/{job_id}"


def send_email(to_address, subject, body):
    if not to_address:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = MAIL_FROM
    message["To"] = to_address
    message.set_content(body)

    if sendmail_configured():
        result = subprocess.run(
            [SENDMAIL_BIN, "-t", "-i"],
            input=message.as_string(),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "sendmail failed")
        return True

    if smtp_configured():
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                if SMTP_USER:
                    server.login(SMTP_USER, SMTP_PASS)
                server.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                if SMTP_USE_TLS:
                    server.starttls()
                    server.ehlo()
                if SMTP_USER:
                    server.login(SMTP_USER, SMTP_PASS)
                server.send_message(message)
        return True

    return False


def notify_submission(meta):
    email = (meta.get("email") or "").strip()
    if not email:
        return

    subject = f"DeepHPI job submitted: {meta['jobId']}"
    body = (
        f"Your DeepHPI job has been submitted.\n\n"
        f"Job ID: {meta['jobId']}\n"
        f"Model family: {meta['model']}\n"
        f"Prediction mode: {meta['feature']}\n"
        f"Host sequences: {meta['hostSequenceCount']} ({meta['hostInputType']})\n"
        f"Pathogen sequences: {meta['pathogenSequenceCount']} ({meta['pathogenInputType']})\n"
        f"Results page: {result_url(meta['jobId'])}\n"
    )
    try:
        send_email(email, subject, body)
    except Exception as exc:  # noqa: BLE001
        print(f"DeepHPI email notification failed for submitted job {meta['jobId']}: {exc}", file=sys.stderr)


def notify_completion(meta):
    email = (meta.get("email") or "").strip()
    if not email:
        return

    summary = meta.get("summary") or {}
    subject = f"DeepHPI job completed: {meta['jobId']}"
    body = (
        f"Your DeepHPI job has completed.\n\n"
        f"Job ID: {meta['jobId']}\n"
        f"Model family: {meta['model']}\n"
        f"Prediction mode: {meta['feature']}\n"
        f"Predicted interactions: {summary.get('interactionCount', 0)}\n"
        f"Host proteins: {summary.get('hostProteinCount', 0)}\n"
        f"Pathogen proteins: {summary.get('pathogenProteinCount', 0)}\n"
        f"Results page: {result_url(meta['jobId'])}\n"
    )
    try:
        send_email(email, subject, body)
    except Exception as exc:  # noqa: BLE001
        print(f"DeepHPI email notification failed for completed job {meta['jobId']}: {exc}", file=sys.stderr)


def notify_failure(meta):
    email = (meta.get("email") or "").strip()
    if not email:
        return

    subject = f"DeepHPI job failed: {meta['jobId']}"
    body = (
        f"Your DeepHPI job did not complete successfully.\n\n"
        f"Job ID: {meta['jobId']}\n"
        f"Model family: {meta['model']}\n"
        f"Prediction mode: {meta['feature']}\n"
        f"Error: {meta.get('error', 'Unknown error')}\n"
        f"Results page: {result_url(meta['jobId'])}\n"
    )
    try:
        send_email(email, subject, body)
    except Exception as exc:  # noqa: BLE001
        print(f"DeepHPI email notification failed for failed job {meta['jobId']}: {exc}", file=sys.stderr)


def ensure_jobs_root():
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)


def bind_server():
    requested_port = PORT
    max_port = int(os.getenv("DEEPHPI_PORT_MAX", str(requested_port + 20)))

    last_error = None
    for port in range(requested_port, max_port + 1):
        try:
            server = ThreadingHTTPServer((HOST, port), DeepHPIHandler)
            return server, port
        except OSError as exc:
            last_error = exc
            if exc.errno != errno.EADDRINUSE:
                raise

    raise SystemExit(
        f"Could not start DeepHPI server because ports {requested_port}-{max_port} are in use."
    ) from last_error


def validate_runtime_assets():
    missing = []

    if not PREDICTOR_SCRIPT.exists():
        missing.append(f"predictor script: {PREDICTOR_SCRIPT}")

    predictor_root = PREDICTOR_SCRIPT.parent
    for model_name in REQUIRED_MODEL_FILES:
        model_path = predictor_root / model_name
        if not model_path.exists():
            missing.append(f"model checkpoint: {model_path}")

    if not DIAMOND_DB.exists():
        missing.append(f"Diamond database: {DIAMOND_DB}")

    if not SWISSPROT_TAB.exists():
        missing.append(f"SwissProt annotation table: {SWISSPROT_TAB}")

    if missing:
        message = [
            "DeepHPI cannot start because required runtime assets are missing.",
            "",
            "Missing files:",
            *[f"- {item}" for item in missing],
            "",
            "Expected asset setup:",
            f"- predictor runtime under: {predictor_root}",
            f"- Diamond database at: {DIAMOND_DB}",
            f"- SwissProt annotation table at: {SWISSPROT_TAB}",
            "",
            "Restore these assets and start the server again.",
        ]
        raise SystemExit("\n".join(message))


def validate_fasta(text, label, expected_type=None):
    content = text.strip()
    if not content:
        raise ValueError(f"{label} FASTA input is required.")

    if expected_type not in {None, "", "protein", "nucleotide"}:
        raise ValueError(f"Unsupported {label.lower()} input type.")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or not FASTA_HEADER.match(lines[0]):
        raise ValueError(f"{label} FASTA input must begin with a FASTA header.")

    sequence_count = 0
    current_sequence_lines = []
    sequence_type = None

    for line in lines:
        if FASTA_HEADER.match(line):
            if current_sequence_lines:
                sequence = "".join(current_sequence_lines)
                active_type = expected_type or sequence_type
                if active_type == "protein" and not PROTEIN_LINE.match(sequence):
                    raise ValueError(
                        f"{label} FASTA contains characters outside the supported amino acid alphabet."
                    )
                if active_type == "nucleotide" and not NUCLEOTIDE_LINE.match(sequence):
                    raise ValueError(
                        f"{label} FASTA contains characters outside the supported nucleotide alphabet."
                    )
                current_sequence_lines = []
            sequence_count += 1
        else:
            normalized = line.upper()
            if sequence_type is None:
                if PROTEIN_LINE.match(normalized):
                    sequence_type = "protein"
                elif NUCLEOTIDE_LINE.match(normalized):
                    sequence_type = "nucleotide"
                else:
                    raise ValueError(
                        f"{label} FASTA contains unsupported characters and could not be identified as protein or nucleotide input."
                    )
            current_sequence_lines.append(normalized)

    if current_sequence_lines:
        sequence = "".join(current_sequence_lines)
        active_type = expected_type or sequence_type
        if active_type == "protein" and not PROTEIN_LINE.match(sequence):
            raise ValueError(
                f"{label} FASTA contains characters outside the supported amino acid alphabet."
            )
        if active_type == "nucleotide" and not NUCLEOTIDE_LINE.match(sequence):
            raise ValueError(
                f"{label} FASTA contains characters outside the supported nucleotide alphabet."
            )

    if sequence_count == 0:
        raise ValueError(f"{label} FASTA input does not contain any sequences.")

    return {"count": sequence_count, "type": expected_type or sequence_type or "protein"}


def validate_pairwise(text):
    if not text.strip():
        return 0

    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        columns = stripped.split("\t")
        if len(columns) != 2 or not columns[0] or not columns[1]:
            raise ValueError(
                "Pairwise input must be a tab-separated file with exactly two columns per row."
            )
        count += 1
    return count


def job_dir(job_id):
    return JOBS_ROOT / job_id


def metadata_path(job_id):
    return job_dir(job_id) / "meta.json"


def results_path(job_id):
    return job_dir(job_id) / "results.tsv"


def network_path(job_id):
    return job_dir(job_id) / "network.json"


def annotation_path(job_id):
    return job_dir(job_id) / "annotations.json"


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2))


def read_rows(job_id):
    path = results_path(job_id)
    if not path.exists():
        return []

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def read_annotations(job_id):
    path = annotation_path(job_id)
    if not path.exists():
        return {}
    return read_json(path)


def load_swissprot_index():
    global SWISSPROT_INDEX

    if SWISSPROT_INDEX is not None:
        return SWISSPROT_INDEX

    index = {}
    if not SWISSPROT_TAB.exists():
        SWISSPROT_INDEX = index
        return index

    with SWISSPROT_TAB.open() as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 8:
                continue
            accession, entry_name, _status, description, _genes, organism, _length, go_terms = row[:8]
            index[entry_name.strip()] = {
                "hit": entry_name.strip(),
                "hitAccession": accession.strip(),
                "description": description.strip(),
                "organism": organism.strip(),
                "go": go_terms.strip(),
            }

    SWISSPROT_INDEX = index
    return index


def enrich_rows(rows, annotations):
    enriched = []
    for row in rows:
        host_annotation = annotations.get(row["Host Protein"], {})
        pathogen_annotation = annotations.get(row["Pathogen Protein"], {})
        enriched.append(
            {
                **row,
                "Host Hit": host_annotation.get("hit", "no hit"),
                "Host Description": host_annotation.get("description", ""),
                "Host Organism": host_annotation.get("organism", ""),
                "Host GO": host_annotation.get("go", ""),
                "Pathogen Hit": pathogen_annotation.get("hit", "no hit"),
                "Pathogen Description": pathogen_annotation.get("description", ""),
                "Pathogen Organism": pathogen_annotation.get("organism", ""),
                "Pathogen GO": pathogen_annotation.get("go", ""),
            }
        )
    return enriched


def summarize_rows(rows):
    host_ids = {row["Host Protein"] for row in rows}
    pathogen_ids = {row["Pathogen Protein"] for row in rows}
    return {
        "interactionCount": len(rows),
        "hostProteinCount": len(host_ids),
        "pathogenProteinCount": len(pathogen_ids),
    }


def build_network(rows, annotations):
    nodes = {}
    edges = []
    interactions = []

    for row in rows:
        host_id = row["Host Protein"]
        pathogen_id = row["Pathogen Protein"]

        if host_id not in nodes:
            host_annotation = annotations.get(host_id, {})
            nodes[host_id] = {
                "id": host_id,
                "label": host_id,
                "type": "host",
                "degree": 0,
                "hit": host_annotation.get("hit", "no hit"),
                "hitAccession": host_annotation.get("hitAccession", ""),
                "description": host_annotation.get("description", ""),
                "organism": host_annotation.get("organism", ""),
                "go": host_annotation.get("go", ""),
            }

        if pathogen_id not in nodes:
            pathogen_annotation = annotations.get(pathogen_id, {})
            nodes[pathogen_id] = {
                "id": pathogen_id,
                "label": pathogen_id,
                "type": "pathogen",
                "degree": 0,
                "hit": pathogen_annotation.get("hit", "no hit"),
                "hitAccession": pathogen_annotation.get("hitAccession", ""),
                "description": pathogen_annotation.get("description", ""),
                "organism": pathogen_annotation.get("organism", ""),
                "go": pathogen_annotation.get("go", ""),
            }

        nodes[host_id]["degree"] += 1
        nodes[pathogen_id]["degree"] += 1
        edges.append(
            {
                "id": f"{host_id}::{pathogen_id}",
                "source": host_id,
                "target": pathogen_id,
                "confidence": float(row["Confidence Score"]),
                "hostProtein": host_id,
                "pathogenProtein": pathogen_id,
            }
        )
        interactions.append(
            {
                "id": f"{host_id}::{pathogen_id}",
                "hostProtein": host_id,
                "hostHit": annotations.get(host_id, {}).get("hit", "no hit"),
                "pathogenProtein": pathogen_id,
                "pathogenHit": annotations.get(pathogen_id, {}).get("hit", "no hit"),
                "confidence": float(row["Confidence Score"]),
            }
        )

    return {"nodes": list(nodes.values()), "edges": edges, "interactions": interactions}


def update_job(job_id, **changes):
    meta = read_json(metadata_path(job_id))
    meta.update(changes)
    write_json(metadata_path(job_id), meta)
    return meta


def run_command(command, cwd):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_diamond_sseqid(raw_value):
    value = raw_value.strip()
    if "|" in value:
        parts = value.split("|")
        if len(parts) >= 3:
            return {
                "hit": parts[2],
                "hitAccession": parts[1],
            }
    return {
        "hit": value,
        "hitAccession": value,
    }


def parse_diamond_title(title):
    cleaned = title.strip()
    if not cleaned:
        return {"description": "", "organism": ""}

    organism = ""
    description = cleaned
    if " OS=" in cleaned:
        description, organism_part = cleaned.split(" OS=", 1)
        organism = organism_part.split(" OX=", 1)[0].split(" GN=", 1)[0].strip()

    return {
        "description": description.strip(),
        "organism": organism.strip(),
    }


def run_diamond_annotations(fasta_path, output_path, threads="4"):
    swissprot_index = load_swissprot_index()
    command = [
        DIAMOND_BIN,
        "blastp",
        "--db",
        str(DIAMOND_DB),
        "--query",
        str(fasta_path),
        "--max-target-seqs",
        "1",
        "--threads",
        threads,
        "--quiet",
        "--outfmt",
        "6",
        "qseqid",
        "sseqid",
        "stitle",
        "--out",
        str(output_path),
    ]
    result = run_command(command, cwd=fasta_path.parent)
    if result.returncode != 0:
        raise RuntimeError(
            f"diamond failed for {fasta_path.name}: {result.stderr.strip() or result.stdout.strip() or 'unknown error'}"
        )

    annotations = {}
    if not output_path.exists():
        return annotations

    with output_path.open() as handle:
        for line in handle:
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 3:
                continue
            protein_id, sseqid, title = columns[:3]
            hit_info = parse_diamond_sseqid(sseqid)
            title_info = parse_diamond_title(title)
            swissprot_record = swissprot_index.get(hit_info["hit"], {})
            annotations[protein_id] = {
                **hit_info,
                "description": swissprot_record.get("description") or title_info.get("description", ""),
                "organism": swissprot_record.get("organism") or title_info.get("organism", ""),
                "go": swissprot_record.get("go", ""),
            }
    return annotations


def ensure_completed_job_assets(job_id):
    meta_file = metadata_path(job_id)
    if not meta_file.exists():
        return None

    meta = read_json(meta_file)
    if meta.get("status") != "completed":
        return meta

    job_root = job_dir(job_id)
    host_fasta = job_root / "host.fasta"
    pathogen_fasta = job_root / "pathogen.fasta"
    rows = read_rows(job_id)

    annotations = read_annotations(job_id)
    if not annotations and DIAMOND_DB.exists() and host_fasta.exists() and pathogen_fasta.exists():
        regenerated_annotations = {}
        regenerated_annotations.update(run_diamond_annotations(host_fasta, job_root / "host_diamond.tsv"))
        regenerated_annotations.update(run_diamond_annotations(pathogen_fasta, job_root / "pathogen_diamond.tsv"))
        annotations = regenerated_annotations
        write_json(annotation_path(job_id), annotations)

    network_file = network_path(job_id)
    refresh_network = True
    if network_file.exists():
        try:
            network_payload = read_json(network_file)
            refresh_network = "interactions" not in network_payload
        except Exception:  # noqa: BLE001
            refresh_network = True

    if refresh_network:
        write_json(network_file, build_network(rows, annotations))

    return meta


def translate_nucleotide_fasta(fasta_path, job_root, label):
    output_dir = job_root / f"{fasta_path.name}.transdecoder_dir"

    long_orfs = run_command(
        [TRANSDECODER_LONGORFS, "-t", str(fasta_path), "--output_dir", str(output_dir)],
        cwd=job_root,
    )
    if long_orfs.returncode != 0:
        raise RuntimeError(
            f"{label} TransDecoder.LongOrfs failed: {long_orfs.stderr.strip() or long_orfs.stdout.strip() or 'unknown error'}"
        )

    predict = run_command(
        [TRANSDECODER_PREDICT, "-t", str(fasta_path), "--no_refine_starts", "--output_dir", str(output_dir)],
        cwd=job_root,
    )
    if predict.returncode != 0:
        raise RuntimeError(
            f"{label} TransDecoder.Predict failed: {predict.stderr.strip() or predict.stdout.strip() or 'unknown error'}"
        )

    candidates = sorted(
        glob.glob(str(job_root / f"{fasta_path.name}.transdecoder*.pep"))
    )
    if not candidates:
        raise RuntimeError(f"{label} translated protein FASTA was not produced by TransDecoder.")

    translated_pep = Path(candidates[0])
    fasta_path.write_text(translated_pep.read_text())

    for generated in glob.glob(str(job_root / f"{fasta_path.name}.transdecoder*")):
        generated_path = Path(generated)
        if generated_path.is_file():
            generated_path.unlink(missing_ok=True)
        elif generated_path.is_dir():
            for child in sorted(generated_path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            generated_path.rmdir()

    for pipeline_file in job_root.glob("pipeliner.*cmds"):
        pipeline_file.unlink(missing_ok=True)


def run_job(job_id):
    try:
        update_job(job_id, status="running", startedAt=utc_now())
        job_root = job_dir(job_id)
        meta = read_json(metadata_path(job_id))
        host_fasta = job_root / "host.fasta"
        pathogen_fasta = job_root / "pathogen.fasta"

        if meta.get("hostInputType") == "nucleotide":
            update_job(job_id, status="running", startedAt=meta.get("startedAt", utc_now()), stage="Translating host nucleotide FASTA")
            translate_nucleotide_fasta(host_fasta, job_root, "Host")
        if meta.get("pathogenInputType") == "nucleotide":
            update_job(job_id, status="running", startedAt=meta.get("startedAt", utc_now()), stage="Translating pathogen nucleotide FASTA")
            translate_nucleotide_fasta(pathogen_fasta, job_root, "Pathogen")

        pairwise_file = job_root / "pairwise.tsv"
        pairwise_argument = str(pairwise_file) if pairwise_file.exists() else "nothing"
        update_job(job_id, status="running", startedAt=meta.get("startedAt", utc_now()), stage="Running DeepHPI prediction")

        annotations = {}
        if DIAMOND_DB.exists():
            update_job(job_id, status="running", startedAt=meta.get("startedAt", utc_now()), stage="Annotating proteins with SwissProt hits")
            annotations.update(run_diamond_annotations(host_fasta, job_root / "host_diamond.tsv"))
            annotations.update(run_diamond_annotations(pathogen_fasta, job_root / "pathogen_diamond.tsv"))
            write_json(annotation_path(job_id), annotations)

        command = [
            PYTHON_BIN,
            str(PREDICTOR_SCRIPT),
            str(host_fasta),
            str(pathogen_fasta),
            meta["feature"],
            meta["model"],
            str(results_path(job_id)),
            pairwise_argument,
        ]

        result = subprocess.run(
            command,
            cwd=RUNTIME_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "DeepHPI prediction failed."
            update_job(job_id, status="failed", completedAt=utc_now(), error=error)
            notify_failure(read_json(metadata_path(job_id)))
            return

        rows = read_rows(job_id)
        annotations = read_annotations(job_id)
        summary = summarize_rows(rows)
        write_json(network_path(job_id), build_network(rows, annotations))
        update_job(
            job_id,
            status="completed",
            completedAt=utc_now(),
            summary=summary,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            stage="Completed",
        )
        notify_completion(read_json(metadata_path(job_id)))
    except Exception as exc:  # noqa: BLE001
        update_job(job_id, status="failed", completedAt=utc_now(), error=str(exc))
        notify_failure(read_json(metadata_path(job_id)))


def create_job(payload):
    ensure_jobs_root()

    host_input = str(payload.get("hostInput", ""))
    pathogen_input = str(payload.get("pathogenInput", ""))
    pairwise_input = str(payload.get("pairwiseInput", ""))
    email = str(payload.get("email", "")).strip()
    model = str(payload.get("model", "PP")).strip()
    feature = str(payload.get("feature", "best")).strip()
    host_input_type = str(payload.get("hostInputType", "")).strip().lower()
    pathogen_input_type = str(payload.get("pathogenInputType", "")).strip().lower()

    if model not in {"PP", "HBP", "HVP", "AP"}:
        raise ValueError("Unsupported DeepHPI model family.")

    if feature not in {"best", "fast"}:
        raise ValueError("Unsupported DeepHPI prediction mode.")

    if host_input_type not in {"", "protein", "nucleotide"}:
        raise ValueError("Unsupported host input type.")
    if pathogen_input_type not in {"", "protein", "nucleotide"}:
        raise ValueError("Unsupported pathogen input type.")

    host_info = validate_fasta(host_input, "Host", host_input_type or None)
    pathogen_info = validate_fasta(pathogen_input, "Pathogen", pathogen_input_type or None)
    pairwise_count = validate_pairwise(pairwise_input)

    job_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    root = job_dir(job_id)
    root.mkdir(parents=True, exist_ok=True)

    (root / "host.fasta").write_text(host_input.strip() + "\n")
    (root / "pathogen.fasta").write_text(pathogen_input.strip() + "\n")

    if pairwise_input.strip():
        (root / "pairwise.tsv").write_text(pairwise_input.strip() + "\n")

    metadata = {
        "jobId": job_id,
        "status": "queued",
        "createdAt": utc_now(),
        "model": model,
        "feature": feature,
        "email": email,
        "hostSequenceCount": host_info["count"],
        "pathogenSequenceCount": pathogen_info["count"],
        "hostInputType": host_info["type"],
        "pathogenInputType": pathogen_info["type"],
        "pairwiseCount": pairwise_count,
        "stage": "Queued",
        "summary": {
            "interactionCount": 0,
            "hostProteinCount": 0,
            "pathogenProteinCount": 0,
        },
    }

    write_json(metadata_path(job_id), metadata)
    notify_submission(metadata)
    Thread(target=run_job, args=(job_id,), daemon=True).start()
    return metadata


class DeepHPIHandler(BaseHTTPRequestHandler):
    server_version = "DeepHPI/1.0"

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def _send_json(self, payload, status=200):
        self._set_headers(status=status, content_type="application/json")
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status=status)

    def do_OPTIONS(self):  # noqa: N802
        self._set_headers(status=204)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/jobs/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) == 3:
                job_id = parts[2]
                meta_file = metadata_path(job_id)
                if not meta_file.exists():
                    return self._send_error("Unknown DeepHPI job.", status=404)
                return self._send_json(read_json(meta_file))

            if len(parts) == 4 and parts[3] == "results":
                job_id = parts[2]
                meta_file = metadata_path(job_id)
                if not meta_file.exists():
                    return self._send_error("Unknown DeepHPI job.", status=404)
                meta = ensure_completed_job_assets(job_id) or read_json(meta_file)
                if meta["status"] != "completed":
                    return self._send_error("DeepHPI results are not available yet.", status=409)
                annotations = read_annotations(job_id)
                rows = read_rows(job_id)
                return self._send_json(
                    {
                        "job": meta,
                        "summary": meta["summary"],
                        "rows": enrich_rows(rows, annotations),
                    }
                )

            if len(parts) == 4 and parts[3] == "network":
                job_id = parts[2]
                meta_file = metadata_path(job_id)
                if not meta_file.exists():
                    return self._send_error("Unknown DeepHPI job.", status=404)
                meta = ensure_completed_job_assets(job_id) or read_json(meta_file)
                if meta["status"] != "completed":
                    return self._send_error("DeepHPI network data are not available yet.", status=409)
                return self._send_json(read_json(network_path(job_id)))

        if path == "/api/meta":
            return self._send_json(
                {
                    "models": ["PP", "HBP", "HVP", "AP"],
                    "features": ["best", "fast"],
                }
            )

        return self._serve_static(path)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/jobs":
            return self._send_error("Unsupported DeepHPI endpoint.", status=404)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            metadata = create_job(payload)
            return self._send_json(metadata, status=202)
        except json.JSONDecodeError:
            return self._send_error("DeepHPI expected a JSON request body.", status=400)
        except ValueError as exc:
            return self._send_error(str(exc), status=400)
        except Exception as exc:  # noqa: BLE001
            return self._send_error(str(exc), status=500)

    def _serve_static(self, request_path):
        if not DIST_ROOT.exists():
            return self._send_error(
                "Frontend build not found. Run `npm run build` or use `npm run dev` for the DeepHPI interface.",
                status=404,
            )

        clean_path = unquote(request_path)
        if clean_path == "/" or "." not in Path(clean_path).name:
            file_path = DIST_ROOT / "index.html"
        else:
            file_path = DIST_ROOT / clean_path.lstrip("/")

        if not file_path.exists() or not file_path.is_file():
            file_path = DIST_ROOT / "index.html"

        content_type = mimetypes.guess_type(file_path.name)[0] or "text/html"
        self._set_headers(status=200, content_type=content_type)
        self.wfile.write(file_path.read_bytes())


def main():
    ensure_jobs_root()
    validate_runtime_assets()

    server, active_port = bind_server()
    if active_port != PORT:
        print(f"Port {PORT} is busy, using http://{HOST}:{active_port} instead.")
    else:
        print(f"DeepHPI server listening on http://{HOST}:{active_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
