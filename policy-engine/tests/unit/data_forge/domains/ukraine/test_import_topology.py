"""Cold-import and identity contract for Ukraine lazy compatibility exports."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

_EXPECTED_EXPORTS: dict[str, tuple[str, str]] = {
    "UKRAINE_ASSET_GROUP": (".assets", "UKRAINE_ASSET_GROUP"),
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY": (".assets", "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY"),
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY": (".assets", "UKRAINE_DEMOGRAPHY_PRIORS_KEY"),
    "UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY": (
        ".assets",
        "UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY",
    ),
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY": (".assets", "UKRAINE_DEMOGRAPHY_TARGETS_KEY"),
    "UKRAINE_NORMALIZED_SOURCES_KEY": (".assets", "UKRAINE_NORMALIZED_SOURCES_KEY"),
    "UKRAINE_RAW_SOURCES_KEY": (".assets", "UKRAINE_RAW_SOURCES_KEY"),
    "UKRAINE_READINESS_KEY": (".assets", "UKRAINE_READINESS_KEY"),
    "UKRAINE_SOURCE_CONFIG_KEY": (".assets", "UKRAINE_SOURCE_CONFIG_KEY"),
    "UKRAINE_STATIC_AGING_INPUTS_KEY": (".assets", "UKRAINE_STATIC_AGING_INPUTS_KEY"),
    "REAL_BACKTEST_BUNDLE_CONTRACT_FQN": (".contracts", "REAL_BACKTEST_BUNDLE_CONTRACT_FQN"),
    "RealBacktestBundleContract": (".contracts", "RealBacktestBundleContract"),
    "DemographyRoleProjection": (".demography", "DemographyRoleProjection"),
    "DemographySourceEvidence": (".demography", "DemographySourceEvidence"),
    "DemographySourceRequest": (".demography", "DemographySourceRequest"),
    "HistoricalLayoutRequest": (".demography", "HistoricalLayoutRequest"),
    "InventorySourceRequest": (".demography", "InventorySourceRequest"),
    "SourceResolutionRefusalError": (".demography", "SourceResolutionRefusalError"),
    "UkraineDemographyArtifacts": (".demography", "UkraineDemographyArtifacts"),
    "load_demography_artifacts": (".demography", "load_demography_artifacts"),
    "load_donor_pool": (".demography", "load_donor_pool"),
    "load_reconciled_targets": (".demography", "load_reconciled_targets"),
    "load_transition_priors": (".demography", "load_transition_priors"),
    "UkraineReadinessSummary": (".shadow", "UkraineReadinessSummary"),
    "UkraineShadowArtifact": (".shadow", "UkraineShadowArtifact"),
    "UkraineShadowBundle": (".shadow", "UkraineShadowBundle"),
    "UkraineShadowDiff": (".shadow", "UkraineShadowDiff"),
    "UkraineSourceSummary": (".shadow", "UkraineSourceSummary"),
    "compare_ukraine_shadow_bundles": (".shadow", "compare_ukraine_shadow_bundles"),
    "load_ukraine_shadow_bundle": (".shadow", "load_ukraine_shadow_bundle"),
    "UkraineLexPreShardDiff": (".sharding", "UkraineLexPreShardDiff"),
    "UkraineLexPreShardSummary": (".sharding", "UkraineLexPreShardSummary"),
    "UkraineLexShardEntry": (".sharding", "UkraineLexShardEntry"),
    "UkraineLexShardPassSummary": (".sharding", "UkraineLexShardPassSummary"),
    "compare_lex_pre_shard_summaries": (".sharding", "compare_lex_pre_shard_summaries"),
    "infer_lex_snapshot_label": (".sharding", "infer_lex_snapshot_label"),
    "lex_pre_shard_index": (".sharding", "lex_pre_shard_index"),
    "lex_pre_shard_pass_name": (".sharding", "lex_pre_shard_pass_name"),
    "load_lex_pre_shard_summary": (".sharding", "load_lex_pre_shard_summary"),
    "build_static_aging_state": (".static_aging", "build_static_aging_state"),
}
_EXPECTED_ALL: tuple[str, ...] = (
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
)
_EXPECTED_CHILD_MODULES: dict[str, str] = {
    "assets": ".assets",
    "contracts": ".contracts",
    "demography": ".demography",
    "manifests": ".manifests",
    "models": ".models",
    "shadow": ".shadow",
    "sharding": ".sharding",
    "static_aging": ".static_aging",
}
_COLD_IMPORT_SCRIPT = (
    "import importlib",
    "import sys",
    "",
    "order = sys.argv[1]",
    'facade_name = "polisyos.data_forge.domains.ukraine"',
    'read_api_name = "polisyos.data_forge.read_api.ukraine"',
    'source_name = "polisyos.data_forge.domains.ukraine.demography.source_inventory"',
    'demography_name = "polisyos.data_forge.domains.ukraine.demography"',
    'if order == "read_api_first":',
    "    api = importlib.import_module(read_api_name)",
    "    assert demography_name not in sys.modules",
    "    facade = importlib.import_module(facade_name)",
    "    assert demography_name not in sys.modules",
    'elif order == "domain_first":',
    "    facade = importlib.import_module(facade_name)",
    "    assert demography_name not in sys.modules",
    "    api = importlib.import_module(read_api_name)",
    "    assert demography_name not in sys.modules",
    'elif order == "source_inventory_first":',
    "    source = importlib.import_module(source_name)",
    "    api = importlib.import_module(read_api_name)",
    "    facade = importlib.import_module(facade_name)",
    'elif order == "runtime_app_first":',
    '    importlib.import_module("polisyos.runtime.http.app")',
    "    api = importlib.import_module(read_api_name)",
    "    facade = importlib.import_module(facade_name)",
    "else:",
    "    raise AssertionError(order)",
    "source = importlib.import_module(source_name)",
    "facade = importlib.import_module(facade_name)",
    "assert source.UkraineJSONSnapshotProvenance is api.UkraineJSONSnapshotProvenance",
    "assert source.VerifiedUkraineStageArtifact is api.VerifiedUkraineStageArtifact",
    "assert source.VerifiedUkraineStageArtifacts is api.VerifiedUkraineStageArtifacts",
    "assert source.load_verified_stage_json_output is api.load_verified_stage_json_output",
    "assert facade.DemographyRoleProjection is importlib.import_module(",
    '    "polisyos.data_forge.domains.ukraine.demography").DemographyRoleProjection',
)

_REMOVE_PROVIDER_SCRIPT = (
    "import importlib",
    "import sys",
    "",
    'name = "DemographyRoleProjection"',
    'facade = importlib.import_module("polisyos.data_forge.domains.ukraine")',
    "assert name in facade.__all__",
    "facade._LAZY_EXPORTS.pop(name)",
    "try:",
    "    getattr(facade, name)",
    "except AttributeError:",
    "    pass",
    "else:",
    '    raise AssertionError("removed lazy provider mapping unexpectedly resolved")',
    'assert not any(module_name == "polisyos.data_forge.domains.ukraine.demography" for module_name in sys.modules)',
)

_FACADE = "polisyos.data_forge.domains.ukraine"


def test_facade_preserves_every_legacy_provider_identity() -> None:
    facade = importlib.import_module(_FACADE)
    expected = {
        **_EXPECTED_EXPORTS,
        **{name: (module, None) for name, module in _EXPECTED_CHILD_MODULES.items()},
    }
    assert facade.__all__ == list(_EXPECTED_ALL)
    assert expected == facade._LAZY_EXPORTS
    for name, (module_name, attribute_name) in expected.items():
        module = importlib.import_module(module_name, facade.__name__)
        provider = module if attribute_name is None else getattr(module, attribute_name)
        assert getattr(facade, name) is provider


@pytest.mark.parametrize(
    "order",
    ["read_api_first", "domain_first", "source_inventory_first", "runtime_app_first"],
)
def test_cold_import_orders_keep_read_api_and_inventory_cycle_free(order: str) -> None:
    script = "\n".join(_COLD_IMPORT_SCRIPT)
    result = subprocess.run(
        [sys.executable, "-c", script, order],
        cwd=Path(__file__).resolve().parents[5],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"cold import order {order!r} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_removed_provider_mapping_does_not_import_demography() -> None:
    script = "\n".join(_REMOVE_PROVIDER_SCRIPT)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[5],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
