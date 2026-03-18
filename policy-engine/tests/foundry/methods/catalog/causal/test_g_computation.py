"""Tests for G-computation estimators: ParametricGFormula, ICEGFormula, LTMLEEstimator."""
from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.g_computation import (
    ICEGFormula,
    LTMLEEstimator,
    ParametricGFormula,
    _ice_estimate,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.dynamic_regime import GComputationResult


# ---------------------------------------------------------------------------
# Shared DGP
# ---------------------------------------------------------------------------

def _make_dynamic_data(
    n_units: int = 400,
    n_periods: int = 3,
    seed: int = 42,
) -> DynamicTreatmentData:
    """Synthetic DGP with known counterfactual means.

    L_0 ~ N(0, 1)
    A_t ~ Bernoulli(sigmoid(0.5 * L_t))
    L_{t+1} = 0.5 * A_t + 0.3 * L_t + N(0, 0.5)
    Y = sum_t A_t + L_0 + N(0, 1)

    True counterfactual means:
        E[Y^{always_treat}] ≈ n_periods + 0 = n_periods   (≈ 3.0 for T=3)
        E[Y^{never_treat}]  ≈ 0 + 0          = 0.0
    """
    rng = np.random.default_rng(seed)
    def sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    L = np.zeros((n_units, n_periods))
    A = np.zeros((n_units, n_periods), dtype=int)
    L[:, 0] = rng.standard_normal(n_units)

    for t in range(n_periods):
        A[:, t] = rng.binomial(1, sigmoid(0.5 * L[:, t]))
        if t < n_periods - 1:
            L[:, t + 1] = 0.5 * A[:, t] + 0.3 * L[:, t] + rng.normal(0, 0.5, n_units)

    Y = A.sum(axis=1).astype(float) + L[:, 0] + rng.standard_normal(n_units)

    return DynamicTreatmentData(
        outcome=Y,
        treatment_sequence=A,
        covariate_sequence=L[:, :, np.newaxis],  # shape (n,T,1)
    )


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


# ---------------------------------------------------------------------------
# ParametricGFormula tests
# ---------------------------------------------------------------------------

class TestParametricGFormula:
    def test_always_treat_recovers_truth(self):
        data = _make_dynamic_data(n_units=500)
        result = ParametricGFormula.pure_step(
            data,
            {"regime": "always_treat", "n_monte_carlo": 300, "n_bootstrap": 100},
        )
        report = result["report"]
        g_result = result["g_result"]
        assert report.status == EstimationStatus.SUCCESS
        assert isinstance(g_result, GComputationResult)
        # E[Y^{always_treat}] ≈ 3.0
        assert abs(g_result.counterfactual_mean - 3.0) < 0.6

    def test_never_treat_recovers_truth(self):
        data = _make_dynamic_data(n_units=500)
        result = ParametricGFormula.pure_step(
            data,
            {"regime": "never_treat", "n_monte_carlo": 300, "n_bootstrap": 100},
        )
        g_result = result["g_result"]
        assert result["report"].status == EstimationStatus.SUCCESS
        # E[Y^{never_treat}] ≈ 0.0
        assert abs(g_result.counterfactual_mean - 0.0) < 0.5

    def test_always_vs_never_positive_contrast(self):
        data = _make_dynamic_data(n_units=400)
        always = ParametricGFormula.pure_step(
            data, {"regime": "always_treat", "n_monte_carlo": 200, "n_bootstrap": 80}
        )["g_result"]
        never = ParametricGFormula.pure_step(
            data, {"regime": "never_treat", "n_monte_carlo": 200, "n_bootstrap": 80}
        )["g_result"]
        # always_treat should give higher outcome than never_treat
        assert always.counterfactual_mean > never.counterfactual_mean

    def test_ci_contains_point_estimate(self):
        data = _make_dynamic_data()
        result = ParametricGFormula.pure_step(
            data, {"regime": "always_treat", "n_bootstrap": 80, "n_monte_carlo": 200}
        )
        g = result["g_result"]
        lo, hi = g.confidence_interval
        assert lo <= g.counterfactual_mean <= hi

    def test_insufficient_units_raises_validation_error(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="at least"):
            DynamicTreatmentData(
                outcome=np.ones(5),
                treatment_sequence=np.ones((5, 2), dtype=int),
                covariate_sequence=np.ones((5, 2, 1)),
            )

    def test_regime_threshold(self):
        data = _make_dynamic_data(n_units=400)
        result = ParametricGFormula.pure_step(
            data,
            {
                "regime": "threshold",
                "threshold_covariate_index": 0,
                "threshold_value": 0.0,
                "n_bootstrap": 80,
                "n_monte_carlo": 200,
            },
        )
        assert result["report"].status == EstimationStatus.SUCCESS
        g = result["g_result"]
        assert np.isfinite(g.counterfactual_mean)

    def test_two_period_data(self):
        data = _make_dynamic_data(n_periods=2)
        result = ParametricGFormula.pure_step(
            data, {"regime": "always_treat", "n_bootstrap": 50, "n_monte_carlo": 100}
        )
        assert result["report"].status == EstimationStatus.SUCCESS

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get(
            "causal.dynamic.g_computation.parametric_g_formula@1.0.0"
        )
        assert method_cls is not None
        assert method_cls is ParametricGFormula


# ---------------------------------------------------------------------------
# ICEGFormula tests
# ---------------------------------------------------------------------------

class TestICEGFormula:
    def test_always_treat_recovers_truth(self):
        data = _make_dynamic_data(n_units=400)
        result = ICEGFormula.pure_step(
            data, {"regime": "always_treat", "n_bootstrap": 100}
        )
        g = result["g_result"]
        assert result["report"].status == EstimationStatus.SUCCESS
        assert abs(g.counterfactual_mean - 3.0) < 0.6

    def test_never_treat_recovers_truth(self):
        data = _make_dynamic_data(n_units=400)
        result = ICEGFormula.pure_step(
            data, {"regime": "never_treat", "n_bootstrap": 100}
        )
        g = result["g_result"]
        assert result["report"].status == EstimationStatus.SUCCESS
        assert abs(g.counterfactual_mean - 0.0) < 0.5

    def test_ci_contains_point(self):
        data = _make_dynamic_data()
        g = ICEGFormula.pure_step(data, {"n_bootstrap": 80})["g_result"]
        lo, hi = g.confidence_interval
        assert lo <= g.counterfactual_mean <= hi

    def test_failure_on_tiny_data(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="at least"):
            DynamicTreatmentData(
                outcome=np.zeros(8),
                treatment_sequence=np.zeros((8, 2), dtype=int),
                covariate_sequence=np.zeros((8, 2, 1)),
            )

    def test_ice_estimate_internal_always_treat(self):
        data = _make_dynamic_data(n_units=300)
        Y = data.outcome.astype(float)
        A = data.treatment_sequence.astype(float)
        L = data.covariate_sequence.astype(float)
        est = _ice_estimate(Y, A, L, {"regime": "always_treat"})
        assert abs(est - 3.0) < 0.8

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get(
            "causal.dynamic.ice_g_formula.ice_g_formula@1.0.0"
        )
        assert method_cls is not None
        assert method_cls is ICEGFormula


# ---------------------------------------------------------------------------
# LTMLEEstimator tests
# ---------------------------------------------------------------------------

class TestLTMLEEstimator:
    def test_always_treat_finite(self):
        data = _make_dynamic_data(n_units=300)
        result = LTMLEEstimator.pure_step(
            data, {"regime": "always_treat", "n_bootstrap": 80}
        )
        g = result["g_result"]
        assert result["report"].status == EstimationStatus.SUCCESS
        assert np.isfinite(g.counterfactual_mean)

    def test_consistent_direction_with_ice(self):
        """LTMLE and ICE should agree on sign of always_treat vs never_treat."""
        data = _make_dynamic_data(n_units=400)
        ltmle_always = LTMLEEstimator.pure_step(
            data, {"regime": "always_treat", "n_bootstrap": 60}
        )["g_result"].counterfactual_mean
        ltmle_never = LTMLEEstimator.pure_step(
            data, {"regime": "never_treat", "n_bootstrap": 60}
        )["g_result"].counterfactual_mean
        assert ltmle_always > ltmle_never

    def test_failure_on_tiny_data(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="at least"):
            DynamicTreatmentData(
                outcome=np.zeros(8),
                treatment_sequence=np.zeros((8, 2), dtype=int),
                covariate_sequence=np.zeros((8, 2, 1)),
            )

    def test_registered_under_correct_fqn(self):
        ensure_causal_methods_registered()
        method_cls = MethodRegistry.get_instance().get("causal.dynamic.ltmle.ltmle@1.0.0")
        assert method_cls is not None
        assert method_cls is LTMLEEstimator


# ---------------------------------------------------------------------------
# Cross-method agreement
# ---------------------------------------------------------------------------

def test_all_three_agree_direction():
    """Parametric, ICE, and LTMLE should agree on which regime gives higher outcome."""
    data = _make_dynamic_data(n_units=500)
    pg_always = ParametricGFormula.pure_step(
        data, {"regime": "always_treat", "n_bootstrap": 60, "n_monte_carlo": 150}
    )["g_result"].counterfactual_mean
    ice_always = ICEGFormula.pure_step(
        data, {"regime": "always_treat", "n_bootstrap": 60}
    )["g_result"].counterfactual_mean
    ltmle_always = LTMLEEstimator.pure_step(
        data, {"regime": "always_treat", "n_bootstrap": 60}
    )["g_result"].counterfactual_mean

    pg_never = ParametricGFormula.pure_step(
        data, {"regime": "never_treat", "n_bootstrap": 60, "n_monte_carlo": 150}
    )["g_result"].counterfactual_mean
    ice_never = ICEGFormula.pure_step(
        data, {"regime": "never_treat", "n_bootstrap": 60}
    )["g_result"].counterfactual_mean

    # All three: always_treat > never_treat
    assert pg_always > pg_never, "ParametricG: always_treat should dominate never_treat"
    assert ice_always > ice_never, "ICE: always_treat should dominate never_treat"
    assert ltmle_always > 0.0, "LTMLE: always_treat estimate should be positive"


def test_all_three_methods_return_success():
    """Quick smoke: all three run without error on the same dataset."""
    data = _make_dynamic_data(n_units=200)
    for cls in [ParametricGFormula, ICEGFormula, LTMLEEstimator]:
        result = cls.pure_step(data, {"n_bootstrap": 50, "n_monte_carlo": 100})
        assert result["report"].status == EstimationStatus.SUCCESS, (
            f"{cls.__name__} returned {result['report'].status}"
        )
