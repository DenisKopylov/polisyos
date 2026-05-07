from __future__ import annotations

import pytest
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.methods.search.strategies.multi_objective import MOBayesianOptimizer, MOConfig
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation


def _make_eval(idx: int, x: float, y: float, space: SearchSpace) -> Evaluation:
    params = {"x": x}
    return Evaluation(
        candidate_id=f"e{idx}",
        params=params,
        params_normalized=space.normalize(params),
        objectives=[
            ObjectiveValue(name="f1", raw_value=x, direction=OptimizationDirection.MINIMIZE),
            ObjectiveValue(name="f2", raw_value=y, direction=OptimizationDirection.MINIMIZE),
        ],
        scalar_score=x + y,
        stage_a_passed=True,
        stage_b_result={"simulation_results": {"x": x, "y": y}},
    )


def test_mo_cold_start(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["f1", "f2"],
        directions=[OptimizationDirection.MINIMIZE, OptimizationDirection.MINIMIZE],
        config=MOConfig(n_initial=3, seed=4),
    )
    candidate = strategy.suggest([])
    assert candidate.source_strategy == "sobol_init"


def test_mo_pareto_front_python_fallback(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["f1", "f2"],
        directions=[OptimizationDirection.MINIMIZE, OptimizationDirection.MINIMIZE],
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [
        _make_eval(0, 0.0, 3.0, simple_space),
        _make_eval(1, 1.0, 2.0, simple_space),
        _make_eval(2, 2.0, 1.0, simple_space),
        _make_eval(3, 3.0, 3.0, simple_space),  # dominated
    ]
    pareto = strategy.get_pareto_front(evals)
    ids = {item.candidate_id for item in pareto}
    assert "e3" not in ids
    assert {"e0", "e1", "e2"}.issubset(ids)


def test_mo_dependency_fallback(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["f1", "f2"],
        directions=[OptimizationDirection.MINIMIZE, OptimizationDirection.MINIMIZE],
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [_make_eval(i, float(i), float(5 - i), simple_space) for i in range(5)]
    candidate = strategy.suggest(evals)
    if fit_gpytorch_mll is None:
        assert candidate.source_strategy == "random_no_botorch"
    else:
        assert candidate.source_strategy in {"ehvi", "random_fallback", "random_hard_limit"}


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_mo_batch_shape_when_deps_available(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["f1", "f2"],
        directions=[OptimizationDirection.MINIMIZE, OptimizationDirection.MINIMIZE],
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [_make_eval(i, float(i), float(5 - i), simple_space) for i in range(8)]
    batch = strategy.suggest_batch(evals, batch_size=2)
    assert len(batch) == 2
