"""Thin wrapper around the BigQuery client used by the app.

Includes local-mode fallbacks that read from the CSV file when
BigQuery isn't configured (GCP_PROJECT_ID is empty or default).
"""
from __future__ import annotations

import csv as _csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.config import config

log = logging.getLogger(__name__)

LOCAL_CSV = Path("data/WA_Fn-UseC_-Telco-Customer-Churn.csv")


def _is_local_mode() -> bool:
    return not config.project_id or config.project_id == "your-project-id"


class BQ:
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=config.project_id)
        return self._client

    def get_customer(self, customer_id):
        if _is_local_mode():
            return self._get_customer_local(customer_id)
        from google.cloud import bigquery
        sql = f"SELECT * FROM `{config.customers_table}` WHERE customerID = @cid LIMIT 1"
        job = self.client.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cid", "STRING", customer_id)]))
        rows = list(job.result())
        return dict(rows[0].items()) if rows else None

    def _get_customer_local(self, customer_id):
        if not LOCAL_CSV.exists():
            return None
        with LOCAL_CSV.open(newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                if row.get("customerID") == customer_id:
                    for key in ("tenure", "SeniorCitizen"):
                        try: row[key] = int(row[key])
                        except: pass
                    for key in ("MonthlyCharges", "TotalCharges"):
                        try: row[key] = float(str(row[key]).strip() or 0)
                        except: row[key] = 0.0
                    return row
        return None

    def list_customer_ids(self, limit=100):
        if _is_local_mode():
            return self._list_customer_ids_local(limit)
        sql = f"SELECT customerID FROM `{config.customers_table}` ORDER BY customerID LIMIT {int(limit)}"
        return [row["customerID"] for row in self.client.query(sql).result()]

    def _list_customer_ids_local(self, limit):
        if not LOCAL_CSV.exists():
            return []
        with LOCAL_CSV.open(newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            return [row["customerID"] for _, row in zip(range(limit), reader)]

    def get_prediction_history(self, customer_id, limit=20):
        if _is_local_mode():
            return []
        from google.cloud import bigquery
        sql = f"SELECT * FROM `{config.predictions_table}` WHERE customer_id = @cid ORDER BY predicted_at DESC LIMIT {int(limit)}"
        job = self.client.query(sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cid", "STRING", customer_id)]))
        return [dict(r.items()) for r in job.result()]

    def get_top_risk(self, limit=20):
        if _is_local_mode():
            return pd.DataFrame()
        sql = f"""SELECT p.customer_id, p.churn_probability, p.risk_tier, c.MonthlyCharges,
                  c.Contract, c.tenure, p.predicted_at
                  FROM `{config.project_id}.{config.bq_dataset}.latest_predictions` p
                  JOIN `{config.customers_table}` c ON p.customer_id = c.customerID
                  WHERE p.risk_tier = 'High' ORDER BY p.churn_probability DESC LIMIT {int(limit)}"""
        return self.client.query(sql).to_dataframe()

    def get_segment_rates(self):
        if _is_local_mode():
            return pd.DataFrame()
        sql = f"SELECT * FROM `{config.project_id}.{config.bq_dataset}.segment_churn_rates`"
        return self.client.query(sql).to_dataframe()

    def get_overall_stats(self):
        if _is_local_mode():
            return self._get_overall_stats_local()
        sql = f"""SELECT COUNT(*) AS total_customers,
                  SUM(IF(Churn = 'Yes', 1, 0)) AS churned_customers,
                  SAFE_DIVIDE(SUM(IF(Churn = 'Yes', 1, 0)), COUNT(*)) AS churn_rate,
                  SUM(MonthlyCharges) * 12 AS annual_revenue
                  FROM `{config.customers_table}`"""
        rows = list(self.client.query(sql).result())
        return dict(rows[0].items()) if rows else {}

    def _get_overall_stats_local(self):
        if not LOCAL_CSV.exists():
            return {}
        total, churned, revenue = 0, 0, 0.0
        with LOCAL_CSV.open(newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                total += 1
                if row.get("Churn") == "Yes":
                    churned += 1
                try: revenue += float(row.get("MonthlyCharges") or 0)
                except: pass
        return {"total_customers": total, "churned_customers": churned,
                "churn_rate": churned / total if total else 0,
                "annual_revenue": revenue * 12}

    def log_prediction(self, record):
        if _is_local_mode():
            return
        record.setdefault("predicted_at", datetime.now(tz=timezone.utc).isoformat())
        if isinstance(record.get("top_factors"), (list, dict)):
            record["top_factors"] = json.dumps(record["top_factors"])
        errors = self.client.insert_rows_json(config.predictions_table, [record])
        if errors:
            raise RuntimeError(f"Failed to log prediction: {errors}")

    def log_predictions_bulk(self, records):
        if _is_local_mode():
            return 0
        rows = []
        for r in records:
            r.setdefault("predicted_at", datetime.now(tz=timezone.utc).isoformat())
            if isinstance(r.get("top_factors"), (list, dict)):
                r["top_factors"] = json.dumps(r["top_factors"])
            rows.append(r)
        if not rows:
            return 0
        errors = self.client.insert_rows_json(config.predictions_table, rows)
        if errors:
            raise RuntimeError(f"Bulk insert failed: {errors}")
        return len(rows)

    def log_action(self, record):
        if _is_local_mode():
            return
        record.setdefault("created_at", datetime.now(tz=timezone.utc).isoformat())
        errors = self.client.insert_rows_json(config.actions_table, [record])
        if errors:
            raise RuntimeError(f"Failed to log action: {errors}")

    def register_model(self, record):
        if _is_local_mode():
            return
        record.setdefault("training_date", datetime.now(tz=timezone.utc).isoformat())
        errors = self.client.insert_rows_json(config.registry_table, [record])
        if errors:
            raise RuntimeError(f"Failed to register model: {errors}")


bq = BQ()
