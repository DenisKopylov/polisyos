# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy

from polisyos.runtime.quality.scholar_academic_evidence import (
    build_scholar_academic_evidence_boundary_record,
    normalize_scholar_academic_evidence_report,
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
