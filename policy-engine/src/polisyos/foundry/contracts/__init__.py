from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AgentState",
    "ComplexMechanism",
    "FidelityLevel",
    "FirmState",
    "GlobalState",
    "MarketState",
    "Mechanism",
    "PatchMap",
    "PatchRecord",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AgentState": ("polisyos.foundry.contracts.state", "AgentState"),
    "FirmState": ("polisyos.foundry.contracts.state", "FirmState"),
    "MarketState": ("polisyos.foundry.contracts.state", "MarketState"),
    "GlobalState": ("polisyos.foundry.contracts.state", "GlobalState"),
    "FidelityLevel": ("polisyos.foundry.contracts.fidelity", "FidelityLevel"),
    "PatchRecord": ("polisyos.foundry.contracts.mechanism", "PatchRecord"),
    "PatchMap": ("polisyos.foundry.contracts.mechanism", "PatchMap"),
    "Mechanism": ("polisyos.foundry.contracts.mechanism", "Mechanism"),
    "ComplexMechanism": ("polisyos.foundry.contracts.mechanism", "ComplexMechanism"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.contracts' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
