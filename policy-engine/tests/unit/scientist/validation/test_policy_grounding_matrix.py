from __future__ import annotations

from polisyos.foundry.validation.causal_validity import (
    build_causal_statistical_validity_report,
)
from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.runtime.quality.ir_analytics_bridge import (
    build_ir_analytics_claim_bridge,
)
from polisyos.scientist.validation.policy_grounding import (
    build_policy_grounding_matrix_report,
    normalize_policy_grounding_matrix,
)


def _evidence_context() -> dict[str, dict[str, object]]:
    return {
        "normative_evidence": {
            "status": "pass",
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "artifact_id": "sha256:" + "1" * 64,
                }
            ],
        },
        "fabric_retrieval_trace": {
            "status": "pass",
            "selected_sources": [
                {
                    "source_id": "production-msme-panel",
                    "source_family": "production_msme_panel",
                }
            ],
        },
        "foundry_method_report": {
            "status": "pass",
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "result_summary": {"effect_estimate": 0.04},
                }
            ],
        },
    }


def _complete_evidence_graph_refs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "portfolio_refs": ["portfolio-rec-1"],
        "independence_refs": ["independence-rec-1"],
        "synthesis_refs": ["synthesis-rec-1"],
        "argument_refs": ["argument-rec-1"],
        "warrant_refs": ["warrant-rec-1"],
        "rebuttal_refs": ["rebuttal-rec-1"],
        "accepted_deficit_refs": ["accepted-deficit-rec-1"],
    }
    payload.update(overrides)
    return payload


def test_policy_grounding_matrix_passes_when_claims_match_evidence() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(),
            },
            {
                "claim_id": "num_1",
                "claim_type": "numerical",
                "major": False,
                "text": "The estimated effect is 0.04.",
                "metric": "effect_estimate",
                "value": 0.0404,
                "tolerance": 0.001,
                "method_refs": ["causal.difference_in_differences"],
            },
        ],
        **context,
    )

    assert report["status"] == "pass"
    assert report["blocking_issue_count"] == 0
    assert report["claims"][0]["claim_family"] == "recommendation"
    assert report["claims"][0]["major"] is True


def test_policy_grounding_matrix_rejects_global_evidence_without_claim_registry_entry() -> None:
    context = _evidence_context()
    context["foundry_method_report"] = {
        "status": "pass",
        "selected_methods": [{"method_id": "foundry.execute"}],
    }

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_credit_guarantee",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target capped credit guarantees to liquidity-constrained MSMEs.",
            }
        ],
        claim_registry={
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [],
        },
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "runtime_claim_registry_entry_missing" in issue_codes
    assert report["runtime_claim_registry"]["summary"]["global_norm_ref_count"] == 1
    assert (
        report["runtime_claim_registry"]["summary"]["generic_global_method_ref_count"]
        == 1
    )


def test_policy_grounding_matrix_uses_claim_registry_as_claim_bound_surface() -> None:
    context = _evidence_context()
    registry = build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "scenario_requirement_refs": ["scenario.req.msme_credit"],
                "data_refs": ["production-msme-panel"],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "rejected_norm_refs": ["norm.ua.unrelated"],
                "method_output_refs": ["causal.difference_in_differences"],
                **_complete_evidence_graph_refs(
                    counter_evidence_refs=["counter-rec-1"],
                    limitation_refs=["limitation-rec-1"],
                    accepted_deficit_refs=["accepted-deficit-rec-1"],
                ),
            }
        ]
    )

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
            }
        ],
        claim_registry=registry,
        **context,
    )

    assert report["status"] == "pass"
    assert report["runtime_claim_registry"]["status"] == "pass"
    assert report["claims"][0]["grounding"]["data_refs"] == ["production-msme-panel"]
    assert report["claims"][0]["grounding"]["norm_refs"] == [
        "norm.ua.credit_eligibility"
    ]
    assert report["claims"][0]["grounding"]["method_refs"] == [
        "causal.difference_in_differences"
    ]


def test_policy_grounding_matrix_consumes_ir_analytics_bridge_refs() -> None:
    context = _evidence_context()
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": "impact_1",
                "analytics_ref": "ir.analytics.partial_id.msme_survival",
                "method_output_refs": ["ir.method.partial_identification.ate"],
                "certificate_refs": ["ir.certificate.dual.msme_survival"],
                "proof_status": "identified",
                "proof_composability_status": "reusable",
                "proof_composability_refs": ["ir.proof_composability.msme_survival"],
                "uncertainty_refs": ["ir.uncertainty.msme_survival"],
                "baseline_refs": ["baseline.status_quo.msme_survival"],
            }
        ],
        run_id="run-w3a-ir",
    )
    registry = build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "impact_1",
                "claim_type": "causal",
                "major": True,
                "text": "The guarantee improves MSME survival versus status quo.",
                "requires_ir_analytics": True,
                "scenario_requirement_refs": ["scenario.req.msme_survival"],
                "data_refs": ["production-msme-panel"],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "portfolio_refs": ["portfolio-impact-1"],
                "independence_refs": ["independence-impact-1"],
                "synthesis_refs": ["synthesis-impact-1"],
                "argument_refs": ["argument-impact-1"],
                "warrant_refs": ["warrant-impact-1"],
                "rebuttal_refs": ["rebuttal-impact-1"],
                "counter_evidence_refs": ["counter-impact-1"],
                "limitation_refs": ["limitation-impact-1"],
                "accepted_deficit_refs": ["accepted-deficit-impact-1"],
                "identification_strategy": "partial_identification",
            }
        ],
        ir_analytics_bridge=bridge,
        run_id="run-w3a-ir",
    )

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "impact_1",
                "claim_type": "causal",
                "major": True,
                "text": "The guarantee improves MSME survival versus status quo.",
                "requires_ir_analytics": True,
                "identification_strategy": "partial_identification",
            }
        ],
        claim_registry=registry,
        ir_analytics_bridge=bridge,
        enforce_claim_support_semantics=True,
        **context,
    )

    assert report["status"] == "pass"
    assert report["runtime_claim_registry"]["summary"]["ir_analytics_binding_count"] == 1
    assert report["claims"][0]["grounding"]["method_refs"] == [
        "ir.method.partial_identification.ate"
    ]
    assert report["claims"][0]["evidence_graph"]["proof_composability_refs"] == [
        "ir.proof_composability.msme_survival"
    ]


def test_policy_grounding_matrix_fails_ir_required_claim_without_bridge() -> None:
    context = _evidence_context()
    registry = build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "impact_1",
                "claim_type": "causal",
                "major": True,
                "text": "The guarantee improves MSME survival versus status quo.",
                "requires_ir_analytics": True,
                "scenario_requirement_refs": ["scenario.req.msme_survival"],
                "data_refs": ["production-msme-panel"],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "method_output_refs": ["ir.method.partial_identification.ate"],
                "portfolio_refs": ["portfolio-impact-1"],
                "argument_refs": ["argument-impact-1"],
                "warrant_refs": ["warrant-impact-1"],
                "rebuttal_refs": ["rebuttal-impact-1"],
                "counter_evidence_refs": ["counter-impact-1"],
                "limitation_refs": ["limitation-impact-1"],
                "accepted_deficit_refs": ["accepted-deficit-impact-1"],
                "identification_strategy": "partial_identification",
            }
        ],
        run_id="run-w3a-ir",
    )

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "impact_1",
                "claim_type": "causal",
                "major": True,
                "text": "The guarantee improves MSME survival versus status quo.",
                "requires_ir_analytics": True,
                "identification_strategy": "partial_identification",
            }
        ],
        claim_registry=registry,
        enforce_claim_support_semantics=True,
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "runtime_claim_registry_ir_analytics_bridge_missing" in issue_codes


def test_policy_grounding_matrix_fails_major_recommendation_missing_evidence_graph_refs() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_missing_graph",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert {
        "major_claim_portfolio_refs_missing",
        "major_claim_independence_refs_missing",
        "major_claim_synthesis_refs_missing",
        "major_claim_argument_refs_missing",
        "major_claim_warrant_refs_missing",
        "major_claim_rebuttal_or_counter_evidence_refs_missing",
        "major_claim_limitation_or_deficit_refs_missing",
    } <= issue_codes
    assert report["claims"][0]["evidence_graph"]["portfolio_refs"] == []


def test_policy_grounding_matrix_prioritizes_model_disagreement_over_graph_gaps() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_selected",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        model_variants=[
            {
                "model_variant_id": "qwen",
                "claims": [
                    {
                        "claim_id": "rec_qwen",
                        "claim_type": "recommendation",
                        "major": True,
                        "policy_action": "targeted_credit_guarantee",
                    }
                ],
            },
            {
                "model_variant_id": "kimi",
                "claims": [
                    {
                        "claim_id": "rec_kimi",
                        "claim_type": "recommendation",
                        "major": True,
                        "policy_action": "blanket_uncapped_credit_support",
                    }
                ],
            },
        ],
        **context,
    )

    issue_codes = [issue["code"] for issue in report["issues"]]
    assert report["status"] == "fail"
    assert issue_codes[0] == "multi_model_policy_disagreement"
    assert "major_claim_portfolio_refs_missing" in issue_codes


def test_policy_grounding_matrix_passes_complete_graph_with_data_quality_limitation() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(
                    accepted_deficit_refs=["data-quality:recency:production-msme-panel"],
                    limitation_refs=["data-quality:recency:production-msme-panel"],
                ),
            }
        ],
        production_data_quality_report={
            "status": "warn",
            "findings": [
                {
                    "code": "production_data_recency_missing",
                    "severity": "warn",
                    "candidate_ref": "production-msme-panel",
                    "claim_ids": ["rec_1"],
                    "evidence_ref": "data-quality:recency:production-msme-panel",
                    "message": "Source has no machine-readable freshness timestamp.",
                }
            ],
        },
        **context,
    )

    graph = report["claims"][0]["evidence_graph"]
    assert report["status"] == "pass"
    assert graph["limitation_refs"] == ["data-quality:recency:production-msme-panel"]
    assert graph["data_quality_limitations"][0]["code"] == "production_data_recency_missing"


def test_policy_grounding_matrix_fails_unsupported_major_recommendation() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_unsupported",
                "claim_type": "recommendation",
                "major": True,
                "text": "Launch a blanket uncapped credit subsidy immediately.",
                "data_refs": [],
                "method_refs": [],
                "norm_refs": [],
            }
        ],
        **context,
    )

    issue = report["issues"][0]
    assert report["status"] == "fail"
    assert issue["code"] == "major_claim_missing_grounding"
    assert issue["claim_text"] == "Launch a blanket uncapped credit subsidy immediately."
    assert issue["missing_evidence_type"] == "data_or_method_or_norm"
    assert issue["next_action"]


def test_policy_grounding_matrix_accepts_claim_family_aliases() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_alias",
                "claim_family": "policy_recommendation",
                "major": "major",
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(),
            }
        ],
        **context,
    )

    assert report["status"] == "pass"
    assert report["claims"][0]["claim_family"] == "recommendation"
    assert report["claims"][0]["claim_type"] == "recommendation"
    assert report["claims"][0]["major"] is True


def test_policy_grounding_matrix_fails_numerical_claim_mismatch() -> None:
    context = _evidence_context()
    context["foundry_method_report"]["selected_methods"][0]["output_ref"] = (
        "sha256:" + "2" * 64
    )
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "num_bad",
                "claim_type": "numerical",
                "text": "The estimated effect is 0.10.",
                "metric": "effect_estimate",
                "value": 0.10,
                "tolerance": 0.001,
                "method_refs": ["causal.difference_in_differences"],
            }
        ],
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    mismatch = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "numeric_claim_mismatch"
    )
    assert report["status"] == "fail"
    assert "numeric_claim_mismatch" in issue_codes
    assert mismatch["metric"] == "effect_estimate"
    assert mismatch["expected"] == 0.04
    assert mismatch["observed"] == 0.10
    assert mismatch["evidence_ref"] == "sha256:" + "2" * 64


def test_policy_grounding_matrix_enforces_support_by_claim_family() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "empirical_missing_data",
                "claim_type": "empirical",
                "major": True,
                "text": "MSME credit demand increased after the programme started.",
            },
            {
                "claim_id": "causal_missing_method",
                "claim_type": "causal",
                "major": True,
                "text": "The programme caused improved firm survival.",
                "data_refs": ["production-msme-panel"],
            },
        ],
        **context,
    )

    issues_by_claim = {
        issue["claim_id"]: issue
        for issue in report["issues"]
        if issue.get("code") == "claim_family_missing_required_grounding"
    }
    assert report["status"] == "fail"
    assert issues_by_claim["empirical_missing_data"]["missing_evidence_type"] == "data"
    assert issues_by_claim["causal_missing_method"]["missing_evidence_type"] == "method"


def test_policy_grounding_matrix_can_enforce_claim_support_semantics() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "empirical_missing_source_attribution",
                "claim_family": "empirical",
                "major": True,
                "text": "MSME credit demand increased after the programme started.",
                "data_refs": ["production-msme-panel"],
            }
        ],
        enforce_claim_support_semantics=True,
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "claim_support_missing_required_predicates" in issue_codes
    assert report["claims"][0]["claim_support"]["publishability"] == "review_required"


def test_policy_grounding_matrix_folds_citation_faithfulness_failures() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "legal_bad_cite",
                "claim_family": "normative",
                "major": True,
                "text": "The rule authorizes the credit support.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        citation_faithfulness_report={
            "schema_version": "policyos.scientist.citation_faithfulness.v1",
            "status": "fail",
            "issues": [
                {
                    "code": "public_claim_has_unfaithful_citation",
                    "severity": "fail",
                    "claim_id": "legal_bad_cite",
                    "citation_ref": "norm.ua.credit_eligibility",
                    "message": "Citation contradicted the legal claim.",
                    "next_action": "Replace the citation.",
                }
            ],
        },
        **context,
    )

    folded = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "public_claim_has_unfaithful_citation"
    )
    assert report["status"] == "fail"
    assert folded["phase"] == "citation_faithfulness"
    assert report["citation_faithfulness"]["status"] == "fail"


def test_policy_grounding_matrix_folds_source_quality_failures() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_family": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        source_quality_report={
            "schema_version": "policyos.scientist.source_quality_report.v1",
            "status": "fail",
            "issues": [
                {
                    "code": "source_quality_not_publishable",
                    "severity": "fail",
                    "source_id": "norm.ua.credit_eligibility",
                    "message": "Withdrawn primary source cannot be published.",
                    "next_action": "Replace the withdrawn source.",
                }
            ],
        },
        **context,
    )

    folded = next(
        issue for issue in report["issues"] if issue["code"] == "source_quality_not_publishable"
    )
    assert report["status"] == "fail"
    assert folded["phase"] == "source_quality"
    assert report["source_quality"]["status"] == "fail"


def test_policy_grounding_matrix_fails_normative_claim_not_in_applicable_set() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "norm_bad",
                "claim_type": "normative",
                "major": True,
                "text": "This is authorized by an unrelated norm.",
                "norm_refs": ["norm.ua.unrelated"],
            }
        ],
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "normative_claim_refs_not_applicable" in issue_codes


def test_policy_grounding_matrix_allows_documented_no_grounding_rationale() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "operational_note",
                "claim_type": "recommendation",
                "major": True,
                "text": "Publish a monitoring dashboard for implementation status.",
                "no_grounding_rationale": (
                    "Operational transparency step; no new empirical or legal claim."
                ),
            }
        ],
        **context,
    )

    assert report["status"] == "pass"


def test_policy_grounding_matrix_warns_for_minor_ungrounded_without_rationale() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "supported_major",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(),
            },
            {
                "claim_id": "minor_note",
                "claim_type": "implementation",
                "major": False,
                "text": "Publish monitoring updates during rollout.",
            },
        ],
        **context,
    )

    issue = report["issues"][0]
    assert report["status"] == "warn"
    assert issue["code"] == "minor_claim_missing_grounding_rationale"
    assert issue["severity"] == "warn"
    assert issue["claim_id"] == "minor_note"


def test_policy_grounding_matrix_minor_rationale_does_not_hide_major_unsupported() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "major_unsupported",
                "claim_type": "recommendation",
                "major": True,
                "text": "Launch a blanket uncapped credit subsidy immediately.",
            },
            {
                "claim_id": "minor_note",
                "claim_type": "implementation",
                "major": False,
                "text": "Publish monitoring updates during rollout.",
                "no_grounding_rationale": "Implementation note; no new empirical claim.",
            },
        ],
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "major_claim_missing_grounding" in issue_codes
    assert report["blocking_issue_count"] == 1


def test_policy_grounding_matrix_requires_machine_readable_major_claims() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "minor_caveat",
                "claim_family": "caveat",
                "major": False,
                "text": "The evidence base should be revisited after implementation.",
                "no_grounding_rationale": "Minor caveat; no new empirical claim.",
            }
        ],
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "no_major_policy_claims" in issue_codes


def test_policy_grounding_matrix_fails_claim_extraction_failure_without_review() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_family": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(),
            }
        ],
        claim_extraction_report={
            "extraction_status": "fail",
            "issues": [{"code": "policy_claim_extraction_failed"}],
        },
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "policy_claim_extraction_failed" in issue_codes


def test_policy_grounding_matrix_warns_when_claim_extraction_requires_review() -> None:
    context = _evidence_context()
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_1",
                "claim_family": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                **_complete_evidence_graph_refs(),
            }
        ],
        claim_extraction_report={
            "extraction_status": "review_required",
            "human_review_required": True,
            "issues": [{"code": "policy_claim_extraction_ambiguous"}],
        },
        **context,
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "warn"
    assert "policy_claim_extraction_requires_review" in issue_codes


def test_normalize_matrix_refuses_raw_pass_for_unsupported_claim() -> None:
    context = _evidence_context()
    normalized = normalize_policy_grounding_matrix(
        {
            "status": "pass",
            "claims": [
                {
                    "claim_id": "rec_unsupported",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Launch a blanket uncapped credit subsidy immediately.",
                }
            ],
        },
        **context,
    )

    issue_codes = {issue["code"] for issue in normalized["issues"]}
    assert normalized["status"] == "fail"
    assert "major_claim_missing_grounding" in issue_codes


def test_policy_grounding_matrix_blocks_major_causal_claim_on_power_failure() -> None:
    context = _evidence_context()
    bad_case = {
        "case_id": "did_underpowered_policy_claim",
        "method_family": "difference_in_differences",
        "scenario": "known_answer",
        "estimand": "ATT",
        "expected_effect": 0.04,
        "observed_effect": 0.041,
        "tolerance": 0.003,
        "uncertainty": {
            "type": "cluster_bootstrap_ci",
            "level": 0.95,
            "interval": [0.033, 0.049],
        },
        "sample_diagnostics": {
            "sample_size": 88,
            "min_required_sample_size": 240,
            "effective_sample_size": 71,
            "power": 0.42,
            "min_power": 0.8,
        },
        "assumption_checks": {
            "parallel_trends": "pass",
            "stable_composition": "pass",
            "no_anticipation": "pass",
        },
        "sensitivity": {"status": "pass"},
        "missingness": {"status": "pass", "missing_rate": 0.03, "max_missing_rate": 0.1},
        "uncertainty_calibration": {
            "status": "pass",
            "coverage": 0.94,
            "target_coverage": 0.95,
            "tolerance": 0.03,
        },
    }
    causal_validity_report = build_causal_statistical_validity_report(
        benchmark_cases=[bad_case]
    )

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "causal_major",
                "claim_family": "causal",
                "major": True,
                "text": "The credit programme caused improved MSME survival.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
            }
        ],
        causal_statistical_validity_report=causal_validity_report,
        **context,
    )

    folded = next(
        issue
        for issue in report["issues"]
        if issue["phase"] == "causal_statistical_validity"
        and issue["code"] == "power_failure"
    )
    assert report["status"] == "fail"
    assert folded["severity"] == "fail"
    assert folded["claim_ids"] == ["causal_major"]
    assert report["causal_statistical_validity"]["status"] == "fail"


def test_policy_grounding_matrix_blocks_major_numerical_claim_on_sensitivity_failure() -> None:
    context = _evidence_context()
    bad_case = {
        "case_id": "did_sensitivity_policy_claim",
        "method_family": "difference_in_differences",
        "scenario": "known_answer",
        "estimand": "ATT",
        "expected_effect": 0.04,
        "observed_effect": 0.041,
        "tolerance": 0.003,
        "uncertainty": {
            "type": "cluster_bootstrap_ci",
            "level": 0.95,
            "interval": [0.033, 0.049],
        },
        "sample_diagnostics": {
            "sample_size": 480,
            "min_required_sample_size": 240,
            "effective_sample_size": 420,
            "power": 0.84,
            "min_power": 0.8,
        },
        "assumption_checks": {
            "parallel_trends": "pass",
            "stable_composition": "pass",
            "no_anticipation": "pass",
        },
        "sensitivity": {"status": "fail", "reason": "robustness_floor_not_met"},
        "missingness": {"status": "pass", "missing_rate": 0.03, "max_missing_rate": 0.1},
        "uncertainty_calibration": {
            "status": "pass",
            "coverage": 0.94,
            "target_coverage": 0.95,
            "tolerance": 0.03,
        },
    }
    causal_validity_report = build_causal_statistical_validity_report(
        benchmark_cases=[bad_case]
    )

    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "num_major",
                "claim_family": "numerical",
                "major": True,
                "text": "The estimated effect is 0.04.",
                "metric": "effect_estimate",
                "value": 0.04,
                "tolerance": 0.001,
                "method_refs": ["causal.difference_in_differences"],
            }
        ],
        causal_statistical_validity_report=causal_validity_report,
        **context,
    )

    folded = next(
        issue
        for issue in report["issues"]
        if issue["phase"] == "causal_statistical_validity"
        and issue["code"] == "sensitivity_failure"
    )
    assert report["status"] == "fail"
    assert folded["claim_ids"] == ["num_major"]
