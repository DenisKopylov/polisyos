from __future__ import annotations

import csv
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


_DEFAULT_DDL_PATH = Path(__file__).resolve().parent / "ddl" / "kuzu_causal.cypher"


class CausalGraphKuzuError(RuntimeError):
    """Base error for causal graph Kuzu materialization."""


class CausalGraphKuzuNotAvailableError(CausalGraphKuzuError):
    """Raised when optional dependency `kuzu` is not available."""


class CausalGraphKuzuSchemaError(CausalGraphKuzuError):
    """Raised when Kuzu schema cannot be applied."""


def ensure_causal_kuzu_schema(
    *,
    kuzu_path: str | Path,
    ddl_path: Path | None = None,
    clear_on_start: bool = False,
) -> None:
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
        raise CausalGraphKuzuSchemaError(f"kuzu DDL file not found: {ddl_file}")

    kuzu = _import_kuzu()
    ddl_text = ddl_file.read_text("utf-8")
    try:
        db = kuzu.Database(str(path))
        conn = kuzu.Connection(db)
        for statement in _iter_ddl_statements(ddl_text):
            conn.execute(statement)
    except Exception as exc:
        raise CausalGraphKuzuSchemaError(f"failed to apply causal kuzu DDL: {exc}") from exc


def materialize_causal_kuzu_from_graph(
    graph: "CausalGraphModel",
    *,
    kuzu_path: str | Path,
    clear_on_start: bool = True,
    kuzu_enabled: bool | None = None,
    tmp_dir: Path | None = None,
    keep_tmp: bool = False,
) -> None:
    if kuzu_enabled is None:
        kuzu_enabled = False
    if not kuzu_enabled:
        return

    kuzu = _import_kuzu()
    ensure_causal_kuzu_schema(
        kuzu_path=kuzu_path,
        clear_on_start=clear_on_start,
    )

    tmp_path, cleanup = _prepare_tmp_dir(tmp_dir=tmp_dir, keep_tmp=keep_tmp)
    nodes_csv = tmp_path / "causal_nodes.csv"
    edges_csv = tmp_path / "causal_edges.csv"
    try:
        _export_graph_nodes_csv(graph, nodes_csv)
        _export_graph_edges_csv(graph, edges_csv)

        kuzu_db = kuzu.Database(str(kuzu_path))
        kuzu_conn = kuzu.Connection(kuzu_db)
        _copy_kuzu_table(kuzu_conn, "CausalVar", nodes_csv)
        _copy_kuzu_table(kuzu_conn, "CausalEdge", edges_csv)

        expected_nodes = len(graph.nodes)
        expected_edges = len(graph.edges)
        kuzu_nodes = int(
            kuzu_conn.execute("MATCH (n:CausalVar) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0]
        )
        kuzu_edges = int(
            kuzu_conn.execute("MATCH ()-[e:CausalEdge]->() RETURN COUNT(e) AS c")
            .get_as_df()
            .iloc[0, 0]
        )
        if kuzu_nodes != expected_nodes:
            raise CausalGraphKuzuError(
                f"kuzu node count mismatch: expected={expected_nodes}, got={kuzu_nodes}"
            )
        if kuzu_edges != expected_edges:
            raise CausalGraphKuzuError(
                f"kuzu edge count mismatch: expected={expected_edges}, got={kuzu_edges}"
            )
    except CausalGraphKuzuError:
        raise
    except Exception as exc:
        raise CausalGraphKuzuError(f"failed to materialize causal graph to kuzu: {exc}") from exc
    finally:
        if cleanup is not None:
            cleanup()
        elif tmp_dir is not None and not keep_tmp:
            _remove_tmp_files([nodes_csv, edges_csv])


def _export_graph_nodes_csv(graph: "CausalGraphModel", output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name"])
        writer.writeheader()
        for node in graph.nodes:
            writer.writerow({"name": node})


def _export_graph_edges_csv(graph: "CausalGraphModel", output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "FROM",
                "TO",
                "mark_src",
                "mark_dst",
                "lag",
                "combined_confidence",
                "graph_type",
                "sources",
                "evidence_refs",
                "metadata_json",
            ],
        )
        writer.writeheader()
        for edge in graph.edges:
            writer.writerow(
                {
                    "FROM": edge.src,
                    "TO": edge.dst,
                    "mark_src": edge.mark_src.value,
                    "mark_dst": edge.mark_dst.value,
                    "lag": edge.lag if edge.lag is not None else "",
                    "combined_confidence": (
                        edge.combined_confidence if edge.combined_confidence is not None else ""
                    ),
                    "graph_type": graph.graph_type.value,
                    "sources": json.dumps([source.value for source in edge.sources]),
                    "evidence_refs": json.dumps(edge.evidence_refs),
                    "metadata_json": json.dumps(edge.metadata, sort_keys=True),
                }
            )


def _import_kuzu():
    try:
        import kuzu

    except Exception as exc:
        raise CausalGraphKuzuNotAvailableError("kuzu not available") from exc
    return kuzu


def _iter_ddl_statements(ddl_text: str) -> list[str]:
    statements: list[str] = []
    for chunk in ddl_text.split(";"):
        lines: list[str] = []
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


def _copy_kuzu_table(conn, table_name: str, csv_path: Path) -> None:
    path_sql = _sql_literal(str(csv_path))
    try:
        conn.execute(f"COPY {table_name} FROM {path_sql} (HEADER=true);")
    except Exception as exc:
        raise CausalGraphKuzuError(
            f"failed to import {table_name} into Kuzu from {csv_path}: {exc}"
        ) from exc


def _prepare_tmp_dir(
    *, tmp_dir: Path | None, keep_tmp: bool
) -> tuple[Path, Callable[[], None] | None]:
    if tmp_dir is None:
        if keep_tmp:
            path = Path(tempfile.mkdtemp(prefix="polisyos_causal_kuzu_"))
            return path, None
        tmp_ctx = tempfile.TemporaryDirectory(prefix="polisyos_causal_kuzu_")
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


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


__all__ = [
    "CausalGraphKuzuError",
    "CausalGraphKuzuNotAvailableError",
    "CausalGraphKuzuSchemaError",
    "ensure_causal_kuzu_schema",
    "materialize_causal_kuzu_from_graph",
]
