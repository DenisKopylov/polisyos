"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "SlotFamily",
    "SlotFamilyManifest",
    "SlotLayout",
    "build_slot_family_manifest",
    "build_slot_layout",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "SlotFamily": ("polisyos.foundry.methods.layout", "SlotFamily"),
    "SlotFamilyManifest": ("polisyos.foundry.methods.layout", "SlotFamilyManifest"),
    "SlotLayout": ("polisyos.foundry.methods.layout", "SlotLayout"),
    "build_slot_family_manifest": ("polisyos.foundry.methods.layout", "build_slot_family_manifest"),
    "build_slot_layout": ("polisyos.foundry.methods.layout", "build_slot_layout"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.layout' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
