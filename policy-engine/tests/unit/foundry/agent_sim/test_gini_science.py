"""Independent pairwise oracles for the exact active-agent Gini statistic."""

from __future__ import annotations

import itertools
from fractions import Fraction

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import ComputeMode, compute_gini, compute_gini_hard
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState as AgentSimState
from polisyos.foundry.agent_sim.state import compute_aggregates
from polisyos.foundry.agent_sim.wiring.executors import _compute_distribution_state
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.plugins.core import DomainConfig
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState


def _pairwise_gini(values: list[int]) -> float:
    """Use the defining double sum, independent of sorted ranks or epsilons."""
    if not values or not any(values):
        return 0.0
    numerator = sum(abs(left - right) for left in values for right in values)
    return float(Fraction(numerator, 2 * len(values) * sum(values)))


_PROFILES = [
    [1, 2, 3],
    [1, 1, 1],
    [0, 0, 3],
    [0, 2, 2],
    [1, 2, 7],
    [0, 0, 0],
]


@pytest.mark.parametrize("x64", [False, True], ids=["float32", "float64"])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize("scale", [1e-30, 1e-12, 1.0, 1e30])
@pytest.mark.parametrize("profile", _PROFILES)
def test_exact_gini_matches_pairwise_oracle_across_units(
    x64: bool, compiled: bool, scale: float, profile: list[int]
) -> None:
    with jax.enable_x64(x64):
        dtype = jnp.float64 if x64 else jnp.float32
        # An inactive NaN must not enter sorting, normalization, or the denominator.
        values = jnp.asarray(
            [profile[0] * scale, np.nan, *[x * scale for x in profile[1:]]], dtype=dtype
        )
        active = jnp.asarray([True, False, True, True])
        function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
        actual = function(values, active)
        assert actual.dtype == dtype
        assert actual.shape == ()
        assert float(actual) == pytest.approx(_pairwise_gini(profile), abs=2e-7)
        permutation = jnp.asarray([3, 1, 0, 2])
        changed = values.at[1].set(-jnp.inf)
        assert float(function(changed[permutation], active[permutation])) == pytest.approx(
            _pairwise_gini(profile), abs=2e-7
        )


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_exact_gini_exhaustive_small_nonnegative_population(compiled: bool) -> None:
    function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
    active = jnp.ones(3, dtype=jnp.bool_)
    for values in itertools.product(range(3), repeat=3):
        actual = function(jnp.asarray(values, dtype=jnp.float32), active)
        assert float(actual) == pytest.approx(_pairwise_gini(list(values)), abs=1e-7)


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_float64_gini_survives_extreme_finite_rescaling(compiled: bool) -> None:
    with jax.enable_x64(True):
        function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
        for scale in (1e-300, 1e300, 1e307):
            actual = function(
                jnp.asarray([scale, 2 * scale, 3 * scale]), jnp.ones(3, dtype=jnp.bool_)
            )
            assert float(actual) == pytest.approx(2 / 9, abs=1e-14)


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_float32_gini_normalizes_before_sum_overflow(compiled: bool) -> None:
    function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
    values = jnp.asarray([1e38, 2e38, 3e38], dtype=jnp.float32)
    assert np.isfinite(np.asarray(values)).all()
    assert float(function(values, jnp.ones(3, dtype=jnp.bool_))) == pytest.approx(2 / 9, abs=2e-7)


@pytest.mark.parametrize("x64", [False, True], ids=["float32", "float64"])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize("empty_shape", [False, True], ids=["masked", "empty"])
def test_no_active_population_has_typed_zero(x64: bool, compiled: bool, empty_shape: bool) -> None:
    with jax.enable_x64(x64):
        dtype = jnp.float64 if x64 else jnp.float32
        values = jnp.asarray([] if empty_shape else [np.nan, np.inf, -np.inf], dtype=dtype)
        function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
        actual = function(values, jnp.zeros(values.shape, dtype=jnp.bool_))
        assert actual.dtype == dtype
        assert float(actual) == 0.0


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_signed_zero_mean_is_refused_by_the_classical_metric_domain(compiled: bool) -> None:
    function = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
    with pytest.raises(RuntimeError, match="classical Gini requires finite nonnegative"):
        jax.block_until_ready(function(jnp.asarray([-1.0, 1.0]), jnp.asarray([True, True])))
    # Refuse during the real refresh before the registered objective receives a scalar.
    plugin = EconomicsPlugin()
    state = EconomicState.empty(n_agents=2, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray([-1.0, 1.0])))
    evaluate = lambda: plugin.get_objectives()["gini"].evaluate(
        jax.jit(EconomicState.update_aggregates)(state)
    )
    with pytest.raises(RuntimeError, match="classical Gini requires finite nonnegative"):
        jax.block_until_ready(evaluate())


@pytest.mark.parametrize("x64", [False, True], ids=["float32", "float64"])
def test_scientific_statistic_reaches_native_plugin_and_global_state_consumers(x64: bool) -> None:
    with jax.enable_x64(x64):
        dtype = jnp.float64 if x64 else jnp.float32
        plugin = EconomicsPlugin()
        state = plugin.create_initial_state(
            DomainConfig(n_agents=12, max_agents=16), jax.random.PRNGKey(113)
        )
        values = jnp.asarray([1e-12, 2e-12, 3e-12] * 4 + [np.nan] * 4, dtype=dtype)
        state = state.replace(agents=state.agents.replace(wealth=values, income=values))
        refreshed = jax.jit(EconomicState.update_aggregates)(state)
        assert float(jax.jit(plugin.get_objectives()["gini"].evaluate)(refreshed)) == pytest.approx(
            2 / 9, abs=2e-7
        )
        assert float(refreshed.distributions.gini_income) == pytest.approx(2 / 9, abs=2e-7)
        observations = jax.jit(plugin.get_observation_builder())(refreshed)
        # JIT division may use a rounded reciprocal in the input precision.
        np.testing.assert_allclose(
            np.asarray(observations[:12, 0]),
            np.asarray(values[:12]) / 100000.0,
            rtol=4 * np.finfo(np.asarray(values).dtype).eps,
        )

        global_state = GlobalState.empty(n_agents=3, n_firms=1)
        tiny = jnp.asarray([1e-12, 2e-12, 3e-12], dtype=dtype)
        global_state = global_state.replace(
            agents=global_state.agents.replace(income=tiny, savings=tiny)
        )
        distribution = jax.jit(lambda value: _compute_distribution_state(value, n_quantiles=3))(
            global_state
        )
        assert float(distribution.gini_income) == pytest.approx(2 / 9, abs=2e-7)
        assert float(distribution.gini_wealth) == pytest.approx(2 / 9, abs=2e-7)
        assert float(
            compute_gini(tiny, global_state.agents.active, mode=ComputeMode.HARD)
        ) == pytest.approx(2 / 9, abs=2e-7)


@pytest.mark.parametrize("scale", [0.0, 1e-12, 1.0, 1e30])
def test_native_aggregate_and_pure_executor_share_active_population_oracle(scale) -> None:
    state = AgentSimState.empty(n_agents=3, max_agents=4, seed=11)
    agents = state.agents.replace(
        active=jnp.asarray([True, False, True, True]),
        wealth=jnp.asarray([scale, 1e12, 2 * scale, 3 * scale], dtype=jnp.float32),
    )
    state = state.replace(agents=agents)
    expected = 0.0 if scale == 0 else 2 / 9
    direct = jax.jit(lambda value: compute_aggregates(value, compute_gini=True))(agents)
    assert float(direct.gini_coefficient) == pytest.approx(expected, abs=2e-7)
    executor = PureExecutor([], aggregate_every=1, compute_gini=True)
    result, metrics = executor.run(state, n_steps=2)
    assert metrics == {}
    assert int(result.time_step) == 2
    assert float(result.aggregates.gini_coefficient) == pytest.approx(expected, abs=2e-7)
    assert result.aggregates.gini_coefficient.dtype == jnp.float32
    np.testing.assert_array_equal(result.agents.wealth, agents.wealth)
