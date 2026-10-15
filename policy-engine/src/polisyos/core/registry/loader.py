"""Load registry bundle payloads and dereference their member registries from CAS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore, CoreJSONArtifactStore
from polisyos.core.artifacts.registry import RegistryBundle, RegistryBundlePayload
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    MetricRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    TrustRegistry,
    UnitsRegistry,
)

if TYPE_CHECKING:
    from pydantic import BaseModel


def _require_core_json_reader(store: ArtifactStore) -> CoreJSONArtifactStore:
    """Narrow the minimal store ABI before any semantic registry read."""
    if not isinstance(store, CoreJSONArtifactStore):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    return store


def _artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _store_read_ref(value: ArtifactRef | ArtifactID | str) -> ArtifactRef | ArtifactID:
    """Keep a selected manifest profile intact at the ArtifactStore boundary."""
    if isinstance(value, ArtifactRef):
        return value
    return _artifact_id(value)


def _artifact_ref(
    value: ArtifactRef | ArtifactID | str, *, kind: str, media_type: str
) -> ArtifactRef:
    if isinstance(value, ArtifactRef):
        return value
    return ArtifactRef(artifact_id=_artifact_id(value), kind=kind, media_type=media_type)


def _load_model[ModelT: BaseModel](
    store: CoreJSONArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
    model_cls: type[ModelT],
) -> ModelT:
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, _store_read_ref(ref))
    return model_cls.model_validate(payload)


@dataclass(frozen=True)
class RegistryBundleContent:
    """Hold the fully materialized registry objects referenced by one bundle."""

    bundle_ref: ArtifactRef
    slot_registry: SlotRegistry
    merge_registry: MergeRuleRegistry
    mechanism_registry: MechanismTypeRegistry
    constraint_registry: ConstraintRegistry
    selector_field_registry: SelectorFieldRegistry | None
    metric_registry: MetricRegistry | None
    units_registry: UnitsRegistry | None
    trust_registry: TrustRegistry | None


def _load_registry_bundle_payload_core_json(
    store: CoreJSONArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
) -> RegistryBundlePayload:
    """Load a bundle payload after the public boundary has checked its reader."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, _store_read_ref(bundle_ref))
    return RegistryBundlePayload.model_validate(payload)


def load_registry_bundle_payload(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
) -> RegistryBundlePayload:
    """Load only the bundle payload graph without dereferencing member registries."""
    core_json_store = _require_core_json_reader(store)
    return _load_registry_bundle_payload_core_json(core_json_store, bundle_ref)


def _load_registry_bundle_core_json(
    store: CoreJSONArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
) -> RegistryBundle:
    """Load and normalize a bundle after the public boundary checked its reader."""
    payload = _load_registry_bundle_payload_core_json(store, bundle_ref)
    ref = _artifact_ref(
        bundle_ref,
        kind="core.registry_bundle",
        media_type="application/json",
    )
    return RegistryBundle(bundle_ref=ref, **payload.model_dump())


def load_registry_bundle(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
) -> RegistryBundle:
    """Load the bundle payload and normalize the bundle reference ABI."""
    core_json_store = _require_core_json_reader(store)
    return _load_registry_bundle_core_json(core_json_store, bundle_ref)


def load_registry_bundle_content(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
) -> RegistryBundleContent:
    """Load a bundle and materialize all referenced registry objects from CAS."""
    core_json_store = _require_core_json_reader(store)
    bundle = _load_registry_bundle_core_json(core_json_store, bundle_ref)
    slot_registry = _load_model(core_json_store, bundle.slot_registry, SlotRegistry)
    merge_registry = _load_model(core_json_store, bundle.merge_registry, MergeRuleRegistry)
    mechanism_registry = _load_model(
        core_json_store, bundle.mechanism_registry, MechanismTypeRegistry
    )
    constraint_registry = _load_model(
        core_json_store, bundle.constraint_registry, ConstraintRegistry
    )
    selector_field_registry = None
    if bundle.selector_field_registry is not None:
        selector_field_registry = _load_model(
            core_json_store, bundle.selector_field_registry, SelectorFieldRegistry
        )
    metric_registry = None
    if bundle.metric_registry is not None:
        metric_registry = _load_model(core_json_store, bundle.metric_registry, MetricRegistry)
    units_registry = None
    if bundle.units_registry is not None:
        units_registry = _load_model(core_json_store, bundle.units_registry, UnitsRegistry)
    trust_registry = None
    if bundle.trust_registry is not None:
        trust_registry = _load_model(core_json_store, bundle.trust_registry, TrustRegistry)
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
