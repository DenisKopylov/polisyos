"""Compatibility facade for method execution-plan optimization.

Canonical module: `polisyos.foundry.methods.compiler.plan_optimizer`.
Sunset: 2026-10-01.
"""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import Any

_MODULE = _import_module("polisyos.foundry.methods.compiler.plan_optimizer")
__all__ = list(getattr(_MODULE, "__all__", [name for name in dir(_MODULE) if not name.startswith("_")]))


def __getattr__(name: str) -> Any:
    if name in __all__:
        value = getattr(_MODULE, name)
        globals()[name] = value
        return value
    raise AttributeError(f"{__name__!r} has no attribute {name!r}")


globals().update({name: getattr(_MODULE, name) for name in __all__})
