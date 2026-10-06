"""Actual reference preparation must preserve the shared finite-number boundary."""

from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds

pytest.importorskip("torch", reason="UNRUN: actual MO reference consumer requires Torch")
pytest.importorskip("botorch", reason="UNRUN: actual MO reference consumer requires BoTorch")
pytest.importorskip("gpytorch", reason="UNRUN: actual MO reference consumer requires GPyTorch")
pytestmark = [pytest.mark.integration]


def _rows() -> list[Evaluation]:
    return [
        Evaluation(
            candidate_id=f"declared-geometry-{index}",
            params={"x": index / 4},
            params_normalized=(index / 4,),
            objectives=[
                ObjectiveValue(name=name, raw_value=value, direction=OptimizationDirection.MAXIMIZE)
                for name, value in zip(("a", "b", "c"), point, strict=True)
            ],
            scalar_score=1.0,
            stage_a_passed=True,
            stage_b_result={"simulation_results": {"measured": True}},
        )
        for index, point in enumerate(((3.0, 1.0, 2.0), (1.0, 3.0, 2.0), (2.0, 2.0, 3.0)))
    ]


def _strategy(config: MOConfig) -> MOBayesianOptimizer:
    return MOBayesianOptimizer(
        SearchSpace([ParameterBounds("x", 0.0, 1.0)]),
        ["a", "b", "c"],
        [OptimizationDirection.MAXIMIZE] * 3,
        config,
    )


@pytest.mark.parametrize("reference", [[0.0, 0.0, 0.0], [10.0, 10.0, 10.0]])
def test_actual_mo_consumer_preserves_nonzero_and_true_zero(reference: list[float]) -> None:
    result = _strategy(MOConfig(ref_point=reference)).compute_hypervolume_assessed(_rows())
    # At origin the three boxes total 24 minus pairwise overlaps10 plus triple2.
    # With reference10 every box has empty intersection with the dominated region.
    assert result.value == (16.0 if reference[0] == 0.0 else 0.0)
    assert result.assessment.status == "available"
    assert result.assessment.basis == "recomputed"


@pytest.mark.parametrize("invalid", [10**400, True, "broken", float("nan"), float("inf")])
def test_configured_reference_refuses_before_lossy_tensor_conversion(invalid: object) -> None:
    config = MOConfig(ref_point=[0.0, 0.0, 0.0])
    config.ref_point[0] = invalid  # type: ignore[assignment,index]
    result = _strategy(config).compute_hypervolume_assessed(_rows())
    assert result.value is None
    assert result.assessment.status == "unavailable"
    assert result.assessment.reason == "invalid_reference_point"


def test_configured_reference_dimension_matches_declared_coordinate_basis() -> None:
    result = _strategy(MOConfig(ref_point=[0.0, 0.0])).compute_hypervolume_assessed(_rows())
    assert result.value is None
    assert result.assessment.reason == "invalid_reference_point"


def test_genuine_zero_offset_remains_available() -> None:
    result = _strategy(MOConfig(ref_point_offset=0.0)).compute_hypervolume_assessed(_rows())
    # The generated reference is(1,1,2); only box(2,2,3) has nonzero volume1.
    assert result.value == 1.0
    assert result.assessment.status == "available"


@pytest.mark.parametrize("invalid", [10**400, True, "broken", float("nan"), float("inf")])
def test_derived_reference_offset_uses_same_finite_number_boundary(invalid: object) -> None:
    config = MOConfig()
    config.ref_point_offset = invalid  # type: ignore[assignment]
    result = _strategy(config).compute_hypervolume_assessed(_rows())
    assert result.value is None
    assert result.assessment.status == "unavailable"
    assert result.assessment.reason == "invalid_reference_point"
