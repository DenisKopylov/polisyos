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
S10_RULE_VERSION_REF = "policyos.layer2.s10.outcome_prediction.v1"
S11_RULE_VERSION_REF = "policyos.layer2.s11.predictive_knowledge.v1"
S12_RULE_VERSION_REF = "policyos.layer2.s12.resource_economics.v1"
S13_RULE_VERSION_REF = "policyos.layer2.s13.post_deploy_accountability.v1"
S14_RULE_VERSION_REF = "policyos.layer2.s14.universality_assurance.v1"


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


def _s10_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "forecast_tier": "observable_calibrated",
        "forecast_authority_disposition_reason": (
            "Observable subset calibration supports a bounded forecast tier."
        ),
        "observable_subset_calibration_status": "pass",
        "forecast_calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "uncertainty_interval_refs": ["interval://ua-msme/credit-access/95"],
        "limitations": ["forecast support only; not recommendation authority"],
        "authority_boundary": {
            "authoritative_for": ["forecast_support_tiering"],
            "may_not_use_for": [
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "closeout_authority",
                "s11_calibration",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S10_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_recommendation",
            "production_claim_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "s11_calibration",
        ],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s11_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s11_predictive_posture_ref": "pdc://layer2/s11/ua-msme/predictive-knowledge",
        "effective_predictive_posture": "limited_by_weakest_boundary",
        "predictive_axis_upgrade_refs": [
            "pdc://layer2/s11/ua-msme/upgrade/measurability"
        ],
        "predictive_axis_rows": [
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "effective_maturity": "predictive",
                "relaxation_decision": "relaxed_to_predictive",
            },
            {
                "axis": "strategic_response",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "effective_maturity": "fail_closed",
                "relaxation_decision": "reverted_fail_closed",
            },
        ],
        "per_axis_predictive_calibration_status": "pass",
        "per_axis_predictive_calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        "proof_carrying_analytics_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "residual_limitation_refs": ["limitation://s11/strategic-response/fail-closed"],
        "s11_public_limitation": (
            "Predictive relaxation is limited by calibration and proof-carrying checks."
        ),
        "weakest_boundary_reason": "strategic_response remains fail_closed under S6.",
        "authority_boundary": {
            "authoritative_for": [
                "per_axis_predictive_calibration",
                "predictive_axis_maturity_upgrade",
            ],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "runtime_closeout_authority",
                "rich_simulation_authority",
                "s12_envelope_growth",
                "s13_accountability_closure",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S11_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "rich_simulation_authority",
        ],
        "limitations": [
            "S11 predictive relaxation remains calibration-limited and not authority."
        ],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _g3_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload = _s11_public_projection_payload(
        proof_carrying_analytics_ref="pdc://layer3/g3/ua-msme/proof/credit-access",
        ir_analytics_bridge_ref="ir-analytics-bridge://layer3/g3/ua-msme",
    )
    payload["layer3_g3_public_export_projection"] = {
        "projection_ref": "pdc://layer3/g3/ua-msme/public-export-projection",
        "status": "pass",
        "certificate_resolution_report_ref": (
            "repo://architecture/policy_design_case/"
            "layer3_g3_certificate_resolution_report.json"
        ),
        "search_ledger_refs": [
            "repo://architecture/policy_design_case/"
            "layer3_g3_ir_analytics_search_ledgers.json"
        ],
        "redacted_search_frontier_refs": [
            "g3-search-frontier://ua-msme/resolved-proof-candidates"
        ],
        "proof_carrying_analytics_refs": [
            "pdc://layer3/g3/ua-msme/proof/credit-access"
        ],
        "ir_analytics_bridge_refs": [
            "ir-analytics-bridge://layer3/g3/ua-msme"
        ],
        "method_requirement_refs": ["method-requirement://layer3/g3/ua-msme"],
        "s11_predictive_posture_refs": [
            "pdc://layer2/s11/ua-msme/predictive-knowledge"
        ],
        "resolved_certificate_count": 1,
        "blocked_certificate_count": 0,
        "authority_boundary": {
            "authoritative_for": ["g3_public_projection_audit"],
            "may_not_use_for": [
                "claim_authority",
                "policy_recommendation",
                "closeout_authority",
                "publication_authority",
            ],
        },
        "may_not_use_for": [
            "claim_authority",
            "policy_recommendation",
            "closeout_authority",
            "publication_authority",
            "search_hit_as_certificate",
        ],
        "raw_proof_payload": {
            "theorem_family": "raw material must not reach PUBLIC"
        },
        "raw_cas_manifest": {"artifact_ids": ["secret-cas-id"]},
        "raw_query_ledger": {"sql": "select * from hidden_ir_catalog"},
    }
    payload.update(overrides)
    return payload


def _s12_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s12_resource_posture_ref": "pdc://layer2/s12/ua-msme/resource-posture",
        "resource_allocation_policy_ref": (
            "pdc://layer2/s12/ua-msme/resource-allocation-policy"
        ),
        "explore_exploit_posture": "balanced_governed",
        "explore_exploit_dial_ref": "pdc://layer2/s7/ua-msme/explore-exploit-dial",
        "voi_allocation_refs": [
            "voi-allocation://ua-msme/acquisition",
            "voi-allocation://ua-msme/refinement",
            "voi-allocation://ua-msme/attention",
        ],
        "voi_site_count": 3,
        "typed_budget_refs": [
            "budget://ua-msme/compute",
            "budget://ua-msme/acquisition",
            "budget://ua-msme/expert-time",
            "budget://ua-msme/human-attention",
            "budget://ua-msme/legal-access",
        ],
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/allocation-pareto-archive",
        "envelope_growth_ledger_ref": "pdc://layer2/s12/ua-msme/envelope-growth-ledger",
        "growth_thermometer_ref": "pdc://layer2/s12/ua-msme/growth-thermometer",
        "override_rate_trend": "flat",
        "reuse_rate_trend": "improving",
        "held_out_status": "pending_s14",
        "resource_allocation_disposition": "advisory_only",
        "s12_public_growth_limitation": (
            "Resource allocation is a governed growth limitation, not a recommendation."
        ),
        "authority_boundary": {
            "authoritative_for": [
                "value_of_information_allocation",
                "explore_exploit_posture",
                "envelope_growth_ledger",
                "growth_thermometers",
                "knowledge_governance_throughput",
                "allocation_priority_input",
            ],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "rollout_authority",
                "publication_authority",
                "claim_authority",
                "closeout_authority",
                "approval_authority",
                "scorecard_authority",
                "preference_learning_authority",
                "mdp_bandit_optimizer_authority",
                "budget_interchangeability",
                "mission_or_value_self_authorization",
                "floor_relaxation",
                "s13_envelope_shrink",
                "s13_accountability_closure",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S12_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_authority",
            "production_recommendation",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "approval_authority",
            "scorecard_authority",
            "preference_learning_authority",
            "mdp_bandit_optimizer_authority",
            "budget_interchangeability",
            "mission_or_value_self_authorization",
            "floor_relaxation",
            "s13_envelope_shrink",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s13_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_s13_post_deploy_accountability_posture",
        "accountability_posture_ref": "pdc://layer2/s13/ua-msme/accountability-posture",
        "deployment_dossier_ref": "pdc://layer2/s13/ua-msme/deployment-dossier",
        "divergence_record_refs": [
            "pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"
        ],
        "learning_update_proposal_refs": [
            "learning-proposal://ua-msme/envelope-shrink"
        ],
        "envelope_revision_ref": "envelope-revision://ua-msme/shrink/001",
        "certified_envelope_delta_ref": "certified-envelope-delta://ua-msme/s12-growth",
        "assurance_case_delta_ref": "assurance-delta://ua-msme/s13/weakened",
        "attribution_status": "attributed",
        "attribution_classes": ["design_error"],
        "learning_change_control_classes": ["reissue_required"],
        "lifecycle_reissue_disposition": "reissue_required",
        "envelope_revision_direction": "shrink",
        "assurance_case_change": "weakened",
        "mape_k_trace_ref": "mape-k://ua-msme/post-deploy",
        "public_revision_state_ref": "public-revision-state://ua-msme/s13/001",
        "public_accountability_note_ref": "public-note://ua-msme/s13/accountability",
        "public_accountability_note": (
            "Post-deploy divergence is attributed and routed to reissue without "
            "rewriting the closed case."
        ),
        "public_revision_state": {
            "revision_state_id": "public-revision-state://ua-msme/s13/001",
            "affected_claim_ids": ["rec_1"],
            "unaffected_claim_ids": ["rec_2"],
            "public_diffs": [
                {
                    "claim_id": "rec_1",
                    "revision_kind": "post_deploy_accountability_note",
                    "public_reason": "Post-deploy divergence attributed to design error.",
                }
            ],
            "closed_case_historical_meaning": "preserved",
            "silent_upgrade_allowed": False,
            "authority_role": "projection_only",
            "may_not_use_for": [
                "claim_evidence_authority",
                "current_evidence_slot",
                "production_rollout_authority",
            ],
        },
        "closed_case_historical_meaning": "preserved",
        "authority_boundary": {
            "authoritative_for": [
                "post_deploy_accountability",
                "deployment_monitorability",
                "divergence_attribution",
                "learning_update_proposal",
                "post_deploy_mape_k_trace",
                "envelope_revision",
                "assurance_case_delta",
                "public_accountability_note",
            ],
            "may_not_use_for": [
                "production_rollout_authority",
                "recommendation_authority",
                "publication_authority",
                "approval_authority",
                "scorecard_authority",
                "pre_policy_evidence",
                "current_evidence_slot",
                "preference_learning",
                "automated_value_learning",
                "naive_ml_update",
                "s14_universality",
                "llm_attribution_authority",
                "local_governance_enum_for_reissue",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S13_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_rollout_authority",
            "recommendation_authority",
            "publication_authority",
            "approval_authority",
            "scorecard_authority",
            "pre_policy_evidence",
            "current_evidence_slot",
            "preference_learning",
            "automated_value_learning",
            "naive_ml_update",
            "s14_universality",
            "llm_attribution_authority",
            "local_governance_enum_for_reissue",
        ],
        "rule_version_ref": S13_RULE_VERSION_REF,
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


def _s14_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s14_universality_assurance_ref": "pdc://layer2/s14/universality-assurance-case",
        "universality_claim_gate_ref": "pdc://layer2/s14/universality-claim-gate",
        "universality_claim_disposition": "universal_claim_limited",
        "declared_operation_envelope_ref": "pdc://layer2/s14/declared-envelope",
        "d4_corpus_track_coverage_ref": "pdc://layer2/s14/d4-corpus-track-coverage",
        "d4_corpus_track_coverage_status": "pass",
        "expert_oracle_bootstrap_ref": "pdc://layer2/s14/expert-oracle-bootstrap",
        "expert_oracle_seed_only_layer_refs": ["weak_gold", "shadow_candidate_pool"],
        "breadth_floor_config_ref": "pdc://layer2/s14/breadth-floor-config",
        "breadth_floor_status": "pass",
        "excluded_domain_refs": ["domain://defense-targeting"],
        "universality_baseline_comparison_ref": "pdc://layer2/s14/baseline-comparison",
        "baseline_comparison_status": "pass",
        "grounded_authority_coverage_ref": "pdc://layer2/s14/grounded-authority",
        "grounded_authority_status": "pass",
        "a_firewall_refs": ["pdc://layer2/s6/a-firewall/measurability"],
        "claim_evidence_binding_refs": ["claim-binding://s14/universal-envelope/001"],
        "value_choice_provenance_refs": ["value-choice://s8/s14/authorized-schedule"],
        "mandate_legitimacy_refs": ["mandate://s14/governance-board/universality"],
        "capacity_check_refs": ["capacity://s14/capacity-constrained-cases"],
        "evaluation_status_composition_ref": "pdc://layer2/s14/status-composition",
        "status_composition_limit_refs": ["limitation://s14/weak-gold-seed-only"],
        "envelope_revision_dynamics_ref": "pdc://layer2/s14/envelope-revision-dynamics",
        "envelope_revision_dynamics_status": "pass",
        "axis_scorecard_ref": "pdc://layer2/s14/axis-scorecard",
        "axis_scorecard_rows": [
            {
                "axis_ref": "ACTOR.state_capacity_feasibility",
                "declared_posture": "limited",
                "battery_status": "pass",
                "limitation_refs": ["limitation://s14/capacity"],
            }
        ],
        "out_of_envelope_axis_refs": ["SYSTEM.dynamics_feedback"],
        "not_tested_axis_refs": ["SYSTEM.dynamics_feedback"],
        "hard_corner_case_refs": ["sealed://s14/capacity-constrained-refugee-services"],
        "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        "sealed_battery_freeze_hash": "sha256:" + "4" * 64,
        "sealed_battery_integrity_status": "pass",
        "mechanism_generality_report_ref": "pdc://layer2/s14/mechanism-generality",
        "mechanism_generality_status": "pass",
        "sublinear_marginal_bespoke_cost_status": "pass",
        "skeptic_defeater_refs": [
            "pdc://layer2/s14/defeater/bespoke_disguise_defeater",
            "pdc://layer2/s14/defeater/confident_theater_defeater",
            "pdc://layer2/s14/defeater/failure_boundary_defeater",
            "pdc://layer2/s14/defeater/single_axis_universality_defeater",
            "pdc://layer2/s14/defeater/frozen_once_defeater",
            "pdc://layer2/s14/defeater/first_call_defeater",
        ],
        "skeptic_defeater_statuses": {
            "bespoke_disguise_defeater": "pass",
            "confident_theater_defeater": "pass",
            "failure_boundary_defeater": "pass",
            "single_axis_universality_defeater": "pass",
            "frozen_once_defeater": "pass",
            "first_call_defeater": "pass",
        },
        "s9_projection_faithfulness_refs": ["pdc://layer2/s9/faithfulness/public"],
        "public_universality_limitation": (
            "Scoped universality is projection-only and limited to the declared envelope."
        ),
        "authority_boundary": {
            "authoritative_for": ["s14_universality_claim_gate"],
            "may_not_use_for": [
                "production_rollout_authority",
                "production_recommendation",
                "recommendation_authority",
                "publication_authority",
                "approval_authority",
                "claim_authority",
                "runtime_closeout_authority",
                "scorecard_authority",
                "preference_learning",
                "automated_value_learning",
                "aggregate_universal_score",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S14_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_rollout_authority",
            "production_recommendation",
            "recommendation_authority",
            "publication_authority",
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "preference_learning",
            "automated_value_learning",
            "aggregate_universal_score",
        ],
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_public_export_surfaces_limited_universality_claim_as_projection_only() -> None:
    bundle = build_public_export_bundle(
        run_id="run-public-s14-universality",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s14_public_projection_payload(),
    )

    assert bundle["authority_role"] == "projection_only"
    semantic_audit = bundle["semantic_audit"]
    verification = semantic_audit["s14_universality_projection_contract_verification"]
    assert verification["status"] == "pass"
    projection = bundle["projection_semantics"]
    assert projection["universality_claim_disposition"] == "universal_claim_limited"
    assert projection["authority_role"] == "projection_only"
    assert "production_recommendation" in projection["may_not_be_used_for"]


def test_public_export_blocks_hidden_battery_material_and_gold_labels() -> None:
    bundle = build_public_export_bundle(
        run_id="run-public-s14-redaction",
        artifacts={
            "public_summary": {
                "safe_ref": "pdc://layer2/s14/sealed-battery-run",
                "sealed_fixture_contents": {"case_id": "s14-hidden"},
                "gold_labels": ["sealed expected boundary"],
                "expert_oracle_private_notes": "private oracle note",
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s14_public_projection_payload(),
    )

    serialized = json.dumps(bundle)
    assert "sealed_fixture_contents" not in serialized
    assert "gold_labels" not in serialized
    assert "expert_oracle_private_notes" not in serialized
    assert bundle["redaction_summary"]["redacted_path_count"] >= 3


def test_public_export_blocks_s14_as_production_or_recommendation_authority() -> None:
    payload = _s14_public_projection_payload(
        authority_boundary={
            "authoritative_for": [
                "s14_universality_claim_gate",
                "production_rollout_authority",
                "recommendation_authority",
            ],
            "may_not_use_for": ["claim_authority"],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S14_RULE_VERSION_REF],
        }
    )

    with pytest.raises(
        PublicExportRedactionError,
        match="s14_as_production_or_recommendation_authority",
    ):
        build_public_export_bundle(
            run_id="run-public-s14-authority-laundering",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=payload,
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


def test_s10_public_export_shows_forecast_tier_without_recommendation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s10-forecast",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    assert projection["forecast_tier"] == "observable_calibrated"
    assert projection["observable_subset_calibration_status"] == "pass"
    assert projection["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert projection["limitations"]
    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "production_recommendation_text" not in rendered
    assert "recommendation_authority" not in rendered


def test_s10_machine_export_requires_calibration_and_source_refs() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="s10_machine_export_requires_calibration_and_source_refs",
    ):
        build_public_export_bundle(
            run_id="run-public-s10-machine-missing-refs",
            artifacts={"machine_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=_s10_public_projection_payload(
                forecast_calibration_record_ref=None,
                source_contract_ref=None,
                method_validity_ref=None,
                credible_evaluation_evidence_ref=None,
            ),
        )


def test_s10_machine_export_preserves_design_graph_context_and_method_validity_refs() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s10-machine-refs",
        artifacts={"machine_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(),
    )

    s10_projection = public_bundle["semantic_audit"]["s10_forecast_projection"]
    assert s10_projection["design_graph_ref"] == (
        "pdc://layer2/s5/ua-msme/recursive-design-graph"
    )
    assert s10_projection["prediction_context_ref"] == (
        "pdc://layer2/s10/ua-msme/prediction-context"
    )
    assert s10_projection["source_contract_ref"] == "source-contract://ua-msme/panel"
    assert s10_projection["method_validity_ref"] == "method-validity://foundry/causal/local"
    assert s10_projection["credible_evaluation_evidence_ref"] == (
        "evidence://ua-msme/credible-evaluation"
    )
    assert s10_projection["authority_boundary"]["may_not_use_for"]


def test_public_projection_does_not_promote_s11_to_recommendation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s11-predictive",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s11_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    assert projection["s11_public_limitation"]
    assert "production_recommendation" in projection["may_not_be_used_for"]
    assert projection["authority_role"] == "projection_only"

    s11_projection = public_bundle["semantic_audit"]["s11_predictive_projection"]
    assert s11_projection["effective_predictive_posture"] == "limited_by_weakest_boundary"
    assert s11_projection["proof_carrying_analytics_ref"].startswith("pdc://layer2/s11/")

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "recommendation_authority" not in rendered
    assert "production_recommendation_text" not in rendered


def test_public_export_projects_g3_audit_refs_without_raw_proof_or_search_payloads() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-g3-analytics-search",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_g3_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    g3_projection = public_bundle["semantic_audit"]["layer3_g3_analytics_search_projection"]

    assert projection["layer3_g3_public_export_projection_status"] == "pass"
    assert projection["layer3_g3_certificate_resolution_report_ref"].endswith(
        "layer3_g3_certificate_resolution_report.json"
    )
    assert projection["layer3_g3_resolved_certificate_count"] == 1
    assert "claim_authority" in projection["may_not_be_used_for"]
    assert g3_projection["authority_role"] == "projection_only"
    assert g3_projection["resolved_certificate_count"] == 1
    assert g3_projection["raw_proof_payload_exported"] is False
    assert g3_projection["raw_cas_manifest_exported"] is False
    assert g3_projection["raw_query_ledger_exported"] is False

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "raw material must not reach PUBLIC" not in rendered
    assert "secret-cas-id" not in rendered
    assert "select * from hidden_ir_catalog" not in rendered


def test_public_projection_shows_growth_limitation_without_allocation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s12-resource-economics",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s12_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    assert projection["s12_public_growth_limitation"]
    assert projection["explore_exploit_posture"] == "balanced_governed"
    assert projection["override_rate_trend"] == "flat"
    assert projection["reuse_rate_trend"] == "improving"
    assert "production_recommendation" in projection["may_not_be_used_for"]
    assert projection["authority_role"] == "projection_only"

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "allocation_recommendation_text" not in rendered
    assert "selected_policy_ref" not in rendered
    assert "allocation-policy://ua-msme/balanced-governed" not in rendered


def test_public_projection_surfaces_accountability_note_and_preserves_historical_meaning() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s13-accountability",
        artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s13_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    assert projection["public_accountability_note"]
    assert projection["envelope_revision_direction"] == "shrink"
    assert projection["closed_case_historical_meaning"] == "preserved"
    assert projection["authority_role"] == "projection_only"
    assert "current_evidence_slot" in projection["may_not_be_used_for"]


def test_public_accountability_note_projects_existing_public_revision_state() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s13-revision-state",
        artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s13_public_projection_payload(),
    )

    revision_states = public_bundle["semantic_audit"]["public_revision_states"]
    accountability_projection = public_bundle["semantic_audit"][
        "s13_post_deploy_accountability_projection"
    ]

    assert revision_states[0]["affected_claim_ids"] == ["rec_1"]
    assert revision_states[0]["unaffected_claim_ids"] == ["rec_2"]
    assert revision_states[0]["silent_upgrade_allowed"] is False
    assert accountability_projection["public_revision_state_ref"] == (
        "public-revision-state://ua-msme/s13/001"
    )
    assert accountability_projection["public_accountability_note_ref"] == (
        "public-note://ua-msme/s13/accountability"
    )


def test_public_projection_reuses_public_revision_state_silent_upgrade_firewall() -> None:
    with pytest.raises(PublicExportRedactionError, match="silent_upgrade"):
        build_public_export_bundle(
            run_id="run-public-s13-silent-upgrade",
            artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=_s13_public_projection_payload(
                public_revision_state={
                    "revision_state_id": "public-revision-state://ua-msme/s13/bad",
                    "affected_claim_ids": ["rec_1"],
                    "unaffected_claim_ids": ["rec_2"],
                    "public_diffs": [],
                    "closed_case_historical_meaning": "changed",
                    "silent_upgrade_allowed": True,
                    "authority_role": "producer_authority",
                    "may_not_use_for": [],
                }
            ),
        )
