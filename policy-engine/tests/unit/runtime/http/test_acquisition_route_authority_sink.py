from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRoutePhaseReceipt,
    AcquisitionRouteRecoveryRequired,
    persist_world_commit_and_reenter,
    resume_world_committed_reentry,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _receipt(
    *,
    receipt_phase: str,
    coarse_phase: str,
    recovery_state: str,
    predecessor_receipt_ref: str | None,
    owner_receipt_refs: tuple[str, ...] = (),
) -> AcquisitionRoutePhaseReceipt:
    return AcquisitionRoutePhaseReceipt(
        receipt_id=f"receipt-{receipt_phase}",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-source",
        route_id="sha256:" + "a" * 64,
        action_generation=1,
        job_id="job-acquisition",
        compiled_ref="sha256:" + "b" * 64,
        planner_report_hash="sha256:" + "c" * 64,
        cost_basis_hash="sha256:" + "d" * 64,
        decision_ref="sha256:" + "e" * 64,
        coarse_phase=coarse_phase,
        receipt_phase=receipt_phase,
        recovery_state=recovery_state,
        predecessor_receipt_ref=predecessor_receipt_ref,
        owner_receipt_refs=owner_receipt_refs,
        generated_at=NOW,
    )


def test_active_owner_receipt_persists_reentry_pending_before_callback(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas,
        event_log=event_log,
        control_store=store,
    )
    requested = sink.persist_phase(
        _receipt(
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
    )
    executing = sink.persist_phase(
        _receipt(
            receipt_phase="executing",
            coarse_phase="executing",
            recovery_state="none",
            predecessor_receipt_ref=requested.receipt_ref,
        )
    )
    pending = _receipt(
        receipt_phase="world_committed_reentry_pending",
        coarse_phase="world_committed",
        recovery_state="reentry_recovery_required",
        predecessor_receipt_ref=executing.receipt_ref,
        owner_receipt_refs=("sha256:" + "f" * 64,),
    )
    reentry_calls = 0

    def crash_after_readback() -> str:
        nonlocal reentry_calls
        reentry_calls += 1
        durable = sink.get_head(pending)
        assert durable is not None
        assert durable.receipt_phase == "world_committed_reentry_pending"
        assert durable.recovery_state == "reentry_recovery_required"
        raise RuntimeError("crash-after-world-commit")

    with pytest.raises(AcquisitionRouteRecoveryRequired):
        persist_world_commit_and_reenter(
            sink=sink,
            pending_receipt=pending,
            reentry=crash_after_readback,
        )

    assert reentry_calls == 1
    pending_durable = sink.get_head(pending)
    assert pending_durable is not None

    def complete_reentry() -> str:
        current = sink.get_head(pending)
        assert current == pending_durable
        assert current.receipt_phase == "world_committed_reentry_pending"
        assert current.receipt_ref == pending_durable.receipt_ref
        assert current.durable_event_id == pending_durable.durable_event_id
        assert all(
            row.event.event_type != "polisyos.runtime.acquisition.route_loop.v1"
            for row in event_log.list_events(run_id=pending.run_id, job_id=pending.job_id)
        )
        return "sha256:" + "1" * 64

    recovered = resume_world_committed_reentry(
        sink=sink,
        pending_receipt=pending,
        reentry=complete_reentry,
    )
    assert recovered.receipt_phase == "terminal"
    assert recovered.recovery_state == "complete"
    assert recovered.predecessor_receipt_ref == pending_durable.receipt_ref
    assert recovered.receipt_ref != pending_durable.receipt_ref
    assert recovered.durable_event_id != pending_durable.durable_event_id

    terminal_manifest = cas.get_manifest(recovered.receipt_ref)
    assert terminal_manifest.kind == "runtime_quality.acquisition_route_loop_receipt"
    assert terminal_manifest.artifact_schema is not None
    assert terminal_manifest.artifact_schema.name == "polisyos.runtime.AcquisitionRouteLoopReceipt"
    terminal_payload = canon.from_canonical_bytes(cas.get_bytes(recovered.receipt_ref))
    assert terminal_payload["schema_version"] == "AcquisitionRouteLoopReceipt@1.0"
    assert terminal_payload["receipt_phase"] == "terminal"
    assert terminal_payload["predecessor_receipt_ref"] == pending_durable.receipt_ref
    assert terminal_payload["reentry_receipt_ref"] == "sha256:" + "1" * 64

    terminal_events = event_log.list_events(event_id=recovered.durable_event_id)
    assert len(terminal_events) == 1
    assert terminal_events[0].event.event_type == "polisyos.runtime.acquisition.route_loop.v1"

    with pytest.raises(ValueError, match="receipt_phase"):
        _receipt(
            receipt_phase="terminal",
            coarse_phase="terminal",
            recovery_state="complete",
            predecessor_receipt_ref=pending_durable.receipt_ref,
            owner_receipt_refs=("sha256:" + "1" * 64,),
        )
