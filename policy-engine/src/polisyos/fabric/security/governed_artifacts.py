"""Runtime governance helpers for governed Fabric artifact writes."""

from __future__ import annotations

from collections.abc import Mapping

from polisyos.core.artifacts.manifest import (
    ArtifactEncryptionPolicyInfo,
    ArtifactGovernanceInfo,
    ArtifactRetentionPolicyInfo,
)

from .access_control import DataClassification, normalize_classification
from .retention import EncryptionMode, RetentionPlanner, RetentionScope


class ArtifactGovernanceError(ValueError):
    """Raised when a governed artifact write does not satisfy runtime policy."""


def resolve_artifact_governance(
    *,
    scope: RetentionScope,
    classification: DataClassification | str | None,
    column_classification: Mapping[str, DataClassification | str] | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
    planner: RetentionPlanner | None = None,
) -> ArtifactGovernanceInfo:
    """Resolve and enforce retention/encryption policy for one artifact write."""

    resolved_classification = normalize_classification(classification)
    normalized_columns = {
        str(column): normalize_classification(level).value
        for column, level in dict(column_classification or {}).items()
        if str(column).strip()
    }
    decision = (planner or RetentionPlanner()).resolve(
        scope=scope,
        classification=resolved_classification,
    )
    _enforce_encryption_requirement(
        scope=scope,
        decision_mode=decision.encryption_mode,
        encrypted_at_rest=encrypted_at_rest,
        field_level_encrypted=field_level_encrypted,
    )
    encryption_verified = _encryption_verified(
        decision_mode=decision.encryption_mode,
        encrypted_at_rest=encrypted_at_rest,
        field_level_encrypted=field_level_encrypted,
    )
    return ArtifactGovernanceInfo(
        classification=resolved_classification.value,
        column_classification=normalized_columns,
        retention=ArtifactRetentionPolicyInfo(
            scope=decision.scope.value,
            retention_days=decision.retention_days,
            delete_on_expiry=decision.delete_on_expiry,
        ),
        encryption=ArtifactEncryptionPolicyInfo(
            mode=decision.encryption_mode.value,
            enforced=decision.encryption_mode != EncryptionMode.NONE,
            verified=encryption_verified,
            key_reference=encryption_key_reference,
        ),
    )


def validate_artifact_governance(
    info: ArtifactGovernanceInfo | None,
) -> ArtifactGovernanceInfo | None:
    """Validate one prebuilt governance payload loaded from storage or external adapters."""

    if info is None:
        return None
    mode = (
        EncryptionMode(str(info.encryption.mode))
        if info.encryption is not None
        else EncryptionMode.NONE
    )
    if info.encryption is not None and info.encryption.enforced and not info.encryption.verified:
        raise ArtifactGovernanceError(
            f"artifact governance requires verified {mode.value} encryption before persistence"
        )
    return info


def _enforce_encryption_requirement(
    *,
    scope: RetentionScope,
    decision_mode: EncryptionMode,
    encrypted_at_rest: bool,
    field_level_encrypted: bool,
) -> None:
    if decision_mode == EncryptionMode.NONE:
        return
    if decision_mode == EncryptionMode.ENVELOPE and not encrypted_at_rest:
        raise ArtifactGovernanceError(
            f"{scope.value} retention policy requires verified at-rest encryption for governed writes"
        )
    if decision_mode == EncryptionMode.FIELD_LEVEL and not field_level_encrypted:
        raise ArtifactGovernanceError(
            f"{scope.value} retention policy requires verified field-level encryption for governed writes"
        )


def _encryption_verified(
    *,
    decision_mode: EncryptionMode,
    encrypted_at_rest: bool,
    field_level_encrypted: bool,
) -> bool:
    if decision_mode == EncryptionMode.NONE:
        return True
    if decision_mode == EncryptionMode.ENVELOPE:
        return encrypted_at_rest
    if decision_mode == EncryptionMode.FIELD_LEVEL:
        return field_level_encrypted
    return False


__all__ = [
    "ArtifactGovernanceError",
    "resolve_artifact_governance",
    "validate_artifact_governance",
]
