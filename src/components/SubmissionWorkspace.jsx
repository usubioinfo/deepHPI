import { useMemo, useState } from "react";
import { demoByModel, featureOptions, modelOptions } from "../content/siteContent";
import { api } from "../lib/api";

function countFastaBlocks(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith(">")).length;
}

function readLocalFile(file, onLoad) {
  if (!file) {
    return;
  }

  const reader = new FileReader();
  reader.onload = () => onLoad(String(reader.result || ""));
  reader.readAsText(file);
}

function ModelCard({ option, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-[0.9rem] border px-4 py-3 text-left transition ${
        active
          ? "border-cobalt bg-cobalt/6 text-ink shadow-[inset_0_0_0_1px_rgba(22,98,196,0.16)]"
          : "border-ink/14 bg-white hover:border-cobalt/28"
      }`}
    >
      <h3 className="text-base font-semibold">{option.label}</h3>
    </button>
  );
}

function FeatureCard({ option, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-[0.9rem] border px-4 py-3 text-left transition ${
        active ? "border-cobalt bg-cobalt text-white" : "border-ink/14 bg-white hover:border-cobalt/28"
      }`}
    >
      <p className="text-sm font-semibold">{option.label}</p>
    </button>
  );
}

function SequencePanel({ value, onChange, onFileLoad, placeholder, compact = false, tone = "host" }) {
  const toneClasses =
    tone === "pathogen"
      ? {
          badge: "bg-[#fff0ec] text-[#c85a45]",
          border: "focus:border-[#d46a57]",
        }
      : {
          badge: "bg-[#edf5ff] text-cobalt",
          border: "focus:border-cobalt",
        };

  return (
    <div className="rounded-[1.1rem] border border-ink/14 bg-white p-3">
      <div className="flex flex-wrap gap-2">
        <label className={`cursor-pointer rounded-full px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-white transition ${
          tone === "pathogen" ? "bg-[#d46a57] hover:bg-[#bf5947]" : "bg-panel hover:bg-[#225c8f]"
        }`}>
          Upload FASTA
          <input
            type="file"
            accept=".fa,.faa,.fasta,.txt"
            className="hidden"
            onChange={(event) => readLocalFile(event.target.files?.[0], onFileLoad)}
          />
        </label>
        <span className={`rounded-full border border-ink/14 px-4 py-2.5 text-sm ${toneClasses.badge}`}>
          Paste FASTA below
        </span>
      </div>

      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`mt-3 w-full rounded-[0.9rem] border border-ink/14 bg-white px-4 py-3 font-mono text-sm leading-6 text-ink outline-none transition focus:bg-white ${toneClasses.border} ${
          compact ? "min-h-[152px]" : "min-h-[178px]"
        }`}
        placeholder={placeholder}
      />
    </div>
  );
}

function HelpModal({ open, onClose }) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#102843]/45 px-4 py-6">
      <div className="paper-panel atlas-ring w-full max-w-2xl rounded-[1.5rem] p-5 md:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Submission help</p>
            <h3 className="mt-2 text-2xl font-semibold text-ink">Preparing a DeepHPI job</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-ink/14 bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:border-panel/40"
          >
            Close
          </button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-[1rem] border border-ink/12 bg-white px-4 py-4">
            <h4 className="text-base font-semibold text-ink">Required input</h4>
            <p className="mt-2 text-sm leading-7 text-ink/80">
              Provide host and pathogen protein FASTA sequences. DeepHPI counts one sequence for each FASTA record beginning with <code>&gt;</code>.
            </p>
          </div>
          <div className="rounded-[1rem] border border-ink/12 bg-white px-4 py-4">
            <h4 className="text-base font-semibold text-ink">Pairwise restriction</h4>
            <p className="mt-2 text-sm leading-7 text-ink/80">
              Optionally provide a two-column tab-separated list of host and pathogen accessions to limit the screening space.
            </p>
          </div>
          <div className="rounded-[1rem] border border-ink/12 bg-white px-4 py-4">
            <h4 className="text-base font-semibold text-ink">Model family</h4>
            <p className="mt-2 text-sm leading-7 text-ink/80">
              Select the biological system that matches your study: plant-pathogen, human-bacteria, human-virus, or animal-pathogen.
            </p>
          </div>
          <div className="rounded-[1rem] border border-ink/12 bg-white px-4 py-4">
            <h4 className="text-base font-semibold text-ink">Prediction mode</h4>
            <p className="mt-2 text-sm leading-7 text-ink/80">
              Use <strong>Sensitive</strong> for more exhaustive screening or <strong>Faster</strong> for quicker runs with a lighter descriptor profile.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SubmissionWorkspace({ navigate }) {
  const [model, setModel] = useState("PP");
  const [feature, setFeature] = useState("best");
  const [hostInputType, setHostInputType] = useState("protein");
  const [pathogenInputType, setPathogenInputType] = useState("protein");
  const [hostInput, setHostInput] = useState("");
  const [pathogenInput, setPathogenInput] = useState("");
  const [pairwiseInput, setPairwiseInput] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const hostCount = useMemo(() => countFastaBlocks(hostInput), [hostInput]);
  const pathogenCount = useMemo(() => countFastaBlocks(pathogenInput), [pathogenInput]);
  const pairwiseCount = useMemo(
    () =>
      pairwiseInput
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean).length,
    [pairwiseInput],
  );

  const activeModel = modelOptions.find((item) => item.id === model);
  const activeFeature = featureOptions.find((item) => item.id === feature);

  const loadDemo = () => {
    const demo = demoByModel[model];
    setHostInput(demo.host);
    setPathogenInput(demo.pathogen);
    setError("");
  };

  const clearForm = () => {
    setHostInput("");
    setPathogenInput("");
    setPairwiseInput("");
    setEmail("");
    setError("");
    setHostInputType("protein");
    setPathogenInputType("protein");
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (!hostInput.trim() || !pathogenInput.trim()) {
      setError("Both host and pathogen FASTA inputs are required.");
      return;
    }

    setSubmitting(true);

    try {
      const response = await api.submitJob({
        hostInput,
        pathogenInput,
        pairwiseInput,
        email,
        model,
        feature,
        hostInputType,
        pathogenInputType,
      });
      navigate(`/results/${response.jobId}`);
    } catch (submissionError) {
      setError(submissionError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <HelpModal open={showHelp} onClose={() => setShowHelp(false)} />

      <form onSubmit={onSubmit} className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <section className="paper-panel atlas-ring rounded-[1.35rem] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h2 className="text-[1.85rem] font-semibold text-ink">Host FASTA</h2>
                <div className="rounded-full border border-cobalt/12 bg-cobalt/6 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-cobalt">
                  {hostCount} sequence{hostCount === 1 ? "" : "s"}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowHelp(true)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-ink/14 bg-white text-sm font-semibold text-ink transition hover:border-panel/38 hover:text-panel"
                aria-label="Open input guide"
                title="Open input guide"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-panel text-xs font-bold text-white">
                  i
                </span>
              </button>
            </div>
            <div className="mt-3">
              <SequencePanel
                value={hostInput}
                onChange={setHostInput}
                onFileLoad={setHostInput}
                placeholder=">host_protein_1"
                compact
                tone="host"
              />
            </div>
          </section>

          <section className="paper-panel atlas-ring rounded-[1.35rem] p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h2 className="text-[1.85rem] font-semibold text-ink">Pathogen FASTA</h2>
                <div className="rounded-full border border-[#d46a57]/18 bg-[#fff0ec] px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[#c85a45]">
                  {pathogenCount} sequence{pathogenCount === 1 ? "" : "s"}
                </div>
              </div>
            </div>
            <div className="mt-3">
              <SequencePanel
                value={pathogenInput}
                onChange={setPathogenInput}
                onFileLoad={setPathogenInput}
                placeholder=">pathogen_protein_1"
                compact
                tone="pathogen"
              />
            </div>
          </section>

          <section className="paper-panel atlas-ring rounded-[1.35rem] p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h2 className="text-[1.6rem] font-semibold text-ink">Pairwise restriction</h2>
                <div className="rounded-full border border-cobalt/12 bg-cobalt/6 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-cobalt">
                  {pairwiseCount} pairs
                </div>
              </div>
              <label className="cursor-pointer rounded-full border border-ink/12 bg-white px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink transition hover:border-cobalt/24">
                Upload Pairwise File
                <input
                  type="file"
                  accept=".tsv,.txt,.tab"
                  className="hidden"
                  onChange={(event) => readLocalFile(event.target.files?.[0], setPairwiseInput)}
                />
              </label>
            </div>

            <textarea
              value={pairwiseInput}
              onChange={(event) => setPairwiseInput(event.target.value)}
              className="mt-3 min-h-[116px] w-full rounded-[0.95rem] border border-ink/14 bg-white px-4 py-3 font-mono text-sm leading-6 outline-none transition focus:border-cobalt"
              placeholder={"host_protein_1\tpathogen_protein_1"}
            />
          </section>
        </div>

        <div className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <section className="paper-panel atlas-ring rounded-[1.35rem] p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[1.85rem] font-semibold text-ink">Prediction settings</h2>
            </div>

            <div className="mt-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Model family</p>
              <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-1">
                {modelOptions.map((option) => (
                  <ModelCard
                    key={option.id}
                    option={option}
                    active={model === option.id}
                    onClick={() => setModel(option.id)}
                  />
                ))}
              </div>
            </div>

            <div className="mt-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Prediction mode</p>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {featureOptions.map((option) => (
                  <FeatureCard
                    key={option.id}
                    option={option}
                    active={feature === option.id}
                    onClick={() => setFeature(option.id)}
                  />
                ))}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Host input</p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {[
                    ["protein", "AA"],
                    ["nucleotide", "NT"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setHostInputType(value)}
                      className={`rounded-[0.9rem] border px-4 py-3 text-sm font-semibold transition ${
                        hostInputType === value
                          ? "border-cobalt bg-cobalt/6 text-cobalt"
                          : "border-ink/14 bg-white text-ink hover:border-cobalt/28"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Pathogen input</p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {[
                    ["protein", "AA"],
                    ["nucleotide", "NT"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setPathogenInputType(value)}
                      className={`rounded-[0.9rem] border px-4 py-3 text-sm font-semibold transition ${
                        pathogenInputType === value
                          ? "border-[#d46a57] bg-[#fff0ec] text-[#c85a45]"
                          : "border-ink/14 bg-white text-ink hover:border-[#d46a57]/28"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-4">
              <label className="block">
                <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cobalt">Notification email</p>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2 w-full rounded-[0.95rem] border border-ink/14 bg-white px-4 py-3 text-sm outline-none transition focus:border-cobalt"
                  placeholder="name@institute.edu"
                />
              </label>
            </div>
          </section>

          <section className="paper-panel atlas-ring rounded-[1.35rem] p-4">
            <div className="grid gap-2 md:grid-cols-2">
              <div className="rounded-[0.95rem] border border-ink/14 bg-paper px-4 py-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink/70">Model family</p>
                <p className="mt-1 text-sm font-semibold text-ink">{activeModel?.label}</p>
              </div>
              <div className="rounded-[0.95rem] border border-ink/14 bg-paper px-4 py-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink/70">Prediction mode</p>
                <p className="mt-1 text-sm font-semibold text-ink">{activeFeature?.label}</p>
              </div>
              <div className="rounded-[0.95rem] border border-ink/14 bg-paper px-4 py-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink/70">Host sequences</p>
                <p className="mt-1 text-sm font-semibold text-ink">{hostCount} ({hostInputType === "protein" ? "AA" : "NT"})</p>
              </div>
              <div className="rounded-[0.95rem] border border-ink/14 bg-paper px-4 py-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink/70">Pathogen sequences</p>
                <p className="mt-1 text-sm font-semibold text-ink">{pathogenCount} ({pathogenInputType === "protein" ? "AA" : "NT"})</p>
              </div>
            </div>

            {error ? (
              <div className="mt-3 rounded-[0.95rem] border border-crimson/20 bg-crimson/8 px-4 py-3 text-sm text-crimson">
                {error}
              </div>
            ) : null}

            <div className="mt-4 grid gap-2 md:grid-cols-3">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-full bg-panel px-5 py-3 text-sm font-semibold text-white transition hover:bg-cobalt disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Submitting..." : "Run Prediction"}
              </button>
              <button
                type="button"
                onClick={loadDemo}
                className="rounded-full border border-cobalt/24 bg-white px-5 py-3 text-sm font-semibold text-cobalt transition hover:border-cobalt hover:bg-cobalt/6"
              >
                Load Demo
              </button>
              <button
                type="button"
                onClick={clearForm}
                className="rounded-full border border-[#d4634f]/24 bg-[#fff2ee] px-5 py-3 text-sm font-semibold text-[#b64b39] transition hover:border-[#d4634f]/40 hover:bg-[#ffe7e1]"
              >
                Clear
              </button>
            </div>
          </section>
        </div>
      </form>
    </>
  );
}
