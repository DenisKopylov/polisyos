from __future__ import annotations

from hashlib import sha256

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.model_state_slots import (
    BoundModelState,
    ModelScalarStateAccessError,
    build_model_scalar_state_layout,
    bind_model_state,
    read_model_scalar_state_slot,
    reattach_model_state_after_execution,
    write_model_scalar_state_slot,
)
from polisyos.ir.kernel import ConstraintRegistry, MechanismTypeRegistry, MergeRuleRegistry
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.units import UnitRef


def _bundle(tmp_path, label: str, slot_id: str) -> tuple[FileSystemCAS, ArtifactRef]:
    store = FileSystemCAS(tmp_path / label)
    slot = SlotSpec(
        slot_id=slot_id,
        scope=SlotScope.GLOBAL,
        kind=SlotKind.STOCK,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id="usd"),
        merge_rule=MergeRuleRef(rule_id="sum"),
        dtype="float32",
        shape=[],
    )
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots={slot_id: slot}),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        return_selected_profile=True,
    )
    return store, bundle.bundle_ref


def _bind(
    state: GlobalState,
    store: FileSystemCAS,
    registry_bundle_ref: ArtifactRef,
    slot_id: str,
) -> BoundModelState:
    return bind_model_state(
        state,
        store=store,
        selected_registry_bundle_ref=registry_bundle_ref,
        slot_ids=(slot_id,),
    )


def _read(
    bound: BoundModelState,
    *,
    slot_id: str,
    registry_ref: ArtifactRef | None = None,
    layout_sha256: str | None = None,
) -> jnp.ndarray:
    return read_model_scalar_state_slot(
        bound,
        slot_id=slot_id,
        selected_registry_bundle_ref=registry_ref or bound.layout.registry_bundle_ref,
        selected_layout_sha256=layout_sha256 or bound.layout.layout_sha256,
    )


def _write(
    bound: BoundModelState,
    *,
    slot_id: str,
    value: object,
) -> BoundModelState:
    return write_model_scalar_state_slot(
        bound,
        slot_id=slot_id,
        value=value,
        selected_registry_bundle_ref=bound.layout.registry_bundle_ref,
        selected_layout_sha256=bound.layout.layout_sha256,
    )


def test_two_unrelated_stock_slots_use_one_generic_accessor_without_name_branches(tmp_path) -> None:
    bundle_a_store, bundle_a = _bundle(tmp_path, "finance-model", "finance.cash_stock")
    bundle_b_store, bundle_b = _bundle(tmp_path, "health-model", "health.staff_stock")
    first_step = GlobalState.empty(n_agents=1, n_firms=1)

    # The same generic sequence handles unrelated model-defined names.
    for layout, slot_id, amount in (
        ((bundle_a_store, bundle_a), "finance.cash_stock", 12.5),
        ((bundle_b_store, bundle_b), "health.staff_stock", 3.0),
    ):
        store, ref = layout
        selected_state = _bind(first_step, store, ref, slot_id)
        selected_state = _write(selected_state, slot_id=slot_id, value=np.float32(amount))
        next_step_state = reattach_model_state_after_execution(
            selected_state,
            selected_state.state,
        )
        observed = _read(next_step_state, slot_id=slot_id)
        assert observed.dtype == jnp.float32
        assert float(observed) == amount


def test_absent_zero_and_present_zero_are_distinct(tmp_path) -> None:
    store, bundle = _bundle(tmp_path, "model", "finance.cash_stock")
    selected_state = _bind(GlobalState.empty(n_agents=1, n_firms=1), store, bundle, "finance.cash_stock")

    with pytest.raises(ModelScalarStateAccessError, match="slot_absent"):
        _read(selected_state, slot_id="finance.cash_stock")

    selected_state = _write(selected_state, slot_id="finance.cash_stock", value=np.float32(0.0))
    assert float(_read(selected_state, slot_id="finance.cash_stock")) == 0.0
    assert bool(selected_state.state.model_scalar_state.present[0])


def test_layout_and_registry_profile_are_bound_across_same_shape_state(tmp_path) -> None:
    store_a, bundle_a = _bundle(tmp_path, "model-a", "finance.cash_stock")
    _store_b, bundle_b = _bundle(tmp_path, "model-b", "health.staff_stock")
    selected_state = _bind(
        GlobalState.empty(n_agents=1, n_firms=1), store_a, bundle_a, "finance.cash_stock"
    )
    layout_b = build_model_scalar_state_layout(
        store=_store_b,
        registry_bundle_ref=bundle_b,
        slot_ids=("health.staff_stock",),
    )
    selected_state = _write(selected_state, slot_id="finance.cash_stock", value=np.float32(5.0))

    with pytest.raises(ModelScalarStateAccessError, match="registry_bundle_mismatch"):
        _read(
            selected_state,
            slot_id="finance.cash_stock",
            registry_ref=bundle_b,
        )
    with pytest.raises(ModelScalarStateAccessError, match="layout_mismatch"):
        _read(
            selected_state,
            slot_id="finance.cash_stock",
            layout_sha256=layout_b.layout_sha256,
        )


def test_unknown_slot_dtype_nonfinite_and_nonempty_rebinding_fail_closed(tmp_path) -> None:
    store, bundle = _bundle(tmp_path, "model", "finance.cash_stock")
    selected_state = _bind(GlobalState.empty(n_agents=1, n_firms=1), store, bundle, "finance.cash_stock")

    with pytest.raises(ModelScalarStateAccessError, match="slot_not_in_selected_layout"):
        _read(selected_state, slot_id="health.staff_stock")
    with pytest.raises(ModelScalarStateAccessError, match="write_nonfinite"):
        _write(selected_state, slot_id="finance.cash_stock", value=np.float32(np.inf))
    with pytest.raises(ModelScalarStateAccessError, match="initial_binding_requires_empty_state"):
        _bind(selected_state.state, store, bundle, "finance.cash_stock")
