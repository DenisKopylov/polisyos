"""Host-side access to model-owned scalar slots carried in ``GlobalState``.

This module is the single layout-aware accessor for the bounded scalar GLOBAL
stock carrier. Call it before entering JAX-transformed code. Semantic slot IDs
and artifact references remain in the selected host-side layout; only numeric
arrays enter the JAX pytree.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.protocol import CoreJSONArtifactStore
from polisyos.core.contracts.model_state_layout import (
    ModelScalarStateLayout,
    ModelScalarStateLayoutRef,
    ModelScalarStateSlot,
    model_scalar_state_layout_digest,
)
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry.loader import load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState, ModelScalarState
from polisyos.ir.kernel import SlotKind, SlotScope, SlotValueType


class ModelScalarStateAccessError(ValueError):
    """Typed refusal for missing, mismatched, or invalid model scalar state."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def build_model_scalar_state_layout(
    *,
    store: CoreJSONArtifactStore,
    registry_bundle_ref: ArtifactRef,
    slot_ids: tuple[str, ...],
) -> ModelScalarStateLayout:
    """Open a selected registry bundle and build its scalar GLOBAL stock layout.

    The canonical registry loader resolves the slot definitions from the exact
    selected bundle. This is the sole production layout factory; callers cannot
    supply independent slot descriptors or claim a registry-to-layout mapping.
    """

    if (
        not slot_ids
        or any(type(slot_id) is not str for slot_id in slot_ids)
        or len(set(slot_ids)) != len(slot_ids)
    ):
        raise ModelScalarStateAccessError("model_scalar_state_slot_selection_invalid")
    try:
        selected_registry = load_registry_bundle_content(store, registry_bundle_ref)
    except Exception as exc:
        raise ModelScalarStateAccessError("model_scalar_state_registry_bundle_unavailable") from exc
    if artifact_ref_identity_key(selected_registry.bundle_ref) != artifact_ref_identity_key(
        registry_bundle_ref
    ):
        raise ModelScalarStateAccessError("model_scalar_state_registry_bundle_mismatch")

    descriptors: list[ModelScalarStateSlot] = []
    for slot_id in sorted(slot_ids):
        spec = selected_registry.slot_registry.slots.get(slot_id)
        if spec is None:
            raise ModelScalarStateAccessError("model_scalar_state_slot_unregistered")
        if (
            spec.state_path is not None
            or spec.scope is not SlotScope.GLOBAL
            or spec.kind is not SlotKind.STOCK
            or spec.value_type is not SlotValueType.DECIMAL
            or spec.unit is None
            or spec.dtype != "float32"
            or spec.shape != []
        ):
            raise ModelScalarStateAccessError("model_scalar_state_slot_profile_unsupported")
        spec_payload = json.dumps(
            spec.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        slot_spec_sha256 = f"sha256:{hashlib.sha256(spec_payload.encode('utf-8')).hexdigest()}"
        descriptors.append(
            ModelScalarStateSlot(
                slot_id=slot_id,
                index=len(descriptors),
                slot_spec_sha256=slot_spec_sha256,
            )
        )
    slot_tuple = tuple(descriptors)
    return ModelScalarStateLayout(
        registry_bundle_ref=registry_bundle_ref,
        slots=slot_tuple,
        layout_sha256=model_scalar_state_layout_digest(
            registry_bundle_ref=registry_bundle_ref,
            slots=slot_tuple,
        ),
    )


@dataclass(frozen=True, slots=True)
class BoundModelState:
    """Host-side binding of numeric state to its exact selected slot layout.

    This wrapper is intentionally not a JAX pytree. Pass ``state`` alone into
    numerical transforms, then reattach it to this same binding after return.
    Persistent snapshot admission is responsible for reconstructing this pair
    from exact snapshot lineage; never manufacture it from an unqualified blob.
    """

    state: GlobalState
    layout: ModelScalarStateLayout
    layout_ref: ModelScalarStateLayoutRef | None = None
    source_snapshot_ref: StateSnapshotRef | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not GlobalState:
            raise ModelScalarStateAccessError("model_scalar_state_global_state_required")
        _validate_carrier_shape(self.state.model_scalar_state, len(self.layout.slots))
        _validate_carrier_values(self.state.model_scalar_state)
        if self.layout_ref is not None:
            _validate_layout_ref(self.layout_ref, self.layout)
        if self.source_snapshot_ref is not None and (
            self.source_snapshot_ref.kind != "foundry.state_snapshot"
            or self.source_snapshot_ref.media_type != "application/json"
            or self.source_snapshot_ref.manifest_profile_sha256 is None
        ):
            raise ModelScalarStateAccessError("model_scalar_state_source_snapshot_ref_invalid")


def empty_model_scalar_state(layout: ModelScalarStateLayout) -> ModelScalarState:
    """Create the fixed-shape absent carrier for one selected verified layout."""

    return ModelScalarState.empty(len(layout.slots))


def bind_model_state(
    state: GlobalState,
    *,
    selected_registry_bundle_ref: ArtifactRef,
    store: CoreJSONArtifactStore,
    slot_ids: tuple[str, ...],
) -> BoundModelState:
    """Initialize model state from an empty GlobalState and a selected CAS bundle.

    The layout is derived from the opened registry bundle here; callers cannot
    provide an independently asserted layout at the initialization boundary.
    """

    layout = build_model_scalar_state_layout(
        store=store,
        registry_bundle_ref=selected_registry_bundle_ref,
        slot_ids=slot_ids,
    )
    _validate_selected_layout(
        layout,
        selected_registry_bundle_ref=selected_registry_bundle_ref,
        selected_layout_sha256=layout.layout_sha256,
    )
    if type(state) is not GlobalState:
        raise ModelScalarStateAccessError("model_scalar_state_global_state_required")
    if state.model_scalar_state is not None:
        raise ModelScalarStateAccessError("model_scalar_state_initial_binding_requires_empty_state")
    state = state.replace(model_scalar_state=empty_model_scalar_state(layout))
    _validate_carrier_shape(state.model_scalar_state, len(layout.slots))
    return BoundModelState(state=state, layout=layout)


def reattach_model_state_after_execution(
    bound_state: BoundModelState,
    executed_state: GlobalState,
) -> BoundModelState:
    """Reattach unchanged host-side layout identity after a JAX execution step."""

    if type(bound_state) is not BoundModelState or type(executed_state) is not GlobalState:
        raise ModelScalarStateAccessError("model_scalar_state_execution_binding_invalid")
    _validate_carrier_shape(executed_state.model_scalar_state, len(bound_state.layout.slots))
    return BoundModelState(
        state=executed_state,
        layout=bound_state.layout,
        layout_ref=bound_state.layout_ref,
        source_snapshot_ref=bound_state.source_snapshot_ref,
    )


def read_model_scalar_state_slot(
    bound_state: BoundModelState,
    *,
    slot_id: str,
    selected_registry_bundle_ref: ArtifactRef,
    selected_layout_sha256: str,
) -> jnp.ndarray:
    """Read a present finite scalar after checking its selected host-side identity.

    The returned scalar array may be passed as an ordinary JAX argument. This
    function itself must not be called from inside ``jit``, ``scan``, or another
    transformed numerical function.
    """

    _validate_bound_context(
        bound_state,
        selected_registry_bundle_ref=selected_registry_bundle_ref,
        selected_layout_sha256=selected_layout_sha256,
    )
    layout = bound_state.layout
    carrier = bound_state.state.model_scalar_state
    assert carrier is not None
    _validate_carrier_shape(carrier, len(layout.slots))
    descriptor = _slot_descriptor(layout, slot_id)
    present = np.asarray(carrier.present[descriptor.index])
    value = np.asarray(carrier.values[descriptor.index])
    if present.shape != () or present.dtype != np.dtype(np.bool_):
        raise ModelScalarStateAccessError("model_scalar_state_presence_invalid")
    if not bool(present.item()):
        raise ModelScalarStateAccessError("model_scalar_state_slot_absent")
    if value.shape != () or value.dtype != np.dtype(np.float32):
        raise ModelScalarStateAccessError("model_scalar_state_value_invalid")
    if not bool(np.isfinite(value).item()):
        raise ModelScalarStateAccessError("model_scalar_state_value_nonfinite")
    return carrier.values[descriptor.index]


def write_model_scalar_state_slot(
    bound_state: BoundModelState,
    *,
    slot_id: str,
    value: Any,
    selected_registry_bundle_ref: ArtifactRef,
    selected_layout_sha256: str,
) -> BoundModelState:
    """Return state with one finite scalar slot present and written.

    Callers must be the existing authorized binding owner or patch VM after
    validating ownership and merge semantics. This primitive validates the
    selected layout and numeric representation; it does not grant authority.
    """

    _validate_bound_context(
        bound_state,
        selected_registry_bundle_ref=selected_registry_bundle_ref,
        selected_layout_sha256=selected_layout_sha256,
    )
    layout = bound_state.layout
    descriptor = _slot_descriptor(layout, slot_id)
    scalar = np.asarray(value)
    if scalar.shape != () or scalar.dtype.hasobject or scalar.dtype.kind not in {"i", "u", "f"}:
        raise ModelScalarStateAccessError("model_scalar_state_write_requires_numeric_scalar")
    if not bool(np.isfinite(scalar).item()):
        raise ModelScalarStateAccessError("model_scalar_state_write_nonfinite")
    converted = np.asarray(scalar, dtype=np.float32)
    if not bool(np.isfinite(converted).item()):
        raise ModelScalarStateAccessError("model_scalar_state_write_out_of_range")

    carrier = bound_state.state.model_scalar_state
    assert carrier is not None
    _validate_carrier_shape(carrier, len(layout.slots))
    updated = ModelScalarState(
        values=carrier.values.at[descriptor.index].set(jnp.asarray(converted, dtype=jnp.float32)),
        present=carrier.present.at[descriptor.index].set(True),
    )
    return BoundModelState(
        state=bound_state.state.replace(model_scalar_state=updated),
        layout=layout,
        layout_ref=bound_state.layout_ref,
        source_snapshot_ref=bound_state.source_snapshot_ref,
    )


def _validate_bound_context(
    bound_state: BoundModelState,
    *,
    selected_registry_bundle_ref: ArtifactRef,
    selected_layout_sha256: str,
) -> None:
    if type(bound_state) is not BoundModelState:
        raise ModelScalarStateAccessError("model_scalar_state_layout_binding_required")
    _validate_selected_layout(
        bound_state.layout,
        selected_registry_bundle_ref=selected_registry_bundle_ref,
        selected_layout_sha256=selected_layout_sha256,
    )


def _validate_selected_layout(
    layout: ModelScalarStateLayout,
    *,
    selected_registry_bundle_ref: ArtifactRef,
    selected_layout_sha256: str,
) -> None:
    if type(layout) is not ModelScalarStateLayout:
        raise ModelScalarStateAccessError("model_scalar_state_layout_required")
    if not isinstance(selected_registry_bundle_ref, ArtifactRef):
        raise ModelScalarStateAccessError("model_scalar_state_selected_registry_ref_required")
    if artifact_ref_identity_key(layout.registry_bundle_ref) != artifact_ref_identity_key(
        selected_registry_bundle_ref
    ):
        raise ModelScalarStateAccessError("model_scalar_state_registry_bundle_mismatch")
    if layout.layout_sha256 != selected_layout_sha256:
        raise ModelScalarStateAccessError("model_scalar_state_layout_mismatch")


def _validate_layout_ref(
    layout_ref: ModelScalarStateLayoutRef,
    layout: ModelScalarStateLayout,
) -> None:
    if (
        type(layout_ref) is not ModelScalarStateLayoutRef
        or layout_ref.kind != "foundry.model_scalar_state_layout"
        or layout_ref.media_type != "application/json"
        or layout_ref.manifest_profile_sha256 is None
        or layout.registry_bundle_ref.manifest_profile_sha256 is None
    ):
        raise ModelScalarStateAccessError("model_scalar_state_layout_ref_invalid")


def _slot_descriptor(layout: ModelScalarStateLayout, slot_id: str):
    try:
        return layout.slot(slot_id)
    except (KeyError, TypeError) as exc:
        raise ModelScalarStateAccessError("model_scalar_state_slot_not_in_selected_layout") from exc


def _validate_carrier_shape(carrier: ModelScalarState, slot_count: int) -> None:
    if type(carrier) is not ModelScalarState:
        raise ModelScalarStateAccessError("model_scalar_state_carrier_invalid")
    if (
        tuple(carrier.values.shape) != (slot_count,)
        or carrier.values.dtype != jnp.float32
        or tuple(carrier.present.shape) != (slot_count,)
        or carrier.present.dtype != jnp.bool_
    ):
        raise ModelScalarStateAccessError("model_scalar_state_layout_shape_mismatch")


def _validate_carrier_values(carrier: ModelScalarState) -> None:
    """Validate host-visible numeric values without entering a JAX transform."""

    values = np.asarray(carrier.values)
    present = np.asarray(carrier.present)
    if not bool(np.isfinite(values).all()):
        raise ModelScalarStateAccessError("model_scalar_state_value_nonfinite")
    if not bool(np.equal(values[~present], np.float32(0.0)).all()):
        raise ModelScalarStateAccessError("model_scalar_state_absent_value_not_canonical_zero")
