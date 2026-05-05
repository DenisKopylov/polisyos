"""Tests for dataset graph builder (DuckDB schema + bulk INSERT)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord


def _make_record(idx: int) -> DatasetRecord:
    return DatasetRecord(
        id=f"ds-{idx}",
        title=f"Dataset {idx}",
        description=f"Description for dataset {idx}",
        publisher="test-publisher",
        themes=["economics"],
        keywords=["GDP", "growth"],
        variables=["GDP", "NY.GDP.MKTP.CD"],
        spatial="US",
        temporal_start="2000",
        temporal_end="2020",
        license="CC-BY-4.0",
        formats=["CSV", "JSON"],
        distributions=[
            DistributionRecord(
                id=f"dist-{idx}-1",
                url=f"http://example.com/{idx}.csv",
                format="CSV",
                connector_type="rest.json",
                connector_params={"url": f"http://example.com/{idx}.csv"},
                source_locator=f"http://example.com/{idx}.csv",
                parser_supported=True,
                machine_readable=True,
            ),
        ],
        polisyos_metrics=["gdp"],
        source_portal="test_portal",
        source="test",
        execution_tier="fetchable",
        preferred_distribution_id=f"dist-{idx}-1",
    )


def test_build_graph_creates_tables_and_inserts() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        records = [_make_record(i) for i in range(5)]

        stats = build_graph(
            records=iter(records),
            db_path=db_path,
            insert_batch_size=3,
        )

        assert stats.datasets == 5
        assert stats.distributions == 5
        assert stats.metric_bindings == 5
        assert stats.schema_profiles == 5

        con = duckdb.connect(str(db_path), read_only=True)
        ds_count = con.execute("SELECT count(*) FROM ds_datasets").fetchone()[0]
        dist_count = con.execute("SELECT count(*) FROM ds_distributions").fetchone()[0]
        binding_count = con.execute("SELECT count(*) FROM ds_metric_bindings").fetchone()[0]
        schema_count = con.execute("SELECT count(*) FROM ds_schema_profiles").fetchone()[0]
        con.close()

        assert ds_count == 5
        assert dist_count == 5
        assert binding_count == 5
        assert schema_count == 5


def test_build_graph_stores_arrays() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        records = [_make_record(0)]

        build_graph(records=iter(records), db_path=db_path)

        con = duckdb.connect(str(db_path), read_only=True)
        row = con.execute(
            "SELECT polisyos_metrics, keywords, variables FROM ds_datasets WHERE id = 'ds-0'"
        ).fetchone()
        con.close()

        assert row is not None
        assert "gdp" in row[0]
        assert "GDP" in row[1]
        assert "NY.GDP.MKTP.CD" in row[2]


def test_build_graph_empty_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        stats = build_graph(records=iter([]), db_path=db_path)
        assert stats.datasets == 0
        assert stats.distributions == 0


def test_build_graph_creates_registry_tables() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_catalog.duckdb"
        records = [_make_record(0)]
        build_graph(records=iter(records), db_path=db_path)

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }
        finally:
            con.close()

        assert "ds_registry_datasets" in tables
        assert "ds_variable_alignments" in tables
        assert "ds_observations" in tables
        assert "ds_metric_bindings" in tables
        assert "ds_schema_profiles" in tables
