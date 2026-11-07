from __future__ import annotations

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts import (
    profile_bound_ref as facade_profile_bound_ref,
)
from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def test_profile_bound_ref_pins_store_selected_default_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ref = store.put_json(
        {"value": "stored"},
        PutOptions(kind="test.profile_bound", media_type="application/json"),
    )
    assert ref.manifest_profile_sha256 is None

    selected = profile_bound_ref(store, ref)
    manifest = store.get_manifest(selected)

    assert selected.artifact_id == ref.artifact_id
    assert selected.manifest_profile_sha256 == artifact_manifest_profile_sha256(manifest)
    assert store.verify(selected).ok


def test_profile_bound_ref_refuses_stale_explicit_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ref = store.put_json(
        {"value": "stored"},
        PutOptions(kind="test.profile_bound", media_type="application/json"),
    )
    stale = ref.model_copy(update={"manifest_profile_sha256": f"sha256:{'f' * 64}"})

    with pytest.raises(ValueError, match="artifact_manifest_view_unavailable"):
        profile_bound_ref(store, stale)


def test_profile_bound_ref_is_exported_by_artifacts_facade() -> None:
    assert facade_profile_bound_ref is profile_bound_ref
    assert "profile_bound_ref" in artifacts.__all__


def test_legacy_alias_keeps_default_only_meaning_for_profiled_and_old_refs(tmp_path) -> None:
    from polisyos.core.artifacts import legacy_default_artifact_id

    store = FileSystemCAS(tmp_path)
    ref = store.put_json(
        {"value": "stored"},
        PutOptions(kind="test.alias", media_type="application/json"),
        return_selected_profile=True,
    )
    assert legacy_default_artifact_id(store, ref) == ref.artifact_id
    assert (
        legacy_default_artifact_id(store, ref.model_copy(update={"manifest_profile_sha256": None}))
        == ref.artifact_id
    )
    assert "legacy_default_artifact_id" in artifacts.__all__


def test_selected_tenant_can_use_its_view_without_reading_foreign_default(tmp_path) -> None:
    from polisyos.core.artifacts import ArtifactOwnershipError, legacy_default_artifact_id

    store_a = FileSystemCAS(tmp_path).for_tenant("tenant-a")
    store_b = FileSystemCAS(tmp_path).for_tenant("tenant-b")
    payload = b"shared selected bytes"
    default = store_a.put_bytes(payload, PutOptions(kind="test.default", media_type="text/plain"))
    selected = store_b.put_bytes(payload, PutOptions(kind="test.selected", media_type="text/plain"))
    assert selected.artifact_id == default.artifact_id
    assert store_b.verify(selected).ok
    with pytest.raises(ArtifactOwnershipError):
        store_b.get_manifest(selected.artifact_id)
    assert legacy_default_artifact_id(store_b, selected) is None
    assert store_b.get_manifest(selected).kind == "test.selected"
    with pytest.raises(ArtifactOwnershipError):
        legacy_default_artifact_id(store_a, selected)


def test_optional_missing_default_does_not_erase_verified_selected_view(tmp_path) -> None:
    from polisyos.core.artifacts import legacy_default_artifact_id

    store = FileSystemCAS(tmp_path)
    payload = b"shared selected bytes"
    store.put_bytes(payload, PutOptions(kind="test.default", media_type="text/plain"))
    selected = store.put_bytes(payload, PutOptions(kind="test.selected", media_type="text/plain"))
    store._manifest_path_for_ref(selected.artifact_id, None).unlink()
    assert store.verify(selected).ok
    assert legacy_default_artifact_id(store, selected) is None


def test_alias_never_swallows_selected_integrity_or_other_default_errors(
    tmp_path, monkeypatch
) -> None:
    from polisyos.core.artifacts import ArtifactID, legacy_default_artifact_id

    store = FileSystemCAS(tmp_path)
    selected = store.put_bytes(
        b"owned bytes",
        PutOptions(kind="test.selected", media_type="text/plain"),
        return_selected_profile=True,
    )
    original_get = store.get_manifest
    default_probes = []

    def corrupt_default(selector):
        if isinstance(selector, ArtifactID):
            default_probes.append(selector)
            raise ValueError("actual_default_decode_failure")
        return original_get(selector)

    monkeypatch.setattr(store, "get_manifest", corrupt_default)
    blob, _manifest = store._paths(selected.artifact_id)
    original_bytes = blob.read_bytes()
    blob.write_bytes(b"changed owned bytes")
    with pytest.raises(ValueError, match="selected_artifact_integrity"):
        legacy_default_artifact_id(store, selected)
    assert default_probes == []
    blob.write_bytes(original_bytes)
    with pytest.raises(ValueError, match="actual_default_decode_failure"):
        legacy_default_artifact_id(store, selected)
