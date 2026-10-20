"""Catalog of runtime-safe Data Forge read API surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

from .surface_routes import READ_API_SURFACE_MODULES, READ_API_SURFACE_SUMMARIES

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(frozen=True, slots=True)
class ReadApiSurface:
    """Public read_api surface metadata without importing domain internals."""

    name: str
    module: str
    summary: str


READ_API_SURFACES: tuple[ReadApiSurface, ...] = tuple(
    ReadApiSurface(name=name, module=module, summary=READ_API_SURFACE_SUMMARIES[name])
    for name, module in READ_API_SURFACE_MODULES.items()
)

_SURFACES_BY_NAME = {surface.name: surface for surface in READ_API_SURFACES}


def available_surfaces() -> tuple[str, ...]:
    """Return available read_api surface names."""
    return tuple(READ_API_SURFACE_MODULES)


def get_surface(name: str) -> ReadApiSurface:
    """Return metadata for a read_api surface."""
    try:
        return _SURFACES_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"unknown Data Forge read_api surface: {name}") from exc


def load_surface(name: str) -> ModuleType:
    """Import and return a read_api surface module by name."""
    try:
        module = READ_API_SURFACE_MODULES[name]
    except KeyError as exc:
        raise KeyError(f"unknown Data Forge read_api surface: {name}") from exc
    return import_module(module)


def surface_module(name: str) -> str:
    """Return the module path for a read_api surface."""
    try:
        return READ_API_SURFACE_MODULES[name]
    except KeyError as exc:
        raise KeyError(f"unknown Data Forge read_api surface: {name}") from exc


__all__ = [
    "READ_API_SURFACES",
    "ReadApiSurface",
    "available_surfaces",
    "get_surface",
    "load_surface",
    "surface_module",
]
