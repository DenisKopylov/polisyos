from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.scorecard import (
    build_quality_scorecard,
    normalize_quality_evidence,
)
from polisyos.core.security.quality_gates import (
    SECURITY_ASSURANCE_REPORT_REF_KEY,
    SECURITY_REPORT_FILE,
    build_security_assurance_report,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "policyos_abuse_cases"


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    ]


def _complete_job_payload() -> dict[str, Any]:
    return {
        "job_id": "job-security",
        "run_id": "R_security",
        "state": "completed",
        "progress": {
            "details": {
                "data_snapshot_ref": _sha("1"),
                "input_bindings_ref": _sha("2"),
                "registry_bundle_ref": _sha("3"),
                "quality_report_ref": _sha("4"),
                "normative_applicability_report_ref": _sha("5"),
                "fabric_retrieval_trace_ref": _sha("6"),
                "foundry_method_report_ref": _sha("7"),
                "policy_grounding_matrix_ref": _sha("8"),
                "conflict_check_ref": _sha("9"),
                SECURITY_ASSURANCE_REPORT_REF_KEY: f"quality_evidence/{SECURITY_REPORT_FILE}",
                "llm_model_variants": [
                    {
                        "model_variant_id": "qwen_1",
                        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                        "provider": "gateway",
                        "status": "completed",
                        "schema_healing_count": 0,
                        "prompt_tokens": 120,
                        "completion_tokens": 32,
                        "total_tokens": 152,
                    }
                ],
                "run_performance_summary": {"status": "pass"},
            }
        },
    }


def _complete_quality_evidence() -> dict[str, Any]:
    return {
        "golden_scenario_contract": {
            "expected_evidence_contract": {
                "admissible_data_source_families": ["production_msme_panel"],
                "foundry_method_expectations": ["causal_effect_estimation"],
            }
        },
        "normative_evidence": {
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "policy_domain": "wartime_msme_support",
                    "effective_from": "2024-01-01",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                }
            ],
            "recommendation_claims": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        "fabric_retrieval_trace": {
            "query_intent": {
                "policy_domain": "wartime_msme_support",
                "query_outcome": "msme_survival_rate",
                "query_treatment": "wartime_credit_support",
            },
            "candidate_sources": [
                {
                    "source_id": "production-msme-panel",
                    "source_family": "production_msme_panel",
                    "source_kind": "production_data",
                    "freshness": {"status": "pass"},
                    "coverage": {"status": "pass"},
                    "schema_compatibility": {"status": "pass"},
                    "relevance_rationale": "Matches requested outcome and treatment.",
                }
            ],
            "selected_source_ids": ["production-msme-panel"],
        },
        "foundry_method_report": {
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "method_family": "causal_effect_estimation",
                    "input_refs": {
                        "data_snapshot_ref": _sha("1"),
                        "input_bindings_ref": _sha("2"),
                    },
                    "assumptions": ["parallel_trends"],
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {"sample_size": 240, "min_required_sample_size": 30},
                    "result_summary": {"effect_estimate": 0.04},
                }
            ],
        },
        "policy_grounding_matrix": {
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        "conflict_check": {"claims": [], "corpus_constraints": []},
    }


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
def test_security_abuse_fixtures_fail_closed_with_operator_envelopes(
    case: dict[str, Any],
) -> None:
    report = build_security_assurance_report(
        payloads={case["surface"]: case["payload"]},
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    issues = {issue["code"]: issue for issue in report["issues"]}
    assert report["status"] == "fail"
    assert case["expected_code"] in issues

    issue = issues[case["expected_code"]]
    assert issue["layer"] == "security"
    assert issue["retryable"] is False
    assert issue["retryability"] == "not_retryable"
    assert issue["evidence_ref"].startswith(
        f"quality_evidence/{SECURITY_REPORT_FILE}#/issues/"
    )
    assert issue["next_action"]

    rendered = json.dumps(report, sort_keys=True)
    for literal in case.get("forbidden_literals", []):
        assert literal not in rendered


def test_security_report_passes_clean_llm_tool_data_artifact_api_dashboard_paths() -> None:
    report = build_security_assurance_report(
        payloads={
            "llm": {"prompt": "Summarize the verified policy evidence."},
            "tool": {"name": "source_quality", "arguments": {"source_id": "ua-stat"}},
            "data": {"source_text": "Official budget bulletin for MSME support."},
            "artifact": {"rendered_content": "Decision packet status: APPROVE."},
            "runtime_api": {"url": "https://api.policyos.example/runs/R_1"},
            "dashboard": {"route": "/runs/R_1/overview", "status": "rendered"},
        },
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert {item["path"] for item in report["assured_paths"]} == {
        "llm",
        "tool",
        "data",
        "artifact",
        "runtime_api",
        "dashboard",
    }


def test_security_report_blocks_scorecard_approval_with_security_layer_gate() -> None:
    report = build_security_assurance_report(
        payloads={
            "artifact": {
                "rendered_content": "<script>window.__POLICYOS_XSS__=true</script>"
            }
        },
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )
    quality_evidence = normalize_quality_evidence(
        {**_complete_quality_evidence(), "security_assurance_report": report},
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-security",
        run_id="R_security",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    security_gates = [
        gate for gate in scorecard["quality_gates"] if gate["layer"] == "security"
    ]
    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert scorecard["evidence_refs"]["security_assurance_report"] == (
        f"quality_evidence/{SECURITY_REPORT_FILE}"
    )
    assert scorecard["evidence_refs"][SECURITY_ASSURANCE_REPORT_REF_KEY] == (
        f"quality_evidence/{SECURITY_REPORT_FILE}"
    )
    assert security_gates[0]["code"] == "unsafe_artifact_rendering_detected"
    assert security_gates[0]["retryable"] is False
    assert security_gates[0]["retryability"] == "not_retryable"
    assert security_gates[0]["evidence_ref"].startswith(
        f"quality_evidence/{SECURITY_REPORT_FILE}#/issues/"
    )
    assert security_gates[0]["next_action"]
    assert any(
        failure["layer"] == "security"
        and failure["code"] == "unsafe_artifact_rendering_detected"
        and failure["retryability"] == "not_retryable"
        for failure in scorecard["blocking_quality_failures"]
    )
