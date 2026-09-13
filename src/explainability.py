"""
Explainable AI (XAI) using SHAP:
Generates global feature importance bar plots, beeswarm plots, and local waterfall explanations
for high-risk illicit transactions, aligning with Figure 6(b) from paper 101165.pdf.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap

def run_shap_analysis(model, X_sample, feature_names, output_dir="artifacts/figures"):
    """
    Computes Tree-SHAP values, produces global importance plot, and saves figures.
    """
    os.makedirs(output_dir, exist_ok=True)
    print("Computing SHAP values for trained model...")
    
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    
    if isinstance(shap_values, list):
        shap_vals = shap_values[1] # illicit class
    elif len(shap_values.shape) == 3:
        shap_vals = shap_values[:, :, 1]
    else:
        shap_vals = shap_values
        
    mean_shap = np.mean(np.abs(shap_vals), axis=0)
    top_indices = np.argsort(-mean_shap)[:15]
    
    shap_df = pd.DataFrame({
        "feature": [feature_names[i] for i in top_indices],
        "mean_shap": [mean_shap[i] for i in top_indices]
    })
    
    # 1. Bar Chart: Mean Absolute SHAP Values (matching paper's Fig. 6(b))
    plt.figure(figsize=(10, 6), dpi=300)
    colors = plt.cm.viridis(np.linspace(0.2, 0.85, len(top_indices)))[::-1]
    bars = plt.barh(shap_df["feature"][::-1], shap_df["mean_shap"][::-1], color=colors, edgecolor="black", alpha=0.85)
    plt.xlabel("Mean |SHAP Value| (Impact on Model Output)", fontsize=12, fontweight="bold")
    plt.ylabel("Feature", fontsize=12, fontweight="bold")
    plt.title("Top Feature Importance via SHAP Analysis (XAI)", fontsize=14, fontweight="bold", pad=15)
    plt.grid(axis="x", linestyle="--", alpha=0.6)
    plt.tight_layout()
    bar_path = os.path.join(output_dir, "shap_summary_barplot.png")
    plt.savefig(bar_path, dpi=300)
    plt.close()
    print(f"Saved SHAP bar plot to {bar_path}")

    # 2. Beeswarm Plot
    plt.figure(figsize=(10, 7), dpi=300)
    shap.summary_plot(shap_vals, X_sample, feature_names=feature_names, max_display=12, show=False)
    plt.title("SHAP Beeswarm Summary Plot (Feature Value Impact)", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    beeswarm_path = os.path.join(output_dir, "shap_beeswarm_plot.png")
    plt.savefig(beeswarm_path, dpi=300)
    plt.close()
    print(f"Saved SHAP beeswarm plot to {beeswarm_path}")
    
    return shap_df, shap_vals, explainer
