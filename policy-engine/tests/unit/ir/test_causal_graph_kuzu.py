from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_graph_kuzu import (
    CausalGraphKuzuSchemaError,
    ensure_causal_kuzu_schema,
    materialize_causal_kuzu_from_graph,
)


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B", "C"],
        edges=[
            CausalEdge(src="A", dst="B"),
            CausalEdge(src="B", dst="C"),
        ],
    )


class _FakeResult:
    def __init__(self, value: int):
        self._value = int(value)

    def get_as_df(self):
        return pd.DataFrame({"c": [self._value]})


class _FakeConnection:
    def __init__(self):
        self.executed: list[str] = []
        self.node_count = 0
        self.edge_count = 0

    def execute(self, statement: str):
        self.executed.append(statement)
        stmt = statement.strip()
        if stmt.startswith("COPY CausalVar FROM "):
            self.node_count = _csv_row_count(_extract_sql_path(stmt))
            return _FakeResult(0)
        if stmt.startswith("COPY CausalEdge FROM "):
            self.edge_count = _csv_row_count(_extract_sql_path(stmt))
            return _FakeResult(0)
        if "MATCH (n:CausalVar) RETURN COUNT(n) AS c" in stmt:
            return _FakeResult(self.node_count)
        if "MATCH ()-[e:CausalEdge]->() RETURN COUNT(e) AS c" in stmt:
            return _FakeResult(self.edge_count)
        return _FakeResult(0)


class _FakeKuzuModule:
    def __init__(self):
        self.connections: list[_FakeConnection] = []

    class Database:
        def __init__(self, path: str):
            self.path = path

    def Connection(self, db):  # noqa: N802
        del db
        conn = _FakeConnection()
        self.connections.append(conn)
        return conn


def _extract_sql_path(stmt: str) -> Path:
    # COPY <table> FROM '<path>' (HEADER=true);
    after_from = stmt.split(" FROM ", 1)[1]
    quoted = after_from.split(" ", 1)[0]
    return Path(quoted.strip("'"))


def _csv_row_count(path: Path) -> int:
    lines = path.read_text("utf-8").splitlines()
    return max(0, len(lines) - 1)


def test_ensure_causal_kuzu_schema_applies_ddl(monkeypatch, tmp_path: Path) -> None:
    fake_kuzu = _FakeKuzuModule()
    monkeypatch.setattr(
        "polisyos.ir.analytics.causal_graph_kuzu._import_kuzu",
        lambda: fake_kuzu,
    )

    ddl = tmp_path / "ddl.cypher"
    ddl.write_text(
        """
        -- comment
        CREATE NODE TABLE IF NOT EXISTS CausalVar(name STRING, PRIMARY KEY(name));
        CREATE REL TABLE IF NOT EXISTS CausalEdge(FROM CausalVar TO CausalVar, mark_src STRING);
        """,
        encoding="utf-8",
    )

    ensure_causal_kuzu_schema(
        kuzu_path=tmp_path / "causal.kuzu",
        ddl_path=ddl,
        clear_on_start=True,
    )
    assert fake_kuzu.connections
    executed = fake_kuzu.connections[-1].executed
    assert any("CREATE NODE TABLE" in stmt for stmt in executed)
    assert any("CREATE REL TABLE" in stmt for stmt in executed)


def test_ensure_causal_kuzu_schema_rejects_missing_ddl(tmp_path: Path) -> None:
    with pytest.raises(CausalGraphKuzuSchemaError, match="DDL file not found"):
        ensure_causal_kuzu_schema(
            kuzu_path=tmp_path / "causal.kuzu",
            ddl_path=tmp_path / "missing.cypher",
        )


def test_materialize_causal_kuzu_from_graph_uses_bulk_copy(monkeypatch, tmp_path: Path) -> None:
    fake_kuzu = _FakeKuzuModule()
    monkeypatch.setattr(
        "polisyos.ir.analytics.causal_graph_kuzu._import_kuzu",
        lambda: fake_kuzu,
    )

    materialize_causal_kuzu_from_graph(
        _graph(),
        kuzu_path=tmp_path / "causal.kuzu",
        kuzu_enabled=True,
    )

    # First connection is schema setup, second is materialization.
    materialize_conn = fake_kuzu.connections[-1]
    assert any(stmt.startswith("COPY CausalVar FROM ") for stmt in materialize_conn.executed)
    assert any(stmt.startswith("COPY CausalEdge FROM ") for stmt in materialize_conn.executed)


def test_materialize_causal_kuzu_real_smoke(tmp_path: Path) -> None:
    kuzu = pytest.importorskip("kuzu")

    graph = _graph()
    kuzu_path = tmp_path / "causal_real.kuzu"
    materialize_causal_kuzu_from_graph(
        graph,
        kuzu_path=kuzu_path,
        kuzu_enabled=True,
    )

    db = kuzu.Database(str(kuzu_path))
    conn = kuzu.Connection(db)
    node_count = int(
        conn.execute("MATCH (n:CausalVar) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0]
    )
    edge_count = int(
        conn.execute("MATCH ()-[e:CausalEdge]->() RETURN COUNT(e) AS c").get_as_df().iloc[0, 0]
    )
    assert node_count == len(graph.nodes)
    assert edge_count == len(graph.edges)
