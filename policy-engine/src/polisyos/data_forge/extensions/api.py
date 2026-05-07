"""Public contract marker for Data Forge domain plugins."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DataForgeDomainPlugin(Protocol):
    """Component-style plugin that exposes a Data Forge domain package."""

    @property
    def metadata(self) -> object:
        ...

    def create(self) -> object:
        ...


__all__ = ["DataForgeDomainPlugin"]
