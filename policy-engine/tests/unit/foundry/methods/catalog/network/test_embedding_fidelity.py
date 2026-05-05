from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.network import (
    NetworkResult,
    compute_embedding_fidelity_certificate,
)
from polisyos.ir.analytics.network_embedding import EmbeddingFidelityStatus


def _ring_adjacency(n_nodes: int) -> np.ndarray:
    adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
    for idx in range(n_nodes):
        adjacency[idx, (idx - 1) % n_nodes] = 1.0
        adjacency[idx, (idx + 1) % n_nodes] = 1.0
    return adjacency


def test_embedding_fidelity_certificate_green_when_separator_is_recoverable() -> None:
    rng = np.random.default_rng(17)
    n_obs = 400
    separator = rng.normal(size=n_obs)
    treatment = 0.8 * separator + rng.normal(scale=0.25, size=n_obs)
    outcome = 1.4 * treatment + 0.9 * separator + rng.normal(scale=0.25, size=n_obs)
    left = 0.7 * separator + rng.normal(scale=0.3, size=n_obs)
    right = -0.5 * separator + rng.normal(scale=0.3, size=n_obs)
    embedding = np.column_stack([separator, separator + rng.normal(scale=0.05, size=n_obs)])

    certificate = compute_embedding_fidelity_certificate(
        {
            "adjacency_matrix": _ring_adjacency(n_obs),
            "embedding_matrix": embedding,
            "embedding_family": "node2vec",
            "separator_matrix": {"community_score": separator},
            "treatment": treatment,
            "outcome": outcome,
            "columns": {"left_aux": left, "right_aux": right},
            "ci_specs": [
                {
                    "name": "aux_independence",
                    "left": "left_aux",
                    "right": "right_aux",
                    "separator_names": ["community_score"],
                }
            ],
        }
    )

    assert certificate["status"] == "green"
    assert certificate["recommended_action"] == "allow_as_adjustment"
    assert certificate["recoverability_scores"]["community_score"] >= 0.9
    assert certificate["collision_rate"] <= 0.05

    result = NetworkResult.model_validate(
        {
            "method_name": "community_detection",
            "embedding_fidelity_certificate": certificate,
        }
    )
    assert result.embedding_fidelity_certificate is not None
    assert result.embedding_fidelity_certificate.status is EmbeddingFidelityStatus.GREEN


def test_embedding_fidelity_certificate_red_when_embedding_collapses_separator() -> None:
    rng = np.random.default_rng(19)
    n_obs = 320
    separator = rng.normal(size=n_obs)
    treatment = separator + rng.normal(scale=0.2, size=n_obs)
    outcome = 1.2 * treatment + 1.1 * separator + rng.normal(scale=0.2, size=n_obs)
    left = separator + rng.normal(scale=0.2, size=n_obs)
    right = -separator + rng.normal(scale=0.2, size=n_obs)
    embedding = np.ones((n_obs, 2), dtype=float)

    certificate = compute_embedding_fidelity_certificate(
        {
            "adjacency_matrix": _ring_adjacency(n_obs),
            "embedding_matrix": embedding,
            "embedding_family": "gcn",
            "separator_matrix": {"latent_proxy": separator},
            "treatment": treatment,
            "outcome": outcome,
            "columns": {"left_aux": left, "right_aux": right},
            "ci_specs": [
                {
                    "name": "aux_independence",
                    "left": "left_aux",
                    "right": "right_aux",
                    "separator_names": ["latent_proxy"],
                }
            ],
        }
    )

    assert certificate["status"] == "red"
    assert certificate["recommended_action"] in {"require_raw_graph_summaries", "require_bounds"}
    assert "separator_recoverability_below_red_threshold" in certificate["failure_modes"]
