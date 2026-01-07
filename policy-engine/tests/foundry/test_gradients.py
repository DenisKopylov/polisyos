import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.fiscal import TaxSubsidy


def test_tax_subsidy_gradient_value() -> None:
    n_agents = 10
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 100.0))

    policy = TaxSubsidy(rate=0.10, n_agents=n_agents)

    def loss_fn(policy_model, current_state):
        next_state, _ = policy_model(current_state, jax.random.PRNGKey(0))
        total_gdp = jnp.sum(next_state.agents.income)
        return -total_gdp

    grad_fn = eqx.filter_grad(loss_fn)
    grads = grad_fn(policy, state)

    assert bool(jnp.isclose(grads.rate, -1000.0))


def test_tax_subsidy_gradient_sign_and_invariants() -> None:
    n_agents = 5
    state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))
    key = jax.random.PRNGKey(0)

    mech = TaxSubsidy(rate=0.1, n_agents=n_agents)

    def loss_fn(mechanism):
        next_state, _ = mechanism(state, key)
        return -jnp.mean(next_state.agents.income)

    grad_fn = eqx.filter_grad(loss_fn)
    grads = grad_fn(mech)

    assert grads.rate is not None
    assert float(grads.rate) < 0.0

    next_state, _ = mech(state, key)
    assert mech.invariants(next_state)
