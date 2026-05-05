"""Specialized indicator, SPARQL, and rolling-window source modules."""

from __future__ import annotations

from ._factory import source

WHO_SOURCE = source(
    "who",
    family="who",
    wave="D",
    endpoint="https://ghoapi.azureedge.net/api/Indicator",
    connector_id="who.indicators",
    profile_id="who_gho",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="annual",
    metrics_required=True,
)
UNESCO_UIS_SOURCE = source(
    "unesco_uis",
    family="uis",
    wave="D",
    endpoint="https://api.uis.unesco.org/api/public/definitions/indicators",
    connector_id="unesco_uis.data",
    profile_id="unesco_uis_public",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="annual",
    metrics_required=True,
)
UNPD_SOURCE = source(
    "unpd",
    family="unpd",
    wave="D",
    endpoint="https://population.un.org/dataportalapi/api/v1/indicators/?pageSize=200",
    connector_id="unpd.data",
    profile_id="unpd_dataportal",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="annual",
    metrics_required=True,
)
WIKIDATA_SPARQL_SOURCE = source(
    "wikidata_sparql",
    family="sparql",
    wave="D",
    endpoint="https://query.wikidata.org/sparql",
    connector_id="sparql.endpoint",
    profile_id="wikidata_sparql",
    run_lane="enrichment",
    update_frequency="weekly",
)
DBPEDIA_SPARQL_SOURCE = source(
    "dbpedia_sparql",
    family="sparql",
    wave="D",
    endpoint="https://dbpedia.org/sparql",
    connector_id="sparql.endpoint",
    profile_id="dbpedia_sparql",
    run_lane="enrichment",
    update_frequency="weekly",
)
OPENAQ_V2_SOURCE = source(
    "openaq_v2",
    family="rest",
    wave="D",
    endpoint="https://api.openaq.org/v2/measurements",
    connector_id="rest.json",
    profile_id="openaq_v2",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="daily",
    history_policy="rolling_window",
    allow_manual_backfill=True,
    default_lookback_days=90,
    max_rows_per_snapshot=750_000,
    max_bytes_per_snapshot=157_286_400,
)
OPEN_METEO_SOURCE = source(
    "open_meteo",
    family="rest",
    wave="D",
    endpoint="https://api.open-meteo.com/v1/forecast",
    connector_id="rest.json",
    profile_id="open_meteo",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="daily",
    history_policy="rolling_window",
    allow_manual_backfill=True,
    default_lookback_days=30,
    max_rows_per_snapshot=500_000,
    max_bytes_per_snapshot=104_857_600,
)
EIA_API_SOURCE = source(
    "eia_api",
    family="rest",
    wave="D",
    endpoint="https://api.eia.gov/v2",
    connector_id="rest.json",
    profile_id="eia_api",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="monthly",
    history_policy="rolling_window",
    allow_manual_backfill=True,
    default_lookback_days=730,
    max_rows_per_snapshot=1_000_000,
    max_bytes_per_snapshot=262_144_000,
)

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
