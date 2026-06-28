"""Layer 3 GY two-ring waist contracts for the workspace control loop."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from .layer2_readiness import (
    ID_PATTERN,
    AuthorityBoundary,
    CertifiedOperationEnvelope,
    DecisionGrade,
    EvidenceBasis,
    EvidenceKind,
    Layer2ReadinessModel,
)

GY_WAIST_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy_waist.v1"
GY_ARTIFACT_ID_PATTERN = r"^(?:[a-z][a-z0-9_.-]*|sha256:[0-9a-f]{64})$"

_VOLATILE_KEYS = {
    "ms",
    "seconds",
    "secs",
    "elapsed",
    "elapsed_s",
    "elapsed_ms",
    "vector_ms",
    "text_ms",
    "duration_ms",
    "duration_s",
    "took_ms",
    "timestamp",
    "generated_at",
    "started_at",
    "finished_at",
    "created_at",
    "wall_time",
    "wall_clock",
    "now",
    "run_at",
    "executed_at",
}
_VOLATILE_SUFFIX = re.compile(r".*(_ms|_secs?|_at|_ns|_us|_latency|_duration)$")
_VERIFIER_WRITERS = frozenset({"verifier", "governance", "a_side", "system_verifier"})
_DECISION_GRADE_RANK: dict[str | None, int] = {
    None: 0,
    "unsupported": 0,
    "descriptive_only": 1,
    "advisory_admissible": 2,
    "decision_admissible": 3,
}


def _is_volatile(key: str) -> bool:
    normalized = key.lower()
    return normalized in _VOLATILE_KEYS or bool(_VOLATILE_SUFFIX.fullmatch(normalized))


def strip_gy_volatile_fields(value: object) -> object:
    """Return ``value`` with volatile timing fields removed recursively."""

    if isinstance(value, dict):
        return {
            str(key): strip_gy_volatile_fields(item)
            for key, item in value.items()
            if not _is_volatile(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [strip_gy_volatile_fields(item) for item in value]
    return value


def gy_content_hash(value: object) -> str:
    """Return a GY evidence content hash over time-stripped canonical JSON."""

    payload = json.dumps(
        strip_gy_volatile_fields(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def assert_ring2_verifier_provenance(
    value: object,
    *,
    context: dict[str, Any] | None = None,
) -> None:
    """Fail closed if a Ring-2 field is consumed without verifier provenance.

    Pydantic ``model_construct`` and ``model_copy(update=...)`` deliberately skip
    validation. Authority-bearing consumers therefore call this boundary check on
    the object they are about to persist, promote, or surface-read. The check
    serializes models to plain JSON and re-validates them with the caller's
    writer context so constructed Ring-2 fields cannot be smuggled through a
    trusted in-memory instance.
    """

    writer_role = str((context or {}).get("writer_role") or "").strip()
    if isinstance(value, BaseModel):
        model_type = type(value)
        try:
            model_type.model_validate(value.model_dump(mode="json"), context=context)
        except Exception as exc:
            raise ValueError(f"Ring-2 verifier provenance rejected: {exc}") from exc
        attempted = _non_empty_ring2_fields(value)
        if attempted and writer_role not in _VERIFIER_WRITERS:
            raise ValueError(
                "Ring-2 verifier provenance rejected for "
                f"{model_type.__name__}: {', '.join(sorted(attempted))}"
            )
        for item in value.__dict__.values():
            assert_ring2_verifier_provenance(item, context=context)
        return
    if isinstance(value, dict):
        for item in value.values():
            assert_ring2_verifier_provenance(item, context=context)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            assert_ring2_verifier_provenance(item, context=context)


def _non_empty_ring2_fields(value: BaseModel) -> list[str]:
    ring2_fields = getattr(type(value), "ring2_fields", frozenset())
    attempted: list[str] = []
    for field in ring2_fields:
        item = getattr(value, field, None)
        if item not in (None, [], {}):
            attempted.append(str(field))
    return attempted


class GyWaistModel(BaseModel):
    """Strict frozen base model with field-level Ring-2 write checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ring2_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def _reject_untrusted_ring2_writes(cls, data: object, info: ValidationInfo) -> object:
        if not isinstance(data, dict) or not cls.ring2_fields:
            return data
        writer_role = str((info.context or {}).get("writer_role") or "").strip()
        if writer_role in _VERIFIER_WRITERS:
            return data
        attempted = [
            field
            for field in cls.ring2_fields
            if field in data and data[field] not in (None, [], {})
        ]
        if attempted:
            raise ValueError(
                "verifier-only Ring-2 field write rejected for "
                f"{cls.__name__}: {', '.join(sorted(attempted))}"
            )
        return data


class OperationClass(StrEnum):
    """Operation verbs available to the GY workspace loop."""

    DISCOVER = "DISCOVER"
    ACQUIRE = "ACQUIRE"
    BIND = "BIND"
    TRANSFORM = "TRANSFORM"
    ESTIMATE = "ESTIMATE"
    SIMULATE = "SIMULATE"
    TRANSPORT = "TRANSPORT"
    VERIFY = "VERIFY"
    REFINE = "REFINE"
    LOWER = "LOWER"
    DECOMPOSE = "DECOMPOSE"
    COMPOSE = "COMPOSE"
    ELICIT = "ELICIT"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"


class SearchTerminalKind(StrEnum):
    """Typed terminal states for anytime GY workspace exits."""

    A_SPEC_GAP = "a_spec_gap"
    TOOL_FAILURE = "tool_failure"
    COMPOSITION_INVALID = "composition_invalid"
    RECURSIVE_BLOCKED = "recursive_blocked"
    SEARCH_CEILING_REPAIR_REQUIRED = "search_ceiling_repair_required"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    ACQUISITION_REQUIRED = "acquisition_required"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FRONTIER_STABLE = "frontier_stable"
    GROUNDED_ADMISSIBLE = "grounded_admissible"
    GROUNDED_PARTIAL_ADMISSIBLE = "grounded_partial_admissible"
    GROUNDED_ABSTENTION = "grounded_abstention"


def _jsonish(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class _DictAccessModel(GyWaistModel):
    """Small adapter for legacy dict-style reads during typed-contract migration."""

    def __getitem__(self, key: str) -> object:
        return _jsonish(getattr(self, key))

    def get(self, key: str, default: object | None = None) -> object | None:
        if not hasattr(self, key):
            return default
        return _jsonish(getattr(self, key))


class SearchTerminalState(_DictAccessModel):
    """Typed terminal state selected by deterministic anytime-exit precedence."""

    kind: SearchTerminalKind
    reason: str = Field(..., min_length=1, max_length=800)
    blocking_obligations: list[str] = Field(default_factory=list)
    budget_kind: str | None = None
    costed_plan: dict[str, Any] | None = None
    data_need_spec: dict[str, Any] | None = None


class ArtifactRef(GyWaistModel):
    """Content-addressed reference for one immutable GY artifact."""

    artifact_id: str = Field(..., pattern=GY_ARTIFACT_ID_PATTERN)
    artifact_type: str = Field(..., min_length=1, max_length=80)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    schema_ref: str = Field(..., min_length=1, max_length=200)
    uri: str = Field(..., min_length=1, max_length=300)
    version: str = Field(..., min_length=1, max_length=80)

    @classmethod
    def from_payload(
        cls,
        *,
        artifact_id: str,
        artifact_type: str,
        payload: object,
        schema_ref: str,
        uri: str,
        version: str,
    ) -> ArtifactRef:
        """Build an artifact ref whose hash uses GY canonical evidence semantics."""

        return cls(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=gy_content_hash(payload),
            schema_ref=schema_ref,
            uri=uri,
            version=version,
        )


class ArtifactEnvelopeVerification(GyWaistModel):
    """Verification refs attached to an artifact envelope."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"latest_promotion_result"})

    latest_applicability_result: str | None = None
    latest_promotion_result: str | None = None


class ArtifactEnvelope(GyWaistModel):
    """Ring-1 artifact carrier with verifier-only Ring-2 authority fields."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset(
        {"authority_boundary", "certified_operation_envelope"}
    )

    ref: ArtifactRef
    payload_ref: str
    payload_schema_ref: str
    lifecycle_state: Literal["shadow", "verified", "promoted", "rejected", "superseded", "archived"]
    created_by: dict[str, str]
    producer_operation: dict[str, str]
    input_artifacts: list[ArtifactRef] = Field(default_factory=list)
    producer_roots: list[ArtifactRef] = Field(default_factory=list)
    certified_operation_envelope: CertifiedOperationEnvelope | None = None
    authority_boundary: AuthorityBoundary | None = None
    obligations: list[str] = Field(default_factory=list)
    verification: ArtifactEnvelopeVerification = Field(
        default_factory=ArtifactEnvelopeVerification
    )


class PortSpec(GyWaistModel):
    """Typed operation port; provided authority is verifier-only."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"provided_authority"})

    port_id: str = Field(..., pattern=ID_PATTERN)
    direction: Literal["consumes", "produces", "requires", "provides"]
    port_type: str = Field(..., min_length=1, max_length=80)
    claim_shape: dict[str, Any]
    multiplicity: dict[str, int]
    constraints: dict[str, Any] = Field(default_factory=dict)
    required_authority: dict[str, Any] | None = None
    provided_authority: AuthorityBoundary | None = None


class OperationContract(GyWaistModel):
    """Coarse operation contract discovered from engine registries."""

    operation_id: str = Field(..., pattern=ID_PATTERN)
    operation_version: str = Field(..., min_length=1, max_length=80)
    operation_class: OperationClass
    consumes: list[PortSpec]
    produces: list[PortSpec]
    formal_preconditions: list[dict[str, Any]] = Field(default_factory=list)
    allowed_internal_execution: list[
        Literal[
            "foundry_method",
            "foundry_method_chain",
            "llm_agent_plan",
            "tool_call",
            "human_request",
        ]
    ]
    implementation_refs: list[dict[str, str]]
    cost_model: dict[str, Any]
    authority_transform: dict[str, Any]
    failure_modes: list[str] = Field(default_factory=list)
    repair_options: list[OperationClass] = Field(default_factory=list)


class OperationInvocationRecord(GyWaistModel):
    """Replay-visible execution record for one operation invocation."""

    invocation_id: str = Field(..., pattern=ID_PATTERN)
    operation_id: str
    operation_version: str
    workspace_id: str
    cycle_index: int = Field(ge=0)
    selected_by: dict[str, str]
    selection_rationale_ref: str | None = None
    input_artifacts: list[ArtifactRef]
    parameters: dict[str, Any]
    internal_trace: dict[str, Any]
    tool_calls: list[str] = Field(default_factory=list)
    human_requests: list[str] = Field(default_factory=list)
    output_artifacts: list[ArtifactRef]
    applicability_result: str
    budget_delta: dict[str, Any]
    status: Literal["started", "completed", "failed", "repair_required", "cancelled"]


class ApplicabilityResult(GyWaistModel):
    """Deterministic formal-gate verdict for an operation."""

    result_id: str = Field(..., pattern=ID_PATTERN)
    invocation_id: str
    status: Literal["applicable", "not_applicable", "applicable_with_warnings", "repair_required"]
    checked_preconditions: list[dict[str, Any]]
    failed_preconditions: list[dict[str, Any]]
    type_errors: list[dict[str, Any]]
    repair_options: list[dict[str, Any]]


class BudgetVector(GyWaistModel):
    """Vector budget used by the GY loop."""

    compute: dict[str, Any] = Field(default_factory=dict)
    acquisition: dict[str, Any] = Field(default_factory=dict)
    expert_attention: dict[str, Any] = Field(default_factory=dict)
    calendar: dict[str, Any] = Field(default_factory=dict)
    novelty: dict[str, Any] = Field(default_factory=dict)
    recursion: dict[str, Any] = Field(default_factory=dict)
    search_quality: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def slice0(cls) -> BudgetVector:
        """Return the minimal Slice-0 budget vector allowed by the GY plan."""

        return cls(
            compute={
                "max_operation_invocations": 3,
                "max_wall_seconds": 30,
                "hard": True,
            },
            search_quality={
                "min_recall_at_known_seeds": 1.0,
                "required_source_classes": ["official"],
            },
        )


class WorkspaceContract(GyWaistModel):
    """Blackboard workspace contract for one GY loop run."""

    workspace_id: str = Field(..., pattern=ID_PATTERN)
    parent_workspace_id: str | None = None
    intent_ref: ArtifactRef
    scope: dict[str, Any]
    artifact_graph_ref: str
    constraint_store_ref: str
    agenda_ref: str
    frontier_ref: str
    allowed_operations: list[str]
    budget: BudgetVector
    recursion_policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_depth": 0,
            "max_child_workspaces": 0,
            "decompose_allowed": False,
        }
    )
    exit_requirements: dict[str, bool] = Field(
        default_factory=lambda: {
            "require_search_exit_contract": True,
            "require_incompleteness_record": True,
            "require_authority_boundaries_for_promotion": True,
        }
    )


class SearchLedgerEvent(GyWaistModel):
    """W3C-PROV-shaped event in the GY search ledger."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"authority_delta"})

    event_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    event_type: str
    actor: dict[str, str]
    input_artifacts: list[ArtifactRef]
    output_artifacts: list[ArtifactRef]
    operation_invocation_ref: str | None = None
    decision_record_ref: str | None = None
    budget_delta: dict[str, Any] | None = None
    authority_delta: dict[str, Any] | None = None
    created_obligations: list[str]
    timestamp: str


class AuthorityDerivationTrace(Layer2ReadinessModel):
    """Trace proving verifier authority is derived, not copied from operation hints."""

    operation_invocation_id: str = Field(..., pattern=ID_PATTERN)
    output_artifact_ref: ArtifactRef
    declared_authority_transform: dict[str, Any]
    computed_evidence_kind: EvidenceKind
    computed_decision_grade: DecisionGrade
    producer_root_classes: list[str]
    method_classification: str
    applicability_result_ref: str
    calibration_refs: list[str] = Field(default_factory=list)
    counterexamples_closed: list[str] = Field(default_factory=list)
    certified_envelope_ref: str | None = None
    unresolved_blockers: list[str] = Field(default_factory=list)
    resulting_authority_boundary_ref: str
    transform_mismatch_disposition: Literal["matched", "downgraded", "rejected", "upgraded"]

    @model_validator(mode="after")
    def _reject_self_promotion(self) -> AuthorityDerivationTrace:
        requested_kind = self.declared_authority_transform.get("requested_evidence_kind")
        requested_grade = self.declared_authority_transform.get("requested_decision_grade")
        if self.transform_mismatch_disposition not in {"matched", "downgraded", "rejected"}:
            raise ValueError("authority_transform hints cannot self-promote")
        kind_self_promotes = (
            isinstance(requested_kind, str)
            and not _computed_evidence_covers_request(
                computed=self.computed_evidence_kind,
                requested=requested_kind,
            )
        )
        grade_self_promotes = (
            isinstance(requested_grade, str)
            and _DECISION_GRADE_RANK.get(requested_grade, 0)
            > _DECISION_GRADE_RANK.get(self.computed_decision_grade, 0)
        )
        if self.transform_mismatch_disposition == "matched" and (
            kind_self_promotes or grade_self_promotes
        ):
            raise ValueError("authority_transform hints cannot self-promote")
        if (
            requested_grade == "decision_admissible"
            and self.computed_decision_grade == "decision_admissible"
            and self.unresolved_blockers
        ):
            raise ValueError("authority_transform hints cannot self-promote past blockers")
        return self


class FrontierSnapshot(GyWaistModel):
    """Anytime snapshot of promoted, shadow, and rejected frontier artifacts."""

    snapshot_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    promoted_candidates: list[ArtifactRef] = Field(default_factory=list)
    shadow_candidates: list[ArtifactRef] = Field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = Field(default_factory=list)
    dominated_candidates: list[dict[str, Any]] = Field(default_factory=list)
    current_best: list[ArtifactRef] = Field(default_factory=list)
    frontier_metrics: dict[str, Any] = Field(default_factory=dict)


class SearchCoverageRecord(_DictAccessModel):
    """What the Slice/search process did and did not cover."""

    operations_attempted: list[str] = Field(default_factory=list)
    operations_not_attempted: list[dict[str, Any]] = Field(default_factory=list)
    methods_attempted: list[str] = Field(default_factory=list)
    source_classes_checked: list[str] = Field(default_factory=list)
    source_classes_missing: list[dict[str, Any]] = Field(default_factory=list)
    jurisdictions_checked: list[str] = Field(default_factory=list)
    time_horizons_checked: list[str] = Field(default_factory=list)


class SearchQualityRecord(_DictAccessModel):
    """Search-quality facts that separate domain limits from search failure."""

    recall_at_known_seeds: float = Field(ge=0, le=1)
    known_seeds_missed: list[str] = Field(default_factory=list)
    freshness_ok: bool
    stale_source_classes: list[str] = Field(default_factory=list)
    semantic_benchmark_run: dict[str, Any] | None = None


class SearchUnresolvedRecord(_DictAccessModel):
    """Outstanding blockers exposed by an anytime exit."""

    counterexamples: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[dict[str, Any]] = Field(default_factory=list)
    unmet_required_ports: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_couplings: list[dict[str, Any]] = Field(default_factory=list)
    human_questions: list[dict[str, Any]] = Field(default_factory=list)


class SearchBudgetRecord(_DictAccessModel):
    """Budget ledger slice attached to SearchIncompletenessRecord."""

    consumed: dict[str, Any]
    remaining: dict[str, Any]
    exhausted: list[str] = Field(default_factory=list)


class SearchNextBestAction(_DictAccessModel):
    """Typed next action candidate used by VOI and acquisition terminals."""

    operation_proposal_ref: str
    estimated_voi: float = Field(ge=0)
    estimated_cost: Any
    reason_not_taken: str
    data_need_spec: dict[str, Any] | None = None
    costed_plan: dict[str, Any] | None = None


class SearchIncompletenessRecord(GyWaistModel):
    """Honesty artifact explaining what search did and did not cover."""

    record_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    coverage: SearchCoverageRecord
    search_quality: SearchQualityRecord
    unresolved: SearchUnresolvedRecord
    budget: SearchBudgetRecord
    next_best_actions: list[SearchNextBestAction]
    ceiling_classification: Literal["domain_ceiling", "search_ceiling", "mixed", "unknown"]


class VOISelectionAudit(GyWaistModel):
    """Auditable value-of-information selection for anytime continuation or exit."""

    audit_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    selected_terminal: SearchTerminalKind
    candidates: list[dict[str, Any]]
    selected_action_ref: str | None = None
    continuation_allowed: bool
    decision_rule_ref: str
    threshold: float | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)
    candidate_actions: list[dict[str, Any]] = Field(default_factory=list)
    agent_suggested_scores: dict[str, Any] = Field(default_factory=dict)
    normalized_scores: dict[str, Any] = Field(default_factory=dict)
    deterministic_voi_inputs: dict[str, Any] = Field(default_factory=dict)
    rejected_or_clipped_inputs: list[dict[str, Any]] = Field(default_factory=list)
    selected_action: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    authority_gain_basis: dict[str, Any] = Field(default_factory=dict)
    decision_value_basis: dict[str, Any] = Field(default_factory=dict)
    cost_basis: dict[str, Any] = Field(default_factory=dict)
    bias_probe_result: dict[str, Any] = Field(default_factory=dict)


class SearchBlockerRecord(GyWaistModel):
    """Typed REFINE/search blocker with replayable frontier and repair context."""

    blocker_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    operation_class: OperationClass
    blocked_port: str = Field(..., min_length=1, max_length=200)
    missing_input: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=1, max_length=800)
    frontier_snapshot_ref: str | None = None
    applicability_result_ref: str | None = None
    repair_options: list[dict[str, Any]] = Field(default_factory=list)
    producer_missing_label: Literal[
        "producer_missing",
        "bridge_missing",
        "artifact_missing",
        "verification_missing",
        "semantic_test_missing",
    ] | None = None
    severity: Literal["repair_required", "blocks_authority", "blocks_execution"] = (
        "repair_required"
    )


class AgentDecisionRecord(GyWaistModel):
    """Ring-1 agent event; agents propose candidates and never write authority."""

    decision_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    invocation_id: str
    role: Literal["pi", "drafter", "critic", "tool_loop"]
    observed_refs: list[ArtifactRef] = Field(default_factory=list)
    candidate_operations: list[OperationClass] = Field(default_factory=list)
    selected_proposal_ref: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    candidate_only: bool = True
    status: Literal["completed", "repair_required", "blocked", "failed"]
    rationale: str = Field(..., min_length=1, max_length=1200)
    model_ref: str | None = None
    input_context_refs: list[str] = Field(default_factory=list)
    produced_candidate_refs: list[ArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_candidate_firewall(self) -> AgentDecisionRecord:
        if self.candidate_only is not True:
            raise ValueError("AgentDecisionRecord is candidate-only; agents cannot write authority")
        return self


class MethodPlan(GyWaistModel):
    """Ring-1 method proposal assembled by an agent or adapter trajectory."""

    plan_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    proposed_by_ref: str
    operation_classes: list[OperationClass]
    method_refs: list[str] = Field(default_factory=list)
    consumes: list[dict[str, Any]] = Field(default_factory=list)
    produces: list[dict[str, Any]] = Field(default_factory=list)
    authority_transform: dict[str, Any]
    admission_state: Literal["candidate_only", "shadow", "rejected"] = "candidate_only"


class MethodOutputConsumptionRecord(GyWaistModel):
    """Proof that ESTIMATE/SIMULATE consumed real Foundry method outputs."""

    consumption_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    operation_invocation_id: str
    operation_class: OperationClass
    consumed_method_output_refs: list[ArtifactRef] = Field(default_factory=list)
    consumed_method_evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    dag_consumed_method_outputs_count: int = Field(ge=0)
    measurement_root_refs: list[ArtifactRef] = Field(default_factory=list)
    constraint_store_ref: str | None = None

    @model_validator(mode="after")
    def _require_consumed_outputs(self) -> MethodOutputConsumptionRecord:
        if (
            self.dag_consumed_method_outputs_count < 1
            or not self.consumed_method_output_refs
            or not self.consumed_method_evidence_refs
        ):
            raise ValueError(
                "MethodOutputConsumptionRecord requires at least one consumed method output"
            )
        if self.dag_consumed_method_outputs_count != len(self.consumed_method_output_refs):
            raise ValueError("dag_consumed_method_outputs_count must match consumed outputs")
        return self


class SearchExitContract(GyWaistModel):
    """Typed terminal contract for every GY workspace run."""

    exit_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    terminal_state: SearchTerminalState
    frontier_snapshot: FrontierSnapshot
    incompleteness_record: SearchIncompletenessRecord
    budget_ledger: dict[str, Any]
    output_artifacts: list[ArtifactRef]
    authority_boundary: AuthorityBoundary | None = None
    next_best_actions: list[SearchNextBestAction] = Field(default_factory=list)
    evidence_kind: EvidenceKind | None = None
    decision_grade: DecisionGrade = "unsupported"
    evidence_ladder_rung: EvidenceKind | Literal["none"] = "none"

    @model_validator(mode="before")
    @classmethod
    def _derive_outcome_authority_projection(cls, value: object) -> object:
        """Derive the outcome authority axes from the verifier-written boundary."""

        if not isinstance(value, dict):
            return value
        payload = dict(value)
        boundary = payload.get("authority_boundary")
        if isinstance(boundary, AuthorityBoundary):
            evidence_kind = boundary.evidence_kind
            decision_grade = boundary.decision_grade or "unsupported"
        elif isinstance(boundary, dict):
            evidence_kind = boundary.get("evidence_kind")
            decision_grade = boundary.get("decision_grade") or "unsupported"
        else:
            evidence_kind = None
            decision_grade = "unsupported"
        derived = {
            "evidence_kind": evidence_kind,
            "decision_grade": decision_grade,
            "evidence_ladder_rung": evidence_kind or "none",
        }
        for field, expected in derived.items():
            if field in payload and payload[field] != expected:
                raise ValueError(
                    f"{field} must be derived from authority_boundary; "
                    f"expected {expected!r}"
                )
            payload[field] = expected
        return payload


class ObligationRecord(GyWaistModel):
    """Open obligation raised by verifier, search, or composition."""

    obligation_id: str = Field(..., pattern=ID_PATTERN)
    obligation_type: str
    raised_by: dict[str, Any]
    blocks: list[dict[str, Any]]
    description: str
    severity: Literal[
        "informational",
        "blocks_promotion",
        "blocks_composition",
        "blocks_decision",
    ]
    resolution_options: list[dict[str, Any]]
    status: Literal["open", "resolved", "escalated", "accepted_as_limit"]


class CouplingDeclaration(_DictAccessModel):
    """Child-declared coupling hypothesis; the graph classifier remains authoritative."""

    from_port: str = Field(..., min_length=1, max_length=200)
    to_port: str = Field(..., min_length=1, max_length=200)
    coupling_kind: Literal[
        "independent",
        "sequential",
        "shared_resource",
        "feedback",
        "mutually_exclusive",
        "unknown",
    ]
    rationale_ref: str = Field(..., min_length=1, max_length=300)


class SubDesignContract(GyWaistModel):
    """Assume-guarantee export from a child Workspace to its parent.

    Authority is carried only by ``PortSpec.provided_authority`` on provided
    ports. Parent workspaces may audit ``internal_trace_ref`` but cannot use it
    as an authority shortcut.
    """

    subdesign_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str = Field(..., min_length=1, max_length=120)
    parent_workspace_id: str | None = Field(default=None, max_length=120)
    scope: dict[str, Any]
    provides: list[PortSpec] = Field(default_factory=list)
    requires: list[PortSpec] = Field(default_factory=list)
    coupling_declarations: list[CouplingDeclaration] = Field(default_factory=list)
    producer_roots: list[ArtifactRef] = Field(default_factory=list)
    search_exit: SearchExitContract
    unresolved_obligations: list[ObligationRecord] = Field(default_factory=list)
    internal_trace_ref: str = Field(..., min_length=1, max_length=300)

    @model_validator(mode="after")
    def _authority_lives_on_ports(self) -> SubDesignContract:
        if self.search_exit.authority_boundary is not None and any(
            port.provided_authority is not None for port in self.provides
        ):
            return self
        if self.search_exit.authority_boundary is not None and not any(
            port.provided_authority is not None for port in self.provides
        ):
            raise ValueError("SubDesignContract authority must be exported on ports")
        return self


class CompositionGateResult(_DictAccessModel):
    """Stage-1 coupling-gate result bridged from the S5 composition owner."""

    verdict: Literal[
        "valid",
        "requires_joint_workspace",
        "requires_capacity_aggregation",
        "requires_system_dynamics",
        "invalid",
    ]
    blocking_edges: list[str] = Field(default_factory=list)
    invalid_reason: str | None = None
    coupling_classification_ref: str | None = None
    decomposition_ref: str | None = None
    composition_receipt_ref: str | None = None
    system_dynamics_requirement_ref: str | None = None


class AuthorityFlowResult(_DictAccessModel):
    """Stage-2 per-port authority-flow result."""

    from_port: str = Field(..., min_length=1, max_length=200)
    to_port: str = Field(..., min_length=1, max_length=200)
    resulting_authority: AuthorityBoundary
    rationale_ref: str = Field(..., min_length=1, max_length=300)
    coupling_kind: str = Field(..., min_length=1, max_length=80)


class EmergentClaimGroundingResult(_DictAccessModel):
    """Stage-3 grounding result for a program-level claim."""

    claim_ref: str = Field(..., min_length=1, max_length=300)
    grounding_status: Literal["grounded", "simulation_only", "missing", "invalid", "unresolved"]
    required_grounding: list[
        Literal[
            "capacity_aggregation",
            "sequencing_consistency",
            "system_dynamics",
            "equilibrium_check",
            "cross_chapter_counterexample_search",
        ]
    ] = Field(default_factory=list)
    resulting_authority: AuthorityBoundary | None = None
    grounding_refs: list[str] = Field(default_factory=list)
    raw_evidence_line_count: int | None = Field(default=None, ge=0)
    effective_independent_evidence_count: int | None = Field(default=None, ge=0)
    limiting_deficits: list[str] = Field(default_factory=list)


class CompositionCertificate(GyWaistModel):
    """Loop-facing certificate produced by the S5 composition engine bridge."""

    certificate_id: str = Field(..., pattern=ID_PATTERN)
    parent_workspace_id: str = Field(..., min_length=1, max_length=120)
    input_subdesigns: list[str] = Field(default_factory=list)
    target_policy_program_ref: str | None = Field(default=None, max_length=300)
    candidate_ref: str | None = Field(default=None, max_length=300)
    claim_refs: list[str] = Field(default_factory=list, max_length=80)
    coupling_gate: CompositionGateResult
    authority_flow: list[AuthorityFlowResult] = Field(default_factory=list)
    emergent_claims: list[EmergentClaimGroundingResult] = Field(default_factory=list)
    unresolved_obligations: list[ObligationRecord] = Field(default_factory=list)
    verdict: Literal["composable", "composable_with_limits", "not_composable"]
    composition_receipt_ref: str | None = None
    composition_law_check_ref: str | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    schema_version: str = GY_WAIST_SCHEMA_VERSION

    @model_validator(mode="after")
    def _require_receipt_for_composable_verdict(self) -> CompositionCertificate:
        if self.verdict != "not_composable" and not self.composition_receipt_ref:
            raise ValueError("composable CompositionCertificate requires CompositionReceipt bridge")
        return self


__all__ = [
    "GY_ARTIFACT_ID_PATTERN",
    "GY_WAIST_SCHEMA_VERSION",
    "AgentDecisionRecord",
    "ApplicabilityResult",
    "ArtifactEnvelope",
    "ArtifactRef",
    "AuthorityDerivationTrace",
    "AuthorityFlowResult",
    "BudgetVector",
    "CompositionCertificate",
    "CompositionGateResult",
    "CouplingDeclaration",
    "DecisionGrade",
    "EmergentClaimGroundingResult",
    "EvidenceBasis",
    "EvidenceKind",
    "FrontierSnapshot",
    "MethodOutputConsumptionRecord",
    "MethodPlan",
    "ObligationRecord",
    "OperationClass",
    "OperationContract",
    "OperationInvocationRecord",
    "PortSpec",
    "SearchBlockerRecord",
    "SearchBudgetRecord",
    "SearchCoverageRecord",
    "SearchExitContract",
    "SearchIncompletenessRecord",
    "SearchLedgerEvent",
    "SearchNextBestAction",
    "SearchQualityRecord",
    "SearchTerminalKind",
    "SearchTerminalState",
    "SearchUnresolvedRecord",
    "SubDesignContract",
    "VOISelectionAudit",
    "WorkspaceContract",
    "assert_ring2_verifier_provenance",
    "gy_content_hash",
    "strip_gy_volatile_fields",
]


def _computed_evidence_covers_request(*, computed: str, requested: str) -> bool:
    if computed == requested:
        return True
    if requested == "elicitation":
        return computed != "incomparable_meet"
    if computed == "measurement":
        return requested in {
            "derivation",
            "proxy",
            "transport",
            "bounds",
            "simulation",
            "elicitation",
        }
    if computed == "derivation":
        return requested in {"proxy", "transport", "bounds", "simulation", "elicitation"}
    return False
