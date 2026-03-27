"""File-based run lock using ``fcntl.flock()`` (Unix/macOS only)."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.scientist.engine.checkpoint import RUN_LOCK_FILENAME, RunLockError


@dataclass
class FcntlLockHandle:
    """Handle for an acquired fcntl-based file lock."""

    run_id: str
    path: Path
    fd: int
    metadata: dict[str, Any]

    def release(self) -> None:
        try:
            import fcntl
        except Exception as exc:  # pragma: no cover
            raise RunLockError("fcntl is unavailable on this platform") from exc
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)

    def is_alive(self) -> bool:
        """Check if the lock is still actively held (fd is valid and PID exists)."""
        try:
            os.fstat(self.fd)
        except OSError:
            return False
        pid = self.metadata.get("pid")
        if pid is not None:
            return _pid_exists(int(pid))
        return True


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock_metadata(lock_path: Path) -> dict[str, Any] | None:
    if not lock_path.exists():
        return None
    try:
        raw = lock_path.read_text("utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


class FcntlRunLock:
    """Run lock backed by ``fcntl.flock()``.

    Satisfies ``RunLockBackend`` protocol.
    """

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def acquire(
        self, *, run_id: str, mode: str, force: bool = False
    ) -> FcntlLockHandle:
        try:
            import fcntl
        except Exception as exc:  # pragma: no cover
            raise RunLockError("fcntl is unavailable on this platform") from exc

        self._run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._run_dir / RUN_LOCK_FILENAME
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            current = _read_lock_metadata(lock_path)
            if force and current is not None:
                same_host = current.get("hostname") == socket.gethostname()
                stale = (
                    same_host
                    and isinstance(current.get("pid"), int)
                    and not _pid_exists(int(current["pid"]))
                )
                if stale:
                    pass  # Stale metadata; lock still held by OS
            os.close(fd)
            holder = ""
            if current:
                holder = (
                    f" holder_pid={current.get('pid')}"
                    f" holder_host={current.get('hostname')}"
                    f" holder_mode={current.get('mode')}"
                )
            raise RunLockError(
                f"run {run_id} is already active.{holder}"
            ) from exc

        metadata = {
            "run_id": run_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "mode": mode,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(
            fd,
            json.dumps(metadata, ensure_ascii=True, sort_keys=True).encode("utf-8"),
        )
        os.fsync(fd)

        return FcntlLockHandle(
            run_id=run_id, path=lock_path, fd=fd, metadata=metadata
        )

    def detect_stale(self, run_id: str) -> bool:
        """Check if a lock file for *run_id* is stale (owner PID dead)."""
        lock_path = self._run_dir / RUN_LOCK_FILENAME
        meta = _read_lock_metadata(lock_path)
        if meta is None:
            return False
        same_host = meta.get("hostname") == socket.gethostname()
        pid = meta.get("pid")
        if same_host and isinstance(pid, int):
            return not _pid_exists(pid)
        return False
