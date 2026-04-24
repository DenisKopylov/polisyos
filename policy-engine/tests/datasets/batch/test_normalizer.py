"""Tests for DCAT normalization (datasets/batch/normalizer.py)."""

from __future__ import annotations

from polisyos.datasets.batch.normalizer import (
    extract_variables,
    map_to_polisyos_metrics,
    normalize_ckan,
    normalize_to_dcat,
    normalize_worldbank,
)


def test_extract_variables_from_title() -> None:
    raw = {"title": "GDP per capita annual data", "notes": "", "description": ""}
    variables = extract_variables(raw)
    assert "GDP" in variables


def test_extract_variables_from_extras() -> None:
    raw = {
        "title": "",
        "notes": "",
        "description": "",
        "extras": [{"key": "indicator", "value": "NY.GDP.MKTP.CD"}],
    }
    variables = extract_variables(raw)
    assert "NY.GDP.MKTP.CD" in variables


def test_extract_variables_from_indicator_id() -> None:
    raw = {"title": "", "notes": "", "description": "", "indicator_id": "SP.POP.TOTL"}
    variables = extract_variables(raw)
    assert "SP.POP.TOTL" in variables


def test_map_to_polisyos_metrics_keyword_match() -> None:
    metrics_map = {
        "unemployment_rate": {
            "keywords": ["unemployment", "jobless"],
            "worldbank_indicators": ["SL.UEM.TOTL.ZS"],
        },
    }
    raw = {"title": "Unemployment rate by country", "notes": "", "description": ""}
    matched = map_to_polisyos_metrics(raw, metrics_map)
    assert "unemployment_rate" in matched


def test_map_to_polisyos_metrics_indicator_code_match() -> None:
    metrics_map = {
        "gdp": {
            "keywords": ["GDP"],
            "worldbank_indicators": ["NY.GDP.MKTP.CD"],
        },
    }
    raw = {
        "title": "Some indicator",
        "notes": "",
        "description": "",
        "indicator_id": "NY.GDP.MKTP.CD",
    }
    matched = map_to_polisyos_metrics(raw, metrics_map)
    assert "gdp" in matched


def test_map_to_polisyos_metrics_uses_heuristic_aliases_when_map_present() -> None:
    metrics_map = {
        "health_outcomes": {
            "keywords": [],
            "worldbank_indicators": [],
        },
        "education_outcomes": {
            "keywords": [],
            "worldbank_indicators": [],
        },
    }
    raw = {
        "IndicatorName": "Life expectancy at birth",
        "description": "Healthy life expectancy by sex",
    }
    matched = map_to_polisyos_metrics(raw, metrics_map)
    assert "health_outcomes" in matched


def test_map_to_polisyos_metrics_keeps_harvest_metric_candidates() -> None:
    metrics_map = {
        "unemployment_rate": {"keywords": []},
        "gdp_per_capita": {"keywords": []},
    }
    raw = {
        "title": "Opaque SDMX dataflow title",
        "harvest_metric_candidates": ["unemployment_rate"],
    }
    matched = map_to_polisyos_metrics(raw, metrics_map)
    assert "unemployment_rate" in matched


def test_map_to_polisyos_metrics_empty_map() -> None:
    assert map_to_polisyos_metrics({"title": "GDP"}, None) == []
    assert map_to_polisyos_metrics({"title": "GDP"}, {}) == []


def test_normalize_ckan_basic() -> None:
    raw = {
        "id": "test-123",
        "title": "Test Dataset",
        "notes": "A test dataset about GDP",
        "organization": {"name": "test-org"},
        "resources": [
            {"id": "r1", "url": "http://example.com/data.csv", "format": "CSV", "name": "data.csv"},
        ],
        "tags": [{"name": "economics"}],
    }
    record = normalize_ckan(raw, "test_portal")
    assert record.title == "Test Dataset"
    assert record.publisher == "test-org"
    assert record.source_portal == "test_portal"
    assert len(record.distributions) == 1
    assert record.distributions[0].format == "CSV"
    assert record.distributions[0].connector_type == "ckan.resource"
    assert record.distributions[0].source_locator == "test-123/r1"
    assert record.distributions[0].parser_supported is True
    assert "economics" in record.themes
    assert "GDP" in record.variables


def test_normalize_ckan_marks_xlsx_parser_supported() -> None:
    raw = {
        "id": "budget-123",
        "title": "Community budget",
        "notes": "Budget table",
        "organization": {"name": "city"},
        "resources": [
            {
                "id": "r1",
                "url": "http://example.com/budget.xlsx",
                "format": "XLSX",
                "name": "budget.xlsx",
            },
        ],
        "tags": [{"name": "budget"}],
    }
    record = normalize_ckan(raw, "data_gov_ua_exec")
    assert record.distributions[0].format == "XLSX"
    assert record.distributions[0].parser_supported is True


def test_normalize_worldbank_basic() -> None:
    raw = {
        "id": "NY.GDP.MKTP.CD",
        "name": "GDP (current US$)",
        "sourceNote": "GDP at purchaser's prices",
        "source": {"value": "World Development Indicators"},
    }
    record = normalize_worldbank(raw)
    assert record.title == "GDP (current US$)"
    assert record.publisher == "World Bank"
    assert record.source_portal == "worldbank"
    assert "NY.GDP.MKTP.CD" in record.variables
    assert len(record.distributions) == 1
    assert record.distributions[0].connector_type == "worldbank.wdi"
    assert record.distributions[0].source_locator == "NY.GDP.MKTP.CD"
    assert record.execution_tier == "catalog"
    assert record.coverage.granularity == "annual"
    assert record.quality.execution_readiness_score > 0.0


def test_normalize_to_dcat_routes_by_connector_type() -> None:
    raw = {"id": "SP.POP.TOTL", "name": "Population, total", "sourceNote": ""}
    record = normalize_to_dcat(raw, "worldbank", "worldbank")
    assert record.publisher == "World Bank"
    assert record.distributions[0].connector_type == "worldbank.wdi"

    raw_sdmx = {
        "id": "une_rt_a",
        "name": "Unemployment rate",
        "description": "",
        "agency_id": "ESTAT",
    }
    record_sdmx = normalize_to_dcat(raw_sdmx, "eurostat", "sdmx")
    assert record_sdmx.publisher == "ESTAT"
    assert record_sdmx.distributions[0].connector_type == "sdmx.source"


def test_normalize_to_dcat_canonicalizes_indicator_api_connectors() -> None:
    who_record = normalize_to_dcat(
        {"IndicatorCode": "WHOSIS_000001", "IndicatorName": "Life expectancy"},
        "who",
        "who",
    )
    assert who_record.distributions[0].connector_type == "who.indicators"
    assert who_record.distributions[0].source_locator == "WHOSIS_000001"

    unpd_record = normalize_to_dcat(
        {
            "id": 1,
            "name": "Contraceptive prevalence",
            "sourceStartYear": 1970,
            "sourceEndYear": 2030,
        },
        "unpd",
        "unpd",
    )
    assert unpd_record.distributions[0].connector_type == "unpd.data"
    assert unpd_record.distributions[0].source_locator == "1"
    assert unpd_record.access.auth_required is True

    uis_record = normalize_to_dcat(
        {
            "indicatorCode": "200101",
            "name": "Total population",
            "dataAvailability": {"timeLine": {"min": 1970, "max": 2025}},
        },
        "unesco_uis",
        "unesco_uis",
    )
    assert uis_record.distributions[0].connector_type == "unesco_uis.data"
    assert uis_record.distributions[0].source_locator == "200101"
    assert uis_record.coverage.time_start == "1970"


def test_normalize_to_dcat_handles_poland_open_data_catalog_row() -> None:
    record = normalize_to_dcat(
        {
            "id": "pl-budget-1",
            "title": "Budzet lokalny miasta",
            "notes": "Dochody i wydatki budzetowe",
            "keywords": ["budzet", "samorzad"],
            "category": "Finanse publiczne",
            "categories": ["Samorzad"],
            "formats": ["XLSX"],
            "organization": {"name": "institution:26"},
            "resources_related_url": "https://api.dane.gov.pl/1.4/datasets/1/resources",
            "spatial": "POL",
            "modified": "2024-03-19T19:14:09Z",
        },
        "data_gov_pl",
        "rest",
    )
    assert record.publisher == "institution:26"
    assert record.source_portal == "data_gov_pl"
    assert record.distributions[0].connector_type == "rest.json"
    assert (
        record.distributions[0].source_locator == "https://api.dane.gov.pl/1.4/datasets/1/resources"
    )
    assert record.coverage.countries == ["POL"]
