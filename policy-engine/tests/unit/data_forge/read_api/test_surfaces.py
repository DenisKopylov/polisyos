from __future__ import annotations

import pytest

from polisyos.data_forge.read_api import (
    available_surfaces,
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
