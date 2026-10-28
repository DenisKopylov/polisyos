"""Bounded per-key resource registry for resilience wrappers."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


def _monotonic() -> float:
    return time.monotonic()


_LOCAL_ADMISSION_OWNER = object()


class BoundedResourceRegistryCapacityError(RuntimeError):
    """Raised when all bounded registry slots carry mandatory live state."""

    def __init__(self, *args: object, _owner: object | None = None) -> None:
        super().__init__(*args)
        self._owner = _owner


class InvalidRateLimitError(ValueError):
    """Raised when local rate admission configuration is invalid."""

    def __init__(self, *args: object, _owner: object | None = None) -> None:
        super().__init__(*args)
        self._owner = _owner


def _capacity_refusal(message: str) -> BoundedResourceRegistryCapacityError:
    return BoundedResourceRegistryCapacityError(message, _owner=_LOCAL_ADMISSION_OWNER)


def _invalid_rate_refusal(message: str) -> InvalidRateLimitError:
    return InvalidRateLimitError(message, _owner=_LOCAL_ADMISSION_OWNER)


def _is_local_admission_error(error: Exception) -> bool:
    return isinstance(error, (BoundedResourceRegistryCapacityError, InvalidRateLimitError)) and (
        error._owner is _LOCAL_ADMISSION_OWNER
    )


@dataclass(slots=True)
class _Entry[T]:
    value: T
    last_used: float
    pins: int = 0


class BoundedResourceRegistry[T]:
    """Lease regulators without evicting an active or protected value.

    max_items bounds quiescent and admission-relevant entries independently.
    A lease pins the selected value under the same lock as TTL and LRU eviction
    before it can be used. Callers must use the value only inside the lease;
    release remains guaranteed on cancellation.
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
        self._items: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._lock = threading.Lock()

    @contextmanager
    def lease(self, key: str, factory: Callable[[], T]) -> Iterator[T]:
        """Pin one canonical value for the entire operation, or refuse admission."""
        now = _monotonic()
        with self._lock:
            self._evict_expired_locked(now)
            entry = self._items.get(key)
            protected = self._protected_count_locked()
            if entry is None:
                if protected >= self._max_items:
                    raise _capacity_refusal(f"bounded resource registry cannot admit key {key!r}")
                entry = _Entry(factory(), now)
                self._items[key] = entry
            elif (
                entry.pins == 0 and self._is_quiescent(entry.value) and protected >= self._max_items
            ):
                raise _capacity_refusal(f"bounded resource registry cannot activate key {key!r}")
            entry.pins += 1
            entry.last_used = now
            self._items.move_to_end(key)
            try:
                self._evict_overflow_locked()
            except BaseException:
                entry.pins -= 1
                raise

        try:
            yield entry.value
        finally:
            with self._lock:
                entry.pins -= 1
                entry.last_used = _monotonic()

    def _evict_expired_locked(self, now: float) -> None:
        expired: list[str] = []
        for key, entry in self._items.items():
            if (
                entry.pins == 0
                and now - entry.last_used > self._ttl_seconds
                and self._is_quiescent(entry.value)
            ):
                expired.append(key)
        for key in expired:
            self._items.pop(key, None)

    def _evict_overflow_locked(self) -> None:
        while self._quiescent_count_locked() > self._max_items:
            evicted = False
            for key, entry in self._items.items():
                if entry.pins == 0 and self._is_quiescent(entry.value):
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

    def _quiescent_count_locked(self) -> int:
        return sum(
            entry.pins == 0 and self._is_quiescent(entry.value) for entry in self._items.values()
        )

    def _protected_count_locked(self) -> int:
        return len(self._items) - self._quiescent_count_locked()
