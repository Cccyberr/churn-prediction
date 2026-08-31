#!/usr/bin/env bash
# ============================================================
# deploy/schedule_jobs.sh
# Sets up Cloud Scheduler to run the bulk scoring job daily at 02:00.
# ============================================================
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env}"
: "${GCP_REGION:?Set GCP_REGION in .env}"

JOB_NAME="churn-bulk-scorer"
SCHEDULE_NAME="churn-daily-rescore"
SERVICE_ACCOUNT="${SCHEDULER_SA:-churn-scheduler@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"

echo "==> Ensuring Scheduler service account exists..."
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" >/dev/null 2>&1; then
  gcloud iam service-accounts create churn-scheduler \
    --display-name="Churn Scheduler Service Account"
fi

echo "==> Granting run.invoker on the job..."
gcloud run jobs add-iam-policy-binding "$JOB_NAME" \
  --region "$GCP_REGION" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" || true

JOB_URI="https://${GCP_REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT_ID}/jobs/${JOB_NAME}:run"

echo "==> Creating / updating Cloud Scheduler job..."
if gcloud scheduler jobs describe "$SCHEDULE_NAME" --location "$GCP_REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULE_NAME" \
    --location "$GCP_REGION" \
    --schedule="0 2 * * *" \
    --uri="$JOB_URI" \
    --http-method=POST \
    --oauth-service-account-email="$SERVICE_ACCOUNT" \
    --time-zone="Asia/Kolkata"
else
  gcloud scheduler jobs create http "$SCHEDULE_NAME" \
    --location "$GCP_REGION" \
    --schedule="0 2 * * *" \
    --uri="$JOB_URI" \
    --http-method=POST \
    --oauth-service-account-email="$SERVICE_ACCOUNT" \
    --time-zone="Asia/Kolkata"
fi

echo "==> Done. Daily 02:00 IST schedule active."
