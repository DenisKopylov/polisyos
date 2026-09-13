"""Real native epoch custody under fixture-only independent policy signatures.

The fixture uses the actual preparation, canonical history, qualification,
finalization and activation owners. It never constructs a positive production
receipt or installs a test chronology verifier.
"""

from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, contracts, security
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.acquisition_executor import ActivatedSemanticEpochAdmissionReceipt
from polisyos.runtime.quality.chronology_qualification import QualificationConsumer
from polisyos.runtime.quality.epoch_deployment import (
    EpochDeploymentConfig,
    EpochTrustedIssuerConfig,
)
from polisyos.runtime.quality.semantic_epoch_qualification import (
    EpochNativePredicateBinding,
    SemanticEpochChronologyOwnerRelation,
    build_semantic_epoch_native_deployment,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _emit_admitted_ref,
    _real_epoch_scenario,
)

contract = contracts.chronology


def sign_native_epoch_scenario(scenario: SimpleNamespace, tmp_path: Path) -> SimpleNamespace:
    """Bind a separately signed native policy to an actual prepared epoch basis."""
    store = scenario.store
    manifest_ref = scenario.prepared.stamp.semantic_manifest_ref
    raw = store.get_bytes(manifest_ref.artifact_id)
    manifest = security.parse_canonical_statement(raw, epoch.SemanticEpochManifest)
    current = scenario.history.resolve_scope_history(
        scope=scenario.query.scope_identity, authority_purpose=scenario.query.authority_purpose
    )
    entries = current.entries
    if manifest.epoch_ref not in {row.epoch_ref for row in entries}:
        entries = (
            *entries,
            epoch.EpochHistoryEntry(
                epoch_ref=manifest.epoch_ref,
                manifest_ref=manifest_ref,
                manifest_content_hash=manifest.manifest_content_hash,
                native_member_ref=manifest_ref,
                native_member_content_hash=security.raw_content_hash(raw),
                predecessor_refs=manifest.predecessor_refs,
            ),
        )
    staged = epoch._persist_history_view(
        artifacts=store,
        scope=scenario.query.scope_identity,
        authority_purpose=scenario.query.authority_purpose,
        entries=entries,
        head_refs=(manifest.epoch_ref,),
    )
    query = contract.NativeChronologyQuery(
        domain=contract.ChronologyProofDomain(
            format=contract.FULL_PREFIX_FORMAT,
            profile=contract.FULL_PREFIX_PROFILE,
            proof_domain="semantic_epoch",
            family="epoch",
            scope_ref=scenario.query.scope_identity.scope_identity_ref,
            authority_purpose=scenario.query.authority_purpose,
        ),
        requested_cutoff_ref=manifest.epoch_ref,
        requested_query_context_ref=scenario.query.requested_query_context_ref,
    )
    key = contract.PredicatePolicySelectionKey(
        **query.domain.model_dump(exclude={"format", "profile"}),
        requested_cutoff_ref=query.requested_cutoff_ref,
    )

    def put(payload: bytes, kind: str) -> artifacts.ArtifactRef:
        return store.put_bytes(
            payload,
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/octet-stream"),
        )

    owner_ref = put(
        b"fixture independent institution for the exact native epoch scope",
        "fixture.epoch.policy_owner",
    )
    bindings = (
        EpochNativePredicateBinding(
            predicate_id="native-member", semantic_property="member_manifest_binding"
        ),
        EpochNativePredicateBinding(
            predicate_id="native-ancestry", semantic_property="ancestry_denominator"
        ),
        EpochNativePredicateBinding(predicate_id="native-query", semantic_property="query_binding"),
    )
    policy = contract.PredicateAdmissionPolicyStatement(
        schema_version="polisyos.chronology.predicate-policy.v1",
        key=key,
        native_schema_profile="policyos.epoch.semantic-manifest.v1",
        required_native_head_role="native_epoch_head",
        rules=tuple(
            contract.PredicateAdmissionRule(
                predicate_id=row.predicate_id,
                subject_kind=row.subject_kind,
                admitted_classes=("recomputed",),
            )
            for row in bindings
        ),
        owner_provenance_ref=owner_ref,
        owner_provenance_content_hash=str(owner_ref.artifact_id),
    )
    policy_ref = put(security.canonical_statement_bytes(policy), "fixture.epoch.native_policy")
    policy_hash = contract._predicate_policy_content_hash(policy)
    relation = SemanticEpochChronologyOwnerRelation(
        schema_version="polisyos.epoch.chronology-owner-relation.v1",
        query=query,
        policy_ref=policy_ref,
        policy_content_hash=policy_hash,
        native_denominator_ref=staged.history_snapshot_ref,
        predicate_bindings=bindings,
    )
    relation_ref = put(
        security.canonical_statement_bytes(relation), "fixture.epoch.native_relation"
    )
    admission = contract.PredicatePolicyAdmissionStatement(
        schema_version="polisyos.chronology.predicate-policy-admission.v1",
        key=key,
        requested_query_context_ref=query.requested_query_context_ref,
        native_schema_profile=policy.native_schema_profile,
        policy_ref=policy_ref,
        policy_content_hash=policy_hash,
        owner_relation_ref=relation_ref,
        owner_relation_content_hash=str(relation_ref.artifact_id),
    )
    private_key = Ed25519PrivateKey.generate()
    signer = artifacts.Ed25519Signer(private_key)
    tmp_path.mkdir(parents=True, exist_ok=True)
    public_key_path = tmp_path / "native-epoch-owner.pub"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    signed = FileSystemSignedArtifactEvidenceRepository(store).persist_signed(
        blob_bytes=security.canonical_statement_bytes(admission),
        write_options=artifacts.ArtifactWriteOptions(
            kind="fixture.epoch.signed_native_admission", media_type="application/octet-stream"
        ),
        signer=signer,
        signing_profile_ref=owner_ref,
        signer_provenance_ref=owner_ref,
    )
    config = EpochDeploymentConfig(
        evidence_cas_root=store.root,
        native_epoch_history_root=scenario.history._root,
        trusted_issuers=(
            EpochTrustedIssuerConfig(
                identity="fixture-native-epoch-owner",
                public_key_path=public_key_path,
                roles=("predicate_policy_admission",),
            ),
        ),
        predicate_policy_admission_refs=(signed.evidence_record_ref,),
    )
    deployment = build_semantic_epoch_native_deployment(config)
    owner = deployment._state().chronology_policy_owner
    if owner is None:
        raise AssertionError("configured native epoch owner was not installed")
    adapter = epoch.SemanticEpochQualificationAdapter(
        history=scenario.history,
        artifacts=store,
        policy_owner=owner,
    )
    original = scenario.service
    service = None
    if original is not None:
        service = epoch.SemanticEpochService(
            boundary_registry=original._boundary_registry,
            boundary_adapters=original._boundary_adapters,
            facet_registry=original._facet_registry,
            facet_provider=original._facet_provider,
            history=scenario.history,
            artifact_store=store,
            qualification_consumer=QualificationConsumer.from_deployment(deployment),
            chronology_adapter=adapter,
        )
    return SimpleNamespace(
        scenario=scenario,
        store=store,
        query=query,
        deployment=deployment,
        adapter=adapter.for_history(staged),
        staged=staged,
        config=config,
        service=service,
        policy=policy,
        admission=admission,
    )


def make_native_epoch_case(tmp_path: Path) -> SimpleNamespace:
    """Prepare one real pending catalog admission and appoint only its fixture policy."""
    return sign_native_epoch_scenario(
        _real_epoch_scenario(tmp_path / "scenario"), tmp_path / "policy"
    )


def finalize_native_epoch_case(case: SimpleNamespace) -> SimpleNamespace:
    """Run real finalization and owner activation, preserving every deciding artifact."""
    scenario = case.scenario
    admitted_ref = _emit_admitted_ref(scenario)
    production = case.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )
    if production.status not in {"appended", "no_change"}:
        raise AssertionError(f"real native epoch finalization refused: {production.failure_codes}")
    activated = scenario.overlay.activate_semantic_epoch(
        pending_receipt=scenario.pending,
        production_receipt=production,
        artifact_store=case.store,
    )
    mapping = contracts.epoch.load_verified_epoch_statement(
        store=case.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(mapping)
    receipt = ActivatedSemanticEpochAdmissionReceipt(
        passport_ref=admitted.passport_ref,
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        pending_overlay_receipt_ref=scenario.pending.receipt_ref,
        semantic_epoch_production_receipt_ref=production.receipt_ref,
        overlay_admission_receipt_ref=activated.receipt_ref,
        native_membership_receipt_ref=admitted.native_membership_receipt_ref,
        semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
        semantic_projection_verification_receipt_ref=admitted.semantic_projection_verification_receipt_ref,
        semantic_epoch_stamp=scenario.prepared.stamp,
        activation_state="active",
    )
    return SimpleNamespace(
        case=case,
        production=production,
        activated=activated,
        receipt=receipt,
        admitted_ref=admitted_ref,
    )
