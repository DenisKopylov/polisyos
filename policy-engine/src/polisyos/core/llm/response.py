"""Normalize provider usage while preserving missing and invalid evidence."""

from __future__ import annotations

import inspect
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from .cache_settlement import CacheSettlementSession
from .settlement import LLMSettledResponse

LLMUsageStatus = Literal["known", "missing", "invalid"]
_USAGE_COMPONENT_KEYS = {
    "prompt": ("prompt_tokens", "input_tokens"),
    "completion": ("completion_tokens", "output_tokens"),
    "total": ("total_tokens",),
}
_USAGE_PAYLOAD_KEYS = frozenset(
    key for aliases in _USAGE_COMPONENT_KEYS.values() for key in aliases
) | {"usage_status"}


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


def extract_llm_response_data(
    response: Any, *, cache_settlement_session: CacheSettlementSession | None = None
) -> LLMResponseData:
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
    ) = _extract_cache_provenance(response, session=cache_settlement_session)
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
            reuse_event_id = _as_str(getattr(event, "event_id", None))
            origin_event_id = _as_str(getattr(event, "origin_event_id", None))
            reuse_request_digest = _as_str(getattr(event, "request_digest", None))
        elif amount is None:
            cost_usd_billable = None
        else:
            cache_hit = False
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
    response: Any, *, session: CacheSettlementSession | None = None
) -> tuple[bool, str | None, str | None, str | None, str | None]:
    """Accept reuse only after the Core session verifies its exact response proof."""
    attestation = getattr(response, "_polisyos_reuse_provenance", None)
    if type(session) is not CacheSettlementSession or attestation is None:
        return False, None, None, None, None
    evidence = session.verify_reuse_attestation(attestation, response)
    if evidence is None:
        return False, None, None, None, None
    return (
        True,
        evidence.reuse_event_id,
        evidence.cache_key,
        evidence.origin_event_id,
        evidence.request_digest,
    )


@dataclass(frozen=True)
class _UsageQuantity:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    status: LLMUsageStatus
    total_basis: Literal["reported", "derived", "unavailable"]


def _usage_quantity(
    usage: Any,
    payload: Any = None,
    *,
    nested_usage_present: bool | None = None,
) -> _UsageQuantity:
    """Parse one selected usage container; never assemble a hybrid quantity.

    A raw mapping with a ``usage`` key selects that nested value, even when it
    is empty, null, or malformed. A nullable container is missing; a null
    component in an actual object is invalid. Only when the key is absent may supported
    top-level token fields select the payload itself. Object-based clients use
    their explicit ``usage`` object; an absent object may expose the same
    top-level token form through its own attributes.

    ``nested_usage_present`` is for content-bound capture readers which store
    the selected nested value separately from the provider's top-level keys.
    It preserves the distinction between absent nested usage and a present but
    malformed non-object value such as ``usage: []``.
    """
    selected, malformed = _select_usage_container(
        usage, payload, nested_usage_present=nested_usage_present
    )
    if malformed:
        return _UsageQuantity(None, None, None, "invalid", "unavailable")
    if selected is _MISSING:
        return _UsageQuantity(None, None, None, "missing", "unavailable")

    explicit = _explicit_status(selected, None, "usage_status")
    prompt = _first_present(selected, *_USAGE_COMPONENT_KEYS["prompt"])
    completion = _first_present(selected, *_USAGE_COMPONENT_KEYS["completion"])
    total = _first_present(selected, *_USAGE_COMPONENT_KEYS["total"])
    p = None if prompt is _MISSING or prompt is None else _as_nonnegative_int(prompt)
    c = None if completion is _MISSING or completion is None else _as_nonnegative_int(completion)
    t = None if total is _MISSING else _as_nonnegative_int(total)
    malformed_component = (prompt is not _MISSING and p is None) or (
        completion is not _MISSING and c is None
    )
    if explicit == "invalid" or malformed_component or (total is not _MISSING and t is None):
        status = "invalid"
    elif (
        explicit == "missing"
        or prompt is _MISSING
        or completion is _MISSING
        or prompt is None
        or completion is None
    ):
        status = "missing"
    else:
        status = "known"
    if total is not _MISSING:
        basis = "reported"
    elif status == "known" and p is not None and c is not None:
        basis, t = "derived", p + c
    else:
        basis = "unavailable"
    return _UsageQuantity(p, c, t, status, basis)


def _select_usage_container(
    usage: Any,
    payload: Any,
    *,
    nested_usage_present: bool | None,
) -> tuple[Any, bool]:
    """Return exactly one source and whether its container type is malformed."""
    if nested_usage_present is True:
        # The provider container is nullable: explicit null remains unavailable,
        # but it is still exclusively selected and cannot borrow outer counts.
        return (_MISSING, False) if usage is None else (usage, not isinstance(usage, Mapping))
    if nested_usage_present is False:
        if _has_usage_fields(payload):
            return payload, False
        return _MISSING, False

    # Raw JSON payloads have the only authoritative presence marker for a
    # nested usage member. Do this before considering a separate ``usage``
    # argument so a malformed nested value cannot borrow top-level counts.
    if isinstance(payload, Mapping):
        if "usage" in payload:
            nested = payload["usage"]
            return (
                (_MISSING, False) if nested is None else (nested, not isinstance(nested, Mapping))
            )
        if usage is not _MISSING and usage is not None:
            return usage, not _is_usage_object(usage)
        if _has_usage_fields(payload):
            return payload, False
        return _MISSING, False

    # A direct mapping may itself be the selected provider usage object or a
    # complete raw payload. The latter case is recognized by a nested member
    # or by top-level token/status keys.
    if isinstance(usage, Mapping):
        if "usage" in usage:
            nested = usage["usage"]
            return (
                (_MISSING, False) if nested is None else (nested, not isinstance(nested, Mapping))
            )
        if _has_usage_fields(usage):
            return usage, False
        return _MISSING, False
    if usage is not _MISSING and usage is not None:
        return usage, not _is_usage_object(usage)
    if _has_usage_fields(payload):
        return payload, False
    return _MISSING, False


def _is_usage_object(value: Any) -> bool:
    """Recognize a structured usage object without accepting scalars/sequences."""
    return isinstance(value, Mapping) or any(
        _get(value, name) is not _MISSING for name in (*_USAGE_PAYLOAD_KEYS, "usage_status")
    )


def _has_usage_fields(value: Any) -> bool:
    """Whether a container explicitly carries a supported token/status field."""
    return any(_get(value, name) is not _MISSING for name in _USAGE_PAYLOAD_KEYS)


def _parse_usage(usage: Any, payload: Any) -> tuple[int, int, LLMUsageStatus]:
    observed = _usage_quantity(usage, payload)
    if observed.status != "known":
        return 0, 0, observed.status
    if observed.prompt_tokens is None or observed.completion_tokens is None:
        raise ValueError("known_usage_quantity_components_missing")
    return observed.prompt_tokens, observed.completion_tokens, observed.status


def _replay_usage_payload(
    usage: Any,
    payload: Any = None,
    *,
    nested_usage_present: bool | None = None,
    unknown_provenance: bool = False,
) -> dict[str, Any]:
    """Project selected quantity presence without inventing nulls or reported totals.

    Only components actually present in the selected source are emitted. Aliases
    use the canonical owner's precedence and normalize to their canonical key.
    Present malformed values normalize to explicit invalid nulls; absent values
    stay absent. The source quantity's derived total is never reissued as reported.

    Args:
        usage: Actual source usage quantity or response payload.
        payload: Optional actual response containing the selected quantity.
        nested_usage_present: Bound source observation of nested-member presence.
        unknown_provenance: One-way ceiling for unattested/reuse replay inputs.
            It can downgrade known to missing, never promote missing or invalid.

    Returns:
        A compact canonical mapping whose parse preserves the effective quantity
        and canonical component presence. It carries no historical authority.
    """
    selected, malformed = _select_usage_container(
        usage, payload, nested_usage_present=nested_usage_present
    )
    if malformed:
        return {"usage_status": "invalid"}
    if selected is _MISSING:
        return {"usage_status": "missing"}
    result: dict[str, Any] = {}
    for aliases in _USAGE_COMPONENT_KEYS.values():
        raw = _first_present(selected, *aliases)
        if raw is not _MISSING:
            result[aliases[0]] = _as_nonnegative_int(raw)
    explicit = _explicit_status(selected, None, "usage_status")
    if explicit is not None:
        result["usage_status"] = explicit
    observed = _usage_quantity(result)
    result["usage_status"] = (
        "missing" if unknown_provenance and observed.status != "invalid" else observed.status
    )
    return result


def _recorded_usage_payload(usage: Any) -> dict[str, Any]:
    """Keep every unattested legacy quantity unknown while preserving presence.

    Old counter magnitudes and status-like flags do not recover availability.
    The same canonical projection retains invalid inputs and never forwards
    historical money as a fresh provider price.
    """
    return _replay_usage_payload(usage, unknown_provenance=True)


def _capture_usage_observation(
    response: Any, *, cache_settlement_session: CacheSettlementSession | None = None
) -> dict[str, Any]:
    """Snapshot actual usage and settlement facts, never a replay reuse capability."""
    settled = response if type(response) is LLMSettledResponse else None
    inner = settled.response if settled is not None else response
    raw = _get(inner, "raw")
    keys = _USAGE_PAYLOAD_KEYS
    if isinstance(raw, dict) and (
        "choices" in raw or "usage" in raw or any(key in raw for key in keys)
    ):
        source = "response_payload"
        raw_usage = raw.get("usage")
        usage_present = "usage" in raw
        usage = (
            {key: value for key, value in raw_usage.items() if key in keys}
            if isinstance(raw_usage, dict)
            else raw_usage
            if usage_present
            else None
        )
        top = {key: value for key, value in raw.items() if key in keys}
    else:
        source, usage, top, usage_present = "normalized_object_only", None, {}, False
    quantity = (
        _usage_quantity(raw)
        if source == "response_payload"
        else _usage_quantity(usage, top, nested_usage_present=False)
    )
    normalized_origin = _usage_quantity(_get(inner, "usage"), inner)
    parsed = extract_llm_response_data(response, cache_settlement_session=cache_settlement_session)
    event = settled.settlement.event if settled is not None else None
    ack = settled.settlement.ack if settled is not None else None
    reuse = bool(parsed.cache_hit or (event is not None and event.cost_origin == "reuse"))
    return {
        "usage_source": source,
        "provider_usage": usage,
        "provider_top_usage": top,
        "provider_usage_present": usage_present,
        "provider_usage_status": quantity.status,
        "provider_total_basis": quantity.total_basis,
        "normalized_origin_usage": None
        if source == "response_payload"
        else {
            "prompt_tokens": normalized_origin.prompt_tokens,
            "completion_tokens": normalized_origin.completion_tokens,
            "usage_status": normalized_origin.status,
        },
        "billable_usage": {
            "prompt_tokens": parsed.prompt_tokens,
            "completion_tokens": parsed.completion_tokens,
            "usage_status": parsed.usage_status,
        },
        "source_cost_origin": event.cost_origin if event is not None else parsed.cost_origin,
        "source_was_reuse": reuse,
        "reuse_verification": "verified_live_core_session"
        if _extract_cache_provenance(inner, session=cache_settlement_session)[0]
        else "not_established",
        "settlement": None
        if event is None
        else {
            "event_id": event.event_id,
            "request_digest": event.request_digest,
            "response_utf8_sha256": event.response_digest,
            "model": event.model,
            "provider": event.provider,
            "kind": event.kind,
            "cost_origin": event.cost_origin,
            "origin_event_id": event.origin_event_id,
            "payload_digest": event.payload_digest,
            "amount": str(event.amount) if event.amount is not None else None,
            "ack_status": ack.status if ack is not None else None,
        },
    }


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


def _first_present(source: Any, *names: str) -> Any:
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
    if isinstance(source, Mapping):
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
