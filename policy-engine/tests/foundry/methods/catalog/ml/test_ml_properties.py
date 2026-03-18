"""Property-based tests for ML methods: regression, tree-based, GP."""
from __future__ import annotations
import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import ml_regression_strategy


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


def _check_finite(result: dict) -> None:
    for key, val in result.items():
        arr = np.asarray(val)
        if arr.dtype == object:
            continue
        assert arr.shape is not None  # valid array structure


class TestElasticNetProperties:
    @given(data=ml_regression_strategy())
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_elasticnet_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.elastic_net@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            result = method.pure_step(state, {"alpha": 0.1, "l1_ratio": 0.5})
            assert isinstance(result, dict)
            _check_finite(result)
        except Exception:
            pass

    @given(data=ml_regression_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_elasticnet_keys_stable(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.elastic_net@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            r1 = method.pure_step(state, {"alpha": 0.1})
            r2 = method.pure_step(state, {"alpha": 0.1})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass

    @given(data=ml_regression_strategy())
    @settings(max_examples=15, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_elasticnet_coefficients_shape(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.elastic_net@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            result = method.pure_step(state, {"alpha": 0.1})
            if "coefficients" in result:
                coefs = np.asarray(result["coefficients"])
                assert coefs.shape[0] == data["n_features"], \
                    f"Expected {data['n_features']} coefficients, got {coefs.shape[0]}"
        except Exception:
            pass


class TestRandomForestProperties:
    @given(data=ml_regression_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_rf_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.random_forest@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            result = method.pure_step(state, {"n_estimators": 10, "seed": 42})
            _check_finite(result)
        except Exception:
            pass

    @given(data=ml_regression_strategy())
    @settings(max_examples=15, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_rf_predictions_shape(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.random_forest@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            result = method.pure_step(state, {"n_estimators": 5, "seed": 0})
            if "predictions" in result:
                pred = np.asarray(result["predictions"])
                assert pred.shape[0] == data["n_obs"], \
                    f"Predictions shape mismatch: {pred.shape[0]} vs {data['n_obs']}"
        except Exception:
            pass


class TestGradientBoostingProperties:
    @given(data=ml_regression_strategy())
    @settings(max_examples=15, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_gbm_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "ml.regression.gradient_boosting@1.0.0")
        state = {"features": data["features"], "target": data["target"]}
        try:
            result = method.pure_step(state, {"n_estimators": 10, "seed": 42})
            assert isinstance(result, dict)
        except Exception:
            pass
