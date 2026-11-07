"""SDMX-family catalog source modules."""

from __future__ import annotations

from ..registry import _catalog_source_module

OECD_SOURCE = _catalog_source_module("oecd")
IMF_SOURCE = _catalog_source_module("imf")
ECB_SOURCE = _catalog_source_module("ecb")
UNDATA_SOURCE = _catalog_source_module("undata")
EUROSTAT_SOURCE = _catalog_source_module("eurostat")
ILO_SOURCE = _catalog_source_module("ilo")
UNICEF_SOURCE = _catalog_source_module("unicef")

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
