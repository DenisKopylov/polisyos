"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "AdaptiveAgentMechanism",
    "AgentPolicy",
    "build_observations",
    "continuous_actions_from_logits",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AdaptiveAgentMechanism": ("polisyos.foundry.agent_sim.agents", "AdaptiveAgentMechanism"),
    "AgentPolicy": ("polisyos.foundry.agent_sim.agents", "AgentPolicy"),
    "build_observations": ("polisyos.foundry.agent_sim.agents", "build_observations"),
    "continuous_actions_from_logits": (
        "polisyos.foundry.agent_sim.agents",
        "continuous_actions_from_logits",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.agents' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
