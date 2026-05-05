from __future__ import annotations

import pytest
from polisyos.scientist.search.strategies.errors import StrategyExhaustedError
from polisyos.scientist.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.search.strategies.space import SearchSpace


def test_random_strategy_deterministic_seed(simple_space: SearchSpace) -> None:
    strategy_a = RandomSearchStrategy(space=simple_space, seed=7)
    strategy_b = RandomSearchStrategy(space=simple_space, seed=7)
    candidates_a = [strategy_a.suggest([]).params for _ in range(3)]
    candidates_b = [strategy_b.suggest([]).params for _ in range(3)]
    assert candidates_a == candidates_b


def test_grid_strategy_exhaustion(simple_space: SearchSpace) -> None:
    strategy = GridSearchStrategy(space=simple_space, points_per_dim=3, max_candidates=3)
    _ = strategy.suggest([])
    _ = strategy.suggest([])
    _ = strategy.suggest([])
    with pytest.raises(StrategyExhaustedError):
        strategy.suggest([])


def test_grid_state_roundtrip(simple_space: SearchSpace) -> None:
    strategy = GridSearchStrategy(space=simple_space, points_per_dim=3, max_candidates=10)
    first = strategy.suggest([])
    second = strategy.suggest([])
    state = strategy.get_state()

    restored = GridSearchStrategy(space=simple_space, points_per_dim=3, max_candidates=10)
    restored.set_state(state)
    third_from_original = strategy.suggest([])
    third_from_restored = restored.suggest([])

    assert first.params != second.params
    assert third_from_original.params == third_from_restored.params
