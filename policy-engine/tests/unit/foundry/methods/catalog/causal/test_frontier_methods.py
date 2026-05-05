from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_frontier_observational(seed: int = 41) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 240
    x = rng.normal(size=(n_obs, 3))
    latent = 0.7 * x[:, 0] + rng.normal(scale=0.6, size=n_obs)
    logits = 0.4 * x[:, 0] + 0.9 * latent
    treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
    treatment_proxy = latent + rng.normal(scale=0.3, size=n_obs)
    outcome_proxy = 0.8 * latent + 0.2 * x[:, 1] + rng.normal(scale=0.3, size=n_obs)
    outcome = 1.25 * treatment + 0.6 * x[:, 0] + latent + rng.normal(scale=0.35, size=n_obs)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": x,
        "treatment_proxy": treatment_proxy,
        "outcome_proxy": outcome_proxy,
    }


def _make_broken_proximal_observational(seed: int = 141) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 240
    x = rng.normal(size=(n_obs, 2))
    treatment = (rng.uniform(size=n_obs) > 0.5).astype(float)
    treatment_proxy = rng.normal(size=n_obs)
    outcome_proxy = rng.normal(size=n_obs)
    outcome = 0.6 * treatment + 1.8 * treatment_proxy + rng.normal(scale=0.25, size=n_obs)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": x,
        "treatment_proxy": treatment_proxy,
        "outcome_proxy": outcome_proxy,
    }


def _make_proximal_mediation_observational(seed: int = 91) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 180
    x = rng.normal(size=(n_obs, 2))
    latent = 0.6 * x[:, 0] + rng.normal(scale=0.5, size=n_obs)
    logits = 0.5 * x[:, 0] + 0.8 * latent
    treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
    mediator = 0.9 * treatment + 0.4 * x[:, 1] + 0.5 * latent + rng.normal(scale=0.3, size=n_obs)
    treatment_proxy = latent + rng.normal(scale=0.25, size=n_obs)
    outcome_proxy = 0.7 * latent + 0.2 * x[:, 0] + rng.normal(scale=0.25, size=n_obs)
    outcome = 0.8 * treatment + 0.9 * mediator + 0.3 * x[:, 0] + latent
    outcome = outcome + rng.normal(scale=0.35, size=n_obs)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "mediator": mediator,
        "covariates": x,
        "treatment_proxy": treatment_proxy,
        "outcome_proxy": outcome_proxy,
    }


def _line_weights(n_obs: int) -> np.ndarray:
    weights = np.zeros((n_obs, n_obs), dtype=float)
    for idx in range(n_obs):
        if idx > 0:
            weights[idx, idx - 1] = 1.0
        if idx + 1 < n_obs:
            weights[idx, idx + 1] = 1.0
    row_sums = weights.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return weights / row_sums


def _make_spatial_frontier_observational(seed: int = 211) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 120
    x = rng.normal(size=(n_obs, 2))
    weight_matrix = _line_weights(n_obs)
    latent = np.linalg.solve(np.eye(n_obs) - 0.22 * weight_matrix, rng.normal(size=n_obs))
    logits = 0.5 * x[:, 0] + 0.8 * latent
    treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
    wa = weight_matrix @ treatment
    treatment_proxy = np.column_stack(
        [
            latent + rng.normal(scale=0.25, size=n_obs),
            weight_matrix @ latent + rng.normal(scale=0.25, size=n_obs),
        ]
    )
    outcome_proxy = np.column_stack(
        [
            0.9 * latent + 0.2 * x[:, 1] + rng.normal(scale=0.25, size=n_obs),
            weight_matrix @ (0.8 * latent) + rng.normal(scale=0.25, size=n_obs),
        ]
    )
    outcome = np.linalg.solve(
        np.eye(n_obs) - 0.18 * weight_matrix,
        1.1 * treatment
        + 0.35 * wa
        + 0.4 * x[:, 0]
        + 0.7 * latent
        + rng.normal(scale=0.2, size=n_obs),
    )
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": x,
        "weight_matrix": weight_matrix,
        "treatment_proxy": treatment_proxy,
        "outcome_proxy": outcome_proxy,
        "spatial_proxy_specs": [
            {
                "proxy_variables": ["Z_ring2"],
                "weight_matrix_ref": "artifact://weights/W",
                "proxy_construction": "buffered_ring_lag",
                "lag_orders": [2, 3],
                "buffer_radius": 2,
                "time_mode": "contemporaneous",
                "allowed_roles": ["treatment_inducing"],
                "spillover_radius_claim": 1,
                "symmetry_or_direction": "undirected",
            },
            {
                "proxy_variables": ["W_ring3"],
                "weight_matrix_ref": "artifact://weights/W",
                "proxy_construction": "buffered_ring_lag",
                "lag_orders": [3, 4],
                "buffer_radius": 3,
                "time_mode": "contemporaneous",
                "allowed_roles": ["outcome_inducing"],
                "spillover_radius_claim": 1,
                "symmetry_or_direction": "undirected",
            },
        ],
    }


def _make_spatial_buffer_failure_observational(seed: int = 307) -> dict[str, np.ndarray]:
    payload = _make_spatial_frontier_observational(seed)
    payload["spatial_proxy_specs"] = [
        payload["spatial_proxy_specs"][0],
        {
            "proxy_variables": ["W_ring1"],
            "weight_matrix_ref": "artifact://weights/W",
            "proxy_construction": "ring_lag",
            "lag_orders": [1],
            "buffer_radius": 0,
            "time_mode": "contemporaneous",
            "allowed_roles": ["outcome_inducing"],
            "spillover_radius_claim": 1,
            "symmetry_or_direction": "undirected",
        },
    ]
    return payload


def _make_network_payload(seed: int = 73) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 120
    x = rng.normal(size=(n_obs, 2))
    treatment = (rng.uniform(size=n_obs) > 0.45).astype(float)
    adjacency = np.zeros((n_obs, n_obs), dtype=float)
    for idx in range(n_obs):
        adjacency[idx, (idx - 1) % n_obs] = 1.0
        adjacency[idx, (idx + 1) % n_obs] = 1.0
    exposure = adjacency @ treatment / 2.0
    outcome = 0.9 * treatment + 0.35 * exposure + 0.75 * treatment * x[:, 0] + 0.15 * x[:, 1]
    outcome = outcome + rng.normal(scale=0.2, size=n_obs)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": x,
        "adjacency_matrix": adjacency,
    }


def test_proximal_bridge_estimator_runs() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.proximal_bridge@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_frontier_observational(),
        params={"n_bootstrap": 60},
        seed=11,
    )

    assert result.output["report"].status == EstimationStatus.SUCCESS
    assert result.output["proximal_result"]["point_estimate"] > 0.4
    assert result.output["proximal_result"]["proxy_strength"] > 0.1
    bridge_report = result.output["bridge_plausibility_report"]
    assert bridge_report["severity"] in {"green", "yellow"}
    assert bridge_report["fallback_disposition"] in {
        "proceed_point_estimate",
        "proceed_with_warning",
    }
    assert bridge_report["residual_r"] >= 0.0


def test_proximal_bridge_estimator_blocks_infeasible_bridge_with_bounds() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.proximal_bridge@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_broken_proximal_observational(),
        params={"n_bootstrap": 60},
        seed=31,
    )

    assert result.output["report"].status == EstimationStatus.ASSUMPTION_FAILED
    assert result.output["proximal_result"] is None
    assert result.output["bridge_plausibility_report"]["severity"] == "red"
    assert (
        result.output["bounds_bundle"]["lower_bound"]
        < result.output["bounds_bundle"]["upper_bound"]
    )
    assert result.output["negative_certificate"]["blocking_type"] in {
        "bridge_equation_infeasible",
        "completeness_unlikely",
    }


def test_proximal_mediation_estimator_runs_when_oracle_gate_is_accepted() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.proximal_mediation@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_proximal_mediation_observational(),
        params={"oracle_gate": "accepted", "target_effect": "nie"},
        seed=19,
    )

    report = result.output["report"]
    payload = result.output["proximal_mediation_result"]
    assert report.status == EstimationStatus.SUCCESS
    assert payload is not None
    assert payload["target_effect"] == "nie"
    assert payload["point_estimate"] == report.point_estimate
    assert payload["bridge_plausibility_report"]["severity"] in {"green", "yellow"}
    assert result.output["negative_certificate"] is None
    assert result.output["bounds_bundle"] is None


def test_proximal_mediation_estimator_returns_bounds_when_oracle_gate_required() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.proximal_mediation@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_proximal_mediation_observational(),
        params={"oracle_gate": "required", "target_effect": "nie"},
        seed=23,
    )

    report = result.output["report"]
    assert report.status == EstimationStatus.ASSUMPTION_FAILED
    assert report.status_reason == "proximal_mediation_oracle_not_accepted"
    assert result.output["proximal_mediation_result"] is None
    assert result.output["negative_certificate"]["blocking_type"] == "completeness_unlikely"
    bounds = result.output["bounds_bundle"]
    assert bounds["estimand_type"] == "path_specific_effect"
    assert bounds["lower_bound"] < bounds["upper_bound"]


def test_spatial_proximal_bridge_estimator_runs() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.spatial_proximal_bridge@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_spatial_frontier_observational(),
        params={"model_family": "sdm", "confidence_level": 0.9},
        seed=13,
    )

    payload = result.output["spatial_proximal_result"]
    bridge_report = result.output["bridge_plausibility_report"]
    assert result.output["report"].status == EstimationStatus.SUCCESS
    assert payload is not None
    assert payload["ate_total"] == payload["point_estimate"]
    assert payload["tau"] > 0.0
    assert np.isfinite(payload["rho"])
    assert bridge_report["severity"] in {"green", "yellow"}
    assert bridge_report["buffer_exclusion_falsification"] is False
    assert result.output["negative_certificate"] is None
    assert result.output["bounds_bundle"] is None


def test_spatial_proximal_bridge_estimator_blocks_buffer_exclusion_failure() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.proximal.spatial_proximal_bridge@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_spatial_buffer_failure_observational(),
        params={"model_family": "sdm"},
        seed=29,
    )

    assert result.output["report"].status == EstimationStatus.ASSUMPTION_FAILED
    assert result.output["spatial_proximal_result"] is None
    assert result.output["bridge_plausibility_report"]["buffer_exclusion_falsification"] is True
    assert (
        result.output["bounds_bundle"]["lower_bound"]
        < result.output["bounds_bundle"]["upper_bound"]
    )
    assert result.output["negative_certificate"]["blocking_type"] == "bridge_equation_infeasible"


def test_distributional_treatment_effect_estimator_emits_quantile_shift() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.distributional.unconditional_qte@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_frontier_observational(),
        params={"n_bins": 24, "n_bootstrap": 60},
        seed=17,
    )

    payload = result.output["distributional_result"]
    assert result.output["report"].status == EstimationStatus.SUCCESS
    assert payload["wasserstein_distance"] > 0.0
    assert len(payload["quantile_shift"]["entries"]) >= 3


def test_network_heterogeneous_effect_estimator_reports_group_effects() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.interference.network_cate@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_network_payload(),
        params={"n_groups": 3, "n_bootstrap": 60},
        seed=23,
    )

    payload = result.output["network_hte_result"]
    assert result.output["report"].status == EstimationStatus.SUCCESS
    assert payload["point_estimate"] > 0.2
    assert len(payload["group_effects"]) >= 2
