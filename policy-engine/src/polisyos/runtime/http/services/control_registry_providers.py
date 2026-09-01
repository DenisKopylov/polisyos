"""Injectable registry bundle for runtime control-plane services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.runtime.quality.capability_discovery import CapabilityDiscoveryProvider
    from polisyos.runtime.quality.capability_resolver import (
        CapabilityConformanceVerifier,
        CapabilityLiveOperationRegistry,
    )


class ConnectorRegistryLike(Protocol):
    """Connector registry surface required by runtime control APIs."""

    def query_entries(self, *args: Any, **kwargs: Any) -> Iterable[Any]: ...


class SourceProfileRegistryLike(Protocol):
    """Source-profile registry surface required by runtime control APIs."""

    def get(self, profile_id: str) -> Any | None: ...
    def list_all(self) -> list[Any]: ...
    def list_by_family(self, connector_family: str) -> list[Any]: ...


class BindingProfileRegistryLike(Protocol):
    """Binding-profile registry surface required by runtime control APIs."""

    def get(self, profile_id: str) -> Any | None: ...
    def list_all(self) -> list[Any]: ...


class ModelProfileRegistryLike(Protocol):
    """Model-profile registry surface required by runtime control APIs."""

    def list_all(self) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class ControlRegistryProviders:
    """Bundle registry dependencies so runtime control paths avoid singleton lookups."""

    connectors: ConnectorRegistryLike
    source_profiles: SourceProfileRegistryLike
    binding_profiles: BindingProfileRegistryLike
    model_profiles: ModelProfileRegistryLike
    gy_catalog_graph: Any | None = None
    capability_discovery_providers: tuple[CapabilityDiscoveryProvider, ...] = ()
    capability_live_operation_registry: CapabilityLiveOperationRegistry | None = None
    capability_conformance_verifier: CapabilityConformanceVerifier | None = None


ConnectorRegistryFactory = Callable[[], ConnectorRegistryLike]
SourceProfileRegistryFactory = Callable[[], SourceProfileRegistryLike]
BindingProfileRegistryFactory = Callable[[], BindingProfileRegistryLike]
ModelProfileRegistryFactory = Callable[[], ModelProfileRegistryLike]
GyCatalogGraphFactory = Callable[[], Any]


def resolve_control_registry_providers(
    *,
    connectors: ConnectorRegistryLike | None = None,
    source_profiles: SourceProfileRegistryLike | None = None,
    binding_profiles: BindingProfileRegistryLike | None = None,
    model_profiles: ModelProfileRegistryLike | None = None,
    gy_catalog_graph: Any | None = None,
    capability_discovery_providers: tuple[CapabilityDiscoveryProvider, ...] = (),
    capability_live_operation_registry: CapabilityLiveOperationRegistry | None = None,
    capability_conformance_verifier: CapabilityConformanceVerifier | None = None,
    connectors_factory: ConnectorRegistryFactory | None = None,
    source_profiles_factory: SourceProfileRegistryFactory | None = None,
    binding_profiles_factory: BindingProfileRegistryFactory | None = None,
    model_profiles_factory: ModelProfileRegistryFactory | None = None,
    gy_catalog_graph_factory: GyCatalogGraphFactory | None = None,
) -> ControlRegistryProviders:
    """Resolve runtime control registries once at the bootstrap boundary."""

    registry_factory_overridden = any(
        factory is not None
        for factory in (
            connectors_factory,
            source_profiles_factory,
            binding_profiles_factory,
            model_profiles_factory,
        )
    )
    if connectors is None:
        connectors = (
            connectors_factory() if connectors_factory is not None else _default_connectors()
        )
    if source_profiles is None:
        source_profiles = (
            source_profiles_factory()
            if source_profiles_factory is not None
            else _default_source_profiles()
        )
    if binding_profiles is None:
        binding_profiles = (
            binding_profiles_factory()
            if binding_profiles_factory is not None
            else _default_binding_profiles()
        )
    if model_profiles is None:
        model_profiles = (
            model_profiles_factory()
            if model_profiles_factory is not None
            else _default_model_profiles()
        )
    if gy_catalog_graph is None:
        if gy_catalog_graph_factory is not None:
            gy_catalog_graph = gy_catalog_graph_factory()
        elif not registry_factory_overridden:
            gy_catalog_graph = _default_gy_catalog_graph()
    resolved_discovery_providers = capability_discovery_providers
    if not registry_factory_overridden:
        if not any(
            provider.resource_kind == "method" for provider in resolved_discovery_providers
        ):
            resolved_discovery_providers = (
                *resolved_discovery_providers,
                _default_causal_method_capability_discovery_provider(),
            )
        if not any(
            provider.resource_kind == "agent" for provider in resolved_discovery_providers
        ):
            resolved_discovery_providers = (
                *resolved_discovery_providers,
                _default_scientist_capability_discovery_provider(),
            )
        if not any(
            provider.resource_kind == "source" for provider in resolved_discovery_providers
        ):
            resolved_discovery_providers = (
                *resolved_discovery_providers,
                _default_source_capability_discovery_provider(
                    connectors=connectors,
                    source_profiles=source_profiles,
                ),
            )
    return ControlRegistryProviders(
        connectors=connectors,
        source_profiles=source_profiles,
        binding_profiles=binding_profiles,
        model_profiles=model_profiles,
        gy_catalog_graph=gy_catalog_graph,
        capability_discovery_providers=resolved_discovery_providers,
        capability_live_operation_registry=capability_live_operation_registry,
        capability_conformance_verifier=capability_conformance_verifier,
    )


def _default_connectors() -> ConnectorRegistryLike:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return cast("ConnectorRegistryLike", ConnectorRegistry.get_instance())


def _default_source_profiles() -> SourceProfileRegistryLike:
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry

    return cast("SourceProfileRegistryLike", SourceProfileRegistry.get_instance())


def _default_binding_profiles() -> BindingProfileRegistryLike:
    from polisyos.fabric.connectors.bindings import BindingProfileRegistry

    return cast("BindingProfileRegistryLike", BindingProfileRegistry.get_instance())


def _default_model_profiles() -> ModelProfileRegistryLike:
    from polisyos.scientist.orchestration.llm.profiles import ModelProfileRegistry

    return cast("ModelProfileRegistryLike", ModelProfileRegistry.get_instance())


def _default_gy_catalog_graph() -> Any:
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph

    return build_slice0_fixture_catalog_graph()


def _default_scientist_capability_discovery_provider() -> CapabilityDiscoveryProvider:
    """Install the lazy Scientist owner without executing either registry factory."""
    from polisyos.runtime.quality.capability_discovery import (
        ScientistRegistryCapabilityDiscoveryProvider,
    )

    return ScientistRegistryCapabilityDiscoveryProvider(
        node_registry_factory=_default_scientist_node_registry,
        tool_registry_factory=_default_scientist_tool_registry,
        recall_measured=False,
    )


def _default_causal_method_capability_discovery_provider() -> CapabilityDiscoveryProvider:
    """Install the persisted release-index bridge without compiling on a request."""
    from polisyos.runtime.quality.capability_discovery import (
        CapabilityIndexCapabilityDiscoveryProvider,
        load_default_capability_index_release,
    )

    return CapabilityIndexCapabilityDiscoveryProvider(
        resource_kind="method",
        capability_index_loader=load_default_capability_index_release,
    )


def _default_source_capability_discovery_provider(
    *,
    connectors: ConnectorRegistryLike,
    source_profiles: SourceProfileRegistryLike,
) -> CapabilityDiscoveryProvider:
    """Install the lazy, paired connector/source-profile snapshot producer."""
    from polisyos.runtime.quality.capability_discovery import (
        ConnectorSourceProfileSnapshotProducer,
    )

    return ConnectorSourceProfileSnapshotProducer(
        connectors=connectors,
        source_profiles=source_profiles,
    )


def _default_scientist_node_registry() -> object:
    """Discover the public NodeRegistry only on the first agent query."""
    from polisyos.scientist import discover_scientist_nodes

    registry, report = discover_scientist_nodes(include_dev_scan=False)
    reasons = tuple(
        f"scientist_node_registry_discovery_error:{message}"
        for message in (*report.discovery_errors, *report.errors)
    )
    return registry, reasons


def _default_scientist_tool_registry() -> object:
    """Build the public ToolRegistry only on the first agent query."""
    from polisyos.scientist import (
        KnowledgeToolkit,
        build_knowledge_tool_registry,
    )

    return build_knowledge_tool_registry(KnowledgeToolkit())


__all__ = [
    "BindingProfileRegistryLike",
    "ConnectorRegistryLike",
    "ControlRegistryProviders",
    "GyCatalogGraphFactory",
    "ModelProfileRegistryLike",
    "SourceProfileRegistryLike",
    "resolve_control_registry_providers",
]
