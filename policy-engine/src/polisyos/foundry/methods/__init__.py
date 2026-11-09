"""Stable lazy facade for Foundry Methods."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .api import _EXPORTS, __all__, __dir__, __version__


def __getattr__(name: str) -> Any:
    """Resolve an existing public export from its current canonical owner."""
    if name not in _EXPORTS:
        raise AttributeError(
            f"module {__name__ + '.api'!r} has no attribute {name!r}"
        ) from KeyError(name)
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    return value
