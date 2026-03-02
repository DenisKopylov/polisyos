from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.catalog.causal import constraint_discovery as constraint_module
from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
    FCIDiscovery,
    GESDiscovery,
    PCDiscovery,
)
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_graph import EdgeMark, GraphType, PAGIdentificationPolicy


def _state() -> TabularCausalDiscoveryData:
    data = np.array(
        [
            [0.2, 1.0, 0.4],
            [0.4, 1.3, 0.8],
            [0.7, 1.9, 1.1],
            [1.0, 2.2, 1.6],
            [1.3, 2.6, 1.9],
            [1.5, 2.9, 2.1],
        ],
        dtype=float,
    )
    return TabularCausalDiscoveryData(data=data, variable_names=["X", "Y", "Z"])


def _adj_with_xy_edge() -> np.ndarray:
    return np.array(
        [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 0],
        ],
        dtype=int,
    )


def _adj_without_edges() -> np.ndarray:
    return np.zeros((3, 3), dtype=int)


def test_pc_discovery_graceful_fallback_on_missing_backend(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error="ModuleNotFoundError: No module named 'causallearn'",
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = PCDiscovery.pure_step(_state(), params={})
    report = output["report"]

    assert output["__determinism_tier__"] is DeterminismTier.STATISTICAL
    assert report.graph.graph_type is GraphType.CPDAG
    assert report.graph.edges == []
    assert report.resolved_graph is None
    assert report.n_bootstrap == 0
    assert any("modulenotfounderror" in warning.lower() for warning in report.warnings)


def test_fci_discovery_graceful_fallback_on_timeout(monkeypatch) -> None:
    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error="FCI timeout after 0.10s",
            timed_out=True,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = FCIDiscovery.pure_step(_state(), params={"timeout_seconds": 1})
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.graph.pag_identification_policy is PAGIdentificationPolicy.CONSERVATIVE
    assert report.graph.edges == []
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert report.n_bootstrap == 0
    assert any("timeout" in warning.lower() for warning in report.warnings)


def test_ges_discovery_bootstrap_stability_is_bounded(monkeypatch) -> None:
    call_count = {"value": 0}

    def _fake_runner(**kwargs):
        del kwargs
        idx = call_count["value"]
        call_count["value"] += 1
        adjacency = _adj_with_xy_edge() if idx in {0, 1, 3} else _adj_without_edges()
        return constraint_module._DiscoveryExecutionResult(
            adjacency=adjacency,
            metadata={},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = GESDiscovery.pure_step(
        _state(),
        params={"n_bootstrap": 3, "timeout_seconds": 60},
    )
    report = output["report"]

    assert report.n_bootstrap == 3
    assert report.bootstrap_stability
    for score in report.bootstrap_stability.values():
        assert 0.0 <= score <= 1.0


def test_endpoint_code_mapping_is_deterministic_and_warns_on_unknown_codes() -> None:
    adjacency = np.array(
        [
            [0, -1, 4],
            [1, 0, 1],
            [5, -1, 0],
        ],
        dtype=int,
    )

    edges, warnings = constraint_module._adjacency_to_edges(
        adjacency=adjacency,
        variable_names=["X", "Y", "Z"],
    )

    assert {(edge.src, edge.dst) for edge in edges} == {("X", "Y"), ("Z", "Y")}
    assert all(edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW for edge in edges)
    assert any("unsupported_endpoint_code_pair" in warning for warning in warnings)


def test_fci_report_keeps_pag_and_emits_resolved_dag(monkeypatch) -> None:
    adjacency = np.array(
        [
            [0, 2, 0],
            [1, 0, 0],
            [0, 0, 0],
        ],
        dtype=int,
    )

    def _fake_runner(**kwargs):
        del kwargs
        return constraint_module._DiscoveryExecutionResult(
            adjacency=adjacency,
            metadata={"engine": "fake"},
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(constraint_module, "_run_discovery_with_timeout", _fake_runner)

    output = FCIDiscovery.pure_step(_state(), params={"n_bootstrap": 0})
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.graph.pag_identification_policy is PAGIdentificationPolicy.CONSERVATIVE
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG


@pytest.mark.integration
def test_fci_var1_emits_pag_uncertainty_when_causallearn_available() -> None:
    pytest.importorskip("causallearn")

    rng = np.random.default_rng(13)
    n = 1400
    latent = rng.normal(0.0, 1.0, size=n)
    x = 0.95 * latent + rng.normal(0.0, 0.4, size=n)
    y = 0.90 * latent + rng.normal(0.0, 0.4, size=n)

    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y]),
        variable_names=["X", "Y"],
    )

    output = FCIDiscovery.pure_step(
        state,
        params={
            "significance_level": 0.01,
            "indep_test": "fisherz",
            "timeout_seconds": 180,
            "n_bootstrap": 0,
        },
    )
    report = output["report"]

    assert report.graph.graph_type is GraphType.PAG
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert any(
        edge.mark_src is EdgeMark.CIRCLE
        or edge.mark_dst is EdgeMark.CIRCLE
        or (edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW)
        for edge in report.graph.edges
    )


@pytest.mark.integration
def test_pc_and_ges_recover_chain_adjacency_when_causallearn_available() -> None:
    pytest.importorskip("causallearn")

    rng = np.random.default_rng(21)
    n = 1200
    x = rng.normal(0.0, 1.0, size=n)
    y = 0.9 * x + rng.normal(0.0, 0.4, size=n)
    z = 0.8 * y + rng.normal(0.0, 0.4, size=n)
    state = TabularCausalDiscoveryData(
        data=np.column_stack([x, y, z]),
        variable_names=["X", "Y", "Z"],
    )

    pc_report = PCDiscovery.pure_step(
        state,
        params={"significance_level": 0.01, "timeout_seconds": 180, "n_bootstrap": 0},
    )["report"]
    ges_report = GESDiscovery.pure_step(
        state,
        params={"score_func": "local_score_BIC", "timeout_seconds": 180, "n_bootstrap": 0},
    )["report"]

    for report in (pc_report, ges_report):
        adjacency_pairs = {frozenset((edge.src, edge.dst)) for edge in report.graph.edges}
        assert frozenset({"X", "Y"}) in adjacency_pairs
        assert frozenset({"Y", "Z"}) in adjacency_pairs
