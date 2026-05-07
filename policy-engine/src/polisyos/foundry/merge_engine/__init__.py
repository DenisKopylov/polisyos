"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "JAXMergeEngine",
    "MergeConflict",
    "MergeConflictContract",
    "MergeConflictError",
    "MergeConflictKind",
    "MergeEngine",
    "MergeRecord",
    "MergeReport",
    "MergeReportContract",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "JAXMergeEngine": ("polisyos.foundry.methods.components.merge_engine", "JAXMergeEngine"),
    "MergeConflict": ("polisyos.foundry.methods.components.merge_engine", "MergeConflict"),
    "MergeConflictContract": ("polisyos.foundry.methods.components.merge_engine", "MergeConflictContract"),
    "MergeConflictError": ("polisyos.foundry.methods.components.merge_engine", "MergeConflictError"),
    "MergeConflictKind": ("polisyos.foundry.methods.components.merge_engine", "MergeConflictKind"),
    "MergeEngine": ("polisyos.foundry.methods.components.merge_engine", "MergeEngine"),
    "MergeRecord": ("polisyos.foundry.methods.components.merge_engine", "MergeRecord"),
    "MergeReport": ("polisyos.foundry.methods.components.merge_engine", "MergeReport"),
    "MergeReportContract": ("polisyos.foundry.methods.components.merge_engine", "MergeReportContract"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.merge_engine' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
