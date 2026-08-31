"""REST API blueprint.

All endpoints are JSON in / JSON out, intended for programmatic access
and the demo `curl` walkthrough.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from flasgger import swag_from
from flask import Blueprint, jsonify, request

from app.bigquery_client import bq
from app.gemini_client import gemini
from app.predictor import predictor
from app.retention import estimate_cltv, recommend

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/health")
@swag_from({
    "tags": ["System"],
    "responses": {200: {"description": "Service is healthy"}},
})
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": predictor.is_ready,
        "model_version": predictor.model_version,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    })


@api_bp.post("/predict")
@swag_from({
    "tags": ["Predictions"],
    "parameters": [{
        "name": "body", "in": "body", "required": True,
        "schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "object"},
                "log": {"type": "boolean", "default": True},
            },
        },
    }],
    "responses": {200: {"description": "Prediction + recommendations"}},
})
def predict():
    payload = request.get_json(silent=True) or {}
    customer = payload.get("customer") or {}
    if not customer:
        return jsonify({"error": "customer object required"}), 400

    pred = predictor.predict(customer)
    recs = recommend(pred, customer)
    cltv = estimate_cltv(customer)

    if payload.get("log", True):
        try:
            bq.log_prediction({
                "prediction_id": str(uuid.uuid4()),
                "customer_id": customer.get("customerID") or customer.get("customer_id") or "anonymous",
                "churn_probability": pred["churn_probability"],
                "prediction": pred["prediction"],
                "risk_tier": pred["risk_tier"],
                "top_factors": pred.get("top_factors", []),
                "model_version": pred["model_version"],
                "source": "api",
            })
        except Exception:  # noqa: BLE001
            log.exception("Failed to log prediction (continuing)")

    return jsonify({
        "prediction": pred,
        "recommendations": recs,
        "estimated_cltv": cltv,
    })


@api_bp.post("/batch-predict")
@swag_from({
    "tags": ["Predictions"],
    "consumes": ["multipart/form-data"],
    "parameters": [{"name": "file", "in": "formData", "type": "file", "required": True}],
    "responses": {200: {"description": "CSV of predictions"}},
})
def batch_predict():
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"error": "file field required (CSV upload)"}), 400

    data = upload.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(data))
    rows = list(reader)
    if not rows:
        return jsonify({"error": "CSV is empty"}), 400

    preds = predictor.predict_batch(rows)

    out_rows = []
    records_to_log = []
    for src, pred in zip(rows, preds):
        out_rows.append({**src, **pred})
        records_to_log.append({
            "prediction_id": str(uuid.uuid4()),
            "customer_id": src.get("customerID") or src.get("customer_id") or "anonymous",
            "churn_probability": pred["churn_probability"],
            "prediction": pred["prediction"],
            "risk_tier": pred["risk_tier"],
            "top_factors": [],
            "model_version": pred["model_version"],
            "source": "batch",
        })

    try:
        bq.log_predictions_bulk(records_to_log)
    except Exception:  # noqa: BLE001
        log.exception("Bulk logging failed (continuing)")

    return jsonify({
        "count": len(out_rows),
        "results": out_rows[:1000],  # cap response size; full CSV via /api/batch-predict/csv
    })


@api_bp.get("/customers/<customer_id>")
@swag_from({
    "tags": ["Customers"],
    "parameters": [{"name": "customer_id", "in": "path", "type": "string", "required": True}],
    "responses": {200: {"description": "Customer + latest predictions"}},
})
def get_customer(customer_id: str):
    cust = bq.get_customer(customer_id)
    if cust is None:
        return jsonify({"error": "customer not found"}), 404
    history = bq.get_prediction_history(customer_id)
    return jsonify({"customer": cust, "prediction_history": history})


@api_bp.get("/insights/overall")
@swag_from({"tags": ["Insights"], "responses": {200: {"description": "Overall stats"}}})
def insights_overall():
    return jsonify(bq.get_overall_stats())


@api_bp.get("/insights/segments")
@swag_from({"tags": ["Insights"], "responses": {200: {"description": "Segment-level churn rates"}}})
def insights_segments():
    df = bq.get_segment_rates()
    return jsonify(df.to_dict(orient="records"))


@api_bp.get("/insights/top-risk")
@swag_from({"tags": ["Insights"], "responses": {200: {"description": "Top at-risk customers"}}})
def insights_top_risk():
    df = bq.get_top_risk(limit=int(request.args.get("limit", 20)))
    df["predicted_at"] = df["predicted_at"].astype(str)
    return jsonify(df.to_dict(orient="records"))


@api_bp.post("/retention-action")
@swag_from({
    "tags": ["Retention"],
    "parameters": [{"name": "body", "in": "body", "required": True, "schema": {"type": "object"}}],
    "responses": {200: {"description": "Action logged"}},
})
def log_action():
    payload = request.get_json(silent=True) or {}
    required = ["customer_id", "action_type"]
    for r in required:
        if r not in payload:
            return jsonify({"error": f"missing field: {r}"}), 400

    record = {
        "action_id": str(uuid.uuid4()),
        "customer_id": payload["customer_id"],
        "prediction_id": payload.get("prediction_id"),
        "action_type": payload["action_type"],
        "action_detail": payload.get("action_detail"),
        "csr_id": payload.get("csr_id", "ui-user"),
        "outcome": payload.get("outcome", "pending"),
        "cost_estimate": float(payload.get("cost_estimate", 0.0)),
    }
    try:
        bq.log_action(record)
    except Exception as e:  # noqa: BLE001
        log.exception("Failed to log action")
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok", "action_id": record["action_id"]})


@api_bp.post("/generate-email")
@swag_from({
    "tags": ["Retention"],
    "parameters": [{"name": "body", "in": "body", "required": True, "schema": {"type": "object"}}],
    "responses": {200: {"description": "Generated retention email"}},
})
def generate_email():
    payload = request.get_json(silent=True) or {}
    customer = payload.get("customer") or {}
    prediction = payload.get("prediction") or {}
    offer = payload.get("offer") or {}
    if not customer or not prediction or not offer:
        return jsonify({"error": "customer, prediction and offer fields required"}), 400
    try:
        text = gemini.generate_retention_email(customer, prediction, offer)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Gemini call failed: {e}"}), 500
    return jsonify({"email": text})


@api_bp.post("/whatif")
@swag_from({"tags": ["Predictions"], "responses": {200: {"description": "Counterfactual probability"}}})
def whatif():
    payload = request.get_json(silent=True) or {}
    base = payload.get("customer") or {}
    overrides = payload.get("overrides") or {}
    if not base:
        return jsonify({"error": "customer object required"}), 400

    counterfactual = {**base, **overrides}
    base_pred = predictor.predict(base)
    new_pred = predictor.predict(counterfactual)
    return jsonify({
        "original": base_pred,
        "counterfactual": new_pred,
        "delta": round(new_pred["churn_probability"] - base_pred["churn_probability"], 4),
    })
