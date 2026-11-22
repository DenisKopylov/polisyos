"""Adopt one exact settled draft under a current Native recovery lease."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from datetime import datetime

    from polisyos.core.llm.settlement import LLMProducerSettlement, LLMSettledResponse
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerReentryBudgetWindow,
        BudgetLedgerSnapshot,
    )


class NativeSettledDraftRecovery(BaseModel):
    """Candidate bytes and exact ledger pins supplied with the new approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_event_id: str = Field(pattern=r"^llm-provider:[a-f0-9]{32}$")
    ledger_revision: int = Field(ge=1, strict=True)
    response_text: str = Field(min_length=1, max_length=131_072, repr=False)


def _verify_settled_draft(
    selected: NativeSettledDraftRecovery,
    *,
    snapshot: BudgetLedgerSnapshot,
    window: BudgetLedgerReentryBudgetWindow,
    source_attempt: int,
    failed_lease_started_at: datetime,
    failed_at: datetime,
) -> LLMProducerSettlement:
    """Read the exact settled bytes and exclude later work in the same action window."""
    from polisyos.core.llm.settlement import (
        LLMProducerEvent,
        LLMProducerSettlement,
        LLMSettlementAck,
    )

    record = snapshot.producer_settlements.get(selected.producer_event_id)
    spend = snapshot.spend_receipts.get(selected.producer_event_id)
    binding = window.scope.run_binding
    mutations = tuple(item for item in snapshot.recent_mutations if item.revision > window.revision)
    if (
        snapshot.revision != selected.ledger_revision
        or snapshot.ledger_id != window.ledger_id
        or snapshot.reentry_budget_windows.get(window.window_id) != window
        or record is None
        or spend is None
        or record.event_id != selected.producer_event_id
        or record.run_binding != binding
        or record.control_job_attempt != source_attempt
        or record.status != "committed"
        or record.cost_origin not in ("estimated", "reported")
        or record.amount is None
        or snapshot.revision != record.revision
        or record.revision != window.revision + 2
        or len(mutations) != 2
        or (spend.event_id, spend.key, spend.provider, spend.amount, spend.revision)
        != (record.event_id, record.key, record.provider, record.amount, record.revision)
        or any(
            item.event_id != record.event_id
            and item.key == record.key
            and item.revision > window.revision
            for item in snapshot.producer_settlements.values()
        )
        or any(
            item.run_id == binding.run_id and item.revision > window.revision
            for item in snapshot.invocation_reservations.values()
        )
        or any(
            item.key == record.key and item.revision > window.revision
            for item in snapshot.compute_reservations.values()
        )
    ):
        raise ValueError("native_settled_draft_ledger_cut_mismatch")
    begin, settle = mutations
    if (
        (begin.operation, begin.revision, begin.key, begin.provider)
        != ("begin_producer_event", window.revision + 1, record.key, record.provider)
        or (settle.operation, settle.revision, settle.key, settle.provider)
        != ("settle_producer_event", record.revision, record.key, record.provider)
        or begin.writer != settle.writer
        or settle.amount != record.amount
        or settle.applied_amount != record.amount
        or not (
            failed_lease_started_at
            <= begin.committed_at
            <= record.committed_at
            <= spend.committed_at
            <= settle.committed_at
            <= failed_at
        )
    ):
        raise ValueError("native_settled_draft_begin_or_settlement_mismatch")
    event = LLMProducerEvent(
        event_id=record.event_id,
        request_digest=record.request_digest,
        response_digest=hashlib.sha256(selected.response_text.encode()).hexdigest(),
        model=record.model,
        provider=record.provider,
        amount=record.amount,
        cost_origin=record.cost_origin,
    )
    if (record.payload_digest, spend.payload_digest) != (event.payload_digest,) * 2:
        raise ValueError("native_settled_draft_response_mismatch")
    return LLMProducerSettlement(
        event,
        LLMSettlementAck(
            event.event_id, event.payload_digest, "committed", (event.event_id,), "ledger"
        ),
    )


@dataclass(slots=True)
class _DraftAdoption:
    """The approved candidate bytes and their exact historical settlement."""

    selected: NativeSettledDraftRecovery
    reopen: Callable[[], LLMProducerSettlement]
    lock: Lock = field(default_factory=Lock)
    consumed: bool = False


_ACTIVE: ContextVar[_DraftAdoption | None] = ContextVar(
    "native_settled_draft_recovery", default=None
)


@contextmanager
def _native_settled_draft_scope(
    selected: NativeSettledDraftRecovery, reopen: Callable[[], LLMProducerSettlement]
) -> Iterator[None]:
    adoption = _DraftAdoption(selected, reopen)
    token = _ACTIVE.set(adoption)
    try:
        yield
        if not adoption.consumed:
            raise ValueError("native_settled_draft_not_consumed")
    finally:
        _ACTIVE.reset(token)


def _adopt_settled_draft(
    client: object,
    kwargs: dict[str, Any],
    producer_context: Mapping[str, Any] | None,
) -> LLMSettledResponse | None:
    """Match the prepared N4 request before handing the draft bytes to its parser."""
    adoption = _ACTIVE.get()
    if adoption is None:
        return None
    if producer_context is None:
        raise ValueError("native_settled_draft_producer_context_missing")
    from polisyos.core.llm.settlement import LLMSettledResponse
    from polisyos.core.llm.traced_client import TracedLLMClient
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse

    with adoption.lock:
        if producer_context["stage"] != "draft":
            if adoption.consumed:
                return None
            raise ValueError("native_settled_draft_stage_not_consumed")
        if adoption.consumed:
            raise ValueError("native_settled_draft_already_consumed")
        settlement = adoption.reopen()
        event = settlement.event
        if (
            type(client) is not TracedLLMClient
            or client._cache_settlement_hooks
            or producer_context["instance"] != "draft_policy"
            or producer_context["attempt"] != 0
            or producer_context["model_id"] != event.model
            or producer_context["preparation"]["kind"] != "identity"
            or client._request_digest((), kwargs) != event.request_digest
        ):
            raise ValueError("native_settled_draft_current_request_mismatch")
        adoption.consumed = True
    # Usage counters are outside the historical ledger content seal. Retain
    # their unknown state while carrying the original committed event exactly.
    response = GatewayLLMResponse(content=adoption.selected.response_text, model=event.model)
    return LLMSettledResponse(response, settlement)
