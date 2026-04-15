#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_DIR="${1:-"$ROOT_DIR/benchmarks/_reports/engineering_done_$(date -u +%Y%m%d-%H%M%SZ)"}"
PYTEST_BIN="${PYTEST_BIN:-}"

if [[ -z "$PYTEST_BIN" ]]; then
    if [[ -x "$ROOT_DIR/.venv/bin/pytest" ]]; then
        PYTEST_BIN="$ROOT_DIR/.venv/bin/pytest"
    else
        PYTEST_BIN="pytest"
    fi
fi

mkdir -p "$REPORT_DIR"
cd "$ROOT_DIR"

{
    echo "run_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "root_dir=$ROOT_DIR"
    echo "report_dir=$REPORT_DIR"
    echo "pytest_bin=$PYTEST_BIN"
} > "$REPORT_DIR/metadata.txt"

run_suite() {
    local suite_name="$1"
    shift
    local log_path="$REPORT_DIR/${suite_name}.log"

    echo "Running ${suite_name}..."
    {
        echo "suite=${suite_name}"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "command=$PYTEST_BIN $*"
        "$PYTEST_BIN" -q "$@"
        echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "status=passed"
    } 2>&1 | tee "$log_path"
}

run_suite phase_a \
    tests/scientist/search/test_judge_stack_imports.py \
    tests/scientist/search/test_judge_thresholds.py \
    tests/scientist/search/test_benchmark_registry.py \
    tests/ir/analytics/test_phase_a_contracts.py \
    tests/foundry/methods/catalog/causal/test_hedge_fallback.py \
    tests/scientist/search/test_policy_blueprint_runtime_guards.py \
    tests/foundry/methods/catalog/causal/test_causal_engine.py

run_suite phase_b_to_f \
    tests/ir/analytics/test_phase_b_contracts.py \
    tests/foundry/methods/catalog/causal/test_query_preservation.py \
    tests/foundry/benchmarks/test_compositional_causality_benchmark.py \
    tests/ir/analytics/test_phase_c_contracts.py \
    tests/scientist/backtesting/test_temporal.py \
    tests/foundry/methods/catalog/causal/test_temporal_estimand_compiler.py \
    tests/ir/analytics/test_phase_d_contracts.py \
    tests/scientist/backtesting/test_phase_d4_challenge_suites.py \
    tests/scientist/search/test_phase_d4_runtime_integration.py \
    tests/foundry/methods/catalog/causal/test_constraint_discovery.py \
    tests/scientist/discovery/test_utility_judge.py \
    tests/scientist/test_build_literature_prior_node.py \
    tests/ir/analytics/test_phase_f_contracts.py

{
    echo "# Causal Engineering Validation"
    echo
    echo "- Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Pytest binary: \`$PYTEST_BIN\`"
    echo "- Phase A log: \`phase_a.log\`"
    echo "- Phase B-F log: \`phase_b_to_f.log\`"
    echo "- Discovery coverage: \`test_constraint_discovery.py\` executed in the same environment as the main validation run."
} > "$REPORT_DIR/summary.md"
