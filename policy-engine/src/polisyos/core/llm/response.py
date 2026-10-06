"""Normalizes provider-specific LLM responses into one PolicyOS telemetry shape."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Literal

LLMUsageStatus = Literal["known", "missing", "invalid"]
_INVALID_FIELD = object()


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
    usage_status: LLMUsageStatus = "missing"
    cost_status: LLMUsageStatus = "missing"

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

    usage = _field(response, "usage")
    prompt_value = _field(usage, "prompt_tokens")
    completion_value = _field(usage, "completion_tokens")
    if usage is None:
        prompt_value = _field(response, "input_tokens")
        completion_value = _field(response, "output_tokens")
    prompt_count = _usage_token(prompt_value)
    completion_count = _usage_token(completion_value)
    usage_status: LLMUsageStatus = "known"
    if (prompt_value is not None and prompt_count is None) or (
        completion_value is not None and completion_count is None
    ):
        usage_status = "invalid"
    elif prompt_value is None or completion_value is None:
        usage_status = "missing"
    declared_usage = _field(usage, "usage_status")
    if declared_usage in ("missing", "invalid"):
        usage_status = declared_usage
    origin_prompt_tokens = prompt_count or 0
    origin_completion_tokens = completion_count or 0
    cost_usd, cost_status = _extract_cost_data(usage=usage, payload=response)
    declared_cost = _field(usage, "cost_status")
    if declared_cost == "invalid":
        cost_usd, cost_status = None, "invalid"
    provider = _as_str(_field(response, "provider"))
    model = _as_str(_field(response, "model"))
    request_id = _as_str(_field(response, "request_id"))

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
        usage_status=usage_status,
        cost_status=cost_status,
    )


def _extract_cache_provenance(
    response: Any,
) -> tuple[bool, str, str | None, str | None]:
    """Read cache provenance only from the internal cache-owned envelope.

    Provider ``raw`` payloads are data, not authority over billing.  The
    cache wrapper attaches these private fields to the response it returns;
    a provider-supplied ``_polisyos_cache`` mapping is intentionally ignored.
    """

    from .settlement import _cache_reuse_provenance

    provenance = _cache_reuse_provenance(response)
    if provenance is None:
        return False, "provider", None, None
    return True, "provider", provenance.reuse_event_id, provenance.cache_key


def _extract_physical_provider_response_data(response: Any) -> LLMResponseData:
    """A known physical provider completion is billable even with borrowed reuse data."""
    parsed = extract_llm_response_data(response)
    return replace(
        parsed,
        prompt_tokens=parsed.origin_prompt_tokens or 0,
        completion_tokens=parsed.origin_completion_tokens or 0,
        cost_usd=parsed.origin_cost_usd,
        cache_hit=False,
        reuse_event_id=None,
        cache_key=None,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        exact = Decimal(str(value))
        parsed = float(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    if (
        not exact.is_finite()
        or exact < 0
        or not Decimal(str(parsed)).is_finite()
        or (parsed == 0 and exact != 0)
    ):
        return None
    return parsed


def _field(value: Any, key: str) -> Any:
    try:
        return value.get(key) if isinstance(value, dict) else getattr(value, key, None)
    except Exception:
        # An obtained response remains available; inaccessible monetary/usage
        # evidence is invalid, rather than a missing field eligible for pricing.
        return _INVALID_FIELD


def _usage_token(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _extract_cost_data(*, usage: Any, payload: Any) -> tuple[float | None, LLMUsageStatus]:
    candidates = [
        _field(usage, "total_cost_usd"),
        _field(usage, "cost_usd"),
        _field(usage, "cost"),
    ]
    if isinstance(usage, dict):
        candidates.extend(
            [
                usage.get("total_cost_usd"),
                usage.get("cost_usd"),
                usage.get("cost"),
            ]
        )
        base_value = usage.get("base_cost_usd")
        fee_value = usage.get("platform_fee_usd")
        if base_value is not None or fee_value is not None:
            base_cost = _as_float(base_value) if base_value is not None else 0.0
            platform_fee = _as_float(fee_value) if fee_value is not None else 0.0
            candidates.append(
                base_cost + platform_fee
                if base_cost is not None and platform_fee is not None
                else "invalid cost component"
            )
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
                _field(payload, "total_cost_usd"),
                _field(payload, "cost_usd"),
                _field(payload, "cost"),
            ]
        )

    for candidate in candidates:
        if candidate is not None:
            parsed = _as_float(candidate)
            return parsed, "known" if parsed is not None else "invalid"
    return None, "missing"


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
