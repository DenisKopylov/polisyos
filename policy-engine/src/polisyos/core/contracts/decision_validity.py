"""Define persisted decision-validity lifecycle contracts.

These DTOs are written into CAS artifacts, control-plane responses, and
decision-validity event logs. `schema_version` and enum values are part of the
stable wire contract consumed by Runtime and Scientist services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

Digest = str


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DecisionValidityStatus(str, Enum):
    """Enumerate lifecycle states assigned to a decision packet evaluation."""

    ACTIVE = "active"
    WARNING = "warning"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    SUPERSEDED = "superseded"
    REISSUED = "reissued"
    WITHDRAWN = "withdrawn"
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
    SOURCE = "source"
    QUALITY_REPORT = "quality_report"
    INPUT_BINDING_REPORT = "input_binding_report"
    KNOWLEDGE_BUNDLE = "knowledge_bundle"
    RESEARCH_INTENT = "research_intent"
    CAUSAL_EVIDENCE = "causal_evidence"
    ECONOMETRIC_EVIDENCE = "econometric_evidence"
    CONTEXT_PROFILE = "context_profile"
    TRANSPORTABILITY = "transportability"
    NORMATIVE_ARBITRATION = "normative_arbitration"
    SEMANTIC_EPOCH = "semantic_epoch"


class DecisionTriggerType(str, Enum):
    """Identify the external or internal event that changed packet validity."""

    NORM_INVALIDATION = "norm_invalidation"
    DATA_INVALIDATION = "data_invalidation"
    SOURCE_INVALIDATION = "source_invalidation"
    METRIC_INVALIDATION = "metric_invalidation"
    MODEL_INVALIDATION = "model_invalidation"
    CONFLICT_INVALIDATION = "conflict_invalidation"
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


EpochValidityPredicateClass = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]


class EpochValidityBatchTarget(BaseModel):
    """One owner-indexed packet selected by a verified epoch transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    packet_ref: str = Field(min_length=1)
    decision_lineage_key: str = Field(min_length=1)
    dependency_key: str = Field(min_length=1)
    status: DecisionValidityStatus
    reason: str = Field(min_length=1)


class EpochTransitionVerificationReceipt(BaseModel):
    """Independently verified transition facts admitted by Decision Validity.

    The HTTP caller never supplies this object.  A container-appointed verifier
    resolves the transition artifact and freezes the complete owner denominator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_purpose: str = Field(min_length=1)
    verifier_provenance_ref: ArtifactRef
    dependency_keys: tuple[str, ...] = Field(min_length=1)
    dependency_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adjudication_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    targets: tuple[EpochValidityBatchTarget, ...] = Field(min_length=1)
    predicate_class: EpochValidityPredicateClass

    @model_validator(mode="after")
    def _targets_are_a_bijection(self) -> EpochTransitionVerificationReceipt:
        dependency_keys = tuple(dict.fromkeys(self.dependency_keys))
        target_keys = tuple((row.packet_ref, row.dependency_key) for row in self.targets)
        if dependency_keys != self.dependency_keys:
            raise ValueError("epoch_transition_dependency_denominator_duplicate")
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("epoch_transition_target_denominator_duplicate")
        if any(row.dependency_key not in dependency_keys for row in self.targets):
            raise ValueError("epoch_transition_target_dependency_unbound")
        return self


class EpochValidityPendingBatch(BaseModel):
    """Complete target denominator persisted before the first packet write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.decision-validity.epoch-pending-batch.v1"] = (
        "polisyos.decision-validity.epoch-pending-batch.v1"
    )
    batch_id: str = Field(min_length=1)
    state: Literal["pending"] = "pending"
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_provenance_ref: ArtifactRef
    dependency_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adjudication_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    targets: tuple[EpochValidityBatchTarget, ...] = Field(min_length=1)
    applied_packet_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _applied_refs_are_an_exact_prefix(self) -> EpochValidityPendingBatch:
        target_refs = tuple(dict.fromkeys(row.packet_ref for row in self.targets))
        if self.applied_packet_refs != target_refs[: len(self.applied_packet_refs)]:
            raise ValueError("epoch_pending_applied_refs_not_target_prefix")
        return self


class EpochValidityBatchCompletionStatement(BaseModel):
    """Non-self-referential durable completion fact for one frozen batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.decision-validity.epoch-batch-completion.v1"] = (
        "polisyos.decision-validity.epoch-batch-completion.v1"
    )
    batch_id: str = Field(min_length=1)
    state: Literal["completed"] = "completed"
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dependency_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adjudication_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_provenance_ref: ArtifactRef
    affected_packet_refs: tuple[str, ...] = Field(min_length=1)
    targets: tuple[EpochValidityBatchTarget, ...] = Field(min_length=1)
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _affected_packets_are_unique(self) -> EpochValidityBatchCompletionStatement:
        if len(self.affected_packet_refs) != len(set(self.affected_packet_refs)):
            raise ValueError("epoch_batch_completion_packet_duplicate")
        if self.affected_packet_refs != tuple(
            dict.fromkeys(target.packet_ref for target in self.targets)
        ):
            raise ValueError("epoch_batch_completion_target_denominator_mismatch")
        return self


class EpochValidityBatchReceipt(BaseModel):
    """Completed, replayable result of one owner-admitted epoch batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.decision-validity.epoch-batch-receipt.v1"] = (
        "polisyos.decision-validity.epoch-batch-receipt.v1"
    )
    batch_id: str = Field(min_length=1)
    state: Literal["completed"] = "completed"
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dependency_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adjudication_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_provenance_ref: ArtifactRef
    completion_receipt_ref: ArtifactRef
    affected_packet_refs: tuple[str, ...] = Field(min_length=1)
    targets: tuple[EpochValidityBatchTarget, ...] = Field(min_length=1)
    claim_bridge_result_refs: tuple[ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def _completed_denominators_are_unique(self) -> EpochValidityBatchReceipt:
        if len(self.affected_packet_refs) != len(set(self.affected_packet_refs)):
            raise ValueError("epoch_batch_receipt_packet_duplicate")
        if self.affected_packet_refs != tuple(
            dict.fromkeys(target.packet_ref for target in self.targets)
        ):
            raise ValueError("epoch_batch_receipt_target_denominator_mismatch")
        bridge_ids = tuple(str(row.artifact_id) for row in self.claim_bridge_result_refs)
        if len(bridge_ids) != len(set(bridge_ids)):
            raise ValueError("epoch_batch_receipt_claim_bridge_duplicate")
        return self


class PersistedEpochValidityBatchEvidence(BaseModel):
    """Read-only exact CAS evidence for one completed owner batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_receipt_ref: ArtifactRef
    batch_receipt_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_bytes: bytes
    receipt: EpochValidityBatchReceipt


class EpochValidityCompletedBatchEvidenceResolver(Protocol):
    """Owner reader for exact completed Decision Validity batch evidence."""

    def resolve_completed_epoch_batch_evidence(
        self,
        *,
        batch_receipt_ref: ArtifactRef,
    ) -> PersistedEpochValidityBatchEvidence:
        """Reload one admitted receipt and its independently checked completion."""
        ...


class EpochValidityCompletedBatchEvidenceDenominator(Protocol):
    """Canonical owner walk over every completed epoch-batch receipt."""

    def enumerate_completed_epoch_batch_evidence(
        self,
    ) -> tuple[PersistedEpochValidityBatchEvidence, ...]:
        """Return a complete, content-verified receipt denominator."""
        ...


class EpochTransitionVerifier(Protocol):
    """Resolve exact transition bytes under one appointed verifier identity."""

    def verify(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: Digest,
        expected_authority_purpose: str,
    ) -> EpochTransitionVerificationReceipt:
        """Return independently reconciled facts or fail closed."""
        ...


class PreN9EpochValiditySubjectStatement(BaseModel):
    """Owner-derived decision-validity selector persisted before N9."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_query_context_ref: ArtifactRef
    owner_query_context_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_packet_lineage_key_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_decision_packet_ref: ArtifactRef | None = None
    packet_epoch_refs: tuple[Digest, ...] = ()


class PersistedPreN9EpochValiditySubject(BaseModel):
    """Content-bound handle; parsed subject bytes never travel beside it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: ArtifactRef
    subject_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class EpochValidityGateReceipt(BaseModel):
    """Owner-reconciled epoch status for one persisted pre-N9 subject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["current", "batch_completed", "pending", "not_established"]
    subject_ref: ArtifactRef
    subject_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_decision_packet_ref: ArtifactRef | None = None
    packet_epoch_refs: tuple[Digest, ...] = ()
    current_epoch_head_refs: tuple[Digest, ...] = ()
    dependency_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adjudication_denominator_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prior_completed_binding_ref: ArtifactRef | None = None
    completed_batch_receipt_ref: ArtifactRef | None = None
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    failure_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _positive_status_has_owner_history(self) -> EpochValidityGateReceipt:
        if self.status in {"current", "batch_completed"} and self.failure_codes:
            raise ValueError("epoch_validity_positive_status_has_failure_codes")
        if self.status == "current":
            if self.prior_completed_binding_ref is None:
                raise ValueError("epoch_validity_current_requires_prior_completed_binding")
            if self.completed_batch_receipt_ref is not None:
                raise ValueError("epoch_validity_current_cannot_carry_completed_batch")
        if self.status == "batch_completed" and self.completed_batch_receipt_ref is None:
            raise ValueError("epoch_validity_batch_completed_requires_receipt")
        return self


class EpochValidityGateNonReceipt(BaseModel):
    """Typed fail-closed result when owner reconciliation cannot establish a gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["pending", "not_established", "rejected"]
    code: str = Field(min_length=1)
    subject_ref: ArtifactRef
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class PersistedEpochValidityGateEvidence(BaseModel):
    """Persisted positive gate handle paired to its exact subject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_evidence_ref: ArtifactRef
    gate_evidence_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    subject_ref: ArtifactRef
    subject_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class PreN9AdmittedCandidate(BaseModel):
    """Only handles crossing from owner reconciliation into the N9 batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    subject_ref: ArtifactRef
    subject_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    gate_evidence_ref: ArtifactRef
    gate_evidence_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class PersistedPreN9AdmittedCandidateBatch(BaseModel):
    """Sealed complete-candidate denominator accepted by the N9 port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_denominator_ref: ArtifactRef
    candidate_denominator_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ordered_admissions: tuple[PreN9AdmittedCandidate, ...] = Field(min_length=1)
    batch_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _admissions_are_a_complete_unique_order(self) -> PersistedPreN9AdmittedCandidateBatch:
        occurrence_refs = tuple(
            str(row.candidate_occurrence_ref.artifact_id) for row in self.ordered_admissions
        )
        subject_refs = tuple(str(row.subject_ref.artifact_id) for row in self.ordered_admissions)
        gate_refs = tuple(str(row.gate_evidence_ref.artifact_id) for row in self.ordered_admissions)
        if (
            len(occurrence_refs) != len(set(occurrence_refs))
            or len(subject_refs) != len(set(subject_refs))
            or len(gate_refs) != len(set(gate_refs))
        ):
            raise ValueError("epoch_validity_admission_bijection_mismatch")
        if any(
            row.aggregate_context_ref != self.aggregate_context_ref
            or row.aggregate_context_content_hash != self.aggregate_context_content_hash
            for row in self.ordered_admissions
        ):
            raise ValueError("epoch_validity_admission_aggregate_mismatch")
        return self


class EpochValidityN9Projection(BaseModel):
    """Independently reloaded DV evidence bound into canonical N9."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_query_context_ref: ArtifactRef
    owner_query_context_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    subject_ref: ArtifactRef
    subject_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    gate_receipt_ref: ArtifactRef
    gate_receipt_content_hash: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_query_context_ref: Digest = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_decision_packet_ref: ArtifactRef | None = None
    completed_batch_receipt_ref: ArtifactRef | None = None
    verifier_provenance_ref: ArtifactRef
    status: Literal["current", "batch_completed"]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _positive_status_binds_its_completion(self) -> EpochValidityN9Projection:
        if self.status == "batch_completed" and self.completed_batch_receipt_ref is None:
            raise ValueError("epoch_validity_projection_batch_receipt_missing")
        if self.status == "current" and self.completed_batch_receipt_ref is not None:
            raise ValueError("epoch_validity_projection_current_has_batch_receipt")
        return self


class EpochValidityPreN9SubjectAuthority(Protocol):
    def persist_for_n9(
        self, *, bound_member_ref: ArtifactRef
    ) -> PersistedPreN9EpochValiditySubject:
        """Derive and persist a subject from one owner-bound member handle."""
        ...


class EpochValidityAuthorityGate(Protocol):
    def reconcile_before_n9(
        self, *, subject_ref: ArtifactRef
    ) -> PersistedEpochValidityGateEvidence | EpochValidityGateNonReceipt:
        """Reload one subject and reconcile all owner facts."""
        ...


class EpochValidityN9EvidenceResolver(Protocol):
    def resolve_verified(
        self,
        *,
        admission: PreN9AdmittedCandidate,
        expected_design_problem_ref: ArtifactRef,
    ) -> EpochValidityN9Projection | EpochValidityGateNonReceipt:
        """Resolve persisted handles; never trust a DTO projection."""
        ...

    def resolve_projection_verified(
        self,
        *,
        projection: EpochValidityN9Projection,
        expected_problem_content_hash: Digest,
    ) -> EpochValidityN9Projection | EpochValidityGateNonReceipt:
        """Reload an offline projection against the bound design problem."""
        ...


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
    "EpochTransitionVerificationReceipt",
    "EpochTransitionVerifier",
    "EpochValidityAuthorityGate",
    "EpochValidityBatchCompletionStatement",
    "EpochValidityBatchReceipt",
    "EpochValidityBatchTarget",
    "EpochValidityCompletedBatchEvidenceResolver",
    "EpochValidityGateNonReceipt",
    "EpochValidityGateReceipt",
    "EpochValidityN9EvidenceResolver",
    "EpochValidityN9Projection",
    "EpochValidityPendingBatch",
    "EpochValidityPreN9SubjectAuthority",
    "PersistedEpochValidityBatchEvidence",
    "PersistedEpochValidityGateEvidence",
    "PersistedPreN9AdmittedCandidateBatch",
    "PersistedPreN9EpochValiditySubject",
    "PreN9AdmittedCandidate",
    "PreN9EpochValiditySubjectStatement",
]
