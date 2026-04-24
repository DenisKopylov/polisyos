"""Tests for transport_score stage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.transport_score import (
    _apply_moderation_penalty,
    _build_context_profiles,
    run_transport_score,
)
from polisyos.academic.knowledge.skg_store import ensure_skg_schema

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "graph" / "scholar_knowledge.duckdb"


def _setup_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    ensure_skg_schema(con)
    con.execute(
        "INSERT INTO ac_skg_versions(version_id, n_articles, n_edges, n_variables, description) "
        "VALUES (1, 0, 0, 0, 'test')"
    )
    return con


def test_no_moderators_no_penalty() -> None:
    assert _apply_moderation_penalty(0.8, []) == 0.8


def test_non_significant_moderator_no_penalty() -> None:
    mods = [{"moderator": "trust", "interaction_pvalue": 0.5}]
    assert _apply_moderation_penalty(0.8, mods) == 0.8


def test_significant_moderator_applies_penalty() -> None:
    mods = [{"moderator": "iq", "interaction_pvalue": 0.03}]
    assert _apply_moderation_penalty(0.8, mods) == pytest.approx(0.75)


def test_multiple_significant_moderators_capped() -> None:
    mods = [
        {"moderator": "iq", "interaction_pvalue": 0.01},
        {"moderator": "trust", "interaction_pvalue": 0.05},
        {"moderator": "income", "interaction_pvalue": 0.02},
        {"moderator": "openness", "interaction_pvalue": 0.08},
        {"moderator": "corruption", "interaction_pvalue": 0.001},
        {"moderator": "gdp", "interaction_pvalue": 0.04},
        {"moderator": "state_capacity", "interaction_pvalue": 0.09},
    ]
    # 7 significant moderators: strong_penalty = min(0.20, 0.05*7) = 0.20
    assert _apply_moderation_penalty(0.8, mods) == pytest.approx(0.6)


def test_build_profiles_empty_db(tmp_db: Path) -> None:
    con = _setup_db(tmp_db)
    try:
        assert _build_context_profiles(con, skg_version=1) == 0
    finally:
        con.close()


def test_build_profiles_with_data(tmp_db: Path) -> None:
    con = _setup_db(tmp_db)
    try:
        con.execute(
            "INSERT INTO ac_skg_context_attributes "
            "(attr_id, openalex_id, canonical_name, attribute_value, country_code, time_period, confidence, skg_version) "
            "VALUES "
            "('a1', 'W1', 'governance.iq', 0.85, 'US', '2015-2020', 0.9, 1),"
            "('a2', 'W2', 'governance.trust', 0.4, 'US', '2015-2020', 0.8, 1),"
            "('a3', 'W3', 'governance.iq', 0.6, 'DE', '2010-2015', 0.7, 1)"
        )
        count = _build_context_profiles(con, skg_version=1)
        assert count == 2

        rows = con.execute(
            "SELECT context_id, context_label FROM ac_skg_context_profiles ORDER BY context_id"
        ).fetchall()
        assert rows == [("DE", "DE (2010-2015)"), ("US", "US (2015-2020)")]
    finally:
        con.close()


def test_run_transport_score_no_db(tmp_path: Path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path)
    result = run_transport_score(config)
    assert result == {
        "edges_scored": 0,
        "moderators_applied": 0,
        "profiles_built": 0,
        "transport_scores_written": 0,
    }


def test_run_transport_score_empty_skg(tmp_path: Path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path)
    con = _setup_db(config.db_path)
    con.close()
    result = run_transport_score(config)
    assert result["edges_scored"] == 0
    assert result["moderators_applied"] == 0
    assert result["transport_scores_written"] == 0


def test_run_transport_score_counts_edges_without_moderators(tmp_path: Path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path)
    con = _setup_db(config.db_path)
    try:
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence) "
            "VALUES ('e1', 'policy', 'outcome', 'positive', 1, '[]', 'observational', 0.8)"
        )
    finally:
        con.close()

    result = run_transport_score(config)
    assert result["edges_scored"] == 1
    assert result["moderators_applied"] == 0
    assert result["transport_scores_written"] == 1

    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT base_confidence, generic_penalty, context_match_reward, transport_confidence, match_mode "
            "FROM ac_skg_transport_scores WHERE edge_id = 'e1'"
        ).fetchone()
    finally:
        con.close()

    assert row == (0.8, 0.0, 0.0, 0.8, "")


def test_run_transport_score_preserves_requested_target_context_without_profile(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path,
        transport_target_context_id="UA",
        transport_target_country_codes=("UA",),
    )
    con = _setup_db(config.db_path)
    try:
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence) "
            "VALUES ('e1', 'policy', 'outcome', 'positive', 1, '[]', 'observational', 0.7)"
        )
    finally:
        con.close()

    result = run_transport_score(config)
    assert result["transport_scores_written"] == 1

    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT target_context_id, transport_confidence FROM ac_skg_transport_scores WHERE edge_id = 'e1'"
        ).fetchone()
    finally:
        con.close()

    assert row == ("UA", pytest.approx(0.7))


def test_run_transport_score_writes_target_aware_scores_without_mutating_edges(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path,
        transport_target_country_codes=("US",),
        transport_target_time_period="2015-2020",
    )
    con = _setup_db(config.db_path)
    try:
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence) "
            "VALUES ('e1', 'fiscal.spending', 'economic.inflation', 'positive', 1, '[\"W1\"]', 'quasi_natural', 0.8)"
        )
        con.execute(
            "INSERT INTO ac_skg_moderation_edges "
            "(moderation_id, base_cause, base_effect, moderator, base_claim_id, direction_of_mod, "
            "interaction_coeff, interaction_pvalue, confidence, match_quality, alignment_source, source_refs, skg_version) "
            "VALUES "
            "('m1', 'fiscal.spending', 'economic.inflation', 'governance.institutional_quality', 'c1', "
            "'dampening', -0.15, 0.02, 0.85, 'exact_claim_ref', 'claim_inventory', '[\"W1\"]', 1)"
        )
        con.execute(
            "INSERT INTO ac_skg_context_attributes "
            "(attr_id, openalex_id, canonical_name, attribute_value, country_code, time_period, confidence, skg_version) "
            "VALUES "
            "('a1', 'W1', 'governance.institutional_quality', 0.8, 'US', '2015-2020', 0.9, 1),"
            "('a2', 'W2', 'governance.institutional_quality', 0.8, 'US', '2015-2020', 0.7, 1)"
        )
    finally:
        con.close()

    result = run_transport_score(config)
    assert result["edges_scored"] == 1
    assert result["moderators_applied"] == 1
    assert result["profiles_built"] == 1

    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        edge_conf = float(
            con.execute("SELECT confidence FROM ac_skg_edges WHERE edge_id = 'e1'").fetchone()[0]
        )
        transport_row = con.execute(
            "SELECT target_context_id, generic_penalty, context_match_reward, transport_confidence, match_mode "
            "FROM ac_skg_transport_scores WHERE edge_id = 'e1'"
        ).fetchone()
    finally:
        con.close()

    assert edge_conf == pytest.approx(0.8)
    assert transport_row[0] == "US"
    assert transport_row[1] == pytest.approx(0.05)
    assert transport_row[2] == pytest.approx(0.2)
    assert transport_row[3] == pytest.approx(0.95)
    assert transport_row[4] == "claim_ref"
    assert config.transport_scores_path.exists()
    assert (config.manifests_dir / "transport_score.json").exists()


def test_run_transport_score_uses_fuzzy_matching_for_moderators(tmp_path: Path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path)
    con = _setup_db(config.db_path)
    try:
        con.execute(
            "INSERT INTO ac_skg_edges "
            "(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence) "
            "VALUES ('e1', 'fiscal.government_tax_revenue', 'economic.growth', 'positive', 1, '[]', 'panel_fe', 0.6)"
        )
        con.execute(
            "INSERT INTO ac_skg_moderation_edges "
            "(moderation_id, base_cause, base_effect, moderator, direction_of_mod, "
            "interaction_coeff, interaction_pvalue, confidence, match_quality, alignment_source, source_refs, skg_version) "
            "VALUES "
            "('m1', 'fiscal.tax_revenue', 'economic.growth', 'trade.trade_openness', 'threshold', "
            "0.2, 0.04, 0.7, 'fuzzy_claim_inventory', 'fuzzy_pair', '[\"W1\"]', 1)"
        )
    finally:
        con.close()

    result = run_transport_score(config)
    assert result["edges_scored"] == 1
    assert result["moderators_applied"] == 1

    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT match_mode, generic_penalty FROM ac_skg_transport_scores WHERE edge_id = 'e1'"
        ).fetchone()
    finally:
        con.close()

    assert row == ("fuzzy", pytest.approx(0.05))
