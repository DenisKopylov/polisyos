"""Runtime-safe read API for catalog Data Forge artifacts."""

from __future__ import annotations

from ._lazy import lazy_dir, load_lazy_export

_CATALOG_DOMAIN = "polisyos.data_forge.domains.catalog"
_EXPORTS = {
    "CATALOG_BASE_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_BASE_SCHEMA_IDS": _CATALOG_DOMAIN,
    "CATALOG_ASSET_GROUP": _CATALOG_DOMAIN,
    "CATALOG_INDEX_KEY": _CATALOG_DOMAIN,
    "CATALOG_NORMALIZED_DATASETS_KEY": _CATALOG_DOMAIN,
    "CATALOG_OBSERVATIONS_KEY": _CATALOG_DOMAIN,
    "CATALOG_RAW_SOURCES_KEY": _CATALOG_DOMAIN,
    "CATALOG_READINESS_KEY": _CATALOG_DOMAIN,
    "CATALOG_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_MODULES_KEY": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_PREFLIGHT_KEY": _CATALOG_DOMAIN,
    "CORE_CATALOG_SOURCE_MODULES": _CATALOG_DOMAIN,
    "CatalogBenchmarkReport": _CATALOG_DOMAIN,
    "CatalogExecutionTier": _CATALOG_DOMAIN,
    "CatalogHistoryPolicy": _CATALOG_DOMAIN,
    "CatalogQCReport": _CATALOG_DOMAIN,
    "CatalogReadinessSummary": _CATALOG_DOMAIN,
    "CatalogReadinessPackage": _CATALOG_DOMAIN,
    "CatalogRunLane": _CATALOG_DOMAIN,
    "CatalogRunProfile": _CATALOG_DOMAIN,
    "CatalogShadowArtifact": _CATALOG_DOMAIN,
    "CatalogShadowBundle": _CATALOG_DOMAIN,
    "CatalogShadowDiff": _CATALOG_DOMAIN,
    "CatalogSourceAssetKeys": _CATALOG_DOMAIN,
    "CatalogSourceModulePlan": _CATALOG_DOMAIN,
    "CatalogSourceModuleSpec": _CATALOG_DOMAIN,
    "CatalogSourceRegistryEntry": _CATALOG_DOMAIN,
    "CatalogSourceRegistrySpec": _CATALOG_DOMAIN,
    "CatalogSourceStage": _CATALOG_DOMAIN,
    "CatalogSourceStageContract": _CATALOG_DOMAIN,
    "CatalogSourceSummary": _CATALOG_DOMAIN,
    "CatalogStageManifest": _CATALOG_DOMAIN,
    "DatasetCatalogGraph": "polisyos.data_forge.domains.catalog.knowledge.search",
    "DatasetCatalogStore": "polisyos.data_forge.domains.catalog.knowledge.store",
    "DatasetRegistry": "polisyos.data_forge.domains.catalog.knowledge.registry",
    "DatasetSearchResult": "polisyos.data_forge.domains.catalog.knowledge.types",
    "MetricBindingMatch": "polisyos.data_forge.domains.catalog.knowledge.types",
    "PStarZResult": "polisyos.data_forge.domains.catalog.knowledge.types",
    "ProxyCandidate": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "ProxyChain": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "SearchFilters": "polisyos.data_forge.domains.catalog.knowledge.search",
    "VariableAlignment": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "build_catalog_source_asset_group": _CATALOG_DOMAIN,
    "build_catalog_schema_registry": _CATALOG_DOMAIN,
    "catalog_source_modules_from_registry": _CATALOG_DOMAIN,
    "compose_confidence_chain": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "compose_confidence_harmonic": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "compare_catalog_shadow_bundles": _CATALOG_DOMAIN,
    "default_catalog_source_registry_path": _CATALOG_DOMAIN,
    "default_seed_alignments_path": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "load_catalog_benchmark_report": _CATALOG_DOMAIN,
    "load_catalog_qc_report": _CATALOG_DOMAIN,
    "load_catalog_readiness_package": _CATALOG_DOMAIN,
    "load_catalog_shadow_bundle": _CATALOG_DOMAIN,
    "load_catalog_source_registry": _CATALOG_DOMAIN,
    "load_seed_alignments": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "plan_catalog_source_stage_contracts": _CATALOG_DOMAIN,
    "plan_catalog_source_modules": _CATALOG_DOMAIN,
    "resolve_proxy": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "score_variable_pair": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "select_catalog_source_modules": _CATALOG_DOMAIN,
    "validate_proxy": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
}


def __getattr__(name: str) -> object:
    """Lazily resolve catalog exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public catalog read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
