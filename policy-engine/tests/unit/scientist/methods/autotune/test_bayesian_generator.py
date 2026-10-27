"""Tests for BayesianCandidateGenerator."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

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
    SearchMethodRunProfile,
)
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
)
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


def test_injected_optimizer_is_not_admitted_as_native_gp_profile() -> None:
    class InjectedOptimizer:
        _config = {"n_initial": 1}
        _space = _native_space()
        _model = None

        @staticmethod
        def _effective_training_corpus(evaluations):
            return list(evaluations)

    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    )
    generator._optimizer = InjectedOptimizer()
    generator._botorch_available = True

    profile = generator._build_source_profile(
        candidate=SimpleNamespace(source_strategy="injected_optimizer"),
        evaluations=[],
        context={"unit": "dimensionless"},
    )

    assert profile.profile_kind == "injected_optimizer"
    assert profile.optimizer_fqn.endswith("InjectedOptimizer")
    assert profile.gp_model_fqn is None
    assert profile.warm_start_eligible is False


def test_injected_optimizer_without_effective_corpus_keeps_training_unknown() -> None:
    class InjectedOptimizerWithoutCorpus:
        _config = {"n_initial": 1}
        _space = _native_space()
        _model = None

    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    )
    generator._optimizer = InjectedOptimizerWithoutCorpus()
    generator._botorch_available = True

    profile = generator._build_source_profile(
        candidate=SimpleNamespace(source_strategy="injected_optimizer"),
        evaluations=[object()],
        context={"unit": "dimensionless"},
    )

    assert profile.training_corpus_fingerprint is None
    assert profile.training_observation_count is None
    assert profile.warm_start_eligible is False


def test_source_profile_uses_canonical_effective_fit_profile() -> None:
    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 10.0}])
    )
    seen: dict[str, object] = {}

    def effective_fit_profile(**kwargs):
        seen.update(kwargs)
        return {
            "profile_kind": "configured_native_gp",
            "optimizer_fqn": (
                "polisyos.scientist.methods.search.strategies.bayesian.BayesianOptimizer"
            ),
            "optimizer_config_fingerprint": "config/actual",
            "proposal_source": kwargs["proposal_source"],
            "search_space_fingerprint": generator._search_space._native.sobol_space_fingerprint(),
            "input_transform_fingerprint": "Normalize[0,1]",
            "input_transform_state_fingerprint": "transform/fit-state",
            "outcome_transform_fingerprint": "Standardize[m=1]",
            "outcome_transform_state_fingerprint": "outcome/fit-state",
            "noise_model_fingerprint": "GaussianLikelihood[inferred]",
            "noise_model_state_fingerprint": "likelihood/fit-state",
            "objective_fingerprint": kwargs["objective_fingerprint"],
            "context_fingerprint": kwargs["context_fingerprint"],
            "training_corpus_fingerprint": "corpus/actual-fit",
            "training_observation_count": 3,
            "gp_model_fqn": "botorch.models.gp_regression.SingleTaskGP",
            "warm_start_eligible": True,
        }

    generator._optimizer.effective_fit_profile = effective_fit_profile
    profile = generator._build_source_profile(
        candidate=SimpleNamespace(source_strategy="bayesian_acquisition"),
        evaluations=[],
        context={"year": 2030},
    )

    assert profile.profile_kind == "configured_native_gp"
    assert profile.training_corpus_fingerprint is None
    assert profile.warm_start_eligible is False
    assert seen == {}


def test_method_run_profile_binds_selected_objective_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def optional_stack_unavailable() -> None:
        from polisyos.scientist.methods.search.strategies.errors import (
            OptionalDependencyUnavailableError,
        )

        raise OptionalDependencyUnavailableError("run-profile unit binding test")

    monkeypatch.setattr(
        "polisyos.scientist.methods.search.strategies.bayesian.require_botorch",
        optional_stack_unavailable,
    )
    generator = BayesianCandidateGenerator(
        search_space=AutotuneSearchSpace([{"name": "x", "lower": 0.0, "upper": 1.0}]),
        primary_metric="budget_deficit",
        direction=MetricDirection.MAXIMIZE,
    )
    objective_fingerprint = generator._objective_profile_fingerprint(unit="USD per resident")
    assert objective_fingerprint is not None

    profile = SearchMethodRunProfile(
        loop_id="loop-unit-binding",
        suite_ref=_ref(),
        method_fqn="example.methods.FiscalMethod",
        method_params_fingerprint="a" * 64,
        candidate_input_bindings={},
        data_snapshot_bindings={},
        method_seed=17,
        primary_metric="budget_deficit",
        direction="maximize",
        split="selection",
        unit="USD per resident",
        search_space_fingerprint="b" * 64,
        context_fingerprint="c" * 64,
        objective_fingerprint=objective_fingerprint,
    )
    generator.set_search_run_context({"loop": "unit-bound"})
    generator.set_search_method_run_profile(profile)
    assert generator._objective_profile_fingerprint() == objective_fingerprint
    assert generator._optimizer._run_objective_fingerprint == objective_fingerprint

    changed_unit = profile.model_copy(update={"unit": "EUR per resident"})
    with pytest.raises(ValueError, match="selected Bayesian objective basis"):
        generator.set_search_method_run_profile(changed_unit)


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
        not (evaluation.status is EvaluationStatus.SUCCESS and evaluation.scalar_score == 0.0)
        for evaluation in evaluations
    )


def test_primary_metric_admission_uses_source_rule_and_retains_unbound_diagnostics() -> None:
    generator = BayesianCandidateGenerator(
        search_space=_native_space(),
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
    )

    def history_row(
        stage_b_result: dict[str, object], objective_value: float = 123.0
    ) -> SearchIteration:
        return SearchIteration(
            iteration=0,
            candidate={"x": 2.0},
            objective_value=objective_value,
            objective_details=[
                ObjectiveValue(
                    name="score",
                    raw_value=objective_value,
                    direction=OptimizationDirection.MINIMIZE,
                )
            ],
            is_promising=True,
            stage_a_passed=True,
            stage_b_result=stage_b_result,
            duration_seconds=0.1,
            timestamp=datetime.now(UTC),
        )

    sourced = generator._history_to_evaluations(
        [history_row({"simulation_results": {"score": 0.8}})]
    )[0]
    # A numeric observation without the declared source unit is diagnostic.
    assert not sourced.is_valid
    assert sourced.scalar_score is None
    assert sourced.objectives[0].raw_value == -0.8
    assert sourced.objectives[0].score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert sourced.objectives[0].score_assessment is not None
    assert sourced.objectives[0].score_assessment.rule_spec is not None
    assert '"source_direction":"maximize"' in sourced.objectives[0].score_assessment.rule_spec

    # Entry-level scalar claims remain visible only as unbound diagnostic values.
    legacy = generator._history_to_evaluations([history_row({})])[0]
    assert not legacy.is_valid
    assert legacy.scalar_score is None
    assert legacy.objectives[0].raw_value == -123.0
    assert legacy.score_status is ObjectiveScoreStatus.UNAVAILABLE

    malformed = generator._history_to_evaluations(
        [history_row({"simulation_results": {"score": "not-a-number"}})]
    )[0]
    assert not malformed.is_valid
    assert malformed.scalar_score is None
    assert malformed.score_status is ObjectiveScoreStatus.INVALID

    conflicting = generator._history_to_evaluations(
        [history_row({"score": 0.8, "simulation_results": {"score": 0.9}})]
    )[0]
    assert not conflicting.is_valid
    assert conflicting.scalar_score is None
    assert conflicting.score_status is ObjectiveScoreStatus.INVALID


class TestBenchmarkToEvaluation:
    def test_converts_evaluation(self):
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            holdout_metrics={"score": 0.8},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            metadata={
                "metric_unit": "dimensionless",
                "params": {"x": 0.2, "y": 0.4, "z": 0.6},
                "params_normalized": [0.2, 0.4, 0.6],
            },
        )
        result = benchmark_to_evaluation(
            bench,
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            dim=3,
            expected_unit="dimensionless",
        )
        assert result is not None
        assert result.scalar_score == -0.8
        assert result.stage_a_passed is True
        assert result.is_valid
        assert result.score_assessment is not None
        assert result.metadata["search_source_assurance"] == (
            "generic_caller_declared_candidate_only"
        )
        assert result.stage_b_result == {
            "metrics": {"score": 0.8},
            "metric_units": {"score": "dimensionless"},
        }
        assert (
            benchmark_to_evaluation(
                bench.model_copy(update={"status": "failed"}),
                primary_metric="score",
                direction=MetricDirection.MAXIMIZE,
                dim=3,
                expected_unit="dimensionless",
            )
            is None
        )

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
                    "metric_unit": "dimensionless",
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
                expected_unit="dimensionless",
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
                "metric_unit": "dimensionless",
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
            expected_unit="dimensionless",
        )

        assert result is None or not result.is_valid

    def test_methodjob_unit_metadata_without_cas_verifier_is_refused(self):
        native_space = _native_space()
        bench = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref_with_id(f"sha256:{'b' * 64}"),
            selection_metrics={"score": 0.8},
            method_result_ref=_ref(),
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata={
                "candidate_id": f"sha256:{'b' * 64}",
                "evaluation_id": f"sha256:{'d' * 64}",
                "origin": "benchmark-run-metadata-unit-only",
                "params": {"x": 7.0},
                "params_normalized": list(native_space.normalize({"x": 7.0})),
                "split": "selection",
                "metric_unit": "dimensionless",
            },
        )

        assert (
            benchmark_to_evaluation(
                bench,
                primary_metric="score",
                direction=MetricDirection.MAXIMIZE,
                split=BenchmarkSplit.SELECTION,
                dim=1,
                search_space=native_space,
                expected_unit="dimensionless",
            )
            is None
        )

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
            "metric_unit": "dimensionless",
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
            expected_unit="dimensionless",
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
            expected_unit="dimensionless",
        )

        assert rejected is None or not rejected.is_valid
