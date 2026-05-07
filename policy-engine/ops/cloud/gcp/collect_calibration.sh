#!/bin/bash
set -euo pipefail

RUN_LABEL="${1:?Usage: collect_calibration.sh <run_label> [out_dir] [status_pass]}"
OUT_DIR="${2:-/tmp/calibration/${RUN_LABEL}}"
STATUS_PASS="${3:-current}"
SHARD_COUNT="${SHARD_COUNT:-6}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"

mkdir -p "${OUT_DIR}"

for i in $(seq 0 $((SHARD_COUNT - 1))); do
  SHARD_SLUG=$(printf "shard_%02d_of_%02d" "${i}" "${SHARD_COUNT}")
  REMOTE_PREFIX="gs://${BUCKET_NAME}/output/${RUN_LABEL}/${STATUS_PASS}/shard_${i}"
  echo "Shard ${i}: ${REMOTE_PREFIX}"
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/llm_requests.jsonl" \
    "${OUT_DIR}/shard_${i}_llm_requests.jsonl" 2> /dev/null || echo "  (no llm_requests yet)"
  gcloud storage cp \
    "${REMOTE_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl" \
    "${OUT_DIR}/shard_${i}_progress.jsonl" 2> /dev/null || echo "  (no progress yet)"
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/telemetry.json" \
    "${OUT_DIR}/shard_${i}_telemetry.json" 2> /dev/null || true
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/run_config.json" \
    "${OUT_DIR}/shard_${i}_run_config.json" 2> /dev/null || true
  gcloud storage cp \
    "${REMOTE_PREFIX}/pipeline.log" \
    "${OUT_DIR}/shard_${i}_pipeline.log" 2> /dev/null || true
done

echo ""
echo "Telemetry saved to ${OUT_DIR}"
echo "Run: python3 /Users/deniskopylov/polisyos/policy-engine/tools/ops_runners/calibration/compare_shards.py ${OUT_DIR}"
