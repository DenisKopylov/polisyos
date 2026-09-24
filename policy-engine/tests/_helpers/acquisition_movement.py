"""Independent signed GY fixture evidence for the real native movement consumer."""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, contracts, security
from polisyos.runtime.quality.acquisition_movement import (
    AcquisitionMovementArtifact,
    AcquisitionMovementService,
    MovementOwnerAdmission,
)
from polisyos.runtime.quality.epoch_deployment import (
    EpochDeploymentConfig,
    EpochTrustedIssuerConfig,
    build_epoch_deployment,
)

contract = contracts.chronology


def configured_movement_service(
    service: AcquisitionMovementService,
    movement: AcquisitionMovementArtifact,
    tmp_path: Path,
    *,
    include_independent_verification: bool = True,
) -> AcquisitionMovementService:
    """Sign exact externally selected policy/owner evidence; never install a fake verifier."""
    store = service._store
    candidate = service._candidate(movement)
    key = contract.PredicatePolicySelectionKey(
        **candidate.query.domain.model_dump(exclude={"format", "profile"}),
        requested_cutoff_ref=candidate.query.requested_cutoff_ref,
    )

    def put(raw: bytes, kind: str) -> artifacts.ArtifactRef:
        return store.put_bytes(
            raw, artifacts.ArtifactWriteOptions(kind=kind, media_type="application/octet-stream")
        )

    provenance_ref = put(b"fixture independent GY policy owner", "fixture.movement.provenance")
    verifier_ref = put(b"fixture independently appointed verifier", "fixture.movement.verifier")
    trust_ref = put(b"fixture scoped public trust snapshot", "fixture.movement.trust")
    policy = contract.PredicateAdmissionPolicyStatement(
        schema_version="polisyos.chronology.predicate-policy.v1",
        key=key,
        native_schema_profile="policyos.runtime.acquisition_movement.v1",
        required_native_head_role="gy_movement_admission",
        rules=(
            contract.PredicateAdmissionRule(
                predicate_id="supplier_reentry_binding",
                subject_kind="member",
                admitted_classes=("recomputed",),
            ),
            contract.PredicateAdmissionRule(
                predicate_id="exact_row_scope",
                subject_kind="query",
                admitted_classes=("recomputed",),
            ),
        ),
        owner_provenance_ref=provenance_ref,
        owner_provenance_content_hash=str(provenance_ref.artifact_id),
    )
    policy_ref = put(security.canonical_statement_bytes(policy), "fixture.movement.policy")
    policy_hash = contract._predicate_policy_content_hash(policy)
    relation = MovementOwnerAdmission(
        query=candidate.query,
        policy_ref=policy_ref,
        movement_artifact_ref=candidate.ordered_members[0].native_artifact_ref,
        supplier_receipt_ref=movement.supplier_receipt_ref,
    )
    relation_ref = put(
        security.canonical_statement_bytes(relation), "fixture.movement.owner_relation"
    )
    admission = contract.PredicatePolicyAdmissionStatement(
        schema_version="polisyos.chronology.predicate-policy-admission.v1",
        key=key,
        requested_query_context_ref=candidate.query.requested_query_context_ref,
        native_schema_profile=policy.native_schema_profile,
        policy_ref=policy_ref,
        policy_content_hash=policy_hash,
        owner_relation_ref=relation_ref,
        owner_relation_content_hash=str(relation_ref.artifact_id),
    )
    private_key = Ed25519PrivateKey.generate()
    signer = artifacts.Ed25519Signer(private_key)
    tmp_path.mkdir(parents=True, exist_ok=True)
    key_path = tmp_path / "movement-owner.pub"
    key_path.write_bytes(
        private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    repository = FileSystemSignedArtifactEvidenceRepository(store)

    def sign(statement, kind):
        return repository.persist_signed(
            blob_bytes=security.canonical_statement_bytes(statement),
            write_options=artifacts.ArtifactWriteOptions(
                kind=kind, media_type="application/octet-stream"
            ),
            signer=signer,
            signing_profile_ref=trust_ref,
            signer_provenance_ref=verifier_ref,
        ).evidence_record_ref

    config = EpochDeploymentConfig(
        evidence_cas_root=store.root,
        trusted_issuers=(
            EpochTrustedIssuerConfig(
                identity="fixture-gy-owner",
                public_key_path=key_path,
                roles=("predicate_policy_admission", "predicate_owner_verification"),
            ),
        ),
        predicate_policy_admission_refs=(sign(admission, "fixture.movement.signed_admission"),),
    )

    def build(config):
        return AcquisitionMovementService(
            control_store=service._control_store,
            artifact_store=store,
            event_log=service._events,
            epoch_deployment=build_epoch_deployment(config),
        )

    selected = build(config)
    if not include_independent_verification:
        return selected
    candidate = selected._candidate(movement)
    proof_ref = put(b"fixture independent native source recheck", "fixture.movement.verification")
    subject_rows = (
        (
            "denominator",
            candidate.declared_denominator_ref,
            candidate.native_denominator_artifact_ref,
            candidate.native_denominator_content_hash,
        ),
        (
            "query_context",
            candidate.query.requested_query_context_ref,
            candidate.query_context_artifact_ref,
            candidate.query_context_content_hash,
        ),
    )
    subjects = [
        contract.VerifiedNativeSubjectIdentity(
            subject_kind=kind,
            subject_ref=subject,
            artifact_ref=ref,
            raw_cas_hash=str(ref.artifact_id),
            semantic_content_hash=semantic,
            verifier_provenance_ref=verifier_ref,
        )
        for kind, subject, ref, semantic in subject_rows
    ]
    member = candidate.ordered_members[0]
    predicates = (
        contract.VerifiedOwnerPredicateEvidence(
            subject_kind="member",
            subject_ref=member.member_ref,
            predicate_id="supplier_reentry_binding",
            predicate_class="recomputed",
            status="satisfied",
            evidence_ref=member.native_artifact_ref,
            evidence_content_hash=str(member.native_artifact_ref.artifact_id),
            evidence_verifier_provenance_ref=verifier_ref,
        ),
        contract.VerifiedOwnerPredicateEvidence(
            subject_kind="query",
            subject_ref=candidate.query.requested_query_context_ref,
            predicate_id="exact_row_scope",
            predicate_class="recomputed",
            status="satisfied",
            evidence_ref=candidate.query_context_artifact_ref,
            evidence_content_hash=str(candidate.query_context_artifact_ref.artifact_id),
            evidence_verifier_provenance_ref=verifier_ref,
        ),
    )
    receipt = contract.VerifiedPredicatePolicyOwnerRelation(
        query=candidate.query,
        owner_relation_ref=relation_ref,
        owner_relation_content_hash=str(relation_ref.artifact_id),
        owner_verifier_provenance_ref=verifier_ref,
        verification_receipt_ref=proof_ref,
        verification_receipt_content_hash=str(proof_ref.artifact_id),
        candidate_content_hash=contract._native_candidate_content_hash(candidate),
        owner_declared_denominator_ref=candidate.declared_denominator_ref,
        candidate_declared_denominator_ref=candidate.declared_denominator_ref,
        owner_ordered_member_refs=(member.member_ref,),
        candidate_ordered_member_refs=(member.member_ref,),
        denominator_identity=subjects[0],
        query_context_identity=subjects[1],
        member_identities=(
            contract.VerifiedNativeMemberIdentity(**member.model_dump(exclude={"native_bytes"})),
        ),
        predicate_evidence=predicates,
        policy_owner_provenance=contract.VerifiedPolicyOwnerProvenance(
            policy_ref=policy_ref,
            policy_content_hash=policy_hash,
            owner_provenance_ref=provenance_ref,
            owner_provenance_content_hash=str(provenance_ref.artifact_id),
            trust_snapshot_ref=trust_ref,
            trust_snapshot_content_hash=str(trust_ref.artifact_id),
            verification_receipt_ref=proof_ref,
            verification_receipt_content_hash=str(proof_ref.artifact_id),
            verifier_provenance_ref=verifier_ref,
            predicate_class="independently_reconciled",
        ),
        predicate_class="independently_reconciled",
    )
    return build(
        config.model_copy(
            update={
                "predicate_owner_verification_refs": (
                    sign(receipt, "fixture.movement.signed_verification"),
                )
            }
        )
    )
