"""Runtime-safe read API for catalog Data Forge artifacts."""

from __future__ import annotations

from ._lazy import lazy_dir, load_lazy_export

_CATALOG_DOMAIN = "polisyos.data_forge.domains.catalog"
_EXPORTS = {
    "CATALOG_ASSET_GROUP": _CATALOG_DOMAIN,
    "CATALOG_INDEX_KEY": _CATALOG_DOMAIN,
    "CATALOG_NORMALIZED_DATASETS_KEY": _CATALOG_DOMAIN,
    "CATALOG_OBSERVATIONS_KEY": _CATALOG_DOMAIN,
    "CATALOG_RAW_SOURCES_KEY": _CATALOG_DOMAIN,
    "CATALOG_READINESS_KEY": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_MODULES_KEY": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_PREFLIGHT_KEY": _CATALOG_DOMAIN,
    "CORE_CATALOG_SOURCE_MODULES": _CATALOG_DOMAIN,
    "CatalogExecutionTier": _CATALOG_DOMAIN,
    "CatalogReadinessSummary": _CATALOG_DOMAIN,
    "CatalogRunLane": _CATALOG_DOMAIN,
    "CatalogRunProfile": _CATALOG_DOMAIN,
    "CatalogShadowArtifact": _CATALOG_DOMAIN,
    "CatalogShadowBundle": _CATALOG_DOMAIN,
    "CatalogShadowDiff": _CATALOG_DOMAIN,
    "CatalogSourceAssetKeys": _CATALOG_DOMAIN,
    "CatalogSourceModulePlan": _CATALOG_DOMAIN,
    "CatalogSourceModuleSpec": _CATALOG_DOMAIN,
    "CatalogSourceSummary": _CATALOG_DOMAIN,
    "CatalogStageManifest": _CATALOG_DOMAIN,
    "build_catalog_source_asset_group": _CATALOG_DOMAIN,
    "compare_catalog_shadow_bundles": _CATALOG_DOMAIN,
    "load_catalog_shadow_bundle": _CATALOG_DOMAIN,
    "plan_catalog_source_modules": _CATALOG_DOMAIN,
    "select_catalog_source_modules": _CATALOG_DOMAIN,
}


def __getattr__(name: str) -> object:
    """Lazily resolve catalog exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public catalog read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
