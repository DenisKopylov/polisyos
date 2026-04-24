#!/bin/bash
set -euo pipefail

BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
STATUS_PASS="${STATUS_PASS:-current}"
SHARD_COUNT="${SHARD_COUNT:-6}"
OUT_DIR="${1:-/tmp/polisyos-gcp-preflight}"

mkdir -p "${OUT_DIR}"

for i in $(seq 0 $((SHARD_COUNT - 1))); do
  SRC="gs://${BUCKET_NAME}/debug/preflight/${STATUS_PASS}/shard_${i}/preflight.json"
  DST="${OUT_DIR}/shard_${i}_preflight.json"
  if gcloud storage cp "${SRC}" "${DST}" > /dev/null 2>&1; then
    echo "Downloaded shard ${i} -> ${DST}"
  else
    echo "Missing preflight report for shard ${i}"
  fi
done

echo ""
echo "Reports saved to ${OUT_DIR}"
