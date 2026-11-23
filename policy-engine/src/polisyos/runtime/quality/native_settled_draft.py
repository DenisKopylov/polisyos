"""Adopt one exact settled draft under a current Native recovery lease."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from datetime import datetime

    from polisyos.core.llm.settlement import LLMProducerSettlement, LLMSettledResponse
    from polisyos.runtime.quality.design_generation import LLMGenerationCall
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRecord,
        BudgetLedgerReentryBudgetWindow,
        BudgetLedgerSnapshot,
        BudgetLedgerSpendReceipt,
    )


class NativeSettledDraftRecovery(BaseModel):
    """Candidate bytes and exact ledger pins supplied with the new approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_event_id: str = Field(pattern=r"^llm-provider:[a-f0-9]{32}$")
    ledger_revision: int = Field(ge=1, strict=True)
    response_text: str = Field(min_length=1, max_length=131_072, repr=False)


class NativeSettledN4Occurrence(BaseModel):
    """One selected, already-paid N4 multipass result and its prepared request identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_event_id: str = Field(pattern=r"^llm-provider:[a-f0-9]{32}$")
    stage: Literal["drafter_multipass"]
    instance: Literal["side_effects_check", "constraint_verify"]
    ordinal: int = Field(ge=0, le=2, strict=True)
    context_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_text: str = Field(min_length=1, max_length=131_072, repr=False)

    @model_validator(mode="after")
    def _require_selected_initial_pass(self) -> NativeSettledN4Occurrence:
        if self.ordinal != 0:
            raise ValueError("native_settled_n4_occurrence_ordinal_not_selected")
        return self


class NativeSettledN4Recovery(BaseModel):
    """Exact post-stop ledger cut and the two paid N4 outputs to adopt once."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prior_recovery_event_id: int = Field(gt=0, strict=True)
    prior_recovery_event_sha256: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    ledger_revision: int = Field(ge=1, strict=True)
    draft: NativeSettledDraftRecovery
    occurrences: tuple[NativeSettledN4Occurrence, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _require_exact_selected_occurrences(self) -> NativeSettledN4Recovery:
        identities = tuple((item.stage, item.instance, item.ordinal) for item in self.occurrences)
        if identities != (
            ("drafter_multipass", "side_effects_check", 0),
            ("drafter_multipass", "constraint_verify", 0),
        ):
            raise ValueError("native_settled_n4_occurrence_selection_invalid")
        event_ids = tuple(item.producer_event_id for item in self.occurrences)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("native_settled_n4_occurrence_event_duplicate")
        if self.ledger_revision <= self.draft.ledger_revision:
            raise ValueError("native_settled_n4_ledger_cut_precedes_draft")
        return self


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


@dataclass(frozen=True, slots=True)
class VerifiedNativeSettledN4Occurrence:
    """One currently verified N4 selection and its exact committed settlement."""

    selection: NativeSettledN4Occurrence
    settlement: LLMProducerSettlement


@dataclass(frozen=True, slots=True)
class VerifiedNativeSettledN4Recovery:
    """Ledger-derived proof for the original draft and selected paid N4 outputs."""

    selection: NativeSettledN4Recovery
    draft_settlement: LLMProducerSettlement
    occurrences: tuple[VerifiedNativeSettledN4Occurrence, ...]
    accounted_producer_event_ids: tuple[str, ...]
    accounted_request_digests: tuple[str, ...]
    baseline_paid_records: tuple[BudgetLedgerProducerRecord, ...]


def _verify_settled_n4_recovery(
    selected: NativeSettledN4Recovery,
    *,
    snapshot: BudgetLedgerSnapshot,
    window: BudgetLedgerReentryBudgetWindow,
    source_attempt: int,
    source_lease_started_at: datetime,
    source_failed_at: datetime,
    action_lease_started_at: datetime,
    action_lease_expires_at: datetime,
) -> VerifiedNativeSettledN4Recovery:
    """Verify the complete append-only paid-B ledger window before reusing N4 bytes.

    The producer attempt remains the original source attempt. The later Native
    action lease supplies the separate time interval for its six charged N4
    retries; this verifier makes no claim about external N5 execution.
    """
    from polisyos.scientist.orchestration.engine.budget_ledger import _reentry_prefix

    binding = window.scope.run_binding
    key = f"nl-run:{binding.run_id}"
    ledger_revision = selected.ledger_revision
    expected_settlement_revisions = tuple(range(window.revision + 2, ledger_revision + 1, 2))
    expected_mutation_revisions = tuple(range(window.revision + 1, ledger_revision + 1))
    timestamps = (
        source_lease_started_at,
        source_failed_at,
        action_lease_started_at,
        action_lease_expires_at,
    )
    if (
        any(value.tzinfo is None or value.utcoffset() is None for value in timestamps)
        or source_lease_started_at > source_failed_at
        or source_failed_at > action_lease_started_at
        or action_lease_started_at > action_lease_expires_at
    ):
        raise ValueError("native_settled_n4_lease_interval_invalid")
    if (
        snapshot.revision != ledger_revision
        or snapshot.ledger_id != window.ledger_id
        or snapshot.reentry_budget_windows.get(window.window_id) != window
        or selected.draft.ledger_revision != window.revision + 2
        or ledger_revision - window.revision < 6
        or (ledger_revision - window.revision) % 2 != 0
        or not (source_lease_started_at <= source_failed_at)
    ):
        raise ValueError("native_settled_n4_ledger_cut_mismatch")

    try:
        baseline_total, baseline_prefix_digest = _reentry_prefix(
            snapshot, binding, cutoff=window.revision
        )
    except ValueError as exc:
        raise ValueError("native_settled_n4_baseline_prefix_mismatch") from exc
    if (baseline_total, baseline_prefix_digest) != (
        window.baseline_total_usd,
        window.baseline_prefix_digest,
    ):
        raise ValueError("native_settled_n4_baseline_prefix_mismatch")
    mutations = tuple(snapshot.recent_mutations)
    mutation_revisions = tuple(item.revision for item in mutations)
    selected_mutations = tuple(item for item in mutations if item.revision > window.revision)
    if (
        len(set(mutation_revisions)) != len(mutation_revisions)
        or tuple(item.revision for item in selected_mutations) != expected_mutation_revisions
        or any(item.revision > ledger_revision for item in mutations)
    ):
        raise ValueError("native_settled_n4_mutation_sequence_mismatch")

    record_entries = tuple(
        sorted(
            (
                (event_id, record)
                for event_id, record in snapshot.producer_settlements.items()
                if record.revision > window.revision
            ),
            key=lambda entry: entry[1].revision,
        )
    )
    records = tuple(record for _event_id, record in record_entries)
    if (
        any(event_id != record.event_id for event_id, record in record_entries)
        or tuple(record.revision for record in records) != expected_settlement_revisions
        or len({record.event_id for record in records}) != len(records)
        or len({record.revision for record in records}) != len(records)
        or len({record.request_digest for record in records}) != len(records)
        or any(
            record.key != key
            or record.run_binding != binding
            or record.control_job_attempt != source_attempt
            or record.status != "committed"
            or record.amount is None
            or not record.amount.is_finite()
            or record.amount < 0
            or record.cost_origin not in {"estimated", "reported"}
            or record.payload_digest is None
            or record.origin_event_id is not None
            or record.reuse_admission is not None
            for record in records
        )
    ):
        raise ValueError("native_settled_n4_producer_outcome_mismatch")

    try:
        current_total, _ = _reentry_prefix(snapshot, binding, cutoff=None)
    except ValueError as exc:
        raise ValueError("native_settled_n4_current_total_not_established") from exc
    if current_total > window.effective_limit_usd:
        raise ValueError("native_settled_n4_budget_window_exceeded")

    spend_entries = tuple(
        sorted(
            (
                (event_id, receipt)
                for event_id, receipt in snapshot.spend_receipts.items()
                if receipt.revision > window.revision
            ),
            key=lambda entry: entry[1].revision,
        )
    )
    later_spends = tuple(receipt for _event_id, receipt in spend_entries)
    if tuple(receipt.event_id for receipt in later_spends) != tuple(
        record.event_id for record in records
    ) or any(event_id != receipt.event_id for event_id, receipt in spend_entries):
        raise ValueError("native_settled_n4_spend_set_mismatch")

    by_revision = {item.revision: item for item in selected_mutations}
    records_by_id = {item.event_id: item for item in records}
    spend_by_id = {item.event_id: item for item in later_spends}
    for record in records:
        begin = by_revision.get(record.revision - 1)
        settle = by_revision.get(record.revision)
        spend = spend_by_id.get(record.event_id)
        if begin is None or settle is None or spend is None:
            raise ValueError("native_settled_n4_mutation_pair_missing")
        if (
            (begin.operation, begin.revision, begin.key, begin.provider)
            != ("begin_producer_event", record.revision - 1, record.key, record.provider)
            or (settle.operation, settle.revision, settle.key, settle.provider)
            != ("settle_producer_event", record.revision, record.key, record.provider)
            or begin.writer != settle.writer
            or settle.amount != record.amount
            or settle.applied_amount != record.amount
            or (
                spend.event_id,
                spend.key,
                spend.provider,
                spend.amount,
                spend.revision,
                spend.payload_digest,
            )
            != (
                record.event_id,
                record.key,
                record.provider,
                record.amount,
                record.revision,
                record.payload_digest,
            )
        ):
            raise ValueError("native_settled_n4_mutation_pair_mismatch")
        started_at, ended_at = (
            (source_lease_started_at, source_failed_at)
            if record.revision == selected.draft.ledger_revision
            else (action_lease_started_at, action_lease_expires_at)
        )
        if not (
            started_at
            <= begin.committed_at
            <= record.committed_at
            <= spend.committed_at
            <= settle.committed_at
            <= ended_at
        ):
            raise ValueError("native_settled_n4_mutation_time_outside_lease")

    run_reserved = snapshot.state.reserved.get(key, Decimal(0))
    if (
        run_reserved != 0
        or any(
            item.run_id == binding.run_id
            and (item.revision > window.revision or item.status not in {"completed", "failed"})
            for item in snapshot.invocation_reservations.values()
        )
        or any(
            item.key == key and (item.revision > window.revision or item.status != "settled")
            for item in snapshot.compute_reservations.values()
        )
    ):
        raise ValueError("native_settled_n4_open_or_physical_reservation")

    draft_record = records_by_id.get(selected.draft.producer_event_id)
    if draft_record is None or draft_record.revision != selected.draft.ledger_revision:
        raise ValueError("native_settled_n4_draft_selection_mismatch")
    draft_settlement = _settled_n4_response(
        draft_record, spend_by_id[draft_record.event_id], selected.draft.response_text
    )
    selected_occurrences: list[VerifiedNativeSettledN4Occurrence] = []
    for occurrence in selected.occurrences:
        record = records_by_id.get(occurrence.producer_event_id)
        if record is None or record.request_digest != occurrence.request_digest:
            raise ValueError("native_settled_n4_occurrence_selection_mismatch")
        selected_occurrences.append(
            VerifiedNativeSettledN4Occurrence(
                occurrence,
                _settled_n4_response(
                    record, spend_by_id[record.event_id], occurrence.response_text
                ),
            )
        )

    return VerifiedNativeSettledN4Recovery(
        selection=selected,
        draft_settlement=draft_settlement,
        occurrences=tuple(selected_occurrences),
        accounted_producer_event_ids=tuple(record.event_id for record in records),
        accounted_request_digests=tuple(record.request_digest for record in records),
        baseline_paid_records=tuple(
            record
            for record in snapshot.producer_settlements.values()
            if record.revision <= window.revision
            and record.run_binding == binding
            and record.key == key
            and record.control_job_attempt == source_attempt
        ),
    )


def _settled_n4_response(
    record: BudgetLedgerProducerRecord,
    spend: BudgetLedgerSpendReceipt,
    response_text: str,
) -> LLMProducerSettlement:
    from polisyos.core.llm.settlement import (
        LLMProducerEvent,
        LLMProducerSettlement,
        LLMSettlementAck,
    )

    event = LLMProducerEvent(
        event_id=record.event_id,
        request_digest=record.request_digest,
        response_digest=hashlib.sha256(response_text.encode()).hexdigest(),
        model=record.model,
        provider=record.provider,
        amount=record.amount,
        cost_origin=record.cost_origin,
    )
    if (
        event.payload_digest != record.payload_digest
        or event.payload_digest != spend.payload_digest
    ):
        raise ValueError("native_settled_n4_response_mismatch")
    return LLMProducerSettlement(
        event,
        LLMSettlementAck(
            event.event_id, event.payload_digest, "committed", (event.event_id,), "ledger"
        ),
    )


def _verify_baseline_n4_response(
    record: BudgetLedgerProducerRecord,
    *,
    stage: str,
    snapshot: BudgetLedgerSnapshot,
    window: BudgetLedgerReentryBudgetWindow,
    begin: BudgetLedgerProducerRecord | None,
    calls: tuple[LLMGenerationCall, ...],
) -> LLMSettledResponse:
    """Reconcile one original producer receipt with its selected durable source bytes."""
    from polisyos.core.llm.settlement import LLMSettledResponse
    from polisyos.scientist.orchestration.engine.budget_ledger import _reentry_prefix
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse

    if (
        snapshot.ledger_id != window.ledger_id
        or snapshot.reentry_budget_windows.get(window.window_id) != window
        or record.revision > window.baseline_revision
        or record.run_binding != window.scope.run_binding
        or snapshot.producer_settlements.get(record.event_id) != record
        or _reentry_prefix(snapshot, window.scope.run_binding, cutoff=window.revision)
        != (window.baseline_total_usd, window.baseline_prefix_digest)
    ):
        raise ValueError("native_settled_n4_baseline_prefix_mismatch")
    spend = snapshot.spend_receipts.get(record.event_id)
    if (
        begin is None
        or spend is None
        or begin.status != "pending"
        or record.status != "committed"
        or record.cost_origin not in {"reported", "estimated"}
        or record.amount is None
        or record.control_job_attempt is None
        or not begin.revision < record.revision == spend.revision
        or not begin.committed_at <= record.committed_at <= spend.committed_at
        or (
            begin.event_id,
            begin.key,
            begin.model,
            begin.provider,
            begin.request_digest,
            begin.run_binding,
            begin.control_job_attempt,
        )
        != (
            record.event_id,
            record.key,
            record.model,
            record.provider,
            record.request_digest,
            record.run_binding,
            record.control_job_attempt,
        )
        or (spend.event_id, spend.key, spend.provider, spend.amount)
        != (record.event_id, record.key, record.provider, record.amount)
    ):
        raise ValueError("native_settled_n4_baseline_settlement_not_established")

    # Match the complete historical provider payload, not the caller's JSON
    # interpretation, a normalized response, or another occurrence's role.
    matched = None
    for call in calls:
        if (
            call.role_hint != stage
            or call.status != "success"
            or call.model_id != record.model
            or not call.raw_llm_response
        ):
            continue
        try:
            settlement = _settled_n4_response(record, spend, call.raw_llm_response)
        except ValueError:
            continue
        if matched is not None:
            raise ValueError("native_settled_n4_baseline_response_ambiguous")
        matched = LLMSettledResponse(
            GatewayLLMResponse(content=call.raw_llm_response, model=record.model), settlement
        )
    if matched is None:
        raise ValueError("native_settled_n4_baseline_response_not_established")
    return matched


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


@dataclass(slots=True)
class _N4Adoption:
    """One recovery lease that consumes the draft and two exact paid N4 passes."""

    selected: NativeSettledN4Recovery
    reopen: Callable[[], VerifiedNativeSettledN4Recovery]
    reopen_baseline: Callable[[BudgetLedgerProducerRecord, str], LLMSettledResponse] | None
    lock: Lock = field(default_factory=Lock)
    draft_consumed: bool = False
    occurrence_index: int = 0
    latest_proof: VerifiedNativeSettledN4Recovery | None = None
    baseline_adopted: set[str] = field(default_factory=set)


_N4_ACTIVE: ContextVar[_N4Adoption | None] = ContextVar("native_settled_n4_recovery", default=None)


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


@contextmanager
def _native_settled_n4_scope(
    selected: NativeSettledN4Recovery,
    reopen: Callable[[], VerifiedNativeSettledN4Recovery],
    *,
    reopen_baseline: Callable[[BudgetLedgerProducerRecord, str], LLMSettledResponse] | None = None,
) -> Iterator[None]:
    """Require one exact draft followed by both selected paid N4 occurrences."""
    if (
        type(selected) is not NativeSettledN4Recovery
        or not callable(reopen)
        or (reopen_baseline is not None and not callable(reopen_baseline))
    ):
        raise TypeError("native_settled_n4_scope_untyped")
    adoption = _N4Adoption(selected, reopen, reopen_baseline)
    token = _N4_ACTIVE.set(adoption)
    try:
        yield
        if not adoption.draft_consumed or adoption.occurrence_index != len(selected.occurrences):
            raise ValueError("native_settled_n4_recovery_not_consumed")
    finally:
        _N4_ACTIVE.reset(token)


def _native_n4_context_matches(
    client: object,
    kwargs: dict[str, Any],
    producer_context: Mapping[str, Any],
    *,
    stage: str,
    instance: str,
    ordinal: int,
    context_id: str | None,
    request_digest: str | None,
) -> bool:
    """Check the active prepared N4 request against a selected event identity."""
    from polisyos.core.llm.traced_client import TracedLLMClient

    if type(client) is not TracedLLMClient or client._cache_settlement_hooks:
        return False
    try:
        current_digest = client._request_digest((), kwargs)
    except (TypeError, ValueError):
        return False
    return (
        producer_context.get("stage") == stage
        and producer_context.get("instance") == instance
        and producer_context.get("attempt") == ordinal
        and (context_id is None or producer_context.get("context_id") == context_id)
        and (request_digest is None or current_digest == request_digest)
        and producer_context.get("model_id") is not None
    )


def _native_n4_managed_direct_call(client: object) -> bool:
    """Require the live Trace owner's actual managed prepared transport."""
    from polisyos.core.llm.traced_client import TracedLLMClient

    if type(client) is not TracedLLMClient:
        return False
    prepared_call = client._prepared_producer_call.get()
    prepared = getattr(prepared_call, "prepared", None)
    if prepared is None:
        return False
    transport = client._managed_direct_transport(prepared)
    return transport is not None and prepared._direct_transport is transport


def _adopt_settled_n4(
    client: object,
    kwargs: dict[str, Any],
    producer_context: Mapping[str, Any] | None,
) -> LLMSettledResponse | None:
    """Adopt selected settled N4 outputs or fence work that replays paid requests."""
    from polisyos.core.llm.settlement import LLMSettledResponse

    adoption = _N4_ACTIVE.get()
    if adoption is None:
        return None
    if producer_context is None:
        raise ValueError("native_settled_n4_producer_context_missing")

    with adoption.lock:
        stage = producer_context.get("stage")
        instance = producer_context.get("instance")
        ordinal = producer_context.get("attempt")
        if not adoption.draft_consumed:
            selected_draft = adoption.selected.draft
            if (
                not _native_n4_context_matches(
                    client,
                    kwargs,
                    producer_context,
                    stage="draft",
                    instance="draft_policy",
                    ordinal=0,
                    context_id=None,
                    request_digest=None,
                )
                or ordinal != 0
            ):
                raise ValueError("native_settled_n4_draft_not_first")
            proof = adoption.reopen()
            if (
                type(proof) is not VerifiedNativeSettledN4Recovery
                or proof.selection != adoption.selected
            ):
                raise ValueError("native_settled_n4_recovery_proof_changed")
            settlement = proof.draft_settlement
            if (
                producer_context.get("model_id") != settlement.event.model
                or producer_context.get("preparation", {}).get("kind") != "identity"
                or client._request_digest((), kwargs) != settlement.event.request_digest
            ):
                raise ValueError("native_settled_n4_draft_request_mismatch")
            adoption.latest_proof = proof
            adoption.draft_consumed = True
            from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse

            return LLMSettledResponse(
                GatewayLLMResponse(
                    content=selected_draft.response_text, model=settlement.event.model
                ),
                settlement,
            )

        if adoption.occurrence_index < len(adoption.selected.occurrences):
            selected = adoption.selected.occurrences[adoption.occurrence_index]
            if (
                stage,
                instance,
                ordinal,
            ) != (selected.stage, selected.instance, selected.ordinal):
                raise ValueError("native_settled_n4_occurrence_not_next")
            proof = adoption.reopen()
            if (
                type(proof) is not VerifiedNativeSettledN4Recovery
                or proof.selection != adoption.selected
            ):
                raise ValueError("native_settled_n4_recovery_proof_changed")
            verified = proof.occurrences[adoption.occurrence_index]
            settlement = verified.settlement
            if (
                verified.selection != selected
                or producer_context.get("model_id") != settlement.event.model
                or not _native_n4_context_matches(
                    client,
                    kwargs,
                    producer_context,
                    stage=selected.stage,
                    instance=selected.instance,
                    ordinal=selected.ordinal,
                    context_id=selected.context_id,
                    request_digest=selected.request_digest,
                )
                or settlement.ack.status != "committed"
                or settlement.ack.durability != "ledger"
                or settlement.ack.receipts != (settlement.event.event_id,)
            ):
                raise ValueError("native_settled_n4_occurrence_request_mismatch")
            adoption.latest_proof = proof
            adoption.occurrence_index += 1
            from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse

            return LLMSettledResponse(
                GatewayLLMResponse(content=selected.response_text, model=settlement.event.model),
                settlement,
            )

        selected_identities = {
            (item.stage, item.instance, item.ordinal) for item in adoption.selected.occurrences
        }
        if (stage, instance, ordinal) in selected_identities or stage in {
            "draft",
            "drafter_multipass",
        }:
            raise ValueError("native_settled_n4_paid_stage_replayed_or_unselected")
        expected_instances = {
            "drafter_consolidation": "consolidation",
            "formalizer": "formalize",
            "critic": "critique",
        }
        if (
            stage not in expected_instances
            or instance != expected_instances[stage]
            or adoption.latest_proof is None
        ):
            raise ValueError("native_settled_n4_new_managed_stage_required")
        from polisyos.core.llm.traced_client import TracedLLMClient

        if type(client) is not TracedLLMClient:
            raise ValueError("native_settled_n4_new_managed_stage_required")
        current_digest = client._request_digest((), kwargs)
        if current_digest in adoption.latest_proof.accounted_request_digests:
            raise ValueError("native_settled_n4_paid_request_digest_replayed")
        if not _native_n4_managed_direct_call(client):
            raise ValueError("native_settled_n4_new_managed_stage_required")
        baseline = tuple(
            record
            for record in adoption.latest_proof.baseline_paid_records
            if record.request_digest == current_digest
        )
        if not baseline:
            return None
        if len(baseline) != 1:
            raise ValueError("native_settled_n4_baseline_response_ambiguous")
        (record,) = baseline
        if record.event_id in adoption.baseline_adopted:
            raise ValueError("native_settled_n4_paid_request_digest_replayed")
        if adoption.reopen_baseline is None or producer_context.get("model_id") != record.model:
            raise ValueError("native_settled_n4_baseline_response_not_established")
        response = adoption.reopen_baseline(record, stage)
        if type(response) is not LLMSettledResponse:
            raise ValueError("native_settled_n4_baseline_response_not_established")
        settlement = response.settlement
        if (
            settlement.event.event_id != record.event_id
            or settlement.event.payload_digest != record.payload_digest
            or settlement.ack.status != "committed"
            or settlement.ack.durability != "ledger"
            or settlement.ack.receipts != (record.event_id,)
            or not isinstance(response.content, str)
            or hashlib.sha256(response.content.encode()).hexdigest()
            != settlement.event.response_digest
        ):
            raise ValueError("native_settled_n4_baseline_response_not_established")
        adoption.baseline_adopted.add(record.event_id)
        return response


def _adopt_settled_draft(
    client: object,
    kwargs: dict[str, Any],
    producer_context: Mapping[str, Any] | None,
) -> LLMSettledResponse | None:
    """Match the prepared N4 request before handing the draft bytes to its parser."""
    adoption = _ACTIVE.get()
    if adoption is None:
        return _adopt_settled_n4(client, kwargs, producer_context)
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
