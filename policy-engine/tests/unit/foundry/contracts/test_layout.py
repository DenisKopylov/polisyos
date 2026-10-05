from __future__ import annotations

import importlib

import pytest

from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, SlotScope
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import (
    SlotKind,
    SlotRegistry,
    SlotSpec,
    SlotValueType,
    build_slot_family_manifest,
    build_slot_layout,
)


def test_slot_family_manifest_includes_cell_families() -> None:
    manifest = build_slot_family_manifest(DEFAULT_SLOT_REGISTRY)

    assert "cells" in manifest.families
    assert "household_cells" in manifest.families

    cells = manifest.families["cells"]
    household_cells = manifest.families["household_cells"]
    global_family = manifest.families["global"]

    assert cells.scope == SlotScope.PER_CELL
    assert cells.state_prefix == "cells"
    assert cells.entity_size_key == "n_cells"
    assert "cells.population" in cells.slots
    assert "cells.output" in cells.slots

    assert household_cells.scope == SlotScope.PER_CELL
    assert household_cells.state_prefix == "household_cells"
    assert household_cells.entity_size_key == "n_household_cells"
    assert "household_cells.disposable_income" in household_cells.slots
    assert "household_cells.poverty_rate" in household_cells.slots

    assert global_family.scope == SlotScope.GLOBAL
    assert global_family.state_prefix is None
    assert global_family.entity_size_key is None


def test_foundry_layout_reexports_ir_slot_family_manifest_builder() -> None:
    """Keep the former Foundry import path as a compatibility consumer."""
    from polisyos.foundry.methods.layout import (
        build_slot_family_manifest as foundry_build_slot_family_manifest,
    )

    assert foundry_build_slot_family_manifest is build_slot_family_manifest


def test_foundry_layout_facade_binds_ir_owner_without_compiler_hop() -> None:
    """The stable Foundry facade must bind directly to the IR owner."""
    compiler_facade = importlib.import_module("polisyos.foundry.methods.compiler.layout")
    foundry_facade = importlib.import_module("polisyos.foundry.methods.layout")
    ir_slots = importlib.import_module("polisyos.ir.kernel.slots")
    original = compiler_facade.build_slot_layout
    sentinel = object()

    try:
        compiler_facade.build_slot_layout = sentinel
        reloaded = importlib.reload(foundry_facade)
        assert reloaded.build_slot_layout is ir_slots.build_slot_layout
    finally:
        compiler_facade.build_slot_layout = original
        importlib.reload(foundry_facade)


@pytest.mark.parametrize(
    "module_path",
    ["polisyos.foundry.methods.layout", "polisyos.foundry.methods.compiler.layout"],
)
def test_both_layout_addresses_preserve_all_ir_object_identities(module_path: str) -> None:
    """Compatibility must preserve the whole supported layout ABI."""
    facade = importlib.import_module(module_path)
    ir_slots = importlib.import_module("polisyos.ir.kernel.slots")
    for name in (
        "SlotLayout",
        "SlotFamily",
        "SlotFamilyManifest",
        "build_slot_layout",
        "build_slot_family_manifest",
    ):
        assert getattr(facade, name) is getattr(ir_slots, name)


def test_native_layout_and_family_builders_distinguish_inventory_from_state_paths() -> None:
    """A registered slot may belong to a family without an executable state path."""
    cases = {
        "custom.worker": "agents.income",
        "cells.unbound": None,
        "unscoped.balance": "balance",
    }
    registry = SlotRegistry(
        slots={
            slot_id: SlotSpec(
                slot_id=slot_id,
                scope=SlotScope.GLOBAL,
                kind=SlotKind.STOCK,
                value_type=SlotValueType.DECIMAL,
                merge_rule=MergeRuleRef(rule_id="sum"),
                state_path=state_path,
            )
            for slot_id, state_path in reversed(list(cases.items()))
        }
    )

    layout = build_slot_layout(registry)
    manifest = build_slot_family_manifest(registry)
    assert layout.layout == {
        "custom.worker": "agents.income",
        "unscoped.balance": "balance",
    }
    assert "cells.unbound" not in layout.layout
    assert manifest.families["cells"].slots == ["cells.unbound"]
    assert manifest.families["cells"].entity_size_key == "n_cells"
    assert manifest.families["agents"].slots == ["custom.worker"]
    assert manifest.families["agents"].scope is SlotScope.PER_AGENT
    assert manifest.families["global"].slots == ["unscoped.balance"]
    assert manifest.families["global"].state_prefix is None
    assert manifest.families["global"].entity_size_key is None
