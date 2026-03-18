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
        "regression_discontinuity",
        "structural_time_series",
        "dowhy_identify_estimate",
    }
    did_names = {sig.name for sig in registry.query(namespace="causal.inference.did")}
    hte_names = {sig.name for sig in registry.query(namespace="causal.hte")}
    targeting_names = {sig.name for sig in registry.query(namespace="causal.targeting")}
    refutation_names = {sig.name for sig in registry.query(namespace="causal.refutation")}
    discovery_names = {sig.name for sig in registry.query(namespace="causal.discovery")}
    diagnostics_names = {sig.name for sig in registry.query(namespace="causal.diagnostics")}
    sensitivity_names = {sig.name for sig in registry.query(namespace="causal.sensitivity")}
    structural_names = {sig.name for sig in registry.query(namespace="causal.structural")}
    prior_names = {sig.name for sig in registry.query(namespace="causal.prior")}
    transport_names = {sig.name for sig in registry.query(namespace="causal.transport")}
    assert did_names.issuperset({"standard", "staggered", "callaway_santanna", "sun_abraham", "dechaisemartin", "borusyak_jaravel_spiess"})
    assert hte_names.issubset({"causal_forest", "double_ml", "meta_learner", "dr_learner", "r_learner"})
    assert targeting_names.issubset({"policy_tree"})
    assert "dowhy_refute" in refutation_names
    assert "parallel_trends_check" in diagnostics_names
    assert "pcmci_discovery" in discovery_names
    assert "pc_discovery" in discovery_names
    assert "fci_discovery" in discovery_names
    assert "ges_discovery" in discovery_names
    assert "dagma_discovery" in discovery_names
    assert "unified_causal_discovery" in discovery_names
    assert "sensitivity_metrics" in sensitivity_names
    assert "gcm_fit" in structural_names
    assert "gcm_query" in structural_names
    assert "twin_network_query" in structural_names
    assert "parameter_transfer" in structural_names
    assert {"build_literature_prior", "reconcile_causal_graph"}.issubset(prior_names)
    assert "check_transportability" in transport_names
    assert "symbolic_identify" in transport_names

    # Phase 1 new namespaces
    treatment_names = {sig.name for sig in registry.query(namespace="causal.treatment_effects")}
    assert treatment_names.issuperset({"aipw", "tmle", "ipw", "propensity_matching", "entropy_balancing", "cbps"})

    bounds_names = {sig.name for sig in registry.query(namespace="causal.bounds")}
    assert bounds_names.issuperset({"manski", "lee"})

    mediation_names = {sig.name for sig in registry.query(namespace="causal.mediation")}
    assert mediation_names.issuperset({"causal_mediation", "controlled_direct_effect", "natural_effects"})

    # Phase 1 L3 counterfactual namespace
    cf_names = {sig.name for sig in registry.query(namespace="causal.counterfactual")}
    assert cf_names.issuperset({"ncm_engine", "actual_causality", "hp_actual_cause", "path_specific_effects"})

    advanced_names = {sig.name for sig in registry.query(namespace="causal.advanced")}
    assert advanced_names.issuperset({"regression_kink", "bunching", "marginal_treatment_effect", "shift_share_iv"})
