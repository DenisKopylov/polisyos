from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_causal_methods_queryable():
    MethodRegistry.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    signatures = list(registry.query(namespace="causal.inference"))
    names = {sig.name for sig in signatures}
    assert names == {
        "synthetic_control",
        "difference_in_differences",
        "regression_discontinuity",
        "structural_time_series",
    }

