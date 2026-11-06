from __future__ import annotations

import pytest

from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    COUNTRY_SCOPES,
    all_country_codes,
    country_region,
    country_scope_members,
    iso2_to_iso3,
    iso2_to_numeric,
    normalize_country_code,
)


def test_country_forms_preserve_canonical_identity_and_unknown_scope_refusal() -> None:
    forms = ("AM", "am", "ARM", "051", "Armenia", "Hayastan")

    assert {normalize_country_code(value) for value in forms} == {"AM"}
    assert iso2_to_iso3("051") == "ARM"
    assert iso2_to_numeric("Hayastan") == "051"

    assert normalize_country_code("51") == ""
    assert normalize_country_code("Atlantis") == ""
    assert country_scope_members("") == COUNTRY_SCOPES["regional_extended"]
    with pytest.raises(ValueError, match="Unknown country scope"):
        country_scope_members("not-a-registered-scope")


def test_united_states_aliases_preserve_country_identity_and_scoped_denominators() -> None:
    forms = ("US", "us", "USA", "840", "United States", "United States of America")

    assert {normalize_country_code(value) for value in forms} == {"US"}
    assert iso2_to_iso3("840") == "USA"
    assert iso2_to_numeric("USA") == "840"
    assert country_region("US") == "North America"
    assert "US" in all_country_codes()
    assert "US" not in country_scope_members("core_blocking")
    assert "US" not in country_scope_members("regional_extended")
    assert "US" not in country_scope_members("full_europe")


def test_wdi_annual_rows_normalize_usa_to_us_without_accepting_another_country() -> None:
    from polisyos.data_requirement import (
        DataQualityMinimums,
        DataRequirementScope,
        DataRequirementSpec,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        _validate_wdi_requirement_rows,
    )

    requirement = DataRequirementSpec(
        requirement_id="data-requirement:country-code-test",
        claim_id="claim:country-code-test",
        required_data_families=("wdi_nominal_gdp_annual",),
        scope=DataRequirementScope(
            population="national_economy",
            geography="US",
            time="2022",
            jurisdiction="US",
        ),
        recency_horizon="P180D",
        quality_minima=DataQualityMinimums(min_completeness=1.0),
        missingness_tolerance=0.0,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("construct:economic.gdp",),
        authority_profile_refs=("authority_profile.research",),
    )
    row = {
        "country_code": "USA",
        "year": 2022,
        "indicator_id": "NY.GDP.MKTP.CD",
        "value": 1.0,
    }

    _validate_wdi_requirement_rows(
        [row],
        requirement=requirement,
        geography="US",
        start="2022",
        end="2022",
        dataset_id="NY.GDP.MKTP.CD",
    )

    with pytest.raises(
        FabricMeasurementRootBindingError,
        match="measurement_requirement_scope_mismatch",
    ):
        _validate_wdi_requirement_rows(
            [{**row, "country_code": "DEU"}],
            requirement=requirement,
            geography="US",
            start="2022",
            end="2022",
            dataset_id="NY.GDP.MKTP.CD",
        )
