from __future__ import annotations

import importlib

import pytest

from polisyos.foundry.calibration.dp_ci import (
    CITestThresholdPolicy,
    CITestThresholdPolicySet,
    DPContext,
    ci_threshold_scope,
    effective_privacy_xi,
    required_n_chi2,
    required_n_kernel,
    resolve_ci_threshold_policy,
)


def test_calibration_facade_exports_canonical_ci_threshold_policy_set() -> None:
    calibration = importlib.import_module("polisyos.foundry.calibration")

    assert "CITestThresholdPolicySet" in calibration.__all__
    assert calibration.CITestThresholdPolicySet is CITestThresholdPolicySet


def test_effective_privacy_xi_shrinks_with_delta_penalty() -> None:
    pure = DPContext(mechanism="gaussian_counts", epsilon=1.0, delta=0.0)
    approximate = DPContext(mechanism="gaussian_counts", epsilon=1.0, delta=1e-6)

    assert effective_privacy_xi(approximate) < effective_privacy_xi(pure)


def test_required_n_bounds_grow_as_privacy_strengthens() -> None:
    weak_privacy = DPContext(mechanism="gaussian_counts", epsilon=2.0, delta=1e-6)
    strong_privacy = DPContext(mechanism="gaussian_counts", epsilon=0.3, delta=1e-6)

    chi2_weak = required_n_chi2(weak_privacy, m_cells=9, z_strata=2)
    chi2_strong = required_n_chi2(strong_privacy, m_cells=9, z_strata=2)
    kernel_weak = required_n_kernel(weak_privacy, dims=3)
    kernel_strong = required_n_kernel(strong_privacy, dims=3)

    assert chi2_strong.required_n > chi2_weak.required_n
    assert kernel_strong.required_n > kernel_weak.required_n


def _resolved_policy_set(*, epsilon: float = 0.7) -> CITestThresholdPolicySet:
    dp_context = {"mechanism": "laplace_counts", "epsilon": epsilon, "delta": 0.0}
    return CITestThresholdPolicySet(
        policies=(
            CITestThresholdPolicy(
                mc_bootstrap_B=1234,
                threshold_scope=ci_threshold_scope(
                    family="categorical_ci",
                    query_type="g2",
                    estimator="stratified_counts",
                    dp_context=dp_context,
                    readiness_target="diagnostic",
                ),
                threshold_registry_version=3,
            ),
        )
    )


def test_resolve_ci_threshold_policy_consumes_exact_resolved_policy() -> None:
    policy = resolve_ci_threshold_policy(
        family="categorical_ci",
        query_type="g2",
        estimator="stratified_counts",
        dp_context={"mechanism": "laplace_counts", "epsilon": 0.7, "delta": 0.0},
        resolved_policies=_resolved_policy_set(),
        n_bootstrap=2000,
    )

    assert policy.mc_bootstrap_B == 1234
    assert policy.threshold_scope["dp_mechanism"] == "laplace_counts"


def test_resolve_ci_threshold_policy_rejects_family_mismatch() -> None:
    with pytest.raises(ValueError, match="scope mismatch"):
        resolve_ci_threshold_policy(
            family="kernel_ci",
            query_type="g2",
            estimator="stratified_counts",
            dp_context={"mechanism": "laplace_counts", "epsilon": 0.7, "delta": 0.0},
            resolved_policies=_resolved_policy_set(),
        )


def test_resolve_ci_threshold_policy_rejects_epsilon_bucket_mismatch() -> None:
    with pytest.raises(ValueError, match="scope mismatch"):
        resolve_ci_threshold_policy(
            family="categorical_ci",
            query_type="g2",
            estimator="stratified_counts",
            dp_context={"mechanism": "laplace_counts", "epsilon": 1.5, "delta": 0.0},
            resolved_policies=_resolved_policy_set(epsilon=0.7),
        )


def test_resolve_ci_threshold_policy_uses_defaults_without_registry() -> None:
    policy = resolve_ci_threshold_policy(
        family="kernel_ci",
        query_type="hsic",
        estimator="permutation",
        dp_context=None,
        alpha=0.025,
        n_bootstrap=111,
    )

    assert policy.alpha_base == pytest.approx(0.025)
    assert policy.mc_bootstrap_B == 111
    assert policy.threshold_registry_version is None
