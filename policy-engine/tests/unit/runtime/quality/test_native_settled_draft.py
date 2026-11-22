from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from polisyos.core.llm.settlement import LLMProducerEvent, LLMProducerSettlement
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.runtime.quality.design_generation import RecordingLLMClient
from polisyos.runtime.quality.native_settled_draft import (
    NativeSettledDraftRecovery,
    _native_settled_draft_scope,
    _verify_settled_draft,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerInvocationReservation,
    BudgetLedgerMutation,
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerReentryBudgetScope,
    BudgetLedgerReentryBudgetWindow,
    BudgetLedgerSnapshot,
    BudgetLedgerSpendReceipt,
    BudgetLedgerWriter,
)

_MODEL = "controlled-model"
_BODY = '{"draft_id":"selected-settled-draft","confidence":0.8}'
_HASH = "a" * 64
_REF = "sha256:" + _HASH
_EVENT_ID = "llm-provider:" + "a" * 32
_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class _Cut:
    selected: NativeSettledDraftRecovery
    snapshot: BudgetLedgerSnapshot
    window: BudgetLedgerReentryBudgetWindow
    event: LLMProducerEvent

    def verify(self) -> LLMProducerSettlement:
        return _verify_settled_draft(
            self.selected,
            snapshot=self.snapshot,
            window=self.window,
            source_attempt=1,
            failed_lease_started_at=_BEFORE,
            failed_at=_BEFORE + timedelta(minutes=2),
        )


def _make_cut(request_digest: str) -> _Cut:
    binding = BudgetLedgerProducerRunBinding(
        run_id="run", tenant_id="tenant", cell_id="cell", profile_id="dev", control_job_id="source"
    )
    window = BudgetLedgerReentryBudgetWindow(
        scope=BudgetLedgerReentryBudgetScope(
            run_binding=binding,
            action_job_id="action",
            route_id=_REF,
            action_generation=3,
            action_phase_ref=_REF,
            source_payload_ref=_REF,
            profile_selection_ref=_REF,
        ),
        ledger_id="ledger",
        resource_identity=(1, 2, "budget.json.lock", 3, 4),
        fresh_limit_usd=Decimal("0.50"),
        global_limit_usd=Decimal("2.00"),
        baseline_total_usd=Decimal("0.70"),
        baseline_revision=15,
        baseline_prefix_digest=_HASH,
        revision=16,
    )
    event = LLMProducerEvent(
        event_id=_EVENT_ID,
        request_digest=request_digest,
        response_digest=hashlib.sha256(_BODY.encode()).hexdigest(),
        model=_MODEL,
        provider="gateway",
        amount=Decimal("0.12903"),
        cost_origin="estimated",
    )
    shared = {
        "event_id": event.event_id,
        "payload_digest": event.payload_digest,
        "key": "nl-run:run",
        "amount": event.amount,
        "provider": event.provider,
        "revision": 18,
        "committed_at": _BEFORE + timedelta(minutes=1),
    }
    writer = BudgetLedgerWriter(host_id="host", writer_id="writer", pid=12)
    snapshot = BudgetLedgerSnapshot(
        ledger_id="ledger",
        revision=18,
        recent_mutations=[
            BudgetLedgerMutation(
                revision=17,
                operation="begin_producer_event",
                key="nl-run:run",
                provider=event.provider,
                writer=writer,
                committed_at=_BEFORE + timedelta(seconds=15),
            ),
            BudgetLedgerMutation(
                revision=18,
                operation="settle_producer_event",
                key="nl-run:run",
                provider=event.provider,
                amount=event.amount,
                applied_amount=event.amount,
                writer=writer,
                committed_at=_BEFORE + timedelta(seconds=75),
            ),
        ],
        spend_receipts={_EVENT_ID: BudgetLedgerSpendReceipt(**shared)},
        producer_settlements={
            _EVENT_ID: BudgetLedgerProducerRecord(
                **shared,
                request_digest=event.request_digest,
                model=event.model,
                cost_origin=event.cost_origin,
                status="committed",
                run_binding=binding,
                control_job_attempt=1,
            )
        },
        reentry_budget_windows={window.window_id: window},
    )
    selected = NativeSettledDraftRecovery(
        producer_event_id=_EVENT_ID, ledger_revision=18, response_text=_BODY
    )
    return _Cut(selected, snapshot, window, event)


class _NoDraftTransport:
    async def generate(self, **_):
        pytest.fail("settled draft adoption must make no provider call")


@pytest.mark.asyncio
@pytest.mark.parametrize("substitute_current_prompt", [False, True])
async def test_actual_recorder_adopts_an_exact_settled_draft_once(
    substitute_current_prompt: bool,
) -> None:
    traced = TracedLLMClient(_NoDraftTransport(), model_name=_MODEL)
    recorder = RecordingLLMClient(traced, model_id=_MODEL, producer_problem_ref=_REF)

    def request(user: str = "original draft request") -> dict:
        return recorder._issue_producer_request(
            stage="draft",
            instance="draft_policy",
            attempt=0,
            request={"system": "system", "user": user, "response_format": {"type": "json_object"}},
        )

    exact = request()
    digest = traced._request_digest(
        (), {name: value for name, value in exact.items() if not name.startswith("_")}
    )
    cut = _make_cut(digest)
    with _native_settled_draft_scope(cut.selected, cut.verify):
        if substitute_current_prompt:
            with pytest.raises(ValueError, match="native_settled_draft_current_request_mismatch"):
                await recorder.generate(**request("substituted draft request"))
        reused = await recorder.generate(**exact)
        assert reused.content == _BODY
        assert reused.settlement.event == cut.event
        assert reused.usage.usage_status == "missing"
        assert recorder.calls[-1].historical_settlement_event_id == _EVENT_ID
        with pytest.raises(ValueError, match="native_settled_draft_already_consumed"):
            await recorder.generate(**request())


def test_adoption_rejects_changed_bytes_removed_spend_or_prior_physical_work() -> None:
    cut = _make_cut(_HASH)
    assert cut.verify().event == cut.event
    with pytest.raises(ValueError, match="native_settled_draft_response_mismatch"):
        _Cut(
            cut.selected.model_copy(update={"response_text": _BODY + " "}),
            cut.snapshot,
            cut.window,
            cut.event,
        ).verify()
    with pytest.raises(ValueError, match="native_settled_draft_ledger_cut_mismatch"):
        _Cut(
            cut.selected,
            cut.snapshot.model_copy(update={"spend_receipts": {}}),
            cut.window,
            cut.event,
        ).verify()


def test_adoption_rejects_begin_before_failed_lease_even_when_settlement_is_inside() -> None:
    cut = _make_cut(_HASH)
    begin, settle = cut.snapshot.recent_mutations
    altered = cut.snapshot.model_copy(
        update={
            "recent_mutations": [
                begin.model_copy(update={"committed_at": _BEFORE - timedelta(seconds=1)}),
                settle,
            ]
        }
    )
    with pytest.raises(ValueError, match="native_settled_draft_begin_or_settlement_mismatch"):
        replace(cut, snapshot=altered).verify()
    reservation = BudgetLedgerInvocationReservation(
        operation_id=_HASH,
        request_digest=_HASH,
        run_id="run",
        profile_digest=_HASH,
        purpose="standard",
        revision=17,
    )
    with pytest.raises(ValueError, match="native_settled_draft_ledger_cut_mismatch"):
        _Cut(
            cut.selected,
            cut.snapshot.model_copy(update={"invocation_reservations": {_HASH: reservation}}),
            cut.window,
            cut.event,
        ).verify()
