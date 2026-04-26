"""Ukraine domain assets for Data Forge."""

from __future__ import annotations

from .assets import (
    UKRAINE_ASSET_GROUP,
    UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
    UKRAINE_DEMOGRAPHY_PRIORS_KEY,
    UKRAINE_DEMOGRAPHY_TARGETS_KEY,
    UKRAINE_NORMALIZED_SOURCES_KEY,
    UKRAINE_RAW_SOURCES_KEY,
    UKRAINE_READINESS_KEY,
    UKRAINE_SOURCE_CONFIG_KEY,
    UKRAINE_STATIC_AGING_INPUTS_KEY,
)
from .demography import (
    UkraineDemographyArtifacts,
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)
from .shadow import (
    UkraineReadinessSummary,
    UkraineShadowArtifact,
    UkraineShadowBundle,
    UkraineShadowDiff,
    UkraineSourceSummary,
    compare_ukraine_shadow_bundles,
    load_ukraine_shadow_bundle,
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
    "UkraineDemographyArtifacts",
    "UkraineReadinessSummary",
    "UkraineShadowArtifact",
    "UkraineShadowBundle",
    "UkraineShadowDiff",
    "UkraineSourceSummary",
    "compare_ukraine_shadow_bundles",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
    "load_ukraine_shadow_bundle",
]
