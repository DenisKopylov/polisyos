from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.network import NetworkData


def _diffusion_state(seed: int = 29) -> NetworkData:
    rng = np.random.default_rng(seed)
    labels = np.array([0] * 6 + [1] * 6, dtype=int)
    n = labels.shape[0]
    adjacency = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            prob = 0.55 if labels[i] == labels[j] else 0.12
            edge = float(rng.uniform() < prob)
            adjacency[i, j] = edge
            adjacency[j, i] = edge
    node_states = np.zeros(n, dtype=float)
    node_states[:3] = 1.0
    return NetworkData(
        adjacency=adjacency,
        node_features=np.column_stack([labels.astype(float), rng.normal(size=n)]),
        node_states=node_states,
        metadata={"ergm_group_labels": labels.tolist()},
    )


def test_diffusion_null_test_returns_calibrated_summary(isolated_registry) -> None:
    method = isolated_registry.get("network.generative.diffusion_null_test@0.1.0")
    result = method.pure_step(
        _diffusion_state(),
        {
            "n_simulations": 10,
            "n_steps": 6,
            "diffusion_rate": 0.35,
            "decay": 0.04,
            "__seed__": 41,
        },
    )["result"]

    assert result.method_name == "diffusion_null_test"
    assert result.metric_name == "final_mean_state"
    assert 0.0 <= result.p_value <= 1.0
    assert result.simulated_metrics.shape == (10,)
    assert "q05" in result.envelope
    assert result.metadata["null_fit_status"] == "null_lite"
