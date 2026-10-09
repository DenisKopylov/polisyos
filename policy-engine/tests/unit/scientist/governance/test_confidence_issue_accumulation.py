"""Confidence artifact failures retain previously accumulated consumer issues."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.uncertainty import (
    UncertaintyEnvelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass


def _context(store, state, *, min_ratio: float = 0.5) -> PassContext:
    profile = ValidationProfile.strict()
    profile = replace(
        profile,
        thresholds={**profile.thresholds, "uncertainty_min_gate_eligible_ratio": min_ratio},
    )
    return PassContext(
        ir=None,
        state={"_store": store, **state},
        registry_bundle=None,
        profile=profile,
        run_id="confidence-issue-preservation",
    )


def _envelope(store: FileSystemCAS):
    return persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=10.0,
            confidence_interval=(9.9, 10.1),
            source="ensemble",
            gate_eligible=True,
            metadata={
                "identification_verified": True,
                "proof_status": "identified",
                "verifier_role": "system_verifier",
                "identification_proof_ref": "sha256:" + "f" * 64,
            },
        ),
    )


def _simulation(store: FileSystemCAS, *, healthy: bool):
    plan = store.put_json(
        {"order": []}, PutOptions(kind="foundry.exec_plan", media_type="application/json")
    )
    metrics = store.put_json(
        {"values": {}}, PutOptions(kind="foundry.metrics", media_type="application/json")
    )
    result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        uncertainty_envelopes={"healthy": _envelope(store)} if healthy else None,
    )
    return store.put_json(
        result, PutOptions(kind="foundry.simulation_result", media_type="application/json")
    )


def _unloadable_simulation(store: FileSystemCAS, failure: str) -> SimulationResultRef:
    if failure == "missing_bytes":
        return SimulationResultRef(artifact_id="sha256:" + "b" * 64)
    if failure == "malformed_json":
        ref = store.put_bytes(
            b"{", PutOptions(kind="foundry.simulation_result", media_type="application/json")
        )
    else:
        assert failure == "wrong_model"
        ref = store.put_json(
            {"not_a_simulation": True},
            PutOptions(kind="foundry.simulation_result", media_type="application/json"),
        )
    return SimulationResultRef(artifact_id=ref.artifact_id)


def _state(location: str, causal_ref=None, simulation_ref=None) -> dict:
    refs = {}
    if causal_ref is not None:
        refs["causal_envelope_ref"] = causal_ref
    if simulation_ref is not None:
        refs["simulation_result_ref"] = simulation_ref
    return {"artifacts_index": refs} if location == "artifacts_index" else refs


def _candidate_blockers(issues):
    return [
        issue
        for issue in issues
        if issue.severity is IssueSeverity.BLOCKER
        and issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW"
        and issue.path == ["artifacts_index", "causal_envelope_ref"]
    ]


@pytest.mark.parametrize("failure", ["missing_bytes", "malformed_json", "wrong_model"])
@pytest.mark.parametrize("location", ["artifacts_index", "top_level"])
@pytest.mark.parametrize("min_ratio", [0.0, 1.0])
def test_simulation_load_failure_preserves_causal_blocker_and_warning(
    tmp_path: Path, failure: str, location: str, min_ratio: float
) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state(location, _envelope(writer), _unloadable_simulation(writer, failure))
    issues = ConfidencePass().validate(
        _context(FileSystemCAS(tmp_path), state, min_ratio=min_ratio)
    )
    actual = json.dumps([issue.model_dump(mode="json") for issue in issues], sort_keys=True)
    assert len(_candidate_blockers(issues)) == 1, actual
    assert len(issues) == 2, actual
    assert issues[0].severity is IssueSeverity.BLOCKER
    assert issues[1].severity is IssueSeverity.WARNING
    assert issues[1].code == "CONFIDENCE_SIM_RESULT_LOAD_FAILED"
    assert issues[1].path == ["artifacts_index", "simulation_result_ref"]


@pytest.mark.parametrize("failure", ["missing_bytes", "malformed_json", "wrong_model"])
@pytest.mark.parametrize("location", ["artifacts_index", "top_level"])
def test_noncausal_failed_simulation_keeps_its_existing_warning(
    tmp_path: Path, failure: str, location: str
) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state(location, simulation_ref=_unloadable_simulation(writer, failure))
    issues = ConfidencePass().validate(_context(FileSystemCAS(tmp_path), state))
    assert len(issues) == 1
    assert issues[0].severity is IssueSeverity.WARNING
    assert issues[0].code == "CONFIDENCE_SIM_RESULT_LOAD_FAILED"


@pytest.mark.parametrize("location", ["artifacts_index", "top_level"])
@pytest.mark.parametrize(
    "boundary", ["missing_store", "absent_simulation", "unresolved_causal", "malformed_causal"]
)
def test_causal_blocker_survives_other_early_return_and_degraded_paths(
    tmp_path: Path, location: str, boundary: str
) -> None:
    writer = FileSystemCAS(tmp_path)
    causal_ref = _envelope(writer)
    if boundary == "unresolved_causal":
        causal_ref = causal_ref.model_copy(update={"artifact_id": "sha256:" + "c" * 64})
    elif boundary == "malformed_causal":
        causal_ref = {"proof_status": "identified"}
    state = _state(location, causal_ref)
    reader = None if boundary == "missing_store" else FileSystemCAS(tmp_path)
    issues = ConfidencePass().validate(_context(reader, state, min_ratio=0.0))
    assert len(_candidate_blockers(issues)) == 1
    if boundary in {"unresolved_causal", "malformed_causal"}:
        assert any(issue.code == "CONFIDENCE_ENVELOPE_LOAD_FAILED" for issue in issues)


@pytest.mark.parametrize("location", ["artifacts_index", "top_level"])
@pytest.mark.parametrize("healthy", [False, True])
def test_loaded_simulation_never_replaces_existing_causal_blocker(
    tmp_path: Path, location: str, healthy: bool
) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state(location, _envelope(writer), _simulation(writer, healthy=healthy))
    issues = ConfidencePass().validate(_context(FileSystemCAS(tmp_path), state, min_ratio=0.0))
    assert len(_candidate_blockers(issues)) == 1
    assert not any(issue.code == "CONFIDENCE_SIM_RESULT_LOAD_FAILED" for issue in issues)


@pytest.mark.parametrize("healthy", [False, True])
def test_loaded_noncausal_simulation_preserves_supported_confidence_profile(
    tmp_path: Path, healthy: bool
) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state("artifacts_index", simulation_ref=_simulation(writer, healthy=healthy))
    issues = ConfidencePass().validate(_context(FileSystemCAS(tmp_path), state, min_ratio=1.0))
    assert issues == []
