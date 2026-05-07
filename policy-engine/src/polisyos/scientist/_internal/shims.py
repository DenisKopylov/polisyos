"""Shared helpers for Scientist compatibility modules."""

from __future__ import annotations

import importlib
from typing import Any


def install_lazy_module_shim(
    module_globals: dict[str, Any],
    *,
    legacy_module: str,
    canonical_module: str,
    public_names: tuple[str, ...],
    sunset_date: str,
    migration_hint: str,
    deprecated_since: str = "2026-05-05",
    shim_id: str | None = None,
) -> None:
    """Populate a legacy module with lazy exports and sunset metadata."""
    resolved_shim_id = shim_id or _default_shim_id(legacy_module, canonical_module)
    lazy_imports = {name: (canonical_module, name) for name in public_names}

    module_globals["__all__"] = public_names
    module_globals["__canonical_module__"] = canonical_module
    module_globals["__deprecated_since__"] = deprecated_since
    module_globals["__shim_id__"] = resolved_shim_id
    module_globals["__shim_sunset_date__"] = sunset_date
    module_globals["__sunset_date__"] = sunset_date
    module_globals["__migration_hint__"] = migration_hint
    module_globals["__shim_metadata__"] = {
        "id": resolved_shim_id,
        "legacy_module": legacy_module,
        "canonical_module": canonical_module,
        "deprecated_since": deprecated_since,
        "sunset_date": sunset_date,
        "migration_hint": migration_hint,
    }
    module_globals["_LAZY_IMPORTS"] = lazy_imports

    def _module_getattr(name: str) -> object:
        if name not in lazy_imports:
            raise AttributeError(f"module {legacy_module!r} has no attribute {name!r}")
        module_name, attr_name = lazy_imports[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        module_globals[name] = value
        return value

    def _module_dir() -> list[str]:
        return sorted(set(module_globals) | set(public_names))

    module_globals["__getattr__"] = _module_getattr
    module_globals["__dir__"] = _module_dir


def _default_shim_id(legacy_module: str, canonical_module: str) -> str:
    legacy_tail = legacy_module.removeprefix("polisyos.scientist.").replace(".", "_")
    canonical_tail = canonical_module.removeprefix("polisyos.scientist.").replace(".", "_")
    return f"scientist.{legacy_tail}-to-{canonical_tail}"


__all__ = ["install_lazy_module_shim"]
