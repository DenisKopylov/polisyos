"""Layer 2 S2 shadow design-search contracts and deterministic producer."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.core import artifacts, canon

from .layer2_readiness import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    EpistemicRegime,
    GovernanceDecisionClass,
    Layer2ReadinessModel,
    ValueOfInformationEstimate,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

S2_DESIGN_SEARCH_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s2_design_search.v1"
S2_DESIGN_RECORD_RULE_VERSION = "policyos.layer2.s2.design_search.v1"

CounterexampleClass = Literal[
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
FieldSourceClass = Literal[
    "deterministic_grammar",
    "llm_candidate",
    "human_reviewer",
    "corpus_exemplar",
    "producer_derived_constraint",
]
S2RunStatus = Literal[
    "shadow_ready",
    "blocked",
    "governance_required",
    "acquisition_required",
    "abstained",
]
RefinementDecisionKind = Literal[
    "refine",
    "acquire",
    "reframe",
    "decompose",
    "human_decision",
    "abstain",
    "block_candidate",
]
ConstraintRecordStatus = Literal["pass", "warn", "limit", "block"]
ConstraintRefinementRoute = Literal[
    "none",
    "acquire",
    "reframe",
    "human_decision",
    "block_candidate",
    "pending_consumer_constraint",
]
S8ValueDisposition = Literal[
    "authorized",
    "advisory_only",
    "contested_multi_principal",
    "blocked_missing_value_provenance",
    "blocked_mandate_not_pass",
    "blocked_p20_normative_laundering",
    "blocked_p22_mandate_laundering",
    "shadow_scenario_only",
]
S8RankingMode = Literal[
    "unranked_frontier_only",
    "ranked_with_authorized_values",
    "shadow_scenario_ranking",
    "ranking_blocked",
]
S8FirewallStatus = Literal["pass", "limit", "block"]
S10ForecastTier = Literal[
    "observable_calibrated",
    "transported_limited",
    "historical_prior_context",
    "simulation_only_advisory",
    "equilibrium_contested_blocked",
    "blocked",
]
S11PredictivePosture = Literal[
    "not_applicable",
    "limited_by_weakest_boundary",
    "fail_closed",
    "predictive_shadow_only",
]
S11ForecastQualityDisposition = Literal[
    "unchanged_s10_tier_consumed",
    "downgraded_by_s11_calibration",
    "blocked_by_s11_calibration",
]
S11CalibrationStatus = Literal[
    "pass",
    "absent",
    "stale",
    "poor",
    "out_of_scope",
]
S12ExploreExploitPosture = Literal[
    "exploit_in_envelope",
    "invest_in_growth",
    "balanced_governed",
    "blocked",
]
S12ThermometerTrend = Literal["improving", "flat", "regressing"]

_COUNTEREXAMPLE_CLASS_VOCABULARY: list[str] = [
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
_INSTRUMENT_FAMILIES = [
    "credit_guarantee",
    "interest_rate_buydown",
    "cash_grant",
]
_AUTHORITY_PURPOSE = "shadow_design_search_replay"
_SEARCH_INCOMPLETENESS_NOTE = (
    "best_known_shadow_frontier is a replayable S2 trace only; it is not exhaustive, "
    "admissibility authority, or a production recommendation."
)
_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "publication_authority",
    "rollout_authority",
    "claim_authority",
    "production_claim_authority",
    "production_closeout_authority",
    "acquisition_authority",
    "source_contract_authority",
]
_NON_POINT_OPTIMIZATION_STRATEGIES = frozenset(
    {
        "robust_satisficing",
        "frame_indexed_portfolio",
        "precautionary_adaptive_pathway",
    }
)
_S8_VALUE_CHOICE_CELL_REF = "ACTOR.value_choice_provenance"
_S8_REQUIRED_HANDOFF_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "preference_learning_authority",
    "s9_projection_authority",
    "s9_projection_maturity",
]
_S10_REQUIRED_HANDOFF_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "production_claim_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "s11_calibration",
]
_S11_REQUIRED_HANDOFF_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "recommendation_authority",
    "production_claim_authority",
    "claim_authority",
    "publication_authority",
    "closeout_authority",
    "forecast_tier_reclassification",
    "s10_forecast_authority",
]
_S11_REGIME_CELL_REF = "KNOWLEDGE.epistemic_regime"
_S11_FORECAST_QUALITY_CELL_REF = "INTERVENTION.forecast_quality"
_S12_RESOURCE_ECONOMICS_CELL_REF = "INTERVENTION.resource_economics"
_S12_REQUIRED_HANDOFF_MAY_NOT_USE_FOR = [
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
]


class Layer2S2DesignSearchInputError(ValueError):
    """Raised when S2 shadow design-search input violates firewalls."""


class Layer2S2DesignSearchInput(Layer2ReadinessModel):
    """Input for the deterministic one-case S2 shadow design-search loop."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    case_id: str = Field(..., min_length=1)
    intent_ref: str = Field(..., min_length=1)
    grammar_ref: str = Field(..., min_length=1)
    actor_ref: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    objective_refs: tuple[str, ...] = Field(..., min_length=1)
    construct_refs: tuple[str, ...] = Field(..., min_length=1)
    authority_profile_ref: str = Field(..., min_length=1)
    requested_posture: Literal["shadow"] = "shadow"
    generated_at: AwareDatetime
    rule_version_ref: str = S2_DESIGN_RECORD_RULE_VERSION
    forced_counterexample_class: CounterexampleClass | None = None
    force_retry_same_candidate: bool = False
    candidate_source_authority: Literal["deterministic_producer", "llm_candidate"] = (
        "deterministic_producer"
    )
    omit_grammar_derivation: bool = False


class Layer2S5CompositionPostureInput(Layer2ReadinessModel):
    """Injected S5 A-gate posture consumed by the S2 shadow loop."""

    coupling_regime: Literal[
        "modular",
        "near_decomposable",
        "hierarchically_coupled",
        "entangled",
    ]
    composition_disposition: Literal[
        "compose",
        "compose_with_limitations",
        "system_evidence_required",
        "blocked",
    ]
    coupling_graph_ref: str
    module_discovery_ref: str
    decomposition_result_ref: str
    composition_receipt_ref: str
    dynamics_requirement_ref: str | None = None
    tractability_budget_ref: str | None = None
    boundary_coupling_rows: list[dict[str, object]] = Field(default_factory=list)
    forecast_support_label: str | None = None
    critical_path_module_refs: list[str] = Field(default_factory=list)
    residual_interaction_risk: str | None = None
    authority_mode: Literal["critical_path_only", "module_local_only", "not_composable"] = (
        "critical_path_only"
    )
    false_modular_penalty: float = Field(default=0.0, ge=0.0)


class Layer2S6BlindSpotPostureInput(Layer2ReadinessModel):
    """Injected S6 A-gate blind-spot posture consumed by the S2 shadow loop."""

    overall_posture: Literal["clear_fail_closed", "limited", "blocked"]
    maturity: Literal["fail_closed"] = "fail_closed"
    measurability_record_ref: str
    aggregation_validity_record_ref: str
    capacity_feasibility_record_ref: str
    mandate_legitimacy_record_ref: str
    strategic_response_record_ref: str
    cluster_authority_dimension_refs: list[str] = Field(default_factory=list, max_length=40)
    bridge_consumer_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    constraint_store_updates: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    c3_authority_dimension_rows: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=10,
    )
    axis_rows: list[dict[str, object]] = Field(default_factory=list, max_length=10)
    blocking_axis_refs: list[str] = Field(default_factory=list, max_length=10)
    limiting_axis_refs: list[str] = Field(default_factory=list, max_length=10)
    post_intervention_dgp_update_ref: str | None = None
    system_dynamics_handoff_required: bool
    regime_reissue_required: bool
    limitation_summary: str
    false_clear_penalty: float = Field(ge=0.0)


class Layer2S7DelegationPostureInput(Layer2ReadinessModel):
    """Injected S7 delegation posture consumed by the S2 shadow loop."""

    delegation_contract_ref: str = Field(..., min_length=1, max_length=300)
    decision_rights_matrix_ref: str = Field(..., min_length=1, max_length=300)
    human_decision_request_ref: str = Field(..., min_length=1, max_length=300)
    human_decision_record_ref: str | None = Field(default=None, max_length=300)
    decision_class_id: str = Field(..., min_length=1, max_length=120)
    required_role: str = Field(..., min_length=1, max_length=120)
    interaction_mode: str = Field(..., min_length=1, max_length=120)
    disposition: str = Field(..., min_length=1, max_length=120)
    available_actions: list[str] = Field(default_factory=list, max_length=10)
    decision_action_exercised: str | None = Field(default=None, max_length=120)
    five_rights_requirement: dict[str, object]
    five_rights_check: dict[str, object] | None = None
    decision_options: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    recommendation_ref: str | None = Field(default=None, max_length=300)
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    material_limitations: list[str] = Field(default_factory=list, max_length=20)
    value_stakes_impact: str = Field(..., min_length=1, max_length=500)
    what_changes_under_each_choice: list[str] = Field(default_factory=list, max_length=20)
    attention_cost_rank: int = Field(ge=1)
    responsibility_integrity_status: str = Field(..., min_length=1, max_length=40)
    mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_firewall_disposition: str = Field(..., min_length=1, max_length=80)
    mandate_source_refs: list[str] = Field(default_factory=list, max_length=20)
    requested_at: AwareDatetime
    decision_due_at: AwareDatetime | None = None
    decided_at: AwareDatetime | None = None
    actor_ref: str | None = Field(default=None, max_length=300)
    voi_rank: int = Field(ge=1)
    need_reasons: list[str] = Field(default_factory=list, max_length=20)
    authority_boundary: AuthorityBoundary
    governed_pilot_eligible: bool
    constraint_store_updates: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    handoff_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    limitation_summary: str = Field(..., min_length=1, max_length=500)


class Layer2S8ValuePostureInput(Layer2ReadinessModel):
    """Injected S8 value-choice posture consumed by the S2 shadow loop."""

    value_choice_provenance_ref: str = Field(..., min_length=1, max_length=300)
    authorized_value_schedule_ref: str | None = Field(default=None, max_length=300)
    shadow_scenario_value_schedule_refs: list[str] = Field(default_factory=list, max_length=40)
    objective_function_provenance_ref: str = Field(..., min_length=1, max_length=300)
    pareto_archive_ref: str = Field(..., min_length=1, max_length=300)
    value_tradeoff_disclosure_ref: str = Field(..., min_length=1, max_length=300)
    mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_firewall_disposition: str = Field(..., min_length=1, max_length=80)
    ranking_mode: S8RankingMode
    disposition: S8ValueDisposition
    p20_firewall_status: S8FirewallStatus
    p22_firewall_status: S8FirewallStatus
    value_provenance_completeness: float = Field(ge=0.0, le=1.0)
    principal_refs: list[str] = Field(default_factory=list, max_length=40)
    conflict_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    affected_group_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    dissent_refs: list[str] = Field(default_factory=list, max_length=40)
    blocking_rights_refs: list[str] = Field(default_factory=list, max_length=40)
    alternative_schedule_sensitivity: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=40,
    )
    rejected_nondominated_alternative_ids: list[str] = Field(
        default_factory=list,
        max_length=40,
    )
    social_weight_provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    delegation_refs: list[str] = Field(default_factory=list, max_length=40)
    value_authorization_decision_refs: list[str] = Field(default_factory=list, max_length=40)
    constraint_store_updates: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    handoff_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    limitation_summary: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary


class Layer2S10ForecastPostureInput(Layer2ReadinessModel):
    """Injected S10 forecast-support posture consumed by the S2 shadow loop."""

    forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    forecast_tier: S10ForecastTier
    forecast_authority_disposition_reason: str = Field(..., min_length=1, max_length=800)
    forecast_support_label: str = Field(..., min_length=1, max_length=160)
    forecast_calibration_record_ref: str | None = Field(default=None, max_length=300)
    design_graph_ref: str = Field(..., min_length=1, max_length=300)
    prediction_context_ref: str = Field(..., min_length=1, max_length=300)
    policy_context_ref: str = Field(..., min_length=1, max_length=300)
    candidate_design_ref: str = Field(..., min_length=1, max_length=300)
    baseline_design_ref: str = Field(..., min_length=1, max_length=300)
    alternative_design_refs: list[str] = Field(default_factory=list, max_length=80)
    prediction_horizon_ref: str = Field(..., min_length=1, max_length=300)
    observable_subset_ref: str | None = Field(default=None, max_length=300)
    uncertainty_interval_refs: list[str] = Field(default_factory=list, max_length=80)
    welfare_comparison_ref: str | None = Field(default=None, max_length=300)
    s5_forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    s6_firewall_status_refs: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=80,
    )
    s8_value_choice_provenance_ref: str = Field(..., min_length=1, max_length=300)
    s8_value_tradeoff_disclosure_ref: str = Field(..., min_length=1, max_length=300)
    source_contract_ref: str | None = Field(default=None, max_length=300)
    method_validity_ref: str | None = Field(default=None, max_length=300)
    credible_evaluation_evidence_ref: str | None = Field(default=None, max_length=300)
    dynamic_equilibrium_check_ref: str | None = Field(default=None, max_length=300)
    sensitivity_analysis_ref: str | None = Field(default=None, max_length=300)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class Layer2S11PredictivePostureInput(Layer2ReadinessModel):
    """Injected S11 predictive-knowledge posture consumed by the S2 shadow loop."""

    predictive_knowledge_ref: str = Field(..., min_length=1, max_length=300)
    effective_predictive_posture: S11PredictivePosture
    axis_upgrade_refs: list[str] = Field(default_factory=list, max_length=80)
    predictive_axis_rows: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    proof_carrying_analytics_ref: str = Field(..., min_length=1, max_length=300)
    ir_analytics_bridge_ref: str = Field(..., min_length=1, max_length=300)
    s10_forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    s10_forecast_tier: S10ForecastTier
    s6_floor_status_refs: list[str] = Field(default_factory=list, max_length=80)
    s6_axis_rows: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    s6_bridge_consumer_rows: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=40,
    )
    s6_constraint_store_update_refs: list[str] = Field(default_factory=list, max_length=80)
    s6_c3_authority_dimension_refs: list[str] = Field(
        default_factory=list,
        max_length=40,
    )
    post_intervention_dgp_update_ref: str | None = Field(default=None, max_length=300)
    system_dynamics_handoff_required: bool
    s11_calibration_record_refs: list[str] = Field(default_factory=list, max_length=80)
    method_infrastructure_refs: list[str] = Field(default_factory=list, max_length=80)
    forecast_quality_disposition: S11ForecastQualityDisposition
    regime_strategy_constraint_ref: str | None = Field(default=None, max_length=300)
    residual_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    per_axis_predictive_calibration_threshold_ref: str = Field(
        ...,
        min_length=1,
        max_length=300,
    )
    per_axis_predictive_calibration_denominator: int = Field(ge=0)
    per_axis_predictive_calibration_numerator: int = Field(ge=0)
    per_axis_predictive_calibration_pass_rate: float = Field(ge=0.0, le=1.0)
    per_axis_predictive_calibration_status: S11CalibrationStatus
    weakest_boundary_reason: str = Field(..., min_length=1, max_length=800)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=list, max_length=80)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @model_validator(mode="after")
    def _validate_predictive_calibration_counts(self) -> Layer2S11PredictivePostureInput:
        if (
            self.per_axis_predictive_calibration_numerator
            > self.per_axis_predictive_calibration_denominator
        ):
            raise ValueError("S11 calibration numerator cannot exceed denominator")
        return self


class Layer2S12ResourceEconomicsPostureInput(Layer2ReadinessModel):
    """Injected S12 resource-economics posture consumed by the S2 shadow loop."""

    resource_allocation_policy_ref: str = Field(..., min_length=1, max_length=300)
    explore_exploit_posture: S12ExploreExploitPosture
    explore_exploit_dial_ref: str | None = Field(default=None, max_length=300)
    delegation_contract_ref: str = Field(..., min_length=1, max_length=300)
    voi_allocation_refs: list[str] = Field(default_factory=list, max_length=80)
    voi_site_count: int = Field(ge=0)
    typed_budget_refs: list[str] = Field(default_factory=list, max_length=20)
    pareto_archive_ref: str = Field(..., min_length=1, max_length=300)
    allocation_priority_rows: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=80,
    )
    envelope_growth_ledger_ref: str = Field(..., min_length=1, max_length=300)
    growth_thermometer_ref: str = Field(..., min_length=1, max_length=300)
    override_rate_trend: S12ThermometerTrend
    reuse_rate_trend: S12ThermometerTrend
    held_out_status: Literal["pending_s14"] = "pending_s14"
    knowledge_governance_throughput_ledger_ref: str = Field(
        ...,
        min_length=1,
        max_length=300,
    )
    residual_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=list, max_length=80)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @model_validator(mode="after")
    def _validate_resource_authority_boundary(
        self,
    ) -> Layer2S12ResourceEconomicsPostureInput:
        if self.voi_site_count < 3:
            raise ValueError("S12 resource posture requires VOI across at least three sites")
        if len(self.typed_budget_refs) < 5:
            raise ValueError("S12 resource posture requires all typed budget refs")
        if not set(self.may_not_use_for) >= set(_S12_REQUIRED_HANDOFF_MAY_NOT_USE_FOR):
            raise ValueError("S12 resource posture missing required may_not_use_for denials")
        return self


class TypedDiagnosticRecord(Layer2ReadinessModel):
    """Design-time diagnostic carried by S2 counterexamples."""

    diagnostic_id: str
    code: str
    severity: Literal["warn", "block", "governance_required"]
    message: str
    authority_purpose: str
    owner: str
    rule_version_ref: str


class DesignGrammarExpansion(Layer2ReadinessModel):
    """Grammar-derived design-space expansion used before candidate emission."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    expansion_id: str
    expansion_ref: str
    case_id: str
    intent_ref: str
    source_grammar_ref: str
    instrument_families: list[str] = Field(..., min_length=2)
    parameter_space: dict[str, list[str]]
    constraints: list[str]
    construct_demand_refs: list[str]
    authority_boundary: AuthorityBoundary
    generated_at: AwareDatetime


class DesignCandidateV0(Layer2ReadinessModel):
    """S2 minimal typed design candidate produced from grammar expansion."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    candidate_id: str
    candidate_ref: str
    case_id: str
    grammar_expansion_ref: str
    instrument_family: str
    parameterization: dict[str, str]
    objective_refs: list[str]
    construct_refs: list[str]
    source_authority: Literal["deterministic_producer", "llm_candidate"]
    field_source_classification: dict[str, FieldSourceClass]
    authority_boundary: AuthorityBoundary
    status: Literal["candidate_unverified", "a_verified_shadow", "blocked"]
    regime: EpistemicRegime | None = None
    design_strategy: str | None = None
    commitment_profile_ref: str | None = None
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None
    coupling_regime: str | None = None
    composition_disposition: str | None = None
    decomposition_result_ref: str | None = None
    composition_receipt_ref: str | None = None
    forecast_support_label: str | None = None
    residual_interaction_risk: str | None = None

    @model_validator(mode="after")
    def _validate_grammar_first(self) -> DesignCandidateV0:
        if not self.grammar_expansion_ref:
            raise ValueError("DesignCandidateV0 requires grammar_expansion_ref")
        if self.source_authority == "llm_candidate" and self.status != "candidate_unverified":
            raise ValueError("llm_candidate cannot become A-verified authority")
        return self


class ConstraintStoreEntry(Layer2ReadinessModel):
    """Typed bounded S2 constraint-store entry consumed by refinement and projection."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    constraint_id: str
    cell_ref: str
    status: ConstraintRecordStatus
    source_ref: str
    consumer_ref: str
    refinement_route: ConstraintRefinementRoute
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    reason: str
    rule_version_ref: str


class ConstraintStoreSnapshot(Layer2ReadinessModel):
    """Snapshot of S2 constraints consumed by A-side verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    snapshot_id: str
    snapshot_ref: str
    grammar_expansion_ref: str
    constraint_ids: list[str]
    hard_constraint_ids: list[str]
    governance_owned_gap_ids: list[str]
    constraint_records: list[ConstraintStoreEntry] = Field(default_factory=list, max_length=40)


class CounterexampleRecord(Layer2ReadinessModel):
    """Typed counterexample emitted by S2 A-verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    counterexample_id: str
    counterexample_ref: str
    case_id: str
    candidate_ref: str
    counterexample_class: CounterexampleClass
    diagnostic: TypedDiagnosticRecord
    evidence_refs: list[str]
    routed_to: Literal[
        "refinement_policy",
        "acquisition",
        "governance",
        "abstention",
        "blocked",
    ]


class RefinementDecision(Layer2ReadinessModel):
    """Decision produced by consuming typed S2 counterexamples."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    decision_id: str
    decision_ref: str
    case_id: str
    candidate_ref: str
    consumed_counterexample_refs: list[str]
    decision: RefinementDecisionKind
    next_candidate_ref: str | None = None
    value_of_information: ValueOfInformationEstimate
    budget_refs: list[str] = Field(..., min_length=1)
    stakes_band: Literal["low", "moderate", "high", "high_stakes"]
    governance_decision_class_ref: str | None = None
    governance_decision_class: GovernanceDecisionClass | None = None
    governance_refs: list[str] = Field(default_factory=list)
    reason: str

    @model_validator(mode="after")
    def _validate_governance_handoff(self) -> RefinementDecision:
        if self.decision == "human_decision" and not self.governance_decision_class_ref:
            raise ValueError("human_decision requires governance_decision_class_ref")
        if self.governance_decision_class and (
            self.governance_decision_class.decision_class_id
            != self.governance_decision_class_ref
        ):
            raise ValueError("governance decision class ref mismatch")
        return self


class SearchIteration(Layer2ReadinessModel):
    """Single replay-visible S2 search iteration."""

    iteration_id: str
    candidate_ref: str
    counterexample_refs: list[str]
    refinement_decision_ref: str
    status: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ]


class SearchLedger(Layer2ReadinessModel):
    """Replayable S2 search ledger."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    ledger_id: str
    ledger_ref: str
    case_id: str
    iterations: list[SearchIteration]
    candidate_refs: list[str]
    counterexample_refs: list[str]
    refinement_decision_refs: list[str]
    deterministic_replay_key: str
    counterexample_conversion_rate: float
    grammar_diversity_minimum: int
    instrument_family_coverage: list[str]
    counterexample_class_vocabulary: list[str]
    acquisition_branch_state: Literal["bridge_missing"] = "bridge_missing"
    delegation_request_refs: list[str] = Field(default_factory=list, max_length=40)
    delegation_record_refs: list[str] = Field(default_factory=list, max_length=40)
    cluster_handoff_refs: list[str] = Field(default_factory=list, max_length=40)
    delegation_status: Literal[
        "not_applicable",
        "requested",
        "recorded",
        "blocked",
        "no_interrupt",
    ] = "not_applicable"
    value_choice_provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    pareto_archive_refs: list[str] = Field(default_factory=list, max_length=40)
    authorized_value_schedule_refs: list[str] = Field(default_factory=list, max_length=40)
    shadow_scenario_value_schedule_refs: list[str] = Field(default_factory=list, max_length=40)
    value_authorization_decision_refs: list[str] = Field(default_factory=list, max_length=40)
    value_choice_status: str = Field(default="not_applicable", min_length=1, max_length=120)
    forecast_support_refs: list[str] = Field(default_factory=list, max_length=40)
    forecast_calibration_record_refs: list[str] = Field(default_factory=list, max_length=40)
    forecast_posture_refs: list[str] = Field(default_factory=list, max_length=40)
    forecast_authority_status: str = Field(
        default="not_applicable",
        min_length=1,
        max_length=120,
    )
    forecast_authority_boundary: AuthorityBoundary | None = None
    predictive_knowledge_refs: list[str] = Field(default_factory=list, max_length=40)
    predictive_axis_upgrade_refs: list[str] = Field(default_factory=list, max_length=40)
    proof_carrying_analytics_refs: list[str] = Field(default_factory=list, max_length=40)
    ir_analytics_bridge_refs: list[str] = Field(default_factory=list, max_length=40)
    s11_calibration_record_refs: list[str] = Field(default_factory=list, max_length=40)
    s11_forecast_quality_constraint_refs: list[str] = Field(
        default_factory=list,
        max_length=40,
    )
    s11_regime_strategy_constraint_refs: list[str] = Field(
        default_factory=list,
        max_length=40,
    )
    s11_residual_limitation_refs: list[str] = Field(default_factory=list, max_length=40)
    predictive_authority_status: str = Field(
        default="not_applicable",
        min_length=1,
        max_length=120,
    )
    predictive_authority_boundary: AuthorityBoundary | None = None
    resource_allocation_policy_refs: list[str] = Field(default_factory=list, max_length=40)
    envelope_growth_ledger_refs: list[str] = Field(default_factory=list, max_length=40)
    growth_thermometer_refs: list[str] = Field(default_factory=list, max_length=40)
    voi_allocation_refs: list[str] = Field(default_factory=list, max_length=80)
    explore_exploit_posture: str = Field(
        default="not_applicable",
        min_length=1,
        max_length=120,
    )
    resource_authority_boundary: AuthorityBoundary | None = None
    no_retry_without_new_grammar: bool
    search_incompleteness_note: str


class ClusterInterfaceContract(Layer2ReadinessModel):
    """Typed cluster blackboard interface used by S2 handoffs."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    contract_id: str
    cell_ref: str
    publishes: list[str]
    consumes: list[str]
    authority_boundary: AuthorityBoundary


class ClusterHandoffRecord(Layer2ReadinessModel):
    """Typed handoff record proving Scientist/design workflow did not launder authority."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    handoff_id: str
    workflow_ref: str
    source_cell_ref: str
    target_cell_ref: str
    artifact_refs: list[str]
    disposition: Literal["emitted", "consumed", "rejected", "blocked"]
    authority_purpose: str
    may_not_use_for: list[str]


class Layer2S2DesignSearchRun(Layer2ReadinessModel):
    """Complete S2 shadow design-search run."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    run_id: str
    status: S2RunStatus
    grammar_expansion: DesignGrammarExpansion
    constraint_store: ConstraintStoreSnapshot
    candidates: list[DesignCandidateV0]
    counterexamples: list[CounterexampleRecord]
    refinement_decisions: list[RefinementDecision]
    search_ledger: SearchLedger
    cluster_interface_contracts: list[ClusterInterfaceContract]
    handoff_records: list[ClusterHandoffRecord]
    design_record: DesignRecordV0
    composition_posture: Layer2S5CompositionPostureInput | None = None
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None
    delegation_posture: Layer2S7DelegationPostureInput | None = None
    value_posture: Layer2S8ValuePostureInput | None = None
    forecast_posture: Layer2S10ForecastPostureInput | None = None
    predictive_posture: Layer2S11PredictivePostureInput | None = None
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None


def run_s2_shadow_design_loop(
    input: Layer2S2DesignSearchInput,
    *,
    regime: EpistemicRegime | None = None,
    design_strategy: str | None = None,
    regime_claim_ref: str | None = None,
    commitment_profile_ref: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> Layer2S2DesignSearchRun:
    """Run the deterministic S2 one-case shadow design-search loop."""

    if input.candidate_source_authority == "llm_candidate" and input.omit_grammar_derivation:
        raise Layer2S2DesignSearchInputError(
            "llm_candidate requires grammar_expansion_ref and remains shadow-only"
        )
    boundary = _shadow_boundary(input)
    run_id = f"layer2.s2.{_slug(input.case_id)}"
    expansion = _grammar_expansion(input, boundary=boundary)
    candidate = _candidate(
        input,
        expansion=expansion,
        boundary=boundary,
        regime=regime,
        design_strategy=design_strategy,
        commitment_profile_ref=commitment_profile_ref,
        commitment_stakes=commitment_stakes,
        composition_posture=composition_posture,
    )
    constraint_store = _constraint_store(
        input,
        expansion=expansion,
        ranked_value_choice_attempted=_attempts_ranked_value_choice(
            design_strategy=design_strategy,
            counterexample_class=input.forced_counterexample_class,
        ),
        blind_spot_posture=blind_spot_posture,
        delegation_posture=delegation_posture,
        value_posture=value_posture,
        predictive_posture=predictive_posture,
        resource_posture=resource_posture,
    )
    counterexample = _counterexample(input, candidate=candidate)
    decision = _refinement_decision(
        input,
        candidate=candidate,
        counterexample=counterexample,
        composition_posture=composition_posture,
        blind_spot_posture=blind_spot_posture,
        value_posture=value_posture,
        predictive_posture=predictive_posture,
    )
    iteration_status = _iteration_status(input, decision)
    iteration_status = _s7_iteration_status(delegation_posture, fallback=iteration_status)
    iteration_status = _s8_iteration_status(
        value_posture,
        ranked_value_choice_attempted=_attempts_ranked_value_choice(
            design_strategy=design_strategy,
            counterexample_class=input.forced_counterexample_class,
        ),
        fallback=iteration_status,
    )
    iteration_status = _s11_iteration_status(
        predictive_posture,
        fallback=iteration_status,
    )
    ledger = _search_ledger(
        input,
        candidate=candidate,
        counterexample=counterexample,
        decision=decision,
        iteration_status=iteration_status,
        composition_posture=composition_posture,
        blind_spot_posture=blind_spot_posture,
        delegation_posture=delegation_posture,
        value_posture=value_posture,
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
        resource_posture=resource_posture,
    )
    design_record = _design_record(
        input,
        candidate=candidate,
        ledger=ledger,
        boundary=boundary,
        regime=regime,
        regime_claim_ref=regime_claim_ref,
        commitment_profile_ref=commitment_profile_ref,
        design_strategy=design_strategy,
        commitment_stakes=commitment_stakes,
        composition_posture=composition_posture,
        blind_spot_posture=blind_spot_posture,
        delegation_posture=delegation_posture,
        value_posture=value_posture,
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
        resource_posture=resource_posture,
    )
    status: S2RunStatus = (
        "governance_required"
        if decision.decision == "human_decision"
        else "acquisition_required"
        if decision.decision == "acquire"
        else "abstained"
        if decision.decision == "abstain"
        else "blocked"
        if decision.decision == "block_candidate"
        else "shadow_ready"
    )
    status = _s7_run_status(delegation_posture, fallback=status)
    status = _s8_run_status(
        value_posture,
        ranked_value_choice_attempted=_attempts_ranked_value_choice(
            design_strategy=design_strategy,
            counterexample_class=input.forced_counterexample_class,
        ),
        fallback=status,
    )
    status = _s11_run_status(predictive_posture, fallback=status)
    return Layer2S2DesignSearchRun(
        run_id=run_id,
        status=status,
        grammar_expansion=expansion,
        constraint_store=constraint_store,
        candidates=[candidate],
        counterexamples=[counterexample],
        refinement_decisions=[decision],
        search_ledger=ledger,
        cluster_interface_contracts=_cluster_interfaces(
            boundary,
            composition_posture=composition_posture,
            blind_spot_posture=blind_spot_posture,
            value_posture=value_posture,
            forecast_posture=forecast_posture,
            predictive_posture=predictive_posture,
            resource_posture=resource_posture,
        ),
        handoff_records=_handoff_records(
            candidate,
            expansion,
            ledger,
            composition_posture=composition_posture,
            blind_spot_posture=blind_spot_posture,
            delegation_posture=delegation_posture,
            value_posture=value_posture,
            forecast_posture=forecast_posture,
            predictive_posture=predictive_posture,
            resource_posture=resource_posture,
        ),
        design_record=design_record,
        composition_posture=composition_posture,
        blind_spot_posture=blind_spot_posture,
        delegation_posture=delegation_posture,
        value_posture=value_posture,
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
        resource_posture=resource_posture,
    )


def project_s2_design_search(
    run: Layer2S2DesignSearchRun,
    *,
    audiences: tuple[Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"], ...],
    s9_projection_context: Mapping[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    """Project S2 search trace without minting recommendation authority."""

    projections: dict[str, dict[str, object]] = {}
    boundary = run.design_record.authority_boundary.model_dump(mode="json")
    s9_context = _s9_projection_context_fields(s9_projection_context)
    regime_axis = _axis_position(run.design_record, "KNOWLEDGE.epistemic_regime")
    commitment_axis = _axis_position(
        run.design_record,
        "INTERVENTION.reversibility_lifecycle_stakes",
    )
    p16_firewall = _firewall_status(run.design_record, "KNOWLEDGE.epistemic_regime")
    p23_firewall = _firewall_status(
        run.design_record,
        "INTERVENTION.reversibility_lifecycle_stakes",
    )
    composition_axis = _axis_position(run.design_record, "INTERVENTION.scale_composition")
    p17_composition_firewall = _firewall_status(
        run.design_record,
        "INTERVENTION.scale_composition",
    )
    s6_firewalls = [
        status for status in run.design_record.firewall_status if _is_s6_cell(status.cell_ref)
    ]
    s8_firewall = _firewall_status(run.design_record, "ACTOR.value_choice_provenance")
    for audience in audiences:
        projection: dict[str, object] = {
            "schema_version": S2_DESIGN_SEARCH_SCHEMA_VERSION,
            "audience": audience,
            "status": run.status,
            "design_record_id": run.design_record.record_id,
            "projection_status": run.design_record.projection_status,
            "canonical_outcome_effect": "none_shadow_only",
            "search_ledger_ref": run.search_ledger.ledger_ref,
            "candidate_refs": list(run.search_ledger.candidate_refs),
            "counterexample_refs": list(run.search_ledger.counterexample_refs),
            "refinement_decision_refs": list(run.search_ledger.refinement_decision_refs),
            "counterexample_conversion_rate": run.search_ledger.counterexample_conversion_rate,
            "grammar_diversity_minimum": run.search_ledger.grammar_diversity_minimum,
            "instrument_family_coverage": list(run.search_ledger.instrument_family_coverage),
            "acquisition_branch_state": run.search_ledger.acquisition_branch_state,
            "search_incompleteness_note": run.search_ledger.search_incompleteness_note,
            "authority_boundary": boundary,
        }
        if regime_axis is not None:
            projection.update(
                _regime_projection_fields(
                    audience,
                    regime_axis=regime_axis,
                    commitment_axis=commitment_axis,
                    p16_firewall=p16_firewall,
                    p23_firewall=p23_firewall,
                    candidate=run.candidates[0],
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_regime_limitation(projection)
        if run.composition_posture is not None:
            projection.update(
                _composition_projection_fields(
                    audience,
                    composition_posture=run.composition_posture,
                    composition_axis=composition_axis,
                    p17_firewall=p17_composition_firewall,
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_composition_limitation(projection)
        if run.blind_spot_posture is not None:
            projection.update(
                _s6_projection_fields(
                    audience,
                    blind_spot_posture=run.blind_spot_posture,
                    s6_firewalls=s6_firewalls,
                    constraint_store=run.constraint_store,
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_blind_spot_disclosure(projection)
        if run.delegation_posture is not None:
            projection.update(
                _s7_projection_fields(
                    audience,
                    delegation_posture=run.delegation_posture,
                    constraint_store=run.constraint_store,
                    blind_spot_posture=run.blind_spot_posture,
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_delegation_request(projection)
        if run.value_posture is not None:
            projection.update(
                _s8_projection_fields(
                    audience,
                    value_posture=run.value_posture,
                    s8_firewall=s8_firewall,
                    constraint_store=run.constraint_store,
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_value_tradeoff_disclosure(projection)
        if run.forecast_posture is not None:
            projection.update(
                _s10_projection_fields(audience, forecast_posture=run.forecast_posture)
            )
        if run.predictive_posture is not None:
            projection.update(
                _s11_projection_fields(
                    audience,
                    predictive_posture=run.predictive_posture,
                    constraint_store=run.constraint_store,
                )
            )
        if run.resource_posture is not None:
            projection.update(
                _s12_projection_fields(
                    audience,
                    resource_posture=run.resource_posture,
                    constraint_store=run.constraint_store,
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_growth_limitation(projection)
        projection.update(s9_context)
        projections[audience] = projection
    return projections


def _s9_projection_context_fields(
    context: Mapping[str, object] | None,
) -> dict[str, object]:
    if context is None:
        return {}
    allowed_keys = (
        "canonical_design_record_ref",
        "canonical_design_record_digest",
        "canonical_design_record_schema_version",
        "canonical_design_record_revision_ref",
        "s9_projection_source_ref",
        "s9_projection_policy",
        "s9_projection_authority_boundary",
        "s9_lowering_boundary",
        "s9_source_revision_ref",
        "s9_reissue_required",
        "s9_faithfulness_ref",
        "s9_faithfulness_status",
        "s9_lowering_gate_ref",
        "s9_lowering_gate_status",
        "s9_design_record_maturity_report_ref",
    )
    fields = {key: context[key] for key in allowed_keys if key in context}
    fields.setdefault("s9_projection_policy", "reads_canonical_design_record")
    fields.setdefault("s9_lowering_boundary", "projection_only_until_grounded")
    return fields


def assert_s2_public_projection_has_regime_limitation(
    projection: Mapping[str, object],
) -> None:
    """Require the load-bearing PUBLIC limitation for projected S4 regime data."""

    if projection.get("audience") == "PUBLIC" and projection.get("regime"):
        limitation = projection.get("limitation")
        if not isinstance(limitation, str) or not limitation.strip():
            raise ValueError("PUBLIC regime projection requires limitation")


def assert_s2_public_projection_has_composition_limitation(
    projection: Mapping[str, object],
) -> None:
    """Require the load-bearing PUBLIC limitation for projected S5 composition data."""

    if projection.get("audience") == "PUBLIC" and projection.get("coupling_regime"):
        limitation = projection.get("composition_limitation")
        if not isinstance(limitation, str) or not limitation.strip():
            raise ValueError("PUBLIC composition projection requires limitation")


def assert_s2_public_projection_has_blind_spot_disclosure(
    projection: Mapping[str, object],
) -> None:
    """Require honest PUBLIC disclosure when S6 blind-spot posture is projected."""

    if projection.get("audience") == "PUBLIC" and projection.get("s6_disclosure_present"):
        disclosure = projection.get("blind_spot_disclosure")
        if not isinstance(disclosure, str) or not disclosure.strip():
            raise ValueError("PUBLIC blind-spot projection requires disclosure")


def assert_s2_public_projection_has_delegation_request(
    projection: Mapping[str, object],
) -> None:
    """Require decision-shaped PUBLIC disclosure for S7 delegation requests."""

    if projection.get("audience") == "PUBLIC" and projection.get("human_decision_needed"):
        limitation = projection.get("delegation_limitation")
        if not isinstance(limitation, str) or not limitation.strip():
            raise ValueError("PUBLIC S7 projection requires delegation limitation")
        if "s7_disposition" in projection:
            raise ValueError("PUBLIC S7 projection must not expose disposition labels")


def assert_s2_public_projection_has_value_tradeoff_disclosure(
    projection: Mapping[str, object],
) -> None:
    """Require value-tradeoff disclosure without raw weights on PUBLIC S8 projection."""

    if not projection.get("value_tradeoff_disclosure_present"):
        return
    summary = projection.get("value_tradeoff_summary")
    source_note = projection.get("frontier_value_source_note")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("PUBLIC S8 projection requires value-tradeoff summary")
    if not isinstance(source_note, str) or "authorized value source" not in source_note:
        raise ValueError("PUBLIC S8 projection requires authorized value-source note")
    forbidden = {
        "raw_social_weights",
        "authorized_value_schedule_ref",
        "social_weight_provenance_refs",
        "principal_conflict_rows",
    }
    leaked = sorted(forbidden & set(projection))
    if leaked:
        raise ValueError(f"PUBLIC S8 projection leaked raw value fields: {leaked}")


def assert_s2_public_projection_has_growth_limitation(
    projection: Mapping[str, object],
) -> None:
    """Require PUBLIC S12 growth disclosure without allocation recommendation authority."""

    if projection.get("audience") != "PUBLIC":
        return
    if not projection.get("s12_resource_posture_ref") and not projection.get(
        "explore_exploit_posture"
    ):
        return
    limitation = projection.get("s12_public_growth_limitation")
    if not isinstance(limitation, str) or not limitation.strip():
        raise ValueError("PUBLIC S12 projection requires growth limitation")
    forbidden = {
        "allocation_priority_rows",
        "selected_policy_ref",
        "allocation_recommendation_text",
        "recommendation_authority",
    }
    leaked = sorted(forbidden & set(projection))
    if leaked:
        raise ValueError(f"PUBLIC S12 projection leaked allocation authority: {leaked}")


def persist_s2_design_search_run(
    run: Layer2S2DesignSearchRun,
    *,
    store: artifacts.FileSystemCAS,
) -> dict[str, artifacts.ArtifactRef]:
    """Persist S2 DesignRecordV0 and SearchLedger as canonical CAS artifacts."""

    producer = artifacts.ProducerInfo(
        component="polisyos.pdc.layer2_design_search",
        version=S2_DESIGN_RECORD_RULE_VERSION,
    )
    design_record_ref = store.put_json(
        run.design_record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.design_record_v0",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.design_record_v0",
                version=run.design_record.schema_version,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    search_ledger_ref = store.put_json(
        run.search_ledger.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.search_ledger",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.search_ledger",
                version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    return {
        "design_record": design_record_ref,
        "search_ledger": search_ledger_ref,
    }


def load_s2_search_ledger(
    *,
    store: artifacts.FileSystemCAS,
    artifact_ref: artifacts.ArtifactRef,
) -> SearchLedger:
    """Load a persisted S2 SearchLedger from CAS."""

    payload = canon.from_canonical_bytes(store.get_bytes(artifact_ref.artifact_id))
    return SearchLedger.model_validate(payload)


def _shadow_boundary(input: Layer2S2DesignSearchInput) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[
            "shadow_design_search_replay",
            "machine_replay_trace",
            "reviewer_search_trace",
        ],
        may_not_use_for=list(_MAY_NOT_USE_FOR),
        source_authority=input.candidate_source_authority,
        posture="shadow",
        rule_version_refs=[input.rule_version_ref],
    )


def _grammar_expansion(
    input: Layer2S2DesignSearchInput,
    *,
    boundary: AuthorityBoundary,
) -> DesignGrammarExpansion:
    slug = _slug(input.case_id)
    return DesignGrammarExpansion(
        expansion_id=f"layer2.s2.grammar.{slug}",
        expansion_ref=f"pdc://layer2/s2/{slug}/grammar-expansion",
        case_id=input.case_id,
        intent_ref=input.intent_ref,
        source_grammar_ref=input.grammar_ref,
        instrument_families=list(_INSTRUMENT_FAMILIES),
        parameter_space={
            "coverage": ["partial_portfolio", "targeted_sector"],
            "risk_share": ["first_loss", "pari_passu"],
            "delivery_channel": ["bank_intermediated", "public_fund"],
        },
        constraints=[
            "shadow_only",
            "a_side_verification_required",
            "no_acquisition_authority",
        ],
        construct_demand_refs=list(input.construct_refs),
        authority_boundary=boundary,
        generated_at=input.generated_at,
    )


def _candidate(
    input: Layer2S2DesignSearchInput,
    *,
    expansion: DesignGrammarExpansion,
    boundary: AuthorityBoundary,
    regime: EpistemicRegime | None = None,
    design_strategy: str | None = None,
    commitment_profile_ref: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
) -> DesignCandidateV0:
    slug = _slug(input.case_id)
    return DesignCandidateV0(
        candidate_id=f"layer2.s2.candidate.{slug}.credit_guarantee",
        candidate_ref=f"pdc://layer2/s2/{slug}/candidate/credit-guarantee",
        case_id=input.case_id,
        grammar_expansion_ref=expansion.expansion_ref,
        instrument_family="credit_guarantee",
        parameterization={
            "coverage": "partial_portfolio",
            "risk_share": "first_loss",
            "delivery_channel": "bank_intermediated",
        },
        objective_refs=list(input.objective_refs),
        construct_refs=list(input.construct_refs),
        source_authority=input.candidate_source_authority,
        field_source_classification={
            "instrument_family": "deterministic_grammar",
            "parameterization": "deterministic_grammar",
            "objective_refs": "producer_derived_constraint",
            "construct_refs": "producer_derived_constraint",
        },
        authority_boundary=boundary,
        status="candidate_unverified",
        regime=regime,
        design_strategy=design_strategy,
        commitment_profile_ref=commitment_profile_ref,
        commitment_stakes=commitment_stakes,
        coupling_regime=(
            composition_posture.coupling_regime if composition_posture is not None else None
        ),
        composition_disposition=(
            composition_posture.composition_disposition
            if composition_posture is not None
            else None
        ),
        decomposition_result_ref=(
            composition_posture.decomposition_result_ref
            if composition_posture is not None
            else None
        ),
        composition_receipt_ref=(
            composition_posture.composition_receipt_ref
            if composition_posture is not None
            else None
        ),
        forecast_support_label=(
            composition_posture.forecast_support_label if composition_posture is not None else None
        ),
        residual_interaction_risk=(
            composition_posture.residual_interaction_risk
            if composition_posture is not None
            else None
        ),
    )


def _constraint_store(
    input: Layer2S2DesignSearchInput,
    *,
    expansion: DesignGrammarExpansion,
    ranked_value_choice_attempted: bool = False,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> ConstraintStoreSnapshot:
    slug = _slug(input.case_id)
    s6_constraints = _s6_constraint_entries(blind_spot_posture)
    s7_constraints = _s7_constraint_entries(delegation_posture)
    s8_constraints = _s8_constraint_entries(
        value_posture,
        case_slug=slug,
        ranked_value_choice_attempted=ranked_value_choice_attempted,
        rule_version_ref=input.rule_version_ref,
    )
    s11_constraints = _s11_constraint_entries(predictive_posture, case_slug=slug)
    s12_constraints = _s12_constraint_entries(resource_posture, case_slug=slug)
    base_constraint_ids = [
        "shadow_only",
        "authority_boundary_required",
        "a_side_counterexample_required",
    ]
    s6_constraint_ids = [entry.constraint_id for entry in s6_constraints]
    s7_constraint_ids = [entry.constraint_id for entry in s7_constraints]
    s8_constraint_ids = [entry.constraint_id for entry in s8_constraints]
    s11_constraint_ids = [entry.constraint_id for entry in s11_constraints]
    s12_constraint_ids = [entry.constraint_id for entry in s12_constraints]
    constraint_records = [
        *s6_constraints,
        *s7_constraints,
        *s8_constraints,
        *s11_constraints,
        *s12_constraints,
    ]
    return ConstraintStoreSnapshot(
        snapshot_id=f"layer2.s2.constraints.{slug}",
        snapshot_ref=f"pdc://layer2/s2/{slug}/constraint-store",
        grammar_expansion_ref=expansion.expansion_ref,
        constraint_ids=[
            *base_constraint_ids,
            *s6_constraint_ids,
            *s7_constraint_ids,
            *s8_constraint_ids,
            *s11_constraint_ids,
            *s12_constraint_ids,
        ],
        hard_constraint_ids=[
            "shadow_only",
            "authority_boundary_required",
            *[
                entry.constraint_id
                for entry in constraint_records
                if entry.status == "block"
            ],
        ],
        governance_owned_gap_ids=[
            "a_spec_gap",
            *[
                entry.constraint_id
                for entry in constraint_records
                if entry.refinement_route == "human_decision"
            ],
        ],
        constraint_records=constraint_records,
    )


def _counterexample(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
) -> CounterexampleRecord:
    counterexample_class = input.forced_counterexample_class or "real_design_blocker"
    if input.force_retry_same_candidate:
        routed_to = "blocked"
    elif counterexample_class == "a_spec_gap":
        routed_to = "governance"
    elif counterexample_class == "substrate_gap":
        routed_to = "acquisition"
    elif counterexample_class == "budget_gap":
        routed_to = "abstention"
    else:
        routed_to = "refinement_policy"

    return CounterexampleRecord(
        counterexample_id=f"layer2.s2.counterexample.{_slug(input.case_id)}.001",
        counterexample_ref=f"pdc://layer2/s2/{_slug(input.case_id)}/counterexample/001",
        case_id=input.case_id,
        candidate_ref=candidate.candidate_ref,
        counterexample_class=counterexample_class,
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"layer2.s2.diagnostic.{_slug(input.case_id)}.001",
            code=f"s2.{counterexample_class}",
            severity="governance_required" if counterexample_class == "a_spec_gap" else "block",
            message=_counterexample_message(counterexample_class),
            authority_purpose=_AUTHORITY_PURPOSE,
            owner="team-policyos-runtime",
            rule_version_ref=input.rule_version_ref,
        ),
        evidence_refs=[
            "repo://architecture/policy_design_case/layer2_first_proving_case.json",
        ],
        routed_to=routed_to,
    )


def _refinement_decision(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
) -> RefinementDecision:
    s8_route = _s8_refinement_decision(
        value_posture,
        ranked_value_choice_attempted=_attempts_ranked_value_choice(
            design_strategy=candidate.design_strategy,
            counterexample_class=counterexample.counterexample_class,
        ),
    )
    s6_route = _s6_refinement_decision(blind_spot_posture)
    s11_route = _s11_refinement_decision(predictive_posture)
    if s8_route == "block_candidate":
        decision: RefinementDecisionKind = s8_route
    elif s11_route == "block_candidate":
        decision = s11_route
    elif s6_route is not None:
        decision = s6_route
    elif s8_route is not None:
        decision = s8_route
    elif s11_route is not None:
        decision = s11_route
    elif input.force_retry_same_candidate:
        decision = "block_candidate"
    elif counterexample.counterexample_class == "a_spec_gap":
        decision = "human_decision"
    elif counterexample.counterexample_class == "substrate_gap":
        decision = "acquire"
    elif counterexample.counterexample_class == "budget_gap":
        decision = "abstain"
    elif (
        composition_posture is not None
        and composition_posture.composition_disposition == "system_evidence_required"
    ):
        decision = "decompose"
    else:
        decision = "refine"
    if (
        decision == "refine"
        and candidate.design_strategy in _NON_POINT_OPTIMIZATION_STRATEGIES
        and counterexample.counterexample_class != "real_design_blocker"
    ):
        decision = "reframe"

    governance_ref: str | None = None
    governance_class: GovernanceDecisionClass | None = None
    if decision == "human_decision":
        if value_posture is not None and value_posture.disposition in {
            "advisory_only",
            "contested_multi_principal",
        }:
            governance_ref = "value_authorization"
            governance_class = _value_authorization_decision_class(input)
        else:
            governance_ref = counterexample.counterexample_class
            governance_class = _governance_decision_class(input)
    return RefinementDecision(
        decision_id=f"layer2.s2.refinement.{_slug(input.case_id)}.001",
        decision_ref=f"pdc://layer2/s2/{_slug(input.case_id)}/refinement/001",
        case_id=input.case_id,
        candidate_ref=candidate.candidate_ref,
        consumed_counterexample_refs=[counterexample.counterexample_ref],
        decision=decision,
        next_candidate_ref=(
            f"pdc://layer2/s2/{_slug(input.case_id)}/candidate/refined-001"
            if decision == "refine"
            else None
        ),
        value_of_information=ValueOfInformationEstimate(
            estimate_id="s2_shadow_refinement_voi",
            purpose="Schedule shadow refinement only; does not relax authority floors.",
            budget_dimensions=["human_attention", "acquisition", "compute"],
            used_by_sites=["layer2.s2.shadow_design_loop"],
            owner="team-policyos-runtime",
            rule_version_ref=input.rule_version_ref,
        ),
        budget_refs=["budget://layer2/s2/shadow-loop"],
        stakes_band=_stakes_band_for_commitment(candidate.commitment_stakes),
        governance_decision_class_ref=governance_ref,
        governance_decision_class=governance_class,
        governance_refs=(
            ["governance://layer2/s2/a_spec_gap"] if decision == "human_decision" else []
        ),
        reason=_decision_reason(
            decision,
            counterexample.counterexample_class,
            design_strategy=candidate.design_strategy,
            composition_posture=composition_posture,
            blind_spot_posture=blind_spot_posture,
            value_posture=value_posture,
            predictive_posture=predictive_posture,
        ),
    )


def _iteration_status(
    input: Layer2S2DesignSearchInput,
    decision: RefinementDecision,
) -> Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "refined_shadow",
]:
    if input.force_retry_same_candidate or decision.decision == "block_candidate":
        return "blocked_no_retry"
    if decision.decision == "human_decision":
        return "governance_required"
    if decision.decision == "acquire":
        return "acquisition_required"
    if decision.decision == "abstain":
        return "abstained"
    return "refined_shadow"


def _search_ledger(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
    iteration_status: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ],
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> SearchLedger:
    slug = _slug(input.case_id)
    replay_key = _deterministic_replay_key(
        input,
        candidate=candidate,
        counterexample=counterexample,
        decision=decision,
        composition_posture=composition_posture,
        blind_spot_posture=blind_spot_posture,
        delegation_posture=delegation_posture,
        value_posture=value_posture,
        forecast_posture=forecast_posture,
        predictive_posture=predictive_posture,
        resource_posture=resource_posture,
    )
    handoff_refs = [
        *_s7_handoff_refs(delegation_posture),
        *_s8_handoff_refs(value_posture),
        *_s11_handoff_refs(predictive_posture),
        *_s12_handoff_refs(resource_posture),
    ]
    return SearchLedger(
        ledger_id=f"layer2.s2.ledger.{slug}",
        ledger_ref=f"pdc://layer2/s2/{slug}/search-ledger",
        case_id=input.case_id,
        iterations=[
            SearchIteration(
                iteration_id=f"layer2.s2.iteration.{slug}.001",
                candidate_ref=candidate.candidate_ref,
                counterexample_refs=[counterexample.counterexample_ref],
                refinement_decision_ref=decision.decision_ref,
                status=iteration_status,
            )
        ],
        candidate_refs=[candidate.candidate_ref],
        counterexample_refs=[counterexample.counterexample_ref],
        refinement_decision_refs=[decision.decision_ref],
        deterministic_replay_key=replay_key,
        counterexample_conversion_rate=1.0,
        grammar_diversity_minimum=3,
        instrument_family_coverage=list(_INSTRUMENT_FAMILIES),
        counterexample_class_vocabulary=list(_COUNTEREXAMPLE_CLASS_VOCABULARY),
        acquisition_branch_state="bridge_missing",
        delegation_request_refs=_s7_delegation_request_refs(delegation_posture),
        delegation_record_refs=_s7_delegation_record_refs(delegation_posture),
        cluster_handoff_refs=handoff_refs,
        delegation_status=_s7_delegation_status(delegation_posture),
        value_choice_provenance_refs=_s8_value_choice_provenance_refs(value_posture),
        pareto_archive_refs=_s8_pareto_archive_refs(value_posture),
        authorized_value_schedule_refs=_s8_authorized_value_schedule_refs(value_posture),
        shadow_scenario_value_schedule_refs=_s8_shadow_scenario_value_schedule_refs(
            value_posture
        ),
        value_authorization_decision_refs=_s8_value_authorization_decision_refs(
            value_posture
        ),
        value_choice_status=_s8_value_choice_status(value_posture),
        forecast_support_refs=_s10_forecast_support_refs(forecast_posture),
        forecast_calibration_record_refs=_s10_forecast_calibration_record_refs(
            forecast_posture
        ),
        forecast_posture_refs=_s10_forecast_posture_refs(forecast_posture),
        forecast_authority_status=_s10_forecast_authority_status(forecast_posture),
        forecast_authority_boundary=(
            forecast_posture.authority_boundary if forecast_posture is not None else None
        ),
        predictive_knowledge_refs=_s11_predictive_knowledge_refs(predictive_posture),
        predictive_axis_upgrade_refs=_s11_predictive_axis_upgrade_refs(
            predictive_posture
        ),
        proof_carrying_analytics_refs=_s11_proof_carrying_analytics_refs(
            predictive_posture
        ),
        ir_analytics_bridge_refs=_s11_ir_analytics_bridge_refs(predictive_posture),
        s11_calibration_record_refs=_s11_calibration_record_refs(predictive_posture),
        s11_forecast_quality_constraint_refs=(
            _s11_forecast_quality_constraint_refs(predictive_posture)
        ),
        s11_regime_strategy_constraint_refs=(
            _s11_regime_strategy_constraint_refs(predictive_posture)
        ),
        s11_residual_limitation_refs=_s11_residual_limitation_refs(
            predictive_posture
        ),
        predictive_authority_status=_s11_predictive_authority_status(
            predictive_posture
        ),
        predictive_authority_boundary=(
            predictive_posture.authority_boundary
            if predictive_posture is not None
            else None
        ),
        resource_allocation_policy_refs=_s12_resource_allocation_policy_refs(
            resource_posture
        ),
        envelope_growth_ledger_refs=_s12_envelope_growth_ledger_refs(resource_posture),
        growth_thermometer_refs=_s12_growth_thermometer_refs(resource_posture),
        voi_allocation_refs=_s12_voi_allocation_refs(resource_posture),
        explore_exploit_posture=_s12_explore_exploit_posture(resource_posture),
        resource_authority_boundary=(
            resource_posture.authority_boundary
            if resource_posture is not None
            else None
        ),
        no_retry_without_new_grammar=input.force_retry_same_candidate,
        search_incompleteness_note=_SEARCH_INCOMPLETENESS_NOTE,
    )


def _design_record(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    ledger: SearchLedger,
    boundary: AuthorityBoundary,
    regime: EpistemicRegime | None = None,
    regime_claim_ref: str | None = None,
    commitment_profile_ref: str | None = None,
    design_strategy: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> DesignRecordV0:
    slug = _slug(input.case_id)
    axis_positions = [
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="design_grammar",
            position="grammar_expanded_shadow_only",
            evidence_refs=[candidate.grammar_expansion_ref],
            authority_purpose=_AUTHORITY_PURPOSE,
            rule_version_ref=input.rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="design_candidate",
            position="candidate_emitted_from_grammar_shadow_only",
            evidence_refs=[candidate.candidate_ref],
            authority_purpose=_AUTHORITY_PURPOSE,
            rule_version_ref=input.rule_version_ref,
        ),
    ]
    firewall_status = [
        AxisFirewallStatus(
            cell_ref="INTERVENTION.design_grammar",
            status="pass",
            pattern_ids=["P10", "P15"],
            reason="Grammar expansion precedes candidate emission in the S2 shadow loop.",
            maturity="predictive",
            rule_version_ref=input.rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="INTERVENTION.design_candidate",
            status="warn",
            pattern_ids=["P05", "P25"],
            reason="Candidate is replay-visible but remains shadow-only and non-exhaustive.",
            maturity="fail_closed",
            rule_version_ref=input.rule_version_ref,
        ),
    ]
    ledger_refs = [ledger.ledger_ref]
    projection_audiences: list[Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]] = [
        "MACHINE",
        "REVIEWER",
    ]
    if regime is not None:
        axis_positions.append(
            AxisPositionDeclaration(
                cluster="KNOWLEDGE",
                axis="epistemic_regime",
                position=regime,
                evidence_refs=[regime_claim_ref] if regime_claim_ref else [],
                authority_purpose="design_strategy_selection",
                rule_version_ref=input.rule_version_ref,
            )
        )
        axis_positions.append(
            AxisPositionDeclaration(
                cluster="INTERVENTION",
                axis="reversibility_lifecycle_stakes",
                position=_commitment_axis_position(
                    commitment_stakes=commitment_stakes,
                    design_strategy=design_strategy,
                ),
                evidence_refs=[commitment_profile_ref] if commitment_profile_ref else [],
                authority_purpose="commitment_gated_floor_selection",
                rule_version_ref=input.rule_version_ref,
            )
        )
        firewall_status.append(
            AxisFirewallStatus(
                cell_ref="KNOWLEDGE.epistemic_regime",
                status="pass" if regime == "risk" else "limit",
                pattern_ids=["P16"],
                reason=f"A-side injected {regime} regime selects {design_strategy or 'strategy'}.",
                maturity="fail_closed",
                rule_version_ref=input.rule_version_ref,
            )
        )
        firewall_status.append(
            AxisFirewallStatus(
                cell_ref="INTERVENTION.reversibility_lifecycle_stakes",
                status="pass" if commitment_stakes == "low" else "limit",
                pattern_ids=["P23"],
                reason=(
                    f"Commitment stakes {commitment_stakes or 'unknown'} select "
                    f"{_selected_floor_for_commitment(commitment_stakes)} floor."
                ),
                maturity="fail_closed",
                rule_version_ref=input.rule_version_ref,
            )
        )
        ledger_refs.extend(
            ref for ref in (regime_claim_ref, commitment_profile_ref) if ref is not None
        )
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if composition_posture is not None:
        axis_positions.extend(
            _composition_axis_positions(composition_posture, input.rule_version_ref)
        )
        firewall_status.extend(
            _composition_firewall_statuses(composition_posture, input.rule_version_ref)
        )
        ledger_refs.extend(_composition_ledger_refs(composition_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if blind_spot_posture is not None:
        axis_positions.extend(_s6_axis_positions(blind_spot_posture, input.rule_version_ref))
        firewall_status.extend(
            _s6_firewall_statuses(blind_spot_posture, input.rule_version_ref)
        )
        ledger_refs.extend(_s6_ledger_refs(blind_spot_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if delegation_posture is not None:
        axis_positions.append(_s7_axis_position(delegation_posture, input.rule_version_ref))
        firewall_status.append(_s7_firewall_status(delegation_posture, input.rule_version_ref))
        ledger_refs.extend(_s7_ledger_refs(delegation_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if value_posture is not None:
        axis_positions.append(_s8_axis_position(value_posture, input.rule_version_ref))
        firewall_status.append(_s8_firewall_status(value_posture, input.rule_version_ref))
        ledger_refs.extend(_s8_ledger_refs(value_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if forecast_posture is not None:
        axis_positions.append(_s10_axis_position(forecast_posture))
        firewall_status.append(_s10_firewall_status(forecast_posture))
        ledger_refs.extend(_s10_design_record_ledger_refs(forecast_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if predictive_posture is not None:
        axis_positions.append(_s11_axis_position(predictive_posture))
        firewall_status.append(_s11_firewall_status(predictive_posture))
        ledger_refs.extend(_s11_design_record_ledger_refs(predictive_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    if resource_posture is not None:
        axis_positions.append(_s12_axis_position(resource_posture))
        firewall_status.append(_s12_firewall_status(resource_posture))
        ledger_refs.extend(_s12_design_record_ledger_refs(resource_posture))
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    not_certified_for = list(_MAY_NOT_USE_FOR)
    if blind_spot_posture is not None and blind_spot_posture.overall_posture == "blocked":
        not_certified_for.append("closeout_authority_blocked_by_s6")
    if (
        predictive_posture is not None
        and predictive_posture.effective_predictive_posture == "fail_closed"
    ):
        not_certified_for.append("closeout_authority_blocked_by_s11")
    if resource_posture is not None:
        not_certified_for = _merge_unique_strings(
            not_certified_for,
            resource_posture.may_not_use_for,
        )
    ledger_refs = list(dict.fromkeys(ledger_refs))[:40]

    return DesignRecordV0(
        record_id=f"layer2.s2.design_record.{slug}",
        candidate_ref=candidate.candidate_ref,
        candidate_source=candidate.source_authority,
        projection_status="shadow",
        authority_boundary=boundary,
        axis_positions=axis_positions,
        firewall_status=firewall_status,
        envelope=CertifiedOperationEnvelope(
            envelope_id=f"layer2.s2.envelope.{slug}",
            domains=[input.domain],
            posture_scopes=["shadow"],
            epistemic_regime_scopes=[regime] if regime else ["ignorance"],
            actor_scopes=[input.actor_ref],
            method_scopes=["deterministic_shadow_design_search"],
            certified_for=[
                "shadow_design_search_replay",
                "machine_replay_trace",
                "reviewer_search_trace",
            ],
            not_certified_for=not_certified_for,
            cluster_authority_dimension_refs=(
                list(blind_spot_posture.cluster_authority_dimension_refs)
                if blind_spot_posture is not None
                else []
            ),
            rule_version_ref=input.rule_version_ref,
        ),
        ledger_refs=ledger_refs,
        projection_audiences=projection_audiences,
    )


def _composition_axis_positions(
    composition_posture: Layer2S5CompositionPostureInput,
    rule_version_ref: str,
) -> list[AxisPositionDeclaration]:
    return [
        AxisPositionDeclaration(
            cluster="SYSTEM",
            axis="connectivity_modularity",
            position=composition_posture.coupling_regime,
            evidence_refs=[
                composition_posture.coupling_graph_ref,
                composition_posture.composition_receipt_ref,
            ],
            authority_purpose="coupling_regime_classification",
            rule_version_ref=rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="SYSTEM",
            axis="dynamics_feedback",
            position=_dynamics_axis_position(composition_posture),
            evidence_refs=[
                ref
                for ref in (
                    composition_posture.dynamics_requirement_ref,
                    composition_posture.coupling_graph_ref,
                )
                if ref is not None
            ],
            authority_purpose="system_dynamics_requirement",
            rule_version_ref=rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="scale_composition",
            position=_composition_axis_position(composition_posture),
            evidence_refs=[
                composition_posture.decomposition_result_ref,
                composition_posture.composition_receipt_ref,
            ],
            authority_purpose="composition_gate",
            rule_version_ref=rule_version_ref,
        ),
    ]


def _composition_firewall_statuses(
    composition_posture: Layer2S5CompositionPostureInput,
    rule_version_ref: str,
) -> list[AxisFirewallStatus]:
    return [
        AxisFirewallStatus(
            cell_ref="SYSTEM.connectivity_modularity",
            status=_coupling_firewall_status(composition_posture),
            pattern_ids=["P17"],
            reason=(
                f"S5 injected {composition_posture.coupling_regime} coupling; "
                "S2 consumes the posture without boundary discovery authority."
            ),
            maturity="fail_closed",
            rule_version_ref=rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="SYSTEM.dynamics_feedback",
            status=_dynamics_firewall_status(composition_posture),
            pattern_ids=["P17", "P24"],
            reason="S5 dynamics posture gates system-effect and feedback claims.",
            maturity="fail_closed",
            rule_version_ref=rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="INTERVENTION.scale_composition",
            status=_composition_firewall_status(composition_posture),
            pattern_ids=["P17"],
            reason="S5 composition receipt gates whole-design authority assembly.",
            maturity="fail_closed",
            rule_version_ref=rule_version_ref,
        ),
    ]


def _composition_ledger_refs(
    composition_posture: Layer2S5CompositionPostureInput,
) -> list[str]:
    return [
        ref
        for ref in (
            composition_posture.coupling_graph_ref,
            composition_posture.module_discovery_ref,
            composition_posture.decomposition_result_ref,
            composition_posture.composition_receipt_ref,
            composition_posture.dynamics_requirement_ref,
            composition_posture.tractability_budget_ref,
        )
        if ref is not None
    ]


def _axis_position(
    record: DesignRecordV0,
    cell_ref: str,
) -> AxisPositionDeclaration | None:
    for position in record.axis_positions:
        if position.cell_ref == cell_ref:
            return position
    return None


def _firewall_status(
    record: DesignRecordV0,
    cell_ref: str,
) -> AxisFirewallStatus | None:
    for status in record.firewall_status:
        if status.cell_ref == cell_ref:
            return status
    return None


def _regime_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    regime_axis: AxisPositionDeclaration,
    commitment_axis: AxisPositionDeclaration | None,
    p16_firewall: AxisFirewallStatus | None,
    p23_firewall: AxisFirewallStatus | None,
    candidate: DesignCandidateV0,
) -> dict[str, object]:
    commitment = _parse_commitment_axis_position(
        commitment_axis.position if commitment_axis else ""
    )
    design_strategy = (
        commitment.get("design_strategy") or candidate.design_strategy or "strategy_not_injected"
    )
    fields: dict[str, object] = {
        "regime": regime_axis.position,
        "design_strategy": design_strategy,
        "limitation": (
            f"{regime_axis.position} is an A-side regime classification for shadow design "
            "strategy only; it does not grant risk-regime authority, production authority, "
            "publication authority, or rollout authority."
        ),
        "commitment_posture": commitment_axis.position if commitment_axis else "not_projected",
        "adaptive_posture": _adaptive_posture(design_strategy),
    }
    if audience in {"REVIEWER", "EXPERT", "MACHINE"}:
        fields.update(
            {
                "p16_firewall_status": p16_firewall.status if p16_firewall else "limit",
                "p23_firewall_status": p23_firewall.status if p23_firewall else "limit",
            }
        )
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "evidence_basis_ref": _first_ref(regime_axis.evidence_refs),
                "commitment_profile_ref": (
                    _first_ref(commitment_axis.evidence_refs) if commitment_axis else None
                ),
                "asymmetry_penalty": _asymmetry_penalty(regime_axis.position),
                "stakes_band": commitment.get("stakes", candidate.commitment_stakes or "unknown"),
                "lifecycle_stage": commitment.get("lifecycle_stage", "see_commitment_profile"),
                "selected_floor": commitment.get(
                    "selected_floor",
                    _selected_floor_for_commitment(candidate.commitment_stakes),
                ),
            }
        )
    return fields


def _composition_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    composition_posture: Layer2S5CompositionPostureInput,
    composition_axis: AxisPositionDeclaration | None,
    p17_firewall: AxisFirewallStatus | None,
) -> dict[str, object]:
    fields: dict[str, object] = {
        "coupling_regime": composition_posture.coupling_regime,
        "composition_disposition": composition_posture.composition_disposition,
        "composition_limitation": _composition_limitation(composition_posture),
    }
    if audience in {"REVIEWER", "EXPERT", "MACHINE"}:
        fields.update(
            {
                "p17_firewall_status": p17_firewall.status if p17_firewall else "limit",
                "composition_strategy": _composition_strategy(composition_posture),
                "residual_interaction_risk": composition_posture.residual_interaction_risk,
            }
        )
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "coupling_graph_ref": composition_posture.coupling_graph_ref,
                "module_discovery_ref": composition_posture.module_discovery_ref,
                "decomposition_result_ref": composition_posture.decomposition_result_ref,
                "composition_receipt_ref": composition_posture.composition_receipt_ref,
                "dynamics_requirement_ref": composition_posture.dynamics_requirement_ref,
                "tractability_budget_ref": composition_posture.tractability_budget_ref,
                "boundary_coupling_rows": list(composition_posture.boundary_coupling_rows),
                "forecast_support_label": composition_posture.forecast_support_label,
                "critical_path_module_refs": list(composition_posture.critical_path_module_refs),
                "false_modular_penalty": composition_posture.false_modular_penalty,
                "authority_mode": composition_posture.authority_mode,
                "composition_axis_position": (
                    composition_axis.position if composition_axis else "not_projected"
                ),
            }
        )
    return fields


def _s6_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    blind_spot_posture: Layer2S6BlindSpotPostureInput,
    s6_firewalls: list[AxisFirewallStatus],
    constraint_store: ConstraintStoreSnapshot,
) -> dict[str, object]:
    pattern_ids = sorted({pattern for firewall in s6_firewalls for pattern in firewall.pattern_ids})
    if audience == "PUBLIC":
        return {
            "s6_disclosure_present": True,
            "blind_spot_disclosure": blind_spot_posture.limitation_summary,
            "blind_spot_limiting_axis_refs": list(blind_spot_posture.limiting_axis_refs),
            "blind_spot_blocking_axis_refs": list(blind_spot_posture.blocking_axis_refs),
        }

    fields: dict[str, object] = {
        "s6_overall_posture": blind_spot_posture.overall_posture,
        "s6_maturity": blind_spot_posture.maturity,
        "s6_pattern_ids": pattern_ids,
        "s6_firewall_status": {
            firewall.cell_ref: firewall.status for firewall in s6_firewalls
        },
        "s6_refinement_route": _s6_refinement_decision(blind_spot_posture),
        "s6_regime_reissue_required": blind_spot_posture.regime_reissue_required,
        "s6_strategy_cap": (
            "strategy_limited_until_s4_reissue"
            if blind_spot_posture.regime_reissue_required
            else "none"
        ),
        "s6_system_dynamics_handoff_required": (
            blind_spot_posture.system_dynamics_handoff_required
        ),
        "s6_post_intervention_dgp_update_ref": (
            blind_spot_posture.post_intervention_dgp_update_ref
        ),
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "s6_record_refs": {
                    "measurability": blind_spot_posture.measurability_record_ref,
                    "aggregation": blind_spot_posture.aggregation_validity_record_ref,
                    "capacity": blind_spot_posture.capacity_feasibility_record_ref,
                    "mandate": blind_spot_posture.mandate_legitimacy_record_ref,
                    "strategic_response": blind_spot_posture.strategic_response_record_ref,
                },
                "s6_axis_rows": list(blind_spot_posture.axis_rows),
                "s6_bridge_consumer_rows": list(blind_spot_posture.bridge_consumer_rows),
                "s6_constraint_store_updates": [
                    record.model_dump(mode="json")
                    for record in constraint_store.constraint_records
                ],
                "s6_c3_authority_dimension_rows": list(
                    blind_spot_posture.c3_authority_dimension_rows
                ),
                "s6_cluster_authority_dimension_refs": list(
                    blind_spot_posture.cluster_authority_dimension_refs
                ),
                "s6_false_clear_penalty": blind_spot_posture.false_clear_penalty,
            }
        )
    return fields


def _s7_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    delegation_posture: Layer2S7DelegationPostureInput,
    constraint_store: ConstraintStoreSnapshot,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None,
) -> dict[str, object]:
    if audience == "PUBLIC":
        return {
            "human_decision_needed": delegation_posture.disposition == "request_human_decision",
            "accountable_role": delegation_posture.required_role,
            "available_decision_actions": list(delegation_posture.available_actions),
            "delegation_limitation": delegation_posture.limitation_summary,
        }

    fields: dict[str, object] = {
        "s7_decision_class_id": delegation_posture.decision_class_id,
        "s7_required_role": delegation_posture.required_role,
        "s7_interaction_mode": delegation_posture.interaction_mode,
        "s7_p26_firewall_status": delegation_posture.responsibility_integrity_status,
        "s7_decision_action_exercised": delegation_posture.decision_action_exercised,
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "delegation_contract_ref": delegation_posture.delegation_contract_ref,
                "decision_rights_matrix_ref": delegation_posture.decision_rights_matrix_ref,
                "human_decision_request_ref": delegation_posture.human_decision_request_ref,
                "human_decision_record_ref": delegation_posture.human_decision_record_ref,
                "recommendation_ref": delegation_posture.recommendation_ref,
                "mandate_record_ref": delegation_posture.mandate_record_ref,
                "mandate_source_refs": list(delegation_posture.mandate_source_refs),
                "decision_rights_matrix_row": {
                    "decision_class_id": delegation_posture.decision_class_id,
                    "required_role": delegation_posture.required_role,
                    "interaction_mode": delegation_posture.interaction_mode,
                    "available_actions": list(delegation_posture.available_actions),
                },
                "five_rights_requirement": dict(delegation_posture.five_rights_requirement),
                "five_rights_check": (
                    dict(delegation_posture.five_rights_check)
                    if delegation_posture.five_rights_check is not None
                    else None
                ),
                "responsibility_integrity_check": {
                    "status": delegation_posture.responsibility_integrity_status,
                    "pattern_ids": ["P26", "P20", "P22"],
                    "record_ref": delegation_posture.human_decision_record_ref,
                },
                "decision_options": list(delegation_posture.decision_options),
                "what_changes_under_each_choice": list(
                    delegation_posture.what_changes_under_each_choice
                ),
                "need_reasons": list(delegation_posture.need_reasons),
                "constraint_store_updates": [
                    record.model_dump(mode="json")
                    for record in constraint_store.constraint_records
                    if record.cell_ref == "CROSS_CUTTING.scientist_orchestration"
                ],
                "handoff_rows": list(delegation_posture.handoff_rows),
                "authority_boundary": delegation_posture.authority_boundary.model_dump(
                    mode="json"
                ),
                "governed_pilot_eligible": _s7_governed_pilot_eligible(
                    delegation_posture,
                    blind_spot_posture=blind_spot_posture,
                ),
            }
        )
    return fields


def _s8_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    value_posture: Layer2S8ValuePostureInput,
    s8_firewall: AxisFirewallStatus | None,
    constraint_store: ConstraintStoreSnapshot,
) -> dict[str, object]:
    if audience == "PUBLIC":
        return {
            "value_tradeoff_disclosure_present": True,
            "value_tradeoff_summary": value_posture.limitation_summary,
            "frontier_value_source_note": (
                "Pareto frontier and ranking context depend on an authorized value source; "
                "S2 cannot turn value weights or tradeoffs into production recommendation "
                "authority."
            ),
        }

    action_route = _s8_action_route(value_posture)
    fields: dict[str, object] = {
        "s8_value_disposition": value_posture.disposition,
        "s8_ranking_mode": value_posture.ranking_mode,
        "s8_p20_firewall_status": value_posture.p20_firewall_status,
        "s8_p22_firewall_status": value_posture.p22_firewall_status,
        "s8_p12_firewall_status": "pass" if value_posture.handoff_rows else "limit",
        "s8_p15_firewall_status": (
            "pass"
            if value_posture.authority_boundary.source_authority != "llm_candidate"
            else "block"
        ),
        "s8_p26_firewall_status": (
            "pass" if value_posture.value_authorization_decision_refs else "limit"
        ),
        "s8_action_route": action_route,
        "s8_firewall_status": s8_firewall.status if s8_firewall else "limit",
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "value_choice_provenance_ref": value_posture.value_choice_provenance_ref,
                "authorized_value_schedule_ref": value_posture.authorized_value_schedule_ref,
                "shadow_scenario_value_schedule_refs": list(
                    value_posture.shadow_scenario_value_schedule_refs
                ),
                "objective_function_provenance_ref": (
                    value_posture.objective_function_provenance_ref
                ),
                "pareto_archive_ref": value_posture.pareto_archive_ref,
                "value_tradeoff_disclosure_ref": (
                    value_posture.value_tradeoff_disclosure_ref
                ),
                "mandate_record_ref": value_posture.mandate_record_ref,
                "s6_mandate_firewall_disposition": (
                    value_posture.s6_mandate_firewall_disposition
                ),
                "principal_refs": list(value_posture.principal_refs),
                "principal_conflict_rows": list(value_posture.conflict_rows),
                "affected_group_rows": list(value_posture.affected_group_rows),
                "dissent_refs": list(value_posture.dissent_refs),
                "blocking_rights_refs": list(value_posture.blocking_rights_refs),
                "alternative_schedule_sensitivity": list(
                    value_posture.alternative_schedule_sensitivity
                ),
                "rejected_nondominated_alternative_ids": list(
                    value_posture.rejected_nondominated_alternative_ids
                ),
                "value_provenance_completeness": (
                    value_posture.value_provenance_completeness
                ),
                "integrity_status": _s8_integrity_status(value_posture),
                "authority_boundary": value_posture.authority_boundary.model_dump(
                    mode="json"
                ),
            }
        )
    if audience == "MACHINE":
        fields.update(
            {
                "social_weight_provenance_refs": list(
                    value_posture.social_weight_provenance_refs
                ),
                "delegation_refs": list(value_posture.delegation_refs),
                "value_authorization_decision_refs": list(
                    value_posture.value_authorization_decision_refs
                ),
                "s8_constraint_store_updates": [
                    record.model_dump(mode="json")
                    for record in constraint_store.constraint_records
                    if record.cell_ref == _S8_VALUE_CHOICE_CELL_REF
                ],
                "s8_handoff_rows": [
                    record.model_dump(mode="json")
                    for record in _s8_handoff_records(value_posture)
                ],
                "deterministic_value_replay_refs": _s8_ledger_refs(value_posture),
            }
        )
    return fields


def _s10_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    forecast_posture: Layer2S10ForecastPostureInput,
) -> dict[str, object]:
    if audience == "PUBLIC":
        return {
            "forecast_tier": forecast_posture.forecast_tier,
            "forecast_limitations": [
                forecast_posture.forecast_authority_disposition_reason,
                "forecast support only; not production recommendation authority",
            ],
        }

    fields: dict[str, object] = {
        "forecast_tier": forecast_posture.forecast_tier,
        "forecast_authority_status": forecast_posture.forecast_tier,
        "forecast_authority_disposition_reason": (
            forecast_posture.forecast_authority_disposition_reason
        ),
        "forecast_support_label": forecast_posture.forecast_support_label,
        "forecast_support_ref": forecast_posture.forecast_support_ref,
        "forecast_calibration_record_ref": (
            forecast_posture.forecast_calibration_record_ref
        ),
        "forecast_authority_boundary": forecast_posture.authority_boundary.model_dump(
            mode="json"
        ),
        "weakest_boundary_inherited": True,
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "design_graph_ref": forecast_posture.design_graph_ref,
                "prediction_context_ref": forecast_posture.prediction_context_ref,
                "policy_context_ref": forecast_posture.policy_context_ref,
                "source_contract_ref": forecast_posture.source_contract_ref,
                "method_validity_ref": forecast_posture.method_validity_ref,
                "credible_evaluation_evidence_ref": (
                    forecast_posture.credible_evaluation_evidence_ref
                ),
                "dynamic_equilibrium_check_ref": (
                    forecast_posture.dynamic_equilibrium_check_ref
                ),
                "sensitivity_analysis_ref": forecast_posture.sensitivity_analysis_ref,
                "uncertainty_interval_refs": list(
                    forecast_posture.uncertainty_interval_refs
                ),
                "s5_forecast_support_ref": forecast_posture.s5_forecast_support_ref,
                "s6_firewall_status_refs": list(forecast_posture.s6_firewall_status_refs),
                "s8_value_choice_provenance_ref": (
                    forecast_posture.s8_value_choice_provenance_ref
                ),
                "s8_value_tradeoff_disclosure_ref": (
                    forecast_posture.s8_value_tradeoff_disclosure_ref
                ),
                "welfare_comparison_ref": forecast_posture.welfare_comparison_ref,
                "may_not_use_for": list(forecast_posture.may_not_use_for),
            }
        )
    return fields


def _s11_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    predictive_posture: Layer2S11PredictivePostureInput,
    constraint_store: ConstraintStoreSnapshot,
) -> dict[str, object]:
    if audience == "PUBLIC":
        return {
            "s11_public_limitation": (
                "Predictive relaxation remains limited by calibration and weakest-boundary "
                "checks; it is not recommendation or claim authority."
            ),
            "effective_predictive_posture": predictive_posture.effective_predictive_posture,
            "may_not_be_used_for": _merge_unique_strings(
                predictive_posture.may_not_use_for,
                _S11_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
            ),
            "authority_role": "projection_only",
        }

    s11_constraints = [
        record.model_dump(mode="json")
        for record in constraint_store.constraint_records
        if record.cell_ref
        in {_S11_REGIME_CELL_REF, _S11_FORECAST_QUALITY_CELL_REF}
    ]
    fields: dict[str, object] = {
        "s11_predictive_posture_ref": predictive_posture.predictive_knowledge_ref,
        "effective_predictive_posture": predictive_posture.effective_predictive_posture,
        "predictive_authority_status": predictive_posture.effective_predictive_posture,
        "predictive_axis_upgrade_refs": list(predictive_posture.axis_upgrade_refs),
        "predictive_axis_rows": list(predictive_posture.predictive_axis_rows),
        "per_axis_predictive_calibration_status": (
            predictive_posture.per_axis_predictive_calibration_status
        ),
        "per_axis_predictive_calibration_threshold_ref": (
            predictive_posture.per_axis_predictive_calibration_threshold_ref
        ),
        "proof_carrying_analytics_ref": (
            predictive_posture.proof_carrying_analytics_ref
        ),
        "ir_analytics_bridge_ref": predictive_posture.ir_analytics_bridge_ref,
        "residual_limitation_refs": list(predictive_posture.residual_limitation_refs),
        "weakest_boundary_reason": predictive_posture.weakest_boundary_reason,
        "forecast_quality_disposition": (
            predictive_posture.forecast_quality_disposition
        ),
        "s10_forecast_support_ref": predictive_posture.s10_forecast_support_ref,
        "s10_forecast_tier": predictive_posture.s10_forecast_tier,
        "s11_constraint_store_updates": s11_constraints,
        "predictive_authority_boundary": (
            predictive_posture.authority_boundary.model_dump(mode="json")
        ),
        "may_not_use_for": list(predictive_posture.may_not_use_for),
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "s6_floor_status_refs": list(predictive_posture.s6_floor_status_refs),
                "s6_axis_rows": list(predictive_posture.s6_axis_rows),
                "s6_bridge_consumer_rows": list(
                    predictive_posture.s6_bridge_consumer_rows
                ),
                "s6_constraint_store_update_refs": list(
                    predictive_posture.s6_constraint_store_update_refs
                ),
                "s6_c3_authority_dimension_refs": list(
                    predictive_posture.s6_c3_authority_dimension_refs
                ),
                "post_intervention_dgp_update_ref": (
                    predictive_posture.post_intervention_dgp_update_ref
                ),
                "system_dynamics_handoff_required": (
                    predictive_posture.system_dynamics_handoff_required
                ),
                "s11_calibration_record_refs": list(
                    predictive_posture.s11_calibration_record_refs
                ),
                "method_infrastructure_refs": list(
                    predictive_posture.method_infrastructure_refs
                ),
                "per_axis_predictive_calibration_denominator": (
                    predictive_posture.per_axis_predictive_calibration_denominator
                ),
                "per_axis_predictive_calibration_numerator": (
                    predictive_posture.per_axis_predictive_calibration_numerator
                ),
                "per_axis_predictive_calibration_pass_rate": (
                    predictive_posture.per_axis_predictive_calibration_pass_rate
                ),
            }
        )
    return fields


def _s12_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    resource_posture: Layer2S12ResourceEconomicsPostureInput,
    constraint_store: ConstraintStoreSnapshot,
) -> dict[str, object]:
    if audience == "PUBLIC":
        return {
            "s12_resource_posture_ref": resource_posture.resource_allocation_policy_ref,
            "explore_exploit_posture": resource_posture.explore_exploit_posture,
            "override_rate_trend": resource_posture.override_rate_trend,
            "reuse_rate_trend": resource_posture.reuse_rate_trend,
            "s12_public_growth_limitation": (
                "Resource allocation is a governed growth limitation, not a "
                "recommendation or claim authority."
            ),
            "may_not_be_used_for": _merge_unique_strings(
                resource_posture.may_not_use_for,
                _S12_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
            ),
            "authority_role": "projection_only",
        }

    fields: dict[str, object] = {
        "s12_resource_posture_ref": resource_posture.resource_allocation_policy_ref,
        "resource_allocation_policy_ref": resource_posture.resource_allocation_policy_ref,
        "explore_exploit_posture": resource_posture.explore_exploit_posture,
        "explore_exploit_dial_ref": resource_posture.explore_exploit_dial_ref,
        "delegation_contract_ref": resource_posture.delegation_contract_ref,
        "voi_allocation_refs": list(resource_posture.voi_allocation_refs),
        "voi_site_count": resource_posture.voi_site_count,
        "typed_budget_refs": list(resource_posture.typed_budget_refs),
        "pareto_archive_ref": resource_posture.pareto_archive_ref,
        "envelope_growth_ledger_ref": resource_posture.envelope_growth_ledger_ref,
        "growth_thermometer_ref": resource_posture.growth_thermometer_ref,
        "override_rate_trend": resource_posture.override_rate_trend,
        "reuse_rate_trend": resource_posture.reuse_rate_trend,
        "held_out_status": resource_posture.held_out_status,
        "knowledge_governance_throughput_ledger_ref": (
            resource_posture.knowledge_governance_throughput_ledger_ref
        ),
        "residual_limitation_refs": list(resource_posture.residual_limitation_refs),
        "resource_allocation_disposition": (
            "blocked"
            if resource_posture.explore_exploit_posture == "blocked"
            else "advisory_only"
        ),
        "resource_authority_boundary": resource_posture.authority_boundary.model_dump(
            mode="json"
        ),
        "may_not_be_used_for": list(resource_posture.may_not_use_for),
    }
    if audience in {"EXPERT", "MACHINE"}:
        fields["allocation_priority_rows"] = list(resource_posture.allocation_priority_rows)
        fields["s12_constraint_store_updates"] = [
            record.model_dump(mode="json")
            for record in constraint_store.constraint_records
            if record.cell_ref == _S12_RESOURCE_ECONOMICS_CELL_REF
        ]
    return fields


def _s6_axis_positions(
    blind_spot_posture: Layer2S6BlindSpotPostureInput,
    rule_version_ref: str,
) -> list[AxisPositionDeclaration]:
    positions: list[AxisPositionDeclaration] = []
    for row in blind_spot_posture.axis_rows:
        cell_ref = str(row.get("cell_ref", "UNKNOWN.unknown"))
        cluster, _, axis = cell_ref.partition(".")
        positions.append(
            AxisPositionDeclaration(
                cluster=cluster,
                axis=axis or "unknown",
                position=str(row.get("disposition", "limit")),
                evidence_refs=[str(row["record_ref"])] if row.get("record_ref") else [],
                authority_purpose="fail_closed_blind_spot_firewall",
                rule_version_ref=rule_version_ref,
            )
        )
    return positions


def _s6_firewall_statuses(
    blind_spot_posture: Layer2S6BlindSpotPostureInput,
    rule_version_ref: str,
) -> list[AxisFirewallStatus]:
    statuses: list[AxisFirewallStatus] = []
    for row in blind_spot_posture.axis_rows:
        status = str(row.get("disposition", "limit"))
        if status not in {"pass", "limit", "block"}:
            status = "limit"
        statuses.append(
            AxisFirewallStatus(
                cell_ref=str(row.get("cell_ref", "UNKNOWN.unknown")),
                status=status,  # type: ignore[arg-type]
                pattern_ids=[str(row.get("firewall_pattern_id", "P18"))],
                reason=str(row.get("decision_reason", blind_spot_posture.limitation_summary)),
                maturity="fail_closed",
                rule_version_ref=rule_version_ref,
            )
        )
    return statuses


def _s6_constraint_entries(
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None,
) -> list[ConstraintStoreEntry]:
    if blind_spot_posture is None:
        return []
    return [
        ConstraintStoreEntry.model_validate(update)
        for update in blind_spot_posture.constraint_store_updates
    ]


def _s7_constraint_entries(
    delegation_posture: Layer2S7DelegationPostureInput | None,
) -> list[ConstraintStoreEntry]:
    if delegation_posture is None:
        return []
    return [
        ConstraintStoreEntry.model_validate(update)
        for update in delegation_posture.constraint_store_updates
    ]


def _s8_constraint_entries(
    value_posture: Layer2S8ValuePostureInput | None,
    *,
    case_slug: str,
    ranked_value_choice_attempted: bool,
    rule_version_ref: str,
) -> list[ConstraintStoreEntry]:
    if value_posture is not None:
        return [
            ConstraintStoreEntry.model_validate(update)
            for update in value_posture.constraint_store_updates
        ]
    if not ranked_value_choice_attempted:
        return []
    return [
        ConstraintStoreEntry(
            constraint_id=f"layer2.s8.{case_slug}.missing_value_provenance",
            cell_ref=_S8_VALUE_CHOICE_CELL_REF,
            status="block",
            source_ref="pdc://layer2/s8/missing-value-choice-provenance",
            consumer_ref="INTERVENTION.design_candidate",
            refinement_route="block_candidate",
            evidence_refs=[],
            reason=(
                "Ranked value choice attempted without injected S8 value-choice "
                "provenance."
            ),
            rule_version_ref=rule_version_ref,
        )
    ]


def _s11_constraint_entries(
    predictive_posture: Layer2S11PredictivePostureInput | None,
    *,
    case_slug: str,
) -> list[ConstraintStoreEntry]:
    if predictive_posture is None:
        return []

    status = _s11_constraint_status(predictive_posture)
    route: ConstraintRefinementRoute = (
        "block_candidate" if status == "block" else "pending_consumer_constraint"
    )
    refs = _s11_design_record_ledger_refs(predictive_posture)
    entries: list[ConstraintStoreEntry] = []
    if (
        predictive_posture.regime_strategy_constraint_ref is not None
        or _s11_calibration_limits_downstream(predictive_posture)
        or predictive_posture.effective_predictive_posture == "fail_closed"
    ):
        entries.append(
            ConstraintStoreEntry(
                constraint_id=f"layer2.s11.{case_slug}.regime_strategy_constraint",
                cell_ref=_S11_REGIME_CELL_REF,
                status=status,
                source_ref=(
                    predictive_posture.regime_strategy_constraint_ref
                    or f"constraint://s11/regime/{case_slug}"
                ),
                consumer_ref="Layer2S2DesignSearchRun.predictive_posture",
                refinement_route=route,
                evidence_refs=refs,
                reason=(
                    "S11 predictive posture constrains regime strategy without rerunning "
                    "S4 classification."
                ),
                rule_version_ref=predictive_posture.rule_version_ref,
            )
        )
    if (
        predictive_posture.forecast_quality_disposition
        != "unchanged_s10_tier_consumed"
        or _s11_calibration_limits_downstream(predictive_posture)
    ):
        entries.append(
            ConstraintStoreEntry(
                constraint_id=f"layer2.s11.{case_slug}.forecast_quality_constraint",
                cell_ref=_S11_FORECAST_QUALITY_CELL_REF,
                status=(
                    "block"
                    if predictive_posture.forecast_quality_disposition
                    == "blocked_by_s11_calibration"
                    else "limit"
                ),
                source_ref=f"constraint://s11/forecast-quality/{case_slug}",
                consumer_ref="Layer2S2DesignSearchRun.predictive_posture",
                refinement_route=(
                    "block_candidate"
                    if predictive_posture.forecast_quality_disposition
                    == "blocked_by_s11_calibration"
                    else "pending_consumer_constraint"
                ),
                evidence_refs=refs,
                reason=(
                    "S11 calibration downgrades forecast-quality use while preserving "
                    f"S10 forecast_tier={predictive_posture.s10_forecast_tier}."
                ),
                rule_version_ref=predictive_posture.rule_version_ref,
            )
        )
    return entries


def _s12_constraint_entries(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
    *,
    case_slug: str,
) -> list[ConstraintStoreEntry]:
    if resource_posture is None:
        return []
    status: ConstraintRecordStatus = (
        "block" if resource_posture.explore_exploit_posture == "blocked" else "limit"
    )
    route: ConstraintRefinementRoute = (
        "block_candidate" if status == "block" else "pending_consumer_constraint"
    )
    reason = (
        "S12 resource allocation posture is consumed as typed allocation priority "
        "and growth limitation only, not as recommendation authority."
    )
    return [
        ConstraintStoreEntry(
            constraint_id=f"layer2.s12.{case_slug}.resource_allocation_constraint",
            cell_ref=_S12_RESOURCE_ECONOMICS_CELL_REF,
            status=status,
            source_ref=resource_posture.resource_allocation_policy_ref,
            consumer_ref="Layer2S2DesignSearchRun.resource_posture",
            refinement_route=route,
            evidence_refs=_s12_design_record_ledger_refs(resource_posture),
            reason=reason,
            rule_version_ref=resource_posture.rule_version_ref,
        )
    ]


def _s6_refinement_decision(
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None,
) -> RefinementDecisionKind | None:
    if blind_spot_posture is None or blind_spot_posture.overall_posture == "clear_fail_closed":
        return None
    priority: dict[str, RefinementDecisionKind] = {
        "block_candidate": "block_candidate",
        "acquire": "acquire",
        "reframe": "reframe",
        "human_decision": "human_decision",
        "pending_consumer_constraint": "acquire",
    }
    for route in priority:
        if any(
            update.get("refinement_route") == route
            for update in blind_spot_posture.constraint_store_updates
        ):
            return priority[route]
    if blind_spot_posture.overall_posture == "blocked":
        return "block_candidate"
    return "acquire"


def _s11_refinement_decision(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> RefinementDecisionKind | None:
    if predictive_posture is None:
        return None
    if (
        predictive_posture.effective_predictive_posture == "fail_closed"
        or predictive_posture.forecast_quality_disposition
        == "blocked_by_s11_calibration"
    ):
        return "block_candidate"
    return None


def _s6_ledger_refs(blind_spot_posture: Layer2S6BlindSpotPostureInput) -> list[str]:
    refs = [
        blind_spot_posture.measurability_record_ref,
        blind_spot_posture.aggregation_validity_record_ref,
        blind_spot_posture.capacity_feasibility_record_ref,
        blind_spot_posture.mandate_legitimacy_record_ref,
        blind_spot_posture.strategic_response_record_ref,
        *blind_spot_posture.cluster_authority_dimension_refs,
    ]
    return list(dict.fromkeys(refs))[:40]


def _s7_ledger_refs(delegation_posture: Layer2S7DelegationPostureInput) -> list[str]:
    refs = [
        delegation_posture.delegation_contract_ref,
        delegation_posture.decision_rights_matrix_ref,
        delegation_posture.human_decision_request_ref,
        delegation_posture.human_decision_record_ref,
        delegation_posture.recommendation_ref,
        delegation_posture.mandate_record_ref,
        *delegation_posture.mandate_source_refs,
        *delegation_posture.provenance_refs,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:40]


def _s7_delegation_request_refs(
    delegation_posture: Layer2S7DelegationPostureInput | None,
) -> list[str]:
    if delegation_posture is None:
        return []
    return [delegation_posture.human_decision_request_ref]


def _s7_delegation_record_refs(
    delegation_posture: Layer2S7DelegationPostureInput | None,
) -> list[str]:
    if delegation_posture is None or delegation_posture.human_decision_record_ref is None:
        return []
    return [delegation_posture.human_decision_record_ref]


def _s7_handoff_refs(
    delegation_posture: Layer2S7DelegationPostureInput | None,
) -> list[str]:
    if delegation_posture is None:
        return []
    return [
        str(row["handoff_id"])
        for row in delegation_posture.handoff_rows
        if row.get("handoff_id")
    ][:40]


def _s7_delegation_status(
    delegation_posture: Layer2S7DelegationPostureInput | None,
) -> Literal["not_applicable", "requested", "recorded", "blocked", "no_interrupt"]:
    if delegation_posture is None:
        return "not_applicable"
    if delegation_posture.disposition.startswith("blocked_"):
        return "blocked"
    if delegation_posture.disposition == "recorded_valid_decision":
        return "recorded"
    if delegation_posture.disposition == "no_interrupt":
        return "no_interrupt"
    return "requested"


def _s8_refinement_decision(
    value_posture: Layer2S8ValuePostureInput | None,
    *,
    ranked_value_choice_attempted: bool,
) -> RefinementDecisionKind | None:
    if value_posture is None:
        return "block_candidate" if ranked_value_choice_attempted else None
    if _s8_blocks_ranked_selection(value_posture):
        return "block_candidate"
    if value_posture.disposition in {"contested_multi_principal", "advisory_only"}:
        return "human_decision"
    if value_posture.disposition == "shadow_scenario_only" and value_posture.ranking_mode != (
        "unranked_frontier_only"
    ):
        return "block_candidate"
    return None


def _s8_run_status(
    value_posture: Layer2S8ValuePostureInput | None,
    *,
    ranked_value_choice_attempted: bool,
    fallback: S2RunStatus,
) -> S2RunStatus:
    decision = _s8_refinement_decision(
        value_posture,
        ranked_value_choice_attempted=ranked_value_choice_attempted,
    )
    if decision == "block_candidate":
        return "blocked"
    if decision == "human_decision" and fallback == "shadow_ready":
        return "governance_required"
    return fallback


def _s8_iteration_status(
    value_posture: Layer2S8ValuePostureInput | None,
    *,
    ranked_value_choice_attempted: bool,
    fallback: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ],
) -> Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "refined_shadow",
]:
    decision = _s8_refinement_decision(
        value_posture,
        ranked_value_choice_attempted=ranked_value_choice_attempted,
    )
    if decision == "block_candidate":
        return "blocked"
    if decision == "human_decision" and fallback == "refined_shadow":
        return "governance_required"
    return fallback


def _s8_blocks_ranked_selection(value_posture: Layer2S8ValuePostureInput) -> bool:
    return (
        value_posture.disposition.startswith("blocked_")
        or value_posture.p20_firewall_status == "block"
        or value_posture.p22_firewall_status == "block"
        or (
            value_posture.disposition == "shadow_scenario_only"
            and value_posture.ranking_mode != "unranked_frontier_only"
        )
    )


def _attempts_ranked_value_choice(
    *,
    design_strategy: str | None,
    counterexample_class: str | None,
) -> bool:
    return (
        design_strategy == "expected_welfare_optimization"
        or counterexample_class == "value_gap"
    )


def _s7_run_status(
    delegation_posture: Layer2S7DelegationPostureInput | None,
    *,
    fallback: S2RunStatus,
) -> S2RunStatus:
    if delegation_posture is None:
        return fallback
    if delegation_posture.disposition.startswith("blocked_"):
        return "blocked"
    if delegation_posture.disposition == "request_human_decision":
        return "governance_required"
    return fallback


def _s7_iteration_status(
    delegation_posture: Layer2S7DelegationPostureInput | None,
    *,
    fallback: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ],
) -> Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "refined_shadow",
]:
    if delegation_posture is None:
        return fallback
    if delegation_posture.disposition.startswith("blocked_"):
        return "blocked"
    if delegation_posture.disposition == "request_human_decision":
        return "governance_required"
    return fallback


def _s7_axis_position(
    delegation_posture: Layer2S7DelegationPostureInput,
    rule_version_ref: str,
) -> AxisPositionDeclaration:
    return AxisPositionDeclaration(
        cluster="CROSS_CUTTING",
        axis="scientist_orchestration",
        position=delegation_posture.disposition,
        evidence_refs=_s7_ledger_refs(delegation_posture),
        authority_purpose="mandate_bounded_delegation_handoff",
        rule_version_ref=rule_version_ref,
    )


def _s7_firewall_status(
    delegation_posture: Layer2S7DelegationPostureInput,
    rule_version_ref: str,
) -> AxisFirewallStatus:
    if delegation_posture.disposition.startswith("blocked_"):
        status: Literal["pass", "warn", "limit", "block"] = "block"
    elif delegation_posture.responsibility_integrity_status == "pass":
        status = "pass"
    else:
        status = "limit"
    return AxisFirewallStatus(
        cell_ref="CROSS_CUTTING.scientist_orchestration",
        status=status,
        pattern_ids=["P26", "P12", "P15", "P20", "P22"],
        reason=(
            "S7 injected mandate-bounded delegation posture; S2 consumes typed refs "
            "without creating approval authority."
        ),
        maturity="fail_closed",
        rule_version_ref=rule_version_ref,
    )


def _s8_axis_position(
    value_posture: Layer2S8ValuePostureInput,
    rule_version_ref: str,
) -> AxisPositionDeclaration:
    return AxisPositionDeclaration(
        cluster="ACTOR",
        axis="value_choice_provenance",
        position=f"{value_posture.disposition};ranking_mode={value_posture.ranking_mode}",
        evidence_refs=_s8_ledger_refs(value_posture),
        authority_purpose="authorized_value_choice_provenance",
        rule_version_ref=rule_version_ref,
    )


def _s8_firewall_status(
    value_posture: Layer2S8ValuePostureInput,
    rule_version_ref: str,
) -> AxisFirewallStatus:
    if _s8_blocks_ranked_selection(value_posture):
        status: Literal["pass", "warn", "limit", "block"] = "block"
    elif (
        value_posture.disposition in {"authorized"}
        and value_posture.p20_firewall_status == "pass"
    ):
        status = "pass"
    elif value_posture.disposition == "contested_multi_principal":
        status = "limit"
    else:
        status = "limit"
    return AxisFirewallStatus(
        cell_ref=_S8_VALUE_CHOICE_CELL_REF,
        status=status,
        pattern_ids=["P20", "P22", "P12", "P15", "P26"],
        reason=(
            "S8 injected value-choice posture gates ranked value choices; S2 consumes "
            "refs without selecting social weights or minting recommendation authority."
        ),
        maturity="fail_closed",
        rule_version_ref=rule_version_ref,
    )


def _s10_axis_position(
    forecast_posture: Layer2S10ForecastPostureInput,
) -> AxisPositionDeclaration:
    return AxisPositionDeclaration(
        cluster="KNOWLEDGE",
        axis="outcome_prediction_welfare_comparison",
        position=(
            f"forecast_tier={forecast_posture.forecast_tier};"
            f"support_label={forecast_posture.forecast_support_label}"
        ),
        evidence_refs=_s10_design_record_ledger_refs(forecast_posture),
        authority_purpose="forecast_support_posture_consumption",
        rule_version_ref=forecast_posture.rule_version_ref,
    )


def _s10_firewall_status(
    forecast_posture: Layer2S10ForecastPostureInput,
) -> AxisFirewallStatus:
    status: Literal["pass", "warn", "limit", "block"]
    if forecast_posture.forecast_tier in {"blocked", "equilibrium_contested_blocked"}:
        status = "block"
    elif forecast_posture.forecast_tier == "observable_calibrated":
        status = "pass"
    else:
        status = "limit"
    return AxisFirewallStatus(
        cell_ref="KNOWLEDGE.outcome_prediction_welfare_comparison",
        status=status,
        pattern_ids=["P05", "P10", "P17", "P20", "P24", "P25"],
        reason=(
            "S10 injected forecast-support posture; S2 consumes refs without "
            "recomputing forecast authority or creating recommendation authority."
        ),
        maturity="fail_closed",
        rule_version_ref=forecast_posture.rule_version_ref,
    )


def _s11_axis_position(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> AxisPositionDeclaration:
    return AxisPositionDeclaration(
        cluster="KNOWLEDGE",
        axis="predictive_knowledge_relaxation",
        position=(
            f"effective_predictive_posture="
            f"{predictive_posture.effective_predictive_posture};"
            f"calibration_status="
            f"{predictive_posture.per_axis_predictive_calibration_status}"
        ),
        evidence_refs=_s11_design_record_ledger_refs(predictive_posture),
        authority_purpose="predictive_posture_constraint_consumption",
        rule_version_ref=predictive_posture.rule_version_ref,
    )


def _s11_firewall_status(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> AxisFirewallStatus:
    status = _s11_constraint_status(predictive_posture)
    return AxisFirewallStatus(
        cell_ref="KNOWLEDGE.predictive_knowledge_relaxation",
        status=status,
        pattern_ids=["P05", "P10", "P18", "P21", "P24"],
        reason=(
            "S11 injected predictive posture is consumed as constraint data only; "
            f"{predictive_posture.weakest_boundary_reason}"
        ),
        maturity="fail_closed",
        rule_version_ref=predictive_posture.rule_version_ref,
    )


def _s12_axis_position(
    resource_posture: Layer2S12ResourceEconomicsPostureInput,
) -> AxisPositionDeclaration:
    return AxisPositionDeclaration(
        cluster="INTERVENTION",
        axis="resource_economics",
        position=(
            f"explore_exploit_posture={resource_posture.explore_exploit_posture};"
            f"voi_site_count={resource_posture.voi_site_count};"
            f"held_out_status={resource_posture.held_out_status}"
        ),
        evidence_refs=_s12_design_record_ledger_refs(resource_posture),
        authority_purpose="resource_posture_constraint_consumption",
        rule_version_ref=resource_posture.rule_version_ref,
    )


def _s12_firewall_status(
    resource_posture: Layer2S12ResourceEconomicsPostureInput,
) -> AxisFirewallStatus:
    status: Literal["pass", "warn", "limit", "block"] = (
        "block" if resource_posture.explore_exploit_posture == "blocked" else "limit"
    )
    if (
        resource_posture.override_rate_trend in {"improving", "flat"}
        and resource_posture.reuse_rate_trend in {"improving", "flat"}
        and resource_posture.held_out_status == "pending_s14"
        and resource_posture.explore_exploit_posture != "blocked"
    ):
        status = "pass"
    return AxisFirewallStatus(
        cell_ref=_S12_RESOURCE_ECONOMICS_CELL_REF,
        status=status,
        pattern_ids=["P03", "P04", "P05", "P10", "P13", "P15"],
        reason=(
            "S12 injected resource posture is consumed as constraint and allocation "
            "priority data only; it cannot authorize recommendations, claims, S13 "
            "shrinkage, or S14 universality."
        ),
        maturity="fail_closed",
        rule_version_ref=resource_posture.rule_version_ref,
    )


def _s11_constraint_status(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> Literal["pass", "warn", "limit", "block"]:
    if (
        predictive_posture.effective_predictive_posture == "fail_closed"
        or predictive_posture.forecast_quality_disposition
        == "blocked_by_s11_calibration"
    ):
        return "block"
    if _s11_calibration_limits_downstream(predictive_posture):
        return "limit"
    if predictive_posture.effective_predictive_posture == "limited_by_weakest_boundary":
        return "limit"
    return "pass"


def _s11_calibration_limits_downstream(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> bool:
    return (
        predictive_posture.per_axis_predictive_calibration_status
        in {"absent", "stale", "poor", "out_of_scope"}
        or predictive_posture.forecast_quality_disposition
        != "unchanged_s10_tier_consumed"
    )


def _s11_run_status(
    predictive_posture: Layer2S11PredictivePostureInput | None,
    *,
    fallback: S2RunStatus,
) -> S2RunStatus:
    if _s11_refinement_decision(predictive_posture) == "block_candidate":
        return "blocked"
    return fallback


def _s11_iteration_status(
    predictive_posture: Layer2S11PredictivePostureInput | None,
    *,
    fallback: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ],
) -> Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "refined_shadow",
]:
    if _s11_refinement_decision(predictive_posture) == "block_candidate":
        return "blocked"
    return fallback


def _s8_ledger_refs(value_posture: Layer2S8ValuePostureInput) -> list[str]:
    refs = [
        value_posture.value_choice_provenance_ref,
        value_posture.authorized_value_schedule_ref,
        *value_posture.shadow_scenario_value_schedule_refs,
        value_posture.objective_function_provenance_ref,
        value_posture.pareto_archive_ref,
        value_posture.value_tradeoff_disclosure_ref,
        value_posture.mandate_record_ref,
        *value_posture.social_weight_provenance_refs,
        *value_posture.delegation_refs,
        *value_posture.value_authorization_decision_refs,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:40]


def _s8_value_choice_provenance_refs(
    value_posture: Layer2S8ValuePostureInput | None,
) -> list[str]:
    if value_posture is None:
        return []
    return [value_posture.value_choice_provenance_ref]


def _s8_pareto_archive_refs(value_posture: Layer2S8ValuePostureInput | None) -> list[str]:
    if value_posture is None:
        return []
    return [value_posture.pareto_archive_ref]


def _s8_authorized_value_schedule_refs(
    value_posture: Layer2S8ValuePostureInput | None,
) -> list[str]:
    if value_posture is None or value_posture.authorized_value_schedule_ref is None:
        return []
    return [value_posture.authorized_value_schedule_ref]


def _s8_shadow_scenario_value_schedule_refs(
    value_posture: Layer2S8ValuePostureInput | None,
) -> list[str]:
    if value_posture is None:
        return []
    return list(value_posture.shadow_scenario_value_schedule_refs)


def _s8_value_authorization_decision_refs(
    value_posture: Layer2S8ValuePostureInput | None,
) -> list[str]:
    if value_posture is None:
        return []
    return list(value_posture.value_authorization_decision_refs)


def _s8_value_choice_status(value_posture: Layer2S8ValuePostureInput | None) -> str:
    if value_posture is None:
        return "not_applicable"
    return value_posture.disposition


def _s10_forecast_support_refs(
    forecast_posture: Layer2S10ForecastPostureInput | None,
) -> list[str]:
    if forecast_posture is None:
        return []
    return [forecast_posture.forecast_support_ref]


def _s10_forecast_calibration_record_refs(
    forecast_posture: Layer2S10ForecastPostureInput | None,
) -> list[str]:
    if forecast_posture is None or forecast_posture.forecast_calibration_record_ref is None:
        return []
    return [forecast_posture.forecast_calibration_record_ref]


def _s10_forecast_posture_refs(
    forecast_posture: Layer2S10ForecastPostureInput | None,
) -> list[str]:
    if forecast_posture is None:
        return []
    refs = [
        forecast_posture.design_graph_ref,
        forecast_posture.prediction_context_ref,
        forecast_posture.policy_context_ref,
        forecast_posture.welfare_comparison_ref,
        forecast_posture.observable_subset_ref,
        *forecast_posture.uncertainty_interval_refs,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:40]


def _s10_forecast_authority_status(
    forecast_posture: Layer2S10ForecastPostureInput | None,
) -> str:
    if forecast_posture is None:
        return "not_applicable"
    return forecast_posture.forecast_tier


def _s10_design_record_ledger_refs(
    forecast_posture: Layer2S10ForecastPostureInput,
) -> list[str]:
    refs = [
        forecast_posture.forecast_support_ref,
        forecast_posture.forecast_calibration_record_ref
        or forecast_posture.welfare_comparison_ref
        or forecast_posture.design_graph_ref,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:2]


def _s11_design_record_ledger_refs(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> list[str]:
    refs = [
        predictive_posture.predictive_knowledge_ref,
        predictive_posture.proof_carrying_analytics_ref,
        predictive_posture.ir_analytics_bridge_ref,
        predictive_posture.s10_forecast_support_ref,
        predictive_posture.post_intervention_dgp_update_ref,
        *predictive_posture.axis_upgrade_refs,
        *predictive_posture.s11_calibration_record_refs,
        *predictive_posture.residual_limitation_refs,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:40]


def _s11_predictive_knowledge_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return [predictive_posture.predictive_knowledge_ref]


def _s11_predictive_axis_upgrade_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return list(predictive_posture.axis_upgrade_refs)


def _s11_proof_carrying_analytics_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return [predictive_posture.proof_carrying_analytics_ref]


def _s11_ir_analytics_bridge_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return [predictive_posture.ir_analytics_bridge_ref]


def _s11_calibration_record_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return list(predictive_posture.s11_calibration_record_refs)


def _s11_forecast_quality_constraint_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return [
        entry.source_ref
        for entry in _s11_constraint_entries(
            predictive_posture,
            case_slug=_slug(predictive_posture.predictive_knowledge_ref),
        )
        if entry.cell_ref == _S11_FORECAST_QUALITY_CELL_REF
    ][:40]


def _s11_regime_strategy_constraint_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    refs = [
        entry.source_ref
        for entry in _s11_constraint_entries(
            predictive_posture,
            case_slug=_slug(predictive_posture.predictive_knowledge_ref),
        )
        if entry.cell_ref == _S11_REGIME_CELL_REF
    ]
    return refs[:40]


def _s11_residual_limitation_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return list(predictive_posture.residual_limitation_refs)


def _s11_predictive_posture_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return _s11_design_record_ledger_refs(predictive_posture)


def _s11_predictive_authority_status(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> str:
    if predictive_posture is None:
        return "not_applicable"
    return predictive_posture.effective_predictive_posture


def _s12_design_record_ledger_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput,
) -> list[str]:
    refs = [
        resource_posture.resource_allocation_policy_ref,
        resource_posture.pareto_archive_ref,
        resource_posture.envelope_growth_ledger_ref,
        resource_posture.growth_thermometer_ref,
        resource_posture.knowledge_governance_throughput_ledger_ref,
        *resource_posture.voi_allocation_refs,
        *resource_posture.typed_budget_refs,
        *resource_posture.residual_limitation_refs,
    ]
    return [ref for ref in dict.fromkeys(refs) if ref is not None][:40]


def _s12_resource_allocation_policy_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> list[str]:
    if resource_posture is None:
        return []
    return [resource_posture.resource_allocation_policy_ref]


def _s12_envelope_growth_ledger_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> list[str]:
    if resource_posture is None:
        return []
    return [resource_posture.envelope_growth_ledger_ref]


def _s12_growth_thermometer_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> list[str]:
    if resource_posture is None:
        return []
    return [resource_posture.growth_thermometer_ref]


def _s12_voi_allocation_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> list[str]:
    if resource_posture is None:
        return []
    return list(resource_posture.voi_allocation_refs)


def _s12_explore_exploit_posture(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> str:
    if resource_posture is None:
        return "not_applicable"
    return resource_posture.explore_exploit_posture


def _s8_handoff_refs(value_posture: Layer2S8ValuePostureInput | None) -> list[str]:
    if value_posture is None:
        return []
    return [record.handoff_id for record in _s8_handoff_records(value_posture)][:40]


def _s11_handoff_refs(
    predictive_posture: Layer2S11PredictivePostureInput | None,
) -> list[str]:
    if predictive_posture is None:
        return []
    return [_s11_handoff_record(predictive_posture).handoff_id]


def _s12_handoff_refs(
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None,
) -> list[str]:
    if resource_posture is None:
        return []
    return [_s12_handoff_record(resource_posture).handoff_id]


def _s8_handoff_records(value_posture: Layer2S8ValuePostureInput) -> list[ClusterHandoffRecord]:
    if not value_posture.handoff_rows:
        return [
            ClusterHandoffRecord(
                handoff_id="layer2.s2.handoff.s8_value_choice_posture",
                workflow_ref="workflow://layer2/s2/shadow-design-loop",
                source_cell_ref=_S8_VALUE_CHOICE_CELL_REF,
                target_cell_ref="INTERVENTION.design_candidate",
                artifact_refs=[
                    value_posture.value_choice_provenance_ref,
                    value_posture.pareto_archive_ref,
                ],
                disposition=_s8_handoff_disposition(value_posture),
                authority_purpose="s8_value_choice_firewall",
                may_not_use_for=list(_S8_REQUIRED_HANDOFF_MAY_NOT_USE_FOR),
            )
        ]
    records: list[ClusterHandoffRecord] = []
    for row in value_posture.handoff_rows:
        payload = dict(row)
        payload.setdefault("source_cell_ref", _S8_VALUE_CHOICE_CELL_REF)
        payload.setdefault("target_cell_ref", "INTERVENTION.design_candidate")
        payload.setdefault("authority_purpose", "s8_value_choice_firewall")
        payload["may_not_use_for"] = _merge_unique_strings(
            payload.get("may_not_use_for"),
            _S8_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
        )
        records.append(ClusterHandoffRecord.model_validate(payload))
    return records


def _s8_handoff_disposition(
    value_posture: Layer2S8ValuePostureInput,
) -> Literal["emitted", "consumed", "rejected", "blocked"]:
    if _s8_blocks_ranked_selection(value_posture):
        return "blocked"
    if value_posture.disposition == "shadow_scenario_only":
        return "rejected"
    return "consumed"


def _s10_handoff_record(
    forecast_posture: Layer2S10ForecastPostureInput,
) -> ClusterHandoffRecord:
    return ClusterHandoffRecord(
        handoff_id="layer2.s2.handoff.s10_forecast_posture",
        workflow_ref="workflow://layer2/s2/shadow-design-loop",
        source_cell_ref="KNOWLEDGE.outcome_prediction_welfare_comparison",
        target_cell_ref="INTERVENTION.design_candidate",
        artifact_refs=[
            forecast_posture.forecast_support_ref,
            *[
                ref
                for ref in (
                    forecast_posture.forecast_calibration_record_ref,
                    forecast_posture.design_graph_ref,
                    forecast_posture.prediction_context_ref,
                )
                if ref is not None
            ],
        ],
        disposition="consumed",
        authority_purpose=(
            "Layer2S10ForecastPostureInput forecast_support_posture_consumed"
        ),
        may_not_use_for=_merge_unique_strings(
            forecast_posture.may_not_use_for,
            _S10_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
        ),
    )


def _s11_handoff_record(
    predictive_posture: Layer2S11PredictivePostureInput,
) -> ClusterHandoffRecord:
    return ClusterHandoffRecord(
        handoff_id="layer2.s2.handoff.s11_predictive_posture",
        workflow_ref="workflow://layer2/s2/shadow-design-loop",
        source_cell_ref="KNOWLEDGE.predictive_knowledge_relaxation",
        target_cell_ref="INTERVENTION.design_candidate",
        artifact_refs=_s11_predictive_posture_refs(predictive_posture),
        disposition=(
            "blocked"
            if _s11_refinement_decision(predictive_posture) == "block_candidate"
            else "consumed"
        ),
        authority_purpose=(
            "Layer2S11PredictivePostureInput predictive_axis_maturity_upgrade "
            "constraint_consumed"
        ),
        may_not_use_for=_merge_unique_strings(
            predictive_posture.may_not_use_for,
            _S11_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
        ),
    )


def _s12_handoff_record(
    resource_posture: Layer2S12ResourceEconomicsPostureInput,
) -> ClusterHandoffRecord:
    return ClusterHandoffRecord(
        handoff_id="layer2.s2.handoff.s12_resource_posture",
        workflow_ref="workflow://layer2/s2/shadow-design-loop",
        source_cell_ref=_S12_RESOURCE_ECONOMICS_CELL_REF,
        target_cell_ref="INTERVENTION.design_candidate",
        artifact_refs=_s12_design_record_ledger_refs(resource_posture),
        disposition=(
            "blocked"
            if resource_posture.explore_exploit_posture == "blocked"
            else "consumed"
        ),
        authority_purpose=(
            "Layer2S12ResourceEconomicsPostureInput allocation_priority_input "
            "constraint_consumed"
        ),
        may_not_use_for=_merge_unique_strings(
            resource_posture.may_not_use_for,
            _S12_REQUIRED_HANDOFF_MAY_NOT_USE_FOR,
        ),
    )


def _s8_action_route(value_posture: Layer2S8ValuePostureInput) -> str:
    decision = _s8_refinement_decision(
        value_posture,
        ranked_value_choice_attempted=value_posture.ranking_mode
        in {"ranked_with_authorized_values", "shadow_scenario_ranking"},
    )
    return decision or "none"


def _s8_integrity_status(value_posture: Layer2S8ValuePostureInput) -> str:
    if (
        value_posture.p20_firewall_status == "block"
        or value_posture.p22_firewall_status == "block"
    ):
        return "block"
    if (
        value_posture.disposition == "authorized"
        and value_posture.value_provenance_completeness == 1
    ):
        return "pass"
    return "limit"


def _merge_unique_strings(value: object, required: list[str]) -> list[str]:
    items: list[str] = []
    if isinstance(value, list):
        items.extend(str(item) for item in value if item)
    items.extend(required)
    return list(dict.fromkeys(items))[:40]


def _s7_governed_pilot_eligible(
    delegation_posture: Layer2S7DelegationPostureInput,
    *,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None,
) -> bool:
    return (
        delegation_posture.governed_pilot_eligible
        and delegation_posture.disposition == "recorded_valid_decision"
        and delegation_posture.human_decision_record_ref is not None
        and delegation_posture.responsibility_integrity_status == "pass"
        and delegation_posture.s6_mandate_firewall_disposition == "pass"
        and blind_spot_posture is not None
        and blind_spot_posture.overall_posture == "clear_fail_closed"
    )


def _is_s6_cell(cell_ref: str) -> bool:
    return cell_ref in {
        "SYSTEM.measurability",
        "SYSTEM.subject_granularity",
        "ACTOR.state_capacity_feasibility",
        "ACTOR.mandate_legitimacy",
        "OTHER_AGENTS.strategic_response",
    }


def _composition_limitation(
    composition_posture: Layer2S5CompositionPostureInput,
) -> str:
    return (
        f"{composition_posture.coupling_regime} coupling with "
        f"{composition_posture.composition_disposition} composition is S5 shadow routing only; "
        "whole-design authority remains limited by the S5 receipt, P17 firewall, and system "
        "evidence obligations."
    )


def _composition_strategy(
    composition_posture: Layer2S5CompositionPostureInput,
) -> str:
    if composition_posture.composition_disposition == "compose":
        return "compose_critical_path_shadow_only"
    if composition_posture.composition_disposition == "compose_with_limitations":
        return "compose_with_s5_limitations"
    if composition_posture.composition_disposition == "system_evidence_required":
        return "require_system_evidence_or_decompose"
    return "blocked_until_s5_repair"


def _dynamics_axis_position(composition_posture: Layer2S5CompositionPostureInput) -> str:
    residual_risk = composition_posture.residual_interaction_risk or "unknown"
    return ";".join(
        [
            f"dynamics_requirement_ref={composition_posture.dynamics_requirement_ref or 'none'}",
            f"forecast_support_label={composition_posture.forecast_support_label or 'none'}",
            f"residual_interaction_risk={residual_risk}",
        ]
    )


def _composition_axis_position(composition_posture: Layer2S5CompositionPostureInput) -> str:
    residual_risk = composition_posture.residual_interaction_risk or "unknown"
    return ";".join(
        [
            f"composition_disposition={composition_posture.composition_disposition}",
            f"authority_mode={composition_posture.authority_mode}",
            f"residual_interaction_risk={residual_risk}",
        ]
    )


def _coupling_firewall_status(
    composition_posture: Layer2S5CompositionPostureInput,
) -> Literal["pass", "warn", "limit", "block"]:
    if composition_posture.coupling_regime == "modular":
        return "pass"
    if composition_posture.coupling_regime == "entangled":
        return "block"
    return "limit"


def _dynamics_firewall_status(
    composition_posture: Layer2S5CompositionPostureInput,
) -> Literal["pass", "warn", "limit", "block"]:
    if composition_posture.composition_disposition in {"system_evidence_required", "blocked"}:
        return "block"
    if (
        composition_posture.dynamics_requirement_ref
        or composition_posture.residual_interaction_risk
    ):
        return "limit"
    return "pass"


def _composition_firewall_status(
    composition_posture: Layer2S5CompositionPostureInput,
) -> Literal["pass", "warn", "limit", "block"]:
    if composition_posture.composition_disposition == "compose":
        return "pass"
    if composition_posture.composition_disposition == "blocked":
        return "block"
    return "limit"


def _commitment_axis_position(
    *,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
    design_strategy: str | None,
) -> str:
    return ";".join(
        [
            f"stakes={commitment_stakes or 'unknown'}",
            "lifecycle_stage=see_commitment_profile",
            f"selected_floor={_selected_floor_for_commitment(commitment_stakes)}",
            f"design_strategy={design_strategy or 'not_injected'}",
        ]
    )


def _parse_commitment_axis_position(position: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in position.split(";"):
        key, separator, value = part.partition("=")
        if separator and key and value:
            parsed[key] = value
    return parsed


def _first_ref(refs: list[str]) -> str | None:
    return refs[0] if refs else None


def _asymmetry_penalty(regime: str) -> float:
    if regime == "risk":
        return 0.0
    if regime == "ignorance":
        return 2.0
    return 1.0


def _adaptive_posture(design_strategy: object) -> str:
    if design_strategy == "expected_welfare_optimization":
        return "optimization_shadow_only"
    if design_strategy == "frame_indexed_portfolio":
        return "frame_indexed_limited"
    if design_strategy == "precautionary_adaptive_pathway":
        return "precautionary_adaptive"
    return "robust_limited"


def _cluster_interfaces(
    boundary: AuthorityBoundary,
    *,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> list[ClusterInterfaceContract]:
    contracts = [
        ClusterInterfaceContract(
            contract_id="layer2.s2.cluster.interface.design_grammar",
            cell_ref="INTERVENTION.design_grammar",
            publishes=["DesignGrammarExpansion"],
            consumes=["Layer2S2DesignSearchInput"],
            authority_boundary=boundary,
        ),
        ClusterInterfaceContract(
            contract_id="layer2.s2.cluster.interface.design_candidate",
            cell_ref="INTERVENTION.design_candidate",
            publishes=["DesignCandidateV0", "SearchLedger", "DesignRecordV0"],
            consumes=["DesignGrammarExpansion", "CounterexampleRecord"],
            authority_boundary=boundary,
        ),
    ]
    if composition_posture is not None:
        contracts.extend(
            [
                ClusterInterfaceContract(
                    contract_id="layer2.s2.cluster.interface.connectivity_modularity",
                    cell_ref="SYSTEM.connectivity_modularity",
                    publishes=["CouplingGraph", "CouplingRegimeClassification"],
                    consumes=["Layer2S5CompositionPostureInput"],
                    authority_boundary=boundary,
                ),
                ClusterInterfaceContract(
                    contract_id="layer2.s2.cluster.interface.dynamics_feedback",
                    cell_ref="SYSTEM.dynamics_feedback",
                    publishes=(
                        ["SystemDynamicsRequirement"]
                        if composition_posture.dynamics_requirement_ref
                        else []
                    ),
                    consumes=["Layer2S5CompositionPostureInput"],
                    authority_boundary=boundary,
                ),
                ClusterInterfaceContract(
                    contract_id="layer2.s2.cluster.interface.scale_composition",
                    cell_ref="INTERVENTION.scale_composition",
                    publishes=["CompositionReceipt"],
                    consumes=[
                        "CouplingGraph",
                        "DecompositionResult",
                        "Layer2S5CompositionPostureInput",
                    ],
                    authority_boundary=boundary,
                ),
            ]
        )
    if blind_spot_posture is not None:
        for row in blind_spot_posture.bridge_consumer_rows:
            cell_ref = str(row.get("cell_ref", "UNKNOWN.unknown"))
            consumer_ref = str(row.get("consumer_ref", "UNKNOWN.consumer"))
            contracts.append(
                ClusterInterfaceContract(
                    contract_id=f"layer2.s2.cluster.interface.s6.{_slug(cell_ref)}.{_slug(consumer_ref)}",
                    cell_ref=cell_ref,
                    publishes=["Layer2S6BlindSpotPostureInput", "ConstraintStoreEntry"],
                    consumes=["Layer2S6BlindSpotPostureInput"],
                    authority_boundary=boundary,
                )
            )
    if value_posture is not None:
        contracts.append(
            ClusterInterfaceContract(
                contract_id="layer2.s2.cluster.interface.value_choice_provenance",
                cell_ref=_S8_VALUE_CHOICE_CELL_REF,
                publishes=["Layer2S8ValuePostureInput", "ConstraintStoreEntry"],
                consumes=["Layer2S8ValuePostureInput"],
                authority_boundary=boundary,
            )
        )
    if forecast_posture is not None:
        contracts.append(
            ClusterInterfaceContract(
                contract_id="layer2.s2.cluster.interface.outcome_prediction",
                cell_ref="KNOWLEDGE.outcome_prediction_welfare_comparison",
                publishes=["SearchLedger"],
                consumes=["Layer2S10ForecastPostureInput"],
                authority_boundary=forecast_posture.authority_boundary,
            )
        )
    if predictive_posture is not None:
        contracts.append(
            ClusterInterfaceContract(
                contract_id="layer2.s2.cluster.interface.predictive_knowledge",
                cell_ref="KNOWLEDGE.predictive_knowledge_relaxation",
                publishes=[
                    "SearchLedger",
                    "ConstraintStoreEntry",
                    "predictive_axis_maturity_upgrade",
                ],
                consumes=["Layer2S11PredictivePostureInput"],
                authority_boundary=predictive_posture.authority_boundary,
            )
        )
    if resource_posture is not None:
        contracts.append(
            ClusterInterfaceContract(
                contract_id="layer2.s2.cluster.interface.resource_economics",
                cell_ref=_S12_RESOURCE_ECONOMICS_CELL_REF,
                publishes=[
                    "SearchLedger",
                    "ConstraintStoreEntry",
                    "allocation_priority_input",
                ],
                consumes=["Layer2S12ResourceEconomicsPostureInput"],
                authority_boundary=resource_posture.authority_boundary,
            )
        )
    return contracts


def _handoff_records(
    candidate: DesignCandidateV0,
    expansion: DesignGrammarExpansion,
    ledger: SearchLedger,
    *,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> list[ClusterHandoffRecord]:
    records = [
        ClusterHandoffRecord(
            handoff_id="layer2.s2.handoff.generation",
            workflow_ref="workflow://layer2/s2/shadow-design-loop",
            source_cell_ref="INTERVENTION.design_grammar",
            target_cell_ref="INTERVENTION.design_candidate",
            artifact_refs=[expansion.expansion_ref, candidate.candidate_ref, ledger.ledger_ref],
            disposition="emitted",
            authority_purpose=_AUTHORITY_PURPOSE,
            may_not_use_for=list(_MAY_NOT_USE_FOR),
        )
    ]
    if composition_posture is not None:
        records.append(
            ClusterHandoffRecord(
                handoff_id="layer2.s2.handoff.s5_composition_posture",
                workflow_ref="workflow://layer2/s2/shadow-design-loop",
                source_cell_ref="INTERVENTION.scale_composition",
                target_cell_ref="INTERVENTION.design_candidate",
                artifact_refs=_composition_ledger_refs(composition_posture),
                disposition="consumed",
                authority_purpose="composition_gate",
                may_not_use_for=[
                    "whole_design_authority_without_coupling_graph",
                    "false_modular_decomposition",
                    "production_recommendation",
                ],
            )
        )
    if blind_spot_posture is not None:
        records.append(
            ClusterHandoffRecord(
                handoff_id="layer2.s2.handoff.s6_blind_spot_posture",
                workflow_ref="workflow://layer2/s2/shadow-design-loop",
                source_cell_ref="RUNTIME_QUALITY.blind_spot_firewalls",
                target_cell_ref="INTERVENTION.design_candidate",
                artifact_refs=_s6_ledger_refs(blind_spot_posture),
                disposition="consumed",
                authority_purpose="fail_closed_blind_spot_constraint_injection",
                may_not_use_for=[
                    "blind_spot_self_clearance_by_b_side",
                    "production_recommendation",
                    "outcome_prediction_authority",
                ],
            )
        )
    if delegation_posture is not None:
        records.extend(
            ClusterHandoffRecord.model_validate(row)
            for row in delegation_posture.handoff_rows
        )
    if value_posture is not None:
        records.extend(_s8_handoff_records(value_posture))
    if forecast_posture is not None:
        records.append(_s10_handoff_record(forecast_posture))
    if predictive_posture is not None:
        records.append(_s11_handoff_record(predictive_posture))
    if resource_posture is not None:
        records.append(_s12_handoff_record(resource_posture))
    return records


def _governance_decision_class(input: Layer2S2DesignSearchInput) -> GovernanceDecisionClass:
    return GovernanceDecisionClass(
        decision_class_id="a_spec_gap",
        label="A-side specification gap",
        required_role="policy_design_governance_reviewer",
        default_posture="shadow",
        high_stakes=False,
        authority_boundary=AuthorityBoundary(
            authoritative_for=["governance_gap_routing"],
            may_not_use_for=list(_MAY_NOT_USE_FOR),
            source_authority="human_governance",
            posture="shadow",
            rule_version_refs=[input.rule_version_ref],
        ),
    )


def _value_authorization_decision_class(
    input: Layer2S2DesignSearchInput,
) -> GovernanceDecisionClass:
    return GovernanceDecisionClass(
        decision_class_id="value_authorization",
        label="Value authorization",
        required_role="principal",
        default_posture="shadow",
        high_stakes=True,
        authority_boundary=AuthorityBoundary(
            authoritative_for=["value_choice_routing"],
            may_not_use_for=[
                "production_recommendation",
                "production_claim_authority",
                "scalar_welfare_authority",
                "preference_learning_authority",
            ],
            source_authority="human_governance",
            posture="shadow",
            rule_version_refs=[input.rule_version_ref],
        ),
    )


def _deterministic_replay_key(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    delegation_posture: Layer2S7DelegationPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    forecast_posture: Layer2S10ForecastPostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
    resource_posture: Layer2S12ResourceEconomicsPostureInput | None = None,
) -> str:
    payload = {
        "case_id": input.case_id,
        "intent_ref": input.intent_ref,
        "grammar_ref": input.grammar_ref,
        "objective_refs": list(input.objective_refs),
        "construct_refs": list(input.construct_refs),
        "candidate_ref": candidate.candidate_ref,
        "counterexample_class": counterexample.counterexample_class,
        "decision": decision.decision,
        "value_of_information.estimate_id": decision.value_of_information.estimate_id,
        "budget_refs": list(decision.budget_refs),
    }
    if any(
        value is not None
        for value in (
            candidate.regime,
            candidate.design_strategy,
            candidate.commitment_profile_ref,
            candidate.commitment_stakes,
        )
    ):
        payload.update(
            {
                "regime": candidate.regime,
                "design_strategy": candidate.design_strategy,
                "commitment_profile_ref": candidate.commitment_profile_ref,
                "commitment_stakes": candidate.commitment_stakes,
            }
        )
    if composition_posture is not None:
        payload["composition_posture"] = composition_posture.model_dump(mode="json")
    if blind_spot_posture is not None:
        payload["blind_spot_posture"] = blind_spot_posture.model_dump(mode="json")
    if delegation_posture is not None:
        payload["delegation_posture"] = delegation_posture.model_dump(mode="json")
    if value_posture is not None:
        payload["value_posture"] = value_posture.model_dump(mode="json")
    if forecast_posture is not None:
        payload["forecast_posture"] = {
            "forecast_support_ref": forecast_posture.forecast_support_ref,
            "forecast_calibration_record_ref": (
                forecast_posture.forecast_calibration_record_ref
            ),
            "forecast_tier": forecast_posture.forecast_tier,
            "design_graph_ref": forecast_posture.design_graph_ref,
            "prediction_context_ref": forecast_posture.prediction_context_ref,
            "rule_version_ref": forecast_posture.rule_version_ref,
        }
    if predictive_posture is not None:
        payload["predictive_posture"] = predictive_posture.model_dump(mode="json")
    if resource_posture is not None:
        payload["resource_posture"] = resource_posture.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _counterexample_message(counterexample_class: str) -> str:
    if counterexample_class == "a_spec_gap":
        return "A-side specification is incomplete and must route to governance."
    if counterexample_class == "substrate_gap":
        return (
            "Required substrate is unavailable; acquisition is required but not authorized by S2."
        )
    if counterexample_class == "budget_gap":
        return "Search budget is exhausted; S2 must abstain from best-candidate authority."
    return "Candidate violates a shadow A-side design constraint and must be refined."


def _decision_reason(
    decision: RefinementDecisionKind,
    counterexample_class: str,
    *,
    design_strategy: str | None = None,
    composition_posture: Layer2S5CompositionPostureInput | None = None,
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None,
    value_posture: Layer2S8ValuePostureInput | None = None,
    predictive_posture: Layer2S11PredictivePostureInput | None = None,
) -> str:
    if (
        predictive_posture is not None
        and _s11_refinement_decision(predictive_posture) == "block_candidate"
    ):
        return (
            "S11 predictive posture fails closed; S2 blocks candidate authority without "
            "turning predictive confidence into recommendation authority."
        )
    if value_posture is not None and _s8_blocks_ranked_selection(value_posture):
        return (
            f"S8 {value_posture.disposition} value-choice posture blocks ranked "
            "selection before S2 can scalarize or recommend a candidate."
        )
    if value_posture is not None and value_posture.disposition == "contested_multi_principal":
        return (
            "S8 contested multi-principal value posture routes to governance instead of "
            "silent scalarization."
        )
    if blind_spot_posture is not None and blind_spot_posture.overall_posture != "clear_fail_closed":
        return (
            f"S6 {blind_spot_posture.overall_posture} blind-spot posture routes "
            "refinement before point optimization; "
            f"{blind_spot_posture.limitation_summary}"
        )
    if decision == "human_decision":
        return "A-side specification gaps are governance-owned and cannot be self-repaired."
    if decision == "acquire":
        return "Substrate gaps route to acquisition while preserving bridge_missing authority."
    if decision == "abstain":
        return "Budget gaps preserve search incompleteness instead of laundering a frontier."
    if decision == "block_candidate":
        return "The same blocked candidate cannot be retried into a pass without new grammar."
    if decision == "reframe":
        strategy_note = f" under {design_strategy}" if design_strategy else ""
        frame_note = (
            "; frame-indexed portfolios remain a limitation until S8 value provenance"
            if design_strategy == "frame_indexed_portfolio"
            else ""
        )
        return (
            f"{counterexample_class} is consumed by reframe{strategy_note}, "
            "not point-optimization refinement"
            f"{frame_note}."
        )
    if decision == "decompose":
        disposition = (
            composition_posture.composition_disposition
            if composition_posture is not None
            else "system_evidence_required"
        )
        return (
            f"{counterexample_class} is consumed by S5 {disposition}; "
            "route to decomposition or system evidence before point optimization."
        )
    return f"{counterexample_class} is consumed by deterministic shadow refinement."


def _stakes_band_for_commitment(
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
) -> Literal["low", "moderate", "high", "high_stakes"]:
    if commitment_stakes == "catastrophic":
        return "high_stakes"
    if commitment_stakes == "high":
        return "high"
    if commitment_stakes == "low":
        return "low"
    return "moderate"


def _selected_floor_for_commitment(
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
) -> Literal["low_stakes", "standard", "high_stakes"]:
    if commitment_stakes == "catastrophic":
        return "high_stakes"
    if commitment_stakes == "low":
        return "low_stakes"
    return "standard"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip(".-")
    if not slug or not slug[0].isalpha():
        return f"s2.{slug or 'record'}"
    return slug
