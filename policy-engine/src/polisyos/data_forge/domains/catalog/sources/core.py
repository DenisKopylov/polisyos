"""Core empirical catalog source modules."""

from __future__ import annotations

from ..registry import _catalog_source_module

WORLDBANK_SOURCE = _catalog_source_module("worldbank")
WVS_SOURCE = _catalog_source_module("wvs")
UKONS_SOURCE = _catalog_source_module("ukons")

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
