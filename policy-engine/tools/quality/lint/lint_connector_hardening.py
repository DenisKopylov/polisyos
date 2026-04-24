#!/usr/bin/env python3
"""
Enforce P7 connector hardening invariants for production HTTP connectors.

Checks:
1. Production connector classes subclass HTTPConnectorBase.
2. Forbidden generic helper definitions are not present in source modules.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from tools._lib.imports import repo_root_from

DEFAULT_SOURCES_ROOT = (
    repo_root_from(__file__) / "src" / "polisyos" / "fabric" / "connectors" / "sources"
)

PRODUCTION_CONNECTORS: dict[str, str] = {
    "world_bank.py": "WorldBankConnector",
    "eurostat.py": "EurostatConnector",
    "ukons.py": "UKONSConnector",
}

FORBIDDEN_HELPERS = frozenset(
    {
        "_get_session",
        "_request_json",
        "_retry_after_seconds",
        "_build_version",
        "_parse_http_datetime",
        "_frame_completeness",
        "_safe_int",
        "_safe_float",
    }
)


@dataclass(frozen=True)
class Violation:
    file: Path
    lineno: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.lineno}: {self.message}"


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _scan_file(path: Path, class_name: str) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[Violation] = []

    connector_class: ast.ClassDef | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            connector_class = node
            break

    if connector_class is None:
        violations.append(
            Violation(
                file=path,
                lineno=1,
                message=f"missing connector class '{class_name}'",
            )
        )
        return violations

    base_names = {_base_name(base) for base in connector_class.bases}
    if "HTTPConnectorBase" not in base_names:
        violations.append(
            Violation(
                file=path,
                lineno=connector_class.lineno,
                message=f"{class_name} must subclass HTTPConnectorBase",
            )
        )

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in FORBIDDEN_HELPERS
        ):
            violations.append(
                Violation(
                    file=path,
                    lineno=node.lineno,
                    message=f"forbidden module helper definition '{node.name}'",
                )
            )

    for node in connector_class.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in FORBIDDEN_HELPERS
        ):
            violations.append(
                Violation(
                    file=path,
                    lineno=node.lineno,
                    message=f"forbidden connector method definition '{node.name}'",
                )
            )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce P7 connector hardening constraints.")
    parser.add_argument(
        "--sources-root",
        type=Path,
        default=DEFAULT_SOURCES_ROOT,
        help="Path to src/polisyos/fabric/connectors/sources",
    )
    args = parser.parse_args()

    root: Path = args.sources_root
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.", file=sys.stderr)
        return 2

    violations: list[Violation] = []
    for filename, class_name in PRODUCTION_CONNECTORS.items():
        path = root / filename
        if not path.exists():
            violations.append(
                Violation(
                    file=path,
                    lineno=1,
                    message="missing production connector module",
                )
            )
            continue
        violations.extend(_scan_file(path, class_name))

    if violations:
        print("lint_connector_hardening: violations found:")
        for violation in sorted(violations, key=lambda item: (str(item.file), item.lineno)):
            print(f"  - {violation}")
        return 1

    print("lint_connector_hardening: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
