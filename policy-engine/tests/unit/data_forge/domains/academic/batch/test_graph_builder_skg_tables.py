from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph, load_graph
from polisyos.data_forge.domains.academic.knowledge.types import (
    EstimateCandidate,
    SourceTopicRef,
    WorkRecord,
)


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
            transport_tables = con.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'ac_skg_transport_scores'"
            ).fetchone()[0]
        finally:
            con.close()

        assert topic_sel == 1
        assert extractions == 1
        assert boundaries == 1
        assert skg_articles == 1
        assert skg_versions == 1
        assert transport_tables == 1


def test_build_graph_rejects_producer_publish_flag_without_admitted_receipt() -> None:
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
                    "supporting_spans": [
                        {"section": "results", "text": "Higher tax rates reduce employment."}
                    ],
                    "supporting_span_ids": ["r_01"],
                    "method_span_ids": ["m_01"],
                    "method_spans": [
                        {"section": "methods", "text": "We use a difference-in-differences design."}
                    ],
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
                    "supporting_spans": [
                        {"section": "results", "text": "Higher tax rates may increase informality."}
                    ],
                    "supporting_span_ids": ["r_02"],
                },
            ],
            context_profile={"context_id": "US"},
        )

        stats = build_graph(records=iter([rec]), db_path=db_path)
        assert stats.raw_claims == 2
        assert stats.claim_adjudications == 0
        assert stats.claims == 0

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            raw_count = con.execute("SELECT COUNT(*) FROM ac_causal_claims_raw").fetchone()[0]
            adjudicated_count = con.execute(
                "SELECT COUNT(*) FROM ac_claim_adjudications"
            ).fetchone()[0]
            published_count = con.execute("SELECT COUNT(*) FROM ac_causal_claims").fetchone()[0]
            raw_claim = con.execute(
                "SELECT design_quality_tier, strong_design_evidence, publish_to_graph, publish_blockers "
                "FROM ac_causal_claims_raw WHERE id = 'c-1'"
            ).fetchone()
            edge_row = con.execute(
                "SELECT candidate_layer, quality_signals_json FROM ac_skg_edges WHERE src = 'tax_rate' AND dst = 'employment'"
            ).fetchone()
        finally:
            con.close()

        assert raw_count == 2
        assert adjudicated_count == 0
        assert published_count == 0
        assert raw_claim == (None, True, True, "")
        assert edge_row is None


def test_build_graph_aggregates_moderation_edges_and_preserves_canonical_name() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_transportability.duckdb"

        records = [
            WorkRecord(
                id="w-ctx-1",
                title="Institutional study 1",
                year=2020,
                causal_claims=[
                    {
                        "claim_id": "c-1",
                        "cause": "fiscal.public_spending",
                        "effect": "economic.output_growth",
                        "publish_to_graph": False,
                    }
                ],
                metadata={
                    "context_attributes": [
                        {
                            "attribute_name": "institutional_quality",
                            "canonical_name": "governance.institutional_quality",
                            "country_codes": ["US"],
                            "confidence": 0.6,
                        }
                    ],
                    "moderation_edges": [
                        {
                            "base_claim_id": "c-1",
                            "base_cause": "policy.spending",
                            "base_effect": "growth.output",
                            "moderator": "governance.institutional_quality",
                            "direction_of_moderation": "amplifying",
                            "confidence": 0.6,
                            "evidence_count": 1,
                        }
                    ],
                },
            ),
            WorkRecord(
                id="w-ctx-2",
                title="Institutional study 2",
                year=2021,
                causal_claims=[
                    {
                        "claim_id": "c-2",
                        "cause": "fiscal.public_spending",
                        "effect": "economic.output_growth",
                        "publish_to_graph": False,
                    }
                ],
                metadata={
                    "context_attributes": [
                        {
                            "attribute_name": "institutional_quality",
                            "canonical_name": "governance.institutional_quality",
                            "country_codes": ["SE"],
                            "confidence": 0.9,
                        }
                    ],
                    "moderation_edges": [
                        {
                            "base_claim_id": "c-2",
                            "base_cause": "policy.spending",
                            "base_effect": "growth.output",
                            "moderator": "governance.institutional_quality",
                            "direction_of_moderation": "dampening",
                            "quantitative_interaction": 0.12,
                            "interaction_pvalue": 0.03,
                            "confidence": 0.8,
                            "evidence_count": 2,
                        }
                    ],
                },
            ),
        ]

        build_graph(records=iter(records), db_path=db_path)

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            canonical_names = con.execute(
                "SELECT canonical_name FROM ac_skg_context_attributes ORDER BY country_code"
            ).fetchall()
            moderation_rows = con.execute(
                "SELECT base_cause, base_effect, evidence_count, confidence, interaction_coeff, source_refs, match_quality, alignment_source "
                "FROM ac_skg_moderation_edges"
            ).fetchall()
        finally:
            con.close()

        assert canonical_names == [
            ("governance.institutional_quality",),
            ("governance.institutional_quality",),
        ]
        assert len(moderation_rows) == 1
        (
            base_cause,
            base_effect,
            evidence_count,
            confidence,
            interaction_coeff,
            source_refs,
            match_quality,
            _alignment_source,
        ) = moderation_rows[0]
        assert base_cause == "fiscal.public_spending"
        assert base_effect == "economic.output_growth"
        assert evidence_count == 3
        assert confidence == 0.8
        assert interaction_coeff == 0.12
        assert json.loads(source_refs) == ["w-ctx-1", "w-ctx-2"]
        assert match_quality == ""


def test_build_graph_materializes_normalized_and_approved_variable_resolution() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_variable_resolution.duckdb"

        rec = WorkRecord(
            id="w-resolution",
            title="Coaching intervention study",
            year=2024,
            extraction_mode="llm_enriched",
            extraction_confidence=0.84,
            causal_claims=[
                {
                    "claim_id": "c-approved",
                    "cause": "institutional_quality.rule_of_law",
                    "effect": "teacher_coaching_program",
                    "direction": "positive",
                    "strength": "quasi_natural",
                    "claim_text": "Rule of law improves teacher coaching programs",
                    "design_family_hint": "did",
                    "source_basis": "fulltext",
                    "claim_extraction_confidence": 0.84,
                    "publish_to_graph": True,
                    "strong_design_evidence": True,
                }
            ],
        )

        build_graph(
            records=iter([rec]),
            db_path=db_path,
            admitted_claim_adjudications={
                "c-approved": {
                    "claim_id": "c-approved",
                    "publishable_edge": True,
                    "design_family": "did",
                    "causal_credibility": "strong",
                    "risk_of_bias": "low",
                    "support_status": "supported",
                    "source_basis": "fulltext",
                    "claim_validity_score": 0.9,
                    "adjudication_confidence": 0.9,
                }
            },
        )

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(
                """
                SELECT canonical_name, normalized_name, approved_canonical_name,
                       is_approved_canonical, resolution_method
                FROM ac_skg_variables
                ORDER BY canonical_name
                """
            ).fetchall()
        finally:
            con.close()

        assert rows == [
            (
                "institutional_quality.rule_of_law",
                "institutional_quality.rule_of_law",
                "institutional_quality.rule_of_law",
                True,
                "exact",
            ),
            (
                "teacher_coaching_program",
                "teacher_coaching_program",
                "education.teacher_coaching",
                True,
                "synonym",
            ),
        ]


def test_build_graph_filters_retracted_work_from_runtime_skg() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_retracted.duckdb"

        rec = WorkRecord(
            id="w-ret",
            title="Retracted study",
            year=2021,
            is_retracted=True,
            estimates=[EstimateCandidate(value=0.2, pattern_name="x", variable_hint="tax.revenue")],
            causal_claims=[
                {
                    "claim_id": "c-ret",
                    "cause": "tax.revenue",
                    "effect": "economic.gdp_growth",
                    "direction": "positive",
                    "publish_to_graph": True,
                }
            ],
        )

        build_graph(records=iter([rec]), db_path=db_path)
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            skg_articles = con.execute("SELECT COUNT(*) FROM ac_skg_articles").fetchone()[0]
            skg_edges = con.execute("SELECT COUNT(*) FROM ac_skg_edges").fetchone()[0]
            skg_edge_evidence = con.execute("SELECT COUNT(*) FROM ac_skg_edge_evidence").fetchone()[
                0
            ]
            skg_parameters = con.execute("SELECT COUNT(*) FROM ac_skg_parameters").fetchone()[0]
        finally:
            con.close()

        assert skg_articles == 1
        assert skg_edges == 0
        assert skg_edge_evidence == 0
        assert skg_parameters == 0


def test_load_graph_prefers_dedicated_simulation_ready_artifact_over_metadata_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_simulation_consistency.duckdb"
        empty_simulation_path = Path(tmpdir) / "simulation_ready_numeric_estimates.jsonl"
        empty_simulation_path.write_text("", encoding="utf-8")

        rec = WorkRecord(
            id="w-sim",
            title="Simulation mismatch study",
            year=2022,
            estimates=[
                EstimateCandidate(value=0.2, pattern_name="x", variable_hint="fiscal_multiplier")
            ],
            metadata={
                "simulation_ready_numeric_estimates": [
                    {
                        "numeric_id": "n-1",
                        "canonical_name": "fiscal_multiplier",
                        "estimate_type": "explicit_value",
                        "point_estimate": 1.5,
                        "estimate_sign": "positive",
                        "unit": "unitless",
                        "evidence_strength": "rct",
                    }
                ]
            },
        )

        stats = load_graph(
            records=iter([rec]),
            db_path=db_path,
            simulation_ready_numeric_path=empty_simulation_path,
        )
        assert stats.skg_simulation_parameters == 0

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            count = con.execute("SELECT COUNT(*) FROM ac_skg_simulation_parameters").fetchone()[0]
        finally:
            con.close()

        assert count == 0
