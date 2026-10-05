"""Independent checkpoint replay and malformed nested-payload controls."""

from __future__ import annotations

import json

import pytest

from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, StrategyState


def _wrapper(seed: int, epsilon: float = 0.5) -> RLStrategyWrapper:
    space = SearchSpace([ParameterBounds("x", -2.0, 3.0)])
    return RLStrategyWrapper(
        RandomSearchStrategy(space, seed=seed + 1),
        space,
        RLConfig(LinearDecay(start=epsilon, end=epsilon), seed=seed),
    )


@pytest.mark.parametrize("payload", ["[]", "null", '"text"', "0", "true", "{}"])
def test_every_malformed_nested_json_is_a_controlled_nonmutating_refusal(payload: str) -> None:
    source = _wrapper(23)
    source.suggest([])
    state = StrategyState.from_artifact(source.get_state().to_artifact())
    state.metadata["base_state"] = payload
    target = _wrapper(901)
    before = target.get_state().to_artifact()
    with pytest.raises(ValueError):
        target.set_state(state)
    assert target.get_state().to_artifact() == before


@pytest.mark.parametrize("epsilon", [0.0, 0.5, 1.0])
def test_json_reopen_replays_nested_stream_with_restore_removal_negative(
    tmp_path,
    epsilon: float,
) -> None:
    source = _wrapper(23, epsilon)
    for _ in range(7):
        source.suggest([])
    state = source.get_state()
    path = tmp_path / "strategy.json"
    path.write_bytes(state.to_artifact())
    expected = [(c.params, c.source_strategy) for c in (source.suggest([]) for _ in range(16))]
    target = _wrapper(901, epsilon)
    target.set_state(StrategyState.from_artifact(path.read_bytes()))
    actual = [(c.params, c.source_strategy) for c in (target.suggest([]) for _ in range(16))]
    assert actual == expected
    # Preserve valid outer JSON and wrapper stream, but restart the nested base.
    removed = StrategyState.from_artifact(path.read_bytes())
    fresh = _wrapper(901, epsilon).get_state()
    removed.metadata["base_state"] = fresh.metadata["base_state"]
    damaged = _wrapper(901, epsilon)
    damaged.set_state(removed)
    observed = [(c.params, c.source_strategy) for c in (damaged.suggest([]) for _ in range(16))]
    if epsilon < 1.0:
        assert observed != expected
    else:
        # Pure exploration deliberately never consumes the nested base.
        assert observed == expected
    assert json.loads(path.read_bytes())["metadata"]["base_state"] == state.metadata["base_state"]
