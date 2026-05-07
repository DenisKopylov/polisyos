"""Public foundry patch vm module API."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import PatchOp
from polisyos.foundry.methods.components.merge_engine import MergeEngine, MergeRecord
from polisyos.ir.kernel import MergeRuleKind, MergeRuleRegistry, SlotRegistry


def _artifact_id(value: ArtifactRef | str) -> str:
    return value.artifact_id if isinstance(value, ArtifactRef) else str(value)


def _put_tensor(store: FileSystemCAS, value: Any) -> ArtifactRef:
    array = np.asarray(value)
    buf = BytesIO()
    np.save(buf, array, allow_pickle=False)
    data = buf.getvalue()
    return store.put_bytes(
        data,
        PutOptions(kind="foundry.patch_value", media_type="application/x-npy"),
    )


def _load_tensor(store: FileSystemCAS, ref: ArtifactRef | str) -> np.ndarray:
    data = store.get_bytes(_artifact_id(ref))
    return np.load(BytesIO(data), allow_pickle=False)


def merge_patch_records(
    store: FileSystemCAS,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    base_values: dict[str, Any] | None = None,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    """Merge patch records into concrete PatchOp list using merge rules."""
    engine = MergeEngine(slot_registry, merge_registry)
    records: list[MergeRecord] = []
    effective_base_values = dict(base_values or {})
    for slot_id, slot_records in patch_records.items():
        for record in slot_records:
            delta = record.get("delta")
            if delta is None and "new_value" in record and "base_value" in record:
                delta = record["new_value"] - record["base_value"]
            if slot_id not in effective_base_values and "base_value" in record:
                effective_base_values[slot_id] = record["base_value"]
            node_id = record.get("node_id") or record.get("intervention_id") or "unknown"
            records.append(
                MergeRecord(
                    node_id=node_id,
                    slot_id=slot_id,
                    value=record.get("value", record.get("new_value")),
                    delta=delta,
                    priority=record.get("priority"),
                    timestamp=record.get("timestamp"),
                )
            )

    report = engine.merge_records(records, effective_base_values)
    report.raise_if_conflicts()

    ops: list[PatchOp] = []
    for slot_id, merged_value in sorted(report.merged_values.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")

        op_kind = "add" if rule.kind == MergeRuleKind.SUM else "set"
        payload = merged_value
        if rule.kind == MergeRuleKind.SUM and slot_id in effective_base_values:
            payload = merged_value - effective_base_values[slot_id]
        value_ref = _put_tensor(store, payload)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op_kind,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}"],
            )
        )
    return ops
