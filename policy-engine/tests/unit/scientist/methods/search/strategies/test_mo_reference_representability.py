"""Native reference refusal precedes real model fitting and random fallback."""

import sys

import pytest

pytest.importorskip("torch", reason="UNRUN: actual native MO backend")
pytest.importorskip("botorch", reason="UNRUN: actual native MO backend")
pytest.importorskip("gpytorch", reason="UNRUN: actual native MO backend")

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds

pytestmark = pytest.mark.integration


def _scenario(offset):
    optimizer = MOBayesianOptimizer(
        SearchSpace([ParameterBounds("x", 0.0, 1.0)]),
        ["a", "b"],
        [OptimizationDirection.MAXIMIZE] * 2,
        MOConfig(n_initial=3, ref_point_offset=offset),
    )
    rows = [
        Evaluation(
            candidate_id=f"row-{index}",
            params={"x": index / 2},
            params_normalized=(index / 2,),
            scalar_score=1.0,
            stage_a_passed=True,
            objectives=[
                ObjectiveValue(name="a", raw_value=value, direction=OptimizationDirection.MAXIMIZE),
                ObjectiveValue(
                    name="b", raw_value=float(index), direction=OptimizationDirection.MAXIMIZE
                ),
            ],
            stage_b_result={"simulation_results": {"measured": True}},
        )
        for index, value in enumerate([-1e308, 0.0, 1e308])
    ]
    return optimizer, rows


@pytest.mark.parametrize("route", ["single", "batch", "indicator"])
@pytest.mark.parametrize("offset", [0.0, 0.1, 1e308])
def test_derived_reference_overflow_refuses_without_model_or_fallback(route, offset):
    optimizer, rows = _scenario(offset)
    counts = {"fit_model_list": 0, "fit_gpytorch_mll": 0, "random_candidate": 0}

    def observe(frame, event, arg):
        if event == "call":
            name = frame.f_code.co_name.removeprefix("_")
            if name in counts:
                counts[name] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        if route == "indicator":
            result = optimizer.compute_hypervolume_assessed(rows)
            assert result.value is None
            assert result.assessment.reason == "invalid_reference_point"
        else:
            suggest = (
                optimizer.suggest
                if route == "single"
                else lambda values: optimizer.suggest_batch(values, batch_size=2)
            )
            with pytest.raises(ValueError, match="invalid_reference_point"):
                suggest(rows)
    finally:
        sys.setprofile(previous)
    assert counts == {"fit_model_list": 0, "fit_gpytorch_mll": 0, "random_candidate": 0}
    assert optimizer._model is None and optimizer._ref_point is None
    assert optimizer.last_objective_admission["assessed_count"] == 3
