from __future__ import annotations

import json

import duckdb

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel


def _seed_skg_tables(db_path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_edges (
                edge_id VARCHAR,
                src VARCHAR,
                dst VARCHAR,
                direction VARCHAR,
                n_articles INTEGER,
                article_refs VARCHAR,
                evidence_strength VARCHAR,
                confidence DOUBLE,
                scope_conditions VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE ac_skg_versions (version_id INTEGER)")
        con.execute(
            """
            CREATE TABLE ac_skg_parameters (
                param_id VARCHAR,
                canonical_name VARCHAR,
                openalex_id VARCHAR,
                parameter_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_simulation_parameters (
                numeric_id VARCHAR,
                openalex_id VARCHAR,
                canonical_name VARCHAR,
                estimate_type VARCHAR,
                point_estimate DOUBLE,
                estimate_sign VARCHAR,
                unit VARCHAR,
                evidence_strength VARCHAR,
                confidence_interval_json VARCHAR,
                std_error DOUBLE,
                linked_claim_ids_json VARCHAR,
                linked_edges_json VARCHAR,
                context_json VARCHAR,
                source_layer VARCHAR,
                uncertainty_source VARCHAR,
                quality_flags_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_family_edges (
                family_edge_id VARCHAR,
                src_family VARCHAR,
                dst_family VARCHAR,
                direction VARCHAR,
                n_articles INTEGER,
                n_claims INTEGER,
                article_refs VARCHAR,
                claim_refs VARCHAR,
                evidence_strength VARCHAR,
                confidence DOUBLE,
                quality_signals_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_context_profiles (
                profile_id VARCHAR,
                context_id VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_transport_scores (
                transport_id VARCHAR,
                edge_id VARCHAR,
                target_context_id VARCHAR,
                base_confidence DOUBLE,
                generic_penalty DOUBLE,
                context_match_reward DOUBLE,
                transport_confidence DOUBLE,
                match_mode VARCHAR,
                matched_moderators_json VARCHAR,
                skg_version INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_moderation_edges (
                moderation_id VARCHAR,
                moderator VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edges VALUES
            ('e1', 'macro.tax', 'macro.employment', 'positive', 3, '["W1","W2"]', 'rct', 0.84, '["OECD"]'),
            ('e2', 'macro.inflation', 'macro.employment', 'negative', 2, '["W3"]', 'observational', 0.62, '["EU"]'),
            ('e3', 'health.bmi', 'health.mortality', 'positive', 2, '["W4"]', 'quasi_natural', 0.77, '["adults"]')
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_parameters VALUES (?, ?, ?, ?, ?)
            """,
            [
                "p1",
                "fiscal_multiplier",
                "W_cee",
                json.dumps(
                    {
                        "value": 1.4,
                        "ci_low": 1.1,
                        "ci_high": 1.7,
                        "unit": "ratio",
                    }
                ),
                json.dumps(
                    {
                        "context_id": "PL",
                        "income_level": "upper_middle",
                        "publication_year": 2020,
                        "institutional_quality": 0.6,
                    }
                ),
            ],
        )
        con.execute("INSERT INTO ac_skg_versions VALUES (5), (6)")
        con.execute("INSERT INTO ac_skg_context_profiles VALUES ('profile_pl', 'PL')")
    finally:
        con.close()


def test_query_prior_for_variables_filters_and_parses_json(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        rows = query.query_prior_for_variables(
            ["macro.tax", "macro.employment"],
            min_confidence=0.7,
            limit=10,
            domain="macro",
        )
    finally:
        query.close()

    assert len(rows) == 1
    edge = rows[0]
    assert edge["edge_id"] == "e1"
    assert edge["src"] == "macro.tax"
    assert edge["dst"] == "macro.employment"
    assert edge["n_articles"] == 3
    assert edge["article_refs"] == ["W1", "W2"]
    assert edge["scope_conditions"] == ["OECD"]
    assert edge["evidence_strength"] == "rct"
    assert edge["confidence"] == 0.84


def test_latest_version_and_snapshot_ref(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        version = query.latest_skg_version_id()
        snapshot = query.skg_snapshot_ref()
    finally:
        query.close()

    assert version == 6
    assert snapshot == f"duckdb://{db_path}#v6"


def test_query_parameters_parses_parameter_and_context(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        candidates = query.query_parameters("fiscal_multiplier")
    finally:
        query.close()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.parameter.name == "fiscal_multiplier"
    assert candidate.parameter.value == 1.4
    assert candidate.parameter.confidence_interval == (1.1, 1.7)
    assert candidate.source_context is not None
    assert candidate.source_context.context_id == "PL"


def test_query_parameters_enriches_transport_metadata(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    con = duckdb.connect(str(db_path))
    try:
        con.execute("INSERT INTO ac_skg_context_profiles VALUES ('profile_ua', 'UA')")
        con.execute("INSERT INTO ac_skg_moderation_edges VALUES ('m1', 'fiscal_multiplier')")
    finally:
        con.close()

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        candidates = query.query_parameters(
            "fiscal_multiplier",
            target_context=ContextProfile(
                context_id="UA",
                income_level=IncomeLevel.UPPER_MIDDLE,
            ),
        )
    finally:
        query.close()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.transport_penalty > 0.0
    assert "moderation_edges:1" in candidate.transport_notes
    assert "transport_score_unavailable" in candidate.transport_notes


def test_query_parameters_prefers_simulation_ready_layer(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO ac_skg_simulation_parameters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "n1",
                "W_sim",
                "fiscal_multiplier",
                "coefficient",
                1.1,
                "positive",
                "unitless",
                "rct",
                "[0.9, 1.3]",
                None,
                '["claim-1"]',
                '["edge-1"]',
                '{"context_id":"UA","income_level":"upper_middle"}',
                "simulation_ready",
                "confidence_interval",
                '[]',
            ],
        )
    finally:
        con.close()

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        candidates = query.query_parameters("fiscal_multiplier")
    finally:
        query.close()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_layer == "simulation_ready"
    assert candidate.parameter.value == 1.1
    assert candidate.parameter.confidence_interval == (0.9, 1.3)
    assert candidate.linked_claim_ids == ("claim-1",)
    assert candidate.linked_edge_ids == ("edge-1",)


def test_query_prior_for_variables_hybrid_merges_family_and_exact(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO ac_skg_family_edges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "fe1",
                "macro.tax",
                "macro.employment",
                "positive",
                5,
                4,
                '["W1","W2","W5","W6","W7"]',
                '["c1","c2","c3","c4"]',
                "meta_analysis",
                0.91,
                '{"conflict_flag": false}',
            ],
        )
    finally:
        con.close()

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        rows = query.query_prior_for_variables(
            ["macro.tax", "macro.employment"],
            min_confidence=0.7,
            limit=10,
            edge_layer="hybrid",
        )
    finally:
        query.close()

    assert len(rows) == 1
    edge = rows[0]
    assert edge["candidate_layer"] == "hybrid"
    assert edge["n_articles"] == 5
    assert edge["confidence"] == 0.91
    assert sorted(edge["article_refs"]) == ["W1", "W2", "W5", "W6", "W7"]


def test_query_edge_support_uses_family_layer_and_conflict_flags(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO ac_skg_family_edges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "fe2",
                "macro.tax",
                "macro.employment",
                "negative",
                3,
                3,
                '["W8","W9","W10"]',
                '["c8","c9","c10"]',
                "observational",
                0.73,
                '{"conflict_flag": true}',
            ],
        )
    finally:
        con.close()

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        rows = query.query_edge_support(
            cause="macro.tax",
            effect="macro.employment",
            support_mode="hybrid",
            min_confidence=0.25,
        )
    finally:
        query.close()

    assert any(row.source_layer in {"family", "hybrid"} for row in rows)
    assert any(row.conflict_flag for row in rows)


def test_query_edge_transport_reads_target_context_scores(tmp_path) -> None:
    db_path = tmp_path / "skg.duckdb"
    _seed_skg_tables(db_path)

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO ac_skg_transport_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "tr1",
                "edge-1",
                "UA",
                0.8,
                0.1,
                0.05,
                0.75,
                "exact",
                '[{"moderator":"institutional_quality"}]',
                1,
            ],
        )
    finally:
        con.close()

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        rows = query.query_edge_transport(["edge-1"], target_context_id="UA")
    finally:
        query.close()

    assert len(rows) == 1
    assert rows[0].edge_id == "edge-1"
    assert rows[0].transport_confidence == 0.75
    assert rows[0].matched_moderators_count == 1
