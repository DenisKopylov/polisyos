"""Effective-action binding and bounded proposal failure on real owner paths."""

from __future__ import annotations

import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import BayesianCandidateGenerator
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.errors import StrategyError
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    ParameterType,
)


def _binary_space() -> SearchSpace:
    return SearchSpace([ParameterBounds("n", 0, 1, ParameterType.INTEGER)])


def test_raw_parameters_and_training_coordinate_must_agree() -> None:
    optimizer = BayesianOptimizer(_binary_space())
    record = Evaluation("actual-zero", {"n": 0}, (1.0,), [], 1.0, True)
    assert optimizer._select_training_subset([record]) == []
    record.params_normalized = (0.0,)
    assert optimizer._select_training_subset([record]) == [record]


def test_binary_batch_never_repeats_and_saturation_is_explicit() -> None:
    optimizer = BayesianOptimizer(_binary_space(), BayesianConfig(n_initial=6))
    batch = optimizer.suggest_batch([], 2)
    assert {candidate.params["n"] for candidate in batch} == {0, 1}
    with pytest.raises(StrategyError, match="unoccupied execution"):
        optimizer.suggest([], pending=batch)


def test_autotune_native_lifecycle_preserves_partial_result_without_repeating_action() -> None:
    space = _binary_space()
    calls = []

    class BinaryLoss:
        name = "binary_loss"

        def evaluate(self, results):
            return ObjectiveValue(self.name, results["n"], OptimizationDirection.MINIMIZE)

    def evaluate(candidate, context):
        calls.append(candidate["n"])
        return {"simulation_results": {"n": candidate["n"]}, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(10), objective=CompositeObjective([BinaryLoss()])
        ),
        candidate_generator=BayesianCandidateGenerator(space, n_initial=6),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=evaluate,
    )
    result = controller.run({})
    assert sorted(calls) == [0, 1]
    assert result.stage_b_evaluations == len(result.history) == 2
    assert result.best_candidate["n"] == 0
    assert result.stopping_reason.startswith("candidate_generation_unavailable:")
