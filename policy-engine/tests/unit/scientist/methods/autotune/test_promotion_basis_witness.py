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


def _evaluation(store, suite_ref, candidate_ref, score, *, policy=None, registry=None):
    basis = benchmark_comparison_basis(
        store, suite_ref, policy or _policy(), SchemaInfo(name="witness.linear", version="1.0")
    )
    incumbent_ref = None
    current = registry.get("comparison-witness") if registry is not None else None
    if current is not None:
        actual_value = json.loads(store.get_bytes(current.candidate_ref))["value"]
        incumbent_ref = persist_benchmark_evaluation(
            store,
            BenchmarkEvaluation(
                loop_id="comparison-witness",
                suite_id="comparison-suite",
                candidate_ref=current.candidate_ref,
                holdout_metrics={"score": float(actual_value)},
                sample_counts={"holdout": 1},
                runtime_split_type=BenchmarkSplit.HOLDOUT,
                promotable=True,
                comparison_basis=basis,
                comparison_predecessor_candidate_ref=current.candidate_ref,
                comparison_predecessor_evaluation_ref=current.evaluation_ref,
            ),
        )
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
            comparison_basis=basis,
            incumbent_evaluation_ref=incumbent_ref,
            comparison_predecessor_candidate_ref=current.candidate_ref
            if current is not None
            else None,
            comparison_predecessor_evaluation_ref=current.evaluation_ref
            if current is not None
            else None,
        ),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )


def test_actual_incumbent_evaluation_cannot_be_replaced_by_pointer_score(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    strong = _candidate(store, suite, 3)
    strong_eval = _evaluation(store, suite, strong, 3, registry=registry)
    assert registry.consider_promotion(
        "comparison-witness", strong, strong_eval, _policy(), suite_ref=suite
    ).promoted
    path = tmp_path / "registry" / "comparison-witness" / "champion.json"
    pointer = json.loads(path.read_text())
    pointer["metrics"]["score"] = 0.0
    path.write_text(json.dumps(pointer))
    before = path.read_bytes()
    weak = _candidate(store, suite, 2)
    weak_eval = _evaluation(store, suite, weak, 2, registry=registry)
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
        _evaluation(store, suite, first, 3, registry=registry),
        _policy(),
        suite_ref=suite,
    ).promoted
    second = _candidate(store, suite, 2)
    changed_policy = _policy(direction=MetricDirection.MINIMIZE, unit="seconds")
    decision = registry.consider_promotion(
        "comparison-witness",
        second,
        _evaluation(store, suite, second, 2, policy=changed_policy, registry=registry),
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
    evaluation = _evaluation(store, suite, other_view, 3, registry=registry)
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
    Path(suite.split_manifest_path).write_text("{}")
    second = evaluator.evaluate(candidate, suite_ref, {"store": store})
    assert first.holdout_metrics["false_positive_rate"] == 0.0
    assert first.holdout_metrics["true_positive_rate"] == 1.0
    assert second.holdout_metrics == first.holdout_metrics
    assert second.sample_counts == {"selection": 160, "holdout": 40}


class _Evaluator:
    def evaluate(self, candidate_ref, suite_ref, context):
        incumbent = context.get("benchmark_comparison_incumbent")
        del suite_ref
        payload = json.loads(context["store"].get_bytes(candidate_ref))
        return BenchmarkEvaluation(
            loop_id="comparison-witness",
            suite_id="comparison-suite",
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(payload["value"])},
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_predecessor_candidate_ref=incumbent.candidate_ref
            if incumbent is not None
            else None,
            comparison_predecessor_evaluation_ref=incumbent.evaluation_ref
            if incumbent is not None
            else None,
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


class _DatasetEvaluator:
    def __init__(self):
        self.calls = []
        self.on_incumbent = None

    def evaluate(self, candidate_ref, suite_ref, context):
        incumbent = context.get("benchmark_comparison_incumbent")
        from polisyos.scientist.methods.autotune.models import (
            benchmark_evaluator_profile,
            load_benchmark_inputs,
            load_model_artifact,
        )

        store = context["store"]
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        rows, split = load_benchmark_inputs(store, suite)
        value = json.loads(store.get_bytes(candidate_ref))["value"]
        self.calls.append((value, suite_ref))
        if self.on_incumbent is not None and value == 2:
            callback, self.on_incumbent = self.on_incumbent, None
            callback()
        score = float(rows[0]["scores"][str(value)])
        return BenchmarkEvaluation(
            loop_id="comparison-witness",
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics={"score": score},
            sample_counts={"holdout": len(split.holdout_ids)},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_basis=benchmark_comparison_basis(
                store, suite_ref, context["policy"], benchmark_evaluator_profile(self)
            ),
            comparison_predecessor_candidate_ref=incumbent.candidate_ref
            if incumbent is not None
            else None,
            comparison_predecessor_evaluation_ref=incumbent.evaluation_ref
            if incumbent is not None
            else None,
        )


def _dataset_suite(store, root, scores):
    from polisyos.scientist.methods.autotune.models import BenchmarkSplitManifest

    root.mkdir()
    dataset, split = root / "data.jsonl", root / "split.json"
    dataset.write_text(json.dumps({"id": "holdout-1", "scores": scores}) + "\n")
    split.write_text(
        BenchmarkSplitManifest(
            suite_id="comparison-suite", holdout_ids=["holdout-1"]
        ).model_dump_json()
    )
    return persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="comparison-suite", dataset_path=str(dataset), split_manifest_path=str(split)
        ),
    )


def _run_candidate(store, registry, evaluator, suite, value):
    return SearchLoopRunner(store=store, registry=registry).run(
        SearchLoopSpec(
            loop_id="comparison-witness",
            mutation_codec=PydanticMutationCodec(_Mutation),
            candidate_generator=SequenceCandidateGenerator(
                [_Mutation(loop_id="comparison-witness", value=value)]
            ),
            benchmark_evaluator=evaluator,
            promotion_policy=_policy(),
        ),
        suite_ref=suite,
        max_iterations=1,
    )


def test_suite_change_executes_incumbent_on_active_data_before_comparing(tmp_path):
    from polisyos.scientist.methods.autotune.models import load_model_artifact

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    evaluator = _DatasetEvaluator()
    old = _dataset_suite(store, tmp_path / "old", {"2": 2, "3": 3})
    _run_candidate(store, registry, evaluator, old, 2)
    incumbent = registry.get("comparison-witness")
    changed = _dataset_suite(store, tmp_path / "changed", {"2": 20, "3": 15})
    result = _run_candidate(store, registry, evaluator, changed, 3)
    assert evaluator.calls[-2:] == [(3, changed), (2, changed)]
    assert registry.get("comparison-witness") == incumbent
    decision = result.history[0].stage_b_result["feedback"]["promotion_decision"]
    assert decision["reason"] == "not_better_than_champion"
    evaluation_id = result.history[0].stage_b_result["simulation_results"]["evaluation_ref"]
    evaluation = load_model_artifact(store, evaluation_id, BenchmarkEvaluation)
    fresh = load_model_artifact(store, evaluation.incumbent_evaluation_ref, BenchmarkEvaluation)
    assert fresh.candidate_ref == incumbent.candidate_ref
    assert fresh.holdout_metrics == {"score": 20.0}
    assert fresh.comparison_basis == evaluation.comparison_basis
    winning = _dataset_suite(store, tmp_path / "winning", {"2": 20, "3": 30})
    _run_candidate(store, registry, evaluator, winning, 3)
    reopened = ChampionRegistry(root=tmp_path / "registry", store=FileSystemCAS(tmp_path / "cas"))
    assert reopened.get("comparison-witness").metrics == {"score": 30.0}
    assert evaluator.calls[-2:] == [(3, winning), (2, winning)]


def test_canonical_incumbent_change_during_real_reevaluation_refuses_stale_comparison(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    evaluator = _DatasetEvaluator()
    old = _dataset_suite(store, tmp_path / "old", {"2": 2, "3": 3, "4": 4})
    _run_candidate(store, registry, evaluator, old, 2)
    changed = _dataset_suite(store, tmp_path / "changed", {"2": 20, "3": 30, "4": 40})
    competitor = _DatasetEvaluator()
    evaluator.on_incumbent = lambda: _run_candidate(store, registry, competitor, changed, 4)
    result = _run_candidate(store, registry, evaluator, changed, 3)
    assert evaluator.calls[-2:] == [(3, changed), (2, changed)]
    decision = result.history[0].stage_b_result["feedback"]["promotion_decision"]
    assert decision["reason"] == "incumbent_changed_during_evaluation"
    assert not decision["promoted"]
    reopened = ChampionRegistry(root=tmp_path / "registry", store=FileSystemCAS(tmp_path / "cas"))
    assert reopened.get("comparison-witness").metrics == {"score": 40.0}


def test_pointer_replace_fault_preserves_complete_old_or_new_fresh_reader(tmp_path, monkeypatch):
    import os

    import pytest

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    first = _candidate(store, suite, 2)
    registry.consider_promotion(
        "comparison-witness",
        first,
        _evaluation(store, suite, first, 2, registry=registry),
        _policy(),
        suite_ref=suite,
    )
    second = _candidate(store, suite, 3)
    second_evaluation = _evaluation(store, suite, second, 3, registry=registry)
    pointer_path = tmp_path / "registry" / "comparison-witness" / "champion.json"
    before = pointer_path.read_bytes()
    replace = os.replace
    for after_replace in (False, True):

        def interrupted(source, target, *, _after=after_replace):
            if Path(target) == pointer_path:
                if _after:
                    replace(source, target)
                raise OSError("injected pointer replacement interruption")
            return replace(source, target)

        with monkeypatch.context() as fault:
            fault.setattr(os, "replace", interrupted)
            with pytest.raises(OSError, match="injected pointer"):
                registry.consider_promotion(
                    "comparison-witness", second, second_evaluation, _policy(), suite_ref=suite
                )
        reopened_store = FileSystemCAS(tmp_path / "cas")
        pointer = ChampionRegistry(root=tmp_path / "registry", store=reopened_store).get(
            "comparison-witness"
        )
        if after_replace:
            assert pointer.candidate_ref == second
            assert pointer.evaluation_ref == second_evaluation
            assert pointer.metrics == {"score": 3.0}
        else:
            assert pointer_path.read_bytes() == before
            assert pointer.candidate_ref == first
        assert json.loads(reopened_store.get_bytes(pointer.evaluation_ref))["candidate_ref"] == (
            pointer.candidate_ref.model_dump(mode="json")
        )


def test_stale_metadata_attachment_cannot_overwrite_a_competing_champion(tmp_path):
    import pytest

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    first, second = [_candidate(store, suite, value) for value in (2, 3)]
    registry.consider_promotion(
        "comparison-witness",
        first,
        _evaluation(store, suite, first, 2, registry=registry),
        _policy(),
        suite_ref=suite,
    )
    stale = registry.get("comparison-witness")
    registry.consider_promotion(
        "comparison-witness",
        second,
        _evaluation(store, suite, second, 3, registry=registry),
        _policy(),
        suite_ref=suite,
    )
    with pytest.raises(ValueError, match="champion_pointer_transition_requires_comparison"):
        registry.write_pointer(
            "comparison-witness", stale.model_copy(update={"metadata": {"attachment": "stale"}})
        )
    assert registry.get("comparison-witness").candidate_ref == second


def test_posix_competing_processes_reread_canonical_pointer_and_fresh_reader(tmp_path):
    import subprocess
    import sys

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _suite(store)
    candidates = [_candidate(store, suite, value) for value in (1, 2, 3)]
    evaluations = [
        _evaluation(store, suite, candidate, value, registry=registry)
        for candidate, value in zip(candidates, (1, 2, 3), strict=True)
    ]
    assert registry.consider_promotion(
        "comparison-witness", candidates[0], evaluations[0], _policy(), suite_ref=suite
    ).promoted
    evaluations[1:] = [
        _evaluation(store, suite, candidates[index], value, registry=registry)
        for index, value in ((1, 2), (2, 3))
    ]
    worker = r"""
import json, sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import PromotionPolicy
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
payload = json.loads(sys.argv[1])
registry = ChampionRegistry(root=Path(payload["root"]), store=FileSystemCAS(Path(payload["cas"])))
if payload["gate"]:
    write = registry._write_pointer
    def gated(loop_id, pointer):
        print("LOCKED", flush=True)
        assert sys.stdin.readline().strip() == "release"
        return write(loop_id, pointer)
    registry._write_pointer = gated
else:
    print("START", flush=True)
decision = registry.consider_promotion(
    "comparison-witness", ArtifactRef.model_validate(payload["candidate"]),
    ArtifactRef.model_validate(payload["evaluation"]), PromotionPolicy.model_validate(payload["policy"]),
    suite_ref=ArtifactRef.model_validate(payload["suite"]),
)
print(decision.model_dump_json(), flush=True)
"""

    def process(index, *, gate):
        payload = {
            "root": str(tmp_path / "registry"),
            "cas": str(tmp_path / "cas"),
            "candidate": candidates[index].model_dump(mode="json"),
            "evaluation": evaluations[index].model_dump(mode="json"),
            "suite": suite.model_dump(mode="json"),
            "policy": _policy().model_dump(mode="json"),
            "gate": gate,
        }
        return subprocess.Popen(
            [sys.executable, "-c", worker, json.dumps(payload)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    with process(2, gate=True) as stronger:
        assert stronger.stdout.readline().strip() == "LOCKED"
        with process(1, gate=False) as weaker:
            assert weaker.stdout.readline().strip() == "START"
            strong_output, strong_error = stronger.communicate("release\n")
            weak_output, weak_error = weaker.communicate()
            assert stronger.returncode == 0, strong_error
            assert weaker.returncode == 0, weak_error
    strong_decision, weak_decision = json.loads(strong_output), json.loads(weak_output)
    assert strong_decision["promoted"]
    assert not weak_decision["promoted"]
    assert weak_decision["reason"] == "incumbent_changed_during_evaluation"
    assert weak_decision["previous_champion"]["candidate_ref"] == candidates[2].model_dump(
        mode="json"
    )
    fresh = ChampionRegistry(root=tmp_path / "registry", store=FileSystemCAS(tmp_path / "cas"))
    assert fresh.get("comparison-witness").candidate_ref == candidates[2]
