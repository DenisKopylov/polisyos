"""Public agent sim graph observations module API."""

from __future__ import annotations

import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import soft_rank
from polisyos.foundry.agent_sim.graphs import aggregate_messages, compute_pagerank
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations


def build_graph_enhanced_observations(
    state: GlobalState,
    *,
    horizon: int | None = None,
    include_expectations: bool = True,
) -> jnp.ndarray:
    """Build graph enhanced observations."""
    agents = state.agents
    edges = state.graph.edges
    n_agents = agents.wealth.shape[0]
    active = agents.active

    base_obs = build_temporal_observations(
        state,
        horizon=horizon,
        include_expectations=include_expectations,
    )

    neighbor_wealth = aggregate_messages(
        agents.wealth[:, None],
        edges,
        aggregation="mean",
        active=active,
    ).squeeze(-1)
    neighbor_consumption = aggregate_messages(
        agents.consumption[:, None],
        edges,
        aggregation="mean",
        active=active,
    ).squeeze(-1)

    edge_mask = active[edges.senders] & active[edges.receivers]
    if hasattr(edges, "active"):
        edge_mask = edge_mask & edges.active

    degrees = jnp.bincount(
        edges.senders,
        weights=edge_mask.astype(jnp.float32),
        length=n_agents,
    )
    max_degree = jnp.maximum(jnp.max(degrees), 1.0)
    normalized_degree = degrees / max_degree

    pagerank = compute_pagerank(edges, n_iterations=20)
    wealth_rank = soft_rank(jnp.where(active, agents.wealth, -1e6), temperature=1.0)

    network_features = jnp.stack(
        [
            neighbor_wealth,
            neighbor_consumption,
            normalized_degree,
            pagerank,
            wealth_rank,
        ],
        axis=-1,
    )
    return jnp.concatenate([base_obs, network_features], axis=-1)
