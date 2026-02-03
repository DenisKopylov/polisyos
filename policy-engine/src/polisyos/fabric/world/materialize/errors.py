from __future__ import annotations


class WorldMaterializationError(Exception):
    """Base error for world materialization."""


class WorldSchemaError(WorldMaterializationError):
    """Raised for schema or DDL failures."""


class WorldSegmentHashMismatch(WorldMaterializationError):
    """Raised when a segment hash does not match the manifest."""


class WorldMergeConflict(WorldMaterializationError):
    """Raised when merge rules are violated (e.g., world.kind conflict)."""


class WorldArtifactReadError(WorldMaterializationError):
    """Raised when CAS artifacts are missing or invalid."""


class WorldKuzuNotAvailable(WorldMaterializationError):
    """Raised when Kuzu is required but not available."""


class WorldKuzuImportError(WorldMaterializationError):
    """Raised when Kuzu import fails unexpectedly."""


class WorldKuzuCopyError(WorldMaterializationError):
    """Raised when Kuzu COPY operations fail."""


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
