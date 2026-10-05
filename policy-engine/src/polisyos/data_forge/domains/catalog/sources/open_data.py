"""Compatibility exports for open-data portal catalog sources.

Source metadata is owned by ``source_registry.yaml`` and projected through
the canonical Data Forge registry parser.
"""

from __future__ import annotations

from ..registry import _catalog_source_module as _source

DATA_GOV_UA_BROAD_SOURCE = _source("data_gov_ua_broad")
DATA_GOV_UA_EXEC_SOURCE = _source("data_gov_ua_exec")
DATA_GOV_RO_BROAD_SOURCE = _source("data_gov_ro_broad")
DATA_GOV_RO_EXEC_SOURCE = _source("data_gov_ro_exec")
DATA_GOV_MD_BROAD_SOURCE = _source("data_gov_md_broad")
DATA_GOV_MD_EXEC_SOURCE = _source("data_gov_md_exec")
DATA_GOV_PL_BROAD_SOURCE = _source("data_gov_pl_broad")
DATA_GOV_PL_EXEC_SOURCE = _source("data_gov_pl_exec")
DATA_GOV_UK_SOURCE = _source("data_gov_uk")
DATA_GOV_US_SOURCE = _source("data_gov_us")
OPENDATASOFT_PUBLIC_SOURCE = _source("opendatasoft_public")
PARIS_OPENDATA_BROAD_SOURCE = _source("paris_opendata_broad")
PARIS_OPENDATA_EXEC_SOURCE = _source("paris_opendata_exec")
NYC_OPENDATA_SOURCE = _source("nyc_opendata")
NYC_OPENDATA_EXEC_SOURCE = _source("nyc_opendata_exec")
CHICAGO_OPENDATA_SOURCE = _source("chicago_opendata")
CHICAGO_OPENDATA_EXEC_SOURCE = _source("chicago_opendata_exec")

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
