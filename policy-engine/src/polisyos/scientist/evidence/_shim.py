"""Internal helpers for Scientist evidence-lane compatibility shims."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any


def install_module_shim(
    module_globals: dict[str, Any],
    *,
    legacy_module: str,
    canonical_module: str,
    shim_id: str,
    sunset_date: str,
    migration_hint: str,
    public_names: tuple[str, ...] | None = None,
) -> None:
    """Populate a legacy module namespace from its canonical implementation."""

    impl = importlib.import_module(canonical_module)
    exported = public_names or tuple(getattr(impl, "__all__", ()))
    if not exported:
        exported = tuple(name for name in dir(impl) if not name.startswith("_"))

    module_globals["_SHIM_TARGET"] = impl
    module_globals["__all__"] = exported
    module_globals["__shim_id__"] = shim_id
    module_globals["__canonical_module__"] = canonical_module
    module_globals["__deprecated_since__"] = "2026-05-05"
    module_globals["__sunset_date__"] = sunset_date
    module_globals["__migration_hint__"] = migration_hint
    module_globals["__shim_metadata__"] = {
        "id": shim_id,
        "legacy_module": legacy_module,
        "canonical_module": canonical_module,
        "deprecated_since": "2026-05-05",
        "sunset_date": sunset_date,
        "migration_hint": migration_hint,
    }
    for name in exported:
        module_globals[name] = getattr(impl, name)


def shim_getattr(module_globals: dict[str, Any], name: str) -> Any:
    target = module_globals["_SHIM_TARGET"]
    if not isinstance(target, ModuleType):
        raise AttributeError(name)
    value = getattr(target, name)
    module_globals[name] = value
    return value


def shim_dir(module_globals: dict[str, Any]) -> list[str]:
    return sorted(set(module_globals) | set(module_globals.get("__all__", ())))


__all__ = [
    "install_module_shim",
    "shim_dir",
    "shim_getattr",
]
