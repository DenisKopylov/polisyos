"""Shared fixtures for search strategy tests."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
    ParameterBounds,
    ParameterType,
)


@pytest.fixture
def simple_space() -> SearchSpace:
    return SearchSpace(bounds=[ParameterBounds(name="x", lower=-5.0, upper=5.0)])


@pytest.fixture
def mixed_space() -> SearchSpace:
    return SearchSpace(
        bounds=[
            ParameterBounds(name="tax_rate", lower=0.0, upper=0.5),
            ParameterBounds(name="budget_steps", lower=1, upper=5, dtype=ParameterType.INTEGER),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B", "C"),
            ),
        ]
    )


def make_evaluation(
    *,
    candidate_id: str,
    params: dict[str, Any],
    score: float,
    space: SearchSpace,
    valid: bool = True,
) -> Evaluation:
    return Evaluation(
        candidate_id=candidate_id,
        params=params,
        params_normalized=space.normalize(params),
        objectives=[
            ObjectiveValue(
                name="score",
                raw_value=score,
                direction=OptimizationDirection.MINIMIZE,
            )
        ],
        scalar_score=score,
        stage_a_passed=valid,
        stage_b_result={"simulation_results": {"score": score}} if valid else None,
        status=EvaluationStatus.SUCCESS if valid else EvaluationStatus.STAGE_B_ERROR,
    )
