"""Exercise existing Core facade exports through actual E artifact consumers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import polisyos.core as core
from polisyos.calibration import (
    evaluate_continuous,
    load_continuous_evaluation,
    persist_continuous_evaluation,
)
from polisyos.core import artifacts, canon
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator


class _CandidateGenerator:
    def generate(self, history, current_best, context):
        return {"x": 0.5}


def _report():
    return evaluate_continuous(
        y_true=[0.0, 1.0, 2.0, 3.0],
        intervals={0.75: [(-0.5, 0.5), (0.5, 1.5), (1.5, 2.5), (-1.0, 0.0)]},
    )


def test_continuous_core_facade_round_trip_and_integrity_valid_forgery(tmp_path: Path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = persist_continuous_evaluation(store, _report())
    reopened = load_continuous_evaluation(artifacts.FileSystemCAS(store.root), ref)
    assert reopened.metadata["interval_coverage"]["requested"] == 4
    assert reopened.curves["interval_coverage"][0].mean_observed == 3 / 4
    assert reopened.to_truthfulness_receipt().diagnostics["gate_eligible"] is False

    payload = canon.from_canonical_bytes(store.get_bytes(ref))
    payload["report"]["metadata"]["interval_coverage"]["observed"] = 1
    forged = store.put_json(
        payload,
        artifacts.ArtifactWriteOptions(
            kind="continuous_calibration_diagnostics",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="continuous_calibration_diagnostics", version="1.0"),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    assert store.verify(forged).ok
    with pytest.raises(ValueError, match="does not reproduce"):
        load_continuous_evaluation(artifacts.FileSystemCAS(store.root), forged)


def test_actual_persistence_consumes_core_root_binding(monkeypatch, tmp_path: Path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")

    def unavailable_options(**kwargs):
        raise RuntimeError("Core artifact export unavailable")

    # Keep the public names present, but remove the actual writer capability.
    monkeypatch.setattr(
        core,
        "artifacts",
        SimpleNamespace(ArtifactWriteOptions=unavailable_options, SchemaInfo=artifacts.SchemaInfo),
    )
    with pytest.raises(RuntimeError, match="Core artifact export unavailable"):
        persist_continuous_evaluation(store, _report())


def test_actual_salib_producer_persists_and_reopens_through_core_facade(tmp_path: Path):
    pytest.importorskip("SALib")
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = SensitivityBridge().analyze_search_space(
        [
            {"name": "x", "lower": 0.0, "upper": 10.0, "unit": "metres"},
            {"name": "z", "lower": 0.0, "upper": 1.0, "unit": "seconds"},
        ],
        lambda values: 2 * values["x"] + 3 * values["z"],
        n_trajectories=16,
        seed=43,
        store=store,
    )
    # Independent physical-range elementary effects: 2*10 and 3*1.
    assert answer["result"].mu_star == pytest.approx({"x": 20.0, "z": 3.0})
    reader = SensitivityAwareCandidateGenerator.from_artifact(
        _CandidateGenerator(), artifacts.FileSystemCAS(store.root), answer["analysis_ref"]
    )
    consumed = reader.generate([], None, {})["_sensitivity"]
    assert consumed["analysis_ref"]["artifact_id"] == str(answer["analysis_ref"].artifact_id)
    assert consumed["analysis_id"] == answer["result"].metadata["analysis_id"]
    assert consumed["population_law_status"] == "not_established"
