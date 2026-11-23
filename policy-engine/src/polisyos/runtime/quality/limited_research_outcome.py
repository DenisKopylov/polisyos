"""Bind a completed model-only result to its bounded research question."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.pdc import gy_content_hash

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        SimulationPortObservation,
        ValuePortObservation,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationContextHandoffV1,
        GenericCycleSimulationN5InputV1,
        GenericN5ExecutionJoinOutcome,
        GenericN5ResolvedResult,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest

type _Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

_MODEL_ONLY_BLOCKER = "simulation_only_k_sim_not_world_evidence"
_SELECTED_KINDS = {
    "profile_ref": "runtime.quality.generic_cycle_simulation_profile",
    "input_ref": "runtime.quality.generic_cycle_simulation_n5_input",
    "execution_ref": "runtime.quality.generic_cycle_simulation_n5_execution",
    "result_ref": "polisyos.runtime.joint_simulation_result",
}


def _are_selected_views(refs: Mapping[str, ArtifactRef]) -> bool:
    return all(
        ref.kind == _SELECTED_KINDS[field]
        and ref.media_type == "application/json"
        and ref.manifest_profile_sha256 is not None
        for field, ref in refs.items()
    )


class LimitedResearchOutcome(BaseModel):
    """Selected numerical scope completed without widening candidate authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.limited_research_outcome.v1"] = (
        "policyos.runtime.limited_research_outcome.v1"
    )
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    design_problem_basis_ref: _Digest
    candidate_id: str = Field(min_length=1)
    candidate_atom_hash: _Digest
    cycle_index: int = Field(ge=0, strict=True)
    profile_ref: ArtifactRef
    input_ref: ArtifactRef
    execution_ref: ArtifactRef
    result_ref: ArtifactRef
    request_content_hash: _Digest
    receipt_payload_hash: _Digest
    world_model_record_content_hash: _Digest
    outcome_variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    steps: tuple[StrictInt, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_exact_views(self) -> LimitedResearchOutcome:
        if not _are_selected_views({field: getattr(self, field) for field in _SELECTED_KINDS}):
            raise ValueError("limited_research_outcome_requires_selected_views")
        if self.steps[0] < 0 or self.steps != tuple(sorted(set(self.steps))):
            raise ValueError("limited_research_outcome_steps_invalid")
        return self

    def matches_cycle(
        self,
        *,
        design_problem_basis_ref: str,
        candidate_atom_hash: str,
        cycle_index: int,
        simulation: SimulationPortObservation,
        value: ValuePortObservation,
        historical_projection: bool = False,
    ) -> bool:
        """Check intrinsic consistency before any historical owner replay."""

        request_binding = simulation.generic_n5_request_binding
        request_matches = (
            self.request_content_hash == request_binding.request_content_hash
            if request_binding is not None
            # Persisted cycle observations leave this request to the selected
            # execution. The serving reader must independently reopen it.
            else historical_projection
        )
        return (
            self.design_problem_basis_ref == design_problem_basis_ref
            and self.candidate_atom_hash == candidate_atom_hash
            and self.cycle_index == cycle_index
            and self.candidate_id == simulation.candidate_id == value.candidate_id
            and self.profile_ref == simulation.generic_profile_ref
            and self.input_ref == simulation.generic_n5_input_ref
            and self.execution_ref == simulation.generic_n5_execution_ref
            and self.result_ref == simulation.simulation_result_ref
            and self.receipt_payload_hash == simulation.simulation_ref
            and request_matches
            and self.world_model_record_content_hash
            == simulation.k_world_ref_before
            == simulation.k_world_ref_after
            == value.world_model_record_content_hash
            and simulation.status == "joint_simulated"
            and value.status == "value_conditional"
            and value.evaluation_mode == "simulate_only"
            and value.decision_grade == "low"
            and value.value_ref == str(self.result_ref.artifact_id)
            and value.authority_blockers == (_MODEL_ONLY_BLOCKER,)
            and value.value_receipt is None
            and value.method_selection_receipt is None
            and value.candidate_value_method_ref is None
            and value.candidate_value_method_limitation_code is None
        )

    def matches_reopened(
        self,
        *,
        problem: DesignProblem,
        join: GenericN5ExecutionJoinOutcome,
        replay: GenericN5ResolvedResult | None,
    ) -> bool:
        """Verify historical scope from the independently reopened execution and body."""

        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationN5ExecutionV3,
        )

        execution = join.execution
        input_record = join.input_record
        if (
            join.status != "resolved"
            # V4 is a blocked obligation and V5 uses a protected successor.
            or type(execution) is not GenericCycleSimulationN5ExecutionV3
            or execution.status != "joint_simulated"
            or execution.initial_method_input_purpose is not None
            or input_record is None
            or input_record.n4_child_profile_family_ref is not None
            or input_record.native_world_checkpoint_ref is not None
            or input_record.profile.profile_selection_kind != "problem"
            or input_record.profile.candidate_value_source_request_ref is not None
            or replay is None
            or replay.input_record != input_record
            or not _matches_selected_n5_atom(input_record, replay.request)
            or not _covers_research_question(problem, replay)
        ):
            return False
        binding = execution.request_binding
        return (
            binding.request == replay.request
            and binding.request_content_hash == self.request_content_hash
            and input_record.cycle_index == self.cycle_index
            and input_record.candidate_atom_hash == self.candidate_atom_hash
            and input_record.candidate_id == self.candidate_id
            and execution.candidate_id == self.candidate_id
            and execution.candidate_atom_hash == self.candidate_atom_hash
            and execution.profile_ref == self.profile_ref
            and execution.input_ref == self.input_ref
            and execution.result_ref == self.result_ref
            and execution.world_model_record_content_hash == self.world_model_record_content_hash
            and gy_content_hash(problem.model_dump(mode="json")) == self.design_problem_basis_ref
            and problem.outcome_of_interest.target_variable == self.outcome_variable
            and replay.request.horizon.steps() == self.steps
            and replay.result.receipt.payload_hash == self.receipt_payload_hash
            and _model_outcome_unit(problem, replay) == self.unit
        )


def _model_outcome_unit(problem: DesignProblem, replay: GenericN5ResolvedResult) -> str | None:
    outcome = problem.outcome_of_interest
    slot = replay.request.world_model_record.slot_binding(outcome.target_variable)
    if slot is None:
        return None
    if outcome.measurement_unit is not None and slot.unit != outcome.measurement_unit:
        return None
    return slot.unit


def _matches_selected_n5_atom(
    input_record: GenericCycleSimulationN5InputV1,
    request: JointSimulationRequest,
) -> bool:
    """Bind the executed atom to the original subject of the reopened N5 input."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV3,
    )

    if len(request.intervention_atoms) != 1:
        return False
    (atom,) = request.intervention_atoms
    materializations = input_record.component_materializations
    if not materializations:
        return atom.content_hash == input_record.candidate_atom_hash
    if type(input_record.n5) is not GenericCycleN5RequestProfileV3 or len(materializations) != 1:
        return False
    (conversion,) = materializations
    return (
        conversion.original_atom_hash == input_record.candidate_atom_hash
        and conversion.candidate_id == input_record.candidate_id
        and conversion.derived_n5_atom == atom
    )


def _covers_research_question(
    problem: DesignProblem,
    replay: GenericN5ResolvedResult,
) -> bool:
    """Check the exact same-model contrast and direction for a bounded question."""

    outcome = problem.outcome_of_interest
    request, result = replay.request, replay.result
    comparator = result.diagnostics.get("ncm_conditional_comparator")
    profile = request.comparator_profile
    if (
        problem.authority_profile.requested_authority_level != "research"
        or any(constraint.hard for constraint in problem.constraints)
        or problem.evidence_acquisition_needs.needs
        or len(problem.objectives) != 1
        # This comparator computes the selected scalar directly.
        or outcome.metric_id != outcome.target_variable
        or problem.objectives[0].metric_id != outcome.metric_id
        or problem.objectives[0].direction != outcome.direction
        or outcome.direction == "maintain_range"
        # The selected-result owner verifies the comparator's typed estimand,
        # request and edges, and the same-seed differences before projection.
        or not result.comparator_refs_verified
        or result.diagnostics.get("effect_basis_status") != "established"
        or not isinstance(comparator, dict)
        or comparator.get("estimand") != outcome.estimand
        or profile is None
        or request.evidence_state is None
        or set(request.evidence_state) != set(outcome.conditioning_variables)
        or request.selected_outcomes != (outcome.target_variable,)
        or result.selected_outcomes != request.selected_outcomes
        or result.world_model_record_content_hash != request.world_model_record.content_hash
        or result.horizon != request.horizon
        or len(request.intervention_atoms) != 1
        or result.atom_ids != (request.intervention_atoms[0].intervention_id,)
        or result.uncertainty_kind != "K_sim"
        or result.world_credal_state_before != result.world_credal_state_after
        or result.receipt.calibration_status != "content_bound_run_receipt"
        or result.receipt.authoritative_for != ("simulation_numerical_uncertainty",)
        or result.promotion_ready_value_packet.get("authority_blockers") != [_MODEL_ONLY_BLOCKER]
        or not {"world_credal_state_shrinkage", "promotion"}.issubset(
            result.receipt.may_not_use_for
        )
    ):
        return False
    unit = _model_outcome_unit(problem, replay)
    steps = request.horizon.steps()
    if not unit or profile.outcome_units.get(outcome.target_variable) != unit or len(steps) != 1:
        return False
    joint = tuple(
        trajectory
        for trajectory in result.trajectories
        if trajectory.run_level == "joint" and trajectory.atom_ids == result.atom_ids
    )
    if len(joint) != 1 or tuple(point.step for point in joint[0].points) != steps:
        return False
    (point,) = joint[0].points
    effect = point.effect.get(outcome.target_variable)
    if (
        effect is None
        or not math.isfinite(effect)
        or point.replication_sampling is None
        or point.replication_sampling.status != "estimated"
    ):
        return False
    return effect > 0.0 if outcome.direction == "maximize" else effect < 0.0


def issue_limited_research_outcome(
    *,
    problem: DesignProblem,
    candidate_atom_hash: str,
    cycle_index: int,
    simulation: SimulationPortObservation,
    handoff: GenericCycleSimulationContextHandoffV1 | None,
    verified_replay: GenericN5ResolvedResult | None,
    authority_blockers: Sequence[str],
) -> LimitedResearchOutcome | None:
    """Issue a candidate-only binding after the live owner reopens N5.

    The caller supplies the successful selected replay from the active N8
    owner boundary. Absent owner evidence and unanswered mandatory scope
    stay on the ordinary N6 path.
    """
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationContextHandoffV1,
        GenericN5ResolvedResult,
    )

    if (
        type(handoff) is not GenericCycleSimulationContextHandoffV1
        or type(verified_replay) is not GenericN5ResolvedResult
        or handoff.profile.profile_selection_kind != "problem"
        or handoff.n4_child_profile_family_ref is not None
        or handoff.profile.candidate_value_source_request_ref is not None
        or verified_replay.initial_method_input is not None
        or simulation.status != "joint_simulated"
        or simulation.model_input_obligation_set_ref is not None
        or tuple(authority_blockers) != (_MODEL_ONLY_BLOCKER,)
        or not _covers_research_question(problem, verified_replay)
    ):
        return None
    request, result = verified_replay.request, verified_replay.result
    input_record = verified_replay.input_record
    binding = simulation.generic_n5_request_binding
    profile_ref = simulation.generic_profile_ref
    input_ref = simulation.generic_n5_input_ref
    execution_ref = simulation.generic_n5_execution_ref
    result_ref = simulation.simulation_result_ref
    world_hash = request.world_model_record.content_hash
    if (
        profile_ref is None
        or input_ref is None
        or execution_ref is None
        or result_ref is None
        or binding is None
        or input_record is None
        or input_record.profile_ref != profile_ref
        or input_record.profile != handoff.profile
        or input_record.n4_source_ref != simulation.generic_n4_source_ref
        or input_record.context_job_ref != handoff.context_job_ref
        or input_record.candidate_id != simulation.candidate_id
        or input_record.candidate_atom_hash != candidate_atom_hash
        or input_record.cycle_index != cycle_index
        or profile_ref != handoff.profile_ref
        or simulation.generic_context_job_ref != handoff.context_job_ref
        or simulation.generic_profile_selection_ref != handoff.profile.profile_selection_ref
        or handoff.context.design_problem_ref != cycle_job_design_problem_ref(problem)
        or handoff.profile.n5.horizon != request.horizon
        or binding.request != request
        or not _matches_selected_n5_atom(input_record, request)
        or result.receipt.payload_hash != simulation.simulation_ref
        or result.receipt.engine_kind != handoff.profile.n5.resource
        or world_hash != simulation.k_world_ref_before
        or world_hash != simulation.k_world_ref_after
    ):
        return None
    selected = {
        "profile_ref": profile_ref,
        "input_ref": input_ref,
        "execution_ref": execution_ref,
        "result_ref": result_ref,
    }
    if not _are_selected_views(selected):
        return None
    unit = _model_outcome_unit(problem, verified_replay)
    if not unit:
        return None
    return LimitedResearchOutcome(
        design_problem_basis_ref=gy_content_hash(problem.model_dump(mode="json")),
        candidate_id=simulation.candidate_id,
        candidate_atom_hash=candidate_atom_hash,
        cycle_index=cycle_index,
        profile_ref=profile_ref,
        input_ref=input_ref,
        execution_ref=execution_ref,
        result_ref=result_ref,
        request_content_hash=binding.request_content_hash,
        receipt_payload_hash=result.receipt.payload_hash,
        world_model_record_content_hash=world_hash,
        outcome_variable=problem.outcome_of_interest.target_variable,
        unit=unit,
        steps=request.horizon.steps(),
    )
