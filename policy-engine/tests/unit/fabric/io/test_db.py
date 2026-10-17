from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from polisyos.fabric.io.db import SimulationDB


def _macro_row(step: int) -> dict[str, object]:
    return {
        "run_id": "run-owner-test",
        "step": step,
        "gdp": 1.0 + step,
        "unemployment_rate": 0.1,
        "inflation_rate": 0.02,
        "avg_price": 100.0,
        "avg_income": 50.0,
        "government_balance": -1.0,
        "timestamp": datetime(2026, 1, 1),
    }


def test_macro_rows_round_trip_after_database_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "simulation.duckdb"
    with SimulationDB(db_path=str(db_path)) as db:
        db.save_macro([_macro_row(0), _macro_row(1)])
        rows = db.conn.execute(
            "SELECT run_id, step, gdp FROM macro_history ORDER BY step"
        ).fetchall()
        assert rows == [("run-owner-test", 0, 1.0), ("run-owner-test", 1, 2.0)]

    with SimulationDB(db_path=str(db_path)) as reopened:
        persisted = reopened.conn.execute(
            "SELECT run_id, step, gdp FROM macro_history ORDER BY step"
        ).fetchall()

    assert persisted == [("run-owner-test", 0, 1.0), ("run-owner-test", 1, 2.0)]


def test_empty_batch_is_a_noop_and_closed_database_refuses_write(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "simulation.duckdb"))
    db.save_macro([])
    assert db.conn.execute("SELECT count(*) FROM macro_history").fetchone() == (0,)
    db.close()

    with pytest.raises(RuntimeError, match="closed"):
        db.save_macro([_macro_row(0)])
