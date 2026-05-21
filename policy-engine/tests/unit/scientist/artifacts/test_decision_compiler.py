from __future__ import annotations

# ruff: noqa: S101
import json

import pytest

from polisyos.scientist.artifacts.decision_compiler import (
    DecisionArtifactCompilationError,
    compile_draft_decision_packet,
    compile_public_decision_artifact,
    compile_publishable_decision_artifact,
)
from tests._helpers.policy_design_case_projection import policy_design_case


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _complete_major_recommendation(**overrides: object) -> dict[str, object]:
    return {
        "claim_id": "rec_credit_guarantee",
        "claim_family": "recommendation",
        "major": True,
        "text": "Target capped credit guarantees to liquidity-constrained MSMEs.",
        "citation_refs": ["source.msme_panel", "norm.ua.credit_guarantee"],
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
            "budget_implication": ["sha256:" + "b" * 64],
            "distributional_impact": ["sha256:" + "d" * 64],
            "implementation_feasibility": ["sha256:" + "f" * 64],
            "implementation_risks": ["sha256:" + "r" * 64],
            "monitoring_plan": ["sha256:" + "m" * 64],
            "policy_tradeoffs": ["sha256:" + "t" * 64],
            "residual_uncertainty": ["sha256:" + "u" * 64],
            "withdrawal_reissue_triggers": ["sha256:" + "w" * 64],
        },
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


def _publishable_inputs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": "run-msme-publishable",
        "title": "MSME credit guarantee decision",
        "final_claims": [_complete_major_recommendation()],
        "policy_grounding_matrix": {
            "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
            "status": "pass",
            "policy_grounding_matrix_ref": "sha256:" + "1" * 64,
        },
        "quality_scorecard": {
            "quality_status": "pass",
            "performance_status": "pass",
            "approval_state": "approval_ready",
            "quality_scorecard_ref": "sha256:" + "2" * 64,
        },
        "conflict_check": {
            "status": "pass",
            "conflict_check_ref": "sha256:" + "5" * 64,
        },
        "approval_state": {"state": "approval_ready"},
        "assurance_refs": {
            "privacy_compliance_report_ref": _sha("6"),
            "security_assurance_report_ref": _sha("7"),
        },
        "claim_registry": _claim_registry(),
        "runtime_authority": _runtime_authority(),
    }
    payload.update(overrides)
    return payload


def test_compiles_public_decision_artifact_from_final_refs() -> None:
    artifact = compile_public_decision_artifact(
        run_id="run-msme-001",
        title="MSME credit guarantee decision",
        final_claims=[_complete_major_recommendation()],
        policy_grounding_matrix={
            "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
            "status": "pass",
            "policy_grounding_matrix_ref": "sha256:" + "1" * 64,
        },
        quality_scorecard={
            "quality_status": "pass",
            "performance_status": "warn",
            "approval_state": "approval_ready",
            "quality_scorecard_ref": "sha256:" + "2" * 64,
            "warnings": [{"code": "latency_warn", "message": "P95 near budget."}],
            "evidence_refs": {
                "fabric_retrieval_trace": "sha256:" + "3" * 64,
                "foundry_method_report": "sha256:" + "4" * 64,
            },
        },
        conflict_check={
            "status": "pass",
            "conflict_check_ref": "sha256:" + "5" * 64,
        },
        approval_state={"state": "approval_ready", "reviewer": "policy-board"},
        performance_warnings=[{"code": "queue_depth_warn", "message": "Queue elevated."}],
        assurance_refs={
            "privacy_compliance_report_ref": "sha256:" + "6" * 64,
            "security_assurance_report_ref": "sha256:" + "7" * 64,
        },
    )

    recommendation = artifact["recommendations"][0]
    assert artifact["schema_version"] == "policyos.scientist.decision_artifact.v1"
    assert artifact["run_id"] == "run-msme-001"
    assert artifact["decision_context"]["quality_status"] == "pass"
    assert artifact["decision_context"]["approval_state"] == "approval_ready"
    assert recommendation["citation_refs"] == [
        "source.msme_panel",
        "norm.ua.credit_guarantee",
    ]
    assert recommendation["sections"]["budget_implication"].startswith("Requires")
    assert artifact["refs"]["quality_scorecard_ref"] == "sha256:" + "2" * 64
    assert artifact["refs"]["privacy_compliance_report_ref"] == "sha256:" + "6" * 64
    assert {warning["code"] for warning in artifact["performance_warnings"]} == {
        "latency_warn",
        "queue_depth_warn",
    }


def test_draft_decision_packet_is_projection_and_non_publishable() -> None:
    artifact = compile_draft_decision_packet(
        run_id="run-draft-001",
        final_claims=[
            _complete_major_recommendation(
                section_evidence_refs={},
                typed_blockers={},
            )
        ],
        policy_grounding_matrix={"status": "fail"},
        quality_scorecard={"quality_status": "fail"},
        conflict_check={"status": "conflict"},
        approval_state="draft",
    )

    assert artifact["artifact_kind"] == "draft_decision_packet"
    assert artifact["authority_role"] == "projection"
    assert artifact["publishability"] == "not_publishable"
    assert artifact["decision_context"]["public_export_status"] == "draft_projection"


def test_publishable_decision_artifact_requires_statement_evidence_or_typed_blocker() -> None:
    claim_without_section_refs = _complete_major_recommendation(
        section_evidence_refs={},
        typed_blockers={
            "budget_implication": [
                {
                    "blocker_type": "budget_authority_unavailable",
                    "reason": "Fiscal envelope has not been published.",
                }
            ]
        },
    )

    inputs = _publishable_inputs(final_claims=[claim_without_section_refs])
    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**inputs)

    assert exc_info.value.issues[0]["code"] == ("claim_statement_missing_evidence_or_blocker")
    missing_scopes = {
        issue["statement_scope"]
        for issue in exc_info.value.issues
        if issue["code"] == "claim_statement_missing_evidence_or_blocker"
    }
    assert "distributional_impact" in missing_scopes
    assert "budget_implication" not in missing_scopes


def test_publishable_decision_artifact_rejects_empty_major_claim_set() -> None:
    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**_publishable_inputs(final_claims=[]))

    assert "publishable_artifact_major_claims_missing" in {
        issue["code"] for issue in exc_info.value.issues
    }


def test_publishable_decision_artifact_rejects_major_claim_without_pdc_registry() -> None:
    inputs = _publishable_inputs()
    inputs.pop("claim_registry")
    inputs.pop("runtime_authority")

    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**inputs)

    assert "claim_compiler_runtime_registry_missing" in {
        issue["code"] for issue in exc_info.value.issues
    }


def test_publishable_decision_artifact_mints_policy_design_case_claim_node() -> None:
    artifact = compile_publishable_decision_artifact(**_publishable_inputs())

    contract = artifact["claim_evidence_contract"]["policy_design_case_claim_contract"]
    assert contract["status"] == "pass"
    major_claim = contract["major_claims"][0]
    assert major_claim["assurance_node_id"] == "claim-node-rec-credit-guarantee"
    assert major_claim["source_data_refs"] == [
        "source.msme_panel",
        "data_forge.snapshot.msme",
    ]
    for required_ref_key in (
        "concept_refs",
        "legal_norm_refs",
        "source_data_refs",
        "scholar_refs",
        "method_refs",
        "portfolio_refs",
        "independence_refs",
        "specification_curve_refs",
        "disconfirming_refs",
        "synthesis_refs",
        "objective_tradeoff_refs",
        "uncertainty_refs",
        "numerical_semantics_refs",
        "monitoring_refs",
    ):
        assert major_claim[required_ref_key]
    node = contract["nodes"][0]
    assert node["node_type"] == "claim"
    assert node["runtime_authority_envelope"]["authority_role"] == "producer_authority"
    assert node["runtime_authority_envelope"]["provenance_kind"] == "runtime_emitted"
    for required_ref_key in (
        "concept_refs",
        "legal_norm_refs",
        "source_data_refs",
        "method_refs",
        "portfolio_refs",
        "independence_refs",
        "specification_curve_refs",
        "disconfirming_refs",
        "synthesis_refs",
        "objective_tradeoff_refs",
        "uncertainty_refs",
        "numerical_semantics_refs",
        "monitoring_refs",
    ):
        assert node[required_ref_key] == major_claim[required_ref_key]
    assert artifact["policy_design_case_claim_nodes"] == contract["nodes"]


def test_publishable_decision_artifact_rejects_claim_registry_missing_producer_refs() -> None:
    registry = _claim_registry()
    claim_row = registry["claims"][0]
    assert isinstance(claim_row, dict)
    producer_refs = dict(claim_row["selected_producer_refs"])
    producer_refs["fabric"] = []
    claim_row["selected_producer_refs"] = producer_refs

    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**_publishable_inputs(claim_registry=registry))

    producer_issues = [
        issue
        for issue in exc_info.value.issues
        if issue["code"] == "claim_compiler_producer_refs_missing"
    ]
    assert producer_issues
    assert producer_issues[0]["producer"] == "fabric"


def test_publishable_decision_artifact_rejects_claim_registry_prose_backfill() -> None:
    registry = _claim_registry()
    claim_row = registry["claims"][0]
    assert isinstance(claim_row, dict)
    claim_row["source_data_refs"] = []

    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**_publishable_inputs(claim_registry=registry))

    assert {
        "claim_compiler_source_data_refs_missing",
        "claim_compiler_prose_backfill_not_authority",
    } <= {issue["code"] for issue in exc_info.value.issues}


def test_publishable_decision_artifact_records_statement_evidence_contract() -> None:
    artifact = compile_publishable_decision_artifact(**_publishable_inputs())

    assert artifact["artifact_kind"] == "publishable_decision_artifact"
    assert artifact["authority_role"] == "final_decision_artifact"
    assert artifact["publishability"] == "publishable"
    contract = artifact["claim_evidence_contract"]
    assert contract["status"] == "pass"
    statement_scopes = {statement["statement_scope"] for statement in contract["statements"]}
    assert {
        "recommendation",
        "budget_implication",
        "implementation_feasibility",
        "distributional_impact",
        "implementation_risks",
        "monitoring_plan",
        "policy_tradeoffs",
        "residual_uncertainty",
    } <= statement_scopes


def test_publishable_decision_artifact_reads_policy_design_case_projection_semantics() -> None:
    artifact = compile_publishable_decision_artifact(
        **_publishable_inputs(policy_design_case=policy_design_case())
    )

    projection = artifact["projection_semantics"]
    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert "publishable" in projection["states"]
    assert artifact["authority_role"] == "final_decision_artifact"


@pytest.mark.parametrize(
    ("override", "expected_code"),
    [
        (
            {
                "policy_grounding_matrix": {
                    "status": "fail",
                    "issues": [{"code": "major_claim_missing_grounding"}],
                }
            },
            "publishable_artifact_grounding_not_passing",
        ),
        (
            {
                "assurance_refs": {
                    "security_assurance_report": {
                        "status": "fail",
                        "issues": [{"code": "unsafe_artifact_rendering_detected"}],
                    },
                    "privacy_compliance_report_ref": "sha256:" + "6" * 64,
                }
            },
            "publishable_artifact_security_not_passing",
        ),
        (
            {
                "assurance_refs": {
                    "privacy_compliance_report": {
                        "status": "fail",
                        "issues": [{"code": "privacy_compliance_blocking_failure"}],
                    },
                    "security_assurance_report_ref": "sha256:" + "7" * 64,
                }
            },
            "publishable_artifact_privacy_not_passing",
        ),
        (
            {
                "conflict_check": {
                    "status": "conflict",
                    "issues": [{"code": "norm_conflict_unresolved"}],
                }
            },
            "publishable_artifact_conflict_not_clear",
        ),
    ],
)
def test_publishable_decision_artifact_blocks_gate_failures(
    override: dict[str, object],
    expected_code: str,
) -> None:
    with pytest.raises(DecisionArtifactCompilationError) as exc_info:
        compile_publishable_decision_artifact(**_publishable_inputs(**override))

    assert expected_code in {issue["code"] for issue in exc_info.value.issues}


def test_public_decision_artifact_omits_private_and_sensitive_fields() -> None:
    artifact = compile_public_decision_artifact(
        run_id="run-redaction-001",
        final_claims=[
            _complete_major_recommendation(
                reviewer_private_notes="Use only in reviewer packet.",
                hidden_benchmark_answer="gold option is B",
                raw_sensitive_data=[{"household_id": "hh-1", "income": 100}],
                credentials={"api_key": "secret-key"},
                metadata={"safe": "kept", "password": "do-not-export"},
            )
        ],
        policy_grounding_matrix={"status": "pass"},
        quality_scorecard={"quality_status": "pass"},
        conflict_check={"status": "pass"},
        approval_state="approval_ready",
    )

    rendered = json.dumps(artifact, sort_keys=True)
    assert "source.msme_panel" in rendered
    assert "norm.ua.credit_guarantee" in rendered
    assert "reviewer_private_notes" not in rendered
    assert "hidden_benchmark_answer" not in rendered
    assert "raw_sensitive_data" not in rendered
    assert "api_key" not in rendered
    assert "password" not in rendered


def test_public_decision_artifact_marks_source_truth_conflicts_not_publishable() -> None:
    artifact = compile_public_decision_artifact(
        run_id="run-conflict-001",
        final_claims=[_complete_major_recommendation()],
        policy_grounding_matrix={"status": "pass"},
        quality_scorecard={
            "quality_status": "pass",
            "approval_state": "approval_ready",
            "source_truth_conflicts": [
                {
                    "field_family": "approval_readiness_public_status",
                    "failure_code": "hds_approval_readiness_authority_conflict",
                    "authoritative_source": "runtime.approval_packet",
                    "conflicting_source": "runtime.dashboard",
                    "lost_fields": ["decision"],
                }
            ],
        },
        conflict_check={"status": "pass"},
        approval_state={"state": "approval_ready"},
    )

    assert artifact["decision_context"]["public_export_status"] == "blocked"
    assert artifact["public_export_constraints"]["source_truth_conflicts_block_publication"] is True
    assert artifact["source_truth_conflicts"][0]["failure_code"] == (
        "hds_approval_readiness_authority_conflict"
    )


def test_public_decision_artifact_detects_runtime_scorecard_projection_conflict() -> None:
    artifact = compile_public_decision_artifact(
        run_id="run-public-conflict-001",
        final_claims=[_complete_major_recommendation()],
        policy_grounding_matrix={"status": "pass"},
        quality_scorecard={
            "quality_status": "fail",
            "approval_state": "approval_ready",
            "quality_scorecard_ref": "sha256:" + "8" * 64,
        },
        conflict_check={"status": "pass"},
        approval_state={"state": "approval_ready"},
    )

    assert artifact["decision_context"]["public_export_status"] == "blocked"
    conflict = artifact["source_truth_conflicts"][0]
    assert conflict["field_family"] == "approval_readiness_public_status"
    assert conflict["failure_code"] == "hds_approval_readiness_authority_conflict"
    assert "public_export_status" in conflict["lost_fields"]
