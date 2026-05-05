"""Tests for three-track transportability data models (Phase 1)."""

from __future__ import annotations

import pytest
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    ContextAttribute,
    EvidenceSpan,
    HeterogeneityResult,
    IdentificationStrategy,
    ModerationEdge,
    PaperKind,
    UncertaintyBudget,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# PaperKind enum
# ---------------------------------------------------------------------------


def test_paper_kind_values() -> None:
    assert PaperKind.EMPIRICAL_CAUSAL.value == "empirical_causal"
    assert PaperKind.CONTEXT_CHARACTERIZATION.value == "context_characterization"
    assert PaperKind.HETEROGENEITY_ANALYSIS.value == "heterogeneity_analysis"
    assert PaperKind.MIXED.value == "mixed"


# ---------------------------------------------------------------------------
# IdentificationStrategy
# ---------------------------------------------------------------------------


def test_identification_strategy_minimal() -> None:
    ids = IdentificationStrategy()
    assert ids.identification_method == ""
    assert ids.exclusion_restrictions == []


def test_identification_strategy_full() -> None:
    ids = IdentificationStrategy(
        identification_method="IV",
        instrument="rainfall",
        exclusion_restrictions=["rainfall affects output only through irrigation"],
        design_assumptions=["monotonicity", "exclusion restriction"],
        identification_confidence=0.85,
    )
    assert ids.instrument == "rainfall"
    assert len(ids.design_assumptions) == 2


def test_identification_strategy_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        IdentificationStrategy(identification_method="IV", bogus_field="x")


def test_identification_strategy_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        IdentificationStrategy(identification_confidence=1.5)
    with pytest.raises(ValidationError):
        IdentificationStrategy(identification_confidence=-0.1)


# ---------------------------------------------------------------------------
# HeterogeneityResult
# ---------------------------------------------------------------------------


def test_heterogeneity_result_minimal() -> None:
    hr = HeterogeneityResult(moderator="income_level")
    assert hr.moderator == "income_level"
    assert hr.subgroup_effects == {}


def test_heterogeneity_result_full() -> None:
    hr = HeterogeneityResult(
        moderator="institutional_quality",
        dimension="cross_country",
        finding="effect stronger in low-quality institutions",
        interaction_coefficient=-0.3,
        interaction_pvalue=0.02,
        subgroup_effects={"high_iq": 0.05, "low_iq": 0.18},
        confidence=0.9,
    )
    assert hr.interaction_coefficient == -0.3
    assert hr.subgroup_effects["low_iq"] == 0.18


def test_heterogeneity_result_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        HeterogeneityResult(moderator="x", unknown=True)


# ---------------------------------------------------------------------------
# UncertaintyBudget
# ---------------------------------------------------------------------------


def test_uncertainty_budget_total() -> None:
    ub = UncertaintyBudget(conflict_residual=0.2, sampling_uncertainty=0.3, graph_uncertainty=0.1)
    assert ub.total == pytest.approx(0.6)


def test_uncertainty_budget_total_capped() -> None:
    ub = UncertaintyBudget(conflict_residual=0.5, sampling_uncertainty=0.4, graph_uncertainty=0.3)
    assert ub.total == 1.0


def test_uncertainty_budget_defaults() -> None:
    ub = UncertaintyBudget()
    assert ub.total == 0.0


def test_uncertainty_budget_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        UncertaintyBudget(conflict_residual=1.5)


# ---------------------------------------------------------------------------
# ContextAttribute
# ---------------------------------------------------------------------------


def test_context_attribute_minimal() -> None:
    ca = ContextAttribute(attribute_name="institutional_quality")
    assert ca.confidence == 0.5
    assert ca.country_codes == []


def test_context_attribute_full() -> None:
    ca = ContextAttribute(
        attribute_name="social_trust",
        canonical_name="governance.social_trust",
        value=0.38,
        unit="wvs_index",
        country_codes=["US", "UK"],
        time_period="2015-2020",
        measurement_method="World Values Survey wave 7",
        confidence=0.9,
        evidence_spans=[EvidenceSpan(text="Trust levels averaged 0.38")],
    )
    assert ca.canonical_name == "governance.social_trust"
    assert len(ca.evidence_spans) == 1


def test_context_attribute_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        ContextAttribute(attribute_name="x", bogus=1)


# ---------------------------------------------------------------------------
# ModerationEdge
# ---------------------------------------------------------------------------


def test_moderation_edge_minimal() -> None:
    me = ModerationEdge(base_cause="spending", base_effect="inflation", moderator="iq")
    assert me.evidence_count == 1
    assert me.confidence == 0.5


def test_moderation_edge_full() -> None:
    me = ModerationEdge(
        base_cause="education.spending",
        base_effect="education.test_scores",
        moderator="governance.decentralization",
        direction_of_moderation="amplifying",
        quantitative_interaction=0.08,
        interaction_pvalue=0.02,
        evidence_count=23,
        confidence=0.85,
        source_openalex_ids=["W1", "W2"],
        evidence_text="The effect is amplified in decentralized systems",
    )
    assert me.quantitative_interaction == 0.08
    assert len(me.source_openalex_ids) == 2


def test_moderation_edge_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        ModerationEdge(base_cause="a", base_effect="b", moderator="c", extra=1)


# ---------------------------------------------------------------------------
# CausalClaim backward compatibility
# ---------------------------------------------------------------------------


def test_causal_claim_without_new_fields() -> None:
    """Old-format claims still parse without identification_strategy or uncertainty_budget."""
    cc = CausalClaim(cause_variable="tax_rate", effect_variable="employment")
    assert cc.identification_strategy is None
    assert cc.uncertainty_budget is None


def test_causal_claim_with_new_fields() -> None:
    ids = IdentificationStrategy(identification_method="IV", instrument="rainfall")
    ub = UncertaintyBudget(conflict_residual=0.1, sampling_uncertainty=0.2)
    cc = CausalClaim(
        cause_variable="tax_rate",
        effect_variable="employment",
        identification_strategy=ids,
        uncertainty_budget=ub,
    )
    assert cc.identification_strategy.instrument == "rainfall"
    assert cc.uncertainty_budget.total == pytest.approx(0.3)


def test_causal_claim_roundtrip_with_new_fields() -> None:
    """Serialize and deserialize CausalClaim with new fields."""
    ids = IdentificationStrategy(
        identification_method="DiD", design_assumptions=["parallel trends"]
    )
    cc = CausalClaim(
        cause_variable="x",
        effect_variable="y",
        identification_strategy=ids,
    )
    payload = cc.model_dump(mode="json")
    restored = CausalClaim.model_validate(payload)
    assert restored.identification_strategy.identification_method == "DiD"
    assert restored.identification_strategy.design_assumptions == ["parallel trends"]


def test_causal_claim_legacy_dict_without_new_fields() -> None:
    """Simulate old serialized data without the new fields."""
    legacy_payload = {
        "cause": "gdp",
        "effect": "employment",
        "direction": "positive",
        "evidence_strength": "rct",
    }
    cc = CausalClaim.model_validate(legacy_payload)
    assert cc.cause_variable == "gdp"
    assert cc.identification_strategy is None


# ---------------------------------------------------------------------------
# ArticleExtractionResult backward compatibility
# ---------------------------------------------------------------------------


def test_aer_schema_version_bump() -> None:
    aer = ArticleExtractionResult(
        openalex_id="W1",
        title="Test",
        extraction_model="m",
        extraction_timestamp="t",
        extraction_confidence=0.8,
    )
    assert aer.schema_version == "1.5"
    assert aer.paper_kind == PaperKind.EMPIRICAL_CAUSAL
    assert aer.heterogeneity_results == []
    assert aer.context_attributes == []
    assert aer.moderation_edges == []
    assert aer.external_validity_assessment == ""


def test_aer_legacy_v10_still_parses() -> None:
    """Schema 1.0 payloads (no new fields) still parse correctly."""
    payload = {
        "schema_version": "1.0",
        "openalex_id": "W1",
        "title": "Old",
        "publication_year": 2020,
        "extraction_model": "m",
        "extraction_timestamp": "t",
        "extraction_confidence": 0.7,
    }
    aer = ArticleExtractionResult.model_validate(payload)
    assert aer.schema_version == "1.0"
    assert aer.year == 2020
    assert aer.paper_kind == PaperKind.EMPIRICAL_CAUSAL


def test_aer_with_all_new_fields() -> None:
    hr = HeterogeneityResult(moderator="income", finding="stronger in low-income")
    ca = ContextAttribute(attribute_name="iq", value=0.8)
    me = ModerationEdge(base_cause="x", base_effect="y", moderator="iq")
    aer = ArticleExtractionResult(
        openalex_id="W1",
        title="Full",
        extraction_model="m",
        extraction_timestamp="t",
        extraction_confidence=0.9,
        paper_kind=PaperKind.MIXED,
        heterogeneity_results=[hr],
        context_attributes=[ca],
        moderation_edges=[me],
        external_validity_assessment="OECD post-2000 only",
    )
    assert aer.paper_kind == PaperKind.MIXED
    assert len(aer.heterogeneity_results) == 1
    assert aer.heterogeneity_results[0].moderator == "income"
    assert len(aer.context_attributes) == 1
    assert len(aer.moderation_edges) == 1
    assert aer.external_validity_assessment == "OECD post-2000 only"


def test_aer_roundtrip_with_new_fields() -> None:
    """Full roundtrip: construct → serialize → deserialize."""
    aer = ArticleExtractionResult(
        openalex_id="W1",
        title="RT",
        extraction_model="m",
        extraction_timestamp="t",
        extraction_confidence=0.85,
        paper_kind=PaperKind.HETEROGENEITY_ANALYSIS,
        heterogeneity_results=[
            HeterogeneityResult(moderator="trust", interaction_coefficient=-0.2)
        ],
        moderation_edges=[
            ModerationEdge(base_cause="a", base_effect="b", moderator="trust", confidence=0.7)
        ],
    )
    payload = aer.model_dump(mode="json")
    restored = ArticleExtractionResult.model_validate(payload)
    assert restored.paper_kind == PaperKind.HETEROGENEITY_ANALYSIS
    assert restored.heterogeneity_results[0].interaction_coefficient == -0.2
    assert restored.moderation_edges[0].confidence == 0.7
