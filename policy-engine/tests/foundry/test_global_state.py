import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState


def test_global_state_shapes_and_employment_counts() -> None:
    n_agents = 100
    n_firms = 10

    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)

    assert state.agents.size == n_agents
    assert state.firms.size == n_firms

    new_employer_ids = state.agents.employer_id.at[:10].set(0)
    new_agents = state.agents.replace(employer_id=new_employer_ids)
    state = state.replace(agents=new_agents)

    mask_employed = new_employer_ids >= 0
    safe_ids = jnp.where(mask_employed, new_employer_ids, 0)
    counts = jax.ops.segment_sum(jnp.where(mask_employed, 1.0, 0.0), safe_ids, n_firms)

    assert float(counts[0]) == 10.0
