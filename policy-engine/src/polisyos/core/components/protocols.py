from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

from .metadata import ComponentMetadata


@runtime_checkable
class Component(Protocol):
    """Runtime component object that produces host-specific implementation."""

    @property
    def metadata(self) -> ComponentMetadata:  # pragma: no cover - Protocol signature
        ...

    def create(self) -> Any:  # pragma: no cover - Protocol signature
        ...


ComponentFactory = Callable[[], Component]


@runtime_checkable
class SupportsValidation(Protocol):
    def validate(self, host: "HostAbi") -> list["ComplianceIssue"]:  # pragma: no cover - Protocol signature
        ...


# Backward-compatibility alias kept for one release.
ComponentProvider = Component


if TYPE_CHECKING:  # pragma: no cover - type-only imports
    from .compliance import ComplianceIssue, HostAbi
