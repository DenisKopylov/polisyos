from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal import dagma_discovery as dagma_module
from polisyos.foundry.methods.catalog.causal.dagma_discovery import DAGMADiscovery
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_graph import GraphType


def _state(n_variables: int = 3, n_samples: int = 16) -> TabularCausalDiscoveryData:
    rng = np.random.default_rng(19)
    data = rng.normal(0.0, 1.0, size=(n_samples, n_variables))
    names = [f"V{i}" for i in range(n_variables)]
    return TabularCausalDiscoveryData(data=data, variable_names=names)


def test_dagma_discovery_success_path(monkeypatch) -> None:
    weights = np.array(
        [
            [0.0, 0.8, 0.0],
            [0.0, 0.0, 0.6],
            [0.0, 0.0, 0.0],
        ],
        dtype=float,
    )

    def _fake_runner(**kwargs):
        del kwargs
        return dagma_module._DAGMAExecutionResult(
            weights=weights,
            metadata={"optimizer": "fake.optimizer", "converged": True, "num_steps": 12},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(dagma_module, "_run_dagma_with_timeout", _fake_runner)

    output = DAGMADiscovery.pure_step(_state(), params={"weight_threshold": 0.1, "n_bootstrap": 0})
    report = output["report"]

    assert report.method == "dagma"
    assert report.graph.graph_type is GraphType.DAG
    edge_pairs = {(edge.src, edge.dst) for edge in report.graph.edges}
    assert ("V0", "V1") in edge_pairs
    assert ("V1", "V2") in edge_pairs
    assert report.metadata["optimizer"] == "fake.optimizer"
    assert report.metadata["algebraic_constraint_severity"] in {"info", "warning", "blocker"}


def test_dagma_discovery_missing_dependency_graceful_fallback(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return dagma_module._DAGMAExecutionResult(
            weights=None,
            metadata={},
            error="ModuleNotFoundError: No module named 'dagma'",
            timed_out=False,
        )

    monkeypatch.setattr(dagma_module, "_run_dagma_with_timeout", _fake_runner)

    output = DAGMADiscovery.pure_step(_state(), params={})
    report = output["report"]

    assert report.method == "dagma"
    assert report.graph.edges == []
    assert report.metadata.get("fallback") is True
    assert any("modulenotfounderror" in warning.lower() for warning in report.warnings)
    assert report.metadata["algebraic_constraint_severity"] in {"warning", "blocker"}


def test_dagma_discovery_forwards_explicit_algebraic_blocks(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        del kwargs
        return dagma_module._DAGMAExecutionResult(
            weights=np.zeros((4, 4), dtype=float),
            metadata={"optimizer": "fake.optimizer", "converged": True},
            error=None,
            timed_out=False,
        )

    def _fake_stamp(
        report,
        *,
        data,
        variable_names,
        significance_level,
        seed,
        algebraic_blocks,
    ):
        del data, variable_names, significance_level, seed
        captured["algebraic_blocks"] = algebraic_blocks
        return report.model_copy(
            update={
                "metadata": {
                    **dict(report.metadata),
                    "algebraic_constraint_severity": "info",
                }
            }
        )

    monkeypatch.setattr(dagma_module, "_run_dagma_with_timeout", _fake_runner)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.constraint_discovery._stamp_algebraic_constraint_audit",
        _fake_stamp,
    )

    output = DAGMADiscovery.pure_step(
        _state(n_variables=4),
        params={
            "weight_threshold": 0.1,
            "algebraic_blocks": [
                {
                    "block_id": "factor_1",
                    "family": "tetrad",
                    "variables": ["V0", "V1", "V2", "V3"],
                }
            ],
        },
    )
    report = output["report"]

    assert captured["algebraic_blocks"] is not None
    assert report.metadata["algebraic_constraint_severity"] == "info"


def test_dagma_discovery_large_variable_smoke(monkeypatch) -> None:
    state = _state(n_variables=52, n_samples=40)

    def _fake_runner(**kwargs):
        del kwargs
        return dagma_module._DAGMAExecutionResult(
            weights=np.zeros((52, 52), dtype=float),
            metadata={"optimizer": "fake.optimizer", "converged": True},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(dagma_module, "_run_dagma_with_timeout", _fake_runner)

    output = DAGMADiscovery.pure_step(state, params={"weight_threshold": 0.2})
    report = output["report"]

    assert report.method == "dagma"
    assert len(report.graph.nodes) == 52
    assert report.graph.edges == []
