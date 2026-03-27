#!/usr/bin/env bash
# Mutation testing for Scientist subsystem using mutmut.
#
# Usage:
#   cd policy-engine
#   bash scripts/mutation_test_scientist.sh governance    # governance passes
#   bash scripts/mutation_test_scientist.sh condition      # condition DSL
#   bash scripts/mutation_test_scientist.sh budget         # budget arithmetic
#   bash scripts/mutation_test_scientist.sh retry          # retry logic
#   bash scripts/mutation_test_scientist.sh checkpoint     # checkpoint fingerprint
#   bash scripts/mutation_test_scientist.sh idempotency    # idempotency keys
#   bash scripts/mutation_test_scientist.sh convergence    # convergence logic
#   bash scripts/mutation_test_scientist.sh api            # scientist API
#   bash scripts/mutation_test_scientist.sh all            # run all targets
#   bash scripts/mutation_test_scientist.sh results        # show results
#
# Prerequisites:
#   pip install "policy-engine[dev]"   # installs mutmut
#
# Target score: >= 80% kill rate per target.
# NOTE: This is slow (~minutes to hours). Run locally before merging critical changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

TARGET="${1:-governance}"

case "${TARGET}" in
  governance)
    PATHS="src/polisyos/scientist/governance/passes/"
    TESTS="tests/scientist/governance/"
    ;;
  condition)
    PATHS="src/polisyos/scientist/engine/condition.py"
    TESTS="tests/scientist/engine/test_condition.py tests/scientist/engine/test_condition_compound.py tests/scientist/engine/test_property_condition.py"
    ;;
  budget)
    PATHS="src/polisyos/scientist/engine/budget.py"
    TESTS="tests/scientist/engine/test_budget.py tests/scientist/engine/test_budget_middleware.py tests/scientist/engine/test_property_budget.py"
    ;;
  retry)
    PATHS="src/polisyos/scientist/engine/retry.py"
    TESTS="tests/scientist/engine/test_retry.py"
    ;;
  checkpoint)
    PATHS="src/polisyos/scientist/engine/checkpoint.py"
    TESTS="tests/scientist/engine/test_checkpoint.py tests/scientist/engine/test_property_checkpoint.py tests/scientist/engine/test_checkpoint_gc.py"
    ;;
  idempotency)
    PATHS="src/polisyos/scientist/engine/idempotency.py"
    TESTS="tests/scientist/engine/test_property_idempotency.py"
    ;;
  convergence)
    PATHS="src/polisyos/scientist/engine/convergence.py"
    TESTS="tests/scientist/engine/test_convergence.py tests/scientist/engine/test_convergence_semantic.py"
    ;;
  api)
    PATHS="src/polisyos/scientist/api.py"
    TESTS="tests/scientist/test_api.py"
    ;;
  all)
    echo "=== Running all mutation targets ==="
    for t in governance condition budget retry checkpoint idempotency convergence api; do
      echo ""
      echo "--- Target: ${t} ---"
      bash "${BASH_SOURCE[0]}" "${t}" || echo "WARN: ${t} did not meet threshold"
    done
    exit 0
    ;;
  results)
    echo "=== Mutation test results ==="
    mutmut results
    echo ""
    echo "=== Survivors (un-killed mutants) ==="
    mutmut results --status survived 2>/dev/null || echo "(none — all mutants killed)"
    exit 0
    ;;
  *)
    echo "Unknown target: ${TARGET}"
    echo "Usage: $0 [governance|condition|budget|retry|checkpoint|idempotency|convergence|api|all|results]"
    exit 1
    ;;
esac

echo "=== Running scientist mutation tests ==="
echo "  Target: ${TARGET}"
echo "  Paths:  ${PATHS}"
echo "  Tests:  ${TESTS}"
echo ""

# Determine the first test dir/file for mutmut --tests-dir
FIRST_TEST_DIR=$(echo "${TESTS}" | awk '{print $1}')

mutmut run \
  --paths-to-mutate "${PATHS}" \
  --tests-dir "${FIRST_TEST_DIR}" \
  --runner "python -m pytest ${TESTS} -x -q --no-header --tb=no" \
  --simple-output

echo ""
echo "=== Results ==="
mutmut results

echo ""
echo "=== Kill rate ==="
TOTAL=$(mutmut results 2>/dev/null | grep -E "^[0-9]+ mutants" | grep -oE "^[0-9]+" || echo 0)
KILLED=$(mutmut results --status killed 2>/dev/null | wc -l | tr -d ' ' || echo 0)
if [ "${TOTAL}" -gt 0 ]; then
  RATE=$(echo "scale=1; ${KILLED} * 100 / ${TOTAL}" | bc)
  echo "Kill rate: ${KILLED}/${TOTAL} = ${RATE}%"
  if (( $(echo "${RATE} < 80" | bc -l) )); then
    echo "WARNING: Kill rate below 80% target."
    exit 1
  else
    echo "OK: Kill rate meets 80% target."
  fi
else
  echo "No mutants found."
fi
