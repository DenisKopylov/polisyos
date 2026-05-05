"""Academic domain scaffolding for Data Forge."""

from __future__ import annotations

from .assets import (
    ACADEMIC_ASSET_GROUP,
    ACADEMIC_CLAIMS_KEY,
    ACADEMIC_EXTRACTED_CLAIMS_KEY,
    ACADEMIC_FULLTEXT_KEY,
    ACADEMIC_NORMALIZED_WORKS_KEY,
    ACADEMIC_PUBLISHED_CLAIMS_KEY,
    ACADEMIC_RAW_WORKS_KEY,
    ACADEMIC_READINESS_KEY,
    ACADEMIC_SKG_KEY,
)
from .batch_assets import (
    ACADEMIC_BATCH_STAGE_DEPENDENCIES,
    ACADEMIC_BATCH_STAGE_ID_PATTERN,
    ACADEMIC_BATCH_STAGE_ORDER,
    CORE_ACADEMIC_BATCH_STAGES,
    AcademicBatchRunProfile,
    AcademicBatchStagePlan,
    AcademicBatchStageSpec,
    build_academic_batch_asset_group,
    plan_academic_batch_stages,
    select_academic_batch_stages,
)
from .quality import (
    AcademicBenchmarkReport,
    AcademicQCReport,
    AcademicReadinessPackage,
    load_academic_benchmark_report,
    load_academic_qc_report,
    load_academic_readiness_package,
)
from .schemas import (
    ACADEMIC_ASSET_SCHEMA_CONTRACTS,
    ACADEMIC_BATCH_SCHEMA_CONTRACTS,
    ACADEMIC_SCHEMA_CONTRACTS,
    build_academic_schema_registry,
)
from .shadow import (
    AcademicReadinessSummary,
    AcademicShadowArtifact,
    AcademicShadowBundle,
    AcademicShadowDiff,
    AcademicStageManifest,
    compare_academic_shadow_bundles,
    load_academic_shadow_bundle,
)
from .skg import AcademicSKGSummary, AcademicSKGTableSummary, load_academic_skg_summary

__all__ = [
    "ACADEMIC_ASSET_GROUP",
    "ACADEMIC_ASSET_SCHEMA_CONTRACTS",
    "ACADEMIC_BATCH_SCHEMA_CONTRACTS",
    "ACADEMIC_BATCH_STAGE_DEPENDENCIES",
    "ACADEMIC_BATCH_STAGE_ID_PATTERN",
    "ACADEMIC_BATCH_STAGE_ORDER",
    "ACADEMIC_CLAIMS_KEY",
    "ACADEMIC_EXTRACTED_CLAIMS_KEY",
    "ACADEMIC_FULLTEXT_KEY",
    "ACADEMIC_NORMALIZED_WORKS_KEY",
    "ACADEMIC_PUBLISHED_CLAIMS_KEY",
    "ACADEMIC_RAW_WORKS_KEY",
    "ACADEMIC_READINESS_KEY",
    "ACADEMIC_SCHEMA_CONTRACTS",
    "ACADEMIC_SKG_KEY",
    "CORE_ACADEMIC_BATCH_STAGES",
    "AcademicBatchRunProfile",
    "AcademicBatchStagePlan",
    "AcademicBatchStageSpec",
    "AcademicBenchmarkReport",
    "AcademicQCReport",
    "AcademicReadinessPackage",
    "AcademicReadinessSummary",
    "AcademicSKGSummary",
    "AcademicSKGTableSummary",
    "AcademicShadowArtifact",
    "AcademicShadowBundle",
    "AcademicShadowDiff",
    "AcademicStageManifest",
    "build_academic_batch_asset_group",
    "build_academic_schema_registry",
    "compare_academic_shadow_bundles",
    "load_academic_benchmark_report",
    "load_academic_qc_report",
    "load_academic_readiness_package",
    "load_academic_shadow_bundle",
    "load_academic_skg_summary",
    "plan_academic_batch_stages",
    "select_academic_batch_stages",
]
