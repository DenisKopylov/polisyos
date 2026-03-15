from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable, Literal

from polisyos.common.logger import get_logger
from polisyos.fabric.io.db import SimulationDB

from .errors import WorldKuzuNotAvailable, WorldMaterializationError, WorldSchemaError

logger = get_logger(__name__)


_DEFAULT_DDL_PATH = Path(__file__).resolve().parents[1] / "ddl" / "kuzu_world.cypher"


def ensure_world_kuzu_schema(
    *,
    kuzu_path: str | Path,
    ddl_path: Path | None = None,
    clear_on_start: bool = False,
) -> None:
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
    try:
        db = kuzu.Database(str(path))
        conn = kuzu.Connection(db)
        for statement in _iter_ddl_statements(ddl_text):
            conn.execute(statement)
    except Exception as exc:
        raise WorldSchemaError(f"failed to apply kuzu DDL: {exc}") from exc


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
    if mode != "rebuild":
        raise ValueError(f"unsupported kuzu materialization mode: {mode}")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    if kuzu_enabled is None:
        kuzu_enabled = False
    if not kuzu_enabled:
        return

    kuzu = _import_kuzu()

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
    path_sql = _sql_literal(str(csv_path))
    try:
        conn.execute(f"COPY {table_name} FROM {path_sql} (HEADER=true);")
    except Exception as exc:
        raise WorldMaterializationError(
            f"failed to import {table_name} into Kuzu from {csv_path}: {exc}"
        ) from exc


def _validate_counts(db: SimulationDB, kuzu_conn) -> None:
    duckdb_nodes = int(
        db.conn.execute("SELECT COUNT(*) FROM world.world_nodes").fetchone()[0]
    )
    duckdb_edges = int(
        db.conn.execute("SELECT COUNT(*) FROM world.world_edges").fetchone()[0]
    )

    kuzu_nodes_df = kuzu_conn.execute(
        "MATCH (n:WorldNode) RETURN COUNT(n) AS c"
    ).get_as_df()
    kuzu_edges_df = kuzu_conn.execute(
        "MATCH ()-[e:WorldEdge]->() RETURN COUNT(e) AS c"
    ).get_as_df()

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


__all__ = [
    "ensure_world_kuzu_schema",
    "materialize_world_kuzu_from_duckdb",
]
