from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    GDPGrowthObjective,
    ObjectiveScoreStatus,
    OptimizationDirection,
    configured_objective_rule_spec,
)
from polisyos.scientist.methods.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation


def _make_eval(idx: int, x: float, y: float, space: SearchSpace) -> Evaluation:
    params = {"x": x}
    source = {"gdp_change": x, "budget_deficit": y}
    gdp = GDPGrowthObjective().evaluate(source)
    budget = BudgetDeficitObjective().evaluate(source)
    assert gdp.score_assessment is not None
    return Evaluation(
        candidate_id=f"e{idx}",
        params=params,
        params_normalized=space.normalize(params),
        objectives=[gdp, budget],
        scalar_score=gdp.raw_value,
        stage_a_passed=True,
        stage_b_result={"simulation_results": source},
        score_status=ObjectiveScoreStatus.AVAILABLE,
        score_assessment=gdp.score_assessment,
    )


def _rule_specs() -> dict[str, str]:
    return {
        "gdp_growth": configured_objective_rule_spec(GDPGrowthObjective()) or "",
        "budget_deficit": configured_objective_rule_spec(BudgetDeficitObjective()) or "",
    }


def test_mo_cold_start(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "budget_deficit"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=3, seed=4),
    )
    candidate = strategy.suggest([])
    assert candidate.source_strategy == "sobol_init"


def test_mo_pareto_front_python_fallback(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "budget_deficit"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [
        _make_eval(0, 0.0, 3.0, simple_space),
        _make_eval(1, 1.0, 2.0, simple_space),
        _make_eval(2, 2.0, 1.0, simple_space),
        _make_eval(3, 0.0, 4.0, simple_space),  # dominated by e0
    ]
    pareto = strategy.get_pareto_front(evals)
    ids = {item.candidate_id for item in pareto}
    assert "e3" not in ids
    assert {"e0", "e1", "e2"}.issubset(ids)


def test_mo_dependency_fallback(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "budget_deficit"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
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
        objective_names=["gdp_growth", "budget_deficit"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [_make_eval(i, float(i), float(5 - i), simple_space) for i in range(8)]
    batch = strategy.suggest_batch(evals, batch_size=2)
    assert len(batch) == 2
