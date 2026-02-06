from pathlib import Path

import pandas as pd
import pytest
from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ConstraintSpec as ProblemConstraintSpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.schedule import ScheduleSpec
from polisyos.ir.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.kernel.human_gate import GateDecision
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


def _build_ir(*, rate: str, min_balance: str | None = None) -> TrinityBundle:
    hard_constraints: list[ProblemConstraintSpec] = []
    if min_balance is not None:
        hard_constraints.append(
            ProblemConstraintSpec(
                constraint_id="min_balance",
                value={"amount": min_balance, "currency": "USD"},
            )
        )
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="workflow_smoke_problem",
            domain=ProblemDomain.FISCAL,
            hard_constraints=hard_constraints,
        ),
        policy_spec=PolicySpec(
            policy_id="workflow_smoke_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_sub",
                    kind="tax_subsidy",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="any",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": rate},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="workflow_smoke_model",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        ),
    )


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

    ir = _build_ir(rate="0.1")

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

    ir = _build_ir(rate="0.5", min_balance="-2000")

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Budget constraint test",
        "ir": ir,
    }
    result = app.invoke(state)

    assert result["feedback"]["verdict"] == "NEEDS_REVISION"


def test_workflow_does_not_create_logs_dir(tmp_path: Path) -> None:
    """
    Workflow must use runtime artifacts under runs/<run_id>/ and not emit legacy logs/.
    """
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
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    ir = _build_ir(rate="0.1")

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "No legacy logs",
        "ir": ir,
    }
    result = app.invoke(state)

    assert result["simulation_results"]["n_agents"] == 2
    assert not (tmp_path / "logs").exists()


def test_workflow_human_gate_pending(tmp_path: Path) -> None:
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
        }
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    ir = _build_ir(rate="0.1")

    app = build_workflow()
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Gate pending",
        "ir": ir,
        "require_human_gate": True,
    }
    result = app.invoke(state)
    assert result["feedback"]["verdict"] == "HUMAN_GATE"
    assert "gate_request" in result


def test_workflow_human_gate_approved(tmp_path: Path) -> None:
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
        }
    ]
    _write_baseline(db_path, baseline_run_id, rows)

    ir = _build_ir(rate="0.1")

    app = build_workflow()
    gate_decision = GateDecision(approved=True, actor="tester")
    state = {
        **_base_state(db_path, graph_path, baseline_run_id, runtime_base_dir),
        "user_request": "Gate approved",
        "ir": ir,
        "require_human_gate": True,
        "gate_decision": gate_decision.model_dump(),
    }
    result = app.invoke(state)
    assert result["feedback"]["verdict"] in {"APPROVE", "NEEDS_REVISION"}
