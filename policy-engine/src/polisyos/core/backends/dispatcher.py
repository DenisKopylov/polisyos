"""Public backends dispatcher module API."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, Iterable, Mapping, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class BackendNotAvailableError(RuntimeError, Generic[K]):
    """Backend not available error exception."""
    backend: K
    reason: str | None = None

    def __str__(self) -> str:
        if self.reason:
            return f"Backend {self.backend!r} is not available: {self.reason}"
        return f"Backend {self.backend!r} is not available"


class BackendDispatcher(Generic[K, V]):
    """
    Generic backend resolver with optional lazy factory.

    The dispatcher caches resolved handlers and is safe to share across threads.
    """

    def __init__(
        self,
        *,
        factory: Callable[[K], V] | None = None,
        availability_check: Callable[[V], bool] | None = None,
    ) -> None:
        self._factory = factory
        self._availability_check = availability_check
        self._handlers: dict[K, V] = {}
        self._lock = threading.RLock()

    def register(self, backend: K, handler: V) -> None:
        with self._lock:
            self._handlers[backend] = handler

    def register_many(self, mapping: Mapping[K, V] | Iterable[tuple[K, V]]) -> None:
        with self._lock:
            if isinstance(mapping, Mapping):
                self._handlers.update(mapping)
            else:
                for backend, handler in mapping:
                    self._handlers[backend] = handler

    def resolve(self, backend: K) -> V:
        with self._lock:
            existing = self._handlers.get(backend)
            if existing is not None:
                return existing

            if self._factory is None:
                raise BackendNotAvailableError(backend, reason="not registered")

            try:
                created = self._factory(backend)
            except ModuleNotFoundError as exc:
                raise BackendNotAvailableError(backend, reason=str(exc)) from exc
            except BackendNotAvailableError:
                raise

            if self._availability_check is not None and not self._availability_check(created):
                raise BackendNotAvailableError(backend, reason="availability check failed")

            self._handlers[backend] = created
            return created

    def available_backends(self) -> frozenset[K]:
        with self._lock:
            return frozenset(self._handlers.keys())

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
