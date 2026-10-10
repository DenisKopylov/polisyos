from __future__ import annotations

import random

import pytest

from polisyos.scientist.methods.search.strategies.codec import ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    StrategyState,
)


def test_search_space_roundtrip_mixed_types(mixed_space: SearchSpace) -> None:
    params = {"tax_rate": 0.22, "budget_steps": 3, "regime": "B"}
    normalized = mixed_space.normalize(params)
    assert len(normalized) == mixed_space.dim

    restored = mixed_space.denormalize(normalized)
    assert abs(restored["tax_rate"] - 0.22) < 1e-6
    assert restored["budget_steps"] == 3
    assert restored["regime"] == "B"


def test_sobol_sampling_is_deterministic(simple_space: SearchSpace) -> None:
    samples_a = simple_space.sample_sobol(5, seed=123)
    samples_b = simple_space.sample_sobol(5, seed=123)
    assert samples_a == samples_b
    assert len(samples_a) == 5


def test_sobol_stream_is_stable_across_request_shape_and_checkpoint(
    simple_space: SearchSpace,
) -> None:
    incremental = RandomSearchStrategy(space=simple_space, seed=123)
    incremental_points = [
        incremental._sobol_candidate(index).params_normalized for index in range(4)
    ]

    batched = RandomSearchStrategy(space=simple_space, seed=123)
    _ = batched._sobol_candidate(3)
    batched_points = [batched._sobol_candidate(index).params_normalized for index in range(4)]
    assert incremental_points == batched_points

    resumed = RandomSearchStrategy(space=simple_space, seed=123)
    _ = [resumed._sobol_candidate(index) for index in range(3)]
    state = resumed.get_state()
    restored = RandomSearchStrategy(space=simple_space, seed=999)
    restored.set_state(StrategyState.from_artifact(state.to_artifact()))
    assert (
        resumed._sobol_candidate(3).params_normalized
        == restored._sobol_candidate(3).params_normalized
    )


def test_legacy_sobol_checkpoint_fails_closed_with_exact_reason(
    simple_space: SearchSpace,
) -> None:
    restored = RandomSearchStrategy(space=simple_space, seed=123)
    legacy = StrategyState(
        strategy_name="RandomSearchStrategy",
        iteration=1,
        rng_state={"python": random.Random(123).getstate()},
    )

    restored.set_state(legacy)
    with pytest.raises(ValueError, match="Sobol checkpoint is incompatible"):
        restored._sobol_candidate(0)


def test_sobol_checkpoint_rejects_same_dimension_space_change(
    simple_space: SearchSpace,
) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=123)
    strategy._sobol_candidate(1)
    state = strategy.get_state()
    different_space = SearchSpace(
        bounds=[ParameterBounds(name="x", lower=-10.0, upper=10.0)]
    )

    restored = RandomSearchStrategy(space=different_space, seed=999)
    with pytest.raises(ValueError, match="search space changed"):
        restored.set_state(StrategyState.from_artifact(state.to_artifact()))


def test_sobol_checkpoint_rejects_cursor_cache_mismatch(
    simple_space: SearchSpace,
) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=123)
    strategy._sobol_candidate(1)
    state = strategy.get_state()
    state.rng_state["sobol"]["cursor"] += 1

    restored = RandomSearchStrategy(space=simple_space, seed=999)
    with pytest.raises(ValueError, match="cursor/cache mismatch"):
        restored.set_state(StrategyState.from_artifact(state.to_artifact()))


def test_sobol_checkpoint_rejects_saved_prefix_divergence(
    simple_space: SearchSpace,
) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=123)
    strategy._sobol_candidate(2)
    state = strategy.get_state()
    original = state.rng_state["sobol"]["cache"][1][0]
    state.rng_state["sobol"]["cache"][1][0] = 0.0 if original != 0.0 else 1.0

    restored = RandomSearchStrategy(space=simple_space, seed=999)
    with pytest.raises(ValueError, match="cached prefix diverges"):
        restored.set_state(StrategyState.from_artifact(state.to_artifact()))


def test_sobol_checkpoint_rejects_unknown_sampler_version(
    simple_space: SearchSpace,
) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=123)
    strategy._sobol_candidate(0)
    state = strategy.get_state()
    state.rng_state["sobol"]["sampler_version"] = "unknown"

    restored = RandomSearchStrategy(space=simple_space, seed=999)
    with pytest.raises(ValueError, match="sampler version is missing or unknown"):
        restored.set_state(StrategyState.from_artifact(state.to_artifact()))


def test_checkpoint_rejects_missing_python_rng_without_mutating_iteration(
    simple_space: SearchSpace,
) -> None:
    restored = RandomSearchStrategy(space=simple_space, seed=999)
    legacy = StrategyState(
        strategy_name="RandomSearchStrategy",
        iteration=99,
        rng_state={},
    )

    with pytest.raises(ValueError, match="Python random state is missing"):
        restored.set_state(legacy)
    assert restored._iteration == 0


def test_checkpoint_rejects_foreign_strategy_before_mutating_state(
    simple_space: SearchSpace,
) -> None:
    restored = RandomSearchStrategy(space=simple_space, seed=999)
    foreign = StrategyState(
        strategy_name="GridSearchStrategy",
        iteration=99,
        rng_state={"python": random.Random(123).getstate()},
    )

    with pytest.raises(ValueError, match="strategy identity changed"):
        restored.set_state(foreign)
    assert restored._iteration == 0


def test_scalar_codec_path_encode_decode() -> None:
    codec = ScalarParameterCodec(
        parameter_paths={
            "tax_rate": "semantic.interventions.0.parameters.tax_rate",
            "capex": "semantic.interventions.0.parameters.capex",
        }
    )
    candidate = {
        "semantic": {
            "interventions": [
                {"parameters": {"tax_rate": 0.18, "capex": 120.0}},
            ]
        }
    }
    encoded = codec.encode(candidate)
    assert encoded["tax_rate"] == 0.18
    assert encoded["capex"] == 120.0

    decoded = codec.decode(encoded)
    params = decoded["semantic"]["interventions"][0]["parameters"]
    assert params["tax_rate"] == 0.18
    assert params["capex"] == 120.0


def test_categorical_requires_categories() -> None:
    try:
        ParameterBounds(name="kind", dtype=ParameterType.CATEGORICAL)
    except ValueError as exc:
        assert "requires at least two categories" in str(exc)
    else:
        raise AssertionError("Expected ValueError for categorical without categories")
