"""Secure fresh-run output and retained artifacts for documentation reviews."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import stat
import uuid
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LogBudgetExceededError(RuntimeError):
    """Signal that complete command output cannot fit the configured log budget."""


_ErrorType = type[Exception]
_ArtifactWriter = Callable[..., dict[str, Any]]
_OutputChild = Callable[..., Path]
_RelativePath = Callable[..., str]
_Digest = Callable[..., str]
_Gzip = Callable[..., bytes]


@dataclass(frozen=True, slots=True)
class ArtifactDependencies:
    """Bind artifact operations to the current review facade helpers and limits."""

    output_root: Path
    default_receipt_name: str
    max_compressed_log_bytes: int
    error_type: _ErrorType
    log_budget_error_type: _ErrorType
    open_output_root: Callable[..., int]
    tracked_paths_under: Callable[..., list[str]]
    git_bytes: Callable[..., bytes]
    nul_paths: Callable[..., tuple[bytes, ...]]
    safe_output_child: _OutputChild
    write_artifact: _ArtifactWriter
    relative: _RelativePath
    sha256: _Digest
    gzip_bytes: _Gzip


def _open_output_root(
    repo_root: Path,
    *,
    dependencies: ArtifactDependencies,
) -> int:
    output_root = dependencies.output_root
    error_type = dependencies.error_type
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        current_fd = os.open(repo_root, directory_flags)
    except OSError as exc:
        raise error_type(f"could not safely open product root: {exc}") from exc
    for component in output_root.parts:
        try:
            with suppress(FileExistsError):
                os.mkdir(component, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
        except OSError as exc:
            os.close(current_fd)
            raise error_type(
                f"docs-review output root has an unsafe or unusable component {component!r}: {exc}"
            ) from exc
        os.close(current_fd)
        current_fd = next_fd
    return current_fd


def _tracked_paths_under(
    repo_root: Path,
    run_directory: str,
    refs: Sequence[str],
    *,
    dependencies: ArtifactDependencies,
) -> list[str]:
    index_paths = dependencies.nul_paths(
        dependencies.git_bytes(
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
        tree_paths = dependencies.nul_paths(
            dependencies.git_bytes(
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
    repo_root: Path,
    requested: Path | None,
    *,
    tracked_refs: Sequence[str],
    dependencies: ArtifactDependencies,
) -> Path:
    output_root = dependencies.output_root
    default_receipt_name = dependencies.default_receipt_name
    error_type = dependencies.error_type
    output_path = repo_root / output_root
    if requested is None:
        run_name = f"run-{uuid.uuid4().hex}"
        receipt_name = default_receipt_name
    else:
        raw_path = requested if requested.is_absolute() else repo_root / requested
        path = Path(os.path.abspath(raw_path))
        try:
            relative = path.relative_to(output_path)
        except ValueError as exc:
            raise error_type(f"receipt must be under {output_root.as_posix()}/") from exc
        if len(relative.parts) != 2:
            raise error_type(
                "receipt must be a file directly inside a fresh run-<32 hex> directory"
            )
        run_name, receipt_name = relative.parts
        if len(run_name) != 36 or not run_name.startswith("run-"):
            raise error_type("receipt directory must use a fresh run-<32 hex> identifier")
        try:
            uuid.UUID(hex=run_name[4:])
        except ValueError as exc:
            raise error_type("receipt directory must use a fresh run-<32 hex> identifier") from exc
        if run_name[4:] != run_name[4:].lower():
            raise error_type("receipt directory must use a lowercase run identifier")
        if path.suffix.lower() != ".json":
            raise error_type("receipt path must end in .json")

    root_fd = dependencies.open_output_root(repo_root)
    try:
        run_relative = (output_root / run_name).as_posix()
        tracked = dependencies.tracked_paths_under(repo_root, run_relative, tracked_refs)
        if tracked:
            raise error_type(
                "fresh review output directory intersects tracked paths: "
                + ", ".join(repr(path) for path in tracked[:5])
            )
        try:
            os.mkdir(run_name, mode=0o700, dir_fd=root_fd)
        except FileExistsError as exc:
            raise error_type(
                f"review run directory already exists and is never overwritten: {run_name}"
            ) from exc
        except OSError as exc:
            raise error_type(f"could not exclusively create review run directory: {exc}") from exc
        run_fd = os.open(
            run_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        try:
            if os.listdir(run_fd):
                raise error_type("new review run directory was not empty")
        finally:
            os.close(run_fd)
    finally:
        os.close(root_fd)
    return output_path / run_name / receipt_name


def _safe_output_child(
    output_path: Path,
    relative: str,
    *,
    dependencies: ArtifactDependencies,
) -> Path:
    error_type = dependencies.error_type
    root = output_path.parent
    candidate = Path(relative)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts:
        raise error_type(f"output path escapes its fresh review directory: {relative}")
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise error_type(f"fresh review directory is unavailable: {exc}") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise error_type("fresh review directory must be a real directory, not a symlink")
    current = root
    for component in candidate.parts[:-1]:
        current = current / component
        with suppress(FileExistsError):
            current.mkdir(mode=0o700)
        try:
            component_stat = current.lstat()
        except OSError as exc:
            raise error_type(f"could not inspect output directory {current}: {exc}") from exc
        if stat.S_ISLNK(component_stat.st_mode) or not stat.S_ISDIR(component_stat.st_mode):
            raise error_type(f"output path traverses a non-directory or symlink: {current}")
    child = current / candidate.parts[-1]
    if child.exists() or child.is_symlink():
        raise error_type(f"output target already exists and is never overwritten: {relative}")
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
    budget_state: dict[str, int] | None,
    dependencies: ArtifactDependencies,
) -> dict[str, Any]:
    encoded = dependencies.gzip_bytes(raw) if compressed else raw
    if budget_state is not None and compressed:
        if budget_state["used"] + len(encoded) > dependencies.max_compressed_log_bytes:
            raise dependencies.log_budget_error_type(
                f"compressed child logs would exceed {dependencies.max_compressed_log_bytes} bytes"
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
        "sha256": dependencies.sha256(encoded),
        "stored_bytes": len(encoded),
        "original_bytes": len(raw),
        "encoding": "gzip" if compressed else "identity",
    }


def _changed_paths_artifact(
    repo_root: Path,
    output_path: Path,
    raw_paths: Sequence[bytes],
    budget_state: dict[str, int],
    *,
    dependencies: ArtifactDependencies,
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
    path = dependencies.safe_output_child(output_path, "raw/changed-paths.jsonl.gz")
    artifact = dependencies.write_artifact(
        path,
        manifest,
        compressed=True,
        budget_state=budget_state,
    )
    artifact["path"] = dependencies.relative(repo_root, path)
    artifact["format"] = "JSON Lines with escaped display path and exact Git path bytes in base64"
    artifact["path_count"] = len(raw_paths)
    artifact["path_set_sha256"] = dependencies.sha256(identity)
    return artifact


def _worktree_status_artifact(
    repo_root: Path,
    output_path: Path,
    status_bytes: bytes,
    budget_state: dict[str, int],
    *,
    dependencies: ArtifactDependencies,
) -> dict[str, Any]:
    path = dependencies.safe_output_child(output_path, "raw/worktree-status.porcelain.gz")
    artifact = dependencies.write_artifact(
        path,
        status_bytes,
        compressed=True,
        budget_state=budget_state,
    )
    artifact["path"] = dependencies.relative(repo_root, path)
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
    *,
    dependencies: ArtifactDependencies,
) -> dict[str, dict[str, Any]]:
    stem = f"{lane}-{sequence:02d}-{key}"
    stdout_path = dependencies.safe_output_child(output_path, f"raw/{stem}.stdout.gz")
    stderr_path = dependencies.safe_output_child(output_path, f"raw/{stem}.stderr.gz")
    stdout_encoded = dependencies.gzip_bytes(stdout)
    stderr_encoded = dependencies.gzip_bytes(stderr)
    encoded_size = len(stdout_encoded) + len(stderr_encoded)
    if budget_state["used"] + encoded_size > dependencies.max_compressed_log_bytes:
        raise dependencies.log_budget_error_type(
            f"compressed child logs would exceed {dependencies.max_compressed_log_bytes} bytes"
        )
    budget_state["used"] += encoded_size
    stdout_meta = dependencies.write_artifact(stdout_path, stdout, compressed=True)
    stderr_meta = dependencies.write_artifact(stderr_path, stderr, compressed=True)
    stdout_meta["path"] = dependencies.relative(repo_root, stdout_path)
    stderr_meta["path"] = dependencies.relative(repo_root, stderr_path)
    return {"stdout": stdout_meta, "stderr": stderr_meta}
