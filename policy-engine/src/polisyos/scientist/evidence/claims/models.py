"""Typed claim contracts for Scientist decision artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef  # noqa: TC001
from polisyos.scientist.methods.search.readiness import DecisionReadiness  # noqa: TC001


class ClaimType(str, Enum):
    """Decision-bearing claim families tracked by the claim spine."""

    FACTUAL = "factual"
    CAUSAL = "causal"
    LEGAL = "legal"
    NORMATIVE = "normative"
    FORECAST = "forecast"
    DISTRIBUTIONAL = "distributional"
    WELFARE = "welfare"
    IMPLEMENTATION = "implementation"
    SOURCE_QUALITY = "source_quality"


class ClaimFamily(str, Enum):
    """Universal policy-design claim family assigned before producer evidence runs."""

    PREFERENCE = "preference"
    LIVED_EXPERIENCE = "lived_experience"
    ACCEPTABILITY = "acceptability"
    LEGITIMACY = "legitimacy"
    PROCEDURAL_FAIRNESS = "procedural_fairness"
    IMPLEMENTATION_FEASIBILITY = "implementation_feasibility"
    OBJECTION_DISSENT = "objection_dissent"
    CONTEXT_ONLY = "context_only"
    CAUSAL = "causal"
    DISTRIBUTIONAL = "distributional"
    WELFARE = "welfare"
    FORECAST = "forecast"
    IMPLEMENTATION = "implementation"


class ClaimUse(str, Enum):
    """Purpose boundary for a decomposed claim."""

    DECISION_SUPPORT = "decision_support"
    METHOD_PRECONDITION = "method_precondition"
    PARTICIPATION_LEGITIMACY = "participation_legitimacy"
    PARTICIPATION_CONTEXT = "participation_context"
    CONTEXT_ONLY = "context-only"
    SUPERIORITY = "superiority"
    IMPLEMENTATION_READINESS = "implementation_readiness"


class ClaimSourceClass(str, Enum):
    """Producer/source class carried by claim-decomposition records."""

    DETERMINISTIC_COMPILER = "deterministic_compiler"
    DETERMINISTIC_PRODUCER = "deterministic_producer"
    GOVERNED_RULE = "governed_rule"
    LEGAL_REQUIREMENT = "legal_requirement"
    DETERMINISTIC_CRITIC = "deterministic_critic"
    PRODUCER_BLOCKER = "producer_blocker"
    HISTORICAL_FAILURE = "historical_failure"
    HUMAN_REVIEWER = "human_reviewer"
    PUBLIC_CONTESTATION = "public_contestation"
    LLM_CANDIDATE = "llm_candidate"
    LLM_CRITIC = "llm_critic"
    LLM_DRAFTER = "llm_drafter"


class BaselineType(str, Enum):
    """Baseline seed family for later comparison evidence."""

    NO_ACTION = "no_action"
    STATUS_QUO = "status_quo"
    BUSINESS_AS_USUAL = "business_as_usual"
    NAMED_ALTERNATIVE = "named_alternative"
    FRAGILITY_SCENARIO = "fragility_scenario"
    SCENARIO_BASELINE = "scenario_baseline"


class AlternativeStatus(str, Enum):
    """Lifecycle state for a seeded policy alternative."""

    SEED = "seed"
    REJECTED = "rejected"
    SELECTED = "selected"


class AlternativeRejectionReason(str, Enum):
    """Typed reason a rejected alternative cannot support a superiority claim."""

    INFERIOR_EVIDENCE = "inferior_evidence"
    DOMINATED_FRONTIER = "dominated_frontier"
    LEGAL_BLOCKER = "legal_blocker"
    IMPLEMENTATION_INFEASIBILITY = "implementation_infeasibility"
    VALUE_CHOICE = "value_choice"
    ACCEPTED_DEFICIT = "accepted_deficit"


class ComparisonProducerFamily(str, Enum):
    """Producer family contributing evidence to a baseline/alternative comparison."""

    CLAIM_DECOMPOSITION = "claim_decomposition"
    FABRIC_SOURCE_CONTRACT = "fabric_source_contract"
    FOUNDRY_METHOD = "foundry_method"
    IR_CAUSAL_ANALYTICS = "ir_causal_analytics"
    SCHOLAR_SUPPORT = "scholar_support"
    RUNTIME_COMPILER = "runtime_compiler"


class ComparisonOptionKind(str, Enum):
    """Role an option plays in a W8.C comparison record."""

    SELECTED_OPTION = "selected_option"
    BASELINE = "baseline"
    ALTERNATIVE = "alternative"


class ComparisonOptionStatus(str, Enum):
    """Local status for one option inside a comparison record."""

    COMPARED = "compared"
    LIMITED = "limited"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class DominanceStatus(str, Enum):
    """Dominance relationship between the selected option and another option."""

    SELECTED_DOMINATES = "selected_dominates"
    OPTION_DOMINATES_SELECTED = "option_dominates_selected"
    NON_DOMINATED = "non_dominated"
    UNKNOWN = "unknown"


class BaselineComparisonStatus(str, Enum):
    """Completeness status for one superiority-claim comparison record."""

    COMPLETE = "complete"
    LIMITED = "limited"
    CONTESTED = "contested"
    BLOCKED = "blocked"


class ClaimSupportStatus(str, Enum):
    """How well available evidence supports a claim."""

    UNSUPPORTED = "unsupported"
    WEAKLY_SUPPORTED = "weakly_supported"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    NOT_EVALUABLE = "not_evaluable"


class ClaimPublishability(str, Enum):
    """Whether a claim may leave the current runtime boundary."""

    DRAFT = "draft"
    INTERNAL_ONLY = "internal_only"
    REVIEW_REQUIRED = "review_required"
    PUBLISHABLE = "publishable"
    BLOCKED = "blocked"


_LLM_SOURCE_CLASSES = {
    ClaimSourceClass.LLM_CANDIDATE,
    ClaimSourceClass.LLM_CRITIC,
    ClaimSourceClass.LLM_DRAFTER,
}


class MethodNeedPrecondition(BaseModel):
    """Claim-bound method need emitted as a precondition, not a method choice."""

    model_config = ConfigDict(extra="forbid")

    precondition_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_type: ClaimType
    method_need: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    source: Literal["claim_decomposition"] = "claim_decomposition"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonEvidenceRef(BaseModel):
    """Claim/option-bound producer evidence used by the W8.C compiler."""

    model_config = ConfigDict(extra="forbid")

    evidence_ref: str = Field(min_length=1)
    producer_family: ComparisonProducerFamily
    option_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    effective_support_count: int | None = Field(default=None, ge=0)
    raw_support_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RejectedOptionReasonRecord(BaseModel):
    """Typed reason why one alternative cannot carry a superiority claim."""

    model_config = ConfigDict(extra="forbid")

    reason_record_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    option_ref: str = Field(min_length=1)
    reason: AlternativeRejectionReason
    source_refs: list[str] = Field(default_factory=list)
    producer_family: ComparisonProducerFamily = ComparisonProducerFamily.RUNTIME_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)


class DominatedFrontierRecord(BaseModel):
    """Evidence-backed record that one option is dominated on the comparison frontier."""

    model_config = ConfigDict(extra="forbid")

    dominated_record_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    dominated_option_ref: str = Field(min_length=1)
    dominating_option_ref: str = Field(min_length=1)
    dominance_status: DominanceStatus
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    method_refs: list[str] = Field(default_factory=list)
    limitation_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_dominance_record(self) -> DominatedFrontierRecord:
        if self.dominance_status is DominanceStatus.SELECTED_DOMINATES and not self.metric_deltas:
            raise ValueError("selected-dominates records require metric_deltas")
        return self


class ComparisonOptionRecord(BaseModel):
    """Comparison evidence and status for a selected option, baseline, or alternative."""

    model_config = ConfigDict(extra="forbid")

    option_ref: str = Field(min_length=1)
    option_kind: ComparisonOptionKind
    label: str = Field(min_length=1)
    status: ComparisonOptionStatus
    evidence_refs: list[str] = Field(default_factory=list)
    data_refs: list[str] = Field(default_factory=list)
    scholar_refs: list[str] = Field(default_factory=list)
    method_refs: list[str] = Field(default_factory=list)
    ir_analytics_refs: list[str] = Field(default_factory=list)
    counterevidence_refs: list[str] = Field(default_factory=list)
    limitation_refs: list[str] = Field(default_factory=list)
    rejected_reasons: list[AlternativeRejectionReason] = Field(default_factory=list)
    dominance_status: DominanceStatus = DominanceStatus.UNKNOWN
    metric_values: dict[str, float] = Field(default_factory=dict)
    effective_independent_support_count: int = Field(default=0, ge=0)
    raw_support_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_option_semantics(self) -> ComparisonOptionRecord:
        if self.status is ComparisonOptionStatus.REJECTED and not self.rejected_reasons:
            raise ValueError("rejected comparison options require rejected_reasons")
        if (
            self.status is ComparisonOptionStatus.COMPARED
            and self.option_kind is not ComparisonOptionKind.SELECTED_OPTION
            and not self.evidence_refs
        ):
            raise ValueError("compared baseline/alternative options require evidence_refs")
        if self.raw_support_count < self.effective_independent_support_count:
            raise ValueError("raw support count cannot be below effective independent support")
        return self


class BaselineComparisonRecord(BaseModel):
    """Full W8.C comparison record for one superiority claim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    comparison_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    selected_option_ref: str = Field(min_length=1)
    selected_option_label: str = Field(min_length=1)
    baseline_refs: list[str] = Field(default_factory=list)
    alternative_refs: list[str] = Field(default_factory=list)
    baseline_types_covered: list[BaselineType] = Field(default_factory=list)
    selected_option_evidence_refs: list[str] = Field(default_factory=list)
    option_comparisons: list[ComparisonOptionRecord] = Field(default_factory=list)
    comparison_evidence: list[ComparisonEvidenceRef] = Field(default_factory=list)
    comparison_method_refs: list[str] = Field(default_factory=list)
    comparison_limitation_refs: list[str] = Field(default_factory=list)
    rejected_option_reasons: list[RejectedOptionReasonRecord] = Field(default_factory=list)
    dominated_frontier_records: list[DominatedFrontierRecord] = Field(default_factory=list)
    comparison_status: BaselineComparisonStatus = BaselineComparisonStatus.LIMITED
    producer_refs: list[str] = Field(default_factory=list)
    authority_boundary: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_comparison_record(self) -> BaselineComparisonRecord:
        if not self.baseline_refs or not self.alternative_refs:
            raise ValueError("comparison records require baseline_refs and alternative_refs")
        if not self.selected_option_evidence_refs:
            raise ValueError("comparison records require selected_option_evidence_refs")
        if not self.comparison_method_refs:
            raise ValueError("comparison records require comparison_method_refs")
        if not self.comparison_limitation_refs:
            raise ValueError("comparison records require explicit comparison_limitation_refs")
        option_refs = {option.option_ref for option in self.option_comparisons}
        required_refs = set(self.baseline_refs) | set(self.alternative_refs) | {
            self.selected_option_ref
        }
        missing = sorted(required_refs - option_refs)
        if missing:
            raise ValueError(f"comparison records are missing option comparisons {missing}")
        if not self.authority_boundary:
            self.authority_boundary = baseline_comparison_authority_boundary()
        return self


def baseline_comparison_authority_boundary() -> dict[str, list[str]]:
    """Return the W8.C authority boundary for comparison compiler records."""

    return {
        "authoritative_for": [
            "baseline_alternative_comparison_records",
            "superiority_claim_comparison_preconditions",
            "rejected_option_reason_records",
            "dominated_frontier_records",
        ],
        "may_not_use_for": [
            "legal_authority",
            "data_source_truth",
            "method_validity_truth",
            "scholar_support_truth",
            "projection_authority",
            "closeout_pass",
        ],
    }


class ClaimFamilyAssignment(BaseModel):
    """Typed assignment linking one claim to universal claim-family semantics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    assignment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_family: ClaimFamily
    claim_type: ClaimType
    claim_use: ClaimUse
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    baseline_refs: list[str] = Field(default_factory=list)
    alternative_refs: list[str] = Field(default_factory=list)
    comparison_refs: list[str] = Field(default_factory=list)
    method_need_preconditions: list[MethodNeedPrecondition] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_assignment_boundary(self) -> ClaimFamilyAssignment:
        if self.claim_use is ClaimUse.SUPERIORITY and (
            not self.baseline_refs or not self.alternative_refs
        ):
            raise ValueError("superiority assignments require baseline_refs and alternative_refs")
        if self.source_class in _LLM_SOURCE_CLASSES and self.claim_use is not ClaimUse.CONTEXT_ONLY:
            raise ValueError("LLM-sourced assignments must remain context-only until admitted")
        for precondition in self.method_need_preconditions:
            if precondition.claim_id != self.claim_id:
                raise ValueError("method precondition claim_id must match assignment claim_id")
        return self


class BaselineRecord(BaseModel):
    """Seed baseline record emitted before comparison evidence exists."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    baseline_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    baseline_type: BaselineType
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_baseline_source(self) -> BaselineRecord:
        if self.source_class in _LLM_SOURCE_CLASSES:
            raise ValueError("LLM-sourced baselines must stay in the hypothesis ledger")
        return self


class AlternativeRecord(BaseModel):
    """Seed alternative record, including rejected alternatives with typed reasons."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    alternative_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: AlternativeStatus = AlternativeStatus.SEED
    rejected_reasons: list[AlternativeRejectionReason] = Field(default_factory=list)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    source_class: ClaimSourceClass = ClaimSourceClass.DETERMINISTIC_COMPILER
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_alternative(self) -> AlternativeRecord:
        if self.status is AlternativeStatus.REJECTED and not self.rejected_reasons:
            raise ValueError("rejected alternatives require rejected_reasons")
        if self.status is not AlternativeStatus.REJECTED and self.rejected_reasons:
            raise ValueError("only rejected alternatives may carry rejected_reasons")
        if self.source_class in _LLM_SOURCE_CLASSES:
            raise ValueError("LLM-sourced alternatives must stay in the hypothesis ledger")
        return self


class ClaimRecord(BaseModel):
    """One typed claim plus its support, counterevidence, and release state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    claim_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_type: ClaimType
    claim_family: ClaimFamily | None = None
    claim_use: ClaimUse | None = None
    text: str = Field(min_length=1)
    normalized_subject: str | None = None
    support_status: ClaimSupportStatus
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    baseline_refs: list[str] = Field(default_factory=list)
    alternative_refs: list[str] = Field(default_factory=list)
    comparison_refs: list[str] = Field(default_factory=list)
    method_need_preconditions: list[MethodNeedPrecondition] = Field(default_factory=list)
    decomposition_source_class: ClaimSourceClass | None = None
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    counterevidence_refs: list[ArtifactRef] = Field(default_factory=list)
    uncertainty_profile_ref: ArtifactRef | None = None
    provenance_ref: ArtifactRef | None = None
    source_attribution: list[str] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_publishability(self) -> ClaimRecord:
        if self.claim_use is ClaimUse.SUPERIORITY and (
            not self.baseline_refs or not self.alternative_refs
        ):
            raise ValueError("superiority claims require baseline_refs and alternative_refs")
        if (
            self.decomposition_source_class in _LLM_SOURCE_CLASSES
            and self.claim_use is not None
            and self.claim_use is not ClaimUse.CONTEXT_ONLY
        ):
            raise ValueError("LLM-sourced decomposition claims must remain context-only")
        for precondition in self.method_need_preconditions:
            if precondition.claim_id != self.claim_id:
                raise ValueError("method precondition claim_id must match claim_id")
        if self.publishability is ClaimPublishability.PUBLISHABLE:
            if self.support_status is not ClaimSupportStatus.SUPPORTED:
                raise ValueError("publishable claims must be supported")
            if self.counterevidence_refs:
                raise ValueError("publishable claims cannot carry unresolved counterevidence")
            if self.blocked_reasons:
                raise ValueError("publishable claims cannot carry blocked_reasons")
            if (
                self.claim_type
                in {
                    ClaimType.CAUSAL,
                    ClaimType.LEGAL,
                    ClaimType.FORECAST,
                    ClaimType.DISTRIBUTIONAL,
                    ClaimType.WELFARE,
                }
                and not self.evidence_refs
            ):
                raise ValueError("publishable high-stakes claims require evidence_refs")
        if self.support_status is ClaimSupportStatus.REFUTED and (
            self.publishability is ClaimPublishability.PUBLISHABLE
        ):
            raise ValueError("refuted claims cannot be publishable")
        return self


class ClaimLedger(BaseModel):
    """CAS-persisted sidecar containing all projected claims for one run/artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    claims: list[ClaimRecord] = Field(default_factory=list)
    family_assignments: list[ClaimFamilyAssignment] = Field(default_factory=list)
    baseline_records: list[BaselineRecord] = Field(default_factory=list)
    alternative_records: list[AlternativeRecord] = Field(default_factory=list)
    comparison_records: list[BaselineComparisonRecord] = Field(default_factory=list)
    decision_readiness_ref: ArtifactRef | None = None
    source_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_by_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_claim_ids(self) -> ClaimLedger:
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("ClaimLedger claim_id values must be unique")
        if any(claim.run_id != self.run_id for claim in self.claims):
            raise ValueError("ClaimLedger claims must share the ledger run_id")
        assignment_ids = [assignment.assignment_id for assignment in self.family_assignments]
        if len(assignment_ids) != len(set(assignment_ids)):
            raise ValueError("ClaimLedger assignment_id values must be unique")
        if any(assignment.run_id != self.run_id for assignment in self.family_assignments):
            raise ValueError("ClaimLedger family assignments must share the ledger run_id")
        baseline_ids = [record.baseline_id for record in self.baseline_records]
        if len(baseline_ids) != len(set(baseline_ids)):
            raise ValueError("ClaimLedger baseline_id values must be unique")
        if any(record.run_id != self.run_id for record in self.baseline_records):
            raise ValueError("ClaimLedger baselines must share the ledger run_id")
        alternative_ids = [record.alternative_id for record in self.alternative_records]
        if len(alternative_ids) != len(set(alternative_ids)):
            raise ValueError("ClaimLedger alternative_id values must be unique")
        if any(record.run_id != self.run_id for record in self.alternative_records):
            raise ValueError("ClaimLedger alternatives must share the ledger run_id")
        known_claim_ids = set(claim_ids)
        for assignment in self.family_assignments:
            if assignment.claim_id not in known_claim_ids:
                raise ValueError(
                    f"ClaimLedger family assignment references unknown claim_id "
                    f"'{assignment.claim_id}'"
                )
        known_baseline_ids = set(baseline_ids)
        known_alternative_ids = set(alternative_ids)
        for claim in self.claims:
            missing_baselines = sorted(set(claim.baseline_refs) - known_baseline_ids)
            missing_alternatives = sorted(set(claim.alternative_refs) - known_alternative_ids)
            if missing_baselines:
                raise ValueError(
                    f"ClaimLedger claim '{claim.claim_id}' references unknown baseline_ids "
                    f"{missing_baselines}"
                )
            if missing_alternatives:
                raise ValueError(
                    f"ClaimLedger claim '{claim.claim_id}' references unknown alternative_ids "
                    f"{missing_alternatives}"
                )
        comparison_ids = [record.comparison_id for record in self.comparison_records]
        if len(comparison_ids) != len(set(comparison_ids)):
            raise ValueError("ClaimLedger comparison_id values must be unique")
        if any(record.run_id != self.run_id for record in self.comparison_records):
            raise ValueError("ClaimLedger comparison records must share the ledger run_id")
        known_comparison_ids = set(comparison_ids)
        for comparison in self.comparison_records:
            if comparison.claim_id not in known_claim_ids:
                raise ValueError(
                    f"ClaimLedger comparison record references unknown claim_id "
                    f"'{comparison.claim_id}'"
                )
            missing_baselines = sorted(set(comparison.baseline_refs) - known_baseline_ids)
            missing_alternatives = sorted(set(comparison.alternative_refs) - known_alternative_ids)
            if missing_baselines:
                raise ValueError(
                    f"ClaimLedger comparison '{comparison.comparison_id}' references "
                    f"unknown baseline_ids {missing_baselines}"
                )
            if missing_alternatives:
                raise ValueError(
                    f"ClaimLedger comparison '{comparison.comparison_id}' references "
                    f"unknown alternative_ids {missing_alternatives}"
                )
        for claim in self.claims:
            missing_comparisons = sorted(set(claim.comparison_refs) - known_comparison_ids)
            if missing_comparisons:
                raise ValueError(
                    f"ClaimLedger claim '{claim.claim_id}' references unknown comparison_ids "
                    f"{missing_comparisons}"
                )
        return self


class ClaimReadinessAssessment(BaseModel):
    """Machine-readable claim readiness decision used by validators and gates."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    support_status: ClaimSupportStatus
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    blocking_reasons: list[str] = Field(default_factory=list)
    review_required_reasons: list[str] = Field(default_factory=list)


class ClaimValidationResult(BaseModel):
    """Validation result for claim-spine publication gates."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    status: Literal["ok", "warning", "blocked", "legacy_missing", "disabled"]
    violations: list[str] = Field(default_factory=list)
    claim_ledger_status: Literal["present", "legacy_missing", "disabled"] = "present"
    workflow_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AlternativeRecord",
    "AlternativeRejectionReason",
    "AlternativeStatus",
    "BaselineComparisonRecord",
    "BaselineComparisonStatus",
    "BaselineRecord",
    "BaselineType",
    "ClaimFamily",
    "ClaimFamilyAssignment",
    "ClaimLedger",
    "ClaimPublishability",
    "ClaimReadinessAssessment",
    "ClaimRecord",
    "ClaimSourceClass",
    "ClaimSupportStatus",
    "ClaimType",
    "ClaimUse",
    "ClaimValidationResult",
    "ComparisonEvidenceRef",
    "ComparisonOptionKind",
    "ComparisonOptionRecord",
    "ComparisonOptionStatus",
    "ComparisonProducerFamily",
    "DominanceStatus",
    "DominatedFrontierRecord",
    "MethodNeedPrecondition",
    "RejectedOptionReasonRecord",
    "baseline_comparison_authority_boundary",
]
