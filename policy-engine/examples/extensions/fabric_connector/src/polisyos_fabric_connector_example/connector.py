"""Example connector exposed through `polisyos.fabric_connectors`."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata


class ExampleRowsConnector:
    """Tiny connector implementation that returns committed example rows."""

    source_id = "example.fabric.local_rows"

    def fetch_preview(self) -> list[dict[str, int | str]]:
        return [
            {"country": "EX", "year": 2026, "value": 42},
            {"country": "EX", "year": 2027, "value": 43},
        ]


@dataclass(frozen=True)
class FabricConnectorExampleComponent:
    """Component provider for the example connector."""

    metadata: ComponentMetadata

    def create(self) -> ExampleRowsConnector:
        return ExampleRowsConnector()


local_rows_connector_component = FabricConnectorExampleComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("example.fabric_connector.local_rows@1.0.0"),
        kind=ComponentKind.FABRIC_CONNECTOR,
        abi_targets={"fabric_connectors_api": ">=2.2.0,<3.0.0"},
        domains=["example"],
        jurisdictions=[],
        tags=["external-example", "fabric"],
        capabilities=Capability.FABRIC_CONNECTOR | Capability.FABRIC_QUERY,
        deps=[],
        display_name="Example Local Rows Connector",
        description="Offline Fabric connector example for extension authors.",
        provides=["example.fabric.local_rows"],
    )
)

__all__ = [
    "ExampleRowsConnector",
    "FabricConnectorExampleComponent",
    "local_rows_connector_component",
]
