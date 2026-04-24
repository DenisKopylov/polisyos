"""Bounded per-key resource registry for resilience wrappers."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


def _monotonic() -> float:
    return time.monotonic()


class BoundedResourceRegistry(Generic[T]):
    """LRU + TTL bounded registry for per-key resilience primitives."""

    def __init__(
        self,
        *,
        max_items: int = 256,
        ttl_seconds: float = 900.0,
    ) -> None:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._max_items = max_items
        self._ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        now = _monotonic()
        with self._lock:
            self._evict_expired_locked(now)
            cached = self._items.pop(key, None)
            if cached is not None:
                _created_at, value = cached
                self._items[key] = (now, value)
                return value

            value = factory()
            self._items[key] = (now, value)
            self._evict_overflow_locked()
            return value

    def snapshot(self) -> dict[str, T]:
        now = _monotonic()
        with self._lock:
            self._evict_expired_locked(now)
            return {key: value for key, (_stamp, value) in self._items.items()}

    def _evict_expired_locked(self, now: float) -> None:
        expired: list[str] = []
        for key, (last_used, _value) in self._items.items():
            if now - last_used > self._ttl_seconds:
                expired.append(key)
        for key in expired:
            self._items.pop(key, None)

    def _evict_overflow_locked(self) -> None:
        while len(self._items) > self._max_items:
            self._items.popitem(last=False)
