"""Unavailable plateau predicates remain visible through the native lifecycle."""

from __future__ import annotations

import json
import math

import pytest

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.stopping import (
    AllStoppingCriteria,
    CompositeStoppingCriterion,
    ImprovementPlateau,
    MaxIterations,
)


@pytest.mark.parametrize("composition", [CompositeStoppingCriterion, AllStoppingCriteria])
def test_unavailable_predicate_survives_composition(composition) -> None:
    criterion = composition([ImprovementPlateau(patience=2), MaxIterations(4)])
    result = criterion.check([{"objective_value": math.nan}] * 3, {"evaluation_iterations": 3})
    assert not result.should_stop
    assert result.details["limitations"][0]["details"]["predicate_basis"] == "not_established"


def test_native_result_retains_limitation_without_claiming_convergence() -> None:
    class Generator:
        def generate(self, history, current_best, context):
            return {"x": len(history), "semantic": {"interventions": []}}

    controller = SearchController(
        config=SearchConfig(
            stopping=CompositeStoppingCriterion([ImprovementPlateau(patience=2), MaxIterations(4)]),
            objective=CompositeObjective([GDPGrowthObjective()]),
        ),
        candidate_generator=Generator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"gdp_change": math.nan},
            "feedback": {"verdict": "REJECT"},
        },
    )
    result = controller.run({})
    assert result.stage_b_evaluations == 4
    assert "Maximum iterations" in result.stopping_reason
    limitations = result.telemetry["stopping_limitations"]
    assert limitations[0]["details"]["predicate_basis"] == "not_established"
    # Limitations retain indices/identity rather than non-JSON numeric values.
    json.dumps(limitations, allow_nan=False)


def test_finite_extreme_improvement_has_explicit_limitation() -> None:
    result = ImprovementPlateau(patience=2).check(
        [{"objective_value": 1e308}, {"objective_value": -1e308}, {"objective_value": -1e308}], {}
    )
    assert not result.should_stop
    assert result.details["limitation"] == "non_finite_derived_improvement"
