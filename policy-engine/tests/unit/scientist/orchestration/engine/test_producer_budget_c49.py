"""Read the real durable owner; never equate physical work with USD."""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _owner(tmp_path, *, cap="1"):
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    binding = BudgetLedgerProducerRunBinding(
        run_id="run-current",
        tenant_id="tenant-current",
        cell_id="cell-current",
        profile_id="profile-current",
        control_job_id="job-current",
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(cap))})
    return middleware, binding, state


def _settle(middleware, binding, name, amount, origin="reported"):
    with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
        return middleware.settle_producer_event_safe(
            name,
            _digest("request-" + name),
            _digest("response-" + name),
            key=f"nl-run:{binding.run_id}",
            model="fixture-model",
            provider="fixture-provider",
            amount=Decimal(amount) if amount is not None else None,
            cost_origin=origin,
        )


def test_actual_snapshot_refresh_exhaustion_and_stable_source_identity(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "first", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    assert first.producer_spent_usd == Decimal("0.2")
    assert first.currency == "USD" and first.remaining_usd == Decimal("0.8")
    assert observer.admit().source_basis_digest == first.source_basis_digest
    # A fresh reader of the same file sees the same canonical owner and event.
    snapshot = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert snapshot.producer_settlements["first"].payload_digest == first.producer_events[0][1]
    _settle(middleware, binding, "second", "0.8")
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    assert observer.last_checked.remaining_usd == Decimal("0")
    assert observer.last_checked.source_basis_digest != first.source_basis_digest
    assert state.spent["run"] == Decimal("1")
    assert "n5_usd_price_not_established" in first.limitations


@pytest.mark.parametrize("kind", ["pending", "unknown", "missing"])
def test_unavailable_producer_cost_never_becomes_free_budget(tmp_path, kind):
    middleware, binding, state = _owner(tmp_path)
    if kind == "pending":
        with middleware.producer_run_binding_scope(binding):
            middleware.begin_producer_event_safe(
                "pending",
                _digest("pending"),
                key=f"nl-run:{binding.run_id}",
                model="m",
                provider="p",
            )
    elif kind == "unknown":
        _settle(middleware, binding, "unknown", None, "unknown")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(ProducerBudgetSourceError):
        observer.admit()
    assert observer.last_checked is None
    assert state.spent == {}


def test_zero_cap_has_independent_refusal_without_inventing_zero_spend(tmp_path):
    middleware, binding, state = _owner(tmp_path, cap="0")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    assert observer.last_checked is None and state.spent == {}


def test_foreign_owner_changed_cap_detached_view_and_snapshot_cannot_authorize(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "first", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    detached = middleware.snapshot_safe()
    detached.producer_settlements.clear()
    assert observer.admit().source_basis_digest == first.source_basis_digest
    with pytest.raises(ProducerBudgetSourceError, match="state_binding_mismatch"):
        observer(state.model_copy(deep=True))
    state.limits["run"].max_usd = Decimal("2")
    with pytest.raises(ProducerBudgetSourceError, match="run_limit_changed"):
        observer.admit()


def test_same_key_foreign_tenant_event_is_not_silently_filtered(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "own", "0.2")
    foreign = binding.model_copy(update={"tenant_id": "foreign-tenant"})
    _settle(middleware, foreign, "foreign", "0.1")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(ProducerBudgetSourceError, match="binding_mismatch"):
        observer.admit()
    assert state.spent == {}


def test_unrelated_global_revision_does_not_renew_the_selected_source_basis(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "own", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    unrelated = binding.model_copy(
        update={"run_id": "unrelated-run", "control_job_id": "unrelated-job"}
    )
    _settle(middleware, unrelated, "unrelated", "0.3")
    current = observer.admit()
    assert current.ledger_revision > first.ledger_revision
    assert current.source_basis_digest == first.source_basis_digest
    assert current.producer_events == first.producer_events
