#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
QUEUE_NAME="${QUEUE_NAME:?Set QUEUE_NAME}"
STATUS_PASS="${STATUS_PASS:?Set STATUS_PASS}"
MANIFEST_BASE_URI="${MANIFEST_BASE_URI:?Set MANIFEST_BASE_URI}"
OUTPUT_ROOT="${OUTPUT_ROOT:?Set OUTPUT_ROOT}"
INSTANCE_NAME_PREFIX="${INSTANCE_NAME_PREFIX:?Set INSTANCE_NAME_PREFIX}"
SHARD_COUNT="${SHARD_COUNT:?Set SHARD_COUNT}"
SHARD_INDICES="${SHARD_INDICES:-}"

WORKER_SA_EMAIL="${WORKER_SA_EMAIL:-lex-workers@${PROJECT_ID}.iam.gserviceaccount.com}"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-2026-04-05}"
RUN_LABEL="${RUN_LABEL:-${QUEUE_NAME}-$(date -u +%Y%m%d-%H%M%S)}"
REPO_BUNDLE_URI="${REPO_BUNDLE_URI:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

MACHINE_TYPE="${MACHINE_TYPE:-t2d-standard-2}"
BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-50}"
BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-ssd}"
PROVISIONING_MODEL="${PROVISIONING_MODEL:-STANDARD}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-1}"
SYNC_INTERVAL_SEC="${SYNC_INTERVAL_SEC:-120}"
ZONE="${ZONE:-europe-west2-b}"
SHARD_ZONE_MAP="${SHARD_ZONE_MAP:-}"
SKIP_EXISTING="${SKIP_EXISTING:-0}"
LOAD_GONKA_SECRETS="${LOAD_GONKA_SECRETS:-1}"
ACCOUNT_START_NUM="${ACCOUNT_START_NUM:-1}"
ACCOUNT_NUM_MAP="${ACCOUNT_NUM_MAP:-}"
RESUME_CACHE_ENABLED="${RESUME_CACHE_ENABLED:-1}"
RESUME_CACHE_ROOT="${RESUME_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/${STATUS_PASS}/${QUEUE_NAME}}"

RPS="${RPS:-5.0}"
PARALLEL_LLM="${PARALLEL_LLM:-16}"
PARALLEL_LLM_GLOBAL="${PARALLEL_LLM_GLOBAL:-56}"
MAX_DOCS="${MAX_DOCS:-0}"
VERIFY_MODE="${VERIFY_MODE:-code}"
BATCH_CHARS="${BATCH_CHARS:-3600}"
BATCH_SIZE="${BATCH_SIZE:-3}"
WARMUP_SEC="${WARMUP_SEC:-30}"
WARMUP_SCALE="${WARMUP_SCALE:-2.0}"
ADAPTIVE_RECOVERY="${ADAPTIVE_RECOVERY:-0.97}"
ADAPTIVE_PENALTY="${ADAPTIVE_PENALTY:-1.35}"
ADAPTIVE_MAX_SCALE="${ADAPTIVE_MAX_SCALE:-4.0}"
GROUP_TIMEOUT="${GROUP_TIMEOUT:-45}"
FOLLOWUP_SCALE="${FOLLOWUP_SCALE:-0.85}"
STRUCTURE_WORKERS="${STRUCTURE_WORKERS:-2}"
XML_PARSE_CHUNK="${XML_PARSE_CHUNK:-128}"
GAP_FILL_MODE="${GAP_FILL_MODE:-narrow}"
GAP_FILL_SHARE="${GAP_FILL_SHARE:-0.10}"
HYPOTHESIS="${HYPOTHESIS:-${QUEUE_NAME}}"
QUALITY_MAX_FULL_ONLY_DOCS_PCT="${QUALITY_MAX_FULL_ONLY_DOCS_PCT:-25.0}"

if [ -z "${REPO_BUNDLE_URI}" ]; then
  REPO_BUNDLE_URI="$(gcloud storage ls "gs://${BUCKET_NAME}/bootstrap/repo/" | tail -n 1)"
fi

if [ -z "${REPO_BUNDLE_URI}" ]; then
  echo "Unable to resolve REPO_BUNDLE_URI"
  exit 1
fi

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

resolve_account_num() {
  local shard_index="$1"
  local entry=""
  local shard=""
  local account_override=""

  if [ -n "${ACCOUNT_NUM_MAP}" ]; then
    IFS=',' read -r -a account_entries <<< "${ACCOUNT_NUM_MAP}"
    for entry in "${account_entries[@]}"; do
      shard="${entry%%:*}"
      account_override="${entry#*:}"
      if [ "${shard}" = "${shard_index}" ] && [ -n "${account_override}" ]; then
        printf '%s\n' "${account_override}"
        return 0
      fi
    done
  fi

  printf '%s\n' "$((ACCOUNT_START_NUM + shard_index))"
}

gcloud config set project "${PROJECT_ID}" > /dev/null

echo "=== Launch worker group ==="
echo "project=${PROJECT_ID} queue=${QUEUE_NAME} status=${STATUS_PASS} run_label=${RUN_LABEL}"
echo "manifest_base=${MANIFEST_BASE_URI}"
echo "resume_cache_root=${RESUME_CACHE_ROOT}"
echo ""

if [ -n "${SHARD_INDICES}" ]; then
  IFS=',' read -r -a SHARD_INDEX_LIST <<< "${SHARD_INDICES}"
else
  SHARD_INDEX_LIST=()
  for i in $(seq 0 $((SHARD_COUNT - 1))); do
    SHARD_INDEX_LIST+=("${i}")
  done
fi

for i in "${SHARD_INDEX_LIST[@]}"; do
  ACCOUNT_NUM="$(resolve_account_num "${i}")"
  INSTANCE_NAME="${INSTANCE_NAME_PREFIX}-${i}"
  INSTANCE_ZONE="$(resolve_zone "${i}")"
  MANIFEST_NAME="$(printf 'shard_%02d_of_%02d.jsonl.zst' "${i}" "${SHARD_COUNT}")"
  MANIFEST_URI="${MANIFEST_BASE_URI%/}/${MANIFEST_NAME}"
  OUTPUT_PREFIX="${OUTPUT_ROOT%/}/shard_${i}"

  META="project-id=${PROJECT_ID}"
  META="${META},bucket-name=${BUCKET_NAME}"
  META="${META},repo-bundle-uri=${REPO_BUNDLE_URI}"
  META="${META},snapshot-label=${SNAPSHOT_LABEL}"
  META="${META},status-pass=${STATUS_PASS}"
  META="${META},worker-mode=run"
  META="${META},queue-name=${QUEUE_NAME}"
  META="${META},run-label=${RUN_LABEL}"
  META="${META},shard-index=${i}"
  META="${META},shard-count=${SHARD_COUNT}"
  META="${META},account-num=${ACCOUNT_NUM}"
  META="${META},manifest-uri=${MANIFEST_URI}"
  META="${META},output-prefix=${OUTPUT_PREFIX}"
  META="${META},max-docs=${MAX_DOCS}"
  META="${META},rps=${RPS}"
  META="${META},parallel-llm=${PARALLEL_LLM}"
  META="${META},parallel-llm-global=${PARALLEL_LLM_GLOBAL}"
  META="${META},batch-chars=${BATCH_CHARS}"
  META="${META},batch-size=${BATCH_SIZE}"
  META="${META},warmup-sec=${WARMUP_SEC}"
  META="${META},warmup-scale=${WARMUP_SCALE}"
  META="${META},adaptive-recovery=${ADAPTIVE_RECOVERY}"
  META="${META},adaptive-penalty=${ADAPTIVE_PENALTY}"
  META="${META},adaptive-max-scale=${ADAPTIVE_MAX_SCALE}"
  META="${META},group-timeout=${GROUP_TIMEOUT}"
  META="${META},followup-scale=${FOLLOWUP_SCALE}"
  META="${META},structure-workers=${STRUCTURE_WORKERS}"
  META="${META},xml-parse-chunk=${XML_PARSE_CHUNK}"
  META="${META},spo-verify-mode=${VERIFY_MODE}"
  META="${META},gap-fill-mode=${GAP_FILL_MODE}"
  META="${META},gap-fill-share=${GAP_FILL_SHARE}"
  META="${META},hypothesis=${HYPOTHESIS}"
  META="${META},quality-max-full-only-docs-pct=${QUALITY_MAX_FULL_ONLY_DOCS_PCT}"
  META="${META},sync-interval-sec=${SYNC_INTERVAL_SEC}"
  META="${META},auto-shutdown=${AUTO_SHUTDOWN}"
  META="${META},load-gonka-secrets=${LOAD_GONKA_SECRETS}"
  META="${META},resume-cache-enabled=${RESUME_CACHE_ENABLED}"
  if [ "${RESUME_CACHE_ENABLED}" = "1" ]; then
    META="${META},resume-cache-prefix=${RESUME_CACHE_ROOT}"
  fi

  if gcloud compute instances describe "${INSTANCE_NAME}" --zone="${INSTANCE_ZONE}" > /dev/null 2>&1; then
    if [ "${SKIP_EXISTING}" = "1" ]; then
      echo "Skipping existing instance ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
      continue
    fi
    echo "Instance already exists: ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
    exit 1
  fi

  CREATE_ARGS=(
    compute instances create "${INSTANCE_NAME}"
    --zone="${INSTANCE_ZONE}"
    --machine-type="${MACHINE_TYPE}"
    --boot-disk-size="${BOOT_DISK_SIZE_GB}GB"
    --boot-disk-type="${BOOT_DISK_TYPE}"
    --image-family=ubuntu-2404-lts-amd64
    --image-project=ubuntu-os-cloud
    --service-account="${WORKER_SA_EMAIL}"
    --scopes=cloud-platform
    --metadata="${META},serial-port-enable=TRUE"
    --metadata-from-file=startup-script="${SCRIPT_DIR}/startup.sh"
    --tags=lex-worker
    --provisioning-model="${PROVISIONING_MODEL}"
  )

  if [ "${PROVISIONING_MODEL}" = "SPOT" ]; then
    CREATE_ARGS+=(
      --maintenance-policy=TERMINATE
      --instance-termination-action=STOP
    )
  fi

  gcloud "${CREATE_ARGS[@]}" > /dev/null

  printf "  %-18s zone=%-15s account=%-2s status=%-8s disk=%-11s max_docs=%s\n" \
    "${INSTANCE_NAME}" "${INSTANCE_ZONE}" "${ACCOUNT_NUM}" "${STATUS_PASS}" "${BOOT_DISK_TYPE}" "${MAX_DOCS}"
done

echo ""
gcloud compute instances list --filter="name~^${INSTANCE_NAME_PREFIX}-" \
  --format="table(name,status,zone.basename(),machineType.basename(),networkInterfaces[0].accessConfigs[0].natIP)"
