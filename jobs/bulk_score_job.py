"""Cloud Run Job: re-score all customers in BigQuery.

Triggered by Cloud Scheduler (see deploy/schedule_jobs.sh). Loads the
trained model from Cloud Storage, predicts for every customer in the
`customers` table, and writes results to the `predictions` table.

Run locally:
    GCP_PROJECT_ID=... BQ_DATASET=telco_churn \
      python jobs/bulk_score_job.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# Allow running from project root: `python jobs/bulk_score_job.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bigquery_client import bq  # noqa: E402
from app.predictor import predictor  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("bulk_score_job")


BATCH_SIZE = 500


def main() -> int:
    log.info("Starting bulk scoring job")
    predictor.load()
    if not predictor.is_ready:
        log.error("Predictor not ready (no model loaded). Aborting.")
        return 1

    sql = f"SELECT * FROM `{bq.client.project}.{os.getenv('BQ_DATASET', 'telco_churn')}.customers`"
    df = bq.client.query(sql).to_dataframe()
    log.info("Loaded %d customers", len(df))

    customers = df.to_dict(orient="records")
    total_written = 0
    high_risk = 0

    for i in range(0, len(customers), BATCH_SIZE):
        chunk = customers[i:i + BATCH_SIZE]
        preds = predictor.predict_batch(chunk)
        rows = []
        for src, p in zip(chunk, preds):
            if p["risk_tier"] == "High":
                high_risk += 1
            rows.append({
                "prediction_id": str(uuid.uuid4()),
                "customer_id": src.get("customerID", "unknown"),
                "churn_probability": p["churn_probability"],
                "prediction": p["prediction"],
                "risk_tier": p["risk_tier"],
                "top_factors": json.dumps([]),
                "model_version": p["model_version"],
                "source": "scheduled",
                "predicted_at": datetime.now(tz=timezone.utc).isoformat(),
            })
        bq.log_predictions_bulk(rows)
        total_written += len(rows)
        log.info("Wrote %d / %d", total_written, len(customers))

    log.info("Done. Total: %d. High-risk: %d", total_written, high_risk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
