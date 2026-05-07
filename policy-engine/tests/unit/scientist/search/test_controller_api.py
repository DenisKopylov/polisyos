"""API-shape regressions for the legacy search controller."""

from __future__ import annotations

from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchEvaluatorPorts,
)
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.stopping import MaxIterations


class _NoopGenerator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "generated"}


class _SingleObjective:
    def evaluate(self, results):
        return ObjectiveValue(
            name="cost",
            raw_value=float(results["cost"]),
            direction=OptimizationDirection.MINIMIZE,
        )

    def evaluate_detailed(self, results):
        return [self.evaluate(results)]


def test_search_controller_accepts_evaluator_ports_value_object() -> None:
    controller = SearchController(
        SearchConfig(
            stopping=MaxIterations(1),
            objective=_SingleObjective(),
        ),
        candidate_generator=_NoopGenerator(),
        evaluators=SearchEvaluatorPorts(
            stage_a=lambda candidate, context: (0.0, bool(candidate) and context["ok"]),
            stage_b=lambda candidate, context: {
                "simulation_results": {"cost": 3.0},
                "feedback": {"verdict": "APPROVE"},
            },
        ),
    )

    result = controller.run({"ok": True}, {"candidate_id": "seed"})

    assert result.best_candidate == {"candidate_id": "seed"}
    assert result.best_objective == 3.0
    assert result.stage_a_evaluations == 1
    assert result.stage_b_evaluations == 1
