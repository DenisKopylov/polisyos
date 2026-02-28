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
    raw = {"title": "Some indicator", "notes": "", "description": "", "indicator_id": "NY.GDP.MKTP.CD"}
    matched = map_to_polisyos_metrics(raw, metrics_map)
    assert "gdp" in matched


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
    assert "economics" in record.themes
    assert "GDP" in record.variables


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
    assert record.distributions[0].connector_type == "worldbank"


def test_normalize_to_dcat_routes_by_connector_type() -> None:
    raw = {"id": "SP.POP.TOTL", "name": "Population, total", "sourceNote": ""}
    record = normalize_to_dcat(raw, "worldbank", "worldbank")
    assert record.publisher == "World Bank"

    raw_sdmx = {"id": "une_rt_a", "name": "Unemployment rate", "description": "", "agency_id": "ESTAT"}
    record_sdmx = normalize_to_dcat(raw_sdmx, "eurostat", "sdmx")
    assert record_sdmx.publisher == "ESTAT"
