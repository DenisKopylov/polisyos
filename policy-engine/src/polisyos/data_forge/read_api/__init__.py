"""Stable runtime-safe Data Forge read APIs."""

from __future__ import annotations

from . import surfaces
from .surfaces import (
    READ_API_SURFACES,
    ReadApiSurface,
    available_surfaces,
    get_surface,
    load_surface,
    surface_module,
)

_SURFACE_NAMES = frozenset(available_surfaces())


def __getattr__(name: str) -> object:
    """Lazily import domain read_api modules only when explicitly requested."""
    if name in _SURFACE_NAMES:
        module = load_surface(name)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return public read_api names without importing domain modules."""
    return sorted({*globals(), *_SURFACE_NAMES})


__all__ = [
    "READ_API_SURFACES",
    "ReadApiSurface",
    "academic",
    "available_surfaces",
    "catalog",
    "get_surface",
    "legal",
    "load_surface",
    "surface_module",
    "surfaces",
    "ukraine",
]
