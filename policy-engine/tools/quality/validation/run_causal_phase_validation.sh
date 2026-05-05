#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
REPORT_DIR="${1:-"$ROOT_DIR/benchmarks/_reports/engineering_done_$(date -u +%Y%m%d-%H%M%SZ)"}"
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

run_validator() {
  local log_path="$REPORT_DIR/closure_contracts_report.log"
  local output_path="$REPORT_DIR/closure_report.json"

  echo "Running closure_validator..."
  set +e
  {
    echo "suite=closure_validator"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTHON_CMD[*]} tools/quality/validation/validate_phase_closure.py --repo-root $ROOT_DIR --output $output_path"
    "${PYTHON_CMD[@]}" \
      tools/quality/validation/validate_phase_closure.py \
      --repo-root "$ROOT_DIR" \
      --output "$output_path"
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
  printf '%s\t%s\t%s\n' "closure_validator" "$suite_status" "$log_path" >> "$SUITE_STATUS_FILE"
}

run_suite closure_contracts \
  tests/unit/ir/analytics/test_phase1_closure_contracts.py \
  tests/unit/ir/analytics/test_phase_closure_contracts.py \
  tests/unit/ir/analytics/test_phase_a_contracts.py \
  tests/unit/ir/analytics/test_phase_b_contracts.py \
  tests/unit/ir/analytics/test_phase_c_contracts.py \
  tests/unit/ir/analytics/test_phase_d_contracts.py \
  tests/unit/ir/analytics/test_phase_f_contracts.py

run_suite distributional_proof \
  tests/unit/scientist/nodes/test_decision_packet_distributional_econometrics.py \
  tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py \
  tests/unit/foundry/methods/catalog/causal/test_density_ratio_distributional_ot.py

run_suite narrow_scope_governance \
  tests/unit/foundry/methods/catalog/causal/test_query_preservation.py \
  tests/unit/ir/analytics/test_proximal_bridge_plausibility.py \
  tests/unit/foundry/methods/catalog/causal/test_interference_identification.py \
  tests/unit/foundry/methods/catalog/causal/test_stochastic_policies.py

run_suite integration_e2e \
  tests/unit/scientist/nodes/builtins/causal/test_run_causal_readiness.py \
  tests/unit/scientist/causal/test_causal_evaluation_node.py \
  tests/unit/scientist/nodes/test_decision_packet_node_v3.py \
  tests/unit/scientist/nodes/test_decision_packet_distributional_econometrics.py \
  tests/unit/scientist/workflows/test_causal_full_workflow_guard.py \
  tests/unit/scientist/workflows/test_workflow_specs.py

run_suite dp_ci_and_thresholds \
  tests/unit/foundry/calibration/test_dp_ci.py \
  tests/unit/foundry/methods/catalog/causal/test_independence_tests.py \
  tests/unit/scientist/search/test_judge_thresholds.py

run_suite kernel_and_operator \
  tests/unit/foundry/methods/catalog/causal/test_kernel_runtime.py \
  tests/unit/ir/analytics/test_kernel_causal_contract.py \
  tests/unit/foundry/methods/catalog/causal/test_operator_valued_methods.py \
  tests/unit/foundry/methods/catalog/causal/test_operator_estimand_compiler.py

run_validator

{
  echo "# Causal Engineering Validation"
  echo
  echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Repository root: \`$ROOT_DIR\`"
  echo "- Pytest command: \`${PYTEST_CMD[*]}\`"
  echo "- Python command: \`${PYTHON_CMD[*]}\`"
  echo "- Closure report: \`closure_report.json\`"
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
