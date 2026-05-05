"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "MechanismSpec",
    "get_mechanism_spec",
    "mechanism_catalog",
    "validate_mechanism_params",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "MechanismSpec": ("polisyos.foundry.contracts.specs", "MechanismSpec"),
    "get_mechanism_spec": ("polisyos.foundry.contracts.specs", "get_mechanism_spec"),
    "mechanism_catalog": ("polisyos.foundry.contracts.specs", "mechanism_catalog"),
    "validate_mechanism_params": ("polisyos.foundry.contracts.specs", "validate_mechanism_params"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.specs' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
