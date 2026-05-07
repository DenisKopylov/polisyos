from __future__ import annotations

from polisyos_fabric_connector_example import local_rows_connector_component

from polisyos.core.components import ComponentKind


def test_local_rows_connector_component_creates_offline_connector() -> None:
    component = local_rows_connector_component

    if component.metadata.kind is not ComponentKind.FABRIC_CONNECTOR:
        raise AssertionError(component.metadata.kind)
    if component.metadata.abi_targets["fabric_connectors_api"] != ">=2.2.0,<3.0.0":
        raise AssertionError(component.metadata.abi_targets)

    connector = component.create()
    if connector.source_id != "example.fabric.local_rows":
        raise AssertionError(connector.source_id)
    if connector.fetch_preview()[0] != {"country": "EX", "year": 2026, "value": 42}:
        raise AssertionError(connector.fetch_preview())
