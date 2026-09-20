from __future__ import annotations

import threading

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
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
    def __init__(self, *, suite_id: str = "dummy_suite", suite_version: str = "1.0") -> None:
        self._suite_id = suite_id
        self._suite_version = suite_version

    def evaluate(self, candidate_ref, suite_ref, context):
        del suite_ref
        store = context["store"]
        candidate = load_model_artifact(store, candidate_ref, DummyMutationConfig)
        score = float(candidate.value)
        return BenchmarkEvaluation(
            loop_id="dummy_loop",
            suite_id=self._suite_id,
            suite_version=self._suite_version,
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


def _promotion_policy(
    *,
    loop_id: str = "dummy_loop",
    compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT,
) -> PromotionPolicy:
    return PromotionPolicy(
        loop_id=loop_id,
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=compare_split,
        min_sample_count=1,
        required_guardrails=["score_present"],
    )


def _persist_candidate(
    store: FileSystemCAS,
    *,
    value: int,
    suite_ref,
) -> ArtifactRef:
    return persist_mutation_artifact(
        store,
        DummyMutationConfig(value=value),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )


def _persist_evaluation(
    store: FileSystemCAS,
    *,
    candidate_ref,
    suite_ref,
    score: float,
    loop_id: str = "dummy_loop",
    suite_id: str = "dummy_suite",
    suite_version: str = "1.0",
    selection_metrics: dict[str, float] | None = None,
    holdout_metrics: dict[str, float] | None = None,
    sample_counts: dict[str, int] | None = None,
    runtime_split_type: BenchmarkSplit | None = None,
):
    evaluation = BenchmarkEvaluation(
        loop_id=loop_id,
        suite_id=suite_id,
        suite_version=suite_version,
        candidate_ref=candidate_ref,
        selection_metrics=selection_metrics if selection_metrics is not None else {"score": score},
        holdout_metrics=holdout_metrics if holdout_metrics is not None else {"score": score},
        sample_counts=(
            sample_counts
            if sample_counts is not None
            else {
                BenchmarkSplit.SELECTION.value: 1,
                BenchmarkSplit.HOLDOUT.value: 1,
            }
        ),
        guardrails={"score_present": True},
        promotable=True,
        runtime_split_type=runtime_split_type,
    )
    return persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
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


def test_champion_registry_rejects_evaluation_for_different_candidate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    candidate_a = _persist_candidate(store, value=3, suite_ref=suite_ref)
    candidate_b = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_a,
        suite_ref=suite_ref,
        score=7.0,
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_b,
        evaluation_ref,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "evaluation_candidate_mismatch"
    assert registry.get("dummy_loop") is None


def test_champion_registry_rejects_evaluation_for_different_loop(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=7.0,
        loop_id="foreign_loop",
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "evaluation_loop_mismatch"
    assert registry.get("dummy_loop") is None


def test_champion_registry_rejects_policy_for_different_loop(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=7.0,
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(loop_id="foreign_loop"),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "policy_loop_mismatch"
    assert registry.get("dummy_loop") is None


@pytest.mark.parametrize(
    ("suite_id", "suite_version", "expected_reason"),
    [
        ("foreign_suite", "1.0", "suite_mismatch"),
        ("dummy_suite", "2.0", "suite_version_mismatch"),
    ],
)
def test_champion_registry_rejects_incompatible_suite(
    tmp_path,
    suite_id: str,
    suite_version: str,
    expected_reason: str,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id=suite_id, suite_version=suite_version),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=7.0,
        suite_id="dummy_suite",
        suite_version="1.0",
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == expected_reason
    assert registry.get("dummy_loop") is None


def test_champion_registry_rejects_evaluation_from_different_suite_basis(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    evaluation_suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0", metadata={"basis": "a"}),
    )
    requested_suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0", metadata={"basis": "b"}),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=evaluation_suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=evaluation_suite_ref,
        score=7.0,
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(),
        suite_ref=requested_suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "suite_basis_mismatch"
    assert registry.get("dummy_loop") is None


def test_champion_registry_rejects_wrong_comparison_split(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=7.0,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(compare_split=BenchmarkSplit.HOLDOUT),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "runtime_split_mismatch"
    assert registry.get("dummy_loop") is None


def test_champion_registry_keeps_newer_champion_when_stale_score_arrives(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    current_candidate = _persist_candidate(store, value=3, suite_ref=suite_ref)
    current_evaluation = _persist_evaluation(
        store,
        candidate_ref=current_candidate,
        suite_ref=suite_ref,
        score=3.0,
    )
    first = registry.consider_promotion(
        "dummy_loop",
        current_candidate,
        current_evaluation,
        _promotion_policy(),
        suite_ref=suite_ref,
    )
    assert first.promoted is True

    stale_candidate = _persist_candidate(store, value=2, suite_ref=suite_ref)
    stale_evaluation = _persist_evaluation(
        store,
        candidate_ref=stale_candidate,
        suite_ref=suite_ref,
        score=2.0,
    )
    second = registry.consider_promotion(
        "dummy_loop",
        stale_candidate,
        stale_evaluation,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    assert second.promoted is False
    assert second.reason == "not_better_than_champion"
    champion = registry.get("dummy_loop")
    assert champion is not None
    assert champion.candidate_ref.artifact_id == current_candidate.artifact_id
    assert champion.metrics["score"] == 3.0


def test_champion_registry_serializes_compare_and_publish_against_new_predecessor(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / ".polisyos" / "search_registry"
    seed_registry = ChampionRegistry(root=root, store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    seed_candidate = _persist_candidate(store, value=1, suite_ref=suite_ref)
    seed_evaluation = _persist_evaluation(
        store,
        candidate_ref=seed_candidate,
        suite_ref=suite_ref,
        score=1.0,
    )
    seed_registry.consider_promotion(
        "dummy_loop",
        seed_candidate,
        seed_evaluation,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    slow_registry = ChampionRegistry(root=root, store=store)
    fast_registry = ChampionRegistry(root=root, store=store)
    slow_candidate = _persist_candidate(store, value=2, suite_ref=suite_ref)
    slow_evaluation = _persist_evaluation(
        store,
        candidate_ref=slow_candidate,
        suite_ref=suite_ref,
        score=2.0,
    )
    fast_candidate = _persist_candidate(store, value=3, suite_ref=suite_ref)
    fast_evaluation = _persist_evaluation(
        store,
        candidate_ref=fast_candidate,
        suite_ref=suite_ref,
        score=3.0,
    )

    slow_read = threading.Event()
    release_slow = threading.Event()
    fast_read = threading.Event()
    release_fast = threading.Event()
    slow_done = threading.Event()
    fast_done = threading.Event()
    decisions: dict[str, object] = {}
    errors: list[BaseException] = []
    pause_slow_once = True

    original_slow_get = slow_registry.get
    original_fast_get = fast_registry.get

    def paused_slow_get(loop_id: str):
        nonlocal pause_slow_once
        current = original_slow_get(loop_id)
        if pause_slow_once:
            pause_slow_once = False
            slow_read.set()
            if not release_slow.wait(timeout=5):
                raise AssertionError("slow writer was not released")
        return current

    def paused_fast_get(loop_id: str):
        current = original_fast_get(loop_id)
        fast_read.set()
        if not release_fast.wait(timeout=5):
            raise AssertionError("fast writer was not released")
        return current

    monkeypatch.setattr(slow_registry, "get", paused_slow_get)
    monkeypatch.setattr(fast_registry, "get", paused_fast_get)

    def run_slow() -> None:
        try:
            decisions["slow"] = slow_registry.consider_promotion(
                "dummy_loop",
                slow_candidate,
                slow_evaluation,
                _promotion_policy(),
                suite_ref=suite_ref,
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            slow_done.set()

    def run_fast() -> None:
        try:
            decisions["fast"] = fast_registry.consider_promotion(
                "dummy_loop",
                fast_candidate,
                fast_evaluation,
                _promotion_policy(),
                suite_ref=suite_ref,
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            fast_done.set()

    slow_thread = threading.Thread(target=run_slow, name="opt04-slow-writer")
    fast_thread = threading.Thread(target=run_fast, name="opt04-fast-writer")
    slow_thread.start()
    assert slow_read.wait(timeout=5)
    fast_thread.start()

    try:
        fast_seen_before_release = fast_read.wait(timeout=0.5)
        if fast_seen_before_release:
            # Unlocked read/compare/publish: force the stronger writer to publish
            # before the stale writer is released, reproducing B117 deterministically.
            release_fast.set()
            assert fast_done.wait(timeout=5)
            release_slow.set()
        else:
            # A correct transaction holds the predecessor read while the slow
            # writer is paused. Once it commits, the strong writer may re-read.
            release_slow.set()
            assert fast_read.wait(timeout=5)
            release_fast.set()
        assert slow_done.wait(timeout=5)
        assert fast_done.wait(timeout=5)
    finally:
        release_slow.set()
        release_fast.set()
        slow_thread.join(timeout=5)
        fast_thread.join(timeout=5)

    assert not slow_thread.is_alive()
    assert not fast_thread.is_alive()
    assert not errors, errors
    assert set(decisions) == {"slow", "fast"}
    champion = ChampionRegistry(root=root, store=store).get("dummy_loop")
    assert champion is not None
    assert champion.metrics["score"] == 3.0


def test_search_loop_runner_rejects_evaluator_from_foreign_suite(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    spec = SearchLoopSpec(
        loop_id="dummy_loop",
        mutation_codec=PydanticMutationCodec(DummyMutationConfig),
        candidate_generator=SequenceCandidateGenerator([DummyMutationConfig(value=7)]),
        benchmark_evaluator=PredictableDummyEvaluator(suite_id="foreign_suite"),
        promotion_policy=_promotion_policy(),
    )

    result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        max_iterations=1,
    )

    assert result.history
    stage_b_result = result.history[-1].stage_b_result
    assert stage_b_result is not None
    assert stage_b_result["feedback"]["promotion_decision"]["reason"] == "suite_mismatch"
    assert registry.get("dummy_loop") is None
