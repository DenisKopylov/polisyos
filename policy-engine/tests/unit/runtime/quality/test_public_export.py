from __future__ import annotations

# ruff: noqa: S101
import json

import pytest

from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report
from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    assert_public_export_official_use_limits,
    build_public_export_bundle,
)
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from tests._helpers.hds_quality import authority_envelope_for, sha
from tests._helpers.policy_design_case_projection import policy_design_case

S9_RULE_VERSION_REF = "policyos.layer2.s9.projection_lowering.v1"


def _s9_public_faithfulness_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "faithfulness_id": "layer2.s9.faithfulness.public",
        "faithfulness_ref": "pdc://layer2/s9/ua-msme/faithfulness/public",
        "render_ref": "pdc://layer2/s9/ua-msme/projection-render/public",
        "request_ref": "pdc://layer2/s9/ua-msme/projection-request/public",
        "canonical_design_record_ref": "pdc://layer2/s9/ua-msme/canonical-design-record",
        "canonical_design_record_digest": "sha256:" + "9" * 64,
        "source_revision_ref": "git://policyos/layer2/s9/red-first",
        "faithfulness_status": "pass",
        "issue_codes": [],
        "added_claim_refs": [],
        "hidden_blocker_refs": [],
        "hidden_limitation_refs": [],
        "tradeoff_direction_status": "preserved",
        "shadow_approval_status": "not_approved",
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.projection_contract_verification.v1"
        ),
        "authority_boundary": {
            "authoritative_for": ["projection_faithfulness"],
            "may_not_use_for": [
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "scorecard_authority",
                "runtime_closeout_authority",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S9_RULE_VERSION_REF],
        },
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


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


def test_public_export_blocks_scalar_welfare_without_frontier_provenance() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="scalar_welfare_aggregate_without_frontier",
    ):
        build_public_export_bundle(
            run_id="run-public-scalar-welfare",
            artifacts={
                "decision_artifact": {
                    "claim_id": "claim:welfare:1",
                    "text": "Publish selected welfare option.",
                },
                "welfare_score": 0.72,
            },
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "publishability": "publishable",
            },
        )


def test_public_export_blocks_unverified_candidate_in_public_artifact() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="candidate_firewall_candidate_unverified",
    ):
        build_public_export_bundle(
            run_id="run-public-candidate-firewall",
            artifacts={
                "public_summary": {
                    "claim_refs": ["hypothesis-candidate:public-claim-1"],
                    "hypothesis_ledger": {
                        "schema_version": "policyos.runtime.hypothesis_ledger.v1",
                        "run_id": "run-wave6f",
                        "job_id": "job-wave6f",
                        "entries": [
                            {
                                "candidate_id": "hypothesis-candidate:public-claim-1",
                                "candidate_ref": "hypothesis-candidate:public-claim-1",
                                "source_class": "llm_drafter",
                                "candidate_kind": "public_projection_claim",
                                "target_authority_slots": ["projection_authority"],
                                "target_claim_ids": ["rec_1"],
                                "prompt_fingerprint": "sha256:" + "1" * 64,
                                "tool_refs": ["tool-output:public-projection"],
                                "repair_decision_lineage": ["repair:none"],
                                "authority_envelope": {
                                    "authoritative_for": ["candidate_hypothesis"],
                                    "may_not_use_for": ["projection_authority"],
                                },
                                "admission_state": "candidate_unverified",
                            }
                        ],
                    },
                }
            },
            authority_envelopes=[],
        )


def test_public_export_rejects_omitted_blocked_claim_without_omission_manifest() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_omission_manifest_missing",
    ):
        build_public_export_bundle(
            run_id="run-public-omission",
            artifacts={
                "claims_manifest": {
                    "included_claim_ids": ["rec_2"],
                    "omitted_claim_ids": ["rec_1"],
                }
            },
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "authority_role": "final_decision_artifact",
                "closeout_verdict": {
                    "status": "blocked",
                    "verdict": "cannot_closeout",
                    "can_closeout": False,
                    "issues": [
                        {
                            "code": "blocked_claim_missing_anchor",
                            "severity": "fail",
                            "message": "Claim rec_1 is blocked.",
                            "claim_ids": ["rec_1"],
                        }
                    ],
                },
            },
        )


def test_public_export_surfaces_omission_manifest_and_projection_contract_status() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-omission",
        artifacts={
            "claims_manifest": {
                "included_claim_ids": ["rec_2"],
                "omitted_claim_ids": ["rec_1"],
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "authority_role": "final_decision_artifact",
            "audit_refs": ["audit://pdc/w5a/public-export"],
            "closeout_verdict": {
                "status": "blocked",
                "verdict": "cannot_closeout",
                "can_closeout": False,
                "issues": [
                    {
                        "code": "omitted_blocked_claim",
                        "severity": "omission",
                        "message": "Claim rec_1 is omitted from the public bundle.",
                        "claim_ids": ["rec_1"],
                        "module_id": "public_export",
                        "evidence_ref": sha("9"),
                    }
                ],
            },
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["contract_verification_status"] == "pass"
    assert "audit://pdc/w5a/public-export" in projection["audit_refs"]
    assert projection["omission_manifest"][0]["claim_ids"] == ["rec_1"]
    assert public_bundle["semantic_audit"]["omission_manifest"] == projection["omission_manifest"]
    assert public_bundle["semantic_audit"]["projection_contract_verification"]["status"] == "pass"


def test_public_export_surfaces_rule_evolution_annotation_without_authority_upgrade() -> None:
    old_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-05",
        version="2026.05",
        effective_at="2026-05-22T00:00:00+00:00",
        rule_refs=[
            {
                "requirement_id": "req.credit_support",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.2},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation",
                "version": "2026.05",
                "ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref="event://rule-evolution/2026-05",
    )
    changed_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-07",
        version="2026.07",
        effective_at="2026-07-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.35},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
            }
        ],
        evidence_ref=sha("c"),
        runtime_event_ref="event://rule-evolution/2026-07",
    )

    public_bundle = build_public_export_bundle(
        run_id="run-public-rule-evolution",
        artifacts={
            "rule_evolution_public_annotation": changed_registry["public_annotation"],
        },
        authority_envelopes=[],
    )

    annotations = public_bundle["semantic_audit"]["rule_evolution_annotations"]
    assert annotations[0]["public_annotation_state"] == "semantic_change"
    assert annotations[0]["revalidation_state"] == "revalidation_required"
    assert annotations[0]["silent_upgrade_allowed"] is False
    assert public_bundle["authority_role"] == "projection_only"


def test_public_export_surfaces_lifecycle_public_revision_state_without_authority_upgrade() -> None:
    lifecycle_report = build_lifecycle_reissue_report(
        report_id="lifecycle-reissue-public",
        case_id="pdc-R_hds_red_control",
        claim_ids=["rec_1", "rec_2"],
        source_events=[
            {
                "event_id": "source-stale-rec-1",
                "event_type": "source_invalidation",
                "invalidation_type": "stale",
                "affected_claim_ids": ["rec_1"],
                "reason": "Primary data source freshness window expired.",
                "evidence_ref": sha("1"),
                "runtime_event_ref": "event://source/stale-rec-1",
                "occurred_at": "2026-07-02T00:00:00+00:00",
            }
        ],
        evidence_ref=sha("2"),
        runtime_event_ref="event://policy-design-case/lifecycle-reissue/public",
    )

    public_bundle = build_public_export_bundle(
        run_id="run-public-lifecycle",
        artifacts={
            "lifecycle_reissue_report": lifecycle_report,
        },
        authority_envelopes=[],
    )

    revision_states = public_bundle["semantic_audit"]["public_revision_states"]
    assert revision_states[0]["affected_claim_ids"] == ["rec_1"]
    assert revision_states[0]["unaffected_claim_ids"] == ["rec_2"]
    assert revision_states[0]["silent_upgrade_allowed"] is False
    assert revision_states[0]["authority_role"] == "projection_only"
    assert "claim_evidence_authority" in revision_states[0]["may_not_use_for"]
    assert public_bundle["authority_role"] == "projection_only"


@pytest.mark.parametrize(
    "recourse_pointer",
    [
        None,
        {
            "uri": "https://appeals.example.test/policy-design-case/run-public-redaction",
            "verification_status": "unreachable",
            "verified_at": "2026-05-22T10:00:00Z",
            "verification_ref": "runtime-event://recourse-pointer/unreachable",
        },
    ],
)
def test_public_export_blocks_high_stakes_contested_production_without_reachable_recourse(
    recourse_pointer: dict[str, object] | None,
) -> None:
    projection_payload: dict[str, object] = {
        "publishability": "publishable",
        "contestability_status": "contested",
        "stakes": "high_stakes",
        "authority_level": "production",
        "decision_context": {"public_export_status": "publishable"},
    }
    if recourse_pointer is not None:
        projection_payload["recourse_pointer"] = recourse_pointer

    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_recourse_pointer_unreachable",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={"decision_artifact": {"claim_id": "rec_1"}},
            authority_envelopes=[],
            policy_design_case={
                **policy_design_case(),
                "contestability_status": "contested",
                "stakes": "high_stakes",
            },
            projection_payload=projection_payload,
        )


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


def test_public_export_requires_s9_faithfulness_pass_for_projection_release() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match=r"s9_projection_faithfulness_failed|s9_projection_added_claim",
    ):
        build_public_export_bundle(
            run_id="run-public-s9-faithfulness",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "s9_projection_faithfulness": _s9_public_faithfulness_payload(
                    faithfulness_status="fail",
                    issue_codes=["s9_projection_added_claim"],
                    added_claim_refs=["claim://ua-msme/new-public-benefit-claim"],
                ),
            },
        )


def test_public_export_blocks_s9_projection_that_hides_redacted_blocker() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="s9_redaction_hides_blocker",
    ):
        build_public_export_bundle(
            run_id="run-public-s9-redaction-blocker",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "s9_projection_faithfulness": _s9_public_faithfulness_payload(
                    faithfulness_status="fail",
                    issue_codes=["s9_redaction_hides_blocker"],
                    hidden_blocker_refs=[
                        "pdc://layer2/s6/ua-msme/strategic-response-blocker"
                    ],
                ),
                "omission_manifest": [],
            },
        )


def test_public_export_without_s9_block_keeps_existing_projection_behavior() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-no-s9",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "public_export_classification": "public_redacted_projection",
            "decision_context": {"public_export_status": "publishable"},
            "publishability": "publishable",
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["authority_role"] == "projection_only"
    assert projection["contract_verification_status"] == "pass"
    assert "s9_projection_faithfulness" not in projection
    assert public_bundle["semantic_audit"]["projection_contract_verification"]["status"] == "pass"
