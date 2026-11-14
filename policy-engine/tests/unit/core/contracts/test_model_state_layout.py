from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.model_state_layout import (
    ModelScalarStateLayout,
    model_scalar_state_slot_spec_digest,
)
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.core.registry.loader import load_registry_bundle_content
from polisyos.foundry.model_state_slots import (
    ModelScalarStateAccessError,
    build_model_scalar_state_layout,
)
from polisyos.ir.kernel import ConstraintRegistry, MechanismTypeRegistry, MergeRuleRegistry
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.units import UnitRef


def _slot(slot_id: str, *, unit_id: str = "usd", shape: list[str] | None = None) -> SlotSpec:
    return SlotSpec(
        slot_id=slot_id,
        scope=SlotScope.GLOBAL,
        kind=SlotKind.STOCK,
        value_type=SlotValueType.DECIMAL,
        unit=UnitRef(unit_id=unit_id),
        merge_rule=MergeRuleRef(rule_id="sum"),
        dtype="float32",
        shape=[] if shape is None else shape,
    )


def _bundle(tmp_path, label: str, slots: tuple[SlotSpec, ...]):
    store = FileSystemCAS(tmp_path / label)
    bundle = build_registry_bundle(
        store,
        slot_registry=SlotRegistry(slots={slot.slot_id: slot for slot in slots}),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        return_selected_profile=True,
    )
    return store, bundle.bundle_ref


def test_layout_factory_opens_selected_bundle_and_orders_unrelated_slots(tmp_path) -> None:
    store, ref = _bundle(
        tmp_path,
        "bundle-a",
        (_slot("health.stock", unit_id="person"), _slot("finance.reserve")),
    )
    layout = build_model_scalar_state_layout(
        store=store,
        registry_bundle_ref=ref,
        slot_ids=("health.stock", "finance.reserve"),
    )

    assert tuple(slot.slot_id for slot in layout.slots) == (
        "finance.reserve",
        "health.stock",
    )
    assert tuple(slot.index for slot in layout.slots) == (0, 1)
    opened = load_registry_bundle_content(store, ref)
    assert layout.registry_bundle_ref == opened.bundle_ref
    assert layout.slots[0].slot_spec_sha256.startswith("sha256:")


def test_layout_digest_changes_with_bundle_profile_or_slot_spec(tmp_path) -> None:
    store_a, ref_a = _bundle(tmp_path, "bundle-a", (_slot("finance.reserve"),))
    layout_a = build_model_scalar_state_layout(
        store=store_a,
        registry_bundle_ref=ref_a,
        slot_ids=("finance.reserve",),
    )
    store_b, ref_b = _bundle(
        tmp_path,
        "bundle-b",
        (_slot("finance.reserve", unit_id="eur"),),
    )
    layout_b = build_model_scalar_state_layout(
        store=store_b,
        registry_bundle_ref=ref_b,
        slot_ids=("finance.reserve",),
    )

    assert layout_a.layout_sha256 != layout_b.layout_sha256
    assert layout_a.slots[0].slot_spec_sha256 != layout_b.slots[0].slot_spec_sha256

    with pytest.raises(ValidationError, match="layout_digest_mismatch"):
        ModelScalarStateLayout(
            registry_bundle_ref=ref_b,
            slots=layout_b.slots,
            layout_sha256=layout_a.layout_sha256,
        )


def test_layout_factory_refuses_unregistered_or_unsupported_slots(tmp_path) -> None:
    store, ref = _bundle(tmp_path, "bundle", (_slot("finance.reserve"),))
    with pytest.raises(ModelScalarStateAccessError, match="slot_unregistered"):
        build_model_scalar_state_layout(
            store=store,
            registry_bundle_ref=ref,
            slot_ids=("health.stock",),
        )

    vector_store, vector_ref = _bundle(
        tmp_path,
        "vector-bundle",
        (_slot("health.stock", shape=["population"]),),
    )
    with pytest.raises(ModelScalarStateAccessError, match="slot_profile_unsupported"):
        build_model_scalar_state_layout(
            store=vector_store,
            registry_bundle_ref=vector_ref,
            slot_ids=("health.stock",),
        )


def test_layout_contract_refuses_profileless_registry_reference(tmp_path) -> None:
    store, ref = _bundle(tmp_path, "bundle", (_slot("finance.reserve"),))
    layout = build_model_scalar_state_layout(
        store=store,
        registry_bundle_ref=ref,
        slot_ids=("finance.reserve",),
    )
    profileless_ref = ArtifactRef.model_validate(
        {**ref.model_dump(mode="python"), "manifest_profile_sha256": None}
    )
    with pytest.raises(ValidationError, match="registry_bundle_profile_required"):
        ModelScalarStateLayout(
            registry_bundle_ref=profileless_ref,
            slots=layout.slots,
            layout_sha256=layout.layout_sha256,
        )


def test_shared_slot_spec_digest_preserves_original_layout_wire_rule() -> None:
    slot = SlotSpec.model_validate(
        {**_slot("finance.reserve").model_dump(mode="python"), "description": "Условный запас"}
    )
    original_bytes = json.dumps(
        slot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    original_digest = f"sha256:{hashlib.sha256(original_bytes).hexdigest()}"
    assert model_scalar_state_slot_spec_digest(slot) == original_digest
    for field, value in (
        ("dtype", "float64"),
        ("unit", {"unit_id": "eur"}),
        ("state_path", "government_balance"),
    ):
        substituted = SlotSpec.model_validate({**slot.model_dump(mode="python"), field: value})
        assert model_scalar_state_slot_spec_digest(substituted) != original_digest
