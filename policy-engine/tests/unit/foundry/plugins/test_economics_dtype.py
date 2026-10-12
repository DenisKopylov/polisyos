"""Native dtype and masked-statistic contracts for the economics plugin."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import compute_gini_hard
from polisyos.foundry.plugins.core import DomainConfig
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.foundry.plugins.economics.mechanisms import (
    ConsumptionMechanism,
    SavingsMechanism,
)

_DTYPE_CASES = [
    pytest.param(jnp.float32, False, jnp.float32, jnp.float32, id="float32-default"),
    pytest.param(jnp.float32, True, jnp.float32, jnp.float32, id="float32-x64"),
    pytest.param(jnp.float64, True, jnp.float64, jnp.float64, id="float64-x64"),
    pytest.param(jnp.int32, False, jnp.float32, jnp.float32, id="integer-default"),
    pytest.param(jnp.int32, True, jnp.float64, jnp.float64, id="integer-x64"),
    pytest.param(jnp.float16, True, jnp.float32, jnp.float16, id="float16-x64"),
    pytest.param(jnp.bfloat16, True, jnp.float32, jnp.bfloat16, id="bfloat16-x64"),
]


def _pairwise_gini(values: np.ndarray) -> float:
    if not len(values):
        return 0.0
    differences = np.abs(values[:, None] - values[None, :])
    return float(differences.sum() / (2 * len(values) * values.sum()))


@pytest.mark.parametrize("dtype,x64,gini_dtype,median_dtype", _DTYPE_CASES)
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize("all_inactive", [False, True], ids=["active", "inactive"])
@pytest.mark.parametrize("statistic", ["gini", "median"])
def test_masked_statistics_preserve_computation_dtype(
    dtype, x64, gini_dtype, median_dtype, compiled, all_inactive, statistic
) -> None:
    with jax.enable_x64(x64):
        values = jnp.asarray([1, 987, 3], dtype=dtype)
        active = jnp.asarray([False, False, False] if all_inactive else [True, False, True])
        function = compute_gini_hard if statistic == "gini" else EconomicState._median_active
        if compiled:
            function = jax.jit(function)

        selected = np.asarray([1, 3], dtype=np.float64) if not all_inactive else np.asarray([])
        if statistic == "gini":
            expected = _pairwise_gini(selected)
            expected_dtype = gini_dtype
        else:
            expected = float(np.sort(selected)[(len(selected) - 1) // 2]) if len(selected) else 0.0
            expected_dtype = median_dtype

        actual = function(values, active)
        assert actual.shape == ()
        assert actual.dtype == jnp.dtype(expected_dtype)
        assert float(actual) == pytest.approx(expected, abs=1e-7)

        # Inactive values and their location cannot change either statistic.
        changed = values.at[1].set(-987)
        permutation = jnp.asarray([2, 0, 1])
        perturbed = function(changed[permutation], active[permutation])
        assert perturbed.dtype == actual.dtype
        assert float(perturbed) == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_float64_lower_median_keeps_values_beyond_float32_precision(compiled) -> None:
    with jax.enable_x64(True):
        values = jnp.asarray([2**24 + 1, 1e12, 2**24 + 3], dtype=jnp.float64)
        active = jnp.asarray([True, False, True])
        function = (
            jax.jit(EconomicState._median_active) if compiled else EconomicState._median_active
        )
        actual = function(values, active)
        assert actual.dtype == jnp.float64
        assert float(actual) == 2**24 + 1


@pytest.mark.parametrize("x64", [False, True], ids=["default", "x64"])
def test_native_plugin_factory_statistics_reach_objective_and_observation_consumers(x64) -> None:
    with jax.enable_x64(x64):
        plugin = EconomicsPlugin()
        state = plugin.create_initial_state(
            DomainConfig(n_agents=20, max_agents=24), jax.random.PRNGKey(913)
        )
        wealth_dtype = jnp.float64 if x64 else jnp.float32
        assert state.agents.wealth.dtype == wealth_dtype
        active = np.asarray(state.agents.active)
        selected = np.asarray(state.agents.wealth, dtype=np.float64)[active]
        expected_gini = _pairwise_gini(selected)
        expected_median = float(np.sort(selected)[(len(selected) - 1) // 2])

        # Invoke the real JIT refresh and registered objective/observation consumers.
        refreshed = jax.jit(EconomicState.update_aggregates)(state)
        objective = jax.jit(plugin.get_objectives()["gini"].evaluate)(refreshed)
        observations = jax.jit(plugin.get_observation_builder())(refreshed)
        assert objective.dtype == wealth_dtype
        assert float(objective) == pytest.approx(expected_gini, abs=1e-6)
        assert refreshed.distributions.median_wealth.dtype == wealth_dtype
        assert float(refreshed.distributions.median_wealth) == expected_median
        assert observations.shape == (24, 6)
        np.testing.assert_allclose(
            np.asarray(observations[:, 0]), np.asarray(state.agents.wealth) / 100000.0, rtol=1e-6
        )
        assert np.isfinite(np.asarray(observations)).all()


def _assert_conditional_state_abi(candidate: EconomicState, template: EconomicState) -> None:
    """Trace the actual JAX conditional that carries a complete economics state."""
    jax.eval_shape(
        lambda predicate: jax.lax.cond(
            predicate,
            lambda _: candidate,
            lambda _: template,
            operand=None,
        ),
        jnp.asarray(True, dtype=jnp.bool_),
    )


@pytest.mark.parametrize("x64_enabled", [False, True], ids=["x64-off", "x64-on"])
def test_builtin_economics_producers_preserve_complete_conditional_state_abi(
    x64_enabled: bool,
) -> None:
    """Every plugin producer keeps the full state pytree compatible under x64."""
    with jax.enable_x64(x64_enabled):
        plugin = EconomicsPlugin()
        state = plugin.create_initial_state(
            DomainConfig(n_agents=10, max_agents=11), jax.random.PRNGKey(31)
        )

        for mechanism in plugin.get_mechanisms():
            candidate = mechanism.apply(state, rng_key=jax.random.PRNGKey(32))
            _assert_conditional_state_abi(candidate, state)


def test_consumption_wealth_uses_the_value_stored_in_its_target_slot() -> None:
    """Wealth uses rounded stored consumption when x64 inputs feed an f32 slot."""
    with jax.enable_x64(True):
        state = EconomicsPlugin().create_initial_state(
            DomainConfig(n_agents=10, max_agents=10), jax.random.PRNGKey(41)
        )
        agents = state.agents.replace(
            wealth=jnp.full_like(state.agents.wealth, 2**24 + 1),
            income=jnp.full_like(state.agents.income, 7.0),
            consumption_preference=jnp.full_like(state.agents.consumption_preference, 0.65),
        )
        result = ConsumptionMechanism().apply(state.replace(agents=agents))

        wealth = float(agents.wealth[0])
        income = float(agents.income[0])
        preference = float(agents.consumption_preference[0])
        unrounded_consumption = income * preference + wealth * 0.02
        expected_stored_consumption = np.asarray(
            unrounded_consumption, dtype=np.asarray(agents.consumption).dtype
        ).item()
        expected_wealth = wealth + income - expected_stored_consumption
        actual_wealth = float(result.agents.wealth[0])

        assert result.agents.consumption.dtype == agents.consumption.dtype
        assert float(result.agents.consumption[0]) == expected_stored_consumption
        assert actual_wealth == expected_wealth
        assert abs(actual_wealth - (wealth + income - unrounded_consumption)) > 0.01


def test_savings_interest_uses_the_value_stored_in_its_target_slot() -> None:
    """Interest uses rounded stored savings when x64 inputs feed an f32 slot."""
    with jax.enable_x64(True):
        state = EconomicsPlugin().create_initial_state(
            DomainConfig(n_agents=10, max_agents=10), jax.random.PRNGKey(42)
        )
        agents = state.agents.replace(
            active=jnp.ones_like(state.agents.active),
            wealth=jnp.full_like(state.agents.wealth, 2**24 + 1),
            consumption=jnp.full_like(state.agents.consumption, 0.5),
        )
        policy = state.policy.replace(interest_rate=jnp.full_like(state.policy.interest_rate, 0.75))
        result = SavingsMechanism().apply(state.replace(agents=agents, policy=policy))

        wealth = float(agents.wealth[0])
        consumption = float(agents.consumption[0])
        rate = float(policy.interest_rate)
        unrounded_savings = wealth - consumption
        slot_dtype = np.asarray(agents.savings).dtype
        rate_dtype = np.asarray(policy.interest_rate).dtype
        operation_dtype = np.result_type(slot_dtype, rate_dtype)
        expected_stored_savings = np.asarray(unrounded_savings, dtype=slot_dtype).item()
        expected_interest = np.asarray(
            np.asarray(expected_stored_savings, dtype=slot_dtype)
            * np.asarray(rate, dtype=rate_dtype)
            / np.asarray(12.0, dtype=operation_dtype),
            dtype=operation_dtype,
        ).item()
        expected_wealth = wealth + expected_interest
        actual_wealth = float(result.agents.wealth[0])
        unrounded_wealth = wealth + unrounded_savings * rate / 12.0

        assert result.agents.savings.dtype == agents.savings.dtype
        assert float(result.agents.savings[0]) == expected_stored_savings
        assert actual_wealth == expected_wealth
        assert abs(actual_wealth - unrounded_wealth) > 0.003
