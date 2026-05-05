"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "DecisionValidityService",
    "DecisionValidityStateStore",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DecisionValidityService": (
        "polisyos.scientist.validation.decision_validity",
        "DecisionValidityService",
    ),
    "DecisionValidityStateStore": (
        "polisyos.scientist.validation.decision_validity",
        "DecisionValidityStateStore",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.decision_validity' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
