"""Public cache lru module API."""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic

from .protocol import K, T, V


@dataclass(frozen=True, slots=True)
class LRUCacheStats:
    """LRU cache stats public type."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCache(Generic[K, V]):
    """Thread-safe in-memory LRU cache."""

    def __init__(self, *, max_size: int | None = None) -> None:
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be >= 1 when provided")
        self._max_size = max_size
        self._values: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def max_size(self) -> int | None:
        return self._max_size

    @max_size.setter
    def max_size(self, value: int | None) -> None:
        if value is not None and value < 1:
            raise ValueError("max_size must be >= 1 when provided")
        with self._lock:
            self._max_size = value
            if value is not None:
                self.prune(value)

    def get(self, key: K, default: T | None = None) -> V | T | None:
        with self._lock:
            if key not in self._values:
                self._misses += 1
                return default
            value = self._values[key]
            self._values.move_to_end(key, last=True)
            self._hits += 1
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._values[key] = value
            self._values.move_to_end(key, last=True)
            self._evict_to_limit()

    def pop(self, key: K, default: T | None = None) -> V | T | None:
        with self._lock:
            return self._values.pop(key, default)

    def delete(self, key: K) -> bool:
        with self._lock:
            return self._values.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def prune(self, max_size: int) -> int:
        if max_size < 0:
            raise ValueError("max_size must be >= 0")
        removed = 0
        with self._lock:
            while len(self._values) > max_size:
                self._values.popitem(last=False)
                self._evictions += 1
                removed += 1
        return removed

    def keys(self) -> list[K]:
        with self._lock:
            return list(self._values.keys())

    def values(self) -> list[V]:
        with self._lock:
            return list(self._values.values())

    def items(self) -> list[tuple[K, V]]:
        with self._lock:
            return list(self._values.items())

    def stats(self) -> LRUCacheStats:
        with self._lock:
            return LRUCacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )

    def _evict_to_limit(self) -> None:
        if self._max_size is None:
            return
        while len(self._values) > self._max_size:
            self._values.popitem(last=False)
            self._evictions += 1

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._values

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)
