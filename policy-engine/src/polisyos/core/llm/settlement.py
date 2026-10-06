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
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from polisyos.common.serialization import stable_json_dumps, to_python_data


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
    amount: Decimal
    cost_origin: Literal["reported", "estimated", "reuse"]
    kind: Literal["provider", "reuse"] = "provider"
    origin_event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id or not self.amount.is_finite() or self.amount < 0:
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
            "amount": str(self.amount),
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
    scope_key: tuple[str, ...], settle: Callable[[LLMProducerEvent, Any], LLMSettlementAck]
) -> Iterator[None]:
    token = _SETTLEMENT_OWNER.set(_SettlementOwner(scope_key, settle))
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
