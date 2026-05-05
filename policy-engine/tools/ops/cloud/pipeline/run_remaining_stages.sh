#!/usr/bin/env bash
# =============================================================================
# Resume a reviewed academic pipeline snapshot without hardcoded credentials.
# =============================================================================
set -euo pipefail

usage() {
  cat << 'EOF'
Usage:
  bash tools/ops/cloud/pipeline/run_remaining_stages.sh --snapshot-root PATH --dry-run
  bash tools/ops/cloud/pipeline/run_remaining_stages.sh --snapshot-root PATH --yes

Options:
  --snapshot-root PATH  Existing snapshot root to resume
  --dry-run             Preview the delegated run_pipeline invocation
  --yes                 Confirm execution
  --topics-dir PATH     Override topics directory passed to run_pipeline.sh
  -h, --help            Show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAPSHOT_ROOT="${POLISYOS_REMAINING_SNAPSHOT_ROOT:-}"
TOPICS_DIR=""
MODE_FLAG=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot-root)
      SNAPSHOT_ROOT="${2:?--snapshot-root requires a value}"
      shift 2
      ;;
    --topics-dir)
      TOPICS_DIR="${2:?--topics-dir requires a value}"
      shift 2
      ;;
    --dry-run | --yes)
      MODE_FLAG="$1"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${MODE_FLAG}" ]]; then
  echo "ERROR: pass --dry-run for preview or --yes to execute." >&2
  exit 2
fi

if [[ -z "${SNAPSHOT_ROOT}" ]]; then
  echo "ERROR: --snapshot-root is required for remaining-stages resume." >&2
  exit 2
fi

if [[ ! -d "${SNAPSHOT_ROOT}" ]]; then
  echo "ERROR: snapshot root does not exist: ${SNAPSHOT_ROOT}" >&2
  exit 1
fi

CMD=(
  bash "${SCRIPT_DIR}/run_pipeline.sh"
  "${MODE_FLAG}"
  --resume
  --snapshot-root "${SNAPSHOT_ROOT}"
)
if [[ -n "${TOPICS_DIR}" ]]; then
  CMD+=(--topics-dir "${TOPICS_DIR}")
fi
CMD+=("${EXTRA_ARGS[@]}")

printf 'Delegating remaining stages via: %q' "${CMD[0]}"
for ((i = 1; i < ${#CMD[@]}; i++)); do
  printf ' %q' "${CMD[$i]}"
done
printf '\n'

exec "${CMD[@]}"
