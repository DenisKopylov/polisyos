"""Expose the compile facade without importing the Trinity compiler eagerly.

The package-level `compile` export is a stable alias of
`polisyos.foundry.compile.api.compile`. It is resolved lazily so tooling can
inspect the package without paying the import cost of the compiler stack.
"""
from __future__ import annotations

import importlib
from typing import Any

__all__ = ["compile"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "compile": ("polisyos.foundry.compile.api", "compile"),
}


def __getattr__(name: str) -> Any:
    """Resolve the lazy `compile` export or raise for unknown names."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
