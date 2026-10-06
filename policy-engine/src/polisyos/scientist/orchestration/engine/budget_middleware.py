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
    BudgetLedgerMutationResult,
    BudgetLedgerSnapshot,
    BudgetResourceEvent,
    BudgetResourceReservation,
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

    def reserve_resource(
        self,
        reservation_id: str,
        *,
        run_id: str,
        budget_keys: tuple[str, ...],
        estimated_usd: Decimal,
        evaluation_id: str | None = None,
    ) -> bool:
        """Reserve an owned attempt through the existing durable ledger."""
        reservation = BudgetResourceReservation(
            reservation_id=reservation_id,
            run_id=run_id,
            budget_keys=budget_keys,
            estimated_usd=estimated_usd,
            evaluation_id=evaluation_id,
        )
        with self._lock:
            result = self._resource_ledger().reserve_resource(reservation)
            self._budget = result.state
            return bool(result.reserved)

    def settle_resource(
        self,
        reservation_id: str,
        event: BudgetResourceEvent,
    ) -> BudgetLedgerMutationResult:
        """Reconcile full measured cost once and refresh the budget consumer snapshot."""
        with self._lock:
            result = self._resource_ledger().settle_resource(reservation_id, event)
            self._budget = result.state
            return result

    def release_resource(self, reservation_id: str) -> None:
        """Release an owned attempt known not to require provider reconciliation."""
        with self._lock:
            self._budget = self._resource_ledger().release_resource(reservation_id).state

    def require_reconciliation(self, reservation_id: str) -> None:
        """Keep an unresolved call's reservation visible across reopening."""
        with self._lock:
            self._budget = self._resource_ledger().require_reconciliation(reservation_id).state

    def _resource_ledger(self) -> BudgetLedger:
        if self._ledger is None:
            raise ValueError("measured resource accounting requires a persisted budget ledger")
        return self._ledger

    def resource_snapshot(self) -> BudgetLedgerSnapshot:
        """Return the existing persisted owner's detached resource accounting snapshot."""
        with self._lock:
            snapshot = self._resource_ledger().snapshot()
            self._budget = snapshot.state
            return snapshot
