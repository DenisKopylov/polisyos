"""Owner-bound input controls for candidate-experiment terminal replay."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_for_manifest,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation_history import (
    verify_candidate_experiment_terminal_history,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision
from tests._helpers.runtime_http import _build_control_service


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash("f"),
    )


def _requested_phase() -> AcquisitionCandidateExperimentPhaseReceipt:
    scope = CandidateUnpricedPolicyScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        design_problem_ref=_hash("1"),
        design_problem_basis_ref=_hash("2"),
        source_cycle_index=0,
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        requirement_id="requirement-a",
        compiled_requirement_ref="compiled-requirement-a",
        candidate_digest=_hash("4"),
        planner_report_hash=_hash("5"),
        compiled_ref=_ref("runtime.compiled_recursive_generation_cycle", "6"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "7"),
        compiler_report_ref=_ref("runtime.data_requirement_compilation_report", "8"),
        configured_port_source_ref=_ref(
            "runtime.quality.n7_configured_candidate_port_source", "9"
        ),
    )
    return AcquisitionCandidateExperimentPhaseReceipt(
        receipt_id="action-a.requested",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id=_hash("a"),
        action_generation=1,
        job_id="action-a",
        source_payload_ref=_hash("b"),
        capability_manifest_ref=_hash("c"),
        request_content_hash=_hash("d"),
        policy_scope=scope,
        policy_ref=_ref("runtime_quality.candidate_unpriced_acquisition_policy", "e"),
        authority_decision_ref=_ref("runtime_quality.agent_action_authority_decision", "0"),
        voi_decision=LoopVOIDecision(
            candidate_id="candidate-a",
            terminal_kind="human_decision_required",
            scheduler_action="reject",
            scheduler_reason="roi_below_threshold",
            priority=0.0,
            next_action="escalate",
            reason="roi_below_threshold",
        ),
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        generated_at=datetime(2026, 11, 4, tzinfo=UTC),
    )


def _phase_writer_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    ControlPlaneStore,
    FileSystemCAS,
    AcquisitionRouteLoopAuthoritySink,
    AcquisitionCandidateExperimentPhaseReceipt,
]:
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    artifact_store = FileSystemCAS(tmp_path / "cas")
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=artifact_store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=database,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_live_authority",
        lambda *_: None,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_phase_owner",
        lambda *_: None,
    )
    return database, artifact_store, sink, _requested_phase()


def _persist_requested_phase(
    sink: AcquisitionRouteLoopAuthoritySink,
    phase: AcquisitionCandidateExperimentPhaseReceipt,
) -> AcquisitionActionHeadRecord:
    event_suffix = "experiment_phase_requested_" + hashlib.sha256(
        phase.receipt_id.encode()
    ).hexdigest()[:16]
    head = sink._persist_receipt(
        phase,
        artifact_kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        schema_name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
        event_type="polisyos.runtime.acquisition.candidate_experiment_phase.v1",
        event_suffix=event_suffix,
        receipt_type=AcquisitionCandidateExperimentPhaseReceipt,
        receipt_label="candidate_experiment_phase",
    )
    assert isinstance(head, AcquisitionActionHeadRecord)
    return head


def test_terminal_history_rejects_unselected_terminal_reference(tmp_path: Path) -> None:
    """An artifact ID without its selected manifest profile is not a history input."""
    service = _build_control_service(tmp_path / "control")
    head = AcquisitionActionHeadRecord(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id="sha256:" + "1" * 64,
        action_generation=1,
        head_generation=1,
        receipt_ref="sha256:" + "2" * 64,
        receipt_sha256="sha256:" + "2" * 64,
        durable_event_id="event-a",
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        job_id="action-a",
        predecessor_receipt_ref="sha256:" + "3" * 64,
        created_at=datetime.now(UTC),
    )
    terminal_ref = ArtifactRef(
        artifact_id="sha256:" + "4" * 64,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
    )
    try:
        with pytest.raises(
            ValueError,
            match="candidate_experiment_terminal_history_owner_not_established",
        ):
            verify_candidate_experiment_terminal_history(
                control_service=service,
                head=head,
                terminal_ref=terminal_ref,
            )
    finally:
        service._control_store.close()


def test_phase_chain_uses_sql_selected_profile_when_default_is_alternate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A phase row selects its writer profile when CAS default is another view."""
    database, artifact_store, sink, phase = _phase_writer_case(tmp_path, monkeypatch)

    try:
        replacement_ref = artifact_store.put_json(
            phase.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
                    version="1.0",
                ),
                producer=ProducerInfo(component="test.replaced_default", version="1"),
                inputs=[],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert replacement_ref.manifest_profile_sha256 is not None

        head = _persist_requested_phase(sink, phase)
        assert head.receipt_manifest_profile_sha256 is not None
        selected_ref = ArtifactRef(
            artifact_id=head.receipt_ref,
            kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
            media_type="application/json",
            manifest_profile_sha256=head.receipt_manifest_profile_sha256,
        )
        default_ref = artifact_ref_for_manifest(artifact_store.get_manifest(head.receipt_ref))
        assert default_ref.artifact_id == replacement_ref.artifact_id == selected_ref.artifact_id
        assert default_ref.manifest_profile_sha256 == replacement_ref.manifest_profile_sha256
        assert default_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256

        chain = sink._verified_candidate_experiment_phase_chain(head)
        assert len(chain) == 1
        assert chain[0].receipt == phase
        assert chain[0].receipt_ref == str(selected_ref.artifact_id)
    finally:
        database.close()


def test_phase_chain_keeps_legacy_profileless_default_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy profileless rows remain readable through their valid CAS default."""
    database, _artifact_store, sink, phase = _phase_writer_case(tmp_path, monkeypatch)

    try:
        head = _persist_requested_phase(sink, phase)
        database._execute(
            "UPDATE runtime_acquisition_action_heads "
            "SET receipt_manifest_profile_sha256 = NULL WHERE receipt_ref = ?",
            (head.receipt_ref,),
        )
        legacy_head = sink.get_head(phase)
        assert legacy_head is not None
        assert legacy_head.receipt_manifest_profile_sha256 is None

        chain = sink._verified_candidate_experiment_phase_chain(legacy_head)
        assert len(chain) == 1
        assert chain[0].receipt == phase
        assert chain[0].receipt_ref == head.receipt_ref
    finally:
        database.close()
