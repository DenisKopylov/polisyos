"""Atomic CAS file-write helpers shared by filesystem-backed artifact stores."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class AtomicFileDurabilityError(OSError):
    """Report a directory-sync failure and whether the name was already published."""

    def __init__(self, message: str, *, replaced: bool) -> None:
        super().__init__(message)
        self.replaced = replaced


def fsync_directory(path: Path) -> None:
    """Fsync a directory entry table, raising when it cannot be made durable."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directory_durable(path: Path) -> None:
    """Create `path` and durably publish each newly created directory entry."""
    path = path.absolute()
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(f"No existing ancestor for {path}")
        current = parent
    if not current.is_dir():
        raise NotADirectoryError(current)

    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise NotADirectoryError(directory) from None
        fsync_directory(directory.parent)


def fsync_parent(path: Path) -> None:
    """Best-effort fsync for the parent directory after an atomic replace/link."""
    try:
        fsync_directory(path.parent)
    except OSError:
        return


class AtomicFileWriter:
    """Write immutable CAS files atomically without leaving temporary residue."""

    @staticmethod
    def write_atomic(path: Path, data: bytes, *, durable_parent: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            if durable_parent:
                try:
                    fsync_directory(path.parent)
                except OSError as exc:
                    raise AtomicFileDurabilityError(
                        "atomic replacement published but parent fsync failed",
                        replaced=True,
                    ) from exc
            else:
                fsync_parent(path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @staticmethod
    def write_once(path: Path, data: bytes, *, durable_parent: bool = False) -> bool:
        """Create `path` atomically and report whether this writer won."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return False
        tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        linked = False
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
                linked = True
            except FileExistsError:
                return False
            if durable_parent:
                try:
                    fsync_directory(path.parent)
                except OSError as exc:
                    raise AtomicFileDurabilityError(
                        "immutable link published but parent fsync failed",
                        replaced=linked,
                    ) from exc
            else:
                fsync_parent(path)
            return True
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)


__all__ = [
    "AtomicFileDurabilityError",
    "AtomicFileWriter",
    "ensure_directory_durable",
    "fsync_directory",
    "fsync_parent",
]
