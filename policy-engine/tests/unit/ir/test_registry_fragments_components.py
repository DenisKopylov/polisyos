from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
)
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.core.registry import (
    build_registry_bundle_from_components,
    load_registry_bundle_content,
    load_registry_bundle_payload,
)
from polisyos.ir.kernel.units import GenericUnit, UnitsRegistry
from polisyos.ir.registry.registry_fragments import RegistryFragmentMeta, UnitsFragment


@dataclass(frozen=True)
class _FragmentComponent:
    metadata: ComponentMetadata
    description: str

    def create(self) -> UnitsFragment:
        return UnitsFragment(
            meta=RegistryFragmentMeta(
                fragment_id="tmp.fragment",
                namespace="roads",
                priority=0,
            ),
            payload=UnitsRegistry(
                units={
                    "roads.kmh": GenericUnit(
                        label="kmh",
                        description=self.description,
                    )
                }
            ),
        )


def _entry(
    *,
    component_id: str,
    description: str,
    source_type: str,
) -> ComponentEntry:
    metadata = ComponentMetadata(
        component_id=ComponentId.parse(component_id),
        kind=ComponentKind.IR_FRAGMENT,
        abi_targets={"ir_abi": "1.x"},
        domains=["roads"],
        jurisdictions=[],
        tags=["test"],
        capabilities=Capability.IR_FRAGMENT,
        deps=[],
    )
    component = _FragmentComponent(metadata=metadata, description=description)
    source = DiscoverySourceInfo(
        source_type=source_type,
        location=f"{source_type}:{component_id}",
    )
    return ComponentEntry(metadata=metadata, component=component, source=source)


def _compose_hash(store: FileSystemCAS, artifact_id: str) -> str:
    payload = from_canonical_bytes(store.get_bytes(ArtifactID.model_validate(artifact_id)))
    assert isinstance(payload, dict)
    hash_value = payload.get("deterministic_hash")
    assert isinstance(hash_value, str)
    return hash_value


def test_ir_fragment_composition_deterministic(tmp_path) -> None:
    entry_point_entry = _entry(
        component_id="roads.ir.fragment_entry@1.0.0",
        description="entry-point value",
        source_type="entry_point",
    )
    dev_override_entry = _entry(
        component_id="roads.ir.fragment_override@1.0.0",
        description="dev-scan value",
        source_type="dev_scan",
    )

    first_index = ComponentRegistry()
    first_index.register(entry_point_entry)
    first_index.register(dev_override_entry)

    second_index = ComponentRegistry()
    second_index.register(dev_override_entry)
    second_index.register(entry_point_entry)

    first_store = FileSystemCAS(tmp_path / "cas_first")
    second_store = FileSystemCAS(tmp_path / "cas_second")

    first_bundle_ref, first_report_ref = build_registry_bundle_from_components(
        first_store,
        components_index=first_index,
        domain="roads",
    )
    second_bundle_ref, second_report_ref = build_registry_bundle_from_components(
        second_store,
        components_index=second_index,
        domain="roads",
    )

    assert first_report_ref is not None
    assert second_report_ref is not None

    first_hash = _compose_hash(first_store, str(first_report_ref.artifact_id))
    second_hash = _compose_hash(second_store, str(second_report_ref.artifact_id))
    assert first_hash == second_hash

    first_report_payload = from_canonical_bytes(first_store.get_bytes(first_report_ref.artifact_id))
    assert isinstance(first_report_payload, dict)
    conflicts = first_report_payload.get("conflicts")
    assert isinstance(conflicts, list)
    assert any(conflict.get("conflict_kind") == "duplicate_different" for conflict in conflicts)

    first_content = load_registry_bundle_content(first_store, first_bundle_ref)
    second_content = load_registry_bundle_content(second_store, second_bundle_ref)

    first_unit = first_content.units_registry.units["roads.kmh"]
    second_unit = second_content.units_registry.units["roads.kmh"]

    assert first_unit.description == "dev-scan value"
    assert second_unit.description == "dev-scan value"


def test_component_fragment_builder_returns_selected_member_profiles(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle_ref, report_ref = build_registry_bundle_from_components(
        store,
        components_index=ComponentRegistry(),
        domain="roads",
        return_selected_profile=True,
    )

    assert report_ref is not None
    assert bundle_ref.manifest_profile_sha256 is not None
    assert store.verify(bundle_ref).ok
    payload = load_registry_bundle_payload(store, bundle_ref)
    members = [
        ("slot_registry", payload.slot_registry),
        ("merge_registry", payload.merge_registry),
        ("constraint_registry", payload.constraint_registry),
        ("mechanism_registry", payload.mechanism_registry),
        ("selector_field_registry", payload.selector_field_registry),
        ("metric_registry", payload.metric_registry),
        ("units_registry", payload.units_registry),
        ("trust_registry", payload.trust_registry),
        ("predicate_registry", payload.predicate_registry),
        ("privacy_registry", payload.privacy_registry),
    ]
    selected_members = [(role, ref) for role, ref in members if ref is not None]
    assert selected_members
    assert all(ref.manifest_profile_sha256 is not None for _, ref in selected_members)

    manifest = store.get_manifest(bundle_ref)
    input_profiles = {item.role: item.manifest_profile_sha256 for item in manifest.inputs}
    for role, ref in selected_members:
        assert input_profiles[role] == ref.manifest_profile_sha256
