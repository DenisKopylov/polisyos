from __future__ import annotations

import sys
from pathlib import Path

from polisyos.data_forge.kernel.pipeline import plan_asset_specs
from polisyos.data_forge.read_api.catalog import (
    CORE_CATALOG_SOURCE_MODULES,
    build_catalog_source_asset_group,
    compare_catalog_shadow_bundles,
    load_catalog_shadow_bundle,
    plan_catalog_source_modules,
    select_catalog_source_modules,
)

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "non_lex_split"
CATALOG_BASELINE_ROOT = FIXTURES_ROOT / "catalog"
CATALOG_CANDIDATE_ROOT = FIXTURES_ROOT / "catalog_candidate"


def test_catalog_source_modules_select_seed_dependencies_without_legacy_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.datasets")}

    selected = select_catalog_source_modules(
        CORE_CATALOG_SOURCE_MODULES,
        wave="C",
        run_profile="prod_core_blocking",
    )
    plans = plan_catalog_source_modules(
        CORE_CATALOG_SOURCE_MODULES,
        wave="C",
        run_profile="prod_core_blocking",
    )

    after = {name for name in sys.modules if name.startswith("polisyos.datasets")}
    assert after == before
    assert tuple(module.source_id for module in selected) == (
        "data_gov_ua_broad",
        "data_gov_ua_exec",
    )
    assert tuple(plan.source.source_id for plan in plans) == (
        "data_gov_ua_broad",
        "data_gov_ua_exec",
    )
    broad_plan, exec_plan = plans
    assert len(broad_plan.asset_specs) == 3
    assert len(exec_plan.asset_specs) == 4
    assert exec_plan.source.asset_keys().observations is not None


def test_catalog_source_asset_group_declares_per_source_dependency_order() -> None:
    group = build_catalog_source_asset_group(
        CORE_CATALOG_SOURCE_MODULES,
        wave="B",
        run_profile="observations_backfill",
    )

    planned = plan_asset_specs(tuple(group.assets.values()))

    assert tuple(str(spec.key) for spec in planned) == (
        "catalog/sources/worldbank/raw",
        "catalog/sources/worldbank/normalized",
        "catalog/sources/worldbank/observations",
        "catalog/sources/worldbank/readiness",
        "catalog/sources/wvs/raw",
        "catalog/sources/wvs/normalized",
        "catalog/sources/wvs/observations",
        "catalog/sources/wvs/readiness",
    )


def test_catalog_shadow_bundle_exposes_source_summaries() -> None:
    bundle = load_catalog_shadow_bundle(CATALOG_BASELINE_ROOT)

    assert bundle.readiness_summary.consumer_ready is True
    assert bundle.readiness_summary.full_publish_ready is True
    assert bundle.readiness_summary.publish_mode == "full-ready"
    assert tuple(source.source_id for source in bundle.source_summaries) == (
        "eurostat",
        "worldbank",
    )
    assert bundle.source_by_id("eurostat").observation_count == 2
    assert bundle.artifact_by_relative_path("publish/consumer_readiness.json")
    assert bundle.warnings == ()


def test_catalog_shadow_diff_reports_source_readiness_and_metric_changes() -> None:
    baseline = load_catalog_shadow_bundle(CATALOG_BASELINE_ROOT)
    candidate = load_catalog_shadow_bundle(CATALOG_CANDIDATE_ROOT)

    diff = compare_catalog_shadow_bundles(baseline, candidate)

    assert diff.has_changes
    assert diff.added_artifacts == ()
    assert diff.removed_artifacts == ()
    assert "publish/consumer_readiness.json" in diff.changed_artifacts
    assert diff.added_sources == ()
    assert diff.removed_sources == ()
    assert diff.changed_sources == ("eurostat",)
    assert diff.readiness_changes["consumer_ready"] == (True, False)
    assert diff.readiness_changes["full_publish_ready"] == (True, False)
    assert diff.readiness_changes["publish_mode"] == ("full-ready", "shadow-warning")
    assert diff.readiness_changes["source_preflight_ready"] == (True, False)
    assert diff.readiness_changes["failed_readiness_checks"] == (
        (),
        (
            "benchmark_ready",
            "fetchability_ready",
            "foundry_ready",
            "source_preflight_ready",
        ),
    )
    assert diff.metric_deltas["table_counts.observations"] == -1.0
    assert diff.metric_deltas["benchmark.benchmark_foundry_fitness_pct"] == -20.0
    assert diff.metric_deltas["source.eurostat.observation_count"] == -1.0
