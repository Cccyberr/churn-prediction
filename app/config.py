"""Centralised config loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Config:
    # GCP
    project_id: str = os.getenv("GCP_PROJECT_ID", "")
    region: str = os.getenv("GCP_REGION", "us-central1")

    # BigQuery
    bq_dataset: str = os.getenv("BQ_DATASET", "telco_churn")

    # Storage
    gcs_model_bucket: str = os.getenv("GCS_MODEL_BUCKET", "")
    gcs_uploads_bucket: str = os.getenv("GCS_UPLOADS_BUCKET", "")

    # Vertex
    use_vertex_endpoint: bool = _bool("USE_VERTEX_ENDPOINT", False)
    vertex_endpoint_id: str = os.getenv("VERTEX_ENDPOINT_ID", "")

    # Model artifacts
    model_local_path: str = os.getenv("MODEL_LOCAL_PATH", "model_artifacts/model.joblib")
    features_meta_path: str = os.getenv("FEATURES_META_PATH", "model_artifacts/features_meta.json")

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Flask
    flask_secret_key: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    flask_env: str = os.getenv("FLASK_ENV", "production")

    # Admin
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")

    # Service
    service_name: str = os.getenv("SERVICE_NAME", "churn-app")

    @property
    def predictions_table(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.predictions"

    @property
    def customers_table(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.customers"

    @property
    def actions_table(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.retention_actions"

    @property
    def registry_table(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.model_registry"


config = Config()
