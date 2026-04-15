#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from

REPO_ROOT_DEFAULT = repo_root_from(__file__)


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str

    def render(self, repo_root: Path) -> str:
        try:
            rel = self.path.relative_to(repo_root)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.lineno}: {self.message}"


def _check_runtime_api_imports(repo_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    src_root = repo_root / "src"
    for py_file in sorted(src_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "polisyos.runtime.api":
                violations.append(
                    Violation(
                        path=py_file,
                        lineno=node.lineno,
                        message="forbidden import from polisyos.runtime.api in src/",
                    )
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "polisyos.runtime.api":
                        violations.append(
                            Violation(
                                path=py_file,
                                lineno=node.lineno,
                                message="forbidden import polisyos.runtime.api in src/",
                            )
                        )
    return violations


def _check_legacy_runtime_markers(repo_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    targets = [
        repo_root / "src/polisyos/runtime/http",
        repo_root / "src/polisyos/core/contracts/runtime.py",
    ]
    for target in targets:
        paths = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in ("legacy_runtime", "allow_unscoped_legacy_runs", "legacy_runs_root"):
                lineno = _find_line(text, marker)
                if lineno is None:
                    continue
                violations.append(
                    Violation(
                        path=path,
                        lineno=lineno,
                        message=f"forbidden runtime legacy marker: {marker}",
                    )
                )
    return violations


def _check_entrypoint_groups(repo_root: Path) -> list[Violation]:
    pyproject = repo_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    violations: list[Violation] = []
    for marker in (
        '[project.entry-points."polisyos.methods"]',
        '[project.entry-points."polisyos.connectors"]',
    ):
        lineno = _find_line(text, marker)
        if lineno is None:
            continue
        violations.append(
            Violation(
                path=pyproject,
                lineno=lineno,
                message=f"legacy entry-point group is forbidden: {marker}",
            )
        )
    return violations


def _check_foundry_facade_imports(repo_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    src_root = repo_root / "src"
    forbidden_prefixes = (
        "polisyos.foundry.domain.state",
        "polisyos.foundry.domain.mechanisms",
        "polisyos.foundry.base",
        "polisyos.foundry.types",
    )
    for py_file in sorted(src_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(
                    node.module == prefix or node.module.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(
                        Violation(
                            path=py_file,
                            lineno=node.lineno,
                            message=f"forbidden foundry compat import: from {node.module}",
                        )
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == prefix or alias.name.startswith(prefix + ".")
                        for prefix in forbidden_prefixes
                    ):
                        violations.append(
                            Violation(
                                path=py_file,
                                lineno=node.lineno,
                                message=f"forbidden foundry compat import: import {alias.name}",
                            )
                        )
    return violations


def _check_execute_fallback_markers(repo_root: Path) -> list[Violation]:
    path = repo_root / "src/polisyos/foundry/execute/api.py"
    text = path.read_text(encoding="utf-8")
    violations: list[Violation] = []
    forbidden_markers = (
        "state_source:data_snapshot_ref_compatibility_fallback",
        "compatibility:legacy_data_snapshot_to_state_snapshot",
        "request.data_snapshot_ref",
        "request.state_snapshot_ref",
    )
    for marker in forbidden_markers:
        lineno = _find_line(text, marker)
        if lineno is None:
            continue
        violations.append(
            Violation(
                path=path,
                lineno=lineno,
                message=f"forbidden execute fallback marker: {marker}",
            )
        )
    return violations


def _find_line(text: str, marker: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if marker in line:
            return index
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce P10 legacy cutover invariants.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repository root",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    violations: list[Violation] = []
    violations.extend(_check_runtime_api_imports(repo_root))
    violations.extend(_check_legacy_runtime_markers(repo_root))
    violations.extend(_check_entrypoint_groups(repo_root))
    violations.extend(_check_foundry_facade_imports(repo_root))
    violations.extend(_check_execute_fallback_markers(repo_root))

    if violations:
        print("lint_legacy_cutover: violations found:")
        for violation in violations:
            print(f"  - {violation.render(repo_root)}")
        return 1

    print("lint_legacy_cutover: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
