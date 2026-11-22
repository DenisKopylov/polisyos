from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.http.services import control_plane_store
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.native_settled_draft import NativeSettledDraftRecovery
from tests.unit.runtime.http.test_control_plane_store_action_head_history import (
    _action_scope,
    _append_head,
    _create_pending_action_job,
    _make_store,
)
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _lease_job


@dataclass(frozen=True)
class _FailedAction:
    store: ControlPlaneStore
    sqlite_path: Path
    failed_job: ControlJobRecord
    failed_worker_id: str
    failed_attempt: int
    head: AcquisitionActionHeadRecord
    execution_scope: ControlJobExecutionScope
    creation_payload: dict[str, Any]
    failure_progress: dict[str, Any]


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _failed_action(
    tmp_path: Path,
    *,
    job_id: str = "native-action",
    newer_head: bool = False,
    world_pending: bool = False,
    failed_error: str = "native materialization failed",
    competitor: str | None = None,
) -> _FailedAction:
    store = _make_store(tmp_path)
    sqlite_path = tmp_path / "control-plane.sqlite3"
    if competitor in {"before", "completed_before"}:
        peer = _create_pending_action_job(store, job_id="native-competing-action")
        peer_worker, peer_attempt = _lease_job(store, peer, "competing-worker")
        if competitor == "completed_before":
            with store.job_execution_fence(
                job_id=peer.job_id, worker_id=peer_worker, attempt=peer_attempt
            ):
                store.complete_job(job_id=peer.job_id, run_id=peer.run_id)
    job = _create_pending_action_job(store, job_id=job_id)
    worker_id, attempt = _lease_job(store, job, f"worker-{job_id}")
    if competitor == "during":
        peer = _create_pending_action_job(store, job_id="native-competing-action")
        _lease_job(store, peer, "competing-worker")
    scope = _action_scope()
    failure_progress = {
        "state": "failed",
        "phase": "native_materialization",
        "failure": {
            "code": "test_native_materialization_failed",
            "message": "Native worker failed after selecting its outcome.",
            "retryable": False,
        },
        "native_resource_ref": _digest(f"{job_id}:resource"),
    }
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt):
        execution_scope = store.current_execution_job_admission().scope
        first_head = _append_head(
            store,
            scope,
            receipt_ref=_digest(f"{job_id}:selected-head"),
            expected_head_generation=0,
            predecessor_receipt_ref=None,
            receipt_phase="outcome_selected",
            receipt_manifest_profile_sha256=_digest(f"{job_id}:selected-profile"),
            job_id=job.job_id,
        )
        if world_pending:
            first_head = store.advance_acquisition_action_head(
                **scope,
                expected_head_generation=first_head.head_generation,
                receipt_ref=_digest(f"{job_id}:world-pending"),
                receipt_sha256=_digest(f"{job_id}:world-pending"),
                receipt_manifest_profile_sha256=_digest(f"{job_id}:world-pending-profile"),
                durable_event_id="world-pending-event",
                coarse_phase="world_committed",
                receipt_phase="world_committed_reentry_pending",
                recovery_state="reentry_recovery_required",
                job_id=job_id,
                predecessor_receipt_ref=first_head.receipt_ref,
            )
        if newer_head:
            _append_head(
                store,
                scope,
                receipt_ref=_digest(f"{job_id}:newer-selected-head"),
                expected_head_generation=first_head.head_generation,
                predecessor_receipt_ref=first_head.receipt_ref,
                receipt_phase="outcome_selected",
                receipt_manifest_profile_sha256=_digest(f"{job_id}:newer-selected-profile"),
                job_id=job.job_id,
            )

    creation_payload = store.get_job_created_event_payload(job.job_id)
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt):
        store.fail_job(
            job_id=job.job_id,
            error_message=failed_error,
            progress=failure_progress,
        )
    failed_job = store.get_job(job.job_id)
    assert failed_job is not None
    assert failed_job.state == "failed"
    return _FailedAction(
        store=store,
        sqlite_path=sqlite_path,
        failed_job=failed_job,
        failed_worker_id=worker_id,
        failed_attempt=attempt,
        head=first_head,
        execution_scope=execution_scope,
        creation_payload=creation_payload,
        failure_progress=failure_progress,
    )


def _request_args(
    action: _FailedAction,
    **overrides: Any,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "expected_job": action.failed_job,
        "failed_attempt": action.failed_attempt,
        "head": action.head,
        "execution_scope": action.execution_scope,
        "request_sha256": _digest("native-recovery-request"),
        "permission_sha256": _digest("native-recovery-permission"),
        "resource_digest": _digest("native-recovery-resource"),
    }
    args.update(overrides)
    return args


def _request(action: _FailedAction, **overrides: Any) -> ControlJobRecord:
    return action.store.request_native_acquisition_custody_recovery(
        **_request_args(action, **overrides)
    )


def _draft_selection() -> NativeSettledDraftRecovery:
    return NativeSettledDraftRecovery(
        producer_event_id="llm-provider:" + "a" * 32,
        ledger_revision=18,
        response_text='{"draft_id":"exact-private-candidate"}',
    )


def test_draft_recovery_outbox_projects_hash_and_reclaimed_lease_cannot_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    action = _failed_action(tmp_path, world_pending=True, failed_error="reentry_recovery_required")
    selected = _draft_selection()
    now = datetime.now(UTC)
    _request(
        action,
        settled_draft=selected,
        approval_expires_at=int((now + timedelta(minutes=2)).timestamp()),
    )
    first = action.store.lease_next_job(worker_id="draft-1", lease_seconds=5)
    assert first is not None
    with action.store.job_execution_fence(
        job_id=first.job_id, worker_id="draft-1", attempt=first.attempt
    ):
        record = action.store.current_native_acquisition_custody_recovery()
    assert record is not None
    assert record.settled_draft == selected
    assert record.recovery_attempt == first.attempt
    assert record.failed_lease_started_at is not None
    assert record.event.payload["settled_draft"]["response_text"] == selected.response_text
    public = action.store.get_outbox_topic_event(
        topic="control.job.custody_recovery_requested",
        event_key=f"{first.job_id}:custody_recovery:{action.failed_attempt}",
        job_id=first.job_id,
    )
    assert public is not None
    assert (
        public.payload["response_sha256"]
        == hashlib.sha256(selected.response_text.encode()).hexdigest()
    )
    assert "response_text" not in json.dumps(public.payload)
    assert selected.response_text not in json.dumps(public.payload)

    monkeypatch.setattr(control_plane_store, "_utc_now", lambda: now + timedelta(seconds=10))
    reclaimed = action.store.lease_next_job(worker_id="draft-2", lease_seconds=60)
    assert reclaimed is not None
    with (
        action.store.job_execution_fence(
            job_id=reclaimed.job_id, worker_id="draft-2", attempt=reclaimed.attempt
        ),
        pytest.raises(ValueError, match="native_settled_draft_recovery_lease_mismatch"),
    ):
        action.store.current_native_acquisition_custody_recovery()


@pytest.mark.parametrize("competitor", ["before", "during"])
def test_draft_recovery_refuses_a_competing_source_run_lease(
    tmp_path: Path, competitor: str
) -> None:
    action = _failed_action(
        tmp_path,
        world_pending=True,
        failed_error="reentry_recovery_required",
        competitor=competitor,
    )
    with pytest.raises(ValueError, match="native_settled_draft_concurrent_source_job"):
        _request(
            action,
            settled_draft=_draft_selection(),
            approval_expires_at=int((datetime.now(UTC) + timedelta(minutes=2)).timestamp()),
        )
    assert len(_recovery_event_rows(action.sqlite_path, action.failed_job.job_id)) == 0
    assert action.store.get_job(action.failed_job.job_id) == action.failed_job


def test_draft_recovery_refuses_a_sibling_terminal_for_the_wrong_attempt(tmp_path: Path) -> None:
    action = _failed_action(
        tmp_path,
        world_pending=True,
        failed_error="reentry_recovery_required",
        competitor="completed_before",
    )
    with sqlite3.connect(action.sqlite_path) as connection:
        event_id, raw = connection.execute(
            "SELECT event_id, payload_json FROM control_job_events WHERE job_id = ? "
            "AND event_type = 'job_completed'",
            ("native-competing-action",),
        ).fetchone()
        payload = json.loads(raw)
        payload["attempt"] += 1
        connection.execute(
            "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
            (json.dumps(payload, sort_keys=True), event_id),
        )
    with pytest.raises(ValueError, match="native_settled_draft_sibling_lifecycle_changed"):
        _request(
            action,
            settled_draft=_draft_selection(),
            approval_expires_at=int((datetime.now(UTC) + timedelta(minutes=2)).timestamp()),
        )


def test_draft_recovery_outbox_rejects_rewritten_private_expiry(tmp_path: Path) -> None:
    action = _failed_action(tmp_path, world_pending=True, failed_error="reentry_recovery_required")
    _request(
        action,
        settled_draft=_draft_selection(),
        approval_expires_at=int((datetime.now(UTC) + timedelta(minutes=2)).timestamp()),
    )
    job_id = action.failed_job.job_id
    (event,) = _recovery_event_rows(action.sqlite_path, job_id)
    payload = json.loads(event["payload_json"])
    payload["approval_expires_at"] += 1_000
    with sqlite3.connect(action.sqlite_path) as connection:
        connection.execute(
            "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
            (json.dumps(payload, sort_keys=True), event["event_id"]),
        )
    leased = action.store.lease_next_job(worker_id="draft-worker", lease_seconds=60)
    assert leased is not None
    with (
        action.store.job_execution_fence(
            job_id=job_id, worker_id="draft-worker", attempt=leased.attempt
        ),
        pytest.raises(ValueError, match="native_custody_recovery_event_outbox_mismatch"),
    ):
        action.store.current_native_acquisition_custody_recovery()


def _rows(path: Path, query: str, parameters: tuple[Any, ...]) -> list[sqlite3.Row]:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query, parameters))


def _table_snapshot(path: Path, table: str, job_id: str) -> dict[str, Any] | None:
    queries = {
        "control_jobs": "SELECT * FROM control_jobs WHERE job_id = ?",
        "control_job_progress": "SELECT * FROM control_job_progress WHERE job_id = ?",
        "control_dead_letter_jobs": "SELECT * FROM control_dead_letter_jobs WHERE job_id = ?",
    }
    row = _rows(path, queries[table], (job_id,))
    return dict(row[0]) if row else None


def _event_payload_bytes(path: Path, event_id: int) -> bytes:
    rows = _rows(
        path,
        "SELECT payload_json FROM control_job_events WHERE event_id = ?",
        (event_id,),
    )
    assert len(rows) == 1
    return str(rows[0]["payload_json"]).encode("utf-8")


def _recovery_event_rows(path: Path, job_id: str) -> list[sqlite3.Row]:
    return _rows(
        path,
        "SELECT event_id, payload_json FROM control_job_events "
        "WHERE job_id = ? AND event_type = 'native_acquisition_custody_recovery_requested' "
        "ORDER BY event_id",
        (job_id,),
    )


def _recovery_outbox_rows(path: Path, job_id: str) -> list[sqlite3.Row]:
    return _rows(
        path,
        "SELECT event_id, event_key, payload_json FROM control_outbox_events "
        "WHERE job_id = ? AND topic = 'control.job.custody_recovery_requested' "
        "ORDER BY created_at, event_id",
        (job_id,),
    )


def _outbox_payload_bytes(path: Path, event_id: str) -> bytes:
    rows = _rows(
        path,
        "SELECT payload_json FROM control_outbox_events WHERE event_id = ?",
        (event_id,),
    )
    assert len(rows) == 1
    return str(rows[0]["payload_json"]).encode("utf-8")


def _failed_outbox(action: _FailedAction, event_key: str) -> Any:
    return action.store.get_outbox_topic_event(
        topic="control.job.failed",
        event_key=event_key,
        job_id=action.failed_job.job_id,
    )


@pytest.mark.parametrize("world_pending", [False, True], ids=["selected", "world-pending"])
def test_failed_worker_recovery_preserves_failure_and_replays_under_new_lease(
    tmp_path: Path,
    world_pending: bool,
) -> None:
    action = _failed_action(tmp_path, world_pending=world_pending)
    store = action.store
    job_id = action.failed_job.job_id
    failure = store.get_job_terminal_source_event_record(job_id)
    assert failure.event_type == "job_failed"
    assert failure.payload["attempt"] == action.failed_attempt
    failure_event_bytes = _event_payload_bytes(action.sqlite_path, failure.event_id)
    failure_outbox = _failed_outbox(action, f"{job_id}:job_failed")
    assert failure_outbox is not None
    failure_outbox_bytes = _outbox_payload_bytes(action.sqlite_path, failure_outbox.event_id)
    failed_job_snapshot = _table_snapshot(action.sqlite_path, "control_jobs", job_id)
    failed_progress_snapshot = _table_snapshot(action.sqlite_path, "control_job_progress", job_id)
    dead_letter_snapshot = _table_snapshot(action.sqlite_path, "control_dead_letter_jobs", job_id)
    assert failed_job_snapshot is not None
    assert failed_progress_snapshot is not None
    assert dead_letter_snapshot is not None
    assert dead_letter_snapshot["acknowledged_at"] is None

    queued = _request(action)

    assert queued.state == "pending"
    assert queued.job_id == action.failed_job.job_id
    assert queued.attempt == action.failed_attempt
    assert queued.payload_ref == action.failed_job.payload_ref
    assert store.get_job_created_event_payload(job_id) == action.creation_payload
    assert queued.progress["phase"] == "acquisition_custody_recovery"
    assert queued.progress["authority_purpose"] == "historical_custody_only"
    assert store.list_job_state_transitions(job_id)[-2:] == ["failed", "pending"]
    assert len(_recovery_event_rows(action.sqlite_path, job_id)) == 1
    assert len(_recovery_outbox_rows(action.sqlite_path, job_id)) == 1

    recovery_event_row = _recovery_event_rows(action.sqlite_path, job_id)[0]
    recovery_payload = json.loads(recovery_event_row["payload_json"])
    assert recovery_payload["authority_purpose"] == "historical_custody_only"
    assert recovery_payload["failed_job"] == failed_job_snapshot
    assert recovery_payload["failed_progress"] == failed_progress_snapshot
    assert recovery_payload["dead_letter"] == dead_letter_snapshot
    assert recovery_payload["failed_event"] == {
        "event_id": failure.event_id,
        "payload_sha256": failure.payload_sha256,
        "payload": failure.payload,
        "created_at": failure.created_at.isoformat(),
    }
    acknowledged = store.list_dead_letter_jobs(acknowledged=True)
    assert len(acknowledged) == 1
    assert acknowledged[0].job_id == job_id
    assert acknowledged[0].acknowledged_by == action.execution_scope.actor_subject

    # The mutable aggregate and DLQ acknowledgement do not rewrite the original
    # failure event or its producer outbox bytes.
    assert _event_payload_bytes(action.sqlite_path, failure.event_id) == failure_event_bytes
    persisted_failure_outbox = _failed_outbox(action, f"{job_id}:job_failed")
    assert persisted_failure_outbox is not None
    assert persisted_failure_outbox.event_id == failure_outbox.event_id
    assert (
        _outbox_payload_bytes(action.sqlite_path, persisted_failure_outbox.event_id)
        == failure_outbox_bytes
    )

    leased = store.lease_next_job(worker_id="native-recovery-worker", lease_seconds=60)
    assert leased is not None
    assert leased.job_id == job_id
    assert leased.state == "running"
    assert leased.attempt == action.failed_attempt + 1
    with store.job_execution_fence(
        job_id=job_id,
        worker_id="native-recovery-worker",
        attempt=leased.attempt,
    ):
        current = store.current_native_acquisition_custody_recovery()
    assert current is not None
    assert current.failed_attempt == action.failed_attempt
    assert current.recovery_attempt == action.failed_attempt + 1
    assert current.head == action.head
    assert current.event.event_id == recovery_event_row["event_id"]
    assert current.event.payload == recovery_payload


def test_duplicate_recovery_is_idempotent_and_allows_rotated_permission_proof(
    tmp_path: Path,
) -> None:
    action = _failed_action(tmp_path)
    first = _request(action)

    duplicate = _request(
        action,
        permission_sha256=_digest("fresh-current-permission-proof"),
    )

    assert first.state == "pending"
    assert duplicate.state == "pending"
    assert duplicate.job_id == first.job_id
    assert duplicate.attempt == first.attempt
    assert len(_recovery_event_rows(action.sqlite_path, first.job_id)) == 1
    assert len(_recovery_outbox_rows(action.sqlite_path, first.job_id)) == 1

    for changed in (
        {"request_sha256": _digest("changed-request-body")},
        {"resource_digest": _digest("changed-resource")},
    ):
        with pytest.raises(ValueError, match="native_custody_recovery_request_stale"):
            _request(action, **changed)
    assert len(_recovery_event_rows(action.sqlite_path, first.job_id)) == 1
    assert len(_recovery_outbox_rows(action.sqlite_path, first.job_id)) == 1


@pytest.mark.parametrize(
    "invalid_case",
    ["actor", "tenant", "payload", "full_profile", "head", "newer_generation"],
)
def test_recovery_refuses_wrong_or_stale_identity_without_mutating_failure(
    tmp_path: Path,
    invalid_case: str,
) -> None:
    action = _failed_action(tmp_path, newer_head=invalid_case == "newer_generation")
    overrides: dict[str, Any] = {}
    if invalid_case == "actor":
        overrides["execution_scope"] = replace(
            action.execution_scope,
            actor_subject="different-actor",
        )
    elif invalid_case == "tenant":
        overrides["execution_scope"] = replace(
            action.execution_scope,
            tenant_id="different-tenant",
        )
    elif invalid_case == "payload":
        overrides["expected_job"] = replace(
            action.failed_job,
            payload_ref=_digest("different-payload"),
        )
    elif invalid_case == "full_profile":
        overrides["head"] = replace(
            action.head,
            receipt_manifest_profile_sha256=_digest("different-full-profile"),
        )
    elif invalid_case == "head":
        overrides["head"] = replace(
            action.head,
            receipt_ref=_digest("different-head-receipt"),
        )

    with pytest.raises(ValueError, match="native_custody_recovery"):
        _request(action, **overrides)

    assert action.store.get_job(action.failed_job.job_id) == action.failed_job
    assert action.store.list_dead_letter_jobs(acknowledged=False)[0].acknowledged_at is None
    assert _recovery_event_rows(action.sqlite_path, action.failed_job.job_id) == []
    assert _recovery_outbox_rows(action.sqlite_path, action.failed_job.job_id) == []


def test_stale_failed_attempt_descriptor_refuses_after_next_attempt_fails(
    tmp_path: Path,
) -> None:
    action = _failed_action(tmp_path)
    _request(action)
    second_worker = "native-recovery-worker-2"
    second_lease = action.store.lease_next_job(worker_id=second_worker, lease_seconds=60)
    assert second_lease is not None
    assert second_lease.attempt == action.failed_attempt + 1
    with action.store.job_execution_fence(
        job_id=second_lease.job_id,
        worker_id=second_worker,
        attempt=second_lease.attempt,
    ):
        action.store.fail_job(
            job_id=second_lease.job_id,
            error_message="second native materialization failure",
            progress={
                "state": "failed",
                "phase": "native_materialization",
                "failure": {
                    "code": "test_native_materialization_failed_again",
                    "message": "The recovery attempt failed.",
                    "retryable": False,
                },
            },
        )
    second_failure = action.store.get_job(second_lease.job_id)
    assert second_failure is not None
    assert second_failure.state == "failed"
    assert second_failure.attempt == action.failed_attempt + 1

    with pytest.raises(ValueError, match="native_custody_recovery_request_stale"):
        _request(action)

    assert len(_recovery_event_rows(action.sqlite_path, second_lease.job_id)) == 1
    assert len(_recovery_outbox_rows(action.sqlite_path, second_lease.job_id)) == 1
    dead_letter = action.store.list_dead_letter_jobs(acknowledged=False)[0]
    assert dead_letter.attempt == second_failure.attempt


def test_second_failure_has_attempt_scoped_outbox_and_completion_key_stays_stable(
    tmp_path: Path,
) -> None:
    action = _failed_action(tmp_path)
    job_id = action.failed_job.job_id
    first_failure_outbox = _failed_outbox(action, f"{job_id}:job_failed")
    assert first_failure_outbox is not None
    _request(action)

    second_worker = "native-recovery-worker-2"
    second_lease = action.store.lease_next_job(worker_id=second_worker, lease_seconds=60)
    assert second_lease is not None
    assert second_lease.attempt == action.failed_attempt + 1
    with action.store.job_execution_fence(
        job_id=job_id,
        worker_id=second_worker,
        attempt=second_lease.attempt,
    ):
        action.store.fail_job(
            job_id=job_id,
            error_message="second native materialization failure",
            progress={
                "state": "failed",
                "phase": "native_materialization",
                "failure": {
                    "code": "test_native_materialization_failed_again",
                    "message": "The recovery attempt failed.",
                    "retryable": False,
                },
            },
        )

    second_failure_outbox = action.store.get_outbox_topic_event(
        topic="control.job.failed",
        event_key=f"{job_id}:job_failed:attempt:{second_lease.attempt}",
        job_id=job_id,
    )
    assert second_failure_outbox is not None
    assert second_failure_outbox.event_key != first_failure_outbox.event_key
    assert _failed_outbox(action, f"{job_id}:job_failed").event_id == first_failure_outbox.event_id

    second_failed_job = action.store.get_job(job_id)
    assert second_failed_job is not None
    second_action = replace(
        action,
        failed_job=second_failed_job,
        failed_attempt=second_lease.attempt,
    )
    _request(second_action)

    third_worker = "native-recovery-worker-3"
    third_lease = action.store.lease_next_job(worker_id=third_worker, lease_seconds=60)
    assert third_lease is not None
    assert third_lease.attempt == action.failed_attempt + 2
    with action.store.job_execution_fence(
        job_id=job_id,
        worker_id=third_worker,
        attempt=third_lease.attempt,
    ):
        current = action.store.current_native_acquisition_custody_recovery()
        assert current is not None
        assert current.failed_attempt == second_lease.attempt
        action.store.complete_job(job_id=job_id, run_id=second_failed_job.run_id)

    completed_outbox = action.store.get_job_completed_outbox_event(job_id)
    assert completed_outbox.event_key == f"{job_id}:job_completed"
    assert len(_recovery_event_rows(action.sqlite_path, job_id)) == 2
    assert len(_recovery_outbox_rows(action.sqlite_path, job_id)) == 2


def test_stale_worker_terminal_fence_cannot_fail_recovered_lease(tmp_path: Path) -> None:
    action = _failed_action(tmp_path)
    _request(action)
    leased = action.store.lease_next_job(worker_id="current-native-worker", lease_seconds=60)
    assert leased is not None
    assert leased.attempt == action.failed_attempt + 1

    with (
        pytest.raises(ControlJobLeaseLostError),
        action.store.job_execution_fence(
            job_id=leased.job_id,
            worker_id=action.failed_worker_id,
            attempt=action.failed_attempt,
        ),
    ):
        action.store.fail_job(
            job_id=leased.job_id,
            error_message="stale original worker must not publish a terminal event",
            progress={"state": "failed", "phase": "stale_worker"},
        )

    current_job = action.store.get_job(leased.job_id)
    assert current_job is not None
    assert current_job.state == "running"
    assert current_job.attempt == leased.attempt
    failure = action.store.get_job_terminal_source_event_record(leased.job_id)
    assert failure.event_type == "job_failed"
    assert failure.payload["attempt"] == action.failed_attempt
    assert len(_recovery_event_rows(action.sqlite_path, leased.job_id)) == 1


@pytest.mark.parametrize("mutation", ["removed", "changed"])
def test_current_recovery_fails_closed_when_immutable_event_is_removed_or_changed(
    tmp_path: Path,
    mutation: str,
) -> None:
    action = _failed_action(tmp_path)
    _request(action)
    leased = action.store.lease_next_job(worker_id="current-native-worker", lease_seconds=60)
    assert leased is not None
    event_rows = _recovery_event_rows(action.sqlite_path, leased.job_id)
    assert len(event_rows) == 1
    recovery_event_id = event_rows[0]["event_id"]
    head_before = action.store.get_acquisition_action_head(
        tenant_id=action.head.tenant_id,
        cell_id=action.head.cell_id,
        run_id=action.head.run_id,
        source_job_id=action.head.source_job_id,
        route_id=action.head.route_id,
        action_generation=action.head.action_generation,
    )
    assert head_before == action.head

    with sqlite3.connect(action.sqlite_path) as connection:
        if mutation == "removed":
            connection.execute(
                "DELETE FROM control_job_events WHERE event_id = ?",
                (recovery_event_id,),
            )
        else:
            payload = json.loads(event_rows[0]["payload_json"])
            payload["failed_event"]["payload_sha256"] = _digest("changed-failure-source-binding")
            connection.execute(
                "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
                (json.dumps(payload, sort_keys=True), recovery_event_id),
            )

    expected_error = (
        "native_custody_recovery_request_missing"
        if mutation == "removed"
        else "native_custody_recovery_failure_changed"
    )
    with (
        action.store.job_execution_fence(
            job_id=leased.job_id,
            worker_id="current-native-worker",
            attempt=leased.attempt,
        ),
        pytest.raises(ValueError, match=expected_error),
    ):
        action.store.current_native_acquisition_custody_recovery()

    current_job = action.store.get_job(leased.job_id)
    assert current_job is not None
    assert current_job.state == "running"
    assert current_job.attempt == leased.attempt
    assert (
        action.store.get_acquisition_action_head(
            tenant_id=action.head.tenant_id,
            cell_id=action.head.cell_id,
            run_id=action.head.run_id,
            source_job_id=action.head.source_job_id,
            route_id=action.head.route_id,
            action_generation=action.head.action_generation,
        )
        == head_before
    )


def test_two_request_owners_schedule_one_recovery_occurrence(tmp_path: Path) -> None:
    """Independent connections compare the same failure/head in the writer transaction."""
    action = _failed_action(tmp_path)
    other = ControlPlaneStore(backend="sqlite", sqlite_path=action.sqlite_path)
    second = replace(action, store=other)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = tuple(workers.map(_request, (action, second)))
    assert tuple(row.state for row in results) == ("pending", "pending")
    assert {row.attempt for row in results} == {action.failed_attempt}
    assert len(_recovery_event_rows(action.sqlite_path, action.failed_job.job_id)) == 1
    assert len(_recovery_outbox_rows(action.sqlite_path, action.failed_job.job_id)) == 1


@pytest.mark.parametrize("graft", ["attempt", "nested-metadata"])
def test_strict_custody_outbox_identity_rejects_boolean_integer_grafts(
    tmp_path: Path,
    graft: str,
) -> None:
    store = _make_store(tmp_path)
    payload = {"attempt": 1, "metadata": {"recovery_generation": 1}}
    original = store.enqueue_outbox_event(
        topic="control.job.custody_recovery_requested",
        event_key="test-strict-custody-payload",
        payload=payload,
        require_matching_payload=True,
    )
    replacement = (
        {"attempt": True, "metadata": {"recovery_generation": 1}}
        if graft == "attempt"
        else {
            "attempt": 1,
            "metadata": {"recovery_generation": True},
        }
    )
    with pytest.raises(ValueError, match="control_job_outbox_immutable_conflict"):
        store.enqueue_outbox_event(
            topic=original.topic,
            event_key=original.event_key,
            payload=replacement,
            require_matching_payload=True,
        )
    retained = store.get_outbox_event(original.event_id)
    assert retained is not None and retained.payload == payload
    assert type(retained.payload["attempt"]) is int
    assert type(retained.payload["metadata"]["recovery_generation"]) is int
