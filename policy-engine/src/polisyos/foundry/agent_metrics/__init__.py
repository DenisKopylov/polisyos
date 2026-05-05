"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "normalize_action",
    "policy_entropy",
    "risk_action_correlation",
    "risk_action_gap",
    "saturation_rate",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "normalize_action": ("polisyos.foundry.agent_sim.agent_metrics", "normalize_action"),
    "policy_entropy": ("polisyos.foundry.agent_sim.agent_metrics", "policy_entropy"),
    "risk_action_correlation": (
        "polisyos.foundry.agent_sim.agent_metrics",
        "risk_action_correlation",
    ),
    "risk_action_gap": ("polisyos.foundry.agent_sim.agent_metrics", "risk_action_gap"),
    "saturation_rate": ("polisyos.foundry.agent_sim.agent_metrics", "saturation_rate"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.agent_metrics' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
