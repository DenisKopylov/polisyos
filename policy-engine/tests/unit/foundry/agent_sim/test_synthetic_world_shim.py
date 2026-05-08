from __future__ import annotations

from pathlib import Path

import polisyos.synthetic_world as synthetic_world
from polisyos.foundry.agent_sim import world as canonical_world


def test_synthetic_world_root_shim_reexports_canonical_world_until_july_2026() -> None:
    shim_dir = Path(synthetic_world.__file__).resolve().parent
    shim_py_files = {path.name for path in shim_dir.iterdir() if path.suffix == ".py"}
    shim_subpackages = {
        path.name for path in shim_dir.iterdir() if path.is_dir() and path.name != "__pycache__"
    }

    assert "2026-07-31" in (synthetic_world.__doc__ or "")
    assert shim_py_files == {"__init__.py"}
    assert shim_subpackages == set()
    assert synthetic_world.__all__ == canonical_world.__all__
    assert synthetic_world.SyntheticWorld is canonical_world.SyntheticWorld
