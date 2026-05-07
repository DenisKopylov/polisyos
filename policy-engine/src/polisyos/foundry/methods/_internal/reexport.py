"""Small helpers for compatibility modules that re-export a canonical target."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def reexport_module(module_name: str, target: str, namespace: dict[str, Any]) -> list[str]:
    """Populate `namespace` from `target` without using star imports."""
    module = import_module(target)
    exported = list(
        getattr(module, "__all__", [name for name in dir(module) if not name.startswith("_")])
    )
    namespace.update({name: getattr(module, name) for name in exported})

    def __getattr__(name: str) -> Any:
        if name in exported:
            value = getattr(module, name)
            namespace[name] = value
            return value
        raise AttributeError(f"{module_name!r} has no attribute {name!r}")

    namespace["__getattr__"] = __getattr__
    return exported
