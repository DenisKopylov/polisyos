from __future__ import annotations

from polisyos.lex.normpack.applicability_report import (
    build_normative_applicability_report,
    build_runtime_normative_applicability_report,
    normalize_normative_applicability_report,
)


def _norm(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "norm_id": "norm.ua.credit_eligibility",
        "artifact_id": "sha256:" + "1" * 64,
        "fact_class": "credit_eligibility_rule",
        "jurisdiction": "UA",
        "policy_domain": "wartime_msme_support",
        "effective_from": "2024-01-01",
        "effective_to": "",
        "source_authority": "Verkhovna Rada",
        "authority_level": "statute",
        "relevance_rationale": "Defines wartime MSME credit eligibility.",
    }
    payload.update(overrides)
    return payload


def test_normative_applicability_report_passes_for_applicable_norm_and_claim() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        candidate_norms=[_norm()],
        recommendation_claims=[
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
    )

    assert report["status"] == "pass"
    assert report["applied_norms"][0]["norm_id"] == "norm.ua.credit_eligibility"
    assert report["rejected_norms"] == []
    assert report["recommendation_coverage"][0]["status"] == "pass"
    assert report["blocking_issue_count"] == 0


def test_normative_report_emits_legal_retrieval_authority_trace() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        candidate_norms=[
            _norm(),
            _norm(
                norm_id="norm.ua.procurement_fixture",
                policy_domain="procurement",
            ),
        ],
        recommendation_claims=[
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        query_terms=["credit support", "wartime MSME eligibility"],
        concept_refs=["concept.msme_survival_rate"],
        legal_corpus_snapshot={
            "snapshot_ref": "sha256:" + "d" * 64,
            "store_kind": "lex_knowledge_graph",
        },
        conflicts=[{"conflict_id": "conflict:resolved-credit-eligibility"}],
    )

    assert report["retrieval_status"] == "completed"
    assert report["legal_corpus_snapshot"]["snapshot_ref"] == "sha256:" + "d" * 64
    assert report["query_terms"] == ["credit support", "wartime MSME eligibility"]
    assert report["concept_refs"] == ["concept.msme_survival_rate"]
    assert report["jurisdiction_filters"] == ["UA"]
    assert report["time_filters"] == ["2026-05-12"]
    assert [norm["norm_id"] for norm in report["candidate_norms"]] == [
        "norm.ua.credit_eligibility",
        "norm.ua.procurement_fixture",
    ]
    assert [norm["norm_id"] for norm in report["selected_norms"]] == [
        "norm.ua.credit_eligibility"
    ]
    assert report["rejected_norms"][0]["reason_code"] == "wrong_policy_domain"
    assert report["conflicts"][0]["conflict_id"] == "conflict:resolved-credit-eligibility"
    assert report["competence"][0]["norm_id"] == "norm.ua.credit_eligibility"
    assert report["authority_blockers"] == []
    assert report["recommendation_coverage"][0]["candidate_norm_refs"] == [
        "norm.ua.credit_eligibility",
        "norm.ua.procurement_fixture",
    ]
    assert report["recommendation_coverage"][0]["selected_norm_refs"] == [
        "norm.ua.credit_eligibility"
    ]
    assert report["recommendation_coverage"][0]["rejected_norm_refs"] == []


def test_normative_report_distinguishes_no_norm_failure_and_missing_store() -> None:
    base = {
        "target_context": {
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        "candidate_norms": [],
        "recommendation_claims": [
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "norm_refs": [],
            }
        ],
        "query_terms": ["credit eligibility"],
        "legal_corpus_snapshot": {"snapshot_ref": "sha256:" + "d" * 64},
    }

    no_relevant = build_normative_applicability_report(
        **base,
        retrieval_status="no_relevant_norm_found",
    )
    retrieval_failed = build_normative_applicability_report(
        **base,
        retrieval_status="retrieval_failed",
    )
    missing_store_base = {**base, "legal_corpus_snapshot": None}
    missing_store = build_normative_applicability_report(
        **missing_store_base,
        retrieval_status="missing_store",
    )

    assert no_relevant["retrieval_status"] == "no_relevant_norm_found"
    assert no_relevant["authority_blockers"][0]["code"] == "no_relevant_norm_found"
    assert retrieval_failed["retrieval_status"] == "retrieval_failed"
    assert retrieval_failed["authority_blockers"][0]["code"] == "lex_retrieval_failed"
    assert missing_store["retrieval_status"] == "missing_store"
    assert missing_store["authority_blockers"][0]["code"] == "lex_legal_store_missing"


def test_no_candidate_norm_requires_query_normalization_report() -> None:
    incomplete = normalize_normative_applicability_report(
        {
            "schema_version": "policyos.lex.normative_applicability_report.v1",
            "status": "fail",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-20",
            },
            "retrieval_status": "no_relevant_norm_found",
            "legal_corpus_snapshot": {
                "kg_path": "/data/legal/finalize/lex_knowledge_graph.duckdb",
                "store_kind": "lex_knowledge_graph",
            },
            "query_terms": ["credit eligibility"],
            "candidate_norms": [],
            "authority_blockers": [{"code": "no_relevant_norm_found"}],
            "recommendation_coverage": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": [],
                }
            ],
        }
    )

    assert "lex_query_normalization_report_missing" in incomplete["issue_codes"]

    complete = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-20",
        },
        candidate_norms=[],
        recommendation_claims=[
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "norm_refs": [],
            }
        ],
        query_terms=["credit eligibility"],
        legal_corpus_snapshot={
            "kg_path": "/data/legal/finalize/lex_knowledge_graph.duckdb",
            "store_kind": "lex_knowledge_graph",
        },
    )

    normalization = complete["query_normalization_report"]
    assert normalization["blocker_code"] == "no_relevant_norm_found"
    assert normalization["kg_paths"] == ["/data/legal/finalize/lex_knowledge_graph.duckdb"]
    assert normalization["language_coverage"]["status"] == "pass"
    assert normalization["normalized_terms"]
    assert "lex_query_normalization_report_missing" not in complete["issue_codes"]
    assert "lex_zero_candidate_query_trace_incomplete" not in complete["issue_codes"]


def test_query_normalization_legal_requirements_survive_without_top_level() -> None:
    nested_requirements = [
        {
            "requirement_id": f"legal_requirement_{index}",
            "domain": "legal",
            "expected_family": "credit_eligibility_rule",
            "required_facets": ["competence_refs"],
            "jurisdiction": "UA",
        }
        for index in range(1, 5)
    ]

    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-20",
        },
        candidate_norms=[],
        recommendation_claims=[],
        query_terms=["credit eligibility"],
        query_normalization_report={
            "original_terms": ["credit eligibility"],
            "normalized_terms": ["кредит", "підприєм"],
            "kg_paths": ["/data/legal/finalize/lex_knowledge_graph.duckdb"],
            "language_coverage": {"status": "pass", "required": ["uk"], "covered": ["uk"]},
            "blocker_code": "no_relevant_norm_found",
            "legal_requirements": nested_requirements,
        },
        legal_corpus_snapshot={
            "kg_path": "/data/legal/finalize/lex_knowledge_graph.duckdb",
            "store_kind": "lex_knowledge_graph",
        },
    )

    assert len(report["legal_requirements"]) == 4
    assert report["summary"]["legal_requirement_count"] == 4


def test_global_candidate_pool_is_scored_into_per_claim_legal_anchors() -> None:
    candidate_norms = [
        _norm(
            norm_id=f"norm.ua.credit.{index:02d}",
            fact_class="credit_eligibility_rule",
            policy_instrument="wartime_credit_support",
            beneficiary_class="msme",
            fiscal_authority="ministry_of_finance",
            implementation_agency="ministry_of_economy",
            competent_authority="cabinet_of_ministers",
            legal_terms=["credit", "eligibility", "msme"],
        )
        for index in range(1, 12)
    ]
    candidate_norms.extend(
        _norm(
            norm_id=f"norm.ua.grant.{index:02d}",
            fact_class="grant_support_rule",
            policy_instrument="grant_support",
            beneficiary_class="msme",
            fiscal_authority="ministry_of_finance",
            implementation_agency="ministry_of_economy",
            competent_authority="cabinet_of_ministers",
            legal_terms=["grant", "non-repayable", "msme"],
        )
        for index in range(1, 12)
    )
    candidate_norms.extend(
        _norm(
            norm_id=f"norm.ua.monitoring.{index:02d}",
            fact_class="implementation_monitoring_rule",
            policy_instrument="monitoring",
            beneficiary_class="public_program",
            fiscal_authority="state_audit_service",
            implementation_agency="ministry_of_economy",
            competent_authority="cabinet_of_ministers",
            legal_terms=["monitoring", "reporting"],
        )
        for index in range(1, 12)
    )

    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-20",
        },
        candidate_norms=candidate_norms,
        recommendation_claims=[
            {
                "claim_id": "rec_credit",
                "major": True,
                "text": "Expand wartime credit eligibility for MSMEs.",
                "policy_instrument": "wartime_credit_support",
                "beneficiary_class": "msme",
                "fiscal_authority": "ministry_of_finance",
                "implementation_agency": "ministry_of_economy",
            },
            {
                "claim_id": "rec_grant",
                "major": True,
                "text": "Provide non-repayable grants for eligible MSMEs.",
                "policy_instrument": "grant_support",
                "beneficiary_class": "msme",
                "fiscal_authority": "ministry_of_finance",
                "implementation_agency": "ministry_of_economy",
            },
            {
                "claim_id": "rec_operational_dashboard",
                "major": True,
                "text": "Publish an operational monitoring dashboard.",
                "no_normative_anchor_rationale": (
                    "Operational transparency recommendation; no new legal authority asserted."
                ),
            },
        ],
    )

    anchors = {item["claim_id"]: item for item in report["claim_legal_anchors"]}
    assert report["summary"]["global_candidate_norm_count"] == 33
    assert report["global_candidate_norm_refs"] == report["candidate_norm_refs"]
    assert anchors["rec_credit"]["status"] == "pass"
    assert anchors["rec_credit"]["selected_norm_refs"]
    assert anchors["rec_credit"]["rejected_norm_refs"]
    assert all(
        ref.startswith("norm.ua.credit.")
        for ref in anchors["rec_credit"]["selected_norm_refs"]
    )
    assert anchors["rec_grant"]["status"] == "pass"
    assert anchors["rec_grant"]["selected_norm_refs"]
    assert all(
        ref.startswith("norm.ua.grant.")
        for ref in anchors["rec_grant"]["selected_norm_refs"]
    )
    assert anchors["rec_operational_dashboard"]["status"] == "pass"
    assert anchors["rec_operational_dashboard"]["reason_code"] == (
        "explicit_no_anchor_rationale"
    )
    assert anchors["rec_operational_dashboard"]["selected_norm_refs"] == []
    assert report["recommendation_coverage"][0]["selected_norm_refs"] == (
        anchors["rec_credit"]["selected_norm_refs"]
    )


def test_normative_applicability_report_rejects_unusable_norms() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        candidate_norms=[
            _norm(norm_id="norm.de.wrong_jurisdiction", jurisdiction="DE"),
            _norm(norm_id="norm.ua.expired", effective_to="2024-12-31"),
            _norm(
                norm_id="norm.ua.missing_authority",
                source_authority="",
                authority_level="",
            ),
        ],
        recommendation_claims=[
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Ground the recommendation in expired law.",
                "norm_refs": ["norm.ua.expired"],
            }
        ],
    )

    rejected = {norm["norm_id"]: norm for norm in report["rejected_norms"]}
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert rejected["norm.de.wrong_jurisdiction"]["reason_code"] == "wrong_jurisdiction"
    assert rejected["norm.ua.expired"]["reason_code"] == "expired_norm"
    assert rejected["norm.ua.missing_authority"]["reason_code"] == (
        "missing_authority_metadata"
    )
    assert "recommendation_references_rejected_norm" in issue_codes
    assert "no_applicable_norms" in issue_codes


def test_normative_applicability_report_requires_major_claim_anchor_or_rationale() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        candidate_norms=[_norm()],
        recommendation_claims=[
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Spend public funds without a legal anchor.",
                "norm_refs": [],
            },
            {
                "claim_id": "rec_2",
                "major": True,
                "text": "Use non-normative operational telemetry only.",
                "norm_refs": [],
                "no_normative_anchor_rationale": (
                    "Operational monitoring claim; no new legal authority asserted."
                ),
            },
        ],
    )

    coverage = {item["claim_id"]: item for item in report["recommendation_coverage"]}
    assert report["status"] == "fail"
    assert coverage["rec_1"]["status"] == "fail"
    assert coverage["rec_1"]["reason_code"] == "missing_normative_anchor"
    assert coverage["rec_2"]["status"] == "pass"
    assert coverage["rec_2"]["reason_code"] == "explicit_no_anchor_rationale"


def test_normalize_report_refuses_pass_status_with_inapplicable_norm() -> None:
    normalized = normalize_normative_applicability_report(
        {
            "status": "pass",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "applied_norms": [_norm(jurisdiction="DE")],
            "recommendation_coverage": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        }
    )

    assert normalized["status"] == "fail"
    assert normalized["issues"][0]["code"] == "wrong_jurisdiction"


def test_normalize_report_refuses_wrong_jurisdiction_selected_norm_false_pass() -> None:
    normalized = normalize_normative_applicability_report(
        {
            "schema_version": "policyos.lex.normative_applicability_report.v1",
            "status": "pass",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "retrieval_status": "completed",
            "legal_corpus_snapshot": {"snapshot_ref": "sha256:" + "d" * 64},
            "query_terms": ["credit support"],
            "selected_norms": [_norm(norm_id="norm.de.credit_eligibility", jurisdiction="DE")],
            "recommendation_coverage": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.de.credit_eligibility"],
                }
            ],
        }
    )

    assert normalized["status"] == "fail"
    assert normalized["issues"][0]["code"] == "wrong_jurisdiction"


def test_normalize_report_rejects_legal_shaped_payload_without_retrieval_trace() -> None:
    normalized = normalize_normative_applicability_report(
        {
            "schema_version": "policyos.lex.normative_applicability_report.v1",
            "status": "pass",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "applied_norms": [_norm()],
            "recommendation_coverage": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        }
    )

    assert normalized["status"] == "fail"
    assert "legal_retrieval_trace_missing" in normalized["issue_codes"]


def test_runtime_report_collects_context_norms_and_recommendation_claims() -> None:
    report = build_runtime_normative_applicability_report(
        context={
            "target_context": {
                "context_id": "UA_WARTIME_MSME_2026",
                "countries": ["UA"],
                "publication_year": 2026,
            },
            "policy_domain": "wartime_msme_support",
            "lex_candidate_norms": [_norm()],
            "policy_recommendations": [
                {
                    "claim_id": "rec_1",
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        domain_hint="Ukraine wartime MSME support policy",
        selected_variant={},
        as_of="2026-05-12",
    )

    assert report["status"] == "pass"
    assert report["target_context"]["jurisdiction"] == "UA"
    assert report["target_context"]["policy_domain"] == "wartime_msme_support"
    assert report["applied_norms"][0]["source_authority"] == "Verkhovna Rada"
    assert report["applied_norms"][0]["effective_from"] == "2024-01-01"
    assert report["recommendation_coverage"][0]["claim_id"] == "rec_1"
