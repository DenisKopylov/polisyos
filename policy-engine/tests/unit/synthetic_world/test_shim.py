from __future__ import annotations

import polisyos.synthetic_world as synthetic_world


def test_synthetic_world_root_shim_reexports_foundry_world_facade() -> None:
    assert synthetic_world.SyntheticWorld.__module__.startswith("polisyos.foundry.agent_sim.world.")
    assert "SyntheticWorld" in synthetic_world.__all__
