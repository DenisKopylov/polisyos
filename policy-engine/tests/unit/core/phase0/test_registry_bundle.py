from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import (
    build_default_registry_bundle,
    build_registry_bundle,
    load_registry_bundle_content,
    load_registry_bundle_payload,
)
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SlotRegistry,
)


def _alternate_manifest_profile(
    store: FileSystemCAS,
    source_store: FileSystemCAS,
    ref: ArtifactRef,
) -> ArtifactRef:
    manifest = source_store.get_manifest(ref)
    return store.put_bytes(
        source_store.get_bytes(ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="test.core.registry", version="2.0.0"),
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
    )


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


def test_registry_bundle_manifest_lineage_preserves_selected_member_profile(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-owner")
    original_put_json = store.put_json
    selected_slot_refs: list[ArtifactRef] = []

    def put_json_with_selected_slot_profile(obj, opts, canon_spec=None):
        ref = original_put_json(obj, opts, canon_spec)
        if opts.kind == "ir.slot_registry":
            ref = _alternate_manifest_profile(store, store, ref)
            selected_slot_refs.append(ref)
        return ref

    monkeypatch.setattr(store, "put_json", put_json_with_selected_slot_profile)
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
    )

    selected_slot_ref = selected_slot_refs[0]
    assert bundle.slot_registry == selected_slot_ref
    assert selected_slot_ref.manifest_profile_sha256 is not None
    payload = load_registry_bundle_payload(store, bundle.bundle_ref)
    assert (
        payload.slot_registry.manifest_profile_sha256
        == selected_slot_ref.manifest_profile_sha256
    )

    manifest = store.get_manifest(bundle.bundle_ref)
    slot_input = next(item for item in manifest.inputs if item.role == "slot_registry")
    assert slot_input.manifest_profile_sha256 == selected_slot_ref.manifest_profile_sha256


def test_registry_loader_refuses_foreign_selected_top_level_bundle_profile(tmp_path) -> None:
    root = tmp_path / "cas"
    owner_store = FileSystemCAS(root).for_tenant("tenant-owner")
    foreign_store = FileSystemCAS(root).for_tenant("tenant-foreign")
    bundle = build_default_registry_bundle(owner_store)
    foreign_bundle_ref = _alternate_manifest_profile(
        foreign_store, owner_store, bundle.bundle_ref
    )

    assert foreign_bundle_ref.artifact_id == bundle.bundle_ref.artifact_id
    assert foreign_bundle_ref.manifest_profile_sha256 is not None
    assert owner_store.get_bytes(bundle.bundle_ref) == foreign_store.get_bytes(
        foreign_bundle_ref
    )
    owner_content = load_registry_bundle_content(owner_store, bundle.bundle_ref)
    assert owner_content.bundle_ref == bundle.bundle_ref

    with pytest.raises(ArtifactOwnershipError):
        load_registry_bundle_content(owner_store, foreign_bundle_ref)
