"""Independently reconcile A's complete named pytest and AST test denominators."""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

FILES = (
    "tests/unit/fabric/test_non_data_acquisition.py",
    "tests/unit/fabric/test_ceiling_relations.py",
)


def parameter_count(node: ast.expr, assignments: dict[str, ast.expr]) -> int:
    """Count literal sequences or sorted keys of an assigned literal dictionary."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return len(node.elts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sorted"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and not node.keywords
    ):
        dictionary = assignments[node.args[0].id]
        if isinstance(dictionary, ast.Dict):
            keys = [ast.literal_eval(key) for key in dictionary.keys]
            if len(keys) != len(set(keys)):
                raise ValueError("ambiguous_duplicate_parameter_key")
            return len(keys)
    raise ValueError(f"ambiguous_parameter_source:{ast.dump(node)}")


def ast_count(path: Path) -> int:
    """Expand every named test and every parametrization from the complete AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    count = 0
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        members = 1
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "parametrize"
            ):
                raise ValueError("ambiguous_test_decorator")
            members *= parameter_count(decorator.args[1], assignments)
        count += members
    return count


class CollectionCounter:
    """Observe pytest's independently executed collection, without running tests."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Count the actual item objects yielded by pytest collection."""
        self.counts.update(str(item.path.relative_to(Path.cwd())) for item in session.items)


def main() -> None:
    """Require complete collection equality; an unreadable member is ambiguous."""
    expected = {path: ast_count(Path(path)) for path in FILES}
    observed = CollectionCounter()
    result = pytest.main([*FILES, "--collect-only", "-o", "addopts=", "-qq"], plugins=[observed])
    sys.stdout.write(
        json.dumps(
            {
                "file_type_denominator": "two named Python test modules",
                "ast": expected,
                "pytest": dict(observed.counts),
                "ambiguous": 0,
            },
            sort_keys=True,
        ) + "\n"
    )
    if result != pytest.ExitCode.OK or dict(observed.counts) != expected:
        raise SystemExit("test_denominator_reconciliation_failed")


if __name__ == "__main__":
    main()
