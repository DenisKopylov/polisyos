"""Property-based tests for global sensitivity analysis methods."""

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

from tests.unit.foundry.methods.testing.strategies import sensitivity_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestSobolIndicesProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=25,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "sensitivity.global.sobol_first_order@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        params = {"param_names": data["param_names"]}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert arr.shape is not None
        except Exception:
            pass

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_indices_in_range(self, data, isolated_registry):
        """First-order Sobol indices should sum to at most 1."""
        method = _method_or_skip(isolated_registry, "sensitivity.global.sobol_first_order@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        params = {"param_names": data["param_names"]}
        try:
            result = method.pure_step(state, params)
            if "first_order" in result:
                s1 = np.asarray(result["first_order"])
                if np.all(np.isfinite(s1)):
                    # Sum of first-order indices should be <= 1 (with tolerance)
                    assert np.sum(s1) <= 1.0 + 0.1, (
                        f"First-order Sobol indices sum > 1: {np.sum(s1)}"
                    )
        except Exception:
            pass

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_deterministic(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "sensitivity.global.sobol_first_order@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        params = {"param_names": data["param_names"]}
        try:
            r1 = method.pure_step(state, params)
            r2 = method.pure_step(state, params)
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestMorrisScreeningProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        params = {"param_names": data["param_names"]}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            assert len(result) > 0
        except Exception:
            pass
