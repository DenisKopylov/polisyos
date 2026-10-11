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
