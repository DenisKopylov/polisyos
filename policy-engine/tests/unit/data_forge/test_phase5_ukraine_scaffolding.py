from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import numpy as np
from polisyos.data_forge.kernel.pipeline import plan_asset_specs
from polisyos.data_forge.read_api.ukraine import (
    UKRAINE_ASSET_GROUP,
    UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
    UKRAINE_DEMOGRAPHY_PRIORS_KEY,
    UKRAINE_DEMOGRAPHY_TARGETS_KEY,
    UKRAINE_NORMALIZED_SOURCES_KEY,
    UKRAINE_RAW_SOURCES_KEY,
    UKRAINE_READINESS_KEY,
    UKRAINE_SOURCE_CONFIG_KEY,
    UKRAINE_STATIC_AGING_INPUTS_KEY,
    build_static_aging_state,
    compare_lex_pre_shard_summaries,
    compare_ukraine_shadow_bundles,
    infer_lex_snapshot_label,
    lex_pre_shard_index,
    lex_pre_shard_pass_name,
    load_demography_artifacts,
    load_donor_pool,
    load_lex_pre_shard_summary,
    load_reconciled_targets,
    load_transition_priors,
    load_ukraine_shadow_bundle,
)

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "ukraine_shadow"
BASELINE_ROOT = FIXTURES_ROOT / "baseline"
CANDIDATE_ROOT = FIXTURES_ROOT / "candidate"


def test_ukraine_asset_group_declares_freeze_safe_dependency_order() -> None:
    planned = plan_asset_specs(tuple(UKRAINE_ASSET_GROUP.assets.values()))

    assert tuple(spec.key for spec in planned) == (
        UKRAINE_SOURCE_CONFIG_KEY,
        UKRAINE_RAW_SOURCES_KEY,
        UKRAINE_NORMALIZED_SOURCES_KEY,
        UKRAINE_DEMOGRAPHY_TARGETS_KEY,
        UKRAINE_DEMOGRAPHY_PRIORS_KEY,
        UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
        UKRAINE_STATIC_AGING_INPUTS_KEY,
        UKRAINE_READINESS_KEY,
    )
    assert not any(
        blocked in str(spec.key) for spec in planned for blocked in ("lex", "npa", "shard", "cloud")
    )


def test_ukraine_shadow_bundle_loads_without_legacy_or_lex_imports() -> None:
    before_ukraine = {name for name in sys.modules if name.startswith("polisyos.ukraine_data")}
    before_lex = {
        name
        for name in sys.modules
        if name.startswith(("polisyos.lex.batch", "polisyos.lex.corpus"))
    }

    bundle = load_ukraine_shadow_bundle(BASELINE_ROOT)

    after_ukraine = {name for name in sys.modules if name.startswith("polisyos.ukraine_data")}
    after_lex = {
        name
        for name in sys.modules
        if name.startswith(("polisyos.lex.batch", "polisyos.lex.corpus"))
    }
    assert after_ukraine == before_ukraine
    assert after_lex == before_lex
    assert bundle.pipeline == "ukraine"
    assert bundle.consumer_ready is True
    assert bundle.readiness_summary.static_aging_ready is True
    assert bundle.readiness_summary.failed_readiness_checks == ()
    assert bundle.table_counts["donor_records"] == 2
    assert len(bundle.artifacts) == 7
    assert all(artifact.checksum_ok is True for artifact in bundle.artifacts)
    assert bundle.artifact_by_relative_path("publish/ukraine_readiness.json")
    assert bundle.artifact_by_relative_path("sharding/pre_shard_summary.json")
    source = bundle.source_by_id("state_statistics_demography")
    assert source is not None
    assert source.records == 2
    assert bundle.warnings == ()


def test_ukraine_demography_read_api_builds_static_aging_state_from_fixture() -> None:
    artifacts = load_demography_artifacts(BASELINE_ROOT)

    state = build_static_aging_state(
        base_weights=np.array([1.0, 2.0]),
        origin_state_index=np.array([0, 1]),
        artifacts=artifacts,
    )

    assert artifacts.metadata["year"] == 2027
    assert np.allclose(state["target_state_totals"], np.array([120.0, 280.0]))
    assert np.array_equal(state["donor_record_index"], np.array([101, 102]))
    assert np.array_equal(state["allowed_transition_mask"], np.array([[True, True], [False, True]]))


def test_ukraine_demography_inputs_load_as_separate_read_api_contracts() -> None:
    targets = load_reconciled_targets(BASELINE_ROOT)
    priors = load_transition_priors(BASELINE_ROOT)
    donor_pool = load_donor_pool(BASELINE_ROOT)

    assert targets["state_ids"] == ["0-17:F:UA", "18-64:F:UA"]
    assert targets["target_state_totals"] == [120.0, 280.0]
    assert targets["entrant_state_totals"] == [12.0, 3.0]
    assert priors["transition_prior_matrix"] == [[0.85, 0.15], [0.05, 0.95]]
    assert priors["allowed_transition_mask"] == [[True, True], [False, True]]
    assert donor_pool["donor_weights"] == [0.4, 0.6]
    assert donor_pool["donor_state_index"] == [0, 1]
    assert donor_pool["donor_record_index"] == [101, 102]


def test_ukraine_shadow_diff_reports_readiness_source_and_metric_changes() -> None:
    baseline = load_ukraine_shadow_bundle(BASELINE_ROOT)
    candidate = load_ukraine_shadow_bundle(CANDIDATE_ROOT)

    diff = compare_ukraine_shadow_bundles(baseline, candidate)

    assert diff.has_changes
    assert diff.added_artifacts == ()
    assert diff.removed_artifacts == ()
    assert "publish/ukraine_readiness.json" in diff.changed_artifacts
    assert "sharding/pre_shard_summary.json" in diff.changed_artifacts
    assert diff.added_sources == ()
    assert diff.removed_sources == ()
    assert diff.changed_sources == ("state_statistics_demography",)
    assert diff.readiness_changes["consumer_ready"] == (True, False)
    assert diff.readiness_changes["source_data_ready"] == (True, False)
    assert diff.readiness_changes["static_aging_ready"] == (True, False)
    assert diff.readiness_changes["failed_readiness_checks"] == (
        (),
        ("source_data_ready", "static_aging_ready"),
    )
    assert diff.metric_deltas["table_counts.source_records"] == -1.0
    assert diff.metric_deltas["table_counts.donor_records"] == -1.0
    assert diff.metric_deltas["source.state_statistics_demography.records"] == -1.0


def test_ukraine_pre_shard_contract_loads_and_diffs_immutable_artifacts() -> None:
    baseline = load_lex_pre_shard_summary(BASELINE_ROOT / "sharding" / "pre_shard_summary.json")
    candidate = load_lex_pre_shard_summary(CANDIDATE_ROOT / "sharding" / "pre_shard_summary.json")

    assert baseline.snapshot_label == "20260501"
    assert baseline.passes["current"].total_docs == 3
    assert (
        infer_lex_snapshot_label("edrnpa_cards_20260501.xml", "edrnpa_texts_20260501.xml")
        == "20260501"
    )
    assert lex_pre_shard_pass_name("Чинний") == "current"
    assert lex_pre_shard_pass_name("Втратив чинність") == "historical"
    assert lex_pre_shard_pass_name("Невідомий статус") is None
    assert lex_pre_shard_index("doc::ua::001", 6) == lex_pre_shard_index("doc::ua::001", 6)

    diff = compare_lex_pre_shard_summaries(baseline, candidate)

    assert diff.has_changes is True
    assert diff.processed_docs_delta == -1
    assert diff.changed_passes == ("current",)
    assert diff.shard_doc_deltas == {"current/shard_01": -1}


def test_ukraine_builders_are_split_under_data_forge_after_shim_sunset() -> None:
    builders_root = Path(__file__).resolve().parents[3] / "src" / "polisyos" / "data_forge"
    runtime_path = builders_root / "domains" / "ukraine" / "builders" / "_runtime.py"
    assert not runtime_path.exists()

    common = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.common")
    sources = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.sources")
    demography = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.demography")
    calibration = importlib.import_module(
        "polisyos.data_forge.domains.ukraine.builders.calibration"
    )
    release = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.release")
    builders = importlib.import_module("polisyos.data_forge.domains.ukraine.builders")

    assert common.MemoryAwareScheduler is builders.MemoryAwareScheduler
    assert sources.build_d0_p0_stage is builders.build_d0_p0_stage
    assert sources.build_d2_stage is builders.build_d2_stage
    assert demography.build_d3_stage is builders.build_d3_stage
    assert calibration.build_d4_stage is builders.build_d4_stage
    assert release.build_d5_stage is builders.build_d5_stage


def test_ukraine_legacy_modules_removed_after_shim_sunset() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    new_adapters = importlib.import_module("polisyos.data_forge.domains.ukraine.adapters")
    new_models = importlib.import_module("polisyos.data_forge.domains.ukraine.models")

    assert not (repo_root / "src" / "polisyos" / "ukraine_data").exists()
    assert new_adapters.TabularSourceAdapter.__module__.startswith(
        "polisyos.data_forge.domains.ukraine."
    )
    assert new_models.PipelineConfig.__module__.startswith("polisyos.data_forge.domains.ukraine.")


def test_ukraine_complexity_exception_is_burned_down() -> None:
    payload = tomllib.loads(
        (
            Path(__file__).resolve().parents[3] / "architecture" / "complexity_exceptions.toml"
        ).read_text(encoding="utf-8")
    )

    exception_paths = {
        str(entry.get("path")) for entry in payload.get("exception", []) if isinstance(entry, dict)
    }
    assert "src/polisyos/ukraine_data/builders.py" not in exception_paths
