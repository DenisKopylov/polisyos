"""Compatibility exports for core empirical catalog sources.

Source metadata is owned by ``source_registry.yaml`` and projected through
the canonical Data Forge registry parser.
"""

from __future__ import annotations

from ..registry import _catalog_source_module as _source

WORLDBANK_SOURCE = _source("worldbank")
WVS_SOURCE = _source("wvs")
UKONS_SOURCE = _source("ukons")

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
