"""Persisted replay checks for the exploration wrapper and its base strategy."""

from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, StrategyState


def _wrapper(*, seed: int = 23, epsilon: float = 0.5) -> RLStrategyWrapper:
    space = SearchSpace(bounds=[ParameterBounds(name="x", lower=-2.0, upper=3.0)])
    return RLStrategyWrapper(
        RandomSearchStrategy(space, seed=seed + 1),
        space,
        RLConfig(LinearDecay(start=epsilon, end=epsilon), seed=seed),
    )


@pytest.mark.parametrize("epsilon", [0.0, 0.5, 1.0])
def test_persisted_wrapper_replays_both_random_streams(tmp_path, epsilon: float) -> None:
    uninterrupted = _wrapper(epsilon=epsilon)
    for _ in range(9):
        uninterrupted.suggest([])
    path = tmp_path / "strategy.json"
    path.write_bytes(uninterrupted.get_state().to_artifact())
    expected = [uninterrupted.suggest([]) for _ in range(12)]

    reopened = _wrapper(seed=901, epsilon=epsilon)
    reopened.set_state(StrategyState.from_artifact(path.read_bytes()))
    actual = [reopened.suggest([]) for _ in range(12)]
    assert [(c.params, c.source_strategy) for c in actual] == [
        (c.params, c.source_strategy) for c in expected
    ]

    fresh = _wrapper(seed=901, epsilon=epsilon)
    assert [fresh.suggest([]).params for _ in range(12)] != [c.params for c in expected]


def test_wrapper_restores_nested_sobol_prefix(tmp_path) -> None:
    source = _wrapper()
    source._base._sobol_candidate(2)
    path = tmp_path / "strategy.json"
    path.write_bytes(source.get_state().to_artifact())
    target = _wrapper(seed=901)
    target.set_state(StrategyState.from_artifact(path.read_bytes()))
    assert target._base._sobol_candidate(3).params == source._base._sobol_candidate(3).params


def test_arbitrary_callable_schedule_is_not_a_replay_basis() -> None:
    target = _wrapper()
    target._config.exploration_schedule = lambda iteration: 0.5
    with pytest.raises(ValueError, match="replayable LinearDecay"):
        target.get_state()


@pytest.mark.parametrize("field", ["strategy_name", "iteration", "rng", "base", "space"])
def test_corrupt_wrapper_checkpoint_refuses_without_mutating_state(field: str) -> None:
    source = _wrapper()
    source.suggest([])
    state = StrategyState.from_artifact(source.get_state().to_artifact())
    if field == "strategy_name":
        state.strategy_name = "RandomSearchStrategy"
    elif field == "iteration":
        state.iteration = -1
    elif field == "rng":
        state.rng_state["python"] = None
    elif field == "base":
        state.metadata["base_state"] = "{}"
    else:
        state.metadata["space"] = "foreign"

    target = _wrapper()
    before = deepcopy(target.get_state())
    with pytest.raises(ValueError):
        target.set_state(state)
    assert target.get_state() == before


def test_changed_schedule_refuses_resume_before_mutation() -> None:
    state = StrategyState.from_artifact(_wrapper(epsilon=0.0).get_state().to_artifact())
    target = _wrapper(epsilon=1.0)
    before = target.get_state()
    with pytest.raises(ValueError, match="schedule"):
        target.set_state(state)
    assert target.get_state() == before
