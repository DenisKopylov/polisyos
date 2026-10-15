"""Public connectors components bridge module API."""

from __future__ import annotations

from dataclasses import dataclass, field

from polisyos.core.components import ComponentRegistry

from ._components_bootstrap import BootstrapTarget, bootstrap_components_into_registry
from ._registry_errors import ConnectorAlreadyRegisteredError as ConnectorAlreadyRegisteredError
from .registry import ConnectorRegistry


def _default_connector_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance(bootstrap=False)


@dataclass(slots=True)
class ComponentsBridgeError:
    """Components bridge error exception."""

    component_id: str
    message: str


@dataclass(slots=True)
class ComponentsBridgeReport:
    """Components bridge report data model."""

    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def bootstrap_connector_registry_from_components(
    components_index: ComponentRegistry,
    registry: BootstrapTarget | None = None,
    *,
    allow_dev_overrides: bool = True,
) -> ComponentsBridgeReport:
    """Bootstrap connector registry from components helper."""
    connector_registry = registry if registry is not None else _default_connector_registry()
    outcome = bootstrap_components_into_registry(
        components_index,
        connector_registry,
        allow_dev_overrides=allow_dev_overrides,
    )
    return ComponentsBridgeReport(
        registered=outcome.registered,
        duplicates=outcome.duplicates,
        errors=outcome.errors,
    )


__all__ = [
    "ComponentsBridgeError",
    "ComponentsBridgeReport",
    "bootstrap_connector_registry_from_components",
]
