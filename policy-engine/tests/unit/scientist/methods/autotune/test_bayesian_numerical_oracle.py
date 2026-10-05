"""Analytic execution and training-coordinate oracles for B112/B113/B127."""

from __future__ import annotations

import json
import math
from dataclasses import asdict

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    benchmark_to_evaluation,
)
from polisyos.scientist.methods.autotune.bayesian_generator import (
    SearchSpace as AutotuneSearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
)
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType


def _mixed_space() -> SearchSpace:
    return SearchSpace(
        [
            ParameterBounds("n", 0.0, 1.0, ParameterType.INTEGER),
            ParameterBounds("kind", dtype=ParameterType.CATEGORICAL, categories=("A", "B")),
            ParameterBounds("x", 0.0, 10.0),
            ParameterBounds("rate", 0.001, 0.1, log_scale=True),
        ]
    )


def _optimizer(space: SearchSpace | AutotuneSearchSpace) -> BayesianOptimizer:
    return BayesianOptimizer(space, config=BayesianConfig(seed=17, n_initial=6))


@pytest.mark.parametrize("lower, upper", [(0.2, 1.8), (-1.8, -0.2), (0.2, 0.8)])
def test_integer_actions_stay_in_declared_physical_interval_or_bounds_are_rejected(
    lower: float, upper: float
) -> None:
    from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy

    # This is an enumerated physical domain, independent of normalization or
    # production rounding. An unsupported bounds specification may be rejected.
    feasible = set(range(math.ceil(lower), math.floor(upper) + 1))
    try:
        space = SearchSpace([ParameterBounds("n", lower, upper, ParameterType.INTEGER)])
        strategy = RandomSearchStrategy(space, seed=42)
    except ValueError:
        return
    for _ in range(10):
        candidate = strategy.suggest([])
        actual = candidate.params["n"]
        assert type(actual) is int and actual in feasible, (lower, upper, actual, feasible)


def test_autotune_first_suggestion_uses_real_space_and_checkpoint_protocol() -> None:
    """Run the default adapter and real optimizer without patching its suggestion."""
    space = AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    generator = BayesianCandidateGenerator(space, seed=17)
    assert generator.botorch_available
    candidate = generator.generate([], {"x": 7.0}, {"oracle_fallback": True})
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"
    assert 0.0 <= candidate["x"] <= 10.0
    state = generator._optimizer.get_state()
    restored = _optimizer(space)
    restored.set_state(state)
    assert restored._sobol_candidate(1).params == generator._optimizer._sobol_candidate(1).params


@pytest.mark.parametrize(
    "direction, expected_score",
    [
        (MetricDirection.MAXIMIZE, -3.0),
        (MetricDirection.MINIMIZE, 3.0),
    ],
)
def test_benchmark_actual_params_full_ids_direction_and_training_tensor(
    direction: MetricDirection,
    expected_score: float,
) -> None:
    pytest.importorskip("torch")
    space = _mixed_space()
    records = []
    for index, x in enumerate((0.0, 10.0)):
        artifact_id = "sha256:" + "a" * 63 + str(index)
        bench = BenchmarkEvaluation(
            loop_id="oracle",
            suite_id="analytic-holdout",
            candidate_ref=ArtifactRef(
                artifact_id=artifact_id, kind="oracle", media_type="application/json"
            ),
            holdout_metrics={"score": 3.0},
            metadata={
                "params": {"n": index, "kind": ("A", "B")[index], "x": x, "rate": 0.01},
                "evaluation_id": f"evaluation-{index}",
                "data_snapshot": "analytic-fixture-v1",
                "replicate_id": "r0",
            },
        )
        record = benchmark_to_evaluation(
            bench, primary_metric="score", direction=direction, search_space=space
        )
        assert record is not None and record.is_valid
        assert record.candidate_id == artifact_id
        assert "score" not in record.params
        assert record.params_normalized == pytest.approx(
            (0.0, 1.0, 0.0, 0.0, 0.5) if index == 0 else (1.0, 0.0, 1.0, 1.0, 0.5)
        )
        assert record.scalar_score == expected_score
        serialized = json.loads(json.dumps(asdict(record), default=str))
        assert serialized["candidate_id"] == artifact_id
        assert serialized["metadata"]["evaluation_id"] == f"evaluation-{index}"
        records.append(record)
    train_x, train_y = _optimizer(space)._prepare_training_data(records)
    for row, expected in zip(
        train_x.tolist(), [[0.0, 1.0, 0.0, 0.0, 0.5], [1.0, 0.0, 1.0, 1.0, 0.5]], strict=True
    ):
        assert row == pytest.approx(expected)
    assert train_y.flatten().tolist() == [-expected_score, -expected_score]


def test_missing_score_and_closed_split_do_not_become_successful_zero_training() -> None:
    space = AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    generator = BayesianCandidateGenerator(space)
    records = generator._history_to_evaluations(
        [
            {"params": {"x": 0.0}, "score": 0.0, "candidate_id": "full-zero-id"},
            {"params": {"x": 10.0}, "candidate_id": "full-missing-id"},
        ]
    )
    assert len(records) == 2
    assert records[0].params_normalized == (0.0,) and records[0].is_valid
    assert records[0].scalar_score == 0.0
    assert records[1].params_normalized == (1.0,) and not records[1].is_valid
    bench = BenchmarkEvaluation(
        loop_id="oracle",
        suite_id="hidden_holdout",
        candidate_ref=ArtifactRef(
            artifact_id="sha256:" + "b" * 64, kind="oracle", media_type="application/json"
        ),
        holdout_metrics={"score": 2.0},
        metadata={"params": {"x": 0.0}},
    )
    assert (
        benchmark_to_evaluation(
            bench,
            primary_metric="score",
            split=BenchmarkSplit.SELECTION,
            search_space=space,
        )
        is None
    )


@pytest.mark.parametrize("route", ["sobol", "random"])
def test_real_discrete_suggestion_has_coordinates_of_executed_action(route: str) -> None:
    space = _mixed_space()
    optimizer = _optimizer(space)
    candidate = optimizer.suggest([]) if route == "sobol" else optimizer._random_candidate()
    n, kind, x, rate = (candidate.params[name] for name in ("n", "kind", "x", "rate"))
    expected = (
        float(n),
        float(kind == "A"),
        float(kind == "B"),
        x / 10.0,
        math.log(rate / 0.001) / math.log(100.0),
    )
    assert candidate.params_normalized == pytest.approx(expected)


def test_initial_suggestion_does_not_repeat_pending_binary_execution() -> None:
    space = SearchSpace([ParameterBounds("n", 0.0, 1.0, ParameterType.INTEGER)])
    optimizer = _optimizer(space)
    first = optimizer.suggest([])
    second = optimizer.suggest([], pending=[first])
    assert first.params != second.params


def test_duplicate_action_control_preserves_continuous_inputs_and_replicas() -> None:
    from polisyos.scientist.methods.search.strategies.types import PolicyCandidate

    space = _mixed_space()
    optimizer = _optimizer(space)
    first = PolicyCandidate(params_normalized=(0.1, 0.9, 0.1, 0.3, 0.5))
    same_action = PolicyCandidate(params_normalized=(0.2, 0.8, 0.2, 0.3, 0.5))
    different_continuous = PolicyCandidate(params_normalized=(0.2, 0.8, 0.2, 0.4, 0.5))
    assert optimizer._is_duplicate(same_action, [first])
    assert not optimizer._is_duplicate(different_continuous, [first])
    first.metadata = {"replicate_id": "r1"}
    same_action.metadata = {"replicate_id": "r2"}
    assert not optimizer._is_duplicate(same_action, [first])


def test_optional_dependency_absence_is_distinct_from_working_optimizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.scientist.methods.autotune.bayesian_generator as adapter

    monkeypatch.setattr(adapter, "_try_import_bayesian", lambda: None)
    space = AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    generator = BayesianCandidateGenerator(space)
    assert generator.botorch_available is False
    assert generator.generate([], {"x": 7.0}, {}) == {"x": 7.0}
