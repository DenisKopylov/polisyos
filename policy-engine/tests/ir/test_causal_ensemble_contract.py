from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_ensemble import (
    CausalModelEnsemble,
    EnsembleMember,
    load_causal_model_ensemble,
    persist_causal_model_ensemble,
)
from polisyos.ir.refs import CausalModelEnsembleRef


def _member(idx: int, *, weight: float = 0.5) -> EnsembleMember:
    return EnsembleMember(
        graph_ref=f"sha256:{idx:064x}",
        discovery_method=f"m{idx}",
        weight=weight,
        bootstrap_stability=0.4,
    )


def test_causal_ensemble_validates_member_cap() -> None:
    with pytest.raises(ValidationError):
        CausalModelEnsemble(members=[_member(i) for i in range(11)])


def test_causal_ensemble_edge_frequency_validation() -> None:
    ensemble = CausalModelEnsemble(
        members=[_member(1, weight=1.0)],
        edge_inclusion_frequency={"X→Y": 0.75, "Y→Z@lag=1": 0.25},
    )
    assert ensemble.edge_inclusion_frequency["X→Y"] == 0.75
    assert ensemble.edge_inclusion_frequency["Y→Z@lag=1"] == 0.25


def test_causal_ensemble_to_uncertainty_envelope_handles_empty_and_non_empty() -> None:
    ensemble = CausalModelEnsemble(
        members=[_member(1, weight=1.0)],
        edge_inclusion_frequency={"X→Y": 1.0},
    )

    empty_env = ensemble.to_uncertainty_envelope({})
    assert empty_env.gate_eligible is False
    assert empty_env.metadata["empty_estimates"] is True

    env = ensemble.to_uncertainty_envelope({"m1": [1.0, 2.0, 3.0], "m2": [4.0]})
    assert env.gate_eligible is True
    assert env.point_estimate == 2.5
    assert env.confidence_interval[0] <= env.point_estimate <= env.confidence_interval[1]


def test_causal_ensemble_artifact_roundtrip_kind(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ensemble = CausalModelEnsemble(
        members=[_member(1, weight=1.0)],
        consensus_graph_ref="sha256:" + "f" * 64,
        edge_inclusion_frequency={"X→Y": 1.0},
    )

    ref = persist_causal_model_ensemble(store, ensemble)
    loaded = load_causal_model_ensemble(store, ref)

    assert isinstance(ref, CausalModelEnsembleRef)
    assert ref.kind == "ir.causal_model_ensemble"
    assert loaded == ensemble
