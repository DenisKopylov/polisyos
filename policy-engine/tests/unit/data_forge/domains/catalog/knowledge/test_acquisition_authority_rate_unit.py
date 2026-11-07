"""Catalog unit selection remains narrow when source names a labor-force rate."""

from __future__ import annotations

import pytest

from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    derive_catalog_unit_from_text,
)


@pytest.mark.parametrize(
    "title",
    [
        "Unemployment, total (% of total labor force) (modeled ILO estimate)",
        "Unemployment (percentage of the labour force)",
    ],
)
def test_declared_labor_force_rate_has_percent_unit(title: str) -> None:
    assert derive_catalog_unit_from_text(title) == "percent"


@pytest.mark.parametrize(
    "title",
    [
        "Unemployment (% of the population)",
        "Unemployment rate",
        "Growth (% of GDP) and unemployment (% of total labor force)",
    ],
)
def test_unscoped_or_ambiguous_rate_cannot_mint_unit(title: str) -> None:
    assert derive_catalog_unit_from_text(title) is None
