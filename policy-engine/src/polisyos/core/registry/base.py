"""Provide an extensible thread-safe registry facade over `GenericRegistry`."""
from __future__ import annotations

import threading
from collections.abc import Callable, Hashable, Mapping
from enum import Enum
from typing import Generic, TypeVar

from .generic import GenericRegistry, GenericRegistrySnapshot, Indexer

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class DuplicateDecision(str, Enum):
    """Duplicate handling strategy for :meth:`BaseRegistry.register`."""

    REJECT = "reject"
    KEEP_EXISTING = "keep_existing"
    REPLACE = "replace"


class BaseRegistry(Generic[K, V]):
    """
    Shared thread-safe registry facade with extension hooks.

    Hooks:
    - ``validate_duplicate``: decide what to do when ``key`` already exists.
    - ``on_register``: invoked after successful registration.
    - ``on_unregister``: invoked after successful unregistration.
    """

    def __init__(
        self,
        *,
        key_fn: Callable[[V], K],
        indexers: Mapping[str, Indexer[V]] | None = None,
    ) -> None:
        self._key_fn = key_fn
        self._entries = GenericRegistry[K, V](key_fn=key_fn, indexers=indexers)
        self._lock = threading.RLock()

    def validate_duplicate(
        self,
        *,
        key: K,
        existing: V,
        incoming: V,
    ) -> DuplicateDecision:
        return DuplicateDecision.REJECT

    def duplicate_error(
        self,
        *,
        key: K,
        existing: V,
        incoming: V,
    ) -> Exception:
        return ValueError(f"Duplicate registry key: {key}")

    def on_register(
        self,
        *,
        key: K,
        value: V,
        replaced: V | None,
    ) -> None:
        return None

    def on_unregister(self, *, key: K, value: V) -> None:
        return None

    def register(self, value: V, *, override: bool = False) -> K:
        key = self._key_fn(value)
        with self._lock:
            existing = self._entries.get(key)
            should_override = override
            if existing is not None and not should_override:
                decision = self.validate_duplicate(
                    key=key,
                    existing=existing,
                    incoming=value,
                )
                if decision == DuplicateDecision.KEEP_EXISTING:
                    return key
                if decision == DuplicateDecision.REPLACE:
                    should_override = True
                else:
                    raise self.duplicate_error(
                        key=key,
                        existing=existing,
                        incoming=value,
                    )

            stored_key = self._entries.register(value, override=should_override)
            replaced = existing if (existing is not None and should_override) else None
            self.on_register(key=stored_key, value=value, replaced=replaced)
            return stored_key

    def unregister(self, key: K) -> V | None:
        with self._lock:
            removed = self._entries.unregister(key)
            if removed is not None:
                self.on_unregister(key=key, value=removed)
            return removed

    def clear(self) -> None:
        with self._lock:
            for key in list(self._entries.keys()):
                removed = self._entries.unregister(key)
                if removed is not None:
                    self.on_unregister(key=key, value=removed)

    def get(self, key: K) -> V | None:
        return self._entries.get(key)

    def require(self, key: K, *, error_factory: Callable[[K], Exception] | None = None) -> V:
        return self._entries.require(key, error_factory=error_factory)

    def keys(self) -> list[K]:
        return self._entries.keys()

    def values(self) -> list[V]:
        return self._entries.values()

    def items(self) -> list[tuple[K, V]]:
        return self._entries.items()

    def find(self, index_name: str, index_value: Hashable) -> list[V]:
        return self._entries.find(index_name, index_value)

    def index_values(self, index_name: str) -> list[Hashable]:
        return self._entries.index_values(index_name)

    def query(
        self,
        *,
        index_filters: Mapping[str, Hashable] | None = None,
        predicate: Callable[[V], bool] | None = None,
    ) -> list[V]:
        return self._entries.query(index_filters=index_filters, predicate=predicate)

    def snapshot(self) -> GenericRegistrySnapshot[K, V]:
        return self._entries.snapshot()

    @property
    def count(self) -> int:
        return self._entries.count

    def __contains__(self, key: K) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        return self.count
