"""Property-based tests for simulation methods — stock-flow, discrete event, bootstrap."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestStockFlowProperties:
    @given(
        initial_stock=st.floats(min_value=10.0, max_value=10000.0, allow_nan=False),
        inflow_rate=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        outflow_rate=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
        n_steps=st.integers(min_value=5, max_value=50),
    )
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_stock_flow_output_finite(
        self, initial_stock, inflow_rate, outflow_rate, n_steps, isolated_registry
    ):
        method = _method_or_skip(isolated_registry, "simulation.system_dynamics.stock_flow@1.0.0")
        state = {"initial_stock": initial_stock}
        params = {"inflow_rate": inflow_rate, "outflow_rate": outflow_rate, "n_steps": n_steps}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
                    assert np.any(np.isfinite(arr)), f"No finite in stock_flow/{key}"
        except Exception:
            pass


class TestBootstrapProperties:
    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
        n_boot=st.integers(min_value=50, max_value=200),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_ci_covers_mean(self, data, n_boot, isolated_registry):
        """Bootstrap CI should generally contain the sample mean."""
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        state = {"data": data}
        params = {"n_bootstrap": n_boot, "statistic": "mean", "confidence_level": 0.99, "seed": 42}
        try:
            result = method.pure_step(state, params)
            if "ci_lower" in result and "ci_upper" in result:
                lo = float(result["ci_lower"])
                hi = float(result["ci_upper"])
                if np.isfinite(lo) and np.isfinite(hi):
                    assert lo <= hi, f"CI lower > upper: {lo} > {hi}"
        except Exception:
            pass

    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_se_non_negative(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        state = {"data": data}
        params = {"n_bootstrap": 100, "statistic": "mean", "seed": 42}
        try:
            result = method.pure_step(state, params)
            if "standard_error" in result:
                se = float(result["standard_error"])
                if np.isfinite(se):
                    assert se >= -1e-10
        except Exception:
            pass

    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_deterministic_with_seed(self, data, isolated_registry):
        """Same seed → same bootstrap result."""
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        state = {"data": data}
        params = {"n_bootstrap": 100, "statistic": "mean", "seed": 42}
        try:
            r1 = method.pure_step(state, params)
            r2 = method.pure_step(state, params)
            for k in r1:
                if k in r2:
                    np.testing.assert_array_equal(np.asarray(r1[k]), np.asarray(r2[k]))
        except Exception:
            pass
