"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "MECHANISM_REGISTRY",
    "MECHANISM_SPECS",
    "MechanismRuntimeDescriptor",
    "MissingRuntimeMechanismSupportError",
    "UnsupportedRuntimeFidelityError",
    "create_mechanism",
    "create_mechanism_from_spec",
    "get_mechanism_class",
    "get_mechanism_descriptor",
    "get_mechanism_spec",
    "has_runtime_mechanism_support",
    "mechanism_catalog",
    "resolve_runtime_fidelity",
    "validate_mechanism_params",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "MECHANISM_REGISTRY": ("polisyos.foundry._registry", "MECHANISM_REGISTRY"),
    "MECHANISM_SPECS": ("polisyos.foundry._registry", "MECHANISM_SPECS"),
    "MechanismRuntimeDescriptor": ("polisyos.foundry._registry", "MechanismRuntimeDescriptor"),
    "MissingRuntimeMechanismSupportError": (
        "polisyos.foundry._registry",
        "MissingRuntimeMechanismSupportError",
    ),
    "UnsupportedRuntimeFidelityError": (
        "polisyos.foundry._registry",
        "UnsupportedRuntimeFidelityError",
    ),
    "create_mechanism": ("polisyos.foundry._registry", "create_mechanism"),
    "create_mechanism_from_spec": ("polisyos.foundry._registry", "create_mechanism_from_spec"),
    "get_mechanism_class": ("polisyos.foundry._registry", "get_mechanism_class"),
    "get_mechanism_descriptor": ("polisyos.foundry._registry", "get_mechanism_descriptor"),
    "get_mechanism_spec": ("polisyos.foundry._registry", "get_mechanism_spec"),
    "has_runtime_mechanism_support": (
        "polisyos.foundry._registry",
        "has_runtime_mechanism_support",
    ),
    "mechanism_catalog": ("polisyos.foundry._registry", "mechanism_catalog"),
    "resolve_runtime_fidelity": ("polisyos.foundry._registry", "resolve_runtime_fidelity"),
    "validate_mechanism_params": ("polisyos.foundry._registry", "validate_mechanism_params"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.registry' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
