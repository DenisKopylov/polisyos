"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "FrontierCapability",
    "FrontierCapabilityStatus",
    "FrontierRuntimeConfig",
    "FrontierRuntimeReport",
    "build_frontier_runtime_report",
    "summarize_agent_promotion_frontier_status",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "FrontierCapability": ("polisyos.scientist.engine.frontier_runtime", "FrontierCapability"),
    "FrontierCapabilityStatus": (
        "polisyos.scientist.engine.frontier_runtime",
        "FrontierCapabilityStatus",
    ),
    "FrontierRuntimeConfig": (
        "polisyos.scientist.engine.frontier_runtime",
        "FrontierRuntimeConfig",
    ),
    "FrontierRuntimeReport": (
        "polisyos.scientist.engine.frontier_runtime",
        "FrontierRuntimeReport",
    ),
    "build_frontier_runtime_report": (
        "polisyos.scientist.engine.frontier_runtime",
        "build_frontier_runtime_report",
    ),
    "summarize_agent_promotion_frontier_status": (
        "polisyos.scientist.engine.frontier_runtime",
        "summarize_agent_promotion_frontier_status",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.frontier_runtime' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
