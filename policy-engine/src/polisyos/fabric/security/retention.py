"""Retention and encryption planning for Fabric governed artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .access_control import DataClassification, normalize_classification


class RetentionScope(str, Enum):
    """Artifact family governed by retention policy."""

    CACHE = "cache"
    CAS = "cas"
    EVIDENCE_BUNDLE = "evidence_bundle"
    WORLD_PROJECTION = "world_projection"
    WORLD_SNAPSHOT = "world_snapshot"
    WORLD_BRANCH = "world_branch"


class EncryptionMode(str, Enum):
    """At-rest encryption mode for governed artifacts."""

    NONE = "none"
    ENVELOPE = "envelope"
    FIELD_LEVEL = "field_level"


class SnapshotRetentionClass(str, Enum):
    """Retention class for retained world snapshots and branches."""

    STANDARD = "standard"
    AUDIT_TAGGED = "audit_tagged"
    LEGAL_HOLD = "legal_hold"


class RetentionPolicy(BaseModel):
    """Retention rule for one artifact scope/classification pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: RetentionScope
    classification: DataClassification
    retention_days: int = Field(ge=0)
    delete_on_expiry: bool = True
    encryption_mode: EncryptionMode = EncryptionMode.NONE


class RetentionDecision(BaseModel):
    """Resolved retention and encryption plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: RetentionScope
    classification: DataClassification
    retention_days: int
    delete_on_expiry: bool
    encryption_mode: EncryptionMode


class SnapshotDeletionImpact(BaseModel):
    """Replay/time-travel impact record emitted before snapshot or branch deletion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str | None = None
    branch_name: str | None = None
    retention_class: SnapshotRetentionClass = SnapshotRetentionClass.STANDARD
    replay_impacted: bool = False
    time_travel_impacted: bool = False
    redaction_ref: str | None = None
    reason: str
    alternative_retention_ref: str | None = None


@dataclass(frozen=True, slots=True)
class RetentionPlanner:
    """Resolve default retention policies per classification and scope."""

    def resolve(
        self,
        *,
        scope: RetentionScope,
        classification: DataClassification | str | None,
    ) -> RetentionDecision:
        resolved = normalize_classification(classification)
        policy = _DEFAULT_POLICIES[(scope, resolved)]
        return RetentionDecision(
            scope=scope,
            classification=resolved,
            retention_days=policy.retention_days,
            delete_on_expiry=policy.delete_on_expiry,
            encryption_mode=policy.encryption_mode,
        )


def classify_snapshot_retention(
    *,
    tags: tuple[str, ...] = (),
    legal_hold: bool = False,
) -> SnapshotRetentionClass:
    """Classify retained world snapshots for GC and legal retention."""

    normalized = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
    if legal_hold or "legal_hold" in normalized or "legal-retention" in normalized:
        return SnapshotRetentionClass.LEGAL_HOLD
    if "audit" in normalized or "audit_tagged" in normalized:
        return SnapshotRetentionClass.AUDIT_TAGGED
    return SnapshotRetentionClass.STANDARD


def build_snapshot_deletion_impact(
    *,
    snapshot_id: str | None = None,
    branch_name: str | None = None,
    retention_class: SnapshotRetentionClass = SnapshotRetentionClass.STANDARD,
    reason: str,
    redaction_ref: str | None = None,
    alternative_retention_ref: str | None = None,
) -> SnapshotDeletionImpact:
    """Build the explicit replay/time-travel impact record for deletion/redaction."""

    if not str(reason or "").strip():
        raise ValueError("snapshot deletion impact requires reason")
    return SnapshotDeletionImpact(
        snapshot_id=snapshot_id,
        branch_name=branch_name,
        retention_class=retention_class,
        replay_impacted=True,
        time_travel_impacted=True,
        redaction_ref=redaction_ref,
        reason=str(reason).strip(),
        alternative_retention_ref=alternative_retention_ref,
    )


_DEFAULT_POLICIES: dict[tuple[RetentionScope, DataClassification], RetentionPolicy] = {}
for scope, classification, retention_days, encryption_mode in (
    (RetentionScope.CACHE, DataClassification.PUBLIC, 30, EncryptionMode.NONE),
    (RetentionScope.CACHE, DataClassification.INTERNAL, 14, EncryptionMode.NONE),
    (RetentionScope.CACHE, DataClassification.CONFIDENTIAL, 7, EncryptionMode.ENVELOPE),
    (RetentionScope.CACHE, DataClassification.REGULATED_PII, 3, EncryptionMode.FIELD_LEVEL),
    (
        RetentionScope.CACHE,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        7,
        EncryptionMode.ENVELOPE,
    ),
    (RetentionScope.CAS, DataClassification.PUBLIC, 365, EncryptionMode.NONE),
    (RetentionScope.CAS, DataClassification.INTERNAL, 180, EncryptionMode.ENVELOPE),
    (RetentionScope.CAS, DataClassification.CONFIDENTIAL, 90, EncryptionMode.ENVELOPE),
    (RetentionScope.CAS, DataClassification.REGULATED_PII, 30, EncryptionMode.FIELD_LEVEL),
    (
        RetentionScope.CAS,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        90,
        EncryptionMode.ENVELOPE,
    ),
    (RetentionScope.EVIDENCE_BUNDLE, DataClassification.PUBLIC, 365, EncryptionMode.NONE),
    (
        RetentionScope.EVIDENCE_BUNDLE,
        DataClassification.INTERNAL,
        180,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.EVIDENCE_BUNDLE,
        DataClassification.CONFIDENTIAL,
        90,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.EVIDENCE_BUNDLE,
        DataClassification.REGULATED_PII,
        30,
        EncryptionMode.FIELD_LEVEL,
    ),
    (
        RetentionScope.EVIDENCE_BUNDLE,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        90,
        EncryptionMode.ENVELOPE,
    ),
    (RetentionScope.WORLD_PROJECTION, DataClassification.PUBLIC, 180, EncryptionMode.NONE),
    (
        RetentionScope.WORLD_PROJECTION,
        DataClassification.INTERNAL,
        90,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_PROJECTION,
        DataClassification.CONFIDENTIAL,
        30,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_PROJECTION,
        DataClassification.REGULATED_PII,
        14,
        EncryptionMode.FIELD_LEVEL,
    ),
    (
        RetentionScope.WORLD_PROJECTION,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        30,
        EncryptionMode.ENVELOPE,
    ),
    (RetentionScope.WORLD_SNAPSHOT, DataClassification.PUBLIC, 365, EncryptionMode.NONE),
    (
        RetentionScope.WORLD_SNAPSHOT,
        DataClassification.INTERNAL,
        365,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_SNAPSHOT,
        DataClassification.CONFIDENTIAL,
        180,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_SNAPSHOT,
        DataClassification.REGULATED_PII,
        90,
        EncryptionMode.FIELD_LEVEL,
    ),
    (
        RetentionScope.WORLD_SNAPSHOT,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        180,
        EncryptionMode.ENVELOPE,
    ),
    (RetentionScope.WORLD_BRANCH, DataClassification.PUBLIC, 365, EncryptionMode.NONE),
    (
        RetentionScope.WORLD_BRANCH,
        DataClassification.INTERNAL,
        365,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_BRANCH,
        DataClassification.CONFIDENTIAL,
        180,
        EncryptionMode.ENVELOPE,
    ),
    (
        RetentionScope.WORLD_BRANCH,
        DataClassification.REGULATED_PII,
        90,
        EncryptionMode.FIELD_LEVEL,
    ),
    (
        RetentionScope.WORLD_BRANCH,
        DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL,
        180,
        EncryptionMode.ENVELOPE,
    ),
):
    _DEFAULT_POLICIES[(scope, classification)] = RetentionPolicy(
        scope=scope,
        classification=classification,
        retention_days=retention_days,
        encryption_mode=encryption_mode,
    )


__all__ = [
    "EncryptionMode",
    "RetentionDecision",
    "RetentionPlanner",
    "RetentionPolicy",
    "RetentionScope",
    "SnapshotDeletionImpact",
    "SnapshotRetentionClass",
    "build_snapshot_deletion_impact",
    "classify_snapshot_retention",
]
