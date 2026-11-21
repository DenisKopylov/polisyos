"""Independently schedule renewal of one existing SQLite control-job lease."""

from __future__ import annotations

import json
import math
import os
import select
import sqlite3
import subprocess
import sys
import sysconfig
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import monotonic

from .control_plane_store import ControlJobLeaseLostError, ControlPlaneStore

_DURATION_ENV = "POLISYOS_CONTROL_SQLITE_LEASE_RENEWAL_MAX_SECONDS"
_PEER_BOOTSTRAP = (
    "import sys; sys.path[:0] = sys.argv[1:4]; "
    "from polisyos.runtime.http.services._control_lease_pulse import _run_peer; "
    "sys.exit(_run_peer(sys.argv[4]))"
)


def _pipe_ready(fd: int, timeout_s: float) -> bool:
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    return bool(poller.poll(math.ceil(timeout_s * 1000)))


def _matches_database(path: Path, device: int, inode: int) -> bool:
    try:
        identity = path.stat()
    except OSError:
        return False
    return (identity.st_dev, identity.st_ino) == (device, inode)


@dataclass(frozen=True, slots=True)
class _SQLiteLeasePulseConfig:
    path: Path
    device: int
    inode: int
    duration_s: int

    @classmethod
    def from_store(
        cls, store: ControlPlaneStore, *, lease_seconds: int
    ) -> _SQLiteLeasePulseConfig | None:
        """Resolve the configured resource once before this worker starts."""
        raw_duration = os.environ.get(_DURATION_ENV)
        if raw_duration is None:
            return None
        try:
            duration_s = int(raw_duration)
            datetime.now(UTC) + timedelta(seconds=duration_s)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{_DURATION_ENV} requires a positive integer duration") from exc
        if duration_s < lease_seconds:
            raise ValueError(f"{_DURATION_ENV} must be at least one lease interval")
        path = store.sqlite_lease_renewal_path()
        if os.name != "posix" or path is None:
            raise ValueError(f"{_DURATION_ENV} requires a local POSIX SQLite control store")
        identity = path.stat()
        return cls(path=path, device=identity.st_dev, inode=identity.st_ino, duration_s=duration_s)

    def matches_database(self) -> bool:
        """Keep the worker and its peer bound to the originally configured resource."""
        return _matches_database(self.path, self.device, self.inode)


class _SQLiteLeasePulse:
    """Hold the sole lifetime pipe and process handle for one claimed attempt."""

    def __init__(
        self,
        *,
        config: _SQLiteLeasePulseConfig,
        job_id: str,
        worker_id: str,
        attempt: int,
        lease_seconds: int,
        heartbeat_interval_s: float,
        claimed_expires_at: datetime,
    ) -> None:
        self._config = config
        self._deadline = claimed_expires_at + timedelta(seconds=config.duration_s - lease_seconds)
        remaining_s = (self._deadline - datetime.now(UTC)).total_seconds()
        self._monotonic_deadline = monotonic() + min(config.duration_s, remaining_s)
        self._ready_timeout = min(
            (claimed_expires_at - datetime.now(UTC)).total_seconds(),
            max(1.0, 2.0 * heartbeat_interval_s),
        )
        if self._ready_timeout <= 0 or self._monotonic_deadline <= monotonic():
            raise ControlJobLeaseLostError("independent SQLite pulse missed its startup window")
        self._cancel_lock = Lock()

        payload = json.dumps(
            {
                "path": str(config.path),
                "device": config.device,
                "inode": config.inode,
                "parent_pid": os.getpid(),
                "job_id": job_id,
                "worker_id": worker_id,
                "attempt": attempt,
                "lease_seconds": lease_seconds,
                "interval_s": heartbeat_interval_s,
                "deadline": self._deadline.isoformat(),
                "monotonic_deadline": self._monotonic_deadline,
            }
        )
        self._process = subprocess.Popen(  # noqa: S603 - fixed Python entrypoint, no shell
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                _PEER_BOOTSTRAP,
                str(Path(__file__).resolve().parents[4]),
                sysconfig.get_path("purelib"),
                sysconfig.get_path("platlib"),
                payload,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            bufsize=0,
            env={},
        )

    def require_ready(self) -> None:
        """Wait for the first actual, committed lease renewal before running the handler."""
        output = self._process.stdout
        if output is None:
            raise ControlJobLeaseLostError("independent SQLite pulse readiness pipe is absent")
        if (
            not _pipe_ready(output.fileno(), self._ready_timeout)
            or output.read(1) != b"1"
            or not self.is_active()
        ):
            raise ControlJobLeaseLostError("independent SQLite pulse did not renew at startup")

    def is_active(self) -> bool:
        """Use process liveness only to refuse before the normal SQL owner check."""
        lifetime = self._process.stdin
        return (
            lifetime is not None
            and not lifetime.closed
            and self._process.poll() is None
            and monotonic() < self._monotonic_deadline
            and datetime.now(UTC) < self._deadline
            and self._config.matches_database()
        )

    def cancel(self) -> None:
        """Stop renewal even if a forked descendant inherited the lifetime pipe."""
        with self._cancel_lock:
            lifetime = self._process.stdin
            if lifetime is not None and not lifetime.closed:
                with suppress(BrokenPipeError):
                    lifetime.write(b"0")
                lifetime.close()

    def close(self) -> None:
        """Reap before allowing another dispatch or registering the worker idle."""
        self.cancel()
        try:
            self._process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                self._process.kill()
            self._process.wait(timeout=1)
        finally:
            if self._process.stdout is not None:
                self._process.stdout.close()


def _run_peer(raw: str) -> int:
    """Run the lease-only entrypoint with no service container or handler."""
    request = json.loads(raw)
    path = Path(request["path"])
    deadline = datetime.fromisoformat(request["deadline"])
    monotonic_deadline = request["monotonic_deadline"]
    lifetime = sys.stdin.fileno()

    def remains_active() -> bool:
        if (
            os.getppid() != request["parent_pid"]
            or monotonic() >= monotonic_deadline
            or datetime.now(UTC) >= deadline
            or _pipe_ready(lifetime, 0)
        ):
            return False
        return _matches_database(path, request["device"], request["inode"])

    if not remains_active():
        return 1
    store = ControlPlaneStore.open_existing_sqlite_for_lease_renewal(path)
    first = True
    retried_contention = False
    while remains_active():
        try:
            renewed = store.renew_job_lease(
                job_id=request["job_id"],
                worker_id=request["worker_id"],
                expected_attempt=request["attempt"],
                lease_seconds=request["lease_seconds"],
                still_active=remains_active,
                renewal_deadline=deadline,
            )
        except sqlite3.OperationalError as exc:
            code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
            if retried_contention or code not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise
            if not remains_active():
                return 0
            try:
                # The stock factory checks the persisted lease when invoked.
                store.job_execution_fence(
                    job_id=request["job_id"],
                    worker_id=request["worker_id"],
                    attempt=request["attempt"],
                )
            except ControlJobLeaseLostError:
                return 1
            retried_contention = True
            if _pipe_ready(lifetime, 0.25):
                break
            continue
        if not renewed:
            return 1
        retried_contention = False
        if first:
            sys.stdout.buffer.write(b"1")
            sys.stdout.buffer.flush()
            first = False
        pause = max(0.0, min(request["interval_s"], monotonic_deadline - monotonic()))
        if _pipe_ready(lifetime, pause):
            break
    return 0
