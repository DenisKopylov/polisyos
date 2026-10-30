"""Atomic CAS file-write helpers shared by filesystem-backed artifact stores."""

from __future__ import annotations

import os
import stat
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class AtomicFileDurabilityError(OSError):
    """Report a directory-sync failure and whether the name was already published."""

    def __init__(self, message: str, *, replaced: bool) -> None:
        super().__init__(message)
        self.replaced = replaced


class _PreparedAtomicReplace:
    """One owner-prepared file, with the data sync separated from replacement."""

    def __init__(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        self._replaced = False
        self._closed = False
        self._temp_identity: tuple[int, int] | None = None
        try:
            descriptor = os.open(self._tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                initial = os.fstat(descriptor)
                self._temp_identity = (initial.st_dev, initial.st_ino)
                handle = os.fdopen(descriptor, "w+b")
            except BaseException:
                os.close(descriptor)
                raise
            with handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                handle.seek(0)
                if handle.read() != data:
                    raise OSError("prepared_atomic_write_content_mismatch")
                self._identity = self._file_identity(os.fstat(handle.fileno()))
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _file_identity(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    def replace(self, *, not_after: datetime | None = None) -> None:
        """Replace the bound path once with the verified prepared file."""
        if self._closed or self._replaced:
            raise OSError("prepared_atomic_write_not_current")
        info = os.stat(self._tmp, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or self._file_identity(info) != self._identity:
            raise OSError("prepared_atomic_write_changed")
        if not_after is not None and (
            not_after.tzinfo is None
            or not_after.utcoffset() is None
            or datetime.now(UTC) >= not_after
        ):
            raise OSError("prepared_atomic_write_deadline_expired")
        os.replace(self._tmp, self._path)
        self._replaced = True

    def sync_parent(self) -> None:
        """Confirm durability after replacement; a failure preserves unknown visibility."""
        if self._closed or not self._replaced:
            raise OSError("prepared_atomic_write_not_replaced")
        try:
            fsync_directory(self._path.parent)
        except OSError as exc:
            raise AtomicFileDurabilityError(
                "atomic replacement published but parent fsync failed", replaced=True
            ) from exc

    def close(self) -> None:
        """Close the product write lifecycle without removing the published file."""
        self._closed = True
        if self._replaced or self._temp_identity is None:
            return
        try:
            current = os.stat(self._tmp, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) == self._temp_identity:
            self._tmp.unlink(missing_ok=True)


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
