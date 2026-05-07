from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from polisyos.data_forge.kernel.pipeline import plan_asset_specs
from polisyos.data_forge.kernel.testing import compare_file_sha256, compare_json_files
from polisyos.data_forge.read_api.catalog import (
    CATALOG_SCHEMA_CONTRACTS,
    CATALOG_SOURCE_SCHEMA_CONTRACTS,
    CORE_CATALOG_SOURCE_MODULES,
    build_catalog_schema_registry,
    build_catalog_source_asset_group,
    catalog_source_modules_from_registry,
    compare_catalog_shadow_bundles,
    load_catalog_benchmark_report,
    load_catalog_qc_report,
    load_catalog_readiness_package,
    load_catalog_shadow_bundle,
    load_catalog_source_registry,
    plan_catalog_source_modules,
    plan_catalog_source_stage_contracts,
    select_catalog_source_modules,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "_data" / "data_forge" / "non_lex_split"
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
        "data_gov_ro_broad",
        "data_gov_ro_exec",
        "data_gov_md_broad",
        "data_gov_md_exec",
        "data_gov_pl_broad",
        "data_gov_pl_exec",
    )
    assert tuple(plan.source.source_id for plan in plans) == (
        "data_gov_ua_broad",
        "data_gov_ua_exec",
        "data_gov_ro_broad",
        "data_gov_ro_exec",
        "data_gov_md_broad",
        "data_gov_md_exec",
        "data_gov_pl_broad",
        "data_gov_pl_exec",
    )
    broad_plan, exec_plan = plans[:2]
    assert len(broad_plan.asset_specs) == 3
    assert len(exec_plan.asset_specs) == 4
    assert exec_plan.source.asset_keys().observations is not None


def test_catalog_source_registry_matches_static_source_modules_without_legacy_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.datasets")}

    registry = load_catalog_source_registry()
    modules = catalog_source_modules_from_registry(registry)

    after = {name for name in sys.modules if name.startswith("polisyos.datasets")}
    assert after == before
    assert len(registry.sources) == 35
    assert tuple(source.source_id for source in registry.sources) == tuple(
        module.source_id for module in CORE_CATALOG_SOURCE_MODULES
    )
    assert tuple(module.source_id for module in modules) == tuple(
        module.source_id for module in CORE_CATALOG_SOURCE_MODULES
    )

    static_by_id = {module.source_id: module for module in CORE_CATALOG_SOURCE_MODULES}
    for entry in registry.sources:
        static = static_by_id[entry.source_id]
        assert entry.to_module_spec() == static

    assert registry.source_by_id("data_gov_uk").enabled is False
    assert tuple(
        source.source_id
        for source in registry.enabled_sources(wave="D", run_profile="rest_backfill")
    ) == ("openaq_v2", "open_meteo", "eia_api")


def test_catalog_source_stage_contracts_cover_harvest_normalize_observe_publish() -> None:
    worldbank = next(
        module for module in CORE_CATALOG_SOURCE_MODULES if module.source_id == "worldbank"
    )
    contracts = worldbank.stage_contracts()

    assert tuple(contract.stage for contract in contracts) == (
        "harvest",
        "normalize",
        "observations",
        "publish",
    )
    assert tuple(str(contract.asset_key) for contract in contracts) == (
        "catalog/sources/worldbank/raw",
        "catalog/sources/worldbank/normalized",
        "catalog/sources/worldbank/observations",
        "catalog/sources/worldbank/readiness",
    )
    assert contracts[2].artifact_globs == (
        "graph/dataset_catalog.duckdb",
        "manifests/core_sources_ingest.json",
    )
    assert contracts[2].legacy_stage == "core_sources_ingest"

    selected_contracts = plan_catalog_source_stage_contracts(
        CORE_CATALOG_SOURCE_MODULES,
        wave="A",
        run_profile="observations_backfill",
    )
    assert tuple(contract.source_id for contract in selected_contracts) == (
        "oecd",
        "oecd",
        "oecd",
        "oecd",
        "eurostat",
        "eurostat",
        "eurostat",
        "eurostat",
    )


def test_catalog_schema_registry_covers_base_and_per_source_assets() -> None:
    registry = build_catalog_schema_registry()
    schema_ids = {schema.schema_id for schema in CATALOG_SCHEMA_CONTRACTS}

    assert {
        "catalog.sources.raw",
        "catalog.sources.modules",
        "catalog.datasets.normalized",
        "catalog.sources.preflight",
        "catalog.observations",
        "catalog.index",
        "catalog.consumer.readiness",
    } <= schema_ids
    assert {
        "catalog.sources.oecd.raw",
        "catalog.sources.oecd.normalized",
        "catalog.sources.oecd.observations",
        "catalog.sources.oecd.readiness",
        "catalog.sources.worldbank.observations",
        "catalog.sources.data_gov_ua_exec.observations",
        "catalog.sources.openaq_v2.readiness",
    } <= schema_ids
    assert len(CATALOG_SOURCE_SCHEMA_CONTRACTS) == sum(
        len(module.stage_contracts()) for module in CORE_CATALOG_SOURCE_MODULES
    )
    assert registry.latest("catalog.consumer.readiness").version == "1.0.0"
    assert registry.latest("catalog.sources.worldbank.observations").json_schema["required"] == [
        "source_id",
        "stage",
        "artifacts",
    ]


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


def test_catalog_readiness_package_loads_benchmark_qc_and_artifact_hashes() -> None:
    benchmark = load_catalog_benchmark_report(CATALOG_BASELINE_ROOT)
    qc = load_catalog_qc_report(CATALOG_BASELINE_ROOT)
    package = load_catalog_readiness_package(CATALOG_BASELINE_ROOT)

    assert benchmark.metrics["benchmark_foundry_fitness_pct"] == 100.0
    assert qc.passed is True
    assert qc.metrics["datasets_with_metric_binding_pct"] == 100.0
    assert package.consumer_ready is True
    assert package.shadow.readiness_summary.full_publish_ready is True
    assert package.artifact_hashes["publish/consumer_readiness.json"] == (
        "b4a2feef436a28a005d016290b5aba7873c5f585f7ea436c358e87fac0fb6afa"
    )


def test_catalog_shadow_diff_reports_source_readiness_and_metric_changes() -> None:
    baseline = load_catalog_shadow_bundle(CATALOG_BASELINE_ROOT)
    candidate = load_catalog_shadow_bundle(CATALOG_CANDIDATE_ROOT)

    diff = compare_catalog_shadow_bundles(baseline, candidate)
    same_hash = compare_file_sha256(
        CATALOG_BASELINE_ROOT / "publish" / "consumer_readiness.json",
        CATALOG_BASELINE_ROOT / "publish" / "consumer_readiness.json",
        name="catalog-readiness-self",
    )
    changed_readiness = compare_json_files(
        CATALOG_BASELINE_ROOT / "publish" / "consumer_readiness.json",
        CATALOG_CANDIDATE_ROOT / "publish" / "consumer_readiness.json",
        name="catalog-readiness-old-vs-new",
    )

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
    assert same_hash.passed is True
    assert changed_readiness.passed is False
    assert changed_readiness.message == "json payload mismatch"


def test_catalog_legacy_core_sources_entrypoint_removed_after_shim_sunset() -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as runtime

    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / "src" / "polisyos" / "datasets").exists()
    assert runtime.CoreSourcesIngestStats.__module__.startswith(
        "polisyos.data_forge.domains.catalog."
    )
    assert runtime.run_core_sources_ingest.__module__ == runtime.__name__


def test_catalog_complexity_exception_is_burned_down() -> None:
    payload = tomllib.loads(
        (
            Path(__file__).resolve().parents[3] / "architecture" / "complexity_exceptions.toml"
        ).read_text(encoding="utf-8")
    )
    exception_paths = {
        str(entry.get("path")) for entry in payload.get("exception", []) if isinstance(entry, dict)
    }

    assert "src/polisyos/datasets/batch/core_sources_ingest.py" not in exception_paths
