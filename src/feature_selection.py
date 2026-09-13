"""
Ensemble Feature Selection based on paper 101165.pdf:
Combines Chi-Square, Recursive Feature Elimination (RFE), and SHAP feature importance
using Borda Count Aggregation to select the top predictive features for fraud detection.
"""

import numpy as np
import pandas as pd
from sklearn.feature_selection import chi2, RFE
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
import lightgbm as lgb
import shap

def run_chi_square_selection(X, y, feature_names):
    """Chi-square feature scoring and ranking."""
    # Chi2 requires non-negative values
    scaler = MinMaxScaler()
    X_pos = scaler.fit_transform(X)
    chi2_stat, p_values = chi2(X_pos, y)
    
    # Higher chi2 stat = more significant = rank 1
    ranked_indices = np.argsort(-chi2_stat)
    ranks = np.empty_like(ranked_indices)
    ranks[ranked_indices] = np.arange(1, len(feature_names) + 1)
    
    return {
        "scores": chi2_stat,
        "ranks": ranks,
        "ranking_order": [feature_names[i] for i in ranked_indices]
    }

def run_rfe_selection(X, y, feature_names, n_features_to_select=30):
    """Recursive Feature Elimination using Random Forest / LightGBM."""
    estimator = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
    rfe = RFE(estimator, n_features_to_select=n_features_to_select, step=10)
    rfe.fit(X, y)
    
    # rfe.ranking_: 1 for selected, >1 for eliminated earlier
    return {
        "scores": -rfe.ranking_, # higher is better
        "ranks": rfe.ranking_,
        "support": rfe.support_
    }

def run_shap_selection(X, y, feature_names):
    """Tree-SHAP feature importance scoring and ranking."""
    model = lgb.LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.05, random_state=42, verbose=-1)
    model.fit(X, y)
    
    explainer = shap.TreeExplainer(model)
    # Sample up to 2000 rows for fast and robust SHAP computation
    sample_size = min(2000, len(X))
    sample_indices = np.random.RandomState(42).choice(len(X), sample_size, replace=False)
    X_sample = X.iloc[sample_indices] if isinstance(X, pd.DataFrame) else X[sample_indices]
    
    shap_values = explainer.shap_values(X_sample)
    if isinstance(shap_values, list):
        # binary classification: index 1 is illicit/fraud class
        shap_vals = shap_values[1]
    elif len(shap_values.shape) == 3:
        shap_vals = shap_values[:, :, 1]
    else:
        shap_vals = shap_values
        
    mean_abs_shap = np.mean(np.abs(shap_vals), axis=0)
    ranked_indices = np.argsort(-mean_abs_shap)
    ranks = np.empty_like(ranked_indices)
    ranks[ranked_indices] = np.arange(1, len(feature_names) + 1)
    
    return {
        "scores": mean_abs_shap,
        "ranks": ranks,
        "ranking_order": [feature_names[i] for i in ranked_indices]
    }

def ensemble_feature_selection(X, y, feature_names, top_k=30):
    """
    Combines Chi2, RFE, and SHAP using Borda Count Aggregation:
    Borda_Score(f) = (N - Rank_chi2(f)) + (N - Rank_rfe(f)) + (N - Rank_shap(f))
    Higher Borda count indicates higher unanimous consensus across methods.
    """
    print("--- Running Chi-Square Feature Selection ---")
    chi2_res = run_chi_square_selection(X, y, feature_names)
    
    print("--- Running RFE Feature Selection ---")
    rfe_res = run_rfe_selection(X, y, feature_names, n_features_to_select=top_k)
    
    print("--- Running SHAP Feature Selection ---")
    shap_res = run_shap_selection(X, y, feature_names)
    
    N = len(feature_names)
    # Calculate Borda count
    borda_points = (N - chi2_res["ranks"]) + (N - rfe_res["ranks"]) + (N - shap_res["ranks"])
    
    ranking_df = pd.DataFrame({
        "feature": feature_names,
        "chi2_rank": chi2_res["ranks"],
        "rfe_rank": rfe_res["ranks"],
        "shap_rank": shap_res["ranks"],
        "borda_score": borda_points
    }).sort_values(by="borda_score", ascending=False).reset_index(drop=True)
    
    ranking_df["ensemble_rank"] = np.arange(1, N + 1)
    selected_features = ranking_df["feature"].head(top_k).tolist()
    
    print(f"Top 10 features selected by Borda Count:")
    print(ranking_df[["ensemble_rank", "feature", "borda_score", "chi2_rank", "rfe_rank", "shap_rank"]].head(10))
    
    return {
        "selected_features": selected_features,
        "ranking_df": ranking_df,
        "chi2_res": chi2_res,
        "rfe_res": rfe_res,
        "shap_res": shap_res
    }
