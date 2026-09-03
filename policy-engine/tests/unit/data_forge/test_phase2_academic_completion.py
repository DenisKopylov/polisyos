from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.kernel.pipeline import plan_asset_specs
from polisyos.data_forge.kernel.testing import compare_file_sha256, compare_json_files
from polisyos.data_forge.read_api.academic import (
    ACADEMIC_BATCH_STAGE_ORDER,
    ACADEMIC_SCHEMA_CONTRACTS,
    CORE_ACADEMIC_BATCH_STAGES,
    build_academic_batch_asset_group,
    build_academic_schema_registry,
    compare_academic_shadow_bundles,
    load_academic_benchmark_report,
    load_academic_qc_report,
    load_academic_readiness_package,
    load_academic_shadow_bundle,
    load_academic_skg_summary,
    plan_academic_batch_stages,
    select_academic_batch_stages,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "_data" / "data_forge" / "non_lex_split"
ACADEMIC_BASELINE_ROOT = FIXTURES_ROOT / "academic"
ACADEMIC_CANDIDATE_ROOT = FIXTURES_ROOT / "academic_candidate"


def test_academic_batch_stage_assets_plan_without_legacy_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.academic")}

    selected = select_academic_batch_stages(run_profile="publish_readiness")
    plans = plan_academic_batch_stages(run_profile="publish_readiness")
    group = build_academic_batch_asset_group(run_profile="publish_readiness")
    planned = plan_asset_specs(tuple(group.assets.values()))

    after = {name for name in sys.modules if name.startswith("polisyos.academic")}
    assert after == before
    assert tuple(stage.stage_id for stage in selected) == ACADEMIC_BATCH_STAGE_ORDER
    assert tuple(plan.stage.stage_id for plan in plans) == ACADEMIC_BATCH_STAGE_ORDER
    assert tuple(str(spec.key) for spec in planned) == tuple(
        f"academic/batch/{stage_id}" for stage_id in ACADEMIC_BATCH_STAGE_ORDER
    )
    publish_stage = next(
        stage for stage in CORE_ACADEMIC_BATCH_STAGES if stage.stage_id == "publish"
    )
    assert publish_stage.artifact_globs == (
        "publish/manifest.json",
        "publish/academic_pipeline_readiness.json",
    )
    assert publish_stage.read_api_surface is True


def test_academic_batch_stage_assets_cover_legacy_stage_set() -> None:
    from polisyos.data_forge.domains.academic.batch.config import ALL_STAGES

    assert set(ACADEMIC_BATCH_STAGE_ORDER) == ALL_STAGES


def test_academic_batch_stage_profiles_can_select_smaller_groups() -> None:
    selected = select_academic_batch_stages(run_profile="extraction_only")

    assert tuple(stage.stage_id for stage in selected) == (
        "topic_select",
        "demand_harvest",
        "doc_normalize",
        "harvest",
        "parse",
        "resolve_extract",
        "claim_extract",
        "context_extract",
        "mechanism_extract",
        "resolve_finalize",
    )


def test_academic_schema_registry_covers_high_level_and_batch_assets() -> None:
    registry = build_academic_schema_registry()
    schema_ids = {schema.schema_id for schema in ACADEMIC_SCHEMA_CONTRACTS}

    assert {
        "academic.works.raw",
        "academic.works.normalized",
        "academic.works.fulltext",
        "academic.claims.extracted",
        "academic.claims.published",
        "academic.skg",
        "academic.pipeline.readiness",
    } <= schema_ids
    assert {f"academic.batch.{stage_id}" for stage_id in ACADEMIC_BATCH_STAGE_ORDER} <= schema_ids
    assert registry.latest("academic.pipeline.readiness").version == "1.0.0"
    assert registry.latest("academic.batch.publish").json_schema["required"] == [
        "stage",
        "status",
        "artifacts",
    ]


def test_academic_readiness_package_loads_benchmark_qc_and_artifact_hashes() -> None:
    benchmark = load_academic_benchmark_report(ACADEMIC_BASELINE_ROOT)
    qc = load_academic_qc_report(ACADEMIC_BASELINE_ROOT)
    package = load_academic_readiness_package(ACADEMIC_BASELINE_ROOT)

    assert benchmark.passed is True
    assert benchmark.metrics["parameter_supported_ratio"] == 0.7
    assert qc.passed is True
    assert qc.metrics["runtime_demanded_canonical_resolution_rate_pct"] == 95.0
    assert package.consumer_ready is False
    assert package.shadow.consumer_ready is False
    assert package.shadow.readiness_summary.failed_readiness_checks == (
        "schema_generation_current",
    )
    assert package.artifact_hashes["publish/academic_pipeline_readiness.json"] == (
        "5cae2fad04ac57db77e3376742e704e7811eade21d6bbb6d93cba2b1a07a9129"
    )


def test_academic_old_vs_new_fixtures_cover_readiness_and_artifact_hashes() -> None:
    baseline = load_academic_shadow_bundle(ACADEMIC_BASELINE_ROOT)
    candidate = load_academic_shadow_bundle(ACADEMIC_CANDIDATE_ROOT)

    diff = compare_academic_shadow_bundles(baseline, candidate)
    same_hash = compare_file_sha256(
        ACADEMIC_BASELINE_ROOT / "publish" / "academic_pipeline_readiness.json",
        ACADEMIC_BASELINE_ROOT / "publish" / "academic_pipeline_readiness.json",
        name="academic-readiness-self",
    )
    changed_readiness = compare_json_files(
        ACADEMIC_BASELINE_ROOT / "publish" / "academic_pipeline_readiness.json",
        ACADEMIC_CANDIDATE_ROOT / "publish" / "academic_pipeline_readiness.json",
        name="academic-readiness-old-vs-new",
    )

    assert diff.has_changes
    assert "publish/academic_pipeline_readiness.json" in diff.changed_artifacts
    assert "consumer_ready" not in diff.readiness_changes
    assert diff.readiness_changes["failed_readiness_checks"] == (
        ("schema_generation_current",),
        (
            "operational_stability_ready",
            "parameter_utility_ready",
            "schema_generation_current",
        ),
    )
    assert diff.metric_deltas["benchmark.parameter_supported_ratio"] == pytest.approx(-0.1)
    assert same_hash.passed is True
    assert changed_readiness.passed is False
    assert changed_readiness.message == "json payload mismatch"


def test_academic_skg_summary_handles_fixture_placeholder_read_only() -> None:
    summary = load_academic_skg_summary(
        ACADEMIC_BASELINE_ROOT / "graph" / "scholar_knowledge.duckdb"
    )

    assert summary.exists is True
    assert summary.readable is False
    assert summary.tables == ()
    assert summary.warnings


def test_academic_skg_summary_reads_real_duckdb_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "scholar_knowledge.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE ac_skg_versions(version_id VARCHAR, created_at TIMESTAMP)")
        con.execute(
            """
            INSERT INTO ac_skg_versions VALUES
              ('v1', TIMESTAMP '2026-04-24 00:00:00'),
              ('v2', TIMESTAMP '2026-04-25 00:00:00')
            """
        )
        con.execute("CREATE TABLE ac_skg_edges(edge_id VARCHAR)")
        con.execute("INSERT INTO ac_skg_edges VALUES ('e1'), ('e2')")
    finally:
        con.close()

    summary = load_academic_skg_summary(db_path)

    assert summary.exists is True
    assert summary.readable is True
    assert summary.latest_version_id == "v2"
    assert summary.table_by_name("ac_skg_edges").row_count == 2
    assert summary.table_by_name("ac_skg_versions").row_count == 2
    assert summary.warnings == ()
