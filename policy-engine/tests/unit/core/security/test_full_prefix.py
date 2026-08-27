from __future__ import annotations

import hashlib
import inspect
import json

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.contracts import chronology as contract
from polisyos.core.security import full_prefix
from polisyos.core.security.full_prefix import FullPrefixVerifier, build_full_prefix_bundle


def _digest(fill: str) -> str:
    return f"sha256:{fill * 64}"


def _ref(fill: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID(_digest(fill)),
        kind="native",
        media_type="application/octet-stream",
    )


def _domain(
    *,
    family: str = "epoch",
    proof_domain: str = "conformance",
    scope_fill: str = "0",
) -> contract.ChronologyProofDomain:
    return contract.ChronologyProofDomain(
        format="polisyos.chronology.full-prefix.v1",
        profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
        proof_domain=proof_domain,
        family=family,
        scope_ref=_digest(scope_fill),
        authority_purpose="publication",
    )


def _member(index: int) -> contract.ChronologyMemberInput:
    native_bytes = f"native-member-{index}".encode()
    fill = format(index + 4, "x")[-1]
    return contract.ChronologyMemberInput(
        member_ref=_digest(fill),
        native_artifact_ref=_ref(format(index + 8, "x")[-1]),
        native_content_hash=contract._native_content_hash(native_bytes),
        native_schema_profile="conformance.native@1",
        native_bytes=native_bytes,
        member_admission_basis_ref=_digest("b"),
        member_admission_context_ref=_digest(format(index + 12, "x")[-1]),
    )


def _request(count: int, *, domain: contract.ChronologyProofDomain | None = None) -> contract.ChronologyBundleRequest:
    return contract.ChronologyBundleRequest(
        domain=domain or _domain(),
        native_schema_profile="conformance.native@1",
        declared_denominator_ref=_digest("1"),
        requested_cutoff_ref=_digest("2"),
        requested_query_context_ref=_digest("3"),
        members=tuple(_member(index) for index in range(count)),
    )


def _independent_canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _independent_bundle(request: contract.ChronologyBundleRequest) -> tuple[bytes, tuple[str, ...]]:
    descriptor = {
        "format": request.domain.format,
        "profile": request.domain.profile,
        "proof_domain": request.domain.proof_domain,
        "family": request.domain.family,
        "scope_ref": request.domain.scope_ref,
        "authority_purpose": request.domain.authority_purpose,
    }
    predecessor = "sha256:" + hashlib.sha256(
        b"polisyos.chronology.genesis.v1\0" + _independent_canonical(descriptor)
    ).hexdigest()
    commitments: list[str] = []
    body: list[bytes] = []
    for ordinal, member in enumerate(request.members):
        native_record = len(member.native_bytes).to_bytes(8, "big") + member.native_bytes
        native_hash = "sha256:" + hashlib.sha256(
            b"polisyos.chronology.native.v1\0" + native_record
        ).hexdigest()
        member_frame = {
            **descriptor,
            "native_schema_profile": request.native_schema_profile,
            "member_ordinal": ordinal,
            "member_ref": member.member_ref,
            "member_content_hash": native_hash,
            "member_admission_basis_ref": member.member_admission_basis_ref,
            "member_admission_context_ref": member.member_admission_context_ref,
            "predecessor_commitment": predecessor,
        }
        member_bytes = _independent_canonical(member_frame)
        commitment = "sha256:" + hashlib.sha256(
            b"polisyos.chronology.member.v1\0" + member_bytes
        ).hexdigest()
        body.extend(
            (
                len(member_bytes).to_bytes(8, "big") + member_bytes,
                native_record,
            )
        )
        commitments.append(commitment)
        predecessor = commitment
    genesis = "sha256:" + hashlib.sha256(
        b"polisyos.chronology.genesis.v1\0" + _independent_canonical(descriptor)
    ).hexdigest()
    header = {
        **descriptor,
        "native_schema_profile": request.native_schema_profile,
        "declared_denominator_ref": request.declared_denominator_ref,
        "requested_cutoff_ref": request.requested_cutoff_ref,
        "requested_query_context_ref": request.requested_query_context_ref,
        "member_count": len(request.members),
        "native_bytes_total": sum(len(member.native_bytes) for member in request.members),
        "first_commitment": commitments[0] if commitments else None,
        "commitment_head": commitments[-1] if commitments else genesis,
    }
    header_bytes = _independent_canonical(header)
    return (
        b"".join((len(header_bytes).to_bytes(8, "big") + header_bytes, *body)),
        tuple(commitments),
    )


@pytest.mark.parametrize(
    ("count", "size", "bundle_hash", "head"),
    [
        (
            0,
            781,
            "sha256:48f4eed374a1155203437f296bf9f9f309233f7d8ba7c5fdc161c52df259390b",
            "sha256:70b86458fbe5bda54106d0c684165bc7f6096c2ade34e95dbcb14e04e9031af8",
        ),
        (
            1,
            1706,
            "sha256:0478bb49e0b3fbf3179456dc633f96a4dbfdfd5a7574120e22b46e8c675f440b",
            "sha256:b8059a2245c531bf862304fd295b6f46bd49fc7a120b0461021ac9dbb1eea670",
        ),
        (
            2,
            2561,
            "sha256:878eca102ce1659950434eb7ee30b653da46a73c8ac63953fc8d9c1da93617cc",
            "sha256:36e65414e5f6d7d34eb32f3c2c22605e0928fbf39231f93f6f11405d6496b498",
        ),
    ],
)
def test_independent_encoder_reproduces_frozen_0_1_2_vectors(
    count: int, size: int, bundle_hash: str, head: str
) -> None:
    request = _request(count)
    built = build_full_prefix_bundle(request)
    assert isinstance(built, contract.EncodedChronologyBundle)
    independent_bytes, independent_commitments = _independent_bundle(request)
    assert independent_bytes == built.bundle_bytes
    assert independent_commitments == built.member_commitments
    assert len(independent_bytes) == size
    assert built.bundle_content_hash == bundle_hash
    assert built.header.commitment_head == head


@pytest.mark.parametrize("count", [0, 1, 2])
def test_builder_and_real_verifier_round_trip_0_1_2(count: int) -> None:
    request = _request(count)
    built = build_full_prefix_bundle(request)
    assert isinstance(built, contract.EncodedChronologyBundle)

    result = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=request.domain,
        expected_bundle_content_hash=built.bundle_content_hash,
    )

    assert isinstance(result, contract.FullPrefixVerified)
    assert result.verified_member_count == count
    assert result.commitment_head == built.header.commitment_head
    assert result.evaluation_state.expected_prefix == "not_requested"


def test_extension_preserves_old_member_frame_and_expected_prefix() -> None:
    one = build_full_prefix_bundle(_request(1))
    two = build_full_prefix_bundle(_request(2))
    assert isinstance(one, contract.EncodedChronologyBundle)
    assert isinstance(two, contract.EncodedChronologyBundle)

    one_records = contract._split_framed_records(one.bundle_bytes)
    two_records = contract._split_framed_records(two.bundle_bytes)
    assert one_records[1:3] == two_records[1:3]

    result = FullPrefixVerifier().verify_bundle(
        two.bundle_bytes,
        expected_domain=two.header.model_dump(mode="python")
        and _request(2).domain,
        expected_prefix=contract.ExpectedCommitmentPrefix(
            domain=_request(1).domain,
            member_count=1,
            commitment_head=one.header.commitment_head,
        ),
    )
    assert isinstance(result, contract.FullPrefixVerified)


def test_wrong_expected_hash_rejects_before_malformed_envelope() -> None:
    result = FullPrefixVerifier().verify_bundle(
        b"not-a-bundle",
        expected_domain=_domain(),
        expected_prefix=None,
        expected_bundle_content_hash=_digest("f"),
    )
    assert isinstance(result, contract.FullPrefixInvocationRejected)
    assert result.failure_codes == (
        contract.FullPrefixInvocationFailureCode.BUNDLE_CONTENT_HASH_MISMATCH,
    )
    assert result.evaluation_state == contract.FullPrefixEvaluationState(
        bundle_content_hash="rejected",
        envelope="not_evaluated",
        members="not_evaluated",
        internal_consistency="not_evaluated",
        expected_prefix="not_requested",
    )


def test_malformed_bytes_without_expected_hash_reject_at_envelope() -> None:
    result = FullPrefixVerifier().verify_bundle(b"short", expected_domain=_domain())
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)
    assert result.failure_codes == (contract.FullPrefixEnvelopeFailureCode.BUNDLE_MALFORMED,)


def test_empty_member_frame_cannot_verify_as_a_commitment() -> None:
    request = _request(1)
    empty_commitment = contract._sha256_digest(contract._MEMBER_PREFIX, b"")
    header = contract._build_header(
        request=request,
        commitments=(empty_commitment,),
        native_bytes_total=0,
    )
    attacked = b"".join(
        (
            contract._frame_record(
                contract._canonical_raw_bytes(contract._header_raw_mapping(header))
            ),
            contract._frame_record(b""),
            contract._frame_record(b""),
        )
    )

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=request.domain)

    assert isinstance(result, contract.FullPrefixMemberRejected)
    assert result.failure_codes == (
        contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME,
    )


def test_oversized_header_rejects_before_json_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    real_loads = full_prefix.json.loads

    def observed_loads(payload: object) -> object:
        nonlocal calls
        calls += 1
        return real_loads(payload)

    monkeypatch.setattr(full_prefix.json, "loads", observed_loads)
    oversized_payload = b"{" + b" " * contract.FULL_PREFIX_MAX_HEADER_FRAME_BYTES

    result = FullPrefixVerifier().verify_bundle(
        contract._frame_record(oversized_payload),
        expected_domain=_domain(),
    )

    assert isinstance(result, contract.FullPrefixEnvelopeRejected)
    assert result.failure_codes == (
        contract.FullPrefixEnvelopeFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
    )
    assert calls == 0


def test_oversized_member_rejects_before_member_json_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = build_full_prefix_bundle(_request(1))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)
    calls = 0
    real_loads = full_prefix.json.loads

    def observed_loads(payload: object) -> object:
        nonlocal calls
        calls += 1
        return real_loads(payload)

    monkeypatch.setattr(full_prefix.json, "loads", observed_loads)
    oversized_member = b"{" + b" " * contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES
    attacked = b"".join(
        (
            contract._frame_record(records[0]),
            contract._frame_record(oversized_member),
            contract._frame_record(records[2]),
        )
    )

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())

    assert isinstance(result, contract.FullPrefixMemberRejected)
    assert result.failure_codes == (
        contract.FullPrefixMemberFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
    )
    assert calls == 1


@pytest.mark.parametrize(
    "replacement",
    [b"changed-native", b"", b"native-member-0-extended"],
)
def test_native_substitution_with_old_markers_rejects(replacement: bytes) -> None:
    built = build_full_prefix_bundle(_request(1))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)
    records[2] = replacement
    attacked = b"".join(contract._frame_record(record) for record in records)

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert isinstance(result, contract.FullPrefixMemberRejected)
    assert contract.FullPrefixMemberFailureCode.NATIVE_CONTENT_HASH_MISMATCH in result.failure_codes


def test_delete_tail_and_prefix_narrowing_do_not_verify() -> None:
    built = build_full_prefix_bundle(_request(2))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)
    attacked = b"".join(contract._frame_record(record) for record in records[:-2])

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert not isinstance(result, contract.FullPrefixVerified)


def test_reorder_and_predecessor_fork_reject() -> None:
    built = build_full_prefix_bundle(_request(2))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)
    attacked_records = [records[0], records[3], records[4], records[1], records[2]]
    attacked = b"".join(contract._frame_record(record) for record in attacked_records)

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert isinstance(result, contract.FullPrefixMemberRejected)
    assert set(result.failure_codes) & {
        contract.FullPrefixMemberFailureCode.PREDECESSOR_MISMATCH,
        contract.FullPrefixMemberFailureCode.ORDINAL_MISMATCH,
    }


@pytest.mark.parametrize(
    "expected_domain",
    [
        _domain(family="movement"),
        _domain(proof_domain="other"),
        _domain(scope_fill="9"),
    ],
)
def test_cross_family_scope_and_domain_replay_reject(
    expected_domain: contract.ChronologyProofDomain,
) -> None:
    built = build_full_prefix_bundle(_request(1))
    assert isinstance(built, contract.EncodedChronologyBundle)
    result = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes, expected_domain=expected_domain
    )
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)
    assert result.failure_codes == (
        contract.FullPrefixEnvelopeFailureCode.PROOF_DOMAIN_MISMATCH,
    )


def test_unknown_profile_has_no_fallback() -> None:
    built = build_full_prefix_bundle(_request(0))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)
    header = json.loads(records[0])
    header["profile"] = "full_prefix_future_v2"
    attacked_header = contract._canonical_raw_bytes(header)
    attacked = contract._frame_record(attacked_header)

    result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)
    assert result.failure_codes == (contract.FullPrefixEnvelopeFailureCode.UNKNOWN_PROFILE,)


def test_expected_prefix_range_domain_and_head_are_separate_failures() -> None:
    built = build_full_prefix_bundle(_request(1))
    assert isinstance(built, contract.EncodedChronologyBundle)
    verifier = FullPrefixVerifier()

    out_of_range = verifier.verify_bundle(
        built.bundle_bytes,
        expected_domain=_domain(),
        expected_prefix=contract.ExpectedCommitmentPrefix(
            domain=_domain(), member_count=2, commitment_head=_digest("0")
        ),
    )
    assert isinstance(out_of_range, contract.FullPrefixExpectedPrefixRejected)
    assert out_of_range.failure_codes == (
        contract.FullPrefixExpectedPrefixFailureCode.OUT_OF_RANGE,
    )

    wrong_head = verifier.verify_bundle(
        built.bundle_bytes,
        expected_domain=_domain(),
        expected_prefix=contract.ExpectedCommitmentPrefix(
            domain=_domain(), member_count=1, commitment_head=_digest("0")
        ),
    )
    assert isinstance(wrong_head, contract.FullPrefixExpectedPrefixRejected)
    assert wrong_head.failure_codes == (
        contract.FullPrefixExpectedPrefixFailureCode.HEAD_MISMATCH,
    )

    wrong_domain = verifier.verify_bundle(
        built.bundle_bytes,
        expected_domain=_domain(),
        expected_prefix=contract.ExpectedCommitmentPrefix(
            domain=_domain(family="movement"),
            member_count=1,
                commitment_head=built.header.commitment_head,
        ),
    )
    assert isinstance(wrong_domain, contract.FullPrefixExpectedPrefixRejected)
    assert wrong_domain.failure_codes == (
        contract.FullPrefixExpectedPrefixFailureCode.DOMAIN_MISMATCH,
    )


def test_verification_statement_is_audit_only_and_real_replay_rejects_substitution() -> None:
    built = build_full_prefix_bundle(_request(2))
    assert isinstance(built, contract.EncodedChronologyBundle)
    valid_prefix = contract.ExpectedCommitmentPrefix(
        domain=_domain(),
        member_count=1,
        commitment_head=built.member_commitments[0],
    )
    verified = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=_domain(),
        expected_prefix=valid_prefix,
        expected_bundle_content_hash=built.bundle_content_hash,
    )
    assert isinstance(verified, contract.FullPrefixVerified)
    substituted = valid_prefix.model_copy(update={"commitment_head": _digest("f")})
    audit_only = contract.FullPrefixVerificationStatement(
        schema_version="polisyos.chronology.full-prefix-verification-result.v1",
        bundle_ref=_ref("a"),
        expected_domain=_domain(),
        expected_prefix=substituted,
        expected_bundle_content_hash=built.bundle_content_hash,
        result=verified,
    )

    replayed = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=audit_only.expected_domain,
        expected_prefix=audit_only.expected_prefix,
        expected_bundle_content_hash=audit_only.expected_bundle_content_hash,
    )

    assert isinstance(replayed, contract.FullPrefixExpectedPrefixRejected)
    assert replayed.failure_codes == (
        contract.FullPrefixExpectedPrefixFailureCode.HEAD_MISMATCH,
    )


def test_member_frame_cap_crossing_is_behavioral() -> None:
    member = _member(0).model_copy(
        update={"native_schema_profile": "x" * contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES}
    )
    request = _request(0).model_copy(
        update={
            "native_schema_profile": member.native_schema_profile,
            "members": (member,),
        }
    )
    result = build_full_prefix_bundle(request)
    assert isinstance(result, contract.FullPrefixBuildRejected)
    assert result.failure_code is contract.FullPrefixBuildFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED


def test_result_models_reject_cross_phase_codes_and_evaluation_state() -> None:
    built = build_full_prefix_bundle(_request(0))
    assert isinstance(built, contract.EncodedChronologyBundle)
    verified = FullPrefixVerifier().verify_bundle(built.bundle_bytes, expected_domain=_domain())
    assert isinstance(verified, contract.FullPrefixVerified)

    with pytest.raises(Exception):
        contract.FullPrefixMemberRejected(
            result_kind="member_rejected",
            status="rejected",
            phase="member",
            terminal_check=contract.FullPrefixTerminalCheck.MEMBERS,
            bundle_content_hash=built.bundle_content_hash,
            parsed_header=built.header,
            verified_member_count=0,
            commitment_head=built.header.commitment_head,
            failure_codes=("commitment_head_mismatch",),
            evaluation_state=verified.evaluation_state,
        )


def test_frozen_tables_are_immutable_and_factory_covers_all_twenty_rows() -> None:
    with pytest.raises(TypeError):
        contract.FULL_PREFIX_TERMINAL_BY_RESULT_KIND["verified"] = (  # type: ignore[index]
            contract.FullPrefixTerminalCheck.ENVELOPE
        )
    key = next(iter(contract.FULL_PREFIX_EVALUATION_TABLE))
    with pytest.raises(TypeError):
        contract.FULL_PREFIX_EVALUATION_TABLE[key] = (  # type: ignore[index]
            contract.FullPrefixEvaluationState(
                bundle_content_hash="rejected",
                envelope="rejected",
                members="rejected",
                internal_consistency="rejected",
                expected_prefix="rejected",
            )
        )

    built = build_full_prefix_bundle(_request(0))
    assert isinstance(built, contract.EncodedChronologyBundle)
    failure_by_kind = {
        "invocation_rejected": (
            contract.FullPrefixInvocationFailureCode.BUNDLE_CONTENT_HASH_MISMATCH,
        ),
        "envelope_rejected": (contract.FullPrefixEnvelopeFailureCode.BUNDLE_MALFORMED,),
        "member_rejected": (
            contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME,
        ),
        "internal_consistency_rejected": (
            contract.FullPrefixInternalConsistencyFailureCode.MEMBER_COUNT_MISMATCH,
        ),
        "expected_prefix_rejected": (
            contract.FullPrefixExpectedPrefixFailureCode.HEAD_MISMATCH,
        ),
        "verified": (),
    }
    observed = {}
    for table_key in contract.FULL_PREFIX_EVALUATION_TABLE:
        result = full_prefix._build_full_prefix_result(
            result_kind=table_key.result_kind,
            expected_bundle_hash_mode=table_key.expected_bundle_hash,
            expected_prefix_mode=table_key.expected_prefix,
            bundle_content_hash=built.bundle_content_hash,
            parsed_header=built.header,
            verified_member_count=0,
            commitment_head=built.header.commitment_head,
            failure_codes=failure_by_kind[table_key.result_kind],
        )
        observed[table_key] = result.evaluation_state
        assert result.terminal_check is contract.FULL_PREFIX_TERMINAL_BY_RESULT_KIND[
            table_key.result_kind
        ]

    assert observed == dict(contract.FULL_PREFIX_EVALUATION_TABLE)
    assert len(observed) == 20


def test_verifier_surface_has_no_native_policy_or_acceptance_parameters() -> None:
    signature = inspect.signature(FullPrefixVerifier.verify_bundle)
    assert set(signature.parameters) == {
        "self",
        "bundle_bytes",
        "expected_domain",
        "expected_prefix",
        "expected_bundle_content_hash",
    }
    forbidden = {
        "accepted",
        "authority_head",
        "current",
        "complete",
        "lineage",
        "policy",
        "denominator",
    }
    assert forbidden.isdisjoint(signature.parameters)
    result_fields = set(contract.FullPrefixVerified.model_fields)
    assert forbidden.isdisjoint(result_fields)


def test_unknown_header_and_member_fields_fail_closed() -> None:
    built = build_full_prefix_bundle(_request(1))
    assert isinstance(built, contract.EncodedChronologyBundle)
    records = contract._split_framed_records(built.bundle_bytes)

    header = json.loads(records[0])
    header["accepted"] = True
    attacked = contract._frame_record(contract._canonical_raw_bytes(header)) + b"".join(
        contract._frame_record(record) for record in records[1:]
    )
    header_result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert isinstance(header_result, contract.FullPrefixEnvelopeRejected)

    member = json.loads(records[1])
    member["authority_head"] = _digest("f")
    attacked = contract._frame_record(records[0]) + contract._frame_record(
        contract._canonical_raw_bytes(member)
    ) + b"".join(contract._frame_record(record) for record in records[2:])
    member_result = FullPrefixVerifier().verify_bundle(attacked, expected_domain=_domain())
    assert isinstance(member_result, contract.FullPrefixMemberRejected)
    assert member_result.failure_codes == (
        contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME,
    )


def test_annotation_only_context_change_moves_commitment_without_rebinding_query() -> None:
    original = build_full_prefix_bundle(_request(1))
    changed_member = _member(0).model_copy(
        update={"member_admission_context_ref": _digest("f")}
    )
    changed_request = _request(0).model_copy(update={"members": (changed_member,)})
    changed = build_full_prefix_bundle(changed_request)
    assert isinstance(original, contract.EncodedChronologyBundle)
    assert isinstance(changed, contract.EncodedChronologyBundle)
    assert original.header.requested_query_context_ref == changed.header.requested_query_context_ref
    assert original.header.commitment_head != changed.header.commitment_head
