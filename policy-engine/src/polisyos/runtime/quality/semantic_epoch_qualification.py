"""Recompute epoch-native predicates under an exact signed policy relation.

This owner defines native verification operations, not their appointment. The
signed admission commits the relation and its complete predicate mapping; an
empty deployment supplies no policy authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, contracts, security
from polisyos.runtime.quality.epoch_deployment import (
    EpochDeployment,
    EpochDeploymentConfig,
    build_epoch_deployment,
)
from polisyos.runtime.quality.semantic_epoch import (
    EpochHistoryEntry,
    EpochScopeIdentity,
    SemanticEpochManifest,
    _history_view_bytes,
)
from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository

contract = contracts.chronology


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EpochNativePredicateBinding(_Model):
    """A signed owner relation maps policy names to recomputable native meanings."""

    predicate_id: str = Field(min_length=1)
    semantic_property: Literal["member_manifest_binding", "ancestry_denominator", "query_binding"]

    @property
    def subject_kind(self) -> Literal["member", "query"]:
        """Return the native subject required by this operation."""
        return "member" if self.semantic_property == "member_manifest_binding" else "query"


class SemanticEpochChronologyOwnerRelation(_Model):
    """Exact native basis committed by a separately signed policy admission."""

    schema_version: Literal["polisyos.epoch.chronology-owner-relation.v1"]
    query: contract.NativeChronologyQuery
    policy_ref: artifacts.ArtifactRef
    policy_content_hash: contract.Digest
    native_denominator_ref: artifacts.ArtifactRef
    predicate_bindings: tuple[EpochNativePredicateBinding, ...]

    @model_validator(mode="after")
    def _complete_native_basis(self) -> SemanticEpochChronologyOwnerRelation:
        if (
            self.query.domain.family != "epoch"
            or self.query.domain.proof_domain != "semantic_epoch"
            or len(self.predicate_bindings) != 3
            or {row.semantic_property for row in self.predicate_bindings}
            != {"member_manifest_binding", "ancestry_denominator", "query_binding"}
            or len({(row.subject_kind, row.predicate_id) for row in self.predicate_bindings}) != 3
        ):
            raise ValueError("epoch native relation has an incomplete or foreign predicate basis")
        return self


class _HistoryStatement(_Model):
    schema_version: Literal["polisyos.epoch.scope-history.v1"]
    scope: EpochScopeIdentity
    authority_purpose: str
    entries: tuple[EpochHistoryEntry, ...]
    head_refs: tuple[contract.Digest, ...]


@dataclass(frozen=True, slots=True)
class SemanticEpochNativePolicyOwner:
    """Concrete native producer/verifier using captured public trust and history."""

    deployment: EpochDeployment

    def __post_init__(self) -> None:
        if type(self.deployment) is not EpochDeployment:
            raise TypeError("native epoch policy requires a captured deployment")
        self.deployment.attestation_state()

    @property
    def _store(self) -> artifacts.ArtifactStore:
        store = self.deployment._runtime_artifact_store()
        if store is None:
            raise ValueError("epoch native evidence store absent")
        return store

    def _put(self, value: BaseModel | dict[str, object], kind: str) -> artifacts.ArtifactRef:
        raw = (
            security.canonical_statement_bytes(value)
            if isinstance(value, BaseModel)
            else contract._frame_record(contract._canonical_raw_bytes(value))
        )
        ref = self._store.put_bytes(
            raw, artifacts.ArtifactWriteOptions(kind=kind, media_type="application/octet-stream")
        )
        if self.deployment._runtime_repository().read_raw(artifact_ref=ref) != raw:
            raise ValueError("native predicate custody readback differs")
        return ref

    @property
    def projection_verifier_provenance_ref(self) -> artifacts.ArtifactRef:
        """Persist the actual verifier operation and its bounded native meanings."""
        return self._put(
            {
                "schema_version": "polisyos.epoch.native-verifier.v1",
                "operation": "SemanticEpochNativePolicyOwner.verify_owner_relation",
                "properties": ["member_manifest_binding", "ancestry_denominator", "query_binding"],
            },
            "epoch.native_verifier_provenance",
        )

    @property
    def projection_verifier_provenance_content_hash(self) -> contract.Digest:
        """Return exact verifier provenance bytes identity."""
        return str(self.projection_verifier_provenance_ref.artifact_id)

    def _admissions(
        self,
    ) -> tuple[
        tuple[
            contract.PredicatePolicyAdmissionStatement,
            contract.SignedArtifactEvidenceRecord,
            contract.SignedArtifactEvidence,
        ],
        ...,
    ]:
        self.deployment.attestation_state()
        return tuple(
            self.deployment._signed_model(
                ref, contract.PredicatePolicyAdmissionStatement, "predicate_policy_admission"
            )
            for ref in self.deployment._state().config.predicate_policy_admission_refs
        )

    @property
    def native_schema_profile(self) -> str:
        """Read the single epoch-native profile from verified owner admissions."""
        profiles = {
            row.native_schema_profile
            for row, _, _ in self._admissions()
            if row.key.family == "epoch" and row.key.proof_domain == "semantic_epoch"
        }
        if len(profiles) != 1:
            raise ValueError("epoch native schema profile missing or ambiguous")
        return profiles.pop()

    def _resolve(
        self, query: contract.NativeChronologyQuery
    ) -> tuple[
        contract.PredicatePolicyAdmissionStatement,
        contract.PersistedPredicateAdmissionPolicy,
        SemanticEpochChronologyOwnerRelation,
        contract.SignedArtifactEvidenceRecord,
        contract.SignedArtifactEvidence,
    ]:
        matches = [
            (admission, record, evidence)
            for admission, record, evidence in self._admissions()
            if admission.key
            == contract.PredicatePolicySelectionKey(
                family=query.domain.family,
                proof_domain=query.domain.proof_domain,
                scope_ref=query.domain.scope_ref,
                authority_purpose=query.domain.authority_purpose,
                requested_cutoff_ref=query.requested_cutoff_ref,
            )
        ]
        if len(matches) != 1:
            raise ValueError("epoch native admission missing or ambiguous")
        admission, record, evidence = matches[0]
        policy_statement = self.deployment._read_model(
            admission.policy_ref, contract.PredicateAdmissionPolicyStatement
        )
        policy = contract.PersistedPredicateAdmissionPolicy(
            policy_ref=admission.policy_ref,
            policy_content_hash=admission.policy_content_hash,
            statement=policy_statement,
        )
        relation_raw = self.deployment._repository().read_raw(
            artifact_ref=admission.owner_relation_ref
        )
        if security.raw_content_hash(relation_raw) != admission.owner_relation_content_hash:
            raise ValueError("native owner relation bytes differ from signed admission")
        relation = security.parse_canonical_statement(
            relation_raw, SemanticEpochChronologyOwnerRelation
        )
        if (
            relation.query != query
            or admission.requested_query_context_ref != query.requested_query_context_ref
            or relation.policy_ref != policy.policy_ref
            or relation.policy_content_hash != policy.policy_content_hash
            or policy.statement.key != admission.key
            or policy.statement.native_schema_profile != admission.native_schema_profile
            or {(r.subject_kind, r.predicate_id) for r in policy.statement.rules}
            != {(r.subject_kind, r.predicate_id) for r in relation.predicate_bindings}
        ):
            raise ValueError("native predicate mapping differs from admitted policy")
        return admission, policy, relation, record, evidence

    def _native(
        self, query: contract.NativeChronologyQuery
    ) -> tuple[
        contract.PredicatePolicyAdmissionStatement,
        contract.PersistedPredicateAdmissionPolicy,
        SemanticEpochChronologyOwnerRelation,
        contract.SignedArtifactEvidenceRecord,
        contract.SignedArtifactEvidence,
        _HistoryStatement,
        contract.NativeChronologyCandidate,
        tuple[contract.VerifiedOwnerPredicateEvidence, ...],
    ]:
        admission, policy, relation, record, evidence = self._resolve(query)
        if (
            relation.native_denominator_ref.kind != "epoch.scope_history"
            or relation.native_denominator_ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("native denominator source profile differs")
        raw = self.deployment._runtime_repository().read_raw(
            artifact_ref=relation.native_denominator_ref
        )
        history = _HistoryStatement.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self._store,
                ref=relation.native_denominator_ref,
                expected_kind="epoch.scope_history",
            )
        )
        if raw != _history_view_bytes(
            scope=history.scope,
            authority_purpose=history.authority_purpose,
            entries=history.entries,
            head_refs=history.head_refs,
        ):
            raise ValueError("native history differs from its producer's canonical bytes")
        if (
            history.scope.scope_identity_ref != query.domain.scope_ref
            or history.authority_purpose != query.domain.authority_purpose
            or history.head_refs != (query.requested_cutoff_ref,)
        ):
            raise ValueError("native history scope, purpose or head differs")
        by_ref = {row.epoch_ref: row for row in history.entries}
        if len(by_ref) != len(history.entries):
            raise ValueError("duplicate native history member")
        selected: set[str] = set()
        visiting: set[str] = set()

        def visit(ref: str) -> None:
            if ref in selected:
                return
            if ref in visiting or ref not in by_ref:
                raise ValueError("native epoch ancestry cyclic or dangling")
            visiting.add(ref)
            for predecessor in by_ref[ref].predecessor_refs:
                visit(predecessor)
            visiting.remove(ref)
            selected.add(ref)

        visit(query.requested_cutoff_ref)
        if selected != set(by_ref):
            raise ValueError("native denominator is not exactly the requested ancestry")
        history_root = self.deployment._state().config.native_epoch_history_root
        if history_root is None:
            raise ValueError("canonical native epoch history owner absent")
        repository = FileSemanticEpochHistoryRepository(root=history_root, artifacts=self._store)
        current = repository.resolve_scope_history(
            scope=history.scope, authority_purpose=history.authority_purpose
        )
        current_by_ref = {row.epoch_ref: row for row in current.entries}
        prospective = query.requested_cutoff_ref not in current_by_ref
        terminal = by_ref[query.requested_cutoff_ref]
        if prospective and terminal.predecessor_refs != current.head_refs:
            raise ValueError("prospective epoch does not extend current owner heads")
        expected = tuple(row for row in current.entries if row.epoch_ref in selected)
        if prospective:
            expected = (*expected, terminal)
        if history.entries != expected:
            raise ValueError("native denominator differs from canonical owner history")
        members = []
        for row in history.entries:
            member_raw = self.deployment._runtime_repository().read_raw(
                artifact_ref=row.native_member_ref
            )
            manifest = security.parse_canonical_statement(member_raw, SemanticEpochManifest)
            if (
                row.native_member_ref != row.manifest_ref
                or row.native_member_ref.kind != "epoch.semantic_manifest"
                or security.raw_content_hash(member_raw) != row.native_member_content_hash
                or manifest.epoch_ref != row.epoch_ref
                or manifest.manifest_content_hash != row.manifest_content_hash
                or manifest.predecessor_refs != row.predecessor_refs
                or manifest.scope_identity != history.scope
                or manifest.authority_purpose != query.domain.authority_purpose
            ):
                raise ValueError("native epoch member does not bind its semantic manifest")
            if (
                row.epoch_ref == query.requested_cutoff_ref
                and manifest.requested_query_context_ref != query.requested_query_context_ref
            ):
                raise ValueError("terminal epoch query context differs")
            members.append(
                contract.ChronologyMemberInput(
                    member_ref=row.epoch_ref,
                    native_artifact_ref=row.native_member_ref,
                    native_content_hash=contract._native_content_hash(member_raw),
                    native_schema_profile=policy.statement.native_schema_profile,
                    native_bytes=member_raw,
                    member_admission_basis_ref=security.raw_content_hash(raw),
                    member_admission_context_ref=query.requested_query_context_ref,
                )
            )
        context_raw = security.canonical_statement_bytes(query)
        context_ref = self._store.put_bytes(
            context_raw,
            artifacts.ArtifactWriteOptions(
                kind="epoch.chronology_query_context",
                media_type="application/vnd.polisyos.chronology-query+json",
            ),
        )
        if self.deployment._runtime_repository().read_raw(artifact_ref=context_ref) != context_raw:
            raise ValueError("native query custody differs")
        member_predicates = []
        query_predicates = []
        predicate_evidence = []
        provenance_ref = self.projection_verifier_provenance_ref
        for binding in relation.predicate_bindings:
            subjects = (
                tuple(member.member_ref for member in members)
                if binding.subject_kind == "member"
                else (query.requested_query_context_ref,)
            )
            for subject in subjects:
                evidence_ref = self._put(
                    {
                        "schema_version": "polisyos.epoch.native-predicate.v1",
                        "query": contract._raw_model_mapping(query),
                        "subject_kind": binding.subject_kind,
                        "subject_ref": subject,
                        "predicate_id": binding.predicate_id,
                        "semantic_property": binding.semantic_property,
                        "native_denominator_ref": contract._raw_model_mapping(
                            relation.native_denominator_ref
                        ),
                        "verifier_provenance_ref": contract._raw_model_mapping(provenance_ref),
                    },
                    "epoch.native_predicate_evidence",
                )
                disposition = contract.PredicateDisposition(
                    predicate_id=binding.predicate_id,
                    predicate_class="recomputed",
                    status="satisfied",
                    evidence_ref=evidence_ref,
                    failure_code=None,
                )
                if binding.subject_kind == "member":
                    member_predicates.append(
                        contract.MemberPredicateDisposition(
                            member_ref=subject, disposition=disposition
                        )
                    )
                else:
                    query_predicates.append(
                        contract.QueryPredicateDisposition(
                            requested_query_context_ref=subject, disposition=disposition
                        )
                    )
                predicate_evidence.append(
                    contract.VerifiedOwnerPredicateEvidence(
                        subject_kind=binding.subject_kind,
                        subject_ref=subject,
                        predicate_id=binding.predicate_id,
                        predicate_class="recomputed",
                        status="satisfied",
                        evidence_ref=evidence_ref,
                        evidence_content_hash=str(evidence_ref.artifact_id),
                        evidence_verifier_provenance_ref=provenance_ref,
                    )
                )
        candidate = contract.NativeChronologyCandidate(
            query=query,
            declared_denominator_ref=security.raw_content_hash(raw),
            native_denominator_artifact_ref=relation.native_denominator_ref,
            native_denominator_content_hash=security.raw_content_hash(raw),
            query_context_artifact_ref=context_ref,
            query_context_content_hash=contract._sha256_digest(
                b"polisyos.epoch.chronology-query-context.v1\0", context_raw
            ),
            ordered_members=tuple(members),
            member_predicates=tuple(member_predicates),
            query_predicates=tuple(query_predicates),
            exterior_limitation_code=None,
            native_authority_head_refs=history.head_refs,
        )
        return (
            admission,
            policy,
            relation,
            record,
            evidence,
            history,
            candidate,
            tuple(predicate_evidence),
        )

    def member_predicates(
        self, *, query: contract.NativeChronologyQuery, entries: tuple[EpochHistoryEntry, ...]
    ) -> tuple[contract.MemberPredicateDisposition, ...]:
        """Recompute member predicates from the signed native basis and owner history."""
        *_, history, candidate, _evidence = self._native(query)
        if entries != history.entries:
            raise ValueError("adapter epoch entries differ from canonical native denominator")
        return candidate.member_predicates

    def query_predicates(
        self, *, query: contract.NativeChronologyQuery
    ) -> tuple[contract.QueryPredicateDisposition, ...]:
        """Recompute native ancestry and query predicates under the admitted mapping."""
        return self._native(query)[6].query_predicates

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
        """Independently reload canonical native truth before returning verified evidence."""
        failure = contract.PolicyOwnerRelationNotEstablished(
            code="policy_owner_relation_not_established",
            status="not_established",
            key=admission.key,
            requested_query_context_ref=query.requested_query_context_ref,
            owner_relation_ref=admission.owner_relation_ref,
        )
        try:
            (
                expected_admission,
                expected_policy,
                _relation,
                _record,
                signed,
                _history,
                expected,
                evidence,
            ) = self._native(query)
            if (
                admission != expected_admission
                or policy != expected_policy
                or candidate != expected
                or self.deployment._repository().read_raw(artifact_ref=admission.owner_relation_ref)
                != owner_relation_bytes
                or self.deployment._repository().read_raw(
                    artifact_ref=policy.statement.owner_provenance_ref
                )
                != policy_owner_provenance_bytes
                or security.raw_content_hash(policy_owner_provenance_bytes)
                != policy.statement.owner_provenance_content_hash
            ):
                return failure
            provenance_ref = self.projection_verifier_provenance_ref
            trust_ref = self._put(
                {
                    "schema_version": "polisyos.epoch.native-policy-trust.v1",
                    "keys": [
                        [identity, security.raw_content_hash(pem), list(roles)]
                        for identity, pem, roles in self.deployment._state().keys
                    ],
                    "revoked_key_ids": list(self.deployment._state().config.revoked_key_ids),
                },
                "epoch.native_policy_trust",
            )
            receipt_ref = self._put(
                {
                    "schema_version": "polisyos.epoch.native-owner-verification.v1",
                    "candidate_content_hash": contract._native_candidate_content_hash(candidate),
                    "signed_policy_admission_ref": contract._raw_model_mapping(
                        signed.persisted.evidence_record_ref
                    ),
                    "owner_relation_ref": contract._raw_model_mapping(admission.owner_relation_ref),
                    "native_predicate_evidence_refs": [
                        contract._raw_model_mapping(row.evidence_ref) for row in evidence
                    ],
                    "trust_snapshot_ref": contract._raw_model_mapping(trust_ref),
                    "verifier_provenance_ref": contract._raw_model_mapping(provenance_ref),
                },
                "epoch.native_owner_verification",
            )
            return contract.VerifiedPredicatePolicyOwnerRelation(
                query=query,
                owner_relation_ref=admission.owner_relation_ref,
                owner_relation_content_hash=admission.owner_relation_content_hash,
                owner_verifier_provenance_ref=provenance_ref,
                verification_receipt_ref=receipt_ref,
                verification_receipt_content_hash=str(receipt_ref.artifact_id),
                candidate_content_hash=contract._native_candidate_content_hash(candidate),
                owner_declared_denominator_ref=expected.declared_denominator_ref,
                candidate_declared_denominator_ref=candidate.declared_denominator_ref,
                owner_ordered_member_refs=tuple(row.member_ref for row in expected.ordered_members),
                candidate_ordered_member_refs=tuple(
                    row.member_ref for row in candidate.ordered_members
                ),
                denominator_identity=contract.VerifiedNativeSubjectIdentity(
                    subject_kind="denominator",
                    subject_ref=candidate.declared_denominator_ref,
                    artifact_ref=candidate.native_denominator_artifact_ref,
                    raw_cas_hash=str(candidate.native_denominator_artifact_ref.artifact_id),
                    semantic_content_hash=candidate.native_denominator_content_hash,
                    verifier_provenance_ref=provenance_ref,
                ),
                query_context_identity=contract.VerifiedNativeSubjectIdentity(
                    subject_kind="query_context",
                    subject_ref=query.requested_query_context_ref,
                    artifact_ref=candidate.query_context_artifact_ref,
                    raw_cas_hash=str(candidate.query_context_artifact_ref.artifact_id),
                    semantic_content_hash=candidate.query_context_content_hash,
                    verifier_provenance_ref=provenance_ref,
                ),
                member_identities=tuple(
                    contract.VerifiedNativeMemberIdentity(
                        **{
                            name: getattr(row, name)
                            for name in contract.VerifiedNativeMemberIdentity.model_fields
                        }
                    )
                    for row in candidate.ordered_members
                ),
                predicate_evidence=evidence,
                policy_owner_provenance=contract.VerifiedPolicyOwnerProvenance(
                    policy_ref=policy.policy_ref,
                    policy_content_hash=policy.policy_content_hash,
                    owner_provenance_ref=policy.statement.owner_provenance_ref,
                    owner_provenance_content_hash=policy.statement.owner_provenance_content_hash,
                    trust_snapshot_ref=trust_ref,
                    trust_snapshot_content_hash=str(trust_ref.artifact_id),
                    verification_receipt_ref=signed.persisted.evidence_record_ref,
                    verification_receipt_content_hash=str(
                        signed.persisted.evidence_record_ref.artifact_id
                    ),
                    verifier_provenance_ref=provenance_ref,
                    predicate_class="independently_reconciled",
                ),
                predicate_class="independently_reconciled",
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return failure


def build_semantic_epoch_native_deployment(config: EpochDeploymentConfig | None) -> EpochDeployment:
    """Assemble native derivation only when the deployment has policy selectors."""
    transport = build_epoch_deployment(config)
    if not transport._state().config.predicate_policy_admission_refs:
        return transport
    owner = SemanticEpochNativePolicyOwner(transport)
    return build_epoch_deployment(
        config,
        native_policy_verifier=owner,
        epoch_chronology_policy_owner=owner,
        _runtime_store_affiliates=(transport,),
    )
