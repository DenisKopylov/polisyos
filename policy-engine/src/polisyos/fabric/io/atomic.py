"""Atomic filesystem helpers for Fabric mutable metadata."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised on POSIX CI/dev hosts
    import fcntl
except Exception:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


def fsync_parent(path: Path) -> None:
    """Flush the directory entry containing ``path`` when the platform supports it."""
    parent = Path(path).parent
    fd: int | None = None
    try:
        fd = os.open(parent, os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        return
    finally:
        if fd is not None:
            os.close(fd)


def cleanup_orphan_tmp_files(root: Path, *, pattern: str = "*.tmp") -> None:
    """Best-effort cleanup for stale temp files left by interrupted atomic writes."""
    if not root.exists():
        return
    for tmp_path in root.rglob(pattern):
        if not tmp_path.is_file():
            continue
        with contextlib.suppress(OSError):
            tmp_path.unlink()


@contextlib.contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    """Cross-process advisory exclusive lock for mutable Fabric index files."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write_text(
    path: Path,
    text: str,
    *,
    validate_tmp: Callable[[Path], None] | None = None,
) -> None:
    """Write text atomically using temp-in-same-dir, file fsync, rename, dir fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        tmp_path = Path(tmp_name)
        if validate_tmp is not None:
            validate_tmp(tmp_path)
        os.replace(tmp_path, path)
        fsync_parent(path)
    except Exception:
        if tmp_name is not None:
            with contextlib.suppress(OSError):
                Path(tmp_name).unlink()
        raise


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    validate_tmp: Callable[[Path], None] | None = None,
) -> None:
    """Write JSON atomically and fsync both file and parent directory."""
    text = json.dumps(payload, sort_keys=True, indent=2)
    atomic_write_text(path, text, validate_tmp=validate_tmp)


def append_text_locked(path: Path, text: str, *, lock_path: Path) -> None:
    """Append text while holding an advisory lock and fsyncing the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(lock_path):
        with path.open("a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        fsync_parent(path)


__all__ = [
    "append_text_locked",
    "atomic_write_json",
    "atomic_write_text",
    "cleanup_orphan_tmp_files",
    "file_lock",
    "fsync_parent",
]
