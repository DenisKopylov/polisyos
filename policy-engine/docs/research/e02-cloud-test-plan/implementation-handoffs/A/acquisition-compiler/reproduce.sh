#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_ROOT:?Set SOURCE_ROOT to the pinned compiler worktree root}"
: "${HANDOFF_DIR:?Set HANDOFF_DIR to this receipt directory}"

expected_commit=5650b7aed7991606d62cd8510b377698a778ce39
expected_tree=b03120869a77b27d02aba456fb7dfc88d582f832
actual_commit=$(git -C "$SOURCE_ROOT" rev-parse HEAD)
actual_tree=$(git -C "$SOURCE_ROOT" rev-parse 'HEAD^{tree}')
if [[ "$actual_commit" != "$expected_commit" || "$actual_tree" != "$expected_tree" ]]; then
  printf 'wrong source pin: commit=%s tree=%s\n' "$actual_commit" "$actual_tree" >&2
  exit 2
fi
if [[ -n "$(git -C "$SOURCE_ROOT" status --porcelain)" ]]; then
  printf 'source worktree must be clean before the receipt run\n' >&2
  exit 2
fi

check_blob() {
  local path="$1"
  local expected="$2"
  local actual
  actual=$(git -C "$SOURCE_ROOT" rev-parse "HEAD:$path")
  if [[ "$actual" != "$expected" ]]; then
    printf 'wrong source blob for %s: %s\n' "$path" "$actual" >&2
    exit 2
  fi
}
check_blob policy-engine/src/polisyos/data_requirement/compiler.py d91823b593427fe275b4b0b6d4f14c499a12aa2d
check_blob policy-engine/src/polisyos/runtime/quality/generation_cycle.py 6ef5c7f8b760a9d76baba446001e3f7a62e29e33
check_blob policy-engine/src/polisyos/runtime/quality/acquisition_planner.py da680b58a7d4bde1ddba87944f82912c52e9faa9
check_blob policy-engine/tests/unit/data_requirement/test_compiler.py 9b97bf857a45cd1a18f7e6a380087d1bf130d03e
check_blob policy-engine/tests/unit/remediation/test_acq_01.py 0adde186e16225cf91103a98e5dda56b796eda40

mkdir -p "$HANDOFF_DIR"
cd "$SOURCE_ROOT/policy-engine"
PYTHONDONTWRITEBYTECODE=1 uv run --extra runtime --extra test python -m pytest -p no:cacheprovider \
  tests/unit/data_requirement/test_compiler.py::test_opaque_scenario_id_is_not_semantic_input \
  tests/unit/data_requirement/test_compiler.py::test_negated_topic_does_not_become_required_construct \
  tests/unit/data_requirement/test_compiler.py::test_generic_scope_does_not_infer_pilot_jurisdiction_or_start \
  tests/unit/data_requirement/test_compiler.py::test_explicit_constructs_are_not_replaced_by_semantic_proposals \
  tests/unit/data_requirement/test_compiler.py::test_semantic_topic_proposal_does_not_cross_capability_authority_boundary \
  tests/unit/remediation/test_acq_01.py::test_n7_explicit_specs_take_precedence_and_preserve_empty_primary \
  tests/unit/remediation/test_acq_01.py::test_n7_typed_any_of_gap_precedes_explicit_specs \
  tests/unit/remediation/test_acq_01.py::test_n7_fallback_handoff_preserves_statement_domain_scope_and_resolver \
  --junitxml="$HANDOFF_DIR/junit.xml" 2>&1 | tee "$HANDOFF_DIR/stdout.txt"
