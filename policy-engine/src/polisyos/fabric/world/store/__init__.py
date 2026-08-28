"""World-store surface for fact emission, validation, artifact persistence, and segment I/O."""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import TYPE_CHECKING, Any

from polisyos.fabric.world.store.emit import (
    emit_attr_fact,
    emit_claim_facts,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    emit_edge_fact,
    emit_world_event_facts,
    emit_world_node_facts,
)
from polisyos.fabric.world.store.errors import (
    WorldFactError,
    WorldIDError,
    WorldSegmentError,
    WorldStoreError,
    WorldValidationError,
)
from polisyos.fabric.world.store.persist import (
    persist_claim,
    persist_conflict_set,
    persist_doc_fragment,
    persist_doc_meta,
    persist_quality_report,
    persist_trust_assessment,
    persist_world_event,
)
from polisyos.fabric.world.store.provenance import (
    event_world_provenance_v1,
    stable_world_provenance_v1,
)
from polisyos.fabric.world.store.quarantine import (
    QuarantineRecord,
    QuarantineReport,
    QuarantineReprocessResult,
    build_quarantine_report,
    list_quarantine_records,
    load_quarantine_payload,
    load_quarantine_record,
    persist_quarantine_record,
    quarantine_index_path,
    register_quarantine_reprocessor,
    reprocess_quarantine_records,
)
from polisyos.fabric.world.store.segments import (
    SEGMENTS_INDEX_NAME,
    WorldFactMutationMetadata,
    WorldMutationKind,
    WorldObservedState,
    WorldSegmentGCReport,
    annotate_world_fact_mutation,
    append_world_segment_index,
    build_world_mutation_metadata,
    gc_world_segments,
    load_world_fact_manifests,
    load_world_facts,
    parse_world_mutation_notes,
    persist_fact_segment_manifest,
    provenance_with_world_mutation,
    vacuum_world_segment_index,
    write_world_fact_segment,
)
from polisyos.fabric.world.store.validate import (
    validate_claim_id,
    validate_conflict_set_id,
    validate_doc_fragment_ids,
    validate_doc_meta_ids,
    validate_fact_is_world_abi,
    validate_quality_report_id,
    validate_trust_assessment_id,
    validate_world_event_id,
    validate_world_facts,
)

_SNAPSHOT_EXPORT_NAMES = frozenset(
    {
        "WorldBranchConflictSummary",
        "WorldBranchGovernanceEvidence",
        "WorldBranchMergeConflictError",
        "WorldBranchMergeReport",
        "WorldBranchRecord",
        "WorldMergeConflictResolution",
        "WorldSnapshotAdapterError",
        "WorldSnapshotAdapterSpec",
        "WorldSnapshotGCReport",
        "WorldSnapshotRecord",
        "create_world_branch",
        "create_world_snapshot",
        "default_world_snapshot_root",
        "delete_world_branch",
        "export_world_branch_governance",
        "gc_world_snapshots",
        "get_world_branch",
        "get_world_snapshot_adapter",
        "list_world_snapshot_adapters",
        "list_world_snapshots",
        "merge_world_branch",
        "register_world_snapshot_record",
        "resolve_world_snapshot",
        "update_world_branch_head",
    }
)

if TYPE_CHECKING:
    from polisyos.fabric.world.store.snapshots import (
        WorldBranchConflictSummary,
        WorldBranchGovernanceEvidence,
        WorldBranchMergeConflictError,
        WorldBranchMergeReport,
        WorldBranchRecord,
        WorldMergeConflictResolution,
        WorldSnapshotAdapterError,
        WorldSnapshotAdapterSpec,
        WorldSnapshotGCReport,
        WorldSnapshotRecord,
        create_world_branch,
        create_world_snapshot,
        default_world_snapshot_root,
        delete_world_branch,
        export_world_branch_governance,
        gc_world_snapshots,
        get_world_branch,
        get_world_snapshot_adapter,
        list_world_snapshot_adapters,
        list_world_snapshots,
        merge_world_branch,
        register_world_snapshot_record,
        resolve_world_snapshot,
        update_world_branch_head,
    )


def __getattr__(name: str) -> Any:
    """Lazily resolve snapshot helpers that require the optional DuckDB backend."""

    if name not in _SNAPSHOT_EXPORT_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    snapshots = _import_module("polisyos.fabric.world.store.snapshots")
    value = getattr(snapshots, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return the declared world-store surface without acquiring snapshot dependencies."""

    return sorted(set(globals()) | _SNAPSHOT_EXPORT_NAMES)

__all__ = [
    "SEGMENTS_INDEX_NAME",
    "QuarantineRecord",
    "QuarantineReport",
    "QuarantineReprocessResult",
    "WorldBranchConflictSummary",
    "WorldBranchGovernanceEvidence",
    "WorldBranchMergeConflictError",
    "WorldBranchMergeReport",
    "WorldBranchRecord",
    "WorldFactError",
    "WorldFactMutationMetadata",
    "WorldIDError",
    "WorldMergeConflictResolution",
    "WorldMutationKind",
    "WorldObservedState",
    "WorldSegmentError",
    "WorldSegmentGCReport",
    "WorldSnapshotAdapterError",
    "WorldSnapshotAdapterSpec",
    "WorldSnapshotGCReport",
    "WorldSnapshotRecord",
    "WorldStoreError",
    "WorldValidationError",
    "annotate_world_fact_mutation",
    "append_world_segment_index",
    "build_quarantine_report",
    "build_world_mutation_metadata",
    "create_world_branch",
    "create_world_snapshot",
    "default_world_snapshot_root",
    "delete_world_branch",
    "emit_attr_fact",
    "emit_claim_facts",
    "emit_doc_fragment_facts",
    "emit_doc_meta_facts",
    "emit_edge_fact",
    "emit_world_event_facts",
    "emit_world_node_facts",
    "event_world_provenance_v1",
    "export_world_branch_governance",
    "gc_world_segments",
    "gc_world_snapshots",
    "get_world_branch",
    "get_world_snapshot_adapter",
    "list_quarantine_records",
    "list_world_snapshot_adapters",
    "list_world_snapshots",
    "load_quarantine_payload",
    "load_quarantine_record",
    "load_world_fact_manifests",
    "load_world_facts",
    "merge_world_branch",
    "parse_world_mutation_notes",
    "persist_claim",
    "persist_conflict_set",
    "persist_doc_fragment",
    "persist_doc_meta",
    "persist_fact_segment_manifest",
    "persist_quality_report",
    "persist_quarantine_record",
    "persist_trust_assessment",
    "persist_world_event",
    "provenance_with_world_mutation",
    "quarantine_index_path",
    "register_quarantine_reprocessor",
    "register_world_snapshot_record",
    "reprocess_quarantine_records",
    "resolve_world_snapshot",
    "stable_world_provenance_v1",
    "update_world_branch_head",
    "vacuum_world_segment_index",
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
]
