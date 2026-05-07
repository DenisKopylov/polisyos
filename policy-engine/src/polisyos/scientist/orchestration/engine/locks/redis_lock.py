"""Distributed run lock backed by Redis."""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.orchestration.engine.checkpoint import RunLockError
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

logger = get_logger(__name__)

try:
    from redis.exceptions import RedisError as _RedisError
except ImportError:  # pragma: no cover - optional dependency
    _RedisError = RuntimeError

_REDIS_LOCK_RUNTIME_ERRORS = (
    _RedisError,
    AttributeError,
    ConnectionError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)

# Lua script for atomic compare-and-delete.
_RELEASE_LUA = """
local value = redis.call("get", KEYS[1])
local token = value
if value then
    local ok, decoded = pcall(cjson.decode, value)
    if ok and decoded and decoded["token"] then
        token = decoded["token"]
    end
end
if token == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Lua script for atomic compare-and-extend TTL.
_EXTEND_LUA = """
local value = redis.call("get", KEYS[1])
local token = value
if value then
    local ok, decoded = pcall(cjson.decode, value)
    if ok and decoded and decoded["token"] then
        token = decoded["token"]
    end
end
if token == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

_FORCE_ACQUIRE_LUA = """
local value = redis.call("get", KEYS[1])
local token = value
if value then
    local ok, decoded = pcall(cjson.decode, value)
    if ok and decoded and decoded["token"] then
        token = decoded["token"]
    end
end
if token == ARGV[1] then
    redis.call("psetex", KEYS[1], ARGV[3], ARGV[2])
    return 1
else
    return 0
end
"""


@dataclass
class RedisLockHandle:
    """Handle for an acquired Redis-based distributed lock."""

    run_id: str
    metadata: dict[str, Any]
    _redis: Any = field(repr=False)
    _key: str = field(repr=False)
    _token: str = field(repr=False)
    _heartbeat_stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _heartbeat_thread: threading.Thread | None = field(default=None, repr=False)

    def release(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)
        self._redis.eval(_RELEASE_LUA, 1, self._key, self._token)

    def is_alive(self) -> bool:
        """Check if the Redis key still exists and our token matches."""
        try:
            current = self._redis.get(self._key)
            return _token_from_payload(current) == self._token
        except _REDIS_LOCK_RUNTIME_ERRORS as exc:
            emit_degraded_path(
                component="scientist.engine.locks.redis",
                operation="is_alive",
                reason="redis_lock_status_probe_failed",
                exc=exc,
                details={"run_id": self.run_id, "lock_key": self._key},
                log=logger,
            )
            return False

    def _start_heartbeat(self, ttl_ms: int) -> None:
        interval = max(ttl_ms // 3, 1000) / 1000.0

        def _extend() -> None:
            while not self._heartbeat_stop.wait(interval):
                try:
                    extended = self._redis.eval(_EXTEND_LUA, 1, self._key, self._token, str(ttl_ms))
                    if not extended:
                        self._heartbeat_stop.set()
                        break
                except _REDIS_LOCK_RUNTIME_ERRORS as exc:
                    emit_degraded_path(
                        component="scientist.engine.locks.redis",
                        operation="heartbeat_extend",
                        reason="redis_lock_heartbeat_failed",
                        exc=exc,
                        details={"run_id": self.run_id, "lock_key": self._key},
                        log=logger,
                    )
                    self._heartbeat_stop.set()
                    break

        t = threading.Thread(target=_extend, daemon=True, name=f"lock-hb-{self.run_id}")
        self._heartbeat_thread = t
        t.start()


class RedisRunLock:
    """Distributed run lock using Redis ``SET NX EX``.

    Satisfies ``RunLockBackend`` protocol.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        key_prefix: str = "polisyos:run_lock:",
        ttl_seconds: int = 3600,
        heartbeat: bool = True,
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._heartbeat = heartbeat
        self._client: Any = None
        self._init_lock = threading.Lock()

    def _redis(self) -> Any:
        if self._client is not None:
            return self._client
        with self._init_lock:
            if self._client is None:
                import redis

                self._client = redis.Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def acquire(
        self, *, run_id: str, mode: str, force: bool = False, owner_token: str | None = None
    ) -> RedisLockHandle:
        r = self._redis()
        key = f"{self._key_prefix}{run_id}"
        token = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
        ttl_ms = self._ttl_seconds * 1000

        metadata = {
            "run_id": run_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "mode": mode,
            "owner_token": token,
            "started_at": datetime.now(UTC).isoformat(),
        }
        payload = json.dumps(
            {
                "token": token,
                "metadata": metadata,
            },
            ensure_ascii=True,
            sort_keys=True,
        )

        acquired = r.set(key, payload, nx=True, px=ttl_ms)
        if not acquired:
            if force:
                if not owner_token:
                    raise RunLockError(f"run {run_id} force acquisition requires owner_token")
                forced = r.eval(
                    _FORCE_ACQUIRE_LUA,
                    1,
                    key,
                    owner_token,
                    payload,
                    str(ttl_ms),
                )
                if not forced:
                    raise RunLockError(
                        f"run {run_id} force acquisition rejected: owner token mismatch"
                    )
            else:
                existing = r.get(key)
                existing_token = _token_from_payload(existing)
                raise RunLockError(
                    f"run {run_id} is already locked. existing_token={existing_token}"
                )

        handle = RedisLockHandle(
            run_id=run_id,
            metadata=metadata,
            _redis=r,
            _key=key,
            _token=token,
        )
        if self._heartbeat:
            handle._start_heartbeat(ttl_ms)
        return handle

    def detect_stale(self, run_id: str) -> bool:
        """Check if the lock for *run_id* has expired (key missing = stale)."""
        r = self._redis()
        key = f"{self._key_prefix}{run_id}"
        try:
            ttl = r.pttl(key)
            # pttl returns -2 if key doesn't exist, -1 if no expiry set
            return ttl == -2
        except _REDIS_LOCK_RUNTIME_ERRORS as exc:
            emit_degraded_path(
                component="scientist.engine.locks.redis",
                operation="detect_stale",
                reason="redis_lock_stale_probe_failed",
                exc=exc,
                details={"run_id": run_id, "lock_key": key},
                log=logger,
            )
            return False


def _token_from_payload(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = str(raw)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return text
    if isinstance(payload, dict):
        token = payload.get("token")
        if token is not None:
            return str(token)
    return text
