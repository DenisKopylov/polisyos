"""Ukraine asset mirror contracts that avoid Lex/NPA sharding surfaces."""

from __future__ import annotations

from polisyos.data_forge.kernel.artifacts import RetentionClass
from polisyos.data_forge.kernel.pipeline import AssetGroup, AssetKey, AssetSpec

UKRAINE_SOURCE_CONFIG_KEY = AssetKey.from_parts("ukraine", "sources", "config")
UKRAINE_RAW_SOURCES_KEY = AssetKey.from_parts("ukraine", "sources", "raw")
UKRAINE_NORMALIZED_SOURCES_KEY = AssetKey.from_parts("ukraine", "sources", "normalized")
UKRAINE_DEMOGRAPHY_TARGETS_KEY = AssetKey.from_parts("ukraine", "demography", "targets")
UKRAINE_DEMOGRAPHY_PRIORS_KEY = AssetKey.from_parts("ukraine", "demography", "priors")
UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY = AssetKey.from_parts("ukraine", "demography", "donor_pool")
UKRAINE_STATIC_AGING_INPUTS_KEY = AssetKey.from_parts("ukraine", "demography", "static_aging")
UKRAINE_READINESS_KEY = AssetKey.from_parts("ukraine", "readiness")

UKRAINE_ASSET_GROUP = AssetGroup.from_specs(
    "ukraine",
    (
        AssetSpec(
            key=UKRAINE_SOURCE_CONFIG_KEY,
            owner="team-data-forge",
            schema_id="ukraine.sources.config",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=UKRAINE_RAW_SOURCES_KEY,
            deps=(UKRAINE_SOURCE_CONFIG_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.sources.raw",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=UKRAINE_NORMALIZED_SOURCES_KEY,
            deps=(UKRAINE_RAW_SOURCES_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.sources.normalized",
            retention=RetentionClass.WARM,
        ),
        AssetSpec(
            key=UKRAINE_DEMOGRAPHY_TARGETS_KEY,
            deps=(UKRAINE_NORMALIZED_SOURCES_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.demography.targets",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=UKRAINE_DEMOGRAPHY_PRIORS_KEY,
            deps=(UKRAINE_NORMALIZED_SOURCES_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.demography.priors",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
            deps=(UKRAINE_NORMALIZED_SOURCES_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.demography.donor_pool",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=UKRAINE_STATIC_AGING_INPUTS_KEY,
            deps=(
                UKRAINE_DEMOGRAPHY_TARGETS_KEY,
                UKRAINE_DEMOGRAPHY_PRIORS_KEY,
                UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
            ),
            owner="team-data-forge",
            schema_id="ukraine.demography.static_aging",
            retention=RetentionClass.HOT,
        ),
        AssetSpec(
            key=UKRAINE_READINESS_KEY,
            deps=(UKRAINE_STATIC_AGING_INPUTS_KEY,),
            owner="team-data-forge",
            schema_id="ukraine.readiness",
            retention=RetentionClass.HOT,
        ),
    ),
)

__all__ = [
    "UKRAINE_ASSET_GROUP",
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY",
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY",
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY",
    "UKRAINE_NORMALIZED_SOURCES_KEY",
    "UKRAINE_RAW_SOURCES_KEY",
    "UKRAINE_READINESS_KEY",
    "UKRAINE_SOURCE_CONFIG_KEY",
    "UKRAINE_STATIC_AGING_INPUTS_KEY",
]
