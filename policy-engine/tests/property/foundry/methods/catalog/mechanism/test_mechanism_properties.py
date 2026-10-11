
"""Property-based tests for mechanism runtime methods."""

from __future__ import annotations

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

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method


@st.composite
def _tax_data(draw):
    n = draw(st.integers(min_value=10, max_value=100))
    income = draw(
        arrays(
            np.float64,
            (n,),
            elements=st.floats(100.0, 100000.0, allow_nan=False, allow_infinity=False),
        )
    )
    rate = draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False))
    return {"income": income, "rate": rate, "n": n}


def _runtime_state(income: np.ndarray):
    import jax.numpy as jnp

    from polisyos.foundry.agent_sim.state import GlobalState

    population = GlobalState.empty(n_agents=len(income), seed=42, max_agents=len(income))
    return population.replace(
        agents=population.agents.replace(income=jnp.asarray(income, dtype=jnp.float32))
    )


def _tax_subsidy_output(data, rate, isolated_registry, property_method_dispatcher):
    fqn = "mechanism.runtime.tax_subsidy@1.0.0"
    method_class = isolated_registry.get(fqn)
    runtime_state = _runtime_state(np.asarray(data["income"], dtype=float))
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=method_class,
        state=runtime_state,
        bound_inputs={"runtime_state": runtime_state},
        params={"rate": rate},
        seed=42,
    ).output["result"]


class TestTaxSubsidyProperties:
    @given(data=_tax_data())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_revenue_non_negative(self, data, isolated_registry, property_method_dispatcher):
        """Legacy selector: non-negative rates emit non-negative subsidy patches."""
        result = _tax_subsidy_output(
            data, data["rate"], isolated_registry, property_method_dispatcher
        )
        patches = result["patches"]
        subsidy = np.asarray(patches["agents.income"][0]["delta"], dtype=float)
        government_delta = float(patches["government.balance"][0]["delta"])

        assert result["mechanism_type"] == "tax_subsidy"
        assert np.isfinite(subsidy).all()
        assert np.all(subsidy >= 0.0)
        np.testing.assert_allclose(subsidy, data["income"] * data["rate"], rtol=1e-6, atol=1e-4)
        assert government_delta == pytest.approx(-float(np.sum(subsidy)), rel=1e-6, abs=1e-4)

    @given(data=_tax_data())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_output_finite(self, data, isolated_registry, property_method_dispatcher):
        result = _tax_subsidy_output(
            data, data["rate"], isolated_registry, property_method_dispatcher
        )
        patches = result["patches"]
        subsidy = np.asarray(patches["agents.income"][0]["delta"], dtype=float)
        government_delta = np.asarray(patches["government.balance"][0]["delta"], dtype=float)

        assert result["n_patch_slots"] == 2
        assert set(patches) == {"agents.income", "government.balance"}
        assert np.isfinite(subsidy).all()
        assert np.isfinite(government_delta).all()

    @given(data=_tax_data())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_zero_rate_no_tax(self, data, isolated_registry, property_method_dispatcher):
        """A zero subsidy rate emits zero transfer deltas on both affected slots."""
        result = _tax_subsidy_output(data, 0.0, isolated_registry, property_method_dispatcher)
        patches = result["patches"]
        subsidy = np.asarray(patches["agents.income"][0]["delta"], dtype=float)
        government_delta = float(patches["government.balance"][0]["delta"])

        np.testing.assert_array_equal(subsidy, np.zeros(data["n"], dtype=float))
        assert government_delta == pytest.approx(0.0, abs=1e-7)
