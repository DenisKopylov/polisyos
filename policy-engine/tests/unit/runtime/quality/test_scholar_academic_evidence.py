# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from polisyos.runtime.quality.scholar_academic_evidence import (
    build_scholar_academic_evidence_boundary_record,
    normalize_scholar_academic_evidence_report,
)
from polisyos.scholar import build_scholar_academic_evidence_report_from_web_bundle
from polisyos.scholar.search.models import (
    ClaimSupportLink,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SearchQueryTrace,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scholar import build_scholar_spine_evidence_binding
from polisyos.scholar_requirement import (
    ScholarSupportRequirementCompiler,
    ScholarSupportRequirementSpec,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    scorecard_for,
    sha,
)


def _scholar_academic_evidence() -> dict[str, object]:
    return {
        "schema_version": "policyos.scholar.academic_evidence.v1",
        "status": "pass",
        "scholar_evidence_ref": sha("8"),
        "cas_ref": sha("8"),
        "runtime_event_ref": sha("e"),
        "provenance_kind": "runtime_emitted",
        "producer_component": "polisyos.scholar.academic_evidence",
        "research_intent": {
            "intent_id": "research-intent-msme-survival",
            "question": "Does wartime credit support improve MSME survival?",
            "policy_domain": "wartime_msme_support",
            "jurisdictions": ["UA"],
            "required_source_types": ["academic", "grey_literature"],
        },
        "query_graph": {
            "graph_id": "query-graph-msme-survival",
            "root_query": "wartime credit support MSME survival Ukraine evidence",
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "wartime credit support MSME survival Ukraine evidence",
                    "perspective": "supporting academic and grey literature",
                }
            ],
        },
        "provider_traces": [
            {
                "trace_id": "trace-q1-openalex",
                "provider": "openalex",
                "query_node_id": "q1",
                "hit_count": 2,
                "searched_at": "2026-05-17T08:30:00+00:00",
            }
        ],
        "source_scoring": [
            {
                "source_id": "literature:msme-survival-review",
                "quality_score": 0.91,
                "freshness_score": 0.95,
                "relevance_score": 0.89,
                "independence_score": 1.0,
            }
        ],
        "snippets": [
            {
                "snippet_id": "snippet:msme-survival-review:1",
                "source_id": "literature:msme-survival-review",
                "query_node_id": "q1",
                "text": "Credit constraints are associated with lower MSME survival.",
                "start_char": 120,
                "end_char": 186,
            }
        ],
        "citations": [
            {
                "citation_id": "citation:msme-survival-review",
                "source_id": "literature:msme-survival-review",
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "evidence_ref": sha("8"),
                "provenance_kind": "runtime_emitted",
                "source_surface": "scholar_retrieval",
            }
        ],
        "freshness": {
            "status": "pass",
            "as_of": "2026-05-17",
            "max_source_age_days": 730,
            "sources": [
                {
                    "source_id": "literature:msme-survival-review",
                    "published_at": "2025-09-01",
                    "age_days": 258,
                    "status": "pass",
                }
            ],
        },
        "corpus_lineage": {
            "knowledge_bundle_ref": sha("9"),
            "corpus_snapshot_ref": sha("a"),
            "lineage_ref": sha("b"),
        },
        "selected_sources": [
            {
                "source_id": "literature:msme-survival-review",
                "source_family": "academic_peer_reviewed",
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "rights": "open_metadata",
            }
        ],
        "rejected_sources": [
            {
                "source_id": "literature:procurement-fixture",
                "reason_code": "off_topic",
                "source_family": "grey_literature",
            }
        ],
        "support_links": [
            {
                "link_id": "support:msme-survival-review:rec_1",
                "claim_id": "rec_1",
                "source_ids": ["literature:msme-survival-review"],
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "citation_ids": ["citation:msme-survival-review"],
            }
        ],
        "conflict_links": [
            {
                "link_id": "conflict:literature:resolved",
                "claim_id": "rec_1",
                "resolution": "No active contradiction after source screening.",
            }
        ],
        "duplicate_markers": [],
        "polarity_markers": [
            {
                "marker_id": "polarity:msme-survival-review:rec_1",
                "claim_id": "rec_1",
                "source_id": "literature:msme-survival-review",
                "snippet_id": "snippet:msme-survival-review:1",
                "polarity": "support",
                "support_status": "supported",
            }
        ],
        "dependence_records": [
            {
                "record_id": "dependence:academic_peer_reviewed:journal",
                "claim_id": "rec_1",
                "source_ids": ["literature:msme-survival-review"],
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "dependence_basis": "single_source_family",
                "raw_source_count": 1,
                "effective_source_count": 1,
            }
        ],
        "participation_downgrade_records": [
            {
                "record_id": "participation-downgrade:rec_1:none",
                "claim_id": "rec_1",
                "claim_use_requested": "academic_support",
                "claim_use_allowed": "academic_support",
                "authority_boundary": "scholar_academic_support_only",
                "downgrade_reason": "not_participation_claim",
            }
        ],
        "literature_deficit_blockers": [],
        "source_family_independence_tags": {
            "literature:msme-survival-review": "academic_peer_reviewed:journal"
        },
    }


def test_scholar_academic_evidence_missing_is_producer_owned_boundary() -> None:
    boundary = build_scholar_academic_evidence_boundary_record(None)

    assert boundary["status"] == "failed"
    assert boundary["producer_owner"] == "team-scholar"
    assert boundary["reader_owner"] == "team-runtime-quality"
    assert boundary["record_family"] == "scholar_academic_evidence.v1"
    assert boundary["runtime_authority_envelope"]["provenance_kind"] == "runtime_blocker"
    assert {
        issue["code"] for issue in boundary["issues"]
    } == {"policy_design_scholar_academic_evidence_missing"}


def test_scholar_academic_evidence_incomplete_claim_support_reports_all_facets() -> None:
    report = normalize_scholar_academic_evidence_report(
        {
            "schema_version": "policyos.scholar.academic_evidence.v1",
            "scholar_evidence_ref": sha("8"),
            "cas_ref": sha("8"),
            "runtime_event_ref": sha("e"),
            "provenance_kind": "runtime_emitted",
            "producer_component": "polisyos.scholar.academic_evidence",
        }
    )

    assert report["status"] == "fail"
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert issue_codes >= {
        "policy_design_scholar_research_intent_missing",
        "policy_design_scholar_query_graph_missing",
        "policy_design_scholar_provider_traces_missing",
        "policy_design_scholar_source_scoring_missing",
        "policy_design_scholar_snippets_missing",
        "policy_design_scholar_citations_missing",
        "policy_design_scholar_freshness_missing",
        "policy_design_scholar_corpus_lineage_missing",
        "policy_design_scholar_support_links_missing",
        "policy_design_scholar_conflict_links_missing",
    }


def test_scholar_evidence_rejects_narrative_citation_without_runtime_provenance() -> None:
    evidence = complete_quality_evidence()
    scholar = _scholar_academic_evidence()
    citation = deepcopy(scholar["citations"][0])  # type: ignore[index]
    assert isinstance(citation, dict)
    citation["source_surface"] = "narrative_citation"
    citation["provenance_kind"] = "narrative_citation"
    citation["evidence_ref"] = "OECD 2024 says this policy works."
    citation["snippet_ids"] = []
    scholar["citations"] = [citation]
    evidence["scholar_evidence"] = scholar

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert "policy_design_scholar_narrative_citation_without_provenance" in blocking_codes(
        scorecard
    )


def test_scholar_evidence_blocks_stale_literature_freshness() -> None:
    evidence = complete_quality_evidence()
    scholar = _scholar_academic_evidence()
    freshness = deepcopy(scholar["freshness"])
    assert isinstance(freshness, dict)
    freshness["status"] = "stale"
    freshness["max_source_age_days"] = 365
    sources = deepcopy(freshness["sources"])
    assert isinstance(sources, list)
    sources[0]["published_at"] = "2021-01-01"
    sources[0]["age_days"] = 1962
    sources[0]["status"] = "stale"
    freshness["sources"] = sources
    scholar["freshness"] = freshness
    evidence["scholar_evidence"] = scholar

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert "policy_design_scholar_literature_freshness_stale" in blocking_codes(scorecard)


def test_scholar_evidence_requires_duplicate_polarity_and_dependence_records() -> None:
    report = normalize_scholar_academic_evidence_report(
        {
            key: value
            for key, value in _scholar_academic_evidence().items()
            if key
            not in {
                "duplicate_markers",
                "polarity_markers",
                "dependence_records",
                "participation_downgrade_records",
            }
        }
    )

    issue_codes = {issue["code"] for issue in report["issues"]}

    assert issue_codes >= {
        "policy_design_scholar_duplicate_markers_missing",
        "policy_design_scholar_polarity_markers_missing",
        "policy_design_scholar_dependence_records_missing",
        "policy_design_scholar_participation_downgrade_missing",
    }


def test_scholar_evidence_collapses_multiple_publications_from_same_underlying_study() -> None:
    scholar = _scholar_academic_evidence()
    scholar["selected_sources"] = [
        {
            "source_id": "literature:study-working-paper",
            "source_family": "academic_working_paper",
            "source_family_independence_tag": "study:credit-panel-2025",
            "underlying_study_id": "credit-panel-2025",
            "rights": "open_metadata",
        },
        {
            "source_id": "literature:study-journal-article",
            "source_family": "academic_peer_reviewed",
            "source_family_independence_tag": "study:credit-panel-2025",
            "underlying_study_id": "credit-panel-2025",
            "rights": "open_metadata",
        },
    ]
    scholar["source_scoring"] = [
        {
            "source_id": "literature:study-working-paper",
            "quality_score": 0.82,
            "freshness_score": 0.9,
            "relevance_score": 0.88,
            "independence_score": 1.0,
        },
        {
            "source_id": "literature:study-journal-article",
            "quality_score": 0.9,
            "freshness_score": 0.95,
            "relevance_score": 0.9,
            "independence_score": 1.0,
        },
    ]
    scholar["freshness"]["sources"] = [  # type: ignore[index]
        {
            "source_id": "literature:study-working-paper",
            "published_at": "2025-05-01",
            "age_days": 381,
            "status": "pass",
        },
        {
            "source_id": "literature:study-journal-article",
            "published_at": "2025-09-01",
            "age_days": 258,
            "status": "pass",
        },
    ]
    scholar["source_family_independence_tags"] = {
        "literature:study-working-paper": "study:credit-panel-2025",
        "literature:study-journal-article": "study:credit-panel-2025",
    }
    scholar["dependence_records"] = []

    report = normalize_scholar_academic_evidence_report(scholar)

    assert "policy_design_scholar_source_family_dependence_unaccounted" in {
        issue["code"] for issue in report["issues"]
    }


def test_scholar_evidence_preserves_participation_like_downgrade() -> None:
    scholar = _scholar_academic_evidence()
    scholar["support_links"] = [
        {
            "link_id": "support:consultation-review:rec_1",
            "claim_id": "rec_1",
            "claim_use_requested": "prevalence",
            "authority_level": "production",
            "population_scope": "affected_population",
            "source_ids": ["literature:msme-survival-review"],
            "snippet_ids": ["snippet:msme-survival-review:1"],
            "citation_ids": ["citation:msme-survival-review"],
        }
    ]
    scholar["participation_downgrade_records"] = [
        {
            "record_id": "participation-downgrade:rec_1:prevalence",
            "claim_id": "rec_1",
            "claim_use_requested": "prevalence",
            "claim_use_allowed": "context-only",
            "authority_level": "production",
            "population_scope": "affected_population",
            "authority_boundary": "academic_publication_not_participation_provenance",
            "downgrade_reason": "scholar_source_cannot_satisfy_affected_population_prevalence",
            "public_projection_effect": "show_limitation",
        }
    ]

    report = normalize_scholar_academic_evidence_report(scholar)

    assert report["issues"] == []
    assert report["status"] == "pass"


def test_scholar_evidence_blocks_participation_like_support_without_downgrade() -> None:
    scholar = _scholar_academic_evidence()
    scholar["support_links"] = [
        {
            "link_id": "support:consultation-review:rec_1",
            "claim_id": "rec_1",
            "claim_use_requested": "prevalence",
            "authority_level": "production",
            "population_scope": "affected_population",
            "source_ids": ["literature:msme-survival-review"],
            "snippet_ids": ["snippet:msme-survival-review:1"],
            "citation_ids": ["citation:msme-survival-review"],
        }
    ]
    scholar["participation_downgrade_records"] = []

    report = normalize_scholar_academic_evidence_report(scholar)

    assert "policy_design_scholar_participation_downgrade_missing" in {
        issue["code"] for issue in report["issues"]
    }


def test_scholar_web_bundle_adapter_emits_w3d_markers_and_participation_downgrade() -> None:
    brief = ResearchBrief(
        question="Do affected MSMEs prefer wartime credit guarantees?",
        domain="wartime_msme_support",
        jurisdictions=["UA"],
        required_source_types=["academic"],
    )
    graph = QueryGraph(
        brief=brief,
        nodes=[
            QueryNode(
                node_id="q1",
                query="affected MSME credit guarantees preference Ukraine study",
                perspective="academic evidence",
                status="searched",
                hit_count=2,
            )
        ],
        root_node_ids=["q1"],
    )
    sources = [
        SourceMetadata(
            source_id="literature:credit-panel-working-paper",
            url="https://example.org/credit-panel-working-paper",
            title="Credit guarantees and MSME outcomes",
            domain="example.org",
            source_type="academic",
            provider="fixture",
            search_query="affected MSME credit guarantees preference Ukraine study",
            search_rank=1,
            fetched_at=datetime(2026, 5, 17, tzinfo=UTC),
            published_at=datetime(2025, 9, 1, tzinfo=UTC),
            page_age_days=258,
            content_sha256="credit-panel-study",
            quality_score=0.91,
        ),
        SourceMetadata(
            source_id="literature:credit-panel-journal-article",
            url="https://example.org/credit-panel-journal-article",
            title="Credit guarantees and MSME outcomes, journal version",
            domain="example.org",
            source_type="academic",
            provider="fixture",
            search_query="affected MSME credit guarantees preference Ukraine study",
            search_rank=2,
            fetched_at=datetime(2026, 5, 17, tzinfo=UTC),
            published_at=datetime(2025, 10, 1, tzinfo=UTC),
            page_age_days=228,
            content_sha256="credit-panel-study",
            quality_score=0.88,
            duplicate_of_source_id="literature:credit-panel-working-paper",
        ),
    ]
    snippets = [
        SourceSnippet(
            snippet_id="snippet:working-paper:1",
            source_id="literature:credit-panel-working-paper",
            url="https://example.org/credit-panel-working-paper",
            query_node_id="q1",
            perspective="academic evidence",
            text=(
                "The study reports improved access to finance, but not "
                "affected-person preference."
            ),
            start_char=10,
            end_char=88,
            relevance_score=0.9,
        ),
        SourceSnippet(
            snippet_id="snippet:journal-article:1",
            source_id="literature:credit-panel-journal-article",
            url="https://example.org/credit-panel-journal-article",
            query_node_id="q1",
            perspective="academic evidence",
            text="The journal article reuses the same underlying study population.",
            start_char=12,
            end_char=74,
            relevance_score=0.87,
        ),
    ]
    bundle = WebEvidenceBundle(
        bundle_id="bundle-credit-panel",
        brief=brief,
        query_graph=graph,
        query_traces=[
            SearchQueryTrace(
                query_node_id="q1",
                query="affected MSME credit guarantees preference Ukraine study",
                perspective="academic evidence",
                provider="fixture",
                hit_count=2,
            )
        ],
        sources=sources,
        snippets=snippets,
        claim_supports=[
            ClaimSupportLink(
                claim_id="rec_1",
                claim_text="Affected MSMEs prefer wartime credit guarantees.",
                snippet_ids=["snippet:working-paper:1", "snippet:journal-article:1"],
                source_ids=[
                    "literature:credit-panel-working-paper",
                    "literature:credit-panel-journal-article",
                ],
                support_score=0.24,
                conflict_score=0.0,
                metadata={
                    "support_status": "supported",
                    "claim_use_requested": "prevalence",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                },
            )
        ],
    )

    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=sha("8"),
        bundle=bundle,
        corpus_snapshot_ref=sha("a"),
        lineage_ref=sha("b"),
    )

    assert report["issues"] == []
    assert report["status"] == "pass"
    assert report["capability_reality_status"] == "implemented"
    assert "academic_support_links" in report["runtime_authority_envelope"]["authoritative_for"]
    assert (
        "affected_person_representativeness"
        in report["runtime_authority_envelope"]["may_not_use_for"]
    )
    assert report["duplicate_markers"] == [
        {
            "marker_id": "duplicate:literature:credit-panel-journal-article",
            "source_id": "literature:credit-panel-journal-article",
            "duplicate_source_id": "literature:credit-panel-journal-article",
            "canonical_source_id": "literature:credit-panel-working-paper",
            "duplicate_basis": "content_sha256",
        }
    ]
    assert report["dependence_records"][0]["raw_source_count"] == 2
    assert report["dependence_records"][0]["effective_source_count"] == 1
    assert report["participation_downgrade_records"][0]["claim_use_allowed"] == "context-only"


def test_scholar_web_bundle_adapter_discounts_same_family_without_duplicate_flag() -> None:
    bundle = {
        "bundle_id": "bundle-shared-study",
        "brief": {
            "question": "Do credit guarantees improve MSME survival?",
            "domain": "wartime_msme_support",
            "jurisdictions": ["UA"],
            "required_source_types": ["academic"],
        },
        "query_graph": {
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "credit guarantees MSME survival Ukraine study",
                    "perspective": "academic evidence",
                    "status": "searched",
                    "hit_count": 2,
                }
            ],
            "root_node_ids": ["q1"],
        },
        "query_traces": [
            {
                "query_node_id": "q1",
                "query": "credit guarantees MSME survival Ukraine study",
                "perspective": "academic evidence",
                "provider": "fixture",
                "hit_count": 2,
            }
        ],
        "sources": [
            {
                "source_id": "literature:working-paper",
                "url": "https://example.org/working-paper",
                "title": "Credit guarantees and MSME survival",
                "domain": "example.org",
                "source_type": "academic",
                "provider": "fixture",
                "published_at": "2025-09-01T00:00:00+00:00",
                "page_age_days": 258,
                "content_sha256": "same-underlying-study",
                "quality_score": 0.9,
            },
            {
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "title": "Credit guarantees and MSME survival, journal version",
                "domain": "example.org",
                "source_type": "academic",
                "provider": "fixture",
                "published_at": "2025-10-01T00:00:00+00:00",
                "page_age_days": 228,
                "content_sha256": "same-underlying-study",
                "quality_score": 0.88,
            },
        ],
        "snippets": [
            {
                "snippet_id": "snippet:working-paper:1",
                "source_id": "literature:working-paper",
                "url": "https://example.org/working-paper",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The working paper reports higher MSME survival.",
                "start_char": 0,
                "end_char": 48,
                "relevance_score": 0.9,
            },
            {
                "snippet_id": "snippet:journal-version:1",
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The journal article uses the same underlying study.",
                "start_char": 0,
                "end_char": 52,
                "relevance_score": 0.87,
            },
        ],
        "claim_supports": [
            {
                "claim_id": "rec_1",
                "claim_text": "Credit guarantees improve MSME survival.",
                "snippet_ids": [
                    "snippet:working-paper:1",
                    "snippet:journal-version:1",
                ],
                "source_ids": [
                    "literature:working-paper",
                    "literature:journal-version",
                ],
                "support_score": 0.7,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            }
        ],
    }

    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=sha("9"),
        bundle=bundle,
        corpus_snapshot_ref=sha("a"),
        lineage_ref=sha("b"),
    )

    assert report["issues"] == []
    assert report["dependence_records"] == [
        {
            "record_id": "dependence:same-underlying-study",
            "source_ids": ["literature:working-paper", "literature:journal-version"],
            "source_family_independence_tag": "same-underlying-study",
            "underlying_study_id": "same-underlying-study",
            "dependence_basis": "source_family_independence_tag",
            "raw_source_count": 2,
            "effective_source_count": 1,
        }
    ]
    assert {
        row["source_id"]: row["independence_score"] for row in report["source_scoring"]
    } == {
        "literature:working-paper": 0.5,
        "literature:journal-version": 0.5,
    }


def test_scholar_adapter_blocks_requirement_support_inflation_from_dependent_corpus() -> None:
    spec = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": "run.scholar.w7d",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_text": "Credit guarantees improve MSME survival.",
                    "claim_type": "causal",
                    "claim_family": "causal",
                    "claim_use": "decision_support",
                }
            ],
        }
    ).requirements[0]
    bundle = {
        "bundle_id": "bundle-shared-study",
        "brief": {
            "question": "Do credit guarantees improve MSME survival?",
            "required_source_types": ["academic"],
        },
        "query_graph": {
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "credit guarantees MSME survival Ukraine study",
                    "perspective": "academic evidence",
                    "status": "searched",
                    "hit_count": 2,
                }
            ],
            "root_node_ids": ["q1"],
        },
        "query_traces": [
            {
                "query_node_id": "q1",
                "query": "credit guarantees MSME survival Ukraine study",
                "perspective": "academic evidence",
                "provider": "fixture",
                "hit_count": 2,
            }
        ],
        "sources": [
            {
                "source_id": "literature:working-paper",
                "url": "https://example.org/working-paper",
                "title": "Credit guarantees and MSME survival",
                "domain": "example.org",
                "source_type": "academic",
                "publication_tier": "peer_reviewed",
                "underlying_study_id": "credit-panel-2025",
                "provider": "fixture",
                "published_at": "2025-09-01T00:00:00+00:00",
                "page_age_days": 258,
                "content_sha256": "credit-panel-study",
                "quality_score": 0.9,
            },
            {
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "title": "Credit guarantees and MSME survival, journal version",
                "domain": "example.org",
                "source_type": "academic",
                "publication_tier": "peer_reviewed",
                "underlying_study_id": "credit-panel-2025",
                "provider": "fixture",
                "published_at": "2025-10-01T00:00:00+00:00",
                "page_age_days": 228,
                "content_sha256": "credit-panel-study",
                "quality_score": 0.88,
            },
        ],
        "snippets": [
            {
                "snippet_id": "snippet:working-paper:1",
                "source_id": "literature:working-paper",
                "url": "https://example.org/working-paper",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The working paper reports higher MSME survival.",
                "start_char": 0,
                "end_char": 48,
                "relevance_score": 0.9,
            },
            {
                "snippet_id": "snippet:journal-version:1",
                "source_id": "literature:journal-version",
                "url": "https://example.org/journal-version",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The journal article uses the same underlying study.",
                "start_char": 0,
                "end_char": 52,
                "relevance_score": 0.87,
            },
        ],
        "claim_supports": [
            {
                "claim_id": "rec_1",
                "claim_text": "Credit guarantees improve MSME survival.",
                "snippet_ids": ["snippet:working-paper:1", "snippet:journal-version:1"],
                "source_ids": ["literature:working-paper", "literature:journal-version"],
                "support_score": 0.7,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            }
        ],
    }

    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=sha("w7d-dependent-corpus"),
        bundle=bundle,
        corpus_snapshot_ref=sha("a"),
        lineage_ref=sha("b"),
        requirement_specs=[spec],
    )

    assert report["status"] == "blocked"
    assert report["support_links"][0]["requirement_id"] == spec.requirement_id
    assert report["support_links"][0]["effective_support_count"] == 1
    assert report["support_links"][0]["required_replication_count"] == 2
    assert report["dependence_records"][0]["collapse_reasons"] == ["shared_underlying_study"]
    assert {
        blocker["code"] for blocker in report["literature_deficit_blockers"]
    } >= {
        "policy_design_scholar_requirement_replication_unmet",
        "policy_design_scholar_requirement_independence_unmet",
    }


def test_scholar_requirement_satisfied_by_claim_source_has_no_deficit_blockers() -> None:
    spec = ScholarSupportRequirementSpec(
        requirement_id="scholar-support:run:rec_1",
        claim_id="rec_1",
        claim_text="Credit guarantees improve MSME survival.",
        required_publication_tier="peer_reviewed",
        recency_days=365,
        required_replication_count=1,
        required_independence_breadth=1,
        required_citation_network_depth=2,
        dependent_corpus_collapse_rules=[
            {"rule_id": "collapse:study", "collapse_on": "underlying_study_id"}
        ],
    )
    bundle = {
        "bundle_id": "bundle-satisfied-requirement",
        "brief": {
            "question": "Do credit guarantees improve MSME survival?",
            "required_source_types": ["academic"],
        },
        "query_graph": {
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "credit guarantees MSME survival peer reviewed",
                    "perspective": "academic evidence",
                    "status": "searched",
                    "hit_count": 1,
                }
            ],
            "root_node_ids": ["q1"],
        },
        "query_traces": [
            {
                "query_node_id": "q1",
                "query": "credit guarantees MSME survival peer reviewed",
                "perspective": "academic evidence",
                "provider": "fixture",
                "hit_count": 1,
            }
        ],
        "sources": [
            {
                "source_id": "literature:peer-current",
                "url": "https://example.org/peer-current",
                "title": "Credit guarantees and MSME survival",
                "domain": "example.org",
                "source_type": "academic",
                "publication_tier": "peer_reviewed",
                "underlying_study_id": "peer-current",
                "provider": "fixture",
                "page_age_days": 30,
                "citation_network_refs": ["citation:a", "citation:b"],
                "quality_score": 0.95,
            }
        ],
        "snippets": [
            {
                "snippet_id": "snippet:peer-current:1",
                "source_id": "literature:peer-current",
                "url": "https://example.org/peer-current",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The peer-reviewed study reports higher MSME survival.",
                "start_char": 0,
                "end_char": 55,
                "relevance_score": 0.9,
            }
        ],
        "claim_supports": [
            {
                "claim_id": "rec_1",
                "claim_text": "Credit guarantees improve MSME survival.",
                "snippet_ids": ["snippet:peer-current:1"],
                "source_ids": ["literature:peer-current"],
                "support_score": 0.8,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            }
        ],
    }

    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=sha("w7d-satisfied-requirement"),
        bundle=bundle,
        corpus_snapshot_ref=sha("a"),
        lineage_ref=sha("b"),
        requirement_specs=[spec],
    )

    assert report["status"] == "pass"
    assert report["literature_deficit_blockers"] == []


def test_scholar_requirement_deficits_are_claim_bound() -> None:
    spec = ScholarSupportRequirementSpec(
        requirement_id="scholar-support:run:rec_1",
        claim_id="rec_1",
        claim_text="Credit guarantees improve MSME survival.",
        required_publication_tier="peer_reviewed",
        recency_days=365,
        required_replication_count=1,
        required_independence_breadth=1,
        required_citation_network_depth=2,
        dependent_corpus_collapse_rules=[
            {"rule_id": "collapse:study", "collapse_on": "underlying_study_id"}
        ],
    )
    bundle = {
        "bundle_id": "bundle-claim-bound-tier",
        "brief": {
            "question": "Do credit guarantees improve MSME survival?",
            "required_source_types": ["academic"],
        },
        "query_graph": {
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "credit guarantees MSME survival evidence",
                    "perspective": "academic evidence",
                    "status": "searched",
                    "hit_count": 2,
                }
            ],
            "root_node_ids": ["q1"],
        },
        "query_traces": [
            {
                "query_node_id": "q1",
                "query": "credit guarantees MSME survival evidence",
                "perspective": "academic evidence",
                "provider": "fixture",
                "hit_count": 2,
            }
        ],
        "sources": [
            {
                "source_id": "literature:grey-stale",
                "url": "https://example.org/grey-stale",
                "title": "Credit guarantee note",
                "domain": "example.org",
                "source_type": "grey_literature",
                "publication_tier": "grey_literature",
                "underlying_study_id": "grey-note",
                "provider": "fixture",
                "page_age_days": 900,
                "citation_network_refs": ["citation:one-hop"],
                "quality_score": 0.5,
            },
            {
                "source_id": "literature:peer-other-claim",
                "url": "https://example.org/peer-other",
                "title": "Peer-reviewed study for another claim",
                "domain": "example.org",
                "source_type": "academic",
                "publication_tier": "peer_reviewed",
                "underlying_study_id": "peer-other",
                "provider": "fixture",
                "page_age_days": 30,
                "citation_network_refs": ["citation:a", "citation:b"],
                "quality_score": 0.95,
            },
        ],
        "snippets": [
            {
                "snippet_id": "snippet:grey-stale:1",
                "source_id": "literature:grey-stale",
                "url": "https://example.org/grey-stale",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The policy note claims higher MSME survival.",
                "start_char": 0,
                "end_char": 45,
                "relevance_score": 0.7,
            },
            {
                "snippet_id": "snippet:peer-other:1",
                "source_id": "literature:peer-other-claim",
                "url": "https://example.org/peer-other",
                "query_node_id": "q1",
                "perspective": "academic evidence",
                "text": "The peer-reviewed study concerns a separate monitoring claim.",
                "start_char": 0,
                "end_char": 61,
                "relevance_score": 0.8,
            },
        ],
        "claim_supports": [
            {
                "claim_id": "rec_1",
                "claim_text": "Credit guarantees improve MSME survival.",
                "snippet_ids": ["snippet:grey-stale:1"],
                "source_ids": ["literature:grey-stale"],
                "support_score": 0.6,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            },
            {
                "claim_id": "rec_2",
                "claim_text": "Monitoring reports improve compliance.",
                "snippet_ids": ["snippet:peer-other:1"],
                "source_ids": ["literature:peer-other-claim"],
                "support_score": 0.6,
                "conflict_score": 0.0,
                "metadata": {"support_status": "supported"},
            },
        ],
    }

    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=sha("w7d-claim-bound-tier"),
        bundle=bundle,
        corpus_snapshot_ref=sha("a"),
        lineage_ref=sha("b"),
        requirement_specs=[spec],
    )

    assert report["status"] == "blocked"
    assert report["support_links"][0]["required_recency_days"] == 365
    assert {
        blocker["code"] for blocker in report["literature_deficit_blockers"]
    } >= {
        "policy_design_scholar_requirement_publication_tier_unmet",
        "policy_design_scholar_requirement_recency_unmet",
        "policy_design_scholar_requirement_citation_network_depth_unmet",
    }


def test_scholar_adapter_preserves_participation_firewall_with_requirement_spec() -> None:
    spec = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": "run.scholar.participation",
            "authority_level": "production",
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_text": "Affected MSMEs prefer credit guarantees.",
                    "claim_type": "factual",
                    "claim_family": "preference",
                    "claim_use": "prevalence",
                    "population_scope": "affected_population",
                }
            ],
        }
    ).requirements[0]
    scholar = _scholar_academic_evidence()
    scholar["support_requirement_specs"] = [spec.model_dump(mode="json")]
    scholar["support_links"] = [
        {
            "link_id": "support:publication:rec_1",
            "claim_id": "rec_1",
            "claim_use_requested": "prevalence",
            "claim_use_allowed": "context-only",
            "authority_level": "production",
            "population_scope": "affected_population",
            "requirement_id": spec.requirement_id,
            "source_ids": ["literature:msme-survival-review"],
            "snippet_ids": ["snippet:msme-survival-review:1"],
            "citation_ids": ["citation:msme-survival-review"],
        }
    ]
    scholar["participation_downgrade_records"] = []

    report = normalize_scholar_academic_evidence_report(scholar)

    assert report["issues"] == []
    assert report["participation_downgrade_records"][0]["claim_use_allowed"] == "context-only"
    assert (
        report["participation_downgrade_records"][0]["authority_boundary"]
        == "academic_publication_not_participation_provenance"
    )


def test_scholar_spine_binding_carries_requirement_refs() -> None:
    spec = ScholarSupportRequirementSpec(
        requirement_id="scholar-support:run:claim.1",
        claim_id="claim.1",
        claim_text="A supported claim.",
        required_publication_tier="peer_reviewed",
        recency_days=730,
        required_replication_count=2,
        required_independence_breadth=2,
        required_citation_network_depth=2,
        dependent_corpus_collapse_rules=[
            {"rule_id": "collapse:study", "collapse_on": "underlying_study_id"}
        ],
    )

    binding = build_scholar_spine_evidence_binding(
        literature_refs=["sha256:literature"],
        requirement_specs=[spec],
    )

    assert binding["requirement_refs"] == ["scholar-support:run:claim.1"]
    assert binding["requirements"][0]["required_independence_breadth"] == 2
