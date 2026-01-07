from pathlib import Path

import pandas as pd
import pytest

from polisyos.fabric.io.db import SimulationDB
from polisyos.scientist.orchestrator.workflow import build_workflow

pytestmark = pytest.mark.integration


def _write_baseline(db_path: Path, run_id: str, rows: list[dict]) -> None:
    db = SimulationDB(str(db_path))
    df = pd.DataFrame(rows)
    db.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df")
    db.close()


def _base_state(
    db_path: Path,
    graph_path: Path,
    baseline_run_id: str,
    runtime_base_dir: Path,
) -> dict:
    return {
        "db_path": str(db_path),
        "graph_path": str(graph_path),
        "baseline_run_id": baseline_run_id,
        "runtime_base_dir": str(runtime_base_dir),
        "revision_count": 0,
        "simulation_results": None,
        "feedback": None,
    }


def test_workflow_llm_generates_ir_and_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "integration.duckdb"
    graph_path = tmp_path / "integration.kuzu"
    baseline_run_id = "baseline_2023"
    runtime_base_dir = tmp_path / "runs"

    rows = [
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 1,
            "age": 30,
            "income": 800.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 2,
            "age": 40,
            "income": 900.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 3,
            "age": 50,
            "income": 1500.0,
            "savings": 0.0,
            "is_employed": True,
        },
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Help the poor people, their income is too low.",
        "ir": None,
    }
    result = app.invoke(state)

    assert result["ir"] is not None
    assert result["simulation_results"]["avg_income"] > (800.0 + 900.0 + 1500.0) / 3
    assert result["feedback"]["verdict"] == "APPROVE"
