"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "QueueMechanism",
    "QueueState",
    "fidelity_gap_report",
    "simulate_queue",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "QueueMechanism": ("polisyos.foundry.execute.queue", "QueueMechanism"),
    "QueueState": ("polisyos.foundry.execute.queue", "QueueState"),
    "fidelity_gap_report": ("polisyos.foundry.execute.queue", "fidelity_gap_report"),
    "simulate_queue": ("polisyos.foundry.execute.queue", "simulate_queue"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.queue' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
