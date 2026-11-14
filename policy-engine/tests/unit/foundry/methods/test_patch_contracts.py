from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.model_state_layout import (
    ModelScalarStateLayout,
    ModelScalarStateSlot,
    model_scalar_state_layout_digest,
)
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot
from polisyos.foundry.execute.patch_vm import ModelStatePatchContext
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodPatchTargetContract,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.merge_engine import MergeEngine, MergeRecord
from polisyos.foundry.methods.lifecycle.compat import SignatureDiff
from polisyos.foundry.methods.patch_contracts import validate_method_patch_targets
from polisyos.foundry.methods.selection.cache import (
    _complete_signature_payload,
    _signature_from_payload,
)
from polisyos.foundry.model_state_slots import bind_model_state, write_model_scalar_state_slot
from polisyos.ir.kernel import ConstraintRegistry, MechanismTypeRegistry
from polisyos.ir.kernel.merge_rules import MergeRuleKind, MergeRuleRegistry, MergeRuleSpec
from polisyos.ir.kernel.slots import (
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotValueType,
)
from polisyos.ir.kernel.slots import (
    SlotSpec as RegistrySlotSpec,
)
from polisyos.ir.kernel.units import MoneyUnit, UnitRef, UnitsRegistry


def _signature() -> MethodSignature:
    return MethodSignature(
        name="accumulate",
        namespace="tests.contract",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("period_flow", SlotType.SCALAR, Unit("currency", "USD"))}),
        output_slots=frozenset(),
        parameters=(ParameterSpec("target_slot", None, is_static=True),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
        patch_targets=(MethodPatchTargetContract("target_slot", "period_flow"),),
    )


def _registry(
    tmp_path,
    *,
    variant: str = "valid",
    source_slot_id: str = "period_flow",
    model_stock: bool = False,
    registry_note: str | None = None,
):
    source = RegistrySlotSpec(
        slot_id=source_slot_id,
        scope=SlotScope.GLOBAL,
        kind=SlotKind.FLOW,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id="selected_currency"),
        merge_rule={"rule_id": "selected_rule"},
    )
    target = RegistrySlotSpec(
        slot_id="accumulated_net",
        scope=SlotScope.GLOBAL,
        kind=SlotKind.STOCK,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id="selected_currency"),
        merge_rule={"rule_id": "selected_rule"},
        state_path=None if model_stock else "government.balance",
        dtype="float32" if model_stock else None,
        shape=[] if model_stock else None,
    )
    for name, slot, field, value in (
        ("target_flow", target, "kind", SlotKind.FLOW),
        ("target_vector", target, "scope", SlotScope.PER_AGENT),
        ("target_int", target, "value_type", SlotValueType.INT),
        ("target_no_path", target, "state_path", None),
        ("target_shape", target, "shape", ["N"]),
        ("source_stock", source, "kind", SlotKind.STOCK),
        ("source_vector", source, "scope", SlotScope.PER_AGENT),
        ("source_int", source, "value_type", SlotValueType.INT),
        ("source_shape", source, "shape", ["N"]),
        ("unit_graft", target, "unit", UnitRef(unit_id="other_currency")),
        ("no_unit", source, "unit", None),
    ):
        if variant == name:
            payload = slot.model_dump(mode="python")
            payload[field] = value
            replacement = RegistrySlotSpec.model_validate(payload)
            if slot is source:
                source = replacement
            else:
                target = replacement
    slots = {source.slot_id: source, target.slot_id: target}
    if variant == "missing_source":
        del slots[source.slot_id]
    if variant == "missing_target":
        del slots[target.slot_id]
    rule = MergeRuleSpec(
        rule_id="selected_rule",
        kind=MergeRuleKind.OVERRIDE if variant == "wrong_rule" else MergeRuleKind.SUM,
    )
    rules = {} if variant == "missing_rule" else {rule.rule_id: rule}
    units = UnitsRegistry(
        units={
            "selected_currency": MoneyUnit(currency="EUR" if variant == "renamed_unit" else "USD"),
            "other_currency": MoneyUnit(currency="USD"),
        }
    )
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots=slots, notes=[registry_note] if registry_note else []),
        merge_registry=MergeRuleRegistry(rules=rules),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        units_registry=None if variant == "missing_units" else units,
        return_selected_profile=True,
    )
    return load_registry_bundle_content(store, bundle.bundle_ref)


def test_selected_registry_controls_patch_contract_and_real_sum_merge(tmp_path) -> None:
    registry = _registry(tmp_path)
    operations = validate_method_patch_targets(
        _signature(),
        params={"target_slot": "accumulated_net"},
        declared_outputs=["accumulated_net"],
        registry=registry,
    )
    assert dict(operations) == {"accumulated_net": "add"}
    with pytest.raises(TypeError):
        operations["foreign"] = "add"
    engine = MergeEngine(registry.slot_registry, registry.merge_registry)
    for flow, expected in ((-6_000_000_000.0, -5_000_000_000.0), (0.0, 1_000_000_000.0)):
        result = engine.merge_records(
            [MergeRecord(node_id="method", slot_id="accumulated_net", delta=flow)],
            {"accumulated_net": 1_000_000_000.0},
        )
        result.raise_if_conflicts()
        assert result.merged_values["accumulated_net"] == expected


@pytest.mark.parametrize(
    ("variant", "code"),
    [
        ("target_flow", "method_patch_target_profile_mismatch"),
        ("target_vector", "method_patch_target_profile_mismatch"),
        ("target_int", "method_patch_target_profile_mismatch"),
        ("target_no_path", "method_patch_target_profile_mismatch"),
        ("target_shape", "method_patch_target_profile_mismatch"),
        ("source_stock", "method_patch_source_profile_mismatch"),
        ("source_vector", "method_input_source_profile_mismatch"),
        ("source_int", "method_input_source_profile_mismatch"),
        ("source_shape", "method_input_source_profile_mismatch"),
        ("unit_graft", "method_patch_source_target_unit_mismatch"),
        ("no_unit", "method_input_abi_unit_mismatch"),
        ("missing_source", "method_input_source_unregistered"),
        ("missing_target", "method_patch_target_unregistered"),
        ("wrong_rule", "method_patch_target_merge_rule_mismatch"),
        ("missing_rule", "method_patch_target_merge_rule_mismatch"),
        ("renamed_unit", "method_input_abi_unit_mismatch"),
        ("missing_units", "method_input_abi_unit_mismatch"),
    ],
)
def test_patch_contract_refuses_incompatible_canonical_registry(tmp_path, variant, code) -> None:
    with pytest.raises(ValueError, match=f"^{code}$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=["accumulated_net"],
            registry=_registry(tmp_path, variant=variant),
        )


@pytest.mark.parametrize("target", [None, "", " accumulated_net", 2])
def test_patch_contract_requires_exact_static_target_parameter(tmp_path, target) -> None:
    with pytest.raises(ValueError, match="^method_patch_target_parameter_unbound$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": target},
            declared_outputs=["accumulated_net"],
            registry=_registry(tmp_path),
        )


@pytest.mark.parametrize("outputs", [[], ["foreign"], ["accumulated_net", "foreign"]])
def test_patch_contract_does_not_allow_missing_or_extra_declared_write(tmp_path, outputs) -> None:
    with pytest.raises(ValueError, match="^method_patch_declared_outputs_mismatch$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=outputs,
            registry=_registry(tmp_path),
        )


def test_patch_contract_changes_abi_and_survives_semantic_cache_round_trip() -> None:
    signature = _signature()
    historical = replace(signature, patch_targets=())
    assert "patch_targets" not in historical._stable_dict()
    assert historical.abi_digest() != signature.abi_digest()
    assert [change.kind for change in SignatureDiff().diff(historical, signature)] == [
        "patch_target_contract_changed"
    ]
    payload = _complete_signature_payload(signature)
    restored = _signature_from_payload(payload)
    assert restored.patch_targets == signature.patch_targets
    assert restored.abi_digest() == signature.abi_digest()
    changed = {**payload, "patch_targets": []}
    assert _signature_from_payload(changed).abi_digest() != signature.abi_digest()


def test_patch_contract_requires_declared_static_parameter_and_scalar_source() -> None:
    signature = _signature()
    with pytest.raises(ValueError, match="^method_patch_target_static_parameter_missing$"):
        replace(signature, parameters=(ParameterSpec("target_slot", None, is_static=False),))
    with pytest.raises(ValueError, match="^method_patch_source_scalar_input_missing$"):
        replace(signature, input_slots=frozenset())
    with pytest.raises(ValueError, match="^method_patch_target_profile_unsupported$"):
        MethodPatchTargetContract("target_slot", "period_flow", operation="set")


def test_legacy_method_without_patch_contract_keeps_legacy_gate(tmp_path) -> None:
    assert not validate_method_patch_targets(
        replace(_signature(), patch_targets=()),
        params={},
        declared_outputs=[],
        registry=_registry(tmp_path),
    )


def test_patch_contract_resolves_explicit_abi_source_alias_from_selected_registry(tmp_path) -> None:
    registry = _registry(tmp_path, source_slot_id="model.selected_flow")
    operations = validate_method_patch_targets(
        _signature(),
        params={"target_slot": "accumulated_net"},
        declared_outputs=["accumulated_net"],
        registry=registry,
        input_slot_sources={"period_flow": "model.selected_flow"},
    )
    assert dict(operations) == {"accumulated_net": "add"}
    with pytest.raises(ValueError, match="^method_input_source_unregistered$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=["accumulated_net"],
            registry=registry,
        )


@pytest.mark.parametrize(
    "sources",
    [
        {},
        {"foreign": "model.selected_flow"},
        {"period_flow": ""},
        {"period_flow": " model.selected_flow"},
        {"period_flow": 3},
        {"period_flow": "model.selected_flow", "foreign": "model.selected_flow"},
    ],
)
def test_patch_contract_explicit_aliases_never_fall_back_to_local_names(tmp_path, sources) -> None:
    with pytest.raises(ValueError, match="^method_patch_input_slot_sources_mismatch$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=["accumulated_net"],
            registry=_registry(tmp_path),
            input_slot_sources=sources,
        )


def test_patch_contract_checks_kind_of_the_mapped_source_not_the_local_abi_name(tmp_path) -> None:
    with pytest.raises(ValueError, match="^method_patch_source_profile_mismatch$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=["accumulated_net"],
            registry=_registry(tmp_path),
            input_slot_sources={"period_flow": "accumulated_net"},
        )


def _model_stock_context(tmp_path, *, registry_note: str | None = None):
    registry = _registry(tmp_path, model_stock=True, registry_note=registry_note)
    store = FileSystemCAS(tmp_path / "cas")
    bound = bind_model_state(
        GlobalState.empty(n_agents=1, n_firms=1),
        store=store,
        selected_registry_bundle_ref=registry.bundle_ref,
        slot_ids=("accumulated_net",),
    )
    bound = write_model_scalar_state_slot(
        bound,
        slot_id="accumulated_net",
        value=np.float32(10.0),
        selected_registry_bundle_ref=registry.bundle_ref,
        selected_layout_sha256=bound.layout.layout_sha256,
    )
    base_ref = put_state_snapshot(store, state=bound, return_selected_profile=True)
    return ModelStatePatchContext(
        store=store, base_ref=base_ref, registry_bundle_ref=registry.bundle_ref
    )


def _validate_model_target(context, *, layout=None, values=None, registry=None):
    return validate_method_patch_targets(
        _signature(),
        params={"target_slot": "accumulated_net"},
        declared_outputs=["accumulated_net"],
        registry=registry or context.registry,
        model_state_layout=layout if layout is not None else context.bound_state.layout,
        model_state_target_values=(
            values
            if values is not None
            else {"accumulated_net": np.asarray(context.read_slot("accumulated_net"))}
        ),
    )


def test_pathless_patch_target_requires_actual_selected_layout_and_present_value(tmp_path) -> None:
    context = _model_stock_context(tmp_path)
    assert dict(_validate_model_target(context)) == {"accumulated_net": "add"}
    with pytest.raises(ValueError, match="^method_patch_target_profile_mismatch$"):
        validate_method_patch_targets(
            _signature(),
            params={"target_slot": "accumulated_net"},
            declared_outputs=["accumulated_net"],
            registry=context.registry,
        )
    with pytest.raises(ValueError, match="^method_patch_target_state_absent$"):
        _validate_model_target(context, values={})


def test_pathless_patch_target_refuses_foreign_same_value_layout(tmp_path) -> None:
    first = _model_stock_context(tmp_path / "first")
    foreign = _model_stock_context(tmp_path / "foreign", registry_note="foreign selection")
    assert float(first.read_slot("accumulated_net")) == float(foreign.read_slot("accumulated_net"))
    with pytest.raises(ValueError, match="^method_patch_target_state_registry_mismatch$"):
        _validate_model_target(first, layout=foreign.bound_state.layout)


@pytest.mark.parametrize(
    "bad_value", [np.float64(10.0), np.array([10.0], dtype=np.float32), np.float32(np.nan)]
)
def test_pathless_patch_target_refuses_noncanonical_present_values(tmp_path, bad_value) -> None:
    context = _model_stock_context(tmp_path)
    with pytest.raises(ValueError, match="^method_patch_target_state_value_invalid$"):
        _validate_model_target(context, values={"accumulated_net": bad_value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dtype", "float64"),
        ("unit", {"unit_id": "other_currency"}),
        ("state_path", "government_balance"),
    ],
)
def test_pathless_patch_target_reconciles_actual_registered_slot_descriptor(
    tmp_path, field, value
) -> None:
    context = _model_stock_context(tmp_path)
    target = context.registry.slot_registry.slots["accumulated_net"]
    substituted = RegistrySlotSpec.model_validate(
        {**target.model_dump(mode="python"), field: value}
    )
    registry = replace(
        context.registry,
        slot_registry=SlotRegistry(
            slots={**context.registry.slot_registry.slots, "accumulated_net": substituted}
        ),
    )
    with pytest.raises(ValueError, match="^method_patch_target_state_layout_mismatch$"):
        _validate_model_target(context, registry=registry)


def test_pathless_patch_target_refuses_same_shape_wrong_slot_or_spec_digest(tmp_path) -> None:
    context = _model_stock_context(tmp_path)
    original = context.bound_state.layout
    for descriptor in (
        ModelScalarStateSlot(
            slot_id="other_stock", index=0, slot_spec_sha256=original.slots[0].slot_spec_sha256
        ),
        ModelScalarStateSlot(
            slot_id="accumulated_net", index=0, slot_spec_sha256=f"sha256:{'0' * 64}"
        ),
    ):
        layout = ModelScalarStateLayout(
            registry_bundle_ref=original.registry_bundle_ref,
            slots=(descriptor,),
            layout_sha256=model_scalar_state_layout_digest(
                registry_bundle_ref=original.registry_bundle_ref, slots=(descriptor,)
            ),
        )
        with pytest.raises(ValueError, match="^method_patch_target_state_layout_mismatch$"):
            _validate_model_target(context, layout=layout)
