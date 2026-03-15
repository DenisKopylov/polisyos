from __future__ import annotations

from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot


def test_method_catalog_snapshot_contains_stable_entries() -> None:
    ensure_all_methods_registered()
    first = build_method_catalog_snapshot(run_id="R_catalog")
    second = build_method_catalog_snapshot(run_id="R_catalog")

    first_fqns = [entry.fqn for entry in first.entries]
    second_fqns = [entry.fqn for entry in second.entries]

    assert first_fqns
    assert first_fqns == second_fqns
    assert first.snapshot_id == second.snapshot_id


def test_method_catalog_snapshot_carries_causal_capability_posture() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    assert snapshot.causal_capability_hash
    assert snapshot.causal_runtime_posture

    symbolic_entry = next(
        entry for entry in snapshot.entries if "causal.transport.symbolic_identify@" in entry.fqn
    )
    assert symbolic_entry.causal_capability_requirements
    assert symbolic_entry.causal_available is False
    assert symbolic_entry.causal_disabled_reasons


def test_method_catalog_snapshot_includes_non_causal_families() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    fqns = {entry.fqn for entry in snapshot.entries}
    assert "econometrics.panel.fixed_effects@1.0.0" in fqns
    assert "econometrics.timeseries.vecm@1.0.0" in fqns
    assert "optimization.resource_lp@1.0.0" in fqns
    assert "optimization.linear.resource_lp@1.0.0" in fqns
    assert "optimization.integer.budget_milp@1.0.0" in fqns
    assert "optimization.io.leontief_io@1.0.0" in fqns
    assert "optimization.dynamic.dynamic_programming@1.0.0" in fqns
    assert "ml.regression.elastic_net@1.0.0" in fqns
    assert "ml.regression.gaussian_process@1.0.0" in fqns
    assert "ml.deep.tabular_transformer@1.0.0" in fqns
    assert "microsim.static.static_microsim@1.0.0" in fqns
    assert "microsim.policy.tax_benefit_calculator@1.0.0" in fqns
    assert "spatial.autocorrelation.moran_i@1.0.0" in fqns
    assert "network.community.community_detection@1.0.0" in fqns
    assert "bayesian.regression.linear_regression@1.0.0" in fqns
    assert "bayesian.timeseries.autoregression@1.0.0" in fqns
