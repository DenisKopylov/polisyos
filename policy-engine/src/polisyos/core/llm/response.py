"""Normalize provider usage while preserving missing and invalid evidence."""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from .settlement import LLMSettledResponse, _CacheReuseOwner

LLMUsageStatus = Literal["known", "missing", "invalid"]


@dataclass(frozen=True)
class LLMResponseData:
    """Normalized response data with independent usage and cost parse status."""

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
    origin_event_id: str | None = None
    cache_key: str | None = None
    reuse_request_digest: str | None = None
    usage_status: LLMUsageStatus = "missing"
    cost_status: LLMUsageStatus = "missing"
    cost_origin: Literal["reported", "estimated", "reuse", "unknown"] | None = None
    settlement_status: Literal["committed", "unknown", "unmanaged"] | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def origin_total_tokens(self) -> int:
        """Return provider usage retained as provenance for cache reuse."""
        prompt_tokens = self.origin_prompt_tokens
        completion_tokens = self.origin_completion_tokens
        return (self.prompt_tokens if prompt_tokens is None else prompt_tokens) + (
            self.completion_tokens if completion_tokens is None else completion_tokens
        )


def extract_llm_response_data(response: Any, *, cache_reuse_owner: Any = None) -> LLMResponseData:
    """Extract usage without converting absent, malformed, or negative data to zero."""
    settlement = response.settlement if type(response) is LLMSettledResponse else None
    if settlement is not None:
        response = response.response

    (
        cache_hit,
        reuse_event_id,
        cache_key,
        origin_event_id,
        reuse_request_digest,
    ) = _extract_cache_provenance(response, owner=cache_reuse_owner)
    content = response.content if hasattr(response, "content") else str(response)
    usage = _get(response, "usage")
    payload = response
    prompt_tokens, completion_tokens, usage_status = _parse_usage(usage, response)
    cost_usd, cost_status = _parse_cost(usage, payload)
    provider = _as_str(_get(response, "provider"))
    model = _as_str(_get(response, "model"))
    request_id = _as_str(_get(response, "request_id"))
    if isinstance(response, dict):
        provider = provider or _as_str(response.get("provider"))
        model = model or _as_str(response.get("model"))
        request_id = request_id or _as_str(response.get("request_id"))

    if cache_hit:
        prompt_tokens_billable = completion_tokens_billable = 0
        cost_usd_billable: float | None = 0.0
        cost_status_billable: LLMUsageStatus = "known"
        usage_status_billable: LLMUsageStatus = "known"
    else:
        prompt_tokens_billable, completion_tokens_billable = prompt_tokens, completion_tokens
        cost_usd_billable, cost_status_billable = cost_usd, cost_status
        usage_status_billable = usage_status

    # A settled envelope is the event authority for cost origin. Parsing remains
    # the evidence status; producer origin is exposed separately by the settlement.
    if settlement is not None:
        event = getattr(settlement, "event", None)
        ack = getattr(settlement, "ack", None)
        amount = getattr(event, "amount", None)
        origin = getattr(event, "cost_origin", None)
        if origin == "reuse":
            cache_hit = True
            prompt_tokens_billable = completion_tokens_billable = 0
            cost_usd_billable = 0.0
        elif amount is None:
            cost_usd_billable = None
        else:
            cost_usd_billable = float(amount)
        settlement_status = getattr(ack, "status", None)
    else:
        origin = None
        settlement_status = None

    return LLMResponseData(
        content=content,
        prompt_tokens=prompt_tokens_billable,
        completion_tokens=completion_tokens_billable,
        provider=provider,
        model=model,
        cost_usd=cost_usd_billable,
        cache_hit=cache_hit,
        usage_origin="reuse" if cache_hit else "provider",
        request_id=request_id,
        origin_prompt_tokens=prompt_tokens,
        origin_completion_tokens=completion_tokens,
        origin_cost_usd=cost_usd,
        reuse_event_id=reuse_event_id,
        origin_event_id=origin_event_id,
        cache_key=cache_key,
        reuse_request_digest=reuse_request_digest,
        usage_status=usage_status_billable,
        cost_status=cost_status_billable,
        cost_origin=origin,
        settlement_status=settlement_status,
    )


def _extract_cache_provenance(
    response: Any, *, owner: Any = None
) -> tuple[bool, str | None, str | None, str | None, str | None]:
    """Accept reuse only from an owner-verified in-process provenance object."""
    provenance = getattr(response, "_polisyos_reuse_provenance", None)
    if type(owner) is not _CacheReuseOwner or provenance is None:
        return False, None, None, None, None
    verify = getattr(owner, "verify_provenance", None)
    if not callable(verify) or not verify(provenance):
        return False, None, None, None, None
    return (
        True,
        _as_str(getattr(provenance, "reuse_event_id", None)),
        _as_str(getattr(provenance, "cache_key", None)),
        _as_str(getattr(provenance, "origin_event_id", None)),
        _as_str(getattr(provenance, "request_digest", None)),
    )


def _parse_usage(usage: Any, payload: Any) -> tuple[int, int, LLMUsageStatus]:
    explicit = _explicit_status(usage, payload, "usage_status")
    prompt = _first_present(usage, payload, "prompt_tokens", "input_tokens")
    completion = _first_present(usage, payload, "completion_tokens", "output_tokens")
    if explicit in {"missing", "invalid"}:
        return 0, 0, explicit
    if prompt is _MISSING or completion is _MISSING or prompt is None or completion is None:
        return 0, 0, "missing"
    parsed_prompt = _as_nonnegative_int(prompt)
    parsed_completion = _as_nonnegative_int(completion)
    if parsed_prompt is None or parsed_completion is None:
        return 0, 0, "invalid"
    return parsed_prompt, parsed_completion, "known"


def _parse_cost(usage: Any, payload: Any) -> tuple[float | None, LLMUsageStatus]:
    return normalize_llm_cost_evidence(usage, payload)


def normalize_llm_cost_evidence(
    usage: Any,
    payload: Any,
) -> tuple[float | None, LLMUsageStatus]:
    """Normalize cost evidence using one ordered alias and presence contract.

    The first present direct-cost field is authoritative, including explicit
    null or malformed values. Component costs are considered only when no
    direct-cost alias is present, and both components must be present and
    valid before they can be summed.
    """
    explicit = _explicit_status(usage, payload, "cost_status")
    if explicit in {"missing", "invalid"}:
        return None, explicit
    candidates = [
        _get(usage, "total_cost_usd"),
        _get(usage, "cost_usd"),
        _get(usage, "cost"),
        _get(payload, "total_cost_usd"),
        _get(payload, "cost_usd"),
        _get(payload, "cost"),
    ]
    for candidate in candidates:
        if candidate is _MISSING:
            continue
        return _normalized_cost_amount(candidate)

    base = _get(usage, "base_cost_usd")
    fee = _get(usage, "platform_fee_usd")
    if base is not _MISSING or fee is not _MISSING:
        if base is _MISSING or fee is _MISSING:
            return None, "invalid"
        parsed_base = _parse_amount(base)
        parsed_fee = _parse_amount(fee)
        if parsed_base is None or parsed_fee is None:
            return None, "invalid"
        return _normalized_cost_amount(parsed_base + parsed_fee)
    if explicit == "known":
        return None, "invalid"
    return None, "missing"


def _normalized_cost_amount(value: Any) -> tuple[float | None, LLMUsageStatus]:
    """Convert one finite nonnegative decimal only when float output preserves it."""
    parsed = value if isinstance(value, Decimal) else _parse_amount(value)
    if parsed is None or not parsed.is_finite() or parsed < 0:
        return None, "invalid"
    try:
        as_float = float(parsed)
    except (OverflowError, ValueError):
        return None, "invalid"
    if not math.isfinite(as_float) or (parsed != 0 and as_float == 0.0):
        return None, "invalid"
    return as_float, "known"


_MISSING = object()


def _first_present(usage: Any, payload: Any, *names: str) -> Any:
    for source in (usage, payload):
        for name in names:
            value = _get(source, name)
            if value is not _MISSING:
                return value
    return _MISSING


def _explicit_status(usage: Any, payload: Any, name: str) -> str | None:
    for source in (usage, payload):
        value = _get(source, name)
        if value is not _MISSING:
            if isinstance(value, str) and value in {"known", "missing", "invalid"}:
                return value
            return "invalid"
    return None


def _get(source: Any, name: str) -> Any:
    if source is None:
        return _MISSING
    if isinstance(source, dict):
        return source.get(name, _MISSING)
    try:
        if name in vars(source):
            return getattr(source, name)
    except TypeError:
        pass
    try:
        inspect.getattr_static(source, name)
    except AttributeError:
        return _MISSING
    try:
        return getattr(source, name)
    except Exception:
        return None


def _as_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _parse_amount(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


__all__ = [
    "LLMResponseData",
    "LLMUsageStatus",
    "extract_llm_response_data",
    "normalize_llm_cost_evidence",
]
