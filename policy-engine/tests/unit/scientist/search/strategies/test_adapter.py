from __future__ import annotations

from datetime import datetime

from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace


def test_adapter_generates_controller_payload(simple_space: SearchSpace) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=11)
    adapter = StrategyAdapter(strategy=strategy, space=simple_space)
    payload = adapter.generate(history=[], current_best=None, context={})
    assert "x" in payload
    assert "semantic" in payload
    assert "_strategy_metadata" in payload
    assert payload["_strategy_metadata"]["source"] == "random"


def test_adapter_syncs_history_and_status(simple_space: SearchSpace) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=11)
    adapter = StrategyAdapter(strategy=strategy, space=simple_space)
    iteration_ok = SearchIteration(
        iteration=0,
        candidate={"x": 1.0, "semantic": {"interventions": []}},
        objective_value=1.0,
        objective_details=[
            ObjectiveValue(
                name="obj",
                raw_value=1.0,
                direction=OptimizationDirection.MINIMIZE,
            )
        ],
        is_promising=True,
        stage_a_passed=True,
        stage_b_result={"simulation_results": {"x": 1.0}},
        duration_seconds=0.1,
        timestamp=datetime.utcnow(),
    )
    iteration_rejected = SearchIteration(
        iteration=1,
        candidate={"x": 2.0, "semantic": {"interventions": []}},
        objective_value=float("inf"),
        objective_details=[],
        is_promising=False,
        stage_a_passed=False,
        stage_b_result=None,
        duration_seconds=0.1,
        timestamp=datetime.utcnow(),
    )
    _ = adapter.generate(
        history=[iteration_ok, iteration_rejected],
        current_best=None,
        context={},
    )
    assert adapter._evaluations[0].is_valid
    assert not adapter._evaluations[1].is_valid


def test_adapter_batch_generation(simple_space: SearchSpace) -> None:
    strategy = RandomSearchStrategy(space=simple_space, seed=17)
    adapter = StrategyAdapter(strategy=strategy, space=simple_space)
    batch = adapter.generate_batch(
        history=[],
        current_best=None,
        context={},
        batch_size=4,
    )
    assert len(batch) == 4
    ids = [item["_strategy_metadata"]["candidate_id"] for item in batch]
    assert len(set(ids)) == 4
