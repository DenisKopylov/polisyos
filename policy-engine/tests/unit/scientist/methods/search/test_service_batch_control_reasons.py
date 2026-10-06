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
        self.rollback_cause = None
        self.before_signal = None

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
            if self.before_signal is not None:
                self.before_signal()
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
        if self.rollback_cause is not None:
            raise self.rollback_cause
        assert state["version"] == "batch-reason-fixture.v1"
        assert state["steps"] == self.steps
        assert type(state["index"]) is int
        self.index = state["index"]


def _service(store, steps, cause=None, *, owner=None):
    port = _BatchPort(steps, cause)
    service = NativeSearchService(
        SearchController(
            SearchConfig(
                stopping=CompositeStoppingCriterion([MaxIterations(2), CostBudgetStopping(100)]),
                objective=CompositeObjective([BudgetDeficitObjective()]),
                enable_stage_a=False,
                batch_size=2,
                max_empty_generation_attempts=2,
                budget_middleware=owner,
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


@pytest.mark.parametrize(
    "exception_type", [StopIteration, ValueError, CancelledError, asyncio.CancelledError]
)
def test_empty_batch_signal_retains_real_provider_settlement_receipt_and_fresh_ledger(
    tmp_path, exception_type
):
    # A local supported transport emits an actual producer response. This proves
    # exact local settlement/custody, not independent external billing truth.
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer

    class Transport:
        calls = 0

        def invoke(self, prompt, **kwargs):
            self.calls += 1
            return {
                "content": "settled",
                "provider": "fixture-batch-provider",
                "request_id": "batch-control-settled-request",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 1.25},
            }

    ledger_path = tmp_path / "paid-budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("100"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(ledger_path))
    transport = Transport()
    caller = LLMBudgetEnforcer(
        client=transport,
        budget_state=state,
        budget_middleware=owner,
        budget_keys=["run"],
        run_id="batch-control-run",
        model_name="fixture-model",
    )
    caller.invoke(
        "one actual transport call",
        _evaluation_id="accepted-previous-call",
        _prompt_tokens_estimate=1,
        max_tokens=1,
    )
    before = FileBudgetLedger(ledger_path).snapshot()
    assert transport.calls == 1
    assert before.state.spent == {"run": Decimal("1.25")}
    assert before.state.provider_spent == {"fixture-batch-provider": Decimal("1.25")}
    assert len(before.spend_receipts) == 1
    receipt = next(iter(before.spend_receipts.values()))
    assert receipt.amount == Decimal("1.25")
    assert receipt.provider == "fixture-batch-provider"

    store = FileSystemCAS(tmp_path / "cas")
    cause = exception_type("batch stopped after a locally acknowledged paid call")
    service = _service(store, ["empty", "signal"], cause, owner=owner)
    with pytest.raises(exception_type) as raised:
        service.run_search(
            initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 2}
        )
    assert raised.value is cause
    port = service.controller._generator
    assert _partial(service) == port.accepted_view
    assert service.controller._run_state.budget_spent == 1.25
    assert service._failure == f"{exception_type.__name__}: {cause}"
    after = FileBudgetLedger(ledger_path).snapshot()
    assert after == before
    assert ledger_path.read_bytes()
    fresh_owner = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    observer = _service(
        FileSystemCAS(tmp_path / "cas"), ["empty", "signal"], cause, owner=fresh_owner
    )
    observer.restore(service.checkpoint_ref)
    assert _partial(observer) == _partial(service)
    assert observer._failure == service._failure
    assert observer.controller._generator.get_state() == port.get_state()
    assert FileBudgetLedger(ledger_path).snapshot() == before
    assert store.get_bytes(port.accepted_ref) == port.accepted_bytes
    assert transport.calls == 1
    print("actual_batch_local_settlement", before.model_dump_json())


def test_async_generator_rollback_refusal_blocks_publication_and_preserves_original_cause(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    original = asyncio.CancelledError("original batch cancellation")
    service = _service(store, ["candidate", "empty", "signal"], original)
    proposal = service.ask(None, None, {})[0]
    evaluation = service.controller._evaluate_for_tell(proposal.payload, iteration=0, context={})
    service.tell(proposal.candidate_id, evaluation)
    assert service.ask(None, None, {}) == []
    ref = service.checkpoint_ref
    old_bytes = store.get_bytes(ref)
    before = _partial(service)
    service.controller._generator.rollback_cause = asyncio.CancelledError("rollback refused")
    with pytest.raises(asyncio.CancelledError) as raised:
        service.ask(None, None, {})
    assert raised.value is original
    assert _partial(service) == before
    assert service.checkpoint_ref == ref
    assert service._publication_blocked is True
    with pytest.raises(ValueError, match="reopen_last_acknowledged_ref"):
        service.ask(None, None, {})
    observer = _service(FileSystemCAS(tmp_path / "cas"), ["candidate", "empty", "signal"], original)
    observer.restore(ref)
    assert _partial(observer) == before
    assert observer.controller._generator.index == 2
    assert store.get_bytes(ref) == old_bytes


class _FailingCheckpointCAS(FileSystemCAS):
    fail_checkpoint = False

    def put_json(self, *args, **kwargs):
        if self.fail_checkpoint:
            raise OSError("actual failure checkpoint publication refused")
        return super().put_json(*args, **kwargs)


def test_failure_checkpoint_io_refusal_retains_original_batch_reason_and_last_ack(tmp_path):
    store = _FailingCheckpointCAS(tmp_path / "cas")
    original = ValueError("original declared batch refusal")
    service = _service(store, ["empty", "signal"], original)
    service.controller._generator.before_signal = lambda: setattr(store, "fail_checkpoint", True)
    with pytest.raises(ValueError) as raised:
        service.run_search(
            initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 2}
        )
    assert raised.value is original
    port = service.controller._generator
    assert _partial(service) == port.accepted_view
    assert service._failure == f"ValueError: {original}"
    assert service._publication_blocked is True
    assert store.get_bytes(port.accepted_ref) == port.accepted_bytes
    observer = _service(FileSystemCAS(tmp_path / "cas"), ["empty", "signal"], original)
    observer.restore(service.checkpoint_ref)
    assert _partial(observer) == _partial(service)
    assert observer.controller._generator.get_state() == port.get_state()
