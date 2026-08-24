"""Policy-free chronology proof contracts and byte-level profile primitives.

The common contract proves only integrity of a supplied native prefix. Native
membership, completeness, authority heads, acceptance, and custody remain with
the family owner and its consumers.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Literal, Protocol, cast, overload

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    ArtifactWriteOptions,
    CanonInfo,
    InputRef,
    IntegrityInfo,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)]
PredicateClass = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]
FullPrefixCheckState = Literal["not_requested", "not_evaluated", "satisfied", "rejected"]

FULL_PREFIX_FORMAT = "polisyos.chronology.full-prefix.v1"
FULL_PREFIX_PROFILE = "full_prefix_canon_json_0_2_0_sha256_256_v1"
FULL_PREFIX_MAX_MEMBERS = 2_500_000
FULL_PREFIX_MAX_BUNDLE_BYTES = 4 * 1024 * 1024 * 1024
FULL_PREFIX_MAX_MEMBER_FRAME_BYTES = 1_024
FULL_PREFIX_MAX_HEADER_FRAME_BYTES = 4_096

_GENESIS_PREFIX = b"polisyos.chronology.genesis.v1\0"
_MEMBER_PREFIX = b"polisyos.chronology.member.v1\0"
_NATIVE_PREFIX = b"polisyos.chronology.native.v1\0"
_BUNDLE_PREFIX = b"polisyos.chronology.bundle.v1\0"
_POLICY_ADMISSION_PREFIX = b"polisyos.chronology.predicate-policy-admission.v1\0"
_POLICY_PREFIX = b"polisyos.chronology.predicate-policy.v1\0"
_DENOMINATOR_PREFIX = b"polisyos.chronology.applicable-predicate-denominator.v1\0"
_OWNER_QUALIFIED_CANDIDATE_PREFIX = b"polisyos.chronology.owner-qualified-native-candidate.v1\0"
_VERIFICATION_RESULT_PREFIX = b"polisyos.chronology.full-prefix-verification-result.v1\0"

CHRONOLOGY_CANON_SPEC = CanonSpec(
    name="polisyos.canon.json",
    version="0.2.0",
    forbid_floats=True,
    forbid_nan_inf=True,
    exclude_none=False,
    max_depth=128,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)


class _ChronologyModel(BaseModel):
    """Strict immutable base for chronology wire DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _raw_value(value: Any) -> Any:
    """Copy a typed value into a fresh raw canonicalization value."""
    if isinstance(value, ArtifactID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {
            field.alias or name: _raw_value(getattr(value, name))
            for name, field in value.__class__.model_fields.items()
        }
    if isinstance(value, tuple | list):
        return [_raw_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _raw_value(item) for key, item in value.items()}
    return value


def _raw_model_mapping(value: BaseModel) -> dict[str, Any]:
    return {
        field.alias or name: _raw_value(getattr(value, name))
        for name, field in value.__class__.model_fields.items()
    }


def _canonical_raw_bytes(value: Any) -> bytes:
    """Canonicalize only an explicitly constructed raw mapping/list/scalar."""
    if isinstance(value, BaseModel) or dataclasses.is_dataclass(value):
        raise TypeError("chronology canonicalization requires a fresh raw mapping")
    return to_canonical_bytes(value, CHRONOLOGY_CANON_SPEC)


def _frame_record(payload: bytes) -> bytes:
    if len(payload) >= 1 << 64:
        raise ValueError("record length exceeds uint64")
    return len(payload).to_bytes(8, "big") + payload


def _split_framed_records(payload: bytes) -> list[bytes]:
    """Split a byte string into exact uint64-framed records."""
    records: list[bytes] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise ValueError("truncated record length")
        size = int.from_bytes(payload[offset : offset + 8], "big")
        offset += 8
        end = offset + size
        if end > len(payload):
            raise ValueError("truncated record payload")
        records.append(payload[offset:end])
        offset = end
    return records


def _sha256_digest(*chunks: bytes) -> Digest:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


class ChronologyProofDomain(_ChronologyModel):
    """Domain-separate one family, scope, and authority purpose."""

    format: Literal["polisyos.chronology.full-prefix.v1"]
    profile: Literal["full_prefix_canon_json_0_2_0_sha256_256_v1"]
    proof_domain: str = Field(min_length=1)
    family: str = Field(min_length=1)
    scope_ref: Digest
    authority_purpose: str = Field(min_length=1)


def _domain_raw_mapping(domain: ChronologyProofDomain) -> dict[str, Any]:
    return {
        "format": domain.format,
        "profile": domain.profile,
        "proof_domain": domain.proof_domain,
        "family": domain.family,
        "scope_ref": domain.scope_ref,
        "authority_purpose": domain.authority_purpose,
    }


def _domain_genesis(domain: ChronologyProofDomain) -> Digest:
    return _sha256_digest(
        _GENESIS_PREFIX,
        _canonical_raw_bytes(_domain_raw_mapping(domain)),
    )


def _native_content_hash(native_bytes: bytes) -> Digest:
    return _sha256_digest(_NATIVE_PREFIX, _frame_record(native_bytes))


def _bundle_content_hash(bundle_bytes: bytes) -> Digest:
    return _sha256_digest(_BUNDLE_PREFIX, bundle_bytes)


class NativeChronologyQuery(_ChronologyModel):
    """Family query without caller-selected policy or native profile."""

    domain: ChronologyProofDomain
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest


class PredicateDisposition(_ChronologyModel):
    """One owner predicate result and its frozen provenance class."""

    predicate_id: str = Field(min_length=1)
    predicate_class: PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    evidence_ref: ArtifactRef | None
    failure_code: str | None

    @model_validator(mode="after")
    def _validate_failure_code(self) -> PredicateDisposition:
        if (self.status == "satisfied") != (self.failure_code is None):
            raise ValueError("failure_code is required exactly when status is not satisfied")
        return self


class PredicateAdmissionRule(_ChronologyModel):
    """Owner rule for one member- or query-level predicate."""

    predicate_id: str = Field(min_length=1)
    subject_kind: Literal["member", "query"]
    admitted_classes: tuple[Literal["recomputed", "independently_reconciled"], ...] = Field(
        min_length=1
    )
    require_evidence_ref: Literal[True] = True

    @model_validator(mode="after")
    def _unique_classes(self) -> PredicateAdmissionRule:
        if len(set(self.admitted_classes)) != len(self.admitted_classes):
            raise ValueError("duplicate admitted predicate class")
        return self


class PredicatePolicySelectionKey(_ChronologyModel):
    """Unique native-owner key for policy/profile admission."""

    family: str = Field(min_length=1)
    proof_domain: str = Field(min_length=1)
    scope_ref: Digest
    authority_purpose: str = Field(min_length=1)
    requested_cutoff_ref: Digest


class PredicateAdmissionPolicyStatement(_ChronologyModel):
    """Owner policy selected before adapter evidence is read."""

    schema_version: Literal["polisyos.chronology.predicate-policy.v1"]
    key: PredicatePolicySelectionKey
    native_schema_profile: str = Field(min_length=1)
    required_native_head_role: str | None = Field(min_length=1)
    rules: tuple[PredicateAdmissionRule, ...]
    owner_provenance_ref: ArtifactRef
    owner_provenance_content_hash: Digest

    @model_validator(mode="after")
    def _unique_rules(self) -> PredicateAdmissionPolicyStatement:
        keys = [(rule.subject_kind, rule.predicate_id) for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate predicate rule")
        return self


class PersistedPredicateAdmissionPolicy(_ChronologyModel):
    """Persisted policy statement and both artifact/semantic identities."""

    policy_ref: ArtifactRef
    policy_content_hash: Digest
    statement: PredicateAdmissionPolicyStatement


class ApplicablePredicateDenominatorStatement(_ChronologyModel):
    """Complete owner-required predicate denominator for one query."""

    schema_version: Literal["polisyos.chronology.applicable-predicate-denominator.v1"]
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    member_subject_refs: tuple[Digest, ...]
    required_member_predicate_pairs: tuple[tuple[Digest, str], ...]
    required_query_predicate_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _unique_denominator_rows(self) -> ApplicablePredicateDenominatorStatement:
        if len(self.member_subject_refs) != len(set(self.member_subject_refs)):
            raise ValueError("duplicate member_subject_ref")
        if len(self.required_member_predicate_pairs) != len(
            set(self.required_member_predicate_pairs)
        ):
            raise ValueError("duplicate required member predicate pair")
        if len(self.required_query_predicate_ids) != len(set(self.required_query_predicate_ids)):
            raise ValueError("duplicate required query predicate")
        member_refs = set(self.member_subject_refs)
        if any(ref not in member_refs for ref, _ in self.required_member_predicate_pairs):
            raise ValueError("required predicate names an unknown member subject")
        return self


class PersistedApplicablePredicateDenominator(_ChronologyModel):
    """Persisted denominator with raw CAS and semantic identities."""

    artifact_ref: ArtifactRef
    cas_raw_bytes_hash: Digest
    denominator_content_hash: Digest
    statement: ApplicablePredicateDenominatorStatement


class PredicatePolicyAdmissionStatement(_ChronologyModel):
    """Owner admission binding a query coordinate to exact policy bytes."""

    schema_version: Literal["polisyos.chronology.predicate-policy-admission.v1"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    native_schema_profile: str = Field(min_length=1)
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: Digest


class PersistedPredicatePolicyAdmission(_ChronologyModel):
    """Persisted unique policy admission relation."""

    admission_ref: ArtifactRef
    admission_content_hash: Digest
    statement: PredicatePolicyAdmissionStatement


class VerifiedNativeMemberIdentity(_ChronologyModel):
    """Independently resolved identity for one native member."""

    member_ref: Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: Digest
    native_schema_profile: str = Field(min_length=1)
    member_admission_basis_ref: Digest
    member_admission_context_ref: Digest


class VerifiedNativeSubjectIdentity(_ChronologyModel):
    """Independently resolved denominator or query-context identity."""

    subject_kind: Literal["denominator", "query_context"]
    subject_ref: Digest
    artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_content_hash: Digest
    verifier_provenance_ref: ArtifactRef


class VerifiedPolicyOwnerProvenance(_ChronologyModel):
    """Independent receipt over policy-owner provenance."""

    policy_ref: ArtifactRef
    policy_content_hash: Digest
    owner_provenance_ref: ArtifactRef
    owner_provenance_content_hash: Digest
    trust_snapshot_ref: ArtifactRef
    trust_snapshot_content_hash: Digest
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]


class VerifiedOwnerPredicateEvidence(_ChronologyModel):
    """Content-resolved owner evidence for one exact subject/predicate row."""

    subject_kind: Literal["member", "query"]
    subject_ref: Digest
    predicate_id: str = Field(min_length=1)
    predicate_class: PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    evidence_ref: ArtifactRef | None
    evidence_content_hash: Digest | None
    evidence_verifier_provenance_ref: ArtifactRef | None

    @model_validator(mode="after")
    def _evidence_triple(self) -> VerifiedOwnerPredicateEvidence:
        present = (
            self.evidence_ref is not None,
            self.evidence_content_hash is not None,
            self.evidence_verifier_provenance_ref is not None,
        )
        if any(present) and not all(present):
            raise ValueError("evidence fields must be all present or all absent")
        return self


class ChronologyMemberInput(_ChronologyModel):
    """Opaque native member bytes plus family-owned identity bindings."""

    member_ref: Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: Digest
    native_schema_profile: str = Field(min_length=1)
    native_bytes: bytes
    member_admission_basis_ref: Digest
    member_admission_context_ref: Digest

    @model_validator(mode="after")
    def _bind_native_bytes(self) -> ChronologyMemberInput:
        if self.native_content_hash != _native_content_hash(self.native_bytes):
            raise ValueError("native_content_hash does not bind native_bytes")
        return self


class MemberPredicateDisposition(_ChronologyModel):
    """Member-keyed predicate disposition."""

    member_ref: Digest
    disposition: PredicateDisposition


class QueryPredicateDisposition(_ChronologyModel):
    """Requested-query-context-keyed predicate disposition."""

    requested_query_context_ref: Digest
    disposition: PredicateDisposition


class NativeChronologyCandidate(_ChronologyModel):
    """Family adapter's candidate native history; never authority by itself."""

    query: NativeChronologyQuery
    declared_denominator_ref: Digest
    native_denominator_artifact_ref: ArtifactRef
    native_denominator_content_hash: Digest
    query_context_artifact_ref: ArtifactRef
    query_context_content_hash: Digest
    ordered_members: tuple[ChronologyMemberInput, ...]
    member_predicates: tuple[MemberPredicateDisposition, ...]
    query_predicates: tuple[QueryPredicateDisposition, ...]
    exterior_limitation_code: str | None
    native_authority_head_refs: tuple[Digest, ...]

    @model_validator(mode="after")
    def _candidate_keys(self) -> NativeChronologyCandidate:
        member_refs = tuple(member.member_ref for member in self.ordered_members)
        if len(member_refs) != len(set(member_refs)):
            raise ValueError("duplicate candidate member_ref")
        predicate_keys = [
            (row.member_ref, row.disposition.predicate_id) for row in self.member_predicates
        ]
        if len(predicate_keys) != len(set(predicate_keys)):
            raise ValueError("duplicate member predicate disposition")
        if any(row.member_ref not in set(member_refs) for row in self.member_predicates):
            raise ValueError("member predicate references an unknown member")
        query_keys = [row.disposition.predicate_id for row in self.query_predicates]
        if len(query_keys) != len(set(query_keys)):
            raise ValueError("duplicate query predicate disposition")
        if any(
            row.requested_query_context_ref != self.query.requested_query_context_ref
            for row in self.query_predicates
        ):
            raise ValueError("query predicate is bound to a different query context")
        if len(self.native_authority_head_refs) != len(set(self.native_authority_head_refs)):
            raise ValueError("duplicate native authority head")
        return self


def _native_candidate_content_hash(candidate: NativeChronologyCandidate) -> Digest:
    mapping = _raw_model_mapping(candidate)
    return _sha256_digest(
        _OWNER_QUALIFIED_CANDIDATE_PREFIX,
        _frame_record(_canonical_raw_bytes(mapping)),
    )


class VerifiedPredicatePolicyOwnerRelation(_ChronologyModel):
    """Independent owner receipt over policy, denominator, members and evidence."""

    query: NativeChronologyQuery
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: Digest
    owner_verifier_provenance_ref: ArtifactRef
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    candidate_content_hash: Digest
    owner_declared_denominator_ref: Digest
    candidate_declared_denominator_ref: Digest
    owner_ordered_member_refs: tuple[Digest, ...]
    candidate_ordered_member_refs: tuple[Digest, ...]
    denominator_identity: VerifiedNativeSubjectIdentity
    query_context_identity: VerifiedNativeSubjectIdentity
    member_identities: tuple[VerifiedNativeMemberIdentity, ...]
    predicate_evidence: tuple[VerifiedOwnerPredicateEvidence, ...]
    policy_owner_provenance: VerifiedPolicyOwnerProvenance
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _receipt_shape(self) -> VerifiedPredicatePolicyOwnerRelation:
        if self.denominator_identity.subject_kind != "denominator":
            raise ValueError("denominator identity has the wrong subject kind")
        if self.query_context_identity.subject_kind != "query_context":
            raise ValueError("query context identity has the wrong subject kind")
        if self.owner_declared_denominator_ref != self.candidate_declared_denominator_ref:
            raise ValueError("owner and candidate denominators differ")
        if self.owner_ordered_member_refs != self.candidate_ordered_member_refs:
            raise ValueError("owner and candidate member sequences differ")
        if tuple(row.member_ref for row in self.member_identities) != (
            self.candidate_ordered_member_refs
        ):
            raise ValueError("verified member identities do not cover the ordered sequence")
        evidence_keys = [
            (row.subject_kind, row.subject_ref, row.predicate_id) for row in self.predicate_evidence
        ]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("duplicate verified predicate evidence")
        return self


class OwnerQualifiedNativeCandidate(_ChronologyModel):
    """Candidate whose complete content is bound by the owner verifier receipt."""

    candidate: NativeChronologyCandidate
    candidate_content_hash: Digest
    owner_relation_verification: VerifiedPredicatePolicyOwnerRelation

    @model_validator(mode="after")
    def _bind_receipt(self) -> OwnerQualifiedNativeCandidate:
        candidate = self.candidate
        receipt = self.owner_relation_verification
        expected_hash = _native_candidate_content_hash(candidate)
        if self.candidate_content_hash != expected_hash:
            raise ValueError("candidate_content_hash does not bind the candidate")
        if receipt.candidate_content_hash != expected_hash:
            raise ValueError("owner receipt does not bind the candidate")
        if receipt.query != candidate.query:
            raise ValueError("owner receipt query differs from candidate query")
        if receipt.candidate_declared_denominator_ref != candidate.declared_denominator_ref:
            raise ValueError("owner receipt denominator differs from candidate")
        member_refs = tuple(member.member_ref for member in candidate.ordered_members)
        if receipt.candidate_ordered_member_refs != member_refs:
            raise ValueError("owner receipt member sequence differs from candidate")
        if receipt.denominator_identity.subject_ref != candidate.declared_denominator_ref:
            raise ValueError("denominator subject identity differs from candidate")
        if receipt.denominator_identity.artifact_ref != candidate.native_denominator_artifact_ref:
            raise ValueError("denominator artifact identity differs from candidate")
        if (
            receipt.denominator_identity.semantic_content_hash
            != candidate.native_denominator_content_hash
        ):
            raise ValueError("denominator semantic hash differs from candidate")
        if (
            receipt.query_context_identity.subject_ref
            != candidate.query.requested_query_context_ref
        ):
            raise ValueError("query-context subject identity differs from candidate")
        if receipt.query_context_identity.artifact_ref != candidate.query_context_artifact_ref:
            raise ValueError("query-context artifact identity differs from candidate")
        if (
            receipt.query_context_identity.semantic_content_hash
            != candidate.query_context_content_hash
        ):
            raise ValueError("query-context semantic hash differs from candidate")
        for member, identity in zip(
            candidate.ordered_members, receipt.member_identities, strict=True
        ):
            expected = (
                member.member_ref,
                member.native_artifact_ref,
                member.native_content_hash,
                member.native_schema_profile,
                member.member_admission_basis_ref,
                member.member_admission_context_ref,
            )
            observed = (
                identity.member_ref,
                identity.native_artifact_ref,
                identity.native_content_hash,
                identity.native_schema_profile,
                identity.member_admission_basis_ref,
                identity.member_admission_context_ref,
            )
            if observed != expected:
                raise ValueError("verified member identity differs from candidate")
        return self


class ResolvedPredicatePolicyAdmission(_ChronologyModel):
    """Exact admission, policy and independently verified owner relation."""

    admission: PersistedPredicatePolicyAdmission
    policy: PersistedPredicateAdmissionPolicy
    owner_relation_verification: VerifiedPredicatePolicyOwnerRelation


class PredicatePolicyResolutionContext(_ChronologyModel):
    """Immutable context passed to every policy byte loader."""

    query: NativeChronologyQuery
    key: PredicatePolicySelectionKey

    @model_validator(mode="after")
    def _bind_key(self) -> PredicatePolicyResolutionContext:
        expected = PredicatePolicySelectionKey(
            family=self.query.domain.family,
            proof_domain=self.query.domain.proof_domain,
            scope_ref=self.query.domain.scope_ref,
            authority_purpose=self.query.domain.authority_purpose,
            requested_cutoff_ref=self.query.requested_cutoff_ref,
        )
        if self.key != expected:
            raise ValueError("policy resolution key does not match the full query")
        return self


class PolicyAdmissionMissingFailure(_ChronologyModel):
    """No owner admission exists for the exact key."""

    code: Literal["policy_admission_missing"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest


class PolicyAdmissionAmbiguousFailure(_ChronologyModel):
    """Multiple owner admissions exist for the exact key."""

    code: Literal["policy_admission_ambiguous"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest


class PolicyBytesMissingFailure(_ChronologyModel):
    """Required policy-plane bytes cannot be resolved."""

    code: Literal["policy_bytes_missing"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    artifact_role: Literal["admission", "policy", "policy_owner_provenance", "owner_relation"]
    missing_ref: ArtifactRef | None


class PolicyBindingMismatchFailure(_ChronologyModel):
    """Present policy-plane bytes fail content binding."""

    code: Literal["policy_binding_mismatch"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    evidence_ref: ArtifactRef


class PolicyQueryBindingMismatchFailure(_ChronologyModel):
    """Admission bytes bind a different native query coordinate."""

    code: Literal["policy_query_binding_mismatch"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    admitted_query_context_ref: Digest


PredicatePolicyResolutionFailure = Annotated[
    PolicyAdmissionMissingFailure
    | PolicyAdmissionAmbiguousFailure
    | PolicyBytesMissingFailure
    | PolicyBindingMismatchFailure
    | PolicyQueryBindingMismatchFailure,
    Field(discriminator="code"),
]


class PolicyOwnerRelationRejected(_ChronologyModel):
    """Present owner relation was independently rejected."""

    code: Literal["policy_owner_relation_rejected"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    owner_relation_ref: ArtifactRef
    evidence_ref: ArtifactRef


class PolicyOwnerDenominatorMismatchFailure(_ChronologyModel):
    """Owner relation rejected before qualification on a denominator mismatch."""

    code: Literal["native_denominator_mismatch"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    expected_denominator_ref: Digest
    observed_denominator_ref: Digest

    @model_validator(mode="after")
    def _is_mismatch(self) -> PolicyOwnerDenominatorMismatchFailure:
        if self.expected_denominator_ref == self.observed_denominator_ref:
            raise ValueError("denominator mismatch requires unequal refs")
        return self


class PolicyOwnerRelationNotEstablished(_ChronologyModel):
    """Independent owner relation could not be established."""

    code: Literal["policy_owner_relation_not_established"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    owner_relation_ref: ArtifactRef | None


PredicatePolicyOwnerRelationFailure = Annotated[
    PolicyOwnerRelationRejected
    | PolicyOwnerDenominatorMismatchFailure
    | PolicyOwnerRelationNotEstablished,
    Field(discriminator="code"),
]


class PredicatePolicyAdmissionIndex(Protocol):
    """Enumerate persisted owner admissions for one exact key."""

    def enumerate_admission_refs(
        self, *, key: PredicatePolicySelectionKey
    ) -> tuple[ArtifactRef, ...]: ...


class PredicatePolicyOwnerProvenanceVerifier(Protocol):
    """Independently resolve and verify family-native owner evidence."""

    def verify_owner_relation(
        self,
        *,
        query: NativeChronologyQuery,
        admission: PredicatePolicyAdmissionStatement,
        policy: PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: NativeChronologyCandidate,
    ) -> VerifiedPredicatePolicyOwnerRelation | PredicatePolicyOwnerRelationFailure: ...


class ChronologyPredicatePolicyArtifacts:
    """Load exact policy-plane bytes through the canonical artifact store."""

    def __init__(self, *, store: ArtifactStore) -> None:
        self._store = store

    def load_admission(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        admission_ref: ArtifactRef,
    ) -> PersistedPredicatePolicyAdmission | PredicatePolicyResolutionFailure:
        """Load and content-verify one admission statement."""
        return self._load_typed_statement(
            context=context,
            artifact_ref=admission_ref,
            expected_content_hash=None,
            role="admission",
            model=PredicatePolicyAdmissionStatement,
            prefix=_POLICY_ADMISSION_PREFIX,
        )

    def load_policy(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        policy_ref: ArtifactRef,
        expected_content_hash: Digest,
    ) -> PersistedPredicateAdmissionPolicy | PredicatePolicyResolutionFailure:
        """Load and content-verify one predicate policy."""
        return self._load_typed_statement(
            context=context,
            artifact_ref=policy_ref,
            expected_content_hash=expected_content_hash,
            role="policy",
            model=PredicateAdmissionPolicyStatement,
            prefix=_POLICY_PREFIX,
        )

    def load_owner_relation_bytes(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        relation_ref: ArtifactRef,
        expected_content_hash: Digest,
    ) -> bytes | PredicatePolicyResolutionFailure:
        """Load opaque owner relation bytes after CAS/content verification."""
        return self._load_opaque_bytes(
            context=context,
            artifact_ref=relation_ref,
            expected_content_hash=expected_content_hash,
            role="owner_relation",
        )

    def load_policy_owner_provenance_bytes(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        provenance_ref: ArtifactRef,
        expected_content_hash: Digest,
    ) -> bytes | PredicatePolicyResolutionFailure:
        """Load opaque policy-owner provenance bytes after verification."""
        return self._load_opaque_bytes(
            context=context,
            artifact_ref=provenance_ref,
            expected_content_hash=expected_content_hash,
            role="policy_owner_provenance",
        )

    def _missing(
        self,
        context: PredicatePolicyResolutionContext,
        role: Literal["admission", "policy", "policy_owner_provenance", "owner_relation"],
        ref: ArtifactRef | None,
    ) -> PolicyBytesMissingFailure:
        return PolicyBytesMissingFailure(
            code="policy_bytes_missing",
            status="not_established",
            key=context.key,
            requested_query_context_ref=context.query.requested_query_context_ref,
            artifact_role=role,
            missing_ref=ref,
        )

    def _mismatch(
        self,
        context: PredicatePolicyResolutionContext,
        ref: ArtifactRef,
    ) -> PolicyBindingMismatchFailure:
        return PolicyBindingMismatchFailure(
            code="policy_binding_mismatch",
            status="rejected",
            key=context.key,
            requested_query_context_ref=context.query.requested_query_context_ref,
            evidence_ref=ref,
        )

    def _verified_bytes(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        artifact_ref: ArtifactRef,
        role: Literal["admission", "policy", "policy_owner_provenance", "owner_relation"],
    ) -> bytes | PredicatePolicyResolutionFailure:
        try:
            report = self._store.verify(artifact_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._missing(context, role, artifact_ref)
        if not report.ok:
            if report.actual_sha256_hex is None:
                return self._missing(context, role, artifact_ref)
            return self._mismatch(context, artifact_ref)
        try:
            payload = self._store.get_bytes(artifact_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._missing(context, role, artifact_ref)
        if _sha256_digest(payload) != str(artifact_ref.artifact_id):
            return self._mismatch(context, artifact_ref)
        return payload

    def _load_opaque_bytes(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        artifact_ref: ArtifactRef,
        expected_content_hash: Digest,
        role: Literal["policy_owner_provenance", "owner_relation"],
    ) -> bytes | PredicatePolicyResolutionFailure:
        payload = self._verified_bytes(context=context, artifact_ref=artifact_ref, role=role)
        if not isinstance(payload, bytes):
            return payload
        if _sha256_digest(payload) != expected_content_hash:
            return self._mismatch(context, artifact_ref)
        return payload

    @overload
    def _load_typed_statement(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        artifact_ref: ArtifactRef,
        expected_content_hash: Digest | None,
        role: Literal["admission"],
        model: type[PredicatePolicyAdmissionStatement],
        prefix: bytes,
    ) -> PersistedPredicatePolicyAdmission | PredicatePolicyResolutionFailure: ...

    @overload
    def _load_typed_statement(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        artifact_ref: ArtifactRef,
        expected_content_hash: Digest | None,
        role: Literal["policy"],
        model: type[PredicateAdmissionPolicyStatement],
        prefix: bytes,
    ) -> PersistedPredicateAdmissionPolicy | PredicatePolicyResolutionFailure: ...

    def _load_typed_statement(
        self,
        *,
        context: PredicatePolicyResolutionContext,
        artifact_ref: ArtifactRef,
        expected_content_hash: Digest | None,
        role: Literal["admission", "policy"],
        model: (type[PredicatePolicyAdmissionStatement] | type[PredicateAdmissionPolicyStatement]),
        prefix: bytes,
    ) -> (
        PersistedPredicatePolicyAdmission
        | PersistedPredicateAdmissionPolicy
        | PredicatePolicyResolutionFailure
    ):
        payload = self._verified_bytes(context=context, artifact_ref=artifact_ref, role=role)
        if not isinstance(payload, bytes):
            return payload
        try:
            records = _split_framed_records(payload)
            if len(records) != 1:
                raise ValueError("expected one framed statement")
            raw = json.loads(records[0])
            if _canonical_raw_bytes(raw) != records[0]:
                raise ValueError("non-canonical statement")
            statement = model.model_validate(raw)
        except (TypeError, ValueError):
            return self._mismatch(context, artifact_ref)
        semantic_hash = _sha256_digest(prefix, _frame_record(records[0]))
        if expected_content_hash is not None and semantic_hash != expected_content_hash:
            return self._mismatch(context, artifact_ref)
        if isinstance(statement, PredicatePolicyAdmissionStatement):
            if statement.key != context.key:
                return self._mismatch(context, artifact_ref)
            if statement.requested_query_context_ref != context.query.requested_query_context_ref:
                return PolicyQueryBindingMismatchFailure(
                    code="policy_query_binding_mismatch",
                    status="rejected",
                    key=context.key,
                    requested_query_context_ref=context.query.requested_query_context_ref,
                    admitted_query_context_ref=statement.requested_query_context_ref,
                )
            return PersistedPredicatePolicyAdmission(
                admission_ref=artifact_ref,
                admission_content_hash=semantic_hash,
                statement=statement,
            )
        if not isinstance(statement, PredicateAdmissionPolicyStatement):
            raise TypeError("policy loader produced an unexpected statement type")
        return PersistedPredicateAdmissionPolicy(
            policy_ref=artifact_ref,
            policy_content_hash=semantic_hash,
            statement=statement,
        )


class ApplicablePredicateDenominatorArtifactFailure(_ChronologyModel):
    """Typed failure to persist/reload the applicable denominator."""

    code: Literal["applicable_predicate_denominator_artifact_not_established"]
    status: Literal["not_established"]
    query: NativeChronologyQuery
    denominator_content_hash: Digest
    evidence_ref: ArtifactRef | None


class ChronologyApplicablePredicateDenominatorArtifacts:
    """Persist one owner-qualified denominator through the canonical store."""

    def __init__(self, *, store: ArtifactStore) -> None:
        self._store = store

    def persist_and_verify(
        self,
        *,
        query: NativeChronologyQuery,
        statement: ApplicablePredicateDenominatorStatement,
        owner_qualified_candidate: OwnerQualifiedNativeCandidate,
    ) -> PersistedApplicablePredicateDenominator | ApplicablePredicateDenominatorArtifactFailure:
        """Persist/reload an owner-qualified denominator through the live store."""
        denominator_hash = _denominator_content_hash(statement)
        candidate = owner_qualified_candidate.candidate
        owner_relation = owner_qualified_candidate.owner_relation_verification
        policy = owner_relation.policy_owner_provenance
        member_refs = tuple(member.member_ref for member in candidate.ordered_members)
        if (
            query != candidate.query
            or statement.policy_ref != policy.policy_ref
            or statement.policy_content_hash != policy.policy_content_hash
            or statement.member_subject_refs != member_refs
        ):
            return self._failure(
                query=query,
                denominator_content_hash=denominator_hash,
                evidence_ref=None,
            )

        raw_statement = _canonical_raw_bytes(_raw_model_mapping(statement))
        artifact_bytes = _frame_record(raw_statement)
        expected_artifact_id = ArtifactID.from_sha256_hex(content_hash(artifact_bytes))
        expected_ref = ArtifactRef(
            artifact_id=expected_artifact_id,
            kind="core.chronology.applicable_predicate_denominator",
            media_type="application/octet-stream",
        )
        inputs = [
            InputRef(
                artifact_id=owner_relation.verification_receipt_ref.artifact_id,
                role="owner_qualification_receipt",
            ),
            InputRef(
                artifact_id=candidate.native_denominator_artifact_ref.artifact_id,
                role="native_denominator",
            ),
            InputRef(
                artifact_id=candidate.query_context_artifact_ref.artifact_id,
                role="query_context",
            ),
            *(
                InputRef(
                    artifact_id=member.native_artifact_ref.artifact_id,
                    role="native_member",
                )
                for member in candidate.ordered_members
            ),
        ]
        schema = SchemaInfo(
            name="polisyos.chronology.ApplicablePredicateDenominator",
            version="1",
        )
        canon = CanonInfo.from_spec(CHRONOLOGY_CANON_SPEC)
        write_options = ArtifactWriteOptions(
            kind=expected_ref.kind,
            media_type=expected_ref.media_type,
            schema=schema,
            inputs=inputs,
            canon=canon,
        )
        observed_ref: ArtifactRef | None = None
        try:
            observed_ref = self._store.put_bytes(artifact_bytes, write_options)
            if observed_ref != expected_ref:
                raise ValueError("denominator store returned a different artifact ref")
            report = self._store.verify(expected_artifact_id)
            if not report.ok:
                raise ValueError("denominator store integrity was not established")
            observed_bytes = self._store.get_bytes(expected_artifact_id)
            if observed_bytes != artifact_bytes:
                raise ValueError("denominator bytes differ after reload")
            observed_manifest = self._store.get_manifest(expected_artifact_id)
            expected_manifest = ArtifactManifest(
                artifact_id=expected_artifact_id,
                kind=expected_ref.kind,
                media_type=expected_ref.media_type,
                byte_size=len(artifact_bytes),
                created_at=observed_manifest.created_at,
                schema=schema,
                canon=canon,
                inputs=inputs,
                integrity=IntegrityInfo(sha256=expected_artifact_id.hex),
            )
            if observed_manifest != expected_manifest:
                raise ValueError("denominator first-writer manifest differs")
            records = _split_framed_records(observed_bytes)
            if len(records) != 1:
                raise ValueError("denominator artifact has the wrong frame count")
            raw_reloaded = json.loads(records[0])
            if not isinstance(raw_reloaded, dict):
                raise ValueError("denominator artifact is not a canonical mapping")
            if _canonical_raw_bytes(raw_reloaded) != records[0]:
                raise ValueError("denominator artifact is non-canonical")
            reloaded = ApplicablePredicateDenominatorStatement.model_validate(raw_reloaded)
            if reloaded != statement or _denominator_content_hash(reloaded) != denominator_hash:
                raise ValueError("denominator semantic bytes differ after reload")
        except Exception:
            return self._failure(
                query=query,
                denominator_content_hash=denominator_hash,
                evidence_ref=observed_ref,
            )
        return PersistedApplicablePredicateDenominator(
            artifact_ref=expected_ref,
            cas_raw_bytes_hash=str(expected_artifact_id),
            denominator_content_hash=denominator_hash,
            statement=reloaded,
        )

    @staticmethod
    def _failure(
        *,
        query: NativeChronologyQuery,
        denominator_content_hash: Digest,
        evidence_ref: ArtifactRef | None,
    ) -> ApplicablePredicateDenominatorArtifactFailure:
        return ApplicablePredicateDenominatorArtifactFailure(
            code="applicable_predicate_denominator_artifact_not_established",
            status="not_established",
            query=query,
            denominator_content_hash=denominator_content_hash,
            evidence_ref=evidence_ref,
        )


class ChronologyBundleRequest(_ChronologyModel):
    """Complete native prefix request under a fixed owner-selected profile."""

    domain: ChronologyProofDomain
    native_schema_profile: str = Field(min_length=1)
    declared_denominator_ref: Digest
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest
    members: tuple[ChronologyMemberInput, ...]

    @model_validator(mode="after")
    def _member_profiles(self) -> ChronologyBundleRequest:
        if any(
            member.native_schema_profile != self.native_schema_profile for member in self.members
        ):
            raise ValueError("member native schema profile mismatch")
        refs = tuple(member.member_ref for member in self.members)
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate bundle member_ref")
        return self


class ChronologyBundleHeader(_ChronologyModel):
    """Canonical header for one complete supplied native prefix."""

    format: Literal["polisyos.chronology.full-prefix.v1"]
    profile: Literal["full_prefix_canon_json_0_2_0_sha256_256_v1"]
    proof_domain: str = Field(min_length=1)
    family: str = Field(min_length=1)
    scope_ref: Digest
    authority_purpose: str = Field(min_length=1)
    native_schema_profile: str = Field(min_length=1)
    declared_denominator_ref: Digest
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest
    member_count: int = Field(ge=0)
    native_bytes_total: int = Field(ge=0)
    first_commitment: Digest | None
    commitment_head: Digest

    @model_validator(mode="after")
    def _zero_shape(self) -> ChronologyBundleHeader:
        if self.member_count == 0 and self.first_commitment is not None:
            raise ValueError("zero-member header must have null first_commitment")
        if self.member_count > 0 and self.first_commitment is None:
            raise ValueError("non-empty header requires first_commitment")
        return self


def _header_raw_mapping(header: ChronologyBundleHeader) -> dict[str, Any]:
    return {
        "format": header.format,
        "profile": header.profile,
        "proof_domain": header.proof_domain,
        "family": header.family,
        "scope_ref": header.scope_ref,
        "authority_purpose": header.authority_purpose,
        "native_schema_profile": header.native_schema_profile,
        "declared_denominator_ref": header.declared_denominator_ref,
        "requested_cutoff_ref": header.requested_cutoff_ref,
        "requested_query_context_ref": header.requested_query_context_ref,
        "member_count": header.member_count,
        "native_bytes_total": header.native_bytes_total,
        "first_commitment": header.first_commitment,
        "commitment_head": header.commitment_head,
    }


def _member_frame_raw_mapping(
    *,
    domain: ChronologyProofDomain,
    native_schema_profile: str,
    member_ordinal: int,
    member: ChronologyMemberInput,
    predecessor_commitment: Digest,
) -> dict[str, Any]:
    return {
        "format": domain.format,
        "profile": domain.profile,
        "proof_domain": domain.proof_domain,
        "family": domain.family,
        "scope_ref": domain.scope_ref,
        "authority_purpose": domain.authority_purpose,
        "native_schema_profile": native_schema_profile,
        "member_ordinal": member_ordinal,
        "member_ref": member.member_ref,
        "member_content_hash": member.native_content_hash,
        "member_admission_basis_ref": member.member_admission_basis_ref,
        "member_admission_context_ref": member.member_admission_context_ref,
        "predecessor_commitment": predecessor_commitment,
    }


def _build_header(
    *,
    request: ChronologyBundleRequest,
    commitments: tuple[Digest, ...],
    native_bytes_total: int,
) -> ChronologyBundleHeader:
    genesis = _domain_genesis(request.domain)
    return ChronologyBundleHeader(
        format=request.domain.format,
        profile=request.domain.profile,
        proof_domain=request.domain.proof_domain,
        family=request.domain.family,
        scope_ref=request.domain.scope_ref,
        authority_purpose=request.domain.authority_purpose,
        native_schema_profile=request.native_schema_profile,
        declared_denominator_ref=request.declared_denominator_ref,
        requested_cutoff_ref=request.requested_cutoff_ref,
        requested_query_context_ref=request.requested_query_context_ref,
        member_count=len(request.members),
        native_bytes_total=native_bytes_total,
        first_commitment=commitments[0] if commitments else None,
        commitment_head=commitments[-1] if commitments else genesis,
    )


class ExpectedCommitmentPrefix(_ChronologyModel):
    """Optional expected earlier prefix relative to the same proof domain."""

    domain: ChronologyProofDomain
    member_count: int = Field(ge=0)
    commitment_head: Digest


class FullPrefixBuildFailureCode(StrEnum):
    """Closed builder failure code set."""

    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"


class FullPrefixInvocationFailureCode(StrEnum):
    """Closed invocation failure code set."""

    BUNDLE_CONTENT_HASH_MISMATCH = "bundle_content_hash_mismatch"


class FullPrefixEnvelopeFailureCode(StrEnum):
    """Closed envelope failure code set."""

    BUNDLE_MALFORMED = "bundle_malformed"
    NON_CANONICAL_HEADER = "non_canonical_header"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNKNOWN_PROFILE = "unknown_profile"
    PROOF_DOMAIN_MISMATCH = "proof_domain_mismatch"
    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"


class FullPrefixMemberFailureCode(StrEnum):
    """Closed member failure code set."""

    NON_CANONICAL_MEMBER_FRAME = "non_canonical_member_frame"
    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"
    NATIVE_CONTENT_HASH_MISMATCH = "native_content_hash_mismatch"
    PREDECESSOR_MISMATCH = "predecessor_mismatch"
    ORDINAL_MISMATCH = "ordinal_mismatch"


class FullPrefixInternalConsistencyFailureCode(StrEnum):
    """Closed aggregate consistency failure code set."""

    MEMBER_COUNT_MISMATCH = "member_count_mismatch"
    NATIVE_BYTES_TOTAL_MISMATCH = "native_bytes_total_mismatch"
    FIRST_COMMITMENT_MISMATCH = "first_commitment_mismatch"
    COMMITMENT_HEAD_MISMATCH = "commitment_head_mismatch"


class FullPrefixExpectedPrefixFailureCode(StrEnum):
    """Closed expected-prefix failure code set."""

    DOMAIN_MISMATCH = "expected_prefix_domain_mismatch"
    OUT_OF_RANGE = "expected_prefix_out_of_range"
    HEAD_MISMATCH = "expected_prefix_head_mismatch"


class FullPrefixEvaluationState(_ChronologyModel):
    """Ordered evaluation state for every proof predicate."""

    bundle_content_hash: FullPrefixCheckState
    envelope: FullPrefixCheckState
    members: FullPrefixCheckState
    internal_consistency: FullPrefixCheckState
    expected_prefix: FullPrefixCheckState


class FullPrefixTerminalCheck(StrEnum):
    """One terminal stage for each discriminated verifier result."""

    VERIFIED = "verified"
    BUNDLE_CONTENT_HASH = "bundle_content_hash"
    ENVELOPE = "envelope"
    MEMBERS = "members"
    INTERNAL_CONSISTENCY = "internal_consistency"
    EXPECTED_PREFIX = "expected_prefix"


class FullPrefixInputMode(StrEnum):
    """Presence mode for optional verifier inputs."""

    ABSENT = "absent"
    PRESENT = "present"


@dataclass(frozen=True, slots=True)
class FullPrefixFailureDescriptor:
    """Unique operation/phase/code/terminal identity for one failure."""

    operation: Literal["verify"]
    phase: Literal["invocation", "envelope", "member", "consistency", "expected_prefix"]
    code: (
        FullPrefixInvocationFailureCode
        | FullPrefixEnvelopeFailureCode
        | FullPrefixMemberFailureCode
        | FullPrefixInternalConsistencyFailureCode
        | FullPrefixExpectedPrefixFailureCode
    )
    terminal_check: FullPrefixTerminalCheck


@dataclass(frozen=True, slots=True)
class FullPrefixEvaluationKey:
    """Result kind plus optional-input presence, the complete state-table key."""

    result_kind: Literal[
        "verified",
        "invocation_rejected",
        "envelope_rejected",
        "member_rejected",
        "internal_consistency_rejected",
        "expected_prefix_rejected",
    ]
    expected_bundle_hash: FullPrefixInputMode
    expected_prefix: FullPrefixInputMode


class EncodedChronologyBundle(_ChronologyModel):
    """Exact encoded bundle and derived proof identities."""

    result_kind: Literal["encoded"]
    bundle_bytes: bytes
    bundle_content_hash: Digest
    header: ChronologyBundleHeader
    member_commitments: tuple[Digest, ...]


class FullPrefixBuildRejected(_ChronologyModel):
    """Builder capacity rejection under the only v1 profile."""

    result_kind: Literal["build_rejected"]
    domain: ChronologyProofDomain
    requested_member_count: int = Field(ge=0)
    failure_code: FullPrefixBuildFailureCode


FullPrefixBuildResult = Annotated[
    EncodedChronologyBundle | FullPrefixBuildRejected,
    Field(discriminator="result_kind"),
]


class _FullPrefixResultShape(Protocol):
    @property
    def result_kind(
        self,
    ) -> Literal[
        "verified",
        "invocation_rejected",
        "envelope_rejected",
        "member_rejected",
        "internal_consistency_rejected",
        "expected_prefix_rejected",
    ]: ...

    @property
    def terminal_check(self) -> FullPrefixTerminalCheck: ...

    @property
    def evaluation_state(self) -> FullPrefixEvaluationState: ...


class _FullPrefixResultModel(_ChronologyModel):
    @model_validator(mode="after")
    def _closed_result_table(self) -> _FullPrefixResultModel:
        table = globals().get("FULL_PREFIX_EVALUATION_TABLE")
        terminals = globals().get("FULL_PREFIX_TERMINAL_BY_RESULT_KIND")
        if table is None or terminals is None:
            return self
        result = cast("_FullPrefixResultShape", self)
        state = result.evaluation_state
        key = FullPrefixEvaluationKey(
            result_kind=result.result_kind,
            expected_bundle_hash=(
                FullPrefixInputMode.ABSENT
                if state.bundle_content_hash == "not_requested"
                else FullPrefixInputMode.PRESENT
            ),
            expected_prefix=(
                FullPrefixInputMode.ABSENT
                if state.expected_prefix == "not_requested"
                else FullPrefixInputMode.PRESENT
            ),
        )
        expected = table.get(key)
        if expected is None or state != expected:
            raise ValueError("evaluation state is not a row in the closed table")
        if result.terminal_check != terminals[key.result_kind]:
            raise ValueError("terminal check does not match result kind")
        codes = getattr(self, "failure_codes", ())
        if len(codes) != len(set(codes)):
            raise ValueError("failure codes must be unique")
        if tuple(codes) != tuple(sorted(codes, key=lambda code: list(type(code)).index(code))):
            raise ValueError("failure codes must use enum declaration order")
        return self


class FullPrefixVerified(_FullPrefixResultModel):
    """Bytes reproduce one complete supplied prefix under the expected domain."""

    result_kind: Literal["verified"]
    status: Literal["verified"]
    terminal_check: Literal[FullPrefixTerminalCheck.VERIFIED]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    evaluation_state: FullPrefixEvaluationState

    @model_validator(mode="after")
    def _verified_matches_header(self) -> FullPrefixVerified:
        if self.verified_member_count != self.parsed_header.member_count:
            raise ValueError("verified member count differs from header")
        if self.commitment_head != self.parsed_header.commitment_head:
            raise ValueError("verified commitment head differs from header")
        return self


class FullPrefixInvocationRejected(_FullPrefixResultModel):
    """Expected bundle digest rejected before parsing."""

    result_kind: Literal["invocation_rejected"]
    status: Literal["rejected"]
    phase: Literal["invocation"]
    terminal_check: Literal[FullPrefixTerminalCheck.BUNDLE_CONTENT_HASH]
    bundle_content_hash: Digest
    parsed_header: None = None
    verified_member_count: Literal[0] = 0
    commitment_head: None = None
    failure_codes: Annotated[tuple[FullPrefixInvocationFailureCode, ...], Field(min_length=1)]
    evaluation_state: FullPrefixEvaluationState


class FullPrefixEnvelopeRejected(_FullPrefixResultModel):
    """Bundle envelope could not be safely admitted."""

    result_kind: Literal["envelope_rejected"]
    status: Literal["rejected"]
    phase: Literal["envelope"]
    terminal_check: Literal[FullPrefixTerminalCheck.ENVELOPE]
    bundle_content_hash: Digest
    parsed_header: None = None
    verified_member_count: Literal[0] = 0
    commitment_head: None = None
    failure_codes: Annotated[tuple[FullPrefixEnvelopeFailureCode, ...], Field(min_length=1)]
    evaluation_state: FullPrefixEvaluationState


class FullPrefixMemberRejected(_FullPrefixResultModel):
    """One member frame/native payload failed ordered verification."""

    result_kind: Literal["member_rejected"]
    status: Literal["rejected"]
    phase: Literal["member"]
    terminal_check: Literal[FullPrefixTerminalCheck.MEMBERS]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[tuple[FullPrefixMemberFailureCode, ...], Field(min_length=1)]
    evaluation_state: FullPrefixEvaluationState


class FullPrefixInternalConsistencyRejected(_FullPrefixResultModel):
    """All members parsed but header aggregates disagreed."""

    result_kind: Literal["internal_consistency_rejected"]
    status: Literal["rejected"]
    phase: Literal["consistency"]
    terminal_check: Literal[FullPrefixTerminalCheck.INTERNAL_CONSISTENCY]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[
        tuple[FullPrefixInternalConsistencyFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState


class FullPrefixExpectedPrefixRejected(_FullPrefixResultModel):
    """Verified bytes do not satisfy the supplied earlier prefix."""

    result_kind: Literal["expected_prefix_rejected"]
    status: Literal["rejected"]
    phase: Literal["expected_prefix"]
    terminal_check: Literal[FullPrefixTerminalCheck.EXPECTED_PREFIX]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[tuple[FullPrefixExpectedPrefixFailureCode, ...], Field(min_length=1)]
    evaluation_state: FullPrefixEvaluationState


FullPrefixRejected = Annotated[
    FullPrefixInvocationRejected
    | FullPrefixEnvelopeRejected
    | FullPrefixMemberRejected
    | FullPrefixInternalConsistencyRejected
    | FullPrefixExpectedPrefixRejected,
    Field(discriminator="result_kind"),
]
FullPrefixVerificationResult = Annotated[
    FullPrefixVerified
    | FullPrefixInvocationRejected
    | FullPrefixEnvelopeRejected
    | FullPrefixMemberRejected
    | FullPrefixInternalConsistencyRejected
    | FullPrefixExpectedPrefixRejected,
    Field(discriminator="result_kind"),
]


class FullPrefixVerificationStatement(_ChronologyModel):
    """Audit-only binding of verifier inputs and result, never a green predicate.

    Intermediate prefix membership cannot be re-proved from this compact DTO;
    every consumer must replay the real verifier over bundle bytes. The model
    rejects contradictions derivable from its own endpoints, but its presence
    or successful parsing does not establish verification.
    """

    schema_version: Literal["polisyos.chronology.full-prefix-verification-result.v1"]
    bundle_ref: ArtifactRef
    expected_domain: ChronologyProofDomain
    expected_prefix: ExpectedCommitmentPrefix | None
    expected_bundle_content_hash: Digest | None
    result: FullPrefixVerificationResult

    @model_validator(mode="after")
    def _bind_optional_inputs(self) -> FullPrefixVerificationStatement:
        state = self.result.evaluation_state
        hash_present = self.expected_bundle_content_hash is not None
        prefix_present = self.expected_prefix is not None
        if hash_present == (state.bundle_content_hash == "not_requested"):
            raise ValueError("expected bundle hash presence differs from evaluation state")
        if prefix_present == (state.expected_prefix == "not_requested"):
            raise ValueError("expected prefix presence differs from evaluation state")
        if (
            self.expected_bundle_content_hash is not None
            and self.expected_bundle_content_hash != self.result.bundle_content_hash
            and self.result.result_kind != "invocation_rejected"
        ):
            raise ValueError("non-invocation result has wrong bundle content hash")
        parsed_header = self.result.parsed_header
        if parsed_header is not None:
            parsed_domain = ChronologyProofDomain(
                format=parsed_header.format,
                profile=parsed_header.profile,
                proof_domain=parsed_header.proof_domain,
                family=parsed_header.family,
                scope_ref=parsed_header.scope_ref,
                authority_purpose=parsed_header.authority_purpose,
            )
            if parsed_domain != self.expected_domain:
                raise ValueError("verification result header differs from expected domain")
        if self.expected_prefix is not None and self.result.result_kind == "verified":
            if self.expected_prefix.domain != self.expected_domain:
                raise ValueError("verified expected prefix has a different proof domain")
            if self.expected_prefix.member_count > self.result.verified_member_count:
                raise ValueError("verified expected prefix is outside the verified range")
            if (
                self.expected_prefix.member_count == 0
                and self.expected_prefix.commitment_head != _domain_genesis(self.expected_domain)
            ):
                raise ValueError("verified zero prefix differs from domain genesis")
            if (
                self.expected_prefix.member_count == self.result.verified_member_count
                and self.expected_prefix.commitment_head != self.result.commitment_head
            ):
                raise ValueError("verified terminal prefix differs from commitment head")
        return self


class PersistedChronologyProof(_ChronologyModel):
    """Reloaded proof bundle and exact persisted verifier sidecar."""

    result_kind: Literal["persisted"]
    artifact_ref: ArtifactRef
    cas_raw_bytes_hash: Digest
    protocol_bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verifier_result_ref: ArtifactRef
    verifier_result_content_hash: Digest
    verification_statement: FullPrefixVerificationStatement


class ChronologyPersistenceManifestMismatch(_ChronologyModel):
    """First-writer manifest differs from the fixed chronology contract."""

    failure_kind: Literal["manifest_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    artifact_role: Literal["bundle", "verification_result"]
    artifact_ref: ArtifactRef
    expected_manifest_content_hash: Digest
    observed_manifest_content_hash: Digest


class ChronologyPersistenceVerificationMismatch(_ChronologyModel):
    """Real verifier rejected supplied or reloaded proof bytes."""

    failure_kind: Literal["verification_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    proof_result: FullPrefixRejected


class ChronologyPersistenceStoreIntegrityMismatch(_ChronologyModel):
    """Store returned present bytes whose CAS integrity mismatched."""

    failure_kind: Literal["store_integrity_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    artifact_role: Literal["bundle", "verification_result"]
    artifact_ref: ArtifactRef
    expected_raw_cas_hash: Digest
    observed_raw_cas_hash: Digest
    verification_report_content_hash: Digest


class ChronologyPersistenceNotEstablished(_ChronologyModel):
    """Mid-flight persistence evidence lost after reconciliation exists.

    The process-generation code in this leaf applies only after qualification
    has already constructed a native reconciliation. Entry into qualification
    under a dead generation uses the separate query-bound result arm below.
    """

    failure_kind: Literal["not_established"]
    disposition: Literal["not_established"]
    query: NativeChronologyQuery
    code: Literal[
        "artifact_store_not_established",
        "bundle_write_not_established",
        "verification_result_write_not_established",
        "persistence_process_generation_not_established",
    ]
    evidence_ref: ArtifactRef | None


ChronologyPersistenceFailure = Annotated[
    ChronologyPersistenceManifestMismatch
    | ChronologyPersistenceVerificationMismatch
    | ChronologyPersistenceStoreIntegrityMismatch
    | ChronologyPersistenceNotEstablished,
    Field(discriminator="failure_kind"),
]


class ChronologyProofPersistenceFailed(_ChronologyModel):
    """Discriminated failed persistence result."""

    result_kind: Literal["persistence_failed"]
    failure: ChronologyPersistenceFailure


ChronologyProofPersistenceResult = Annotated[
    PersistedChronologyProof | ChronologyProofPersistenceFailed,
    Field(discriminator="result_kind"),
]


class NativeChronologyOwnerContext(_ChronologyModel):
    """Full query, owner-qualified candidate and exact policy admission bytes."""

    query: NativeChronologyQuery
    owner_qualified_candidate: OwnerQualifiedNativeCandidate
    policy_admission_ref: ArtifactRef
    policy_admission_content_hash: Digest
    predicate_admission_policy_ref: ArtifactRef
    predicate_admission_policy_content_hash: Digest

    @model_validator(mode="after")
    def _same_query(self) -> NativeChronologyOwnerContext:
        if self.owner_qualified_candidate.candidate.query != self.query:
            raise ValueError("owner context query differs from qualified candidate")
        return self


class NativeChronologyReconciliation(_ChronologyModel):
    """Completed family reconciliation before projection/persistence."""

    owner_context: NativeChronologyOwnerContext
    authoritative_native_schema_profile: str = Field(min_length=1)
    applicable_predicate_denominator: PersistedApplicablePredicateDenominator

    @model_validator(mode="after")
    def _profile_matches_members(self) -> NativeChronologyReconciliation:
        candidate = self.owner_context.owner_qualified_candidate.candidate
        if any(
            member.native_schema_profile != self.authoritative_native_schema_profile
            for member in candidate.ordered_members
        ):
            raise ValueError("reconciliation profile differs from a member profile")
        return self


class NativeChronologyQualified(_ChronologyModel):
    """Qualified native candidate with verified and reloaded persisted proof."""

    result_kind: Literal["qualified"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixVerified
    persisted_proof: PersistedChronologyProof


class NativeFullPrefixBuildRejected(_ChronologyModel):
    """Profile-capacity failure after positive owner reconciliation."""

    result_kind: Literal["build_rejected"]
    reconciliation: NativeChronologyReconciliation
    build_result: FullPrefixBuildRejected


class NativeSchemaProfileRejected(_ChronologyModel):
    """Candidate member profiles differ from the owner-selected profile."""

    result_kind: Literal["profile_rejected"]
    code: Literal["native_schema_profile_mismatch"]
    owner_context: NativeChronologyOwnerContext
    expected_profile: str
    observed_profiles: tuple[str, ...]

    @model_validator(mode="after")
    def _is_mismatch(self) -> NativeSchemaProfileRejected:
        if self.observed_profiles and set(self.observed_profiles) == {self.expected_profile}:
            raise ValueError("profile rejection requires an actual mismatch")
        return self


class NativePredicateRejected(_ChronologyModel):
    """Applicable owner predicate denominator was not authority-positive."""

    result_kind: Literal["predicate_rejected"]
    code: Literal["native_predicate_inadmissible"]
    owner_context: NativeChronologyOwnerContext
    evidence_refs: tuple[ArtifactRef, ...]


class NativeFullPrefixProofRejected(_ChronologyModel):
    """Real common verifier rejected the built native prefix."""

    result_kind: Literal["proof_rejected"]
    code: Literal["full_prefix_proof_rejected"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixRejected


type NativeChronologyCandidateRejected = (
    NativeSchemaProfileRejected | NativePredicateRejected | NativeFullPrefixProofRejected
)


class NativeExteriorNotEstablished(_ChronologyModel):
    """Verified prefix with an owner-reported exterior limitation."""

    result_kind: Literal["native_exterior_not_established"]
    code: Literal["native_exterior_not_established"]
    reconciliation: NativeChronologyReconciliation
    exterior_limitation_code: str = Field(min_length=1)
    proof_result: FullPrefixVerified


class NativeAuthorityHeadNotEstablished(_ChronologyModel):
    """Verified prefix whose family requires but lacks a native authority head."""

    result_kind: Literal["native_authority_head_not_established"]
    code: Literal["native_authority_head_not_established"]
    reconciliation: NativeChronologyReconciliation
    required_native_head_role: str = Field(min_length=1)
    proof_result: FullPrefixVerified


class NativeExteriorAndAuthorityHeadNotEstablished(_ChronologyModel):
    """Preserve simultaneous exterior and required-native-head limitations."""

    result_kind: Literal["native_exterior_and_authority_head_not_established"]
    reconciliation: NativeChronologyReconciliation
    exterior_limitation_code: str = Field(min_length=1)
    required_native_head_role: str = Field(min_length=1)
    proof_result: FullPrefixVerified


class NativeProjectionCustodyGap(_ChronologyModel):
    """Verified native terminal lacks its family projection custody receipt."""

    result_kind: Literal["projection_custody_gap"]
    status: Literal["native_not_established"]
    code: Literal["native_projection_custody_gap"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixVerified
    missing_projection_receipt_role: Literal["native_projection_receipt"]


class NativeQualificationProcessGenerationNotEstablished(_ChronologyModel):
    """Qualification entry refused before any owner dependency is accessed.

    This query-bound terminal is distinct from
    ``persistence_process_generation_not_established``: the latter is a
    mid-flight persistence failure and therefore requires a completed native
    reconciliation, while this arm must not construct one.
    """

    result_kind: Literal["qualification_process_generation_not_established"]
    status: Literal["not_established"]
    code: Literal["qualification_process_generation_not_established"]
    query: NativeChronologyQuery


class NativeChronologyPolicyResolutionFailed(_ChronologyModel):
    """Query-bound failure before an owner-qualified candidate exists."""

    result_kind: Literal["policy_resolution_failed"]
    query: NativeChronologyQuery
    failure: PredicatePolicyResolutionFailure | PredicatePolicyOwnerRelationFailure

    @model_validator(mode="after")
    def _same_query_context(self) -> NativeChronologyPolicyResolutionFailed:
        if self.failure.requested_query_context_ref != self.query.requested_query_context_ref:
            raise ValueError("policy failure carries a different query coordinate")
        return self


class NativeApplicablePredicateDenominatorPersistenceFailed(_ChronologyModel):
    """Owner-qualified candidate whose denominator artifact was not established."""

    result_kind: Literal["predicate_denominator_persistence_failed"]
    owner_context: NativeChronologyOwnerContext
    failure: ApplicablePredicateDenominatorArtifactFailure

    @model_validator(mode="after")
    def _same_query(self) -> NativeApplicablePredicateDenominatorPersistenceFailed:
        if self.failure.query != self.owner_context.query:
            raise ValueError("denominator persistence failure has a different query")
        return self


class NativeChronologyPersistenceFailed(_ChronologyModel):
    """Post-projection common persistence failure after reconciliation."""

    result_kind: Literal["persistence_failed"]
    reconciliation: NativeChronologyReconciliation
    failure: ChronologyPersistenceFailure

    @model_validator(mode="after")
    def _same_query(self) -> NativeChronologyPersistenceFailed:
        if self.failure.query != self.reconciliation.owner_context.query:
            raise ValueError("persistence failure has a different query")
        return self


NativeChronologyQualificationResult = Annotated[
    NativeChronologyQualified
    | NativeFullPrefixBuildRejected
    | NativeSchemaProfileRejected
    | NativePredicateRejected
    | NativeFullPrefixProofRejected
    | NativeExteriorNotEstablished
    | NativeAuthorityHeadNotEstablished
    | NativeExteriorAndAuthorityHeadNotEstablished
    | NativeProjectionCustodyGap
    | NativeQualificationProcessGenerationNotEstablished
    | NativeChronologyPolicyResolutionFailed
    | NativeApplicablePredicateDenominatorPersistenceFailed
    | NativeChronologyPersistenceFailed,
    Field(discriminator="result_kind"),
]


def _policy_admission_content_hash(statement: PredicatePolicyAdmissionStatement) -> Digest:
    raw = _canonical_raw_bytes(_raw_model_mapping(statement))
    return _sha256_digest(_POLICY_ADMISSION_PREFIX, _frame_record(raw))


def _predicate_policy_content_hash(statement: PredicateAdmissionPolicyStatement) -> Digest:
    raw = _canonical_raw_bytes(_raw_model_mapping(statement))
    return _sha256_digest(_POLICY_PREFIX, _frame_record(raw))


def _denominator_content_hash(
    statement: ApplicablePredicateDenominatorStatement,
) -> Digest:
    raw = _canonical_raw_bytes(_raw_model_mapping(statement))
    return _sha256_digest(_DENOMINATOR_PREFIX, _frame_record(raw))


def _verification_statement_content_hash(
    statement: FullPrefixVerificationStatement,
) -> Digest:
    raw = _canonical_raw_bytes(_raw_model_mapping(statement))
    return _sha256_digest(_VERIFICATION_RESULT_PREFIX, _frame_record(raw))


def _profile_capacity_failure(
    *,
    domain: ChronologyProofDomain,
    member_count: int,
    header_frame_bytes: int,
    member_frame_bytes: tuple[int, ...],
    native_frame_bytes: tuple[int, ...],
) -> FullPrefixBuildRejected | None:
    """Evaluate the exact numeric v1 caps without allocating cap-sized payloads."""
    exceeds = (
        member_count > FULL_PREFIX_MAX_MEMBERS
        or header_frame_bytes > FULL_PREFIX_MAX_HEADER_FRAME_BYTES
        or any(size > FULL_PREFIX_MAX_MEMBER_FRAME_BYTES for size in member_frame_bytes)
        or header_frame_bytes + sum(member_frame_bytes) + sum(native_frame_bytes)
        > FULL_PREFIX_MAX_BUNDLE_BYTES
    )
    if not exceeds:
        return None
    return FullPrefixBuildRejected(
        result_kind="build_rejected",
        domain=domain,
        requested_member_count=member_count,
        failure_code=FullPrefixBuildFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
    )


def _evaluation_state(
    result_kind: str,
    *,
    expected_bundle_hash: FullPrefixInputMode,
    expected_prefix: FullPrefixInputMode,
) -> FullPrefixEvaluationState:
    hash_state: FullPrefixCheckState = (
        "not_requested" if expected_bundle_hash is FullPrefixInputMode.ABSENT else "satisfied"
    )
    later_prefix: FullPrefixCheckState = (
        "not_requested" if expected_prefix is FullPrefixInputMode.ABSENT else "not_evaluated"
    )
    if result_kind == "invocation_rejected":
        return FullPrefixEvaluationState(
            bundle_content_hash="rejected",
            envelope="not_evaluated",
            members="not_evaluated",
            internal_consistency="not_evaluated",
            expected_prefix=later_prefix,
        )
    if result_kind == "envelope_rejected":
        return FullPrefixEvaluationState(
            bundle_content_hash=hash_state,
            envelope="rejected",
            members="not_evaluated",
            internal_consistency="not_evaluated",
            expected_prefix=later_prefix,
        )
    if result_kind == "member_rejected":
        return FullPrefixEvaluationState(
            bundle_content_hash=hash_state,
            envelope="satisfied",
            members="rejected",
            internal_consistency="not_evaluated",
            expected_prefix=later_prefix,
        )
    if result_kind == "internal_consistency_rejected":
        return FullPrefixEvaluationState(
            bundle_content_hash=hash_state,
            envelope="satisfied",
            members="satisfied",
            internal_consistency="rejected",
            expected_prefix=later_prefix,
        )
    if result_kind == "expected_prefix_rejected":
        return FullPrefixEvaluationState(
            bundle_content_hash=hash_state,
            envelope="satisfied",
            members="satisfied",
            internal_consistency="satisfied",
            expected_prefix="rejected",
        )
    if result_kind == "verified":
        return FullPrefixEvaluationState(
            bundle_content_hash=hash_state,
            envelope="satisfied",
            members="satisfied",
            internal_consistency="satisfied",
            expected_prefix=(
                "not_requested" if expected_prefix is FullPrefixInputMode.ABSENT else "satisfied"
            ),
        )
    raise ValueError(f"unknown full-prefix result kind: {result_kind}")


FULL_PREFIX_FAILURE_DESCRIPTORS: tuple[FullPrefixFailureDescriptor, ...] = (
    *(
        FullPrefixFailureDescriptor(
            "verify", "invocation", code, FullPrefixTerminalCheck.BUNDLE_CONTENT_HASH
        )
        for code in FullPrefixInvocationFailureCode
    ),
    *(
        FullPrefixFailureDescriptor("verify", "envelope", code, FullPrefixTerminalCheck.ENVELOPE)
        for code in FullPrefixEnvelopeFailureCode
    ),
    *(
        FullPrefixFailureDescriptor("verify", "member", code, FullPrefixTerminalCheck.MEMBERS)
        for code in FullPrefixMemberFailureCode
    ),
    *(
        FullPrefixFailureDescriptor(
            "verify",
            "consistency",
            code,
            FullPrefixTerminalCheck.INTERNAL_CONSISTENCY,
        )
        for code in FullPrefixInternalConsistencyFailureCode
    ),
    *(
        FullPrefixFailureDescriptor(
            "verify",
            "expected_prefix",
            code,
            FullPrefixTerminalCheck.EXPECTED_PREFIX,
        )
        for code in FullPrefixExpectedPrefixFailureCode
    ),
)

FULL_PREFIX_TERMINAL_BY_RESULT_KIND: Mapping[str, FullPrefixTerminalCheck] = MappingProxyType(
    {
        "verified": FullPrefixTerminalCheck.VERIFIED,
        "invocation_rejected": FullPrefixTerminalCheck.BUNDLE_CONTENT_HASH,
        "envelope_rejected": FullPrefixTerminalCheck.ENVELOPE,
        "member_rejected": FullPrefixTerminalCheck.MEMBERS,
        "internal_consistency_rejected": FullPrefixTerminalCheck.INTERNAL_CONSISTENCY,
        "expected_prefix_rejected": FullPrefixTerminalCheck.EXPECTED_PREFIX,
    }
)


def _build_evaluation_table() -> Mapping[FullPrefixEvaluationKey, FullPrefixEvaluationState]:
    rows: dict[FullPrefixEvaluationKey, FullPrefixEvaluationState] = {}
    for kind in FULL_PREFIX_TERMINAL_BY_RESULT_KIND:
        for hash_mode in FullPrefixInputMode:
            for prefix_mode in FullPrefixInputMode:
                if kind == "invocation_rejected" and hash_mode is FullPrefixInputMode.ABSENT:
                    continue
                if kind == "expected_prefix_rejected" and prefix_mode is FullPrefixInputMode.ABSENT:
                    continue
                rows[
                    FullPrefixEvaluationKey(kind, hash_mode, prefix_mode)  # type: ignore[arg-type]
                ] = _evaluation_state(
                    kind,
                    expected_bundle_hash=hash_mode,
                    expected_prefix=prefix_mode,
                )
    return MappingProxyType(rows)


FULL_PREFIX_EVALUATION_TABLE = _build_evaluation_table()


CHRONOLOGY_WIRE_MODELS: tuple[type[BaseModel], ...] = tuple(
    value
    for value in list(globals().values())
    if isinstance(value, type)
    and issubclass(value, _ChronologyModel)
    and value not in {_ChronologyModel, _FullPrefixResultModel}
)
for _wire_model in CHRONOLOGY_WIRE_MODELS:
    _wire_model.model_rebuild(force=True)


__all__ = [
    "CHRONOLOGY_CANON_SPEC",
    "CHRONOLOGY_WIRE_MODELS",
    "FULL_PREFIX_EVALUATION_TABLE",
    "FULL_PREFIX_FAILURE_DESCRIPTORS",
    "FULL_PREFIX_FORMAT",
    "FULL_PREFIX_MAX_BUNDLE_BYTES",
    "FULL_PREFIX_MAX_HEADER_FRAME_BYTES",
    "FULL_PREFIX_MAX_MEMBERS",
    "FULL_PREFIX_MAX_MEMBER_FRAME_BYTES",
    "FULL_PREFIX_PROFILE",
    "FULL_PREFIX_TERMINAL_BY_RESULT_KIND",
    "ApplicablePredicateDenominatorArtifactFailure",
    "ApplicablePredicateDenominatorStatement",
    "ChronologyApplicablePredicateDenominatorArtifacts",
    "ChronologyBundleHeader",
    "ChronologyBundleRequest",
    "ChronologyMemberInput",
    "ChronologyPersistenceFailure",
    "ChronologyPersistenceManifestMismatch",
    "ChronologyPersistenceNotEstablished",
    "ChronologyPersistenceStoreIntegrityMismatch",
    "ChronologyPersistenceVerificationMismatch",
    "ChronologyPredicatePolicyArtifacts",
    "ChronologyProofDomain",
    "ChronologyProofPersistenceFailed",
    "ChronologyProofPersistenceResult",
    "Digest",
    "EncodedChronologyBundle",
    "ExpectedCommitmentPrefix",
    "FullPrefixBuildFailureCode",
    "FullPrefixBuildRejected",
    "FullPrefixBuildResult",
    "FullPrefixCheckState",
    "FullPrefixEnvelopeFailureCode",
    "FullPrefixEnvelopeRejected",
    "FullPrefixEvaluationKey",
    "FullPrefixEvaluationState",
    "FullPrefixExpectedPrefixFailureCode",
    "FullPrefixExpectedPrefixRejected",
    "FullPrefixFailureDescriptor",
    "FullPrefixInputMode",
    "FullPrefixInternalConsistencyFailureCode",
    "FullPrefixInternalConsistencyRejected",
    "FullPrefixInvocationFailureCode",
    "FullPrefixInvocationRejected",
    "FullPrefixMemberFailureCode",
    "FullPrefixMemberRejected",
    "FullPrefixRejected",
    "FullPrefixTerminalCheck",
    "FullPrefixVerificationResult",
    "FullPrefixVerificationStatement",
    "FullPrefixVerified",
    "MemberPredicateDisposition",
    "NativeApplicablePredicateDenominatorPersistenceFailed",
    "NativeAuthorityHeadNotEstablished",
    "NativeChronologyCandidate",
    "NativeChronologyCandidateRejected",
    "NativeChronologyOwnerContext",
    "NativeChronologyPersistenceFailed",
    "NativeChronologyPolicyResolutionFailed",
    "NativeChronologyQualificationResult",
    "NativeChronologyQualified",
    "NativeChronologyQuery",
    "NativeChronologyReconciliation",
    "NativeExteriorAndAuthorityHeadNotEstablished",
    "NativeExteriorNotEstablished",
    "NativeFullPrefixBuildRejected",
    "NativeFullPrefixProofRejected",
    "NativePredicateRejected",
    "NativeProjectionCustodyGap",
    "NativeSchemaProfileRejected",
    "OwnerQualifiedNativeCandidate",
    "PersistedApplicablePredicateDenominator",
    "PersistedChronologyProof",
    "PersistedPredicateAdmissionPolicy",
    "PersistedPredicatePolicyAdmission",
    "PolicyAdmissionAmbiguousFailure",
    "PolicyAdmissionMissingFailure",
    "PolicyBindingMismatchFailure",
    "PolicyBytesMissingFailure",
    "PolicyOwnerDenominatorMismatchFailure",
    "PolicyOwnerRelationNotEstablished",
    "PolicyOwnerRelationRejected",
    "PolicyQueryBindingMismatchFailure",
    "PredicateAdmissionPolicyStatement",
    "PredicateAdmissionRule",
    "PredicateClass",
    "PredicateDisposition",
    "PredicatePolicyAdmissionIndex",
    "PredicatePolicyAdmissionStatement",
    "PredicatePolicyOwnerProvenanceVerifier",
    "PredicatePolicyOwnerRelationFailure",
    "PredicatePolicyResolutionContext",
    "PredicatePolicyResolutionFailure",
    "PredicatePolicySelectionKey",
    "QueryPredicateDisposition",
    "ResolvedPredicatePolicyAdmission",
    "VerifiedNativeMemberIdentity",
    "VerifiedNativeSubjectIdentity",
    "VerifiedOwnerPredicateEvidence",
    "VerifiedPolicyOwnerProvenance",
    "VerifiedPredicatePolicyOwnerRelation",
]
