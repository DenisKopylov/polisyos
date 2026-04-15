"""LLM budget enforcement wrapper."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.engine.operational_monitoring import get_operational_monitor
from polisyos.scientist.error_semantics import emit_degraded_path
from polisyos.scientist.llm.cost_anomaly import CostAnomalyDetector

logger = get_logger(__name__)

_OBSERVABILITY_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.engine.operational_monitoring import ScientistOperationalMonitor


@dataclass(slots=True)
class _BudgetReservation:
    estimated_cost: Decimal
    reserved_amounts: dict[str, Decimal] = field(default_factory=dict)

    def outstanding_items(self) -> list[tuple[str, Decimal]]:
        return [
            (key, amount)
            for key, amount in self.reserved_amounts.items()
            if amount > 0
        ]

    def clear_key(self, key: str) -> None:
        if key in self.reserved_amounts:
            self.reserved_amounts[key] = Decimal(0)

    def has_outstanding(self) -> bool:
        return any(amount > 0 for amount in self.reserved_amounts.values())


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
    ) -> None:
        self._client = client
        self._budget_state = budget_state
        self._budget_keys = budget_keys
        self._model_name = model_name
        self._audit_log = audit_log
        self._run_id = run_id
        self._lock = threading.Lock()
        self._anomaly_detector = CostAnomalyDetector()
        self._metrics = metrics
        self._operational_monitor = operational_monitor

    @property
    def budget_state(self) -> BudgetState:
        return self._budget_state

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
            from polisyos.scientist.llm.token_estimator import estimate_request_tokens
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

    def _pre_check(self, kwargs: dict[str, Any]) -> _BudgetReservation:
        """Estimate cost, reserve budget, and reject calls that cannot fit."""
        estimated = self._estimate_cost(kwargs)
        run_id = kwargs.get("_run_id", "")

        reserved_keys: list[str] = []
        reservation = _BudgetReservation(estimated_cost=estimated)
        with self._lock:
            for key in self._budget_keys:
                has_limit = key in self._budget_state.limits
                if not self._budget_state.reserve(key, estimated):
                    remaining = self._budget_state.remaining(key)
                    for reserved_key in reserved_keys:
                        reserved_amount = reservation.reserved_amounts.get(
                            reserved_key,
                            Decimal(0),
                        )
                        if reserved_amount > 0:
                            self._budget_state.release(reserved_key, reserved_amount)
                            reservation.clear_key(reserved_key)
                    if self._audit_log:
                        self._audit_log.append(
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
            self._audit_log.append(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_RESERVED",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(estimated),
                    "model": self._model_name,
                },
            )
            self._audit_log.append(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_CHECK",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(estimated),
                    "model": self._model_name,
                },
            )
        return reservation

    def _release_reservation(
        self,
        reservation: _BudgetReservation,
        *,
        run_id: str,
        reason: str,
    ) -> None:
        """Release any outstanding reservation for the current call."""
        released_keys: list[str] = []
        with self._lock:
            for key, reserved in reservation.outstanding_items():
                self._budget_state.release(key, reserved)
                reservation.clear_key(key)
                released_keys.append(key)

        if released_keys and self._audit_log:
            self._audit_log.append(
                run_id=run_id,
                actor="budget_enforcer",
                action="BUDGET_RELEASED",
                metadata={
                    "budget_keys": released_keys,
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "model": self._model_name,
                    "reason": reason,
                },
            )

    def _post_record(
        self,
        response: Any,
        *,
        reservation: _BudgetReservation,
        run_id: str,
    ) -> Decimal:
        """Extract actual cost from response and commit the reservation."""
        data = extract_llm_response_data(response)
        try:
            actual_cost = self._resolve_actual_cost(data)
        except (ArithmeticError, TypeError, ValueError) as exc:
            emit_degraded_path(
                component="llm.budget_enforcer",
                operation="post_record",
                reason="cost_accounting_fallback",
                exc=exc,
                details={
                    "estimated_cost_usd": str(reservation.estimated_cost),
                    "model": self._model_name,
                    "run_id": run_id,
                },
                log=logger,
                metrics=self._resolve_metrics(),
            )
            # Budget-critical path prefers conservative accounting over silent under-charge.
            actual_cost = reservation.estimated_cost

        with self._lock:
            for key in self._budget_keys:
                reserved = reservation.reserved_amounts.get(key, Decimal(0))
                if reserved > 0:
                    self._budget_state.release(key, reserved)
                    reservation.clear_key(key)
                self._budget_state.record_spend(key, actual_cost)
                if self._budget_state.is_soft_limit_exceeded(key):
                    logger.warning(
                        "Soft budget limit exceeded for key={}, spent={}",
                        key,
                        self._budget_state.spent.get(key),
                    )

        if self._audit_log:
            self._audit_log.append(
                run_id=run_id,
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
        self._emit_cost_metrics(actual_cost, data)

        return actual_cost

    def _resolve_actual_cost(self, data: Any) -> Decimal:
        if data.cost_usd is not None:
            return self._coerce_cost_decimal(data.cost_usd)
        estimated_cost = estimate_llm_cost_usd(
            model=self._model_name,
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
        )
        return self._coerce_cost_decimal(estimated_cost)

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
                data.prompt_tokens, {**attrs, "direction": "input"},
            )
            m.llm_tokens_total.add(
                data.completion_tokens, {**attrs, "direction": "output"},
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
                elapsed_s * 1000.0, {"model_id": self._model_name},
            )

    def _resolve_metrics(self) -> MetricsRegistry | None:
        if self._metrics is not None:
            return self._metrics
        try:
            from polisyos.core.observability import get_metrics
        except _OBSERVABILITY_IMPORT_ERRORS:
            return None
        self._metrics = get_metrics()
        return self._metrics

    def _resolve_operational_monitor(self) -> ScientistOperationalMonitor | None:
        if self._operational_monitor is not None:
            return self._operational_monitor
        try:
            monitor = get_operational_monitor()
        except _OBSERVABILITY_IMPORT_ERRORS:
            return None
        self._operational_monitor = monitor
        return self._operational_monitor

    async def generate(self, **kwargs: Any) -> Any:
        """Budget-aware async generate wrapper."""
        _stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        reservation = self._pre_check(kwargs)
        run_id = kwargs.get("_run_id", "")
        t0 = time.perf_counter()
        committed = False
        try:
            response = await self._client.generate(**_stripped)
            self._record_latency(time.perf_counter() - t0)
            self._post_record(
                response,
                reservation=reservation,
                run_id=run_id,
            )
            committed = True
            return response
        finally:
            if not committed and reservation.has_outstanding():
                self._release_reservation(
                    reservation,
                    run_id=run_id,
                    reason="generate_error",
                )

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        """Budget-aware sync invoke wrapper."""
        reservation = self._pre_check(kwargs)
        run_id = kwargs.get("_run_id", "")
        t0 = time.perf_counter()
        committed = False
        try:
            response = self._client.invoke(prompt, **kwargs)
            self._record_latency(time.perf_counter() - t0)
            self._post_record(
                response,
                reservation=reservation,
                run_id=run_id,
            )
            committed = True
            return response
        finally:
            if not committed and reservation.has_outstanding():
                self._release_reservation(
                    reservation,
                    run_id=run_id,
                    reason="invoke_error",
                )
