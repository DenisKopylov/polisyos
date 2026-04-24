#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SCHOLAR_ROOT = REPO_ROOT / "src" / "polisyos" / "scholar"
FORBIDDEN_MODULE = "polisyos.fabric.io.db"


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str


def _scan_file(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == FORBIDDEN_MODULE or module.startswith(f"{FORBIDDEN_MODULE}."):
                violations.append(
                    Violation(
                        path=path,
                        lineno=node.lineno,
                        message=f"forbidden import from {FORBIDDEN_MODULE}",
                    )
                )
            if module == "polisyos.fabric.io":
                names = {alias.name for alias in node.names}
                if "db" in names or "SimulationDB" in names:
                    violations.append(
                        Violation(
                            path=path,
                            lineno=node.lineno,
                            message="forbidden import from polisyos.fabric.io (db coupling)",
                        )
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported = alias.name
                if imported == FORBIDDEN_MODULE or imported.startswith(f"{FORBIDDEN_MODULE}."):
                    violations.append(
                        Violation(
                            path=path,
                            lineno=node.lineno,
                            message=f"forbidden import {imported}",
                        )
                    )
    return violations


def check() -> int:
    if not SCHOLAR_ROOT.exists():
        print(f"ERROR: scholar root not found: {SCHOLAR_ROOT}")
        return 2

    violations: list[Violation] = []
    for path in sorted(SCHOLAR_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        violations.extend(_scan_file(path))

    if not violations:
        print("Scholar import gate: OK")
        return 0

    print("Scholar import gate: FAILED")
    for row in violations:
        try:
            rel = row.path.relative_to(REPO_ROOT)
        except ValueError:
            rel = row.path
        print(f"{rel}:{row.lineno}: {row.message}")
    return 1


if __name__ == "__main__":
    sys.exit(check())
