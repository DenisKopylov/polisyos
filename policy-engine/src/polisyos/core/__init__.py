"""Public Core facade."""

from __future__ import annotations

import importlib

__all__ = [
    "artifacts",
    "backends",
    "canon",
    "components",
    "contracts",
    "discovery",
    "evaluation",
    "errors",
    "llm",
    "observability",
    "registry",
    "run",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module
