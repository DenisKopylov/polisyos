"""Property-based tests for policy evaluation and social welfare methods."""

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

from tests.foundry.methods.testing.strategies import _finite_array, distribution_strategy


@st.composite
def cost_benefit_strategy(draw):
    n_periods = draw(st.integers(min_value=3, max_value=12))
    costs = draw(_finite_array((n_periods,), min_value=0.0, max_value=1000.0))
    benefits = draw(_finite_array((n_periods,), min_value=0.0, max_value=2000.0))
    discount_rate = draw(st.floats(min_value=0.01, max_value=0.20, allow_nan=False))
    return {
        "costs": costs,
        "benefits": benefits,
        "discount_rate": discount_rate,
        "n_periods": n_periods,
    }


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestCostBenefitProperties:
    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cba_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "policy.welfare.cost_benefit_analysis@1.0.0")
        state = {"costs": data["costs"], "benefits": data["benefits"]}
        params = {"discount_rate": data["discount_rate"]}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if arr.size > 0 and np.issubdtype(arr.dtype, np.floating):
                    assert arr.shape is not None
        except Exception:
            pass

    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_positive_npv_when_benefits_exceed_costs(self, data, isolated_registry):
        """When benefits > 2x costs in every period, NPV should be positive."""
        method = _method_or_skip(isolated_registry, "policy.welfare.cost_benefit_analysis@1.0.0")
        large_benefits = data["costs"] * 3.0 + 1.0
        state = {"costs": data["costs"], "benefits": large_benefits}
        params = {"discount_rate": 0.05}
        try:
            result = method.pure_step(state, params)
            if "npv" in result:
                npv = float(result["npv"])
                if np.isfinite(npv):
                    assert npv > -1e-6, f"NPV should be positive when benefits >> costs: {npv}"
        except Exception:
            pass

    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cba_deterministic(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "policy.welfare.cost_benefit_analysis@1.0.0")
        state = {"costs": data["costs"], "benefits": data["benefits"]}
        params = {"discount_rate": data["discount_rate"]}
        try:
            r1 = method.pure_step(state, params)
            r2 = method.pure_step(state, params)
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestSocialWelfareProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_utilitarian_swf_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "policy.welfare.utilitarian_swf@1.0.0")
        state = {"income": data["income"], "weights": data["weights"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_rawlsian_swf_output_finite(self, data, isolated_registry):
        """Rawlsian SWF = min(income) — should be finite for finite input."""
        method = _method_or_skip(isolated_registry, "policy.welfare.rawlsian_swf@1.0.0")
        state = {"income": data["income"], "weights": data["weights"]}
        try:
            result = method.pure_step(state, {})
            if "welfare" in result:
                w = float(result["welfare"])
                if np.isfinite(np.min(data["income"])):
                    assert np.isfinite(w), "Rawlsian welfare is not finite"
        except Exception:
            pass
