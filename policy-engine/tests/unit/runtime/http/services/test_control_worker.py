from __future__ import annotations

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker


def test_dispatch_persists_deduplicated_handoff_refs_on_worker_events(tmp_path) -> None:
    store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    job_id = "job-worker-handoff-provenance"
    store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id="run-worker-handoff-provenance",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="fixture",
        initial_progress={
            "evidence_spine_handoffs": [
                {
                    "input_refs": [
                        "artifact://fixture-input",
                        "artifact://fixture-input",
                        "",
                    ],
                    "output_refs": ["artifact://fixture-output"],
                    "carrier_ref": "artifact://fixture-carrier",
                }
            ]
        },
    )

    worker = ControlWorker(
        store=store,
        handler=lambda job: store.complete_job(job_id=job.job_id),
        worker_id="worker-handoff-provenance",
    )

    assert worker.dispatch_once() is True
    completed = store.get_job(job_id)
    assert completed is not None
    assert completed.state == "completed"

    events = store.list_diagnostic_events(job_id=job_id)
    assert [record.event.state_after for record in events] == ["leased", "released"]
    for record in events:
        assert record.event.input_refs.count("artifact://fixture-input") == 1
        assert "artifact://fixture-output" in record.event.input_refs
        assert "artifact://fixture-carrier" in record.event.input_refs
        assert record.event.tenant_id == "tenant-unknown"
        assert record.event.cell_id == "cell-unknown"
