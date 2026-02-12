#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OPENAPI_FILE="${PROJECT_ROOT}/schemas/runtime_api_v1.openapi.json"
OUT_FILE="${PROJECT_ROOT}/frontend/runtime-dashboard/src/api/types.ts"

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required to run openapi-typescript" >&2
  exit 1
fi

npx --yes openapi-typescript "${OPENAPI_FILE}" --output "${OUT_FILE}"
echo "Generated ${OUT_FILE}"
