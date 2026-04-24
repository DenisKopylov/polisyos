"""Define runtime protocols implemented by discovered plugin components."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .metadata import ComponentMetadata


@runtime_checkable
class Component(Protocol):
    """Discovered plugin contract that exposes metadata plus a host-side factory."""

    @property
    def metadata(self) -> ComponentMetadata:  # pragma: no cover - Protocol signature
        """Return static metadata consumed by discovery, compliance, and registry resolution."""
        ...

    def create(self) -> Any:  # pragma: no cover - Protocol signature
        """Instantiate the host-side implementation for this component."""
        ...


ComponentFactory = Callable[[], Component]


@runtime_checkable
class SupportsValidation(Protocol):
    """Optional protocol for components that can self-validate against host ABI."""

    def validate(
        self, host: HostAbi
    ) -> list[ComplianceIssue]:  # pragma: no cover - Protocol signature
        """Return component-authored compliance findings for the supplied host ABI."""
        ...


# Backward-compatibility alias kept for one release.
ComponentProvider = Component


if TYPE_CHECKING:  # pragma: no cover - type-only imports
    from .compliance import ComplianceIssue, HostAbi
