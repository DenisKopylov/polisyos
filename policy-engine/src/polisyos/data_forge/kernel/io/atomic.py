"""Atomic file write helpers for Data Forge publication boundaries."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_bytes(path: str | Path, payload: bytes) -> Path:
    """Write bytes through a temp file in the target directory and atomically replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
        _fsync_dir(target.parent)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


def atomic_write_text(path: str | Path, payload: str) -> Path:
    """Atomically write UTF-8 text and return the target path."""
    return atomic_write_bytes(path, payload.encode("utf-8"))


def atomic_write_json(path: str | Path, payload: object) -> Path:
    """Atomically write a deterministic UTF-8 JSON document."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return atomic_write_text(path, text)


def atomic_commit_path(staging_path: str | Path, final_path: str | Path) -> Path:
    """Atomically replace `final_path` with an already-staged file or directory."""
    staging = Path(staging_path)
    final = Path(final_path)
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final)
    _fsync_dir(final.parent)
    return final


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "atomic_commit_path",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
]
