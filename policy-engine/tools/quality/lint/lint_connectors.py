#!/usr/bin/env python3
"""
Law A & Law B enforcement for the connectors subtree.

Scans every .py file under ``src/polisyos/fabric/connectors/`` and
ensures that no runtime import targets:
    - ``polisyos.scientist.*``   (Law A violation)
    - ``polisyos.foundry.*``     (Law B violation)

Imports inside ``if TYPE_CHECKING:`` blocks are reported as warnings
(non-blocking) to allow forward-reference type annotations.

Exit codes:
    0  - all clean
    1  - one or more ERRORS found (CI should fail)
    2  - usage error (bad arguments, missing path)
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from tools._lib.imports import repo_root_from, is_type_checking_test


FORBIDDEN_PREFIXES: dict[str, str] = {
    "polisyos.scientist": "Law A (Import Gate)",
    "polisyos.foundry": "Law B (Foundry Purity)",
    "scientist": "Law A (Import Gate)",
    "foundry": "Law B (Foundry Purity)",
}

DEFAULT_CONNECTORS_ROOT = (
    repo_root_from(__file__) / "src" / "polisyos" / "fabric" / "connectors"
)


@dataclass(frozen=True)
class Violation:
    file: Path
    lineno: int
    col_offset: int
    imported_module: str
    violated_law: str
    in_type_checking: bool

    @property
    def severity(self) -> str:
        return "WARNING" if self.in_type_checking else "ERROR"

    def __str__(self) -> str:
        return (
            f"[{self.severity}] {self.file}:{self.lineno}:{self.col_offset} "
            f"- imports '{self.imported_module}' ({self.violated_law})"
        )


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[Violation] = []
        self._type_checking_depth = 0

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        if is_type_checking_test(node.test):
            self._type_checking_depth += 1
            for child in node.body:
                self.visit(child)
            self._type_checking_depth -= 1
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._check(alias.name, node.lineno, node.col_offset)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            self._check(node.module, node.lineno, node.col_offset)
        else:
            for alias in node.names:
                self._check(alias.name, node.lineno, node.col_offset)

    def _check(self, module: str, lineno: int, col_offset: int) -> None:
        for prefix, law in FORBIDDEN_PREFIXES.items():
            if module == prefix or module.startswith(f"{prefix}."):
                self.violations.append(
                    Violation(
                        file=self.file_path,
                        lineno=lineno,
                        col_offset=col_offset,
                        imported_module=module,
                        violated_law=law,
                        in_type_checking=self._type_checking_depth > 0,
                    )
                )
                break


def scan(root: Path) -> list[Violation]:
    all_violations: list[Violation] = []

    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            print(f"[SYNTAX ERROR] {py_file}: {exc}", file=sys.stderr)
            continue

        visitor = _ImportVisitor(py_file)
        visitor.visit(tree)
        all_violations.extend(visitor.violations)

    all_violations.sort(key=lambda v: (v.file, v.lineno, v.col_offset))
    return all_violations


def _print_report(violations: list[Violation], strict: bool) -> None:
    if not violations:
        print("lint_connectors: all clean - no Law A/B violations found.")
        return

    errors = [v for v in violations if not v.in_type_checking]
    warnings = [v for v in violations if v.in_type_checking]

    print(f"\n{'=' * 70}")
    print("  lint_connectors - Architectural Law Enforcement Report")
    print(f"{'=' * 70}\n")

    if errors:
        print(f"ERRORS ({len(errors)}) - these MUST be fixed:\n")
        for v in errors:
            print(f"    {v}")
        print()

    if warnings:
        label = (
            "WARNINGS (treated as ERRORS in --strict mode)"
            if strict
            else "WARNINGS (non-blocking)"
        )
        print(f"{label} ({len(warnings)}):\n")
        for v in warnings:
            print(f"    {v}")
        print()

    print("-" * 70)
    print("Laws reference:")
    for prefix, law in FORBIDDEN_PREFIXES.items():
        if prefix.startswith("polisyos."):
            print(f"    {law}: connectors/ must not import {prefix}.*")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce Law A (Import Gate) and Law B (Foundry Purity) on connectors.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        default=DEFAULT_CONNECTORS_ROOT,
        help="Root directory to scan (default: src/polisyos/fabric/connectors).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat TYPE_CHECKING imports as errors (not just warnings).",
    )
    args = parser.parse_args()

    if not args.src_root.is_dir():
        print(f"Error: '{args.src_root}' is not a directory.", file=sys.stderr)
        return 2

    violations = scan(args.src_root)
    _print_report(violations, strict=args.strict)

    errors = [v for v in violations if not v.in_type_checking]
    if args.strict:
        errors = violations

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
