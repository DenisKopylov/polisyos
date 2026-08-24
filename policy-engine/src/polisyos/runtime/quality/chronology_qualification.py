"""Owner-qualified composition over the policy-free full-prefix protocol.

This module is production-internal.  It resolves family-owner policy and
provenance from the one process owner container, then drives the common builder
and verifier.  It does not create a family producer, accept an anchor, or
promote the common commitment head into a native authority head.
"""

from __future__ import annotations

import os
from typing import NoReturn, Protocol, SupportsIndex

from polisyos.core import build_full_prefix_bundle
from polisyos.core import contracts as core_contracts
from polisyos.runtime.quality import chronology_proof

contract = core_contracts.chronology


class NativeChronologyAuthorityAdapter(Protocol):
    """Return one family-native candidate without selecting common policy."""

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate: ...


def _selection_key(
    request: contract.NativeChronologyQuery,
) -> contract.PredicatePolicySelectionKey:
    return contract.PredicatePolicySelectionKey(
        family=request.domain.family,
        proof_domain=request.domain.proof_domain,
        scope_ref=request.domain.scope_ref,
        authority_purpose=request.domain.authority_purpose,
        requested_cutoff_ref=request.requested_cutoff_ref,
    )


def _entry_generation_failure(
    request: contract.NativeChronologyQuery,
) -> contract.NativeQualificationProcessGenerationNotEstablished:
    return contract.NativeQualificationProcessGenerationNotEstablished(
        result_kind="qualification_process_generation_not_established",
        status="not_established",
        code="qualification_process_generation_not_established",
        query=request,
    )


def _policy_failure(
    *,
    request: contract.NativeChronologyQuery,
    failure: (
        contract.PredicatePolicyResolutionFailure | contract.PredicatePolicyOwnerRelationFailure
    ),
) -> contract.NativeChronologyPolicyResolutionFailed:
    return contract.NativeChronologyPolicyResolutionFailed(
        result_kind="policy_resolution_failed",
        query=request,
        failure=failure,
    )


def _owner_relation_not_established(
    *,
    request: contract.NativeChronologyQuery,
    key: contract.PredicatePolicySelectionKey,
    owner_relation_ref: contract.ArtifactRef | None,
) -> contract.NativeChronologyPolicyResolutionFailed:
    return _policy_failure(
        request=request,
        failure=contract.PolicyOwnerRelationNotEstablished(
            code="policy_owner_relation_not_established",
            status="not_established",
            key=key,
            requested_query_context_ref=request.requested_query_context_ref,
            owner_relation_ref=owner_relation_ref,
        ),
    )


def _policy_binding_mismatch(
    *,
    request: contract.NativeChronologyQuery,
    key: contract.PredicatePolicySelectionKey,
    evidence_ref: contract.ArtifactRef,
) -> contract.NativeChronologyPolicyResolutionFailed:
    return _policy_failure(
        request=request,
        failure=contract.PolicyBindingMismatchFailure(
            code="policy_binding_mismatch",
            status="rejected",
            key=key,
            requested_query_context_ref=request.requested_query_context_ref,
            evidence_ref=evidence_ref,
        ),
    )


def _reconcile_predicates(
    *,
    candidate: contract.NativeChronologyCandidate,
    receipt: contract.VerifiedPredicatePolicyOwnerRelation,
    policy: contract.PredicateAdmissionPolicyStatement,
    denominator: contract.ApplicablePredicateDenominatorStatement,
) -> tuple[contract.ArtifactRef, ...] | None:
    member_rules = tuple(rule for rule in policy.rules if rule.subject_kind == "member")
    query_rules = tuple(rule for rule in policy.rules if rule.subject_kind == "query")
    expected_keys = tuple(
        ("member", member_ref, rule.predicate_id)
        for member_ref in denominator.member_subject_refs
        for rule in member_rules
    ) + tuple(
        ("query", candidate.query.requested_query_context_ref, rule.predicate_id)
        for rule in query_rules
    )
    candidate_rows = {
        ("member", row.member_ref, row.disposition.predicate_id): row.disposition
        for row in candidate.member_predicates
    } | {
        (
            "query",
            row.requested_query_context_ref,
            row.disposition.predicate_id,
        ): row.disposition
        for row in candidate.query_predicates
    }
    receipt_rows = {
        (row.subject_kind, row.subject_ref, row.predicate_id): row
        for row in receipt.predicate_evidence
    }
    if (
        len(candidate_rows) != len(expected_keys)
        or len(receipt_rows) != len(expected_keys)
        or set(candidate_rows) != set(expected_keys)
        or set(receipt_rows) != set(expected_keys)
        or denominator.required_member_predicate_pairs
        != tuple(
            (subject_ref, predicate_id)
            for kind, subject_ref, predicate_id in expected_keys
            if kind == "member"
        )
        or denominator.required_query_predicate_ids
        != tuple(predicate_id for kind, _, predicate_id in expected_keys if kind == "query")
    ):
        return None

    rules = {(rule.subject_kind, rule.predicate_id): rule for rule in policy.rules}
    evidence_refs: list[contract.ArtifactRef] = []
    for key in expected_keys:
        kind, _, predicate_id = key
        disposition = candidate_rows[key]
        evidence = receipt_rows[key]
        rule = rules[(kind, predicate_id)]
        if (
            disposition.status != "satisfied"
            or evidence.status != "satisfied"
            or disposition.predicate_class not in rule.admitted_classes
            or evidence.predicate_class not in rule.admitted_classes
            or disposition.predicate_class != evidence.predicate_class
            or disposition.evidence_ref is None
            or evidence.evidence_ref is None
            or evidence.evidence_content_hash is None
            or evidence.evidence_verifier_provenance_ref is None
            or disposition.evidence_ref != evidence.evidence_ref
        ):
            return None
        evidence_refs.append(evidence.evidence_ref)
    return tuple(evidence_refs)


class QualificationConsumer:
    """Resolve owner policy and qualify one candidate through the real verifier."""

    __slots__ = ("_creator_pid", "_generation", "_owner")

    def __init__(self) -> None:
        raise TypeError("use QualificationConsumer.from_current_owner_container()")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("qualification consumers cannot be serialized")

    @classmethod
    def from_current_owner_container(cls) -> QualificationConsumer:
        """Bind the current private owner generation without caller injection."""
        registry = chronology_proof._PERSISTENCE_REGISTRY
        owner = registry._resolve_current_owner()
        consumer = object.__new__(cls)
        consumer._owner = owner
        consumer._generation = registry._generation
        consumer._creator_pid = os.getpid()
        return consumer

    def qualify(
        self,
        *,
        adapter: NativeChronologyAuthorityAdapter,
        request: contract.NativeChronologyQuery,
    ) -> contract.NativeChronologyQualificationResult:
        """Qualify one native candidate without taking family authority."""
        registry = chronology_proof._PERSISTENCE_REGISTRY
        owner = self._owner
        if (
            owner is None
            or self._creator_pid != os.getpid()
            or self._generation is not registry._generation
            or not registry._owner_is_current(owner)
        ):
            return _entry_generation_failure(request)

        key = _selection_key(request)
        context = contract.PredicatePolicyResolutionContext(query=request, key=key)
        try:
            admission_refs = owner._admission_index.enumerate_admission_refs(key=key)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _owner_relation_not_established(
                request=request,
                key=key,
                owner_relation_ref=None,
            )
        if not admission_refs:
            return _policy_failure(
                request=request,
                failure=contract.PolicyAdmissionMissingFailure(
                    code="policy_admission_missing",
                    status="not_established",
                    key=key,
                    requested_query_context_ref=request.requested_query_context_ref,
                ),
            )
        if len(admission_refs) != 1:
            return _policy_failure(
                request=request,
                failure=contract.PolicyAdmissionAmbiguousFailure(
                    code="policy_admission_ambiguous",
                    status="not_established",
                    key=key,
                    requested_query_context_ref=request.requested_query_context_ref,
                ),
            )

        artifacts = contract.ChronologyPredicatePolicyArtifacts(store=owner._store)
        admission = artifacts.load_admission(
            context=context,
            admission_ref=admission_refs[0],
        )
        if not isinstance(admission, contract.PersistedPredicatePolicyAdmission):
            return _policy_failure(request=request, failure=admission)
        policy = artifacts.load_policy(
            context=context,
            policy_ref=admission.statement.policy_ref,
            expected_content_hash=admission.statement.policy_content_hash,
        )
        if not isinstance(policy, contract.PersistedPredicateAdmissionPolicy):
            return _policy_failure(request=request, failure=policy)
        if (
            policy.statement.key != key
            or policy.statement.native_schema_profile != admission.statement.native_schema_profile
            or policy.policy_ref != admission.statement.policy_ref
            or policy.policy_content_hash != admission.statement.policy_content_hash
        ):
            return _policy_binding_mismatch(
                request=request,
                key=key,
                evidence_ref=policy.policy_ref,
            )
        provenance_bytes = artifacts.load_policy_owner_provenance_bytes(
            context=context,
            provenance_ref=policy.statement.owner_provenance_ref,
            expected_content_hash=policy.statement.owner_provenance_content_hash,
        )
        if not isinstance(provenance_bytes, bytes):
            return _policy_failure(request=request, failure=provenance_bytes)
        relation_bytes = artifacts.load_owner_relation_bytes(
            context=context,
            relation_ref=admission.statement.owner_relation_ref,
            expected_content_hash=admission.statement.owner_relation_content_hash,
        )
        if not isinstance(relation_bytes, bytes):
            return _policy_failure(request=request, failure=relation_bytes)

        try:
            candidate = adapter.reconcile_candidate(request)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _owner_relation_not_established(
                request=request,
                key=key,
                owner_relation_ref=admission.statement.owner_relation_ref,
            )
        if not isinstance(candidate, contract.NativeChronologyCandidate):
            return _owner_relation_not_established(
                request=request,
                key=key,
                owner_relation_ref=admission.statement.owner_relation_ref,
            )
        owner_receipt = owner._owner_provenance_verifier.verify_owner_relation(
            query=request,
            admission=admission.statement,
            policy=policy,
            policy_owner_provenance_bytes=provenance_bytes,
            owner_relation_bytes=relation_bytes,
            candidate=candidate,
        )
        if not isinstance(owner_receipt, contract.VerifiedPredicatePolicyOwnerRelation):
            return _policy_failure(request=request, failure=owner_receipt)
        try:
            qualified_candidate = contract.OwnerQualifiedNativeCandidate(
                candidate=candidate,
                candidate_content_hash=contract._native_candidate_content_hash(candidate),
                owner_relation_verification=owner_receipt,
            )
        except ValueError:
            return _policy_failure(
                request=request,
                failure=contract.PolicyOwnerRelationRejected(
                    code="policy_owner_relation_rejected",
                    status="rejected",
                    key=key,
                    requested_query_context_ref=request.requested_query_context_ref,
                    owner_relation_ref=admission.statement.owner_relation_ref,
                    evidence_ref=owner_receipt.verification_receipt_ref,
                ),
            )
        owner_context = contract.NativeChronologyOwnerContext(
            query=request,
            owner_qualified_candidate=qualified_candidate,
            policy_admission_ref=admission.admission_ref,
            policy_admission_content_hash=admission.admission_content_hash,
            predicate_admission_policy_ref=policy.policy_ref,
            predicate_admission_policy_content_hash=policy.policy_content_hash,
        )
        observed_profiles = tuple(
            member.native_schema_profile for member in candidate.ordered_members
        )
        if any(
            observed != policy.statement.native_schema_profile for observed in observed_profiles
        ):
            return contract.NativeSchemaProfileRejected(
                result_kind="profile_rejected",
                code="native_schema_profile_mismatch",
                owner_context=owner_context,
                expected_profile=policy.statement.native_schema_profile,
                observed_profiles=observed_profiles,
            )

        member_rules = tuple(
            rule for rule in policy.statement.rules if rule.subject_kind == "member"
        )
        query_rules = tuple(rule for rule in policy.statement.rules if rule.subject_kind == "query")
        denominator_statement = contract.ApplicablePredicateDenominatorStatement(
            schema_version=("polisyos.chronology.applicable-predicate-denominator.v1"),
            policy_ref=policy.policy_ref,
            policy_content_hash=policy.policy_content_hash,
            member_subject_refs=tuple(member.member_ref for member in candidate.ordered_members),
            required_member_predicate_pairs=tuple(
                (member.member_ref, rule.predicate_id)
                for member in candidate.ordered_members
                for rule in member_rules
            ),
            required_query_predicate_ids=tuple(rule.predicate_id for rule in query_rules),
        )
        denominator = contract.ChronologyApplicablePredicateDenominatorArtifacts(
            store=owner._store
        ).persist_and_verify(
            query=request,
            statement=denominator_statement,
            owner_qualified_candidate=qualified_candidate,
        )
        if not isinstance(denominator, contract.PersistedApplicablePredicateDenominator):
            return contract.NativeApplicablePredicateDenominatorPersistenceFailed(
                result_kind="predicate_denominator_persistence_failed",
                owner_context=owner_context,
                failure=denominator,
            )
        evidence_refs = _reconcile_predicates(
            candidate=candidate,
            receipt=owner_receipt,
            policy=policy.statement,
            denominator=denominator.statement,
        )
        if evidence_refs is None:
            available_refs = tuple(
                row.evidence_ref
                for row in owner_receipt.predicate_evidence
                if row.evidence_ref is not None
            )
            return contract.NativePredicateRejected(
                result_kind="predicate_rejected",
                code="native_predicate_inadmissible",
                owner_context=owner_context,
                evidence_refs=available_refs,
            )

        reconciliation = contract.NativeChronologyReconciliation(
            owner_context=owner_context,
            authoritative_native_schema_profile=policy.statement.native_schema_profile,
            applicable_predicate_denominator=denominator,
        )
        build_result = build_full_prefix_bundle(
            contract.ChronologyBundleRequest(
                domain=request.domain,
                native_schema_profile=policy.statement.native_schema_profile,
                declared_denominator_ref=candidate.declared_denominator_ref,
                requested_cutoff_ref=request.requested_cutoff_ref,
                requested_query_context_ref=request.requested_query_context_ref,
                members=candidate.ordered_members,
            )
        )
        if isinstance(build_result, contract.FullPrefixBuildRejected):
            return contract.NativeFullPrefixBuildRejected(
                result_kind="build_rejected",
                reconciliation=reconciliation,
                build_result=build_result,
            )
        proof_result = owner._verifier.verify_bundle(
            build_result.bundle_bytes,
            expected_domain=request.domain,
            expected_prefix=None,
            expected_bundle_content_hash=build_result.bundle_content_hash,
        )
        if not isinstance(proof_result, contract.FullPrefixVerified):
            return contract.NativeFullPrefixProofRejected(
                result_kind="proof_rejected",
                code="full_prefix_proof_rejected",
                reconciliation=reconciliation,
                proof_result=proof_result,
            )

        exterior = candidate.exterior_limitation_code
        required_head_role = policy.statement.required_native_head_role
        head_missing = required_head_role is not None and not candidate.native_authority_head_refs
        if exterior is not None and head_missing:
            return contract.NativeExteriorAndAuthorityHeadNotEstablished(
                result_kind="native_exterior_and_authority_head_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code=exterior,
                required_native_head_role=required_head_role,
                proof_result=proof_result,
            )
        if exterior is not None:
            return contract.NativeExteriorNotEstablished(
                result_kind="native_exterior_not_established",
                code="native_exterior_not_established",
                reconciliation=reconciliation,
                exterior_limitation_code=exterior,
                proof_result=proof_result,
            )
        if head_missing:
            return contract.NativeAuthorityHeadNotEstablished(
                result_kind="native_authority_head_not_established",
                code="native_authority_head_not_established",
                reconciliation=reconciliation,
                required_native_head_role=required_head_role,
                proof_result=proof_result,
            )

        # Cluster 2 intentionally has no family-projection receipt producer or
        # production family call site.  The common consumer therefore ends at
        # the exact family-owned custody gap; C4 owns the first positive path.
        return contract.NativeProjectionCustodyGap(
            result_kind="projection_custody_gap",
            status="native_not_established",
            code="native_projection_custody_gap",
            reconciliation=reconciliation,
            proof_result=proof_result,
            missing_projection_receipt_role="native_projection_receipt",
        )


__all__ = ["NativeChronologyAuthorityAdapter", "QualificationConsumer"]
