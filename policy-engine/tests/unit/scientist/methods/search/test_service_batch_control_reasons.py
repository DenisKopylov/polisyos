"""Actual public empty-batch reasons and acknowledged partial-state controls."""

from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError
from copy import deepcopy

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist import NativeSearchService
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    CostBudgetStopping,
    MaxIterations,
)


def _stage_a(candidate, context):
    return 0.0, True


def _stage_b(candidate, context):
    return {"simulation_results": {"budget_deficit": candidate["cost"]}}


class _BatchPort:
    def __init__(self, steps, cause=None):
        self.steps = list(steps)
        self.index = 0
        self.cause = cause
        self.service = None
        self.accepted_ref = None
        self.accepted_view = None
        self.accepted_bytes = None

    def generate(self, *args):
        raise AssertionError("The public batch port must be used")

    def generate_batch(self, history, current_best, context, batch_size):
        if self.accepted_ref is None and history:
            self.accepted_ref = self.service.checkpoint_ref
            self.accepted_view = _partial(self.service)
            self.accepted_bytes = self.service._store.get_bytes(self.accepted_ref)
        step = self.steps[self.index] if self.index < len(self.steps) else "empty"
        self.index += 1
        if step == "signal":
            raise self.cause
        if step == "candidate":
            return [{"cost": 1}]
        return []

    def get_state(self):
        return {
            "version": "batch-reason-fixture.v1",
            "steps": list(self.steps),
            "index": self.index,
        }

    def set_state(self, state):
        assert state["version"] == "batch-reason-fixture.v1"
        assert state["steps"] == self.steps
        assert type(state["index"]) is int
        self.index = state["index"]


def _service(store, steps, cause=None):
    port = _BatchPort(steps, cause)
    service = NativeSearchService(
        SearchController(
            SearchConfig(
                stopping=CompositeStoppingCriterion([MaxIterations(2), CostBudgetStopping(100)]),
                objective=CompositeObjective([BudgetDeficitObjective()]),
                enable_stage_a=False,
                batch_size=2,
                max_empty_generation_attempts=2,
            ),
            port,
            _stage_a,
            _stage_b,
        ),
        store=store,
    )
    port.service = service
    return service


def _partial(service):
    state = service.controller._run_state
    return {
        "history": deepcopy(state.history),
        "evaluation_iterations": state.evaluation_iterations,
        "stage_b_evaluations": state.stage_b_evaluations,
        "budget_spent": state.budget_spent,
        "budget_snapshot": deepcopy(state.budget_snapshot),
        "pending": deepcopy(service._pending_candidates),
        "completed": set(service._completed_candidate_ids),
    }


@pytest.mark.parametrize("exception_type", [StopIteration, ValueError, CancelledError])
def test_empty_batch_then_declared_signal_preserves_cause_partial_cost_and_fresh_view(
    tmp_path, exception_type
):
    store = FileSystemCAS(tmp_path / "cas")
    cause = exception_type("declared batch cancellation/refusal/exhaustion")
    service = _service(store, ["empty", "signal"], cause)
    with pytest.raises(exception_type) as raised:
        service.run_search(
            initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 2}
        )
    assert raised.value is cause
    port = service.controller._generator
    assert port.accepted_ref is not None
    old_bytes = port.accepted_bytes
    assert _partial(service) == port.accepted_view
    assert service.controller._run_state.evaluation_iterations == 1
    assert service.controller._run_state.budget_spent == 7.5
    assert service.controller._run_state.generation_attempts == 1
    assert service.controller._run_state.empty_generation_attempts == 1
    assert service._failure == f"{exception_type.__name__}: {cause}"
    observer = _service(FileSystemCAS(tmp_path / "cas"), ["empty", "signal"], cause)
    observer.restore(service.checkpoint_ref)
    assert _partial(observer) == _partial(service)
    assert observer.controller._generator.get_state() == port.get_state()
    assert observer._failure == service._failure
    assert store.get_bytes(port.accepted_ref) == old_bytes


@pytest.mark.parametrize(
    "steps, expected_reason, expected_iterations",
    [
        (["empty", "candidate"], "[max_iterations] Maximum iterations (2) reached", 2),
        (["empty", "empty"], "generation_exhausted", 1),
    ],
)
def test_empty_batch_transient_and_persistent_preserve_actual_partial_cost(
    tmp_path, steps, expected_reason, expected_iterations
):
    store = FileSystemCAS(tmp_path / "cas")
    service = _service(store, steps)
    result = service.run_search(
        initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 2}
    )
    assert result.stopping_reason == expected_reason
    assert result.iterations_completed == result.stage_b_evaluations == expected_iterations
    assert service.controller._run_state.generation_attempts == 2
    assert service.controller._run_state.budget_spent == 7.5
    assert [row.candidate["cost"] for row in result.history] == (
        [2, 1] if expected_iterations == 2 else [2]
    )
    observer = _service(FileSystemCAS(tmp_path / "cas"), steps)
    observer.restore(service.checkpoint_ref)
    assert _partial(observer) == _partial(service)
    assert observer.resume_search(context={"cumulative_cost_usd": 7.5}).history == result.history


def test_async_cancel_after_empty_public_batch_keeps_acknowledged_generator_and_partial_state(
    tmp_path,
):
    store = FileSystemCAS(tmp_path / "cas")
    cause = asyncio.CancelledError("actual asynchronous batch cancellation")
    service = _service(store, ["candidate", "empty", "signal"], cause)
    context = {"cumulative_cost_usd": 7.5}
    proposal = service.ask(None, None, context)[0]
    evaluation = service.controller._evaluate_for_tell(
        proposal.payload, iteration=0, context=context
    )
    service.tell(proposal.candidate_id, evaluation)
    assert service.ask(None, None, context) == []
    acknowledged_ref = service.checkpoint_ref
    old_bytes = store.get_bytes(acknowledged_ref)
    state_before = deepcopy(service.controller._generator.get_state())
    partial_before = _partial(service)
    with pytest.raises(asyncio.CancelledError) as raised:
        service.ask(None, None, context)
    assert raised.value is cause
    assert _partial(service) == partial_before
    assert service.checkpoint_ref == acknowledged_ref
    assert service.controller._generator.get_state() == state_before
    observer = _service(FileSystemCAS(tmp_path / "cas"), ["candidate", "empty", "signal"], cause)
    observer.restore(acknowledged_ref)
    assert _partial(observer) == _partial(service)
    assert observer.controller._generator.get_state() == service.controller._generator.get_state()
    assert store.get_bytes(acknowledged_ref) == old_bytes
