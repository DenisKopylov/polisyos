"""Small helpers for lazy read_api exports."""

from __future__ import annotations

from importlib import import_module


def load_lazy_export(
    name: str,
    *,
    exports: dict[str, str],
    module_name: str,
    namespace: dict[str, object],
) -> object:
    """Load a public export from its implementation module on first use."""
    target_module = exports.get(name)
    if target_module is None:
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
    value = getattr(import_module(target_module), name)
    namespace[name] = value
    return value


def lazy_dir(namespace: dict[str, object], exports: dict[str, str]) -> list[str]:
    """Return a deterministic dir() result for a lazy read_api module."""
    return sorted({*namespace, *exports})


__all__ = ["lazy_dir", "load_lazy_export"]
