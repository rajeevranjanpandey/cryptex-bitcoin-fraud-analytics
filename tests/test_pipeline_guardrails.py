import numpy as np
import pandas as pd

from src.data_loader import load_data, get_temporal_splits
from src.drift_experiment import select_threshold_from_validation, summarize_binary_predictions


def test_load_data_maps_class_and_drops_unknown(tmp_path):
    csv_path = tmp_path / "elliptic_like.csv"
    pd.DataFrame(
        {
            "txId": ["a", "b", "c", "d"],
            "time_step": [1, 2, 3, 4],
            "feat_1": [0.1, 0.2, 0.3, 0.4],
            "class": ["1", "2", "unknown", "illicit"],
        }
    ).to_csv(csv_path, index=False)

    df = load_data(filepath=str(csv_path), drop_unknown_labels=True)
    assert len(df) == 3
    assert set(df["label"].tolist()) == {0, 1}


def test_load_data_validates_required_headers(tmp_path):
    csv_path = tmp_path / "missing_cols.csv"
    pd.DataFrame({"txId": ["a"], "feat_1": [1.0], "label": [1]}).to_csv(csv_path, index=False)
    try:
        load_data(filepath=str(csv_path))
        assert False, "Expected ValueError for missing required columns"
    except ValueError as exc:
        assert "Missing required columns" in str(exc)


def test_temporal_split_is_chronological_and_disjoint():
    df = pd.DataFrame(
        {
            "txId": [f"tx{i}" for i in range(8)],
            "time_step": [1, 10, 34, 35, 39, 40, 45, 49],
            "feat_1": np.linspace(0.1, 0.8, 8),
            "label": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )
    splits = get_temporal_splits(df)
    train, tune, test = splits["train"], splits["tune"], splits["test"]

    assert train["time_step"].max() <= 34
    assert tune["time_step"].min() >= 35 and tune["time_step"].max() <= 39
    assert test["time_step"].min() >= 40
    assert set(train["txId"]).isdisjoint(set(tune["txId"]))
    assert set(train["txId"]).isdisjoint(set(test["txId"]))
    assert set(tune["txId"]).isdisjoint(set(test["txId"]))


def test_threshold_is_selected_from_validation_probabilities():
    y_val = np.array([1, 1, 0, 0, 0, 1])
    p_val = np.array([0.95, 0.81, 0.75, 0.40, 0.15, 0.20])
    selection = select_threshold_from_validation(y_val, p_val, thresholds=np.array([0.2, 0.5, 0.8]))

    assert selection["threshold"] in {0.5, 0.8}
    assert 0.0 <= selection["f1"] <= 1.0


def test_evaluation_summary_includes_confusion_and_ranking_metrics():
    y_true = np.array([1, 1, 0, 0, 0, 1])
    probs = np.array([0.9, 0.7, 0.6, 0.3, 0.2, 0.4])
    metrics = summarize_binary_predictions(y_true, probs, threshold=0.5)

    for key in ["auprc", "roc_auc", "precision", "recall", "f1", "tp", "fp", "fn", "tn"]:
        assert key in metrics
    assert metrics["tp"] + metrics["fn"] == 3
    assert metrics["fp"] + metrics["tn"] == 3
