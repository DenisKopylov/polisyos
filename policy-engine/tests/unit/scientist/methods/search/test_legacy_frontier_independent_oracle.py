"""Real native consumer oracle for complete finite legacy objective vectors."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchEvaluatorPorts,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    GDPGrowthObjective,
)
from polisyos.scientist.methods.search.stopping import MaxIterations


class _Generator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "unavailable-fiscal"}


@pytest.mark.parametrize(
    "fiscal_metrics",
    [
        pytest.param({}, id="missing"),
        pytest.param({"gov_balance": None}, id="null"),
        pytest.param({"gov_balance": False, "budget_deficit": 99.0}, id="bool-false"),
        pytest.param({"gov_balance": True}, id="bool-true"),
        pytest.param({"gov_balance": "bad"}, id="malformed"),
        pytest.param({"gov_balance": math.nan}, id="nan"),
        pytest.param({"gov_balance": math.inf}, id="inf"),
        pytest.param({"gov_balance": -math.inf}, id="negative-inf"),
        pytest.param({"gov_balance": 10**400}, id="conversion-overflow"),
        pytest.param({"gov_balance": -1.0, "government_balance": 1.0}, id="conflicting-aliases"),
    ],
)
def test_actual_native_frontier_cannot_use_unavailable_coordinate_to_dominate(fiscal_metrics):
    calls = []

    def stage_b(candidate, context):
        del context
        calls.append(candidate["candidate_id"])
        metrics = (
            {"gdp_change": 1.0, "gov_balance": -10.0}
            if candidate["candidate_id"] == "measured"
            else {"gdp_change": 2.0, **fiscal_metrics}
        )
        return {"simulation_results": metrics, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        SearchConfig(
            stopping=MaxIterations(2),
            objective=CompositeObjective([GDPGrowthObjective(), BudgetDeficitObjective()]),
            max_iterations_hard_limit=2,
        ),
        candidate_generator=_Generator(),
        evaluators=SearchEvaluatorPorts(
            stage_a=lambda candidate, context: (0.0, True), stage_b=stage_b
        ),
    )
    result = controller.run({}, {"candidate_id": "measured"})
    assert calls == ["measured", "unavailable-fiscal"]
    assert result.best_candidate == {"candidate_id": "measured"}
    assert result.best_objective == 9.0
    assert len(result.history) == 2
    unavailable = result.history[-1].objective_details
    assert math.isnan(unavailable[1].raw_value)
    assert unavailable[1].is_satisfied is False

    # The independently enumerated complete vector is (-GDP, deficit)=(-1, 10).
    # (-2, unavailable) cannot establish dominance despite its better GDP axis.
    assert len(result.pareto_front) == 1
    point = result.pareto_front[0]
    assert point["candidate"] == {"candidate_id": "measured"}
    assert len(point["objectives"]) == 2
    assert {value["name"]: value["raw_value"] for value in point["objectives"]} == {
        "gdp_growth": 1.0,
        "budget_deficit": 10.0,
    }
    assert {value["name"]: value["direction"] for value in point["objectives"]} == {
        "gdp_growth": "maximize",
        "budget_deficit": "minimize",
    }
