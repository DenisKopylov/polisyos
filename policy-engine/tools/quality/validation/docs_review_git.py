"""Git-selected review windows for the documentation review command."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class ReviewError(ValueError):
    """Signal an input or evidence condition that prevents a review verdict."""


@dataclass(frozen=True)
class GitWindow:
    """Resolved change window and its actual Git-selected paths."""

    base_commit: str | None
    head_commit: str | None
    comparison_base: str | None
    checkout_commit: str | None
    workspace_matches_head: bool | None
    workspace_mismatch_reason: str | None
    worktree_status: bytes | None
    paths: tuple[str, ...]
    selection: str
    raw_paths: tuple[bytes, ...] = ()


_GitBytes = Callable[..., bytes]
_PathParser = Callable[..., tuple[bytes, ...]]


@dataclass(frozen=True, slots=True)
class GitReviewDependencies:
    """Bind Git-window resolution to the current facade operations."""

    resolve_commit: Callable[..., str]
    select_changed_paths: Callable[..., tuple[bytes, ...]]
    porcelain_status: Callable[..., bytes]
    git_environment: Callable[[], dict[str, str]]
    error_type: type[Exception]


def _git_bytes(
    repo_root: Path,
    *args: str,
    environment: dict[str, str],
    error_type: type[Exception] = ReviewError,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            env=environment,
        )
    except OSError as exc:
        raise error_type(f"could not run Git: {type(exc).__name__}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise error_type(f"git {' '.join(args[:2])} failed: {detail or result.returncode}")
    return result.stdout


def _resolve_commit(
    repo_root: Path,
    ref: str,
    *,
    git_bytes: _GitBytes,
    error_type: type[Exception] = ReviewError,
) -> str:
    if ref.startswith("-"):
        raise error_type(f"Git ref must not start with '-': {ref!r}")
    value_bytes = git_bytes(
        repo_root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
    )
    value = value_bytes.removesuffix(b"\n").decode("ascii", errors="strict")
    if len(value) != 40 and len(value) != 64:
        raise error_type(f"Git did not resolve {ref!r} to a full commit ID")
    return value.lower()


def _nul_paths(
    raw: bytes,
    *,
    command: str,
    error_type: type[Exception] = ReviewError,
) -> tuple[bytes, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise error_type(f"git {command} returned a non-NUL-terminated path list")
    return tuple(path for path in raw[:-1].split(b"\0") if path)


def _select_changed_paths(
    repo_root: Path,
    *,
    comparison_base: str | None,
    head: str,
    git_bytes: _GitBytes,
    nul_paths: _PathParser,
    error_type: type[Exception] = ReviewError,
) -> tuple[bytes, ...]:
    diff_args = [
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--relative",
    ]
    if comparison_base is None:
        diff_args.extend(("HEAD", "--", "."))
    else:
        diff_args.extend((comparison_base, head, "--", "."))
    changed = set(
        nul_paths(
            git_bytes(repo_root, *diff_args),
            command="diff --name-only -z",
        )
    )
    if head == "HEAD":
        untracked = git_bytes(
            repo_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            ".",
        )
        changed.update(
            nul_paths(
                untracked,
                command="ls-files --others -z",
            )
        )
    return tuple(sorted(changed))


def _porcelain_status(
    repo_root: Path,
    *,
    git_environment: Callable[[], dict[str, str]],
    error_type: type[Exception] = ReviewError,
) -> bytes:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--",
                ".",
            ],
            check=False,
            capture_output=True,
            env=git_environment(),
        )
    except OSError as exc:
        raise error_type(
            f"could not inspect Git worktree status: {type(exc).__name__}: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise error_type(f"git status failed: {detail or result.returncode}")
    return result.stdout


def _resolve_git_window(
    repo_root: Path,
    *,
    base_ref: str | None,
    head_ref: str | None,
    dependencies: GitReviewDependencies,
) -> GitWindow:
    error_type = dependencies.error_type
    if (base_ref is None) != (head_ref is None):
        raise error_type("--base-ref and --head-ref must be supplied together")

    if base_ref is None:
        checkout = dependencies.resolve_commit(repo_root, "HEAD")
        raw_paths = dependencies.select_changed_paths(
            repo_root,
            comparison_base=None,
            head="HEAD",
        )
        paths = tuple(path.decode("utf-8", errors="surrogateescape") for path in raw_paths)
        return GitWindow(
            base_commit=None,
            head_commit=None,
            comparison_base=None,
            checkout_commit=checkout,
            workspace_matches_head=None,
            workspace_mismatch_reason=None,
            worktree_status=None,
            paths=paths,
            selection=(
                "Complete Git path set under the configured product root: worktree diff against "
                "HEAD plus untracked nonignored paths; paths outside the product root are "
                "excluded, including repository-root AGENTS.md when the product root is nested"
            ),
            raw_paths=raw_paths,
        )

    base = dependencies.resolve_commit(repo_root, base_ref)
    head = dependencies.resolve_commit(repo_root, head_ref or "")
    try:
        merge_base_result = subprocess.run(
            ["git", "merge-base", head, base],
            cwd=repo_root,
            check=False,
            capture_output=True,
            env=dependencies.git_environment(),
        )
    except OSError as exc:
        raise error_type(f"could not run git merge-base: {type(exc).__name__}: {exc}") from exc
    if merge_base_result.returncode == 0:
        comparison_base = merge_base_result.stdout.removesuffix(b"\n").decode("ascii")
    elif merge_base_result.returncode == 1:
        comparison_base = base
    else:
        detail = merge_base_result.stderr.decode("utf-8", errors="replace").strip()
        raise error_type(f"git merge-base failed: {detail or merge_base_result.returncode}")
    checkout = dependencies.resolve_commit(repo_root, "HEAD")
    try:
        worktree_status = dependencies.porcelain_status(repo_root)
    except error_type as exc:
        workspace_matches = False
        mismatch_reason = str(exc)
        worktree_status = None
    else:
        workspace_matches = checkout == head and not worktree_status
        mismatch_reason = None
        if checkout != head:
            mismatch_reason = "checkout HEAD differs from the requested immutable head commit"
        elif worktree_status:
            mismatch_reason = (
                "product worktree has tracked or untracked changes outside the immutable head"
            )
    raw_paths = dependencies.select_changed_paths(
        repo_root,
        comparison_base=comparison_base,
        head=head,
    )
    paths = tuple(path.decode("utf-8", errors="surrogateescape") for path in raw_paths)
    return GitWindow(
        base_commit=base,
        head_commit=head,
        comparison_base=comparison_base,
        checkout_commit=checkout,
        workspace_matches_head=workspace_matches,
        workspace_mismatch_reason=mismatch_reason,
        worktree_status=worktree_status,
        paths=paths,
        selection=(
            "Complete Git path set under the configured product root: commit diff from "
            "merge-base(base, head), or base when no merge-base exists; paths outside the "
            "product root are excluded, including repository-root AGENTS.md when the product "
            "root is nested"
        ),
        raw_paths=raw_paths,
    )
