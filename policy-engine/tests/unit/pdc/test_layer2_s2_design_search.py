from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import polisyos.pdc as pdc
from polisyos.pdc import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    ConstraintStoreEntry,
    ConstraintStoreSnapshot,
    CounterexampleRecord,
    DesignCandidateV0,
    DesignGrammarExpansion,
    DesignRecordV0,
    Layer2S2DesignSearchInput,
    Layer2S2DesignSearchInputError,
    Layer2S5CompositionPostureInput,
    Layer2S6BlindSpotPostureInput,
    RefinementDecision,
    SearchLedger,
    assert_s2_public_projection_has_blind_spot_disclosure,
    assert_s2_public_projection_has_composition_limitation,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIRST_PROVING_CASE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer2_first_proving_case.json"
)
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def _input() -> Layer2S2DesignSearchInput:
    proving_case = json.loads(FIRST_PROVING_CASE_PATH.read_text(encoding="utf-8"))
    return Layer2S2DesignSearchInput(
        schema_version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
        case_id=str(proving_case["case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in proving_case["constructs"]),
        construct_refs=tuple(f"construct://{item}" for item in proving_case["constructs"]),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=NOW,
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )


def _s6_blind_spot_posture(
    *,
    overall_posture: str = "blocked",
    blocking_axis_refs: list[str] | None = None,
    limiting_axis_refs: list[str] | None = None,
    regime_reissue_required: bool = True,
    system_dynamics_handoff_required: bool = True,
) -> Layer2S6BlindSpotPostureInput:
    blocking = (
        blocking_axis_refs
        if blocking_axis_refs is not None
        else [
            "SYSTEM.measurability",
            "OTHER_AGENTS.strategic_response",
        ]
    )
    limiting = (
        limiting_axis_refs
        if limiting_axis_refs is not None
        else [
            "SYSTEM.subject_granularity",
            "ACTOR.state_capacity_feasibility",
            "ACTOR.mandate_legitimacy",
        ]
    )
    axis_rows = [
        {
            "axis": "measurability",
            "cell_ref": "SYSTEM.measurability",
            "record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
            "firewall_pattern_id": "P18",
            "disposition": "block" if "SYSTEM.measurability" in blocking else "limit",
            "decision_reason": "proxy value constructs require disclosure",
        },
        {
            "axis": "subject_granularity",
            "cell_ref": "SYSTEM.subject_granularity",
            "record_ref": "pdc://layer2/s6/ua-msme/aggregation-validity",
            "firewall_pattern_id": "P19",
            "disposition": "limit",
            "decision_reason": "jurisdiction evidence cannot close subgroup targeting claims",
        },
        {
            "axis": "state_capacity_feasibility",
            "cell_ref": "ACTOR.state_capacity_feasibility",
            "record_ref": "pdc://layer2/s6/ua-msme/capacity-feasibility",
            "firewall_pattern_id": "P21",
            "disposition": "limit",
            "decision_reason": "capacity building is required before implementability closure",
        },
        {
            "axis": "mandate_legitimacy",
            "cell_ref": "ACTOR.mandate_legitimacy",
            "record_ref": "pdc://layer2/s6/ua-msme/mandate-legitimacy",
            "firewall_pattern_id": "P22",
            "disposition": "limit",
            "decision_reason": "mandate remains candidate-unverified",
        },
        {
            "axis": "strategic_response",
            "cell_ref": "OTHER_AGENTS.strategic_response",
            "record_ref": "pdc://layer2/s6/ua-msme/strategic-response",
            "firewall_pattern_id": "P24",
            "disposition": (
                "block" if "OTHER_AGENTS.strategic_response" in blocking else "limit"
            ),
            "decision_reason": "Goodhart risk requires post-intervention DGP update",
        },
    ]
    return Layer2S6BlindSpotPostureInput(
        overall_posture=overall_posture,
        measurability_record_ref="pdc://layer2/s6/ua-msme/measurability-adequacy",
        aggregation_validity_record_ref="pdc://layer2/s6/ua-msme/aggregation-validity",
        capacity_feasibility_record_ref="pdc://layer2/s6/ua-msme/capacity-feasibility",
        mandate_legitimacy_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
        strategic_response_record_ref="pdc://layer2/s6/ua-msme/strategic-response",
        cluster_authority_dimension_refs=[
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/aggregation_validity",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/capacity_feasibility",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/mandate_legitimacy",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/strategic_robustness",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/response_model_validity",
        ],
        bridge_consumer_rows=[
            {
                "cell_ref": "SYSTEM.measurability",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "producer_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "block",
            },
            {
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "consumer_ref": "SYSTEM.post_intervention_dgp",
                "producer_ref": "pdc://layer2/s6/ua-msme/strategic-response",
                "disposition": "block",
            },
        ],
        constraint_store_updates=[
            {
                "constraint_id": "layer2.s6.measurability.block",
                "cell_ref": "SYSTEM.measurability",
                "status": "block",
                "source_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "refinement_route": "block_candidate",
                "evidence_refs": ["pdc://layer2/s6/ua-msme/measurability-adequacy"],
                "reason": "proxy value constructs require disclosure",
                "rule_version_ref": "policyos.layer2.s6.blind_spot_firewalls.v1",
            },
            {
                "constraint_id": "layer2.s6.strategic_response.block",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "status": "block",
                "source_ref": "pdc://layer2/s6/ua-msme/strategic-response",
                "consumer_ref": "SYSTEM.post_intervention_dgp",
                "refinement_route": "human_decision",
                "evidence_refs": ["pdc://layer2/s6/ua-msme/strategic-response"],
                "reason": "Goodhart risk requires post-intervention DGP update",
                "rule_version_ref": "policyos.layer2.s6.blind_spot_firewalls.v1",
            },
            {
                "constraint_id": "layer2.s6.value_choice.pending",
                "cell_ref": "ACTOR.mandate_legitimacy",
                "status": "limit",
                "source_ref": "pdc://layer2/s6/ua-msme/mandate-legitimacy",
                "consumer_ref": "ACTOR.value_choice_provenance",
                "refinement_route": "pending_consumer_constraint",
                "evidence_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
                "reason": "S8 value-choice consumer is pending",
                "rule_version_ref": "policyos.layer2.s6.blind_spot_firewalls.v1",
            },
        ],
        c3_authority_dimension_rows=[
            {
                "cell_ref": "SYSTEM.measurability",
                "authority_dimension": "measurability_adequacy",
                "producer_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "block",
            },
            {
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "authority_dimension": "strategic_robustness",
                "producer_ref": "pdc://layer2/s6/ua-msme/strategic-response",
                "disposition": "block",
            },
            {
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "authority_dimension": "response_model_validity",
                "producer_ref": "pdc://layer2/s6/ua-msme/strategic-response",
                "disposition": "block",
            },
        ],
        axis_rows=axis_rows,
        blocking_axis_refs=blocking,
        limiting_axis_refs=limiting,
        post_intervention_dgp_update_ref="pdc://layer2/s6/ua-msme/post-intervention-dgp",
        system_dynamics_handoff_required=system_dynamics_handoff_required,
        regime_reissue_required=regime_reissue_required,
        limitation_summary=(
            "Unmeasured values, aggregation drift, capacity, mandate, and strategic-response "
            "risks limit this shadow design."
        ),
        false_clear_penalty=5.0,
    )


def _delegation_posture(
    *,
    disposition: str = "request_human_decision",
    human_decision_record_ref: str | None = None,
    decision_action_exercised: str | None = None,
    responsibility_integrity_status: str = "limit",
    governed_pilot_eligible: bool = False,
    required_role: str = "policy_design_governance_reviewer",
    actor_ref: str | None = None,
    interaction_mode: str = "request_driven",
    request_ref: str = "pdc://layer2/s7/ua-msme/human-decision-request",
) -> object:
    from polisyos.pdc import Layer2S7DelegationPostureInput

    return Layer2S7DelegationPostureInput(
        delegation_contract_ref="pdc://layer2/s7/ua-msme/delegation-contract",
        decision_rights_matrix_ref="pdc://layer2/s7/ua-msme/decision-rights-matrix",
        human_decision_request_ref=request_ref,
        human_decision_record_ref=human_decision_record_ref,
        decision_class_id="a_spec_gap",
        required_role=required_role,
        interaction_mode=interaction_mode,
        disposition=disposition,
        available_actions=[
            "request_evidence",
            "approve",
            "reject",
            "revise_scope",
            "escalate",
        ],
        decision_action_exercised=decision_action_exercised,
        five_rights_requirement={
            "right_decision": "Decide the A-side specification gap.",
            "right_person": required_role,
            "right_information": "Evidence, limitations, consequences, and alternatives.",
            "right_format_channel": "reviewer_console",
            "right_time": "before S2 route can still change",
        },
        five_rights_check=(
            {
                "right_decision": True,
                "right_person": required_role == "policy_design_governance_reviewer",
                "right_information": responsibility_integrity_status == "pass",
                "right_format_channel": True,
                "right_time": True,
            }
            if human_decision_record_ref
            else None
        ),
        decision_options=[
            {"option_id": "request_evidence", "action": "request_evidence"},
            {"option_id": "approve_shadow_handoff", "action": "approve"},
        ],
        recommendation_ref="pdc://layer2/s7/ua-msme/recommendation",
        provenance_refs=[
            "pdc://layer2/s2/ua-msme-affordable-loans-2022/refinement/001",
        ],
        material_limitations=[
            "S7 decision refs are closeout-visible but not production authority.",
        ],
        value_stakes_impact="Delegation can route the design but cannot choose social weights.",
        what_changes_under_each_choice=[
            "Approval records a bounded human decision.",
            "Requesting evidence keeps S2 in governance-required posture.",
        ],
        attention_cost_rank=2,
        responsibility_integrity_status=responsibility_integrity_status,
        mandate_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
        s6_mandate_firewall_disposition="pass",
        mandate_source_refs=["legal://ua/msme-credit/2022/mandate"],
        requested_at=NOW,
        decision_due_at=NOW,
        decided_at=NOW if human_decision_record_ref else None,
        actor_ref=actor_ref,
        voi_rank=1,
        need_reasons=["high_stakes", "value_laden"],
        authority_boundary={
            "authoritative_for": [
                "delegation_integrity",
                "human_decision_routing",
            ],
            "may_not_use_for": [
                "production_claim_authority",
                "value_choice_authority",
                "s13_accountability_closure",
            ],
            "source_authority": "human_governance",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s7.delegation.v1"],
        },
        governed_pilot_eligible=governed_pilot_eligible,
        constraint_store_updates=[
            {
                "constraint_id": "layer2.s7.delegation.human_decision",
                "cell_ref": "CROSS_CUTTING.scientist_orchestration",
                "status": "block" if disposition.startswith("blocked_") else "limit",
                "source_ref": request_ref,
                "consumer_ref": "INTERVENTION.design_candidate",
                "refinement_route": "human_decision",
                "evidence_refs": [request_ref],
                "reason": "S7 delegation posture requires typed human decision routing.",
                "rule_version_ref": "policyos.layer2.s7.delegation.v1",
            }
        ],
        handoff_rows=[
            {
                "handoff_id": "layer2.s7.ua-msme.scientist-orchestration",
                "workflow_ref": "scientist://workflow/ua-msme/delegation",
                "source_cell_ref": "CROSS_CUTTING.scientist_orchestration",
                "target_cell_ref": "INTERVENTION.design_candidate",
                "artifact_refs": [
                    "pdc://layer2/s7/ua-msme/delegation-contract",
                    "pdc://layer2/s7/ua-msme/decision-rights-matrix",
                    request_ref,
                ],
                "disposition": "blocked" if disposition.startswith("blocked_") else "emitted",
                "authority_purpose": "mandate_bounded_delegation_handoff",
                "may_not_use_for": [
                    "production_claim_authority",
                    "human_approval_without_decision_record",
                ],
            }
        ],
        limitation_summary="Human decision routing is bounded to S7 delegation integrity.",
    )


def _s8_value_posture(
    *,
    disposition: str = "blocked_missing_value_provenance",
    ranking_mode: str = "ranking_blocked",
    authorized_value_schedule_ref: str | None = None,
    p20_firewall_status: str = "block",
    p22_firewall_status: str = "pass",
    value_provenance_completeness: float = 1.0,
    conflict_rows: list[dict[str, object]] | None = None,
) -> object:
    from polisyos import pdc

    return pdc.Layer2S8ValuePostureInput(
        value_choice_provenance_ref="pdc://layer2/s8/ua-msme/value-choice-provenance",
        authorized_value_schedule_ref=authorized_value_schedule_ref,
        shadow_scenario_value_schedule_refs=[
            "pdc://layer2/s8/ua-msme/value-schedule/shadow-scenario"
        ],
        objective_function_provenance_ref="pdc://layer2/s8/ua-msme/objective-provenance",
        pareto_archive_ref="pdc://layer2/s8/ua-msme/pareto-archive",
        value_tradeoff_disclosure_ref="pdc://layer2/s8/ua-msme/value-tradeoff-disclosure",
        mandate_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
        s6_mandate_firewall_disposition="pass",
        ranking_mode=ranking_mode,
        disposition=disposition,
        p20_firewall_status=p20_firewall_status,
        p22_firewall_status=p22_firewall_status,
        value_provenance_completeness=value_provenance_completeness,
        principal_refs=["principal://ua/ministry-of-economy"],
        conflict_rows=conflict_rows or [],
        affected_group_rows=[
            {
                "group_ref": "group://low-income-msmes",
                "disclosure_ref": "pdc://layer2/s8/ua-msme/affected-groups",
            }
        ],
        dissent_refs=["dissent://ua-msme/sme-panel"],
        blocking_rights_refs=["rights://ua-msme/legal-equality"],
        alternative_schedule_sensitivity=[
            {
                "scenario_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/scenario",
                "selected_alternative_ref": "alternative://cash-transfer",
                "status": "shadow_scenario_only",
            }
        ],
        rejected_nondominated_alternative_ids=["cash_transfer"],
        social_weight_provenance_refs=[
            "foundry://welfare/social-weight-provenance/public-budget-2026"
        ],
        delegation_refs=["pdc://layer2/s7/ua-msme/value-authorization-request"],
        value_authorization_decision_refs=[
            "pdc://layer2/s7/ua-msme/value-authorization-record"
        ],
        constraint_store_updates=[
            {
                "constraint_id": "layer2.s8.value_choice.blocked",
                "cell_ref": "ACTOR.value_choice_provenance",
                "status": "block" if p20_firewall_status == "block" else "limit",
                "source_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
                "consumer_ref": "INTERVENTION.design_candidate",
                "refinement_route": "block_candidate",
                "evidence_refs": [
                    "pdc://layer2/s8/ua-msme/value-choice-provenance",
                    "pdc://layer2/s8/ua-msme/pareto-archive",
                ],
                "reason": "Ranked value choice requires authorized S8 provenance.",
                "rule_version_ref": "policyos.layer2.s8.value_choice.v1",
            }
        ],
        handoff_rows=[
            {
                "handoff_id": "layer2.s8.ua-msme.value-choice",
                "workflow_ref": "scientist://workflow/ua-msme/value-choice",
                "source_cell_ref": "ACTOR.value_choice_provenance",
                "target_cell_ref": "INTERVENTION.design_candidate",
                "artifact_refs": [
                    "pdc://layer2/s8/ua-msme/value-choice-provenance",
                    "pdc://layer2/s8/ua-msme/pareto-archive",
                ],
                "disposition": "blocked" if p20_firewall_status == "block" else "consumed",
                "authority_purpose": "s8_value_choice_firewall",
                "may_not_use_for": [
                    "production_recommendation",
                    "preference_learning_authority",
                    "s9_projection_maturity",
                ],
            }
        ],
        limitation_summary=(
            "Frontier facts are visible, but ranked value choices require an "
            "authorized value schedule."
        ),
        authority_boundary={
            "authoritative_for": [
                "value_choice_provenance",
                "shadow_design_search_replay",
            ],
            "may_not_use_for": [
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "scalar_welfare_authority",
                "preference_learning_authority",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s8.value_choice.v1"],
        },
    )


def _s10_forecast_posture(**overrides: object) -> object:
    posture_model = pdc.Layer2S10ForecastPostureInput
    payload: dict[str, object] = {
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "forecast_tier": "observable_calibrated",
        "forecast_authority_disposition_reason": (
            "Observable subset calibration supports bounded forecast posture."
        ),
        "forecast_support_label": "validated_local_dynamic_model",
        "forecast_calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "candidate_design_ref": "candidate://ua-msme/targeted-credit",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "prediction_horizon_ref": "horizon://12-months",
        "observable_subset_ref": "pdc://layer2/s10/ua-msme/observable-subset",
        "uncertainty_interval_refs": ["interval://ua-msme/credit-access/95"],
        "welfare_comparison_ref": "pdc://layer2/s10/ua-msme/welfare-comparison",
        "s5_forecast_support_ref": "pdc://layer2/s5/ua-msme/system-effect-support",
        "s6_firewall_status_refs": [
            "pdc://layer2/s6/ua-msme/measurability-adequacy",
            "pdc://layer2/s6/ua-msme/strategic-response",
        ],
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice",
        "s8_value_tradeoff_disclosure_ref": "pdc://layer2/s8/ua-msme/tradeoff",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "dynamic_equilibrium_check_ref": "equilibrium-check://ua-msme/system-effect",
        "sensitivity_analysis_ref": "sensitivity://ua-msme/credit-access",
        "authority_boundary": {
            "authoritative_for": [
                "forecast_support_tiering",
                "observable_subset_calibration",
            ],
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
            "rule_version_refs": ["policyos.layer2.s10.outcome_prediction.v1"],
        },
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "s11_calibration",
        ],
        "rule_version_ref": "policyos.layer2.s10.outcome_prediction.v1",
    }
    payload.update(overrides)
    return posture_model(**payload)


def _s11_predictive_posture(**overrides: object) -> object:
    posture_model = pdc.Layer2S11PredictivePostureInput
    payload: dict[str, object] = {
        "predictive_knowledge_ref": "pdc://layer2/s11/ua-msme/predictive-knowledge",
        "effective_predictive_posture": "limited_by_weakest_boundary",
        "axis_upgrade_refs": [
            "pdc://layer2/s11/ua-msme/upgrade/measurability",
            "pdc://layer2/s11/ua-msme/upgrade/strategic-response",
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
        "proof_carrying_analytics_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "s10_forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "s10_forecast_tier": "observable_calibrated",
        "s6_floor_status_refs": [
            "pdc://layer2/s6/ua-msme/measurability-adequacy",
            "pdc://layer2/s6/ua-msme/strategic-response",
        ],
        "s6_axis_rows": [
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            },
            {
                "axis": "strategic_response",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "record_ref": "pdc://layer2/s6/ua-msme/strategic-response",
                "disposition": "block",
            },
        ],
        "s6_bridge_consumer_rows": [
            {
                "cell_ref": "SYSTEM.measurability",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "producer_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            }
        ],
        "s6_constraint_store_update_refs": [
            "constraint://s6/measurability",
            "constraint://s6/strategic-response",
        ],
        "s6_c3_authority_dimension_refs": [
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy",
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/strategic_robustness",
        ],
        "post_intervention_dgp_update_ref": "pdc://layer2/s6/ua-msme/post-intervention-dgp",
        "system_dynamics_handoff_required": True,
        "s11_calibration_record_refs": [
            "pdc://layer2/s11/ua-msme/calibration/measurability",
            "pdc://layer2/s11/ua-msme/calibration/strategic-response",
        ],
        "method_infrastructure_refs": ["foundry://methods/calibration/local-causal"],
        "forecast_quality_disposition": "downgraded_by_s11_calibration",
        "regime_strategy_constraint_ref": "constraint://s11/regime/strategic-response",
        "residual_limitation_refs": [
            "limitation://s11/strategic-response/fail-closed",
            "limitation://s11/calibration/stale",
        ],
        "per_axis_predictive_calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        "per_axis_predictive_calibration_denominator": 4,
        "per_axis_predictive_calibration_numerator": 3,
        "per_axis_predictive_calibration_pass_rate": 0.75,
        "per_axis_predictive_calibration_status": "pass",
        "weakest_boundary_reason": "strategic_response remains fail_closed under S6.",
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
                "rich_simulation_authority",
                "s12_envelope_growth",
                "s13_accountability_closure",
                "s14_universality",
                "mandate_legitimacy_predictive_upgrade",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s11.predictive_knowledge.v1"],
        },
        "may_not_use_for": [
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "rich_simulation_authority",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
            "mandate_legitimacy_predictive_upgrade",
        ],
        "rule_version_ref": "policyos.layer2.s11.predictive_knowledge.v1",
    }
    payload.update(overrides)
    return posture_model(**payload)


def test_s2_shadow_loop_emits_grammar_candidate_counterexample_refinement_and_record() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert isinstance(run.grammar_expansion, DesignGrammarExpansion)
    assert isinstance(run.candidates[0], DesignCandidateV0)
    assert isinstance(run.constraint_store, ConstraintStoreSnapshot)
    assert isinstance(run.counterexamples[0], CounterexampleRecord)
    assert isinstance(run.refinement_decisions[0], RefinementDecision)
    assert isinstance(run.search_ledger, SearchLedger)
    assert isinstance(run.design_record, DesignRecordV0)
    assert run.status == "shadow_ready"
    assert run.search_ledger.counterexample_conversion_rate == 1.0
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert run.design_record.projection_status == "shadow"
    assert run.design_record.candidate_ref == run.candidates[0].candidate_ref
    assert run.design_record.ledger_refs == [run.search_ledger.ledger_ref]
    assert run.design_record.axis_positions
    assert run.design_record.firewall_status
    assert run.search_ledger.counterexample_refs == [run.counterexamples[0].counterexample_ref]
    assert run.search_ledger.refinement_decision_refs == [run.refinement_decisions[0].decision_ref]
    assert run.refinement_decisions[0].value_of_information.estimate_id == (
        "s2_shadow_refinement_voi"
    )
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for


def test_s2_candidate_is_derived_from_grammar_before_candidate_emission() -> None:
    run = run_s2_shadow_design_loop(_input())

    candidate = run.candidates[0]
    assert candidate.grammar_expansion_ref == run.grammar_expansion.expansion_ref
    assert candidate.source_authority == "deterministic_producer"
    assert candidate.field_source_classification["instrument_family"] == "deterministic_grammar"
    assert candidate.field_source_classification["parameterization"] == "deterministic_grammar"
    assert run.grammar_expansion.instrument_families[:2] == [
        "credit_guarantee",
        "interest_rate_buydown",
    ]
    assert "cash_grant" in run.grammar_expansion.instrument_families


def test_s2_counterexample_classes_are_governed_and_typed() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert set(run.search_ledger.counterexample_class_vocabulary) == {
        "real_design_blocker",
        "substrate_gap",
        "a_spec_gap",
        "abstraction_gap",
        "value_gap",
        "budget_gap",
    }
    assert {record.counterexample_class for record in run.counterexamples} == {
        "real_design_blocker"
    }
    assert run.counterexamples[0].diagnostic.severity == "block"
    assert run.counterexamples[0].diagnostic.authority_purpose == "shadow_design_search_replay"


def test_constraint_store_snapshot_carries_typed_constraint_records() -> None:
    entry = ConstraintStoreEntry(
        constraint_id="layer2.s6.measurability.block",
        cell_ref="SYSTEM.measurability",
        status="block",
        source_ref="pdc://layer2/s6/ua-msme/measurability-adequacy",
        consumer_ref="KNOWLEDGE.epistemic_regime",
        refinement_route="block_candidate",
        evidence_refs=["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        reason="proxy value constructs require disclosure",
        rule_version_ref="policyos.layer2.s6.blind_spot_firewalls.v1",
    )
    snapshot = ConstraintStoreSnapshot(
        snapshot_id="layer2.s2.constraints.ua_msme",
        snapshot_ref="pdc://layer2/s2/ua-msme/constraint-store",
        grammar_expansion_ref="pdc://layer2/s2/ua-msme/grammar-expansion",
        constraint_ids=["shadow_only", entry.constraint_id],
        hard_constraint_ids=[entry.constraint_id],
        governance_owned_gap_ids=[],
        constraint_records=[entry],
    )

    assert snapshot.constraint_records == [entry]
    assert snapshot.constraint_records[0].refinement_route == "block_candidate"


def test_constraint_store_snapshot_rejects_extra_constraint_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        ConstraintStoreEntry(
            constraint_id="layer2.s6.bad",
            cell_ref="SYSTEM.measurability",
            status="block",
            source_ref="pdc://layer2/s6/ua-msme/measurability-adequacy",
            consumer_ref="KNOWLEDGE.epistemic_regime",
            refinement_route="block_candidate",
            evidence_refs=[],
            reason="bad payload",
            rule_version_ref="policyos.layer2.s6.blind_spot_firewalls.v1",
            unexpected="not allowed",
        )


def test_s2_a_spec_gap_routes_to_governance_not_self_repair() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "a_spec_gap"})
    )

    assert run.status == "governance_required"
    assert run.refinement_decisions[0].decision == "human_decision"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.refinement_decisions[0].governance_decision_class_ref == "a_spec_gap"
    assert run.refinement_decisions[0].governance_decision_class is not None
    assert "governance://layer2/s2/a_spec_gap" in run.refinement_decisions[0].governance_refs


def test_s2_substrate_gap_requests_acquisition_without_claiming_acquisition() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "substrate_gap"})
    )

    assert run.status == "acquisition_required"
    assert run.refinement_decisions[0].decision == "acquire"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert "acquisition_authority" in run.design_record.authority_boundary.may_not_use_for


def test_s2_budget_gap_abstains_with_honest_search_incompleteness() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "budget_gap"})
    )

    assert run.status == "abstained"
    assert run.refinement_decisions[0].decision == "abstain"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert "best_known_shadow_frontier" in run.search_ledger.search_incompleteness_note
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for


def test_s2_blocked_candidate_cannot_be_retried_into_pass_without_new_grammar() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"force_retry_same_candidate": True})
    )

    assert run.status == "blocked"
    assert run.refinement_decisions[0].decision == "block_candidate"
    assert run.search_ledger.no_retry_without_new_grammar is True
    assert run.search_ledger.iterations[-1].status == "blocked_no_retry"


def test_s2_llm_only_candidate_without_grammar_derivation_fails_p15() -> None:
    with pytest.raises(
        Layer2S2DesignSearchInputError,
        match="llm_candidate requires grammar_expansion_ref and remains shadow-only",
    ):
        run_s2_shadow_design_loop(
            _input().model_copy(
                update={
                    "candidate_source_authority": "llm_candidate",
                    "omit_grammar_derivation": True,
                }
            )
        )


def test_s2_replay_key_is_deterministic_for_same_input() -> None:
    first = run_s2_shadow_design_loop(_input())
    second = run_s2_shadow_design_loop(_input())

    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_s2_machine_and_reviewer_projection_expose_trace_without_authority() -> None:
    run = run_s2_shadow_design_loop(_input())

    projections = project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))

    assert set(projections) == {"MACHINE", "REVIEWER"}
    assert projections["MACHINE"]["search_ledger_ref"] == run.search_ledger.ledger_ref
    assert projections["MACHINE"]["grammar_diversity_minimum"] == 3
    assert projections["REVIEWER"]["counterexample_conversion_rate"] == 1.0
    assert "best_known_shadow_frontier" in projections["REVIEWER"]["search_incompleteness_note"]
    assert (
        "publication_authority" in projections["REVIEWER"]["authority_boundary"]["may_not_use_for"]
    )


def test_injected_regime_recorded_on_record_without_self_classification() -> None:
    pure_s2 = run_s2_shadow_design_loop(_input())
    assert pure_s2.candidates[0].regime is None
    assert pure_s2.design_record.envelope.epistemic_regime_scopes == ["ignorance"]

    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )

    candidate = run.candidates[0]
    assert candidate.regime == "uncertainty"
    assert candidate.design_strategy == "robust_satisficing"
    assert candidate.commitment_profile_ref == "pdc://layer2/s4/commitment/ua-msme"
    assert candidate.commitment_stakes == "high"
    assert run.design_record.envelope.epistemic_regime_scopes == ["uncertainty"]
    axis_by_cell = {position.cell_ref: position for position in run.design_record.axis_positions}
    assert axis_by_cell["KNOWLEDGE.epistemic_regime"].position == "uncertainty"
    assert axis_by_cell["KNOWLEDGE.epistemic_regime"].evidence_refs == [
        "pdc://layer2/s4/claim/ua-msme/regime"
    ]
    assert "INTERVENTION.reversibility_lifecycle_stakes" in axis_by_cell
    firewall_by_cell = {status.cell_ref: status for status in run.design_record.firewall_status}
    assert "P16" in firewall_by_cell["KNOWLEDGE.epistemic_regime"].pattern_ids
    assert "P23" in firewall_by_cell["INTERVENTION.reversibility_lifecycle_stakes"].pattern_ids
    assert "pdc://layer2/s4/claim/ua-msme/regime" in run.design_record.ledger_refs
    assert "pdc://layer2/s4/commitment/ua-msme" in run.design_record.ledger_refs


def test_four_audience_surface_renders_regime() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )

    projections = project_s2_design_search(
        run,
        audiences=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"),
    )

    assert set(projections) == {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"}
    for projection in projections.values():
        assert projection["regime"] == "uncertainty"
        assert projection["design_strategy"] == "robust_satisficing"
    assert "limitation" in projections["PUBLIC"]
    assert "risk-regime authority" in projections["PUBLIC"]["limitation"]
    assert "evidence_basis_ref" not in projections["PUBLIC"]
    assert projections["REVIEWER"]["p16_firewall_status"] == "limit"
    assert projections["EXPERT"]["evidence_basis_ref"] == "pdc://layer2/s4/claim/ua-msme/regime"
    assert projections["EXPERT"]["commitment_profile_ref"] == ("pdc://layer2/s4/commitment/ua-msme")
    assert projections["EXPERT"]["stakes_band"] == "high"
    assert projections["EXPERT"]["selected_floor"] == "standard"
    assert projections["MACHINE"]["p23_firewall_status"] == "limit"


def test_public_projection_dropping_limitation_fails() -> None:
    from polisyos.pdc._impl.layer2_design_search import (
        assert_s2_public_projection_has_regime_limitation,
    )

    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )
    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]
    assert_s2_public_projection_has_regime_limitation(public_projection)

    broken_projection = dict(public_projection)
    broken_projection.pop("limitation")
    with pytest.raises(ValueError, match="PUBLIC regime projection requires limitation"):
        assert_s2_public_projection_has_regime_limitation(broken_projection)


def test_precautionary_strategy_blocks_point_optimization_refinement() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "abstraction_gap"}),
        regime="ignorance",
        design_strategy="precautionary_adaptive_pathway",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="catastrophic",
    )

    decision = run.refinement_decisions[0]
    assert decision.decision == "reframe"
    assert decision.next_candidate_ref is None
    assert decision.stakes_band == "high_stakes"
    assert "precautionary_adaptive_pathway" in decision.reason


def test_s2_persists_design_record_and_search_ledger(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)

    assert refs["design_record"].kind == "policyos.layer2_s2.design_record_v0"
    assert refs["search_ledger"].kind == "policyos.layer2_s2.search_ledger"
    assert refs["design_record"].media_type == "application/json"
    assert refs["search_ledger"].media_type == "application/json"
    design_record = json.loads(store.get_bytes(refs["design_record"].artifact_id))
    search_ledger = json.loads(store.get_bytes(refs["search_ledger"].artifact_id))
    assert design_record["record_id"] == run.design_record.record_id
    assert search_ledger["deterministic_replay_key"] == (run.search_ledger.deterministic_replay_key)


def test_s2_loaded_ledger_replays_same_key(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import load_s2_search_ledger, persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)
    loaded = load_s2_search_ledger(store=store, artifact_ref=refs["search_ledger"])

    assert loaded == run.search_ledger


def test_injected_composition_recorded_on_record_without_self_decomposition() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="near_decomposable",
            boundary_coupling_rows=[
                {
                    "boundary_ref": "boundary://credit/fiscal",
                    "source_module_ref": "module://credit-program-enrollment",
                    "target_module_ref": "module://fiscal-burden-per-beneficiary",
                    "coupling_regime": "near_decomposable",
                    "feedback_intensity": "weak",
                }
            ],
            composition_disposition="compose_with_limitations",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="transported_with_heavy_limitation",
            critical_path_module_refs=[
                "module://credit-program-enrollment",
                "module://fiscal-burden-per-beneficiary",
            ],
            residual_interaction_risk="medium",
        ),
    )

    candidate = run.candidates[0]
    assert candidate.coupling_regime == "near_decomposable"
    assert candidate.composition_disposition == "compose_with_limitations"
    assert "pdc://layer2/s5/ua-msme/coupling-graph" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/module-discovery" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/decomposition-result" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/composition-receipt" in run.design_record.ledger_refs
    assert "pdc://layer2/s5/ua-msme/tractability-budget" in run.design_record.ledger_refs

    axis_by_cell = {axis.cell_ref: axis for axis in run.design_record.axis_positions}
    firewall_by_cell = {fw.cell_ref: fw for fw in run.design_record.firewall_status}
    assert axis_by_cell["SYSTEM.connectivity_modularity"].position == "near_decomposable"
    assert axis_by_cell["INTERVENTION.scale_composition"].position.startswith(
        "composition_disposition=compose_with_limitations"
    )
    assert "P17" in firewall_by_cell["SYSTEM.connectivity_modularity"].pattern_ids
    assert "P17" in firewall_by_cell["INTERVENTION.scale_composition"].pattern_ids


def test_s2_shadow_loop_does_not_import_or_call_s5_classifier() -> None:
    import inspect

    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "layer2_coupling_composition" not in source
    assert "classify_coupling" not in source
    assert "decompose_design" not in source


def test_four_audience_surface_renders_composition_posture() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="near_decomposable",
            boundary_coupling_rows=[
                {
                    "boundary_ref": "boundary://credit/fiscal",
                    "source_module_ref": "module://credit",
                    "target_module_ref": "module://fiscal",
                    "coupling_regime": "near_decomposable",
                    "feedback_intensity": "weak",
                }
            ],
            composition_disposition="compose_with_limitations",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="transported_with_heavy_limitation",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="medium",
        ),
    )

    projections = project_s2_design_search(
        run,
        audiences=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"),
    )

    for projection in projections.values():
        assert projection["coupling_regime"] == "near_decomposable"
        assert projection["composition_disposition"] == "compose_with_limitations"
        assert "whole-design authority" in projection["composition_limitation"]

    assert projections["PUBLIC"]["composition_limitation"]
    assert projections["REVIEWER"]["p17_firewall_status"] == "limit"
    assert projections["EXPERT"]["coupling_graph_ref"] == "pdc://layer2/s5/ua-msme/coupling-graph"
    assert (
        projections["EXPERT"]["boundary_coupling_rows"][0]["boundary_ref"]
        == "boundary://credit/fiscal"
    )
    assert projections["EXPERT"]["forecast_support_label"] == (
        "transported_with_heavy_limitation"
    )
    assert projections["MACHINE"]["critical_path_module_refs"] == [
        "module://credit",
        "module://fiscal",
    ]


def test_public_composition_projection_requires_limitation() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="entangled",
            composition_disposition="system_evidence_required",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="simulation_only_system_effect",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="high",
        ),
    )
    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]
    assert_s2_public_projection_has_composition_limitation(public_projection)
    broken_projection = dict(public_projection)
    broken_projection["composition_limitation"] = ""

    with pytest.raises(ValueError, match="PUBLIC composition projection requires limitation"):
        assert_s2_public_projection_has_composition_limitation(broken_projection)


def test_entangled_composition_routes_refinement_to_decompose_not_point_optimize() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
        composition_posture=Layer2S5CompositionPostureInput(
            coupling_regime="entangled",
            composition_disposition="system_evidence_required",
            coupling_graph_ref="pdc://layer2/s5/ua-msme/coupling-graph",
            module_discovery_ref="pdc://layer2/s5/ua-msme/module-discovery",
            decomposition_result_ref="pdc://layer2/s5/ua-msme/decomposition-result",
            composition_receipt_ref="pdc://layer2/s5/ua-msme/composition-receipt",
            dynamics_requirement_ref="pdc://layer2/s5/ua-msme/system-dynamics-requirement",
            tractability_budget_ref="pdc://layer2/s5/ua-msme/tractability-budget",
            forecast_support_label="simulation_only_system_effect",
            critical_path_module_refs=["module://credit", "module://fiscal"],
            residual_interaction_risk="high",
        ),
    )

    assert run.refinement_decisions[0].decision in {"decompose", "reframe", "human_decision"}
    assert run.refinement_decisions[0].decision != "refine"


def test_injected_s6_blind_spot_posture_recorded_without_b_side_self_classification() -> None:
    pure_s2 = run_s2_shadow_design_loop(_input())
    assert not any(
        status.cell_ref == "SYSTEM.measurability" for status in pure_s2.design_record.firewall_status
    )

    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    axis_by_cell = {axis.cell_ref: axis for axis in run.design_record.axis_positions}
    firewall_by_cell = {fw.cell_ref: fw for fw in run.design_record.firewall_status}
    assert axis_by_cell["SYSTEM.measurability"].position == "block"
    assert axis_by_cell["OTHER_AGENTS.strategic_response"].position == "block"
    assert "P18" in firewall_by_cell["SYSTEM.measurability"].pattern_ids
    assert "P24" in firewall_by_cell["OTHER_AGENTS.strategic_response"].pattern_ids
    assert run.blind_spot_posture == _s6_blind_spot_posture()
    assert "pdc://layer2/s6/ua-msme/measurability-adequacy" in run.design_record.ledger_refs
    assert "pdc://layer2/s6/ua-msme/strategic-response" in run.design_record.ledger_refs


def test_four_audience_surface_renders_s6_fail_closed_posture() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    projections = project_s2_design_search(
        run,
        audiences=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"),
    )

    assert set(projections) == {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"}
    assert "BlindSpotOverallPosture" not in projections["PUBLIC"]
    assert "overall_posture" not in projections["PUBLIC"]
    assert projections["REVIEWER"]["s6_overall_posture"] == "blocked"
    assert set(projections["REVIEWER"]["s6_pattern_ids"]) == {"P18", "P19", "P21", "P22", "P24"}
    assert projections["EXPERT"]["s6_record_refs"]["strategic_response"] == (
        "pdc://layer2/s6/ua-msme/strategic-response"
    )
    assert projections["MACHINE"]["s6_axis_rows"][0]["cell_ref"] == "SYSTEM.measurability"


def test_public_projection_discloses_unmeasured_values_and_feasibility_limits() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert_s2_public_projection_has_blind_spot_disclosure(public_projection)
    disclosure = public_projection["blind_spot_disclosure"]
    assert "Unmeasured values" in disclosure
    assert "capacity" in disclosure
    assert "mandate" in disclosure
    assert "strategic-response" in disclosure


def test_s6_blocking_axis_routes_refinement_to_reframe_or_acquire_not_point_optimize() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    assert run.status in {"blocked", "governance_required", "acquisition_required"}
    assert run.refinement_decisions[0].decision in {
        "block_candidate",
        "acquire",
        "reframe",
        "human_decision",
    }
    assert run.refinement_decisions[0].decision != "refine"


def test_s6_constraints_written_to_constraint_store_snapshot() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    constraint_ids = {entry.constraint_id for entry in run.constraint_store.constraint_records}
    assert "layer2.s6.measurability.block" in constraint_ids
    assert "layer2.s6.strategic_response.block" in constraint_ids
    assert "layer2.s6.measurability.block" in run.constraint_store.hard_constraint_ids


def test_s6_constraint_records_are_typed_not_projection_only() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    assert all(isinstance(entry, ConstraintStoreEntry) for entry in run.constraint_store.constraint_records)
    assert {
        entry.refinement_route for entry in run.constraint_store.constraint_records
    } >= {"block_candidate", "human_decision", "pending_consumer_constraint"}


def test_s6_cluster_authority_dimension_refs_enter_certified_envelope() -> None:
    posture = _s6_blind_spot_posture()
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=posture)

    assert run.design_record.envelope.cluster_authority_dimension_refs == (
        posture.cluster_authority_dimension_refs
    )


def test_blocking_s6_dimension_prevents_closeout_authority_composition() -> None:
    run = run_s2_shadow_design_loop(_input(), blind_spot_posture=_s6_blind_spot_posture())

    assert "closeout_authority_blocked_by_s6" in run.design_record.envelope.not_certified_for
    assert "production_closeout_authority" in run.design_record.authority_boundary.may_not_use_for


def test_s6_regime_reissue_constraint_caps_strategy_without_rerunning_s4() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="risk",
        design_strategy="expected_welfare_optimization",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="low",
        blind_spot_posture=_s6_blind_spot_posture(regime_reissue_required=True),
    )

    reviewer_projection = project_s2_design_search(run, audiences=("REVIEWER",))["REVIEWER"]
    assert reviewer_projection["regime"] == "risk"
    assert reviewer_projection["s6_regime_reissue_required"] is True
    assert reviewer_projection["s6_strategy_cap"] == "strategy_limited_until_s4_reissue"


def test_pdc_exports_s6_posture_and_constraint_store_entry() -> None:
    import polisyos.pdc as pdc

    assert pdc.Layer2S6BlindSpotPostureInput is Layer2S6BlindSpotPostureInput
    assert pdc.ConstraintStoreEntry is ConstraintStoreEntry


def test_pdc_does_not_import_layer2_blind_spot_firewalls() -> None:
    import inspect

    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "layer2_blind_spot_firewalls" not in source
    assert "evaluate_measurability" not in source
    assert "evaluate_aggregation" not in source
    assert "evaluate_capacity" not in source
    assert "evaluate_mandate" not in source
    assert "evaluate_strategic_response" not in source


def test_s2_consumes_s7_delegation_posture_and_pauses_for_human_request() -> None:
    input_row = _input()
    posture = _delegation_posture(disposition="request_human_decision")

    run = run_s2_shadow_design_loop(input_row, delegation_posture=posture)

    assert run.delegation_posture == posture
    assert run.status == "governance_required"
    assert any(
        record.cell_ref == "CROSS_CUTTING.scientist_orchestration"
        and record.refinement_route == "human_decision"
        for record in run.constraint_store.constraint_records
    )
    assert posture.human_decision_request_ref in run.design_record.ledger_refs


def test_s2_consumes_valid_s7_human_decision_without_production_authority() -> None:
    posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        governed_pilot_eligible=True,
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )

    run = run_s2_shadow_design_loop(
        _input(),
        blind_spot_posture=_s6_blind_spot_posture(
            overall_posture="clear_fail_closed",
            blocking_axis_refs=[],
            limiting_axis_refs=[],
            regime_reissue_required=False,
            system_dynamics_handoff_required=False,
        ),
        delegation_posture=posture,
    )

    assert run.delegation_posture == posture
    assert run.design_record.projection_status == "shadow"
    assert "production_closeout_authority" in run.design_record.authority_boundary.may_not_use_for
    assert posture.human_decision_record_ref in run.search_ledger.delegation_record_refs
    assert posture.human_decision_record_ref in run.design_record.ledger_refs


def test_s2_s7_wrong_role_record_blocks_self_approval() -> None:
    posture = _delegation_posture(
        disposition="blocked_wrong_role",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/wrong-role-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="block",
        required_role="technical_reviewer",
        actor_ref="principal://ua/technical-reviewer",
    )

    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)

    assert run.status in {"blocked", "governance_required"}
    assert any(
        record.cell_ref == "CROSS_CUTTING.scientist_orchestration" and record.status == "block"
        for record in run.constraint_store.constraint_records
    )
    assert run.search_ledger.delegation_status == "blocked"


def test_s2_s7_public_projection_is_decision_shaped_pull_first() -> None:
    posture = _delegation_posture(disposition="request_human_decision")
    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert public_projection["human_decision_needed"] is True
    assert public_projection["accountable_role"] == "policy_design_governance_reviewer"
    assert set(public_projection["available_decision_actions"]) == {
        "request_evidence",
        "approve",
        "reject",
        "revise_scope",
        "escalate",
    }
    assert public_projection["delegation_limitation"]
    assert "blocked_oversight_theater" not in json.dumps(public_projection)
    assert "s7_disposition" not in public_projection


def test_s2_s7_search_ledger_and_closeout_payload_include_decision_record_refs() -> None:
    posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )

    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)
    payload = run.model_dump(mode="json")

    assert posture.human_decision_request_ref in run.search_ledger.delegation_request_refs
    assert posture.human_decision_record_ref in run.search_ledger.delegation_record_refs
    assert posture.human_decision_record_ref in payload["design_record"]["ledger_refs"]
    assert (
        "production_claim_authority"
        in payload["design_record"]["authority_boundary"]["may_not_use_for"]
    )


def test_s2_s7_persisted_search_ledger_round_trips_delegation_refs(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import load_s2_search_ledger, persist_s2_design_search_run

    posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )
    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)

    loaded = load_s2_search_ledger(store=store, artifact_ref=refs["search_ledger"])

    assert loaded.delegation_request_refs == [posture.human_decision_request_ref]
    assert loaded.delegation_record_refs == [posture.human_decision_record_ref]
    assert loaded.delegation_status == "recorded"


def test_s2_s7_search_ledger_defaults_preserve_legacy_cas_payloads() -> None:
    legacy_payload = run_s2_shadow_design_loop(_input()).search_ledger.model_dump(mode="json")
    legacy_payload.pop("delegation_request_refs", None)
    legacy_payload.pop("delegation_record_refs", None)
    legacy_payload.pop("cluster_handoff_refs", None)
    legacy_payload.pop("delegation_status", None)

    loaded = SearchLedger.model_validate(legacy_payload)

    assert loaded.delegation_request_refs == []
    assert loaded.delegation_record_refs == []
    assert loaded.cluster_handoff_refs == []
    assert loaded.delegation_status == "not_applicable"


def test_s2_s7_replay_key_unchanged_without_delegation_posture() -> None:
    first = run_s2_shadow_design_loop(_input())
    second = run_s2_shadow_design_loop(_input())

    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.search_ledger.delegation_request_refs == []
    assert first.search_ledger.delegation_status == "not_applicable"


def test_s2_s7_replay_key_changes_when_delegation_record_changes() -> None:
    first = run_s2_shadow_design_loop(
        _input(),
        delegation_posture=_delegation_posture(
            disposition="recorded_valid_decision",
            human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record-a",
            decision_action_exercised="approve",
            responsibility_integrity_status="pass",
            actor_ref="principal://ua/policy-design-governance-reviewer",
        ),
    )
    second = run_s2_shadow_design_loop(
        _input(),
        delegation_posture=_delegation_posture(
            disposition="recorded_valid_decision",
            human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record-b",
            decision_action_exercised="revise_scope",
            responsibility_integrity_status="pass",
            actor_ref="principal://ua/policy-design-governance-reviewer",
        ),
    )

    assert first.search_ledger.deterministic_replay_key != (
        second.search_ledger.deterministic_replay_key
    )


def test_s2_s7_reviewer_projection_shows_p26_and_role_status() -> None:
    posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )
    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)

    reviewer_projection = project_s2_design_search(run, audiences=("REVIEWER",))["REVIEWER"]

    assert reviewer_projection["s7_decision_class_id"] == "a_spec_gap"
    assert reviewer_projection["s7_required_role"] == "policy_design_governance_reviewer"
    assert reviewer_projection["s7_interaction_mode"] == "request_driven"
    assert reviewer_projection["s7_p26_firewall_status"] == "pass"
    assert reviewer_projection["s7_decision_action_exercised"] == "approve"


def test_s2_s7_expert_machine_projection_contains_refs_matrix_and_integrity() -> None:
    posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )
    run = run_s2_shadow_design_loop(_input(), delegation_posture=posture)

    projections = project_s2_design_search(run, audiences=("EXPERT", "MACHINE"))

    for projection in projections.values():
        assert projection["delegation_contract_ref"] == posture.delegation_contract_ref
        assert projection["decision_rights_matrix_ref"] == posture.decision_rights_matrix_ref
        assert projection["human_decision_request_ref"] == posture.human_decision_request_ref
        assert projection["human_decision_record_ref"] == posture.human_decision_record_ref
        assert projection["decision_rights_matrix_row"]["required_role"] == posture.required_role
        assert projection["responsibility_integrity_check"]["status"] == "pass"
        assert projection["authority_boundary"]["may_not_use_for"]


def test_s2_s7_governed_pilot_requires_s6_mandate_and_s7_valid_record() -> None:
    valid_posture = _delegation_posture(
        disposition="recorded_valid_decision",
        human_decision_record_ref="pdc://layer2/s7/ua-msme/human-decision-record",
        decision_action_exercised="approve",
        responsibility_integrity_status="pass",
        governed_pilot_eligible=True,
        actor_ref="principal://ua/policy-design-governance-reviewer",
    )
    valid_run = run_s2_shadow_design_loop(
        _input(),
        blind_spot_posture=_s6_blind_spot_posture(
            overall_posture="clear_fail_closed",
            blocking_axis_refs=[],
            limiting_axis_refs=[],
            regime_reissue_required=False,
            system_dynamics_handoff_required=False,
        ),
        delegation_posture=valid_posture,
    )
    blocked_run = run_s2_shadow_design_loop(
        _input(),
        blind_spot_posture=_s6_blind_spot_posture(),
        delegation_posture=valid_posture,
    )

    valid_projection = project_s2_design_search(valid_run, audiences=("MACHINE",))["MACHINE"]
    blocked_projection = project_s2_design_search(blocked_run, audiences=("MACHINE",))["MACHINE"]

    assert valid_run.delegation_posture.governed_pilot_eligible is True
    assert valid_projection["governed_pilot_eligible"] is True
    assert blocked_projection["governed_pilot_eligible"] is False
    assert valid_run.design_record.projection_status == "shadow"


def test_s2_does_not_import_s7_runtime_quality_producer() -> None:
    import inspect

    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "layer2_delegation" not in source
    assert "build_decision_rights_matrix" not in source
    assert "record_human_decision" not in source
    assert "evaluate_delegation_for_case" not in source


def test_s2_consumes_s8_value_posture_and_blocks_ranking_without_authorized_schedule() -> None:
    posture = _s8_value_posture()

    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    assert run.value_posture == posture
    assert run.status == "blocked"
    assert any(
        record.cell_ref == "ACTOR.value_choice_provenance"
        and record.status == "block"
        and record.refinement_route == "block_candidate"
        for record in run.constraint_store.constraint_records
    )
    assert run.search_ledger.value_choice_status == "blocked_missing_value_provenance"


def test_s2_value_gap_records_p20_constraint_and_ledger_refs() -> None:
    posture = _s8_value_posture()

    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    p20_constraints = [
        row
        for row in run.constraint_store.constraint_records
        if row.cell_ref == "ACTOR.value_choice_provenance"
    ]
    assert p20_constraints
    assert p20_constraints[0].status == "block"
    assert p20_constraints[0].source_ref == posture.value_choice_provenance_ref
    assert posture.pareto_archive_ref in run.search_ledger.pareto_archive_refs
    assert posture.value_choice_provenance_ref in run.search_ledger.value_choice_provenance_refs
    assert posture.value_choice_provenance_ref in run.design_record.ledger_refs


def test_s2_public_projection_exposes_value_tradeoff_summary_only() -> None:
    posture = _s8_value_posture(
        disposition="authorized",
        ranking_mode="ranked_with_authorized_values",
        authorized_value_schedule_ref="pdc://layer2/s8/ua-msme/value-schedule/authorized",
        p20_firewall_status="pass",
    )
    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert public_projection["value_tradeoff_disclosure_present"] is True
    assert public_projection["value_tradeoff_summary"]
    assert public_projection["frontier_value_source_note"]
    assert "raw_social_weights" not in public_projection
    assert "authorized_value_schedule_ref" not in public_projection

    from polisyos import pdc

    pdc.assert_s2_public_projection_has_value_tradeoff_disclosure(public_projection)


def test_s2_reviewer_projection_renders_value_class_status_and_firewalls() -> None:
    posture = _s8_value_posture(
        disposition="contested_multi_principal",
        ranking_mode="ranking_blocked",
        p20_firewall_status="limit",
        conflict_rows=[
            {
                "principal_ref": "principal://ua/ministry-of-economy",
                "incompatible_with": ["principal://ua/social-policy-ministry"],
                "conflict_reason": "distributional schedule conflict",
            }
        ],
    )
    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    reviewer_projection = project_s2_design_search(run, audiences=("REVIEWER",))["REVIEWER"]

    assert reviewer_projection["s8_value_disposition"] == "contested_multi_principal"
    assert reviewer_projection["s8_ranking_mode"] == "ranking_blocked"
    assert reviewer_projection["s8_p20_firewall_status"] == "limit"
    assert reviewer_projection["s8_p22_firewall_status"] == "pass"
    assert reviewer_projection["s8_action_route"] in {"human_decision", "block_candidate"}


def test_s2_expert_machine_projection_renders_value_refs_conflicts_and_integrity() -> None:
    posture = _s8_value_posture(
        disposition="contested_multi_principal",
        ranking_mode="ranking_blocked",
        p20_firewall_status="limit",
        conflict_rows=[
            {
                "principal_ref": "principal://ua/ministry-of-economy",
                "incompatible_with": ["principal://ua/social-policy-ministry"],
                "conflict_reason": "distributional schedule conflict",
            }
        ],
    )
    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    projections = project_s2_design_search(run, audiences=("EXPERT", "MACHINE"))

    for projection in projections.values():
        assert projection["value_choice_provenance_ref"] == posture.value_choice_provenance_ref
        assert projection["pareto_archive_ref"] == posture.pareto_archive_ref
        assert projection["shadow_scenario_value_schedule_refs"]
        assert projection["principal_conflict_rows"] == posture.conflict_rows
        assert projection["affected_group_rows"] == posture.affected_group_rows
        assert projection["dissent_refs"] == posture.dissent_refs
        assert projection["blocking_rights_refs"] == posture.blocking_rights_refs
        assert projection["alternative_schedule_sensitivity"]
        assert projection["value_provenance_completeness"] == 1.0
        assert projection["authority_boundary"]["may_not_use_for"]


def test_s2_does_not_treat_s8_as_production_recommendation_authority() -> None:
    posture = _s8_value_posture(
        disposition="authorized",
        ranking_mode="ranked_with_authorized_values",
        authorized_value_schedule_ref="pdc://layer2/s8/ua-msme/value-schedule/authorized",
        p20_firewall_status="pass",
    )

    run = run_s2_shadow_design_loop(_input(), value_posture=posture)

    assert run.design_record.projection_status == "shadow"
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for
    assert "production_claim_authority" in run.design_record.authority_boundary.may_not_use_for
    assert run.value_posture.authority_boundary.posture == "shadow"
    assert run.search_ledger.value_choice_status == "authorized"


def test_s2_consumes_injected_s10_forecast_posture_without_recomputing_authority() -> None:
    posture = _s10_forecast_posture()

    run = run_s2_shadow_design_loop(_input(), forecast_posture=posture)

    assert run.forecast_posture == posture
    assert run.search_ledger.forecast_support_refs == [posture.forecast_support_ref]
    assert run.search_ledger.forecast_calibration_record_refs == [
        posture.forecast_calibration_record_ref
    ]
    assert run.search_ledger.forecast_authority_status == "observable_calibrated"
    assert run.search_ledger.forecast_authority_boundary == posture.authority_boundary
    assert posture.design_graph_ref in run.search_ledger.forecast_posture_refs
    assert posture.prediction_context_ref in run.search_ledger.forecast_posture_refs
    assert posture.source_contract_ref not in run.design_record.ledger_refs
    assert posture.method_validity_ref not in run.design_record.ledger_refs
    assert len(run.design_record.ledger_refs) <= 40


def test_s2_s10_replay_digest_changes_only_when_forecast_posture_changes() -> None:
    no_s10_first = run_s2_shadow_design_loop(_input())
    no_s10_second = run_s2_shadow_design_loop(_input())
    first = run_s2_shadow_design_loop(_input(), forecast_posture=_s10_forecast_posture())
    second = run_s2_shadow_design_loop(_input(), forecast_posture=_s10_forecast_posture())
    changed = run_s2_shadow_design_loop(
        _input(),
        forecast_posture=_s10_forecast_posture(
            forecast_support_ref="pdc://layer2/s10/ua-msme/forecast-support/revision-2",
            forecast_calibration_record_ref=(
                "pdc://layer2/s10/ua-msme/calibration/revision-2"
            ),
        ),
    )

    assert no_s10_first.search_ledger.deterministic_replay_key == (
        no_s10_second.search_ledger.deterministic_replay_key
    )
    assert no_s10_first.model_dump(mode="json") == no_s10_second.model_dump(mode="json")
    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.search_ledger.deterministic_replay_key != (
        changed.search_ledger.deterministic_replay_key
    )


def test_s2_s10_search_ledger_defaults_preserve_legacy_cas_payloads() -> None:
    legacy_payload = run_s2_shadow_design_loop(_input()).search_ledger.model_dump(mode="json")
    legacy_payload.pop("forecast_support_refs", None)
    legacy_payload.pop("forecast_calibration_record_refs", None)
    legacy_payload.pop("forecast_posture_refs", None)
    legacy_payload.pop("forecast_authority_status", None)
    legacy_payload.pop("forecast_authority_boundary", None)

    loaded = SearchLedger.model_validate(legacy_payload)

    assert loaded.forecast_support_refs == []
    assert loaded.forecast_calibration_record_refs == []
    assert loaded.forecast_posture_refs == []
    assert loaded.forecast_authority_status == "not_applicable"
    assert loaded.forecast_authority_boundary is None


def test_s2_s10_handoff_records_consumed_posture_not_recommendation_authority() -> None:
    posture = _s10_forecast_posture()
    run = run_s2_shadow_design_loop(_input(), forecast_posture=posture)

    rendered_interfaces = json.dumps(
        [row.model_dump(mode="json") for row in run.cluster_interface_contracts],
        sort_keys=True,
    )
    rendered_handoffs = json.dumps(
        [row.model_dump(mode="json") for row in run.handoff_records],
        sort_keys=True,
    )

    assert "Layer2S10ForecastPostureInput" in rendered_interfaces
    assert "Layer2S10ForecastPostureInput" in rendered_handoffs
    assert "recommendation_authority" not in rendered_interfaces
    assert "production_recommendation" in rendered_handoffs


def test_s2_does_not_import_or_call_s10_runtime_quality_producer() -> None:
    import inspect

    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "polisyos.runtime.quality.layer2_outcome_prediction" not in source
    assert "layer2_outcome_prediction" not in source
    assert "build_forecast_support" not in source


def test_s2_s10_public_projection_exposes_tier_and_limits_without_recommendation() -> None:
    posture = _s10_forecast_posture(
        forecast_tier="transported_limited",
        forecast_authority_disposition_reason=(
            "Transported estimate is limited by jurisdiction and response uncertainty."
        ),
    )
    run = run_s2_shadow_design_loop(_input(), forecast_posture=posture)

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert public_projection["forecast_tier"] == "transported_limited"
    assert public_projection["forecast_limitations"]
    assert "production_recommendation_text" not in public_projection
    assert "recommendation_authority" not in json.dumps(public_projection)


def test_s2_s10_expert_machine_projection_exposes_refs_and_weakest_boundary() -> None:
    posture = _s10_forecast_posture()
    run = run_s2_shadow_design_loop(_input(), forecast_posture=posture)

    projections = project_s2_design_search(run, audiences=("EXPERT", "MACHINE"))

    for projection in projections.values():
        assert projection["forecast_support_ref"] == posture.forecast_support_ref
        assert projection["forecast_calibration_record_ref"] == (
            posture.forecast_calibration_record_ref
        )
        assert projection["design_graph_ref"] == posture.design_graph_ref
        assert projection["prediction_context_ref"] == posture.prediction_context_ref
        assert projection["source_contract_ref"] == posture.source_contract_ref
        assert projection["method_validity_ref"] == posture.method_validity_ref
        assert projection["credible_evaluation_evidence_ref"] == (
            posture.credible_evaluation_evidence_ref
        )
        assert projection["uncertainty_interval_refs"] == posture.uncertainty_interval_refs
        assert projection["forecast_authority_boundary"] == (
            posture.authority_boundary.model_dump(mode="json")
        )
        assert projection["weakest_boundary_inherited"] is True


def test_s2_consumes_injected_s11_posture_without_runtime_producer_import() -> None:
    posture = _s11_predictive_posture()

    run = run_s2_shadow_design_loop(_input(), predictive_posture=posture)

    assert run.predictive_posture == posture
    assert run.search_ledger.predictive_knowledge_refs == [
        posture.predictive_knowledge_ref
    ]
    assert run.search_ledger.predictive_axis_upgrade_refs == list(
        posture.axis_upgrade_refs
    )
    assert run.search_ledger.proof_carrying_analytics_refs == [
        posture.proof_carrying_analytics_ref
    ]
    assert run.search_ledger.ir_analytics_bridge_refs == [posture.ir_analytics_bridge_ref]
    assert run.search_ledger.predictive_authority_status == (
        posture.effective_predictive_posture
    )
    assert run.search_ledger.predictive_authority_boundary == posture.authority_boundary

    source = (
        REPO_ROOT / "src/polisyos/pdc/_impl/layer2_design_search.py"
    ).read_text(encoding="utf-8")
    assert "layer2_predictive_knowledge" not in source


def test_s2_s11_replay_digest_changes_only_when_predictive_posture_changes() -> None:
    no_s11_first = run_s2_shadow_design_loop(_input())
    no_s11_second = run_s2_shadow_design_loop(_input())
    first = run_s2_shadow_design_loop(_input(), predictive_posture=_s11_predictive_posture())
    second = run_s2_shadow_design_loop(_input(), predictive_posture=_s11_predictive_posture())
    changed = run_s2_shadow_design_loop(
        _input(),
        predictive_posture=_s11_predictive_posture(
            predictive_knowledge_ref="pdc://layer2/s11/ua-msme/predictive-knowledge/revision-2",
            s11_calibration_record_refs=[
                "pdc://layer2/s11/ua-msme/calibration/measurability/revision-2"
            ],
        ),
    )

    assert no_s11_first.search_ledger.deterministic_replay_key == (
        no_s11_second.search_ledger.deterministic_replay_key
    )
    assert no_s11_first.model_dump(mode="json") == no_s11_second.model_dump(mode="json")
    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.search_ledger.deterministic_replay_key != (
        changed.search_ledger.deterministic_replay_key
    )


def test_s2_s11_search_ledger_defaults_preserve_legacy_cas_payloads() -> None:
    legacy_payload = run_s2_shadow_design_loop(_input()).search_ledger.model_dump(mode="json")
    legacy_s11_fields = (
        "predictive_knowledge_refs",
        "predictive_axis_upgrade_refs",
        "proof_carrying_analytics_refs",
        "ir_analytics_bridge_refs",
        "s11_calibration_record_refs",
        "s11_forecast_quality_constraint_refs",
        "s11_regime_strategy_constraint_refs",
        "s11_residual_limitation_refs",
        "predictive_authority_status",
        "predictive_authority_boundary",
    )
    for field_name in legacy_s11_fields:
        legacy_payload.pop(field_name, None)

    loaded = SearchLedger.model_validate(legacy_payload)

    assert loaded.predictive_knowledge_refs == []
    assert loaded.predictive_axis_upgrade_refs == []
    assert loaded.proof_carrying_analytics_refs == []
    assert loaded.ir_analytics_bridge_refs == []
    assert loaded.s11_calibration_record_refs == []
    assert loaded.s11_forecast_quality_constraint_refs == []
    assert loaded.s11_regime_strategy_constraint_refs == []
    assert loaded.s11_residual_limitation_refs == []
    assert loaded.predictive_authority_status == "not_applicable"
    assert loaded.predictive_authority_boundary is None


def test_s2_s11_handoff_records_consumed_posture_not_recommendation_authority() -> None:
    posture = _s11_predictive_posture()
    run = run_s2_shadow_design_loop(_input(), predictive_posture=posture)

    rendered_interfaces = json.dumps(
        [row.model_dump(mode="json") for row in run.cluster_interface_contracts],
        sort_keys=True,
    )
    rendered_handoffs = json.dumps(
        [row.model_dump(mode="json") for row in run.handoff_records],
        sort_keys=True,
    )

    assert "Layer2S11PredictivePostureInput" in rendered_interfaces
    assert "Layer2S11PredictivePostureInput" in rendered_handoffs
    assert "predictive_axis_maturity_upgrade" in rendered_interfaces
    assert "production_recommendation" in rendered_handoffs
    assert "recommendation_authority" not in rendered_interfaces


def test_s2_s11_persisted_search_ledger_round_trips_predictive_refs(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import load_s2_search_ledger, persist_s2_design_search_run

    posture = _s11_predictive_posture()
    run = run_s2_shadow_design_loop(_input(), predictive_posture=posture)
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)

    loaded = load_s2_search_ledger(store=store, artifact_ref=refs["search_ledger"])

    assert loaded.predictive_knowledge_refs == [posture.predictive_knowledge_ref]
    assert loaded.predictive_axis_upgrade_refs == list(posture.axis_upgrade_refs)
    assert loaded.proof_carrying_analytics_refs == [
        posture.proof_carrying_analytics_ref
    ]
    assert loaded.s11_calibration_record_refs == list(posture.s11_calibration_record_refs)
    assert loaded.predictive_authority_status == posture.effective_predictive_posture


def test_s11_weakest_boundary_caps_search_ledger_projection() -> None:
    posture = _s11_predictive_posture(
        effective_predictive_posture="fail_closed",
        weakest_boundary_reason="stale calibration keeps strategic_response fail_closed.",
        residual_limitation_refs=["limitation://s11/stale-calibration"],
    )
    run = run_s2_shadow_design_loop(_input(), predictive_posture=posture)

    projection = project_s2_design_search(run, audiences=("REVIEWER",))["REVIEWER"]

    assert run.search_ledger.predictive_authority_status == "fail_closed"
    assert "limitation://s11/stale-calibration" in (
        run.search_ledger.s11_residual_limitation_refs
    )
    assert projection["predictive_authority_status"] == "fail_closed"
    assert projection["weakest_boundary_reason"] == posture.weakest_boundary_reason
    assert "production_recommendation_text" not in projection


def test_s11_poor_calibration_downgrades_forecast_quality_without_reclassifying_s10_tier() -> None:
    forecast_posture = _s10_forecast_posture(forecast_tier="observable_calibrated")
    predictive_posture = _s11_predictive_posture(
        per_axis_predictive_calibration_status="poor",
        forecast_quality_disposition="downgraded_by_s11_calibration",
    )

    run = run_s2_shadow_design_loop(
        _input(),
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
    )

    forecast_quality_rows = [
        row
        for row in run.constraint_store.constraint_records
        if row.cell_ref == "INTERVENTION.forecast_quality"
    ]
    assert forecast_quality_rows
    assert forecast_quality_rows[0].status == "limit"
    assert "forecast_tier=observable_calibrated" in forecast_quality_rows[0].reason
    assert run.forecast_posture is not None
    assert run.forecast_posture.forecast_tier == "observable_calibrated"
    assert run.search_ledger.forecast_authority_status == "observable_calibrated"


def test_s2_records_s11_forecast_quality_constraint_without_rerunning_s4_or_s10() -> None:
    forecast_posture = _s10_forecast_posture(forecast_tier="observable_calibrated")
    predictive_posture = _s11_predictive_posture(
        per_axis_predictive_calibration_status="poor",
        forecast_quality_disposition="downgraded_by_s11_calibration",
    )

    run = run_s2_shadow_design_loop(
        _input(),
        regime="risk",
        design_strategy="expected_welfare_optimization",
        regime_claim_ref="pdc://layer2/s4/ua-msme/regime/risk",
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
    )

    assert run.candidates[0].regime == "risk"
    assert run.candidates[0].design_strategy == "expected_welfare_optimization"
    assert run.forecast_posture is not None
    assert run.forecast_posture.forecast_tier == "observable_calibrated"
    assert run.search_ledger.s11_forecast_quality_constraint_refs
    assert run.search_ledger.s11_regime_strategy_constraint_refs == [
        predictive_posture.regime_strategy_constraint_ref
    ]


def _s9_projection_context() -> dict[str, object]:
    return {
        "canonical_design_record_ref": "pdc://layer2/s9/ua-msme/canonical-design-record",
        "canonical_design_record_digest": "sha256:" + "9" * 64,
        "canonical_design_record_schema_version": (
            "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
        ),
        "canonical_design_record_revision_ref": (
            "pdc://layer2/s9/ua-msme/canonical-design-record/revision/001"
        ),
        "s9_projection_source_ref": "pdc://layer2/s9/ua-msme/projection-source",
        "s9_projection_policy": "reads_canonical_design_record",
        "s9_projection_authority_boundary": {
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
            "rule_version_refs": ["policyos.layer2.s9.projection_lowering.v1"],
        },
        "s9_lowering_boundary": "projection_only_until_grounded",
        "s9_source_revision_ref": "git://policyos/layer2/s9/red-first",
        "s9_reissue_required": False,
        "s9_faithfulness_ref": "pdc://layer2/s9/ua-msme/faithfulness/public",
        "s9_lowering_gate_ref": "pdc://layer2/s9/ua-msme/lowering-gate/legal-diff",
        "s9_lowering_gate_status": "lowering_blocked_missing_grounding",
    }


def test_s2_projection_feed_carries_s9_source_refs_without_authority() -> None:
    run = run_s2_shadow_design_loop(_input(), value_posture=_s8_value_posture())
    context = _s9_projection_context()

    projections = project_s2_design_search(
        run,
        audiences=("MACHINE", "REVIEWER"),
        s9_projection_context=context,
    )

    machine = projections["MACHINE"]
    assert machine["s9_projection_source_ref"] == context["s9_projection_source_ref"]
    assert machine["s9_projection_policy"] == "reads_canonical_design_record"
    assert machine["canonical_design_record_ref"] == context["canonical_design_record_ref"]
    assert machine["s9_source_revision_ref"] == context["s9_source_revision_ref"]
    assert machine["s9_projection_authority_boundary"]["posture"] == "shadow"
    assert "production_claim_authority" in machine["s9_projection_authority_boundary"][
        "may_not_use_for"
    ]


def test_s2_public_projection_remains_shadow_when_s9_projection_passes() -> None:
    posture = _s8_value_posture(
        disposition="authorized",
        ranking_mode="ranked_with_authorized_values",
        authorized_value_schedule_ref="pdc://layer2/s8/ua-msme/value-schedule/authorized",
        p20_firewall_status="pass",
    )
    run = run_s2_shadow_design_loop(_input(), value_posture=posture)
    context = {
        **_s9_projection_context(),
        "s9_faithfulness_status": "pass",
        "s9_lowering_gate_status": "projection_allowed",
    }

    public_projection = project_s2_design_search(
        run,
        audiences=("PUBLIC",),
        s9_projection_context=context,
    )["PUBLIC"]

    assert run.design_record.projection_status == "shadow"
    assert public_projection["projection_status"] == "shadow"
    assert public_projection["canonical_outcome_effect"] == "none_shadow_only"
    assert public_projection["s9_projection_policy"] == "reads_canonical_design_record"
    assert public_projection["s9_lowering_boundary"] == "projection_only_until_grounded"
    assert "production_recommendation" in public_projection["authority_boundary"][
        "may_not_use_for"
    ]


def test_s2_machine_projection_exposes_s9_faithfulness_and_lowering_boundary() -> None:
    run = run_s2_shadow_design_loop(_input(), value_posture=_s8_value_posture())
    context = _s9_projection_context()

    machine_projection = project_s2_design_search(
        run,
        audiences=("MACHINE",),
        s9_projection_context=context,
    )["MACHINE"]

    assert machine_projection["s9_faithfulness_ref"] == context["s9_faithfulness_ref"]
    assert machine_projection["s9_lowering_gate_ref"] == context["s9_lowering_gate_ref"]
    assert machine_projection["s9_lowering_gate_status"] == (
        "lowering_blocked_missing_grounding"
    )
    assert machine_projection["s9_lowering_boundary"] == "projection_only_until_grounded"
    assert machine_projection["canonical_design_record_digest"] == (
        context["canonical_design_record_digest"]
    )


def test_s2_does_not_import_s9_projection_lowering_producer() -> None:
    import inspect

    import polisyos.pdc._impl.layer2_design_search as s2_design_search

    source = inspect.getsource(s2_design_search)

    assert "runtime.quality.layer2_projection_lowering" not in source
    assert "layer2_projection_lowering" not in source
    assert "build_canonical_design_record" not in source
    assert "verify_projection_faithfulness" not in source
