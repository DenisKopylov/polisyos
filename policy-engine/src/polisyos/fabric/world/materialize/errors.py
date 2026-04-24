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


class WorldSegmentHashMismatch(WorldMaterializationError):
    """Raised when a segment hash does not match the manifest."""

    default_category = ErrorCategory.VALIDATION


class WorldMergeConflict(WorldMaterializationError):
    """Raised when merge rules are violated (e.g., world.kind conflict)."""

    default_category = ErrorCategory.VALIDATION


class WorldArtifactReadError(WorldMaterializationError):
    """Raised when CAS artifacts are missing or invalid."""

    default_category = ErrorCategory.TRANSIENT


class WorldKuzuNotAvailable(WorldMaterializationError):
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
