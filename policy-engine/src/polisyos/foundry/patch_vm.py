from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import PatchOp
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
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    """Merge patch records into concrete PatchOp list using merge rules."""
    ops: list[PatchOp] = []
    for slot_id, records in sorted(patch_records.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")

        if rule.kind == MergeRuleKind.SUM:
            total_delta = None
            for record in records:
                delta = record.get("delta")
                if delta is None and "new_value" in record and "base_value" in record:
                    delta = record["new_value"] - record["base_value"]
                if delta is None:
                    raise ValueError(f"Missing delta for sum merge on slot '{slot_id}'")
                total_delta = delta if total_delta is None else total_delta + delta
            patch_value = total_delta if total_delta is not None else 0
            op_kind = "add"
        elif rule.kind == MergeRuleKind.OVERRIDE:
            picked = sorted(records, key=lambda item: item["node_id"])[-1]
            patch_value = picked.get("value", picked.get("new_value"))
            if patch_value is None:
                raise ValueError(f"Missing value for override merge on slot '{slot_id}'")
            op_kind = "set"
        elif rule.kind == MergeRuleKind.PRIORITY:
            missing = [item["node_id"] for item in records if item.get("priority") is None]
            if missing:
                raise ValueError(
                    f"Merge rule 'priority' requires priority for: {', '.join(sorted(missing))}"
                )
            picked = sorted(
                records,
                key=lambda item: (-int(item["priority"]), item["node_id"]),
            )[0]
            patch_value = picked.get("value", picked.get("new_value"))
            if patch_value is None:
                raise ValueError(f"Missing value for priority merge on slot '{slot_id}'")
            op_kind = "set"
        elif rule.kind == MergeRuleKind.ERROR:
            if len(records) > 1:
                ids = ", ".join(sorted(item["node_id"] for item in records))
                raise ValueError(f"Merge conflict for slot '{slot_id}': {ids}")
            patch_value = records[0].get("value", records[0].get("new_value"))
            if patch_value is None:
                raise ValueError(f"Missing value for error merge on slot '{slot_id}'")
            op_kind = "set"
        else:
            raise ValueError(f"Unsupported merge rule '{rule.kind}' for '{slot_id}'")

        value_ref = _put_tensor(store, patch_value)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op_kind,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}"],
            )
        )
    return ops
