"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "compute_mechanism_welfare_bound_report",
    "load_observed_range_bundle",
    "load_welfare_bound_report",
    "persist_observed_range_bundle",
    "persist_welfare_bound_report",
    "safe_compute_mechanism_welfare_bound_report",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "compute_mechanism_welfare_bound_report": (
        "polisyos.foundry.welfare.bounds",
        "compute_mechanism_welfare_bound_report",
    ),
    "load_observed_range_bundle": ("polisyos.foundry.welfare.bounds", "load_observed_range_bundle"),
    "load_welfare_bound_report": ("polisyos.foundry.welfare.bounds", "load_welfare_bound_report"),
    "persist_observed_range_bundle": (
        "polisyos.foundry.welfare.bounds",
        "persist_observed_range_bundle",
    ),
    "persist_welfare_bound_report": (
        "polisyos.foundry.welfare.bounds",
        "persist_welfare_bound_report",
    ),
    "safe_compute_mechanism_welfare_bound_report": (
        "polisyos.foundry.welfare.bounds",
        "safe_compute_mechanism_welfare_bound_report",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.welfare_bounds' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
