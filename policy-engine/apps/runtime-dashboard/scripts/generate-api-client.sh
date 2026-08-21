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

OPENAPI_FILE="${PROJECT_ROOT}/schemas/runtime_api_v1.openapi.json"
OUT_FILE="${OUTPUT_ROOT}/apps/runtime-dashboard/src/api/types.ts"

if command -v pnpm > /dev/null 2>&1; then
  PNPM=(pnpm)
elif command -v corepack > /dev/null 2>&1; then
  PNPM=(corepack pnpm)
else
  echo "pnpm or corepack is required to run openapi-typescript" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT_FILE}")"
"${PNPM[@]}" exec openapi-typescript "${OPENAPI_FILE}" --output "${OUT_FILE}"
"${PNPM[@]}" exec prettier --write "${OUT_FILE}"
echo "Generated ${OUT_FILE}"
