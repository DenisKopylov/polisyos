from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb

from polisyos.academic.batch.graph_builder import build_graph
from polisyos.academic.knowledge.types import EstimateCandidate, SourceTopicRef, WorkRecord


def test_build_graph_creates_skg_tables() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_skg.duckdb"

        rec = WorkRecord(
            id="w-1",
            title="Study 1",
            abstract="effect of policy on outcome",
            year=2020,
            cited_by_count=42,
            study_design="did",
            estimates=[EstimateCandidate(value=0.1, pattern_name="x", variable_hint="var")],
            source_topics=[
                SourceTopicRef(
                    topic_id="T1",
                    topic_display_name="Topic 1",
                    policy_block="b",
                    policy_subblock="s",
                    rank=1,
                    selection_score=0.9,
                    batch_origin="strict_recent",
                    selected_at="2026-01-01T00:00:00Z",
                )
            ],
            boundary_conditions=[{"scope_text": "in low income countries", "confidence": 0.5}],
            context_profile={"context_id": "US"},
        )

        stats = build_graph(records=iter([rec]), db_path=db_path)
        assert stats.works == 1

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            topic_sel = con.execute("SELECT COUNT(*) FROM ac_topic_selections").fetchone()[0]
            extractions = con.execute("SELECT COUNT(*) FROM ac_article_extractions").fetchone()[0]
            boundaries = con.execute("SELECT COUNT(*) FROM ac_boundary_conditions").fetchone()[0]
            skg_articles = con.execute("SELECT COUNT(*) FROM ac_skg_articles").fetchone()[0]
            skg_versions = con.execute("SELECT COUNT(*) FROM ac_skg_versions").fetchone()[0]
        finally:
            con.close()

        assert topic_sel == 1
        assert extractions == 1
        assert boundaries == 1
        assert skg_articles == 1
        assert skg_versions == 1
