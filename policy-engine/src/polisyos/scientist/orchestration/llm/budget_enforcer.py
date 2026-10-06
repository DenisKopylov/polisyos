"""LLM budget enforcement wrapper."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.settlement import (
    LLMAuditObligation,
    LLMAuditResolution,
    LLMProducerEvent,
    LLMSettlementAck,
    _completion_amount,
    _new_producer_id,
    _request_digest,
    _settlement_owner_context,
)
from polisyos.core.llm.traced_client import LLMAccountingError
from polisyos.core.observability import estimate_llm_cost_usd
from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.operational_monitoring import get_operational_monitor
from polisyos.scientist.orchestration.llm.cost_anomaly import CostAnomalyDetector

logger = get_logger(__name__)

_OBSERVABILITY_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.orchestration.engine.operational_monitoring import (
        ScientistOperationalMonitor,
    )


def _default_metrics() -> MetricsRegistry:
    from polisyos.core.observability import get_metrics

    return get_metrics()


def _default_operational_monitor() -> ScientistOperationalMonitor:
    return get_operational_monitor()


@dataclass(slots=True)
class _BudgetReservation:
    estimated_cost: Decimal
    reserved_amounts: dict[str, Decimal] = field(default_factory=dict)
    attempt_id: str = ""
    request_digest: str = ""
    provider_started: bool = False

    def outstanding_items(self) -> list[tuple[str, Decimal]]:
        return [(key, amount) for key, amount in self.reserved_amounts.items() if amount > 0]

    def clear_key(self, key: str) -> None:
        if key in self.reserved_amounts:
            self.reserved_amounts[key] = Decimal(0)

    def has_outstanding(self) -> bool:
        return any(amount > 0 for amount in self.reserved_amounts.values())


class _CompletionResolver:
    """Constructor-bound bridge; references alone cannot discharge obligations."""

    def __init__(self, owner: LLMBudgetEnforcer) -> None:
        self._owner = owner

    def resolve(self, obligation: Any, owner_resolution_ref: str | None) -> Any:
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerCompletionResolution,
        )

        proof = self._owner._completion_proofs.get(obligation.obligation_id)
        if proof is None or proof[:2] != (obligation.payload_digest, owner_resolution_ref):
            raise RuntimeError("completion requires this owner's exact verified resolution")
        return BudgetLedgerCompletionResolution(
            obligation_id=obligation.obligation_id,
            record_digest=obligation.payload_digest,
            phase=obligation.phase,
            known_receipt_ids=obligation.known_receipt_ids,
            owner_resolution_ref=owner_resolution_ref,
            status=proof[2],
        )


class LLMBudgetEnforcer:
    """Wraps an LLM client with pre-call budget checks and post-call cost recording.

    Use this as a drop-in replacement for ``TracedLLMClient`` or
    ``GatewayLLMClient`` when budget enforcement is needed.

    Thread-safe: internal lock guards ``BudgetState`` mutations.
    """

    def __init__(
        self,
        *,
        client: Any,
        budget_state: BudgetState,
        budget_keys: list[str],
        model_name: str = "default",
        audit_log: Any | None = None,
        run_id: str = "",
        metrics: MetricsRegistry | None = None,
        operational_monitor: ScientistOperationalMonitor | None = None,
        budget_middleware: BudgetMiddleware | None = None,
        audit_reconciler: Callable[[LLMAuditObligation], LLMAuditResolution] | None = None,
    ) -> None:
        if (
            not isinstance(budget_keys, list)
            or not budget_keys
            or any(not isinstance(key, str) or not key for key in budget_keys)
        ):
            raise ValueError("LLM accounting requires nonempty budget target keys")
        if len(set(budget_keys)) != len(budget_keys):
            raise ValueError("LLM accounting budget target keys must be unique")
        self._client = client
        self._completion_proofs: dict[str, tuple[str, str | None, str]] = {}
        self._completion_records: dict[str, Any] = {}
        self._pending_audits: dict[str, tuple[LLMAuditObligation, Any]] = {}
        self._audit_reservations: dict[str, _BudgetReservation] = {}
        self._completed_audits: dict[str, LLMAuditResolution] = {}
        self._retained_responses: dict[str, Any] = {}
        self._retained_run_ids: dict[str, str] = {}
        self._audit_reconciler = audit_reconciler
        self._budget_middleware = (
            budget_middleware.with_completion_resolver(_CompletionResolver(self))
            if budget_middleware is not None
            else None
        )
        self._budget_state = (
            budget_middleware.budget_state if budget_middleware is not None else budget_state
        )
        self._owned_calls: set[asyncio.Task[Any]] = set()
        self._unknown_settlements: dict[str, tuple[LLMProducerEvent, _BudgetReservation]] = {}
        self._budget_keys = tuple(budget_keys)
        self._model_name = model_name
        self._audit_log = audit_log
        self._run_id = run_id
        self._lock = threading.Lock()
        self._anomaly_detector = CostAnomalyDetector()
        self._metrics = metrics
        self._operational_monitor = operational_monitor

    @property
    def budget_state(self) -> BudgetState:
        if self._budget_middleware is not None:
            self._budget_state = self._budget_middleware.budget_state
        return self._budget_state

    def _reserve_budget(self, key: str, amount: Decimal) -> bool:
        if self._budget_middleware is not None:
            return self._budget_middleware.reserve_safe(key, amount)
        return self._budget_state.reserve(key, amount)

    def _release_budget(self, key: str, amount: Decimal) -> None:
        if self._budget_middleware is not None:
            self._budget_middleware.release_safe(key, amount)
        else:
            self._budget_state.release(key, amount)

    def remaining_budget(self) -> Decimal | None:
        """Return the smallest remaining budget across configured keys."""
        with self._lock:
            remaining: list[Decimal] = [
                value
                for key in self._budget_keys
                if (value := self._budget_state.remaining(key)) is not None
            ]
        if not remaining:
            return None
        return min(remaining)

    def _estimate_cost(self, kwargs: dict[str, Any]) -> Decimal:
        """Estimate call cost from the request payload."""
        max_tokens = kwargs.get("max_tokens", 4096)
        prompt_tokens = kwargs.get("_prompt_tokens_estimate", 0)
        if prompt_tokens == 0:
            from polisyos.scientist.orchestration.llm.token_estimator import estimate_request_tokens

            prompt_tokens = estimate_request_tokens(
                system=kwargs.get("system"),
                user=kwargs.get("user"),
                messages=kwargs.get("messages"),
                tools=kwargs.get("tools"),
                model=self._model_name,
                provider_hint=getattr(self._client, "provider_hint", None),
            )

        estimated = Decimal(
            str(
                estimate_llm_cost_usd(
                    model=self._model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=max_tokens,
                )
            )
        )
        return estimated

    def _pre_check(
        self, kwargs: dict[str, Any], *, attempt_id: str, request_digest: str
    ) -> _BudgetReservation:
        """Estimate cost, reserve budget, and reject calls that cannot fit."""
        if self._pending_audits:
            obligation, response = next(iter(self._pending_audits.values()))
            raise self._audit_error(obligation, response, RuntimeError("required audit is pending"))
        if self._unknown_settlements:
            event = next(iter(self._unknown_settlements.values()))[0]
            raise LLMAccountingError(
                response=self._retained_responses.get(event.event_id),
                event={"producer_event": event, "settlement_status": "unknown"},
                cause=RuntimeError("reconcile the unknown producer settlement before another call"),
            )
        if self._budget_middleware is not None:
            pending = self._budget_middleware.list_completion_obligations_safe(self._budget_keys)
            pending = [
                r
                for r in pending
                if r.phase != "provider_in_flight"
                or r.owner_epoch != self._budget_middleware.completion_owner_epoch
            ]
            if pending:
                raise LLMAccountingError(
                    response=None,
                    event={"completion_obligation": pending[0], "settlement_status": "unknown"},
                    cause=RuntimeError("persisted budget completion obligation is unresolved"),
                )
            self._budget_state = self._budget_middleware.budget_state
        estimated = self._estimate_cost(kwargs)
        run_id = kwargs.get("_run_id", self._run_id)

        reserved_keys: list[str] = []
        reservation = _BudgetReservation(
            estimated_cost=estimated, attempt_id=attempt_id, request_digest=request_digest
        )
        if self._budget_middleware is not None:
            from polisyos.scientist.orchestration.engine.budget_ledger import (
                BudgetLedgerCompletionObligation,
            )

            body = {
                "event_id": attempt_id,
                "kind": "provider_intent",
                "amount": None,
                "request_digest": request_digest,
            }
            reservation.reserved_amounts = {
                key: estimated if key in self._budget_state.limits else Decimal(0)
                for key in self._budget_keys
            }
            record = BudgetLedgerCompletionObligation(
                obligation_id=attempt_id,
                event_payload=body,
                event_digest="sha256:"
                + hashlib.sha256(
                    json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                run_id=run_id,
                budget_keys=self._budget_keys,
                reserved_amounts=reservation.reserved_amounts,
                phase="provider_in_flight",
                owner_epoch=self._budget_middleware.completion_owner_epoch,
            )
            self._completion_records[attempt_id] = record
            try:
                admitted = self._budget_middleware.admit_provider_intent_safe(record)
            except Exception as exc:
                raise LLMAccountingError(
                    response=None,
                    event={"completion_obligation": record, "settlement_status": "unknown"},
                    cause=exc,
                ) from exc
            if not admitted:
                self._completion_records.pop(attempt_id, None)
                raise BudgetExhaustedError("LLM request cannot reserve its exact budget intent")
            self._budget_state = self._budget_middleware.budget_state
        else:
            with self._lock:
                for key in self._budget_keys:
                    has_limit = key in self._budget_state.limits
                    if not self._reserve_budget(key, estimated):
                        remaining = self._budget_state.remaining(key)
                        for reserved_key in reserved_keys:
                            reserved_amount = reservation.reserved_amounts.get(
                                reserved_key,
                                Decimal(0),
                            )
                            if reserved_amount > 0:
                                self._release_budget(reserved_key, reserved_amount)
                                reservation.clear_key(reserved_key)
                        if self._audit_log:
                            self._append_audit(
                                run_id=run_id,
                                actor="budget_enforcer",
                                action="BUDGET_EXCEEDED",
                                metadata={
                                    "budget_key": key,
                                    "estimated_cost_usd": str(estimated),
                                    "remaining_usd": str(remaining),
                                    "model": self._model_name,
                                },
                            )
                        raise BudgetExhaustedError(
                            f"LLM call would exceed budget '{key}': "
                            f"estimated=${estimated}, remaining=${remaining}"
                        )
                    reservation.reserved_amounts[key] = estimated if has_limit else Decimal(0)
                    reserved_keys.append(key)

        if self._audit_log:
            self._append_audit(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_RESERVED",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(estimated),
                    "model": self._model_name,
                },
                reservation=reservation,
            )
            self._append_audit(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_CHECK",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(estimated),
                    "model": self._model_name,
                },
                reservation=reservation,
            )
        return reservation

    def _release_reservation(
        self,
        reservation: _BudgetReservation,
        *,
        run_id: str,
        reason: str,
        producer_event: LLMProducerEvent | None = None,
        charge_ack: LLMSettlementAck | None = None,
        response: Any = None,
    ) -> None:
        """Release any outstanding reservation for the current call."""
        released_keys: list[str] = []
        with self._lock:
            for key, reserved in reservation.outstanding_items():
                self._release_budget(key, reserved)
                reservation.clear_key(key)
                released_keys.append(key)

        if released_keys and self._audit_log:
            self._append_audit(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_RELEASED",
                metadata={
                    "budget_keys": released_keys,
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "model": self._model_name,
                    "reason": reason,
                },
                producer_event=producer_event,
                charge_ack=charge_ack,
                response=response,
            )

    def _post_record(
        self,
        response: Any,
        *,
        reservation: _BudgetReservation | None = None,
        run_id: str | None = None,
        producer_event: LLMProducerEvent | None = None,
    ) -> Decimal:
        """Extract actual cost from response and commit the reservation."""
        reservation = reservation or _BudgetReservation(estimated_cost=Decimal(0))
        resolved_run_id = self._run_id if run_id is None else run_id
        data = extract_llm_response_data(response)
        try:
            actual_cost = (
                producer_event.amount
                if producer_event is not None
                else self._resolve_actual_cost(data)
            )
        except (ArithmeticError, TypeError, ValueError) as exc:
            emit_degraded_path(
                component="llm.budget_enforcer",
                operation="post_record",
                reason="cost_accounting_fallback",
                exc=exc,
                details={
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "model": self._model_name,
                    "run_id": resolved_run_id,
                },
                log=logger,
                metrics=self._resolve_metrics(),
            )
            raise LLMAccountingError(
                response=response,
                event={"settlement_status": "unknown", "cost_origin": "unknown"},
                cause=exc,
            ) from exc
        if actual_cost is None:
            raise ValueError("unknown producer amount cannot be recorded as spend")

        with self._lock:
            for key in self._budget_keys:
                reserved = reservation.reserved_amounts.get(key, Decimal(0))
                if reserved > 0:
                    self._release_budget(key, reserved)
                    reservation.clear_key(key)
                self._budget_state.record_spend(key, actual_cost)
                if self._budget_state.is_soft_limit_exceeded(key):
                    logger.warning(
                        "Soft budget limit exceeded for key={}, spent={}",
                        key,
                        self._budget_state.spent.get(key),
                    )

        if self._audit_log and producer_event is None:
            self._append_audit(
                run_id=resolved_run_id,
                actor="budget_enforcer",
                action="BUDGET_COMMITTED",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "actual_cost_usd": str(actual_cost),
                    "delta_cost_usd": str(actual_cost - reservation.estimated_cost),
                    "model": self._model_name,
                },
            )

        # Emit OTel metrics
        try:
            self._emit_cost_metrics(actual_cost, data)
        except Exception:
            logger.warning("Optional LLM budget metrics sink failed")

        return actual_cost

    def _resolve_actual_cost(self, data: Any) -> Decimal:
        amount, _ = _completion_amount(data, self._model_name)
        if amount is None:
            raise ValueError("provider monetary evidence is unknown")
        return amount

    @staticmethod
    def _coerce_cost_decimal(value: Any) -> Decimal:
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0:
            raise ValueError(f"invalid llm cost value: {value!r}")
        return parsed

    def _emit_cost_metrics(self, cost: Decimal, data: Any) -> None:
        """Emit LLM cost, token, and budget utilization metrics."""
        m = self._resolve_metrics()
        if m is None:
            return

        attrs = {"model_id": self._model_name}

        if m.llm_cost_usd is not None:
            m.llm_cost_usd.record(float(cost), attrs)

        if m.llm_calls_total is not None:
            m.llm_calls_total.add(1, attrs)

        if data is not None and m.llm_tokens_total is not None:
            m.llm_tokens_total.add(
                data.prompt_tokens,
                {**attrs, "direction": "input"},
            )
            m.llm_tokens_total.add(
                data.completion_tokens,
                {**attrs, "direction": "output"},
            )

        # Budget utilization gauge
        if m.scientist_llm_budget_utilization is not None:
            for key in self._budget_keys:
                utilization = self._budget_state.utilization(key)
                if utilization is not None:
                    m.scientist_llm_budget_utilization.set(
                        utilization,
                        {"budget_key": key, "run_id": self._run_id},
                    )

        # Anomaly detection
        cost_f = float(cost)
        if cost_f > 0 and self._anomaly_detector.check(cost_f):
            logger.warning(
                "Anomalous LLM cost detected: ${:.4f} for model={}",
                cost_f,
                self._model_name,
            )
            monitor = self._resolve_operational_monitor()
            if monitor is not None:
                monitor.record_alert(
                    alert_type="budget_anomaly",
                    severity="warn",
                    run_id=self._run_id or None,
                    details={
                        "model_id": self._model_name,
                        "cost_usd": cost_f,
                    },
                )
            if m.scientist_llm_cost_anomalies_total is not None:
                m.scientist_llm_cost_anomalies_total.add(1, attrs)

    def _record_latency(self, elapsed_s: float) -> None:
        """Emit LLM call latency to OTel histogram."""
        m = self._resolve_metrics()
        if m is None:
            return
        if m.llm_latency_ms is not None:
            m.llm_latency_ms.record(
                elapsed_s * 1000.0,
                {"model_id": self._model_name},
            )

    def _resolve_metrics(self) -> MetricsRegistry | None:
        if self._metrics is not None:
            return self._metrics
        try:
            self._metrics = _default_metrics()
        except _OBSERVABILITY_IMPORT_ERRORS:
            return None
        return self._metrics

    def _resolve_operational_monitor(self) -> ScientistOperationalMonitor | None:
        if self._operational_monitor is not None:
            return self._operational_monitor
        try:
            monitor = _default_operational_monitor()
        except _OBSERVABILITY_IMPORT_ERRORS:
            return None
        self._operational_monitor = monitor
        return self._operational_monitor

    @staticmethod
    def _event_body(event: LLMProducerEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "request_digest": event.request_digest,
            "response_digest": event.response_digest,
            "model": event.model,
            "provider": event.provider,
            "amount": str(event.amount) if event.amount is not None else None,
            "cost_origin": event.cost_origin,
            "kind": event.kind,
            "origin_event_id": event.origin_event_id,
        }

    def _retain_completion(
        self,
        obligation_id: str,
        event: LLMProducerEvent | None,
        reservation: _BudgetReservation,
        run_id: str,
        phase: str,
        *,
        charge_ack: LLMSettlementAck | None = None,
        required_action: dict[str, Any] | None = None,
    ) -> Any:
        if self._budget_middleware is None:
            return None
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerCompletionObligation,
        )

        existing = self._completion_records.get(obligation_id)
        body = (
            self._event_body(event)
            if event is not None
            else {
                "event_id": obligation_id,
                "kind": "budget_audit",
                "amount": None,
                "action": required_action["action"] if required_action else None,
                "run_id": run_id,
                "required_action": required_action,
            }
        )
        record = BudgetLedgerCompletionObligation(
            obligation_id=obligation_id,
            event_payload=body,
            event_digest=event.payload_digest
            if event is not None
            else "sha256:"
            + hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            run_id=run_id,
            budget_keys=self._budget_keys,
            reserved_amounts=(
                existing.reserved_amounts
                if existing is not None
                else dict(reservation.reserved_amounts)
            ),
            phase=phase,
            owner_epoch=self._budget_middleware.completion_owner_epoch,
            known_receipt_ids=tuple(r.event_id for r in charge_ack.receipts) if charge_ack else (),
            required_action=required_action,
        )
        # Store the exact intended record before I/O; lost publication ACK remains pending locally.
        self._completion_records[obligation_id] = record
        if existing is None:
            received = self._budget_middleware.retain_completion_obligation_safe(record)
        else:
            received = self._budget_middleware.transition_completion_obligation_safe(
                record, expected_digest=existing.payload_digest
            )
        self._completion_records[obligation_id] = received
        return received

    def _complete_record(self, obligation_id: str, resolution_ref: str | None) -> None:
        record = self._completion_records.get(obligation_id)
        if record is None or self._budget_middleware is None:
            return
        self._completion_proofs[obligation_id] = (
            record.payload_digest,
            resolution_ref,
            "resolved",
        )
        try:
            self._budget_middleware.complete_completion_obligation_safe(
                obligation_id,
                expected_digest=record.payload_digest,
                known_receipt_ids=record.known_receipt_ids,
                owner_resolution_ref=resolution_ref,
            )
        finally:
            self._completion_proofs.pop(obligation_id, None)
        self._completion_records.pop(obligation_id, None)

    def _abort_unstarted_intent(self, reservation: _BudgetReservation, run_id: str) -> None:
        """Release an intent only while the actual client call has never been entered."""
        if reservation.provider_started:
            raise RuntimeError("an entered provider attempt cannot be declared not admitted")
        record = self._completion_records.get(reservation.attempt_id)
        if record is None or self._budget_middleware is None:
            self._release_reservation(reservation, run_id=run_id, reason="not_admitted")
            return
        released_keys = [key for key, _ in reservation.outstanding_items()]
        self._completion_proofs[record.obligation_id] = (
            record.payload_digest,
            None,
            "not_admitted",
        )
        try:
            self._budget_middleware.abort_provider_intent_safe(
                record.obligation_id, expected_digest=record.payload_digest
            )
        finally:
            self._completion_proofs.pop(record.obligation_id, None)
        self._completion_records.pop(record.obligation_id, None)
        for key in reservation.reserved_amounts:
            reservation.clear_key(key)
        if released_keys:
            self._append_audit(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_RELEASED",
                metadata={
                    "budget_keys": released_keys,
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "model": self._model_name,
                    "reason": "not_admitted",
                },
                reservation=reservation,
            )

    @staticmethod
    def _audit_error(
        obligation: LLMAuditObligation, response: Any, cause: BaseException
    ) -> LLMAccountingError:
        return LLMAccountingError(
            response=response,
            event={
                "audit_obligation": obligation,
                "required_audit_status": "pending",
                "charge_ack": obligation.charge_ack,
                "settlement_status": (
                    obligation.charge_ack.status
                    if obligation.charge_ack is not None
                    else "unmanaged"
                ),
                "producer_event": obligation.event,
            },
            cause=cause,
        )

    def _append_audit(
        self,
        *,
        run_id: str,
        actor: str,
        action: Any,
        metadata: dict[str, Any],
        producer_event: LLMProducerEvent | None = None,
        charge_ack: LLMSettlementAck | None = None,
        response: Any = None,
        reservation: _BudgetReservation | None = None,
        act_id: str | None = None,
    ) -> None:
        if self._audit_log is None:
            return
        identity = act_id or "budget-audit:" + _new_producer_id()
        if identity in self._pending_audits:
            obligation, retained_response = self._pending_audits[identity]
            raise self._audit_error(
                obligation, retained_response, RuntimeError("resolve the original audit act first")
            )
        # Detach caller-owned nested values from the exact protected act.
        frozen_metadata = to_python_data(metadata)
        obligation = LLMAuditObligation(
            event=producer_event,
            run_id=run_id,
            scope_key=self._accounting_scope(run_id),
            charge_ack=charge_ack,
            action=action,
            actor=actor,
            act_id=identity,
            metadata=tuple(frozen_metadata.items()),
        )
        self._pending_audits[identity] = (obligation, response)
        self._audit_reservations[identity] = reservation or _BudgetReservation(Decimal(0))
        try:
            self._retain_completion(
                identity,
                producer_event,
                reservation or _BudgetReservation(Decimal(0)),
                run_id,
                "protected_audit_pending",
                charge_ack=charge_ack,
                required_action={
                    "run_id": run_id,
                    "actor": actor,
                    "action": action,
                    "metadata": frozen_metadata,
                },
            )
            self._audit_log.append(
                run_id=run_id, actor=actor, action=action, metadata=frozen_metadata
            )
            resolution = LLMAuditResolution(
                obligation.payload_digest, "committed", "local-audit-return:" + identity
            )
            self._completed_audits[identity] = resolution
            self._complete_record(identity, resolution.evidence_ref)
        except Exception as exc:
            raise self._audit_error(obligation, response, exc) from exc
        self._pending_audits.pop(identity, None)
        self._audit_reservations.pop(identity, None)
        self._completed_audits.pop(identity, None)

    def reconcile_required_audit(self, act_id: str) -> LLMSettlementAck:
        """Resolve only a retained act through this constructor's trusted audit owner.

        No provider request, monetary charge, or automatic audit append is issued.
        The resolver verifies the original durable act, including ambiguous effects.
        A diagnostic evidence reference alone cannot resolve an obligation.
        """
        obligation, response = self._pending_audits[act_id]
        resolved = self._completed_audits.get(act_id)
        if resolved is None and self._audit_reconciler is None:
            raise self._audit_error(
                obligation, response, RuntimeError("audit owner is unavailable")
            )
        try:
            if resolved is None:
                resolved = self._audit_reconciler(obligation)
            if not isinstance(resolved, LLMAuditResolution) or (
                resolved.obligation_digest != obligation.payload_digest
                or resolved.status != "committed"
                or not resolved.evidence_ref
            ):
                raise RuntimeError("audit owner did not verify the exact original obligation")
            self._completed_audits[act_id] = resolved
            if obligation.event is None:
                self._abort_unstarted_intent(self._audit_reservations[act_id], obligation.run_id)
            self._complete_record(act_id, resolved.evidence_ref)
        except Exception as exc:
            raise self._audit_error(obligation, response, exc) from exc
        self._pending_audits.pop(act_id, None)
        self._audit_reservations.pop(act_id, None)
        self._completed_audits.pop(act_id, None)
        if obligation.event is not None:
            if obligation.action == "BUDGET_COMMITTED":
                self._unknown_settlements.pop(obligation.event.event_id, None)
                self._retained_responses.pop(obligation.event.event_id, None)
                self._retained_run_ids.pop(obligation.event.event_id, None)
            elif obligation.event.event_id in self._unknown_settlements:
                pending = self._unknown_settlements[obligation.event.event_id]
                if obligation.charge_ack is not None:
                    self._finish_settlement(
                        pending[0], response, pending[1], obligation.run_id, obligation.charge_ack
                    )
        return obligation.charge_ack or LLMSettlementAck(
            obligation.act_id, obligation.payload_digest, "unmanaged"
        )

    def _accounting_scope(self, run_id: str) -> tuple[str, ...]:
        owner = (
            self._budget_middleware.settlement_owner_identity
            if self._budget_middleware is not None
            else ("memory-budget", str(id(self._budget_state)))
        )
        return (*owner, run_id, *sorted(self._budget_keys))

    @staticmethod
    def _ledger_event_identity(event: LLMProducerEvent, key: str) -> tuple[str, str]:
        key_digest = hashlib.sha256(key.encode()).hexdigest()
        event_id = f"{event.event_id}:budget:{key_digest}"
        payload_digest = hashlib.sha256(f"{event.payload_digest}:{key}".encode()).hexdigest()
        return event_id, payload_digest

    def _settle_event(
        self, event: LLMProducerEvent, response: Any, reservation: _BudgetReservation, run_id: str
    ) -> LLMSettlementAck:
        self._unknown_settlements[event.event_id] = (event, reservation)
        self._retained_responses[event.event_id] = response
        self._retained_run_ids[event.event_id] = run_id
        if event.amount is None:
            self._retain_completion(
                reservation.attempt_id or event.event_id, event, reservation, run_id, "cost_unknown"
            )
            raise LLMAccountingError(
                response=response,
                event={
                    "producer_event": event,
                    "settlement_status": "unknown",
                    "cost_origin": "unknown",
                },
                cause=RuntimeError(
                    "actual provider amount is unknown; retain the obtained operation"
                ),
            )
        receipts = []
        if event.kind == "provider" and self._budget_middleware is not None:
            self._retain_completion(
                reservation.attempt_id or event.event_id,
                event,
                reservation,
                run_id,
                "ledger_ack_unknown",
            )
            for key in self._budget_keys:
                event_id, payload_digest = self._ledger_event_identity(event, key)
                receipt = self._budget_middleware.settle_spend_safe(
                    event_id,
                    key,
                    event.amount,
                    provider=event.provider,
                    payload_digest=payload_digest,
                )
                self._validate_receipt(receipt, event_id, payload_digest, key, event)
                receipts.append(receipt)
            self._budget_state = self._budget_middleware.budget_state
        elif event.kind == "provider":
            self._post_record(
                response, reservation=reservation, run_id=run_id, producer_event=event
            )
        ack = LLMSettlementAck(
            event.event_id,
            event.payload_digest,
            "committed",
            tuple(receipts),
            "ledger" if self._budget_middleware is not None else "memory",
        )
        return self._finish_settlement(event, response, reservation, run_id, ack)

    def _finish_settlement(
        self,
        event: LLMProducerEvent,
        response: Any,
        reservation: _BudgetReservation,
        run_id: str,
        ack: LLMSettlementAck,
    ) -> LLMSettlementAck:
        metadata = {
            "producer_event_id": event.event_id,
            "payload_digest": event.payload_digest,
            "actual_cost_usd": str(event.amount),
            "settlement_status": "committed",
        }
        if self._budget_middleware is not None:
            self._retain_completion(
                reservation.attempt_id or event.event_id,
                event,
                reservation,
                run_id,
                "protected_audit_pending" if self._audit_log is not None else "ledger_ack_unknown",
                charge_ack=ack,
                required_action={
                    "run_id": run_id,
                    "actor": "budget_enforcer",
                    "action": "BUDGET_COMMITTED",
                    "metadata": metadata,
                }
                if self._audit_log is not None
                else None,
            )
        self._release_reservation(
            reservation,
            run_id=run_id,
            reason="producer_settled",
            producer_event=event,
            charge_ack=ack,
            response=response,
        )
        if self._audit_log is not None:
            self._append_audit(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_COMMITTED",
                metadata=metadata,
                producer_event=event,
                charge_ack=ack,
                response=response,
                reservation=reservation,
                act_id=reservation.attempt_id or event.event_id,
            )
        else:
            self._complete_record(reservation.attempt_id or event.event_id, None)
        self._unknown_settlements.pop(event.event_id, None)
        self._retained_responses.pop(event.event_id, None)
        self._retained_run_ids.pop(event.event_id, None)
        if self._budget_middleware is not None or event.kind == "reuse":
            try:
                self._emit_cost_metrics(event.amount, extract_llm_response_data(response))
            except Exception:
                logger.warning("Optional LLM budget metrics sink failed")
        return ack

    @staticmethod
    def _validate_receipt(
        receipt: Any, event_id: str, payload_digest: str, key: str, event: LLMProducerEvent
    ) -> None:
        from polisyos.scientist.orchestration.engine.budget_ledger import BudgetLedgerSpendReceipt

        if not isinstance(receipt, BudgetLedgerSpendReceipt) or (
            receipt.event_id != event_id
            or receipt.payload_digest != payload_digest
            or receipt.key != key
            or receipt.amount != event.amount
            or receipt.provider != event.provider
        ):
            raise RuntimeError("durable receipt conflicts with exact producer charge")

    def reconcile_settlement(
        self, event: LLMProducerEvent, *, retry_missing: bool = False
    ) -> LLMSettlementAck:
        """Resolve exact receipts or explicitly retry an owned, retained producer event.

        An absent receipt remains unknown by default. Retry can publish only the
        exact event already observed by this owner; caller-supplied events cannot
        manufacture provider evidence or issue a new provider request.
        """
        if self._budget_middleware is None:
            raise RuntimeError("durable reconciliation requires a budget ledger")
        if event.amount is None:
            return LLMSettlementAck(event.event_id, event.payload_digest, "unknown")
        retained = self._unknown_settlements.get(event.event_id)
        if retained is not None and retained[0] != event:
            raise ValueError("reconciliation event conflicts with retained producer evidence")
        if retry_missing and retained is None:
            raise ValueError("settlement retry requires this owner's retained producer event")
        receipts = []
        for key in self._budget_keys:
            event_id, payload_digest = self._ledger_event_identity(event, key)
            receipt = self._budget_middleware.resolve_spend_safe(event_id)
            if receipt is None and retry_missing:
                receipt = self._budget_middleware.settle_spend_safe(
                    event_id,
                    key,
                    event.amount,
                    provider=event.provider,
                    payload_digest=payload_digest,
                )
            if receipt is None:
                return LLMSettlementAck(event.event_id, event.payload_digest, "unknown")
            self._validate_receipt(receipt, event_id, payload_digest, key, event)
            receipts.append(receipt)
        pending = self._unknown_settlements.get(event.event_id)
        ack = LLMSettlementAck(
            event.event_id, event.payload_digest, "committed", tuple(receipts), "ledger"
        )
        if pending is not None:
            return self._finish_settlement(
                event,
                self._retained_responses.get(event.event_id),
                pending[1],
                self._retained_run_ids[event.event_id],
                ack,
            )
        # Read-only receipt resolution cannot erase a persisted owner obligation.
        return ack

    async def generate(self, **kwargs: Any) -> Any:
        """Run a budget-owned producer operation independently of caller cancellation."""
        task = asyncio.create_task(self._generate_owned(kwargs))
        self._owned_calls.add(task)

        def completed(done: asyncio.Task[Any]) -> None:
            self._owned_calls.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(completed)
        return await asyncio.shield(task)

    def _retain_failed_attempt(
        self, reservation: _BudgetReservation, run_id: str, cause: BaseException
    ) -> LLMAccountingError:
        observed = next(
            (event for event, owned in self._unknown_settlements.values() if owned is reservation),
            None,
        )
        event = observed or LLMProducerEvent(
            event_id=reservation.attempt_id,
            request_digest=reservation.request_digest,
            response_digest=_request_digest({"completion_failure_type": type(cause).__qualname__}),
            model=self._model_name,
            provider="unknown",
            amount=None,
            cost_origin="unknown",
        )
        response = self._retained_responses.get(event.event_id)
        self._unknown_settlements[event.event_id] = (event, reservation)
        self._retained_responses[event.event_id] = response
        self._retained_run_ids[event.event_id] = run_id
        publication_error = None
        try:
            self._retain_completion(
                reservation.attempt_id,
                event,
                reservation,
                run_id,
                "cost_unknown" if event.amount is None else "ledger_ack_unknown",
            )
        except Exception as exc:
            publication_error = exc
        return LLMAccountingError(
            response=response,
            event={
                "producer_event": event,
                "settlement_status": "unknown",
                "completion_publication_error": publication_error,
            },
            cause=cause,
        )

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        """Keep the asynchronous invoke producer and settlement owned after cancellation."""
        task = asyncio.create_task(self._generate_owned(kwargs, prompt=prompt))
        self._owned_calls.add(task)

        def completed(done: asyncio.Task[Any]) -> None:
            self._owned_calls.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(completed)
        return await asyncio.shield(task)

    async def _generate_owned(self, kwargs: dict[str, Any], *, prompt: str | None = None) -> Any:
        stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        producer_id = _new_producer_id()
        request_digest = _request_digest(
            {"args": () if prompt is None else (prompt,), "kwargs": stripped}
        )
        reservation = self._pre_check(
            kwargs if prompt is None else {"user": prompt, **kwargs},
            attempt_id=producer_id,
            request_digest=request_digest,
        )
        run_id = kwargs.get("_run_id", self._run_id)
        t0 = time.perf_counter()
        committed = False

        def settle(event: LLMProducerEvent, response: Any) -> LLMSettlementAck:
            nonlocal committed
            ack = self._settle_event(event, response, reservation, run_id)
            committed = ack.status == "committed"
            return ack

        try:
            with _settlement_owner_context(
                self._accounting_scope(run_id),
                settle,
                attempt_id=producer_id,
                request_digest=request_digest,
            ):
                reservation.provider_started = True
                if prompt is None:
                    response = await self._client.generate(**stripped)
                else:
                    response = await self._client.ainvoke(prompt, **stripped)
                if not committed:
                    data = extract_llm_response_data(response)
                    event = LLMProducerEvent(
                        event_id=producer_id,
                        request_digest=request_digest,
                        response_digest="sha256:"
                        + hashlib.sha256(str(data.content).encode()).hexdigest(),
                        model=data.model or self._model_name,
                        provider=data.provider or "unknown",
                        amount=_completion_amount(data, self._model_name)[0],
                        cost_origin=_completion_amount(data, self._model_name)[1],
                    )
                    settle(event, response)
            try:
                self._record_latency(time.perf_counter() - t0)
            except Exception:
                logger.warning("Optional LLM latency metrics sink failed")
            return response
        except LLMAccountingError:
            raise
        except BaseException as exc:
            if reservation.provider_started and not committed:
                failure = self._retain_failed_attempt(reservation, run_id, exc)
                if isinstance(exc, Exception):
                    raise failure from exc
            raise
        finally:
            if (
                not committed
                and not reservation.provider_started
                and reservation.has_outstanding()
                and not self._unknown_settlements
            ):
                self._abort_unstarted_intent(reservation, run_id)

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        """Budget-aware sync invoke wrapper."""
        stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        producer_id = _new_producer_id()
        request_digest = _request_digest({"args": (prompt,), "kwargs": stripped})
        reservation = self._pre_check(
            {"user": prompt, **kwargs},
            attempt_id=producer_id,
            request_digest=request_digest,
        )
        run_id = kwargs.get("_run_id", self._run_id)
        t0 = time.perf_counter()
        committed = False

        def settle(event: LLMProducerEvent, response: Any) -> LLMSettlementAck:
            nonlocal committed
            ack = self._settle_event(event, response, reservation, run_id)
            committed = ack.status == "committed"
            return ack

        try:
            stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            with _settlement_owner_context(
                self._accounting_scope(run_id),
                settle,
                attempt_id=producer_id,
                request_digest=request_digest,
            ):
                reservation.provider_started = True
                response = self._client.invoke(prompt, **stripped)
                if not committed:
                    data = extract_llm_response_data(response)
                    event = LLMProducerEvent(
                        event_id=producer_id,
                        request_digest=request_digest,
                        response_digest="sha256:"
                        + hashlib.sha256(str(data.content).encode()).hexdigest(),
                        model=data.model or self._model_name,
                        provider=data.provider or "unknown",
                        amount=_completion_amount(data, self._model_name)[0],
                        cost_origin=_completion_amount(data, self._model_name)[1],
                    )
                    settle(event, response)
            try:
                self._record_latency(time.perf_counter() - t0)
            except Exception:
                logger.warning("Optional LLM latency metrics sink failed")
            return response
        except LLMAccountingError:
            raise
        except BaseException as exc:
            if reservation.provider_started and not committed:
                failure = self._retain_failed_attempt(reservation, run_id, exc)
                if isinstance(exc, Exception):
                    raise failure from exc
            raise
        finally:
            if (
                not committed
                and not reservation.provider_started
                and reservation.has_outstanding()
                and not self._unknown_settlements
            ):
                self._abort_unstarted_intent(reservation, run_id)
