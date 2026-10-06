"""Actual executed coordinates belong to the attainable native domain."""

import math

import pytest

from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType


@pytest.mark.parametrize("lower,upper", [(0.2, 1.8), (-1.8, -0.2), (0.2, 0.8)])
def test_fractional_integer_bounds_contain_every_executed_action(lower, upper):
    if math.ceil(lower) > math.floor(upper):
        with pytest.raises(ValueError):
            SearchSpace([ParameterBounds("n", lower, upper, ParameterType.INTEGER)])
        return
    space = SearchSpace([ParameterBounds("n", lower, upper, ParameterType.INTEGER)])
    strategy = RandomSearchStrategy(space)
    for _ in range(12):
        candidate = strategy.suggest([])
        assert lower <= candidate.params["n"] <= upper
        assert candidate.params_normalized == space.normalize(candidate.params)


def test_categorical_boolean_and_integer_have_distinct_encoding():
    space = SearchSpace(
        [ParameterBounds("c", dtype=ParameterType.CATEGORICAL, categories=(True, 1))]
    )
    assert space.normalize({"c": True}) == (1.0, 0.0)
    assert space.normalize({"c": 1}) == (0.0, 1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True])
def test_invalid_normalized_coordinate_refuses(bad):
    with pytest.raises(ValueError):
        SearchSpace([ParameterBounds("x")]).denormalize((bad,))
