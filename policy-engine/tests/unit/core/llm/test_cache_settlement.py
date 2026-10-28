from __future__ import annotations

import copy
import hashlib
import pickle
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import polisyos.core.llm.cache_settlement as cache_settlement
from polisyos.core.llm.cache_settlement import (
    CacheFlightOutcome,
    CacheFlightRegistration,
    CacheReuseAttestation,
    CacheSettlementSession,
    bind_cache_settlement_client,
    cache_response_digest,
    create_cache_settlement_session,
    session_for_cache_client,
)
from polisyos.core.llm.response import extract_llm_response_data


class _CacheClient:
    pass


def test_same_content_changed_usage_cannot_reuse_an_actual_origin() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin, outcome = _settled_success(session)
    proof = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="full-projection",
        origin_event_id=origin,
        outcome=outcome,
    )
    evidence = session.verify_reuse_attestation(proof, response)
    assert evidence is not None
    assert evidence.response_digest == hashlib.sha256(response.content.encode()).hexdigest()
    assert evidence.projection_digest == cache_response_digest(response)
    response.usage["prompt_tokens"] = 999
    assert session.verify_reuse_attestation(proof, response) is None
    with pytest.raises(ValueError):
        session.issue_reuse_attestation(
            response=response,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id="same-content-other-usage",
            origin_event_id=origin,
            outcome=outcome,
        )


class _RegistrationSubclass(CacheFlightRegistration):
    __slots__ = ()


class _OutcomeSubclass(CacheFlightOutcome):
    __slots__ = ()


class _AttestationSubclass(CacheReuseAttestation):
    __slots__ = ()


@dataclass
class _ReuseResponse:
    content: str = "cached result"
    usage: dict[str, int | float] = field(
        default_factory=lambda: {
            "prompt_tokens": 12,
            "completion_tokens": 4,
            "cost_usd": 0.75,
        }
    )
    _polisyos_cache_hit: bool = True


def _settled_success(
    session: CacheSettlementSession,
    *,
    attempt_id: str = "producer-attempt",
    origin_event_id: str = "provider-event",
) -> tuple[str, str, str, CacheFlightOutcome]:
    scope_key = ("issuer", "epoch", "tenant", "purpose")
    request_digest = "request-digest"
    cache_key = "scoped-cache-key"
    registration = session.register_request(scope_key, request_digest, attempt_id)
    session.bind_request_key(registration, cache_key)
    session.dispatch(registration, attempt_id)
    outcome = session.settle_flight(
        registrations=(registration,),
        cache_key=cache_key,
        request_digest=request_digest,
        producer_attempt_id=attempt_id,
        terminal="success",
        origin_event_id=origin_event_id,
        response_digest=cache_response_digest(_ReuseResponse()),
        retain_for_s=30,
    )
    return cache_key, request_digest, origin_event_id, outcome


def test_cache_session_uses_exact_client_and_noncopyable_opaque_registration() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)

    assert session_for_cache_client(client) is session
    assert create_cache_settlement_session(client) is session
    assert session.owns(client)
    assert session_for_cache_client(_CacheClient()) is None
    registration = session.register_request(("scope",), "digest", "attempt")
    assert not hasattr(registration, "owner_id")
    assert not hasattr(registration, "scope_key")
    with pytest.raises(TypeError, match="issued by Core"):
        CacheFlightRegistration()
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(registration)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(registration)


def test_reuse_attestation_is_core_issued_session_and_response_bound() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin_event_id, outcome = _settled_success(session)
    attestation = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-event",
        origin_event_id=origin_event_id,
        outcome=outcome,
    )

    evidence = session.verify_reuse_attestation(attestation, response)
    assert evidence is not None
    assert evidence.cache_key == cache_key
    assert evidence.request_digest == request_digest
    assert evidence.reuse_event_id == "reuse-event"
    assert evidence.origin_event_id == origin_event_id
    assert not hasattr(attestation, "signature")
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(attestation)
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.deepcopy(attestation)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(attestation)

    other_response = _ReuseResponse()
    assert session.verify_reuse_attestation(attestation, other_response) is None
    other_client = _CacheClient()
    other_session = create_cache_settlement_session(other_client)
    assert other_session.verify_reuse_attestation(attestation, response) is None
    assert session.verify_reuse_attestation(object(), response) is None
    fake_session = object.__new__(CacheSettlementSession)
    assert fake_session.verify_reuse_attestation(attestation, response) is None
    field_name = "cache_key"
    with pytest.raises(AttributeError, match="immutable"):
        setattr(attestation, field_name, "mutated")


def test_only_verified_response_bound_proof_changes_cache_accounting() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin_event_id, outcome = _settled_success(session)
    forged_marker = SimpleNamespace(
        content=response.content,
        usage=response.usage,
        _polisyos_cache_hit=True,
        _polisyos_reuse_provenance=object(),
    )

    refused = extract_llm_response_data(
        forged_marker,
        cache_settlement_session=session,
    )
    assert refused.cache_hit is False
    assert refused.prompt_tokens == 12
    assert refused.completion_tokens == 4
    assert refused.cost_usd == 0.75

    attestation = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-event",
        origin_event_id=origin_event_id,
        outcome=outcome,
    )
    response._polisyos_reuse_provenance = attestation
    accepted = extract_llm_response_data(
        response,
        cache_settlement_session=session,
    )
    assert accepted.cache_hit is True
    assert accepted.prompt_tokens == 0
    assert accepted.completion_tokens == 0
    assert accepted.cost_usd == 0.0
    assert accepted.reuse_event_id == "reuse-event"
    assert accepted.origin_event_id == origin_event_id


def test_cancelled_flight_cannot_issue_reuse_attestation() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    scope_key = ("issuer", "epoch")
    request_digest = "request-digest"
    cache_key = "scoped-cache-key"
    attempt_id = "cancelled-attempt"
    registration = session.register_request(scope_key, request_digest, attempt_id)
    session.bind_request_key(registration, cache_key)
    session.dispatch(registration, attempt_id)
    outcome = session.settle_flight(
        registrations=(registration,),
        cache_key=cache_key,
        request_digest=request_digest,
        producer_attempt_id=attempt_id,
        terminal="cancelled",
    )

    with pytest.raises(ValueError, match="successful registered flight"):
        session.issue_reuse_attestation(
            response=response,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id="forbidden-reuse",
            origin_event_id="cancelled-origin",
            outcome=outcome,
        )


def test_mutated_provenance_payload_fails_closed() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin_event_id, outcome = _settled_success(session)
    attestation = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-event",
        origin_event_id=origin_event_id,
        outcome=outcome,
    )
    provenance = object.__getattribute__(attestation, "_CacheReuseAttestation__provenance")
    object.__setattr__(provenance, "signature", "mutated signature")

    assert session.verify_reuse_attestation(attestation, response) is None


def test_origin_is_bound_to_each_successful_flight_and_retained_hit() -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response_a = _ReuseResponse()
    response_b = _ReuseResponse()
    cache_key, request_digest, origin_a, outcome_a = _settled_success(
        session, attempt_id="provider-a-attempt", origin_event_id="provider-a-event"
    )
    _, _, origin_b, outcome_b = _settled_success(
        session, attempt_id="provider-b-attempt", origin_event_id="provider-b-event"
    )

    # Both origin IDs belong to successful same-client flights for this exact key and digest.
    with pytest.raises(ValueError, match="origin"):
        session.issue_reuse_attestation(
            response=response_a,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id="reuse-from-a",
            origin_event_id=origin_b,
            outcome=outcome_a,
        )
    refused = extract_llm_response_data(response_a, cache_settlement_session=session)
    assert refused.cache_hit is False
    assert refused.prompt_tokens == 12
    assert refused.completion_tokens == 4
    assert refused.cost_usd == 0.75

    attestation_a = session.issue_reuse_attestation(
        response=response_a,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-from-a",
        origin_event_id=origin_a,
        outcome=outcome_a,
    )
    evidence_a = session.verify_reuse_attestation(attestation_a, response_a)
    assert evidence_a is not None
    assert evidence_a.origin_event_id == origin_a

    with pytest.raises(ValueError, match="retained"):
        session.issue_reuse_attestation(
            response=response_b,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id="retained-reuse-a",
            origin_event_id=origin_a,
        )
    retained_b = session.issue_reuse_attestation(
        response=response_b,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="retained-reuse-b",
        origin_event_id=origin_b,
    )
    evidence_b = session.verify_reuse_attestation(retained_b, response_b)
    assert evidence_b is not None
    assert evidence_b.origin_event_id == origin_b

    response_from_b_flight = _ReuseResponse()
    attestation_b = session.issue_reuse_attestation(
        response=response_from_b_flight,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-from-b",
        origin_event_id=origin_b,
        outcome=outcome_b,
    )
    evidence_from_b = session.verify_reuse_attestation(attestation_b, response_from_b_flight)
    assert evidence_from_b is not None
    assert evidence_from_b.origin_event_id == origin_b


def test_fake_registration_handles_are_refused_before_owner_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    registration = session.register_request(("scope",), "digest", "attempt")
    registered_value = object.__getattribute__(
        registration, "_CacheFlightRegistration__registration"
    )
    missing = object.__new__(CacheFlightRegistration)
    copied = object.__new__(CacheFlightRegistration)
    object.__setattr__(copied, "_CacheFlightRegistration__registration", registered_value)
    subclassed = object.__new__(_RegistrationSubclass)
    object.__setattr__(subclassed, "_CacheFlightRegistration__registration", registered_value)
    owner = cache_settlement._owner_for(session)
    assert owner is not None
    traps = {
        name: Mock(side_effect=AssertionError(f"owner operation {name} must not run"))
        for name in ("bind_request_key", "dispatch", "join", "settle_flight")
    }
    for name, trap in traps.items():
        monkeypatch.setattr(owner, name, trap)

    for handle in (missing, copied, subclassed):
        with pytest.raises(ValueError, match="registration"):
            session.bind_request_key(handle, "scoped-cache-key")
        with pytest.raises(ValueError, match="registration"):
            session.dispatch(handle, "attempt")
        with pytest.raises(ValueError, match="registration"):
            session.join(handle, ("scope",), "digest", "scoped-cache-key", "attempt")
        with pytest.raises(ValueError, match="registration"):
            session.settle_flight(
                registrations=(handle,),
                cache_key="scoped-cache-key",
                request_digest="digest",
                producer_attempt_id="attempt",
                terminal="success",
                origin_event_id="provider-event",
            )

    assert not any(trap.called for trap in traps.values())


def test_foreign_or_forged_outcomes_and_attestations_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin_event_id, outcome = _settled_success(session)
    other_client = _CacheClient()
    other_session = create_cache_settlement_session(other_client)
    _, _, _, foreign_outcome = _settled_success(other_session)
    raw_outcome = object.__getattribute__(outcome, "_CacheFlightOutcome__outcome")
    missing_outcome = object.__new__(CacheFlightOutcome)
    copied_outcome = object.__new__(CacheFlightOutcome)
    object.__setattr__(copied_outcome, "_CacheFlightOutcome__outcome", raw_outcome)
    subclassed_outcome = object.__new__(_OutcomeSubclass)
    object.__setattr__(subclassed_outcome, "_CacheFlightOutcome__outcome", raw_outcome)
    genuine_attestation = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="reuse-event",
        origin_event_id=origin_event_id,
        outcome=outcome,
    )
    owner = cache_settlement._owner_for(session)
    assert owner is not None
    issue_trap = Mock(side_effect=AssertionError("Core must refuse foreign outcomes first"))
    monkeypatch.setattr(owner, "issue", issue_trap)

    for candidate in (foreign_outcome, missing_outcome, copied_outcome, subclassed_outcome):
        with pytest.raises(ValueError, match="outcome"):
            session.issue_reuse_attestation(
                response=response,
                cache_key=cache_key,
                request_digest=request_digest,
                reuse_event_id="reuse-event",
                origin_event_id=origin_event_id,
                outcome=candidate,
            )
    assert not issue_trap.called

    attestation = genuine_attestation
    raw_provenance = object.__getattribute__(attestation, "_CacheReuseAttestation__provenance")
    raw_response_ref = object.__getattribute__(attestation, "_CacheReuseAttestation__response_ref")
    missing_attestation = object.__new__(CacheReuseAttestation)
    copied_attestation = object.__new__(CacheReuseAttestation)
    object.__setattr__(missing_attestation, "_CacheReuseAttestation__provenance", raw_provenance)
    object.__setattr__(
        missing_attestation, "_CacheReuseAttestation__response_ref", raw_response_ref
    )
    object.__setattr__(copied_attestation, "_CacheReuseAttestation__provenance", raw_provenance)
    object.__setattr__(copied_attestation, "_CacheReuseAttestation__response_ref", raw_response_ref)
    subclassed_attestation = object.__new__(_AttestationSubclass)
    object.__setattr__(subclassed_attestation, "_CacheReuseAttestation__provenance", raw_provenance)
    object.__setattr__(
        subclassed_attestation, "_CacheReuseAttestation__response_ref", raw_response_ref
    )
    verify_trap = Mock(side_effect=AssertionError("Core must refuse forged attestations first"))
    monkeypatch.setattr(owner, "verify_provenance", verify_trap)

    for candidate in (missing_attestation, copied_attestation, subclassed_attestation):
        assert session.verify_reuse_attestation(candidate, response) is None
    assert not verify_trap.called


def test_cache_owner_alias_attribute_cannot_steal_an_existing_session() -> None:
    owner, legitimate, sibling = _CacheClient(), _CacheClient(), _CacheClient()
    session = bind_cache_settlement_client(owner, legitimate)
    sibling._cache_settlement_owner = owner
    assert session.owns(legitimate)
    assert session_for_cache_client(legitimate) is session
    assert session_for_cache_client(sibling) is None
    assert not session.owns(sibling)


def test_reuse_attestation_binds_content_as_well_as_response_identity() -> None:
    owner = _CacheClient()
    session = create_cache_settlement_session(owner)
    response = _ReuseResponse()
    cache_key, request_digest, origin, outcome = _settled_success(session)
    proof = session.issue_reuse_attestation(
        response=response,
        cache_key=cache_key,
        request_digest=request_digest,
        reuse_event_id="content-bound-reuse",
        origin_event_id=origin,
        outcome=outcome,
    )
    assert session.verify_reuse_attestation(proof, response) is not None
    response.content = "different body on the same live response"
    assert session.verify_reuse_attestation(proof, response) is None
    with pytest.raises(ValueError, match="projection does not match"):
        session.issue_reuse_attestation(
            response=response,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id="counterfeit-body",
            origin_event_id=origin,
            outcome=outcome,
        )


@pytest.mark.parametrize("ttl", [2.0, 0.0])
def test_real_settled_origin_reuse_has_a_fixed_producer_expiry(
    monkeypatch: pytest.MonkeyPatch,
    ttl: float,
) -> None:
    """Retained reuse works after flight release, then expires without renewal."""
    import polisyos.core.llm.settlement as settlement

    clock = [100.0]
    monkeypatch.setattr(settlement, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    response = _ReuseResponse()
    cache_key, request_digest, origin_id = "ttl-key", "ttl-request", "ttl-origin"
    registration = session.register_request(("fixture-scope",), request_digest, "ttl-producer")
    session.bind_request_key(registration, cache_key)
    session.dispatch(registration, "ttl-producer")
    outcome = session.settle_flight(
        registrations=(registration,),
        cache_key=cache_key,
        request_digest=request_digest,
        producer_attempt_id="ttl-producer",
        terminal="success",
        origin_event_id=origin_id,
        response_digest=cache_response_digest(response),
        retain_for_s=ttl,
    )
    session.release_flight((registration,), outcome)

    def retained_reuse(event_id: str) -> CacheReuseAttestation:
        return session.issue_reuse_attestation(
            response=response,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id=event_id,
            origin_event_id=origin_id,
        )

    if ttl:
        initial = retained_reuse("ttl-initial")
        assert session.verify_reuse_attestation(initial, response) is not None
        clock[0] = 100.0 + ttl / 2
        later = retained_reuse("ttl-later")
        assert session.verify_reuse_attestation(later, response) is not None
    clock[0] = 100.0 + ttl
    with pytest.raises(ValueError, match="retained successful producer event"):
        retained_reuse("ttl-expired")
    owner = cache_settlement._owner_for(session)
    assert owner is not None and not owner._published


@pytest.mark.parametrize("ttl", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_invalid_retention_ttl_cannot_publish_a_successful_origin(
    ttl: float,
) -> None:
    """A nonfinite/negative TTL refuses before a real flight mutates publication."""
    client = _CacheClient()
    session = create_cache_settlement_session(client)
    registration = session.register_request(("fixture-scope",), "ttl-request", "ttl-producer")
    session.bind_request_key(registration, "ttl-key")
    session.dispatch(registration, "ttl-producer")
    with pytest.raises(ValueError, match="finite and nonnegative"):
        session.settle_flight(
            registrations=(registration,),
            cache_key="ttl-key",
            request_digest="ttl-request",
            producer_attempt_id="ttl-producer",
            terminal="success",
            origin_event_id="ttl-origin",
            response_digest=cache_response_digest(_ReuseResponse()),
            retain_for_s=ttl,
        )
    owner = cache_settlement._owner_for(session)
    assert owner is not None and not owner._published and not owner._outcomes
