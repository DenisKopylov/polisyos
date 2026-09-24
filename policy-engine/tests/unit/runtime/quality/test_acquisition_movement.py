"""Movement admission consumes supplier evidence without borrowing its authority."""

from pathlib import Path

from polisyos.core import canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_movement import AcquisitionMovementService
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.http.test_acquisition_route_authority_sink import _receipt


def test_supplier_terminal_is_not_gy_admission(tmp_path: Path) -> None:
    """A real persisted no-growth terminal cannot become row movement."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    events = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas, event_log=events, control_store=store
    )
    requested = _receipt(
        receipt_phase="requested",
        coarse_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
    )
    first = sink.persist_phase(requested)
    executing = sink.persist_phase(
        _receipt(
            receipt_phase="executing",
            coarse_phase="executing",
            recovery_state="none",
            predecessor_receipt_ref=first.receipt_ref,
        )
    )
    payload = requested.model_dump(
        exclude={
            "schema_version",
            "coarse_phase",
            "receipt_phase",
            "recovery_state",
            "predecessor_receipt_ref",
            "owner_receipt_refs",
            "receipt_id",
        }
    )
    terminal = AcquisitionRouteLoopReceipt(
        **payload,
        receipt_id="supplier-terminal",
        predecessor_receipt_ref=executing.receipt_ref,
        owner_receipt_refs=("sha256:" + "f" * 64,),
        terminal_outcome="quarantined_no_growth",
    )
    head = sink.persist_terminal(terminal)
    supplier_bytes = cas.get_bytes(head.receipt_ref)
    service = AcquisitionMovementService(control_store=store, artifact_store=cas, event_log=events)

    result = service.consume_terminal(supplier_receipt_ref=head.receipt_ref)

    assert result.status == "refused"
    assert result.reason == "supplier_no_reentry"
    assert result.movement_record is None
    assert result.supplier_receipt_ref == head.receipt_ref
    assert result.receipt_ref != head.receipt_ref
    persisted = canon.from_canonical_bytes(cas.get_bytes(result.receipt_ref))
    assert persisted["reason"] == "supplier_no_reentry"
    assert cas.get_bytes(head.receipt_ref) == supplier_bytes
    assert sink.get_head(terminal) == head


def test_empty_deployment_row_read_refuses_without_inventing_movement(tmp_path: Path) -> None:
    """The installed consumer reports missing evidence under an empty policy slot."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas")
    service = AcquisitionMovementService(
        control_store=store,
        artifact_store=cas,
        event_log=RuntimeDiagnosticEventLog(store=store, artifact_store=cas),
    )
    row = service.project_row(
        row_id="unobserved-row", run_id="unobserved-run", design_problem_ref="sha256:" + "a" * 64
    )
    assert row.records == ()
    assert row.status == "not_established"
    assert row.reason == "movement_supplier_missing"
    assert row.policy_status == "policy_admission_missing"
