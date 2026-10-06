"""Actual batch intake refuses unrepresentable scalars without losing valid rows."""

import pytest

from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds


@pytest.mark.parametrize("scalar", [10**400, True, False, "broken", float("inf"), float("nan")])
def test_native_batch_refuses_invalid_scalar_and_keeps_measured_rows(scalar):
    strategy = BayesianOptimizer(
        SearchSpace([ParameterBounds("x")]), BayesianConfig(n_initial=6, seed=19)
    )
    assert strategy.backend_available, "UNRUN: actual optional backend required"
    rows = [
        Evaluation(
            candidate_id=name,
            params={"x": x},
            params_normalized=(x,),
            objectives=[],
            scalar_score=score,
            stage_a_passed=True,
        )
        for name, x, score in (
            ("measured-a", 0.2, 2.0),
            ("invalid", 0.4, scalar),
            ("measured-b", 0.6, 1.0),
        )
    ]
    assert not rows[1].is_valid
    candidate = strategy.suggest(rows)
    assert candidate.source_strategy == "sobol_init"
    assert strategy._model is None
    assert [row.candidate_id for row in strategy._effective_training_corpus(rows)] == [
        "measured-a",
        "measured-b",
    ]
    assert strategy.last_training_admission_report == [
        {"candidate_id": "invalid", "reason": "invalid_outcome"},
    ]
