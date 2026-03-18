#!/usr/bin/env bash
# Mutation testing for Foundry methods using mutmut.
#
# Usage:
#   cd policy-engine
#   bash scripts/mutation_test.sh            # run on backends/ (default)
#   bash scripts/mutation_test.sh base       # run on base.py only
#   bash scripts/mutation_test.sh full       # run on entire methods/ package
#   bash scripts/mutation_test.sh results    # show results without re-running
#
# Prerequisites:
#   pip install "policy-engine[dev]"   # installs mutmut
#
# Target score: >= 70% kill rate for backends/ and base.py core paths.
# NOTE: This is slow (~minutes to hours). Do NOT run on every PR.
# Run weekly in a dedicated CI job or locally before merging critical changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

TARGET="${1:-backends}"

case "${TARGET}" in
  backends)
    PATHS="src/polisyos/foundry/methods/backends/"
    TESTS="tests/foundry/methods/backends/"
    ;;
  base)
    PATHS="src/polisyos/foundry/methods/base.py"
    TESTS="tests/foundry/methods/"
    ;;
  resolution)
    PATHS="src/polisyos/foundry/methods/resolution.py"
    TESTS="tests/foundry/methods/test_semver_resolution.py"
    ;;
  full)
    PATHS="src/polisyos/foundry/methods/"
    TESTS="tests/foundry/"
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
    echo "Usage: $0 [backends|base|resolution|full|results]"
    exit 1
    ;;
esac

echo "=== Running mutation tests ==="
echo "  Paths:  ${PATHS}"
echo "  Tests:  ${TESTS}"
echo ""

mutmut run \
  --paths-to-mutate "${PATHS}" \
  --tests-dir "${TESTS}" \
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
  if (( $(echo "${RATE} < 70" | bc -l) )); then
    echo "WARNING: Kill rate below 70% target."
    exit 1
  else
    echo "OK: Kill rate meets 70% target."
  fi
else
  echo "No mutants found."
fi
