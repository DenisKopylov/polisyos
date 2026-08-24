from __future__ import annotations

import hashlib
import inspect
from typing import Any

import pytest

from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import (
    FullPrefixVerifier,
    build_full_prefix_bundle,
)
from polisyos.runtime.quality import chronology_proof, chronology_qualification
from tests._helpers.chronology_qualification import make_qualification_case


def _digest(label: str) -> contract.Digest:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _query() -> contract.NativeChronologyQuery:
    return contract.NativeChronologyQuery(
        domain=contract.ChronologyProofDomain(
            format=contract.FULL_PREFIX_FORMAT,
            profile=contract.FULL_PREFIX_PROFILE,
            proof_domain="qualification-unit",
            family="unit-native",
            scope_ref=_digest("scope"),
            authority_purpose="publication",
        ),
        requested_cutoff_ref=_digest("cutoff"),
        requested_query_context_ref=_digest("query-context"),
    )


class _ExplodingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        del request
        self.calls += 1
        raise AssertionError("adapter must not run under an absent owner generation")


@pytest.fixture(autouse=True)
def _clear_owner_appointment() -> Any:
    registry = chronology_proof._PERSISTENCE_REGISTRY
    registry._clear_for_test()
    yield
    registry._clear_for_test()


def test_qualification_module_exposes_only_the_two_internal_composition_symbols() -> None:
    assert chronology_qualification.__all__ == [
        "NativeChronologyAuthorityAdapter",
        "QualificationConsumer",
    ]
    assert set(
        inspect.signature(
            chronology_qualification.NativeChronologyAuthorityAdapter.reconcile_candidate
        ).parameters
    ) == {"self", "request"}
    assert set(
        inspect.signature(chronology_qualification.QualificationConsumer.qualify).parameters
    ) == {"self", "adapter", "request"}
    assert (
        set(
            inspect.signature(
                chronology_qualification.QualificationConsumer.from_current_owner_container
            ).parameters
        )
        == set()
    )
    with pytest.raises(TypeError, match="from_current_owner_container"):
        chronology_qualification.QualificationConsumer()


def test_absent_owner_generation_refuses_before_adapter_or_store_access() -> None:
    adapter = _ExplodingAdapter()
    query = _query()
    consumer = chronology_qualification.QualificationConsumer.from_current_owner_container()

    result = consumer.qualify(adapter=adapter, request=query)

    assert isinstance(result, contract.NativeQualificationProcessGenerationNotEstablished)
    assert result.result_kind == "qualification_process_generation_not_established"
    assert result.query == query
    assert adapter.calls == 0


def test_candidate_copy_cannot_become_owner_truth(tmp_path: Any) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=2,
        candidate_member_ordinals=(0,),
    )

    candidate = case.candidate
    built = build_full_prefix_bundle(
        contract.ChronologyBundleRequest(
            domain=case.query.domain,
            native_schema_profile=candidate.ordered_members[0].native_schema_profile,
            declared_denominator_ref=candidate.declared_denominator_ref,
            requested_cutoff_ref=case.query.requested_cutoff_ref,
            requested_query_context_ref=case.query.requested_query_context_ref,
            members=candidate.ordered_members,
        )
    )
    assert isinstance(built, contract.EncodedChronologyBundle)
    verified_prefix = FullPrefixVerifier().verify_bundle(
        built.bundle_bytes,
        expected_domain=case.query.domain,
        expected_bundle_content_hash=built.bundle_content_hash,
    )
    assert isinstance(verified_prefix, contract.FullPrefixVerified)

    result = case.appoint_consumer().qualify(
        adapter=case.adapter,
        request=case.query,
    )

    assert isinstance(result, contract.NativeChronologyPolicyResolutionFailed)
    assert result.failure.code == "native_denominator_mismatch"
    assert result.failure.expected_denominator_ref == case.owner_denominator_ref
    assert result.failure.observed_denominator_ref == case.candidate.declared_denominator_ref


def test_zero_member_profile_is_visible_through_owner_denominator(tmp_path: Any) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=0,
        policy_profile="fixture.inventory.strict@1",
        candidate_profile="fixture.inventory.lax@1",
    )

    result = case.appoint_consumer().qualify(
        adapter=case.adapter,
        request=case.query,
    )

    assert isinstance(result, contract.NativeChronologyPolicyResolutionFailed)
    assert result.failure.code == "native_denominator_mismatch"


def test_predicate_reconciliation_is_a_bijection_not_tuple_order(tmp_path: Any) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=2,
    )
    case.adapter.candidate = case.candidate.model_copy(
        update={"member_predicates": tuple(reversed(case.candidate.member_predicates))}
    )

    result = case.appoint_consumer().qualify(
        adapter=case.adapter,
        request=case.query,
    )

    assert isinstance(result, contract.NativeProjectionCustodyGap)


class _ReceiptWithoutPredicateEvidence:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def verify_owner_relation(self, **kwargs: Any) -> Any:
        receipt = self._delegate.verify_owner_relation(**kwargs)
        assert isinstance(receipt, contract.VerifiedPredicatePolicyOwnerRelation)
        return receipt.model_copy(update={"predicate_evidence": ()})


def test_predicate_rejection_uses_only_owner_held_evidence(tmp_path: Any) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
    )
    registry = chronology_proof._PERSISTENCE_REGISTRY
    registry._appoint_for_test(
        store_factory=lambda: case.store,
        verifier_factory=FullPrefixVerifier,
        admission_index_factory=lambda: case.admission_index,
        owner_provenance_verifier_factory=lambda: _ReceiptWithoutPredicateEvidence(
            case.owner_verifier
        ),
    )
    consumer = chronology_qualification.QualificationConsumer.from_current_owner_container()

    result = consumer.qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativePredicateRejected)
    assert result.evidence_refs == ()
