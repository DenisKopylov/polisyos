"""Apply world fact segments into DuckDB tables and derived query projections."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.canon import content_hash
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.temporal import parse_datetime_utc, utc_now
from polisyos.fabric.world.providers import resolve_world_observability
from polisyos.fabric.world.store.segments import load_world_fact_manifests
from polisyos.ir.fact_log import FactSegmentManifest
from polisyos.ir.world.predicates import WORLD_REL_PREFIX

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

from .errors import (
    WorldMaterializationError,
    WorldMergeConflict,
    WorldSchemaError,
    WorldSegmentHashMismatch,
)
from .projections import build_projection_refresh_plan, update_projections
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


class WorldRefreshTrigger(str, Enum):
    """Reason a materialization run was requested."""

    ON_SEGMENT_ARRIVAL = "on_segment_arrival"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"


class WorldProjectionFailureMode(str, Enum):
    """How projection refresh failures should be handled."""

    FAIL_CLOSED = "fail_closed"
    STALE_IF_ERROR = "stale_if_error"


@dataclass(frozen=True)
class WorldMaterializationPolicy:
    """Refresh policy attached to one materialization run."""

    trigger: WorldRefreshTrigger = WorldRefreshTrigger.ON_SEGMENT_ARRIVAL
    projection_failure_mode: WorldProjectionFailureMode = WorldProjectionFailureMode.FAIL_CLOSED


@dataclass(frozen=True)
class WorldMaterializationStep:
    """Explain one topologically sorted materialization step."""

    name: str
    depends_on: tuple[str, ...] = ()
    incremental: bool = True
    impacted: bool = True
    reason: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldMaterializationPlan:
    """Explainable materialization DAG linearized into execution order."""

    steps: tuple[WorldMaterializationStep, ...] = ()

    def explain(self) -> tuple[str, ...]:
        lines: list[str] = []
        for step in self.steps:
            deps = ", ".join(step.depends_on) or "none"
            note_suffix = f" notes=[{'; '.join(step.notes)}]" if step.notes else ""
            lines.append(
                f"{step.name}: depends_on=[{deps}] incremental={step.incremental} "
                f"impacted={step.impacted} reason={step.reason}{note_suffix}"
            )
        return tuple(lines)


@dataclass(frozen=True)
class WorldMaterializationShard:
    """Logical shard for tenant/dataset/time-partitioned materialization."""

    shard_id: str
    tenant_id: str
    dataset_id: str
    time_partition: str
    segment_ids: tuple[str, ...]


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
    projection_names: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    plan: WorldMaterializationPlan = field(default_factory=WorldMaterializationPlan)


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
    db.conn.execute(f"ALTER TABLE world.{table_name} ADD COLUMN {column_name} {ddl_type}")


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
    cas: ArtifactStore,
    fact_manifests: Iterable[FactSegmentManifest],
    *,
    refresh_policy: WorldMaterializationPolicy | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> WorldMaterializeStats:
    """Apply unapplied world segments into DuckDB and aggregate per-run materialization stats."""
    manifests = list(fact_manifests)
    policy = refresh_policy or WorldMaterializationPolicy()
    resolved = resolve_world_observability(tracer=tracer, metrics=metrics)
    with resolved.tracer.start_as_current_span(
        FABRIC_TRACE_NAMES["materialize"],
        attributes={"world.segment_count": len(manifests)},
    ):
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
            segment_stats = apply_world_segment(
                db,
                cas,
                manifest,
                refresh_policy=policy,
                tracer=resolved.tracer,
                metrics=resolved.metrics,
            )
            stats.segments_applied += 1
            stats.facts_inserted += segment_stats.facts_inserted
            stats.nodes_touched += segment_stats.nodes_touched
            stats.edges_inserted += segment_stats.edges_inserted
            stats.projections_updated += segment_stats.projections_updated
            stats.segments.append(segment_stats)

        if getattr(resolved.metrics, "set_fabric_segment_count", None):
            tenant_groups = _group_manifests_by_tenant(manifests)
            if tenant_groups:
                for tenant_id, tenant_manifests in sorted(tenant_groups.items()):
                    resolved.metrics.set_fabric_segment_count(
                        float(len(tenant_manifests)),
                        tenant_id=tenant_id,
                    )
            else:
                resolved.metrics.set_fabric_segment_count(float(stats.segments_total))
        lag_seconds = _materialization_lag_seconds(manifests)
        if lag_seconds is not None and getattr(
            resolved.metrics, "set_fabric_materialization_lag", None
        ):
            tenant_groups = _group_manifests_by_tenant(manifests)
            if len(tenant_groups) == 1:
                tenant_id, tenant_manifests = next(iter(tenant_groups.items()))
                tenant_lag_seconds = _materialization_lag_seconds(tenant_manifests)
                if tenant_lag_seconds is not None:
                    resolved.metrics.set_fabric_materialization_lag(
                        tenant_lag_seconds,
                        tenant_id=tenant_id,
                    )
            else:
                resolved.metrics.set_fabric_materialization_lag(lag_seconds)
        return stats


def materialize_world_duckdb_from_fact_log(
    fact_log_root: Path,
    db: SimulationDB,
    cas: ArtifactStore,
    *,
    refresh_policy: WorldMaterializationPolicy | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> WorldMaterializeStats:
    """Load indexed world segments from the fact log and materialize them into DuckDB."""
    manifests = load_world_fact_manifests(fact_log_root)
    return ensure_world_materialized(
        db,
        cas,
        manifests,
        refresh_policy=refresh_policy,
        tracer=tracer,
        metrics=metrics,
    )


def plan_world_materialization_shards(
    fact_manifests: Iterable[FactSegmentManifest],
    *,
    default_tenant: str = "shared",
    time_granularity: str = "month",
) -> tuple[WorldMaterializationShard, ...]:
    """Group manifests into tenant/dataset/time shards for scale-out planning."""
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for manifest in fact_manifests:
        tenant_id = str(manifest.stats.get("tenant_id", default_tenant))
        dataset_id = str(manifest.stats.get("dataset_id", "world"))
        time_partition = _time_partition_for_manifest(
            manifest,
            granularity=time_granularity,
        )
        grouped.setdefault((tenant_id, dataset_id, time_partition), []).append(manifest.segment_id)

    shards = [
        WorldMaterializationShard(
            shard_id=f"{tenant_id}:{dataset_id}:{time_partition}",
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            time_partition=time_partition,
            segment_ids=tuple(segment_ids),
        )
        for (tenant_id, dataset_id, time_partition), segment_ids in sorted(grouped.items())
    ]
    return tuple(shards)


def apply_world_segment(
    db: SimulationDB,
    cas: ArtifactStore,
    manifest: FactSegmentManifest,
    *,
    refresh_policy: WorldMaterializationPolicy | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> WorldMaterializeSegmentStats:
    """Stage and merge one world fact segment into DuckDB inside a single transaction."""
    segment_path = Path(manifest.path)
    if not segment_path.exists():
        raise WorldMaterializationError(f"missing world segment: {segment_path}")
    policy = refresh_policy or WorldMaterializationPolicy()

    resolved = resolve_world_observability(tracer=tracer, metrics=metrics)
    with resolved.tracer.start_as_current_span(
        FABRIC_TRACE_NAMES["materialize"],
        attributes={
            "world.segment_id": manifest.segment_id,
            "world.segment_rows": manifest.row_count,
        },
    ):
        _verify_segment_hash(segment_path, manifest.sha256)

        staged = stage_world_segment(manifest)

        db.conn.execute("BEGIN")
        try:
            if staged.df.empty:
                plan = build_world_materialization_plan(
                    manifest=manifest,
                    touched_node_kinds=(),
                    refresh_policy=policy,
                )
                stats = _record_empty_segment(db, manifest, plan=plan)
                db.conn.execute("COMMIT")
                return stats

            facts_inserted = 0
            edges_inserted = 0
            materialization_notes: list[str] = []

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
                        raise WorldMergeConflict(f"world.kind conflict for nodes: {conflict_ids}")
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

            touched_node_kinds = _load_touched_node_kinds(db, touched_ids)
            projection_plan = build_projection_refresh_plan(touched_node_kinds=touched_node_kinds)
            world_plan = build_world_materialization_plan(
                manifest=manifest,
                touched_node_kinds=touched_node_kinds,
                refresh_policy=policy,
            )

            projection_stats = None
            projection_backups: dict[str, str] = {}
            if (
                policy.projection_failure_mode is WorldProjectionFailureMode.STALE_IF_ERROR
                and projection_plan.steps
            ):
                projection_backups = _backup_projection_tables(
                    db,
                    table_names=tuple(
                        table_name
                        for step in projection_plan.steps
                        for table_name in step.target_tables
                    ),
                )
            try:
                projection_stats = update_projections(
                    db.conn,
                    cas,
                    touched_node_ids=touched_ids,
                    in_transaction=True,
                )
            except WorldMergeConflict:
                _cleanup_projection_backups(db, projection_backups)
                raise
            except Exception as exc:
                if policy.projection_failure_mode is not WorldProjectionFailureMode.STALE_IF_ERROR:
                    _cleanup_projection_backups(db, projection_backups)
                    raise
                _restore_projection_tables(db, projection_backups)
                materialization_notes.append(
                    f"projection refresh left stale due to {type(exc).__name__}: {exc}"
                )
            else:
                _cleanup_projection_backups(db, projection_backups)

            segment_stats = WorldMaterializeSegmentStats(
                segment_id=manifest.segment_id,
                segment_sha256=manifest.sha256,
                row_count=manifest.row_count,
                facts_inserted=facts_inserted,
                nodes_touched=nodes_touched,
                edges_inserted=edges_inserted,
                projections_updated=(
                    projection_stats.total_updates if projection_stats is not None else 0
                ),
                projection_names=projection_plan.impacted_projection_names,
                notes=tuple(materialization_notes),
                plan=world_plan,
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
    except Exception as exc:
        logger.error(
            "Failed to load applied segments from SimulationDB; refusing to reapply segments",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise WorldMaterializationError(
            "failed to load applied world segments; materialization state is uncertain"
        ) from exc
    return {row[0]: row[1] for row in rows}


def _materialization_lag_seconds(manifests: Iterable[FactSegmentManifest]) -> float | None:
    latest = None
    for manifest in manifests:
        if not isinstance(manifest.time_end, str) or not manifest.time_end:
            continue
        try:
            candidate = parse_datetime_utc(manifest.time_end, what="world segment time_end")
        except Exception:
            continue
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        return None
    return max((utc_now() - latest).total_seconds(), 0.0)


def _load_touched_node_kinds(db: SimulationDB, touched_node_ids: Sequence[str]) -> tuple[str, ...]:
    if not touched_node_ids:
        return ()
    touched_df = pd.DataFrame({"node_id": list(touched_node_ids)})
    touched_name = _register_df(db.conn, touched_df, prefix="touched_node_kinds")
    try:
        rows = db.conn.execute(
            f"""
            SELECT DISTINCT kind
            FROM world.world_nodes
            WHERE node_id IN (SELECT node_id FROM {touched_name})
              AND kind IS NOT NULL
            ORDER BY kind
            """
        ).fetchall()
    finally:
        db.conn.unregister(touched_name)
    return tuple(str(row[0]) for row in rows if row and row[0] is not None)


def _backup_projection_tables(
    db: SimulationDB,
    *,
    table_names: Sequence[str],
) -> dict[str, str]:
    backups: dict[str, str] = {}
    for table_name in dict.fromkeys(table_names):
        safe_name = table_name.replace(".", "_").replace("-", "_")
        backup_name = f"tmp_{safe_name}_backup_{uuid.uuid4().hex}"
        db.conn.execute(f"CREATE TEMP TABLE {backup_name} AS SELECT * FROM {table_name}")
        backups[table_name] = backup_name
    return backups


def _restore_projection_tables(db: SimulationDB, backups: dict[str, str]) -> None:
    try:
        for table_name, backup_name in backups.items():
            db.conn.execute(f"DELETE FROM {table_name}")
            db.conn.execute(f"INSERT INTO {table_name} SELECT * FROM {backup_name}")
    finally:
        _cleanup_projection_backups(db, backups)


def _cleanup_projection_backups(db: SimulationDB, backups: dict[str, str]) -> None:
    for backup_name in backups.values():
        try:
            db.conn.execute(f"DROP TABLE IF EXISTS {backup_name}")
        except Exception:
            continue


def build_world_materialization_plan(
    *,
    manifest: FactSegmentManifest,
    touched_node_kinds: Iterable[str],
    refresh_policy: WorldMaterializationPolicy | None = None,
) -> WorldMaterializationPlan:
    """Build the explainable topological plan for one world segment."""

    policy = refresh_policy or WorldMaterializationPolicy()
    normalized_kinds = tuple(str(kind).strip() for kind in touched_node_kinds if str(kind).strip())
    projection_plan = build_projection_refresh_plan(touched_node_kinds=normalized_kinds)
    segment_step = WorldMaterializationStep(
        name=f"segment:{manifest.segment_id}",
        incremental=True,
        impacted=True,
        reason="append-only world fact segment arrival",
        notes=(f"row_count={manifest.row_count}", f"trigger={policy.trigger.value}"),
    )
    base_steps = [
        WorldMaterializationStep(
            name="world.world_facts",
            depends_on=(segment_step.name,),
            incremental=True,
            impacted=manifest.row_count > 0,
            reason="insert only new facts by fact_id",
        ),
        WorldMaterializationStep(
            name="world.world_nodes",
            depends_on=("world.world_facts",),
            incremental=True,
            impacted=bool(normalized_kinds),
            reason="merge touched node envelopes from ranked attribute facts",
        ),
        WorldMaterializationStep(
            name="world.world_edges",
            depends_on=("world.world_facts",),
            incremental=True,
            impacted=manifest.row_count > 0,
            reason="insert only new relationship facts as graph edges",
        ),
    ]
    projection_steps = [
        WorldMaterializationStep(
            name=f"projection:{step.name}",
            depends_on=(
                "world.world_nodes",
                "world.world_edges",
                *(f"projection:{dep}" for dep in step.depends_on),
            ),
            incremental=step.supports_incremental,
            impacted=True,
            reason=step.reason,
            notes=(f"targets={','.join(step.target_tables)}",),
        )
        for step in projection_plan.steps
    ]
    kuzu_step = WorldMaterializationStep(
        name="kuzu.export",
        depends_on=("world.world_nodes", "world.world_edges"),
        incremental=False,
        impacted=False,
        reason="explicit rebuild-only contract; no incremental Kuzu updates",
        notes=(
            "mode=rebuild_only",
            "cost grows with full node/edge export volume",
        ),
    )
    return WorldMaterializationPlan(steps=(segment_step, *base_steps, *projection_steps, kuzu_step))


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
    db: SimulationDB,
    manifest: FactSegmentManifest,
    *,
    plan: WorldMaterializationPlan | None = None,
) -> WorldMaterializeSegmentStats:
    stats = WorldMaterializeSegmentStats(
        segment_id=manifest.segment_id,
        segment_sha256=manifest.sha256,
        row_count=manifest.row_count,
        facts_inserted=0,
        nodes_touched=0,
        edges_inserted=0,
        projections_updated=0,
        plan=plan or WorldMaterializationPlan(),
    )
    _record_segment_meta(db, manifest, stats)
    return stats


def _record_segment_meta(
    db: SimulationDB,
    manifest: FactSegmentManifest,
    stats: WorldMaterializeSegmentStats,
) -> None:
    notes_payload = None
    if stats.notes or stats.projection_names or stats.plan.steps:
        notes_payload = json.dumps(
            {
                "projection_names": list(stats.projection_names),
                "notes": list(stats.notes),
                "plan": list(stats.plan.explain()),
            },
            sort_keys=True,
        )
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
            notes_payload,
        ],
    )


def _time_partition_for_manifest(
    manifest: FactSegmentManifest,
    *,
    granularity: str,
) -> str:
    raw_value = manifest.time_end or manifest.time_start
    if raw_value is None:
        return "unbounded"
    try:
        parsed = parse_datetime_utc(raw_value, what="world shard time partition")
    except Exception:
        return "unbounded"
    if granularity == "day":
        return parsed.strftime("%Y-%m-%d")
    if granularity == "year":
        return parsed.strftime("%Y")
    return parsed.strftime("%Y-%m")


def _group_manifests_by_tenant(
    manifests: Sequence[FactSegmentManifest],
) -> dict[str, list[FactSegmentManifest]]:
    grouped: dict[str, list[FactSegmentManifest]] = {}
    for manifest in manifests:
        stats = manifest.stats if isinstance(manifest.stats, dict) else {}
        tenant_id = str(stats.get("tenant_id", "") or "").strip()
        if tenant_id:
            grouped.setdefault(tenant_id, []).append(manifest)
    return grouped


__all__ = [
    "WorldMaterializationPlan",
    "WorldMaterializationPolicy",
    "WorldMaterializationShard",
    "WorldMaterializationStep",
    "WorldMaterializeSegmentStats",
    "WorldMaterializeStats",
    "WorldProjectionFailureMode",
    "WorldRefreshTrigger",
    "apply_world_segment",
    "build_world_materialization_plan",
    "ensure_world_materialized",
    "ensure_world_schema",
    "materialize_world_duckdb_from_fact_log",
    "plan_world_materialization_shards",
]
