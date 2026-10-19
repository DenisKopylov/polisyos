"""Opaque Core-owned owner boundary for authenticated cache reuse."""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from typing import Literal, NoReturn

from .settlement import (
    _CacheFlightOutcome,
    _CacheFlightRegistration,
    _CacheReuseOwner,
    _CacheReuseProvenance,
)

_SESSION_LOCK = threading.RLock()
_SESSIONS_BY_CLIENT: dict[int, tuple[weakref.ReferenceType[object], CacheSettlementSession]] = {}
_OWNERS_BY_SESSION: dict[
    int,
    tuple[
        weakref.ReferenceType[CacheSettlementSession],
        _CacheReuseOwner,
        weakref.ReferenceType[object],
    ],
] = {}
_HANDLES_BY_ID: dict[
    int, tuple[weakref.ReferenceType[object], weakref.ReferenceType[CacheSettlementSession], object]
] = {}


class _OpaqueValue:
    """Disable ordinary mutation, copying, and serialization of capability handles."""

    __slots__ = ("__weakref__",)

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError("Core cache-settlement handles are immutable")

    def __copy__(self) -> NoReturn:
        raise TypeError("Core cache-settlement handles cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        raise TypeError("Core cache-settlement handles cannot be copied")

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        raise TypeError("Core cache-settlement handles cannot be serialized")


class CacheFlightRegistration(_OpaqueValue):
    """Opaque handle for one registration owned by a cache session."""

    __slots__ = ("__registration",)

    def __init__(self) -> None:
        raise TypeError("cache flight registrations are issued by Core")


class CacheFlightOutcome(_OpaqueValue):
    """Opaque handle for one settled cache flight owned by a cache session."""

    __slots__ = ("__outcome",)

    def __init__(self) -> None:
        raise TypeError("cache flight outcomes are issued by Core")


class CacheReuseAttestation(_OpaqueValue):
    """Opaque response-bound proof that Core admitted a particular cache reuse."""

    __slots__ = ("__provenance", "__response_ref")

    def __init__(self) -> None:
        raise TypeError("cache reuse attestations are issued by Core")


@dataclass(frozen=True, slots=True)
class CacheReuseEvidence:
    """Read-only facts recovered after Core verifies a reuse attestation."""

    cache_key: str
    request_digest: str
    reuse_event_id: str
    origin_event_id: str


class CacheSettlementSession(_OpaqueValue):
    """Typed capability whose operations keep cache owner secrets inside Core."""

    __slots__ = ()

    def __init__(self) -> None:
        raise TypeError("cache settlement sessions are issued by Core")

    def owns(self, client: object) -> bool:
        """Return whether this session remains bound to the exact live client."""
        owner = _owner_for(self)
        return owner is not None and owner.owns(client)

    def register_request(
        self, scope_key: tuple[str, ...], request_digest: str, attempt_id: str
    ) -> CacheFlightRegistration:
        """Register one cache request and return an opaque session-bound handle."""
        registration = _owner_or_raise(self).register_request(scope_key, request_digest, attempt_id)
        handle = object.__new__(CacheFlightRegistration)
        object.__setattr__(handle, "_CacheFlightRegistration__registration", registration)
        _remember_handle(self, handle, registration)
        return handle

    def bind_request_key(self, registration: CacheFlightRegistration, cache_key: str) -> None:
        """Bind a registered request to its exact internal cache key."""
        _owner_or_raise(self).bind_request_key(_registration_value(self, registration), cache_key)

    def dispatch(self, registration: CacheFlightRegistration, attempt_id: str) -> None:
        """Record that the registered producer was dispatched for this attempt."""
        _owner_or_raise(self).dispatch(_registration_value(self, registration), attempt_id)

    def join(
        self,
        registration: CacheFlightRegistration,
        scope_key: tuple[str, ...],
        request_digest: str,
        cache_key: str,
        attempt_id: str,
    ) -> None:
        """Join one receiver to the matching producer request."""
        _owner_or_raise(self).join(
            _registration_value(self, registration),
            scope_key,
            request_digest,
            cache_key,
            attempt_id,
        )

    def settle_flight(
        self,
        *,
        registrations: tuple[CacheFlightRegistration, ...],
        cache_key: str,
        request_digest: str,
        producer_attempt_id: str,
        terminal: Literal["success", "error", "deadline", "cancelled"],
        origin_event_id: str | None = None,
    ) -> CacheFlightOutcome:
        """Settle a registered flight without exposing Core's stored outcome."""
        outcome = _owner_or_raise(self).settle_flight(
            registrations=tuple(_registration_value(self, item) for item in registrations),
            cache_key=cache_key,
            request_digest=request_digest,
            producer_attempt_id=producer_attempt_id,
            terminal=terminal,
            origin_event_id=origin_event_id,
        )
        handle = object.__new__(CacheFlightOutcome)
        object.__setattr__(handle, "_CacheFlightOutcome__outcome", outcome)
        _remember_handle(self, handle, outcome)
        return handle

    def issue_reuse_attestation(
        self,
        *,
        response: object,
        cache_key: str,
        request_digest: str,
        reuse_event_id: str,
        origin_event_id: str,
        outcome: CacheFlightOutcome | None = None,
    ) -> CacheReuseAttestation:
        """Issue a signed reuse proof bound to this response and successful origin."""
        try:
            response_ref = weakref.ref(response)
        except TypeError as exc:
            raise TypeError("cache reuse response must support weak references") from exc
        internal_outcome = _outcome_value(self, outcome) if outcome is not None else None
        provenance = _owner_or_raise(self).issue(
            cache_key,
            request_digest,
            reuse_event_id,
            origin_event_id,
            internal_outcome,
            response_identity=id(response),
        )
        attestation = object.__new__(CacheReuseAttestation)
        object.__setattr__(attestation, "_CacheReuseAttestation__provenance", provenance)
        object.__setattr__(attestation, "_CacheReuseAttestation__response_ref", response_ref)
        _remember_handle(self, attestation, provenance)
        return attestation

    def verify_reuse_attestation(
        self, attestation: object, response: object
    ) -> CacheReuseEvidence | None:
        """Verify exact session, HMAC, response identity, and successful owner facts."""
        provenance = _handle_value(self, attestation, CacheReuseAttestation, _CacheReuseProvenance)
        if provenance is None:
            return None
        try:
            response_ref = object.__getattribute__(
                attestation, "_CacheReuseAttestation__response_ref"
            )
        except AttributeError:
            return None
        if (
            type(self) is not CacheSettlementSession
            or type(provenance) is not _CacheReuseProvenance
            or not isinstance(response_ref, weakref.ReferenceType)
            or response_ref() is not response
            or type(provenance.response_identity) is not int
            or provenance.response_identity != id(response)
        ):
            return None
        owner = _owner_for(self)
        if owner is None or not owner.verify_provenance(provenance):
            return None
        return CacheReuseEvidence(
            cache_key=provenance.cache_key,
            request_digest=provenance.request_digest,
            reuse_event_id=provenance.reuse_event_id,
            origin_event_id=provenance.origin_event_id,
        )


def create_cache_settlement_session(client: object) -> CacheSettlementSession:
    """Create or recover the one Core settlement session for an exact cache client."""
    try:
        weakref.ref(client)
    except TypeError as exc:
        raise TypeError("cache client must support weak references") from exc
    client_id = id(client)
    with _SESSION_LOCK:
        current = _SESSIONS_BY_CLIENT.get(client_id)
        if current is not None and current[0]() is client:
            return current[1]
        session = object.__new__(CacheSettlementSession)
        owner = _CacheReuseOwner(client)
        client_ref = weakref.ref(client, lambda reference: _discard_client(client_id, reference))
        session_ref = weakref.ref(session)
        _SESSIONS_BY_CLIENT[client_id] = (client_ref, session)
        _OWNERS_BY_SESSION[id(session)] = (session_ref, owner, client_ref)
        return session


def session_for_cache_client(client: object) -> CacheSettlementSession | None:
    """Return the existing session only for the exact registered cache client."""
    with _SESSION_LOCK:
        current = _SESSIONS_BY_CLIENT.get(id(client))
        if current is None or current[0]() is not client:
            return None
        return current[1]


def _discard_client(client_id: int, reference: weakref.ReferenceType[object]) -> None:
    with _SESSION_LOCK:
        current = _SESSIONS_BY_CLIENT.get(client_id)
        if current is None or current[0] is not reference:
            return
        session = current[1]
        del _SESSIONS_BY_CLIENT[client_id]
        owner_entry = _OWNERS_BY_SESSION.get(id(session))
        if owner_entry is not None and owner_entry[0]() is session:
            del _OWNERS_BY_SESSION[id(session)]


def _owner_for(session: CacheSettlementSession) -> _CacheReuseOwner | None:
    with _SESSION_LOCK:
        current = _OWNERS_BY_SESSION.get(id(session))
        if current is None or current[0]() is not session or current[2]() is None:
            return None
        return current[1]


def _owner_or_raise(session: CacheSettlementSession) -> _CacheReuseOwner:
    owner = _owner_for(session)
    if owner is None:
        raise ValueError("cache settlement session has no live Core owner")
    return owner


def _remember_handle(session: CacheSettlementSession, handle: _OpaqueValue, value: object) -> None:
    handle_id = id(handle)
    handle_ref = weakref.ref(handle, lambda reference: _discard_handle(handle_id, reference))
    session_ref = weakref.ref(session)
    with _SESSION_LOCK:
        _HANDLES_BY_ID[handle_id] = (handle_ref, session_ref, value)


def _discard_handle(handle_id: int, reference: weakref.ReferenceType[object]) -> None:
    with _SESSION_LOCK:
        current = _HANDLES_BY_ID.get(handle_id)
        if current is not None and current[0] is reference:
            del _HANDLES_BY_ID[handle_id]


def _handle_value(
    session: CacheSettlementSession,
    handle: object,
    handle_type: type[_OpaqueValue],
    value_type: type[object],
) -> object | None:
    if type(handle) is not handle_type:
        return None
    with _SESSION_LOCK:
        current = _HANDLES_BY_ID.get(id(handle))
        if (
            current is None
            or current[0]() is not handle
            or current[1]() is not session
            or type(current[2]) is not value_type
        ):
            return None
        return current[2]


def _registration_value(
    session: CacheSettlementSession, registration: CacheFlightRegistration
) -> _CacheFlightRegistration:
    value = _handle_value(session, registration, CacheFlightRegistration, _CacheFlightRegistration)
    if value is None:
        raise ValueError("cache flight registration is foreign or malformed")
    return value


def _outcome_value(
    session: CacheSettlementSession, outcome: CacheFlightOutcome
) -> _CacheFlightOutcome:
    value = _handle_value(session, outcome, CacheFlightOutcome, _CacheFlightOutcome)
    if value is None:
        raise ValueError("cache flight outcome is foreign or malformed")
    return value


__all__ = [
    "CacheFlightOutcome",
    "CacheFlightRegistration",
    "CacheReuseAttestation",
    "CacheReuseEvidence",
    "CacheSettlementSession",
    "create_cache_settlement_session",
    "session_for_cache_client",
]
