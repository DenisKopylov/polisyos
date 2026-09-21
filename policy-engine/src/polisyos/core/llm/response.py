"""Normalizes provider-specific LLM responses into one PolicyOS telemetry shape."""

from __future__ import annotations

from collections.abc import Mapping
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

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def extract_llm_response_data(response: Any) -> LLMResponseData:
    """Extract content, usage, model, and cost fields from heterogeneous LLM SDK responses."""
    content = response.content if hasattr(response, "content") else str(response)
    cache_hit, usage_origin = _extract_cache_provenance(response)
    prompt_tokens = 0
    completion_tokens = 0
    provider: str | None = None
    model: str | None = None
    cost_usd: float | None = None
    request_id: str | None = None

    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            cost_usd = _extract_cost_usd(
                usage=usage,
                payload=response,
            )
        elif isinstance(response, dict):
            usage = response.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(usage.get("completion_tokens", 0) or 0)
            cost_usd = _extract_cost_usd(usage=usage, payload=response)
        elif hasattr(response, "input_tokens"):
            prompt_tokens = int(getattr(response, "input_tokens", 0) or 0)
            completion_tokens = int(getattr(response, "output_tokens", 0) or 0)
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
        prompt_tokens = 0
        completion_tokens = 0
        provider = None
        model = None
        cost_usd = None
        request_id = None

    return LLMResponseData(
        content=content,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
        provider=provider,
        model=model,
        cost_usd=cost_usd,
        cache_hit=cache_hit,
        usage_origin=usage_origin,
        request_id=request_id,
    )


def _extract_cache_provenance(response: Any) -> tuple[bool, str]:
    """Read cache provenance without changing provider response semantics."""

    raw: Any
    if isinstance(response, Mapping):
        raw = response.get("raw")
        if raw is None:
            raw = response
    else:
        raw = getattr(response, "raw", None)
    if not isinstance(raw, Mapping):
        return False, "provider"
    marker = raw.get("_polisyos_cache")
    if not isinstance(marker, Mapping):
        return False, "provider"
    cache_hit = marker.get("status") == "hit"
    origin = marker.get("usage_origin")
    if not isinstance(origin, str) or not origin.strip():
        origin = "provider"
    return cache_hit, origin.strip()


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
