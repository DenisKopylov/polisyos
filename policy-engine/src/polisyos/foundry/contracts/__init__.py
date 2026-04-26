"""Re-export public Foundry state and fidelity contracts shared across subsystems."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AgentSimRuntimeState",
    "AgentState",
    "CellState",
    "ComplexMechanism",
    "FeedbackState",
    "FidelityLevel",
    "FirmState",
    "GlobalState",
    "HouseholdCellState",
    "MarketState",
    "Mechanism",
    "PatchMap",
    "PatchRecord",
    "ProcurementGraphState",
    "QueueEventCalendarState",
    "QueueRuntimeState",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AgentState": ("polisyos.foundry.contracts.state", "AgentState"),
    "AgentSimRuntimeState": ("polisyos.foundry.contracts.state", "AgentSimRuntimeState"),
    "CellState": ("polisyos.foundry.contracts.state", "CellState"),
    "FeedbackState": ("polisyos.foundry.contracts.state", "FeedbackState"),
    "FirmState": ("polisyos.foundry.contracts.state", "FirmState"),
    "HouseholdCellState": ("polisyos.foundry.contracts.state", "HouseholdCellState"),
    "MarketState": ("polisyos.foundry.contracts.state", "MarketState"),
    "GlobalState": ("polisyos.foundry.contracts.state", "GlobalState"),
    "ProcurementGraphState": ("polisyos.foundry.contracts.state", "ProcurementGraphState"),
    "QueueEventCalendarState": (
        "polisyos.foundry.contracts.state",
        "QueueEventCalendarState",
    ),
    "QueueRuntimeState": ("polisyos.foundry.contracts.state", "QueueRuntimeState"),
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
