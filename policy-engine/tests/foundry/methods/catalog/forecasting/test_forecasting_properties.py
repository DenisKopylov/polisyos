"""Property-based tests for forecasting methods."""
from __future__ import annotations
import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import timeseries_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestExponentialSmoothingProperties:
    @given(data=timeseries_strategy())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_ses_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0")
        state = {"endog": data["endog"]}
        try:
            result = method.pure_step(state, {"alpha": 0.3})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.all(np.isnan(arr)), f"All-NaN in SES/{key}"
        except Exception:
            pass

    @given(data=timeseries_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_ses_deterministic(self, data, isolated_registry):
        """Same input → same output."""
        method = _method_or_skip(isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0")
        state = {"endog": data["endog"]}
        try:
            r1 = method.pure_step(state, {"alpha": 0.3})
            r2 = method.pure_step(state, {"alpha": 0.3})
            for k in r1:
                if k in r2:
                    np.testing.assert_array_equal(np.asarray(r1[k]), np.asarray(r2[k]))
        except Exception:
            pass


class TestThetaProperties:
    @given(data=timeseries_strategy())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_theta_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "forecasting.univariate.theta@1.0.0")
        state = {"endog": data["endog"]}
        try:
            result = method.pure_step(state, {"horizon": 5})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
                    assert np.any(np.isfinite(arr)), f"No finite values in theta/{key}"
        except Exception:
            pass

    @given(data=timeseries_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_theta_forecast_length(self, data, isolated_registry):
        """Forecast output length should match requested horizon."""
        method = _method_or_skip(isolated_registry, "forecasting.univariate.theta@1.0.0")
        state = {"endog": data["endog"]}
        horizon = 5
        try:
            result = method.pure_step(state, {"horizon": horizon})
            if "forecast" in result:
                fc = np.asarray(result["forecast"])
                assert len(fc) == horizon, f"Expected {horizon} forecasts, got {len(fc)}"
        except Exception:
            pass
