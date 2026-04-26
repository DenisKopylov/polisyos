"""Academic asset mirror contracts for Phase 0C."""

from __future__ import annotations

from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

ACADEMIC_RAW_WORKS_KEY = AssetKey.from_parts("academic", "works", "raw")
ACADEMIC_NORMALIZED_WORKS_KEY = AssetKey.from_parts("academic", "works", "normalized")
ACADEMIC_FULLTEXT_KEY = AssetKey.from_parts("academic", "works", "fulltext")
ACADEMIC_EXTRACTED_CLAIMS_KEY = AssetKey.from_parts("academic", "claims", "extracted")
ACADEMIC_PUBLISHED_CLAIMS_KEY = AssetKey.from_parts("academic", "claims", "published")
ACADEMIC_CLAIMS_KEY = ACADEMIC_PUBLISHED_CLAIMS_KEY
ACADEMIC_SKG_KEY = AssetKey.from_parts("academic", "skg")
ACADEMIC_READINESS_KEY = AssetKey.from_parts("academic", "readiness")

ACADEMIC_ASSET_GROUP = AssetGroup.from_specs(
    "academic",
    (
        AssetSpec(
            key=ACADEMIC_RAW_WORKS_KEY,
            owner="team-data-forge",
            schema_id="academic.works.raw",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=ACADEMIC_NORMALIZED_WORKS_KEY,
            deps=(ACADEMIC_RAW_WORKS_KEY,),
            owner="team-data-forge",
            schema_id="academic.works.normalized",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=ACADEMIC_FULLTEXT_KEY,
            deps=(ACADEMIC_NORMALIZED_WORKS_KEY,),
            owner="team-data-forge",
            schema_id="academic.works.fulltext",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=ACADEMIC_EXTRACTED_CLAIMS_KEY,
            deps=(ACADEMIC_FULLTEXT_KEY,),
            owner="team-data-forge",
            schema_id="academic.claims.extracted",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=ACADEMIC_PUBLISHED_CLAIMS_KEY,
            deps=(ACADEMIC_EXTRACTED_CLAIMS_KEY,),
            owner="team-data-forge",
            schema_id="academic.claims.published",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=ACADEMIC_SKG_KEY,
            deps=(ACADEMIC_PUBLISHED_CLAIMS_KEY,),
            owner="team-data-forge",
            schema_id="academic.skg",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=ACADEMIC_READINESS_KEY,
            deps=(ACADEMIC_SKG_KEY,),
            owner="team-data-forge",
            schema_id="academic.pipeline.readiness",
            retention=RetentionClass.HOT,
        ),
    ),
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
]
