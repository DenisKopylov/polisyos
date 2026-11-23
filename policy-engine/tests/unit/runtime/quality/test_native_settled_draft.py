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
    NativeSettledN4Occurrence,
    NativeSettledN4Recovery,
    _adopt_settled_draft,
    _native_settled_draft_scope,
    _native_settled_n4_scope,
    _verify_settled_draft,
    _verify_settled_n4_recovery,
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
    _reentry_prefix,
)

_MODEL = "controlled-model"
_BODY = '{"draft_id":"selected-settled-draft","confidence":0.8}'
_HASH = "a" * 64
_REF = "sha256:" + _HASH
_EVENT_ID = "llm-provider:" + "a" * 32
_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
_N4_BODY = '{"pass":"paid-pass-result"}'
_ACTION_START = _BEFORE + timedelta(minutes=3)
_ACTION_END = _BEFORE + timedelta(minutes=9)


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


@dataclass(frozen=True)
class _N4Cut:
    selected: NativeSettledN4Recovery
    snapshot: BudgetLedgerSnapshot
    window: BudgetLedgerReentryBudgetWindow

    def verify(self):
        return _verify_settled_n4_recovery(
            self.selected,
            snapshot=self.snapshot,
            window=self.window,
            source_attempt=1,
            source_lease_started_at=_BEFORE,
            source_failed_at=_BEFORE + timedelta(minutes=2),
            action_lease_started_at=_ACTION_START,
            action_lease_expires_at=_ACTION_END,
        )


def _make_n4_cut() -> _N4Cut:
    binding = BudgetLedgerProducerRunBinding(
        run_id="run",
        tenant_id="tenant",
        cell_id="cell",
        profile_id="dev",
        control_job_id="source",
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
    writer = BudgetLedgerWriter(host_id="host", writer_id="writer", pid=12)

    def add_event(
        *,
        event_id: str,
        request_digest: str,
        response_text: str,
        revision: int,
        committed_at: datetime,
        amount: Decimal,
    ) -> tuple[BudgetLedgerProducerRecord, BudgetLedgerSpendReceipt]:
        event = LLMProducerEvent(
            event_id=event_id,
            request_digest=request_digest,
            response_digest=hashlib.sha256(response_text.encode()).hexdigest(),
            model=_MODEL,
            provider="gateway",
            amount=amount,
            cost_origin="estimated",
        )
        shared = {
            "event_id": event.event_id,
            "payload_digest": event.payload_digest,
            "key": "nl-run:run",
            "amount": amount,
            "provider": "gateway",
            "revision": revision,
            "committed_at": committed_at,
        }
        return (
            BudgetLedgerProducerRecord(
                **shared,
                request_digest=event.request_digest,
                model=event.model,
                cost_origin=event.cost_origin,
                status="committed",
                run_binding=binding,
                control_job_attempt=1,
            ),
            BudgetLedgerSpendReceipt(**shared),
        )

    baseline, baseline_spend = add_event(
        event_id="llm-provider:" + "b" * 32,
        request_digest="1" * 64,
        response_text="baseline",
        revision=16,
        committed_at=_BEFORE - timedelta(seconds=5),
        amount=Decimal("0.70"),
    )
    prefix_snapshot = BudgetLedgerSnapshot(
        ledger_id="ledger",
        revision=30,
        producer_settlements={baseline.event_id: baseline},
        spend_receipts={baseline_spend.event_id: baseline_spend},
    )
    baseline_total, baseline_digest = _reentry_prefix(prefix_snapshot, binding, cutoff=16)
    window = window.model_copy(
        update={
            "baseline_total_usd": baseline_total,
            "baseline_prefix_digest": baseline_digest,
        }
    )

    draft, draft_spend = add_event(
        event_id=_EVENT_ID,
        request_digest="2" * 64,
        response_text=_BODY,
        revision=18,
        committed_at=_BEFORE + timedelta(seconds=20),
        amount=Decimal("0.12903"),
    )
    records = [baseline, draft]
    spends = [baseline_spend, draft_spend]
    mutations = [
        BudgetLedgerMutation(
            revision=17,
            operation="begin_producer_event",
            key=draft.key,
            provider=draft.provider,
            writer=writer,
            committed_at=_BEFORE + timedelta(seconds=15),
        ),
        BudgetLedgerMutation(
            revision=18,
            operation="settle_producer_event",
            key=draft.key,
            provider=draft.provider,
            amount=draft.amount,
            applied_amount=draft.amount,
            writer=writer,
            committed_at=_BEFORE + timedelta(seconds=30),
        ),
    ]
    event_ids = ["llm-provider:" + str(index) * 32 for index in range(1, 7)]
    request_digests = [
        hashlib.sha256(f"request-{index}".encode()).hexdigest() for index in range(6)
    ]
    occurrence_specs = (
        ("side_effects_check", event_ids[0], request_digests[0], "4" * 64, 20),
        ("constraint_verify", event_ids[3], request_digests[3], "7" * 64, 26),
    )
    occurrences = tuple(
        NativeSettledN4Occurrence(
            producer_event_id=event_id,
            stage="drafter_multipass",
            instance=instance,
            ordinal=0,
            context_id=context_id,
            request_digest=request_digest,
            response_text=_N4_BODY,
        )
        for instance, event_id, request_digest, context_id, _revision in occurrence_specs
    )
    for index, (event_id, request_digest) in enumerate(
        zip(event_ids, request_digests, strict=True)
    ):
        revision = 20 + index * 2
        started_at = _ACTION_START + timedelta(seconds=index * 20)
        record, spend = add_event(
            event_id=event_id,
            request_digest=request_digest,
            response_text=_N4_BODY,
            revision=revision,
            committed_at=started_at + timedelta(seconds=1),
            amount=Decimal("0.0016"),
        )
        records.append(record)
        spends.append(spend)
        mutations.extend(
            (
                BudgetLedgerMutation(
                    revision=revision - 1,
                    operation="begin_producer_event",
                    key=record.key,
                    provider=record.provider,
                    writer=writer,
                    committed_at=started_at,
                ),
                BudgetLedgerMutation(
                    revision=revision,
                    operation="settle_producer_event",
                    key=record.key,
                    provider=record.provider,
                    amount=record.amount,
                    applied_amount=record.amount,
                    writer=writer,
                    committed_at=started_at + timedelta(seconds=3),
                ),
            )
        )

    selected = NativeSettledN4Recovery(
        prior_recovery_event_id=31,
        prior_recovery_event_sha256="sha256:" + "f" * 64,
        ledger_revision=30,
        draft=NativeSettledDraftRecovery(
            producer_event_id=_EVENT_ID,
            ledger_revision=18,
            response_text=_BODY,
        ),
        occurrences=occurrences,
    )
    snapshot = BudgetLedgerSnapshot(
        ledger_id="ledger",
        revision=30,
        recent_mutations=mutations,
        producer_settlements={record.event_id: record for record in records},
        spend_receipts={spend.event_id: spend for spend in spends},
        reentry_budget_windows={window.window_id: window},
    )
    return _N4Cut(selected, snapshot, window)


def _bind_n4_cut_to_live_requests(
    cut: _N4Cut,
    *,
    draft_digest: str,
    occurrence_requests: tuple[tuple[NativeSettledN4Occurrence, str], ...],
    extra_accounted_request: tuple[str, str] | None = None,
) -> _N4Cut:
    records = dict(cut.snapshot.producer_settlements)
    spends = dict(cut.snapshot.spend_receipts)

    def bind(event_id: str, request_digest: str, body: str) -> None:
        record = records[event_id]
        event = LLMProducerEvent(
            event_id=record.event_id,
            request_digest=request_digest,
            response_digest=hashlib.sha256(body.encode()).hexdigest(),
            model=record.model,
            provider=record.provider,
            amount=record.amount,
            cost_origin=record.cost_origin,
        )
        records[event_id] = record.model_copy(
            update={"request_digest": request_digest, "payload_digest": event.payload_digest}
        )
        spends[event_id] = spends[event_id].model_copy(
            update={"payload_digest": event.payload_digest}
        )

    bind(cut.selected.draft.producer_event_id, draft_digest, cut.selected.draft.response_text)
    bound_occurrences = []
    for occurrence, request_digest in occurrence_requests:
        bind(occurrence.producer_event_id, request_digest, occurrence.response_text)
        bound_occurrences.append(occurrence.model_copy(update={"request_digest": request_digest}))
    if extra_accounted_request is not None:
        event_id, request_digest = extra_accounted_request
        bind(event_id, request_digest, _N4_BODY)
    selected = cut.selected.model_copy(update={"occurrences": tuple(bound_occurrences)})
    return _N4Cut(
        selected,
        cut.snapshot.model_copy(update={"producer_settlements": records, "spend_receipts": spends}),
        cut.window,
    )


def _issued_n4_request(
    recorder: RecordingLLMClient,
    traced: TracedLLMClient,
    *,
    stage: str,
    instance: str,
    attempt: int,
    user: str,
) -> tuple[dict, dict, str]:
    request = recorder._issue_producer_request(
        stage=stage,
        instance=instance,
        attempt=attempt,
        request={
            "system": f"system:{stage}:{instance}",
            "user": user,
            "response_format": {"type": "json_object"},
        },
    )
    prepared = {name: value for name, value in request.items() if not name.startswith("_")}
    context = prepared["metadata"]["polisyos_producer_request"]
    return request, context, traced._request_digest((), prepared)


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


def test_n4_recovery_verifies_append_only_window_and_keeps_all_paid_events_accounted() -> None:
    cut = _make_n4_cut()
    proof = cut.verify()

    assert proof.selection == cut.selected
    assert proof.draft_settlement.event.event_id == _EVENT_ID
    assert tuple(item.selection.instance for item in proof.occurrences) == (
        "side_effects_check",
        "constraint_verify",
    )
    assert tuple(item.settlement.event.event_id for item in proof.occurrences) == (
        cut.selected.occurrences[0].producer_event_id,
        cut.selected.occurrences[1].producer_event_id,
    )
    assert proof.accounted_producer_event_ids == (
        _EVENT_ID,
        *("llm-provider:" + str(index) * 32 for index in range(1, 7)),
    )
    settlements = (proof.draft_settlement, *(item.settlement for item in proof.occurrences))
    assert all(
        item.ack.durability == "ledger" and item.ack.status == "committed" for item in settlements
    )


def test_n4_recovery_rejects_an_incomplete_mutation_window_or_changed_paid_request() -> None:
    cut = _make_n4_cut()
    with pytest.raises(ValueError, match="native_settled_n4_mutation_sequence_mismatch"):
        replace(
            cut,
            snapshot=cut.snapshot.model_copy(
                update={
                    "recent_mutations": [
                        item for item in cut.snapshot.recent_mutations if item.revision != 25
                    ]
                }
            ),
        ).verify()

    selected_occurrence = cut.selected.occurrences[0].model_copy(
        update={"request_digest": "e" * 64}
    )
    changed_selection = cut.selected.model_copy(
        update={"occurrences": (selected_occurrence, *cut.selected.occurrences[1:])}
    )
    with pytest.raises(ValueError, match="native_settled_n4_occurrence_selection_mismatch"):
        replace(cut, selected=changed_selection).verify()

    changed_bytes = cut.selected.occurrences[0].model_copy(update={"response_text": _N4_BODY + " "})
    changed_selection = cut.selected.model_copy(
        update={"occurrences": (changed_bytes, *cut.selected.occurrences[1:])}
    )
    with pytest.raises(ValueError, match="native_settled_n4_response_mismatch"):
        replace(cut, selected=changed_selection).verify()


def test_n4_recovery_rejects_changed_baseline_unknown_settlement_and_open_n5_reservation() -> None:
    cut = _make_n4_cut()
    baseline_record = cut.snapshot.producer_settlements["llm-provider:" + "b" * 32]
    altered_baseline = cut.snapshot.model_copy(
        update={
            "producer_settlements": {
                **cut.snapshot.producer_settlements,
                baseline_record.event_id: baseline_record.model_copy(
                    update={"amount": Decimal("0.71")}
                ),
            }
        }
    )
    with pytest.raises(ValueError, match="native_settled_n4_baseline_prefix_mismatch"):
        replace(cut, snapshot=altered_baseline).verify()

    event_id = cut.selected.occurrences[0].producer_event_id
    paid_record = cut.snapshot.producer_settlements[event_id]
    unknown_record = paid_record.model_copy(update={"status": "unknown"})
    unknown_snapshot = cut.snapshot.model_copy(
        update={
            "producer_settlements": {
                **cut.snapshot.producer_settlements,
                event_id: unknown_record,
            }
        }
    )
    with pytest.raises(ValueError, match="native_settled_n4_producer_outcome_mismatch"):
        replace(cut, snapshot=unknown_snapshot).verify()

    reservation = BudgetLedgerInvocationReservation(
        operation_id=_HASH,
        request_digest=_HASH,
        run_id="run",
        profile_digest=_HASH,
        purpose="standard",
        revision=19,
    )
    with pytest.raises(ValueError, match="native_settled_n4_open_or_physical_reservation"):
        replace(
            cut,
            snapshot=cut.snapshot.model_copy(
                update={"invocation_reservations": {_HASH: reservation}}
            ),
        ).verify()


def test_n4_recovery_rejects_provider_effects_outside_their_own_lease_interval() -> None:
    cut = _make_n4_cut()
    action_begin = next(item for item in cut.snapshot.recent_mutations if item.revision == 19)
    altered = cut.snapshot.model_copy(
        update={
            "recent_mutations": [
                item.model_copy(update={"committed_at": _BEFORE + timedelta(minutes=2, seconds=59)})
                if item is action_begin
                else item
                for item in cut.snapshot.recent_mutations
            ]
        }
    )
    with pytest.raises(ValueError, match="native_settled_n4_mutation_time_outside_lease"):
        replace(cut, snapshot=altered).verify()


def test_n4_recovery_selector_is_strict_and_rejects_duplicate_or_wrong_ordinal_items() -> None:
    cut = _make_n4_cut()
    with pytest.raises(ValueError, match="native_settled_n4_occurrence_ordinal_not_selected"):
        NativeSettledN4Occurrence(
            **{
                **cut.selected.occurrences[0].model_dump(),
                "ordinal": 1,
            }
        )
    with pytest.raises(ValueError, match="native_settled_n4_occurrence_selection_invalid"):
        NativeSettledN4Recovery.model_validate(
            {
                **cut.selected.model_dump(),
                "occurrences": [
                    cut.selected.occurrences[0].model_dump(),
                    cut.selected.occurrences[0].model_dump(),
                ],
            }
        )


@pytest.mark.asyncio
async def test_native_recorder_consumes_draft_and_two_paid_n4_calls_once_then_fences_old_digests() -> (
    None
):
    traced = TracedLLMClient(_NoDraftTransport(), model_name=_MODEL)
    recorder = RecordingLLMClient(traced, model_id=_MODEL, producer_problem_ref=_REF)
    draft_request, _draft_context, draft_digest = _issued_n4_request(
        recorder,
        traced,
        stage="draft",
        instance="draft_policy",
        attempt=0,
        user="original settled draft request",
    )
    side_request, side_context, side_digest = _issued_n4_request(
        recorder,
        traced,
        stage="drafter_multipass",
        instance="side_effects_check",
        attempt=0,
        user="paid side effects request",
    )
    constraint_request, constraint_context, constraint_digest = _issued_n4_request(
        recorder,
        traced,
        stage="drafter_multipass",
        instance="constraint_verify",
        attempt=0,
        user="paid constraint request",
    )
    formalizer_request, _formalizer_context, formalizer_digest = _issued_n4_request(
        recorder,
        traced,
        stage="formalizer",
        instance="formalize",
        attempt=0,
        user="new formalizer request",
    )
    base = _make_n4_cut()
    side_selection = base.selected.occurrences[0].model_copy(
        update={"context_id": side_context["context_id"]}
    )
    constraint_selection = base.selected.occurrences[1].model_copy(
        update={"context_id": constraint_context["context_id"]}
    )
    duplicate_digest_event = "llm-provider:" + "2" * 32
    cut = _bind_n4_cut_to_live_requests(
        base,
        draft_digest=draft_digest,
        occurrence_requests=(
            (side_selection, side_digest),
            (constraint_selection, constraint_digest),
        ),
        extra_accounted_request=(duplicate_digest_event, formalizer_digest),
    )
    reopen_count = 0

    def reopen():
        nonlocal reopen_count
        reopen_count += 1
        return cut.verify()

    with _native_settled_n4_scope(cut.selected, reopen):
        draft = await recorder.generate(**draft_request)
        assert draft.content == _BODY
        side = await recorder.generate(**side_request)
        assert side.content == _N4_BODY
        repeated_side_request, _, _ = _issued_n4_request(
            recorder,
            traced,
            stage="drafter_multipass",
            instance="side_effects_check",
            attempt=0,
            user="paid side effects request",
        )
        with pytest.raises(ValueError, match="native_settled_n4_occurrence_not_next"):
            await recorder.generate(**repeated_side_request)
        constraint = await recorder.generate(**constraint_request)
        assert constraint.content == _N4_BODY
        replay_after_selection, _, _ = _issued_n4_request(
            recorder,
            traced,
            stage="drafter_multipass",
            instance="side_effects_check",
            attempt=0,
            user="paid side effects request",
        )
        with pytest.raises(ValueError, match="native_settled_n4_paid_stage_replayed_or_unselected"):
            await recorder.generate(**replay_after_selection)
        with pytest.raises(ValueError, match="native_settled_n4_paid_request_digest_replayed"):
            await recorder.generate(**formalizer_request)

    assert [call.status for call in recorder.calls] == [
        "success",
        "success",
        "error",
        "success",
        "error",
        "error",
    ]
    assert recorder._managed_call_indices == set()
    assert reopen_count == 3


@pytest.mark.asyncio
async def test_native_n4_scope_allows_new_managed_consolidation_after_selected_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.design_generation import _PREPARED_INPUT_KEY
    from polisyos.scientist.orchestration.llm._n4_request import _binding_scope

    traced = TracedLLMClient(_NoDraftTransport(), model_name=_MODEL)
    managed_transport = object()
    monkeypatch.setattr(
        traced,
        "_managed_direct_transport",
        lambda _prepared=None: managed_transport,
    )
    recorder = RecordingLLMClient(traced, model_id=_MODEL, producer_problem_ref=_REF)
    draft_request, _draft_context, draft_digest = _issued_n4_request(
        recorder,
        traced,
        stage="draft",
        instance="draft_policy",
        attempt=0,
        user="original settled draft request",
    )
    side_request, side_context, side_digest = _issued_n4_request(
        recorder,
        traced,
        stage="drafter_multipass",
        instance="side_effects_check",
        attempt=0,
        user="paid side effects request",
    )
    constraint_request, constraint_context, constraint_digest = _issued_n4_request(
        recorder,
        traced,
        stage="drafter_multipass",
        instance="constraint_verify",
        attempt=0,
        user="paid constraint request",
    )
    base = _make_n4_cut()
    cut = _bind_n4_cut_to_live_requests(
        base,
        draft_digest=draft_digest,
        occurrence_requests=(
            (
                base.selected.occurrences[0].model_copy(
                    update={"context_id": side_context["context_id"]}
                ),
                side_digest,
            ),
            (
                base.selected.occurrences[1].model_copy(
                    update={"context_id": constraint_context["context_id"]}
                ),
                constraint_digest,
            ),
        ),
    )
    proof = cut.verify()

    with _native_settled_n4_scope(cut.selected, lambda: proof):
        assert (await recorder.generate(**draft_request)).content == _BODY
        assert (await recorder.generate(**side_request)).content == _N4_BODY
        assert (await recorder.generate(**constraint_request)).content == _N4_BODY

        consolidation, context, _ = _issued_n4_request(
            recorder,
            traced,
            stage="drafter_consolidation",
            instance="consolidation",
            attempt=0,
            user="new consolidation request",
        )
        prepared = consolidation.pop(_PREPARED_INPUT_KEY)
        kwargs = {name: value for name, value in consolidation.items() if not name.startswith("_")}
        with (
            _binding_scope(recorder._producer_request_binding, context, kwargs),
            traced.prepared_producer_input(prepared, kwargs),
        ):
            assert _adopt_settled_draft(traced, kwargs, context) is None
