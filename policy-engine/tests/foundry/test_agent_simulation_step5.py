import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim import (
    InheritanceConfig,
    InheritanceMechanism,
    PopulationConfig,
    allocate_multiple_slots,
    batch_create_agents,
    batch_remove_agents,
    create_population_manager,
    free_multiple_slots,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.types import FidelityLevel


def _tree_shapes(tree):
    def shape_or_none(x):
        if hasattr(x, "shape"):
            return x.shape
        if isinstance(x, (int, float, bool)):
            return ()
        return None

    return jax.tree_util.tree_map(shape_or_none, tree)


def _assert_stable_tree(a, b):
    assert jax.tree_util.tree_structure(a) == jax.tree_util.tree_structure(b)
    assert _tree_shapes(a) == _tree_shapes(b)


def test_free_list_allocate_free() -> None:
    manager = create_population_manager(max_agents=10, initial_active=5)
    manager, slots, n_allocated = allocate_multiple_slots(manager, 3)
    assert int(n_allocated) == 3
    assert int(manager.n_active) == 8

    valid_mask = jnp.arange(3, dtype=jnp.int32) < n_allocated
    manager = free_multiple_slots(manager, slots, valid_mask)
    assert int(manager.n_active) == 5


def test_active_mask_consistency() -> None:
    state = GlobalState.empty(n_agents=4, max_agents=8, seed=0)
    parent_indices = jnp.full((3,), -1, dtype=jnp.int32)
    state = batch_create_agents(
        state,
        n_new=3,
        parent_indices=parent_indices,
        rng_key=jax.random.PRNGKey(1),
        config=PopulationConfig(),
        n_requested=jnp.array(3, dtype=jnp.int32),
    )
    removal_mask = state.agents.active & (jnp.arange(8, dtype=jnp.int32) % 2 == 0)
    state = batch_remove_agents(state, removal_mask)
    assert int(jnp.sum(state.agents.active)) == int(state.population_manager.n_active)


def test_inheritance_conserves_wealth() -> None:
    state = GlobalState.empty(n_agents=3, seed=0)
    agents = state.agents.replace(
        wealth=jnp.array([100.0, 0.0, 50.0], dtype=jnp.float32),
        parent_id=jnp.array([-1, 0, -1], dtype=jnp.int32),
        parent_slot=jnp.array([-1, 0, -1], dtype=jnp.int32),
        active=jnp.array([True, True, True]),
    )
    state = state.replace(agents=agents)
    death_mask = jnp.array([True, False, False])
    mech = InheritanceMechanism(
        config=InheritanceConfig(inheritance_to_children=1.0, inheritance_tax_rate=0.1)
    )
    new_state, metrics = mech.apply(state, death_mask, None, FidelityLevel.SURROGATE_FLUID)
    final_state = batch_remove_agents(new_state, death_mask)
    initial_total = jnp.sum(agents.wealth)
    final_total = jnp.sum(final_state.agents.wealth)
    tax = metrics["inheritance_tax_collected"]
    assert bool(jnp.isclose(final_total + tax, initial_total, rtol=0.01))


def test_population_jit_shapes_stable() -> None:
    state = GlobalState.empty(n_agents=4, max_agents=8, seed=0)
    config = PopulationConfig()
    parent_indices = jnp.full((2,), -1, dtype=jnp.int32)

    @jax.jit
    def step(state, key):
        key1, key2 = jax.random.split(key)
        state = batch_create_agents(
            state,
            n_new=2,
            parent_indices=parent_indices,
            rng_key=key1,
            config=config,
            n_requested=jnp.array(2, dtype=jnp.int32),
        )
        death_mask = jax.random.bernoulli(key2, 0.25, shape=state.agents.active.shape)
        state = batch_remove_agents(state, death_mask)
        return state

    s1 = step(state, jax.random.PRNGKey(0))
    s2 = step(s1, jax.random.PRNGKey(1))
    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)
