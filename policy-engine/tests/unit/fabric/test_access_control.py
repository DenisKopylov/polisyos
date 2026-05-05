from __future__ import annotations

import pytest
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.fabric.security import (
    ArtifactGovernanceError,
    DataClassification,
    EncryptionMode,
    RetentionPlanner,
    RetentionScope,
    classification_allowed,
    resolve_artifact_governance,
)


def test_classification_access_requires_purpose_for_confidential_data() -> None:
    scope = AccessScope(
        tenant_id="tenant-a",
        cell_id=None,
        principal_type="user",
        user_sub="analyst",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
    )

    allowed, reason = classification_allowed(scope, DataClassification.CONFIDENTIAL)

    assert allowed is False
    assert "purpose_of_use" in reason


def test_retention_planner_assigns_field_level_encryption_for_regulated_pii() -> None:
    planner = RetentionPlanner()

    decision = planner.resolve(
        scope=RetentionScope.CAS,
        classification=DataClassification.REGULATED_PII,
    )

    assert decision.retention_days == 30
    assert decision.encryption_mode == EncryptionMode.FIELD_LEVEL


def test_resolve_artifact_governance_requires_verified_encryption() -> None:
    with pytest.raises(ArtifactGovernanceError, match="at-rest encryption"):
        resolve_artifact_governance(
            scope=RetentionScope.CAS,
            classification=DataClassification.CONFIDENTIAL,
        )


def test_resolve_artifact_governance_persists_column_classification() -> None:
    info = resolve_artifact_governance(
        scope=RetentionScope.CACHE,
        classification=DataClassification.INTERNAL,
        column_classification={"ssn": DataClassification.REGULATED_PII},
        encrypted_at_rest=True,
        encryption_key_reference="kms://fabric/test",
    )

    assert info.classification == "internal"
    assert info.column_classification == {"ssn": "regulated_pii"}
    assert info.retention is not None
    assert info.retention.scope == "cache"
    assert info.encryption is not None
    assert info.encryption.mode == "none"
    assert info.encryption.verified is True
