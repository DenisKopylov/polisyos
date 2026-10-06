"""Normalizes provider-specific LLM responses into one PolicyOS telemetry shape."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any


class _InvalidLLMCostError(ValueError):
    """A present provider cost is invalid; it cannot become absent or zero."""


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
        if isinstance(response, dict):
            usage = response.get("usage")
        cost_usd = _extract_cost_usd(usage=usage, payload=response)
        provider = _as_str(getattr(response, "provider", None))
        model = _as_str(getattr(response, "model", None))
        request_id = _as_str(getattr(response, "request_id", None))
        if isinstance(response, dict):
            provider = provider or _as_str(response.get("provider"))
            model = model or _as_str(response.get("model"))
            request_id = request_id or _as_str(response.get("request_id"))
        if usage is not None and not isinstance(response, dict):
            origin_prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            origin_completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        elif isinstance(response, dict):
            usage = response.get("usage") or {}
            origin_prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            origin_completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        elif hasattr(response, "input_tokens"):
            origin_prompt_tokens = int(getattr(response, "input_tokens", 0) or 0)
            origin_completion_tokens = int(getattr(response, "output_tokens", 0) or 0)
    except _InvalidLLMCostError:
        raise
    except Exception:
        origin_prompt_tokens = 0
        origin_completion_tokens = 0
        # Usage counts are ancillary to an independently admitted paid receipt.
        # Invalid token metadata must not turn known provider spend into absence.

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
    """Consume B's receiver-bound operational cache capability, not a type marker."""
    from .settlement import _cache_reuse_provenance

    provenance = _cache_reuse_provenance(response)
    if provenance is None:
        return False, "provider", None, None
    return True, "provider", provenance.reuse_event_id, provenance.cache_key


def _extract_physical_provider_response_data(response: Any) -> LLMResponseData:
    """Preserve B's billable physical-completion boundary with strict D cost intake."""
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
        raise _InvalidLLMCostError("provider cost cannot be boolean")
    if not isinstance(value, (int, float, Decimal, str)):
        raise _InvalidLLMCostError("provider cost must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _InvalidLLMCostError("provider cost must be finite and nonnegative") from exc
    if not isfinite(parsed) or parsed < 0:
        raise _InvalidLLMCostError("provider cost must be finite and nonnegative")
    if parsed == 0:
        try:
            original_is_zero = Decimal(str(value)) == 0
        except InvalidOperation as exc:
            raise _InvalidLLMCostError("provider cost must be numeric") from exc
        if not original_is_zero:
            raise _InvalidLLMCostError("nonzero provider cost cannot normalize to zero")
    return parsed


def _extract_cost_usd(*, usage: Any, payload: Any) -> float | None:
    def field(source: Any, name: str) -> Any:
        return source.get(name) if isinstance(source, dict) else getattr(source, name, None)

    sources: tuple[Any, ...] = (usage, payload)
    raw = field(payload, "raw")
    raw_sources: tuple[Any, ...] = ()
    if isinstance(raw, dict):
        # The native Gateway retains its original report here. Its normalized
        # envelope can erase a negative amount or a finite, falsy zero. Preserve
        # the original fields' first-present order, while validating both forms.
        raw_sources = (field(raw, "usage"), raw)

    def declared_totals(group: tuple[Any, ...]) -> list[Decimal]:
        totals = []
        for source in group:
            # Validate all declarations before selecting a basis. Each alias is
            # a USD total; base + platform fee is the existing component total.
            for name in ("total_cost_usd", "cost_usd", "cost"):
                value = field(source, name)
                if _as_float(value) is not None:
                    totals.append(Decimal(str(value)))
            components = [field(source, name) for name in ("base_cost_usd", "platform_fee_usd")]
            admitted = [_as_float(value) for value in components]
            if any(value is not None for value in admitted):
                total = sum(
                    (Decimal(str(value)) for value in components if value is not None), Decimal(0)
                )
                _as_float(total)
                totals.append(total)
        return totals

    original_totals = declared_totals(raw_sources)
    normalized_totals = declared_totals(sources)
    # The original report establishes the total; its envelope must agree with
    # that total or the Gateway's explicit float component-addition relation.
    totals = original_totals or normalized_totals
    if not totals:
        return None
    if any(total != totals[0] for total in totals[1:]):
        raise _InvalidLLMCostError("conflicting provider cost declarations in USD")
    if original_totals:
        allowed_normalized = {totals[0], Decimal(str(_as_float(totals[0])))}
        if not any(
            field(source, name) is not None
            for source in raw_sources
            for name in ("total_cost_usd", "cost_usd", "cost")
        ):
            raw_usage = field(raw, "usage")
            components = [
                _as_float(field(raw_usage, name)) for name in ("base_cost_usd", "platform_fee_usd")
            ]
            if any(value is not None for value in components):
                # Native Gateway performs binary float addition for these two
                # components. Admit that exact relation, not arbitrary rounding.
                allowed_normalized.add(Decimal(str(sum(value or 0.0 for value in components))))
        if any(total not in allowed_normalized for total in normalized_totals):
            raise _InvalidLLMCostError(
                "conflicting provider cost across original and normalized USD declarations"
            )
    return _as_float(totals[0])


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
