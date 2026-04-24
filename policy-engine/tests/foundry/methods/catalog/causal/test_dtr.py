"""Tests for Dynamic Treatment Regime estimators: Q-learning, A-learning, OWL, DR-DTR."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.dtr import (
    ALearningDTR,
    DoublyRobustDTR,
    OutcomeWeightedLearning,
    QLearningDTR,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.dynamic_regime import DTRResult

# ---------------------------------------------------------------------------
# Shared DGP
# ---------------------------------------------------------------------------


def _make_dtr_data(
    n_units: int = 400,
    n_periods: int = 2,
    seed: int = 42,
) -> DynamicTreatmentData:
    """DGP where always-treating is clearly optimal.

    L_0 ~ N(0, 1)
    A_t ~ Bernoulli(0.5)                 [random treatment]
    L_{t+1} = 0.5 * A_t + 0.3 * L_t + N(0, 0.5)
    Y = 2 * A_0 + 2 * A_1 + L_0 + N(0, 0.5)

    d*(H) = always_treat gives E[Y^{d*}] ≈ 4.0
    d*(H) = never_treat   gives E[Y^{never}] ≈ 0.0
    """
    rng = np.random.default_rng(seed)
    L = np.zeros((n_units, n_periods))
    A = np.zeros((n_units, n_periods), dtype=int)
    L[:, 0] = rng.standard_normal(n_units)

    for t in range(n_periods):
        A[:, t] = rng.integers(0, 2, n_units)
        if t < n_periods - 1:
            L[:, t + 1] = 0.5 * A[:, t] + 0.3 * L[:, t] + rng.normal(0, 0.5, n_units)

    Y = 2.0 * A.sum(axis=1).astype(float) + L[:, 0] + rng.normal(0, 0.5, n_units)

    return DynamicTreatmentData(
        outcome=Y,
        treatment_sequence=A,
        covariate_sequence=L[:, :, np.newaxis],
    )


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


# ---------------------------------------------------------------------------
# Q-Learning
# ---------------------------------------------------------------------------


class TestQLearningDTR:
    def test_returns_success(self):
        data = _make_dtr_data()
        result = QLearningDTR.pure_step(data, {"n_bootstrap": 50})
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_dtr_result(self):
        data = _make_dtr_data()
        result = QLearningDTR.pure_step(data, {"n_bootstrap": 50})
        assert isinstance(result["dtr_result"], DTRResult)

    def test_optimal_value_positive(self):
        """Always-treat DGP → optimal value should be positive."""
        data = _make_dtr_data(n_units=400)
        result = QLearningDTR.pure_step(data, {"n_bootstrap": 60})
        assert result["dtr_result"].value_estimate > 0.0

    def test_ci_is_finite_and_ordered(self):
        data = _make_dtr_data()
        dtr = QLearningDTR.pure_step(data, {"n_bootstrap": 60})["dtr_result"]
        lo, hi = dtr.value_ci
        assert lo <= dtr.value_estimate <= hi
        assert np.isfinite(lo) and np.isfinite(hi)

    def test_failure_on_tiny_data(self):
        # Method requires n_units >= 20; use 15 to pass DynamicTreatmentData validation
        tiny = DynamicTreatmentData(
            outcome=np.ones(15),
            treatment_sequence=np.ones((15, 2), dtype=int),
            covariate_sequence=np.ones((15, 2, 1)),
        )
        result = QLearningDTR.pure_step(tiny, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_n_stages_matches_periods(self):
        data = _make_dtr_data(n_periods=3)
        result = QLearningDTR.pure_step(data, {"n_bootstrap": 50})
        assert result["dtr_result"].n_stages == 3

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.q_learning.q_learning@1.0.0")
        assert method_cls is not None
        assert method_cls is QLearningDTR


# ---------------------------------------------------------------------------
# A-Learning
# ---------------------------------------------------------------------------


class TestALearningDTR:
    def test_returns_success(self):
        data = _make_dtr_data()
        result = ALearningDTR.pure_step(data, {"n_bootstrap": 50})
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_dtr_result(self):
        data = _make_dtr_data()
        result = ALearningDTR.pure_step(data, {"n_bootstrap": 50})
        assert isinstance(result["dtr_result"], DTRResult)

    def test_optimal_value_positive(self):
        data = _make_dtr_data(n_units=400)
        result = ALearningDTR.pure_step(data, {"n_bootstrap": 60})
        assert result["dtr_result"].value_estimate > 0.0

    def test_agrees_with_q_learning_direction(self):
        """A-learning and Q-learning should agree on direction: value > 0."""
        data = _make_dtr_data(n_units=400, seed=7)
        q_val = QLearningDTR.pure_step(data, {"n_bootstrap": 50})["dtr_result"].value_estimate
        a_val = ALearningDTR.pure_step(data, {"n_bootstrap": 50})["dtr_result"].value_estimate
        assert (q_val > 0) == (a_val > 0), (
            f"Q-learning value={q_val:.3f}, A-learning value={a_val:.3f} disagree on sign"
        )

    def test_failure_on_tiny_data(self):
        tiny = DynamicTreatmentData(
            outcome=np.ones(15),
            treatment_sequence=np.ones((15, 2), dtype=int),
            covariate_sequence=np.ones((15, 2, 1)),
        )
        result = ALearningDTR.pure_step(tiny, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.a_learning.a_learning@1.0.0")
        assert method_cls is not None
        assert method_cls is ALearningDTR


# ---------------------------------------------------------------------------
# Outcome-Weighted Learning
# ---------------------------------------------------------------------------


class TestOutcomeWeightedLearning:
    def test_returns_success(self):
        data = _make_dtr_data(n_units=300)
        result = OutcomeWeightedLearning.pure_step(data, {"n_bootstrap": 40})
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_dtr_result(self):
        data = _make_dtr_data(n_units=300)
        result = OutcomeWeightedLearning.pure_step(data, {"n_bootstrap": 40})
        assert isinstance(result["dtr_result"], DTRResult)

    def test_value_estimate_finite(self):
        data = _make_dtr_data(n_units=300)
        dtr = OutcomeWeightedLearning.pure_step(data, {"n_bootstrap": 40})["dtr_result"]
        assert np.isfinite(dtr.value_estimate)

    def test_failure_on_tiny_data(self):
        tiny = DynamicTreatmentData(
            outcome=np.ones(15),
            treatment_sequence=np.ones((15, 2), dtype=int),
            covariate_sequence=np.ones((15, 2, 1)),
        )
        result = OutcomeWeightedLearning.pure_step(tiny, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.owl.owl@1.0.0")
        assert method_cls is not None
        assert method_cls is OutcomeWeightedLearning


# ---------------------------------------------------------------------------
# Doubly Robust DTR
# ---------------------------------------------------------------------------


class TestDoublyRobustDTR:
    def test_returns_success(self):
        data = _make_dtr_data(n_units=300)
        result = DoublyRobustDTR.pure_step(data, {"n_bootstrap": 40})
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_returns_dtr_result(self):
        data = _make_dtr_data(n_units=300)
        result = DoublyRobustDTR.pure_step(data, {"n_bootstrap": 40})
        assert isinstance(result["dtr_result"], DTRResult)

    def test_value_estimate_finite(self):
        data = _make_dtr_data(n_units=300)
        dtr = DoublyRobustDTR.pure_step(data, {"n_bootstrap": 40})["dtr_result"]
        assert np.isfinite(dtr.value_estimate)

    def test_ci_ordered(self):
        data = _make_dtr_data(n_units=300)
        dtr = DoublyRobustDTR.pure_step(data, {"n_bootstrap": 50})["dtr_result"]
        lo, hi = dtr.value_ci
        assert lo <= hi
        assert np.isfinite(lo) and np.isfinite(hi)

    def test_failure_on_tiny_data(self):
        tiny = DynamicTreatmentData(
            outcome=np.ones(15),
            treatment_sequence=np.ones((15, 2), dtype=int),
            covariate_sequence=np.ones((15, 2, 1)),
        )
        result = DoublyRobustDTR.pure_step(tiny, {})
        assert result["report"].status == EstimationStatus.INPUT_INVALID

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.dr_dtr.dr_dtr@1.0.0")
        assert method_cls is not None
        assert method_cls is DoublyRobustDTR


# ---------------------------------------------------------------------------
# Cross-method consistency
# ---------------------------------------------------------------------------


def test_all_four_methods_run_successfully():
    """Quick smoke: all four DTR methods complete without error."""
    data = _make_dtr_data(n_units=200)
    for cls in [QLearningDTR, ALearningDTR, OutcomeWeightedLearning, DoublyRobustDTR]:
        result = cls.pure_step(data, {"n_bootstrap": 40})
        assert result["report"].status == EstimationStatus.SUCCESS, (
            f"{cls.__name__} returned {result['report'].status}"
        )


def test_q_and_a_learning_value_estimates_positive():
    """On always-treat-optimal DGP, both Q and A-learning should give positive values."""
    data = _make_dtr_data(n_units=400, seed=99)
    q_val = QLearningDTR.pure_step(data, {"n_bootstrap": 50})["dtr_result"].value_estimate
    a_val = ALearningDTR.pure_step(data, {"n_bootstrap": 50})["dtr_result"].value_estimate
    assert q_val > 0, f"Q-learning value={q_val:.3f} not positive"
    assert a_val > 0, f"A-learning value={a_val:.3f} not positive"
