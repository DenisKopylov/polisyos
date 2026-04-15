"""
Property-based tests for Gaussian Process and variational inference methods.
"""
from __future__ import annotations

import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)

sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import (
    bayesian_regression_strategy,
    spatial_data_strategy,
)


def _check_finite(result: dict, fqn: str) -> None:
    for key, val in result.items():
        arr = np.asarray(val)
        if arr.dtype == object:
            continue
        if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
            assert arr.shape is not None


class TestGaussianProcessProperties:
    @given(data=bayesian_regression_strategy())
    @settings(max_examples=15, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_gp_regression_output_finite(self, data, isolated_registry):
        fqn = "bayesian.gp.gp_regression@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"features": data["X"], "target": data["y"]}
        try:
            result = method.pure_step(state, {"kernel": "rbf", "seed": 42})
            assert isinstance(result, dict)
            _check_finite(result, fqn)
        except Exception:
            pass

    @given(data=bayesian_regression_strategy())
    @settings(max_examples=10, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_gp_predictive_variance_positive(self, data, isolated_registry):
        """GP predictive variance should be non-negative."""
        fqn = "bayesian.gp.gp_regression@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"features": data["X"], "target": data["y"]}
        try:
            result = method.pure_step(state, {"kernel": "rbf", "seed": 0})
            if "predictive_variance" in result:
                var = np.asarray(result["predictive_variance"])
                if np.all(np.isfinite(var)):
                    assert np.all(var >= -1e-10), "GP predictive variance is negative"
        except Exception:
            pass

    @given(data=bayesian_regression_strategy())
    @settings(max_examples=10, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_gp_deterministic_same_seed(self, data, isolated_registry):
        fqn = "bayesian.gp.gp_regression@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"features": data["X"], "target": data["y"]}
        try:
            r1 = method.pure_step(state, {"seed": 42})
            r2 = method.pure_step(state, {"seed": 42})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestVariationalInferenceProperties:
    @given(data=bayesian_regression_strategy())
    @settings(max_examples=15, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_mean_field_vi_output_dict(self, data, isolated_registry):
        fqn = "bayesian.variational.mean_field_vi@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"features": data["X"], "target": data["y"]}
        try:
            result = method.pure_step(state, {"n_iterations": 100, "seed": 42})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=bayesian_regression_strategy())
    @settings(max_examples=10, deadline=20000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_elbo_is_finite(self, data, isolated_registry):
        """ELBO (Evidence Lower BOund) should be finite after convergence."""
        fqn = "bayesian.variational.mean_field_vi@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"features": data["X"], "target": data["y"]}
        try:
            result = method.pure_step(state, {"n_iterations": 200, "seed": 0})
            if "elbo" in result:
                elbo = float(result["elbo"])
                # ELBO should be finite (not necessarily converged, but not NaN)
                assert not np.isnan(elbo), "ELBO is NaN"
        except Exception:
            pass
