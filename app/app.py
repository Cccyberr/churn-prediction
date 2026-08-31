"""Flask application factory + UI routes."""
from __future__ import annotations

import logging
import uuid

from flasgger import Swagger
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS

from app.api.routes import api_bp
from app.auth import require_admin
from app.bigquery_client import bq
from app.config import config
from app.gemini_client import gemini
from app.predictor import predictor
from app.retention import estimate_cltv, recommend


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> Flask:
    _configure_logging()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.flask_secret_key
    CORS(app)

    Swagger(app, template={
        "info": {
            "title": "Churn Prediction Platform API",
            "version": "1.0.0",
            "description": "REST API for the customer churn prediction and retention analytics platform.",
        },
    })

    # Best-effort model load; the app still serves UI even if model missing
    try:
        predictor.load()
    except Exception:  # noqa: BLE001
        app.logger.exception("Model load failed at startup (continuing).")

    app.register_blueprint(api_bp)

    # ----- UI routes -------------------------------------------------

    @app.get("/")
    def index():
        sample_ids = []
        try:
            sample_ids = bq.list_customer_ids(limit=50)
        except Exception:  # noqa: BLE001
            app.logger.warning("Could not load sample customer IDs from BQ", exc_info=True)
        return render_template("index.html", sample_ids=sample_ids, model_version=predictor.model_version)

    @app.post("/predict")
    def predict_ui():
        customer_id = (request.form.get("customerID") or "").strip()

        # Either load from BQ by ID, or use form values directly
        if customer_id and request.form.get("use_existing") == "1":
            customer = bq.get_customer(customer_id)
            if customer is None:
                flash(f"Customer {customer_id} not found.", "error")
                return redirect(url_for("index"))
        else:
            customer = {k: v for k, v in request.form.items() if k not in {"use_existing"}}
            customer.setdefault("customerID", customer_id or f"manual-{uuid.uuid4().hex[:8]}")

        try:
            pred = predictor.predict(customer)
        except Exception as e:  # noqa: BLE001
            flash(f"Prediction failed: {e}", "error")
            return redirect(url_for("index"))

        recs = recommend(pred, customer)
        cltv = estimate_cltv(customer)

        try:
            bq.log_prediction({
                "prediction_id": str(uuid.uuid4()),
                "customer_id": customer.get("customerID", "anonymous"),
                "churn_probability": pred["churn_probability"],
                "prediction": pred["prediction"],
                "risk_tier": pred["risk_tier"],
                "top_factors": pred.get("top_factors", []),
                "model_version": pred["model_version"],
                "source": "ui",
            })
        except Exception:  # noqa: BLE001
            app.logger.exception("Failed to log UI prediction")

        return render_template(
            "result.html",
            customer=customer, prediction=pred,
            recommendations=recs, cltv=cltv,
        )

    @app.get("/customer/<customer_id>")
    def customer_360(customer_id: str):
        customer = bq.get_customer(customer_id)
        if customer is None:
            flash(f"Customer {customer_id} not found.", "error")
            return redirect(url_for("index"))
        history = bq.get_prediction_history(customer_id)
        try:
            pred = predictor.predict(customer)
        except Exception:  # noqa: BLE001
            pred = None
        return render_template("customer_360.html", customer=customer, history=history, current=pred)

    @app.get("/whatif")
    def whatif_page():
        sample_ids = []
        try:
            sample_ids = bq.list_customer_ids(limit=50)
        except Exception:  # noqa: BLE001
            pass
        return render_template("whatif.html", sample_ids=sample_ids)

    @app.get("/batch")
    def batch_page():
        return render_template("batch.html")

    @app.get("/admin")
    @require_admin
    def admin_page():
        stats = {}
        try:
            stats = bq.get_overall_stats()
        except Exception:  # noqa: BLE001
            app.logger.warning("Could not load admin stats", exc_info=True)
        return render_template("admin.html", stats=stats, model_version=predictor.model_version)

    @app.post("/admin/generate-email")
    @require_admin
    def admin_generate_email():
        cid = request.form.get("customer_id", "").strip()
        if not cid:
            return jsonify({"error": "customer_id required"}), 400
        customer = bq.get_customer(cid)
        if customer is None:
            return jsonify({"error": "customer not found"}), 404
        pred = predictor.predict(customer)
        recs = recommend(pred, customer)
        offer = recs[0] if recs else {"title": "Retention check-in", "detail": "General outreach"}
        try:
            email = gemini.generate_retention_email(customer, pred, offer)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 500
        return jsonify({"customer_id": cid, "offer": offer, "email": email})

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "model_loaded": predictor.is_ready,
            "model_version": predictor.model_version,
        })

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=True)
