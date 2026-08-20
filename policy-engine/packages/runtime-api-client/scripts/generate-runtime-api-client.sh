#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OUTPUT_ROOT="${PROJECT_ROOT}"

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
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "${OUTPUT_ROOT}" != /* ]]; then
  OUTPUT_ROOT="${PWD}/${OUTPUT_ROOT}"
fi

OPENAPI_FILE="schemas/runtime_api_v1.openapi.json"
TYPES_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/types.ts"
RUNTIME_TS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/runtimeApiClient.ts"
RUNTIME_JS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/runtimeApiClient.js"
CANONICAL_TS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/canonicalRuntimeApiClient.ts"
CANONICAL_JS_OUT="${OUTPUT_ROOT}/packages/runtime-api-client/canonicalRuntimeApiClient.js"

mkdir -p "$(dirname "${TYPES_OUT}")"
cd "${PROJECT_ROOT}"

npx --yes openapi-typescript@7.13.0 "${OPENAPI_FILE}" -o "${TYPES_OUT}"
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
  "${RUNTIME_TS_OUT}" \
  "${RUNTIME_JS_OUT}" \
  "${CANONICAL_TS_OUT}" \
  "${CANONICAL_JS_OUT}"
