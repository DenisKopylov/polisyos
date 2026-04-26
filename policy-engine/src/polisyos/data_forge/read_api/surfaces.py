"""Catalog of runtime-safe Data Forge read API surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(frozen=True, slots=True)
class ReadApiSurface:
    """Public read_api surface metadata without importing domain internals."""

    name: str
    module: str
    summary: str


READ_API_SURFACES: tuple[ReadApiSurface, ...] = (
    ReadApiSurface(
        name="academic",
        module="polisyos.data_forge.read_api.academic",
        summary="Academic artifact, readiness, and shadow-diff readers.",
    ),
    ReadApiSurface(
        name="catalog",
        module="polisyos.data_forge.read_api.catalog",
        summary="Dataset catalog artifact, source-module, readiness, and shadow-diff readers.",
    ),
    ReadApiSurface(
        name="legal",
        module="polisyos.data_forge.read_api.legal",
        summary="Read-only Lex shadow artifact and differential readers.",
    ),
    ReadApiSurface(
        name="ukraine",
        module="polisyos.data_forge.read_api.ukraine",
        summary="Ukraine non-Lex artifact and demographic static-aging readers.",
    ),
)

_SURFACES_BY_NAME = {surface.name: surface for surface in READ_API_SURFACES}


def available_surfaces() -> tuple[str, ...]:
    """Return available read_api surface names."""
    return tuple(surface.name for surface in READ_API_SURFACES)


def get_surface(name: str) -> ReadApiSurface:
    """Return metadata for a read_api surface."""
    try:
        return _SURFACES_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"unknown Data Forge read_api surface: {name}") from exc


def load_surface(name: str) -> ModuleType:
    """Import and return a read_api surface module by name."""
    return import_module(get_surface(name).module)


def surface_module(name: str) -> str:
    """Return the module path for a read_api surface."""
    return get_surface(name).module


__all__ = [
    "READ_API_SURFACES",
    "ReadApiSurface",
    "available_surfaces",
    "get_surface",
    "load_surface",
    "surface_module",
]
