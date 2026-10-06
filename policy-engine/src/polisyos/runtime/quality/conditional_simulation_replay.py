"""Replay candidate-only N8 values from the selected, persisted N5 evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationExecutionV5,
    CandidateSimulationN5InputV5,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
    CycleSubstrateContextArtifactOwner,
    cycle_job_profile_selection_ref,
)
from polisyos.runtime.quality.design_generation import N4CandidateScenarioProposalCandidate
from polisyos.runtime.quality.generation_cycle import (
    _N8_CANDIDATE_SIMULATION_LIMITATIONS,
    GenerationCycleRecord,
    SimulationPortObservation,
    ValuePortObservation,
    _DefaultSimulationBoundFoundryValuePort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    N4CandidateScenarioSourceRecordV1,
    N4CandidateScenarioSourceRecordV2,
    N4CandidateScenarioSourceRecordV3,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    derive_candidate_scenario_atom,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveGenerationCycleRun,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore


class ConditionalSimulationReplayValue(BaseModel):
    """One freshly recomputed, candidate-limited N8 projection and its basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_source: Literal["recomputed_from_n5_cas", "not_established"] = (
        "recomputed_from_n5_cas"
    )
    cycle_index: int = Field(ge=0)
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str | None = None
    n4_source_ref: ArtifactRef | None = None
    n4_atom_id: str | None = None
    n4_atom_content_hash: str | None = None
    n5_input_ref: ArtifactRef | None = None
    n5_execution_ref: ArtifactRef | None = None
    n5_result_ref: ArtifactRef | None = None
    n5_receipt_payload_hash: str | None = None
    context_job_ref: ArtifactRef | None = None
    profile_config_ref: str | None = None
    profile_content_hash: str | None = None
    profile_selection_ref: str | None = None
    n5_atom_id: str | None = None
    n5_atom_content_hash: str | None = None
    outcome_variable: str | None = None
    world_model_record_id: str | None = None
    world_model_record_content_hash: str | None = None
    selected_engine_kind: str | None = None
    selected_method_fqn: str | None = None
    selected_objective_ref: str | None = None
    trajectory_count: int | None = Field(default=None, ge=0)
    observation: ValuePortObservation


def replay_conditional_simulation_values(
    recursive_run: RecursiveGenerationCycleRun,
    *,
    store: ArtifactStore,
    context_owner: CycleSubstrateContextArtifactOwner,
    admission_owner: ConfiguredCandidateSimulationContextAdmissionOwner | None,
    expected_job_id: str,
    expected_run_id: str,
    expected_tenant_id: str,
    expected_cell_id: str,
) -> tuple[ConditionalSimulationReplayValue, ...]:
    """Recompute selected candidate N8 values from owner-resolved V5 CAS records.

    The existing persisted value-port status is deliberately ignored. This read
    path resolves the immutable N5 input, execution, selected N4 source, and
    historical context artifact again, then calls only the conditional branch
    of the existing simulation-bound N8 value port. It never reruns N5 and does
    not establish N9, S8, empirical grounding, or currentness.
    """

    if type(recursive_run) is not RecursiveGenerationCycleRun:
        return ()
    if not all(
        isinstance(value, str) and value.strip()
        for value in (expected_job_id, expected_run_id, expected_tenant_id, expected_cell_id)
    ):
        return ()
    if recursive_run.run_id != f"recursive:{recursive_run.recursive_graph.graph_id}":
        return ()

    repository = GenerationSourceRepository(store=store)
    replayed: list[ConditionalSimulationReplayValue] = []
    for node in recursive_run.leaf_nodes:
        leaf_run = node.cycle_run
        if leaf_run is None:
            continue
        for cycle in leaf_run.cycles:
            diagnostics = cycle.simulation.diagnostics
            if diagnostics.get("candidate_simulation_purpose") != "candidate_scenario_n5_only":
                continue
            replayed.append(
                _replay_cycle(
                    cycle,
                    diagnostics=diagnostics,
                    repository=repository,
                    store=store,
                    context_owner=context_owner,
                    admission_owner=admission_owner,
                    expected_job_id=expected_job_id,
                    expected_run_id=expected_run_id,
                    expected_tenant_id=expected_tenant_id,
                    expected_cell_id=expected_cell_id,
                )
            )
    return tuple(replayed)


def _replay_cycle(
    cycle: GenerationCycleRecord,
    *,
    diagnostics: Mapping[str, object],
    repository: GenerationSourceRepository,
    store: ArtifactStore,
    context_owner: CycleSubstrateContextArtifactOwner,
    admission_owner: ConfiguredCandidateSimulationContextAdmissionOwner | None,
    expected_job_id: str,
    expected_run_id: str,
    expected_tenant_id: str,
    expected_cell_id: str,
) -> ConditionalSimulationReplayValue:
    candidate_id = cycle.selected_candidate_ref
    value = _blocked(
        cycle,
        candidate_id=candidate_id,
        expected_job_id=expected_job_id,
        expected_run_id=expected_run_id,
        expected_tenant_id=expected_tenant_id,
        expected_cell_id=expected_cell_id,
        code="conditional_simulation_replay_unavailable",
        reason="The persisted N5 candidate basis could not be replayed from its owners.",
    )
    try:
        if not candidate_id.strip():
            raise ValueError("candidate_simulation_selected_candidate_missing")
        input_ref = _selected_artifact_ref(
            diagnostics,
            selected_key="candidate_simulation_n5_input_selected_ref",
            identity_key="candidate_simulation_n5_input_ref",
        )
        execution_ref = _selected_artifact_ref(
            diagnostics,
            selected_key="candidate_simulation_execution_selected_ref",
            identity_key="candidate_simulation_execution_ref",
        )
        source_ref = _selected_artifact_ref(
            diagnostics,
            selected_key="candidate_simulation_n4_source_selected_ref",
            identity_key="candidate_simulation_n4_source_ref",
        )
        context_ref = _selected_artifact_ref(
            diagnostics,
            selected_key="candidate_simulation_context_job_selected_ref",
            identity_key="candidate_simulation_context_job_ref",
        )

        input_record = repository.resolve_candidate_simulation_v5(
            ref=input_ref,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        if type(input_record) is not CandidateSimulationN5InputV5:
            raise ValueError("candidate_simulation_n5_input_v5_required")
        if (
            artifact_ref_identity_key(input_record.n4_source_ref)
            != artifact_ref_identity_key(source_ref)
            or artifact_ref_identity_key(input_record.context_job_ref)
            != artifact_ref_identity_key(context_ref)
            or input_record.original_candidate_id != candidate_id
            or input_record.original_candidate_hash != cycle.selected_candidate_content_hash
            or input_record.original_n4_atom_hash != cycle.selected_candidate_content_hash
            or input_record.profile_config_ref
            != candidate_simulation_profile_ref(input_record.profile)
            or diagnostics.get("candidate_simulation_profile_ref")
            != input_record.profile_config_ref
        ):
            raise ValueError("candidate_simulation_selected_input_cycle_binding_mismatch")

        materialization = input_record.materialization
        value = value.model_copy(
            update={
                "n4_source_ref": source_ref,
                "n5_input_ref": input_ref,
                "n5_result_ref": cycle.simulation.simulation_result_ref,
                "context_job_ref": context_ref,
                "profile_config_ref": input_record.profile_config_ref,
                "profile_content_hash": input_record.profile.content_hash,
                "profile_selection_ref": input_record.profile.profile_selection_ref,
                "n5_atom_id": materialization.derived_n5_atom.intervention_id,
                "n5_atom_content_hash": materialization.derived_n5_atom.content_hash,
                "outcome_variable": input_record.outcome_variable,
                "world_model_record_content_hash": (materialization.world_model_record_hash),
            }
        )
        execution = repository.resolve_candidate_simulation_v5(
            ref=execution_ref,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        if type(execution) is not CandidateSimulationExecutionV5:
            raise ValueError("candidate_simulation_execution_v5_required")
        if artifact_ref_identity_key(execution.n5_input_ref) != artifact_ref_identity_key(
            input_ref
        ):
            raise ValueError("candidate_simulation_execution_input_selected_view_mismatch")
        if artifact_ref_identity_key(execution.n4_source_ref) != artifact_ref_identity_key(
            source_ref
        ):
            raise ValueError("candidate_simulation_execution_source_selected_view_mismatch")
        if artifact_ref_identity_key(execution.context_job_ref) != artifact_ref_identity_key(
            context_ref
        ):
            raise ValueError("candidate_simulation_execution_context_selected_view_mismatch")
        value = value.model_copy(
            update={"n5_execution_ref": execution_ref, "n5_result_ref": execution.n5_result_ref}
        )
        if (
            execution.original_candidate_id != candidate_id
            or execution.original_candidate_hash != cycle.selected_candidate_content_hash
            or execution.original_n4_atom_hash != cycle.selected_candidate_content_hash
            or execution.profile_config_ref != input_record.profile_config_ref
            or execution.derived_n5_atom_hash
            != input_record.materialization.derived_n5_atom.content_hash
            or execution.problem_ref != input_record.materialization.problem_ref
            or execution.world_model_record_hash
            != input_record.materialization.world_model_record_hash
        ):
            raise ValueError("candidate_simulation_execution_cycle_binding_mismatch")

        source = repository.load_candidate_scenario_source_for_n5(
            source_ref,
            expected_run_id=expected_run_id,
            expected_job_id=expected_job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        source_v2 = (
            source.source_record
            if type(source) is N4CandidateScenarioSourceRecordV3
            else source
            if type(source) is N4CandidateScenarioSourceRecordV2
            else None
        )
        if type(source_v2) is not N4CandidateScenarioSourceRecordV2:
            raise ValueError("candidate_simulation_n4_source_v2_required")
        source_v1 = source_v2.source_record
        if (
            type(source_v1) is not N4CandidateScenarioSourceRecordV1
            or source_v1.status != "candidate_unverified"
            or source_v1.candidate is None
            or type(source_v1.candidate) is not N4CandidateScenarioProposalCandidate
            or source_v1.candidate.candidate_id != candidate_id
            or source_v1.candidate.atom.content_hash != cycle.selected_candidate_content_hash
            or source_v1.candidate.atom.intervention_id
            != input_record.materialization.derived_n5_atom.intervention_id
            or input_record.profile != source_v1.profile
            or input_record.profile.profile_selection_ref
            != cycle_job_profile_selection_ref(source_v1.problem)
            or source_v2.model_declaration_ref != input_record.model_declaration_ref
            or source_v2.ncm_ref != input_record.ncm_ref
        ):
            raise ValueError("candidate_simulation_n4_cycle_source_binding_mismatch")
        value = value.model_copy(
            update={
                "candidate_content_hash": source_v1.candidate.atom.content_hash,
                "n4_atom_id": source_v1.candidate.atom.intervention_id,
                "n4_atom_content_hash": source_v1.candidate.atom.content_hash,
            }
        )

        expected_derived_atom = derive_candidate_scenario_atom(
            source_v1.candidate.atom,
            target_world_slot=materialization.target_world_slot,
            value=materialization.value,
        )
        if (
            materialization.candidate_id != candidate_id
            or materialization.original_candidate_hash != cycle.selected_candidate_content_hash
            or materialization.original_atom_hash != source_v1.candidate.atom.content_hash
            or materialization.derived_n5_atom != expected_derived_atom
        ):
            raise ValueError("candidate_simulation_derived_atom_recompute_mismatch")

        persisted_declaration = _verify_configured_profile(
            admission_owner=admission_owner,
            repository=repository,
            input_record=input_record,
            expected_job_id=expected_job_id,
            expected_run_id=expected_run_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        context_job = context_owner.resolve_historical_job_artifact(
            context_ref,
            problem=source_v1.problem,
            expected_job_id=expected_job_id,
            expected_run_id=expected_run_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        world = context_job.context.world_model_record
        value = value.model_copy(update={"world_model_record_id": world.world_model_record_id})
        configured_inputs = input_record.profile.context_inputs
        from polisyos.runtime.quality.world_model_record import (
            derive_candidate_scenario_world_model_record,
            world_model_artifact_views,
        )

        expected_world = derive_candidate_scenario_world_model_record(
            configured_inputs.world_model_record,
            ncm_artifact_ref=input_record.ncm_ref,
            declaration_content_hash=persisted_declaration.content_hash,
            substrate_registry_view_ref=world_model_artifact_views(world).substrate_registry_ref,
        )
        if (
            context_job.context.content_hash != source_v1.context_hash
            or context_job.context.substrate_registry != configured_inputs.substrate_registry
            or context_job.context.selected_registry_entry_hashes
            != configured_inputs.selected_registry_entry_hashes
            or context_job.context.intervention_substrate
            != configured_inputs.intervention_substrate
            or context_job.context.candidate_levers != configured_inputs.candidate_levers
            or context_job.context.transport_context != configured_inputs.transport_context
            or context_job.context.source_pack_content_hash
            != configured_inputs.source_pack_content_hash
            or context_job.context.substrate_input_content_hash
            != configured_inputs.substrate_input_content_hash
            or context_job.context.domain != source_v1.problem.domain
            or world.content_hash != source_v1.world_model_record_hash
            or world.content_hash != materialization.world_model_record_hash
            or world.content_hash != execution.world_model_record_hash
            or world != expected_world
            or str(world.world_model_record_id)
            != str(input_record.materialization.derived_n5_atom.world_model_record_ref)
            or str(input_record.ncm_ref.artifact_id) not in world.simulation_model_ref.ncm_refs
        ):
            raise ValueError("candidate_simulation_context_world_binding_mismatch")

        simulation = cycle.simulation
        if (
            type(simulation) is not SimulationPortObservation
            or simulation.status != "joint_simulated"
            or simulation.candidate_id != candidate_id
            or simulation.simulation_result_ref is None
            or artifact_ref_identity_key(simulation.simulation_result_ref)
            != artifact_ref_identity_key(execution.n5_result_ref)
            or simulation.simulation_ref != execution.n5_result_content_hash
            or simulation.uncertainty_kind != "K_sim"
            or simulation.k_world_ref_before != world.content_hash
            or simulation.k_world_ref_after != world.content_hash
        ):
            raise ValueError("candidate_simulation_cycle_n5_result_binding_mismatch")
        blockers = set(simulation.authority_blockers)
        if "candidate_scenario_n5_only" not in blockers or not blockers.issubset(
            _N8_CANDIDATE_SIMULATION_LIMITATIONS
        ):
            raise ValueError("candidate_simulation_n8_limiter_not_allowlisted")

        result = load_joint_simulation_result(
            execution.n5_result_ref,
            store=store,
            expected_world_model_record_content_hash=world.content_hash,
            expected_atom_ids=(materialization.derived_n5_atom.intervention_id,),
            expected_selected_outcomes=(input_record.outcome_variable,),
        )
        if (
            result.world_model_record_ref != world.world_model_record_id
            or result.receipt.payload_hash != execution.n5_result_content_hash
            or result.atom_ids != (materialization.derived_n5_atom.intervention_id,)
            or result.selected_outcomes != (input_record.outcome_variable,)
        ):
            raise ValueError("candidate_simulation_n5_result_basis_mismatch")
        selected_engines = tuple(
            decision for decision in result.engine_decisions if decision.decision == "selected"
        )
        if len(selected_engines) != 1 or not result.trajectories:
            raise ValueError("candidate_simulation_n5_selected_engine_not_unique")
        selected_engine = selected_engines[0]
        if not selected_engine.method_fqn or any(
            (
                trajectory.engine_kind,
                trajectory.method_fqn,
                trajectory.objective_ref,
            )
            != (
                selected_engine.engine_kind,
                selected_engine.method_fqn,
                selected_engine.objective_ref,
            )
            for trajectory in result.trajectories
        ):
            raise ValueError("candidate_simulation_n5_trajectory_engine_mismatch")

        replayed_simulation = simulation.model_copy(update={"world_model_record": world})
        observation = _DefaultSimulationBoundFoundryValuePort(
            repo_root=None,
            cycle_substrate_context=context_job.context,
            artifact_store=store,
        )(
            candidate=source_v1.candidate,
            simulation=replayed_simulation,
            problem=source_v1.problem,
            cycle_index=cycle.cycle_index,
        )
        if (
            type(observation) is not ValuePortObservation
            or observation.candidate_id != candidate_id
            or observation.status not in {"value_conditional", "value_blocked"}
        ):
            raise ValueError("candidate_simulation_n8_replay_observation_invalid")

        return ConditionalSimulationReplayValue(
            cycle_index=cycle.cycle_index,
            job_id=expected_job_id,
            run_id=expected_run_id,
            tenant_id=expected_tenant_id,
            cell_id=expected_cell_id,
            candidate_id=candidate_id,
            candidate_content_hash=source_v1.candidate.atom.content_hash,
            n4_source_ref=source_ref,
            n4_atom_id=source_v1.candidate.atom.intervention_id,
            n4_atom_content_hash=source_v1.candidate.atom.content_hash,
            n5_input_ref=input_ref,
            n5_execution_ref=execution_ref,
            n5_result_ref=execution.n5_result_ref,
            n5_receipt_payload_hash=result.receipt.payload_hash,
            context_job_ref=context_ref,
            profile_config_ref=input_record.profile_config_ref,
            profile_content_hash=input_record.profile.content_hash,
            profile_selection_ref=input_record.profile.profile_selection_ref,
            n5_atom_id=materialization.derived_n5_atom.intervention_id,
            n5_atom_content_hash=materialization.derived_n5_atom.content_hash,
            outcome_variable=input_record.outcome_variable,
            world_model_record_id=world.world_model_record_id,
            world_model_record_content_hash=world.content_hash,
            selected_engine_kind=str(selected_engine.engine_kind),
            selected_method_fqn=selected_engine.method_fqn,
            selected_objective_ref=selected_engine.objective_ref,
            trajectory_count=len(result.trajectories),
            observation=observation,
        )
    except Exception:
        return value.model_copy(
            update={
                "observation": ValuePortObservation(
                    status="value_blocked",
                    candidate_id=candidate_id,
                    authority_blockers=("conditional_simulation_replay_refused",),
                    reason=(
                        "The persisted N5 candidate basis failed owner-bound replay; "
                        "no conditional value is projected."
                    ),
                    evaluation_mode="simulate_only",
                    decision_grade="blocked",
                ),
            }
        )


def _selected_artifact_ref(
    diagnostics: Mapping[str, object],
    *,
    selected_key: str,
    identity_key: str,
) -> ArtifactRef:
    selected = diagnostics.get(selected_key)
    if not isinstance(selected, Mapping):
        raise ValueError(f"{selected_key}_missing")
    ref = ArtifactRef.model_validate(selected)
    identity = diagnostics.get(identity_key)
    if identity is not None and (not isinstance(identity, str) or identity != str(ref.artifact_id)):
        raise ValueError(f"{identity_key}_selected_view_mismatch")
    return ref


def _verify_configured_profile(
    *,
    admission_owner: ConfiguredCandidateSimulationContextAdmissionOwner | None,
    repository: GenerationSourceRepository,
    input_record: CandidateSimulationN5InputV5,
    expected_job_id: str,
    expected_run_id: str,
    expected_tenant_id: str,
    expected_cell_id: str,
) -> CandidateSimulationSyntheticModelDeclarationV1:
    if type(admission_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner:
        raise ValueError("candidate_simulation_configured_profile_owner_unavailable")
    if admission_owner.store is not repository.store:
        raise ValueError("candidate_simulation_configured_profile_store_mismatch")
    profile_ref = candidate_simulation_profile_ref(input_record.profile)
    matches = tuple(
        profile
        for profile in admission_owner.profiles
        if profile.profile_selection_ref == input_record.profile.profile_selection_ref
    )
    if len(matches) != 1 or matches[0] != input_record.profile:
        raise ValueError("candidate_simulation_configured_profile_mismatch")
    configured_declarations = tuple(
        declaration
        for declaration in admission_owner.model_declarations
        if declaration.profile_config_ref == profile_ref
    )
    if len(configured_declarations) != 1:
        raise ValueError("candidate_simulation_configured_model_declaration_missing")
    persisted_declaration = repository.load_candidate_model_declaration(
        input_record.model_declaration_ref,
        expected_profile=input_record.profile,
        expected_run_id=expected_run_id,
        expected_job_id=expected_job_id,
        expected_tenant_id=expected_tenant_id,
        expected_cell_id=expected_cell_id,
    )
    if (
        persisted_declaration != configured_declarations[0]
        or persisted_declaration.profile_config_ref != profile_ref
        or persisted_declaration.profile_content_hash != input_record.profile.content_hash
        or persisted_declaration.profile_selection_ref != input_record.profile.profile_selection_ref
        or persisted_declaration.outcome_variable != input_record.outcome_variable
    ):
        raise ValueError("candidate_simulation_configured_model_declaration_mismatch")
    return persisted_declaration


def _blocked(
    cycle: GenerationCycleRecord,
    *,
    candidate_id: str,
    expected_job_id: str,
    expected_run_id: str,
    expected_tenant_id: str,
    expected_cell_id: str,
    code: str,
    reason: str,
) -> ConditionalSimulationReplayValue:
    return ConditionalSimulationReplayValue(
        projection_source="not_established",
        cycle_index=cycle.cycle_index,
        job_id=expected_job_id,
        run_id=expected_run_id,
        tenant_id=expected_tenant_id,
        cell_id=expected_cell_id,
        candidate_id=candidate_id,
        candidate_content_hash=cycle.selected_candidate_content_hash,
        observation=ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate_id,
            authority_blockers=(code,),
            reason=reason,
            evaluation_mode="simulate_only",
            decision_grade="blocked",
        ),
    )
