"""Thread-safe budget enforcement middleware for the workflow engine.

Wraps :class:`BudgetState` with locking and provides pre-execution
budget checks, threshold alerts, and reservation lifecycle.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from polisyos.core.llm.cache_settlement import CacheSettlementSession
from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedger,
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSnapshot,
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)

__all__ = ["BudgetMiddleware"]


@dataclass(frozen=True)
class _ProducerAttemptScope:
    """Call-local attribution attached to one established producer run binding."""

    run_binding: BudgetLedgerProducerRunBinding
    control_job_attempt: int | None
    pre_admission_attempt_id: str | None


class BudgetMiddleware:
    """Thread-safe budget enforcement layer for workflow executors."""

    def __init__(
        self,
        budget_state: BudgetState,
        *,
        ledger: BudgetLedger | None = None,
        continuation_owner_identity: tuple[str, str, str] | None = None,
        continuation_resource_identity: tuple[int, int, str, int, int] | None = None,
        continuation_snapshot_anchor: tuple[int, str] | None = None,
        invocation_settlement_profile: Literal["single_owner_local_v1"] | None = None,
    ) -> None:
        if invocation_settlement_profile not in (None, "single_owner_local_v1"):
            raise ValueError("budget_invocation_settlement_profile_invalid")
        if invocation_settlement_profile is not None and type(ledger) is not FileBudgetLedger:
            raise ValueError("budget_ledger_engine_owner_not_supported")
        if (
            invocation_settlement_profile is not None
            and continuation_owner_identity is not None
            and (continuation_resource_identity is None or continuation_snapshot_anchor is None)
        ):
            raise ValueError("budget_ledger_continuation_binding_incomplete")
        self._ledger = ledger
        self._invocation_settlement_profile = invocation_settlement_profile
        if continuation_owner_identity is None and (
            continuation_resource_identity is not None or continuation_snapshot_anchor is not None
        ):
            raise ValueError("budget_ledger_continuation_binding_incomplete")
        self._strict_continuation = continuation_resource_identity is not None
        if continuation_owner_identity is not None:
            if ledger is None:
                raise RuntimeError("budget continuation requires a configured ledger")
            if self._strict_continuation or continuation_snapshot_anchor is not None:
                self._budget = ledger.load_existing(
                    continuation_owner_identity,
                    expected_resource_identity=continuation_resource_identity,
                    expected_snapshot_anchor=continuation_snapshot_anchor,
                )
            else:
                self._budget = ledger.load_existing(continuation_owner_identity)
        else:
            self._budget = (
                ledger.load_or_bootstrap(budget_state) if ledger is not None else budget_state
            )
        self._lock = threading.Lock()
        # Registry lifetime cannot wait behind monetary dependency I/O.
        self._producer_binding_lock = threading.Lock()
        self._alerted: set[tuple[str, int]] = set()
        self._active_producer_run_bindings: dict[str, BudgetLedgerProducerRunBinding] = {}
        self._active_producer_run_binding_counts: dict[str, int] = {}
        self._producer_attempt_scope: ContextVar[_ProducerAttemptScope | None] = ContextVar(
            f"budget_producer_attempt_scope_{id(self)}", default=None
        )

    @property
    def budget_state(self) -> BudgetState:
        if self._ledger is not None:
            with self._lock:
                self._budget = self._ledger.load()
        return self._budget

    @property
    def invocation_settlement_profile(self) -> Literal["single_owner_local_v1"] | None:
        """Return the explicitly selected local invocation-settlement profile."""
        return self._invocation_settlement_profile

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Expose persisted ledger/contract identity without synthetic memory ownership."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            return self._ledger.settlement_owner_identity

    def continuation_binding(
        self,
    ) -> tuple[tuple[str, str, str], tuple[int, int, str, int, int], tuple[int, str]]:
        """Obtain the locked owner/resource/snapshot binding for a local continuation."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("budget continuation requires a configured ledger")
            return self._ledger.continuation_binding()

    def _continuation_state(
        self,
    ) -> tuple[
        tuple[str, str, str], tuple[int, int, str, int, int], tuple[int, str], BudgetLedgerSnapshot
    ]:
        """Obtain a single confirmed detached snapshot and its exact local binding."""
        with self._lock:
            if type(self._ledger) is not FileBudgetLedger:
                raise ValueError("budget_ledger_engine_owner_not_supported")
            return self._ledger._continuation_state()

    def _arm_engine_guard(
        self,
        owner: tuple[str, str, str],
        resource: tuple[int, int, str, int, int],
        anchor: tuple[int, str],
    ) -> None:
        """Bind the actual engine owner to its protected local continuation point."""
        with self._lock:
            if (
                type(self._ledger) is not FileBudgetLedger
                or self._invocation_settlement_profile != "single_owner_local_v1"
            ):
                raise ValueError("budget_ledger_engine_owner_not_supported")
            self._budget = self._ledger.load_existing(
                owner, expected_resource_identity=resource, expected_snapshot_anchor=anchor
            )
            self._strict_continuation = True

    def _issue_engine_settlement_writer(
        self,
    ) -> Callable[[str, Decimal, str, str | None], BudgetLedgerSpendReceipt]:
        """Give the engine a narrow event writer, never the raw ledger."""
        with self._lock:
            if type(self._ledger) is not FileBudgetLedger or not self._strict_continuation:
                raise ValueError("budget_ledger_engine_owner_not_supported")
            ledger = self._ledger
            write = ledger._issue_engine_settlement_writer()

        def settle(
            event_id: str, amount: Decimal, payload_digest: str, provider: str | None
        ) -> BudgetLedgerSpendReceipt:
            with self._lock:
                receipt = write(event_id, amount, payload_digest, provider)
                try:
                    self._budget = ledger.load()
                except (OSError, ValueError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, payload_digest
                    ) from exc
                return receipt

        return settle

    def _read_engine_spent(self) -> Decimal:
        """Read only the confirmed current run spend for an issued engine view."""
        with self._lock:
            if type(self._ledger) is not FileBudgetLedger or not self._strict_continuation:
                raise ValueError("budget_ledger_engine_owner_not_supported")
            self._budget = self._ledger.load()
            return self._budget.spent.get("run", Decimal(0))

    def pre_check(self, alias: str, budget_key: str = "run") -> None:
        """Raise :class:`BudgetExhaustedError` if budget is exhausted."""
        with self._lock:
            if self._ledger is not None and self._strict_continuation:
                self._budget, remaining = self._ledger.load_for_admission(budget_key)
            elif self._ledger is not None:
                self._budget = self._ledger.load()
                remaining = self._budget.remaining(budget_key)
            else:
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
            except (OSError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, payload_digest) from exc
            return receipt

    def resolve_spend_safe(self, event_id: str) -> BudgetLedgerSpendReceipt | None:
        """Resolve a ledger receipt without manufacturing an acknowledgment from memory."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            receipt = self._ledger.resolve_spend(event_id)
            try:
                self._budget = self._ledger.load()
            except (OSError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                digest = receipt.payload_digest if receipt is not None else "readback"
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, digest) from exc
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
            run_binding = self._active_run_binding_for_key(key)
            control_job_attempt, pre_admission_attempt_id = self._attempt_attribution_for(
                run_binding
            )
            return self._ledger.begin_producer_event(
                event_id,
                request_digest,
                key,
                model,
                provider,
                run_binding=run_binding,
                control_job_attempt=control_job_attempt,
                pre_admission_attempt_id=pre_admission_attempt_id,
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
        cache_reuse_session: CacheSettlementSession | None = None,
        cache_reuse_response: object | None = None,
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
            if existing is None:
                control_job_attempt, pre_admission_attempt_id = self._attempt_attribution_for(
                    active_binding
                )
            else:
                # The durable begin fixes attribution, including an explicit unknown.
                # A later lease scope must not relabel a delayed settlement.
                control_job_attempt = existing.control_job_attempt
                pre_admission_attempt_id = existing.pre_admission_attempt_id
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
                control_job_attempt=control_job_attempt,
                pre_admission_attempt_id=pre_admission_attempt_id,
                cache_reuse_session=cache_reuse_session,
                cache_reuse_response=cache_reuse_response,
            )
            try:
                self._budget = self._ledger.load()
            except (OSError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, payload_digest) from exc
            return record

    def resolve_producer_event_safe(self, event_id: str) -> BudgetLedgerProducerRecord | None:
        """Read pending, unknown or committed producer outcome without zero fallback."""
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable producer settlement requires a configured ledger")
            record = self._ledger.resolve_producer_event(event_id)
            try:
                self._budget = self._ledger.load()
            except (OSError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                digest = (
                    (record.payload_digest or record.request_digest)
                    if record is not None
                    else "readback"
                )
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, digest) from exc
            return record

    @contextmanager
    def producer_run_binding_scope(
        self,
        run_binding: BudgetLedgerProducerRunBinding,
        *,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
    ) -> Iterator[None]:
        """Bind producer writes to one server-issued owner and call-local attempt."""
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("producer_run_binding_must_be_typed")
        if control_job_attempt is not None and (
            type(control_job_attempt) is not int or control_job_attempt < 1
        ):
            raise ValueError("producer_control_job_attempt_must_be_positive_integer")
        if pre_admission_attempt_id is not None and (
            not isinstance(pre_admission_attempt_id, str)
            or not re.fullmatch(r"[a-f0-9]{32}", pre_admission_attempt_id)
        ):
            raise ValueError("producer_pre_admission_attempt_id_invalid")
        if control_job_attempt is not None and pre_admission_attempt_id is not None:
            raise ValueError("producer_attempt_attribution_is_ambiguous")
        prior_scope = self._producer_attempt_scope.get()
        if (
            prior_scope is not None
            and prior_scope.run_binding == run_binding
            and control_job_attempt is None
            and pre_admission_attempt_id is None
        ):
            control_job_attempt = prior_scope.control_job_attempt
            pre_admission_attempt_id = prior_scope.pre_admission_attempt_id
        with self._producer_binding_lock:
            existing = self._active_producer_run_bindings.get(run_binding.run_id)
            if existing is not None and existing != run_binding:
                raise ValueError("producer_run_binding_conflict")
            self._active_producer_run_bindings[run_binding.run_id] = run_binding
            self._active_producer_run_binding_counts[run_binding.run_id] = (
                self._active_producer_run_binding_counts.get(run_binding.run_id, 0) + 1
            )
        scope_token = self._producer_attempt_scope.set(
            _ProducerAttemptScope(
                run_binding=run_binding,
                control_job_attempt=control_job_attempt,
                pre_admission_attempt_id=pre_admission_attempt_id,
            )
        )
        try:
            yield
        finally:
            self._producer_attempt_scope.reset(scope_token)
            with self._producer_binding_lock:
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

    def snapshot_safe(self) -> BudgetLedgerSnapshot:
        """Read one detached canonical snapshot for cross-event reconciliation.

        Selection and reuse-origin validation must read the same source revision.
        The returned view is not an authorization token or a new ledger writer.
        """
        with self._lock:
            if self._ledger is None:
                raise RuntimeError("durable budget settlement requires a configured ledger")
            snapshot = self._ledger.snapshot()
            if type(snapshot) is not BudgetLedgerSnapshot:
                raise TypeError("budget_ledger_snapshot_must_be_typed")
            self._budget = snapshot.state.model_copy(deep=True)
            return snapshot.model_copy(deep=True)

    def _active_run_binding_for_key(
        self,
        key: str,
    ) -> BudgetLedgerProducerRunBinding | None:
        prefix = "nl-run:"
        if not key.startswith(prefix):
            return None
        with self._producer_binding_lock:
            return self._active_producer_run_bindings.get(key.removeprefix(prefix))

    def _attempt_attribution_for(
        self,
        run_binding: BudgetLedgerProducerRunBinding | None,
    ) -> tuple[int | None, str | None]:
        """Return attribution only when the current context names the same run owner."""
        scope = self._producer_attempt_scope.get()
        if run_binding is None or scope is None or scope.run_binding != run_binding:
            return None, None
        return scope.control_job_attempt, scope.pre_admission_attempt_id
