#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
LOCATION=${LOCATION:-us-central1}
GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-"${PROJECT_ID}-iron-diet-bucket"}

echo "==> Configuring GCP environment for project: ${PROJECT_ID}..."

# 1. Authenticate Application Default Credentials
gcloud auth application-default login --quiet || true
gcloud config set project "${PROJECT_ID}"

# 2. Enable Required Google Cloud APIs
echo "==> Enabling required APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com

# 3. Create GCS Storage Bucket
echo "==> Setting up GCS Bucket: ${GCS_BUCKET_NAME}..."
if ! gcloud storage buckets describe "gs://${GCS_BUCKET_NAME}" &>/dev/null; then
  gcloud storage buckets create "gs://${GCS_BUCKET_NAME}" --location="${LOCATION}"
  echo "Bucket gs://${GCS_BUCKET_NAME} created."
else
  echo "Bucket gs://${GCS_BUCKET_NAME} already exists."
fi

# 4. Grant Vertex AI User Role
echo "==> Assigning IAM roles..."
USER_ACCOUNT=$(gcloud config get-value account)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="user:${USER_ACCOUNT}" \
  --role="roles/aiplatform.user" --quiet

echo "Done."