from __future__ import annotations

import json

import duckdb

from polisyos.academic.knowledge.skg_query import SKGQuery


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
