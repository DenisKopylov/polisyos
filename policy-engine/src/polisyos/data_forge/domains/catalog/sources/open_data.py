"""Open-data portal catalog source modules."""

from __future__ import annotations

from ._factory import source

DATA_GOV_UA_BROAD_SOURCE = source(
    "data_gov_ua_broad",
    family="ckan",
    wave="C",
    endpoint="https://data.gov.ua/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_ua",
    update_frequency="irregular",
)
DATA_GOV_UA_EXEC_SOURCE = source(
    "data_gov_ua_exec",
    family="ckan",
    wave="C",
    endpoint="https://data.gov.ua/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_ua",
    execution_tier="fetchable",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="irregular",
    seed_from="data_gov_ua_broad",
    require_curated_resources=True,
)
DATA_GOV_RO_BROAD_SOURCE = source(
    "data_gov_ro_broad",
    family="ckan",
    wave="C",
    endpoint="https://data.gov.ro/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_ro",
    update_frequency="irregular",
)
DATA_GOV_RO_EXEC_SOURCE = source(
    "data_gov_ro_exec",
    family="ckan",
    wave="C",
    endpoint="https://data.gov.ro/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_ro",
    execution_tier="fetchable",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="irregular",
    seed_from="data_gov_ro_broad",
    require_curated_resources=True,
)
DATA_GOV_MD_BROAD_SOURCE = source(
    "data_gov_md_broad",
    family="ckan",
    wave="C",
    endpoint="https://dataset.gov.md/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_md",
    update_frequency="irregular",
)
DATA_GOV_MD_EXEC_SOURCE = source(
    "data_gov_md_exec",
    family="ckan",
    wave="C",
    endpoint="https://dataset.gov.md/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_md",
    execution_tier="fetchable",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="irregular",
    seed_from="data_gov_md_broad",
    require_curated_resources=True,
)
DATA_GOV_PL_BROAD_SOURCE = source(
    "data_gov_pl_broad",
    family="poland_api",
    wave="C",
    endpoint="https://api.dane.gov.pl/1.4/datasets",
    connector_id="rest.json",
    profile_id="data_gov_pl",
    update_frequency="irregular",
)
DATA_GOV_PL_EXEC_SOURCE = source(
    "data_gov_pl_exec",
    family="poland_api",
    wave="C",
    endpoint="https://api.dane.gov.pl/1.4/datasets",
    connector_id="rest.json",
    profile_id="data_gov_pl",
    execution_tier="fetchable",
    run_lane="empirical",
    publish_blocking=True,
    update_frequency="irregular",
    seed_from="data_gov_pl_broad",
    require_curated_resources=True,
)
DATA_GOV_UK_SOURCE = source(
    "data_gov_uk",
    family="ckan",
    wave="C",
    endpoint="https://data.gov.uk/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_uk",
    enabled=False,
    update_frequency="irregular",
)
DATA_GOV_US_SOURCE = source(
    "data_gov_us",
    family="ckan",
    wave="C",
    endpoint="https://catalog.data.gov/api/3/action/package_search",
    connector_id="ckan.resource",
    profile_id="data_gov_us",
    enabled=False,
    update_frequency="irregular",
)
OPENDATASOFT_PUBLIC_SOURCE = source(
    "opendatasoft_public",
    family="opendatasoft",
    wave="D",
    endpoint="https://public.opendatasoft.com",
    connector_id="opendatasoft.ods",
    profile_id="opendatasoft_public",
    update_frequency="weekly",
)
PARIS_OPENDATA_BROAD_SOURCE = source(
    "paris_opendata_broad",
    family="opendatasoft",
    wave="D",
    endpoint="https://opendata.paris.fr",
    connector_id="opendatasoft.ods",
    profile_id="paris_opendata",
    update_frequency="weekly",
)
PARIS_OPENDATA_EXEC_SOURCE = source(
    "paris_opendata_exec",
    family="opendatasoft",
    wave="D",
    endpoint="https://opendata.paris.fr",
    connector_id="opendatasoft.ods",
    profile_id="paris_opendata",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="weekly",
    seed_from="paris_opendata_broad",
    require_curated_resources=True,
)
NYC_OPENDATA_SOURCE = source(
    "nyc_opendata",
    family="socrata",
    wave="D",
    endpoint="https://data.cityofnewyork.us",
    connector_id="socrata.soda",
    profile_id="nyc_opendata",
    update_frequency="weekly",
)
NYC_OPENDATA_EXEC_SOURCE = source(
    "nyc_opendata_exec",
    family="socrata",
    wave="D",
    endpoint="https://data.cityofnewyork.us",
    connector_id="socrata.soda",
    profile_id="nyc_opendata",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="weekly",
    seed_from="nyc_opendata",
    require_curated_resources=True,
)
CHICAGO_OPENDATA_SOURCE = source(
    "chicago_opendata",
    family="socrata",
    wave="D",
    endpoint="https://data.cityofchicago.org",
    connector_id="socrata.soda",
    profile_id="chicago_opendata",
    update_frequency="weekly",
)
CHICAGO_OPENDATA_EXEC_SOURCE = source(
    "chicago_opendata_exec",
    family="socrata",
    wave="D",
    endpoint="https://data.cityofchicago.org",
    connector_id="socrata.soda",
    profile_id="chicago_opendata",
    execution_tier="fetchable",
    run_lane="empirical",
    update_frequency="weekly",
    seed_from="chicago_opendata",
    require_curated_resources=True,
)

OPEN_DATA_CATALOG_SOURCE_MODULES = (
    DATA_GOV_UA_BROAD_SOURCE,
    DATA_GOV_UA_EXEC_SOURCE,
    DATA_GOV_RO_BROAD_SOURCE,
    DATA_GOV_RO_EXEC_SOURCE,
    DATA_GOV_MD_BROAD_SOURCE,
    DATA_GOV_MD_EXEC_SOURCE,
    DATA_GOV_PL_BROAD_SOURCE,
    DATA_GOV_PL_EXEC_SOURCE,
    DATA_GOV_UK_SOURCE,
    DATA_GOV_US_SOURCE,
    OPENDATASOFT_PUBLIC_SOURCE,
    PARIS_OPENDATA_BROAD_SOURCE,
    PARIS_OPENDATA_EXEC_SOURCE,
    NYC_OPENDATA_SOURCE,
    NYC_OPENDATA_EXEC_SOURCE,
    CHICAGO_OPENDATA_SOURCE,
    CHICAGO_OPENDATA_EXEC_SOURCE,
)

__all__ = [
    "CHICAGO_OPENDATA_EXEC_SOURCE",
    "CHICAGO_OPENDATA_SOURCE",
    "DATA_GOV_MD_BROAD_SOURCE",
    "DATA_GOV_MD_EXEC_SOURCE",
    "DATA_GOV_PL_BROAD_SOURCE",
    "DATA_GOV_PL_EXEC_SOURCE",
    "DATA_GOV_RO_BROAD_SOURCE",
    "DATA_GOV_RO_EXEC_SOURCE",
    "DATA_GOV_UA_BROAD_SOURCE",
    "DATA_GOV_UA_EXEC_SOURCE",
    "DATA_GOV_UK_SOURCE",
    "DATA_GOV_US_SOURCE",
    "NYC_OPENDATA_EXEC_SOURCE",
    "NYC_OPENDATA_SOURCE",
    "OPENDATASOFT_PUBLIC_SOURCE",
    "OPEN_DATA_CATALOG_SOURCE_MODULES",
    "PARIS_OPENDATA_BROAD_SOURCE",
    "PARIS_OPENDATA_EXEC_SOURCE",
]
