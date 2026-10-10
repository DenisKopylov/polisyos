from __future__ import annotations

import json

import pytest

from polisyos.scientist.methods.search.strategies.errors import StrategyExhaustedError
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import StrategyState


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


def test_random_state_json_roundtrip_preserves_next_values_and_rejects_wrong_version(
    simple_space: SearchSpace,
) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=7)
    _ = [strategy.suggest([]) for _ in range(3)]
    artifact = strategy.get_state().to_artifact()
    decoded = StrategyState.from_artifact(artifact)

    restored = RandomSearchStrategy(space=simple_space, seed=999)
    restored.set_state(decoded)
    assert strategy.suggest([]).params == restored.suggest([]).params

    payload = json.loads(artifact.decode("utf-8"))
    payload["rng_state"]["python"]["version"] += 1
    incompatible = StrategyState.from_artifact(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    )
    with pytest.raises(ValueError, match="Python random state version"):
        restored.set_state(incompatible)
