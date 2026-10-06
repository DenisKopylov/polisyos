"""Actual MO quantity consumer and generic row-intake boundary."""

from dataclasses import replace

import pytest

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds


def strategy():
    return MOBayesianOptimizer(
        SearchSpace([ParameterBounds("x", 0.0, 1.0)]),
        ["a", "b", "c"],
        [OptimizationDirection.MAXIMIZE] * 3,
        MOConfig(ref_point=[0.0, 0.0, 0.0]),
    )


def rows():
    return [
        Evaluation(
            candidate_id=str(index),
            params={"x": 0.5},
            params_normalized=(0.5,),
            objectives=[
                ObjectiveValue(name=name, raw_value=value, direction=OptimizationDirection.MAXIMIZE)
                for name, value in zip(("a", "b", "c"), point, strict=True)
            ],
            scalar_score=1.0,
            stage_a_passed=True,
            stage_b_result={"simulation_results": {"measured": True}},
        )
        for index, point in enumerate([(3.0, 1.0, 2.0), (1.0, 3.0, 2.0), (2.0, 2.0, 3.0)])
    ]


def test_actual_strategy_quantity_and_backend_absence_are_distinct():
    optimizer = strategy()
    assert optimizer._botorch_ready, (
        "UNRUN: this numerical positive requires the actual optional backend"
    )
    evaluations = rows()
    assert optimizer.compute_hypervolume(evaluations) == 16.0
    assert optimizer.last_hypervolume_assessment.status == "available"
    optimizer._botorch_ready = False  # negative capability removal only
    assert optimizer.compute_hypervolume(evaluations) is None
    assert optimizer.last_hypervolume_assessment.reason == "optional_backend_unavailable"
    assert len(optimizer.get_pareto_front(evaluations)) == 3


@pytest.mark.parametrize("raw", [10**400, True, "broken", float("nan"), float("inf")])
def test_strategy_excludes_invalid_scalar_without_fabricating_zero(raw):
    optimizer = strategy()
    evaluations = rows()
    evaluations[1].objectives[0] = replace(evaluations[1].objectives[0], raw_value=raw)
    assert [row.candidate_id for row in optimizer.get_pareto_front(evaluations)] == ["0", "2"]
    report = optimizer.last_objective_admission
    assert report["status"] == "partial"
    assert report["input_count"] == 3 and report["assessed_count"] == 2
    assert report["rejected_rows"][0]["input_index"] == 1
    assert report["rejected_rows"][0]["reason"] == "non_finite_or_untyped_objective:a"


def test_actual_zero_and_no_usable_inputs_have_different_assessments():
    optimizer = strategy()
    evaluations = rows()
    for evaluation in evaluations:
        evaluation.objectives[1] = replace(evaluation.objectives[1], raw_value=0.0)
    assert optimizer.compute_hypervolume(evaluations) == 0.0
    assert optimizer.last_hypervolume_assessment.status == "available"
    assert optimizer.compute_hypervolume([]) is None
    assert optimizer.last_hypervolume_assessment.reason == "no_usable_inputs"
