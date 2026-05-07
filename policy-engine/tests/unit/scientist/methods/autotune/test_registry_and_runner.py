from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopRunner,
    SearchLoopSpec,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.models import default_store, load_model_artifact
from polisyos.scientist.methods.autotune.runtime import (
    ChampionBackedRuntimeLoader,
    PydanticMutationCodec,
    SequenceCandidateGenerator,
)
from pydantic import ConfigDict, Field


class DummyMutationConfig(MutationArtifact):
    model_config = ConfigDict(extra="forbid")

    loop_id: str = "dummy_loop"
    value: int = Field(default=0)


class PredictableDummyEvaluator:
    def evaluate(self, candidate_ref, suite_ref, context):
        del suite_ref
        store = context["store"]
        candidate = load_model_artifact(store, candidate_ref, DummyMutationConfig)
        score = float(candidate.value)
        return BenchmarkEvaluation(
            loop_id="dummy_loop",
            suite_id="dummy_suite",
            suite_version="1.0",
            candidate_ref=candidate_ref,
            selection_metrics={"score": score},
            holdout_metrics={"score": score},
            sample_counts={
                BenchmarkSplit.SELECTION.value: 3,
                BenchmarkSplit.HOLDOUT.value: 3,
            },
            guardrails={"score_present": True},
            promotable=True,
        )


def test_default_store_uses_storage_factory(tmp_path, monkeypatch) -> None:
    seen: dict[str, object] = {}
    expected_store = FileSystemCAS(tmp_path / ".polisyos")

    def _fake_build_artifact_store(config):
        seen["config"] = config
        return expected_store

    monkeypatch.setattr(
        "polisyos.scientist.methods.autotune.models.build_artifact_store",
        _fake_build_artifact_store,
    )

    store = default_store(tmp_path / ".polisyos")

    assert store is expected_store
    assert seen["config"].backend == "filesystem"
    assert seen["config"].root == str(tmp_path / ".polisyos")


def test_autotune_persistence_helpers_accept_protocol_backed_store(tmp_path) -> None:
    backing_store = FileSystemCAS(tmp_path / ".polisyos")

    class _ArtifactStoreProxy:
        def __init__(self, store: FileSystemCAS) -> None:
            self._store = store

        def get_bytes(self, artifact_id):
            return self._store.get_bytes(artifact_id)

        def put_json(self, obj, opts, *, canon_spec=None):
            return self._store.put_json(obj, opts, canon_spec=canon_spec)

    proxy = _ArtifactStoreProxy(backing_store)
    ref = persist_mutation_artifact(proxy, DummyMutationConfig(value=5))
    loaded = load_model_artifact(proxy, ref, DummyMutationConfig)

    assert loaded.value == 5


def test_search_loop_runner_promotes_and_runtime_loader_reads_champion(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    loader = ChampionBackedRuntimeLoader(
        loop_id="dummy_loop",
        model_cls=DummyMutationConfig,
        baseline_factory=lambda context: DummyMutationConfig(value=1),
        store=store,
        registry=registry,
    )
    spec = SearchLoopSpec(
        loop_id="dummy_loop",
        mutation_codec=PydanticMutationCodec(DummyMutationConfig),
        candidate_generator=SequenceCandidateGenerator(
            [
                DummyMutationConfig(value=2),
                DummyMutationConfig(value=7),
            ]
        ),
        benchmark_evaluator=PredictableDummyEvaluator(),
        promotion_policy=PromotionPolicy(
            loop_id="dummy_loop",
            primary_metric="score",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.HOLDOUT,
            min_sample_count=1,
            required_guardrails=["score_present"],
        ),
        runtime_loader=loader,
    )

    result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        max_iterations=2,
    )

    assert result.best_candidate is not None
    assert result.best_candidate["value"] == 7
    champion = registry.get("dummy_loop")
    assert champion is not None
    loaded = loader.load()
    assert loaded.value == 7


def test_champion_registry_is_idempotent_for_same_candidate_and_evaluation(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    candidate_ref = persist_mutation_artifact(store, DummyMutationConfig(value=3))
    evaluation = BenchmarkEvaluation(
        loop_id="dummy_loop",
        suite_id="dummy_suite",
        suite_version="1.0",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 3.0},
        holdout_metrics={"score": 3.0},
        sample_counts={
            BenchmarkSplit.SELECTION.value: 1,
            BenchmarkSplit.HOLDOUT.value: 1,
        },
        guardrails={"score_present": True},
        promotable=True,
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    policy = PromotionPolicy(
        loop_id="dummy_loop",
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_sample_count=1,
        required_guardrails=["score_present"],
    )

    first = registry.consider_promotion("dummy_loop", candidate_ref, evaluation_ref, policy)
    second = registry.consider_promotion("dummy_loop", candidate_ref, evaluation_ref, policy)

    assert first.promoted is True
    assert second.promoted is False
    assert second.reason == "already_champion"
