"""Defense-in-depth helpers for enforcing column-level authorization on fabric outputs."""

from polisyos.fabric.security.access_control import (
    AccessAuditEvent,
    DataClassification,
    JsonlAccessAuditLog,
    RowAccessPolicy,
    cardinality_bucket,
    classification_allowed,
    current_trace_id,
    normalize_classification,
)
from polisyos.fabric.security.column_mask import (
    apply_requested_column_guard,
    mask_dataframe_columns,
    normalize_allowed_columns,
)
from polisyos.fabric.security.governed_artifacts import (
    ArtifactGovernanceError,
    resolve_artifact_governance,
    validate_artifact_governance,
)
from polisyos.fabric.security.retention import (
    EncryptionMode,
    RetentionDecision,
    RetentionPlanner,
    RetentionPolicy,
    RetentionScope,
    SnapshotDeletionImpact,
    SnapshotRetentionClass,
    build_snapshot_deletion_impact,
    classify_snapshot_retention,
)

__all__ = [
    "AccessAuditEvent",
    "ArtifactGovernanceError",
    "DataClassification",
    "EncryptionMode",
    "JsonlAccessAuditLog",
    "RetentionDecision",
    "RetentionPlanner",
    "RetentionPolicy",
    "RetentionScope",
    "RowAccessPolicy",
    "SnapshotDeletionImpact",
    "SnapshotRetentionClass",
    "apply_requested_column_guard",
    "build_snapshot_deletion_impact",
    "cardinality_bucket",
    "classification_allowed",
    "classify_snapshot_retention",
    "current_trace_id",
    "mask_dataframe_columns",
    "normalize_allowed_columns",
    "normalize_classification",
    "resolve_artifact_governance",
    "validate_artifact_governance",
]
