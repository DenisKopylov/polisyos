"""Pin the child release to the persisted control-job execution fence."""

import sqlite3
from pathlib import Path

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlPlaneStore,
)


def _leased(store: ControlPlaneStore, *, known: bool) -> int:
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established" if known else "not_established",
        "tenant_id": "tenant-a" if known else None,
        "cell_id": "cell-a" if known else None,
        "actor_subject": "actor-a" if known else None,
        "actor_authenticated": known,
        "actor_roles": ["analyst"] if known else [],
    }
    payload = {
        "job_id": "job-a",
        "run_id": "run-a",
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": "sha256:fixture-payload",
        "submitted_by": "actor-a" if known else None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {"candidate": True},
        "capability_manifest_ref": None,
        "execution_scope": scope,
    }
    store.create_job(
        job_id="job-a",
        kind="natural_language_run",
        run_id="run-a",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=None,
        payload_ref="sha256:fixture-payload",
        submitted_by="actor-a" if known else None,
        creation_event_payload=payload,
    )
    job = store.lease_next_job(worker_id="worker-a", lease_seconds=60)
    assert job is not None
    return job.attempt


def test_live_owner_fence_and_lost_lease_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    attempt = _leased(store, known=True)
    with store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
        fence = store.child_computation_publication_fence()
        assert (fence.root_run_id, fence.control_job_id, fence.tenant_id, fence.cell_id) == (
            "run-a",
            "job-a",
            "tenant-a",
            "cell-a",
        )
        fence.check_active()
        with fence.publication():
            assert store.current_execution_job_record().run_id == "run-a"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ("2000-01-01T00:00:00+00:00", "job-a"),
            )
        with pytest.raises(ControlJobLeaseLostError), fence.publication():
            pytest.fail("expired lease reached release head")
    with pytest.raises(ControlJobLeaseLostError):
        fence.check_active()


def test_unknown_scope_cannot_issue_publication_fence(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "unknown.sqlite3")
    attempt = _leased(store, known=False)
    with (
        store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt),
        pytest.raises(ControlJobExecutionAdmissionError, match="scope_not_established"),
    ):
        store.child_computation_publication_fence()


def test_generic_event_and_outbox_cannot_mint_child_authority(tmp_path: Path) -> None:
    path = tmp_path / "reserved.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    attempt = _leased(store, known=True)
    with store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
        with pytest.raises(ValueError, match="child_release_event_reserved_for_owner"):
            store.append_event(
                job_id="job-a", event_type="child.release.authorized.forged", payload={}
            )
        with pytest.raises(ValueError, match="child_release_outbox_reserved_for_owner"):
            store.enqueue_outbox_event(topic="control.child.release.forged", payload={})
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT count(*) FROM control_job_events WHERE event_type LIKE 'child.release.%'"
        ).fetchone()
        assert rows == (0,)
        rows = conn.execute(
            "SELECT count(*) FROM control_outbox_events WHERE topic LIKE 'control.child.release.%'"
        ).fetchone()
        assert rows == (0,)
