"""Native history family and wire projection with an explicit upstream replay seam.

The fake verifier return is not Native source/result evidence. Real CAS selected
views and the finite public projection are exercised here; the maintained
retained-source selector owns the authentic full continuation qualification.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import native_source_reentry_history as history
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import SimulationPortObservation
from tests.unit.core.contracts.test_run_native_generic_acquisition_history_v1 import _wire_row


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
