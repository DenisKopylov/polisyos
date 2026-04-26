from __future__ import annotations

import sys
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
    compare_ukraine_shadow_bundles,
    load_demography_artifacts,
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
    before_lex = {name for name in sys.modules if name.startswith("polisyos.lex.batch")}

    bundle = load_ukraine_shadow_bundle(BASELINE_ROOT)

    after_ukraine = {name for name in sys.modules if name.startswith("polisyos.ukraine_data")}
    after_lex = {name for name in sys.modules if name.startswith("polisyos.lex.batch")}
    assert after_ukraine == before_ukraine
    assert after_lex == before_lex
    assert bundle.pipeline == "ukraine"
    assert bundle.consumer_ready is True
    assert bundle.readiness_summary.static_aging_ready is True
    assert bundle.readiness_summary.failed_readiness_checks == ()
    assert bundle.table_counts["donor_records"] == 2
    assert len(bundle.artifacts) == 6
    assert all(artifact.checksum_ok is True for artifact in bundle.artifacts)
    assert bundle.artifact_by_relative_path("publish/ukraine_readiness.json")
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


def test_ukraine_shadow_diff_reports_readiness_source_and_metric_changes() -> None:
    baseline = load_ukraine_shadow_bundle(BASELINE_ROOT)
    candidate = load_ukraine_shadow_bundle(CANDIDATE_ROOT)

    diff = compare_ukraine_shadow_bundles(baseline, candidate)

    assert diff.has_changes
    assert diff.added_artifacts == ()
    assert diff.removed_artifacts == ()
    assert "publish/ukraine_readiness.json" in diff.changed_artifacts
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
