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

OUT_FILE="${OUTPUT_ROOT}/apps/runtime-dashboard/src/api/types.ts"

if ! command -v corepack > /dev/null 2>&1; then
  echo "UNRUN: corepack is required to format the generated dashboard types" >&2
  exit 2
fi
PNPM=(corepack pnpm --dir "${PROJECT_ROOT}/apps/runtime-dashboard")

node "${PROJECT_ROOT}/packages/runtime-api-client/scripts/generate-openapi-types.mjs" \
  --openapi "${OPENAPI_FILE}" \
  --output "${OUT_FILE}"
"${PNPM[@]}" exec prettier --write "${OUT_FILE}"
echo "Generated ${OUT_FILE}"
