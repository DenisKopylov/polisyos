#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-polisyos-lex}"
PROJECT_NAME="${PROJECT_NAME:-PolicyOS Lex Pipeline}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:?Set BILLING_ACCOUNT_ID}"
REGION="${REGION:-europe-west1}"
ZONE="${ZONE:-europe-west1-b}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-data}"
WORKER_SA_NAME="${WORKER_SA_NAME:-lex-workers}"

ACTIVE_ACCOUNT="$(gcloud config get-value account 2> /dev/null || true)"
WORKER_SA_EMAIL="${WORKER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== GCP bootstrap ==="
echo "Account: ${ACTIVE_ACCOUNT}"
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Zone:    ${ZONE}"
echo "Bucket:  ${BUCKET_NAME}"
echo ""

if ! gcloud projects describe "${PROJECT_ID}" > /dev/null 2>&1; then
  echo "[1/6] Creating project ${PROJECT_ID} ..."
  gcloud projects create "${PROJECT_ID}" --name="${PROJECT_NAME}"
else
  echo "[1/6] Project ${PROJECT_ID} already exists"
fi

echo "[2/6] Setting active project ..."
gcloud config set project "${PROJECT_ID}" > /dev/null

echo "[3/6] Linking billing ..."
gcloud billing projects link "${PROJECT_ID}" \
  --billing-account="${BILLING_ACCOUNT_ID}" > /dev/null

echo "[4/6] Enabling APIs ..."
gcloud services enable \
  compute.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  serviceusage.googleapis.com \
  oslogin.googleapis.com > /dev/null

echo "[5/6] Ensuring worker service account exists ..."
if ! gcloud iam service-accounts describe "${WORKER_SA_EMAIL}" > /dev/null 2>&1; then
  gcloud iam service-accounts create "${WORKER_SA_NAME}" \
    --display-name="PolicyOS Lex Workers" > /dev/null
else
  echo "  Service account already exists: ${WORKER_SA_EMAIL}"
fi

for role in \
  roles/secretmanager.secretAccessor \
  roles/storage.objectAdmin \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${WORKER_SA_EMAIL}" \
    --role="${role}" \
    --quiet > /dev/null
done

echo "[6/6] Ensuring bucket exists ..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" > /dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="${REGION}" \
    --default-storage-class=STANDARD > /dev/null
else
  echo "  Bucket already exists: gs://${BUCKET_NAME}"
fi

echo ""
echo "Bootstrap complete."
echo "Worker service account: ${WORKER_SA_EMAIL}"
