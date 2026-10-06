"""The actual autotune caller uses native lifecycle and retained CAS readers."""

from __future__ import annotations

import copy

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import (
    ChampionBackedRuntimeLoader,
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.search.controller import SearchController


class _Mutation(MutationArtifact):
    loop_id: str = "native_history"
    value: int = 0


class _Evaluator:
    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
        return BenchmarkEvaluation(
            loop_id="native_history",
            suite_id="fixture",
            candidate_ref=candidate_ref,
            holdout_metrics={"score": candidate.value},
            sample_counts={"holdout": 2},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HOLDOUT,
        )


def test_native_caller_current_and_retained_readers_survive_reopen(tmp_path, monkeypatch) -> None:
    def forbidden_legacy_run(*args, **kwargs):
        raise AssertionError("autotune caller bypassed the native SearchService lifecycle")

    monkeypatch.setattr(SearchController, "run", forbidden_legacy_run)
    root = tmp_path / "cas"
    registry_root = tmp_path / "registry"
    store = FileSystemCAS(root)
    suite_ref = persist_benchmark_suite(store, BenchmarkSuite(suite_id="fixture"))

    def run(values):
        fresh_store = FileSystemCAS(root)
        registry = ChampionRegistry(root=registry_root, store=fresh_store)
        spec = SearchLoopSpec(
            loop_id="native_history",
            mutation_codec=PydanticMutationCodec(_Mutation),
            candidate_generator=SequenceCandidateGenerator(
                [_Mutation(value=value) for value in values]
            ),
            benchmark_evaluator=_Evaluator(),
            promotion_policy=PromotionPolicy(
                loop_id="native_history", primary_metric="score", min_sample_count=1
            ),
        )
        result = SearchLoopRunner(store=fresh_store, registry=registry).run(
            spec,
            suite_ref=suite_ref,
            max_iterations=len(values),
        )
        return result, registry.get("native_history")

    first, original_pointer = run([2, 7])
    retained_first = copy.deepcopy(first)
    second, current_pointer = run([9])
    assert first == retained_first
    assert first.search_id != second.search_id
    assert first.stage_b_evaluations == 2 and second.stage_b_evaluations == 1
    assert first.best_candidate["value"] == 7 and second.best_candidate["value"] == 9
    assert original_pointer.candidate_ref != current_pointer.candidate_ref

    reopened_store = FileSystemCAS(root)
    reopened_registry = ChampionRegistry(root=registry_root, store=reopened_store)
    current_loader = ChampionBackedRuntimeLoader(
        loop_id="native_history",
        model_cls=_Mutation,
        baseline_factory=lambda context: _Mutation(),
        store=reopened_store,
        registry=reopened_registry,
    )
    assert current_loader.load().value == 9
    assert load_model_artifact(reopened_store, original_pointer.candidate_ref, _Mutation).value == 7
    for iteration, expected in zip(first.history, (2, 7), strict=True):
        artifact_id = iteration.stage_b_result["simulation_results"]["evaluation_ref"]
        evaluation = load_model_artifact(
            reopened_store,
            ArtifactRef(
                artifact_id=artifact_id,
                kind="scientist.autotune.native_history.evaluation",
                media_type="application/json",
            ),
            BenchmarkEvaluation,
        )
        assert evaluation.holdout_metrics["score"] == expected
        assert (
            load_model_artifact(reopened_store, evaluation.candidate_ref, _Mutation).value
            == expected
        )
