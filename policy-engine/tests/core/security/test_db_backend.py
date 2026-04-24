from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from polisyos.core.security.db_backend import DuckDBLegacyBackend
from polisyos.fabric.io.db import SimulationDB


def test_duckdb_backend_transaction_rollback(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))
    backend = DuckDBLegacyBackend(db)

    backend.execute(
        "INSERT INTO macro_history (run_id, step, gdp, unemployment_rate, inflation_rate, avg_price, avg_income, government_balance) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ["r1", 0, 1.0, 0.1, 0.02, 100.0, 50.0, 0.0],
    )

    with pytest.raises(RuntimeError):
        with backend.transaction():
            backend.execute(
                "INSERT INTO macro_history (run_id, step, gdp, unemployment_rate, inflation_rate, avg_price, avg_income, government_balance) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ["r1", 1, 1.1, 0.1, 0.02, 100.0, 50.0, 0.0],
            )
            raise RuntimeError("force rollback")

    rows = backend.fetchall("SELECT step FROM macro_history ORDER BY step ASC")
    assert [row[0] for row in rows] == [0]
    backend.close()


def test_duckdb_tenant_scope_validates_uuid(tmp_path: Path) -> None:
    db = SimulationDB(db_path=str(tmp_path / "sim2.duckdb"))
    backend = DuckDBLegacyBackend(db)

    with pytest.raises(Exception), backend.tenant_scope("not-a-uuid"):
        pass

    backend.close()
