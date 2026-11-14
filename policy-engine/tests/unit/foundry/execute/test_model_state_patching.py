from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateDelta
from polisyos.core.registry import build_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.ops import apply_ops_to_state
from polisyos.foundry.execute._internal.patching import (
    apply_patch_map,
    apply_patch_records,
    apply_state_delta,
    apply_state_delta_and_snapshot,
)
from polisyos.foundry.execute._internal.snapshots import (
    load_bound_model_state_snapshot,
    put_state_snapshot,
)
from polisyos.foundry.execute.patch_vm import ModelStatePatchContext, merge_patch_records
from polisyos.foundry.model_state_slots import (
    bind_model_state,
    read_model_scalar_state_slot,
    write_model_scalar_state_slot,
)
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    ConstraintRegistry,
    MechanismTypeRegistry,
    SlotRegistry,
)
from polisyos.ir.kernel.slots import SlotKind, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.units import UnitRef


def _context(tmp_path, *, slot_id: str = "model.accumulated_value", present: bool = True):
    store = FileSystemCAS(tmp_path)
    slot = SlotSpec(
        slot_id=slot_id,
        scope=SlotScope.GLOBAL,
        kind=SlotKind.STOCK,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id="usd"),
        merge_rule={"rule_id": "sum"},
        dtype="float32",
        shape=[],
    )
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(
            slots={
                slot_id: slot,
                "government.balance": DEFAULT_SLOT_REGISTRY.slots["government.balance"],
            }
        ),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        return_selected_profile=True,
    )
    bound = bind_model_state(
        GlobalState.empty(n_agents=1, n_firms=1),
        store=store,
        selected_registry_bundle_ref=bundle.bundle_ref,
        slot_ids=(slot_id,),
    )
    if present:
        bound = write_model_scalar_state_slot(
            bound,
            slot_id=slot_id,
            value=np.float32(10.0),
            selected_registry_bundle_ref=bundle.bundle_ref,
            selected_layout_sha256=bound.layout.layout_sha256,
        )
    base_ref = put_state_snapshot(store, state=bound, return_selected_profile=True)
    context = ModelStatePatchContext(
        store=store, base_ref=base_ref, registry_bundle_ref=bundle.bundle_ref
    )
    return context


def _read(context, state, slot_id: str) -> float:
    current = context.with_state(state)
    return float(
        read_model_scalar_state_slot(
            current.bound_state,
            slot_id=slot_id,
            selected_registry_bundle_ref=current.registry_bundle_ref,
            selected_layout_sha256=current.bound_state.layout.layout_sha256,
        )
    )


def _delta(context, ops, *, base_ref=None):
    return context.store.put_json(
        StateDelta(base_ref=base_ref or context.base_ref, ops=ops),
        PutOptions(
            kind=StateDelta.ARTIFACT_KIND,
            media_type=StateDelta.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=StateDelta.ARTIFACT_SCHEMA_NAME, version=StateDelta.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[input_ref_from_artifact_ref(context.base_ref, role="base_state")]
            + [input_ref_from_artifact_ref(op.value_ref, role="patch_value") for op in ops],
        ),
        return_selected_profile=True,
    )


@pytest.mark.parametrize("slot_id", ["health.staff_stock", "model.accumulated_value"])
def test_generic_model_stock_patch_uses_existing_merge_ops_delta_and_snapshot(
    tmp_path, slot_id
) -> None:
    context = _context(tmp_path, slot_id=slot_id)
    records = {slot_id: [{"node_id": "writer", "delta": np.float32(2.0)}]}
    kwargs = {
        "slot_registry": context.registry.slot_registry,
        "merge_registry": context.registry.merge_registry,
        "model_state_context": context,
    }
    expected = apply_patch_records(context.bound_state.state, records, **kwargs)
    assert _read(context, expected, slot_id) == 12.0
    mapped = apply_patch_map(context.bound_state.state, records, **kwargs)
    assert _read(context, mapped, slot_id) == 12.0
    ops = merge_patch_records(context.store, records, return_selected_profile=True, **kwargs)
    assert len(ops) == 1 and ops[0].op == "add"
    applied = apply_ops_to_state(
        context.store, base_state=context.bound_state.state, ops=ops, **kwargs
    )
    assert _read(context, applied, slot_id) == 12.0
    delta_ref = _delta(context, ops)
    replayed = apply_state_delta(
        context.store,
        base_state=context.bound_state.state,
        state_delta_ref=delta_ref,
        **kwargs,
    )
    assert _read(context, replayed, slot_id) == 12.0
    with pytest.raises(ValueError, match="model_scalar_state_patch_opening_state_required"):
        apply_state_delta(
            context.store,
            base_state=replayed,
            state_delta_ref=delta_ref,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context.with_state(replayed),
        )
    saved, artifacts = apply_state_delta_and_snapshot(
        context.store,
        base_state=context.bound_state.state,
        state_delta_ref=delta_ref,
        **kwargs,
    )
    assert _read(context, saved, slot_id) == 12.0
    fresh = load_bound_model_state_snapshot(
        FileSystemCAS(tmp_path), snapshot_ref=artifacts.state_snapshot_ref
    )
    assert fresh.layout == context.bound_state.layout
    assert (
        float(
            read_model_scalar_state_slot(
                fresh,
                slot_id=slot_id,
                selected_registry_bundle_ref=context.registry_bundle_ref,
                selected_layout_sha256=fresh.layout.layout_sha256,
            )
        )
        == 12.0
    )


def test_model_stock_patch_cannot_replace_absent_with_implicit_zero(tmp_path) -> None:
    context = _context(tmp_path, present=False)
    records = {"model.accumulated_value": [{"node_id": "writer", "delta": np.float32(0.0)}]}
    for operation in (
        lambda: merge_patch_records(
            context.store,
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        ),
        lambda: apply_patch_records(
            context.bound_state.state,
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        ),
    ):
        with pytest.raises(ValueError, match="model_scalar_state_slot_absent"):
            operation()


def test_model_stock_patch_requires_context_and_its_exact_current_state(tmp_path) -> None:
    context = _context(tmp_path)
    records = {"model.accumulated_value": [{"delta": np.float32(2.0)}]}
    with pytest.raises(ValueError, match="model_scalar_state_patch_context_required"):
        apply_patch_records(
            context.bound_state.state,
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
        )
    with pytest.raises(ValueError, match="model_scalar_state_patch_base_state_mismatch"):
        apply_patch_records(
            context.bound_state.state.replace(),
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        )


def test_model_stock_patch_refuses_foreign_registry_and_mutated_merge_rule(tmp_path) -> None:
    context = _context(tmp_path / "a")
    foreign = _context(tmp_path / "b", slot_id="model.foreign_stock")
    with pytest.raises(ValueError, match="model_scalar_state_patch_registry_mismatch"):
        ModelStatePatchContext(
            store=context.store,
            base_ref=context.base_ref,
            registry_bundle_ref=foreign.registry_bundle_ref,
        )
    changed = deepcopy(context.registry.merge_registry)
    changed.rules.pop("sum")
    with pytest.raises(ValueError, match="model_scalar_state_patch_registry_content_mismatch"):
        merge_patch_records(
            context.store,
            {"model.accumulated_value": [{"delta": np.float32(2.0)}]},
            slot_registry=context.registry.slot_registry,
            merge_registry=changed,
            model_state_context=context,
        )


def test_model_stock_delta_replay_requires_exact_original_snapshot(tmp_path) -> None:
    context = _context(tmp_path / "a")
    foreign = _context(tmp_path / "b", slot_id="model.foreign_stock")
    ops = merge_patch_records(
        context.store,
        {"model.accumulated_value": [{"delta": np.float32(2.0)}]},
        slot_registry=context.registry.slot_registry,
        merge_registry=context.registry.merge_registry,
        model_state_context=context,
        return_selected_profile=True,
    )
    delta_ref = _delta(context, ops, base_ref=foreign.base_ref)
    with pytest.raises(ValueError, match="model_scalar_state_patch_base_ref_mismatch"):
        apply_state_delta(
            context.store,
            base_state=context.bound_state.state,
            state_delta_ref=delta_ref,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        )


def test_model_stock_patch_refuses_a_claimed_base_instead_of_the_selected_base(tmp_path) -> None:
    context = _context(tmp_path)
    records = {
        "model.accumulated_value": [{"new_value": np.float32(12.0), "base_value": np.float32(0.0)}]
    }
    for operation in (
        lambda: merge_patch_records(
            context.store,
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        ),
        lambda: apply_patch_records(
            context.bound_state.state,
            records,
            slot_registry=context.registry.slot_registry,
            merge_registry=context.registry.merge_registry,
            model_state_context=context,
        ),
    ):
        with pytest.raises(ValueError, match="model_scalar_state_patch_base_value_mismatch"):
            operation()
