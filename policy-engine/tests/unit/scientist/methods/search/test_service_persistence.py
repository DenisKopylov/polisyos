"""Real native service/CAS persistence, fresh resume and bounded rollback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
    BudgetDeficitObjective,
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.search.stopping import (
    CostBudgetStopping,
    ImprovementPlateau,
    MaxIterations,
    MaxWallTime,
)


class _Mutation(MutationArtifact):
    value: int


def _identity_score(value):
    return value


def _shifted_score(value):
    return value + 10


class _Evaluator:
    def __init__(self, *, fail_value=None, failure_marker=None, scale=1):
        self.calls = []
        self.fail_value = fail_value
        self.failure_marker = failure_marker
        self.scale = scale

    def checkpoint_configuration(self):
        return {
            "scale": self.scale,
            "fail_once_value": self.fail_value,
            "failure_marker": str(self.failure_marker),
        }

    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
        suite = load_model_artifact(context["store"], suite_ref, BenchmarkSuite)
        self.calls.append(candidate.value)
        if candidate.value == self.fail_value and not self.failure_marker.exists():
            self.failure_marker.write_text("actual evaluator failure observed", encoding="utf-8")
            raise RuntimeError("actual evaluator interruption")
        current = context["benchmark_comparison_incumbent"]
        return BenchmarkEvaluation(
            loop_id=candidate.loop_id,
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics={
                "score": float(
                    context.get("score_callback", _identity_score)(candidate.value) * self.scale
                    + context.get("score_offset", 0)
                )
            },
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
    evaluator = _Evaluator(
        fail_value=fail_value, failure_marker=tmp_path / "evaluation-failure.txt"
    )
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
        tmp_path, fail_value=2
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
    observer = fresh_runner.create_service(
        _runner(tmp_path, fail_value=2)[-1], suite_ref=suite, max_iterations=3
    )
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


def _checkpoint_stage_b(candidate, context):
    if context.get("interrupt_all"):
        raise RuntimeError("initial sentinel interrupted")
    if candidate.get("position") == context.get("interrupt_position", -1):
        raise RuntimeError("batch interrupted")
    return {"simulation_results": {"budget_deficit": candidate["cost"]}}


def _direct(store, *, stopping=None, generator=None):
    controller = SearchController(
        SearchConfig(
            stopping=stopping or MaxIterations(2),
            objective=CompositeObjective([BudgetDeficitObjective()]),
            enable_stage_a=False,
        ),
        generator or SequenceCandidateGenerator([{"cost": 2}, {"cost": 1}]),
        lambda candidate, context: (0.0, True),
        _checkpoint_stage_b,
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

        def validate_checkpoint_history(self, history, value):
            # The actual producer always returns an empty batch and consumes no
            # history. Its entire saved state is the fixed profile, not a flag.
            if value != {"version": "empty.v1"} or history:
                raise ValueError("empty checkpoint profile or history changed")

        def set_state(self, value):
            self.validate_checkpoint_history([], value)

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
    "mutation",
    [
        "version",
        "counter_bool",
        "history_count",
        "generator_cursor",
        "pending_order",
        "cost_huge",
        "cost_origin_claim",
        "hard_limit_bool",
        "stage_a_integer",
        "pending_carrier",
        "initial_carrier",
    ],
)
def test_actual_cas_checkpoint_corruption_refuses_before_run_state_or_generator_effect(
    tmp_path, mutation
):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes

    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)
    if mutation == "hard_limit_bool":
        source.controller._config.max_iterations_hard_limit = 1
    source.ask(None, None, {})
    payload = from_canonical_bytes(store.get_bytes(source.checkpoint_ref))
    if mutation == "version":
        payload["schema_version"] = "search-service.v99"
    elif mutation == "counter_bool":
        payload["run_state"]["evaluation_iterations"] = True
    elif mutation == "history_count":
        payload["run_state"]["evaluation_iterations"] = 1
    elif mutation == "generator_cursor":
        payload["generator_state"]["index"] = 20
    elif mutation == "cost_huge":
        payload["run_state"]["budget_snapshot"] = {"cumulative_cost_usd": 10**400}
    elif mutation == "cost_origin_claim":
        payload["run_state"]["budget_evidence"] = {
            "source": "configured_owner_recorded_state",
            "receipt_revision_available": False,
            "provider_cost_origin_available": True,
            "recorded_by_provider": {},
            "unavailable_reason": None,
        }
    elif mutation == "hard_limit_bool":
        payload["configuration"]["hard_limit"] = True
    elif mutation == "stage_a_integer":
        payload["configuration"]["stage_a_enabled"] = 0
    elif mutation == "pending_carrier":
        payload["pending_candidates"]["candidate_0_0"]["cost"] = {
            "__search_nonfinite_float__": "invalid"
        }
    elif mutation == "initial_carrier":
        payload["initial_candidate"] = {"cost": {"__search_nonfinite_float__": "invalid"}}
    else:
        payload["pending_candidate_ids"] = []
    bad = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="scientist.search.service_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256

    bad = bad.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(bad).manifest
            )
        }
    )
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    if mutation == "hard_limit_bool":
        target.controller._config.max_iterations_hard_limit = 1
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

    with pytest.raises(RuntimeError, match="batch interrupted"):
        source.run_search(initial_context={"interrupt_position": 1})
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

    seed = {"cost": 0, "__sentinel__": {"sentinel_id": "resume-initial"}}
    with pytest.raises(RuntimeError, match="initial sentinel interrupted"):
        source.run_search(initial_context={"interrupt_all": True}, initial_candidate=seed)
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


class _FailingCAS(FileSystemCAS):
    fail_write = False
    fail_readback = False

    def put_json(self, *args, **kwargs):
        if self.fail_write:
            raise OSError("actual checkpoint publication failed")
        return super().put_json(*args, **kwargs)

    def get_verified_snapshot(self, ref):
        if self.fail_readback:
            raise OSError("actual checkpoint readback failed")
        return super().get_verified_snapshot(ref)


@pytest.mark.parametrize("failure", ["fail_write", "fail_readback"])
def test_failed_ask_publication_restores_cursor_ids_and_last_acknowledged_fresh_view(
    tmp_path, failure
):
    store = _FailingCAS(tmp_path / "cas")
    service = _direct(store)
    first = service.ask(None, None, {})[0]
    service.tell(
        first.candidate_id,
        service.controller._evaluate_for_tell(first.payload, iteration=0, context={}),
    )
    acknowledged = service.checkpoint_ref
    before = service.controller._generator.get_state()
    setattr(store, failure, True)
    with pytest.raises(OSError, match="actual checkpoint"):
        service.ask(None, None, {})
    assert service.checkpoint_ref == acknowledged
    assert service.controller._generator.get_state() == before
    assert service._ask_iteration == 1
    assert service._pending_candidates == {}
    fresh = _direct(FileSystemCAS(tmp_path / "cas"))
    fresh.restore(acknowledged)
    assert fresh.controller._history == service.controller._history
    assert fresh._ask_iteration == service._ask_iteration
    assert fresh.controller._generator.get_state() == service.controller._generator.get_state()
    setattr(store, failure, False)
    live_next = service.ask(None, None, {})[0]
    fresh_next = fresh.ask(None, None, {})[0]
    assert live_next == fresh_next
    assert live_next.candidate_id == "candidate_1_0"
    assert live_next.payload == {"cost": 1}


@pytest.mark.parametrize("failure", ["fail_write", "fail_readback"])
def test_failed_tell_publication_restores_local_state_and_prior_durable_pending_view(
    tmp_path, failure
):
    store = _FailingCAS(tmp_path / "cas")
    service = _direct(store)
    proposal = service.ask(None, None, {})[0]
    pending_ref = service.checkpoint_ref
    evaluation = service.controller._evaluate_for_tell(proposal.payload, iteration=0, context={})
    setattr(store, failure, True)
    with pytest.raises(OSError, match="actual checkpoint"):
        service.tell(proposal.candidate_id, evaluation)
    assert service.checkpoint_ref == pending_ref
    assert service.controller._history == []
    assert service.controller._run_state.evaluation_iterations == 0
    assert service.controller._run_state.stage_b_evaluations == 0
    assert service._completed_candidate_ids == set()
    assert service._pending_candidates == {proposal.candidate_id: proposal.payload}
    observer = _direct(FileSystemCAS(tmp_path / "cas"))
    observer.restore(pending_ref)
    assert observer._pending_candidates == service._pending_candidates
    assert observer.controller._history == []
    setattr(store, failure, False)
    assert service.tell(proposal.candidate_id, evaluation).history_length == 1
    fresh = _direct(FileSystemCAS(tmp_path / "cas"))
    fresh.restore(service.checkpoint_ref)
    assert fresh.controller._run_state.evaluation_iterations == 1
    assert fresh.controller._run_state.stage_b_evaluations == 1
    assert fresh._completed_candidate_ids == {proposal.candidate_id}
    assert fresh._pending_candidates == {}
    with pytest.raises(ValueError, match="duplicate"):
        fresh.tell(proposal.candidate_id, evaluation)


def test_custom_parameterized_objective_checkpoint_refuses_resume_instead_of_build_identity(
    tmp_path,
):
    class Parameterized(BudgetDeficitObjective):
        def __init__(self, factor):
            super().__init__()
            self.factor = factor

        def evaluate(self, results):
            return ObjectiveValue(
                name=self.name,
                raw_value=results["budget_deficit"] * self.factor,
                direction=OptimizationDirection.MINIMIZE,
            )

    source = _direct(FileSystemCAS(tmp_path / "cas"))
    source.controller._config.objective = CompositeObjective([Parameterized(1)])
    source.ask(None, None, {})
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    target.controller._config.objective = CompositeObjective([Parameterized(2)])
    with pytest.raises(ValueError, match="unsupported_objective_or_evaluator_profile"):
        target.restore(source.checkpoint_ref)
    assert target.controller._run_state.search_id == ""
    assert target.controller._generator.get_state()["index"] == 0


def _default_stage_b(candidate, context, coefficient=1):
    return {"simulation_results": {"budget_deficit": candidate["cost"] * coefficient}}


def test_actual_stateless_evaluator_defaults_and_objective_parameters_bind_resume(tmp_path):
    source = _direct(FileSystemCAS(tmp_path / "cas"))
    source.controller._stage_b = _default_stage_b
    source.ask(None, None, {})
    original = _default_stage_b.__defaults__
    try:
        _default_stage_b.__defaults__ = (2,)
        target = _direct(FileSystemCAS(tmp_path / "cas"))
        target.controller._stage_b = _default_stage_b
        with pytest.raises(ValueError, match="configuration_mismatch"):
            target.restore(source.checkpoint_ref)
        assert target.controller._run_state.search_id == ""
    finally:
        _default_stage_b.__defaults__ = original
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    target.controller._stage_b = _default_stage_b
    target.controller._config.objective = CompositeObjective([BudgetDeficitObjective(weight=2)])
    with pytest.raises(ValueError, match="configuration_mismatch"):
        target.restore(source.checkpoint_ref)
    assert target.controller._generator.get_state()["index"] == 0


@pytest.mark.parametrize("changed", ["warm_corpus", "policy_stack", "external_arbiter"])
def test_actual_warm_and_policy_configuration_changes_refuse_resume(tmp_path, changed):
    from polisyos.scientist.policy_design.objectives import ObjectiveStack

    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)
    source.controller._config.initial_evaluations = [
        {"candidate": {"cost": 3}, "objective_value": 3.0, "is_promising": True}
    ]
    source.controller._config.policy_objective_stack = ObjectiveStack()
    source.ask(None, None, {})
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    target.controller._config.initial_evaluations = list(
        source.controller._config.initial_evaluations
    )
    target.controller._config.policy_objective_stack = ObjectiveStack()
    if changed == "warm_corpus":
        target.controller._config.initial_evaluations = [
            {"candidate": {"cost": 4}, "objective_value": 4.0, "is_promising": True}
        ]
    elif changed == "policy_stack":
        target.controller._config.policy_objective_stack = ObjectiveStack(near_binding_ratio=0.8)
    else:
        target.controller._config.resource_arbiter = object()
    with pytest.raises(
        ValueError, match="configuration_mismatch|unsupported_objective_or_evaluator_profile"
    ):
        target.restore(source.checkpoint_ref)
    assert target.controller._history == []
    assert target.controller._generator.get_state()["index"] == 0


def test_same_actual_warm_corpus_fresh_reader_preserves_training_and_current_history(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)
    warm = {"candidate": {"cost": 3}, "objective_value": 3.0, "is_promising": True}
    source.controller._config.initial_evaluations = [warm]
    result = source.run_search(initial_context={})
    assert [row.iteration for row in result.history] == [-1, 0, 1]
    assert [row.candidate["cost"] for row in result.history] == [3, 2, 1]
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    target.controller._config.initial_evaluations = [dict(warm)]
    target.restore(source.checkpoint_ref)
    reopened = target.resume_search()
    assert reopened.history == result.history
    assert reopened.best_candidate == {"cost": 1}
    assert target.controller._run_state.training_evaluations == 1
    assert target.controller._run_state.evaluation_iterations == 2


def test_fresh_public_service_retains_typed_policy_history_frontier_and_next_tell(tmp_path):
    from polisyos.scientist.policy_design.objectives import (
        ObjectiveChannelValue,
        ObjectiveDirection,
        ObjectiveKind,
        PolicyEvaluationVector,
    )

    def evaluation(cost):
        return EvaluationBundle(
            objective_value=float(cost),
            is_promising=True,
            policy_evaluation=PolicyEvaluationVector(
                primary={
                    "cost": ObjectiveChannelValue(
                        name="cost",
                        kind=ObjectiveKind.PRIMARY,
                        value=float(cost),
                        direction=ObjectiveDirection.MINIMIZE,
                    )
                }
            ),
        )

    source = _direct(FileSystemCAS(tmp_path / "cas"))
    first = source.ask(None, None, {})[0]
    accepted = source.tell(first.candidate_id, evaluation(first.payload["cost"]))
    assert accepted.frontier_delta
    assert isinstance(source.controller._history[0].policy_evaluation, PolicyEvaluationVector)
    fresh = _direct(FileSystemCAS(tmp_path / "cas"))
    fresh.restore(source.checkpoint_ref)
    assert fresh.controller._history == source.controller._history
    assert fresh.controller._run_state.pareto_points == source.controller._run_state.pareto_points
    assert (
        fresh.controller._run_state.pareto_projection
        == source.controller._run_state.pareto_projection
    )
    second = fresh.ask(None, None, {})[0]
    final = fresh.tell(second.candidate_id, evaluation(second.payload["cost"]))
    assert final.best_candidate == {"cost": 1}
    assert final.best_objective == 1
    observer = _direct(FileSystemCAS(tmp_path / "cas"))
    observer.restore(fresh.checkpoint_ref)
    assert observer.controller._history == fresh.controller._history
    assert observer.controller._run_state.pareto_points == fresh.controller._run_state.pareto_points
    assert all(
        isinstance(row.policy_evaluation, PolicyEvaluationVector)
        for row in observer.controller._history
    )


def test_checkpoint_requires_exact_public_snapshot_profile_on_resume(tmp_path):
    source = _direct(FileSystemCAS(tmp_path / "cas"))
    source.ask(None, None, {})
    assert source.checkpoint_ref.manifest_profile_sha256 is not None
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="exact_manifest_profile_required"):
        target.restore(source.checkpoint_ref.model_copy(update={"manifest_profile_sha256": None}))
    assert target.controller._run_state.search_id == ""


def test_actual_checkpoint_consumer_uses_one_public_verified_snapshot_without_split_reads(tmp_path):
    class SingleSnapshotCAS(FileSystemCAS):
        snapshot_reads = 0

        def get_verified_snapshot(self, ref):
            self.snapshot_reads += 1
            return super().get_verified_snapshot(ref)

        def get_manifest(self, *args, **kwargs):
            raise AssertionError("forbidden separately observed manifest")

        def get_bytes(self, *args, **kwargs):
            raise AssertionError("forbidden separately observed bytes")

        def verify(self, *args, **kwargs):
            raise AssertionError("forbidden separately observed verification")

    store = SingleSnapshotCAS(tmp_path / "cas")
    source = _direct(store)
    proposal = source.ask(None, None, {})[0]
    assert store.snapshot_reads == 1
    target_store = SingleSnapshotCAS(tmp_path / "cas")
    target = _direct(target_store)
    target.restore(source.checkpoint_ref)
    assert target_store.snapshot_reads == 1
    assert target._pending_candidates == {proposal.candidate_id: proposal.payload}
    print("public_snapshot_checkpoint", source.checkpoint_ref.model_dump(mode="json"))


@pytest.mark.parametrize(
    "maximum", [True, 10**400, float("nan"), float("inf"), -1, 0, Decimal("1e-1000")]
)
def test_cost_budget_constructor_refuses_invalid_present_scalar(maximum):
    with pytest.raises(ValueError, match="finite positive"):
        CostBudgetStopping(maximum)


@pytest.mark.parametrize("coefficient", ["min_improvement", "absolute_tolerance"])
@pytest.mark.parametrize(
    "invalid", [True, 10**400, float("nan"), float("inf"), -1, Decimal("1e-1000")]
)
def test_plateau_coefficients_refuse_invalid_present_scale_without_overflow(coefficient, invalid):
    with pytest.raises(ValueError, match="finite nonnegative"):
        ImprovementPlateau(objective_unit="points", **{coefficient: invalid})


@pytest.mark.parametrize("invalid", [10**400, Decimal("1e-1000"), True])
def test_plateau_observation_unavailable_preserves_declared_formula_and_genuine_zero(invalid):
    criterion = ImprovementPlateau(patience=2, objective_unit="points")
    unavailable = criterion.check(
        [{"objective_value": 0}, {"objective_value": 0}, {"objective_value": invalid}], {}
    )
    assert unavailable.should_stop is False
    assert unavailable.details["adequacy_status"] == "not_established"
    zero = criterion.check([{"objective_value": Decimal(0)}] * 3, {})
    assert zero.should_stop is True
    assert zero.details["tolerance"] == 0.01
    assert zero.details["relative_tolerance"] == 0.01
    assert zero.details["objective_unit"] == "points"


@pytest.mark.parametrize(
    "cost", [True, 10**400, float("nan"), float("inf"), -1, None, Decimal("1e-1000")]
)
def test_cost_observation_and_actual_controller_context_are_unavailable_without_crash(
    tmp_path, cost
):
    stopping = CostBudgetStopping(5)
    check = stopping.check([], {"cumulative_cost_usd": cost})
    assert check.should_stop
    assert check.details["budget_available"] is False
    service = _direct(FileSystemCAS(tmp_path / "cas"), stopping=stopping)
    result = service.run_search(initial_context={"cumulative_cost_usd": cost})
    assert result.history == []
    assert result.stage_b_evaluations == 0
    assert result.telemetry["budget_available"] is False
    assert result.telemetry["budget_spent"] is None
    assert (
        result.telemetry["budget_evidence"]["unavailable_reason"]
        == "context_cost_missing_or_invalid"
    )


def test_recorded_cost_public_owner_port_reopens_without_receipt_or_provider_origin_authority(
    tmp_path,
):
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    ledger_path = tmp_path / "budget.json"
    owner = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    owner.record_spend_safe("run", Decimal(2), provider="test-provider")
    source = _direct(FileSystemCAS(tmp_path / "cas"), stopping=CostBudgetStopping(5))
    source.controller._config.budget_middleware = owner
    source.controller._refresh_budget_snapshot({"cumulative_cost_usd": 0})
    state = source.controller._stopping_state()
    assert state["cumulative_cost_usd"] == 2
    evidence = state["budget_evidence"]
    assert evidence["source"] == "configured_owner_recorded_state"
    assert evidence["recorded_by_provider"] == {"test-provider": 2}
    assert evidence["provider_cost_origin_available"] is False
    assert evidence["receipt_revision_available"] is False
    assert source.controller._run_state.budget_ledger_revision is None
    fresh_writer = FileBudgetLedger(ledger_path)
    fresh_writer.record_spend("run", Decimal(3), provider="test-provider")
    result = source.run_search(initial_context={"cumulative_cost_usd": 0})
    assert result.history == []
    assert result.telemetry["budget_spent"] == 5
    assert result.telemetry["budget_evidence"]["recorded_by_provider"] == {"test-provider": 5}
    target = _direct(FileSystemCAS(tmp_path / "cas"), stopping=CostBudgetStopping(5))
    target.controller._config.budget_middleware = BudgetMiddleware(
        BudgetState(), ledger=FileBudgetLedger(ledger_path)
    )
    target.restore(source.checkpoint_ref)
    reopened = target.resume_search()
    assert reopened.telemetry["budget_evidence"] == result.telemetry["budget_evidence"]
    assert reopened.telemetry["budget_ledger_id"] == result.telemetry["budget_ledger_id"]
    assert reopened.telemetry["budget_ledger_revision"] is None
    print("recorded_cost_reopen", result.telemetry["budget_evidence"])


def test_recorded_memory_zero_is_available_without_durable_identity_or_measured_zero(tmp_path):
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    source = _direct(FileSystemCAS(tmp_path / "cas"), stopping=CostBudgetStopping(5))
    source.controller._config.budget_middleware = BudgetMiddleware(BudgetState())
    source.controller._refresh_budget_snapshot({})
    check = source.controller._config.stopping.check([], source.controller._stopping_state())
    assert check.should_stop is False
    assert check.details["cost"] == 0
    assert check.details["budget_available"] is True
    assert check.details["budget_evidence"]["recorded_spend_key_present"] is False
    assert check.details["budget_evidence"]["provider_cost_origin_available"] is False
    assert source.controller._run_state.budget_ledger_id is None


def test_original_v1_checkpoint_manifest_refuses_explicitly_before_effect(tmp_path):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes

    store = FileSystemCAS(tmp_path / "cas")
    source = _direct(store)
    source.ask(None, None, {})
    payload = from_canonical_bytes(store.get_verified_snapshot(source.checkpoint_ref).data)
    payload["schema_version"] = "search-service.v1"
    payload["run_state"].pop("budget_evidence")
    old = store.put_json(
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
    old = old.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(old).manifest
            )
        }
    )
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="checkpoint_manifest_mismatch"):
        target.restore(old)
    assert target.controller._run_state.search_id == ""
    assert target.controller._generator.get_state()["index"] == 0


@pytest.mark.parametrize("change", ["evaluator", "context", "callback", "codec", "opaque"])
def test_native_actual_configuration_changes_refuse_before_state_or_evaluation_effect(
    tmp_path, change
):
    runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
    context = {"score_offset": 1, "score_callback": _identity_score}
    result = runner.run(spec, suite_ref=suite, max_iterations=1, context=context)
    assert registry.get("resume").metrics == {"score": 2}
    fresh_runner, _, _, _, fresh_evaluator, fresh_spec = _runner(tmp_path)
    active_context = dict(context)
    if change == "evaluator":
        fresh_evaluator.scale = 2
    elif change == "context":
        active_context["score_offset"] = 2
    elif change == "callback":
        active_context["score_callback"] = _shifted_score
    elif change == "codec":
        from dataclasses import replace

        class DifferentMutation(_Mutation):
            pass

        fresh_spec = replace(fresh_spec, mutation_codec=PydanticMutationCodec(DifferentMutation))
    else:
        active_context["opaque_runtime_configuration"] = object()
    target = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=1)
    with pytest.raises(
        ValueError, match="configuration_mismatch|unsupported_objective_or_evaluator_profile"
    ):
        target.restore(
            ArtifactRef.model_validate(result.telemetry["checkpoint_ref"]), context=active_context
        )
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target.controller._generator.get_state()["index"] == 0
    assert fresh_evaluator.calls == []


def test_native_same_content_configuration_and_context_fresh_resume(tmp_path):
    runner, _, registry, suite, evaluator, spec = _runner(tmp_path)
    context = {"score_offset": 1, "score_callback": _identity_score}
    result = runner.run(spec, suite_ref=suite, max_iterations=1, context=context)
    fresh_runner, _, _, _, fresh_evaluator, fresh_spec = _runner(tmp_path)
    reopened = fresh_runner.resume(
        fresh_spec,
        suite_ref=suite,
        checkpoint_ref=ArtifactRef.model_validate(result.telemetry["checkpoint_ref"]),
        context=context,
        max_iterations=1,
    )
    assert reopened.history == result.history
    assert fresh_evaluator.calls == []
    assert reopened.best_candidate == result.best_candidate
    assert registry.get("resume").metrics == {"score": 2}


@pytest.mark.parametrize("representation", ["wire", "canonical_tag"])
def test_decimal_recorded_owner_underflow_is_unavailable_and_wire_underflow_refuses(
    tmp_path, representation
):
    import json

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon.canon_json import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    store = FileSystemCAS(tmp_path / "cas")
    service = _direct(store, stopping=CostBudgetStopping(5))
    service.controller._config.budget_middleware = BudgetMiddleware(
        BudgetState(spent={"run": Decimal("1e-1000")})
    )
    result = service.run_search(initial_context={})
    assert result.history == []
    assert result.telemetry["budget_spent"] is None
    assert result.telemetry["budget_available"] is False
    assert result.telemetry["budget_evidence"]["unavailable_reason"] == "recorded_cost_invalid"
    source = _direct(store)
    source.ask(None, None, {})
    payload = from_canonical_bytes(store.get_verified_snapshot(source.checkpoint_ref).data)
    if representation == "wire":
        assert payload["run_state"]["budget_spent"] is None
        wire = json.dumps(payload, sort_keys=True)
        assert wire.count('"budget_spent": null') == 1
        raw = wire.replace('"budget_spent": null', '"budget_spent": 1e-1000', 1).encode()
        assert b'"budget_spent": 1e-1000' in raw
    else:
        payload["run_state"]["budget_spent"] = {"_type": "float", "repr": "1e-1000"}
        raw = json.dumps(payload, sort_keys=True).encode()
    bad = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="scientist.search.service_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
            ),
        ),
    )
    bad = bad.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(bad).manifest
            )
        }
    )
    target = _direct(FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="numeric_underflow"):
        target.restore(bad)
    assert target.controller._run_state.search_id == ""
    assert target.controller._generator.get_state()["index"] == 0
