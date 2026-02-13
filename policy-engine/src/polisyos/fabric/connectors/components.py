from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.connectors import ConnectorCapability

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import SourceConnector

FABRIC_CONNECTORS_API_VERSION = ">=2.2.0,<3.0.0"


@dataclass(frozen=True)
class ConnectorComponent:
    metadata: ComponentMetadata
    connector_class: type

    def create(self) -> type:
        return self.connector_class


def connector_component_from_class(
    connector_class: type["SourceConnector"],
    *,
    tags: list[str] | None = None,
) -> ConnectorComponent:
    connector_meta = connector_class.metadata
    connector_id = str(connector_meta.fully_qualified_id)

    metadata = ComponentMetadata(
        component_id=ComponentId.parse(connector_id),
        kind=ComponentKind.FABRIC_CONNECTOR,
        abi_targets={"fabric_connectors_api": FABRIC_CONNECTORS_API_VERSION},
        domains=[],
        jurisdictions=[],
        tags=sorted(set((tags or []) + [f"connector:{connector_meta.namespace}"])),
        capabilities=_to_component_capabilities(getattr(connector_class, "capabilities", ConnectorCapability(0))),
        deps=[],
        display_name=connector_meta.source_name,
        description=f"Fabric connector component for {connector_meta.source_organization}",
    )

    return ConnectorComponent(metadata=metadata, connector_class=connector_class)


def _to_component_capabilities(connector_capabilities: ConnectorCapability) -> Capability:
    caps = Capability.FABRIC_CONNECTOR

    if connector_capabilities & (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.INCREMENTAL_FETCH
        | ConnectorCapability.STREAMING
    ):
        caps |= Capability.FABRIC_QUERY

    return caps


def _load_builtin_connectors() -> Iterable[type["SourceConnector"]]:
    try:
        from .sources import (
            CKANCatalogConnector,
            CKANResourceConnector,
            EurostatConnector,
            OpendatasoftConnector,
            RestJsonConnector,
            SDMXSourceConnector,
            SocrataConnector,
            SPARQLConnector,
            UKONSConnector,
            WorldBankConnector,
        )
    except Exception:
        return ()

    return (
        WorldBankConnector,
        EurostatConnector,
        UKONSConnector,
        SDMXSourceConnector,
        CKANCatalogConnector,
        CKANResourceConnector,
        SocrataConnector,
        OpendatasoftConnector,
        SPARQLConnector,
        RestJsonConnector,
    )


def _build_builtin_components() -> list[ConnectorComponent]:
    components: list[ConnectorComponent] = []
    for connector_class in _load_builtin_connectors():
        namespace = str(getattr(getattr(connector_class, "metadata", object()), "namespace", ""))
        tags = ["builtin"]
        if namespace:
            tags.append(f"source:{namespace}")
        try:
            components.append(connector_component_from_class(connector_class, tags=tags))
        except Exception:
            continue
    return components


def _component_by_short_id(components: list[ConnectorComponent], short_id: str) -> ConnectorComponent | None:
    for component in components:
        if component.metadata.component_id.name == short_id:
            return component
    return None


_BUILTIN_COMPONENTS = _build_builtin_components()
world_bank_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "wdi")
eurostat_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "data")
ukons_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "datasets")
sdmx_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "source")
ckan_catalog_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "catalog")
ckan_resource_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "resource")
socrata_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "soda")
opendatasoft_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "ods")
sparql_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "endpoint")
rest_json_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "json")
__polisyos_components__ = list(_BUILTIN_COMPONENTS)

__all__ = [
    "FABRIC_CONNECTORS_API_VERSION",
    "ConnectorComponent",
    "connector_component_from_class",
    "world_bank_connector_component",
    "eurostat_connector_component",
    "ukons_connector_component",
    "sdmx_connector_component",
    "ckan_catalog_connector_component",
    "ckan_resource_connector_component",
    "socrata_connector_component",
    "opendatasoft_connector_component",
    "sparql_connector_component",
    "rest_json_connector_component",
    "__polisyos_components__",
]
