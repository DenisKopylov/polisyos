from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable

from polisyos.common.logger import get_logger
from polisyos.common.timestamps import parse_iso_datetime, to_iso_utc, utc_now
from polisyos.core.canon import content_hash

logger = get_logger(__name__)


@runtime_checkable
class _HasRoot(Protocol):
    @property
    def root(self) -> Path: ...

def _serialize_datetime(value: datetime | None) -> str | None:
    return to_iso_utc(value) if value is not None else None


@dataclass(frozen=True)
class FreshnessRuntimeState:
    last_checked_at: datetime | None = None
    last_refresh_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    failed_refresh_count: int = 0


@dataclass(frozen=True)
class FreshnessRefreshLock:
    path: Path
    fd: int

    def release(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.fd)
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()

    def __enter__(self) -> "FreshnessRefreshLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.release()


class FreshnessStateStore:
    """Mutable sidecar store for freshness runtime state.

    CAS artifacts remain immutable. Operational data used to prevent refresh storms
    is persisted under `<cas_root>/freshness_state`.
    """

    def __init__(self, cas: _HasRoot | Path) -> None:
        if isinstance(cas, Path):
            root_path = cas
        else:
            maybe_root = getattr(cas, "root", None)
            root_path = maybe_root if isinstance(maybe_root, Path) else Path(cas)

        self._base = root_path / "freshness_state"
        self._states = self._base / "states"
        self._locks = self._base / "locks"
        self._states.mkdir(parents=True, exist_ok=True)
        self._locks.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(*parts: str) -> str:
        normalized = "|".join(part.strip() for part in parts if part and part.strip())
        if not normalized:
            return "global"
        return content_hash(normalized)

    def _state_path(self, key: str) -> Path:
        return self._states / f"{key}.json"

    def _lock_path(self, key: str) -> Path:
        return self._locks / f"{key}.lock"

    def load(self, key: str) -> FreshnessRuntimeState:
        path = self._state_path(key)
        if not path.exists():
            return FreshnessRuntimeState()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            logger.debug("Failed to parse freshness state file %s", path)
            return FreshnessRuntimeState()
        if not isinstance(payload, dict):
            return FreshnessRuntimeState()
        return FreshnessRuntimeState(
            last_checked_at=parse_iso_datetime(payload.get("last_checked_at")),
            last_refresh_attempt_at=parse_iso_datetime(payload.get("last_refresh_attempt_at")),
            next_retry_at=parse_iso_datetime(payload.get("next_retry_at")),
            failed_refresh_count=max(0, int(payload.get("failed_refresh_count", 0) or 0)),
        )

    def save(self, key: str, state: FreshnessRuntimeState) -> None:
        payload = {
            "last_checked_at": _serialize_datetime(state.last_checked_at),
            "last_refresh_attempt_at": _serialize_datetime(state.last_refresh_attempt_at),
            "next_retry_at": _serialize_datetime(state.next_retry_at),
            "failed_refresh_count": int(state.failed_refresh_count),
        }
        path = self._state_path(key)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temp.replace(path)

    def record_check(self, key: str, *, now: datetime | None = None) -> FreshnessRuntimeState:
        now_utc = now or utc_now()
        current = self.load(key)
        updated = FreshnessRuntimeState(
            last_checked_at=now_utc,
            last_refresh_attempt_at=current.last_refresh_attempt_at,
            next_retry_at=current.next_retry_at,
            failed_refresh_count=current.failed_refresh_count,
        )
        self.save(key, updated)
        return updated

    def record_refresh_attempt(
        self,
        key: str,
        *,
        now: datetime | None = None,
    ) -> FreshnessRuntimeState:
        now_utc = now or utc_now()
        current = self.load(key)
        updated = FreshnessRuntimeState(
            last_checked_at=now_utc,
            last_refresh_attempt_at=now_utc,
            next_retry_at=current.next_retry_at,
            failed_refresh_count=current.failed_refresh_count,
        )
        self.save(key, updated)
        return updated

    def record_refresh_success(
        self,
        key: str,
        *,
        now: datetime | None = None,
    ) -> FreshnessRuntimeState:
        now_utc = now or utc_now()
        updated = FreshnessRuntimeState(
            last_checked_at=now_utc,
            last_refresh_attempt_at=now_utc,
            next_retry_at=None,
            failed_refresh_count=0,
        )
        self.save(key, updated)
        return updated

    def record_refresh_failure(
        self,
        key: str,
        *,
        cooldown_seconds: int,
        now: datetime | None = None,
    ) -> FreshnessRuntimeState:
        now_utc = now or utc_now()
        current = self.load(key)
        cooldown = max(0, int(cooldown_seconds))
        next_retry = now_utc + timedelta(seconds=cooldown) if cooldown > 0 else now_utc
        updated = FreshnessRuntimeState(
            last_checked_at=now_utc,
            last_refresh_attempt_at=now_utc,
            next_retry_at=next_retry,
            failed_refresh_count=current.failed_refresh_count + 1,
        )
        self.save(key, updated)
        return updated

    def acquire_lock(self, key: str, *, ttl_seconds: int = 600) -> FreshnessRefreshLock | None:
        path = self._lock_path(key)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

        def _try_open() -> FreshnessRefreshLock | None:
            try:
                fd = os.open(path, flags, 0o600)
            except FileExistsError:
                return None
            payload = {
                "key": key,
                "pid": os.getpid(),
                "acquired_at": _serialize_datetime(utc_now()),
            }
            os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
            os.fsync(fd)
            return FreshnessRefreshLock(path=path, fd=fd)

        lock = _try_open()
        if lock is not None:
            return lock

        if ttl_seconds > 0 and path.exists():
            age = utc_now().timestamp() - path.stat().st_mtime
            if age > float(ttl_seconds):
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()
                return _try_open()
        return None


__all__ = [
    "FreshnessRefreshLock",
    "FreshnessRuntimeState",
    "FreshnessStateStore",
]
