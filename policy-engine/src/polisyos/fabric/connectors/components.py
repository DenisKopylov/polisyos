"""Public connectors components module API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.connectors import ConnectorCapability

logger = get_logger(__name__)

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import SourceConnector

    __polisyos_components__: tuple[ConnectorComponent, ...]
    ckan_catalog_connector_component: ConnectorComponent | None
    ckan_resource_connector_component: ConnectorComponent | None
    eurostat_connector_component: ConnectorComponent | None
    event_stream_connector_component: ConnectorComponent | None
    file_tabular_connector_component: ConnectorComponent | None
    geojson_connector_component: ConnectorComponent | None
    graphql_connector_component: ConnectorComponent | None
    object_storage_connector_component: ConnectorComponent | None
    opendatasoft_connector_component: ConnectorComponent | None
    rest_json_connector_component: ConnectorComponent | None
    sdmx_connector_component: ConnectorComponent | None
    socrata_connector_component: ConnectorComponent | None
    sparql_connector_component: ConnectorComponent | None
    sql_query_connector_component: ConnectorComponent | None
    ukons_connector_component: ConnectorComponent | None
    unesco_uis_connector_component: ConnectorComponent | None
    unpd_connector_component: ConnectorComponent | None
    who_connector_component: ConnectorComponent | None
    world_bank_connector_component: ConnectorComponent | None
    wvs_connector_component: ConnectorComponent | None

FABRIC_CONNECTORS_API_VERSION = ">=2.2.0,<3.0.0"


@dataclass(frozen=True)
class ConnectorComponent:
    """Connector component public type."""

    metadata: ComponentMetadata
    connector_class: type

    def create(self) -> type:
        return self.connector_class


def connector_component_from_class(
    connector_class: type[SourceConnector],
    *,
    tags: list[str] | None = None,
) -> ConnectorComponent:
    """Connector component from class helper."""
    connector_meta = connector_class.metadata
    connector_id = str(connector_meta.fully_qualified_id)

    metadata = ComponentMetadata(
        component_id=ComponentId.parse(connector_id),
        kind=ComponentKind.FABRIC_CONNECTOR,
        abi_targets={"fabric_connectors_api": FABRIC_CONNECTORS_API_VERSION},
        domains=[],
        jurisdictions=[],
        tags=sorted(set((tags or []) + [f"connector:{connector_meta.namespace}"])),
        capabilities=_to_component_capabilities(
            getattr(connector_class, "capabilities", ConnectorCapability(0))
        ),
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


def _load_builtin_connectors() -> Iterable[type[SourceConnector]]:
    try:
        from .sources import (
            CKANCatalogConnector,
            CKANResourceConnector,
            EurostatConnector,
            EventStreamConnector,
            FileTabularConnector,
            GeoJSONConnector,
            GraphQLConnector,
            ObjectStorageConnector,
            OpendatasoftConnector,
            RestJsonConnector,
            SDMXSourceConnector,
            SocrataConnector,
            SPARQLConnector,
            SQLQueryConnector,
            UKONSConnector,
            UNESCOUISConnector,
            UNPDConnector,
            WHOConnector,
            WorldBankConnector,
            WVSConnector,
        )
    except Exception:
        logger.debug(
            "Failed to import builtin connector classes",
            exc_info=True,
        )
        return ()

    return (
        WorldBankConnector,
        WVSConnector,
        EurostatConnector,
        FileTabularConnector,
        ObjectStorageConnector,
        SQLQueryConnector,
        GraphQLConnector,
        GeoJSONConnector,
        EventStreamConnector,
        UKONSConnector,
        SDMXSourceConnector,
        CKANCatalogConnector,
        CKANResourceConnector,
        SocrataConnector,
        OpendatasoftConnector,
        SPARQLConnector,
        RestJsonConnector,
        WHOConnector,
        UNPDConnector,
        UNESCOUISConnector,
    )


def _build_builtin_components() -> tuple[ConnectorComponent, ...]:
    components: list[ConnectorComponent] = []
    for connector_class in _load_builtin_connectors():
        namespace = str(getattr(getattr(connector_class, "metadata", object()), "namespace", ""))
        tags = ["builtin"]
        if namespace:
            tags.append(f"source:{namespace}")
        try:
            components.append(connector_component_from_class(connector_class, tags=tags))
        except Exception:
            logger.debug(
                "Failed to build component from connector class %s",
                getattr(connector_class, "__name__", connector_class),
                exc_info=True,
            )
            continue
    return tuple(components)


def _component_by_short_id(
    components: Iterable[ConnectorComponent],
    short_id: str,
) -> ConnectorComponent | None:
    for component in components:
        if component.metadata.component_id.name == short_id:
            return component
    return None


@lru_cache(maxsize=1)
def _builtin_components() -> tuple[ConnectorComponent, ...]:
    return _build_builtin_components()


def _component_by_namespace(namespace: str) -> ConnectorComponent | None:
    for component in _builtin_components():
        if component.metadata.component_id.namespace == namespace:
            return component
    return None


_COMPONENT_EXPORTS: dict[str, str] = {
    "world_bank_connector_component": "wdi",
    "wvs_connector_component": "wave7",
    "eurostat_connector_component": "data",
    "ukons_connector_component": "datasets",
    "sdmx_connector_component": "source",
    "ckan_catalog_connector_component": "catalog",
    "ckan_resource_connector_component": "resource",
    "socrata_connector_component": "soda",
    "opendatasoft_connector_component": "ods",
    "sparql_connector_component": "endpoint",
    "rest_json_connector_component": "json",
    "who_connector_component": "indicators",
    "file_tabular_connector_component": "tabular",
    "object_storage_connector_component": "blob",
    "sql_query_connector_component": "query",
    "graphql_connector_component": "api",
    "geojson_connector_component": "features",
    "event_stream_connector_component": "jsonl",
}


def __getattr__(name: str) -> object:
    if name in {"_BUILTIN_COMPONENTS", "__polisyos_components__"}:
        return _builtin_components()
    if name in _COMPONENT_EXPORTS:
        return _component_by_short_id(_builtin_components(), _COMPONENT_EXPORTS[name])
    if name == "unpd_connector_component":
        return _component_by_namespace("unpd")
    if name == "unesco_uis_connector_component":
        return _component_by_namespace("unesco_uis")
    raise AttributeError(name)


__all__ = [
    "FABRIC_CONNECTORS_API_VERSION",
    "ConnectorComponent",
    "__polisyos_components__",
    "ckan_catalog_connector_component",
    "ckan_resource_connector_component",
    "connector_component_from_class",
    "eurostat_connector_component",
    "event_stream_connector_component",
    "file_tabular_connector_component",
    "geojson_connector_component",
    "graphql_connector_component",
    "object_storage_connector_component",
    "opendatasoft_connector_component",
    "rest_json_connector_component",
    "sdmx_connector_component",
    "socrata_connector_component",
    "sparql_connector_component",
    "sql_query_connector_component",
    "ukons_connector_component",
    "unesco_uis_connector_component",
    "unpd_connector_component",
    "who_connector_component",
    "world_bank_connector_component",
    "wvs_connector_component",
]
