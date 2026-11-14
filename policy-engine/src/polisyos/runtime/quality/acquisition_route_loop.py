"""Crash-safe orchestration for costed and bounded candidate acquisition routes."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import canon
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    artifact_ref_identity_key,
    load_core_json_artifact,
)
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionSelectedEvaluation,
    CandidateEvaluationTerminalHistory,
    CandidateExperimentTerminalHistory,
    _candidate_model_values_same,
    _candidate_ref_same,
)
from polisyos.runtime.quality.acquisition_planner import (
    _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
    _N7_CONFIGURED_REPORT_SCHEMA,
    _N7_SOURCE_DESCRIPTOR_JOIN_RULE,
    _N7_SOURCE_JOIN_RULE,
    AcquisitionActionRecord,
    AcquisitionCostBasisRecord,
    AcquisitionPlannerReport,
    AcquisitionRequirementGap,
    _n7_candidate_n5_l1_planner_records_match,
    _n7_load_derivation_bundle,
    _n7_require_current_report_input_provenance,
    load_planner_acquisition_cost_schedule,
    produce_acquisition_cost_basis_record,
    validate_persisted_acquisition_planner_report,
    validate_persisted_data_requirement_compilation_report,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    CandidateSourceReentryReceipt,
    GenerationCycleRecord,
    GenerationCycleRun,
    LoopVOIDecision,
    _cycle_acquisition_requirement,
    _cycle_basis_ref,
    _n7_cycle_source_gap,
    _n7_generic_fallback_source_record_matches,
    _n7_joined_planner_records_match,
    _problem_ref,
    generation_cycle_run_content_hash,
    validate_acquisition_overlay_continuation,
    validate_candidate_source_continuation,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.services.adapters.core_run import TerminalCoreRunSource
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        OriginalRunBudgetScopeEvidence,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        _CandidateExperimentHistoryPrefix,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedPolicyBinding,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.model_input_requirements import SelectedProgramGraphInputBasis
    from polisyos.runtime.quality.model_input_routing import ModelInputRoutingReport


class _ArtifactSchema(Protocol):
    name: str
    version: str


class _ArtifactProducer(Protocol):
    component: str


class _ArtifactManifest(Protocol):
    kind: str
    artifact_schema: _ArtifactSchema | None
    producer: _ArtifactProducer | None


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> _ArtifactManifest: ...


class AcquisitionRouteClosureError(ValueError):
    """Typed fail-closed current-route resolution error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _select_source_planner_record(
    report: AcquisitionPlannerReport,
    source: AcquisitionRequirementGap | None,
) -> AcquisitionActionRecord:
    """Select one source action without dropping other compiler gaps."""
    records = report.acquisition_records
    if len(records) == 1:
        return records[0]
    if source is None:
        raise AcquisitionRouteClosureError("costed_route_not_unique")
    selected = tuple(
        record
        for record in records
        if record.requirement_gap_ref == source.requirement_gap_id
        and record.requirement_schema_version == source.requirement_schema_version
        and record.gap_type == source.gap_type
        and record.compiled_requirement_ref != source.compiled_requirement_ref
    )
    if selected:
        if len(selected) != 1:
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        return selected[0]
    fallback_candidates = tuple(
        record
        for record in records
        if source.requirement_gap_id in record.scenario_requirement_refs
    )
    if len(fallback_candidates) != 1 or not _n7_generic_fallback_source_record_matches(
        source, fallback_candidates[0]
    ):
        raise AcquisitionRouteClosureError("costed_route_not_unique")
    return fallback_candidates[0]


class AcquisitionRouteRecoveryRequired(RuntimeError):  # noqa: N818 - exact lifecycle signal
    """Raised after the durable world-commit head requires re-entry recovery."""


def _resolve_source_cycle_problem_basis(
    *,
    generation_run: GenerationCycleRun,
    source_cycle: GenerationCycleRecord,
    design_problem: DesignProblem,
    design_problem_ref: str,
    acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = (),
    candidate_basis_transitions: tuple[CandidateSourceReentryReceipt, ...] = (),
) -> DesignProblem:
    """Compose verified source refreshes separately from actual design revisions.

    The route owner's action fold supplies the acquisition proofs only after
    selected CAS, event, action and append-only continuation replay. A receipt
    object or same-basis declaration supplied by a caller is not admission;
    mutation consumers must obtain this closure from that live owner again.
    """

    if (
        _problem_ref(design_problem) != design_problem_ref
        or generation_run.design_problem_ref != design_problem_ref
    ):
        raise AcquisitionRouteClosureError("source_cycle_subject_binding_mismatch")
    indexes = tuple(cycle.cycle_index for cycle in generation_run.cycles)
    if len(indexes) != len(set(indexes)):
        raise AcquisitionRouteClosureError("source_cycle_basis_chain_invalid")
    matching_source = tuple(
        cycle for cycle in generation_run.cycles if cycle.cycle_index == source_cycle.cycle_index
    )
    if matching_source != (source_cycle,):
        raise AcquisitionRouteClosureError("source_cycle_not_in_generation_run")
    prefix = tuple(
        sorted(
            (
                cycle
                for cycle in generation_run.cycles
                if cycle.cycle_index <= source_cycle.cycle_index
            ),
            key=lambda cycle: cycle.cycle_index,
        )
    )
    if tuple(cycle.cycle_index for cycle in prefix) != tuple(range(source_cycle.cycle_index + 1)):
        raise AcquisitionRouteClosureError("source_cycle_basis_predecessor_missing")

    transitions: dict[int, AcquisitionOverlayReentryReceipt | CandidateSourceReentryReceipt] = {}
    for transition in acquisition_basis_transitions:
        index = transition.new_cycle.cycle_index
        continued = transition.continued_generation_run
        if (
            index in transitions
            or not transition.schema_version.endswith(".v3")
            or transition.source_cycle_index + 1 != index
            or transition.design_problem_ref != design_problem_ref
            or continued is None
            or continued.run_id != generation_run.run_id
            or continued.cycles != generation_run.cycles[: index + 1]
            or transition.new_cycle != continued.cycles[-1]
        ):
            raise AcquisitionRouteClosureError("source_acquisition_basis_transition_invalid")
        transitions[index] = transition
    for transition in candidate_basis_transitions:
        index = transition.new_cycle.cycle_index
        continued = transition.continued_generation_run
        if (
            index in transitions
            or transition.source_cycle_index + 1 != index
            or transition.design_problem_ref != design_problem_ref
            or continued.run_id != generation_run.run_id
            or continued.cycles != generation_run.cycles[: index + 1]
            or transition.new_cycle != continued.cycles[-1]
        ):
            raise AcquisitionRouteClosureError("source_candidate_basis_transition_invalid")
        transitions[index] = transition
    expected_basis = design_problem
    for cycle in prefix:
        if cycle.design_problem_ref != design_problem_ref or _cycle_basis_ref(
            cycle
        ) != _problem_ref(expected_basis):
            raise AcquisitionRouteClosureError("source_cycle_basis_chain_invalid")
        if cycle.cycle_index == source_cycle.cycle_index:
            return expected_basis
        transition = transitions.get(cycle.cycle_index + 1)
        if transition is None:
            expected_basis = cycle.revision_request.revised_problem
        elif transition.source_candidate_ref != cycle.selected_candidate_ref or _cycle_basis_ref(
            transition.new_cycle
        ) != _problem_ref(expected_basis):
            raise AcquisitionRouteClosureError("source_acquisition_basis_transition_invalid")
    raise AcquisitionRouteClosureError("source_cycle_basis_unresolved")


class AcquisitionRoutePhaseReceipt(BaseModel):
    """Immutable phase fact for one exact acquisition action generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "AcquisitionRoutePhaseReceipt@1.0",
        "AcquisitionRoutePhaseReceipt@1.1",
        "AcquisitionRoutePhaseReceipt@1.2",
    ] = "AcquisitionRoutePhaseReceipt@1.0"
    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planner_report_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    coarse_phase: Literal["requested", "executing", "world_committed", "candidate_input_prepared"]
    receipt_phase: Literal[
        "requested",
        "executing",
        "outcome_selected",
        "world_committed_reentry_pending",
        "candidate_input_reentry_pending",
    ]
    recovery_state: Literal["none", "reentry_recovery_required"]
    predecessor_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    owner_receipt_refs: tuple[str, ...] = ()
    candidate_receipt_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_phase_truth(self) -> AcquisitionRoutePhaseReceipt:
        expected = {
            "requested": ("requested", "none"),
            "executing": ("executing", "none"),
            "outcome_selected": ("executing", "none"),
            "world_committed_reentry_pending": (
                "world_committed",
                "reentry_recovery_required",
            ),
            "candidate_input_reentry_pending": (
                "candidate_input_prepared",
                "reentry_recovery_required",
            ),
        }[self.receipt_phase]
        if (self.coarse_phase, self.recovery_state) != expected:
            raise ValueError("acquisition_route_phase_state_mismatch")
        if self.receipt_phase == "requested" and self.predecessor_receipt_ref is not None:
            raise ValueError("requested_phase_cannot_have_predecessor")
        if self.receipt_phase != "requested" and self.predecessor_receipt_ref is None:
            raise ValueError("acquisition_route_phase_predecessor_missing")
        if self.receipt_phase == "outcome_selected":
            if (
                self.schema_version
                not in {
                    "AcquisitionRoutePhaseReceipt@1.1",
                    "AcquisitionRoutePhaseReceipt@1.2",
                }
                or len(self.owner_receipt_refs) != 1
            ):
                raise ValueError("acquisition_action_selection_binding_invalid")
        elif self.receipt_phase == "candidate_input_reentry_pending":
            if self.schema_version != "AcquisitionRoutePhaseReceipt@1.2":
                raise ValueError("acquisition_route_phase_schema_version_mismatch")
        elif self.schema_version != "AcquisitionRoutePhaseReceipt@1.0":
            raise ValueError("acquisition_route_phase_schema_version_mismatch")
        if self.schema_version == "AcquisitionRoutePhaseReceipt@1.2":
            if (
                self.candidate_receipt_ref is None
                or self.candidate_receipt_ref.kind
                != "runtime_quality.acquisition_candidate_action_receipt"
                or self.candidate_receipt_ref.manifest_profile_sha256 is None
                or str(self.candidate_receipt_ref.artifact_id) not in self.owner_receipt_refs
            ):
                raise ValueError("candidate_phase_selected_profile_missing")
        elif self.candidate_receipt_ref is not None:
            raise ValueError("candidate_phase_selected_profile_unexpected")
        if (
            self.receipt_phase
            in {"world_committed_reentry_pending", "candidate_input_reentry_pending"}
            and not self.owner_receipt_refs
        ):
            raise ValueError("world_commit_owner_receipt_missing")
        return self


class AcquisitionRouteLoopReceipt(BaseModel):
    """Immutable terminal fact for one exact acquisition action generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "AcquisitionRouteLoopReceipt@1.0", "AcquisitionRouteLoopReceipt@1.1"
    ] = "AcquisitionRouteLoopReceipt@1.0"
    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planner_report_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal[
        "quarantined_no_growth", "reentry_completed", "candidate_reentry_completed"
    ]
    predecessor_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    reentry_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    candidate_action_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_reentry_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_terminal_truth(self) -> AcquisitionRouteLoopReceipt:
        if self.terminal_outcome in {"reentry_completed", "candidate_reentry_completed"}:
            if self.reentry_receipt_ref is None:
                raise ValueError("terminal_reentry_receipt_missing")
        elif self.reentry_receipt_ref is not None:
            raise ValueError("quarantined_terminal_cannot_claim_reentry")
        if self.terminal_outcome == "candidate_reentry_completed":
            if (
                self.schema_version != "AcquisitionRouteLoopReceipt@1.1"
                or self.candidate_action_ref is None
                or self.candidate_action_ref.kind
                != "runtime_quality.acquisition_candidate_action_receipt"
                or self.candidate_action_ref.manifest_profile_sha256 is None
                or str(self.candidate_action_ref.artifact_id) not in self.owner_receipt_refs
                or self.candidate_reentry_ref is None
                or self.candidate_reentry_ref.kind
                != "runtime_quality.candidate_source_reentry_receipt"
                or self.candidate_reentry_ref.manifest_profile_sha256 is None
                or str(self.candidate_reentry_ref.artifact_id) != self.reentry_receipt_ref
            ):
                raise ValueError("terminal_candidate_input_binding_missing")
        elif (
            self.schema_version != "AcquisitionRouteLoopReceipt@1.0"
            or self.candidate_action_ref is not None
            or self.candidate_reentry_ref is not None
        ):
            raise ValueError("terminal_candidate_input_schema_mismatch")
        return self


class AcquisitionRouteLoopReceiptV2(BaseModel):
    """Versioned terminal separating source admission from selected evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteLoopReceipt@2.0"] = "AcquisitionRouteLoopReceipt@2.0"
    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planner_report_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal[
        "quarantined_no_growth", "reentry_completed", "source_admitted_evaluation_retained"
    ]
    predecessor_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    reentry_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    evaluation_decision_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    selected_evaluation_witness_ref: ArtifactRef
    selected_evaluation: AcquisitionSelectedEvaluation | None = None
    current_continuation_ref: ArtifactRef | None = None
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_terminal_truth(self) -> AcquisitionRouteLoopReceiptV2:
        if self.terminal_outcome == "reentry_completed":
            if self.reentry_receipt_ref is None or self.current_continuation_ref is not None:
                raise ValueError("terminal_reentry_receipt_missing_or_retained_continuation")
        elif self.reentry_receipt_ref is not None:
            raise ValueError("terminal_cannot_claim_new_reentry")
        if self.terminal_outcome == "source_admitted_evaluation_retained" and (
            self.selected_evaluation is None
            or self.selected_evaluation.basis_ref is None
            or self.current_continuation_ref is None
            or self.selected_evaluation.basis_ref != self.selected_basis_ref
            or self.selected_evaluation.n5_execution_ref != self.selected_evaluation_witness_ref
        ):
            raise ValueError("terminal_retained_evaluation_incomplete")
        for ref, kind in (
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.selected_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
        ):
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or (ref.manifest_profile_sha256 is None)
            ):
                raise ValueError("terminal_evaluation_selected_profile_missing")
        if self.selected_evaluation_witness_ref.manifest_profile_sha256 is None:
            raise ValueError("terminal_evaluation_witness_profile_missing")
        return self


class AcquisitionCandidateRouteLoopReceipt(BaseModel):
    """Candidate-only terminal with a separately fenced evaluation frontier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteLoopReceipt@3.0"] = "AcquisitionRouteLoopReceipt@3.0"
    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planner_report_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal["candidate_reentry_completed", "candidate_evaluation_retained"]
    predecessor_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    candidate_action_ref: ArtifactRef
    candidate_reentry_ref: ArtifactRef | None = None
    evaluation_decision_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    selected_evaluation_witness_ref: ArtifactRef
    selected_evaluation: AcquisitionSelectedEvaluation | None = None
    current_continuation_ref: ArtifactRef | None = None
    generated_at: AwareDatetime

    @property
    def reentry_receipt_ref(self) -> str | None:
        """Expose the immutable ID for existing terminal-reader projections."""
        return str(self.candidate_reentry_ref.artifact_id) if self.candidate_reentry_ref else None

    @model_validator(mode="after")
    def _validate_candidate_terminal(self) -> AcquisitionCandidateRouteLoopReceipt:
        def identity(ref: ArtifactRef | None) -> tuple[str, str, str, str | None] | None:
            if ref is None:
                return None
            if set(type(ref).model_fields) - set(ArtifactRef.model_fields):
                raise ValueError("candidate_terminal_ref_subtype_semantics_unsupported")
            return artifact_ref_identity_key(ref)

        required = (
            (self.candidate_action_ref, {"runtime_quality.acquisition_candidate_action_receipt"}),
            (self.evaluation_decision_ref, {"runtime_quality.acquisition_evaluation_decision"}),
            (self.selected_basis_ref, {"runtime_quality.acquisition_evaluation_basis"}),
            (
                self.selected_evaluation_witness_ref,
                {
                    "runtime.quality.candidate_simulation_execution",
                    "runtime_quality.candidate_source_reentry_receipt",
                },
            ),
        )
        if any(
            ref.kind not in kinds
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            or identity(ref) is None
            for ref, kinds in required
        ):
            raise ValueError("candidate_terminal_selected_profile_invalid")
        if str(self.candidate_action_ref.artifact_id) not in self.owner_receipt_refs:
            raise ValueError("candidate_terminal_action_owner_missing")
        if str(self.evaluation_decision_ref.artifact_id) not in self.owner_receipt_refs:
            raise ValueError("candidate_terminal_decision_owner_missing")
        # The selected evaluation may describe an owner-derived later cycle
        # for the same rooted candidate. Its effective content hash is bound
        # by historical replay, not inferred from this immutable policy scope.
        if self.selected_evaluation is not None and (
            identity(self.selected_evaluation.basis_ref) != identity(self.selected_basis_ref)
            or identity(self.selected_evaluation.n5_execution_ref)
            != identity(self.selected_evaluation_witness_ref)
        ):
            raise ValueError("candidate_terminal_evaluation_binding_invalid")
        if self.selected_evaluation is None and identity(
            self.selected_evaluation_witness_ref
        ) != identity(self.candidate_reentry_ref):
            raise ValueError("candidate_terminal_blocked_witness_invalid")
        if self.terminal_outcome == "candidate_reentry_completed":
            if (
                self.candidate_reentry_ref is None
                or self.candidate_reentry_ref.kind
                != "runtime_quality.candidate_source_reentry_receipt"
                or self.candidate_reentry_ref.media_type != "application/json"
                or self.candidate_reentry_ref.manifest_profile_sha256 is None
                or identity(self.candidate_reentry_ref) is None
                or self.current_continuation_ref is not None
            ):
                raise ValueError("candidate_terminal_reentry_invalid")
        elif (
            self.candidate_reentry_ref is not None
            or self.selected_evaluation is None
            or self.current_continuation_ref is None
            or self.current_continuation_ref.kind
            != "runtime_quality.candidate_acquisition_retained_continuation"
            or self.current_continuation_ref.media_type != "application/json"
            or self.current_continuation_ref.manifest_profile_sha256 is None
            or identity(self.current_continuation_ref) is None
            or identity(self.selected_evaluation.basis_ref) != identity(self.selected_basis_ref)
            or identity(self.selected_evaluation.n5_execution_ref)
            != identity(self.selected_evaluation_witness_ref)
        ):
            raise ValueError("candidate_terminal_retention_invalid")
        return self


_ExperimentOwnerRef = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


def _require_experiment_selected_ref(ref: ArtifactRef, kinds: frozenset[str]) -> None:
    """Check the selected view's shape; the sink must still replay its owner."""
    if (
        not _candidate_ref_same(ref, ref)
        or ref.kind not in kinds
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_experiment_selected_profile_invalid")


class _CandidateExperimentActionIdentity(BaseModel):
    """Shared immutable identity; no field here is itself an effect permit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1, strict=True)
    job_id: str = Field(min_length=1)
    source_payload_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    capability_manifest_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    policy_scope: CandidateUnpricedPolicyScope
    policy_ref: ArtifactRef
    authority_decision_ref: ArtifactRef
    voi_decision: LoopVOIDecision
    monetary_cost: Literal["not_established"] = "not_established"
    information_value: Literal["not_established"] = "not_established"
    observed_data_authority: Literal[False] = False
    publication_authority: Literal[False] = False
    predecessor_receipt_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[_ExperimentOwnerRef, ...] = ()
    generated_at: AwareDatetime

    @field_validator("observed_data_authority", "publication_authority", mode="before")
    @classmethod
    def _require_no_authority(cls, value: object) -> object:
        if value is not False:
            raise ValueError("candidate_experiment_authority_forbidden")
        return value

    @model_validator(mode="after")
    def _validate_identity(self) -> _CandidateExperimentActionIdentity:
        scope = self.policy_scope
        if (
            (scope.tenant_id, scope.cell_id, scope.run_id, scope.source_job_id)
            != (self.tenant_id, self.cell_id, self.run_id, self.source_job_id)
            or self.voi_decision.candidate_id != scope.candidate_id
            or self.voi_decision.scheduler_action != "reject"
            or self.voi_decision.scheduler_reason != "roi_below_threshold"
            or len(set(self.owner_receipt_refs)) != len(self.owner_receipt_refs)
        ):
            raise ValueError("candidate_experiment_identity_invalid")
        _require_experiment_selected_ref(
            self.policy_ref, frozenset({"runtime_quality.candidate_unpriced_acquisition_policy"})
        )
        _require_experiment_selected_ref(
            self.authority_decision_ref,
            frozenset({"runtime_quality.agent_action_authority_decision"}),
        )
        return self

    @property
    def compiled_ref(self) -> ArtifactRef:
        """Return the full selected compiled-source view."""
        return self.policy_scope.compiled_ref

    @property
    def planner_report_hash(self) -> str:
        """Return the selected planner report's content hash."""
        return self.policy_scope.planner_report_hash


class AcquisitionCandidateExperimentPhaseReceipt(_CandidateExperimentActionIdentity):
    """Immutable candidate-experiment phase, distinct from costed phases."""

    schema_version: Literal[
        "AcquisitionCandidateExperimentPhaseReceipt@1.0",
        "AcquisitionCandidateExperimentPhaseReceipt@2.0",
    ] = "AcquisitionCandidateExperimentPhaseReceipt@1.0"
    coarse_phase: Literal["requested", "executing", "candidate_input_prepared"]
    receipt_phase: Literal[
        "requested",
        "authorization_refreshed",
        "executing",
        "outcome_selected",
        "candidate_input_reentry_pending",
    ]
    recovery_state: Literal["none", "reentry_recovery_required"]
    candidate_receipt_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _validate_phase(self) -> AcquisitionCandidateExperimentPhaseReceipt:
        if (
            self.receipt_phase == "authorization_refreshed"
            and self.schema_version != "AcquisitionCandidateExperimentPhaseReceipt@2.0"
        ):
            raise ValueError("candidate_experiment_refresh_requires_v2")
        if (
            self.receipt_phase == "requested"
            and self.schema_version == "AcquisitionCandidateExperimentPhaseReceipt@2.0"
        ):
            raise ValueError("candidate_experiment_refresh_requires_original_requested_root")
        expected = {
            "requested": ("requested", "none"),
            "authorization_refreshed": ("requested", "none"),
            "executing": ("executing", "none"),
            "outcome_selected": ("executing", "none"),
            "candidate_input_reentry_pending": (
                "candidate_input_prepared",
                "reentry_recovery_required",
            ),
        }[self.receipt_phase]
        if (self.coarse_phase, self.recovery_state) != expected:
            raise ValueError("candidate_experiment_phase_state_mismatch")
        if (self.receipt_phase == "requested") != (self.predecessor_receipt_ref is None):
            raise ValueError("candidate_experiment_phase_predecessor_invalid")
        if self.receipt_phase in {"requested", "authorization_refreshed", "executing"}:
            if self.candidate_receipt_ref is not None or self.owner_receipt_refs:
                raise ValueError("candidate_experiment_phase_outcome_premature")
        else:
            if self.candidate_receipt_ref is None:
                raise ValueError("candidate_experiment_phase_action_missing")
            _require_experiment_selected_ref(
                self.candidate_receipt_ref,
                frozenset({"runtime_quality.acquisition_candidate_action_receipt"}),
            )
            action_ref = str(self.candidate_receipt_ref.artifact_id)
            if action_ref not in self.owner_receipt_refs or (
                self.receipt_phase == "outcome_selected"
                and self.owner_receipt_refs != (action_ref,)
            ):
                raise ValueError("candidate_experiment_phase_action_owner_missing")
        return self


class AcquisitionCandidateExperimentTerminalReceipt(_CandidateExperimentActionIdentity):
    """Candidate-only terminal; replay, not construction, establishes history."""

    schema_version: Literal["AcquisitionCandidateExperimentTerminalReceipt@1.0"] = (
        "AcquisitionCandidateExperimentTerminalReceipt@1.0"
    )
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal[
        "candidate_reentry_completed", "candidate_evaluation_retained", "candidate_blocked"
    ]
    candidate_action_ref: ArtifactRef
    candidate_reentry_ref: ArtifactRef | None = None
    evaluation_decision_ref: ArtifactRef | None = None
    selected_basis_ref: ArtifactRef | None = None
    selected_evaluation_witness_ref: ArtifactRef | None = None
    selected_evaluation: AcquisitionSelectedEvaluation | None = None
    current_continuation_ref: ArtifactRef | None = None
    blocker_ref: ArtifactRef | None = None
    blocker_reason: str | None = Field(default=None, min_length=1)

    @property
    def reentry_receipt_ref(self) -> str | None:
        """Expose the selected re-entry ID without asserting its authority."""
        return str(self.candidate_reentry_ref.artifact_id) if self.candidate_reentry_ref else None

    @model_validator(mode="after")
    def _validate_terminal(self) -> AcquisitionCandidateExperimentTerminalReceipt:
        if self.predecessor_receipt_ref is None:
            raise ValueError("candidate_experiment_terminal_predecessor_missing")
        _require_experiment_selected_ref(
            self.candidate_action_ref,
            frozenset({"runtime_quality.acquisition_candidate_action_receipt"}),
        )
        if str(self.candidate_action_ref.artifact_id) not in self.owner_receipt_refs:
            raise ValueError("candidate_experiment_terminal_action_owner_missing")
        if self.terminal_outcome == "candidate_blocked":
            if (
                self.blocker_ref is None
                or self.blocker_reason is None
                or not self.blocker_reason.strip()
                or any(
                    item is not None
                    for item in (
                        self.candidate_reentry_ref,
                        self.evaluation_decision_ref,
                        self.selected_basis_ref,
                        self.selected_evaluation_witness_ref,
                        self.selected_evaluation,
                        self.current_continuation_ref,
                    )
                )
            ):
                raise ValueError("candidate_experiment_terminal_blocked_invalid")
            _require_experiment_selected_ref(self.blocker_ref, frozenset({self.blocker_ref.kind}))
            if str(self.blocker_ref.artifact_id) not in self.owner_receipt_refs:
                raise ValueError("candidate_experiment_terminal_blocker_owner_missing")
            return self
        if self.blocker_ref is not None or self.blocker_reason is not None:
            raise ValueError("candidate_experiment_terminal_blocker_unexpected")
        if (
            self.evaluation_decision_ref is None
            or self.selected_basis_ref is None
            or self.selected_evaluation_witness_ref is None
        ):
            raise ValueError("candidate_experiment_terminal_evaluation_missing")
        _require_experiment_selected_ref(
            self.evaluation_decision_ref,
            frozenset({"runtime_quality.acquisition_evaluation_decision"}),
        )
        _require_experiment_selected_ref(
            self.selected_basis_ref, frozenset({"runtime_quality.acquisition_evaluation_basis"})
        )
        _require_experiment_selected_ref(
            self.selected_evaluation_witness_ref,
            frozenset(
                {
                    "runtime.quality.candidate_simulation_execution",
                    "runtime_quality.candidate_source_reentry_receipt",
                }
            ),
        )
        if str(self.evaluation_decision_ref.artifact_id) not in self.owner_receipt_refs:
            raise ValueError("candidate_experiment_terminal_decision_owner_missing")
        if self.selected_evaluation is not None and (
            self.selected_evaluation.candidate_id != self.policy_scope.candidate_id
            or self.selected_evaluation.design_problem_ref
            != self.policy_scope.design_problem_basis_ref
            or self.selected_evaluation.evaluation_run_id != self.run_id
            or not _candidate_ref_same(self.selected_evaluation.basis_ref, self.selected_basis_ref)
            or not _candidate_ref_same(
                self.selected_evaluation.n5_execution_ref, self.selected_evaluation_witness_ref
            )
        ):
            raise ValueError("candidate_experiment_terminal_evaluation_mismatch")
        if self.terminal_outcome == "candidate_reentry_completed":
            if self.candidate_reentry_ref is None or self.current_continuation_ref is not None:
                raise ValueError("candidate_experiment_terminal_reentry_invalid")
            _require_experiment_selected_ref(
                self.candidate_reentry_ref,
                frozenset({"runtime_quality.candidate_source_reentry_receipt"}),
            )
            if self.selected_evaluation is None and not _candidate_ref_same(
                self.selected_evaluation_witness_ref, self.candidate_reentry_ref
            ):
                raise ValueError("candidate_experiment_terminal_blocked_witness_invalid")
        else:
            if (
                self.candidate_reentry_ref is not None
                or self.selected_evaluation is None
                or self.current_continuation_ref is None
            ):
                raise ValueError("candidate_experiment_terminal_retention_invalid")
            _require_experiment_selected_ref(
                self.current_continuation_ref,
                frozenset({"runtime_quality.candidate_acquisition_retained_continuation"}),
            )
        return self


class AcquisitionCandidateExperimentTerminalReceiptV2(
    AcquisitionCandidateExperimentTerminalReceipt
):
    """Candidate-only no-fetch terminal bound to a selected reuse occurrence.

    ``run_lifecycle`` must persist the occurrence before this terminal. The
    terminal-history owner must reopen its manifest and verify the role-tagged
    exact prior action/source/N5 references before accepting reuse. This model
    validates the selected view and owner closure; parsing alone does not prove
    the persisted occurrence contents or authorize an effect.
    """

    schema_version: Literal["AcquisitionCandidateExperimentTerminalReceipt@2.0"] = (
        "AcquisitionCandidateExperimentTerminalReceipt@2.0"
    )
    terminal_outcome: Literal["candidate_evaluation_retained", "candidate_blocked"]
    candidate_reentry_ref: Literal[None] = None
    reuse_occurrence_ref: ArtifactRef

    @model_validator(mode="after")
    def _validate_reuse_terminal(self) -> AcquisitionCandidateExperimentTerminalReceiptV2:
        _require_experiment_selected_ref(
            self.reuse_occurrence_ref,
            frozenset({"runtime_quality.candidate_experiment_reuse_occurrence"}),
        )
        if str(self.reuse_occurrence_ref.artifact_id) not in self.owner_receipt_refs:
            raise ValueError("candidate_experiment_terminal_reuse_occurrence_owner_missing")
        return self


def parse_acquisition_route_phase_receipt(
    value: object,
) -> AcquisitionRoutePhaseReceipt | AcquisitionCandidateExperimentPhaseReceipt:
    """Select the explicitly versioned phase without coercing one family to another."""
    if isinstance(
        value, (AcquisitionRoutePhaseReceipt, AcquisitionCandidateExperimentPhaseReceipt)
    ):
        value = value.model_dump(mode="python")
    if not isinstance(value, dict):
        raise ValueError("acquisition_phase_payload_not_mapping")
    if value.get("schema_version") == "AcquisitionCandidateExperimentPhaseReceipt@1.0":
        return AcquisitionCandidateExperimentPhaseReceipt.model_validate(value)
    return AcquisitionRoutePhaseReceipt.model_validate(value)


def parse_acquisition_route_loop_receipt(
    value: object,
) -> (
    AcquisitionRouteLoopReceipt
    | AcquisitionRouteLoopReceiptV2
    | AcquisitionCandidateRouteLoopReceipt
    | AcquisitionCandidateExperimentTerminalReceipt
    | AcquisitionCandidateExperimentTerminalReceiptV2
):
    """Select the exact versioned reader; legacy serialized meaning is unchanged."""
    if isinstance(
        value,
        (
            AcquisitionRouteLoopReceipt,
            AcquisitionRouteLoopReceiptV2,
            AcquisitionCandidateRouteLoopReceipt,
            AcquisitionCandidateExperimentTerminalReceipt,
            AcquisitionCandidateExperimentTerminalReceiptV2,
        ),
    ):
        value = value.model_dump(mode="python")
    if not isinstance(value, dict):
        raise ValueError("acquisition_terminal_payload_not_mapping")
    if value.get("schema_version") == "AcquisitionRouteLoopReceipt@2.0":
        return AcquisitionRouteLoopReceiptV2.model_validate(value)
    if value.get("schema_version") == "AcquisitionRouteLoopReceipt@3.0":
        return AcquisitionCandidateRouteLoopReceipt.model_validate(value)
    if value.get("schema_version") == "AcquisitionCandidateExperimentTerminalReceipt@1.0":
        return AcquisitionCandidateExperimentTerminalReceipt.model_validate(value)
    if value.get("schema_version") == "AcquisitionCandidateExperimentTerminalReceipt@2.0":
        return AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(value)
    return AcquisitionRouteLoopReceipt.model_validate(value)


AcquisitionTerminalReceipt = (
    AcquisitionRouteLoopReceipt
    | AcquisitionRouteLoopReceiptV2
    | AcquisitionCandidateRouteLoopReceipt
    | AcquisitionCandidateExperimentTerminalReceipt
    | AcquisitionCandidateExperimentTerminalReceiptV2
)


class AcquisitionRoutePhaseHead(Protocol):
    """Read-back fields required from one durable acquisition phase head."""

    receipt_ref: str
    receipt_phase: str
    recovery_state: str


class AcquisitionRoutePhaseSink(Protocol):
    """Persistence surface required by the crash-safe route helpers."""

    def persist_phase(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead: ...

    def persist_terminal(
        self,
        receipt: AcquisitionTerminalReceipt,
    ) -> AcquisitionRoutePhaseHead: ...

    def get_head(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead | None: ...


class CompletedControlJobCoreSourceResolver(Protocol):
    """HTTP-composed port for exact completed-job to Core-attempt source intake."""

    def __call__(
        self,
        job: ControlJobRecord,
        *,
        expected_control_run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> TerminalCoreRunSource: ...


class VerifiedAcquisitionRouteClosure(BaseModel):
    """Content-bound route origin and latest verified continuation closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    source_payload_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    capability_manifest_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compiled_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_event_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem: DesignProblem
    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    route_source_cycle_index: int = Field(ge=0)
    planner_report: AcquisitionPlannerReport
    planner_record: AcquisitionActionRecord
    cost_basis_record: AcquisitionCostBasisRecord
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    # Transport only. The actual action fold replayed these selected receipts;
    # the production mutation bridge re-resolves that owner before using them.
    acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = Field(
        default=(), exclude=True, repr=False
    )
    candidate_basis_transitions: tuple[CandidateSourceReentryReceipt, ...] = Field(
        default=(), exclude=True, repr=False
    )
    candidate_terminal_history: tuple[object, ...] = Field(default=(), exclude=True, repr=False)

    @field_validator("candidate_terminal_history")
    @classmethod
    def _require_verified_candidate_histories(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if any(type(item) is not CandidateEvaluationTerminalHistory for item in value):
            raise ValueError("candidate_terminal_history_untyped")
        return value

    @property
    def route_source_cycle(self) -> GenerationCycleRecord:
        """Resolve the immutable compiled cycle that anchors route and cost identity."""

        matches = tuple(
            cycle
            for cycle in self.generation_run.cycles
            if cycle.cycle_index == self.route_source_cycle_index
        )
        if len(matches) != 1:
            raise AcquisitionRouteClosureError("route_origin_cycle_not_in_continuation")
        return matches[0]

    @property
    def design_problem_basis(self) -> DesignProblem:
        """Recompute the concrete source-cycle basis from the recorded revision chain."""

        return _resolve_source_cycle_problem_basis(
            generation_run=self.generation_run,
            source_cycle=self.source_cycle,
            design_problem=self.design_problem,
            design_problem_ref=self.design_problem_ref,
            acquisition_basis_transitions=self.acquisition_basis_transitions,
            candidate_basis_transitions=self.candidate_basis_transitions,
        )

    @property
    def design_problem_basis_ref(self) -> str:
        """Return the recomputed hash of the concrete source-cycle basis."""

        return _problem_ref(self.design_problem_basis)


class _ActionHead(Protocol):
    """Structural view of the persisted action-generation owner."""

    action_generation: int
    job_id: str


class _VerifiedActionOutcome(Protocol):
    """Exact verified head and its latest persisted phase or terminal receipt."""

    head: _ActionHead
    latest_receipt: AcquisitionRoutePhaseReceipt | AcquisitionTerminalReceipt
    executing_phase_ref: str | None
    candidate_terminal_history: CandidateEvaluationTerminalHistory | None


class _ActionOutcomeReader(Protocol):
    """Read every owner-verified generation for one exact route identity."""

    def action_outcomes(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> tuple[_VerifiedActionOutcome, ...]: ...

    def resolve_action_generation(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        job_id: str,
    ) -> int: ...


@dataclass(frozen=True)
class _CompletedNLOrigin:
    """Completed NL output joined to its job, terminal event, and Core manifest."""

    job: ControlJobRecord
    payload_ref: str
    manifest_ref: str
    compiled_ref: str
    selected_compiled_ref: ArtifactRef
    terminal_event_id: str
    compiled: CompiledRecursiveGenerationCycleRun


@dataclass(frozen=True)
class _VerifiedAcquisitionOrigin(_CompletedNLOrigin):
    """Owner-replayed selected source before route-specific authority is considered."""

    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    design_problem_basis: DesignProblem
    report: AcquisitionPlannerReport
    planner_record: AcquisitionActionRecord
    source_requirement: AcquisitionRequirementGap | None
    configured_port_source: object | None
    cost: AcquisitionCostBasisRecord | None


@dataclass(frozen=True)
class VerifiedModelInputRoutingOrigin:
    """Read-only source custody for a selected blocked model-input occurrence."""

    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    source_payload_ref: str
    capability_manifest_ref: str
    compiled_ref: ArtifactRef
    terminal_event_id: str
    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    design_problem_basis: DesignProblem
    n5_execution_ref: ArtifactRef
    n5_expectation: GenericN5ExecutionJoinExpectation
    selected_basis: SelectedProgramGraphInputBasis
    routing_report_ref: ArtifactRef
    routing_report: ModelInputRoutingReport


@dataclass(frozen=True)
class VerifiedCandidateExperimentOrigin:
    """Verified candidate experiment source; it does not authorize an effect."""

    schema_version: Literal["polisyos.runtime.candidate_experiment_origin.v1"]
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    source_payload_ref: str
    capability_manifest_ref: str
    request_content_hash: str
    route_id: str
    policy_ref: ArtifactRef
    policy_scope: CandidateUnpricedPolicyScope
    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    design_problem_basis: DesignProblem
    planner_report: AcquisitionPlannerReport
    planner_record: AcquisitionActionRecord
    monetary_cost: Literal["not_established"] = "not_established"
    action_authority: Literal["not_established"] = "not_established"
    # Transport only: a mutation must reopen the owner, source and live lease.
    current_action_head: AcquisitionActionHeadRecord | None = None
    current_terminal_history: CandidateExperimentTerminalHistory | None = None
    candidate_terminal_history_chain: tuple[CandidateExperimentTerminalHistory, ...] = ()

    @property
    def source_attempt_prefix(self) -> tuple[str, ...]:
        """Return only actual acquisition attempts from the verified terminal chain.

        Candidate-experiment ``@1.0`` terminals own an acquisition action.
        The ``@2.0`` reuse terminal carries that prior action as provenance but
        performs no source acquisition, so it must not advance this ordered
        attempt prefix.
        """
        return tuple(
            entry.action.attempt_id
            for entry in self.candidate_terminal_history_chain
            if type(entry.terminal) is AcquisitionCandidateExperimentTerminalReceipt
            and entry.terminal.schema_version == "AcquisitionCandidateExperimentTerminalReceipt@1.0"
        )

    @property
    def effective_generation_run(self) -> GenerationCycleRun:
        """Return the current run derived from the complete verified terminal chain."""
        return _candidate_experiment_effective_source(self)[0]

    @property
    def effective_source_cycle(self) -> GenerationCycleRecord:
        """Return the current cycle derived from the complete verified terminal chain."""
        return _candidate_experiment_effective_source(self)[1]


@dataclass(frozen=True)
class _ResolvedCurrentCandidateExperiment:
    """Carry one owner-replayed current origin and its exact action outcomes."""

    origin: VerifiedCandidateExperimentOrigin
    outcomes: tuple[VerifiedAcquisitionActionOutcome, ...]


def _candidate_experiment_effective_source(
    origin: VerifiedCandidateExperimentOrigin,
) -> tuple[GenerationCycleRun, GenerationCycleRecord]:
    """Fold reentries and validate no-fetch reuse against the selected source root.

    This is a typed projection, not an authorization or source-read shortcut.
    Every terminal in the chain must be replayed by its historical owner before
    a consumer uses either effective value.
    """
    from dataclasses import replace

    from polisyos.runtime.quality.generation_cycle import (
        candidate_source_basis_cycle_pair_matches,
        generation_cycle_run_content_hash,
        validate_candidate_source_continuation,
    )

    generation_run = origin.generation_run
    source_cycle = origin.source_cycle
    prefix: list[CandidateExperimentTerminalHistory] = []
    for generation, history in enumerate(origin.candidate_terminal_history_chain, start=1):
        if (
            type(history) is not CandidateExperimentTerminalHistory
            or type(history.terminal)
            not in {
                AcquisitionCandidateExperimentTerminalReceipt,
                AcquisitionCandidateExperimentTerminalReceiptV2,
            }
            or history.head.action_generation != generation
            or history.terminal.action_generation != generation
            or not _candidate_model_values_same(
                replace(
                    history.origin,
                    current_action_head=None,
                    current_terminal_history=None,
                    candidate_terminal_history_chain=(),
                ),
                replace(
                    origin,
                    current_action_head=None,
                    current_terminal_history=None,
                    candidate_terminal_history_chain=(),
                ),
            )
            or history.origin.candidate_terminal_history_chain != tuple(prefix)
            or not generation_run.cycles
            or generation_run.cycles[-1] != source_cycle
        ):
            raise ValueError("candidate_experiment_effective_source_history_mismatch")
        if type(history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2:
            from polisyos.runtime.quality.candidate_experiment_reuse import (
                CandidateExperimentReuseActionSelection,
            )
            from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
                CandidateExperimentReuseOccurrence,
            )

            if not prefix:
                raise ValueError("candidate_experiment_effective_source_reuse_predecessor_missing")
            predecessor = prefix[-1]
            if (
                not _candidate_model_values_same(history.action, predecessor.action)
                or not _candidate_model_values_same(history.source, predecessor.source)
                or not _candidate_ref_same(
                    history.terminal.candidate_action_ref,
                    predecessor.terminal.candidate_action_ref,
                )
            ):
                raise ValueError("candidate_experiment_effective_source_reuse_source_mismatch")
            predecessor_evaluation = (
                predecessor.reentry_evaluation
                if predecessor.terminal.terminal_outcome == "candidate_reentry_completed"
                else predecessor.evaluation
                if predecessor.terminal.terminal_outcome == "candidate_evaluation_retained"
                else None
            )
            selection = getattr(history.reuse_occurrence, "selection", None)
            predecessor_budget_window = (
                predecessor.provenance_budget_window
                if predecessor.provenance_budget_window is not None
                else predecessor.budget_window
            )
            if (
                type(history.reuse_occurrence) is not CandidateExperimentReuseOccurrence
                or type(selection) is not CandidateExperimentReuseActionSelection
                or not _candidate_ref_same(
                    history.reuse_occurrence_ref, history.terminal.reuse_occurrence_ref
                )
                or history.budget_window is not None
                or not _candidate_model_values_same(
                    history.provenance_budget_window, predecessor_budget_window
                )
                or predecessor_evaluation is None
            ):
                raise ValueError("candidate_experiment_effective_source_reuse_occurrence_mismatch")
            if (
                selection.route_id != history.terminal.route_id
                or not _candidate_ref_same(
                    selection.predecessor_terminal_ref, predecessor.terminal_ref
                )
                or not _candidate_ref_same(
                    selection.predecessor_action_ref,
                    predecessor.terminal.candidate_action_ref,
                )
                or not _candidate_ref_same(
                    selection.source_ref, predecessor.action.candidate_source_ref
                )
                or not _candidate_ref_same(
                    selection.n5_input_ref, predecessor_evaluation.selected.n5_input_ref
                )
                or not _candidate_ref_same(
                    selection.n5_execution_ref, predecessor_evaluation.selected.n5_execution_ref
                )
                or not _candidate_ref_same(
                    selection.n5_result_ref, predecessor_evaluation.selected.n5_result_ref
                )
                or not _candidate_ref_same(selection.policy_ref, history.origin.policy_ref)
            ):
                raise ValueError("candidate_experiment_effective_source_reuse_selection_mismatch")
            if history.terminal.terminal_outcome == "candidate_evaluation_retained":
                prior_selection = predecessor_evaluation.selected
                prior_basis_ref = predecessor.terminal.selected_basis_ref
                if (
                    history.continuation is None
                    or history.reentry is not None
                    or history.evaluation is None
                    or history.reentry_evaluation is not None
                    or (
                        prior_selection.basis_ref is not None
                        and not _candidate_ref_same(prior_selection.basis_ref, prior_basis_ref)
                    )
                    or not _candidate_model_values_same(
                        history.evaluation.selected, prior_selection
                    )
                    or not _candidate_model_values_same(
                        history.terminal.selected_evaluation,
                        prior_selection.model_copy(update={"basis_ref": prior_basis_ref}),
                    )
                ):
                    raise ValueError(
                        "candidate_experiment_effective_source_reuse_retention_mismatch"
                    )
            elif history.terminal.terminal_outcome == "candidate_blocked":
                predecessor_frontier = predecessor.frontier_after
                if (
                    history.reentry is not None
                    or history.continuation is not None
                    or history.evaluation is not None
                    or history.reentry_evaluation is not None
                    or history.frontier_before != predecessor_frontier
                    or history.frontier_after != predecessor_frontier
                ):
                    raise ValueError("candidate_experiment_effective_source_reuse_blocker_mismatch")
            else:
                raise ValueError("candidate_experiment_effective_source_outcome_unsupported")
        elif type(history.terminal) is AcquisitionCandidateExperimentTerminalReceipt and (
            history.terminal.terminal_outcome == "candidate_reentry_completed"
        ):
            reentry = history.reentry
            if (
                reentry is None
                or reentry.source_cycle_index != source_cycle.cycle_index
                or reentry.source_generation_run_content_hash
                != generation_cycle_run_content_hash(generation_run)
                or reentry.basis_transition.from_cycle_index != source_cycle.cycle_index
                or reentry.basis_transition.to_cycle_index != source_cycle.cycle_index + 1
                or not candidate_source_basis_cycle_pair_matches(
                    transition=reentry.basis_transition,
                    source_cycle=source_cycle,
                    target_cycle=reentry.new_cycle,
                )
            ):
                raise ValueError("candidate_experiment_effective_source_transition_mismatch")
            validate_candidate_source_continuation(generation_run, reentry)
            generation_run = reentry.continued_generation_run
            source_cycle = reentry.new_cycle
        elif type(history.terminal) is AcquisitionCandidateExperimentTerminalReceipt and (
            history.terminal.terminal_outcome == "candidate_evaluation_retained"
        ):
            if (
                history.continuation is None
                or history.reentry is not None
                or history.evaluation is None
            ):
                raise ValueError("candidate_experiment_effective_source_retention_mismatch")
        elif type(history.terminal) is AcquisitionCandidateExperimentTerminalReceipt and (
            history.terminal.terminal_outcome == "candidate_blocked"
        ):
            if (
                history.reentry is not None
                or history.continuation is not None
                or history.evaluation is not None
                or history.reentry_evaluation is not None
                or history.frontier_before is not None
                or history.frontier_after is not None
            ):
                raise ValueError("candidate_experiment_effective_source_blocker_mismatch")
        else:
            raise ValueError("candidate_experiment_effective_source_outcome_unsupported")
        prefix.append(history)
    if not generation_run.cycles or generation_run.cycles[-1] != source_cycle:
        raise ValueError("candidate_experiment_effective_source_cycle_not_current")
    return generation_run, source_cycle


@dataclass(frozen=True)
class _CandidateExperimentSourceIdentity:
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    source_payload_ref: str
    capability_manifest_ref: str


def _select_candidate_experiment_source_policy_historical(
    *,
    artifact_store: _ArtifactStore,
    origin: _VerifiedAcquisitionOrigin,
    configured_bindings: tuple[CandidateUnpricedPolicyBinding, ...],
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> tuple[CandidateUnpricedPolicyBinding, str, _CandidateExperimentSourceIdentity]:
    """Calculate the exact selected policy/source join without current permission."""
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedPolicyBinding,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        validate_candidate_compiler_relation,
    )

    report = origin.report
    binding = report.requirement_basis_binding
    lineage = report.candidate_lineage
    planner_ref = origin.source_cycle.acquisition_routing_report_ref
    source = origin.configured_port_source
    if (
        binding is None
        or lineage is None
        or planner_ref is None
        or source is None
        or origin.planner_record.compiled_requirement_ref is None
    ):
        raise AcquisitionRouteClosureError("candidate_experiment_origin_not_established")
    candidates = []
    for configured in configured_bindings:
        if type(configured) is not CandidateUnpricedPolicyBinding:
            raise AcquisitionRouteClosureError("candidate_experiment_policy_untyped")
        scope = configured.scope
        if (
            (scope.tenant_id, scope.cell_id, scope.run_id, scope.source_job_id)
            != (tenant_id, cell_id, run_id, origin.job.job_id)
            or scope.design_problem_ref != origin.compiled.design_problem_ref
            or scope.design_problem_basis_ref != source.design_problem_basis_ref
            or scope.source_cycle_index != origin.source_cycle.cycle_index
            or scope.candidate_id != origin.source_cycle.selected_candidate_ref
            or scope.candidate_content_hash != origin.source_cycle.selected_candidate_content_hash
            or scope.compiled_requirement_ref != origin.planner_record.compiled_requirement_ref
            or scope.planner_report_hash != agent_action_content_hash(report)
            or artifact_ref_identity_key(scope.compiled_ref)
            != artifact_ref_identity_key(origin.selected_compiled_ref)
            or artifact_ref_identity_key(scope.planner_report_ref)
            != artifact_ref_identity_key(planner_ref)
            or artifact_ref_identity_key(scope.compiler_report_ref)
            != artifact_ref_identity_key(binding.compiler_report_ref)
            or artifact_ref_identity_key(scope.configured_port_source_ref)
            != artifact_ref_identity_key(lineage.port_source_ref)
        ):
            continue
        try:
            validate_candidate_compiler_relation(
                artifact_store,
                requirement_basis_binding=binding,
                compiled_requirement_ref=scope.compiled_requirement_ref,
                requirement_id=scope.requirement_id,
                candidate_digest=scope.candidate_digest,
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        candidates.append(configured)
    if len(candidates) != 1:
        raise AcquisitionRouteClosureError("candidate_experiment_policy_not_unique")
    selected = candidates[0]
    route_id = agent_action_content_hash(
        {
            "schema_version": "polisyos.runtime.candidate_experiment_route.v1",
            "purpose": "bounded_candidate_experiment_voi_unknown",
            "scope": selected.scope.model_dump(mode="json"),
            "policy_ref": selected.policy_ref.model_dump(mode="json"),
            "source_payload_ref": origin.payload_ref,
            "source_cycle_voi_decision": origin.source_cycle.voi_decision.model_dump(mode="json"),
        }
    )
    source_identity = _CandidateExperimentSourceIdentity(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=origin.job.job_id,
        source_payload_ref=origin.payload_ref,
        capability_manifest_ref=origin.manifest_ref,
    )
    return selected, route_id, source_identity


def _calculate_candidate_experiment_origin_historical(
    *,
    origin: _VerifiedAcquisitionOrigin,
    selected: CandidateUnpricedPolicyBinding,
    route_id: str,
    evidence: OriginalRunBudgetScopeEvidence,
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> VerifiedCandidateExperimentOrigin:
    """Build the candidate-only historical projection from verified read inputs."""
    report = origin.report
    if evidence.request_content_hash is None:
        raise AcquisitionRouteClosureError("candidate_experiment_intent_not_established")
    return VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=origin.job.job_id,
        source_payload_ref=origin.payload_ref,
        capability_manifest_ref=origin.manifest_ref,
        request_content_hash=evidence.request_content_hash,
        route_id=route_id,
        policy_ref=selected.policy_ref,
        policy_scope=selected.scope,
        generation_run=origin.generation_run,
        source_cycle=origin.source_cycle,
        design_problem_basis=origin.design_problem_basis,
        planner_report=report,
        planner_record=origin.planner_record,
    )


def _read_selected_candidate_experiment_receipt_historical(
    *,
    artifact_store: _ArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    head: AcquisitionActionHeadRecord,
) -> (
    AcquisitionCandidateExperimentPhaseReceipt
    | AcquisitionCandidateExperimentTerminalReceipt
    | AcquisitionCandidateExperimentTerminalReceiptV2
):
    """Reopen selected SQL/CAS/event bytes without composing a current service owner."""
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _read_verified_acquisition_action_phase,
    )
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord

    if (
        type(head) is not AcquisitionActionHeadRecord
        or head.receipt_ref != head.receipt_sha256
        or head.receipt_manifest_profile_sha256 is None
    ):
        raise AcquisitionRouteClosureError("candidate_experiment_history_owner_not_composed")
    ref = ArtifactRef(
        artifact_id=ArtifactID.model_validate(head.receipt_ref),
        kind=(
            "runtime_quality.acquisition_route_loop_receipt"
            if head.receipt_phase == "terminal"
            else "runtime_quality.acquisition_candidate_experiment_phase_receipt"
        ),
        media_type="application/json",
        manifest_profile_sha256=head.receipt_manifest_profile_sha256,
    )
    verified = _read_verified_acquisition_action_phase(
        artifact_store=artifact_store,
        event_log=event_log,
        receipt_ref=head.receipt_ref,
        selected_ref=ref,
    )
    receipt = verified.receipt
    if (
        type(receipt)
        not in {
            AcquisitionCandidateExperimentPhaseReceipt,
            AcquisitionCandidateExperimentTerminalReceipt,
            AcquisitionCandidateExperimentTerminalReceiptV2,
        }
        or verified.durable_event_id != head.durable_event_id
        or any(
            getattr(receipt, field) != getattr(head, field)
            for field in (
                "tenant_id",
                "cell_id",
                "run_id",
                "source_job_id",
                "route_id",
                "action_generation",
                "job_id",
                "receipt_phase",
                "predecessor_receipt_ref",
            )
        )
    ):
        raise AcquisitionRouteClosureError("candidate_experiment_historical_head_mismatch")
    return receipt


class AcquisitionRouteLoop:
    """Resolve verified closures and own acquisition phase orchestration."""

    def __init__(
        self,
        *,
        control_store: ControlPlaneStore,
        artifact_store: _ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        core_source_resolver: CompletedControlJobCoreSourceResolver,
        tenant_id: str,
        cell_id: str,
        action_outcome_reader: _ActionOutcomeReader | None = None,
    ) -> None:
        if not tenant_id.strip() or not cell_id.strip():
            raise ValueError("acquisition route loop requires tenant and cell")
        for capability in ("has", "get_bytes", "get_manifest"):
            if not callable(getattr(artifact_store, capability, None)):
                raise TypeError("acquisition route loop requires guarded CAS read capabilities")
        self._control_store = control_store
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._core_source_resolver = core_source_resolver
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        self._action_outcome_reader = action_outcome_reader

    def _resolve_completed_nl_origin(self, *, run_id: str) -> _CompletedNLOrigin:
        """Reopen the one completed NL output before applying any route policy."""

        try:
            job = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=run_id,
                kind="natural_language_run",
            )
        except ValueError as exc:
            raise AcquisitionRouteClosureError("source_job_ambiguous") from exc
        if job is None:
            raise AcquisitionRouteClosureError("source_job_not_completed")
        if job.run_id != run_id or job.state != "completed":
            raise AcquisitionRouteClosureError("source_job_not_completed")
        payload_ref = job.payload_ref
        manifest_ref = job.capability_manifest_ref
        if payload_ref is None or manifest_ref is None:
            raise AcquisitionRouteClosureError("source_job_owner_refs_missing")
        payload = self._read_json_artifact(
            payload_ref,
            expected_kind="runtime.control_job_payload.natural_language_run",
            expected_schema_name="polisyos.runtime.ControlJobPayload",
        )
        if not isinstance(payload, dict) or (
            payload.get("tenant_id") != self._tenant_id
            or payload.get("cell_id") != self._cell_id
            or payload.get("run_id") != run_id
        ):
            raise AcquisitionRouteClosureError("source_job_actor_scope_mismatch")
        if not self._artifact_store.has(ArtifactID.model_validate(manifest_ref)):
            raise AcquisitionRouteClosureError("source_manifest_missing")
        progress = job.progress
        compiled_ref = progress.get("compiled_recursive_generation_cycle_ref")
        if (
            progress.get("state") != "completed"
            or progress.get("phase") != "natural_language_run"
            or progress.get("run_id") != run_id
            or not isinstance(compiled_ref, str)
        ):
            raise AcquisitionRouteClosureError("source_progress_incomplete")
        try:
            selected_compiled_ref = ArtifactRef.model_validate(
                progress.get("compiled_recursive_generation_cycle_artifact_ref")
            )
            terminal = self._core_source_resolver(
                job,
                expected_control_run_id=run_id,
                tenant_id=self._tenant_id,
                cell_id=self._cell_id,
            )
        except (TypeError, ValueError, OSError) as exc:
            raise AcquisitionRouteClosureError("source_core_attempt_not_established") from exc
        compiled_outputs = tuple(
            ref
            for ref in terminal.manifest.outputs
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        )
        if (
            terminal.manifest.status != "ok"
            or terminal.tenant_id != self._tenant_id
            or terminal.cell_id != self._cell_id
            or str(terminal.manifest_ref.artifact_id) != progress.get("manifest_ref")
            or len(compiled_outputs) != 1
            or str(compiled_outputs[0].artifact_id) != compiled_ref
            or artifact_ref_identity_key(compiled_outputs[0])
            != artifact_ref_identity_key(selected_compiled_ref)
        ):
            raise AcquisitionRouteClosureError("source_core_output_binding_mismatch")
        terminal_event_id = self._resolve_terminal_event(
            run_id=run_id,
            job_id=job.job_id,
            compiled_ref=compiled_ref,
            manifest_ref=manifest_ref,
        )
        compiled_payload = self._read_json_artifact(
            selected_compiled_ref,
            expected_kind="runtime.compiled_recursive_generation_cycle",
            expected_schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        )
        from polisyos.runtime.http.services.control.generation_cycle import (
            CompiledRecursiveGenerationCycleRun,
        )

        try:
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)
        except (TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError("compiled_run_invalid") from exc
        return _CompletedNLOrigin(
            job=job,
            payload_ref=payload_ref,
            manifest_ref=manifest_ref,
            compiled_ref=compiled_ref,
            selected_compiled_ref=selected_compiled_ref,
            terminal_event_id=terminal_event_id,
            compiled=compiled,
        )

    def _resolve_verified_origin(
        self, *, run_id: str, experiment: bool = False
    ) -> _VerifiedAcquisitionOrigin:
        """Reopen the completed owner and selected planner/actual-cycle lineage."""

        completed = self._resolve_completed_nl_origin(run_id=run_id)
        job = completed.job
        compiled = completed.compiled
        candidates = [
            (leaf.cycle_run, cycle)
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
            if cycle.acquisition_routing_report is not None
            and (
                (not experiment and cycle.acquisition_cost_basis_record is not None)
                or (
                    experiment
                    and cycle.acquisition_cost_basis_record is None
                    and cycle.acquisition_routing_report.schema_version
                    == _N7_CONFIGURED_REPORT_SCHEMA
                )
            )
        ]
        if len(candidates) != 1:
            raise AcquisitionRouteClosureError(
                "candidate_experiment_source_not_unique"
                if experiment
                else "costed_route_not_unique"
            )
        generation_run, source_cycle = candidates[0]
        source_problem = _resolve_source_cycle_problem_basis(
            generation_run=generation_run,
            source_cycle=source_cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
        )
        report = source_cycle.acquisition_routing_report
        cost = source_cycle.acquisition_cost_basis_record
        if report is None or (not experiment and cost is None):
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        request = source_cycle.revision_request.strategy_payload.get("acquisition_request")
        configured_port_source = None
        source_rule = request.get("n7_source_join_rule") if isinstance(request, Mapping) else None
        if (
            report.schema_version == _N7_CONFIGURED_REPORT_SCHEMA
            and source_rule != _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE
        ):
            raise AcquisitionRouteClosureError("source_requirement_rule_missing_or_downgraded")
        if (
            source_cycle.value_port.candidate_n5_l1_routing is not None
            and source_rule != _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE
        ):
            raise AcquisitionRouteClosureError("source_requirement_rule_missing_or_downgraded")
        if experiment and source_rule != _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE:
            raise AcquisitionRouteClosureError("candidate_experiment_source_rule_not_established")
        if source_rule == _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE:
            source_requirement, refusal = _n7_cycle_source_gap(
                source_problem, cycle=source_cycle, acquisition_request=request
            )
            if refusal is not None or source_requirement is None:
                raise AcquisitionRouteClosureError("source_requirement_binding_mismatch")
        else:
            source_requirement = _cycle_acquisition_requirement(
                source_cycle.grounding, source_cycle.value_port
            )
        planner_record = _select_source_planner_record(report, source_requirement)
        planner_ref = source_cycle.acquisition_routing_report_ref
        if planner_ref is None:
            raise AcquisitionRouteClosureError("acquisition_planner_report_ref_required")
        basis_issues = validate_persisted_acquisition_planner_report(
            self._artifact_store,
            planner_ref,
            report,
            expected_scenario_id=compiled.design_problem.design_problem_id,
            expected_compiled_requirement_ref=planner_record.compiled_requirement_ref,
        )
        if basis_issues:
            first_issue = basis_issues[0]
            code = first_issue.get("code") if isinstance(first_issue, dict) else None
            raise AcquisitionRouteClosureError(
                code if isinstance(code, str) else "acquisition_planner_basis_not_revalidated"
            )
        try:
            _n7_require_current_report_input_provenance(report)
        except ValueError as exc:
            raise AcquisitionRouteClosureError(str(exc)) from exc
        source_semantic_schema = planner_record.requirement_schema_version in {
            "policyos.runtime.l1_variable_availability_gap.v1",
            "policyos.runtime.grounding_coverage_gap.v1",
        }
        if source_semantic_schema and source_requirement is None:
            raise AcquisitionRouteClosureError("source_requirement_missing")
        if source_rule is not None and source_rule not in {
            _N7_SOURCE_JOIN_RULE,
            _N7_SOURCE_DESCRIPTOR_JOIN_RULE,
            _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
        }:
            raise AcquisitionRouteClosureError("source_requirement_rule_unsupported")
        row_has_joined_shape = (
            source_semantic_schema
            and source_requirement is not None
            and planner_record.compiled_requirement_ref
            != source_requirement.compiled_requirement_ref
        )
        if row_has_joined_shape and source_rule is None:
            raise AcquisitionRouteClosureError("source_requirement_rule_missing")
        if source_rule in {
            _N7_SOURCE_JOIN_RULE,
            _N7_SOURCE_DESCRIPTOR_JOIN_RULE,
            _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
        }:
            if not isinstance(request, Mapping):
                raise AcquisitionRouteClosureError("source_requirement_request_missing")
            source_gap, refusal = _n7_cycle_source_gap(
                source_problem,
                cycle=source_cycle,
                acquisition_request=request,
            )
            binding = report.requirement_basis_binding
            if refusal is not None or source_gap is None or binding is None:
                raise AcquisitionRouteClosureError("source_requirement_binding_mismatch")
            if source_rule == _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE:
                from polisyos.runtime.quality.acquisition_planner import (
                    _n7_verify_configured_candidate_report_cycle,
                )

                try:
                    configured_port_source = _n7_verify_configured_candidate_report_cycle(
                        artifact_store=self._artifact_store,
                        control_store=self._control_store,
                        report=report,
                        report_ref=planner_ref,
                        generation_run=generation_run,
                        source_cycle=source_cycle,
                        tenant_id=self._tenant_id,
                        cell_id=self._cell_id,
                        run_id=run_id,
                        source_job_id=job.job_id,
                        design_problem_ref=compiled.design_problem_ref,
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise AcquisitionRouteClosureError(
                        "source_requirement_candidate_lineage_unverified"
                    ) from exc
                issues = validate_persisted_data_requirement_compilation_report(
                    self._artifact_store, binding, require_selected_writer_profile=True
                )
                if issues:
                    raise AcquisitionRouteClosureError(
                        "source_requirement_compiler_profile_unverified"
                    )
            try:
                compiler_report = DataRequirementCompilationReport.model_validate(
                    load_core_json_artifact(self._artifact_store, binding.compiler_report_ref)
                )
            except Exception as exc:
                raise AcquisitionRouteClosureError(
                    "source_requirement_compiler_unreadable"
                ) from exc
            if source_rule == _N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE:
                grounding_gap = source_cycle.grounding.acquisition_requirement
                derivation_bundle = None
                if configured_port_source is not None:
                    bundle_ref = configured_port_source.derivation_bundle_ref
                    if bundle_ref is not None:
                        try:
                            derivation_bundle = _n7_load_derivation_bundle(
                                self._artifact_store, bundle_ref
                            )
                        except (OSError, RuntimeError, TypeError, ValueError) as exc:
                            raise AcquisitionRouteClosureError(
                                "source_requirement_derivation_bundle_unverified"
                            ) from exc
                matching = _n7_candidate_n5_l1_planner_records_match(
                    source_gap=source_gap,
                    accompanying_requirement_gaps=(grounding_gap,) if grounding_gap else (),
                    specs=compiler_report.specs,
                    capability_resolutions=compiler_report.capability_requirement_resolutions,
                    report=report,
                    derivation_bundle=derivation_bundle,
                )
            else:
                matching = _n7_joined_planner_records_match(
                    problem=source_problem,
                    acquisition_request=request,
                    source_gap=source_gap,
                    specs=compiler_report.specs,
                    capability_resolutions=compiler_report.capability_requirement_resolutions,
                    report=report,
                    require_descriptor_join=source_rule == _N7_SOURCE_DESCRIPTOR_JOIN_RULE,
                )
            if not matching:
                raise AcquisitionRouteClosureError("source_requirement_projection_mismatch")
        return _VerifiedAcquisitionOrigin(
            job=job,
            payload_ref=completed.payload_ref,
            manifest_ref=completed.manifest_ref,
            compiled_ref=completed.compiled_ref,
            selected_compiled_ref=completed.selected_compiled_ref,
            terminal_event_id=completed.terminal_event_id,
            compiled=compiled,
            generation_run=generation_run,
            source_cycle=source_cycle,
            design_problem_basis=source_problem,
            report=report,
            planner_record=planner_record,
            source_requirement=source_requirement,
            configured_port_source=configured_port_source,
            cost=cost,
        )

    def resolve_model_input_routing_origin(
        self, *, run_id: str, routing_report_ref: ArtifactRef
    ) -> VerifiedModelInputRoutingOrigin:
        """Reopen the exact V10 root-leaf report and its blocked N5 occurrence.

        This historical join resolves source custody. A successor must still
        obtain current action authority and replay the selected Catalog before
        using an activated observation.
        """
        from polisyos.core.artifacts import (
            CoreJSONArtifactStore,
            matches_artifact_store_protocol,
            validate_core_model_json_artifact,
        )
        from polisyos.core.contracts import ModelInputObligationSet
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.generation_cycle import (
            _GENERATION_CYCLE_MODEL_INPUT_ROUTING_SCHEMA_VERSION,
            _generation_source_run_id,
            resolve_generation_cycle_run_context_history,
        )
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner,
            GenericCycleSimulationN5ExecutionV4,
            GenericCycleSimulationN5InputV1,
            GenericN5ExecutionJoinExpectation,
        )
        from polisyos.runtime.quality.model_input_routing import (
            MODEL_INPUT_ROUTING_REPORT_KIND,
            read_model_input_routing_report,
        )

        if (
            routing_report_ref.kind != MODEL_INPUT_ROUTING_REPORT_KIND
            or routing_report_ref.media_type != "application/json"
            or routing_report_ref.manifest_profile_sha256 is None
        ):
            raise AcquisitionRouteClosureError("model_input_source_report_not_selected")
        completed = self._resolve_completed_nl_origin(run_id=run_id)
        compiled = completed.compiled
        recursive_run = compiled.recursive_run
        leaves = recursive_run.leaf_nodes
        if (
            len(leaves) != 1
            or leaves[0].node_ref != recursive_run.root_node_ref
            or leaves[0].cycle_run is None
        ):
            raise AcquisitionRouteClosureError("model_input_source_root_leaf_not_established")
        generation_run = leaves[0].cycle_run
        source_run_id = _generation_source_run_id(compiled.design_problem)
        if (
            generation_run.schema_version != _GENERATION_CYCLE_MODEL_INPUT_ROUTING_SCHEMA_VERSION
            or not generation_run.cycles
            or generation_run.cycles[-1].model_input_routing_report_ref != routing_report_ref
            or sum(
                cycle.model_input_routing_report_ref == routing_report_ref
                for cycle in generation_run.cycles
            )
            != 1
        ):
            raise AcquisitionRouteClosureError("model_input_source_report_not_selected")
        cycle = generation_run.cycles[-1]
        simulation = cycle.simulation
        handoff = compiled.generic_cycle_simulation_handoff
        scope = (completed.job.job_id, run_id, self._tenant_id, self._cell_id)
        if (
            generation_run.run_id != source_run_id
            or generation_run.design_problem_ref != compiled.design_problem_ref
            or completed.selected_compiled_ref.manifest_profile_sha256 is None
            or handoff is None
            or (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id) != scope
            or handoff.profile.profile_selection_kind != "problem"
            or handoff.n4_child_profile_family_ref is not None
            or compiled.n4_child_profile_set_ref is not None
            or simulation.status != "simulation_blocked"
            or simulation.simulation_result_ref is not None
            or simulation.generic_n4_child_profile_family_ref is not None
            or simulation.generic_n4_child_profile_set_ref is not None
            or simulation.generic_n5_input_ref is None
            or simulation.generic_n5_execution_ref is None
            or simulation.model_input_obligation_set_ref is None
            or simulation.generic_n4_source_ref is None
            or simulation.generic_profile_ref != handoff.profile_ref
            or simulation.generic_profile_selection_ref != handoff.profile.profile_selection_ref
        ):
            raise AcquisitionRouteClosureError("model_input_source_n5_lineage_not_established")
        store = self._artifact_store
        if not matches_artifact_store_protocol(store, CoreJSONArtifactStore):
            raise AcquisitionRouteClosureError("model_input_source_profile_store_unavailable")
        history = resolve_generation_cycle_run_context_history(
            generation_run,
            context_owner=CycleSubstrateContextArtifactOwner(store=store),
            initial_problem=compiled.design_problem,
            expected_job_id=completed.job.job_id,
            expected_run_id=run_id,
            expected_tenant_id=self._tenant_id,
            expected_cell_id=self._cell_id,
        )
        bindings = tuple(row for row in history.bindings if row.cycle_index == cycle.cycle_index)
        if history.status != "resolved" or len(bindings) != 1:
            raise AcquisitionRouteClosureError("model_input_source_context_history_not_established")
        (binding,) = bindings
        if (
            simulation.generic_context_job_ref != binding.context_job_ref
            or cycle.design_problem_basis_ref != cycle_job_design_problem_ref(binding.problem)
            or (
                cycle.cycle_index == 0
                and (
                    binding.context_job_ref != handoff.context_job_ref
                    or binding.context != handoff.context
                )
            )
        ):
            raise AcquisitionRouteClosureError("model_input_source_context_mismatch")

        # The generic owner independently reopens N4 and recomputes this
        # outcome from the candidate and problem during the V4 request replay.
        input_record = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(store, simulation.generic_n5_input_ref)
        )
        expectation = GenericN5ExecutionJoinExpectation(
            input_ref=simulation.generic_n5_input_ref,
            result_ref=None,
            status="simulation_blocked",
            model_input_obligation_set_ref=simulation.model_input_obligation_set_ref,
            n4_source_ref=simulation.generic_n4_source_ref,
            context_job_ref=binding.context_job_ref,
            profile_ref=handoff.profile_ref,
            child_family_ref=None,
            child_set_ref=None,
            profile_selection_ref=handoff.profile.profile_selection_ref,
            profile=handoff.profile,
            design_problem_ref=cycle.design_problem_basis_ref,
            outcome_variable=input_record.outcome_variable,
            cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            candidate_atom_hash=cycle.selected_candidate_content_hash,
            world_model_record_content_hash=binding.context.world_model_record.content_hash,
            job_id=completed.job.job_id,
            run_id=run_id,
            source_run_id=source_run_id,
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
        )
        execution_ref = simulation.generic_n5_execution_ref
        owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
        join, selected_basis = owner.resolve_n5_execution_join_with_program_graph_input_basis(
            execution_ref, expected=expectation
        )
        if (
            join.status != "resolved"
            or type(join.execution) is not GenericCycleSimulationN5ExecutionV4
            or selected_basis is None
        ):
            raise AcquisitionRouteClosureError("model_input_source_n5_join_not_established")
        report = read_model_input_routing_report(store, routing_report_ref)
        obligation_set = validate_core_model_json_artifact(
            ModelInputObligationSet, store, simulation.model_input_obligation_set_ref
        )
        if (
            report.obligation_set_ref != simulation.model_input_obligation_set_ref
            or report.selected_invocation != obligation_set.invocation
        ):
            raise AcquisitionRouteClosureError("model_input_source_report_invocation_mismatch")
        return VerifiedModelInputRoutingOrigin(
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
            source_job_id=completed.job.job_id,
            source_payload_ref=completed.payload_ref,
            capability_manifest_ref=completed.manifest_ref,
            compiled_ref=completed.selected_compiled_ref,
            terminal_event_id=completed.terminal_event_id,
            generation_run=generation_run,
            source_cycle=cycle,
            design_problem_basis=binding.problem,
            n5_execution_ref=execution_ref,
            n5_expectation=expectation,
            selected_basis=selected_basis,
            routing_report_ref=routing_report_ref,
            routing_report=report,
        )

    def resolve_candidate_experiment_origin(
        self, *, run_id: str
    ) -> VerifiedCandidateExperimentOrigin:
        """Resolve an unacted experiment source for read-only projection."""
        result = self._resolve_candidate_experiment_source(run_id=run_id)
        if self._control_store.list_acquisition_action_heads_for_source(
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
            source_job_id=result.source_job_id,
        ):
            raise AcquisitionRouteClosureError(
                "candidate_experiment_action_history_not_established"
            )
        return result

    def _resolve_candidate_experiment_source(
        self, *, run_id: str, historical_policy_ref: ArtifactRef | None = None
    ) -> VerifiedCandidateExperimentOrigin:
        """Reopen a current or selected historical source without granting authority."""
        from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            CandidateUnpricedPolicyBinding,
            list_current_candidate_unpriced_policy_bindings,
            read_candidate_unpriced_policy,
            verify_candidate_unpriced_experiment_policy_intent,
        )

        origin = self._resolve_verified_origin(run_id=run_id, experiment=True)
        if (
            origin.source_cycle.voi_decision.scheduler_action != "reject"
            or origin.source_cycle.voi_decision.scheduler_reason != "roi_below_threshold"
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_roi_rejection_missing")
        service = getattr(self._core_source_resolver, "__self__", None)
        report = origin.report
        binding = report.requirement_basis_binding
        lineage = report.candidate_lineage
        planner_ref = origin.source_cycle.acquisition_routing_report_ref
        source = origin.configured_port_source
        if (
            type(service) is not ControlPlaneService
            or service._control_store is not self._control_store
            or service._artifact_store is not self._artifact_store
            or binding is None
            or lineage is None
            or planner_ref is None
            or source is None
            or origin.planner_record.compiled_requirement_ref is None
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_origin_not_established")
        try:
            if historical_policy_ref is None:
                configured_bindings = list_current_candidate_unpriced_policy_bindings(
                    control_service=service,
                    tenant_id=self._tenant_id,
                    cell_id=self._cell_id,
                    run_id=run_id,
                    source_job_id=origin.job.job_id,
                    candidate_id=origin.source_cycle.selected_candidate_ref,
                )
            else:
                policy = read_candidate_unpriced_policy(
                    store=self._artifact_store,
                    event_log=self._event_log,
                    ref=historical_policy_ref,
                )
                configured_bindings = (
                    CandidateUnpricedPolicyBinding(
                        scope=policy.scope, policy_ref=historical_policy_ref
                    ),
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError(
                "candidate_experiment_policy_binding_unavailable"
            ) from exc
        selected, route_id, source_identity = _select_candidate_experiment_source_policy_historical(
            artifact_store=self._artifact_store,
            origin=origin,
            configured_bindings=configured_bindings,
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
        )
        try:
            evidence = verify_candidate_unpriced_experiment_policy_intent(
                control_service=service,
                closure=source_identity,
                scope=selected.scope,
                policy_ref=selected.policy_ref,
                require_current=historical_policy_ref is None,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError(
                "candidate_experiment_intent_not_established"
            ) from exc
        result = _calculate_candidate_experiment_origin_historical(
            origin=origin,
            selected=selected,
            route_id=route_id,
            evidence=evidence,
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
        )
        if self._control_store.get_job(origin.job.job_id) != origin.job:
            raise AcquisitionRouteClosureError("candidate_experiment_source_changed")
        return result

    def _selected_candidate_experiment_receipt(
        self, head: object
    ) -> (
        AcquisitionCandidateExperimentPhaseReceipt
        | AcquisitionCandidateExperimentTerminalReceipt
        | AcquisitionCandidateExperimentTerminalReceiptV2
    ):
        """Reopen a receipt selected by the exact action head and durable event."""
        from polisyos.runtime.http.services.control.run_lifecycle import (
            AcquisitionRouteLoopAuthoritySink,
            ControlPlaneService,
        )
        from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord

        service = getattr(self._core_source_resolver, "__self__", None)
        sink = self._action_outcome_reader
        if (
            type(head) is not AcquisitionActionHeadRecord
            or type(service) is not ControlPlaneService
            or type(sink) is not AcquisitionRouteLoopAuthoritySink
            or service.acquisition_route_sink is not sink
            or sink._control_store is not self._control_store
            or sink._artifact_store is not self._artifact_store
            or sink._event_log is not self._event_log
            or head.receipt_ref != head.receipt_sha256
            or head.receipt_manifest_profile_sha256 is None
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_history_owner_not_composed")
        return _read_selected_candidate_experiment_receipt_historical(
            artifact_store=self._artifact_store, event_log=self._event_log, head=head
        )

    def resolve_candidate_experiment_predecessor_origin(
        self,
        *,
        run_id: str,
        predecessor_terminal_ref: ArtifactRef | None,
        expected_action_generation: int | None = None,
        historical_policy_ref: ArtifactRef | None = None,
        historical_action_job_id: str | None = None,
    ) -> VerifiedCandidateExperimentOrigin:
        """Fully replay the historical prefix selected by an immutable request."""
        return self._resolve_candidate_experiment_predecessor_origin(
            run_id=run_id,
            predecessor_terminal_ref=predecessor_terminal_ref,
            expected_action_generation=expected_action_generation,
            historical_policy_ref=historical_policy_ref,
            historical_action_job_id=historical_action_job_id,
        )

    def _resolve_candidate_experiment_predecessor_origin(
        self,
        *,
        run_id: str,
        predecessor_terminal_ref: ArtifactRef | None,
        expected_action_generation: int | None = None,
        historical_policy_ref: ArtifactRef | None = None,
        historical_action_job_id: str | None = None,
        history_prefix: _CandidateExperimentHistoryPrefix | None = None,
    ) -> VerifiedCandidateExperimentOrigin:
        """Reopen exactly the historical prefix selected by one request.

        This is historical evidence, not permission to act against the current
        head. Live consumers must independently fence that head and its lease.
        """
        from dataclasses import replace

        from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
        from polisyos.runtime.quality.acquisition_evaluation_history import (
            _candidate_experiment_history_prefix_origin,
            verify_candidate_experiment_terminal_history,
        )

        service = getattr(self._core_source_resolver, "__self__", None)
        prefix_origin = (
            None
            if history_prefix is None
            else _candidate_experiment_history_prefix_origin(
                history_prefix, control_service=service
            )
        )
        if prefix_origin is not None and (
            (prefix_origin.tenant_id, prefix_origin.cell_id, prefix_origin.run_id)
            != (self._tenant_id, self._cell_id, run_id)
            or self._action_outcome_reader is not history_prefix.sink
            or self._artifact_store is not history_prefix.artifact_store
            or self._control_store is not history_prefix.control_store
            or self._event_log is not history_prefix.event_log
            or (
                expected_action_generation is not None
                and len(prefix_origin.candidate_terminal_history_chain) + 1
                != expected_action_generation
            )
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_history_prefix_owner_mismatch")

        if predecessor_terminal_ref is None:
            if expected_action_generation not in {None, 1}:
                raise AcquisitionRouteClosureError("candidate_experiment_predecessor_not_selected")
            if historical_policy_ref is None and historical_action_job_id is None:
                origin = self._resolve_candidate_experiment_source(run_id=run_id)
                if prefix_origin is not None and not _candidate_model_values_same(
                    prefix_origin, origin
                ):
                    raise AcquisitionRouteClosureError("candidate_experiment_predecessor_changed")
                return origin
            if (
                historical_policy_ref is None
                or type(historical_action_job_id) is not str
                or not historical_action_job_id
            ):
                raise AcquisitionRouteClosureError("candidate_experiment_historical_anchor_missing")
            origin = self._resolve_candidate_experiment_source(
                run_id=run_id, historical_policy_ref=historical_policy_ref
            )
            heads = self._control_store.list_acquisition_action_heads_for_source(
                tenant_id=self._tenant_id,
                cell_id=self._cell_id,
                run_id=run_id,
                source_job_id=origin.source_job_id,
            )
            selected = tuple(
                head
                for head in heads
                if head.route_id == origin.route_id
                and head.action_generation == 1
                and head.job_id == historical_action_job_id
            )
            if len(selected) != 1:
                raise AcquisitionRouteClosureError("candidate_experiment_historical_anchor_missing")
            receipt = self._selected_candidate_experiment_receipt(selected[0])
            if (
                not _candidate_ref_same(receipt.policy_ref, historical_policy_ref)
                or self._control_store.get_acquisition_action_head(
                    tenant_id=self._tenant_id,
                    cell_id=self._cell_id,
                    run_id=run_id,
                    source_job_id=origin.source_job_id,
                    route_id=origin.route_id,
                    action_generation=1,
                )
                != selected[0]
            ):
                raise AcquisitionRouteClosureError("candidate_experiment_historical_policy_changed")
            if prefix_origin is not None and not _candidate_model_values_same(
                prefix_origin, origin
            ):
                raise AcquisitionRouteClosureError("candidate_experiment_predecessor_changed")
            return origin
        ref = predecessor_terminal_ref
        if (
            type(ref) is not ArtifactRef
            or not _candidate_ref_same(ref, ref)
            or ref.kind != "runtime_quality.acquisition_route_loop_receipt"
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_profile_invalid")
        if historical_action_job_id is not None:
            raise AcquisitionRouteClosureError("candidate_experiment_historical_anchor_invalid")
        if type(service) is not ControlPlaneService:
            raise AcquisitionRouteClosureError("candidate_experiment_history_owner_not_composed")
        # The selected terminal supplies a policy locator. The exact SQL head,
        # receipt profile and full signed terminal history authenticate it.
        from polisyos.runtime.http.services.control.run_lifecycle import (
            AcquisitionRouteLoopAuthoritySink,
        )

        sink = self._action_outcome_reader
        if (
            type(sink) is not AcquisitionRouteLoopAuthoritySink
            or service.acquisition_route_sink is not sink
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_history_owner_not_composed")
        selected_receipt = sink._read_verified_action_phase(
            str(ref.artifact_id), selected_ref=ref
        ).receipt
        if type(selected_receipt) not in {
            AcquisitionCandidateExperimentTerminalReceipt,
            AcquisitionCandidateExperimentTerminalReceiptV2,
        } or (
            selected_receipt.tenant_id,
            selected_receipt.cell_id,
            selected_receipt.run_id,
        ) != (self._tenant_id, self._cell_id, run_id):
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_not_selected")
        if historical_policy_ref is not None and not _candidate_ref_same(
            selected_receipt.policy_ref, historical_policy_ref
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_historical_policy_changed")
        selected_policy_ref = selected_receipt.policy_ref
        origin = self._resolve_candidate_experiment_source(
            run_id=run_id, historical_policy_ref=selected_policy_ref
        )
        scope = {
            "tenant_id": origin.tenant_id,
            "cell_id": origin.cell_id,
            "run_id": origin.run_id,
            "source_job_id": origin.source_job_id,
        }
        heads = self._control_store.list_acquisition_action_heads_for_source(**scope)
        selected = tuple(
            head
            for head in heads
            if head.route_id == origin.route_id
            and head.receipt_ref == str(ref.artifact_id)
            and head.receipt_manifest_profile_sha256 == ref.manifest_profile_sha256
            and head.receipt_phase == "terminal"
        )
        if len(selected) != 1:
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_not_selected")
        head = selected[0]
        if self._selected_candidate_experiment_receipt(head) != selected_receipt:
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_changed")
        if (
            expected_action_generation is not None
            and head.action_generation + 1 != expected_action_generation
        ):
            raise AcquisitionRouteClosureError(
                "candidate_experiment_predecessor_generation_invalid"
            )
        if prefix_origin is None:
            history = verify_candidate_experiment_terminal_history(
                control_service=service, head=head, terminal_ref=ref
            )
        else:
            history = prefix_origin.current_terminal_history
            if history is None or not _candidate_ref_same(history.terminal_ref, ref):
                raise AcquisitionRouteClosureError("candidate_experiment_predecessor_not_selected")
        prefix = (*history.origin.candidate_terminal_history_chain, history)
        if (
            len(prefix) != head.action_generation
            or history.head != head
            or not _candidate_model_values_same(
                replace(
                    history.origin,
                    current_action_head=None,
                    current_terminal_history=None,
                    candidate_terminal_history_chain=(),
                ),
                origin,
            )
            or self._control_store.get_acquisition_action_head(
                **scope, route_id=origin.route_id, action_generation=head.action_generation
            )
            != head
            or not _candidate_model_values_same(
                origin,
                self._resolve_candidate_experiment_source(
                    run_id=run_id, historical_policy_ref=selected_policy_ref
                ),
            )
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_changed")
        result = replace(
            origin,
            candidate_terminal_history_chain=prefix,
            current_terminal_history=history,
        )
        if prefix_origin is not None and not _candidate_model_values_same(prefix_origin, result):
            raise AcquisitionRouteClosureError("candidate_experiment_predecessor_changed")
        return result

    def resolve_current_candidate_experiment(
        self,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> VerifiedCandidateExperimentOrigin:
        """Return the owner-replayed source and current history projection.

        This compatibility entry point intentionally exposes only the origin;
        callers that need its verified owner outcomes use the private composed
        resolution below.
        """
        return self._resolve_current_candidate_experiment_resolution(
            run_id=run_id,
            before_action_generation=before_action_generation,
            action_job_id=action_job_id,
        ).origin

    def _resolve_current_candidate_experiment_resolution(
        self,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> _ResolvedCurrentCandidateExperiment:
        """Replay the live experiment source and retain its owner-verified outcomes.

        Each terminal generation is accepted only after its experiment-aware
        historical owner replays the selected profile, PA2 history, action,
        source, evaluation, and atomic frontier. This result is still not a live
        lease or effect permit. The exact tuple is for one in-process read only;
        it must not be reused as permission or across a later operation.
        """
        from dataclasses import replace

        from polisyos.runtime.http.services.control.run_lifecycle import (
            AcquisitionRouteLoopAuthoritySink,
            ControlPlaneService,
            VerifiedAcquisitionActionOutcome,
        )
        from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord

        if before_action_generation is not None:
            raise AcquisitionRouteClosureError(
                "candidate_experiment_historical_cutoff_not_established"
            )
        if action_job_id is not None and (not isinstance(action_job_id, str) or not action_job_id):
            raise AcquisitionRouteClosureError("candidate_experiment_action_job_invalid")

        origin = self._resolve_candidate_experiment_source(run_id=run_id)
        scope = {
            "tenant_id": self._tenant_id,
            "cell_id": self._cell_id,
            "run_id": run_id,
            "source_job_id": origin.source_job_id,
        }
        heads = self._control_store.list_acquisition_action_heads_for_source(**scope)
        if any(
            type(head) is not AcquisitionActionHeadRecord
            or (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            != (self._tenant_id, self._cell_id, run_id, origin.source_job_id)
            or head.route_id != origin.route_id
            for head in heads
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_foreign_action_head")
        if tuple(head.action_generation for head in heads) != tuple(range(1, len(heads) + 1)):
            raise AcquisitionRouteClosureError("candidate_experiment_action_history_not_contiguous")

        reader = self._action_outcome_reader
        service = getattr(self._core_source_resolver, "__self__", None)
        owner_reader = getattr(
            AcquisitionRouteLoopAuthoritySink, "experiment_action_outcomes", None
        )
        if (
            type(reader) is not AcquisitionRouteLoopAuthoritySink
            or type(service) is not ControlPlaneService
            or reader._control_store is not self._control_store
            or reader._artifact_store is not self._artifact_store
            or reader._event_log is not self._event_log
            or getattr(reader._core_source_resolver, "__self__", None) is not service
            or not callable(owner_reader)
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_history_owner_not_composed")
        try:
            outcomes = owner_reader(
                reader,
                **scope,
                route_id=origin.route_id,
                verified_origin=origin,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError(
                "candidate_experiment_action_history_not_verified"
            ) from exc
        if (
            not isinstance(outcomes, tuple)
            or any(type(item) is not VerifiedAcquisitionActionOutcome for item in outcomes)
            or tuple(item.head for item in outcomes) != heads
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_action_history_not_verified")

        if tuple(item.head.action_generation for item in outcomes) != tuple(
            range(1, len(outcomes) + 1)
        ):
            raise AcquisitionRouteClosureError("candidate_experiment_action_history_not_contiguous")
        current_head = None
        current_terminal_history = None
        previous_terminal_history: CandidateExperimentTerminalHistory | None = None
        terminal_history_chain: list[CandidateExperimentTerminalHistory] = []
        for index, outcome in enumerate(outcomes):
            head = outcome.head
            receipt = outcome.latest_receipt
            is_terminal = type(receipt) in {
                AcquisitionCandidateExperimentTerminalReceipt,
                AcquisitionCandidateExperimentTerminalReceiptV2,
            }
            if is_terminal:
                history = outcome.candidate_experiment_terminal_history
                if (
                    type(history) is not CandidateExperimentTerminalHistory
                    or history.head != head
                    or history.terminal != receipt
                    or history.terminal_ref.artifact_id
                    != ArtifactID.model_validate(head.receipt_ref)
                    or history.terminal_ref.manifest_profile_sha256
                    != head.receipt_manifest_profile_sha256
                    or history.origin.candidate_terminal_history_chain
                    != tuple(terminal_history_chain)
                ):
                    raise AcquisitionRouteClosureError(
                        "candidate_experiment_terminal_history_not_verified"
                    )
                if type(receipt) is AcquisitionCandidateExperimentTerminalReceiptV2:
                    # The canonical history owner has replayed the exact reuse
                    # occurrence, including its retained or blocked outcome.
                    if (
                        previous_terminal_history is None
                        or history.frontier_before is None
                        or history.frontier_before != previous_terminal_history.frontier_after
                    ):
                        raise AcquisitionRouteClosureError(
                            "candidate_experiment_terminal_generation_fold_mismatch"
                        )
                else:
                    decision = history.decision
                    if decision is None or history.selected_basis is None:
                        raise AcquisitionRouteClosureError(
                            "candidate_experiment_terminal_evaluation_history_not_established"
                        )
                    if previous_terminal_history is None:
                        if (
                            decision.prior_basis_ref is not None
                            or decision.prior_evaluation is not None
                            or decision.expected_frontier_revision != 0
                            or decision.expected_frontier_ref is not None
                        ):
                            raise AcquisitionRouteClosureError(
                                "candidate_experiment_prior_frontier_history_not_established"
                            )
                    else:
                        previous = previous_terminal_history
                        if previous.frontier_after is None:
                            if (
                                previous.evaluation is not None
                                or decision.comparison_result != "not_established"
                                or decision.predicate_provenance != "not_established"
                                or decision.prior_basis_ref is not None
                                or decision.prior_evaluation is not None
                                or decision.expected_frontier_ref is not None
                                or decision.expected_frontier_revision != 0
                            ):
                                raise AcquisitionRouteClosureError(
                                    "candidate_experiment_terminal_generation_fold_mismatch"
                                )
                        elif (
                            previous.selected_basis is None
                            or not _candidate_ref_same(
                                decision.prior_basis_ref,
                                previous.terminal.selected_basis_ref,
                            )
                            or decision.expected_frontier_ref
                            != previous.frontier_after.frontier_ref
                            or decision.expected_frontier_revision
                            != previous.frontier_after.revision
                            or previous.evaluation is None
                            or decision.prior_evaluation is None
                            or not _candidate_model_values_same(
                                decision.prior_evaluation,
                                previous.evaluation.selected.model_copy(
                                    update={"basis_ref": previous.terminal.selected_basis_ref}
                                ),
                            )
                        ):
                            raise AcquisitionRouteClosureError(
                                "candidate_experiment_terminal_generation_fold_mismatch"
                            )
                    if receipt.terminal_outcome == "candidate_evaluation_retained":
                        previous = previous_terminal_history
                        continuation = history.continuation
                        current_basis = history.current_basis
                        if (
                            previous is None
                            or previous.selected_basis is None
                            or continuation is None
                            or current_basis is None
                            or not _candidate_model_values_same(
                                history.selected_basis, previous.selected_basis
                            )
                            or not _candidate_model_values_same(
                                history.evaluation, previous.evaluation
                            )
                            or not (
                                set(previous.selected_basis.limitations)
                                | set(current_basis.limitations)
                                | (
                                    set(previous.continuation.limitations)
                                    if previous.continuation is not None
                                    else set()
                                )
                            ).issubset(continuation.limitations)
                        ):
                            raise AcquisitionRouteClosureError(
                                "candidate_experiment_retained_limitations_not_established"
                            )
                current_terminal_history = history
                previous_terminal_history = history
                terminal_history_chain.append(history)
            elif type(receipt) is not AcquisitionCandidateExperimentPhaseReceipt:
                raise AcquisitionRouteClosureError("candidate_experiment_action_receipt_untyped")
            if (
                (receipt.tenant_id, receipt.cell_id, receipt.run_id, receipt.source_job_id)
                != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
                or receipt.route_id != origin.route_id
                or receipt.source_payload_ref != origin.source_payload_ref
                or receipt.capability_manifest_ref != origin.capability_manifest_ref
                or receipt.request_content_hash != origin.request_content_hash
                or not _candidate_model_values_same(receipt.policy_scope, origin.policy_scope)
                or not _candidate_ref_same(receipt.policy_ref, origin.policy_ref)
                or not _candidate_model_values_same(
                    receipt.voi_decision, origin.source_cycle.voi_decision
                )
                or receipt.action_generation != head.action_generation
                or receipt.job_id != head.job_id
                or receipt.coarse_phase != head.coarse_phase
                or receipt.receipt_phase != head.receipt_phase
                or receipt.recovery_state != head.recovery_state
                or receipt.predecessor_receipt_ref != head.predecessor_receipt_ref
                or head.receipt_ref != head.receipt_sha256
            ):
                raise AcquisitionRouteClosureError("candidate_experiment_action_identity_mismatch")
            if (
                index == len(outcomes) - 1
                and action_job_id is not None
                and action_job_id != head.job_id
            ):
                raise AcquisitionRouteClosureError("candidate_experiment_action_pending")
            if index < len(outcomes) - 1 and not is_terminal:
                raise AcquisitionRouteClosureError(
                    "candidate_experiment_action_generation_predecessor_not_terminal"
                )
            current_head = head

        refreshed_origin = self._resolve_candidate_experiment_source(run_id=run_id)
        if not _candidate_model_values_same(origin, refreshed_origin):
            raise AcquisitionRouteClosureError("candidate_experiment_source_changed")
        if self._control_store.list_acquisition_action_heads_for_source(**scope) != heads:
            raise AcquisitionRouteClosureError("candidate_experiment_action_history_changed")
        return _ResolvedCurrentCandidateExperiment(
            origin=replace(
                refreshed_origin,
                current_action_head=current_head,
                current_terminal_history=current_terminal_history,
                candidate_terminal_history_chain=tuple(terminal_history_chain),
            ),
            outcomes=outcomes,
        )

    def resolve_current_route(
        self,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> VerifiedAcquisitionRouteClosure:
        """Resolve the sole completed natural-language costed source closure."""

        origin = self._resolve_verified_origin(run_id=run_id)
        job = origin.job
        payload_ref = origin.payload_ref
        manifest_ref = origin.manifest_ref
        compiled_ref = origin.compiled_ref
        terminal_event_id = origin.terminal_event_id
        compiled = origin.compiled
        generation_run = origin.generation_run
        source_cycle = origin.source_cycle
        report = origin.report
        planner_record = origin.planner_record
        cost = origin.cost
        if cost is None:
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        schedule = load_planner_acquisition_cost_schedule()
        recomputed = produce_acquisition_cost_basis_record(
            missing_distribution=cost.missing_distribution,
            strategy=planner_record.recommended_strategy,
            schedule=schedule,
        )
        if (
            recomputed is None
            or recomputed != cost
            or source_cycle.acquisition_cost_basis_hash != cost.record_content_hash
            or cost.schedule_content_hash != schedule.schedule_content_hash
        ):
            raise AcquisitionRouteClosureError("cost_basis_revalidation_required")
        route_source_cycle = source_cycle
        route_id = _content_hash(
            {
                "tenant_id": self._tenant_id,
                "cell_id": self._cell_id,
                "run_id": run_id,
                "source_job_id": job.job_id,
                "compiled_ref": compiled_ref,
                "design_problem_ref": compiled.design_problem_ref,
                "planner_run_id": report.run_id,
                "planner_record_id": planner_record.acquisition_id,
                "cost_basis_hash": cost.record_content_hash,
            }
        )
        (
            generation_run,
            source_cycle,
            basis_transitions,
            candidate_transitions,
            candidate_history,
        ) = self._latest_verified_source(
            run_id=run_id,
            source_job_id=job.job_id,
            route_id=route_id,
            compiled_ref=compiled_ref,
            planner_report_hash=agent_action_content_hash(report),
            cost_basis_hash=cost.record_content_hash,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
            generation_run=generation_run,
            source_cycle=source_cycle,
            before_action_generation=before_action_generation,
            action_job_id=action_job_id,
        )
        _resolve_source_cycle_problem_basis(
            generation_run=generation_run,
            source_cycle=source_cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
            acquisition_basis_transitions=basis_transitions,
            candidate_basis_transitions=candidate_transitions,
        )
        return VerifiedAcquisitionRouteClosure(
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
            source_job_id=job.job_id,
            source_payload_ref=payload_ref,
            capability_manifest_ref=manifest_ref,
            compiled_ref=compiled_ref,
            compiled_content_hash=compiled.content_hash,
            terminal_event_id=terminal_event_id,
            design_problem_ref=compiled.design_problem_ref,
            design_problem=compiled.design_problem,
            generation_run=generation_run,
            source_cycle=source_cycle,
            route_source_cycle_index=route_source_cycle.cycle_index,
            acquisition_basis_transitions=basis_transitions,
            candidate_basis_transitions=candidate_transitions,
            candidate_terminal_history=candidate_history,
            planner_report=report,
            planner_record=planner_record,
            cost_basis_record=cost,
            cost_basis_hash=cost.record_content_hash,
            route_id=route_id,
        )

    def _latest_verified_source(
        self,
        *,
        run_id: str,
        source_job_id: str,
        route_id: str,
        compiled_ref: str,
        planner_report_hash: str,
        cost_basis_hash: str,
        design_problem: DesignProblem,
        design_problem_ref: str,
        generation_run: GenerationCycleRun,
        source_cycle: GenerationCycleRecord,
        before_action_generation: int | None,
        action_job_id: str | None,
    ) -> tuple[
        GenerationCycleRun,
        GenerationCycleRecord,
        tuple[AcquisitionOverlayReentryReceipt, ...],
        tuple[CandidateSourceReentryReceipt, ...],
        tuple[CandidateEvaluationTerminalHistory, ...],
    ]:
        """Fold only verified terminal re-entry receipts over the compiled source."""

        if before_action_generation is not None and before_action_generation < 1:
            raise AcquisitionRouteClosureError("continuation_action_generation_invalid")
        if before_action_generation is not None and action_job_id is not None:
            raise AcquisitionRouteClosureError("continuation_action_cutoff_ambiguous")
        reader = self._action_outcome_reader
        if reader is None:
            list_heads = getattr(self._control_store, "list_acquisition_action_heads", None)
            if not callable(list_heads):
                raise AcquisitionRouteClosureError("continuation_selector_not_composed")
            heads = list_heads(
                tenant_id=self._tenant_id,
                cell_id=self._cell_id,
                run_id=run_id,
                source_job_id=source_job_id,
                route_id=route_id,
            )
            if heads:
                raise AcquisitionRouteClosureError("continuation_selector_not_composed")
            outcomes: tuple[_VerifiedActionOutcome, ...] = ()
        else:
            try:
                outcomes = reader.action_outcomes(
                    tenant_id=self._tenant_id,
                    cell_id=self._cell_id,
                    run_id=run_id,
                    source_job_id=source_job_id,
                    route_id=route_id,
                )
            except (AttributeError, TypeError, ValueError, OSError) as exc:
                raise AcquisitionRouteClosureError(
                    "acquisition_action_history_not_verified"
                ) from exc
            if not isinstance(outcomes, tuple):
                raise AcquisitionRouteClosureError("acquisition_action_history_not_verified")
            if action_job_id is not None:
                same_job = tuple(item for item in outcomes if item.head.job_id == action_job_id)
                if len(same_job) > 1:
                    raise AcquisitionRouteClosureError(
                        "acquisition_action_job_generation_ambiguous"
                    )
                if same_job:
                    before_action_generation = same_job[0].head.action_generation
                elif outcomes:
                    latest = outcomes[-1].latest_receipt
                    if not isinstance(
                        latest,
                        (
                            AcquisitionRouteLoopReceipt,
                            AcquisitionRouteLoopReceiptV2,
                            AcquisitionCandidateRouteLoopReceipt,
                        ),
                    ) or latest.terminal_outcome not in {
                        "quarantined_no_growth",
                        "reentry_completed",
                        "source_admitted_evaluation_retained",
                        "candidate_reentry_completed",
                        "candidate_evaluation_retained",
                    }:
                        raise AcquisitionRouteClosureError(
                            "acquisition_action_generation_not_resolvable"
                        )
                    before_action_generation = outcomes[-1].head.action_generation + 1
                else:
                    before_action_generation = 1

        selected_run = generation_run
        selected_cycle = source_cycle
        basis_transitions: list[AcquisitionOverlayReentryReceipt] = []
        candidate_transitions: list[CandidateSourceReentryReceipt] = []
        candidate_history: list[CandidateEvaluationTerminalHistory] = []
        for snapshot in outcomes:
            receipt = snapshot.latest_receipt
            if (
                receipt.action_generation != snapshot.head.action_generation
                or receipt.action_generation < 1
            ):
                raise AcquisitionRouteClosureError("acquisition_action_history_not_verified")
            if (
                before_action_generation is not None
                and snapshot.head.action_generation >= before_action_generation
            ):
                continue
            if not isinstance(
                receipt,
                (
                    AcquisitionRouteLoopReceipt,
                    AcquisitionRouteLoopReceiptV2,
                    AcquisitionCandidateRouteLoopReceipt,
                ),
            ):
                raise AcquisitionRouteClosureError("acquisition_action_outcome_not_terminal")
            if (
                receipt.tenant_id != self._tenant_id
                or receipt.cell_id != self._cell_id
                or receipt.run_id != run_id
                or receipt.source_job_id != source_job_id
                or receipt.route_id != route_id
                or receipt.compiled_ref != compiled_ref
                or receipt.planner_report_hash != planner_report_hash
                or receipt.cost_basis_hash != cost_basis_hash
            ):
                raise AcquisitionRouteClosureError("acquisition_action_source_identity_mismatch")
            if isinstance(receipt, AcquisitionCandidateRouteLoopReceipt):
                history = snapshot.candidate_terminal_history
                if (
                    type(history) is not CandidateEvaluationTerminalHistory
                    or history.head != snapshot.head
                    or not _candidate_model_values_same(history.terminal, receipt)
                ):
                    raise AcquisitionRouteClosureError(
                        "candidate_terminal_history_owner_not_established"
                    )
                candidate_history.append(history)
            if receipt.terminal_outcome == "quarantined_no_growth":
                continue
            if receipt.terminal_outcome == "candidate_reentry_completed":
                from polisyos.runtime.quality.candidate_source_reentry_history import (
                    verify_candidate_source_reentry_history,
                )

                if (
                    not isinstance(
                        receipt, (AcquisitionRouteLoopReceipt, AcquisitionCandidateRouteLoopReceipt)
                    )
                    or receipt.candidate_action_ref is None
                    or receipt.candidate_reentry_ref is None
                ):
                    raise AcquisitionRouteClosureError("candidate_reentry_profile_missing")
                transition = verify_candidate_source_reentry_history(
                    artifact_store=self._artifact_store,
                    event_log=self._event_log,
                    control_store=self._control_store,
                    receipt_ref=receipt.candidate_reentry_ref,
                    expected_tenant_id=self._tenant_id,
                    expected_cell_id=self._cell_id,
                    expected_run_id=run_id,
                    expected_source_job_id=source_job_id,
                    expected_action_job_id=receipt.job_id,
                    expected_route_id=route_id,
                    expected_action_generation=receipt.action_generation,
                    expected_selected_action_ref=receipt.candidate_action_ref,
                )
                validate_candidate_source_continuation(selected_run, transition)
                if transition.source_cycle_index != selected_cycle.cycle_index:
                    raise AcquisitionRouteClosureError("candidate_reentry_source_cycle_mismatch")
                selected_run = transition.continued_generation_run
                selected_cycle = transition.new_cycle
                candidate_transitions.append(transition)
                continue
            if receipt.terminal_outcome == "candidate_evaluation_retained":
                if not isinstance(receipt, AcquisitionCandidateRouteLoopReceipt):
                    raise AcquisitionRouteClosureError(
                        "candidate_retained_history_owner_not_established"
                    )
                continue
            if receipt.terminal_outcome == "source_admitted_evaluation_retained":
                from polisyos.runtime.quality.acquisition_evaluation_history import (
                    verify_retained_route_accumulator,
                )

                verify_retained_route_accumulator(
                    artifact_store=self._artifact_store,
                    event_log=self._event_log,
                    control_store=self._control_store,
                    snapshot=snapshot,
                    terminal=receipt,
                    generation_run=selected_run,
                    source_cycle=selected_cycle,
                    design_problem_ref=design_problem_ref,
                )
                # The actual selected evaluation tuple was reconciled above;
                # admission changed, the evaluation accumulator did not.
                continue
            selected_run, selected_cycle = self._verified_reentry_source(
                snapshot=snapshot,
                terminal=receipt,
                source_run=selected_run,
                source_cycle=selected_cycle,
                design_problem=design_problem,
                design_problem_ref=design_problem_ref,
                route_id=route_id,
                source_job_id=source_job_id,
                acquisition_basis_transitions=tuple(basis_transitions),
                candidate_basis_transitions=tuple(candidate_transitions),
            )
            # The preceding call verified this exact immutable source/event/
            # predecessor relation. Reload its typed body for the basis fold;
            # never derive a transition from a same-ID marker alone.
            transition = AcquisitionOverlayReentryReceipt.model_validate(
                self._read_json_artifact(
                    receipt.reentry_receipt_ref,
                    expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                    expected_schema_name="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                    expected_schema_versions=("2.0",),
                )
            )
            basis_transitions.append(transition)
        return (
            selected_run,
            selected_cycle,
            tuple(basis_transitions),
            tuple(candidate_transitions),
            tuple(candidate_history),
        )

    def _verified_reentry_source(
        self,
        *,
        snapshot: object,
        terminal: AcquisitionTerminalReceipt,
        source_run: GenerationCycleRun,
        source_cycle: GenerationCycleRecord,
        design_problem: DesignProblem,
        design_problem_ref: str,
        route_id: str,
        source_job_id: str,
        acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = (),
        candidate_basis_transitions: tuple[CandidateSourceReentryReceipt, ...] = (),
    ) -> tuple[GenerationCycleRun, GenerationCycleRecord]:
        """Verify owner persistence, event scope, growth binding, and append-only N4 history."""

        if terminal.reentry_receipt_ref is None or not source_run.cycles:
            raise AcquisitionRouteClosureError("continuation_reentry_ref_missing")
        action_phase_ref = getattr(snapshot, "executing_phase_ref", None)
        if not isinstance(action_phase_ref, str):
            raise AcquisitionRouteClosureError("continuation_action_phase_missing")
        owner_refs = tuple(terminal.owner_receipt_refs)
        try:
            growth_refs = tuple(
                ref
                for ref in owner_refs
                if self._artifact_store.get_manifest(ArtifactID.model_validate(ref)).kind
                == "runtime_quality.acquisition_world_growth_receipt"
            )
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_growth_owner_unverified") from exc
        if len(growth_refs) != 1:
            raise AcquisitionRouteClosureError("continuation_growth_owner_ambiguous")
        from polisyos.runtime.quality.acquisition_world_growth import (
            AcquisitionWorldGrowthReceipt,
        )
        from polisyos.runtime.quality.authority_reconciliation import (
            reconcile_authority_ref,
        )

        growth_ref = growth_refs[0]
        try:
            growth_payload = self._read_json_artifact(
                growth_ref,
                expected_kind="runtime_quality.acquisition_world_growth_receipt",
                expected_schema_name=AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
                expected_schema_versions=("1.1",),
            )
            if (
                not isinstance(growth_payload, dict)
                or growth_payload.get("schema_version") != "AcquisitionWorldGrowthReceipt@1.1"
                or "action_phase_ref" not in growth_payload
            ):
                raise ValueError("growth schema or action phase absent")
            growth = AcquisitionWorldGrowthReceipt.model_validate(growth_payload)
            growth_report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=growth_ref,
                expected_tenant_id=self._tenant_id,
                expected_cell_id=self._cell_id,
                expected_run_id=terminal.run_id,
                expected_job_id=source_job_id,
            )
            growth_manifest = self._artifact_store.get_manifest(
                ArtifactID.model_validate(growth_ref)
            )
            if (
                growth_manifest.producer is None
                or growth_manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
                or growth_report.durable_event_id is None
                or growth.action_phase_ref != action_phase_ref
                or growth.selection.key
                != (self._tenant_id, self._cell_id, terminal.run_id, route_id)
                or growth.selection.design_problem_ref != design_problem_ref
            ):
                raise ValueError("growth reentry binding mismatch")
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_growth_owner_unverified") from exc

        reentry_ref = terminal.reentry_receipt_ref
        try:
            reentry_payload = self._read_json_artifact(
                reentry_ref,
                expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                expected_schema_name="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                expected_schema_versions=("1.0", "2.0"),
            )
            if not isinstance(reentry_payload, dict) or "schema_version" not in reentry_payload:
                raise AcquisitionRouteClosureError("continuation_schema_version_missing")
            if reentry_payload["schema_version"] in {
                "policyos.runtime.acquisition_overlay_reentry.v1",
                "policyos.runtime.acquisition_overlay_reentry.v2",
            }:
                raise AcquisitionRouteClosureError("legacy_occurrence_unbound")
            if (
                reentry_payload["schema_version"]
                != "policyos.runtime.acquisition_overlay_reentry.v3"
            ):
                raise AcquisitionRouteClosureError("continuation_schema_version_invalid")
            reentry = AcquisitionOverlayReentryReceipt.model_validate(reentry_payload)
            reentry_manifest = self._artifact_store.get_manifest(
                ArtifactID.model_validate(reentry_ref)
            )
            if (
                reentry_manifest.producer is None
                or reentry_manifest.producer.component
                != "polisyos.runtime.acquisition_world_growth"
            ):
                raise ValueError("reentry producer mismatch")
            if not reentry.schema_version.endswith(".v3"):
                raise AcquisitionRouteClosureError("legacy_occurrence_unbound")
            if (
                reentry_manifest.artifact_schema is None
                or reentry_manifest.artifact_schema.version != "2.0"
            ):
                raise ValueError("v3 reentry schema version mismatch")
            reentry_event_id = "evt_acquisition_reentry_" + growth_ref.removeprefix("sha256:")
            reentry_report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=reentry_ref,
                expected_tenant_id=self._tenant_id,
                expected_cell_id=self._cell_id,
                expected_run_id=terminal.run_id,
                expected_job_id=source_job_id,
            )
            rows = self._event_log.list_events(event_id=reentry_event_id, limit=2)
            if (
                reentry_report.durable_event_id != reentry_event_id
                or len(rows) != 1
                or rows[0].event.event_source != "polisyos.runtime.acquisition_world_growth"
                or rows[0].event.producer_component != "polisyos.runtime.acquisition_world_growth"
                or rows[0].event.phase != "reentry_terminal"
                or rows[0].event.state_after != "reentry_terminal"
                or rows[0].event.tenant_id != self._tenant_id
                or rows[0].event.cell_id != self._cell_id
                or rows[0].event.run_id != terminal.run_id
                or rows[0].event.job_id != source_job_id
                or reentry_ref not in rows[0].event.artifact_refs
            ):
                raise ValueError("reentry event binding mismatch")
            if (
                reentry.source_run_id != source_run.run_id
                or reentry.design_problem_ref != design_problem_ref
                or reentry.source_cycle_index != source_cycle.cycle_index
                or reentry.source_candidate_ref != source_cycle.selected_candidate_ref
                or reentry.new_cycle.cycle_index != source_cycle.cycle_index + 1
                or reentry.new_cycle.design_problem_ref != design_problem_ref
                or reentry.new_cycle.design_problem_basis_ref
                != _problem_ref(
                    _resolve_source_cycle_problem_basis(
                        generation_run=source_run,
                        source_cycle=source_cycle,
                        design_problem=design_problem,
                        design_problem_ref=design_problem_ref,
                        acquisition_basis_transitions=acquisition_basis_transitions,
                        candidate_basis_transitions=candidate_basis_transitions,
                    )
                )
                or reentry.overlay_receipt_ref
                != str(growth.activation.overlay_admission_receipt_ref.artifact_id)
                or reentry.semantic_epoch_production_receipt_ref
                != str(growth.activation.semantic_epoch_production_receipt_ref.artifact_id)
                or reentry.admitted_observation_count
                != growth.previously_active_observations + growth.admitted_observation_delta
            ):
                raise ValueError("reentry source or growth binding mismatch")
            validate_acquisition_overlay_continuation(source_run, reentry)
        except AcquisitionRouteClosureError:
            raise
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_reentry_unverified") from exc
        continued = reentry.continued_generation_run
        if (
            continued is None
            or generation_cycle_run_content_hash(continued)
            != reentry.continued_generation_run_content_hash
        ):
            raise AcquisitionRouteClosureError("continuation_run_missing")
        return continued, reentry.new_cycle

    def _resolve_terminal_event(
        self,
        *,
        run_id: str,
        job_id: str,
        compiled_ref: str,
        manifest_ref: str,
    ) -> str:
        matches = [
            row.event
            for row in self._event_log.list_events(run_id=run_id, job_id=job_id)
            if row.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
            and row.event.phase == "job_execution"
            and row.event.state_before == "running"
            and row.event.state_after == "completed"
            and row.event.tenant_id == self._tenant_id
            and row.event.cell_id == self._cell_id
            and compiled_ref in row.event.artifact_refs
            and manifest_ref in row.event.artifact_refs
        ]
        if not matches:
            raise AcquisitionRouteClosureError("source_terminal_event_missing")
        if len(matches) != 1:
            raise AcquisitionRouteClosureError("source_terminal_event_ambiguous")
        return matches[0].event_id

    def _read_json_artifact(
        self,
        ref: str | ArtifactRef,
        *,
        expected_kind: str,
        expected_schema_name: str,
        expected_schema_versions: tuple[str, ...] = ("1.0",),
    ) -> object:
        from polisyos.core.artifacts import load_core_json_artifact

        try:
            selected_ref = ref if isinstance(ref, ArtifactRef) else ArtifactID.model_validate(ref)
            artifact_id = (
                selected_ref.artifact_id if isinstance(selected_ref, ArtifactRef) else selected_ref
            )
            selected_id = str(artifact_id)
            if not self._artifact_store.has(selected_ref):
                raise ValueError("artifact missing")
            blob = self._artifact_store.get_bytes(selected_ref)
            if selected_id != f"sha256:{hashlib.sha256(blob).hexdigest()}":
                raise ValueError("artifact content mismatch")
            manifest = self._artifact_store.get_manifest(selected_ref)
            schema = manifest.artifact_schema
            if (
                manifest.kind != expected_kind
                or schema is None
                or schema.name != expected_schema_name
                or schema.version not in expected_schema_versions
            ):
                raise ValueError("artifact manifest mismatch")
            return load_core_json_artifact(
                self._artifact_store, selected_ref, raw_payload_bytes=blob
            )
        except Exception as exc:
            raise AcquisitionRouteClosureError("source_artifact_unverified") from exc


def _content_hash(payload: object) -> str:
    return f"sha256:{canon.content_hash(canon.to_canonical_bytes(payload, canon.CanonSpec()))}"


def persist_world_commit_and_reenter(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    reentry: Callable[[], str],
) -> AcquisitionRoutePhaseHead:
    """Persist/read back the recovery head before attempting direct re-entry."""

    if pending_receipt.receipt_phase != "world_committed_reentry_pending":
        raise ValueError("world_commit_pending_receipt_required")
    pending_head = sink.persist_phase(pending_receipt)
    if (
        pending_head.receipt_phase != "world_committed_reentry_pending"
        or sink.get_head(pending_receipt) != pending_head
    ):
        raise RuntimeError("world_commit_pending_head_readback_failed")
    try:
        reentry_ref = reentry()
    except Exception as exc:
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_required") from exc
    return _persist_terminal_after_reentry(
        sink=sink,
        pending_receipt=pending_receipt,
        pending_receipt_ref=pending_head.receipt_ref,
        reentry_ref=reentry_ref,
    )


def resume_world_committed_reentry(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    reentry: Callable[[], str],
) -> AcquisitionRoutePhaseHead:
    """Resume only re-entry from an exact durable world-committed head."""

    pending_head = sink.get_head(pending_receipt)
    if (
        pending_head is None
        or pending_head.receipt_phase != "world_committed_reentry_pending"
        or pending_head.recovery_state != "reentry_recovery_required"
    ):
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_head_missing")
    try:
        reentry_ref = reentry()
    except Exception as exc:
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_required") from exc
    return _persist_terminal_after_reentry(
        sink=sink,
        pending_receipt=pending_receipt,
        pending_receipt_ref=pending_head.receipt_ref,
        reentry_ref=reentry_ref,
    )


def _persist_terminal_after_reentry(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    pending_receipt_ref: str,
    reentry_ref: str,
) -> AcquisitionRoutePhaseHead:
    if not isinstance(reentry_ref, str) or not reentry_ref.startswith("sha256:"):
        raise AcquisitionRouteRecoveryRequired("reentry_receipt_invalid")
    terminal = AcquisitionRouteLoopReceipt(
        receipt_id=f"{pending_receipt.receipt_id}.terminal",
        tenant_id=pending_receipt.tenant_id,
        cell_id=pending_receipt.cell_id,
        run_id=pending_receipt.run_id,
        source_job_id=pending_receipt.source_job_id,
        route_id=pending_receipt.route_id,
        action_generation=pending_receipt.action_generation,
        job_id=pending_receipt.job_id,
        compiled_ref=pending_receipt.compiled_ref,
        planner_report_hash=pending_receipt.planner_report_hash,
        cost_basis_hash=pending_receipt.cost_basis_hash,
        decision_ref=pending_receipt.decision_ref,
        terminal_outcome="reentry_completed",
        predecessor_receipt_ref=pending_receipt_ref,
        owner_receipt_refs=pending_receipt.owner_receipt_refs,
        reentry_receipt_ref=reentry_ref,
        generated_at=datetime.now(pending_receipt.generated_at.tzinfo),
    )
    return sink.persist_terminal(terminal)


__all__ = [
    "AcquisitionCandidateExperimentPhaseReceipt",
    "AcquisitionCandidateExperimentTerminalReceipt",
    "AcquisitionCandidateExperimentTerminalReceiptV2",
    "AcquisitionRouteClosureError",
    "AcquisitionRouteLoop",
    "AcquisitionRouteLoopReceipt",
    "AcquisitionRouteLoopReceiptV2",
    "AcquisitionRoutePhaseReceipt",
    "AcquisitionRouteRecoveryRequired",
    "AcquisitionTerminalReceipt",
    "VerifiedAcquisitionRouteClosure",
    "VerifiedCandidateExperimentOrigin",
    "VerifiedModelInputRoutingOrigin",
    "parse_acquisition_route_loop_receipt",
    "parse_acquisition_route_phase_receipt",
    "persist_world_commit_and_reenter",
    "resume_world_committed_reentry",
]
