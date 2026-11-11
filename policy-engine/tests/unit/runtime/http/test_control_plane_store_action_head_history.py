from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlPlaneStore,
    PendingAcquisitionActionAuthorizationCAS,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
    DiagnosticEventContractError,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_action_job

type _CheckpointPublication = tuple[
    ControlPlaneStore,
    AcquisitionActionHeadRecord,
    str,
    int,
    RuntimeDiagnosticEventLog,
    DiagnosticEvent,
]


def _make_store(tmp_path: Path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _action_scope() -> dict[str, Any]:
    return {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "source-job",
        "route_id": "sha256:" + "a" * 64,
        "action_generation": 1,
    }


def _receipt_ref(character: str) -> str:
    return "sha256:" + character * 64


def _create_pending_action_job(
    store: ControlPlaneStore,
    *,
    job_id: str = "action-job",
) -> Any:
    run_id = "run-a"
    payload_ref = _receipt_ref("e")
    submitted_by = "tester"
    capability_manifest_ref = _receipt_ref("f")
    creation_event_payload = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "acquisition",
        "pipeline_id": None,
        "payload_ref": payload_ref,
        "submitted_by": submitted_by,
        "requested_execution_profile": None,
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": capability_manifest_ref,
        "execution_scope": {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "actor_subject": submitted_by,
            "actor_authenticated": True,
            "actor_roles": ["operator"],
        },
    }
    return store.create_job(
        job_id=job_id,
        kind="acquisition",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="governed",
        policy_flags={},
        capability_manifest_ref=capability_manifest_ref,
        payload_ref=payload_ref,
        submitted_by=submitted_by,
        creation_event_payload=creation_event_payload,
    )


def _pending_authorization_cas(job: Any) -> PendingAcquisitionActionAuthorizationCAS:
    assert job.payload_ref is not None
    assert job.submitted_by is not None
    return PendingAcquisitionActionAuthorizationCAS(
        expected_job_attempt=job.attempt,
        expected_payload_ref=job.payload_ref,
        expected_submitted_by=job.submitted_by,
    )


def _append_head(
    store: ControlPlaneStore,
    scope: dict[str, Any],
    *,
    receipt_ref: str,
    expected_head_generation: int,
    predecessor_receipt_ref: str | None,
    receipt_phase: str,
    receipt_manifest_profile_sha256: str | None = None,
    job_id: str = "action-job",
    pending_authorization_cas: PendingAcquisitionActionAuthorizationCAS | None = None,
) -> AcquisitionActionHeadRecord:
    coarse_phase, recovery_state = {
        "requested": ("requested", "none"),
        "authorization_refreshed": ("requested", "none"),
        "executing": ("executing", "none"),
        "outcome_selected": ("executing", "none"),
        "candidate_input_reentry_pending": (
            "candidate_input_prepared",
            "reentry_recovery_required",
        ),
        "terminal": ("terminal", "complete"),
    }[receipt_phase]
    return store.advance_acquisition_action_head(
        **scope,
        expected_head_generation=expected_head_generation,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"event-{expected_head_generation + 1}",
        coarse_phase=coarse_phase,
        receipt_phase=receipt_phase,
        recovery_state=recovery_state,
        job_id=job_id,
        predecessor_receipt_ref=predecessor_receipt_ref,
        receipt_manifest_profile_sha256=receipt_manifest_profile_sha256,
        pending_authorization_cas=pending_authorization_cas,
    )


@pytest.mark.parametrize("attempt", [0, 4])
def test_authorization_refreshed_appends_for_exact_pending_job_and_preserves_request(
    tmp_path: Path,
    attempt: int,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    if attempt:
        with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
            connection.execute(
                "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
                (attempt, job.job_id),
            )
        job = store.get_job(job.job_id)
        assert job is not None

    initial_profile = _receipt_ref("a")
    refreshed_profile = _receipt_ref("b")
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("c"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=initial_profile,
        job_id=job.job_id,
    )
    refreshed = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("d"),
        expected_head_generation=1,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="authorization_refreshed",
        receipt_manifest_profile_sha256=refreshed_profile,
        job_id=job.job_id,
        pending_authorization_cas=_pending_authorization_cas(job),
    )

    persisted_job = store.get_job(job.job_id)
    assert persisted_job is not None
    assert persisted_job.same_execution_inputs(job)
    assert persisted_job.payload_ref == job.payload_ref
    assert persisted_job.state == "pending"
    assert persisted_job.attempt == attempt
    assert store.get_acquisition_action_head(**scope) == refreshed
    assert (
        store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=requested.receipt_ref)
        == requested
    )
    assert refreshed.receipt_phase == "authorization_refreshed"
    assert (refreshed.coarse_phase, refreshed.recovery_state) == ("requested", "none")
    assert requested.receipt_manifest_profile_sha256 == initial_profile
    assert refreshed.receipt_manifest_profile_sha256 == refreshed_profile


def test_authorization_refreshed_duplicate_stale_predecessor_does_not_append(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_receipt_ref("f"),
        job_id=job.job_id,
    )
    refreshed = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=1,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="authorization_refreshed",
        receipt_manifest_profile_sha256=_receipt_ref("e"),
        job_id=job.job_id,
        pending_authorization_cas=_pending_authorization_cas(job),
    )

    with pytest.raises(ValueError, match="acquisition_action_predecessor_conflict"):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("d"),
            expected_head_generation=1,
            predecessor_receipt_ref=requested.receipt_ref,
            receipt_phase="authorization_refreshed",
            receipt_manifest_profile_sha256=_receipt_ref("e"),
            job_id=job.job_id,
            pending_authorization_cas=_pending_authorization_cas(job),
        )

    assert store.get_acquisition_action_head(**scope) == refreshed
    assert (
        store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=_receipt_ref("d")) is None
    )


@pytest.mark.parametrize(
    ("replacement", "update_sql"),
    [
        pytest.param(
            1,
            "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
            id="attempt",
        ),
        pytest.param(
            _receipt_ref("d"),
            "UPDATE control_jobs SET payload_ref = ? WHERE job_id = ?",
            id="payload_ref",
        ),
        pytest.param(
            "changed-submitter",
            "UPDATE control_jobs SET submitted_by = ? WHERE job_id = ?",
            id="submitted_by",
        ),
        pytest.param(
            "failed",
            "UPDATE control_jobs SET state = ? WHERE job_id = ?",
            id="state",
        ),
    ],
)
def test_authorization_refreshed_rejects_changed_pending_job_without_new_head(
    tmp_path: Path,
    replacement: int | str,
    update_sql: str,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_receipt_ref("f"),
        job_id=job.job_id,
    )
    with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
        connection.execute(update_sql, (replacement, job.job_id))

    with pytest.raises((ControlJobLeaseLostError, ControlJobExecutionAdmissionError)):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("b"),
            expected_head_generation=1,
            predecessor_receipt_ref=requested.receipt_ref,
            receipt_phase="authorization_refreshed",
            receipt_manifest_profile_sha256=_receipt_ref("e"),
            job_id=job.job_id,
            pending_authorization_cas=_pending_authorization_cas(job),
        )

    assert store.get_acquisition_action_head(**scope) == requested
    assert (
        store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=_receipt_ref("b")) is None
    )


def test_authorization_refreshed_refuses_worker_claim_that_wins_first(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_receipt_ref("f"),
        job_id=job.job_id,
    )
    claimed = store.lease_next_job(worker_id="worker-action-job")
    assert claimed is not None
    assert claimed.job_id == job.job_id
    assert claimed.state == "running"

    with pytest.raises(ControlJobLeaseLostError):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("b"),
            expected_head_generation=1,
            predecessor_receipt_ref=requested.receipt_ref,
            receipt_phase="authorization_refreshed",
            receipt_manifest_profile_sha256=_receipt_ref("e"),
            job_id=job.job_id,
            pending_authorization_cas=_pending_authorization_cas(job),
        )

    assert store.get_acquisition_action_head(**scope) == requested
    persisted_job = store.get_job(job.job_id)
    assert persisted_job is not None
    assert persisted_job.state == "running"
    assert persisted_job.payload_ref == job.payload_ref


def test_authorization_refreshed_requires_phase_scoped_valid_cas(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()

    with pytest.raises(ValueError, match="pending_acquisition_action_authorization_cas_required"):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("a"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="authorization_refreshed",
        )
    with pytest.raises(ValueError, match="pending_acquisition_action_authorization_phase_mismatch"):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("b"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="requested",
            pending_authorization_cas=PendingAcquisitionActionAuthorizationCAS(
                expected_job_attempt=0,
                expected_payload_ref=_receipt_ref("e"),
                expected_submitted_by="tester",
            ),
        )
    with pytest.raises(TypeError, match="pending_acquisition_action_authorization_cas_untyped"):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("c"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="authorization_refreshed",
            pending_authorization_cas="untyped",
        )
    with pytest.raises(
        ValueError, match="pending_acquisition_action_authorization_attempt_invalid"
    ):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("d"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="authorization_refreshed",
            pending_authorization_cas=PendingAcquisitionActionAuthorizationCAS(
                expected_job_attempt=True,
                expected_payload_ref=_receipt_ref("e"),
                expected_submitted_by="tester",
            ),
        )
    with pytest.raises(
        ValueError, match="pending_acquisition_action_authorization_identity_invalid"
    ):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("d"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="authorization_refreshed",
            pending_authorization_cas=PendingAcquisitionActionAuthorizationCAS(
                expected_job_attempt=0,
                expected_payload_ref=_receipt_ref("e"),
                expected_submitted_by=" ",
            ),
        )

    assert store.get_acquisition_action_head(**scope) is None


def test_authorization_refreshed_keeps_requested_coarse_phase_without_recovery(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_receipt_ref("f"),
        job_id=job.job_id,
    )

    with pytest.raises(ValueError, match="acquisition_action_authorization_phase_invalid"):
        store.advance_acquisition_action_head(
            **scope,
            expected_head_generation=1,
            receipt_ref=_receipt_ref("b"),
            receipt_sha256=_receipt_ref("b"),
            durable_event_id="event-2",
            coarse_phase="executing",
            receipt_phase="authorization_refreshed",
            recovery_state="none",
            job_id=job.job_id,
            predecessor_receipt_ref=requested.receipt_ref,
            pending_authorization_cas=_pending_authorization_cas(job),
            receipt_manifest_profile_sha256=_receipt_ref("e"),
        )

    assert store.get_acquisition_action_head(**scope) == requested


def test_action_head_history_resolves_old_receipt_after_terminal_append(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    executing = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=1,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="executing",
    )
    selected = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("c"),
        expected_head_generation=2,
        predecessor_receipt_ref=executing.receipt_ref,
        receipt_phase="outcome_selected",
    )
    terminal = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("d"),
        expected_head_generation=3,
        predecessor_receipt_ref=selected.receipt_ref,
        receipt_phase="terminal",
    )

    assert store.get_acquisition_action_head(**scope) == terminal
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=selected.receipt_ref,
        )
        == selected
    )
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=terminal.receipt_ref,
        )
        == terminal
    )
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=_receipt_ref("e"),
        )
        is None
    )


@pytest.mark.parametrize(
    ("field", "foreign_value"),
    [
        ("tenant_id", "foreign-tenant"),
        ("cell_id", "foreign-cell"),
        ("run_id", "foreign-run"),
        ("source_job_id", "foreign-source-job"),
        ("route_id", "sha256:" + "d" * 64),
        ("action_generation", 2),
    ],
)
def test_action_head_history_rejects_every_foreign_scope_axis(
    tmp_path: Path,
    field: str,
    foreign_value: str | int,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    head = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )

    foreign_scope = {**scope, field: foreign_value}
    assert (
        store.get_acquisition_action_head_by_receipt(
            **foreign_scope,
            receipt_ref=head.receipt_ref,
        )
        is None
    )


def test_action_head_history_returns_no_result_for_ambiguous_receipt(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    repeated_receipt = _receipt_ref("b")
    first = _append_head(
        store,
        scope,
        receipt_ref=repeated_receipt,
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    second = _append_head(
        store,
        scope,
        receipt_ref=repeated_receipt,
        expected_head_generation=1,
        predecessor_receipt_ref=first.receipt_ref,
        receipt_phase="executing",
    )

    assert store.get_acquisition_action_head(**scope) == second
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=repeated_receipt,
        )
        is None
    )


def test_action_head_history_returns_no_result_for_corrupt_receipt_hash_relation(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    head = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
        connection.execute(
            """
            UPDATE runtime_acquisition_action_heads
            SET receipt_sha256 = ?
            WHERE tenant_id = ? AND cell_id = ? AND run_id = ?
              AND source_job_id = ? AND route_id = ? AND action_generation = ?
              AND head_generation = ?
            """,
            (
                _receipt_ref("c"),
                scope["tenant_id"],
                scope["cell_id"],
                scope["run_id"],
                scope["source_job_id"],
                scope["route_id"],
                scope["action_generation"],
                head.head_generation,
            ),
        )

    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=head.receipt_ref,
        )
        is None
    )


@pytest.fixture
def pending_checkpoint_publication(tmp_path: Path) -> _CheckpointPublication:
    store = _make_store(tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="action-job")
    scope = _action_scope()
    head = None
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        for index, phase in enumerate(
            ("requested", "executing", "outcome_selected", "candidate_input_reentry_pending")
        ):
            head = _append_head(
                store,
                scope,
                receipt_ref=_receipt_ref(str(index)),
                expected_head_generation=index,
                predecessor_receipt_ref=None if head is None else head.receipt_ref,
                receipt_phase=phase,
                receipt_manifest_profile_sha256=_receipt_ref("f"),
            )
    assert head is not None
    cas = FileSystemCAS(tmp_path / "checkpoint-cas")
    checkpoint = cas.put_bytes(
        b"candidate checkpoint", PutOptions(kind="test.checkpoint", media_type="text/plain")
    )
    payload_ref = str(checkpoint.artifact_id)
    event = DiagnosticEvent(
        event_id="evt_candidate_source_reentry_n5_checkpoint_test",
        event_source="polisyos.runtime",
        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
        event_time=datetime.now(UTC).replace(microsecond=0),
        event_subject="run/run-a/job/action-job/phase/candidate_source_reentry_n5_checkpoint",
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id="trace-run-a",
        span_id="span-n5-checkpoint",
        parent_span_id=None,
        run_id=head.run_id,
        job_id=head.job_id,
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        producer_component="polisyos.runtime.acquisition_world_growth",
        producer_version="1.0",
        execution_profile="governed",
        phase="candidate_source_reentry_n5_checkpoint",
        state_before=None,
        state_after="n5_checkpoint_selected",
        payload_ref=payload_ref,
        artifact_refs=(payload_ref,),
        input_refs=(head.receipt_ref,),
        blocking_status=None,
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key=None,
    )
    return (
        store,
        head,
        worker,
        attempt,
        RuntimeDiagnosticEventLog(store=store, artifact_store=cas),
        event,
    )


def test_candidate_n5_checkpoint_reuses_exact_event_and_refuses_collision(
    pending_checkpoint_publication: _CheckpointPublication,
) -> None:
    store, head, worker, attempt, log, event = pending_checkpoint_publication
    prepared = log.prepare(event)
    other = log.artifact_store.put_bytes(
        b"foreign checkpoint", PutOptions(kind="test.checkpoint", media_type="text/plain")
    )
    other_ref = str(other.artifact_id)
    conflicting = log.prepare(
        event.model_copy(update={"payload_ref": other_ref, "artifact_refs": (other_ref,)})
    )
    different_event = log.prepare(event.model_copy(update={"state_after": "different_state"}))
    with store.job_execution_fence(job_id=head.job_id, worker_id=worker, attempt=attempt):
        record = store.append_candidate_experiment_n5_checkpoint(
            pending_head=head, prepared_event=prepared
        )
        assert (
            store.append_candidate_experiment_n5_checkpoint(
                pending_head=head, prepared_event=prepared
            )
            == record
        )
        for invalid in (conflicting, different_event):
            with pytest.raises(DiagnosticEventContractError) as refused:
                store.append_candidate_experiment_n5_checkpoint(
                    pending_head=head, prepared_event=invalid
                )
            assert refused.value.code == "authority_event_collision"
    assert store.list_diagnostic_events(event_id=event.event_id) == [record]
    assert record.payload_ref == event.artifact_refs[0]
    assert store.get_acquisition_action_head(**_action_scope()) == head


def test_candidate_n5_checkpoint_requires_exact_pending_profile_and_artifact(
    pending_checkpoint_publication: _CheckpointPublication,
) -> None:
    store, head, worker, attempt, log, event = pending_checkpoint_publication
    prepared = log.prepare(event)
    foreign_head = replace(head, receipt_manifest_profile_sha256=_receipt_ref("0"))
    mismatched = log.prepare(event.model_copy(update={"artifact_refs": (_receipt_ref("a"),)}))
    with store.job_execution_fence(job_id=head.job_id, worker_id=worker, attempt=attempt):
        with pytest.raises(
            ValueError, match="candidate_experiment_n5_checkpoint_pending_head_changed"
        ):
            store.append_candidate_experiment_n5_checkpoint(
                pending_head=foreign_head, prepared_event=prepared
            )
        with pytest.raises(
            ValueError, match="candidate_experiment_n5_checkpoint_event_binding_invalid"
        ):
            store.append_candidate_experiment_n5_checkpoint(
                pending_head=head, prepared_event=mismatched
            )
    assert not store.list_diagnostic_events(event_id=event.event_id)


def test_candidate_n5_checkpoint_refuses_an_expired_worker_lease(
    tmp_path: Path,
    pending_checkpoint_publication: _CheckpointPublication,
) -> None:
    store, head, worker, attempt, log, event = pending_checkpoint_publication
    prepared = log.prepare(event)
    fence = store.job_execution_fence(job_id=head.job_id, worker_id=worker, attempt=attempt)
    with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", head.job_id),
        )
    with fence, pytest.raises(ControlJobLeaseLostError):
        store.append_candidate_experiment_n5_checkpoint(pending_head=head, prepared_event=prepared)
    assert not store.list_diagnostic_events(event_id=event.event_id)


@pytest.mark.parametrize("axis", ["tenant_id", "cell_id"])
def test_authorization_refreshed_reconciles_creation_scope_even_with_a_foreign_head(
    tmp_path: Path, axis: str
) -> None:
    """A pre-existing foreign SQL head cannot change the immutable job's scope."""
    store = _make_store(tmp_path)
    scope = _action_scope()
    job = _create_pending_action_job(store)
    scope[axis] = "foreign-scope"
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
        receipt_manifest_profile_sha256=_receipt_ref("f"),
        job_id=job.job_id,
    )
    with pytest.raises(ControlJobLeaseLostError, match="authorization scope changed"):
        _append_head(
            store,
            scope,
            receipt_ref=_receipt_ref("b"),
            expected_head_generation=1,
            predecessor_receipt_ref=requested.receipt_ref,
            receipt_phase="authorization_refreshed",
            receipt_manifest_profile_sha256=_receipt_ref("e"),
            job_id=job.job_id,
            pending_authorization_cas=_pending_authorization_cas(job),
        )
    assert store.get_acquisition_action_head(**scope) == requested
    assert store.get_job(job.job_id) == job
