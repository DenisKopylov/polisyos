from __future__ import annotations

import pytest
from polisyos.scholar.search.models import (
    ClaimSupportLink,
    FetchSafetyEvent,
    QueryGraph,
    ResearchBrief,
    SourceMetadata,
    SourceQualitySignal,
    SourceSnippet,
    WebEvidenceBundle,
)
from pydantic import ValidationError


def _brief() -> ResearchBrief:
    return ResearchBrief(question="minimum wage evidence")


def test_web_evidence_bundle_accepts_safety_and_quality_extensions() -> None:
    brief = _brief()
    bundle = WebEvidenceBundle(
        bundle_id="bundle-1",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[
            SourceMetadata(
                source_id="src.1",
                url="https://agency.gov/report",
                title="Agency report",
                domain="agency.gov",
            )
        ],
        snippets=[
            SourceSnippet(
                snippet_id="snip.1",
                source_id="src.1",
                url="https://agency.gov/report",
                query_node_id="q1",
                perspective="overview",
                text="Policy evidence text.",
                start_char=0,
                end_char=21,
            )
        ],
        claim_supports=[
            ClaimSupportLink(
                claim_id="claim.1",
                claim_text="policy evidence",
                snippet_ids=["snip.1"],
                source_ids=["src.1"],
                support_score=0.4,
                metadata={
                    "claim_id_namespace": "legacy_local",
                    "support_status": "supported",
                },
            )
        ],
        fetch_safety_events=[
            FetchSafetyEvent(
                event_id="fetch_safety.1",
                url="https://agency.gov/report",
                event_type="prompt_injection_suspected",
                severity="warning",
                message="untrusted instruction-like text",
            )
        ],
        source_quality_signals=[
            SourceQualitySignal(
                source_id="src.1",
                authority_score=0.9,
                freshness_score=0.8,
                primary_source_score=0.95,
                anti_seo_score=1.0,
                duplicate_score=0.0,
            )
        ],
    )

    assert bundle.fetch_safety_events[0].event_type == "prompt_injection_suspected"
    assert bundle.source_quality_signals[0].source_id == "src.1"


def test_claim_support_link_with_missing_snippet_id_fails_validation() -> None:
    brief = _brief()
    with pytest.raises(ValidationError, match="missing snippet_id"):
        WebEvidenceBundle(
            bundle_id="bundle-1",
            brief=brief,
            query_graph=QueryGraph(brief=brief),
            sources=[
                SourceMetadata(
                    source_id="src.1",
                    url="https://agency.gov/report",
                    domain="agency.gov",
                )
            ],
            claim_supports=[
                ClaimSupportLink(
                    claim_id="claim.1",
                    claim_text="policy evidence",
                    snippet_ids=["snip.missing"],
                    source_ids=["src.1"],
                    support_score=0.5,
                    metadata={"support_status": "supported"},
                )
            ],
        )
