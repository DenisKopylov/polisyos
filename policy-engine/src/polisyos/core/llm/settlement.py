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
from typing import Any, Literal, SupportsIndex
from weakref import WeakKeyDictionary

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
    _metadata_json: str = field(repr=False)
    actor: str = "budget_enforcer"
    action: Literal[
        "BUDGET_RESERVED", "BUDGET_CHECK", "BUDGET_EXCEEDED", "BUDGET_RELEASED", "BUDGET_COMMITTED"
    ] = "BUDGET_COMMITTED"
    act_id: str = ""

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

    __slots__ = ("_client", "_flight_claims", "_seal")

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self._seal = secrets.token_bytes(32)
        self._flight_claims: WeakKeyDictionary[_CacheFlightRegistration, _RegisteredFlight] = (
            WeakKeyDictionary()
        )

    def owns(self, client: Any) -> bool:
        return self._client is client

    def register_request(
        self, scope_key: tuple[str, ...], request_digest: str, attempt_id: str
    ) -> _CacheFlightRegistration:
        registration = _CacheFlightRegistration()
        self._flight_claims[registration] = _RegisteredFlight(
            scope_key, request_digest, "", None, frozenset((attempt_id,))
        )
        return registration

    def bind_request_key(self, registration: _CacheFlightRegistration, cache_key: str) -> None:
        record = self._flight_claims[registration]
        if record.cache_key and record.cache_key != cache_key:
            raise RuntimeError("cache request key cannot change after registration")
        self._flight_claims[registration] = _RegisteredFlight(
            record.scope_key,
            record.request_digest,
            cache_key,
            record.producer_attempt_id,
            record.receivers,
        )

    def dispatch(self, registration: _CacheFlightRegistration, attempt_id: str) -> None:
        record = self._flight_claims[registration]
        if record.producer_attempt_id is not None or attempt_id not in record.receivers:
            raise RuntimeError("cache physical dispatch requires the original registered request")
        self._flight_claims[registration] = _RegisteredFlight(
            record.scope_key, record.request_digest, record.cache_key, attempt_id, record.receivers
        )

    def join(
        self,
        registration: _CacheFlightRegistration,
        scope_key: tuple[str, ...],
        request_digest: str,
        cache_key: str,
        attempt_id: str,
    ) -> None:
        record = self._flight_claims[registration]
        if (
            record.scope_key != scope_key
            or record.request_digest != request_digest
            or record.cache_key != cache_key
            or record.producer_attempt_id is None
            or attempt_id in record.receivers
        ):
            raise RuntimeError("cache join does not bind the admitted physical flight")
        self._flight_claims[registration] = _RegisteredFlight(
            record.scope_key,
            record.request_digest,
            record.cache_key,
            record.producer_attempt_id,
            record.receivers | {attempt_id},
        )

    def registered_outcome(self, outcome: _CacheFlightOutcome) -> bool:
        record = self._flight_claims.get(outcome.registration)
        if record is None:
            return False
        role = (
            "not_dispatched"
            if record.producer_attempt_id is None
            else "producer"
            if record.producer_attempt_id == outcome.receiver_attempt_id
            else "joined"
        )
        return (
            outcome.owner is self
            and outcome.scope_key == record.scope_key
            and outcome.request_digest == record.request_digest
            and outcome.cache_key == record.cache_key
            and outcome.producer_attempt_id == record.producer_attempt_id
            and outcome.receiver_attempt_id in record.receivers
            and outcome.role == role
        )

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

    def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
        raise TypeError("cache reuse authority is an in-process capability")


@dataclass(frozen=True, slots=True)
class _CacheReuseProvenance:
    owner: _CacheReuseOwner
    seal: object
    cache_key: str
    reuse_event_id: str
    request_digest: str = ""

    def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
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
    flight_owner: _CacheReuseOwner | None = None
    observe_flight: Callable[[_CacheFlightOutcome], None] | None = None
    entry_client: Any = None
    observe_entry: Callable[[Literal["preflight", "delegated"]], None] | None = None


@dataclass(frozen=True, slots=True)
class _CacheFlightOutcome:
    """An actual cache flight's terminal participation, never serialized authority."""

    owner: _CacheReuseOwner
    registration: _CacheFlightRegistration
    cache_key: str
    request_digest: str
    scope_key: tuple[str, ...]
    producer_attempt_id: str | None
    receiver_attempt_id: str
    role: Literal["producer", "joined", "not_dispatched"]
    settlement: LLMProducerSettlement | None
    response: Any
    error: BaseException | None

    def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
        raise TypeError("cache flight participation is an in-process owner capability")


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _CacheFlightRegistration:
    """Opaque registered request identity, retained only by actual active receivers."""

    def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
        raise TypeError("cache flight registration cannot be serialized as authority")


@dataclass(frozen=True, slots=True)
class _RegisteredFlight:
    scope_key: tuple[str, ...]
    request_digest: str
    cache_key: str
    producer_attempt_id: str | None
    receivers: frozenset[str]


def _observe_cache_flight(
    owner: _CacheReuseOwner,
    *,
    registration: _CacheFlightRegistration | None,
    cache_key: str,
    request_digest: str,
    scope_key: tuple[str, ...],
    producer_attempt_id: str | None,
    role: Literal["producer", "joined", "not_dispatched"],
    settlement: LLMProducerSettlement | None,
    response: Any,
    error: BaseException | None,
) -> None:
    """Deliver only an outcome from the receiver's configured exact cache emitter."""
    receiver = _current_settlement_owner()
    if receiver is None or receiver.flight_owner is None:
        return
    if registration is None:
        raise RuntimeError("accounted cache outcome lacks an actual registered request")
    if (
        receiver.flight_owner is not owner
        or receiver.request_digest != request_digest
        or receiver.scope_key != scope_key
        or not receiver.attempt_id
        or (role != "not_dispatched" and not producer_attempt_id)
        or (role == "producer" and receiver.attempt_id != producer_attempt_id)
        or (role == "joined" and receiver.attempt_id == producer_attempt_id)
        or (role == "not_dispatched" and producer_attempt_id is not None)
    ):
        raise RuntimeError("cache flight outcome does not bind this accounting receiver")
    outcome = _CacheFlightOutcome(
        owner,
        registration,
        cache_key,
        request_digest,
        scope_key,
        producer_attempt_id,
        receiver.attempt_id,
        role,
        settlement,
        response,
        error,
    )
    if not owner.registered_outcome(outcome):
        raise RuntimeError("cache outcome does not match its registered participation")
    if receiver.observe_flight is not None:
        receiver.observe_flight(outcome)


def _observe_traced_entry(client: Any, phase: Literal["preflight", "delegated"]) -> None:
    """Observe entry only from this receiver's exact constructor-admitted wrapper.

    Delegation is not proof of remote provider dispatch: failure after it stays
    unknown. Preflight proves only that this logical call has not delegated.
    """
    receiver = _current_settlement_owner()
    if (
        receiver is not None
        and receiver.entry_client is client
        and receiver.observe_entry is not None
    ):
        receiver.observe_entry(phase)


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
    flight_owner: _CacheReuseOwner | None = None,
    observe_flight: Callable[[_CacheFlightOutcome], None] | None = None,
    entry_client: Any = None,
    observe_entry: Callable[[Literal["preflight", "delegated"]], None] | None = None,
) -> Iterator[None]:
    token = _SETTLEMENT_OWNER.set(
        _SettlementOwner(
            scope_key,
            settle,
            attempt_id,
            request_digest,
            flight_owner,
            observe_flight,
            entry_client,
            observe_entry,
        )
    )
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
