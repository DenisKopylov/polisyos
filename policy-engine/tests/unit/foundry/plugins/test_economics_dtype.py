"""Native dtype and masked-statistic contracts for the economics plugin."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import compute_gini_hard
from polisyos.foundry.plugins.core import DomainConfig
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState

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
