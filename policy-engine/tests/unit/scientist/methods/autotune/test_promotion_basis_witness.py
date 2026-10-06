"""Behavioral witnesses for immutable comparison and canonical publication."""

from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.cheap_stage import (
    CheapStageBenchmarkEvaluator,
    CheapStageTuningConfig,
    write_correlation_dataset,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    benchmark_comparison_basis,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver


class _Mutation(MutationArtifact):
    value: int


def _policy(*, direction=MetricDirection.MAXIMIZE, unit="points") -> PromotionPolicy:
    return PromotionPolicy(
        loop_id="comparison-witness",
        primary_metric="score",
        unit=unit,
        direction=direction,
        compare_split=BenchmarkSplit.HOLDOUT,
    )


def _suite(store: FileSystemCAS) -> ArtifactRef:
    return persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="comparison-suite", data_basis="candidate_only")
    )


def _candidate(store: FileSystemCAS, suite_ref: ArtifactRef, value: int) -> ArtifactRef:
    return persist_mutation_artifact(
        store,
        _Mutation(loop_id="comparison-witness", value=value),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )


def _evaluation(store, suite_ref, candidate_ref, score, *, policy=None):
    return persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="comparison-witness",
            suite_id="comparison-suite",
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(score)},
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_basis=benchmark_comparison_basis(
                store,
                suite_ref,
                policy or _policy(),
                SchemaInfo(name="witness.linear", version="1.0"),
            ),
        ),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )


def test_actual_incumbent_evaluation_cannot_be_replaced_by_pointer_score(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    strong = _candidate(store, suite, 3)
    strong_eval = _evaluation(store, suite, strong, 3)
    assert registry.consider_promotion(
        "comparison-witness", strong, strong_eval, _policy(), suite_ref=suite
    ).promoted
    path = tmp_path / "registry" / "comparison-witness" / "champion.json"
    pointer = json.loads(path.read_text())
    pointer["metrics"]["score"] = 0.0
    path.write_text(json.dumps(pointer))
    before = path.read_bytes()
    weak = _candidate(store, suite, 2)
    weak_eval = _evaluation(store, suite, weak, 2)
    decision = registry.consider_promotion(
        "comparison-witness", weak, weak_eval, _policy(), suite_ref=suite
    )
    assert not decision.promoted
    assert path.read_bytes() == before


def test_policy_unit_and_direction_are_part_of_the_comparison_basis(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    first = _candidate(store, suite, 3)
    assert registry.consider_promotion(
        "comparison-witness",
        first,
        _evaluation(store, suite, first, 3),
        _policy(),
        suite_ref=suite,
    ).promoted
    second = _candidate(store, suite, 2)
    changed_policy = _policy(direction=MetricDirection.MINIMIZE, unit="seconds")
    decision = registry.consider_promotion(
        "comparison-witness",
        second,
        _evaluation(store, suite, second, 2, policy=changed_policy),
        changed_policy,
        suite_ref=suite,
    )
    assert not decision.promoted
    assert registry.get("comparison-witness").candidate_ref == first


def test_evaluation_candidate_identity_includes_the_selected_manifest_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    first = _candidate(store, suite, 3)
    other_suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="other-suite", data_basis="candidate_only")
    )
    other_view = _candidate(store, other_suite, 3)
    assert first.artifact_id == other_view.artifact_id
    assert first.manifest_profile_sha256 != other_view.manifest_profile_sha256
    evaluation = _evaluation(store, suite, other_view, 3)
    decision = registry.consider_promotion(
        "comparison-witness", first, evaluation, _policy(), suite_ref=suite
    )
    assert not decision.promoted
    assert registry.get("comparison-witness") is None


def test_real_cheap_stage_consumes_frozen_dataset_and_split_after_paths_change(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    records = [
        {
            "candidate_hash": str(i),
            "stage_a_score": 0.1 if i % 2 == 0 else 0.9,
            "stage_b_score": float(i % 2),
            "stage_b_approved": i % 2 == 0,
        }
        for i in range(200)
    ]
    suite = write_correlation_dataset(records, output_dir=tmp_path / "inputs")
    suite_ref = persist_benchmark_suite(store, suite)
    candidate = persist_mutation_artifact(store, CheapStageTuningConfig(threshold=0.5))
    evaluator = CheapStageBenchmarkEvaluator(store=store)
    first = evaluator.evaluate(candidate, suite_ref, {"store": store})
    Path(suite.dataset_path).write_text(
        "\n".join(
            json.dumps({**row, "stage_b_approved": not row["stage_b_approved"]}) for row in records
        )
    )
    second = evaluator.evaluate(candidate, suite_ref, {"store": store})
    assert first.holdout_metrics["false_positive_rate"] == 0.0
    assert first.holdout_metrics["true_positive_rate"] == 1.0
    assert second.holdout_metrics == first.holdout_metrics
    assert second.sample_counts == {"selection": 160, "holdout": 40}


class _Evaluator:
    def evaluate(self, candidate_ref, suite_ref, context):
        del suite_ref
        payload = json.loads(context["store"].get_bytes(candidate_ref.artifact_id))
        return BenchmarkEvaluation(
            loop_id="comparison-witness",
            suite_id="comparison-suite",
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(payload["value"])},
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
        )


def test_existing_runner_invokes_public_ask_and_tell(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    calls = {"ask": 0, "tell": 0}
    for name in calls:
        original = getattr(_NativeSearchServiceDriver, name)

        def traced(self, *args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(_NativeSearchServiceDriver, name, traced)
    spec = SearchLoopSpec(
        loop_id="comparison-witness",
        mutation_codec=PydanticMutationCodec(_Mutation),
        candidate_generator=SequenceCandidateGenerator(
            [
                _Mutation(loop_id="comparison-witness", value=2),
                _Mutation(loop_id="comparison-witness", value=3),
            ]
        ),
        benchmark_evaluator=_Evaluator(),
        promotion_policy=_policy(),
    )
    result = SearchLoopRunner(
        store=store, registry=ChampionRegistry(root=tmp_path / "registry", store=store)
    ).run(spec, suite_ref=_suite(store), max_iterations=2)
    assert result.iterations_completed == 2
    assert calls == {"ask": 2, "tell": 2}
