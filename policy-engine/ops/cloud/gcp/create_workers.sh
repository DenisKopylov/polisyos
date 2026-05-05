#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
ZONE="${ZONE:-europe-west1-b}"
SHARD_COUNT="${SHARD_COUNT:-6}"
STATUS_PASS="${STATUS_PASS:-current}"
WORKER_MODE="${WORKER_MODE:-preflight}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
WORKER_SA_EMAIL="${WORKER_SA_EMAIL:?Set WORKER_SA_EMAIL}"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-2026-04-05}"
REPO_BUNDLE_URI="${REPO_BUNDLE_URI:?Set REPO_BUNDLE_URI}"
MACHINE_TYPE="${MACHINE_TYPE:-t2d-standard-2}"
INSTANCE_NAME_PREFIX="${INSTANCE_NAME_PREFIX:-lex-worker}"
START_INDEX="${START_INDEX:-0}"
END_INDEX="${END_INDEX:-$((SHARD_COUNT - 1))}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
SHARD_ZONE_MAP="${SHARD_ZONE_MAP:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "${WORKER_MODE}" = "preflight" ]; then
  BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-30}"
  BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-standard}"
  RESUME_CACHE_ENABLED="${RESUME_CACHE_ENABLED:-0}"
else
  BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-80}"
  BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-ssd}"
  RESUME_CACHE_ENABLED="${RESUME_CACHE_ENABLED:-1}"
fi
RESUME_CACHE_ROOT="${RESUME_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/${STATUS_PASS}/shards_${SHARD_COUNT}}"

gcloud config set project "${PROJECT_ID}" > /dev/null

if [ "${START_INDEX}" -lt 0 ] || [ "${END_INDEX}" -lt "${START_INDEX}" ] || [ "${END_INDEX}" -ge "${SHARD_COUNT}" ]; then
  echo "Invalid shard window: START_INDEX=${START_INDEX} END_INDEX=${END_INDEX} SHARD_COUNT=${SHARD_COUNT}"
  exit 1
fi

echo "=== Create workers ==="
echo "project=${PROJECT_ID} zone=${ZONE} machine_type=${MACHINE_TYPE} shards=${START_INDEX}-${END_INDEX}/${SHARD_COUNT} mode=${WORKER_MODE}"

resolve_zone() {
  local shard_index="$1"
  local entry=""
  local shard=""
  local zone_override=""

  if [ -n "${SHARD_ZONE_MAP}" ]; then
    IFS=',' read -r -a zone_entries <<< "${SHARD_ZONE_MAP}"
    for entry in "${zone_entries[@]}"; do
      shard="${entry%%:*}"
      zone_override="${entry#*:}"
      if [ "${shard}" = "${shard_index}" ] && [ -n "${zone_override}" ]; then
        printf '%s\n' "${zone_override}"
        return 0
      fi
    done
  fi

  printf '%s\n' "${ZONE}"
}

for i in $(seq "${START_INDEX}" "${END_INDEX}"); do
  ACCOUNT_NUM=$((i + 1))
  INSTANCE_NAME="${INSTANCE_NAME_PREFIX}-${i}"
  INSTANCE_ZONE="$(resolve_zone "${i}")"
  OUTPUT_PREFIX="gs://${BUCKET_NAME}/debug/preflight/${STATUS_PASS}/shard_${i}"
  RESUME_CACHE_PREFIX="${RESUME_CACHE_ROOT}/shard_${i}"
  META="project-id=${PROJECT_ID}"
  META="${META},bucket-name=${BUCKET_NAME}"
  META="${META},repo-bundle-uri=${REPO_BUNDLE_URI}"
  META="${META},snapshot-label=${SNAPSHOT_LABEL}"
  META="${META},status-pass=${STATUS_PASS}"
  META="${META},worker-mode=${WORKER_MODE}"
  META="${META},shard-index=${i}"
  META="${META},shard-count=${SHARD_COUNT}"
  META="${META},account-num=${ACCOUNT_NUM}"
  META="${META},output-prefix=${OUTPUT_PREFIX}"
  META="${META},resume-cache-enabled=${RESUME_CACHE_ENABLED}"
  if [ "${RESUME_CACHE_ENABLED}" = "1" ]; then
    META="${META},resume-cache-prefix=${RESUME_CACHE_PREFIX}"
  fi

  if gcloud compute instances describe "${INSTANCE_NAME}" --zone="${INSTANCE_ZONE}" > /dev/null 2>&1; then
    if [ "${SKIP_EXISTING}" = "1" ]; then
      echo "Skipping existing instance ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
      continue
    fi
    echo "Instance already exists: ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
    exit 1
  fi

  gcloud compute instances create "${INSTANCE_NAME}" \
    --zone="${INSTANCE_ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    --boot-disk-size="${BOOT_DISK_SIZE_GB}GB" \
    --boot-disk-type="${BOOT_DISK_TYPE}" \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --service-account="${WORKER_SA_EMAIL}" \
    --scopes=cloud-platform \
    --metadata="${META},serial-port-enable=TRUE" \
    --metadata-from-file=startup-script="${SCRIPT_DIR}/startup.sh" \
    --tags=lex-worker \
    --provisioning-model=SPOT \
    --maintenance-policy=TERMINATE \
    --instance-termination-action=STOP

  echo "Created ${INSTANCE_NAME} zone=${INSTANCE_ZONE} account=${ACCOUNT_NUM} mode=${WORKER_MODE}"
done

echo ""
gcloud compute instances list --filter="name~^${INSTANCE_NAME_PREFIX}-" \
  --format="table(name,status,machineType.basename(),networkInterfaces[0].accessConfigs[0].natIP)"
