"""Public connectors components module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from polisyos.common.logger import get_logger
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.connectors import ConnectorCapability

logger = get_logger(__name__)

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import SourceConnector

FABRIC_CONNECTORS_API_VERSION = ">=2.2.0,<3.0.0"


@dataclass(frozen=True)
class ConnectorComponent:
    """Connector component public type."""
    metadata: ComponentMetadata
    connector_class: type

    def create(self) -> type:
        return self.connector_class


def connector_component_from_class(
    connector_class: type["SourceConnector"],
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
            UNESCOUISConnector,
            UNPDConnector,
            UKONSConnector,
            WHOConnector,
            WorldBankConnector,
            WVSConnector,
        )
    except Exception:
        logger.debug(
            "Failed to import builtin connector classes", exc_info=True,
        )
        return ()

    return (
        WorldBankConnector,
        WVSConnector,
        EurostatConnector,
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
            logger.debug(
                "Failed to build component from connector class %s",
                getattr(connector_class, "__name__", connector_class), exc_info=True,
            )
            continue
    return components


def _component_by_short_id(components: list[ConnectorComponent], short_id: str) -> ConnectorComponent | None:
    for component in components:
        if component.metadata.component_id.name == short_id:
            return component
    return None


_BUILTIN_COMPONENTS = _build_builtin_components()
world_bank_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "wdi")
wvs_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "wave7")
eurostat_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "data")
ukons_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "datasets")
sdmx_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "source")
ckan_catalog_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "catalog")
ckan_resource_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "resource")
socrata_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "soda")
opendatasoft_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "ods")
sparql_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "endpoint")
rest_json_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "json")
who_connector_component = _component_by_short_id(_BUILTIN_COMPONENTS, "indicators")
unpd_connector_component = next(
    (
        component
        for component in _BUILTIN_COMPONENTS
        if component.metadata.component_id.namespace == "unpd"
    ),
    None,
)
unesco_uis_connector_component = next(
    (
        component
        for component in _BUILTIN_COMPONENTS
        if component.metadata.component_id.namespace == "unesco_uis"
    ),
    None,
)
__polisyos_components__ = list(_BUILTIN_COMPONENTS)

__all__ = [
    "FABRIC_CONNECTORS_API_VERSION",
    "ConnectorComponent",
    "connector_component_from_class",
    "world_bank_connector_component",
    "wvs_connector_component",
    "eurostat_connector_component",
    "ukons_connector_component",
    "sdmx_connector_component",
    "ckan_catalog_connector_component",
    "ckan_resource_connector_component",
    "socrata_connector_component",
    "opendatasoft_connector_component",
    "sparql_connector_component",
    "rest_json_connector_component",
    "who_connector_component",
    "unpd_connector_component",
    "unesco_uis_connector_component",
    "__polisyos_components__",
]
