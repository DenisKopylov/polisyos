"""Export the materialized world graph from DuckDB into a Kuzu graph database."""

from __future__ import annotations

import contextlib
import re
import shutil
import tempfile
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from polisyos.common.logger import get_logger
from polisyos.fabric.io.db import SimulationDB

from .errors import WorldKuzuNotAvailable, WorldMaterializationError, WorldSchemaError

logger = get_logger(__name__)

_KUZU_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_DEFAULT_DDL_PATH = Path(__file__).resolve().parents[1] / "ddl" / "kuzu_world.cypher"


@dataclass(frozen=True)
class WorldKuzuRefreshContract:
    """Explicit contract for the Kuzu export path."""

    mode: Literal["rebuild"] = "rebuild"
    incremental_supported: bool = False
    estimated_nodes: int | None = None
    estimated_edges: int | None = None
    batch_size: int = 50_000
    notes: tuple[str, ...] = (
        "Kuzu export is rebuild-only.",
        "Incremental graph maintenance is not implemented yet.",
        "Cost scales with full world node and edge counts.",
    )


@dataclass(frozen=True)
class WorldGraphNodeRecord:
    """One world-node snapshot row reusable for Kuzu or in-memory reasoning."""

    node_id: str
    kind: str
    label: str | None = None
    artifact_id: str | None = None


@dataclass(frozen=True)
class WorldGraphEdgeRecord:
    """One world-edge snapshot row reusable for Kuzu or in-memory reasoning."""

    source_id: str
    target_id: str
    kind: str
    predicate_id: str | None = None
    tx_time: str | None = None
    valid_time: str | None = None
    confidence: float | None = None
    weight: float | None = None
    event_id: str | None = None


@dataclass(frozen=True)
class WorldGraphNeighborhood:
    """Generic neighborhood traversal result."""

    center_id: str
    nodes: tuple[WorldGraphNodeRecord, ...]
    edges: tuple[WorldGraphEdgeRecord, ...]
    max_hops: int


@dataclass(frozen=True)
class WorldGraphSourceOverlap:
    """Answer whether multiple upstream sources overlap around one entity."""

    center_id: str
    overlapping_sources: tuple[WorldGraphNodeRecord, ...]
    related_entities: tuple[WorldGraphNodeRecord, ...]
    traversed_edges: tuple[WorldGraphEdgeRecord, ...]


@dataclass(frozen=True)
class WorldGraphConflictNeighborhood:
    """Conflict-focused local view rooted at an entity."""

    center_id: str
    conflict_nodes: tuple[WorldGraphNodeRecord, ...]
    evidence_edges: tuple[WorldGraphEdgeRecord, ...]


@dataclass(frozen=True)
class WorldGraphPolicyImpact:
    """Downstream policy-domain impact view rooted at an entity."""

    center_id: str
    impacted_nodes: tuple[WorldGraphNodeRecord, ...]
    traversed_edges: tuple[WorldGraphEdgeRecord, ...]
    max_hops: int


class WorldGraphSnapshot:
    """Small in-memory world graph mirror for tests and fallback reasoning."""

    def __init__(
        self,
        nodes: Sequence[WorldGraphNodeRecord],
        edges: Sequence[WorldGraphEdgeRecord],
    ) -> None:
        self.nodes = {node.node_id: node for node in nodes}
        self.edges = tuple(edges)
        self._outgoing: dict[str, list[WorldGraphEdgeRecord]] = defaultdict(list)
        self._incoming: dict[str, list[WorldGraphEdgeRecord]] = defaultdict(list)
        for edge in edges:
            self._outgoing[edge.source_id].append(edge)
            self._incoming[edge.target_id].append(edge)

    @classmethod
    def from_duckdb(cls, db: SimulationDB) -> WorldGraphSnapshot:
        node_rows = db.conn.execute(
            """
            SELECT node_id, kind, label, artifact_id
            FROM world.world_nodes
            ORDER BY node_id
            """
        ).fetchall()
        edge_rows = db.conn.execute(
            """
            SELECT source_id, target_id, kind, predicate_id, tx_time, valid_time, confidence, weight, event_id
            FROM world.world_edges
            ORDER BY source_id, target_id, kind
            """
        ).fetchall()
        return cls(
            nodes=[
                WorldGraphNodeRecord(
                    node_id=str(row[0]),
                    kind=str(row[1]),
                    label=None if row[2] is None else str(row[2]),
                    artifact_id=None if row[3] is None else str(row[3]),
                )
                for row in node_rows
            ],
            edges=[
                WorldGraphEdgeRecord(
                    source_id=str(row[0]),
                    target_id=str(row[1]),
                    kind=str(row[2]),
                    predicate_id=None if row[3] is None else str(row[3]),
                    tx_time=None if row[4] is None else str(row[4]),
                    valid_time=None if row[5] is None else str(row[5]),
                    confidence=None if row[6] is None else float(row[6]),
                    weight=None if row[7] is None else float(row[7]),
                    event_id=None if row[8] is None else str(row[8]),
                )
                for row in edge_rows
            ],
        )

    def node(self, node_id: str) -> WorldGraphNodeRecord | None:
        return self.nodes.get(node_id)

    def outgoing(self, node_id: str) -> tuple[WorldGraphEdgeRecord, ...]:
        return tuple(self._outgoing.get(node_id, ()))

    def incoming(self, node_id: str) -> tuple[WorldGraphEdgeRecord, ...]:
        return tuple(self._incoming.get(node_id, ()))


def build_world_kuzu_lineage_query(
    node_id: str, *, max_hops: int = 2
) -> tuple[str, dict[str, object]]:
    hops = max(1, max_hops)
    query = f"""
        MATCH path = (seed:WorldNode)-[:WorldEdge*1..{hops}]-(neighbor:WorldNode)
        WHERE seed.id = $node_id
        RETURN path
    """
    return query.strip(), {"node_id": node_id}


def build_world_kuzu_entity_neighborhood_query(
    node_id: str,
    *,
    max_hops: int = 2,
) -> tuple[str, dict[str, object]]:
    hops = max(1, max_hops)
    query = f"""
        MATCH path = (seed:WorldNode)-[:WorldEdge*1..{hops}]-(neighbor:WorldNode)
        WHERE seed.id = $node_id
        RETURN path
    """
    return query.strip(), {"node_id": node_id}


def build_world_kuzu_conflict_query(
    node_id: str, *, max_hops: int = 2
) -> tuple[str, dict[str, object]]:
    hops = max(1, max_hops)
    query = f"""
        MATCH path = (seed:WorldNode)-[edges:WorldEdge*1..{hops}]-(neighbor:WorldNode)
        WHERE seed.id = $node_id
          AND ANY(edge IN edges WHERE edge.kind CONTAINS 'conflict' OR edge.kind CONTAINS 'contrad')
        RETURN path
    """
    return query.strip(), {"node_id": node_id}


def build_world_kuzu_policy_impact_query(
    node_id: str,
    *,
    max_hops: int = 3,
) -> tuple[str, dict[str, object]]:
    hops = max(1, max_hops)
    query = f"""
        MATCH path = (seed:WorldNode)-[:WorldEdge*1..{hops}]->(neighbor:WorldNode)
        WHERE seed.id = $node_id
          AND (neighbor.kind CONTAINS 'policy' OR neighbor.kind CONTAINS 'impact' OR neighbor.kind CONTAINS 'domain')
        RETURN path
    """
    return query.strip(), {"node_id": node_id}


def query_world_entity_neighborhood(
    snapshot: WorldGraphSnapshot,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphNeighborhood:
    visited_nodes: set[str] = {node_id}
    visited_edges: set[tuple[str, str, str]] = set()
    queue = deque([(node_id, 0)])
    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for edge in (*snapshot.outgoing(current_id), *snapshot.incoming(current_id)):
            edge_key = (edge.source_id, edge.target_id, edge.kind)
            visited_edges.add(edge_key)
            neighbor_id = edge.target_id if edge.source_id == current_id else edge.source_id
            if neighbor_id in visited_nodes:
                continue
            visited_nodes.add(neighbor_id)
            queue.append((neighbor_id, depth + 1))
    nodes = tuple(snapshot.nodes[node] for node in sorted(visited_nodes) if node in snapshot.nodes)
    edges = tuple(
        edge
        for edge in snapshot.edges
        if (edge.source_id, edge.target_id, edge.kind) in visited_edges
    )
    return WorldGraphNeighborhood(
        center_id=node_id,
        nodes=nodes,
        edges=edges,
        max_hops=max_hops,
    )


def query_world_source_overlap(
    snapshot: WorldGraphSnapshot,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphSourceOverlap:
    neighborhood = query_world_entity_neighborhood(snapshot, node_id, max_hops=max_hops)
    overlapping_sources = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id and ("source" in node.kind or node.artifact_id is not None)
    )
    related_entities = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id and node not in overlapping_sources
    )
    return WorldGraphSourceOverlap(
        center_id=node_id,
        overlapping_sources=overlapping_sources,
        related_entities=related_entities,
        traversed_edges=neighborhood.edges,
    )


def query_world_conflict_neighborhood(
    snapshot: WorldGraphSnapshot,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphConflictNeighborhood:
    neighborhood = query_world_entity_neighborhood(snapshot, node_id, max_hops=max_hops)
    conflict_nodes = tuple(
        node for node in neighborhood.nodes if "conflict" in node.kind or "contrad" in node.kind
    )
    evidence_edges = tuple(
        edge for edge in neighborhood.edges if "conflict" in edge.kind or "contrad" in edge.kind
    )
    return WorldGraphConflictNeighborhood(
        center_id=node_id,
        conflict_nodes=conflict_nodes,
        evidence_edges=evidence_edges,
    )


def query_world_policy_impact(
    snapshot: WorldGraphSnapshot,
    node_id: str,
    *,
    max_hops: int = 3,
) -> WorldGraphPolicyImpact:
    neighborhood = query_world_entity_neighborhood(snapshot, node_id, max_hops=max_hops)
    impacted_nodes = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id
        and ("policy" in node.kind or "impact" in node.kind or "domain" in node.kind)
    )
    traversed_ids = {node.node_id for node in impacted_nodes} | {node_id}
    traversed_edges = tuple(
        edge
        for edge in neighborhood.edges
        if edge.source_id in traversed_ids or edge.target_id in traversed_ids
    )
    return WorldGraphPolicyImpact(
        center_id=node_id,
        impacted_nodes=impacted_nodes,
        traversed_edges=traversed_edges,
        max_hops=max_hops,
    )


def query_world_kuzu_entity_neighborhood(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphNeighborhood:
    """Query a live Kuzu graph for one entity neighborhood."""

    nodes = _fetch_kuzu_neighborhood_nodes(kuzu_conn, node_id, max_hops=max_hops)
    edges = _fetch_kuzu_neighborhood_edges(kuzu_conn, node_id, max_hops=max_hops)
    return WorldGraphNeighborhood(
        center_id=node_id,
        nodes=nodes,
        edges=edges,
        max_hops=max_hops,
    )


def query_world_kuzu_source_overlap(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphSourceOverlap:
    """Resolve source overlap directly from a live Kuzu traversal."""

    neighborhood = query_world_kuzu_entity_neighborhood(
        kuzu_conn,
        node_id,
        max_hops=max_hops,
    )
    overlapping_sources = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id and ("source" in node.kind or node.artifact_id is not None)
    )
    related_entities = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id and node not in overlapping_sources
    )
    return WorldGraphSourceOverlap(
        center_id=node_id,
        overlapping_sources=overlapping_sources,
        related_entities=related_entities,
        traversed_edges=neighborhood.edges,
    )


def query_world_kuzu_conflict_neighborhood(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int = 2,
) -> WorldGraphConflictNeighborhood:
    """Resolve conflict neighborhoods from live Kuzu traversal results."""

    neighborhood = query_world_kuzu_entity_neighborhood(
        kuzu_conn,
        node_id,
        max_hops=max_hops,
    )
    conflict_nodes = tuple(
        node for node in neighborhood.nodes if "conflict" in node.kind or "contrad" in node.kind
    )
    evidence_edges = tuple(
        edge for edge in neighborhood.edges if "conflict" in edge.kind or "contrad" in edge.kind
    )
    return WorldGraphConflictNeighborhood(
        center_id=node_id,
        conflict_nodes=conflict_nodes,
        evidence_edges=evidence_edges,
    )


def query_world_kuzu_policy_impact(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int = 3,
) -> WorldGraphPolicyImpact:
    """Resolve downstream policy impact directly from a live Kuzu traversal."""

    neighborhood = query_world_kuzu_entity_neighborhood(
        kuzu_conn,
        node_id,
        max_hops=max_hops,
    )
    impacted_nodes = tuple(
        node
        for node in neighborhood.nodes
        if node.node_id != node_id
        and ("policy" in node.kind or "impact" in node.kind or "domain" in node.kind)
    )
    traversed_ids = {node.node_id for node in impacted_nodes} | {node_id}
    traversed_edges = tuple(
        edge
        for edge in neighborhood.edges
        if edge.source_id in traversed_ids or edge.target_id in traversed_ids
    )
    return WorldGraphPolicyImpact(
        center_id=node_id,
        impacted_nodes=impacted_nodes,
        traversed_edges=traversed_edges,
        max_hops=max_hops,
    )


def explain_world_kuzu_refresh_contract(
    db: SimulationDB | None = None,
    *,
    batch_size: int = 50_000,
) -> WorldKuzuRefreshContract:
    """Describe the rebuild-only Kuzu contract and its current cost surface."""

    estimated_nodes = None
    estimated_edges = None
    if db is not None:
        estimated_nodes = int(
            db.conn.execute("SELECT COUNT(*) FROM world.world_nodes").fetchone()[0]
        )
        estimated_edges = int(
            db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0]
        )
    return WorldKuzuRefreshContract(
        estimated_nodes=estimated_nodes,
        estimated_edges=estimated_edges,
        batch_size=batch_size,
    )


def ensure_world_kuzu_schema(
    *,
    kuzu_path: str | Path,
    ddl_path: Path | None = None,
    clear_on_start: bool = False,
) -> None:
    """Create or reset the Kuzu schema used for world-graph projection."""
    kuzu = _import_kuzu()
    path = Path(kuzu_path)
    if clear_on_start and path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)

    ddl_file = Path(ddl_path) if ddl_path is not None else _DEFAULT_DDL_PATH
    if not ddl_file.exists():
        raise WorldSchemaError(f"kuzu DDL file not found: {ddl_file}")

    ddl_text = ddl_file.read_text("utf-8")
    db = None
    conn = None
    try:
        db = kuzu.Database(str(path))
        conn = kuzu.Connection(db)
        for statement in _iter_ddl_statements(ddl_text):
            conn.execute(statement)
    except Exception as exc:
        raise WorldSchemaError(f"failed to apply kuzu DDL: {exc}") from exc
    finally:
        _close_kuzu_resource(conn)
        _close_kuzu_resource(db)


def materialize_world_kuzu_from_duckdb(
    db: SimulationDB,
    *,
    kuzu_path: str | Path,
    mode: Literal["rebuild"] = "rebuild",
    clear_on_start: bool = True,
    batch_size: int = 50_000,
    tmp_dir: Path | None = None,
    keep_tmp: bool = False,
    kuzu_enabled: bool | None = None,
) -> None:
    """Rebuild the Kuzu world graph from the already materialized DuckDB world tables."""
    if mode != "rebuild":
        raise ValueError(f"unsupported kuzu materialization mode: {mode}")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    if kuzu_enabled is None:
        kuzu_enabled = False
    if not kuzu_enabled:
        return

    kuzu = _import_kuzu()
    contract = explain_world_kuzu_refresh_contract(db, batch_size=batch_size)
    logger.info(
        "Running rebuild-only Kuzu export",
        mode=contract.mode,
        incremental_supported=contract.incremental_supported,
        estimated_nodes=contract.estimated_nodes,
        estimated_edges=contract.estimated_edges,
        batch_size=contract.batch_size,
    )

    ensure_world_kuzu_schema(
        kuzu_path=kuzu_path,
        clear_on_start=clear_on_start,
    )

    tmp_path, cleanup = _prepare_tmp_dir(tmp_dir=tmp_dir, keep_tmp=keep_tmp)
    nodes_csv = tmp_path / "world_nodes.csv"
    edges_csv = tmp_path / "world_edges.csv"

    try:
        _export_world_nodes(db, nodes_csv)
        _export_world_edges(db, edges_csv)

        kuzu_db = kuzu.Database(str(kuzu_path))
        kuzu_conn = kuzu.Connection(kuzu_db)

        _copy_kuzu_table(kuzu_conn, "WorldNode", nodes_csv)
        _copy_kuzu_table(kuzu_conn, "WorldEdge", edges_csv)

        _validate_counts(db, kuzu_conn)
    except WorldMaterializationError:
        raise
    except Exception as exc:
        raise WorldMaterializationError(str(exc)) from exc
    finally:
        _close_kuzu_resource(locals().get("kuzu_conn"))
        _close_kuzu_resource(locals().get("kuzu_db"))
        if cleanup is not None:
            cleanup()
        elif tmp_dir is not None and not keep_tmp:
            _remove_tmp_files([nodes_csv, edges_csv])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_kuzu():
    try:
        import kuzu

    except Exception as exc:
        raise WorldKuzuNotAvailable("kuzu not available") from exc
    return kuzu


def _close_kuzu_resource(resource) -> None:
    if resource is None:
        return
    close = getattr(resource, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()


def _iter_ddl_statements(ddl_text: str) -> list[str]:
    statements: list[str] = []
    for chunk in ddl_text.split(";"):
        lines = []
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("--") or stripped.startswith("//"):
                continue
            lines.append(line)
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


def _prepare_tmp_dir(
    *, tmp_dir: Path | None, keep_tmp: bool
) -> tuple[Path, Callable[[], None] | None]:
    if tmp_dir is None:
        if keep_tmp:
            path = Path(tempfile.mkdtemp(prefix="polisyos_world_kuzu_"))
            return path, None
        tmp_ctx = tempfile.TemporaryDirectory(prefix="polisyos_world_kuzu_")
        return Path(tmp_ctx.name), tmp_ctx.cleanup

    path = Path(tmp_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path, None


def _remove_tmp_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)


def _export_world_nodes(db: SimulationDB, output_path: Path) -> None:
    sql = """
        SELECT
            node_id AS id,
            kind,
            label,
            artifact_id
        FROM world.world_nodes
        ORDER BY node_id
    """
    _duckdb_copy(db, sql, output_path)


def _export_world_edges(db: SimulationDB, output_path: Path) -> None:
    sql = """
        SELECT
            src_id AS "FROM",
            dst_id AS "TO",
            edge_id,
            kind,
            predicate_id,
            tx_time,
            valid_time,
            NULL AS confidence,
            NULL AS weight,
            CASE
              WHEN kind IN ('prov.used','prov.was_associated_with')
                AND src_id LIKE 'event.%' THEN src_id
              WHEN kind = 'prov.was_generated_by' AND dst_id LIKE 'event.%' THEN dst_id
              ELSE NULL
            END AS event_id
        FROM world.world_edges
        ORDER BY edge_id
    """
    _duckdb_copy(db, sql, output_path)


def _duckdb_copy(db: SimulationDB, select_sql: str, output_path: Path) -> None:
    path_sql = _sql_literal(str(output_path))
    try:
        db.conn.execute(
            "\n".join(
                [
                    "COPY (",
                    select_sql.strip(),
                    ") TO ",
                    f"{path_sql} (HEADER, DELIMITER ',', QUOTE '\"', ESCAPE '\"');",
                ]
            )
        )
    except Exception as exc:
        raise WorldMaterializationError(
            f"failed to export CSV via DuckDB COPY to {output_path}: {exc}"
        ) from exc


def _copy_kuzu_table(conn, table_name: str, csv_path: Path) -> None:
    if not _KUZU_IDENTIFIER_RE.fullmatch(table_name):
        raise WorldMaterializationError(f"unsafe Kuzu table identifier: {table_name!r}")
    path_sql = _sql_literal(str(csv_path))
    try:
        conn.execute(f"COPY {table_name} FROM {path_sql} (HEADER=true);")
    except Exception as exc:
        raise WorldMaterializationError(
            f"failed to import {table_name} into Kuzu from {csv_path}: {exc}"
        ) from exc


def _validate_counts(db: SimulationDB, kuzu_conn) -> None:
    duckdb_nodes = int(db.conn.execute("SELECT COUNT(*) FROM world.world_nodes").fetchone()[0])
    duckdb_edges = int(db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0])

    kuzu_nodes_df = kuzu_conn.execute("MATCH (n:WorldNode) RETURN COUNT(n) AS c").get_as_df()
    kuzu_edges_df = kuzu_conn.execute("MATCH ()-[e:WorldEdge]->() RETURN COUNT(e) AS c").get_as_df()

    kuzu_nodes = int(kuzu_nodes_df.iloc[0, 0])
    kuzu_edges = int(kuzu_edges_df.iloc[0, 0])

    if duckdb_nodes != kuzu_nodes:
        raise WorldMaterializationError(
            f"kuzu nodes count mismatch: duckdb={duckdb_nodes} kuzu={kuzu_nodes}"
        )
    if duckdb_edges != kuzu_edges:
        raise WorldMaterializationError(
            f"kuzu edges count mismatch: duckdb={duckdb_edges} kuzu={kuzu_edges}"
        )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _fetch_kuzu_neighborhood_nodes(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int,
) -> tuple[WorldGraphNodeRecord, ...]:
    query = _build_kuzu_neighborhood_nodes_query(max_hops=max_hops)
    rows = _execute_kuzu_df(kuzu_conn, query, {"node_id": node_id})
    nodes: dict[str, WorldGraphNodeRecord] = {}
    for row in rows:
        record = WorldGraphNodeRecord(
            node_id=str(row["node_id"]),
            kind=str(row["kind"]),
            label=_optional_text(row.get("label")),
            artifact_id=_optional_text(row.get("artifact_id")),
        )
        nodes[record.node_id] = record
    return tuple(nodes[node] for node in sorted(nodes))


def _fetch_kuzu_neighborhood_edges(
    kuzu_conn: Any,
    node_id: str,
    *,
    max_hops: int,
) -> tuple[WorldGraphEdgeRecord, ...]:
    edge_ids_query = _build_kuzu_neighborhood_edge_ids_query(max_hops=max_hops)
    edge_id_rows = _execute_kuzu_df(kuzu_conn, edge_ids_query, {"node_id": node_id})
    edge_ids = sorted(
        {
            _optional_text(row.get("edge_id"))
            for row in edge_id_rows
            if _optional_text(row.get("edge_id"))
        }
    )
    if not edge_ids:
        return ()
    edge_rows_query = _build_kuzu_neighborhood_edge_rows_query()
    rows = _execute_kuzu_df(kuzu_conn, edge_rows_query, {"edge_ids": edge_ids})
    edges: dict[tuple[str, str, str], WorldGraphEdgeRecord] = {}
    for row in rows:
        record = WorldGraphEdgeRecord(
            source_id=str(row["source_id"]),
            target_id=str(row["target_id"]),
            kind=str(row["kind"]),
            predicate_id=_optional_text(row.get("predicate_id")),
            tx_time=_optional_text(row.get("tx_time")),
            valid_time=_optional_text(row.get("valid_time")),
            confidence=_optional_float(row.get("confidence")),
            weight=_optional_float(row.get("weight")),
            event_id=_optional_text(row.get("event_id")),
        )
        edges[(record.source_id, record.target_id, record.kind)] = record
    return tuple(edges[key] for key in sorted(edges, key=lambda item: (item[0], item[1], item[2])))


def _build_kuzu_neighborhood_nodes_query(*, max_hops: int) -> str:
    hops = max(1, max_hops)
    return f"""
        MATCH path = (seed:WorldNode)-[:WorldEdge*1..{hops}]-(neighbor:WorldNode)
        WHERE seed.id = $node_id
        UNWIND NODES(path) AS node
        RETURN DISTINCT
            node.id AS node_id,
            node.kind AS kind,
            node.label AS label,
            node.artifact_id AS artifact_id
        UNION
        MATCH (seed:WorldNode)
        WHERE seed.id = $node_id
        RETURN DISTINCT
            seed.id AS node_id,
            seed.kind AS kind,
            seed.label AS label,
            seed.artifact_id AS artifact_id
    """.strip()


def _build_kuzu_neighborhood_edge_ids_query(*, max_hops: int) -> str:
    hops = max(1, max_hops)
    return f"""
        MATCH path = (seed:WorldNode)-[edges:WorldEdge*1..{hops}]-(neighbor:WorldNode)
        WHERE seed.id = $node_id
        UNWIND RELS(path) AS edge
        RETURN DISTINCT edge.edge_id AS edge_id
    """.strip()


def _build_kuzu_neighborhood_edge_rows_query() -> str:
    return """
        MATCH (src:WorldNode)-[edge:WorldEdge]->(dst:WorldNode)
        WHERE edge.edge_id IN $edge_ids
        RETURN DISTINCT
            src.id AS source_id,
            dst.id AS target_id,
            edge.kind AS kind,
            edge.predicate_id AS predicate_id,
            edge.tx_time AS tx_time,
            edge.valid_time AS valid_time,
            edge.confidence AS confidence,
            edge.weight AS weight,
            edge.event_id AS event_id
    """.strip()


def _execute_kuzu_df(
    kuzu_conn: Any,
    query: str,
    params: dict[str, object],
) -> list[dict[str, object]]:
    result = kuzu_conn.execute(query, params)
    if hasattr(result, "get_as_df"):
        frame = result.get_as_df()
        if hasattr(frame, "to_dict"):
            return list(frame.to_dict(orient="records"))
    if hasattr(result, "to_dict"):
        return list(result.to_dict(orient="records"))
    raise WorldMaterializationError("Kuzu query result does not expose a tabular DataFrame view")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


__all__ = [
    "WorldKuzuRefreshContract",
    "ensure_world_kuzu_schema",
    "explain_world_kuzu_refresh_contract",
    "materialize_world_kuzu_from_duckdb",
]
