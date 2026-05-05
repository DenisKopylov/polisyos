"""Core empirical catalog source modules."""

from __future__ import annotations

from ._factory import source

WORLDBANK_SOURCE = source(
    "worldbank",
    family="worldbank",
    wave="B",
    endpoint="https://api.worldbank.org/v2/indicator",
    connector_id="worldbank.wdi",
    profile_id="worldbank_wdi",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="annual",
    metrics_required=True,
)
WVS_SOURCE = source(
    "wvs",
    family="wvs",
    wave="B",
    endpoint="https://www.worldvaluessurvey.org/WVSDocumentationWVL.jsp",
    connector_id="wvs.wave7",
    profile_id="wvs_wave7",
    execution_tier="transport_ready",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="wave",
    metrics_required=True,
)
UKONS_SOURCE = source(
    "ukons",
    family="ukons",
    wave="B",
    endpoint="https://api.beta.ons.gov.uk/v1/datasets",
    connector_id="ukons.datasets",
    profile_id="ukons_public",
    update_frequency="monthly",
)

CORE_EMPIRICAL_CATALOG_SOURCE_MODULES = (
    WORLDBANK_SOURCE,
    WVS_SOURCE,
    UKONS_SOURCE,
)

__all__ = [
    "CORE_EMPIRICAL_CATALOG_SOURCE_MODULES",
    "UKONS_SOURCE",
    "WORLDBANK_SOURCE",
    "WVS_SOURCE",
]
