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


class _RunRecordModelDump:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, object]:
        return self._payload.copy()


def _run_record_payload(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "parent_run_id": None,
        "seed": 13,
        "repro_mode": "strict",
        "backend": "cpu",
        "python_version": "3.14.3",
        "platform": "test",
        "generated_at": datetime(2026, 1, 1),
        "schema_version": "1",
        "generator": {"name": "fixture-generator", "version": "1.0"},
        "library_versions": {"numpy": "1.0"},
        "flags": {"deterministic": True},
    }


def test_run_record_generator_defaults_only_when_absent_and_rejects_malformed(
    tmp_path: Path,
) -> None:
    with SimulationDB(db_path=str(tmp_path / "run-records.duckdb")) as db:
        valid = _run_record_payload("run-record-valid")
        db.save_run_record(_RunRecordModelDump(valid))

        absent = _run_record_payload("run-record-absent")
        del absent["generator"]
        db.save_run_record(_RunRecordModelDump(absent))

        rows = db.conn.execute(
            "SELECT run_id, generator_name, generator_version FROM run_records ORDER BY run_id"
        ).fetchall()
        assert rows == [
            ("run-record-absent", None, None),
            ("run-record-valid", "fixture-generator", "1.0"),
        ]

        malformed = _run_record_payload("run-record-malformed")
        malformed["generator"] = None
        with pytest.raises(TypeError, match="generator metadata must be a mapping"):
            db.save_run_record(_RunRecordModelDump(malformed))

        assert db.conn.execute("SELECT count(*) FROM run_records").fetchone() == (2,)
