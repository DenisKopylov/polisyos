"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "apply_patch_map",
    "apply_patch_records",
    "apply_state_delta",
    "apply_state_delta_and_snapshot",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "apply_patch_map": ("polisyos.foundry.execute._patching", "apply_patch_map"),
    "apply_patch_records": ("polisyos.foundry.execute._patching", "apply_patch_records"),
    "apply_state_delta": ("polisyos.foundry.execute._patching", "apply_state_delta"),
    "apply_state_delta_and_snapshot": (
        "polisyos.foundry.execute._patching",
        "apply_state_delta_and_snapshot",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry._executor_patching' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
