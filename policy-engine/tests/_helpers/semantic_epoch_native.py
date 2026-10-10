"""Real native epoch custody under fixture-only independent policy signatures.

The fixture uses the actual preparation, canonical history, qualification,
finalization and activation owners. It never constructs a positive production
receipt or installs a test chronology verifier.
"""

import base64
import hashlib
import json
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


def _semantic_handshake(
    store: FileSystemCAS,
    *,
    source_ref: object,
) -> tuple[
    epoch_contract.AcquisitionSemanticBoundaryCandidate,
    epoch.PreparedSemanticEpoch,
]:
    """Build exact pre-passport bytes without relying on a future passport ref."""

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
    candidate_statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement(
        source_record_ref=source_ref,
        source_record_content_hash=str(source_ref.artifact_id),
        scope_identity_ref=scope.scope_identity_ref,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_ref=query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=query.purpose_admission_cutoff_ref,
        requested_query_context_ref=query.requested_query_context_ref,
    )
    candidate_ref = put(
        epoch_contract.acquisition_semantic_candidate_bytes(candidate_statement),
        kind="epoch.acquisition_semantic_boundary_candidate",
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
        candidate_ref=candidate_ref,
        candidate_content_hash=(
            epoch_contract.acquisition_semantic_candidate_content_hash(candidate_statement)
        ),
        statement=candidate_statement,
    )
    manifest_values = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": query.scope_identity.model_dump(mode="json"),
        "authority_purpose": query.authority_purpose,
        "valid_effect_coordinate_ref": query.valid_effect_coordinate_ref,
        "visibility_knowledge_cutoff_ref": query.visibility_knowledge_cutoff_ref,
        "purpose_admission_cutoff_ref": query.purpose_admission_cutoff_ref,
        "requested_query_context_ref": query.requested_query_context_ref,
        "boundary_registry_content_hash": epoch._sha256(b"test-registry"),
        "facet_registry_content_hash": epoch._sha256(b"test-facets"),
        "boundary_denominator_hash": epoch._sha256(b"test-boundary"),
        "facet_denominator_hash": epoch._sha256(b"test-facet"),
        "boundary_semantic_hashes": [],
        "facet_semantic_hashes": [],
        "predecessor_refs": [],
    }
    manifest_hash = epoch._model_hash(
        epoch._MANIFEST_PREFIX,
        manifest_values,
    )
    semantic_manifest = epoch.SemanticEpochManifest(
        **manifest_values,
        manifest_content_hash=manifest_hash,
        epoch_ref=epoch._sha256(
            epoch._EPOCH_PREFIX,
            manifest_hash.encode(),
        ),
    )
    semantic_manifest_ref, _ = epoch._persist_model(
        store=store,
        value=semantic_manifest,
        kind="epoch.semantic_manifest",
    )
    boundary_receipt_ref = put(
        b"boundary-denominator",
        kind="epoch.boundary_denominator_receipt",
    )
    facet_receipt_ref = put(
        b"facet-denominator",
        kind="epoch.facet_denominator_receipt",
    )
    stamp = epoch_contract.SemanticEpochStamp(
        epoch_ref=semantic_manifest.epoch_ref,
        semantic_manifest_ref=semantic_manifest_ref,
        semantic_manifest_hash=semantic_manifest.manifest_content_hash,
        boundary_denominator_receipt_ref=boundary_receipt_ref,
        boundary_denominator_receipt_hash=epoch._sha256(b"boundary-denominator"),
        facet_denominator_receipt_ref=facet_receipt_ref,
        facet_denominator_receipt_hash=epoch._sha256(b"facet-denominator"),
        requested_query_context_ref=context_ref,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_ref=query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=query.purpose_admission_cutoff_ref,
        predicate_provenance_class="independently_reconciled",
    )
    bindings = (
        epoch.PreparedBoundaryCandidateBinding(
            registration_id="n13b-acquisition-native-history",
            candidate_refs=(candidate_ref,),
        ),
    )
    statement = {
        "query": query,
        "stamp": stamp,
        "boundary_candidate_refs": (candidate_ref,),
        "boundary_candidates_by_registration": bindings,
        "owner_denominator_receipt_refs": (),
        "status": "prepared",
    }
    canonical = epoch_contract.canonical_epoch_bytes(statement)
    prepared_ref = put(len(canonical).to_bytes(8, "big") + canonical, kind="epoch.prepared")
    prepared = epoch.PreparedSemanticEpoch(
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=epoch._model_hash(
            b"polisyos.epoch.prepared.v1\0",
            statement,
        ),
        **statement,
    )
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


def _authority(
    tmp_path: Path,
    *,
    source_rows: list[dict[str, object]],
):
    repo_root = tmp_path / "repo"
    graph = catalog_read_api.build_slice0_fixture_catalog_graph(repo_root / "catalog")
    graph.close()
    baseline = repo_root / "catalog/catalog.duckdb"
    source_path = repo_root / "evidence/local-distress.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(canonical_json_bytes(source_rows))
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
    declaration_values = {
        "schema_version": "polisyos.data_forge.local_source_rights_declaration.v1",
        "source_path": "evidence/local-distress.json",
        "source_content_sha256": _sha(source_path),
        "license_id": "CC-BY-4.0",
        "authority_id": "synthetic.fixture.owner",
        "rights_authority": "Synthetic fixture data owner",
        "authority_ref": "https://example.test/local-distress/terms",
    }
    rights_document_path = repo_root / "evidence/local-distress-rights.json"
    rights_declaration = catalog_read_api.build_local_source_rights_declaration(
        **declaration_values,
        signature_base64=base64.b64encode(
            signer.sign(canonical_json_bytes(declaration_values))
        ).decode("ascii"),
    )
    rights_document_path.write_text(
        json.dumps(
            rights_declaration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    rights_receipt = catalog_read_api.verify_local_source_rights(
        repo_root=repo_root,
        source_path="evidence/local-distress.json",
        rights_document_path="evidence/local-distress-rights.json",
    )
    rights_receipt_path = repo_root / "evidence/local-distress-rights-receipt.json"
    rights_receipt_path.write_text(
        json.dumps(
            rights_receipt.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    l5 = _write_l5(repo_root)
    entry = catalog_read_api.build_authority_entry(
        source_lane="local_lift",
        target_variable="cells.distress_score",
        landing_dataset_id="acquisition.local.corrected_firm_panels",
        landing_distribution_id="acquisition.local.corrected_firm_panels.json",
        raw_field="distress_score",
        raw_unit="ratio",
        canonical_unit="ratio",
        unit_transform="identity",
        unit_transform_ref="fabric://units/ratio-identity/v1",
        alignment_method="meta_analytic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=0.0,
        valid_max=1.0,
        evidence_refs=("repo://evidence/local-distress.json",),
        schema_contract_ref="repo://acquisition-registry#/local-distress/schema",
        schema_columns=(
            catalog_read_api.AuthoritySchemaColumn(
                name="country_code", logical_types=("string",), nullable=False
            ),
            catalog_read_api.AuthoritySchemaColumn(
                name="distress_score", logical_types=("number",), nullable=False
            ),
            catalog_read_api.AuthoritySchemaColumn(
                name="year", logical_types=("integer",), nullable=False
            ),
        ),
        l5_family_id="distress_enforcement",
        local_source_path="evidence/local-distress.json",
        local_source_sha256=_sha(source_path),
        local_license_id="CC-BY-4.0",
        local_rights_receipt_path="evidence/local-distress-rights-receipt.json",
        local_rights_receipt_sha256=_sha(rights_receipt_path),
        title="Owner-validated local distress observations",
        description="Content-bound local observations for the distress slot.",
        country_codes=("UA",),
        temporal_start="2024",
        temporal_end="2025",
    )
    registry = catalog_read_api.build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(entry,),
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
        entry,
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
    authority, entry = _authority(
        tmp_path,
        source_rows=source_rows or selected_rows,
    )
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
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "acquisition-overlay.duckdb",
    )
    overlay.initialize()
    facet_raw = epoch_contract.canonical_epoch_bytes({"semantic_value": "catalog-semantics"})
    facet_ref = store.put_bytes(
        facet_raw,
        ArtifactWriteOptions(
            kind="epoch.semantic_facet_source.v1",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
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
            "catalog_acquisition": (
                epoch.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                    owner=overlay,
                    artifacts=store,
                )
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
    candidate_ref = store.put_bytes(
        epoch_contract.acquisition_semantic_candidate_bytes(candidate_statement),
        ArtifactWriteOptions(
            kind="epoch.acquisition_semantic_boundary_candidate",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
        candidate_ref=candidate_ref,
        candidate_content_hash=(
            epoch_contract.acquisition_semantic_candidate_content_hash(candidate_statement)
        ),
        statement=candidate_statement,
    )
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
