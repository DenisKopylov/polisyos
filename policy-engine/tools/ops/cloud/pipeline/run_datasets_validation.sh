#!/usr/bin/env bash
# =============================================================================
# Datasets validation runner for cloud server.
# Runs preflight_core first, inspects manifests, then launches prod_core_blocking
# only when the preflight contract passes.
# =============================================================================

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/cloud/run_datasets_validation.sh [--run-id RUN_ID] [--dry-run]

Options:
  --run-id RUN_ID  Override the run identifier used for preflight/core roots
  --dry-run        Preview directories and commands without executing them
  -h, --help       Show this help
EOF
}

generate_run_id() {
  python3 - <<'PY'
from datetime import datetime, timezone
import secrets

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"{stamp}-{secrets.token_hex(4)}")
PY
}

REPO_ROOT="${POLISYOS_REPO_ROOT:-/opt/polisyos/policy-engine}"
DATA_ROOT="${POLISYOS_DATA_ROOT:-/data}"
DRY_RUN=0
RUN_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id)
      RUN_ID="${2:?--run-id requires a value}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(generate_run_id)"
fi

cd "$REPO_ROOT"

if [[ ! -d .venv ]]; then
  echo "ERROR: .venv not found in $REPO_ROOT" >&2
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  echo "Loaded .env"
else
  echo "ERROR: .env not found in $REPO_ROOT" >&2
  exit 1
fi

export PYTHONPATH=src
export PYTHONUNBUFFERED=1

PREFLIGHT_ROOT="${DATA_ROOT}/output/datasets_preflight_${RUN_ID}"
CORE_ROOT="${DATA_ROOT}/output/datasets_core_${RUN_ID}"

PREFLIGHT_CMD=(
  python3 -m polisyos.datasets.batch.cli run
  --snapshot-root "$PREFLIGHT_ROOT"
  --run-profile preflight_core
  --stages harvest,normalize,merge_dedup,graph_load,graph_index,core_sources_ingest,embed,benchmark,qc
  --resume-mode smart
  --thermal
  --no-fail-fast
)

CORE_CMD=(
  python3 -m polisyos.datasets.batch.cli run
  --snapshot-root "$CORE_ROOT"
  --run-profile prod_core_blocking
  --resume-mode smart
  --thermal
  --no-fail-fast
)

echo "=== DATASETS VALIDATION PREVIEW ==="
echo "Run ID:      $RUN_ID"
echo "Preflight:   $PREFLIGHT_ROOT"
echo "Core root:   $CORE_ROOT"
printf 'Preflight:   %q' "${PREFLIGHT_CMD[0]}"
for ((i = 1; i < ${#PREFLIGHT_CMD[@]}; i++)); do
  printf ' %q' "${PREFLIGHT_CMD[$i]}"
done
printf '\n'
printf 'Core:        %q' "${CORE_CMD[0]}"
for ((i = 1; i < ${#CORE_CMD[@]}; i++)); do
  printf ' %q' "${CORE_CMD[$i]}"
done
printf '\n'

if [[ "$DRY_RUN" -eq 1 ]]; then
  exit 0
fi

if [[ -e "$PREFLIGHT_ROOT" || -e "$CORE_ROOT" ]]; then
  echo "ERROR: refusing to reuse existing output roots without an explicit resume workflow." >&2
  echo "  Preflight: $PREFLIGHT_ROOT" >&2
  echo "  Core:      $CORE_ROOT" >&2
  exit 1
fi

mkdir -p "$PREFLIGHT_ROOT" "$CORE_ROOT"

echo ""
echo "=== DATASETS PREFLIGHT ==="
echo "Run ID:      $RUN_ID"
echo "Preflight:   $PREFLIGHT_ROOT"
echo "Core root:   $CORE_ROOT"
echo "Started:     $(date)"
echo

if "${PREFLIGHT_CMD[@]}" 2>&1 | tee "$PREFLIGHT_ROOT/pipeline.log"; then
  :
else
  preflight_exit=$?
  echo "Preflight command failed with exit code $preflight_exit" >&2
  exit "$preflight_exit"
fi

export PREFLIGHT_ROOT
if python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["PREFLIGHT_ROOT"]) / "datasets"
qc_path = root / "qc_report.json"
benchmark_path = root / "benchmark_report.json"

if not qc_path.exists() or not benchmark_path.exists():
    print("Preflight missing qc_report.json or benchmark_report.json")
    sys.exit(1)

qc = json.loads(qc_path.read_text(encoding="utf-8"))
benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))

if not bool(qc.get("passed")):
    print("Preflight QC failed")
    sys.exit(2)

metrics = benchmark.get("metrics") if isinstance(benchmark.get("metrics"), dict) else {}
preflight_cases = benchmark.get("source_preflight", {}).get("sources", [])
if float(metrics.get("benchmark_source_preflight_ready_pct", 0.0) or 0.0) < 90.0:
    print("Preflight source readiness below threshold")
    sys.exit(3)

bad_sources = [
    case.get("source", "")
    for case in preflight_cases
    if isinstance(case, dict)
    and (
        int(case.get("failed_shards", 0) or 0) > 0
        or bool(case.get("auth_or_env_failure"))
        or not bool(case.get("ready"))
    )
]
if bad_sources:
    print("Preflight blocking source failures: " + ", ".join(sorted(set(str(item) for item in bad_sources if item))))
    sys.exit(4)

print("Preflight contract passed")
PY
then
  :
else
  contract_exit=$?
  echo "Stopping after preflight. Contract check failed with exit code $contract_exit" >&2
  exit "$contract_exit"
fi

echo
echo "=== DATASETS PROD CORE BLOCKING ==="
echo "Core root:   $CORE_ROOT"
echo "Started:     $(date)"
echo

if "${CORE_CMD[@]}" 2>&1 | tee "$CORE_ROOT/pipeline.log"; then
  echo
  echo "=== DATASETS VALIDATION FINISHED ==="
  echo "Preflight root: $PREFLIGHT_ROOT"
  echo "Core root:      $CORE_ROOT"
  echo "Ended:          $(date)"
else
  core_exit=$?
  echo
  echo "=== DATASETS VALIDATION FAILED ===" >&2
  echo "Preflight root: $PREFLIGHT_ROOT" >&2
  echo "Core root:      $CORE_ROOT" >&2
  echo "Ended:          $(date)" >&2
  exit "$core_exit"
fi
