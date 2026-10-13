"""Ukraine domain assets for Data Forge."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_EXPORTS: dict[str, tuple[str, str | None]] = {
    'UKRAINE_ASSET_GROUP': ('.assets', 'UKRAINE_ASSET_GROUP'),
    'UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY': ('.assets', 'UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY'),
    'UKRAINE_DEMOGRAPHY_PRIORS_KEY': ('.assets', 'UKRAINE_DEMOGRAPHY_PRIORS_KEY'),
    'UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY': (
        '.assets',
        'UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY',
    ),
    'UKRAINE_DEMOGRAPHY_TARGETS_KEY': ('.assets', 'UKRAINE_DEMOGRAPHY_TARGETS_KEY'),
    'UKRAINE_NORMALIZED_SOURCES_KEY': ('.assets', 'UKRAINE_NORMALIZED_SOURCES_KEY'),
    'UKRAINE_RAW_SOURCES_KEY': ('.assets', 'UKRAINE_RAW_SOURCES_KEY'),
    'UKRAINE_READINESS_KEY': ('.assets', 'UKRAINE_READINESS_KEY'),
    'UKRAINE_SOURCE_CONFIG_KEY': ('.assets', 'UKRAINE_SOURCE_CONFIG_KEY'),
    'UKRAINE_STATIC_AGING_INPUTS_KEY': ('.assets', 'UKRAINE_STATIC_AGING_INPUTS_KEY'),
    'REAL_BACKTEST_BUNDLE_CONTRACT_FQN': ('.contracts', 'REAL_BACKTEST_BUNDLE_CONTRACT_FQN'),
    'RealBacktestBundleContract': ('.contracts', 'RealBacktestBundleContract'),
    'DemographyRoleProjection': ('.demography', 'DemographyRoleProjection'),
    'DemographySourceEvidence': ('.demography', 'DemographySourceEvidence'),
    'DemographySourceRequest': ('.demography', 'DemographySourceRequest'),
    'HistoricalLayoutRequest': ('.demography', 'HistoricalLayoutRequest'),
    'InventorySourceRequest': ('.demography', 'InventorySourceRequest'),
    'SourceResolutionRefusalError': ('.demography', 'SourceResolutionRefusalError'),
    'UkraineDemographyArtifacts': ('.demography', 'UkraineDemographyArtifacts'),
    'load_demography_artifacts': ('.demography', 'load_demography_artifacts'),
    'load_donor_pool': ('.demography', 'load_donor_pool'),
    'load_reconciled_targets': ('.demography', 'load_reconciled_targets'),
    'load_transition_priors': ('.demography', 'load_transition_priors'),
    'UkraineReadinessSummary': ('.shadow', 'UkraineReadinessSummary'),
    'UkraineShadowArtifact': ('.shadow', 'UkraineShadowArtifact'),
    'UkraineShadowBundle': ('.shadow', 'UkraineShadowBundle'),
    'UkraineShadowDiff': ('.shadow', 'UkraineShadowDiff'),
    'UkraineSourceSummary': ('.shadow', 'UkraineSourceSummary'),
    'compare_ukraine_shadow_bundles': ('.shadow', 'compare_ukraine_shadow_bundles'),
    'load_ukraine_shadow_bundle': ('.shadow', 'load_ukraine_shadow_bundle'),
    'UkraineLexPreShardDiff': ('.sharding', 'UkraineLexPreShardDiff'),
    'UkraineLexPreShardSummary': ('.sharding', 'UkraineLexPreShardSummary'),
    'UkraineLexShardEntry': ('.sharding', 'UkraineLexShardEntry'),
    'UkraineLexShardPassSummary': ('.sharding', 'UkraineLexShardPassSummary'),
    'compare_lex_pre_shard_summaries': ('.sharding', 'compare_lex_pre_shard_summaries'),
    'infer_lex_snapshot_label': ('.sharding', 'infer_lex_snapshot_label'),
    'lex_pre_shard_index': ('.sharding', 'lex_pre_shard_index'),
    'lex_pre_shard_pass_name': ('.sharding', 'lex_pre_shard_pass_name'),
    'load_lex_pre_shard_summary': ('.sharding', 'load_lex_pre_shard_summary'),
    'build_static_aging_state': ('.static_aging', 'build_static_aging_state'),
    'assets': ('.assets', None),
    'contracts': ('.contracts', None),
    'demography': ('.demography', None),
    'manifests': ('.manifests', None),
    'models': ('.models', None),
    'shadow': ('.shadow', None),
    'sharding': ('.sharding', None),
    'static_aging': ('.static_aging', None),
}

__all__ = [
    "REAL_BACKTEST_BUNDLE_CONTRACT_FQN",
    "UKRAINE_ASSET_GROUP",
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY",
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY",
    "UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY",
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY",
    "UKRAINE_NORMALIZED_SOURCES_KEY",
    "UKRAINE_RAW_SOURCES_KEY",
    "UKRAINE_READINESS_KEY",
    "UKRAINE_SOURCE_CONFIG_KEY",
    "UKRAINE_STATIC_AGING_INPUTS_KEY",
    "DemographyRoleProjection",
    "DemographySourceEvidence",
    "DemographySourceRequest",
    "HistoricalLayoutRequest",
    "InventorySourceRequest",
    "RealBacktestBundleContract",
    "SourceResolutionRefusalError",
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

def __getattr__(name: str) -> object:
    """Resolve the historical compatibility surface to its original provider."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = module if export_name is None else getattr(module, export_name)
    globals()[name] = value
    return value

def __dir__() -> list[str]:
    """List the compatibility surface without importing its providers."""
    return sorted({*globals(), *_LAZY_EXPORTS})

if TYPE_CHECKING:
    from .assets import (
        UKRAINE_ASSET_GROUP,
        UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
        UKRAINE_DEMOGRAPHY_PRIORS_KEY,
        UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY,
        UKRAINE_DEMOGRAPHY_TARGETS_KEY,
        UKRAINE_NORMALIZED_SOURCES_KEY,
        UKRAINE_RAW_SOURCES_KEY,
        UKRAINE_READINESS_KEY,
        UKRAINE_SOURCE_CONFIG_KEY,
        UKRAINE_STATIC_AGING_INPUTS_KEY,
    )
    from .contracts import REAL_BACKTEST_BUNDLE_CONTRACT_FQN, RealBacktestBundleContract
    from .demography import (
        DemographyRoleProjection,
        DemographySourceEvidence,
        DemographySourceRequest,
        HistoricalLayoutRequest,
        InventorySourceRequest,
        SourceResolutionRefusalError,
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
