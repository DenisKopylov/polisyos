"""Typed contracts for the W6.C obligation graph compiler."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

OBLIGATION_GRAPH_SCHEMA_VERSION = "policyos.obligation_graph.v1"
OBLIGATION_GRAPH_CONTRACT_ID = "policy_design_case.obligation_graph.v1"


class SourceClass(StrEnum):
    """C38 source classes with authority ceilings."""

    GOVERNED_RULE = "governed_rule"
    LEGAL_REQUIREMENT = "legal_requirement"
    DETERMINISTIC_CRITIC = "deterministic_critic"
    PRODUCER_BLOCKER = "producer_blocker"
    HISTORICAL_FAILURE = "historical_failure"
    LLM_CANDIDATE = "llm_candidate"
    LLM_CRITIC_CONSENSUS = "llm_critic_consensus"
    HUMAN_REVIEWER = "human_reviewer"
    PUBLIC_CONTESTATION = "public_contestation"


class PriorityClass(StrEnum):
    """C38 local priority class for obligation promotion."""

    AUTHORITY_LEVEL_MANDATORY = "authority_level_mandatory"
    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"
    REVIEW_REQUIRED = "review_required"
    CANDIDATE = "candidate"
    OPTIONAL = "optional"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class DeferredState(StrEnum):
    """Visibility state for non-frontier bundles."""

    DEFERRED = "deferred"
    REJECTED = "rejected"


class FacetSnapshot(BaseModel):
    """Minimal W6.A facet snapshot consumed by W6.C.

    W6.C intentionally consumes facet snapshots rather than importing a W6.A
    runtime implementation. The parallel Wave 6 contract is field-level: facet
    identity, type, value, concept grounding, authority profile, scope, and
    temporal window.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    facet_id: str = Field(min_length=1)
    facet_type: str = Field(min_length=1)
    value: str = Field(min_length=1)
    concept_ref: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    authority_profile: str = Field(min_length=1)
    temporal_window: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "facet_id",
        "facet_type",
        "value",
        "concept_ref",
        "scope",
        "authority_profile",
        "temporal_window",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)


class GovernedObligationRule(BaseModel):
    """Governed W6.B rule snapshot consumed by the obligation compiler."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(min_length=1)
    rule_family: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    logic_hash: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    authority_level: str = Field(min_length=1)
    evidence_basis: str = Field(min_length=1)
    status: Literal["proposed", "governed", "deprecated", "withdrawn"] = "governed"
    public_revalidation_effect: str = Field(min_length=1)
    obligation_text: str = Field(min_length=1)
    authority_profile: str = Field(min_length=1)
    temporal_window: str = Field(min_length=1)
    remedy_path: str = Field(min_length=1)
    logic: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    required_facets: dict[str, str] = Field(default_factory=dict)
    priority_ceiling: PriorityClass = PriorityClass.MANDATORY
    authority_allowance_passed: bool = True
    admissibility_passed: bool = True
    current_run_relevance_passed: bool = True
    material_public_risk_passed: bool = True
    marginal_assurance_value: float = Field(default=1.0, ge=0.0)
    expected_cost: float = Field(default=0.0, ge=0.0)
    degradation_risk: float = Field(default=0.0, ge=0.0)
    reviewer_burden_minutes: float = Field(default=0.0, ge=0.0)
    complexity_cost: float = Field(default=1.0, ge=0.0)
    lineage_refs: tuple[str, ...] = Field(default=())
    deadline_at: datetime | None = None
    escalation_owner: str | None = None

    @field_validator(
        "rule_id",
        "rule_family",
        "rule_version",
        "logic_hash",
        "owner",
        "scope",
        "authority_level",
        "evidence_basis",
        "public_revalidation_effect",
        "obligation_text",
        "authority_profile",
        "temporal_window",
        "remedy_path",
        "escalation_owner",
        mode="before",
    )
    @classmethod
    def _strip_optional_or_required_text(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> str | None:
        if info.field_name == "escalation_owner":
            return _optional_text(value)
        return _required_text(value)

    @field_validator("required_facets", mode="before")
    @classmethod
    def _normalize_required_facets(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("required_facets must be a mapping")
        return {_required_text(key): _required_text(item) for key, item in value.items()}

    @field_validator("lineage_refs", mode="before")
    @classmethod
    def _normalize_lineage_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ObligationCandidateInput(BaseModel):
    """Raw source obligation candidate accepted into the unbounded ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    obligation_text: str = Field(min_length=1)
    source_class: SourceClass
    source_ref: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    authority_profile: str = Field(min_length=1)
    temporal_window: str = Field(min_length=1)
    remedy_path: str = Field(min_length=1)
    priority_hint: PriorityClass | None = None
    authority_allowance_passed: bool = False
    admissibility_passed: bool = False
    current_run_relevance_passed: bool = False
    material_public_risk_passed: bool = False
    marginal_assurance_value: float = Field(default=0.0, ge=0.0)
    expected_cost: float = Field(default=0.0, ge=0.0)
    degradation_risk: float = Field(default=0.0, ge=0.0)
    reviewer_burden_minutes: float = Field(default=0.0, ge=0.0)
    complexity_cost: float = Field(default=1.0, ge=0.0)
    lineage_refs: tuple[str, ...] = Field(default=())
    deadline_at: datetime | None = None
    escalation_owner: str | None = None
    competence_ref: str | None = None
    time_scope_ref: str | None = None
    claim_ref: str | None = None
    material: bool = False
    authority_envelope_ref: str | None = None
    producer_validation_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "candidate_id",
        "family",
        "obligation_text",
        "source_ref",
        "owner",
        "scope",
        "authority_profile",
        "temporal_window",
        "remedy_path",
        "escalation_owner",
        "competence_ref",
        "time_scope_ref",
        "claim_ref",
        "authority_envelope_ref",
        "producer_validation_ref",
        mode="before",
    )
    @classmethod
    def _strip_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        optional = {
            "escalation_owner",
            "competence_ref",
            "time_scope_ref",
            "claim_ref",
            "authority_envelope_ref",
            "producer_validation_ref",
        }
        if info.field_name in optional:
            return _optional_text(value)
        return _required_text(value)

    @field_validator("lineage_refs", mode="before")
    @classmethod
    def _normalize_lineage_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ComplexityBudget(BaseModel):
    """Governed W6.C frontier complexity budget."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_frontier_items: int = Field(default=25, ge=0)
    max_total_complexity_cost: float = Field(default=25.0, ge=0.0)
    max_reviewer_burden_minutes: float = Field(default=240.0, ge=0.0)
    budget_ref: str = Field(default="governed-config://obligation-frontier/default", min_length=1)
    owner: str = Field(default="team-runtime-quality", min_length=1)


class BundleKey(BaseModel):
    """Canonical bundle key bounding the obligation bundle ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    authority_profile: str = Field(min_length=1)
    temporal_window: str = Field(min_length=1)
    remedy_path: str = Field(min_length=1)


class CandidateLedgerEntry(BaseModel):
    """Append-only candidate ledger row with raw source classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ledger_entry_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    obligation_text: str = Field(min_length=1)
    source_class: SourceClass
    source_ref: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    authority_profile: str = Field(min_length=1)
    temporal_window: str = Field(min_length=1)
    remedy_path: str = Field(min_length=1)
    bundle_key: BundleKey
    priority_hint: PriorityClass | None = None
    source_ceiling: PriorityClass
    effective_priority: PriorityClass
    ceiling_reason: str = Field(min_length=1)
    promotion_blockers: tuple[str, ...] = Field(default=())
    authority_allowance_passed: bool
    admissibility_passed: bool
    current_run_relevance_passed: bool
    material_public_risk_passed: bool
    marginal_assurance_value: float = Field(ge=0.0)
    expected_cost: float = Field(ge=0.0)
    degradation_risk: float = Field(ge=0.0)
    reviewer_burden_minutes: float = Field(ge=0.0)
    complexity_cost: float = Field(ge=0.0)
    lineage_refs: tuple[str, ...] = Field(default=())
    deadline_at: datetime | None = None
    escalation_owner: str | None = None
    competence_ref: str | None = None
    time_scope_ref: str | None = None
    claim_ref: str | None = None
    material: bool = False
    authority_envelope_ref: str | None = None
    producer_validation_ref: str | None = None
    observed_at: datetime
    closeout_effect: Literal["candidate_ledger_only"] = "candidate_ledger_only"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeadlineBinding(BaseModel):
    """Deadline and escalation binding for a bundle or frontier item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner: str = Field(min_length=1)
    escalation_owner: str = Field(min_length=1)
    deadline_at: datetime | None = None
    source_refs: tuple[str, ...] = Field(default=())
    escalation: Literal["owner_triage_required"] = "owner_triage_required"


class ObligationBundle(BaseModel):
    """Canonicalized and deduplicated obligation bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str = Field(min_length=1)
    bundle_key: BundleKey
    active: bool = True
    canonical_obligation_text: str = Field(min_length=1)
    canonical_priority: PriorityClass
    child_count: int = Field(ge=1)
    candidate_refs: tuple[str, ...] = Field(default=())
    ledger_entry_refs: tuple[str, ...] = Field(default=())
    source_classes: tuple[SourceClass, ...] = Field(default=())
    source_ceiling_summary: dict[str, str] = Field(default_factory=dict)
    lineage_refs: tuple[str, ...] = Field(default=())
    dominated_candidate_refs: tuple[str, ...] = Field(default=())
    dominance_reason: str = Field(min_length=1)
    marginal_assurance_value: float = Field(ge=0.0)
    expected_cost: float = Field(ge=0.0)
    degradation_risk: float = Field(ge=0.0)
    reviewer_burden_minutes: float = Field(ge=0.0)
    complexity_cost: float = Field(ge=0.0)
    deadline_binding: DeadlineBinding
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def family(self) -> str:
        """Bundle family convenience accessor."""

        return self.bundle_key.family

    @property
    def scope(self) -> str:
        """Bundle scope convenience accessor."""

        return self.bundle_key.scope

    @property
    def authority_profile(self) -> str:
        """Bundle authority-profile convenience accessor."""

        return self.bundle_key.authority_profile

    @property
    def temporal_window(self) -> str:
        """Bundle temporal-window convenience accessor."""

        return self.bundle_key.temporal_window

    @property
    def remedy_path(self) -> str:
        """Bundle remedy-path convenience accessor."""

        return self.bundle_key.remedy_path


class FrontierItem(BaseModel):
    """One promoted bundle in the bounded blocking frontier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frontier_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    bundle_key: BundleKey
    priority_class: PriorityClass
    obligation_text: str = Field(min_length=1)
    source_classes: tuple[SourceClass, ...] = Field(default=())
    candidate_refs: tuple[str, ...] = Field(default=())
    marginal_assurance_value: float = Field(ge=0.0)
    expected_cost: float = Field(ge=0.0)
    degradation_risk: float = Field(ge=0.0)
    reviewer_burden_minutes: float = Field(ge=0.0)
    complexity_cost: float = Field(ge=0.0)
    deadline_binding: DeadlineBinding
    metadata: dict[str, Any] = Field(default_factory=dict)
    closeout_effect: Literal["blocks_or_caps_closeout"] = "blocks_or_caps_closeout"


class DeferredObligationRecord(BaseModel):
    """Visible record for a deferred or rejected non-frontier bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str = Field(min_length=1)
    bundle_key: BundleKey
    state: DeferredState
    reason: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    observed_at: datetime
    reopen_trigger: str = Field(min_length=1)
    candidate_refs: tuple[str, ...] = Field(default=())
    priority_class: PriorityClass


class ObligationGraph(BaseModel):
    """Compiled W6.C obligation graph with three-tier ledger and frontier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.obligation_graph.v1"] = OBLIGATION_GRAPH_SCHEMA_VERSION
    contract_id: Literal["policy_design_case.obligation_graph.v1"] = (
        OBLIGATION_GRAPH_CONTRACT_ID
    )
    graph_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    generated_at: datetime
    facets: tuple[FacetSnapshot, ...] = Field(default=())
    candidate_ledger: tuple[CandidateLedgerEntry, ...] = Field(default=())
    bundle_ledger: tuple[ObligationBundle, ...] = Field(default=())
    blocking_frontier: tuple[FrontierItem, ...] = Field(default=())
    deferred_or_rejected: tuple[DeferredObligationRecord, ...] = Field(default=())
    complexity_budget: ComplexityBudget
    telemetry: dict[str, Any] = Field(default_factory=dict)
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    authority_boundary: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    surface: Literal["obligation_graph.audit_surface"] = "obligation_graph.audit_surface"


def _required_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("value must not be empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_required_text(value),)
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("value must be a string or iterable of strings") from exc
    return tuple(dict.fromkeys(_required_text(item) for item in items))


__all__ = [
    "OBLIGATION_GRAPH_CONTRACT_ID",
    "OBLIGATION_GRAPH_SCHEMA_VERSION",
    "BundleKey",
    "CandidateLedgerEntry",
    "ComplexityBudget",
    "DeadlineBinding",
    "DeferredObligationRecord",
    "DeferredState",
    "FacetSnapshot",
    "FrontierItem",
    "GovernedObligationRule",
    "ObligationBundle",
    "ObligationCandidateInput",
    "ObligationGraph",
    "PriorityClass",
    "SourceClass",
]
