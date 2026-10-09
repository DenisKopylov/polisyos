"""Thread-safe budget enforcement middleware for the workflow engine.

Wraps :class:`BudgetState` with locking and provides pre-execution
budget checks, threshold alerts, and reservation lifecycle.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Literal

from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedger,
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSpendReceipt,
)

__all__ = ["BudgetMiddleware"]


class BudgetMiddleware:
    """Thread-safe budget enforcement layer for workflow executors."""

    def __init__(
        self,
        budget_state: BudgetState,
        *,
        ledger: BudgetLedger | None = None,
    ) -> None:
        self._ledger = ledger
        self._budget = (
            ledger.load_or_bootstrap(budget_state) if ledger is not None else budget_state
        )
        self._lock = threading.Lock()
        self._alerted: set[tuple[str, int]] = set()
        self._active_producer_run_bindings: dict[str, BudgetLedgerProducerRunBinding] = {}
        self._active_producer_run_binding_counts: dict[str, int] = {}

    @property
    def budget_state(self) -> BudgetState:
        if self._ledger is not None:
            with self._lock:
                self._budget = self._ledger.load()
        return self._budget

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Expose persisted ledger/contract identity without synthetic memory ownership."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            return self._ledger.settlement_owner_identity

    def pre_check(self, alias: str, budget_key: str = "run") -> None:
        """Raise :class:`BudgetExhaustedError` if budget is exhausted."""
        with self._lock:
            if self._ledger is not None:
                self._budget = self._ledger.load()
            remaining = self._budget.remaining(budget_key)
            if remaining is not None and remaining <= Decimal(0):
                raise BudgetExhaustedError(
                    f"Budget '{budget_key}' exhausted before node '{alias}'",
                )

    def check_thresholds(self, budget_key: str = "run") -> list[int]:
        """Return newly crossed thresholds (80, 90). Deduplicates alerts."""
        with self._lock:
            if self._ledger is not None:
                self._budget = self._ledger.load()
            alerts = self._budget.threshold_alerts(budget_key)
            new_alerts = [level for level in alerts if (budget_key, level) not in self._alerted]
            for level in new_alerts:
                self._alerted.add((budget_key, level))
            return new_alerts

    def record_spend_safe(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> None:
        """Thread-safe spend recording."""
        with self._lock:
            if self._ledger is None:
                self._budget.record_spend(key, amount, provider=provider)
            else:
                self._budget = self._ledger.record_spend(
                    key,
                    amount,
                    provider=provider,
                ).state

    def reserve_safe(self, key: str, amount: Decimal) -> bool:
        """Thread-safe reservation."""
        with self._lock:
            if self._ledger is None:
                return self._budget.reserve(key, amount)
            result = self._ledger.reserve(key, amount)
            self._budget = result.state
            return bool(result.reserved)

    def release_safe(self, key: str, amount: Decimal) -> Decimal:
        """Thread-safe release. Returns the actual released amount."""
        with self._lock:
            if self._ledger is None:
                return self._budget.release(key, amount)
            result = self._ledger.release(key, amount)
            self._budget = result.state
            return result.applied_amount

    def commit_safe(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> Decimal:
        """Thread-safe commit (reservation -> spend). Returns committed amount."""
        with self._lock:
            if self._ledger is None:
                return self._budget.commit_reservation(key, amount, provider=provider)
            result = self._ledger.commit_reservation(key, amount, provider=provider)
            self._budget = result.state
            return result.applied_amount

    def settle_spend_safe(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None = None,
    ) -> BudgetLedgerSpendReceipt:
        """Persist one producer charge exactly once through a configured ledger.

        An in-memory BudgetState cannot issue a durable acknowledgment. If
        delivery/readback fails, the same event remains resolvable; callers
        must retain unknown settlement instead of declaring zero cost.
        """
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            receipt = self._ledger.settle_spend(
                event_id, key, amount, payload_digest=payload_digest, provider=provider
            )
            try:
                self._budget = self._ledger.load()
            except OSError as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, payload_digest) from exc
            return receipt

    def resolve_spend_safe(self, event_id: str) -> BudgetLedgerSpendReceipt | None:
        """Resolve a ledger receipt without manufacturing an acknowledgment from memory."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            receipt = self._ledger.resolve_spend(event_id)
            self._budget = self._ledger.load()
            return receipt

    def begin_producer_event_safe(
        self,
        event_id: str,
        request_digest: str,
        *,
        key: str,
        model: str,
        provider: str,
    ) -> BudgetLedgerProducerRecord:
        """Durably retain provider intent before dispatching external work."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable producer settlement requires a configured ledger")
            return self._ledger.begin_producer_event(
                event_id,
                request_digest,
                key,
                model,
                provider,
                run_binding=self._active_run_binding_for_key(key),
            )

    def settle_producer_event_safe(
        self,
        event_id: str,
        request_digest: str,
        payload_digest: str,
        *,
        key: str,
        model: str,
        provider: str,
        amount: Decimal | None,
        cost_origin: Literal["reported", "estimated", "reuse", "unknown"],
        origin_event_id: str | None = None,
    ) -> BudgetLedgerProducerRecord:
        """Persist the final status and charge together; missing amount stays unknown."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable producer settlement requires a configured ledger")
            active_binding = self._active_run_binding_for_key(key)
            existing = self._ledger.resolve_producer_event(event_id)
            if existing is None:
                run_binding = active_binding
            else:
                if existing.key != key:
                    raise ValueError("producer event budget key conflicts with existing intent")
                if active_binding is not None and active_binding != existing.run_binding:
                    raise ValueError("producer event run binding conflicts with existing intent")
                # The durable begin is the owner issuance boundary. A shielded
                # provider/cache task may settle after its run scope has exited,
                # so retain that exact binding rather than recomputing it from
                # ambient context or silently dropping it.
                run_binding = existing.run_binding
            record = self._ledger.settle_producer_event(
                event_id,
                request_digest,
                payload_digest,
                key,
                model,
                provider,
                amount,
                cost_origin,
                origin_event_id,
                run_binding=run_binding,
            )
            self._budget = self._ledger.load()
            return record

    def resolve_producer_event_safe(self, event_id: str) -> BudgetLedgerProducerRecord | None:
        """Read pending, unknown or committed producer outcome without zero fallback."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable producer settlement requires a configured ledger")
            record = self._ledger.resolve_producer_event(event_id)
            self._budget = self._ledger.load()
            return record

    @contextmanager
    def producer_run_binding_scope(
        self,
        run_binding: BudgetLedgerProducerRunBinding,
    ) -> Iterator[None]:
        """Bind producer writes to one server-issued run owner for a bounded execution."""
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("producer_run_binding_must_be_typed")
        with self._lock:
            existing = self._active_producer_run_bindings.get(run_binding.run_id)
            if existing is not None and existing != run_binding:
                raise ValueError("producer_run_binding_conflict")
            self._active_producer_run_bindings[run_binding.run_id] = run_binding
            self._active_producer_run_binding_counts[run_binding.run_id] = (
                self._active_producer_run_binding_counts.get(run_binding.run_id, 0) + 1
            )
        try:
            yield
        finally:
            with self._lock:
                if self._active_producer_run_bindings.get(run_binding.run_id) == run_binding:
                    remaining = (
                        self._active_producer_run_binding_counts.get(run_binding.run_id, 1) - 1
                    )
                    if remaining > 0:
                        self._active_producer_run_binding_counts[run_binding.run_id] = remaining
                    else:
                        del self._active_producer_run_bindings[run_binding.run_id]
                        self._active_producer_run_binding_counts.pop(run_binding.run_id, None)

    def list_producer_events_for_run_safe(
        self,
        run_binding: BudgetLedgerProducerRunBinding,
    ) -> tuple[BudgetLedgerProducerRecord, ...]:
        """Read pending and settled events only for one exact persisted run owner."""
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("producer_run_binding_must_be_typed")
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            records = self._ledger.list_producer_events_for_run(run_binding)
            self._budget = self._ledger.load()
            return records

    def _active_run_binding_for_key(
        self,
        key: str,
    ) -> BudgetLedgerProducerRunBinding | None:
        prefix = "nl-run:"
        if not key.startswith(prefix):
            return None
        return self._active_producer_run_bindings.get(key.removeprefix(prefix))
