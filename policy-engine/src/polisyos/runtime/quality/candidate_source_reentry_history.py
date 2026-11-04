"""Replay candidate-source re-entry through immutable producer-owned inputs.

This is the historical reader for the acquisition bridge's candidate outcome.
It does not acquire a lease, resolve the current route, write artifacts, or
establish source currentness. The route fold separately supplies the prior run
to ``validate_candidate_source_continuation`` for append-only history checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from polisyos.core import artifacts, canon
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRoutePhaseReceipt
    from polisyos.runtime.quality.acquisition_world_growth import (
        CandidateAcquisitionWorldCheckpoint,
        CandidateAcquisitionWorldIntent,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationScenarioProfile
    from polisyos.runtime.quality.cycle_substrate import AcquiredCandidateContextPreparation
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceBasisTransition,
        CandidateSourceReentryReceipt,
        GenerationCycleRecord,
    )
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.world_model_record import WorldModelRecord

_PRODUCER = "polisyos.runtime.acquisition_world_growth"
_REENTRY_KIND = "runtime_quality.candidate_source_reentry_receipt"
_INTENT_KIND = "runtime_quality.acquisition_candidate_world_intent"
_CHECKPOINT_KIND = "runtime_quality.acquisition_candidate_world_checkpoint"


@dataclass(frozen=True)
class _Scope:
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    action_job_id: str
    route_id: str
    action_generation: int


def _selected_payload(
    store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef, *, kind: str
) -> object:
    if (
        type(ref) is not artifacts.ArtifactRef
        or ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        or not store.verify(ref).ok
        or artifacts.profile_bound_ref(store, ref) != ref
    ):
        raise ValueError("candidate_reentry_history_selected_profile_invalid")
    return artifacts.load_core_json_artifact(store, ref)


def _owner_record[RecordT: BaseModel](
    *,
    store: artifacts.ArtifactStore,
    events: RuntimeDiagnosticEventLog,
    ref: artifacts.ArtifactRef,
    record_type: type[RecordT],
    kind: str,
    schema: str,
    version: str,
    phase: str,
    event_id: str,
    inputs: Sequence[artifacts.InputRef],
    compiled_ref: str,
    scope: _Scope,
) -> RecordT:
    record = record_type.model_validate(_selected_payload(store, ref, kind=kind))
    manifest = store.get_manifest(ref)
    closure = manifest.same_input_closure
    expected_refs = tuple(
        dict.fromkeys((compiled_ref, *(str(item.artifact_id) for item in inputs)))
    )
    if (
        manifest.artifact_schema != artifacts.SchemaInfo(name=schema, version=version)
        or manifest.producer != artifacts.ProducerInfo(component=_PRODUCER, version="1.0")
        or manifest.inputs != list(inputs)
        or manifest.tenant_context is None
        or manifest.tenant_context.tenant_id != scope.tenant_id
        or manifest.tenant_context.cell_id != scope.cell_id
        or closure is None
        or closure.status != "closed"
        or closure.closure_id != str(ref.artifact_id).removeprefix("sha256:")
        or closure.tenant_id != scope.tenant_id
        or closure.cell_id != scope.cell_id
        or closure.run_id != scope.run_id
        or closure.job_id != scope.source_job_id
        or closure.closure_sha256 != scope.route_id
        or tuple(closure.evidence_input_refs) != expected_refs
    ):
        raise ValueError("candidate_reentry_history_owner_profile_mismatch")
    report = reconcile_authority_ref(
        artifact_store=store,
        event_log=events,
        cas_ref=ref,
        expected_tenant_id=scope.tenant_id,
        expected_cell_id=scope.cell_id,
        expected_run_id=scope.run_id,
        expected_job_id=scope.source_job_id,
    )
    rows = events.list_events(event_id=event_id, limit=2)
    if report.durable_event_id != event_id or len(rows) != 1:
        raise ValueError("candidate_reentry_history_owner_event_missing")
    event = rows[0].event
    if (
        event.event_source != _PRODUCER
        or event.event_type != "polisyos.runtime.diagnostic.producer_execution.v1"
        or event.producer_component != _PRODUCER
        or event.producer_version != "1.0"
        or event.phase != phase
        or event.state_after != phase
        or event.tenant_id != scope.tenant_id
        or event.cell_id != scope.cell_id
        or event.run_id != scope.run_id
        or event.job_id != scope.source_job_id
        or str(ref.artifact_id) not in event.artifact_refs
    ):
        raise ValueError("candidate_reentry_history_owner_event_mismatch")
    return record


def _same_view(
    store: artifacts.ArtifactStore,
    owner_ref: artifacts.ArtifactRef,
    selected_ref: artifacts.ArtifactRef,
) -> bool:
    return (
        owner_ref.artifact_id == selected_ref.artifact_id
        and owner_ref.kind == selected_ref.kind
        and owner_ref.media_type == selected_ref.media_type
        and artifacts.artifact_ref_identity_key(artifacts.profile_bound_ref(store, owner_ref))
        == artifacts.artifact_ref_identity_key(artifacts.profile_bound_ref(store, selected_ref))
    )


def _require_world_creation_time(world: WorldModelRecord) -> None:
    """Check the selected producer clock without replacing its stored value."""
    try:
        created_at = datetime.fromisoformat(world.created_at)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_reentry_history_world_created_at_invalid") from exc
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("candidate_reentry_history_world_created_at_invalid")


def _retained_world_values(world: WorldModelRecord) -> dict[str, object]:
    """Project the base fields which the acquired-world producer retains."""
    return world.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "created_at",
            "world_model_record_id",
            "content_hash",
            "producer_ref",
            "authority_status",
            "valid_time_scope",
            "tx_time_scope",
            "fabric_world_ref",
            "data_forge_binding_ref",
            "simulation_model_ref",
            "foundry_binding_ref",
            "limitations",
            "artifact_views",
            "substrate_registry_ref",
        },
    )


def _world_and_profile(
    *,
    store: artifacts.ArtifactStore,
    receipt: CandidateSourceBasisTransition,
    action: CandidateAcquisitionActionReceipt,
    source: CandidateAcquisitionSource,
    intent: CandidateAcquisitionWorldIntent,
    checkpoint: CandidateAcquisitionWorldCheckpoint,
    problem: DesignProblem,
) -> tuple[
    WorldModelRecord, CandidateSimulationScenarioProfile, AcquiredCandidateContextPreparation
]:
    from polisyos.core.contracts import (
        CandidateAcquisitionSourceDataSnapshotLineage,
        DataSnapshot,
    )
    from polisyos.foundry.data_plane import (
        load_input_bindings,
        prepare_input_bindings,
        prepare_json_input_binding_values,
    )
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )
    from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage
    from polisyos.runtime.quality.data_state_substrate import (
        CandidateAcquisitionSourceSlotBinding,
        _candidate_acquisition_snapshot_values,
        _prepare_acquired_observation_world,
        _require_candidate_acquisition_world_scope,
        _verify_actual_acquired_native_world,
    )
    from polisyos.runtime.quality.world_model_record import (
        _prepare_world_simulation_model_ref,
        load_world_model_record,
        read_world_model_record_owner_values,
        world_model_artifact_views,
    )

    configured = intent.configured_profile
    base = configured.context_inputs.world_model_record
    base_views = world_model_artifact_views(base)
    binding = CandidateAcquisitionSourceSlotBinding(
        profile_selection_ref=action.profile_selection_ref,
        candidate_digest=action.candidate_digest,
        canonical_variable_id=action.canonical_variable_id,
        target_slot_id=action.target_slot_id,
    )
    _require_candidate_acquisition_world_scope(
        problem=problem, base=base, binding=binding, source=source
    )
    if (
        configured.profile_selection_ref != action.profile_selection_ref
        or checkpoint.base_data_snapshot_ref != base_views.data_snapshot_ref
    ):
        raise ValueError("candidate_reentry_history_configured_basis_mismatch")
    read_world_model_record_owner_values(
        store,
        world_model_record=base,
        registry_bundle_ref=base_views.registry_bundle_ref,
        substrate_registry=configured.context_inputs.substrate_registry,
    )
    world = load_world_model_record(store, receipt.world_model_ref)
    _require_world_creation_time(world)
    views = world_model_artifact_views(world)
    snapshot = DataSnapshot.model_validate(
        _selected_payload(store, receipt.data_snapshot_ref, kind="fabric.data_snapshot")
    )
    actual = read_world_model_record_owner_values(
        store,
        world_model_record=world,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=configured.context_inputs.substrate_registry,
    )
    lineage = validate_data_snapshot_owner_lineage(
        store,
        receipt.data_snapshot_ref,
        snapshot,
        candidate_only=True,
        binding_lineage_refs=actual.data_forge_binding.lineage_refs,
    )
    payload, _stats, _notes, rule = _candidate_acquisition_snapshot_values(
        store,
        base_data_snapshot_ref=base_views.data_snapshot_ref,
        candidate_source_ref=receipt.candidate_source_ref,
        slot_binding=binding,
        transaction_time=intent.transaction_time,
    )
    prior_bindings = load_input_bindings(store, base_views.input_bindings_ref)
    rules = tuple(
        item for item in prior_bindings.rules if item.target_slot_id != rule.target_slot_id
    )
    rules = (*rules, rule)
    prospective = prepare_json_input_binding_values(
        store,
        payload_json=json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"),
        registry_bundle_ref=base_views.registry_bundle_ref,
        rules=rules,
    )
    bindings = load_input_bindings(store, views.input_bindings_ref)
    if any(
        not _same_view(store, getattr(bindings, field), getattr(views, field))
        for field in ("data_snapshot_ref", "registry_bundle_ref", "bound_state_snapshot_ref")
    ):
        raise ValueError("candidate_reentry_history_binding_source_mismatch")
    replayed = prepare_input_bindings(
        store,
        data_snapshot_ref=views.data_snapshot_ref,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=list(bindings.rules),
        registered_sql_admission_ref=bindings.registered_sql_admission_ref,
    )
    state = load_state_snapshot(store, snapshot_ref=views.bound_state_snapshot_ref)
    if (
        replayed.effective_rules != prospective.effective_rules
        or replayed.applied_binding_ids != prospective.applied_binding_ids
        or replayed.warnings != prospective.warnings
        or state_snapshot_value_projection(state)
        != state_snapshot_value_projection(prospective.materialized_state)
        or state_snapshot_value_projection(replayed.materialized_state)
        != state_snapshot_value_projection(state)
    ):
        raise ValueError("candidate_reentry_history_state_rule_mismatch")
    plan = _prepare_acquired_observation_world(
        store,
        base_world_model_record=base,
        acquired_rule=rule,
        registry_bundle_ref=base_views.registry_bundle_ref,
        substrate_registry=configured.context_inputs.substrate_registry,
    )
    expected_model = plan.materialized_model(receipt.data_snapshot_ref)
    expected_simulation = _prepare_world_simulation_model_ref(
        model_spec=expected_model,
        model_spec_ref=views.model_spec_ref,
        registry_bundle_ref=base_views.registry_bundle_ref,
        mechanism_refs=base.simulation_model_ref.mechanism_refs,
        gcm_refs=base.simulation_model_ref.gcm_refs,
        ncm_refs=base.simulation_model_ref.ncm_refs,
        program_graph_refs=base.simulation_model_ref.program_graph_refs,
    )
    tx_time = intent.transaction_time.astimezone(UTC).isoformat()
    if (
        _retained_world_values(world) != _retained_world_values(base)
        or world.content_hash != receipt.world_model_content_hash
        or world.producer_ref
        != "polisyos.runtime.quality.data_state_substrate.build_candidate_acquisition_world"
        or world.authority_status != "limited"
        or world.valid_time_scope != "not_established"
        or world.tx_time_scope != tx_time
        or views.data_snapshot_ref != receipt.data_snapshot_ref
        or views.registry_bundle_ref != base_views.registry_bundle_ref
        or views.program_graph_refs != base_views.program_graph_refs
        or views.ncm_refs != base_views.ncm_refs
        or actual.model_spec != expected_model
        or world.simulation_model_ref != expected_simulation
        or world.fabric_world_ref.snapshot_id != snapshot.stats.get("snapshot_id")
        or world.fabric_world_ref.as_of_valid_time != base.fabric_world_ref.as_of_valid_time
        or world.fabric_world_ref.world_query_policy != base.fabric_world_ref.world_query_policy
        or world.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
        != base.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
        or not isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        or snapshot.source_lineage.base_data_snapshot_ref != base_views.data_snapshot_ref
        or snapshot.source_lineage.candidate_source_ref != receipt.candidate_source_ref
        or snapshot.stats.get("materialized_at_transaction_time") != tx_time
        or world.limitations.model_dump(exclude={"admissibility_blockers"})
        != plan.limitations.model_dump(exclude={"admissibility_blockers"})
        or not (
            set(plan.limitations.admissibility_blockers)
            | set(source.limitations)
            | set(lineage.required_admissibility_blockers)
        ).issubset(world.limitations.admissibility_blockers)
    ):
        raise ValueError("candidate_reentry_history_world_recipe_mismatch")
    _verify_actual_acquired_native_world(world, str(snapshot.data_ref.artifact_id), tx_time)
    owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(configured,), model_declarations=(intent.original_model_declaration,), store=store
    )
    prepared = owner.prepare_context_for_acquired_world(
        problem=problem,
        profile_selection_ref=action.profile_selection_ref,
        world_model_record=world,
        job_id=action.action_job_id,
        run_id=action.run_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
    )
    return world, prepared.profile, prepared


def _require_n4_origin(
    *,
    actual_origin_ref: artifacts.ArtifactRef | None,
    prior_source_ref: artifacts.ArtifactRef,
    prior_origin_ref: artifacts.ArtifactRef | None,
) -> None:
    """Keep the source owner's flattened root lineage and exact selected view."""
    if actual_origin_ref != (prior_origin_ref or prior_source_ref):
        raise ValueError("candidate_reentry_history_n4_origin_mismatch")


def _verify_n5(
    *,
    store: artifacts.ArtifactStore,
    receipt: CandidateSourceBasisTransition,
    target_cycle: GenerationCycleRecord,
    prior_origin_ref: artifacts.ArtifactRef | None,
    profile: CandidateSimulationScenarioProfile,
    problem: DesignProblem,
) -> None:
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _candidate_simulation_selected_n4_source_ref,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.n5_execution_basis import (
        exact_n5_content_bytes,
        read_n5_execution_implementation_witness,
    )

    repository = GenerationSourceRepository(store)
    expected = {
        "expected_run_id": receipt.run_id,
        "expected_job_id": receipt.action_job_id,
        "expected_tenant_id": receipt.tenant_id,
        "expected_cell_id": receipt.cell_id,
    }
    simulation = target_cycle.simulation
    source_ref = _candidate_simulation_selected_n4_source_ref(simulation)
    if source_ref != receipt.n4_source_ref:
        raise ValueError("candidate_reentry_history_n4_transition_mismatch")
    if source_ref is not None:
        _selected_payload(store, source_ref, kind="runtime.quality.n4_candidate_scenario_source")
        source = repository.load_candidate_scenario_source_for_reissue(
            source_ref,
            expected_run_id=receipt.run_id,
            expected_tenant_id=receipt.tenant_id,
            expected_cell_id=receipt.cell_id,
            expected_candidate_id=receipt.source_candidate_ref,
            expected_candidate_content_hash=target_cycle.selected_candidate_content_hash,
            expected_world_content_hash=receipt.scenario_world_model_content_hash,
            expected_context_job_ref=receipt.context_job_ref,
        )
        if (
            source.problem != problem
            or source.job_id != receipt.action_job_id
            or source.stable_subject_ref != target_cycle.design_problem_ref
            or exact_n5_content_bytes(source.profile) != exact_n5_content_bytes(profile)
        ):
            raise ValueError("candidate_reentry_history_n4_problem_mismatch")
        _require_n4_origin(
            actual_origin_ref=source.origin_source_ref,
            prior_source_ref=receipt.prior_n4_source_ref,
            prior_origin_ref=prior_origin_ref,
        )
    if any(
        ref is not None and ref != receipt.context_job_ref
        for ref in (
            simulation.candidate_simulation_context_job_ref,
            simulation.cycle_substrate_context_job_ref,
        )
    ) or any(
        value is not None and value != receipt.scenario_world_model_content_hash
        for value in (simulation.k_world_ref_before, simulation.k_world_ref_after)
    ):
        raise ValueError("candidate_reentry_history_n4_context_mismatch")
    input_record = None
    if receipt.n5_input_ref is not None:
        input_record = repository.resolve_candidate_simulation_v5(
            ref=receipt.n5_input_ref, **expected
        )
        if type(input_record) is not CandidateSimulationN5InputV5 or (
            input_record.context_job_ref != receipt.context_job_ref
            or input_record.model_declaration_ref != receipt.model_declaration_ref
            or input_record.ncm_ref != receipt.ncm_ref
            or input_record.original_candidate_id != receipt.source_candidate_ref
            or input_record.original_candidate_hash != target_cycle.selected_candidate_content_hash
            or input_record.materialization.world_model_record_hash
            != receipt.scenario_world_model_content_hash
            or exact_n5_content_bytes(input_record.profile) != exact_n5_content_bytes(profile)
            or input_record.n4_source_ref != source_ref
        ):
            raise ValueError("candidate_reentry_history_n5_input_mismatch")
    execution = None
    if receipt.n5_execution_ref is not None:
        execution = repository.resolve_candidate_simulation_v5(
            ref=receipt.n5_execution_ref, **expected
        )
        if (
            type(execution) is not CandidateSimulationExecutionV5
            or input_record is None
            or (
                execution.n5_input_ref != receipt.n5_input_ref
                or execution.n5_result_ref != receipt.n5_result_ref
                or execution.context_job_ref != receipt.context_job_ref
                or execution.model_declaration_ref != receipt.model_declaration_ref
                or execution.ncm_ref != receipt.ncm_ref
                or execution.original_candidate_id != receipt.source_candidate_ref
                or execution.original_candidate_hash != target_cycle.selected_candidate_content_hash
                or execution.world_model_record_hash != receipt.scenario_world_model_content_hash
            )
        ):
            raise ValueError("candidate_reentry_history_n5_execution_mismatch")
    if receipt.n5_result_ref is not None:
        if input_record is None:
            raise ValueError("candidate_reentry_history_n5_result_input_missing")
        result = load_joint_simulation_result(
            receipt.n5_result_ref,
            store=store,
            expected_world_model_record_content_hash=receipt.scenario_world_model_content_hash,
            expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
            expected_selected_outcomes=(input_record.outcome_variable,),
            expected_receipt_payload_hash=(
                execution.n5_result_content_hash
                if execution is not None
                else simulation.simulation_ref or ""
            ),
        )
        if execution is not None:
            read_n5_execution_implementation_witness(result, input_ref=receipt.n5_input_ref)
    if simulation.status == "joint_simulated" and execution is None:
        raise ValueError("candidate_reentry_history_n5_completion_unwitnessed")


def _read_historical_action(
    *,
    store: artifacts.ArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    action_ref: artifacts.ArtifactRef,
) -> tuple[CandidateAcquisitionActionReceipt, AcquisitionRoutePhaseReceipt]:
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRoutePhaseReceipt
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
        read_candidate_acquisition_action_historical,
    )

    # These parses select the immutable phase only. Neither becomes an owner
    # fact until the canonical action reader verifies both selected records.
    selected = CandidateAcquisitionActionReceipt.model_validate(
        _selected_payload(
            store, action_ref, kind="runtime_quality.acquisition_candidate_action_receipt"
        )
    )
    executing = AcquisitionRoutePhaseReceipt.model_validate(
        _selected_payload(
            store,
            selected.selected_action_phase_ref,
            kind="runtime_quality.acquisition_route_phase_receipt",
        )
    )
    action = read_candidate_acquisition_action_historical(
        artifact_store=store,
        event_log=event_log,
        receipt_ref=action_ref,
        executing_phase=executing,
        executing_phase_ref=str(selected.selected_action_phase_ref.artifact_id),
    )
    return action, executing


def _scope_from_action(action: CandidateAcquisitionActionReceipt) -> _Scope:
    return _Scope(**{name: getattr(action, name) for name in _Scope.__dataclass_fields__})


def _verify_prior_basis(
    *,
    store: artifacts.ArtifactStore,
    control_store: ControlPlaneStore,
    transition: CandidateSourceBasisTransition,
    source_cycle: GenerationCycleRecord,
    target_cycle: GenerationCycleRecord,
    problem: DesignProblem,
    action: CandidateAcquisitionActionReceipt,
    intent: CandidateAcquisitionWorldIntent,
) -> N4CandidateScenarioSourceRecordV3:
    from polisyos.runtime.quality.acquisition_world_growth import resolve_first_candidate_n4_prior
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

    repository = GenerationSourceRepository(store)
    prior_source = repository.load_candidate_scenario_source_for_reissue(
        transition.prior_n4_source_ref,
        expected_run_id=transition.run_id,
        expected_tenant_id=transition.tenant_id,
        expected_cell_id=transition.cell_id,
        expected_candidate_id=transition.source_candidate_ref,
        expected_candidate_content_hash=transition.source_candidate_content_hash,
        expected_world_content_hash=transition.prior_scenario_world_model_hash,
        expected_context_job_ref=transition.prior_context_job_ref,
    )
    if transition.prior_n5_input_ref is None:
        # The shared acquisition owner admits only its exact recorded N6
        # before-N5 branch. Missing input bytes alone never establish no call.
        first_source = resolve_first_candidate_n4_prior(
            artifact_store=store,
            source_cycle=source_cycle,
            problem=problem,
            tenant_id=transition.tenant_id,
            cell_id=transition.cell_id,
            run_id=transition.run_id,
            source_job_id=action.source_job_id,
            design_problem_ref=target_cycle.design_problem_ref,
        )
        if exact_n5_content_bytes(first_source) != exact_n5_content_bytes(prior_source):
            raise ValueError("candidate_reentry_history_first_source_mismatch")
    else:
        prior_input = repository.resolve_candidate_simulation_v5(
            ref=transition.prior_n5_input_ref,
            expected_run_id=transition.run_id,
            expected_job_id=prior_source.job_id,
            expected_tenant_id=transition.tenant_id,
            expected_cell_id=transition.cell_id,
        )
        if (
            type(prior_input) is not CandidateSimulationN5InputV5
            or prior_input.n4_source_ref != transition.prior_n4_source_ref
            or prior_input.context_job_ref != transition.prior_context_job_ref
            or prior_input.original_candidate_id != transition.source_candidate_ref
            or prior_input.original_candidate_hash != transition.source_candidate_content_hash
            or prior_input.materialization.world_model_record_hash
            != transition.prior_scenario_world_model_hash
        ):
            raise ValueError("candidate_reentry_history_prior_input_mismatch")
    if (
        prior_source.problem != problem
        or prior_source.stable_subject_ref != target_cycle.design_problem_ref
        or prior_source.profile_selection_ref != action.profile_selection_ref
        or exact_n5_content_bytes(prior_source.profile)
        != exact_n5_content_bytes(intent.configured_profile)
        or exact_n5_content_bytes(prior_source.model_declaration)
        != exact_n5_content_bytes(intent.original_model_declaration)
    ):
        raise ValueError("candidate_reentry_history_prior_basis_mismatch")
    prior_context = CycleSubstrateContextArtifactOwner(
        store=store, control_store=control_store
    ).resolve_historical_job_artifact(
        transition.prior_context_job_ref,
        problem=problem,
        expected_design_problem_ref=transition.design_problem_basis_ref,
        expected_job_id=prior_source.job_id,
        expected_run_id=transition.run_id,
        expected_tenant_id=transition.tenant_id,
        expected_cell_id=transition.cell_id,
    )
    if (
        prior_context.context.world_model_record.content_hash
        != transition.prior_scenario_world_model_hash
        or (
            transition.prior_context_job_ref.manifest_profile_sha256 is None
            and "historical_context_profile_selection_not_established" not in transition.limitations
        )
    ):
        raise ValueError("candidate_reentry_history_prior_context_mismatch")
    return prior_source


def verify_candidate_source_basis_transition_historical(
    *,
    store: artifacts.ArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    transition: CandidateSourceBasisTransition,
    source_cycle: GenerationCycleRecord,
    target_cycle: GenerationCycleRecord,
    problem: DesignProblem,
) -> None:
    """Reopen the selected owner basis of one declared candidate-only edge.

    This also runs before the outer re-entry receipt exists. The selected
    action supplies its historical source-job and action-generation scope;
    its immutable phase is verified by the canonical action owner. Full-run
    append-only reconciliation remains the route fold's responsibility.

    Args:
        store: Tenant-authorized artifact reader for every selected parent.
        event_log: Immutable producer event history.
        control_store: Historical context owner's dependency; no lease is read.
        transition: Intrinsic edge declaring exact selected producer inputs.
        source_cycle: Actual occurrence immediately before this acquisition.
        target_cycle: Actual occurrence produced from the selected candidate world.
        problem: The unchanged concrete problem basis of both occurrences.

    Raises:
        ValueError: The edge, selected producer chain, or limitations fail replay.
    """
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        CandidateAcquisitionWorldCheckpoint,
        CandidateAcquisitionWorldIntent,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        build_cycle_substrate_context,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceBasisTransition,
        GenerationCycleRecord,
        candidate_source_basis_cycle_pair_matches,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
    from polisyos.runtime.quality.world_model_record import (
        derive_candidate_scenario_world_model_record,
        world_model_artifact_views,
    )

    if (
        type(transition) is not CandidateSourceBasisTransition
        or type(source_cycle) is not GenerationCycleRecord
        or type(target_cycle) is not GenerationCycleRecord
        or type(problem) is not DesignProblem
    ):
        raise ValueError("candidate_reentry_history_cycle_pair_mismatch")
    # Reopen intrinsic values too; callers may hold mutable nested DTOs.
    transition = CandidateSourceBasisTransition.model_validate(transition.model_dump(mode="python"))
    source_cycle = GenerationCycleRecord.model_validate(source_cycle.model_dump(mode="python"))
    target_cycle = GenerationCycleRecord.model_validate(target_cycle.model_dump(mode="python"))
    problem = DesignProblem.model_validate(problem.model_dump(mode="python"))
    if not candidate_source_basis_cycle_pair_matches(
        transition=transition, source_cycle=source_cycle, target_cycle=target_cycle
    ) or transition.design_problem_basis_ref != gy_content_hash(problem.model_dump(mode="json")):
        raise ValueError("candidate_reentry_history_cycle_pair_mismatch")
    action, executing = _read_historical_action(
        store=store, event_log=event_log, action_ref=transition.candidate_action_ref
    )
    scope = _scope_from_action(action)
    if action.candidate_source_ref != transition.candidate_source_ref or any(
        getattr(transition, name) != getattr(scope, name)
        for name in ("tenant_id", "cell_id", "run_id", "action_job_id", "route_id")
    ):
        raise ValueError("candidate_reentry_history_source_action_mismatch")
    identity = hashlib.sha256(
        canon.to_canonical_bytes(transition.candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    intent = _owner_record(
        store=store,
        events=event_log,
        ref=transition.candidate_world_intent_ref,
        record_type=CandidateAcquisitionWorldIntent,
        kind=_INTENT_KIND,
        schema="polisyos.runtime.CandidateAcquisitionWorldIntent",
        version="1.2",
        phase="candidate_world_materialization_started",
        event_id="evt_candidate_world_intent_" + identity,
        inputs=(
            artifacts.input_ref_from_artifact_ref(
                transition.candidate_action_ref, role="candidate_acquisition_action"
            ),
        ),
        compiled_ref=executing.compiled_ref,
        scope=scope,
    )
    raw_checkpoint = CandidateAcquisitionWorldCheckpoint.model_validate(
        _selected_payload(store, transition.candidate_world_checkpoint_ref, kind=_CHECKPOINT_KIND)
    )
    checkpoint = _owner_record(
        store=store,
        events=event_log,
        ref=transition.candidate_world_checkpoint_ref,
        record_type=CandidateAcquisitionWorldCheckpoint,
        kind=_CHECKPOINT_KIND,
        schema="polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
        version="1.1",
        phase="candidate_world_prepared",
        event_id="evt_candidate_world_checkpoint_" + identity,
        inputs=AcquisitionWorldGrowthBridge._candidate_world_checkpoint_inputs(raw_checkpoint),
        compiled_ref=executing.compiled_ref,
        scope=scope,
    )
    for record in (intent, checkpoint):
        if (
            record.candidate_action_ref != transition.candidate_action_ref
            or record.action_phase_ref != action.action_phase_ref
            or any(
                getattr(record, name) != getattr(scope, name)
                for name in ("tenant_id", "cell_id", "run_id", "action_job_id", "route_id")
            )
        ):
            raise ValueError("candidate_reentry_history_world_action_mismatch")
    if (
        checkpoint.intent_ref != transition.candidate_world_intent_ref
        or checkpoint.candidate_source_ref != transition.candidate_source_ref
        or checkpoint.data_snapshot_ref != transition.data_snapshot_ref
        or checkpoint.world_model_ref != transition.world_model_ref
        or checkpoint.transaction_time != intent.transaction_time
    ):
        raise ValueError("candidate_reentry_history_checkpoint_mismatch")
    prior_source = _verify_prior_basis(
        store=store,
        control_store=control_store,
        transition=transition,
        source_cycle=source_cycle,
        target_cycle=target_cycle,
        problem=problem,
        action=action,
        intent=intent,
    )
    source = read_candidate_acquisition_source(store, source_ref=transition.candidate_source_ref)
    context_job = CycleSubstrateContextArtifactOwner(
        store=store, control_store=control_store
    ).resolve_historical_job_artifact(
        transition.context_job_ref,
        problem=problem,
        expected_design_problem_ref=transition.design_problem_basis_ref,
        expected_job_id=scope.action_job_id,
        expected_run_id=scope.run_id,
        expected_tenant_id=scope.tenant_id,
        expected_cell_id=scope.cell_id,
    )
    world, profile, prepared = _world_and_profile(
        store=store,
        receipt=transition,
        action=action,
        source=source,
        intent=intent,
        checkpoint=checkpoint,
        problem=problem,
    )
    declaration, _ncm = GenerationSourceRepository(store).load_candidate_declared_ncm(
        declaration_ref=transition.model_declaration_ref,
        ncm_ref=transition.ncm_ref,
        expected_profile=profile,
        expected_run_id=scope.run_id,
        expected_job_id=scope.action_job_id,
        expected_tenant_id=scope.tenant_id,
        expected_cell_id=scope.cell_id,
    )
    if exact_n5_content_bytes(declaration) != exact_n5_content_bytes(prepared.model_declaration):
        raise ValueError("candidate_reentry_history_declaration_mismatch")
    registry_ref = world_model_artifact_views(
        context_job.context.world_model_record
    ).substrate_registry_ref
    scenario_world = derive_candidate_scenario_world_model_record(
        world,
        ncm_artifact_ref=transition.ncm_ref,
        declaration_content_hash=declaration.content_hash,
        substrate_registry_view_ref=registry_ref,
    )
    inputs = prepared.source_context_inputs
    denial_set = set(action.limitations) | set(world.limitations.admissibility_blockers)
    if transition.prior_context_job_ref.manifest_profile_sha256 is None:
        denial_set.add("historical_context_profile_selection_not_established")
    denials = tuple(sorted(denial_set))
    context = build_cycle_substrate_context(
        design_problem_ref=transition.design_problem_basis_ref,
        domain=problem.domain,
        substrate_registry=inputs.substrate_registry,
        selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
        world_model_record=scenario_world,
        intervention_substrate=inputs.intervention_substrate,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=inputs.source_pack_content_hash,
        substrate_input_content_hash=inputs.substrate_input_content_hash,
        additional_authority_denials=denials,
    )
    if (
        exact_n5_content_bytes(context_job.context) != exact_n5_content_bytes(context)
        or context.world_model_record.content_hash != transition.scenario_world_model_content_hash
        or not (set(denials) | set(context.may_not_use_for)).issubset(transition.limitations)
        or "candidate_only" not in transition.limitations
    ):
        raise ValueError("candidate_reentry_history_context_or_limitations_mismatch")
    _verify_n5(
        store=store,
        receipt=transition,
        target_cycle=target_cycle,
        prior_origin_ref=prior_source.origin_source_ref,
        profile=profile,
        problem=problem,
    )


def verify_candidate_source_reentry_history(
    *,
    artifact_store: artifacts.ArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    receipt_ref: artifacts.ArtifactRef,
    expected_tenant_id: str,
    expected_cell_id: str,
    expected_run_id: str,
    expected_source_job_id: str,
    expected_action_job_id: str,
    expected_route_id: str,
    expected_action_generation: int,
    expected_selected_action_ref: artifacts.ArtifactRef,
) -> CandidateSourceReentryReceipt:
    """Verify one selected candidate outcome without the historical worker lease.

    Args:
        artifact_store: Tenant-authorized reader for the selected artifact views.
        event_log: Runtime diagnostic history owning the immutable producer events.
        control_store: Context owner dependency; no current job or route is read.
        receipt_ref: Exact selected candidate re-entry receipt from the terminal.
        expected_tenant_id: Tenant already bound by the caller's action chain.
        expected_cell_id: Cell already bound by the caller's action chain.
        expected_run_id: Control run bound by the caller's action chain.
        expected_source_job_id: Completed NL source job, also the producer event job.
        expected_action_job_id: Acquisition job that produced the context and N5.
        expected_route_id: Immutable compiler/planner route identity.
        expected_action_generation: Selected protected action generation.
        expected_selected_action_ref: Exact candidate-action receipt selected by the terminal.

    Returns:
        The owner-replayed candidate receipt, with all recorded limitations.

    Raises:
        ValueError: A selected artifact, producer relation, or semantic input is invalid.
    """
    from polisyos.runtime.quality.acquisition_world_growth import candidate_source_reentry_inputs
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceReentryReceipt,
        validate_generation_cycle_run_history,
    )

    scope = _Scope(
        expected_tenant_id,
        expected_cell_id,
        expected_run_id,
        expected_source_job_id,
        expected_action_job_id,
        expected_route_id,
        expected_action_generation,
    )
    if (
        any(
            not value
            for value in (
                scope.tenant_id,
                scope.cell_id,
                scope.run_id,
                scope.source_job_id,
                scope.action_job_id,
                scope.route_id,
            )
        )
        or type(scope.action_generation) is not int
        or scope.action_generation < 1
    ):
        raise ValueError("candidate_reentry_history_expected_scope_invalid")
    receipt = CandidateSourceReentryReceipt.model_validate(
        _selected_payload(artifact_store, receipt_ref, kind=_REENTRY_KIND)
    )
    if receipt.candidate_action_ref != expected_selected_action_ref or any(
        getattr(receipt, name) != getattr(scope, name) for name in _Scope.__dataclass_fields__
    ):
        raise ValueError("candidate_reentry_history_action_scope_mismatch")
    action, executing = _read_historical_action(
        store=artifact_store, event_log=event_log, action_ref=receipt.candidate_action_ref
    )
    if _scope_from_action(action) != scope:
        raise ValueError("candidate_reentry_history_source_action_mismatch")
    identity = hashlib.sha256(
        canon.to_canonical_bytes(receipt.candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    receipt = _owner_record(
        store=artifact_store,
        events=event_log,
        ref=receipt_ref,
        record_type=CandidateSourceReentryReceipt,
        kind=_REENTRY_KIND,
        schema="polisyos.runtime.CandidateSourceReentryReceipt",
        version="1.0",
        phase="candidate_source_reentry_terminal",
        event_id="evt_candidate_source_reentry_" + identity,
        inputs=candidate_source_reentry_inputs(receipt),
        compiled_ref=executing.compiled_ref,
        scope=scope,
    )
    if validate_generation_cycle_run_history(
        receipt.continued_generation_run.model_dump(mode="json")
    ):
        raise ValueError("candidate_reentry_history_continuation_intrinsic_invalid")
    context_job = CycleSubstrateContextArtifactOwner(
        store=artifact_store, control_store=control_store
    ).resolve_historical_job_artifact(
        receipt.context_job_ref,
        expected_design_problem_ref=receipt.design_problem_basis_ref,
        expected_job_id=scope.action_job_id,
        expected_run_id=scope.run_id,
        expected_tenant_id=scope.tenant_id,
        expected_cell_id=scope.cell_id,
    )
    cycles = receipt.continued_generation_run.cycles
    if receipt.source_cycle_index >= len(cycles):
        raise ValueError("candidate_reentry_history_source_cycle_missing")
    verify_candidate_source_basis_transition_historical(
        store=artifact_store,
        event_log=event_log,
        control_store=control_store,
        transition=receipt.basis_transition,
        source_cycle=cycles[receipt.source_cycle_index],
        target_cycle=receipt.new_cycle,
        problem=context_job.problem,
    )
    return receipt
