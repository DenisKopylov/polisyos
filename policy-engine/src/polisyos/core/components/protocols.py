from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .metadata import ComponentMetadata


@runtime_checkable
class ComponentProvider(Protocol):
    """Minimal provider protocol for component instances."""

    @property
    def metadata(self) -> ComponentMetadata:  # pragma: no cover - Protocol signature
        ...

    def create(self) -> Any:  # pragma: no cover - Protocol signature
        ...
