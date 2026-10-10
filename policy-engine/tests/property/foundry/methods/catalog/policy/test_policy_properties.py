"""Property-based tests for policy evaluation and social welfare methods."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import _finite_array, distribution_strategy


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


def _run(registry, dispatcher, fqn, state, params=None):
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=registry.get(fqn),
        state=state,
        bound_inputs=state,
        params=params or {},
        seed=17,
    ).output


class TestCostBenefitProperties:
    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cba_output_finite(self, data, isolated_registry, property_method_dispatcher):
        state = {"benefits": data["benefits"], "costs": data["costs"]}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "policy.welfare.cost_benefit_analysis@1.0.0",
            state,
            {"discount_rate": data["discount_rate"]},
        )["result"]
        assert np.isfinite(float(result["npv"]))
        assert np.isfinite(float(result["bcr"]))

    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_positive_npv_when_benefits_exceed_costs(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """A strictly positive discounted net flow yields positive NPV."""
        costs = np.asarray(data["costs"], dtype=float)
        state = {"costs": costs, "benefits": costs * 3.0 + 1.0}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "policy.welfare.cost_benefit_analysis@1.0.0",
            state,
            {"discount_rate": 0.05},
        )["result"]
        assert float(result["npv"]) > 0.0

    @given(data=cost_benefit_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_cba_deterministic(self, data, isolated_registry, property_method_dispatcher):
        state = {"benefits": data["benefits"], "costs": data["costs"]}
        params = {"discount_rate": data["discount_rate"]}
        fqn = "policy.welfare.cost_benefit_analysis@1.0.0"
        first = _run(isolated_registry, property_method_dispatcher, fqn, state, params)["result"]
        second = _run(isolated_registry, property_method_dispatcher, fqn, state, params)["result"]
        # Compare the complete result schema emitted by the CBA method.
        assert first == second


class TestSocialWelfareProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_utilitarian_swf_output_dict(self, data, isolated_registry, property_method_dispatcher):
        values = np.asarray(data["income"], dtype=float)
        weights = np.asarray(data["weights"], dtype=float)
        state = {"values": values}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "policy.welfare.utilitarian_swf@1.0.0",
            state,
            {"weights": weights},
        )["result"]
        assert np.isfinite(float(result["welfare"]))
        assert float(result["welfare"]) == float(np.sum(weights * values))
        assert int(result["n_agents"]) == values.size

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_rawlsian_swf_output_finite(self, data, isolated_registry, property_method_dispatcher):
        """Rawlsian welfare equals the least utility in the supplied vector."""
        values = np.asarray(data["income"], dtype=float)
        state = {"values": values}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "policy.welfare.rawlsian_swf@1.0.0",
            state,
        )["result"]
        assert np.isfinite(float(result["welfare"]))
        assert float(result["welfare"]) == float(np.min(values))
