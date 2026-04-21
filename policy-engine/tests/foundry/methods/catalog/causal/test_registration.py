from __future__ import annotations

import builtins
import sys

from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal._registry_boot import register_causal_methods
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
    proximal_names = {sig.name for sig in registry.query(namespace="causal.proximal")}
    distributional_names = {sig.name for sig in registry.query(namespace="causal.distributional")}
    interference_names = {sig.name for sig in registry.query(namespace="causal.interference")}
    operator_names = {sig.name for sig in registry.query(namespace="causal.operator")}
    assert did_names.issuperset({"standard", "staggered", "callaway_santanna", "sun_abraham", "dechaisemartin", "borusyak_jaravel_spiess"})
    assert hte_names.issubset({"causal_forest", "causal_bcf", "forest_dr", "double_ml", "meta_learner", "dr_learner", "r_learner"})
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
    assert "proximal_bridge" in proximal_names
    assert "proximal_mediation" in proximal_names
    assert "unconditional_qte" in distributional_names
    assert {"partial", "network_aipw", "spatial", "bipartite", "network_cate"}.issubset(interference_names)
    assert {
        "cme_krr",
        "operator_r_learner",
        "kiv",
        "proximal_minimax",
        "apply_probe",
        "export_basis",
        "unsupported_target",
    }.issubset(operator_names)

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


def test_register_causal_methods_keeps_g_computation_when_sklearn_missing(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sklearn" or name.startswith("sklearn."):
            raise ModuleNotFoundError("No module named 'sklearn'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for module_name in (
        "polisyos.foundry.methods.catalog.causal._sklearn_compat",
        "polisyos.foundry.methods.catalog.causal.g_computation",
        "polisyos.foundry.methods.catalog.causal.g_estimation",
    ):
        sys.modules.pop(module_name, None)

    names = {method.signature.name for method in register_causal_methods()}
    assert {"parametric_g_formula", "ice_g_formula", "ltmle"} <= names
