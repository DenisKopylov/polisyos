from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    canonical_json_bytes,
    derive_live_http_budget,
)
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
from polisyos.runtime.quality import chronology_qualification
from polisyos.runtime.quality import semantic_epoch as semantic_epoch_runtime
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionStatus,
    ObservationProvenanceClass,
    SemanticEpochAdmissionResolutionError,
    _require_semantic_handshake,
    admit_acquisition_with_semantic_epoch,
    build_admission_passport,
    build_metadata_schema_profile,
    derive_observation_provenance_rejections,
    persist_acquisition_quarantine,
    revalidate_admission_passport,
)
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)


@pytest.mark.parametrize(
    ("observation_class", "expected"),
    [
        (ObservationProvenanceClass.OBSERVED, ()),
        (ObservationProvenanceClass.PROXY, ()),
        (
            ObservationProvenanceClass.DERIVED,
            ("derived_cannot_enter_observed_overlay",),
        ),
        (
            ObservationProvenanceClass.MODEL_OUTPUT,
            ("model_output_not_observation",),
        ),
    ],
)
def test_observation_provenance_rejections_are_structural(
    observation_class: ObservationProvenanceClass,
    expected: tuple[str, ...],
) -> None:
    assert derive_observation_provenance_rejections(observation_class) == expected


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
    semantic_epoch_runtime.PreparedSemanticEpoch,
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
    scope = semantic_epoch_runtime.build_epoch_scope_identity(
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
    query = semantic_epoch_runtime.EpochResolutionQuery(
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
        "boundary_registry_content_hash": semantic_epoch_runtime._sha256(b"test-registry"),
        "facet_registry_content_hash": semantic_epoch_runtime._sha256(b"test-facets"),
        "boundary_denominator_hash": semantic_epoch_runtime._sha256(b"test-boundary"),
        "facet_denominator_hash": semantic_epoch_runtime._sha256(b"test-facet"),
        "boundary_semantic_hashes": [],
        "facet_semantic_hashes": [],
        "predecessor_refs": [],
    }
    manifest_hash = semantic_epoch_runtime._model_hash(
        semantic_epoch_runtime._MANIFEST_PREFIX,
        manifest_values,
    )
    semantic_manifest = semantic_epoch_runtime.SemanticEpochManifest(
        **manifest_values,
        manifest_content_hash=manifest_hash,
        epoch_ref=semantic_epoch_runtime._sha256(
            semantic_epoch_runtime._EPOCH_PREFIX,
            manifest_hash.encode(),
        ),
    )
    semantic_manifest_ref, _ = semantic_epoch_runtime._persist_model(
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
        boundary_denominator_receipt_hash=semantic_epoch_runtime._sha256(b"boundary-denominator"),
        facet_denominator_receipt_ref=facet_receipt_ref,
        facet_denominator_receipt_hash=semantic_epoch_runtime._sha256(b"facet-denominator"),
        requested_query_context_ref=context_ref,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_ref=query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=query.purpose_admission_cutoff_ref,
        predicate_provenance_class="independently_reconciled",
    )
    bindings = (
        semantic_epoch_runtime.PreparedBoundaryCandidateBinding(
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
    prepared = semantic_epoch_runtime.PreparedSemanticEpoch(
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=semantic_epoch_runtime._model_hash(
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
    semantic_epoch_runtime.PreparedSemanticEpoch,
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
    prepared = semantic_epoch_runtime.PreparedSemanticEpoch(
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=semantic_epoch_runtime._model_hash(
            b"polisyos.epoch.prepared.v1\0",
            prepared_mapping,
        ),
        **prepared_mapping,
    )
    return candidate, prepared


def _persist_fabricated_prepared(
    store: FileSystemCAS,
    *,
    candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
    query: semantic_epoch_runtime.EpochResolutionQuery,
    mapping: dict[str, object],
) -> object:
    canonical = epoch_contract.canonical_epoch_bytes(mapping)
    prepared_ref = store.put_bytes(
        len(canonical).to_bytes(8, "big") + canonical,
        ArtifactWriteOptions(
            kind="epoch.prepared",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    prepared_hash = epoch_contract.epoch_semantic_content_hash(
        domain="polisyos.epoch.prepared.v1",
        value=mapping,
    )

    def model_dump(*, mode: str) -> dict[str, object]:
        assert mode == "python"
        return {
            **mapping,
            "prepared_epoch_ref": prepared_ref,
            "prepared_content_hash": prepared_hash,
        }

    stamp_mapping = mapping["stamp"]
    assert isinstance(stamp_mapping, dict)
    return SimpleNamespace(
        prepared_epoch_ref=prepared_ref,
        prepared_content_hash=prepared_hash,
        query=query,
        stamp=epoch_contract.SemanticEpochStamp.model_construct(**stamp_mapping),
        boundary_candidate_refs=(candidate.candidate_ref,),
        status="prepared",
        model_dump=model_dump,
    )


@pytest.mark.parametrize(
    "predicate_class",
    ["consumer_asserted", "institutionally_supplied", "not_established"],
)
def test_non_authority_predicate_stamp_gets_exact_typed_refusal(
    tmp_path: Path,
    predicate_class: str,
) -> None:
    passport, store, _, _, _ = _fixture(tmp_path)
    candidate, prepared = _semantic_handshake_from_passport(passport, store)
    raw = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=prepared.prepared_epoch_ref,
        expected_kind="epoch.prepared",
    )
    stamp = raw["stamp"]
    assert isinstance(stamp, dict)
    stamp["predicate_provenance_class"] = predicate_class
    fabricated = _persist_fabricated_prepared(
        store,
        candidate=candidate,
        query=prepared.query,
        mapping=raw,
    )

    with pytest.raises(SemanticEpochAdmissionResolutionError) as captured:
        _require_semantic_handshake(
            artifact_store=store,
            boundary_candidate=candidate,
            prepared_epoch=fabricated,
        )
    assert captured.value.code == "predicate_not_authority_grade"


def test_prepared_stamp_epoch_ref_mismatch_gets_exact_typed_refusal(
    tmp_path: Path,
) -> None:
    passport, store, _, _, _ = _fixture(tmp_path)
    candidate, prepared = _semantic_handshake_from_passport(passport, store)
    identity = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": prepared.query.scope_identity.model_dump(mode="json"),
        "authority_purpose": prepared.query.authority_purpose,
        "valid_effect_coordinate_ref": prepared.query.valid_effect_coordinate_ref,
        "visibility_knowledge_cutoff_ref": prepared.query.visibility_knowledge_cutoff_ref,
        "purpose_admission_cutoff_ref": prepared.query.purpose_admission_cutoff_ref,
        "requested_query_context_ref": prepared.query.requested_query_context_ref,
        "boundary_registry_content_hash": semantic_epoch_runtime._sha256(b"registry"),
        "facet_registry_content_hash": semantic_epoch_runtime._sha256(b"facets"),
        "boundary_denominator_hash": semantic_epoch_runtime._sha256(b"boundary"),
        "facet_denominator_hash": semantic_epoch_runtime._sha256(b"facet"),
        "boundary_semantic_hashes": [],
        "facet_semantic_hashes": [],
        "predecessor_refs": [],
    }
    manifest_hash = semantic_epoch_runtime._model_hash(
        semantic_epoch_runtime._MANIFEST_PREFIX,
        identity,
    )
    manifest = semantic_epoch_runtime.SemanticEpochManifest(
        **identity,
        manifest_content_hash=manifest_hash,
        epoch_ref=semantic_epoch_runtime._sha256(
            semantic_epoch_runtime._EPOCH_PREFIX,
            manifest_hash.encode(),
        ),
    )
    manifest_ref, _ = semantic_epoch_runtime._persist_model(
        store=store,
        value=manifest,
        kind="epoch.semantic_manifest",
    )
    raw = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=prepared.prepared_epoch_ref,
        expected_kind="epoch.prepared",
    )
    stamp = raw["stamp"]
    assert isinstance(stamp, dict)
    stamp["semantic_manifest_ref"] = manifest_ref.model_dump(mode="json")
    stamp["semantic_manifest_hash"] = manifest.manifest_content_hash
    stamp["epoch_ref"] = "sha256:" + "0" * 64
    fabricated = _persist_fabricated_prepared(
        store,
        candidate=candidate,
        query=prepared.query,
        mapping=raw,
    )

    with pytest.raises(SemanticEpochAdmissionResolutionError) as captured:
        _require_semantic_handshake(
            artifact_store=store,
            boundary_candidate=candidate,
            prepared_epoch=fabricated,
        )
    assert captured.value.code == "epoch_ref_mismatch"


def test_foreign_native_query_gets_exact_query_context_refusal(tmp_path: Path) -> None:
    passport, store, authority, _, raw_ref = _fixture(tmp_path)
    _, prepared = _semantic_handshake_from_passport(passport, store)
    query = prepared.query

    def coordinate(attribute: str, role: str) -> tuple[str, bytes, str]:
        evidence_ref = getattr(query, f"{attribute}_evidence_ref")
        raw = store.get_bytes(evidence_ref.artifact_id)
        return (
            evidence_ref.kind,
            raw,
            epoch_contract.native_coordinate_ref(
                family="catalog_acquisition",
                role=role,
                schema_profile=evidence_ref.kind,
                coordinate_bytes=raw,
            ),
        )

    valid = coordinate("valid_effect_coordinate", "valid_effect")
    visibility = coordinate("visibility_knowledge_cutoff", "visibility_knowledge_cutoff")
    admission = coordinate("purpose_admission_cutoff", "purpose_admission_cutoff")
    foreign_query = epoch_contract.AcquisitionBoundaryResolutionQuery(
        scope_identity_ref=query.scope_identity.scope_identity_ref,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_schema_profile=valid[0],
        valid_effect_coordinate_bytes=valid[1],
        valid_effect_coordinate_ref=valid[2],
        visibility_knowledge_cutoff_schema_profile=visibility[0],
        visibility_knowledge_cutoff_bytes=visibility[1],
        visibility_knowledge_cutoff_ref=visibility[2],
        purpose_admission_cutoff_schema_profile=admission[0],
        purpose_admission_cutoff_bytes=admission[1],
        purpose_admission_cutoff_ref=admission[2],
        requested_query_context_ref="sha256:" + "f" * 64,
    )

    class ForeignQueryService:
        def acquisition_owner_query(self, *, query: object) -> object:
            del query
            return foreign_query

        def prepare_acquisition_candidate(self, **_: object) -> object:
            raise AssertionError("foreign query reached epoch preparation")

    with pytest.raises(SemanticEpochAdmissionResolutionError) as captured:
        admit_acquisition_with_semantic_epoch(
            epoch_id=2,
            raw_evidence_ref=raw_ref,
            artifact_store=store,
            authority=authority,
            overlay=object(),
            epoch_service=ForeignQueryService(),
            epoch_query=query,
        )
    assert captured.value.code == "query_context_mismatch"


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
    service = semantic_epoch_runtime.SemanticEpochService(
        boundary_registry=semantic_epoch_runtime.build_boundary_registry(
            (
                semantic_epoch_runtime.EpochBoundarySourceRegistration(
                    registration_id="n13b-acquisition-native-history",
                    owner_kind="catalog_acquisition",
                    owner_source_ref=semantic_epoch_runtime._sha256(b"test-catalog-owner"),
                    opaque_scope_binding_ref=semantic_epoch_runtime._sha256(b"test-catalog-scope"),
                ),
            )
        ),
        boundary_adapters={
            "catalog_acquisition": (
                semantic_epoch_runtime.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                    owner=overlay,
                    artifacts=store,
                )
            )
        },
        facet_registry=semantic_epoch_runtime.build_facet_registry(
            (
                semantic_epoch_runtime.SemanticFacetRegistration(
                    facet_id="catalog-semantics",
                    source_binding_ref=str(facet_ref.artifact_id),
                ),
            )
        ),
        facet_provider=semantic_epoch_runtime.ArtifactSemanticFacetProvider(
            artifacts=store,
            source_refs={str(facet_ref.artifact_id): facet_ref},
        ),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=(
            semantic_epoch_runtime.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
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


def _test_positive_production_receipt(scenario: SimpleNamespace):
    """Persist a test-only positive receipt after real owner re-enumeration.

    This helper exercises Data Forge's activation transaction.  It is not a
    production policy appointment: the production composition is separately
    required to return ``policy_admission_missing``.
    """

    admitted_ref = _emit_admitted_ref(scenario)

    def put_dummy(*, kind: str):
        return scenario.store.put_bytes(
            kind.encode("utf-8"),
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )

    statement = semantic_epoch_runtime.SemanticEpochProductionReceipt(
        production_mode="acquisition_finalization",
        status="appended",
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
        epoch_ref=scenario.prepared.stamp.epoch_ref,
        semantic_manifest_ref=scenario.prepared.stamp.semantic_manifest_ref,
        owner_denominator_receipt_refs=(),
        history_append_receipt_ref=put_dummy(kind="epoch.history_append_receipt"),
        chronology_bundle_ref=put_dummy(kind="chronology.full_prefix.bundle"),
        chronology_verification_ref=put_dummy(kind="chronology.verifier.result"),
        requested_query_context_ref=scenario.query.requested_query_context_ref,
        failure_codes=(),
    )
    return semantic_epoch_runtime.persist_semantic_epoch_production_receipt(
        store=scenario.store,
        receipt=statement,
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


def _activate_real_epoch_scenario(scenario: SimpleNamespace):
    """Activate one pending scenario through the real overlay transaction."""

    production = _test_positive_production_receipt(scenario)
    activated = scenario.overlay.activate_semantic_epoch(
        pending_receipt=scenario.pending,
        production_receipt=production,
        artifact_store=scenario.store,
    )
    return production, activated


def _second_real_epoch_scenario(
    scenario: SimpleNamespace,
    *,
    epoch_id: int = 2,
) -> SimpleNamespace:
    """Persist another ordinal over the same semantic candidate and owner bytes."""

    passport = build_admission_passport(
        epoch_id=epoch_id,
        raw_evidence_ref=scenario.raw_ref,
        artifact_store=scenario.store,
        raw_artifact_id=scenario.passport.raw_artifact_id,
        authority=scenario.authority,
        boundary_candidate=scenario.candidate,
        prepared_epoch=scenario.prepared,
    )
    pending = scenario.overlay.admit_epoch(
        passport=passport,
        prepared_epoch=scenario.prepared,
        boundary_candidate=scenario.candidate,
        artifact_store=scenario.store,
        authority=scenario.authority,
    )
    values = dict(vars(scenario))
    values.update(passport=passport, pending=pending)
    return SimpleNamespace(**values)


def test_passport_uses_resolved_semantic_stamp_not_supplied_epoch_ref(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)

    assert scenario.passport.semantic_epoch_stamp == scenario.prepared.stamp
    assert scenario.passport.semantic_epoch_ref == scenario.prepared.stamp.epoch_ref
    payload = scenario.passport.model_dump(mode="python")
    with pytest.raises(ValidationError, match="semantic epoch ref differs"):
        type(scenario.passport)(**{**payload, "semantic_epoch_ref": "sha256:" + "0" * 64})


def test_prepared_epoch_identity_excludes_future_passport_ref(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    prepared_raw = scenario.store.get_bytes(scenario.prepared.prepared_epoch_ref.artifact_id)

    assert b"passport_id" not in prepared_raw
    assert b"passport_ref" not in prepared_raw
    assert scenario.passport.passport_id.encode("utf-8") not in prepared_raw


def test_preparation_succeeds_before_operational_ordinal_exists(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    prepared_raw = scenario.store.get_bytes(scenario.prepared.prepared_epoch_ref.artifact_id)
    prepared_mapping = from_canonical_bytes(prepared_raw[8:])

    assert scenario.prepared.status == "prepared"
    assert isinstance(prepared_mapping, dict)
    assert "epoch_id" not in prepared_mapping


def test_finalization_reenumerates_admitted_owner_denominator(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "DELETE FROM ds_observations WHERE observation_id = "
            "(SELECT observation_id FROM ds_observations ORDER BY observation_id LIMIT 1)"
        )
    finally:
        con.close()
    receipt = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )

    assert receipt.status == "not_established"
    assert receipt.failure_codes == ("epoch_scope_unresolved",)


def test_finalization_binds_passport_to_stable_candidate_without_rehashing_epoch(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    receipt = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )

    assert receipt.status == "not_established"
    assert receipt.failure_codes == ("policy_admission_missing",)
    assert receipt.prepared_epoch_ref == scenario.prepared.prepared_epoch_ref
    assert receipt.admitted_boundary_evidence_ref == admitted_ref
    assert scenario.passport.semantic_epoch_ref == scenario.prepared.stamp.epoch_ref


def test_service_persists_native_history_and_common_proof_before_return(
    tmp_path: Path,
) -> None:
    """The absent owner stops before a positive history/proof claim is persisted."""

    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    receipt = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )
    history = scenario.history.resolve_scope_history(
        scope=scenario.query.scope_identity,
        authority_purpose=scenario.query.authority_purpose,
    )

    assert receipt.failure_codes == ("policy_admission_missing",)
    assert receipt.history_append_receipt_ref is None
    assert receipt.chronology_bundle_ref is None
    assert receipt.chronology_verification_ref is None
    assert history.entries == ()


def test_passport_is_owner_resolved_measured_and_content_derived(tmp_path: Path) -> None:
    passport, _, authority, _ = _valid_passport(tmp_path)

    assert passport.status is AdmissionStatus.ADMITTED_DEGRADED
    assert passport.rejection_codes == ()
    assert passport.measured_profile.inference_mode == "measured_quarantine"
    assert passport.measured_profile.sample_row_count == 2
    assert passport.raw_evidence_verified is True
    assert passport.cas_evidence_verified is True
    assert passport.schema_validation.conformant is True
    assert passport.source_authority_verified is True
    assert passport.license_evidence.authority_ref == "repo://evidence/local-distress-rights.json"
    assert passport.license_evidence.authority_content_sha256 == _sha(
        authority.repo_root / "evidence/local-distress-rights.json"
    )
    assert passport.l5_trust.tier == "authoritative_partial_coverage"
    assert passport.registration == authority.resolve(passport.authority_entry_id).registration
    assert passport.passport_id.startswith("passport:sha256:")

    payload = passport.model_dump(mode="python")
    with pytest.raises(ValidationError, match="status must be recomputed"):
        type(passport)(**{**payload, "status": "admitted"})
    with pytest.raises(ValidationError, match="passport identity must be recomputed"):
        type(passport)(**{**payload, "passport_id": "passport:sha256:" + "0" * 64})


def test_schema_drift_missing_cas_and_source_drift_each_fail_closed(
    tmp_path: Path,
) -> None:
    schema_drift, _, _, _, _ = _fixture(
        tmp_path / "schema",
        rows=[
            {
                "country_code": "UA",
                "year": 2024,
                "distress_score": 0.42,
                "unexpected": "drift",
            }
        ],
    )
    assert schema_drift.status is AdmissionStatus.QUARANTINED
    assert any("unexpected_response_field" in code for code in schema_drift.rejection_codes)

    missing_cas, _, _, _, _ = _fixture(
        tmp_path / "missing-cas",
        raw_artifact_override="sha256:" + "0" * 64,
    )
    assert missing_cas.status is AdmissionStatus.QUARANTINED
    assert "raw_cas_evidence_unresolved" in missing_cas.rejection_codes

    source_drift, _, _, _, _ = _fixture(
        tmp_path / "source-drift",
        rows=[{"country_code": "UA", "year": 2024, "distress_score": 0.2}],
        source_rows=[{"country_code": "UA", "year": 2024, "distress_score": 0.9}],
    )
    assert source_drift.status is AdmissionStatus.QUARANTINED
    assert "source_authority_unverified" in source_drift.rejection_codes


def test_pii_and_metadata_only_profiles_never_earn_admission(tmp_path: Path) -> None:
    pii, _, _, _, _ = _fixture(
        tmp_path / "pii",
        rows=[
            {
                "country_code": "UA",
                "year": 2024,
                "distress_score": 0.42,
                "email": "alice@example.com",
            }
        ],
    )
    assert pii.status is AdmissionStatus.QUARANTINED
    assert "pii_scan_blocked" in pii.rejection_codes

    passport, _, _, _ = _valid_passport(tmp_path / "metadata")
    metadata_only = build_metadata_schema_profile(
        dataset_id=passport.measured_profile.dataset_id,
        distribution_id=passport.measured_profile.distribution_id,
        source_profile_id=passport.measured_profile.source_profile_id,
        columns=passport.measured_profile.columns,
        raw_evidence_event_sha256=passport.raw_evidence_ref.event_sha256,
    )
    forged = passport.model_copy(update={"measured_profile": metadata_only})
    with pytest.raises(ValidationError):
        type(passport).model_validate(forged.model_dump(mode="python"))


def test_fabricated_raw_ref_and_derived_as_observed_fail_revalidation(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path)
    fake_ref = passport.raw_evidence_ref.model_copy(update={"event_sha256": "sha256:" + "0" * 64})
    forged = passport.model_copy(update={"raw_evidence_ref": fake_ref})
    with pytest.raises(ValueError, match="raw_evidence_ref_unresolved"):
        revalidate_admission_passport(
            forged,
            artifact_store=store,
            authority=authority,
        )

    candidate = passport.model_copy(
        update={"observation_class": ObservationProvenanceClass.MODEL_OUTPUT}
    )
    with pytest.raises(ValidationError):
        type(passport).model_validate(candidate.model_dump(mode="python"))


def test_quarantined_passport_uses_existing_fabric_quarantine_owner(tmp_path: Path) -> None:
    passport, store, _, _, _ = _fixture(
        tmp_path,
        raw_artifact_override="sha256:" + "0" * 64,
    )

    persisted = persist_acquisition_quarantine(
        store,
        passport=passport,
        raw_payload={"raw": "quarantine-only"},
    )
    records = list_quarantine_records(store)

    assert persisted.artifact_id is not None
    assert len(records) == 1
    assert records[0][1].reason == "raw_cas_evidence_unresolved"


def test_revalidation_reopens_registry_and_l5_owners(tmp_path: Path) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path)
    revalidated = revalidate_admission_passport(
        passport,
        artifact_store=store,
        authority=authority,
    )
    assert revalidated == passport

    authority.l5_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="acquisition_authority_unresolved"):
        revalidate_admission_passport(
            passport,
            artifact_store=store,
            authority=authority,
        )


def test_local_license_requires_resolved_owner_declaration(tmp_path: Path) -> None:
    passport, store, authority, entry = _valid_passport(tmp_path / "drift")
    rights_path = authority.repo_root / "evidence/local-distress-rights.json"
    rights_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="acquisition_authority_unresolved"):
        revalidate_admission_passport(
            passport,
            artifact_store=store,
            authority=authority,
        )

    values = entry.model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        catalog_read_api.AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["local_rights_receipt_path"] = None
    values["local_rights_receipt_sha256"] = None
    with pytest.raises(ValidationError, match="content-bound rights evidence"):
        catalog_read_api.build_authority_entry(**values)

    trust_passport, trust_store, trust_authority, _ = _valid_passport(tmp_path / "trust-drift")
    trust_authority.local_rights_trust_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="acquisition_authority_unresolved"):
        revalidate_admission_passport(
            trust_passport,
            artifact_store=trust_store,
            authority=trust_authority,
        )

    provision_passport, provision_store, provision_authority, _ = _valid_passport(
        tmp_path / "provision-drift"
    )
    provision_path = (
        provision_authority.repo_root / catalog_read_api.DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    )
    provision_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="acquisition_authority_unresolved"):
        revalidate_admission_passport(
            provision_passport,
            artifact_store=provision_store,
            authority=provision_authority,
        )


def test_passport_license_projection_cannot_replace_owner_authority(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path)
    forged_license = passport.license_evidence.model_copy(
        update={"authority_ref": "https://attacker.invalid/fake-license"}
    )
    forged = passport.model_copy(update={"license_evidence": forged_license})

    with pytest.raises(ValueError, match="license_authority_drift"):
        revalidate_admission_passport(
            forged,
            artifact_store=store,
            authority=authority,
        )


def test_coordinated_rights_and_acquisition_rebaseline_cannot_replace_trust_anchor(
    tmp_path: Path,
) -> None:
    _, _, authority, entry = _valid_passport(tmp_path)
    attacker = Ed25519PrivateKey.generate()
    public_key = attacker.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    malicious_trust = catalog_read_api.build_local_rights_trust_registry(
        authorities=(
            catalog_read_api.LocalRightsTrustedAuthority(
                authority_id="attacker.owner",
                rights_authority="Attacker owner",
                authority_ref="https://attacker.invalid/fake-terms",
                ed25519_public_key_base64=base64.b64encode(public_key).decode("ascii"),
                admissible_license_ids=("CC-BY-4.0",),
            ),
        )
    )
    authority.local_rights_trust_path.write_text(
        json.dumps(
            malicious_trust.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    declaration_values = {
        "schema_version": "polisyos.data_forge.local_source_rights_declaration.v1",
        "source_path": "evidence/local-distress.json",
        "source_content_sha256": _sha(authority.repo_root / "evidence/local-distress.json"),
        "license_id": "CC-BY-4.0",
        "authority_id": "attacker.owner",
        "rights_authority": "Attacker owner",
        "authority_ref": "https://attacker.invalid/fake-terms",
    }
    declaration = catalog_read_api.build_local_source_rights_declaration(
        **declaration_values,
        signature_base64=base64.b64encode(
            attacker.sign(canonical_json_bytes(declaration_values))
        ).decode("ascii"),
    )
    rights_document = authority.repo_root / "evidence/local-distress-rights.json"
    rights_document.write_text(
        json.dumps(
            declaration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    receipt = catalog_read_api.verify_local_source_rights(
        repo_root=authority.repo_root,
        source_path="evidence/local-distress.json",
        rights_document_path="evidence/local-distress-rights.json",
    )
    receipt_path = authority.repo_root / "evidence/local-distress-rights-receipt.json"
    receipt_path.write_text(
        json.dumps(
            receipt.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    values = entry.model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        catalog_read_api.AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["local_rights_receipt_sha256"] = _sha(receipt_path)
    malicious_entry = catalog_read_api.build_authority_entry(**values)
    malicious_registry = catalog_read_api.build_authority_registry(
        baseline_content_sha256=_sha(authority.baseline_path),
        l5_measurement_registry_sha256=_sha(authority.l5_path),
        entries=(malicious_entry,),
    )
    authority.registry_path.write_text(
        json.dumps(
            malicious_registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        catalog_read_api.AcquisitionAuthorityError,
        match="local_rights_trust_registry_content_drift",
    ):
        authority.resolve(malicious_entry.entry_id)


def test_rights_verifier_rejects_declaration_for_different_source(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    source = repo_root / "evidence/source.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("[]", encoding="utf-8")
    declaration = catalog_read_api.build_local_source_rights_declaration(
        schema_version="polisyos.data_forge.local_source_rights_declaration.v1",
        source_path="evidence/other.json",
        source_content_sha256=_sha(source),
        license_id="CC-BY-4.0",
        authority_id="synthetic.fixture.owner",
        rights_authority="Synthetic fixture data owner",
        authority_ref="https://example.test/source/terms",
        signature_base64=base64.b64encode(b"0" * 64).decode("ascii"),
    )
    rights = repo_root / "evidence/source-rights.json"
    rights.write_text(
        json.dumps(
            declaration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        catalog_read_api.AcquisitionAuthorityError,
        match="local_rights_document_source_drift",
    ):
        catalog_read_api.verify_local_source_rights(
            repo_root=repo_root,
            source_path="evidence/source.json",
            rights_document_path="evidence/source-rights.json",
        )


def test_valid_shaped_self_attested_rights_fail_signature_verification(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    evidence = repo_root / "evidence"
    evidence.mkdir(parents=True)
    source = evidence / "source.json"
    source.write_text("[]", encoding="utf-8")
    trusted_signer = Ed25519PrivateKey.generate()
    trusted_public_key = trusted_signer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    trust_registry = catalog_read_api.build_local_rights_trust_registry(
        authorities=(
            catalog_read_api.LocalRightsTrustedAuthority(
                authority_id="trusted.owner",
                rights_authority="Trusted owner",
                authority_ref="https://example.test/trusted/terms",
                ed25519_public_key_base64=base64.b64encode(trusted_public_key).decode("ascii"),
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
        "source_path": "evidence/source.json",
        "source_content_sha256": _sha(source),
        "license_id": "CC-BY-4.0",
        "authority_id": "trusted.owner",
        "rights_authority": "Trusted owner",
        "authority_ref": "https://example.test/trusted/terms",
    }
    attacker = Ed25519PrivateKey.generate()
    declaration = catalog_read_api.build_local_source_rights_declaration(
        **declaration_values,
        signature_base64=base64.b64encode(
            attacker.sign(canonical_json_bytes(declaration_values))
        ).decode("ascii"),
    )
    rights = evidence / "source-rights.json"
    rights.write_text(
        json.dumps(
            declaration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        catalog_read_api.AcquisitionAuthorityError,
        match="local_rights_signature_invalid",
    ):
        catalog_read_api.verify_local_source_rights(
            repo_root=repo_root,
            source_path="evidence/source.json",
            rights_document_path="evidence/source-rights.json",
        )

    disallowed_values = {
        **declaration_values,
        "license_id": "ODC-BY-1.0",
    }
    disallowed = catalog_read_api.build_local_source_rights_declaration(
        **disallowed_values,
        signature_base64=base64.b64encode(
            trusted_signer.sign(canonical_json_bytes(disallowed_values))
        ).decode("ascii"),
    )
    rights.write_text(
        json.dumps(
            disallowed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        catalog_read_api.AcquisitionAuthorityError,
        match="local_rights_signing_authority_drift",
    ):
        catalog_read_api.verify_local_source_rights(
            repo_root=repo_root,
            source_path="evidence/source.json",
            rights_document_path="evidence/source-rights.json",
        )
