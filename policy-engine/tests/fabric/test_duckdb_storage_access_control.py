from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from polisyos.core.security.exceptions import TenantIsolationError
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.storage.duckdb_adapter import DuckDBStorageAdapter


def test_duckdb_storage_adapter_requires_tenant_column_for_scope(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    adapter = DuckDBStorageAdapter(db)

    try:
        with pytest.raises(TenantIsolationError):
            with adapter.tenant_scope("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"):
                pass
    finally:
        adapter.close()


def test_duckdb_storage_adapter_enforces_tenant_filter(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    adapter = DuckDBStorageAdapter(db, tenant_column="tenant_id", fail_closed=True)
    db.conn.execute("CREATE TABLE records (id TEXT, tenant_id TEXT, payload TEXT)")
    db.conn.execute(
        "INSERT INTO records VALUES "
        "('a1', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'row-a'), "
        "('b1', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'row-b')"
    )

    try:
        with pytest.raises(TenantIsolationError):
            adapter.query_table("records", columns=("id", "payload"))

        with adapter.tenant_scope("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"):
            frame = adapter.query_table("records", columns=("id", "payload"))

        assert frame.to_dict(orient="records") == [{"id": "a1", "payload": "row-a"}]
    finally:
        adapter.close()
