"""Tests for DatasetCatalogStore (DuckDB read-only queries)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.knowledge.search import DatasetCatalogGraph
from polisyos.datasets.knowledge.store import DatasetCatalogStore
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord


def _build_test_db(tmpdir: str) -> Path:
    db_path = Path(tmpdir) / "test_catalog.duckdb"
    records = [
        DatasetRecord(
            id="ds-gdp",
            title="GDP per capita by country",
            description="Annual GDP per capita, World Bank data",
            publisher="World Bank",
            themes=["economics"],
            keywords=["GDP", "per capita"],
            variables=["NY.GDP.PCAP.CD"],
            polisyos_metrics=["gdp", "avg_income"],
            spatial="WORLD",
            source_portal="worldbank",
            formats=["JSON"],
            distributions=[
                DistributionRecord(
                    id="dist-gdp-1",
                    url="https://api.worldbank.org/v2/data",
                    format="JSON",
                    connector_type="worldbank.wdi",
                    connector_params={"indicator_id": "NY.GDP.PCAP.CD"},
                    source_locator="NY.GDP.PCAP.CD",
                    parser_supported=True,
                    machine_readable=True,
                    profile_id="worldbank_wdi",
                    quality_score=0.9,
                ),
            ],
            source="worldbank",
            source_dataset_id="NY.GDP.PCAP.CD",
            execution_tier="fetchable",
            preferred_distribution_id="dist-gdp-1",
        ),
        DatasetRecord(
            id="ds-unemp",
            title="Unemployment rate, annual",
            description="Unemployment by country",
            publisher="ILO",
            variables=["SL.UEM.TOTL.ZS"],
            polisyos_metrics=["unemployment_rate"],
            source_portal="worldbank",
            formats=["CSV"],
            distributions=[],
        ),
    ]
    build_graph(records=iter(records), db_path=db_path)
    return db_path


def test_search_by_text() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)  # No HNSW for text-only test
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.search_by_text("GDP", top_k=10)
            assert len(results) >= 1
            assert any("GDP" in r.title for r in results)
        finally:
            store.close()


def test_find_by_polisyos_metric() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_polisyos_metric("gdp")
            assert len(results) >= 1
            assert "gdp" in results[0].polisyos_metrics
        finally:
            store.close()


def test_resolve_metric_bindings() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            bindings = store.resolve_metric_bindings("gdp")
            assert len(bindings) == 1
            assert bindings[0].request_dataset_id == "NY.GDP.PCAP.CD"
            assert bindings[0].connector_id == "worldbank.wdi"
        finally:
            store.close()


def test_find_by_variables() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_variables(["NY.GDP.PCAP.CD"])
            assert len(results) >= 1
        finally:
            store.close()


def test_find_by_variables_empty() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.find_by_variables([])
            assert results == []
        finally:
            store.close()


def test_get_connector_params() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            connector = store.get_connector_params("ds-gdp")
            assert connector is not None
            assert connector["type"] == "worldbank.wdi"
            assert connector["dataset_id"] == "NY.GDP.PCAP.CD"
        finally:
            store.close()


def test_get_connector_params_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            connector = store.get_connector_params("nonexistent-id")
            assert connector is None
        finally:
            store.close()


def test_get_distributions() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            dists = store.get_distributions("ds-gdp")
            assert len(dists) == 1
            assert dists[0].connector_type == "worldbank.wdi"
            assert dists[0].parser_supported is True
        finally:
            store.close()


def test_resolve_fetch_target() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            target = store.resolve_fetch_target("ds-gdp")
            assert target is not None
            assert target.connector_id == "worldbank.wdi"
            assert target.request_dataset_id == "NY.GDP.PCAP.CD"
            assert target.profile_id == "worldbank_wdi"
        finally:
            store.close()


def test_search_by_text_matches_metric_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        index_dir = Path(tmpdir)
        store = DatasetCatalogStore(db_path, index_dir)
        try:
            results = store.search_by_text("avg_income", top_k=10)
            assert len(results) >= 1
            assert results[0].id == "ds-gdp"
        finally:
            store.close()


def test_graph_search_datasets_expands_ukrainian_query_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_test_db(tmpdir)
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.search_datasets("ввп на душу населення", top_k=5)
            assert results
            assert results[0].id == "ds-gdp"
        finally:
            graph.close()


def test_graph_search_datasets_boosts_country_specific_sources() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        build_graph(
            records=iter(
                [
                    DatasetRecord(
                        id="ds-ro-health",
                        title="CHELTUIELI PENTRU SANATATE",
                        description="Sanatate publica si spitale",
                        source="data_gov_ro",
                        source_portal="data_gov_ro",
                        dataset_id="ro-health-1",
                        formats=["XLSX"],
                        distributions=[],
                    ),
                    DatasetRecord(
                        id="ds-md-health",
                        title="Statistica gender: Sanatatea femeilor in Moldova",
                        description="Sanatate publica in Republica Moldova",
                        source="data_gov_md",
                        source_portal="data_gov_md",
                        dataset_id="md-health-1",
                        formats=["XLSX"],
                        distributions=[],
                    ),
                ]
            ),
            db_path=db_path,
        )
        graph = DatasetCatalogGraph(db_path, Path(tmpdir))
        try:
            results = graph.search_datasets("sanatate publica romania", top_k=5)
            assert results
            assert results[0].id == "ds-ro-health"
        finally:
            graph.close()
