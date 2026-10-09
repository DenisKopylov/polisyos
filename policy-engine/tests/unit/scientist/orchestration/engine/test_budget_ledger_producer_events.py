"""Durable producer records retain monetary origin and unresolved status."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def _middleware(path: Path) -> BudgetMiddleware:
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    return BudgetMiddleware(state, ledger=FileBudgetLedger(path))


def _dig(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_pending_unknown_estimated_reported_zero_and_reuse_survive_reopen(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    pending = middleware.begin_producer_event_safe(
        "pending", _dig("request-pending"), key="run", model="m", provider="p"
    )
    assert pending.status == "pending" and pending.amount is None
    assert middleware.budget_state.spent == {}

    unknown = middleware.settle_producer_event_safe(
        "pending",
        _dig("request-pending"),
        _dig("response-unknown"),
        key="run",
        model="m",
        provider="p",
        amount=None,
        cost_origin="unknown",
    )
    assert unknown.status == "unknown" and unknown.amount is None
    assert middleware.budget_state.spent == {}

    estimated = middleware.settle_producer_event_safe(
        "estimated",
        _dig("request-estimated"),
        _dig("response-estimated"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0.12"),
        cost_origin="estimated",
    )
    zero = middleware.settle_producer_event_safe(
        "reported-zero",
        _dig("request-zero"),
        _dig("response-zero"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0"),
        cost_origin="reported",
    )
    reuse = middleware.settle_producer_event_safe(
        "reuse-zero",
        _dig("request-reuse"),
        _dig("response-reuse"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0"),
        cost_origin="reuse",
        origin_event_id="reported-zero",
    )

    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.schema_version == "1.3"
    assert reopened.producer_settlements["pending"].status == "unknown"
    assert reopened.producer_settlements["pending"].amount is None
    assert reopened.producer_settlements["estimated"] == estimated
    assert estimated.cost_origin == "estimated" and estimated.amount == Decimal("0.12")
    assert zero.cost_origin == "reported" and zero.amount == Decimal("0")
    assert reuse.cost_origin == "reuse" and reuse.origin_event_id == "reported-zero"
    assert reopened.state.spent["run"] == Decimal("0.12")
    assert set(reopened.spend_receipts) == {"estimated", "reported-zero", "reuse-zero"}


def test_producer_run_binding_is_persisted_and_exactly_scoped_across_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    owner = BudgetLedgerProducerRunBinding(
        run_id="run-owner-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="research",
        control_job_id="job-a",
    )
    other_owner = owner.model_copy(update={"tenant_id": "tenant-b"})
    with middleware.producer_run_binding_scope(owner):
        pending = middleware.begin_producer_event_safe(
            "pending-owner-a",
            _dig("request-pending-owner-a"),
            key="nl-run:run-owner-a",
            model="m",
            provider="p",
        )

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    assert pending.status == "pending"
    assert pending.run_binding == owner
    assert reopened.list_producer_events_for_run_safe(owner) == (pending,)
    assert reopened.list_producer_events_for_run_safe(other_owner) == ()

    def _nest_conflicting_owner_scope() -> None:
        with middleware.producer_run_binding_scope(owner):
            with middleware.producer_run_binding_scope(other_owner):
                pass

    with pytest.raises(ValueError, match="producer_run_binding_conflict"):
        _nest_conflicting_owner_scope()

    # A nested identical scope cannot release the outer producer owner early.
    with middleware.producer_run_binding_scope(owner):
        with middleware.producer_run_binding_scope(owner):
            pass
        still_bound = middleware.begin_producer_event_safe(
            "nested-owner-a",
            _dig("request-nested-owner-a"),
            key="nl-run:run-owner-a",
            model="m",
            provider="p",
        )
    assert still_bound.run_binding == owner
    assert reopened.list_producer_events_for_run_safe(owner) == (pending, still_bound)


def test_delayed_settlement_retains_binding_issued_at_durable_begin(tmp_path: Path) -> None:
    middleware = _middleware(tmp_path / "ledger.json")
    owner = BudgetLedgerProducerRunBinding(
        run_id="run-late-settlement",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="research",
        control_job_id="job-late-settlement",
    )
    request_digest = _dig("request-late-settlement")
    payload_digest = _dig("response-late-settlement")
    with middleware.producer_run_binding_scope(owner):
        middleware.begin_producer_event_safe(
            "late-settlement",
            request_digest,
            key=f"nl-run:{owner.run_id}",
            model="m",
            provider="p",
        )

    settled = middleware.settle_producer_event_safe(
        "late-settlement",
        request_digest,
        payload_digest,
        key=f"nl-run:{owner.run_id}",
        model="m",
        provider="p",
        amount=Decimal("0.25"),
        cost_origin="reported",
    )
    assert settled.status == "committed"
    assert settled.run_binding == owner
    assert middleware.list_producer_events_for_run_safe(owner) == (settled,)
