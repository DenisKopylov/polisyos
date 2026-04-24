#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
REPORT_DIR="${1:-"$ROOT_DIR/benchmarks/_reports/foundry_phase0_$(date -u +%Y%m%d-%H%M%SZ)"}"
PYTEST_BIN="${PYTEST_BIN:-}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -n "$PYTEST_BIN" ]]; then
  PYTEST_CMD=("$PYTEST_BIN")
elif [[ -x "$ROOT_DIR/.venv/bin/pytest" ]]; then
  PYTEST_CMD=("$ROOT_DIR/.venv/bin/pytest")
else
  PYTEST_CMD=("uv" "run" "pytest")
fi

if [[ -n "$PYTHON_BIN" ]]; then
  PYTHON_CMD=("$PYTHON_BIN")
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_CMD=("$ROOT_DIR/.venv/bin/python")
elif command -v python3 > /dev/null 2>&1; then
  PYTHON_CMD=("python3")
else
  PYTHON_CMD=("uv" "run" "python")
fi

mkdir -p "$REPORT_DIR"
rm -f \
  "$REPORT_DIR"/*.log \
  "$REPORT_DIR"/*.json \
  "$REPORT_DIR"/metadata.txt \
  "$REPORT_DIR"/summary.md \
  "$REPORT_DIR"/suite_status.tsv
cd "$ROOT_DIR"

SUITE_STATUS_FILE="$REPORT_DIR/suite_status.tsv"
BENCHMARK_JSON="$REPORT_DIR/synthetic_world_phase0_smoke.json"
CLOSURE_JSON="$REPORT_DIR/foundry_phase0_closure.json"
: > "$SUITE_STATUS_FILE"
FAILURES=0

{
  echo "run_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root_dir=$ROOT_DIR"
  echo "report_dir=$REPORT_DIR"
  echo "pytest_cmd=${PYTEST_CMD[*]}"
  echo "python_cmd=${PYTHON_CMD[*]}"
} > "$REPORT_DIR/metadata.txt"

run_suite() {
  local suite_name="$1"
  shift
  local log_path="$REPORT_DIR/${suite_name}.log"

  echo "Running ${suite_name}..."
  set +e
  {
    echo "suite=${suite_name}"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTEST_CMD[*]} -q $*"
    "${PYTEST_CMD[@]}" -q "$@"
    local status=$?
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $status -eq 0 ]]; then
      echo "status=passed"
    else
      echo "status=failed"
    fi
    exit "$status"
  } 2>&1 | tee "$log_path"
  local suite_status="${PIPESTATUS[0]}"
  set -e
  if [[ "$suite_status" -ne 0 ]]; then
    FAILURES=1
  fi
  printf '%s\t%s\t%s\n' "$suite_name" "$suite_status" "$log_path" >> "$SUITE_STATUS_FILE"
}

run_benchmark() {
  local log_path="$REPORT_DIR/synthetic_world_phase0_smoke.log"

  echo "Running synthetic_world_phase0_smoke..."
  set +e
  {
    echo "suite=synthetic_world_phase0_smoke"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTHON_CMD[*]} benchmarks/synthetic_world/phase0_seed_benchmark.py --mode smoke --json $BENCHMARK_JSON --quiet"
    "${PYTHON_CMD[@]}" benchmarks/synthetic_world/phase0_seed_benchmark.py --mode smoke --json "$BENCHMARK_JSON" --quiet
    local status=$?
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $status -eq 0 ]]; then
      echo "status=passed"
    else
      echo "status=failed"
    fi
    exit "$status"
  } 2>&1 | tee "$log_path"
  local suite_status="${PIPESTATUS[0]}"
  set -e
  if [[ "$suite_status" -ne 0 ]]; then
    FAILURES=1
  fi
  printf '%s\t%s\t%s\n' "synthetic_world_phase0_smoke" "$suite_status" "$log_path" >> "$SUITE_STATUS_FILE"
}

run_validator() {
  local log_path="$REPORT_DIR/foundry_phase0_closure.log"

  echo "Running foundry_phase0_closure..."
  set +e
  {
    echo "suite=foundry_phase0_closure"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTHON_CMD[*]} tools/quality/validation/validate_foundry_phase0_closure.py --repo-root $ROOT_DIR --benchmark-report $BENCHMARK_JSON --output $CLOSURE_JSON"
    "${PYTHON_CMD[@]}" \
      tools/quality/validation/validate_foundry_phase0_closure.py \
      --repo-root "$ROOT_DIR" \
      --benchmark-report "$BENCHMARK_JSON" \
      --output "$CLOSURE_JSON"
    local status=$?
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $status -eq 0 ]]; then
      echo "status=passed"
    else
      echo "status=failed"
    fi
    exit "$status"
  } 2>&1 | tee "$log_path"
  local suite_status="${PIPESTATUS[0]}"
  set -e
  if [[ "$suite_status" -ne 0 ]]; then
    FAILURES=1
  fi
  printf '%s\t%s\t%s\n' "foundry_phase0_closure" "$suite_status" "$log_path" >> "$SUITE_STATUS_FILE"
}

run_suite truthfulness_catalog \
  tests/foundry/test_catalog_snapshot.py \
  -k "truthfulness or hmc_and_nuts"

run_suite truthfulness_advisor \
  tests/foundry/methods/test_selection_advisor.py \
  -k truthfulness

run_suite statistical_budgets \
  tests/foundry/methods/backends/test_backends.py \
  -k "statistical or degrades_when_runtime_drift_exceeds_cpu_budget"

run_suite equivalence_dispatch \
  tests/foundry/methods/test_dispatch_runtime_selection.py \
  -k equivalence

run_suite forecasting_uncertainty \
  tests/foundry/methods/catalog/forecasting/test_uncertainty_bundle.py

run_suite validated_dispatch \
  tests/foundry/methods/backends/test_validated_dispatch.py

run_suite synthetic_world_registry \
  tests/synthetic_world/test_seed_worlds.py

run_benchmark
run_validator

{
  echo "# Foundry Phase 0 Validation"
  echo
  echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Repository root: \`$ROOT_DIR\`"
  echo "- Pytest command: \`${PYTEST_CMD[*]}\`"
  echo "- Python command: \`${PYTHON_CMD[*]}\`"
  echo "- Benchmark report: \`$(basename "$BENCHMARK_JSON")\`"
  echo "- Closure report: \`$(basename "$CLOSURE_JSON")\`"
  echo
  echo "## Suite Status"
  while IFS=$'\t' read -r suite_name suite_status log_path; do
    if [[ -z "${suite_name:-}" ]]; then
      continue
    fi
    if [[ "$suite_status" -eq 0 ]]; then
      echo "- ${suite_name}: passed (\`$(basename "$log_path")\`)"
    else
      echo "- ${suite_name}: failed (\`$(basename "$log_path")\`)"
    fi
  done < "$SUITE_STATUS_FILE"
} > "$REPORT_DIR/summary.md"

exit "$FAILURES"
