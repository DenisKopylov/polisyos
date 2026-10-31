"""Load registry bundle payloads and dereference their member registries from CAS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import matches_artifact_store_protocol
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
from polisyos.core.artifacts.protocol import (
    ArtifactStore,
    CoreJSONArtifactStore,
)
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


class RegistryBundleModelReader(Protocol):
    """Read models through an existing selected, aggregate-bounded owner.

    This transport does not grant source permission or establish reader origin.
    The caller retains its fixed scoped reader and existing custody checks.
    """

    def read_typed_model(
        self, model: type[BaseModel], ref: ArtifactRef
    ) -> tuple[ArtifactManifest, BaseModel, int, int]:
        """Return the strict model and actual manifest/payload transfer counts."""
        ...


def _require_selected_reader_manifest(ref: ArtifactRef, manifest: ArtifactManifest) -> None:
    from polisyos.core.artifacts import artifact_manifest_profile_sha256

    if (
        not isinstance(ref, ArtifactRef)
        or ref.manifest_profile_sha256 is None
        or type(manifest) is not ArtifactManifest
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise ValueError("registry_bounded_reader_selected_manifest_mismatch")


def _read_model_from_reader[ModelT: BaseModel](
    reader: RegistryBundleModelReader, ref: ArtifactRef, model: type[ModelT]
) -> ModelT:
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("registry_bounded_reader_selected_reference_required")
    result = reader.read_typed_model(model, ref)
    if type(result) is not tuple or len(result) != 4:
        raise ValueError("registry_bounded_reader_model_receipt_invalid")
    manifest, value, manifest_bytes, payload_bytes = result
    _require_selected_reader_manifest(ref, manifest)
    if type(value) is not model or any(
        type(count) is not int or count < 0 for count in (manifest_bytes, payload_bytes)
    ):
        raise ValueError("registry_bounded_reader_model_receipt_invalid")
    return cast("ModelT", value)


def _require_core_json_reader(store: ArtifactStore) -> CoreJSONArtifactStore:
    """Narrow the minimal store ABI before any semantic registry read."""
    if not matches_artifact_store_protocol(store, CoreJSONArtifactStore):
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
    *,
    reader: RegistryBundleModelReader | None = None,
) -> ModelT:
    from polisyos.core.artifacts import load_core_json_artifact

    if reader is not None:
        if not isinstance(ref, ArtifactRef):
            raise ValueError("registry_bounded_reader_selected_reference_required")
        return _read_model_from_reader(reader, ref, model_cls)
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
    *,
    reader: RegistryBundleModelReader | None = None,
) -> RegistryBundlePayload:
    """Load a bundle payload after the public boundary has checked its reader."""
    return _load_model(store, bundle_ref, RegistryBundlePayload, reader=reader)


def load_registry_bundle_payload(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
    *,
    reader: RegistryBundleModelReader | None = None,
) -> RegistryBundlePayload:
    """Load the bundle graph, optionally through its fixed bounded model reader.

    Supplying a reader requires a full selected reference and has no legacy
    source-read fallback. Reader absence preserves the compatibility route.
    """
    core_json_store = _require_core_json_reader(store)
    return _load_registry_bundle_payload_core_json(core_json_store, bundle_ref, reader=reader)


def _load_registry_bundle_core_json(
    store: CoreJSONArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
    *,
    reader: RegistryBundleModelReader | None = None,
) -> RegistryBundle:
    """Load and normalize a bundle after the public boundary checked its reader."""
    payload = _load_registry_bundle_payload_core_json(store, bundle_ref, reader=reader)
    ref = _artifact_ref(
        bundle_ref,
        kind="core.registry_bundle",
        media_type="application/json",
    )
    return RegistryBundle(bundle_ref=ref, **payload.model_dump())


def load_registry_bundle(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
    *,
    reader: RegistryBundleModelReader | None = None,
) -> RegistryBundle:
    """Load and normalize a bundle, preserving an optional bounded model reader."""
    core_json_store = _require_core_json_reader(store)
    return _load_registry_bundle_core_json(core_json_store, bundle_ref, reader=reader)


def load_registry_bundle_content(
    store: ArtifactStore,
    bundle_ref: ArtifactRef | ArtifactID | str,
    *,
    reader: RegistryBundleModelReader | None = None,
) -> RegistryBundleContent:
    """Materialize the canonical registry graph through the selected read route.

    An optional fixed bounded reader receives the bundle and every existing
    required/optional member load; no member falls back to a legacy source read.
    """
    core_json_store = _require_core_json_reader(store)
    bundle = _load_registry_bundle_core_json(core_json_store, bundle_ref, reader=reader)
    slot_registry = _load_model(core_json_store, bundle.slot_registry, SlotRegistry, reader=reader)
    merge_registry = _load_model(
        core_json_store, bundle.merge_registry, MergeRuleRegistry, reader=reader
    )
    mechanism_registry = _load_model(
        core_json_store, bundle.mechanism_registry, MechanismTypeRegistry, reader=reader
    )
    constraint_registry = _load_model(
        core_json_store, bundle.constraint_registry, ConstraintRegistry, reader=reader
    )
    selector_field_registry = None
    if bundle.selector_field_registry is not None:
        selector_field_registry = _load_model(
            core_json_store, bundle.selector_field_registry, SelectorFieldRegistry, reader=reader
        )
    metric_registry = None
    if bundle.metric_registry is not None:
        metric_registry = _load_model(
            core_json_store, bundle.metric_registry, MetricRegistry, reader=reader
        )
    units_registry = None
    if bundle.units_registry is not None:
        units_registry = _load_model(
            core_json_store, bundle.units_registry, UnitsRegistry, reader=reader
        )
    trust_registry = None
    if bundle.trust_registry is not None:
        trust_registry = _load_model(
            core_json_store, bundle.trust_registry, TrustRegistry, reader=reader
        )
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
