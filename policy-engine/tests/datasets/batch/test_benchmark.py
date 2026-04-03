from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.datasets.batch.benchmark import BenchmarkSuite, SearchBenchmarkCase, run_benchmark
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord


def _write_test_registry(path: Path, entries: list[dict[str, object]]) -> None:
    lines = ["version: 1", "sources:"]
    for entry in entries:
        lines.extend(
            [
                f"  - name: {entry['name']}",
                f"    family: {entry['family']}",
                f"    wave: {entry.get('wave', 'A')}",
                f"    endpoint: {entry.get('endpoint', 'https://example.test/' + str(entry['name']))}",
                f"    enabled: {str(entry.get('enabled', True)).lower()}",
                f"    execution_tier: {entry.get('execution_tier', 'fetchable')}",
                f"    run_lane: {entry.get('run_lane', 'empirical')}",
                f"    publish_blocking: {str(entry.get('publish_blocking', True)).lower()}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_benchmark_fixture(config: DatasetBatchConfig) -> None:
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-gdp",
                    title="GDP per capita by country",
                    description="Annual GDP per capita indicator",
                    source="worldbank",
                    source_portal="worldbank",
                    dataset_id="NY.GDP.PCAP.CD",
                    source_dataset_id="NY.GDP.PCAP.CD",
                    execution_tier="transport_ready",
                    update_frequency="annual",
                    polisyos_metrics=["gdp_per_capita"],
                    variables=["country_code", "year", "value"],
                    preferred_distribution_id="dist-gdp",
                    distributions=[
                        DistributionRecord(
                            id="dist-gdp",
                            connector_type="worldbank.wdi",
                            source_locator="NY.GDP.PCAP.CD",
                            profile_id="worldbank_wdi",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.9,
                        )
                    ],
                ),
                DatasetRecord(
                    id="ds-unemp",
                    title="Unemployment rate annual",
                    description="Labor market unemployment rate",
                    source="ilo",
                    source_portal="ilo",
                    dataset_id="UNE_RATE",
                    source_dataset_id="UNE_RATE",
                    execution_tier="transport_ready",
                    update_frequency="annual",
                    polisyos_metrics=["unemployment_rate"],
                    variables=["country_code", "year", "value"],
                    preferred_distribution_id="dist-unemp",
                    distributions=[
                        DistributionRecord(
                            id="dist-unemp",
                            connector_type="sdmx.source",
                            source_locator="UNE_RATE",
                            profile_id="ilo_sdmx",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.8,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    con = duckdb.connect(str(config.db_path))
    try:
        con.executemany(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "ds-gdp",
                    "worldbank",
                    "GDP per capita by country",
                    json.dumps({"countries": ["UA"], "time_range": "2020-2020"}),
                    json.dumps({"access_type": "open"}),
                    "annual",
                    "2026-01-01",
                ),
                (
                    "ds-unemp",
                    "ilo",
                    "Unemployment rate annual",
                    json.dumps({"countries": ["UA"], "time_range": "2020-2020"}),
                    json.dumps({"access_type": "open"}),
                    "annual",
                    "2026-01-01",
                ),
            ],
        )
        con.executemany(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ds-gdp", "value", "gdp_per_capita", "exact", 0.95, "seed", False, 0.0),
                ("ds-unemp", "value", "unemployment_rate", "exact", 0.95, "seed", False, 0.0),
            ],
        )
        con.executemany(
            "INSERT INTO ds_observations "
            "(observation_id, dataset_id, raw_variable, canonical_var, country_code, year, survey_year, wave, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("obs-gdp", "ds-gdp", "value", "gdp_per_capita", "UA", 2020, None, None, 1000.0, "{}"),
                ("obs-unemp", "ds-unemp", "value", "unemployment_rate", "UA", 2020, None, None, 8.0, "{}"),
            ],
        )
    finally:
        con.close()


def test_run_benchmark_writes_report_and_metrics(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    _build_benchmark_fixture(config)

    suite = BenchmarkSuite(
        search_cases=(
            SearchBenchmarkCase(
                case_id="gdp",
                query="gdp per capita",
                expected_metrics=("gdp_per_capita",),
                expected_sources=("worldbank",),
            ),
            SearchBenchmarkCase(
                case_id="unemployment",
                query="unemployment rate",
                expected_metrics=("unemployment_rate",),
                expected_sources=("ilo",),
            ),
        ),
        retrieval_metrics=("gdp_per_capita", "unemployment_rate"),
        transport_variables=("gdp_per_capita", "unemployment_rate"),
        foundry_metrics=("gdp_per_capita", "unemployment_rate"),
    )

    outcome = run_benchmark(config, suite=suite)

    assert outcome.report_path.exists()
    assert outcome.metrics["benchmark_search_top5_relevance_pct"] == 100.0
    assert outcome.metrics["benchmark_retrieval_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_transport_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_foundry_fitness_pct"] == 100.0
    assert "benchmark_source_preflight_ready_pct" in outcome.metrics

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["kind"] == "datasets_benchmark"
    assert len(payload["search"]["cases"]) == 2
    assert "source_preflight" in payload


def test_run_benchmark_accepts_alias_metrics_for_retrieval_transport_and_foundry(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-health",
                    title="Life expectancy by country",
                    description="Healthy life expectancy indicator",
                    source="who",
                    source_portal="who",
                    dataset_id="LE_001",
                    source_dataset_id="LE_001",
                    execution_tier="transport_ready",
                    update_frequency="annual",
                    polisyos_metrics=["life_expectancy"],
                    variables=["country_code", "year", "value"],
                    preferred_distribution_id="dist-health",
                    distributions=[
                        DistributionRecord(
                            id="dist-health",
                            connector_type="who.indicators",
                            source_locator="LE_001",
                            profile_id="who_gho",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.9,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    con = duckdb.connect(str(config.db_path))
    try:
        con.execute(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-health",
                "who",
                "Life expectancy by country",
                json.dumps({"countries": ["UA"], "time_range": "2020-2020"}),
                json.dumps({"access_type": "open"}),
                "annual",
                "2026-01-01",
            ],
        )
        con.execute(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-health",
                "value",
                "life_expectancy",
                "exact",
                0.95,
                "seed",
                False,
                0.0,
            ],
        )
        con.execute(
            "INSERT INTO ds_observations "
            "(observation_id, dataset_id, raw_variable, canonical_var, country_code, year, survey_year, wave, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "obs-health",
                "ds-health",
                "value",
                "life_expectancy",
                "UA",
                2020,
                None,
                None,
                72.1,
                "{}",
            ],
        )
    finally:
        con.close()

    suite = BenchmarkSuite(
        search_cases=(
            SearchBenchmarkCase(
                case_id="health",
                query="life expectancy",
                expected_metrics=("health_outcomes",),
                expected_sources=("who",),
            ),
        ),
        retrieval_metrics=("health_outcomes",),
        transport_variables=("health_outcomes",),
        foundry_metrics=("health_outcomes",),
    )

    outcome = run_benchmark(config, suite=suite)

    assert outcome.metrics["benchmark_search_top5_relevance_pct"] == 100.0
    assert outcome.metrics["benchmark_retrieval_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_transport_ready_pct"] == 100.0
    assert outcome.metrics["benchmark_foundry_fitness_pct"] == 100.0


def test_run_benchmark_aggregates_bulk_equivalence_manifests(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    _build_benchmark_fixture(config)

    manifest_root = config.manifests_dir / "observations" / "bulk_equivalence"
    (manifest_root / "eurostat" / "v1").mkdir(parents=True, exist_ok=True)
    (manifest_root / "ilo" / "v2").mkdir(parents=True, exist_ok=True)
    (manifest_root / "eurostat" / "v1" / "une_rt_a.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "source": "eurostat",
                "dataset_id": "une_rt_a",
                "dataset_version": "v1",
                "compared_series": 25,
                "mismatches": 1,
                "blocking": True,
            }
        ),
        encoding="utf-8",
    )
    (manifest_root / "ilo" / "v2" / "emp.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "source": "ilo",
                "dataset_id": "EMP_TEMP_SEX_IND_OCU_NB_A",
                "dataset_version": "v2",
                "compared_series": 50,
                "mismatches": 1,
                "blocking": False,
            }
        ),
        encoding="utf-8",
    )

    outcome = run_benchmark(config)

    assert outcome.metrics["benchmark_bulk_equivalence_mismatch_rate"] == round((2 / 75) * 100.0, 2)
    assert outcome.metrics["benchmark_bulk_equivalence_blocking_sources_total"] == 1

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert len(payload["bulk_equivalence"]["manifests"]) == 2


def test_run_benchmark_marks_partial_eval_when_core_ingest_is_blocked(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(
        registry_path,
        [
            {
                "name": "oecd",
                "family": "sdmx",
                "execution_tier": "fetchable",
                "run_lane": "empirical",
                "publish_blocking": True,
            }
        ],
    )
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    (raw_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source": "oecd",
                "endpoint": "https://example.test",
                "payload": str(payload),
                "count": 1,
            }
        ),
        encoding="utf-8",
    )

    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-inflation",
                    title="Inflation index",
                    description="Inflation index dataset",
                    source="oecd",
                    source_portal="oecd",
                    dataset_id="DF_TEST",
                    source_dataset_id="DF_TEST",
                    execution_tier="transport_ready",
                    update_frequency="annual",
                    polisyos_metrics=["inflation"],
                    variables=["country_code", "year", "value"],
                    preferred_distribution_id="dist-inflation",
                    distributions=[
                        DistributionRecord(
                            id="dist-inflation",
                            connector_type="sdmx.source",
                            source_locator="DF_TEST",
                            profile_id="oecd_sdmx",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.9,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    con = duckdb.connect(str(config.db_path))
    try:
        con.execute(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-inflation",
                "oecd",
                "Inflation index",
                json.dumps({"countries": ["UA"], "time_range": "2022-2022"}),
                json.dumps({"access_type": "open"}),
                "annual",
                "2026-01-01",
            ],
        )
        con.execute(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-inflation",
                "value",
                "inflation",
                "exact",
                0.95,
                "seed",
                False,
                0.0,
            ],
        )
    finally:
        con.close()

    config.stage_state_path.write_text(
        json.dumps(
            {
                "core_sources_ingest": {
                    "status": "running",
                    "metadata": {
                        "current_phase": "planning",
                        "blocked_by_source": {"oecd": 1},
                        "quota_wait_seconds_by_source": {"oecd": 60.0},
                        "capability_failures_by_source": {"oecd": 1},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    suite = BenchmarkSuite(
        search_cases=(
            SearchBenchmarkCase(
                case_id="inflation",
                query="inflation index",
                expected_metrics=("inflation",),
                expected_sources=("oecd",),
            ),
        ),
        retrieval_metrics=("inflation",),
        transport_variables=("inflation",),
        foundry_metrics=("inflation",),
    )

    outcome = run_benchmark(config, suite=suite)
    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["evaluation_mode"] == "partial-eval"
    assert payload["diagnostic_context"]["blocked"] is True
    assert payload["transport"]["variables"][0]["alignment_present_without_observations"] is True
    assert payload["transport"]["variables"][0]["observation_missing_due_to_stage_block"] is True
    assert payload["source_preflight"]["sources"][0]["source_blocked_by_quota"] is True
    assert payload["source_preflight"]["sources"][0]["failure_reason"] == "ingest_blocked"


def test_foundry_benchmark_prefers_execution_grade_alias_binding_over_catalog_exact(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-catalog-health",
                    title="Health glossary broad catalog record",
                    description="Catalog-level health reference entry",
                    source="data_gov_ua_broad",
                    source_portal="data_gov_ua_broad",
                    dataset_id="ua-health-catalog",
                    source_dataset_id="ua-health-catalog",
                    execution_tier="catalog",
                    polisyos_metrics=["health_outcomes"],
                    preferred_distribution_id="dist-catalog-health",
                    distributions=[
                        DistributionRecord(
                            id="dist-catalog-health",
                            connector_type="ckan.resource",
                            source_locator="ua-health-catalog/resource-1",
                            profile_id="data_gov_ua_ckan",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.5,
                        )
                    ],
                ),
                DatasetRecord(
                    id="ds-life",
                    title="Life expectancy by country",
                    description="Healthy life expectancy indicator",
                    source="who",
                    source_portal="who",
                    dataset_id="WHOSIS_000001",
                    source_dataset_id="WHOSIS_000001",
                    execution_tier="transport_ready",
                    update_frequency="annual",
                    polisyos_metrics=["life_expectancy"],
                    variables=["country_code", "year", "value"],
                    preferred_distribution_id="dist-life",
                    distributions=[
                        DistributionRecord(
                            id="dist-life",
                            connector_type="who.indicators",
                            source_locator="WHOSIS_000001",
                            profile_id="who_gho",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.9,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    con = duckdb.connect(str(config.db_path))
    try:
        con.execute(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-life",
                "who",
                "Life expectancy by country",
                json.dumps({"countries": ["UA"], "time_range": "2020-2020"}),
                json.dumps({"access_type": "open"}),
                "annual",
                "2026-01-01",
            ],
        )
        con.execute(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "ds-life",
                "value",
                "life_expectancy",
                "exact",
                0.95,
                "seed",
                False,
                0.0,
            ],
        )
        con.execute(
            "INSERT INTO ds_observations "
            "(observation_id, dataset_id, raw_variable, canonical_var, country_code, year, survey_year, wave, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "obs-life",
                "ds-life",
                "value",
                "life_expectancy",
                "UA",
                2020,
                None,
                None,
                72.1,
                "{}",
            ],
        )
    finally:
        con.close()

    suite = BenchmarkSuite(
        search_cases=(),
        retrieval_metrics=(),
        transport_variables=(),
        foundry_metrics=("health_outcomes",),
    )

    outcome = run_benchmark(config, suite=suite)

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    result = payload["foundry"]["metrics"][0]
    assert result["dataset_id"] == "ds-life"
    assert result["execution_tier"] == "transport_ready"
    assert result["fit"] is True


def test_run_benchmark_adds_romania_search_cases_when_source_present(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-ro-budget",
                    title="Buget local municipiu Romania",
                    description="Date despre buget local si cheltuieli municipale",
                    source="data_gov_ro_broad",
                    source_portal="data_gov_ro_broad",
                    dataset_id="ro-budget-1",
                    source_dataset_id="ro-budget-1",
                    execution_tier="catalog",
                    update_frequency="irregular",
                    themes=["buget", "municipal"],
                    preferred_distribution_id="dist-ro-budget",
                    distributions=[
                        DistributionRecord(
                            id="dist-ro-budget",
                            connector_type="ckan.resource",
                            source_locator="ro-budget-1/res-1",
                            profile_id="data_gov_ro",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.8,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    outcome = run_benchmark(config)

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    case_ids = {case["case_id"] for case in payload["suite"]["search_cases"]}
    assert "romania_budget" in case_ids
    assert "romania_eu_comparator" in case_ids


def test_run_benchmark_adds_poland_and_moldova_cases_when_sources_present(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-pl-budget",
                    title="Budzet lokalny miasta Polska",
                    description="Dane o dochodach i wydatkach budzetowych",
                    source="data_gov_pl_broad",
                    source_portal="data_gov_pl_broad",
                    dataset_id="pl-budget-1",
                    source_dataset_id="pl-budget-1",
                    execution_tier="catalog",
                    update_frequency="irregular",
                    themes=["budzet", "samorzad"],
                    preferred_distribution_id="dist-pl-budget",
                    distributions=[
                        DistributionRecord(
                            id="dist-pl-budget",
                            connector_type="rest.json",
                            source_locator="https://api.dane.gov.pl/1.4/datasets/1/resources",
                            profile_id="data_gov_pl",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.8,
                        )
                    ],
                ),
                DatasetRecord(
                    id="ds-md-budget",
                    title="Buget local Moldova",
                    description="Date despre buget local si cheltuieli municipale",
                    source="data_gov_md_broad",
                    source_portal="data_gov_md_broad",
                    dataset_id="md-budget-1",
                    source_dataset_id="md-budget-1",
                    execution_tier="catalog",
                    update_frequency="irregular",
                    themes=["buget", "municipal"],
                    preferred_distribution_id="dist-md-budget",
                    distributions=[
                        DistributionRecord(
                            id="dist-md-budget",
                            connector_type="ckan.resource",
                            source_locator="md-budget-1/res-1",
                            profile_id="data_gov_md",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.8,
                        )
                    ],
                ),
            ]
        ),
        db_path=config.db_path,
    )

    outcome = run_benchmark(config)

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    case_ids = {case["case_id"] for case in payload["suite"]["search_cases"]}
    assert "poland_budget" in case_ids
    assert "moldova_budget" in case_ids


def test_source_preflight_requires_positive_empirical_rows_for_transport_source(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(
        registry_path,
        [
            {
                "name": "worldbank",
                "family": "worldbank",
                "execution_tier": "transport_ready",
            }
        ],
    )
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_benchmark_fixture(config)

    raw_dir = config.raw_dir / "worldbank" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"NY.GDP.PCAP.CD"}\n', encoding="utf-8")
    with open(raw_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump({"count": 1, "payload": str(payload)}, fh)
    with open(config.manifests_dir / "observation_source_summary.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "worldbank": {
                    "complete": 1,
                    "complete_with_rows": 0,
                    "complete_empty": 1,
                    "failed": 0,
                    "deferred": 0,
                    "rows": 0,
                }
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    outcome = run_benchmark(
        config,
        suite=BenchmarkSuite(search_cases=(), retrieval_metrics=(), transport_variables=(), foundry_metrics=()),
    )

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    case = payload["source_preflight"]["sources"][0]

    assert case["status"] == "complete"
    assert case["empirical_status"] == "complete_empty"
    assert case["ready"] is False


def test_source_preflight_counts_exec_graph_artifacts_without_registry_rows(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(
        registry_path,
        [
            {
                "name": "data_gov_ua_exec",
                "family": "ckan",
                "execution_tier": "fetchable",
            }
        ],
    )
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-ua-exec",
                    title="UA execution dataset",
                    description="Fetchable curated execution slice",
                    source="data_gov_ua_exec",
                    source_portal="data_gov_ua_exec",
                    dataset_id="ua-exec-1",
                    source_dataset_id="ua-exec-1",
                    execution_tier="fetchable",
                    polisyos_metrics=["gdp_per_capita"],
                    preferred_distribution_id="dist-ua-exec",
                    distributions=[
                        DistributionRecord(
                            id="dist-ua-exec",
                            connector_type="ckan.resource",
                            source_locator="ua-exec-1/resource-1",
                            profile_id="data_gov_ua_ckan",
                            parser_supported=True,
                            machine_readable=True,
                            quality_score=0.9,
                        )
                    ],
                )
            ]
        ),
        db_path=config.db_path,
    )

    raw_dir = config.raw_dir / "data_gov_ua_exec" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"ua-exec-1"}\n', encoding="utf-8")
    with open(raw_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump({"count": 1, "payload": str(payload)}, fh)
    with open(config.manifests_dir / "observation_source_summary.json", "w", encoding="utf-8") as fh:
        json.dump({}, fh)

    outcome = run_benchmark(
        config,
        suite=BenchmarkSuite(search_cases=(), retrieval_metrics=(), transport_variables=(), foundry_metrics=()),
    )

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    case = payload["source_preflight"]["sources"][0]

    assert case["catalog_count"] >= 1
    assert case["binding_count"] >= 1
    assert case["ready"] is True
