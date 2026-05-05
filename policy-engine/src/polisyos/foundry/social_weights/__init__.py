"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "prepare_social_weight_schedule",
    "social_weighted_resource",
    "social_weights_for_incomes",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "prepare_social_weight_schedule": (
        "polisyos.foundry.welfare.social_weights",
        "prepare_social_weight_schedule",
    ),
    "social_weighted_resource": (
        "polisyos.foundry.welfare.social_weights",
        "social_weighted_resource",
    ),
    "social_weights_for_incomes": (
        "polisyos.foundry.welfare.social_weights",
        "social_weights_for_incomes",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.social_weights' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
