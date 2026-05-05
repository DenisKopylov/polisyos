from __future__ import annotations

import sys
from pathlib import Path

import pytest
from polisyos.data_forge.kernel.pipeline import plan_asset_specs
from polisyos.data_forge.read_api.academic import (
    ACADEMIC_ASSET_GROUP,
    ACADEMIC_CLAIMS_KEY,
    ACADEMIC_EXTRACTED_CLAIMS_KEY,
    ACADEMIC_FULLTEXT_KEY,
    ACADEMIC_NORMALIZED_WORKS_KEY,
    ACADEMIC_PUBLISHED_CLAIMS_KEY,
    ACADEMIC_RAW_WORKS_KEY,
    ACADEMIC_READINESS_KEY,
    ACADEMIC_SKG_KEY,
    compare_academic_shadow_bundles,
    load_academic_shadow_bundle,
)
from polisyos.data_forge.read_api.catalog import (
    CATALOG_ASSET_GROUP,
    CATALOG_INDEX_KEY,
    CATALOG_NORMALIZED_DATASETS_KEY,
    CATALOG_OBSERVATIONS_KEY,
    CATALOG_RAW_SOURCES_KEY,
    CATALOG_READINESS_KEY,
    CATALOG_SOURCE_MODULES_KEY,
    CATALOG_SOURCE_PREFLIGHT_KEY,
    load_catalog_shadow_bundle,
)

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "non_lex_split"


def test_academic_asset_group_declares_dependency_order() -> None:
    planned = plan_asset_specs(tuple(ACADEMIC_ASSET_GROUP.assets.values()))

    assert tuple(spec.key for spec in planned) == (
        ACADEMIC_RAW_WORKS_KEY,
        ACADEMIC_NORMALIZED_WORKS_KEY,
        ACADEMIC_FULLTEXT_KEY,
        ACADEMIC_EXTRACTED_CLAIMS_KEY,
        ACADEMIC_PUBLISHED_CLAIMS_KEY,
        ACADEMIC_SKG_KEY,
        ACADEMIC_READINESS_KEY,
    )
    assert ACADEMIC_CLAIMS_KEY == ACADEMIC_PUBLISHED_CLAIMS_KEY


def test_catalog_asset_group_declares_dependency_order() -> None:
    planned = plan_asset_specs(tuple(CATALOG_ASSET_GROUP.assets.values()))

    assert tuple(spec.key for spec in planned) == (
        CATALOG_RAW_SOURCES_KEY,
        CATALOG_SOURCE_MODULES_KEY,
        CATALOG_NORMALIZED_DATASETS_KEY,
        CATALOG_SOURCE_PREFLIGHT_KEY,
        CATALOG_OBSERVATIONS_KEY,
        CATALOG_INDEX_KEY,
        CATALOG_READINESS_KEY,
    )


def test_academic_shadow_bundle_loads_without_legacy_academic_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.academic")}

    bundle = load_academic_shadow_bundle(FIXTURES_ROOT / "academic")

    after = {name for name in sys.modules if name.startswith("polisyos.academic")}
    assert after == before
    assert bundle.pipeline == "academic"
    assert bundle.consumer_ready is True
    assert bundle.readiness["canonical_runtime_ready"] is True
    assert bundle.readiness_summary.consumer_ready is True
    assert bundle.readiness_summary.failed_readiness_checks == ()
    assert bundle.benchmark_metrics["parameter_supported_ratio"] == 0.7
    assert bundle.qc_metrics["runtime_demanded_canonical_resolution_rate_pct"] == 95.0
    assert len(bundle.artifacts) == 5
    assert all(artifact.checksum_ok is True for artifact in bundle.artifacts)
    assert bundle.artifact_by_relative_path("publish/academic_pipeline_readiness.json")
    assert bundle.stage_manifests[0].stage == "publish"
    assert bundle.warnings == ()


def test_academic_shadow_diff_reports_readiness_and_metric_changes() -> None:
    baseline = load_academic_shadow_bundle(FIXTURES_ROOT / "academic")
    candidate = load_academic_shadow_bundle(FIXTURES_ROOT / "academic_candidate")

    diff = compare_academic_shadow_bundles(baseline, candidate)

    assert diff.has_changes
    assert diff.added_artifacts == ()
    assert diff.removed_artifacts == ()
    assert "publish/academic_pipeline_readiness.json" in diff.changed_artifacts
    assert diff.readiness_changes["consumer_ready"] == (True, False)
    assert diff.readiness_changes["parameter_utility_ready"] == (True, False)
    assert diff.readiness_changes["failed_readiness_checks"] == (
        (),
        ("operational_stability_ready", "parameter_utility_ready"),
    )
    assert diff.metric_deltas["benchmark.parameter_supported_ratio"] == pytest.approx(-0.1)
    assert diff.metric_deltas["qc.runtime_demanded_canonical_resolution_rate_pct"] == -3.0


def test_catalog_shadow_bundle_loads_without_legacy_dataset_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.datasets")}

    bundle = load_catalog_shadow_bundle(FIXTURES_ROOT / "catalog")

    after = {name for name in sys.modules if name.startswith("polisyos.datasets")}
    assert after == before
    assert bundle.pipeline == "datasets"
    assert bundle.consumer_ready is True
    assert bundle.full_publish_ready is True
    assert bundle.publish_mode == "full-ready"
    assert bundle.table_counts["datasets"] == 2
    assert bundle.benchmark_metrics["benchmark_foundry_fitness_pct"] == 100.0
    assert bundle.readiness_summary.failed_readiness_checks == ()
    assert bundle.source_by_id("worldbank")
    assert len(bundle.artifacts) == 5
    assert all(artifact.checksum_ok is True for artifact in bundle.artifacts)
    assert bundle.stage_manifests[0].stage == "publish"
    assert bundle.warnings == ()
