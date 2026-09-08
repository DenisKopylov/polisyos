"""Define persisted decision-validity lifecycle contracts.

These DTOs are written into CAS artifacts, control-plane responses, and
decision-validity event logs. `schema_version` and enum values are part of the
stable wire contract consumed by Runtime and Scientist services.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

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

_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_EPOCH_IMPACT_SNAPSHOT_SCHEMA = "polisyos.decision-validity.epoch-impact-snapshot.v1"
_EPOCH_RECONCILIATION_SCHEMA = "polisyos.epoch-transition-denominator-reconciliation.v1"
_EPOCH_RECONCILIATION_BINDING_SCHEMA = (
    "polisyos.decision-validity.epoch-reconciliation-admission-binding.v1"
)
_EPOCH_AUTHORITY_PURPOSE = "decision_validity_epoch_transition"
_CANONICALIZATION_PROFILE = "polisyos.canon.json/0.2.0"
_SNAPSHOT_KIND = "scientist.decision_validity_epoch_impact_snapshot"
_SNAPSHOT_MEDIA_TYPE = "application/json"
_RECONCILIATION_KIND = "polisyos.epoch.transition_denominator_reconciliation_receipt"
_RECONCILIATION_MEDIA_TYPE = "application/vnd.polisyos.chronology+json"
_CANON_SPEC = CanonSpec()


def _semantic_hash(domain: str, payload: object) -> Digest:
    raw = to_canonical_bytes(payload, _CANON_SPEC)
    return "sha256:" + hashlib.sha256(domain.encode("utf-8") + b"\0" + raw).hexdigest()


def _raw_sha256(payload: bytes) -> Digest:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _artifact_ref_key(ref: ArtifactRef) -> tuple[str, str, str]:
    return (str(ref.artifact_id), ref.kind, ref.media_type)


class DecisionValidityEpochImpactOwnerRow(BaseModel):
    """Freeze one semantic-epoch dependency row from the Scientist owner index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependency_key: str = Field(min_length=1)
    dependency_kind: Literal[DecisionDependencyKind.SEMANTIC_EPOCH]
    artifact_id: Digest = Field(pattern=_DIGEST_PATTERN)
    packet_refs: tuple[str, ...]
    lineage_keys: tuple[str, ...]

    @model_validator(mode="after")
    def _members_are_canonical(self) -> DecisionValidityEpochImpactOwnerRow:
        if self.packet_refs != tuple(sorted(set(self.packet_refs))):
            raise ValueError("epoch_impact_snapshot_packet_refs_noncanonical")
        if self.lineage_keys != tuple(sorted(set(self.lineage_keys))):
            raise ValueError("epoch_impact_snapshot_lineage_keys_noncanonical")
        if any(not value for value in (*self.packet_refs, *self.lineage_keys)):
            raise ValueError("epoch_impact_snapshot_member_empty")
        return self


class DecisionValidityEpochImpactTarget(BaseModel):
    """Bind one affected packet and lineage to its semantic-epoch key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    packet_ref: str = Field(min_length=1)
    dependency_key: str = Field(min_length=1)
    decision_lineage_key: str = Field(min_length=1)


def _impact_denominator_ref(
    owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...],
) -> Digest:
    rows = [row.model_dump(mode="json") for row in owner_rows]
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _raw_sha256(raw)


def _owner_projection_generation_ref(
    *,
    requested_dependency_keys: tuple[str, ...],
    owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...],
    targets: tuple[DecisionValidityEpochImpactTarget, ...],
) -> Digest:
    return _semantic_hash(
        "polisyos.decision-validity.epoch-impact-owner-projection.v1",
        {
            "requested_dependency_keys": requested_dependency_keys,
            "owner_rows": owner_rows,
            "targets": targets,
        },
    )


class DecisionValidityEpochImpactSnapshot(BaseModel):
    """Persist the exact Scientist owner projection used by epoch intake."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[_EPOCH_IMPACT_SNAPSHOT_SCHEMA] = _EPOCH_IMPACT_SNAPSHOT_SCHEMA
    authority_purpose: Literal[_EPOCH_AUTHORITY_PURPOSE] = _EPOCH_AUTHORITY_PURPOSE
    requested_query_context_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    requested_dependency_keys: tuple[str, ...]
    owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...]
    targets: tuple[DecisionValidityEpochImpactTarget, ...]
    decision_impact_denominator_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    owner_projection_generation_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    snapshot_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)

    @classmethod
    def build(
        cls,
        *,
        requested_query_context_ref: Digest,
        requested_dependency_keys: tuple[str, ...],
        owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...],
        targets: tuple[DecisionValidityEpochImpactTarget, ...],
    ) -> DecisionValidityEpochImpactSnapshot:
        """Build a self-bound snapshot from one already enumerated owner projection."""

        values: dict[str, object] = {
            "schema_version": _EPOCH_IMPACT_SNAPSHOT_SCHEMA,
            "authority_purpose": _EPOCH_AUTHORITY_PURPOSE,
            "requested_query_context_ref": requested_query_context_ref,
            "requested_dependency_keys": requested_dependency_keys,
            "owner_rows": owner_rows,
            "targets": targets,
            "decision_impact_denominator_ref": _impact_denominator_ref(owner_rows),
            "owner_projection_generation_ref": _owner_projection_generation_ref(
                requested_dependency_keys=requested_dependency_keys,
                owner_rows=owner_rows,
                targets=targets,
            ),
        }
        return cls(
            **values,
            snapshot_content_hash=_semantic_hash(
                "polisyos.decision-validity.epoch-impact-snapshot.v1", values
            ),
        )

    @model_validator(mode="after")
    def _projection_is_exact_and_self_bound(self) -> DecisionValidityEpochImpactSnapshot:
        if self.requested_dependency_keys != tuple(sorted(set(self.requested_dependency_keys))):
            raise ValueError("epoch_impact_snapshot_requested_keys_noncanonical")
        if not self.requested_dependency_keys:
            raise ValueError("epoch_impact_snapshot_requested_keys_empty")
        if self.owner_rows != tuple(sorted(self.owner_rows, key=lambda row: row.dependency_key)):
            raise ValueError("epoch_impact_snapshot_owner_rows_noncanonical")
        row_keys = tuple(row.dependency_key for row in self.owner_rows)
        if len(row_keys) != len(set(row_keys)) or row_keys != self.requested_dependency_keys:
            raise ValueError("epoch_impact_snapshot_owner_rows_mismatch")
        ordered_targets = tuple(
            sorted(
                self.targets,
                key=lambda row: (row.dependency_key, row.packet_ref, row.decision_lineage_key),
            )
        )
        target_keys = tuple((row.dependency_key, row.packet_ref) for row in self.targets)
        if self.targets != ordered_targets or len(target_keys) != len(set(target_keys)):
            raise ValueError("epoch_impact_snapshot_targets_noncanonical")
        if any(row.dependency_key not in self.requested_dependency_keys for row in self.targets):
            raise ValueError("epoch_impact_snapshot_target_key_unbound")
        for owner in self.owner_rows:
            owner_targets = tuple(
                row for row in self.targets if row.dependency_key == owner.dependency_key
            )
            if tuple(row.packet_ref for row in owner_targets) != owner.packet_refs:
                raise ValueError("epoch_impact_snapshot_packet_membership_mismatch")
            if (
                tuple(sorted({row.decision_lineage_key for row in owner_targets}))
                != owner.lineage_keys
            ):
                raise ValueError("epoch_impact_snapshot_lineage_membership_mismatch")
        if self.decision_impact_denominator_ref != _impact_denominator_ref(self.owner_rows):
            raise ValueError("epoch_impact_snapshot_denominator_mismatch")
        if self.owner_projection_generation_ref != _owner_projection_generation_ref(
            requested_dependency_keys=self.requested_dependency_keys,
            owner_rows=self.owner_rows,
            targets=self.targets,
        ):
            raise ValueError("epoch_impact_snapshot_owner_generation_mismatch")
        values = self.model_dump(mode="json", exclude={"snapshot_content_hash"})
        if self.snapshot_content_hash != _semantic_hash(
            "polisyos.decision-validity.epoch-impact-snapshot.v1", values
        ):
            raise ValueError("epoch_impact_snapshot_content_hash_mismatch")
        return self


class DecisionValidityEpochImpactSnapshotHandle(BaseModel):
    """Reference exact persisted Scientist snapshot bytes and their self-hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_ref: ArtifactRef
    snapshot_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def _ref_has_snapshot_profile(self) -> DecisionValidityEpochImpactSnapshotHandle:
        if (
            self.snapshot_ref.kind != _SNAPSHOT_KIND
            or self.snapshot_ref.media_type != _SNAPSHOT_MEDIA_TYPE
        ):
            raise ValueError("decision_validity_epoch_impact_snapshot_ref_profile_mismatch")
        return self


class PersistedDecisionValidityEpochImpactSnapshot(BaseModel):
    """Carry exact snapshot bytes only after full local persistence verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handle: DecisionValidityEpochImpactSnapshotHandle
    snapshot_bytes: bytes
    snapshot: DecisionValidityEpochImpactSnapshot

    @model_validator(mode="after")
    def _bytes_are_exact(self) -> PersistedDecisionValidityEpochImpactSnapshot:
        try:
            parsed = DecisionValidityEpochImpactSnapshot.model_validate(
                from_canonical_bytes(self.snapshot_bytes)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("decision_validity_epoch_impact_snapshot_bytes_invalid") from exc
        if (
            _raw_sha256(self.snapshot_bytes) != str(self.handle.snapshot_ref.artifact_id)
            or to_canonical_bytes(parsed.model_dump(mode="json"), _CANON_SPEC)
            != self.snapshot_bytes
            or parsed != self.snapshot
            or self.handle.snapshot_content_hash != parsed.snapshot_content_hash
        ):
            raise ValueError("decision_validity_epoch_impact_snapshot_bytes_mismatch")
        return self


class EpochTransitionDenominatorMappingRow(BaseModel):
    """Map one Scientist impact member to exactly one Runtime target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependency_key: str = Field(min_length=1)
    dependency_artifact_id: Digest = Field(pattern=_DIGEST_PATTERN)
    packet_ref: str = Field(min_length=1)
    decision_lineage_key: str = Field(min_length=1)
    runtime_target_ref: ArtifactRef


class EpochTransitionDenominatorReconciliationReceipt(BaseModel):
    """Content-bind an independently verified relation between both owner denominators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[_EPOCH_RECONCILIATION_SCHEMA] = _EPOCH_RECONCILIATION_SCHEMA
    reconciliation_rule_version: Literal[_EPOCH_RECONCILIATION_SCHEMA] = (
        _EPOCH_RECONCILIATION_SCHEMA
    )
    canonicalization_profile: Literal[_CANONICALIZATION_PROFILE] = _CANONICALIZATION_PROFILE
    authority_purpose: Literal[_EPOCH_AUTHORITY_PURPOSE] = _EPOCH_AUTHORITY_PURPOSE
    requested_query_context_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"
    verifier_provenance_ref: ArtifactRef
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)
    epoch_dependency_denominator_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    runtime_target_refs: tuple[ArtifactRef, ...]
    scientist_snapshot_ref: ArtifactRef
    scientist_snapshot_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)
    decision_impact_denominator_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    requested_dependency_keys: tuple[str, ...]
    scientist_owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...]
    scientist_targets: tuple[DecisionValidityEpochImpactTarget, ...]
    mapping_rows: tuple[EpochTransitionDenominatorMappingRow, ...]
    reconciliation_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)

    @classmethod
    def build(
        cls,
        *,
        requested_query_context_ref: Digest,
        verifier_provenance_ref: ArtifactRef,
        transition_artifact_ref: ArtifactRef,
        transition_content_hash: Digest,
        epoch_dependency_denominator_ref: Digest,
        runtime_target_refs: tuple[ArtifactRef, ...],
        scientist_snapshot_ref: ArtifactRef,
        scientist_snapshot_content_hash: Digest,
        decision_impact_denominator_ref: Digest,
        requested_dependency_keys: tuple[str, ...],
        scientist_owner_rows: tuple[DecisionValidityEpochImpactOwnerRow, ...],
        scientist_targets: tuple[DecisionValidityEpochImpactTarget, ...],
        mapping_rows: tuple[EpochTransitionDenominatorMappingRow, ...],
    ) -> EpochTransitionDenominatorReconciliationReceipt:
        """Build a self-bound receipt from exact producer-derived coordinates."""

        values: dict[str, object] = {
            "schema_version": _EPOCH_RECONCILIATION_SCHEMA,
            "reconciliation_rule_version": _EPOCH_RECONCILIATION_SCHEMA,
            "canonicalization_profile": _CANONICALIZATION_PROFILE,
            "authority_purpose": _EPOCH_AUTHORITY_PURPOSE,
            "predicate_class": "independently_reconciled",
            "requested_query_context_ref": requested_query_context_ref,
            "verifier_provenance_ref": verifier_provenance_ref,
            "transition_artifact_ref": transition_artifact_ref,
            "transition_content_hash": transition_content_hash,
            "epoch_dependency_denominator_ref": epoch_dependency_denominator_ref,
            "runtime_target_refs": runtime_target_refs,
            "scientist_snapshot_ref": scientist_snapshot_ref,
            "scientist_snapshot_content_hash": scientist_snapshot_content_hash,
            "decision_impact_denominator_ref": decision_impact_denominator_ref,
            "requested_dependency_keys": requested_dependency_keys,
            "scientist_owner_rows": scientist_owner_rows,
            "scientist_targets": scientist_targets,
            "mapping_rows": mapping_rows,
        }
        return cls(
            **values,
            reconciliation_content_hash=_semantic_hash(
                "polisyos.epoch-transition-denominator-reconciliation.v1", values
            ),
        )

    @model_validator(mode="after")
    def _relation_is_complete_and_self_bound(
        self,
    ) -> EpochTransitionDenominatorReconciliationReceipt:
        if self.runtime_target_refs != tuple(
            sorted(self.runtime_target_refs, key=_artifact_ref_key)
        ):
            raise ValueError("epoch_reconciliation_runtime_targets_noncanonical")
        if len({_artifact_ref_key(ref) for ref in self.runtime_target_refs}) != len(
            self.runtime_target_refs
        ):
            raise ValueError("epoch_reconciliation_runtime_target_duplicate")
        if (
            self.scientist_snapshot_ref.kind != _SNAPSHOT_KIND
            or self.scientist_snapshot_ref.media_type != _SNAPSHOT_MEDIA_TYPE
        ):
            raise ValueError("epoch_reconciliation_snapshot_ref_profile_mismatch")
        snapshot = DecisionValidityEpochImpactSnapshot.build(
            requested_query_context_ref=self.requested_query_context_ref,
            requested_dependency_keys=self.requested_dependency_keys,
            owner_rows=self.scientist_owner_rows,
            targets=self.scientist_targets,
        )
        if (
            self.decision_impact_denominator_ref != snapshot.decision_impact_denominator_ref
            or self.scientist_snapshot_content_hash != snapshot.snapshot_content_hash
        ):
            raise ValueError("epoch_reconciliation_snapshot_mirror_mismatch")
        mapping_order = tuple(
            sorted(
                self.mapping_rows,
                key=lambda row: (row.dependency_key, row.packet_ref, row.decision_lineage_key),
            )
        )
        mapping_keys = tuple(
            (row.dependency_key, row.packet_ref, row.decision_lineage_key)
            for row in self.mapping_rows
        )
        target_keys = tuple(
            (row.dependency_key, row.packet_ref, row.decision_lineage_key)
            for row in self.scientist_targets
        )
        if (
            self.mapping_rows != mapping_order
            or len(mapping_keys) != len(set(mapping_keys))
            or mapping_keys != target_keys
        ):
            raise ValueError("epoch_reconciliation_mapping_denominator_mismatch")
        owner_artifacts = {
            row.dependency_key: row.artifact_id for row in self.scientist_owner_rows
        }
        for owner in self.scientist_owner_rows:
            candidates = tuple(
                ref
                for ref in self.runtime_target_refs
                if str(ref.artifact_id) == owner.artifact_id
            )
            if len(candidates) != 1:
                raise ValueError("epoch_denominator_membership_mismatch")
        for row in self.mapping_rows:
            candidates = tuple(
                ref
                for ref in self.runtime_target_refs
                if str(ref.artifact_id) == row.dependency_artifact_id
            )
            if (
                owner_artifacts.get(row.dependency_key) != row.dependency_artifact_id
                or len(candidates) != 1
                or candidates[0] != row.runtime_target_ref
            ):
                raise ValueError("epoch_denominator_membership_mismatch")
        values = self.model_dump(mode="json", exclude={"reconciliation_content_hash"})
        if self.reconciliation_content_hash != _semantic_hash(
            "polisyos.epoch-transition-denominator-reconciliation.v1", values
        ):
            raise ValueError("epoch_reconciliation_content_hash_mismatch")
        return self


class EpochTransitionDenominatorReconciliationHandle(BaseModel):
    """Reference exact persisted reconciliation bytes and their self-hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_receipt_ref: ArtifactRef
    reconciliation_receipt_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def _ref_has_reconciliation_profile(self) -> EpochTransitionDenominatorReconciliationHandle:
        if (
            self.reconciliation_receipt_ref.kind != _RECONCILIATION_KIND
            or self.reconciliation_receipt_ref.media_type != _RECONCILIATION_MEDIA_TYPE
        ):
            raise ValueError("epoch_reconciliation_receipt_ref_profile_mismatch")
        return self


class PersistedEpochTransitionDenominatorReconciliation(BaseModel):
    """Carry exact receipt bytes only after complete persistence verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handle: EpochTransitionDenominatorReconciliationHandle
    receipt_bytes: bytes
    receipt: EpochTransitionDenominatorReconciliationReceipt

    @model_validator(mode="after")
    def _bytes_are_exact(self) -> PersistedEpochTransitionDenominatorReconciliation:
        try:
            parsed = EpochTransitionDenominatorReconciliationReceipt.model_validate(
                from_canonical_bytes(self.receipt_bytes)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("epoch_reconciliation_receipt_bytes_invalid") from exc
        if (
            _raw_sha256(self.receipt_bytes)
            != str(self.handle.reconciliation_receipt_ref.artifact_id)
            or to_canonical_bytes(parsed.model_dump(mode="json"), _CANON_SPEC) != self.receipt_bytes
            or parsed != self.receipt
            or self.handle.reconciliation_receipt_content_hash
            != parsed.reconciliation_content_hash
        ):
            raise ValueError("epoch_reconciliation_receipt_bytes_mismatch")
        return self


class EpochDenominatorReconciliationAdmissionBinding(BaseModel):
    """Write-once Scientist owner binding to one exact reconciliation receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[_EPOCH_RECONCILIATION_BINDING_SCHEMA] = (
        _EPOCH_RECONCILIATION_BINDING_SCHEMA
    )
    batch_id: str = Field(min_length=1)
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)
    requested_query_context_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_purpose: Literal[_EPOCH_AUTHORITY_PURPOSE] = _EPOCH_AUTHORITY_PURPOSE
    decision_impact_denominator_ref: Digest = Field(pattern=_DIGEST_PATTERN)
    scientist_snapshot_ref: ArtifactRef
    scientist_snapshot_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)
    verifier_provenance_ref: ArtifactRef
    reconciliation_receipt_ref: ArtifactRef
    reconciliation_receipt_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)
    reconciliation_rule_version: Literal[_EPOCH_RECONCILIATION_SCHEMA] = (
        _EPOCH_RECONCILIATION_SCHEMA
    )
    canonicalization_profile: Literal[_CANONICALIZATION_PROFILE] = _CANONICALIZATION_PROFILE
    binding_content_hash: Digest = Field(pattern=_DIGEST_PATTERN)

    @classmethod
    def build(
        cls,
        *,
        batch_id: str,
        transition_artifact_ref: ArtifactRef,
        transition_content_hash: Digest,
        requested_query_context_ref: Digest,
        decision_impact_denominator_ref: Digest,
        scientist_snapshot_ref: ArtifactRef,
        scientist_snapshot_content_hash: Digest,
        verifier_provenance_ref: ArtifactRef,
        reconciliation_receipt_ref: ArtifactRef,
        reconciliation_receipt_content_hash: Digest,
    ) -> EpochDenominatorReconciliationAdmissionBinding:
        """Build a self-bound write-once owner binding."""

        values: dict[str, object] = {
            "schema_version": _EPOCH_RECONCILIATION_BINDING_SCHEMA,
            "batch_id": batch_id,
            "transition_artifact_ref": transition_artifact_ref,
            "transition_content_hash": transition_content_hash,
            "requested_query_context_ref": requested_query_context_ref,
            "authority_purpose": _EPOCH_AUTHORITY_PURPOSE,
            "decision_impact_denominator_ref": decision_impact_denominator_ref,
            "scientist_snapshot_ref": scientist_snapshot_ref,
            "scientist_snapshot_content_hash": scientist_snapshot_content_hash,
            "verifier_provenance_ref": verifier_provenance_ref,
            "reconciliation_receipt_ref": reconciliation_receipt_ref,
            "reconciliation_receipt_content_hash": reconciliation_receipt_content_hash,
            "reconciliation_rule_version": _EPOCH_RECONCILIATION_SCHEMA,
            "canonicalization_profile": _CANONICALIZATION_PROFILE,
        }
        return cls(
            **values,
            binding_content_hash=_semantic_hash(
                "polisyos.decision-validity.epoch-reconciliation-admission-binding.v1", values
            ),
        )

    @property
    def handle(self) -> EpochTransitionDenominatorReconciliationHandle:
        """Return the exact sidecar handle without changing serialized binding bytes."""

        return EpochTransitionDenominatorReconciliationHandle(
            reconciliation_receipt_ref=self.reconciliation_receipt_ref,
            reconciliation_receipt_content_hash=self.reconciliation_receipt_content_hash,
        )

    @model_validator(mode="after")
    def _binding_is_self_bound(self) -> EpochDenominatorReconciliationAdmissionBinding:
        DecisionValidityEpochImpactSnapshotHandle(
            snapshot_ref=self.scientist_snapshot_ref,
            snapshot_content_hash=self.scientist_snapshot_content_hash,
        )
        _ = self.handle
        values = self.model_dump(mode="json", exclude={"binding_content_hash"})
        if self.binding_content_hash != _semantic_hash(
            "polisyos.decision-validity.epoch-reconciliation-admission-binding.v1", values
        ):
            raise ValueError("epoch_reconciliation_admission_binding_hash_mismatch")
        return self


class EpochTransitionDenominatorReconciliationReader(Protocol):
    """Resolve candidate and exact reconciliation receipts without importing Runtime."""

    verifier_provenance_ref: ArtifactRef | None

    def resolve_for_first_admission(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        transition_content_hash: Digest,
        requested_query_context_ref: Digest,
        authority_purpose: Literal["decision_validity_epoch_transition"],
        scientist_snapshot_handle: DecisionValidityEpochImpactSnapshotHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Resolve the unique candidate matching first-admission coordinates."""
        ...

    def resolve_exact(
        self,
        *,
        handle: EpochTransitionDenominatorReconciliationHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Resolve one frozen receipt by exact ref and content hash."""
        ...


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
    "DecisionValidityEpochImpactOwnerRow",
    "DecisionValidityEpochImpactSnapshot",
    "DecisionValidityEpochImpactSnapshotHandle",
    "DecisionValidityEpochImpactTarget",
    "DecisionValidityEvaluation",
    "DecisionValidityStatus",
    "DecisionValidityTransition",
    "EpochDenominatorReconciliationAdmissionBinding",
    "EpochTransitionDenominatorMappingRow",
    "EpochTransitionDenominatorReconciliationHandle",
    "EpochTransitionDenominatorReconciliationReader",
    "EpochTransitionDenominatorReconciliationReceipt",
    "EpochTransitionVerificationReceipt",
    "EpochTransitionVerifier",
    "EpochValidityAuthorityGate",
    "EpochValidityBatchCompletionStatement",
    "EpochValidityBatchReceipt",
    "EpochValidityBatchTarget",
    "EpochValidityCompletedBatchEvidenceDenominator",
    "EpochValidityCompletedBatchEvidenceResolver",
    "EpochValidityGateNonReceipt",
    "EpochValidityGateReceipt",
    "EpochValidityN9EvidenceResolver",
    "EpochValidityN9Projection",
    "EpochValidityPendingBatch",
    "EpochValidityPreN9SubjectAuthority",
    "PersistedDecisionValidityEpochImpactSnapshot",
    "PersistedEpochTransitionDenominatorReconciliation",
    "PersistedEpochValidityBatchEvidence",
    "PersistedEpochValidityGateEvidence",
    "PersistedPreN9AdmittedCandidateBatch",
    "PersistedPreN9EpochValiditySubject",
    "PreN9AdmittedCandidate",
    "PreN9EpochValiditySubjectStatement",
]
