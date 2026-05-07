"""Public contract marker for runtime middleware plugins."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RuntimeMiddlewarePlugin(Protocol):
    """Component-style plugin that creates a runtime middleware factory or class."""

    @property
    def metadata(self) -> object:
        ...

    def create(self) -> object:
        ...


__all__ = ["RuntimeMiddlewarePlugin"]
