from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    CausalCredibility,
    CausalDirection,
    ClaimAdjudicationResult,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EnvironmentAuditReport,
    EvidenceParameter,
    EvidenceSpan,
    EvidenceStrength,
    LiteratureCausalPrior,
    LiteratureEdgePrior,
    ParameterType,
    ReconciliationDiagnostics,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
    TextQuality,
    load_article_extraction_result,
    load_literature_causal_prior,
    persist_article_extraction_result,
    persist_literature_causal_prior,
)
from pydantic import ValidationError


def _minimal_parameter() -> EvidenceParameter:
    return EvidenceParameter(
        name="gdp_growth",
        value=0.2,
        parameter_type=ParameterType.QUANTITATIVE,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        geographic_scope="OECD",
    )


def test_article_extraction_result_dual_read_legacy_v10() -> None:
    payload = {
        "schema_version": "1.0",
        "openalex_id": "https://openalex.org/W1",
        "doi": "10.1/demo",
        "title": "Legacy article",
        "publication_year": 2020,
        "cited_by_count": 10,
        "empirical_parameters": [_minimal_parameter().model_dump(mode="json")],
        "causal_claims": [
            {
                "cause": "gdp growth",
                "effect": "employment",
                "direction": "mixed",
                "evidence_strength": "observational",
            }
        ],
        "boundary_conditions": [
            {
                "scope_text": "in high income countries",
                "threshold_value": "high",
                "operator": "=",
                "confidence": 0.4,
            }
        ],
        "extraction_model": "demo-model",
        "extraction_timestamp": "2026-02-28T00:00:00Z",
        "extraction_confidence": 0.7,
    }

    result = ArticleExtractionResult.model_validate(payload)

    assert result.year == 2020
    assert result.publication_year == 2020
    assert result.schema_version == "1.0"
    assert result.causal_claims[0].cause_variable == "gdp growth"
    assert result.causal_claims[0].effect_variable == "employment"
    assert result.causal_claims[0].direction == CausalDirection.MIXED
    assert result.boundary_conditions[0].required_value == "high"


def test_article_extraction_result_v11_roundtrip() -> None:
    result = ArticleExtractionResult(
        openalex_id="https://openalex.org/W2",
        title="Modern article",
        year=2023,
        cited_by_count=25,
        source_basis=SourceBasis.FULLTEXT,
        text_quality=TextQuality.EXTRACTED_FULLTEXT,
        supporting_spans=[
            EvidenceSpan(
                section="results",
                text="Policy increases employment.",
                sentence_index=0,
                score=0.8,
            )
        ],
        empirical_parameters=[_minimal_parameter()],
        causal_claims=[
            CausalClaim(
                claim_id="c-1",
                claim_text="Policy increases employment",
                claim_type=ClaimType.CAUSAL_CLAIM,
                cause_variable="gdp_growth",
                effect_variable="employment_rate",
                direction=CausalDirection.POSITIVE,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.RCT,
                evidence_strength=EvidenceStrength.RCT,
                supporting_spans=[
                    EvidenceSpan(
                        section="results",
                        text="Policy increases employment.",
                        sentence_index=0,
                        score=0.8,
                    )
                ],
            )
        ],
        extraction_model="demo-model",
        extraction_timestamp="2026-02-28T00:00:00Z",
        extraction_confidence=0.9,
        source_context=ContextProfile(context_id="US", context_label="United States"),
    )

    assert result.schema_version == "1.5"
    assert result.publication_year == 2023
    assert result.causal_claims[0].claim_explicitness == ClaimExplicitness.EXPLICIT
    assert result.source_basis == SourceBasis.FULLTEXT


def test_article_extraction_artifact_persist_load(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    result = ArticleExtractionResult(
        openalex_id="https://openalex.org/W3",
        title="Persisted article",
        year=2024,
        cited_by_count=40,
        empirical_parameters=[_minimal_parameter()],
        extraction_model="demo-model",
        extraction_timestamp="2026-02-28T00:00:00Z",
        extraction_confidence=0.88,
    )

    ref = persist_article_extraction_result(store, result)
    loaded = load_article_extraction_result(store, ref["artifact_id"])

    assert loaded.openalex_id == result.openalex_id
    assert loaded.year == 2024
    assert loaded.publication_year == 2024
    assert loaded.empirical_parameters[0].name == "gdp_growth"


def test_causal_claim_normalizes_derived_fields_consistently() -> None:
    payload = {
        "cause": "tax_rate",
        "effect": "employment",
        "supporting_spans": [
            EvidenceSpan(span_id="support-1", text="Tax increases lower employment"),
        ],
        "method_spans": [EvidenceSpan(span_id="method-1", text="DiD specification")],
    }
    normalized = CausalClaim.normalize_payload(payload)
    claim = CausalClaim.from_payload(payload)

    assert "cause_variable" not in payload
    assert normalized["cause_variable"] == "tax_rate"
    assert claim.claim_text == "tax_rate -> employment"
    assert claim.supporting_span_ids == ["support-1"]
    assert claim.method_span_ids == ["method-1"]
    assert claim.model_copy(deep=True).claim_text == "tax_rate -> employment"
    reparsed = CausalClaim.model_validate(claim.model_dump(mode="json"))
    assert reparsed.supporting_span_ids == ["support-1"]
    assert reparsed.method_span_ids == ["method-1"]


def test_causal_claim_is_frozen_report_contract() -> None:
    claim = CausalClaim.from_payload({"cause": "tax_rate", "effect": "employment"})

    with pytest.raises(ValidationError, match="frozen"):
        claim.claim_text = "mutated"


def test_article_extraction_result_normalizes_year_aliases_consistently() -> None:
    payload = {
        "openalex_id": "https://openalex.org/W4",
        "title": "Alias normalization",
        "publication_year": 2022,
        "extraction_model": "demo-model",
        "extraction_timestamp": "2026-02-28T00:00:00Z",
        "extraction_confidence": 0.91,
    }

    normalized = ArticleExtractionResult.normalize_payload(payload)
    result = ArticleExtractionResult.from_payload(payload)

    assert "year" not in payload
    assert normalized["year"] == 2022
    assert result.year == 2022
    assert result.publication_year == 2022
    assert result.model_copy(deep=True).year == 2022
    reparsed = ArticleExtractionResult.model_validate(result.model_dump(mode="json"))
    assert reparsed.year == 2022
    assert reparsed.publication_year == 2022


def test_article_extraction_result_is_frozen_report_contract() -> None:
    result = ArticleExtractionResult(
        openalex_id="https://openalex.org/W5",
        title="Frozen",
        extraction_model="demo-model",
        extraction_timestamp="2026-02-28T00:00:00Z",
        extraction_confidence=0.91,
    )

    with pytest.raises(ValidationError, match="frozen"):
        result.title = "mutated"


def test_literature_prior_to_graph_sets_discovery_metadata() -> None:
    prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="tax_rate",
                dst="employment",
                confidence=0.72,
                n_articles=4,
                evidence_strength=EvidenceStrength.RCT,
                article_refs=["W1", "W2"],
                scope_conditions=["OECD"],
                direction=CausalDirection.NEGATIVE,
            )
        ],
        skg_version_id=11,
        skg_snapshot_ref="duckdb:///tmp/skg.duckdb#v11",
    )

    graph = prior.to_causal_graph_model(nodes=["tax_rate", "employment"])
    assert graph.discovery_method == "literature_prior"
    assert graph.skg_version_id == 11
    assert graph.metadata["skg_snapshot_ref"] == "duckdb:///tmp/skg.duckdb#v11"
    assert len(graph.edges) == 1
    assert graph.edges[0].literature_confidence == 0.72


def test_literature_prior_artifact_persist_load_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="x",
                dst="y",
                confidence=0.66,
                evidence_strength=EvidenceStrength.OBSERVATIONAL,
                article_refs=["W42"],
            )
        ],
        skg_version_id=3,
        skg_snapshot_ref="duckdb:///tmp/skg.duckdb#v3",
        metadata={"topic": "labor"},
    )

    ref = persist_literature_causal_prior(store, prior)
    loaded = load_literature_causal_prior(store, ref)
    assert loaded == prior
    assert loaded.edges[0].src == "x"
    assert loaded.metadata["topic"] == "labor"


def test_literature_prior_roundtrips_environment_audit(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="x",
                dst="y",
                confidence=0.66,
                evidence_strength=EvidenceStrength.OBSERVATIONAL,
                article_refs=["W42"],
            )
        ],
        environment_audit=EnvironmentAuditReport(
            status="warning",
            n_environments=3,
            ks_passed=False,
            ks_rejected_variables=[0],
            ks_p_values={"feature_0_domain_a_vs_b": 0.01},
            icp_run=True,
            icp_passed=False,
            variant_features=[1],
            icp_p_values={"feature_1": 0.02},
            warnings=["ks_detected_distribution_shift"],
            metadata={"source": "test"},
        ),
        metadata={"topic": "labor"},
    )

    ref = persist_literature_causal_prior(store, prior)
    loaded = load_literature_causal_prior(store, ref)
    graph = loaded.to_causal_graph_model(nodes=["x", "y"])

    assert loaded.environment_audit is not None
    assert loaded.environment_audit.status == "warning"
    assert loaded.environment_audit.variant_features == [1]
    assert graph.metadata["environment_audit_status"] == "warning"


def test_reconciliation_diagnostics_contract_minimal() -> None:
    diagnostics = ReconciliationDiagnostics(
        cyclic_inconsistency_norm=0.2,
        irreducible_conflict_norm=0.6,
        diagnostics_truncated=True,
        truncation_reason="max_recon_edges_exceeded",
        d0_shape=(3, 3),
        d1_shape=(1, 3),
        delta0_shape=(3, 3),
        delta1_shape=(3, 1),
    )
    payload = diagnostics.model_dump(mode="json")
    assert payload["irreducible_conflict_norm"] == 0.6
    assert payload["diagnostics_truncated"] is True


def test_claim_adjudication_contract_minimal() -> None:
    adjudication = ClaimAdjudicationResult(
        claim_id="c-1",
        openalex_id="https://openalex.org/W1",
        cause_variable="tax_rate",
        effect_variable="employment",
        source_basis=SourceBasis.FULLTEXT,
        paper_asserts_causality_score=0.9,
        claim_type=ClaimType.CAUSAL_ASSERTION,
        design_family=DesignFamily.DID,
        causal_credibility=CausalCredibility.MODERATE,
        risk_of_bias=RiskOfBias.MODERATE,
        support_status=SupportStatus.SUPPORTED,
        claim_validity_score=0.82,
        adjudication_confidence=0.88,
        publishable_edge=True,
    )
    payload = adjudication.model_dump(mode="json")
    assert payload["publishable_edge"] is True
    assert payload["design_family"] == "did"
