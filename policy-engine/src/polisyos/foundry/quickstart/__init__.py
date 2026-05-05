"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "FeedbackQuickstartRunResult",
    "QuickstartRunResult",
    "build_trivial_trinity_bundle",
    "prepare_trivial_feedback_config",
    "prepare_trivial_input_bindings",
    "prepare_trivial_multiplicity_config",
    "put_trivial_trinity_bundle",
    "resolve_registry_bundle_ref",
    "run_feedback_compile_execute",
    "run_feedback_multiplicity_demo",
    "run_trivial_compile_execute",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "FeedbackQuickstartRunResult": ("polisyos.foundry._quickstart", "FeedbackQuickstartRunResult"),
    "QuickstartRunResult": ("polisyos.foundry._quickstart", "QuickstartRunResult"),
    "build_trivial_trinity_bundle": (
        "polisyos.foundry._quickstart",
        "build_trivial_trinity_bundle",
    ),
    "prepare_trivial_feedback_config": (
        "polisyos.foundry._quickstart",
        "prepare_trivial_feedback_config",
    ),
    "prepare_trivial_input_bindings": (
        "polisyos.foundry._quickstart",
        "prepare_trivial_input_bindings",
    ),
    "prepare_trivial_multiplicity_config": (
        "polisyos.foundry._quickstart",
        "prepare_trivial_multiplicity_config",
    ),
    "put_trivial_trinity_bundle": ("polisyos.foundry._quickstart", "put_trivial_trinity_bundle"),
    "resolve_registry_bundle_ref": ("polisyos.foundry._quickstart", "resolve_registry_bundle_ref"),
    "run_feedback_compile_execute": (
        "polisyos.foundry._quickstart",
        "run_feedback_compile_execute",
    ),
    "run_feedback_multiplicity_demo": (
        "polisyos.foundry._quickstart",
        "run_feedback_multiplicity_demo",
    ),
    "run_trivial_compile_execute": ("polisyos.foundry._quickstart", "run_trivial_compile_execute"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.quickstart' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
