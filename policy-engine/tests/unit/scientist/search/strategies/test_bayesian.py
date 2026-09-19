from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    PolicyCandidate,
)

from .conftest import make_evaluation


def test_bayesian_cold_start_uses_sobol(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=3, seed=1))
    c0 = strategy.suggest([])
    c1 = strategy.suggest(
        [make_evaluation(candidate_id="e0", params=c0.params, score=1.0, space=simple_space)]
    )
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


def test_duplicate_detection_uses_canonical_integer_and_category_execution() -> None:
    space = SearchSpace(
        bounds=[
            ParameterBounds(name="budget_steps", lower=0, upper=1, dtype=ParameterType.INTEGER),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B"),
            ),
        ]
    )
    strategy = BayesianOptimizer(space, BayesianConfig(seed=13))
    pending = PolicyCandidate(
        candidate_id="replica-a",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.12, 0.80, 0.20),
    )
    proposal = PolicyCandidate(
        candidate_id="replica-b",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.24, 0.60, 0.40),
    )

    assert proposal.params_normalized != pending.params_normalized
    assert strategy._is_duplicate(proposal, [pending])

    different_integer = PolicyCandidate(
        candidate_id="different-integer",
        params={"budget_steps": 1, "regime": "A"},
        params_normalized=(0.86, 0.80, 0.20),
    )
    different_category = PolicyCandidate(
        candidate_id="different-category",
        params={"budget_steps": 0, "regime": "B"},
        params_normalized=(0.12, 0.20, 0.80),
    )

    assert not strategy._is_duplicate(different_integer, [pending])
    assert not strategy._is_duplicate(different_category, [pending])


def test_duplicate_detection_keeps_same_replicate_different_seed_distinct() -> None:
    space = SearchSpace(
        bounds=[
            ParameterBounds(name="budget_steps", lower=0, upper=1, dtype=ParameterType.INTEGER),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B"),
            ),
        ]
    )
    strategy = BayesianOptimizer(space, BayesianConfig(seed=13))
    pending = PolicyCandidate(
        candidate_id="replica-seed-17",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.12, 0.80, 0.20),
        metadata={"replicate_id": "replicate-1", "seed": 17},
    )
    proposal = PolicyCandidate(
        candidate_id="replica-seed-23",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.24, 0.60, 0.40),
        metadata={"replicate_id": "replicate-1", "seed": 23},
    )

    assert proposal.params_normalized != pending.params_normalized
    assert not strategy._is_duplicate(proposal, [pending])


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_batch_shape_when_deps_available(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=8))
    evaluations = [
        make_evaluation(
            candidate_id=f"e{i}",
            params={"x": float(i - 2)},
            score=float((i - 2) ** 2),
            space=simple_space,
        )
        for i in range(6)
    ]
    batch = strategy.suggest_batch(evaluations, batch_size=3)
    assert len(batch) == 3


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_warm_start_reaches_gp_training_before_initial_threshold(
    simple_space: SearchSpace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm history and current observations form one compatible GP corpus."""
    strategy = BayesianOptimizer(
        simple_space,
        BayesianConfig(n_initial=6, num_restarts=3, raw_samples=32, seed=21),
    )
    warm = [
        make_evaluation(
            candidate_id=f"warm-{index}",
            params={"x": -3.5 + index},
            score=float(index),
            space=simple_space,
        )
        for index in range(6)
    ]
    warm[2].provenance_ref = "origin/run-1/evaluation-2"
    warm[2].metadata = {"replicate_id": "replica-1", "seed": 1}
    duplicate = make_evaluation(
        candidate_id="warm-2",
        params={"x": -1.5},
        score=2.0,
        space=simple_space,
    )
    duplicate.provenance_ref = "origin/run-1/evaluation-2"
    duplicate.metadata = {"replicate_id": "replica-1", "seed": 1}
    independent_replica = make_evaluation(
        candidate_id="warm-2-replica",
        params={"x": -1.5},
        score=2.25,
        space=simple_space,
    )
    independent_replica.provenance_ref = "origin/run-1/evaluation-2/replica-2"
    independent_replica.metadata = {"replicate_id": "replica-2", "seed": 2}
    warm.extend([duplicate, independent_replica])
    malformed = make_evaluation(
        candidate_id="warm-foreign-basis",
        params={"x": 4.5},
        score=7.0,
        space=simple_space,
    )
    malformed.params_normalized = (0.25, 0.75)
    warm.append(malformed)
    current = [
        make_evaluation(
            candidate_id="current-0",
            params={"x": 4.0},
            score=8.0,
            space=simple_space,
        )
    ]

    strategy.warm_start(warm)
    observed_corpus: list[tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]] = []
    observed_ids: list[tuple[str, ...]] = []
    original_prepare = strategy._prepare_training_data

    def observe_prepare(evaluations):
        observed_ids.append(tuple(evaluation.candidate_id for evaluation in evaluations))
        return original_prepare(evaluations)

    original_fit = strategy._fit_gp

    def observe_fit(X, y_bo):
        x_rows = tuple(
            tuple(float(value) for value in row)
            for row in X.detach().cpu().tolist()
        )
        y_rows = tuple(float(row[0]) for row in y_bo.detach().cpu().tolist())
        observed_corpus.append((x_rows, y_rows))
        return original_fit(X, y_bo)

    monkeypatch.setattr(strategy, "_prepare_training_data", observe_prepare)
    monkeypatch.setattr(strategy, "_fit_gp", observe_fit)
    candidate = strategy.suggest(current)

    assert len(observed_ids) == 1
    expected_ids = [evaluation.candidate_id for evaluation in warm[:6]] + [
        "warm-2-replica",
        "current-0",
    ]
    assert sorted(observed_ids[0]) == sorted(expected_ids)
    assert "warm-foreign-basis" not in observed_ids[0]
    assert len(observed_corpus) == 1
    observed_x, observed_y = observed_corpus[0]
    expected_by_id = {
        evaluation.candidate_id: evaluation for evaluation in [*warm, *current]
    }
    expected_evaluations = [expected_by_id[candidate_id] for candidate_id in observed_ids[0]]
    expected_x = tuple(
        tuple(float(value) for value in evaluation.params_normalized)
        for evaluation in expected_evaluations
    )
    expected_y = tuple(-float(evaluation.scalar_score) for evaluation in expected_evaluations)
    for actual_row, expected_row in zip(observed_x, expected_x, strict=True):
        assert actual_row == pytest.approx(expected_row)
    assert observed_y == pytest.approx(expected_y)
    assert candidate.source_strategy == "bayesian_acquisition"
    assert candidate.acquisition_value is not None
    assert candidate.predicted_mean is not None
    assert candidate.predicted_std is not None
    assert math.isfinite(candidate.acquisition_value)
    assert math.isfinite(candidate.predicted_mean)
    assert math.isfinite(candidate.predicted_std)


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_no_refit_preserves_learned_gp_state_with_new_observation(
    simple_space: SearchSpace,
) -> None:
    """A pre-refit-interval observation conditions the fitted GP instead of resetting it."""
    strategy = BayesianOptimizer(
        simple_space,
        BayesianConfig(
            n_initial=1,
            num_restarts=3,
            raw_samples=32,
            refit_interval=10,
            seed=22,
        ),
    )
    initial = [
        make_evaluation(
            candidate_id=f"initial-{index}",
            params={"x": -3.5 + index},
            score=float((index - 3) ** 2),
            space=simple_space,
        )
        for index in range(8)
    ]
    strategy.suggest(initial)
    assert strategy._model is not None
    model_before = strategy._model
    learned_before = {
        name: parameter.detach().clone()
        for name, parameter in model_before.named_parameters()
    }
    transform_state_before = {}
    for attribute in ("input_transform", "outcome_transform"):
        transform = getattr(model_before, attribute, None)
        assert transform is not None
        transform_state_before[attribute] = {
            name: value.detach().clone() for name, value in transform.state_dict().items()
        }

    expanded = initial + [
        make_evaluation(
            candidate_id="new-observation",
            params={"x": 4.0},
            score=0.25,
            space=simple_space,
        )
    ]
    strategy.suggest(expanded)

    assert strategy._model is not None
    model_train_X = strategy._model.train_inputs[0]
    model_train_X = model_train_X.reshape(-1, model_train_X.shape[-1])
    actual_train_rows = tuple(
        tuple(float(value) for value in row)
        for row in model_train_X.detach().cpu().tolist()
    )
    expected_train_rows = tuple(
        tuple(float(value) for value in evaluation.params_normalized)
        for evaluation in expanded
    )
    assert len(actual_train_rows) == len(expected_train_rows) == 9
    for actual_row, expected_row in zip(actual_train_rows, expected_train_rows, strict=True):
        assert actual_row == pytest.approx(expected_row)
    learned_after = dict(strategy._model.named_parameters())
    assert set(learned_before).issubset(learned_after)
    for name, parameter in learned_before.items():
        assert strategy._torch.equal(parameter, learned_after[name].detach())
    for attribute, before_state in transform_state_before.items():
        transform_after = getattr(strategy._model, attribute, None)
        assert transform_after is not None
        after_state = transform_after.state_dict()
        assert set(after_state) == set(before_state)
        for name, value in before_state.items():
            assert strategy._torch.equal(value, after_state[name].detach())
