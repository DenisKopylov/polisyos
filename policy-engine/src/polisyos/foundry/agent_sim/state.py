from __future__ import annotations

from typing import TYPE_CHECKING

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int


@chex.dataclass(frozen=True)
class AgentState:
    """State-of-array layout for agent properties."""

    active: Bool[Array, "n_agents"]
    agent_id: Int[Array, "n_agents"]
    birth_step: Int[Array, "n_agents"]
    parent_id: Int[Array, "n_agents"]
    parent_slot: Int[Array, "n_agents"]
    parent_wealth_at_birth: Float[Array, "n_agents"]
    life_expectancy: Int[Array, "n_agents"]
    fertility_rate: Float[Array, "n_agents"]
    wealth: Float[Array, "n_agents"]
    income: Float[Array, "n_agents"]
    consumption: Float[Array, "n_agents"]
    savings: Float[Array, "n_agents"]
    consumption_target: Float[Array, "n_agents"]
    information_level: Float[Array, "n_agents"]
    debt: Float[Array, "n_agents"]
    employed: Bool[Array, "n_agents"]
    retired: Bool[Array, "n_agents"]
    utility_adjustment: Float[Array, "n_agents"]
    risk_aversion: Float[Array, "n_agents"]
    discount_factor: Float[Array, "n_agents"]
    skill_level: Float[Array, "n_agents"]
    education_years: Float[Array, "n_agents"]
    age: Int[Array, "n_agents"]
    expected_lifetime_utility: Float[Array, "n_agents"]
    savings_target: Float[Array, "n_agents"]
    planning_horizon: Int[Array, "n_agents"]
    expected_income_growth: Float[Array, "n_agents"]
    n_connections: Int[Array, "n_agents"]

    @property
    def size(self) -> int:
        return int(self.wealth.shape[0])


@chex.dataclass(frozen=True)
class PolicyState:
    """Global policy parameters shared by all agents."""

    tax_rate: Float[Array, ""]
    transfer_rate: Float[Array, ""]
    interest_rate: Float[Array, ""]
    expected_interest_rate: Float[Array, ""]


@chex.dataclass(frozen=True)
class AggregateState:
    """Aggregate metrics computed from the agent population."""

    total_wealth: Float[Array, ""]
    mean_consumption: Float[Array, ""]
    gini_coefficient: Float[Array, ""]


@chex.dataclass(frozen=True)
class GlobalState:
    """Complete simulation state for multi-agent execution."""

    agents: AgentState
    policy: PolicyState
    aggregates: AggregateState
    distributions: "DistributionState"
    graph: "GraphState"
    population_manager: "PopulationManager"
    next_agent_id: Int[Array, ""]
    time_step: Int[Array, ""]
    simulation_horizon: Int[Array, ""]
    phase_id: Int[Array, ""]
    rng_key: chex.PRNGKey

    @classmethod
    def empty(
        cls,
        n_agents: int,
        *,
        rng_key: chex.PRNGKey | None = None,
        seed: int = 0,
        simulation_horizon: int = 256,
        n_quantiles: int = 10,
        max_agents: int | None = None,
    ) -> "GlobalState":
        from polisyos.foundry.agent_sim.distributions import DistributionState
        from polisyos.foundry.agent_sim.graphs import GraphState
        from polisyos.foundry.agent_sim.population import PopulationManager

        key = rng_key if rng_key is not None else jax.random.PRNGKey(int(seed))
        max_agents = int(max_agents) if max_agents is not None else int(n_agents)
        initial_agents = int(n_agents)
        agents = AgentState(
            active=jnp.zeros(max_agents, dtype=jnp.bool_).at[:initial_agents].set(True),
            agent_id=jnp.where(
                jnp.arange(max_agents) < initial_agents,
                jnp.arange(max_agents, dtype=jnp.int32),
                -jnp.ones(max_agents, dtype=jnp.int32),
            ),
            birth_step=jnp.zeros(max_agents, dtype=jnp.int32),
            parent_id=jnp.full(max_agents, -1, dtype=jnp.int32),
            parent_slot=jnp.full(max_agents, -1, dtype=jnp.int32),
            parent_wealth_at_birth=jnp.zeros(max_agents, dtype=jnp.float32),
            life_expectancy=jnp.full(max_agents, simulation_horizon, dtype=jnp.int32),
            fertility_rate=jnp.zeros(max_agents, dtype=jnp.float32),
            wealth=jnp.zeros(max_agents, dtype=jnp.float32),
            income=jnp.zeros(max_agents, dtype=jnp.float32),
            consumption=jnp.zeros(max_agents, dtype=jnp.float32),
            savings=jnp.zeros(max_agents, dtype=jnp.float32),
            consumption_target=jnp.zeros(max_agents, dtype=jnp.float32),
            information_level=jnp.zeros(max_agents, dtype=jnp.float32),
            debt=jnp.zeros(max_agents, dtype=jnp.float32),
            employed=jnp.zeros(max_agents, dtype=jnp.bool_),
            retired=jnp.zeros(max_agents, dtype=jnp.bool_),
            utility_adjustment=jnp.zeros(max_agents, dtype=jnp.float32),
            risk_aversion=jnp.ones(max_agents, dtype=jnp.float32) * 0.5,
            discount_factor=jnp.ones(max_agents, dtype=jnp.float32) * 0.95,
            skill_level=jnp.ones(max_agents, dtype=jnp.float32),
            education_years=jnp.zeros(max_agents, dtype=jnp.float32),
            age=jnp.zeros(max_agents, dtype=jnp.int32),
            expected_lifetime_utility=jnp.zeros(max_agents, dtype=jnp.float32),
            savings_target=jnp.zeros(max_agents, dtype=jnp.float32),
            planning_horizon=jnp.full(max_agents, simulation_horizon, dtype=jnp.int32),
            expected_income_growth=jnp.zeros(max_agents, dtype=jnp.float32),
            n_connections=jnp.zeros(max_agents, dtype=jnp.int32),
        )
        policy = PolicyState(
            tax_rate=jnp.array(0.0, dtype=jnp.float32),
            transfer_rate=jnp.array(0.0, dtype=jnp.float32),
            interest_rate=jnp.array(0.01, dtype=jnp.float32),
            expected_interest_rate=jnp.array(0.01, dtype=jnp.float32),
        )
        aggregates = AggregateState(
            total_wealth=jnp.array(0.0, dtype=jnp.float32),
            mean_consumption=jnp.array(0.0, dtype=jnp.float32),
            gini_coefficient=jnp.array(0.0, dtype=jnp.float32),
        )
        distributions = DistributionState.empty(max_agents, n_quantiles=n_quantiles)
        graph = GraphState.empty(max_agents)
        population_manager = PopulationManager(
            free_stack=jnp.arange(max_agents, dtype=jnp.int32),
            free_top=jnp.array(initial_agents, dtype=jnp.int32),
            max_agents=int(max_agents),
            n_active=jnp.array(initial_agents, dtype=jnp.int32),
            total_births=jnp.array(0, dtype=jnp.int32),
            total_deaths=jnp.array(0, dtype=jnp.int32),
        )
        return cls(
            agents=agents,
            policy=policy,
            aggregates=aggregates,
            distributions=distributions,
            graph=graph,
            population_manager=population_manager,
            next_agent_id=jnp.array(initial_agents, dtype=jnp.int32),
            time_step=jnp.array(0, dtype=jnp.int32),
            simulation_horizon=jnp.array(simulation_horizon, dtype=jnp.int32),
            phase_id=jnp.array(0, dtype=jnp.int32),
            rng_key=key,
        )


if TYPE_CHECKING:
    from polisyos.foundry.agent_sim.distributions import DistributionState
    from polisyos.foundry.agent_sim.graphs import GraphState
    from polisyos.foundry.agent_sim.population import PopulationManager


def compute_aggregates(
    agents: AgentState,
    *,
    compute_gini: bool = False,
) -> AggregateState:
    active = agents.active.astype(jnp.float32)
    active_count = jnp.sum(active)
    safe_count = jnp.maximum(active_count, 1.0)
    total_wealth = jnp.sum(agents.wealth * active)
    mean_consumption = jnp.sum(agents.consumption * active) / safe_count

    if compute_gini:
        gini = _gini_from_values(agents.wealth, active)
    else:
        gini = jnp.array(0.0, dtype=jnp.float32)

    return AggregateState(
        total_wealth=total_wealth,
        mean_consumption=mean_consumption,
        gini_coefficient=gini,
    )


def _gini_from_values(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
    active_values = jnp.where(active > 0.0, values, 0.0)
    sorted_vals = jnp.sort(active_values)
    n = sorted_vals.shape[0]
    cum = jnp.cumsum(sorted_vals)
    total = cum[-1]
    total = jnp.maximum(total, 1e-6)
    gini = (n + 1 - 2.0 * jnp.sum(cum) / total) / n
    return jnp.clip(gini, 0.0, 1.0)
