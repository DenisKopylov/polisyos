"""Create, mutate, and aggregate graph structures used by agent-simulation mechanisms."""

from __future__ import annotations

import chex
import jax
import jax.numpy as jnp
import numpy as np
from jaxtyping import Array, Bool, Float, Int


class EdgeType:
    """Enumerate the social, economic, and informational edge labels used in runtime graphs."""

    SOCIAL_FRIEND = 0
    SOCIAL_FAMILY = 1
    ECONOMIC_EMPLOYER = 2
    ECONOMIC_LENDER = 3
    SPATIAL_NEIGHBOR = 4
    INFO_INFLUENCE = 5


@chex.dataclass(frozen=True)
class EdgeList:
    """Store a sparse graph as parallel sender and receiver arrays for JAX execution."""

    senders: Int[Array, n_edges]
    receivers: Int[Array, n_edges]
    weights: Float[Array, n_edges]
    edge_types: Int[Array, n_edges]
    n_nodes: int
    n_edges: int
    is_directed: bool = True


@chex.dataclass(frozen=True)
class FixedSizeEdgeList:
    """Store a capacity-bounded graph that can be mutated in-place during simulation."""

    senders: Int[Array, max_edges]
    receivers: Int[Array, max_edges]
    weights: Float[Array, max_edges]
    edge_types: Int[Array, max_edges]
    active: Bool[Array, max_edges]
    n_nodes: int
    max_edges: int
    n_active_edges: Int[Array, ""]


@chex.dataclass(frozen=True)
class GraphState:
    """Track graph structure plus degree caches used by runtime executors."""

    edges: EdgeList | FixedSizeEdgeList
    node_to_edges_start: Int[Array, n_nodes_plus_one]
    sorted_by_receiver: Bool[Array, ""]
    in_degrees: Int[Array, n_nodes]
    out_degrees: Int[Array, n_nodes]
    last_structure_update: Int[Array, ""]

    @classmethod
    def empty(cls, n_nodes: int) -> GraphState:
        empty_edges = EdgeList(
            senders=jnp.zeros((0,), dtype=jnp.int32),
            receivers=jnp.zeros((0,), dtype=jnp.int32),
            weights=jnp.zeros((0,), dtype=jnp.float32),
            edge_types=jnp.zeros((0,), dtype=jnp.int32),
            n_nodes=int(n_nodes),
            n_edges=0,
            is_directed=True,
        )
        return cls(
            edges=empty_edges,
            node_to_edges_start=jnp.zeros((n_nodes + 1,), dtype=jnp.int32),
            sorted_by_receiver=jnp.array(False),
            in_degrees=jnp.zeros((n_nodes,), dtype=jnp.int32),
            out_degrees=jnp.zeros((n_nodes,), dtype=jnp.int32),
            last_structure_update=jnp.array(-1, dtype=jnp.int32),
        )


@chex.dataclass(frozen=True)
class MultiEdgeList:
    """Provide per-edge-type views over a shared runtime edge list."""

    all_edges: EdgeList

    def get_edges_by_type(self, edge_type: int) -> EdgeList:
        mask = self.all_edges.edge_types == edge_type
        senders = self.all_edges.senders[mask]
        receivers = self.all_edges.receivers[mask]
        weights = self.all_edges.weights[mask]
        edge_types = self.all_edges.edge_types[mask]
        n_edges = int(senders.shape[0])
        return EdgeList(
            senders=senders,
            receivers=receivers,
            weights=weights,
            edge_types=edge_types,
            n_nodes=self.all_edges.n_nodes,
            n_edges=n_edges,
            is_directed=self.all_edges.is_directed,
        )


def create_random_graph(
    n_nodes: int,
    avg_degree: float,
    rng_key: chex.PRNGKey,
    *,
    graph_type: str = "erdos_renyi",
) -> EdgeList:
    """Create random graph."""
    if graph_type == "erdos_renyi":
        return _create_erdos_renyi(n_nodes, avg_degree, rng_key)
    if graph_type == "barabasi_albert":
        return create_scale_free_graph(n_nodes, max(1, int(avg_degree / 2)), rng_key)
    if graph_type == "watts_strogatz":
        return create_watts_strogatz_graph(n_nodes, max(2, int(avg_degree)), 0.1, rng_key)
    raise ValueError(f"Unknown graph type: {graph_type}")


def _create_erdos_renyi(
    n_nodes: int,
    avg_degree: float,
    rng_key: chex.PRNGKey,
) -> EdgeList:
    p = avg_degree / max(n_nodes - 1, 1)
    if n_nodes <= 1000:
        key1, _ = jax.random.split(rng_key)
        i_idx, j_idx = jnp.meshgrid(
            jnp.arange(n_nodes),
            jnp.arange(n_nodes),
            indexing="ij",
        )
        i_flat = i_idx.reshape(-1)
        j_flat = j_idx.reshape(-1)
        mask = i_flat != j_flat
        i_flat = i_flat[mask]
        j_flat = j_flat[mask]
        random_vals = jax.random.uniform(key1, shape=i_flat.shape)
        edge_mask = random_vals < p
        senders = i_flat[edge_mask]
        receivers = j_flat[edge_mask]
    else:
        expected_edges = max(1, int(n_nodes * avg_degree))
        senders, receivers = _sample_edges(n_nodes, expected_edges, rng_key)

    n_edges = int(senders.shape[0])
    return EdgeList(
        senders=senders,
        receivers=receivers,
        weights=jnp.ones((n_edges,), dtype=jnp.float32),
        edge_types=jnp.zeros((n_edges,), dtype=jnp.int32),
        n_nodes=int(n_nodes),
        n_edges=n_edges,
        is_directed=True,
    )


def _sample_edges(
    n_nodes: int,
    n_edges: int,
    rng_key: chex.PRNGKey,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    key1, key2 = jax.random.split(rng_key)
    senders = jax.random.randint(key1, shape=(n_edges,), minval=0, maxval=n_nodes)
    receivers = jax.random.randint(key2, shape=(n_edges,), minval=0, maxval=n_nodes)
    self_loops = senders == receivers
    receivers = jnp.where(self_loops, (receivers + 1) % n_nodes, receivers)
    return senders, receivers


def create_watts_strogatz_graph(
    n_nodes: int,
    degree: int,
    rewire_prob: float,
    rng_key: chex.PRNGKey,
) -> EdgeList:
    """Create watts strogatz graph."""
    if degree % 2 != 0:
        degree = degree + 1
    half = degree // 2

    base = jnp.arange(n_nodes)
    offsets = jnp.arange(1, half + 1)
    senders = jnp.repeat(base, half)
    receivers = (base[:, None] + offsets[None, :]).reshape(-1) % n_nodes

    n_edges = int(senders.shape[0])
    key1, key2 = jax.random.split(rng_key)
    rewire_mask = jax.random.uniform(key1, shape=(n_edges,)) < rewire_prob
    new_receivers = jax.random.randint(key2, shape=(n_edges,), minval=0, maxval=n_nodes)
    new_receivers = jnp.where(
        new_receivers == senders,
        (new_receivers + 1) % n_nodes,
        new_receivers,
    )
    receivers = jnp.where(rewire_mask, new_receivers, receivers)

    return EdgeList(
        senders=senders,
        receivers=receivers,
        weights=jnp.ones((n_edges,), dtype=jnp.float32),
        edge_types=jnp.zeros((n_edges,), dtype=jnp.int32),
        n_nodes=int(n_nodes),
        n_edges=n_edges,
        is_directed=True,
    )


def create_spatial_graph(
    positions: jnp.ndarray,
    radius: float,
    active: jnp.ndarray,
    rng_key: chex.PRNGKey | None = None,
) -> EdgeList:
    """Create spatial graph."""
    n_nodes = positions.shape[0]
    if n_nodes <= 2000:
        diff = positions[:, None, :] - positions[None, :, :]
        distances = jnp.sqrt(jnp.sum(diff**2, axis=-1))
        proximity = (distances < radius) & (distances > 0)
        proximity = proximity & active[:, None] & active[None, :]
        senders, receivers = jnp.where(proximity)
    else:
        expected_edges = max(1, int(n_nodes * 10))
        if rng_key is None:
            rng_key = jax.random.PRNGKey(0)
        senders, receivers = _sample_edges(n_nodes, expected_edges, rng_key)

    n_edges = int(senders.shape[0])
    if n_edges == 0:
        return EdgeList(
            senders=senders,
            receivers=receivers,
            weights=jnp.zeros((0,), dtype=jnp.float32),
            edge_types=jnp.zeros((0,), dtype=jnp.int32),
            n_nodes=int(n_nodes),
            n_edges=0,
            is_directed=False,
        )

    edge_distances = jnp.sqrt(jnp.sum((positions[senders] - positions[receivers]) ** 2, axis=-1))
    weights = 1.0 / (edge_distances + 0.1)
    return EdgeList(
        senders=senders,
        receivers=receivers,
        weights=weights.astype(jnp.float32),
        edge_types=jnp.full((n_edges,), EdgeType.SPATIAL_NEIGHBOR, dtype=jnp.int32),
        n_nodes=int(n_nodes),
        n_edges=n_edges,
        is_directed=False,
    )


def create_scale_free_graph(
    n_nodes: int,
    m: int,
    rng_key: chex.PRNGKey,
) -> EdgeList:
    """Create scale free graph."""
    if n_nodes <= 1:
        return EdgeList(
            senders=jnp.zeros((0,), dtype=jnp.int32),
            receivers=jnp.zeros((0,), dtype=jnp.int32),
            weights=jnp.zeros((0,), dtype=jnp.float32),
            edge_types=jnp.zeros((0,), dtype=jnp.int32),
            n_nodes=int(n_nodes),
            n_edges=0,
            is_directed=False,
        )

    initial = min(n_nodes, max(2, m + 1))
    seed = int(jax.random.randint(rng_key, shape=(), minval=0, maxval=2**31 - 1))
    rng = np.random.default_rng(seed)
    senders_list: list[int] = []
    receivers_list: list[int] = []
    degrees = np.zeros((n_nodes,), dtype=np.int64)

    for i in range(initial):
        for j in range(i + 1, initial):
            senders_list.extend([i, j])
            receivers_list.extend([j, i])
            degrees[i] += 1
            degrees[j] += 1

    for new_node in range(initial, n_nodes):
        n_targets = min(m, new_node)
        if n_targets <= 0:
            continue
        probs = degrees[:new_node].astype(np.float64)
        total = float(probs.sum())
        if total > 0.0:
            probs = probs / total
        else:
            probs = None
        targets = rng.choice(new_node, size=n_targets, replace=False, p=probs)
        for target in np.asarray(targets, dtype=np.int64):
            target_i = int(target)
            senders_list.extend([new_node, target_i])
            receivers_list.extend([target_i, new_node])
            degrees[new_node] += 1
            degrees[target_i] += 1

    senders = jnp.array(senders_list, dtype=jnp.int32)
    receivers = jnp.array(receivers_list, dtype=jnp.int32)
    n_edges = int(senders.shape[0])
    return EdgeList(
        senders=senders,
        receivers=receivers,
        weights=jnp.ones((n_edges,), dtype=jnp.float32),
        edge_types=jnp.zeros((n_edges,), dtype=jnp.int32),
        n_nodes=int(n_nodes),
        n_edges=n_edges,
        is_directed=False,
    )


def create_fixed_size_graph(edges: EdgeList, max_edges: int) -> FixedSizeEdgeList:
    """Create fixed size graph."""
    n_edges = edges.n_edges
    if n_edges > max_edges:
        raise ValueError(f"Too many edges: {n_edges} > {max_edges}")
    senders = jnp.zeros((max_edges,), dtype=jnp.int32)
    receivers = jnp.zeros((max_edges,), dtype=jnp.int32)
    weights = jnp.zeros((max_edges,), dtype=jnp.float32)
    edge_types = jnp.zeros((max_edges,), dtype=jnp.int32)
    active = jnp.zeros((max_edges,), dtype=jnp.bool_)
    senders = senders.at[:n_edges].set(edges.senders)
    receivers = receivers.at[:n_edges].set(edges.receivers)
    weights = weights.at[:n_edges].set(edges.weights)
    edge_types = edge_types.at[:n_edges].set(edges.edge_types)
    active = active.at[:n_edges].set(True)
    return FixedSizeEdgeList(
        senders=senders,
        receivers=receivers,
        weights=weights,
        edge_types=edge_types,
        active=active,
        n_nodes=edges.n_nodes,
        max_edges=max_edges,
        n_active_edges=jnp.array(n_edges, dtype=jnp.int32),
    )


def aggregate_messages(
    node_features: jnp.ndarray,
    edges: EdgeList | FixedSizeEdgeList,
    *,
    aggregation: str = "sum",
    active: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Aggregate sender features onto receivers for graph-based mechanism updates."""
    senders = edges.senders
    receivers = edges.receivers
    weights = edges.weights
    n_nodes = node_features.shape[0]

    edge_mask = jnp.ones(weights.shape[0], dtype=jnp.bool_)
    if hasattr(edges, "active"):
        edge_mask = edge_mask & edges.active
    if active is not None:
        edge_mask = edge_mask & active[senders] & active[receivers]

    sender_features = node_features[senders]
    weight_f = weights[:, None] * edge_mask.astype(node_features.dtype)[:, None]
    weighted = sender_features * weight_f

    if aggregation == "sum":
        return jax.ops.segment_sum(weighted, receivers, num_segments=n_nodes)

    if aggregation == "mean":
        summed = jax.ops.segment_sum(weighted, receivers, num_segments=n_nodes)
        weight_sums = jax.ops.segment_sum(
            weights * edge_mask.astype(weights.dtype),
            receivers,
            num_segments=n_nodes,
        )
        return summed / (weight_sums[:, None] + 1e-8)

    if aggregation == "max":
        masked = jnp.where(edge_mask[:, None], weighted, -jnp.inf)
        aggregated = jax.ops.segment_max(masked, receivers, num_segments=n_nodes)
        has_edges = jax.ops.segment_sum(
            edge_mask.astype(jnp.float32),
            receivers,
            num_segments=n_nodes,
        )
        return jnp.where(has_edges[:, None] > 0, aggregated, 0.0)

    raise ValueError(f"Unknown aggregation: {aggregation}")


def scatter_messages(
    source_features: jnp.ndarray,
    edges: EdgeList | FixedSizeEdgeList,
    *,
    operation: str = "add",
    active: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Scatter source features across edges before receiver-side accumulation."""
    senders = edges.senders
    receivers = edges.receivers
    weights = edges.weights
    n_nodes = source_features.shape[0]

    edge_mask = jnp.ones(weights.shape[0], dtype=jnp.bool_)
    if hasattr(edges, "active"):
        edge_mask = edge_mask & edges.active
    if active is not None:
        edge_mask = edge_mask & active[senders] & active[receivers]

    features = source_features[senders] * weights[:, None]
    features = features * edge_mask.astype(features.dtype)[:, None]
    result = jnp.zeros((n_nodes, source_features.shape[1]), dtype=source_features.dtype)

    if operation == "add":
        return result.at[receivers].add(features)
    if operation == "max":
        return result.at[receivers].max(features)
    if operation == "update":
        return result.at[receivers].set(features)
    raise ValueError(f"Unknown operation: {operation}")


def segment_softmax(scores: jnp.ndarray, segment_ids: jnp.ndarray, n_segments: int) -> jnp.ndarray:
    """Normalize edge scores within each receiver segment for attention layers."""
    max_scores = jax.ops.segment_max(scores, segment_ids, num_segments=n_segments)
    shifted = scores - max_scores[segment_ids]
    exp_scores = jnp.exp(shifted)
    sum_exp = jax.ops.segment_sum(exp_scores, segment_ids, num_segments=n_segments)
    return exp_scores / (sum_exp[segment_ids] + 1e-8)


def apply_edge_attention(
    messages: jnp.ndarray,
    edges: EdgeList | FixedSizeEdgeList,
    *,
    query_features: jnp.ndarray,
    key_features: jnp.ndarray,
    temperature: float = 1.0,
) -> jnp.ndarray:
    """Weight edge messages by receiver-local attention scores."""
    queries = query_features[edges.receivers]
    keys = key_features[edges.senders]
    scores = jnp.sum(queries * keys, axis=-1) / temperature
    attention = segment_softmax(scores, edges.receivers, query_features.shape[0])
    return messages * attention[:, None]


def multi_hop_aggregation(
    node_features: jnp.ndarray,
    edges: EdgeList | FixedSizeEdgeList,
    *,
    n_hops: int = 2,
    aggregation: str = "mean",
    decay: float = 0.5,
    active: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Propagate messages across repeated hops with exponential decay."""

    def body(hop, carry):
        current, aggregated = carry
        messages = aggregate_messages(
            current,
            edges,
            aggregation=aggregation,
            active=active,
        )
        weight = jnp.power(decay, hop)
        aggregated = aggregated + weight * messages
        return messages, aggregated

    init = (node_features, jnp.zeros_like(node_features))
    _, out = jax.lax.fori_loop(0, n_hops, body, init)
    return out


def compute_degree_centrality(edges: EdgeList | FixedSizeEdgeList) -> jnp.ndarray:
    """Compute normalized total-degree centrality for each node."""
    in_degrees, out_degrees = compute_degrees(edges)
    n_nodes = in_degrees.shape[0]
    total_degree = in_degrees + out_degrees
    denom = max(n_nodes - 1, 1)
    return total_degree.astype(jnp.float32) / float(denom)


def compute_pagerank(
    edges: EdgeList | FixedSizeEdgeList,
    *,
    damping: float = 0.85,
    n_iterations: int = 20,
) -> jnp.ndarray:
    """Estimate PageRank-style influence scores over the current graph."""
    n_nodes = edges.n_nodes
    weights = edges.weights
    edge_mask = jnp.ones(weights.shape[0], dtype=jnp.bool_)
    if hasattr(edges, "active"):
        edge_mask = edge_mask & edges.active
    weights = weights * edge_mask.astype(weights.dtype)

    out_deg = jax.ops.segment_sum(weights, edges.senders, num_segments=n_nodes)
    out_deg = jnp.maximum(out_deg, 1.0)
    pr0 = jnp.ones((n_nodes,), dtype=jnp.float32) / float(n_nodes)

    def body(_, pr):
        messages = pr[edges.senders] * weights / out_deg[edges.senders]
        incoming = jax.ops.segment_sum(messages, edges.receivers, num_segments=n_nodes)
        return (1.0 - damping) / float(n_nodes) + damping * incoming

    return jax.lax.fori_loop(0, n_iterations, body, pr0)


def compute_graph_metrics(
    edges: EdgeList | FixedSizeEdgeList,
    active: jnp.ndarray,
) -> dict[str, jnp.ndarray]:
    """Summarize density and degree dispersion for the active graph."""
    n_nodes = active.shape[0]
    edge_mask = active[edges.senders] & active[edges.receivers]
    if hasattr(edges, "active"):
        edge_mask = edge_mask & edges.active

    edge_weights = edge_mask.astype(jnp.float32)
    n_active = jnp.sum(active.astype(jnp.float32))
    n_edges = jnp.sum(edge_weights)
    max_edges = n_active * (n_active - 1.0)
    density = n_edges / (max_edges + 1e-8)

    degrees = jnp.bincount(edges.senders, weights=edge_weights, length=n_nodes)
    avg_degree = jnp.sum(degrees * active) / jnp.maximum(n_active, 1.0)
    degree_std = jnp.sqrt(
        jnp.sum((degrees - avg_degree) ** 2 * active) / jnp.maximum(n_active, 1.0)
    )
    max_degree = jnp.max(degrees * active.astype(jnp.float32))

    return {
        "graph_density": density,
        "avg_degree": avg_degree,
        "degree_std": degree_std,
        "max_degree": max_degree,
        "n_edges": n_edges,
    }


def compute_degrees(
    edges: EdgeList | FixedSizeEdgeList,
    *,
    n_nodes: int | None = None,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Compute in-degree and out-degree arrays for the current edge set."""
    n_nodes = edges.n_nodes if n_nodes is None else n_nodes
    edge_mask = jnp.ones(edges.senders.shape[0], dtype=jnp.float32)
    if hasattr(edges, "active"):
        edge_mask = edge_mask * edges.active.astype(jnp.float32)
    in_degrees = jnp.bincount(edges.receivers, weights=edge_mask, length=n_nodes)
    out_degrees = jnp.bincount(edges.senders, weights=edge_mask, length=n_nodes)
    return in_degrees.astype(jnp.int32), out_degrees.astype(jnp.int32)


class DynamicGraphUpdater:
    """Evolve graph structure by removing stale edges and sampling new ones."""

    def __init__(
        self,
        *,
        formation_rate: float = 0.01,
        removal_rate: float = 0.005,
        homophily_strength: float = 0.5,
    ):
        self.formation_rate = formation_rate
        self.removal_rate = removal_rate
        self.homophily_strength = homophily_strength

    def update_graph(self, graph: GraphState, agents, rng_key: chex.PRNGKey) -> GraphState:
        edges = graph.edges
        if hasattr(edges, "active"):
            edges = self._update_fixed_edges(edges, agents, rng_key)
        else:
            edges = self._update_edge_list(edges, agents, rng_key)
        in_degrees, out_degrees = compute_degrees(edges, n_nodes=agents.active.shape[0])
        return graph.replace(edges=edges, in_degrees=in_degrees, out_degrees=out_degrees)

    def _update_edge_list(self, edges: EdgeList, agents, rng_key: chex.PRNGKey) -> EdgeList:
        key_remove, key_add = jax.random.split(rng_key)
        keep_mask = jax.random.uniform(key_remove, shape=(edges.n_edges,)) >= self.removal_rate
        senders = edges.senders[keep_mask]
        receivers = edges.receivers[keep_mask]
        weights = edges.weights[keep_mask]
        edge_types = edges.edge_types[keep_mask]

        expected_new = max(1, int(edges.n_nodes * self.formation_rate))
        new_senders, new_receivers = _sample_edges(edges.n_nodes, expected_new, key_add)
        senders = jnp.concatenate([senders, new_senders])
        receivers = jnp.concatenate([receivers, new_receivers])
        weights = jnp.concatenate([weights, jnp.ones_like(new_senders, dtype=jnp.float32)])
        edge_types = jnp.concatenate([edge_types, jnp.zeros_like(new_senders, dtype=jnp.int32)])
        n_edges = int(senders.shape[0])
        return EdgeList(
            senders=senders,
            receivers=receivers,
            weights=weights,
            edge_types=edge_types,
            n_nodes=edges.n_nodes,
            n_edges=n_edges,
            is_directed=edges.is_directed,
        )

    def _update_fixed_edges(
        self,
        edges: FixedSizeEdgeList,
        agents,
        rng_key: chex.PRNGKey,
    ) -> FixedSizeEdgeList:
        key_remove, key_add, key_recv, key_accept = jax.random.split(rng_key, 4)
        remove_rand = jax.random.uniform(key_remove, shape=(edges.max_edges,))
        new_active = edges.active & (remove_rand >= self.removal_rate)

        available = edges.max_edges - jnp.sum(new_active.astype(jnp.int32))
        target_add = jnp.minimum(
            available,
            jnp.array(int(edges.n_nodes * self.formation_rate), dtype=jnp.int32),
        )

        order = jnp.argsort(new_active)
        update_mask = jnp.arange(edges.max_edges) < target_add
        update_slots = order

        candidate_senders = jax.random.randint(
            key_add, shape=(edges.max_edges,), minval=0, maxval=edges.n_nodes
        )
        candidate_receivers = jax.random.randint(
            key_recv, shape=(edges.max_edges,), minval=0, maxval=edges.n_nodes
        )
        candidate_receivers = jnp.where(
            candidate_receivers == candidate_senders,
            (candidate_receivers + 1) % edges.n_nodes,
            candidate_receivers,
        )

        if self.homophily_strength > 0.0:
            sender_wealth = agents.wealth[candidate_senders]
            receiver_wealth = agents.wealth[candidate_receivers]
            diff = jnp.abs(sender_wealth - receiver_wealth)
            accept_prob = jnp.exp(-self.homophily_strength * diff)
            accept_rand = jax.random.uniform(key_accept, shape=(edges.max_edges,))
            accept = accept_rand < accept_prob
            candidate_receivers = jnp.where(accept, candidate_receivers, edges.receivers)

        slot_active = (
            jnp.zeros((edges.max_edges,), dtype=jnp.bool_).at[update_slots].set(update_mask)
        )
        senders = jnp.where(slot_active, candidate_senders, edges.senders)
        receivers = jnp.where(slot_active, candidate_receivers, edges.receivers)
        weights = jnp.where(slot_active, jnp.ones_like(edges.weights), edges.weights)
        edge_types = jnp.where(slot_active, jnp.zeros_like(edges.edge_types), edges.edge_types)
        new_active = jnp.where(slot_active, True, new_active)

        n_active_edges = jnp.sum(new_active.astype(jnp.int32))
        return edges.replace(
            senders=senders,
            receivers=receivers,
            weights=weights,
            edge_types=edge_types,
            active=new_active,
            n_active_edges=n_active_edges,
        )
