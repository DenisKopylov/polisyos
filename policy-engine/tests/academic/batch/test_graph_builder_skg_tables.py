from __future__ import annotations

import tempfile
import json
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


def test_build_graph_uses_claim_publish_flags_for_published_layer() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_claims.duckdb"

        rec = WorkRecord(
            id="w-claim",
            title="Study 2",
            abstract="effects of tax policy",
            year=2021,
            cited_by_count=30,
            study_design="did",
            trust_score=0.7,
            causal_claims=[
                {
                    "claim_id": "c-1",
                    "cause": "tax_rate",
                    "effect": "employment",
                    "direction": "negative",
                    "strength": "quasi_natural",
                    "claim_text": "Higher tax rates reduce employment",
                    "claim_type": "causal_claim",
                    "design_family_hint": "did",
                    "source_basis": "fulltext",
                    "claim_extraction_confidence": 0.82,
                    "publish_to_graph": True,
                    "strong_design_evidence": True,
                    "supporting_spans": [{"section": "results", "text": "Higher tax rates reduce employment."}],
                    "supporting_span_ids": ["r_01"],
                    "method_span_ids": ["m_01"],
                    "method_spans": [{"section": "methods", "text": "We use a difference-in-differences design."}],
                },
                {
                    "claim_id": "c-2",
                    "cause": "tax_rate",
                    "effect": "informality",
                    "direction": "positive",
                    "strength": "observational",
                    "claim_text": "Higher tax rates may increase informality",
                    "claim_type": "associative",
                    "design_family_hint": "ols",
                    "source_basis": "abstract_only",
                    "claim_extraction_confidence": 0.22,
                    "publish_to_graph": False,
                    "publish_blockers": ["source_basis_not_fulltext", "design_not_publishable"],
                    "supporting_spans": [{"section": "results", "text": "Higher tax rates may increase informality."}],
                    "supporting_span_ids": ["r_02"],
                },
            ],
            context_profile={"context_id": "US"},
        )

        stats = build_graph(records=iter([rec]), db_path=db_path)
        assert stats.raw_claims == 2
        assert stats.claim_adjudications == 2
        assert stats.claims == 1

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            raw_count = con.execute("SELECT COUNT(*) FROM ac_causal_claims_raw").fetchone()[0]
            adjudicated_count = con.execute("SELECT COUNT(*) FROM ac_claim_adjudications").fetchone()[0]
            published_count = con.execute("SELECT COUNT(*) FROM ac_causal_claims").fetchone()[0]
        finally:
            con.close()

        assert raw_count == 2
        assert adjudicated_count == 2
        assert published_count == 1
