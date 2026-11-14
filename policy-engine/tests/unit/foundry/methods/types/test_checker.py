from __future__ import annotations

from dataclasses import replace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.types import validate_registered_method_input
from polisyos.ir.kernel import ConstraintRegistry, MechanismTypeRegistry
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import (
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotValueType,
)
from polisyos.ir.kernel.slots import (
    SlotSpec as RegistrySlotSpec,
)
from polisyos.ir.kernel.units import GenericUnit, MoneyUnit, UnitRef, UnitsRegistry


def _read_only_signature(*, unit: Unit | None = None, vector: bool = False) -> MethodSignature:
    return MethodSignature(
        name="read",
        namespace="tests.input_contract",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "local_amount",
                    SlotType.VECTOR if vector else SlotType.SCALAR,
                    unit or Unit("currency", "USD"),
                    shape=(1,) if vector else (),
                )
            }
        ),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _selected_registry(tmp_path, *, variant: str = "valid"):
    unit = MoneyUnit(currency="EUR" if variant == "other_currency" else "USD")
    if variant == "label_only":
        unit = GenericUnit(label="USD")
    slot = RegistrySlotSpec(
        slot_id="selected.amount",
        scope=SlotScope.PER_AGENT if variant == "vector_scope" else SlotScope.GLOBAL,
        kind=SlotKind.FLOW if variant == "flow" else SlotKind.STOCK,
        value_type=SlotValueType.INT if variant == "integer" else SlotValueType.DECIMAL,
        unit=None if variant == "no_unit" else UnitRef(unit_id="model_unit"),
        merge_rule={"rule_id": "sum"},
        shape=["N"] if variant == "vector_shape" else None,
    )
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots={slot.slot_id: slot}),
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        units_registry=(
            None if variant == "no_units" else UnitsRegistry(units={"model_unit": unit})
        ),
        return_selected_profile=True,
    )
    return load_registry_bundle_content(store, bundle.bundle_ref)


@pytest.mark.parametrize("variant", ["valid", "flow"])
def test_read_only_method_accepts_registered_money_without_patch_targets(tmp_path, variant) -> None:
    signature = _read_only_signature()
    assert signature.patch_targets == ()
    registry = _selected_registry(tmp_path, variant=variant)
    source = validate_registered_method_input(
        signature,
        input_slot_id="local_amount",
        registered_slot_id="selected.amount",
        registry=registry,
    )
    assert source is registry.slot_registry.slots["selected.amount"]
    assert source.unit == UnitRef(unit_id="model_unit")


@pytest.mark.parametrize(
    ("variant", "code"),
    [
        ("vector_scope", "method_input_source_profile_mismatch"),
        ("vector_shape", "method_input_source_profile_mismatch"),
        ("integer", "method_input_source_profile_mismatch"),
        ("other_currency", "method_input_abi_unit_mismatch"),
        ("label_only", "method_input_abi_unit_mismatch"),
        ("no_unit", "method_input_abi_unit_mismatch"),
        ("no_units", "method_input_abi_unit_mismatch"),
    ],
)
def test_registered_input_does_not_infer_scalar_or_currency_from_labels(
    tmp_path, variant, code
) -> None:
    with pytest.raises(ValueError, match=f"^{code}$"):
        validate_registered_method_input(
            _read_only_signature(),
            input_slot_id="local_amount",
            registered_slot_id="selected.amount",
            registry=_selected_registry(tmp_path, variant=variant),
        )


@pytest.mark.parametrize("unit", [Unit("currency", "EUR"), Unit("currency", "USD", scale=0.01)])
def test_registered_input_requires_exact_abi_currency_and_scale(tmp_path, unit) -> None:
    with pytest.raises(ValueError, match="^method_input_abi_unit_mismatch$"):
        validate_registered_method_input(
            _read_only_signature(unit=unit),
            input_slot_id="local_amount",
            registered_slot_id="selected.amount",
            registry=_selected_registry(tmp_path),
        )


def test_registered_input_refuses_missing_local_or_global_identity_and_vector_abi(tmp_path) -> None:
    registry = _selected_registry(tmp_path)
    signature = _read_only_signature()
    for selected_signature, local_id in (
        (signature, "foreign"),
        (_read_only_signature(vector=True), "local_amount"),
        (replace(signature, input_slots=frozenset()), "local_amount"),
    ):
        with pytest.raises(ValueError, match="^method_input_abi_scalar_slot_unavailable$"):
            validate_registered_method_input(
                selected_signature,
                input_slot_id=local_id,
                registered_slot_id="selected.amount",
                registry=registry,
            )
    with pytest.raises(ValueError, match="^method_input_source_unregistered$"):
        validate_registered_method_input(
            signature,
            input_slot_id="local_amount",
            registered_slot_id="foreign.amount",
            registry=registry,
        )
