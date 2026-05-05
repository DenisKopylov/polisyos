from __future__ import annotations

from polisyos.foundry.methods.layout import build_slot_family_manifest
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, SlotScope


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
