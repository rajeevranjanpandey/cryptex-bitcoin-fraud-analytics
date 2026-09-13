"""
Main Orchestration Pipeline for Elliptic Bitcoin Fraud Analytics Project:
Integrates MAI 601 Topic 1 (Temporal Drift Mitigation without Retraining)
with Paper 101165.pdf (Ensemble Feature Selection, Optuna Tuning, SHAP XAI).
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np

from src.data_loader import load_data, get_temporal_splits
from src.feature_selection import ensemble_feature_selection
from src.models import get_base_models, tune_lightgbm_optuna, tune_xgboost_optuna
from src.drift_experiment import compute_temporal_psi, evaluate_static_models, evaluate_continuous_retraining
from src.in_context_model import run_in_context_ablation
from src.cost_evaluator import add_costs_to_results
from src.explainability import run_shap_analysis
from src.visualizer import plot_decay_curve, plot_drift_chart, plot_cost_chart, plot_ablation_barchart, generate_summary_table

RESULTS_DIR = "artifacts/results"
WEB_DATA_DIR = "web/data"

def run_full_pipeline(optuna_trials=20, context_size=2000):
    start_time = time.time()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(WEB_DATA_DIR, exist_ok=True)
    
    print("================================================================================")
    print("  ELLIPTIC BITCOIN FRAUD ANALYTICS: END-TO-END TEMPORAL DRIFT & XAI PIPELINE  ")
    print("================================================================================")
    
    # 1. Load Data & Temporal Splits
    print("\n[STEP 1/7] Loading and partitioning Elliptic dataset...")
    df = load_data()
    splits = get_temporal_splits(df)
    train_df = splits["train"]
    tune_df = splits["tune"]
    test_df = splits["test"]
    all_feature_cols = splits["feature_cols"]
    
    print(f"Total labeled dataset: {len(df):,} transactions")
    print(f"  - Train Set (Steps 1..34): {len(train_df):,} txs ({sum(train_df['label']==1):,} illicit)")
    print(f"  - Tune Set  (Steps 35..39): {len(tune_df):,} txs ({sum(tune_df['label']==1):,} illicit)")
    print(f"  - Test Set  (Steps 40..49): {len(test_df):,} txs ({sum(test_df['label']==1):,} illicit)")
    
    # 2. Ensemble Feature Selection (from Paper 101165.pdf)
    print("\n[STEP 2/7] Running Ensemble Feature Selection (Chi2 + RFE + SHAP + Borda Count)...")
    X_train_full = train_df[all_feature_cols]
    y_train = train_df["label"].values
    
    # Use representative sample for feature selection speed
    fs_sample_size = min(5000, len(X_train_full))
    rng = np.random.RandomState(42)
    sample_idx = rng.choice(len(X_train_full), fs_sample_size, replace=False)
    X_train_sample = X_train_full.iloc[sample_idx]
    y_train_sample = y_train[sample_idx]
    
    fs_results = ensemble_feature_selection(X_train_sample, y_train_sample, all_feature_cols, top_k=25)
    selected_features = fs_results["selected_features"]
    
    # Save feature ranking
    fs_results["ranking_df"].to_csv(os.path.join(RESULTS_DIR, "feature_borda_ranking.csv"), index=False)
    print(f"Selected {len(selected_features)} top features for model training.")
    
    # 3. Population Stability Index (PSI) Drift Analysis
    print("\n[STEP 3/7] Calculating Population Stability Index (PSI) across all 49 time steps...")
    psi_df = compute_temporal_psi(df, selected_features[:10], ref_steps=range(1, 35))
    psi_df.to_csv(os.path.join(RESULTS_DIR, "temporal_psi_drift.csv"), index=False)
    
    # 4. Model Tuning & Optimization
    print("\n[STEP 4/7] Hyperparameter Optimization via Optuna (Paper 101165.pdf)...")
    X_train = train_df[selected_features]
    X_val = tune_df[selected_features]
    y_val = tune_df["label"].values
    
    best_lgbm, best_lgbm_params = tune_lightgbm_optuna(X_train, y_train, X_val, y_val, n_trials=optuna_trials)
    best_xgb, best_xgb_params = tune_xgboost_optuna(X_train, y_train, X_val, y_val, n_trials=optuna_trials)
    
    with open(os.path.join(RESULTS_DIR, "best_hyperparameters.json"), "w") as f:
        json.dump({"LightGBM": best_lgbm_params, "XGBoost": best_xgb_params}, f, indent=2)
        
    # Baseline models suite
    base_models = get_base_models()
    base_models["LightGBM"] = best_lgbm
    base_models["XGBoost"] = best_xgb
    
    # 5. Static Models Sequential Evaluation
    print("\n[STEP 5/7] Evaluating Static Baselines & Continuous Retraining (Steps 40..49)...")
    static_results_df, fitted_models = evaluate_static_models(train_df, test_df, selected_features, base_models)
    
    # Continuous Retraining ("Expensive Option")
    retrained_results_df = evaluate_continuous_retraining(
        df, range(40, 50), selected_features, best_lgbm_params=best_lgbm_params
    )
    
    # 6. In-Context Exemplar Model & 4-way Ablation Study (Topic 1 Core Innovation)
    print("\n[STEP 6/7] Running In-Context Exemplar Selection & 4-Way Ablation Study...")
    ablation_results_df = run_in_context_ablation(df, range(40, 50), selected_features, context_size=context_size)
    
    # Combine all results
    all_results_df = pd.concat([static_results_df, retrained_results_df, ablation_results_df], ignore_index=True)
    all_results_df = add_costs_to_results(all_results_df, c_fn=10000.0, c_fp=100.0)
    all_results_df.to_csv(os.path.join(RESULTS_DIR, "all_models_temporal_results.csv"), index=False)
    
    # 7. XAI and SHAP Interpretability
    print("\n[STEP 7/7] Computing SHAP Explainable AI (XAI) outputs...")
    shap_sample = X_train.sample(n=min(1500, len(X_train)), random_state=42)
    shap_df, shap_vals, explainer = run_shap_analysis(best_lgbm, shap_sample, selected_features)
    shap_df.to_csv(os.path.join(RESULTS_DIR, "shap_feature_importance.csv"), index=False)
    
    # Generate Publication Figures and Tables
    print("\nGenerating Figures and Summary Tables...")
    plot_decay_curve(all_results_df)
    plot_drift_chart(psi_df)
    plot_cost_chart(all_results_df)
    plot_ablation_barchart(all_results_df[all_results_df["category"] == "In-Context"])
    summary_table = generate_summary_table(all_results_df)
    
    # Export web dashboard data JSON
    web_export = {
        "summary": summary_table.to_dict(orient="records"),
        "temporal_results": all_results_df.to_dict(orient="records"),
        "psi_drift": psi_df.to_dict(orient="records"),
        "feature_ranking": fs_results["ranking_df"].head(20).to_dict(orient="records"),
        "shap_importance": shap_df.to_dict(orient="records"),
        "metadata": {
            "total_transactions": len(df),
            "illicit_transactions": int(sum(df["label"] == 1)),
            "licit_transactions": int(sum(df["label"] == 0)),
            "features_selected": len(selected_features),
            "optuna_trials": optuna_trials,
            "cost_fn": 10000.0,
            "cost_fp": 100.0,
            "runtime_seconds": round(time.time() - start_time, 2)
        }
    }
    with open(os.path.join(WEB_DATA_DIR, "dashboard_data.json"), "w") as f:
        json.dump(web_export, f, indent=2)
        
    print("\n================================================================================")
    print(f" PIPELINE COMPLETED SUCCESSFULLY IN {time.time() - start_time:.1f} SECONDS! ")
    print("================================================================================")
    print(f"Artifacts saved in {RESULTS_DIR} and {WEB_DATA_DIR}")
    return all_results_df, summary_table

if __name__ == "__main__":
    run_full_pipeline()
