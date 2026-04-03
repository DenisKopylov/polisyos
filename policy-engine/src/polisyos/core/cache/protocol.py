"""Define the minimal mutable cache protocol shared by cache backends."""
from __future__ import annotations

from collections.abc import Hashable
from typing import Protocol, TypeVar, runtime_checkable

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")
T = TypeVar("T")


@runtime_checkable
class Cache(Protocol[K, V]):
    """Generic mutable cache contract."""

    def get(self, key: K, default: T | None = None) -> V | T | None:
        """Return a cached value or `default` when the key is absent."""
        ...

    def set(self, key: K, value: V) -> None:
        """Store or overwrite a cached value."""
        ...

    def pop(self, key: K, default: T | None = None) -> V | T | None:
        """Remove a cached key and return its value or `default`."""
        ...

    def delete(self, key: K) -> bool:
        """Remove a key and report whether an entry existed."""
        ...

    def clear(self) -> None:
        """Drop all cached entries."""
        ...

    def __contains__(self, key: object) -> bool:
        ...

    def __len__(self) -> int:
        ...
