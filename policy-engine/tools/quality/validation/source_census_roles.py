"""Select Python source universes and assign their bounded analysis roles.

These roles control static source analysis only. They do not establish runtime
reachability, importability, ownership, or authority. Unknown source families
fail closed so a newly added root cannot silently leave an analysis denominator.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

PythonSourceRole = Literal[
    "production_capable",
    "research_only",
    "test_only",
    "benchmark_only",
    "example_only",
]

_SOURCE_FAMILY_ROLES: dict[str, PythonSourceRole] = {
    "apps": "production_capable",
    "architecture": "production_capable",
    "benchmarks": "benchmark_only",
    "dev-oracles": "production_capable",
    "docs": "production_capable",
    "examples": "example_only",
    "ops": "production_capable",
    "src": "production_capable",
    "tests": "test_only",
    "tools": "production_capable",
    "workers": "production_capable",
}
_SOURCE_SUFFIXES = (".py", ".pyi")


@dataclass(frozen=True, slots=True)
class PythonSourcePathCensus:
    """Hold independently selected Git and filesystem Python path sets.

    Attributes:
        product_root: Resolved product directory walked by the filesystem selector.
        git_root: Resolved worktree root used by the Git selectors.
        product_prefix: Exact product-root prefix relative to the Git root.
        indexed_paths: Product-relative indexed Python paths, including ignored paths.
        ignored_indexed_paths: Indexed Python paths matched by Git ignore rules.
        git_paths: Product-relative indexed and nonignored-untracked Python paths.
        filesystem_paths: Product-relative paths independently found on disk, retaining
            tracked ignored files and excluding ignored untracked files.
    """

    product_root: Path
    git_root: Path
    product_prefix: str
    indexed_paths: frozenset[str]
    ignored_indexed_paths: frozenset[str]
    git_paths: frozenset[str]
    filesystem_paths: frozenset[str]


def normalize_product_git_path(relative_path: str, product_prefix: str) -> str | None:
    """Remove one exact product-root component from a Git-root-relative path.

    Args:
        relative_path: Path emitted by Git, relative to the worktree root.
        product_prefix: Product-root path relative to the worktree, or empty at root.

    Returns:
        Product-relative path, empty string for the product root itself, or None
        when the path is outside the product root. The prefix is removed once only.
    """

    candidate = relative_path.rstrip("/")
    prefix = product_prefix.strip("/")
    if not prefix:
        return candidate
    if candidate == prefix:
        return ""
    rooted_prefix = f"{prefix}/"
    if not candidate.startswith(rooted_prefix):
        return None
    return candidate[len(rooted_prefix) :]


def classify_python_source_role(relative_path: str) -> PythonSourceRole:
    """Assign the repository's current static-analysis role to one product path.

    The active source families are apps, architecture, benchmarks, dev-oracles,
    docs, examples, ops, src, tests, tools, and workers. A root-level source file
    is production-capable. Only docs/research/** is research-only.

    Args:
        relative_path: POSIX path relative to the product root.

    Returns:
        The role used by source-analysis consumers.

    Raises:
        AssertionError: If the path is malformed or its top-level family is unknown.
    """

    parts = relative_path.split("/")
    if (
        not relative_path
        or relative_path.startswith("/")
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise AssertionError(f"unclassified Python/stub path: {relative_path}")
    if len(parts) == 1:
        return "production_capable"
    if parts[0] == "docs" and parts[1] == "research":
        return "research_only"
    role = _SOURCE_FAMILY_ROLES.get(parts[0])
    if role is None:
        raise AssertionError(f"unclassified Python/stub path: {relative_path}")
    return role


def _run_git(git_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(  # noqa: S603 - fixed local Git executable and argv; no shell.
        ["git", "-C", str(git_root), *args],  # noqa: S607 - Git is the sole executable.
        check=False,
        capture_output=True,
        input=input_bytes,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed ({completed.returncode}): "
            f"{completed.stderr.decode(errors='replace')}"
        )
    return completed.stdout


def _product_source_paths(paths: bytes, product_prefix: str) -> set[str]:
    selected: set[str] = set()
    for item in paths.split(b"\0"):
        if not item:
            continue
        product_path = normalize_product_git_path(item.decode(), product_prefix)
        if product_path is not None and product_path.endswith(_SOURCE_SUFFIXES):
            selected.add(product_path)
    return selected


def _walk_error(error: OSError) -> None:
    raise error


def python_source_path_census(product_root: Path) -> PythonSourcePathCensus:
    """Select the complete active product .py/.pyi source universe twice.

    Git selection includes indexed files even when ignore rules match them, plus
    nonignored untracked files; ignored untracked files are excluded. Filesystem
    selection walks independently, does not follow directory symlinks, prunes only
    Git-ignored untracked subtrees with no indexed Python descendants, and reconciles
    discovered paths through git check-ignore (which leaves indexed files visible).
    Walk, Git, decoding, and ignore-query errors fail closed. Non-Python files and
    paths outside the exact product-root component are outside this selector.

    Args:
        product_root: Product directory inside a Git worktree.

    Returns:
        The resolved roots and independently derived Git/filesystem path sets.

    Raises:
        AssertionError: If roots do not share one worktree, a subprocess fails, or
            filesystem enumeration cannot be completed.
    """

    resolved_product = product_root.resolve()
    git_root_result = subprocess.run(  # noqa: S603 - fixed read-only local Git query.
        ["git", "-C", str(resolved_product), "rev-parse", "--show-toplevel"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    git_root = Path(git_root_result.stdout.strip()).resolve()
    try:
        product_prefix = resolved_product.relative_to(git_root).as_posix()
    except ValueError as exc:
        raise AssertionError("product root is outside its Git worktree") from exc
    if product_prefix == ".":
        product_prefix = ""

    indexed_paths = _product_source_paths(
        _run_git(git_root, "ls-files", "--cached", "-z"), product_prefix
    )
    git_paths = _product_source_paths(
        _run_git(
            git_root,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ),
        product_prefix,
    )
    indexed_git_paths = [
        f"{product_prefix}/{path}" if product_prefix else path for path in sorted(indexed_paths)
    ]
    indexed_ignore_payload = b"\0".join(path.encode() for path in indexed_git_paths)
    if indexed_ignore_payload:
        indexed_ignore_payload += b"\0"
    ignored_indexed_result = subprocess.run(  # noqa: S603 - fixed read-only local Git query.
        ["git", "-C", str(git_root), "check-ignore", "--no-index", "--stdin", "-z"],  # noqa: S607
        check=False,
        capture_output=True,
        input=indexed_ignore_payload,
    )
    if ignored_indexed_result.returncode not in {0, 1}:
        raise AssertionError(ignored_indexed_result.stderr.decode(errors="replace"))
    ignored_indexed_paths = _product_source_paths(ignored_indexed_result.stdout, product_prefix)
    ignored_directories = {
        product_path
        for item in _run_git(
            git_root,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
        ).split(b"\0")
        if item
        if (product_path := normalize_product_git_path(item.decode(), product_prefix)) is not None
    }

    indexed_parent_directories: set[str] = set()
    for source_path in indexed_paths:
        for parent in PurePosixPath(source_path).parents:
            if parent.as_posix() != ".":
                indexed_parent_directories.add(parent.as_posix())

    discovered: set[str] = set()
    discovered_git_paths: list[str] = []

    def retain_child_directory(parent: Path, child_name: str) -> bool:
        if child_name == ".git":
            return False
        child = (parent / child_name).relative_to(resolved_product).as_posix()
        if child not in ignored_directories:
            return True
        # Keep ignored directories containing indexed source; skip ignored-only
        # subtrees without indexed Python descendants.
        return child in indexed_parent_directories

    for directory, child_dirs, file_names in os.walk(
        resolved_product, topdown=True, followlinks=False, onerror=_walk_error
    ):
        root = Path(directory)
        child_dirs[:] = [
            child_name for child_name in child_dirs if retain_child_directory(root, child_name)
        ]
        for file_name in file_names:
            if not file_name.endswith(_SOURCE_SUFFIXES):
                continue
            relative_path = (root / file_name).relative_to(resolved_product).as_posix()
            discovered.add(relative_path)
            discovered_git_paths.append(
                f"{product_prefix}/{relative_path}" if product_prefix else relative_path
            )

    ignore_payload = b"\0".join(path.encode() for path in discovered_git_paths)
    if ignore_payload:
        ignore_payload += b"\0"
    ignored_result = subprocess.run(  # noqa: S603 - fixed read-only local Git query.
        ["git", "-C", str(git_root), "check-ignore", "--stdin", "-z"],  # noqa: S607
        check=False,
        capture_output=True,
        input=ignore_payload,
    )
    if ignored_result.returncode not in {0, 1}:
        raise AssertionError(ignored_result.stderr.decode(errors="replace"))
    ignored_files = _product_source_paths(ignored_result.stdout, product_prefix)
    filesystem_paths = discovered - ignored_files

    return PythonSourcePathCensus(
        product_root=resolved_product,
        git_root=git_root,
        product_prefix=product_prefix,
        indexed_paths=frozenset(indexed_paths),
        ignored_indexed_paths=frozenset(ignored_indexed_paths),
        git_paths=frozenset(git_paths),
        filesystem_paths=frozenset(filesystem_paths),
    )
