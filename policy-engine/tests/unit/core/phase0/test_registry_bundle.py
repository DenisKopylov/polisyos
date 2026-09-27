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
    UnitsRegistry,
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


@pytest.mark.parametrize(
    ("member_kind", "member_role"),
    [
        ("ir.slot_registry", "slot_registry"),
        ("ir.units_registry", "units_registry"),
    ],
)
def test_registry_bundle_manifest_lineage_preserves_selected_member_profile(
    tmp_path, monkeypatch, member_kind: str, member_role: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-owner")
    original_put_json = store.put_json
    selected_member_refs: list[ArtifactRef] = []

    def put_json_with_selected_member_profile(obj, opts, canon_spec=None):
        ref = original_put_json(obj, opts, canon_spec)
        if opts.kind == member_kind:
            ref = _alternate_manifest_profile(store, store, ref)
            selected_member_refs.append(ref)
        return ref

    monkeypatch.setattr(store, "put_json", put_json_with_selected_member_profile)
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        units_registry=UnitsRegistry() if member_role == "units_registry" else None,
    )

    selected_member_ref = selected_member_refs[0]
    assert getattr(bundle, member_role) == selected_member_ref
    assert selected_member_ref.manifest_profile_sha256 is not None
    payload = load_registry_bundle_payload(store, bundle.bundle_ref)
    assert (
        getattr(payload, member_role).manifest_profile_sha256
        == selected_member_ref.manifest_profile_sha256
    )

    manifest = store.get_manifest(bundle.bundle_ref)
    member_input = next(item for item in manifest.inputs if item.role == member_role)
    assert member_input.manifest_profile_sha256 == selected_member_ref.manifest_profile_sha256


def test_registry_loader_resolves_selected_top_level_bundle_without_fallback(tmp_path) -> None:
    root = tmp_path / "cas"
    owner_store = FileSystemCAS(root).for_tenant("tenant-owner")
    bundle = build_default_registry_bundle(owner_store)
    selected_bundle_ref = _alternate_manifest_profile(
        owner_store, owner_store, bundle.bundle_ref
    )

    assert selected_bundle_ref.artifact_id == bundle.bundle_ref.artifact_id
    assert selected_bundle_ref.manifest_profile_sha256 is not None
    owner_content = load_registry_bundle_content(owner_store, bundle.bundle_ref)
    assert owner_content.bundle_ref == bundle.bundle_ref
    selected_content = load_registry_bundle_content(owner_store, selected_bundle_ref)
    assert selected_content.bundle_ref == selected_bundle_ref

    unheld_ref = selected_bundle_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(ArtifactOwnershipError):
        load_registry_bundle_content(owner_store, unheld_ref)
