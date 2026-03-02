from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalDirection,
    CausalClaim,
    EvidenceParameter,
    EvidenceStrength,
    LiteratureCausalPrior,
    LiteratureEdgePrior,
    ParameterType,
    ReconciliationDiagnostics,
    load_article_extraction_result,
    load_literature_causal_prior,
    persist_article_extraction_result,
    persist_literature_causal_prior,
)


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
        empirical_parameters=[_minimal_parameter()],
        causal_claims=[
            CausalClaim(
                cause_variable="gdp_growth",
                effect_variable="employment_rate",
                direction=CausalDirection.POSITIVE,
                evidence_strength=EvidenceStrength.RCT,
            )
        ],
        extraction_model="demo-model",
        extraction_timestamp="2026-02-28T00:00:00Z",
        extraction_confidence=0.9,
        source_context=ContextProfile(context_id="US", context_label="United States"),
    )

    assert result.schema_version == "1.1"
    assert result.publication_year == 2023


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
