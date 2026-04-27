from __future__ import annotations

from datetime import UTC, datetime

from polisyos.scholar.search.models import (
    QueryGraph,
    ResearchBrief,
    SourceMetadata,
    WebEvidenceBundle,
)
from polisyos.scientist.evidence.source_quality import (
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
