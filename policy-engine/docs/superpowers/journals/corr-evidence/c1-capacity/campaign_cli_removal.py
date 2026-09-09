"""Remove one CLI admission property in memory and run unchanged negative controls."""

from __future__ import annotations

import argparse
import ast
import inspect

import pytest

from polisyos.data_forge.domains.academic.batch import reextraction_cli as owner

TESTS = "tests/unit/data_forge/domains/academic/batch/test_reextraction_cli.py"


def main() -> int:
    """Mutate no disk source, keep declared plan markers, and retain a valid frame control."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("property", choices=["authorization", "source_frame"])
    args = parser.parse_args()
    original = owner._admit_plan if args.property == "authorization" else owner.run_plan
    tree = ast.parse(inspect.getsource(original))
    function = tree.body[0]
    if not isinstance(function, (ast.AsyncFunctionDef, ast.FunctionDef)):
        raise RuntimeError("cli_removal_owner_shape_changed")
    match = "full_pass_authorized" if args.property == "authorization" else "current != plan.frame"
    indices = [
        index
        for index, node in enumerate(function.body)
        if isinstance(node, ast.If) and match in ast.unparse(node.test)
    ]
    if args.property == "source_frame":
        # The intake comparator lives inside the open-source transaction.
        candidates = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.If) and ast.unparse(node.test) == match
        ]
    else:
        candidates = [function.body[index] for index in indices]
    if len(candidates) != 1:
        raise RuntimeError("cli_removal_predicate_identity_ambiguous")
    target = candidates[0]
    target.test = ast.Constant(value=False)
    ast.fix_missing_locations(tree)
    exec(compile(tree, inspect.getsourcefile(original) or "<cli-owner>", "exec"), vars(owner))  # noqa: S102 - bounded in-memory removal of the actual property; no source mutation.
    node = (
        "test_cli_refuses_unauthorized_before_credentials_source_or_outputs"
        if args.property == "authorization"
        else "test_frame_identity_mismatch_is_recomputed_before_credentials"
    )
    return int(
        pytest.main(
            [
                TESTS + "::" + node,
                TESTS + "::test_prepare_reconciles_complete_source_and_distinct_secondary[work_id]",
                "-q",
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
