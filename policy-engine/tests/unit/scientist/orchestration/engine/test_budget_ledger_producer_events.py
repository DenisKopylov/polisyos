"""Durable producer records retain monetary origin and unresolved status."""

from __future__ import annotations

import hashlib
import json
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
    source = middleware.settle_producer_event_safe(
        "reuse-source",
        _dig("request-reuse"),
        _dig("response-reuse-source"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0.01"),
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
        origin_event_id=source.event_id,
    )

    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.schema_version == "1.3"
    assert reopened.producer_settlements["pending"].status == "unknown"
    assert reopened.producer_settlements["pending"].amount is None
    assert reopened.producer_settlements["estimated"] == estimated
    assert estimated.cost_origin == "estimated" and estimated.amount == Decimal("0.12")
    assert zero.cost_origin == "reported" and zero.amount == Decimal("0")
    assert source.cost_origin == "reported" and source.amount == Decimal("0.01")
    assert reuse.cost_origin == "reuse" and reuse.origin_event_id == source.event_id
    assert reopened.state.spent["run"] == Decimal("0.13")
    assert set(reopened.spend_receipts) == {
        "estimated",
        "reported-zero",
        "reuse-source",
        "reuse-zero",
    }


@pytest.mark.parametrize(
    "origin_state",
    ["absent", "pending", "foreign", "request_mismatch", "model_mismatch", "provider_mismatch"],
)
def test_reuse_settlement_requires_a_committed_same_owner_source_before_write(
    tmp_path: Path,
    origin_state: str,
) -> None:
    path = tmp_path / f"{origin_state}.json"
    middleware = _middleware(path)
    owner = BudgetLedgerProducerRunBinding(
        run_id="run-owner-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="research",
        control_job_id="job-a",
    )
    foreign_owner = owner.model_copy(
        update={"run_id": "run-owner-b", "tenant_id": "tenant-b", "control_job_id": "job-b"}
    )
    request_digest = _dig("reuse-request")
    origin_event_id = "provider-origin"

    if origin_state == "pending":
        with middleware.producer_run_binding_scope(owner):
            middleware.begin_producer_event_safe(
                origin_event_id,
                request_digest,
                key=f"nl-run:{owner.run_id}",
                model="m",
                provider="p",
            )
    elif origin_state in {"foreign", "request_mismatch", "model_mismatch", "provider_mismatch"}:
        source_owner = foreign_owner if origin_state == "foreign" else owner
        source_request = (
            _dig("different-request") if origin_state == "request_mismatch" else request_digest
        )
        source_model = "source-model" if origin_state == "model_mismatch" else "m"
        source_provider = "source-provider" if origin_state == "provider_mismatch" else "p"
        with middleware.producer_run_binding_scope(source_owner):
            middleware.settle_producer_event_safe(
                origin_event_id,
                source_request,
                _dig("provider-origin-response"),
                key=f"nl-run:{source_owner.run_id}",
                model=source_model,
                provider=source_provider,
                amount=Decimal("0.02"),
                cost_origin="reported",
            )

    before = path.read_bytes()
    with middleware.producer_run_binding_scope(owner):
        with pytest.raises(ValueError, match="producer_reuse_origin"):
            middleware.settle_producer_event_safe(
                "reuse-attempt",
                request_digest,
                _dig("reuse-response"),
                key=f"nl-run:{owner.run_id}",
                model="m",
                provider="p",
                amount=Decimal(0),
                cost_origin="reuse",
                origin_event_id=None if origin_state == "absent" else origin_event_id,
            )

    assert path.read_bytes() == before
    reopened = FileBudgetLedger(path).snapshot()
    assert "reuse-attempt" not in reopened.producer_settlements


def test_unknown_physical_origin_allows_zero_reuse_without_promoting_unknown_cost(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown-origin.json"
    middleware = _middleware(path)
    owner = BudgetLedgerProducerRunBinding(
        run_id="run-owner-unknown",
        tenant_id="tenant-unknown",
        cell_id="cell-unknown",
        profile_id="research",
        control_job_id="job-unknown",
    )
    request_digest = _dig("unknown-reuse-request")
    with middleware.producer_run_binding_scope(owner):
        source = middleware.settle_producer_event_safe(
            "unknown-physical-origin",
            request_digest,
            _dig("unknown-physical-response"),
            key=f"nl-run:{owner.run_id}",
            model="m",
            provider="p",
            amount=None,
            cost_origin="unknown",
        )
        reuse = middleware.settle_producer_event_safe(
            "reuse-of-unknown-origin",
            request_digest,
            _dig("reused-response"),
            key=f"nl-run:{owner.run_id}",
            model="m",
            provider="p",
            amount=Decimal(0),
            cost_origin="reuse",
            origin_event_id=source.event_id,
        )

    reopened = FileBudgetLedger(path).snapshot()
    stored_source = reopened.producer_settlements[source.event_id]
    stored_reuse = reopened.producer_settlements[reuse.event_id]
    assert stored_source.status == "unknown"
    assert stored_source.cost_origin == "unknown"
    assert stored_source.amount is None
    assert stored_reuse.status == "committed"
    assert stored_reuse.cost_origin == "reuse"
    assert stored_reuse.amount == Decimal(0)
    assert stored_reuse.origin_event_id == stored_source.event_id
    assert stored_reuse.run_binding == stored_source.run_binding == owner
    assert reopened.state.spent.get(f"nl-run:{owner.run_id}", Decimal(0)) == Decimal(0)


def test_reopen_and_terminal_retry_reject_orphaned_reuse_origin(tmp_path: Path) -> None:
    path = tmp_path / "orphaned-reuse.json"
    middleware = _middleware(path)
    request_digest = _dig("orphan-request")
    response_digest = _dig("orphan-response")
    middleware.settle_producer_event_safe(
        "physical-origin",
        request_digest,
        _dig("physical-response"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0.02"),
        cost_origin="reported",
    )
    middleware.settle_producer_event_safe(
        "reuse-event",
        request_digest,
        response_digest,
        key="run",
        model="m",
        provider="p",
        amount=Decimal(0),
        cost_origin="reuse",
        origin_event_id="physical-origin",
    )

    wire = json.loads(path.read_text())
    wire["producer_settlements"]["reuse-event"]["origin_event_id"] = "missing-origin"
    path.write_text(json.dumps(wire))

    with pytest.raises(ValueError, match="producer_reuse_origin"):
        FileBudgetLedger(path).snapshot()
    with pytest.raises(ValueError, match="producer_reuse_origin"):
        middleware.settle_producer_event_safe(
            "reuse-event",
            request_digest,
            response_digest,
            key="run",
            model="m",
            provider="p",
            amount=Decimal(0),
            cost_origin="reuse",
            origin_event_id="missing-origin",
        )


def test_reuse_event_shape_is_refused_before_durable_state(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    source = middleware.settle_producer_event_safe(
        "physical-origin",
        _dig("request-shape"),
        _dig("physical-response"),
        key="run",
        model="m",
        provider="p",
        amount=Decimal("0.02"),
        cost_origin="reported",
    )
    before = path.read_bytes()

    for event_id, amount, cost_origin, origin_event_id in (
        ("missing-origin-id", Decimal(0), "reuse", None),
        ("nonzero-reuse", Decimal("0.01"), "reuse", source.event_id),
        ("provider-with-origin", Decimal("0.01"), "reported", source.event_id),
    ):
        with pytest.raises(ValueError, match="producer_reuse_origin"):
            middleware.settle_producer_event_safe(
                event_id,
                _dig("request-shape"),
                _dig(f"response-{event_id}"),
                key="run",
                model="m",
                provider="p",
                amount=amount,
                cost_origin=cost_origin,
                origin_event_id=origin_event_id,
            )
        assert path.read_bytes() == before

    assert set(FileBudgetLedger(path).snapshot().producer_settlements) == {source.event_id}


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
