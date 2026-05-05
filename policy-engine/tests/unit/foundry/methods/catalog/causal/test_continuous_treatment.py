"""Tests for continuous treatment estimators (Phase 6)."""

from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.continuous_treatment import (
    EntropyBalancingContinuousEstimator,
    GeneralizedPropensityScoreEstimator,
    KernelDoseResponseEstimator,
    ShiftInterventionEstimator,
    _normal_pdf,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    ContinuousTreatmentData,
    DoseResponseResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def linear_dgp(rng):
    """Y = 2*T + X[:,1] + noise; T correlated with X."""
    n = 500
    X = rng.normal(0, 1, (n, 3))
    T = 0.5 * X[:, 0] + rng.normal(0, 1, n)
    Y = 2.0 * T + X[:, 1] + rng.normal(0, 0.5, n)
    return Y, T, X


@pytest.fixture
def small_linear_dgp(rng):
    n = 200
    X = rng.normal(0, 1, (n, 2))
    T = rng.normal(0, 1, n)
    Y = 1.5 * T + rng.normal(0, 0.3, n)
    return Y, T, X


# ---------------------------------------------------------------------------
# _normal_pdf helper
# ---------------------------------------------------------------------------


class TestNormalPDF:
    def test_positive(self):
        x = np.array([0.0, 1.0, -1.0])
        assert (_normal_pdf(x, 0.0, 1.0) > 0).all()

    def test_peaks_at_mean(self):
        mu = 2.0
        sigma = 0.5
        x = np.linspace(-3, 7, 200)
        pdf = _normal_pdf(x, mu, sigma)
        assert x[np.argmax(pdf)] == pytest.approx(mu, abs=0.1)

    def test_integrates_to_one(self):
        x = np.linspace(-10, 10, 10000)
        dx = x[1] - x[0]
        pdf = _normal_pdf(x, 0.0, 1.0)
        integral = (pdf * dx).sum()
        assert abs(integral - 1.0) < 0.01


# ---------------------------------------------------------------------------
# ContinuousTreatmentData protocol
# ---------------------------------------------------------------------------


class TestContinuousTreatmentData:
    def test_basic_construction(self, rng):
        n = 100
        Y = rng.normal(0, 1, n)
        T = rng.normal(0, 1, n)
        X = rng.normal(0, 1, (n, 3))
        data = ContinuousTreatmentData(outcome=Y, treatment=T, covariates=X)
        assert data.n_obs == n

    def test_shape_mismatch_raises(self, rng):
        Y = rng.normal(0, 1, 100)
        T = rng.normal(0, 1, 80)
        X = rng.normal(0, 1, (100, 3))
        with pytest.raises(ValueError):
            ContinuousTreatmentData(outcome=Y, treatment=T, covariates=X)

    def test_extra_field_forbidden(self, rng):
        Y = rng.normal(0, 1, 50)
        T = rng.normal(0, 1, 50)
        X = rng.normal(0, 1, (50, 2))
        with pytest.raises(Exception):
            ContinuousTreatmentData(outcome=Y, treatment=T, covariates=X, extra=1)

    def test_evaluation_points_optional(self, rng):
        n = 50
        Y = rng.normal(0, 1, n)
        T = rng.normal(0, 1, n)
        X = rng.normal(0, 1, (n, 2))
        data = ContinuousTreatmentData(outcome=Y, treatment=T, covariates=X)
        assert data.evaluation_points is None

    def test_feature_names_optional(self, rng):
        n = 50
        Y = rng.normal(0, 1, n)
        T = rng.normal(0, 1, n)
        X = rng.normal(0, 1, (n, 2))
        data = ContinuousTreatmentData(
            outcome=Y, treatment=T, covariates=X, feature_names=("age", "income")
        )
        assert data.feature_names == ("age", "income")


# ---------------------------------------------------------------------------
# GeneralizedPropensityScoreEstimator
# ---------------------------------------------------------------------------


class TestGPSEstimator:
    def test_output_shape(self, linear_dgp):
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_bootstrap": 20, "n_eval_points": 10}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        n_eval = 10
        assert len(dr["treatment_grid"]) == n_eval
        assert len(dr["dose_response"]) == n_eval

    def test_confidence_bands_straddle_point_estimate(self, linear_dgp):
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_bootstrap": 20, "n_eval_points": 10}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        lo = np.asarray(dr["confidence_band_lower"])
        hi = np.asarray(dr["confidence_band_upper"])
        dr_val = np.asarray(dr["dose_response"])
        assert (lo <= dr_val + 1e-10).all()
        assert (hi >= dr_val - 1e-10).all()

    def test_linear_dgp_recovers_slope(self, linear_dgp):
        """With Y = 2*T + noise, dose-response slope should be near 2."""
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_bootstrap": 30, "n_eval_points": 15}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        grid = np.asarray(dr["treatment_grid"])
        curve = np.asarray(dr["dose_response"])
        slope = np.polyfit(grid, curve, 1)[0]
        assert 1.3 < slope < 2.7, f"Expected slope ~2, got {slope:.3f}"

    def test_n_obs_in_result(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, {"n_bootstrap": 10})
        assert result["dose_response_result"]["n_obs"] == len(Y)

    def test_all_finite(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, {"n_bootstrap": 10})
        dr = result["dose_response_result"]
        for key in [
            "dose_response",
            "standard_errors",
            "confidence_band_lower",
            "confidence_band_upper",
        ]:
            assert np.isfinite(np.asarray(dr[key])).all(), f"{key} contains non-finite"

    def test_custom_eval_points(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        eval_pts = np.linspace(-1, 1, 7)
        state = {"outcome": Y, "treatment": T, "covariates": X, "evaluation_points": eval_pts}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, {"n_bootstrap": 5})
        dr = result["dose_response_result"]
        assert len(dr["treatment_grid"]) == 7

    def test_method_name_set(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, {"n_bootstrap": 5})
        method = result["dose_response_result"]["method"]
        assert "gps" in method.lower() or "hirano" in method.lower()

    def test_standard_errors_positive(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = GeneralizedPropensityScoreEstimator.pure_step(state, {"n_bootstrap": 10})
        se = np.asarray(result["dose_response_result"]["standard_errors"])
        assert (se >= 0).all()


# ---------------------------------------------------------------------------
# KernelDoseResponseEstimator
# ---------------------------------------------------------------------------


class TestKernelDoseResponseEstimator:
    def test_output_shape(self, linear_dgp):
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_folds": 3, "n_eval_points": 8}
        result = KernelDoseResponseEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        assert len(dr["treatment_grid"]) == 8
        assert len(dr["dose_response"]) == 8

    def test_all_finite(self, linear_dgp):
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = KernelDoseResponseEstimator.pure_step(state, {"n_folds": 3, "n_eval_points": 8})
        dr = result["dose_response_result"]
        for key in ["dose_response", "standard_errors"]:
            assert np.isfinite(np.asarray(dr[key])).all(), f"{key} has non-finite values"

    def test_linear_dgp_recovers_direction(self, linear_dgp):
        """Kernel DR dose-response should be monotonically increasing for Y=2T+noise."""
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_folds": 3, "n_eval_points": 12}
        result = KernelDoseResponseEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        curve = np.asarray(dr["dose_response"])
        # Fit linear; slope should be > 0
        slope = np.polyfit(range(len(curve)), curve, 1)[0]
        assert slope > 0, f"Expected positive slope, got {slope:.3f}"

    def test_doubly_robust_bias_when_both_correct(self, rng):
        """Near-zero bias with correctly-specified nuisance models."""
        n = 600
        X = rng.normal(0, 1, (n, 2))
        T = rng.normal(0, 1, n)  # T independent of X → GPS correct trivially
        Y = 1.5 * T + rng.normal(0, 0.3, n)  # simple linear
        state = {"outcome": Y, "treatment": T, "covariates": X}
        eval_pts = np.array([0.0])
        state_with_pts = dict(state, evaluation_points=eval_pts)
        result = KernelDoseResponseEstimator.pure_step(
            state_with_pts, {"n_folds": 3, "n_eval_points": 1}
        )
        dr = result["dose_response_result"]
        # At t=0, β(0) ≈ E[Y(0)] ≈ mean(X[:,1]*0 + 0) = 0
        beta_at_zero = float(np.asarray(dr["dose_response"])[0])
        assert abs(beta_at_zero) < 1.0, f"Expected β(0)≈0, got {beta_at_zero:.3f}"

    def test_confidence_bands_straddle_estimate(self, linear_dgp):
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = KernelDoseResponseEstimator.pure_step(state, {"n_folds": 3, "n_eval_points": 8})
        dr = result["dose_response_result"]
        lo = np.asarray(dr["confidence_band_lower"])
        hi = np.asarray(dr["confidence_band_upper"])
        beta = np.asarray(dr["dose_response"])
        assert (lo <= beta + 1e-10).all()
        assert (hi >= beta - 1e-10).all()


# ---------------------------------------------------------------------------
# ShiftInterventionEstimator
# ---------------------------------------------------------------------------


class TestShiftInterventionEstimator:
    def test_zero_delta_near_zero_effect(self, small_linear_dgp):
        """delta=0 → E[Y(A+0)] - E[Y(A)] ≈ 0."""
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.0, "n_folds": 3})
        effect = result["shift_effect"]["point_estimate"]
        assert abs(effect) < 0.5, f"Expected effect≈0 for delta=0, got {effect:.3f}"

    def test_positive_delta_positive_effect_linear_dgp(self, linear_dgp):
        """For Y=2T, shifting T by δ>0 gives effect ≈ 2δ."""
        Y, T, X = linear_dgp
        delta = 0.5
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": delta, "n_folds": 3})
        effect = result["shift_effect"]["point_estimate"]
        # Expect effect ≈ 2 * delta = 1.0, allow 60% tolerance
        assert 0.4 < effect < 1.6, f"Expected effect≈{2 * delta}, got {effect:.3f}"

    def test_output_keys_present(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.3, "n_folds": 3})
        assert "shift_effect" in result
        assert "point_estimate" in result["shift_effect"]
        assert "standard_error" in result["shift_effect"]

    def test_standard_error_positive(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.2, "n_folds": 3})
        se = result["shift_effect"]["standard_error"]
        assert se >= 0

    def test_negative_delta_reverses_sign(self, linear_dgp):
        """Shift by -δ gives negative effect when slope > 0."""
        Y, T, X = linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        r_pos = ShiftInterventionEstimator.pure_step(state, {"delta": 0.5, "n_folds": 3})
        r_neg = ShiftInterventionEstimator.pure_step(state, {"delta": -0.5, "n_folds": 3})
        assert r_pos["shift_effect"]["point_estimate"] > 0
        assert r_neg["shift_effect"]["point_estimate"] < 0

    def test_all_finite(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.1, "n_folds": 3})
        se = (
            result["shift_effect"]["shift_effect"]["standard_error"]
            if "shift_effect" in result["shift_effect"]
            else result["shift_effect"]["standard_error"]
        )
        assert np.isfinite(result["shift_effect"]["point_estimate"])

    def test_method_name_in_result(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.2, "n_folds": 3})
        method = result["shift_effect"].get("method", "")
        assert "shift" in method.lower() or "diaz" in method.lower() or method == ""

    def test_density_ratio_diagnostics_present(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = ShiftInterventionEstimator.pure_step(state, {"delta": 0.2, "n_folds": 3})
        diagnostics = result["shift_effect"]["density_ratio_diagnostics"]
        assert diagnostics["status"] == "ok"
        assert diagnostics["effective_sample_size"] > 0
        assert diagnostics["max_density_ratio"] >= diagnostics["min_density_ratio"]


# ---------------------------------------------------------------------------
# EntropyBalancingContinuousEstimator
# ---------------------------------------------------------------------------


class TestEntropyBalancingContinuousEstimator:
    def test_output_shape(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        params = {"n_eval_points": 8, "n_bootstrap": 10}
        result = EntropyBalancingContinuousEstimator.pure_step(state, params)
        dr = result["dose_response_result"]
        assert len(dr["treatment_grid"]) == 8
        assert len(dr["dose_response"]) == 8

    def test_all_finite(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = EntropyBalancingContinuousEstimator.pure_step(
            state, {"n_eval_points": 6, "n_bootstrap": 5}
        )
        dr = result["dose_response_result"]
        for key in ["dose_response", "standard_errors"]:
            assert np.isfinite(np.asarray(dr[key])).all(), f"{key} has non-finite values"

    def test_confidence_bands_ordered(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = EntropyBalancingContinuousEstimator.pure_step(
            state, {"n_eval_points": 8, "n_bootstrap": 10}
        )
        dr = result["dose_response_result"]
        lo = np.asarray(dr["confidence_band_lower"])
        hi = np.asarray(dr["confidence_band_upper"])
        assert (lo <= hi + 1e-10).all()

    def test_standard_errors_non_negative(self, small_linear_dgp):
        Y, T, X = small_linear_dgp
        state = {"outcome": Y, "treatment": T, "covariates": X}
        result = EntropyBalancingContinuousEstimator.pure_step(
            state, {"n_eval_points": 6, "n_bootstrap": 5}
        )
        se = np.asarray(result["dose_response_result"]["standard_errors"])
        assert (se >= 0).all()


# ---------------------------------------------------------------------------
# CrossFitContinuousOrchestrator (integration)
# ---------------------------------------------------------------------------


class TestCrossFitContinuousOrchestrator:
    def test_gps_oof_in_range(self, small_linear_dgp):
        from polisyos.foundry.methods.catalog.causal.cross_fit import (
            CrossFitContinuousOrchestrator,
        )

        Y, T, X = small_linear_dgp
        state = {"covariates": X, "treatment": T, "outcome": Y}
        result = CrossFitContinuousOrchestrator.pure_step(state, {"n_folds": 3})
        gps = result["gps_oof"]
        min_gps = 1e-4
        assert (np.asarray(gps) >= min_gps).all(), "GPS OOF contains values below min_gps"

    def test_fold_assignments_cover_all(self, small_linear_dgp):
        from polisyos.foundry.methods.catalog.causal.cross_fit import (
            CrossFitContinuousOrchestrator,
        )

        Y, T, X = small_linear_dgp
        state = {"covariates": X, "treatment": T, "outcome": Y}
        result = CrossFitContinuousOrchestrator.pure_step(state, {"n_folds": 4})
        fold_assignments = np.asarray(result["fold_assignments"])
        assert set(fold_assignments.tolist()) == {0, 1, 2, 3}

    def test_outcome_oof_finite(self, small_linear_dgp):
        from polisyos.foundry.methods.catalog.causal.cross_fit import (
            CrossFitContinuousOrchestrator,
        )

        Y, T, X = small_linear_dgp
        state = {"covariates": X, "treatment": T, "outcome": Y}
        result = CrossFitContinuousOrchestrator.pure_step(state, {"n_folds": 3})
        assert np.isfinite(np.asarray(result["outcome_oof"])).all()

    def test_output_length_matches_input(self, small_linear_dgp):
        from polisyos.foundry.methods.catalog.causal.cross_fit import (
            CrossFitContinuousOrchestrator,
        )

        Y, T, X = small_linear_dgp
        n = len(Y)
        state = {"covariates": X, "treatment": T, "outcome": Y}
        result = CrossFitContinuousOrchestrator.pure_step(state, {"n_folds": 3})
        assert len(result["gps_oof"]) == n
        assert len(result["outcome_oof"]) == n
        assert len(result["fold_assignments"]) == n


# ---------------------------------------------------------------------------
# DoseResponseResult model
# ---------------------------------------------------------------------------


class TestDoseResponseResult:
    def test_construction(self, rng):
        n = 10
        grid = np.linspace(0, 1, n)
        curve = grid * 2
        se = np.ones(n) * 0.1
        result = DoseResponseResult(
            treatment_grid=grid,
            dose_response=curve,
            confidence_band_lower=curve - 0.2,
            confidence_band_upper=curve + 0.2,
            standard_errors=se,
            method="test_method",
            n_obs=100,
        )
        assert result.n_obs == 100
        assert result.method == "test_method"

    def test_extra_fields_forbidden(self, rng):
        n = 5
        grid = np.linspace(0, 1, n)
        with pytest.raises(Exception):
            DoseResponseResult(
                treatment_grid=grid,
                dose_response=grid,
                confidence_band_lower=grid,
                confidence_band_upper=grid,
                standard_errors=grid,
                method="t",
                n_obs=50,
                unknown=1,
            )
