from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import polisyos.core as core
import polisyos.core.contracts as core_contracts
from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS
from polisyos.core.contracts import chronology as contract


def _digest(fill: str) -> str:
    return f"sha256:{fill * 64}"


def _ref(fill: str, *, kind: str = "test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID(_digest(fill)),
        kind=kind,
        media_type="application/octet-stream",
    )


def _domain(*, family: str = "epoch", scope_fill: str = "0") -> contract.ChronologyProofDomain:
    return contract.ChronologyProofDomain(
        format="polisyos.chronology.full-prefix.v1",
        profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
        proof_domain="conformance",
        family=family,
        scope_ref=_digest(scope_fill),
        authority_purpose="publication",
    )


def _query(*, context_fill: str = "3") -> contract.NativeChronologyQuery:
    return contract.NativeChronologyQuery(
        domain=_domain(),
        requested_cutoff_ref=_digest("2"),
        requested_query_context_ref=_digest(context_fill),
    )


def _policy_statement(
    *, required_native_head_role: str | None
) -> contract.PredicateAdmissionPolicyStatement:
    return contract.PredicateAdmissionPolicyStatement(
        schema_version="polisyos.chronology.predicate-policy.v1",
        key=contract.PredicatePolicySelectionKey(
            family="epoch",
            proof_domain="conformance",
            scope_ref=_digest("0"),
            authority_purpose="publication",
            requested_cutoff_ref=_digest("2"),
        ),
        native_schema_profile="conformance.native@1",
        required_native_head_role=required_native_head_role,
        rules=(),
        owner_provenance_ref=_ref("9", kind="owner-provenance"),
        owner_provenance_content_hash=_digest("a"),
    )


def _member(
    *, ordinal: int = 0, native_bytes: bytes = b"epoch-0"
) -> contract.ChronologyMemberInput:
    del ordinal
    return contract.ChronologyMemberInput(
        member_ref=_digest("4"),
        native_artifact_ref=_ref("5", kind="native"),
        native_content_hash=contract._native_content_hash(native_bytes),
        native_schema_profile="conformance.native@1",
        native_bytes=native_bytes,
        member_admission_basis_ref=_digest("6"),
        member_admission_context_ref=_digest("7"),
    )


def _owner_qualified_candidate(
    *,
    query: contract.NativeChronologyQuery | None = None,
    exterior_limitation_code: str | None = None,
    native_authority_head_refs: tuple[contract.Digest, ...] = (),
) -> contract.OwnerQualifiedNativeCandidate:
    member = _member()
    resolved_query = query or _query()
    policy_owner_provenance = contract.VerifiedPolicyOwnerProvenance(
        policy_ref=_ref("a", kind="predicate-policy"),
        policy_content_hash=_digest("a"),
        owner_provenance_ref=_ref("9", kind="owner-provenance"),
        owner_provenance_content_hash=_digest("9"),
        trust_snapshot_ref=_ref("8", kind="trust-snapshot"),
        trust_snapshot_content_hash=_digest("8"),
        verification_receipt_ref=_ref("7", kind="policy-owner-verification"),
        verification_receipt_content_hash=_digest("7"),
        verifier_provenance_ref=_ref("6", kind="verifier-provenance"),
        predicate_class="independently_reconciled",
    )
    candidate = contract.NativeChronologyCandidate(
        query=resolved_query,
        declared_denominator_ref=_digest("1"),
        native_denominator_artifact_ref=_ref("b", kind="native-denominator"),
        native_denominator_content_hash=_digest("1"),
        query_context_artifact_ref=_ref("c", kind="query-context"),
        query_context_content_hash=_digest("3"),
        ordered_members=(member,),
        member_predicates=(),
        query_predicates=(),
        exterior_limitation_code=exterior_limitation_code,
        native_authority_head_refs=native_authority_head_refs,
    )
    candidate_hash = contract._native_candidate_content_hash(candidate)
    owner_relation = contract.VerifiedPredicatePolicyOwnerRelation(
        query=resolved_query,
        owner_relation_ref=_ref("5", kind="owner-relation"),
        owner_relation_content_hash=_digest("5"),
        owner_verifier_provenance_ref=_ref("4", kind="owner-verifier"),
        verification_receipt_ref=_ref("3", kind="owner-verification"),
        verification_receipt_content_hash=_digest("3"),
        candidate_content_hash=candidate_hash,
        owner_declared_denominator_ref=candidate.declared_denominator_ref,
        candidate_declared_denominator_ref=candidate.declared_denominator_ref,
        owner_ordered_member_refs=(member.member_ref,),
        candidate_ordered_member_refs=(member.member_ref,),
        denominator_identity=contract.VerifiedNativeSubjectIdentity(
            subject_kind="denominator",
            subject_ref=candidate.declared_denominator_ref,
            artifact_ref=candidate.native_denominator_artifact_ref,
            raw_cas_hash=_digest("b"),
            semantic_content_hash=candidate.native_denominator_content_hash,
            verifier_provenance_ref=_ref("2", kind="denominator-verifier"),
        ),
        query_context_identity=contract.VerifiedNativeSubjectIdentity(
            subject_kind="query_context",
            subject_ref=resolved_query.requested_query_context_ref,
            artifact_ref=candidate.query_context_artifact_ref,
            raw_cas_hash=_digest("c"),
            semantic_content_hash=candidate.query_context_content_hash,
            verifier_provenance_ref=_ref("1", kind="query-verifier"),
        ),
        member_identities=(
            contract.VerifiedNativeMemberIdentity(
                member_ref=member.member_ref,
                native_artifact_ref=member.native_artifact_ref,
                native_content_hash=member.native_content_hash,
                native_schema_profile=member.native_schema_profile,
                member_admission_basis_ref=member.member_admission_basis_ref,
                member_admission_context_ref=member.member_admission_context_ref,
            ),
        ),
        predicate_evidence=(),
        policy_owner_provenance=policy_owner_provenance,
        predicate_class="independently_reconciled",
    )
    return contract.OwnerQualifiedNativeCandidate(
        candidate=candidate,
        candidate_content_hash=candidate_hash,
        owner_relation_verification=owner_relation,
    )


def _raw_artifact_ref(payload: bytes, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID(f"sha256:{hashlib.sha256(payload).hexdigest()}"),
        kind=kind,
        media_type="application/octet-stream",
    )


def _owner_context(
    qualified: contract.OwnerQualifiedNativeCandidate,
) -> contract.NativeChronologyOwnerContext:
    policy = qualified.owner_relation_verification.policy_owner_provenance
    return contract.NativeChronologyOwnerContext(
        query=qualified.candidate.query,
        owner_qualified_candidate=qualified,
        policy_admission_ref=_ref("d", kind="policy-admission"),
        policy_admission_content_hash=_digest("d"),
        predicate_admission_policy_ref=policy.policy_ref,
        predicate_admission_policy_content_hash=policy.policy_content_hash,
    )


def _self_consistent_denominator(
    statement: contract.ApplicablePredicateDenominatorStatement,
) -> contract.PersistedApplicablePredicateDenominator:
    raw_statement = contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
    artifact_ref = _raw_artifact_ref(
        contract._frame_record(raw_statement),
        kind="core.chronology.applicable_predicate_denominator",
    )
    return contract.PersistedApplicablePredicateDenominator(
        artifact_ref=artifact_ref,
        cas_raw_bytes_hash=str(artifact_ref.artifact_id),
        denominator_content_hash=contract._denominator_content_hash(statement),
        statement=statement,
    )


def _reconciliation(
    tmp_path: Path,
    *,
    qualified: contract.OwnerQualifiedNativeCandidate | None = None,
) -> contract.NativeChronologyReconciliation:
    resolved = qualified or _owner_qualified_candidate()
    policy = resolved.owner_relation_verification.policy_owner_provenance
    statement = contract.ApplicablePredicateDenominatorStatement(
        schema_version="polisyos.chronology.applicable-predicate-denominator.v1",
        policy_ref=policy.policy_ref,
        policy_content_hash=policy.policy_content_hash,
        member_subject_refs=tuple(
            member.member_ref for member in resolved.candidate.ordered_members
        ),
        required_member_predicate_pairs=(),
        required_query_predicate_ids=(),
    )
    persisted = contract.ChronologyApplicablePredicateDenominatorArtifacts(
        store=FileSystemCAS(tmp_path / "reconciliation-cas")
    ).persist_and_verify(
        query=resolved.candidate.query,
        statement=statement,
        owner_qualified_candidate=resolved,
    )
    assert isinstance(persisted, contract.PersistedApplicablePredicateDenominator)
    return contract.NativeChronologyReconciliation(
        owner_context=_owner_context(resolved),
        authoritative_native_schema_profile="conformance.native@1",
        applicable_predicate_denominator=persisted,
    )


@dataclass(frozen=True)
class _VerifiedCase:
    bundle: contract.EncodedChronologyBundle
    result: contract.FullPrefixVerified
    persisted: contract.PersistedChronologyProof


def _verified_case(
    reconciliation: contract.NativeChronologyReconciliation,
    *,
    requested_query_context_ref: contract.Digest | None = None,
) -> _VerifiedCase:
    candidate = reconciliation.owner_context.owner_qualified_candidate.candidate
    query = reconciliation.owner_context.query
    request = contract.ChronologyBundleRequest(
        domain=query.domain,
        native_schema_profile=reconciliation.authoritative_native_schema_profile,
        declared_denominator_ref=candidate.declared_denominator_ref,
        requested_cutoff_ref=query.requested_cutoff_ref,
        requested_query_context_ref=(
            requested_query_context_ref or query.requested_query_context_ref
        ),
        members=candidate.ordered_members,
    )
    bundle = core.build_full_prefix_bundle(request)
    assert isinstance(bundle, contract.EncodedChronologyBundle)
    result = core.FullPrefixVerifier().verify_bundle(
        bundle.bundle_bytes,
        expected_domain=request.domain,
        expected_bundle_content_hash=bundle.bundle_content_hash,
    )
    assert isinstance(result, contract.FullPrefixVerified)
    bundle_ref = _raw_artifact_ref(
        bundle.bundle_bytes,
        kind="core.chronology.full_prefix.bundle",
    )
    statement = contract.FullPrefixVerificationStatement(
        schema_version="polisyos.chronology.full-prefix-verification-result.v1",
        bundle_ref=bundle_ref,
        expected_domain=request.domain,
        expected_prefix=None,
        expected_bundle_content_hash=bundle.bundle_content_hash,
        result=result,
    )
    statement_bytes = contract._frame_record(
        contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
    )
    verifier_result_ref = _raw_artifact_ref(
        statement_bytes,
        kind="core.chronology.full_prefix.verification_result",
    )
    persisted = contract.PersistedChronologyProof(
        result_kind="persisted",
        artifact_ref=bundle_ref,
        cas_raw_bytes_hash=str(bundle_ref.artifact_id),
        protocol_bundle_content_hash=bundle.bundle_content_hash,
        parsed_header=bundle.header,
        verifier_result_ref=verifier_result_ref,
        verifier_result_content_hash=contract._verification_statement_content_hash(statement),
        verification_statement=statement,
    )
    return _VerifiedCase(bundle=bundle, result=result, persisted=persisted)


def test_zero_member_golden_vector_is_byte_exact() -> None:
    request = contract.ChronologyBundleRequest(
        domain=_domain(),
        native_schema_profile="conformance.native@1",
        declared_denominator_ref=_digest("1"),
        requested_cutoff_ref=_digest("2"),
        requested_query_context_ref=_digest("3"),
        members=(),
    )

    header = contract._build_header(request=request, commitments=(), native_bytes_total=0)
    header_bytes = contract._canonical_raw_bytes(contract._header_raw_mapping(header))
    bundle = contract._frame_record(header_bytes)

    assert contract._domain_genesis(request.domain) == (
        "sha256:70b86458fbe5bda54106d0c684165bc7f6096c2ade34e95dbcb14e04e9031af8"
    )
    assert len(header_bytes) == 773
    assert bundle[:8].hex() == "0000000000000305"
    assert len(bundle) == 781
    assert contract._bundle_content_hash(bundle) == (
        "sha256:48f4eed374a1155203437f296bf9f9f309233f7d8ba7c5fdc161c52df259390b"
    )
    assert b'"first_commitment":null' in header_bytes


def test_canonical_profile_rejects_models_dataclasses_and_floats() -> None:
    class Payload(BaseModel):
        value: int

    @dataclass
    class DataclassPayload:
        value: int

    with pytest.raises(TypeError, match="raw mapping"):
        contract._canonical_raw_bytes(Payload(value=1))
    with pytest.raises(TypeError, match="raw mapping"):
        contract._canonical_raw_bytes(DataclassPayload(value=1))
    with pytest.raises(ValueError, match="float forbidden"):
        contract._canonical_raw_bytes({"value": 1.0})


def test_every_wire_model_is_strict_frozen_and_schema_rebuilt() -> None:
    instance = _domain()
    with pytest.raises(ValidationError):
        contract.ChronologyProofDomain.model_validate(
            {**instance.model_dump(mode="python"), "unknown": "blocked"}
        )
    with pytest.raises(ValidationError):
        instance.family = "movement"  # type: ignore[misc]

    for model in contract.CHRONOLOGY_WIRE_MODELS:
        schema = model.model_json_schema()
        assert schema["additionalProperties"] is False


def test_wire_dtos_and_operations_are_reexported_only_through_core_root() -> None:
    assert core.ChronologyProofDomain is contract.ChronologyProofDomain
    assert core.NativeChronologyQualificationResult is contract.NativeChronologyQualificationResult
    assert (
        core.PolicyOwnerDenominatorMismatchFailure is contract.PolicyOwnerDenominatorMismatchFailure
    )
    assert "NativeDenominatorRejected" not in core.__all__
    assert (
        core_contracts.PolicyOwnerDenominatorMismatchFailure
        is contract.PolicyOwnerDenominatorMismatchFailure
    )
    assert "NativeDenominatorRejected" not in core_contracts.__all__
    assert core.FullPrefixVerificationResult is contract.FullPrefixVerificationResult
    assert core.build_full_prefix_bundle.__module__ == "polisyos.core.security.full_prefix"
    assert core.FullPrefixVerifier.__module__ == "polisyos.core.security.full_prefix"


def test_entry_process_generation_failure_is_a_query_bound_thirteenth_arm() -> None:
    query = _query()
    result = contract.NativeQualificationProcessGenerationNotEstablished(
        result_kind="qualification_process_generation_not_established",
        status="not_established",
        code="qualification_process_generation_not_established",
        query=query,
    )

    adapter = TypeAdapter(contract.NativeChronologyQualificationResult)
    parsed = adapter.validate_python(result.model_dump(mode="python"))

    assert parsed == result
    assert len(adapter.json_schema()["oneOf"]) == 13
    assert set(result.__class__.model_fields) == {
        "result_kind",
        "status",
        "code",
        "query",
    }
    with pytest.raises(ValidationError):
        contract.NativeQualificationProcessGenerationNotEstablished.model_validate(
            {**result.model_dump(mode="python"), "owner_context": object()}
        )


def test_denominator_mismatch_is_a_pre_positive_query_bound_failure() -> None:
    query = _query()
    failure = contract.PolicyOwnerDenominatorMismatchFailure(
        code="native_denominator_mismatch",
        status="rejected",
        key=_policy_statement(required_native_head_role=None).key,
        requested_query_context_ref=query.requested_query_context_ref,
        expected_denominator_ref=_digest("1"),
        observed_denominator_ref=_digest("2"),
    )
    result = contract.NativeChronologyPolicyResolutionFailed(
        result_kind="policy_resolution_failed",
        query=query,
        failure=failure,
    )

    parsed = TypeAdapter(contract.NativeChronologyQualificationResult).validate_python(
        result.model_dump(mode="python")
    )

    assert parsed == result
    assert parsed.failure.expected_denominator_ref == _digest("1")
    assert parsed.failure.observed_denominator_ref == _digest("2")
    qualification_schema = TypeAdapter(contract.NativeChronologyQualificationResult).json_schema()
    assert set(qualification_schema["discriminator"]["mapping"]) == {
        "build_rejected",
        "native_authority_head_not_established",
        "native_exterior_and_authority_head_not_established",
        "native_exterior_not_established",
        "persistence_failed",
        "policy_resolution_failed",
        "predicate_denominator_persistence_failed",
        "predicate_rejected",
        "profile_rejected",
        "projection_custody_gap",
        "proof_rejected",
        "qualification_process_generation_not_established",
        "qualified",
    }
    owner_failure_schema = TypeAdapter(contract.PredicatePolicyOwnerRelationFailure).json_schema()
    assert set(owner_failure_schema["discriminator"]["mapping"]) == {
        "native_denominator_mismatch",
        "policy_owner_relation_not_established",
        "policy_owner_relation_rejected",
    }
    assert len(TypeAdapter(contract.NativeChronologyCandidateRejected).json_schema()["anyOf"]) == 3
    assert "NativeDenominatorRejected" not in contract.__all__
    assert "PolicyOwnerDenominatorMismatchFailure" in contract.__all__
    with pytest.raises(
        ValidationError, match="policy failure carries a different query coordinate"
    ):
        contract.NativeChronologyPolicyResolutionFailed(
            result_kind="policy_resolution_failed",
            query=_query(context_fill="4"),
            failure=failure,
        )
    wrong_key = contract.PredicatePolicySelectionKey(
        family=query.domain.family,
        proof_domain=query.domain.proof_domain,
        scope_ref=_digest("f"),
        authority_purpose=query.domain.authority_purpose,
        requested_cutoff_ref=query.requested_cutoff_ref,
    )
    wrong_key_failure = contract.PolicyOwnerDenominatorMismatchFailure(
        code="native_denominator_mismatch",
        status="rejected",
        key=wrong_key,
        requested_query_context_ref=query.requested_query_context_ref,
        expected_denominator_ref=_digest("1"),
        observed_denominator_ref=_digest("2"),
    )
    with pytest.raises(
        ValidationError,
        match="policy failure carries a key that differs from the full query",
    ):
        contract.NativeChronologyPolicyResolutionFailed(
            result_kind="policy_resolution_failed",
            query=query,
            failure=wrong_key_failure,
        )
    with pytest.raises(ValidationError, match="denominator mismatch requires unequal refs"):
        contract.PolicyOwnerDenominatorMismatchFailure(
            **{
                **failure.model_dump(mode="python"),
                "observed_denominator_ref": failure.expected_denominator_ref,
            }
        )


def test_policy_head_requirement_is_required_nullable_and_canonical_null() -> None:
    no_head = _policy_statement(required_native_head_role=None)
    required_head = _policy_statement(required_native_head_role="epoch_authority_head")

    raw_mapping = contract._raw_model_mapping(no_head)
    canonical = contract._canonical_raw_bytes(raw_mapping)

    assert "required_native_head_role" in raw_mapping
    assert raw_mapping["required_native_head_role"] is None
    assert contract.PredicateAdmissionPolicyStatement.model_fields[
        "required_native_head_role"
    ].is_required()
    assert b'"required_native_head_role":null' in canonical
    assert contract._predicate_policy_content_hash(no_head) == (
        "sha256:d514a5a766a178ef4bd6b0035c48ac14922f5a88d23ece5730a012a305652a26"
    )
    assert contract._predicate_policy_content_hash(required_head) != (
        contract._predicate_policy_content_hash(no_head)
    )
    with pytest.raises(ValidationError):
        contract.PredicateAdmissionPolicyStatement.model_validate(
            {
                key: value
                for key, value in no_head.model_dump(mode="python").items()
                if key != "required_native_head_role"
            }
        )
    with pytest.raises(ValidationError):
        _policy_statement(required_native_head_role="")


def test_lowercase_digest_and_nonnegative_counts_fail_closed() -> None:
    with pytest.raises(ValidationError):
        contract.ChronologyProofDomain(
            format="polisyos.chronology.full-prefix.v1",
            profile="full_prefix_canon_json_0_2_0_sha256_256_v1",
            proof_domain="conformance",
            family="epoch",
            scope_ref="sha256:" + "A" * 64,
            authority_purpose="publication",
        )
    with pytest.raises(ValidationError):
        contract.ExpectedCommitmentPrefix(
            domain=_domain(), member_count=-1, commitment_head=_digest("0")
        )


@pytest.mark.parametrize(
    ("status", "failure_code", "accepted"),
    [
        ("satisfied", None, True),
        ("satisfied", "unexpected", False),
        ("rejected", "owner_rejected", True),
        ("rejected", None, False),
        ("not_established", "evidence_missing", True),
        ("not_established", None, False),
    ],
)
def test_predicate_failure_code_is_present_exactly_for_non_satisfied_status(
    status: str,
    failure_code: str | None,
    accepted: bool,
) -> None:
    payload = {
        "predicate_id": "member_admitted",
        "predicate_class": "independently_reconciled",
        "status": status,
        "evidence_ref": _ref("8"),
        "failure_code": failure_code,
    }
    if accepted:
        assert contract.PredicateDisposition.model_validate(payload).status == status
    else:
        with pytest.raises(ValidationError):
            contract.PredicateDisposition.model_validate(payload)


def test_policy_and_denominator_reject_duplicate_rules_and_subjects_before_hashing() -> None:
    rule = contract.PredicateAdmissionRule(
        predicate_id="member_admitted",
        subject_kind="member",
        admitted_classes=("recomputed", "independently_reconciled"),
    )
    key = contract.PredicatePolicySelectionKey(
        family="epoch",
        proof_domain="conformance",
        scope_ref=_digest("0"),
        authority_purpose="publication",
        requested_cutoff_ref=_digest("2"),
    )
    with pytest.raises(ValidationError, match="duplicate predicate rule"):
        contract.PredicateAdmissionPolicyStatement(
            schema_version="polisyos.chronology.predicate-policy.v1",
            key=key,
            native_schema_profile="conformance.native@1",
            required_native_head_role=None,
            rules=(rule, rule),
            owner_provenance_ref=_ref("9"),
            owner_provenance_content_hash=_digest("a"),
        )

    with pytest.raises(ValidationError, match="duplicate member_subject_ref"):
        contract.ApplicablePredicateDenominatorStatement(
            schema_version=("polisyos.chronology.applicable-predicate-denominator.v1"),
            policy_ref=_ref("9"),
            policy_content_hash=_digest("a"),
            member_subject_refs=(_digest("4"), _digest("4")),
            required_member_predicate_pairs=((_digest("4"), "member_admitted"),),
            required_query_predicate_ids=("denominator_complete",),
        )


def test_owner_evidence_optional_triple_is_all_present_or_all_absent() -> None:
    base = {
        "subject_kind": "member",
        "subject_ref": _digest("4"),
        "predicate_id": "member_admitted",
        "predicate_class": "independently_reconciled",
        "status": "satisfied",
    }
    with pytest.raises(ValidationError, match="all present or all absent"):
        contract.VerifiedOwnerPredicateEvidence(
            **base,
            evidence_ref=_ref("8"),
            evidence_content_hash=None,
            evidence_verifier_provenance_ref=None,
        )


def test_failure_descriptor_and_evaluation_denominators_are_closed() -> None:
    enum_members: set[tuple[type[StrEnum], StrEnum]] = set()
    for enum_type in (
        contract.FullPrefixInvocationFailureCode,
        contract.FullPrefixEnvelopeFailureCode,
        contract.FullPrefixMemberFailureCode,
        contract.FullPrefixInternalConsistencyFailureCode,
        contract.FullPrefixExpectedPrefixFailureCode,
    ):
        enum_members.update((enum_type, member) for member in enum_type)

    described = {
        (type(descriptor.code), descriptor.code)
        for descriptor in contract.FULL_PREFIX_FAILURE_DESCRIPTORS
    }
    assert described == enum_members
    assert len(described) == len(contract.FULL_PREFIX_FAILURE_DESCRIPTORS)
    assert len(contract.FULL_PREFIX_EVALUATION_TABLE) == 20
    assert set(contract.FULL_PREFIX_TERMINAL_BY_RESULT_KIND) == {
        "verified",
        "invocation_rejected",
        "envelope_rejected",
        "member_rejected",
        "internal_consistency_rejected",
        "expected_prefix_rejected",
    }


@pytest.mark.parametrize(
    ("member_count", "header_frame_bytes", "member_frame_bytes", "native_frame_bytes"),
    [
        (contract.FULL_PREFIX_MAX_MEMBERS + 1, 1, (), ()),
        (0, contract.FULL_PREFIX_MAX_HEADER_FRAME_BYTES + 1, (), ()),
        (1, 1, (contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES + 1,), (1,)),
        (
            1,
            contract.FULL_PREFIX_MAX_HEADER_FRAME_BYTES,
            (contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES,),
            (
                contract.FULL_PREFIX_MAX_BUNDLE_BYTES
                - contract.FULL_PREFIX_MAX_HEADER_FRAME_BYTES
                - contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES
                + 1,
            ),
        ),
    ],
)
def test_each_frozen_capacity_crossing_returns_the_one_profile_failure(
    member_count: int,
    header_frame_bytes: int,
    member_frame_bytes: tuple[int, ...],
    native_frame_bytes: tuple[int, ...],
) -> None:
    failure = contract._profile_capacity_failure(
        domain=_domain(),
        member_count=member_count,
        header_frame_bytes=header_frame_bytes,
        member_frame_bytes=member_frame_bytes,
        native_frame_bytes=native_frame_bytes,
    )
    assert failure is not None
    assert (
        failure.failure_code is contract.FullPrefixBuildFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED
    )


def test_native_candidate_content_hash_binds_every_candidate_field() -> None:
    member = _member()
    candidate = contract.NativeChronologyCandidate(
        query=_query(),
        declared_denominator_ref=_digest("1"),
        native_denominator_artifact_ref=_ref("b", kind="denominator"),
        native_denominator_content_hash=_digest("1"),
        query_context_artifact_ref=_ref("c", kind="query-context"),
        query_context_content_hash=_digest("3"),
        ordered_members=(member,),
        member_predicates=(
            contract.MemberPredicateDisposition(
                member_ref=member.member_ref,
                disposition=contract.PredicateDisposition(
                    predicate_id="member_admitted",
                    predicate_class="independently_reconciled",
                    status="satisfied",
                    evidence_ref=_ref("8"),
                    failure_code=None,
                ),
            ),
        ),
        query_predicates=(
            contract.QueryPredicateDisposition(
                requested_query_context_ref=_digest("3"),
                disposition=contract.PredicateDisposition(
                    predicate_id="denominator_complete",
                    predicate_class="independently_reconciled",
                    status="satisfied",
                    evidence_ref=_ref("d"),
                    failure_code=None,
                ),
            ),
        ),
        exterior_limitation_code=None,
        native_authority_head_refs=(_digest("e"),),
    )
    original = contract._native_candidate_content_hash(candidate)
    changed = candidate.model_copy(update={"native_authority_head_refs": (_digest("f"),)})
    assert contract._native_candidate_content_hash(changed) != original


def test_native_candidate_rejects_blank_exterior_limitation_code() -> None:
    candidate = _owner_qualified_candidate().candidate

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        contract.NativeChronologyCandidate.model_validate(
            {
                **candidate.model_dump(mode="python"),
                "exterior_limitation_code": "",
            }
        )


def test_query_cannot_carry_adapter_selected_profile_or_policy() -> None:
    payload = _query().model_dump(mode="python")
    for forbidden in (
        "native_schema_profile",
        "policy_ref",
        "policy_version",
        "accepted",
        "authority_head",
        "current",
        "complete",
        "lineage",
    ):
        with pytest.raises(ValidationError):
            contract.NativeChronologyQuery.model_validate({**payload, forbidden: "caller"})


def test_denominator_adapter_persists_reloads_and_detects_live_store_corruption(
    tmp_path: Path,
) -> None:
    qualified = _owner_qualified_candidate()
    policy = qualified.owner_relation_verification.policy_owner_provenance
    statement = contract.ApplicablePredicateDenominatorStatement(
        schema_version="polisyos.chronology.applicable-predicate-denominator.v1",
        policy_ref=policy.policy_ref,
        policy_content_hash=policy.policy_content_hash,
        member_subject_refs=tuple(
            member.member_ref for member in qualified.candidate.ordered_members
        ),
        required_member_predicate_pairs=(),
        required_query_predicate_ids=(),
    )
    store = FileSystemCAS(tmp_path / "cas")
    adapter = contract.ChronologyApplicablePredicateDenominatorArtifacts(store=store)

    persisted = adapter.persist_and_verify(
        query=qualified.candidate.query,
        statement=statement,
        owner_qualified_candidate=qualified,
    )

    assert isinstance(persisted, contract.PersistedApplicablePredicateDenominator)
    assert persisted.statement == statement
    assert persisted.cas_raw_bytes_hash == str(persisted.artifact_ref.artifact_id)
    assert store.verify(persisted.artifact_ref.artifact_id).ok is True
    manifest = store.get_manifest(persisted.artifact_ref.artifact_id)
    assert manifest.kind == "core.chronology.applicable_predicate_denominator"
    assert manifest.media_type == "application/octet-stream"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == ("polisyos.chronology.ApplicablePredicateDenominator")
    assert manifest.artifact_schema.version == "1"

    blob, _ = store.get_paths(persisted.artifact_ref.artifact_id)
    blob.write_bytes(b"corrupt")
    corrupted = adapter.persist_and_verify(
        query=qualified.candidate.query,
        statement=statement,
        owner_qualified_candidate=qualified,
    )
    assert isinstance(corrupted, contract.ApplicablePredicateDenominatorArtifactFailure)
    assert corrupted.status == "not_established"
    assert corrupted.evidence_ref == persisted.artifact_ref


def test_owner_context_rejects_policy_identity_not_bound_by_owner_receipt() -> None:
    qualified = _owner_qualified_candidate()
    context = _owner_context(qualified)

    with pytest.raises(ValidationError, match="policy identity differs from owner receipt"):
        contract.NativeChronologyOwnerContext.model_validate(
            {
                **context.model_dump(mode="python"),
                "predicate_admission_policy_ref": _ref("f", kind="predicate-policy"),
            }
        )


@pytest.mark.parametrize("changed_copy", ["semantic_hash", "raw_identity"])
def test_persisted_denominator_rejects_self_inconsistent_identity_copies(
    tmp_path: Path,
    changed_copy: str,
) -> None:
    persisted = _reconciliation(tmp_path).applicable_predicate_denominator
    payload = persisted.model_dump(mode="python")
    if changed_copy == "semantic_hash":
        payload["denominator_content_hash"] = _digest("f")
    else:
        payload["cas_raw_bytes_hash"] = _digest("f")

    with pytest.raises(ValidationError, match=r"denominator .* identity"):
        contract.PersistedApplicablePredicateDenominator.model_validate(payload)


@pytest.mark.parametrize("changed_relation", ["policy", "members"])
def test_reconciliation_rejects_denominator_not_bound_to_owner_candidate(
    tmp_path: Path,
    changed_relation: str,
) -> None:
    reconciliation = _reconciliation(tmp_path)
    statement_payload = reconciliation.applicable_predicate_denominator.statement.model_dump(
        mode="python"
    )
    if changed_relation == "policy":
        statement_payload["policy_ref"] = _ref("f", kind="predicate-policy")
        statement_payload["policy_content_hash"] = _digest("f")
    else:
        statement_payload["member_subject_refs"] = (_digest("f"),)
    statement = contract.ApplicablePredicateDenominatorStatement.model_validate(statement_payload)
    internally_consistent = _self_consistent_denominator(statement)

    with pytest.raises(ValidationError, match=r"denominator .* differs"):
        contract.NativeChronologyReconciliation(
            owner_context=reconciliation.owner_context,
            authoritative_native_schema_profile=(
                reconciliation.authoritative_native_schema_profile
            ),
            applicable_predicate_denominator=internally_consistent,
        )


def test_predicate_rejection_rejects_evidence_absent_from_owner_receipt() -> None:
    context = _owner_context(_owner_qualified_candidate())

    with pytest.raises(ValidationError, match="evidence is absent from owner receipt"):
        contract.NativePredicateRejected(
            result_kind="predicate_rejected",
            code="native_predicate_inadmissible",
            owner_context=context,
            evidence_refs=(_ref("f", kind="predicate-evidence"),),
        )


def test_build_rejection_binds_domain_and_member_count_to_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reconciliation = _reconciliation(tmp_path)
    candidate = reconciliation.owner_context.owner_qualified_candidate.candidate
    foreign_domain = _domain(family="inventory", scope_fill="f")
    request = contract.ChronologyBundleRequest(
        domain=foreign_domain,
        native_schema_profile=reconciliation.authoritative_native_schema_profile,
        declared_denominator_ref=candidate.declared_denominator_ref,
        requested_cutoff_ref=reconciliation.owner_context.query.requested_cutoff_ref,
        requested_query_context_ref=(
            reconciliation.owner_context.query.requested_query_context_ref
        ),
        members=candidate.ordered_members,
    )
    monkeypatch.setattr(contract, "FULL_PREFIX_MAX_MEMBERS", 0)
    rejected = core.build_full_prefix_bundle(request)
    assert isinstance(rejected, contract.FullPrefixBuildRejected)

    with pytest.raises(
        ValidationError,
        match=r"build rejection .* differs from reconciliation",
    ):
        contract.NativeFullPrefixBuildRejected(
            result_kind="build_rejected",
            reconciliation=reconciliation,
            build_result=rejected,
        )


def _foreign_prefix_rejection(
    reconciliation: contract.NativeChronologyReconciliation,
) -> contract.FullPrefixExpectedPrefixRejected:
    foreign = _verified_case(
        reconciliation,
        requested_query_context_ref=_digest("f"),
    )
    rejected = core.FullPrefixVerifier().verify_bundle(
        foreign.bundle.bundle_bytes,
        expected_domain=reconciliation.owner_context.query.domain,
        expected_prefix=contract.ExpectedCommitmentPrefix(
            domain=reconciliation.owner_context.query.domain,
            member_count=foreign.bundle.header.member_count,
            commitment_head=_digest("e"),
        ),
        expected_bundle_content_hash=foreign.bundle.bundle_content_hash,
    )
    assert isinstance(rejected, contract.FullPrefixExpectedPrefixRejected)
    return rejected


def test_native_proof_rejection_binds_parsed_header_to_reconciliation(tmp_path: Path) -> None:
    reconciliation = _reconciliation(tmp_path)
    rejected = _foreign_prefix_rejection(reconciliation)

    with pytest.raises(ValidationError, match="proof header differs from reconciliation"):
        contract.NativeFullPrefixProofRejected(
            result_kind="proof_rejected",
            code="full_prefix_proof_rejected",
            reconciliation=reconciliation,
            proof_result=rejected,
        )


@pytest.mark.parametrize(
    "terminal_kind",
    ["qualified", "exterior", "head", "combined", "projection"],
)
def test_verified_terminal_proof_header_binds_reconciliation(
    tmp_path: Path,
    terminal_kind: str,
) -> None:
    exterior = "owner-exterior" if terminal_kind in {"exterior", "combined"} else None
    reconciliation = _reconciliation(
        tmp_path,
        qualified=_owner_qualified_candidate(exterior_limitation_code=exterior),
    )
    foreign = _verified_case(
        reconciliation,
        requested_query_context_ref=_digest("f"),
    )

    with pytest.raises(ValidationError, match="proof header differs from reconciliation"):
        if terminal_kind == "qualified":
            contract.NativeChronologyQualified(
                result_kind="qualified",
                reconciliation=reconciliation,
                proof_result=foreign.result,
                persisted_proof=foreign.persisted,
            )
        elif terminal_kind == "exterior":
            contract.NativeExteriorNotEstablished(
                result_kind="native_exterior_not_established",
                code="native_exterior_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code="owner-exterior",
                proof_result=foreign.result,
            )
        elif terminal_kind == "head":
            contract.NativeAuthorityHeadNotEstablished(
                result_kind="native_authority_head_not_established",
                code="native_authority_head_not_established",
                reconciliation=reconciliation,
                required_native_head_role="owner-head",
                proof_result=foreign.result,
            )
        elif terminal_kind == "combined":
            contract.NativeExteriorAndAuthorityHeadNotEstablished(
                result_kind="native_exterior_and_authority_head_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code="owner-exterior",
                required_native_head_role="owner-head",
                proof_result=foreign.result,
            )
        else:
            contract.NativeProjectionCustodyGap(
                result_kind="projection_custody_gap",
                status="native_not_established",
                code="native_projection_custody_gap",
                reconciliation=reconciliation,
                proof_result=foreign.result,
                missing_projection_receipt_role="native_projection_receipt",
            )


@pytest.mark.parametrize(
    "mask_fabrication",
    [
        "exterior_absent",
        "exterior_changed",
        "head_present",
        "head_with_exterior",
        "combined_exterior_absent",
        "combined_head_present",
        "projection_with_exterior",
    ],
)
def test_native_limitation_leaves_reject_carrier_observable_inverse_masks(
    tmp_path: Path,
    mask_fabrication: str,
) -> None:
    candidate_exterior = (
        "owner-exterior"
        if mask_fabrication
        in {
            "exterior_changed",
            "head_with_exterior",
            "combined_head_present",
            "projection_with_exterior",
        }
        else None
    )
    candidate_heads = (
        (_digest("e"),) if mask_fabrication in {"head_present", "combined_head_present"} else ()
    )
    reconciliation = _reconciliation(
        tmp_path,
        qualified=_owner_qualified_candidate(
            exterior_limitation_code=candidate_exterior,
            native_authority_head_refs=candidate_heads,
        ),
    )
    proof = _verified_case(reconciliation).result

    with pytest.raises(ValidationError, match="limitation mask"):
        if mask_fabrication in {"exterior_absent", "exterior_changed"}:
            contract.NativeExteriorNotEstablished(
                result_kind="native_exterior_not_established",
                code="native_exterior_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code="claimed-exterior",
                proof_result=proof,
            )
        elif mask_fabrication in {"head_present", "head_with_exterior"}:
            contract.NativeAuthorityHeadNotEstablished(
                result_kind="native_authority_head_not_established",
                code="native_authority_head_not_established",
                reconciliation=reconciliation,
                required_native_head_role="owner-head",
                proof_result=proof,
            )
        elif mask_fabrication in {"combined_exterior_absent", "combined_head_present"}:
            contract.NativeExteriorAndAuthorityHeadNotEstablished(
                result_kind="native_exterior_and_authority_head_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code="owner-exterior",
                required_native_head_role="owner-head",
                proof_result=proof,
            )
        else:
            contract.NativeProjectionCustodyGap(
                result_kind="projection_custody_gap",
                status="native_not_established",
                code="native_projection_custody_gap",
                reconciliation=reconciliation,
                proof_result=proof,
                missing_projection_receipt_role="native_projection_receipt",
            )


@pytest.mark.parametrize(
    "persisted_fabrication",
    ["protocol_hash", "parsed_header", "bundle_ref", "sidecar_hash"],
)
def test_persisted_proof_rejects_self_inconsistent_copies(
    tmp_path: Path,
    persisted_fabrication: str,
) -> None:
    reconciliation = _reconciliation(tmp_path)
    verified = _verified_case(reconciliation)
    payload = verified.persisted.model_dump(mode="python")
    if persisted_fabrication == "protocol_hash":
        payload["protocol_bundle_content_hash"] = _digest("f")
    elif persisted_fabrication == "parsed_header":
        payload["parsed_header"] = _verified_case(
            reconciliation,
            requested_query_context_ref=_digest("f"),
        ).bundle.header
    elif persisted_fabrication == "bundle_ref":
        statement = verified.persisted.verification_statement.model_copy(
            update={"bundle_ref": _ref("f", kind="full-prefix-bundle")}
        )
        payload["verification_statement"] = statement
    else:
        payload["verifier_result_content_hash"] = _digest("f")

    with pytest.raises(ValidationError, match=r"persisted proof .* differs"):
        contract.PersistedChronologyProof.model_validate(payload)


def test_qualified_leaf_rejects_a_different_persisted_verified_proof(tmp_path: Path) -> None:
    reconciliation = _reconciliation(tmp_path)
    base = _verified_case(reconciliation)
    foreign = _verified_case(
        reconciliation,
        requested_query_context_ref=_digest("f"),
    )

    with pytest.raises(ValidationError, match="persisted proof differs from verified proof"):
        contract.NativeChronologyQualified(
            result_kind="qualified",
            reconciliation=reconciliation,
            proof_result=base.result,
            persisted_proof=foreign.persisted,
        )


def test_persistence_verification_failure_binds_parsed_header_to_reconciliation(
    tmp_path: Path,
) -> None:
    reconciliation = _reconciliation(tmp_path)
    rejected = _foreign_prefix_rejection(reconciliation)
    failure = contract.ChronologyPersistenceVerificationMismatch(
        failure_kind="verification_mismatch",
        disposition="rejected",
        query=reconciliation.owner_context.query,
        proof_result=rejected,
    )

    with pytest.raises(ValidationError, match="proof header differs from reconciliation"):
        contract.NativeChronologyPersistenceFailed(
            result_kind="persistence_failed",
            reconciliation=reconciliation,
            failure=failure,
        )
