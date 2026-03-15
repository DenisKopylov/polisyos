from __future__ import annotations

import json

import duckdb

from polisyos.datasets.batch.benchmark import BenchmarkSuite, SearchBenchmarkCase, run_benchmark
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord


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
            "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

    with open(outcome.report_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["kind"] == "datasets_benchmark"
    assert len(payload["search"]["cases"]) == 2


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
            "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
