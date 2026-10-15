"""Stable runtime-safe Data Forge read APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import surfaces
from .surfaces import (
    READ_API_SURFACES,
    ReadApiSurface,
    available_surfaces,
    get_surface,
    load_surface,
    surface_module,
)

if TYPE_CHECKING:
    from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
    from polisyos.data_forge.kernel.snapshot import finalize_snapshot

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
    "write_publish_manifest": (
        "polisyos.data_forge.kernel.pipeline.manifests",
        "write_publish_manifest",
    ),
    "finalize_snapshot": (
        "polisyos.data_forge.kernel.snapshot",
        "finalize_snapshot",
    ),
}


def __getattr__(name: str) -> object:
    """Lazily import the selected public implementation only when requested."""
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


def pipeline_binding_surface(pipeline: str) -> tuple[str, str] | None:
    """Return Data Forge's immutable role/surface pair for one pipeline.

    The canonical mapping remains owned by snapshot finalization and is loaded
    only when a caller asks to resolve one pipeline.

    Args:
        pipeline: Canonical snapshot pipeline identifier.

    Returns:
        The role/surface pair owned by snapshot finalization, or ``None`` when
        the pipeline has no registered binding surface.
    """
    from importlib import import_module

    bindings = import_module("polisyos.data_forge.kernel.snapshot").PIPELINE_BINDING_SURFACES
    selected = bindings.get(pipeline)
    if selected is None:
        return None
    return (selected[0], selected[1])


__all__ = [
    "READ_API_SURFACES",
    "OfficialSnapshotAnswer",
    "ReadApiSurface",
    "academic",
    "available_surfaces",
    "build_privacy_compliance_report",
    "catalog",
    "compliance",
    "finalize_snapshot",
    "get_surface",
    "legal",
    "load_surface",
    "normalize_privacy_compliance_report",
    "pipeline_binding_surface",
    "provenance",
    "surface_module",
    "surfaces",
    "ukraine",
    "write_publish_manifest",
]
