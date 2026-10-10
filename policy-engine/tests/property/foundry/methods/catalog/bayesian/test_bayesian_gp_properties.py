"""Property-based tests for Gaussian Process and variational inference methods."""

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
from tests.unit.foundry.methods.testing.strategies import bayesian_regression_strategy


def _check_finite(result: dict, fqn: str) -> None:
    posterior = result["result"]
    assert posterior.posterior_means, f"{fqn} returned no posterior means"
    for name, value in posterior.posterior_means.items():
        assert np.isfinite(value), f"Non-finite posterior mean {name!r} in {fqn}"
    for name, interval in posterior.credible_intervals.items():
        bounds = np.asarray(interval, dtype=float)
        assert np.isfinite(bounds).all(), f"Non-finite interval {name!r} in {fqn}"
        assert bounds[0] <= bounds[1], f"Reversed interval {name!r} in {fqn}"
    predictions = np.asarray(result["prediction_result"].predictions, dtype=float)
    assert predictions.size > 0
    assert np.isfinite(predictions).all(), f"Non-finite predictions in {fqn}"


class TestGaussianProcessProperties:
    @given(data=bayesian_regression_strategy())
    @settings(
        max_examples=15,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gp_regression_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "bayesian.gp.gp_regression@1.0.0"
        method = isolated_registry.get(fqn)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"features": data["X"], "target": data["y"]},
            params={"kernel": "rbf"},
            seed=42,
        )
        assert isinstance(result.output, dict)
        _check_finite(result.output, fqn)

    @given(data=bayesian_regression_strategy())
    @settings(
        max_examples=10,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gp_reported_uncertainty_interval_ordered(
        self, data, isolated_registry, property_method_dispatcher
    ):
        method = isolated_registry.get("bayesian.gp.gp_regression@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"features": data["X"], "target": data["y"]},
            params={"kernel": "rbf"},
            seed=0,
        )
        lower, upper = result.output["uncertainty_envelope"].confidence_interval
        assert np.isfinite([lower, upper]).all()
        assert lower <= upper

    @given(data=bayesian_regression_strategy())
    @settings(
        max_examples=10,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gp_deterministic_same_seed(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("bayesian.gp.gp_regression@1.0.0")
        state = {"features": data["X"], "target": data["y"]}
        first = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={},
            seed=42,
        )
        second = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={},
            seed=42,
        )
        np.testing.assert_array_equal(
            first.output["prediction_result"].predictions,
            second.output["prediction_result"].predictions,
        )
        assert first.output["rmse_test"] == second.output["rmse_test"]


class TestVariationalInferenceProperties:
    @given(data=bayesian_regression_strategy())
    @settings(
        max_examples=15,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_mean_field_vi_output_dict(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("bayesian.variational.mean_field_vi@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"features": data["X"], "target": data["y"]},
            params={"max_iter": 100},
            seed=42,
        )
        assert isinstance(result.output, dict)
        assert result.output["result"].method_name == "mean_field_vi"
        assert result.output["elbo_history"]

    @given(data=bayesian_regression_strategy())
    @settings(
        max_examples=10,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_elbo_history_is_finite(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("bayesian.variational.mean_field_vi@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"features": data["X"], "target": data["y"]},
            params={"max_iter": 200},
            seed=0,
        )
        history = np.asarray(result.output["elbo_history"], dtype=float)
        assert history.size > 0
        assert np.isfinite(history).all()
