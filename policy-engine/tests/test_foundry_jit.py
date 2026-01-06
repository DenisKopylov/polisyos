import jax
import jax.numpy as jnp

from src.domain.state import GlobalState
from src.foundry.fiscal import IncomeTax, TaxSubsidy


def _tree_shapes(tree):
    def shape_or_none(x):
        return getattr(x, "shape", None)

    return jax.tree_util.tree_map(shape_or_none, tree)


def _assert_stable_tree(a, b):
    assert jax.tree_util.tree_structure(a) == jax.tree_util.tree_structure(b)
    assert _tree_shapes(a) == _tree_shapes(b)


def test_tax_subsidy_jit_step_stable():
    n_agents = 5
    state = GlobalState.empty(n_agents, 0)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))

    mech = TaxSubsidy(rate=0.1, n_agents=n_agents)
    step = jax.jit(mech.step)

    s1 = step(state, jax.random.PRNGKey(0))
    s2 = step(s1, jax.random.PRNGKey(1))

    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)


def test_income_tax_jit_step_stable():
    n_agents = 5
    state = GlobalState.empty(n_agents, 0)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))

    mech = IncomeTax(rate=0.2, n_agents=n_agents)
    step = jax.jit(mech.step)

    s1 = step(state, jax.random.PRNGKey(0))
    s2 = step(s1, jax.random.PRNGKey(1))

    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)
