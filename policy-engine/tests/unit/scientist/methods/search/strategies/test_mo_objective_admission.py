"""Declared objective vectors through actual MO frontier and fitted model consumers."""

from unittest.mock import patch

import pytest

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies import multi_objective as module
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds


def optimizer():
    space = SearchSpace([ParameterBounds("x", 0, 1)])
    return MOBayesianOptimizer(
        space,
        ["cost", "benefit"],
        [OptimizationDirection.MINIMIZE, OptimizationDirection.MAXIMIZE],
        MOConfig(n_initial=3, seed=47, num_restarts=2, raw_samples=16),
    )


def row(identity, x, cost, benefit):
    return Evaluation(
        identity,
        {"x": x},
        (x,),
        [
            ObjectiveValue("cost", cost, OptimizationDirection.MINIMIZE),
            ObjectiveValue("benefit", benefit, OptimizationDirection.MAXIMIZE),
        ],
        0.0,
        True,
    )


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("invalid", ["missing", "nan", "inf", "bool", "duplicate", "direction"])
def test_complete_vector_frontier_reports_every_excluded_original_row(native, invalid):
    strategy = optimizer()
    if native and not strategy._botorch_ready:
        pytest.skip("optional GP stack unavailable")
    strategy._botorch_ready = native
    healthy = row("complete", 0.25, 1.0, 1.0)
    rejected = row("invalid", 0.75, 0.0, 100.0)
    if invalid == "missing":
        rejected.objectives = rejected.objectives[1:]
    elif invalid in {"nan", "inf", "bool"}:
        value = {"nan": float("nan"), "inf": float("inf"), "bool": True}[invalid]
        rejected.objectives[0] = ObjectiveValue("cost", value, OptimizationDirection.MINIMIZE)
    elif invalid == "duplicate":
        rejected.objectives.append(ObjectiveValue("cost", 1.0, OptimizationDirection.MINIMIZE))
    else:
        rejected.objectives[0] = ObjectiveValue("cost", 0.0, OptimizationDirection.MAXIMIZE)
    assert [e.candidate_id for e in strategy.get_pareto_front([healthy, rejected])] == ["complete"]
    report = strategy.last_objective_admission
    assert report["status"] == "partial"
    assert report["input_count"] == 2 and report["assessed_count"] == 1
    assert report["rejected_rows"][0]["input_index"] == 1
    assert report["rejected_rows"][0]["candidate_id"] == "invalid"
    assert report["rejected_rows"][0]["reason"]


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_actual_model_list_fit_uses_only_complete_ordered_finite_vectors():
    strategy = optimizer()
    healthy = [
        row(f"complete-{i}", x, cost, benefit)
        for i, (x, cost, benefit) in enumerate(
            [(0.15, 1.0, 2.0), (0.45, 2.0, 1.0), (0.85, 3.0, 4.0)]
        )
    ]
    rejected = row("missing-cost", 0.6, 0.0, 100.0)
    rejected.objectives = rejected.objectives[1:]
    admitted = strategy._select_training_subset([*healthy, rejected])
    assert [e.candidate_id for e in admitted] == [e.candidate_id for e in healthy]
    assert strategy.last_objective_admission["input_count"] == 4
    assert strategy.last_objective_admission["assessed_count"] == 3
    # Direct training entry repeats the same admission; no row can bypass it.
    train_x, train_y = strategy._prepare_training_data([*healthy, rejected])
    assert train_x.tolist() == [[0.15], [0.45], [0.85]]
    assert train_y.tolist() == [[-1.0, 2.0], [-2.0, 1.0], [-3.0, 4.0]]
    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        strategy._fit_model_list(train_x, train_y)
    assert fit.call_count == 1
    assert len(strategy._model.models) == 2
    assert all(model.train_inputs[0].shape[0] == 3 for model in strategy._model.models)


def test_all_unassessed_cold_start_exposes_original_denominator():
    strategy = optimizer()
    rejected = row("missing-cost", 0.6, 0.0, 100.0)
    rejected.objectives = rejected.objectives[1:]
    candidate = strategy.suggest([rejected] * 5)
    assert candidate.source_strategy == "sobol_init"
    assert strategy.last_objective_admission["status"] == "unavailable"
    assert strategy.last_objective_admission["input_count"] == 5
    assert strategy.last_objective_admission["assessed_count"] == 0
