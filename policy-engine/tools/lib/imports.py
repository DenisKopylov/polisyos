"""Shared import/bootstrap helpers for repository tools."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_SENTINELS = ("pyproject.toml", "tools", "src")


class RepositoryRootUnavailableError(ValueError):
    """Raised when no existing PolicyOS workspace root can be resolved."""


def _find_repo_root(start: Path) -> Path | None:
    """Return the nearest existing repository root at or above ``start``."""

    current = start.parent if start.is_file() else start
    for candidate in (current, *current.parents):
        if all((candidate / sentinel).exists() for sentinel in _REPO_SENTINELS):
            return candidate
    return None


def _explicit_workspace_root(root: str | Path, *, source: str) -> Path:
    """Validate that ``root`` names an existing workspace root, not an inferred path."""

    candidate = Path(root).expanduser().resolve()
    if not candidate.is_dir() or _find_repo_root(candidate) != candidate:
        raise RepositoryRootUnavailableError(
            f"{source} is not an existing PolicyOS workspace root: {candidate}"
        )
    return candidate


def repo_root_from(
    file_path: str | Path,
    *,
    allow_cwd_fallback: bool = False,
    workspace_root: str | Path | None = None,
) -> Path:
    """Resolve the workspace root from source ancestry or an explicitly enabled checkout.

    Source-file ancestry remains authoritative by default. ``workspace_root`` selects an
    explicit existing workspace, while ``allow_cwd_fallback`` permits an unanchored installed
    module to resolve the current directory only when it is inside an existing workspace.
    """

    if workspace_root is not None:
        return _explicit_workspace_root(workspace_root, source="workspace_root")

    path = Path(file_path).resolve()
    source_root = _find_repo_root(path)
    if source_root is not None:
        return source_root

    if allow_cwd_fallback:
        cwd_root = _find_repo_root(Path.cwd().resolve())
        if cwd_root is not None:
            return cwd_root

    raise RepositoryRootUnavailableError(
        f"Could not resolve a PolicyOS workspace root from {file_path!r}; "
        "enable CWD fallback from an existing checkout or provide an existing workspace_root."
    )


def ensure_repo_import_roots(
    file_path: str | Path,
    *,
    include_repo_root: bool = True,
    include_src_root: bool = True,
    workspace_root: str | Path | None = None,
) -> tuple[Path, Path]:
    """Add existing workspace import roots to ``sys.path`` exactly once.

    Callers that identify their source file inside a checkout stay anchored to that root. An
    installed module with no source-tree anchor may use the current directory only when it has
    the existing PolicyOS workspace layout; an explicit ``workspace_root`` takes precedence.
    """

    repo_root = repo_root_from(
        file_path,
        allow_cwd_fallback=True,
        workspace_root=workspace_root,
    )
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
