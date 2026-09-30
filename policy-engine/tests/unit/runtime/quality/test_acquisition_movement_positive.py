"""Real supplier completion and separate GY admission reach the board consumer."""

import asyncio
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon, contracts
from polisyos.runtime.http.services.cycle_board_projection import CycleBoardProjectionService
from polisyos.runtime.quality.acquisition_movement import AcquisitionMovementService
from tests._helpers.acquisition_movement import configured_movement_service
from tests.unit.runtime.http.test_cycle_board_projection_service import (
    REPO_ROOT,
    _component_packets,
    _depth_payload,
    _service,
)


def _board(service, supplier):
    """Use existing board enumeration fixtures with the actual completed problem row."""
    depth = _depth_payload()
    domain_runs = dict(depth.domain_runs)
    domain_runs["first_vertical"] = domain_runs["first_vertical"].model_copy(
        update={
            "generation_cycle_run_id": supplier.closure.generation_run.run_id,
            "design_problem_ref": supplier.closure.design_problem_ref,
            "design_problem": supplier.closure.design_problem,
        }
    )
    _, raw, index = _service(
        packets=_component_packets(depth=depth.model_copy(update={"domain_runs": domain_runs}))
    )
    return CycleBoardProjectionService(
        projection_service=raw,
        run_index=index,
        repository_root=REPO_ROOT,
        movement_service=service,
    )


def _supplier(tmp_path, monkeypatch, *, revised_source: bool = False):
    from tests._helpers.acquisition_supplier import build_supplier_terminal_case

    return asyncio.run(
        build_supplier_terminal_case(tmp_path, monkeypatch, revised_source=revised_source)
    )


def _movement_service(supplier):
    return AcquisitionMovementService(
        control_store=supplier.control._control_store,
        artifact_store=supplier.control._artifact_store,
        event_log=supplier.control._diagnostic_event_log,
    )


def test_native_supplier_requires_separate_gy_act_then_projects_to_cycle_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplier = _supplier(tmp_path / "supplier", monkeypatch)
    unallocated = _movement_service(supplier)
    store = supplier.control._artifact_store
    supplier_bytes = store.get_bytes(supplier.supplier_receipt_ref)
    movement = unallocated._derive_movement(supplier.supplier_receipt_ref)
    assert movement.admitted_observation_count == 1
    assert movement.new_cycle_index == movement.source_cycle_index + 1
    assert movement.deeper_terminal_event_id != movement.source_terminal_event_id

    refused = unallocated.consume_terminal(supplier_receipt_ref=supplier.supplier_receipt_ref)
    assert refused.status == "refused"
    assert refused.reason == "policy_admission_missing"
    assert refused.movement_record is None
    assert store.get_bytes(supplier.supplier_receipt_ref) == supplier_bytes

    missing_verification = configured_movement_service(
        unallocated,
        movement,
        tmp_path / "missing-verification",
        include_independent_verification=False,
    )
    partial = missing_verification.consume_terminal(
        supplier_receipt_ref=supplier.supplier_receipt_ref
    )
    assert partial.status == "refused"
    assert partial.movement_record is None

    selected = configured_movement_service(unallocated, movement, tmp_path / "gy-owner")
    admitted = selected.consume_terminal(supplier_receipt_ref=supplier.supplier_receipt_ref)
    assert admitted.status == "admitted", admitted.reason
    assert admitted.movement_record is not None
    assert admitted.receipt_ref != supplier.supplier_receipt_ref
    assert store.get_bytes(supplier.supplier_receipt_ref) == supplier_bytes
    assert canon.from_canonical_bytes(store.get_bytes(admitted.receipt_ref))["status"] == "admitted"

    board = _board(selected, supplier).get()
    row = next(row for row in board.payload.rows if row.row_id == movement.row_id)
    assert row.movement_records == (admitted.movement_record,)
    assert row.movement_status.status == "available"
    assert board.payload.movement_gap.execution_status == "partial"
    assert board.payload.movement_gap.exhaustive is False
    source = next(
        item
        for item in board.composition_manifest
        if item.source_id == f"native-movement:{row.row_id}"
    )
    assert source.authoritative_for == ("per_row_movement",)
    assert "register_closure" in source.may_not_use_for
    global_source = next(
        item
        for item in board.composition_manifest
        if item.source_id == "n13b-global-deeper-terminal"
    )
    assert "per_row_movement" in global_source.may_not_use_for


def test_revised_source_basis_survives_served_admission_reentry_and_movement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revised costed cycle preserves stable S and replays exact basis B to the board."""

    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt

    supplier = _supplier(tmp_path / "supplier", monkeypatch, revised_source=True)
    closure = supplier.closure
    subject = closure.design_problem_ref
    basis = closure.design_problem_basis_ref
    assert closure.source_cycle.cycle_index == 1
    assert subject == closure.generation_run.design_problem_ref
    assert subject == closure.source_cycle.design_problem_ref
    assert subject != basis
    assert closure.design_problem_basis == closure.generation_run.cycles[0].revision_request.revised_problem

    unallocated = _movement_service(supplier)
    movement = unallocated._derive_movement(supplier.supplier_receipt_ref)
    assert movement.design_problem_ref == subject
    assert movement.source_cycle_index == 1
    assert movement.new_cycle_index == 2

    selected = configured_movement_service(unallocated, movement, tmp_path / "gy-owner")
    admitted = selected.consume_terminal(supplier_receipt_ref=supplier.supplier_receipt_ref)
    assert admitted.status == "admitted", admitted.reason
    assert admitted.movement_record is not None
    row = next(
        row for row in _board(selected, supplier).get().payload.rows if row.row_id == movement.row_id
    )
    assert row.movement_records == (admitted.movement_record,)

    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(
            supplier.control._artifact_store.get_bytes(movement.reentry_receipt_ref)
        )
    )
    assert reentry.design_problem_ref == subject
    assert reentry.new_cycle.design_problem_ref == subject
    assert reentry.new_cycle.design_problem_basis_ref == basis
    growth = supplier.case.bridge.project_growth(closure)
    assert growth is not None

    prior = closure.generation_run.cycles[0]
    revised = prior.revision_request.revised_problem
    changed_basis = revised.model_copy(
        update={
            "runtime_hints": {
                **revised.runtime_hints,
                "r13_basis_removal_probe": "changed-with-subject-and-route-markers-retained",
            }
        }
    )
    changed_prior = prior.model_copy(
        update={
            "revision_request": prior.revision_request.model_copy(
                update={"revised_problem": changed_basis}
            )
        }
    )
    changed_run = closure.generation_run.model_copy(
        update={"cycles": (changed_prior, *closure.generation_run.cycles[1:])}
    )
    changed_closure = closure.model_copy(update={"generation_run": changed_run})
    assert changed_closure.design_problem_ref == subject
    assert changed_closure.route_id == closure.route_id
    assert changed_closure.source_cycle.design_problem_basis_ref == basis
    with pytest.raises(AcquisitionRouteClosureError, match="source_cycle_basis_chain_invalid"):
        supplier.case.bridge._validate_reentry(changed_closure, growth, reentry)


def test_remove_decisive_native_bytes_keeps_receipt_markers_but_retracts_board_movement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplier = _supplier(tmp_path / "supplier", monkeypatch)
    unallocated = _movement_service(supplier)
    movement = unallocated._derive_movement(supplier.supplier_receipt_ref)
    selected = configured_movement_service(unallocated, movement, tmp_path / "gy-owner")
    admitted = selected.consume_terminal(supplier_receipt_ref=supplier.supplier_receipt_ref)
    assert admitted.status == "admitted", admitted.reason
    assert admitted.movement_record is not None
    store = supplier.control._artifact_store
    record = admitted.movement_record
    qualifier = contracts.chronology.NativeChronologyQualified.model_validate(
        canon.from_canonical_bytes(store.get_bytes(record.qualification_ref))
    )
    board = _board(selected, supplier)
    marker_refs = (
        supplier.supplier_receipt_ref,
        admitted.receipt_ref,
        record.movement_artifact_ref,
        record.qualification_ref,
    )
    marker_bytes = {ref: store.get_bytes(ref) for ref in marker_refs}
    decisive_refs = (
        str(qualifier.projection_receipt.artifact_ref.artifact_id),
        movement.reentry_receipt_ref,
    )
    for decisive_ref in decisive_refs:
        baseline = next(row for row in board.get().payload.rows if row.row_id == movement.row_id)
        assert baseline.movement_records == (record,)
        blob, _manifest = store._paths(artifacts.ArtifactID.model_validate(decisive_ref))
        native_bytes = blob.read_bytes()
        blob.unlink()
        try:
            packet = board.get()
            row = next(row for row in packet.payload.rows if row.row_id == movement.row_id)
            assert row.movement_records == ()
            assert row.movement_status.status == "invalid_source"
            assert packet.payload.movement_gap.movement_records == ()
            assert all(store.get_bytes(ref) == raw for ref, raw in marker_bytes.items())
            assert (
                canon.from_canonical_bytes(store.get_bytes(admitted.receipt_ref))["status"]
                == "admitted"
            )
            assert not blob.exists(), "row replay silently recreated missing prior native custody"
        finally:
            blob.write_bytes(native_bytes)
