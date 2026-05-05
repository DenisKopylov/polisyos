"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "GradientHealthReport",
    "gradient_health",
    "gradient_health_report",
    "soft_clamp",
    "soft_step",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "GradientHealthReport": ("polisyos.foundry._internal.utils", "GradientHealthReport"),
    "gradient_health": ("polisyos.foundry._internal.utils", "gradient_health"),
    "gradient_health_report": ("polisyos.foundry._internal.utils", "gradient_health_report"),
    "soft_clamp": ("polisyos.foundry._internal.utils", "soft_clamp"),
    "soft_step": ("polisyos.foundry._internal.utils", "soft_step"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.utils' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
