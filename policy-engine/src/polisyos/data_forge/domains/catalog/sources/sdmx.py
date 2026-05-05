"""SDMX-family catalog source modules."""

from __future__ import annotations

from ._factory import source

OECD_SOURCE = source(
    "oecd",
    family="sdmx",
    wave="A",
    endpoint="https://sdmx.oecd.org/public/rest/dataflow",
    connector_id="sdmx.source",
    profile_id="oecd_sdmx",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="quarterly",
    metrics_required=True,
)
IMF_SOURCE = source(
    "imf",
    family="sdmx",
    wave="A",
    endpoint="https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/dataflow/IMF",
    connector_id="sdmx.source",
    profile_id="imf_sdmx",
    update_frequency="monthly",
)
ECB_SOURCE = source(
    "ecb",
    family="sdmx",
    wave="A",
    endpoint="https://data-api.ecb.europa.eu/service/dataflow",
    connector_id="sdmx.source",
    profile_id="ecb_sdmx",
    update_frequency="daily",
)
UNDATA_SOURCE = source(
    "undata",
    family="undata",
    wave="A",
    endpoint="https://data.un.org/ws/rest/dataflow/",
    connector_id="sdmx.source",
    profile_id="unsd_sdmx",
    update_frequency="annual",
)
EUROSTAT_SOURCE = source(
    "eurostat",
    family="sdmx",
    wave="A",
    endpoint="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all/latest?detail=allstubs",
    connector_id="eurostat.data",
    profile_id="eurostat_public",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="monthly",
    metrics_required=True,
)
ILO_SOURCE = source(
    "ilo",
    family="sdmx",
    wave="D",
    endpoint="https://sdmx.ilo.org/rest/dataflow/ILO",
    connector_id="sdmx.source",
    profile_id="ilo_sdmx",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="monthly",
    metrics_required=True,
)
UNICEF_SOURCE = source(
    "unicef",
    family="sdmx",
    wave="D",
    endpoint="https://sdmx.data.unicef.org/ws/rest/dataflow/UNICEF",
    connector_id="sdmx.source",
    enabled=False,
    update_frequency="annual",
)

SDMX_CATALOG_SOURCE_MODULES = (
    OECD_SOURCE,
    IMF_SOURCE,
    ECB_SOURCE,
    UNDATA_SOURCE,
    EUROSTAT_SOURCE,
    ILO_SOURCE,
    UNICEF_SOURCE,
)

__all__ = [
    "ECB_SOURCE",
    "EUROSTAT_SOURCE",
    "ILO_SOURCE",
    "IMF_SOURCE",
    "OECD_SOURCE",
    "SDMX_CATALOG_SOURCE_MODULES",
    "UNDATA_SOURCE",
    "UNICEF_SOURCE",
]
