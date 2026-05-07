"""Example domain exposed through `polisyos.data_forge_domains`."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata


class CityBudgetDomain:
    """Tiny Data Forge domain with one deterministic fixture."""

    domain_id = "example.city_budget"

    def materialize(self) -> list[dict[str, int | str]]:
        return [
            {"city": "Example City", "program": "transit", "amount": 1200},
            {"city": "Example City", "program": "housing", "amount": 800},
        ]


@dataclass(frozen=True)
class DataForgeDomainExampleComponent:
    """Component provider for the example Data Forge domain."""

    metadata: ComponentMetadata

    def create(self) -> CityBudgetDomain:
        return CityBudgetDomain()


city_budget_domain_component = DataForgeDomainExampleComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("example.data_forge_domain.city_budget@1.0.0"),
        kind=ComponentKind.DATA_FORGE_DOMAIN,
        abi_targets={"data_forge_domain_api": ">=1.0.0,<2.0.0"},
        domains=["example"],
        jurisdictions=[],
        tags=["external-example", "data-forge"],
        capabilities=Capability.DATA_FORGE_DOMAIN,
        deps=[],
        display_name="Example City Budget Domain",
        description="Offline Data Forge domain example for extension authors.",
        provides=["example.city_budget.materialize"],
    )
)

__all__ = [
    "CityBudgetDomain",
    "DataForgeDomainExampleComponent",
    "city_budget_domain_component",
]
