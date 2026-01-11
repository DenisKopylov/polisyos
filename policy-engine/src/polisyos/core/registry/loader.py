from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.registry import RegistryBundle, RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MetricRegistry,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    TrustRegistry,
    UnitsRegistry,
)


def _artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _artifact_ref(
    value: ArtifactRef | ArtifactID | str, *, kind: str, media_type: str
) -> ArtifactRef:
    if isinstance(value, ArtifactRef):
        return value
    return ArtifactRef(artifact_id=_artifact_id(value), kind=kind, media_type=media_type)


def _load_model(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):
    data = store.get_bytes(_artifact_id(ref))
    payload = from_canonical_bytes(data)
    return model_cls.model_validate(payload)


@dataclass(frozen=True)
class RegistryBundleContent:
    bundle_ref: ArtifactRef
    slot_registry: SlotRegistry
    merge_registry: MergeRuleRegistry
    mechanism_registry: MechanismTypeRegistry
    constraint_registry: ConstraintRegistry
    selector_field_registry: SelectorFieldRegistry | None
    metric_registry: MetricRegistry | None
    units_registry: UnitsRegistry | None
    trust_registry: TrustRegistry | None


def load_registry_bundle_payload(
    store: FileSystemCAS, bundle_ref: ArtifactRef | ArtifactID | str
) -> RegistryBundlePayload:
    data = store.get_bytes(_artifact_id(bundle_ref))
    payload = from_canonical_bytes(data)
    return RegistryBundlePayload.model_validate(payload)


def load_registry_bundle(
    store: FileSystemCAS, bundle_ref: ArtifactRef | ArtifactID | str
) -> RegistryBundle:
    payload = load_registry_bundle_payload(store, bundle_ref)
    ref = _artifact_ref(
        bundle_ref,
        kind="core.registry_bundle",
        media_type="application/json",
    )
    return RegistryBundle(bundle_ref=ref, **payload.model_dump())


def load_registry_bundle_content(
    store: FileSystemCAS, bundle_ref: ArtifactRef | ArtifactID | str
) -> RegistryBundleContent:
    bundle = load_registry_bundle(store, bundle_ref)
    slot_registry = _load_model(store, bundle.slot_registry, SlotRegistry)
    merge_registry = _load_model(store, bundle.merge_registry, MergeRuleRegistry)
    mechanism_registry = _load_model(store, bundle.mechanism_registry, MechanismTypeRegistry)
    constraint_registry = _load_model(store, bundle.constraint_registry, ConstraintRegistry)
    selector_field_registry = None
    if bundle.selector_field_registry is not None:
        selector_field_registry = _load_model(
            store, bundle.selector_field_registry, SelectorFieldRegistry
        )
    metric_registry = None
    if bundle.metric_registry is not None:
        metric_registry = _load_model(store, bundle.metric_registry, MetricRegistry)
    units_registry = None
    if bundle.units_registry is not None:
        units_registry = _load_model(store, bundle.units_registry, UnitsRegistry)
    trust_registry = None
    if bundle.trust_registry is not None:
        trust_registry = _load_model(store, bundle.trust_registry, TrustRegistry)
    return RegistryBundleContent(
        bundle_ref=bundle.bundle_ref,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        mechanism_registry=mechanism_registry,
        constraint_registry=constraint_registry,
        selector_field_registry=selector_field_registry,
        metric_registry=metric_registry,
        units_registry=units_registry,
        trust_registry=trust_registry,
    )
