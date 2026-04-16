import itertools
import importlib
import os
import sys
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pa
import torch
import torch.utils.data as utils

import iFeature.codes.APAAC as apaac
import iFeature.codes.CTDC as ctdc
import iFeature.codes.CTDT as ctdt
import iFeature.codes.CTriad as ctriad
import iFeature.codes.NMBroto as nmbroto
import iFeature.codes.PAAC as paac
import readFasta


SCRIPT_ROOT = Path(__file__).resolve().parent
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.set_num_threads(min(16, max(1, (os.cpu_count() or 1))))


def featureGenerationAPAAC(training_split):
    features = np.empty([152, 0])
    for _, row in training_split.iterrows():
        feature = apaac.APAAC([[row["proteinA"], row["seqA"]]])[1][1:77]
        feature.extend(apaac.APAAC([[row["proteinB"], row["seqB"]]])[1][1:77])
        features = np.append(features, feature)
    return features


def featureGenerationPAAC_CTDC_CTDT(training_split):
    features = np.empty([252, 0])
    for _, row in training_split.iterrows():
        feature = paac.PAAC([[row["proteinA"], row["seqA"]]])[1][1:49]
        feature.extend(ctdc.CTDC([[row["proteinA"], row["seqA"]]])[1][1:40])
        feature.extend(ctdt.CTDT([[row["proteinA"], row["seqA"]]])[1][1:40])
        feature.extend(paac.PAAC([[row["proteinB"], row["seqB"]]])[1][1:49])
        feature.extend(ctdc.CTDC([[row["proteinB"], row["seqB"]]])[1][1:40])
        feature.extend(ctdt.CTDT([[row["proteinB"], row["seqB"]]])[1][1:40])
        features = np.append(features, feature)
    return features


def featureGenerationPAAC_CT_NMBroto(training_split):
    features = np.empty([1230, 0])
    for _, row in training_split.iterrows():
        feature = paac.PAAC([[row["proteinA"], row["seqA"]]])[1][1:49]
        feature.extend(ctriad.CTriad([[row["proteinA"], row["seqA"]]])[1][1:344])
        feature.extend(nmbroto.NMBroto([[row["proteinA"], row["seqA"]]])[1][1:255])
        feature.extend(paac.PAAC([[row["proteinB"], row["seqB"]]])[1][1:49])
        feature.extend(ctriad.CTriad([[row["proteinB"], row["seqB"]]])[1][1:344])
        feature.extend(nmbroto.NMBroto([[row["proteinB"], row["seqB"]]])[1][1:255])
        features = np.append(features, feature)
    return features


def featureGenerationCT(training_split):
    features = np.empty([686, 0])
    for _, row in training_split.iterrows():
        feature = ctriad.CTriad([[row["proteinA"], row["seqA"]]])[1][1:344]
        feature.extend(ctriad.CTriad([[row["proteinB"], row["seqB"]]])[1][1:344])
        features = np.append(features, feature)
    return features


def build_testing_dataframe(host_fasta, pathogen_fasta, pairwise_filename):
    col_names = ["proteinA", "seqA", "proteinB", "seqB"]
    testing_df = pa.DataFrame(columns=col_names)
    pairwise_enabled = False
    pairs_to_test = set()

    if pairwise_filename != "nothing":
        pairwise_enabled = True
        pairwise_df = pa.read_csv(pairwise_filename, sep="\t", header=None)
        pairs_to_test = set((pairwise_df.iloc[:, 0] + pairwise_df.iloc[:, 1]).values)

    for host_sequence in host_fasta:
        for pathogen_sequence in pathogen_fasta:
            pair_key = host_sequence[0] + pathogen_sequence[0]
            if pairwise_enabled and pair_key not in pairs_to_test:
                continue
            testing_df.loc[len(testing_df)] = [
                host_sequence[0],
                host_sequence[1],
                pathogen_sequence[0],
                pathogen_sequence[1],
            ]

    return testing_df


def get_parallel_cores(number_of_rows):
    if number_of_rows < 4:
        return 1
    if number_of_rows < 10:
        return 4
    if number_of_rows < 16:
        return 10
    return 16


def parallelize_dataframe(dataframe, func):
    n_cores = get_parallel_cores(dataframe.shape[0])
    row_indices = np.array_split(np.arange(dataframe.shape[0]), n_cores)
    df_split = [dataframe.iloc[index_split].copy() for index_split in row_indices if len(index_split) > 0]
    pool = Pool(n_cores)
    try:
        features = np.concatenate(pool.map(func, df_split))
    finally:
        pool.close()
        pool.join()
    return features


def load_model_and_features(testing_df, feature, model_type):
    model_lookup = {
        ("PP", "best"): ("Best_PP.pth", "Convolutional1DNN_PAAC_CTDC_CTDT", featureGenerationPAAC_CTDC_CTDT, 252),
        ("HBP", "best"): ("Best_HBP.pth", "Convolutional1DNN_PAAC_CT_NMBroto", featureGenerationPAAC_CT_NMBroto, 1230),
        ("HVP", "best"): ("Best_HVP.pth", "Convolutional1DNN_PAAC_CT_NMBroto", featureGenerationPAAC_CT_NMBroto, 1230),
        ("AP", "best"): ("Best_AP.pth", "Convolutional1DNN_PAAC_CT_NMBroto", featureGenerationPAAC_CT_NMBroto, 1230),
        ("PP", "fast"): ("Fast_PP.pth", "Convolutional1DNN_APAAC", featureGenerationAPAAC, 152),
        ("HBP", "fast"): ("Fast_HBP.pth", "Convolutional1DNN_CT", featureGenerationCT, 686),
        ("HVP", "fast"): ("Fast_HVP.pth", "Convolutional1DNN_CT", featureGenerationCT, 686),
        ("AP", "fast"): ("Fast_AP.pth", "Convolutional1DNN_CT", featureGenerationCT, 686),
    }

    if (model_type, feature) not in model_lookup:
        raise ValueError("Unsupported model/feature combination: %s/%s" % (model_type, feature))

    model_name, module_name, feature_builder, vector_size = model_lookup[(model_type, feature)]
    model_path = SCRIPT_ROOT / model_name
    if not model_path.exists():
        raise FileNotFoundError(f"DeepHPI model file not found: {model_path}")

    importlib.import_module(module_name)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="You are using `torch.load` with `weights_only=False`",
            category=FutureWarning,
        )
        model = torch.load(model_path, map_location=device, weights_only=False)
    model = model.to(device)

    features = parallelize_dataframe(testing_df, feature_builder)
    features = np.swapaxes(features.reshape((testing_df.shape[0], vector_size)), 0, 1)
    return model, features


def score_predictions(model, features):
    labels = np.zeros([len(features[0])], dtype=np.float32)
    features = features.astype(np.float32)

    tensor_x = torch.from_numpy(features).transpose(0, 1).unsqueeze(1)
    tensor_y = torch.from_numpy(labels)

    test_dataset = utils.TensorDataset(tensor_x, tensor_y)
    test_loader = torch.utils.data.DataLoader(
        dataset=test_dataset,
        batch_size=40,
        shuffle=False,
    )

    model.eval()

    probabilities = []
    with torch.no_grad():
        for batch_features, batch_labels in test_loader:
            batch_features = batch_features.to(device)
            batch_labels = batch_labels.to(device)
            outputs = model(batch_features)
            batch_probabilities = torch.squeeze(outputs).detach().cpu().reshape(-1).tolist()
            probabilities.extend(batch_probabilities)

    return [float(probability) for probability in probabilities]


def write_results(output_file_name, testing_df, probabilities):
    result_columns = [
        "Row",
        "Host Protein",
        "Host Sequence",
        "Pathogen Protein",
        "Pathogen Sequence",
        "Confidence Score",
    ]

    positive_indices = [index for index, probability in enumerate(probabilities) if probability >= 0.5]

    if not positive_indices:
        pa.DataFrame(columns=result_columns).to_csv(output_file_name, sep="\t", index=False)
        return

    results_df = testing_df.iloc[positive_indices].copy().reset_index(drop=True)
    results_df.columns = [
        "Host Protein",
        "Host Sequence",
        "Pathogen Protein",
        "Pathogen Sequence",
    ]
    results_df.insert(0, "Row", np.arange(1, len(results_df) + 1))
    results_df["Confidence Score"] = [probabilities[index] for index in positive_indices]
    results_df.to_csv(output_file_name, sep="\t", index=False)


def run_prediction(host_file, pathogen_file, feature, model_type, output_file_name, pairwise_filename):
    host_fasta = readFasta.readFasta(host_file)
    pathogen_fasta = readFasta.readFasta(pathogen_file)
    testing_df = build_testing_dataframe(host_fasta, pathogen_fasta, pairwise_filename)

    if testing_df.empty:
        write_results(output_file_name, testing_df, [])
        return

    model, features = load_model_and_features(testing_df, feature, model_type)
    probabilities = score_predictions(model, features)
    write_results(output_file_name, testing_df, probabilities)


def main():
    host_file = sys.argv[1]
    pathogen_file = sys.argv[2]
    feature = sys.argv[3]
    model_type = sys.argv[4]
    output_file_name = sys.argv[5]
    pairwise_filename = "nothing"

    if len(sys.argv) > 6:
        pairwise_filename = sys.argv[6]

    run_prediction(
        host_file=host_file,
        pathogen_file=pathogen_file,
        feature=feature,
        model_type=model_type,
        output_file_name=output_file_name,
        pairwise_filename=pairwise_filename,
    )


if __name__ == "__main__":
    main()
