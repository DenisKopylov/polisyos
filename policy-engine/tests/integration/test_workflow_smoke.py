from pathlib import Path

import pandas as pd
import pytest

from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.types import SelectorOperator
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


def test_workflow_smoke_approve(tmp_path: Path) -> None:
    db_path = tmp_path / "integration.duckdb"
    graph_path = tmp_path / "integration.kuzu"
    baseline_run_id = "baseline_2023"
    runtime_base_dir = tmp_path / "runs"

    rows = [
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 1,
            "age": 25,
            "income": 500.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 2,
            "age": 30,
            "income": 500.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 3,
            "age": 35,
            "income": 500.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 4,
            "age": 40,
            "income": 2000.0,
            "savings": 0.0,
            "is_employed": True,
        },
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": 5,
            "age": 45,
            "income": 2000.0,
            "savings": 0.0,
            "is_employed": True,
        },
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    ir = PolicySurfaceIR(
        semantic={
            "context_snapshot_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "time_semantics": {"frequency": "M", "start_date": "2024-01-01", "step_count": 1},
            "interventions": [
                {
                    "intervention_id": "tax_sub",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "any",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.1"},
                }
            ],
            "objectives": [],
            "constraints": [],
        }
    )

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Test policy simulation",
        "ir": ir,
    }
    result = app.invoke(state)

    stats = result["simulation_results"]
    assert stats["n_agents"] == 5
    assert abs(stats["avg_income"] - 1210.0) < 1.0
    assert result["feedback"]["verdict"] == "APPROVE"


def test_workflow_budget_constraint_needs_revision(tmp_path: Path) -> None:
    db_path = tmp_path / "integration.duckdb"
    graph_path = tmp_path / "integration.kuzu"
    baseline_run_id = "baseline_2023"
    runtime_base_dir = tmp_path / "runs"

    rows = [
        {
            "run_id": baseline_run_id,
            "step": 0,
            "agent_id": i,
            "age": 30,
            "income": 1000.0,
            "savings": 0.0,
            "is_employed": True,
        }
        for i in range(10)
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    ir = PolicySurfaceIR(
        semantic={
            "context_snapshot_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "time_semantics": {"frequency": "M", "start_date": "2024-01-01", "step_count": 1},
            "interventions": [
                {
                    "intervention_id": "sub",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "any",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.5"},
                }
            ],
            "objectives": [],
            "constraints": [
                {
                    "constraint_id": "min_balance",
                    "value": {"amount": "-2000", "currency": "USD"},
                }
            ],
        }
    )

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Budget constraint test",
        "ir": ir,
    }
    result = app.invoke(state)

    assert result["feedback"]["verdict"] == "NEEDS_REVISION"
