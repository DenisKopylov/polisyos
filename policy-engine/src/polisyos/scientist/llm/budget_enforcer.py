"""LLM budget enforcement wrapper."""

from __future__ import annotations

import time
import threading
from decimal import Decimal
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetState
from polisyos.scientist.llm.cost_anomaly import CostAnomalyDetector

logger = get_logger(__name__)


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
    ) -> None:
        self._client = client
        self._budget_state = budget_state
        self._budget_keys = budget_keys
        self._model_name = model_name
        self._audit_log = audit_log
        self._run_id = run_id
        self._lock = threading.Lock()
        self._anomaly_detector = CostAnomalyDetector()

    @property
    def budget_state(self) -> BudgetState:
        return self._budget_state

    def _pre_check(self, kwargs: dict[str, Any]) -> Decimal:
        """Estimate cost and check budget before an LLM call.

        Returns the estimated cost.
        Raises ``BudgetExhaustedError`` if any budget key would be exceeded.
        """
        max_tokens = kwargs.get("max_tokens", 4096)
        prompt_tokens = kwargs.get("_prompt_tokens_estimate", 0)
        if prompt_tokens == 0:
            from polisyos.scientist.llm.token_estimator import estimate_request_tokens
            prompt_tokens = estimate_request_tokens(
                system=kwargs.get("system"),
                user=kwargs.get("user"),
                tools=kwargs.get("tools"),
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

        with self._lock:
            for key in self._budget_keys:
                if self._budget_state.would_exceed(key, estimated):
                    remaining = self._budget_state.remaining(key)
                    if self._audit_log:
                        self._audit_log.append(
                            run_id=kwargs.get("_run_id", ""),
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

        if self._audit_log:
            self._audit_log.append(
                run_id=kwargs.get("_run_id", ""),
                actor="budget_enforcer",
                action="BUDGET_CHECK",
                metadata={
                    "budget_keys": self._budget_keys,
                    "estimated_cost_usd": str(estimated),
                    "model": self._model_name,
                },
            )
        return estimated

    def _post_record(self, response: Any) -> Decimal:
        """Extract actual cost from response and record spend."""
        try:
            data = extract_llm_response_data(response)
            actual_cost = Decimal(
                str(
                    estimate_llm_cost_usd(
                        model=self._model_name,
                        prompt_tokens=data.prompt_tokens,
                        completion_tokens=data.completion_tokens,
                    )
                )
            )
        except Exception:  # noqa: BLE001
            actual_cost = Decimal(0)
            data = None

        with self._lock:
            for key in self._budget_keys:
                self._budget_state.record_spend(key, actual_cost)
                if self._budget_state.is_soft_limit_exceeded(key):
                    logger.warning(
                        "Soft budget limit exceeded for key=%s, spent=%s",
                        key,
                        self._budget_state.spent.get(key),
                    )

        # Emit OTel metrics
        self._emit_cost_metrics(actual_cost, data)

        return actual_cost

    def _emit_cost_metrics(self, cost: Decimal, data: Any) -> None:
        """Emit LLM cost, token, and budget utilization metrics."""
        try:
            from polisyos.core.observability import get_metrics
            m = get_metrics()
        except Exception:  # noqa: BLE001
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
                "Anomalous LLM cost detected: $%.4f for model=%s",
                cost_f, self._model_name,
            )
            if m.scientist_llm_cost_anomalies_total is not None:
                m.scientist_llm_cost_anomalies_total.add(1, attrs)

    def _record_latency(self, elapsed_s: float) -> None:
        """Emit LLM call latency to OTel histogram."""
        try:
            from polisyos.core.observability import get_metrics
            m = get_metrics()
        except Exception:  # noqa: BLE001
            return
        if m.llm_latency_ms is not None:
            m.llm_latency_ms.record(
                elapsed_s * 1000.0, {"model_id": self._model_name},
            )

    async def generate(self, **kwargs: Any) -> Any:
        """Budget-aware async generate wrapper."""
        _stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        self._pre_check(kwargs)
        t0 = time.perf_counter()
        response = await self._client.generate(**_stripped)
        self._record_latency(time.perf_counter() - t0)
        self._post_record(response)
        return response

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        """Budget-aware sync invoke wrapper."""
        self._pre_check(kwargs)
        t0 = time.perf_counter()
        response = self._client.invoke(prompt, **kwargs)
        self._record_latency(time.perf_counter() - t0)
        self._post_record(response)
        return response
