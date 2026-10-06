"""Thread-safe budget enforcement middleware for the workflow engine.

Wraps :class:`BudgetState` with locking and provides pre-execution
budget checks, threshold alerts, and reservation lifecycle.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedger,
    BudgetLedgerCompletionObligation,
    BudgetLedgerCompletionOutcomeUnknownError,
    BudgetLedgerCompletionResolver,
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

    @property
    def budget_state(self) -> BudgetState:
        if self._ledger is not None:
            with self._lock:
                self._budget = self._ledger.load()
        return self._budget

    @property
    def completion_owner_epoch(self) -> str:
        """Return this configured live owner's epoch without caller-selected binding."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            return self._ledger.completion_owner_epoch

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Expose persisted ledger/contract identity without synthetic memory ownership."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            return self._ledger.settlement_owner_identity

    def pre_check(self, alias: str, budget_key: str = "run") -> None:
        """Refuse exhausted budgets and unresolved completion on this actual key."""
        with self._lock:
            if self._ledger is not None:
                self._budget = self._ledger.load_for_admission((budget_key,))
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

    def with_completion_resolver(
        self, resolver: BudgetLedgerCompletionResolver
    ) -> BudgetMiddleware:
        """Construct a bound completion-owner view without mutating another owner."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            return BudgetMiddleware(
                self._budget, ledger=self._ledger.with_completion_resolver(resolver)
            )

    def retain_completion_obligation_safe(
        self, record: BudgetLedgerCompletionObligation
    ) -> BudgetLedgerCompletionObligation:
        """Persist observed unresolved work separately from monetary spend receipts."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            retained = self._ledger.retain_completion_obligation(record)
            self._refresh_completion(record.obligation_id, retained.payload_digest)
            return retained

    def admit_provider_intent_safe(self, record: BudgetLedgerCompletionObligation) -> bool:
        """Atomically reserve all keys and retain intent before physical admission."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            admitted = self._ledger.admit_provider_intent(record)
            self._refresh_completion(record.obligation_id, record.payload_digest)
            return admitted

    def abort_provider_intent_safe(self, obligation_id: str, expected_digest: str) -> bool:
        """Abort only original live owner work verified as physically unentered."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            aborted = self._ledger.abort_provider_intent(obligation_id, expected_digest)
            self._refresh_completion(obligation_id, expected_digest)
            return aborted

    def list_completion_obligations_safe(
        self, budget_keys: tuple[str, ...]
    ) -> tuple[BudgetLedgerCompletionObligation, ...]:
        """Discover unresolved completion work through the actual durable owner."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            return self._ledger.list_completion_obligations(budget_keys)

    def transition_completion_obligation_safe(
        self, record: BudgetLedgerCompletionObligation, expected_digest: str
    ) -> BudgetLedgerCompletionObligation:
        """Advance the exact retained event after actual per-key charge acknowledgments."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            advanced = self._ledger.transition_completion_obligation(record, expected_digest)
            self._refresh_completion(record.obligation_id, advanced.payload_digest)
            return advanced

    def complete_completion_obligation_safe(
        self,
        obligation_id: str,
        expected_digest: str,
        known_receipt_ids: tuple[str, ...],
        owner_resolution_ref: str | None = None,
    ) -> bool:
        """Resolve only actual charge receipts and constructor-bound owner verification."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable completion requires a configured ledger")
            completed = self._ledger.complete_completion_obligation(
                obligation_id, expected_digest, known_receipt_ids, owner_resolution_ref
            )
            self._refresh_completion(obligation_id, expected_digest)
            return completed

    def _refresh_completion(self, obligation_id: str, record_digest: str) -> None:
        assert self._ledger is not None
        try:
            self._budget = self._ledger.load()
        except OSError as exc:
            raise BudgetLedgerCompletionOutcomeUnknownError(obligation_id, record_digest) from exc
