import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.graph_mechanisms import (
    InformationDiffusionMechanism,
    LaborNetworkMechanism,
    NetworkLendingMechanism,
    SocialInfluenceMechanism,
)
from polisyos.foundry.agent_sim.graphs import EdgeList, GraphState, compute_degrees
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


def _make_state() -> GlobalState:
    edges = EdgeList(
        senders=jnp.array([0, 1], dtype=jnp.int32),
        receivers=jnp.array([2, 2], dtype=jnp.int32),
        weights=jnp.array([1.0, 1.0], dtype=jnp.float32),
        edge_types=jnp.array([0, 0], dtype=jnp.int32),
        n_nodes=4,
        n_edges=2,
        is_directed=True,
    )
    in_degrees, out_degrees = compute_degrees(edges)
    graph = GraphState.empty(4).replace(
        edges=edges,
        in_degrees=in_degrees,
        out_degrees=out_degrees,
    )

    state = GlobalState.empty(n_agents=4, seed=0, max_agents=4)
    agents = state.agents.replace(
        active=jnp.array([True, True, True, False], dtype=jnp.bool_),
        consumption=jnp.array([1.0, 3.0, 9.0, 7.0], dtype=jnp.float32),
        consumption_target=jnp.array([0.0, 0.0, 4.0, 11.0], dtype=jnp.float32),
        information_level=jnp.array([0.2, 0.9, 0.1, 0.7], dtype=jnp.float32),
        wealth=jnp.array([20.0, 70.0, 1.0, 100.0], dtype=jnp.float32),
        income=jnp.array([4.0, 6.0, 2.0, 8.0], dtype=jnp.float32),
        debt=jnp.array([0.0, 1.0, 0.0, 5.0], dtype=jnp.float32),
        employed=jnp.array([True, True, False, False], dtype=jnp.bool_),
    )
    return state.replace(agents=agents, graph=graph)


def test_social_influence_updates_only_active_targets() -> None:
    state = _make_state()
    mechanism = SocialInfluenceMechanism(influence_strength=1.0, aggregation="mean")

    next_state, metrics = mechanism.apply(state, None, FidelityLevel.SURROGATE_FLUID)

    assert bool(jnp.isclose(next_state.agents.consumption_target[2], 2.0))
    assert bool(jnp.isclose(next_state.agents.consumption_target[3], 11.0))
    assert set(metrics) == {"mean_neighbor_consumption", "consumption_correlation"}


def test_information_diffusion_is_bounded_and_preserves_inactive_agents() -> None:
    state = _make_state()
    mechanism = InformationDiffusionMechanism(diffusion_rate=1.0, decay_rate=0.0)

    next_state, metrics = mechanism.apply(
        state,
        jax.random.PRNGKey(0),
        FidelityLevel.SURROGATE_FLUID,
    )

    assert bool(jnp.all((next_state.agents.information_level >= 0.0) & (next_state.agents.information_level <= 1.0)))
    assert bool(jnp.isclose(next_state.agents.information_level[3], state.agents.information_level[3]))
    assert all(bool(jnp.isfinite(value)) for value in metrics.values())


def test_network_lending_conserves_active_wealth_and_records_borrower_debt() -> None:
    state = _make_state()
    mechanism = NetworkLendingMechanism(max_loan_fraction=0.2, interest_rate=0.1)

    next_state, metrics = mechanism.apply(
        state,
        jax.random.PRNGKey(0),
        FidelityLevel.SURROGATE_FLUID,
    )

    assert bool(jnp.isclose(next_state.agents.wealth[2], 15.0))
    assert bool(jnp.isclose(next_state.agents.debt[2], 15.4))
    assert bool(jnp.isclose(next_state.agents.wealth[1], 56.0))
    assert bool(jnp.isclose(next_state.agents.wealth[0], state.agents.wealth[0]))
    assert bool(jnp.isclose(next_state.agents.wealth[3], state.agents.wealth[3]))
    assert bool(
        jnp.isclose(
            jnp.sum(next_state.agents.wealth[:3]),
            jnp.sum(state.agents.wealth[:3]),
        )
    )
    assert bool(jnp.isclose(metrics["total_loans"], 14.0))
    assert bool(jnp.isclose(metrics["n_borrowers"], 1.0))


def test_labor_network_uses_neighbor_referrals() -> None:
    state = _make_state()
    mechanism = LaborNetworkMechanism(referral_probability=1.0)

    next_state, metrics = mechanism.apply(
        state,
        jax.random.PRNGKey(0),
        FidelityLevel.SURROGATE_FLUID,
    )

    assert bool(next_state.agents.employed[2])
    assert bool(jnp.isclose(next_state.agents.income[2], 5.0))
    assert bool(jnp.isclose(next_state.agents.income[3], state.agents.income[3]))
    assert bool(jnp.isclose(metrics["new_jobs"], 1.0))
    assert bool(jnp.isclose(metrics["unemployment_rate"], 0.0))
