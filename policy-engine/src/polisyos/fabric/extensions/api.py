"""Public contract marker for Fabric connector plugins."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FabricConnectorPlugin(Protocol):
    """Component-style plugin that creates a Fabric connector implementation."""

    @property
    def metadata(self) -> object:
        ...

    def create(self) -> object:
        ...


__all__ = ["FabricConnectorPlugin"]
