from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import pcmci_discovery as pcmci_module
from polisyos.foundry.methods.catalog.causal.pcmci_discovery import PCMCIDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import TimeSeriesCausalData


def _state() -> TimeSeriesCausalData:
    data = np.array(
        [
            [0.1, 0.2],
            [0.2, 0.3],
            [0.25, 0.5],
            [0.31, 0.7],
            [0.45, 0.9],
            [0.6, 1.1],
        ],
        dtype=float,
    )
    return TimeSeriesCausalData(data=data, variable_names=["X", "Y"])


def test_pcmci_discovery_graceful_fallback_on_missing_backend(monkeypatch):
    def _fake_runner(**kwargs):
        del kwargs
        return pcmci_module._PCMCIExecutionResult(
            edges=[],
            error="ModuleNotFoundError: No module named 'tigramite'",
            timed_out=False,
        )

    monkeypatch.setattr(pcmci_module, "_run_pcmci_with_timeout", _fake_runner)

    output = PCMCIDiscovery.pure_step(_state(), params={})
    report = output["report"]

    assert report.method == "pcmci+"
    assert report.graph.nodes == ["X", "Y"]
    assert report.graph.edges == []
    assert report.n_bootstrap == 0
    assert any("modulenotfounderror" in warning.lower() for warning in report.warnings)


def test_pcmci_discovery_graceful_fallback_on_timeout(monkeypatch):
    def _fake_runner(**kwargs):
        del kwargs
        return pcmci_module._PCMCIExecutionResult(
            edges=[],
            error="PCMCI timeout after 0.10s",
            timed_out=True,
        )

    monkeypatch.setattr(pcmci_module, "_run_pcmci_with_timeout", _fake_runner)

    output = PCMCIDiscovery.pure_step(_state(), params={"timeout_seconds": 1})
    report = output["report"]

    assert report.graph.edges == []
    assert report.n_bootstrap == 0
    assert any("timeout" in warning.lower() for warning in report.warnings)


def test_pcmci_discovery_bootstrap_stability_is_bounded(monkeypatch):
    base_edge = pcmci_module.CausalEdge(
        src="X",
        dst="Y",
        lag=1,
        p_value=0.02,
        data_confidence=0.98,
        sources=[pcmci_module.EdgeSource.DATA],
        combined_confidence=0.9,
    )

    call_count = {"value": 0}

    def _fake_runner(**kwargs):
        del kwargs
        current = call_count["value"]
        call_count["value"] += 1
        if current == 0:
            return pcmci_module._PCMCIExecutionResult(
                edges=[base_edge],
                error=None,
                timed_out=False,
            )
        if current in {1, 3}:
            return pcmci_module._PCMCIExecutionResult(
                edges=[base_edge],
                error=None,
                timed_out=False,
            )
        return pcmci_module._PCMCIExecutionResult(
            edges=[],
            error=None,
            timed_out=False,
        )

    monkeypatch.setattr(pcmci_module, "_run_pcmci_with_timeout", _fake_runner)

    output = PCMCIDiscovery.pure_step(
        _state(),
        params={
            "n_bootstrap": 3,
            "timeout_seconds": 120,
            "max_lag": 1,
            "cond_ind_test": "par_corr",
        },
    )
    report = output["report"]

    assert report.n_bootstrap == 3
    assert report.bootstrap_stability
    for score in report.bootstrap_stability.values():
        assert 0.0 <= score <= 1.0


def test_pcmci_discovery_bootstrap_truncation_updates_completed_count(monkeypatch):
    base_edge = pcmci_module.CausalEdge(
        src="X",
        dst="Y",
        lag=1,
        p_value=0.01,
        data_confidence=0.99,
        sources=[pcmci_module.EdgeSource.DATA],
        combined_confidence=0.9,
    )

    call_count = {"value": 0}

    def _fake_runner(**kwargs):
        del kwargs
        current = call_count["value"]
        call_count["value"] += 1
        if current == 0:
            return pcmci_module._PCMCIExecutionResult(
                edges=[base_edge],
                error=None,
                timed_out=False,
            )
        if current == 1:
            return pcmci_module._PCMCIExecutionResult(
                edges=[base_edge],
                error=None,
                timed_out=False,
            )
        return pcmci_module._PCMCIExecutionResult(
            edges=[],
            error="PCMCI timeout after 0.01s",
            timed_out=True,
        )

    monkeypatch.setattr(pcmci_module, "_run_pcmci_with_timeout", _fake_runner)

    output = PCMCIDiscovery.pure_step(
        _state(),
        params={
            "n_bootstrap": 3,
            "timeout_seconds": 120,
            "max_lag": 1,
            "cond_ind_test": "par_corr",
        },
    )
    report = output["report"]

    assert report.n_bootstrap == 1
    assert report.bootstrap_stability == {"X->Y@lag=1": 1.0}
    assert any("bootstrap_truncated" in warning for warning in report.warnings)


def test_pcmci_discovery_var1_detects_lagged_edge_when_tigramite_available():
    pytest.importorskip("tigramite")

    rng = np.random.default_rng(7)
    n = 500
    x = np.zeros(n, dtype=float)
    y = np.zeros(n, dtype=float)
    for t in range(1, n):
        x[t] = 0.9 * x[t - 1] + rng.normal(0.0, 0.1)
        y[t] = 0.8 * x[t - 1] + 0.5 * y[t - 1] + rng.normal(0.0, 0.1)

    state = TimeSeriesCausalData(
        data=np.column_stack([x, y]),
        variable_names=["X", "Y"],
    )

    output = PCMCIDiscovery.pure_step(
        state,
        params={
            "max_lag": 1,
            "n_bootstrap": 0,
            "significance_level": 0.05,
            "cond_ind_test": "par_corr",
            "timeout_seconds": 120,
        },
    )
    report = output["report"]

    edge_keys = {f"{edge.src}->{edge.dst}@lag={edge.lag}" for edge in report.graph.edges}
    assert "X->Y@lag=1" in edge_keys
