"""Measured resource settlement through the existing persisted budget owner."""

from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetResourceEvent,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def owner(path):
    return BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}),
        ledger=FileBudgetLedger(path, mutation_history_limit=1),
    )


def event(request_id="request-1", amount="1", keys=("run",)):
    return BudgetResourceEvent(
        provider="provider-a",
        request_id=request_id,
        run_id="run-1",
        amount_usd=Decimal(amount),
        budget_keys=keys,
    )


def test_measured_charge_reopens_and_duplicate_survives_journal_eviction(tmp_path):
    path = tmp_path / "budget.json"
    middleware = owner(path)
    assert middleware.reserve_resource(
        "attempt-1", run_id="run-1", budget_keys=("run",), estimated_usd=Decimal("2")
    )
    settled = middleware.settle_resource("attempt-1", event())
    assert settled.applied_amount == Decimal("1")
    reopened = owner(path)
    assert reopened.budget_state.spent["run"] == Decimal("1")
    assert reopened.budget_state.reserved["run"] == 0
    assert reopened.budget_state.remaining("run") == Decimal("4")
    reopened.record_spend_safe("run", Decimal("0"))
    before = FileBudgetLedger(path).snapshot()
    duplicate = reopened.settle_resource("attempt-1", event())
    assert duplicate.revision == before.revision
    assert FileBudgetLedger(path).snapshot() == before
    with pytest.raises(ValueError, match="conflict"):
        reopened.settle_resource("attempt-1", event(amount="2"))
    assert FileBudgetLedger(path).snapshot() == before


def test_actual_above_estimate_and_unlimited_key_are_fully_charged(tmp_path):
    middleware = owner(tmp_path / "budget.json")
    assert middleware.reserve_resource(
        "attempt-1", run_id="run-1", budget_keys=("run", "unlimited"), estimated_usd=Decimal("0.5")
    )
    middleware.settle_resource("attempt-1", event(amount="2", keys=("run", "unlimited")))
    state = middleware.budget_state
    assert state.spent == {"run": Decimal("2"), "unlimited": Decimal("2")}
    assert state.remaining("run") == Decimal("3")
    assert state.provider_spent == {"provider-a": Decimal("2")}
    assert state.reserved.get("run", 0) == 0


def test_reservations_are_owned_and_replay_does_not_release_another_attempt(tmp_path):
    middleware = owner(tmp_path / "budget.json")
    for attempt in ("attempt-1", "attempt-2"):
        assert middleware.reserve_resource(
            attempt, run_id="run-1", budget_keys=("run",), estimated_usd=Decimal("2")
        )
    middleware.settle_resource("attempt-1", event())
    middleware.settle_resource("attempt-1", event())
    assert middleware.budget_state.reserved["run"] == Decimal("2")
    middleware.settle_resource("attempt-2", event("request-2", "0.5"))
    assert middleware.budget_state.spent["run"] == Decimal("1.5")
    assert middleware.budget_state.remaining("run") == Decimal("3.5")


def test_same_provider_receipt_delivery_with_new_reservation_does_not_double_charge(tmp_path):
    middleware = owner(tmp_path / "budget.json")
    for attempt in ("attempt-1", "attempt-2"):
        assert middleware.reserve_resource(
            attempt, run_id="run-1", budget_keys=("run",), estimated_usd=Decimal("1")
        )
        middleware.settle_resource(attempt, event())
    assert middleware.budget_state.spent["run"] == Decimal("1")
    assert middleware.budget_state.reserved["run"] == 0


def test_unknown_billing_retains_reservation_for_reconciliation(tmp_path):
    path = tmp_path / "budget.json"
    middleware = owner(path)
    middleware.reserve_resource(
        "attempt-1", run_id="run-1", budget_keys=("run",), estimated_usd=Decimal("2")
    )
    middleware.require_reconciliation("attempt-1")
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.resource_reservations["attempt-1"].status == "reconciliation_required"
    assert snapshot.state.spent == {}
    assert snapshot.state.remaining("run") == Decimal("3")
    middleware.settle_resource("attempt-1", event())
    assert owner(path).budget_state.remaining("run") == Decimal("4")
