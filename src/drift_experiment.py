"""
Temporal Drift Experiment:
1. Population Stability Index (PSI) calculation across all 49 time steps (highlighting step 43).
2. Prediction Drift tracking (average predicted fraud probability over time).
3. Static Baseline models (trained on steps 1-34, evaluated sequentially on steps 40-49).
4. Continuous Retraining Baseline ('The expensive option' - retrained at each step t on steps 1 to t-1).
"""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, recall_score, f1_score, precision_score
import lightgbm as lgb
import xgboost as xgb

def calculate_psi(expected, actual, num_bins=10, epsilon=1e-4):
    """
    Computes the Population Stability Index (PSI) between a reference/expected distribution
    and an actual distribution at a specific time step.
    PSI < 0.1: No significant drift
    0.1 <= PSI < 0.2: Moderate drift
    PSI >= 0.2: Significant drift
    """
    # Create bin boundaries from expected distribution
    percentiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(expected, percentiles)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf
    
    # Calculate counts in each bin
    expected_counts, _ = np.histogram(expected, bins=bin_edges)
    actual_counts, _ = np.histogram(actual, bins=bin_edges)
    
    # Calculate proportions with epsilon smoothing
    expected_pct = (expected_counts / len(expected)) + epsilon
    actual_pct = (actual_counts / len(actual)) + epsilon
    
    # Normalize proportions
    expected_pct /= expected_pct.sum()
    actual_pct /= actual_pct.sum()
    
    psi_value = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi_value)

def compute_temporal_psi(df, top_features, ref_steps=range(1, 35)):
    """
    Computes average PSI across top features for every time step t in 1..49
    relative to the baseline training distribution (steps 1..34).
    """
    ref_data = df[df["time_step"].isin(ref_steps)]
    time_steps = sorted(df["time_step"].unique())
    
    psi_records = []
    
    for t in time_steps:
        step_data = df[df["time_step"] == t]
        if len(step_data) == 0:
            continue
            
        feature_psis = []
        for feat in top_features:
            feat_psi = calculate_psi(ref_data[feat].values, step_data[feat].values)
            feature_psis.append(feat_psi)
            
        avg_psi = float(np.mean(feature_psis))
        max_psi = float(np.max(feature_psis))
        
        psi_records.append({
            "time_step": int(t),
            "num_transactions": int(len(step_data)),
            "num_illicit": int(sum(step_data["label"] == 1)),
            "illicit_ratio": float(np.mean(step_data["label"] == 1)),
            "avg_psi": avg_psi,
            "max_psi": max_psi
        })
        
    return pd.DataFrame(psi_records)

def evaluate_static_models(train_df, test_steps_df, feature_cols, models_dict):
    """
    Evaluates static models (trained once on steps 1-34) sequentially across test steps 40..49.
    Returns DataFrame containing AUPRC, Recall, F1, and Precision per step per model.
    """
    X_train = train_df[feature_cols].values
    y_train = train_df["label"].values
    
    print("Fitting static baseline models on steps 1..34...")
    fitted_models = {}
    for name, model in models_dict.items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        fitted_models[name] = model
        
    results = []
    test_steps = sorted(test_steps_df["time_step"].unique())
    
    for t in test_steps:
        step_df = test_steps_df[test_steps_df["time_step"] == t]
        X_test = step_df[feature_cols].values
        y_test = step_df["label"].values
        n_pos = sum(y_test == 1)
        
        for name, model in fitted_models.items():
            probs = model.predict_proba(X_test)[:, 1]
            preds = (probs >= 0.5).astype(int)
            
            auprc = average_precision_score(y_test, probs) if n_pos > 0 else 0.0
            recall = recall_score(y_test, preds, zero_division=0)
            precision = precision_score(y_test, preds, zero_division=0)
            f1 = f1_score(y_test, preds, zero_division=0)
            
            results.append({
                "method": f"Static_{name}",
                "category": "Static",
                "time_step": int(t),
                "auprc": float(auprc),
                "recall": float(recall),
                "precision": float(precision),
                "f1": float(f1),
                "avg_prob": float(np.mean(probs)),
                "num_illicit": int(n_pos),
                "total_tx": len(step_df)
            })
            
    return pd.DataFrame(results), fitted_models

def evaluate_continuous_retraining(all_df, test_steps_range, feature_cols, best_lgbm_params=None):
    """
    Evaluates the 'Expensive Option': at every test step t, retrains the model
    on all historical data from steps 1 to t-1.
    """
    print("Running Continuous Retraining Baseline (Retrained at each step t in 40..49)...")
    results = []
    
    for t in sorted(test_steps_range):
        train_hist_df = all_df[all_df["time_step"] < t]
        test_step_df = all_df[all_df["time_step"] == t]
        
        X_train_hist = train_hist_df[feature_cols].values
        y_train_hist = train_hist_df["label"].values
        
        X_test = test_step_df[feature_cols].values
        y_test = test_step_df["label"].values
        n_pos = sum(y_test == 1)
        
        # Train fresh LightGBM model on all accumulated data up to t-1
        params = best_lgbm_params.copy() if best_lgbm_params else {"n_estimators": 150, "max_depth": 6, "learning_rate": 0.05, "class_weight": "balanced"}
        params["random_state"] = 42
        params["verbose"] = -1
        params["n_jobs"] = -1
        
        retrained_model = lgb.LGBMClassifier(**params)
        retrained_model.fit(X_train_hist, y_train_hist)
        
        probs = retrained_model.predict_proba(X_test)[:, 1]
        preds = (probs >= 0.5).astype(int)
        
        auprc = average_precision_score(y_test, probs) if n_pos > 0 else 0.0
        recall = recall_score(y_test, preds, zero_division=0)
        precision = precision_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        
        results.append({
            "method": "Continuous_Retraining_LGBM",
            "category": "Retrained",
            "time_step": int(t),
            "auprc": float(auprc),
            "recall": float(recall),
            "precision": float(precision),
            "f1": float(f1),
            "avg_prob": float(np.mean(probs)),
            "num_illicit": int(n_pos),
            "total_tx": len(test_step_df)
        })
        
    return pd.DataFrame(results)
