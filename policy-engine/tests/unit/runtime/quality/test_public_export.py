from __future__ import annotations

import json

import pytest

from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    assert_public_export_official_use_limits,
    build_public_export_bundle,
)
from tests._helpers.hds_quality import authority_envelope_for, sha
from tests._helpers.policy_design_case_projection import policy_design_case


def test_public_export_redacts_sensitive_payloads_and_preserves_audit_semantics() -> None:
    authority_envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("3"),
    )
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        title="Public MSME support audit",
        artifacts={
            "decision_artifact": {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "text": "Target wartime credit support to eligible MSMEs.",
                "support_refs": {
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                },
                "hidden_benchmark_answer": "gold answer is option B",
                "provider_credentials": {"api_key": "sk-secret-token"},
                "tenant_id": "tenant-1",
                "private_prompt": "private system prompt for internal scoring",
                "restricted_source_material": "licensed source page text",
            }
        },
        authority_envelopes=[authority_envelope],
    )

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "Target wartime credit support" in rendered
    assert "production-msme-panel" in rendered
    assert "causal.difference_in_differences" in rendered
    assert "norm.ua.credit_eligibility" in rendered
    assert "gold answer is option B" not in rendered
    assert "sk-secret-token" not in rendered
    assert "tenant-1" not in rendered
    assert "private system prompt" not in rendered
    assert "licensed source page text" not in rendered

    projection = public_bundle["semantic_audit"]["authority_projections"][0]
    assert projection["evidence_id"] == "evidence-policy_grounding_matrix"
    assert projection["artifact_kind"] == "policy_grounding_matrix"
    assert projection["schema_name"] == "runtime_quality.policy_grounding_matrix.v1"
    assert projection["phase"] == "quality_evidence"
    assert projection["source_authority_role"] == "producer_authority"
    assert projection["source_blocking_status"] == "non_blocking"
    assert projection["authority_role"] == "projection_only"
    assert projection["allowed_scorecard_authority_role"] == "not_authoritative"
    assert projection["tenant_redacted"] is True
    assert projection["tenant_fingerprint"].startswith("sha256:")

    assert public_bundle["evidence_class"] == "redacted_derived"
    assert public_bundle["official_use_limits"]["official_use"] == "public_audit_only"
    assert "scorecard_authority" in public_bundle["official_use_limits"]["may_not_be_used_for"]
    assert "approval_authority" in public_bundle["official_use_limits"]["may_not_be_used_for"]
    assert public_bundle["redaction_summary"]["redacted_path_count"] >= 5


def test_public_export_reads_policy_design_case_projection_without_exposing_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        artifacts={
            "decision_artifact": {
                "claim_id": "rec_1",
                "text": "Target wartime credit support to eligible MSMEs.",
                "provider_credentials": {"api_key": "sk-secret-token"},
                "tenant_id": "tenant-sensitive",
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "public_export_classification": "public_redacted_projection",
            "decision_context": {"public_export_status": "publishable"},
            "publishability": "publishable",
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["primary_state"] == "redacted"
    assert {"publishable", "redacted", "projection_only"} <= set(projection["states"])
    assert projection["authority_role"] == "projection_only"
    assert "scorecard_authority" in projection["may_not_be_used_for"]

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "Target wartime credit support" in rendered
    assert "sk-secret-token" not in rendered
    assert "tenant-sensitive" not in rendered


def test_public_export_official_use_guard_rejects_authority_upgrade() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        artifacts={"summary": {"text": "Public summary."}},
        authority_envelopes=[],
    )
    public_bundle["authority_role"] = "producer_authority"

    with pytest.raises(PublicExportRedactionError, match="public_export_not_authority"):
        assert_public_export_official_use_limits(public_bundle)


def test_public_export_rejects_unexplained_replay_drift_even_with_scorecard_files() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_replay_drift_unexplained",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={
                "quality_scorecard_file": "quality_scorecard.json",
                "quality_scorecard_summary": {
                    "quality_status": "pass",
                    "approval_state": "approval_ready",
                },
                "drift_explanation": {
                    "schema_version": "policyos.drift_explanation.v1",
                    "status": "unexplained_drift",
                    "production_readiness": "fail",
                    "summary": {
                        "difference_count": 1,
                        "unexplained_difference_count": 1,
                        "drift_sources": ["data"],
                        "max_impact": "high",
                    },
                },
            },
            authority_envelopes=[],
        )


def test_public_export_rejects_accepted_non_ready_replay_drift() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_replay_drift_unbounded",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={
                "quality_scorecard_summary": {
                    "quality_status": "pass",
                    "approval_state": "approval_ready",
                },
                "drift_explanation": {
                    "schema_version": "policyos.drift_explanation.v1",
                    "status": "accepted_drift_non_ready",
                    "production_readiness": "fail",
                    "summary": {
                        "difference_count": 2,
                        "accepted_difference_count": 2,
                        "unexplained_difference_count": 0,
                        "drift_sources": ["registry"],
                        "max_impact": "high",
                    },
                    "blocking_failure": {
                        "code": "authority_replay_drift_unbounded",
                    },
                },
            },
            authority_envelopes=[],
        )
