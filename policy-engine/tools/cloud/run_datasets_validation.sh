#!/bin/bash
# =============================================================================
# Datasets validation runner for cloud server.
# Runs preflight_core first, inspects manifests, then launches prod_core_blocking
# only when the preflight contract passes.
# =============================================================================

set -uo pipefail

cd /opt/policyos/policy-engine || exit 1

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found"
  exit 1
fi
source .venv/bin/activate

if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo "Loaded .env"
else
  echo "ERROR: .env not found"
  exit 1
fi

export PYTHONPATH=src
export PYTHONUNBUFFERED=1

RUN_ID="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
PREFLIGHT_ROOT="/data/output/datasets_preflight_${RUN_ID}"
CORE_ROOT="/data/output/datasets_core_${RUN_ID}"

mkdir -p "$PREFLIGHT_ROOT" "$CORE_ROOT"

echo "=== DATASETS PREFLIGHT ==="
echo "Run ID:      $RUN_ID"
echo "Preflight:   $PREFLIGHT_ROOT"
echo "Core root:   $CORE_ROOT"
echo "Started:     $(date)"
echo

python3 -m polisyos.datasets.batch.cli run \
  --snapshot-root "$PREFLIGHT_ROOT" \
  --run-profile preflight_core \
  --stages harvest,normalize,merge_dedup,graph_load,graph_index,core_sources_ingest,embed,benchmark,qc \
  --resume-mode smart \
  --thermal \
  --no-fail-fast \
  2>&1 | tee "$PREFLIGHT_ROOT/pipeline.log"
PREFLIGHT_EXIT=${PIPESTATUS[0]}

if [ "$PREFLIGHT_EXIT" -ne 0 ]; then
  echo "Preflight command failed with exit code $PREFLIGHT_EXIT"
  exit "$PREFLIGHT_EXIT"
fi

export PREFLIGHT_ROOT
python3 - <<'PY'
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
PREFLIGHT_CONTRACT_EXIT=$?

if [ "$PREFLIGHT_CONTRACT_EXIT" -ne 0 ]; then
  echo "Stopping after preflight. Contract check failed with exit code $PREFLIGHT_CONTRACT_EXIT"
  exit "$PREFLIGHT_CONTRACT_EXIT"
fi

echo
echo "=== DATASETS PROD CORE BLOCKING ==="
echo "Core root:   $CORE_ROOT"
echo "Started:     $(date)"
echo

python3 -m polisyos.datasets.batch.cli run \
  --snapshot-root "$CORE_ROOT" \
  --run-profile prod_core_blocking \
  --resume-mode smart \
  --thermal \
  --no-fail-fast \
  2>&1 | tee "$CORE_ROOT/pipeline.log"
CORE_EXIT=${PIPESTATUS[0]}

echo
echo "=== DATASETS VALIDATION FINISHED ==="
echo "Preflight root: $PREFLIGHT_ROOT"
echo "Core root:      $CORE_ROOT"
echo "Ended:          $(date)"

exit "$CORE_EXIT"
