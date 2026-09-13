"""
Model definitions, Optuna hyperparameter optimization, and training routines.
Covers the 6 ML models from paper 101165.pdf: LightGBM, XGBoost, Random Forest, DT, KNN, and Logistic Regression.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score, accuracy_score
import lightgbm as lgb
import xgboost as xgb
import optuna

# Suppress optuna verbose logs
optuna.logging.set_verbosity(optuna.logging.WARNING)

def get_base_models():
    """Returns dictionary of default baseline models."""
    return {
        "LR": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "DT": DecisionTreeClassifier(max_depth=8, class_weight="balanced", random_state=42),
        "KNN": KNeighborsClassifier(n_neighbors=7, weights="distance", n_jobs=-1),
        "RF": RandomForestClassifier(n_estimators=100, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1),
        "XGBoost": xgb.XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.05, scale_pos_weight=5.0, random_state=42, eval_metric="logloss"),
        "LightGBM": lgb.LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.05, class_weight="balanced", random_state=42, verbose=-1)
    }

def tune_lightgbm_optuna(X_train, y_train, X_val, y_val, n_trials=30):
    """
    Optuna Bayesian hyperparameter optimization for LightGBM,
    mirroring the methodology from paper 101165.pdf.
    """
    print(f"Starting Optuna Hyperparameter Tuning for LightGBM ({n_trials} trials)...")
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300, step=25),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 10.0),
            "random_state": 42,
            "verbose": -1,
            "n_jobs": -1
        }
        
        clf = lgb.LGBMClassifier(**params)
        clf.fit(X_train, y_train)
        preds_prob = clf.predict_proba(X_val)[:, 1]
        # Optimize for Area Under Precision-Recall Curve (AUPRC) on the imbalanced validation set
        score = average_precision_score(y_val, preds_prob)
        return score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    
    print(f"Optuna Best Trial: Value (AUPRC) = {study.best_value:.4f}")
    print("Best LightGBM Parameters:", study.best_params)
    
    best_model = lgb.LGBMClassifier(**study.best_params, random_state=42, verbose=-1, n_jobs=-1)
    best_model.fit(X_train, y_train)
    return best_model, study.best_params

def tune_xgboost_optuna(X_train, y_train, X_val, y_val, n_trials=25):
    """
    Optuna Bayesian hyperparameter optimization for XGBoost.
    """
    print(f"Starting Optuna Hyperparameter Tuning for XGBoost ({n_trials} trials)...")
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 250, step=25),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 10.0),
            "random_state": 42,
            "eval_metric": "logloss",
            "n_jobs": -1
        }
        
        clf = xgb.XGBClassifier(**params)
        clf.fit(X_train, y_train)
        preds_prob = clf.predict_proba(X_val)[:, 1]
        score = average_precision_score(y_val, preds_prob)
        return score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    
    print(f"Optuna Best XGBoost AUPRC = {study.best_value:.4f}")
    best_model = xgb.XGBClassifier(**study.best_params, random_state=42, eval_metric="logloss", n_jobs=-1)
    best_model.fit(X_train, y_train)
    return best_model, study.best_params

def evaluate_predictions(y_true, y_prob, threshold=0.5):
    """Computes full suite of classification metrics."""
    y_pred = (y_prob >= threshold).astype(int)
    
    auprc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0
    try:
        roc_auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0
    except Exception:
        roc_auc = 0.0
        
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    return {
        "auprc": auprc,
        "roc_auc": roc_auc,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }
