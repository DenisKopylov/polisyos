import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import apply_patch_map
from polisyos.foundry.fiscal import IncomeTax, TaxSubsidy
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _tree_shapes(tree):
    def shape_or_none(x):
        return getattr(x, "shape", None)

    return jax.tree_util.tree_map(shape_or_none, tree)


def _assert_stable_tree(a, b):
    assert jax.tree_util.tree_structure(a) == jax.tree_util.tree_structure(b)
    assert _tree_shapes(a) == _tree_shapes(b)


def test_tax_subsidy_jit_step_stable():
    n_agents = 5
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))

    mech = TaxSubsidy(rate=0.1, n_agents=n_agents)

    @eqx.filter_jit
    def step(mech, state, key):
        patches, next_key = mech.emit_patches(state, key)
        next_state = apply_patch_map(
            state,
            patches,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="subsidy",
        )
        return next_state, next_key

    s1, k1 = step(mech, state, jax.random.PRNGKey(0))
    s2, k2 = step(mech, s1, jax.random.PRNGKey(1))

    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)
    assert k1.shape == k2.shape


def test_income_tax_jit_step_stable():
    n_agents = 5
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.ones(n_agents) * 1000.0,
            reported_income=jnp.ones(n_agents) * 1000.0,
        )
    )

    mech = IncomeTax(rate=0.2, n_agents=n_agents)

    @eqx.filter_jit
    def step(mech, state, key):
        patches, next_key = mech.emit_patches(state, key)
        next_state = apply_patch_map(
            state,
            patches,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="tax",
        )
        return next_state, next_key

    s1, k1 = step(mech, state, jax.random.PRNGKey(0))
    s2, k2 = step(mech, s1, jax.random.PRNGKey(1))

    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)
    assert k1.shape == k2.shape
