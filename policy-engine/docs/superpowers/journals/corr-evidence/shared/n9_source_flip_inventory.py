"""Reconcile the complete existing source-flip tuple with its AST declarations."""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path


def main() -> None:
    path = Path("tools/quality/validation/check_layer3_gy_promotion_contract.py")
    tree = ast.parse(path.read_text())
    names = {"_SourceFlipReplacement", "_SourceFlipCase", "_source_flip_cases", "_pytest_probe"}
    module = ast.Module(body=[
        node for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ], type_ignores=[])
    namespace = {"dataclass": dataclass}
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102
    cases = namespace["_source_flip_cases"]()
    actual = {case.mutation_id for case in cases}
    declared = {
        keyword.value.value for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_SourceFlipCase"
        for keyword in node.keywords if keyword.arg == "mutation_id"
    }
    if actual != declared or len(cases) != len(actual):
        raise ValueError("source_flip_identity_sets_disagree")
    issues = []
    for case in cases:
        for replacement in case.replacements:
            occurrences = Path(replacement.relative_path).read_text().count(replacement.old)
            if occurrences != 1:
                issues.append({
                    "case": case.mutation_id, "kind": "source", "occurrences": occurrences,
                    "target": replacement.old,
                })
        for nodeid in case.probe_command:
            if "::" not in nodeid:
                continue
            filename, name = nodeid.split("::", 1)
            functions = {
                node.name for node in ast.walk(ast.parse(Path(filename).read_text()))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if name not in functions:
                issues.append({"case": case.mutation_id, "kind": "test", "nodeid": nodeid})
    sys.stdout.write(json.dumps({
        "denominator": "complete actual source-flip tuple versus AST constructor identity set",
        "count": len(cases), "identity_sets_equal": True, "issues": issues,
        "scope": "structural inventory only; actual property removals are separate executions",
    }, indent=2) + "\n")
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
