"""Actual native service lifecycle and call-removal witnesses."""

from __future__ import annotations

import pytest

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
