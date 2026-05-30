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
_EXPORTS = {
    "OfficialSnapshotAnswer": (
        "polisyos.data_forge.read_api.provenance",
        "OfficialSnapshotAnswer",
    ),
    "build_privacy_compliance_report": (
        "polisyos.data_forge.read_api.compliance",
        "build_privacy_compliance_report",
    ),
    "normalize_privacy_compliance_report": (
        "polisyos.data_forge.read_api.compliance",
        "normalize_privacy_compliance_report",
    ),
}


def __getattr__(name: str) -> object:
    """Lazily import domain read_api modules only when explicitly requested."""
    if name in _SURFACE_NAMES:
        module = load_surface(name)
        globals()[name] = module
        return module
    target = _EXPORTS.get(name)
    if target is not None:
        module_name, attribute_name = target
        from importlib import import_module

        value = getattr(import_module(module_name), attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return public read_api names without importing domain modules."""
    return sorted({*globals(), *_SURFACE_NAMES, *_EXPORTS})


__all__ = [
    "READ_API_SURFACES",
    "OfficialSnapshotAnswer",
    "ReadApiSurface",
    "academic",
    "available_surfaces",
    "build_privacy_compliance_report",
    "catalog",
    "compliance",
    "get_surface",
    "legal",
    "load_surface",
    "normalize_privacy_compliance_report",
    "provenance",
    "surface_module",
    "surfaces",
    "ukraine",
]
