"""Executed actions remain inside their finite, attainable physical domains."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType


@pytest.mark.parametrize("lower,upper", [(0.2, 1.8), (-1.8, -0.2), (-1.2, 1.2)])
def test_fractional_integer_bounds_on_native_random_and_sobol(lower, upper) -> None:
    space = SearchSpace([ParameterBounds("n", lower, upper, dtype=ParameterType.INTEGER)])
    random = RandomSearchStrategy(space, seed=42)
    for index in range(16):
        candidates = [random.suggest([]), random._sobol_candidate(index)]
        for candidate in candidates:
            action = candidate.params["n"]
            assert isinstance(action, int)
            assert math.ceil(lower) <= action <= math.floor(upper)
            assert candidate.params_normalized == space.normalize(candidate.params)
            space.validate_params(candidate.params)


@pytest.mark.parametrize("lower,upper", [(0.2, 0.8), (-0.8, -0.2)])
def test_empty_integer_domain_refuses_before_sampling(lower, upper) -> None:
    with pytest.raises(ValueError, match="no attainable"):
        ParameterBounds("n", lower, upper, dtype=ParameterType.INTEGER)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_coordinates_cannot_decode_to_actions(value) -> None:
    space = SearchSpace(
        [
            ParameterBounds("x"),
            ParameterBounds("c", dtype=ParameterType.CATEGORICAL, categories=("a", "b")),
        ]
    )
    for vector in ((value, 0.0, 1.0), (0.5, value, 1.0)):
        with pytest.raises(ValueError, match="finite"):
            space.denormalize(vector)
    with pytest.raises(ValueError, match="Finite"):
        space.normalize({"x": value, "c": "a"})


def test_continuous_log_and_extreme_finite_coordinates_preserve_bounds() -> None:
    spaces = [
        SearchSpace([ParameterBounds("x", -0.3, 0.7)]),
        SearchSpace([ParameterBounds("x", 0.1, 30, dtype=ParameterType.LOG_CONTINUOUS)]),
        SearchSpace([ParameterBounds("x", -1e308, 1e308)]),
    ]
    for space in spaces:
        for normalized in (0.0, 0.1, 0.5, 0.9, 1.0):
            candidate = space.candidate_from_vector((normalized,), source_strategy="fixture")
            space.validate_params(candidate.params)
            assert candidate.params_normalized == pytest.approx((normalized,), abs=1e-12)


def test_physical_observation_admission_does_not_hide_clipped_actions() -> None:
    space = SearchSpace([ParameterBounds("n", 0.2, 1.8, dtype=ParameterType.INTEGER)])
    for action in (0, 2, 0.5, math.nan):
        with pytest.raises(ValueError):
            space.validate_params({"n": action})
