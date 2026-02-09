"""Public Core facade."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "artifacts",
    "backends",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "evaluation",
    "errors",
    "llm",
    "observability",
    "pipeline",
    "resilience",
    "registry",
    "run",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
