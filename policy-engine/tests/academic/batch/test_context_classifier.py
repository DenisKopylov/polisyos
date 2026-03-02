from __future__ import annotations

from polisyos.academic.batch.context_classifier import infer_context_from_article
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    EvidenceParameter,
    EvidenceStrength,
    ParameterType,
)


def _result() -> ArticleExtractionResult:
    return ArticleExtractionResult(
        openalex_id="https://openalex.org/W123",
        title="Test Article",
        year=2022,
        cited_by_count=12,
        empirical_parameters=[
            EvidenceParameter(
                name="gdp_growth",
                value=0.1,
                parameter_type=ParameterType.QUANTITATIVE,
                evidence_strength=EvidenceStrength.OBSERVATIONAL,
                geographic_scope="OECD",
            )
        ],
        extraction_model="demo-model",
        extraction_timestamp="2026-02-28T00:00:00Z",
        extraction_confidence=0.8,
    )


def test_infer_context_from_affiliations_single_country() -> None:
    work = {
        "publication_year": 2021,
        "authorships": [
            {
                "institutions": [
                    {"country_code": "US"},
                    {"country_code": "US"},
                ]
            }
        ],
    }
    context = infer_context_from_article(work, _result())

    assert context.context_id == "US"
    assert context.income_level == "high"
    assert context.publication_year == 2021


def test_infer_context_multi_country_fallback() -> None:
    work = {
        "publication_year": 2020,
        "authorships": [
            {"institutions": [{"country_code": "DE"}]},
            {"institutions": [{"country_code": "BR"}]},
        ],
    }
    context = infer_context_from_article(work, _result())

    assert context.context_label == "Multi-country"
    assert "+" in context.context_id
    assert context.publication_year == 2020
