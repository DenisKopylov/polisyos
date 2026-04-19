"""Provide a thread-safe TTL cache with optional LRU eviction."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Callable, Generic, cast

from .protocol import K, T, V


@dataclass(frozen=True, slots=True)
class TTLCacheStats:
    """Expose TTL cache hit/miss/eviction/expiration counters."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0


class TTLCache(Generic[K, V]):
    """Thread-safe in-memory TTL cache with optional LRU size bound."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_size: int | None = None,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be >= 1 when provided")
        self._ttl_seconds = float(ttl_seconds)
        self._max_size = max_size
        self._time_fn = time_fn
        self._values: OrderedDict[K, tuple[V, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    @property
    def ttl_seconds(self) -> float:
        """Return the current expiry window in seconds."""
        return self._ttl_seconds

    @ttl_seconds.setter
    def ttl_seconds(self, value: float) -> None:
        """Update the expiry window and immediately purge stale entries."""
        with self._lock:
            self._ttl_seconds = float(value)
            self._purge_expired(now=self._time_fn())

    @property
    def max_size(self) -> int | None:
        """Return the current size cap, or `None` for time-only expiry."""
        return self._max_size

    @max_size.setter
    def max_size(self, value: int | None) -> None:
        """Update the size cap and evict oldest entries if needed."""
        if value is not None and value < 1:
            raise ValueError("max_size must be >= 1 when provided")
        with self._lock:
            self._max_size = value
            self._evict_to_limit()

    def get(self, key: K, default: T | None = None) -> V | T | None:
        """Return a non-expired value and refresh its LRU position."""
        now = self._time_fn()
        with self._lock:
            item = self._values.get(key)
            if item is None:
                self._misses += 1
                return default
            value, expires_at = item
            if now >= expires_at:
                self._values.pop(key, None)
                self._expirations += 1
                self._misses += 1
                return default
            self._values.move_to_end(key, last=True)
            self._hits += 1
            return value

    def set(self, key: K, value: V) -> None:
        """Store a value with a new expiry timestamp."""
        now = self._time_fn()
        expires_at = now + self._ttl_seconds
        with self._lock:
            self._values[key] = (value, expires_at)
            self._values.move_to_end(key, last=True)
            self._purge_expired(now=now)
            self._evict_to_limit()

    def pop(self, key: K, default: T | None = None) -> V | T | None:
        """Remove and return a non-expired value, or `default` if absent/stale."""
        with self._lock:
            item = self._values.pop(key, None)
            if item is None:
                return default
            value, expires_at = item
            if self._time_fn() >= expires_at:
                self._expirations += 1
                return default
            return value

    def delete(self, key: K) -> bool:
        """Remove a key and report whether an entry existed."""
        with self._lock:
            return self._values.pop(key, None) is not None

    def clear(self) -> None:
        """Drop all cached entries while preserving telemetry counters."""
        with self._lock:
            self._values.clear()

    def keys(self) -> list[K]:
        """Return all non-expired keys in LRU order."""
        now = self._time_fn()
        with self._lock:
            self._purge_expired(now=now)
            return list(self._values.keys())

    def values(self) -> list[V]:
        """Return all non-expired values in LRU order."""
        now = self._time_fn()
        with self._lock:
            self._purge_expired(now=now)
            return [item[0] for item in self._values.values()]

    def items(self) -> list[tuple[K, V]]:
        """Return all non-expired key/value pairs in LRU order."""
        now = self._time_fn()
        with self._lock:
            self._purge_expired(now=now)
            return [(key, value) for key, (value, _) in self._values.items()]

    def stats(self) -> TTLCacheStats:
        """Snapshot cache telemetry counters."""
        with self._lock:
            return TTLCacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                expirations=self._expirations,
            )

    def _purge_expired(self, *, now: float) -> int:
        removed = 0
        for key, (_value, expires_at) in list(self._values.items()):
            if now < expires_at:
                continue
            self._values.pop(key, None)
            self._expirations += 1
            removed += 1
        return removed

    def _evict_to_limit(self) -> int:
        if self._max_size is None:
            return 0
        removed = 0
        while len(self._values) > self._max_size:
            self._values.popitem(last=False)
            self._evictions += 1
            removed += 1
        return removed

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, Hashable):
            return False
        cache_key = cast("K", key)
        now = self._time_fn()
        with self._lock:
            item = self._values.get(cache_key)
            if item is None:
                return False
            _value, expires_at = item
            if now >= expires_at:
                self._values.pop(cache_key, None)
                self._expirations += 1
                return False
            return True

    def __len__(self) -> int:
        now = self._time_fn()
        with self._lock:
            self._purge_expired(now=now)
            return len(self._values)
