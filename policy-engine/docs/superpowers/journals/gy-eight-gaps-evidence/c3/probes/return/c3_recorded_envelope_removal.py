"""Remove one recorded-input property in memory while retaining its markers."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import textwrap


def main() -> int:
    import pytest

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("supplied-envelope", "full-source-equality"))
    args = parser.parse_args()
    test = "tests/unit/runtime/quality/test_data_forge_binding.py::"
    if args.mode == "supplied-envelope":
        from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner

        name = "_load_observational_data"
        original = inspect.getsource(getattr(owner, name))
        tree = ast.parse(textwrap.dedent(original))
        mutations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "envelope_supplied"
                for target in node.targets
            ):
                node.value = ast.parse(
                    'isinstance(payload, dict) and "contract_payload" in payload', mode="eval",
                ).body
                mutations.append(node.lineno)
        selected = [
            test + "test_causal_reader_materializes_actual_recorded_root",
            test + "test_causal_reader_cannot_treat_a_stripped_envelope_as_a_bare_dto",
        ]
    else:
        from polisyos.runtime.quality import data_forge_binding as owner

        name = "verify_recorded_panel_method_input"
        original = inspect.getsource(getattr(owner, name))
        tree = ast.parse(textwrap.dedent(original))
        mutations = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and ast.unparse(node.test) == "actual_payload != expected_payload"
            ):
                node.test = ast.Constant(False)
                mutations.append(node.lineno)
        selected = [
            test + "test_recorded_panel_method_input_roundtrips_measured_and_assumed_fields",
            test + "test_recorded_panel_fabricated_values_are_refused_with_all_markers",
        ]
    if len(mutations) != 1:
        raise RuntimeError(f"removal must identify exactly its single predicate: {mutations}")
    ast.fix_missing_locations(tree)
    exec(compile(tree, inspect.getsourcefile(owner) or name, "exec"), owner.__dict__)  # noqa: S102
    print(json.dumps({  # noqa: T201 - complete deciding removal receipt
        "property_removed": args.mode, "owner": owner.__name__, "function": name,
        "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "mutated_function_lines": mutations, "selected_node_ids": selected,
    }))
    return int(pytest.main(["-q", "-rA", "--tb=short", *selected]))


if __name__ == "__main__":
    raise SystemExit(main())
