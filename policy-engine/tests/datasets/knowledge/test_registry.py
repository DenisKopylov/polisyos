from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from polisyos.datasets.knowledge.registry import DatasetRegistry


def _build_registry_db(tmpdir: str) -> Path:
    db_path = Path(tmpdir) / "registry.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ds_registry_datasets (
                dataset_id VARCHAR PRIMARY KEY,
                provider VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                coverage_json VARCHAR NOT NULL,
                access_json VARCHAR NOT NULL,
                update_freq VARCHAR NOT NULL,
                last_updated VARCHAR NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE ds_variable_alignments (
                dataset_id VARCHAR NOT NULL,
                raw_variable VARCHAR NOT NULL,
                canonical_var VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                evidence VARCHAR NOT NULL,
                is_proxy BOOLEAN DEFAULT FALSE,
                proxy_penalty FLOAT DEFAULT 0.0,
                PRIMARY KEY (dataset_id, raw_variable, canonical_var)
            );
            """
        )
        con.execute(
            """
            CREATE TABLE ds_observations (
                observation_id VARCHAR PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                raw_variable VARCHAR NOT NULL,
                canonical_var VARCHAR NOT NULL,
                country_code VARCHAR NOT NULL,
                year INTEGER,
                survey_year INTEGER,
                wave INTEGER,
                value DOUBLE,
                condition_json VARCHAR DEFAULT '{}'
            );
            """
        )

        con.executemany(
            "INSERT INTO ds_registry_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "WB_WGI",
                    "world_bank",
                    "World Governance Indicators",
                    json.dumps({"countries": ["UA", "DE"], "time_range": "1996-2023"}),
                    json.dumps({"access_type": "open"}),
                    "annual",
                    "2026-01-01",
                ),
                (
                    "TI_CPI",
                    "transparency_international",
                    "Corruption Perceptions Index",
                    json.dumps({"countries": ["UA", "DE"], "time_range": "2012-2023"}),
                    json.dumps({"access_type": "open"}),
                    "annual",
                    "2026-01-01",
                ),
                (
                    "WVS_W7",
                    "world_values_survey",
                    "WVS Wave 7",
                    json.dumps({"countries": ["UA", "DE"], "time_range": "2017-2022"}),
                    json.dumps({"access_type": "open"}),
                    "wave",
                    "2026-01-01",
                ),
            ],
        )
        con.executemany(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("WB_WGI", "RL.EST", "institutional_quality", "exact", 0.92, "direct", False, 0.0),
                ("TI_CPI", "cpi_score", "institutional_quality", "exact", 0.78, "proxy", True, 0.2),
                ("WVS_W7", "A165", "social_trust", "exact", 0.95, "direct", False, 0.0),
            ],
        )
        con.executemany(
            "INSERT INTO ds_observations "
            "(observation_id, dataset_id, raw_variable, canonical_var, country_code, year, survey_year, wave, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "obs1",
                    "WB_WGI",
                    "RL.EST",
                    "institutional_quality",
                    "UA",
                    2020,
                    None,
                    None,
                    0.5,
                    "{}",
                ),
                (
                    "obs2",
                    "TI_CPI",
                    "cpi_score",
                    "institutional_quality",
                    "UA",
                    2020,
                    None,
                    None,
                    0.4,
                    "{}",
                ),
                ("obs3", "WVS_W7", "A165", "social_trust", "UA", 2020, 2020, 7, 0.6, "{}"),
                ("obs4", "WVS_W7", "A165", "social_trust", "DE", 2018, 2018, 7, 0.55, "{}"),
            ],
        )
    finally:
        con.close()
    return db_path


def test_find_datasets_for_variable_orders_direct_before_proxy() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        matches = registry.find_datasets_for_variable("institutional_quality", "UA", (2020, 2020))
        assert len(matches) >= 2
        assert matches[0].is_proxy is False
        assert any(match.is_proxy for match in matches)


def test_find_datasets_for_variable_wave_closest() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        matches = registry.find_datasets_for_variable("social_trust", "DE", (2020, 2020))
        assert len(matches) >= 1
        assert matches[0].temporal_match == "wave_closest"
        assert matches[0].actual_survey_year == 2018


def test_compute_p_star_z_point_estimate() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        result = registry.compute_p_star_z("institutional_quality", "UA", 2020)
        assert result.value is not None
        assert abs(result.value - 0.5) < 1e-9
        assert result.dataset_id == "WB_WGI"
        assert result.raw_variable == "RL.EST"


def test_compute_p_star_z_returns_none_when_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        result = registry.compute_p_star_z("missing_variable", "UA", 2020)
        assert result.value is None
        assert result.dataset_id is None


def test_compute_p_star_z_conditional_graceful_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        result = registry.compute_p_star_z(
            "social_trust",
            "UA",
            2020,
            condition_on={"tax_rate": 0.2},
        )
        assert result.value is None
        assert result.is_conditional is True
        assert result.penalty_breakdown.get("condition_variables_missing") == 1.0


def test_compute_p_star_z_conditional_never_silently_returns_marginal() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        result = registry.compute_p_star_z(
            "institutional_quality",
            "UA",
            2020,
            condition_on={"institutional_quality": 0.5},
        )
        assert result.value is None
        assert result.is_conditional is True
        assert result.penalty_breakdown.get("conditional_filter_unavailable") == 1.0


def test_find_datasets_for_variables_bulk_groups_results() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _build_registry_db(tmpdir)
        registry = DatasetRegistry(db_path)
        results = registry.find_datasets_for_variables_bulk(
            ["institutional_quality", "social_trust"],
            "UA",
            (2020, 2020),
        )

        assert "institutional_quality" in results
        assert "social_trust" in results
        assert results["institutional_quality"]
        assert results["social_trust"]
