"""State-delta application, patch-record helpers, and combined delta+snapshot."""

from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import PatchOp, StateDelta
from polisyos.foundry.execute.patch_vm import merge_patch_records
from polisyos.foundry.methods.merge_engine import MergeEngine, MergeRecord
from polisyos.ir.kernel import MergeRuleRegistry, SlotRegistry

from ._models import (
    ApplyArtifacts,
    artifact_id,
    get_state_path,
    load_model,
    set_state_path,
)
from ._ops import apply_ops_for_slot, validate_ops_compatibility
from ._snapshots import put_state_snapshot

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
    store: FileSystemCAS,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> Any:
    """Apply a CAS-backed StateDelta to a base state using slot merge rules."""
    state_delta = load_model(store, state_delta_ref, StateDelta)
    ops_by_slot: dict[str, list[PatchOp]] = {}
    for op in state_delta.ops:
        ops_by_slot.setdefault(op.slot_id, []).append(op)

    state = base_state
    for slot_id, ops in sorted(ops_by_slot.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        validate_ops_compatibility(slot_id, rule.kind, ops)

        base_value = get_state_path(state, slot_spec.state_path)
        merged = apply_ops_for_slot(store, base_value, ops)
        state = set_state_path(state, slot_spec.state_path, merged)

    return state


def apply_patch_records(
    base_state: Any,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> Any:
    """
    Apply in-memory patch records (delta/value/new_value) to a state.
    Mirrors merge_patch_records semantics without CAS IO.
    """
    engine = MergeEngine(slot_registry, merge_registry)

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
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        base_values[slot_id] = get_state_path(base_state, slot_spec.state_path)

    report = engine.merge_records(records, base_values)
    report.raise_if_conflicts()

    state = base_state
    for slot_id, merged_value in report.merged_values.items():
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        state = set_state_path(state, slot_spec.state_path, merged_value)
    return state


def apply_patch_map(
    base_state: Any,
    patch_map: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    default_node_id: str = "mechanism",
    priority: int | None = None,
) -> Any:
    """Normalize a slot patch map into merge records and apply it to state."""
    patch_records: dict[str, list[dict[str, Any]]] = {}
    for slot_id, patches in patch_map.items():
        patch_list = patches if isinstance(patches, list) else [patches]
        for patch in patch_list:
            record = {"node_id": default_node_id}
            if "priority" not in patch:
                record["priority"] = priority
            record.update(patch)
            patch_records.setdefault(slot_id, []).append(record)
    return apply_patch_records(
        base_state,
        patch_records,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )


def apply_state_delta_and_snapshot(
    store: FileSystemCAS,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    step: int | None = None,
    base_ref: ArtifactRef | None = None,
) -> tuple[Any, ApplyArtifacts]:
    """Apply a StateDelta and persist the resulting state snapshot artifact."""
    state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )
    snapshot_ref = put_state_snapshot(
        store,
        state=state,
        step=step,
        inputs=[
            InputRef(artifact_id=artifact_id(state_delta_ref), role="state_delta"),
        ]
        + (
            [InputRef(artifact_id=base_ref.artifact_id, role="base_state")]
            if base_ref is not None
            else []
        ),
    )
    return state, ApplyArtifacts(state_snapshot_ref=snapshot_ref)


# ---------------------------------------------------------------------------
# Internal helper (thin wrapper kept for backward compat)
# ---------------------------------------------------------------------------


def _merge_patch_records(
    store: FileSystemCAS,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    return merge_patch_records(
        store,
        patch_records,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )
