import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim import (
    EdgeList,
    GraphState,
    SocialInfluenceMechanism,
    aggregate_messages,
    compute_degrees,
    compute_pagerank,
    create_random_graph,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


def test_message_passing_sum() -> None:
    edges = EdgeList(
        senders=jnp.array([0, 0, 1], dtype=jnp.int32),
        receivers=jnp.array([1, 2, 2], dtype=jnp.int32),
        weights=jnp.array([1.0, 1.0, 1.0], dtype=jnp.float32),
        edge_types=jnp.array([0, 0, 0], dtype=jnp.int32),
        n_nodes=3,
        n_edges=3,
        is_directed=True,
    )
    features = jnp.array([[1.0], [2.0], [3.0]], dtype=jnp.float32)
    result = aggregate_messages(features, edges, aggregation="sum")
    expected = jnp.array([[0.0], [1.0], [3.0]], dtype=jnp.float32)
    assert bool(jnp.allclose(result, expected))


def test_message_passing_mean() -> None:
    edges = EdgeList(
        senders=jnp.array([0, 1], dtype=jnp.int32),
        receivers=jnp.array([2, 2], dtype=jnp.int32),
        weights=jnp.array([1.0, 1.0], dtype=jnp.float32),
        edge_types=jnp.array([0, 0], dtype=jnp.int32),
        n_nodes=3,
        n_edges=2,
        is_directed=True,
    )
    features = jnp.array([[2.0], [4.0], [0.0]], dtype=jnp.float32)
    result = aggregate_messages(features, edges, aggregation="mean")
    assert bool(jnp.isclose(result[2, 0], 3.0))


def test_edge_list_memory() -> None:
    n_nodes = 1000
    avg_degree = 10
    edges = create_random_graph(n_nodes, avg_degree, jax.random.PRNGKey(0))

    memory = (
        edges.senders.nbytes
        + edges.receivers.nbytes
        + edges.weights.nbytes
        + edges.edge_types.nbytes
    )
    adjacency_memory = n_nodes * n_nodes * 4
    assert memory < adjacency_memory / 10


def test_pagerank_convergence() -> None:
    edges = create_random_graph(100, 6, jax.random.PRNGKey(0))
    pr = compute_pagerank(edges, n_iterations=50)
    assert bool(jnp.isclose(jnp.sum(pr), 1.0, atol=0.05))
    assert bool(jnp.all(pr >= 0))


def test_social_influence_target() -> None:
    edges = EdgeList(
        senders=jnp.array([0, 1], dtype=jnp.int32),
        receivers=jnp.array([2, 2], dtype=jnp.int32),
        weights=jnp.array([1.0, 1.0], dtype=jnp.float32),
        edge_types=jnp.array([0, 0], dtype=jnp.int32),
        n_nodes=3,
        n_edges=2,
        is_directed=True,
    )
    in_deg, out_deg = compute_degrees(edges)
    graph = GraphState.empty(3).replace(edges=edges, in_degrees=in_deg, out_degrees=out_deg)

    state = GlobalState.empty(n_agents=3, seed=0)
    agents = state.agents.replace(
        consumption=jnp.array([1.0, 2.0, 3.0], dtype=jnp.float32)
    )
    state = state.replace(agents=agents, graph=graph)

    mech = SocialInfluenceMechanism(influence_strength=1.0, aggregation="mean")
    new_state, _ = mech.apply(state, None, FidelityLevel.SURROGATE_FLUID)
    assert bool(jnp.isclose(new_state.agents.consumption_target[2], 1.5))
