"""Decisive C3 property removals in one disposable process, never source edits.

Run only after the staged/context mechanism and its selected test patch land.
Each mutant must make its formerly passing consumer assertion fail.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import textwrap
from dataclasses import replace
from unittest.mock import patch


def main() -> int:
    import pytest

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("readback", "context", "presence"))
    args = parser.parse_args()
    test = "tests/unit/runtime/quality/test_workspace_foundry_consumption.py::"
    if args.mode == "presence":
        from polisyos.runtime.quality.workspace import foundry_consumption

        original = foundry_consumption._verified_method_input_refs
        tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
        removed = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                expected = "bool(inputs.keys() & staged_slots.keys())"
                matching = [value for value in node.values if ast.unparse(value) == expected]
                if matching:
                    node.values = [value for value in node.values if value not in matching]
                    removed.extend(matching)
        if len(removed) != 1:
            raise RuntimeError("expected the one actual-lineage presence predicate")
        ast.fix_missing_locations(tree)
        exec(  # noqa: S102 - disposable in-memory property removal
            compile(tree, inspect.getsourcefile(original), "exec"), foundry_consumption.__dict__,
        )
        return int(pytest.main([
            "-q", "-rA", "--tb=short",
            test + "test_staged_intake_real_owner_is_consumed_without_weakening_measurement",
            test + "test_staged_result_lineage_cannot_hide_supplied_intake_by_removing_state_slots",
        ]))
    if args.mode == "readback":
        from polisyos.runtime.quality.workspace import foundry_consumption

        # Keep all artifact markers, manifest data and the actual method replay.
        # Only the source/readback predicate is removed.
        with patch.object(
            foundry_consumption, "verify_staged_foundry_input_state", return_value=None,
        ):
            return int(pytest.main([
                "-q", "-rA", "--tb=short",
                test + "test_staged_intake_owner_readback_refuses_decisive_mutation[source_output]",
                test + "test_staged_intake_owner_readback_refuses_decisive_mutation[source_status]",
            ]))

    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

    original = WorkspaceLoop._phase2_context

    def omit_context(self: WorkspaceLoop, *, workspace_id: str) -> tuple[object, object]:
        context, bundle_ref = original(self, workspace_id=workspace_id)
        return replace(
            context, eval_safety_execution_context=None, eval_safety_verifier=None,
        ), bundle_ref

    with patch.object(WorkspaceLoop, "_phase2_context", omit_context):
        return int(pytest.main([
            "-q", "-rA", "--tb=short",
            test + "test_workspace_context_reaches_actual_causal_safety_refusal",
        ]))


if __name__ == "__main__":
    raise SystemExit(main())
