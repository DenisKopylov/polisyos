from __future__ import annotations

from datetime import UTC, datetime

from polisyos.scholar.search.models import (
    QueryGraph,
    ResearchBrief,
    SourceMetadata,
    WebEvidenceBundle,
)
from polisyos.scientist.evidence import source_quality
from polisyos.scientist.evidence.source_quality import (
    build_source_quality_report,
    score_source_quality,
    score_web_evidence_bundle_sources,
)


def test_source_quality_scores_primary_authoritative_sources() -> None:
    source = SourceMetadata(
        source_id="src.gov",
        url="https://agency.gov/report",
        domain="agency.gov",
        source_type="government",
        page_age_days=15,
        anti_seo_score=0.0,
    )

    signal = score_source_quality(source, now=datetime(2026, 4, 26, tzinfo=UTC))

    assert signal.authority_score >= 0.9
    assert signal.freshness_score == 1.0
    assert signal.primary_source_score >= 0.9
    assert signal.anti_seo_score == 1.0
    assert "primary_or_official_source_type" in signal.reasons


def test_bundle_source_quality_returns_one_signal_per_source() -> None:
    brief = ResearchBrief(question="evidence")
    bundle = WebEvidenceBundle(
        bundle_id="bundle",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[
            SourceMetadata(
                source_id="src.1",
                url="https://example.org/report",
                domain="example.org",
            )
        ],
    )

    assert len(score_web_evidence_bundle_sources(bundle)) == 1


def test_source_quality_assessment_declares_scores_advisory() -> None:
    source = SourceMetadata(
        source_id="src.gov",
        url="https://agency.gov/rule",
        domain="agency.gov",
        source_type="government",
        page_age_days=120,
        anti_seo_score=0.0,
    )

    assessment = source_quality.evaluate_source_quality(
        source,
        claim_family="normative",
        now=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert assessment.score_calibration == "advisory"
    assert assessment.overall_quality_score >= 0.8
    assert assessment.publishable is True
    assert assessment.independent_evidence is True
    assert "score_calibration:advisory_v1" in assessment.reasons


def test_withdrawn_primary_source_cannot_remain_publishable() -> None:
    source = SourceMetadata(
        source_id="src.withdrawn-law",
        url="https://agency.gov/withdrawn-rule",
        domain="agency.gov",
        source_type="regulation",
        page_age_days=3,
        anti_seo_score=0.0,
    )

    assessment = source_quality.evaluate_source_quality(
        source,
        claim_family="normative",
        invalidation_type="withdrawn",
        now=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert assessment.source_class == "primary"
    assert assessment.invalidation_state == "withdraw"
    assert assessment.publishable is False
    assert "withdrawn_primary_source_blocks_publication" in assessment.reasons


def test_source_quality_report_blocks_withdrawn_primary_sources() -> None:
    report = build_source_quality_report(
        sources=[
            {
                "source_id": "norm.withdrawn",
                "url": "https://agency.gov/withdrawn",
                "domain": "agency.gov",
                "source_type": "regulation",
                "page_age_days": 1,
                "invalidation_type": "withdrawn",
            }
        ],
        claim_families=["legal"],
        now=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert report["schema_version"] == "policyos.scientist.source_quality_report.v1"
    assert report["score_calibration"] == "advisory"
    assert report["status"] == "fail"
    assert report["issues"][0]["code"] == "source_quality_not_publishable"


def test_freshness_ttl_differs_by_claim_family_and_source_class() -> None:
    now = datetime(2026, 4, 26, tzinfo=UTC)
    policy_source = SourceMetadata(
        source_id="src.official",
        url="https://agency.gov/rule",
        domain="agency.gov",
        source_type="government",
        published_at=datetime(2024, 4, 26, tzinfo=UTC),
    )
    news_source = SourceMetadata(
        source_id="src.news",
        url="https://news.example.com/forecast",
        domain="news.example.com",
        source_type="news",
        published_at=datetime(2026, 2, 1, tzinfo=UTC),
    )

    policy_assessment = source_quality.evaluate_source_quality(
        policy_source,
        claim_family="normative",
        now=now,
    )
    forecast_assessment = source_quality.evaluate_source_quality(
        news_source,
        claim_family="forecast",
        now=now,
    )

    assert source_quality.source_freshness_ttl_days(
        "normative",
        "primary",
    ) > source_quality.source_freshness_ttl_days(
        "forecast",
        "news",
    )
    assert policy_assessment.freshness_state == "fresh"
    assert forecast_assessment.freshness_state == "stale"
    assert forecast_assessment.invalidation_state == "stale"


def test_source_quality_claim_family_aliases_match_claim_support_semantics() -> None:
    assert source_quality.source_freshness_ttl_days(
        "factual",
        "primary",
    ) == source_quality.source_freshness_ttl_days(
        "empirical",
        "primary",
    )
    assert source_quality.source_freshness_ttl_days(
        "legal",
        "primary",
    ) == source_quality.source_freshness_ttl_days(
        "normative",
        "primary",
    )
    assert source_quality.source_freshness_ttl_days(
        "welfare",
        "academic",
    ) == source_quality.source_freshness_ttl_days(
        "causal",
        "academic",
    )


def test_duplicates_and_material_conflicts_require_review_without_independent_credit() -> None:
    source = SourceMetadata(
        source_id="src.duplicate",
        url="https://example.org/brief",
        domain="example.org",
        source_type="web",
        page_age_days=10,
        duplicate_of_source_id="src.original",
    )

    assessment = source_quality.evaluate_source_quality(
        source,
        claim_family="empirical",
        conflict_level="material",
        now=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert assessment.duplicate_of_source_id == "src.original"
    assert assessment.independent_evidence is False
    assert assessment.invalidation_state == "review"
    assert assessment.publishable is False
    assert "duplicate_not_independent_evidence" in assessment.reasons
    assert "material_source_conflict_requires_review" in assessment.reasons
