"""Expose the compile facade without importing the Trinity compiler eagerly.

The package-level `compile` export is a stable alias of
`polisyos.foundry.compile.api.compile`. It is resolved lazily so tooling can
inspect the package without paying the import cost of the compiler stack.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

__all__ = ["compile"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "compile": ("polisyos.foundry.compile.api", "compile"),
}


def __getattr__(name: str) -> Any:
    """Resolve the lazy `compile` export or raise for unknown names."""
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    module_name = f"{__name__}.{name}"
    try:
        value = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(name) from None
        raise
    globals()[name] = value
    return value


class _CallableCompileModule(types.ModuleType):
    """Allow `polisyos.foundry.compile(...)` while preserving package imports."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return __getattr__("compile")(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableCompileModule

parent = sys.modules.get("polisyos.foundry")
if parent is not None:
    parent.__dict__["compile"] = sys.modules[__name__]
    parent.__dict__["compile_program"] = sys.modules[__name__]
