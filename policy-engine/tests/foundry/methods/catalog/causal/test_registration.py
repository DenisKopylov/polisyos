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
        "dowhy_identify_estimate",
    }
    hte_names = {sig.name for sig in registry.query(namespace="causal.hte")}
    targeting_names = {sig.name for sig in registry.query(namespace="causal.targeting")}
    refutation_names = {sig.name for sig in registry.query(namespace="causal.refutation")}
    discovery_names = {sig.name for sig in registry.query(namespace="causal.discovery")}
    sensitivity_names = {sig.name for sig in registry.query(namespace="causal.sensitivity")}
    structural_names = {sig.name for sig in registry.query(namespace="causal.structural")}
    prior_names = {sig.name for sig in registry.query(namespace="causal.prior")}
    transport_names = {sig.name for sig in registry.query(namespace="causal.transport")}
    assert hte_names.issubset({"causal_forest", "double_ml", "meta_learner"})
    assert targeting_names.issubset({"policy_tree"})
    assert "dowhy_refute" in refutation_names
    assert "pcmci_discovery" in discovery_names
    assert "pc_discovery" in discovery_names
    assert "fci_discovery" in discovery_names
    assert "ges_discovery" in discovery_names
    assert "sensitivity_metrics" in sensitivity_names
    assert "gcm_fit" in structural_names
    assert "gcm_query" in structural_names
    assert "parameter_transfer" in structural_names
    assert {"build_literature_prior", "reconcile_causal_graph"}.issubset(prior_names)
    assert "check_transportability" in transport_names
