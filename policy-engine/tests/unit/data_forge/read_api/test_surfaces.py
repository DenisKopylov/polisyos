from __future__ import annotations

import pytest

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
from polisyos.data_forge.read_api import (
    academic,
    available_surfaces,
    catalog,
    get_surface,
    surface_module,
)


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
