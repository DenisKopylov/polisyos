#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-2026-04-05}"
PRE_SHARDED_ROOT="${PRE_SHARDED_ROOT:-${WORKSPACE_ROOT}/data/data_lex/pre_sharded/${SNAPSHOT_LABEL}}"
RAW_DATA_ROOT="${RAW_DATA_ROOT:-${WORKSPACE_ROOT}/data/data_lex}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
INCLUDE_RAW_XML="${INCLUDE_RAW_XML:-0}"

if [ ! -d "${PRE_SHARDED_ROOT}" ]; then
  echo "Pre-sharded root not found: ${PRE_SHARDED_ROOT}"
  exit 1
fi

DEST_ROOT="gs://${BUCKET_NAME}/input/pre_sharded/${SNAPSHOT_LABEL}"
echo "Uploading pre-sharded inputs to ${DEST_ROOT}"
gcloud storage rsync -r "${PRE_SHARDED_ROOT}" "${DEST_ROOT}"

if [ "${INCLUDE_RAW_XML}" = "1" ]; then
  echo "Uploading raw XML snapshot ..."
  gcloud storage cp \
    "${RAW_DATA_ROOT}/edrnpa_cards_${SNAPSHOT_LABEL}.xml" \
    "gs://${BUCKET_NAME}/input/raw/"
  gcloud storage cp \
    "${RAW_DATA_ROOT}/edrnpa_texts_${SNAPSHOT_LABEL}.xml" \
    "gs://${BUCKET_NAME}/input/raw/"
fi

echo "Input upload complete."
