#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

BANNED_IMPORT_ROOTS = {
    "duckdb",
    "kuzu",
    "pandas",
    "polars",
    "pyarrow",
    "random",
    "requests",
    "httpx",
    "sqlite3",
    "sqlalchemy",
    "subprocess",
    "os",
    "pathlib",
    "shutil",
    "glob",
    "tempfile",
}

BANNED_BUILTINS = {"print", "open"}


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str


class FoundryVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[Violation] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in BANNED_IMPORT_ROOTS:
                self.violations.append(
                    Violation(
                        path=self.path,
                        lineno=node.lineno,
                        message=f"banned import: {alias.name}",
                    )
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            return
        root = node.module.split(".")[0]
        if root in BANNED_IMPORT_ROOTS:
            self.violations.append(
                Violation(
                    path=self.path,
                    lineno=node.lineno,
                    message=f"banned import: {node.module}",
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in BANNED_BUILTINS:
            self.violations.append(
                Violation(
                    path=self.path,
                    lineno=node.lineno,
                    message=f"banned builtin call: {node.func.id}()",
                )
            )
        self.generic_visit(node)


def find_foundry_roots(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "src" / "foundry",
        repo_root / "src" / "polisyos" / "foundry",
    ]
    return [path for path in candidates if path.exists()]


def iter_py_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def format_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint foundry for banned imports and I/O.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    roots = find_foundry_roots(repo_root)
    if not roots:
        print("No foundry roots found.")
        return 2

    violations: list[Violation] = []
    for root in roots:
        for path in iter_py_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            visitor = FoundryVisitor(path)
            visitor.visit(tree)
            violations.extend(visitor.violations)

    if violations:
        print("Foundry ban list violations:")
        for violation in violations:
            print(f"- {format_path(repo_root, violation.path)}:{violation.lineno} {violation.message}")
        return 1

    print("Foundry ban list: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
