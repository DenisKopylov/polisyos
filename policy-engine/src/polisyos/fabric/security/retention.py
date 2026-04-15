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


class EncryptionMode(str, Enum):
    """At-rest encryption mode for governed artifacts."""

    NONE = "none"
    ENVELOPE = "envelope"
    FIELD_LEVEL = "field_level"


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
]
