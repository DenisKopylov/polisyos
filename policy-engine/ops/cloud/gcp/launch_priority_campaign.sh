#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRODUCT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE_ROOT="$(cd "${PRODUCT_ROOT}/.." && pwd)"

SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-2026-04-05}"
CAMPAIGN_LABEL="${CAMPAIGN_LABEL:-priority-$(date -u +%Y%m%d-%H%M%S)}"
WORKER_SA_EMAIL="${WORKER_SA_EMAIL:-lex-workers@${PROJECT_ID}.iam.gserviceaccount.com}"
REPO_BUNDLE_URI="${REPO_BUNDLE_URI:-}"
PACKAGE_REPO="${PACKAGE_REPO:-1}"

LOCAL_MANIFEST_ROOT="${LOCAL_MANIFEST_ROOT:-${PRODUCT_ROOT}/_build/ops/gcp/priority_manifests}"
GCS_MANIFEST_ROOT="${GCS_MANIFEST_ROOT:-gs://${BUCKET_NAME}/input/priority_manifests/${SNAPSHOT_LABEL}/${CAMPAIGN_LABEL}}"
CURRENT_BASE_CACHE_ROOT="${CURRENT_BASE_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/current/shards_6}"
CURRENT_CAMPAIGN_CACHE_ROOT="${CURRENT_CAMPAIGN_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/current/${CAMPAIGN_LABEL}}"
HISTORY_BASE_CACHE_ROOT="${HISTORY_BASE_CACHE_ROOT:-}"
HISTORY_CAMPAIGN_CACHE_ROOT="${HISTORY_CAMPAIGN_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/history/${CAMPAIGN_LABEL}}"

QUEUE1_OUTPUT_ROOT="gs://${BUCKET_NAME}/output/${CAMPAIGN_LABEL}/current/queue1_core_current"
QUEUE2_OUTPUT_ROOT="gs://${BUCKET_NAME}/output/${CAMPAIGN_LABEL}/current/queue2_fast_useful_current"
HISTORY_OUTPUT_ROOT="gs://${BUCKET_NAME}/output/${CAMPAIGN_LABEL}/history/history_parallel"

QUEUE1_INSTANCE_PREFIX="${QUEUE1_INSTANCE_PREFIX:-lex-q1-${CAMPAIGN_LABEL}}"
QUEUE2_INSTANCE_PREFIX="${QUEUE2_INSTANCE_PREFIX:-lex-q2-${CAMPAIGN_LABEL}}"
HISTORY_INSTANCE_PREFIX="${HISTORY_INSTANCE_PREFIX:-lex-hist-${CAMPAIGN_LABEL}}"

QUEUE_ZONE_MAP="${QUEUE_ZONE_MAP:-0:europe-west2-b,1:europe-west2-b,2:europe-west2-b,3:europe-west3-b,4:europe-west3-b,5:europe-west3-b}"
HISTORY_ZONE_MAP="${HISTORY_ZONE_MAP:-0:europe-west2-b,1:europe-west3-b}"
WATCH_INTERVAL_SEC="${WATCH_INTERVAL_SEC:-300}"
WATCHER_LOG_DIR="${WATCHER_LOG_DIR:-${PRODUCT_ROOT}/_build/logs/gcp_watchers/${CAMPAIGN_LABEL}}"

QUEUE1_RUN_LABEL="${QUEUE1_RUN_LABEL:-${CAMPAIGN_LABEL}-q1}"
QUEUE2_RUN_LABEL="${QUEUE2_RUN_LABEL:-${CAMPAIGN_LABEL}-q2}"
HISTORY_RUN_LABEL="${HISTORY_RUN_LABEL:-${CAMPAIGN_LABEL}-history}"

mkdir -p "${WATCHER_LOG_DIR}"

resolve_bundle() {
  if [ -n "${REPO_BUNDLE_URI}" ]; then
    printf '%s\n' "${REPO_BUNDLE_URI}"
    return 0
  fi

  if [ "${PACKAGE_REPO}" = "1" ]; then
    BUCKET_NAME="${BUCKET_NAME}" UPLOAD=1 "${SCRIPT_DIR}/package_repo.sh" > /dev/null
  fi

  gcloud storage ls "gs://${BUCKET_NAME}/bootstrap/repo/" | tail -n 1
}

build_manifests() {
  local cmd=(
    python3
    "${WORKSPACE_ROOT}/policy-engine/tools/ops_runners/cloud/build_priority_manifests.py"
    --snapshot-label "${SNAPSHOT_LABEL}"
    --campaign-label "${CAMPAIGN_LABEL}"
    --output-root "${LOCAL_MANIFEST_ROOT}"
    --gcs-output-root "${GCS_MANIFEST_ROOT}"
    --current-processed-cache-root "${CURRENT_BASE_CACHE_ROOT}"
    --current-processed-cache-root "${CURRENT_CAMPAIGN_CACHE_ROOT}"
    --queue1-shards 6
    --queue2-shards 6
    --queue3-shards 6
    --history-shards 2
  )

  if [ -n "${HISTORY_BASE_CACHE_ROOT}" ]; then
    cmd+=(--history-processed-cache-root "${HISTORY_BASE_CACHE_ROOT}")
  fi
  cmd+=(--history-processed-cache-root "${HISTORY_CAMPAIGN_CACHE_ROOT}")
  "${cmd[@]}"
}

launch_queue1() {
  PROJECT_ID="${PROJECT_ID}" \
    BUCKET_NAME="${BUCKET_NAME}" \
    WORKER_SA_EMAIL="${WORKER_SA_EMAIL}" \
    SNAPSHOT_LABEL="${SNAPSHOT_LABEL}" \
    REPO_BUNDLE_URI="${REPO_BUNDLE_URI}" \
    QUEUE_NAME="queue1_core_current" \
    STATUS_PASS="current" \
    MANIFEST_BASE_URI="${GCS_MANIFEST_ROOT}/queue1_core_current" \
    OUTPUT_ROOT="${QUEUE1_OUTPUT_ROOT}" \
    INSTANCE_NAME_PREFIX="${QUEUE1_INSTANCE_PREFIX}" \
    SHARD_COUNT=6 \
    SHARD_ZONE_MAP="${QUEUE_ZONE_MAP}" \
    MACHINE_TYPE="t2d-standard-2" \
    BOOT_DISK_SIZE_GB=50 \
    BOOT_DISK_TYPE="pd-ssd" \
    PROVISIONING_MODEL="STANDARD" \
    LOAD_GONKA_SECRETS=1 \
    RESUME_CACHE_ENABLED=1 \
    RESUME_CACHE_ROOT="${CURRENT_CAMPAIGN_CACHE_ROOT}" \
    RPS=5.0 \
    PARALLEL_LLM=16 \
    PARALLEL_LLM_GLOBAL=56 \
    VERIFY_MODE="code" \
    BATCH_CHARS=3600 \
    BATCH_SIZE=3 \
    XML_PARSE_CHUNK=128 \
    RUN_LABEL="${QUEUE1_RUN_LABEL}" \
    GAP_FILL_MODE="narrow" \
    GAP_FILL_SHARE="0.10" \
    HYPOTHESIS="queue1_core_current" \
    "${SCRIPT_DIR}/launch_worker_group.sh"
}

launch_queue2() {
  PROJECT_ID="${PROJECT_ID}" \
    BUCKET_NAME="${BUCKET_NAME}" \
    WORKER_SA_EMAIL="${WORKER_SA_EMAIL}" \
    SNAPSHOT_LABEL="${SNAPSHOT_LABEL}" \
    REPO_BUNDLE_URI="${REPO_BUNDLE_URI}" \
    QUEUE_NAME="queue2_fast_useful_current" \
    STATUS_PASS="current" \
    MANIFEST_BASE_URI="${GCS_MANIFEST_ROOT}/queue2_fast_useful_current" \
    OUTPUT_ROOT="${QUEUE2_OUTPUT_ROOT}" \
    INSTANCE_NAME_PREFIX="${QUEUE2_INSTANCE_PREFIX}" \
    SHARD_COUNT=6 \
    SHARD_ZONE_MAP="${QUEUE_ZONE_MAP}" \
    MACHINE_TYPE="t2d-standard-2" \
    BOOT_DISK_SIZE_GB=50 \
    BOOT_DISK_TYPE="pd-ssd" \
    PROVISIONING_MODEL="STANDARD" \
    LOAD_GONKA_SECRETS=1 \
    RESUME_CACHE_ENABLED=1 \
    RESUME_CACHE_ROOT="${CURRENT_CAMPAIGN_CACHE_ROOT}" \
    RPS=5.0 \
    PARALLEL_LLM=16 \
    PARALLEL_LLM_GLOBAL=56 \
    VERIFY_MODE="code" \
    BATCH_CHARS=3600 \
    BATCH_SIZE=3 \
    XML_PARSE_CHUNK=128 \
    RUN_LABEL="${QUEUE2_RUN_LABEL}" \
    GAP_FILL_MODE="narrow" \
    GAP_FILL_SHARE="0.10" \
    HYPOTHESIS="queue2_fast_useful_current" \
    "${SCRIPT_DIR}/launch_worker_group.sh"
}

launch_history() {
  PROJECT_ID="${PROJECT_ID}" \
    BUCKET_NAME="${BUCKET_NAME}" \
    WORKER_SA_EMAIL="${WORKER_SA_EMAIL}" \
    SNAPSHOT_LABEL="${SNAPSHOT_LABEL}" \
    REPO_BUNDLE_URI="${REPO_BUNDLE_URI}" \
    QUEUE_NAME="history_parallel" \
    STATUS_PASS="history" \
    MANIFEST_BASE_URI="${GCS_MANIFEST_ROOT}/history_parallel" \
    OUTPUT_ROOT="${HISTORY_OUTPUT_ROOT}" \
    INSTANCE_NAME_PREFIX="${HISTORY_INSTANCE_PREFIX}" \
    SHARD_COUNT=2 \
    SHARD_ZONE_MAP="${HISTORY_ZONE_MAP}" \
    MACHINE_TYPE="e2-standard-2" \
    BOOT_DISK_SIZE_GB=40 \
    BOOT_DISK_TYPE="pd-standard" \
    PROVISIONING_MODEL="STANDARD" \
    LOAD_GONKA_SECRETS=0 \
    RESUME_CACHE_ENABLED=1 \
    RESUME_CACHE_ROOT="${HISTORY_CAMPAIGN_CACHE_ROOT}" \
    RPS=1.0 \
    PARALLEL_LLM=1 \
    PARALLEL_LLM_GLOBAL=1 \
    VERIFY_MODE="code" \
    BATCH_CHARS=3600 \
    BATCH_SIZE=3 \
    XML_PARSE_CHUNK=128 \
    RUN_LABEL="${HISTORY_RUN_LABEL}" \
    HYPOTHESIS="history_parallel" \
    "${SCRIPT_DIR}/launch_worker_group.sh"
}

start_watcher() {
  local name="$1"
  shift
  local log_path="${WATCHER_LOG_DIR}/${name}.log"
  nohup "$@" > "${log_path}" 2>&1 &
  echo "Started watcher ${name}: pid=$! log=${log_path}"
}

start_queue1_watcher() {
  local on_shard_complete_cmd
  on_shard_complete_cmd=$(
    cat << EOF
PROJECT_ID=$(printf '%q' "${PROJECT_ID}") \
BUCKET_NAME=$(printf '%q' "${BUCKET_NAME}") \
SNAPSHOT_LABEL=$(printf '%q' "${SNAPSHOT_LABEL}") \
WORKER_SA_EMAIL=$(printf '%q' "${WORKER_SA_EMAIL}") \
REPO_BUNDLE_URI=$(printf '%q' "${REPO_BUNDLE_URI}") \
QUEUE_NAME=queue2_fast_useful_current \
STATUS_PASS=current \
MANIFEST_BASE_URI=$(printf '%q' "${GCS_MANIFEST_ROOT}/queue2_fast_useful_current") \
OUTPUT_ROOT=$(printf '%q' "${QUEUE2_OUTPUT_ROOT}") \
INSTANCE_NAME_PREFIX=$(printf '%q' "${QUEUE2_INSTANCE_PREFIX}") \
SHARD_COUNT=6 \
SHARD_INDICES=__SHARD_INDEX__ \
SHARD_ZONE_MAP=$(printf '%q' "${QUEUE_ZONE_MAP}") \
MACHINE_TYPE=t2d-standard-2 \
BOOT_DISK_SIZE_GB=50 \
BOOT_DISK_TYPE=pd-ssd \
PROVISIONING_MODEL=STANDARD \
LOAD_GONKA_SECRETS=1 \
RESUME_CACHE_ENABLED=1 \
RESUME_CACHE_ROOT=$(printf '%q' "${CURRENT_CAMPAIGN_CACHE_ROOT}") \
RPS=5.0 \
PARALLEL_LLM=16 \
PARALLEL_LLM_GLOBAL=56 \
VERIFY_MODE=code \
BATCH_CHARS=3600 \
BATCH_SIZE=3 \
XML_PARSE_CHUNK=128 \
RUN_LABEL=$(printf '%q' "${QUEUE2_RUN_LABEL}") \
GAP_FILL_MODE=narrow \
GAP_FILL_SHARE=0.10 \
HYPOTHESIS=queue2_fast_useful_current \
SKIP_EXISTING=1 \
${SCRIPT_DIR}/launch_worker_group.sh
EOF
  )

  start_watcher "queue1" env \
    PROJECT_ID="${PROJECT_ID}" \
    INSTANCE_NAME_PREFIX="${QUEUE1_INSTANCE_PREFIX}" \
    OUTPUT_ROOT="${QUEUE1_OUTPUT_ROOT}" \
    SHARD_COUNT=6 \
    SHARD_ZONE_MAP="${QUEUE_ZONE_MAP}" \
    CHECK_INTERVAL_SEC="${WATCH_INTERVAL_SEC}" \
    ON_SHARD_COMPLETE_CMD_TEMPLATE="${on_shard_complete_cmd}" \
    STATE_DIR="${WATCHER_LOG_DIR}/queue1-promotions" \
    "${SCRIPT_DIR}/watch_worker_group.sh"
}

start_queue2_watcher() {
  start_watcher "queue2" env \
    PROJECT_ID="${PROJECT_ID}" \
    INSTANCE_NAME_PREFIX="${QUEUE2_INSTANCE_PREFIX}" \
    OUTPUT_ROOT="${QUEUE2_OUTPUT_ROOT}" \
    SHARD_COUNT=6 \
    SHARD_ZONE_MAP="${QUEUE_ZONE_MAP}" \
    CHECK_INTERVAL_SEC="${WATCH_INTERVAL_SEC}" \
    "${SCRIPT_DIR}/watch_worker_group.sh"
}

start_history_watcher() {
  start_watcher "history" env \
    PROJECT_ID="${PROJECT_ID}" \
    INSTANCE_NAME_PREFIX="${HISTORY_INSTANCE_PREFIX}" \
    OUTPUT_ROOT="${HISTORY_OUTPUT_ROOT}" \
    SHARD_COUNT=2 \
    SHARD_ZONE_MAP="${HISTORY_ZONE_MAP}" \
    CHECK_INTERVAL_SEC="${WATCH_INTERVAL_SEC}" \
    "${SCRIPT_DIR}/watch_worker_group.sh"
}

REPO_BUNDLE_URI="$(resolve_bundle)"
build_manifests
launch_queue1
launch_history
start_queue1_watcher
start_queue2_watcher
start_history_watcher

echo "Campaign ready."
echo "Campaign label: ${CAMPAIGN_LABEL}"
echo "Manifest root: ${GCS_MANIFEST_ROOT}"
