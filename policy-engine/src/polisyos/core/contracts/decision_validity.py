"""Define persisted decision-validity lifecycle contracts.

These DTOs are written into CAS artifacts, control-plane responses, and
decision-validity event logs. `schema_version` and enum values are part of the
stable wire contract consumed by Runtime and Scientist services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DecisionValidityStatus(str, Enum):
    """Enumerate lifecycle states assigned to a decision packet evaluation."""

    ACTIVE = "active"
    WARNING = "warning"
    STALE = "stale"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class DecisionDependencyKind(str, Enum):
    """Classify the dependency keys watched by a decision-validity envelope."""

    NORM_PACK = "norm_pack"
    LEGAL_REPORT = "legal_report"
    NORM_REFERENCE = "norm_reference"
    DATA_SNAPSHOT = "data_snapshot"
    DATASET = "dataset"
    DATA_SCHEMA = "data_schema"
    QUALITY_REPORT = "quality_report"
    INPUT_BINDING_REPORT = "input_binding_report"
    KNOWLEDGE_BUNDLE = "knowledge_bundle"
    RESEARCH_INTENT = "research_intent"
    CAUSAL_EVIDENCE = "causal_evidence"
    ECONOMETRIC_EVIDENCE = "econometric_evidence"
    CONTEXT_PROFILE = "context_profile"
    TRANSPORTABILITY = "transportability"
    NORMATIVE_ARBITRATION = "normative_arbitration"


class DecisionTriggerType(str, Enum):
    """Identify the external or internal event that changed packet validity."""

    LAW_CHANGE = "law_change"
    DATASET_SUPERSEDED = "dataset_superseded"
    HISTORICAL_SEMANTIC_REVISION = "historical_semantic_revision"
    CONTRADICTING_EVIDENCE = "contradicting_evidence"
    CONTEXT_PROFILE_DRIFT = "context_profile_drift"
    POST_DEPLOYMENT_REFUTATION = "post_deployment_refutation"
    HUMAN_GATE = "human_gate"
    EXPERT_REVIEW = "expert_review"
    LEGACY_PACKET = "legacy_packet"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class DecisionDependencyRef(BaseModel):
    """Describe one dependency tracked by a decision-validity envelope."""

    model_config = ConfigDict(extra="forbid")

    kind: DecisionDependencyKind
    key: str
    artifact_id: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionBasisSection(BaseModel):
    """Group dependency refs and optional summary metadata for one basis domain."""

    model_config = ConfigDict(extra="forbid")

    dependencies: list[DecisionDependencyRef] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class DecisionTriggerSpec(BaseModel):
    """Declare one trigger and the dependency keys it should watch."""

    model_config = ConfigDict(extra="forbid")

    trigger_type: DecisionTriggerType
    dependency_keys: list[str] = Field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionTriggerRecord(BaseModel):
    """Record one evaluated trigger and its resulting packet status."""

    model_config = ConfigDict(extra="forbid")

    trigger_type: DecisionTriggerType
    status: DecisionValidityStatus
    reason: str
    dependency_key: str | None = None
    source_ref: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DecisionValidityEnvelope(BaseModel):
    """Persist the dependency surface and watched triggers for one decision packet."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    built_at: datetime = Field(default_factory=_utc_now)
    decision_lineage_key: str
    policy_fingerprint: str
    source_context_fingerprint: str | None = None
    target_context_fingerprint: str | None = None
    normative_basis: DecisionBasisSection = Field(default_factory=DecisionBasisSection)
    data_basis: DecisionBasisSection = Field(default_factory=DecisionBasisSection)
    knowledge_basis: DecisionBasisSection = Field(default_factory=DecisionBasisSection)
    transportability_basis: DecisionBasisSection = Field(default_factory=DecisionBasisSection)
    watched_triggers: list[DecisionTriggerSpec] = Field(default_factory=list)

    def dependency_keys(self) -> list[str]:
        """Return unique dependency keys in first-seen order across all basis sections."""
        keys: list[str] = []
        for section in (
            self.normative_basis,
            self.data_basis,
            self.knowledge_basis,
            self.transportability_basis,
        ):
            for dependency in section.dependencies:
                if dependency.key not in keys:
                    keys.append(dependency.key)
        return keys


class DecisionValidityEvaluation(BaseModel):
    """Store the current validity verdict, trigger evidence, and reissue hints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    decision_packet_ref: str | None = None
    decision_lineage_key: str
    status: DecisionValidityStatus
    evaluated_at: datetime = Field(default_factory=_utc_now)
    reasons: list[str] = Field(default_factory=list)
    triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    dependency_keys: list[str] = Field(default_factory=list)
    recommended_action: str = "none"
    review_required: bool = False
    supersedes_decision_ref: str | None = None
    superseded_by_ref: str | None = None


DecisionLifecycleJobState = Literal["pending", "completed", "cancelled"]
DecisionLifecycleJobKind = Literal["evaluation", "scheduled_monitoring"]


class DecisionDependencyEvent(BaseModel):
    """Represent one append-only dependency event emitted into the control-plane log."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    event_id: str
    dedupe_key: str
    occurred_at: datetime = Field(default_factory=_utc_now)
    recorded_at: datetime = Field(default_factory=_utc_now)
    trigger_type: DecisionTriggerType
    status: DecisionValidityStatus
    reason: str
    dependency_keys: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionValidityTransition(BaseModel):
    """Capture one status transition for a tracked decision packet."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    transition_id: str
    packet_ref: str
    decision_lineage_key: str
    previous_status: DecisionValidityStatus | None = None
    current_status: DecisionValidityStatus
    reason: str
    occurred_at: datetime = Field(default_factory=_utc_now)
    triggered_by_event_id: str | None = None
    evaluation_ref: str | None = None
    review_required: bool = False


class DecisionLifecycleJob(BaseModel):
    """Describe a scheduled or completed control-plane follow-up job."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    job_id: str
    job_kind: DecisionLifecycleJobKind
    packet_ref: str
    decision_lineage_key: str
    state: DecisionLifecycleJobState = "pending"
    reason: str
    scheduled_for: datetime = Field(default_factory=_utc_now)
    trigger_event_id: str | None = None
    monitoring_contract_ref: str | None = None
    completed_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "DecisionBasisSection",
    "DecisionDependencyEvent",
    "DecisionDependencyKind",
    "DecisionDependencyRef",
    "DecisionLifecycleJob",
    "DecisionLifecycleJobKind",
    "DecisionLifecycleJobState",
    "DecisionTriggerRecord",
    "DecisionTriggerSpec",
    "DecisionTriggerType",
    "DecisionValidityEnvelope",
    "DecisionValidityEvaluation",
    "DecisionValidityStatus",
    "DecisionValidityTransition",
]
