"""Built-in component packs for PolicyOS Phase 19."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = ["roads", "econ"]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module 'polisyos.packs' has no attribute '{name}'")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
