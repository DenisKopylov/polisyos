from __future__ import annotations

from polisyos_data_forge_domain_example import city_budget_domain_component

from polisyos.core.components import ComponentKind


def test_city_budget_domain_component_materializes_fixture() -> None:
    component = city_budget_domain_component

    if component.metadata.kind is not ComponentKind.DATA_FORGE_DOMAIN:
        raise AssertionError(component.metadata.kind)
    if component.metadata.abi_targets["data_forge_domain_api"] != ">=1.0.0,<2.0.0":
        raise AssertionError(component.metadata.abi_targets)

    domain = component.create()
    if domain.domain_id != "example.city_budget":
        raise AssertionError(domain.domain_id)
    if domain.materialize()[0]["program"] != "transit":
        raise AssertionError(domain.materialize())
