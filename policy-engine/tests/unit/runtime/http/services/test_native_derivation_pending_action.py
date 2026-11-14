"""Native derivation action projections and pending terminal lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionRouteListResponse,
    NativeDerivationLeafRouteProjection,
    NativeModelInputTargetProjection,
)
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
)
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceipt,
    NativeDerivationLeafProviderSelection,
    NativeDerivationLeafRouteAvailability,
    NativeModelInputTargetAvailability,
)


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + digit * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + digit * 64,
    )


def test_native_leaf_availability_is_readonly_and_route_bound() -> None:
    bundle_ref = _ref("runtime.quality.n7_derivation_bundle", "a")
    availability = NativeDerivationLeafRouteAvailability(
        route_id="sha256:" + "b" * 64,
        source_node_id="node-income",
        derivation_bundle_ref=bundle_ref,
        requirement_gap_id="gap-income",
        planner_record_id="planner-income",
        selected_supplier_ref=None,
        source_origin=SimpleNamespace(),
        expected_scope=None,
        reason_codes=("native_leaf_supplier_not_established",),
    )

    projection = AcquisitionActionService._native_leaf_projection(
        availability, tenant_id="tenant-a", cell_id="cell-a", run_id="run-a"
    )
    response = AcquisitionRouteListResponse(run_id="run-a", routes=(projection,))

    assert type(response.routes[0]) is NativeDerivationLeafRouteProjection
    assert response.routes[0].route_id == availability.route_id
    assert response.routes[0].derivation_bundle_ref == bundle_ref
    assert response.routes[0].selected_supplier_ref is None
    assert response.routes[0].reason_codes == ("native_leaf_supplier_not_established",)
    assert "cost_basis" not in response.routes[0].model_dump(mode="json")
    assert "replay_pins" not in response.routes[0].model_dump(mode="json")


def test_unplanned_native_model_input_target_projects_selected_refs_without_plan() -> None:
    target = NativeModelInputTargetAvailability(
        route_id="sha256:" + "b" * 64,
        obligation_set_ref=_ref("runtime.quality.model_input_obligation_set", "a"),
        model_input_obligation_ref=_ref("runtime.quality.model_input_obligation", "c"),
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "d"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "e"),
        requirement_gap_id="gap-native-model-input",
        planner_record_id="planner-native-model-input",
        reason_codes=("native_derivation_plan_not_selected",),
    )

    projection = AcquisitionActionService._native_model_input_target_projection(
        target, tenant_id="tenant-a", cell_id="cell-a", run_id="run-a"
    )

    assert projection.model_goal_status == "inputs_pending"
    assert projection.action_authority == "not_established"
    assert projection.publication_authority is False
    assert projection.source_currentness == "not_established"
    assert projection.obligation_set_ref == target.obligation_set_ref
    assert projection.model_input_obligation_ref == target.model_input_obligation_ref
    assert projection.configured_port_source_ref == target.configured_port_source_ref
    assert projection.planner_report_ref == target.planner_report_ref
    assert "derivation_bundle_ref" not in projection.model_dump(mode="json")
    assert "cost_basis" not in projection.model_dump(mode="json")
    assert "replay_pins" not in projection.model_dump(mode="json")


def test_service_list_and_get_preserve_native_target_and_leaf_union() -> None:
    target = NativeModelInputTargetAvailability(
        route_id="sha256:" + "b" * 64,
        obligation_set_ref=_ref("runtime.quality.model_input_obligation_set", "a"),
        model_input_obligation_ref=_ref("runtime.quality.model_input_obligation", "c"),
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "d"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "e"),
        requirement_gap_id="gap-native-model-input",
        planner_record_id="planner-native-model-input",
        reason_codes=("native_derivation_plan_not_selected",),
    )
    leaf = NativeDerivationLeafRouteAvailability(
        route_id="sha256:" + "f" * 64,
        source_node_id="node-income",
        derivation_bundle_ref=_ref("runtime.quality.n7_derivation_bundle", "1"),
        requirement_gap_id="gap-leaf-income",
        planner_record_id="planner-leaf-income",
        selected_supplier_ref=None,
        source_origin=SimpleNamespace(),
        expected_scope=None,
        reason_codes=("native_leaf_supplier_not_established",),
    )
    loop = SimpleNamespace(resolve_native_derivation_leaf_routes=lambda *, run_id: (target, leaf))
    service = object.__new__(AcquisitionActionService)
    service._route_loop = lambda **_kwargs: loop

    listed = service.list_routes(tenant_id="tenant-a", cell_id="cell-a", run_id="run-a")
    got_target = service.get_route(
        tenant_id="tenant-a", cell_id="cell-a", run_id="run-a", route_id=target.route_id
    )
    got_leaf = service.get_route(
        tenant_id="tenant-a", cell_id="cell-a", run_id="run-a", route_id=leaf.route_id
    )

    assert tuple(type(item) for item in listed.routes) == (
        NativeModelInputTargetProjection,
        NativeDerivationLeafRouteProjection,
    )
    assert listed.routes[0].route_id == got_target.route_id == target.route_id
    assert listed.routes[1].route_id == got_leaf.route_id == leaf.route_id
    assert listed.routes[0].tenant_id == got_target.tenant_id == "tenant-a"
    assert listed.routes[1].cell_id == got_leaf.cell_id == "cell-a"
    with pytest.raises(AcquisitionActionServiceError, match="native_leaf_route_not_current"):
        service.get_route(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-a",
            route_id="sha256:" + "2" * 64,
        )


@pytest.mark.parametrize(
    ("field", "bad_ref"),
    [
        ("model_input_obligation_ref", _ref("wrong.kind", "c")),
        (
            "configured_port_source_ref",
            ArtifactRef(
                artifact_id="sha256:" + "d" * 64,
                kind="runtime.quality.n7_configured_candidate_port_source",
                media_type="application/json",
            ),
        ),
    ],
)
def test_unplanned_native_model_input_target_rejects_wrong_or_unselected_ref(
    field: str, bad_ref: ArtifactRef
) -> None:
    payload = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "route_id": "sha256:" + "b" * 64,
        "obligation_set_ref": _ref("runtime.quality.model_input_obligation_set", "a"),
        "model_input_obligation_ref": _ref("runtime.quality.model_input_obligation", "c"),
        "configured_port_source_ref": _ref(
            "runtime.quality.n7_configured_candidate_port_source", "d"
        ),
        "planner_report_ref": _ref("runtime.acquisition_planner_report", "e"),
        "requirement_gap_id": "gap-native-model-input",
        "planner_record_id": "planner-native-model-input",
        "reason_codes": ["native_derivation_plan_not_selected"],
    }
    payload[field] = bad_ref.model_dump(mode="python")

    with pytest.raises(ValueError, match="native_model_input_target_ref_unselected"):
        NativeModelInputTargetProjection.model_validate(payload)


def test_native_leaf_admission_skips_scalar_dispatch_but_legacy_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_closure = SimpleNamespace(native_derivation_leaf_scope=object())
    legacy_closure = SimpleNamespace(native_derivation_leaf_scope=None)
    bridge = SimpleNamespace()
    execution = object.__new__(WorldBankWDIAcquisitionExecutionPort)
    execution._world_growth_bridge = bridge
    scalar_calls: list[tuple[object, object]] = []

    def scalar_dispatch(selected_bridge: object, selected_closure: object) -> str:
        scalar_calls.append((selected_bridge, selected_closure))
        return "legacy-dispatched"

    from polisyos.runtime.quality import acquisition_evaluation_dispatch

    monkeypatch.setattr(
        acquisition_evaluation_dispatch,
        "complete_positive_acquisition_admission",
        scalar_dispatch,
    )

    assert execution.complete_positive_admission(native_closure) is None
    assert execution.complete_positive_admission(legacy_closure) == "legacy-dispatched"
    assert scalar_calls == [(bridge, legacy_closure)]


def test_inputs_pending_terminal_completes_action_without_consuming_model_movement() -> None:
    collection_ref = _ref("runtime_quality.native_derivation_input_checkpoint", "c")
    profile_ref = _ref("runtime.quality.native_derivation_leaf_cost_profile", "d")
    provider = NativeDerivationLeafProviderSelection(
        source_node_id="node-income",
        supplier_ref=_ref("fixture.native_supplier", "a"),
        authority_entry_id="acquisition-authority:sha256:" + "b" * 64,
        connector_id="worldbank.wdi",
    )
    terminal = AcquisitionRouteLoopReceipt(
        schema_version="AcquisitionRouteLoopReceipt@1.2",
        receipt_id="job-a.terminal.inputs-pending",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-job-a",
        route_id="sha256:" + "e" * 64,
        action_generation=1,
        job_id="job-a",
        compiled_ref="sha256:" + "f" * 64,
        planner_report_hash="sha256:" + "1" * 64,
        cost_basis_hash="sha256:" + "2" * 64,
        decision_ref="sha256:" + "3" * 64,
        terminal_outcome="inputs_pending",
        predecessor_receipt_ref="sha256:" + "4" * 64,
        owner_receipt_refs=(str(collection_ref.artifact_id),),
        native_input_collection_ref=collection_ref,
        owner_declared_profile_ref=profile_ref,
        native_leaf_provider_selection=provider,
        generated_at=datetime.now(UTC),
    )
    sink = SimpleNamespace(
        verify_action_head=lambda selected_head: SimpleNamespace(
            head=selected_head, latest_receipt=terminal
        ),
        _read_verified_action_phase=lambda _ref: SimpleNamespace(receipt=terminal),
    )
    movement_calls: list[str] = []
    service = object.__new__(AcquisitionActionService)
    service.control_service = SimpleNamespace(acquisition_route_sink=sink)
    service._movement_service = SimpleNamespace(
        consume_terminal=lambda *, supplier_receipt_ref: movement_calls.append(supplier_receipt_ref)
    )
    head = AcquisitionActionHeadRecord(
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        source_job_id=terminal.source_job_id,
        route_id=terminal.route_id,
        action_generation=terminal.action_generation,
        head_generation=1,
        receipt_ref="sha256:" + "5" * 64,
        receipt_sha256="5" * 64,
        durable_event_id="event-a",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=terminal.job_id,
        predecessor_receipt_ref=terminal.predecessor_receipt_ref,
        created_at=datetime.now(UTC),
        receipt_manifest_profile_sha256="sha256:" + "5" * 64,
    )

    progress = service._terminal_progress(head)
    service._consume_movement(head.receipt_ref)

    assert progress["state"] == "completed"
    assert progress["model_goal_status"] == "inputs_pending"
    assert progress["native_input_collection_ref"] == collection_ref
    assert progress["owner_declared_profile_ref"] == profile_ref
    assert terminal.schema_version == "AcquisitionRouteLoopReceipt@1.2"
    assert terminal.native_leaf_provider_selection == provider
    assert movement_calls == []


def test_inputs_pending_terminal_readback_must_match_current_head() -> None:
    terminal = AcquisitionRouteLoopReceipt(
        schema_version="AcquisitionRouteLoopReceipt@1.0",
        receipt_id="other.terminal",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-job-a",
        route_id="sha256:" + "6" * 64,
        action_generation=1,
        job_id="other",
        compiled_ref="sha256:" + "7" * 64,
        planner_report_hash="sha256:" + "8" * 64,
        cost_basis_hash="sha256:" + "9" * 64,
        decision_ref="sha256:" + "a" * 64,
        terminal_outcome="quarantined_no_growth",
        predecessor_receipt_ref="sha256:" + "b" * 64,
        owner_receipt_refs=("sha256:" + "c" * 64,),
        generated_at=datetime.now(UTC),
    )
    service = object.__new__(AcquisitionActionService)
    service.control_service = SimpleNamespace(
        acquisition_route_sink=SimpleNamespace(
            verify_action_head=lambda selected_head: SimpleNamespace(
                head=selected_head, latest_receipt=terminal
            )
        )
    )
    head = AcquisitionActionHeadRecord(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-job-a",
        route_id="sha256:" + "d" * 64,
        action_generation=1,
        head_generation=1,
        receipt_ref="sha256:" + "e" * 64,
        receipt_sha256="e" * 64,
        durable_event_id="event-a",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id="job-a",
        predecessor_receipt_ref="sha256:" + "b" * 64,
        created_at=datetime.now(UTC),
        receipt_manifest_profile_sha256="sha256:" + "e" * 64,
    )

    with pytest.raises(ValueError, match="acquisition_terminal_head_mismatch"):
        service._terminal_progress(head)
