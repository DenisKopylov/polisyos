"""Schema and byte-level witnesses for the CAS manifest serialization contract."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    IntegrityInfo,
)
from polisyos.runtime.http.services.channel_contracts import RunDetailSnapshot


def _artifact_id(hex_value: str) -> ArtifactID:
    return ArtifactID.from_sha256_hex(hex_value * 64)


def test_historical_selectorless_refs_keep_their_default_dump_shape() -> None:
    artifact_id = _artifact_id("c")
    ref = ArtifactRef(artifact_id=artifact_id, kind="legacy.ref", media_type="application/json")
    input_ref = InputRef(artifact_id=artifact_id, role="legacy_input")

    assert ref.model_dump(mode="json") == {
        "artifact_id": str(artifact_id),
        "kind": "legacy.ref",
        "media_type": "application/json",
    }
    assert input_ref.model_dump(mode="json") == {
        "artifact_id": str(artifact_id),
        "role": "legacy_input",
    }


def test_historical_v1_manifest_sidecar_bytes_and_digest_are_exact() -> None:
    artifact_id = _artifact_id("a")
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        kind="fixture.historical",
        media_type="application/json",
        byte_size=7,
        created_at=datetime(2026, 9, 26, tzinfo=UTC),
        inputs=[InputRef(artifact_id=_artifact_id("b"), role="historical_basis")],
        integrity=IntegrityInfo(sha256="a" * 64),
    )

    expected = (
        b'{"artifact_id":"sha256:'
        + b"a" * 64
        + b'","byte_size":7,"created_at":"2026-09-26T00:00:00Z",'
        b'"inputs":[{"artifact_id":"sha256:'
        + b"b" * 64
        + b'","role":"historical_basis"}],"integrity":{"sha256":"'
        + b"a" * 64
        + b'"},"kind":"fixture.historical","media_type":"application/json","warnings":[]}'
    )
    assert "manifest_schema_version" not in manifest.model_dump(mode="json")
    actual = ManifestLifecycle.to_bytes(manifest)

    assert actual == expected
    assert hashlib.sha256(actual).hexdigest() == (
        "10090ca6eb18b5579964936034407bac02b125292654c2c1aed4d5a0eff35927"
    )


def test_all_archived_policy_design_cas_sidecars_replay_byte_exactly() -> None:
    fixture_root = (
        Path(__file__).resolve().parents[4]
        / "architecture/policy_design_case/layer3_gy_acquisition_cas/artifacts"
    )
    sidecars = sorted(fixture_root.rglob("*.manifest.json"))
    assert len(sidecars) == 11

    for sidecar in sidecars:
        original = sidecar.read_bytes()
        manifest = ArtifactManifest.model_validate_json(original)
        assert ManifestLifecycle.to_bytes(manifest) == original, sidecar


def test_selected_view_v2_fields_are_emitted_as_real_data() -> None:
    artifact_id = _artifact_id("d")
    profile_sha = "sha256:" + "1" * 64
    input_ref = InputRef(
        artifact_id=_artifact_id("e"),
        role="selected_basis",
        manifest_profile_sha256=profile_sha,
    )
    ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="selected.ref",
        media_type="application/json",
        manifest_profile_sha256=profile_sha,
    )
    manifest = ArtifactManifest(
        manifest_schema_version="v2",
        artifact_id=artifact_id,
        kind="selected.manifest",
        media_type="application/json",
        byte_size=1,
        inputs=[input_ref],
        integrity=IntegrityInfo(sha256="d" * 64),
    )

    assert ref.model_dump(mode="json")["manifest_profile_sha256"] == profile_sha
    assert input_ref.model_dump(mode="json")["manifest_profile_sha256"] == profile_sha
    assert manifest.model_dump(mode="json")["manifest_schema_version"] == "v2"
    sidecar = ManifestLifecycle.to_bytes(manifest)
    assert b'"manifest_schema_version":"v2"' in sidecar
    assert b'"manifest_profile_sha256":"' + profile_sha.encode() + b'"' in sidecar


def _assert_strict_serialization_schema(schema: dict[str, object]) -> None:
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    assert isinstance(schema.get("properties"), dict)
    assert schema["properties"]


def test_cas_models_have_strict_serialization_schemas() -> None:
    for model in (ArtifactRef, InputRef, ArtifactManifest):
        _assert_strict_serialization_schema(model.model_json_schema(mode="serialization"))

    artifact_ref_schema = ArtifactRef.model_json_schema(mode="serialization")
    assert artifact_ref_schema["properties"]["artifact_id"]["type"] == "string"
    for model in (ArtifactRef, InputRef):
        selector_schema = model.model_json_schema(mode="serialization")["properties"][
            "manifest_profile_sha256"
        ]
        assert selector_schema["anyOf"][0]["pattern"] == r"^sha256:[0-9a-f]{64}$"
    manifest_schema = ArtifactManifest.model_json_schema(mode="serialization")
    assert "manifest_schema_version" in manifest_schema["properties"]


def test_served_channel_projection_keeps_typed_nested_artifact_ref_schema() -> None:
    schema = RunDetailSnapshot.model_json_schema(mode="serialization")
    _assert_strict_serialization_schema(schema)

    field = schema["properties"]["decision_superseded_by_ref"]
    artifact_ref_schema = schema["$defs"]["ArtifactRef"]
    _assert_strict_serialization_schema(artifact_ref_schema)
    assert field["anyOf"][0]["$ref"] == "#/$defs/ArtifactRef"
    assert artifact_ref_schema["properties"]["artifact_id"]["type"] == "string"
