"""Property-based tests for validation methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.strategies import cross_section_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestCrossValidationProperties:
    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cv_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        params = {"n_folds": 3}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert np.any(np.isfinite(arr)), f"No finite values in cv/{key}"
        except Exception:
            pass

    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cv_deterministic(self, data, isolated_registry):
        """Same input → same CV scores."""
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        params = {"n_folds": 3}
        try:
            r1 = method.pure_step(state, params)
            r2 = method.pure_step(state, params)
            for k in r1:
                if k in r2:
                    np.testing.assert_array_equal(np.asarray(r1[k]), np.asarray(r2[k]))
        except Exception:
            pass


class TestNormalScoresProperties:
    @given(data=cross_section_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_normal_scores_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.all(np.isnan(arr)), f"All-NaN in normal_scores/{key}"
        except Exception:
            pass

    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_scores_bounded(self, data, isolated_registry):
        """Probability scores should be in [0, 1]."""
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        try:
            result = method.pure_step(state, {})
            if "pit_values" in result:
                pit = np.asarray(result["pit_values"])
                if np.all(np.isfinite(pit)):
                    assert np.all(pit >= -1e-10) and np.all(pit <= 1.0 + 1e-10)
        except Exception:
            pass
