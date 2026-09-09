"""Reconcile the complete selected constraint test population and removal identities."""

# ruff: noqa: S101, T201 - complete deciding probe.

from __future__ import annotations

import ast
import itertools
import json
import re
from pathlib import Path

from _build.gy_gaps.c1_selector_test_reconciliation import outcomes


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    folder = root / "_build/gy-gaps/c3/constraints"
    test_path = "tests/unit/runtime/quality/test_workspace_foundry_consumption.py"
    tree = ast.parse((root / test_path).read_text())
    definitions = {node.name: node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    source = ast.parse((root / "src/polisyos/runtime/quality/workspace/foundry_consumption.py").read_text())
    allowed = next(ast.literal_eval(node.value.args[0]) for node in source.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_ALLOWED_CONSTRAINT_SOURCES"
                           for t in node.targets))
    types = ast.parse((root / "src/polisyos/pdc/_impl/layer2_design_search.py").read_text())
    statuses = next(ast.literal_eval(node.value.slice) for node in types.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "ConstraintRecordStatus"
                            for t in node.targets))

    def expand(selector):
        path, name = selector.split("::")
        assert path == test_path
        arrays = []
        for deco in definitions[name].decorator_list:
            if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr == "parametrize"):
                continue
            assert not deco.keywords
            expression = ast.unparse(deco.args[1])
            if expression == "sorted(constraint_owner._ALLOWED_CONSTRAINT_SOURCES)":
                values = sorted(allowed)
            elif expression == "get_args(ConstraintRecordStatus)":
                values = statuses
            else:
                values = ast.literal_eval(deco.args[1])
            arrays.append(values)
        return {selector} if not arrays else {
            selector + "[" + "-".join(map(str, row)) + "]"
            for row in itertools.product(*reversed(arrays))
        }

    expected = set().union(*(expand(test_path + "::" + name) for name in definitions))
    native = json.loads((folder / "owner-integrated-green.json").read_text())
    correction = json.loads((folder / "owner-corrected-controls.json").read_text())
    initial, corrected = outcomes(native), outcomes(correction)
    progress = sum(len(match.group(1)) for line in native["stdout"].splitlines()
                   if (match := re.match(r"^([.FExs]+)\s+\[\s*\d+%\]", line)))
    assert set(initial) == expected and len(expected) == progress
    corrected_expected = set().union(*(expand(arg) for arg in correction["command"]
                                      if arg.startswith(test_path + "::")))
    assert set(corrected) == corrected_expected
    failures = {key for key, value in initial.items() if value != "PASSED"}
    assert failures <= corrected.keys()
    final = initial | corrected
    assert all(value == "PASSED" for value in final.values())
    comparisons = {}
    for mode in ("decision-consumption", "method-reconciliation", "emission-content"):
        receipt = json.loads((folder / f"{mode}-removal.json").read_text())
        declarations = [json.loads(line) for line in receipt["stdout"].splitlines()
                        if line.startswith("{") and '"selected_node_ids"' in line]
        assert len(declarations) == 1
        declared = set().union(*(expand(item) for item in declarations[0]["selected_node_ids"]))
        measured = outcomes(receipt)
        assert set(measured) == declared and declared <= final.keys()
        assert set(measured.values()) == {"PASSED", "FAILED"}
        assert receipt["returncode"] == 1 and not receipt["timed_out"]
        comparisons[mode] = {
            "selected_expanded_denominator": len(declared),
            "positive_controls": sorted(key for key, status in measured.items() if status == "PASSED"),
            "pass_to_fail_identities": sorted(key for key, status in measured.items() if status == "FAILED"),
            "missing_identities": sorted(declared - measured.keys()),
            "unexpected_identities": sorted(measured.keys() - declared),
        }
    print(json.dumps({
        "python_file_denominator": [test_path], "complete_test_definition_count": len(definitions),
        "ast_expanded_identity_count": len(expected), "independent_pytest_progress_count": progress,
        "actual_outcome_identity_count": len(initial), "initial_failure_identities": sorted(failures),
        "correction_receipt": "owner-corrected-controls.json",
        "corrected_identity_count": len(corrected), "remaining_nonpassing": [],
        "comparison_basis": "complete original wave plus exact targeted corrected controls; no unrun identity promoted",
        "removals": comparisons,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
