from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle


def test_build_default_registry_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)

    assert bundle.bundle_ref.kind == "core.registry_bundle"
    assert store.has(bundle.bundle_ref.artifact_id)
    assert store.has(bundle.slot_registry.artifact_id)
    assert store.has(bundle.merge_registry.artifact_id)
    assert store.has(bundle.mechanism_registry.artifact_id)
    assert store.has(bundle.constraint_registry.artifact_id)
    if bundle.units_registry is not None:
        assert store.has(bundle.units_registry.artifact_id)
