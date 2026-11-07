"""Facade for emitting, validating, persisting, and materializing world facts."""

from __future__ import annotations

import importlib.util as _importlib_util

from polisyos.fabric.world.store import (
    SEGMENTS_INDEX_NAME,
    WorldFactError,
    WorldIDError,
    WorldSegmentError,
    WorldStoreError,
    WorldValidationError,
    append_world_segment_index,
    emit_attr_fact,
    emit_claim_facts,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    emit_edge_fact,
    emit_world_event_facts,
    emit_world_node_facts,
    event_world_provenance_v1,
    load_world_fact_manifests,
    load_world_facts,
    persist_claim,
    persist_conflict_set,
    persist_doc_fragment,
    persist_doc_meta,
    persist_fact_segment_manifest,
    persist_quality_report,
    persist_trust_assessment,
    persist_world_event,
    stable_world_provenance_v1,
    validate_claim_id,
    validate_conflict_set_id,
    validate_doc_fragment_ids,
    validate_doc_meta_ids,
    validate_fact_is_world_abi,
    validate_quality_report_id,
    validate_trust_assessment_id,
    validate_world_event_id,
    validate_world_facts,
    write_world_fact_segment,
)
from polisyos.fabric.world.write import (
    WorldSnapshotBackendUnavailable,
    WorldSnapshotFactWrite,
    WorldSnapshotNodeWrite,
    WorldSnapshotWriteRequest,
    write_world_snapshot,
)

_DUCKDB_AVAILABLE = _importlib_util.find_spec("duckdb") is not None
if _DUCKDB_AVAILABLE:
    from polisyos.fabric.world.materialize import (
        MergeStrategy as MergeStrategy,
    )
    from polisyos.fabric.world.materialize import (
        WorldArtifactReadError as WorldArtifactReadError,
    )
    from polisyos.fabric.world.materialize import (
        WorldKuzuCopyError as WorldKuzuCopyError,
    )
    from polisyos.fabric.world.materialize import (
        WorldKuzuImportError as WorldKuzuImportError,
    )
    from polisyos.fabric.world.materialize import (
        WorldKuzuNotAvailable as WorldKuzuNotAvailable,
    )
    from polisyos.fabric.world.materialize import (
        WorldMaterializationError as WorldMaterializationError,
    )
    from polisyos.fabric.world.materialize import (
        WorldMaterializationPolicy as WorldMaterializationPolicy,
    )
    from polisyos.fabric.world.materialize import (
        WorldMaterializeSegmentStats as WorldMaterializeSegmentStats,
    )
    from polisyos.fabric.world.materialize import (
        WorldMaterializeStats as WorldMaterializeStats,
    )
    from polisyos.fabric.world.materialize import (
        WorldMergeConflict as WorldMergeConflict,
    )
    from polisyos.fabric.world.materialize import (
        WorldSchemaError as WorldSchemaError,
    )
    from polisyos.fabric.world.materialize import (
        WorldSegmentHashMismatch as WorldSegmentHashMismatch,
    )
    from polisyos.fabric.world.materialize import (
        apply_world_segment as apply_world_segment,
    )
    from polisyos.fabric.world.materialize import (
        ensure_world_kuzu_schema as ensure_world_kuzu_schema,
    )
    from polisyos.fabric.world.materialize import (
        ensure_world_materialized as ensure_world_materialized,
    )
    from polisyos.fabric.world.materialize import (
        ensure_world_schema as ensure_world_schema,
    )
    from polisyos.fabric.world.materialize import (
        materialize_world_duckdb_from_fact_log as materialize_world_duckdb_from_fact_log,
    )
    from polisyos.fabric.world.materialize import (
        materialize_world_kuzu_from_duckdb as materialize_world_kuzu_from_duckdb,
    )

    _MATERIALIZE_EXPORTS: tuple[str, ...] = (
        "MergeStrategy",
        "WorldArtifactReadError",
        "WorldKuzuCopyError",
        "WorldKuzuImportError",
        "WorldKuzuNotAvailable",
        "WorldMaterializationError",
        "WorldMaterializationPolicy",
        "WorldMaterializeSegmentStats",
        "WorldMaterializeStats",
        "WorldMergeConflict",
        "WorldSchemaError",
        "WorldSegmentHashMismatch",
        "apply_world_segment",
        "ensure_world_kuzu_schema",
        "ensure_world_materialized",
        "ensure_world_schema",
        "materialize_world_duckdb_from_fact_log",
        "materialize_world_kuzu_from_duckdb",
    )
    _MATERIALIZE_AVAILABLE = True
else:  # pragma: no cover - optional dependency path
    _MATERIALIZE_EXPORTS = ()
    _MATERIALIZE_AVAILABLE = False

__all__ = [
    "SEGMENTS_INDEX_NAME",
    "WorldFactError",
    "WorldIDError",
    "WorldSegmentError",
    "WorldSnapshotBackendUnavailable",
    "WorldSnapshotFactWrite",
    "WorldSnapshotNodeWrite",
    "WorldSnapshotWriteRequest",
    "WorldStoreError",
    "WorldValidationError",
    "append_world_segment_index",
    "emit_attr_fact",
    "emit_claim_facts",
    "emit_doc_fragment_facts",
    "emit_doc_meta_facts",
    "emit_edge_fact",
    "emit_world_event_facts",
    "emit_world_node_facts",
    "event_world_provenance_v1",
    "load_world_fact_manifests",
    "load_world_facts",
    "persist_claim",
    "persist_conflict_set",
    "persist_doc_fragment",
    "persist_doc_meta",
    "persist_fact_segment_manifest",
    "persist_quality_report",
    "persist_trust_assessment",
    "persist_world_event",
    "stable_world_provenance_v1",
    "validate_claim_id",
    "validate_conflict_set_id",
    "validate_doc_fragment_ids",
    "validate_doc_meta_ids",
    "validate_fact_is_world_abi",
    "validate_quality_report_id",
    "validate_trust_assessment_id",
    "validate_world_event_id",
    "validate_world_facts",
    "write_world_fact_segment",
    "write_world_snapshot",
]

if _MATERIALIZE_AVAILABLE:
    __all__.extend(_MATERIALIZE_EXPORTS)
