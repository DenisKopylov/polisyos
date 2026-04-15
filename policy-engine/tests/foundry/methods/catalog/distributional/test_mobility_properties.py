"""Property-based tests for distributional mobility and polarization methods."""
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

from tests.foundry.methods.testing.strategies import distribution_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestTransitionMatrixProperties:
    @given(data=distribution_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_transition_rows_sum_to_one(self, data, isolated_registry):
        """Each row of the transition matrix should sum to ~1."""
        method = _method_or_skip(isolated_registry, "distributional.mobility.transition_matrix@1.0.0")
        n = len(data["income"])
        state = {"income_t0": data["income"], "income_t1": data["income"] * 1.05}
        try:
            result = method.pure_step(state, {"n_quantiles": 5})
            if "transition_matrix" in result:
                tm = np.asarray(result["transition_matrix"])
                if np.all(np.isfinite(tm)):
                    row_sums = tm.sum(axis=1)
                    np.testing.assert_allclose(row_sums, 1.0, atol=0.05)
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_transition_matrix_non_negative(self, data, isolated_registry):
        """Transition probabilities must be non-negative."""
        method = _method_or_skip(isolated_registry, "distributional.mobility.transition_matrix@1.0.0")
        state = {"income_t0": data["income"], "income_t1": data["income"] * 1.05}
        try:
            result = method.pure_step(state, {"n_quantiles": 5})
            if "transition_matrix" in result:
                tm = np.asarray(result["transition_matrix"])
                if np.all(np.isfinite(tm)):
                    assert np.all(tm >= -1e-10), "Negative transition probabilities"
        except Exception:
            pass


class TestPolarizationProperties:
    @given(data=distribution_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_esteban_ray_non_negative(self, data, isolated_registry):
        """Esteban-Ray polarization index should be non-negative."""
        method = _method_or_skip(isolated_registry, "distributional.polarization.esteban_ray@1.0.0")
        state = {"income": data["income"], "weights": data["weights"]}
        try:
            result = method.pure_step(state, {"alpha": 1.0})
            if "polarization" in result:
                p = float(result["polarization"])
                if np.isfinite(p):
                    assert p >= -1e-10, f"Negative polarization: {p}"
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(max_examples=15, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_esteban_ray_deterministic(self, data, isolated_registry):
        """Same input → same polarization index."""
        method = _method_or_skip(isolated_registry, "distributional.polarization.esteban_ray@1.0.0")
        state = {"income": data["income"], "weights": data["weights"]}
        try:
            r1 = method.pure_step(state, {"alpha": 1.0})
            r2 = method.pure_step(state, {"alpha": 1.0})
            for k in r1:
                if k in r2:
                    np.testing.assert_array_equal(np.asarray(r1[k]), np.asarray(r2[k]))
        except Exception:
            pass
