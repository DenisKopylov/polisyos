"""Public Scientist facade with lazy imports."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = ["ExperimentState", "run_experiment"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "run_experiment": ("polisyos.scientist.api", "run_experiment"),
    "ExperimentState": ("polisyos.scientist.engine.state", "ExperimentState"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
