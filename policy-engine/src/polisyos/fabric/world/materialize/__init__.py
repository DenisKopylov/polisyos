from __future__ import annotations

from polisyos.fabric.world.materialize.duckdb import (
    WorldMaterializeSegmentStats,
    WorldMaterializeStats,
    apply_world_segment,
    ensure_world_materialized,
    ensure_world_schema,
    materialize_world_duckdb_from_fact_log,
)
from polisyos.fabric.world.materialize.errors import (
    WorldArtifactReadError,
    WorldKuzuCopyError,
    WorldKuzuImportError,
    WorldKuzuNotAvailable,
    WorldMaterializationError,
    WorldMergeConflict,
    WorldSchemaError,
    WorldSegmentHashMismatch,
)
from polisyos.fabric.world.materialize.kuzu import (
    ensure_world_kuzu_schema,
    materialize_world_kuzu_from_duckdb,
)
from polisyos.fabric.world.materialize.rules import MergeStrategy

__all__ = [
    "MergeStrategy",
    "WorldArtifactReadError",
    "WorldKuzuCopyError",
    "WorldKuzuImportError",
    "WorldKuzuNotAvailable",
    "WorldMaterializationError",
    "WorldMaterializeSegmentStats",
    "WorldMaterializeStats",
    "WorldMergeConflict",
    "WorldSchemaError",
    "WorldSegmentHashMismatch",
    "apply_world_segment",
    "ensure_world_materialized",
    "ensure_world_kuzu_schema",
    "ensure_world_schema",
    "materialize_world_duckdb_from_fact_log",
    "materialize_world_kuzu_from_duckdb",
]
