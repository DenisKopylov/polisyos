"""Shared helpers for package-level lazy facades."""

from __future__ import annotations

import importlib
from typing import Any

LazyExportMap = dict[str, tuple[str, str]]


def resolve_lazy_export(
    name: str,
    *,
    namespace: dict[str, Any],
    exports: LazyExportMap,
) -> Any:
    """Resolve one lazily-exported symbol and memoize it in ``namespace``."""
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value


def lazy_dir(namespace: dict[str, Any], exports: LazyExportMap) -> list[str]:
    """Return a stable ``dir()`` view for lazy facades."""
    return sorted(set(namespace) | set(exports))


__all__ = ["LazyExportMap", "lazy_dir", "resolve_lazy_export"]
