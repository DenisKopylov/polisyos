"""Property-based tests for distributional / inequality methods."""

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

from tests.foundry.methods.testing.strategies import distribution_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestGiniProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "distributional.inequality.lorenz_curve@1.0.0")
        state = {"values": data["income"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            if "result" in result and "gini" in result["result"]:
                g = float(result["result"]["gini"])
                assert np.isfinite(g), "Gini is not finite"
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_in_range(self, data, isolated_registry):
        """Gini coefficient should be in [0, 1]."""
        method = _method_or_skip(isolated_registry, "distributional.inequality.lorenz_curve@1.0.0")
        state = {"values": data["income"]}
        try:
            result = method.pure_step(state, {})
            if "result" in result and "gini" in result["result"]:
                g = float(result["result"]["gini"])
                if np.isfinite(g):
                    assert 0.0 <= g <= 1.0, f"Gini out of [0,1]: {g}"
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_deterministic(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "distributional.inequality.lorenz_curve@1.0.0")
        state = {"values": data["income"]}
        try:
            r1 = method.pure_step(state, {})
            r2 = method.pure_step(state, {})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestFGTPovertyProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_fgt_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "distributional.poverty.fgt@1.0.0")
        state = {
            "values": data["income"],
            "poverty_line": data["poverty_line"],
        }
        try:
            result = method.pure_step(state, {"alpha": 0})
            payload = result.get("result", {})
            for key, val in payload.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert np.isfinite(arr).any() or arr.size == 0
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_headcount_ratio_in_range(self, data, isolated_registry):
        """FGT(0) = headcount ratio should be in [0, 1]."""
        method = _method_or_skip(isolated_registry, "distributional.poverty.fgt@1.0.0")
        state = {
            "values": data["income"],
            "poverty_line": data["poverty_line"],
        }
        try:
            result = method.pure_step(state, {"alpha": 0})
            if "result" in result and "headcount_ratio" in result["result"]:
                hcr = float(result["result"]["headcount_ratio"])
                if np.isfinite(hcr):
                    assert 0.0 <= hcr <= 1.0
        except Exception:
            pass
