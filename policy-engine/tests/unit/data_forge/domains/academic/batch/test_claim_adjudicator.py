from __future__ import annotations

from polisyos.data_forge.domains.academic.batch.resolve_extract import _apply_publish_gate
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    CausalDirection,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EvidenceSpan,
    EvidenceStrength,
    SourceBasis,
    TextQuality,
)


def _base_result(claim: CausalClaim) -> ArticleExtractionResult:
    return ArticleExtractionResult(
        openalex_id="https://openalex.org/W1",
        title="Policy Study",
        year=2023,
        cited_by_count=10,
        source_basis=SourceBasis.FULLTEXT,
        text_quality=TextQuality.EXTRACTED_FULLTEXT,
        supporting_spans=claim.supporting_spans,
        method_spans=claim.method_spans,
        causal_claims=[claim],
        extraction_model="demo",
        extraction_timestamp="2026-03-06T00:00:00Z",
        extraction_confidence=0.82,
        methodology="difference in differences",
        citation_summary="empirical study",
    )


def test_publish_gate_keeps_whitelisted_did_claim() -> None:
    claim = CausalClaim(
        claim_id="c-1",
        claim_text="Higher tax rates reduce employment",
        claim_type=ClaimType.CAUSAL_CLAIM,
        cause_variable="tax_rate",
        effect_variable="employment",
        direction=CausalDirection.NEGATIVE,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.DID,
        evidence_strength=EvidenceStrength.QUASI_NATURAL,
        supporting_spans=[
            EvidenceSpan(
                span_id="r_01",
                section="results",
                text="Higher tax rates reduce employment.",
                sentence_index=0,
                score=0.9,
            )
        ],
        method_spans=[
            EvidenceSpan(
                span_id="m_01",
                section="methods",
                text="We use a difference-in-differences design with parallel trends checks.",
                sentence_index=1,
                score=0.9,
            )
        ],
        supporting_span_ids=["r_01"],
        method_span_ids=["m_01"],
        source_basis=SourceBasis.FULLTEXT,
        claim_extraction_confidence=0.9,
    )
    result = _apply_publish_gate(_base_result(claim))
    assert result.causal_claims[0].publish_to_graph is True
    assert result.causal_claims[0].strong_design_evidence is True


def test_publish_gate_keeps_panel_fe_claim_with_method_signal() -> None:
    claim = CausalClaim(
        claim_id="c-2",
        claim_text="Higher tax rates correlate with lower employment",
        claim_type=ClaimType.CAUSAL_CLAIM,
        cause_variable="tax_rate",
        effect_variable="employment",
        direction=CausalDirection.NEGATIVE,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.PANEL_FE,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        supporting_spans=[
            EvidenceSpan(
                span_id="r_01",
                section="results",
                text="Higher tax rates correlate with lower employment.",
                sentence_index=0,
                score=0.9,
            )
        ],
        method_spans=[
            EvidenceSpan(
                span_id="m_01",
                section="methods",
                text="We estimate panel fixed effects models.",
                sentence_index=1,
                score=0.9,
            )
        ],
        supporting_span_ids=["r_01"],
        method_span_ids=["m_01"],
        source_basis=SourceBasis.FULLTEXT,
        claim_extraction_confidence=0.9,
    )
    result = _apply_publish_gate(_base_result(claim))
    assert result.causal_claims[0].publish_to_graph is True
    assert result.causal_claims[0].design_quality_tier == 3
    assert "design_not_publishable" not in result.causal_claims[0].publish_blockers


def test_publish_gate_keeps_event_study_only_with_strong_design() -> None:
    claim = CausalClaim(
        claim_id="c-3",
        claim_text="The reform reduces informality",
        claim_type=ClaimType.CAUSAL_CLAIM,
        cause_variable="tax_reform",
        effect_variable="informality",
        direction=CausalDirection.NEGATIVE,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.EVENT_STUDY,
        evidence_strength=EvidenceStrength.QUASI_NATURAL,
        supporting_spans=[
            EvidenceSpan(
                span_id="r_01",
                section="results",
                text="The event-study estimates show the reform reduces informality after implementation.",
                sentence_index=0,
                score=0.9,
            )
        ],
        method_spans=[
            EvidenceSpan(
                span_id="m_01",
                section="methods",
                text="We run an event study with dynamic treatment effects around staggered adoption.",
                sentence_index=1,
                score=0.9,
            )
        ],
        supporting_span_ids=["r_01"],
        method_span_ids=["m_01"],
        source_basis=SourceBasis.FULLTEXT,
        claim_extraction_confidence=0.9,
    )
    result = _apply_publish_gate(_base_result(claim))
    assert result.causal_claims[0].publish_to_graph is True
    assert result.causal_claims[0].strong_design_evidence is True
