"""Filesystem helpers for hardened tooling flows."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def iter_repository_files(repo_root: Path) -> Iterator[Path]:
    """Enumerate tracked paths without admitting station-local ignore rules or files.

    Args:
        repo_root: Repository or product directory whose files should be enumerated.

    Yields:
        Tracked paths, including absent paths so callers can report unreadable input.
        Standalone fixture directories without Git metadata use their complete file set.

    Raises:
        RuntimeError: Git metadata exists but its tracked paths cannot be enumerated.
        OSError: Git cannot be executed or the fixture directory cannot be read.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "-z", "--", "."],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if listed.returncode == 0:
        yield from (
            repo_root / relative
            for relative in sorted(set(os.fsdecode(listed.stdout).split("\0")))
            if relative
        )
        return
    if any((parent / ".git").exists() for parent in (repo_root, *repo_root.parents)):
        raise RuntimeError("committed file enumeration is ambiguous: git ls-files failed")
    yield from sorted(path for path in repo_root.rglob("*") if path.is_file())


def normalize_filesystem_path(
    value: str | Path,
    *,
    kind: str = "path",
    must_exist: bool = True,
    allow_directory: bool | None = None,
) -> Path:
    """Normalize and validate a filesystem path before use."""

    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{kind} must not be empty")
    if "\x00" in raw:
        raise ValueError(f"{kind} must not contain NUL bytes")

    path = Path(raw).expanduser().resolve(strict=must_exist)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"{kind} not found: {path}")

    if allow_directory is True and path.exists() and not path.is_dir():
        raise ValueError(f"{kind} must be a directory: {path}")
    if allow_directory is False and path.exists() and path.is_dir():
        raise ValueError(f"{kind} must be a file: {path}")
    return path


def atomic_write_text(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Write a text file atomically via a sibling temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a binary file atomically via a sibling temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    trailing_newline: bool = True,
) -> None:
    """Serialize JSON atomically."""

    rendered = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    if trailing_newline:
        rendered += "\n"
    atomic_write_text(
        path,
        rendered,
        encoding=encoding,
    )


def write_text_exclusive(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Create a text file only if it does not already exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def write_json_exclusive(
    path: Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    trailing_newline: bool = True,
) -> None:
    """Create a JSON file only if it does not already exist."""

    rendered = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    if trailing_newline:
        rendered += "\n"
    write_text_exclusive(path, rendered, encoding=encoding)


@contextmanager
def exclusive_lock(path: Path, *, content: str = "") -> Iterator[Path]:
    """Acquire a lock file via O_CREAT|O_EXCL and remove it on exit."""

    write_text_exclusive(path, content, encoding="utf-8")
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def atomic_replace_path(
    staged_path: Path,
    final_path: Path,
    *,
    backup_suffix: str | None = None,
) -> Path | None:
    """Atomically replace a file or directory, preserving the previous target as a backup."""

    staged_path = normalize_filesystem_path(staged_path, kind="staged path", must_exist=True)
    final_path = normalize_filesystem_path(final_path, kind="final path", must_exist=False)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Path | None = None
    if final_path.exists():
        suffix = backup_suffix or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = final_path.with_name(f"{final_path.name}.bak.{suffix}")
        if backup_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing backup path: {backup_path}")
        final_path.replace(backup_path)

    try:
        staged_path.replace(final_path)
    except Exception:
        if backup_path is not None and backup_path.exists() and not final_path.exists():
            backup_path.replace(final_path)
        raise

    return backup_path


class FileReadMeasurement:
    """Collect explicit file-reader operations without claiming a process-wide audit."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._inputs: list[dict[str, Any]] = []

    def record(self, path: Path, operation: str, **facts: Any) -> None:
        """Record a completed read, failed attempt, or filesystem presence probe."""
        try:
            name = path.relative_to(self.root).as_posix()
        except ValueError:
            name = str(path)
        self._inputs.append({"path": name, "operation": operation, **facts})

    def snapshot(self, *, complete_verdict: bool = True) -> dict[str, Any]:
        """Return actual operations and the boundary the collector cannot observe."""
        return {
            "complete_verdict": complete_verdict,
            "finding_coverage": "explicit file-reader operations only",
            "inputs": list(self._inputs),
            "unresolved_by_construction": [
                "Python imports, Git object/ref access, subprocess reads and external services "
                "are not observed by this explicit file-reader receipt.",
            ],
        }


_ACTIVE_FILE_READS: ContextVar[FileReadMeasurement | None] = ContextVar(
    "tool_file_read_measurement",
    default=None,
)


@contextmanager
def measure_file_reads(root: Path) -> Iterator[FileReadMeasurement]:
    """Collect this caller's explicit reads, reusing an enclosing same-root receipt."""
    existing = _ACTIVE_FILE_READS.get()
    if existing is not None and existing.root == root.resolve():
        yield existing
        return
    measurement = FileReadMeasurement(root)
    token = _ACTIVE_FILE_READS.set(measurement)
    try:
        yield measurement
    finally:
        _ACTIVE_FILE_READS.reset(token)


def _record_file_read(path: Path, operation: str, **facts: Any) -> None:
    measurement = _ACTIVE_FILE_READS.get()
    if measurement is not None:
        measurement.record(path, operation, **facts)


def measured_read_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Read text and record success or unreadability; the digest binds decoded text."""
    try:
        value = path.read_text(encoding=encoding)
    except (OSError, UnicodeError) as error:
        _record_file_read(path, "read_text", status="unreadable", error=type(error).__name__)
        raise
    _record_file_read(
        path,
        "read_text",
        status="read",
        encoding=encoding,
        characters=len(value),
        text_sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
    )
    return value


def measured_read_bytes(path: Path) -> bytes:
    """Read bytes and record the exact content identity or failed attempt."""
    try:
        value = path.read_bytes()
    except OSError as error:
        _record_file_read(path, "read_bytes", status="unreadable", error=type(error).__name__)
        raise
    _record_file_read(
        path,
        "read_bytes",
        status="read",
        bytes=len(value),
        sha256=hashlib.sha256(value).hexdigest(),
    )
    return value


def _measured_path_kind(path: Path, *, directory: bool) -> bool:
    operation = "is_dir" if directory else "is_file"
    try:
        mode = path.stat().st_mode
        result = stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)
    except (FileNotFoundError, NotADirectoryError):
        _record_file_read(path, operation, status="absent", result=False)
        return False
    except OSError as error:
        _record_file_read(path, operation, status="unreadable", error=type(error).__name__)
        raise
    _record_file_read(path, operation, status="present", result=result)
    return result


def measured_is_file(path: Path) -> bool:
    """Probe file presence while keeping access errors distinct from absence."""
    return _measured_path_kind(path, directory=False)


def measured_is_dir(path: Path) -> bool:
    """Probe directory presence without turning inaccessible parents into absence."""
    return _measured_path_kind(path, directory=True)
