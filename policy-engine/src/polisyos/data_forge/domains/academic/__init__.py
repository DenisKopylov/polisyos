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
from .shadow import (
    AcademicReadinessSummary,
    AcademicShadowArtifact,
    AcademicShadowBundle,
    AcademicShadowDiff,
    AcademicStageManifest,
    compare_academic_shadow_bundles,
    load_academic_shadow_bundle,
)

__all__ = [
    "ACADEMIC_ASSET_GROUP",
    "ACADEMIC_CLAIMS_KEY",
    "ACADEMIC_EXTRACTED_CLAIMS_KEY",
    "ACADEMIC_FULLTEXT_KEY",
    "ACADEMIC_NORMALIZED_WORKS_KEY",
    "ACADEMIC_PUBLISHED_CLAIMS_KEY",
    "ACADEMIC_RAW_WORKS_KEY",
    "ACADEMIC_READINESS_KEY",
    "ACADEMIC_SKG_KEY",
    "AcademicReadinessSummary",
    "AcademicShadowArtifact",
    "AcademicShadowBundle",
    "AcademicShadowDiff",
    "AcademicStageManifest",
    "compare_academic_shadow_bundles",
    "load_academic_shadow_bundle",
]
