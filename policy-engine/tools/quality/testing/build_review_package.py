#!/usr/bin/env python3
"""Build deterministic, offline review packages for a Git commit range."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

SOURCE_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SOURCE_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_REPO_ROOT))

from tools.lib.fs import atomic_write_bytes  # noqa: E402

PACKAGE_MAGIC: Final = b"POLISYOS_REVIEW_PACKAGE\n"
SCHEMA_VERSION: Final = 1
_GIT_CONTEXT_ENVIRONMENT_KEYS: Final = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_EXEC_PATH",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)
_STABLE_DIFF_ARGUMENTS: Final = (
    "--find-renames=50%",
    "--diff-algorithm=histogram",
    "--no-indent-heuristic",
    "--unified=3",
    "--inter-hunk-context=0",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--no-relative",
)


class ReviewPackageError(RuntimeError):
    """Raised when a review package cannot be proven safe to build."""


def _git_environment() -> dict[str, str]:
    """Return a noninteractive Git environment with external execution disabled."""

    environment = os.environ.copy()
    for key in _GIT_CONTEXT_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    for key in tuple(environment):
        if key == "GIT_CONFIG_COUNT" or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(key, None)
    environment.pop("GIT_EXTERNAL_DIFF", None)
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PAGER": "cat",
        }
    )
    return environment


def _git_argv(*arguments: str) -> list[str]:
    """Build a pinned Git argument vector for deterministic read-only commands."""

    return [
        "git",
        "--no-pager",
        "--no-replace-objects",
        "--literal-pathspecs",
        "-c",
        "color.ui=false",
        "-c",
        "core.pager=cat",
        "-c",
        "core.quotePath=true",
        "-c",
        "diff.algorithm=histogram",
        "-c",
        "diff.context=3",
        "-c",
        "diff.indentHeuristic=false",
        "-c",
        "diff.interHunkContext=0",
        "-c",
        "diff.mnemonicPrefix=false",
        "-c",
        "diff.noprefix=false",
        "-c",
        f"diff.orderFile={os.devnull}",
        "-c",
        "diff.renameLimit=32767",
        *arguments,
    ]


def _run_git(worktree: Path, *arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> bytes:
    """Run one read-only Git command without a shell and return stdout bytes."""

    result = subprocess.run(  # noqa: S603 - Git argv is explicit and never shell-expanded.
        _git_argv(*arguments),
        cwd=worktree,
        env=_git_environment(),
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode not in accepted_codes:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        rendered = " ".join(arguments[:2])
        raise ReviewPackageError(
            f"git {rendered} failed with exit {result.returncode}: {detail or 'no diagnostic'}"
        )
    return result.stdout


def _discover_worktree(invocation_cwd: Path) -> Path:
    """Resolve the current Git worktree even when invoked from a subdirectory."""

    raw_root = _run_git(invocation_cwd, "rev-parse", "--show-toplevel").rstrip(b"\r\n")
    if not raw_root:
        raise ReviewPackageError("git rev-parse returned an empty worktree root")
    worktree = Path(os.fsdecode(raw_root)).resolve(strict=True)
    if not worktree.is_dir():
        raise ReviewPackageError("resolved Git worktree root is not a directory")
    return worktree


def _resolve_commit(worktree: Path, revision: str, *, label: str) -> str:
    """Resolve and peel one revision to a real commit object."""

    if not revision or "\x00" in revision:
        raise ReviewPackageError(f"{label} revision must not be empty or contain NUL")
    raw_commit = _run_git(
        worktree,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{revision}^{{commit}}",
    ).strip()
    try:
        commit = raw_commit.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ReviewPackageError(f"{label} revision resolved to a non-ASCII object id") from exc
    if not commit or any(character not in "0123456789abcdef" for character in commit):
        raise ReviewPackageError(f"{label} revision did not resolve to a full commit id")
    return commit


def _require_ancestor(worktree: Path, base_commit: str, head_commit: str) -> None:
    """Fail unless ``base_commit`` is an ancestor of ``head_commit``."""

    result = subprocess.run(  # noqa: S603 - Git argv is explicit and never shell-expanded.
        _git_argv("merge-base", "--is-ancestor", base_commit, head_commit),
        cwd=worktree,
        env=_git_environment(),
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode == 1:
        raise ReviewPackageError("base commit is not an ancestor of head commit")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewPackageError(
            "git merge-base --is-ancestor failed with exit "
            f"{result.returncode}: {detail or 'no diagnostic'}"
        )


def _resolve_git_path(worktree: Path, *arguments: str) -> Path:
    """Resolve a Git-reported administrative path to an absolute real path."""

    raw_path = _run_git(worktree, "rev-parse", *arguments).rstrip(b"\r\n")
    if not raw_path:
        raise ReviewPackageError("git rev-parse returned an empty administrative path")
    path = Path(os.fsdecode(raw_path))
    if not path.is_absolute():
        path = worktree / path
    return path.resolve(strict=True)


def _is_at_or_below(path: Path, root: Path) -> bool:
    """Return whether ``path`` is ``root`` or one of its descendants."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlink_components(path: Path, *, worktree: Path, label: str) -> None:
    """Reject an existing symlink at any worktree-relative path component."""

    relative = path.relative_to(worktree)
    current = worktree
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ReviewPackageError(f"{label} path must not traverse a symlink")
        if not current.exists():
            break


def _touches_admin_state(path: Path, *, admin_roots: tuple[Path, ...]) -> bool:
    """Detect administrative ancestors by inode, including case-folded aliases."""

    current = path if path.exists() else path.parent
    while True:
        for admin_root in admin_roots:
            if _is_at_or_below(current, admin_root):
                return True
            try:
                if current.exists() and admin_root.exists() and current.samefile(admin_root):
                    return True
            except OSError:
                continue
        if current == current.parent:
            return False
        current = current.parent


def _resolve_inside_worktree(
    raw_path: str | Path,
    *,
    invocation_cwd: Path,
    worktree: Path,
    label: str,
    must_exist: bool = False,
) -> Path:
    """Resolve a file path and reject symlinks, admin paths, or worktree escapes."""

    rendered = str(raw_path)
    if not rendered or "\x00" in rendered:
        raise ReviewPackageError(f"{label} path must not be empty or contain NUL")
    candidate = Path(rendered)
    if not candidate.is_absolute():
        candidate = invocation_cwd / candidate
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(worktree)
    except ValueError as exc:
        raise ReviewPackageError(f"{label} path must stay inside the Git worktree") from exc
    git_marker = worktree / ".git"
    if _is_at_or_below(lexical, git_marker):
        raise ReviewPackageError(f"{label} path must not target the Git marker")
    _reject_symlink_components(lexical, worktree=worktree, label=label)
    try:
        resolved = lexical.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ReviewPackageError(f"{label} path does not exist") from exc
    try:
        resolved.relative_to(worktree)
    except ValueError as exc:
        raise ReviewPackageError(f"{label} real path must stay inside the Git worktree") from exc
    git_dir = _resolve_git_path(worktree, "--git-dir")
    common_dir = _resolve_git_path(worktree, "--git-common-dir")
    if _touches_admin_state(resolved, admin_roots=(git_marker, git_dir, common_dir)):
        raise ReviewPackageError(f"{label} path must not target Git administrative state")
    if must_exist and not resolved.exists():
        raise ReviewPackageError(f"{label} path does not exist")
    if resolved.exists() and not resolved.is_file():
        raise ReviewPackageError(f"{label} path must name a file")
    return resolved


def _normalize_git_text(payload: bytes) -> bytes:
    """Normalize generated Git text to LF without decoding repository paths."""

    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _render_section(name: str, payload: bytes, *, digest: str | None = None) -> bytes:
    """Render one length-delimited deterministic package section."""

    header = f"section={name}\nlength={len(payload)}\n".encode("ascii")
    if digest is not None:
        header += f"sha256={digest}\n".encode("ascii")
    header += b"\n"
    return header + payload + b"\nend_section\n"


def _render_package(
    worktree: Path,
    *,
    base_commit: str,
    head_commit: str,
    prior_findings: bytes | None,
) -> bytes:
    """Render the stable shared sections for a full or delta package."""

    commit_list = _normalize_git_text(
        _run_git(
            worktree,
            "rev-list",
            "--reverse",
            "--topo-order",
            f"{base_commit}..{head_commit}",
        )
    )
    diff_stat = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            "--stat=120,100,9999",
            "--stat-graph-width=20",
            *_STABLE_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
        )
    )
    name_status = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            "--name-status",
            *_STABLE_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
        )
    )
    patch = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            "--binary",
            "--full-index",
            *_STABLE_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
        )
    )
    package_kind = "delta" if prior_findings is not None else "full"
    metadata = (
        PACKAGE_MAGIC
        + f"schema_version={SCHEMA_VERSION}\n".encode("ascii")
        + f"package_kind={package_kind}\n".encode("ascii")
        + f"base_commit={base_commit}\n".encode("ascii")
        + f"head_commit={head_commit}\n\n".encode("ascii")
    )
    sections = [
        metadata,
        _render_section("commit_list", commit_list),
        _render_section("diff_stat", diff_stat),
        _render_section("name_status", name_status),
        _render_section("patch", patch),
    ]
    if prior_findings is not None:
        sections.append(
            _render_section(
                "prior_findings",
                prior_findings,
                digest=hashlib.sha256(prior_findings).hexdigest(),
            )
        )
    sections.append(b"end_package\n")
    return b"".join(sections)


def build_review_package(
    *,
    base_revision: str,
    head_revision: str,
    output_path: str | Path,
    prior_findings_path: str | Path | None = None,
    invocation_cwd: Path | None = None,
) -> bytes:
    """Build and atomically persist one full or delta commit-range review package.

    Args:
        base_revision: Revision naming the already-reviewed lower bound.
        head_revision: Revision naming the upper review bound.
        output_path: Destination inside the current Git worktree.
        prior_findings_path: Exact prior-review checklist for delta mode.
        invocation_cwd: Directory from which Git worktree discovery starts.

    Returns:
        The exact package bytes written to ``output_path``.

    Raises:
        ReviewPackageError: If revisions, ancestry, or the destination fail validation.
    """

    origin = (invocation_cwd or Path.cwd()).resolve(strict=True)
    worktree = _discover_worktree(origin)
    destination = _resolve_inside_worktree(
        output_path,
        invocation_cwd=origin,
        worktree=worktree,
        label="output",
    )
    prior_findings: bytes | None = None
    if prior_findings_path is not None:
        checklist = _resolve_inside_worktree(
            prior_findings_path,
            invocation_cwd=origin,
            worktree=worktree,
            label="prior findings",
            must_exist=True,
        )
        if checklist == destination:
            raise ReviewPackageError("output path must differ from prior findings path")
        prior_findings = checklist.read_bytes()
        if not prior_findings or not prior_findings.strip():
            raise ReviewPackageError("prior findings file must not be empty")
    base_commit = _resolve_commit(worktree, base_revision, label="base")
    head_commit = _resolve_commit(worktree, head_revision, label="head")
    _require_ancestor(worktree, base_commit, head_commit)
    package = _render_package(
        worktree,
        base_commit=base_commit,
        head_commit=head_commit,
        prior_findings=prior_findings,
    )
    atomic_write_bytes(destination, package)
    return package


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the standalone review-package command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Lower commit-range revision.")
    parser.add_argument("--head", required=True, help="Upper commit-range revision.")
    parser.add_argument("--output", required=True, help="Output path inside the Git worktree.")
    parser.add_argument(
        "--prior-findings",
        help="Prior-review findings checklist; when present, build a delta package.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build a review package and return a shell-compatible exit code."""

    args = _parse_args(argv)
    try:
        package = build_review_package(
            base_revision=args.base,
            head_revision=args.head,
            output_path=args.output,
            prior_findings_path=args.prior_findings,
        )
    except (OSError, ReviewPackageError) as exc:
        print(f"review-package error: {exc}", file=sys.stderr)
        return 2
    print(f"review package written ({len(package)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
