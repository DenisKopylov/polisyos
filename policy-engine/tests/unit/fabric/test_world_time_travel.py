from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.security import (
    ArtifactGovernanceError,
    DataClassification,
    RetentionScope,
    resolve_artifact_governance,
)
from polisyos.fabric.world.materialize import ensure_world_schema
from polisyos.fabric.world.materialize.sql import sql_update_world_nodes
from polisyos.fabric.world.query import WorldQueryError, query_world_table
from polisyos.fabric.world.store import (
    WorldBranchMergeConflictError,
    WorldSnapshotAdapterError,
    WorldSnapshotRecord,
    create_world_branch,
    create_world_snapshot,
    gc_world_snapshots,
    list_world_snapshot_adapters,
    merge_world_branch,
    register_world_snapshot_record,
    resolve_world_snapshot,
)
from polisyos.runtime.http.services.temporal import TemporalService


def _insert_node_attr_fact(
    db: SimulationDB,
    *,
    fact_id: str,
    predicate_id: str,
    object_value: str | None,
    tx_time: str,
    valid_time: str | None,
    segment_id: str,
) -> None:
    db.conn.execute(
        """
        INSERT INTO world.world_facts (
            fact_id,
            schema_version,
            subject_id,
            predicate_id,
            object_value,
            target_id,
            valid_time,
            tx_time,
            provenance_json,
            trust_json,
            legal_json,
            segment_id
        )
        VALUES (?, '1.0', 'node.time', ?, ?, NULL, ?, ?, '{}', NULL, NULL, ?)
        """,
        [fact_id, predicate_id, object_value, valid_time, tx_time, segment_id],
    )


def _refresh_current_world_node(db: SimulationDB) -> None:
    db.conn.execute(
        """
        INSERT INTO world.world_nodes (node_id, kind)
        SELECT 'node.time', 'claim'
        WHERE NOT EXISTS (
            SELECT 1 FROM world.world_nodes WHERE node_id = 'node.time'
        )
        """
    )
    db.conn.register("node_time_touch", pd.DataFrame({"node_id": ["node.time"]}))
    try:
        db.conn.execute(sql_update_world_nodes("node_time_touch"))
    finally:
        db.conn.unregister("node_time_touch")


def test_query_world_nodes_supports_bitemporal_as_of_without_rebuild(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    ensure_world_schema(db)

    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("1" * 64),
        predicate_id="world.kind",
        object_value="claim",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-01-01T00:00:00Z",
        segment_id="seg.kind",
    )
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("2" * 64),
        predicate_id="world.label",
        object_value="Late arrival",
        valid_time="2025-01-15T00:00:00Z",
        tx_time="2026-02-01T00:00:00Z",
        segment_id="seg.late",
    )
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("3" * 64),
        predicate_id="world.label",
        object_value="Corrected label",
        valid_time="2025-01-15T00:00:00Z",
        tx_time="2026-03-01T00:00:00Z",
        segment_id="seg.corrected",
    )
    _refresh_current_world_node(db)

    before_arrival = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        as_of_tx_time="2026-01-20T00:00:00Z",
        as_of_valid_time="2025-02-01T00:00:00Z",
    )
    assert before_arrival.empty

    after_arrival = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        as_of_tx_time="2026-02-10T00:00:00Z",
        as_of_valid_time="2025-02-01T00:00:00Z",
    )
    assert after_arrival.iloc[0]["label"] == "Late arrival"

    after_correction = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        as_of_tx_time="2026-03-10T00:00:00Z",
        as_of_valid_time="2025-02-01T00:00:00Z",
    )
    assert after_correction.iloc[0]["label"] == "Corrected label"

    temporal_scope = TemporalService().resolve_scope(
        valid_at=pd.Timestamp("2025-02-01T00:00:00Z").to_pydatetime(),
        tx_at=pd.Timestamp("2026-02-10T00:00:00Z").to_pydatetime(),
    )
    via_runtime_adapter = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        **TemporalService().world_query_kwargs(temporal_scope),
    )
    assert via_runtime_adapter.iloc[0]["label"] == "Late arrival"


def test_world_branch_snapshot_queries_do_not_contaminate_base(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "base.duckdb"))
    ensure_world_schema(db)

    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("4" * 64),
        predicate_id="world.kind",
        object_value="claim",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-01-01T00:00:00Z",
        segment_id="seg.kind",
    )
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("5" * 64),
        predicate_id="world.label",
        object_value="Base label",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-01-01T00:00:00Z",
        segment_id="seg.base",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "world_snapshots"
    base_snapshot = create_world_snapshot(db, snapshot_root=snapshot_root)
    create_world_branch(
        snapshot_root,
        branch_name="scenario_a",
        base_snapshot_id=base_snapshot.snapshot_id,
        provenance={"source": "test"},
    )

    branch_db_path = tmp_path / "branch.duckdb"
    shutil.copy2(base_snapshot.snapshot_path, branch_db_path)
    branch_db = SimulationDB(db_path=str(branch_db_path))
    _insert_node_attr_fact(
        branch_db,
        fact_id="sha256:" + ("6" * 64),
        predicate_id="world.label",
        object_value="Branch label",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-02-01T00:00:00Z",
        segment_id="seg.branch",
    )
    _refresh_current_world_node(branch_db)
    create_world_snapshot(
        branch_db,
        snapshot_root=snapshot_root,
        branch_name="scenario_a",
        base_snapshot_id=base_snapshot.snapshot_id,
        provenance={"source": "branch"},
    )

    base_rows = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
    )
    branch_rows = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        snapshot_root=snapshot_root,
        branch="scenario_a",
    )

    assert base_rows.iloc[0]["label"] == "Base label"
    assert branch_rows.iloc[0]["label"] == "Branch label"


def test_world_snapshot_gc_keeps_tagged_audit_snapshots(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "gc.duckdb"))
    ensure_world_schema(db)
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("7" * 64),
        predicate_id="world.kind",
        object_value="claim",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-01-01T00:00:00Z",
        segment_id="seg.kind",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "gc_snapshots"
    snapshot1 = create_world_snapshot(db, snapshot_root=snapshot_root)
    snapshot2 = create_world_snapshot(
        db,
        snapshot_root=snapshot_root,
        tags=("audit",),
    )
    snapshot3 = create_world_snapshot(db, snapshot_root=snapshot_root)

    report = gc_world_snapshots(
        snapshot_root,
        keep_latest=1,
        retain_tags=("audit",),
    )

    assert snapshot1.snapshot_id in report.deleted_snapshot_ids
    assert snapshot2.snapshot_id in report.retained_snapshot_ids
    assert snapshot3.snapshot_id in report.retained_snapshot_ids
    assert not Path(snapshot1.snapshot_path).exists()
    assert Path(snapshot2.snapshot_path).exists()
    assert Path(snapshot3.snapshot_path).exists()


def test_world_snapshot_adapter_registry_exposes_future_table_formats() -> None:
    adapters = {item.adapter_name: item for item in list_world_snapshot_adapters()}

    assert "duckdb_native_file_copy" in adapters
    assert "iceberg_table" in adapters
    assert "delta_table" in adapters
    assert adapters["duckdb_native_file_copy"].supports_snapshot_create is True
    assert adapters["duckdb_native_file_copy"].supports_read_query is True
    assert adapters["iceberg_table"].supports_snapshot_create is False
    assert adapters["iceberg_table"].retention_scope == "metadata_only"
    assert "Future adapter path" in adapters["iceberg_table"].cost_notes


def test_register_world_snapshot_record_supports_external_adapter_metadata(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "external_snapshots"
    record = register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_external_iceberg",
            snapshot_path="s3://warehouse/fabric/world_snapshots/main",
            created_at="2026-04-15T10:00:00Z",
            branch_name="scenario_iceberg",
            base_snapshot_id="world_snapshot_external_iceberg",
            as_of_tx_time="2026-04-15T10:00:00Z",
            merge_policy="fail_on_conflict",
            provenance={"source": "integration-test"},
            storage_adapter="iceberg_table",
            adapter_config={
                "catalog": "rest",
                "table_identifier": "fabric.world_snapshots.main",
            },
        ),
    )

    resolved = resolve_world_snapshot(snapshot_root, branch_name="scenario_iceberg")

    assert resolved.snapshot_id == record.snapshot_id
    assert resolved.storage_adapter == "iceberg_table"
    assert resolved.adapter_config["catalog"] == "rest"
    assert resolved.governance is not None
    assert resolved.governance.classification == "public"


def test_gc_world_snapshots_deletes_external_metadata_without_touching_remote_uri(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "external_gc"
    register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_external_delta",
            snapshot_path="abfss://policy/world_snapshots/delta/main",
            created_at="2026-04-15T10:00:00Z",
            branch_name="expired_external",
            base_snapshot_id="world_snapshot_external_delta",
            storage_adapter="delta_table",
        ),
    )
    branch_file = snapshot_root / "branches" / "expired_external.json"
    assert branch_file.exists()
    branch_file.unlink()

    report = gc_world_snapshots(snapshot_root, keep_latest=0, retain_tags=())

    assert report.deleted_snapshot_ids == ("world_snapshot_external_delta",)
    assert not (snapshot_root / "metadata" / "world_snapshot_external_delta.json").exists()


def test_legal_hold_world_snapshot_requires_encryption_metadata(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "legal_hold_missing_encryption"

    with pytest.raises(ArtifactGovernanceError, match="legal retention"):
        register_world_snapshot_record(
            snapshot_root,
            WorldSnapshotRecord(
                snapshot_id="world_snapshot_legal_hold_missing_encryption",
                snapshot_path="s3://warehouse/fabric/world_snapshots/legal-hold",
                created_at="2026-04-15T10:00:00Z",
                branch_name="legal_hold_missing_encryption",
                base_snapshot_id="world_snapshot_legal_hold_missing_encryption",
                storage_adapter="iceberg_table",
                tags=("legal_hold",),
            ),
        )


def test_gc_world_snapshots_preserves_legal_hold_even_when_retain_tags_empty(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "legal_hold_gc"
    register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_legal_hold",
            snapshot_path="s3://warehouse/fabric/world_snapshots/legal-hold",
            created_at="2026-04-15T10:00:00Z",
            branch_name="legal_hold",
            base_snapshot_id="world_snapshot_legal_hold",
            storage_adapter="iceberg_table",
            tags=("legal_hold",),
            governance=resolve_artifact_governance(
                scope=RetentionScope.WORLD_SNAPSHOT,
                classification=DataClassification.INTERNAL,
                encrypted_at_rest=True,
                encryption_key_reference="kms://fabric/world/legal-hold",
            ),
        ),
    )
    register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_expired",
            snapshot_path="s3://warehouse/fabric/world_snapshots/expired",
            created_at="2026-04-16T10:00:00Z",
            branch_name="expired",
            base_snapshot_id="world_snapshot_expired",
            storage_adapter="iceberg_table",
        ),
    )
    for branch in ("legal_hold", "expired"):
        branch_file = snapshot_root / "branches" / f"{branch}.json"
        assert branch_file.exists()
        branch_file.unlink()

    report = gc_world_snapshots(snapshot_root, keep_latest=0, retain_tags=())

    assert report.retained_snapshot_ids == ("world_snapshot_legal_hold",)
    assert report.deleted_snapshot_ids == ("world_snapshot_expired",)
    assert (snapshot_root / "metadata" / "world_snapshot_legal_hold.json").exists()
    assert not (snapshot_root / "metadata" / "world_snapshot_expired.json").exists()


def test_query_world_table_rejects_external_snapshot_adapter_without_runtime_support(
    tmp_path: Path,
) -> None:
    db = SimulationDB(db_path=str(tmp_path / "query.duckdb"))
    ensure_world_schema(db)
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("a" * 64),
        predicate_id="world.kind",
        object_value="claim",
        valid_time="2026-01-01T00:00:00Z",
        tx_time="2026-01-01T00:00:00Z",
        segment_id="seg.kind",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "query_external"
    register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_external_query",
            snapshot_path="s3://warehouse/fabric/world_snapshots/main",
            created_at="2026-04-15T10:00:00Z",
            branch_name="scenario_iceberg",
            base_snapshot_id="world_snapshot_external_query",
            storage_adapter="iceberg_table",
        ),
    )

    with pytest.raises(WorldQueryError, match="iceberg_table"):
        query_world_table(
            db,
            table="world_nodes",
            columns=("node_id",),
            branch="scenario_iceberg",
            snapshot_root=snapshot_root,
        )


def test_create_world_snapshot_rejects_unimplemented_future_adapter(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "future_adapter.duckdb"))
    ensure_world_schema(db)

    with pytest.raises(WorldSnapshotAdapterError, match="iceberg_table"):
        create_world_snapshot(
            db,
            snapshot_root=tmp_path / "future_adapter_snapshots",
            storage_adapter="iceberg_table",
        )


def test_create_world_snapshot_fails_closed_when_encryption_requirement_is_unmet(
    tmp_path: Path,
) -> None:
    db = SimulationDB(db_path=str(tmp_path / "governed_snapshot.duckdb"))
    ensure_world_schema(db)

    with pytest.raises(ArtifactGovernanceError, match="at-rest encryption"):
        create_world_snapshot(
            db,
            snapshot_root=tmp_path / "governed_snapshot_root",
            classification=DataClassification.CONFIDENTIAL,
        )


def test_register_world_snapshot_record_preserves_governance_metadata(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "governed_external_snapshots"
    record = register_world_snapshot_record(
        snapshot_root,
        WorldSnapshotRecord(
            snapshot_id="world_snapshot_governed_external",
            snapshot_path="s3://warehouse/fabric/world_snapshots/governed",
            created_at="2026-04-15T10:00:00Z",
            branch_name="governed_external",
            base_snapshot_id="world_snapshot_governed_external",
            storage_adapter="iceberg_table",
            governance=resolve_artifact_governance(
                scope=RetentionScope.WORLD_PROJECTION,
                classification=DataClassification.INTERNAL,
                encrypted_at_rest=True,
                encryption_key_reference="kms://fabric/world",
            ),
        ),
    )

    assert record.governance is not None
    assert record.governance.classification == "internal"
    assert record.governance.retention is not None
    assert record.governance.retention.scope == "world_projection"


def test_world_branch_merge_applies_branch_head_without_manual_rebuild(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "merge_base.duckdb"))
    ensure_world_schema(db)

    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("8" * 64),
        predicate_id="world.kind",
        object_value="claim",
        tx_time="2026-01-01T00:00:00Z",
        valid_time="2026-01-01T00:00:00Z",
        segment_id="seg.kind",
    )
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("9" * 64),
        predicate_id="world.label",
        object_value="Base label",
        tx_time="2026-01-01T00:00:00Z",
        valid_time="2026-01-01T00:00:00Z",
        segment_id="seg.base",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "merge_snapshots"
    base_snapshot = create_world_snapshot(db, snapshot_root=snapshot_root)
    create_world_branch(
        snapshot_root,
        branch_name="scenario_merge",
        base_snapshot_id=base_snapshot.snapshot_id,
    )

    branch_db_path = tmp_path / "merge_branch.duckdb"
    shutil.copy2(base_snapshot.snapshot_path, branch_db_path)
    with SimulationDB(db_path=str(branch_db_path)) as branch_db:
        _insert_node_attr_fact(
            branch_db,
            fact_id="sha256:" + ("a" * 64),
            predicate_id="world.label",
            object_value="Merged branch label",
            tx_time="2026-02-01T00:00:00Z",
            valid_time="2026-01-01T00:00:00Z",
            segment_id="seg.branch",
        )
        _refresh_current_world_node(branch_db)
        create_world_snapshot(
            branch_db,
            snapshot_root=snapshot_root,
            branch_name="scenario_merge",
            base_snapshot_id=base_snapshot.snapshot_id,
        )

    report = merge_world_branch(
        snapshot_root,
        branch_name="scenario_merge",
        target_branch_name="main",
        merge_policy="branch_wins",
        provenance={"actor": "pytest"},
    )

    merged_rows = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
        snapshot_root=snapshot_root,
        branch="main",
    )
    base_rows = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "label"),
        where={"node_id": "node.time"},
    )

    assert report.merged_snapshot.branch_name == "main"
    assert report.merged_snapshot.provenance["merge"]["source_branch"] == "scenario_merge"
    assert merged_rows.iloc[0]["label"] == "Merged branch label"
    assert base_rows.iloc[0]["label"] == "Base label"


def test_world_branch_merge_fail_on_conflicting_world_kind(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "conflict_base.duckdb"))
    ensure_world_schema(db)
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("b" * 64),
        predicate_id="world.kind",
        object_value="claim",
        tx_time="2026-01-01T00:00:00Z",
        valid_time="2026-01-01T00:00:00Z",
        segment_id="seg.base.kind",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "conflict_snapshots"
    base_snapshot = create_world_snapshot(db, snapshot_root=snapshot_root)
    create_world_branch(
        snapshot_root,
        branch_name="scenario_conflict",
        base_snapshot_id=base_snapshot.snapshot_id,
        merge_policy="fail_on_conflict",
    )

    branch_db_path = tmp_path / "conflict_branch.duckdb"
    shutil.copy2(base_snapshot.snapshot_path, branch_db_path)
    with SimulationDB(db_path=str(branch_db_path)) as branch_db:
        _insert_node_attr_fact(
            branch_db,
            fact_id="sha256:" + ("c" * 64),
            predicate_id="world.kind",
            object_value="policy_domain",
            tx_time="2026-02-01T00:00:00Z",
            valid_time="2026-01-01T00:00:00Z",
            segment_id="seg.branch.kind",
        )
        _refresh_current_world_node(branch_db)
        create_world_snapshot(
            branch_db,
            snapshot_root=snapshot_root,
            branch_name="scenario_conflict",
            base_snapshot_id=base_snapshot.snapshot_id,
            merge_policy="fail_on_conflict",
        )

    with pytest.raises(WorldBranchMergeConflictError, match="world.kind conflict") as excinfo:
        merge_world_branch(
            snapshot_root,
            branch_name="scenario_conflict",
            target_branch_name="main",
            merge_policy="fail_on_conflict",
        )
    payload = excinfo.value.export_payload()
    assert payload["table_name"] == "world.world_facts"
    assert payload["merge_policy"] == "fail_on_conflict"
    assert payload["conflict_summary"]["unresolved"] is True


def test_world_branch_merge_target_wins_on_conflicting_world_kind(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "target_wins_base.duckdb"))
    ensure_world_schema(db)
    _insert_node_attr_fact(
        db,
        fact_id="sha256:" + ("d" * 64),
        predicate_id="world.kind",
        object_value="claim",
        tx_time="2026-01-01T00:00:00Z",
        valid_time="2026-01-01T00:00:00Z",
        segment_id="seg.base.kind",
    )
    _refresh_current_world_node(db)

    snapshot_root = tmp_path / "target_wins_snapshots"
    base_snapshot = create_world_snapshot(db, snapshot_root=snapshot_root)
    create_world_branch(
        snapshot_root,
        branch_name="scenario_target_wins",
        base_snapshot_id=base_snapshot.snapshot_id,
        merge_policy="target_wins",
    )

    branch_db_path = tmp_path / "target_wins_branch.duckdb"
    shutil.copy2(base_snapshot.snapshot_path, branch_db_path)
    with SimulationDB(db_path=str(branch_db_path)) as branch_db:
        _insert_node_attr_fact(
            branch_db,
            fact_id="sha256:" + ("e" * 64),
            predicate_id="world.kind",
            object_value="policy_domain",
            tx_time="2026-02-01T00:00:00Z",
            valid_time="2026-01-01T00:00:00Z",
            segment_id="seg.branch.kind",
        )
        _refresh_current_world_node(branch_db)
        create_world_snapshot(
            branch_db,
            snapshot_root=snapshot_root,
            branch_name="scenario_target_wins",
            base_snapshot_id=base_snapshot.snapshot_id,
            merge_policy="target_wins",
        )

    report = merge_world_branch(
        snapshot_root,
        branch_name="scenario_target_wins",
        target_branch_name="main",
        merge_policy="target_wins",
    )
    merged_rows = query_world_table(
        db,
        table="world_nodes",
        columns=("node_id", "kind"),
        where={"node_id": "node.time"},
        snapshot_root=snapshot_root,
        branch="main",
    )

    assert merged_rows.iloc[0]["kind"] == "claim"
    assert len(report.resolved_conflicts) == 1
    assert report.resolved_conflicts[0].winner_value == "claim"
