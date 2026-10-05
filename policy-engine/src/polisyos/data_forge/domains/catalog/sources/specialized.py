"""Compatibility exports for specialized catalog sources.

Source metadata is owned by ``source_registry.yaml`` and projected through
the canonical Data Forge registry parser.
"""

from __future__ import annotations

from ..registry import _catalog_source_module as _source

WHO_SOURCE = _source("who")
UNESCO_UIS_SOURCE = _source("unesco_uis")
UNPD_SOURCE = _source("unpd")
WIKIDATA_SPARQL_SOURCE = _source("wikidata_sparql")
DBPEDIA_SPARQL_SOURCE = _source("dbpedia_sparql")
OPENAQ_V2_SOURCE = _source("openaq_v2")
OPEN_METEO_SOURCE = _source("open_meteo")
EIA_API_SOURCE = _source("eia_api")

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
