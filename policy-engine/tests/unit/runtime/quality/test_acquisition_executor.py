from __future__ import annotations

import base64
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
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    OverlayAdmissionError,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane.evidence_journal import (
    canonical_json_bytes,
)
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
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
from tests._helpers.semantic_epoch_native import (
    _emit_admitted_ref,
    _fixture,
    _real_epoch_scenario,
    _semantic_handshake_from_passport,
    _sha,
    _valid_passport,
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

    def statement_projection() -> dict[str, object]:
        return semantic_epoch_runtime.PreparedSemanticEpoch.canonical_statement_projection(mapping)

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
        statement_projection=statement_projection,
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


def test_prepared_owner_projection_replays_through_both_admission_consumers(
    tmp_path: Path,
) -> None:
    """Persisted owner bytes pass handshake and overlay admission without serializer drift."""

    scenario = _real_epoch_scenario(tmp_path)
    persisted = epoch_contract.load_verified_epoch_statement(
        store=scenario.store,
        ref=scenario.prepared.prepared_epoch_ref,
        expected_kind="epoch.prepared",
    )
    projection = scenario.prepared.statement_projection()

    assert persisted["boundary_candidate_refs"][0]["manifest_profile_sha256"] is None
    assert (
        persisted["query"]["valid_effect_coordinate_evidence_ref"]["manifest_profile_sha256"]
        is None
    )
    assert epoch_contract.canonical_epoch_bytes(projection) == epoch_contract.canonical_epoch_bytes(
        persisted
    )
    assert scenario.pending.activation_state == "pending_epoch_activation"

    tampered = scenario.prepared.model_copy(update={"prepared_content_hash": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="prepared_semantic_epoch_cas_binding_mismatch"):
        _require_semantic_handshake(
            artifact_store=scenario.store,
            boundary_candidate=scenario.candidate,
            prepared_epoch=tampered,
        )
    with pytest.raises(OverlayAdmissionError, match="prepared_epoch_candidate_binding_mismatch"):
        scenario.overlay.admit_epoch(
            passport=scenario.passport,
            prepared_epoch=tampered,
            boundary_candidate=scenario.candidate,
            artifact_store=scenario.store,
            authority=scenario.authority,
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
