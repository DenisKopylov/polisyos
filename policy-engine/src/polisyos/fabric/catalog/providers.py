"""Injectable provider bundle for catalog and connector-discovery flows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from polisyos.fabric.connectors.profiles import SourceProfileRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry


@dataclass(frozen=True, slots=True)
class CatalogProviders:
    """Bundle catalog-facing registries so callers avoid ad hoc singleton lookups."""

    connector_registry: ConnectorRegistry
    source_profiles: SourceProfileRegistry


CatalogRegistryFactory = Callable[[], ConnectorRegistry]
CatalogProfilesFactory = Callable[[], SourceProfileRegistry]


def resolve_catalog_providers(
    *,
    connector_registry: ConnectorRegistry | None = None,
    source_profiles: SourceProfileRegistry | None = None,
    connector_registry_factory: CatalogRegistryFactory | None = None,
    source_profiles_factory: CatalogProfilesFactory | None = None,
) -> CatalogProviders:
    """Resolve catalog providers, defaulting only at the outer boundary."""

    if connector_registry is None:
        connector_registry = (
            connector_registry_factory()
            if connector_registry_factory is not None
            else _default_connector_registry()
        )
    if source_profiles is None:
        source_profiles = (
            source_profiles_factory()
            if source_profiles_factory is not None
            else _default_source_profiles()
        )
    return CatalogProviders(
        connector_registry=connector_registry,
        source_profiles=source_profiles,
    )


def _default_connector_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance()


def _default_source_profiles() -> SourceProfileRegistry:
    return SourceProfileRegistry.get_instance()


__all__ = ["CatalogProviders", "resolve_catalog_providers"]
