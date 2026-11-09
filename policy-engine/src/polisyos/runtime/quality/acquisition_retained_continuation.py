"""Actual current cheap consequences of a retained candidate evaluation.

The artifact is a new source-reaction observation with freshly produced cheap
diagnostics. It retains the original generation/N4/N5 evaluation occurrence;
it grants no validation or publication authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.data_requirement import (
    CapabilityRequirementResolution,
    DataRequirementCompilationReport,
)
from polisyos.pdc import CounterexampleRecord, RefinementDecision, SearchIteration
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationDecision,
    AcquisitionSelectedEvaluation,
    _candidate_model_values_same,
    _candidate_ref_same,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_planner import (
    _N7_SOURCE_JOIN_RULE,
    AcquisitionCostBasisRecord,
    AcquisitionPlannerReport,
    AcquisitionRequirementBasisBinding,
    AcquisitionWorldSnapshot,
    _n7_legacy_planner_records_match,
    load_acquisition_planner_report,
    n7_planner_input_content_hash,
    validate_persisted_acquisition_planner_report,
    validate_persisted_data_requirement_compilation_report,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    DesignRevisionRequest,
    LoopVOIDecision,
    ValuePortObservation,
    _cycle_acquisition_requirement,
    _n7_bound_source_gap,
    _n7_joined_planner_records_match,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)
from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
from polisyos.scientist.orchestration.engine import ProducerBudgetObservation

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationDecision,
        ResolvedAcquisitionEvaluation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateRouteLoopReceipt,
        AcquisitionRouteLoopReceiptV2,
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

_HASH = r"^sha256:[0-9a-f]{64}$"


class AcquisitionRetainedPlannerInputs(BaseModel):
    """All actual inputs consumed by the existing planner input-binding owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    acquisition_request: dict[str, Any]
    compiled_requirement_specs: tuple[dict[str, Any], ...]
    capability_requirement_resolutions: tuple[CapabilityRequirementResolution, ...] | None
    requirement_basis_binding: AcquisitionRequirementBasisBinding
    design_problem: DesignProblem
    generated_at: AwareDatetime
    world_snapshot: AcquisitionWorldSnapshot
    compilation_report: DataRequirementCompilationReport

    def planner_content_hash(self) -> str:
        """Recompute the actual owner hash over the complete consumed input set."""
        from inspect import signature

        names = set(type(self).model_fields) - {"compilation_report"}
        if names != set(signature(n7_planner_input_content_hash).parameters):
            raise ValueError("retained_planner_input_schema_not_established")
        return n7_planner_input_content_hash(
            run_id=self.run_id,
            acquisition_request=self.acquisition_request,
            compiled_requirement_specs=self.compiled_requirement_specs,
            capability_requirement_resolutions=self.capability_requirement_resolutions,
            requirement_basis_binding=self.requirement_basis_binding,
            design_problem=self.design_problem,
            generated_at=self.generated_at,
            world_snapshot=self.world_snapshot,
        )


class AcquisitionRetainedCurrentProjection(BaseModel):
    """Freshly produced candidate-band grounding/value/VOI/requirement outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_cycle_index: int = Field(ge=0)
    selected_candidate_id: str
    selected_candidate_content_hash: str = Field(pattern=_HASH)
    grounding: CandidateGroundingObservation
    value_port: ValuePortObservation
    execution_schedule: SchedulingDecision
    terminal_kind: str
    voi_decision: LoopVOIDecision
    revision_request: DesignRevisionRequest
    counterexample: CounterexampleRecord
    refinement_decision: RefinementDecision
    search_iteration: SearchIteration
    current_planner_report: AcquisitionPlannerReport | None = None
    current_planner_report_ref: ArtifactRef | None = None
    current_planner_world_snapshot: AcquisitionWorldSnapshot | None = None
    current_cost_basis: AcquisitionCostBasisRecord | None = None
    current_planner_inputs: AcquisitionRetainedPlannerInputs | None = None


class AcquisitionRetainedContinuation(BaseModel):
    """A source/action-bound record of actual current continuation work."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ARTIFACT_KIND: ClassVar[str] = "runtime_quality.acquisition_retained_continuation"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.AcquisitionRetainedContinuation"
    schema_version: Literal["AcquisitionRetainedContinuation@1.0"] = (
        "AcquisitionRetainedContinuation@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_rule: Literal["AD-E02-B09-01/current-cheap-consequences/v1"] = (
        "AD-E02-B09-01/current-cheap-consequences/v1"
    )
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    action_job_id: str
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    compiled_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    candidate_id: str
    selected_action_receipt_ref: ArtifactRef
    evaluation_decision_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    growth_receipt_ref: ArtifactRef
    admitted_source_ref: ArtifactRef
    retained_evaluation: AcquisitionSelectedEvaluation
    current_projection: AcquisitionRetainedCurrentProjection
    predicate_provenance: Literal["recomputed"] = "recomputed"
    generated_at: str
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _verify_content(self) -> AcquisitionRetainedContinuation:
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("acquisition_retained_continuation_content_mismatch")
        projection = self.current_projection
        if (
            projection.source_cycle_index != self.retained_evaluation.cycle_index
            or projection.selected_candidate_id != self.retained_evaluation.candidate_id
            or projection.selected_candidate_content_hash
            != self.retained_evaluation.candidate_content_hash
            or projection.grounding.candidate_id != self.candidate_id
            or projection.value_port.candidate_id != self.candidate_id
            or projection.voi_decision.candidate_id != self.candidate_id
        ):
            raise ValueError("acquisition_retained_current_projection_subject_mismatch")
        if (
            projection.counterexample.candidate_ref != self.candidate_id
            or projection.refinement_decision.candidate_ref != self.candidate_id
            or projection.search_iteration.candidate_ref != self.candidate_id
            or projection.revision_request.source_counterexample_ref
            != projection.counterexample.counterexample_ref
            or projection.refinement_decision.consumed_counterexample_refs
            != [projection.counterexample.counterexample_ref]
            or projection.search_iteration.counterexample_refs
            != [projection.counterexample.counterexample_ref]
            or projection.search_iteration.refinement_decision_ref
            != projection.refinement_decision.decision_ref
        ):
            raise ValueError("acquisition_retained_current_diagnostic_join_mismatch")
        if (
            (projection.current_planner_report is None)
            != (projection.current_planner_inputs is None)
            or (projection.current_planner_report is None)
            != (projection.current_planner_report_ref is None)
            or (projection.current_planner_report is None)
            != (projection.current_planner_world_snapshot is None)
        ):
            raise ValueError("acquisition_retained_planner_binding_incomplete")
        return self


class CandidateAcquisitionRetainedContinuation(BaseModel):
    """A candidate-only fresh reaction retaining one selected prior N5 result.

    The producer must replay both complete candidate bases, recheck the live
    owner and compare the same budget observation around the cheap work. This
    record does not itself establish any of those owner checks or admission.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    ARTIFACT_KIND: ClassVar[str] = "runtime_quality.candidate_acquisition_retained_continuation"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = (
        "polisyos.runtime.CandidateAcquisitionRetainedContinuation"
    )
    schema_version: Literal["CandidateAcquisitionRetainedContinuation@1.0"] = (
        "CandidateAcquisitionRetainedContinuation@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_rule: Literal["candidate-source-current-cheap-consequences.v1"] = (
        "candidate-source-current-cheap-consequences.v1"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    compiled_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    candidate_action_ref: ArtifactRef
    reuse_occurrence_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_world_intent_ref: ArtifactRef
    candidate_source_ref: ArtifactRef
    evaluation_decision_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    retained_evaluation: AcquisitionSelectedEvaluation
    current_projection: AcquisitionRetainedCurrentProjection
    retained_port_capture_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    budget_observation_before: ProducerBudgetObservation
    budget_observation_after: ProducerBudgetObservation
    limitations: tuple[str, ...] = Field(min_length=1)
    predicate_provenance: Literal["recomputed"] = "recomputed"
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    generated_at: str = Field(min_length=1)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _verify_content(self) -> CandidateAcquisitionRetainedContinuation:
        _validate_reuse_occurrence_ref(self.reuse_occurrence_ref)
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_retained_continuation_content_mismatch")
        refs = (
            (self.candidate_action_ref, "runtime_quality.acquisition_candidate_action_receipt"),
            (self.candidate_world_intent_ref, "runtime_quality.acquisition_candidate_world_intent"),
            (self.candidate_source_ref, "runtime.quality.candidate_acquisition_source"),
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.current_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
        )
        if any(
            not _candidate_ref_same(ref, ref)
            or ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in refs
        ):
            raise ValueError("candidate_retained_continuation_selected_ref_invalid")
        if self.retained_port_capture_ref is not None and (
            not _candidate_ref_same(self.retained_port_capture_ref, self.retained_port_capture_ref)
            or self.retained_port_capture_ref.kind
            != "runtime_quality.candidate_retained_port_capture"
            or self.retained_port_capture_ref.media_type != "application/json"
            or self.retained_port_capture_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("candidate_retained_port_capture_ref_invalid")
        if self.budget_observation_before != self.budget_observation_after:
            raise ValueError("candidate_retained_budget_observation_changed")
        budget_binding = self.budget_observation_before.run_binding
        if (
            budget_binding.run_id != self.run_id
            or budget_binding.tenant_id != self.tenant_id
            or budget_binding.cell_id != self.cell_id
            or budget_binding.control_job_id != self.source_job_id
        ):
            raise ValueError("candidate_retained_budget_run_binding_mismatch")
        required_limitations = {
            *self.budget_observation_before.limitations,
            "runtime_allocation_not_established",
        }
        if (
            not required_limitations.issubset(self.limitations)
            or len(set(self.limitations)) != len(self.limitations)
            or any(not item.strip() for item in self.limitations)
        ):
            raise ValueError("candidate_retained_limitations_incomplete")
        projection = self.current_projection
        retained = self.retained_evaluation
        if not _candidate_model_values_same(retained, retained):
            raise ValueError("candidate_retained_evaluation_view_invalid")
        if (
            retained.basis_ref is None
            or projection.source_cycle_index != retained.cycle_index
            or projection.selected_candidate_id != retained.candidate_id
            or projection.selected_candidate_content_hash != retained.candidate_content_hash
            or retained.candidate_id != self.candidate_id
            or retained.design_problem_ref != self.design_problem_basis_ref
            or projection.grounding.candidate_id != self.candidate_id
            or projection.value_port.candidate_id != self.candidate_id
            or projection.voi_decision.candidate_id != self.candidate_id
        ):
            raise ValueError("candidate_retained_projection_subject_mismatch")
        if (
            projection.counterexample.candidate_ref != self.candidate_id
            or projection.refinement_decision.candidate_ref != self.candidate_id
            or projection.search_iteration.candidate_ref != self.candidate_id
            or projection.revision_request.source_counterexample_ref
            != projection.counterexample.counterexample_ref
            or projection.refinement_decision.consumed_counterexample_refs
            != [projection.counterexample.counterexample_ref]
            or projection.search_iteration.counterexample_refs
            != [projection.counterexample.counterexample_ref]
            or projection.search_iteration.refinement_decision_ref
            != projection.refinement_decision.decision_ref
        ):
            raise ValueError("candidate_retained_diagnostic_join_mismatch")
        if (
            (projection.current_planner_report is None)
            != (projection.current_planner_inputs is None)
            or (projection.current_planner_report is None)
            != (projection.current_planner_report_ref is None)
            or (projection.current_planner_report is None)
            != (projection.current_planner_world_snapshot is None)
        ):
            raise ValueError("candidate_retained_planner_binding_incomplete")
        return self


def _validate_reuse_occurrence_ref(ref: ArtifactRef | None) -> None:
    if ref is None:
        return
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND,
    )

    if (
        not _candidate_ref_same(ref, ref)
        or ref.kind != CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_retained_reuse_occurrence_ref_invalid")


class CandidateRetainedPortCapture(BaseModel):
    """Owner-recorded fresh candidate port outputs for one retained evaluation.

    The referenced configured port source contains the actual observations and
    their digest preimages. This record binds that selected view to the current
    action and the original numerical occurrence; it is not catalog absence,
    currentness, acquisition permission, or publication authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    ARTIFACT_KIND: ClassVar[str] = "runtime_quality.candidate_retained_port_capture"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.CandidateRetainedPortCapture"
    schema_version: Literal["CandidateRetainedPortCapture@1.0"] = "CandidateRetainedPortCapture@1.0"
    authority_purpose: Literal["recorded_candidate_routing_only"] = (
        "recorded_candidate_routing_only"
    )
    comparison_rule: Literal["candidate-retained-current-port-capture.v1"] = (
        "candidate-retained-current-port-capture.v1"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    compiled_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    candidate_action_ref: ArtifactRef
    reuse_occurrence_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_world_intent_ref: ArtifactRef
    candidate_source_ref: ArtifactRef
    evaluation_decision_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    retained_evaluation: AcquisitionSelectedEvaluation
    configured_port_source_ref: ArtifactRef
    catalog_content_ref: str = Field(pattern=r"^catalog_read_source_content://sha256:[0-9a-f]{64}$")
    budget_observation_before: ProducerBudgetObservation
    budget_observation_after: ProducerBudgetObservation
    historical_catalog_absence: Literal["not_established"] = "not_established"
    catalog_currentness: Literal["not_established"] = "not_established"
    predicate_provenance: Literal["recomputed"] = "recomputed"
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    generated_at: str = Field(min_length=1)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _validate_capture(self) -> CandidateRetainedPortCapture:
        _validate_reuse_occurrence_ref(self.reuse_occurrence_ref)
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_retained_port_capture_content_mismatch")
        refs = (
            (self.candidate_action_ref, "runtime_quality.acquisition_candidate_action_receipt"),
            (self.candidate_world_intent_ref, "runtime_quality.acquisition_candidate_world_intent"),
            (self.candidate_source_ref, "runtime.quality.candidate_acquisition_source"),
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.current_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
            (
                self.configured_port_source_ref,
                "runtime.quality.n7_configured_candidate_port_source",
            ),
        )
        if any(
            not _candidate_ref_same(ref, ref)
            or ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in refs
        ):
            raise ValueError("candidate_retained_port_capture_selected_ref_invalid")
        selected = self.retained_evaluation
        budget = self.budget_observation_before
        if (
            selected.basis_ref is None
            or selected.candidate_id != self.candidate_id
            or selected.design_problem_ref != self.design_problem_basis_ref
            or selected.evaluation_run_id != self.run_id
            or self.budget_observation_after != budget
            or (
                budget.run_binding.tenant_id,
                budget.run_binding.cell_id,
                budget.run_binding.run_id,
                budget.run_binding.control_job_id,
            )
            != (self.tenant_id, self.cell_id, self.run_id, self.source_job_id)
        ):
            raise ValueError("candidate_retained_port_capture_subject_mismatch")
        return self


class _ReactionIdentityInputs(TypedDict):
    problem: DesignProblem
    cycle_index: int
    candidate_id: str
    source_reaction_ref: ArtifactRef


def read_candidate_acquisition_retained_continuation(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    ref: ArtifactRef,
    decision: CandidateAcquisitionEvaluationDecision,
    terminal: AcquisitionCandidateRouteLoopReceipt | AcquisitionCandidateExperimentTerminalReceipt,
    prior_closure: VerifiedAcquisitionRouteClosure | None = None,
    prior_experiment_origin: VerifiedCandidateExperimentOrigin | None = None,
) -> tuple[CandidateAcquisitionRetainedContinuation, ResolvedAcquisitionEvaluation]:
    """Replay one candidate-only continuation against its selected prior owner.

    The caller supplies either the existing costed source closure or the
    separately typed candidate-experiment origin. The caller must independently
    verify the terminal head, selected owner-history chain, both basis comparisons,
    ledger window and commit. This reader neither opens a live lease nor establishes
    historical catalog absence or currentness.
    """
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationDecision,
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
        _N7_CONFIGURED_REPORT_SCHEMA,
        _n7_candidate_n5_l1_planner_records_match,
        _n7_load_configured_candidate_port_source,
        _validate_persisted_planner_report,
        produce_acquisition_cost_basis_record,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        AcquisitionCandidateRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _counterexample_record,
        _default_revision_request,
        _refinement_decision,
        _requirement_missing_distributions,
        _search_iteration,
    )

    experiment_types = (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )
    source_count = int(prior_closure is not None) + int(prior_experiment_origin is not None)
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or type(terminal) not in (AcquisitionCandidateRouteLoopReceipt, *experiment_types)
        or source_count != 1
        or (
            prior_closure is not None and type(prior_closure) is not VerifiedAcquisitionRouteClosure
        )
        or (
            prior_experiment_origin is not None
            and type(prior_experiment_origin) is not VerifiedCandidateExperimentOrigin
        )
        or (
            prior_closure is not None and type(terminal) is not AcquisitionCandidateRouteLoopReceipt
        )
        or (prior_experiment_origin is not None and type(terminal) not in experiment_types)
        or decision.comparison_result != "equivalent"
        or decision.predicate_provenance != "recomputed"
        or terminal.terminal_outcome != "candidate_evaluation_retained"
        or not _candidate_ref_same(terminal.current_continuation_ref, ref)
        or (type(terminal) in experiment_types and terminal.candidate_reentry_ref is not None)
    ):
        raise ValueError("candidate_retained_owner_scope_not_established")
    if prior_closure is not None:
        prior_tenant_id = prior_closure.tenant_id
        prior_cell_id = prior_closure.cell_id
        prior_run_id = prior_closure.run_id
        prior_source_job_id = prior_closure.source_job_id
        prior_route_id = prior_closure.route_id
        prior_compiled_ref = prior_closure.compiled_ref
        prior_design_problem_ref = prior_closure.design_problem_ref
        prior_design_problem_basis_ref = prior_closure.design_problem_basis_ref
        prior_generation_run = prior_closure.generation_run
        prior_source_cycle = prior_closure.source_cycle
        prior_design_problem_basis = prior_closure.design_problem_basis
    else:
        if prior_experiment_origin is None:
            raise ValueError("candidate_retained_experiment_source_not_established")
        if type(terminal) not in experiment_types:
            raise ValueError("candidate_retained_experiment_source_not_established")
        experiment_terminal = terminal
        scope = prior_experiment_origin.policy_scope
        root_source_cycle = prior_experiment_origin.source_cycle
        root_generation_run = prior_experiment_origin.generation_run
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            CandidateUnpricedPolicyScope,
        )
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleRecord,
            GenerationCycleRun,
            _problem_ref,
        )

        if (
            type(root_source_cycle) is not GenerationCycleRecord
            or type(root_generation_run) is not GenerationCycleRun
            or type(scope) is not CandidateUnpricedPolicyScope
            or type(prior_experiment_origin.design_problem_basis) is not DesignProblem
            or root_generation_run.run_id != prior_experiment_origin.run_id
            or root_generation_run.design_problem_ref != scope.design_problem_ref
            or tuple(
                cycle
                for cycle in root_generation_run.cycles
                if cycle.cycle_index == root_source_cycle.cycle_index
            )
            != (root_source_cycle,)
            or prior_experiment_origin.schema_version
            != "polisyos.runtime.candidate_experiment_origin.v1"
            or prior_experiment_origin.monetary_cost != "not_established"
            or prior_experiment_origin.action_authority != "not_established"
            or scope.source_cycle_index != root_source_cycle.cycle_index
            or scope.source_job_id != prior_experiment_origin.source_job_id
            or scope.tenant_id != prior_experiment_origin.tenant_id
            or scope.cell_id != prior_experiment_origin.cell_id
            or scope.run_id != prior_experiment_origin.run_id
            or scope.candidate_id != root_source_cycle.selected_candidate_ref
            or scope.candidate_content_hash != root_source_cycle.selected_candidate_content_hash
            or not _candidate_ref_same(scope.compiled_ref, scope.compiled_ref)
            or _problem_ref(prior_experiment_origin.design_problem_basis)
            != scope.design_problem_basis_ref
            or str(scope.compiled_ref.artifact_id) != decision.compiled_ref
            or scope.design_problem_ref != decision.design_problem_ref
            or scope.design_problem_basis_ref != decision.design_problem_basis_ref
            or prior_experiment_origin.route_id != decision.route_id
        ):
            raise ValueError("candidate_retained_experiment_source_not_established")
        effective_source_cycle = prior_experiment_origin.effective_source_cycle
        effective_generation_run = prior_experiment_origin.effective_generation_run
        if (
            type(effective_source_cycle) is not GenerationCycleRecord
            or type(effective_generation_run) is not GenerationCycleRun
            or effective_generation_run.run_id != root_generation_run.run_id
            or effective_generation_run.design_problem_ref != root_generation_run.design_problem_ref
            or not effective_generation_run.cycles
            or effective_generation_run.cycles[-1] != effective_source_cycle
            or tuple(
                cycle
                for cycle in effective_generation_run.cycles
                if cycle.cycle_index == effective_source_cycle.cycle_index
            )
            != (effective_source_cycle,)
            or effective_source_cycle.cycle_index < root_source_cycle.cycle_index
            or scope.candidate_id != effective_source_cycle.selected_candidate_ref
            or scope.candidate_id != decision.candidate_id
            or effective_source_cycle.selected_candidate_content_hash
            != decision.source_candidate_content_hash
        ):
            raise ValueError("candidate_retained_experiment_source_not_established")
        prior_tenant_id = prior_experiment_origin.tenant_id
        prior_cell_id = prior_experiment_origin.cell_id
        prior_run_id = prior_experiment_origin.run_id
        prior_source_job_id = prior_experiment_origin.source_job_id
        prior_route_id = prior_experiment_origin.route_id
        prior_compiled_ref = str(scope.compiled_ref.artifact_id)
        prior_design_problem_ref = scope.design_problem_ref
        prior_design_problem_basis_ref = scope.design_problem_basis_ref
        prior_generation_run = effective_generation_run
        prior_source_cycle = effective_source_cycle
        prior_design_problem_basis = prior_experiment_origin.design_problem_basis
        if (
            not _candidate_model_values_same(experiment_terminal.policy_scope, scope)
            or not _candidate_ref_same(
                experiment_terminal.policy_ref, prior_experiment_origin.policy_ref
            )
            or experiment_terminal.source_payload_ref != prior_experiment_origin.source_payload_ref
            or experiment_terminal.capability_manifest_ref
            != prior_experiment_origin.capability_manifest_ref
            or experiment_terminal.request_content_hash
            != prior_experiment_origin.request_content_hash
            or not _candidate_model_values_same(
                experiment_terminal.voi_decision, root_source_cycle.voi_decision
            )
        ):
            raise ValueError("candidate_retained_experiment_source_not_established")
    record = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=ref,
        record_type=CandidateAcquisitionRetainedContinuation,
    )
    if type(record) is not CandidateAcquisitionRetainedContinuation:
        raise TypeError("candidate_retained_continuation_reader_mismatch")
    occurrence = (
        terminal.reuse_occurrence_ref
        if type(terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
        else None
    )
    if (
        not _candidate_ref_same(record.reuse_occurrence_ref, occurrence)
        or not _candidate_ref_same(decision.reuse_occurrence_ref, occurrence)
        or (occurrence is not None and record.retained_port_capture_ref is None)
    ):
        raise ValueError("candidate_retained_reuse_occurrence_mismatch")
    for name in (
        "tenant_id",
        "cell_id",
        "run_id",
        "source_job_id",
        "action_job_id",
        "action_generation",
        "route_id",
        "compiled_ref",
        "design_problem_ref",
        "candidate_id",
    ):
        if getattr(record, name) != getattr(decision, name):
            raise ValueError("candidate_retained_action_mismatch:" + name)
    if (
        (record.tenant_id, record.cell_id, record.run_id, record.source_job_id, record.route_id)
        != (
            terminal.tenant_id,
            terminal.cell_id,
            terminal.run_id,
            terminal.source_job_id,
            terminal.route_id,
        )
        or record.action_job_id != terminal.job_id
        or record.action_generation != terminal.action_generation
        or record.compiled_ref != terminal.compiled_ref
        or record.compiled_ref != prior_compiled_ref
        or record.design_problem_ref != prior_design_problem_ref
        or record.design_problem_basis_ref != decision.design_problem_basis_ref
        or record.design_problem_basis_ref != prior_design_problem_basis_ref
        or not _candidate_ref_same(record.candidate_action_ref, decision.candidate_action_ref)
        or not _candidate_ref_same(record.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(
            record.candidate_world_intent_ref, decision.candidate_world_intent_ref
        )
        or not _candidate_ref_same(record.candidate_source_ref, decision.candidate_source_ref)
        or not _candidate_ref_same(record.evaluation_decision_ref, terminal.evaluation_decision_ref)
        or not _candidate_ref_same(record.current_basis_ref, decision.current_basis_ref)
        or not _candidate_model_values_same(record.retained_evaluation, decision.prior_evaluation)
        or not _candidate_model_values_same(
            record.retained_evaluation, terminal.selected_evaluation
        )
        or not _candidate_ref_same(
            record.retained_evaluation.basis_ref, terminal.selected_basis_ref
        )
        or not _candidate_ref_same(
            record.retained_evaluation.n5_execution_ref, terminal.selected_evaluation_witness_ref
        )
        or (record.tenant_id, record.cell_id, record.run_id, record.source_job_id, record.route_id)
        != (
            prior_tenant_id,
            prior_cell_id,
            prior_run_id,
            prior_source_job_id,
            prior_route_id,
        )
    ):
        raise ValueError("candidate_retained_selected_join_mismatch")
    prior = resolve_selected_acquisition_evaluation_parts(
        artifact_store=store,
        control_store=control_store,
        tenant_id=prior_tenant_id,
        cell_id=prior_cell_id,
        run_id=prior_run_id,
        generation_run=prior_generation_run,
        source_cycle=prior_source_cycle,
        design_problem_ref=prior_design_problem_ref,
    )
    if prior.source.problem != prior_design_problem_basis or not _candidate_model_values_same(
        prior.selected.model_copy(update={"basis_ref": record.retained_evaluation.basis_ref}),
        record.retained_evaluation,
    ):
        raise ValueError("candidate_retained_prior_evaluation_mismatch")
    projection = record.current_projection
    routing = projection.value_port.candidate_n5_l1_routing
    previous_routing = prior_source_cycle.value_port.candidate_n5_l1_routing
    if routing is None or (
        previous_routing is not None and routing.requirement_gap != previous_routing.requirement_gap
    ):
        raise ValueError("candidate_retained_current_l1_not_established")
    for actual, expected in (
        (routing.source_ref, prior.selected.n4_source_ref),
        (routing.context_job_ref, prior.selected.context_job_ref),
        (routing.n5_input_ref, prior.selected.n5_input_ref),
        (routing.n5_execution_ref, prior.selected.n5_execution_ref),
        (routing.n5_result_ref, prior.selected.n5_result_ref),
    ):
        if artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected):
            raise ValueError("candidate_retained_l1_evaluation_mismatch")
    common: _ReactionIdentityInputs = {
        "problem": prior.source.problem,
        "cycle_index": projection.source_cycle_index,
        "candidate_id": record.candidate_id,
        "source_reaction_ref": record.current_basis_ref,
    }
    counterexample = _counterexample_record(
        **common, grounding=projection.grounding, value_port=projection.value_port
    )
    revision = _default_revision_request(
        **common,
        terminal_kind=projection.terminal_kind,
        counterexample=counterexample,
        grounding=projection.grounding,
        value_port=projection.value_port,
        source_issue_rule=True,
    )
    refinement = _refinement_decision(
        **common,
        counterexample=counterexample,
        revision=revision,
        next_action=projection.voi_decision,
    )
    iteration = _search_iteration(
        **common,
        counterexample=counterexample,
        decision=refinement,
        next_action=projection.voi_decision,
    )
    if any(
        exact_n5_content_bytes(actual) != exact_n5_content_bytes(expected)
        for actual, expected in (
            (projection.counterexample, counterexample),
            (projection.revision_request, revision),
            (projection.refinement_decision, refinement),
            (projection.search_iteration, iteration),
        )
    ):
        raise ValueError("candidate_retained_diagnostic_owner_replay_mismatch")
    report = projection.current_planner_report
    report_ref = projection.current_planner_report_ref
    inputs = projection.current_planner_inputs
    snapshot = projection.current_planner_world_snapshot
    request = revision.strategy_payload.get("acquisition_request")
    if (
        report is None
        or report_ref is None
        or report_ref.manifest_profile_sha256 is None
        or inputs is None
        or snapshot is None
        or not isinstance(request, dict)
        or request.get("n7_source_join_rule") != _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE
        or inputs.acquisition_request != {**request, "cycle_index": projection.source_cycle_index}
        or inputs.design_problem != prior.source.problem
        or inputs.run_id != report.run_id
        or inputs.generated_at != report.generated_at
        or inputs.requirement_basis_binding != report.requirement_basis_binding
        or inputs.world_snapshot != snapshot
        or inputs.planner_content_hash() != report.planning_context_hash
        or inputs.capability_requirement_resolutions
        != inputs.compilation_report.capability_requirement_resolutions
        or not store.verify(report_ref).ok
        or _validate_persisted_planner_report(store=store, ref=report_ref, report=report)
        or validate_persisted_data_requirement_compilation_report(
            store,
            inputs.requirement_basis_binding,
            expected_report=inputs.compilation_report,
            require_selected_writer_profile=True,
        )
        or tuple(spec.model_dump(mode="json") for spec in inputs.compilation_report.specs)
        != inputs.compiled_requirement_specs
    ):
        raise ValueError("candidate_retained_planner_inputs_not_established")
    source_gap, refusal = _n7_bound_source_gap(
        prior.source.problem,
        grounding=projection.grounding,
        value_port=projection.value_port,
        selected_candidate_ref=projection.selected_candidate_id,
        selected_candidate_content_hash=projection.selected_candidate_content_hash,
        design_problem_basis_ref=record.design_problem_basis_ref,
        acquisition_request=inputs.acquisition_request,
    )
    accompanying = (
        (projection.grounding.acquisition_requirement,)
        if projection.grounding.acquisition_requirement is not None
        else ()
    )
    if report.schema_version == _N7_CONFIGURED_REPORT_SCHEMA:
        if record.retained_port_capture_ref is None or report.candidate_lineage is None:
            raise ValueError("candidate_retained_port_capture_not_established")
        capture = read_acquisition_evaluation_artifact(
            store=store,
            event_log=event_log,
            ref=record.retained_port_capture_ref,
            record_type=CandidateRetainedPortCapture,
        )
        if type(capture) is not CandidateRetainedPortCapture:
            raise ValueError("candidate_retained_port_capture_not_established")
        port = _n7_load_configured_candidate_port_source(store, capture.configured_port_source_ref)
        if (
            any(
                getattr(capture, name) != getattr(record, name)
                for name in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "action_job_id",
                    "action_generation",
                    "route_id",
                    "compiled_ref",
                    "design_problem_ref",
                    "design_problem_basis_ref",
                    "candidate_id",
                )
            )
            or any(
                not _candidate_ref_same(getattr(capture, name), getattr(record, name))
                for name in (
                    "candidate_action_ref",
                    "candidate_world_intent_ref",
                    "candidate_source_ref",
                    "evaluation_decision_ref",
                    "current_basis_ref",
                )
            )
            or not _candidate_ref_same(
                capture.configured_port_source_ref, report.candidate_lineage.port_source_ref
            )
            or not _candidate_model_values_same(
                capture.retained_evaluation, record.retained_evaluation
            )
            or not _candidate_ref_same(capture.reuse_occurrence_ref, occurrence)
            or capture.budget_observation_before != record.budget_observation_before
            or capture.budget_observation_after != record.budget_observation_after
            or (
                port.tenant_id,
                port.cell_id,
                port.run_id,
                port.source_job_id,
                port.source_generation_run_id,
                port.cycle_index,
                port.candidate_id,
                port.candidate_content_hash,
                port.design_problem_basis_ref,
            )
            != (
                record.tenant_id,
                record.cell_id,
                record.run_id,
                prior.selected.evaluation_job_id,
                prior.selected.generation_run_id,
                prior.selected.cycle_index,
                prior.selected.candidate_id,
                prior.selected.candidate_content_hash,
                prior.selected.design_problem_ref,
            )
            or any(
                not _candidate_ref_same(actual, expected)
                for actual, expected in (
                    (port.n4_source_ref, prior.selected.n4_source_ref),
                    (port.context_job_ref, prior.selected.context_job_ref),
                    (port.n5_input_ref, prior.selected.n5_input_ref),
                    (port.n5_execution_ref, prior.selected.n5_execution_ref),
                    (port.n5_result_ref, prior.selected.n5_result_ref),
                )
            )
            or not _candidate_model_values_same(
                CandidateGroundingObservation.model_validate(port.grounding_observation),
                projection.grounding,
            )
            or not _candidate_model_values_same(
                ValuePortObservation.model_validate(port.value_observation), projection.value_port
            )
            or not _candidate_model_values_same(port.source_gap, source_gap)
            or len(port.accompanying_requirement_gaps) != len(accompanying)
            or any(
                not _candidate_model_values_same(actual, expected)
                for actual, expected in zip(
                    port.accompanying_requirement_gaps, accompanying, strict=True
                )
            )
        ):
            raise ValueError("candidate_retained_port_capture_mismatch")
    elif record.retained_port_capture_ref is not None:
        raise ValueError("candidate_retained_port_capture_unexpected")
    if (
        refusal is not None
        or source_gap is None
        or not _n7_candidate_n5_l1_planner_records_match(
            source_gap=source_gap,
            accompanying_requirement_gaps=accompanying,
            specs=inputs.compilation_report.specs,
            capability_resolutions=inputs.compilation_report.capability_requirement_resolutions,
            report=report,
        )
    ):
        # Empty refusals remain visible, but this version has no independent
        # owner replay for their compiler-routing cause and cannot select them.
        raise ValueError("candidate_retained_planner_projection_not_established")
    selected_rows = tuple(
        row
        for row in report.acquisition_records
        if source_gap.requirement_gap_id in row.scenario_requirement_refs
    )
    distributions = _requirement_missing_distributions(source_gap)
    expected_cost = (
        produce_acquisition_cost_basis_record(
            missing_distribution=distributions[0], strategy=selected_rows[0].recommended_strategy
        )
        if report.status != "blocked" and len(selected_rows) == 1 and len(distributions) == 1
        else None
    )
    if projection.current_cost_basis != expected_cost:
        raise ValueError("candidate_retained_planner_cost_mismatch")
    if (
        snapshot.world_model_record_ref != prior.selected.world_model_record_hash
        or snapshot.world_ref != prior.selected.world_model_record_hash
        or not _candidate_ref_same(snapshot.current_candidate_basis_ref, record.current_basis_ref)
        or not _candidate_ref_same(
            snapshot.current_candidate_action_ref, record.candidate_action_ref
        )
        or not _candidate_ref_same(
            snapshot.current_candidate_source_ref, record.candidate_source_ref
        )
    ):
        raise ValueError("candidate_retained_planner_source_mismatch")
    return record, prior


def read_acquisition_retained_continuation(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
    decision: AcquisitionEvaluationDecision,
    terminal: AcquisitionRouteLoopReceiptV2,
) -> AcquisitionRetainedContinuation:
    """Reopen producer/event/profile, exact action/evaluation and compiler joins."""
    record = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=ref,
        record_type=AcquisitionRetainedContinuation,
    )
    if type(record) is not AcquisitionRetainedContinuation:
        raise TypeError("acquisition_retained_continuation_reader_mismatch")
    for name in (
        "tenant_id",
        "cell_id",
        "run_id",
        "source_job_id",
        "action_job_id",
        "action_generation",
        "route_id",
        "compiled_ref",
        "design_problem_ref",
        "candidate_id",
    ):
        if getattr(record, name) != getattr(decision, name):
            raise ValueError("acquisition_retained_continuation_action_mismatch:" + name)
    if (
        record.evaluation_decision_ref != terminal.evaluation_decision_ref
        or record.current_basis_ref != decision.current_basis_ref
        or record.selected_action_receipt_ref != decision.selected_action_receipt_ref
        or record.growth_receipt_ref != decision.growth_receipt_ref
        or record.admitted_source_ref != decision.admitted_source_ref
        or record.retained_evaluation != terminal.selected_evaluation
        or record.retained_evaluation != decision.prior_evaluation
    ):
        raise ValueError("acquisition_retained_continuation_selected_join_mismatch")
    from polisyos.runtime.quality.generation_cycle import (
        _counterexample_record,
        _default_revision_request,
        _refinement_decision,
        _search_iteration,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    source = GenerationSourceRepository(store).load_candidate_scenario_source_in_owner_scope(
        record.retained_evaluation.n4_source_ref,
        expected_run_id=record.run_id,
        expected_tenant_id=record.tenant_id,
        expected_cell_id=record.cell_id,
    )
    if (
        type(source) is not N4CandidateScenarioSourceRecordV3
        or source.candidate is None
        or source.candidate.candidate_id != record.candidate_id
        or source.candidate.atom.content_hash != record.retained_evaluation.candidate_content_hash
        or source.cycle_problem_ref != record.retained_evaluation.design_problem_ref
    ):
        raise ValueError("acquisition_retained_current_diagnostic_source_mismatch")
    projection = record.current_projection
    common: _ReactionIdentityInputs = {
        "problem": source.problem,
        "cycle_index": projection.source_cycle_index,
        "candidate_id": record.candidate_id,
        "source_reaction_ref": record.current_basis_ref,
    }
    counterexample = _counterexample_record(
        **common,
        grounding=projection.grounding,
        value_port=projection.value_port,
    )
    request = projection.revision_request.strategy_payload.get("acquisition_request")
    source_driver_rule = request.get("n7_source_driver_rule") if isinstance(request, dict) else None
    source_join_rule = request.get("n7_source_join_rule") if isinstance(request, dict) else None
    if (
        source_driver_rule is not None
        and source_driver_rule != "policyos.runtime.n7_source_driver.v1"
    ):
        raise ValueError("acquisition_retained_source_driver_rule_unsupported")
    if source_join_rule is not None and source_join_rule != _N7_SOURCE_JOIN_RULE:
        raise ValueError("acquisition_retained_source_join_rule_unsupported")
    if source_driver_rule is not None and source_join_rule is None:
        raise ValueError("acquisition_retained_source_driver_rule_unbound")
    revision = _default_revision_request(
        **common,
        terminal_kind=projection.terminal_kind,
        counterexample=counterexample,
        grounding=projection.grounding,
        value_port=projection.value_port,
        source_issue_rule=source_join_rule is not None,
    )
    refinement = _refinement_decision(
        **common,
        counterexample=counterexample,
        revision=revision,
        next_action=projection.voi_decision,
    )
    iteration = _search_iteration(
        **common,
        counterexample=counterexample,
        decision=refinement,
        next_action=projection.voi_decision,
    )
    for actual, expected in (
        (projection.counterexample, counterexample),
        (projection.revision_request, revision),
        (projection.refinement_decision, refinement),
        (projection.search_iteration, iteration),
    ):
        if exact_n5_content_bytes(actual) != exact_n5_content_bytes(expected):
            raise ValueError("acquisition_retained_current_diagnostic_owner_replay_mismatch")
    report = projection.current_planner_report
    if report is not None:
        ref = projection.current_planner_report_ref
        if ref is None or report.requirement_basis_binding is None:
            raise ValueError("acquisition_retained_current_requirement_not_established")
        loaded = load_acquisition_planner_report(store, ref)
        if loaded != report:
            raise ValueError("acquisition_retained_current_planner_readback_mismatch")
        binding = report.requirement_basis_binding
        planner_inputs = projection.current_planner_inputs
        if (
            planner_inputs is None
            or planner_inputs.run_id != report.run_id
            or planner_inputs.generated_at != report.generated_at
            or planner_inputs.requirement_basis_binding != binding
            or planner_inputs.world_snapshot != projection.current_planner_world_snapshot
            or planner_inputs.planner_content_hash() != report.planning_context_hash
        ):
            raise ValueError("acquisition_retained_actual_planner_input_mismatch")
        if validate_persisted_data_requirement_compilation_report(
            store,
            binding,
            expected_report=planner_inputs.compilation_report,
        ):
            raise ValueError("acquisition_retained_actual_compiler_input_unverified")
        # Walk every actual routed requirement. A present report string or
        # embedded compiler payload cannot substitute for the shared verifier.
        for row in report.acquisition_records:
            issues = validate_persisted_acquisition_planner_report(
                store,
                ref,
                report,
                expected_scenario_id=binding.scenario_id,
                expected_compiled_requirement_ref=row.compiled_requirement_ref,
            )
            if issues:
                raise ValueError("acquisition_retained_current_planner_unverified")
        source_requirement = _cycle_acquisition_requirement(
            projection.grounding,
            projection.value_port,
        )
        source_rule = planner_inputs.acquisition_request.get("n7_source_join_rule")
        if source_rule != source_join_rule:
            raise ValueError("acquisition_retained_source_join_rule_mismatch")
        # The retained owner does not currently produce the inline candidate
        # checkpoint; do not accept an unexplained injected checkpoint here.
        if source_rule is not None and (
            not isinstance(request, dict)
            or planner_inputs.acquisition_request
            != {**request, "cycle_index": projection.source_cycle_index}
        ):
            raise ValueError("acquisition_retained_source_request_mismatch")
        semantic_rows = tuple(
            row
            for row in report.acquisition_records
            if row.requirement_schema_version
            in {
                "policyos.runtime.l1_variable_availability_gap.v1",
                "policyos.runtime.grounding_coverage_gap.v1",
            }
        )
        if source_requirement is None:
            if source_rule is not None or semantic_rows:
                raise ValueError("acquisition_retained_source_requirement_missing")
        elif report.acquisition_records:
            source_gap, refusal = _n7_bound_source_gap(
                source.problem,
                grounding=projection.grounding,
                value_port=projection.value_port,
                selected_candidate_ref=projection.selected_candidate_id,
                selected_candidate_content_hash=projection.selected_candidate_content_hash,
                design_problem_basis_ref=record.retained_evaluation.design_problem_ref,
                acquisition_request=planner_inputs.acquisition_request,
            )
            compiler_report = planner_inputs.compilation_report
            if (
                refusal is not None
                or source_gap is None
                or tuple(spec.model_dump(mode="json") for spec in compiler_report.specs)
                != planner_inputs.compiled_requirement_specs
            ):
                raise ValueError("acquisition_retained_source_projection_mismatch")
            if source_rule == _N7_SOURCE_JOIN_RULE:
                valid_source_projection = _n7_joined_planner_records_match(
                    problem=source.problem,
                    acquisition_request=planner_inputs.acquisition_request,
                    source_gap=source_gap,
                    specs=compiler_report.specs,
                    capability_resolutions=compiler_report.capability_requirement_resolutions,
                    report=report,
                )
            else:
                valid_source_projection = _n7_legacy_planner_records_match(
                    source_gap=source_gap,
                    specs=compiler_report.specs,
                    capability_resolutions=compiler_report.capability_requirement_resolutions,
                    report=report,
                )
            if not valid_source_projection:
                raise ValueError("acquisition_retained_source_projection_mismatch")
        elif source_rule is not None and report.basis_limitation_code is None:
            raise ValueError("acquisition_retained_source_projection_mismatch")
        snapshot = projection.current_planner_world_snapshot
        if snapshot is None or snapshot.world_model_record_ref != (
            record.retained_evaluation.world_model_record_hash
        ):
            raise ValueError("acquisition_retained_planner_evaluation_world_mismatch")
        for name, expected in (
            ("current_acquisition_basis_ref", record.current_basis_ref),
            ("current_acquisition_growth_ref", record.growth_receipt_ref),
            ("current_acquisition_source_ref", record.admitted_source_ref),
        ):
            actual = getattr(snapshot, name, None)
            if actual is None or artifact_ref_identity_key(actual) != artifact_ref_identity_key(
                expected
            ):
                raise ValueError("acquisition_retained_planner_current_source_mismatch")
    return record
