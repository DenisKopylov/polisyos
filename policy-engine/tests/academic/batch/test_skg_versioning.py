from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from polisyos.academic.knowledge.skg_store import ensure_skg_schema
from polisyos.academic.knowledge.skg_versioning import SKGVersionManager


def test_skg_version_manager_create_and_finalize() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "skg.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            mgr = SKGVersionManager()
            version = mgr.create_version(con, description="test")
            mgr.finalize_version(con, version_id=version, n_articles=10, n_edges=20, n_variables=30)
            row = con.execute(
                "SELECT version_id, n_articles, n_edges, n_variables FROM ac_skg_versions WHERE version_id = ?",
                [version],
            ).fetchone()
        finally:
            con.close()

        assert row is not None
        assert int(row[1]) == 10
        assert int(row[2]) == 20
        assert int(row[3]) == 30


def test_skg_version_manager_handle_retraction_removes_or_updates_edges() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "skg.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            ensure_skg_schema(con)
            con.execute(
                """
                INSERT INTO ac_skg_articles(openalex_id, doi, title, year, cited_by_count, extraction_json, context_json, skg_version)
                VALUES
                ('W1', '10.1/a', 'A', 2020, 5, '{}', '{}', 1),
                ('W2', '10.1/b', 'B', 2021, 6, '{}', '{}', 1)
                """
            )
            con.execute(
                """
                INSERT INTO ac_skg_edges(edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence, scope_conditions)
                VALUES
                ('e1', 'x', 'y', 'positive', 2, ?, 'observational', 0.6, '[]')
                """,
                [json.dumps(["W1", "W2"])],
            )

            mgr = SKGVersionManager()
            report = mgr.handle_retraction(con, "W1")

            row = con.execute("SELECT n_articles, article_refs FROM ac_skg_edges WHERE edge_id='e1'").fetchone()
            article_row = con.execute("SELECT retracted FROM ac_skg_articles WHERE openalex_id='W1'").fetchone()
        finally:
            con.close()

        assert "e1" in report["affected_edges"]
        assert row is not None
        assert int(row[0]) == 1
        assert json.loads(str(row[1])) == ["W2"]
        assert bool(article_row[0]) is True
