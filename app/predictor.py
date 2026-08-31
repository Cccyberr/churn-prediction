"""Churn predictor: loads a trained sklearn pipeline and produces predictions.

Supports two modes:
  * USE_VERTEX_ENDPOINT=true  -> calls a deployed Vertex AI endpoint
  * USE_VERTEX_ENDPOINT=false -> loads the joblib pipeline bundled in the image
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import config

log = logging.getLogger(__name__)

# Canonical feature order (matches training notebook output)
FEATURE_COLUMNS = [
    "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService",
    "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges",
]

NUMERIC_COLUMNS = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _normalise_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce a raw customer dict into the canonical feature dict."""
    out: dict[str, Any] = {}
    for col in FEATURE_COLUMNS:
        val = raw.get(col)
        if col in NUMERIC_COLUMNS:
            out[col] = _to_float(val)
        else:
            out[col] = str(val) if val is not None else "No"
    return out


def _risk_tier(prob: float) -> str:
    if prob >= 0.70:
        return "High"
    if prob >= 0.40:
        return "Medium"
    return "Low"


class Predictor:
    """Wraps the trained pipeline + SHAP-style feature attribution."""

    def __init__(self) -> None:
        self._pipeline = None
        self._feature_names: list[str] = []
        self._global_importance: dict[str, float] = {}
        self._model_version: str = "unknown"
        self._endpoint = None

    # ---- Loading -------------------------------------------------------

    def load(self) -> None:
        if config.use_vertex_endpoint and config.vertex_endpoint_id:
            self._load_vertex()
        else:
            self._load_local()

    def _load_local(self) -> None:
        path = Path(config.model_local_path)
        if not path.exists():
            log.warning("Model file not found at %s — predictor will not function until trained.", path)
            return
        self._pipeline = joblib.load(path)
        log.info("Loaded model from %s", path)

        meta_path = Path(config.features_meta_path)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self._feature_names = meta.get("feature_names", [])
            self._global_importance = meta.get("global_importance", {})
            self._model_version = meta.get("model_version", "v1")
            log.info("Loaded feature meta. Model version: %s", self._model_version)

    def _load_vertex(self) -> None:
        from google.cloud import aiplatform

        aiplatform.init(project=config.project_id, location=config.region)
        self._endpoint = aiplatform.Endpoint(config.vertex_endpoint_id)
        self._model_version = f"vertex:{config.vertex_endpoint_id}"
        log.info("Initialised Vertex endpoint %s", config.vertex_endpoint_id)

    # ---- Prediction ----------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None or self._endpoint is not None

    @property
    def model_version(self) -> str:
        return self._model_version

    def predict(self, raw: dict[str, Any]) -> dict[str, Any]:
        row = _normalise_row(raw)

        if self._endpoint is not None:
            return self._predict_vertex(row)
        if self._pipeline is None:
            raise RuntimeError("No model loaded. Train and place artifacts in model_artifacts/.")

        df = pd.DataFrame([row])
        proba = float(self._pipeline.predict_proba(df)[0][1])
        tier = _risk_tier(proba)
        factors = self._top_factors(df, top_n=5)

        return {
            "churn_probability": round(proba, 4),
            "prediction": "Yes" if proba >= 0.5 else "No",
            "risk_tier": tier,
            "top_factors": factors,
            "model_version": self._model_version,
        }

    def predict_batch(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        normalised = [_normalise_row(r) for r in rows]
        df = pd.DataFrame(normalised)

        if self._pipeline is None:
            raise RuntimeError("Batch predict requires the local pipeline.")

        probs = self._pipeline.predict_proba(df)[:, 1]
        out: list[dict[str, Any]] = []
        for i, p in enumerate(probs):
            p_f = float(p)
            out.append({
                "churn_probability": round(p_f, 4),
                "prediction": "Yes" if p_f >= 0.5 else "No",
                "risk_tier": _risk_tier(p_f),
                "model_version": self._model_version,
                "input_index": i,
            })
        return out

    # ---- Explainability ------------------------------------------------

    def _top_factors(self, df: pd.DataFrame, top_n: int = 5) -> list[dict[str, Any]]:
        """Per-prediction factor attribution.

        We use a lightweight approach: combine global feature importance
        with per-row feature values to produce a readable explanation.
        Heavyweight SHAP is computed at training time and exported in
        features_meta.json; this keeps Cloud Run cold-start fast.
        """
        if not self._global_importance:
            return []

        row = df.iloc[0].to_dict()
        factors: list[dict[str, Any]] = []

        for feat, importance in self._global_importance.items():
            raw_feat = feat.split("__")[-1] if "__" in feat else feat
            base_feat = raw_feat.split("_")[0] if raw_feat not in row else raw_feat
            value = row.get(base_feat, row.get(raw_feat, None))

            if value is None:
                continue
            factors.append({
                "feature": base_feat,
                "value": value,
                "importance": round(float(importance), 4),
            })

        factors.sort(key=lambda x: x["importance"], reverse=True)
        seen = set()
        unique: list[dict[str, Any]] = []
        for f in factors:
            if f["feature"] in seen:
                continue
            seen.add(f["feature"])
            unique.append(f)
            if len(unique) >= top_n:
                break
        return unique

    def _predict_vertex(self, row: dict[str, Any]) -> dict[str, Any]:
        instances = [row]
        response = self._endpoint.predict(instances=instances)
        # Vertex tabular returns dicts with a 'scores' field or similar
        pred = response.predictions[0]
        if isinstance(pred, dict):
            proba = float(pred.get("scores", [0, 0])[1] if "scores" in pred else pred.get("probability", 0.0))
        else:
            proba = float(pred)
        return {
            "churn_probability": round(proba, 4),
            "prediction": "Yes" if proba >= 0.5 else "No",
            "risk_tier": _risk_tier(proba),
            "top_factors": [],
            "model_version": self._model_version,
        }


predictor = Predictor()
