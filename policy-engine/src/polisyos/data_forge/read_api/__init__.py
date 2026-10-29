"""Stable runtime-safe Data Forge read APIs."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from . import surfaces
from .surface_routes import READ_API_SURFACE_MODULES as _READ_API_SURFACE_MODULES
from .surfaces import (
    READ_API_SURFACES,
    ReadApiSurface,
    available_surfaces,
    get_surface,
    load_surface,
    surface_module,
)

if TYPE_CHECKING:
    from polisyos.data_forge.kernel.io.generation_basis import (
        GenerationBasis as GenerationBasis,
    )
    from polisyos.data_forge.kernel.io.generation_basis import (
        build_generation_basis as build_generation_basis,
    )
    from polisyos.data_forge.kernel.pipeline.manifests import (
        prepare_publish_manifest as prepare_publish_manifest,
    )
    from polisyos.data_forge.kernel.pipeline.manifests import read_manifest as read_manifest
    from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
    from polisyos.data_forge.kernel.snapshot import finalize_snapshot
    from polisyos.data_forge.kernel.snapshot.finalize import (
        prepare_snapshot_binding_meaning as prepare_snapshot_binding_meaning,
    )
    from polisyos.data_forge.kernel.snapshot.finalize import (
        read_snapshot_binding_meaning as read_snapshot_binding_meaning,
    )
    from polisyos.data_forge.read_api.compliance import (
        build_privacy_compliance_report as build_privacy_compliance_report,
    )
    from polisyos.data_forge.read_api.compliance import (
        normalize_privacy_compliance_report as normalize_privacy_compliance_report,
    )
    from polisyos.data_forge.read_api.provenance import (
        OfficialSnapshotAnswer as OfficialSnapshotAnswer,
    )
    from polisyos.data_forge.read_api.ukraine import (
        UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT,
    )
    from polisyos.data_forge.read_api.ukraine import (
        UkraineD4GovernanceRequest as UkraineD4GovernanceRequest,
    )
    from polisyos.data_forge.read_api.ukraine import (
        UkraineIdentityResolutionCohort as UkraineIdentityResolutionCohort,
    )
    from polisyos.data_forge.read_api.ukraine import (
        UkraineIdentityResolutionCohortRow as UkraineIdentityResolutionCohortRow,
    )
    from polisyos.data_forge.read_api.ukraine import (
        ukraine_d4_json_snapshot_model_type as ukraine_d4_json_snapshot_model_type,
    )

    from . import academic as academic
    from . import catalog as catalog
    from . import compliance as compliance
    from . import legal as legal
    from . import provenance as provenance
    from . import ukraine as ukraine

_EXPORTS = {
    "UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT": (
        "polisyos.data_forge.read_api.ukraine",
        "UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT",
    ),
    "UkraineD4GovernanceRequest": (
        "polisyos.data_forge.read_api.ukraine",
        "UkraineD4GovernanceRequest",
    ),
    "UkraineIdentityResolutionCohort": (
        "polisyos.data_forge.read_api.ukraine",
        "UkraineIdentityResolutionCohort",
    ),
    "UkraineIdentityResolutionCohortRow": (
        "polisyos.data_forge.read_api.ukraine",
        "UkraineIdentityResolutionCohortRow",
    ),
    "ukraine_d4_json_snapshot_model_type": (
        "polisyos.data_forge.read_api.ukraine",
        "ukraine_d4_json_snapshot_model_type",
    ),
    "OfficialSnapshotAnswer": (
        "polisyos.data_forge.read_api.provenance",
        "OfficialSnapshotAnswer",
    ),
    "GenerationBasis": ("polisyos.data_forge.kernel.io.generation_basis", "GenerationBasis"),
    "build_generation_basis": (
        "polisyos.data_forge.kernel.io.generation_basis",
        "build_generation_basis",
    ),
    "build_privacy_compliance_report": (
        "polisyos.data_forge.read_api.compliance",
        "build_privacy_compliance_report",
    ),
    "normalize_privacy_compliance_report": (
        "polisyos.data_forge.read_api.compliance",
        "normalize_privacy_compliance_report",
    ),
    "prepare_publish_manifest": (
        "polisyos.data_forge.kernel.pipeline.manifests",
        "prepare_publish_manifest",
    ),
    "prepare_snapshot_binding_meaning": (
        "polisyos.data_forge.kernel.snapshot.finalize",
        "prepare_snapshot_binding_meaning",
    ),
    "read_snapshot_binding_meaning": (
        "polisyos.data_forge.kernel.snapshot.finalize",
        "read_snapshot_binding_meaning",
    ),
    "read_manifest": ("polisyos.data_forge.kernel.pipeline.manifests", "read_manifest"),
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
    if name in _READ_API_SURFACE_MODULES:
        module = import_module(_READ_API_SURFACE_MODULES[name])
        globals()[name] = module
        return module
    target = _EXPORTS.get(name)
    if target is not None:
        module_name, attribute_name = target
        value = getattr(import_module(module_name), attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return public read_api names without importing domain modules."""
    return sorted({*globals(), *_READ_API_SURFACE_MODULES, *_EXPORTS})


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
    "UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT",
    "GenerationBasis",
    "OfficialSnapshotAnswer",
    "ReadApiSurface",
    "UkraineD4GovernanceRequest",
    "UkraineIdentityResolutionCohort",
    "UkraineIdentityResolutionCohortRow",
    "academic",
    "available_surfaces",
    "build_generation_basis",
    "build_privacy_compliance_report",
    "catalog",
    "compliance",
    "finalize_snapshot",
    "get_surface",
    "legal",
    "load_surface",
    "normalize_privacy_compliance_report",
    "pipeline_binding_surface",
    "prepare_publish_manifest",
    "prepare_snapshot_binding_meaning",
    "provenance",
    "read_manifest",
    "read_snapshot_binding_meaning",
    "surface_module",
    "surfaces",
    "ukraine",
    "ukraine_d4_json_snapshot_model_type",
    "write_publish_manifest",
]
