"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "CostBudget",
    "CostEstimate",
    "CostModel",
    "create_cost_model",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CostBudget": ("polisyos.foundry.methods.cost_model", "CostBudget"),
    "CostEstimate": ("polisyos.foundry.methods.cost_model", "CostEstimate"),
    "CostModel": ("polisyos.foundry.methods.cost_model", "CostModel"),
    "create_cost_model": ("polisyos.foundry.methods.cost_model", "create_cost_model"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.cost_model' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
