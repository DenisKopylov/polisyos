"""Owner-bound input controls for candidate-experiment terminal replay."""

from __future__ import annotations

import hashlib
from dataclasses import replace
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
    AcquisitionEvaluationFrontierRecord,
    AcquisitionEvaluationFrontierValue,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation_history import (
    _candidate_experiment_frontier_transition_for_history,
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
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
    _append_action,
    _bootstrap,
    _create_action_job,
)


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
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "9"),
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
        lambda *_args, **_kwargs: None,
    )
    return database, artifact_store, sink, _requested_phase()


def _persist_requested_phase(
    sink: AcquisitionRouteLoopAuthoritySink,
    phase: AcquisitionCandidateExperimentPhaseReceipt,
) -> AcquisitionActionHeadRecord:
    event_suffix = (
        "experiment_phase_requested_" + hashlib.sha256(phase.receipt_id.encode()).hexdigest()[:16]
    )
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


def test_candidate_experiment_frontier_history_reopens_immutable_sql_versions(
    tmp_path: Path,
) -> None:
    """Retained and blocked history resolve their recorded frontier versions."""
    database = ControlPlaneStore(
        backend="sqlite", sqlite_path=tmp_path / "frontier-history.sqlite3"
    )
    _source_job, frontier1, _progress = _bootstrap(database, tmp_path)
    key = frontier1.key
    retained_job, retained_worker, retained_attempt = _create_action_job(
        database, job_id="retained-action"
    )
    retained_value = AcquisitionEvaluationFrontierValue(
        selected_evaluation_witness_ref=frontier1.selected_evaluation_witness_ref,
        selected_evaluation_content_hash=frontier1.selected_evaluation_content_hash,
        basis_ref=frontier1.basis_ref,
        basis_content_hash=frontier1.basis_content_hash,
        decision_ref=_hash("6"),
    )
    retained = _append_action(
        database,
        job=retained_job,
        worker_id=retained_worker,
        attempt=retained_attempt,
        key=key,
        expected_revision=frontier1.revision,
        expected_ref=frontier1.frontier_ref,
        route_id="retained-action",
        replacement=retained_value,
    )
    frontier2 = retained.frontier
    assert frontier2.revision == frontier1.revision + 1
    assert frontier2.basis_ref == frontier1.basis_ref
    assert frontier2.selected_evaluation_witness_ref == frontier1.selected_evaluation_witness_ref
    assert frontier2.selected_evaluation_content_hash == frontier1.selected_evaluation_content_hash

    blocked_job, blocked_worker, blocked_attempt = _create_action_job(
        database, job_id="blocked-action"
    )
    blocked = _append_action(
        database,
        job=blocked_job,
        worker_id=blocked_worker,
        attempt=blocked_attempt,
        key=key,
        expected_revision=frontier2.revision,
        expected_ref=frontier2.frontier_ref,
        route_id="blocked-action",
        replacement=None,
    )
    assert blocked.head.evaluation_frontier_before_ref == frontier2.frontier_ref

    later_job, later_worker, later_attempt = _create_action_job(database, job_id="later-action")
    later_value = AcquisitionEvaluationFrontierValue(
        selected_evaluation_witness_ref=_hash("7"),
        selected_evaluation_content_hash=_hash("8"),
        basis_ref=_hash("9"),
        basis_content_hash=_hash("a"),
        decision_ref=_hash("b"),
    )
    later = _append_action(
        database,
        job=later_job,
        worker_id=later_worker,
        attempt=later_attempt,
        key=key,
        expected_revision=frontier2.revision,
        expected_ref=frontier2.frontier_ref,
        route_id="later-action",
        replacement=later_value,
    )
    assert later.frontier.revision == frontier2.revision + 1
    assert database.read_acquisition_evaluation_frontier(key) == later.frontier

    def resolve(
        *,
        head: AcquisitionActionHeadRecord,
        before_ref: str | None,
        before_revision: int,
        selected: AcquisitionEvaluationFrontierRecord,
    ) -> tuple[
        AcquisitionEvaluationFrontierRecord | None,
        AcquisitionEvaluationFrontierRecord | None,
    ]:
        return _candidate_experiment_frontier_transition_for_history(
            control_store=database,
            key=key,
            head=head,
            expected_frontier_ref=before_ref,
            expected_frontier_revision=before_revision,
            selected_basis_ref=selected.basis_ref,
            selected_basis_content_hash=selected.basis_content_hash,
            decision_ref=selected.decision_ref,
            selected_evaluation_witness_ref=selected.selected_evaluation_witness_ref,
            selected_evaluation_content_hash=selected.selected_evaluation_content_hash,
        )

    retained_before, retained_after = resolve(
        head=retained.head,
        before_ref=frontier1.frontier_ref,
        before_revision=frontier1.revision,
        selected=frontier2,
    )
    assert retained_before == frontier1
    assert retained_after == frontier2

    blocked_before, blocked_after = _candidate_experiment_frontier_transition_for_history(
        control_store=database,
        key=key,
        head=blocked.head,
        expected_frontier_ref=frontier2.frontier_ref,
        expected_frontier_revision=frontier2.revision,
        selected_basis_ref="sha256:" + "c" * 64,
        selected_basis_content_hash="sha256:" + "d" * 64,
        decision_ref="sha256:" + "e" * 64,
        selected_evaluation_witness_ref="sha256:" + "f" * 64,
        selected_evaluation_content_hash=None,
    )
    assert blocked_before == frontier2
    assert blocked_after == frontier2

    with pytest.raises(ValueError, match="candidate_experiment_terminal_frontier_after_mismatch"):
        resolve(
            head=replace(retained.head, evaluation_frontier_ref=frontier1.frontier_ref),
            before_ref=frontier1.frontier_ref,
            before_revision=frontier1.revision,
            selected=frontier2,
        )
    with pytest.raises(ValueError, match="candidate_experiment_terminal_frontier_after_mismatch"):
        resolve(
            head=replace(retained.head, evaluation_frontier_ref=later.frontier.frontier_ref),
            before_ref=frontier1.frontier_ref,
            before_revision=frontier1.revision,
            selected=later.frontier,
        )
    missing_frontier_ref = _hash("2")
    assert database.get_acquisition_evaluation_frontier_by_ref(missing_frontier_ref) is None
    with pytest.raises(ValueError, match="candidate_experiment_terminal_frontier_before_mismatch"):
        resolve(
            head=replace(
                retained.head,
                evaluation_frontier_before_ref=missing_frontier_ref,
            ),
            before_ref=missing_frontier_ref,
            before_revision=frontier1.revision,
            selected=frontier2,
        )
    with pytest.raises(ValueError, match="candidate_experiment_terminal_frontier_after_mismatch"):
        resolve(
            head=replace(retained.head, evaluation_frontier_ref=missing_frontier_ref),
            before_ref=frontier1.frontier_ref,
            before_revision=frontier1.revision,
            selected=frontier2,
        )
    with pytest.raises(ValueError, match="candidate_experiment_terminal_blocked_frontier_mismatch"):
        _candidate_experiment_frontier_transition_for_history(
            control_store=database,
            key=key,
            head=replace(blocked.head, evaluation_frontier_ref=later.frontier.frontier_ref),
            expected_frontier_ref=frontier2.frontier_ref,
            expected_frontier_revision=frontier2.revision,
            selected_basis_ref="sha256:" + "c" * 64,
            selected_basis_content_hash="sha256:" + "d" * 64,
            decision_ref="sha256:" + "e" * 64,
            selected_evaluation_witness_ref="sha256:" + "f" * 64,
            selected_evaluation_content_hash=None,
        )

    _foreign_source_job, foreign_frontier, _foreign_progress = _bootstrap(
        database, tmp_path, source_job_id="source-foreign"
    )
    with pytest.raises(ValueError, match="candidate_experiment_terminal_frontier_before_mismatch"):
        resolve(
            head=replace(
                retained.head,
                evaluation_frontier_before_ref=foreign_frontier.frontier_ref,
            ),
            before_ref=foreign_frontier.frontier_ref,
            before_revision=foreign_frontier.revision,
            selected=frontier2,
        )

    database.close()


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
