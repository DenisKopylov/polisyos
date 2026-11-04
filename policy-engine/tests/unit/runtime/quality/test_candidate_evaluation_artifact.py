"""Selected candidate evaluation records use the real CAS and event reader.

The input parent artifacts are component fixtures, not a selected action or an
N5. These checks establish only persistence/selection and refusal behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo, SchemaInfo
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateAcquisitionEvaluationDecision,
    _candidate_evaluation_event_id,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash


def _decision_fixture(tmp_path: Path) -> SimpleNamespace:
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=cas)

    def parent(kind: str, tag: str):
        return cas.put_json(
            {"fixture_parent": tag},
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    action = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
    intent = parent("runtime_quality.acquisition_candidate_world_intent", "intent")
    source = parent("runtime.quality.candidate_acquisition_source", "source")
    basis = parent("runtime_quality.acquisition_evaluation_basis", "basis")
    draft = CandidateAcquisitionEvaluationDecision.model_construct(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-source",
        action_job_id="job-action",
        action_generation=1,
        route_id="sha256:" + "1" * 64,
        compiled_ref="sha256:" + "2" * 64,
        design_problem_ref="sha256:" + "3" * 64,
        design_problem_basis_ref="sha256:" + "4" * 64,
        candidate_id="candidate-a",
        source_candidate_content_hash="sha256:" + "5" * 64,
        candidate_action_ref=action,
        candidate_world_intent_ref=intent,
        candidate_source_ref=source,
        current_basis_ref=basis,
        comparison_result="not_established",
        predicate_provenance="not_established",
        reason_codes=("initial_prior_basis_not_established",),
        expected_frontier_revision=0,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC).isoformat(),
        content_hash="sha256:" + "0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"content_hash"})
    decision = CandidateAcquisitionEvaluationDecision.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )
    return SimpleNamespace(cas=cas, events=events, decision=decision)


def test_candidate_decision_reopens_exact_selected_manifest_and_event(tmp_path: Path) -> None:
    fixture = _decision_fixture(tmp_path)
    cas, events, decision = fixture.cas, fixture.events, fixture.decision
    selected = persist_acquisition_evaluation_artifact(store=cas, event_log=events, record=decision)
    assert selected.manifest_profile_sha256 is not None
    assert (
        read_acquisition_evaluation_artifact(
            store=cas,
            event_log=events,
            ref=selected,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        == decision
    )

    # Identical decision bytes under a foreign producer are a different view.
    sibling = cas.put_json(
        decision.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=decision.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=decision.ARTIFACT_SCHEMA_NAME, version="1.0"),
            producer=ProducerInfo(component="foreign.fixture", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == selected.artifact_id
    assert sibling.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="acquisition_evaluation_artifact_owner_mismatch"):
        read_acquisition_evaluation_artifact(
            store=cas,
            event_log=events,
            ref=sibling,
            record_type=CandidateAcquisitionEvaluationDecision,
        )

    # An otherwise valid selected artifact without its real event is not a
    # replayable owner record, even though its bytes remain readable.
    other_control = ControlPlaneStore(
        backend="sqlite", sqlite_path=tmp_path / "missing-event.sqlite3"
    )
    missing_event_log = RuntimeDiagnosticEventLog(store=other_control, artifact_store=cas)
    with pytest.raises((ValueError, RuntimeError), match=r"event|authority"):
        read_acquisition_evaluation_artifact(
            store=cas,
            event_log=missing_event_log,
            ref=selected,
            record_type=CandidateAcquisitionEvaluationDecision,
        )


def test_candidate_decision_recovers_owner_event_before_selected_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real event/CAS inventory recovery does not issue the decision twice."""
    fixture = _decision_fixture(tmp_path)
    decision = fixture.decision
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = fixture.cas
    bridge.event_log = fixture.events
    action = SimpleNamespace(
        action_job_id=decision.action_job_id,
        action_generation=decision.action_generation,
        candidate_source_ref=decision.candidate_source_ref,
    )
    closure = SimpleNamespace(
        tenant_id=decision.tenant_id,
        cell_id=decision.cell_id,
        run_id=decision.run_id,
        source_job_id=decision.source_job_id,
        route_id=decision.route_id,
        compiled_ref=decision.compiled_ref,
        design_problem_ref=decision.design_problem_ref,
        design_problem_basis_ref=decision.design_problem_basis_ref,
        source_cycle=SimpleNamespace(
            selected_candidate_ref=decision.candidate_id,
            selected_candidate_content_hash=decision.source_candidate_content_hash,
        ),
    )
    root = tmp_path / "selector"
    root.mkdir()
    overlay = root / "overlay.sqlite"
    monkeypatch.setattr(bridge, "_require_selected_candidate_action", lambda **_: action)
    monkeypatch.setattr(bridge, "candidate_source_selection", lambda _: object())
    monkeypatch.setattr(bridge, "_candidate_source_prior_owner", lambda **_: (None, None, None))
    monkeypatch.setattr(
        bridge,
        "_candidate_world_materialization_intent",
        lambda **_: (decision.candidate_world_intent_ref, object()),
    )
    monkeypatch.setattr(bridge, "_paths", lambda *_args, **_kwargs: (overlay, None))
    writer = bridge._write_candidate_world_pointer

    def crash_before_pointer(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected_pointer_crash")

    monkeypatch.setattr(bridge, "_write_candidate_world_pointer", crash_before_pointer)
    with pytest.raises(OSError, match="injected_pointer_crash"):
        dispatch._select_candidate_evaluation_artifact(
            bridge=bridge, closure=closure, record=decision
        )
    event_id = _candidate_evaluation_event_id(decision)
    assert len(fixture.events.list_events(event_id=event_id, limit=2)) == 1
    assert not (root / (event_id + ".selected.json")).exists()

    monkeypatch.setattr(bridge, "_write_candidate_world_pointer", writer)

    def unexpected_reissue(**_kwargs: object) -> None:
        pytest.fail("recovery attempted to reissue the selected decision")

    monkeypatch.setattr(dispatch, "persist_acquisition_evaluation_artifact", unexpected_reissue)
    changed_payload = decision.model_dump(mode="json", exclude={"content_hash"})
    changed_payload["generated_at"] = "2026-11-03T01:00:00+00:00"
    changed = CandidateAcquisitionEvaluationDecision.model_validate(
        {**changed_payload, "content_hash": exact_n5_content_hash(changed_payload)}
    )
    with pytest.raises(ValueError, match="candidate_evaluation_selected_record_changed"):
        dispatch._select_candidate_evaluation_artifact(
            bridge=bridge, closure=closure, record=changed
        )
    assert not (root / (event_id + ".selected.json")).exists()
    recovered = dispatch._candidate_evaluation_artifact_for_recovery(
        bridge=bridge,
        closure=closure,
        candidate_action_ref=decision.candidate_action_ref,
        role="decision",
    )
    assert recovered is not None
    original_ref, original_record = recovered
    assert original_record == decision
    assert original_record.generated_at == "2026-11-03T00:00:00+00:00"
    assert not (root / (event_id + ".selected.json")).exists()
    selected = dispatch._select_candidate_evaluation_artifact(
        bridge=bridge, closure=closure, record=original_record
    )
    assert selected == original_ref
    assert selected.manifest_profile_sha256 is not None
    assert (root / (event_id + ".selected.json")).exists()
    assert (
        read_acquisition_evaluation_artifact(
            store=fixture.cas,
            event_log=fixture.events,
            ref=selected,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        == decision
    )
