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
        ...

    def set(self, key: K, value: V) -> None:
        ...

    def pop(self, key: K, default: T | None = None) -> V | T | None:
        ...

    def delete(self, key: K) -> bool:
        ...

    def clear(self) -> None:
        ...

    def __contains__(self, key: object) -> bool:
        ...

    def __len__(self) -> int:
        ...
