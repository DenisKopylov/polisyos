from __future__ import annotations

import json
from collections.abc import Callable
from itertools import permutations
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
import pytest

from polisyos.ir._internal.runtime_protocols import protocol_declared_callables_are_callable
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
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
        if stmt == "CALL table_info('CausalEdge') RETURN name":
            return _FakePropertyResult(["payload_json"])
        return _FakeResult(0)


class _FakePropertyResult:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def get_as_df(self) -> pd.DataFrame:
        return pd.DataFrame({"name": self.names})


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


@pytest.mark.parametrize(
    "second_edge",
    [
        CausalEdge(src="A", dst="B"),
        CausalEdge(src="A", dst="B", mark_src=EdgeMark.ARROW),
        CausalEdge(src="A", dst="B", lag=1),
        CausalEdge(src="A", dst="B", lag=2),
    ],
    ids=["identical", "bidirected", "lag1", "lag2"],
)
def test_direct_kuzu_refuses_relation_collision_before_first_write(second_edge: CausalEdge) -> None:
    """Endpoint-only MERGE cannot represent multiple relation occurrences."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["A", "B"],
        edges=[CausalEdge(src="A", dst="B"), second_edge],
    )
    writes: list[str] = []

    class RecordingConnection:
        def execute(self, statement: str, parameters: object) -> None:
            del parameters
            writes.append(statement)

    with pytest.raises(ValueError, match="materialize_causal_kuzu_from_graph"):
        graph.to_kuzu(RecordingConnection())
    assert writes == []


def test_kuzu_rows_preserve_all_causal_edge_payload_fields(tmp_path: Path) -> None:
    """Confidence-distinct occurrences must not become identical exported rows."""
    from polisyos.ir.analytics.causal_graph_kuzu import _export_graph_edges_csv

    first = CausalEdge(
        src="A",
        dst="B",
        data_confidence=0.1,
        literature_confidence=0.2,
        llm_confidence=0.3,
        expert_confidence=0.4,
        simulation_confidence=0.5,
        combined_confidence=0.6,
        unsupported_by_evidence=True,
        p_value=0.01,
        evidence_refs=["selected:evidence"],
        metadata={"nested": {"repeated": [1, 1, 2]}},
    )
    second = first.model_copy(update={"data_confidence": 0.9})
    graph = CausalGraphModel(graph_type=GraphType.ADMG, nodes=["A", "B"], edges=[first, second])
    rows = graph.kuzu_edge_rows
    assert rows[0] != rows[1]
    assert [json.loads(row["payload_json"]) for row in rows] == [
        edge.model_dump(mode="json") for edge in graph.edges
    ]
    path = tmp_path / "edges.csv"
    _export_graph_edges_csv(graph, path)
    import csv

    with path.open(newline="") as stream:
        exported = list(csv.DictReader(stream))
    assert [json.loads(row["payload_json"]) for row in exported] == [
        first.model_dump(mode="json"),
        second.model_dump(mode="json"),
    ]


def test_kuzu_bulk_unsupported_incremental_policy_refuses_before_backend_or_writes(
    monkeypatch, tmp_path: Path
) -> None:
    def unexpected_backend():
        raise AssertionError("unsupported policy must refuse before backend or schema writes")

    monkeypatch.setattr("polisyos.ir.analytics.causal_graph_kuzu._import_kuzu", unexpected_backend)
    with pytest.raises(CausalGraphKuzuError, match="incremental"):
        materialize_causal_kuzu_from_graph(
            _graph(), kuzu_path=tmp_path / "existing.kuzu", clear_on_start=False, kuzu_enabled=True
        )


def test_disabled_bulk_does_not_require_incremental_policy_or_backend(
    monkeypatch, tmp_path: Path
) -> None:
    def unexpected_backend():
        raise AssertionError("disabled adapter must remain a no-op")

    monkeypatch.setattr("polisyos.ir.analytics.causal_graph_kuzu._import_kuzu", unexpected_backend)
    materialize_causal_kuzu_from_graph(
        _graph(), kuzu_path=tmp_path / "existing.kuzu", clear_on_start=False, kuzu_enabled=False
    )
    assert not (tmp_path / "existing.kuzu").exists()


def test_default_schema_adds_payload_without_replacing_existing_rows(
    monkeypatch, tmp_path: Path
) -> None:
    class LegacyConnection(_FakeConnection):
        def execute(self, statement: str):
            if statement == "CALL table_info('CausalEdge') RETURN name":
                self.executed.append(statement)
                return _FakePropertyResult(["mark_src", "metadata_json"])
            return super().execute(statement)

    class LegacyModule(_FakeKuzuModule):
        def Connection(self, db):  # noqa: N802
            del db
            connection = LegacyConnection()
            self.connections.append(connection)
            return connection

    module = LegacyModule()
    monkeypatch.setattr("polisyos.ir.analytics.causal_graph_kuzu._import_kuzu", lambda: module)
    path = tmp_path / "existing.kuzu"
    path.write_bytes(b"historical database marker")
    ensure_causal_kuzu_schema(kuzu_path=path, clear_on_start=False)
    assert path.read_bytes() == b"historical database marker"
    statements = module.connections[-1].executed
    assert statements[-1] == "ALTER TABLE CausalEdge ADD payload_json STRING"
    assert not any("DELETE" in statement or "COPY" in statement for statement in statements)


def test_current_schema_does_not_add_payload_again(monkeypatch, tmp_path: Path) -> None:
    module = _FakeKuzuModule()
    monkeypatch.setattr("polisyos.ir.analytics.causal_graph_kuzu._import_kuzu", lambda: module)
    ensure_causal_kuzu_schema(kuzu_path=tmp_path / "current.kuzu")
    assert not any(statement.startswith("ALTER") for statement in module.connections[-1].executed)


def test_direct_old_schema_refuses_before_creating_nodes() -> None:
    statements: list[str] = []

    class LegacyConnection:
        def execute(self, statement: str, parameters: object):
            del parameters
            statements.append(statement)
            return _FakePropertyResult(["mark_src", "metadata_json"])

    with pytest.raises(ValueError, match="ensure_causal_kuzu_schema"):
        _graph().to_kuzu(LegacyConnection())
    assert statements == ["CALL table_info('CausalEdge') RETURN name"]


def test_direct_simple_graph_refuses_preexisting_parallel_target_before_all_writes(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.ir.analytics import causal_graph as owner

    statements: list[str] = []
    writes: list[str] = []

    class ExistingMixedConnection:
        def execute(self, statement: str, parameters: dict[str, object]):
            statements.append(statement)
            if statement == "CALL table_info('CausalEdge') RETURN name":
                return _FakePropertyResult(["payload_json"])
            if "RETURN COUNT(e) AS c" in statement:
                # The first pair is safe. A later ambiguous pair must prevent
                # the complete plan, including unrelated new-node creation.
                return _FakeResult(1 if parameters["src"] == "A" else 2)
            writes.append(statement)
            return None

    with pytest.raises(ValueError, match="multiple existing relation occurrences"):
        _graph().to_kuzu(ExistingMixedConnection())
    assert len(statements) == 3
    assert all("MERGE" not in statement for statement in statements)
    assert writes == []
    # Removal control keeps incoming graph/schema and actual method intact;
    # ignoring the target multiplicity reopens the destructive update plan.
    monkeypatch.setattr(owner, "operator", SimpleNamespace(index=lambda _: 0))
    _graph().to_kuzu(ExistingMixedConnection())
    assert len(writes) == 5  # three node and two relation updates


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
    # The direct simple path declares update/idempotence, not occurrence append.
    graph.to_kuzu(conn)
    graph.to_kuzu(conn)
    rows = conn.execute("MATCH ()-[e:CausalEdge]->() RETURN e.payload_json AS payload").get_as_df()
    assert sorted(
        (json.loads(value) for value in rows["payload"]), key=lambda item: item["src"]
    ) == sorted(
        (edge.model_dump(mode="json") for edge in graph.edges), key=lambda item: item["src"]
    )


def test_native_kuzu_full_payload_multiplicity_all_permutations(tmp_path: Path) -> None:
    kuzu = pytest.importorskip("kuzu")
    edges = [
        CausalEdge(src="X", dst="Y", data_confidence=0.2, p_value=0.01),
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, expert_confidence=0.5),
        CausalEdge(src="X", dst="Y", lag=1, literature_confidence=0.6),
        CausalEdge(src="X", dst="Y", lag=2, simulation_confidence=0.7),
        CausalEdge(src="X", dst="Y", data_confidence=0.2, p_value=0.01),
    ]
    expected = sorted(json.dumps(edge.model_dump(mode="json"), sort_keys=True) for edge in edges)
    path = tmp_path / "permutation.kuzu"
    for permutation in permutations(edges):
        graph = CausalGraphModel(graph_type=GraphType.ADMG, nodes=["X", "Y"], edges=permutation)
        materialize_causal_kuzu_from_graph(graph, kuzu_path=path, kuzu_enabled=True)
        db = kuzu.Database(str(path))
        conn = kuzu.Connection(db)
        rows = conn.execute(
            "MATCH ()-[e:CausalEdge]->() RETURN e.payload_json AS payload, "
            "e.mark_src AS mark_src, e.lag AS lag, e.metadata_json AS metadata"
        ).get_as_df()
        assert len(rows) == 5
        actual = []
        for row in rows.itertuples(index=False):
            payload = json.loads(row.payload)
            assert payload["mark_src"] == row.mark_src
            assert payload["metadata"] == json.loads(row.metadata)
            if payload["lag"] is not None:
                assert payload["lag"] == row.lag
            actual.append(json.dumps(payload, sort_keys=True))
        assert sorted(actual) == expected
        before = sorted(actual)
        simple = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "new-node"],
            edges=[CausalEdge(src="X", dst="Y", metadata={"would_overwrite": True})],
        )
        with pytest.raises(ValueError, match="multiple existing relation occurrences"):
            simple.to_kuzu(conn)
        after = conn.execute(
            "MATCH ()-[e:CausalEdge]->() RETURN e.payload_json AS payload"
        ).get_as_df()
        assert (
            sorted(json.dumps(json.loads(value), sort_keys=True) for value in after["payload"])
            == before
        )
        assert conn.execute("MATCH (n:CausalVar) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0] == 2
        conn.close()
        db.close()


def test_native_kuzu_legacy_schema_requires_upgrade_before_direct_writes(tmp_path: Path) -> None:
    from polisyos.ir.analytics.causal_graph_kuzu import _DEFAULT_DDL_PATH, _iter_ddl_statements

    kuzu = pytest.importorskip("kuzu")
    path = tmp_path / "legacy.kuzu"
    db = kuzu.Database(str(path))
    conn = kuzu.Connection(db)
    legacy = _DEFAULT_DDL_PATH.read_text().replace(",\n    payload_json STRING", "")
    for statement in _iter_ddl_statements(legacy):
        conn.execute(statement)
    conn.execute("MERGE (n:CausalVar {name: 'A'})")
    with pytest.raises(ValueError, match="ensure_causal_kuzu_schema"):
        _graph().to_kuzu(conn)
    assert conn.execute("MATCH (n:CausalVar) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0] == 1
    conn.close()
    db.close()
    ensure_causal_kuzu_schema(kuzu_path=path, clear_on_start=False)
    db = kuzu.Database(str(path))
    conn = kuzu.Connection(db)
    _graph().to_kuzu(conn)
    assert conn.execute("MATCH (n:CausalVar) RETURN COUNT(n) AS c").get_as_df().iloc[0, 0] == 3
    assert (
        conn.execute("MATCH ()-[e:CausalEdge]->() RETURN COUNT(e) AS c").get_as_df().iloc[0, 0] == 2
    )
    conn.close()
    db.close()
