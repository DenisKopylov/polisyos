"""Candidate closure comparisons never become protected authority admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef, CanonInfo
from polisyos.runtime.quality import authority
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    ClosureCasIdentity,
    ClosureMemberContract,
    ClosureNullIdentity,
    SameInputClosure,
    SameInputClosureContract,
    assert_authority_bearing,
    assert_runtime_emitted,
    assert_same_input_closure,
    classify_authority_role,
    deserialize_authority_envelope,
    seal_consumed_input_set,
    verify_same_input_closure,
)


class _Echo:
    """Deliberately untrusted caller adapter, including nonexistent CAS bytes."""

    def __init__(self, member: Any, refs: tuple[str, ...]) -> None:
        self.member = member
        self.refs = refs

    def resolve_member(self, member: Any, *, tenant_id: str, purpose: str) -> Any:
        assert (tenant_id, purpose) == ("tenant-1", "scorecard")
        return self.member

    def consumed_input_refs(self, *, run_id: str, job_id: str) -> tuple[str, ...]:
        assert (run_id, job_id) == ("run-1", "job-1")
        return self.refs


def _member(profile: str = "a") -> ClosureCasIdentity:
    return ClosureCasIdentity(
        name="policy_intent_ref",
        role="policy_intent_envelope",
        artifact_ref=ArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="runtime.policy_intent_envelope",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + profile * 64,
        ),
        schema_name="polisyos.runtime.PolicyIntentEnvelope",
        schema_version="1.0",
        producer_component="caller.invented.producer",
        producer_version="1.0",
    )


def _contract(*, required: bool = True) -> SameInputClosureContract:
    return SameInputClosureContract(
        owner="caller.invented.owner",
        purpose="scorecard",
        rule_version="candidate@2.0",
        members=(
            ClosureMemberContract(
                name="policy_intent_ref",
                role="policy_intent_envelope",
                identity_domain="cas",
                required=required,
            ),
        ),
    )


def _closure(member: Any, refs: tuple[str, ...] = ("caller-declared-edge",)) -> SameInputClosure:
    spec = canon.CanonSpec(exclude_none=False)
    projection = {
        "domain": "polisyos.runtime.same_input_closure",
        "schema_version": "2.0",
        "identity_law_version": "candidate@2.0",
        "canonical_spec": CanonInfo.from_spec(spec).model_dump(mode="json"),
        "owner": "caller.invented.owner",
        "purpose": "scorecard",
        "scope": {
            "run_id": "run-1",
            "job_id": "job-1",
            "tenant_id": "tenant-1",
            "cell_id": "cell-1",
        },
        "members": [member.model_dump(mode="json")],
        "evidence_input_refs": list(refs),
    }
    return SameInputClosure(
        schema_version="2.0",
        closure_id="diagnostic-locator",
        status="closed",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
        evidence_input_refs=refs,
        members=(member,),
        closure_sha256="sha256:"
        + hashlib.sha256(canon.to_canonical_bytes(projection, spec)).hexdigest(),
    )


def _arguments(
    closure: SameInputClosure, adapter: _Echo, *, required: bool = True
) -> dict[str, Any]:
    return {
        "closure": closure,
        "contract": _contract(required=required),
        "resolver": adapter,
        "expected_run_id": "run-1",
        "expected_job_id": "job-1",
        "expected_tenant_id": "tenant-1",
        "expected_cell_id": "cell-1",
    }


def _envelope(closure: SameInputClosure) -> Any:
    fixture = (
        Path(__file__).parents[3]
        / "fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
    )
    payload = json.loads(fixture.read_text())["payload"]
    payload.update(run_id="run-1", job_id="job-1", tenant_id="tenant-1", cell_id="cell-1")
    payload["same_input_closure"] = closure.model_dump(mode="json")
    return deserialize_authority_envelope(payload)


def test_coherent_echo_and_nonexistent_artifact_cannot_issue_authority() -> None:
    member = _member()
    closure = _closure(member)
    adapter = _Echo(member, closure.evidence_input_refs)
    candidate = authority.compare_same_input_closure_candidate(**_arguments(closure, adapter))
    assert type(candidate) is SameInputClosure
    assert candidate == closure
    with pytest.raises(AuthorityEnvelopeError, match="owner_not_established"):
        verify_same_input_closure(**_arguments(closure, adapter))
    envelope = _envelope(closure)
    assert classify_authority_role(envelope) == "not_authoritative"
    for consumer in (assert_authority_bearing, assert_runtime_emitted):
        with pytest.raises(AuthorityEnvelopeError, match="verification_missing"):
            consumer(envelope)
    with pytest.raises(AuthorityEnvelopeError, match="verification_missing"):
        assert_same_input_closure([envelope])
    with pytest.raises(AuthorityEnvelopeError, match="verification_missing"):
        seal_consumed_input_set(closure=closure, members=[])


@pytest.mark.parametrize("variant", ["profile", "hidden", "order", "digest"])
def test_candidate_comparison_preserves_selected_profile_and_order(variant: str) -> None:
    member = _member()
    refs = ("role-a:view-a", "role-a:view-a", "role-b:view-b")
    closure = _closure(member, refs)
    adapter = _Echo(member, refs)
    expected = "digest_mismatch"
    if variant == "profile":
        adapter.member = _member("b")
        expected = "member_resolution_mismatch"
    elif variant == "hidden":
        adapter.refs = (*refs, "hidden:decisive")
        expected = "consumption_mismatch"
    elif variant == "order":
        adapter.refs = tuple(reversed(refs))
        expected = "consumption_mismatch"
    else:
        closure = closure.model_copy(update={"closure_sha256": "sha256:" + "f" * 64})
    with pytest.raises(AuthorityEnvelopeError, match=expected):
        authority.compare_same_input_closure_candidate(**_arguments(closure, adapter))


def test_optional_cas_candidate_contract_accepts_absence_without_authority() -> None:
    absent = ClosureNullIdentity(name="policy_intent_ref", role="policy_intent_envelope")
    closure = _closure(absent)
    arguments = _arguments(closure, _Echo(absent, closure.evidence_input_refs), required=False)
    assert authority.compare_same_input_closure_candidate(**arguments) == closure
    with pytest.raises(AuthorityEnvelopeError, match="owner_not_established"):
        verify_same_input_closure(**arguments)
    with pytest.raises(
        AuthorityEnvelopeError, match=r"required_member_absent|member_contract_mismatch"
    ):
        authority.compare_same_input_closure_candidate(
            **_arguments(closure, _Echo(absent, closure.evidence_input_refs)),
        )


def test_v2_alias_tampering_and_v1_typed_members_are_refused() -> None:
    member = _member()
    closure = _closure(member)
    data = closure.model_dump(mode="json")
    data["policy_intent_ref"] = "sha256:" + "f" * 64
    with pytest.raises(ValidationError, match="legacy_alias_not_bound"):
        SameInputClosure.model_validate(data)
    data["schema_version"] = "1.0"
    data["policy_intent_ref"] = None
    with pytest.raises(ValidationError, match="legacy_members_forbidden"):
        SameInputClosure.model_validate(data)


def test_duck_admission_cannot_replace_a_real_owner() -> None:
    closure = _closure(_member())

    class Duck:
        def __init__(self) -> None:
            self.closure = closure

        def _revalidate(self, candidate: SameInputClosure) -> bool:
            return candidate == closure

    with pytest.raises(AuthorityEnvelopeError, match="verification_mismatch"):
        assert_same_input_closure([_envelope(closure)], verified=[Duck()])  # type: ignore[list-item]
    with pytest.raises(AuthorityEnvelopeError, match="verification_missing"):
        seal_consumed_input_set(closure=closure, members=[], verified_closure=Duck())  # type: ignore[arg-type]


def test_advisory_flag_cannot_promote_a_mixed_legacy_v2_collection() -> None:
    candidate = _closure(_member())
    v2 = _envelope(candidate)
    legacy_payload = v2.model_dump(mode="json")
    legacy_payload["same_input_closure"] = SameInputClosure(
        closure_id="historical",
        status="closed",
        closure_sha256="sha256:" + "a" * 64,
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
    ).model_dump(mode="json")
    legacy = deserialize_authority_envelope(legacy_payload)
    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
        assert_same_input_closure([legacy, v2])
    with pytest.raises(AuthorityEnvelopeError, match="verification_missing"):
        assert_same_input_closure([legacy, v2], historical_advisory=True)
