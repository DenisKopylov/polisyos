"""Current-population readers and explicitly dated distribution snapshots."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.analysis import BehaviorAnalyzer
from polisyos.foundry.agent_sim.credit_assignment import CentralizedCritic
from polisyos.foundry.agent_sim.distribution_executor import DistributionAwareExecutor
from polisyos.foundry.agent_sim.distributions import (
    DistributionConfig,
    RewardConfig,
    compress_distribution_state,
    compute_distribution_aware_reward,
    compute_gini_hard,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.government_policy import (
    GovernmentTrainingConfig,
    build_government_welfare_reward,
)
from polisyos.foundry.agent_sim.mechanisms import ConsumptionMechanism
from polisyos.foundry.agent_sim.metrics import MetricsCollector, standard_training_metrics
from polisyos.foundry.agent_sim.modes import social_welfare_objective
from polisyos.foundry.agent_sim.policy import SharedPolicy
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.methods.catalog.simulation.dynamics import AgentPopulationSimulationEstimator
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.foundry.plugins.economics.objectives import SocialWelfareObjective

_READERS = (
    "critic-wealth",
    "critic-income",
    "metric",
    "mode",
    "government",
    "reward",
    "analysis",
    "method",
)


def _current_gini_reader(name):
    if name.startswith("critic"):
        slot = 4 if name == "critic-wealth" else 5
        return lambda s: CentralizedCritic.build_global_observations(s)[slot]
    if name == "metric":
        definitions = [d for d in standard_training_metrics() if d.name == "gini_wealth"]
        collector = MetricsCollector(definitions, max_history=2)
        return lambda s: collector.collect(s).get_latest("gini_wealth")
    if name == "mode":
        return lambda s: -social_welfare_objective(s, {"neg_gini": 1.0})
    if name == "government":
        reward = build_government_welfare_reward(
            GovernmentTrainingConfig(welfare_weights={"neg_gini": 1.0})
        )
        return lambda s: -reward(s)
    if name == "reward":
        unpenalized = RewardConfig(penalize_inequality=False)
        penalized = RewardConfig(penalize_inequality=True, inequality_weight=1.0)
        return lambda s: (
            compute_distribution_aware_reward(s, s, unpenalized)
            - compute_distribution_aware_reward(s, s, penalized)
        )[0]
    if name == "analysis":
        executor = PureExecutor([], aggregate_every=1, compute_gini=False)
        return lambda s: BehaviorAnalyzer.counterfactual_analysis(None, s, {}, executor, n_steps=2)[
            "baseline_gini"
        ]
    if name == "method":
        return lambda s: AgentPopulationSimulationEstimator.pure_step(
            {
                "initial_wealth": s.agents.wealth,
                "initial_income": s.agents.income,
                "active_mask": s.agents.active,
            },
            {"mechanism_names": (), "n_steps": 2},
        )["result"]["final_gini"]
    raise AssertionError(name)


def _state(values, *, income=False):
    state = GlobalState.empty(n_agents=len(values), seed=7)
    fields = {
        "wealth": jnp.asarray(values),
        "income": jnp.ones(len(values)),
        "consumption": jnp.ones(len(values)),
    }
    if income:
        fields.update(wealth=jnp.ones(len(values)), income=jnp.asarray(values))
    return state.replace(agents=state.agents.replace(**fields))


@pytest.mark.parametrize("reader", _READERS)
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_live_readers_measure_current_population_despite_valid_stale_snapshot(reader, compiled):
    state = _state([1.0, 3.0], income=reader == "critic-income")
    assert float(state.distributions.gini_wealth) == 0
    assert int(state.distributions.last_update_step) == -1
    evaluate = _current_gini_reader(reader)
    if compiled:
        evaluate = jax.jit(evaluate)
    assert float(evaluate(state)) == pytest.approx(1 / 4, abs=2e-7)


@pytest.mark.parametrize("reader", _READERS)
@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0], [np.nan, 1.0]])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_live_readers_refuse_invalid_current_population_before_metric_publication(
    reader, values, compiled
):
    state = _state(values, income=reader == "critic-income")
    assert float(state.distributions.gini_wealth) == 0
    evaluate = _current_gini_reader(reader)
    if compiled:
        evaluate = jax.jit(evaluate)
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(evaluate(state))


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_non_gini_rewards_continue_to_allow_signed_resource_simulation(compiled):
    state = _state([-2.0, 1.0])
    mode = lambda s: social_welfare_objective(s, {"gdp": 1.0})
    government = build_government_welfare_reward(
        GovernmentTrainingConfig(welfare_weights={"gdp": 1.0})
    )
    for function in (mode, government):
        evaluate = jax.jit(function) if compiled else function
        assert np.isfinite(float(evaluate(state)))
    result = compute_distribution_aware_reward(
        state, state, RewardConfig(penalize_inequality=False)
    )
    assert np.isfinite(np.asarray(result)).all()


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_social_welfare_uses_current_gini_with_original_sign_and_weight(compiled):
    before = EconomicState.empty(n_agents=2, seed=7)
    current = before.replace(agents=before.agents.replace(wealth=jnp.asarray([1.0, 3.0])))
    evaluate = SocialWelfareObjective({"neg_gini": 0.7}).evaluate
    if compiled:
        evaluate = jax.jit(evaluate)
    assert float(evaluate(current)) == pytest.approx(-0.7 / 4, abs=2e-7)
    invalid = current.replace(agents=current.agents.replace(wealth=jnp.asarray([-2.0, 1.0])))
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
    ):
        jax.block_until_ready(evaluate(invalid))


def test_real_wealth_visualization_admits_current_population_before_modifying_axes():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plugin = EconomicsPlugin()
    state = EconomicState.empty(n_agents=2, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray([1.0, 3.0])))
    _, ax = plt.subplots()
    try:
        assert plugin.get_visualizations()["wealth_distribution"](state, ax) is ax
        assert ax.get_title() == "Wealth Distribution (Gini: 0.250)"
        before = len(ax.patches), ax.get_title()
        invalid = state.replace(agents=state.agents.replace(wealth=jnp.asarray([-2.0, 1.0])))
        with pytest.raises(
            (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
        ):
            plugin.get_visualizations()["wealth_distribution"](invalid, ax)
        assert (len(ax.patches), ax.get_title()) == before
    finally:
        plt.close(ax.figure)


def test_distribution_executor_exposes_dated_snapshot_not_current_population():
    # A real consumption transition changes resources after the scheduled refresh.
    policy = SharedPolicy(10, 1, (), key=jax.random.PRNGKey(3))
    initial = _state([1.0, 3.0])
    executor = DistributionAwareExecutor(
        [ConsumptionMechanism(policy)],
        distribution_config=DistributionConfig(update_frequency=8, n_quantiles=10),
    )
    first, metrics = executor.step(initial)
    assert int(first.time_step) == 1
    assert int(first.distributions.last_update_step) == 0
    assert float(metrics["gini_wealth"]) == pytest.approx(1 / 4, abs=2e-7)
    assert float(compute_gini_hard(first.agents.wealth, first.agents.active)) != pytest.approx(
        float(metrics["gini_wealth"]), abs=1e-4
    )
    second, metrics2 = executor.step(first)
    assert int(second.time_step) == 2 and int(second.distributions.last_update_step) == 0
    assert float(metrics2["gini_wealth"]) == float(metrics["gini_wealth"])
    compact = compress_distribution_state(second.distributions)
    assert int(compact.last_update_step) == 0
    assert float(compact.gini_wealth) == float(metrics["gini_wealth"])
