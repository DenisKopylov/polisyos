"""Persisted strategy types and semantic action identities."""

import json

import pytest

from polisyos.scientist.methods.search.frontier import policy_candidate_hash
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, StrategyState


@pytest.mark.parametrize("bad", [True, 1.0])
@pytest.mark.parametrize("field", ["codec_version", "algorithm_version", "dimension"])
def test_schema_integers_refuse_boolean_and_float(field, bad):
    strategy = RandomSearchStrategy(SearchSpace([ParameterBounds("x")]))
    state = StrategyState.from_artifact(strategy.get_state().to_artifact())
    before = strategy.get_state().to_artifact()
    state.rng_state["sobol"][field] = bad
    with pytest.raises(ValueError):
        strategy.set_state(state)
    assert strategy.get_state().to_artifact() == before


@pytest.mark.parametrize("payload", [None, [], 1, True, {}, {"strategy_name": "x"}])
def test_malformed_artifact_has_controlled_refusal(payload):
    with pytest.raises(ValueError):
        StrategyState.from_artifact(json.dumps(payload).encode())


@pytest.mark.parametrize("schema", [None, True, 2, "strategy_state.v999"])
def test_present_invalid_schema_is_not_legacy_absence(schema):
    strategy = RandomSearchStrategy(SearchSpace([ParameterBounds("x")]))
    before = strategy.get_state().to_artifact()
    payload = json.loads(before)
    payload["schema_version"] = schema
    with pytest.raises(ValueError):
        strategy.set_state(StrategyState.from_artifact(json.dumps(payload).encode()))
    assert strategy.get_state().to_artifact() == before
    payload.pop("schema_version")
    strategy.set_state(StrategyState.from_artifact(json.dumps(payload).encode()))
    assert strategy.get_state().to_artifact() == before


def test_nested_semantic_metadata_date_is_identity():
    first = {"semantic": {"metadata": {"starts_at": "2026-01-01"}}}
    second = {"semantic": {"metadata": {"starts_at": "2026-02-01"}}}
    assert policy_candidate_hash(first) != policy_candidate_hash(second)
    assert policy_candidate_hash({**first, "created_at": "2026-03-01"}) == policy_candidate_hash(
        first
    )


def test_actual_random_stream_survives_json_roundtrip():
    space = SearchSpace([ParameterBounds("x")])
    original = RandomSearchStrategy(space, seed=27)
    original.suggest([])
    resumed = RandomSearchStrategy(space)
    resumed.set_state(StrategyState.from_artifact(original.get_state().to_artifact()))
    assert resumed.suggest([]).params == original.suggest([]).params


@pytest.mark.parametrize("field", ["sobol_coordinate", "python_gauss_next"])
def test_unrepresentable_base_numeric_state_refuses_atomically(field):
    strategy = RandomSearchStrategy(SearchSpace([ParameterBounds("x")]), seed=31)
    strategy._sobol_candidate(0)
    before = strategy.get_state().to_artifact()
    state = StrategyState.from_artifact(before)
    if field == "sobol_coordinate":
        state.rng_state["sobol"]["cache"][0][0] = 10**400
    else:
        state.rng_state["python"]["gauss_next"] = 10**400
    with pytest.raises(ValueError):
        strategy.set_state(state)
    assert strategy.get_state().to_artifact() == before
