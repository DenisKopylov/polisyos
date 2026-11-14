"""Public foundry patch vm module API."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from io import BytesIO
from typing import TYPE_CHECKING, Any

import numpy as np

from polisyos.core.artifacts import validate_return_selected_profile
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.contracts.foundry import PatchOp
from polisyos.foundry.execute._internal.models import put_tensor
from polisyos.foundry.methods.components.merge_engine import MergeEngine, MergeRecord
from polisyos.ir.kernel import MergeRuleKind, MergeRuleRegistry, SlotRegistry

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import CoreJSONArtifactStore
    from polisyos.core.registry import RegistryBundleContent
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.model_state_slots import BoundModelState


def _registry_payload(registry: SlotRegistry | MergeRuleRegistry) -> str:
    return json.dumps(registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ModelStatePatchContext:
    """Admit one selected persistent model-state base for host-side patching.

    Construction opens the actual selected snapshot and registries through
    their canonical readers. The resulting facts are scoped to this execution;
    they are neither an authority grant nor a substitute for current permission
    checks. Semantic names and CAS references never enter the numerical pytree.

    Attributes:
        store: Scoped store used to admit and subsequently apply the patches.
        base_ref: Exact selected opening snapshot, including manifest profile.
        registry_bundle_ref: Exact selected registry used by this execution.
        bound_state: Canonically loaded state and its persistent layout.
        registry: Canonically loaded selected registry content.
    """

    store: CoreJSONArtifactStore
    base_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    bound_state: BoundModelState = field(init=False)
    registry: RegistryBundleContent = field(init=False)
    _opening_state: GlobalState = field(init=False, repr=False)
    _base_identity: tuple[str, str, str, str | None] = field(init=False, repr=False)
    _registry_identity: tuple[str, str, str, str | None] = field(init=False, repr=False)
    _layout_payload: str = field(init=False, repr=False)
    _slot_registry_payload: str = field(init=False, repr=False)
    _merge_registry_payload: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        from polisyos.core.registry import load_registry_bundle_content
        from polisyos.foundry.execute._internal.snapshots import load_bound_model_state_snapshot
        from polisyos.foundry.model_state_slots import ModelScalarStateAccessError

        bound_state = load_bound_model_state_snapshot(self.store, snapshot_ref=self.base_ref)
        if artifact_ref_identity_key(self.registry_bundle_ref) != artifact_ref_identity_key(
            bound_state.layout.registry_bundle_ref
        ):
            raise ModelScalarStateAccessError("model_scalar_state_patch_registry_mismatch")
        registry = load_registry_bundle_content(self.store, self.registry_bundle_ref)
        if artifact_ref_identity_key(registry.bundle_ref) != artifact_ref_identity_key(
            self.registry_bundle_ref
        ):
            raise ModelScalarStateAccessError("model_scalar_state_patch_registry_mismatch")
        object.__setattr__(self, "bound_state", bound_state)
        object.__setattr__(self, "registry", registry)
        object.__setattr__(self, "_opening_state", bound_state.state)
        object.__setattr__(self, "_base_identity", artifact_ref_identity_key(self.base_ref))
        object.__setattr__(
            self, "_registry_identity", artifact_ref_identity_key(self.registry_bundle_ref)
        )
        object.__setattr__(self, "_layout_payload", bound_state.layout.model_dump_json())
        object.__setattr__(
            self, "_slot_registry_payload", _registry_payload(registry.slot_registry)
        )
        object.__setattr__(
            self, "_merge_registry_payload", _registry_payload(registry.merge_registry)
        )

    def validate_inputs(
        self,
        *,
        slot_registry: SlotRegistry,
        merge_registry: MergeRuleRegistry,
        base_state: Any | None = None,
        store: ArtifactStore | None = None,
    ) -> None:
        """Check actual operation inputs against the admitted immutable facts."""
        from polisyos.foundry.model_state_slots import ModelScalarStateAccessError

        if store is not None and store is not self.store:
            raise ModelScalarStateAccessError("model_scalar_state_patch_store_mismatch")
        if base_state is not None and base_state is not self.bound_state.state:
            raise ModelScalarStateAccessError("model_scalar_state_patch_base_state_mismatch")
        source_ref = self.bound_state.source_snapshot_ref
        if (
            source_ref is None
            or self.bound_state.layout_ref is None
            or artifact_ref_identity_key(self.base_ref) != self._base_identity
            or artifact_ref_identity_key(source_ref) != self._base_identity
        ):
            raise ModelScalarStateAccessError("model_scalar_state_patch_base_ref_mismatch")
        if (
            artifact_ref_identity_key(self.registry_bundle_ref) != self._registry_identity
            or artifact_ref_identity_key(self.bound_state.layout.registry_bundle_ref)
            != self._registry_identity
            or self.bound_state.layout.model_dump_json() != self._layout_payload
        ):
            raise ModelScalarStateAccessError("model_scalar_state_patch_registry_mismatch")
        if (
            _registry_payload(slot_registry) != self._slot_registry_payload
            or _registry_payload(merge_registry) != self._merge_registry_payload
        ):
            raise ModelScalarStateAccessError("model_scalar_state_patch_registry_content_mismatch")

    def with_state(self, state: GlobalState) -> ModelStatePatchContext:
        """Reattach actual in-memory execution output without reloading its base."""
        self.validate_inputs(
            slot_registry=self.registry.slot_registry, merge_registry=self.registry.merge_registry
        )
        return self._with_state_after_validation(state)

    def _with_state_after_validation(self, state: GlobalState) -> ModelStatePatchContext:
        """Reattach within an operation whose immutable context was checked once."""
        from polisyos.foundry.model_state_slots import reattach_model_state_after_execution

        bound_state = reattach_model_state_after_execution(self.bound_state, state)
        result = object.__new__(type(self))
        for descriptor in fields(self):
            object.__setattr__(result, descriptor.name, getattr(self, descriptor.name))
        object.__setattr__(result, "bound_state", bound_state)
        return result

    def read_slot(self, slot_id: str) -> Any:
        """Read a present scalar through the canonical selected-layout accessor."""
        from polisyos.foundry.model_state_slots import read_model_scalar_state_slot

        return read_model_scalar_state_slot(
            self.bound_state,
            slot_id=slot_id,
            selected_registry_bundle_ref=self.registry_bundle_ref,
            selected_layout_sha256=self.bound_state.layout.layout_sha256,
        )

    def write_slot(self, slot_id: str, value: Any) -> GlobalState:
        """Write a finite scalar after the caller validates its actual merge rule."""
        from polisyos.foundry.model_state_slots import write_model_scalar_state_slot

        return write_model_scalar_state_slot(
            self.bound_state,
            slot_id=slot_id,
            value=value,
            selected_registry_bundle_ref=self.registry_bundle_ref,
            selected_layout_sha256=self.bound_state.layout.layout_sha256,
        ).state


def _validate_model_state_patch_context(
    context: ModelStatePatchContext | None,
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    base_state: Any | None = None,
    store: ArtifactStore | None = None,
) -> None:
    from polisyos.foundry.model_state_slots import ModelScalarStateAccessError

    if context is None:
        if getattr(base_state, "model_scalar_state", None) is not None:
            raise ModelScalarStateAccessError("model_scalar_state_patch_context_required")
        return
    if type(context) is not ModelStatePatchContext:
        raise ModelScalarStateAccessError("model_scalar_state_patch_context_required")
    context.validate_inputs(
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        base_state=base_state,
        store=store,
    )


def _require_model_state_base_value(supplied: Any, actual: Any) -> None:
    supplied_array = np.asarray(supplied)
    actual_array = np.asarray(actual)
    if (
        supplied_array.shape != actual_array.shape
        or supplied_array.dtype != actual_array.dtype
        or supplied_array.tobytes() != actual_array.tobytes()
    ):
        raise ValueError("model_scalar_state_patch_base_value_mismatch")


def _model_state_patch_base_values(
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    context: ModelStatePatchContext | None,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for slot_id, records in patch_records.items():
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is not None and slot_spec.state_path is None:
            if context is None:
                raise ValueError("model_scalar_state_patch_context_required")
            actual_base = context.read_slot(slot_id)
            for record in records:
                if "base_value" in record:
                    _require_model_state_base_value(record["base_value"], actual_base)
            values[slot_id] = actual_base
    return values


def _put_tensor(
    store: ArtifactStore, value: Any, *, return_selected_profile: bool = False
) -> ArtifactRef:
    return put_tensor(store, value, return_selected_profile=return_selected_profile)


def _load_tensor(store: ArtifactStore, ref: ArtifactRef | str) -> np.ndarray:
    selector = ArtifactID.model_validate(ref) if isinstance(ref, str) else ref
    data = store.get_bytes(selector)
    return np.load(BytesIO(data), allow_pickle=False)


def merge_patch_records(
    store: ArtifactStore,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    base_values: dict[str, Any] | None = None,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    return_selected_profile: bool = False,
    model_state_context: ModelStatePatchContext | None = None,
) -> list[PatchOp]:
    """Merge patch records into concrete PatchOp list using merge rules."""
    validate_return_selected_profile(return_selected_profile)
    selected_profile = return_selected_profile or model_state_context is not None
    _validate_model_state_patch_context(
        model_state_context,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        store=store,
    )
    engine = MergeEngine(slot_registry, merge_registry)
    records: list[MergeRecord] = []
    effective_base_values = dict(base_values or {})
    model_base_values = _model_state_patch_base_values(
        patch_records, slot_registry=slot_registry, context=model_state_context
    )
    for slot_id, actual_base in model_base_values.items():
        if slot_id in effective_base_values:
            _require_model_state_base_value(effective_base_values[slot_id], actual_base)
        effective_base_values[slot_id] = actual_base
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
        if (
            slot_spec is None
            or slot_spec.state_path == ""
            or (slot_spec.state_path is None and model_state_context is None)
        ):
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")

        op_kind = "add" if rule.kind == MergeRuleKind.SUM else "set"
        payload = merged_value
        if rule.kind == MergeRuleKind.SUM and slot_id in effective_base_values:
            payload = merged_value - effective_base_values[slot_id]
        value_ref = _put_tensor(store, payload, return_selected_profile=selected_profile)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op_kind,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}"],
            )
        )
    return ops
