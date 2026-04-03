"""Public registry generic module API."""
from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
T = TypeVar("T")
I = TypeVar("I", bound=Hashable)

Indexer = Callable[[T], I | Iterable[I] | None]


@dataclass(frozen=True, slots=True)
class GenericRegistrySnapshot(Generic[K, T]):
    """Generic registry snapshot data model."""
    keys: tuple[K, ...]
    values: tuple[T, ...]

    def as_dict(self) -> dict[K, T]:
        return dict(zip(self.keys, self.values, strict=True))


class GenericRegistry(Generic[K, T]):
    """
    Thread-safe generic registry with optional secondary indices.
    """

    def __init__(
        self,
        *,
        key_fn: Callable[[T], K],
        indexers: Mapping[str, Indexer] | None = None,
    ) -> None:
        self._key_fn = key_fn
        self._indexers: dict[str, Indexer] = dict(indexers or {})
        self._items: dict[K, T] = {}
        self._indices: dict[str, dict[Hashable, set[K]]] = {
            index_name: defaultdict(set) for index_name in self._indexers
        }
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_index_values(raw: Hashable | Iterable[Hashable] | None) -> list[Hashable]:
        if raw is None:
            return []
        if isinstance(raw, (str, bytes)):
            return [raw]
        if isinstance(raw, Iterable):
            values: list[Hashable] = []
            for item in raw:
                if item is not None:
                    values.append(item)
            return values
        return [raw]

    def _index_item(self, key: K, item: T) -> None:
        for index_name, extractor in self._indexers.items():
            values = self._normalize_index_values(extractor(item))
            bucket = self._indices[index_name]
            for value in values:
                bucket[value].add(key)

    def _deindex_item(self, key: K, item: T) -> None:
        for index_name, extractor in self._indexers.items():
            values = self._normalize_index_values(extractor(item))
            bucket = self._indices[index_name]
            for value in values:
                keys = bucket.get(value)
                if not keys:
                    continue
                keys.discard(key)
                if not keys:
                    bucket.pop(value, None)

    def register(self, item: T, *, override: bool = False) -> K:
        key = self._key_fn(item)
        with self._lock:
            existing = self._items.get(key)
            if existing is not None and not override:
                raise ValueError(f"Duplicate registry key: {key}")
            if existing is not None:
                self._deindex_item(key, existing)
            self._items[key] = item
            self._index_item(key, item)
        return key

    def unregister(self, key: K) -> T | None:
        with self._lock:
            item = self._items.pop(key, None)
            if item is None:
                return None
            self._deindex_item(key, item)
            return item

    def get(self, key: K) -> T | None:
        with self._lock:
            return self._items.get(key)

    def require(self, key: K, *, error_factory: Callable[[K], Exception] | None = None) -> T:
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                return item
        if error_factory is not None:
            raise error_factory(key)
        raise KeyError(key)

    def keys(self) -> list[K]:
        with self._lock:
            return list(self._items.keys())

    def values(self) -> list[T]:
        with self._lock:
            return list(self._items.values())

    def items(self) -> list[tuple[K, T]]:
        with self._lock:
            return list(self._items.items())

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            for index in self._indices.values():
                index.clear()

    def find(self, index_name: str, index_value: Hashable) -> list[T]:
        with self._lock:
            index = self._indices.get(index_name)
            if index is None:
                raise KeyError(f"Unknown secondary index '{index_name}'")
            keys = list(index.get(index_value, set()))
            return [self._items[key] for key in keys if key in self._items]

    def index_values(self, index_name: str) -> list[Hashable]:
        with self._lock:
            index = self._indices.get(index_name)
            if index is None:
                raise KeyError(f"Unknown secondary index '{index_name}'")
            return list(index.keys())

    def query(
        self,
        *,
        index_filters: Mapping[str, Hashable] | None = None,
        predicate: Callable[[T], bool] | None = None,
    ) -> list[T]:
        with self._lock:
            if not index_filters:
                keys = set(self._items.keys())
            else:
                key_sets: list[set[K]] = []
                for index_name, index_value in index_filters.items():
                    index = self._indices.get(index_name)
                    if index is None:
                        raise KeyError(f"Unknown secondary index '{index_name}'")
                    key_sets.append(set(index.get(index_value, set())))
                keys = set.intersection(*key_sets) if key_sets else set()

            rows: list[T] = []
            for key in keys:
                item = self._items.get(key)
                if item is None:
                    continue
                if predicate is not None and not predicate(item):
                    continue
                rows.append(item)
            return rows

    def snapshot(self) -> GenericRegistrySnapshot[K, T]:
        with self._lock:
            keys = tuple(self._items.keys())
            values = tuple(self._items.values())
        return GenericRegistrySnapshot(keys=keys, values=values)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._items)
