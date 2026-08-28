from __future__ import annotations

import builtins
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world import (
    WorldSnapshotBackendUnavailable,
    WorldSnapshotFactWrite,
    WorldSnapshotNodeWrite,
    WorldSnapshotWriteRequest,
    write_world_snapshot,
)
from polisyos.fabric.world.materialize import ensure_world_schema
from polisyos.fabric.world.store import WorldSnapshotRecord, WorldValidationError


def _request(tmp_path: Path) -> WorldSnapshotWriteRequest:
    return WorldSnapshotWriteRequest(
        snapshot_root=tmp_path / "snapshots",
        snapshot_id="snapshot-1",
        branch_name="observed",
        as_of_valid_time="2026-05-01T00:00:00+00:00",
        as_of_tx_time="2026-05-01T00:00:00+00:00",
        provenance={"producer": "test"},
        nodes=(
            WorldSnapshotNodeWrite(
                node_id="node-1",
                kind="data_state",
                label="node one",
                artifact_id="sha256:" + "1" * 64,
                props_ref=None,
            ),
        ),
        facts=(
            WorldSnapshotFactWrite(
                fact_id="fact-1",
                schema_version="1.0",
                subject_id="node-1",
                predicate_id="data_state.payload_hash",
                object_value="sha256:" + "1" * 64,
                target_id=None,
                valid_time="2026-05-01T00:00:00Z",
                tx_time="2026-05-01T00:00:00Z",
                provenance_json={"producer": "test"},
                trust_json=None,
                legal_json=None,
                segment_id="seg-1",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("factory", "payload"),
    [
        (
            WorldSnapshotNodeWrite,
            {
                "node_id": "node-1",
                "kind": "data_state",
                "label": None,
                "artifact_id": None,
                "props_ref": None,
                "unexpected": True,
            },
        ),
        (
            WorldSnapshotFactWrite,
            {
                "fact_id": "fact-1",
                "schema_version": "1.0",
                "subject_id": "node-1",
                "predicate_id": "predicate",
                "object_value": None,
                "target_id": None,
                "valid_time": None,
                "tx_time": "2026-05-01T00:00:00Z",
                "provenance_json": {},
                "trust_json": None,
                "legal_json": None,
                "segment_id": None,
                "unexpected": True,
            },
        ),
    ],
)
def test_world_snapshot_write_contracts_forbid_extra_fields(
    factory: Callable[..., object],
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        factory(**payload)


def test_world_snapshot_write_contracts_are_frozen(tmp_path: Path) -> None:
    request = _request(tmp_path)

    with pytest.raises(ValidationError):
        request.nodes[0].node_id = "changed"
    with pytest.raises(ValidationError):
        request.facts[0].fact_id = "changed"
    with pytest.raises(ValidationError):
        request.snapshot_id = "changed"


@pytest.mark.parametrize(
    "request_update",
    [
        {"nodes": ()},
        {"facts": ()},
        {
            "nodes": (
                {
                    "node_id": "node-1",
                    "kind": "data_state",
                    "label": None,
                    "artifact_id": None,
                    "props_ref": None,
                },
                {
                    "node_id": "node-1",
                    "kind": "data_state",
                    "label": None,
                    "artifact_id": None,
                    "props_ref": None,
                },
            )
        },
        {
            "facts": (
                {
                    "fact_id": "fact-1",
                    "schema_version": "1.0",
                    "subject_id": "node-1",
                    "predicate_id": "predicate.one",
                    "object_value": None,
                    "target_id": None,
                    "valid_time": None,
                    "tx_time": "2026-05-01T00:00:00Z",
                    "provenance_json": {},
                    "trust_json": None,
                    "legal_json": None,
                    "segment_id": None,
                },
                {
                    "fact_id": "fact-1",
                    "schema_version": "1.0",
                    "subject_id": "node-1",
                    "predicate_id": "predicate.two",
                    "object_value": None,
                    "target_id": None,
                    "valid_time": None,
                    "tx_time": "2026-05-01T00:00:00Z",
                    "provenance_json": {},
                    "trust_json": None,
                    "legal_json": None,
                    "segment_id": None,
                },
            )
        },
        {
            "facts": (
                {
                    "fact_id": "fact-1",
                    "schema_version": "1.0",
                    "subject_id": "missing-node",
                    "predicate_id": "predicate",
                    "object_value": None,
                    "target_id": None,
                    "valid_time": None,
                    "tx_time": "2026-05-01T00:00:00Z",
                    "provenance_json": {},
                    "trust_json": None,
                    "legal_json": None,
                    "segment_id": None,
                },
            )
        },
        {
            "facts": (
                {
                    "fact_id": "fact-1",
                    "schema_version": "1.0",
                    "subject_id": "node-1",
                    "predicate_id": "predicate",
                    "object_value": None,
                    "target_id": "missing-node",
                    "valid_time": None,
                    "tx_time": "2026-05-01T00:00:00Z",
                    "provenance_json": {},
                    "trust_json": None,
                    "legal_json": None,
                    "segment_id": None,
                },
            )
        },
        {
            "nodes": (
                {
                    "node_id": "node-1",
                    "kind": "data_state",
                    "label": None,
                    "artifact_id": None,
                    "props_ref": None,
                },
                {
                    "node_id": "node-2",
                    "kind": "data_state",
                    "label": None,
                    "artifact_id": None,
                    "props_ref": None,
                },
            )
        },
    ],
)
def test_world_snapshot_write_request_rejects_invalid_identity_graph(
    tmp_path: Path,
    request_update: dict[str, object],
) -> None:
    payload = _request(tmp_path).model_dump()
    payload.update(request_update)

    with pytest.raises(ValidationError):
        WorldSnapshotWriteRequest.model_validate(payload)


def test_world_snapshot_write_validates_before_backend_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.world import write as world_write

    valid = _request(tmp_path)
    invalid = WorldSnapshotWriteRequest.model_construct(
        **{key: value for key, value in valid.__dict__.items() if key != "nodes"},
        nodes=(),
    )
    monkeypatch.setattr(
        world_write._importlib_util,
        "find_spec",
        lambda _name: (_ for _ in ()).throw(AssertionError("backend probe ran")),
    )

    with pytest.raises(ValidationError):
        write_world_snapshot(tmp_path / "world.duckdb", invalid)


def test_world_snapshot_write_translates_only_absent_duckdb_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.world import write as world_write

    monkeypatch.setattr(world_write._importlib_util, "find_spec", lambda name: None)

    with pytest.raises(WorldSnapshotBackendUnavailable):
        write_world_snapshot(tmp_path / "world.duckdb", _request(tmp_path))


def test_world_snapshot_write_propagates_internal_import_defects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.world import write as world_write

    real_import = builtins.__import__

    def _import_with_internal_defect(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "polisyos.fabric.io.db":
            raise ModuleNotFoundError("internal backend dependency missing", name="internal_missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(world_write._importlib_util, "find_spec", lambda _name: object())
    monkeypatch.setattr(builtins, "__import__", _import_with_internal_defect)

    with pytest.raises(ModuleNotFoundError, match="internal backend dependency missing") as exc_info:
        write_world_snapshot(tmp_path / "fabric-world.duckdb", _request(tmp_path))

    assert exc_info.value.name == "internal_missing"
    assert not isinstance(exc_info.value, WorldSnapshotBackendUnavailable)


class _RowsResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _InterceptingConnection:
    def __init__(self, connection: Any, *, orphan_kind: str | None) -> None:
        self._connection = connection
        self.orphan_kind = orphan_kind
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object | None = None) -> Any:
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        if self.orphan_kind == "fact" and "AS orphan_fact_id" in normalized:
            return _RowsResult([("fact-1",)])
        if self.orphan_kind == "node" and "AS orphan_node_id" in normalized:
            return _RowsResult([("node-1",)])
        if parameters is None:
            return self._connection.execute(sql)
        return self._connection.execute(sql, parameters)

    def close(self) -> None:
        self._connection.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def _install_intercepting_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    orphan_kind: str | None,
) -> list[_InterceptingConnection]:
    from polisyos.fabric import io as fabric_io
    from polisyos.fabric.io import db as db_module

    real_simulation_db = SimulationDB
    connections: list[_InterceptingConnection] = []

    class InterceptingSimulationDB(real_simulation_db):
        def __init__(self, db_path: str) -> None:
            super().__init__(db_path=db_path)
            wrapped = _InterceptingConnection(self.conn, orphan_kind=orphan_kind)
            self.conn = wrapped
            connections.append(wrapped)

    monkeypatch.setattr(db_module, "SimulationDB", InterceptingSimulationDB)
    # Keep the already-imported package attribute aligned with the module owner.
    monkeypatch.setattr(fabric_io, "SimulationDB", InterceptingSimulationDB, raising=False)
    return connections


def _seed_replacement_rows(db_path: Path) -> None:
    with SimulationDB(db_path=str(db_path)) as db:
        ensure_world_schema(db)
        db.conn.execute(
            """
            INSERT INTO world.world_nodes (node_id, kind, label)
            VALUES ('node-1', 'old-kind', 'old managed'),
                   ('unrelated-node', 'claim', 'unrelated')
            """
        )
        db.conn.execute(
            """
            INSERT INTO world.world_facts (
                fact_id, schema_version, subject_id, predicate_id, object_value,
                target_id, valid_time, tx_time, provenance_json, trust_json,
                legal_json, segment_id
            )
            VALUES ('fact-1', '0.9', 'node-1', 'old.predicate', 'old', NULL,
                    NULL, '2026-04-01T00:00:00Z', '{}', NULL, NULL, 'old-seg'),
                   ('unrelated-fact', '1.0', 'unrelated-node', 'world.kind', 'claim', NULL,
                    NULL, '2026-04-01T00:00:00Z', '{}', NULL, NULL, 'other-seg')
            """
        )


def _managed_rows(db_path: Path) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    with SimulationDB(db_path=str(db_path)) as db:
        nodes = db.conn.execute(
            """
            SELECT node_id, kind, label
            FROM world.world_nodes
            ORDER BY node_id
            """
        ).fetchall()
        facts = db.conn.execute(
            """
            SELECT fact_id, schema_version, subject_id, predicate_id, object_value, segment_id
            FROM world.world_facts
            ORDER BY fact_id
            """
        ).fetchall()
    return nodes, facts


@pytest.mark.parametrize("orphan_kind", ["fact", "node"])
def test_world_snapshot_write_rolls_back_orphaned_postconditions_before_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    orphan_kind: str,
) -> None:
    from polisyos.fabric.world.store import snapshots

    db_path = tmp_path / "fabric-world.duckdb"
    _seed_replacement_rows(db_path)
    before = _managed_rows(db_path)
    connections = _install_intercepting_db(monkeypatch, orphan_kind=orphan_kind)
    snapshot_calls: list[object] = []
    monkeypatch.setattr(
        snapshots,
        "create_world_snapshot",
        lambda *_args, **_kwargs: snapshot_calls.append(object()),
    )

    with pytest.raises(WorldValidationError):
        write_world_snapshot(db_path, _request(tmp_path))

    assert _managed_rows(db_path) == before
    assert snapshot_calls == []
    assert any(statement == "ROLLBACK" for statement in connections[0].statements)


def test_world_snapshot_write_replaces_only_managed_rows_and_snapshots_after_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.world.store import snapshots

    db_path = tmp_path / "fabric-world.duckdb"
    _seed_replacement_rows(db_path)
    connections = _install_intercepting_db(monkeypatch, orphan_kind=None)
    snapshot_calls: list[dict[str, object]] = []
    expected = WorldSnapshotRecord(
        snapshot_id="snapshot-1",
        snapshot_path=str(tmp_path / "snapshots" / "snapshot-1.duckdb"),
        created_at="2026-05-01T00:00:01Z",
        branch_name="observed",
        as_of_valid_time="2026-05-01T00:00:00+00:00",
        as_of_tx_time="2026-05-01T00:00:00+00:00",
        provenance={"producer": "test"},
    )

    def _snapshot_spy(_db: object, **kwargs: object) -> WorldSnapshotRecord:
        assert connections[0].statements[-1] == "COMMIT"
        snapshot_calls.append(kwargs)
        return expected

    monkeypatch.setattr(snapshots, "create_world_snapshot", _snapshot_spy)

    result = write_world_snapshot(db_path, _request(tmp_path))

    assert result is expected
    assert snapshot_calls == [
        {
            "snapshot_root": tmp_path / "snapshots",
            "snapshot_id": "snapshot-1",
            "branch_name": "observed",
            "as_of_valid_time": "2026-05-01T00:00:00+00:00",
            "as_of_tx_time": "2026-05-01T00:00:00+00:00",
            "provenance": {"producer": "test"},
        }
    ]
    assert _managed_rows(db_path) == (
        [
            ("node-1", "data_state", "node one"),
            ("unrelated-node", "claim", "unrelated"),
        ],
        [
            (
                "fact-1",
                "1.0",
                "node-1",
                "data_state.payload_hash",
                "sha256:" + "1" * 64,
                "seg-1",
            ),
            ("unrelated-fact", "1.0", "unrelated-node", "world.kind", "claim", "other-seg"),
        ],
    )
