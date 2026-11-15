"""Exact discrete initial facts remain distinct from semantic float inputs."""

from __future__ import annotations

import stat
from dataclasses import replace
from decimal import Decimal

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import FoundryInputBindings, FoundryInputBindingsRef
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import (
    _materialize_explicit_initial_binding_tensor,
    _materialize_selected_binding_tensor,
    _SelectedBindingTensorPolicy,
    load_input_bindings,
    reconcile_explicit_initial_binding_slots,
)
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers.selected_method_input import prepare_selected_method_input_case


@pytest.fixture(scope="module")
def initial_case(tmp_path_factory):
    case, _metadata = prepare_selected_method_input_case(
        tmp_path_factory.mktemp("explicit-initial"),
        method_class=PeriodFlowToStock,
        income_values=(4, 4),
        opening_balance_usd=4096,
        explicit_initial_slot_values={
            "agents.is_employed": [False, True],
            "agents.employer_id": [-1, 0],
        },
    )
    yield case
    case.close()


def test_actual_discrete_initial_producer_reopens_exact_typed_values(initial_case):
    case = initial_case
    state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
    assert np.asarray(state.agents.is_employed).dtype == np.dtype("bool")
    assert np.asarray(state.agents.employer_id).dtype == np.dtype("int32")
    np.testing.assert_array_equal(state.agents.is_employed, [False, True])
    np.testing.assert_array_equal(state.agents.employer_id, [-1, 0])
    supplied = reconcile_explicit_initial_binding_slots(
        case.store,
        input_bindings_ref=case.input_bindings_ref,
        expected_state_paths={
            "agents.is_employed": "agents.is_employed",
            "agents.employer_id": "agents.employer_id",
            "agents.income": "agents.income",
            "government.balance": "government_balance",
        },
    )
    assert set(supplied) == {
        "agents.is_employed",
        "agents.employer_id",
        "agents.income",
        "government.balance",
    }


@pytest.mark.parametrize(
    ("slot_id", "value", "mutation", "reason"),
    [
        ("agents.is_employed", [0, 1], None, "source_not_boolean"),
        ("agents.employer_id", [False, True], None, "source_not_integer"),
        ("agents.employer_id", [-1.0, 0.0], None, "source_not_integer"),
        ("agents.employer_id", [2**31, 0], None, "integer_out_of_range"),
        ("agents.employer_id", [-(2**31) - 1, 0], None, "integer_out_of_range"),
        ("agents.employer_id", -1, None, "shape_mismatch"),
        ("agents.employer_id", [[-1], [0]], None, "shape_mismatch"),
        ("agents.employer_id", [-1, None], None, "source_not_integer"),
        ("agents.is_employed", [False, True], "target_dtype", "target_encoding_mismatch"),
        ("agents.employer_id", [-1, 0], "precision", "target_encoding_mismatch"),
        ("agents.employer_id", [-1, 0], "scale", "target_encoding_mismatch"),
        ("agents.employer_id", [-1, 0], "transform", "transform_mismatch"),
    ],
)
def test_discrete_replay_refuses_coercion_overflow_and_shape_changes(
    initial_case, slot_id, value, mutation, reason
):
    case = initial_case
    registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
    bindings = load_input_bindings(case.store, case.input_bindings_ref)
    slot = registry.slot_registry.slots[slot_id]
    rule = next(rule for rule in bindings.rules if rule.target_slot_id == slot_id)
    target = (
        np.asarray([False, True])
        if slot_id == "agents.is_employed"
        else np.asarray([-1, 0], dtype=np.int32)
    )
    policy = _SelectedBindingTensorPolicy(target.shape, target.dtype.name, Decimal(0))
    if mutation == "target_dtype":
        target = target.astype(np.int32)
    elif mutation == "precision":
        policy = replace(policy, max_absolute_error=Decimal(1))
    elif mutation == "scale":
        policy = replace(policy, fixed_unit_multiplier=Decimal(2))
    elif mutation == "transform":
        rule = type(rule).model_validate(
            rule.model_dump(mode="python") | {"transforms": [{"op": "to_int"}]}
        )
    with pytest.raises(ValueError, match=f"^explicit_initial_binding_{reason}$"):
        _materialize_explicit_initial_binding_tensor(
            value, rule=rule, slot=slot, target_tensor=target, policy=policy
        )
    # The independently selected semantic decimal/NPY primitive stays float-only.
    with pytest.raises(ValueError, match="^semantic_binding_target_encoding_mismatch$"):
        _materialize_selected_binding_tensor(
            [False, True] if slot_id == "agents.is_employed" else [-1, 0],
            rule=rule,
            slot=slot,
            target_tensor=target,
            policy=policy,
        )


def test_discrete_initial_replay_refuses_changed_persisted_target_and_missing_source(initial_case):
    case = initial_case
    original = load_input_bindings(case.store, case.input_bindings_ref)
    state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
    changed = state.replace(
        agents=state.agents.replace(is_employed=jnp.asarray([True, True], dtype=jnp.bool_))
    )
    changed_ref = put_state_snapshot(
        case.store,
        state=changed,
        inputs=list(case.store.get_manifest(case.bound_state_snapshot_ref).inputs),
        return_selected_profile=True,
    )
    changed_bindings = original.model_copy(update={"bound_state_snapshot_ref": changed_ref})
    changed_binding_ref = case.store.put_json(
        changed_bindings,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.0"),
            inputs=[
                input_ref_from_artifact_ref(changed_ref, role=edge.role)
                if edge.role == "artifact.bound_state_snapshot_ref"
                else edge
                for edge in case.store.get_manifest(case.input_bindings_ref).inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        ValueError, match="^explicit_initial_binding_state_mismatch:agents.is_employed$"
    ):
        reconcile_explicit_initial_binding_slots(
            case.store,
            input_bindings_ref=FoundryInputBindingsRef.model_validate(
                changed_binding_ref.model_dump(mode="python")
            ),
            expected_state_paths={"agents.is_employed": "agents.is_employed"},
        )

    blob, _ = case.store._paths(case.source_ref.artifact_id)
    content, mode = blob.read_bytes(), stat.S_IMODE(blob.stat().st_mode)
    blob.unlink()
    try:
        with pytest.raises(
            ValueError,
            match=r"^DataSnapshot selected nested reference profile does not resolve: data_ref$",
        ) as missing:
            reconcile_explicit_initial_binding_slots(
                case.store,
                input_bindings_ref=case.input_bindings_ref,
                expected_state_paths={"agents.is_employed": "agents.is_employed"},
            )
        assert isinstance(missing.value.__cause__, FileNotFoundError)
        assert str(case.source_ref.artifact_id).removeprefix("sha256:") in str(
            missing.value.__cause__
        )
    finally:
        blob.write_bytes(content)
        blob.chmod(mode)
    assert reconcile_explicit_initial_binding_slots(
        case.store,
        input_bindings_ref=case.input_bindings_ref,
        expected_state_paths={"agents.is_employed": "agents.is_employed"},
    ) == ("agents.is_employed",)
