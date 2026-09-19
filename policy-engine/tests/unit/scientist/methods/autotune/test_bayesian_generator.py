"""Tests for BayesianCandidateGenerator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.ids import ArtifactID
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
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    EvaluationStatus,
    ParameterBounds,
    ParameterType,
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
    """The autotune wrapper must drive the native mixed-type SearchSpace protocol."""
    native_space = SearchSpace(
        bounds=[
            ParameterBounds(name="tax_rate", lower=0.0, upper=1.0),
            ParameterBounds(
                name="budget_steps",
                lower=0,
                upper=1,
                dtype=ParameterType.INTEGER,
            ),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B", "C"),
            ),
        ]
    )
    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace(
            [
                {"name": "tax_rate", "lower": 0.0, "upper": 1.0},
                {
                    "name": "budget_steps",
                    "lower": 0,
                    "upper": 1,
                    "dtype": ParameterType.INTEGER,
                },
                {
                    "name": "regime",
                    "dtype": ParameterType.CATEGORICAL,
                    "categories": ("A", "B", "C"),
                },
            ]
        ),
        n_initial=1,
        seed=7,
    )

    candidate = generator.generate(history=[], current_best=None, context={})
    expected_vector = native_space.sample_sobol(n_samples=1, seed=7)[0]
    expected_params = native_space.denormalize(expected_vector)

    assert {name: candidate[name] for name in expected_params} == expected_params


def test_search_iteration_history_preserves_origin_params_split_and_full_ids() -> None:
    native_space = _native_space()
    observations = [
        (
            f"sha256:{'c' * 64}",
            f"sha256:{'e' * 64}",
            7.0,
            "search-run-17",
            "selection",
            0.25,
        ),
        (
            f"sha256:{'f' * 64}",
            f"sha256:{'1' * 64}",
            2.0,
            "search-run-18",
            "holdout",
            0.75,
        ),
    ]
    iterations = [
        SearchIteration(
            iteration=index,
            candidate={
                "x": x,
                "_strategy_metadata": {
                    "candidate_id": candidate_id,
                    "evaluation_id": evaluation_id,
                    "origin": origin,
                    "split": split,
                },
            },
            objective_value=score,
            objective_details=[
                ObjectiveValue(
                    name="score",
                    raw_value=score,
                    direction=OptimizationDirection.MINIMIZE,
                )
            ],
            is_promising=True,
            stage_a_passed=True,
            stage_b_result={
                "candidate_id": candidate_id,
                "evaluation_id": evaluation_id,
                "origin": origin,
                "params": {"x": x},
                "score": score,
                "split": split,
            },
            duration_seconds=0.1,
            timestamp=datetime.now(UTC),
        )
        for index, (candidate_id, evaluation_id, x, origin, split, score) in enumerate(observations)
    ]
    generator = BayesianCandidateGenerator(search_space=native_space)

    evaluations = generator._history_to_evaluations(iterations)

    assert len(evaluations) == len(observations)
    assert evaluations[0].params_normalized != evaluations[1].params_normalized
    for evaluation, (candidate_id, evaluation_id, x, origin, split, _score) in zip(
        evaluations, observations, strict=True
    ):
        assert evaluation.candidate_id == candidate_id
        assert evaluation.params == {"x": x}
        assert evaluation.params_normalized == native_space.normalize({"x": x})
        assert evaluation.metadata["origin"] == origin
        assert evaluation.metadata["split"] == split
        assert evaluation.metadata["evaluation_id"] == evaluation_id
        assert evaluation.stage_b_result is not None
        assert evaluation.stage_b_result["params"] == {"x": x}


@pytest.mark.parametrize(
    "identity_field",
    ["candidate_id", "evaluation_id", "split", "origin"],
)
def test_history_identity_conflicts_fail_closed(identity_field: str) -> None:
    native_space = _native_space()
    values = {
        "candidate_id": ("candidate-id", "runtime-id", "metadata-id"),
        "evaluation_id": ("candidate-eval", "runtime-eval", "metadata-eval"),
        "split": ("selection", "holdout", "metadata-split"),
        "origin": ("candidate-origin", "runtime-origin", "metadata-origin"),
    }
    candidate_value, runtime_value, metadata_value = values[identity_field]
    canonical_identity = {
        "candidate_id": "shared-candidate-id",
        "evaluation_id": "shared-evaluation-id",
        "split": "selection",
        "origin": "shared-origin",
    }
    candidate_metadata = dict(canonical_identity)
    runtime_identity = dict(canonical_identity)
    metadata_identity = dict(canonical_identity)
    candidate_metadata[identity_field] = candidate_value
    runtime_identity[identity_field] = runtime_value
    metadata_identity[identity_field] = metadata_value

    iteration = SearchIteration(
        iteration=0,
        candidate={"x": 7.0, "_strategy_metadata": candidate_metadata},
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
            **runtime_identity,
            "metadata": metadata_identity,
            "params": {"x": 7.0},
            "score": 0.25,
        },
        duration_seconds=0.1,
        timestamp=datetime.now(UTC),
    )

    evaluations = BayesianCandidateGenerator(search_space=native_space)._history_to_evaluations(
        [iteration]
    )

    assert not any(evaluation.is_valid for evaluation in evaluations)


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
        native_space = _native_space()
        observations = [
            (f"sha256:{'b' * 64}", f"sha256:{'d' * 64}", 7.0, "benchmark-run-17"),
            (f"sha256:{'2' * 64}", f"sha256:{'3' * 64}", 2.0, "benchmark-run-18"),
        ]
        for candidate_id, evaluation_id, x, origin in observations:
            bench = BenchmarkEvaluation(
                loop_id="loop1",
                suite_id="suite1",
                candidate_ref=_ref_with_id(candidate_id),
                selection_metrics={"score": 0.8},
                holdout_metrics={"score": 0.4},
                runtime_split_type=BenchmarkSplit.SELECTION,
                metadata={
                    "evaluation_id": evaluation_id,
                    "origin": origin,
                    "params": {"x": x},
                    "params_normalized": list(native_space.normalize({"x": x})),
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
            assert result.params == {"x": x}
            assert result.params_normalized == native_space.normalize({"x": x})
            assert result.metadata["evaluation_id"] == evaluation_id
            assert result.metadata["origin"] == origin
            assert result.metadata["split"] == "selection"

    def test_rejects_metadata_split_conflicting_with_typed_runtime_split(self):
        native_space = _native_space()
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref_with_id(f"sha256:{'b' * 64}"),
            selection_metrics={"score": 0.8},
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata={
                "evaluation_id": f"sha256:{'d' * 64}",
                "origin": "benchmark-run-conflict",
                "params": {"x": 7.0},
                "params_normalized": list(native_space.normalize({"x": 7.0})),
                "split": "holdout",
            },
        )

        result = benchmark_to_evaluation(
            bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            split=BenchmarkSplit.SELECTION,
            dim=1,
        )

        assert result is None or not result.is_valid

    def test_merges_canonical_artifact_id_wire_identity_and_rejects_distinct_wire_id(self):
        native_space = _native_space()
        typed_ref = ArtifactRef(
            artifact_id=ArtifactID.from_sha256_hex("a" * 64),
            kind="test",
            media_type="application/json",
        )
        round_tripped_ref = ArtifactRef.model_validate_json(typed_ref.model_dump_json())
        canonical_wire_id = round_tripped_ref.model_dump(mode="json")["artifact_id"]

        assert isinstance(round_tripped_ref.artifact_id, ArtifactID)
        assert canonical_wire_id == f"sha256:{'a' * 64}"
        metadata = {
            "candidate_id": canonical_wire_id,
            "evaluation_id": f"sha256:{'d' * 64}",
            "origin": "benchmark-run-canonical-id",
            "params": {"x": 7.0},
            "split": "selection",
        }
        accepted_bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=round_tripped_ref,
            selection_metrics={"score": 0.8},
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata=metadata,
        )

        accepted = benchmark_to_evaluation(
            accepted_bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            split=BenchmarkSplit.SELECTION,
            dim=1,
            search_space=native_space,
        )

        assert accepted is not None
        assert accepted.is_valid
        assert accepted.candidate_id == canonical_wire_id

        rejected_bench = accepted_bench.model_copy(
            update={"metadata": {**metadata, "candidate_id": f"sha256:{'b' * 64}"}}
        )
        rejected = benchmark_to_evaluation(
            rejected_bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            split=BenchmarkSplit.SELECTION,
            dim=1,
            search_space=native_space,
        )

        assert rejected is None or not rejected.is_valid
