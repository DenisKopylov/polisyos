from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.ukraine.manifests import (
    D5ReleaseContentRef,
    D5ReleaseHandoffRequest,
    D5ReleaseProducerFacts,
)
from polisyos.data_forge.read_api.ukraine import (
    UkraineJSONSnapshotProvenance,
    UkraineJSONSnapshotRefusalError,
    VerifiedUkraineReleaseArtifact,
    VerifiedUkraineReleaseArtifacts,
    VerifiedUkraineStageArtifact,
    VerifiedUkraineStageArtifacts,
    read_ukraine_json_snapshot,
)


class _StatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    state_ids: list[str]


def test_profileless_stage_json_is_a_typed_candidate_with_exact_raw_identity(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = b'{"state_ids":["a","b"]}'
    digest = hashlib.sha256(payload).hexdigest()
    ref = store.put_bytes(
        payload,
        PutOptions(kind="data_forge.ukraine.stage_output_snapshot", media_type="application/json"),
        return_selected_profile=True,
    )
    artifact = VerifiedUkraineStageArtifact(
        source_path="targets.json",
        content_ref=ref,
        sha256=digest,
        size_bytes=len(payload),
    )

    read = read_ukraine_json_snapshot(
        store,
        artifact.content_ref,
        raw_payload_bytes=payload,
        expected_sha256=artifact.sha256,
        expected_size_bytes=artifact.size_bytes,
        expected_kind="data_forge.ukraine.stage_output_snapshot",
        consumer_contract="unit.demography.targets",
        model_type=_StatePayload,
    )

    assert read.provenance.profile_status == "profile_absent_raw_snapshot_candidate"
    assert read.provenance.selected_artifact_id == str(ref.artifact_id)
    assert read.provenance.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    assert read.provenance.content_sha256 == digest
    assert read.provenance.producer_attestation_status == "not_established"
    assert read.provenance.currentness_provenance == "not_established"
    assert read.raw_payload_bytes == payload
    assert read.value_for_candidate().state_ids == ["a", "b"]
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_profile_not_verified"):
        _ = read.value


def test_declared_unknown_profile_is_raw_only_without_decoding_and_requires_exact_selector(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = b"not-json-under-an-unknown-profile"
    digest = hashlib.sha256(payload).hexdigest()
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind="data_forge.ukraine.stage_output_snapshot",
            media_type="application/json",
            canon=CoreCanonInfo(name="polisyos.canon.future", version="9.9.9"),
        ),
        return_selected_profile=True,
    )
    artifact = VerifiedUkraineStageArtifact(
        source_path="future.json",
        content_ref=ref,
        sha256=digest,
        size_bytes=len(payload),
    )
    read = read_ukraine_json_snapshot(
        store,
        artifact.content_ref,
        raw_payload_bytes=payload,
        expected_sha256=artifact.sha256,
        expected_size_bytes=artifact.size_bytes,
        expected_kind="data_forge.ukraine.stage_output_snapshot",
        consumer_contract="unit.future-profile",
        model_type=_StatePayload,
    )
    assert read.provenance.profile_status == "declared_unknown_candidate"
    assert read.provenance.selected_artifact_id == str(ref.artifact_id)
    assert read.provenance.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    assert read.provenance.content_sha256 == digest
    assert read.provenance.artifact_ref.manifest_profile_sha256 == ref.manifest_profile_sha256
    assert read.raw_only_candidate_bytes == payload
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_unknown_profile_raw_only"):
        read.value_for_candidate()
    unqualified_ref = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_profile_selector_missing"):
        read_ukraine_json_snapshot(
            store,
            unqualified_ref,
            raw_payload_bytes=payload,
            expected_sha256=digest,
            expected_size_bytes=len(payload),
            expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract="unit.future-profile-unqualified",
            model_type=_StatePayload,
        )


def test_profileless_snapshot_refuses_duplicate_keys_and_content_identity_drift(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = b'{"state_ids":["a"]}'
    digest = hashlib.sha256(payload).hexdigest()
    ref = store.put_bytes(
        payload,
        PutOptions(kind="data_forge.ukraine.stage_output_snapshot", media_type="application/json"),
        return_selected_profile=True,
    )
    duplicate = b'{"state_ids":["a"],"state_ids":["b"]}'
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_content_binding_mismatch"):
        read_ukraine_json_snapshot(
            store, ref, raw_payload_bytes=duplicate, expected_sha256=digest,
            expected_size_bytes=len(duplicate), expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract="unit.duplicate", model_type=_StatePayload,
        )
    duplicate_digest = hashlib.sha256(duplicate).hexdigest()
    duplicate_ref = store.put_bytes(
        duplicate,
        PutOptions(kind="data_forge.ukraine.stage_output_snapshot", media_type="application/json"),
        return_selected_profile=True,
    )
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_json_or_schema_invalid"):
        read_ukraine_json_snapshot(
            store, duplicate_ref, raw_payload_bytes=duplicate,
            expected_sha256=duplicate_digest,
            expected_size_bytes=len(duplicate), expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract="unit.duplicate", model_type=_StatePayload,
        )

def test_declared_profile_reader_constructs_prefixed_selection_and_bare_content_digest(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ref = store.put_json(
        {"state_ids": ["a", "b"]},
        PutOptions(kind="data_forge.ukraine.stage_output_snapshot", media_type="application/json"),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    payload = store.get_bytes(ref)
    digest = hashlib.sha256(payload).hexdigest()
    artifact = VerifiedUkraineStageArtifact(
        source_path="targets.json",
        content_ref=ref,
        sha256=digest,
        size_bytes=len(payload),
    )

    read = read_ukraine_json_snapshot(
        store,
        artifact.content_ref,
        raw_payload_bytes=payload,
        expected_sha256=artifact.sha256,
        expected_size_bytes=artifact.size_bytes,
        expected_kind="data_forge.ukraine.stage_output_snapshot",
        consumer_contract="unit.declared-profile.targets",
        model_type=_StatePayload,
    )

    assert read.provenance.profile_status == "declared_bytes_conformant"
    assert read.provenance.selected_artifact_id == str(ref.artifact_id)
    assert read.provenance.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    assert read.provenance.selected_manifest_profile_sha256.startswith("sha256:")
    assert read.provenance.content_sha256 == digest
    assert not read.provenance.content_sha256.startswith("sha256:")
    assert read.value.state_ids == ["a", "b"]


def test_selected_profile_and_content_digest_fields_keep_distinct_canonical_forms() -> None:
    digest = "a" * 64
    profile = "sha256:" + ("b" * 64)
    ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(digest),
        kind="data_forge.ukraine.stage_output_snapshot",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )
    provenance_fields = {
        "artifact_ref": ref,
        "selected_artifact_id": str(ref.artifact_id),
        "selected_manifest_profile_sha256": profile,
        "content_sha256": digest,
        "content_size_bytes": 1,
        "artifact_kind": ref.kind,
        "profile_status": "declared_bytes_conformant",
        "consumer_contract": "unit.digest-roles",
        "schema_validation_provenance": "recomputed",
        "source_materialization": "reader_materialized",
    }
    provenance = UkraineJSONSnapshotProvenance(**provenance_fields)
    assert provenance.selected_artifact_id == str(ref.artifact_id)
    assert provenance.selected_manifest_profile_sha256 == profile
    assert provenance.content_sha256 == digest

    invalid_provenance = (
        ("selected_artifact_id", digest),
        ("selected_manifest_profile_sha256", profile.removeprefix("sha256:")),
        ("content_sha256", f"sha256:{digest}"),
    )
    for field_name, invalid_value in invalid_provenance:
        with pytest.raises(ValidationError):
            UkraineJSONSnapshotProvenance(**{**provenance_fields, field_name: invalid_value})

    handoff_request = D5ReleaseHandoffRequest(
        declared_release_root="release-root",
        producer_facts=D5ReleaseProducerFacts(
            primary_region_id="region-1",
            primary_sector_id="sector-1",
            graph_compression_degree_preservation_score=1.0,
            graph_compression_edge_weight_reconstruction_error=0.0,
        ),
        content_refs={
            name: D5ReleaseContentRef(path=f"{name}.json", sha256=digest, size_bytes=1)
            for name in ("cell_registry", "d4_governance_request", "graph_compression_bundle")
        },
    )
    receipt_cases = (
        (
            VerifiedUkraineStageArtifact,
            {
                "source_path": "targets.json",
                "content_ref": ref,
                "sha256": digest,
                "size_bytes": 1,
            },
            "sha256",
        ),
        (
            VerifiedUkraineStageArtifacts,
            {
                "stage_id": "d1",
                "run_id": "run-1",
                "finished_at": "2026-10-12T00:00:00Z",
                "manifest_source_path": "manifest.json",
                "manifest_ref": ref,
                "manifest_sha256": digest,
            },
            "manifest_sha256",
        ),
        (
            VerifiedUkraineReleaseArtifact,
            {
                "source_path": "release.json",
                "content_ref": ref,
                "sha256": digest,
                "size_bytes": 1,
            },
            "sha256",
        ),
        (
            VerifiedUkraineReleaseArtifacts,
            {
                "declared_release_root": "release-root",
                "manifest_source_path": "manifest.json",
                "manifest_ref": ref,
                "manifest_sha256": digest,
                "manifest_size_bytes": 1,
                "handoff_request": handoff_request,
            },
            "manifest_sha256",
        ),
    )
    for model, fields, digest_field in receipt_cases:
        assert model(**fields)
        with pytest.raises(ValidationError):
            model(**{**fields, digest_field: f"sha256:{digest}"})
