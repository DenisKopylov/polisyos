"""Normalizes provider-specific LLM responses into one PolicyOS telemetry shape."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Literal

LLMUsageStatus = Literal["known", "missing", "invalid"]
_INVALID_FIELD = object()


@dataclass(frozen=True)
class LLMLocalSpendReceipt:
    """Read-only view returned by an existing configured local ledger adapter."""

    event_id: str
    payload_digest: str
    key: str
    amount: Decimal
    provider: str | None


_LOCAL_RECEIPT_RESOLVER: ContextVar[Callable[[Any], LLMLocalSpendReceipt | None] | None] = (
    ContextVar("llm_local_receipt_resolver", default=None)
)


@contextmanager
def llm_local_receipt_resolver(
    resolver: Callable[[Any], LLMLocalSpendReceipt | None] | None,
) -> Iterator[None]:
    """Supply operational readback; this port never settles or grants permission."""
    token = _LOCAL_RECEIPT_RESOLVER.set(resolver)
    try:
        yield
    finally:
        _LOCAL_RECEIPT_RESOLVER.reset(token)


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


def extract_llm_response_data(
    response: Any, *, _physical_provider: bool = False
) -> LLMResponseData:
    """Extract content, usage, model, and cost fields from heterogeneous LLM SDK responses."""
    from .settlement import LLMSettledResponse

    if isinstance(response, LLMSettledResponse):
        response = response.response
    content = response.content if hasattr(response, "content") else str(response)
    cache_hit, usage_origin, reuse_event_id, cache_key = (
        (False, "provider", None, None)
        if _physical_provider
        else _extract_cache_provenance(response)
    )
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
    """Recognize B's receiver-bound operational capability, not a financial debit."""
    from .settlement import _cache_reuse_provenance

    provenance = _cache_reuse_provenance(response)
    if provenance is None:
        return False, "provider", None, None
    return True, "provider", provenance.reuse_event_id, provenance.cache_key


def _require_durable_cache_reuse(response: Any) -> None:
    """Admit zero new charge only after the current paid-origin ledger readback.

    Generic cache discovery remains B's operational receiver capability. This
    existing financial predicate runs before a durable D owner issues its ACK.
    """
    from .settlement import (
        LLMProducerSettlement,
        LLMSettledResponse,
        _cache_reuse_provenance,
        producer_settlement,
    )

    if isinstance(response, LLMSettledResponse):
        response = response.response

    provenance = _cache_reuse_provenance(response)
    if provenance is None:
        raise ValueError("durable cache reuse requires current receiver capability")
    origin = producer_settlement(response)
    resolver = _LOCAL_RECEIPT_RESOLVER.get()
    if not isinstance(origin, LLMProducerSettlement) or resolver is None:
        raise ValueError(
            "cache reuse requires original producer settlement and local receipt readback"
        )
    event, ack = origin.event, origin.ack
    content = getattr(response, "content", None)
    if (
        not isinstance(content, str)
        or event.kind != "provider"
        or event.request_digest != provenance.request_digest
        or event.response_digest != "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        or event.model != getattr(response, "model", None)
        or event.provider != getattr(response, "provider", None)
        or ack.status != "committed"
        or ack.durability != "ledger"
        or not ack.receipts
    ):
        raise ValueError(
            "cache reuse does not bind original response content/context and paid receipt"
        )
    for declared in ack.receipts:
        receipt = resolver(declared)
        if not isinstance(receipt, LLMLocalSpendReceipt):
            raise ValueError("cache reuse receipt readback unavailable")
        expected_id = f"{event.event_id}:budget:{hashlib.sha256(receipt.key.encode()).hexdigest()}"
        expected_digest = hashlib.sha256(
            f"{event.payload_digest}:{receipt.key}".encode()
        ).hexdigest()
        if (
            receipt.event_id != expected_id
            or receipt.payload_digest != expected_digest
            or receipt.amount != event.amount
            or receipt.provider != event.provider
        ):
            raise ValueError("cache reuse receipt conflicts with original producer input")
    reported = _extract_cost_usd(usage=getattr(response, "usage", None), payload=response)
    if event.cost_origin == "reported" and (
        reported is None or Decimal(str(reported)) != event.amount
    ):
        raise ValueError("cache reuse reported cost conflicts with original paid receipt")
    if event.cost_origin == "estimated" and reported is not None:
        raise ValueError("cache reuse cannot relabel an estimated origin as reported cost")


def _extract_physical_provider_response_data(response: Any) -> LLMResponseData:
    """Preserve B's billable physical-completion boundary with strict D cost intake."""
    parsed = extract_llm_response_data(response, _physical_provider=True)
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
    try:
        value = _extract_cost_usd(usage=usage, payload=payload)
    except _InvalidLLMCostError:
        return None, "invalid"
    return value, "known" if value is not None else "missing"


def _extract_cost_usd(*, usage: Any, payload: Any) -> float | None:
    def field(source: Any, name: str) -> Any:
        return _field(source, name)

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
            if isinstance(source, dict) and any(
                name in source and source[name] is None
                for name in (
                    "total_cost_usd",
                    "cost_usd",
                    "cost",
                    "base_cost_usd",
                    "platform_fee_usd",
                )
            ):
                raise _InvalidLLMCostError("present provider cost cannot be null")
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
