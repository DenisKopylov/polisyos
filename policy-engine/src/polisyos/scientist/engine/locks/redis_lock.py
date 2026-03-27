"""Distributed run lock backed by Redis."""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.engine.checkpoint import RunLockError

logger = get_logger(__name__)

# Lua script for atomic compare-and-delete.
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Lua script for atomic compare-and-extend TTL.
_EXTEND_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
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
            return current == self._token
        except Exception:  # noqa: BLE001
            return False

    def _start_heartbeat(self, ttl_ms: int) -> None:
        interval = max(ttl_ms // 3, 1000) / 1000.0

        def _extend() -> None:
            while not self._heartbeat_stop.wait(interval):
                try:
                    self._redis.eval(
                        _EXTEND_LUA, 1, self._key, self._token, str(ttl_ms)
                    )
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to extend lock TTL for %s", self._key)

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

                self._client = redis.Redis.from_url(
                    self._redis_url, decode_responses=True
                )
        return self._client

    def acquire(
        self, *, run_id: str, mode: str, force: bool = False
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
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(metadata, ensure_ascii=True, sort_keys=True)

        acquired = r.set(key, token, nx=True, px=ttl_ms)
        if not acquired:
            if force:
                # Force acquire: overwrite existing lock
                r.set(key, token, px=ttl_ms)
            else:
                existing = r.get(key)
                raise RunLockError(
                    f"run {run_id} is already locked. existing_token={existing}"
                )

        # Store metadata in a companion key so other processes can inspect.
        r.set(f"{key}:meta", payload, px=ttl_ms)

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
        except Exception:  # noqa: BLE001
            return False
