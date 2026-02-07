from __future__ import annotations

from typing import Any

from polisyos.scientist.doe.designs import AdversarialPlan, AdversarialStrategy, ParameterSpec
from polisyos.scientist.search.adversarial import NegatedCompositeObjective, run_stress_test
from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)


class QuadraticObjective:
    @property
    def name(self) -> str:
        return "quadratic"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        x = float(results.get("x", 0.0))
        y = float(results.get("y", 0.0))
        return ObjectiveValue(
            name=self.name,
            raw_value=x * x + y * y,
            direction=self.direction,
        )


def test_negated_objective_inverts_sign() -> None:
    base = CompositeObjective([QuadraticObjective()])
    negated = NegatedCompositeObjective(base)

    base_value = base.evaluate({"x": 2.0, "y": 0.0}).raw_value
    negated_value = negated.evaluate({"x": 2.0, "y": 0.0}).raw_value

    assert base_value == 4.0
    assert negated_value == -4.0


def test_run_stress_test_grid_extreme_reports_worst_case() -> None:
    plan = AdversarialPlan(
        parameter_specs=[
            ParameterSpec(name="x", lower_bound=-1.0, upper_bound=1.0),
            ParameterSpec(name="y", lower_bound=-1.0, upper_bound=1.0),
        ],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=10,
        vulnerability_threshold=2.0,
        stop_on_first_vulnerability=False,
    )

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"x": candidate["x"], "y": candidate["y"]}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([QuadraticObjective()]),
        stage_b_evaluator=stage_b,
        candidate_generator=None,
        context={},
    )

    assert report.total_scenarios_evaluated >= 4
    assert report.worst_case_objective is not None
    assert report.worst_case_objective >= 2.0
    assert report.vulnerabilities

