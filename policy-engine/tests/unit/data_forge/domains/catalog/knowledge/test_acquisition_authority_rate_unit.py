"""Catalog unit selection remains narrow when source names a labor-force rate."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityError,
    derive_catalog_unit_from_text,
)
from tests._helpers.lane01_wdi_profiles import (
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    build_fixture_wdi_authority,
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Registered share (percent)", "percent"),
        ("Registered share (percentage)", "percent"),
        ("Registered share (15%)", "percent"),
        ("Fiscal balance (% of GDP)", "percent"),
        ("Registered share (percentage of total labour force)", "percent"),
    ],
)
def test_coordinate_only_mode_extracts_physical_percent_tokens(
    text: str,
    expected: str,
) -> None:
    assert derive_catalog_unit_from_text(text, coordinate_only=True) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Registered percentile score",
        "Registered share (percentage points)",
        "Registered share (percentagepoints)",
        "Registered share (percent) and current USD",
        "Registered share without a unit",
    ],
)
def test_coordinate_only_mode_refuses_nonunit_or_ambiguous_text(text: str) -> None:
    assert derive_catalog_unit_from_text(text, coordinate_only=True) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cash surplus/deficit (% of GDP)", "percent_gdp"),
        ("Unemployment (percentage of the labour force)", "percent"),
        ("GDP (current US$)", "usd"),
        ("Current LCU", "local_currency"),
        ("Consumer price index (2010 = 100)", "index"),
        ("Registered share (percent)", None),
    ],
)
def test_default_catalog_unit_mode_preserves_legacy_projection(
    text: str,
    expected: str | None,
) -> None:
    assert derive_catalog_unit_from_text(text) == expected


def _generic_percent_profile(*, source_title: str, source_description: str) -> CandidateWDIProfile:
    return replace(
        UNEMPLOYMENT_PROFILE,
        construct="registered.share",
        indicator_id="TEST.SHARE",
        source_title=source_title,
        source_description=source_description,
        target_slot="candidate.share",
        population="population:fixture",
        denominator="registered.total",
    )


def test_fixed_transform_resolves_generic_catalog_percent_coordinate(tmp_path: Path) -> None:
    profile = _generic_percent_profile(
        source_title="Registered share (percent)",
        source_description="The registered source coordinate is percent.",
    )
    authority, entry = build_fixture_wdi_authority(tmp_path, profile)

    resolved = authority.resolve(entry.entry_id)

    assert resolved.registration.field_binding.raw_unit == "percent"
    assert resolved.registration.field_binding.canonical_unit == "ratio"
    assert resolved.registration.field_binding.unit_transform == "fixed_multiplicative"
    assert resolved.upstream_catalog_projection is not None
    assert resolved.upstream_catalog_projection["catalog_unit"] == "percent"


def test_fixed_transform_projects_gdp_percentage_as_physical_percent_coordinate(
    tmp_path: Path,
) -> None:
    profile = replace(
        _generic_percent_profile(
            source_title="Controlled source (% of GDP)",
            source_description="Synthetic catalog text used only to identify the percent coordinate.",
        ),
        denominator=None,
        quantity_kind="unconstrained",
    )
    authority, entry = build_fixture_wdi_authority(tmp_path, profile)

    resolved = authority.resolve(entry.entry_id)

    assert resolved.registration.field_binding.raw_unit == "percent"
    assert resolved.registration.field_binding.canonical_unit == "ratio"
    assert resolved.registration.field_binding.unit_transform == "fixed_multiplicative"
    assert resolved.entry.source_semantic_definition_ref is None
    assert resolved.entry.source_measure_scope is not None
    assert resolved.entry.source_measure_scope.denominator is None
    assert resolved.entry.source_measure_scope.quantity_kind == "unconstrained"
    assert resolved.upstream_catalog_projection is not None
    assert resolved.upstream_catalog_projection["catalog_unit"] == "percent"


def test_identity_gdp_percentage_keeps_legacy_percent_gdp_projection(tmp_path: Path) -> None:
    profile = replace(
        _generic_percent_profile(
            source_title="Controlled source (% of GDP)",
            source_description="Synthetic catalog text used only to identify the percent coordinate.",
        ),
        raw_unit="percent_gdp",
        canonical_unit="percent_gdp",
        transform="identity",
        transform_ref="fabric://units/percent-gdp-identity/v1",
        denominator=None,
        quantity_kind="unconstrained",
    )
    authority, entry = build_fixture_wdi_authority(tmp_path, profile)

    resolved = authority.resolve(entry.entry_id)

    assert resolved.registration.field_binding.raw_unit == "percent_gdp"
    assert resolved.registration.field_binding.canonical_unit == "percent_gdp"
    assert resolved.registration.field_binding.unit_transform == "identity"
    assert resolved.upstream_catalog_projection is not None
    assert resolved.upstream_catalog_projection["catalog_unit"] == "percent_gdp"


def test_registered_raw_percent_cannot_fill_unknown_catalog_unit(tmp_path: Path) -> None:
    profile = _generic_percent_profile(
        source_title="Registered share",
        source_description="A controlled source description without a declared unit.",
    )
    authority, entry = build_fixture_wdi_authority(tmp_path, profile)

    with pytest.raises(AcquisitionAuthorityError, match="catalog_unit_unresolved"):
        authority.resolve(entry.entry_id)
