"""Real CAS persistence and fresh readers for declared baseline strategy states."""

from __future__ import annotations

import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.search.strategies.errors import StrategyExhaustedError
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    StrategyState,
)


def _space():
    return SearchSpace(
        [
            ParameterBounds("rate", 0.01, 1.0, dtype=ParameterType.LOG_CONTINUOUS),
            ParameterBounds("count", 1, 5, dtype=ParameterType.INTEGER),
            ParameterBounds("kind", dtype=ParameterType.CATEGORICAL, categories=("A", "B")),
        ]
    )


def _persist(tmp_path, strategy):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        strategy.get_state().to_artifact(),
        artifacts.PutOptions(
            kind="search.strategy_state",
            media_type="application/octet-stream",
        ),
    )
    fresh_store = artifacts.FileSystemCAS(tmp_path / "cas")
    return StrategyState.from_artifact(fresh_store.get_bytes(ref))


@pytest.mark.parametrize("kind", ["random", "grid", "rl_random", "rl_grid"])
def test_supported_baselines_actual_cas_fresh_reader_next_sequence_and_independent_replica(
    tmp_path,
    kind,
):
    space = _space()

    def make(seed):
        base = (
            GridSearchStrategy(space, seed=seed, points_per_dim=3, max_candidates=18)
            if "grid" in kind
            else RandomSearchStrategy(space, seed=seed)
        )
        return (
            RLStrategyWrapper(base, space, RLConfig(LinearDecay(0.35, 0.35), seed=seed + 1))
            if kind.startswith("rl_")
            else base
        )

    live = make(19)
    replica = make(71)
    independent_reference = make(71)
    for _ in range(3):
        live.suggest([])
        assert replica.suggest([]).params == independent_reference.suggest([]).params
    fresh = make(999)
    fresh.set_state(_persist(tmp_path, live))
    restored_values, replica_values = [], []
    for _ in range(8):
        resumed = fresh.suggest([]).params
        uninterrupted = live.suggest([]).params
        assert resumed == uninterrupted
        restored_values.append(resumed)
        replica_values.append(replica.suggest([]).params)
        assert replica_values[-1] == independent_reference.suggest([]).params
    if "random" in kind:
        assert restored_values != replica_values
    print("ACTUAL_BASELINE_CAS_NEXT_SEQUENCE", kind, restored_values)


def test_grid_exhausted_checkpoint_remains_exhausted_after_actual_cas_fresh_reader(tmp_path):
    space = _space()
    live = GridSearchStrategy(space, points_per_dim=3, max_candidates=3)
    assert len({repr(live.suggest([]).params) for _ in range(3)}) == 3
    fresh = GridSearchStrategy(space, points_per_dim=3, max_candidates=3)
    fresh.set_state(_persist(tmp_path, live))
    for strategy in (live, fresh):
        with pytest.raises(StrategyExhaustedError):
            strategy.suggest([])


@pytest.mark.parametrize(
    "field,value",
    [
        ("cursor", True),
        ("cursor", -1),
        ("cursor", 19),
        ("cursor", 0.5),
        ("cursor", "1"),
        ("cursor", None),
        ("grid_state_version", True),
        ("grid_state_version", 999),
        ("points_per_dim", True),
        ("points_per_dim", 4),
        ("max_candidates", True),
        ("max_candidates", 17),
        ("grid_size", True),
        ("grid_size", 17),
    ],
)
def test_grid_corrupted_own_state_refuses_before_base_mutation(tmp_path, field, value):
    space = _space()
    live = GridSearchStrategy(space, seed=19, points_per_dim=3, max_candidates=18)
    live.suggest([])
    state = _persist(tmp_path, live)
    state.iteration += 99
    state.metadata[field] = value
    fresh = GridSearchStrategy(space, seed=999, points_per_dim=3, max_candidates=18)
    before = fresh.get_state().to_artifact()
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert fresh.get_state().to_artifact() == before


@pytest.mark.parametrize(
    "field", ["cursor", "grid_state_version", "points_per_dim", "max_candidates", "grid_size"]
)
def test_grid_missing_own_state_is_explicit_incompatibility_without_mutation(tmp_path, field):
    space = _space()
    live = GridSearchStrategy(space, points_per_dim=3, max_candidates=18)
    live.suggest([])
    state = _persist(tmp_path, live)
    state.metadata.pop(field, None)
    fresh = GridSearchStrategy(space, points_per_dim=3, max_candidates=18)
    before = fresh.get_state().to_artifact()
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert fresh.get_state().to_artifact() == before


@pytest.mark.parametrize("points,cap", [(4, 18), (3, 17)])
def test_grid_foreign_configuration_is_not_the_same_continuation(tmp_path, points, cap):
    space = _space()
    live = GridSearchStrategy(space, points_per_dim=3, max_candidates=18)
    live.suggest([])
    state = _persist(tmp_path, live)
    fresh = GridSearchStrategy(space, points_per_dim=points, max_candidates=cap)
    before = fresh.get_state().to_artifact()
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert fresh.get_state().to_artifact() == before


def test_existing_custom_rl_schedule_refuses_checkpoint_with_explicit_recipe():
    space = _space()
    wrapper = RLStrategyWrapper(
        RandomSearchStrategy(space), space, RLConfig(exploration_schedule=lambda _: 0.5)
    )
    with pytest.raises(ValueError, match="supported versioned schedule"):
        wrapper.get_state()


@pytest.mark.parametrize(
    "points,cap", [(True, 18), (2.5, 18), ("3", 18), (3, True), (3, 0), (3, 2.5)]
)
def test_grid_configuration_intake_refuses_before_grid_materialization(points, cap):
    with pytest.raises(ValueError):
        GridSearchStrategy(_space(), points_per_dim=points, max_candidates=cap)


@pytest.mark.parametrize("space_value", [None, "foreign-space"])
def test_grid_missing_or_foreign_space_binding_refuses_before_live_mutation(tmp_path, space_value):
    space = _space()
    live = GridSearchStrategy(space, seed=19, points_per_dim=3, max_candidates=18)
    live.suggest([])
    state = _persist(tmp_path, live)
    state.metadata["space"] = space_value
    state.iteration += 99
    fresh = GridSearchStrategy(space, seed=999, points_per_dim=3, max_candidates=18)
    before = fresh.get_state().to_artifact()
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert fresh.get_state().to_artifact() == before
