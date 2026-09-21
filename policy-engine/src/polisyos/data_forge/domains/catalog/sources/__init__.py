"""Static per-source catalog modules for Data Forge."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from ..source_modules import CatalogSourceModuleSpec

from .core import UKONS_SOURCE, WORLDBANK_SOURCE, WVS_SOURCE
from .open_data import (
    CHICAGO_OPENDATA_EXEC_SOURCE,
    CHICAGO_OPENDATA_SOURCE,
    DATA_GOV_MD_BROAD_SOURCE,
    DATA_GOV_MD_EXEC_SOURCE,
    DATA_GOV_PL_BROAD_SOURCE,
    DATA_GOV_PL_EXEC_SOURCE,
    DATA_GOV_RO_BROAD_SOURCE,
    DATA_GOV_RO_EXEC_SOURCE,
    DATA_GOV_UA_BROAD_SOURCE,
    DATA_GOV_UA_EXEC_SOURCE,
    DATA_GOV_UK_SOURCE,
    DATA_GOV_US_SOURCE,
    NYC_OPENDATA_EXEC_SOURCE,
    NYC_OPENDATA_SOURCE,
    OPENDATASOFT_PUBLIC_SOURCE,
    PARIS_OPENDATA_BROAD_SOURCE,
    PARIS_OPENDATA_EXEC_SOURCE,
)
from .sdmx import (
    ECB_SOURCE,
    EUROSTAT_SOURCE,
    ILO_SOURCE,
    IMF_SOURCE,
    OECD_SOURCE,
    UNDATA_SOURCE,
    UNICEF_SOURCE,
)
from .specialized import (
    DBPEDIA_SPARQL_SOURCE,
    EIA_API_SOURCE,
    OPEN_METEO_SOURCE,
    OPENAQ_V2_SOURCE,
    UNESCO_UIS_SOURCE,
    UNPD_SOURCE,
    WHO_SOURCE,
    WIKIDATA_SPARQL_SOURCE,
)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _registry_filter_overlays() -> dict[str, dict[str, object]]:
    """Load rich filter fields from the canonical catalog source registry."""
    registry_path = Path(__file__).resolve().parent.parent / "source_registry.yaml"
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        return {}

    overlays: dict[str, dict[str, object]] = {}
    for row in payload["sources"]:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("name") or "").strip()
        if not source_id:
            continue
        overlays[source_id] = {
            "agency_prefix": str(row.get("agency_prefix") or "").strip(),
            "agency_allowlist": _string_tuple(row.get("agency_allowlist")),
            "exclude_agencies": _string_tuple(row.get("exclude_agencies")),
            "format_allowlist": tuple(
                item.upper() for item in _string_tuple(row.get("format_allowlist"))
            ),
            "format_denylist": tuple(
                item.upper() for item in _string_tuple(row.get("format_denylist"))
            ),
            "keyword_allowlist": tuple(
                item.lower() for item in _string_tuple(row.get("keyword_allowlist"))
            ),
            "keyword_denylist": tuple(
                item.lower() for item in _string_tuple(row.get("keyword_denylist"))
            ),
        }
    return overlays


def _project_registry_filters(
    modules: tuple[CatalogSourceModuleSpec, ...],
) -> tuple[CatalogSourceModuleSpec, ...]:
    overlays = _registry_filter_overlays()
    return tuple(
        module.model_copy(update=overlays.get(module.source_id, {})) for module in modules
    )


# The batch registry and its consumers remain DFI-02 compatibility_pending.
ALL_CATALOG_SOURCE_MODULES = (
    OECD_SOURCE,
    IMF_SOURCE,
    ECB_SOURCE,
    UNDATA_SOURCE,
    EUROSTAT_SOURCE,
    WORLDBANK_SOURCE,
    WVS_SOURCE,
    UKONS_SOURCE,
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
    ILO_SOURCE,
    UNICEF_SOURCE,
    WHO_SOURCE,
    UNESCO_UIS_SOURCE,
    UNPD_SOURCE,
    OPENDATASOFT_PUBLIC_SOURCE,
    PARIS_OPENDATA_BROAD_SOURCE,
    PARIS_OPENDATA_EXEC_SOURCE,
    NYC_OPENDATA_SOURCE,
    NYC_OPENDATA_EXEC_SOURCE,
    CHICAGO_OPENDATA_SOURCE,
    CHICAGO_OPENDATA_EXEC_SOURCE,
    WIKIDATA_SPARQL_SOURCE,
    DBPEDIA_SPARQL_SOURCE,
    OPENAQ_V2_SOURCE,
    OPEN_METEO_SOURCE,
    EIA_API_SOURCE,
)
ALL_CATALOG_SOURCE_MODULES = _project_registry_filters(ALL_CATALOG_SOURCE_MODULES)

__all__ = [
    "ALL_CATALOG_SOURCE_MODULES",
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
    "DBPEDIA_SPARQL_SOURCE",
    "ECB_SOURCE",
    "EIA_API_SOURCE",
    "EUROSTAT_SOURCE",
    "ILO_SOURCE",
    "IMF_SOURCE",
    "NYC_OPENDATA_EXEC_SOURCE",
    "NYC_OPENDATA_SOURCE",
    "OECD_SOURCE",
    "OPENAQ_V2_SOURCE",
    "OPENDATASOFT_PUBLIC_SOURCE",
    "OPEN_METEO_SOURCE",
    "PARIS_OPENDATA_BROAD_SOURCE",
    "PARIS_OPENDATA_EXEC_SOURCE",
    "UKONS_SOURCE",
    "UNDATA_SOURCE",
    "UNESCO_UIS_SOURCE",
    "UNICEF_SOURCE",
    "UNPD_SOURCE",
    "WHO_SOURCE",
    "WIKIDATA_SPARQL_SOURCE",
    "WORLDBANK_SOURCE",
    "WVS_SOURCE",
]
