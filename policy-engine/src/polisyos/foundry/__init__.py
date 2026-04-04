"""Expose the stable Foundry compile/execute entrypoints behind lazy imports.

`polisyos.foundry` is the user-facing facade for turning Trinity bundles into
`ExecPlan` artifacts and replaying those plans against bound `GlobalState`
snapshots. Exports stay lazy so CLI/docs imports do not eagerly load JAX,
solver, or optional catalog backends unless `compile()` or `execute()` is
actually called.

The stable public surface of this package is intentionally narrow:
`compile`, `compile_program` (compatibility alias), and `execute`.
"""
from __future__ import annotations

import importlib
import sys
import types
from typing import Any

__all__ = ["compile", "compile_program", "execute"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "compile": ("polisyos.foundry.compile.api", "compile"),
    "compile_program": ("polisyos.foundry.compile.api", "compile"),
    "execute": ("polisyos.foundry.execute.api", "execute"),
}


def _resolve_lazy_export(name: str) -> Any:
    """Resolve and memoize one stable facade export."""

    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __getattr__(name: str) -> Any:
    """Resolve a lazy public export on first access.

    Args:
        name: Export name requested from the package facade.

    Returns:
        The resolved function object, memoized in module globals.

    Raises:
        AttributeError: If `name` is not part of the stable Foundry facade.
    """
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry' has no attribute '{name}'")
    return _resolve_lazy_export(name)


def __dir__() -> list[str]:
    """Return eager globals plus lazy facade exports for interactive discovery."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))


class _FoundryFacadeModule(types.ModuleType):
    """Keep facade exports stable even after submodule imports shadow package attrs."""

    def __getattribute__(self, name: str) -> Any:
        lazy_imports = types.ModuleType.__getattribute__(self, "_LAZY_IMPORTS")
        if name in lazy_imports:
            module_dict = types.ModuleType.__getattribute__(self, "__dict__")
            current = module_dict.get(name)
            if isinstance(current, types.ModuleType) or current is None:
                return _resolve_lazy_export(name)
        return types.ModuleType.__getattribute__(self, name)


sys.modules[__name__].__class__ = _FoundryFacadeModule
