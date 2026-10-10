"""Property-based tests for ML regression methods."""

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
from tests.unit.foundry.methods.testing.strategies import ml_regression_strategy


def _check_finite(result: dict, fqn: str) -> None:
    prediction_result = result["result"]
    predictions = np.asarray(prediction_result.predictions, dtype=float)
    assert predictions.size > 0, f"{fqn} returned no predictions"
    assert np.isfinite(predictions).all(), f"{fqn} returned non-finite predictions"
    assert prediction_result.metrics, f"{fqn} returned no metrics"
    assert all(np.isfinite(value) for value in prediction_result.metrics.values())


class TestElasticNetProperties:
    @given(data=ml_regression_strategy())
    @settings(
        max_examples=30, deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_elasticnet_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "ml.regression.elastic_net@1.0.0"
        method = isolated_registry.get(fqn)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"features": data["features"], "target": data["target"]},
            params={"l1_ratio": 0.5, "cv": 5},
            seed=42,
        )
        assert isinstance(result.output, dict)
        _check_finite(result.output, fqn)

    @given(data=ml_regression_strategy())
    @settings(
        max_examples=20, deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_elasticnet_result_keys_stable(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("ml.regression.elastic_net@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        first = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method, state=state,
            params={"l1_ratio": 0.5}, seed=1,
        ).output
        second = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method, state=state,
            params={"l1_ratio": 0.5}, seed=1,
        ).output
        assert set(first) == set(second) == {"result", "uncertainty_envelope"}
        assert set(first["result"].metrics) == set(second["result"].metrics)
        assert set(first["result"].coefficients) == set(second["result"].coefficients)

    @given(data=ml_regression_strategy())
    @settings(
        max_examples=15, deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_elasticnet_coefficients_shape(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("ml.regression.elastic_net@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method,
            state={"features": data["features"], "target": data["target"]},
            params={"l1_ratio": 0.5}, seed=0,
        )
        coefficients = result.output["result"].coefficients
        assert len(coefficients) == data["n_features"] + 1
        assert all(np.isfinite(value) for value in coefficients.values())


class TestRandomForestProperties:
    @given(data=ml_regression_strategy())
    @settings(
        max_examples=20, deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_rf_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "ml.regression.random_forest@1.0.0"
        method = isolated_registry.get(fqn)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method,
            state={"features": data["features"], "target": data["target"]},
            params={"n_estimators": 10, "random_state": 42}, seed=42,
        )
        _check_finite(result.output, fqn)

    @given(data=ml_regression_strategy())
    @settings(
        max_examples=15, deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_rf_predictions_shape(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("ml.regression.random_forest@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method,
            state={"features": data["features"], "target": data["target"]},
            params={"n_estimators": 5, "random_state": 0}, seed=0,
        )
        predictions = np.asarray(result.output["result"].predictions)
        assert predictions.shape == (data["n_obs"],)


class TestGradientBoostingProperties:
    @given(data=ml_regression_strategy())
    @settings(
        max_examples=15, deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gbm_output_and_predictions(self, data, isolated_registry, property_method_dispatcher):
        fqn = "ml.regression.gradient_boosting@1.0.0"
        method = isolated_registry.get(fqn)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher, method_class=method,
            state={"features": data["features"], "target": data["target"]},
            params={"n_estimators": 10, "random_state": 42}, seed=42,
        )
        assert isinstance(result.output, dict)
        _check_finite(result.output, fqn)
        assert result.output["result"].predictions.shape == (data["n_obs"],)
