from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts as core_artifacts
from polisyos.core.artifacts import manifest as artifact_manifest
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    IntegrityInfo,
    _coerce_input_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.contracts import StorePutOptions


def test_artifact_ref_conversion_preserves_selected_manifest_view() -> None:
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    selected_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="test.parent.selected",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )

    input_ref_factory = getattr(core_artifacts, "input_ref_from_artifact_ref", None)
    identity_key = getattr(artifact_manifest, "artifact_ref_identity_key", None)
    assert callable(input_ref_factory)
    assert callable(identity_key)
    lineage = input_ref_factory(selected_ref, role="selected_parent")

    assert lineage == InputRef(
        artifact_id=artifact_id,
        role="selected_parent",
        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
    )
    default_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
    assert input_ref_factory(default_ref, role="selected_parent") == InputRef(
        artifact_id=artifact_id,
        role="selected_parent",
    )
    assert identity_key(default_ref) != identity_key(selected_ref)


def test_store_boundary_revalidates_unchecked_artifact_ref_copy() -> None:
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    selected_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="test.parent.selected",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    unchecked = selected_ref.model_copy(update={"artifact_id": str(artifact_id)})

    normalized_id, profile, normalized_ref = artifact_manifest.artifact_reference_parts(
        unchecked
    )
    assert normalized_id == artifact_id
    assert isinstance(normalized_id, ArtifactID)
    assert profile == selected_ref.manifest_profile_sha256
    assert normalized_ref == selected_ref
    assert isinstance(normalized_ref.artifact_id, ArtifactID)

    malformed = selected_ref.model_copy(update={"artifact_id": "not-an-artifact-id"})
    with pytest.raises(ValidationError):
        artifact_manifest.artifact_reference_parts(malformed)

    class ScopedRef(ArtifactRef):
        scope: str

    scoped = ScopedRef(
        artifact_id=artifact_id,
        kind="test.parent.selected",
        media_type="application/json",
        scope="owner-a",
    ).model_copy(update={"artifact_id": str(artifact_id)})
    _, _, normalized_scoped = artifact_manifest.artifact_reference_parts(scoped)
    assert isinstance(normalized_scoped, ScopedRef)
    assert normalized_scoped.scope == "owner-a"
    assert isinstance(normalized_scoped.artifact_id, ArtifactID)


def test_dict_lineage_preserves_selected_manifest_view_across_idempotent_puts(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    payload = {"parent": "same bytes"}
    default_parent = store.put_json(
        payload,
        PutOptions(kind="test.parent.default", media_type="application/json"),
    )
    selected_parent = store.put_json(
        payload,
        PutOptions(kind="test.parent.selected", media_type="application/json"),
    )

    assert selected_parent.artifact_id == default_parent.artifact_id
    assert selected_parent.manifest_profile_sha256 is not None

    child_payload = {"child": True}
    child_opts = StorePutOptions(
        kind="test.child.selected-lineage",
        media_type="application/json",
        inputs=[
            {
                "artifact_id": str(selected_parent.artifact_id),
                "role": "selected_parent",
                "manifest_profile_sha256": selected_parent.manifest_profile_sha256,
            }
        ],
    )
    child = store.put_json(child_payload, child_opts)
    replayed_child = store.put_json(child_payload, child_opts)

    assert replayed_child == child
    manifest = store.get_manifest(child)
    assert manifest.manifest_schema_version == "v3"
    assert manifest.inputs == [
        InputRef(
            artifact_id=selected_parent.artifact_id,
            role="selected_parent",
            manifest_profile_sha256=selected_parent.manifest_profile_sha256,
        )
    ]


def test_dict_lineage_rejects_malformed_manifest_profile_selector(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    parent = store.put_json(
        {"parent": True},
        PutOptions(kind="test.parent", media_type="application/json"),
    )

    with pytest.raises(ValidationError, match="manifest_profile_sha256"):
        store.put_json(
            {"child": True},
            StorePutOptions(
                kind="test.child.invalid-lineage",
                media_type="application/json",
                inputs=[
                    {
                        "artifact_id": str(parent.artifact_id),
                        "role": "parent",
                        "manifest_profile_sha256": "sha256:" + "g" * 64,
                    }
                ],
            ),
        )


def test_dict_lineage_without_selector_remains_supported(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    parent = store.put_json(
        {"parent": True},
        PutOptions(kind="test.parent", media_type="application/json"),
    )

    child = store.put_json(
        {"child": True},
        StorePutOptions(
            kind="test.child",
            media_type="application/json",
            inputs=[{"artifact_id": str(parent.artifact_id), "role": "parent"}],
        ),
    )

    manifest = store.get_manifest(child)
    assert manifest.inputs == [InputRef(artifact_id=parent.artifact_id, role="parent")]


def test_profile_comparison_normalizes_dict_lineage_with_selected_view() -> None:
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    parent_id = ArtifactID.from_sha256_hex("b" * 64)
    profile_sha256 = "sha256:" + "c" * 64
    input_ref = InputRef(
        artifact_id=parent_id,
        role="selected_parent",
        manifest_profile_sha256=profile_sha256,
    )
    manifest = ArtifactManifest(
        manifest_schema_version="v2",
        artifact_id=artifact_id,
        kind="test.child.selected-lineage",
        media_type="application/json",
        byte_size=5,
        inputs=[input_ref],
        integrity=IntegrityInfo(sha256="a" * 64),
    )
    opts = ArtifactWriteOptions(
        kind="test.child.selected-lineage",
        media_type="application/json",
        inputs=[
            {
                "artifact_id": str(parent_id),
                "role": "selected_parent",
                "manifest_profile_sha256": profile_sha256,
            }
        ],
    )

    assert ManifestLifecycle.profile_mismatches(manifest, data_size=5, opts=opts) == ()


def test_attribute_lineage_keeps_selected_manifest_view() -> None:
    artifact_id = ArtifactID.from_sha256_hex("d" * 64)
    profile_sha256 = "sha256:" + "e" * 64

    input_ref = _coerce_input_ref(
        SimpleNamespace(
            artifact_id=str(artifact_id),
            role="selected_parent",
            manifest_profile_sha256=profile_sha256,
        )
    )

    assert input_ref == InputRef(
        artifact_id=artifact_id,
        role="selected_parent",
        manifest_profile_sha256=profile_sha256,
    )


def test_put_bytes_keeps_duck_typed_options_with_dict_selected_lineage(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    default_parent = store.put_json(
        {"parent": "same bytes"},
        PutOptions(kind="test.parent.default", media_type="application/json"),
    )
    selected_parent = store.put_json(
        {"parent": "same bytes"},
        PutOptions(kind="test.parent.selected", media_type="application/json"),
    )
    assert default_parent.artifact_id == selected_parent.artifact_id

    options = SimpleNamespace(
        kind="test.child.duck-options",
        media_type="application/octet-stream",
        schema=None,
        producer=None,
        env=None,
        inputs=[
            {
                "artifact_id": str(selected_parent.artifact_id),
                "role": "selected_parent",
                "manifest_profile_sha256": selected_parent.manifest_profile_sha256,
            }
        ],
        canon=None,
        governance=None,
        tenant_context=None,
        same_input_closure=None,
        authority=None,
        warnings=None,
    )
    child = store.put_bytes(b"child", options)
    replayed_child = store.put_bytes(b"child", options)

    assert replayed_child == child
    manifest = store.get_manifest(child)
    assert manifest.manifest_schema_version == "v3"
    assert manifest.inputs == [
        InputRef(
            artifact_id=selected_parent.artifact_id,
            role="selected_parent",
            manifest_profile_sha256=selected_parent.manifest_profile_sha256,
        )
    ]
