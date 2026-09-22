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
  echo "corepack is required to run openapi-typescript" >&2
  exit 1
fi

PNPM=(corepack pnpm)
CLIENT_PACKAGE_ROOT="${PROJECT_ROOT}/packages/runtime-api-client"

mkdir -p "$(dirname "${OUT_FILE}")"
corepack pnpm --dir "${CLIENT_PACKAGE_ROOT}" exec openapi-typescript \
  "${OPENAPI_FILE}" --output "${OUT_FILE}"
node "${PROJECT_ROOT}/packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs" \
  --types "${OUT_FILE}"
"${PNPM[@]}" exec prettier --write "${OUT_FILE}"
echo "Generated ${OUT_FILE}"
