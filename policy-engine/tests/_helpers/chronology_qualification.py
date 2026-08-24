"""Test-only native authority shapes for chronology protocol conformance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
)
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import FullPrefixVerifier
from polisyos.runtime.quality import chronology_proof, chronology_qualification


def _digest(label: str) -> contract.Digest:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _put_raw(store: FileSystemCAS, payload: bytes, *, kind: str) -> ArtifactRef:
    return store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/octet-stream",
        ),
    )


def _put_statement(
    store: FileSystemCAS,
    statement: object,
    *,
    kind: str,
) -> ArtifactRef:
    raw_mapping = contract._raw_model_mapping(statement)
    payload = contract._frame_record(contract._canonical_raw_bytes(raw_mapping))
    return _put_raw(store, payload, kind=kind)


def _native_bytes(
    *,
    shape: Literal["epoch", "inventory"],
    ordinal: int,
    annotation_revision: int,
) -> bytes:
    if shape == "epoch":
        mapping: dict[str, object] = {
            "schema": "fixture.epoch-like-native.v1",
            "epoch_ref": f"semantic-version-{ordinal}",
            "valid_effect": [ordinal, ordinal + 1],
            "visibility_knowledge": [ordinal + 10, ordinal + 11],
            "branch": "a" if ordinal % 2 == 0 else "b",
            "annotation_revision": annotation_revision,
            "status": "historical" if ordinal == 0 else "current",
        }
    else:
        mapping = {
            "schema": "fixture.opaque-inventory.v1",
            "inventory_record_id": f"record-{ordinal}",
            "opaque_value": f"value-{ordinal}",
            "annotation_revision": annotation_revision,
            "terminal": ordinal > 0,
            "historical": ordinal == 0,
        }
    return contract._canonical_raw_bytes(mapping)


class _FixtureBytesModel(BaseModel):
    """Strict immutable schema for independently persisted fixture authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _OwnerEvidenceStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-evidence.v1"]
    subject_kind: Literal["member", "query"]
    subject_ref: contract.Digest
    predicate_id: str
    predicate_class: contract.PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    failure_code: str | None


class _NativeDenominatorMember(_FixtureBytesModel):
    member_ref: contract.Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: contract.Digest
    native_schema_profile: str
    member_admission_basis_ref: contract.Digest
    member_admission_context_ref: contract.Digest
    predicate_evidence_refs: tuple[ArtifactRef, ...]


class _NativeDenominatorStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.native-denominator.v1"]
    family: str
    native_schema_profile: str
    native_authority_head_refs: tuple[contract.Digest, ...]
    members: tuple[_NativeDenominatorMember, ...]


class _OwnerQueryContextStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-query-context.v1"]
    query: contract.NativeChronologyQuery
    exterior_limitation_code: str | None
    predicate_evidence_refs: tuple[ArtifactRef, ...]


class _OwnerRelationStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-relation.v1"]
    key: contract.PredicatePolicySelectionKey
    policy_ref: ArtifactRef
    native_denominator_artifact_ref: ArtifactRef
    query_context_artifact_ref: ArtifactRef


@dataclass(frozen=True, slots=True)
class _OwnerTruth:
    query: contract.NativeChronologyQuery
    native_schema_profile: str
    denominator_ref: contract.Digest
    denominator_artifact_ref: ArtifactRef
    denominator_content_hash: contract.Digest
    query_context_artifact_ref: ArtifactRef
    query_context_content_hash: contract.Digest
    member_identities: tuple[contract.VerifiedNativeMemberIdentity, ...]
    predicate_statements: tuple[_OwnerEvidenceStatement, ...]
    predicate_evidence: tuple[contract.VerifiedOwnerPredicateEvidence, ...]
    exterior_limitation_code: str | None
    native_authority_head_refs: tuple[contract.Digest, ...]


_DENOMINATOR_PREFIX = b"fixture.native-denominator.v1\0"
_QUERY_CONTEXT_PREFIX = b"fixture.query-context.v1\0"


def _model_bytes(model: BaseModel) -> bytes:
    return contract._canonical_raw_bytes(contract._raw_model_mapping(model))


def _load_typed_bytes(
    store: FileSystemCAS,
    ref: ArtifactRef,
    model: type[_FixtureBytesModel],
) -> tuple[_FixtureBytesModel, bytes]:
    report = store.verify(ref.artifact_id)
    payload = store.get_bytes(ref.artifact_id)
    if not report.ok or str(ref.artifact_id) != contract._sha256_digest(payload):
        raise ValueError("fixture authority bytes fail CAS verification")
    raw: Any = json.loads(payload)
    if not isinstance(raw, dict) or contract._canonical_raw_bytes(raw) != payload:
        raise ValueError("fixture authority bytes are not canonical")
    return model.model_validate(raw), payload


@dataclass(slots=True)
class EpochLikeQualificationAdapter:
    """Test-only epoch-like shape with sparse bitemporal and branch roles."""

    candidate: contract.NativeChronologyCandidate
    epoch_ref: str = "semantic-version-current"
    valid_effect_roles: tuple[str, str] = ("valid", "effect")
    visibility_knowledge_roles: tuple[str, str] = ("visibility", "knowledge")
    incomparable_native_branches: tuple[str, str] = ("a", "b")
    calls: int = 0

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        self.calls += 1
        if request != self.candidate.query:
            return self.candidate.model_copy(update={"query": request})
        return self.candidate


@dataclass(slots=True)
class OpaqueInventoryQualificationAdapter:
    """Test-only non-epoch shape with no native clock, fork or authority head."""

    candidate: contract.NativeChronologyCandidate
    calls: int = 0

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        self.calls += 1
        if request != self.candidate.query:
            return self.candidate.model_copy(update={"query": request})
        return self.candidate


@dataclass(slots=True)
class _SingleAdmissionIndex:
    key: contract.PredicatePolicySelectionKey
    refs: tuple[ArtifactRef, ...]
    calls: list[contract.PredicatePolicySelectionKey] = field(default_factory=list)

    def enumerate_admission_refs(
        self, *, key: contract.PredicatePolicySelectionKey
    ) -> tuple[ArtifactRef, ...]:
        self.calls.append(key)
        if key != self.key:
            return ()
        return self.refs


@dataclass(frozen=True, slots=True)
class _FixtureOwnerVerifier:
    store: FileSystemCAS
    key: contract.PredicatePolicySelectionKey
    policy: contract.PersistedPredicateAdmissionPolicy
    policy_owner_provenance_bytes: bytes
    owner_relation_bytes: bytes
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: contract.Digest
    owner_receipt_ref: ArtifactRef
    owner_verifier_ref: ArtifactRef
    policy_owner_provenance_ref: ArtifactRef
    trust_snapshot_ref: ArtifactRef
    policy_owner_receipt_ref: ArtifactRef
    evidence_verifier_ref: ArtifactRef
    failure_evidence_ref: ArtifactRef
    _calls: list[None] = field(default_factory=list)

    @property
    def calls(self) -> int:
        return len(self._calls)

    def _rejected(
        self, query: contract.NativeChronologyQuery
    ) -> contract.PolicyOwnerRelationRejected:
        return contract.PolicyOwnerRelationRejected(
            code="policy_owner_relation_rejected",
            status="rejected",
            key=self.key,
            requested_query_context_ref=query.requested_query_context_ref,
            owner_relation_ref=self.owner_relation_ref,
            evidence_ref=self.failure_evidence_ref,
        )

    def _stored_exact(self, ref: ArtifactRef, expected: bytes) -> bool:
        try:
            report = self.store.verify(ref.artifact_id)
            payload = self.store.get_bytes(ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False
        return (
            report.ok
            and payload == expected
            and str(ref.artifact_id) == (f"sha256:{hashlib.sha256(expected).hexdigest()}")
        )

    def _denominator_mismatch(
        self,
        *,
        query: contract.NativeChronologyQuery,
        expected: contract.Digest,
        observed: contract.Digest,
    ) -> contract.PolicyOwnerDenominatorMismatchFailure:
        return contract.PolicyOwnerDenominatorMismatchFailure(
            code="native_denominator_mismatch",
            status="rejected",
            key=self.key,
            requested_query_context_ref=query.requested_query_context_ref,
            expected_denominator_ref=expected,
            observed_denominator_ref=observed,
        )

    def _load_evidence(
        self,
        ref: ArtifactRef,
    ) -> tuple[_OwnerEvidenceStatement, contract.VerifiedOwnerPredicateEvidence]:
        loaded, payload = _load_typed_bytes(
            self.store,
            ref,
            _OwnerEvidenceStatement,
        )
        if not isinstance(loaded, _OwnerEvidenceStatement):
            raise TypeError("owner evidence decoder returned the wrong model")
        verified = contract.VerifiedOwnerPredicateEvidence(
            subject_kind=loaded.subject_kind,
            subject_ref=loaded.subject_ref,
            predicate_id=loaded.predicate_id,
            predicate_class=loaded.predicate_class,
            status=loaded.status,
            evidence_ref=ref,
            evidence_content_hash=contract._sha256_digest(payload),
            evidence_verifier_provenance_ref=self.evidence_verifier_ref,
        )
        return loaded, verified

    def _derive_owner_truth(self) -> _OwnerTruth:
        relation, stored_relation_bytes = _load_typed_bytes(
            self.store,
            self.owner_relation_ref,
            _OwnerRelationStatement,
        )
        if not isinstance(relation, _OwnerRelationStatement):
            raise TypeError("owner relation decoder returned the wrong model")
        if (
            stored_relation_bytes != self.owner_relation_bytes
            or relation.key != self.key
            or relation.policy_ref != self.policy.policy_ref
        ):
            raise ValueError("owner relation is not bound to the appointed policy")

        denominator, denominator_bytes = _load_typed_bytes(
            self.store,
            relation.native_denominator_artifact_ref,
            _NativeDenominatorStatement,
        )
        query_context, query_context_bytes = _load_typed_bytes(
            self.store,
            relation.query_context_artifact_ref,
            _OwnerQueryContextStatement,
        )
        if not isinstance(denominator, _NativeDenominatorStatement) or not isinstance(
            query_context, _OwnerQueryContextStatement
        ):
            raise TypeError("owner truth decoder returned the wrong model")
        if denominator.family != self.key.family:
            raise ValueError("owner denominator names a different family")
        if denominator.native_schema_profile != self.policy.statement.native_schema_profile:
            raise ValueError("owner denominator profile differs from owner policy")

        member_identities: list[contract.VerifiedNativeMemberIdentity] = []
        evidence_statements: list[_OwnerEvidenceStatement] = []
        predicate_evidence: list[contract.VerifiedOwnerPredicateEvidence] = []
        for member in denominator.members:
            report = self.store.verify(member.native_artifact_ref.artifact_id)
            native_bytes = self.store.get_bytes(member.native_artifact_ref.artifact_id)
            if (
                not report.ok
                or str(member.native_artifact_ref.artifact_id)
                != contract._sha256_digest(native_bytes)
                or member.native_content_hash != contract._native_content_hash(native_bytes)
            ):
                raise ValueError("owner member bytes fail independent verification")
            member_identities.append(
                contract.VerifiedNativeMemberIdentity(
                    member_ref=member.member_ref,
                    native_artifact_ref=member.native_artifact_ref,
                    native_content_hash=member.native_content_hash,
                    native_schema_profile=member.native_schema_profile,
                    member_admission_basis_ref=member.member_admission_basis_ref,
                    member_admission_context_ref=member.member_admission_context_ref,
                )
            )
            for evidence_ref in member.predicate_evidence_refs:
                statement, verified = self._load_evidence(evidence_ref)
                if statement.subject_kind != "member" or statement.subject_ref != member.member_ref:
                    raise ValueError("member evidence names the wrong owner subject")
                evidence_statements.append(statement)
                predicate_evidence.append(verified)

        for evidence_ref in query_context.predicate_evidence_refs:
            statement, verified = self._load_evidence(evidence_ref)
            if (
                statement.subject_kind != "query"
                or statement.subject_ref != query_context.query.requested_query_context_ref
            ):
                raise ValueError("query evidence names the wrong owner subject")
            evidence_statements.append(statement)
            predicate_evidence.append(verified)

        return _OwnerTruth(
            query=query_context.query,
            native_schema_profile=denominator.native_schema_profile,
            denominator_ref=contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                denominator_bytes,
            ),
            denominator_artifact_ref=relation.native_denominator_artifact_ref,
            denominator_content_hash=contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                denominator_bytes,
            ),
            query_context_artifact_ref=relation.query_context_artifact_ref,
            query_context_content_hash=contract._sha256_digest(
                _QUERY_CONTEXT_PREFIX,
                query_context_bytes,
            ),
            member_identities=tuple(member_identities),
            predicate_statements=tuple(evidence_statements),
            predicate_evidence=tuple(predicate_evidence),
            exterior_limitation_code=query_context.exterior_limitation_code,
            native_authority_head_refs=denominator.native_authority_head_refs,
        )

    def verify_owner_relation(
        self,
        *,
        query: contract.NativeChronologyQuery,
        admission: contract.PredicatePolicyAdmissionStatement,
        policy: contract.PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: contract.NativeChronologyCandidate,
    ) -> (
        contract.VerifiedPredicatePolicyOwnerRelation | contract.PredicatePolicyOwnerRelationFailure
    ):
        self._calls.append(None)
        if (
            admission.key != self.key
            or policy != self.policy
            or policy_owner_provenance_bytes != self.policy_owner_provenance_bytes
            or owner_relation_bytes != self.owner_relation_bytes
            or not self._stored_exact(
                self.policy_owner_provenance_ref,
                self.policy_owner_provenance_bytes,
            )
            or not self._stored_exact(self.owner_relation_ref, self.owner_relation_bytes)
        ):
            return self._rejected(query)
        try:
            truth = self._derive_owner_truth()
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._rejected(query)

        try:
            _, candidate_denominator_bytes = _load_typed_bytes(
                self.store,
                candidate.native_denominator_artifact_ref,
                _NativeDenominatorStatement,
            )
            candidate_denominator_ref = contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                candidate_denominator_bytes,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._rejected(query)
        if (
            candidate.declared_denominator_ref != candidate_denominator_ref
            or candidate.native_denominator_content_hash != candidate_denominator_ref
        ):
            return self._rejected(query)

        if truth.denominator_ref != candidate_denominator_ref:
            return self._denominator_mismatch(
                query=query,
                expected=truth.denominator_ref,
                observed=candidate_denominator_ref,
            )

        candidate_identities = tuple(
            contract.VerifiedNativeMemberIdentity(
                member_ref=member.member_ref,
                native_artifact_ref=member.native_artifact_ref,
                native_content_hash=member.native_content_hash,
                native_schema_profile=member.native_schema_profile,
                member_admission_basis_ref=member.member_admission_basis_ref,
                member_admission_context_ref=member.member_admission_context_ref,
            )
            for member in candidate.ordered_members
        )
        candidate_predicates = {
            ("member", row.member_ref, row.disposition.predicate_id): (
                row.disposition.predicate_class,
                row.disposition.status,
                row.disposition.failure_code,
                row.disposition.evidence_ref,
            )
            for row in candidate.member_predicates
        } | {
            (
                "query",
                row.requested_query_context_ref,
                row.disposition.predicate_id,
            ): (
                row.disposition.predicate_class,
                row.disposition.status,
                row.disposition.failure_code,
                row.disposition.evidence_ref,
            )
            for row in candidate.query_predicates
        }
        owner_predicates = {
            (statement.subject_kind, statement.subject_ref, statement.predicate_id): (
                statement.predicate_class,
                statement.status,
                statement.failure_code,
                verified.evidence_ref,
            )
            for statement, verified in zip(
                truth.predicate_statements,
                truth.predicate_evidence,
                strict=True,
            )
        }
        if (
            query != truth.query
            or candidate.query != truth.query
            or candidate.native_denominator_artifact_ref != truth.denominator_artifact_ref
            or candidate.native_denominator_content_hash != truth.denominator_content_hash
            or candidate.query_context_artifact_ref != truth.query_context_artifact_ref
            or candidate.query_context_content_hash != truth.query_context_content_hash
            or candidate_identities != truth.member_identities
            or candidate_predicates != owner_predicates
            or candidate.exterior_limitation_code != truth.exterior_limitation_code
            or candidate.native_authority_head_refs != truth.native_authority_head_refs
            or any(
                not self._stored_exact(member.native_artifact_ref, member.native_bytes)
                for member in candidate.ordered_members
            )
        ):
            return self._rejected(query)

        candidate_hash = contract._native_candidate_content_hash(candidate)

        return contract.VerifiedPredicatePolicyOwnerRelation(
            query=query,
            owner_relation_ref=self.owner_relation_ref,
            owner_relation_content_hash=self.owner_relation_content_hash,
            owner_verifier_provenance_ref=self.owner_verifier_ref,
            verification_receipt_ref=self.owner_receipt_ref,
            verification_receipt_content_hash=str(self.owner_receipt_ref.artifact_id),
            candidate_content_hash=candidate_hash,
            owner_declared_denominator_ref=truth.denominator_ref,
            candidate_declared_denominator_ref=candidate.declared_denominator_ref,
            owner_ordered_member_refs=tuple(
                member.member_ref for member in truth.member_identities
            ),
            candidate_ordered_member_refs=tuple(
                member.member_ref for member in candidate.ordered_members
            ),
            denominator_identity=contract.VerifiedNativeSubjectIdentity(
                subject_kind="denominator",
                subject_ref=truth.denominator_ref,
                artifact_ref=truth.denominator_artifact_ref,
                raw_cas_hash=str(truth.denominator_artifact_ref.artifact_id),
                semantic_content_hash=truth.denominator_content_hash,
                verifier_provenance_ref=self.owner_verifier_ref,
            ),
            query_context_identity=contract.VerifiedNativeSubjectIdentity(
                subject_kind="query_context",
                subject_ref=query.requested_query_context_ref,
                artifact_ref=truth.query_context_artifact_ref,
                raw_cas_hash=str(truth.query_context_artifact_ref.artifact_id),
                semantic_content_hash=truth.query_context_content_hash,
                verifier_provenance_ref=self.owner_verifier_ref,
            ),
            member_identities=truth.member_identities,
            predicate_evidence=truth.predicate_evidence,
            policy_owner_provenance=contract.VerifiedPolicyOwnerProvenance(
                policy_ref=policy.policy_ref,
                policy_content_hash=policy.policy_content_hash,
                owner_provenance_ref=self.policy_owner_provenance_ref,
                owner_provenance_content_hash=contract._sha256_digest(
                    self.policy_owner_provenance_bytes
                ),
                trust_snapshot_ref=self.trust_snapshot_ref,
                trust_snapshot_content_hash=str(self.trust_snapshot_ref.artifact_id),
                verification_receipt_ref=self.policy_owner_receipt_ref,
                verification_receipt_content_hash=str(self.policy_owner_receipt_ref.artifact_id),
                verifier_provenance_ref=self.owner_verifier_ref,
                predicate_class="independently_reconciled",
            ),
            predicate_class="independently_reconciled",
        )


@dataclass(slots=True)
class QualificationCase:
    store: FileSystemCAS
    query: contract.NativeChronologyQuery
    candidate: contract.NativeChronologyCandidate
    policy: contract.PersistedPredicateAdmissionPolicy
    admission_ref: ArtifactRef
    admission_index: _SingleAdmissionIndex
    owner_verifier: _FixtureOwnerVerifier
    adapter: EpochLikeQualificationAdapter | OpaqueInventoryQualificationAdapter
    owner_denominator_ref: contract.Digest

    def appoint_consumer(self) -> chronology_qualification.QualificationConsumer:
        registry = chronology_proof._PERSISTENCE_REGISTRY
        registry._appoint_for_test(
            store_factory=lambda: self.store,
            verifier_factory=FullPrefixVerifier,
            admission_index_factory=lambda: self.admission_index,
            owner_provenance_verifier_factory=lambda: self.owner_verifier,
        )
        return chronology_qualification.QualificationConsumer.from_current_owner_container()


def make_qualification_case(
    root: Path,
    *,
    shape: Literal["epoch", "inventory"],
    member_count: int,
    candidate_member_ordinals: tuple[int, ...] | None = None,
    required_native_head_role: str | None = None,
    native_authority_head_refs: tuple[contract.Digest, ...] | None = None,
    exterior_limitation_code: str | None = None,
    annotation_revision: int = 0,
    policy_profile: str | None = None,
    owner_native_profile: str | None = None,
    candidate_profile: str | None = None,
    predicate_class: contract.PredicateClass = "independently_reconciled",
    omit_query_predicate: bool = False,
    missing_owner_relation: bool = False,
    include_novel_candidate_member: bool = False,
) -> QualificationCase:
    store = FileSystemCAS(root)
    family = "epoch-like-fixture" if shape == "epoch" else "opaque-inventory-fixture"
    selected_profile = policy_profile or f"fixture.{shape}.native@1"
    authoritative_profile = owner_native_profile or selected_profile
    observed_profile = candidate_profile or authoritative_profile
    candidate_member_count = member_count + int(include_novel_candidate_member)
    candidate_ordinals = (
        tuple(range(candidate_member_count))
        if candidate_member_ordinals is None
        else candidate_member_ordinals
    )
    if len(candidate_ordinals) != len(set(candidate_ordinals)) or any(
        ordinal < 0 or ordinal >= candidate_member_count for ordinal in candidate_ordinals
    ):
        raise ValueError("candidate member ordinals must be unique available members")
    domain = contract.ChronologyProofDomain(
        format=contract.FULL_PREFIX_FORMAT,
        profile=contract.FULL_PREFIX_PROFILE,
        proof_domain=f"{shape}-conformance",
        family=family,
        scope_ref=_digest(f"{shape}:scope"),
        authority_purpose="publication",
    )
    query = contract.NativeChronologyQuery(
        domain=domain,
        requested_cutoff_ref=_digest(f"{shape}:cutoff"),
        requested_query_context_ref=_digest(f"{shape}:query-context"),
    )
    key = contract.PredicatePolicySelectionKey(
        family=family,
        proof_domain=domain.proof_domain,
        scope_ref=domain.scope_ref,
        authority_purpose=domain.authority_purpose,
        requested_cutoff_ref=query.requested_cutoff_ref,
    )
    member_rule = contract.PredicateAdmissionRule(
        predicate_id="owner_member_admitted",
        subject_kind="member",
        admitted_classes=("independently_reconciled",),
    )
    query_rule = contract.PredicateAdmissionRule(
        predicate_id="owner_denominator_complete",
        subject_kind="query",
        admitted_classes=("independently_reconciled",),
    )
    provenance_bytes = f"{shape}:owner-provenance:v1".encode()
    provenance_ref = _put_raw(
        store,
        provenance_bytes,
        kind="fixture.policy-owner-provenance",
    )
    policy_statement = contract.PredicateAdmissionPolicyStatement(
        schema_version="polisyos.chronology.predicate-policy.v1",
        key=key,
        native_schema_profile=selected_profile,
        required_native_head_role=required_native_head_role,
        rules=(member_rule, query_rule),
        owner_provenance_ref=provenance_ref,
        owner_provenance_content_hash=contract._sha256_digest(provenance_bytes),
    )
    policy_ref = _put_statement(
        store,
        policy_statement,
        kind="fixture.predicate-policy",
    )
    persisted_policy = contract.PersistedPredicateAdmissionPolicy(
        policy_ref=policy_ref,
        policy_content_hash=contract._predicate_policy_content_hash(policy_statement),
        statement=policy_statement,
    )

    owner_members: list[_NativeDenominatorMember] = []
    candidate_members: dict[int, contract.ChronologyMemberInput] = {}
    candidate_member_rows: dict[int, contract.MemberPredicateDisposition] = {}
    for ordinal in range(candidate_member_count):
        native_bytes = _native_bytes(
            shape=shape,
            ordinal=ordinal,
            annotation_revision=annotation_revision,
        )
        native_ref = _put_raw(store, native_bytes, kind=f"fixture.{shape}.member")
        member_ref = _digest(f"{shape}:member:{ordinal}")
        basis_ref = _digest(f"{shape}:basis:{ordinal}")
        context_ref = _digest(f"{shape}:context:{ordinal}")
        evidence_statement = _OwnerEvidenceStatement(
            schema_version="fixture.chronology.owner-evidence.v1",
            subject_kind="member",
            subject_ref=member_ref,
            predicate_id=member_rule.predicate_id,
            predicate_class=predicate_class,
            status="satisfied",
            failure_code=None,
        )
        evidence_ref = _put_raw(
            store,
            _model_bytes(evidence_statement),
            kind="fixture.owner-predicate-evidence",
        )
        if ordinal < member_count:
            owner_members.append(
                _NativeDenominatorMember(
                    member_ref=member_ref,
                    native_artifact_ref=native_ref,
                    native_content_hash=contract._native_content_hash(native_bytes),
                    native_schema_profile=authoritative_profile,
                    member_admission_basis_ref=basis_ref,
                    member_admission_context_ref=context_ref,
                    predicate_evidence_refs=(evidence_ref,),
                )
            )
        candidate_members[ordinal] = contract.ChronologyMemberInput(
            member_ref=member_ref,
            native_artifact_ref=native_ref,
            native_content_hash=contract._native_content_hash(native_bytes),
            native_schema_profile=observed_profile,
            native_bytes=native_bytes,
            member_admission_basis_ref=basis_ref,
            member_admission_context_ref=context_ref,
        )
        candidate_member_rows[ordinal] = contract.MemberPredicateDisposition(
            member_ref=member_ref,
            disposition=contract.PredicateDisposition(
                predicate_id=member_rule.predicate_id,
                predicate_class=predicate_class,
                status="satisfied",
                evidence_ref=evidence_ref,
                failure_code=None,
            ),
        )

    query_evidence_statement = _OwnerEvidenceStatement(
        schema_version="fixture.chronology.owner-evidence.v1",
        subject_kind="query",
        subject_ref=query.requested_query_context_ref,
        predicate_id=query_rule.predicate_id,
        predicate_class=predicate_class,
        status="satisfied",
        failure_code=None,
    )
    query_evidence_ref = _put_raw(
        store,
        _model_bytes(query_evidence_statement),
        kind="fixture.owner-predicate-evidence",
    )
    heads = native_authority_head_refs
    if heads is None:
        heads = (_digest("epoch:authority-head"),) if shape == "epoch" else ()

    owner_denominator = _NativeDenominatorStatement(
        schema_version="fixture.chronology.native-denominator.v1",
        family=family,
        native_schema_profile=authoritative_profile,
        native_authority_head_refs=heads,
        members=tuple(owner_members),
    )
    owner_denominator_bytes = _model_bytes(owner_denominator)
    owner_denominator_artifact_ref = _put_raw(
        store,
        owner_denominator_bytes,
        kind="fixture.native-denominator",
    )
    owner_query_context = _OwnerQueryContextStatement(
        schema_version="fixture.chronology.owner-query-context.v1",
        query=query,
        exterior_limitation_code=exterior_limitation_code,
        predicate_evidence_refs=(query_evidence_ref,),
    )
    owner_query_context_bytes = _model_bytes(owner_query_context)
    owner_query_context_artifact_ref = _put_raw(
        store,
        owner_query_context_bytes,
        kind="fixture.native-query-context",
    )

    candidate_denominator_members = tuple(
        _NativeDenominatorMember(
            member_ref=candidate_members[ordinal].member_ref,
            native_artifact_ref=candidate_members[ordinal].native_artifact_ref,
            native_content_hash=candidate_members[ordinal].native_content_hash,
            native_schema_profile=candidate_members[ordinal].native_schema_profile,
            member_admission_basis_ref=(candidate_members[ordinal].member_admission_basis_ref),
            member_admission_context_ref=(candidate_members[ordinal].member_admission_context_ref),
            predicate_evidence_refs=(candidate_member_rows[ordinal].disposition.evidence_ref,),
        )
        for ordinal in candidate_ordinals
    )
    candidate_denominator = _NativeDenominatorStatement(
        schema_version="fixture.chronology.native-denominator.v1",
        family=family,
        native_schema_profile=observed_profile,
        native_authority_head_refs=heads,
        members=candidate_denominator_members,
    )
    candidate_denominator_bytes = _model_bytes(candidate_denominator)
    candidate_denominator_artifact_ref = _put_raw(
        store,
        candidate_denominator_bytes,
        kind="fixture.native-denominator",
    )
    candidate_denominator_ref = contract._sha256_digest(
        _DENOMINATOR_PREFIX,
        candidate_denominator_bytes,
    )
    query_predicates = ()
    candidate_query_evidence_refs = ()
    if not omit_query_predicate:
        query_predicates = (
            contract.QueryPredicateDisposition(
                requested_query_context_ref=query.requested_query_context_ref,
                disposition=contract.PredicateDisposition(
                    predicate_id=query_rule.predicate_id,
                    predicate_class=predicate_class,
                    status="satisfied",
                    evidence_ref=query_evidence_ref,
                    failure_code=None,
                ),
            ),
        )
        candidate_query_evidence_refs = (query_evidence_ref,)
    candidate_query_context = _OwnerQueryContextStatement(
        schema_version="fixture.chronology.owner-query-context.v1",
        query=query,
        exterior_limitation_code=exterior_limitation_code,
        predicate_evidence_refs=candidate_query_evidence_refs,
    )
    candidate_query_context_bytes = _model_bytes(candidate_query_context)
    candidate_query_context_artifact_ref = _put_raw(
        store,
        candidate_query_context_bytes,
        kind="fixture.native-query-context",
    )

    candidate = contract.NativeChronologyCandidate(
        query=query,
        declared_denominator_ref=candidate_denominator_ref,
        native_denominator_artifact_ref=candidate_denominator_artifact_ref,
        native_denominator_content_hash=candidate_denominator_ref,
        query_context_artifact_ref=candidate_query_context_artifact_ref,
        query_context_content_hash=contract._sha256_digest(
            _QUERY_CONTEXT_PREFIX,
            candidate_query_context_bytes,
        ),
        ordered_members=tuple(candidate_members[ordinal] for ordinal in candidate_ordinals),
        member_predicates=tuple(candidate_member_rows[ordinal] for ordinal in candidate_ordinals),
        query_predicates=query_predicates,
        exterior_limitation_code=exterior_limitation_code,
        native_authority_head_refs=heads,
    )

    owner_relation = _OwnerRelationStatement(
        schema_version="fixture.chronology.owner-relation.v1",
        key=key,
        policy_ref=policy_ref,
        native_denominator_artifact_ref=owner_denominator_artifact_ref,
        query_context_artifact_ref=owner_query_context_artifact_ref,
    )
    owner_relation_bytes = _model_bytes(owner_relation)
    if missing_owner_relation:
        owner_relation_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(_digest(f"{shape}:missing-relation")),
            kind="fixture.owner-relation",
            media_type="application/octet-stream",
        )
    else:
        owner_relation_ref = _put_raw(
            store,
            owner_relation_bytes,
            kind="fixture.owner-relation",
        )
    admission_statement = contract.PredicatePolicyAdmissionStatement(
        schema_version="polisyos.chronology.predicate-policy-admission.v1",
        key=key,
        requested_query_context_ref=query.requested_query_context_ref,
        native_schema_profile=selected_profile,
        policy_ref=policy_ref,
        policy_content_hash=persisted_policy.policy_content_hash,
        owner_relation_ref=owner_relation_ref,
        owner_relation_content_hash=contract._sha256_digest(owner_relation_bytes),
    )
    admission_ref = _put_statement(
        store,
        admission_statement,
        kind="fixture.predicate-policy-admission",
    )

    owner_receipt_bytes = f"{shape}:owner-verification-receipt".encode()
    owner_receipt_ref = _put_raw(
        store,
        owner_receipt_bytes,
        kind="fixture.owner-verification-receipt",
    )
    owner_verifier_ref = _put_raw(
        store,
        f"{shape}:owner-verifier".encode(),
        kind="fixture.owner-verifier-provenance",
    )
    trust_snapshot_ref = _put_raw(
        store,
        f"{shape}:trust-snapshot".encode(),
        kind="fixture.trust-snapshot",
    )
    policy_owner_receipt_ref = _put_raw(
        store,
        f"{shape}:policy-owner-receipt".encode(),
        kind="fixture.policy-owner-receipt",
    )
    evidence_verifier_ref = _put_raw(
        store,
        f"{shape}:evidence-verifier".encode(),
        kind="fixture.evidence-verifier",
    )
    failure_evidence_ref = _put_raw(
        store,
        f"{shape}:owner-rejection".encode(),
        kind="fixture.owner-rejection",
    )
    admission_index = _SingleAdmissionIndex(key=key, refs=(admission_ref,))
    owner_verifier = _FixtureOwnerVerifier(
        store=store,
        key=key,
        policy=persisted_policy,
        policy_owner_provenance_bytes=provenance_bytes,
        owner_relation_bytes=owner_relation_bytes,
        owner_relation_ref=owner_relation_ref,
        owner_relation_content_hash=contract._sha256_digest(owner_relation_bytes),
        owner_receipt_ref=owner_receipt_ref,
        owner_verifier_ref=owner_verifier_ref,
        policy_owner_provenance_ref=provenance_ref,
        trust_snapshot_ref=trust_snapshot_ref,
        policy_owner_receipt_ref=policy_owner_receipt_ref,
        evidence_verifier_ref=evidence_verifier_ref,
        failure_evidence_ref=failure_evidence_ref,
    )
    adapter: EpochLikeQualificationAdapter | OpaqueInventoryQualificationAdapter
    if shape == "epoch":
        adapter = EpochLikeQualificationAdapter(candidate=candidate)
    else:
        adapter = OpaqueInventoryQualificationAdapter(candidate=candidate)
    return QualificationCase(
        store=store,
        query=query,
        candidate=candidate,
        policy=persisted_policy,
        admission_ref=admission_ref,
        admission_index=admission_index,
        owner_verifier=owner_verifier,
        adapter=adapter,
        owner_denominator_ref=contract._sha256_digest(
            _DENOMINATOR_PREFIX,
            owner_denominator_bytes,
        ),
    )


__all__ = [
    "EpochLikeQualificationAdapter",
    "OpaqueInventoryQualificationAdapter",
    "QualificationCase",
    "make_qualification_case",
]
