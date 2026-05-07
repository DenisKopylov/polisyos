#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OPENAPI_FILE="${PROJECT_ROOT}/schemas/runtime_api_v1.openapi.json"
OUT_FILE="${PROJECT_ROOT}/apps/runtime-dashboard/src/api/types.ts"

if command -v pnpm > /dev/null 2>&1; then
  PNPM=(pnpm)
elif command -v corepack > /dev/null 2>&1; then
  PNPM=(corepack pnpm)
else
  echo "pnpm or corepack is required to run openapi-typescript" >&2
  exit 1
fi

"${PNPM[@]}" exec openapi-typescript "${OPENAPI_FILE}" --output "${OUT_FILE}"
"${PNPM[@]}" exec prettier --write "${OUT_FILE}"
echo "Generated ${OUT_FILE}"
