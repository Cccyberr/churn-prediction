#!/usr/bin/env bash
# ============================================================
# deploy/deploy_app.sh
# Deploys the Flask web app to Cloud Run.
# Run from the project root: bash deploy/deploy_app.sh
# ============================================================
set -euo pipefail

# Load env vars
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env}"
: "${GCP_REGION:?Set GCP_REGION in .env}"
: "${BQ_DATASET:=telco_churn}"
: "${SERVICE_NAME:=churn-app}"

echo "==> Project:  $GCP_PROJECT_ID"
echo "==> Region:   $GCP_REGION"
echo "==> Service:  $SERVICE_NAME"

gcloud config set project "$GCP_PROJECT_ID" >/dev/null

# Build env-vars string for Cloud Run (only non-secret values)
ENV_VARS="GCP_PROJECT_ID=${GCP_PROJECT_ID}"
ENV_VARS+=",GCP_REGION=${GCP_REGION}"
ENV_VARS+=",BQ_DATASET=${BQ_DATASET}"
ENV_VARS+=",USE_VERTEX_ENDPOINT=${USE_VERTEX_ENDPOINT:-false}"
ENV_VARS+=",VERTEX_ENDPOINT_ID=${VERTEX_ENDPOINT_ID:-}"
ENV_VARS+=",GEMINI_MODEL=${GEMINI_MODEL:-gemini-1.5-flash}"
ENV_VARS+=",ADMIN_USERNAME=${ADMIN_USERNAME:-admin}"
ENV_VARS+=",SERVICE_NAME=${SERVICE_NAME}"

# Secrets are passed separately. Easiest path for a student demo:
# put them inline. For production, use Secret Manager.
SECRET_VARS=""
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  SECRET_VARS+="GEMINI_API_KEY=${GEMINI_API_KEY},"
fi
if [[ -n "${FLASK_SECRET_KEY:-}" ]]; then
  SECRET_VARS+="FLASK_SECRET_KEY=${FLASK_SECRET_KEY},"
fi
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
  SECRET_VARS+="ADMIN_PASSWORD=${ADMIN_PASSWORD},"
fi
SECRET_VARS="${SECRET_VARS%,}"

EXTRA_FLAGS=()
if [[ -n "$SECRET_VARS" ]]; then
  EXTRA_FLAGS+=(--update-env-vars "$SECRET_VARS")
fi

echo "==> Deploying via gcloud run deploy (Cloud Build will containerize)..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 5 \
  --min-instances 0 \
  --concurrency 80 \
  --set-env-vars "$ENV_VARS" \
  "${EXTRA_FLAGS[@]}"

echo
echo "==> Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format='value(status.url)'
