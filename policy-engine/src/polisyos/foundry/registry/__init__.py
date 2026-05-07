"""Compatibility shim for the canonical Foundry extensions registry."""

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

_TARGET = "polisyos.foundry.extensions.registry"

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "MECHANISM_REGISTRY": (_TARGET, "MECHANISM_REGISTRY"),
    "MECHANISM_SPECS": (_TARGET, "MECHANISM_SPECS"),
    "MechanismRuntimeDescriptor": (_TARGET, "MechanismRuntimeDescriptor"),
    "MissingRuntimeMechanismSupportError": (
        _TARGET,
        "MissingRuntimeMechanismSupportError",
    ),
    "UnsupportedRuntimeFidelityError": (
        _TARGET,
        "UnsupportedRuntimeFidelityError",
    ),
    "create_mechanism": (_TARGET, "create_mechanism"),
    "create_mechanism_from_spec": (_TARGET, "create_mechanism_from_spec"),
    "get_mechanism_class": (_TARGET, "get_mechanism_class"),
    "get_mechanism_descriptor": (_TARGET, "get_mechanism_descriptor"),
    "get_mechanism_spec": (_TARGET, "get_mechanism_spec"),
    "has_runtime_mechanism_support": (
        _TARGET,
        "has_runtime_mechanism_support",
    ),
    "mechanism_catalog": (_TARGET, "mechanism_catalog"),
    "resolve_runtime_fidelity": (_TARGET, "resolve_runtime_fidelity"),
    "validate_mechanism_params": (_TARGET, "validate_mechanism_params"),
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
