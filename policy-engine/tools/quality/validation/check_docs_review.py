#!/usr/bin/env python3
"""Review Git-selected documentation changes with existing repository checks."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import stat
import subprocess
import time
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.devx.workspace._repo_hygiene import _DEFAULT_MARKDOWN_EXCLUDES
from tools.lib.imports import repo_root_from
from tools.quality.validation import check_docs_gate

REPO_ROOT = repo_root_from(__file__).resolve()
OUTPUT_ROOT = Path("_build/docs-maintenance/docs-review")
DEFAULT_RECEIPT_NAME = "review.json"
MAX_COMPRESSED_LOG_BYTES = 32 * 1024 * 1024
DOCS_STYLE_EXCLUDES = _DEFAULT_MARKDOWN_EXCLUDES
UNRUN_GATE_KEYS = {"docs_lifecycle"}
UNRUN_INDEPENDENT_KEYS = {"docs_impact", "rendered_links"}


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


class ReviewError(ValueError):
    """Signal an input or evidence condition that prevents a review verdict."""


class LogBudgetExceededError(RuntimeError):
    """Signal that complete command output cannot fit the configured log budget."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Product root containing docs/, tools/, mkdocs.yml and _build/.",
    )
    parser.add_argument(
        "--base-ref",
        help="Base Git commit/ref; must be paired with --head-ref.",
    )
    parser.add_argument(
        "--head-ref",
        help="Head Git commit/ref; must be paired with --base-ref.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve Git changes and print the exact plan without executing checks.",
    )
    parser.add_argument(
        "--run-independent",
        action="store_true",
        help=(
            "Run Markdown style, source-impact review, and a matching rendered-link check "
            "independently of D6 fail-fast results."
        ),
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        help="Expected existing MkDocs site output; must equal configured site_dir.",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help=(
            f"Summary receipt under a fresh run directory in {OUTPUT_ROOT}/ "
            f"(default filename: {DEFAULT_RECEIPT_NAME})."
        ),
    )
    return parser


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            env=_git_environment(),
        )
    except OSError as exc:
        raise ReviewError(f"could not run Git: {type(exc).__name__}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewError(f"git {' '.join(args[:2])} failed: {detail or result.returncode}")
    return result.stdout


def _safe_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["UV_NO_SYNC"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _git_environment() -> dict[str, str]:
    environment = _safe_environment()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    return environment


def _resolve_commit(repo_root: Path, ref: str) -> str:
    if ref.startswith("-"):
        raise ReviewError(f"Git ref must not start with '-': {ref!r}")
    value_bytes = _git_bytes(
        repo_root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
    )
    value = value_bytes.removesuffix(b"\n").decode("ascii", errors="strict")
    if len(value) != 40 and len(value) != 64:
        raise ReviewError(f"Git did not resolve {ref!r} to a full commit ID")
    return value.lower()


def _nul_paths(raw: bytes, *, command: str) -> tuple[bytes, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise ReviewError(f"git {command} returned a non-NUL-terminated path list")
    return tuple(path for path in raw[:-1].split(b"\0") if path)


def _select_changed_paths(
    repo_root: Path, *, comparison_base: str | None, head: str
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
    changed = set(_nul_paths(_git_bytes(repo_root, *diff_args), command="diff --name-only -z"))
    if head == "HEAD":
        untracked = _git_bytes(
            repo_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            ".",
        )
        changed.update(_nul_paths(untracked, command="ls-files --others -z"))
    return tuple(sorted(changed))


def _porcelain_status(repo_root: Path) -> bytes:
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
            env=_git_environment(),
        )
    except OSError as exc:
        raise ReviewError(
            f"could not inspect Git worktree status: {type(exc).__name__}: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewError(f"git status failed: {detail or result.returncode}")
    return result.stdout


def _resolve_git_window(
    repo_root: Path, *, base_ref: str | None, head_ref: str | None
) -> GitWindow:
    if (base_ref is None) != (head_ref is None):
        raise ReviewError("--base-ref and --head-ref must be supplied together")

    if base_ref is None:
        checkout = _resolve_commit(repo_root, "HEAD")
        raw_paths = _select_changed_paths(repo_root, comparison_base=None, head="HEAD")
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

    base = _resolve_commit(repo_root, base_ref)
    head = _resolve_commit(repo_root, head_ref or "")
    try:
        merge_base_result = subprocess.run(
            ["git", "merge-base", head, base],
            cwd=repo_root,
            check=False,
            capture_output=True,
            env=_git_environment(),
        )
    except OSError as exc:
        raise ReviewError(f"could not run git merge-base: {type(exc).__name__}: {exc}") from exc
    if merge_base_result.returncode == 0:
        comparison_base = merge_base_result.stdout.removesuffix(b"\n").decode("ascii")
    elif merge_base_result.returncode == 1:
        comparison_base = base
    else:
        detail = merge_base_result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewError(f"git merge-base failed: {detail or merge_base_result.returncode}")
    checkout = _resolve_commit(repo_root, "HEAD")
    try:
        worktree_status = _porcelain_status(repo_root)
    except ReviewError as exc:
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
    raw_paths = _select_changed_paths(repo_root, comparison_base=comparison_base, head=head)
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


def _open_output_root(repo_root: Path) -> int:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        current_fd = os.open(repo_root, directory_flags)
    except OSError as exc:
        raise ReviewError(f"could not safely open product root: {exc}") from exc
    for component in OUTPUT_ROOT.parts:
        try:
            with suppress(FileExistsError):
                os.mkdir(component, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
        except OSError as exc:
            os.close(current_fd)
            raise ReviewError(
                f"docs-review output root has an unsafe or unusable component {component!r}: {exc}"
            ) from exc
        os.close(current_fd)
        current_fd = next_fd
    return current_fd


def _tracked_paths_under(repo_root: Path, run_directory: str, refs: Sequence[str]) -> list[str]:
    index_paths = _nul_paths(
        _git_bytes(
            repo_root,
            "ls-files",
            "--cached",
            "-z",
            "--",
            run_directory,
        ),
        command="ls-files --cached -z",
    )
    tracked = [path.decode("utf-8", errors="surrogateescape") for path in index_paths]
    for ref in dict.fromkeys(refs):
        tree_paths = _nul_paths(
            _git_bytes(
                repo_root,
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                ref,
                "--",
                run_directory,
            ),
            command="ls-tree -r -z",
        )
        tracked.extend(path.decode("utf-8", errors="surrogateescape") for path in tree_paths)
    return tracked


def _resolve_output_path(
    repo_root: Path, requested: Path | None, *, tracked_refs: Sequence[str]
) -> Path:
    output_root = repo_root / OUTPUT_ROOT
    if requested is None:
        run_name = f"run-{uuid.uuid4().hex}"
        receipt_name = DEFAULT_RECEIPT_NAME
    else:
        raw_path = requested if requested.is_absolute() else repo_root / requested
        path = Path(os.path.abspath(raw_path))
        try:
            relative = path.relative_to(output_root)
        except ValueError as exc:
            raise ReviewError(f"receipt must be under {OUTPUT_ROOT.as_posix()}/") from exc
        if len(relative.parts) != 2:
            raise ReviewError(
                "receipt must be a file directly inside a fresh run-<32 hex> directory"
            )
        run_name, receipt_name = relative.parts
        if len(run_name) != 36 or not run_name.startswith("run-"):
            raise ReviewError("receipt directory must use a fresh run-<32 hex> identifier")
        try:
            uuid.UUID(hex=run_name[4:])
        except ValueError as exc:
            raise ReviewError("receipt directory must use a fresh run-<32 hex> identifier") from exc
        if run_name[4:] != run_name[4:].lower():
            raise ReviewError("receipt directory must use a lowercase run identifier")
        if path.suffix.lower() != ".json":
            raise ReviewError("receipt path must end in .json")

    root_fd = _open_output_root(repo_root)
    try:
        run_relative = (OUTPUT_ROOT / run_name).as_posix()
        tracked = _tracked_paths_under(repo_root, run_relative, tracked_refs)
        if tracked:
            raise ReviewError(
                "fresh review output directory intersects tracked paths: "
                + ", ".join(repr(path) for path in tracked[:5])
            )
        try:
            os.mkdir(run_name, mode=0o700, dir_fd=root_fd)
        except FileExistsError as exc:
            raise ReviewError(
                f"review run directory already exists and is never overwritten: {run_name}"
            ) from exc
        except OSError as exc:
            raise ReviewError(f"could not exclusively create review run directory: {exc}") from exc
        run_fd = os.open(
            run_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        try:
            if os.listdir(run_fd):
                raise ReviewError("new review run directory was not empty")
        finally:
            os.close(run_fd)
    finally:
        os.close(root_fd)
    return output_root / run_name / receipt_name


def _safe_output_child(output_path: Path, relative: str) -> Path:
    root = output_path.parent
    candidate = Path(relative)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts:
        raise ReviewError(f"output path escapes its fresh review directory: {relative}")
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise ReviewError(f"fresh review directory is unavailable: {exc}") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise ReviewError("fresh review directory must be a real directory, not a symlink")
    current = root
    for component in candidate.parts[:-1]:
        current = current / component
        with suppress(FileExistsError):
            current.mkdir(mode=0o700)
        try:
            component_stat = current.lstat()
        except OSError as exc:
            raise ReviewError(f"could not inspect output directory {current}: {exc}") from exc
        if stat.S_ISLNK(component_stat.st_mode) or not stat.S_ISDIR(component_stat.st_mode):
            raise ReviewError(f"output path traverses a non-directory or symlink: {current}")
    child = current / candidate.parts[-1]
    if child.exists() or child.is_symlink():
        raise ReviewError(f"output target already exists and is never overwritten: {relative}")
    return child


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gzip_bytes(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=6, mtime=0)


def _write_artifact(
    path: Path,
    raw: bytes,
    *,
    compressed: bool,
    budget_state: dict[str, int] | None = None,
) -> dict[str, Any]:
    encoded = _gzip_bytes(raw) if compressed else raw
    if budget_state is not None and compressed:
        if budget_state["used"] + len(encoded) > MAX_COMPRESSED_LOG_BYTES:
            raise LogBudgetExceededError(
                f"compressed child logs would exceed {MAX_COMPRESSED_LOG_BYTES} bytes"
            )
        budget_state["used"] += len(encoded)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise
    return {
        "path": path.as_posix(),
        "sha256": _sha256(encoded),
        "stored_bytes": len(encoded),
        "original_bytes": len(raw),
        "encoding": "gzip" if compressed else "identity",
    }


def _changed_paths_artifact(
    repo_root: Path, output_path: Path, raw_paths: Sequence[bytes], budget_state: dict[str, int]
) -> dict[str, Any]:
    identity = b"\0".join(raw_paths)
    if raw_paths:
        identity += b"\0"
    lines = [
        json.dumps(
            {
                "display_path": raw_path.decode("utf-8", errors="surrogateescape"),
                "path_bytes_base64": base64.b64encode(raw_path).decode("ascii"),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        for raw_path in raw_paths
    ]
    manifest = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    path = _safe_output_child(output_path, "raw/changed-paths.jsonl.gz")
    artifact = _write_artifact(path, manifest, compressed=True, budget_state=budget_state)
    artifact["path"] = _relative(repo_root, path)
    artifact["format"] = "JSON Lines with escaped display path and exact Git path bytes in base64"
    artifact["path_count"] = len(raw_paths)
    artifact["path_set_sha256"] = _sha256(identity)
    return artifact


def _worktree_status_artifact(
    repo_root: Path, output_path: Path, status_bytes: bytes, budget_state: dict[str, int]
) -> dict[str, Any]:
    path = _safe_output_child(output_path, "raw/worktree-status.porcelain.gz")
    artifact = _write_artifact(path, status_bytes, compressed=True, budget_state=budget_state)
    artifact["path"] = _relative(repo_root, path)
    artifact["format"] = "Git porcelain v1, NUL-delimited"
    artifact["entry_bytes"] = len(status_bytes)
    return artifact


def _store_logs(
    repo_root: Path,
    output_path: Path,
    lane: str,
    sequence: int,
    key: str,
    stdout: bytes,
    stderr: bytes,
    budget_state: dict[str, int],
) -> dict[str, dict[str, Any]]:
    stem = f"{lane}-{sequence:02d}-{key}"
    stdout_path = _safe_output_child(output_path, f"raw/{stem}.stdout.gz")
    stderr_path = _safe_output_child(output_path, f"raw/{stem}.stderr.gz")
    stdout_encoded = _gzip_bytes(stdout)
    stderr_encoded = _gzip_bytes(stderr)
    encoded_size = len(stdout_encoded) + len(stderr_encoded)
    if budget_state["used"] + encoded_size > MAX_COMPRESSED_LOG_BYTES:
        raise LogBudgetExceededError(
            f"compressed child logs would exceed {MAX_COMPRESSED_LOG_BYTES} bytes"
        )
    budget_state["used"] += encoded_size
    stdout_meta = _write_artifact(stdout_path, stdout, compressed=True)
    stderr_meta = _write_artifact(stderr_path, stderr, compressed=True)
    stdout_meta["path"] = _relative(repo_root, stdout_path)
    stderr_meta["path"] = _relative(repo_root, stderr_path)
    return {"stdout": stdout_meta, "stderr": stderr_meta}


def _hash_file(path: Path) -> dict[str, Any] | None:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        return None
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"path": path.as_posix(), "sha256": digest.hexdigest(), "bytes": size}


def _file_identity(path: Path | None) -> tuple[int, int] | None:
    if path is None:
        return None
    try:
        entry_stat = path.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
        return None
    return entry_stat.st_mtime_ns, entry_stat.st_size


def _exit_status(key: str, code: int) -> str:
    if code == 0:
        return "PASS"
    if code == 2 and key in UNRUN_GATE_KEYS | UNRUN_INDEPENDENT_KEYS:
        return "UNRUN"
    if code == 1 and key == "docs_impact":
        return "REVIEW_REQUIRED"
    return "FAIL"


def _run_child(
    repo_root: Path,
    output_path: Path,
    *,
    lane: str,
    sequence: int,
    key: str,
    label: str,
    argv: Sequence[str],
    budget_state: dict[str, int],
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "key": key,
        "label": label,
        "argv": list(argv),
        "cwd": _relative(repo_root, repo_root),
        "status": "UNRUN",
        "exit_code": None,
    }
    receipt_before = _file_identity(receipt_path)
    try:
        completed = subprocess.run(
            list(argv),
            cwd=repo_root,
            check=False,
            capture_output=True,
            env=_safe_environment(),
        )
    except OSError as exc:
        result.update(
            {
                "status": "UNRUN",
                "reason": f"could not start child: {type(exc).__name__}: {exc}",
            }
        )
    else:
        result["exit_code"] = completed.returncode
        result["status"] = _exit_status(key, completed.returncode)
        try:
            result.update(
                _store_logs(
                    repo_root,
                    output_path,
                    lane,
                    sequence,
                    key,
                    completed.stdout,
                    completed.stderr,
                    budget_state,
                )
            )
            result["log_status"] = "COMPLETE"
        except (LogBudgetExceededError, OSError, ReviewError) as exc:
            result["log_status"] = "UNRUN"
            result["log_reason"] = str(exc)
            if result["status"] == "PASS":
                result["status"] = "UNRUN"
        if receipt_path is not None:
            child_receipt = _hash_file(receipt_path)
            receipt_after = _file_identity(receipt_path)
            if child_receipt is None or receipt_after == receipt_before:
                result["process_status"] = result["status"]
                result["child_receipt_status"] = "UNRUN"
                result["child_receipt_reason"] = (
                    "the child did not produce a fresh declared receipt"
                )
                result["status"] = "UNRUN"
            else:
                child_receipt["path"] = _relative(repo_root, receipt_path)
                result["child_receipt_status"] = "PRESENT"
                result["child_receipt"] = child_receipt
                if key == "docs_impact":
                    impact_report: Any = None
                    with suppress(UnicodeError, json.JSONDecodeError):
                        impact_report = json.loads(completed.stdout.decode("utf-8"))
                    if isinstance(impact_report, dict):
                        impact_status = impact_report.get("status")
                        reported_receipt = impact_report.get("receipt_path")
                        summary = impact_report.get("summary")
                    else:
                        impact_status = None
                        reported_receipt = None
                        summary = None
                    expected = {
                        0: "PASS",
                        1: "REVIEW_REQUIRED",
                        2: "UNRUN",
                    }.get(completed.returncode)
                    try:
                        receipt_matches = isinstance(reported_receipt, str) and Path(
                            reported_receipt
                        ).resolve(strict=False) == receipt_path.resolve(strict=False)
                    except (OSError, RuntimeError):
                        receipt_matches = False
                    if impact_status != expected or not receipt_matches:
                        result["status"] = "UNRUN"
                        result["child_receipt_reason"] = (
                            "docs-impact exit code, compact status, and receipt path do not agree"
                        )
                    else:
                        result["status"] = impact_status
                        result["impact_status"] = impact_status
                        if isinstance(summary, dict):
                            result["human_review_page_count"] = summary.get(
                                "human_review_page_count"
                            )
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def _markdown_style_paths(repo_root: Path, paths: Sequence[str]) -> tuple[str, ...]:
    candidates = []
    for path in paths:
        normalized = path
        if not normalized.lower().endswith(".md"):
            continue
        if any(normalized.startswith(prefix) for prefix in DOCS_STYLE_EXCLUDES):
            continue
        if (repo_root / normalized).is_file():
            candidates.append(normalized)
    return tuple(sorted(set(candidates)))


def _mkdocs_site_configuration(repo_root: Path) -> tuple[Path, str]:
    try:
        from mkdocs.config import load_config

        config = load_config(config_file=str(repo_root / "mkdocs.yml"))
        site_dir = Path(config["site_dir"])
        if not site_dir.is_absolute():
            site_dir = repo_root / site_dir
        site_url = str(config.get("site_url") or "").strip()
        if not site_url:
            raise ReviewError("MkDocs config does not define site_url")
        return site_dir.resolve(strict=False), site_url
    except ReviewError:
        raise
    except Exception as exc:
        raise ReviewError(
            f"MkDocs site configuration unavailable: {type(exc).__name__}: {exc}"
        ) from exc


def _site_choice(
    repo_root: Path, requested: Path | None
) -> tuple[Path | None, str | None, str | None]:
    try:
        configured_site, site_url = _mkdocs_site_configuration(repo_root)
    except ReviewError as exc:
        return None, None, str(exc)
    selected = requested
    if selected is None:
        selected_path = configured_site
    else:
        selected_path = selected if selected.is_absolute() else repo_root / selected
        selected_path = selected_path.resolve(strict=False)
        if selected_path != configured_site:
            return (
                configured_site,
                site_url,
                "--site-dir does not match the configured MkDocs site_dir; no alternate build is run",
            )
    build_root = (repo_root / "_build").resolve(strict=False)
    if not build_root.is_relative_to(repo_root.resolve(strict=False)):
        return configured_site, site_url, "repository _build path resolves outside the product root"
    if not selected_path.resolve(strict=False).is_relative_to(build_root):
        return configured_site, site_url, "configured MkDocs site_dir is outside repository _build/"
    return selected_path, site_url, None


def _gate_child_plan(plan: check_docs_gate.GatePlan) -> list[dict[str, Any]]:
    return [
        {
            "key": command.key,
            "label": command.label,
            "argv": list(command.argv),
            "status": "PLANNED",
        }
        for command in plan.commands
    ]


def _run_gate(
    repo_root: Path,
    output_path: Path,
    plan: check_docs_gate.GatePlan,
    budget_state: dict[str, int],
    *,
    dry_run: bool,
    unavailable_reason: str | None = None,
) -> dict[str, Any]:
    if unavailable_reason:
        children = _gate_child_plan(plan)
        for child in children:
            child["status"] = "UNRUN"
            child["reason"] = unavailable_reason
        return {
            "status": "UNRUN",
            "children": children,
            "findings": [finding.__dict__ for finding in plan.findings],
            "reason": unavailable_reason,
        }
    if dry_run:
        return {
            "status": "UNRUN",
            "children": _gate_child_plan(plan),
            "findings": [finding.__dict__ for finding in plan.findings],
            "reason": "dry-run resolved the plan but executed no validation children",
        }

    children: list[dict[str, Any]] = []
    blocked_by: str | None = None
    for sequence, command in enumerate(plan.commands, start=1):
        if blocked_by is not None:
            children.append(
                {
                    "key": command.key,
                    "label": command.label,
                    "argv": list(command.argv),
                    "status": "BLOCKED",
                    "blocked_by": blocked_by,
                }
            )
            continue
        child = _run_child(
            repo_root,
            output_path,
            lane="d6",
            sequence=sequence,
            key=command.key,
            label=command.label,
            argv=command.argv,
            budget_state=budget_state,
        )
        children.append(child)
        if child["status"] != "PASS":
            blocked_by = command.key

    findings = [finding.__dict__ for finding in plan.findings]
    if findings:
        status = "FAIL"
    elif blocked_by is not None:
        status = next(child["status"] for child in children if child["key"] == blocked_by)
    else:
        status = "PASS"
    return {"status": status, "children": children, "findings": findings}


def _impact_child(
    repo_root: Path, output_path: Path, window: GitWindow
) -> tuple[tuple[str, ...] | None, Path | None, str | None]:
    if window.base_commit is None or window.head_commit is None or window.comparison_base is None:
        return (
            None,
            None,
            "source impact requires immutable base/head commits; current worktree has no immutable head snapshot",
        )
    child_receipt = _safe_output_child(output_path, "children/docs-impact.json")
    argv = (
        "uv",
        "run",
        "polisyos-tools",
        "validation",
        "check-docs-impact",
        "--repo-root",
        str(repo_root),
        "--base-ref",
        window.comparison_base,
        "--head-ref",
        window.head_commit,
        "--format",
        "json",
        "--output",
        str(child_receipt),
    )
    return argv, child_receipt, None


def _run_independent(
    repo_root: Path,
    output_path: Path,
    window: GitWindow,
    plan: check_docs_gate.GatePlan,
    gate: dict[str, Any],
    budget_state: dict[str, int],
    *,
    dry_run: bool,
    run_independent: bool,
    requested_site_dir: Path | None,
    workspace_mismatch_reason: str | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "requested": run_independent,
        "style": {"status": "NOT_REQUESTED"},
        "impact": {"status": "NOT_REQUESTED"},
        "build": {"status": "NOT_REQUESTED"},
        "rendered_links": {"status": "NOT_REQUESTED"},
        "unmeasured": [
            "check-docs-source-bindings is not automatically run; docs-impact only queues pages whose declared Source of truth intersects the immutable changed-path set and does not prove prose truth or pin equality"
        ],
    }
    if not run_independent:
        return result

    style_paths = _markdown_style_paths(repo_root, window.paths)
    if not style_paths:
        result["style"] = {
            "status": "NOT_APPLICABLE",
            "reason": "no changed existing Markdown files are in the configured docs-style scope",
        }
    elif workspace_mismatch_reason:
        result["style"] = {
            "status": "UNRUN",
            "reason": workspace_mismatch_reason,
            "selected_path_count": len(style_paths),
        }
    elif dry_run:
        result["style"] = {
            "status": "PLANNED",
            "argv": ["uv", "run", "polisyos-tools", "workspace", "docs-style", *style_paths],
            "selected_path_count": len(style_paths),
        }
    else:
        child = _run_child(
            repo_root,
            output_path,
            lane="independent",
            sequence=1,
            key="docs_style",
            label="lint changed authored Markdown",
            argv=("uv", "run", "polisyos-tools", "workspace", "docs-style", *style_paths),
            budget_state=budget_state,
        )
        child["selected_path_count"] = len(style_paths)
        result["style"] = child

    try:
        impact_argv, impact_receipt, impact_reason = _impact_child(repo_root, output_path, window)
    except ReviewError as exc:
        impact_argv, impact_receipt, impact_reason = None, None, str(exc)
    if impact_reason:
        result["impact"] = {"status": "UNRUN", "reason": impact_reason}
    elif dry_run:
        result["impact"] = {
            "status": "PLANNED",
            "argv": list(impact_argv or ()),
            "receipt_path": _relative(repo_root, impact_receipt or output_path),
        }
    else:
        result["impact"] = _run_child(
            repo_root,
            output_path,
            lane="independent",
            sequence=2,
            key="docs_impact",
            label="queue source-bound pages affected by changed source paths",
            argv=impact_argv or (),
            budget_state=budget_state,
            receipt_path=impact_receipt,
        )

    strict_command = next(
        (command for command in plan.commands if command.key == "strict_docs_build"), None
    )
    gate_build = next(
        (child for child in gate["children"] if child["key"] == "strict_docs_build"), None
    )
    if strict_command is None or workspace_mismatch_reason:
        site_dir, site_url, site_problem = None, None, None
    else:
        site_dir, site_url, site_problem = _site_choice(repo_root, requested_site_dir)
    build_child: dict[str, Any] | None = None
    if strict_command is None:
        result["build"] = {
            "status": "NOT_APPLICABLE",
            "reason": "D6 did not plan a strict docs build; independent review does not add a build",
        }
        result["rendered_links"] = {
            "status": "NOT_APPLICABLE",
            "reason": "no matching strict docs build was planned",
        }
    elif workspace_mismatch_reason:
        result["build"] = {"status": "UNRUN", "reason": workspace_mismatch_reason}
        result["rendered_links"] = {"status": "UNRUN", "reason": workspace_mismatch_reason}
    elif dry_run:
        link_status = "UNRUN" if site_problem else "PLANNED"
        result["build"] = {
            "status": "PLANNED",
            "argv": list(strict_command.argv),
            "site_dir": _relative(repo_root, site_dir) if site_dir is not None else None,
        }
        result["rendered_links"] = {
            "status": link_status,
            "site_dir": _relative(repo_root, site_dir) if site_dir is not None else None,
            "site_url": site_url,
            "reason": site_problem,
        }
    else:
        if gate_build is not None and gate_build["status"] != "BLOCKED":
            build_child = gate_build
            result["build"] = {
                "status": gate_build["status"],
                "source": "D6 gate child; reused without a duplicate build",
                "gate_child_key": "strict_docs_build",
            }
        else:
            build_child = _run_child(
                repo_root,
                output_path,
                lane="independent",
                sequence=3,
                key="strict_docs_build",
                label="build configured docs site independently after D6 early stop",
                argv=strict_command.argv,
                budget_state=budget_state,
            )
            result["build"] = {
                **build_child,
                "source": "independent execution of the existing D6 strict-build command",
            }
        if build_child["status"] != "PASS":
            result["rendered_links"] = {
                "status": "UNRUN",
                "reason": "matching strict docs build did not pass",
            }
        elif site_problem:
            result["rendered_links"] = {"status": "UNRUN", "reason": site_problem}
        elif site_dir is None or site_url is None:
            result["rendered_links"] = {
                "status": "UNRUN",
                "reason": "configured MkDocs output or site_url could not be resolved",
            }
        else:
            try:
                link_receipt = _safe_output_child(output_path, "children/rendered-links.json")
            except ReviewError as exc:
                result["rendered_links"] = {"status": "UNRUN", "reason": str(exc)}
                return result
            link_child = _run_child(
                repo_root,
                output_path,
                lane="independent",
                sequence=4,
                key="rendered_links",
                label="check local links in the matching existing MkDocs output",
                argv=(
                    "uv",
                    "run",
                    "polisyos-tools",
                    "validation",
                    "check-docs-rendered-links",
                    "--site-dir",
                    str(site_dir),
                    "--site-url",
                    site_url,
                    "--output",
                    str(link_receipt),
                ),
                budget_state=budget_state,
                receipt_path=link_receipt,
            )
            link_child["site_dir"] = _relative(repo_root, site_dir)
            result["rendered_links"] = link_child
    return result


def _overall_status(gate: dict[str, Any], independent: dict[str, Any], *, dry_run: bool) -> str:
    statuses = [gate["status"]]
    if independent["requested"]:
        statuses.extend(
            independent[key]["status"]
            for key in ("style", "impact", "build", "rendered_links")
            if independent[key]["status"] not in {"NOT_APPLICABLE", "NOT_REQUESTED"}
        )
    if "FAIL" in statuses:
        return "FAIL"
    if "UNRUN" in statuses or dry_run:
        return "UNRUN"
    if "PLANNED" in statuses:
        return "UNRUN"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    return "PASS"


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ReviewError("fresh review directory is unavailable or is a symlink")
    encoded = (json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _empty_report(repo_root: Path, output_path: Path, reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "UNRUN",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "receipt": str(output_path),
        "reason": reason,
        "gate": {"status": "UNRUN", "children": [], "findings": []},
        "independent": {"requested": False},
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if (args.base_ref is None) != (args.head_ref is None):
        _parser().error("--base-ref and --head-ref must be supplied together")
    repo_root = args.repo_root.resolve()
    try:
        window = _resolve_git_window(
            repo_root,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
        )
        plan = check_docs_gate.build_gate_plan(window.paths)
    except (ReviewError, OSError, UnicodeError) as exc:
        print(json.dumps({"verdict": "UNRUN", "reason": str(exc)}, sort_keys=True))
        return 2

    tracked_refs = tuple(
        value
        for value in (window.checkout_commit, window.base_commit, window.head_commit)
        if value is not None
    )
    try:
        output_path = _resolve_output_path(repo_root, args.receipt, tracked_refs=tracked_refs)
    except (ReviewError, OSError, UnicodeError) as exc:
        print(json.dumps({"verdict": "UNRUN", "reason": str(exc)}, sort_keys=True))
        return 2

    budget_state = {"used": 0}
    try:
        changed_artifact = _changed_paths_artifact(
            repo_root, output_path, window.raw_paths, budget_state
        )
    except (OSError, LogBudgetExceededError, ReviewError) as exc:
        report = _empty_report(repo_root, output_path, f"could not retain the Git path set: {exc}")
        try:
            _write_summary(output_path, report)
        except (OSError, ReviewError) as write_exc:
            report["reason"] += f"; summary could not be written: {write_exc}"
        print(
            json.dumps(
                {
                    "verdict": "UNRUN",
                    "reason": report["reason"],
                    "receipt": _relative(repo_root, output_path),
                },
                sort_keys=True,
            )
        )
        return 2
    worktree_status_artifact = None
    if window.worktree_status is not None:
        try:
            worktree_status_artifact = _worktree_status_artifact(
                repo_root, output_path, window.worktree_status, budget_state
            )
        except (OSError, LogBudgetExceededError, ReviewError) as exc:
            report = _empty_report(
                repo_root, output_path, f"could not retain Git worktree status: {exc}"
            )
            try:
                _write_summary(output_path, report)
            except (OSError, ReviewError) as write_exc:
                report["reason"] += f"; summary could not be written: {write_exc}"
            print(
                json.dumps(
                    {
                        "verdict": "UNRUN",
                        "reason": report["reason"],
                        "receipt": _relative(repo_root, output_path),
                    },
                    sort_keys=True,
                )
            )
            return 2

    gate = _run_gate(
        repo_root,
        output_path,
        plan,
        budget_state,
        dry_run=args.dry_run,
        unavailable_reason=window.workspace_mismatch_reason,
    )
    independent = _run_independent(
        repo_root,
        output_path,
        window,
        plan,
        gate,
        budget_state,
        dry_run=args.dry_run,
        run_independent=args.run_independent,
        requested_site_dir=args.site_dir,
        workspace_mismatch_reason=window.workspace_mismatch_reason,
    )
    status = _overall_status(gate, independent, dry_run=args.dry_run)
    report = {
        "schema_version": 1,
        "status": status,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "receipt": _relative(repo_root, output_path),
        "inputs": {
            "base_ref": args.base_ref,
            "base_commit": window.base_commit,
            "comparison_base_commit": window.comparison_base,
            "head_ref": args.head_ref,
            "head_commit": window.head_commit,
            "checkout_head_commit": window.checkout_commit,
            "workspace_matches_head": window.workspace_matches_head,
            "workspace_mismatch_reason": window.workspace_mismatch_reason,
            "worktree_status_artifact": worktree_status_artifact,
            "selection": window.selection,
            "path_scope": {
                "included": "all Git-selected paths relative to the configured product root",
                "excluded": (
                    "every path outside the product root, including repository-root AGENTS.md "
                    "when the product root is nested"
                ),
            },
            "changed_path_count": len(window.paths),
            "changed_path_artifact": changed_artifact,
        },
        "plan": {
            "gate_commands": _gate_child_plan(plan),
            "gate_findings": [finding.__dict__ for finding in plan.findings],
            "run_independent": args.run_independent,
            "dry_run": args.dry_run,
        },
        "gate": gate,
        "independent": independent,
        "log_budget": {
            "limit_compressed_bytes": MAX_COMPRESSED_LOG_BYTES,
            "used_compressed_bytes": budget_state["used"],
        },
        "unmeasured": [
            "check-docs-source-bindings is not automatically run; docs-impact only queues pages whose declared Source of truth intersects the immutable changed-path set and does not prove prose truth or pin equality",
            "runtime behavior, external URL liveness, browser behavior and deployment",
        ],
    }
    try:
        _write_summary(output_path, report)
    except (OSError, ReviewError) as exc:
        print(
            json.dumps(
                {
                    "verdict": "UNRUN",
                    "reason": f"final review receipt could not be safely written: {exc}",
                    "receipt": _relative(repo_root, output_path),
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "verdict": status,
                "receipt": _relative(repo_root, output_path),
                "changed_path_count": len(window.paths),
                "gate": gate["status"],
                "independent_requested": args.run_independent,
            },
            sort_keys=True,
        )
    )
    return {"PASS": 0, "FAIL": 1, "UNRUN": 2, "REVIEW_REQUIRED": 1}[status]


if __name__ == "__main__":
    raise SystemExit(main())
