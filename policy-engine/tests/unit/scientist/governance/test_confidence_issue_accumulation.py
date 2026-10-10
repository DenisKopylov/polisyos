"""Confidence artifact failures retain previously accumulated consumer issues."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


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


def _propagated_simulation(store: FileSystemCAS) -> SimulationResultRef:
    """Emit a controlled persisted result through the existing propagation node."""
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_confidence_propagation_admission",
    )
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.confidence.propagation_admission"),
    )
    input_envelope_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            metadata={
                "param_name": "data_snapshot",
                "identification_verified": True,
                "proof_status": "identified",
                "verifier_role": "system_verifier",
                "identification_proof_ref": "sha256:" + "f" * 64,
            },
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref, uncertainty_envelope_ref=input_envelope_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"healthy": 10}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    simulation_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=128),
    )
    state = ExperimentState(
        run_id="R_confidence_propagation_admission",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id)
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_ref},
        params={
            "propagation_mc_n_samples": 100,
            "propagation_mc_batch_size": 100,
            "propagation_sensitivity": {"healthy": {"data_snapshot": 1.0}},
        },
    )

    outcome = PropagateUncertaintyNode().execute(context, state)

    assert outcome.status == "ok"
    return outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]


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


def test_noncausal_simulation_without_envelopes_preserves_empty_result(tmp_path: Path) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state("artifacts_index", simulation_ref=_simulation(writer, healthy=False))
    issues = ConfidencePass().validate(_context(FileSystemCAS(tmp_path), state, min_ratio=1.0))
    assert issues == []


def test_metadata_only_healthy_envelope_remains_admission_limited(tmp_path: Path) -> None:
    writer = FileSystemCAS(tmp_path)
    state = _state("artifacts_index", simulation_ref=_simulation(writer, healthy=True))

    issues = ConfidencePass().validate(_context(FileSystemCAS(tmp_path), state, min_ratio=1.0))

    limited = next(
        issue for issue in issues if issue.code == "CONFIDENCE_ENVELOPE_ADMISSION_LIMITED"
    )
    assert limited.severity is IssueSeverity.BLOCKER
    assert limited.path == ["uncertainty_envelopes", "healthy"]
    assert "propagation_report_ref_missing" in limited.message
    assert any(issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW" for issue in issues)


def test_existing_propagation_output_remains_limited_without_admitted_verifier(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _propagated_simulation(store)

    issues = ConfidencePass().validate(
        _context(store, _state("artifacts_index", simulation_ref=simulation_ref), min_ratio=1.0)
    )

    limited = next(
        issue for issue in issues if issue.code == "CONFIDENCE_ENVELOPE_ADMISSION_LIMITED"
    )
    assert limited.severity is IssueSeverity.BLOCKER
    assert limited.path == ["uncertainty_envelopes", "healthy"]
    assert "draw_success_ledger_missing" in limited.message
    assert "draw_basis_verifier_missing" in limited.message
