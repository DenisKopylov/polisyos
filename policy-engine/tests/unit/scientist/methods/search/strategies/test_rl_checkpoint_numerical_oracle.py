"""Actual nested random and Sobol continuation through the RL wrapper."""

import json

import pytest

from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, StrategyState


@pytest.mark.parametrize("kind", ["random", "sobol"])
def test_wrapper_and_nested_rng_actual_consumers_resume(kind):
    space = SearchSpace([ParameterBounds("x")])

    def make():
        base = (
            RandomSearchStrategy(space, seed=38)
            if kind == "random"
            else BayesianOptimizer(space, BayesianConfig(seed=38))
        )
        return RLStrategyWrapper(base, space, RLConfig(LinearDecay(0.35, 0.35), seed=39))

    original = make()
    original.suggest([])
    saved = StrategyState.from_artifact(original.get_state().to_artifact())
    restored = make()
    restored.set_state(saved)
    assert [restored.suggest([]).params for _ in range(9)] == [
        original.suggest([]).params for _ in range(9)
    ]


@pytest.mark.parametrize(
    "payload", [None, [], True, 1, {}, {"strategy_name": "RandomSearchStrategy"}]
)
def test_nested_malformed_json_refuses_without_wrapper_or_base_mutation(payload):
    space = SearchSpace([ParameterBounds("x")])
    wrapper = RLStrategyWrapper(RandomSearchStrategy(space), space)
    saved = wrapper.get_state()
    before = saved.to_artifact()
    saved.metadata["base_state"] = json.dumps(payload)
    with pytest.raises(ValueError):
        wrapper.set_state(saved)
    assert wrapper.get_state().to_artifact() == before
