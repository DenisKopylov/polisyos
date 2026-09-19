"""Tests for BayesianCandidateGenerator."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace as AutotuneSearchSpace,
    benchmark_to_evaluation,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
)
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    EvaluationStatus,
    ParameterBounds,
)


def _ref() -> ArtifactRef:
    return ArtifactRef(artifact_id=f"sha256:{'a' * 64}", kind="test", media_type="application/json")


def _ref_with_id(artifact_id: str) -> ArtifactRef:
    return ArtifactRef(artifact_id=artifact_id, kind="test", media_type="application/json")


def _native_space() -> SearchSpace:
    return SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=10.0)])


class TestBayesianCandidateGeneratorFallback:
    """Tests when botorch is NOT available (fallback mode)."""

    def test_generate_returns_current_best(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([], {"x": 1.0}, {})
        assert result == {"x": 1.0}

    def test_generate_returns_last_history(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([{"a": 1}, {"b": 2}], None, {})
        assert result == {"b": 2}

    def test_generate_returns_context_when_empty(self):
        gen = BayesianCandidateGenerator(search_space=None)
        result = gen.generate([], None, {"default": True})
        assert result == {"default": True}

    def test_botorch_not_available(self):
        gen = BayesianCandidateGenerator(search_space=None)
        assert gen.botorch_available is False

    def test_warm_start_no_crash(self):
        gen = BayesianCandidateGenerator(search_space=None)
        gen.warm_start([])  # should not raise

    def test_generate_protocol_compliance(self):
        """Generator satisfies the CandidateGenerator protocol."""

        gen = BayesianCandidateGenerator(search_space=None)
        # Structural check: has generate method with correct signature
        assert hasattr(gen, "generate")
        result = gen.generate([], None, {"ctx": True})
        assert isinstance(result, dict)


def test_first_sobol_candidate_uses_native_search_space_protocol() -> None:
    """The autotune wrapper must drive a real SearchSpace on its first suggest."""
    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}]),
        n_initial=1,
        seed=7,
    )

    candidate = generator.generate(history=[], current_best=None, context={})

    assert 0.0 <= candidate["x"] <= 10.0
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"


def test_search_iteration_history_preserves_origin_params_split_and_full_ids() -> None:
    full_candidate_id = f"sha256:{'c' * 64}"
    full_evaluation_id = f"sha256:{'e' * 64}"
    iteration = SearchIteration(
        iteration=7,
        candidate={
            "x": 7.0,
            "_strategy_metadata": {
                "candidate_id": full_candidate_id,
                "evaluation_id": full_evaluation_id,
                "origin": "search-run-17",
                "split": "selection",
            },
        },
        objective_value=0.25,
        objective_details=[
            ObjectiveValue(
                name="score",
                raw_value=0.25,
                direction=OptimizationDirection.MINIMIZE,
            )
        ],
        is_promising=True,
        stage_a_passed=True,
        stage_b_result={
            "candidate_id": full_candidate_id,
            "evaluation_id": full_evaluation_id,
            "origin": "search-run-17",
            "params": {"x": 7.0},
            "score": 0.25,
            "split": "selection",
        },
        duration_seconds=0.1,
        timestamp=datetime.now(UTC),
    )
    generator = BayesianCandidateGenerator(search_space=_native_space())

    evaluations = generator._history_to_evaluations([iteration])

    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.candidate_id == full_candidate_id
    assert evaluation.params == {"x": 7.0}
    assert evaluation.params_normalized == (0.7,)
    assert evaluation.stage_b_result == iteration.stage_b_result
    assert evaluation.metadata["origin"] == "search-run-17"
    assert evaluation.metadata["split"] == "selection"
    assert evaluation.metadata["evaluation_id"] == full_evaluation_id


def test_history_without_score_is_not_a_successful_zero_observation() -> None:
    generator = BayesianCandidateGenerator(search_space=_native_space())

    evaluations = generator._history_to_evaluations([{"x": 7.0}])

    assert not any(evaluation.is_valid for evaluation in evaluations)
    assert all(
        not (
            evaluation.status is EvaluationStatus.SUCCESS
            and evaluation.scalar_score == 0.0
        )
        for evaluation in evaluations
    )


class TestBenchmarkToEvaluation:
    def test_converts_evaluation(self):
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            holdout_metrics={"score": 0.8},
        )
        result = benchmark_to_evaluation(
            bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            dim=3,
        )
        # May be None if deps unavailable
        if result is not None:
            assert result.scalar_score == -0.8
            assert result.stage_a_passed is True

    def test_returns_none_for_missing_metric(self):
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            holdout_metrics={"other": 0.5},
        )
        result = benchmark_to_evaluation(bench, primary_metric="score")
        # Either None (no deps) or None (missing metric)
        assert result is None

    def test_preserves_full_identity_split_origin_and_candidate_params(self):
        candidate_id = f"sha256:{'b' * 64}"
        evaluation_id = f"sha256:{'d' * 64}"
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref_with_id(candidate_id),
            selection_metrics={"score": 0.8},
            holdout_metrics={"score": 0.4},
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata={
                "evaluation_id": evaluation_id,
                "origin": "benchmark-run-17",
                "params": {"x": 7.0},
                "params_normalized": [0.7],
                "split": "selection",
            },
        )

        result = benchmark_to_evaluation(
            bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            split=BenchmarkSplit.SELECTION,
            dim=1,
        )

        assert result is not None
        assert result.candidate_id == candidate_id
        assert result.params == {"x": 7.0}
        assert result.params_normalized == (0.7,)
        assert result.metadata["evaluation_id"] == evaluation_id
        assert result.metadata["origin"] == "benchmark-run-17"
        assert result.metadata["split"] == "selection"
