"""Catalog asset mirror contracts for Phase 0C."""

from __future__ import annotations

from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

CATALOG_RAW_SOURCES_KEY = AssetKey.from_parts("catalog", "sources", "raw")
CATALOG_SOURCE_MODULES_KEY = AssetKey.from_parts("catalog", "sources", "modules")
CATALOG_NORMALIZED_DATASETS_KEY = AssetKey.from_parts("catalog", "datasets", "normalized")
CATALOG_SOURCE_PREFLIGHT_KEY = AssetKey.from_parts("catalog", "sources", "preflight")
CATALOG_OBSERVATIONS_KEY = AssetKey.from_parts("catalog", "observations")
CATALOG_INDEX_KEY = AssetKey.from_parts("catalog", "index")
CATALOG_READINESS_KEY = AssetKey.from_parts("catalog", "readiness")

CATALOG_ASSET_GROUP = AssetGroup.from_specs(
    "catalog",
    (
        AssetSpec(
            key=CATALOG_RAW_SOURCES_KEY,
            owner="team-data-forge",
            schema_id="catalog.sources.raw",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=CATALOG_SOURCE_MODULES_KEY,
            deps=(CATALOG_RAW_SOURCES_KEY,),
            owner="team-data-forge",
            schema_id="catalog.sources.modules",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=CATALOG_NORMALIZED_DATASETS_KEY,
            deps=(CATALOG_SOURCE_MODULES_KEY,),
            owner="team-data-forge",
            schema_id="catalog.datasets.normalized",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=CATALOG_SOURCE_PREFLIGHT_KEY,
            deps=(CATALOG_SOURCE_MODULES_KEY, CATALOG_NORMALIZED_DATASETS_KEY),
            owner="team-data-forge",
            schema_id="catalog.sources.preflight",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=CATALOG_OBSERVATIONS_KEY,
            deps=(CATALOG_NORMALIZED_DATASETS_KEY, CATALOG_SOURCE_PREFLIGHT_KEY),
            owner="team-data-forge",
            schema_id="catalog.observations",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=CATALOG_INDEX_KEY,
            deps=(CATALOG_NORMALIZED_DATASETS_KEY, CATALOG_OBSERVATIONS_KEY),
            owner="team-data-forge",
            schema_id="catalog.index",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=CATALOG_READINESS_KEY,
            deps=(CATALOG_INDEX_KEY, CATALOG_SOURCE_PREFLIGHT_KEY),
            owner="team-data-forge",
            schema_id="catalog.consumer.readiness",
            retention=RetentionClass.HOT,
        ),
    ),
)

__all__ = [
    "CATALOG_ASSET_GROUP",
    "CATALOG_INDEX_KEY",
    "CATALOG_NORMALIZED_DATASETS_KEY",
    "CATALOG_OBSERVATIONS_KEY",
    "CATALOG_RAW_SOURCES_KEY",
    "CATALOG_READINESS_KEY",
    "CATALOG_SOURCE_MODULES_KEY",
    "CATALOG_SOURCE_PREFLIGHT_KEY",
]
