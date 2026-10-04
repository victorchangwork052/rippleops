#!/usr/bin/env bash
# Deploy RippleOps to Cloud Run (API + web) using Cloud Build from source.
#
#   PROJECT=my-project REGION=us-central1 scripts/deploy_cloud_run.sh
#
# Prerequisites: gcloud authenticated with rights to enable services, create a
# service account and deploy Cloud Run; BigQuery seeded with
# scripts/seed_bigquery.py --project "$PROJECT".
set -euo pipefail

PROJECT="${PROJECT:?Set PROJECT to your Google Cloud project ID}"
REGION="${REGION:-us-central1}"
DATASET="${DATASET:-rippleops}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
SA_NAME="rippleops-api"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Enabling services"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  bigquery.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

echo "==> Least-privilege service account for the API"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" --display-name "RippleOps API"
for role in roles/bigquery.jobUser roles/bigquery.dataViewer roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${SA}" --role "$role" \
    --condition None --quiet >/dev/null
done

echo "==> Deploying API"
# One instance keeps the in-process demo state (events, scenarios, actions) consistent.
gcloud run deploy rippleops-api --quiet --project "$PROJECT" --region "$REGION" --source "$ROOT/apps/api" \
  --service-account "$SA" --allow-unauthenticated --min-instances 1 --max-instances 1 --memory 2Gi --timeout 600 \
  --set-env-vars "APP_ENV=production,DATA_BACKEND=bigquery,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},BIGQUERY_DATASET=${DATASET},GEMINI_MODEL=${GEMINI_MODEL},GOOGLE_GENAI_USE_VERTEXAI=true"
API_URL="$(gcloud run services describe rippleops-api --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"

echo "==> Deploying web"
gcloud run deploy rippleops-web --quiet --project "$PROJECT" --region "$REGION" --source "$ROOT/apps/web" \
  --allow-unauthenticated --set-env-vars "API_BASE_URL=${API_URL}"
WEB_URL="$(gcloud run services describe rippleops-web --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"

# Browsers only call the web service; restrict API CORS to it.
gcloud run services update rippleops-api --project "$PROJECT" --region "$REGION" \
  --update-env-vars "CORS_ORIGINS=${WEB_URL}" >/dev/null

echo "==> Smoke test"
curl -fsS "${API_URL}/api/health" && echo
curl -fsS -o /dev/null -w "web: HTTP %{http_code}\n" "${WEB_URL}/"
echo "RippleOps is live at ${WEB_URL}"
