"""Declared cache equality preserves invalidation without creating authority."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    ClosureOwnerValueIdentity,
    ConsumedInputMember,
    DeclaredBasisCacheSeal,
    SameInputClosure,
    SealedConsumedInputSet,
    assert_consumed_input_reuse,
    assert_runtime_emitted,
    authority_purpose_blockers,
    authority_surface_decision,
    classify_authority_role,
    deserialize_authority_envelope,
    seal_consumed_input_set,
)
from tests.unit.runtime.quality.test_authority import _valid_payload
from tests.unit.runtime.quality.test_closure_authority_withdrawal import _positive_boundary


def _closure() -> SameInputClosure:
    return SameInputClosure(
        closure_id="declared-cache-only",
        status="not_closed",
        run_id="cache-run",
        job_id="cache-job",
        tenant_id="cache-tenant",
    )


def _member(name: str, identity: str = "a", kind: str = "source") -> ConsumedInputMember:
    return ConsumedInputMember.model_validate(
        {
            "member_id": name,
            "member_kind": kind,
            "declared_identity": "sha256:" + identity * 64,
            "resolved_identity": "sha256:" + identity * 64,
            "predicate_class": "recomputed",
        }
    )


def _cache(members: list[ConsumedInputMember] | None = None) -> DeclaredBasisCacheSeal:
    return seal_consumed_input_set(
        closure=_closure(),
        members=members if members is not None else [_member("source")],
        purpose="declared_basis_cache_equality",
    )


def test_explicit_cache_equality_keeps_only_declared_basis_and_order_independence() -> None:
    source, environment = _member("source"), _member("environment", kind="environment")
    sealed = _cache([source, environment])
    assert type(sealed) is DeclaredBasisCacheSeal
    assert sealed.authority_role == "diagnostic_only"
    assert sealed.purpose_completeness_basis == "not_established"
    assert sealed.basis_scope == "declared_members_only"
    assert (
        assert_consumed_input_reuse(
            sealed,
            closure=_closure(),
            fresh_members=[environment, source],
            purpose="declared_basis_cache_equality",
        )
        == sealed
    )
    # A subset is merely that declared subset; this does not establish that a
    # producer has no hidden inputs, even though its mechanical equality holds.
    subset = _cache([source])
    assert (
        assert_consumed_input_reuse(
            subset,
            closure=_closure(),
            fresh_members=[source],
            purpose="declared_basis_cache_equality",
        )
        == subset
    )
    assert subset.purpose_completeness_basis == "not_established"


@pytest.mark.parametrize("variant", ["missing", "extra", "substituted", "duplicate"])
def test_cache_reuse_still_rejects_before_after_membership_drift(variant: str) -> None:
    source = _member("source")
    sealed = _cache([source])
    cases = {
        "missing": ([], "member_missing"),
        "extra": ([source, _member("environment", kind="environment")], "member_extra"),
        "substituted": ([_member("source", identity="b")], "member_substituted"),
        "duplicate": ([source, source], "member_duplicate"),
    }
    fresh, code = cases[variant]
    with pytest.raises(AuthorityEnvelopeError, match=code):
        assert_consumed_input_reuse(
            sealed,
            closure=_closure(),
            fresh_members=fresh,
            purpose="declared_basis_cache_equality",
        )


def test_cache_seal_is_revalidated_instead_of_trusting_its_marker() -> None:
    sealed = _cache()
    forged = sealed.model_copy(update={"membership_sha256": "sha256:" + "f" * 64})
    with pytest.raises(AuthorityEnvelopeError, match="cache_seal_invalid"):
        assert_consumed_input_reuse(
            forged,
            closure=_closure(),
            fresh_members=[_member("source")],
            purpose="declared_basis_cache_equality",
        )


@pytest.mark.parametrize(
    ("field", "value"), [("authority_role", "producer_authority"), ("purpose", "authority")]
)
def test_cache_role_and_purpose_cannot_be_promoted_on_wire(field: str, value: str) -> None:
    payload = _cache().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError):
        DeclaredBasisCacheSeal.model_validate(payload)


def test_cache_seal_cannot_satisfy_any_protected_authority_path() -> None:
    sealed = _cache()
    with pytest.raises(AuthorityEnvelopeError, match="cache_seal_not_authoritative"):
        assert_consumed_input_reuse(sealed, closure=_closure(), fresh_members=[_member("source")])  # type: ignore[call-overload]
    with pytest.raises(AuthorityEnvelopeError, match="not_closed"):
        seal_consumed_input_set(closure=_closure(), members=[_member("source")])
    with pytest.raises(ValidationError):
        SealedConsumedInputSet.model_validate(sealed.model_dump(mode="json"))
    candidate = {**sealed.model_dump(mode="json"), **_positive_boundary()}
    decision = authority_surface_decision(candidate, surface="artifact", purpose="publication")
    assert decision.blocking and decision.status == "blocked"
    assert authority_purpose_blockers(candidate, "publication")
    # Even putting the cache object into a verifier slot cannot grant a role.
    payload = _valid_payload()
    envelope = deserialize_authority_envelope(payload)
    assert classify_authority_role(envelope, verified_closure=sealed) == "not_authoritative"  # type: ignore[arg-type]
    with pytest.raises(AuthorityEnvelopeError):
        assert_runtime_emitted(envelope, verified_closure=sealed)  # type: ignore[arg-type]


def test_cache_equality_binds_the_entire_declared_v2_closure() -> None:
    member = ClosureOwnerValueIdentity(
        name="effective_mode_ref",
        role="effective_mode",
        owner="declared-cache-owner",
        rule_version="cache-rule@1",
        value={"mode": "dev"},
    )
    closure = SameInputClosure(
        schema_version="2.0",
        closure_id="cache-v2",
        status="not_closed",
        run_id="cache-run",
        job_id="cache-job",
        tenant_id="cache-tenant",
        members=(member,),
        closure_sha256="sha256:" + "1" * 64,
    )
    sealed = seal_consumed_input_set(
        closure=closure,
        members=[_member("source")],
        purpose="declared_basis_cache_equality",
    )
    changed = closure.model_copy(
        update={"members": (member.model_copy(update={"value": {"mode": "research"}}),)}
    )
    # Keep the claimed digest and old string tuple fixed; full typed member
    # change still invalidates this mechanical declared-basis cache.
    assert changed.identity_tuple() == closure.identity_tuple()
    with pytest.raises(AuthorityEnvelopeError, match="closure_mismatch"):
        assert_consumed_input_reuse(
            sealed,
            closure=changed,
            fresh_members=[_member("source")],
            purpose="declared_basis_cache_equality",
        )


def test_historical_v1_identity_law_stays_readable_but_new_cache_binds_refs() -> None:
    original = SameInputClosure(
        closure_id="historical",
        status="closed",
        run_id="cache-run",
        job_id="cache-job",
        tenant_id="cache-tenant",
        closure_sha256="sha256:" + "1" * 64,
        evidence_input_refs=("declared-a",),
    )
    changed = original.model_copy(update={"evidence_input_refs": ("declared-b",)})
    # Compatibility only: this is the original v1 tuple, not a new admission.
    assert original.identity_tuple() == changed.identity_tuple()
    sealed = seal_consumed_input_set(
        closure=original,
        members=[_member("source")],
        purpose="declared_basis_cache_equality",
    )
    with pytest.raises(AuthorityEnvelopeError, match="closure_mismatch"):
        assert_consumed_input_reuse(
            sealed,
            closure=changed,
            fresh_members=[_member("source")],
            purpose="declared_basis_cache_equality",
        )
    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
        seal_consumed_input_set(closure=original, members=[_member("source")])
