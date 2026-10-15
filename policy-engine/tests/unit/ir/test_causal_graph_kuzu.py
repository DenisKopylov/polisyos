from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
import pytest

from polisyos.ir._internal.runtime_protocols import protocol_declared_callables_are_callable
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_graph_kuzu import (
    CausalGraphKuzuError,
    CausalGraphKuzuNotAvailableError,
    CausalGraphKuzuSchemaError,
    _count_query_result,
    _KuzuModule,
    ensure_causal_kuzu_schema,
    materialize_causal_kuzu_from_graph,
)


@runtime_checkable
class _MixedCallableProtocol(Protocol):
    label: str
    factory: Callable[[str], object]

    def execute(self) -> object: ...


class _ValidMixedCallableCandidate:
    label = "ordinary data member"

    def __init__(self) -> None:
        self.factory = lambda value: value

    def execute(self) -> object:
        return None


class _NonCallableMethodCandidate:
    label = "ordinary data member"
    factory: Callable[[str], object] = lambda value: value
    execute = 7


class _NonCallableFactoryCandidate:
    label = "ordinary data member"
    factory = 7

    def execute(self) -> object:
        return None


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
    def __init__(self, value: object) -> None:
        self._value = value

    def get_as_df(self) -> pd.DataFrame:
        return pd.DataFrame({"c": [self._value]})


class _FakeConnection:
    def __init__(self) -> None:
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


class _CountConnection:
    def __init__(self, value: object) -> None:
        self.value = value

    def execute(self, statement: str) -> _FakeResult:
        del statement
        return _FakeResult(self.value)


class _FakeKuzuModule:
    def __init__(self) -> None:
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
        "polisyos.ir.analytics.causal_graph_kuzu.importlib.import_module",
        lambda module_name: fake_kuzu,
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


def test_ensure_causal_kuzu_schema_reports_missing_optional_backend(
    monkeypatch,
    tmp_path: Path,
) -> None:
    ddl = tmp_path / "ddl.cypher"
    ddl.write_text("CREATE NODE TABLE IF NOT EXISTS CausalVar(name STRING, PRIMARY KEY(name));")

    def missing_backend(module_name: str):
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(
        "polisyos.ir.analytics.causal_graph_kuzu.importlib.import_module",
        missing_backend,
    )
    with pytest.raises(CausalGraphKuzuNotAvailableError, match="kuzu not available"):
        ensure_causal_kuzu_schema(kuzu_path=tmp_path / "causal.kuzu", ddl_path=ddl)


@pytest.mark.parametrize("member_name", ["Database", "Connection"])
def test_ensure_causal_kuzu_schema_rejects_noncallable_module_members(
    monkeypatch,
    tmp_path: Path,
    member_name: str,
) -> None:
    ddl = tmp_path / "ddl.cypher"
    ddl.write_text("CREATE NODE TABLE IF NOT EXISTS CausalVar(name STRING, PRIMARY KEY(name));")
    fake_kuzu = _FakeKuzuModule()
    fake_kuzu.__dict__[member_name] = 7
    assert isinstance(fake_kuzu, _KuzuModule)
    monkeypatch.setattr(
        "polisyos.ir.analytics.causal_graph_kuzu.importlib.import_module",
        lambda module_name: fake_kuzu,
    )

    with pytest.raises(
        CausalGraphKuzuNotAvailableError,
        match="does not expose Database and Connection",
    ):
        ensure_causal_kuzu_schema(kuzu_path=tmp_path / "causal.kuzu", ddl_path=ddl)


def test_protocol_callable_check_preserves_noncallable_data_members() -> None:
    assert isinstance(_ValidMixedCallableCandidate(), _MixedCallableProtocol)
    assert isinstance(_NonCallableMethodCandidate(), _MixedCallableProtocol)
    assert isinstance(_NonCallableFactoryCandidate(), _MixedCallableProtocol)
    assert protocol_declared_callables_are_callable(
        _ValidMixedCallableCandidate(),
        _MixedCallableProtocol,
    )
    assert not protocol_declared_callables_are_callable(
        _NonCallableMethodCandidate(),
        _MixedCallableProtocol,
    )
    assert not protocol_declared_callables_are_callable(
        _NonCallableFactoryCandidate(),
        _MixedCallableProtocol,
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (2.75, "non-integer"),
        ("3", "non-integer"),
        (True, "non-integer"),
        (-1, "negative"),
    ],
)
def test_count_query_result_rejects_non_integer_or_negative_values(
    value: object,
    message: str,
) -> None:
    with pytest.raises(CausalGraphKuzuError, match=message):
        _count_query_result(_CountConnection(value), "RETURN COUNT(n) AS c")


@pytest.mark.parametrize("value", [4, np.int64(4)])
def test_count_query_result_accepts_indexable_nonnegative_integers(value: object) -> None:
    assert _count_query_result(_CountConnection(value), "RETURN COUNT(n) AS c") == 4


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
