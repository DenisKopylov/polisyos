from __future__ import annotations

from polisyos.scientist.artifacts.decision_compiler import (
    DecisionArtifactCompilationError,
    compile_publishable_decision_artifact,
)
from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.scientist.validation.decision_artifact_quality import (
    build_decision_artifact_quality_report,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _complete_major_recommendation(**overrides: object) -> dict[str, object]:
    return {
        "claim_id": "rec_credit_guarantee",
        "claim_family": "recommendation",
        "major": True,
        "text": "Target capped credit guarantees to liquidity-constrained MSMEs.",
        "citation_refs": ["source.msme_panel", "norm.ua.credit_guarantee"],
        "data_refs": ["source.msme_panel"],
        "method_refs": ["foundry.did.msme_survival"],
        "norm_refs": ["norm.ua.credit_guarantee"],
        "portfolio_refs": ["portfolio.rec_credit_guarantee"],
        "independence_refs": ["independence.rec_credit_guarantee"],
        "synthesis_refs": ["synthesis.rec_credit_guarantee"],
        "argument_refs": ["argument.rec_credit_guarantee"],
        "warrant_refs": ["warrant.rec_credit_guarantee"],
        "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
        "accepted_deficit_refs": ["data-quality.recency.msme_panel"],
        "limitation_refs": ["data-quality.recency.msme_panel"],
        "support_summary": "Supported by selected panel data, legal norms, and method output.",
        "uncertainty": "Estimated effects remain uncertain and depend on uptake.",
        "policy_tradeoffs": "Improves access to finance while increasing fiscal exposure.",
        "distributional_impact": "Track women-owned and rural MSME outcomes separately.",
        "implementation_feasibility": "Can use existing participating-bank reporting rails.",
        "budget_implication": "Requires a capped guarantee envelope and loss reserve.",
        "stakeholder_impact": "Affects MSMEs, banks, fiscal authority, and auditors.",
        "implementation_risks": (
            "Bank capacity, adverse selection, and fraud controls remain risks."
        ),
        "residual_uncertainty": "Demand elasticity and repayment shocks remain uncertain.",
        "monitoring_plan": "Monitor uptake, defaults, complaints, and subgroup outcomes monthly.",
        "withdrawal_reissue_triggers": (
            "Withdraw or reissue if default rates exceed the cap or legal scope changes."
        ),
        "section_evidence_refs": {
            "budget_implication": [_sha("b")],
            "distributional_impact": [_sha("d")],
            "implementation_feasibility": [_sha("f")],
            "implementation_risks": [_sha("r")],
            "monitoring_plan": [_sha("m")],
            "policy_tradeoffs": [_sha("t")],
            "residual_uncertainty": [
                _sha("u"),
                "data-quality.recency.msme_panel",
            ],
            "withdrawal_reissue_triggers": [_sha("w")],
        },
        "limitations": [
            {
                "code": "production_data_recency_missing",
                "evidence_ref": "data-quality.recency.msme_panel",
                "source": "production_data_quality_report",
            }
        ],
        **overrides,
    }


def _claim_registry(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "policyos.runtime.policy_design_case.claim_registry.v1",
        "claims": [
            {
                "claim_id": "rec_credit_guarantee",
                "assurance_node_id": "claim-node-rec-credit-guarantee",
                "claim_ref": _sha("a"),
                "runtime_event_ref": "event://policy_design_case/claim/rec_credit_guarantee",
                "concept_refs": ["concept.msme_credit_guarantee"],
                "legal_norm_refs": ["norm.ua.credit_guarantee"],
                "source_data_refs": ["source.msme_panel", "data_forge.snapshot.msme"],
                "scholar_refs": ["scholar.msme_survival_review"],
                "method_refs": ["foundry.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                "independence_refs": ["independence.rec_credit_guarantee"],
                "specification_curve_refs": ["spec_curve.rec_credit_guarantee"],
                "disconfirming_refs": ["disconfirming.rec_credit_guarantee"],
                "synthesis_refs": ["synthesis.rec_credit_guarantee"],
                "objective_tradeoff_refs": ["objective_tradeoff.rec_credit_guarantee"],
                "uncertainty_refs": ["uncertainty.rec_credit_guarantee"],
                "numerical_semantics_refs": ["num_semantics.rec_credit_guarantee"],
                "monitoring_refs": ["monitoring.rec_credit_guarantee"],
                "selected_producer_refs": {
                    "lex": ["norm.ua.credit_guarantee"],
                    "fabric": ["source.msme_panel"],
                    "data_forge": ["data_forge.snapshot.msme"],
                    "scholar": ["scholar.msme_survival_review"],
                    "foundry": [
                        "foundry.did.msme_survival",
                        "uncertainty.rec_credit_guarantee",
                    ],
                    "options_objectives": ["objective_tradeoff.rec_credit_guarantee"],
                },
            }
        ],
    }
    payload.update(overrides)
    return payload


def _runtime_authority() -> dict[str, object]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": _sha("a"),
        "runtime_event_ref": "event://policy_design_case/claim/rec_credit_guarantee",
    }


def _complete_artifact(
    recommendation: dict[str, object] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    final_claims = [recommendation or _complete_major_recommendation()]
    try:
        artifact = compile_publishable_decision_artifact(
            run_id="run-quality-001",
            final_claims=final_claims,
            policy_grounding_matrix={
                "status": "pass",
                "policy_grounding_matrix_ref": _sha("1"),
            },
            quality_scorecard={
                "quality_status": "pass",
                "approval_state": "approval_ready",
                "quality_scorecard_ref": _sha("2"),
                "evidence_refs": {
                    "claim_support_report": _sha("3"),
                    "citation_faithfulness_report": _sha("4"),
                },
            },
            conflict_check={"status": "pass", "conflict_check_ref": _sha("5")},
            approval_state="approval_ready",
            assurance_refs={"privacy_compliance_report_ref": _sha("6")},
            claim_registry=_claim_registry(),
            runtime_authority=_runtime_authority(),
        )
    except DecisionArtifactCompilationError as exc:
        artifact = dict(exc.draft_artifact)
    return artifact, final_claims


def test_quality_report_passes_complete_serious_decision_artifact() -> None:
    artifact, final_claims = _complete_artifact()

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        policy_grounding_matrix_ref="sha256:" + "1" * 64,
        quality_scorecard_ref="sha256:" + "2" * 64,
        profile="production",
    )
    repeated = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        policy_grounding_matrix_ref="sha256:" + "1" * 64,
        quality_scorecard_ref="sha256:" + "2" * 64,
        profile="production",
    )

    assert report["status"] == "pass"
    assert report["blocking_issue_count"] == 0
    assert report["decision_artifact_quality_report_ref"].startswith("sha256:")
    assert report["decision_artifact_quality_report_ref"] == (
        repeated["decision_artifact_quality_report_ref"]
    )
    assert report["parallel_evaluation"]["uses_compiled_output"] is True
    assert "policy_grounding_matrix_ref" in report["input_refs"]
    assert "quality_scorecard_ref" in report["input_refs"]
    assert report["claim_evidence_contract"]["status"] == "pass"


def test_quality_report_fails_without_runtime_claim_registry_entry() -> None:
    artifact, final_claims = _complete_artifact()

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        claim_registry={
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [],
        },
        profile="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "runtime_claim_registry_entry_missing" in issue_codes


def test_quality_report_accepts_runtime_claim_registry_projection() -> None:
    recommendation = _complete_major_recommendation(
        scenario_requirement_refs=["scenario.req.credit_support"],
        selected_norm_refs=["norm.ua.credit_guarantee"],
        rejected_norm_refs=["norm.ua.unrelated"],
        method_output_refs=["foundry.did.msme_survival"],
        counter_evidence_refs=["counter.rec_credit_guarantee"],
        scholar_deficit_refs=["scholar-deficit.msme_credit"],
        objective_tradeoff_refs=["objective_tradeoff.rec_credit_guarantee"],
        uncertainty_refs=["uncertainty.rec_credit_guarantee"],
        numerical_semantics_refs=["num_semantics.rec_credit_guarantee"],
        monitoring_refs=["monitoring.rec_credit_guarantee"],
        specification_curve_refs=["spec_curve.rec_credit_guarantee"],
        claim_ref=_sha("a"),
        runtime_event_ref="event://runtime_claim_registry/rec_credit_guarantee",
    )
    registry = build_runtime_claim_registry(
        claims=[recommendation],
        run_id="run-quality-001",
    )
    artifact, final_claims = _complete_artifact(recommendation)

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        claim_registry=registry,
        profile="production",
    )

    assert report["status"] == "pass"
    assert report["runtime_claim_registry"]["status"] == "pass"
    assert report["summary"]["runtime_claim_registry_entry_count"] == 1


def test_quality_report_fails_when_public_ready_contract_is_missing() -> None:
    artifact, final_claims = _complete_artifact()
    artifact.pop("claim_evidence_contract")

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "decision_artifact_claim_evidence_contract_missing" in issue_codes


def test_quality_report_fails_when_public_sections_are_not_bound_to_evidence() -> None:
    artifact, final_claims = _complete_artifact()
    contract = artifact["claim_evidence_contract"]
    assert isinstance(contract, dict)
    contract["statements"] = [
        statement
        for statement in contract["statements"]
        if statement["statement_scope"] != "implementation_feasibility"
    ]

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="production",
    )

    section_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "decision_artifact_public_section_unbound"
    )
    assert report["status"] == "fail"
    assert section_issue["public_section"] == "implementation_feasibility"
    assert section_issue["claim_id"] == "rec_credit_guarantee"


def test_serious_profile_fails_when_major_recommendation_sections_are_missing() -> None:
    artifact, final_claims = _complete_artifact(
        _complete_major_recommendation(
            budget_implication="",
            stakeholder_impact="",
            monitoring_plan="",
        )
    )

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="governed",
    )

    missing = [
        issue
        for issue in report["issues"]
        if issue["code"] == "major_recommendation_missing_required_section"
    ]
    assert report["status"] == "fail"
    assert {issue["section"] for issue in missing} == {
        "budget_implication",
        "stakeholder_impact",
        "monitoring_plan",
    }


def test_quality_report_fails_overstated_certainty_and_public_secrets() -> None:
    artifact, final_claims = _complete_artifact(
        _complete_major_recommendation(
            text=(
                "The benchmark proves this model will definitely cause a fully "
                "compliant outcome."
            ),
            uncertainty="No uncertainty.",
        )
    )
    artifact["hidden_benchmark_answer"] = "gold answer"
    artifact["decision_context"]["credentials"] = {"api_key": "secret-key"}

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "overstated_causal_certainty" in issue_codes
    assert "overstated_model_certainty" in issue_codes
    assert "overstated_benchmark_certainty" in issue_codes
    assert "overstated_compliance_certainty" in issue_codes
    assert "public_export_contains_forbidden_data" in issue_codes


def test_quality_report_fails_when_public_artifact_drops_citations() -> None:
    artifact, final_claims = _complete_artifact()
    artifact["recommendations"][0]["citation_refs"] = []

    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="production",
    )

    issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "citation_refs_dropped"
    )
    assert report["status"] == "fail"
    assert issue["claim_id"] == "rec_credit_guarantee"
