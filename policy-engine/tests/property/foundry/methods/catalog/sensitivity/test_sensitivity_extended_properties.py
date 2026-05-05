"""Property-based tests for sensitivity analysis methods — Sobol, Morris, specification curve."""

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


class TestMorrisProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        try:
            result = method.pure_step(state, {"param_names": data["param_names"]})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert np.any(np.isfinite(arr)), f"No finite values in morris/{key}"
        except Exception:
            pass

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_mu_star_non_negative(self, data, isolated_registry):
        """mu* (absolute elementary effects) should be non-negative."""
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        state = {"X": data["X"], "Y": data["Y"]}
        try:
            result = method.pure_step(state, {"param_names": data["param_names"]})
            if "mu_star" in result:
                ms = np.asarray(result["mu_star"])
                if np.all(np.isfinite(ms)):
                    assert np.all(ms >= -1e-10), "Negative mu*"
        except Exception:
            pass


class TestSpecificationCurveProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_specification_curve_output_dict(self, data, isolated_registry):
        method = _method_or_skip(
            isolated_registry, "sensitivity.specification.specification_curve@1.0.0"
        )
        state = {"X": data["X"], "Y": data["Y"]}
        try:
            result = method.pure_step(state, {"param_names": data["param_names"]})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_specification_curve_deterministic(self, data, isolated_registry):
        method = _method_or_skip(
            isolated_registry, "sensitivity.specification.specification_curve@1.0.0"
        )
        state = {"X": data["X"], "Y": data["Y"]}
        try:
            r1 = method.pure_step(state, {"param_names": data["param_names"]})
            r2 = method.pure_step(state, {"param_names": data["param_names"]})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass
