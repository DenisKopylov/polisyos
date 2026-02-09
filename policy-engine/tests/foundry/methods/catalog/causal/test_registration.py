from __future__ import annotations

from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_causal_methods_queryable():
    MethodRegistry.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    infer_names = {sig.name for sig in registry.query(namespace="causal.inference")}
    assert infer_names == {
        "synthetic_control",
        "difference_in_differences",
        "regression_discontinuity",
        "structural_time_series",
    }
    hte_names = {sig.name for sig in registry.query(namespace="causal.hte")}
    targeting_names = {sig.name for sig in registry.query(namespace="causal.targeting")}
    assert hte_names.issubset({"causal_forest", "double_ml", "meta_learner"})
    assert targeting_names.issubset({"policy_tree"})
