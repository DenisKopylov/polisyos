"""Helpers for package mirror-ratchet contract tests."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@cache
def _source_modules(package: str) -> tuple[Path, ...]:
    source_root = REPO_ROOT / "src" / "polisyos" / package
    assert source_root.exists(), f"missing source package: {source_root}"
    return tuple(
        sorted(
            path
            for path in source_root.rglob("*.py")
            if path.name != "__init__.py" and "__pycache__" not in path.parts
        )
    )


@cache
def _module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def assert_source_stem_has_static_contract(package: str, stem: str) -> None:
    """Assert source modules sharing a stem are real contract-bearing modules."""
    matching_paths = tuple(path for path in _source_modules(package) if path.stem == stem)
    assert matching_paths, f"no source modules named {stem!r} found in {package!r}"

    for path in matching_paths:
        tree = _module_ast(path)
        executable_nodes = tuple(
            node
            for node in tree.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        )
        assert executable_nodes, f"{path} is empty or docstring-only"
        assert any(_is_contract_node(node) for node in executable_nodes), (
            f"{path} has no definition, assignment, or import-surface contract"
        )


def _is_contract_node(node: ast.stmt) -> bool:
    return isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Assign,
            ast.AnnAssign,
            ast.Import,
            ast.ImportFrom,
        ),
    )
