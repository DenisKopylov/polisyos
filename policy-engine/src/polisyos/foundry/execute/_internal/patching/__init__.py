"""State-delta application, patch-record helpers, and combined delta+snapshot."""

from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import ArtifactStore, CoreJSONArtifactStore
from polisyos.core.contracts.foundry import PatchOp, StateDelta
from polisyos.foundry.execute._internal.models import (
    ApplyArtifacts,
    artifact_input_ref,
    get_state_path,
    load_model,
    set_state_path,
)
from polisyos.foundry.execute._internal.ops import (
    apply_ops_to_state,
)
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot
from polisyos.foundry.execute.patch_vm import (
    ModelStatePatchContext,
    _model_state_patch_base_values,
    _validate_model_state_patch_context,
    merge_patch_records,
)
from polisyos.foundry.methods.components.merge_engine import MergeEngine, MergeRecord
from polisyos.ir.kernel import MergeRuleRegistry, SlotRegistry

__all__ = [
    "apply_patch_map",
    "apply_patch_records",
    "apply_state_delta",
    "apply_state_delta_and_snapshot",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_state_delta(
    store: CoreJSONArtifactStore,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    model_state_context: ModelStatePatchContext | None = None,
) -> Any:
    """Apply a CAS-backed StateDelta to a base state using slot merge rules."""
    state_delta = load_model(store, state_delta_ref, StateDelta)
    if model_state_context is not None and type(model_state_context) is not ModelStatePatchContext:
        raise ValueError("model_scalar_state_patch_context_required")
    if model_state_context is not None and (
        state_delta.base_ref is None
        or artifact_ref_identity_key(state_delta.base_ref)
        != artifact_ref_identity_key(model_state_context.base_ref)
    ):
        raise ValueError("model_scalar_state_patch_base_ref_mismatch")
    if model_state_context is not None and base_state is not model_state_context._opening_state:
        raise ValueError("model_scalar_state_patch_opening_state_required")
    return apply_ops_to_state(
        store,
        base_state=base_state,
        ops=state_delta.ops,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        model_state_context=model_state_context,
    )


def apply_patch_records(
    base_state: Any,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    model_state_context: ModelStatePatchContext | None = None,
) -> Any:
    """
    Apply in-memory patch records (delta/value/new_value) to a state.
    Mirrors merge_patch_records semantics without CAS IO.
    """
    _validate_model_state_patch_context(
        model_state_context,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        base_state=base_state,
    )
    engine = MergeEngine(slot_registry, merge_registry)
    model_base_values = _model_state_patch_base_values(
        patch_records, slot_registry=slot_registry, context=model_state_context
    )

    records: list[MergeRecord] = []
    for slot_id, slot_records in patch_records.items():
        for record in slot_records:
            delta = record.get("delta")
            if delta is None and "new_value" in record and "base_value" in record:
                delta = record["new_value"] - record["base_value"]
            records.append(
                MergeRecord(
                    node_id=record.get("node_id", "unknown"),
                    slot_id=slot_id,
                    value=record.get("value", record.get("new_value")),
                    delta=delta,
                    priority=record.get("priority"),
                    timestamp=record.get("timestamp"),
                )
            )

    base_values: dict[str, Any] = {}
    for slot_id in patch_records:
        slot_spec = slot_registry.slots.get(slot_id)
        if (
            slot_spec is None
            or slot_spec.state_path == ""
            or (slot_spec.state_path is None and model_state_context is None)
        ):
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        base_values[slot_id] = (
            model_base_values[slot_id]
            if slot_spec.state_path is None
            else get_state_path(base_state, slot_spec.state_path)
        )

    report = engine.merge_records(records, base_values)
    report.raise_if_conflicts()

    state = base_state
    for slot_id, merged_value in report.merged_values.items():
        slot_spec = slot_registry.slots.get(slot_id)
        if (
            slot_spec is None
            or slot_spec.state_path == ""
            or (slot_spec.state_path is None and model_state_context is None)
        ):
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        state = (
            model_state_context._with_state_after_validation(state).write_slot(
                slot_id, merged_value
            )
            if slot_spec.state_path is None and model_state_context is not None
            else set_state_path(state, slot_spec.state_path, merged_value)
        )
    return state


def apply_patch_map(
    base_state: Any,
    patch_map: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    default_node_id: str = "mechanism",
    priority: int | None = None,
    model_state_context: ModelStatePatchContext | None = None,
) -> Any:
    """Normalize a slot patch map into merge records and apply it to state."""
    patch_records: dict[str, list[dict[str, Any]]] = {}
    for slot_id, patches in patch_map.items():
        patch_list = patches if isinstance(patches, list) else [patches]
        for patch in patch_list:
            record = dict(patch)
            record.setdefault("node_id", default_node_id)
            if "priority" not in patch:
                record["priority"] = priority
            patch_records.setdefault(slot_id, []).append(record)
    return apply_patch_records(
        base_state,
        patch_records,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        model_state_context=model_state_context,
    )


def apply_state_delta_and_snapshot(
    store: CoreJSONArtifactStore,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    step: int | None = None,
    base_ref: ArtifactRef | None = None,
    return_selected_profile: bool = False,
    model_state_context: ModelStatePatchContext | None = None,
) -> tuple[Any, ApplyArtifacts]:
    """Apply a StateDelta and persist the resulting state snapshot artifact."""
    state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        model_state_context=model_state_context,
    )
    if model_state_context is not None:
        if base_ref is not None and artifact_ref_identity_key(
            base_ref
        ) != artifact_ref_identity_key(model_state_context.base_ref):
            raise ValueError("model_scalar_state_patch_base_ref_mismatch")
        base_ref = model_state_context.base_ref
    snapshot_ref = put_state_snapshot(
        store,
        state=(
            model_state_context._with_state_after_validation(state).bound_state
            if model_state_context is not None
            else state
        ),
        step=step,
        inputs=[
            artifact_input_ref(state_delta_ref, role="state_delta"),
        ]
        + (
            [input_ref_from_artifact_ref(base_ref, role="base_state")]
            if base_ref is not None
            else []
        ),
        return_selected_profile=return_selected_profile,
    )
    return state, ApplyArtifacts(state_snapshot_ref=snapshot_ref)


# ---------------------------------------------------------------------------
# Internal helper (thin wrapper kept for backward compat)
# ---------------------------------------------------------------------------


def _merge_patch_records(
    store: ArtifactStore,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    model_state_context: ModelStatePatchContext | None = None,
) -> list[PatchOp]:
    return merge_patch_records(
        store,
        patch_records,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        model_state_context=model_state_context,
    )
