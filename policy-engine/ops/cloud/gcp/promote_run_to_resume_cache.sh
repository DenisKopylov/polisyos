#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
RUN_LABEL="${1:?Usage: promote_run_to_resume_cache.sh <run_label> [status_pass] [snapshot_label] [shard_count]}"
STATUS_PASS="${2:-current}"
SNAPSHOT_LABEL="${3:-2026-04-05}"
SHARD_COUNT="${4:-6}"
RESUME_CACHE_ROOT="${RESUME_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/${STATUS_PASS}/shards_${SHARD_COUNT}}"

SYNCABLE_CACHE_DIRS=(
  provisions
  references
  domains
  spo_results
  spo_grounded
  resolved_references
)

gcloud config set project "${PROJECT_ID}" > /dev/null

sync_dir() {
  local src_dir="$1"
  local dst_dir="$2"
  gcloud storage rsync -r "${src_dir}/" "${dst_dir}/" > /dev/null 2>&1 || true
}

sync_file() {
  local src_file="$1"
  local dst_file="$2"
  gcloud storage cp "${src_file}" "${dst_file}" > /dev/null 2>&1 || true
}

echo "=== Promote run into resume cache ==="
echo "project=${PROJECT_ID} run_label=${RUN_LABEL} status=${STATUS_PASS} snapshot=${SNAPSHOT_LABEL}"
echo "resume_cache_root=${RESUME_CACHE_ROOT}"
echo ""

for i in $(seq 0 $((SHARD_COUNT - 1))); do
  SHARD_SLUG="$(printf 'shard_%02d_of_%02d' "${i}" "${SHARD_COUNT}")"
  RUN_PREFIX="gs://${BUCKET_NAME}/output/${RUN_LABEL}/${STATUS_PASS}/shard_${i}"
  CACHE_PREFIX="${RESUME_CACHE_ROOT}/shard_${i}"

  echo "Shard ${i}: ${RUN_PREFIX} -> ${CACHE_PREFIX}"
  sync_file \
    "${RUN_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl" \
    "${CACHE_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl"
  sync_file \
    "${RUN_PREFIX}/manifests/doc_metadata.json" \
    "${CACHE_PREFIX}/manifests/doc_metadata.json"

  for dir_name in "${SYNCABLE_CACHE_DIRS[@]}"; do
    sync_dir "${RUN_PREFIX}/${dir_name}" "${CACHE_PREFIX}/${dir_name}"
  done
done

echo ""
echo "Resume cache updated at ${RESUME_CACHE_ROOT}"
