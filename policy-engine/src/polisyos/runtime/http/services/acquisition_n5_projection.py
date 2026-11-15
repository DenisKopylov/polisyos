"""Shared finite projection of owner-resolved N5 candidate results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactRef,
    read_core_manifest_profile,
)
from polisyos.core.contracts import RunCandidateSimulationN5ResultBody

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactManifest, CoreJSONArtifactStore
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
        JointSimulationResult,
    )


class SelectedN5ScopeNotEstablishedError(ValueError):
    """The selected N5 result has no declared tenant and cell binding."""


def read_selected_n5_result_manifest(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    *,
    tenant_id: str,
    cell_id: str,
) -> ArtifactManifest:
    """Reopen the exact result manifest and enforce its tenant and cell scope."""
    manifest = read_core_manifest_profile(store, ref)[0]
    scope = manifest.tenant_context
    if scope is None:
        raise SelectedN5ScopeNotEstablishedError("generic_n5_result_scope_not_established")
    if (scope.tenant_id, scope.cell_id) != (tenant_id, cell_id):
        raise ArtifactOwnershipError("selected N5 result belongs to another tenant or cell")
    return manifest


def build_candidate_n5_result_body(
    *,
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    result: JointSimulationResult,
    source: N4CandidateScenarioSourceRecordV3,
    tenant_id: str,
    cell_id: str,
    authority_purpose: str,
) -> RunCandidateSimulationN5ResultBody:
    """Project owner-resolved candidate N5 numbers and their declared units."""
    manifest = read_selected_n5_result_manifest(
        store,
        ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    return RunCandidateSimulationN5ResultBody.model_validate(
        {
            **n5_numerical_body_payload(
                ref=ref,
                manifest=manifest,
                result=result,
                authority_purpose=authority_purpose,
            ),
            **n5_declared_candidate_units(source, result),
        }
    )


def n5_numerical_body_payload(
    *,
    ref: ArtifactRef,
    manifest: ArtifactManifest,
    result: JointSimulationResult,
    authority_purpose: str,
    store: CoreJSONArtifactStore | None = None,
    request: JointSimulationRequest | None = None,
) -> dict[str, object]:
    """Project finite numerical fields and selected-slot units when replay establishes them."""
    if ref.manifest_profile_sha256 is None or manifest.artifact_schema is None:
        raise ValueError("candidate_n5_result_body_selected_manifest_view_not_established")
    payload: dict[str, object] = {
        "artifact_ref": ref,
        "artifact_schema_name": manifest.artifact_schema.name,
        "artifact_schema_version": manifest.artifact_schema.version,
        "result_schema_version": result.schema_version,
        "selected_manifest_profile_sha256": ref.manifest_profile_sha256,
        "world_model_record_ref": result.world_model_record_ref,
        "world_model_record_content_hash": result.world_model_record_content_hash,
        "atom_ids": result.atom_ids,
        "selected_outcomes": result.selected_outcomes,
        "horizon": result.horizon.model_dump(mode="python"),
        "trajectories": tuple(
            {
                "run_level": trajectory.run_level,
                "atom_ids": trajectory.atom_ids,
                "points": tuple(
                    {
                        "step": point.step,
                        "outcomes": point.outcomes,
                        "effects": point.effect,
                    }
                    for point in trajectory.points
                ),
            }
            for trajectory in result.trajectories
        ),
        "uncertainty_kind": result.uncertainty_kind,
        "authority_purpose": authority_purpose,
        "candidate_status": "candidate_unverified",
        "currentness_status": "not_established",
        "publication_authority": False,
    }
    if request is not None:
        if store is None:
            raise ValueError("generic_n5_outcome_units_store_not_established")
        payload.update(_generic_program_graph_outcome_unit_fields(store, request, result))
    return payload


def _generic_program_graph_outcome_unit_fields(
    store: CoreJSONArtifactStore,
    request: JointSimulationRequest,
    result: JointSimulationResult,
) -> dict[str, object]:
    """Reopen the selected registry and bind each outcome to its declared slot unit.

    The result's recorded aggregation witness is checked when an aggregation was
    used. A variable name or profile declaration by itself never supplies a unit.
    """
    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    def limited(code: str) -> dict[str, object]:
        return {
            "outcome_units_status": "not_established",
            "outcome_units_limitation_code": code,
        }

    if len(request.engine_plan) != 1 or request.engine_plan[0].engine_kind != "program_graph":
        return limited("generic_n5_outcome_unit_program_graph_not_selected")
    plan = request.engine_plan[0]
    graph_ref = plan.program_graph_ref
    if graph_ref is None or plan.exec_plan_ref is None:
        return limited("generic_n5_outcome_unit_program_graph_not_selected")
    try:
        views = world_model_artifact_views(request.world_model_record)
        selected_graphs = tuple(
            candidate
            for candidate in views.program_graph_refs
            if artifact_ref_identity_key(candidate) == artifact_ref_identity_key(graph_ref)
        )
        if len(selected_graphs) != 1:
            return limited("generic_n5_outcome_unit_graph_view_not_selected")
        registry_ref = views.registry_bundle_ref
        if (
            registry_ref.kind != "core.registry_bundle"
            or registry_ref.media_type != "application/json"
            or registry_ref.manifest_profile_sha256 is None
        ):
            return limited("generic_n5_outcome_unit_registry_view_not_selected")
        registries = load_registry_bundle_content(store, registry_ref)
        if plan.slot_registry != registries.slot_registry:
            return limited("generic_n5_outcome_unit_slot_registry_mismatch")
        units_registry = registries.units_registry
        if units_registry is None:
            return limited("generic_n5_outcome_unit_units_registry_missing")
        if tuple(result.selected_outcomes) != tuple(request.selected_outcomes):
            return limited("generic_n5_outcome_unit_result_scope_mismatch")

        outcome_units: dict[str, str] = {}
        for outcome in request.selected_outcomes:
            state_path = plan.variable_map.get(outcome, outcome)
            slots = tuple(
                slot
                for slot in registries.slot_registry.slots.values()
                if slot.state_path == state_path
            )
            if len(slots) != 1:
                return limited("generic_n5_outcome_unit_slot_not_unique")
            (slot,) = slots
            unit_id = None if slot.unit is None else slot.unit.unit_id
            policy_slots = tuple(
                binding
                for binding in request.world_model_record.policy_slot_map
                if binding.state_path == state_path
            )
            if (
                unit_id is None
                or unit_id not in units_registry.units
                or len(policy_slots) != 1
                or policy_slots[0].slot_id != slot.slot_id
                or policy_slots[0].unit != unit_id
            ):
                return limited("generic_n5_outcome_unit_policy_binding_mismatch")
            aggregation = plan.outcome_aggregations.get(outcome)
            if aggregation is not None:
                if aggregation.unit != unit_id:
                    return limited("generic_n5_outcome_unit_aggregation_mismatch")
                if not _result_records_selected_outcome_unit(
                    result,
                    outcome=outcome,
                    unit_id=unit_id,
                    slot_id=str(slot.slot_id),
                ):
                    return limited("generic_n5_outcome_unit_execution_witness_missing")
            outcome_units[outcome] = unit_id
        if set(outcome_units) != set(request.selected_outcomes):
            return limited("generic_n5_outcome_unit_denominator_mismatch")
        return {
            "outcome_units": outcome_units,
            "outcome_units_status": "resolved",
            "outcome_unit_registry_ref": registry_ref,
        }
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        code = getattr(exc, "code", None)
        return limited(
            code if isinstance(code, str) else "generic_n5_outcome_unit_source_not_established"
        )


def _result_records_selected_outcome_unit(
    result: JointSimulationResult,
    *,
    outcome: str,
    unit_id: str,
    slot_id: str,
) -> bool:
    """Require every retained aggregation row to match the selected slot unit."""
    states_seen = 0
    for trajectory in result.trajectories:
        for point in trajectory.points:
            engine_state = point.engine_state
            replicated_states = engine_state.get("replication_engine_states")
            states = replicated_states if isinstance(replicated_states, list) else [engine_state]
            for state in states:
                if not isinstance(state, dict):
                    return False
                aggregation_basis = state.get("outcome_aggregation_basis")
                basis = (
                    aggregation_basis.get(outcome) if isinstance(aggregation_basis, dict) else None
                )
                if (
                    not isinstance(basis, dict)
                    or basis.get("unit") != unit_id
                    or basis.get("unit_binding_status") != "matched_producer_slot"
                    or basis.get("unit_slot_id") != slot_id
                ):
                    return False
                states_seen += 1
    return states_seen > 0


def n5_declared_candidate_units(
    source: N4CandidateScenarioSourceRecordV3, result: JointSimulationResult
) -> dict[str, object]:
    """Project units from the actual selected declaration already reopened by N5."""
    declaration = source.model_declaration
    if set(result.selected_outcomes) != {declaration.outcome_variable}:
        raise ValueError("candidate_n5_public_outcome_unit_binding_mismatch")
    return {
        "outcome_units": {declaration.outcome_variable: declaration.outcome_unit_id},
        "unit_provenance": "declared_candidate_model",
        "model_declaration_ref": source.model_declaration_ref,
    }
