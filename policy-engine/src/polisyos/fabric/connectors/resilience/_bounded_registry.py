"""Bounded per-key resource registry for resilience wrappers."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar

T = TypeVar("T")


def _monotonic() -> float:
    return time.monotonic()


class BoundedResourceRegistryCapacityError(RuntimeError):
    """Raised when all bounded registry slots carry mandatory live state."""


class BoundedResourceRegistry(Generic[T]):
    """LRU + TTL registry that never discards live resilience state.

    ``max_items`` bounds the number of quiescent lookup entries and the number
    of protected entries independently. Protected entries remain in the same
    bounded map while their owner reports admission-relevant state, so a small
    amount of lookup pressure cannot reset a cooldown or circuit. If the
    finite protected budget is exhausted, a new non-quiescent key fails with a
    typed capacity error instead of creating an unbounded side map.
    """

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
        self._leases: dict[str, int] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        now = _monotonic()
        with self._lock:
            return self._get_or_create_locked(key, factory, now, owned=False)

    @contextmanager
    def lease(self, key: str, factory: Callable[[], T]) -> Iterator[T]:
        """Own one registered resource throughout an operation, even at neutral state.

        Ownership is acquired atomically with lookup and consumes the same finite
        protected-state budget. The lease count lives only while its map entry exists.
        """
        with self._lock:
            value = self._get_or_create_locked(key, factory, _monotonic(), owned=True)
            self._leases[key] = self._leases.get(key, 0) + 1
        try:
            yield value
        finally:
            with self._lock:
                remaining = self._leases[key] - 1
                if remaining:
                    self._leases[key] = remaining
                else:
                    del self._leases[key]
                self._evict_expired_locked(_monotonic())
                self._evict_overflow_locked()

    def _get_or_create_locked(
        self, key: str, factory: Callable[[], T], now: float, *, owned: bool
    ) -> T:
        self._evict_expired_locked(now)
        cached = self._items.get(key)
        if cached is not None:
            _created_at, value = cached
            if (
                owned
                and self._entry_is_quiescent(key, value)
                and self._protected_count_locked() >= self._max_items
            ):
                raise BoundedResourceRegistryCapacityError(
                    f"bounded resource registry cannot own protected key {key!r}"
                )
            self._items.pop(key)
            self._items[key] = (now, value)
            return value

        protected_count = self._protected_count_locked()
        if protected_count > self._max_items:
            raise BoundedResourceRegistryCapacityError(
                "bounded resource registry protected-state capacity exhausted"
            )
        if owned and protected_count >= self._max_items:
            raise BoundedResourceRegistryCapacityError(
                f"bounded resource registry cannot own protected key {key!r}"
            )

        value = factory()
        if protected_count >= self._max_items and (owned or not self._is_quiescent(value)):
            raise BoundedResourceRegistryCapacityError(
                f"bounded resource registry cannot admit protected key {key!r}"
            )
        self._items[key] = (now, value)
        if not owned:
            self._evict_overflow_locked()
        return value

    def snapshot(self) -> dict[str, T]:
        now = _monotonic()
        with self._lock:
            self._evict_expired_locked(now)
            return {key: value for key, (_stamp, value) in self._items.items()}

    def _evict_expired_locked(self, now: float) -> None:
        expired: list[str] = []
        for key, (last_used, value) in self._items.items():
            if now - last_used > self._ttl_seconds and self._entry_is_quiescent(key, value):
                expired.append(key)
        for key in expired:
            self._items.pop(key, None)

    def _evict_overflow_locked(self) -> None:
        while self._quiescent_count_locked() > self._max_items:
            evicted = False
            for key, (_last_used, value) in self._items.items():
                if self._entry_is_quiescent(key, value):
                    self._items.pop(key)
                    evicted = True
                    break
            if not evicted:
                return

    def _is_quiescent(self, value: T) -> bool:
        predicate = getattr(value, "is_quiescent", None)
        if predicate is None:
            return False
        return bool(predicate())

    def _entry_is_quiescent(self, key: str, value: T) -> bool:
        return not self._leases.get(key, 0) and self._is_quiescent(value)

    def _quiescent_count_locked(self) -> int:
        return sum(
            self._entry_is_quiescent(key, value) for key, (_stamp, value) in self._items.items()
        )

    def _protected_count_locked(self) -> int:
        return len(self._items) - self._quiescent_count_locked()
