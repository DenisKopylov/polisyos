from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _identified_payload(seed: int = 17) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 520
    x = rng.normal(size=(n_obs, 2))
    treatment_prob = 1.0 / (1.0 + np.exp(-(0.25 + 0.45 * x[:, 0] - 0.20 * x[:, 1])))
    treatment = (rng.uniform(size=n_obs) < treatment_prob).astype(float)
    group_prob = 1.0 / (1.0 + np.exp(-(-0.30 + 1.00 * treatment + 0.55 * x[:, 0])))
    group = (rng.uniform(size=n_obs) < group_prob).astype(int)
    log_income = (
        1.3
        + 0.30 * x[:, 0]
        - 0.15 * x[:, 1]
        + 0.25 * treatment
        + 0.35 * group
        + 0.18 * treatment * group
        + rng.normal(scale=0.22, size=n_obs)
    )
    outcome = np.exp(log_income)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "group": group,
        "covariates": x,
    }


def _support_mismatch_payload(seed: int = 33) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 320
    x = rng.normal(size=(n_obs, 2))
    treatment = (rng.uniform(size=n_obs) > 0.5).astype(float)
    group = treatment.astype(int)
    log_income = (
        1.1 + 0.25 * x[:, 0] + 0.15 * treatment + 0.40 * group + rng.normal(scale=0.20, size=n_obs)
    )
    outcome = np.exp(log_income)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "group": group,
        "covariates": x,
    }


def test_endogenous_group_decomposition_runs_on_identified_payload() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.distributional.endogenous_group_decomposition@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_identified_payload(),
        params={"n_folds": 3, "functional": "theil_t"},
        seed=7,
    )

    report = result.output["report"]
    payload = result.output["decomposition_result"]

    assert report.status is EstimationStatus.SUCCESS
    assert payload["status"] == "identified"
    assert payload["functional"] == "theil_t"
    assert len(payload["laws"]) == 4
    total = payload["total_effect"]["point_estimate"]
    comp = payload["compositional_effect"]["point_estimate"]
    struct = payload["structural_effect"]["point_estimate"]
    assert abs(total - (comp + struct)) < 1.0e-8
    assert payload["negative_certificate"] is None
    assert result.output["bounds_bundle"] is None
    assert result.output["distributional_bounds_bundle"] is None


def test_endogenous_group_decomposition_runs_generalized_entropy_alpha() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.distributional.endogenous_group_decomposition@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_identified_payload(seed=21),
        params={"n_folds": 3, "functional": "generalized_entropy", "alpha": 2.0},
        seed=5,
    )

    report = result.output["report"]
    payload = result.output["decomposition_result"]

    assert report.status is EstimationStatus.SUCCESS
    assert payload["status"] == "identified"
    assert payload["functional"] == "generalized_entropy"
    assert payload["functional_parameters"]["generalized_entropy_alpha"] == 2.0
    assert payload["shapley_compositional_effect"] is not None
    assert payload["shapley_structural_effect"] is not None
    assert result.output["distributional_bounds_bundle"] is None


def test_endogenous_group_decomposition_can_target_trimmed_overlap() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.distributional.endogenous_group_decomposition@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_identified_payload(),
        params={
            "n_folds": 3,
            "functional": "theil_t",
            "trim_to_overlap": True,
            "min_group_probability": 0.30,
            "min_retained_fraction": 0.60,
        },
        seed=7,
    )

    report = result.output["report"]
    payload = result.output["decomposition_result"]

    assert report.status is EstimationStatus.SUCCESS
    assert payload["status"] == "trimmed"
    assert payload["reference_population"] == "overlap_trimmed_pooled_x"
    assert 0.60 <= payload["retained_fraction"] < 1.0
    assert result.output["bounds_bundle"] is None
    assert result.output["distributional_bounds_bundle"] is None
    assert result.output["negative_certificate"] is None
    assert result.output["warnings"]


def test_endogenous_group_decomposition_returns_bounds_on_support_mismatch() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("causal.distributional.endogenous_group_decomposition@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_support_mismatch_payload(),
        params={"n_folds": 3, "functional": "theil_t"},
        seed=9,
    )

    report = result.output["report"]
    payload = result.output["decomposition_result"]
    bounds = result.output["bounds_bundle"]
    distributional_bounds = result.output["distributional_bounds_bundle"]
    negative = result.output["negative_certificate"]

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert payload["status"] == "bounded"
    assert bounds is not None
    assert bounds["lower_bound"] <= bounds["upper_bound"]
    assert distributional_bounds is not None
    assert distributional_bounds["estimand_type"] == "endogenous_group_inequality_decomposition"
    assert distributional_bounds["metadata"]["effect_order"] == [
        "total",
        "compositional",
        "structural",
        "shapley_compositional",
        "shapley_structural",
    ]
    assert negative is not None
    assert negative["blocking_type"] == "support_mismatch"
