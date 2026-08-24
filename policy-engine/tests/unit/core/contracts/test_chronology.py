from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import polisyos.core as core
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


def _owner_qualified_candidate() -> contract.OwnerQualifiedNativeCandidate:
    member = _member()
    query = _query()
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
        query=query,
        declared_denominator_ref=_digest("1"),
        native_denominator_artifact_ref=_ref("b", kind="native-denominator"),
        native_denominator_content_hash=_digest("1"),
        query_context_artifact_ref=_ref("c", kind="query-context"),
        query_context_content_hash=_digest("3"),
        ordered_members=(member,),
        member_predicates=(),
        query_predicates=(),
        exterior_limitation_code=None,
        native_authority_head_refs=(),
    )
    candidate_hash = contract._native_candidate_content_hash(candidate)
    owner_relation = contract.VerifiedPredicatePolicyOwnerRelation(
        query=query,
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
            subject_ref=query.requested_query_context_ref,
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
    assert core.FullPrefixVerificationResult is contract.FullPrefixVerificationResult
    assert core.build_full_prefix_bundle.__module__ == "polisyos.core.security.full_prefix"
    assert core.FullPrefixVerifier.__module__ == "polisyos.core.security.full_prefix"


def test_entry_process_generation_failure_is_a_query_bound_fourteenth_arm() -> None:
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
    assert len(adapter.json_schema()["oneOf"]) == 14
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
