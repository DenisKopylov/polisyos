"""Real native epoch custody under fixture-only independent policy signatures.

The fixture uses the actual preparation, canonical history, qualification,
finalization and activation owners. It never constructs a positive production
receipt or installs a test chronology verifier.
"""

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, contracts, security
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import CatalogAcquisitionOverlay
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    canonical_json_bytes,
    derive_live_http_budget,
)
from polisyos.runtime.quality import chronology_qualification
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.acquisition_executor import (
    ActivatedSemanticEpochAdmissionReceipt,
    _logical_type,
    _persist_acquisition_semantic_candidate,
    build_admission_passport,
)
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
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)

contract = contracts.chronology


@dataclass(frozen=True, slots=True)
class NativeEpochFixtureSignedAdmission:
    """Exact selected admission artifact and its retained signed-evidence record."""

    artifact_ref: artifacts.ArtifactRef
    evidence: contract.PersistedSignedArtifactEvidence


@dataclass(frozen=True, slots=True)
class _NativeEpochFixtureCustodyEntry:
    """Context needed to decide whether this fixture may reuse a signature."""

    store: FileSystemCAS
    store_root: Path
    artifact_ref: artifacts.ArtifactRef
    evidence_record_ref: artifacts.ArtifactRef
    signing_profile_ref: artifacts.ArtifactRef
    signer_provenance_ref: artifacts.ArtifactRef
    signer_key_id: str
    issuer_identity: str
    issuer_roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeEpochFixtureCustodian:
    """Hold one fixture issuer key and reuse only its fully reconciled envelopes."""

    store: FileSystemCAS
    owner_ref: artifacts.ArtifactRef
    signer: artifacts.Ed25519Signer
    public_key_path: Path
    issuer_identity: str = "fixture-native-epoch-owner"
    issuer_roles: tuple[str, ...] = ("predicate_policy_admission",)
    _entries: list[_NativeEpochFixtureCustodyEntry] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, store: FileSystemCAS, root: Path) -> NativeEpochFixtureCustodian:
        """Create a per-test fixture issuer bound to this exact CAS and profile."""
        owner_ref = store.put_bytes(
            b"fixture independent institution for the exact native epoch scope",
            artifacts.ArtifactWriteOptions(
                kind="fixture.epoch.policy_owner",
                media_type="application/octet-stream",
            ),
        )
        private_key = Ed25519PrivateKey.generate()
        signer = artifacts.Ed25519Signer(private_key)
        root.mkdir(parents=True, exist_ok=True)
        key_path_id = hashlib.sha256(signer.key_id.encode("utf-8")).hexdigest()
        public_key_path = root / f"native-epoch-owner-{key_path_id}.pub"
        public_key_bytes = private_key.public_key().public_bytes(
            Encoding.PEM,
            PublicFormat.SubjectPublicKeyInfo,
        )
        with public_key_path.open("xb") as public_key_file:
            public_key_file.write(public_key_bytes)
        return cls(
            store=store,
            owner_ref=owner_ref,
            signer=signer,
            public_key_path=public_key_path,
        )

    def persist_or_reuse(
        self,
        *,
        blob_bytes: bytes,
        signing_profile_ref: artifacts.ArtifactRef,
        signer_provenance_ref: artifacts.ArtifactRef,
    ) -> NativeEpochFixtureSignedAdmission:
        """Persist one admission or return its exact previously verified envelope."""
        write_options = artifacts.ArtifactWriteOptions(
            kind="fixture.epoch.signed_native_admission",
            media_type="application/octet-stream",
        )
        artifact_ref = self.store.put_bytes(blob_bytes, write_options)
        matching_entries = [
            entry
            for entry in self._entries
            if entry.artifact_ref.artifact_id == artifact_ref.artifact_id
        ]
        if matching_entries:
            if len(matching_entries) != 1:
                raise ValueError("native epoch fixture has ambiguous retained signatures")
            entry = matching_entries[0]
            if not self._context_matches(
                entry,
                artifact_ref=artifact_ref,
                signing_profile_ref=signing_profile_ref,
                signer_provenance_ref=signer_provenance_ref,
            ):
                raise ValueError("native epoch fixture signing context conflicts with envelope")
            return self._read_and_verify(
                entry,
                blob_bytes=blob_bytes,
                artifact_ref=artifact_ref,
                signing_profile_ref=signing_profile_ref,
                signer_provenance_ref=signer_provenance_ref,
            )

        if self.store.has_signature(artifact_ref):
            raise ValueError(
                "existing signature is not owned by this native epoch fixture custodian"
            )

        persisted = FileSystemSignedArtifactEvidenceRepository(self.store).persist_signed(
            blob_bytes=blob_bytes,
            write_options=write_options,
            signer=self.signer,
            signing_profile_ref=signing_profile_ref,
            signer_provenance_ref=signer_provenance_ref,
        )
        entry = _NativeEpochFixtureCustodyEntry(
            store=self.store,
            store_root=self.store.root.resolve(),
            artifact_ref=artifact_ref,
            evidence_record_ref=persisted.evidence_record_ref,
            signing_profile_ref=signing_profile_ref,
            signer_provenance_ref=signer_provenance_ref,
            signer_key_id=self.signer.key_id,
            issuer_identity=self.issuer_identity,
            issuer_roles=self.issuer_roles,
        )
        self._entries.append(entry)
        return self._read_and_verify(
            entry,
            blob_bytes=blob_bytes,
            artifact_ref=artifact_ref,
            signing_profile_ref=signing_profile_ref,
            signer_provenance_ref=signer_provenance_ref,
        )

    def _context_matches(
        self,
        entry: _NativeEpochFixtureCustodyEntry,
        *,
        artifact_ref: artifacts.ArtifactRef,
        signing_profile_ref: artifacts.ArtifactRef,
        signer_provenance_ref: artifacts.ArtifactRef,
    ) -> bool:
        return (
            entry.store is self.store
            and entry.store_root == self.store.root.resolve()
            and entry.artifact_ref == artifact_ref
            and entry.signing_profile_ref == signing_profile_ref
            and entry.signer_provenance_ref == signer_provenance_ref
            and entry.signer_key_id == self.signer.key_id
            and entry.issuer_identity == self.issuer_identity
            and entry.issuer_roles == self.issuer_roles
        )

    def _read_and_verify(
        self,
        entry: _NativeEpochFixtureCustodyEntry,
        *,
        blob_bytes: bytes,
        artifact_ref: artifacts.ArtifactRef,
        signing_profile_ref: artifacts.ArtifactRef,
        signer_provenance_ref: artifacts.ArtifactRef,
    ) -> NativeEpochFixtureSignedAdmission:
        evidence = FileSystemSignedArtifactEvidenceRepository(self.store).read_exact(
            evidence_record_ref=entry.evidence_record_ref
        )
        frames = contract._split_framed_records(evidence.persisted.record_bytes)
        if len(frames) != 1:
            raise ValueError("native epoch fixture evidence record has invalid framing")
        raw_record = json.loads(frames[0])
        if not isinstance(raw_record, dict):
            raise ValueError("native epoch fixture evidence record is not a mapping")
        record = contract.SignedArtifactEvidenceRecord.model_validate(raw_record)
        if evidence.blob_bytes != blob_bytes or record.artifact_ref != artifact_ref:
            raise ValueError("native epoch fixture envelope does not bind exact admission bytes")
        if (
            record.signing_profile_ref != signing_profile_ref
            or record.signer_provenance_ref != signer_provenance_ref
        ):
            raise ValueError("native epoch fixture envelope profile or provenance mismatch")
        if (
            entry.store is not self.store
            or entry.store_root != self.store.root.resolve()
            or entry.signer_key_id != self.signer.key_id
            or entry.issuer_identity != self.issuer_identity
            or entry.issuer_roles != self.issuer_roles
        ):
            raise ValueError("native epoch fixture envelope custody context changed")

        signature = artifacts.DetachedSignature.model_validate_json(
            evidence.detached_signature_bytes
        )
        if signature.key_id != self.signer.key_id:
            raise ValueError("native epoch fixture signature key differs from custodian")
        verifier = artifacts.Ed25519Verifier(strict_identity=True)
        trusted_key_id = verifier.load_trusted_key_file(
            self.public_key_path,
            identity=self.issuer_identity,
        )
        if trusted_key_id != self.signer.key_id:
            raise ValueError("native epoch fixture issuer key binding changed")
        verification = self.store.verify_signature(
            artifact_ref,
            verifier,
            strict_identity=True,
        )
        if verification.status is not artifacts.SignatureVerificationStatus.VALID:
            raise ValueError("native epoch fixture signature did not verify for its issuer")
        return NativeEpochFixtureSignedAdmission(
            artifact_ref=artifact_ref,
            evidence=evidence.persisted,
        )


def sign_native_epoch_scenario(
    scenario: SimpleNamespace,
    tmp_path: Path,
    *,
    custodian: NativeEpochFixtureCustodian | None = None,
    prior_admission_refs: tuple[artifacts.ArtifactRef, ...] = (),
) -> SimpleNamespace:
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

    if custodian is None:
        custodian = NativeEpochFixtureCustodian.create(store, tmp_path / "issuer")
    elif custodian.store is not store:
        raise ValueError("native epoch fixture custodian belongs to a different CAS")
    owner_ref = custodian.owner_ref
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
    signed = custodian.persist_or_reuse(
        blob_bytes=security.canonical_statement_bytes(admission),
        signing_profile_ref=owner_ref,
        signer_provenance_ref=owner_ref,
    )
    admission_refs: list[artifacts.ArtifactRef] = []
    seen_admission_ref_keys: set[tuple[str, str, str, str | None]] = set()
    for admission_ref in (*prior_admission_refs, signed.evidence.evidence_record_ref):
        admission_ref_key = artifacts.artifact_ref_identity_key(admission_ref)
        if admission_ref_key in seen_admission_ref_keys:
            continue
        seen_admission_ref_keys.add(admission_ref_key)
        admission_refs.append(admission_ref)
    config = EpochDeploymentConfig(
        evidence_cas_root=store.root,
        native_epoch_history_root=scenario.history._root,
        trusted_issuers=(
            EpochTrustedIssuerConfig(
                identity=custodian.issuer_identity,
                public_key_path=custodian.public_key_path,
                roles=custodian.issuer_roles,
            ),
        ),
        predicate_policy_admission_refs=tuple(admission_refs),
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
            qualification_consumer=QualificationConsumer.from_deployment(
                deployment, runtime_artifact_store=store
            ),
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
        signed=signed,
        custodian=custodian,
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


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _profile() -> SourceProfile:
    return SourceProfile(
        profile_id="local_parquet",
        display_name="Owner-validated local payload",
        connector_family="local",
        base_url="file:///owner-validated-local",
        timeout_seconds=30,
    )


def _build_acquisition_epoch_fixture_service(
    *,
    store: FileSystemCAS,
    authority: catalog_read_api.CanonicalAcquisitionAuthority,
    root: Path,
) -> tuple[
    epoch.SemanticEpochService,
    CatalogAcquisitionOverlay,
    FileSemanticEpochHistoryRepository,
]:
    """Compose the registered acquisition owner used by real epoch preparation."""
    root.mkdir(parents=True, exist_ok=True)
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        root / "acquisition-overlay.duckdb",
    )
    overlay.initialize()
    facet_ref = store.put_bytes(
        epoch_contract.canonical_epoch_bytes({"semantic_value": "catalog-semantics"}),
        ArtifactWriteOptions(
            kind="epoch.semantic_facet_source.v1",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
    )
    history = FileSemanticEpochHistoryRepository(
        root=root / "history",
        artifacts=store,
    )
    service = epoch.SemanticEpochService(
        boundary_registry=epoch.build_boundary_registry(
            (
                epoch.EpochBoundarySourceRegistration(
                    registration_id="n13b-acquisition-native-history",
                    owner_kind="catalog_acquisition",
                    owner_source_ref=epoch._sha256(b"test-catalog-owner"),
                    opaque_scope_binding_ref=epoch._sha256(b"test-catalog-scope"),
                ),
            )
        ),
        boundary_adapters={
            "catalog_acquisition": epoch.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                owner=overlay,
                artifacts=store,
            )
        },
        facet_registry=epoch.build_facet_registry(
            (
                epoch.SemanticFacetRegistration(
                    facet_id="catalog-semantics",
                    source_binding_ref=str(facet_ref.artifact_id),
                ),
            )
        ),
        facet_provider=epoch.ArtifactSemanticFacetProvider(
            artifacts=store,
            source_refs={str(facet_ref.artifact_id): facet_ref},
        ),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=(
            epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=history,
                artifacts=store,
            )
        ),
    )
    return service, overlay, history


def _semantic_handshake(
    store: FileSystemCAS,
    *,
    source_ref: object,
    authority: catalog_read_api.CanonicalAcquisitionAuthority,
) -> tuple[
    epoch_contract.AcquisitionSemanticBoundaryCandidate,
    epoch.PreparedSemanticEpoch,
]:
    """Build a candidate and prepared epoch through the registered service."""

    assert hasattr(source_ref, "artifact_id")

    def put(payload: bytes, *, kind: str):
        return store.put_bytes(
            payload,
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )

    scope_bytes = b'{"domain":"acquisition-test","jurisdiction":"UA"}'
    scope = epoch.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.acquisition-test-scope.v1",
        identity_bytes=scope_bytes,
    )
    coordinate_payloads = {
        "valid_effect": b"passport-fixture-valid-2025-01-01",
        "visibility_knowledge_cutoff": b"passport-fixture-visible-2025-02-01",
        "purpose_admission_cutoff": b"passport-fixture-admitted-2025-02-02",
    }
    coordinate_refs: dict[str, tuple[object, str]] = {}
    for role, payload in coordinate_payloads.items():
        kind = f"epoch.coordinate.{role}.v1"
        ref = put(payload, kind=kind)
        coordinate_refs[role] = (
            ref,
            epoch_contract.native_coordinate_ref(
                family="epoch",
                role=role,
                schema_profile=kind,
                coordinate_bytes=payload,
            ),
        )
    context_ref = epoch_contract.epoch_query_context_ref(
        family="epoch",
        scope_bytes=scope_bytes,
        authority_purpose="publication",
        coordinate_refs=tuple(coordinate_refs[role][1] for role in coordinate_payloads),
    )
    query = epoch.EpochResolutionQuery(
        scope_identity=scope,
        authority_purpose="publication",
        valid_effect_coordinate_evidence_ref=coordinate_refs["valid_effect"][0],
        valid_effect_coordinate_ref=coordinate_refs["valid_effect"][1],
        visibility_knowledge_cutoff_evidence_ref=coordinate_refs["visibility_knowledge_cutoff"][0],
        visibility_knowledge_cutoff_ref=coordinate_refs["visibility_knowledge_cutoff"][1],
        purpose_admission_cutoff_evidence_ref=coordinate_refs["purpose_admission_cutoff"][0],
        purpose_admission_cutoff_ref=coordinate_refs["purpose_admission_cutoff"][1],
        requested_query_context_ref=context_ref,
    )
    service_root = (
        store.root.parent
        / "semantic-epoch-handshake"
        / hashlib.sha256(str(source_ref.artifact_id).encode("utf-8")).hexdigest()[:12]
    )
    service, overlay, _history = _build_acquisition_epoch_fixture_service(
        store=store,
        authority=authority,
        root=service_root,
    )
    try:
        native_query = service.acquisition_owner_query(query=query)
        candidate_statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement(
            source_record_ref=source_ref,
            source_record_content_hash=str(source_ref.artifact_id),
            scope_identity_ref=native_query.scope_identity_ref,
            authority_purpose=native_query.authority_purpose,
            valid_effect_coordinate_ref=native_query.valid_effect_coordinate_ref,
            visibility_knowledge_cutoff_ref=native_query.visibility_knowledge_cutoff_ref,
            purpose_admission_cutoff_ref=native_query.purpose_admission_cutoff_ref,
            requested_query_context_ref=native_query.requested_query_context_ref,
        )
        candidate = _persist_acquisition_semantic_candidate(
            artifact_store=store,
            statement=candidate_statement,
        )
        prepared = service.prepare_acquisition_candidate(
            query=query,
            candidate_ref=candidate.candidate_ref,
        )
    finally:
        overlay.close()
    return candidate, prepared


def _semantic_handshake_from_passport(
    passport: object,
    store: FileSystemCAS,
) -> tuple[
    epoch_contract.AcquisitionSemanticBoundaryCandidate,
    epoch.PreparedSemanticEpoch,
]:
    """Reload the exact semantic handshake bound into one v2 passport."""

    candidate_ref = passport.semantic_boundary_candidate_ref
    candidate_raw = store.get_bytes(candidate_ref.artifact_id)
    candidate_statement = (
        epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
            from_canonical_bytes(candidate_raw[8:])
        )
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
        candidate_ref=candidate_ref,
        candidate_content_hash=passport.semantic_boundary_candidate_content_hash,
        statement=candidate_statement,
    )
    prepared_ref = passport.prepared_semantic_epoch_ref
    prepared_raw = store.get_bytes(prepared_ref.artifact_id)
    prepared_mapping = from_canonical_bytes(prepared_raw[8:])
    assert isinstance(prepared_mapping, dict)
    prepared = epoch.PreparedSemanticEpoch(
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=epoch._model_hash(
            b"polisyos.epoch.prepared.v1\0",
            prepared_mapping,
        ),
        **prepared_mapping,
    )
    return candidate, prepared


def _write_l5(repo_root: Path) -> Path:
    path = repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "coverage_rules": {"distress_enforcement": 0.6},
                "proxy_mappings": {},
                "trust_tiers": {
                    "authoritative_partial_coverage": {
                        "tier": "authoritative_partial_coverage",
                        "min_coverage": 0.5,
                        "max_coverage": 1.0,
                        "trust_cap": 0.85,
                        "trust_multiplier": 0.95,
                    },
                    "administrative_noisy": {
                        "tier": "administrative_noisy",
                        "min_coverage": 0.0,
                        "max_coverage": 1.0,
                        "trust_cap": 0.7,
                        "trust_multiplier": 0.85,
                    },
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _source_rows_by_raw_field(
    source_rows: list[dict[str, object]],
    variable_specs: Sequence[Mapping[str, object]],
    condition_units_by_raw_field: Mapping[str, str] | None,
) -> dict[str, list[dict[str, object]]]:
    """Bind optional synthetic condition units to each selected raw field."""
    raw_fields = tuple(dict.fromkeys(str(spec["raw_field"]) for spec in variable_specs))
    if condition_units_by_raw_field is None:
        return dict.fromkeys(raw_fields, source_rows)
    if set(condition_units_by_raw_field) != set(raw_fields):
        raise ValueError("native_epoch_fixture_condition_unit_fields_mismatch")
    rows_by_raw_field: dict[str, list[dict[str, object]]] = {}
    for raw_field in raw_fields:
        unit = condition_units_by_raw_field[raw_field]
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError("native_epoch_fixture_condition_unit_missing")
        selected_rows: list[dict[str, object]] = []
        for row in source_rows:
            condition_value = row.get("condition_json", "{}")
            if not isinstance(condition_value, str):
                raise ValueError("native_epoch_fixture_condition_json_malformed")
            try:
                condition = json.loads(condition_value)
            except json.JSONDecodeError as exc:
                raise ValueError("native_epoch_fixture_condition_json_malformed") from exc
            if not isinstance(condition, dict):
                raise ValueError("native_epoch_fixture_condition_json_wrong_shape")
            existing_unit = condition.get("unit")
            if existing_unit not in (None, "", unit):
                raise ValueError("native_epoch_fixture_condition_unit_conflicts")
            condition["unit"] = unit
            selected_rows.append(
                {
                    **row,
                    "condition_json": json.dumps(
                        condition,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
        rows_by_raw_field[raw_field] = selected_rows
    return rows_by_raw_field


def _authority(
    tmp_path: Path,
    *,
    source_rows: list[dict[str, object]],
    variable_specs: Sequence[Mapping[str, object]] | None = None,
    unadmitted_baseline_observations: Sequence[Mapping[str, object]] = (),
    condition_units_by_raw_field: Mapping[str, str] | None = None,
):
    repo_root = tmp_path / "repo"
    graph = catalog_read_api.build_slice0_fixture_catalog_graph(repo_root / "catalog")
    graph.close()
    baseline = repo_root / "catalog/catalog.duckdb"
    if unadmitted_baseline_observations:
        import duckdb

        connection = duckdb.connect(str(baseline))
        try:
            for observation in unadmitted_baseline_observations:
                connection.execute(
                    "INSERT INTO ds_observations (observation_id, dataset_id, raw_variable, canonical_var, country_code, year, survey_year, wave, value, condition_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(
                        observation[field]
                        for field in (
                            "observation_id",
                            "dataset_id",
                            "raw_variable",
                            "canonical_var",
                            "country_code",
                            "year",
                            "survey_year",
                            "wave",
                            "value",
                            "condition_json",
                        )
                    ),
                )
        finally:
            connection.close()
    if variable_specs is None:
        selected_specs: tuple[Mapping[str, object], ...] = (
            {
                "target_variable": "cells.distress_score",
                "raw_field": "distress_score",
                "raw_unit": "ratio",
                "canonical_unit": "ratio",
                "landing_dataset_id": "acquisition.local.corrected_firm_panels",
                "landing_distribution_id": "acquisition.local.corrected_firm_panels.json",
                "unit_transform_ref": "fabric://units/ratio-identity/v1",
                "schema_contract_ref": "repo://acquisition-registry#/local-distress/schema",
                "title": "Owner-validated local distress observations",
                "description": "Content-bound local observations for the distress slot.",
                "temporal_start": "2024",
                "temporal_end": "2025",
            },
        )
    else:
        selected_specs = tuple(variable_specs)
    source_rows_by_raw_field = _source_rows_by_raw_field(
        source_rows, selected_specs, condition_units_by_raw_field
    )
    signer = Ed25519PrivateKey.generate()
    public_key = signer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    trust_registry = catalog_read_api.build_local_rights_trust_registry(
        authorities=(
            catalog_read_api.LocalRightsTrustedAuthority(
                authority_id="synthetic.fixture.owner",
                rights_authority="Synthetic fixture data owner",
                authority_ref="https://example.test/local-distress/terms",
                ed25519_public_key_base64=base64.b64encode(public_key).decode("ascii"),
                admissible_license_ids=("CC-BY-4.0",),
            ),
        )
    )
    trust_path = repo_root / catalog_read_api.DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    trust_path.write_text(
        json.dumps(
            trust_registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    source_bindings: dict[str, tuple[str, Path, str, Path]] = {}
    for index, (raw_field, variable_rows) in enumerate(source_rows_by_raw_field.items(), start=1):
        if condition_units_by_raw_field is None:
            source_relative_path = "evidence/local-distress.json"
            rights_relative_path = "evidence/local-distress-rights.json"
            receipt_relative_path = "evidence/local-distress-rights-receipt.json"
        else:
            suffix = f"variable-{index:02d}"
            source_relative_path = f"evidence/local-distress-{suffix}.json"
            rights_relative_path = f"evidence/local-distress-{suffix}-rights.json"
            receipt_relative_path = f"evidence/local-distress-{suffix}-rights-receipt.json"
        source_path = repo_root / source_relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(canonical_json_bytes(variable_rows))
        declaration_values = {
            "schema_version": "polisyos.data_forge.local_source_rights_declaration.v1",
            "source_path": source_relative_path,
            "source_content_sha256": _sha(source_path),
            "license_id": "CC-BY-4.0",
            "authority_id": "synthetic.fixture.owner",
            "rights_authority": "Synthetic fixture data owner",
            "authority_ref": "https://example.test/local-distress/terms",
        }
        rights_document_path = repo_root / rights_relative_path
        rights_document_path.write_text(
            json.dumps(
                catalog_read_api.build_local_source_rights_declaration(
                    **declaration_values,
                    signature_base64=base64.b64encode(
                        signer.sign(canonical_json_bytes(declaration_values))
                    ).decode("ascii"),
                ).model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        rights_receipt = catalog_read_api.verify_local_source_rights(
            repo_root=repo_root,
            source_path=source_relative_path,
            rights_document_path=rights_relative_path,
        )
        rights_receipt_path = repo_root / receipt_relative_path
        rights_receipt_path.write_text(
            json.dumps(
                rights_receipt.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        source_bindings[raw_field] = (
            source_relative_path,
            source_path,
            receipt_relative_path,
            rights_receipt_path,
        )
    l5 = _write_l5(repo_root)
    years = tuple(
        sorted(
            int(row[key])
            for row in source_rows
            for key in ("year", "survey_year", "wave")
            if row.get(key) is not None
        )
    )
    if not years:
        raise ValueError("native_epoch_fixture_requires_time_coordinate")
    entries_list = []
    for spec in selected_specs:
        raw_field = str(spec["raw_field"])
        # Freeze the exact carrier schema after optional per-field condition
        # augmentation, before the journal/passport measures those same bytes.
        selected_source_rows = source_rows_by_raw_field[raw_field]
        source_columns = tuple(sorted({name for row in selected_source_rows for name in row}))
        schema_columns_list: list[catalog_read_api.AuthoritySchemaColumn] = []
        for name in source_columns:
            values = [row.get(name) for row in selected_source_rows]
            logical_type = _logical_type(values)
            if logical_type.startswith("mixed["):
                raise ValueError("semantic_epoch_fixture_schema_type_unresolved")
            schema_columns_list.append(
                catalog_read_api.AuthoritySchemaColumn(
                    name=name,
                    logical_types=(logical_type,),
                    nullable=any(
                        name not in row or row.get(name) is None for row in selected_source_rows
                    ),
                )
            )
        schema_columns = tuple(schema_columns_list)
        (
            source_relative_path,
            source_path,
            receipt_relative_path,
            rights_receipt_path,
        ) = source_bindings[raw_field]
        entries_list.append(
            catalog_read_api.build_authority_entry(
                source_lane="local_lift",
                target_variable=str(spec["target_variable"]),
                landing_dataset_id=str(
                    spec.get(
                        "landing_dataset_id",
                        "acquisition.local." + str(spec["target_variable"]).replace(".", "_"),
                    )
                ),
                landing_distribution_id=str(
                    spec.get(
                        "landing_distribution_id",
                        "acquisition.local."
                        + str(spec["target_variable"]).replace(".", "_")
                        + ".json",
                    )
                ),
                raw_field=raw_field,
                raw_unit=str(spec.get("raw_unit", spec.get("canonical_unit", "ratio"))),
                canonical_unit=str(spec.get("canonical_unit", spec.get("raw_unit", "ratio"))),
                unit_transform=str(spec.get("unit_transform", "identity")),
                unit_transform_ref=str(
                    spec.get(
                        "unit_transform_ref",
                        "fabric://units/"
                        + str(spec.get("canonical_unit", "ratio"))
                        + "-identity/v1",
                    )
                ),
                alignment_method="meta_analytic",
                alignment_confidence=0.8,
                is_proxy=False,
                proxy_penalty=0.0,
                aggregation_method="identity",
                valid_min=float(spec.get("valid_min", 0.0)),
                valid_max=float(spec.get("valid_max", 1.0)),
                evidence_refs=("repo://" + source_relative_path,),
                schema_contract_ref=str(
                    spec.get(
                        "schema_contract_ref",
                        "repo://acquisition-registry#/" + raw_field + "/schema",
                    )
                ),
                schema_columns=schema_columns,
                l5_family_id="distress_enforcement",
                local_source_path=source_relative_path,
                local_source_sha256=_sha(source_path),
                local_license_id="CC-BY-4.0",
                local_rights_receipt_path=receipt_relative_path,
                local_rights_receipt_sha256=_sha(rights_receipt_path),
                title=str(
                    spec.get(
                        "title", f"Owner-validated local {spec['target_variable']} observations"
                    )
                ),
                description=str(
                    spec.get("description", "Content-bound synthetic candidate observations.")
                ),
                country_codes=("UA",),
                temporal_start=str(spec.get("temporal_start", years[0])),
                temporal_end=str(spec.get("temporal_end", years[-1])),
            )
        )
    entries = tuple(entries_list)
    registry = catalog_read_api.build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=entries,
    )
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    provision = catalog_read_api.build_acquisition_authority_provision(
        baseline_owner_ref="repo://catalog/catalog.duckdb",
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_owner_ref=("repo://" + DEFAULT_L5_MEASUREMENT_REGISTRY.as_posix()),
        l5_measurement_registry_content_sha256=_sha(l5),
        local_rights_trust_anchor_sha256=_sha(trust_path),
    )
    provision_path = repo_root / catalog_read_api.DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    provision_path.parent.mkdir(parents=True, exist_ok=True)
    provision_path.write_text(
        json.dumps(
            provision.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return (
        catalog_read_api.CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=baseline,
        ),
        entries,
    )


def _fixture(
    tmp_path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    source_rows: list[dict[str, object]] | None = None,
    raw_artifact_override: str | None = None,
):
    selected_rows = rows or [
        {"country_code": "UA", "year": 2024, "distress_score": 0.42},
        {"country_code": "UA", "year": 2025, "distress_score": 0.51},
    ]
    authority, entries = _authority(
        tmp_path,
        source_rows=source_rows or selected_rows,
    )
    entry = entries[0]
    resolved = authority.resolve(entry.entry_id)
    payload = canonical_json_bytes(selected_rows)
    store = FileSystemCAS(tmp_path / "cas")
    artifact = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="fabric.acquisition.raw_evidence",
            media_type="application/json",
        ),
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / "journal.jsonl")
    request_ref = journal.append_request(
        attempt_id="local-lift-001",
        request={
            "authority_entry_id": entry.entry_id,
            "authority_registry_content_sha256": resolved.registry_content_sha256,
            "variable_id": entry.target_variable,
            "source_lane": entry.source_lane,
            "dataset_id": entry.landing_dataset_id,
            "distribution_id": entry.landing_distribution_id,
            "connector_id": resolved.registration.connector_id,
            "profile_id": resolved.registration.source_profile_id,
            "request_dataset_id": resolved.registration.request_dataset_id,
            "schema_contract": entry.schema_projection(),
        },
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id="local-lift-001",
        request_ref=request_ref,
        payload=payload,
        status_code=None,
        response_headers={"content-type": "application/json"},
        budget=derive_live_http_budget(
            _profile(),
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
        ),
    )
    boundary_candidate, prepared_epoch = _semantic_handshake(
        store,
        source_ref=artifact,
        authority=authority,
    )
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        raw_artifact_id=raw_artifact_override or str(artifact.artifact_id),
        authority=authority,
        boundary_candidate=boundary_candidate,
        prepared_epoch=prepared_epoch,
    )
    return passport, store, authority, entry, raw_ref


def _valid_passport(tmp_path: Path):
    passport, store, authority, entry, _ = _fixture(tmp_path)
    return passport, store, authority, entry


def _real_epoch_scenario(tmp_path: Path, *, epoch_id: int = 1) -> SimpleNamespace:
    """Prepare and persist one pending admission through the real epoch service."""

    fixture_passport, store, authority, entry, raw_ref = _fixture(tmp_path / "authority")
    fixture_candidate, fixture_prepared = _semantic_handshake_from_passport(
        fixture_passport,
        store,
    )
    query = fixture_prepared.query
    service, overlay, history = _build_acquisition_epoch_fixture_service(
        store=store,
        authority=authority,
        root=tmp_path,
    )
    native_query = service.acquisition_owner_query(query=query)
    candidate_statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement(
        source_record_ref=fixture_candidate.statement.source_record_ref,
        source_record_content_hash=fixture_candidate.statement.source_record_content_hash,
        scope_identity_ref=native_query.scope_identity_ref,
        authority_purpose=native_query.authority_purpose,
        valid_effect_coordinate_ref=native_query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=native_query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=native_query.purpose_admission_cutoff_ref,
        requested_query_context_ref=native_query.requested_query_context_ref,
    )
    candidate = _persist_acquisition_semantic_candidate(
        artifact_store=store,
        statement=candidate_statement,
    )
    candidate_ref = candidate.candidate_ref
    prepared = service.prepare_acquisition_candidate(
        query=query,
        candidate_ref=candidate.candidate_ref,
    )
    passport = build_admission_passport(
        epoch_id=epoch_id,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        raw_artifact_id=fixture_passport.raw_artifact_id,
        authority=authority,
        boundary_candidate=candidate,
        prepared_epoch=prepared,
    )
    pending = overlay.admit_epoch(
        passport=passport,
        prepared_epoch=prepared,
        boundary_candidate=candidate,
        artifact_store=store,
        authority=authority,
    )
    return SimpleNamespace(
        store=store,
        authority=authority,
        entry=entry,
        raw_ref=raw_ref,
        overlay=overlay,
        history=history,
        service=service,
        query=query,
        candidate=candidate,
        prepared=prepared,
        passport=passport,
        pending=pending,
    )


def _emit_admitted_ref(scenario: SimpleNamespace):
    """Persist the real owner bridge after complete native re-enumeration."""

    owner_query = scenario.service.acquisition_owner_query(query=scenario.query)
    return scenario.overlay.emit_admitted_boundary_evidence(
        query=owner_query,
        passport=scenario.passport,
        prepared_epoch=scenario.prepared,
        boundary_candidate=scenario.candidate,
        pending_receipt=scenario.pending,
        artifact_store=scenario.store,
    )


def make_native_multivariable_active_projections(
    tmp_path: Path,
    *,
    source_rows: list[dict[str, object]],
    variable_specs: Sequence[Mapping[str, object]],
    unadmitted_baseline_observations: Sequence[Mapping[str, object]] = (),
    condition_units_by_raw_field: Mapping[str, str] | None = None,
    artifact_store: FileSystemCAS | None = None,
) -> SimpleNamespace:
    """Create active projections through the real signed epoch owner chain.

    Rows are controlled synthetic candidate inputs; source meaning, assignment,
    support, sampling, and unit authority remain unestablished.
    """
    if not variable_specs:
        raise ValueError("native_epoch_fixture_requires_variable_specs")
    authority, entries = _authority(
        tmp_path / "authority",
        source_rows=source_rows,
        variable_specs=variable_specs,
        unadmitted_baseline_observations=unadmitted_baseline_observations,
        condition_units_by_raw_field=condition_units_by_raw_field,
    )
    source_rows_by_raw_field = _source_rows_by_raw_field(
        source_rows, variable_specs, condition_units_by_raw_field
    )
    store = artifact_store or FileSystemCAS(tmp_path / "cas")
    journal = AppendOnlyEvidenceJournal(tmp_path / "journal.jsonl")
    overlay_path = catalog_read_api.default_acquisition_overlay_path(authority.repo_root)
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    history = FileSemanticEpochHistoryRepository(root=tmp_path / "history", artifacts=store)
    facet_ref = store.put_bytes(
        epoch_contract.canonical_epoch_bytes({"semantic_value": "catalog-semantics"}),
        ArtifactWriteOptions(
            kind="epoch.semantic_facet_source.v1",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
    )
    service = epoch.SemanticEpochService(
        boundary_registry=epoch.build_boundary_registry(
            (
                epoch.EpochBoundarySourceRegistration(
                    registration_id="n13b-acquisition-native-history",
                    owner_kind="catalog_acquisition",
                    owner_source_ref=epoch._sha256(b"test-catalog-owner"),
                    opaque_scope_binding_ref=epoch._sha256(b"test-catalog-scope"),
                ),
            )
        ),
        boundary_adapters={
            "catalog_acquisition": epoch.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                owner=overlay, artifacts=store
            )
        },
        facet_registry=epoch.build_facet_registry(
            (
                epoch.SemanticFacetRegistration(
                    facet_id="catalog-semantics", source_binding_ref=str(facet_ref.artifact_id)
                ),
            )
        ),
        facet_provider=epoch.ArtifactSemanticFacetProvider(
            artifacts=store, source_refs={str(facet_ref.artifact_id): facet_ref}
        ),
        history=history,
        artifact_store=store,
        qualification_consumer=QualificationConsumer.from_unallocated_policy_authority(),
        chronology_adapter=epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
            history=history, artifacts=store
        ),
    )
    fixture_custodian = NativeEpochFixtureCustodian.create(
        store,
        tmp_path / "native-epoch-owner",
    )
    projections: dict[str, object] = {}
    prior_admission_refs: list[artifacts.ArtifactRef] = []
    for epoch_id, entry in enumerate(entries, start=1):
        resolved = authority.resolve(entry.entry_id)
        attempt_id = f"n8-multivariable-owner-{epoch_id:02d}"
        payload = canonical_json_bytes(source_rows_by_raw_field[str(entry.raw_field)])
        source_ref = store.put_bytes(
            payload,
            ArtifactWriteOptions(
                kind="fabric.acquisition.raw_evidence",
                media_type="application/json",
            ),
        )
        request_ref = journal.append_request(
            attempt_id=attempt_id,
            request={
                "authority_entry_id": entry.entry_id,
                "authority_registry_content_sha256": resolved.registry_content_sha256,
                "variable_id": entry.target_variable,
                "source_lane": entry.source_lane,
                "dataset_id": entry.landing_dataset_id,
                "distribution_id": entry.landing_distribution_id,
                "connector_id": resolved.registration.connector_id,
                "profile_id": resolved.registration.source_profile_id,
                "request_dataset_id": resolved.registration.request_dataset_id,
                "schema_contract": entry.schema_projection(),
            },
        )
        raw_ref = journal.append_raw_evidence(
            attempt_id=attempt_id,
            request_ref=request_ref,
            payload=payload,
            status_code=None,
            response_headers={"content-type": "application/json"},
            budget=derive_live_http_budget(
                _profile(), max_response_bytes=65_536, max_decompressed_bytes=65_536
            ),
        )
        candidate0, prepared0 = _semantic_handshake(
            store,
            source_ref=source_ref,
            authority=authority,
        )
        native_query = service.acquisition_owner_query(query=prepared0.query)
        statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement(
            source_record_ref=candidate0.statement.source_record_ref,
            source_record_content_hash=candidate0.statement.source_record_content_hash,
            scope_identity_ref=native_query.scope_identity_ref,
            authority_purpose=native_query.authority_purpose,
            valid_effect_coordinate_ref=native_query.valid_effect_coordinate_ref,
            visibility_knowledge_cutoff_ref=native_query.visibility_knowledge_cutoff_ref,
            purpose_admission_cutoff_ref=native_query.purpose_admission_cutoff_ref,
            requested_query_context_ref=native_query.requested_query_context_ref,
        )
        candidate = _persist_acquisition_semantic_candidate(
            artifact_store=store,
            statement=statement,
        )
        candidate_ref = candidate.candidate_ref
        prepared = service.prepare_acquisition_candidate(
            query=prepared0.query, candidate_ref=candidate_ref
        )
        passport = build_admission_passport(
            epoch_id=epoch_id,
            raw_evidence_ref=raw_ref,
            artifact_store=store,
            raw_artifact_id=str(source_ref.artifact_id),
            authority=authority,
            boundary_candidate=candidate,
            prepared_epoch=prepared,
        )
        pending = overlay.admit_epoch(
            passport=passport,
            prepared_epoch=prepared,
            boundary_candidate=candidate,
            artifact_store=store,
            authority=authority,
        )
        scenario = SimpleNamespace(
            store=store,
            authority=authority,
            entry=entry,
            raw_ref=raw_ref,
            overlay=overlay,
            history=history,
            service=service,
            query=prepared0.query,
            candidate=candidate,
            prepared=prepared,
            passport=passport,
            pending=pending,
        )
        native_case = sign_native_epoch_scenario(
            scenario,
            tmp_path / f"policy-{epoch_id:02d}",
            custodian=fixture_custodian,
            prior_admission_refs=tuple(prior_admission_refs),
        )
        prior_admission_refs.append(native_case.signed.evidence.evidence_record_ref)
        finalized = finalize_native_epoch_case(native_case)
        projections[entry.target_variable] = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=finalized.activated.receipt_ref,
            artifact_store=store,
            passport=passport,
            authority=authority,
        )
    return SimpleNamespace(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        overlay_path=overlay_path,
        artifact_store=store,
        authority=authority,
        overlay=overlay,
        projections=projections,
        entries=entries,
        native_service=native_case.service,
    )
