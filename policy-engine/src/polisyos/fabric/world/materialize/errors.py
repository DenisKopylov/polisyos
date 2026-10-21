"""Public materialize errors module API."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError


class WorldMaterializationError(PolicyOSError):
    """Base error for world materialization."""

    default_stage = "fabric.world.materialize"
    default_category = ErrorCategory.FATAL


class WorldSchemaError(WorldMaterializationError):
    """Raised for schema or DDL failures."""

    default_category = ErrorCategory.VALIDATION


# AD-E02-FABRIC-N818-01 v1: preserve only the selected existing exception identities.
# this is an N818 compatibility rationale, not an exception-class or waiver framework.
# Decision path: `policy-engine/docs/research/e02-cloud-test-plan/integration/architecture-decisions-2026-10-21/09-fabric-exception-identities.md`.
class WorldSegmentHashMismatch(WorldMaterializationError):  # noqa: N818 -- world integrity checks classify this validation type
    """Raised when a segment hash does not match the manifest."""

    default_category = ErrorCategory.VALIDATION


class WorldMergeConflict(WorldMaterializationError):  # noqa: N818 -- world merge consumers catch this validation type
    """Raised when merge rules are violated (e.g., world.kind conflict)."""

    default_category = ErrorCategory.VALIDATION


class WorldArtifactReadError(WorldMaterializationError):
    """Raised when CAS artifacts are missing or invalid."""

    default_category = ErrorCategory.TRANSIENT


class WorldKuzuNotAvailable(WorldMaterializationError):  # noqa: N818 -- optional Kuzu consumers classify this transient refusal
    """Raised when Kuzu is required but not available."""

    default_category = ErrorCategory.TRANSIENT


class WorldKuzuImportError(WorldMaterializationError):
    """Raised when Kuzu import fails unexpectedly."""

    default_category = ErrorCategory.TRANSIENT


class WorldKuzuCopyError(WorldMaterializationError):
    """Raised when Kuzu COPY operations fail."""

    default_category = ErrorCategory.TRANSIENT


__all__ = [
    "WorldArtifactReadError",
    "WorldKuzuCopyError",
    "WorldKuzuImportError",
    "WorldKuzuNotAvailable",
    "WorldMaterializationError",
    "WorldMergeConflict",
    "WorldSchemaError",
    "WorldSegmentHashMismatch",
]
