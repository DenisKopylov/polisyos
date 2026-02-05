from __future__ import annotations

import pytest

from polisyos.scientist.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.search.strategies.space import SearchSpace

from .conftest import make_evaluation


def test_bayesian_cold_start_uses_sobol(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=3, seed=1))
    c0 = strategy.suggest([])
    c1 = strategy.suggest([make_evaluation(candidate_id="e0", params=c0.params, score=1.0, space=simple_space)])
    assert c0.source_strategy == "sobol_init"
    assert c1.source_strategy == "sobol_init"


def test_bayesian_no_dependency_fallback(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=2))
    evaluations = [
        make_evaluation(candidate_id="e0", params={"x": 0.0}, score=1.0, space=simple_space),
        make_evaluation(candidate_id="e1", params={"x": 1.0}, score=0.5, space=simple_space),
        make_evaluation(candidate_id="e2", params={"x": -1.0}, score=0.2, space=simple_space),
    ]
    candidate = strategy.suggest(evaluations)
    if fit_gpytorch_mll is None:
        assert candidate.source_strategy == "random_no_botorch"
    else:
        assert candidate.source_strategy in {
            "bayesian_acquisition",
            "random_fallback",
            "random_hard_limit",
            "random_insufficient_data",
            "random_duplicate_avoidance",
        }


def test_bayesian_state_roundtrip_without_deps(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=5))
    evals = [
        make_evaluation(candidate_id="e0", params={"x": 0.0}, score=1.0, space=simple_space),
        make_evaluation(candidate_id="e1", params={"x": 1.0}, score=0.5, space=simple_space),
    ]
    _ = strategy.suggest(evals)
    state = strategy.get_state()

    restored = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=999))
    restored.set_state(state)
    assert restored.get_state().iteration == state.iteration


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_batch_shape_when_deps_available(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=8))
    evaluations = [
        make_evaluation(candidate_id=f"e{i}", params={"x": float(i - 2)}, score=float((i - 2) ** 2), space=simple_space)
        for i in range(6)
    ]
    batch = strategy.suggest_batch(evaluations, batch_size=3)
    assert len(batch) == 3

