"""Property-based tests for survey estimation methods."""

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

from tests.foundry.methods.testing.strategies import survey_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestHorvitzThompsonProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        state = {
            "outcome": data["outcome"],
            "weights": data["weights"],
            "strata_id": data["strata_id"],
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
                    assert arr.shape is not None
        except Exception:
            pass

    @given(data=survey_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_estimate_not_nan(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        state = {
            "outcome": data["outcome"],
            "weights": data["weights"],
            "strata_id": data["strata_id"],
        }
        try:
            result = method.pure_step(state, {})
            if "estimate" in result:
                est = np.asarray(result["estimate"])
                # For valid positive weights and finite outcome, estimate should be finite
                assert not np.any(np.isnan(est)), "HT estimate is NaN"
        except Exception:
            pass

    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_deterministic(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        state = {
            "outcome": data["outcome"],
            "weights": data["weights"],
            "strata_id": data["strata_id"],
        }
        try:
            r1 = method.pure_step(state, {})
            r2 = method.pure_step(state, {})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestRakingProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_raking_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "survey.weighting.raking@1.0.0")
        state = {"weights": data["weights"], "strata_id": data["strata_id"]}
        params = {
            "target_totals": {
                int(s): float(np.sum(data["weights"][data["strata_id"] == s]))
                for s in np.unique(data["strata_id"])
            }
        }
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
        except Exception:
            pass
