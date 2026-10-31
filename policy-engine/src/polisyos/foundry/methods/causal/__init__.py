"""Lazy facade for causal catalog methods."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ._exports import CAUSAL_METHOD_EXPORTS as __all__  # noqa: N811


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("polisyos.foundry.methods.causal._facade"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
