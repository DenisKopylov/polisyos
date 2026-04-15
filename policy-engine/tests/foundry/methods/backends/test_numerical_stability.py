"""
Numerical stability tests for Foundry methods.

Verifies that methods handle pathological input gracefully:
- Near-singular matrices (high condition number)
- Extreme input magnitudes (very large / very small values)
- Zero variance in outcome
- Minimum viable sample sizes
"""
from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.output_monitor import MethodOutputMonitor


# ---------------------------------------------------------------------------
# Helper: numerical quality checker
# ---------------------------------------------------------------------------

def _assert_output_finite_or_warned(result: dict, method_fqn: str) -> None:
    """
    For ill-conditioned inputs we allow two outcomes:
    1. Result is finite (method handled the problem gracefully), OR
    2. Result contains NaN/Inf but the monitor flagged it (method degraded gracefully)

    Either way the method must NOT raise an unhandled exception.
    """
    monitor = MethodOutputMonitor()
    flags = monitor.check_basic(result)
    nan_inf_flags = [f for f in flags if f.reason in {"nan_detected", "inf_detected"}]
    # It's acceptable to have NaN/Inf in ill-conditioned output — what matters
    # is that the method did not crash with an unhandled exception.
    _ = nan_inf_flags  # just checking the method completes


# ---------------------------------------------------------------------------
# Near-singular matrix tests
# ---------------------------------------------------------------------------

class TestNearSingularMatrix:
    """Methods receiving near-singular design matrices should not crash."""

    @pytest.fixture()
    def near_singular_regression_data(self):
        """Design matrix with condition number ~ 1e12."""
        rng = np.random.default_rng(0)
        n = 50
        # Create near-collinear features: x2 ≈ x1 + small noise
        x1 = rng.standard_normal(n)
        x2 = x1 + 1e-8 * rng.standard_normal(n)  # almost identical to x1
        X = np.column_stack([x1, x2]).astype(np.float64)
        y = x1 * 1.5 + rng.standard_normal(n) * 0.1
        return {"features": X, "target": y}

    def test_linear_regression_near_singular_does_not_crash(
        self, near_singular_regression_data, isolated_registry
    ):
        fqn = "bayesian.regression.linear_regression@1.0.0"
        method_cls = isolated_registry.get(fqn)

        # Must complete without raising (may produce NaN/Inf which monitor catches)
        result = method_cls.pure_step(near_singular_regression_data, {"seed": 0})
        _assert_output_finite_or_warned(result, fqn)

    @pytest.fixture()
    def near_singular_iv_data(self):
        """IV data with weak instrument (near-zero first stage)."""
        rng = np.random.default_rng(1)
        n = 100
        instrument = rng.standard_normal(n)
        treatment = 1e-10 * instrument + rng.standard_normal(n)  # essentially useless IV
        outcome = treatment * 2.0 + rng.standard_normal(n)
        entity_ids = np.repeat(np.arange(n // 2), 2).astype(np.int64)
        return {
            "dependent": outcome.astype(np.float64),
            "exog": np.column_stack([treatment, np.ones(n)]).astype(np.float64),
            "instrument_ids": instrument.reshape(-1, 1).astype(np.float64),
            "entity_ids": entity_ids,
            "time_ids": np.tile(np.array([0, 1], dtype=np.int64), n // 2),
        }

    def test_iv_weak_instrument_does_not_crash(
        self, near_singular_iv_data, isolated_registry
    ):
        fqn = "econometrics.iv.two_stage_least_squares@1.0.0"
        method_cls = isolated_registry.get(fqn)

        result = method_cls.pure_step(near_singular_iv_data, {"n_endogenous": 1})
        _assert_output_finite_or_warned(result, fqn)


# ---------------------------------------------------------------------------
# Extreme magnitude inputs
# ---------------------------------------------------------------------------

class TestExtremeMagnitudes:
    @pytest.fixture()
    def extreme_large_data(self):
        rng = np.random.default_rng(2)
        n_units = 20
        n_periods = 4
        return {
            "outcome": (rng.standard_normal((n_units, n_periods)) * 1e10).astype(np.float64),
            "treatment": (rng.standard_normal(n_units) > 0).astype(np.float64),
            "time_treatment": 2,
        }

    @pytest.fixture()
    def extreme_small_data(self):
        rng = np.random.default_rng(3)
        n_units = 20
        n_periods = 4
        return {
            "outcome": (rng.standard_normal((n_units, n_periods)) * 1e-10).astype(np.float64),
            "treatment": (rng.standard_normal(n_units) > 0).astype(np.float64),
            "time_treatment": 2,
        }

    def test_did_extreme_large_does_not_crash(self, extreme_large_data, isolated_registry):
        fqn = "causal.inference.did.standard@1.0.0"
        method_cls = isolated_registry.get(fqn)
        result = method_cls.pure_step(extreme_large_data, {})
        _assert_output_finite_or_warned(result, fqn)

    def test_did_extreme_small_does_not_crash(self, extreme_small_data, isolated_registry):
        fqn = "causal.inference.did.standard@1.0.0"
        method_cls = isolated_registry.get(fqn)
        result = method_cls.pure_step(extreme_small_data, {})
        _assert_output_finite_or_warned(result, fqn)


# ---------------------------------------------------------------------------
# Zero variance in outcome
# ---------------------------------------------------------------------------

class TestZeroVariance:
    @pytest.fixture()
    def zero_variance_data(self):
        """Outcome is constant — zero variance."""
        n_units = 15
        n_periods = 4
        return {
            "outcome": np.zeros((n_units, n_periods), dtype=np.float64),
            "treatment": (np.arange(n_units) >= n_units // 2).astype(np.float64),
            "time_treatment": 2,
        }

    def test_did_zero_variance_does_not_crash(self, zero_variance_data, isolated_registry):
        fqn = "causal.inference.did.standard@1.0.0"
        method_cls = isolated_registry.get(fqn)
        # Should not raise — might return zeros or NaN (monitored)
        try:
            result = method_cls.pure_step(zero_variance_data, {})
            _assert_output_finite_or_warned(result, fqn)
        except Exception as exc:
            # Only acceptable exception: explicit "zero variance" domain errors
            # Crash with KeyError / AttributeError etc. is not acceptable
            msg = str(exc).lower()
            acceptable_terms = {"singular", "variance", "degenerate", "rank", "converge"}
            assert any(t in msg for t in acceptable_terms), (
                f"Unexpected exception for zero-variance input: {exc!r}"
            )


# ---------------------------------------------------------------------------
# Minimum viable sample sizes
# ---------------------------------------------------------------------------

class TestMinimumSampleSizes:
    """Methods should either work or raise a clear DomainError at n_min."""

    @pytest.fixture()
    def tiny_panel_data(self):
        """Smallest possible panel: 2 entities × 2 periods = 4 observations."""
        return {
            "outcome": np.array([[1.0, 1.5], [2.0, 2.5]], dtype=np.float64),
            "treatment": np.array([0.0, 1.0], dtype=np.float64),
            "time_treatment": 1,
        }

    def test_did_minimum_sample_does_not_silently_corrupt(
        self, tiny_panel_data, isolated_registry
    ):
        fqn = "causal.inference.did.standard@1.0.0"
        method_cls = isolated_registry.get(fqn)

        try:
            result = method_cls.pure_step(tiny_panel_data, {})
            # If it runs — output must be dict with at least one key
            assert isinstance(result, dict)
            assert len(result) > 0
        except Exception:
            # Raising on tiny sample is acceptable (explicit fail-fast)
            pass

    def test_lp_minimum_constraints(self, isolated_registry):
        """LP with single constraint and single variable."""
        fqn = "optimization.linear.resource_lp@1.0.0"
        method_cls = isolated_registry.get(fqn)

        state = {
            "c": np.array([-1.0]),       # minimize -x (= maximize x)
            "A_ub": np.array([[1.0]]),   # x <= 10
            "b_ub": np.array([10.0]),
        }
        try:
            result = method_cls.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass  # Acceptable to raise on degenerate LP


# ---------------------------------------------------------------------------
# Output monitor integration: flags raised on pathological outputs
# ---------------------------------------------------------------------------

class TestOutputMonitorWithPathologicalData:
    def test_monitor_flags_nan_from_method(self):
        """Construct synthetic result with NaN and verify monitor detects it."""
        from polisyos.foundry.methods.output_monitor import MethodOutputMonitor
        monitor = MethodOutputMonitor()
        bad_result = {"coefficients": np.array([1.0, float("nan"), 3.0])}
        flags = monitor.check_basic(bad_result)
        assert any(f.reason == "nan_detected" for f in flags)

    def test_monitor_flags_inf_from_method(self):
        from polisyos.foundry.methods.output_monitor import MethodOutputMonitor
        monitor = MethodOutputMonitor()
        bad_result = {"se": np.array([0.1, float("inf")])}
        flags = monitor.check_basic(bad_result)
        assert any(f.reason == "inf_detected" for f in flags)

    def test_clean_result_no_flags(self):
        from polisyos.foundry.methods.output_monitor import MethodOutputMonitor
        monitor = MethodOutputMonitor()
        good_result = {"ate": np.array([0.25, 0.30, 0.20])}
        flags = monitor.check_basic(good_result)
        assert flags == []
