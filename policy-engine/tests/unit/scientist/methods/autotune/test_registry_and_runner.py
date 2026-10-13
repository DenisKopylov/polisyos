from __future__ import annotations

import threading

import pytest
from pydantic import ConfigDict, Field

from polisyos.core.artifacts import ProducerInfo, PutOptions
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    input_ref_from_artifact_ref,
)
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
            runtime_split_type=BenchmarkSplit.HOLDOUT,
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
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
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
    runtime_split_type: BenchmarkSplit | None = BenchmarkSplit.HOLDOUT,
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
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
    )


def _selected_manifest_view(
    store: FileSystemCAS, ref: ArtifactRef, *, producer_component: str
) -> ArtifactRef:
    manifest = store.get_manifest(ref)
    selected = store.put_bytes(
        store.get_bytes(ref),
        PutOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component=producer_component, version="1.0.0"),
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == ref.artifact_id
    assert selected.manifest_profile_sha256 is not None
    assert selected.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.get_bytes(selected) == store.get_bytes(ref)
    store.get_manifest(selected)
    return selected


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
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    candidate_ref = _persist_candidate(store, value=3, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=3.0,
    )
    policy = _promotion_policy()

    first = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        policy,
        suite_ref=suite_ref,
    )
    second = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        policy,
        suite_ref=suite_ref,
    )

    assert first.promoted is True
    assert second.promoted is False
    assert second.reason == "already_champion"


def test_champion_registry_rejects_omitted_suite_binding(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="foreign_suite", suite_version="1.0"),
    )
    candidate_ref = _persist_candidate(store, value=7, suite_ref=suite_ref)
    evaluation_ref = _persist_evaluation(
        store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        score=7.0,
        suite_id="foreign_suite",
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        candidate_ref,
        evaluation_ref,
        _promotion_policy(),
    )

    assert decision.promoted is False
    assert decision.reason == "suite_ref_required"
    assert registry.get("dummy_loop") is None


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


def test_champion_registry_rejects_bound_promotion_over_unknown_seed_basis(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0"),
    )
    baseline_candidate = _persist_candidate(store, value=1, suite_ref=suite_ref)
    baseline_evaluation = _persist_evaluation(
        store,
        candidate_ref=baseline_candidate,
        suite_ref=suite_ref,
        score=1.0,
    )
    registry.seed_baseline(
        "dummy_loop",
        candidate_ref=baseline_candidate,
        evaluation_ref=baseline_evaluation,
    )
    challenger = _persist_candidate(store, value=7, suite_ref=suite_ref)
    challenger_evaluation = _persist_evaluation(
        store,
        candidate_ref=challenger,
        suite_ref=suite_ref,
        score=7.0,
    )

    decision = registry.consider_promotion(
        "dummy_loop",
        challenger,
        challenger_evaluation,
        _promotion_policy(),
        suite_ref=suite_ref,
    )

    assert decision.promoted is False
    assert decision.reason == "champion_suite_basis_unknown"
    champion = registry.get("dummy_loop")
    assert champion is not None
    assert champion.candidate_ref.artifact_id == baseline_candidate.artifact_id


def test_champion_registry_binds_selected_candidate_and_suite_views(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_default = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0")
    )
    suite_selected = _selected_manifest_view(
        store, suite_default, producer_component="tests.autotune.selected-suite-view"
    )
    candidate = _persist_candidate(store, value=7, suite_ref=suite_selected)
    evaluation = _persist_evaluation(
        store, candidate_ref=candidate, suite_ref=suite_selected, score=7.0
    )
    matched = registry.consider_promotion(
        "dummy_loop", candidate, evaluation, _promotion_policy(), suite_ref=suite_selected
    )
    assert matched.promoted
    champion = registry.get("dummy_loop")
    assert champion is not None
    assert champion.metadata["suite_ref"] == suite_selected.model_dump(mode="json")

    other_candidate = _persist_candidate(store, value=8, suite_ref=suite_default)
    other_evaluation = _persist_evaluation(
        store, candidate_ref=other_candidate, suite_ref=suite_default, score=8.0
    )
    refused = registry.consider_promotion(
        "dummy_loop",
        other_candidate,
        other_evaluation,
        _promotion_policy(),
        suite_ref=suite_default,
    )
    assert not refused.promoted
    assert refused.reason == "champion_suite_basis_mismatch"
    assert registry.get("dummy_loop") == champion


def test_champion_registry_rejects_same_candidate_bytes_with_other_selected_profile(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0")
    )
    candidate = _persist_candidate(store, value=7, suite_ref=suite_ref)
    selected_candidate = _selected_manifest_view(
        store, candidate, producer_component="tests.autotune.selected-candidate-view"
    )
    evaluation = _persist_evaluation(store, candidate_ref=candidate, suite_ref=suite_ref, score=7.0)
    decision = registry.consider_promotion(
        "dummy_loop", selected_candidate, evaluation, _promotion_policy(), suite_ref=suite_ref
    )
    assert not decision.promoted
    assert decision.reason == "evaluation_candidate_mismatch"
    assert registry.get("dummy_loop") is None


def test_persist_evaluation_preserves_candidate_profile_and_rejects_conflicting_view(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="dummy_suite", suite_version="1.0")
    )
    candidate = _persist_candidate(store, value=7, suite_ref=suite)
    selected = _selected_manifest_view(
        store, candidate, producer_component="tests.autotune.evaluation-candidate-view"
    )
    other_selected = _selected_manifest_view(
        store, candidate, producer_component="tests.autotune.other-evaluation-view"
    )
    evaluation = BenchmarkEvaluation(
        loop_id="dummy_loop",
        suite_id="dummy_suite",
        suite_version="1.0",
        candidate_ref=selected,
        selection_metrics={"score": 7.0},
        holdout_metrics={"score": 7.0},
        sample_counts={"selection": 1, "holdout": 1},
        guardrails={"score_present": True},
        promotable=True,
        runtime_split_type=BenchmarkSplit.HOLDOUT,
    )
    with pytest.raises(ValueError, match="candidate_lineage_mismatch"):
        persist_benchmark_evaluation(
            store,
            evaluation,
            inputs=[input_ref_from_artifact_ref(other_selected, role="candidate")],
        )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    candidate_edges = [
        item for item in store.get_manifest(evaluation_ref).inputs if item.role == "candidate"
    ]
    assert candidate_edges == [input_ref_from_artifact_ref(selected, role="candidate")]


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


def test_champion_registry_rejects_missing_runtime_split_when_resolution_disagrees(
    tmp_path,
) -> None:
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
        runtime_split_type=None,
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


def test_pydantic_mutation_codec_keeps_runtime_identity_after_modeling() -> None:
    from polisyos.scientist.methods.autotune.models import (
        PydanticMutationCodec as ModelCodec,
    )
    from polisyos.scientist.methods.autotune.runtime import (
        PydanticMutationCodec as RuntimeCodec,
    )

    assert RuntimeCodec is ModelCodec
    assert RuntimeCodec.__module__ == "polisyos.scientist.methods.autotune.runtime"
