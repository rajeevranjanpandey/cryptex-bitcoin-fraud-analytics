"""
Data loader and downloader for the Elliptic Bitcoin Dataset.
Handles downloading classes and features, joining, and temporal splitting.
"""

import os
import urllib.request
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CLASSES_URL = "https://huggingface.co/datasets/SuodhanJ6/elliptic_txs_classes/resolve/main/elliptic_txs_classes.csv"
FEATURES_URL = "https://huggingface.co/datasets/SuodhanJ6/elliptic_txs_features/resolve/main/elliptic_txs_features.csv"

REQUIRED_TRANSACTION_COLUMNS = ["txId", "time_step"]

def download_file(url: str, dest_path: str):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        print(f"File already exists: {dest_path} ({os.path.getsize(dest_path)} bytes)")
        return
    print(f"Downloading {url} to {dest_path}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024 * 2 # 2MB
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = (downloaded / total) * 100
                print(f"\rDownloaded {downloaded / (1024*1024):.1f}/{total / (1024*1024):.1f} MB ({pct:.1f}%)", end="", flush=True)
            else:
                print(f"\rDownloaded {downloaded / (1024*1024):.1f} MB", end="", flush=True)
    print("\nDownload complete.")

def prepare_labeled_dataset():
    """
    Downloads classes and features, streams/filters only labelled transactions (class 1 or 2),
    and saves a clean, compact CSV: data/elliptic_labeled.csv
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    classes_path = os.path.join(DATA_DIR, "elliptic_txs_classes.csv")
    labeled_path = os.path.join(DATA_DIR, "elliptic_labeled.csv")
    
    if os.path.exists(labeled_path) and os.path.getsize(labeled_path) > 10 * 1024 * 1024:
        print(f"Labeled dataset already prepared at {labeled_path}")
        return labeled_path

    # Step 1: Download classes
    download_file(CLASSES_URL, classes_path)
    print("Reading classes file...")
    classes_df = pd.read_csv(classes_path)
    # class mapping: '1' is illicit (fraud), '2' is licit (non-fraud), 'unknown' is unlabelled
    classes_df["class"] = classes_df["class"].astype(str)
    labeled_classes = classes_df[classes_df["class"].isin(["1", "2"])].copy()
    labeled_classes["label"] = (labeled_classes["class"] == "1").astype(int) # 1 = fraud, 0 = non-fraud
    tx_to_label = dict(zip(labeled_classes["txId"].astype(str), labeled_classes["label"]))
    print(f"Total labelled transactions: {len(tx_to_label)} (Illicit/Fraud: {sum(labeled_classes['label']==1)}, Licit: {sum(labeled_classes['label']==0)})")

    # Step 2: Stream download and filter features file directly
    print(f"Streaming and filtering features from {FEATURES_URL}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(FEATURES_URL, headers=headers)
    
    # Column names: txId, time_step, feat_1 ... feat_165
    header_cols = ["txId", "time_step"] + [f"feat_{i}" for i in range(1, 166)]
    
    with urllib.request.urlopen(req) as resp, open(labeled_path, "w") as out_f:
        # Write header with label added
        out_f.write(",".join(header_cols + ["label"]) + "\n")
        
        buffer = ""
        matched_count = 0
        total_lines = 0
        
        while True:
            chunk = resp.read(1024 * 1024 * 4) # 4MB chunk
            if not chunk:
                if buffer:
                    lines = [buffer]
                else:
                    break
            else:
                text = buffer + chunk.decode("utf-8", errors="ignore")
                lines = text.split("\n")
                buffer = lines[-1] # incomplete line
                lines = lines[:-1]

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                # Format: txId,time_step,feat_1...
                parts = line.split(",", 2)
                tx_id = parts[0].strip()
                if tx_id in tx_to_label:
                    label_val = tx_to_label[tx_id]
                    out_f.write(f"{line},{label_val}\n")
                    matched_count += 1
                    
            if total_lines % 20000 == 0:
                print(f"\rProcessed {total_lines:,} rows, matched {matched_count:,} labeled transactions...", end="", flush=True)

    print(f"\nCompleted! Saved {matched_count} labeled transactions to {labeled_path}")
    return labeled_path

def validate_dataframe_headers(df: pd.DataFrame):
    missing = [c for c in REQUIRED_TRANSACTION_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Expected at least {REQUIRED_TRANSACTION_COLUMNS}.")
    feature_cols = [c for c in df.columns if c.startswith("feat_")]
    if not feature_cols:
        raise ValueError("No feature columns found. Expected one or more columns with 'feat_' prefix.")

def map_label_values(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    mapping = {
        "1": 1,
        "illicit": 1,
        "fraud": 1,
        "true": 1,
        "2": 0,
        "0": 0,
        "licit": 0,
        "non-fraud": 0,
        "non_fraud": 0,
        "false": 0,
        "unknown": np.nan,
        "nan": np.nan,
        "none": np.nan,
        "": np.nan,
    }
    mapped = normalized.map(mapping)
    numeric = pd.to_numeric(series, errors="coerce")
    mapped = mapped.where(~mapped.isna(), numeric)
    mapped = mapped.where(mapped.isin([0, 1]), np.nan)
    return mapped

def load_data(filepath=None, drop_unknown_labels=True):
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "elliptic_labeled.csv")
    if not os.path.exists(filepath):
        prepare_labeled_dataset()
    df = pd.read_csv(filepath)
    validate_dataframe_headers(df)

    if "label" not in df.columns:
        if "class" not in df.columns:
            raise ValueError("Input data must contain either a 'label' column or a 'class' column.")
        df["label"] = map_label_values(df["class"])
    else:
        df["label"] = map_label_values(df["label"])

    df["time_step"] = pd.to_numeric(df["time_step"], errors="coerce")
    if df["time_step"].isna().any():
        raise ValueError("Found non-numeric values in 'time_step'.")
    df["time_step"] = df["time_step"].astype(int)

    if drop_unknown_labels:
        before = len(df)
        df = df[df["label"].isin([0, 1])].copy()
        removed = before - len(df)
        if removed > 0:
            print(f"Dropped {removed} rows with unknown/unmapped labels from {os.path.basename(filepath)}.")
    else:
        df["label"] = df["label"].astype("Float64")
    if drop_unknown_labels:
        df["label"] = df["label"].astype(int)
    return df

def get_temporal_splits(df):
    """
    Splits by time step according to MAI 601 project specification:
    - Train: Steps 1 to 34
    - Tune / Val: Steps 35 to 39
    - Test: Steps 40 to 49
    """
    required_cols = ["time_step", "label"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns for split: {missing_cols}")

    known_df = df[df["label"].isin([0, 1])].copy()

    train_df = known_df[known_df["time_step"] <= 34].copy()
    tune_df = known_df[(known_df["time_step"] >= 35) & (known_df["time_step"] <= 39)].copy()
    test_df = known_df[(known_df["time_step"] >= 40) & (known_df["time_step"] <= 49)].copy()
    
    feature_cols = [c for c in known_df.columns if c.startswith("feat_")]
    feature_cols = sorted(
        feature_cols,
        key=lambda x: (0, int(x.split("_")[1])) if x.split("_")[1].isdigit() else (1, x)
    )

    if len(set(train_df.index).intersection(set(tune_df.index))) > 0 or len(set(train_df.index).intersection(set(test_df.index))) > 0 or len(set(tune_df.index).intersection(set(test_df.index))) > 0:
        raise ValueError("Temporal split leakage detected: overlapping rows between train/tune/test sets.")
    if (len(train_df) > 0 and len(tune_df) > 0 and train_df["time_step"].max() >= tune_df["time_step"].min()) or \
       (len(tune_df) > 0 and len(test_df) > 0 and tune_df["time_step"].max() >= test_df["time_step"].min()):
        raise ValueError("Temporal split boundaries overlap; chronological ordering violated.")
    
    return {
        "train": train_df,
        "tune": tune_df,
        "test": test_df,
        "feature_cols": feature_cols
    }

if __name__ == "__main__":
    prepare_labeled_dataset()
