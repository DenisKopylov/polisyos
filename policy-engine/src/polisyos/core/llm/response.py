"""Normalizes provider-specific LLM responses into one PolicyOS telemetry shape."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class LLMResponseData:
    """LLM response data public type."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    provider: str | None = None
    model: str | None = None
    cost_usd: float | None = None
    cache_hit: bool = False
    usage_origin: str = "provider"
    request_id: str | None = None
    origin_prompt_tokens: int | None = None
    origin_completion_tokens: int | None = None
    origin_cost_usd: float | None = None
    reuse_event_id: str | None = None
    cache_key: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def origin_total_tokens(self) -> int:
        """Return provider usage retained as provenance for cache reuse."""

        prompt_tokens = self.origin_prompt_tokens
        completion_tokens = self.origin_completion_tokens
        if prompt_tokens is None:
            prompt_tokens = self.prompt_tokens
        if completion_tokens is None:
            completion_tokens = self.completion_tokens
        return prompt_tokens + completion_tokens


def extract_llm_response_data(response: Any) -> LLMResponseData:
    """Extract content, usage, model, and cost fields from heterogeneous LLM SDK responses."""
    from .settlement import LLMSettledResponse

    if isinstance(response, LLMSettledResponse):
        response = response.response
    content = response.content if hasattr(response, "content") else str(response)
    cache_hit, usage_origin, reuse_event_id, cache_key = _extract_cache_provenance(response)
    origin_prompt_tokens = 0
    origin_completion_tokens = 0
    provider: str | None = None
    model: str | None = None
    cost_usd: float | None = None
    request_id: str | None = None

    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            origin_prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            origin_completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            cost_usd = _extract_cost_usd(
                usage=usage,
                payload=response,
            )
        elif isinstance(response, dict):
            usage = response.get("usage", {})
            origin_prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            origin_completion_tokens = int(usage.get("completion_tokens", 0) or 0)
            cost_usd = _extract_cost_usd(usage=usage, payload=response)
        elif hasattr(response, "input_tokens"):
            origin_prompt_tokens = int(getattr(response, "input_tokens", 0) or 0)
            origin_completion_tokens = int(getattr(response, "output_tokens", 0) or 0)
        provider = _as_str(getattr(response, "provider", None))
        model = _as_str(getattr(response, "model", None))
        request_id = _as_str(getattr(response, "request_id", None))
        if isinstance(response, dict):
            provider = provider or _as_str(response.get("provider"))
            model = model or _as_str(response.get("model"))
            request_id = request_id or _as_str(response.get("request_id"))
            if cost_usd is None:
                cost_usd = _extract_cost_usd(
                    usage=response.get("usage"),
                    payload=response,
                )
    except Exception:
        origin_prompt_tokens = 0
        origin_completion_tokens = 0
        provider = None
        model = None
        cost_usd = None
        request_id = None

    reported_cost_usd = cost_usd
    billable_prompt_tokens = 0 if cache_hit else origin_prompt_tokens
    billable_completion_tokens = 0 if cache_hit else origin_completion_tokens
    billable_cost_usd = 0.0 if cache_hit else reported_cost_usd

    return LLMResponseData(
        content=content,
        prompt_tokens=max(0, billable_prompt_tokens),
        completion_tokens=max(0, billable_completion_tokens),
        provider=provider,
        model=model,
        cost_usd=billable_cost_usd,
        cache_hit=cache_hit,
        usage_origin=usage_origin,
        request_id=request_id,
        origin_prompt_tokens=max(0, origin_prompt_tokens),
        origin_completion_tokens=max(0, origin_completion_tokens),
        origin_cost_usd=reported_cost_usd,
        reuse_event_id=reuse_event_id,
        cache_key=cache_key,
    )


def _extract_cache_provenance(
    response: Any,
) -> tuple[bool, str, str | None, str | None]:
    """Read cache provenance only from the internal cache-owned envelope.

    Provider ``raw`` payloads are data, not authority over billing.  The
    cache wrapper attaches these private fields to the response it returns;
    a provider-supplied ``_polisyos_cache`` mapping is intentionally ignored.
    """

    response_type = type(response)
    cache_hit = (
        response_type.__name__ == "_CacheReuseGatewayResponse"
        and response_type.__module__.endswith(".prompt_cache")
        and getattr(response, "_polisyos_cache_hit", False) is True
    )
    if not cache_hit:
        return False, "provider", None, None
    reuse_event_id = _as_str(getattr(response, "_polisyos_reuse_event_id", None))
    cache_key = _as_str(getattr(response, "_polisyos_cache_key", None))
    return True, "provider", reuse_event_id, cache_key


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return 0.0
    return parsed


def _extract_cost_usd(*, usage: Any, payload: Any) -> float | None:
    candidates = [
        getattr(usage, "total_cost_usd", None) if usage is not None else None,
        getattr(usage, "cost_usd", None) if usage is not None else None,
        getattr(usage, "cost", None) if usage is not None else None,
    ]
    if isinstance(usage, dict):
        candidates.extend(
            [
                usage.get("total_cost_usd"),
                usage.get("cost_usd"),
                usage.get("cost"),
            ]
        )
        base_cost = _as_float(usage.get("base_cost_usd"))
        platform_fee = _as_float(usage.get("platform_fee_usd"))
        if base_cost is not None or platform_fee is not None:
            candidates.append((base_cost or 0.0) + (platform_fee or 0.0))
    if isinstance(payload, dict):
        candidates.extend(
            [
                payload.get("total_cost_usd"),
                payload.get("cost_usd"),
                payload.get("cost"),
            ]
        )
    else:
        candidates.extend(
            [
                getattr(payload, "total_cost_usd", None),
                getattr(payload, "cost_usd", None),
                getattr(payload, "cost", None),
            ]
        )

    for candidate in candidates:
        parsed = _as_float(candidate)
        if parsed is not None:
            return parsed
    return None


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
