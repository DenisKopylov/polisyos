"""Semantic epoch owner graph binds every live-acquisition passport reference."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.contracts.chronology import _split_framed_records
from polisyos.runtime.quality import semantic_epoch
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionPassport,
    build_admission_passport,
)
from tests._helpers.semantic_epoch_native import _build_acquisition_epoch_fixture_service
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _live_execution_fixture,
    _live_semantic_handshake,
)


def test_existing_owner_receipt_reference_schemas_have_complete_roles() -> None:
    """Derived ArtifactRef subclasses participate in the owner-wide census."""
    for model_type, roles in semantic_epoch._OWNER_RECEIPT_REFERENCE_ROLES.items():
        declared: set[tuple[str, ...]] = set()
        for name, field in model_type.model_fields.items():
            if name != "query":
                declared.update(
                    semantic_epoch._declared_artifact_ref_paths(field.annotation, (name,))
                )
        assert declared == set(roles), model_type.__name__


def test_live_passport_source_role_survives_owner_snapshot_and_refuses_wrong_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay the selected source profile through the real Catalog owner graph."""
    authority, _, store, evidence, _, _ = _live_execution_fixture(tmp_path / "source")
    candidate, prepared = _live_semantic_handshake(store, evidence, authority=authority)
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=authority,
        boundary_candidate=candidate,
        prepared_epoch=prepared,
        live_source_execution=evidence,
    )
    service, overlay, _ = _build_acquisition_epoch_fixture_service(
        store=store, authority=authority, root=tmp_path / "epoch"
    )
    try:
        overlay.admit_epoch(
            passport=passport,
            prepared_epoch=prepared,
            boundary_candidate=candidate,
            artifact_store=store,
            authority=authority,
        )
        query = service.acquisition_owner_query(query=prepared.query)
        membership = overlay.resolve_native_membership(query=query)
        raw_snapshot = overlay.load_acquisition_owner_snapshot(
            ref=membership.owner_source_snapshot_ref
        )
        (raw_record,) = _split_framed_records(raw_snapshot)
        snapshot = json.loads(raw_record)
        semantic_epoch._validate_owner_snapshot_reference_graph(
            snapshot, owner_kind="catalog_acquisition"
        )

        prefix = ("rows", "*", "observed_passport_json")
        role_path = (*prefix, "live_source_execution", "raw_artifact_ref")
        roles = semantic_epoch._OWNER_SNAPSHOT_REFERENCE_ROLES["catalog_acquisition"]
        declared = semantic_epoch._model_artifact_ref_paths(AdmissionPassport)
        recorded = {path[len(prefix) :] for path in roles if path[: len(prefix)] == prefix}
        assert declared == recorded
        raw_ref = evidence.raw_artifact_ref
        assert raw_ref is not None and raw_ref.manifest_profile_sha256 is not None
        for field, actual_ref, expected_kind in (
            ("raw_artifact_ref", raw_ref, "fabric.acquisition.raw_evidence"),
            ("evidence_bundle_ref", evidence.evidence_bundle_ref, "fabric.evidence_bundle"),
            ("data_snapshot_ref", evidence.data_snapshot_ref, "fabric.data_snapshot"),
        ):
            ref_path = (*prefix, "live_source_execution", field)
            assert roles[ref_path] == expected_kind
            assert ("live_source_execution", field) in declared
            semantic_epoch._require_owner_reference_role(actual_ref, expected_kind=expected_kind)
            wrong_ref = actual_ref.model_copy(update={"kind": "fabric.world_payload"})
            with pytest.raises(ValueError, match="owner artifact role mismatch"):
                semantic_epoch._require_owner_reference_role(wrong_ref, expected_kind=expected_kind)

        missing_roles = dict(roles)
        del missing_roles[role_path]
        monkeypatch.setitem(
            semantic_epoch._OWNER_SNAPSHOT_REFERENCE_ROLES,
            "catalog_acquisition",
            missing_roles,
        )
        with pytest.raises(ValueError, match="passport schema reference roles are incomplete"):
            semantic_epoch._validate_owner_snapshot_reference_graph(
                snapshot, owner_kind="catalog_acquisition"
            )
    finally:
        overlay.close()


def test_catalog_passport_reference_schema_has_complete_roles() -> None:
    """Even an unset optional ref participates in the complete schema denominator."""
    prefix = ("rows", "*", "observed_passport_json")
    roles = semantic_epoch._OWNER_SNAPSHOT_REFERENCE_ROLES["catalog_acquisition"]
    embedded = {path[len(prefix) :] for path in roles if path[: len(prefix)] == prefix}
    assert semantic_epoch._model_artifact_ref_paths(AdmissionPassport) == embedded
    assert roles[(*prefix, "source_authority_entry", "source_unit_declaration_ref")] == (
        "fabric.source_metric_unit_declaration"
    )


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_source_unit_producer_bytes_reopen_through_the_epoch_codec(
    tmp_path: Path, version: str
) -> None:
    """A real candidate declaration is readable without becoming unit authority."""
    from polisyos.core import artifacts
    from polisyos.core.artifacts import ArtifactIntegrityError
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.fabric.connectors.contracts import (
        SourceMetricUnitDeclaration,
        load_source_metric_unit_declaration,
    )
    from polisyos.fabric.connectors.contracts.source_units import _declaration_json_payload
    from tests.unit.fabric.connectors.contracts.test_source_units import _create

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    current_ref = _create(store)
    current = load_source_metric_unit_declaration(store, current_ref)
    ref = artifacts.ArtifactRef.model_validate(current_ref.model_dump(mode="json"))
    if version == "1.0":
        # A retained legacy fixture uses the same owner model/serialization,
        # without relabeling the current 1.1 producer's original artifact.
        payload = current.model_dump(mode="json")
        payload.update(
            schema_version="fabric.source_metric_unit.v1",
            source_contract_content_hash=current.source_contract.content_hash,
        )
        payload.pop("source_contract_hash_profile")
        legacy = SourceMetricUnitDeclaration.model_validate(payload)
        ref = store.put_json(
            _declaration_json_payload(legacy),
            artifacts.ArtifactWriteOptions(
                kind=ref.kind,
                media_type=ref.media_type,
                schema=artifacts.SchemaInfo(name=current.ARTIFACT_SCHEMA_NAME, version="1.0"),
            ),
            CanonSpec(forbid_floats=False, exclude_none=False),
            return_selected_profile=True,
        )
        load_source_metric_unit_declaration(store, ref)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema.version == version and manifest.inputs == []
    codec = semantic_epoch._require_owner_reference_role(ref, expected_kind=ref.kind)
    assert codec.payload_format == "producer_json" and codec.canon == manifest.canon
    reader = artifacts.FileSystemCAS.open_existing_read_only(store.root)
    decoded = semantic_epoch._load_selected_acquisition_mapping(reader, ref, expected_kind=ref.kind)
    assert to_canonical_bytes(
        decoded, CanonSpec(forbid_floats=False, exclude_none=False)
    ) == store.get_bytes(ref)
    assert SourceMetricUnitDeclaration.model_validate(decoded).model_dump(mode="json") == (
        load_source_metric_unit_declaration(store, ref).model_dump(mode="json")
    )
    assert decoded["semantic_authority"] == decoded["acquisition_permission"] == "not_established"
    assert decoded["source_currentness"] == "not_established"
    wrong_kind = ref.model_copy(update={"kind": "fabric.data_snapshot"})
    wrong_media = ref.model_copy(update={"media_type": "application/octet-stream"})
    for wrong in (wrong_kind, wrong_media):
        with pytest.raises(ValueError, match=r"^owner artifact role mismatch$"):
            semantic_epoch._require_owner_reference_role(wrong, expected_kind=ref.kind)
    with pytest.raises(
        ValueError, match=r"^selected acquisition artifact selector is not established$"
    ):
        semantic_epoch._load_selected_acquisition_mapping(
            reader, ref.model_copy(update={"manifest_profile_sha256": None}), expected_kind=ref.kind
        )
    selected_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    held = selected_path.with_name(selected_path.name + ".held")
    selected_path.rename(held)
    try:
        with pytest.raises(FileNotFoundError):
            semantic_epoch._load_selected_acquisition_mapping(reader, ref, expected_kind=ref.kind)
    finally:
        held.rename(selected_path)
    assert (
        semantic_epoch._load_selected_acquisition_mapping(reader, ref, expected_kind=ref.kind)
        == decoded
    )
    blob, _ = store._paths(ref.artifact_id)
    held_blob = blob.with_name(blob.name + ".held")
    blob.rename(held_blob)
    try:
        blob.write_bytes(b'{"corrupt":true}')
        with pytest.raises(ArtifactIntegrityError, match=r"^Blob sha256 mismatch for "):
            semantic_epoch._load_selected_acquisition_mapping(reader, ref, expected_kind=ref.kind)
    finally:
        blob.unlink()
        held_blob.rename(blob)
    assert (
        semantic_epoch._load_selected_acquisition_mapping(reader, ref, expected_kind=ref.kind)
        == decoded
    )


@pytest.mark.parametrize("mutation", ["schema_name", "schema_version", "canon", "inputs"])
def test_source_unit_codec_refuses_a_foreign_selected_manifest(
    tmp_path: Path, mutation: str
) -> None:
    """The new kind does not relax selected profile/schema/direct-edge checks."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core import artifacts
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from tests.unit.fabric.connectors.contracts.test_source_units import _create

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    original = _create(store)
    manifest = store.get_manifest(original)
    payload = from_canonical_bytes(store.get_bytes(original))
    spec = CanonSpec(forbid_floats=False, exclude_none=(mutation == "canon"))
    schema = artifacts.SchemaInfo(
        name="foreign.SourceMetricUnitDeclaration"
        if mutation == "schema_name"
        else manifest.artifact_schema.name,
        version="9.0" if mutation == "schema_version" else manifest.artifact_schema.version,
    )
    extra_ref = store.put_json(
        {"test_owned_input": True},
        artifacts.ArtifactWriteOptions(
            kind="test.epoch_codec_extra_input", media_type="application/json"
        ),
        return_selected_profile=True,
    )
    foreign = store.put_json(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=original.kind,
            media_type=original.media_type,
            schema=schema,
            producer=manifest.producer,
            inputs=[artifacts.input_ref_from_artifact_ref(extra_ref, role="unexpected")]
            if mutation == "inputs"
            else None,
        ),
        spec,
        return_selected_profile=True,
    )
    assert artifacts.artifact_ref_identity_key(foreign) != artifacts.artifact_ref_identity_key(
        original
    )
    if mutation != "canon":
        assert foreign.artifact_id == original.artifact_id
    with pytest.raises(CanonicalProfileRefusalError) as failure:
        semantic_epoch._load_selected_acquisition_mapping(
            store, foreign, expected_kind=original.kind
        )
    assert failure.value.code == "canon_profile_typed_artifact_profile_mismatch"
