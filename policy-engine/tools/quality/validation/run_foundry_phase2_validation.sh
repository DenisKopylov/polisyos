#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
REPORT_DIR="${1:-"$ROOT_DIR/benchmarks/_reports/foundry_phase2_$(date -u +%Y%m%d-%H%M%SZ)"}"
LATEST_DIR="$ROOT_DIR/benchmarks/_reports/foundry_phase2_latest"
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
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=("python3")
else
    PYTHON_CMD=("uv" "run" "python")
fi

mkdir -p "$REPORT_DIR" "$LATEST_DIR"
rm -f \
    "$REPORT_DIR"/*.log \
    "$REPORT_DIR"/*.json \
    "$REPORT_DIR"/*.tsv \
    "$REPORT_DIR"/metadata.txt \
    "$REPORT_DIR"/summary.md
cd "$ROOT_DIR"

MANIFEST_JSON="$ROOT_DIR/tools/quality/validation/foundry_phase2_manifest.json"
ACCEPTANCE_JUNIT="$REPORT_DIR/foundry_phase2_acceptance.xml"
JUDGE_JUNIT="$REPORT_DIR/foundry_phase2_judge.xml"
BENCHMARK_JSON="$REPORT_DIR/foundry_phase2_benchmarks.json"
EVIDENCE_JSON="$REPORT_DIR/foundry_phase2_evidence.json"
CLOSURE_JSON="$REPORT_DIR/foundry_phase2_closure.json"
SUITE_STATUS_FILE="$REPORT_DIR/suite_status.tsv"
BENCHMARK_STATUS_FILE="$REPORT_DIR/benchmark_status.tsv"
FAILURES=0

{
    echo "run_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "root_dir=$ROOT_DIR"
    echo "report_dir=$REPORT_DIR"
    echo "pytest_cmd=${PYTEST_CMD[*]}"
    echo "python_cmd=${PYTHON_CMD[*]}"
} > "$REPORT_DIR/metadata.txt"

: > "$SUITE_STATUS_FILE"
: > "$BENCHMARK_STATUS_FILE"

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

run_pytest_with_junit() {
    local suite_name="$1"
    local junit_path="$2"
    shift 2
    local log_path="$REPORT_DIR/${suite_name}.log"

    echo "Running ${suite_name}..."
    set +e
    {
        echo "suite=${suite_name}"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "command=${PYTEST_CMD[*]} -q --junitxml=$junit_path $*"
        "${PYTEST_CMD[@]}" -q --junitxml="$junit_path" "$@"
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
    local suite_id="$1"
    local script_path="$2"
    shift 2
    local json_path="$REPORT_DIR/${suite_id}.json"
    local log_path="$REPORT_DIR/${suite_id}.log"

    echo "Running benchmark ${suite_id}..."
    set +e
    {
        echo "suite=${suite_id}"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "command=${PYTHON_CMD[*]} $script_path $* --json $json_path --quiet"
        "${PYTHON_CMD[@]}" "$script_path" "$@" --json "$json_path" --quiet
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
    printf '%s\t%s\t%s\t%s\n' "$suite_id" "$suite_status" "$json_path" "$log_path" >> "$BENCHMARK_STATUS_FILE"
    printf '%s\t%s\t%s\n' "$suite_id" "$suite_status" "$log_path" >> "$SUITE_STATUS_FILE"
}

run_pytest_with_junit phase2_acceptance "$ACCEPTANCE_JUNIT" \
    tests/foundry/methods/catalog/econometrics/test_iv.py::test_high_dimensional_post_selection_iv_assigns_orthogonal_tier \
    tests/foundry/methods/catalog/econometrics/test_thresholds.py::test_state_dependent_threshold_runs_with_known_surface \
    tests/foundry/test_foundry_v2_domains.py::test_foundry_v2_nonstationary_garch_dispatch \
    tests/foundry/methods/catalog/causal/test_distributional_bounds.py::test_distributional_bounds_engine_routes_mtr_and_sd_inequality_families \
    tests/foundry/methods/catalog/distributional/test_mobility.py::TestTransitionMatrix::test_attrition_adjusted_ipcw_recovers_balanced_rows_and_persists_bounds \
    tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py::test_ordinal_poverty_config_persists_report_and_summary \
    tests/foundry/methods/catalog/network/test_peer_effect_decomposition.py::test_peer_effect_decomposition_identified_route \
    tests/foundry/methods/catalog/network/test_analysis.py::TestStrategicNetworkFormation::test_event_history_route_is_used_when_available \
    tests/foundry/methods/catalog/network/test_ergm.py::test_ergm_null_model_returns_diagnostics \
    tests/foundry/methods/catalog/network/test_sbm.py::test_sbm_stratification_bridges_into_network_causal_data \
    tests/foundry/methods/catalog/network/test_missingness.py::test_network_estimator_threads_missingness_assessment_into_result \
    tests/foundry/methods/catalog/network/test_embedding_fidelity.py::test_embedding_fidelity_certificate_green_when_separator_is_recoverable \
    tests/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_maup_certificate_with_candidate_partitions \
    tests/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_status_success \
    tests/foundry/methods/catalog/causal/test_interference.py::test_spatial_interference_hodge_diagnostics_attach_multiscale_profile

run_pytest_with_junit phase2_judges "$JUDGE_JUNIT" \
    tests/foundry/validation/test_phase2_judge_stack.py

run_suite phase2_closure_runtime_support \
    tests/foundry/validation/test_phase2_closure.py \
    tests/tools/test_scientist_phase2_gate.py \
    tests/scientist/search/test_phase_b_policy_runtime.py \
    -k "phase2_closure or phase2_closure_report or phase2_benchmark_scope"

run_suite phase2_runtime_apis \
    tests/runtime/http/test_mobility_api.py \
    tests/runtime/http/test_sae_spatial_route.py

run_benchmark phase2_econometrics_frontier benchmarks/econometrics/phase2_frontier.py
run_benchmark phase2_distributional_frontier benchmarks/distributional/phase2_frontier.py
run_benchmark phase2_mobility_frontier benchmarks/distributional/phase2_mobility_frontier.py
run_benchmark phase2_network_identification benchmarks/network/phase2_identification_frontier.py
run_benchmark phase2_spatial_identification benchmarks/spatial/phase2_identification_frontier.py
run_benchmark ergm_null_diffusion benchmarks/network/ergm_null_diffusion.py --mode smoke
run_benchmark sbm_stratified_interference benchmarks/interference/sbm_stratified_interference.py --mode smoke
run_benchmark survey_causal_frontier_sae benchmarks/survey/causal_frontier_sae_benchmark.py --mode smoke

"${PYTHON_CMD[@]}" - "$BENCHMARK_STATUS_FILE" "$BENCHMARK_JSON" <<'PY'
import json
import sys
from pathlib import Path

status_file = Path(sys.argv[1])
output_file = Path(sys.argv[2])
benchmarks: list[dict[str, object]] = []
for raw_line in status_file.read_text(encoding="utf-8").splitlines():
    if not raw_line.strip():
        continue
    suite_id, exit_code, json_path, _log_path = raw_line.split("\t")
    payload = {}
    report_path = Path(json_path)
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    status = "pass" if exit_code == "0" else "fail"
    payload_status = str(
        payload.get("status")
        or payload.get("overall_status")
        or payload.get("suite_status")
        or ""
    ).strip().lower()
    if payload_status and payload_status not in {"pass", "passed", "success", "green", "ok"}:
        status = "fail"
    entry = {"name": suite_id, "status": status}
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        entry["metrics"] = metrics
    aggregate_metrics = payload.get("aggregate_metrics")
    if isinstance(aggregate_metrics, dict):
        entry["aggregate_metrics"] = aggregate_metrics
    benchmarks.append(entry)

output_file.write_text(
    json.dumps({"benchmarks": benchmarks}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

set +e
{
    echo "suite=phase2_evidence_generation"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTHON_CMD[*]} tools/quality/validation/generate_foundry_phase2_evidence.py --manifest $MANIFEST_JSON --acceptance-junit-xml $ACCEPTANCE_JUNIT --judge-junit-xml $JUDGE_JUNIT --output $EVIDENCE_JSON"
    "${PYTHON_CMD[@]}" \
        tools/quality/validation/generate_foundry_phase2_evidence.py \
        --manifest "$MANIFEST_JSON" \
        --acceptance-junit-xml "$ACCEPTANCE_JUNIT" \
        --judge-junit-xml "$JUDGE_JUNIT" \
        --output "$EVIDENCE_JSON"
    status=$?
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $status -eq 0 ]]; then
        echo "status=passed"
    else
        echo "status=failed"
    fi
    exit "$status"
} 2>&1 | tee "$REPORT_DIR/foundry_phase2_evidence.log"
evidence_status="${PIPESTATUS[0]}"
set -e
if [[ "$evidence_status" -ne 0 ]]; then
    FAILURES=1
fi
printf '%s\t%s\t%s\n' "phase2_evidence_generation" "$evidence_status" "$REPORT_DIR/foundry_phase2_evidence.log" >> "$SUITE_STATUS_FILE"

set +e
{
    echo "suite=foundry_phase2_closure"
    echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "command=${PYTHON_CMD[*]} tools/quality/validation/validate_foundry_phase2_closure.py --repo-root $ROOT_DIR --manifest $MANIFEST_JSON --acceptance-junit-xml $ACCEPTANCE_JUNIT --benchmark-report $BENCHMARK_JSON --evidence-report $EVIDENCE_JSON --output $CLOSURE_JSON"
    "${PYTHON_CMD[@]}" \
        tools/quality/validation/validate_foundry_phase2_closure.py \
        --repo-root "$ROOT_DIR" \
        --manifest "$MANIFEST_JSON" \
        --acceptance-junit-xml "$ACCEPTANCE_JUNIT" \
        --benchmark-report "$BENCHMARK_JSON" \
        --evidence-report "$EVIDENCE_JSON" \
        --output "$CLOSURE_JSON"
    status=$?
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ $status -eq 0 ]]; then
        echo "status=passed"
    else
        echo "status=failed"
    fi
    exit "$status"
} 2>&1 | tee "$REPORT_DIR/foundry_phase2_closure.log"
validator_status="${PIPESTATUS[0]}"
set -e
if [[ "$validator_status" -ne 0 ]]; then
    FAILURES=1
fi
printf '%s\t%s\t%s\n' "foundry_phase2_closure" "$validator_status" "$REPORT_DIR/foundry_phase2_closure.log" >> "$SUITE_STATUS_FILE"

cp "$CLOSURE_JSON" "$LATEST_DIR/foundry_phase2_closure.json"

{
    echo "# Foundry Phase 2 Validation"
    echo
    echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Repository root: \`$ROOT_DIR\`"
    echo "- Pytest command: \`${PYTEST_CMD[*]}\`"
    echo "- Python command: \`${PYTHON_CMD[*]}\`"
    echo "- Manifest: \`$(basename "$MANIFEST_JSON")\`"
    echo "- Acceptance JUnit: \`$(basename "$ACCEPTANCE_JUNIT")\`"
    echo "- Judge JUnit: \`$(basename "$JUDGE_JUNIT")\`"
    echo "- Benchmark report: \`$(basename "$BENCHMARK_JSON")\`"
    echo "- Evidence report: \`$(basename "$EVIDENCE_JSON")\`"
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
