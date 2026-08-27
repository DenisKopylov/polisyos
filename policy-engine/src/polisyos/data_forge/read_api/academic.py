"""Runtime-safe read API for academic Data Forge artifacts."""

from __future__ import annotations

from ._lazy import lazy_dir, load_lazy_export

_ACADEMIC_DOMAIN = "polisyos.data_forge.domains.academic"
_ACADEMIC_KNOWLEDGE = f"{_ACADEMIC_DOMAIN}.knowledge"
_CLAIM_ADJUDICATOR = f"{_ACADEMIC_DOMAIN}.batch.claim_adjudicator"
_RUNTIME_CANONICAL_REGISTRY = f"{_ACADEMIC_KNOWLEDGE}.runtime_canonical_registry"
_EXPORTS = {
    "ACADEMIC_ASSET_GROUP": _ACADEMIC_DOMAIN,
    "ACADEMIC_ASSET_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_DEPENDENCIES": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_ID_PATTERN": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_ORDER": _ACADEMIC_DOMAIN,
    "ACADEMIC_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_EXTRACTED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_FULLTEXT_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_NORMALIZED_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_PUBLISHED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_RAW_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_READINESS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_SKG_KEY": _ACADEMIC_DOMAIN,
    "CORE_ACADEMIC_BATCH_STAGES": _ACADEMIC_DOMAIN,
    "AcademicBatchRunProfile": _ACADEMIC_DOMAIN,
    "AcademicBatchStagePlan": _ACADEMIC_DOMAIN,
    "AcademicBatchStageSpec": _ACADEMIC_DOMAIN,
    "AcademicBenchmarkReport": _ACADEMIC_DOMAIN,
    "AcademicQCReport": _ACADEMIC_DOMAIN,
    "AcademicReadinessSummary": _ACADEMIC_DOMAIN,
    "AcademicReadinessPackage": _ACADEMIC_DOMAIN,
    "AcademicSKGSummary": _ACADEMIC_DOMAIN,
    "AcademicSKGTableSummary": _ACADEMIC_DOMAIN,
    "AcademicShadowArtifact": _ACADEMIC_DOMAIN,
    "AcademicShadowBundle": _ACADEMIC_DOMAIN,
    "AcademicShadowDiff": _ACADEMIC_DOMAIN,
    "AcademicStageManifest": _ACADEMIC_DOMAIN,
    "AcademicBatchConfig": "polisyos.data_forge.domains.academic.batch.config",
    "CANONICAL_VARIABLES": f"{_ACADEMIC_KNOWLEDGE}.canonical_seed",
    "CanonicalVariableResolver": f"{_ACADEMIC_KNOWLEDGE}.canonical_resolver",
    "CausalClaimResult": f"{_ACADEMIC_KNOWLEDGE}.types",
    "EstimateCandidate": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ParameterCandidate": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "ParameterPrior": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ParameterSelector": f"{_ACADEMIC_KNOWLEDGE}.parameter_selector",
    "RUNTIME_CANONICAL_REGISTRY": _RUNTIME_CANONICAL_REGISTRY,
    "RUNTIME_CANONICAL_REGISTRY_VERSION": _RUNTIME_CANONICAL_REGISTRY,
    "SKGQuery": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "ScholarKnowledgeGraph": f"{_ACADEMIC_KNOWLEDGE}.search",
    "WorkRecord": f"{_ACADEMIC_KNOWLEDGE}.types",
    "WorkSearchResult": f"{_ACADEMIC_KNOWLEDGE}.types",
    "GonkaMultiKeyPool": "polisyos.data_forge.domains.academic.batch._resolve_extract_providers",
    "build_academic_batch_asset_group": _ACADEMIC_DOMAIN,
    "build_academic_schema_registry": _ACADEMIC_DOMAIN,
    "compare_academic_shadow_bundles": _ACADEMIC_DOMAIN,
    "load_academic_benchmark_report": _ACADEMIC_DOMAIN,
    "load_academic_qc_report": _ACADEMIC_DOMAIN,
    "load_academic_readiness_package": _ACADEMIC_DOMAIN,
    "load_academic_skg_summary": _ACADEMIC_DOMAIN,
    "load_academic_shadow_bundle": _ACADEMIC_DOMAIN,
    "plan_academic_batch_stages": _ACADEMIC_DOMAIN,
    "materialize_claim_adjudication_result": _CLAIM_ADJUDICATOR,
    "produce_claim_adjudication_input": _CLAIM_ADJUDICATOR,
    "run_edge_synthesize": "polisyos.data_forge.domains.academic.batch.edge_synthesize",
    "runtime_approved_synonyms": _RUNTIME_CANONICAL_REGISTRY,
    "runtime_canonical_entries": _RUNTIME_CANONICAL_REGISTRY,
    "runtime_canonical_names": _RUNTIME_CANONICAL_REGISTRY,
    "select_academic_batch_stages": _ACADEMIC_DOMAIN,
}


def __getattr__(name: str) -> object:
    """Lazily resolve academic exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public academic read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
