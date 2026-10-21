"""Schema and byte-level witnesses for the CAS manifest serialization contract."""

from __future__ import annotations

import hashlib
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactWriteOptions,
    artifact_manifest_profile_projection,
    artifact_manifest_profile_sha256,
    expected_artifact_manifest_for_write,
)
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    InputRef,
    IntegrityInfo,
    SchemaInfo,
)
from polisyos.runtime.http.services.channel_contracts import RunDetailSnapshot


def _artifact_id(hex_value: str) -> ArtifactID:
    return ArtifactID.from_sha256_hex(hex_value * 64)


def test_core_manifest_profile_lifecycle_preserves_v1_v2_v3_golden_digests() -> None:
    expected = {
        "v1": "sha256:becce32c7823c3bcd2f5d9e26f706cb2094bbbf1803a3268f22641e0a6b84bdb",
        "v2": "sha256:1694daeaf2a39d255ce1c7848ff99ab502851c8d4983edfd59c22e7f82bb4fc2",
        "v3": "sha256:5592dadc32c55a1406eb2d813237e3e150209f74f5be22c276bffd97600b8fdc",
    }

    for version, digest in expected.items():
        manifest = ArtifactManifest(
            manifest_schema_version=version,
            artifact_id=_artifact_id("a"),
            kind="test.profile_golden",
            media_type="application/json",
            byte_size=42,
            created_at=datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
            artifact_schema=SchemaInfo(name="test.Golden", version="1.0"),
            canon=CanonInfo(),
            inputs=[],
            integrity=IntegrityInfo(
                sha256="b" * 64,
                optional={"digest": "c" * 64},
            ),
            warnings=[],
        )

        assert artifact_manifest_profile_sha256(manifest) == digest
        projection = artifact_manifest_profile_projection(manifest)
        assert "artifact_id" not in projection
        assert "byte_size" not in projection
        assert "created_at" not in projection
        if version in {"v1", "v2"}:
            assert "integrity" not in projection
        else:
            assert projection["integrity"] == {"optional": {"digest": "c" * 64}}


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
    product_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "architecture/generated_artifacts.toml").is_file()
    )
    fixture_root = (
        product_root / "architecture/policy_design_case/layer3_gy_acquisition_cas/artifacts"
    )
    sidecars = sorted(fixture_root.rglob("*.manifest.json"))
    registry = tomllib.loads(
        (product_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    family = next(
        item
        for item in registry["family"]
        if item["id"] == "policy-design-case-layer3-gy-n13b-frozen-acquisition-evidence"
    )
    fixture_prefix = fixture_root.relative_to(product_root).as_posix() + "/"
    expected_sidecars = {
        path
        for path in family["outputs"]
        if path.startswith(fixture_prefix) and path.endswith(".manifest.json")
    }
    actual_sidecars = {sidecar.relative_to(product_root).as_posix() for sidecar in sidecars}
    _assert_exact_manifest_sidecar_inventory(expected_sidecars, actual_sidecars)
    with pytest.raises(AssertionError, match="missing="):
        _assert_exact_manifest_sidecar_inventory(
            expected_sidecars, actual_sidecars - {min(expected_sidecars)}
        )

    serialized_by_profile: dict[tuple[str, str], bytes] = {}
    for sidecar in sidecars:
        original = sidecar.read_bytes()
        manifest = ArtifactManifest.model_validate_json(original)
        assert ManifestLifecycle.to_bytes(manifest) == original, sidecar
        profile_sha256 = ManifestLifecycle.profile_sha256(manifest)
        identity = (str(manifest.artifact_id), profile_sha256)
        previous = serialized_by_profile.setdefault(identity, original)
        assert previous == original, ("profile aliases differ in serialized bytes", sidecar)
        stem = sidecar.name.removesuffix(".manifest.json")
        artifact_hex = str(manifest.artifact_id).removeprefix("sha256:")
        if ".view." in stem:
            selected_artifact_hex, selected_profile_hex = stem.split(".view.", maxsplit=1)
            assert selected_artifact_hex == artifact_hex, sidecar
            assert selected_profile_hex == profile_sha256.removeprefix("sha256:"), sidecar
        else:
            assert stem == artifact_hex, sidecar


def _assert_exact_manifest_sidecar_inventory(
    expected_sidecars: set[str], actual_sidecars: set[str]
) -> None:
    missing = expected_sidecars - actual_sidecars
    unexpected = actual_sidecars - expected_sidecars
    assert not missing and not unexpected, (
        f"manifest sidecar inventory differs: missing={sorted(missing)}, "
        f"unexpected={sorted(unexpected)}"
    )


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


def test_public_expected_manifest_helper_reuses_canonical_lifecycle_profile() -> None:
    data = b"current manifest facade fixture"
    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())
    selected_profile = "sha256:" + "9" * 64
    options = ArtifactWriteOptions(
        kind="fixture.selected",
        media_type="application/octet-stream",
        inputs=[
            InputRef(
                artifact_id=_artifact_id("e"),
                role="basis",
                manifest_profile_sha256=selected_profile,
            )
        ],
    )
    created_at = datetime(2026, 10, 9, tzinfo=UTC)

    public_manifest = expected_artifact_manifest_for_write(
        artifact_id=artifact_id,
        data=data,
        opts=options,
        created_at=created_at,
    )
    canonical_manifest = ManifestLifecycle.expected_for_write(
        artifact_id=artifact_id,
        data=data,
        opts=options,
        created_at=created_at,
    )

    assert public_manifest == canonical_manifest
    assert public_manifest.inputs[0].manifest_profile_sha256 == selected_profile
    assert artifact_manifest_profile_sha256(public_manifest) == ManifestLifecycle.profile_sha256(
        canonical_manifest
    )


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


def test_profileless_authority_event_link_keeps_historical_dump_shape() -> None:
    authority = ArtifactAuthorityInfo(
        authority_envelope_ref="sha256:" + "a" * 64,
        diagnostic_event_ref="sha256:" + "b" * 64,
        manifest_ref="cas-manifest://sha256:" + "c" * 64,
        payload_sha256="c" * 64,
    )
    assert authority.model_dump(mode="json") == {
        "authority_envelope_ref": "sha256:" + "a" * 64,
        "diagnostic_event_ref": "sha256:" + "b" * 64,
        "manifest_ref": "cas-manifest://sha256:" + "c" * 64,
        "payload_sha256": "c" * 64,
    }
    selected_profile = "sha256:" + "d" * 64
    selected = authority.model_copy(
        update={"diagnostic_event_manifest_profile_sha256": selected_profile}
    )
    assert (
        selected.model_dump(mode="json")["diagnostic_event_manifest_profile_sha256"]
        == selected_profile
    )
