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
