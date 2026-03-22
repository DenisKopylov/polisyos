"""LLM budget enforcement wrapper."""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetState

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
    ) -> None:
        self._client = client
        self._budget_state = budget_state
        self._budget_keys = budget_keys
        self._model_name = model_name
        self._audit_log = audit_log
        self._lock = threading.Lock()

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
            # Rough estimate: 1 char ≈ 0.25 tokens
            system_text = kwargs.get("system", "") or ""
            user_text = kwargs.get("user", "") or ""
            prompt_tokens = (len(system_text) + len(user_text)) // 4

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

        with self._lock:
            for key in self._budget_keys:
                self._budget_state.record_spend(key, actual_cost)
                if self._budget_state.is_soft_limit_exceeded(key):
                    logger.warning(
                        "Soft budget limit exceeded for key=%s, spent=%s",
                        key,
                        self._budget_state.spent.get(key),
                    )
        return actual_cost

    async def generate(self, **kwargs: Any) -> Any:
        """Budget-aware async generate wrapper."""
        _stripped = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        self._pre_check(kwargs)
        response = await self._client.generate(**_stripped)
        self._post_record(response)
        return response

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        """Budget-aware sync invoke wrapper."""
        self._pre_check(kwargs)
        response = self._client.invoke(prompt, **kwargs)
        self._post_record(response)
        return response
