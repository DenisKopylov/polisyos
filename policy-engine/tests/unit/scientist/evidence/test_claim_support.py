from __future__ import annotations

from polisyos.scholar.search.models import (
    QueryGraph,
    ResearchBrief,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scientist.evidence.claim_support import (
    build_claim_support_links,
    validate_claim_support_links,
)


def _snippet() -> SourceSnippet:
    return SourceSnippet(
        snippet_id="snip.1",
        source_id="src.1",
        url="https://example.org/report",
        query_node_id="q1",
        perspective="overview",
        text="Minimum wage increased earnings for low wage workers.",
        start_char=0,
        end_char=53,
    )


def test_claim_support_mapping_uses_snippet_level_links() -> None:
    links = build_claim_support_links(
        ["minimum wage increased earnings"],
        [_snippet()],
    )

    assert links[0].snippet_ids == ["snip.1"]
    assert links[0].source_ids == ["src.1"]
    assert links[0].metadata["claim_id_namespace"] == "legacy_local"
    assert links[0].metadata["support_status"] in {"supported", "weakly_supported"}


def test_claim_support_validator_rejects_missing_snippet_refs() -> None:
    brief = ResearchBrief(question="minimum wage")
    bundle = WebEvidenceBundle.model_construct(
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
        snippets=[_snippet()],
        claim_supports=[
            build_claim_support_links(["minimum wage increased earnings"], [_snippet()])[
                0
            ].model_copy(update={"snippet_ids": ["snip.missing"]})
        ],
    )

    assert "missing_snippet_id:claim.1:snip.missing" in validate_claim_support_links(bundle)
