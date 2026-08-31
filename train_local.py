"""Train the churn model LOCALLY from the IBM Telco CSV.

This is a no-GCP shortcut so you can run the Flask app on your laptop
without setting up BigQuery / Vertex AI first.

Usage:
    python train_local.py

Reads:  data/WA_Fn-UseC_-Telco-Customer-Churn.csv
Writes: model_artifacts/model.joblib
        model_artifacts/features_meta.json
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# ----- Config -----
CSV_PATH = Path("data/WA_Fn-UseC_-Telco-Customer-Churn.csv")
OUT_DIR = Path("model_artifacts")
MODEL_VERSION = "v1-local"

FEATURE_COLUMNS = [
    "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService",
    "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges",
]
NUMERIC = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]
CATEGORICAL = [c for c in FEATURE_COLUMNS if c not in NUMERIC]


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found.")
        print("Place WA_Fn-UseC_-Telco-Customer-Churn.csv in the data/ folder first.")
        return 1

    print(f"==> Loading {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"    Rows: {len(df)}, Columns: {len(df.columns)}")

    # Clean: TotalCharges has whitespace-only entries
    df["TotalCharges"] = pd.to_numeric(
        df["TotalCharges"].astype(str).str.strip(), errors="coerce"
    )
    df["TotalCharges"] = df["TotalCharges"].fillna(df["TotalCharges"].median())

    # Target
    df["churn"] = (df["Churn"] == "Yes").astype(int)
    print(f"    Class balance: {df['churn'].value_counts().to_dict()}")

    X = df[FEATURE_COLUMNS].copy()
    y = df["churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"    Train: {len(X_train)}, Test: {len(X_test)}")

    print("==> Building pipeline")
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])

    scale_pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    clf = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.08,
        subsample=0.85, colsample_bytree=0.85,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss", random_state=42, n_jobs=-1,
    )
    pipeline = Pipeline([("preprocess", preprocessor), ("model", clf)])

    print("==> Training (takes ~10 seconds)")
    pipeline.fit(X_train, y_train)

    print("==> Evaluating")
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy":  round(accuracy_score(y_test, y_pred), 4),
        "roc_auc":   round(roc_auc_score(y_test, y_proba), 4),
        "precision": round(precision_score(y_test, y_pred), 4),
        "recall":    round(recall_score(y_test, y_pred), 4),
        "f1":        round(f1_score(y_test, y_pred), 4),
    }
    print(f"    Accuracy : {metrics['accuracy']}")
    print(f"    ROC-AUC  : {metrics['roc_auc']}")
    print(f"    Precision: {metrics['precision']}")
    print(f"    Recall   : {metrics['recall']}")
    print(f"    F1       : {metrics['f1']}")
    print()
    print(classification_report(y_test, y_pred, target_names=["No Churn", "Churn"]))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    # Feature importance (using XGBoost's built-in, no SHAP needed for local)
    print("==> Computing feature importances")
    preproc = pipeline.named_steps["preprocess"]
    feat_names = (
        NUMERIC
        + list(preproc.named_transformers_["cat"].get_feature_names_out(CATEGORICAL))
    )
    importances = pipeline.named_steps["model"].feature_importances_
    pairs = sorted(zip(feat_names, importances), key=lambda x: x[1], reverse=True)

    print("    Top 10 features:")
    for name, imp in pairs[:10]:
        print(f"      {imp:.4f}  {name}")

    global_importance = {name: float(imp) for name, imp in pairs[:20]}

    # Save
    OUT_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, OUT_DIR / "model.joblib")

    meta = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "algorithm": "XGBoostClassifier",
        "metrics": metrics,
        "feature_names": feat_names,
        "global_importance": global_importance,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC,
        "categorical_features": CATEGORICAL,
    }
    (OUT_DIR / "features_meta.json").write_text(json.dumps(meta, indent=2))

    print()
    print("==> Done.")
    print(f"    Wrote {OUT_DIR / 'model.joblib'}")
    print(f"    Wrote {OUT_DIR / 'features_meta.json'}")
    print()
    print("Now run the Flask app:")
    print("    python -m app.app")
    print("Open http://localhost:8080")
    return 0


if __name__ == "__main__":
    sys.exit(main())