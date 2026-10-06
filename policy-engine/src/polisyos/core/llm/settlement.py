"""Producer-owned LLM completion and durable settlement composition.

This module carries operational events, not permission grants. Deployment owners
supply accounting and reuse policy separately; provider payloads cannot install
these contexts.
"""

from __future__ import annotations

import contextvars
import hashlib
import hmac
import json
import secrets
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.core.observability.pricing import estimate_llm_cost_usd


def _request_digest(value: Any) -> str:
    """Bind actual request bytes without retaining them in an accounting record."""

    def bind(item: Any) -> Any:
        if isinstance(item, (bytes, bytearray, memoryview)):
            content = bytes(item)
            return {
                "llm_bytes_sha256": hashlib.sha256(content).hexdigest(),
                "byte_length": len(content),
            }
        if isinstance(item, Mapping):
            return {str(key): bind(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [bind(child) for child in item]
        return to_python_data(item)

    return (
        "sha256:"
        + hashlib.sha256(stable_json_dumps(bind(value), sort_keys=True).encode()).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class LLMProducerEvent:
    """One immutable observed completion, including exact accounting identity."""

    event_id: str
    request_digest: str
    response_digest: str
    model: str
    provider: str
    amount: Decimal | None
    cost_origin: Literal["reported", "estimated", "reuse", "unknown"]
    kind: Literal["provider", "reuse"] = "provider"
    origin_event_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.event_id
            or (self.amount is None and (self.cost_origin != "unknown" or self.kind != "provider"))
            or (
                self.amount is not None
                and (
                    not self.amount.is_finite() or self.amount < 0 or self.cost_origin == "unknown"
                )
            )
        ):
            raise ValueError("invalid LLM producer settlement event")

    @property
    def payload_digest(self) -> str:
        """Bind the actual charge tuple independently of provider request IDs."""
        value = {
            "event_id": self.event_id,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "model": self.model,
            "provider": self.provider,
            "amount": str(self.amount) if self.amount is not None else None,
            "cost_origin": self.cost_origin,
            "kind": self.kind,
            "origin_event_id": self.origin_event_id,
        }
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )


@dataclass(frozen=True, slots=True)
class LLMSettlementAck:
    """Acknowledgement of an exact event; absent acknowledgement is unknown."""

    event_id: str
    payload_digest: str
    status: Literal["committed", "unknown", "unmanaged"]
    receipts: tuple[Any, ...] = ()
    durability: Literal["ledger", "memory", "none"] = "none"


@dataclass(frozen=True, slots=True)
class LLMProducerSettlement:
    """Immutable producer event and the acknowledgement actually received."""

    event: LLMProducerEvent
    ack: LLMSettlementAck

    def __post_init__(self) -> None:
        if (
            self.ack.event_id != self.event.event_id
            or self.ack.payload_digest != self.event.payload_digest
        ):
            raise ValueError("settlement acknowledgement does not bind the producer event")
        if self.event.amount is None and self.ack.status == "committed":
            raise ValueError("unknown producer amount cannot acquire a committed acknowledgement")


@dataclass(frozen=True, slots=True, init=False)
class LLMAuditObligation:
    """A required audit act distinct from an already known monetary receipt."""

    event: LLMProducerEvent | None
    run_id: str
    scope_key: tuple[str, ...]
    charge_ack: LLMSettlementAck | None
    actor: str = "budget_enforcer"
    action: Literal[
        "BUDGET_RESERVED", "BUDGET_CHECK", "BUDGET_EXCEEDED", "BUDGET_RELEASED", "BUDGET_COMMITTED"
    ] = "BUDGET_COMMITTED"
    act_id: str = ""
    _metadata_json: str = field(repr=False)

    def __init__(
        self,
        event: LLMProducerEvent | None,
        run_id: str,
        scope_key: tuple[str, ...],
        charge_ack: LLMSettlementAck | None,
        action: Literal[
            "BUDGET_RESERVED",
            "BUDGET_CHECK",
            "BUDGET_EXCEEDED",
            "BUDGET_RELEASED",
            "BUDGET_COMMITTED",
        ] = "BUDGET_COMMITTED",
        act_id: str = "",
        metadata: tuple[tuple[str, Any], ...] = (),
        actor: str = "budget_enforcer",
    ) -> None:
        object.__setattr__(self, "event", event)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "scope_key", tuple(scope_key))
        object.__setattr__(self, "charge_ack", charge_ack)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "act_id", act_id)
        object.__setattr__(
            self,
            "_metadata_json",
            stable_json_dumps(to_python_data(dict(metadata)), sort_keys=True),
        )

    @property
    def metadata(self) -> tuple[tuple[str, Any], ...]:
        """Return a detached view of the original canonical protected-act payload."""
        return tuple(json.loads(self._metadata_json).items())

    @property
    def payload_digest(self) -> str:
        """Bind the original operation, actual run, owner scope and charge receipts."""
        return _request_digest(
            {
                "producer_event": self.event.payload_digest if self.event is not None else None,
                "act_id": self.act_id,
                "metadata": self.metadata,
                "run_id": self.run_id,
                "scope_key": self.scope_key,
                "action": self.action,
                "actor": self.actor,
                "charge_ack": {
                    "event_id": self.charge_ack.event_id,
                    "payload_digest": self.charge_ack.payload_digest,
                    "status": self.charge_ack.status,
                    "durability": self.charge_ack.durability,
                    # The admitted ledger DTO owns its JSON encoding (including
                    # exact Decimal strings); the request serializer deliberately
                    # refuses arbitrary Decimal objects.
                    "receipts": tuple(
                        receipt.model_dump(mode="json")
                        if isinstance(receipt, BaseModel)
                        else receipt
                        for receipt in self.charge_ack.receipts
                    ),
                }
                if self.charge_ack is not None
                else None,
            }
        )


@dataclass(frozen=True, slots=True)
class LLMAuditResolution:
    """Exact completion evidence returned by a constructor-admitted audit owner.

    The reference is diagnostic. The trusted resolver verifies the physical
    audit act; a string or this DTO alone does not establish audit authority.
    """

    obligation_digest: str
    status: Literal["committed", "unknown"]
    evidence_ref: str


def _completion_amount(
    data: Any, model: str
) -> tuple[Decimal | None, Literal["reported", "estimated", "reuse", "unknown"]]:
    """Admit a numeric amount only from reported cost or observed priced usage."""
    if data.cache_hit:
        return Decimal(0), "reuse"
    origin: Literal["reported", "estimated"]
    if data.cost_status == "known" and data.cost_usd is not None:
        value, origin = data.cost_usd, "reported"
    elif data.cost_status == "missing" and data.usage_status == "known":
        value = estimate_llm_cost_usd(
            model=model,
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
        )
        origin = "estimated"
    else:
        return None, "unknown"
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        return None, "unknown"
    return amount, origin


class LLMSettledResponse:
    """Delegate a provider response while retaining its operational settlement."""

    __slots__ = ("_polisyos_settlement", "response")

    def __init__(self, response: Any, settlement: LLMProducerSettlement) -> None:
        self.response = response
        self._polisyos_settlement = settlement

    def __getattr__(self, name: str) -> Any:
        return getattr(self.response, name)

    def __str__(self) -> str:
        return str(self.response)


class _CacheReuseOwner:
    """An emitter admitted by its receiver, never by a response's type claim."""

    __slots__ = ("_client", "_seal")

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self._seal = secrets.token_bytes(32)

    def owns(self, client: Any) -> bool:
        return self._client is client

    def _signature(self, cache_key: str, request_digest: str, reuse_event_id: str) -> bytes:
        payload = stable_json_dumps([cache_key, request_digest, reuse_event_id]).encode()
        return hmac.digest(self._seal, payload, "sha256")

    def issue(self, cache_key: str, request_digest: str = "") -> _CacheReuseProvenance:
        reuse_event_id = f"cache-reuse:{uuid.uuid4().hex}"
        return _CacheReuseProvenance(
            self,
            self._signature(cache_key, request_digest, reuse_event_id),
            cache_key,
            reuse_event_id,
            request_digest,
        )

    def __reduce_ex__(self, protocol: int) -> Any:
        raise TypeError("cache reuse authority is an in-process capability")


@dataclass(frozen=True, slots=True)
class _CacheReuseProvenance:
    owner: _CacheReuseOwner
    seal: object
    cache_key: str
    reuse_event_id: str
    request_digest: str = ""

    def __reduce_ex__(self, protocol: int) -> Any:
        raise TypeError("cache reuse provenance cannot be serialized as authority")


def _cache_reuse_provenance(response: Any) -> _CacheReuseProvenance | None:
    consumer = _CACHE_REUSE_CONSUMER.get()
    value = getattr(response, "_polisyos_cache_reuse_provenance", None)
    if (
        consumer is not None
        and isinstance(value, _CacheReuseProvenance)
        and value.owner is consumer.owner
        and value.request_digest == consumer.request_digest
        and isinstance(value.cache_key, str)
        and isinstance(value.reuse_event_id, str)
        and isinstance(value.seal, bytes)
        and hmac.compare_digest(
            value.seal,
            consumer.owner._signature(value.cache_key, value.request_digest, value.reuse_event_id),
        )
    ):
        return value
    return None


@dataclass(frozen=True, slots=True)
class _SettlementOwner:
    scope_key: tuple[str, ...]
    settle: Callable[[LLMProducerEvent, Any], LLMSettlementAck]
    attempt_id: str | None = None
    request_digest: str | None = None


@dataclass(frozen=True, slots=True)
class _ProducerCompletion:
    scope_key: tuple[str, ...]
    request_digest: str
    complete: Callable[[Any, bool], LLMSettledResponse]


@dataclass(frozen=True, slots=True)
class _CacheReuseConsumer:
    owner: _CacheReuseOwner
    request_digest: str


_SETTLEMENT_OWNER: contextvars.ContextVar[_SettlementOwner | None] = contextvars.ContextVar(
    "polisyos_llm_settlement_owner", default=None
)
_PRODUCER_COMPLETION: contextvars.ContextVar[_ProducerCompletion | None] = contextvars.ContextVar(
    "polisyos_llm_producer_completion", default=None
)
_CACHE_REUSE_CONSUMER: contextvars.ContextVar[_CacheReuseConsumer | None] = contextvars.ContextVar(
    "polisyos_llm_cache_reuse_consumer", default=None
)


def _new_producer_id() -> str:
    return "llm-producer:" + uuid.uuid4().hex


def _current_settlement_owner() -> _SettlementOwner | None:
    return _SETTLEMENT_OWNER.get()


def _current_producer_completion() -> _ProducerCompletion | None:
    return _PRODUCER_COMPLETION.get()


@contextmanager
def _settlement_owner_context(
    scope_key: tuple[str, ...],
    settle: Callable[[LLMProducerEvent, Any], LLMSettlementAck],
    *,
    attempt_id: str | None = None,
    request_digest: str | None = None,
) -> Iterator[None]:
    token = _SETTLEMENT_OWNER.set(_SettlementOwner(scope_key, settle, attempt_id, request_digest))
    try:
        yield
    finally:
        _SETTLEMENT_OWNER.reset(token)


@contextmanager
def _producer_completion_context(
    scope_key: tuple[str, ...],
    request_digest: str,
    complete: Callable[[Any, bool], LLMSettledResponse],
) -> Iterator[None]:
    token = _PRODUCER_COMPLETION.set(_ProducerCompletion(scope_key, request_digest, complete))
    try:
        yield
    finally:
        _PRODUCER_COMPLETION.reset(token)


@contextmanager
def _cache_reuse_consumer_context(
    owner: _CacheReuseOwner | None, request_digest: str
) -> Iterator[None]:
    consumer = _CacheReuseConsumer(owner, request_digest) if owner is not None else None
    token = _CACHE_REUSE_CONSUMER.set(consumer)
    try:
        yield
    finally:
        _CACHE_REUSE_CONSUMER.reset(token)


def producer_settlement(response: Any) -> LLMProducerSettlement | None:
    """Return typed operational settlement attached by the actual producer path."""
    value = getattr(response, "_polisyos_settlement", None)
    return value if isinstance(value, LLMProducerSettlement) else None
