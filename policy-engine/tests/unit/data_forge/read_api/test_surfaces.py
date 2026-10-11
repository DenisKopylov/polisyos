from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.core.artifacts.protocol import (
    resolve_manifest_by_profile as canonical_resolve_manifest_by_profile,
)
from polisyos.core.canon.canon_json import (
    CanonSpec as CanonicalCanonSpec,
)
from polisyos.core.canon.canon_json import (
    from_canonical_bytes as canonical_from_canonical_bytes,
)
from polisyos.core.canon.hashing import content_hash as canonical_content_hash
from polisyos.core.contracts import CatalogRunProfile as CoreCatalogRunProfile
from polisyos.core.contracts.control import (
    CatalogRunProfile as CanonicalCoreCatalogRunProfile,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGRead as CanonicalPreparedSKGRead,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGReadReceipt as CanonicalPreparedSKGReadReceipt,
)
from polisyos.data_forge.domains.catalog import (
    CatalogRunProfile,
    CatalogSourceRegistryEntry,
    CatalogSourceRegistrySpec,
)
from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError as CanonicalCatalogSelectionError,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection as CanonicalActivatedAcquisitionObservationProjection,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay as CanonicalCatalogAcquisitionOverlay,
)
from polisyos.data_forge.read_api import (
    academic,
    available_surfaces,
    catalog,
    get_surface,
    surface_module,
)
from polisyos.ir import analytics as ir_analytics
from polisyos.ir.analytics.causal_graph import CausalGraphModel as CanonicalCausalGraphModel
from polisyos.ir.analytics.data_views import DataViewRequest as CanonicalDataViewRequest


def test_catalog_type_checking_exports_match_lazy_mapping() -> None:
    catalog_module = import_module("polisyos.data_forge.read_api.catalog")
    tree = ast.parse(Path(catalog_module.__file__).read_text(encoding="utf-8"))
    type_only_exports = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for statement in node.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module is not None
        and statement.module.startswith("polisyos.data_forge.")
        for alias in statement.names
    }
    assert type_only_exports == set(catalog_module._EXPORTS)


def test_existing_facade_exports_preserve_canonical_object_identity() -> None:
    assert core_artifacts.resolve_manifest_by_profile is canonical_resolve_manifest_by_profile
    assert core_canon.CanonSpec is CanonicalCanonSpec
    assert core_canon.from_canonical_bytes is canonical_from_canonical_bytes
    assert core_canon.content_hash is canonical_content_hash
    assert CoreCatalogRunProfile is CanonicalCoreCatalogRunProfile
    assert ir_analytics.CausalGraphModel is CanonicalCausalGraphModel
    assert ir_analytics.DataViewRequest is CanonicalDataViewRequest
    assert catalog.CatalogRunProfile is CatalogRunProfile
    assert catalog.CatalogSelectionError is CanonicalCatalogSelectionError
    assert (
        catalog.ActivatedAcquisitionObservationProjection
        is CanonicalActivatedAcquisitionObservationProjection
    )
    assert catalog.CatalogAcquisitionOverlay is CanonicalCatalogAcquisitionOverlay

def test_read_api_surface_registry_resolves_public_modules() -> None:
    assert set(available_surfaces()) >= {"academic", "catalog", "legal", "ukraine"}

    catalog = get_surface("catalog")

    assert catalog.module == "polisyos.data_forge.read_api.catalog"
    assert surface_module("ukraine") == "polisyos.data_forge.read_api.ukraine"


def test_read_api_surface_registry_rejects_unknown_surface() -> None:
    with pytest.raises(KeyError, match="unknown Data Forge read_api surface"):
        get_surface("runtime")


def test_runtime_contract_exports_keep_canonical_object_identity() -> None:
    assert academic.PreparedSKGRead is CanonicalPreparedSKGRead
    assert academic.PreparedSKGReadReceipt is CanonicalPreparedSKGReadReceipt
    assert catalog.CatalogRunProfile is CatalogRunProfile
    assert catalog.CatalogSourceRegistryEntry is CatalogSourceRegistryEntry
    assert catalog.CatalogSourceRegistrySpec is CatalogSourceRegistrySpec
