"""Shared import/bootstrap helpers for repository tools."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_SENTINELS = ("pyproject.toml", "tools", "src")


def repo_root_from(file_path: str | Path) -> Path:
    """Infer the repository product root from a file living under the repo tree."""

    path = Path(file_path).resolve()
    current = path.parent if path.is_file() else path
    for candidate in (current, *current.parents):
        if all((candidate / sentinel).exists() for sentinel in _REPO_SENTINELS):
            return candidate
    raise ValueError(f"Could not infer repository root from {file_path!r}")


def ensure_repo_import_roots(
    file_path: str | Path,
    *,
    include_repo_root: bool = True,
    include_src_root: bool = True,
) -> tuple[Path, Path]:
    """Add the repo and/or ``src`` roots to ``sys.path`` exactly once."""

    repo_root = repo_root_from(file_path)
    src_root = repo_root / "src"
    candidates: list[Path] = []
    if include_repo_root:
        candidates.append(repo_root)
    if include_src_root:
        candidates.append(src_root)

    for candidate in candidates:
        rendered = str(candidate)
        if candidate.exists() and rendered not in sys.path:
            sys.path.insert(0, rendered)
    return repo_root, src_root


def is_type_checking_test(node: ast.AST) -> bool:
    """Return whether an AST node tests ``TYPE_CHECKING``."""

    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False
