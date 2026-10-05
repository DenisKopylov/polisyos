"""Compatibility exports for SDMX-family catalog sources.

Source metadata is owned by ``source_registry.yaml`` and projected through
the canonical Data Forge registry parser.
"""

from __future__ import annotations

from ..registry import _catalog_source_module as _source

OECD_SOURCE = _source("oecd")
IMF_SOURCE = _source("imf")
ECB_SOURCE = _source("ecb")
UNDATA_SOURCE = _source("undata")
EUROSTAT_SOURCE = _source("eurostat")
ILO_SOURCE = _source("ilo")
UNICEF_SOURCE = _source("unicef")

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
