import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim import (
    ComputeMode,
    DistributionAwareTaxMechanism,
    DistributionConfig,
    RelativeConsumptionMechanism,
    TargetedTransferMechanism,
    compute_gini_hard,
    compute_gini_soft,
    compute_quantiles_hard,
    compute_ranks_hard,
    create_distribution_aware_executor,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.types import FidelityLevel


def test_gini_known_distributions() -> None:
    equal_values = jnp.ones(1000, dtype=jnp.float32) * 100.0
    active = jnp.ones(1000, dtype=jnp.bool_)
    gini_equal = compute_gini_hard(equal_values, active)
    assert float(gini_equal) < 0.01

    unequal_values = jnp.zeros(1000, dtype=jnp.float32)
    unequal_values = unequal_values.at[0].set(1_000_000.0)
    gini_unequal = compute_gini_hard(unequal_values, active)
    assert float(gini_unequal) > 0.99


def test_quantiles_sorted() -> None:
    values = jax.random.normal(jax.random.PRNGKey(0), (10000,)) + 10.0
    active = jnp.ones(10000, dtype=jnp.bool_)
    quantiles = compute_quantiles_hard(values, active, 10)
    assert bool(jnp.all(quantiles[1:] >= quantiles[:-1]))


def test_soft_hard_consistency() -> None:
    values = jax.random.uniform(jax.random.PRNGKey(0), (1000,))
    active = jnp.ones(1000, dtype=jnp.bool_)
    gini_hard = compute_gini_hard(values, active)
    gini_soft = compute_gini_soft(values, active, temperature=0.1)
    denom = jnp.maximum(gini_hard, 1e-6)
    assert bool(jnp.abs(gini_hard - gini_soft) / denom < 0.1)


def test_active_mask_respected() -> None:
    values = jnp.array([1.0, 2.0, 3.0, 4.0, 5.0, 1000.0], dtype=jnp.float32)
    active = jnp.array([True, True, True, True, True, False])
    gini_with_outlier = compute_gini_hard(values, active)
    assert float(gini_with_outlier) < 0.3


def test_ranks_unique() -> None:
    values = jnp.arange(100, dtype=jnp.float32)
    active = jnp.ones(100, dtype=jnp.bool_)
    ranks = compute_ranks_hard(values, active)
    assert int(jnp.unique(ranks).size) == 100


def test_distribution_update_frequency() -> None:
    config = DistributionConfig(update_frequency=2, mode=ComputeMode.HARD)
    executor = create_distribution_aware_executor([], config)
    state = GlobalState.empty(n_agents=4, seed=0)

    update_steps = []
    for step in range(6):
        state, _ = executor.step(state)
        if int(state.distributions.last_update_step) == int(state.time_step - 1):
            update_steps.append(step)

    assert update_steps == [0, 2, 4]


def test_distribution_aware_tax_uses_ranks() -> None:
    state = GlobalState.empty(n_agents=2, seed=0)
    agents = state.agents.replace(
        income=jnp.array([100.0, 100.0], dtype=jnp.float32),
        active=jnp.array([True, True]),
    )
    distributions = state.distributions.replace(
        income_ranks=jnp.array([0.0, 1.0], dtype=jnp.float32),
        last_update_step=state.time_step,
    )
    state = state.replace(agents=agents, distributions=distributions)

    mech = DistributionAwareTaxMechanism(base_rate=0.1, progressivity=0.2)
    new_state, _ = mech.apply(state, None, FidelityLevel.SURROGATE_FLUID)
    assert float(new_state.agents.income[0]) > float(new_state.agents.income[1])


def test_targeted_transfers_apply_to_bottom() -> None:
    state = GlobalState.empty(n_agents=2, seed=0)
    agents = state.agents.replace(
        income=jnp.array([10.0, 10.0], dtype=jnp.float32),
        active=jnp.array([True, True]),
    )
    distributions = state.distributions.replace(
        income_ranks=jnp.array([0.1, 0.9], dtype=jnp.float32),
        last_update_step=state.time_step,
    )
    state = state.replace(agents=agents, distributions=distributions)

    mech = TargetedTransferMechanism(total_budget=100.0, target_percentile=0.3)
    new_state, metrics = mech.apply(state, None, FidelityLevel.SURROGATE_FLUID)
    assert float(new_state.agents.income[0]) > float(state.agents.income[0])
    assert float(new_state.agents.income[1]) == float(state.agents.income[1])
    assert float(metrics["total_transferred"]) > 0.0


def test_relative_consumption_sets_adjustment() -> None:
    state = GlobalState.empty(n_agents=3, seed=0)
    agents = state.agents.replace(
        consumption=jnp.array([1.0, 2.0, 3.0], dtype=jnp.float32),
        active=jnp.array([True, True, True]),
    )
    distributions = state.distributions.replace(
        consumption_quantiles=jnp.array([1.0, 2.0, 3.0], dtype=jnp.float32),
        wealth_ranks=jnp.array([0.1, 0.5, 0.9], dtype=jnp.float32),
        last_update_step=state.time_step,
    )
    state = state.replace(agents=agents, distributions=distributions)

    mech = RelativeConsumptionMechanism(
        comparison_intensity=0.5,
        reference_type="median",
    )
    new_state, _ = mech.apply(state, None, FidelityLevel.SURROGATE_FLUID)
    assert float(new_state.agents.utility_adjustment[0]) < 0.0
    assert float(new_state.agents.utility_adjustment[1]) == 0.0
    assert float(new_state.agents.utility_adjustment[2]) == 0.0
