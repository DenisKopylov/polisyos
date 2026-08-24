from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import (
    FullPrefixVerifier,
    build_full_prefix_bundle,
)
from polisyos.runtime.quality import chronology_proof, chronology_qualification
from tests._helpers.chronology_qualification import (
    EpochLikeQualificationAdapter,
    OpaqueInventoryQualificationAdapter,
    QualificationCase,
    make_qualification_case,
)


@pytest.fixture(autouse=True)
def _clear_owner_appointment() -> Any:
    registry = chronology_proof._PERSISTENCE_REGISTRY
    registry._clear_for_test()
    yield
    registry._clear_for_test()


def _bundle_request(case: QualificationCase) -> contract.ChronologyBundleRequest:
    candidate = case.adapter.candidate
    profile = (
        candidate.ordered_members[0].native_schema_profile
        if candidate.ordered_members
        else case.policy.statement.native_schema_profile
    )
    return contract.ChronologyBundleRequest(
        domain=case.query.domain,
        native_schema_profile=profile,
        declared_denominator_ref=candidate.declared_denominator_ref,
        requested_cutoff_ref=case.query.requested_cutoff_ref,
        requested_query_context_ref=case.query.requested_query_context_ref,
        members=candidate.ordered_members,
    )


def _build(case: QualificationCase) -> contract.EncodedChronologyBundle:
    built = build_full_prefix_bundle(_bundle_request(case))
    assert isinstance(built, contract.EncodedChronologyBundle)
    return built


def _qualify(case: QualificationCase) -> contract.NativeChronologyQualificationResult:
    return case.appoint_consumer().qualify(adapter=case.adapter, request=case.query)


def _verified_result(
    result: contract.NativeChronologyQualificationResult,
) -> contract.FullPrefixVerified:
    assert isinstance(
        result,
        (
            contract.NativeProjectionCustodyGap,
            contract.NativeExteriorNotEstablished,
            contract.NativeAuthorityHeadNotEstablished,
            contract.NativeExteriorAndAuthorityHeadNotEstablished,
        ),
    )
    return result.proof_result


def _foreign_scope_query(
    query: contract.NativeChronologyQuery,
) -> contract.NativeChronologyQuery:
    return query.model_copy(
        update={
            "domain": query.domain.model_copy(
                update={"scope_ref": contract._sha256_digest(b"parent-scope")}
            )
        }
    )


def _assert_owner_policy_changes_authority_not_proof(root: Path) -> None:
    no_head_required = make_qualification_case(
        root / "optional",
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(),
    )
    head_required = make_qualification_case(
        root / "required",
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(),
        required_native_head_role="current_epoch",
    )
    optional_result = _qualify(no_head_required)
    required_result = _qualify(head_required)
    assert isinstance(optional_result, contract.NativeProjectionCustodyGap)
    assert isinstance(required_result, contract.NativeAuthorityHeadNotEstablished)
    assert (
        optional_result.proof_result.bundle_content_hash
        == required_result.proof_result.bundle_content_hash
    )


def _assert_valid_prefix_omission_fails_owner_denominator(root: Path) -> None:
    case = make_qualification_case(
        root,
        shape="inventory",
        member_count=2,
        candidate_member_ordinals=(0,),
    )
    built = _build(case)
    verified = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=case.query.domain,
    )
    assert isinstance(verified, contract.FullPrefixVerified)
    result = _qualify(case)
    assert isinstance(result, contract.NativeChronologyPolicyResolutionFailed)
    assert result.failure.code == "native_denominator_mismatch"
    assert result.failure.expected_denominator_ref == case.owner_denominator_ref


@pytest.mark.parametrize("shape", ["epoch", "inventory"])
def test_two_native_shapes_preserve_scope_and_reject_parent_scope(
    tmp_path: Path,
    shape: str,
) -> None:
    case = make_qualification_case(tmp_path / shape, shape=shape, member_count=2)
    accepted = _qualify(case)
    assert isinstance(accepted, contract.NativeProjectionCustodyGap)
    assert accepted.proof_result.parsed_header.scope_ref == case.query.domain.scope_ref

    foreign_query = _foreign_scope_query(case.query)
    rejected = case.appoint_consumer().qualify(
        adapter=case.adapter,
        request=foreign_query,
    )
    assert isinstance(rejected, contract.NativeChronologyPolicyResolutionFailed)
    assert rejected.failure.code == "policy_admission_missing"


def test_sparse_native_time_roles_are_not_fabricated(tmp_path: Path) -> None:
    epoch = make_qualification_case(tmp_path / "epoch", shape="epoch", member_count=2)
    inventory = make_qualification_case(tmp_path / "inventory", shape="inventory", member_count=2)
    epoch_result = _qualify(epoch)
    inventory_result = _qualify(inventory)
    epoch_header = _verified_result(epoch_result).parsed_header
    inventory_header = _verified_result(inventory_result).parsed_header

    forbidden = {"epoch_ref", "valid", "effect", "visibility", "knowledge", "branch"}
    assert forbidden.isdisjoint(type(epoch_header).model_fields)
    assert forbidden.isdisjoint(type(inventory_header).model_fields)
    assert isinstance(epoch.adapter, EpochLikeQualificationAdapter)
    assert isinstance(inventory.adapter, OpaqueInventoryQualificationAdapter)
    assert json.loads(inventory.candidate.ordered_members[0].native_bytes)["schema"] == (
        "fixture.opaque-inventory.v1"
    )


def test_common_bundle_requires_no_universal_event_envelope(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)
    built = _build(case)
    records = contract._split_framed_records(built.bundle_bytes)
    header = json.loads(records[0])
    header["event_time"] = "fabricated"
    attacked = contract._frame_record(contract._canonical_raw_bytes(header)) + b"".join(
        contract._frame_record(record) for record in records[1:]
    )
    result = FullPrefixVerifier().verify_bundle(
        attacked,
        expected_domain=case.query.domain,
    )
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)


def test_owner_disposition_changes_without_changing_verified_proof(
    tmp_path: Path,
) -> None:
    _assert_owner_policy_changes_authority_not_proof(tmp_path)


def test_withdrawn_historical_member_remains_membership_verifiable(
    tmp_path: Path,
) -> None:
    case = make_qualification_case(tmp_path, shape="epoch", member_count=2)
    historical = json.loads(case.candidate.ordered_members[0].native_bytes)
    assert historical["status"] == "historical"
    result = _qualify(case)
    proof = _verified_result(result)
    assert proof.verified_member_count == 2


def test_common_surface_cannot_mutate_decision_or_claim_heads() -> None:
    signature = inspect.signature(FullPrefixVerifier.verify_bundle)
    fields = set(contract.ChronologyBundleHeader.model_fields)
    forbidden = {"decision_head", "claim_head", "decision", "claim"}
    assert forbidden.isdisjoint(signature.parameters)
    assert forbidden.isdisjoint(fields)


def test_adapter_cannot_admit_source_or_accept_anchor() -> None:
    parameters = set(
        inspect.signature(
            chronology_qualification.NativeChronologyAuthorityAdapter.reconcile_candidate
        ).parameters
    )
    qualify_parameters = set(
        inspect.signature(chronology_qualification.QualificationConsumer.qualify).parameters
    )
    assert parameters == {"self", "request"}
    assert qualify_parameters == {"self", "adapter", "request"}
    assert {"policy", "admission", "source", "anchor"}.isdisjoint(parameters | qualify_parameters)


def test_owner_denominator_is_complete_before_qualification(tmp_path: Path) -> None:
    _assert_valid_prefix_omission_fails_owner_denominator(tmp_path)


def test_native_byte_substitution_changes_commitment(tmp_path: Path) -> None:
    original = make_qualification_case(tmp_path / "original", shape="inventory", member_count=1)
    annotated = make_qualification_case(
        tmp_path / "annotated",
        shape="inventory",
        member_count=1,
        annotation_revision=1,
    )
    original_proof = FullPrefixVerifier().verify_bundle(
        _build(original).bundle_bytes,
        expected_domain=original.query.domain,
    )
    annotated_proof = FullPrefixVerifier().verify_bundle(
        _build(annotated).bundle_bytes,
        expected_domain=annotated.query.domain,
    )
    assert isinstance(original_proof, contract.FullPrefixVerified)
    assert isinstance(annotated_proof, contract.FullPrefixVerified)
    assert original_proof.commitment_head != annotated_proof.commitment_head


def test_delete_insert_reorder_and_fork_fail_proof_order(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=2)
    built = _build(case)
    records = contract._split_framed_records(built.bundle_bytes)
    mutations = (
        records[:1] + records[3:],
        records + records[1:3],
        records[:1] + records[3:5] + records[1:3],
        [*records[:2], records[2] + b"fork", *records[3:]],
    )
    for mutated_records in mutations:
        attacked = b"".join(contract._frame_record(record) for record in mutated_records)
        result = FullPrefixVerifier().verify_bundle(
            attacked,
            expected_domain=case.query.domain,
        )
        assert not isinstance(result, contract.FullPrefixVerified)


def test_native_multi_head_is_preserved_and_never_time_selected(tmp_path: Path) -> None:
    heads = (
        contract._sha256_digest(b"authority-head-a"),
        contract._sha256_digest(b"authority-head-b"),
    )
    case = make_qualification_case(
        tmp_path,
        shape="epoch",
        member_count=1,
        native_authority_head_refs=heads,
        required_native_head_role="current_branch_heads",
    )
    result = _qualify(case)
    assert isinstance(result, contract.NativeProjectionCustodyGap)
    candidate = result.reconciliation.owner_context.owner_qualified_candidate.candidate
    assert candidate.native_authority_head_refs == heads
    assert "native_authority_head_refs" not in type(result.proof_result.parsed_header).model_fields


def test_unknown_exterior_returns_native_not_established(tmp_path: Path) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
        exterior_limitation_code="outside_owner_denominator",
    )
    result = _qualify(case)
    assert isinstance(result, contract.NativeExteriorNotEstablished)
    assert result.exterior_limitation_code == "outside_owner_denominator"
    assert isinstance(result.proof_result, contract.FullPrefixVerified)


def test_offline_replay_uses_only_frozen_inputs(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=2)
    built = _build(case)
    first = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=case.query.domain,
        expected_bundle_content_hash=built.bundle_content_hash,
    )
    replay = FullPrefixVerifier().verify_bundle(
        bytes(built.bundle_bytes),
        expected_domain=case.query.domain,
        expected_bundle_content_hash=built.bundle_content_hash,
    )
    assert isinstance(first, contract.FullPrefixVerified)
    assert replay == first


def test_projection_suppression_reports_custody_gap_without_rewriting_terminal(
    tmp_path: Path,
) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=2)
    result = _qualify(case)
    assert isinstance(result, contract.NativeProjectionCustodyGap)
    assert result.status == "native_not_established"
    assert result.code == "native_projection_custody_gap"
    assert result.missing_projection_receipt_role == "native_projection_receipt"
    candidate = result.reconciliation.owner_context.owner_qualified_candidate.candidate
    assert candidate == case.candidate


def test_valid_prefix_omitting_owner_member_fails_qualification(tmp_path: Path) -> None:
    _assert_valid_prefix_omission_fails_owner_denominator(tmp_path)


def test_commitment_and_native_authority_heads_are_distinct(tmp_path: Path) -> None:
    native_head = contract._sha256_digest(b"native-authority")
    case = make_qualification_case(
        tmp_path,
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(native_head,),
    )
    result = _qualify(case)
    proof = _verified_result(result)
    assert proof.commitment_head != native_head
    assert (
        result.reconciliation.owner_context.owner_qualified_candidate.candidate.native_authority_head_refs
        == (native_head,)
    )


def test_common_verifier_never_inspects_native_policy_fields() -> None:
    assert set(inspect.signature(FullPrefixVerifier.verify_bundle).parameters) == {
        "self",
        "bundle_bytes",
        "expected_domain",
        "expected_prefix",
        "expected_bundle_content_hash",
    }
    forbidden = {"policy", "admission", "predicate", "authority_head", "accepted"}
    assert forbidden.isdisjoint(contract.FullPrefixVerified.model_fields)


@pytest.mark.parametrize("shape", ["epoch", "inventory"])
def test_both_native_adapters_share_the_real_verifier_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shape: str,
) -> None:
    case = make_qualification_case(tmp_path / shape, shape=shape, member_count=1)
    real_builder = chronology_qualification.build_full_prefix_bundle

    def _corrupt(
        request: contract.ChronologyBundleRequest,
    ) -> contract.FullPrefixBuildResult:
        built = real_builder(request)
        assert isinstance(built, contract.EncodedChronologyBundle)
        return built.model_copy(update={"bundle_bytes": built.bundle_bytes + b"corrupt"})

    monkeypatch.setattr(chronology_qualification, "build_full_prefix_bundle", _corrupt)
    result = _qualify(case)
    assert isinstance(result, contract.NativeFullPrefixProofRejected)
    assert not isinstance(result.proof_result, contract.FullPrefixVerified)


def test_chronology_never_uses_confidence_ledger_scope_or_head() -> None:
    roots = (
        Path(contract.__file__),
        Path(inspect.getfile(FullPrefixVerifier)),
        Path(chronology_qualification.__file__),
    )
    for source_path in roots:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any("confidence_ledger" in module for module in imported_modules)
    assert {"confidence_scope", "confidence_head"}.isdisjoint(
        contract.ChronologyBundleHeader.model_fields
    )


def test_fixed_full_prefix_profile_behaviors_and_caps() -> None:
    assert contract.FULL_PREFIX_MAX_MEMBERS == 2_500_000
    assert contract.FULL_PREFIX_MAX_BUNDLE_BYTES == 4 * 1024 * 1024 * 1024
    assert contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES == 1_024
    crossings = (
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
    )
    domain = contract.ChronologyProofDomain(
        format=contract.FULL_PREFIX_FORMAT,
        profile=contract.FULL_PREFIX_PROFILE,
        proof_domain="capacity",
        family="capacity",
        scope_ref=contract._sha256_digest(b"capacity-scope"),
        authority_purpose="audit",
    )
    for member_count, header_bytes, member_bytes, native_bytes in crossings:
        failure = contract._profile_capacity_failure(
            domain=domain,
            member_count=member_count,
            header_frame_bytes=header_bytes,
            member_frame_bytes=member_bytes,
            native_frame_bytes=native_bytes,
        )
        assert failure is not None
        assert failure.failure_code.value == "proof_profile_capacity_exceeded"


def test_unknown_profile_and_cross_domain_replay_reject(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)
    built = _build(case)
    records = contract._split_framed_records(built.bundle_bytes)
    header = json.loads(records[0])
    header["profile"] = "unknown-profile"
    attacked = contract._frame_record(contract._canonical_raw_bytes(header)) + b"".join(
        contract._frame_record(record) for record in records[1:]
    )
    result = FullPrefixVerifier().verify_bundle(
        attacked,
        expected_domain=case.query.domain,
    )
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)


def test_authority_only_and_annotation_only_heads_move_orthogonally(
    tmp_path: Path,
) -> None:
    optional = make_qualification_case(
        tmp_path / "optional",
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(),
    )
    required = make_qualification_case(
        tmp_path / "required",
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(),
        required_native_head_role="current_epoch",
    )
    annotation = make_qualification_case(
        tmp_path / "annotation",
        shape="epoch",
        member_count=1,
        native_authority_head_refs=(),
        annotation_revision=1,
    )
    optional_result = _qualify(optional)
    required_result = _qualify(required)
    annotation_result = _qualify(annotation)
    optional_proof = _verified_result(optional_result)
    required_proof = _verified_result(required_result)
    annotation_proof = _verified_result(annotation_result)
    assert optional_proof.commitment_head == required_proof.commitment_head
    assert optional_proof.commitment_head != annotation_proof.commitment_head
    assert (
        optional.candidate.native_authority_head_refs
        == annotation.candidate.native_authority_head_refs
    )


def test_inventory_without_native_head_uses_empty_head_tuple(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)
    result = _qualify(case)
    assert isinstance(result, contract.NativeProjectionCustodyGap)
    assert case.candidate.native_authority_head_refs == ()


def test_predicate_class_comes_from_owner_verifier_receipt(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)
    result = _qualify(case)
    assert isinstance(result, contract.NativeProjectionCustodyGap)
    receipt = (
        result.reconciliation.owner_context.owner_qualified_candidate.owner_relation_verification
    )
    assert {row.predicate_class for row in receipt.predicate_evidence} == {
        "independently_reconciled"
    }


@pytest.mark.parametrize(
    "predicate_class",
    ["consumer_asserted", "institutionally_supplied", "not_established"],
)
def test_non_authority_predicate_classes_fail_qualification(
    tmp_path: Path,
    predicate_class: contract.PredicateClass,
) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
        predicate_class=predicate_class,
    )
    result = _qualify(case)
    assert isinstance(result, contract.NativePredicateRejected)


def test_remove_content_check_keep_markers_fails(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)
    built = _build(case)
    records = contract._split_framed_records(built.bundle_bytes)
    attacked_native = records[2] + b"changed"
    attacked = b"".join(
        contract._frame_record(record) for record in (records[0], records[1], attacked_native)
    )
    result = FullPrefixVerifier().verify_bundle(
        attacked,
        expected_domain=case.query.domain,
    )
    assert isinstance(result, contract.FullPrefixMemberRejected)


@pytest.mark.parametrize("failure_mode", ["novel_member", "missing_relation"])
def test_novel_member_unknown_relation_or_provenance_fails(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
        include_novel_candidate_member=failure_mode == "novel_member",
        missing_owner_relation=failure_mode == "missing_relation",
    )
    result = _qualify(case)
    assert isinstance(result, contract.NativeChronologyPolicyResolutionFailed)
    expected_code = (
        "native_denominator_mismatch" if failure_mode == "novel_member" else "policy_bytes_missing"
    )
    assert result.failure.code == expected_code


def test_sibling_consumer_cannot_bypass_verifier_or_lift_limitation(
    tmp_path: Path,
) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
        exterior_limitation_code="owner_exterior_unknown",
    )
    case.appoint_consumer()
    first = chronology_qualification.QualificationConsumer.from_current_owner_container()
    second = chronology_qualification.QualificationConsumer.from_current_owner_container()
    first_result = first.qualify(adapter=case.adapter, request=case.query)
    second_result = second.qualify(adapter=case.adapter, request=case.query)
    assert isinstance(first_result, contract.NativeExteriorNotEstablished)
    assert isinstance(second_result, contract.NativeExteriorNotEstablished)
    assert case.owner_verifier.calls == 2


def test_owner_policy_change_moves_authority_not_proof(tmp_path: Path) -> None:
    _assert_owner_policy_changes_authority_not_proof(tmp_path)


def test_remove_predecessor_check_keep_markers_fails(tmp_path: Path) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=2)
    built = _build(case)
    records = contract._split_framed_records(built.bundle_bytes)
    first_frame = json.loads(records[1])
    second_frame = json.loads(records[3])
    second_frame["predecessor_commitment"] = first_frame["predecessor_commitment"]
    attacked = b"".join(
        contract._frame_record(record)
        for record in (
            records[0],
            records[1],
            records[2],
            contract._canonical_raw_bytes(second_frame),
            records[4],
        )
    )
    result = FullPrefixVerifier().verify_bundle(
        attacked,
        expected_domain=case.query.domain,
    )
    assert isinstance(result, contract.FullPrefixMemberRejected)


def test_valid_prefix_denominator_omission_fails(tmp_path: Path) -> None:
    _assert_valid_prefix_omission_fails_owner_denominator(tmp_path)


def test_valid_shaped_unknown_profile_has_no_fallback(tmp_path: Path) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=0,
        policy_profile="fixture.inventory.strict@1",
        candidate_profile="fixture.inventory.lax@1",
    )
    result = _qualify(case)
    assert isinstance(result, contract.NativeChronologyPolicyResolutionFailed)
    assert result.failure.code == "native_denominator_mismatch"


def test_cross_family_scope_domain_replay_fails(tmp_path: Path) -> None:
    epoch = make_qualification_case(tmp_path / "epoch", shape="epoch", member_count=1)
    inventory = make_qualification_case(tmp_path / "inventory", shape="inventory", member_count=1)
    built = _build(epoch)
    result = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=inventory.query.domain,
    )
    assert isinstance(result, contract.FullPrefixEnvelopeRejected)
    assert result.failure_codes == (contract.FullPrefixEnvelopeFailureCode.PROOF_DOMAIN_MISMATCH,)
