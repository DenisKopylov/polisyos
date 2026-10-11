"""Property-based tests for forecasting methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import timeseries_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _forecast(method_result, method_fqn: str) -> np.ndarray:
    """Return the method's nested point forecast, requiring the declared result path."""
    assert isinstance(method_result.output, dict), f"{method_fqn} did not return an output mapping"
    result = method_result.output.get("result")
    assert isinstance(result, dict), f"{method_fqn} did not return its forecast result mapping"
    return np.asarray(result["forecast"], dtype=float)


class TestExponentialSmoothingProperties:
    @given(data=timeseries_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ses_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "forecasting.univariate.exponential_smoothing@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"series": data["endog"]}
        horizon = 6
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"alpha": 0.3, "horizon": horizon},
            seed=0,
        )
        forecast = _forecast(invocation, fqn)
        assert forecast.shape == (horizon,)
        assert np.isfinite(forecast).all()

    @given(data=timeseries_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ses_deterministic(self, data, isolated_registry, property_method_dispatcher):
        """Same input and explicit dispatch seed produce the same point forecast."""
        fqn = "forecasting.univariate.exponential_smoothing@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"series": data["endog"]}
        params = {"alpha": 0.3}
        first = _forecast(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params=params,
                seed=0,
            ), fqn
        )
        second = _forecast(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params=params,
                seed=0,
            ), fqn
        )
        np.testing.assert_array_equal(first, second)


class TestThetaProperties:
    @given(data=timeseries_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_theta_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "forecasting.univariate.theta@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"series": data["endog"]}
        horizon = 6
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"horizon": horizon},
            seed=0,
        )
        forecast = _forecast(invocation, fqn)
        assert forecast.shape == (horizon,)
        assert np.isfinite(forecast).all()

    @given(data=timeseries_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_theta_forecast_length(self, data, isolated_registry, property_method_dispatcher):
        """Forecast output length matches the requested horizon."""
        fqn = "forecasting.univariate.theta@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"series": data["endog"]}
        horizon = 5
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"horizon": horizon},
            seed=0,
        )
        forecast = _forecast(invocation, fqn)
        assert forecast.shape == (horizon,)
        assert np.isfinite(forecast).all()
