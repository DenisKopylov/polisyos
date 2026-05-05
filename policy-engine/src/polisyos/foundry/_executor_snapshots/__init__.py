"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "export_seed_state_npz",
    "import_seed_state_npz",
    "load_state_snapshot",
    "put_state_snapshot",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "export_seed_state_npz": ("polisyos.foundry.execute._snapshots", "export_seed_state_npz"),
    "import_seed_state_npz": ("polisyos.foundry.execute._snapshots", "import_seed_state_npz"),
    "load_state_snapshot": ("polisyos.foundry.execute._snapshots", "load_state_snapshot"),
    "put_state_snapshot": ("polisyos.foundry.execute._snapshots", "put_state_snapshot"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry._executor_snapshots' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
