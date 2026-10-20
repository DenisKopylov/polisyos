from __future__ import annotations


def test_funnel_facade_preserves_ir_uncertainty_type_export() -> None:
    from polisyos.ir import UncertaintyType as IRUncertaintyType
    from polisyos.scientist.methods.search.funnel import UncertaintyType

    assert UncertaintyType is IRUncertaintyType
