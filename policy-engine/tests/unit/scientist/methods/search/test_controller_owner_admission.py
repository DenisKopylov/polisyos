"""Ordinary search consumes canonical owner admission after actual LLM events."""

import asyncio
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.llm.traced_client import LLMAccountingError
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver
from polisyos.scientist.methods.search.stopping import CostBudgetStopping, MaxIterations
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerCompletionRequiredError,
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

_helpers = run_path(str(Path(__file__).with_name("test_controller.py")))
_text = run_path(
    str(
        Path(__file__).resolve().parents[5]
        / "tests/integration/core/llm/test_gateway_response_text_cost.py"
    )
)


class _CountedGenerator:
    def __init__(self):
        self.calls = 0

    def generate(self, history, current_best, context):
        self.calls += 1
        return {"candidate_id": "candidate-1", "semantic": {"interventions": []}}


def _controller(owner, *, stopping):
    evaluations = []

    def stage_b(candidate, context):
        evaluations.append(candidate)
        return {"simulation_results": {"gdp_change": 2}, "feedback": {"verdict": "APPROVE"}}

    search = _helpers["controller"](stage_b, stopping=stopping, owner=owner)
    generator = _CountedGenerator()
    search._generator = generator
    return search, generator, evaluations


def _fresh_checkpoint_state(search):
    # An actual new reader sees JSON bytes, not an in-memory copied dataclass.
    payload = json.loads(json.dumps(search._run_state.checkpoint_state()))
    restored = SearchRunState.from_checkpoint(payload)
    assert restored.budget_snapshot == search._run_state.budget_snapshot
    assert restored.budget_evidence == search._run_state.budget_evidence
    return payload, restored


def _actual_operation(tmp_path, lexeme):
    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", lexeme))
    path, enforcer = _text["build_owned_enforcer"](tmp_path, gateway)
    return gateway, path, enforcer


def _fresh_owner(path):
    return BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))


@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000"])
@pytest.mark.parametrize("cost_stopping", [False, True])
def test_actual_tiny_response_pending_owner_stops_run_and_direct_ask_before_proposal(
    tmp_path, lexeme, cost_stopping
):
    gateway, path, enforcer = _actual_operation(tmp_path, lexeme)
    with pytest.raises(LLMAccountingError) as failure:
        asyncio.run(_text["invoke"](enforcer))
    event = failure.value.event["producer_event"]
    before = FileBudgetLedger(path).snapshot()
    assert gateway.transport.calls == 1 and event.amount is None
    assert before.state.spent == {} and before.spend_receipts == {}
    assert before.state.reserved["run"] > 0
    pending = next(iter(before.completion_obligations.values()))
    assert pending.event_payload["event_id"] == event.event_id
    assert pending.event_payload["amount"] is None
    stopping = CostBudgetStopping(1) if cost_stopping else MaxIterations(1)
    search, generator, evaluations = _controller(_fresh_owner(path), stopping=stopping)
    result = search.run({"cumulative_cost_usd": 0})
    assert generator.calls == 0 and evaluations == [] and result.iterations_completed == 0
    assert result.best_candidate is None
    assert result.telemetry["budget_snapshot"] == {}
    assert result.telemetry["budget_spent"] is None
    assert result.telemetry["budget_available"] is False
    assert search._run_state.budget_spent is None
    assert search._stopping_state()["budget_spent"] is None
    assert "cumulative_cost_usd" not in search._stopping_state()
    _, restored = _fresh_checkpoint_state(search)
    assert restored.budget_spent is None and restored.budget_available is False
    assert result.telemetry["budget_evidence"]["admission"] == "unavailable"
    if cost_stopping:
        assert "Cost budget unavailable" in result.stopping_reason
    else:
        assert (
            result.stopping_reason
            == "budget_owner_admission_refused:BudgetLedgerCompletionRequiredError"
        )
    direct, direct_generator, direct_evaluations = _controller(
        _fresh_owner(path), stopping=MaxIterations(1)
    )
    with pytest.raises(BudgetLedgerCompletionRequiredError):
        _NativeSearchServiceDriver(direct).ask(None, None, {})
    assert direct_generator.calls == 0 and direct_evaluations == []
    assert direct._run_state.budget_spent is None
    assert direct._stopping_state()["budget_spent"] is None
    assert FileBudgetLedger(path).snapshot() == before and gateway.transport.calls == 1


@pytest.mark.parametrize("amount,cutoff", [("1", 1), ("5", 10)])
def test_actual_paid_or_exhausted_owner_keeps_known_spend_in_ordinary_controller(
    tmp_path, amount, cutoff
):
    gateway, path, enforcer = _actual_operation(tmp_path, amount)
    asyncio.run(_text["invoke"](enforcer))
    before = FileBudgetLedger(path).snapshot()
    assert before.state.spent == {"run": Decimal(amount)}
    assert len(before.spend_receipts) == 1 and before.completion_obligations == {}
    search, generator, evaluations = _controller(
        _fresh_owner(path), stopping=CostBudgetStopping(cutoff)
    )
    result = search.run({"cumulative_cost_usd": 0})
    assert generator.calls == 0 and evaluations == []
    assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": float(amount)}
    assert result.telemetry["budget_available"] is True
    assert search._run_state.budget_spent == float(amount)
    assert search._stopping_state()["budget_spent"] == float(amount)
    _, restored = _fresh_checkpoint_state(search)
    assert restored.budget_spent == float(amount) and restored.budget_available is True
    assert result.telemetry["budget_evidence"]["admission"] == (
        "exhausted" if amount == "5" else "admitted"
    )
    assert gateway.transport.calls == 1 and FileBudgetLedger(path).snapshot() == before


def test_initialized_owner_with_no_actual_events_preserves_known_initial_zero(tmp_path):
    gateway, path, _ = _actual_operation(tmp_path, "0")
    before = FileBudgetLedger(path).snapshot()
    assert before.spend_receipts == {} and before.completion_obligations == {}
    search, generator, evaluations = _controller(_fresh_owner(path), stopping=CostBudgetStopping(1))
    search._config.max_iterations_hard_limit = 1
    result = search.run({"cumulative_cost_usd": 999})
    assert generator.calls == len(evaluations) == result.iterations_completed == 1
    assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": 0.0}
    assert result.telemetry["budget_available"] is True
    assert search._run_state.budget_spent == 0
    assert search._stopping_state()["budget_spent"] == 0
    _, restored = _fresh_checkpoint_state(search)
    assert restored.budget_spent == 0 and restored.budget_available is True
    assert result.telemetry["budget_evidence"]["admission"] == "admitted"
    assert gateway.transport.calls == 0 and FileBudgetLedger(path).snapshot() == before


def test_retained_actual_response_cost_without_settlement_cannot_admit_next_search(
    tmp_path, monkeypatch
):
    gateway, path, enforcer = _actual_operation(tmp_path, "1")
    owner = enforcer._budget_middleware

    def remove_settlement(event_id, key, amount, *, payload_digest, provider):
        # Preserve typed ACK coordinates and cost=1; no ledger debit or receipt.
        return BudgetLedgerSpendReceipt(
            event_id=event_id,
            key=key,
            amount=amount,
            payload_digest=payload_digest,
            provider=provider,
            revision=FileBudgetLedger(path).snapshot().revision,
        )

    monkeypatch.setattr(owner, "settle_spend_safe", remove_settlement)
    with pytest.raises(LLMAccountingError):
        asyncio.run(_text["invoke"](enforcer))
    assert gateway.normalized_response.usage.cost_usd == 1
    before = FileBudgetLedger(path).snapshot()
    assert before.state.spent == {} and before.spend_receipts == {}
    assert before.completion_obligations
    search, generator, evaluations = _controller(_fresh_owner(path), stopping=CostBudgetStopping(1))
    result = search.run({"cumulative_cost_usd": 0})
    assert generator.calls == 0 and evaluations == []
    assert result.telemetry["budget_available"] is False
    assert result.telemetry["budget_snapshot"] == {}
    assert search._run_state.budget_spent is None
    assert search._stopping_state()["budget_spent"] is None
    _, restored = _fresh_checkpoint_state(search)
    assert restored.budget_spent is None and restored.budget_available is False
    assert gateway.transport.calls == 1 and FileBudgetLedger(path).snapshot() == before


@pytest.mark.parametrize("changed", ["available", "zero_snapshot", "admission"])
def test_actual_pending_checkpoint_cannot_invent_admission_while_retaining_owner_markers(
    tmp_path, changed
):
    _, path, enforcer = _actual_operation(tmp_path, "1e-1000")
    with pytest.raises(LLMAccountingError):
        asyncio.run(_text["invoke"](enforcer))
    search, generator, evaluations = _controller(_fresh_owner(path), stopping=CostBudgetStopping(1))
    search.run({"cumulative_cost_usd": 0})
    payload, restored = _fresh_checkpoint_state(search)
    assert restored.budget_spent is None and generator.calls == 0 and evaluations == []
    altered = deepcopy(payload)
    if changed == "available":
        altered["budget_available"] = True
    elif changed == "zero_snapshot":
        altered["budget_snapshot"] = {"cumulative_cost_usd": 0.0}
    else:
        altered["budget_evidence"]["admission"] = "fabricated_success"
    # Keep ledger identity, all receipt/source markers and the actual run ID.
    assert altered["budget_ledger_id"] == payload["budget_ledger_id"]
    with pytest.raises(ValueError):
        SearchRunState.from_checkpoint(altered)
