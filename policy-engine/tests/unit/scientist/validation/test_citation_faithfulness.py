from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.scientist.validation.citation_faithfulness import (
    BLOCKING_CITATION_LABELS,
    SCHEMA_VERSION,
    build_citation_faithfulness_report,
    build_policy_context_citation_faithfulness_report,
)

GOLDEN_PATH = (
    Path(__file__).parents[3]
    / "_golden"
    / "quality"
    / "citation_faithfulness"
    / "cases.json"
)


def _golden() -> dict[str, object]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _cases() -> list[dict[str, object]]:
    return list(_golden()["cases"])  # type: ignore[index]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["case_id"])
def test_golden_cases_label_cited_evidence_offline(case: dict[str, object]) -> None:
    report = build_citation_faithfulness_report(
        claims=[case["claim"]],
        evidence=case["evidence"],
    )

    labels_by_ref = {
        citation["citation_ref"]: citation["label"]
        for claim in report["claims"]
        for citation in claim["citations"]
    }

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == case["expected_status"]
    assert labels_by_ref == case["expected_labels"]
    assert report["live_llm_judging_enabled"] is False


def test_required_mismatch_dimensions_are_represented_in_fixtures() -> None:
    golden = _golden()
    represented = {
        str(case.get("mismatch_dimension"))
        for case in _cases()
        if case.get("mismatch_dimension")
    }

    assert represented == set(golden["required_mismatch_dimensions"])


def test_public_factual_and_legal_claims_cannot_pass_with_bad_refs() -> None:
    bad_public_cases = [
        case
        for case in _cases()
        if case["case_id"]
        in {
            "contradicts_public_legal_claim",
            "irrelevant_public_factual_claim",
        }
    ]

    for case in bad_public_cases:
        report = build_citation_faithfulness_report(
            claims=[case["claim"]],
            evidence=case["evidence"],
        )
        labels = {
            citation["label"]
            for claim in report["claims"]
            for citation in claim["citations"]
        }
        blocking_codes = {issue["code"] for issue in report["issues"]}

        assert report["status"] == "fail"
        assert labels & BLOCKING_CITATION_LABELS
        assert "public_claim_has_unfaithful_citation" in blocking_codes


def test_public_factual_claim_without_citation_fails_claim_status() -> None:
    report = build_citation_faithfulness_report(
        claims=[
            {
                "claim_id": "fact.no_cite",
                "claim_family": "factual",
                "public": True,
                "text": "The programme increased firm survival rates.",
            }
        ],
        evidence=[],
    )

    assert report["status"] == "fail"
    assert report["claims"][0]["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} == {
        "public_claim_missing_citation"
    }


def test_policy_context_helper_builds_offline_evidence_from_runtime_payloads() -> None:
    report = build_policy_context_citation_faithfulness_report(
        claims=[
            {
                "claim_id": "legal.supported",
                "claim_family": "legal",
                "public": True,
                "text": "The rule authorizes targeted credit support.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        normative_evidence={
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "legal_text": "The rule authorizes targeted credit support for eligible firms.",
                }
            ]
        },
        fabric_retrieval_trace={"selected_sources": []},
    )

    assert report["status"] == "pass"
    assert report["claims"][0]["citations"][0]["label"] == "supports"
    assert report["live_llm_judging_enabled"] is False


def test_checker_reports_residual_risk_and_false_pass_limits() -> None:
    case = next(
        item for item in _cases() if item["case_id"] == "supports_public_legal_claim"
    )

    report = build_citation_faithfulness_report(
        claims=[case["claim"]],
        evidence=case["evidence"],
    )

    assert report["residual_risk"]["level"] == "medium"
    assert report["residual_risk"]["deterministic_only"] is True
    assert report["false_pass_limits"]
    assert "semantic_paraphrase_not_proven" in report["false_pass_limits"]
    assert "metadata_omission_can_hide_scope_mismatch" in report["false_pass_limits"]
