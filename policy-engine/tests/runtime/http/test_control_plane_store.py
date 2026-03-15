from __future__ import annotations

import time

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
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
