"""Stable execute facade for compiled Foundry plans."""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

__all__ = ["ResolvedExecutionPosture", "execute", "resolve_execution_posture"]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ResolvedExecutionPosture": ("polisyos.foundry.execute.api", "ResolvedExecutionPosture"),
    "execute": ("polisyos.foundry.execute.api", "execute"),
    "resolve_execution_posture": ("polisyos.foundry.execute.api", "resolve_execution_posture"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value

    module_name = f"{__name__}.{name}"
    try:
        value = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(
                f"module 'polisyos.foundry.execute' has no attribute {name!r}"
            ) from None
        raise
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))


class _CallableExecuteModule(types.ModuleType):
    """Allow `polisyos.foundry.execute(...)` while preserving package imports."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return __getattr__("execute")(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableExecuteModule
