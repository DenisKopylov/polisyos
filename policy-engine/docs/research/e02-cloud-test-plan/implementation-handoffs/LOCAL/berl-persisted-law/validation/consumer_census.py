"""Enumerate BERL validation consumers across all product Python files."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SOURCE_ROOT = Path("src/polisyos")
TARGETS = {
    "validate_explanation_bundle",
    "validate_persisted_explanation_bundle_payload",
}


def called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def main() -> None:
    files = sorted(SOURCE_ROOT.rglob("*.py"))
    call_sites: list[tuple[str, int, str, str]] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = called_name(node)
                if name in TARGETS:
                    call_sites.append((str(path), node.lineno, name, "call"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in TARGETS:
                    call_sites.append((str(path), node.lineno, node.name, "definition"))

    persisted = [
        row
        for row in call_sites
        if row[2] == "validate_persisted_explanation_bundle_payload" and row[3] == "call"
    ]
    _emit(f"Complete source denominator: {len(files)} Python files under {SOURCE_ROOT}")
    _emit(f"All target call/definition rows: {len(call_sites)}")
    _emit("Complete target rows:")
    for path, lineno, name, kind in sorted(call_sites):
        _emit(f"  {kind}: {path}:{lineno} {name}")
    _emit(f"Persisted-consumer call-site denominator: {len(persisted)}")
    for path, lineno, name, _ in sorted(persisted):
        _emit(f"  {path}:{lineno} {name}")


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


if __name__ == "__main__":
    main()
