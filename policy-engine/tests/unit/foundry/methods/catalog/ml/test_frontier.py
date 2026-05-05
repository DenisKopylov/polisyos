from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.ml import TabularData, ensure_ml_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_tabular(seed: int = 101) -> TabularData:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(120, 6))
    y = (
        1.1
        + 1.4 * x[:, 0]
        - 0.8 * x[:, 1]
        + 0.6 * x[:, 0] * x[:, 2]
        + rng.normal(scale=0.25, size=120)
    )
    return TabularData(features=x, target=y, feature_names=[f"x{i}" for i in range(x.shape[1])])


def test_ft_transformer_and_tabnet_run() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    tabular = _make_tabular()

    for fqn in ("ml.deep.ft_transformer@1.0.0", "ml.deep.tabnet@1.0.0"):
        method_cls = registry.get(fqn)
        result = dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=tabular,
            params={},
            seed=31,
        )
        assert result.output["result"].metrics["r_squared"] > 0.25
        assert result.output["uncertainty_envelope"] is not None


def test_graph_conv_runs_on_node_regression() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    rng = np.random.default_rng(131)
    n_nodes = 48
    node_features = rng.normal(size=(n_nodes, 3))
    adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
    for idx in range(n_nodes):
        adjacency[idx, (idx - 1) % n_nodes] = 1.0
        adjacency[idx, (idx + 1) % n_nodes] = 1.0
    neighbor_signal = (adjacency @ node_features[:, 0]) / 2.0
    target = (
        0.8 * node_features[:, 0] + 0.6 * neighbor_signal + rng.normal(scale=0.15, size=n_nodes)
    )

    method_cls = registry.get("ml.graph.graph_conv@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"node_features": node_features, "adjacency_matrix": adjacency, "target": target},
        params={},
        seed=37,
    )

    assert result.output["result"].metrics["r_squared"] > 0.2
    assert "x0" in result.output["result"].feature_importances
    assert result.output["result"].embedding_fidelity_certificate is not None
    assert result.output["result"].embedding_fidelity_certificate.family == "gcn"
    assert result.output["result"].metadata["embedding_fidelity_certificate"]["status"] == "yellow"


def test_masked_autoencoder_returns_embedding() -> None:
    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("ml.self_supervised.masked_autoencoder@1.0.0")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={"latent_dim": 4, "mask_fraction": 0.2},
        seed=43,
    )

    embedding = result.output["result"]
    assert np.asarray(embedding.transformed).shape[1] == 4
    assert embedding.metadata["reconstruction_rmse"] >= 0.0
    assert embedding.embedding_fidelity_certificate is not None
    assert embedding.embedding_fidelity_certificate.family == "masked_autoencoder"
    assert embedding.metadata["embedding_fidelity_certificate"]["status"] == "yellow"
