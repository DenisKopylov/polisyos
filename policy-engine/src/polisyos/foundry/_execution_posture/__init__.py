"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "ResolvedExecutionPosture",
    "resolve_execution_posture",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ResolvedExecutionPosture": ("polisyos.foundry.execute._posture", "ResolvedExecutionPosture"),
    "resolve_execution_posture": ("polisyos.foundry.execute._posture", "resolve_execution_posture"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry._execution_posture' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
