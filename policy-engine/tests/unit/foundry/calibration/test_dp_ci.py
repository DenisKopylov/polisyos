from __future__ import annotations

import pytest
from polisyos.foundry.calibration.dp_ci import (
    DPContext,
    effective_privacy_xi,
    required_n_chi2,
    required_n_kernel,
    resolve_ci_threshold_policy,
)
from polisyos.scientist.search.judge_thresholds import (
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
)


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


def test_resolve_ci_threshold_policy_prefers_dp_specific_entry(tmp_path) -> None:
    registry = JudgeThresholdRegistry(tmp_path / "judge_thresholds")
    registry.record(
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=1234,
            direction="min",
            rationale="unit test override",
            benchmark_source="unit_test",
            scope_family="categorical_ci",
            scope_query_type="g2",
            scope_estimator="stratified_counts",
            scope_dp_mechanism="laplace_counts",
            scope_dp_epsilon_bucket="0.5_to_1.0",
            scope_dp_delta_bucket="zero",
        ),
        change_reason="seed DP specific MC override",
        approved_by="tests",
    )

    policy = resolve_ci_threshold_policy(
        family="categorical_ci",
        query_type="g2",
        estimator="stratified_counts",
        dp_context={"mechanism": "laplace_counts", "epsilon": 0.7, "delta": 0.0},
        registry_root=tmp_path / "judge_thresholds",
        n_bootstrap=2000,
    )

    assert policy.mc_bootstrap_B == 1234
    assert policy.threshold_scope["dp_mechanism"] == "laplace_counts"


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
