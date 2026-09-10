"""Remove one actual C3 constraint property in memory, retaining source markers."""

# ruff: noqa: S101, T201 - deciding probe assertions and complete evidence output.

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import textwrap
from pathlib import Path


def main() -> int:
    import pytest

    from polisyos.runtime.quality.workspace import foundry_consumption as owner
    from polisyos.runtime.quality.workspace import loop

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("decision-consumption", "method-reconciliation", "emission-content")
    )
    mode = parser.parse_args().mode
    test = "tests/unit/runtime/quality/test_workspace_foundry_consumption.py::"
    if mode == "decision-consumption":
        namespace, holder, name = loop.__dict__, loop, "_phase2_constraint_blockers"
        selected = [
            test + "test_missing_constraint_basis_is_persisted_and_recomputed",
            test + "test_actual_phase2_loop_records_constraint_refusal_before_earlier_source_block",
        ]
    elif mode == "method-reconciliation":
        namespace, holder, name = (
            owner.__dict__,
            owner.ConstraintStoreIngestor,
            "_verified_method_outputs",
        )
        selected = [
            test + "test_missing_constraint_basis_is_persisted_and_recomputed",
            test
            + "test_real_method_report_is_reconciled_before_constraint_consumption_without_reexecution",
        ]
    else:
        namespace, holder, name = owner.__dict__, owner.ConstraintStoreIngestor, "_persist"
        selected = [
            test + "test_constraint_projection_bytes_bind_the_complete_parent_role_basis",
            test + "test_every_constraint_emission_requires_actual_full_readback",
        ]
    function = getattr(holder, name)
    path = Path(inspect.getsourcefile(function))
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    definition = tree.body[0]
    if mode == "emission-content":
        matches = [
            node
            for node in ast.walk(definition)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Constant)
                and child.value == "constraint_emission_readback_mismatch"
                for child in ast.walk(ast.Module(body=node.body, type_ignores=[]))
            )
        ]
        assert len(matches) == 1
        matches[0].test = ast.Constant(False)
    else:
        # The complete former function body remains as unreachable marker text;
        # the real call site now receives only the removed-property substitute.
        replacement = "[]" if mode == "decision-consumption" else "([], [], None)"
        definition.body = [
            ast.Return(value=ast.parse(replacement, mode="eval").body),
            *definition.body,
        ]
    ast.fix_missing_locations(tree)
    local = {}
    exec(compile(tree, str(path), "exec"), namespace, local)  # noqa: S102
    setattr(holder, name, local[name])
    print(
        json.dumps(
            {
                "property_removed": mode,
                "owner_path": str(path),
                "source_sha256": source_hash,
                "function": name,
                "selected_node_ids": selected,
                "markers_retained": True,
            }
        )
    )
    result = int(pytest.main(["-q", "-rA", "--show-capture=no", "--tb=short", *selected]))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source_hash
    print(json.dumps({"source_unchanged": True, "pytest_returncode": result}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
