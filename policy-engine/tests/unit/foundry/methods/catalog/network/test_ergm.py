from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.network import NetworkData, fit_ergm_null_model


def _clustered_graph(seed: int = 11) -> NetworkData:
    rng = np.random.default_rng(seed)
    labels = np.array([0] * 8 + [1] * 8, dtype=int)
    n = labels.shape[0]
    adjacency = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            prob = 0.65 if labels[i] == labels[j] else 0.08
            edge = float(rng.uniform() < prob)
            adjacency[i, j] = edge
            adjacency[j, i] = edge
    node_features = np.column_stack(
        [
            labels.astype(float),
            rng.normal(scale=0.2, size=n),
        ]
    )
    return NetworkData(
        adjacency=adjacency,
        node_features=node_features,
        metadata={"ergm_group_labels": labels.tolist()},
    )


def test_ergm_null_model_returns_diagnostics() -> None:
    state = _clustered_graph()
    fit = fit_ergm_null_model(
        state,
        {
            "degree_decay": 0.3,
            "triangle_decay": 0.5,
            "ridge_penalty": 0.8,
            "n_simulations": 12,
            "save_graphs": 3,
            "__seed__": 5,
        },
    ).result

    assert fit.fit_status == "null_lite"
    assert "intercept" in fit.coefficients
    assert "gwdegree" in fit.coefficients
    assert "gwesp" in fit.coefficients
    assert "nodemix" in fit.coefficients
    assert fit.simulated_graphs.shape == (3, 16, 16)
    assert "edge_density" in fit.gof_checks
    assert isinstance(fit.degeneracy_alarm, bool)
    assert 0.0 <= fit.diagnostics["simulated_edge_density_mean"] <= 1.0


def test_ergm_estimator_registered_and_runs(isolated_registry) -> None:
    method = isolated_registry.get("network.generative.ergm_null@0.1.0")
    state = _clustered_graph(seed=19)
    result = method.pure_step(state, {"n_simulations": 10, "__seed__": 9})["result"]
    assert result.method_name == "ergm_null"
    assert result.metadata["n_simulations"] == 10
