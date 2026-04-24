from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.storage import DuckDBStorageAdapter, InMemoryStorageAdapter, StoragePort


def _macro_row(step: int) -> dict:
    return {
        "run_id": "run-1",
        "step": step,
        "gdp": 1.0 + step,
        "unemployment_rate": 0.1,
        "inflation_rate": 0.02,
        "avg_price": 100.0,
        "avg_income": 50.0,
        "government_balance": -1.0,
        "timestamp": datetime(2026, 1, 1),
    }


def test_duckdb_storage_adapter_runtime_protocol(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    adapter = DuckDBStorageAdapter(db)
    assert isinstance(adapter, StoragePort)
    adapter.close()


def test_duckdb_storage_adapter_transaction_rollback(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    adapter = DuckDBStorageAdapter(db)

    adapter.save_macro([_macro_row(0)])
    baseline = adapter.query_table("macro_history", columns=("step",), limit=100)
    assert len(baseline) == 1

    with pytest.raises(RuntimeError), adapter.transaction():
        adapter.save_macro([_macro_row(1)])
        raise RuntimeError("rollback")

    after = adapter.query_table(
        "macro_history", columns=("step",), order_by=("step ASC",), limit=100
    )
    assert list(after["step"]) == [0]
    adapter.close()


def test_inmemory_storage_adapter_basic_query_and_transaction() -> None:
    adapter = InMemoryStorageAdapter()
    adapter.save_macro([_macro_row(0)])
    adapter.save_macro([_macro_row(1)])

    data = adapter.query_table(
        "macro_history",
        columns=("step", "run_id"),
        where={"run_id": "run-1"},
        order_by=("step DESC",),
    )
    assert list(data["step"]) == [1, 0]

    with pytest.raises(ValueError), adapter.transaction():
        adapter.save_macro([_macro_row(2)])
        raise ValueError("force rollback")

    after = adapter.query_table(
        "macro_history", columns=("step",), order_by=("step ASC",), limit=100
    )
    assert list(after["step"]) == [0, 1]
    adapter.close()
