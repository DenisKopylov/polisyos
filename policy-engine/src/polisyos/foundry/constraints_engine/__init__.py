"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "AggregationFunction",
    "check_composite_constraints",
    "check_constraints",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AggregationFunction": (
        "polisyos.foundry.validation.constraints_engine",
        "AggregationFunction",
    ),
    "check_composite_constraints": (
        "polisyos.foundry.validation.constraints_engine",
        "check_composite_constraints",
    ),
    "check_constraints": ("polisyos.foundry.validation.constraints_engine", "check_constraints"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry.constraints_engine' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
