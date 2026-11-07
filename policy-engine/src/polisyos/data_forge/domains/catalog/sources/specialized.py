"""Specialized indicator, SPARQL, and rolling-window source modules."""

from __future__ import annotations

from ..registry import _catalog_source_module

WHO_SOURCE = _catalog_source_module("who")
UNESCO_UIS_SOURCE = _catalog_source_module("unesco_uis")
UNPD_SOURCE = _catalog_source_module("unpd")
WIKIDATA_SPARQL_SOURCE = _catalog_source_module("wikidata_sparql")
DBPEDIA_SPARQL_SOURCE = _catalog_source_module("dbpedia_sparql")
OPENAQ_V2_SOURCE = _catalog_source_module("openaq_v2")
OPEN_METEO_SOURCE = _catalog_source_module("open_meteo")
EIA_API_SOURCE = _catalog_source_module("eia_api")

SPECIALIZED_CATALOG_SOURCE_MODULES = (
    WHO_SOURCE,
    UNESCO_UIS_SOURCE,
    UNPD_SOURCE,
    WIKIDATA_SPARQL_SOURCE,
    DBPEDIA_SPARQL_SOURCE,
    OPENAQ_V2_SOURCE,
    OPEN_METEO_SOURCE,
    EIA_API_SOURCE,
)


__all__ = [
    "DBPEDIA_SPARQL_SOURCE",
    "EIA_API_SOURCE",
    "OPENAQ_V2_SOURCE",
    "OPEN_METEO_SOURCE",
    "SPECIALIZED_CATALOG_SOURCE_MODULES",
    "UNESCO_UIS_SOURCE",
    "UNPD_SOURCE",
    "WHO_SOURCE",
    "WIKIDATA_SPARQL_SOURCE",
]
