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


__all__ = [
    "WorldArtifactReadError",
    "WorldMaterializationError",
    "WorldMergeConflict",
    "WorldSchemaError",
    "WorldSegmentHashMismatch",
]
