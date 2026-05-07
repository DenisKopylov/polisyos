"""DuckDB-native world snapshots, branch metadata, and retention helpers."""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo
from polisyos.fabric.io.atomic import atomic_write_json
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.quality.safety import quote_sql_identifier
from polisyos.fabric.security import (
    ArtifactGovernanceError,
    DataClassification,
    RetentionScope,
    SnapshotRetentionClass,
    classify_snapshot_retention,
    resolve_artifact_governance,
    validate_artifact_governance,
)
from polisyos.fabric.temporal import parse_datetime_utc, utc_now
from polisyos.fabric.world.materialize.sql import (
    sql_insert_missing_nodes,
    sql_update_world_nodes,
)
from polisyos.ir.world.predicates import WORLD_KIND

_SNAPSHOT_STORAGE_ADAPTER = "duckdb_native_file_copy"
_DEFAULT_BRANCH = "main"
_ICEBERG_SNAPSHOT_ADAPTER = "iceberg_table"
_DELTA_SNAPSHOT_ADAPTER = "delta_table"
_LEGAL_HOLD_TAGS = frozenset({"legal_hold", "legal-retention", "legal_retention"})
_IMMUTABLE_MERGE_TABLES = frozenset({"world.world_facts", "world.world_edges"})
_MERGEABLE_WORLD_TABLES = (
    "world._meta_world_segments",
    "world.world_facts",
    "world.world_edges",
    "world.world_events",
    "world.doc_sources",
    "world.doc_versions",
    "world.doc_fragments",
    "world.claims",
    "world.claim_citations",
    "world.conflict_sets",
    "world.conflict_members",
    "world.trust_assessments",
    "world.quality_reports",
    "world.world_nodes",
)


class WorldSnapshotAdapterError(ValueError):
    """Raised when snapshot storage adapters cannot satisfy one requested operation."""


class WorldBranchMergeConflictError(ValueError):
    """Typed, exportable branch-merge conflict."""

    def __init__(
        self,
        message: str,
        *,
        table_name: str,
        merge_policy: str,
        conflict_keys: Sequence[Sequence[Any]] = (),
        conflict_summary: WorldBranchConflictSummary | None = None,
    ) -> None:
        super().__init__(message)
        self.table_name = table_name
        self.merge_policy = merge_policy
        self.conflict_keys = tuple(tuple(key) for key in conflict_keys)
        self.conflict_summary = conflict_summary or WorldBranchConflictSummary(
            conflict_count=len(self.conflict_keys),
            conflict_types=("row_conflict",),
            table_names=(table_name,),
            unresolved=True,
        )

    def export_payload(self) -> dict[str, Any]:
        """Return a machine-readable conflict payload for reviews and audits."""

        return {
            "table_name": self.table_name,
            "merge_policy": self.merge_policy,
            "conflict_keys": [list(key) for key in self.conflict_keys],
            "conflict_summary": asdict(self.conflict_summary),
        }


def _world_table_sql(table_name: str) -> str:
    return quote_sql_identifier(table_name, what="world table", allow_dotted=True)


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True)
class WorldSnapshotAdapterSpec:
    """Capability contract for one world snapshot storage adapter."""

    adapter_name: str
    format_family: str
    read_mode: str
    supports_snapshot_create: bool
    supports_read_query: bool
    supports_branch_merge: bool
    requires_local_artifact: bool = True
    retention_scope: str = "metadata_and_local_artifact"
    cost_notes: str = ""


_WORLD_SNAPSHOT_ADAPTERS: dict[str, WorldSnapshotAdapterSpec] = {
    _SNAPSHOT_STORAGE_ADAPTER: WorldSnapshotAdapterSpec(
        adapter_name=_SNAPSHOT_STORAGE_ADAPTER,
        format_family="duckdb",
        read_mode="read_only_database_copy",
        supports_snapshot_create=True,
        supports_read_query=True,
        supports_branch_merge=True,
        requires_local_artifact=True,
        retention_scope="metadata_and_local_artifact",
        cost_notes=(
            "Default path copies the file-backed DuckDB database into retained local snapshots."
        ),
    ),
    _ICEBERG_SNAPSHOT_ADAPTER: WorldSnapshotAdapterSpec(
        adapter_name=_ICEBERG_SNAPSHOT_ADAPTER,
        format_family="iceberg",
        read_mode="catalog_or_filesystem_manifest",
        supports_snapshot_create=False,
        supports_read_query=False,
        supports_branch_merge=False,
        requires_local_artifact=False,
        retention_scope="metadata_only",
        cost_notes=(
            "Future adapter path: register externally materialized Iceberg snapshots and query "
            "them through a catalog-aware runtime. Local DuckDB point-in-time queries and "
            "branch merges remain DuckDB-only for now."
        ),
    ),
    _DELTA_SNAPSHOT_ADAPTER: WorldSnapshotAdapterSpec(
        adapter_name=_DELTA_SNAPSHOT_ADAPTER,
        format_family="delta",
        read_mode="delta_log_or_catalog_manifest",
        supports_snapshot_create=False,
        supports_read_query=False,
        supports_branch_merge=False,
        requires_local_artifact=False,
        retention_scope="metadata_only",
        cost_notes=(
            "Future adapter path: register externally materialized Delta snapshots and query "
            "them through a Delta-aware runtime. Local DuckDB point-in-time queries and branch "
            "merges remain DuckDB-only for now."
        ),
    ),
}


@dataclass(frozen=True)
class WorldSnapshotRecord:
    """Metadata for one retained DuckDB world snapshot."""

    snapshot_id: str
    snapshot_path: str
    created_at: str
    branch_name: str = _DEFAULT_BRANCH
    base_snapshot_id: str | None = None
    as_of_tx_time: str | None = None
    as_of_valid_time: str | int | None = None
    merge_policy: str = "fail_on_conflict"
    tags: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    storage_adapter: str = _SNAPSHOT_STORAGE_ADAPTER
    adapter_config: dict[str, Any] = field(default_factory=dict)
    governance: ArtifactGovernanceInfo | None = None


@dataclass(frozen=True)
class WorldBranchConflictSummary:
    """Reviewable summary of merge conflicts on a world branch."""

    conflict_count: int = 0
    conflict_types: tuple[str, ...] = ()
    table_names: tuple[str, ...] = ()
    unresolved: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldBranchGovernanceEvidence:
    """One branch governance event retained with branch metadata."""

    event_kind: str
    actor: str
    reason: str
    created_at: str
    target_branch: str | None = None
    source_branch: str | None = None
    target_snapshot_id: str | None = None
    source_snapshot_id: str | None = None
    merge_strategy: str | None = None
    retained_audit_ref: str | None = None
    conflict_summary: WorldBranchConflictSummary = field(
        default_factory=WorldBranchConflictSummary
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldBranchRecord:
    """Metadata for one logical scenario-analysis branch."""

    branch_name: str
    base_snapshot_id: str
    head_snapshot_id: str
    created_at: str
    merge_policy: str = "fail_on_conflict"
    provenance: dict[str, Any] = field(default_factory=dict)
    branch_kind: str = "observed"
    observed_state: str = "observed"
    scenario_ref: str | None = None
    actor: str = "fabric.system"
    reason: str = "branch_registered"
    retained_audit_ref: str | None = None
    governance_events: tuple[WorldBranchGovernanceEvidence, ...] = ()
    deleted_at: str | None = None


@dataclass(frozen=True)
class WorldSnapshotGCReport:
    """Outcome of snapshot retention and garbage collection."""

    retained_snapshot_ids: tuple[str, ...]
    deleted_snapshot_ids: tuple[str, ...]
    dry_run: bool = False


@dataclass(frozen=True)
class WorldMergeConflictResolution:
    """One deterministic conflict decision applied during branch merge."""

    subject_id: str
    predicate_id: str
    winner_value: str
    loser_values: tuple[str, ...]


@dataclass(frozen=True)
class WorldBranchMergeReport:
    """Outcome of merging one branch head into another branch head."""

    source_branch_name: str
    target_branch_name: str
    source_snapshot_id: str
    target_snapshot_id: str
    merge_policy: str
    merged_snapshot: WorldSnapshotRecord
    resolved_conflicts: tuple[WorldMergeConflictResolution, ...] = ()
    conflict_summary: WorldBranchConflictSummary = field(
        default_factory=WorldBranchConflictSummary
    )
    governance_evidence: WorldBranchGovernanceEvidence | None = None


def list_world_snapshot_adapters() -> tuple[WorldSnapshotAdapterSpec, ...]:
    """List supported and future-path snapshot adapters in deterministic order."""

    return tuple(_WORLD_SNAPSHOT_ADAPTERS[name] for name in sorted(_WORLD_SNAPSHOT_ADAPTERS))


def get_world_snapshot_adapter(adapter_name: str) -> WorldSnapshotAdapterSpec:
    """Resolve one snapshot adapter specification by name."""

    normalized = str(adapter_name or "").strip()
    if not normalized:
        raise WorldSnapshotAdapterError("world snapshot adapter name must not be empty")
    spec = _WORLD_SNAPSHOT_ADAPTERS.get(normalized)
    if spec is None:
        raise WorldSnapshotAdapterError(f"unsupported world snapshot adapter: {normalized!r}")
    return spec


def default_world_snapshot_root(db: SimulationDB | str | Path) -> Path:
    """Return the default sibling directory for DuckDB-native world snapshots."""

    db_path = db.db_path if isinstance(db, SimulationDB) else db
    return Path(f"{Path(db_path)}.world_snapshots")


def create_world_snapshot(
    db: SimulationDB,
    *,
    snapshot_root: Path | None = None,
    snapshot_id: str | None = None,
    branch_name: str = _DEFAULT_BRANCH,
    base_snapshot_id: str | None = None,
    merge_policy: str = "fail_on_conflict",
    provenance: Mapping[str, Any] | None = None,
    tags: Sequence[str] = (),
    as_of_tx_time: str | None = None,
    as_of_valid_time: str | int | None = None,
    storage_adapter: str = _SNAPSHOT_STORAGE_ADAPTER,
    adapter_config: Mapping[str, Any] | None = None,
    classification: DataClassification | str | None = None,
    column_classification: Mapping[str, DataClassification | str] | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> WorldSnapshotRecord:
    """Checkpoint the current DuckDB world into one retained snapshot file."""

    adapter_spec = get_world_snapshot_adapter(storage_adapter)
    if not adapter_spec.supports_snapshot_create:
        raise WorldSnapshotAdapterError(
            f"snapshot adapter {adapter_spec.adapter_name!r} does not support local snapshot "
            f"creation yet. {adapter_spec.cost_notes}"
        )
    db_path = Path(db.db_path)
    if str(db_path) == ":memory:" or not db_path.exists():
        raise ValueError("world snapshots require a file-backed DuckDB database")

    root = Path(snapshot_root) if snapshot_root is not None else default_world_snapshot_root(db)
    _ensure_snapshot_layout(root)
    snapshot_tags = _normalize_snapshot_tags(tags)
    _enforce_legal_hold_encryption_metadata(
        tags=snapshot_tags,
        encrypted_at_rest=encrypted_at_rest,
        field_level_encrypted=field_level_encrypted,
        encryption_key_reference=encryption_key_reference,
    )
    governance_classification = _snapshot_governance_classification(
        classification=classification,
        tags=snapshot_tags,
    )

    snap_id = snapshot_id or _new_snapshot_id()
    created_at = utc_now().isoformat().replace("+00:00", "Z")
    tx_time = as_of_tx_time or _max_world_fact_value(db, "tx_time")
    valid_time = (
        as_of_valid_time
        if as_of_valid_time is not None
        else _max_world_fact_value(db, "valid_time", skip_null=True)
    )
    snapshot_path = _snapshot_file(root, snap_id)

    db.conn.execute("CHECKPOINT")
    shutil.copy2(db_path, snapshot_path)

    record = WorldSnapshotRecord(
        snapshot_id=snap_id,
        snapshot_path=str(snapshot_path),
        created_at=created_at,
        branch_name=branch_name,
        base_snapshot_id=base_snapshot_id,
        as_of_tx_time=tx_time,
        as_of_valid_time=valid_time,
        merge_policy=merge_policy,
        tags=snapshot_tags,
        provenance=dict(provenance or {}),
        storage_adapter=adapter_spec.adapter_name,
        adapter_config=dict(adapter_config or {}),
        governance=resolve_artifact_governance(
            scope=RetentionScope.WORLD_SNAPSHOT,
            classification=governance_classification,
            column_classification=column_classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )
    return register_world_snapshot_record(root, record)


def register_world_snapshot_record(
    snapshot_root: Path,
    record: WorldSnapshotRecord,
) -> WorldSnapshotRecord:
    """Persist snapshot metadata for an already-materialized snapshot artifact."""

    root = Path(snapshot_root)
    _ensure_snapshot_layout(root)
    adapter_spec = get_world_snapshot_adapter(record.storage_adapter)
    snapshot_tags = _normalize_snapshot_tags(record.tags)
    snapshot_path = str(record.snapshot_path).strip()
    if not snapshot_path:
        raise WorldSnapshotAdapterError("world snapshot path must not be empty")
    if adapter_spec.requires_local_artifact:
        artifact_path = Path(snapshot_path)
        if not artifact_path.exists():
            raise FileNotFoundError(f"world snapshot artifact missing: {snapshot_path}")
    governance = record.governance
    if governance is None:
        governance = resolve_artifact_governance(
            scope=RetentionScope.WORLD_SNAPSHOT,
            classification=DataClassification.PUBLIC,
        )
        record = WorldSnapshotRecord(
            snapshot_id=record.snapshot_id,
            snapshot_path=record.snapshot_path,
            created_at=record.created_at,
            branch_name=record.branch_name,
            base_snapshot_id=record.base_snapshot_id,
            as_of_tx_time=record.as_of_tx_time,
            as_of_valid_time=record.as_of_valid_time,
            merge_policy=record.merge_policy,
            tags=snapshot_tags,
            provenance=dict(record.provenance),
            storage_adapter=record.storage_adapter,
            adapter_config=dict(record.adapter_config),
            governance=governance,
        )
    else:
        validate_artifact_governance(governance)
        record = WorldSnapshotRecord(
            snapshot_id=record.snapshot_id,
            snapshot_path=record.snapshot_path,
            created_at=record.created_at,
            branch_name=record.branch_name,
            base_snapshot_id=record.base_snapshot_id,
            as_of_tx_time=record.as_of_tx_time,
            as_of_valid_time=record.as_of_valid_time,
            merge_policy=record.merge_policy,
            tags=snapshot_tags,
            provenance=dict(record.provenance),
            storage_adapter=record.storage_adapter,
            adapter_config=dict(record.adapter_config),
            governance=governance,
        )
    _validate_snapshot_retention_governance(record)

    atomic_write_json(
        _snapshot_meta_file(root, record.snapshot_id), _snapshot_record_payload(record)
    )
    existing_branch = _maybe_get_world_branch(root, record.branch_name)
    event_kind = "branch_created" if existing_branch is None else "branch_head_updated"
    actor = str(record.provenance.get("actor") or getattr(existing_branch, "actor", "fabric.system"))
    reason = str(
        record.provenance.get("reason")
        or ("snapshot_registered" if existing_branch is None else "snapshot_head_registered")
    )
    governance_event = _build_branch_governance_event(
        event_kind=event_kind,
        actor=actor,
        reason=reason,
        target_branch=record.branch_name,
        target_snapshot_id=record.snapshot_id,
        retained_audit_ref=record.provenance.get("retained_audit_ref"),
    )
    _upsert_branch(
        root,
        WorldBranchRecord(
            branch_name=record.branch_name,
            base_snapshot_id=(
                existing_branch.base_snapshot_id
                if existing_branch is not None
                else record.base_snapshot_id or record.snapshot_id
            ),
            head_snapshot_id=record.snapshot_id,
            created_at=(
                existing_branch.created_at if existing_branch is not None else record.created_at
            ),
            merge_policy=record.merge_policy,
            provenance=dict(record.provenance),
            branch_kind=getattr(existing_branch, "branch_kind", "observed"),
            observed_state=getattr(existing_branch, "observed_state", "observed"),
            scenario_ref=getattr(existing_branch, "scenario_ref", None),
            actor=actor,
            reason=reason,
            retained_audit_ref=(
                str(record.provenance.get("retained_audit_ref"))
                if record.provenance.get("retained_audit_ref") is not None
                else getattr(existing_branch, "retained_audit_ref", None)
            ),
            governance_events=(
                (*existing_branch.governance_events, governance_event)
                if existing_branch is not None
                else (governance_event,)
            ),
            deleted_at=getattr(existing_branch, "deleted_at", None),
        ),
    )
    return record


def create_world_branch(
    snapshot_root: Path,
    *,
    branch_name: str,
    base_snapshot_id: str,
    merge_policy: str = "fail_on_conflict",
    provenance: Mapping[str, Any] | None = None,
    actor: str = "fabric.system",
    reason: str = "branch_created",
    retained_audit_ref: str | None = None,
    branch_kind: str = "observed",
    scenario_ref: str | None = None,
    assumption_lineage_refs: Sequence[str] = (),
    model_lineage_refs: Sequence[str] = (),
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> WorldBranchRecord:
    """Register a logical branch that starts from an existing base snapshot."""

    root = Path(snapshot_root)
    _ensure_snapshot_layout(root)
    _load_snapshot(root, base_snapshot_id)
    normalized_kind = _normalize_branch_kind(branch_kind)
    if normalized_kind == "scenario" and not str(scenario_ref or "").strip():
        raise ValueError("scenario branches require scenario_ref")
    if normalized_kind == "scenario" and not any(
        str(ref).strip() for ref in assumption_lineage_refs
    ):
        raise ValueError("scenario branches require assumption lineage")
    if normalized_kind == "scenario" and not str(valid_from or "").strip():
        raise ValueError("scenario branches require valid_from")
    observed_state = "simulated" if normalized_kind == "scenario" else "observed"
    branch_provenance = dict(provenance or {})
    if normalized_kind == "scenario":
        branch_provenance["scenario_contract"] = {
            "scenario_ref": str(scenario_ref),
            "assumption_lineage_refs": [
                str(ref).strip() for ref in assumption_lineage_refs if str(ref).strip()
            ],
            "model_lineage_refs": [
                str(ref).strip() for ref in model_lineage_refs if str(ref).strip()
            ],
            "valid_from": valid_from,
            "valid_to": valid_to,
            "observed_state": observed_state,
            "source_marker": "scenario_state_not_observed_world",
        }
    governance_event = _build_branch_governance_event(
        event_kind="branch_created",
        actor=actor,
        reason=reason,
        target_branch=branch_name,
        target_snapshot_id=base_snapshot_id,
        retained_audit_ref=retained_audit_ref,
        metadata={
            "branch_kind": normalized_kind,
            "scenario_ref": scenario_ref,
        },
    )
    record = WorldBranchRecord(
        branch_name=branch_name,
        base_snapshot_id=base_snapshot_id,
        head_snapshot_id=base_snapshot_id,
        created_at=utc_now().isoformat().replace("+00:00", "Z"),
        merge_policy=merge_policy,
        provenance=branch_provenance,
        branch_kind=normalized_kind,
        observed_state=observed_state,
        scenario_ref=str(scenario_ref) if scenario_ref is not None else None,
        actor=actor,
        reason=reason,
        retained_audit_ref=retained_audit_ref,
        governance_events=(governance_event,),
    )
    _upsert_branch(root, record)
    return record


def list_world_snapshots(snapshot_root: Path) -> list[WorldSnapshotRecord]:
    """Load all retained world snapshots sorted by creation time."""

    root = Path(snapshot_root)
    metadata_dir = _metadata_dir(root)
    if not metadata_dir.exists():
        return []
    snapshots: list[WorldSnapshotRecord] = []
    for path in sorted(metadata_dir.glob("*.json")):
        snapshots.append(_snapshot_from_payload(path.read_text("utf-8")))
    snapshots.sort(key=lambda record: record.created_at)
    return snapshots


def get_world_branch(snapshot_root: Path, branch_name: str) -> WorldBranchRecord:
    """Load one branch metadata record."""

    branch_path = _branch_file(snapshot_root, branch_name)
    if not branch_path.exists():
        raise FileNotFoundError(f"world branch not found: {branch_name}")
    payload = json.loads(branch_path.read_text("utf-8"))
    return _branch_from_payload(payload)


def resolve_world_snapshot(
    snapshot_root: Path,
    *,
    snapshot_id: str | None = None,
    branch_name: str | None = None,
    as_of_tx_time: str | None = None,
    as_of_valid_time: str | int | None = None,
) -> WorldSnapshotRecord:
    """Resolve an exact or point-in-time snapshot for one branch."""

    root = Path(snapshot_root)
    if snapshot_id is not None:
        return _load_snapshot(root, snapshot_id)

    resolved_branch = branch_name or _DEFAULT_BRANCH
    if as_of_tx_time is None and as_of_valid_time is None:
        branch = get_world_branch(root, resolved_branch)
        if branch.deleted_at is not None:
            raise FileNotFoundError(f"world branch was deleted: {resolved_branch}")
        return _load_snapshot(root, branch.head_snapshot_id)

    branch = get_world_branch(root, resolved_branch)
    if branch.deleted_at is not None:
        raise FileNotFoundError(f"world branch was deleted: {resolved_branch}")

    candidates = [
        snapshot
        for snapshot in list_world_snapshots(root)
        if snapshot.branch_name == resolved_branch
    ]
    if as_of_tx_time is not None:
        candidates = [
            snapshot
            for snapshot in candidates
            if snapshot.as_of_tx_time is not None
            and _temporal_lte(snapshot.as_of_tx_time, as_of_tx_time, label="as_of_tx_time")
        ]
    if as_of_valid_time is not None:
        candidates = [
            snapshot
            for snapshot in candidates
            if snapshot.as_of_valid_time is not None
            and _temporal_lte(
                snapshot.as_of_valid_time,
                as_of_valid_time,
                label="as_of_valid_time",
            )
        ]
    if not candidates:
        raise FileNotFoundError(
            f"no retained snapshot matched branch={resolved_branch!r} "
            f"tx_time={as_of_tx_time!r} valid_time={as_of_valid_time!r}"
        )
    candidates.sort(
        key=lambda snapshot: (
            _temporal_sort_key(snapshot.as_of_tx_time or snapshot.created_at),
            _temporal_sort_key(snapshot.as_of_valid_time)
            if snapshot.as_of_valid_time is not None
            else (),
            snapshot.created_at,
        )
    )
    return candidates[-1]


def gc_world_snapshots(
    snapshot_root: Path,
    *,
    keep_latest: int = 0,
    keep_since: str | None = None,
    retain_tags: Sequence[str] = ("audit", "legal_hold", "legal-retention"),
    dry_run: bool = False,
) -> WorldSnapshotGCReport:
    """Delete expired snapshots while retaining branch heads, audit, and legal-hold snapshots."""

    root = Path(snapshot_root)
    snapshots = list_world_snapshots(root)
    retained_tags = {str(tag).strip() for tag in retain_tags if str(tag).strip()}
    keep_since_dt = parse_datetime_utc(keep_since, what="keep_since") if keep_since else None

    protected_ids = {
        branch.head_snapshot_id for branch in _list_branches(root) if branch.deleted_at is None
    }
    protected_ids.update(
        snapshot.snapshot_id
        for snapshot in snapshots
        if classify_snapshot_retention(tags=snapshot.tags)
        in {SnapshotRetentionClass.AUDIT_TAGGED, SnapshotRetentionClass.LEGAL_HOLD}
    )
    if keep_latest > 0:
        protected_ids.update(snapshot.snapshot_id for snapshot in snapshots[-keep_latest:])
    if retained_tags:
        protected_ids.update(
            snapshot.snapshot_id
            for snapshot in snapshots
            if retained_tags.intersection(snapshot.tags)
        )
    if keep_since_dt is not None:
        protected_ids.update(
            snapshot.snapshot_id
            for snapshot in snapshots
            if parse_datetime_utc(snapshot.created_at, what="snapshot created_at") >= keep_since_dt
        )

    deleted_ids: list[str] = []
    retained_ids: list[str] = []
    for snapshot in snapshots:
        if snapshot.snapshot_id in protected_ids:
            retained_ids.append(snapshot.snapshot_id)
            continue
        deleted_ids.append(snapshot.snapshot_id)
        if dry_run:
            continue
        for path in _snapshot_artifact_paths(snapshot):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        meta_path = _snapshot_meta_file(root, snapshot.snapshot_id)
        if meta_path.exists():
            meta_path.unlink()

    if not dry_run:
        retained_ids = [snapshot.snapshot_id for snapshot in list_world_snapshots(root)]
    return WorldSnapshotGCReport(
        retained_snapshot_ids=tuple(retained_ids),
        deleted_snapshot_ids=tuple(deleted_ids),
        dry_run=dry_run,
    )


def merge_world_branch(
    snapshot_root: Path,
    *,
    branch_name: str,
    target_branch_name: str = _DEFAULT_BRANCH,
    merge_policy: str | None = None,
    provenance: Mapping[str, Any] | None = None,
    tags: Sequence[str] = (),
    actor: str = "fabric.system",
    reason: str = "branch_merge",
    retained_audit_ref: str | None = None,
) -> WorldBranchMergeReport:
    """Merge one branch head into another with explicit conflict policy."""

    root = Path(snapshot_root)
    _ensure_snapshot_layout(root)

    source_branch = get_world_branch(root, branch_name)
    target_branch = get_world_branch(root, target_branch_name)
    resolved_policy = str(
        merge_policy
        or source_branch.merge_policy
        or target_branch.merge_policy
        or "fail_on_conflict"
    )
    if resolved_policy not in {"fail_on_conflict", "branch_wins", "target_wins"}:
        raise ValueError(f"unsupported merge_policy: {resolved_policy!r}")
    if source_branch.deleted_at is not None:
        raise FileNotFoundError(f"world branch was deleted: {branch_name}")
    if target_branch.deleted_at is not None:
        raise FileNotFoundError(f"world branch was deleted: {target_branch_name}")

    source_snapshot = _load_snapshot(root, source_branch.head_snapshot_id)
    target_snapshot = _load_snapshot(root, target_branch.head_snapshot_id)
    source_adapter = get_world_snapshot_adapter(source_snapshot.storage_adapter)
    target_adapter = get_world_snapshot_adapter(target_snapshot.storage_adapter)
    if not source_adapter.supports_branch_merge or not target_adapter.supports_branch_merge:
        raise WorldSnapshotAdapterError(
            "branch merge currently requires merge-capable snapshot adapters. "
            f"source={source_adapter.adapter_name!r}, target={target_adapter.adapter_name!r}. "
            f"{source_adapter.cost_notes or target_adapter.cost_notes}"
        )
    temp_db_path = root / f".merge_{uuid.uuid4().hex}.duckdb"
    shutil.copy2(target_snapshot.snapshot_path, temp_db_path)

    conflict_resolutions: list[WorldMergeConflictResolution] = []
    merged_snapshot: WorldSnapshotRecord | None = None
    merge_governance: WorldBranchGovernanceEvidence | None = None
    try:
        with (
            SimulationDB(db_path=str(temp_db_path)) as merged_db,
            SimulationDB(db_path=str(source_snapshot.snapshot_path)) as source_db,
        ):
            merged_db.conn.execute("BEGIN")
            try:
                source_tables = set(_list_world_tables(source_db))
                target_tables = set(_list_world_tables(merged_db))
                for table_name in _MERGEABLE_WORLD_TABLES:
                    if table_name not in source_tables or table_name not in target_tables:
                        continue
                    table_sql = _world_table_sql(table_name)
                    target_frame = merged_db.conn.execute(f"SELECT * FROM {table_sql}").fetchdf()
                    source_frame = source_db.conn.execute(f"SELECT * FROM {table_sql}").fetchdf()
                    primary_keys = _primary_key_columns(merged_db, table_name)
                    if not primary_keys:
                        continue
                    merged_frame = _merge_table_frames(
                        table_name=table_name,
                        target_frame=target_frame,
                        source_frame=source_frame,
                        primary_keys=primary_keys,
                        merge_policy=resolved_policy,
                    )
                    if table_name == "world.world_facts":
                        merged_frame, resolutions = _resolve_world_kind_fact_conflicts(
                            merged_frame,
                            target_frame=target_frame,
                            source_frame=source_frame,
                            merge_policy=resolved_policy,
                        )
                        conflict_resolutions.extend(resolutions)
                    _replace_table_contents(merged_db, table_name, merged_frame)

                _refresh_merged_world_nodes(
                    merged_db,
                    source_db=source_db,
                )
                merged_db.conn.execute("COMMIT")
            except Exception:
                merged_db.conn.execute("ROLLBACK")
                raise

            conflict_summary = _conflict_summary_from_resolutions(conflict_resolutions)
            merge_governance = _build_branch_governance_event(
                event_kind="branch_merged",
                actor=actor,
                reason=reason,
                target_branch=target_branch_name,
                source_branch=branch_name,
                target_snapshot_id=target_snapshot.snapshot_id,
                source_snapshot_id=source_snapshot.snapshot_id,
                merge_strategy=resolved_policy,
                retained_audit_ref=retained_audit_ref,
                conflict_summary=conflict_summary,
            )
            merged_snapshot = create_world_snapshot(
                merged_db,
                snapshot_root=root,
                branch_name=target_branch_name,
                base_snapshot_id=target_snapshot.snapshot_id,
                merge_policy=resolved_policy,
                provenance={
                    "merge": {
                        "source_branch": branch_name,
                        "target_branch": target_branch_name,
                        "source_snapshot_id": source_snapshot.snapshot_id,
                        "target_snapshot_id": target_snapshot.snapshot_id,
                        "resolved_conflicts": len(conflict_resolutions),
                        "conflict_summary": asdict(conflict_summary),
                        "governance": asdict(merge_governance),
                    },
                    "actor": actor,
                    "reason": reason,
                    "retained_audit_ref": retained_audit_ref,
                    **dict(provenance or {}),
                },
                tags=tags,
            )
            _append_branch_governance_event(root, target_branch_name, merge_governance)
    finally:
        if temp_db_path.exists():
            temp_db_path.unlink()

    if merged_snapshot is None:
        raise RuntimeError("world branch merge completed without a merged snapshot")
    return WorldBranchMergeReport(
        source_branch_name=branch_name,
        target_branch_name=target_branch_name,
        source_snapshot_id=source_snapshot.snapshot_id,
        target_snapshot_id=target_snapshot.snapshot_id,
        merge_policy=resolved_policy,
        merged_snapshot=merged_snapshot,
        resolved_conflicts=tuple(conflict_resolutions),
        conflict_summary=_conflict_summary_from_resolutions(conflict_resolutions),
        governance_evidence=merge_governance,
    )


def update_world_branch_head(
    snapshot_root: Path,
    *,
    branch_name: str,
    head_snapshot_id: str,
    actor: str,
    reason: str,
    retained_audit_ref: str | None = None,
) -> WorldBranchRecord:
    """Move a branch head with explicit governance evidence."""

    root = Path(snapshot_root)
    _ensure_snapshot_layout(root)
    _load_snapshot(root, head_snapshot_id)
    branch = get_world_branch(root, branch_name)
    if branch.deleted_at is not None:
        raise FileNotFoundError(f"world branch was deleted: {branch_name}")
    event = _build_branch_governance_event(
        event_kind="branch_head_updated",
        actor=actor,
        reason=reason,
        target_branch=branch_name,
        target_snapshot_id=head_snapshot_id,
        retained_audit_ref=retained_audit_ref,
    )
    updated = WorldBranchRecord(
        branch_name=branch.branch_name,
        base_snapshot_id=branch.base_snapshot_id,
        head_snapshot_id=head_snapshot_id,
        created_at=branch.created_at,
        merge_policy=branch.merge_policy,
        provenance=dict(branch.provenance),
        branch_kind=branch.branch_kind,
        observed_state=branch.observed_state,
        scenario_ref=branch.scenario_ref,
        actor=actor,
        reason=reason,
        retained_audit_ref=retained_audit_ref or branch.retained_audit_ref,
        governance_events=(*branch.governance_events, event),
        deleted_at=branch.deleted_at,
    )
    _upsert_branch(root, updated)
    return updated


def delete_world_branch(
    snapshot_root: Path,
    *,
    branch_name: str,
    actor: str,
    reason: str,
    retained_audit_ref: str | None = None,
) -> WorldBranchRecord:
    """Mark a branch deleted while retaining exportable governance evidence."""

    root = Path(snapshot_root)
    branch = get_world_branch(root, branch_name)
    deleted_at = utc_now().isoformat().replace("+00:00", "Z")
    event = _build_branch_governance_event(
        event_kind="branch_deleted",
        actor=actor,
        reason=reason,
        target_branch=branch_name,
        target_snapshot_id=branch.head_snapshot_id,
        retained_audit_ref=retained_audit_ref,
    )
    updated = WorldBranchRecord(
        branch_name=branch.branch_name,
        base_snapshot_id=branch.base_snapshot_id,
        head_snapshot_id=branch.head_snapshot_id,
        created_at=branch.created_at,
        merge_policy=branch.merge_policy,
        provenance=dict(branch.provenance),
        branch_kind=branch.branch_kind,
        observed_state=branch.observed_state,
        scenario_ref=branch.scenario_ref,
        actor=actor,
        reason=reason,
        retained_audit_ref=retained_audit_ref or branch.retained_audit_ref,
        governance_events=(*branch.governance_events, event),
        deleted_at=deleted_at,
    )
    _upsert_branch(root, updated)
    return updated


def export_world_branch_governance(
    snapshot_root: Path,
    branch_name: str,
) -> dict[str, Any]:
    """Export branch governance evidence as stable JSON-ready data."""

    branch = get_world_branch(Path(snapshot_root), branch_name)
    return asdict(branch)


def _new_snapshot_id() -> str:
    timestamp = utc_now(drop_microseconds=True).strftime("%Y%m%dT%H%M%SZ")
    return f"world_snapshot_{timestamp}_{uuid.uuid4().hex[:8]}"


def _ensure_snapshot_layout(snapshot_root: Path) -> None:
    _snapshots_dir(snapshot_root).mkdir(parents=True, exist_ok=True)
    _metadata_dir(snapshot_root).mkdir(parents=True, exist_ok=True)
    _branches_dir(snapshot_root).mkdir(parents=True, exist_ok=True)


def _snapshots_dir(snapshot_root: Path) -> Path:
    return Path(snapshot_root) / "snapshots"


def _metadata_dir(snapshot_root: Path) -> Path:
    return Path(snapshot_root) / "metadata"


def _branches_dir(snapshot_root: Path) -> Path:
    return Path(snapshot_root) / "branches"


def _snapshot_file(snapshot_root: Path, snapshot_id: str) -> Path:
    return _snapshots_dir(snapshot_root) / f"{snapshot_id}.duckdb"


def _snapshot_meta_file(snapshot_root: Path, snapshot_id: str) -> Path:
    return _metadata_dir(snapshot_root) / f"{snapshot_id}.json"


def _branch_file(snapshot_root: Path, branch_name: str) -> Path:
    return _branches_dir(snapshot_root) / f"{branch_name}.json"


def _snapshot_record_payload(record: WorldSnapshotRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["tags"] = list(record.tags)
    payload["governance"] = (
        record.governance.model_dump(mode="json", exclude_none=True)
        if record.governance is not None
        else None
    )
    return payload


def _normalize_snapshot_tags(tags: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(tag).strip() for tag in tags if str(tag).strip()))


def _enforce_legal_hold_encryption_metadata(
    *,
    tags: Sequence[str],
    encrypted_at_rest: bool,
    field_level_encrypted: bool,
    encryption_key_reference: str | None,
) -> None:
    retention_class = classify_snapshot_retention(tags=tuple(tags))
    if retention_class != SnapshotRetentionClass.LEGAL_HOLD:
        return
    if not (encrypted_at_rest or field_level_encrypted):
        raise ArtifactGovernanceError(
            "world_snapshot legal retention requires verified encryption metadata"
        )
    if not str(encryption_key_reference or "").strip():
        raise ArtifactGovernanceError(
            "world_snapshot legal retention requires encryption_key_reference"
        )


def _validate_snapshot_retention_governance(record: WorldSnapshotRecord) -> None:
    retention_class = classify_snapshot_retention(tags=record.tags)
    if retention_class != SnapshotRetentionClass.LEGAL_HOLD:
        return
    governance = record.governance
    encryption = governance.encryption if governance is not None else None
    if (
        encryption is None
        or not encryption.enforced
        or not encryption.verified
        or not str(encryption.key_reference or "").strip()
    ):
        raise ArtifactGovernanceError(
            "world_snapshot legal retention requires verified encryption metadata"
        )


def _snapshot_governance_classification(
    *,
    classification: DataClassification | str | None,
    tags: Sequence[str],
) -> DataClassification | str | None:
    if classify_snapshot_retention(tags=tuple(tags)) != SnapshotRetentionClass.LEGAL_HOLD:
        return classification
    if classification is None:
        return DataClassification.INTERNAL
    try:
        resolved = DataClassification(str(classification).strip().lower())
    except ValueError:
        return classification
    if resolved == DataClassification.PUBLIC:
        return DataClassification.INTERNAL
    return classification


def _snapshot_from_payload(payload: str) -> WorldSnapshotRecord:
    raw = json.loads(payload)
    return WorldSnapshotRecord(
        snapshot_id=str(raw["snapshot_id"]),
        snapshot_path=str(raw["snapshot_path"]),
        created_at=str(raw["created_at"]),
        branch_name=str(raw.get("branch_name", _DEFAULT_BRANCH)),
        base_snapshot_id=raw.get("base_snapshot_id"),
        as_of_tx_time=raw.get("as_of_tx_time"),
        as_of_valid_time=raw.get("as_of_valid_time"),
        merge_policy=str(raw.get("merge_policy", "fail_on_conflict")),
        tags=tuple(str(tag) for tag in raw.get("tags", [])),
        provenance=dict(raw.get("provenance", {})),
        storage_adapter=str(raw.get("storage_adapter", _SNAPSHOT_STORAGE_ADAPTER)),
        adapter_config=dict(raw.get("adapter_config", {})),
        governance=(
            ArtifactGovernanceInfo.model_validate(raw["governance"])
            if raw.get("governance") is not None
            else None
        ),
    )


def _branch_from_payload(payload: Mapping[str, Any]) -> WorldBranchRecord:
    governance_events = tuple(
        _branch_governance_from_payload(item)
        for item in payload.get("governance_events", ())
        if isinstance(item, Mapping)
    )
    return WorldBranchRecord(
        branch_name=str(payload["branch_name"]),
        base_snapshot_id=str(payload["base_snapshot_id"]),
        head_snapshot_id=str(payload["head_snapshot_id"]),
        created_at=str(payload["created_at"]),
        merge_policy=str(payload.get("merge_policy", "fail_on_conflict")),
        provenance=dict(payload.get("provenance", {})),
        branch_kind=str(payload.get("branch_kind", "observed")),
        observed_state=str(payload.get("observed_state", "observed")),
        scenario_ref=payload.get("scenario_ref"),
        actor=str(payload.get("actor", "fabric.system")),
        reason=str(payload.get("reason", "branch_registered")),
        retained_audit_ref=payload.get("retained_audit_ref"),
        governance_events=governance_events,
        deleted_at=payload.get("deleted_at"),
    )


def _branch_governance_from_payload(payload: Mapping[str, Any]) -> WorldBranchGovernanceEvidence:
    return WorldBranchGovernanceEvidence(
        event_kind=str(payload["event_kind"]),
        actor=str(payload["actor"]),
        reason=str(payload["reason"]),
        created_at=str(payload.get("created_at") or utc_now().isoformat().replace("+00:00", "Z")),
        target_branch=payload.get("target_branch"),
        source_branch=payload.get("source_branch"),
        target_snapshot_id=payload.get("target_snapshot_id"),
        source_snapshot_id=payload.get("source_snapshot_id"),
        merge_strategy=payload.get("merge_strategy"),
        retained_audit_ref=payload.get("retained_audit_ref"),
        conflict_summary=_conflict_summary_from_payload(payload.get("conflict_summary", {})),
        metadata=dict(payload.get("metadata", {})),
    )


def _conflict_summary_from_payload(payload: object) -> WorldBranchConflictSummary:
    if not isinstance(payload, Mapping):
        return WorldBranchConflictSummary()
    return WorldBranchConflictSummary(
        conflict_count=int(payload.get("conflict_count", 0)),
        conflict_types=tuple(str(item) for item in payload.get("conflict_types", ())),
        table_names=tuple(str(item) for item in payload.get("table_names", ())),
        unresolved=bool(payload.get("unresolved", False)),
        notes=tuple(str(item) for item in payload.get("notes", ())),
    )


def _build_branch_governance_event(
    *,
    event_kind: str,
    actor: str,
    reason: str,
    target_branch: str | None = None,
    source_branch: str | None = None,
    target_snapshot_id: str | None = None,
    source_snapshot_id: str | None = None,
    merge_strategy: str | None = None,
    retained_audit_ref: object = None,
    conflict_summary: WorldBranchConflictSummary | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> WorldBranchGovernanceEvidence:
    if not str(actor or "").strip():
        raise ValueError("branch governance evidence requires actor")
    if not str(reason or "").strip():
        raise ValueError("branch governance evidence requires reason")
    return WorldBranchGovernanceEvidence(
        event_kind=str(event_kind),
        actor=str(actor).strip(),
        reason=str(reason).strip(),
        created_at=utc_now().isoformat().replace("+00:00", "Z"),
        target_branch=target_branch,
        source_branch=source_branch,
        target_snapshot_id=target_snapshot_id,
        source_snapshot_id=source_snapshot_id,
        merge_strategy=merge_strategy,
        retained_audit_ref=str(retained_audit_ref) if retained_audit_ref is not None else None,
        conflict_summary=conflict_summary or WorldBranchConflictSummary(),
        metadata=dict(metadata or {}),
    )


def _append_branch_governance_event(
    snapshot_root: Path,
    branch_name: str,
    event: WorldBranchGovernanceEvidence,
) -> WorldBranchRecord:
    branch = get_world_branch(snapshot_root, branch_name)
    updated = WorldBranchRecord(
        branch_name=branch.branch_name,
        base_snapshot_id=branch.base_snapshot_id,
        head_snapshot_id=branch.head_snapshot_id,
        created_at=branch.created_at,
        merge_policy=branch.merge_policy,
        provenance=dict(branch.provenance),
        branch_kind=branch.branch_kind,
        observed_state=branch.observed_state,
        scenario_ref=branch.scenario_ref,
        actor=event.actor,
        reason=event.reason,
        retained_audit_ref=event.retained_audit_ref or branch.retained_audit_ref,
        governance_events=(*branch.governance_events, event),
        deleted_at=branch.deleted_at,
    )
    _upsert_branch(snapshot_root, updated)
    return updated


def _maybe_get_world_branch(snapshot_root: Path, branch_name: str) -> WorldBranchRecord | None:
    try:
        return get_world_branch(snapshot_root, branch_name)
    except FileNotFoundError:
        return None


def _normalize_branch_kind(value: str) -> str:
    normalized = str(value or "observed").strip().lower()
    if normalized not in {"observed", "scenario"}:
        raise ValueError("world branch kind must be 'observed' or 'scenario'")
    return normalized


def _load_snapshot(snapshot_root: Path, snapshot_id: str) -> WorldSnapshotRecord:
    meta_path = _snapshot_meta_file(snapshot_root, snapshot_id)
    if not meta_path.exists():
        raise FileNotFoundError(f"world snapshot not found: {snapshot_id}")
    record = _snapshot_from_payload(meta_path.read_text("utf-8"))
    adapter_spec = get_world_snapshot_adapter(record.storage_adapter)
    if adapter_spec.requires_local_artifact and not Path(record.snapshot_path).exists():
        raise FileNotFoundError(f"world snapshot file missing: {record.snapshot_path}")
    return record


def _snapshot_artifact_paths(record: WorldSnapshotRecord) -> tuple[Path, ...]:
    adapter_spec = get_world_snapshot_adapter(record.storage_adapter)
    if adapter_spec.retention_scope != "metadata_and_local_artifact":
        return ()
    snapshot_path = str(record.snapshot_path).strip()
    if not snapshot_path or _looks_like_external_uri(snapshot_path):
        return ()
    return (Path(snapshot_path),)


def _looks_like_external_uri(path: str) -> bool:
    return "://" in path and not path.startswith("file://")


def _upsert_branch(snapshot_root: Path, record: WorldBranchRecord) -> None:
    atomic_write_json(_branch_file(snapshot_root, record.branch_name), asdict(record))


def _list_branches(snapshot_root: Path) -> list[WorldBranchRecord]:
    branch_dir = _branches_dir(snapshot_root)
    if not branch_dir.exists():
        return []
    branches: list[WorldBranchRecord] = []
    for path in sorted(branch_dir.glob("*.json")):
        try:
            branches.append(get_world_branch(snapshot_root, path.stem))
        except FileNotFoundError:
            continue
    return branches


def _list_world_tables(db: SimulationDB) -> tuple[str, ...]:
    rows = db.conn.execute(
        """
        SELECT table_schema || '.' || table_name
        FROM information_schema.tables
        WHERE table_schema = 'world'
        ORDER BY table_name
        """
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _primary_key_columns(db: SimulationDB, table_name: str) -> tuple[str, ...]:
    _world_table_sql(table_name)
    rows = db.conn.execute(f"PRAGMA table_info({_sql_string_literal(table_name)})").fetchall()
    primary_keys = [(int(row[5]), str(row[1])) for row in rows if int(row[5]) > 0]
    primary_keys.sort(key=lambda item: item[0])
    return tuple(name for _, name in primary_keys)


def _merge_table_frames(
    *,
    table_name: str,
    target_frame: pd.DataFrame,
    source_frame: pd.DataFrame,
    primary_keys: Sequence[str],
    merge_policy: str,
) -> pd.DataFrame:
    if source_frame.empty:
        return target_frame
    if target_frame.empty:
        return source_frame

    pk_columns = list(primary_keys)
    target_rows = {_row_key(row, pk_columns): row for row in target_frame.to_dict(orient="records")}
    source_rows = {_row_key(row, pk_columns): row for row in source_frame.to_dict(orient="records")}
    merged_rows = dict(target_rows)
    conflicts: list[tuple[tuple[Any, ...], dict[str, Any], dict[str, Any]]] = []

    for key, source_row in source_rows.items():
        target_row = target_rows.get(key)
        if target_row is None:
            merged_rows[key] = source_row
            continue
        if _rows_equivalent(target_row, source_row):
            continue
        conflicts.append((key, target_row, source_row))

    if conflicts and table_name in _IMMUTABLE_MERGE_TABLES:
        keys = [key for key, _, _ in conflicts]
        raise WorldBranchMergeConflictError(
            f"immutable merge conflict in {table_name} for keys: "
            + ", ".join(repr(key) for key in keys),
            table_name=table_name,
            merge_policy=merge_policy,
            conflict_keys=keys,
            conflict_summary=WorldBranchConflictSummary(
                conflict_count=len(keys),
                conflict_types=("immutable_row_conflict",),
                table_names=(table_name,),
                unresolved=True,
            ),
        )
    if conflicts and merge_policy == "fail_on_conflict":
        keys = [key for key, _, _ in conflicts]
        raise WorldBranchMergeConflictError(
            f"merge conflict in {table_name} for keys: "
            + ", ".join(repr(key) for key in keys),
            table_name=table_name,
            merge_policy=merge_policy,
            conflict_keys=keys,
            conflict_summary=WorldBranchConflictSummary(
                conflict_count=len(keys),
                conflict_types=("row_conflict",),
                table_names=(table_name,),
                unresolved=True,
            ),
        )
    if conflicts and merge_policy == "branch_wins":
        for key, _, source_row in conflicts:
            merged_rows[key] = source_row

    ordered_columns = list(target_frame.columns)
    merged_frame = pd.DataFrame(
        [merged_rows[key] for key in sorted(merged_rows)],
        columns=ordered_columns,
    )
    return merged_frame


def _row_key(row: Mapping[str, Any], primary_keys: Sequence[str]) -> tuple[Any, ...]:
    return tuple(row[column] for column in primary_keys)


def _rows_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if left.keys() != right.keys():
        return False
    return all(_normalize_row_value(left[key]) == _normalize_row_value(right[key]) for key in left)


def _normalize_row_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _resolve_world_kind_fact_conflicts(
    merged_frame: pd.DataFrame,
    *,
    target_frame: pd.DataFrame,
    source_frame: pd.DataFrame,
    merge_policy: str,
) -> tuple[pd.DataFrame, list[WorldMergeConflictResolution]]:
    kind_rows = merged_frame[
        (merged_frame["predicate_id"] == WORLD_KIND) & merged_frame["object_value"].notna()
    ]
    if kind_rows.empty:
        return merged_frame, []

    resolutions: list[WorldMergeConflictResolution] = []
    keep_fact_ids = set(merged_frame["fact_id"].tolist())
    for subject_id, group in kind_rows.groupby("subject_id", sort=True):
        values = sorted(
            {str(value) for value in group["object_value"].tolist() if value is not None}
        )
        if len(values) <= 1:
            continue
        if merge_policy == "fail_on_conflict":
            raise WorldBranchMergeConflictError(
                f"world.kind conflict for subject_id={subject_id!r}: {', '.join(values)}",
                table_name="world.world_facts",
                merge_policy=merge_policy,
                conflict_keys=((subject_id, WORLD_KIND),),
                conflict_summary=WorldBranchConflictSummary(
                    conflict_count=1,
                    conflict_types=("world_kind",),
                    table_names=("world.world_facts",),
                    unresolved=True,
                    notes=(f"values={','.join(values)}",),
                ),
            )
        winner_value = _winner_world_kind_value(
            subject_id=str(subject_id),
            target_frame=target_frame,
            source_frame=source_frame,
            merge_policy=merge_policy,
        )
        for row in group.to_dict(orient="records"):
            if str(row["object_value"]) != winner_value:
                keep_fact_ids.discard(str(row["fact_id"]))
        resolutions.append(
            WorldMergeConflictResolution(
                subject_id=str(subject_id),
                predicate_id=WORLD_KIND,
                winner_value=winner_value,
                loser_values=tuple(value for value in values if value != winner_value),
            )
        )

    if not resolutions:
        return merged_frame, []
    filtered = merged_frame[merged_frame["fact_id"].astype(str).isin(keep_fact_ids)].reset_index(
        drop=True
    )
    return filtered, resolutions


def _conflict_summary_from_resolutions(
    resolutions: Sequence[WorldMergeConflictResolution],
) -> WorldBranchConflictSummary:
    if not resolutions:
        return WorldBranchConflictSummary()
    return WorldBranchConflictSummary(
        conflict_count=len(resolutions),
        conflict_types=("world_kind",),
        table_names=("world.world_facts",),
        unresolved=False,
        notes=tuple(
            f"{resolution.subject_id}:{resolution.predicate_id}"
            for resolution in resolutions
        ),
    )


def _winner_world_kind_value(
    *,
    subject_id: str,
    target_frame: pd.DataFrame,
    source_frame: pd.DataFrame,
    merge_policy: str,
) -> str:
    preferred = source_frame if merge_policy == "branch_wins" else target_frame
    fallback = target_frame if merge_policy == "branch_wins" else source_frame
    winner = _latest_kind_value_for_subject(preferred, subject_id)
    if winner is not None:
        return winner
    fallback_winner = _latest_kind_value_for_subject(fallback, subject_id)
    if fallback_winner is None:
        raise ValueError(f"unable to determine winner world.kind value for {subject_id}")
    return fallback_winner


def _latest_kind_value_for_subject(frame: pd.DataFrame, subject_id: str) -> str | None:
    if frame.empty:
        return None
    subset = frame[
        (frame["predicate_id"] == WORLD_KIND)
        & (frame["subject_id"] == subject_id)
        & frame["object_value"].notna()
    ]
    if subset.empty:
        return None
    ordered = subset.sort_values(by=["tx_time", "fact_id"], ascending=[False, False])
    value = ordered.iloc[0]["object_value"]
    return None if pd.isna(value) else str(value)


def _replace_table_contents(
    db: SimulationDB,
    table_name: str,
    frame: pd.DataFrame,
) -> None:
    table_sql = _world_table_sql(table_name)
    db.conn.execute(f"DELETE FROM {table_sql}")
    if frame.empty:
        return
    temp_name = f"merge_{table_name.split('.')[-1]}_{uuid.uuid4().hex[:8]}"
    db.conn.register(temp_name, frame)
    try:
        temp_sql = quote_sql_identifier(temp_name, what="temporary merge table")
        columns = ", ".join(
            quote_sql_identifier(str(column), what="merge table column") for column in frame.columns
        )
        db.conn.execute(f"INSERT INTO {table_sql} ({columns}) SELECT {columns} FROM {temp_sql}")
    finally:
        db.conn.unregister(temp_name)


def _refresh_merged_world_nodes(
    db: SimulationDB,
    *,
    source_db: SimulationDB,
) -> None:
    touched_rows = source_db.conn.execute(
        """
        SELECT DISTINCT node_id
        FROM (
            SELECT subject_id AS node_id FROM world.world_facts
            UNION ALL
            SELECT src_id AS node_id FROM world.world_edges
            UNION ALL
            SELECT dst_id AS node_id FROM world.world_edges
            UNION ALL
            SELECT node_id FROM world.world_nodes
        )
        WHERE node_id IS NOT NULL
        """
    ).fetchall()
    touched_ids = sorted(str(row[0]) for row in touched_rows if row and row[0] is not None)
    if not touched_ids:
        return
    touched_frame = pd.DataFrame({"node_id": touched_ids})
    temp_name = f"merge_touched_nodes_{uuid.uuid4().hex[:8]}"
    db.conn.register(temp_name, touched_frame)
    try:
        db.conn.execute(sql_insert_missing_nodes(temp_name))
        db.conn.execute(sql_update_world_nodes(temp_name))
    finally:
        db.conn.unregister(temp_name)


def _max_world_fact_value(
    db: SimulationDB,
    column_name: str,
    *,
    skip_null: bool = False,
) -> str | None:
    column_sql = quote_sql_identifier(column_name, what="world fact column")
    where = f"WHERE {column_sql} IS NOT NULL" if skip_null else ""
    row = db.conn.execute(
        f"SELECT MAX({column_sql}) FROM {_world_table_sql('world.world_facts')} {where}"
    ).fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def _temporal_sort_key(value: str | int | None) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (int, float)):
        return (float(value),)
    return (parse_datetime_utc(value, what="snapshot temporal key"),)


def _temporal_lte(candidate: str | int, target: str | int, *, label: str) -> bool:
    if isinstance(candidate, (int, float)) or isinstance(target, (int, float)):
        return float(candidate) <= float(target)
    return parse_datetime_utc(candidate, what=label) <= parse_datetime_utc(target, what=label)


__all__ = [
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
]
