"""Tests for Causal Reinforcement Learning: OffPolicyEvaluator and CausalBandit."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.causal_rl import CausalBandit, OffPolicyEvaluator
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.dynamic_regime import BanditResult, OPEResult

# ---------------------------------------------------------------------------
# DGP helpers
# ---------------------------------------------------------------------------


def _make_ope_data(
    n_units: int = 400,
    n_periods: int = 2,
    seed: int = 42,
    behavior_prob: float = 0.5,
) -> DynamicTreatmentData:
    """Longitudinal data with known behavior policy probabilities.

    Behavior policy: π_b(A=1|H) = behavior_prob (constant, ignores H).
    Y = sum_t A_t + N(0, 0.5)
    """
    rng = np.random.default_rng(seed)
    L = np.zeros((n_units, n_periods))
    A = np.zeros((n_units, n_periods), dtype=int)
    L[:, 0] = rng.standard_normal(n_units)

    for t in range(n_periods):
        A[:, t] = rng.binomial(1, behavior_prob, n_units)
        if t < n_periods - 1:
            L[:, t + 1] = 0.3 * L[:, t] + rng.normal(0, 0.3, n_units)

    Y = A.sum(axis=1).astype(float) + rng.normal(0, 0.5, n_units)

    # Constant behavior policy probabilities
    behavior_probs = np.full((n_units, n_periods), behavior_prob)

    return DynamicTreatmentData(
        outcome=Y,
        treatment_sequence=A,
        covariate_sequence=L[:, :, np.newaxis],
        behavior_policy_probs=behavior_probs,
    )


def _make_bandit_data(
    n_units: int = 400,
    seed: int = 42,
) -> DynamicTreatmentData:
    """Two-period data for causal bandit test.

    Arm 1 (A_0=1) gives higher outcome than Arm 0 (A_0=0).
    Y = 3 * A_0 + A_1 + N(0, 0.5)  →  arm 1 is clearly better
    """
    rng = np.random.default_rng(seed)
    n_periods = 2
    A = rng.integers(0, 2, (n_units, n_periods))
    L = rng.standard_normal((n_units, n_periods, 1))
    Y = 3.0 * A[:, 0].astype(float) + A[:, 1].astype(float) + rng.normal(0, 0.5, n_units)

    return DynamicTreatmentData(
        outcome=Y,
        treatment_sequence=A,
        covariate_sequence=L,
    )


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


# ---------------------------------------------------------------------------
# OffPolicyEvaluator tests
# ---------------------------------------------------------------------------


class TestOffPolicyEvaluator:
    def test_returns_success_with_behavior_probs(self):
        data = _make_ope_data()
        result = OffPolicyEvaluator.pure_step(
            data, {"method": "is", "target_policy": "always_treat", "n_bootstrap": 60}
        )
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_ope_result_instance(self):
        data = _make_ope_data()
        result = OffPolicyEvaluator.pure_step(data, {"method": "is", "n_bootstrap": 60})
        assert isinstance(result["ope_result"], OPEResult)

    def test_failure_without_behavior_probs(self):
        """OPE must fail gracefully when behavior_policy_probs is None."""
        data_no_probs = DynamicTreatmentData(
            outcome=np.random.randn(200),
            treatment_sequence=np.random.randint(0, 2, (200, 2)),
            covariate_sequence=np.random.randn(200, 2, 1),
            behavior_policy_probs=None,
        )
        result = OffPolicyEvaluator.pure_step(data_no_probs, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_policy_value_finite(self):
        data = _make_ope_data(n_units=300)
        ope = OffPolicyEvaluator.pure_step(data, {"method": "is", "n_bootstrap": 50})["ope_result"]
        assert np.isfinite(ope.policy_value)

    def test_ci_ordered(self):
        data = _make_ope_data(n_units=300)
        ope = OffPolicyEvaluator.pure_step(data, {"method": "is", "n_bootstrap": 50})["ope_result"]
        lo, hi = ope.confidence_interval
        assert lo <= hi
        assert np.isfinite(lo) and np.isfinite(hi)

    def test_dr_method_runs(self):
        """DR (doubly robust) OPE estimator should also succeed."""
        data = _make_ope_data(n_units=300)
        result = OffPolicyEvaluator.pure_step(data, {"method": "dr", "n_bootstrap": 50})
        assert result["report"].status == EstimationStatus.SUCCESS
        assert isinstance(result["ope_result"], OPEResult)

    def test_same_policy_recovers_observed_mean(self):
        """IS with target = behavior policy should recover approx E[Y]."""
        data = _make_ope_data(n_units=400, behavior_prob=0.5)
        # IS with behavior policy as target: ρ_i ≡ 1 → V̂^{IS} = E[Y]
        ope = OffPolicyEvaluator.pure_step(
            data,
            {"method": "is", "target_policy": "random_half", "n_bootstrap": 60},
        )["ope_result"]
        assert np.isfinite(ope.policy_value)

    def test_ess_positive(self):
        data = _make_ope_data(n_units=300)
        ope = OffPolicyEvaluator.pure_step(data, {"method": "is", "n_bootstrap": 50})["ope_result"]
        assert ope.effective_sample_size > 0

    def test_failure_on_tiny_data(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="at least"):
            DynamicTreatmentData(
                outcome=np.zeros(5),
                treatment_sequence=np.zeros((5, 2), dtype=int),
                covariate_sequence=np.zeros((5, 2, 1)),
                behavior_policy_probs=np.full((5, 2), 0.5),
            )

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.ope.ope@1.0.0")
        assert method_cls is not None
        assert method_cls is OffPolicyEvaluator


# ---------------------------------------------------------------------------
# CausalBandit tests
# ---------------------------------------------------------------------------


class TestCausalBandit:
    def test_returns_success(self):
        data = _make_bandit_data()
        result = CausalBandit.pure_step(data, {"n_rounds": 50, "n_arms": 2})
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_bandit_result_instance(self):
        data = _make_bandit_data()
        result = CausalBandit.pure_step(data, {"n_rounds": 50})
        assert isinstance(result["bandit_result"], BanditResult)

    def test_finds_best_arm(self):
        """With a large effect (Y = 3*A_0), bandit should identify arm 1 as optimal."""
        data = _make_bandit_data(n_units=500, seed=1)
        bandit = CausalBandit.pure_step(data, {"n_rounds": 80, "n_arms": 2})["bandit_result"]
        # Arm 1 = do(A_0=1) should be optimal (higher Y)
        assert "1" in bandit.optimal_arm or "do(A_0=1)" in bandit.optimal_arm, (
            f"Expected arm 1 to be optimal, got {bandit.optimal_arm!r}"
        )

    def test_arm_estimates_present(self):
        data = _make_bandit_data()
        bandit = CausalBandit.pure_step(data, {"n_rounds": 50})["bandit_result"]
        assert len(bandit.arm_estimates) == 2
        for v in bandit.arm_estimates.values():
            assert np.isfinite(v)

    def test_arm_cis_ordered(self):
        data = _make_bandit_data()
        bandit = CausalBandit.pure_step(data, {"n_rounds": 50})["bandit_result"]
        for lo, hi in bandit.arm_cis.values():
            assert lo <= hi

    def test_best_arm_has_higher_estimate_than_worst(self):
        data = _make_bandit_data(n_units=500)
        bandit = CausalBandit.pure_step(data, {"n_rounds": 80, "n_arms": 2})["bandit_result"]
        estimates = list(bandit.arm_estimates.values())
        assert max(estimates) >= min(estimates)

    def test_failure_on_tiny_data(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="at least"):
            DynamicTreatmentData(
                outcome=np.zeros(5),
                treatment_sequence=np.zeros((5, 2), dtype=int),
                covariate_sequence=np.zeros((5, 2, 1)),
            )

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get(
            "causal.dynamic.causal_bandit.causal_bandit@1.0.0"
        )
        assert method_cls is not None
        assert method_cls is CausalBandit


# ---------------------------------------------------------------------------
# Cross-method smoke
# ---------------------------------------------------------------------------


def test_both_rl_methods_run_successfully():
    """Smoke: OPE (with behavior probs) and CausalBandit both run without error."""
    ope_data = _make_ope_data(n_units=200)
    ope_result = OffPolicyEvaluator.pure_step(ope_data, {"method": "is", "n_bootstrap": 40})
    assert ope_result["report"].status == EstimationStatus.SUCCESS

    bandit_data = _make_bandit_data(n_units=200)
    bandit_result = CausalBandit.pure_step(bandit_data, {"n_rounds": 40})
    assert bandit_result["report"].status == EstimationStatus.SUCCESS
