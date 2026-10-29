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

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceiptV2
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


class _ReactionIdentityInputs(TypedDict):
    problem: DesignProblem
    cycle_index: int
    candidate_id: str
    source_reaction_ref: ArtifactRef


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
