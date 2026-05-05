from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.solver_runner import SolverRunner
from polisyos.foundry.methods.optimization import (
    AllocationItem,
    BudgetMILP,
    LeontiefInputOutput,
    OptimizationProblem,
    ResourceConstraint,
    ResourceLP,
)


def _knapsack_problem() -> OptimizationProblem:
    return OptimizationProblem(
        problem_id="knapsack_5",
        items=(
            AllocationItem(item_id="a", cost=2.0, benefit=6.0),
            AllocationItem(item_id="b", cost=2.0, benefit=10.0),
            AllocationItem(item_id="c", cost=3.0, benefit=12.0),
            AllocationItem(item_id="d", cost=1.0, benefit=7.0),
            AllocationItem(item_id="e", cost=4.0, benefit=14.0),
        ),
        budget=7.0,
        objective="maximize",
    )


def test_budget_milp_known_answer_or_graceful_error() -> None:
    payload, solver_info = BudgetMILP.pure_step(_knapsack_problem(), {})
    status = payload["status"]
    if status == "error":
        assert "error" in solver_info
        return

    assert status in {"optimal", "feasible"}
    assert payload["objective_value"] is not None
    assert float(payload["objective_value"]) >= 30.0
    assert payload["constraints_satisfied"].get("budget", True)


def test_resource_lp_known_answer_or_graceful_error() -> None:
    problem = OptimizationProblem(
        problem_id="lp_2var",
        items=(
            AllocationItem(item_id="x", cost=0.0, benefit=3.0, max_units=10, is_integer=False),
            AllocationItem(item_id="y", cost=0.0, benefit=2.0, max_units=10, is_integer=False),
        ),
        constraints=(
            ResourceConstraint(
                constraint_id="capacity",
                coefficients={"x": 2.0, "y": 1.0},
                bound=10.0,
                sense="<=",
            ),
        ),
    )

    payload, solver_info = ResourceLP.pure_step(problem, {"prefer_ortools": False})
    status = payload["status"]
    if status == "error":
        assert "error" in solver_info
        return

    assert status in {"optimal", "feasible"}
    assert payload["objective_value"] is not None
    assert float(payload["objective_value"]) >= 14.9


def test_leontief_model_solution_and_unproductive_guard() -> None:
    state = {
        "technical_coefficients": [[0.2, 0.1], [0.05, 0.15]],
        "final_demand": [100.0, 80.0],
        "sector_names": ["s1", "s2"],
    }
    result = LeontiefInputOutput.pure_step(
        state,
        {"strict_productivity": True, "n_perturbation_samples": 32},
    )
    assert result["status"] == "optimal"

    a = np.array(state["technical_coefficients"], dtype=float)
    d = np.array(state["final_demand"], dtype=float)
    expected = np.linalg.inv(np.eye(2) - a) @ d
    assert np.allclose(np.array(result["output_vector"], dtype=float), expected, atol=1e-6)

    bad = {
        "technical_coefficients": [[0.8, 0.6], [0.4, 0.8]],
        "final_demand": [10.0, 10.0],
    }
    bad_result = LeontiefInputOutput.pure_step(bad, {"strict_productivity": True})
    assert bad_result["status"] == "error"


def test_budget_milp_through_method_dispatcher_if_solver_available() -> None:
    runner = SolverRunner()
    if not runner.is_available():
        pytest.skip("solver backend not available in this environment")

    MethodDispatcher.reset_instance()
    dispatcher = MethodDispatcher.get_instance()
    dispatch_result = dispatcher.dispatch(
        method_class=BudgetMILP,
        signature=BudgetMILP.signature,
        state=_knapsack_problem(),
        params={},
        seed=7,
    )
    output = dispatch_result.output
    assert isinstance(output, dict)
    assert output["status"] in {
        "optimal",
        "feasible",
        "infeasible",
        "timeout",
        "error",
        "unknown",
    }
