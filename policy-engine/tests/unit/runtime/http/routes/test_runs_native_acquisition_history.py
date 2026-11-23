"""Native history family and wire projection with an explicit upstream replay seam.

The fake verifier return is not Native source/result evidence. Real CAS selected
views and the finite public projection are exercised here; the maintained
retained-source selector owns the authentic full continuation qualification.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import native_source_reentry_history as history
from polisyos.runtime.quality.acquisition_route_loop import persist_world_commit_and_reenter
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
    AcquisitionWorldGrowthReceipt,
    AcquisitionWorldGrowthRoute,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleRun,
    SimulationPortObservation,
    _derive_fronts,
    generation_cycle_run_content_hash,
    validate_acquisition_overlay_continuation,
)
from tests._helpers.semantic_epoch_native import finalize_native_epoch_case, make_native_epoch_case
from tests.unit.core.contracts.test_run_native_generic_acquisition_history_v1 import _wire_row
from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _v3_fixture
from tests.unit.runtime.quality.test_native_derivation_action_history import _native_requested


@pytest.fixture
def projection_case(tmp_path, monkeypatch):
    """Use real selected files; script only the already-verified upstream result."""
    wire = _wire_row(request_profile_version="v4")
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    tenant, cell = "native-history-tenant", "native-history-cell"
    refs = {}
    for name, value in wire.items():
        if not name.endswith("_ref") or not isinstance(value, dict):
            continue
        options = artifacts.ArtifactWriteOptions(
            kind=value["kind"],
            media_type="application/json",
            tenant_context=artifacts.ArtifactTenantContextInfo(tenant_id=tenant, cell_id=cell),
            schema=(
                artifacts.SchemaInfo(
                    name=wire["simulation_result_body"]["artifact_schema_name"],
                    version=wire["simulation_result_body"]["artifact_schema_version"],
                )
                if name == "n5_result_ref"
                else None
            ),
        )
        refs[name] = store.put_json(
            (
                {"schema_version": wire["n5_execution_schema_version"]}
                if name == "n5_execution_ref"
                else {"scripted_owner_boundary": name}
            ),
            options,
            return_selected_profile=True,
        )
    owner_profile = store.put_json(
        {"fixture": "owner cost profile"},
        artifacts.ArtifactWriteOptions(
            kind="runtime.quality.native_derivation_leaf_cost_profile",
            media_type="application/json",
        ),
        return_selected_profile=True,
    )
    provider = object()
    phase = SimpleNamespace(
        compiled_ref=str(refs["source_compiled_ref"].artifact_id),
        owner_declared_profile_ref=owner_profile,
        native_leaf_provider_selection=provider,
    )
    simulation = SimulationPortObservation(
        candidate_id=wire["candidate_id"],
        status="joint_simulated",
        simulation_result_ref=refs["n5_result_ref"],
        generic_n4_source_ref=refs["n4_source_ref"],
        generic_context_job_ref=refs["context_job_ref"],
        cycle_substrate_context_job_ref=refs["context_job_ref"],
        generic_profile_ref=refs["original_profile_ref"],
        generic_n5_input_ref=refs["n5_input_ref"],
        generic_n5_execution_ref=refs["n5_execution_ref"],
        generic_profile_selection_ref=wire["original_profile_selection_ref"],
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
    )
    prepared = SimpleNamespace(
        n4_source_ref=refs["n4_source_ref"],
        n5_input_ref=refs["n5_input_ref"],
        candidate_id=wire["candidate_id"],
    )
    completed = SimpleNamespace(
        n5_execution_ref=refs["n5_execution_ref"],
        n5_result_ref=refs["n5_result_ref"],
        simulation=simulation,
    )
    body = deepcopy(wire["simulation_result_body"])
    numerical = SimpleNamespace(
        schema_version=body["result_schema_version"],
        world_model_record_ref=body["world_model_record_ref"],
        world_model_record_content_hash=body["world_model_record_content_hash"],
        atom_ids=tuple(body["atom_ids"]),
        selected_outcomes=tuple(body["selected_outcomes"]),
        horizon=SimpleNamespace(model_dump=lambda **kwargs: deepcopy(body["horizon"])),
        trajectories=tuple(
            SimpleNamespace(
                run_level=row["run_level"],
                atom_ids=tuple(row["atom_ids"]),
                points=tuple(
                    SimpleNamespace(
                        step=point["step"], outcomes=point["outcomes"], effect=point["effects"]
                    )
                    for point in row["points"]
                ),
            )
            for row in body["trajectories"]
        ),
        uncertainty_kind="K_sim",
    )
    verified = SimpleNamespace(
        selection=SimpleNamespace(
            pending_action_phase=phase,
            pending_action_phase_ref=refs["pending_action_phase_ref"],
            checkpoint_ref=refs["native_world_checkpoint_ref"],
            checkpoint=SimpleNamespace(collection_refs=(refs["native_input_collection_ref"],)),
            original_generic_input_ref=refs["original_generic_input_ref"],
            original_profile_ref=refs["original_profile_ref"],
            world_model_record=SimpleNamespace(
                content_hash=wire["world_model_record_content_hash"]
            ),
        ),
        progress=SimpleNamespace(
            prepared=(refs["prepared_checkpoint_ref"], prepared),
            n5_completed=(refs["n5_completed_checkpoint_ref"], completed),
            cycle_completed=(refs["cycle_completed_checkpoint_ref"], object()),
        ),
        input_record=SimpleNamespace(
            profile=SimpleNamespace(profile_selection_ref=wire["original_profile_selection_ref"]),
            native_current_profile_selection_ref=wire["current_profile_selection_ref"],
            context_job_ref=refs["context_job_ref"],
            schema_version=wire["n5_input_schema_version"],
            n5=SimpleNamespace(schema_version=wire["request_profile_schema_version"]),
        ),
        result=SimpleNamespace(result=numerical, request=SimpleNamespace(engine_plan=())),
    )
    route_receipt = SimpleNamespace(
        schema_version="AcquisitionRouteLoopReceipt@1.2",
        terminal_outcome="reentry_completed",
        owner_declared_profile_ref=owner_profile,
        native_leaf_provider_selection=provider,
        source_job_id=wire["source_job_id"],
        job_id=wire["action_job_id"],
        route_id=wire["route_id"],
        action_generation=wire["action_generation"],
        run_id="actual-control-run",
    )
    reentry = SimpleNamespace(
        source_cycle_index=wire["source_cycle_index"],
        new_cycle=SimpleNamespace(cycle_index=wire["continued_cycle_index"], simulation=simulation),
    )
    head = object()
    verified_head = SimpleNamespace(
        head=head,
        latest_receipt=route_receipt,
        phase_chain=(
            SimpleNamespace(
                receipt_ref=str(refs["pending_action_phase_ref"].artifact_id), receipt=phase
            ),
        ),
    )
    service = SimpleNamespace(
        _control_store=control,
        acquisition_route_sink=SimpleNamespace(verify_action_head=lambda selected: verified_head),
    )
    observed = []

    def scripted_replay(**kwargs):
        observed.append(kwargs)
        return verified

    monkeypatch.setattr(history, "read_native_source_reentry_history", scripted_replay)
    args = {
        "store": store,
        "control_service": service,
        "event_log": events,
        "head": head,
        "route_receipt_ref": refs["route_receipt_ref"],
        "route_receipt": route_receipt,
        "reentry_receipt_ref": refs["reentry_receipt_ref"],
        "reentry_receipt": reentry,
        "source_generation_run": object(),
        "compiled_ref": refs["source_compiled_ref"],
        "tenant_id": tenant,
        "cell_id": cell,
    }
    try:
        yield SimpleNamespace(
            args=args,
            verified=verified,
            observed=observed,
            refs=refs,
            simulation=simulation,
            wire=wire,
        )
    finally:
        control.close()


def test_native_history_projection_preserves_unpaired_profile_and_no_current_authority(
    projection_case,
):
    case = projection_case
    row = runs._native_generic_acquisition_history_entry(**case.args)
    assert (
        row.request_profile_schema_version == "policyos.runtime.generic_cycle_n5_request_profile.v4"
    )
    assert row.original_profile_selection_ref != row.current_profile_selection_ref
    assert row.n5_owner_join_status == "resolved"
    assert row.simulation_result_body.artifact_ref == case.refs["n5_result_ref"]
    assert row.simulation_result_body.trajectories[0].points[1].outcomes == {
        "government.balance": 0.30
    }
    assert row.currentness_status == "not_established"
    assert row.publication_authority is False
    assert row.authority_purpose == "candidate_observation_only"
    assert not set(row.model_dump()).intersection({"ncm_ref", "child_profile_family_ref"})
    assert case.observed[0]["owner"]._native_world_action_owner is None
    assert (
        case.observed[0]["owner"]._native_action_control_store
        is case.args["control_service"]._control_store
    )


@pytest.mark.parametrize(
    "mutation", ["mixed", "loose_profile", "foreign_kind", "policy_child", "missing"]
)
def test_native_history_source_family_refuses_mixed_foreign_or_unselected_refs(
    projection_case, mutation
):
    simulation = projection_case.simulation
    if mutation == "mixed":
        updates = {"candidate_simulation_n4_source_ref": projection_case.refs["n4_source_ref"]}
        code = "acquisition_reentry_source_family_mixed"
    elif mutation == "loose_profile":
        updates = {
            "generic_n5_input_ref": simulation.generic_n5_input_ref.model_copy(
                update={"manifest_profile_sha256": None}
            )
        }
        code = "acquisition_reentry_source_profile_missing"
    elif mutation == "foreign_kind":
        updates = {
            "generic_n4_source_ref": simulation.generic_n4_source_ref.model_copy(
                update={"kind": "runtime.quality.n4_candidate_scenario_source"}
            )
        }
        code = "acquisition_reentry_source_ref_kind_invalid"
    elif mutation == "policy_child":
        updates = {
            "generic_n4_child_profile_family_ref": projection_case.refs["original_profile_ref"]
        }
        code = "native_acquisition_reentry_policy_child_family_invalid"
    else:
        updates = {"generic_n5_input_ref": None}
        code = "acquisition_reentry_source_family_incomplete"
    with pytest.raises(ValueError, match=f"^{code}$"):
        runs._acquisition_reentry_source_family(simulation.model_copy(update=updates))
    assert projection_case.observed == []


def test_legacy_ncm_history_still_selects_its_own_complete_family(projection_case):
    refs = projection_case.refs
    ncm = SimulationPortObservation(
        candidate_id="legacy-candidate",
        status="simulation_pending_n5",
        candidate_simulation_n4_source_ref=refs["n4_source_ref"].model_copy(
            update={"kind": "runtime.quality.n4_candidate_scenario_source"}
        ),
        candidate_simulation_context_job_ref=refs["context_job_ref"],
        candidate_simulation_n5_input_ref=refs["n5_input_ref"].model_copy(
            update={"kind": "runtime.quality.candidate_simulation_n5_input"}
        ),
        candidate_simulation_profile_config_ref="configured-legacy-ncm",
        candidate_simulation_profile_selection_ref="sha256:" + "a" * 64,
    )
    assert runs._acquisition_reentry_source_family(ncm) == "candidate"


@pytest.mark.parametrize("mutation", ["compiled", "profile", "provider", "ancestor"])
def test_native_history_requires_the_original_terminal_ancestor_and_profile(
    projection_case, mutation
):
    case = projection_case
    phase = case.verified.selection.pending_action_phase
    if mutation == "compiled":
        phase.compiled_ref = "sha256:" + "f" * 64
    elif mutation == "profile":
        phase.owner_declared_profile_ref = phase.owner_declared_profile_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
    elif mutation == "provider":
        phase.native_leaf_provider_selection = object()
    else:
        case.verified.selection.pending_action_phase_ref = (
            case.verified.selection.pending_action_phase_ref.model_copy(
                update={"artifact_id": artifacts.ArtifactID.model_validate("sha256:" + "f" * 64)}
            )
        )
    with pytest.raises(
        ValueError, match=r"^native_acquisition_reentry_terminal_ancestor_mismatch$"
    ):
        runs._native_generic_acquisition_history_entry(**case.args)


def test_native_blocked_history_reads_exact_growth_and_refuses_missing_selected_view(
    tmp_path, request
):
    native = make_native_epoch_case(tmp_path / "native")
    finalized = finalize_native_epoch_case(native)
    store = native.store
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    request.addfinalizer(control.close)
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=events, control_store=control
    )
    service = SimpleNamespace(_control_store=control, acquisition_route_sink=sink)
    source = GenerationCycleRun.model_validate(_v3_fixture()[1])
    prior = source.cycles[-1]
    blocker = "budget_exhausted_for_next_level"
    new_cycle = prior.model_copy(
        update={
            "cycle_index": prior.cycle_index + 1,
            "terminal_kind": "acquisition_required",
            "simulation": SimulationPortObservation(
                candidate_id=prior.selected_candidate_ref,
                status="simulation_blocked",
                authority_blockers=(blocker,),
                diagnostics={"port": "N6", "reason": blocker, "scheduler_action": "defer"},
            ),
            "voi_decision": prior.voi_decision.model_copy(
                update={
                    "terminal_kind": "acquisition_required",
                    "scheduler_action": "defer",
                    "scheduler_reason": blocker,
                }
            ),
        }
    )
    appended = tuple(
        item.model_copy(update={"cycle_index": new_cycle.cycle_index})
        for item in source.candidate_summaries
        if item.cycle_index == prior.cycle_index
    )
    summaries = source.candidate_summaries + appended
    continued = source.model_copy(
        update={
            "cycles": (*source.cycles, new_cycle),
            "candidate_summaries": summaries,
            "fronts": _derive_fronts(summaries),
        }
    )
    activated = finalized.activated
    reentry = AcquisitionOverlayReentryReceipt.issue(
        source_run_id=source.run_id,
        design_problem_ref=source.design_problem_ref,
        source_cycle_index=prior.cycle_index,
        source_candidate_ref=prior.selected_candidate_ref,
        overlay_receipt_ref=str(activated.receipt_ref.artifact_id),
        overlay_receipt_content_hash=activated.receipt_content_hash,
        baseline_content_hash=activated.baseline_before_sha256,
        overlay_path="fixture-overlay",
        epoch_id=activated.epoch_id,
        passport_id=activated.passport_id,
        passport_variable_id=native.scenario.passport.variable_id,
        admitted_observation_count=activated.admitted_observation_count,
        semantic_epoch_ref=activated.semantic_epoch_stamp.epoch_ref,
        semantic_epoch_production_receipt_ref=str(finalized.production.receipt_ref.artifact_id),
        semantic_epoch_production_receipt_content_hash=finalized.production.receipt_content_hash,
        new_cycle=new_cycle,
        candidate_summaries=appended,
        source_generation_run_content_hash=generation_cycle_run_content_hash(source),
        continued_generation_run_content_hash=generation_cycle_run_content_hash(continued),
        continued_generation_run=continued,
    )
    validate_acquisition_overlay_continuation(source, reentry)
    compiled_ref = store.put_json(
        {"design_problem_ref": source.design_problem_ref},
        artifacts.ArtifactWriteOptions(
            kind="runtime.compiled_recursive_generation_cycle", media_type="application/json"
        ),
        return_selected_profile=True,
    )
    initial = _native_requested(store, index=1, now=datetime.now(UTC)).model_copy(
        update={"compiled_ref": str(compiled_ref.artifact_id)}
    )
    requested = sink.persist_phase(initial)
    executing = sink.persist_phase(
        initial.model_copy(
            update={
                "receipt_id": "executing",
                "receipt_phase": "executing",
                "coarse_phase": "executing",
                "predecessor_receipt_ref": requested.receipt_ref,
            }
        )
    )
    query = native.scenario.query
    growth = AcquisitionWorldGrowthReceipt(
        selection=AcquisitionWorldGrowthRoute(
            tenant_id=initial.tenant_id,
            cell_id=initial.cell_id,
            run_id=initial.run_id,
            route_id=initial.route_id,
            design_problem_ref=source.design_problem_ref,
            epoch_id=activated.epoch_id,
            epoch_scope_identity=query.scope_identity,
            authority_purpose=query.authority_purpose,
            valid_effect_coordinate_evidence_ref=query.valid_effect_coordinate_evidence_ref,
            visibility_knowledge_cutoff_evidence_ref=query.visibility_knowledge_cutoff_evidence_ref,
            purpose_admission_cutoff_evidence_ref=query.purpose_admission_cutoff_evidence_ref,
            facet_source_refs={},
            reentry_budget_usd=Decimal("0.10"),
        ),
        binding_id="fixture-binding",
        activation=finalized.receipt,
        passport_id=activated.passport_id,
        admitted_observation_delta=activated.admitted_observation_count,
        previously_active_observations=0,
        live_evidence_refs=(native.scenario.passport.raw_artifact_id,),
        action_phase_ref=executing.receipt_ref,
    )
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(),
        repo_root=tmp_path,
        runtime_root=tmp_path,
        authority=native.scenario.authority,
        artifact_store=store,
        event_log=events,
        epoch_deployment=native.deployment,
    )
    growth_id = bridge._persist(
        initial,
        growth.model_dump(mode="json"),
        "runtime_quality.acquisition_world_growth_receipt",
        AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
        "world_committed",
    )
    selected_phase = {
        "receipt_id": "outcome",
        "receipt_phase": "outcome_selected",
        "coarse_phase": "executing",
        "predecessor_receipt_ref": executing.receipt_ref,
        "owner_receipt_refs": (growth_id,),
    }
    selection = sink.persist_phase(initial.model_copy(update=selected_phase))
    reentry_event_id = "evt_acquisition_reentry_" + growth_id.removeprefix("sha256:")
    reentry_ref = bridge._persist(
        initial,
        reentry.model_dump(mode="json"),
        "runtime_quality.acquisition_overlay_reentry_receipt",
        "polisyos.runtime.AcquisitionOverlayReentryReceipt",
        "reentry_terminal",
        event_id=reentry_event_id,
        return_selected_profile=True,
    )
    report = reconcile_authority_ref(
        artifact_store=store,
        event_log=events,
        cas_ref=reentry_ref,
        expected_tenant_id=initial.tenant_id,
        expected_cell_id=initial.cell_id,
        expected_run_id=initial.run_id,
        expected_job_id=initial.source_job_id,
    )
    assert report.durable_event_id == reentry_event_id
    terminal = persist_world_commit_and_reenter(
        sink=sink,
        pending_receipt=initial.model_copy(
            update={
                **selected_phase,
                "receipt_id": "pending",
                "receipt_phase": "world_committed_reentry_pending",
                "coarse_phase": "world_committed",
                "recovery_state": "reentry_recovery_required",
                "predecessor_receipt_ref": selection.receipt_ref,
            }
        ),
        reentry=lambda: str(reentry_ref.artifact_id),
    )
    fresh_sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=events, control_store=control
    )
    service.acquisition_route_sink = fresh_sink
    selected_terminal = artifacts.artifact_ref_for_manifest(
        artifacts.resolve_manifest_by_profile(
            store, terminal.receipt_ref, terminal.receipt_manifest_profile_sha256
        )
    )
    terminal_receipt = fresh_sink.verify_action_head(terminal).latest_receipt
    args = {
        "store": store,
        "control_service": service,
        "head": terminal,
        "route_receipt_ref": selected_terminal,
        "route_receipt": terminal_receipt,
        "reentry_receipt_ref": reentry_ref,
        "reentry_event_id": report.durable_event_id,
        "reentry_receipt": reentry,
        "compiled_ref": compiled_ref,
    }
    row = runs._native_generic_blocked_acquisition_history_entry(**args)
    assert row.blocker_code == blocker
    assert row.continued_cycle_index == prior.cycle_index + 1
    assert row.numerical_result_status == row.currentness_status == "not_established"
    assert row.publication_authority is False
    assert not {"n5_result_ref", "simulation_result_body"} & row.model_dump().keys()

    with pytest.raises(ValueError, match="native_acquisition_blocked_reentry_event_mismatch"):
        runs._native_generic_blocked_acquisition_history_entry(
            **{**args, "reentry_event_id": "evt_acquisition_reentry_" + "0" * 64}
        )

    unexpected_simulation = new_cycle.simulation.model_copy(
        update={"simulation_ref": str(compiled_ref.artifact_id)}
    )
    unexpected_reentry = reentry.model_copy(
        update={"new_cycle": new_cycle.model_copy(update={"simulation": unexpected_simulation})}
    )
    with pytest.raises(ValueError, match="native_acquisition_blocked_reentry_not_established"):
        runs._native_generic_blocked_acquisition_history_entry(
            **{**args, "reentry_receipt": unexpected_reentry}
        )

    overlay_ref = activated.receipt_ref
    exact_view = store._manifest_path_for_ref(
        overlay_ref.artifact_id, overlay_ref.manifest_profile_sha256
    )
    exact_view.unlink()
    assert store.has(overlay_ref.artifact_id)
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        runs._native_generic_blocked_acquisition_history_entry(**args)
