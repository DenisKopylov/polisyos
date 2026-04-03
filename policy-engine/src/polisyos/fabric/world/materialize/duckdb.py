"""Apply world fact segments into DuckDB tables and derived query projections."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.store.segments import load_world_fact_manifests
from polisyos.ir.fact_log import FactSegmentManifest
from polisyos.ir.world.predicates import WORLD_REL_PREFIX

from .errors import (
    WorldMaterializationError,
    WorldMergeConflict,
    WorldSchemaError,
    WorldSegmentHashMismatch,
)
from .projections import update_projections
from .sql import (
    sql_count_new_edges,
    sql_count_new_world_facts,
    sql_insert_missing_nodes,
    sql_insert_world_edges,
    sql_insert_world_facts,
    sql_kind_conflicts,
    sql_load_applied_segments,
    sql_update_world_nodes,
)
from .staging import stage_world_segment

logger = get_logger(__name__)


@dataclass
class WorldMaterializeSegmentStats:
    """World materialize segment stats public type."""
    segment_id: str
    segment_sha256: str
    row_count: int
    facts_inserted: int
    nodes_touched: int
    edges_inserted: int
    projections_updated: int


@dataclass
class WorldMaterializeStats:
    """World materialize stats public type."""
    segments_total: int
    segments_applied: int
    segments_skipped: int
    facts_inserted: int
    nodes_touched: int
    edges_inserted: int
    projections_updated: int
    segments: list[WorldMaterializeSegmentStats] = field(default_factory=list)


def ensure_world_schema(db: SimulationDB, *, ddl_path: Path | None = None) -> None:
    """Create or migrate the DuckDB world schema before applying fact segments."""
    if ddl_path is None:
        ddl_path = Path(__file__).resolve().parents[1] / "ddl" / "duckdb_world.sql"
    ddl_path = Path(ddl_path)
    if not ddl_path.exists():
        raise WorldSchemaError(f"world DDL file not found: {ddl_path}")
    ddl = ddl_path.read_text("utf-8")
    try:
        db.conn.execute(ddl)
        _ensure_world_schema_migrations(db)
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSchemaError(f"failed to apply world DDL: {exc}") from exc


def _column_exists(db: SimulationDB, table_name: str, column_name: str) -> bool:
    rows = db.conn.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'world'
          AND table_name = ?
          AND column_name = ?
        LIMIT 1
        """,
        [table_name, column_name],
    ).fetchall()
    return bool(rows)


def _ensure_column(
    db: SimulationDB,
    *,
    table_name: str,
    column_name: str,
    ddl_type: str,
) -> None:
    if _column_exists(db, table_name, column_name):
        return
    db.conn.execute(
        f"ALTER TABLE world.{table_name} ADD COLUMN {column_name} {ddl_type}"
    )


def _ensure_world_schema_migrations(db: SimulationDB) -> None:
    # Idempotent online migrations for pre-phase14 databases.
    for column_name, ddl_type in (
        ("conflict_key", "VARCHAR"),
        ("conflict_kind", "VARCHAR"),
        ("winner_claim_id", "VARCHAR"),
        ("resolution_policy_id", "VARCHAR"),
        ("resolution_confidence", "VARCHAR"),
        ("resolution_artifact_id", "VARCHAR"),
        ("meta_artifact_id", "VARCHAR"),
    ):
        _ensure_column(
            db,
            table_name="conflict_sets",
            column_name=column_name,
            ddl_type=ddl_type,
        )
    for column_name, ddl_type in (
        ("role", "VARCHAR"),
        ("rank", "INTEGER"),
    ):
        _ensure_column(
            db,
            table_name="conflict_members",
            column_name=column_name,
            ddl_type=ddl_type,
        )


def ensure_world_materialized(
    db: SimulationDB,
    cas: FileSystemCAS,
    fact_manifests: Iterable[FactSegmentManifest],
) -> WorldMaterializeStats:
    """Apply unapplied world segments into DuckDB and aggregate per-run materialization stats."""
    manifests = list(fact_manifests)
    ensure_world_schema(db)
    stats = WorldMaterializeStats(
        segments_total=len(manifests),
        segments_applied=0,
        segments_skipped=0,
        facts_inserted=0,
        nodes_touched=0,
        edges_inserted=0,
        projections_updated=0,
    )
    applied = _load_applied_segments(db)
    for manifest in manifests:
        existing = applied.get(manifest.segment_id)
        if existing:
            if existing != manifest.sha256:
                raise WorldSegmentHashMismatch(
                    "segment hash mismatch for "
                    f"{manifest.segment_id}: {existing} != {manifest.sha256}"
                )
            stats.segments_skipped += 1
            continue
        segment_stats = apply_world_segment(db, cas, manifest)
        stats.segments_applied += 1
        stats.facts_inserted += segment_stats.facts_inserted
        stats.nodes_touched += segment_stats.nodes_touched
        stats.edges_inserted += segment_stats.edges_inserted
        stats.projections_updated += segment_stats.projections_updated
        stats.segments.append(segment_stats)
    return stats


def materialize_world_duckdb_from_fact_log(
    fact_log_root: Path,
    db: SimulationDB,
    cas: FileSystemCAS,
) -> WorldMaterializeStats:
    """Load indexed world segments from the fact log and materialize them into DuckDB."""
    manifests = load_world_fact_manifests(fact_log_root)
    return ensure_world_materialized(db, cas, manifests)


def apply_world_segment(
    db: SimulationDB,
    cas: FileSystemCAS,
    manifest: FactSegmentManifest,
) -> WorldMaterializeSegmentStats:
    """Stage and merge one world fact segment into DuckDB inside a single transaction."""
    segment_path = Path(manifest.path)
    if not segment_path.exists():
        raise WorldMaterializationError(f"missing world segment: {segment_path}")

    _verify_segment_hash(segment_path, manifest.sha256)

    staged = stage_world_segment(manifest)

    db.conn.execute("BEGIN")
    try:
        if staged.df.empty:
            stats = _record_empty_segment(db, manifest)
            db.conn.execute("COMMIT")
            return stats

        facts_inserted = 0
        edges_inserted = 0

        facts_df = _prepare_world_facts_df(staged.df, manifest.segment_id)
        if not facts_df.empty:
            facts_name = _register_df(db.conn, facts_df, prefix="world_facts")
            try:
                facts_inserted = int(
                    db.conn.execute(sql_count_new_world_facts(facts_name)).fetchone()[0]
                )
                db.conn.execute(sql_insert_world_facts(facts_name))
            finally:
                db.conn.unregister(facts_name)

        touched_ids = sorted(set(staged.touched_node_ids))
        nodes_touched = len(touched_ids)
        if nodes_touched:
            touched_df = pd.DataFrame({"node_id": touched_ids})
            touched_name = _register_df(db.conn, touched_df, prefix="touched_nodes")
            try:
                db.conn.execute(sql_insert_missing_nodes(touched_name))
                conflicts = db.conn.execute(sql_kind_conflicts(touched_name)).fetchall()
                if conflicts:
                    conflict_ids = ", ".join(row[0] for row in conflicts)
                    raise WorldMergeConflict(
                        f"world.kind conflict for nodes: {conflict_ids}"
                    )
                db.conn.execute(sql_update_world_nodes(touched_name))
            finally:
                db.conn.unregister(touched_name)

        edges_df = _prepare_world_edges_df(staged.edge_df, manifest.segment_id)
        if not edges_df.empty:
            edges_name = _register_df(db.conn, edges_df, prefix="world_edges")
            try:
                edges_inserted = int(
                    db.conn.execute(sql_count_new_edges(edges_name)).fetchone()[0]
                )
                db.conn.execute(sql_insert_world_edges(edges_name))
            finally:
                db.conn.unregister(edges_name)

        projection_stats = update_projections(db.conn, cas, touched_node_ids=touched_ids)

        segment_stats = WorldMaterializeSegmentStats(
            segment_id=manifest.segment_id,
            segment_sha256=manifest.sha256,
            row_count=manifest.row_count,
            facts_inserted=facts_inserted,
            nodes_touched=nodes_touched,
            edges_inserted=edges_inserted,
            projections_updated=projection_stats.total_updates,
        )

        _record_segment_meta(db, manifest, segment_stats)
        db.conn.execute("COMMIT")
        return segment_stats
    except Exception as exc:
        db.conn.execute("ROLLBACK")
        if isinstance(exc, WorldMaterializationError):
            raise
        raise WorldMaterializationError(str(exc)) from exc


def _register_df(conn, df: pd.DataFrame, *, prefix: str) -> str:
    name = f"{prefix}_{uuid.uuid4().hex}"
    conn.register(name, df)
    return name


def _verify_segment_hash(path: Path, expected_sha256: str) -> None:
    digest = content_hash(path.read_bytes())
    if digest != expected_sha256:
        raise WorldSegmentHashMismatch(
            f"segment hash mismatch for {path}: {digest} != {expected_sha256}"
        )


def _load_applied_segments(db: SimulationDB) -> dict[str, str]:
    try:
        rows = db.conn.execute(sql_load_applied_segments()).fetchall()
    except Exception:
        logger.debug(
            "Failed to load applied segments from SimulationDB", exc_info=True,
        )
        return {}
    return {row[0]: row[1] for row in rows}


def _prepare_world_facts_df(df: pd.DataFrame, segment_id: str) -> pd.DataFrame:
    facts_df = df.copy()
    facts_df["provenance_json"] = facts_df["provenance"]
    facts_df["trust_json"] = facts_df["trust"]
    facts_df["legal_json"] = facts_df["legal"]
    facts_df["segment_id"] = segment_id
    columns = [
        "fact_id",
        "schema_version",
        "subject_id",
        "predicate_id",
        "object_value",
        "target_id",
        "valid_time",
        "tx_time",
        "provenance_json",
        "trust_json",
        "legal_json",
        "segment_id",
    ]
    return facts_df[columns]


def _prepare_world_edges_df(df: pd.DataFrame, segment_id: str) -> pd.DataFrame:
    if df.empty:
        return df
    edges_df = df.copy()
    edges_df["edge_id"] = edges_df["fact_id"]
    edges_df["src_id"] = edges_df["subject_id"]
    edges_df["dst_id"] = edges_df["target_id"]
    edges_df["kind"] = edges_df["predicate_id"].astype(str).str[len(WORLD_REL_PREFIX) :]
    edges_df["provenance_json"] = edges_df["provenance"]
    edges_df["trust_json"] = edges_df["trust"]
    edges_df["legal_json"] = edges_df["legal"]
    edges_df["segment_id"] = segment_id
    columns = [
        "edge_id",
        "src_id",
        "predicate_id",
        "kind",
        "dst_id",
        "valid_time",
        "tx_time",
        "provenance_json",
        "trust_json",
        "legal_json",
        "segment_id",
    ]
    return edges_df[columns]


def _record_empty_segment(
    db: SimulationDB, manifest: FactSegmentManifest
) -> WorldMaterializeSegmentStats:
    stats = WorldMaterializeSegmentStats(
        segment_id=manifest.segment_id,
        segment_sha256=manifest.sha256,
        row_count=manifest.row_count,
        facts_inserted=0,
        nodes_touched=0,
        edges_inserted=0,
        projections_updated=0,
    )
    _record_segment_meta(db, manifest, stats)
    return stats


def _record_segment_meta(
    db: SimulationDB,
    manifest: FactSegmentManifest,
    stats: WorldMaterializeSegmentStats,
) -> None:
    db.conn.execute(
        """
        INSERT INTO world._meta_world_segments (
            segment_id,
            segment_sha256,
            row_count,
            facts_inserted,
            nodes_touched,
            edges_inserted,
            projections_updated,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            manifest.segment_id,
            manifest.sha256,
            manifest.row_count,
            stats.facts_inserted,
            stats.nodes_touched,
            stats.edges_inserted,
            stats.projections_updated,
            None,
        ],
    )


__all__ = [
    "WorldMaterializeSegmentStats",
    "WorldMaterializeStats",
    "apply_world_segment",
    "ensure_world_materialized",
    "ensure_world_schema",
    "materialize_world_duckdb_from_fact_log",
]
