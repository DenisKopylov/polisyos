"""Exercise the public retained reference read against real isolated DuckDB bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.read_api import academic


def _snapshot(path: Path) -> academic.SourceSnapshot:
    return academic.SourceSnapshot(
        path=path,
        reference="fixture://retained",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


@pytest.fixture
def source_path(tmp_path: Path) -> Path:
    path = tmp_path / "source.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_skg_simulation_parameters AS "
            "SELECT 'n1' numeric_id, 'W1' openalex_id, 'avg_income' canonical_name, "
            "'[\"c1\"]' linked_claim_ids_json, '[\"e1\"]' linked_edges_json "
            "UNION ALL SELECT 'n2', 'W2', 'income_mean', '{}', NULL "
            "UNION ALL SELECT 'n3', 'W3', NULL, NULL, NULL"
        )
    return path


def test_complete_population_retains_unknown_and_malformed_candidate_rows(source_path, tmp_path):
    result = academic.read_source_reference_population(
        source=_snapshot(source_path), target_variable="avg_income", scratch=tmp_path / "spill"
    )
    assert result.status == "reference_population_recomputed"
    assert result.row_count == 3
    assert result.distinct_numeric_id_count == 3
    assert result.distinct_variable_name_count == 2
    assert len(result.literal_target_row_indices) == 1
    assert result.rows[result.literal_target_row_indices[0]].numeric_id == "n1"
    assert any(row.linked_claim_ids_json == "{}" for row in result.rows)
    assert result.scientific_eligibility == "not_established"
    assert result.semantic_target_coverage == "not_established"


@pytest.mark.parametrize("target", [None, "household_income", "AVG_INCOME"])
def test_no_literal_match_never_claims_semantic_absence(source_path, tmp_path, target):
    result = academic.read_source_reference_population(
        source=_snapshot(source_path), target_variable=target, scratch=tmp_path / "spill"
    )
    assert result.row_count == 3
    assert result.literal_target_row_indices == ()
    assert result.semantic_target_coverage == "not_established"


@pytest.mark.parametrize("mutation", ["view", "virtual", "nontext"])
def test_unretained_or_inexact_input_refuses_the_population(source_path, tmp_path, mutation):
    with duckdb.connect(str(source_path)) as con:
        if mutation == "view":
            con.execute("ALTER TABLE ac_skg_simulation_parameters RENAME TO original")
            con.execute("CREATE VIEW ac_skg_simulation_parameters AS SELECT * FROM original")
        elif mutation == "virtual":
            con.execute("ALTER TABLE ac_skg_simulation_parameters RENAME TO original")
            con.execute(
                "CREATE TABLE ac_skg_simulation_parameters "
                "(numeric_id VARCHAR, openalex_id VARCHAR, canonical_name VARCHAR, "
                "linked_claim_ids_json VARCHAR, linked_edges_json VARCHAR, "
                "derived VARCHAR GENERATED ALWAYS AS (numeric_id))"
            )
        else:
            con.execute("ALTER TABLE ac_skg_simulation_parameters DROP COLUMN numeric_id")
            con.execute("ALTER TABLE ac_skg_simulation_parameters ADD COLUMN numeric_id INTEGER")
    result = academic.read_source_reference_population(
        source=_snapshot(source_path), target_variable="avg_income", scratch=tmp_path / "spill"
    )
    assert result.status == "refused"
    assert result.row_count is None
    assert result.distinct_numeric_id_count is None
    assert result.distinct_variable_name_count is None
    assert result.projection_sha256 is None
    assert result.refusal_reasons


def test_snapshot_drift_is_not_a_new_owner_pin(source_path, tmp_path):
    snapshot = _snapshot(source_path)
    with duckdb.connect(str(source_path)) as con:
        con.execute("UPDATE ac_skg_simulation_parameters SET canonical_name='other'")
    with pytest.raises(ValueError, match="source_snapshot_hash_mismatch"):
        academic.read_source_reference_population(
            source=snapshot, target_variable="avg_income", scratch=tmp_path / "spill"
        )
