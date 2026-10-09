#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OUTPUT_ROOT="${PROJECT_ROOT}"
OPENAPI_FILE="${PROJECT_ROOT}/schemas/runtime_api_v1.openapi.json"

while (($#)); do
  case "$1" in
    --)
      shift
      ;;
    --output-root)
      if (($# < 2)); then
        echo "--output-root requires a value" >&2
        exit 2
      fi
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --openapi)
      if (($# < 2)); then
        echo "--openapi requires a value" >&2
        exit 2
      fi
      OPENAPI_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "${OUTPUT_ROOT}" != /* ]]; then
  OUTPUT_ROOT="${PWD}/${OUTPUT_ROOT}"
fi

if [[ "${OPENAPI_FILE}" != /* ]]; then
  OPENAPI_FILE="${PROJECT_ROOT}/${OPENAPI_FILE}"
fi

TYPES_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/types.ts"
CANONICAL_TS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/canonicalRuntimeApiClient.ts"
CANONICAL_JS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/canonicalRuntimeApiClient.js"

# Keep the low-level raw pair as a private handoff to the canonicalizer.  Only
# the canonical pair and schema types belong to the declared output family.
SCRATCH_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/polisyos-runtime-api-client.XXXXXXXX")"
RUNTIME_TS_OUT="${SCRATCH_ROOT}/runtimeApiClient.ts"
RUNTIME_JS_OUT="${SCRATCH_ROOT}/runtimeApiClient.js"
cleanup() {
  rm -rf -- "${SCRATCH_ROOT}"
}
trap cleanup EXIT

mkdir -p "$(dirname "${TYPES_OUT}")" "$(dirname "${CANONICAL_TS_OUT}")"
cd "${PROJECT_ROOT}"

node packages/runtime-api-client/scripts/generate-openapi-types.mjs \
  --openapi "${OPENAPI_FILE}" \
  --output "${TYPES_OUT}"
PYTHONPATH=src:. "${PROJECT_ROOT}/.venv/bin/python" \
  tools/ops_runners/runtime/generate_runtime_client.py \
  --openapi "${OPENAPI_FILE}" \
  --out-ts "${RUNTIME_TS_OUT}" \
  --out-js "${RUNTIME_JS_OUT}"
node packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs \
  --openapi "${OPENAPI_FILE}" \
  --client "${RUNTIME_TS_OUT}" \
  --out-ts "${CANONICAL_TS_OUT}" \
  --runtime-js "${RUNTIME_JS_OUT}" \
  --out-js "${CANONICAL_JS_OUT}"

printf 'Generated %s\n' \
  "${TYPES_OUT}" \
  "${CANONICAL_TS_OUT}" \
  "${CANONICAL_JS_OUT}"
