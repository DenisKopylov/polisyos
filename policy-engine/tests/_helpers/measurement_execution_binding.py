"""Build a test-only binding through the real persisted control-job admission path."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def measurement_execution_binding(tmp_path: Path, *, scope_established: bool = True):
    """Read one typed admitted scope under a live SQLite worker fence.

    This helper exercises the persisted creation event and outbox reconciliation;
    it never treats test labels, an artifact header, or ambient context as admission.
    """
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.data_forge_binding import (
        bind_measurement_root_execution_scope,
    )

    nonce = uuid4().hex
    job_id = f"job-measurement-scope-{nonce}"
    run_id = f"run-measurement-scope-{nonce}"
    actor_subject = f"measurement-test-actor-{nonce}"
    tenant_id = f"tenant-measurement-test-{nonce}"
    cell_id = f"cell-measurement-test-{nonce}"
    payload_ref = "sha256:" + "a" * 64
    manifest_ref = "sha256:" + "b" * 64
    scope_payload = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "actor_subject": actor_subject,
        "actor_authenticated": True,
        "actor_roles": ["analyst"],
    }
    event_payload = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": payload_ref,
        "submitted_by": actor_subject,
        "requested_execution_profile": "research",
        "effective_execution_profile": "research",
        "policy_flags": {},
        "capability_manifest_ref": manifest_ref,
    }
    if scope_established:
        event_payload["execution_scope"] = scope_payload
    store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / f"measurement-control-{nonce}.sqlite3",
    )
    try:
        created = store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=manifest_ref,
            payload_ref=payload_ref,
            submitted_by=actor_subject,
            creation_event_payload=event_payload,
        )
        leased = store.lease_next_job(
            worker_id=f"measurement-scope-worker-{nonce}",
            lease_seconds=30,
        )
        if leased is None or leased.job_id != created.job_id:
            raise AssertionError("test control job was not leased")
        worker_id = leased.lease_owner
        if not worker_id:
            raise AssertionError("test control job lease owner was not established")
        with store.job_execution_fence(
            job_id=leased.job_id,
            worker_id=worker_id,
            attempt=leased.attempt,
        ):
            admission = store.current_execution_job_admission()
            return bind_measurement_root_execution_scope(
                admission=admission,
                job=admission.job,
                execution_scope=admission.scope,
            )
    finally:
        store.close()
