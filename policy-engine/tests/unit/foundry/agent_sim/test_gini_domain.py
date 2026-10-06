"""Active-population admission for classical Gini at real runtime consumers."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import (
    compute_gini_hard,
    compute_gini_proxy,
    compute_gini_soft,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState as AgentSimState
from polisyos.foundry.agent_sim.state import compute_aggregates
from polisyos.foundry.agent_sim.wiring.executors import _compute_distribution_state
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_income_quintile_breakdown,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
    CrossDomainInteraction,
)
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState


@pytest.mark.parametrize("function", [compute_gini_hard, compute_gini_soft, compute_gini_proxy])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "values", [[-2.0, 1.0], [-1.0, 2.0], [-1.0, 1.0], [np.nan, 1.0], [np.inf, 1.0]]
)
def test_classical_gini_refuses_invalid_active_population(function, compiled, values) -> None:
    evaluate = jax.jit(function) if compiled else function
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(evaluate(jnp.asarray(values), jnp.ones(2, dtype=jnp.bool_)))


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_admission_excludes_inactive_invalid_padding_and_preserves_exact_law(compiled) -> None:
    evaluate = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
    with jax.enable_x64(True):
        for scale in (0.0, 1e-300, 1e-12, 1.0, 1e300):
            values = jnp.asarray([scale, -np.inf, 2 * scale, np.nan, 3 * scale])
            mask = jnp.asarray([True, False, True, False, True])
            result = evaluate(values, mask)
            assert result.dtype == jnp.float64
            assert float(result) == pytest.approx(0 if scale == 0 else 2 / 9, abs=1e-14)
        assert float(evaluate(jnp.asarray([np.nan, -np.inf]), jnp.zeros(2, dtype=bool))) == 0


@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
@pytest.mark.parametrize(
    "consumer", ["aggregate", "executor", "native-distribution", "plugin-income", "plugin-wealth"]
)
def test_invalid_metric_is_refused_before_actual_consumer_publication(values, consumer) -> None:
    if consumer in {"aggregate", "executor"}:
        state = AgentSimState.empty(n_agents=2, seed=7)
        state = state.replace(agents=state.agents.replace(wealth=jnp.asarray(values)))
        if consumer == "aggregate":
            evaluate = lambda: jax.jit(lambda a: compute_aggregates(a, compute_gini=True))(
                state.agents
            )
        else:
            evaluate = lambda: PureExecutor([], aggregate_every=1, compute_gini=True).run(state, 2)
        # Signed resource simulation remains possible when Gini is not requested.
        unmeasured, _ = PureExecutor([], aggregate_every=1, compute_gini=False).run(state, 2)
        np.testing.assert_array_equal(unmeasured.agents.wealth, values)
    elif consumer == "native-distribution":
        state = GlobalState.empty(n_agents=2, n_firms=1)
        state = state.replace(agents=state.agents.replace(income=jnp.asarray(values)))
        evaluate = lambda: jax.jit(lambda s: _compute_distribution_state(s, n_quantiles=2))(state)
    else:
        state = EconomicState.empty(n_agents=2, seed=7)
        slot = "income" if consumer == "plugin-income" else "wealth"
        state = state.replace(agents=state.agents.replace(**{slot: jnp.asarray(values)}))
        objective = EconomicsPlugin().get_objectives()["gini"]
        # The genuine aggregate refresh must refuse before the objective sees a scalar.
        evaluate = lambda: objective.evaluate(jax.jit(EconomicState.update_aggregates)(state))
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(evaluate())


@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
def test_distributional_report_api_preserves_existing_typed_unavailable_metric(values) -> None:
    population = np.tile(np.asarray(values), 5)
    breakdown = build_income_quintile_breakdown(population, population)
    report = build_distributional_report(
        [breakdown], incomes_before=population, incomes_after=population
    )
    assert report.overall_gini_before is None
    assert report.overall_gini_after is None
    assert report.metadata["negative_values_present"] is True


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
def test_registered_objective_refuses_current_signed_population_despite_valid_cached_metric(
    compiled, values
) -> None:
    state = EconomicState.empty(n_agents=2, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray(values)))
    assert np.isfinite(float(state.distributions.gini_wealth))
    evaluate = EconomicsPlugin().get_objectives()["gini"].evaluate
    if compiled:
        evaluate = jax.jit(evaluate)
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
    ):
        jax.block_until_ready(evaluate(state))


def test_composite_interaction_current_population_is_admitted_at_registered_objective() -> None:
    registry = PluginRegistry()
    registry.clear()
    plugin = EconomicsPlugin()
    registry.register(plugin)
    state = EconomicState.empty(n_agents=12, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray([2.0, 1.0] * 6)))
    interaction = CrossDomainInteraction(
        source_domain="economics",
        target_domain="economics",
        source_field="agents.wealth",
        target_field="agents.wealth",
        transform=lambda values: values * jnp.asarray([-1.0, 1.0] * 6),
    )
    config = CompositeStateConfig(
        domains={"economics": DomainConfig(n_agents=12, enabled_mechanisms=("taxation",))},
        interactions=[interaction],
    )
    composite = CompositeState(
        domain_states={"economics": state}, time_step=jnp.asarray(0), config=config
    )
    after = CompositeExecutor(["economics"], registry).step(composite, jax.random.PRNGKey(3))
    current = after.get_domain("economics")
    np.testing.assert_array_equal(current.agents.wealth, [-2.0, 1.0] * 6)
    assert np.isfinite(float(current.distributions.gini_wealth))
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
    ):
        jax.block_until_ready(plugin.get_objectives()["gini"].evaluate(current))
