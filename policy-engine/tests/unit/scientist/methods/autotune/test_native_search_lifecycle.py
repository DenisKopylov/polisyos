"""Actual native service lifecycle and call-removal witnesses."""

from __future__ import annotations

from copy import deepcopy

import pytest

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
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver
from polisyos.scientist.methods.search.stopping import MaxIterations


class _Cost:
    name = "cost"

    def evaluate(self, results):
        return ObjectiveValue(
            name=self.name,
            raw_value=float(results["cost"]),
            direction=OptimizationDirection.MINIMIZE,
        )


class _Batch:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    def generate_batch(self, history, current_best, context, batch_size):
        self.calls += 1
        return self.batches.pop(0) if self.batches else []

    def generate(self, history, current_best, context):
        raise AssertionError("actual configured batch supplier is required")


def _driver(batches, *, max_iterations=2, stage_a=None, stage_b=None, warm=None):
    generator = _Batch(batches)
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(max_iterations),
            objective=CompositeObjective([_Cost()]),
            batch_size=2,
            initial_evaluations=warm or [],
        ),
        candidate_generator=generator,
        stage_a_evaluator=stage_a or (lambda candidate, context: (0.0, True)),
        stage_b_evaluator=stage_b
        or (
            lambda candidate, context: {
                "simulation_results": {"cost": candidate["cost"]},
                "feedback": {"verdict": "APPROVE"},
            }
        ),
    )
    return _NativeSearchServiceDriver(controller), generator


def test_native_route_forbids_private_full_evaluation_and_preserves_warm_sentinel_empty_stop(
    monkeypatch,
):
    batches = [
        [],
        [
            {
                "candidate_id": "sentinel",
                "cost": 0,
                "__sentinel__": {"sentinel_id": "native-witness"},
            },
            {"candidate_id": "rejected", "cost": 3},
        ],
        [{"candidate_id": "accepted", "cost": 1}],
    ]
    driver, generator = _driver(
        batches,
        stage_a=lambda candidate, context: (0.0, candidate["candidate_id"] != "rejected"),
        warm=[{"candidate": {"candidate_id": "warm", "cost": 10}, "objective_value": 10}],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("private full evaluation route called")

    monkeypatch.setattr(driver.controller, "_evaluate_candidate", forbidden)
    result = driver.run_search(initial_context={})
    assert generator.calls == 3
    assert [row.candidate["candidate_id"] for row in result.history] == [
        "warm",
        "rejected",
        "accepted",
    ]
    assert result.iterations_completed == 2
    assert result.stage_a_evaluations == 3
    assert result.stage_b_evaluations == 2
    assert result.telemetry["sentinel_evaluations"] == 1
    assert result.telemetry["training_evaluations"] == 1
    assert result.best_candidate["candidate_id"] == "accepted"
    assert result.telemetry["generation_transition"]["kind"] == "transient_empty"


def test_native_failure_leaves_only_pending_candidate_then_same_instance_tell_continues():
    calls = []
    failing = True

    def stage_b(candidate, context):
        nonlocal failing
        calls.append(candidate["candidate_id"])
        if candidate["candidate_id"] == "second" and failing:
            failing = False
            raise RuntimeError("actual Stage B failure")
        return {
            "simulation_results": {"cost": candidate["cost"]},
            "feedback": {"verdict": "APPROVE"},
        }

    driver, _ = _driver(
        [[{"candidate_id": "first", "cost": 2}, {"candidate_id": "second", "cost": 1}]],
        stage_b=stage_b,
    )
    with pytest.raises(RuntimeError, match="actual Stage B failure"):
        driver.run_search(initial_context={})
    assert [row.candidate["candidate_id"] for row in driver.controller._history] == ["first"]
    assert driver.controller._run_state.stage_b_evaluations == 1
    assert set(driver._pending_candidates) == {"second"}
    evaluation = driver.controller._evaluate_for_tell(
        driver._pending_candidates["second"], iteration=1, context={}
    )
    snapshot = driver.tell("second", evaluation)
    assert snapshot.history_length == 2
    assert snapshot.best_candidate["candidate_id"] == "second"
    assert calls == ["first", "second", "second"]
    assert driver.controller._run_state.stage_b_evaluations == 2
    assert not driver._pending_candidates
    with pytest.raises(ValueError, match="duplicate"):
        driver.tell("second", evaluation)
    assert len(driver.controller._history) == 2


def test_native_partial_batch_stop_retains_unaccepted_pending_without_double_count():
    driver, _ = _driver(
        [[{"candidate_id": "first", "cost": 2}, {"candidate_id": "second", "cost": 1}]],
        max_iterations=1,
    )
    result = driver.run_search(initial_context={})
    assert result.iterations_completed == 1
    assert len(result.history) == 1
    assert result.stage_b_evaluations == 1
    assert set(driver._pending_candidates) == {"second"}
    assert driver.controller._run_state.evaluation_iterations == 1


@pytest.mark.parametrize("removed_call", ["ask", "tell"])
def test_public_call_removal_trap_is_reached_before_history_acceptance(monkeypatch, removed_call):
    driver, _ = _driver([[{"candidate_id": "first", "cost": 2}]], max_iterations=1)

    def forbidden(*args, **kwargs):
        raise AssertionError(f"required public {removed_call} called")

    monkeypatch.setattr(driver, removed_call, forbidden)
    with pytest.raises(AssertionError, match=f"required public {removed_call}"):
        driver.run_search(initial_context={})
    assert not driver.controller._history
    assert driver.controller._run_state.evaluation_iterations == 0


class _Mutation(MutationArtifact):
    value: int


class _CandidateEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
        suite = load_model_artifact(context["store"], suite_ref, BenchmarkSuite)
        current = context["benchmark_comparison_incumbent"]
        self.calls.append(candidate.value)
        return BenchmarkEvaluation(
            loop_id=candidate.loop_id,
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics={"score": float(candidate.value)},
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=True,
            comparison_predecessor_candidate_ref=current.candidate_ref
            if current is not None
            else None,
            comparison_predecessor_evaluation_ref=current.evaluation_ref
            if current is not None
            else None,
        )


def _public_runner_inputs(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="native-lifecycle", data_basis="candidate_only")
    )
    evaluator = _CandidateEvaluator()
    spec = SearchLoopSpec(
        loop_id="native-lifecycle",
        mutation_codec=PydanticMutationCodec(_Mutation),
        candidate_generator=SequenceCandidateGenerator(
            [_Mutation(loop_id="native-lifecycle", value=value) for value in (1, 2)]
        ),
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="native-lifecycle", primary_metric="score", unit="points"
        ),
    )
    return store, registry, suite, evaluator, spec


def test_public_runner_two_runs_detach_history_and_preserve_actual_cas_evaluation(
    tmp_path, monkeypatch
):
    store, registry, suite, evaluator, spec = _public_runner_inputs(tmp_path)
    runner = SearchLoopRunner(store=store, registry=registry)
    calls = {"ask": 0, "tell": 0}
    original_ask, original_tell = _NativeSearchServiceDriver.ask, _NativeSearchServiceDriver.tell

    def ask(self, *args, **kwargs):
        calls["ask"] += 1
        return original_ask(self, *args, **kwargs)

    def tell(self, *args, **kwargs):
        calls["tell"] += 1
        return original_tell(self, *args, **kwargs)

    monkeypatch.setattr(_NativeSearchServiceDriver, "ask", ask)
    monkeypatch.setattr(_NativeSearchServiceDriver, "tell", tell)
    first = runner.run(spec, suite_ref=suite, max_iterations=1)
    first_history = deepcopy(first.history)
    first_evaluation = first.history[0].stage_b_result["simulation_results"]["evaluation_ref"]
    second = runner.run(spec, suite_ref=suite, max_iterations=1)
    assert first.search_id != second.search_id
    assert first.history == first_history
    assert [row.candidate["value"] for row in first.history] == [1]
    assert [row.candidate["value"] for row in second.history] == [2]
    assert first.best_candidate["value"] == 1
    assert second.best_candidate["value"] == 2
    assert first.iterations_completed == second.iterations_completed == 1
    assert first.stage_b_evaluations == second.stage_b_evaluations == 1
    assert calls == {"ask": 2, "tell": 2}
    assert evaluator.calls == [1, 2, 1]
    reopened_store = FileSystemCAS(tmp_path / "cas")
    old_evaluation = load_model_artifact(reopened_store, first_evaluation, BenchmarkEvaluation)
    assert old_evaluation.holdout_metrics == {"score": 1.0}
    current = ChampionRegistry(root=tmp_path / "registry", store=reopened_store).get(spec.loop_id)
    assert current.metrics == {"score": 2.0}


def test_public_runner_refuses_zero_iteration_budget_before_any_evaluation(tmp_path):
    store, registry, suite, evaluator, spec = _public_runner_inputs(tmp_path)
    with pytest.raises(ValueError, match="max_iter must be >= 1"):
        SearchLoopRunner(store=store, registry=registry).run(
            spec, suite_ref=suite, max_iterations=0
        )
    assert evaluator.calls == []
    assert registry.get(spec.loop_id) is None


def test_native_empty_supplier_exhausts_without_accepting_history():
    driver, generator = _driver([])
    result = driver.run_search(initial_context={})
    assert generator.calls == 3
    assert result.stopping_reason == "generation_exhausted"
    assert not result.history
    assert result.best_candidate is None
    assert result.iterations_completed == result.stage_b_evaluations == 0
    assert not driver._pending_candidates
