"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "build_causal_execution_plan",
    "build_default_execution_plan",
    "build_reproducibility_manifest",
    "evaluate_iteration",
    "persist_evaluator_report",
    "persist_execution_plan",
    "persist_iteration_state",
    "persist_preflight_report",
    "persist_reproducibility_manifest",
    "preflight_execution_plan",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "build_causal_execution_plan": ("polisyos.scientist.llm.cycle", "build_causal_execution_plan"),
    "build_default_execution_plan": (
        "polisyos.scientist.llm.cycle",
        "build_default_execution_plan",
    ),
    "build_reproducibility_manifest": (
        "polisyos.scientist.llm.cycle",
        "build_reproducibility_manifest",
    ),
    "evaluate_iteration": ("polisyos.scientist.llm.cycle", "evaluate_iteration"),
    "persist_evaluator_report": ("polisyos.scientist.llm.cycle", "persist_evaluator_report"),
    "persist_execution_plan": ("polisyos.scientist.llm.cycle", "persist_execution_plan"),
    "persist_iteration_state": ("polisyos.scientist.llm.cycle", "persist_iteration_state"),
    "persist_preflight_report": ("polisyos.scientist.llm.cycle", "persist_preflight_report"),
    "persist_reproducibility_manifest": (
        "polisyos.scientist.llm.cycle",
        "persist_reproducibility_manifest",
    ),
    "preflight_execution_plan": ("polisyos.scientist.llm.cycle", "preflight_execution_plan"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.llm_cycle' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
