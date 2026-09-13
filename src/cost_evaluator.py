"""
Financial Cost Model (Topic 1: Put a price on it).
Computes the financial loss per step:
Cost(t) = C_FN * FN(t) + C_FP * FP(t)
where C_FN is the cost of a missed illicit transaction and C_FP is the cost of a false alarm.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

DEFAULT_C_FN = 10000.0 # $10,000 per missed fraud
DEFAULT_C_FP = 100.0   # $100 per false alarm

def compute_financial_cost(y_true, y_prob, threshold=0.5, c_fn=DEFAULT_C_FN, c_fp=DEFAULT_C_FP):
    """
    Calculates confusion matrix counts and monetary loss for given predictions.
    """
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    
    fraud_loss = fn * c_fn
    friction_cost = fp * c_fp
    total_cost = fraud_loss + friction_cost
    
    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "fraud_loss": float(fraud_loss),
        "friction_cost": float(friction_cost),
        "total_cost": float(total_cost)
    }

def add_costs_to_results(results_df, c_fn=DEFAULT_C_FN, c_fp=DEFAULT_C_FP):
    """
    Given a results dataframe with num_illicit, recall, precision, total_tx,
    estimates TP, FP, FN and computes dollar cost per step.
    """
    df = results_df.copy()
    
    # TP = recall * num_illicit
    tp = np.round(df["recall"] * df["num_illicit"]).astype(int)
    fn = df["num_illicit"] - tp
    
    # From precision = TP / (TP + FP) => FP = TP * (1 - prec) / prec (when prec > 0)
    prec = df["precision"].values
    fp = np.zeros_like(tp)
    for i in range(len(df)):
        if prec[i] > 0 and tp[i] > 0:
            fp[i] = int(np.round(tp[i] * (1.0 - prec[i]) / prec[i]))
        else:
            # Fallback estimation based on average probability or threshold
            fp[i] = int(np.round((df["total_tx"].iloc[i] - df["num_illicit"].iloc[i]) * 0.02))
            
    df["tp"] = tp
    df["fn"] = fn
    df["fp"] = fp
    df["fraud_loss"] = df["fn"] * c_fn
    df["friction_cost"] = df["fp"] * c_fp
    df["total_cost"] = df["fraud_loss"] + df["friction_cost"]
    
    return df
