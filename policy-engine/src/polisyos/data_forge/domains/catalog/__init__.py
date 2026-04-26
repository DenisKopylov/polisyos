"""Catalog domain scaffolding for Data Forge."""

from __future__ import annotations

from .assets import (
    CATALOG_ASSET_GROUP,
    CATALOG_INDEX_KEY,
    CATALOG_NORMALIZED_DATASETS_KEY,
    CATALOG_OBSERVATIONS_KEY,
    CATALOG_RAW_SOURCES_KEY,
    CATALOG_READINESS_KEY,
    CATALOG_SOURCE_MODULES_KEY,
    CATALOG_SOURCE_PREFLIGHT_KEY,
)
from .shadow import (
    CatalogReadinessSummary,
    CatalogShadowArtifact,
    CatalogShadowBundle,
    CatalogShadowDiff,
    CatalogSourceSummary,
    CatalogStageManifest,
    compare_catalog_shadow_bundles,
    load_catalog_shadow_bundle,
)
from .source_modules import (
    CORE_CATALOG_SOURCE_MODULES,
    CatalogExecutionTier,
    CatalogRunLane,
    CatalogRunProfile,
    CatalogSourceAssetKeys,
    CatalogSourceModulePlan,
    CatalogSourceModuleSpec,
    build_catalog_source_asset_group,
    plan_catalog_source_modules,
    select_catalog_source_modules,
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
    "CORE_CATALOG_SOURCE_MODULES",
    "CatalogExecutionTier",
    "CatalogReadinessSummary",
    "CatalogRunLane",
    "CatalogRunProfile",
    "CatalogShadowArtifact",
    "CatalogShadowBundle",
    "CatalogShadowDiff",
    "CatalogSourceAssetKeys",
    "CatalogSourceModulePlan",
    "CatalogSourceModuleSpec",
    "CatalogSourceSummary",
    "CatalogStageManifest",
    "build_catalog_source_asset_group",
    "compare_catalog_shadow_bundles",
    "load_catalog_shadow_bundle",
    "plan_catalog_source_modules",
    "select_catalog_source_modules",
]
