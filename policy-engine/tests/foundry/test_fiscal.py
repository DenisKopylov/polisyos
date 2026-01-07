import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.fiscal import IncomeTax, TaxSubsidy


def test_budget_accounting() -> None:
    n_agents = 10
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(
        agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0),
        government_balance=jnp.array(0.0),
    )

    tax_mech = IncomeTax(n_agents=n_agents, rate=0.10)
    state, _ = tax_mech(state, jax.random.PRNGKey(0))

    assert float(state.government_balance) == 1000.0

    subsidy_mech = TaxSubsidy(n_agents=n_agents, rate=0.50)
    state, _ = subsidy_mech(state, jax.random.PRNGKey(1))

    assert float(state.government_balance) == -3500.0
