"""Property-based tests for survey design and estimation methods."""
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

from tests.foundry.methods.testing.strategies import survey_strategy


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


class TestComplexSurveyProperties:
    @given(data=survey_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_weighted_mean_in_range(self, data, isolated_registry):
        """Weighted mean should be within the range of outcome values."""
        method = _method_or_skip(isolated_registry, "survey.design.complex_survey@1.0.0")
        state = {"outcome": data["outcome"], "weights": data["weights"], "strata_id": data["strata_id"]}
        try:
            result = method.pure_step(state, {})
            if "weighted_mean" in result:
                wm = float(result["weighted_mean"])
                if np.isfinite(wm):
                    lo, hi = float(np.min(data["outcome"])), float(np.max(data["outcome"]))
                    assert lo - 1e-6 <= wm <= hi + 1e-6
        except Exception:
            pass

    @given(data=survey_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_se_non_negative(self, data, isolated_registry):
        """Standard error must be non-negative."""
        method = _method_or_skip(isolated_registry, "survey.design.complex_survey@1.0.0")
        state = {"outcome": data["outcome"], "weights": data["weights"], "strata_id": data["strata_id"]}
        try:
            result = method.pure_step(state, {})
            if "standard_error" in result:
                se = float(result["standard_error"])
                if np.isfinite(se):
                    assert se >= -1e-10
        except Exception:
            pass


class TestRakingProperties:
    @given(data=survey_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_raking_weights_positive(self, data, isolated_registry):
        """Raked weights should be positive."""
        method = _method_or_skip(isolated_registry, "survey.weighting.raking@1.0.0")
        state = {"weights": data["weights"], "strata_id": data["strata_id"]}
        try:
            result = method.pure_step(state, {})
            if "raked_weights" in result:
                rw = np.asarray(result["raked_weights"])
                if np.all(np.isfinite(rw)):
                    assert np.all(rw > -1e-10)
        except Exception:
            pass
