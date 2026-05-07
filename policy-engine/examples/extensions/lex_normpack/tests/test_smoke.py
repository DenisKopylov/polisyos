from __future__ import annotations

from polisyos_lex_normpack_example import minimum_wage_normpack_component

from polisyos.core.components import ComponentKind


def test_minimum_wage_normpack_component_returns_static_pack() -> None:
    component = minimum_wage_normpack_component

    if component.metadata.kind is not ComponentKind.NORM_PACK_PROVIDER:
        raise AssertionError(component.metadata.kind)
    if component.metadata.abi_targets["ir_abi"] != "1.0":
        raise AssertionError(component.metadata.abi_targets)

    provider = component.create()
    norm_pack = provider.get_static_norm_pack(
        cas=None,
        jurisdiction="EX",
        domain="labor",
        as_of="2026-01-01",
    )

    if norm_pack.pack_id != "normpack.example.minimum_wage":
        raise AssertionError(norm_pack.pack_id)
    if norm_pack.norms[0].norm_id != "norm.example.minimum_wage.floor":
        raise AssertionError(norm_pack.norms[0].norm_id)
