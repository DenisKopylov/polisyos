from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.objective import (
    GDPGrowthObjective,
    InequalityObjective,
    ObjectiveScoreStatus,
    OptimizationDirection,
    configured_objective_rule_spec,
)
from polisyos.scientist.methods.search.strategies import multi_objective as multi_objective_module
from polisyos.scientist.methods.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation


def _make_eval(idx: int, x: float, y: float, space: SearchSpace) -> Evaluation:
    params = {"x": x}
    source = {
        "gdp_change": x,
        "gini_coefficient": y,
        "metric_units": {
            "gdp_change": "percentage-points",
            "gini_coefficient": "dimensionless",
        },
    }
    gdp = GDPGrowthObjective(expected_unit="percentage-points").evaluate(source)
    inequality = InequalityObjective(expected_unit="dimensionless").evaluate(source)
    assert gdp.score_status is ObjectiveScoreStatus.AVAILABLE
    assert inequality.score_status is ObjectiveScoreStatus.AVAILABLE
    assert gdp.score_assessment is not None
    return Evaluation(
        candidate_id=f"e{idx}",
        params=params,
        params_normalized=space.normalize(params),
        objectives=[gdp, inequality],
        scalar_score=gdp.raw_value,
        stage_a_passed=True,
        stage_b_result={"simulation_results": source},
        score_status=ObjectiveScoreStatus.AVAILABLE,
        score_assessment=gdp.score_assessment,
    )


def _rule_specs() -> dict[str, str]:
    return {
        "gdp_growth": configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="percentage-points")
        )
        or "",
        "inequality": configured_objective_rule_spec(
            InequalityObjective(expected_unit="dimensionless")
        )
        or "",
    }


def test_mo_cold_start(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "inequality"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=3, seed=4),
    )
    candidate = strategy.suggest([])
    assert candidate.source_strategy == "sobol_init"


def test_mo_pareto_front_python_fallback(simple_space: SearchSpace) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "inequality"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [
        _make_eval(0, 0.0, 0.4, simple_space),
        _make_eval(1, 1.0, 0.6, simple_space),
        _make_eval(2, 2.0, 0.8, simple_space),
        _make_eval(3, 0.0, 0.9, simple_space),  # dominated by e0
    ]
    pareto = strategy.get_pareto_front(evals)
    ids = {item.candidate_id for item in pareto}
    assert "e3" not in ids
    assert {"e0", "e1", "e2"}.issubset(ids)


def test_mo_dependency_fallback(simple_space: SearchSpace, monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing_botorch() -> None:
        raise multi_objective_module.OptionalDependencyUnavailableError(
            "fixture optional backend unavailable"
        )

    monkeypatch.setattr(multi_objective_module, "require_botorch", raise_missing_botorch)
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "inequality"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=1, seed=4),
    )
    evals = [_make_eval(i, float(i), 0.4 + 0.05 * i, simple_space) for i in range(5)]
    candidate = strategy.suggest(evals)
    assert candidate.source_strategy == "random_no_botorch"


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_mo_batch_shape_when_deps_available(
    simple_space: SearchSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy = MOBayesianOptimizer(
        simple_space,
        objective_names=["gdp_growth", "inequality"],
        directions=[OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE],
        objective_rule_specs=_rule_specs(),
        config=MOConfig(n_initial=1, num_restarts=4, raw_samples=64, seed=4),
    )
    evals = [_make_eval(i, float(i), 0.35 + 0.05 * i, simple_space) for i in range(8)]
    fit_calls = []
    optimize_calls = []
    original_fit = multi_objective_module.fit_gpytorch_mll
    original_optimize = multi_objective_module.optimize_acqf

    def tracked_fit(mll):
        fit_calls.append(mll)
        return original_fit(mll)

    def tracked_optimize(**kwargs):
        optimize_calls.append(kwargs)
        return original_optimize(**kwargs)

    monkeypatch.setattr(multi_objective_module, "fit_gpytorch_mll", tracked_fit)
    monkeypatch.setattr(multi_objective_module, "optimize_acqf", tracked_optimize)

    batch = strategy.suggest_batch(evals, batch_size=2)

    assert len(batch) == 2
    assert len(fit_calls) == 1
    assert strategy._model is not None
    assert strategy._train_X is not None
    assert tuple(strategy._train_X.shape) == (8, 1)
    assert strategy._train_Y is not None
    assert tuple(strategy._train_Y.shape) == (8, 2)
    assert len(optimize_calls) == 1
    assert optimize_calls[0]["q"] == 2
    assert isinstance(
        optimize_calls[0]["acq_function"],
        multi_objective_module.qExpectedHypervolumeImprovement,
    )
    assert [candidate.source_strategy for candidate in batch] == [
        "batch_qehvi",
        "batch_qehvi",
    ]
