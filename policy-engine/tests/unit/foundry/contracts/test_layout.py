from __future__ import annotations

import importlib

from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, SlotScope
from polisyos.ir.kernel.slots import build_slot_family_manifest


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
