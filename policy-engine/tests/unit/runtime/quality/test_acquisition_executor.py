from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    canonical_json_bytes,
    derive_live_http_budget,
)
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionStatus,
    ObservationProvenanceClass,
    build_admission_passport,
    build_metadata_schema_profile,
    persist_acquisition_quarantine,
    revalidate_admission_passport,
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
        local_rights_trust_anchor_sha256=_sha(trust_path),
    )
    provision_path = (
        repo_root / catalog_read_api.DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    )
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
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        raw_artifact_id=raw_artifact_override or str(artifact.artifact_id),
        authority=authority,
    )
    return passport, store, authority, entry, raw_ref


def _valid_passport(tmp_path: Path):
    passport, store, authority, entry, _ = _fixture(tmp_path)
    return passport, store, authority, entry


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
    assert (
        passport.license_evidence.authority_ref
        == "repo://evidence/local-distress-rights.json"
    )
    assert passport.license_evidence.authority_content_sha256 == _sha(
        authority.repo_root / "evidence/local-distress-rights.json"
    )
    assert passport.l5_trust.tier == "authoritative_partial_coverage"
    assert passport.registration == authority.resolve(
        passport.authority_entry_id
    ).registration
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
    fake_ref = passport.raw_evidence_ref.model_copy(
        update={"event_sha256": "sha256:" + "0" * 64}
    )
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

    trust_passport, trust_store, trust_authority, _ = _valid_passport(
        tmp_path / "trust-drift"
    )
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
        provision_authority.repo_root
        / catalog_read_api.DEFAULT_ACQUISITION_AUTHORITY_PROVISION
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
        "source_content_sha256": _sha(
            authority.repo_root / "evidence/local-distress.json"
        ),
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
                ed25519_public_key_base64=base64.b64encode(
                    trusted_public_key
                ).decode("ascii"),
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
