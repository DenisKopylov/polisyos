from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.causal import build_block_stratified_network_causal_data
from polisyos.foundry.methods.network import EdgeListNetworkData, NetworkData
from sklearn.metrics import adjusted_rand_score


def _synthetic_sbm_graph(
    *,
    block_sizes: tuple[int, int] = (18, 18),
    p_in: float = 0.75,
    p_out: float = 0.10,
    seed: int = 7,
) -> tuple[NetworkData, np.ndarray]:
    rng = np.random.default_rng(seed)
    labels = np.concatenate(
        [np.full(size, block_id, dtype=int) for block_id, size in enumerate(block_sizes)]
    )
    n = int(labels.shape[0])
    adjacency = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            prob = p_in if labels[i] == labels[j] else p_out
            edge = float(rng.uniform() < prob)
            adjacency[i, j] = edge
            adjacency[j, i] = edge
    node_features = np.column_stack(
        [
            labels.astype(float) + rng.normal(scale=0.10, size=n),
            (labels == 0).astype(float) + rng.normal(scale=0.10, size=n),
        ]
    )
    node_ids = [f"n{i}" for i in range(n)]
    return NetworkData(
        adjacency=adjacency,
        node_features=node_features,
        node_ids=node_ids,
    ), labels


def test_edge_list_network_data_round_trips_to_dense() -> None:
    sparse = EdgeListNetworkData(
        edge_index=np.array([[0, 1], [1, 2], [2, 3]], dtype=int),
        n_nodes=4,
        node_states=np.array([0.0, 1.0, 0.0, 1.0]),
    )
    dense = sparse.to_network_data()
    assert dense.adjacency.shape == (4, 4)
    assert float(dense.adjacency[0, 1]) == 1.0
    assert float(dense.adjacency[1, 0]) == 1.0
    assert float(dense.adjacency[0, 3]) == 0.0


def test_sbm_stratification_recovers_block_structure(isolated_registry) -> None:
    method = isolated_registry.get("network.community.sbm_stratification@1.0.0")
    state, truth = _synthetic_sbm_graph()
    result = method.pure_step(
        state,
        {
            "n_blocks": 2,
            "covariate_scale": 0.6,
            "bootstrap_samples": 4,
            "min_block_size": 4,
            "__seed__": 13,
        },
    )["result"]

    ari = adjusted_rand_score(truth, np.asarray(result.labels, dtype=int))
    assert ari > 0.75
    assert result.co_clustering.shape == (truth.shape[0], truth.shape[0])
    assert result.responsibilities.shape == (truth.shape[0], 2)
    assert result.block_connectivity.shape == (2, 2)
    assert result.stability["overall_stability"] > 0.50
    assert result.metadata["fit_type"] == "covariate_assisted_dcsbm_approx"
    assert result.positivity_report["status"] == "not_evaluated"


def test_sbm_stratification_bridges_into_network_causal_data(isolated_registry) -> None:
    method = isolated_registry.get("network.community.sbm_stratification@1.0.0")
    state, _ = _synthetic_sbm_graph(seed=17)
    stratification = method.pure_step(
        state,
        {"n_blocks": 2, "bootstrap_samples": 3, "min_block_size": 4, "__seed__": 19},
    )["result"]

    n = state.adjacency.shape[0]
    treatment = np.zeros(n, dtype=float)
    treatment[::2] = 1.0
    outcome = 1.5 * treatment + np.random.default_rng(23).normal(scale=0.1, size=n)
    causal_data, bridge = build_block_stratified_network_causal_data(
        outcome=outcome,
        treatment=treatment,
        covariates=state.node_features,
        adjacency_matrix=state.adjacency,
        stratification=stratification,
    )

    assert np.array_equal(causal_data.cluster_id, np.asarray(stratification.labels, dtype=int))
    assert bridge.cluster_id.shape == (n,)
    assert len(bridge.block_support) == 2
    assert bridge.positivity_passed
    assert "block_connectivity" in bridge.aggregate_exposures
