#!/usr/bin/env bash
# ============================================================
# deploy/deploy_job.sh
# Builds the bulk-scoring job image and registers it as a Cloud Run Job.
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
: "${BQ_DATASET:=telco_churn}"

JOB_NAME="churn-bulk-scorer"
IMAGE="gcr.io/${GCP_PROJECT_ID}/${JOB_NAME}:latest"

echo "==> Building image: ${IMAGE}"
gcloud builds submit \
  --tag "$IMAGE" \
  --project "$GCP_PROJECT_ID" \
  --config /dev/stdin <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'jobs/Dockerfile.job', '-t', '${IMAGE}', '.']
images: ['${IMAGE}']
EOF

echo "==> Creating / updating Cloud Run Job: ${JOB_NAME}"
if gcloud run jobs describe "$JOB_NAME" --region "$GCP_REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB_NAME" \
    --image "$IMAGE" \
    --region "$GCP_REGION" \
    --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID},BQ_DATASET=${BQ_DATASET}" \
    --memory 2Gi \
    --cpu 2 \
    --task-timeout 1800
else
  gcloud run jobs create "$JOB_NAME" \
    --image "$IMAGE" \
    --region "$GCP_REGION" \
    --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID},BQ_DATASET=${BQ_DATASET}" \
    --memory 2Gi \
    --cpu 2 \
    --task-timeout 1800
fi

echo "==> Done. Trigger manually with:"
echo "    gcloud run jobs execute $JOB_NAME --region $GCP_REGION"
