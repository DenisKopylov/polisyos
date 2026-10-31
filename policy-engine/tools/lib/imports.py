"""Shared import/bootstrap helpers for repository tools."""

from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from pathlib import Path

_REPO_FILE_SENTINELS = ("pyproject.toml",)
_REPO_DIRECTORY_SENTINELS = ("tools", "src")


def repo_root_from(file_path: str | Path) -> Path:
    """Infer the repository product root from a file living under the repo tree."""

    path = Path(file_path).resolve()
    current = path.parent if path.is_file() else path
    for candidate in (current, *current.parents):
        if all((candidate / sentinel).is_file() for sentinel in _REPO_FILE_SENTINELS) and all(
            (candidate / sentinel).is_dir() for sentinel in _REPO_DIRECTORY_SENTINELS
        ):
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


def resolve_polisyos_source_module_file(
    repo_root: str | Path,
    module_name: str,
    *,
    is_file: Callable[[Path], bool] | None = None,
) -> tuple[Path | None, str | None]:
    """Resolve a polisyos module using Python's package-before-module precedence.

    The optional probe lets inventory callers account for filesystem reads without
    implementing their own module/package selection rules. Python's file finder
    prefers ``name/__init__.py`` when both it and ``name.py`` exist.
    """
    if not module_name.startswith("polisyos"):
        return None, "external_module"
    parts = module_name.split(".")
    if not parts or parts[0] != "polisyos" or any(not part.isidentifier() for part in parts):
        return None, "module_outside_source_root"

    source_root = Path(repo_root) / "src"
    stem = source_root.joinpath(*parts)
    package_initializer = stem / "__init__.py"
    module_file = stem.with_suffix(".py")
    probe = is_file or Path.is_file
    selected = (
        package_initializer
        if probe(package_initializer)
        else module_file
        if probe(module_file)
        else None
    )

    if selected is None:
        return module_file, "module_missing"
    try:
        resolved_root = source_root.resolve()
        if not selected.resolve().is_relative_to(resolved_root):
            return None, "module_outside_source_root"
    except OSError:
        return None, "module_unreadable"
    return selected, None
