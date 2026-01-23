from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int

from polisyos.foundry.agent_sim.state import AgentState

if TYPE_CHECKING:
    from polisyos.foundry.agent_sim.graphs import GraphState
    from polisyos.foundry.agent_sim.state import GlobalState


@chex.dataclass(frozen=True)
class PopulationManager:
    free_stack: Int[Array, "max_agents"]
    free_top: Int[Array, ""]
    max_agents: int
    n_active: Int[Array, ""]
    total_births: Int[Array, ""]
    total_deaths: Int[Array, ""]


@chex.dataclass(frozen=True)
class PopulationState:
    agents: AgentState
    manager: PopulationManager
    next_agent_id: Int[Array, ""]


@dataclass(frozen=True)
class PopulationConfig:
    max_initial_age: int = 80
    mean_life_expectancy: int = 75
    std_life_expectancy: int = 10
    retirement_age: int = 65
    base_fertility_rate: float = 0.02
    fertility_start_age: int = 20
    fertility_end_age: int = 45
    base_income: float = 50.0
    mean_log_wealth: float = 3.0
    std_log_wealth: float = 1.5
    initial_employment_rate: float = 0.7
    inheritance_fraction: float = 0.3


@dataclass(frozen=True)
class LifecycleConfig:
    population_config: PopulationConfig = PopulationConfig()
    steps_per_year: int = 12
    enable_gift_transfers: bool = False
    max_births_per_step: int = 100
    max_immigrants_per_step: int = 100
    base_mortality_rate: float = 0.001
    age_mortality_factor: float = 0.0001
    wealth_mortality_factor: float = -0.0001


@dataclass(frozen=True)
class InheritanceConfig:
    inheritance_to_children: float = 0.7
    inheritance_to_spouse: float = 0.2
    inheritance_tax_rate: float = 0.1
    min_inheritance: float = 0.0
    max_inheritance_per_heir: float = 1e6


@dataclass(frozen=True)
class GraphSyncConfig:
    connect_newborns_to_parents: bool = True
    connect_newborns_to_random: bool = True
    initial_connections: int = 5
    max_new_edges: int = 512


def create_population_manager(max_agents: int, initial_active: int) -> PopulationManager:
    return PopulationManager(
        free_stack=jnp.arange(max_agents, dtype=jnp.int32),
        free_top=jnp.array(initial_active, dtype=jnp.int32),
        max_agents=int(max_agents),
        n_active=jnp.array(initial_active, dtype=jnp.int32),
        total_births=jnp.array(0, dtype=jnp.int32),
        total_deaths=jnp.array(0, dtype=jnp.int32),
    )


def initialize_population(
    initial_n_agents: int,
    max_agents: int,
    rng_key: chex.PRNGKey,
    config: PopulationConfig,
    steps_per_year: int = 12,
) -> tuple[AgentState, PopulationManager, jnp.ndarray]:
    if initial_n_agents > max_agents:
        raise ValueError("initial_n_agents must be <= max_agents")

    key1, key2, key3, key4, key5 = jax.random.split(rng_key, 5)
    active = jnp.zeros(max_agents, dtype=jnp.bool_).at[:initial_n_agents].set(True)

    agent_id = jnp.where(
        jnp.arange(max_agents) < initial_n_agents,
        jnp.arange(max_agents, dtype=jnp.int32),
        -jnp.ones(max_agents, dtype=jnp.int32),
    )
    birth_step = jnp.zeros(max_agents, dtype=jnp.int32)
    parent_id = jnp.full(max_agents, -1, dtype=jnp.int32)
    parent_slot = jnp.full(max_agents, -1, dtype=jnp.int32)
    parent_wealth_at_birth = jnp.zeros(max_agents, dtype=jnp.float32)

    age_years = jax.random.randint(
        key1,
        (max_agents,),
        0,
        int(config.max_initial_age),
    )
    age = age_years * jnp.array(steps_per_year, dtype=jnp.int32)
    age = jnp.where(active, age, 0)

    life_expectancy_years = (
        config.mean_life_expectancy
        + config.std_life_expectancy * jax.random.normal(key2, (max_agents,))
    ).astype(jnp.int32)
    life_expectancy_years = jnp.maximum(life_expectancy_years, age_years + 1)
    life_expectancy = life_expectancy_years * jnp.array(steps_per_year, dtype=jnp.int32)

    fertility_rate = jnp.where(
        (age_years >= config.fertility_start_age)
        & (age_years <= config.fertility_end_age),
        config.base_fertility_rate,
        0.0,
    )
    fertility_rate = jnp.where(active, fertility_rate, 0.0)

    log_wealth = config.mean_log_wealth + config.std_log_wealth * jax.random.normal(
        key3, (max_agents,)
    )
    wealth = jnp.exp(log_wealth)
    wealth = jnp.where(active, wealth, 0.0)

    skill_level = jax.random.uniform(key4, (max_agents,), minval=0.5, maxval=2.0)
    age_factor = jnp.minimum(age_years / 40.0, 1.0)
    income = config.base_income * skill_level * (0.5 + age_factor)
    income = jnp.where(active, income, 0.0)

    risk_aversion = 1.0 + jax.random.gamma(key5, 2.0, (max_agents,))
    discount_factor = 0.9 + 0.09 * jax.random.beta(
        jax.random.fold_in(key5, 1), 5.0, 2.0, (max_agents,)
    )

    employed = jax.random.bernoulli(
        jax.random.fold_in(key5, 2),
        config.initial_employment_rate,
        (max_agents,),
    )
    retired = age_years >= config.retirement_age
    employed = employed & ~retired
    employed = employed & active
    retired = retired & active

    agents = AgentState(
        active=active,
        agent_id=agent_id,
        birth_step=birth_step,
        parent_id=parent_id,
        parent_slot=parent_slot,
        parent_wealth_at_birth=parent_wealth_at_birth,
        life_expectancy=life_expectancy,
        fertility_rate=fertility_rate,
        wealth=wealth,
        income=income,
        consumption=jnp.zeros(max_agents, dtype=jnp.float32),
        savings=jnp.zeros(max_agents, dtype=jnp.float32),
        consumption_target=jnp.zeros(max_agents, dtype=jnp.float32),
        information_level=jnp.zeros(max_agents, dtype=jnp.float32),
        debt=jnp.zeros(max_agents, dtype=jnp.float32),
        employed=employed,
        retired=retired,
        utility_adjustment=jnp.zeros(max_agents, dtype=jnp.float32),
        risk_aversion=risk_aversion,
        discount_factor=discount_factor,
        skill_level=skill_level,
        education_years=jnp.zeros(max_agents, dtype=jnp.float32),
        age=age,
        expected_lifetime_utility=jnp.zeros(max_agents, dtype=jnp.float32),
        savings_target=jnp.zeros(max_agents, dtype=jnp.float32),
        planning_horizon=jnp.full(max_agents, 256, dtype=jnp.int32),
        expected_income_growth=jnp.zeros(max_agents, dtype=jnp.float32),
        n_connections=jnp.zeros(max_agents, dtype=jnp.int32),
    )

    manager = create_population_manager(max_agents, initial_n_agents)
    next_agent_id = jnp.array(initial_n_agents, dtype=jnp.int32)
    return agents, manager, next_agent_id


def allocate_slot(
    manager: PopulationManager,
) -> tuple[PopulationManager, jnp.ndarray, jnp.ndarray]:
    has_free = manager.free_top < manager.max_agents
    slot_index = jnp.where(
        has_free,
        manager.free_stack[manager.free_top],
        -jnp.ones((), dtype=jnp.int32),
    )
    new_free_top = jnp.where(
        has_free,
        manager.free_top + 1,
        manager.free_top,
    )
    new_n_active = jnp.where(
        has_free,
        manager.n_active + 1,
        manager.n_active,
    )
    new_manager = manager.replace(
        free_top=new_free_top,
        n_active=new_n_active,
        total_births=manager.total_births + has_free.astype(jnp.int32),
    )
    return new_manager, slot_index, has_free


def allocate_multiple_slots(
    manager: PopulationManager,
    n_slots: int,
    *,
    n_requested: jnp.ndarray | None = None,
) -> tuple[PopulationManager, jnp.ndarray, jnp.ndarray]:
    if n_requested is None:
        n_requested = jnp.array(n_slots, dtype=jnp.int32)
    available = jnp.array(manager.max_agents, dtype=jnp.int32) - manager.free_top
    n_slots_val = jnp.array(n_slots, dtype=jnp.int32)
    n_to_allocate = jnp.minimum(jnp.minimum(n_slots_val, available), n_requested)

    slot_range = manager.free_top + jnp.arange(n_slots, dtype=jnp.int32)
    slot_range = jnp.clip(slot_range, 0, manager.max_agents - 1)
    slot_indices = jnp.where(
        jnp.arange(n_slots, dtype=jnp.int32) < n_to_allocate,
        manager.free_stack[slot_range],
        -jnp.ones((n_slots,), dtype=jnp.int32),
    )

    new_free_top = manager.free_top + n_to_allocate
    new_manager = manager.replace(
        free_top=new_free_top,
        n_active=manager.n_active + n_to_allocate,
        total_births=manager.total_births + n_to_allocate,
    )
    return new_manager, slot_indices, n_to_allocate


def free_slot(manager: PopulationManager, slot_index: jnp.ndarray) -> PopulationManager:
    is_valid = (slot_index >= 0) & (slot_index < manager.max_agents)
    can_free = is_valid & (manager.free_top > 0)
    new_free_top = jnp.where(can_free, manager.free_top - 1, manager.free_top)

    def _update_stack(stack):
        return stack.at[new_free_top].set(slot_index)

    new_free_stack = jax.lax.cond(can_free, _update_stack, lambda s: s, manager.free_stack)
    new_n_active = jnp.where(can_free, manager.n_active - 1, manager.n_active)
    return manager.replace(
        free_stack=new_free_stack,
        free_top=new_free_top,
        n_active=new_n_active,
        total_deaths=manager.total_deaths + can_free.astype(jnp.int32),
    )


def free_multiple_slots(
    manager: PopulationManager,
    slot_indices: jnp.ndarray,
    valid_mask: jnp.ndarray,
) -> PopulationManager:
    def free_one(carry, inp):
        mgr = carry
        idx, valid = inp
        return jax.lax.cond(valid, lambda m: free_slot(m, idx), lambda m: m, mgr), None

    new_manager, _ = jax.lax.scan(
        free_one,
        manager,
        (slot_indices, valid_mask),
    )
    return new_manager


def batch_create_agents(
    state: "GlobalState",
    n_new: int,
    parent_indices: jnp.ndarray,
    rng_key: chex.PRNGKey,
    config: PopulationConfig,
    *,
    n_requested: jnp.ndarray | None = None,
    birth_step: jnp.ndarray | None = None,
    age_override: jnp.ndarray | None = None,
    steps_per_year: int = 12,
) -> "GlobalState":
    manager, slot_indices, n_allocated = allocate_multiple_slots(
        state.population_manager,
        n_new,
        n_requested=n_requested,
    )
    allocated_mask = jnp.arange(n_new, dtype=jnp.int32) < n_allocated
    keys = jax.random.split(rng_key, 5)

    has_parent = parent_indices >= 0
    parent_idx_safe = jnp.clip(parent_indices, 0, state.agents.wealth.shape[0] - 1)
    has_parent = has_parent & state.agents.active[parent_idx_safe]
    parent_wealth = jnp.where(has_parent, state.agents.wealth[parent_idx_safe], 0.0)
    parent_agent_id = jnp.where(
        has_parent,
        state.agents.agent_id[parent_idx_safe],
        -jnp.ones_like(parent_indices, dtype=jnp.int32),
    )
    parent_slot = jnp.where(
        has_parent,
        parent_indices,
        -jnp.ones_like(parent_indices, dtype=jnp.int32),
    )
    inherited = config.inheritance_fraction * parent_wealth

    own_wealth = jnp.exp(
        config.mean_log_wealth + config.std_log_wealth * jax.random.normal(keys[0], (n_new,))
    ) * 0.1
    new_wealth = inherited + own_wealth

    parent_risk = jnp.where(
        has_parent,
        state.agents.risk_aversion[parent_idx_safe],
        1.5,
    )
    mutation = 0.2 * jax.random.normal(keys[1], (n_new,))
    new_risk = jnp.maximum(0.5, parent_risk + mutation)

    parent_skill = jnp.where(
        has_parent,
        state.agents.skill_level[parent_idx_safe],
        1.0,
    )
    skill_noise = 0.3 * jax.random.normal(keys[2], (n_new,))
    new_skill = jnp.clip(parent_skill * 0.7 + 0.3 + skill_noise, 0.5, 2.5)

    new_discount = 0.9 + 0.09 * jax.random.beta(keys[3], 5.0, 2.0, (n_new,))

    new_life_years = (
        config.mean_life_expectancy
        + config.std_life_expectancy * jax.random.normal(keys[4], (n_new,))
    ).astype(jnp.int32)
    new_life_years = jnp.maximum(new_life_years, 20)
    new_life = new_life_years * jnp.array(steps_per_year, dtype=jnp.int32)

    new_age = jnp.zeros((n_new,), dtype=jnp.int32)
    if age_override is not None:
        new_age = age_override

    step_val = state.time_step if birth_step is None else birth_step

    def update_agent(i, agents):
        def apply(agents):
            idx = slot_indices[i]
            next_id = state.next_agent_id + i
            return agents.replace(
                active=agents.active.at[idx].set(True),
                agent_id=agents.agent_id.at[idx].set(next_id),
                birth_step=agents.birth_step.at[idx].set(step_val),
                parent_id=agents.parent_id.at[idx].set(parent_agent_id[i]),
                parent_slot=agents.parent_slot.at[idx].set(parent_slot[i]),
                parent_wealth_at_birth=agents.parent_wealth_at_birth.at[idx].set(
                    parent_wealth[i]
                ),
                age=agents.age.at[idx].set(new_age[i]),
                life_expectancy=agents.life_expectancy.at[idx].set(new_life[i]),
                fertility_rate=agents.fertility_rate.at[idx].set(0.0),
                wealth=agents.wealth.at[idx].set(new_wealth[i]),
                income=agents.income.at[idx].set(0.0),
                consumption=agents.consumption.at[idx].set(0.0),
                savings=agents.savings.at[idx].set(0.0),
                debt=agents.debt.at[idx].set(0.0),
                risk_aversion=agents.risk_aversion.at[idx].set(new_risk[i]),
                discount_factor=agents.discount_factor.at[idx].set(new_discount[i]),
                skill_level=agents.skill_level.at[idx].set(new_skill[i]),
                education_years=agents.education_years.at[idx].set(0.0),
                employed=agents.employed.at[idx].set(False),
                retired=agents.retired.at[idx].set(False),
                consumption_target=agents.consumption_target.at[idx].set(0.0),
                information_level=agents.information_level.at[idx].set(0.0),
                utility_adjustment=agents.utility_adjustment.at[idx].set(0.0),
                expected_lifetime_utility=agents.expected_lifetime_utility.at[idx].set(0.0),
                savings_target=agents.savings_target.at[idx].set(0.0),
                planning_horizon=agents.planning_horizon.at[idx].set(
                    state.simulation_horizon.astype(jnp.int32)
                ),
                expected_income_growth=agents.expected_income_growth.at[idx].set(0.0),
                n_connections=agents.n_connections.at[idx].set(0),
            )

        valid = allocated_mask[i] & (slot_indices[i] >= 0)
        return jax.lax.cond(valid, apply, lambda a: a, agents)

    new_agents = jax.lax.fori_loop(0, int(n_new), update_agent, state.agents)
    return state.replace(
        agents=new_agents,
        population_manager=manager,
        next_agent_id=state.next_agent_id + n_allocated,
    )


def batch_remove_agents(state: "GlobalState", removal_mask: jnp.ndarray) -> "GlobalState":
    removal_mask = removal_mask & state.agents.active
    slot_indices = jnp.arange(state.population_manager.max_agents, dtype=jnp.int32)
    manager = free_multiple_slots(state.population_manager, slot_indices, removal_mask)

    active = state.agents.active & ~removal_mask

    def reset(field, value):
        return jnp.where(removal_mask, value, field)

    agents = state.agents.replace(
        active=active,
        agent_id=reset(state.agents.agent_id, -1),
        birth_step=reset(state.agents.birth_step, 0),
        parent_id=reset(state.agents.parent_id, -1),
        parent_slot=reset(state.agents.parent_slot, -1),
        parent_wealth_at_birth=reset(state.agents.parent_wealth_at_birth, 0.0),
        wealth=reset(state.agents.wealth, 0.0),
        income=reset(state.agents.income, 0.0),
        consumption=reset(state.agents.consumption, 0.0),
        savings=reset(state.agents.savings, 0.0),
        debt=reset(state.agents.debt, 0.0),
        consumption_target=reset(state.agents.consumption_target, 0.0),
        information_level=reset(state.agents.information_level, 0.0),
        fertility_rate=reset(state.agents.fertility_rate, 0.0),
        employed=reset(state.agents.employed, False),
        retired=reset(state.agents.retired, False),
    )

    return state.replace(agents=agents, population_manager=manager)


def compute_death_mask(
    state: "GlobalState",
    rng_key: chex.PRNGKey,
    *,
    base_mortality_rate: float = 0.001,
    age_mortality_factor: float = 0.0001,
    wealth_mortality_factor: float = -0.0001,
    steps_per_year: int = 12,
) -> jnp.ndarray:
    agents = state.agents
    age_years = agents.age // steps_per_year
    base_hazard = base_mortality_rate
    age_hazard = age_mortality_factor * jnp.exp(0.1 * age_years)
    wealth_mean = jnp.sum(agents.wealth * agents.active) / (
        jnp.sum(agents.active) + 1e-8
    )
    wealth_normalized = agents.wealth / (wealth_mean + 1e-8)
    wealth_hazard = wealth_mortality_factor * jnp.log(wealth_normalized + 1.0)
    over_life_exp = jnp.maximum(agents.age - agents.life_expectancy, 0)
    life_exp_hazard = 0.1 * over_life_exp / steps_per_year

    death_prob = jnp.clip(
        base_hazard + age_hazard + wealth_hazard + life_exp_hazard,
        0.0,
        1.0,
    )
    death_prob = jnp.where(agents.active, death_prob, 0.0)
    random_vals = jax.random.uniform(rng_key, shape=death_prob.shape)
    return random_vals < death_prob


def sync_graph_with_population(
    graph: "GraphState",
    old_active: jnp.ndarray,
    new_active: jnp.ndarray,
    births: jnp.ndarray,
    rng_key: chex.PRNGKey,
    config: GraphSyncConfig,
    parent_slots: jnp.ndarray | None = None,
) -> "GraphState":
    edges = graph.edges
    if not hasattr(edges, "active"):
        return graph

    edge_alive = new_active[edges.senders] & new_active[edges.receivers] & edges.active
    edges = edges.replace(active=edge_alive)

    if not config.connect_newborns_to_random:
        active_weights = edges.active.astype(jnp.int32)
        in_degrees = jnp.bincount(
            edges.receivers,
            weights=active_weights,
            length=edges.n_nodes,
        )
        out_degrees = jnp.bincount(
            edges.senders,
            weights=active_weights,
            length=edges.n_nodes,
        )
        return graph.replace(
            edges=edges,
            in_degrees=in_degrees.astype(jnp.int32),
            out_degrees=out_degrees.astype(jnp.int32),
            last_structure_update=graph.last_structure_update + 1,
        )

    n_births = jnp.sum(births.astype(jnp.int32))
    has_births = n_births > 0

    def _add_edges(g: "GraphState") -> "GraphState":
        edges_local = g.edges
        free_mask = ~edges_local.active
        max_edges = edges_local.max_edges
        max_new_edges = jnp.minimum(
            jnp.array(config.max_new_edges, dtype=jnp.int32),
            jnp.sum(free_mask.astype(jnp.int32)),
        )
        key_slots, key_births, key_senders, key_receivers = jax.random.split(rng_key, 4)
        slot_candidates = jax.random.randint(
            key_slots, shape=(max_edges,), minval=0, maxval=max_edges
        )

        birth_weights = births.astype(jnp.float32)
        birth_weights = birth_weights / jnp.maximum(jnp.sum(birth_weights), 1.0)
        sender_random = jax.random.choice(
            key_senders,
            edges_local.n_nodes,
            shape=(max_edges,),
            replace=True,
            p=birth_weights,
        )

        active_weights = new_active.astype(jnp.float32)
        active_weights = active_weights / jnp.maximum(jnp.sum(active_weights), 1.0)
        receiver_random = jax.random.choice(
            key_receivers,
            edges_local.n_nodes,
            shape=(max_edges,),
            replace=True,
            p=active_weights,
        )
        use_parent_edges = config.connect_newborns_to_parents and parent_slots is not None
        n_parent_edges = jnp.where(
            use_parent_edges,
            jnp.minimum(n_births.astype(jnp.int32), max_new_edges),
            jnp.array(0, dtype=jnp.int32),
        )
        parent_candidates = receiver_random
        sender_candidates = sender_random

        if use_parent_edges:
            parent_slots_safe = jnp.clip(parent_slots, 0, edges_local.n_nodes - 1)
            birth_samples = jax.random.choice(
                key_births,
                edges_local.n_nodes,
                shape=(max_edges,),
                replace=True,
                p=birth_weights,
            )
            parent_valid = parent_slots[birth_samples] >= 0
            parent_candidates = jnp.where(
                parent_valid,
                parent_slots_safe[birth_samples],
                receiver_random,
            )
            sender_candidates = birth_samples

        edge_idx = jnp.arange(max_edges, dtype=jnp.int32)
        use_parent_mask = edge_idx < n_parent_edges
        sender_candidates = jnp.where(use_parent_mask, sender_candidates, sender_random)
        receiver_candidates = jnp.where(use_parent_mask, parent_candidates, receiver_random)
        receiver_candidates = jnp.where(
            receiver_candidates == sender_candidates,
            (receiver_candidates + 1) % edges_local.n_nodes,
            receiver_candidates,
        )

        def add_one(i, edges_inner):
            idx = slot_candidates[i]
            can_add = free_mask[idx] & (i < max_new_edges)

            def _update(edges_inner):
                return edges_inner.replace(
                    senders=edges_inner.senders.at[idx].set(sender_candidates[i]),
                    receivers=edges_inner.receivers.at[idx].set(receiver_candidates[i]),
                    weights=edges_inner.weights.at[idx].set(1.0),
                    edge_types=edges_inner.edge_types.at[idx].set(0),
                    active=edges_inner.active.at[idx].set(True),
                )

            return jax.lax.cond(can_add, _update, lambda e: e, edges_inner)

        edges_updated = jax.lax.fori_loop(0, int(edges_local.max_edges), add_one, edges_local)
        n_active_edges = jnp.sum(edges_updated.active.astype(jnp.int32))
        edges_updated = edges_updated.replace(n_active_edges=n_active_edges)
        active_weights = edges_updated.active.astype(jnp.int32)
        in_degrees = jnp.bincount(
            edges_updated.receivers,
            weights=active_weights,
            length=edges_updated.n_nodes,
        )
        out_degrees = jnp.bincount(
            edges_updated.senders,
            weights=active_weights,
            length=edges_updated.n_nodes,
        )
        return g.replace(
            edges=edges_updated,
            in_degrees=in_degrees.astype(jnp.int32),
            out_degrees=out_degrees.astype(jnp.int32),
            last_structure_update=g.last_structure_update + 1,
        )

    return jax.lax.cond(has_births, _add_edges, lambda g: g.replace(edges=edges), graph)
