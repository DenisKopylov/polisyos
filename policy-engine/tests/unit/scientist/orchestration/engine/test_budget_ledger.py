"""Native single-key settlement through the canonical B1.1 budget owner.

Reservations are aggregate key balances. A durable spend receipt does not
release them or establish attempt ownership or atomic multi-key settlement.
"""

import hashlib
import json
from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine import budget_ledger
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def owner(path):
    return BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}),
        ledger=FileBudgetLedger(path, mutation_history_limit=1),
    )


def event(request_id="request-1", amount="1", key="run"):
    payload = {"provider": "provider-a", "request_id": request_id, "amount": amount, "key": key}
    return {
        "event_id": f"provider-a:{request_id}:{key}",
        "key": key,
        "amount": Decimal(amount),
        "payload_digest": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "provider": "provider-a",
    }


def test_measured_charge_reopens_and_duplicate_survives_journal_eviction(tmp_path):
    path = tmp_path / "budget.json"
    middleware = owner(path)
    assert middleware.reserve_safe("run", Decimal("2"))
    settled = middleware.settle_spend_safe(**event())
    assert isinstance(settled, BudgetLedgerSpendReceipt)
    assert settled.amount == Decimal("1")
    assert middleware.budget_state.reserved["run"] == Decimal("2")
    assert middleware.release_safe("run", Decimal("2")) == Decimal("2")
    reopened = owner(path)
    assert reopened.budget_state.spent["run"] == Decimal("1")
    assert reopened.budget_state.reserved["run"] == 0
    assert reopened.budget_state.remaining("run") == Decimal("4")
    reopened.record_spend_safe("run", Decimal("0"))
    before = FileBudgetLedger(path).snapshot()
    assert all(m.operation != "settle_spend" for m in before.recent_mutations)
    duplicate = reopened.settle_spend_safe(**event())
    assert duplicate == settled
    assert reopened.resolve_spend_safe(settled.event_id) == settled
    assert FileBudgetLedger(path).snapshot() == before
    for change in (
        {"amount": Decimal("2")},
        {"key": "other"},
        {"provider": "other"},
        {"payload_digest": "0" * 64},
    ):
        with pytest.raises(ValueError, match="conflict"):
            reopened.settle_spend_safe(**{**event(), **change})
        assert FileBudgetLedger(path).snapshot() == before
    with pytest.raises(ValueError, match="frozen"):
        settled.amount = Decimal("2")
    assert FileBudgetLedger(path).snapshot() == before


@pytest.mark.parametrize("key", ["run", "unlimited"])
def test_actual_above_estimate_and_unlimited_key_are_fully_charged(tmp_path, key):
    middleware = owner(tmp_path / "budget.json")
    assert middleware.reserve_safe(key, Decimal("0.5"))
    middleware.settle_spend_safe(**event(amount="2", key=key))
    state = middleware.budget_state
    assert state.spent == {key: Decimal("2")}
    assert state.remaining(key) == (Decimal("2.5") if key == "run" else None)
    assert state.provider_spent == {"provider-a": Decimal("2")}
    assert state.reserved[key] == Decimal("0.5")
    assert middleware.release_safe(key, Decimal("0.5")) == Decimal("0.5")
    assert middleware.budget_state.reserved[key] == 0
    assert middleware.budget_state.remaining(key) == (Decimal("3") if key == "run" else None)


def test_receipt_retry_does_not_release_aggregate_reserved_capacity(tmp_path):
    middleware = owner(tmp_path / "budget.json")
    assert middleware.reserve_safe("run", Decimal("2"))
    assert middleware.reserve_safe("run", Decimal("2"))
    receipt = middleware.settle_spend_safe(**event())
    assert middleware.settle_spend_safe(**event()) == receipt
    assert middleware.budget_state.reserved["run"] == Decimal("4")
    assert middleware.release_safe("run", Decimal("2")) == Decimal("2")
    assert middleware.budget_state.reserved["run"] == Decimal("2")
    middleware.settle_spend_safe(**event("request-2", "0.5"))
    assert middleware.budget_state.reserved["run"] == Decimal("2")
    assert middleware.release_safe("run", Decimal("2")) == Decimal("2")
    assert middleware.budget_state.spent["run"] == Decimal("1.5")
    assert middleware.budget_state.remaining("run") == Decimal("3.5")


def test_same_provider_receipt_delivery_with_new_reservation_does_not_double_charge(tmp_path):
    middleware = owner(tmp_path / "budget.json")
    first = None
    for _ in range(2):
        assert middleware.reserve_safe("run", Decimal("1"))
        receipt = middleware.settle_spend_safe(**event())
        if first is None:
            first = receipt
        assert receipt == first
        assert middleware.budget_state.reserved["run"] == Decimal("1")
        assert middleware.release_safe("run", Decimal("1")) == Decimal("1")
    assert middleware.budget_state.spent["run"] == Decimal("1")
    assert middleware.budget_state.reserved["run"] == 0


@pytest.mark.parametrize("write_before_ack", [False, True])
def test_unknown_ack_retains_capacity_until_fresh_receipt_resolution(
    tmp_path, monkeypatch, write_before_ack
):
    path = tmp_path / "budget.json"
    middleware = owner(path)
    assert middleware.reserve_safe("run", Decimal("2"))
    actual_replace = budget_ledger.os.replace

    def lose_ack(source, target):
        if target == path:
            if write_before_ack:
                actual_replace(source, target)
            raise OSError("actual ledger publication acknowledgment unavailable")
        return actual_replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(budget_ledger.os, "replace", lose_ack)
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as error:
            middleware.settle_spend_safe(**event())
    assert error.value.event_id == event()["event_id"]
    assert error.value.payload_digest == event()["payload_digest"]
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.reserved["run"] == Decimal("2")
    assert snapshot.state.spent == ({"run": Decimal("1")} if write_before_ack else {})
    reopened = owner(path)
    resolved = reopened.resolve_spend_safe(event()["event_id"])
    assert (resolved is not None) is write_before_ack
    receipt = reopened.settle_spend_safe(**event())
    assert reopened.resolve_spend_safe(receipt.event_id) == receipt
    assert reopened.settle_spend_safe(**event()) == receipt
    assert reopened.budget_state.spent["run"] == Decimal("1")
    assert reopened.budget_state.reserved["run"] == Decimal("2")
    assert reopened.release_safe("run", Decimal("2")) == Decimal("2")
    assert owner(path).budget_state.remaining("run") == Decimal("4")
