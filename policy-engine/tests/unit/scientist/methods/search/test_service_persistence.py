"""Real native service/CAS persistence, fresh resume and bounded rollback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.search.contracts import EvaluationBundle
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchStatus,
)
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.search.stopping import MaxIterations, MaxWallTime


class _Mutation(MutationArtifact):
    value: int


class _Evaluator:
    def __init__(self, *, fail_value=None):
        self.calls = []
        self.fail_value = fail_value

    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
        suite = load_model_artifact(context["store"], suite_ref, BenchmarkSuite)
        self.calls.append(candidate.value)
        if candidate.value == self.fail_value:
            raise RuntimeError("actual evaluator interruption")
        current = context["benchmark_comparison_incumbent"]
        return BenchmarkEvaluation(
            loop_id=candidate.loop_id,
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(candidate.value)},
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_predecessor_candidate_ref=current.candidate_ref if current else None,
            comparison_predecessor_evaluation_ref=current.evaluation_ref if current else None,
        )


def _runner(tmp_path, *, fail_value=None):
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "champions", store=store)
    suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="resume", data_basis="candidate_only")
    )
    evaluator = _Evaluator(fail_value=fail_value)
    spec = SearchLoopSpec(
        loop_id="resume",
        mutation_codec=PydanticMutationCodec(_Mutation),
        candidate_generator=SequenceCandidateGenerator(
            [_Mutation(loop_id="resume", value=value) for value in (1, 2, 3)]
        ),
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(loop_id="resume", primary_metric="score", unit="points"),
    )
    return SearchLoopRunner(store=store, registry=registry), store, registry, suite, evaluator, spec


def test_native_factory_failure_checkpoint_fresh_public_resume_retains_evaluated_subject(tmp_path):
    runner, store, registry, suite, evaluator, spec = _runner(tmp_path, fail_value=2)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    with pytest.raises(RuntimeError, match="actual evaluator interruption"):
        service.run_search(initial_context={})
    old_ref = service.checkpoint_ref
    assert isinstance(old_ref, ArtifactRef)
    assert service.controller._status is SearchStatus.FAILED
    assert [row.candidate["value"] for row in service.controller._history] == [1]
    assert set(service._pending_candidates) == {"candidate_1_0"}
    old_bytes = store.get_bytes(old_ref)
    fresh_runner, fresh_store, fresh_registry, fresh_suite, fresh_evaluator, fresh_spec = _runner(
        tmp_path
    )
    result = fresh_runner.resume(
        fresh_spec, suite_ref=suite, checkpoint_ref=old_ref, max_iterations=3
    )
    assert [row.candidate["value"] for row in result.history] == [1, 2, 3]
    assert result.iterations_completed == result.stage_b_evaluations == 3
    assert result.best_candidate["value"] == 3
    assert fresh_evaluator.calls == [2, 1, 3, 2]
    assert fresh_store.get_bytes(old_ref) == old_bytes
    assert fresh_registry.get("resume").metrics == {"score": 3.0}
    for row in result.history:
        evaluation = load_model_artifact(
            fresh_store,
            row.stage_b_result["simulation_results"]["evaluation_ref"],
            BenchmarkEvaluation,
        )
        assert evaluation.holdout_metrics == {"score": float(row.candidate["value"])}
    final_ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
    observer = fresh_runner.create_service(_runner(tmp_path)[-1], suite_ref=suite, max_iterations=3)
    observer.restore(final_ref)
    assert observer.controller._run_state.pareto_front == result.pareto_front
    assert [row.candidate for row in observer.controller._history] == [
        row.candidate for row in result.history
    ]
    assert observer.controller._run_state.stage_b_evaluations == 3


def test_pending_and_completed_ids_survive_fresh_reader_and_failed_tell_rolls_back(tmp_path):
    runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    proposal = service.ask(None, None, {})[0]
    pending_ref = service.checkpoint_ref
    observer = _runner(tmp_path)[0].create_service(
        _runner(tmp_path)[-1], suite_ref=suite, max_iterations=3
    )
    observer.restore(pending_ref)
    with pytest.raises(KeyError):
        observer.tell("unknown", EvaluationBundle(objective_value=1, is_promising=True))
    with pytest.raises(TypeError):
        observer.tell(
            proposal.candidate_id,
            EvaluationBundle(objective_value=1, is_promising=True, stage_b_result={"feedback": []}),
        )
    assert observer.controller._history == []
    assert set(observer._pending_candidates) == {proposal.candidate_id}
    evaluation = observer.controller._evaluate_for_tell(proposal.payload, iteration=0, context={})
    snapshot = observer.tell(proposal.candidate_id, evaluation)
    assert snapshot.history_length == 1
    fresh = _runner(tmp_path)[0].create_service(
        _runner(tmp_path)[-1], suite_ref=suite, max_iterations=3
    )
    fresh.restore(observer.checkpoint_ref)
    with pytest.raises(ValueError, match="duplicate"):
        fresh.tell(proposal.candidate_id, evaluation)
    assert [row.candidate["value"] for row in fresh.controller._history] == [1]
    assert fresh.ask(None, None, {})[0].payload["value"] == 2


def test_stopped_checkpoint_is_terminal_and_wrong_rule_or_suite_refuses_without_effect(tmp_path):
    runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
    result = runner.run(spec, suite_ref=suite, max_iterations=1)
    ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
    fresh_runner, _, _, _, fresh_evaluator, fresh_spec = _runner(tmp_path)
    stopped = fresh_runner.resume(fresh_spec, suite_ref=suite, checkpoint_ref=ref, max_iterations=1)
    assert stopped.search_id == result.search_id
    assert stopped.stopping_reason == result.stopping_reason
    assert fresh_evaluator.calls == []
    assert stopped.history == result.history
    with pytest.raises(ValueError, match="configuration_mismatch"):
        fresh_runner.resume(
            _runner(tmp_path)[-1], suite_ref=suite, checkpoint_ref=ref, max_iterations=2
        )
    wrong_suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="other", data_basis="candidate_only")
    )
    target = fresh_runner.create_service(
        _runner(tmp_path)[-1], suite_ref=wrong_suite, max_iterations=1
    )
    with pytest.raises(ValueError, match="configuration_mismatch"):
        target.restore(ref)
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []


class _Cost:
    name = "cost"
    direction = OptimizationDirection.MINIMIZE

    def evaluate(self, results):
        return ObjectiveValue(name="cost", raw_value=results["cost"], direction=self.direction)


def _direct(store, *, stopping=None, generator=None):
    controller = SearchController(
        SearchConfig(
            stopping=stopping or MaxIterations(2),
            objective=CompositeObjective([_Cost()]),
            enable_stage_a=False,
        ),
        generator or SequenceCandidateGenerator([{"cost": 2}, {"cost": 1}]),
        lambda candidate, context: (0.0, True),
        lambda candidate, context: {"simulation_results": {"cost": candidate["cost"]}},
    )
    return NativeSearchService(controller, store=store)


def test_wall_clock_origin_survives_pause_and_empty_generation_is_terminal(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    stopping = MaxWallTime(10)
    service = _direct(store, stopping=stopping)
    service.ask(None, None, {})
    stopping._start_time = datetime.now(UTC) - timedelta(seconds=20)
    ref = service.checkpoint()
    observer = _direct(FileSystemCAS(tmp_path / "cas"), stopping=MaxWallTime(10))
    observer.restore(ref)
    result = observer.resume_search()
    assert result.history == []
    assert result.iterations_completed == 0
    assert "Wall time" in result.stopping_reason
    assert observer.controller._config.stopping._start_time == stopping._start_time

    class Empty:
        def generate(self, *args):
            return []

        def generate_batch(self, *args, **kwargs):
            return []

        def get_state(self):
            return {"version": "empty.v1"}

        def set_state(self, value):
            assert value == {"version": "empty.v1"}

    empty = _direct(store, generator=Empty())
    empty.controller._config.batch_size = 2
    exhausted = empty.run_search(initial_context={})
    assert exhausted.stopping_reason == "generation_exhausted"
    assert exhausted.history == []
    reopened = _direct(store, generator=Empty())
    reopened.controller._config.batch_size = 2
    reopened.restore(empty.checkpoint_ref)
    assert reopened.resume_search().stopping_reason == "generation_exhausted"
    assert reopened.controller._run_state.generation_attempts == 3


@pytest.mark.parametrize(
    "mutation", ["version", "counter_bool", "history_count", "generator_cursor", "pending_order"]
)
def test_actual_cas_checkpoint_corruption_refuses_before_run_state_or_generator_effect(
    tmp_path, mutation
):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes

    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)
    source.ask(None, None, {})
    payload = from_canonical_bytes(store.get_bytes(source.checkpoint_ref))
    if mutation == "version":
        payload["schema_version"] = "search-service.v2"
    elif mutation == "counter_bool":
        payload["run_state"]["evaluation_iterations"] = True
    elif mutation == "history_count":
        payload["run_state"]["evaluation_iterations"] = 1
    elif mutation == "generator_cursor":
        payload["generator_state"]["index"] = 20
    else:
        payload["pending_candidate_ids"] = []
    bad = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="scientist.search.service_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="1.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    before = target.controller._generator.get_state()
    with pytest.raises(ValueError):
        target.restore(bad)
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target.controller._generator.get_state() == before
    assert target._pending_candidates == {}


def test_generator_without_checkpoint_contract_refuses_public_resume(tmp_path):
    class LegacyGenerator:
        def generate(self, *args):
            return {"cost": 1}

    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store, generator=LegacyGenerator())
    source.ask(None, None, {})
    target = _direct(store, generator=LegacyGenerator())
    with pytest.raises(ValueError, match="unsupported_generator_profile"):
        target.restore(source.checkpoint_ref)
    assert target.controller._run_state.search_id == ""


class _CheckpointBatch(SequenceCandidateGenerator):
    def generate_batch(self, history, current_best, context, batch_size):
        return [self.generate(history, current_best, context) for _ in range(batch_size)]


def test_actual_pending_batch_order_survives_canonical_json_key_sorting(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    candidates = [{"cost": 20 - index, "position": index} for index in range(13)]
    source = _direct(store, stopping=MaxIterations(13), generator=_CheckpointBatch(candidates))
    source.controller._config.batch_size = 13

    def interrupted(candidate, context):
        if candidate["position"] == 1:
            raise RuntimeError("batch interrupted")
        return {"simulation_results": {"cost": candidate["cost"]}}

    source.controller._stage_b = interrupted
    with pytest.raises(RuntimeError, match="batch interrupted"):
        source.run_search(initial_context={})
    assert [row.candidate["position"] for row in source.controller._history] == [0]
    target = _direct(
        FileSystemCAS(tmp_path / "cas"),
        stopping=MaxIterations(13),
        generator=_CheckpointBatch(candidates),
    )
    target.controller._config.batch_size = 13
    target.restore(source.checkpoint_ref)
    result = target.resume_search()
    assert [row.candidate["position"] for row in result.history] == list(range(13))
    assert result.iterations_completed == result.stage_b_evaluations == 13
    assert result.best_candidate["position"] == 12
    assert not target._pending_candidates


def test_initial_sentinel_failure_resume_preserves_initial_termination(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)

    def interrupted(candidate, context):
        raise RuntimeError("initial sentinel interrupted")

    source.controller._stage_b = interrupted
    seed = {"cost": 0, "__sentinel__": {"sentinel_id": "resume-initial"}}
    with pytest.raises(RuntimeError, match="initial sentinel interrupted"):
        source.run_search(initial_context={}, initial_candidate=seed)
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    target.restore(source.checkpoint_ref)
    result = target.resume_search()
    assert result.stopping_reason == "Initial sentinel evaluated"
    assert result.history == []
    assert result.iterations_completed == 0
    assert result.stage_b_evaluations == result.telemetry["sentinel_evaluations"] == 1
    assert target.controller._generator.get_state()["index"] == 0


def test_registered_checkpoint_facade_and_normal_contract_imports_do_not_load_runtime():
    import os
    import subprocess
    import sys

    script = """
import sys
import polisyos.scientist as public
class Trap:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"polisyos.scientist.methods.search.controller", "polisyos.scientist.methods.search.funnel.orchestrator"}:
            raise AssertionError("eager runtime import: " + fullname)
sys.meta_path.insert(0, Trap())
checkpoint = public.SearchServiceCheckpoint
from polisyos.scientist.methods.search.contracts import CandidateProposal, SearchService
from polisyos.scientist.methods import search
assert search.SearchServiceCheckpoint is checkpoint
assert search.CandidateProposal is CandidateProposal
assert "polisyos.scientist.methods.search.controller" not in sys.modules
assert "polisyos.scientist.methods.search.funnel.orchestrator" not in sys.modules
assert "torch" not in sys.modules
print("normal contract import retained canonical DTO identities without runtime imports")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=dict(os.environ)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "canonical DTO identities" in result.stdout
