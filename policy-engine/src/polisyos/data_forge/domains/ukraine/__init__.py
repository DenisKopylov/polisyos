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
from .contracts import REAL_BACKTEST_BUNDLE_CONTRACT_FQN, RealBacktestBundleContract
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
from .sharding import (
    UkraineLexPreShardDiff,
    UkraineLexPreShardSummary,
    UkraineLexShardEntry,
    UkraineLexShardPassSummary,
    compare_lex_pre_shard_summaries,
    infer_lex_snapshot_label,
    lex_pre_shard_index,
    lex_pre_shard_pass_name,
    load_lex_pre_shard_summary,
)
from .static_aging import build_static_aging_state

__all__ = [
    "REAL_BACKTEST_BUNDLE_CONTRACT_FQN",
    "UKRAINE_ASSET_GROUP",
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY",
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY",
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY",
    "UKRAINE_NORMALIZED_SOURCES_KEY",
    "UKRAINE_RAW_SOURCES_KEY",
    "UKRAINE_READINESS_KEY",
    "UKRAINE_SOURCE_CONFIG_KEY",
    "UKRAINE_STATIC_AGING_INPUTS_KEY",
    "RealBacktestBundleContract",
    "UkraineDemographyArtifacts",
    "UkraineLexPreShardDiff",
    "UkraineLexPreShardSummary",
    "UkraineLexShardEntry",
    "UkraineLexShardPassSummary",
    "UkraineReadinessSummary",
    "UkraineShadowArtifact",
    "UkraineShadowBundle",
    "UkraineShadowDiff",
    "UkraineSourceSummary",
    "build_static_aging_state",
    "compare_lex_pre_shard_summaries",
    "compare_ukraine_shadow_bundles",
    "infer_lex_snapshot_label",
    "lex_pre_shard_index",
    "lex_pre_shard_pass_name",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_lex_pre_shard_summary",
    "load_reconciled_targets",
    "load_transition_priors",
    "load_ukraine_shadow_bundle",
]
