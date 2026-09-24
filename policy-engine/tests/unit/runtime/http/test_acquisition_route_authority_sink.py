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
    AcquisitionRouteLoopReceipt,
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


@pytest.fixture
def generation_owner(tmp_path):
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas, event_log=event_log, control_store=store
    )
    return sink, store, cas


def _generation_identity():
    return {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "job-source",
        "route_id": "sha256:" + "a" * 64,
    }


def _persist_generation(sink, *, generation, job_id, terminal_outcome=None):
    """Exercise the real receipt owner; supplied owner refs are fixture evidence."""
    common = {"action_generation": generation, "job_id": job_id}
    requested = _receipt(
        receipt_phase="requested",
        coarse_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
    )
    requested = AcquisitionRoutePhaseReceipt.model_validate({**requested.model_dump(), **common})
    head = sink.persist_phase(requested)
    executing = AcquisitionRoutePhaseReceipt.model_validate(
        {
            **requested.model_dump(),
            "receipt_id": "receipt-executing",
            "receipt_phase": "executing",
            "coarse_phase": "executing",
            "predecessor_receipt_ref": head.receipt_ref,
        }
    )
    head = sink.persist_phase(executing)
    if terminal_outcome is None:
        return head
    terminal = AcquisitionRouteLoopReceipt.model_validate(
        {
            **executing.model_dump(exclude={"schema_version"}),
            "receipt_id": "receipt-terminal",
            "receipt_phase": "terminal",
            "coarse_phase": "terminal",
            "recovery_state": "complete",
            "predecessor_receipt_ref": head.receipt_ref,
            "terminal_outcome": terminal_outcome,
            "owner_receipt_refs": ("sha256:" + "f" * 64,),
            "reentry_receipt_ref": (
                "sha256:" + "1" * 64 if terminal_outcome == "reentry_completed" else None
            ),
        }
    )
    return sink.persist_terminal(terminal)


def test_action_generation_preserves_quarantine_and_reuses_exact_job(generation_owner):
    sink, store, cas = generation_owner
    identity = _generation_identity()
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    first = _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    first_bytes = cas.get_bytes(first.receipt_ref)
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    assert sink.resolve_action_generation(**identity, job_id="second-job") == 2
    second = _persist_generation(sink, generation=2, job_id="second-job")
    assert sink.resolve_action_generation(**identity, job_id="second-job") == 2
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    heads = store.list_acquisition_action_heads(**identity)
    assert heads == (first, second)
    assert cas.get_bytes(first.receipt_ref) == first_bytes
    assert store.get_acquisition_action_head(**identity, action_generation=1) == first


@pytest.mark.parametrize("terminal_outcome", [None, "reentry_completed"])
def test_new_action_generation_refuses_pending_or_positive_owner(
    generation_owner, terminal_outcome
):
    sink, _store, _cas = generation_owner
    _persist_generation(sink, generation=1, job_id="first-job", terminal_outcome=terminal_outcome)
    with pytest.raises(ValueError, match="acquisition_action_generation_not_reopenable"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")


def test_action_generation_refuses_row_marker_without_terminal_custody(generation_owner):
    sink, store, _cas = generation_owner
    head = _persist_generation(sink, generation=1, job_id="first-job")
    store._execute(
        "UPDATE runtime_acquisition_action_heads SET coarse_phase = 'terminal', "
        "receipt_phase = 'terminal', recovery_state = 'complete' WHERE receipt_ref = ?",
        (head.receipt_ref,),
    )
    with pytest.raises(ValueError, match="acquisition_action_head_binding_mismatch"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")


def test_action_generation_requires_current_receipt_readback(generation_owner, monkeypatch):
    sink, store, cas = generation_owner
    head = _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    before = store.list_acquisition_action_heads(**_generation_identity())
    original = cas.get_bytes

    def unreadable(ref):
        if ref == head.receipt_ref:
            raise OSError("selected terminal receipt unreadable")
        return original(ref)

    monkeypatch.setattr(cas, "get_bytes", unreadable)
    with pytest.raises(OSError, match="selected terminal receipt unreadable"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")
    assert store.list_acquisition_action_heads(**_generation_identity()) == before


def test_action_generation_refuses_same_job_in_multiple_generations(generation_owner):
    sink, _store, _cas = generation_owner
    _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    _persist_generation(sink, generation=2, job_id="first-job")
    with pytest.raises(ValueError, match="acquisition_action_job_generation_ambiguous"):
        sink.resolve_action_generation(**_generation_identity(), job_id="first-job")
