"""Retain actual durable LLM begin receipts without worker-held trace/SQL locks."""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core.artifacts import read_core_manifest_profile, validate_core_model_json_artifact
from polisyos.core.llm import LLMProducerIntent
from polisyos.core.trace import TraceRecord
from polisyos.scientist.orchestration.engine import (
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.run import RunContext
    from polisyos.runtime.http.services.adapters.core_run import TerminalCoreRunSource

_PHASE = "llm_producer"
_OPEN = "PRODUCER_BASIS_OPENED"
_INTENT = "PRODUCER_INTENT_RETAINED"
_CLOSE = "PRODUCER_BASIS_CLOSED"


class _ControlJobProducerIntent(BaseModel):
    """Bind actual returned/read-back pending ownership, never an expected substitute."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ARTIFACT_KIND: ClassVar[str] = "runtime.control_job_llm_producer_intent"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.ControlJobLLMProducerIntent"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "2.0"

    schema_version: Literal["policyos.runtime.control_job_llm_producer_intent.v2"] = (
        "policyos.runtime.control_job_llm_producer_intent.v2"
    )
    intent: LLMProducerIntent
    begin_receipt: BudgetLedgerProducerRecord

    @model_validator(mode="after")
    def _actual_pending_begin(self) -> _ControlJobProducerIntent:
        receipt, intent = self.begin_receipt, self.intent
        if (
            receipt.status != "pending"
            or receipt.payload_digest is not None
            or receipt.amount is not None
            or receipt.origin_event_id is not None
            or receipt.reuse_admission is not None
            or receipt.cost_origin != "unknown"
            or receipt.run_binding is None
            or receipt.control_job_attempt is None
            or receipt.pre_admission_attempt_id is not None
            or (
                receipt.event_id,
                receipt.request_digest,
                receipt.key,
                receipt.model,
                receipt.provider,
            )
            != (intent.event_id, intent.request_digest, intent.key, intent.model, intent.provider)
        ):
            raise ValueError("producer_basis_actual_begin_not_established")
        return self


class _ControlJobProducerBasis:
    """Collect durable refs using short state locks; only the parent writes its trace."""

    def __init__(
        self,
        *,
        run_binding: BudgetLedgerProducerRunBinding,
        attempt: int,
        persist: Callable[[_ControlJobProducerIntent], ArtifactRef],
        readback: Callable[[str], object],
    ) -> None:
        self._binding, self._attempt = run_binding, attempt
        self._persist, self._readback = persist, readback
        self._lock = threading.Lock()
        self._refs: dict[str, ArtifactRef] = {}
        self._closed = False
        self._failed = False
        self._admission_complete = False

    def observe(self, intent: LLMProducerIntent, receipt: object) -> None:
        """Reopen the actual begin and verify its full owner before external work."""
        try:
            with self._lock:
                if self._closed:
                    raise RuntimeError("producer_basis_scope_closed")
            actual = self._readback(intent.event_id)
            if (
                type(receipt) is not BudgetLedgerProducerRecord
                or type(actual) is not BudgetLedgerProducerRecord
            ):
                raise TypeError("producer_basis_begin_receipt_untyped")
            if actual != receipt:
                raise ValueError("producer_basis_begin_readback_mismatch")
            source = _ControlJobProducerIntent(intent=intent, begin_receipt=actual)
            if actual.run_binding != self._binding or actual.control_job_attempt != self._attempt:
                raise ValueError("producer_basis_actual_begin_owner_mismatch")
            # Durable before dispatch, but no Core RunContext or SQL lock is
            # held by this callback. The parent attaches refs when scope closes.
            reference = self._persist(source)
            with self._lock:
                if self._closed or intent.event_id in self._refs:
                    raise RuntimeError("producer_basis_closed_or_duplicate_begin")
                self._refs[intent.event_id] = reference
        except BaseException:
            with self._lock:
                self._failed = True
            raise

    def close_admission(self, complete: bool) -> None:
        """Signal closure without waiting on an in-progress dependency operation."""
        with self._lock:
            self._closed = True
            self._admission_complete = complete

    def closed_snapshot(self) -> tuple[bool, tuple[ArtifactRef, ...]]:
        """Return known durable facts and whether the actual admission set closed."""
        with self._lock:
            complete = self._closed and self._admission_complete and not self._failed
            return complete, tuple(self._refs.values())


@contextmanager
def control_job_producer_basis_scope(
    *,
    context: RunContext,
    run_binding: BudgetLedgerProducerRunBinding,
    attempt: int,
    persist: Callable[[_ControlJobProducerIntent], ArtifactRef],
    readback: Callable[[str], object],
) -> Iterator[_ControlJobProducerBasis]:
    """Persist before work; attach the independent basis on the parent after close."""
    if context.run_manifest.control_job_id != run_binding.control_job_id:
        raise ValueError("producer_basis_core_job_mismatch")
    context.emit(_PHASE, _OPEN, metrics={"control_job_attempt": attempt})
    basis = _ControlJobProducerBasis(
        run_binding=run_binding, attempt=attempt, persist=persist, readback=readback
    )
    try:
        yield basis
    finally:
        complete, references = basis.closed_snapshot()
        for reference in references:
            context.emit(_PHASE, _INTENT, outputs=[reference])
        context.emit(
            _PHASE, _CLOSE, metrics={"control_job_attempt": attempt, "complete": int(complete)}
        )


def read_control_job_producer_basis(
    *,
    store: ArtifactStore,
    terminal: TerminalCoreRunSource,
    run_binding: BudgetLedgerProducerRunBinding,
    attempt: int,
) -> dict[str, BudgetLedgerProducerRecord]:
    """Reopen exact current actual-begin receipts from the completed Core trace."""
    trace_ref = terminal.manifest.trace_ref
    if trace_ref is None or trace_ref.kind != "core.trace.jsonl":
        raise ValueError("producer_basis_trace_missing")
    manifest, _ = read_core_manifest_profile(store, trace_ref)
    raw = store.get_bytes(trace_ref.artifact_id)
    if hashlib.sha256(raw).hexdigest() != manifest.integrity.sha256:
        raise ValueError("producer_basis_trace_content_mismatch")
    records = [TraceRecord.model_validate_json(line) for line in raw.splitlines() if line]
    state: Literal["absent", "open", "closed"] = "absent"
    receipts: dict[str, BudgetLedgerProducerRecord] = {}
    for record in records:
        if (
            record.run_id != terminal.run_id
            or record.tenant_id != run_binding.tenant_id
            or record.cell_id != run_binding.cell_id
        ):
            raise ValueError("producer_basis_trace_owner_mismatch")
        if record.phase != _PHASE:
            continue
        if record.event in {_OPEN, _CLOSE}:
            expected = {"control_job_attempt": attempt}
            if record.event == _CLOSE:
                expected["complete"] = 1
            if (
                record.metrics != expected
                or any(type(value) is not int for value in record.metrics.values())
                or record.refs.inputs
                or record.refs.outputs
            ):
                raise ValueError("producer_basis_interval_not_established")
            if record.event == _OPEN and state == "absent":
                state = "open"
            elif record.event == _CLOSE and state == "open":
                state = "closed"
            else:
                raise ValueError("producer_basis_interval_ambiguous")
            continue
        if record.event != _INTENT or state != "open" or len(record.refs.outputs) != 1:
            raise ValueError("producer_basis_begin_outside_interval")
        source = validate_core_model_json_artifact(
            _ControlJobProducerIntent, store, record.refs.outputs[0]
        )
        actual = source.begin_receipt
        if actual.run_binding != run_binding or actual.control_job_attempt != attempt:
            raise ValueError("producer_basis_actual_owner_mismatch")
        if actual.event_id in receipts:
            raise ValueError("producer_basis_dispatch_duplicate")
        receipts[actual.event_id] = actual
    if state != "closed":
        raise ValueError("producer_basis_interval_not_closed")
    return receipts
