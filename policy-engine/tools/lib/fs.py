"""Filesystem helpers for hardened tooling flows."""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, Protocol, TextIO, cast


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
    """Write text atomically normally, or through the active native output root."""
    output_root = active_secure_output_root()
    if output_root is not None:
        output_root.write_text(path, data, encoding=encoding)
        return
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
    """Write bytes atomically normally, or through the active native output root."""
    output_root = active_secure_output_root()
    if output_root is not None:
        output_root.write_bytes(path, data)
        return
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


class SecureOutputRoot:
    """Create evidence files beneath one pinned directory without following links.

    The root directory is opened once and retained as a directory descriptor. Each
    output path is resolved relative to that descriptor, and every descendant
    directory and final leaf is opened with no-follow and exclusive-create flags.
    """

    def __init__(self, root: Path) -> None:
        """Open an existing output root without following any path component.

        Args:
            root: Existing directory that owns all files written by this instance.

        Raises:
            OSError: The platform lacks required no-follow directory support, or a
                component of ``root`` is not a real directory.
            ValueError: ``root`` is empty or contains a NUL byte.
        """
        self.root = _absolute_output_path(root, kind="output root")
        self._descriptor = _open_absolute_directory(self.root)
        self._owned_descriptors: dict[tuple[str, ...], int] = {}
        self._shared_leaf_ids: dict[tuple[str, ...], tuple[int, int]] = {}
        self._owned_lock = threading.RLock()

    def __enter__(self) -> SecureOutputRoot:
        """Return this open output root for use as a context manager."""
        if self._descriptor < 0:
            raise ValueError("secure output root is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the pinned output root descriptor."""
        self.close()

    def close(self) -> None:
        """Close the pinned root and every leaf descriptor owned by this lifecycle."""
        with self._owned_lock:
            for descriptor in self._owned_descriptors.values():
                os.close(descriptor)
            self._owned_descriptors.clear()
            if self._descriptor >= 0:
                descriptor = self._descriptor
                self._descriptor = -1
                os.close(descriptor)

    @classmethod
    def from_inherited_descriptor(
        cls,
        root: Path,
        descriptor: int,
        *,
        expected_identity: tuple[int, int],
        shared_leaf_ids: dict[tuple[str, ...], tuple[int, int]],
    ) -> SecureOutputRoot:
        """Attach to a root descriptor explicitly passed by the scoped runner."""
        observed = os.fstat(descriptor)
        if not stat.S_ISDIR(observed.st_mode):
            raise OSError("inherited output descriptor is not a directory")
        if (observed.st_dev, observed.st_ino) != expected_identity:
            raise OSError("inherited output descriptor identity mismatch")
        instance = cls.__new__(cls)
        instance.root = _absolute_output_path(root, kind="output root")
        instance._descriptor = os.dup(descriptor)
        instance._owned_descriptors = {}
        instance._shared_leaf_ids = dict(shared_leaf_ids)
        instance._owned_lock = threading.RLock()
        return instance

    def inherited_scope_environment(self) -> dict[str, str]:
        """Describe this root and its shared leaves for one admitted child."""
        root_stat = os.fstat(self.descriptor)
        shared = {
            "/".join(parts): [device, inode]
            for parts, (device, inode) in sorted(self._shared_leaf_ids.items())
        }
        return {
            _SECURE_OUTPUT_ROOT_ENV: str(self.root),
            _SECURE_OUTPUT_ROOT_ID_ENV: f"{root_stat.st_dev}:{root_stat.st_ino}",
            _SECURE_OUTPUT_ROOT_FD_ENV: str(self.descriptor),
            _SECURE_OUTPUT_SHARED_LEAVES_ENV: json.dumps(shared, sort_keys=True),
        }

    def claim_shared_leaf(self, path: Path) -> None:
        """Create and bind the identity of one lifecycle-shared mutable sink."""
        descriptor = self._owned_file_descriptor(path)
        parts = _output_parts_beneath(path, self.root)
        observed = os.fstat(descriptor)
        with self._owned_lock:
            self._shared_leaf_ids[parts] = (observed.st_dev, observed.st_ino)

    @property
    def descriptor(self) -> int:
        """Return this live directory descriptor for a child handoff."""
        if self.closed:
            raise ValueError("secure output root is closed")
        return self._descriptor

    @property
    def closed(self) -> bool:
        """Whether this output root has released its pinned directory descriptor."""
        return self._descriptor < 0

    def create_directory(self, path: Path) -> None:
        """Create one new directory below the pinned root without following links.

        Missing parent directories are created beneath the pinned descriptor. The
        final directory must be new.

        Args:
            path: Absolute or working-directory-relative strict descendant of root.

        Raises:
            FileExistsError: The final directory already exists.
            OSError: A parent is a symlink or cannot be opened safely.
            ValueError: The requested path is not below root.
        """
        if self.closed:
            raise ValueError("secure output root is closed")
        parts = _output_parts_beneath(path, self.root)
        with self._owned_lock:
            parent_descriptor = _open_output_parent(self._descriptor, parts[:-1])
            try:
                os.mkdir(parts[-1], 0o700, dir_fd=parent_descriptor)
            finally:
                os.close(parent_descriptor)

    def ensure_directory(self, path: Path) -> None:
        """Create missing directories beneath root or validate existing ones."""
        if self.closed:
            raise ValueError("secure output root is closed")
        parts = _output_parts_beneath(path, self.root)
        with self._owned_lock:
            descriptor = _open_output_parent(self._descriptor, parts)
            os.close(descriptor)

    def open_binary(self, path: Path) -> BinaryIO:
        """Open one lifecycle-owned binary output stream."""
        return cast(
            "BinaryIO",
            self._open_stream(path, binary=True, encoding=None, buffering=-1),
        )

    def open_text(self, path: Path, *, encoding: str = "utf-8", buffering: int = -1) -> TextIO:
        """Open one lifecycle-owned text output stream."""
        return cast(
            "TextIO",
            self._open_stream(path, binary=False, encoding=encoding, buffering=buffering),
        )

    def _open_stream(
        self,
        path: Path,
        *,
        binary: bool,
        encoding: str | None,
        buffering: int,
    ) -> _LockedStream:
        self._owned_lock.acquire()
        descriptor: int | None = None
        try:
            self._owned_file_descriptor(path)
            descriptor = self._open_fresh_owned_descriptor(path, os.O_WRONLY)
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if binary:
                stream = os.fdopen(descriptor, "wb", buffering=buffering)
            else:
                if encoding is None:
                    raise ValueError("text output requires an encoding")
                stream = os.fdopen(descriptor, "w", encoding=encoding, buffering=buffering)
            descriptor = None
            return _LockedStream(stream, self._owned_lock)
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            self._owned_lock.release()
            raise

    def _open_fresh_owned_descriptor(self, path: Path, access_flags: int) -> int:
        """Open a distinct description and verify it still names the owned object."""
        owner = self._owned_file_descriptor(path)
        parts = _output_parts_beneath(path, self.root)
        parent_descriptor = _open_output_parent(self._descriptor, parts[:-1])
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            os.close(parent_descriptor)
            raise OSError("platform does not provide O_NOFOLLOW")
        try:
            descriptor = os.open(
                parts[-1],
                access_flags
                | nofollow
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent_descriptor,
            )
        finally:
            os.close(parent_descriptor)
        owner_stat = os.fstat(owner)
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            os.close(descriptor)
            raise OSError("output leaf is not a regular file")
        if (opened_stat.st_dev, opened_stat.st_ino) != (owner_stat.st_dev, owner_stat.st_ino):
            os.close(descriptor)
            raise OSError("output leaf no longer names its lifecycle-owned object")
        return descriptor

    def _owned_file_descriptor(self, path: Path) -> int:
        """Return this lifecycle's exclusive descriptor for one output leaf.

        The descriptor identifies the leaf object the root created. This does not
        prove the directory object's physical pathname remains below ``root`` if an
        unrelated same-UID process renames a parent directory concurrently.
        """
        if self.closed:
            raise ValueError("secure output root is closed")
        parts = _output_parts_beneath(path, self.root)
        with self._owned_lock:
            descriptor = self._owned_descriptors.get(parts)
            if descriptor is not None:
                return descriptor
            parent_descriptor = _open_output_parent(self._descriptor, parts[:-1])
            nofollow = getattr(os, "O_NOFOLLOW", None)
            if nofollow is None:
                os.close(parent_descriptor)
                raise OSError("platform does not provide O_NOFOLLOW")
            expected = self._shared_leaf_ids.get(parts)
            flags = (
                os.O_RDWR | nofollow | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
            )
            if expected is None:
                flags |= os.O_CREAT | os.O_EXCL
            try:
                descriptor = os.open(parts[-1], flags, 0o600, dir_fd=parent_descriptor)
            finally:
                os.close(parent_descriptor)
            observed = os.fstat(descriptor)
            if not stat.S_ISREG(observed.st_mode):
                os.close(descriptor)
                raise OSError("output leaf is not a regular file")
            if expected is not None and (observed.st_dev, observed.st_ino) != expected:
                os.close(descriptor)
                raise OSError("shared output sink identity changed")
            self._owned_descriptors[parts] = descriptor
            return descriptor

    def open_owned_binary(self, path: Path) -> BinaryIO:
        """Open a fresh description for one lifecycle-owned mutable leaf.

        The root lock covers same-process threads. Callers use flock on the fresh
        file description to serialize processes; dup is not a lock because macOS
        associates duplicate descriptors with the same open-file description.
        """
        self._owned_lock.acquire()
        descriptor: int | None = None
        try:
            descriptor = self._open_fresh_owned_descriptor(path, os.O_RDWR)
            stream = os.fdopen(descriptor, "r+b")
            descriptor = None
            return cast("BinaryIO", _LockedStream(stream, self._owned_lock))
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            self._owned_lock.release()
            raise

    def read_owned_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        """Read the owned leaf by descriptor without resolving its current pathname."""
        descriptor = self._owned_file_descriptor(path)
        with self._owned_lock:
            size = os.fstat(descriptor).st_size
            chunks: list[bytes] = []
            offset = 0
            while offset < size:
                chunk = os.pread(descriptor, size - offset, offset)
                if not chunk:
                    break
                chunks.append(chunk)
                offset += len(chunk)
        return b"".join(chunks).decode(encoding)

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Create once, then update only this lifecycle's descriptor-owned leaf."""
        with self._owned_lock:
            descriptor = self._owned_file_descriptor(path)
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("secure output write made no forward progress")
                view = view[written:]
            os.fsync(descriptor)

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None:
        """Create once, then update this lifecycle's descriptor-owned text leaf."""
        self.write_bytes(path, data.encode(encoding))


class _LockRelease(Protocol):
    """The part of a lock used by the managed stream."""

    def release(self) -> None:
        """Release one lock acquisition."""


class _LockedStream:
    """Hold a lifecycle thread lock until its stream closes."""

    def __init__(self, stream: BinaryIO | TextIO, lock: _LockRelease) -> None:
        self._stream = stream
        self._lock = lock
        self._closed = False

    def __enter__(self) -> _LockedStream:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._stream.close()
        finally:
            self._closed = True
            self._lock.release()

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


_SECURE_OUTPUT_ROOT_ENV = "POLISYOS_TOOLS_SECURE_OUTPUT_ROOT"
_SECURE_OUTPUT_ROOT_ID_ENV = "POLISYOS_TOOLS_SECURE_OUTPUT_ROOT_ID"
_SECURE_OUTPUT_ROOT_FD_ENV = "POLISYOS_TOOLS_SECURE_OUTPUT_ROOT_FD"
_SECURE_OUTPUT_SHARED_LEAVES_ENV = "POLISYOS_TOOLS_SECURE_OUTPUT_SHARED_LEAVES"
_ACTIVE_SECURE_OUTPUT_ROOT: ContextVar[SecureOutputRoot | None] = ContextVar(
    "polisyos_active_secure_output_root", default=None
)
_INHERITED_SECURE_OUTPUT_ROOT: SecureOutputRoot | None = None
_INHERITED_SECURE_OUTPUT_LOCK = threading.Lock()


def _inherited_secure_output_root() -> SecureOutputRoot | None:
    """Attach the scoped output root passed through the canonical runner seam."""
    global _INHERITED_SECURE_OUTPUT_ROOT
    descriptor_text = os.environ.get(_SECURE_OUTPUT_ROOT_FD_ENV, "")
    if not descriptor_text:
        return None
    with _INHERITED_SECURE_OUTPUT_LOCK:
        if _INHERITED_SECURE_OUTPUT_ROOT is not None and not _INHERITED_SECURE_OUTPUT_ROOT.closed:
            return _INHERITED_SECURE_OUTPUT_ROOT
        root_text = os.environ.get(_SECURE_OUTPUT_ROOT_ENV, "")
        identity_text = os.environ.get(_SECURE_OUTPUT_ROOT_ID_ENV, "")
        shared_text = os.environ.get(_SECURE_OUTPUT_SHARED_LEAVES_ENV, "{}")
        try:
            device_text, inode_text = identity_text.split(":", maxsplit=1)
            shared_payload = json.loads(shared_text)
            if not isinstance(shared_payload, dict):
                raise ValueError("shared sink map is not an object")
            shared: dict[tuple[str, ...], tuple[int, int]] = {}
            for name, identity in shared_payload.items():
                parts = tuple(str(name).split("/"))
                if not parts or any(part in {"", ".", ".."} for part in parts):
                    raise ValueError("shared sink path is invalid")
                if not isinstance(identity, list) or len(identity) != 2:
                    raise ValueError("shared sink identity is invalid")
                if any(not isinstance(value, int) for value in identity):
                    raise ValueError("shared sink identity is invalid")
                shared[parts] = (identity[0], identity[1])
            root = SecureOutputRoot.from_inherited_descriptor(
                Path(root_text),
                int(descriptor_text),
                expected_identity=(int(device_text), int(inode_text)),
                shared_leaf_ids=shared,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise OSError("cannot attach inherited secure output scope") from error
        _INHERITED_SECURE_OUTPUT_ROOT = root
        atexit.register(root.close)
        return root


@contextmanager
def bind_secure_output_root(output_root: SecureOutputRoot) -> Iterator[SecureOutputRoot]:
    """Bind one already-open output root to a narrow synchronous producer scope.

    Args:
        output_root: Open root whose descriptor remains owned by its caller.

    Yields:
        The exact root object bound for consumers in this context.
    """
    if output_root.closed:
        raise ValueError("cannot bind a closed secure output root")
    token = _ACTIVE_SECURE_OUTPUT_ROOT.set(output_root)
    try:
        yield output_root
    finally:
        _ACTIVE_SECURE_OUTPUT_ROOT.reset(token)


def active_secure_output_root(root: Path | None = None) -> SecureOutputRoot | None:
    """Return the bound output root, optionally requiring a matching path."""
    output_root = _ACTIVE_SECURE_OUTPUT_ROOT.get()
    if output_root is None:
        output_root = _inherited_secure_output_root()
    if root is not None and output_root is not None:
        requested_root = _absolute_output_path(root, kind="output root")
        if output_root.root != requested_root:
            raise ValueError(
                f"active secure output root differs from requested root: {requested_root}"
            )
    return output_root


def write_scoped_report_text(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Write one report through the active native root or preserve ordinary atomic writes.

    An active recorder scope creates a new leaf through its pinned descriptor. Calls
    outside that explicit scope retain atomic_write_text replacement semantics.
    """
    output_root = active_secure_output_root()
    if output_root is None:
        atomic_write_text(path, data, encoding=encoding)
    else:
        output_root.write_text(path, data, encoding=encoding)


def _absolute_output_path(path: Path, *, kind: str) -> Path:
    raw = os.fspath(path)
    if not raw or "\x00" in raw:
        raise ValueError(f"{kind} must be a non-empty path without NUL bytes")
    return Path(os.path.abspath(raw))


def _directory_open_flags() -> int:
    directory = getattr(os, "O_DIRECTORY", None)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if directory is None or nofollow is None:
        raise OSError("platform does not provide O_DIRECTORY and O_NOFOLLOW")
    return os.O_RDONLY | directory | nofollow | getattr(os, "O_CLOEXEC", 0)


def _open_absolute_directory(path: Path) -> int:
    flags = _directory_open_flags()
    descriptor = os.open(os.sep, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _output_parts_beneath(path: Path, root: Path) -> tuple[str, ...]:
    absolute_path = _absolute_output_path(path, kind="output path")
    try:
        relative = absolute_path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"output path escaped its pinned root: {absolute_path}") from error
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise ValueError("output path must name a file below its pinned root")
    return relative.parts


def _open_output_parent(root_descriptor: int, components: tuple[str, ...]) -> int:
    flags = _directory_open_flags()
    descriptor = os.dup(root_descriptor)
    try:
        for component in components:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                with suppress(FileExistsError):
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


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
    except FileNotFoundError, NotADirectoryError:
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


class AdmittedPathError(ValueError):
    """An attempted filesystem operation resolves outside its admitted root."""


def resolve_admitted_path(path: Path, root: Path) -> Path:
    """Resolve a path and require it to remain beneath the owner's admitted root."""
    admitted_root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(admitted_root):
        raise AdmittedPathError(
            f"resolved path escapes admitted root: path={resolved}, root={admitted_root}"
        )
    return resolved


def admitted_is_file(path: Path, root: Path) -> bool:
    """Check file presence only after resolving beneath the admitted root."""
    return measured_is_file(resolve_admitted_path(path, root))


def admitted_is_dir(path: Path, root: Path) -> bool:
    """Check directory presence only after resolving beneath the admitted root."""
    return measured_is_dir(resolve_admitted_path(path, root))


def admitted_read_bytes(path: Path, root: Path) -> bytes:
    """Read exact bytes only after resolving beneath the admitted root."""
    return measured_read_bytes(resolve_admitted_path(path, root))


def admitted_read_text(path: Path, root: Path, *, encoding: str = "utf-8") -> str:
    """Read decoded text only after resolving beneath the admitted root."""
    return measured_read_text(resolve_admitted_path(path, root), encoding=encoding)


def admitted_file_digest(path: Path, root: Path) -> tuple[int, str]:
    """Stream a contained regular file and return its mode and SHA-256 digest."""
    resolved = resolve_admitted_path(path, root)
    digest = hashlib.sha256()
    size = 0
    try:
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        mode = resolved.stat().st_mode & 0o777
    except OSError as error:
        _record_file_read(
            resolved,
            "read_stream",
            status="unreadable",
            error=type(error).__name__,
        )
        raise
    hexdigest = digest.hexdigest()
    _record_file_read(
        resolved,
        "read_stream",
        status="read",
        bytes=size,
        sha256=hexdigest,
    )
    return mode, hexdigest
