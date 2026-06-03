from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

import pytest

import polisyos.runtime.quality.projection_semantics as projection_semantics_module
from polisyos.core.contracts.policy_design_case_projection import (
    PolicyDesignCaseAudience,
    PolicyDesignCaseProjection,
)
from polisyos.participation_requirement import (
    ParticipationProvenanceCompiler,
    ParticipationProvenanceRecord,
    ParticipationSourceKind,
    evaluate_participation_requirement,
)
from polisyos.pdc import compile_runtime_policy_design_case
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
    build_policy_design_case_projection_contract_fixture,
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
    verify_policy_design_case_projection_consumer_contract,
)
from tests._helpers.policy_design_case_projection import policy_design_case, sha

S9_RULE_VERSION_REF = "policyos.layer2.s9.projection_lowering.v1"
S9_CANONICAL_REF = "pdc://layer2/s9/ua-msme/canonical-design-record"
S9_SOURCE_REVISION_REF = "git://policyos/layer2/s9/red-first"
S10_RULE_VERSION_REF = "policyos.layer2.s10.outcome_prediction.v1"
S11_RULE_VERSION_REF = "policyos.layer2.s11.predictive_knowledge.v1"
S12_RULE_VERSION_REF = "policyos.layer2.s12.resource_economics.v1"
S13_RULE_VERSION_REF = "policyos.layer2.s13.post_deploy_accountability.v1"


def _s9_consumer_verifier() -> object:
    return (
        projection_semantics_module.verify_s9_projection_faithfulness_for_pdc_consumer_contract
    )


def _s9_faithfulness_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "faithfulness_id": "layer2.s9.faithfulness.public",
        "faithfulness_ref": "pdc://layer2/s9/ua-msme/faithfulness/public",
        "render_ref": "pdc://layer2/s9/ua-msme/projection-render/public",
        "request_ref": "pdc://layer2/s9/ua-msme/projection-request/public",
        "canonical_design_record_ref": S9_CANONICAL_REF,
        "canonical_design_record_digest": "sha256:" + "9" * 64,
        "source_revision_ref": S9_SOURCE_REVISION_REF,
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


def _s9_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_canonical_design_record",
        "source_revision_ref": S9_SOURCE_REVISION_REF,
        "s9_projection_faithfulness": _s9_faithfulness_payload(),
        "closeout_truth": {
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "blocker_codes": ["s6_strategic_response_blocker"],
            "omission_codes": ["s9_public_projection_missing_limitation"],
        },
        "omission_manifest": [
            {
                "omission_code": "s9_public_projection_missing_limitation",
                "claim_ids": ["rec_1"],
                "reason": "load-bearing limitation must be disclosed.",
            }
        ],
        "contested_records": [
            {
                "contested_record_id": "contest-s8-value-choice",
                "contestability_status": "contested",
            }
        ],
        "deficit_register": [
            {
                "deficit_id": "deficit-s8-value-provenance",
                "deficit_code": "value_choice_contested",
            }
        ],
        "projection_gaps": [
            {
                "gap_code": "s6_strategic_response_blocker",
                "gap_family": "closeout_blocker",
            }
        ],
        "may_not_be_used_for": [
            "claim_authority",
            "scorecard_authority",
            "runtime_closeout_authority",
            "production_recommendation",
        ],
    }
    payload.update(overrides)
    return payload


def _s10_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_canonical_design_record",
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "forecast_tier": "observable_calibrated",
        "forecast_authority_disposition_reason": (
            "Observable subset calibration supports a bounded forecast tier."
        ),
        "forecast_calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "uncertainty_interval_refs": ["interval://ua-msme/credit-access/95"],
        "calibration_status": "pass",
        "s5_forecast_support_ref": "pdc://layer2/s5/ua-msme/system-effect-support",
        "s6_firewall_status_refs": ["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice",
        "s8_value_tradeoff_disclosure_ref": "pdc://layer2/s8/ua-msme/tradeoff",
        "welfare_comparison": {
            "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice",
            "s8_value_tradeoff_disclosure_ref": "pdc://layer2/s8/ua-msme/tradeoff",
            "scalar_summary_allowed": False,
            "pareto_frontier_ref": "foundry://welfare/frontier/ua-msme",
            "rejected_nondominated_alternative_refs": [
                "alternative://ua-msme/cash-transfer"
            ],
        },
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


def _s11_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "audience": "REVIEWER",
        "authority_role": "projection_only",
        "projection_policy": "reads_canonical_design_record",
        "s11_predictive_posture_ref": "pdc://layer2/s11/ua-msme/predictive-knowledge",
        "effective_predictive_posture": "limited_by_weakest_boundary",
        "predictive_axis_upgrade_refs": [
            "pdc://layer2/s11/ua-msme/upgrade/measurability",
            "pdc://layer2/s11/ua-msme/upgrade/strategic-response",
        ],
        "predictive_axis_rows": [
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "effective_maturity": "predictive",
                "relaxation_decision": "relaxed_to_predictive",
                "confidence": 0.78,
            },
            {
                "axis": "strategic_response",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "effective_maturity": "fail_closed",
                "relaxation_decision": "reverted_fail_closed",
                "confidence": 0.41,
            },
        ],
        "per_axis_predictive_calibration_status": "pass",
        "per_axis_predictive_calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        "proof_carrying_analytics_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "residual_limitation_refs": [
            "limitation://s11/strategic-response/fail-closed",
            "limitation://s11/calibration/current-run",
        ],
        "weakest_boundary_reason": "strategic_response remains fail_closed under S6.",
        "s11_public_limitation": (
            "Predictive relaxation is limited by per-axis calibration and proof checks."
        ),
        "authority_boundary": {
            "authoritative_for": [
                "per_axis_predictive_calibration",
                "predictive_axis_maturity_upgrade",
                "proof_carrying_analytics_validity",
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
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s12_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "audience": "EXPERT",
        "authority_role": "projection_only",
        "projection_policy": "reads_resource_economics_posture_as_constraint",
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
        "residual_limitation_refs": ["limitation://s12/no-production-authority"],
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


def _s13_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "audience": "REVIEWER",
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
        "closed_case_historical_meaning": "preserved",
        "owner": "policy-design-accountability-owner",
        "deadline": "2026-07-01",
        "action_item_status": "closed",
        "action_item_closure_refs": ["closure://ua-msme/s13/action-item/001"],
        "oversight_effectiveness_ref": "oversight://ua-msme/effectiveness/001",
        "oversight_accountability_state": "rubber_stamp_divergence_review_required",
        "reissue_actions": ["open_reissue_packet", "publish_accountability_note"],
        "historical_prior_influence_refs": [
            "historical-prior-influence:ua-msme/default-risk-route"
        ],
        "source_refs": ["post-policy-observation://ua-msme/default-rate-2023"],
        "replay_digest": "sha256:" + "a" * 64,
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


def _issue_codes(result: dict[str, object]) -> set[str]:
    issues = result.get("issues", [])
    return {
        str(issue.get("code"))
        for issue in issues
        if isinstance(issue, dict) and issue.get("code")
    } | {str(code) for code in result.get("issue_codes", [])}


def test_projection_semantics_labels_publishable_without_minting_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="final_artifact",
        source_payload={
            "artifact_kind": "publishable_decision_artifact",
            "publishability": "publishable",
            "decision_context": {"public_export_status": "publishable"},
            "authority_role": "final_decision_artifact",
        },
        source_ref=sha("9"),
        generated_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC),
    )

    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert projection["source_authority_refs"]["policy_design_case_ref"] == sha("a")
    assert "publishable" in projection["states"]
    assert "projection_only" in projection["states"]
    assert {label["state"]: label["authority_role"] for label in projection["labels"]}[
        "publishable"
    ] == "projection_only"
    assert "scorecard_authority" in projection["may_not_be_used_for"]

    assert_policy_design_projection_not_authority(projection)


def test_projection_backend_consumes_runtime_pdc_graph_as_source_of_truth() -> None:
    graph = compile_runtime_policy_design_case(
        run_id="run-24",
        job_id="job-24",
        tenant_id="tenant-sensitive",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-graph-source",
                "claim_type": "factual",
                "claim_use": "decision_support",
                "text": "Graph-backed policy claim.",
                "support_status": "supported",
                "publishability": "review_required",
                "readiness_level": "recommendation_ready",
                "obligation_refs": ["obligation:graph-source"],
            }
        ],
        claim_registry={
            "runtime_claim_registry_ref": sha("1"),
            "claims": [
                {
                    "claim_id": "claim-graph-source",
                    "data_refs": ["data:graph-source"],
                    "selected_norm_refs": ["norm:graph-source"],
                    "method_output_refs": ["method:graph-source"],
                }
            ],
        },
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "graph_source_blocker",
                    "severity": "fail",
                    "message": "The graph source carries the blocker.",
                    "module_id": "claim_registry",
                }
            ],
        },
        generated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )

    projection = build_policy_design_case_projection_from_runtime_graph(
        runtime_pdc_graph=graph,
        surface="machine_projection",
        audience=PolicyDesignCaseAudience.MACHINE,
        generated_at=datetime(2026, 5, 24, 12, 1, tzinfo=UTC),
    )

    assert projection["source_ref"] == graph.graph_ref
    assert projection["projection_policy"] == "reads_runtime_policy_design_case_graph"
    assert projection["source_state"]["runtime_pdc_graph_ref"] == graph.graph_ref
    assert set(projection["source_state"]["runtime_pdc_graph_consumed_fields"]) <= set(
        type(graph).model_fields
    )
    assert projection["closeout_truth"]["blocker_codes"] == ["graph_source_blocker"]
    assert projection["authority_role"] == "projection_only"
    assert projection["authoritative_for"] == []

    verification = verify_policy_design_case_projection_consumer_contract(
        projections={"machine": projection},
        expected_closeout_truth=projection["closeout_truth"],
        runtime_pdc_graph=graph,
    )

    assert verification["status"] == "pass"
    assert verification["consumer_contracts"][0]["verified_fields"][-2:] == [
        "runtime_pdc_graph_ref",
        "runtime_pdc_graph_consumed_fields",
    ]


def test_projection_semantics_labels_public_exports_as_redacted_projection() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
            "decision_context": {"public_export_status": "publishable"},
        },
        source_ref=sha("8"),
    )

    assert projection["primary_state"] == "redacted"
    assert projection["authority_role"] == "projection_only"
    assert projection["redacted"] is True
    assert {"redacted", "publishable", "projection_only"} <= set(projection["states"])
    assert "tenant-sensitive" not in str(projection)


def test_projection_semantics_rejects_projection_that_mints_claim_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="dashboard",
        source_payload={"decision_context": {"public_export_status": "publishable"}},
    )
    projection["authority_role"] = "producer_authority"

    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_mints_authority",
    ):
        assert_policy_design_projection_not_authority(projection)


def test_projection_semantics_rejects_authority_bearing_projection_source() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_source_mints_authority",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="api_projection",
            source_payload={
                "authority_role": "producer_authority",
                "decision_context": {"public_export_status": "publishable"},
            },
        )


def test_projection_semantics_rejects_capability_binding_projection_laundering() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="capability_binding_projection_laundering",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="dashboard",
            source_payload={
                "authority_role": "projection_only",
                "capability_binding_results": [
                    {
                        "schema_version": "policyos.capability_binding_result.v1",
                        "binding_id": "binding:projection-laundered",
                        "status": "selected_exact",
                        "authority_role": "projection_only",
                        "authoritative_for": ["claim_evidence"],
                        "satisfies_claim_evidence": True,
                    }
                ],
            },
        )


def test_projection_semantics_blocks_unverified_candidate_projection_laundering() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="candidate_firewall_candidate_unverified",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="dashboard",
            source_payload={
                "authority_role": "projection_only",
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
                                "may_not_use_for": [
                                    "projection_authority",
                                    "claim_authority",
                                ],
                            },
                            "admission_state": "candidate_unverified",
                        }
                    ],
                },
            },
        )


def test_typed_projection_preserves_closeout_truth_across_audiences() -> None:
    closeout = {
        "schema_version": "policyos.runtime.can_i_closeout.reader_skeleton.v1",
        "status": "blocked",
        "verdict": "cannot_closeout",
        "can_closeout": False,
        "issues": [
            {
                "code": "claim_registry_missing_legal_anchor",
                "severity": "fail",
                "message": "Claim has global Lex refs but no per-claim legal anchor.",
                "module_id": "claim_registry",
                "owner": "team-scientist-evidence",
                "evidence_ref": sha("1"),
                "next_action": "Bind the Lex authority ref to claim rec_1.",
            }
        ],
    }
    source_payload = {
        "artifact_kind": "publishable_decision_artifact",
        "publishability": "publishable",
        "decision_context": {"public_export_status": "publishable"},
        "authority_role": "final_decision_artifact",
        "deficit_register": [
            {
                "deficit_id": "deficit-participation-frame",
                "deficit_family": "participation",
                "deficit_code": "summary_without_underlying_method",
                "claim_ids": ["rec_1"],
                "authority_level": "production",
                "audience_scope": "public",
                "disposition": "publish_with_limitation",
                "owner": "team-participation",
                "ttl_expires_at": "2026-06-01T00:00:00Z",
                "runtime_event_ref": "event://deficits/participation-frame",
                "evidence_ref": sha("2"),
                "public_limitation_note": (
                    "Participation prevalence is limited to sampled respondents."
                ),
            }
        ],
        "contested_records": [
            {
                "contested_record_id": "contest-rec-1",
                "case_ref": sha("3"),
                "claim_refs": ["rec_1"],
                "audience_visibility": ["public", "reviewer", "expert", "machine"],
                "contestability_status": "contested",
                "grounds": ["counterevidence"],
                "standing_or_actor_ref": "actor://msme-association",
                "counterevidence_refs": [sha("4")],
                "source_truth_conflict_refs": [sha("5")],
                "authority_profile": "production",
                "publication_effect": "review_before_publication",
                "reopening_trigger_refs": ["event://reopen/rec-1"],
                "lifecycle_event_refs": ["event://lifecycle/rec-1"],
                "recourse_outcome_refs": [],
                "ingestion_event_refs": [],
                "public_projection_effect": "show_contested_state",
            }
        ],
        "invariant_summary": {
            "status": "fail",
            "passing_count": 7,
            "failing_count": 1,
            "blocker_codes": ["claim_registry_missing_legal_anchor"],
            "evidence_refs": [sha("6")],
        },
    }

    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=closeout,
        source_payload=source_payload,
        audiences=(
            PolicyDesignCaseAudience.PUBLIC,
            PolicyDesignCaseAudience.REVIEWER,
            PolicyDesignCaseAudience.EXPERT,
            PolicyDesignCaseAudience.MACHINE,
        ),
        generated_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    assert fixture["status"] == "pass"
    assert {
        row["audience"] for row in fixture["consumer_contracts"] if row["status"] == "pass"
    } == {"public", "reviewer", "expert", "machine"}
    projections = fixture["projections"]
    public = PolicyDesignCaseProjection.model_validate(projections["public"])
    machine = PolicyDesignCaseProjection.model_validate(projections["machine"])

    assert public.schema_version == "policyos.runtime.policy_design_case.projection.v1"
    assert public.authority_role == "projection_only"
    assert public.authoritative_for == ()
    assert "runtime_closeout_authority" in public.may_not_be_used_for
    assert public.closeout_truth.can_closeout is False
    assert public.closeout_truth.blocker_codes == ("claim_registry_missing_legal_anchor",)
    assert machine.closeout_truth == public.closeout_truth
    assert public.deficit_register[0].deficit_code == "summary_without_underlying_method"
    assert public.contested_records[0].contestability_status == "contested"
    assert public.projection_gaps[0].gap_code == "claim_registry_missing_legal_anchor"
    assert public.invariant_summary.status == "fail"
    assert public.redacted is True
    assert machine.redacted is False


def test_external_surface_fixture_surfaces_omissions_audit_refs_and_contract_status() -> None:
    closeout = {
        "schema_version": "policyos.runtime.can_i_closeout.reader_skeleton.v1",
        "status": "blocked",
        "verdict": "cannot_closeout",
        "can_closeout": False,
        "issues": [
            {
                "code": "blocked_claim_missing_anchor",
                "severity": "fail",
                "message": "Blocked claim is missing a claim-bound legal anchor.",
                "module_id": "claim_registry",
                "owner": "team-scientist-evidence",
                "evidence_ref": sha("1"),
            },
            {
                "code": "omitted_blocked_claim",
                "severity": "omission",
                "message": "Claim rec_1 is omitted from the public summary.",
                "claim_ids": ["rec_1"],
                "module_id": "public_export",
                "owner": "team-policyos-runtime",
                "evidence_ref": sha("2"),
            },
            {
                "code": "limited_participation_frame",
                "severity": "limitation",
                "message": "Participation evidence is sampled and cannot be generalized.",
                "claim_ids": ["rec_2"],
                "module_id": "participation",
                "owner": "team-participation",
                "evidence_ref": sha("3"),
            },
        ],
    }
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=closeout,
        source_payload={
            "authority_role": "final_decision_artifact",
            "audit_refs": ["audit://pdc/w5a/surface-truth"],
            "source_ref": sha("4"),
            "redaction_summary": {
                "erased_paths": ["claims.rec_1.private_basis"],
                "redacted_path_count": 1,
            },
        },
        generated_at=datetime(2026, 5, 23, 11, 0, tzinfo=UTC),
    )

    assert fixture["status"] == "pass"
    public = fixture["projections"]["public"]
    machine = fixture["projections"]["machine"]

    assert public["contract_verification_status"] == "pass"
    assert machine["contract_verification_status"] == "pass"
    assert "audit://pdc/w5a/surface-truth" in public["audit_refs"]
    assert public["omission_manifest"][0]["omission_code"] == "omitted_blocked_claim"
    assert public["omission_manifest"][0]["claim_ids"] == ["rec_1"]
    assert {gap["gap_family"] for gap in public["projection_gaps"]} >= {
        "closeout",
        "limitation",
        "omission",
    }
    assert public["closeout_truth"]["limitation_codes"] == ["limited_participation_frame"]
    assert public["closeout_truth"]["omission_codes"] == ["omitted_blocked_claim"]


def test_projection_contract_rejects_public_audience_hiding_blockers_or_contested_state() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "blocked_claim",
                    "severity": "fail",
                    "message": "Blocked claim cannot be hidden.",
                }
            ],
        },
        source_payload={
            "authority_role": "final_decision_artifact",
            "contested_records": [
                {
                    "contested_record_id": "contest-hidden",
                    "case_ref": sha("3"),
                    "claim_refs": ["rec_1"],
                    "audience_visibility": ["public"],
                    "contestability_status": "contested",
                    "grounds": ["dissent"],
                    "standing_or_actor_ref": "actor://affected",
                    "counterevidence_refs": [sha("4")],
                    "source_truth_conflict_refs": [],
                    "authority_profile": "production",
                    "publication_effect": "review_before_publication",
                    "reopening_trigger_refs": [],
                    "lifecycle_event_refs": [],
                    "recourse_outcome_refs": [],
                    "ingestion_event_refs": [],
                    "public_projection_effect": "show_contested_state",
                }
            ],
        },
    )
    public_projection = dict(fixture["projections"]["public"])
    public_projection["closeout_truth"] = {
        **dict(public_projection["closeout_truth"]),
        "blocker_codes": [],
        "blockers": [],
    }
    public_projection["contested_records"] = []

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "public": public_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert {issue["code"] for issue in result["issues"]} >= {
        "policy_design_projection_hides_closeout_blockers",
        "policy_design_projection_hides_contested_state",
    }


def test_projection_semantics_surfaces_participation_requirement_downgrades_safely() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e",
            "claims": [
                {
                    "claim_id": "claim-preference",
                    "claim_family": "preference",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                    "text": "Affected population preference claim.",
                }
            ],
        }
    ).requirements[0]
    evaluation = evaluate_participation_requirement(
        requirement,
        [
            ParticipationProvenanceRecord(
                participation_ref="participation:thin-consultation",
                claim_refs=("claim-preference",),
                source_kind=ParticipationSourceKind.CONSULTATION,
                consultation_mode="consult",
                provenance_class="C_attributable_nonrepresentative",
                representativeness_class="nonrepresentative",
                sampling_or_recruitment_frame=None,
                affected_group_map={"groups": ["self_selected_msmes"]},
                consent_redaction_state="public_summary_only",
                dissent_state="recorded",
                sponsor_disclosure="agency_sponsor_disclosed",
                limitations=("raw transcript exists but is not public-safe",),
                evidence_ref=sha("7"),
                raw_material_ref="restricted://participation/raw/transcript-1",
            )
        ],
    )

    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
            "participation_requirement_evaluations": [
                evaluation.model_dump(mode="json")
            ],
        },
        audience=PolicyDesignCaseAudience.PUBLIC,
        source_ref=sha("8"),
    )

    assert projection["participation_requirements"][0]["claim_use_requested"] == "prevalence"
    assert projection["participation_requirements"][0]["claim_use_allowed"] == "qualitative"
    assert projection["participation_requirements"][0]["raw_materials_redacted"] is True
    assert "restricted://participation/raw/transcript-1" not in str(projection)
    assert "nonrepresentative_for_claim_scope" in {
        gap["gap_code"] for gap in projection["projection_gaps"]
    }
    assert projection["deficit_register"][0]["deficit_family"] == "participation"


def test_projection_contract_rejects_missing_omission_manifest_even_when_shape_passes() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "omitted_blocked_claim",
                    "severity": "omission",
                    "message": "Claim rec_1 is omitted from the public summary.",
                    "claim_ids": ["rec_1"],
                    "module_id": "public_export",
                }
            ],
        },
        source_payload={"authority_role": "final_decision_artifact"},
    )
    public_projection = dict(fixture["projections"]["public"])
    public_projection["omission_manifest"] = []

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "public": public_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_hides_omission_manifest" in {
        issue["code"] for issue in result["issues"]
    }


def test_projection_contract_rejects_machine_surface_without_reconstructable_refs() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "ready",
            "verdict": "can_closeout",
            "can_closeout": True,
            "issues": [],
        },
        source_payload={
            "authority_role": "final_decision_artifact",
            "source_ref": sha("7"),
            "audit_refs": ["audit://pdc/w5a/machine-contract"],
        },
    )
    machine_projection = {
        **dict(fixture["projections"]["machine"]),
        "source_ref": None,
        "source_ref_fingerprint": None,
        "source_authority_refs": {},
        "audit_refs": [],
    }

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "machine": machine_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_machine_refs_missing" in {
        issue["code"] for issue in result["issues"]
    }


def test_high_stakes_contested_projection_records_unreachable_recourse_as_publication_blocker() -> (
    None
):
    projection = build_policy_design_case_projection_semantics(
        policy_design_case={
            **policy_design_case(),
            "contestability_status": "contested",
            "stakes": "high_stakes",
        },
        surface="public_export",
        source_payload={
            "publishability": "publishable",
            "contestability_status": "contested",
            "stakes": "high_stakes",
            "authority_level": "production",
            "decision_context": {"public_export_status": "publishable"},
            "recourse_pointer": {
                "uri": "https://appeals.example.test/pdc/run-24",
                "verification_status": "verified_reachable",
                "verified_at": "2026-05-18T09:30:00Z",
                "verification_ref": "event://recourse/verified",
                "source_kind": "llm_candidate",
            },
        },
        audience=PolicyDesignCaseAudience.PUBLIC,
        generated_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    typed = PolicyDesignCaseProjection.model_validate(projection)

    assert typed.primary_state == "blocked"
    assert "blocked" in typed.states
    assert typed.recourse_pointer is None
    assert {gap.gap_code for gap in typed.projection_gaps} >= {
        "public_export_recourse_pointer_unreachable"
    }
    assert {blocker.code for blocker in typed.closeout_truth.blockers} >= {
        "public_export_recourse_pointer_unreachable"
    }


def test_s9_projection_semantics_reuses_pdc_consumer_contract_for_closeout_truth() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload()

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth=payload["closeout_truth"],
        expected_contested_record_ids=["contest-s8-value-choice"],
    )

    assert result["status"] == "pass"
    assert result["consumer_contract_ref"] == (
        "policyos.runtime.policy_design_case.projection_contract_verification.v1"
    )
    assert result["s9_projection_faithfulness"]["faithfulness_status"] == "pass"


def test_s9_projection_faithfulness_rejects_missing_closeout_blocker() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload(
        closeout_truth={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "blocker_codes": [],
            "omission_codes": ["s9_public_projection_missing_limitation"],
        }
    )

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "blocker_codes": ["s6_strategic_response_blocker"],
            "omission_codes": ["s9_public_projection_missing_limitation"],
        },
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_hides_closeout_blockers" in _issue_codes(result)


def test_s9_projection_faithfulness_rejects_added_public_claim() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload(
        s9_projection_faithfulness=_s9_faithfulness_payload(
            faithfulness_status="fail",
            issue_codes=["s9_projection_added_claim"],
            added_claim_refs=["claim://ua-msme/new-public-benefit-claim"],
        )
    )

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth=payload["closeout_truth"],
    )

    assert result["status"] == "fail"
    assert "s9_projection_added_claim" in _issue_codes(result)


def test_s9_projection_faithfulness_rejects_tradeoff_inversion() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload(
        s9_projection_faithfulness=_s9_faithfulness_payload(
            faithfulness_status="fail",
            issue_codes=["s9_tradeoff_inversion"],
            tradeoff_direction_status="inverted",
        )
    )

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth=payload["closeout_truth"],
    )

    assert result["status"] == "fail"
    assert "s9_tradeoff_inversion" in _issue_codes(result)


def test_s9_projection_faithfulness_rejects_shadow_candidate_as_approved() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload(
        s9_projection_faithfulness=_s9_faithfulness_payload(
            faithfulness_status="fail",
            issue_codes=["s9_shadow_candidate_rendered_as_approved"],
            shadow_approval_status="rendered_as_approved",
        )
    )

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth=payload["closeout_truth"],
    )

    assert result["status"] == "fail"
    assert "s9_shadow_candidate_rendered_as_approved" in _issue_codes(result)


def test_s9_projection_faithfulness_preserves_contested_and_deficit_records() -> None:
    verifier = _s9_consumer_verifier()
    payload = _s9_projection_payload(contested_records=[], deficit_register=[])

    result = verifier(
        projections={"public": payload},
        expected_closeout_truth=payload["closeout_truth"],
        expected_contested_record_ids=["contest-s8-value-choice"],
        expected_deficit_codes=["value_choice_contested"],
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_hides_contested_state" in _issue_codes(result)
    assert "s9_projection_hides_deficit_record" in _issue_codes(result)


def test_s10_projection_semantics_blocks_simulation_only_as_evidence() -> None:
    verifier = projection_semantics_module.verify_s10_forecast_projection_consumer_contract
    payload = _s10_projection_payload(
        forecast_tier="simulation_only_advisory",
        evidence_authority_claimed=True,
        forecast_calibration_record_ref=None,
        calibration_status="not_applicable_non_observable",
    )

    result = verifier(projections={"public": payload})

    assert result["status"] == "fail"
    assert "s10_simulation_only_laundered_as_evidence" in _issue_codes(result)


def test_s10_projection_semantics_preserves_uncertainty_and_boundary() -> None:
    verifier = projection_semantics_module.verify_s10_forecast_projection_consumer_contract
    payload = _s10_projection_payload()

    result = verifier(projections={"machine": {**payload, "audience": "MACHINE"}})

    assert result["status"] == "pass"
    assert result["s10_forecast_projection"]["uncertainty_interval_refs"] == (
        payload["uncertainty_interval_refs"]
    )
    assert result["s10_forecast_projection"]["authority_boundary"] == (
        payload["authority_boundary"]
    )


def test_s10_projection_semantics_blocks_scalar_welfare_tradeoff_hiding() -> None:
    verifier = projection_semantics_module.verify_s10_forecast_projection_consumer_contract
    payload = _s10_projection_payload(
        welfare_comparison={
            "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice",
            "s8_value_tradeoff_disclosure_ref": "pdc://layer2/s8/ua-msme/tradeoff",
            "scalar_summary_allowed": True,
            "scalar_welfare_summary_ref": "welfare://ua-msme/scalar-score",
            "pareto_frontier_ref": None,
            "rejected_nondominated_alternative_refs": [],
        }
    )

    result = verifier(projections={"public": payload})

    assert result["status"] == "fail"
    assert "s10_scalar_welfare_hides_pareto_tradeoff" in _issue_codes(result)


def test_expert_and_machine_projection_surface_s11_confidence_and_residual_limits() -> None:
    verifier = projection_semantics_module.verify_s11_predictive_projection_consumer_contract
    expert = _s11_projection_payload(audience="EXPERT")
    machine = _s11_projection_payload(audience="MACHINE")

    result = verifier(projections={"expert": expert, "machine": machine})

    assert result["status"] == "pass"
    s11_projection = result["s11_predictive_projection"]
    assert s11_projection["predictive_axis_rows"][0]["confidence"] == 0.78
    assert s11_projection["residual_limitation_refs"] == (
        expert["residual_limitation_refs"]
    )
    assert s11_projection["proof_carrying_analytics_ref"] == (
        expert["proof_carrying_analytics_ref"]
    )


def test_reviewer_projection_surfaces_s11_proof_and_calibration_limitations() -> None:
    verifier = projection_semantics_module.verify_s11_predictive_projection_consumer_contract
    payload = _s11_projection_payload(audience="REVIEWER")

    result = verifier(projections={"reviewer": payload})

    assert result["status"] == "pass"
    s11_projection = result["s11_predictive_projection"]
    assert s11_projection["per_axis_predictive_calibration_status"] == "pass"
    assert s11_projection["per_axis_predictive_calibration_threshold_ref"]
    assert s11_projection["proof_carrying_analytics_ref"].startswith("pdc://layer2/s11/")
    assert s11_projection["weakest_boundary_reason"]


def test_public_projection_surfaces_required_s11_limitation_without_authority_promotion() -> None:
    verifier = projection_semantics_module.verify_s11_predictive_projection_consumer_contract
    payload = _s11_projection_payload(audience="PUBLIC")

    result = verifier(projections={"public": payload})

    assert result["status"] == "pass"
    public_projection = result["public_projection"]
    assert public_projection["s11_public_limitation"]
    assert "proof_carrying_analytics_ref" not in public_projection
    assert "production_recommendation" in public_projection["may_not_be_used_for"]
    assert public_projection["authority_role"] == "projection_only"


def test_expert_machine_projection_surfaces_explore_exploit_and_thermometers() -> None:
    verifier = projection_semantics_module.verify_s12_resource_projection_consumer_contract
    expert = _s12_projection_payload(audience="EXPERT")
    machine = _s12_projection_payload(audience="MACHINE")

    result = verifier(projections={"expert": expert, "machine": machine})

    assert result["status"] == "pass"
    s12_projection = result["s12_resource_projection"]
    assert s12_projection["explore_exploit_posture"] == "balanced_governed"
    assert s12_projection["voi_site_count"] >= 3
    assert len(s12_projection["typed_budget_refs"]) == 5
    assert s12_projection["pareto_archive_ref"] == expert["pareto_archive_ref"]
    assert s12_projection["growth_thermometer_ref"] == expert["growth_thermometer_ref"]
    assert s12_projection["override_rate_trend"] in {"improving", "flat"}
    assert s12_projection["reuse_rate_trend"] in {"improving", "flat"}


def test_projection_semantics_blocks_allocation_as_recommendation_authority() -> None:
    verifier = projection_semantics_module.verify_s12_resource_projection_consumer_contract
    payload = _s12_projection_payload(
        audience="PUBLIC",
        authority_role="recommendation_authority",
        allocation_recommendation_text="Allocate the next budget to the selected option.",
        may_not_be_used_for=[
            "rollout_authority",
            "publication_authority",
            "claim_authority",
        ],
    )

    result = verifier(projections={"public": payload})

    assert result["status"] == "fail"
    assert "s12_allocation_as_recommendation_authority" in _issue_codes(result)


def test_expert_machine_projection_surfaces_attribution_and_envelope_revision() -> None:
    verifier = (
        projection_semantics_module
        .verify_s13_post_deploy_accountability_projection_consumer_contract
    )
    expert = _s13_projection_payload(audience="EXPERT")
    machine = _s13_projection_payload(audience="MACHINE")

    result = verifier(projections={"expert": expert, "machine": machine})

    assert result["status"] == "pass"
    s13_projection = result["s13_post_deploy_accountability_projection"]
    assert s13_projection["attribution_status"] == "attributed"
    assert s13_projection["attribution_classes"] == ["design_error"]
    assert s13_projection["learning_change_control_classes"] == ["reissue_required"]
    assert s13_projection["envelope_revision_direction"] == "shrink"
    assert s13_projection["assurance_case_change"] == "weakened"
    assert s13_projection["replay_digest"].startswith("sha256:")


def test_reviewer_projection_surfaces_mape_k_trace_action_closure_oversight_state_and_existing_reissue_disposition() -> None:
    verifier = (
        projection_semantics_module
        .verify_s13_post_deploy_accountability_projection_consumer_contract
    )
    reviewer = _s13_projection_payload(audience="REVIEWER")

    result = verifier(projections={"reviewer": reviewer})

    assert result["status"] == "pass"
    s13_projection = result["s13_post_deploy_accountability_projection"]
    assert s13_projection["mape_k_trace_ref"] == "mape-k://ua-msme/post-deploy"
    assert s13_projection["action_item_status"] == "closed"
    assert s13_projection["action_item_closure_refs"]
    assert s13_projection["oversight_accountability_state"] == (
        "rubber_stamp_divergence_review_required"
    )
    assert s13_projection["lifecycle_reissue_disposition"] == "reissue_required"


def test_projection_blocks_learning_update_as_current_evidence_authority() -> None:
    verifier = (
        projection_semantics_module
        .verify_s13_post_deploy_accountability_projection_consumer_contract
    )
    payload = _s13_projection_payload(
        audience="MACHINE",
        authority_role="projection_only",
        current_evidence_refs=["learning-proposal://ua-msme/envelope-shrink"],
        may_not_be_used_for=[
            "production_rollout_authority",
            "recommendation_authority",
        ],
    )

    result = verifier(projections={"machine": payload})

    assert result["status"] == "fail"
    assert "s13_learning_update_as_current_evidence_authority" in _issue_codes(result)


def test_projection_blocks_s13_as_universality_or_production_authority() -> None:
    verifier = (
        projection_semantics_module
        .verify_s13_post_deploy_accountability_projection_consumer_contract
    )
    payload = _s13_projection_payload(
        audience="PUBLIC",
        authority_role="production_rollout_authority",
        authority_boundary={
            "authoritative_for": ["s14_universality", "production_rollout_authority"],
            "may_not_use_for": ["publication_authority"],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S13_RULE_VERSION_REF],
        },
    )

    result = verifier(projections={"public": payload})

    assert result["status"] == "fail"
    assert "s13_as_universality_or_production_authority" in _issue_codes(result)
