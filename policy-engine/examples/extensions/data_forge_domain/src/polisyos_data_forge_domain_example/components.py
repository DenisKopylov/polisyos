"""Local dev-scan declaration for the example Data Forge domain."""

from .domain import city_budget_domain_component

__polisyos_components__ = [city_budget_domain_component]

__all__ = ["__polisyos_components__"]
