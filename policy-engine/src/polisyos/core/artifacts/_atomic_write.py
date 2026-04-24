"""Atomic CAS file-write helpers shared by filesystem-backed artifact stores."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def fsync_parent(path: Path) -> None:
    """Best-effort fsync for the parent directory after an atomic replace/link."""
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class AtomicFileWriter:
    """Write immutable CAS files atomically without leaving temporary residue."""

    @staticmethod
    def write_atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            fsync_parent(path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @staticmethod
    def write_once(path: Path, data: bytes) -> bool:
        """Create `path` atomically and report whether this writer won."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return False
        tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError:
                return False
            fsync_parent(path)
            return True
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)


__all__ = ["AtomicFileWriter", "fsync_parent"]
