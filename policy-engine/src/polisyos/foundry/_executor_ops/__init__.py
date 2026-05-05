"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "apply_op",
    "apply_operator",
    "apply_ops_for_slot",
    "apply_ops_to_state",
    "check_constraints",
    "coerce_number",
    "coerce_selector_scalar",
    "evaluate_selector",
    "selector_field_values",
    "validate_ops_compatibility",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "apply_op": ("polisyos.foundry.execute._ops", "apply_op"),
    "apply_operator": ("polisyos.foundry.execute._ops", "apply_operator"),
    "apply_ops_for_slot": ("polisyos.foundry.execute._ops", "apply_ops_for_slot"),
    "apply_ops_to_state": ("polisyos.foundry.execute._ops", "apply_ops_to_state"),
    "check_constraints": ("polisyos.foundry.execute._ops", "check_constraints"),
    "coerce_number": ("polisyos.foundry.execute._ops", "coerce_number"),
    "coerce_selector_scalar": ("polisyos.foundry.execute._ops", "coerce_selector_scalar"),
    "evaluate_selector": ("polisyos.foundry.execute._ops", "evaluate_selector"),
    "selector_field_values": ("polisyos.foundry.execute._ops", "selector_field_values"),
    "validate_ops_compatibility": ("polisyos.foundry.execute._ops", "validate_ops_compatibility"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry._executor_ops' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
