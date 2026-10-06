"""Actual verified CAS producer, native runner and local champion consumers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    benchmark_comparison_basis,
    benchmark_evaluator_profile,
    load_benchmark_inputs,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
    seed_loop_baseline,
)


class _Mutation(MutationArtifact):
    value: int


class _SnapshotCAS(FileSystemCAS):
    """Observe the real public proof port and forbid legacy separately read views."""

    def __init__(self, path):
        super().__init__(path)
        self.reads = []

    def get_verified_snapshot(self, ref):
        result = super().get_verified_snapshot(ref)
        self.reads.append((ref, result.manifest_bytes))
        return result

    def get_bytes(self, *args, **kwargs):
        raise AssertionError("forbidden split byte read")

    def get_manifest(self, *args, **kwargs):
        raise AssertionError("forbidden split manifest read")

    def verify(self, *args, **kwargs):
        raise AssertionError("forbidden split verification")


class _Evaluator:
    def checkpoint_configuration(self):
        return {"fixture_formula": "candidate_value_times_immutable_holdout_weight.v1"}

    def evaluate(self, candidate_ref, suite_ref, context):
        store = context["store"]
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        candidate = load_model_artifact(store, candidate_ref, _Mutation)
        rows, split = load_benchmark_inputs(store, suite)
        current = context["benchmark_comparison_incumbent"]
        score = candidate.value * sum(
            row["weight"] for row in rows if str(row["id"]) in split.holdout_ids
        )
        return BenchmarkEvaluation(
            loop_id="verified",
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(score)},
            sample_counts={
                "selection": len(split.selection_ids),
                "holdout": len(split.holdout_ids),
            },
            guardrails={"finite": True},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_basis=benchmark_comparison_basis(
                store, suite_ref, context["policy"], benchmark_evaluator_profile(self)
            ),
            comparison_predecessor_candidate_ref=current.candidate_ref if current else None,
            comparison_predecessor_evaluation_ref=current.evaluation_ref if current else None,
        )


def _environment(tmp_path, *, values=(1, 2), store_type=_SnapshotCAS):
    store = store_type(tmp_path / "cas")
    registry = ChampionRegistry(tmp_path / "champions", store=store)
    dataset = tmp_path / "dataset.ndjson"
    dataset.write_text('{"id":"s","weight":10}\n{"id":"h","weight":1}\n')
    split_path = tmp_path / "split.json"
    split_path.write_text(
        BenchmarkSplitManifest(
            suite_id="verified-data", selection_ids=["s"], holdout_ids=["h"]
        ).model_dump_json()
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="verified-data", dataset_path=str(dataset), split_manifest_path=str(split_path)
        ),
    )
    policy = PromotionPolicy(
        loop_id="verified",
        primary_metric="score",
        unit="fixture_points",
        required_guardrails=["finite"],
    )
    spec = SearchLoopSpec(
        loop_id="verified",
        mutation_codec=PydanticMutationCodec(_Mutation),
        candidate_generator=SequenceCandidateGenerator(
            [_Mutation(loop_id="verified", value=value) for value in values]
        ),
        benchmark_evaluator=_Evaluator(),
        promotion_policy=policy,
    )
    return store, registry, suite_ref, policy, spec


def _produce_pair(store, registry, suite_ref, policy, value, *, current=None):
    """Execute actual evaluations and persist the pair before the pointer effect."""
    candidate = _Mutation(loop_id="verified", value=value)
    candidate_ref = persist_mutation_artifact(
        store, candidate, inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")]
    )
    evaluator = _Evaluator()
    current = registry.get("verified") if current is None else current
    context = {
        "store": store,
        "registry": registry,
        "policy": policy,
        "benchmark_comparison_incumbent": current,
    }
    evaluation = evaluator.evaluate(candidate_ref, suite_ref, context)
    if current is not None:
        incumbent = evaluator.evaluate(current.candidate_ref, suite_ref, context)
        incumbent_ref = persist_benchmark_evaluation(store, incumbent)
        evaluation = evaluation.model_copy(update={"incumbent_evaluation_ref": incumbent_ref})
    return candidate_ref, persist_benchmark_evaluation(store, evaluation)


def test_native_evaluator_registry_and_fresh_process_read_exact_profiles_and_immutable_inputs(
    tmp_path,
):
    store, registry, suite_ref, policy, spec = _environment(tmp_path)
    (tmp_path / "dataset.ndjson").write_text('{"id":"h","weight":999}\n')
    (tmp_path / "split.json").write_text("{}")
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite_ref, max_iterations=2
    )
    assert [row.stage_b_result["simulation_results"]["score"] for row in result.history] == [1, 2]
    pointer = ChampionRegistry(tmp_path / "champions", store=FileSystemCAS(tmp_path / "cas")).get(
        "verified"
    )
    assert pointer.metrics == {"score": 2}
    assert pointer.candidate_ref.manifest_profile_sha256 is not None
    assert pointer.evaluation_ref.manifest_profile_sha256 is not None
    for row in result.history:
        artifacts = row.stage_b_result["simulation_results"]
        for key in ("candidate_artifact_ref", "evaluation_artifact_ref", "suite_artifact_ref"):
            assert ArtifactRef.model_validate(artifacts[key]).manifest_profile_sha256 is not None
    script = """
import hashlib,json,sys
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation,load_model_artifact
root=Path(sys.argv[1]); store=FileSystemCAS(root/'cas')
pointer=ChampionRegistry(root/'champions',store=store).get('verified')
evaluation=load_model_artifact(store,pointer.evaluation_ref,BenchmarkEvaluation)
assert pointer.metrics == evaluation.holdout_metrics == {'score':2.0}
assert evaluation.comparison_basis.dataset_ref.manifest_profile_sha256 is not None
assert evaluation.comparison_basis.split_manifest_ref.manifest_profile_sha256 is not None
print(json.dumps({'fresh_process_pointer':pointer.model_dump(mode='json'),'model_origin':sys.modules[BenchmarkEvaluation.__module__].__file__}),flush=True)
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert child.returncode == 0, child.stdout + child.stderr
    print(child.stdout)
    assert store.reads


def test_actual_reused_content_keeps_old_qualified_view_and_refuses_wrong_candidate_profile(
    tmp_path,
):
    store, registry, suite_ref, policy, _ = _environment(tmp_path)
    candidate_ref, evaluation_ref = _produce_pair(store, registry, suite_ref, policy, 1)
    suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
    reused = persist_mutation_artifact(
        store,
        _Mutation(loop_id="verified", value=1),
        inputs=[
            input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
            input_ref_from_artifact_ref(suite.dataset_ref, role="actual_reuse_note"),
        ],
    )
    assert reused.artifact_id == candidate_ref.artifact_id
    assert reused.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
    wrong = registry.consider_promotion(
        "verified", reused, evaluation_ref, policy, suite_ref=suite_ref
    )
    assert wrong.promoted is False
    assert wrong.reason == "evaluation_candidate_mismatch"
    assert registry.get("verified") is None
    actual = registry.consider_promotion(
        "verified", candidate_ref, evaluation_ref, policy, suite_ref=suite_ref
    )
    assert actual.promoted is True
    fresh = ChampionRegistry(tmp_path / "champions", store=FileSystemCAS(tmp_path / "cas"))
    assert fresh.get("verified").candidate_ref == candidate_ref
    old_view = store.get_verified_snapshot(candidate_ref).manifest
    new_view = store.get_verified_snapshot(reused).manifest
    assert {item.role for item in old_view.inputs} == {"benchmark_suite"}
    assert {item.role for item in new_view.inputs} == {"benchmark_suite", "actual_reuse_note"}
    print(
        "actual_reused_views", candidate_ref.model_dump(mode="json"), reused.model_dump(mode="json")
    )


def test_native_seed_incumbent_is_actually_re_evaluated_on_active_immutable_suite(tmp_path):
    store, registry, suite_ref, policy, spec = _environment(tmp_path, values=(2,))
    initial = seed_loop_baseline(
        loop_id="verified",
        baseline=_Mutation(loop_id="verified", value=1),
        store=store,
        registry=registry,
    )
    assert initial.metrics == {}
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite_ref, max_iterations=1
    )
    decision = result.history[0].stage_b_result["feedback"]["promotion_decision"]
    assert decision["promoted"] is True
    fresh_store = FileSystemCAS(tmp_path / "cas")
    pointer = ChampionRegistry(tmp_path / "champions", store=fresh_store).get("verified")
    assert pointer.metrics == {"score": 2}
    evaluation = load_model_artifact(fresh_store, pointer.evaluation_ref, BenchmarkEvaluation)
    incumbent = load_model_artifact(
        fresh_store, evaluation.incumbent_evaluation_ref, BenchmarkEvaluation
    )
    assert incumbent.holdout_metrics == {"score": 1}
    assert incumbent.comparison_basis == evaluation.comparison_basis
    assert incumbent.candidate_ref == initial.candidate_ref


def test_competing_native_writer_refuses_actual_stale_pair_after_lock_held_reread(tmp_path):
    store, registry, suite_ref, policy, spec = _environment(tmp_path, values=(1,))
    SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite_ref, max_iterations=1
    )
    entered, release = Event(), Event()

    class BarrierEvaluator(_Evaluator):
        def evaluate(self, candidate_ref, suite_ref, context):
            candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
            if candidate.value == 3:
                entered.set()
                release.wait()
            return super().evaluate(candidate_ref, suite_ref, context)

    slow = replace(
        spec,
        candidate_generator=SequenceCandidateGenerator([_Mutation(loop_id="verified", value=3)]),
        benchmark_evaluator=BarrierEvaluator(),
    )
    fast = replace(
        spec,
        candidate_generator=SequenceCandidateGenerator([_Mutation(loop_id="verified", value=2)]),
    )
    with ThreadPoolExecutor() as workers:
        pending = workers.submit(
            SearchLoopRunner(store=store, registry=registry).run,
            slow,
            suite_ref=suite_ref,
            max_iterations=1,
        )
        entered.wait()
        try:
            other = ChampionRegistry(tmp_path / "champions", store=FileSystemCAS(tmp_path / "cas"))
            SearchLoopRunner(store=other._store, registry=other).run(
                fast, suite_ref=suite_ref, max_iterations=1
            )
        finally:
            release.set()
        slow_result = pending.result()
    decision = slow_result.history[0].stage_b_result["feedback"]["promotion_decision"]
    assert decision["promoted"] is False
    assert decision["reason"] == "incumbent_changed_during_evaluation"
    pointer = ChampionRegistry(tmp_path / "champions", store=FileSystemCAS(tmp_path / "cas")).get(
        "verified"
    )
    assert pointer.metrics == {"score": 2}


@pytest.mark.parametrize("boundary,expected_score", [("before", 1), ("after", 2)])
def test_actual_process_exit_around_atomic_pointer_replace_has_complete_fresh_view(
    tmp_path, boundary, expected_score
):
    store, registry, suite_ref, policy, _ = _environment(tmp_path)
    first, first_eval = _produce_pair(store, registry, suite_ref, policy, 1)
    assert registry.consider_promotion(
        "verified", first, first_eval, policy, suite_ref=suite_ref
    ).promoted
    second, second_eval = _produce_pair(store, registry, suite_ref, policy, 2)
    packet = {
        "candidate": second.model_dump(mode="json"),
        "evaluation": second_eval.model_dump(mode="json"),
        "suite": suite_ref.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
    }
    packet_path = tmp_path / "child-input.json"
    packet_path.write_text(json.dumps(packet))
    script = """
import json,os,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import PromotionPolicy
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
root=Path(sys.argv[1]); packet=json.loads(Path(sys.argv[2]).read_text()); boundary=sys.argv[3]
registry=ChampionRegistry(root/'champions',store=FileSystemCAS(root/'cas'))
original=os.replace
def replace(source,target,*args,**kwargs):
    if Path(target) == registry._pointer_path('verified'):
        print(json.dumps({'actual_pointer_boundary':boundary,'pointer':str(target)}),flush=True)
        if boundary == 'before': os._exit(72)
        original(source,target,*args,**kwargs)
        os._exit(73)
    return original(source,target,*args,**kwargs)
os.replace=replace
registry.consider_promotion('verified',ArtifactRef.model_validate(packet['candidate']),ArtifactRef.model_validate(packet['evaluation']),PromotionPolicy.model_validate(packet['policy']),suite_ref=ArtifactRef.model_validate(packet['suite']))
raise AssertionError('actual pointer publication boundary was not exercised')
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(packet_path), boundary],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert child.returncode == (72 if boundary == "before" else 73), child.stdout + child.stderr
    assert "actual_pointer_boundary" in child.stdout
    print(child.stdout)
    fresh_store = FileSystemCAS(tmp_path / "cas")
    pointer = ChampionRegistry(tmp_path / "champions", store=fresh_store).get("verified")
    assert pointer.metrics == {"score": expected_score}
    evaluation = load_model_artifact(fresh_store, pointer.evaluation_ref, BenchmarkEvaluation)
    assert evaluation.candidate_ref == pointer.candidate_ref
    assert evaluation.holdout_metrics == pointer.metrics
