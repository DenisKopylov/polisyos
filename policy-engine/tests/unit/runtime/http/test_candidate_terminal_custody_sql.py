"""Real SQL tests for synchronous Scientific terminal custody."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.runtime.http.services import control_plane_store
from polisyos.runtime.http.services.control.run_lifecycle import (
    _acquisition_route_receipt_inputs,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionEvaluationFrontierCAS,
    AcquisitionEvaluationFrontierRecord,
    AcquisitionEvaluationFrontierValue,
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceiptV2
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)
from tests.unit.runtime.http.test_control_plane_store_action_head_history import (
    _action_scope,
    _append_head,
    _create_pending_action_job,
    _make_store,
    _pending_authorization_cas,
)
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
    _bootstrap,
    _lease_job,
    _sha,
    _value,
)


def _custody_case(
    tmp_path: Path,
) -> tuple[ControlPlaneStore, dict[str, Any], AcquisitionEvaluationFrontierRecord]:
    store = _make_store(tmp_path)
    _, frontier, _ = _bootstrap(store, tmp_path, source_job_id="source-job")
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_sha("request"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_sha("requested-profile"),
    )
    refreshed = _append_head(
        store,
        scope,
        receipt_ref=_sha("refreshed"),
        expected_head_generation=1,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="authorization_refreshed",
        receipt_manifest_profile_sha256=_sha("refreshed-profile"),
        pending_authorization_cas=_pending_authorization_cas(job),
    )
    worker, attempt = _lease_job(store, job, "prior-worker")
    head = refreshed
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        for phase in ("executing", "outcome_selected", "candidate_input_reentry_pending"):
            head = _append_head(
                store,
                scope,
                receipt_ref=_sha(phase),
                expected_head_generation=head.head_generation,
                predecessor_receipt_ref=head.receipt_ref,
                receipt_phase=phase,
                receipt_manifest_profile_sha256=_sha(f"{phase}-profile"),
            )
        # Stock fenced failure derives its owner from the live creation/fence
        # protocol and retains adjacent projections from that same attempt.
        store.upsert_progress(
            job_id=job.job_id, progress={"diagnostic_events": [{"event_id": "prior-attempt"}]}
        )
        store.fail_job(
            job_id=job.job_id,
            error_message="interrupted publication",
            progress={"state": "failed", "phase": "candidate_experiment", "attempt": attempt},
        )
    terminal = ArtifactRef(
        artifact_id=ArtifactID(_sha("orphan terminal")),
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=_sha("terminal-profile"),
    )
    receipt_id = f"{job.job_id}.candidate-experiment.terminal"
    event_id = (
        f"evt_acquisition_1_experiment_terminal_{sha256(receipt_id.encode()).hexdigest()[:16]}"
    )
    replacement = _value("C witness", "C selection")
    cas = AcquisitionEvaluationFrontierCAS(
        key=frontier.key,
        expected_revision=frontier.revision,
        expected_frontier_ref=frontier.frontier_ref,
        replacement=replacement,
    )
    event = DiagnosticEvent(
        event_id=event_id,
        event_source="polisyos.runtime.quality.acquisition_route_loop",
        event_type="polisyos.runtime.acquisition.candidate_experiment_terminal.v1",
        event_time=datetime.now(UTC),
        event_subject=f"run/{job.run_id}/job/{job.job_id}/acquisition/terminal",
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id="trace-c",
        span_id="span-terminal",
        parent_span_id=None,
        run_id=head.run_id,
        job_id=head.job_id,
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        producer_component="polisyos.runtime.acquisition_route_loop",
        producer_version="1.0",
        execution_profile="governed",
        phase="acquisition_route_loop",
        state_before="candidate_input_reentry_pending",
        state_after="terminal",
        payload_ref=str(terminal.artifact_id),
        artifact_refs=(str(terminal.artifact_id),),
        input_refs=(
            head.receipt_ref,
            replacement.basis_ref,
            replacement.decision_ref,
            replacement.selected_evaluation_witness_ref,
        ),
        blocking_status="non_blocking",
        redaction_policy_ref=None,
        duplicate_of=None,
        dedupe_key=None,
    )
    store.append_diagnostic_event(event=event)
    expiry = int(time.time()) + 300
    assert store.consume_step_up_assertion(assertion_id="step-up", expires_at=expiry)
    return (
        store,
        {
            "expected_job": store.get_job(job.job_id),
            "expected_head": head,
            "terminal_ref": terminal,
            "terminal_event_id": event_id,
            "frontier_cas": cas,
            "actor_subject": "tester",
            "resource_digest": _sha("bound custody resource"),
            "authority_expires_at": expiry,
            "step_up_sha256": _sha("step-up"),
        },
        frontier,
    )


def _ordinary_custody_case(
    tmp_path: Path,
) -> tuple[ControlPlaneStore, dict[str, Any], AcquisitionEvaluationFrontierRecord]:
    store = _make_store(tmp_path)
    _, frontier, _ = _bootstrap(store, tmp_path, source_job_id="source-job")
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_sha("ordinary-request"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_sha("ordinary-request-profile"),
        job_id=job.job_id,
    )
    refreshed = _append_head(
        store,
        scope,
        receipt_ref=_sha("ordinary-refreshed"),
        expected_head_generation=requested.head_generation,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="authorization_refreshed",
        receipt_manifest_profile_sha256=_sha("ordinary-refreshed-profile"),
        pending_authorization_cas=_pending_authorization_cas(job),
        job_id=job.job_id,
    )
    worker, attempt = _lease_job(store, job, "ordinary-prior-worker")
    head = refreshed
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        for phase in ("executing", "outcome_selected"):
            head = _append_head(
                store,
                scope,
                receipt_ref=_sha(f"ordinary-{phase}"),
                expected_head_generation=head.head_generation,
                predecessor_receipt_ref=head.receipt_ref,
                receipt_phase=phase,
                receipt_manifest_profile_sha256=_sha(f"ordinary-{phase}-profile"),
                job_id=job.job_id,
            )
        head = store.advance_acquisition_action_head(
            **scope,
            expected_head_generation=head.head_generation,
            receipt_ref=_sha("ordinary-world-pending"),
            receipt_sha256=_sha("ordinary-world-pending"),
            durable_event_id="event-ordinary-world-pending",
            coarse_phase="world_committed",
            receipt_phase="world_committed_reentry_pending",
            recovery_state="reentry_recovery_required",
            job_id=job.job_id,
            predecessor_receipt_ref=head.receipt_ref,
            receipt_manifest_profile_sha256=_sha("ordinary-world-pending-profile"),
        )
        store.upsert_progress(
            job_id=job.job_id,
            progress={"diagnostic_events": [{"event_id": "ordinary-prior-attempt"}]},
        )
        store.fail_job(
            job_id=job.job_id,
            error_message="interrupted ordinary terminal publication",
            progress={
                "state": "failed",
                "phase": "acquisition_model_revision",
                "attempt": attempt,
            },
        )

    # Model the existing pre-profile legacy head; today's writer correctly
    # refuses to create a profile downgrade as a new lifecycle transition.
    with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
        connection.execute(
            "UPDATE runtime_acquisition_action_heads "
            "SET receipt_manifest_profile_sha256 = NULL WHERE job_id = ? AND receipt_ref = ?",
            (job.job_id, head.receipt_ref),
        )
    head = store.get_acquisition_action_head(**scope)
    assert head is not None and head.receipt_manifest_profile_sha256 is None

    def ref(label: str, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID(_sha(label)),
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=_sha(f"{label}-profile"),
        )

    reentry = ref("ordinary-reentry", "runtime_quality.acquisition_overlay_reentry_receipt")
    selected_execution = ref(
        "ordinary-selected-execution", "runtime.quality.candidate_simulation_execution"
    )
    selected_basis = ref("ordinary-selected-basis", "runtime_quality.acquisition_evaluation_basis")
    decision = ref("ordinary-selected-decision", "runtime_quality.acquisition_evaluation_decision")
    selected = AcquisitionSelectedEvaluation(
        candidate_id=frontier.key.candidate_id,
        candidate_content_hash=_sha("ordinary-candidate-content"),
        design_problem_ref=frontier.key.design_problem_ref,
        world_model_record_hash=_sha("ordinary-world-record"),
        evaluation_job_id=job.job_id,
        evaluation_run_id=job.run_id,
        generation_run_id="ordinary-generation-run",
        cycle_index=0,
        n4_source_ref=ref("ordinary-n4", "runtime.quality.n4_candidate_scenario_source"),
        context_job_ref=ref("ordinary-context", "runtime.quality.cycle_substrate_context_job"),
        n5_input_ref=ref("ordinary-n5-input", "runtime.quality.candidate_simulation_n5_input"),
        n5_execution_ref=selected_execution,
        n5_result_ref=ref("ordinary-n5-result", "polisyos.runtime.joint_simulation_result"),
        basis_ref=selected_basis,
    )
    generated_at = datetime.now(UTC)
    terminal = AcquisitionRouteLoopReceiptV2(
        receipt_id=f"{job.job_id}.terminal.v2",
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
        action_generation=head.action_generation,
        job_id=head.job_id,
        compiled_ref=_sha("ordinary-compiled"),
        planner_report_hash=_sha("ordinary-planner"),
        cost_basis_hash=_sha("ordinary-cost-basis"),
        decision_ref=_sha("ordinary-route-decision"),
        terminal_outcome="reentry_completed",
        predecessor_receipt_ref=head.receipt_ref,
        owner_receipt_refs=(str(reentry.artifact_id), str(decision.artifact_id)),
        reentry_receipt_ref=str(reentry.artifact_id),
        evaluation_decision_ref=decision,
        selected_basis_ref=selected_basis,
        selected_evaluation_witness_ref=selected_execution,
        selected_evaluation=selected,
        generated_at=generated_at,
    )
    terminal_digest = sha256(
        to_canonical_bytes(terminal.model_dump(mode="json"), CanonSpec(forbid_floats=False))
    ).hexdigest()
    terminal_id = f"sha256:{terminal_digest}"
    terminal_ref = ArtifactRef(
        artifact_id=ArtifactID(terminal_id),
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=_sha("ordinary-terminal-profile"),
    )
    frontier_cas = AcquisitionEvaluationFrontierCAS(
        key=frontier.key,
        expected_revision=frontier.revision,
        expected_frontier_ref=frontier.frontier_ref,
        replacement=AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(selected_execution.artifact_id),
            selected_evaluation_content_hash=_sha("ordinary-execution-content"),
            basis_ref=str(selected_basis.artifact_id),
            basis_content_hash=_sha("ordinary-basis-content"),
            decision_ref=str(decision.artifact_id),
        ),
    )
    event = DiagnosticEvent(
        event_id=(f"evt_acquisition_{head.action_generation}_loop_terminal_{terminal_digest}"),
        event_source="polisyos.runtime.quality.acquisition_route_loop",
        event_type="polisyos.runtime.acquisition.route_loop.v2",
        event_time=terminal.generated_at,
        event_subject=f"run/{head.run_id}/job/{head.job_id}/acquisition/terminal",
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id=f"trace-{head.job_id}",
        span_id="span-terminal",
        parent_span_id=None,
        run_id=head.run_id,
        job_id=head.job_id,
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        producer_component="polisyos.runtime.acquisition_route_loop",
        producer_version="2026.08.28+ds15-c02",
        execution_profile="governed",
        phase="acquisition_route_loop",
        state_before=head.receipt_phase,
        state_after="terminal",
        payload_ref=terminal_id,
        artifact_refs=(terminal_id,),
        input_refs=_acquisition_route_receipt_inputs(terminal),
        blocking_status="non_blocking",
        redaction_policy_ref=None,
        duplicate_of=None,
        dedupe_key=f"{head.job_id}:acquisition_route_loop:{terminal.receipt_id}:cas_write",
    )
    prepared_event = RuntimeDiagnosticEventLog(
        store=store,
        artifact_store=object(),
    ).prepare(event, payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True))
    expiry = int(time.time()) + 300
    assert store.consume_step_up_assertion(assertion_id="ordinary-step-up", expires_at=expiry)
    return (
        store,
        {
            "expected_job": store.get_job(job.job_id),
            "expected_head": head,
            "terminal": terminal,
            "terminal_ref": terminal_ref,
            "frontier_cas": frontier_cas,
            "prepared_event": prepared_event,
            "reentry_ref": reentry,
            "selected_n5_execution_ref": selected_execution,
            "actor_subject": "tester",
            "resource_digest": _sha("ordinary bound custody resource"),
            "authority_expires_at": expiry,
            "step_up_sha256": _sha("ordinary-step-up"),
        },
        frontier,
    )


def _rows(path: Path, job_id: str) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return {
            table: connection.execute(
                f"SELECT * FROM {table} WHERE job_id = ?",  # noqa: S608 (fixed tables below)
                (job_id,),
            ).fetchall()
            for table in (
                "control_jobs",
                "control_job_events",
                "control_job_progress",
                "control_dead_letter_jobs",
                "control_outbox_events",
                "runtime_acquisition_action_heads",
                "control_diagnostic_events",
            )
        }


@pytest.mark.parametrize("prior_ack", [False, True])
def test_candidate_custody_settles_exact_failed_attempt_and_preserves_history(
    tmp_path: Path,
    prior_ack: bool,
) -> None:
    store, args, frontier = _custody_case(tmp_path)
    path = tmp_path / "control-plane.sqlite3"
    original = args["expected_job"]
    if prior_ack:
        store.acknowledge_dead_letter_job(
            job_id=original.job_id, acknowledged_by="previous operator"
        )
    original_dlq = store.list_dead_letter_jobs(acknowledged=prior_ack)[0]
    before = _rows(path, original.job_id)
    failure = store.get_job_terminal_source_event_record(original.job_id)
    assert original.progress["execution_owner_binding"]["attempt"] == original.attempt
    assert original.progress["execution_owner_binding"]["lease_owner"] == "prior-worker"
    assert original.progress["diagnostic_events"] == [{"event_id": "prior-attempt"}]
    head = store.settle_candidate_experiment_terminal_custody(**args)
    assert head.head_generation == 6 and head.receipt_phase == "terminal"
    assert head.receipt_manifest_profile_sha256 == args["terminal_ref"].manifest_profile_sha256
    assert head.evaluation_frontier_before_ref == frontier.frontier_ref
    assert (
        store.read_acquisition_evaluation_frontier(frontier.key).revision == frontier.revision + 1
    )
    after = _rows(path, original.job_id)
    assert set(before["control_job_events"]) <= set(after["control_job_events"])
    assert set(before["control_outbox_events"]) <= set(after["control_outbox_events"])
    assert before["control_diagnostic_events"] == after["control_diagnostic_events"]
    dlq = store.list_dead_letter_jobs(acknowledged=True)[0]
    assert dlq.attempt == original.attempt
    assert dlq.acknowledged_by == ("previous operator" if prior_ack else args["actor_subject"])
    if prior_ack:
        assert dlq == original_dlq
    audit = store._get_outbox_event_by_key(
        topic="control.job.candidate_experiment_terminal_custody_settled",
        event_key=args["step_up_sha256"],
    )
    assert audit is not None
    assert audit.payload["dead_letter"]["failed_at"] == original_dlq.failed_at.isoformat()
    assert audit.payload["dead_letter"]["acknowledged_by"] == original_dlq.acknowledged_by
    assert audit.payload["failed_event_id"] == failure.event_id
    assert audit.payload["frontier_before_ref"] == frontier.frontier_ref
    assert audit.payload["failed_progress"] == original.progress
    final = store.get_job(original.job_id)
    assert final is not None
    assert final.state == "completed" and final.attempt == original.attempt + 1
    assert final.lease_owner is None and final.lease_expires_at is None
    assert final.payload_ref == original.payload_ref and final.submitted_by == original.submitted_by
    assert final.progress["terminal_receipt_ref"] == str(args["terminal_ref"].artifact_id)
    owner = final.progress["execution_owner_binding"]
    assert owner["attempt"] == final.attempt and owner["job_id"] == final.job_id
    assert owner["lease_owner"].startswith("terminal-custody-")
    assert "diagnostic_events" not in final.progress
    assert failure.event_type == "job_failed"
    assert any(
        "candidate_experiment_terminal_custody_settled" in row
        for row in after["control_job_events"]
    )
    with pytest.raises(
        ControlJobLeaseLostError, match="candidate_terminal_custody_failed_attempt_changed"
    ):
        store.settle_candidate_experiment_terminal_custody(**args)
    assert _rows(path, original.job_id) == after


@pytest.mark.parametrize(
    ("case", "error", "reason"),
    [
        ("foreign", ControlJobExecutionAdmissionError, "candidate_terminal_custody_actor_refused"),
        ("expired", ValueError, "candidate_experiment_step_up_expired_before_admission"),
        ("stale-frontier", ValueError, "acquisition_evaluation_frontier_conflict"),
        ("stale-head", ValueError, "candidate_terminal_custody_head_changed"),
        ("unselected", ValueError, "candidate_terminal_custody_subject_invalid"),
        ("other-event", ValueError, "candidate_terminal_custody_event_mismatch"),
        ("wrong-event-payload", ValueError, "candidate_terminal_custody_event_mismatch"),
        ("drifted-progress", ValueError, "candidate_terminal_custody_failed_progress_changed"),
        (
            "unconsumed",
            ControlJobExecutionAdmissionError,
            "candidate_terminal_custody_step_up_unbound",
        ),
    ],
)
def test_candidate_custody_refusal_leaves_failed_cut(
    tmp_path: Path, case: str, error: type[Exception], reason: str
) -> None:
    store, args, frontier = _custody_case(tmp_path)
    original = args["expected_job"]
    path = tmp_path / "control-plane.sqlite3"
    if case == "drifted-progress":
        store.upsert_progress(
            job_id=original.job_id,
            progress={**original.progress, "diagnostic_events": [{"event_id": "another attempt"}]},
        )
        # The freshly read job and its original ownership still match at
        # admission. Only the retained failure's immutable snapshot differs.
        args["expected_job"] = store.get_job(original.job_id)
    before = _rows(path, original.job_id)
    if case == "foreign":
        args["actor_subject"] = "another-operator"
    elif case == "expired":
        args["authority_expires_at"] = int(time.time()) - 1
    elif case == "stale-frontier":
        args["frontier_cas"] = replace(args["frontier_cas"], expected_frontier_ref=_sha("stale"))
    elif case == "stale-head":
        args["expected_head"] = replace(args["expected_head"], durable_event_id="stale-head")
    elif case == "unselected":
        args["terminal_ref"] = args["terminal_ref"].model_copy(
            update={"manifest_profile_sha256": None}
        )
    elif case == "unconsumed":
        args["step_up_sha256"] = _sha("never consumed")
    elif case == "wrong-event-payload":
        args["terminal_ref"] = args["terminal_ref"].model_copy(
            update={"artifact_id": ArtifactID(_sha("another terminal"))}
        )
    elif case == "other-event":
        args["terminal_event_id"] = "event-unrelated"
    with pytest.raises(error, match=reason):
        store.settle_candidate_experiment_terminal_custody(**args)
    assert _rows(path, original.job_id) == before
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier


def test_candidate_custody_head_insert_abort_rolls_back_lease_frontier_and_audit(
    tmp_path: Path,
) -> None:
    store, args, frontier = _custody_case(tmp_path)
    path = tmp_path / "control-plane.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER abort_custody_head BEFORE INSERT ON runtime_acquisition_action_heads "
            "WHEN NEW.receipt_phase = 'terminal' "
            "BEGIN SELECT RAISE(ABORT, 'custody_sql_abort'); END"
        )
    original = args["expected_job"]
    before = _rows(path, original.job_id)
    with pytest.raises(sqlite3.IntegrityError, match="custody_sql_abort"):
        store.settle_candidate_experiment_terminal_custody(**args)
    assert _rows(path, original.job_id) == before
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier


def test_candidate_custody_expiry_at_commit_rolls_back_completed_private_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, args, frontier = _custody_case(tmp_path)
    path = tmp_path / "control-plane.sqlite3"
    job_id = args["expected_job"].job_id
    expiry = args["authority_expires_at"]
    before = _rows(path, job_id)
    states = []

    def clock() -> int:
        state = store.get_job(job_id).state
        states.append(state)
        # This separate SQL reader must not see the private in-flight effects.
        assert _rows(path, job_id) == before
        return expiry if state == "completed" else expiry - 1

    monkeypatch.setattr(control_plane_store, "time", SimpleNamespace(time=clock))
    with pytest.raises(ValueError, match="candidate_experiment_step_up_expired_before_admission"):
        store.settle_candidate_experiment_terminal_custody(**args)
    assert states == ["failed", "failed", "completed"]
    assert _rows(path, job_id) == before
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier


def test_ordinary_terminal_custody_appends_v2_and_preserves_failed_history(
    tmp_path: Path,
) -> None:
    store, args, frontier = _ordinary_custody_case(tmp_path)
    path = tmp_path / "control-plane.sqlite3"
    original = args["expected_job"]
    before = _rows(path, original.job_id)
    failure = store.get_job_terminal_source_event_record(original.job_id)
    original_dlq = store.list_dead_letter_jobs(acknowledged=False)[0]
    assert failure.event_type == "job_failed"
    assert failure.payload["error_message"] == original.error_message

    head = store.settle_candidate_model_revision_terminal_custody(**args)

    assert head.head_generation == args["expected_head"].head_generation + 1
    assert head.receipt_phase == "terminal" and head.recovery_state == "complete"
    assert head.receipt_ref == str(args["terminal_ref"].artifact_id)
    assert head.receipt_manifest_profile_sha256 == args["terminal_ref"].manifest_profile_sha256
    assert head.evaluation_frontier_before_ref == frontier.frontier_ref
    after = _rows(path, original.job_id)
    assert set(before["control_job_events"]) <= set(after["control_job_events"])
    assert set(before["control_outbox_events"]) <= set(after["control_outbox_events"])
    assert before["control_diagnostic_events"] == []
    assert len(after["control_diagnostic_events"]) == 1
    terminal_event = store.list_diagnostic_events(
        event_id=args["prepared_event"].publication_values()[0].event_id,
        run_id=original.run_id,
        job_id=original.job_id,
    )
    assert len(terminal_event) == 1
    event = terminal_event[0].event
    assert event.event_type == "polisyos.runtime.acquisition.route_loop.v2"
    assert event.state_before == "world_committed_reentry_pending"
    assert event.state_after == "terminal"
    assert event.event_subject == (
        f"run/{original.run_id}/job/{original.job_id}/acquisition/terminal"
    )
    assert event.event_id.startswith(
        f"evt_acquisition_{args['expected_head'].action_generation}_loop_terminal_"
    )
    legacy_event_id = (
        f"evt_acquisition_{args['expected_head'].action_generation}_experiment_terminal_"
        f"{sha256(f'{original.job_id}.candidate-experiment.terminal'.encode()).hexdigest()[:16]}"
    )
    assert event.event_id != legacy_event_id
    assert event.input_refs == _acquisition_route_receipt_inputs(args["terminal"])
    frontier_after = store.read_acquisition_evaluation_frontier(frontier.key)
    assert frontier_after.revision == frontier.revision + 1
    assert frontier_after.selected_evaluation_witness_ref == str(
        args["selected_n5_execution_ref"].artifact_id
    )
    replacement = args["frontier_cas"].replacement
    assert replacement is not None
    assert frontier_after.basis_ref == replacement.basis_ref
    assert frontier_after.decision_ref == replacement.decision_ref

    audit = store._get_outbox_event_by_key(
        topic="control.job.ordinary_acquisition_terminal_custody_settled",
        event_key=args["step_up_sha256"],
    )
    assert audit is not None
    assert audit.payload["schema_version"] == "ordinary_acquisition_terminal_custody.v1"
    assert audit.payload["failed_event_id"] == failure.event_id
    assert audit.payload["failed_progress"] == original.progress
    assert audit.payload["pending_receipt_ref"] == args["expected_head"].receipt_ref
    final = store.get_job(original.job_id)
    assert final is not None
    assert final.state == "completed" and final.attempt == original.attempt + 1
    assert final.progress["phase"] == "acquisition_model_revision"
    assert final.progress["terminal_outcome"] == "reentry_completed"
    assert final.progress["terminal_receipt_ref"] == str(args["terminal_ref"].artifact_id)
    failed_rows = [row for row in before["control_job_events"] if row[2] == "job_failed"]
    assert len(failed_rows) == 1 and failed_rows[0] in after["control_job_events"]
    final_dlq = store.list_dead_letter_jobs(acknowledged=True)[0]
    assert final_dlq.attempt == original_dlq.attempt
    assert final_dlq.error_message == original_dlq.error_message
    assert final_dlq.failed_at == original_dlq.failed_at
    assert final_dlq.acknowledged_by == args["actor_subject"]
    assert any(
        "ordinary_acquisition_terminal_custody_settled" in row
        for row in after["control_job_events"]
    )


def test_ordinary_terminal_custody_head_abort_rolls_back_event_and_frontier(
    tmp_path: Path,
) -> None:
    store, args, frontier = _ordinary_custody_case(tmp_path)
    path = tmp_path / "control-plane.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER abort_ordinary_terminal_head "
            "BEFORE INSERT ON runtime_acquisition_action_heads "
            "WHEN NEW.receipt_phase = 'terminal' "
            "BEGIN SELECT RAISE(ABORT, 'ordinary_terminal_sql_abort'); END"
        )
    original = args["expected_job"]
    before = _rows(path, original.job_id)
    with pytest.raises(sqlite3.IntegrityError, match="ordinary_terminal_sql_abort"):
        store.settle_candidate_model_revision_terminal_custody(**args)
    assert _rows(path, original.job_id) == before
    assert (
        store.list_diagnostic_events(
            event_id=args["prepared_event"].publication_values()[0].event_id
        )
        == []
    )
    assert store.get_job_terminal_source_event_record(original.job_id).event_type == "job_failed"
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier


def test_ordinary_terminal_custody_rejects_foreign_event_scope_without_effects(
    tmp_path: Path,
) -> None:
    store, args, frontier = _ordinary_custody_case(tmp_path)
    original = args["expected_job"]
    path = tmp_path / "control-plane.sqlite3"
    before = _rows(path, original.job_id)
    event, _ = args["prepared_event"].publication_values()
    foreign = event.model_copy(update={"tenant_id": "another-tenant"})
    args["prepared_event"] = RuntimeDiagnosticEventLog(
        store=store,
        artifact_store=object(),
    ).prepare(foreign, payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True))

    with pytest.raises(ValueError, match="ordinary_terminal_custody_event_binding_invalid"):
        store.settle_candidate_model_revision_terminal_custody(**args)

    assert _rows(path, original.job_id) == before
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier


@pytest.mark.parametrize("field", ["event_time", "dedupe_key"])
def test_ordinary_terminal_custody_rejects_changed_event_metadata_without_effects(
    tmp_path: Path,
    field: str,
) -> None:
    store, args, frontier = _ordinary_custody_case(tmp_path)
    original = args["expected_job"]
    path = tmp_path / "control-plane.sqlite3"
    before = _rows(path, original.job_id)
    event, _ = args["prepared_event"].publication_values()
    changed_value = (
        event.event_time + timedelta(seconds=1)
        if field == "event_time"
        else "foreign-terminal:cas_write"
    )
    changed_event = event.model_copy(update={field: changed_value})
    args["prepared_event"] = RuntimeDiagnosticEventLog(
        store=store,
        artifact_store=object(),
    ).prepare(
        changed_event,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )

    with pytest.raises(ValueError, match="ordinary_terminal_custody_event_binding_invalid"):
        store.settle_candidate_model_revision_terminal_custody(**args)

    assert _rows(path, original.job_id) == before
    assert store.read_acquisition_evaluation_frontier(frontier.key) == frontier
