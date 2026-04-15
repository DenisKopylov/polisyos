from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime
from typing import cast

import polisyos.runtime.http.services.control_worker as control_worker_module
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.services.control_plane_store import ControlJobRecord, ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker


def _make_store(tmp_path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def test_control_plane_store_tracks_worker_leases_and_outbox(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.heartbeat_worker(
        worker_id="worker-a",
        state="idle",
        lease_seconds=30,
        backend="external",
        metadata={"zone": "lab"},
    )

    workers = store.list_worker_leases()
    assert len(workers) == 1
    assert workers[0].worker_id == "worker-a"
    assert workers[0].state == "idle"
    assert workers[0].metadata["zone"] == "lab"

    record = store.create_job(
        job_id="job_fixture_001",
        kind="workflow_run",
        run_id="R_fixture_001",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    assert leased.job_id == record.job_id

    store.heartbeat_worker(
        worker_id="worker-a",
        state="running",
        lease_seconds=30,
        backend="external",
        active_job_id=record.job_id,
        metadata={"job_kind": record.kind},
    )
    store.update_progress_state(
        job_id=record.job_id,
        state="running",
        progress={"phase": "dispatch"},
    )
    store.complete_job(
        job_id=record.job_id,
        progress={"phase": "completed"},
    )

    first = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    second = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    assert first.event_id == second.event_id

    topics = {item.topic for item in store.list_outbox_events(state=None, limit=16)}
    assert "control.job.created" in topics
    assert "control.job.running" in topics
    assert "control.job.progress" in topics
    assert "control.job.completed" in topics
    assert "control.decision_validity.event_published" in topics

    store.mark_outbox_published(event_id=first.event_id)
    published = store.get_outbox_event(first.event_id)
    assert published is not None
    assert published.state == "published"

    store.release_worker(worker_id="worker-a")
    all_workers = store.list_worker_leases(active_only=False)
    assert all_workers[0].state == "stopped"


def test_control_worker_renews_job_lease_while_handler_runs(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_renewal",
        kind="workflow_run",
        run_id="R_fixture_renewal",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    observed: dict[str, object] = {}

    def _handler(job) -> None:
        initial = store.get_job(job.job_id)
        assert initial is not None
        observed["initial_expiry"] = initial.lease_expires_at
        deadline = time.time() + 4.0
        renewed = None
        while time.time() < deadline:
            current = store.get_job(job.job_id)
            assert current is not None
            if (
                current.lease_expires_at is not None
                and initial.lease_expires_at is not None
                and current.lease_expires_at > initial.lease_expires_at
            ):
                renewed = current.lease_expires_at
                break
            time.sleep(0.1)
        observed["renewed_expiry"] = renewed
        store.complete_job(job_id=job.job_id)

    worker = ControlWorker(
        store=store,
        handler=_handler,
        lease_seconds=2,
        poll_interval_s=0.05,
        worker_id="ctrl-worker-test",
    )

    assert worker.dispatch_once() is True
    assert observed["renewed_expiry"] is not None
    assert observed["renewed_expiry"] > observed["initial_expiry"]

    workers = store.list_worker_leases(active_only=False)
    assert len(workers) == 1
    assert workers[0].worker_id == "ctrl-worker-test"
    assert workers[0].state == "idle"
    assert workers[0].metadata["last_job_id"] == "job_fixture_renewal"


def test_control_plane_store_dead_letters_terminal_failures(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_failed",
        kind="workflow_run",
        run_id="R_fixture_failed",
        pipeline_id="pipeline_fixture",
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.fail_job(job_id="job_fixture_failed", error_message="permanent failure")

    failed = store.get_job("job_fixture_failed")
    assert failed is not None
    assert failed.state == "failed"

    dead_letters = store.list_dead_letter_jobs()
    assert len(dead_letters) == 1
    assert dead_letters[0].job_id == "job_fixture_failed"
    assert dead_letters[0].run_id == "R_fixture_failed"
    assert dead_letters[0].pipeline_id == "pipeline_fixture"
    assert dead_letters[0].error_message == "permanent failure"
    assert dead_letters[0].acknowledged_at is None

    store.acknowledge_dead_letter_job(
        job_id="job_fixture_failed",
        acknowledged_by="operator@example.test",
    )
    assert store.list_dead_letter_jobs() == []
    acknowledged = store.list_dead_letter_jobs(acknowledged=True)
    assert acknowledged[0].acknowledged_by == "operator@example.test"


def test_control_plane_sqlite_uses_wal_journaling(tmp_path) -> None:
    db_path = tmp_path / "control-plane.sqlite3"
    _ = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)

    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert synchronous in {1, 2}


class _FlakyHeartbeatStore:
    def __init__(self) -> None:
        self.fail = threading.Event()

    def heartbeat_worker(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )

    def renew_job_lease(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )


def test_control_worker_shutdown_suppresses_heartbeat_store_unavailable_logs(
    monkeypatch,
) -> None:
    store = _FlakyHeartbeatStore()
    warnings: list[tuple[object, ...]] = []
    exceptions: list[tuple[object, ...]] = []
    worker = ControlWorker(
        store=cast("ControlPlaneStore", store),
        handler=lambda _job: None,
        lease_seconds=1,
        worker_id="ctrl-worker-shutdown",
    )
    job = ControlJobRecord(
        job_id="job_shutdown",
        kind="workflow_run",
        state="running",
        run_id="R_shutdown",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=None,
        lease_owner=worker.worker_id,
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={},
    )

    def _handler(_job: ControlJobRecord) -> None:
        store.fail.set()
        worker._stop.set()
        time.sleep(worker._heartbeat_interval_s + 0.05)

    monkeypatch.setattr(worker, "_handler", _handler)
    monkeypatch.setattr(
        control_worker_module.logger,
        "warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    monkeypatch.setattr(
        control_worker_module.logger,
        "exception",
        lambda *args, **kwargs: exceptions.append(args),
    )

    worker._run_with_lease_heartbeat(job)

    assert warnings == []
    assert exceptions == []
