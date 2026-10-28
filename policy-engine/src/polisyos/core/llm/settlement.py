"""Typed producer settlement and in-process cache ownership contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Literal, Protocol

CostOrigin = Literal["reported", "estimated", "reuse", "unknown"]
SettlementStatus = Literal["committed", "unknown", "unmanaged"]


class LLMSettlementOwnershipError(RuntimeError):
    """Nested traced clients cannot agree on one exact settlement-store owner."""


class LLMSettlementIntegrityError(RuntimeError):
    """A nested producer result does not match its owner-bound event and receipt."""


class LLMProducerAdmissionGuard(Protocol):
    """Validate and fence a producer operation under its current owner admission."""

    def __call__[T](self, operation: Callable[[], T]) -> T: ...


@dataclass(frozen=True, slots=True)
class LLMProducerIntent:
    """Actual central producer begin facts, before external work or reuse settlement."""

    event_id: str
    request_digest: str
    key: str
    model: str
    provider: str


@dataclass(frozen=True, slots=True)
class LLMProducerEvent:
    """One physical provider outcome or one authenticated reuse event."""

    event_id: str
    request_digest: str
    response_digest: str
    model: str
    provider: str
    amount: Decimal | None
    cost_origin: CostOrigin
    kind: Literal["provider", "reuse"] = "provider"
    origin_event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id or not self.request_digest or not self.response_digest:
            raise ValueError("producer event identity and digests are required")
        if self.cost_origin not in {"reported", "estimated", "reuse", "unknown"}:
            raise ValueError("unsupported producer cost origin")
        if self.amount is None:
            if self.kind != "provider" or self.cost_origin != "unknown":
                raise ValueError("only an unknown provider amount may be absent")
        elif not self.amount.is_finite() or self.amount < 0 or self.cost_origin == "unknown":
            raise ValueError("known producer amounts must be finite and nonnegative")
        if self.kind == "reuse":
            if self.cost_origin != "reuse" or self.amount != Decimal(0):
                raise ValueError("reuse events carry an exact zero and reuse origin")
            if not self.origin_event_id or not self.origin_event_id.strip():
                raise ValueError("reuse events require an origin event ID")
        elif self.origin_event_id is not None:
            raise ValueError("provider events cannot carry a reuse origin event ID")

    @property
    def payload_digest(self) -> str:
        payload = {
            "amount": str(self.amount) if self.amount is not None else None,
            "cost_origin": self.cost_origin,
            "event_id": self.event_id,
            "kind": self.kind,
            "model": self.model,
            "origin_event_id": self.origin_event_id,
            "provider": self.provider,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class LLMSettlementAck:
    """Acknowledgment bound to one immutable producer payload."""

    event_id: str
    payload_digest: str
    status: SettlementStatus
    receipts: tuple[str, ...] = ()
    durability: Literal["ledger", "memory", "none"] = "none"


@dataclass(frozen=True, slots=True)
class LLMProducerSettlement:
    """Producer event plus an acknowledgment that names that exact event."""

    event: LLMProducerEvent
    ack: LLMSettlementAck

    def __post_init__(self) -> None:
        if self.ack.event_id != self.event.event_id:
            raise ValueError("settlement acknowledgment event ID does not bind producer event")
        if self.ack.payload_digest != self.event.payload_digest:
            raise ValueError("settlement acknowledgment digest does not bind producer event")
        if self.ack.status == "committed" and self.event.amount is None:
            raise ValueError("an unknown provider amount cannot be committed")


@dataclass(frozen=True, slots=True)
class LLMSettledResponse:
    """Response envelope preserving provider result and its monetary settlement."""

    response: Any
    settlement: LLMProducerSettlement

    @property
    def _polisyos_settled_response(self) -> Any:
        return self.response

    @property
    def _polisyos_settlement(self) -> LLMProducerSettlement:
        return self.settlement

    def __getattr__(self, name: str) -> Any:
        return getattr(self.response, name)

    def __str__(self) -> str:
        return str(self.response)


@dataclass(frozen=True, slots=True)
class _CacheFlightRegistration:
    owner_id: str
    scope_key: tuple[str, ...]
    request_digest: str
    attempt_id: str
    cache_key: str | None = None
    role: Literal["producer", "receiver", "not_dispatched"] = "not_dispatched"


@dataclass(frozen=True, slots=True)
class _CacheFlightOutcome:
    owner_id: str
    scope_key: tuple[str, ...]
    request_digest: str
    cache_key: str
    producer_attempt_id: str
    receiver_attempt_ids: tuple[str, ...]
    role: Literal["producer", "receiver", "not_dispatched"]
    terminal: Literal["success", "error", "deadline", "cancelled"]
    origin_event_id: str | None = None
    response_digest: str | None = None


@dataclass(frozen=True, slots=True)
class _CacheReuseProvenance:
    owner_id: str
    cache_key: str
    request_digest: str
    reuse_event_id: str
    origin_event_id: str
    response_identity: int
    response_digest: str
    scope_key: tuple[str, ...]
    signature: bytes

    def __reduce_ex__(self, protocol: int) -> Any:
        raise TypeError("cache reuse provenance cannot be serialized")


@dataclass(frozen=True, slots=True)
class _RetainedCacheOrigin:
    origin_event_id: str
    scope_key: tuple[str, ...]
    response_digest: str
    expires_at: float


class _CacheReuseOwner:
    """Per-client capability for authenticating actual cache-owned reuse."""

    def __init__(self, client: Any = None, *, retention_limit: int = 128) -> None:
        self._client_ref = weakref.ref(client) if client is not None else None
        self._owner_id = secrets.token_hex(16)
        self._secret = secrets.token_bytes(32)
        self._registrations: dict[str, _CacheFlightRegistration] = {}
        self._registration_handles: dict[str, _CacheFlightRegistration] = {}
        self._outcomes: dict[str, _CacheFlightOutcome] = {}
        if type(retention_limit) is not int or retention_limit < 1:
            raise ValueError("cache origin retention limit must be a positive integer")
        self._retention_limit = retention_limit
        self._published: OrderedDict[tuple[str, str], _RetainedCacheOrigin] = OrderedDict()

    def __reduce_ex__(self, protocol: int) -> Any:
        raise TypeError("cache owner capability cannot be serialized")

    def owns(self, client: Any) -> bool:
        return self._client_ref is not None and self._client_ref() is client

    def register_request(
        self, scope_key: tuple[str, ...], request_digest: str, attempt_id: str
    ) -> _CacheFlightRegistration:
        self._prune_retained_origins()
        registration = _CacheFlightRegistration(
            self._owner_id, tuple(scope_key), request_digest, attempt_id
        )
        self._registrations[attempt_id] = registration
        self._registration_handles[attempt_id] = registration
        return registration

    def bind_request_key(self, registration: _CacheFlightRegistration, cache_key: str) -> None:
        self._replace_registration(registration, cache_key=cache_key)

    def dispatch(self, registration: _CacheFlightRegistration, attempt_id: str) -> None:
        current = self._registered_registration(registration)
        if registration.attempt_id != attempt_id:
            raise ValueError("cache dispatch must be bound to its registered attempt")
        if current.cache_key is None:
            raise ValueError("cache dispatch must bind its exact request key")
        self._replace_registration(registration, role="producer")

    def join(
        self,
        registration: _CacheFlightRegistration,
        scope_key: tuple[str, ...],
        request_digest: str,
        cache_key: str,
        attempt_id: str,
    ) -> None:
        current = self._registered_registration(registration)
        if (
            current.owner_id != self._owner_id
            or current.scope_key != tuple(scope_key)
            or current.request_digest != request_digest
            or current.cache_key != cache_key
            or current.attempt_id != attempt_id
        ):
            raise ValueError("cache receiver does not match the registered producer request")
        self._replace_registration(registration, role="receiver")

    def settle_flight(
        self,
        *,
        registrations: tuple[_CacheFlightRegistration, ...],
        cache_key: str,
        request_digest: str,
        producer_attempt_id: str,
        terminal: Literal["success", "error", "deadline", "cancelled"],
        origin_event_id: str | None = None,
        response_digest: str | None = None,
        retain_for_s: float = 0,
    ) -> _CacheFlightOutcome:
        retention_ttl = float(retain_for_s)
        if not math.isfinite(retention_ttl) or retention_ttl < 0:
            raise ValueError("cache origin retention TTL must be finite and nonnegative")
        producer_handle = self._registration_handles.get(producer_attempt_id)
        producer = (
            self._registered_registration(producer_handle) if producer_handle is not None else None
        )
        if producer is None or producer.role != "producer":
            raise ValueError("cache flight has no registered dispatched producer")
        if producer.cache_key != cache_key or producer.request_digest != request_digest:
            raise ValueError("cache flight producer binding disagrees with outcome")
        receivers: list[str] = []
        for item in registrations:
            current = self._registered_registration(item)
            if current.scope_key != producer.scope_key:
                continue
            if (
                current.request_digest == request_digest
                and current.cache_key == cache_key
                and current.role == "receiver"
            ):
                receivers.append(current.attempt_id)
        outcome = _CacheFlightOutcome(
            self._owner_id,
            producer.scope_key,
            request_digest,
            cache_key,
            producer_attempt_id,
            tuple(sorted(set(receivers))),
            "producer",
            terminal,
            origin_event_id=origin_event_id if terminal == "success" else None,
            response_digest=response_digest if terminal == "success" else None,
        )
        self._outcomes[producer_attempt_id] = outcome
        if terminal == "success" and origin_event_id and response_digest:
            self._published[(cache_key, request_digest)] = _RetainedCacheOrigin(
                origin_event_id=origin_event_id,
                scope_key=producer.scope_key,
                response_digest=response_digest,
                expires_at=time.monotonic() + retention_ttl,
            )
        self._prune_retained_origins()
        return outcome

    def configure_retention(self, retention_limit: int) -> None:
        """Tighten a shared owner's resource bound without widening its authority."""
        if type(retention_limit) is not int or retention_limit < 1:
            raise ValueError("cache origin retention limit must be a positive integer")
        self._retention_limit = min(self._retention_limit, retention_limit)
        self._prune_retained_origins()

    def _prune_retained_origins(self) -> None:
        now = time.monotonic()
        for identity, retained in tuple(self._published.items()):
            if retained.expires_at <= now:
                del self._published[identity]
        while len(self._published) > self._retention_limit:
            self._published.popitem(last=False)

    def forget_cached_key(self, cache_key: str) -> None:
        """Remove origins for a key whose physical cache entry no longer exists."""
        for identity in tuple(self._published):
            if identity[0] == cache_key:
                del self._published[identity]

    def release_flight(
        self,
        registrations: tuple[_CacheFlightRegistration, ...],
        outcome: _CacheFlightOutcome | None,
    ) -> None:
        """Drop transient flight state after all response attestations were issued."""
        for registration in registrations:
            current = self._registration_handles.get(registration.attempt_id)
            if current is registration:
                self._registrations.pop(registration.attempt_id, None)
                self._registration_handles.pop(registration.attempt_id, None)
        if outcome is not None and self._outcomes.get(outcome.producer_attempt_id) is outcome:
            self._outcomes.pop(outcome.producer_attempt_id, None)

    def registered_outcome(self, outcome: _CacheFlightOutcome) -> bool:
        if type(outcome) is not _CacheFlightOutcome:
            return False
        try:
            producer_attempt_id = outcome.producer_attempt_id
        except AttributeError:
            return False
        if self._outcomes.get(producer_attempt_id) is not outcome:
            return False
        if outcome.owner_id != self._owner_id:
            return False
        producer = self._registrations.get(producer_attempt_id)
        if (
            producer is None
            or producer.role != "producer"
            or producer.scope_key != outcome.scope_key
            or producer.request_digest != outcome.request_digest
            or producer.cache_key != outcome.cache_key
        ):
            return False
        return all(
            (receiver := self._registrations.get(attempt_id)) is not None
            and receiver.role == "receiver"
            and receiver.scope_key == outcome.scope_key
            and receiver.request_digest == outcome.request_digest
            and receiver.cache_key == outcome.cache_key
            for attempt_id in outcome.receiver_attempt_ids
        )

    def issue(
        self,
        cache_key: str,
        request_digest: str = "",
        reuse_event_id: str | None = None,
        origin_event_id: str | None = None,
        outcome: _CacheFlightOutcome | None = None,
        *,
        response_identity: int,
        response_digest: str,
    ) -> _CacheReuseProvenance:
        reuse_id = reuse_event_id or secrets.token_hex(16)
        if outcome is not None:
            if not self.registered_outcome(outcome) or outcome.terminal != "success":
                raise ValueError("cache reuse requires the exact successful registered flight")
            if (outcome.cache_key, outcome.request_digest) != (cache_key, request_digest):
                raise ValueError("cache reuse request does not match its settled flight")
            origin_id = outcome.origin_event_id
            scope_key = outcome.scope_key
            expected_response_digest = outcome.response_digest
            if not origin_id or origin_event_id != origin_id:
                raise ValueError("cache reuse origin does not match its settled flight")
        else:
            self._prune_retained_origins()
            retained = self._published.get((cache_key, request_digest))
            if retained is None or origin_event_id != retained.origin_event_id:
                raise ValueError("cache reuse has no matching retained successful producer event")
            origin_id = retained.origin_event_id
            scope_key = retained.scope_key
            expected_response_digest = retained.response_digest
            self._published.move_to_end((cache_key, request_digest))
        if expected_response_digest is None or expected_response_digest != response_digest:
            raise ValueError("cache reuse projection does not match its successful origin")
        signature = self._signature(
            cache_key,
            request_digest,
            reuse_id,
            origin_id,
            response_identity,
            response_digest,
            scope_key,
        )
        return _CacheReuseProvenance(
            self._owner_id,
            cache_key,
            request_digest,
            reuse_id,
            origin_id,
            response_identity,
            response_digest,
            scope_key,
            signature,
        )

    def verify_provenance(self, provenance: Any) -> bool:
        if type(provenance) is not _CacheReuseProvenance:
            return False
        if (
            type(provenance.owner_id) is not str
            or provenance.owner_id != self._owner_id
            or type(provenance.cache_key) is not str
            or type(provenance.request_digest) is not str
            or type(provenance.reuse_event_id) is not str
            or type(provenance.origin_event_id) is not str
            or type(provenance.response_identity) is not int
            or type(provenance.response_digest) is not str
            or type(provenance.scope_key) is not tuple
            or not all(type(item) is str for item in provenance.scope_key)
            or type(provenance.signature) is not bytes
        ):
            return False
        return hmac.compare_digest(
            provenance.signature,
            self._signature(
                provenance.cache_key,
                provenance.request_digest,
                provenance.reuse_event_id,
                provenance.origin_event_id,
                provenance.response_identity,
                provenance.response_digest,
                provenance.scope_key,
            ),
        )

    def _signature(
        self,
        cache_key: str,
        request_digest: str,
        reuse_event_id: str,
        origin_event_id: str,
        response_identity: int,
        response_digest: str,
        scope_key: tuple[str, ...],
    ) -> bytes:
        body = json.dumps(
            [
                self._owner_id,
                cache_key,
                request_digest,
                reuse_event_id,
                origin_event_id,
                response_identity,
                response_digest,
                scope_key,
            ],
            separators=(",", ":"),
        ).encode()
        return hmac.new(self._secret, body, hashlib.sha256).digest()

    def _registered_registration(
        self, registration: _CacheFlightRegistration
    ) -> _CacheFlightRegistration:
        if type(registration) is not _CacheFlightRegistration:
            raise ValueError("cache flight registration is stale or foreign")
        attempt_id = registration.attempt_id
        if self._registration_handles.get(attempt_id) is not registration:
            raise ValueError("cache flight registration is stale or foreign")
        current = self._registrations.get(attempt_id)
        if current is None or (
            current.owner_id,
            current.scope_key,
            current.request_digest,
            current.attempt_id,
        ) != (
            registration.owner_id,
            registration.scope_key,
            registration.request_digest,
            registration.attempt_id,
        ):
            raise ValueError("cache flight registration is stale or foreign")
        return current

    def _replace_registration(self, registration: _CacheFlightRegistration, **changes: Any) -> None:
        current = self._registered_registration(registration)
        self._registrations[registration.attempt_id] = replace(current, **changes)


__all__ = [
    "CostOrigin",
    "LLMProducerEvent",
    "LLMProducerSettlement",
    "LLMSettledResponse",
    "LLMSettlementAck",
    "LLMSettlementIntegrityError",
    "LLMSettlementOwnershipError",
    "SettlementStatus",
]
