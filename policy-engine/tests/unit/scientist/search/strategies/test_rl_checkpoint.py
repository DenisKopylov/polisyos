"""Persisted RL wrapper and nested strategy checkpoint regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    StrategyState,
)


def _wrapper(seed: int, epsilon: float = 0.5) -> RLStrategyWrapper:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])
    return RLStrategyWrapper(
        RandomSearchStrategy(space, seed=seed + 1),
        space,
        RLConfig(LinearDecay(start=epsilon, end=epsilon), seed=seed),
    )


@pytest.mark.parametrize("epsilon", [0.0, 0.5, 1.0])
def test_persisted_checkpoint_replays_wrapper_and_nested_random(
    tmp_path: Path, epsilon: float
) -> None:
    source = _wrapper(23, epsilon)
    for _ in range(7):
        source.suggest([])
    path = tmp_path / "strategy.json"
    path.write_bytes(source.get_state().to_artifact())
    expected = [
        (candidate.params, candidate.source_strategy)
        for candidate in (source.suggest([]) for _ in range(16))
    ]
    restored = _wrapper(901, epsilon)
    restored.set_state(StrategyState.from_artifact(path.read_bytes()))
    assert [
        (candidate.params, candidate.source_strategy)
        for candidate in (restored.suggest([]) for _ in range(16))
    ] == expected


@pytest.mark.parametrize("payload", ["[]", "null", '"text"', "0", "true", "{}"])
def test_invalid_nested_checkpoint_refuses_without_mutation(payload: str) -> None:
    source = _wrapper(23)
    source.suggest([])
    state = StrategyState.from_artifact(source.get_state().to_artifact())
    state.metadata["base_state"] = payload
    target = _wrapper(901)
    before = target.get_state().to_artifact()
    with pytest.raises(ValueError):
        target.set_state(state)
    assert target.get_state().to_artifact() == before


def test_checkpoint_refuses_changed_schedule_without_mutation() -> None:
    source = _wrapper(23, 0.5)
    state = StrategyState.from_artifact(source.get_state().to_artifact())
    target = _wrapper(901, 0.25)
    before = target.get_state().to_artifact()
    with pytest.raises(ValueError):
        target.set_state(state)
    assert target.get_state().to_artifact() == before


def test_restore_of_nested_state_is_required(tmp_path: Path) -> None:
    source = _wrapper(23, 0.0)
    for _ in range(7):
        source.suggest([])
    path = tmp_path / "strategy.json"
    path.write_bytes(source.get_state().to_artifact())
    expected = [source.suggest([]).params for _ in range(8)]
    saved = StrategyState.from_artifact(path.read_bytes())
    replacement = _wrapper(901, 0.0).get_state()
    saved.metadata["base_state"] = replacement.metadata["base_state"]
    assert json.loads(path.read_bytes())["metadata"]["base_state"] != saved.metadata["base_state"]
    damaged = _wrapper(901, 0.0)
    damaged.set_state(saved)
    assert [damaged.suggest([]).params for _ in range(8)] != expected


def test_nested_grid_cursor_resumes_from_json() -> None:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])

    def make() -> RLStrategyWrapper:
        return RLStrategyWrapper(
            GridSearchStrategy(space, points_per_dim=8),
            space,
            RLConfig(LinearDecay(0.0, 0.0)),
        )

    source = make()
    for _ in range(3):
        source.suggest([])
    checkpoint = source.get_state().to_artifact()
    expected = [source.suggest([]).params for _ in range(4)]
    target = make()
    target.set_state(StrategyState.from_artifact(checkpoint))
    assert [target.suggest([]).params for _ in range(4)] == expected


@pytest.mark.parametrize("kind", ["changed_points", "bad_cursor"])
def test_nested_grid_refusal_leaves_wrapper_and_base_unchanged(kind: str) -> None:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])
    source = RLStrategyWrapper(
        GridSearchStrategy(space, points_per_dim=8, seed=7),
        space,
        RLConfig(LinearDecay(0.0, 0.0), seed=23),
    )
    for _ in range(3):
        source.suggest([])
    saved = StrategyState.from_artifact(source.get_state().to_artifact())
    target = RLStrategyWrapper(
        GridSearchStrategy(space, points_per_dim=4 if kind == "changed_points" else 8, seed=99),
        space,
        RLConfig(LinearDecay(0.0, 0.0), seed=901),
    )
    if kind == "bad_cursor":
        nested = json.loads(saved.metadata["base_state"])
        nested["iteration"] = 9
        nested["metadata"]["cursor"] = "bad"
        saved.metadata["base_state"] = json.dumps(nested)
    before = target.get_state().to_artifact()
    with pytest.raises(ValueError):
        target.set_state(saved)
    assert target.get_state().to_artifact() == before


def test_bayesian_sobol_nested_checkpoint_replays_without_fit(tmp_path: Path) -> None:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])

    def make(seed: int) -> RLStrategyWrapper:
        return RLStrategyWrapper(
            BayesianOptimizer(space, BayesianConfig(seed=38)),
            space,
            RLConfig(LinearDecay(0.0, 0.0), seed=seed),
        )

    source = make(23)
    for _ in range(3):
        assert source.suggest([]).source_strategy == "sobol_init"
    checkpoint = tmp_path / "sobol.json"
    checkpoint.write_bytes(source.get_state().to_artifact())
    expected = [source.suggest([]).params for _ in range(4)]
    target = make(901)
    target.set_state(StrategyState.from_artifact(checkpoint.read_bytes()))
    assert [target.suggest([]).params for _ in range(4)] == expected


def test_restore_keeps_shared_caller_config_unchanged() -> None:
    source = _wrapper(23)
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])
    config = RLConfig(LinearDecay(0.5, 0.5), seed=901)
    target = RLStrategyWrapper(RandomSearchStrategy(space, seed=902), space, config)
    target.set_state(StrategyState.from_artifact(source.get_state().to_artifact()))
    assert config.seed == 901
    assert target.get_state().metadata["seed"] == 23


def test_linear_decay_replays_across_changing_evaluation_counts() -> None:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])
    evaluation = Evaluation(
        candidate_id="candidate",
        params={"x": 0.0},
        params_normalized=(0.4,),
        objectives=[],
        scalar_score=None,
        stage_a_passed=False,
    )

    def make(seed: int) -> RLStrategyWrapper:
        return RLStrategyWrapper(
            RandomSearchStrategy(space, seed=seed + 1),
            space,
            RLConfig(LinearDecay(start=1.0, end=0.0, n_steps=8), seed=seed),
        )

    source = make(23)
    for count in range(5):
        source.suggest([evaluation] * count)
    checkpoint = source.get_state().to_artifact()
    expected = [source.suggest([evaluation] * count) for count in range(5, 13)]
    assert any(candidate.source_strategy == "rl_exploration" for candidate in expected)
    assert any(candidate.source_strategy == "random" for candidate in expected)
    target = make(901)
    target.set_state(StrategyState.from_artifact(checkpoint))
    actual = [target.suggest([evaluation] * count) for count in range(5, 13)]
    assert [(item.params, item.source_strategy) for item in actual] == [
        (item.params, item.source_strategy) for item in expected
    ]


def test_outer_rng_or_legacy_basis_refuses_before_nested_mutation() -> None:
    state = StrategyState.from_artifact(_wrapper(23).get_state().to_artifact())
    target = _wrapper(901)
    before = target.get_state().to_artifact()
    state.rng_state["python"]["codec_version"] += 1
    with pytest.raises(ValueError):
        target.set_state(state)
    assert target.get_state().to_artifact() == before

    state = StrategyState.from_artifact(_wrapper(23).get_state().to_artifact())
    del state.metadata["rl_state_version"]
    with pytest.raises(ValueError, match="checkpoint basis"):
        target.set_state(state)
    assert target.get_state().to_artifact() == before


@pytest.mark.parametrize("arguments", [(1.1, 0.1, 2), (1.0, -0.1, 2), (1.0, 0.1, 0)])
def test_invalid_linear_decay_is_rejected(arguments: tuple[float, float, int]) -> None:
    with pytest.raises(ValueError, match="schedule"):
        LinearDecay(*arguments)
