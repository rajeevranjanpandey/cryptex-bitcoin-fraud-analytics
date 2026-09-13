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

def load_data(filepath=None):
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "elliptic_labeled.csv")
    if not os.path.exists(filepath):
        prepare_labeled_dataset()
    df = pd.read_csv(filepath)
    return df

def get_temporal_splits(df):
    """
    Splits by time step according to MAI 601 project specification:
    - Train: Steps 1 to 34
    - Tune / Val: Steps 35 to 39
    - Test: Steps 40 to 49
    """
    train_df = df[df["time_step"] <= 34].copy()
    tune_df = df[(df["time_step"] >= 35) & (df["time_step"] <= 39)].copy()
    test_df = df[df["time_step"] >= 40].copy()
    
    feature_cols = [c for c in df.columns if c.startswith("feat_")]
    
    return {
        "train": train_df,
        "tune": tune_df,
        "test": test_df,
        "feature_cols": feature_cols
    }

if __name__ == "__main__":
    prepare_labeled_dataset()
