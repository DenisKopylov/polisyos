"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "ReleaseAcceptanceReport",
    "ReleaseAcceptanceRunner",
    "ReleaseAcceptanceStep",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ReleaseAcceptanceReport": (
        "polisyos.foundry.validation.release_acceptance",
        "ReleaseAcceptanceReport",
    ),
    "ReleaseAcceptanceRunner": (
        "polisyos.foundry.validation.release_acceptance",
        "ReleaseAcceptanceRunner",
    ),
    "ReleaseAcceptanceStep": (
        "polisyos.foundry.validation.release_acceptance",
        "ReleaseAcceptanceStep",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry.release_acceptance' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
