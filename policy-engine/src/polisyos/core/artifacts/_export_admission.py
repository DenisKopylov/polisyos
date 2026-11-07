"""Finite, target-local admission for retained CAS export generations.

Limits count reserved sibling entries and logical regular-file bytes. They are
not a filesystem quota, free-space forecast, cleanup authority, or protection
against an uncoordinated actor growing/replacing entries after a measurement.
"""

from __future__ import annotations

import os
import stat
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from weakref import WeakValueDictionary

DEFAULT_MAX_RETAINED_GENERATIONS = 8
DEFAULT_MAX_RETAINED_BYTES = 1024**3
_THREAD_LOCKS: WeakValueDictionary[str, threading.Lock] = WeakValueDictionary()
_THREAD_LOCKS_GUARD = threading.Lock()


class ExportResourceError(OSError):
    """Refuse export work or diagnose a visible export's retained resource limit."""

    def __init__(
        self,
        reason: str,
        *,
        target: Path,
        lock_path: Path,
        occupied_paths: tuple[Path, ...] = (),
        occupied_bytes: int | None = None,
        max_retained_generations: int,
        max_retained_bytes: int,
        replaced: bool = False,
        staging_path: Path | None = None,
    ) -> None:
        self.reason = reason
        self.target = target
        self.lock_path = lock_path
        self.occupied_paths = occupied_paths
        self.occupied_bytes = occupied_bytes
        self.max_retained_generations = max_retained_generations
        self.max_retained_bytes = max_retained_bytes
        self.replaced = replaced
        self.staging_path = staging_path
        super().__init__(
            f"CAS export resource refusal ({reason}): target={target}; "
            f"occupied_count={len(occupied_paths)}; occupied_paths={occupied_paths[:8]}; "
            f"occupied_bytes={occupied_bytes}; "
            f"limits={max_retained_generations}/{max_retained_bytes}; replaced={replaced}"
        )


@dataclass(frozen=True, slots=True)
class _RetainedSnapshot:
    paths: tuple[Path, ...]
    byte_size: int


def _logical_bytes(path: Path) -> int:
    total = 0
    pending = [path]
    while pending:
        current = pending.pop()
        metadata = current.lstat()
        if stat.S_ISREG(metadata.st_mode):
            total += metadata.st_size
        elif stat.S_ISDIR(metadata.st_mode):
            with os.scandir(current) as entries:
                pending.extend(Path(entry.path) for entry in entries)
        else:
            raise OSError(
                f"Retained export entry cannot be measured without following it: {current}"
            )
    return total


@dataclass(slots=True)
class _ExportAdmission:
    target: Path
    lock_path: Path
    max_retained_generations: int
    max_retained_bytes: int
    stage_limit_bytes: int = 0
    written_bytes: int = 0
    staging_path: Path | None = None
    publication_completed: bool = False

    def refusal(
        self,
        reason: str,
        paths: tuple[Path, ...] = (),
        byte_size: int | None = None,
        *,
        replaced: bool = False,
    ) -> ExportResourceError:
        return ExportResourceError(
            reason,
            target=self.target,
            lock_path=self.lock_path,
            occupied_paths=paths,
            occupied_bytes=byte_size,
            max_retained_generations=self.max_retained_generations,
            max_retained_bytes=self.max_retained_bytes,
            replaced=replaced,
            staging_path=self.staging_path,
        )

    def snapshot(self, *, exclude: Path | None = None, replaced: bool = False) -> _RetainedSnapshot:
        replaced = replaced or self.publication_completed
        prefixes = tuple(
            f".{self.target.name}.{kind}-" for kind in ("staging", "generation", "previous")
        )
        paths: list[Path] = []
        try:
            # Enumeration itself is an observation, not proof that an unknown
            # namespace is empty. Keep the entire observation in one boundary.
            for path in self.target.parent.iterdir():
                if path.name.startswith(prefixes) and path != exclude:
                    paths.append(path)
            paths.sort(key=lambda path: path.name)
            byte_size = sum(_logical_bytes(path) for path in paths)
        except OSError as error:
            raise self.refusal(
                "unmeasurable_retained_entry", tuple(paths), replaced=replaced
            ) from error
        return _RetainedSnapshot(tuple(paths), byte_size)

    def reserve(self) -> None:
        snapshot = self.snapshot()
        try:
            displaced_bytes = _logical_bytes(self.target) if self.target.exists() else 0
        except OSError as error:
            raise self.refusal("unmeasurable_target", snapshot.paths) from error
        # Every admitted attempt reserves one possible incomplete/previous stage.
        # Success on an absent target naturally leaves that slot unused.
        if (
            len(snapshot.paths) + 1 > self.max_retained_generations
            or snapshot.byte_size + displaced_bytes > self.max_retained_bytes
            or snapshot.byte_size >= self.max_retained_bytes
        ):
            raise self.refusal("retention_limit", snapshot.paths, snapshot.byte_size)
        self.stage_limit_bytes = self.max_retained_bytes - snapshot.byte_size

    def consume(self, amount: int) -> None:
        if self.written_bytes + amount > self.stage_limit_bytes:
            snapshot = self.snapshot()
            raise self.refusal("stage_byte_limit", snapshot.paths, snapshot.byte_size)
        self.written_bytes += amount

    def before_publication(self, staging_path: Path) -> None:
        self.staging_path = staging_path
        snapshot = self.snapshot(exclude=staging_path)
        try:
            displaced_bytes = _logical_bytes(self.target) if self.target.exists() else 0
            stage_bytes = _logical_bytes(staging_path)
        except OSError as error:
            raise self.refusal("unmeasurable_publication_entry", snapshot.paths) from error
        if (
            len(snapshot.paths) + 1 > self.max_retained_generations
            or snapshot.byte_size + max(displaced_bytes, stage_bytes) > self.max_retained_bytes
        ):
            raise self.refusal(
                "retention_limit_before_publication", snapshot.paths, snapshot.byte_size
            )

    def after_publication(self) -> _RetainedSnapshot:
        self.publication_completed = True
        snapshot = self.snapshot(replaced=True)
        if (
            len(snapshot.paths) > self.max_retained_generations
            or snapshot.byte_size > self.max_retained_bytes
        ):
            raise self.refusal(
                "retention_limit_after_publication",
                snapshot.paths,
                snapshot.byte_size,
                replaced=True,
            )
        return snapshot


class _BudgetedArchiveWriter:
    """Limit actual compressed stage writes without buffering the archive."""

    def __init__(self, output: BinaryIO, admission: _ExportAdmission) -> None:
        self._output = output
        self._admission = admission

    def write(self, data: bytes) -> int:
        self._admission.consume(len(data))
        return self._output.write(data)

    def tell(self) -> int:
        return self._output.tell()

    def flush(self) -> None:
        self._output.flush()

    def read(self, size: int = -1) -> bytes:
        return self._output.read(size)

    def seek(self, offset: int) -> int:
        if offset != self._output.tell():
            raise OSError("Compressed export staging is a forward-only stream")
        return offset

    def close(self) -> None:
        # Borrow the stream. Its original fd owner performs fsync and closes it.
        self._output.flush()


@contextmanager
def _export_target_admission(
    target: Path,
    *,
    max_retained_generations: int,
    max_retained_bytes: int,
    validate_target: Callable[[], None],
) -> Iterator[_ExportAdmission]:
    """Acquire a nonblocking cooperating-writer lease before source consumption."""
    for value in (max_retained_generations, max_retained_bytes):
        if type(value) is not int or value < 0:
            raise ValueError("Export retention limits must be nonnegative integers")
    target.parent.mkdir(parents=True, exist_ok=True)
    target = target.parent.resolve() / target.name
    lock_path = target.with_name(f".{target.name}.export.lock")
    admission = _ExportAdmission(target, lock_path, max_retained_generations, max_retained_bytes)
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(str(lock_path))
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[str(lock_path)] = lock
    if not lock.acquire(blocking=False):
        raise admission.refusal("busy")
    descriptor = -1
    flocked = False
    body_error: BaseException | None = None
    try:
        try:
            import fcntl
        except ImportError as error:
            raise admission.refusal("lock_backend_unavailable") from error
        try:
            descriptor = os.open(
                lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
            )
        except OSError as error:
            raise admission.refusal("lock_unavailable") from error
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise admission.refusal("lock_not_regular")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise admission.refusal("busy") from error
        flocked = True
        current = lock_path.lstat()
        if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise admission.refusal("lock_identity_changed")
        validate_target()
        admission.reserve()
        yield admission
    except BaseException as error:
        body_error = error
        raise
    finally:
        release_error: OSError | None = None
        try:
            if descriptor >= 0:
                try:
                    if flocked:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError as error:
                    release_error = error
                finally:
                    try:
                        os.close(descriptor)
                    except OSError as error:
                        release_error = release_error or error
        finally:
            # Neither a backend unlock nor fd-close error can strand the thread gate.
            # Permanent lockfile identity is shared by future waiters; never unlink it.
            lock.release()
        if release_error is not None:
            if body_error is not None:
                body_error.add_note(f"Export lease release unavailable: {release_error}")
            else:
                snapshot = admission.snapshot(replaced=admission.publication_completed)
                raise admission.refusal(
                    "lock_release_unavailable",
                    snapshot.paths,
                    snapshot.byte_size,
                    replaced=admission.publication_completed,
                ) from release_error
