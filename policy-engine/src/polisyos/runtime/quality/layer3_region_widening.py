"""Layer 3 G7 bounded region-widening constants and contracts.

G7 is a region-cohort adapter over existing Layer 3 evidence. It owns audit,
marginal-cost, and S14 grounded-breadth feed readings only; it does not mint
production, recommendation, legal, closeout, scorecard, or universal authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.runtime.quality.nl_replay_orchestration import (
    build_nl_replay_orchestration_continuity,
    validate_nl_replay_orchestration_continuity,
)
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
    verify_s12_resource_projection_consumer_contract,
    verify_s13_post_deploy_accountability_projection_consumer_contract,
    verify_s14_universality_projection_consumer_contract,
)
from polisyos.runtime.quality.replay import build_replay_manifest

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
G1_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
G1_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
)
G1_GROUNDED_SOURCE_CONTRACTS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json"
)
G1_SUBSTRATE_SEARCH_LEDGERS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_substrate_search_ledgers.json"
)
G4_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json"
G4_PROMOTION_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_promotion_records.json"
G4_GOVERNANCE_THROUGHPUT_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_governance_throughput_delta.json"
)
G5_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json"
G5_CONVERSION_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_conversion_records.json"
G5_W12D_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g5_w12d_consumer_gate.json"
G5_ENVELOPE_EXPANSION_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_envelope_expansion_delta.json"
)
G5_STATUS_COMPOSITION_LEDGER_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_status_composition_ledger.json"
)
G5_DEMAND_PULL_ATTEMPT_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_demand_pull_attempt_record.json"
)
G5_DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g5_dependency_health_metric_snapshot.json"
)
G6_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_readiness_manifest.json"
G6_GROUNDED_RESULT_OR_ABSTENTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_grounded_result_or_abstention.json"
)
G6_SEARCH_LEDGER_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_search_ledger.json"
G6_AGENT_RUN_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_agent_run_records.json"
G6_GROUNDING_DEMAND_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_grounding_demand_record.json"
)
G6_ORCHESTRATION_CHOICE_AUDIT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_choice_audit.json"
)
G6_G5_INVOCATION_PLAN_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_g5_invocation_plan.json"
G6_DEMAND_PULL_VS_ABSTENTION_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_demand_pull_vs_abstention_delta.json"
)
G6_ORCHESTRATION_CONTINUITY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_continuity.json"
)
G6_REPLAY_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_replay_manifest.json"
S14_ASSURANCE_MANIFEST_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json"
)
GL_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json"
GL_LEGAL_AUTHORITY_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_authority_report.json"
)
G7_DEPENDENCY_PATHS: tuple[Path, ...] = (
    G1_READINESS_PATH,
    G1_SEARCH_RECALL_FRESHNESS_PATH,
    G1_SUBSTRATE_SEARCH_LEDGERS_PATH,
    G4_READINESS_PATH,
    G4_PROMOTION_RECORDS_PATH,
    G4_GOVERNANCE_THROUGHPUT_DELTA_PATH,
    G5_READINESS_PATH,
    G5_CONVERSION_RECORDS_PATH,
    G5_W12D_CONSUMER_GATE_PATH,
    G5_ENVELOPE_EXPANSION_DELTA_PATH,
    G5_STATUS_COMPOSITION_LEDGER_PATH,
    G5_DEMAND_PULL_ATTEMPT_RECORD_PATH,
    G5_DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH,
    G6_READINESS_PATH,
    G6_GROUNDED_RESULT_OR_ABSTENTION_PATH,
    G6_SEARCH_LEDGER_PATH,
    G6_AGENT_RUN_RECORDS_PATH,
    G6_G5_INVOCATION_PLAN_PATH,
    G6_DEMAND_PULL_VS_ABSTENTION_DELTA_PATH,
    G6_ORCHESTRATION_CONTINUITY_PATH,
    G6_REPLAY_MANIFEST_PATH,
    S14_ASSURANCE_MANIFEST_PATH,
)

G7_SCHEMA_VERSION: str = "policyos.policy_design_case.layer3_g7_region_widening.v1"
G7_RULE_VERSION: str = "policyos.layer3.g7.region_widening.v1"
G7_SURFACE_ID: str = "layer3_g7_region_widening_surface"
G7_GENERATED_ARTIFACT_FAMILY_ID: str = (
    "policy-design-case-layer3-g7-region-widening-artifacts"
)

G7_AUTHORITATIVE_FOR: tuple[str, ...] = (
    "layer3_g7_region_widening_audit",
    "layer3_g7_marginal_grounding_cost_reading",
    "layer3_g7_s14_grounded_breadth_feed",
)
G7_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_authority",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "recommendation_authority",
    "universal_claim_authority",
    "universal_claim_authority_without_s14",
    "s14_universality_claim_without_s14_gate",
    "g8_metric_governance_authority",
)
G7_PUBLIC_OFFICIAL_USE_LIMITS: tuple[str, ...] = (
    "public_audit",
    "operator_triage",
    "external_explanation",
)
G7_PUBLIC_REQUIRED_DENIED_USES: frozenset[str] = frozenset(
    {
        "approval_authority",
        "automated_value_learning",
        "claim_authority",
        "closeout_authority",
        "current_evidence_slot",
        "preference_learning",
        "production_authority",
        "production_claim_authority",
        "production_recommendation",
        "production_rollout_authority",
        "publication_authority",
        "recommendation_authority",
        "rollout_authority",
        "runtime_closeout_authority",
        "s13_accountability_closure",
        "s14_universality",
        "scorecard_authority",
        "aggregate_universal_score",
        "budget_interchangeability",
        "floor_relaxation",
        "llm_attribution_authority",
        "local_governance_enum_for_reissue",
        "mdp_bandit_optimizer_authority",
        "mission_or_value_self_authorization",
        "naive_ml_update",
        "pre_policy_evidence",
        "preference_learning_authority",
        "s13_envelope_shrink",
    }
)
G7_PUBLIC_PROJECTION_DENIED_USES: tuple[str, ...] = tuple(
    dict.fromkeys((*G7_MAY_NOT_USE_FOR, *sorted(G7_PUBLIC_REQUIRED_DENIED_USES)))
)

ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g7_g5_readiness_missing",
    "layer3_g7_g6_readiness_missing",
    "layer3_g7_current_g5_unchanged_blocker",
    "layer3_g7_no_real_grounded_region_breadth",
    "layer3_g7_region_candidate_set_missing",
    "layer3_g7_candidate_set_hardcoded_as_coverage",
    "layer3_g7_region_case_without_grounding_matrix",
    "layer3_g7_status_composition_missing",
    "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
    "layer3_g7_g6_candidate_counted_as_grounded",
    "layer3_g7_fixture_breadth_counted_as_grounded",
    "layer3_g7_grounded_case_without_governed_promotion",
    "layer3_g7_g4_seed_promotion_projected_to_region",
    "layer3_g7_g4_promotion_gate_shape_missing",
    "layer3_g7_g4_mapping_fallback_counted_as_governed",
    "layer3_g7_bespoke_patch_counted_as_reuse",
    "layer3_g7_marginal_cost_without_cost_ledger",
    "layer3_g7_sublinear_claim_without_grounded_cases",
    "layer3_g7_s12_growth_thermometer_missing",
    "layer3_g7_s12_projection_bypasses_resource_economics_shape",
    "layer3_g7_s12_growth_without_certified_delta",
    "layer3_g7_s12_held_out_status_overclaimed",
    "layer3_g7_s12_deny_list_omitted",
    "layer3_g7_s13_certified_delta_missing",
    "layer3_g7_pending_delta_counted_as_expansion",
    "layer3_g7_search_hit_counted_as_coverage",
    "layer3_g7_search_recall_or_freshness_missing",
    "layer3_g7_governance_throughput_missing",
    "layer3_g7_accountable_principal_missing",
    "layer3_g7_effective_independence_inflated",
    "layer3_g7_semantic_loss_hidden_by_region_score",
    "layer3_g7_g5_may_not_use_for_ignored",
    "layer3_g7_g6_may_not_use_for_ignored",
    "layer3_g7_s14_feed_missing",
    "layer3_g7_s14_battery_input_manifest_missing",
    "layer3_g7_s14_feed_uses_fixtures",
    "layer3_g7_s14_consumer_gate_missing",
    "layer3_g7_s14_manifest_runner_output_conflated",
    "layer3_g7_universal_claim_without_s14_gate",
    "layer3_g7_public_projection_authority_leak",
    "layer3_g7_public_raw_payload_leak",
    "layer3_g7_projection_omits_required_deny_list",
    "layer3_g7_public_projection_contract_failed",
    "layer3_g7_generated_artifacts_family_missing",
    "layer3_g7_inventory_surface_missing",
    "layer3_g7_reference_index_missing",
    "layer3_g7_route_contract_registry_missing",
    "layer3_g7_manifest_runtime_drift",
    "layer3_g7_replay_manifest_missing",
    "layer3_g7_orchestration_continuity_missing",
    "layer3_g7_replay_helper_bypassed",
    "layer3_g7_closed_case_replay_mutated",
    "layer3_g7_persisted_artifact_missing",
)
G7_ISSUE_CODE_DICTIONARY: tuple[str, ...] = ALL_ISSUE_CODES
G7_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES: dict[str, tuple[str, ...]] = {
    "g5_unchanged_blocker_as_region_grounded": (
        "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
    ),
    "g6_candidate_as_region_grounded": ("layer3_g7_g6_candidate_counted_as_grounded",),
    "fixture_breadth_as_grounded": ("layer3_g7_fixture_breadth_counted_as_grounded",),
    "hardcoded_candidate_set_as_region_coverage": (
        "layer3_g7_candidate_set_hardcoded_as_coverage",
    ),
    "search_hit_as_region_coverage": ("layer3_g7_search_hit_counted_as_coverage",),
    "grounded_case_without_governed_promotion": (
        "layer3_g7_grounded_case_without_governed_promotion",
    ),
    "g4_seed_promotion_as_region_governance": (
        "layer3_g7_g4_seed_promotion_projected_to_region",
    ),
    "g4_promotion_without_full_gate_shape": (
        "layer3_g7_g4_promotion_gate_shape_missing",
    ),
    "g4_mapping_fallback_as_region_governance": (
        "layer3_g7_g4_mapping_fallback_counted_as_governed",
    ),
    "bespoke_patch_as_mechanism_reuse": (
        "layer3_g7_bespoke_patch_counted_as_reuse",
    ),
    "sublinear_cost_without_cost_ledger": (
        "layer3_g7_marginal_cost_without_cost_ledger",
    ),
    "sublinear_cost_without_grounded_cases": (
        "layer3_g7_sublinear_claim_without_grounded_cases",
    ),
    "s12_growth_thermometer_missing": ("layer3_g7_s12_growth_thermometer_missing",),
    "s12_projection_bypasses_resource_economics_shape": (
        "layer3_g7_s12_projection_bypasses_resource_economics_shape",
    ),
    "s12_growth_without_certified_delta": (
        "layer3_g7_s12_growth_without_certified_delta",
    ),
    "s12_held_out_status_overclaimed": (
        "layer3_g7_s12_held_out_status_overclaimed",
    ),
    "s12_deny_list_omitted": ("layer3_g7_s12_deny_list_omitted",),
    "s13_certified_delta_missing": ("layer3_g7_s13_certified_delta_missing",),
    "pending_delta_as_region_expansion": (
        "layer3_g7_pending_delta_counted_as_expansion",
    ),
    "semantic_loss_hidden_by_region_score": (
        "layer3_g7_semantic_loss_hidden_by_region_score",
    ),
    "effective_independence_inflated": (
        "layer3_g7_effective_independence_inflated",
    ),
    "g5_may_not_use_for_ignored": ("layer3_g7_g5_may_not_use_for_ignored",),
    "g6_may_not_use_for_ignored": ("layer3_g7_g6_may_not_use_for_ignored",),
    "s14_feed_missing": ("layer3_g7_s14_feed_missing",),
    "s14_battery_input_manifest_missing": (
        "layer3_g7_s14_battery_input_manifest_missing",
    ),
    "s14_feed_uses_fixtures": ("layer3_g7_s14_feed_uses_fixtures",),
    "s14_manifest_as_runner_output": (
        "layer3_g7_s14_manifest_runner_output_conflated",
    ),
    "universal_claim_without_s14_gate": (
        "layer3_g7_universal_claim_without_s14_gate",
    ),
    "public_projection_authority_leak": (
        "layer3_g7_public_projection_authority_leak",
    ),
    "public_projection_raw_payload_leak": ("layer3_g7_public_raw_payload_leak",),
    "public_projection_required_deny_list_missing": (
        "layer3_g7_projection_omits_required_deny_list",
    ),
    "public_projection_contract_missing_or_failed": (
        "layer3_g7_public_projection_contract_failed",
    ),
    "generated_artifacts_family_missing": (
        "layer3_g7_generated_artifacts_family_missing",
    ),
    "inventory_surface_missing": ("layer3_g7_inventory_surface_missing",),
    "reference_index_missing": ("layer3_g7_reference_index_missing",),
    "route_contract_registry_missing": ("layer3_g7_route_contract_registry_missing",),
    "manifest_runtime_drift": ("layer3_g7_manifest_runtime_drift",),
    "replay_manifest_missing": ("layer3_g7_replay_manifest_missing",),
    "orchestration_continuity_missing": (
        "layer3_g7_orchestration_continuity_missing",
    ),
    "replay_helper_bypassed": ("layer3_g7_replay_helper_bypassed",),
    "closed_case_replay_mutated": ("layer3_g7_closed_case_replay_mutated",),
}
REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS: tuple[str, ...] = tuple(
    G7_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES
)


class _G7Model(BaseModel):
    """Strict base model for G7 runtime-quality DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


Layer3G7EngineeringReadinessStatus = Literal["pass", "fail", "blocked"]
Layer3G7RegionValueClosureStatus = Literal[
    "pass",
    "blocked_by_current_g5_unchanged_blocker",
    "blocked_by_no_real_grounded_region_breadth",
    "blocked_by_bespoke_reuse",
    "blocked_by_s14_feed",
    "fail",
]
Layer3G7RegionConversionSourceClass = Literal[
    "persisted_current_g5_record",
    "synthetic_g5_compatible_test_record",
    "external_g5_compatible_record",
    "g6_candidate",
    "fixture_only",
]
Layer3G7GovernedPromotionJoinStatus = Literal[
    "pass",
    "missing",
    "blocked",
    "shadow_only",
]
Layer3G7RegionConversionStatus = Literal[
    "grounded_limited",
    "grounded_abstention",
    "blocked_current_g5_unchanged_blocker",
    "blocked_ungrounded",
    "blocked_ungoverned_promotion",
    "blocked_g4_gate_shape",
    "blocked_source_class",
    "blocked_search_hit_without_adapter",
]
Layer3G7ConversionMatrixStatus = Literal["pass", "blocked", "fail"]
Layer3G7S12ProjectionStatus = Literal["pass", "blocked", "fail"]
Layer3G7GrowthCountingDisposition = Literal[
    "counted_mechanism_growth",
    "blocked_missing_envelope_delta",
    "blocked_one_off_growth",
]
Layer3G7MechanismReuseStatus = Literal[
    "pass",
    "blocked_insufficient_grounded_cases",
    "blocked_by_bespoke_patch",
    "blocked_by_one_off_growth",
    "blocked_low_reuse",
]
Layer3G7SublinearMarginalCostStatus = Literal[
    "pass",
    "blocked_insufficient_grounded_cases",
    "blocked_bespoke_reuse",
    "blocked_s12_growth_thermometer",
    "blocked_semantic_loss",
    "blocked_reuse_threshold",
    "blocked_marginal_cost_not_sublinear",
]
Layer3G7RegionExpansionStatus = Literal["pass", "flat", "blocked", "fail"]
Layer3G7EnvelopeRevisionDirection = Literal[
    "expand",
    "pending",
    "hold",
    "shrink",
    "split",
]
Layer3G7SemanticLossStatus = Literal["pass", "blocked"]
Layer3G7HealthMetricDeltaStatus = Literal["pass", "blocked", "flat"]
Layer3G7StatusCompositionStatus = Literal["pass", "blocked", "fail"]
Layer3G7S14FeedStatus = Literal["pass", "blocked_no_real_grounded_breadth", "blocked"]
Layer3G7S14ConsumerGateStatus = Literal["pass", "blocked"]
Layer3G7ProjectionSurfaceStatus = Literal["pass", "fail", "not_applicable_no_payload"]
Layer3G7AuditSurfaceStatus = Literal["pass", "fail"]
Layer3G7ReplayStatus = Literal["pass", "fail"]
G7_REQUIRED_G4_PROMOTION_GATE_REFS: tuple[str, ...] = (
    "grounded_contract_set_ref",
    "a_completeness_ledger_ref",
    "weakest_boundary_composition_ref",
    "human_decision_integrity_gate_ref",
    "g5_handoff_ref",
)


class Layer3G7ValidationIssue(_G7Model):
    """One fail-closed G7 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G7ValidationReport(_G7Model):
    """G7 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G7ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_code_dictionary: tuple[str, ...] = G7_ISSUE_CODE_DICTIONARY


class Layer3G7DependencyReadinessSnapshot(_G7Model):
    """Dependency snapshot for the G7 region-widening bridge."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    engineering_readiness_status: Layer3G7EngineeringReadinessStatus
    region_value_closure_status: Layer3G7RegionValueClosureStatus
    g1_readiness_status: str = "missing"
    g1_search_recall_status: str = "missing"
    g1_index_freshness_status: str = "missing"
    g1_substrate_search_control_plane_status: str = "missing"
    g1_substrate_search_ledger_count: int = Field(default=0, ge=0)
    g1_substrate_search_authoritative_for: tuple[str, ...] = Field(default=())
    g1_substrate_search_may_not_use_for: tuple[str, ...] = Field(default=())
    g4_readiness_status: str = "missing"
    g4_promotion_record_count: int = Field(default=0, ge=0)
    g4_governed_promoted_count: int = Field(default=0, ge=0)
    g4_promotion_blocked_count: int = Field(default=0, ge=0)
    g4_governance_throughput_status: str = "missing"
    g5_readiness_status: str = "missing"
    g5_conversion_outcome: str | None = None
    g5_grounding_disposition: str | None = None
    g5_grounded_region_seed_count: int = Field(default=0, ge=0)
    g5_conversion_record_count: int = Field(default=0, ge=0)
    g5_w12d_consumer_gate_status: str = "missing"
    g5_envelope_expansion_status: str = "missing"
    g5_status_composition_status: str = "missing"
    g5_demand_pull_attempt_status: str = "missing"
    g5_dependency_health_metric_snapshot_status: str = "missing"
    g5_may_not_use_for: tuple[str, ...] = Field(default=())
    g6_readiness_status: str = "missing"
    g6_engineering_readiness_status: str = "missing"
    g6_grounded_value_closure_status: str = "missing"
    g6_result_outcome: str | None = None
    g6_grounding_disposition: str | None = None
    g6_g5_conversion_outcome: str | None = None
    g6_search_ledger_status: str = "missing"
    g6_agent_run_record_count: int = Field(default=0, ge=0)
    g6_g5_invocation_plan_status: str = "missing"
    g6_demand_pull_vs_abstention_status: str = "missing"
    g6_orchestration_continuity_status: str = "missing"
    g6_replay_manifest_status: str = "missing"
    g6_may_not_use_for: tuple[str, ...] = Field(default=())
    s14_assurance_manifest_status: str = "missing"
    s14_helper_availability_status: str = "missing"
    loaded_artifact_paths: tuple[str, ...] = Field(default=())
    missing_artifact_paths: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7RegionCaseConversionInput(_G7Model):
    """G7-shaped input row over an upstream G5 conversion and G4 promotion."""

    case_id: str = Field(min_length=1)
    region_ref: str | None = None
    source_class: Layer3G7RegionConversionSourceClass
    g5_conversion_record: dict[str, Any] = Field(default_factory=dict)
    g4_promotion_record: dict[str, Any] | None = None
    governed_promotion_status: Layer3G7GovernedPromotionJoinStatus = "pass"
    source_contract_status: str = "pass"
    search_health_status: str = "pass"
    effective_independence_status: str = "pass"
    search_status: Literal["adapter_backed", "hit_without_adapter", "missing"] = (
        "adapter_backed"
    )
    g4_record_source: str = "persisted_g4_record"
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())


class Layer3G7GovernedPromotionJoin(_G7Model):
    """G7 validation view of a case-specific G4 governed promotion join."""

    status: Layer3G7GovernedPromotionJoinStatus
    g4_record_source: str = "missing"
    g4_promotion_record_ref: str | None = None
    g4_promotion_state: str = "missing"
    g4_grounded_contract_set_ref: str | None = None
    g4_a_completeness_ledger_ref: str | None = None
    g4_weakest_boundary_composition_ref: str | None = None
    g4_human_decision_integrity_gate_ref: str | None = None
    g4_g5_handoff_ref: str | None = None
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7RegionConversionRecord(_G7Model):
    """Per-case G7 conversion record that preserves upstream authority boundaries."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    case_id: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    source_class: Layer3G7RegionConversionSourceClass
    g5_conversion_record_ref: str | None = None
    g5_conversion_outcome: str | None = None
    grounding_disposition: str | None = None
    region_grounding_status: Layer3G7RegionConversionStatus
    governed_promotion_status: Layer3G7GovernedPromotionJoinStatus
    source_contract_status: str = "pass"
    search_health_status: str = "pass"
    effective_independence_status: str = "pass"
    search_status: Literal["adapter_backed", "hit_without_adapter", "missing"] = (
        "adapter_backed"
    )
    g4_promotion_record_ref: str | None = None
    g4_governed_promotion_join_status: Layer3G7GovernedPromotionJoinStatus
    g4_grounded_contract_set_ref: str | None = None
    g4_a_completeness_ledger_ref: str | None = None
    g4_weakest_boundary_composition_ref: str | None = None
    g4_human_decision_integrity_gate_ref: str | None = None
    g4_g5_handoff_ref: str | None = None
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    upstream_may_not_use_for: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR
    is_grounded: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7RegionConversionStatusMatrix(_G7Model):
    """Aggregate G7 conversion status over bounded region case records."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    matrix_id: str
    region_ref: str = Field(min_length=1)
    status: Layer3G7ConversionMatrixStatus
    records: tuple[Layer3G7RegionConversionRecord, ...] = Field(default=())
    grounded_region_case_count: int = Field(default=0, ge=0)
    blocked_region_case_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7S12GrowthThermometerProjection(_G7Model):
    """Projection over S12/G5 demand and reuse signals consumed by G7."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    status: Layer3G7S12ProjectionStatus
    thermometer_ref: str = Field(min_length=1)
    g5_demand_pull_attempt_ref: str | None = None
    g5_envelope_expansion_delta_ref: str | None = None
    g5_dependency_health_snapshot_ref: str | None = None
    demand_pull_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    reused_primitive_refs: tuple[str, ...] = Field(default=())
    one_off_growth_refs: tuple[str, ...] = Field(default=())
    held_out_status: Literal["pending_s14", "executed", "missing"] = "pending_s14"
    held_out_battery_ref: str | None = None
    certified_envelope_delta_refs: tuple[str, ...] = Field(default=())
    growth_without_envelope_delta_count: int = Field(default=0, ge=0)
    growth_counting_disposition: Layer3G7GrowthCountingDisposition = (
        "counted_mechanism_growth"
    )
    reuse_rate: float = Field(default=0.0, ge=0.0)
    s12_projection_contract_status: str = "missing"
    s12_projection_contract_issue_codes: tuple[str, ...] = Field(default=())
    s12_projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())


class Layer3G7MechanismReuseRecord(_G7Model):
    """Per-case mechanism reuse reading for a grounded G7 region case."""

    case_id: str = Field(min_length=1)
    conversion_record_ref: str | None = None
    is_grounded: bool = False
    reused_primitive_refs: tuple[str, ...] = Field(default=())
    one_off_growth_refs: tuple[str, ...] = Field(default=())
    bespoke_patch_refs: tuple[str, ...] = Field(default=())
    reuse_status: Literal["reused", "not_grounded", "bespoke_patch", "one_off_growth"]


class Layer3G7MechanismReuseLedger(_G7Model):
    """Aggregate mechanism reuse ledger for G7 marginal-cost claims."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    ledger_id: str
    reuse_status: Layer3G7MechanismReuseStatus
    records: tuple[Layer3G7MechanismReuseRecord, ...] = Field(default=())
    grounded_region_case_count: int = Field(default=0, ge=0)
    reused_case_count: int = Field(default=0, ge=0)
    mechanism_reuse_rate: float = Field(default=0.0, ge=0.0)
    reuse_threshold: float = Field(default=0.5, ge=0.0)
    reused_primitive_refs: tuple[str, ...] = Field(default=())
    one_off_growth_refs: tuple[str, ...] = Field(default=())
    bespoke_patch_refs: tuple[str, ...] = Field(default=())
    bespoke_patch_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7MarginalGroundingCostRow(_G7Model):
    """One case contribution to the G7 marginal grounding-cost curve."""

    case_id: str = Field(min_length=1)
    conversion_record_ref: str | None = None
    is_grounded: bool = False
    effort_units: float = Field(default=0.0, ge=0.0)
    cumulative_effort_units: float = Field(default=0.0, ge=0.0)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7MarginalGroundingCostLedger(_G7Model):
    """G7 marginal grounding-cost ledger with fail-closed sublinear status."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    ledger_id: str
    baseline_seed_effort_units: float = Field(default=0.0, ge=0.0)
    added_case_effort_units: tuple[float, ...] = Field(default=())
    mean_added_case_effort_units: float = Field(default=0.0, ge=0.0)
    marginal_cost_ratio_to_seed: float = Field(default=0.0, ge=0.0)
    cumulative_grounding_cost_curve: tuple[float, ...] = Field(default=())
    grounded_region_case_count: int = Field(default=0, ge=0)
    added_region_case_count: int = Field(default=0, ge=0)
    bespoke_patch_count: int = Field(default=0, ge=0)
    semantic_loss_blocker_count: int = Field(default=0, ge=0)
    sublinear_marginal_cost_status: Layer3G7SublinearMarginalCostStatus
    rows: tuple[Layer3G7MarginalGroundingCostRow, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionEnvelopeExpansionDelta(_G7Model):
    """G7 region envelope expansion reading over grounded conversion records."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    delta_id: str
    region_ref: str = Field(min_length=1)
    expansion_status: Layer3G7RegionExpansionStatus
    envelope_revision_direction: Layer3G7EnvelopeRevisionDirection = "expand"
    certified_envelope_delta_refs: tuple[str, ...] = Field(default=())
    materialized_from_s12_growth_entry_ref: str | None = None
    assurance_case_delta_ref: str | None = None
    grounded_region_case_count: int = Field(default=0, ge=0)
    expanded_case_count: int = Field(default=0, ge=0)
    denominator: int = Field(default=0, ge=0)
    envelope_expansion_rate: float = Field(default=0.0, ge=0.0)
    expanded_case_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionSemanticLossRow(_G7Model):
    """Per-case semantic loss check for region aggregation."""

    case_id: str = Field(min_length=1)
    semantic_loss_status: Layer3G7SemanticLossStatus
    source_truth_lost: bool = False
    lineage_collapsed: bool = False
    authority_boundary_weakened: bool = False
    time_roles_merged: bool = False
    legal_or_mandate_status_dropped: bool = False
    g6_candidate_text_as_evidence: bool = False
    case_caveats_disappeared: bool = False
    certified_delta_ref_dropped: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7RegionSemanticLossLedger(_G7Model):
    """Aggregate G7 semantic-loss ledger that blocks region pass."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    ledger_id: str
    semantic_loss_status: Layer3G7SemanticLossStatus
    rows: tuple[Layer3G7RegionSemanticLossRow, ...] = Field(default=())
    semantic_loss_blocker_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7HealthMetricDelta(_G7Model):
    """G7 region health metric delta readings without useful-design optimization."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    status: Layer3G7HealthMetricDeltaStatus
    metrics: dict[str, str] = Field(default_factory=dict)
    envelope_expansion_rate_region: float = Field(default=0.0, ge=0.0)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7StatusCompositionLedger(_G7Model):
    """Composed G7 status lattice over expansion, semantics, cost, and S14."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    ledger_id: str
    status: Layer3G7StatusCompositionStatus
    weakest_region_status: str
    public_projection_status_claim: str = "missing"
    region_conversion_status: str = "missing"
    region_expansion_status: str = "missing"
    semantic_loss_status: str = "missing"
    marginal_cost_status: str = "missing"
    s14_feed_status: str = "missing"
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7S14GroundedBreadthFeed(_G7Model):
    """G7 grounded-breadth feed prepared for S14 consumption."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    feed_id: str
    feed_ref: str
    region_ref: str = Field(min_length=1)
    status: Layer3G7S14FeedStatus
    grounded_region_case_refs: tuple[str, ...] = Field(default=())
    grounded_authority_coverage_refs: tuple[str, ...] = Field(default=())
    a_firewall_refs: tuple[str, ...] = Field(default=())
    claim_evidence_binding_refs: tuple[str, ...] = Field(default=())
    mandate_legal_refs: tuple[str, ...] = Field(default=())
    capacity_regime_coupling_refs: tuple[str, ...] = Field(default=())
    mechanism_generality_report_refs: tuple[str, ...] = Field(default=())
    envelope_revision_delta_refs: tuple[str, ...] = Field(default=())
    visible_limitation_refs: tuple[str, ...] = Field(default=())
    denied_uses: tuple[str, ...] = G7_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7S14MechanismGeneralityProjection(_G7Model):
    """G7 projection into the S14 mechanism-generality helper shape."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    projection_id: str
    projection_ref: str
    status: Literal["pass", "blocked"]
    mechanism_generality_report_ref: str | None = None
    growth_thermometer_ref: str | None = None
    mechanism_reuse_rate: float = Field(default=0.0, ge=0.0)
    reused_mechanism_refs: tuple[str, ...] = Field(default=())
    bespoke_patch_refs: tuple[str, ...] = Field(default=())
    held_out_status: str = "pending_s14"
    issue_codes: tuple[str, ...] = Field(default=())
    report_payload: dict[str, Any] = Field(default_factory=dict)
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7S14BatteryInputManifest(_G7Model):
    """Read-only G7 input manifest consumed by the S14 battery runner."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    s14_battery_input_manifest_id: str = Field(min_length=1)
    grounded_breadth_feed_ref: str = Field(min_length=1)
    mechanism_generality_projection_ref: str = Field(min_length=1)
    grounded_authority_coverage_ref: str = Field(min_length=1)
    envelope_revision_dynamics_ref: str = Field(min_length=1)
    certified_envelope_delta_refs: tuple[str, ...] = Field(default=())
    visible_limitation_refs: tuple[str, ...] = Field(default=())
    sealed_battery_mutation_status: Literal["not_mutated"] = "not_mutated"
    hidden_case_access_status: Literal["not_accessed_by_g7"] = "not_accessed_by_g7"
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7S14ConsumerGate(_G7Model):
    """G7-side consumer gate before handing grounded breadth to S14."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    status: Layer3G7S14ConsumerGateStatus
    missing_capability_label: str | None = None
    s14_battery_input_manifest_ref: str | None = None
    s14_authority_issue_codes: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G7_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionScorecard(_G7Model):
    """Region-widening audit scorecard without approval or recommendation authority."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    scorecard_id: str
    scorecard_ref: str
    region_ref: str = Field(min_length=1)
    status: Literal["pass", "blocked", "fail"]
    region_envelope_posture: str
    grounded_case_count: int = Field(default=0, ge=0)
    blocked_case_count: int = Field(default=0, ge=0)
    pending_case_count: int = Field(default=0, ge=0)
    g7_region_value_closure_status: Layer3G7RegionValueClosureStatus
    mechanism_reuse_status: str
    marginal_cost_status: str
    s14_feed_status: str
    visible_limitation_refs: tuple[str, ...] = Field(default=())
    denied_uses: tuple[str, ...] = G7_PUBLIC_PROJECTION_DENIED_USES
    safe_artifact_refs: tuple[str, ...] = Field(default=())
    source_fingerprints: dict[str, str] = Field(default_factory=dict)
    scorecard_fingerprint: str
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionWideningAuditSurface(_G7Model):
    """Multi-audience G7 region-widening audit surface with redacted PUBLIC payload."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    surface_id: str = G7_SURFACE_ID
    region_ref: str = Field(min_length=1)
    status: Layer3G7AuditSurfaceStatus
    audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    surface_audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    REVIEWER: dict[str, Any] = Field(default_factory=dict)
    EXPERT: dict[str, Any] = Field(default_factory=dict)
    MACHINE: dict[str, Any] = Field(default_factory=dict)
    s12_resource_projection_contract_verification: dict[str, Any] = Field(
        default_factory=dict
    )
    s13_post_deploy_accountability_projection_contract_verification: dict[
        str, Any
    ] = Field(default_factory=dict)
    s14_universality_projection_contract_verification: dict[str, Any] = Field(
        default_factory=dict
    )
    public_projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    projection_contract_statuses: dict[str, str] = Field(default_factory=dict)
    source_fingerprints: dict[str, str] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_PUBLIC_PROJECTION_DENIED_USES


class Layer3G7PublicExportProjectionRefs(_G7Model):
    """Reference-only public export projection refs for G7 audit surfaces."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    status: Layer3G7AuditSurfaceStatus
    public_export_projection_ref: str
    region_ref: str = Field(min_length=1)
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    safe_artifact_refs: tuple[str, ...] = Field(default=())
    public_projection_contract_status: str = "fail"
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_PUBLIC_PROJECTION_DENIED_USES


class Layer3G7OrchestrationContinuity(_G7Model):
    """G7 wrapper over shared NL replay orchestration continuity."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    continuity_id: str
    region_ref: str = Field(min_length=1)
    status: Layer3G7ReplayStatus
    record: dict[str, Any] = Field(default_factory=dict)
    upstream_closed_case_replay_refs: dict[str, dict[str, str]] = Field(
        default_factory=dict
    )
    continuity_fingerprint: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7ReplayManifest(_G7Model):
    """G7 replay manifest wrapper with closed upstream refs by fingerprint."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    manifest_id: str
    region_ref: str = Field(min_length=1)
    status: Layer3G7ReplayStatus
    manifest: dict[str, Any]
    replay_fingerprints: dict[str, str] = Field(default_factory=dict)
    generated_artifact_paths: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7ConformanceNegativeResult(_G7Model):
    """One G7 conformance negative with expected and observed issue codes."""

    negative_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    expected_issue_codes: tuple[str, ...] = Field(min_length=1)
    observed_issue_codes: tuple[str, ...] = Field(default=())
    missing_issue_codes: tuple[str, ...] = Field(default=())
    probe_ref: str = Field(min_length=1)
    capability_reality_label: Literal[
        "implemented",
        "semantic_test_missing",
        "contract_only",
    ] = "implemented"


class Layer3G7ConformanceReport(_G7Model):
    """G7 conformance report covering every required negative path."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    report_id: str = "layer3-g7://conformance/report"
    status: Literal["pass", "fail"]
    capability_reality_label: Literal[
        "implemented",
        "semantic_test_missing",
        "contract_only",
    ]
    required_negative_ids: tuple[str, ...] = REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS
    negative_results: tuple[Layer3G7ConformanceNegativeResult, ...] = Field(default=())
    missing_negative_ids: tuple[str, ...] = Field(default=())
    failing_negative_ids: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g7_region_widening_audit",)
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


def _empty_g7_region_conversion_status_matrix() -> Layer3G7RegionConversionStatusMatrix:
    return Layer3G7RegionConversionStatusMatrix(
        matrix_id="layer3-g7://region-conversion-status-matrix/unbuilt",
        region_ref="region://unbuilt",
        status="blocked",
        issue_codes=("layer3_g7_no_real_grounded_region_breadth",),
    )


class Layer3G7Bundle(_G7Model):
    """Minimal Task 2 G7 bundle for dependency and overclaim validation."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    dependency_readiness_snapshot: Layer3G7DependencyReadinessSnapshot
    region_value_closure_status: Layer3G7RegionValueClosureStatus = (
        "blocked_by_no_real_grounded_region_breadth"
    )
    region_conversion_status_matrix: Layer3G7RegionConversionStatusMatrix = Field(
        default_factory=_empty_g7_region_conversion_status_matrix
    )
    region_grounded_case_count: int = Field(default=0, ge=0)
    g6_region_conversion_count: int = Field(default=0, ge=0)
    seed_g4_promotion_projected_to_region: bool = False
    status_composition_claim: Literal["pass", "blocked", "fail", "missing"] = "missing"
    per_case_grounding_status: str = "blocked_current_g5_unchanged_blocker"
    s14_feed_status: str = "blocked_no_real_grounded_breadth"
    semantic_loss_status: str = "not_built"
    marginal_cost_status: str = "blocked_insufficient_grounded_cases"
    closed_replay_mutation_detected: bool = False


Layer3G7CandidateSource = Literal[
    "current_g5_seed_case",
    "readiness_control_plane_fixture",
    "external_candidate_input",
]
Layer3G7CoverageStatus = Literal[
    "blocked_control_plane_only",
    "blocked_search_control_plane_only",
    "blocked_no_grounded_records",
    "pass",
]
Layer3G7RowGroundingStatus = Literal[
    "blocked_current_g5_unchanged_blocker",
    "blocked_missing_grounding_matrix_refs",
    "control_plane_candidate",
    "grounded_limited",
    "grounded_abstention",
]


class Layer3G7RegionCaseCandidate(_G7Model):
    """One bounded G7 region case candidate."""

    case_id: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    candidate_source: Layer3G7CandidateSource = "external_candidate_input"
    adjacency_basis_refs: tuple[str, ...] = Field(default=())
    source_contract_refs: tuple[str, ...] = Field(default=())
    search_ledger_refs: tuple[str, ...] = Field(default=())
    demand_refs: tuple[str, ...] = Field(default=())
    s12_voi_refs: tuple[str, ...] = Field(default=())
    s3_demand_pull_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    g6_request_refs: tuple[str, ...] = Field(default=())
    g6_agent_refs: tuple[str, ...] = Field(default=())
    g4_promotion_refs: tuple[str, ...] = Field(default=())
    g5_conversion_record_refs: tuple[str, ...] = Field(default=())
    declared_envelope_refs: tuple[str, ...] = Field(default=())
    time_refs: tuple[str, ...] = Field(default=())
    envelope_posture: Literal["in", "out", "pending"] = "pending"
    missing_ref_blockers: tuple[str, ...] = Field(default=())
    missing_ref_limitations: tuple[str, ...] = Field(default=())
    blockers: tuple[str, ...] = Field(default=())
    limitations: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionCandidateSet(_G7Model):
    """Bounded G7 region candidate input set."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    candidate_set_id: str
    region_ref: str = Field(min_length=1)
    cases: tuple[Layer3G7RegionCaseCandidate, ...] = Field(default=())
    case_count: int = Field(default=0, ge=0)
    coverage_authority_status: Literal["control_plane_only", "external_input_pending"] = (
        "external_input_pending"
    )
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7SearchRecallFreshnessJoin(_G7Model):
    """G7 join over G1 source/search-health and search-ledger boundaries."""

    status: Literal["pass", "fail", "missing"] = "missing"
    g1_source_contract_refs: tuple[str, ...] = Field(default=())
    g1_search_recall_status: str = "missing"
    g1_index_freshness_status: str = "missing"
    search_ledger_refs: tuple[str, ...] = Field(default=())
    search_authoritative_for: tuple[str, ...] = Field(default=())
    search_may_not_use_for: tuple[str, ...] = Field(default=())
    search_discovery_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G7RegionGroundingMatrixRow(_G7Model):
    """One G7 grounding matrix row with explicit blockers and limitations."""

    case_id: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    candidate_source: Layer3G7CandidateSource
    row_grounding_status: Layer3G7RowGroundingStatus
    envelope_posture: Literal["in", "out", "pending"] = "pending"
    source_contract_refs: tuple[str, ...] = Field(default=())
    search_ledger_refs: tuple[str, ...] = Field(default=())
    search_authoritative_for: tuple[str, ...] = Field(default=())
    search_may_not_use_for: tuple[str, ...] = Field(default=())
    g4_promotion_record_refs: tuple[str, ...] = Field(default=())
    g4_promotion_state: str = "missing"
    g5_conversion_record_refs: tuple[str, ...] = Field(default=())
    g5_conversion_outcome: str | None = None
    grounding_disposition: str | None = None
    g6_request_refs: tuple[str, ...] = Field(default=())
    g6_agent_refs: tuple[str, ...] = Field(default=())
    g6_diagnostic_refs: tuple[str, ...] = Field(default=())
    gl_legal_status: str = "not_required"
    gl_legal_refs: tuple[str, ...] = Field(default=())
    s14_declared_envelope_refs: tuple[str, ...] = Field(default=())
    s14_pending_feed_refs: tuple[str, ...] = Field(default=())
    demand_refs: tuple[str, ...] = Field(default=())
    s12_voi_refs: tuple[str, ...] = Field(default=())
    s3_demand_pull_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    time_refs: tuple[str, ...] = Field(default=())
    missing_ref_blockers: tuple[str, ...] = Field(default=())
    missing_ref_limitations: tuple[str, ...] = Field(default=())
    blockers: tuple[str, ...] = Field(default=())
    limitations: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


class Layer3G7RegionGroundingMatrix(_G7Model):
    """G7 matrix joining bounded candidates to available grounding refs."""

    schema_version: str = G7_SCHEMA_VERSION
    rule_version: str = G7_RULE_VERSION
    matrix_id: str
    region_ref: str = Field(min_length=1)
    candidate_set_ref: str = Field(min_length=1)
    rows: tuple[Layer3G7RegionGroundingMatrixRow, ...] = Field(default=())
    row_count: int = Field(default=0, ge=0)
    coverage_status: Layer3G7CoverageStatus
    grounded_case_count: int = Field(default=0, ge=0)
    blocked_case_count: int = Field(default=0, ge=0)
    search_recall_freshness_join: Layer3G7SearchRecallFreshnessJoin
    search_discovery_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G7_MAY_NOT_USE_FOR


def default_readiness_candidate_rows() -> tuple[dict[str, object], ...]:
    """Return deterministic readiness candidates for the UA MSME adjacent region."""

    common = {
        "region_ref": "region://ua/msme-adjacent",
        "search_ledger_refs": (
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        ),
        "declared_envelope_refs": ("envelope://g7/ua-msme-adjacent",),
        "time_refs": ("time://policy-year/2022",),
    }
    return (
        {
            **common,
            "case_id": "ua-msme-affordable-loans-2022",
            "candidate_source": "current_g5_seed_case",
            "adjacency_basis_refs": ("adjacency://ua-msme/pinned-g5-seed",),
            "demand_refs": ("demand://g5/ua-msme-affordable-loans-2022",),
            "s3_demand_pull_refs": ("s3-demand-pull://ua-msme/first-proving-ground",),
            "accountable_principal_refs": ("principal://ua-msme/first-proving-ground",),
            "envelope_posture": "in",
        },
        {
            **common,
            "case_id": "ua-msme-energy-resilience-2022",
            "candidate_source": "readiness_control_plane_fixture",
            "adjacency_basis_refs": ("adjacency://ua-msme/energy-resilience",),
            "demand_refs": ("demand://s12/ua-msme/energy-resilience",),
        },
        {
            **common,
            "case_id": "ua-msme-export-credit-2022",
            "candidate_source": "readiness_control_plane_fixture",
            "adjacency_basis_refs": ("adjacency://ua-msme/export-credit",),
            "demand_refs": ("demand://s12/ua-msme/export-credit",),
        },
        {
            **common,
            "case_id": "ua-msme-displaced-firm-recovery-2022",
            "candidate_source": "readiness_control_plane_fixture",
            "adjacency_basis_refs": ("adjacency://ua-msme/displaced-firm-recovery",),
            "demand_refs": ("demand://s12/ua-msme/displaced-firm-recovery",),
        },
    )


def build_g7_region_candidate_set(
    *,
    region_ref: str,
    case_rows: Iterable[Mapping[str, object]],
) -> Layer3G7RegionCandidateSet:
    """Build a bounded G7 candidate set from shaped case rows."""

    cases = tuple(_candidate_from_row(region_ref=region_ref, row=row) for row in case_rows)
    is_control_plane = all(
        row.candidate_source in {"current_g5_seed_case", "readiness_control_plane_fixture"}
        for row in cases
    )
    return Layer3G7RegionCandidateSet(
        candidate_set_id=f"layer3-g7://region-candidate-set/{_slug_ref(region_ref)}",
        region_ref=region_ref,
        cases=cases,
        case_count=len(cases),
        coverage_authority_status="control_plane_only"
        if is_control_plane
        else "external_input_pending",
    )


def build_g7_search_recall_freshness_join(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    search_discovery_refs: Iterable[str] = (),
) -> Layer3G7SearchRecallFreshnessJoin:
    """Join G1 source contracts and search ledgers without minting coverage authority."""

    root = Path(repo_root)
    source_contracts = _g1_source_contract_refs(
        _read_json(root / G1_GROUNDED_SOURCE_CONTRACTS_PATH)
    )
    search_payload = _as_mapping(_read_json(root / G1_SEARCH_RECALL_FRESHNESS_PATH)).get(
        "search_recall_freshness", {}
    )
    search_status = _as_mapping(search_payload)
    search_ledgers = _rows_from_payload(_read_json(root / G1_SUBSTRATE_SEARCH_LEDGERS_PATH))
    search_ledger_refs = _dedupe(
        row.get("ledger_id") or row.get("replay_key") for row in search_ledgers
    )
    search_authoritative_for = _dedupe(
        value for row in search_ledgers for value in _as_str_tuple(row.get("authoritative_for"))
    )
    search_may_not_use_for = _dedupe(
        value for row in search_ledgers for value in _as_str_tuple(row.get("may_not_use_for"))
    )
    issue_codes: list[str] = []
    if not source_contracts or not search_ledger_refs:
        issue_codes.append("layer3_g7_search_recall_or_freshness_missing")
    if search_authoritative_for or "search_hit_as_authority" not in search_may_not_use_for:
        issue_codes.append("layer3_g7_search_hit_counted_as_coverage")
    return Layer3G7SearchRecallFreshnessJoin(
        status="fail" if issue_codes else "pass",
        g1_source_contract_refs=source_contracts,
        g1_search_recall_status=_search_status(search_status, "search_recall_status"),
        g1_index_freshness_status=_search_status(search_status, "index_freshness_status"),
        search_ledger_refs=search_ledger_refs,
        search_authoritative_for=search_authoritative_for,
        search_may_not_use_for=search_may_not_use_for,
        search_discovery_refs=tuple(search_discovery_refs),
        issue_codes=tuple(issue_codes),
    )


def build_g7_region_grounding_matrix(
    *,
    candidate_set: Layer3G7RegionCandidateSet,
    search_discovery_refs: Iterable[str] = (),
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> Layer3G7RegionGroundingMatrix:
    """Join each G7 region candidate to existing grounding and diagnostic refs."""

    root = Path(repo_root)
    search_refs = tuple(search_discovery_refs)
    search_join = build_g7_search_recall_freshness_join(
        repo_root=root,
        search_discovery_refs=search_refs,
    )
    g4_by_case = _records_by_case_id(
        _as_mapping(_read_json(root / G4_PROMOTION_RECORDS_PATH)).get("promotion_records")
    )
    g5_by_case = _records_by_case_id(
        _as_mapping(_read_json(root / G5_CONVERSION_RECORDS_PATH)).get("conversion_records")
    )
    g6_demand = _as_mapping(_read_json(root / G6_GROUNDING_DEMAND_RECORD_PATH))
    g6_audit = _as_mapping(_read_json(root / G6_ORCHESTRATION_CHOICE_AUDIT_PATH))
    gl_readiness = _as_mapping(_read_json(root / GL_READINESS_PATH))
    gl_report = _as_mapping(_read_json(root / GL_LEGAL_AUTHORITY_REPORT_PATH))
    s14_manifest = _as_mapping(_read_json(root / S14_ASSURANCE_MANIFEST_PATH))

    rows = tuple(
        _build_grounding_matrix_row(
            candidate=candidate,
            search_join=search_join,
            g4_record=g4_by_case.get(candidate.case_id),
            g5_record=g5_by_case.get(candidate.case_id),
            g6_demand=g6_demand,
            g6_audit=g6_audit,
            gl_readiness=gl_readiness,
            gl_report=gl_report,
            s14_manifest=s14_manifest,
        )
        for candidate in candidate_set.cases
    )
    grounded_count = sum(
        1 for row in rows if row.row_grounding_status in {"grounded_limited", "grounded_abstention"}
    )
    issue_codes = _dedupe(
        (
            *search_join.issue_codes,
            *(code for row in rows for code in row.issue_codes),
        )
    )
    coverage_status = _matrix_coverage_status(
        candidate_set=candidate_set,
        search_discovery_refs=search_refs,
        grounded_count=grounded_count,
    )
    if coverage_status == "blocked_control_plane_only":
        issue_codes = _dedupe(
            (*issue_codes, "layer3_g7_candidate_set_hardcoded_as_coverage")
        )
    if coverage_status == "blocked_search_control_plane_only":
        issue_codes = _dedupe((*issue_codes, "layer3_g7_search_hit_counted_as_coverage"))
    return Layer3G7RegionGroundingMatrix(
        matrix_id=f"layer3-g7://region-grounding-matrix/{_slug_ref(candidate_set.region_ref)}",
        region_ref=candidate_set.region_ref,
        candidate_set_ref=candidate_set.candidate_set_id,
        rows=rows,
        row_count=len(rows),
        coverage_status=coverage_status,
        grounded_case_count=grounded_count,
        blocked_case_count=sum(1 for row in rows if row.row_grounding_status.startswith("blocked")),
        search_recall_freshness_join=search_join,
        search_discovery_refs=search_refs,
        issue_codes=issue_codes,
    )


def build_g7_region_conversion_records(
    *,
    region_ref: str,
    conversion_inputs: Iterable[Mapping[str, object] | Layer3G7RegionCaseConversionInput],
) -> tuple[Layer3G7RegionConversionRecord, ...]:
    """Build per-case G7 conversion records from upstream G5/G4-shaped inputs."""

    return tuple(
        _build_g7_region_conversion_record(
            region_ref=region_ref,
            conversion_input=_conversion_input_from_row(
                region_ref=region_ref,
                row=row,
            ),
        )
        for row in conversion_inputs
    )


def build_g7_region_conversion_status_matrix(
    *,
    region_ref: str,
    records: Iterable[Layer3G7RegionConversionRecord],
) -> Layer3G7RegionConversionStatusMatrix:
    """Aggregate region conversion records without minting wider authority."""

    rows = tuple(records)
    grounded_count = sum(1 for row in rows if row.is_grounded)
    blocked_count = len(rows) - grounded_count
    issue_codes = _dedupe(code for row in rows for code in row.issue_codes)
    if not rows or grounded_count == 0:
        issue_codes = _dedupe((*issue_codes, "layer3_g7_no_real_grounded_region_breadth"))
    return Layer3G7RegionConversionStatusMatrix(
        matrix_id=f"layer3-g7://region-conversion-status-matrix/{_slug_ref(region_ref)}",
        region_ref=region_ref,
        status="pass" if grounded_count > 0 and not issue_codes else "blocked",
        records=rows,
        grounded_region_case_count=grounded_count,
        blocked_region_case_count=blocked_count,
        issue_codes=issue_codes,
    )


def synthetic_future_grounded_region_records(
    *,
    governed_promotion_status: Layer3G7GovernedPromotionJoinStatus = "pass",
    omit_g4_gate_ref: str | None = None,
    g4_record_source: str = "synthetic_g4_compatible_test_record",
) -> tuple[dict[str, object], ...]:
    """Return test-scope future records that validate through G5 and G4 shapes."""

    cases = (
        ("ua-msme-energy-resilience-2022", "typed_blocker -> grounded_limited"),
        ("ua-msme-export-credit-2022", "typed_blocker -> grounded_abstention"),
    )
    return tuple(
        {
            "case_id": case_id,
            "region_ref": "region://ua/msme-adjacent",
            "source_class": "synthetic_g5_compatible_test_record",
            "g5_conversion_record": _synthetic_g5_conversion_record(
                case_id=case_id,
                conversion_outcome=conversion_outcome,
            ),
            "g4_promotion_record": _synthetic_g4_promotion_record(
                case_id=case_id,
                omit_gate_ref=omit_g4_gate_ref,
            ),
            "governed_promotion_status": governed_promotion_status,
            "source_contract_status": "pass",
            "search_health_status": "pass",
            "effective_independence_status": "pass",
            "search_status": "adapter_backed",
            "g4_record_source": g4_record_source,
        }
        for case_id, conversion_outcome in cases
    )


_DEFAULT_S12_PROJECTION: object = object()


def build_g7_s12_growth_thermometer_projection(
    *,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    demand_pull_refs: Iterable[str] = (),
    accountable_principal_refs: Iterable[str] = (),
    reused_primitive_refs: Iterable[str] = (),
    one_off_growth_refs: Iterable[str] = (),
    held_out_status: Literal["pending_s14", "executed", "missing"] = "pending_s14",
    held_out_battery_ref: str | None = None,
    certified_envelope_delta_refs: Iterable[str] = (),
    growth_without_envelope_delta_count: int = 0,
    growth_counting_disposition: Layer3G7GrowthCountingDisposition = (
        "counted_mechanism_growth"
    ),
    may_not_use_for: Iterable[str] = (),
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> Layer3G7S12GrowthThermometerProjection:
    """Project G5/S12 demand and reuse signals for G7 without S12 authority."""

    rows = _coerce_g7_conversion_records(conversion_records)
    g5_inputs = _g5_s12_projection_inputs(repo_root=repo_root)
    resolved_demand_refs = _dedupe((*demand_pull_refs, *g5_inputs["demand_pull_refs"]))
    resolved_principal_refs = _dedupe(
        (*accountable_principal_refs, *g5_inputs["accountable_principal_refs"])
    )
    resolved_delta_refs = _dedupe(
        (*certified_envelope_delta_refs, *g5_inputs["certified_envelope_delta_refs"])
    )
    resolved_reuse_refs = _dedupe(
        (
            *reused_primitive_refs,
            *g5_inputs["reuse_refs"],
            *_conversion_reuse_refs(rows),
        )
    )
    one_off_refs = tuple(one_off_growth_refs)
    s12_may_not = tuple(may_not_use_for) or _g5_s12_projection_may_not_use_for()
    reuse_rate = _safe_ratio(
        len([row for row in rows if row.is_grounded and _case_reuse_refs(row)]),
        max(1, sum(1 for row in rows if row.is_grounded)),
    )
    issue_codes: list[str] = []
    if growth_counting_disposition == "counted_mechanism_growth" and (
        growth_without_envelope_delta_count > 0 or not resolved_delta_refs
    ):
        issue_codes.append("layer3_g7_s12_growth_without_certified_delta")
    if held_out_status != "pending_s14" or held_out_battery_ref:
        issue_codes.append("layer3_g7_s12_held_out_status_overclaimed")
    if not set(s12_may_not) >= set(_g5_s12_projection_may_not_use_for()):
        issue_codes.append("layer3_g7_s12_deny_list_omitted")
    if one_off_refs and growth_counting_disposition == "counted_mechanism_growth":
        issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")

    contract_payload = _s12_growth_projection_contract_payload(
        thermometer_ref="s12-growth-thermometer://layer3-g7/ua-msme-adjacent",
        held_out_status=held_out_status,
        growth_without_envelope_delta_count=growth_without_envelope_delta_count,
        growth_counting_disposition=growth_counting_disposition,
        may_not_use_for=s12_may_not,
    )
    contract = _verify_s12_projection_contract(contract_payload)
    contract_issue_codes = _as_str_tuple(contract.get("issue_codes"))
    if contract.get("status") != "pass":
        issue_codes.append("layer3_g7_s12_projection_bypasses_resource_economics_shape")
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G7S12GrowthThermometerProjection(
        status="pass" if not issue_codes else "blocked",
        thermometer_ref="s12-growth-thermometer://layer3-g7/ua-msme-adjacent",
        g5_demand_pull_attempt_ref=G5_DEMAND_PULL_ATTEMPT_RECORD_PATH.as_posix(),
        g5_envelope_expansion_delta_ref=G5_ENVELOPE_EXPANSION_DELTA_PATH.as_posix(),
        g5_dependency_health_snapshot_ref=(
            G5_DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH.as_posix()
        ),
        demand_pull_refs=resolved_demand_refs,
        accountable_principal_refs=resolved_principal_refs,
        reused_primitive_refs=resolved_reuse_refs,
        one_off_growth_refs=one_off_refs,
        held_out_status=held_out_status,
        held_out_battery_ref=held_out_battery_ref,
        certified_envelope_delta_refs=resolved_delta_refs,
        growth_without_envelope_delta_count=growth_without_envelope_delta_count,
        growth_counting_disposition=growth_counting_disposition,
        reuse_rate=reuse_rate,
        s12_projection_contract_status=str(contract.get("status") or "missing"),
        s12_projection_contract_issue_codes=contract_issue_codes,
        s12_projection_contract_verification=contract,
        issue_codes=tuple(issue_codes),
        may_not_use_for=s12_may_not,
    )


def build_g7_mechanism_reuse_ledger(
    *,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    s12_growth_thermometer_projection: (
        Layer3G7S12GrowthThermometerProjection | None
    ) = None,
    bespoke_patch_refs: Iterable[str] = (),
    one_off_growth_refs: Iterable[str] = (),
    reuse_threshold: float = 0.5,
) -> Layer3G7MechanismReuseLedger:
    """Build a mechanism reuse ledger that blocks bespoke patches as reuse."""

    rows = _coerce_g7_conversion_records(conversion_records)
    projection_reuse_refs = (
        s12_growth_thermometer_projection.reused_primitive_refs
        if s12_growth_thermometer_projection is not None
        else ()
    )
    one_off_refs = _dedupe(
        (
            *one_off_growth_refs,
            *(
                s12_growth_thermometer_projection.one_off_growth_refs
                if s12_growth_thermometer_projection is not None
                else ()
            ),
        )
    )
    bespoke_refs = tuple(bespoke_patch_refs)
    records = tuple(
        _build_g7_mechanism_reuse_record(
            row=row,
            projection_reuse_refs=projection_reuse_refs,
            bespoke_patch_refs=bespoke_refs,
            one_off_growth_refs=one_off_refs,
        )
        for row in rows
    )
    grounded_count = sum(1 for row in rows if row.is_grounded)
    reused_count = sum(1 for row in records if row.reuse_status == "reused")
    reuse_rate = _safe_ratio(reused_count, grounded_count)
    issue_codes: list[str] = []
    if bespoke_refs:
        issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")
        reuse_status: Layer3G7MechanismReuseStatus = "blocked_by_bespoke_patch"
    elif one_off_refs:
        issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")
        reuse_status = "blocked_by_one_off_growth"
    elif grounded_count == 0:
        issue_codes.append("layer3_g7_sublinear_claim_without_grounded_cases")
        reuse_status = "blocked_insufficient_grounded_cases"
    elif reuse_rate < reuse_threshold:
        reuse_status = "blocked_low_reuse"
    else:
        reuse_status = "pass"
    return Layer3G7MechanismReuseLedger(
        ledger_id="layer3-g7://mechanism-reuse-ledger/ua-msme-adjacent",
        reuse_status=reuse_status,
        records=records,
        grounded_region_case_count=grounded_count,
        reused_case_count=reused_count,
        mechanism_reuse_rate=reuse_rate,
        reuse_threshold=reuse_threshold,
        reused_primitive_refs=_dedupe(
            ref for record in records for ref in record.reused_primitive_refs
        ),
        one_off_growth_refs=one_off_refs,
        bespoke_patch_refs=bespoke_refs,
        bespoke_patch_count=len(bespoke_refs),
        issue_codes=tuple(issue_codes),
    )


def build_g7_marginal_grounding_cost_ledger(
    *,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger,
    s12_growth_thermometer_projection: (
        Layer3G7S12GrowthThermometerProjection | None | object
    ) = _DEFAULT_S12_PROJECTION,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None = None,
    baseline_seed_effort_units: float = 10.0,
) -> Layer3G7MarginalGroundingCostLedger:
    """Build the G7 marginal grounding-cost ledger with sublinear blockers."""

    rows = _coerce_g7_conversion_records(conversion_records)
    if s12_growth_thermometer_projection is _DEFAULT_S12_PROJECTION:
        growth_projection = build_g7_s12_growth_thermometer_projection(
            conversion_records=rows
        )
    elif isinstance(s12_growth_thermometer_projection, Layer3G7S12GrowthThermometerProjection):
        growth_projection = s12_growth_thermometer_projection
    else:
        growth_projection = None
    grounded_rows = tuple(row for row in rows if row.is_grounded)
    added_case_efforts = tuple(4.0 for _row in grounded_rows)
    mean_added = _safe_mean(added_case_efforts)
    ratio = mean_added / baseline_seed_effort_units if baseline_seed_effort_units else 0.0
    cost_rows = _g7_marginal_cost_rows(
        rows=rows,
        added_case_efforts=added_case_efforts,
    )
    issue_codes: list[str] = [*mechanism_reuse_ledger.issue_codes]
    semantic_loss_blocker_count = (
        semantic_loss_ledger.semantic_loss_blocker_count
        if semantic_loss_ledger is not None
        else sum(
            1
            for row in rows
            if "layer3_g7_semantic_loss_hidden_by_region_score" in row.issue_codes
        )
    )
    if semantic_loss_ledger is not None:
        issue_codes.extend(semantic_loss_ledger.issue_codes)
    if growth_projection is not None:
        issue_codes.extend(growth_projection.issue_codes)
    status = _g7_sublinear_cost_status(
        grounded_count=len(grounded_rows),
        marginal_cost_ratio_to_seed=ratio,
        mechanism_reuse_ledger=mechanism_reuse_ledger,
        growth_projection=growth_projection,
        semantic_loss_blocker_count=semantic_loss_blocker_count,
        issue_codes=issue_codes,
    )
    return Layer3G7MarginalGroundingCostLedger(
        ledger_id="layer3-g7://marginal-grounding-cost-ledger/ua-msme-adjacent",
        baseline_seed_effort_units=baseline_seed_effort_units,
        added_case_effort_units=added_case_efforts,
        mean_added_case_effort_units=mean_added,
        marginal_cost_ratio_to_seed=ratio,
        cumulative_grounding_cost_curve=tuple(
            row.cumulative_effort_units for row in cost_rows
        ),
        grounded_region_case_count=len(grounded_rows),
        added_region_case_count=len(grounded_rows),
        bespoke_patch_count=mechanism_reuse_ledger.bespoke_patch_count,
        semantic_loss_blocker_count=semantic_loss_blocker_count,
        sublinear_marginal_cost_status=status,
        rows=cost_rows,
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_region_envelope_expansion_delta(
    *,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    certified_envelope_delta_refs: Iterable[str] = (),
    envelope_revision_direction: Layer3G7EnvelopeRevisionDirection = "expand",
    materialized_from_s12_growth_entry_ref: str | None = None,
    assurance_case_delta_ref: str | None = None,
    region_ref: str = "region://ua/msme-adjacent",
) -> Layer3G7RegionEnvelopeExpansionDelta:
    """Build the G7 region expansion delta and block non-expand revisions."""

    rows = _coerce_g7_conversion_records(conversion_records)
    grounded_rows = tuple(row for row in rows if row.is_grounded)
    issue_codes: list[str] = []
    blocker_refs: list[str] = []
    limitation_refs: list[str] = []
    delta_refs = tuple(certified_envelope_delta_refs)
    positive_shape = (
        bool(delta_refs)
        and envelope_revision_direction == "expand"
        and materialized_from_s12_growth_entry_ref is not None
        and assurance_case_delta_ref is not None
    )
    if grounded_rows and envelope_revision_direction != "expand":
        issue_codes.append("layer3_g7_pending_delta_counted_as_expansion")
        limitation_refs.append("limitation://g7/non-expand-envelope-revision")
    elif grounded_rows and not positive_shape:
        issue_codes.append("layer3_g7_s13_certified_delta_missing")
        blocker_refs.append("blocker://g7/s13-certified-expand-delta-missing")

    expanded_count = len(grounded_rows) if positive_shape else 0
    denominator = max(1, len(rows))
    expansion_rate = _safe_ratio(expanded_count, denominator)
    if expanded_count > 0:
        expansion_status: Layer3G7RegionExpansionStatus = "pass"
    elif grounded_rows:
        expansion_status = "blocked"
    else:
        expansion_status = "flat"
    return Layer3G7RegionEnvelopeExpansionDelta(
        delta_id=f"layer3-g7://region-envelope-expansion-delta/{_slug_ref(region_ref)}",
        region_ref=region_ref,
        expansion_status=expansion_status,
        envelope_revision_direction=envelope_revision_direction,
        certified_envelope_delta_refs=delta_refs,
        materialized_from_s12_growth_entry_ref=materialized_from_s12_growth_entry_ref,
        assurance_case_delta_ref=assurance_case_delta_ref,
        grounded_region_case_count=len(grounded_rows),
        expanded_case_count=expanded_count,
        denominator=denominator,
        envelope_expansion_rate=expansion_rate,
        expanded_case_refs=tuple(row.case_id for row in grounded_rows)
        if expanded_count
        else (),
        blocker_refs=tuple(blocker_refs),
        limitation_refs=tuple(limitation_refs),
        issue_codes=tuple(issue_codes),
    )


def build_g7_region_semantic_loss_ledger(
    *,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    source_truth_lost_case_ids: Iterable[str] = (),
    lineage_collapsed_case_ids: Iterable[str] = (),
    authority_boundary_weakened_case_ids: Iterable[str] = (),
    time_roles_merged_case_ids: Iterable[str] = (),
    legal_or_mandate_status_dropped_case_ids: Iterable[str] = (),
    g6_candidate_text_case_ids: Iterable[str] = (),
    caveats_dropped_case_ids: Iterable[str] = (),
    certified_delta_ref_dropped_case_ids: Iterable[str] = (),
) -> Layer3G7RegionSemanticLossLedger:
    """Build a semantic-loss ledger that blocks hidden regional score inflation."""

    rows = _coerce_g7_conversion_records(conversion_records)
    source_truth = set(source_truth_lost_case_ids)
    lineage = set(lineage_collapsed_case_ids)
    authority = set(authority_boundary_weakened_case_ids)
    time_roles = set(time_roles_merged_case_ids)
    legal = set(legal_or_mandate_status_dropped_case_ids)
    g6_text = set(g6_candidate_text_case_ids)
    caveats = set(caveats_dropped_case_ids)
    delta_dropped = set(certified_delta_ref_dropped_case_ids)
    semantic_rows = tuple(
        _build_g7_semantic_loss_row(
            row=row,
            source_truth_lost=row.case_id in source_truth,
            lineage_collapsed=row.case_id in lineage,
            authority_boundary_weakened=row.case_id in authority,
            time_roles_merged=row.case_id in time_roles,
            legal_or_mandate_status_dropped=row.case_id in legal,
            g6_candidate_text_as_evidence=(
                row.case_id in g6_text or row.source_class == "g6_candidate"
            ),
            case_caveats_disappeared=row.case_id in caveats,
            certified_delta_ref_dropped=row.case_id in delta_dropped,
        )
        for row in rows
    )
    blocker_count = sum(
        1 for row in semantic_rows if row.semantic_loss_status == "blocked"
    )
    return Layer3G7RegionSemanticLossLedger(
        ledger_id="layer3-g7://region-semantic-loss-ledger/ua-msme-adjacent",
        semantic_loss_status="blocked" if blocker_count else "pass",
        rows=semantic_rows,
        semantic_loss_blocker_count=blocker_count,
        issue_codes=_dedupe(code for row in semantic_rows for code in row.issue_codes),
    )


def build_g7_health_metric_delta(
    *,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None = None,
    governance_throughput_status: str = "pass",
    search_recall_status: str = "pass",
    demand_pull_vs_abstention_status: str = "pass",
) -> Layer3G7HealthMetricDelta:
    """Build the G7 health metric delta without useful-design-rate optimization."""

    metrics = {
        "envelope-expansion-rate(region)": region_envelope_expansion_delta.expansion_status,
        "adapter-semantic-loss(region)": (
            semantic_loss_ledger.semantic_loss_status
            if semantic_loss_ledger is not None
            else "pass"
        ),
        "governance-throughput(region)": governance_throughput_status,
        "search-recall@known-seeds+index-staleness(region)": search_recall_status,
        "demand-pull-vs-abstention(region)": demand_pull_vs_abstention_status,
    }
    issue_codes: list[str] = [*region_envelope_expansion_delta.issue_codes]
    if semantic_loss_ledger is not None:
        issue_codes.extend(semantic_loss_ledger.issue_codes)
    if governance_throughput_status == "missing":
        issue_codes.append("layer3_g7_governance_throughput_missing")
    status: Layer3G7HealthMetricDeltaStatus
    if region_envelope_expansion_delta.expansion_status == "flat" and not issue_codes:
        status = "flat"
    elif issue_codes:
        status = "blocked"
    else:
        status = "pass"
    return Layer3G7HealthMetricDelta(
        status=status,
        metrics=metrics,
        envelope_expansion_rate_region=(
            region_envelope_expansion_delta.envelope_expansion_rate
        ),
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_status_composition_ledger(
    *,
    region_conversion_status_matrix: Layer3G7RegionConversionStatusMatrix,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger,
    marginal_cost_ledger: Layer3G7MarginalGroundingCostLedger,
    s14_feed_status: str,
    public_projection_status_claim: str = "missing",
    governance_throughput_status: str = "pass",
) -> Layer3G7StatusCompositionLedger:
    """Compose G7 status so the strongest public claim cannot exceed blockers."""

    issue_codes: list[str] = [
        *region_conversion_status_matrix.issue_codes,
        *region_envelope_expansion_delta.issue_codes,
        *semantic_loss_ledger.issue_codes,
        *marginal_cost_ledger.issue_codes,
    ]
    if s14_feed_status.startswith("blocked") or s14_feed_status == "missing":
        issue_codes.append("layer3_g7_s14_feed_missing")
    if governance_throughput_status == "missing":
        issue_codes.append("layer3_g7_governance_throughput_missing")
    blocked_inputs = [
        region_conversion_status_matrix.status != "pass",
        region_envelope_expansion_delta.expansion_status != "pass",
        semantic_loss_ledger.semantic_loss_status != "pass",
        marginal_cost_ledger.sublinear_marginal_cost_status != "pass",
        s14_feed_status.startswith("blocked") or s14_feed_status == "missing",
        governance_throughput_status == "missing",
    ]
    if public_projection_status_claim == "pass" and any(blocked_inputs):
        issue_codes.append("layer3_g7_status_composition_missing")
    status: Layer3G7StatusCompositionStatus = "blocked" if issue_codes else "pass"
    return Layer3G7StatusCompositionLedger(
        ledger_id="layer3-g7://status-composition-ledger/ua-msme-adjacent",
        status=status,
        weakest_region_status="blocked" if any(blocked_inputs) else "pass",
        public_projection_status_claim=public_projection_status_claim,
        region_conversion_status=region_conversion_status_matrix.status,
        region_expansion_status=region_envelope_expansion_delta.expansion_status,
        semantic_loss_status=semantic_loss_ledger.semantic_loss_status,
        marginal_cost_status=marginal_cost_ledger.sublinear_marginal_cost_status,
        s14_feed_status=s14_feed_status,
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_s14_grounded_breadth_feed(
    *,
    region_ref: str,
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None = None,
    fixture_grounded_refs: Iterable[str] = (),
    g6_candidate_refs: Iterable[str] = (),
) -> Layer3G7S14GroundedBreadthFeed:
    """Build a consumer-ready S14 grounded-breadth feed from real G7 rows."""

    rows = _coerce_g7_conversion_records(conversion_records)
    grounded_rows = tuple(row for row in rows if row.is_grounded)
    issue_codes: list[str] = []
    limitations: list[str] = []
    fixture_refs = tuple(fixture_grounded_refs)
    g6_refs = tuple(g6_candidate_refs)
    if fixture_refs:
        issue_codes.append("layer3_g7_s14_feed_uses_fixtures")
        limitations.extend(fixture_refs)
    if g6_refs:
        issue_codes.append("layer3_g7_g6_candidate_counted_as_grounded")
        limitations.extend(g6_refs)
    for row in rows:
        issue_codes.extend(row.issue_codes)
    if not grounded_rows:
        issue_codes.append("layer3_g7_s14_feed_missing")
    grounded_authority = _build_g7_s14_grounded_authority_coverage(grounded_rows)
    envelope_dynamics = _build_g7_s14_envelope_revision_dynamics(
        region_envelope_expansion_delta
    )
    missing_limitations = _g7_s14_missing_grounding_limitations(grounded_rows)
    limitations.extend(missing_limitations)
    status: Layer3G7S14FeedStatus = (
        "pass" if grounded_rows and not issue_codes else "blocked_no_real_grounded_breadth"
    )
    return Layer3G7S14GroundedBreadthFeed(
        feed_id=f"layer3-g7://s14-grounded-breadth-feed/{_slug_ref(region_ref)}",
        feed_ref=f"layer3-g7://s14/grounded-breadth-feed/{_slug_ref(region_ref)}",
        region_ref=region_ref,
        status=status,
        grounded_region_case_refs=tuple(row.case_id for row in grounded_rows),
        grounded_authority_coverage_refs=(grounded_authority.coverage_ref,),
        a_firewall_refs=tuple(grounded_authority.a_firewall_refs),
        claim_evidence_binding_refs=tuple(grounded_authority.claim_evidence_binding_refs),
        mandate_legal_refs=tuple(grounded_authority.mandate_legitimacy_refs),
        capacity_regime_coupling_refs=_dedupe(
            (
                *grounded_authority.capacity_check_refs,
                *grounded_authority.regime_refs,
                *grounded_authority.coupling_refs,
            )
        ),
        mechanism_generality_report_refs=("pdc://layer2/s14/mechanism-generality",),
        envelope_revision_delta_refs=tuple(envelope_dynamics.certified_envelope_delta_refs),
        visible_limitation_refs=_dedupe(limitations),
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_s14_mechanism_generality_projection(
    *,
    s12_growth_thermometer_projection: Layer3G7S12GrowthThermometerProjection,
    one_off_growth_refs: Iterable[str] = (),
) -> Layer3G7S14MechanismGeneralityProjection:
    """Project G7 S12 growth into the S14 mechanism-generality helper."""

    from polisyos.runtime.quality.layer2_universality_assurance import (
        build_s14_mechanism_generality_from_growth_thermometer,
    )

    one_off_refs = _dedupe(
        (*s12_growth_thermometer_projection.one_off_growth_refs, *one_off_growth_refs)
    )
    growth_payload = {
        "thermometer_ref": s12_growth_thermometer_projection.thermometer_ref,
        "held_out_status": s12_growth_thermometer_projection.held_out_status,
        "reuse_rate": s12_growth_thermometer_projection.reuse_rate,
        "reused_primitive_refs": list(
            s12_growth_thermometer_projection.reused_primitive_refs
        ),
        "one_off_growth_refs": list(one_off_refs),
    }
    report = build_s14_mechanism_generality_from_growth_thermometer(
        growth_thermometer=growth_payload,
        held_out_case_refs=[],
    )
    issue_codes: list[str] = []
    if one_off_refs:
        issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")
    return Layer3G7S14MechanismGeneralityProjection(
        projection_id="layer3-g7://s14-mechanism-generality-projection/ua-msme-adjacent",
        projection_ref="layer3-g7://s14/mechanism-generality-projection",
        status="blocked" if issue_codes else "pass",
        mechanism_generality_report_ref=report.report_ref,
        growth_thermometer_ref=report.growth_thermometer_ref,
        mechanism_reuse_rate=report.mechanism_reuse_rate,
        reused_mechanism_refs=tuple(report.reused_mechanism_refs),
        bespoke_patch_refs=tuple(report.bespoke_patch_refs),
        held_out_status=report.s12_held_out_status,
        issue_codes=tuple(issue_codes),
        report_payload=report.model_dump(mode="json"),
    )


def build_g7_s14_battery_input_manifest(
    *,
    grounded_breadth_feed: Layer3G7S14GroundedBreadthFeed,
    mechanism_generality_projection: Layer3G7S14MechanismGeneralityProjection,
) -> Layer3G7S14BatteryInputManifest:
    """Build the read-only manifest that S14 may inspect as external input."""

    issue_codes = _dedupe(
        (*grounded_breadth_feed.issue_codes, *mechanism_generality_projection.issue_codes)
    )
    return Layer3G7S14BatteryInputManifest(
        s14_battery_input_manifest_id="layer3-g7-s14-battery-input:ua-msme-adjacent",
        grounded_breadth_feed_ref=grounded_breadth_feed.feed_ref,
        mechanism_generality_projection_ref=(
            mechanism_generality_projection.projection_ref
        ),
        grounded_authority_coverage_ref=(
            grounded_breadth_feed.grounded_authority_coverage_refs[0]
            if grounded_breadth_feed.grounded_authority_coverage_refs
            else "missing://g7/s14/grounded-authority-coverage"
        ),
        envelope_revision_dynamics_ref="pdc://layer2/s14/envelope-revision-dynamics",
        certified_envelope_delta_refs=grounded_breadth_feed.envelope_revision_delta_refs,
        visible_limitation_refs=grounded_breadth_feed.visible_limitation_refs,
        issue_codes=issue_codes,
        may_not_use_for=_dedupe((*G7_MAY_NOT_USE_FOR, "s14_universality")),
    )


def build_g7_s14_consumer_gate(
    *,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None,
    universality_claim_text: str | None = None,
    public_projection_payload: Mapping[str, object] | None = None,
) -> Layer3G7S14ConsumerGate:
    """Gate G7 handoff to S14 and block universal wording without S14 authority."""

    from polisyos.runtime.quality.layer2_universality_assurance import (
        verify_universality_claim_authority,
    )

    issue_codes: list[str] = []
    s14_issue_codes: list[str] = []
    missing_label = None
    manifest_ref = None
    if s14_battery_input_manifest is None:
        issue_codes.append("layer3_g7_s14_battery_input_manifest_missing")
        missing_label = "consumer_missing"
    else:
        manifest_ref = s14_battery_input_manifest.s14_battery_input_manifest_id
        issue_codes.extend(s14_battery_input_manifest.issue_codes)
    if universality_claim_text:
        issue_codes.append("layer3_g7_universal_claim_without_s14_gate")
        s14_issue_codes.extend(
            _as_str_tuple(
                verify_universality_claim_authority(
                    {"claim_text": universality_claim_text}
                ).get("false_clear_counts")
            )
        )
    if public_projection_payload is not None:
        authority_report = verify_universality_claim_authority(public_projection_payload)
        s14_issue_codes.extend(
            str(issue.get("code"))
            for issue in authority_report.get("issues", ())
            if isinstance(issue, Mapping) and issue.get("code") is not None
        )
        if "battery_result_as_production_authority" in s14_issue_codes:
            issue_codes.append("layer3_g7_public_projection_authority_leak")
        if "aggregate_universal_number_laundering" in s14_issue_codes:
            issue_codes.append("layer3_g7_universal_claim_without_s14_gate")
        if "gold_label_leak_into_dev_signal" in s14_issue_codes:
            issue_codes.append("layer3_g7_public_raw_payload_leak")
    if s14_battery_input_manifest is not None and s14_battery_input_manifest.issue_codes:
        issue_codes.extend(s14_battery_input_manifest.issue_codes)
    return Layer3G7S14ConsumerGate(
        status="blocked" if issue_codes or s14_issue_codes else "pass",
        missing_capability_label=missing_label,
        s14_battery_input_manifest_ref=manifest_ref,
        s14_authority_issue_codes=_dedupe(s14_issue_codes),
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_region_scorecard(
    *,
    region_ref: str,
    region_conversion_status_matrix: Layer3G7RegionConversionStatusMatrix,
    status_composition_ledger: Layer3G7StatusCompositionLedger,
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger,
    marginal_cost_ledger: Layer3G7MarginalGroundingCostLedger,
    s14_grounded_breadth_feed: Layer3G7S14GroundedBreadthFeed,
) -> Layer3G7RegionScorecard:
    """Build the G7 region scorecard as an audit summary, not authority."""

    issue_codes = _dedupe(
        (
            *region_conversion_status_matrix.issue_codes,
            *status_composition_ledger.issue_codes,
            *mechanism_reuse_ledger.issue_codes,
            *marginal_cost_ledger.issue_codes,
            *s14_grounded_breadth_feed.issue_codes,
        )
    )
    total_cases = len(region_conversion_status_matrix.records)
    grounded_count = region_conversion_status_matrix.grounded_region_case_count
    blocked_count = region_conversion_status_matrix.blocked_region_case_count
    pending_count = max(total_cases - grounded_count - blocked_count, 0)
    closure_status = _g7_scorecard_closure_status(
        conversion_status_matrix=region_conversion_status_matrix,
        status_composition_ledger=status_composition_ledger,
        mechanism_reuse_ledger=mechanism_reuse_ledger,
        marginal_cost_ledger=marginal_cost_ledger,
        s14_grounded_breadth_feed=s14_grounded_breadth_feed,
    )
    source_fingerprints = {
        "conversion_status_matrix_fingerprint": _fingerprint(
            region_conversion_status_matrix.model_dump(mode="json")
        ),
        "governed_promotion_join_fingerprint": _fingerprint(
            [
                {
                    "case_id": row.case_id,
                    "g4_promotion_record_ref": row.g4_promotion_record_ref,
                    "g4_governed_promotion_join_status": (
                        row.g4_governed_promotion_join_status
                    ),
                }
                for row in region_conversion_status_matrix.records
            ]
        ),
        "status_composition_ledger_fingerprint": _fingerprint(
            status_composition_ledger.model_dump(mode="json")
        ),
        "mechanism_reuse_ledger_fingerprint": _fingerprint(
            mechanism_reuse_ledger.model_dump(mode="json")
        ),
        "marginal_cost_ledger_fingerprint": _fingerprint(
            marginal_cost_ledger.model_dump(mode="json")
        ),
        "s14_feed_fingerprint": _fingerprint(
            s14_grounded_breadth_feed.model_dump(mode="json")
        ),
    }
    scorecard_payload = {
        "region_ref": region_ref,
        "region_envelope_posture": status_composition_ledger.region_expansion_status,
        "grounded_case_count": grounded_count,
        "blocked_case_count": blocked_count,
        "pending_case_count": pending_count,
        "g7_region_value_closure_status": closure_status,
        "mechanism_reuse_status": mechanism_reuse_ledger.reuse_status,
        "marginal_cost_status": marginal_cost_ledger.sublinear_marginal_cost_status,
        "s14_feed_status": s14_grounded_breadth_feed.status,
        "source_fingerprints": source_fingerprints,
        "issue_codes": issue_codes,
    }
    scorecard_fingerprint = _fingerprint(scorecard_payload)
    source_fingerprints["scorecard_fingerprint"] = scorecard_fingerprint
    return Layer3G7RegionScorecard(
        scorecard_id=f"layer3-g7://region-scorecard/{_slug_ref(region_ref)}",
        scorecard_ref=f"repo://architecture/policy_design_case/layer3_g7_region_scorecard.json#{_slug_ref(region_ref)}",
        region_ref=region_ref,
        status="pass" if closure_status == "pass" and not issue_codes else "blocked",
        region_envelope_posture=status_composition_ledger.region_expansion_status,
        grounded_case_count=grounded_count,
        blocked_case_count=blocked_count,
        pending_case_count=pending_count,
        g7_region_value_closure_status=closure_status,
        mechanism_reuse_status=mechanism_reuse_ledger.reuse_status,
        marginal_cost_status=marginal_cost_ledger.sublinear_marginal_cost_status,
        s14_feed_status=s14_grounded_breadth_feed.status,
        visible_limitation_refs=_dedupe(
            (
                *s14_grounded_breadth_feed.visible_limitation_refs,
                *region_conversion_status_matrix.issue_codes,
                *status_composition_ledger.issue_codes,
            )
        ),
        safe_artifact_refs=_g7_safe_artifact_refs(),
        source_fingerprints=source_fingerprints,
        scorecard_fingerprint=scorecard_fingerprint,
        issue_codes=issue_codes,
    )


def build_g7_region_widening_audit_surface(
    *,
    scorecard: Layer3G7RegionScorecard,
    s12_growth_thermometer_projection: Layer3G7S12GrowthThermometerProjection | None,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None,
    s14_consumer_gate: Layer3G7S14ConsumerGate | None,
    public_projection_overrides: Mapping[str, object] | None = None,
) -> Layer3G7RegionWideningAuditSurface:
    """Build the redacted G7 audit surface and projection contract verifications."""

    public_projection = _g7_public_projection(
        scorecard=scorecard,
        s12_growth_thermometer_projection=s12_growth_thermometer_projection,
        region_envelope_expansion_delta=region_envelope_expansion_delta,
        semantic_loss_ledger=semantic_loss_ledger,
        s14_battery_input_manifest=s14_battery_input_manifest,
        s14_consumer_gate=s14_consumer_gate,
    )
    if public_projection_overrides:
        public_projection.update(dict(public_projection_overrides))
    s12_verification = _verify_optional_projection_contract(
        "s12_resource_projection",
        public_projection,
    )
    s13_verification = _verify_optional_projection_contract(
        "s13_post_deploy_accountability_projection",
        public_projection,
    )
    s14_verification = _verify_optional_projection_contract(
        "s14_universality_projection",
        public_projection,
    )
    public_projection.update(
        _g7_projection_contract_statuses(
            s12_verification=s12_verification,
            s13_verification=s13_verification,
            s14_verification=s14_verification,
        )
    )
    public_verification = _verify_g7_public_projection_contract(
        public_projection=public_projection,
        s12_verification=s12_verification,
        s13_verification=s13_verification,
        s14_verification=s14_verification,
    )
    issue_codes = _dedupe(
        (
            *scorecard.issue_codes,
            *public_verification.get("issue_codes", ()),
        )
    )
    source_fingerprints = _g7_audit_source_fingerprints(
        scorecard=scorecard,
        public_projection=public_projection,
        s12_growth_thermometer_projection=s12_growth_thermometer_projection,
        region_envelope_expansion_delta=region_envelope_expansion_delta,
        semantic_loss_ledger=semantic_loss_ledger,
        s14_battery_input_manifest=s14_battery_input_manifest,
        s14_consumer_gate=s14_consumer_gate,
    )
    return Layer3G7RegionWideningAuditSurface(
        region_ref=scorecard.region_ref,
        status="fail" if issue_codes else "pass",
        PUBLIC=public_projection,
        REVIEWER={
            "region_scorecard_ref": scorecard.scorecard_ref,
            "blocked_case_count": scorecard.blocked_case_count,
            "visible_limitation_refs": list(scorecard.visible_limitation_refs),
            "may_not_use_for": list(G7_PUBLIC_PROJECTION_DENIED_USES),
        },
        EXPERT={
            "source_fingerprints": source_fingerprints,
            "projection_contract_statuses": _g7_projection_contract_statuses(
                s12_verification=s12_verification,
                s13_verification=s13_verification,
                s14_verification=s14_verification,
            ),
            "may_not_use_for": list(G7_PUBLIC_PROJECTION_DENIED_USES),
        },
        MACHINE={
            "schema_version": G7_SCHEMA_VERSION,
            "rule_version": G7_RULE_VERSION,
            "source_fingerprints": source_fingerprints,
            "safe_artifact_refs": list(scorecard.safe_artifact_refs),
            "may_not_use_for": list(G7_PUBLIC_PROJECTION_DENIED_USES),
        },
        s12_resource_projection_contract_verification=s12_verification,
        s13_post_deploy_accountability_projection_contract_verification=s13_verification,
        s14_universality_projection_contract_verification=s14_verification,
        public_projection_contract_verification=public_verification,
        projection_contract_statuses=_g7_projection_contract_statuses(
            s12_verification=s12_verification,
            s13_verification=s13_verification,
            s14_verification=s14_verification,
        ),
        source_fingerprints=source_fingerprints,
        issue_codes=issue_codes,
    )


def build_g7_public_export_projection_refs(
    *,
    audit_surface: Layer3G7RegionWideningAuditSurface,
) -> Layer3G7PublicExportProjectionRefs:
    """Build reference-only public export refs from the G7 audit surface."""

    return Layer3G7PublicExportProjectionRefs(
        status=audit_surface.status,
        public_export_projection_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g7_public_export_projection_refs.json#PUBLIC"
        ),
        region_ref=audit_surface.region_ref,
        PUBLIC=dict(audit_surface.PUBLIC),
        safe_artifact_refs=tuple(audit_surface.PUBLIC.get("safe_artifact_refs", ())),
        public_projection_contract_status=str(
            audit_surface.public_projection_contract_verification.get("status") or "fail"
        ),
        issue_codes=audit_surface.issue_codes,
    )


def build_g7_orchestration_continuity(
    *,
    scorecard: Layer3G7RegionScorecard,
    audit_surface: Layer3G7RegionWideningAuditSurface,
    upstream_closed_case_replay_refs: Mapping[str, Mapping[str, str]],
    upstream_closed_case_payloads: Mapping[str, Mapping[str, object]] | None = None,
) -> Layer3G7OrchestrationContinuity:
    """Build G7 orchestration continuity with closed G5/G6 refs by fingerprint."""

    normalized_refs = _normalize_g7_upstream_closed_replay_refs(
        upstream_closed_case_replay_refs
    )
    issue_codes: list[str] = []
    if set(normalized_refs) < {"g5", "g6"}:
        issue_codes.append("layer3_g7_orchestration_continuity_missing")
    if upstream_closed_case_payloads:
        issue_codes.append("layer3_g7_closed_case_replay_mutated")
    surfaces = _g7_continuity_surfaces(
        scorecard=scorecard,
        audit_surface=audit_surface,
        upstream_closed_case_replay_refs=normalized_refs,
    )
    continuity = validate_nl_replay_orchestration_continuity(
        build_nl_replay_orchestration_continuity(
            request_context=surfaces["request_context"],
            workflow_state=surfaces["workflow_state"],
            job_progress=surfaces["job_progress"],
            replay_manifest=surfaces["replay_manifest"],
            bundle_payload=surfaces["bundle"],
            quality_evidence=surfaces["quality_evidence"],
            inspection_report=surfaces["inspection"],
            readiness_payload=surfaces["readiness"],
            export_payload=surfaces["export"],
        )
    )
    if continuity.get("status") != "pass":
        issue_codes.append("layer3_g7_orchestration_continuity_missing")
    continuity["upstream_closed_case_replay_refs"] = normalized_refs
    continuity["closed_payload_mutation_status"] = (
        "blocked" if upstream_closed_case_payloads else "not_mutated"
    )
    return Layer3G7OrchestrationContinuity(
        continuity_id=f"layer3-g7://orchestration-continuity/{_slug_ref(scorecard.region_ref)}",
        region_ref=scorecard.region_ref,
        status="fail" if issue_codes else "pass",
        record=dict(continuity),
        upstream_closed_case_replay_refs=normalized_refs,
        continuity_fingerprint=str(continuity.get("continuity_fingerprint") or ""),
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_replay_manifest(
    *,
    scorecard: Layer3G7RegionScorecard,
    audit_surface: Layer3G7RegionWideningAuditSurface,
    orchestration_continuity: Layer3G7OrchestrationContinuity | None = None,
    upstream_closed_case_replay_refs: Mapping[str, Mapping[str, str]] | None = None,
) -> Layer3G7ReplayManifest:
    """Build the G7 replay manifest using the shared deterministic replay helper."""

    normalized_refs = _normalize_g7_upstream_closed_replay_refs(
        upstream_closed_case_replay_refs or {}
    )
    if orchestration_continuity is None:
        orchestration_continuity = build_g7_orchestration_continuity(
            scorecard=scorecard,
            audit_surface=audit_surface,
            upstream_closed_case_replay_refs=normalized_refs,
        )
    issue_codes: list[str] = []
    if orchestration_continuity.status != "pass":
        issue_codes.append("layer3_g7_orchestration_continuity_missing")
        issue_codes.extend(orchestration_continuity.issue_codes)
    if audit_surface.status != "pass":
        issue_codes.extend(audit_surface.issue_codes)
    replay_fingerprints = _g7_replay_fingerprints(
        scorecard=scorecard,
        audit_surface=audit_surface,
        upstream_closed_case_replay_refs=normalized_refs,
    )
    generated_paths = _g7_generated_artifact_paths()
    manifest = build_replay_manifest(
        request_payload={
            "region_ref": scorecard.region_ref,
            "scorecard_ref": scorecard.scorecard_ref,
            "surface_id": audit_surface.surface_id,
            "authority_role": "projection_only",
        },
        dependency_fingerprints=replay_fingerprints,
        data_refs={
            "dependency_artifact_refs": list(_g7_dependency_artifact_refs()),
            "generated_artifact_paths": list(generated_paths),
            "safe_artifact_refs": list(scorecard.safe_artifact_refs),
        },
        source_refs={
            "upstream_closed_case_replay_refs": normalized_refs,
            "public_export_projection_ref": (
                "repo://architecture/policy_design_case/"
                "layer3_g7_public_export_projection_refs.json#PUBLIC"
            ),
        },
        run_params={
            "schema_version": G7_SCHEMA_VERSION,
            "rule_version": G7_RULE_VERSION,
            "authority_role": "projection_only",
            "may_not_use_for": list(G7_MAY_NOT_USE_FOR),
        },
        authority_envelopes=[
            {
                "ref": scorecard.scorecard_ref,
                "authoritative_for": list(scorecard.authoritative_for),
                "may_not_use_for": list(scorecard.may_not_use_for),
            },
            {
                "ref": audit_surface.surface_id,
                "authoritative_for": list(audit_surface.authoritative_for),
                "may_not_use_for": list(audit_surface.may_not_use_for),
            },
        ],
        registry_refs={
            "surface_id": G7_SURFACE_ID,
            "generated_artifact_family_id": G7_GENERATED_ARTIFACT_FAMILY_ID,
        },
        rule_evolution_registry={
            "schema_version": G7_SCHEMA_VERSION,
            "rule_version": G7_RULE_VERSION,
        },
        orchestration_continuity=orchestration_continuity.record,
        execution_summary={
            "g7_region_value_closure_status": scorecard.g7_region_value_closure_status,
            "g7_public_projection_contract_status": (
                audit_surface.public_projection_contract_verification.get("status")
            ),
            "generated_artifact_paths": list(generated_paths),
        },
        quality_summary={
            "mechanism_reuse_status": scorecard.mechanism_reuse_status,
            "marginal_cost_status": scorecard.marginal_cost_status,
            "s14_feed_status": scorecard.s14_feed_status,
            "projection_contract_statuses": audit_surface.projection_contract_statuses,
        },
    )
    return Layer3G7ReplayManifest(
        manifest_id=f"layer3-g7://replay-manifest/{_slug_ref(scorecard.region_ref)}",
        region_ref=scorecard.region_ref,
        status="fail" if issue_codes else "pass",
        manifest=manifest,
        replay_fingerprints=replay_fingerprints,
        generated_artifact_paths=generated_paths,
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_conformance_report(
    *,
    repo_root: Path,
    dependency_readiness_snapshot: Layer3G7DependencyReadinessSnapshot | None = None,
    region_grounding_matrix: Layer3G7RegionGroundingMatrix | None = None,
    region_conversion_status_matrix: Layer3G7RegionConversionStatusMatrix | None = None,
    status_composition_ledger: Layer3G7StatusCompositionLedger | None = None,
    s12_growth_thermometer_projection: (
        Layer3G7S12GrowthThermometerProjection | None
    ) = None,
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger | None = None,
    marginal_cost_ledger: Layer3G7MarginalGroundingCostLedger | None = None,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None = None,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None = None,
    s14_grounded_breadth_feed: Layer3G7S14GroundedBreadthFeed | None = None,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None = None,
    s14_consumer_gate: Layer3G7S14ConsumerGate | None = None,
    audit_surface: Layer3G7RegionWideningAuditSurface | None = None,
    replay_manifest: Layer3G7ReplayManifest | None = None,
    orchestration_continuity: Layer3G7OrchestrationContinuity | None = None,
    registration_statuses: Mapping[str, str] | None = None,
    manifest_runtime_drift_keys: Iterable[str] = (),
    replay_helper_status: str = "pass",
    required_negative_ids: Iterable[str] | None = None,
    observed_negative_issue_codes: Mapping[str, Iterable[str]] | None = None,
) -> Layer3G7ConformanceReport:
    """Build the G7 conformance report from semantic negative probes."""

    required = tuple(required_negative_ids or REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS)
    observed_map = (
        _normalize_g7_conformance_observed_issue_codes(observed_negative_issue_codes)
        if observed_negative_issue_codes is not None
        else _g7_default_conformance_observed_issue_codes(
            repo_root=repo_root,
            dependency_readiness_snapshot=dependency_readiness_snapshot,
            region_grounding_matrix=region_grounding_matrix,
            region_conversion_status_matrix=region_conversion_status_matrix,
            status_composition_ledger=status_composition_ledger,
            s12_growth_thermometer_projection=s12_growth_thermometer_projection,
            mechanism_reuse_ledger=mechanism_reuse_ledger,
            marginal_cost_ledger=marginal_cost_ledger,
            region_envelope_expansion_delta=region_envelope_expansion_delta,
            semantic_loss_ledger=semantic_loss_ledger,
            s14_grounded_breadth_feed=s14_grounded_breadth_feed,
            s14_battery_input_manifest=s14_battery_input_manifest,
            s14_consumer_gate=s14_consumer_gate,
            audit_surface=audit_surface,
            replay_manifest=replay_manifest,
            orchestration_continuity=orchestration_continuity,
            registration_statuses=registration_statuses or {},
            manifest_runtime_drift_keys=tuple(manifest_runtime_drift_keys),
            replay_helper_status=replay_helper_status,
        )
    )
    results: list[Layer3G7ConformanceNegativeResult] = []
    missing_negative_ids: list[str] = []
    failing_negative_ids: list[str] = []
    issue_codes: list[str] = []
    for negative_id in required:
        expected_codes = G7_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES.get(negative_id)
        if not expected_codes:
            missing_negative_ids.append(str(negative_id))
            issue_codes.append(str(negative_id))
            continue
        observed_codes = _dedupe(observed_map.get(negative_id, ()))
        missing_issue_codes = tuple(
            code for code in expected_codes if code not in observed_codes
        )
        if missing_issue_codes:
            failing_negative_ids.append(negative_id)
            issue_codes.extend(missing_issue_codes)
        results.append(
            Layer3G7ConformanceNegativeResult(
                negative_id=negative_id,
                status="fail" if missing_issue_codes else "pass",
                expected_issue_codes=expected_codes,
                observed_issue_codes=observed_codes,
                missing_issue_codes=missing_issue_codes,
                probe_ref=f"layer3-g7://conformance/negative/{negative_id}",
                capability_reality_label=(
                    "semantic_test_missing" if missing_issue_codes else "implemented"
                ),
            )
        )
    status: Literal["pass", "fail"] = (
        "fail" if missing_negative_ids or failing_negative_ids else "pass"
    )
    return Layer3G7ConformanceReport(
        status=status,
        capability_reality_label=(
            "implemented" if status == "pass" else "semantic_test_missing"
        ),
        required_negative_ids=required,
        negative_results=tuple(results),
        missing_negative_ids=tuple(missing_negative_ids),
        failing_negative_ids=tuple(failing_negative_ids),
        issue_codes=_dedupe(issue_codes),
    )


def build_g7_dependency_readiness_snapshot(repo_root: Path) -> Layer3G7DependencyReadinessSnapshot:
    """Build the G7 dependency snapshot from persisted Layer 3 artifacts.

    Args:
        repo_root: Repository root containing `architecture/policy_design_case`.

    Returns:
        Strict dependency snapshot that keeps G5/G6 blockers separate from G7
        engineering readiness.
    """

    root = Path(repo_root)
    payloads = {path: _read_json(root / path) for path in G7_DEPENDENCY_PATHS}
    loaded_paths = tuple(path.as_posix() for path, payload in payloads.items() if payload)
    missing_paths = tuple(path.as_posix() for path, payload in payloads.items() if not payload)

    g1_readiness = _as_mapping(payloads[G1_READINESS_PATH])
    g1_search = _as_mapping(payloads[G1_SEARCH_RECALL_FRESHNESS_PATH]).get(
        "search_recall_freshness", {}
    )
    if not isinstance(g1_search, Mapping):
        g1_search = {}
    search_ledgers = _rows_from_payload(payloads[G1_SUBSTRATE_SEARCH_LEDGERS_PATH])
    search_authoritative_for = _dedupe(
        value for row in search_ledgers for value in _as_str_tuple(row.get("authoritative_for"))
    )
    search_may_not_use_for = _dedupe(
        value for row in search_ledgers for value in _as_str_tuple(row.get("may_not_use_for"))
    )
    g1_search_control_status = (
        "pass"
        if search_ledgers
        and not search_authoritative_for
        and "search_hit_as_authority" in search_may_not_use_for
        else ("missing" if not search_ledgers else "fail")
    )

    g4_readiness = _as_mapping(payloads[G4_READINESS_PATH])
    g4_promotion_payload = _as_mapping(payloads[G4_PROMOTION_RECORDS_PATH])
    g4_records = _as_mapping_rows(g4_promotion_payload.get("promotion_records"))
    g4_throughput = _as_mapping(payloads[G4_GOVERNANCE_THROUGHPUT_DELTA_PATH])

    g5_readiness = _as_mapping(payloads[G5_READINESS_PATH])
    g5_records = _as_mapping_rows(
        _as_mapping(payloads[G5_CONVERSION_RECORDS_PATH]).get("conversion_records")
    )
    g5_record = g5_records[0] if g5_records else {}
    g5_may_not_use_for = _as_str_tuple(g5_record.get("may_not_use_for"))
    g5_conversion_outcome = _optional_str(
        g5_record.get("conversion_outcome") or g5_readiness.get("g5_conversion_outcome")
    )
    g5_grounding_disposition = _optional_str(g5_record.get("grounding_disposition"))
    g5_grounded_seed_count = sum(
        1
        for row in g5_records
        if row.get("case_id") == "ua-msme-affordable-loans-2022"
        and row.get("grounding_disposition") in {"grounded_limited", "grounded_abstention"}
        and row.get("conversion_outcome") != "unchanged_blocker"
    )

    g6_readiness = _as_mapping(payloads[G6_READINESS_PATH])
    g6_result = _as_mapping(payloads[G6_GROUNDED_RESULT_OR_ABSTENTION_PATH])
    g6_records = _as_mapping_rows(
        _as_mapping(payloads[G6_AGENT_RUN_RECORDS_PATH]).get("agent_run_records")
    )
    g6_record = g6_records[0] if g6_records else {}
    g6_invocation = _as_mapping(payloads[G6_G5_INVOCATION_PLAN_PATH])
    g6_may_not_use_for = _as_str_tuple(
        g6_result.get("may_not_use_for") or g6_record.get("may_not_use_for")
    )

    region_value_status = _g7_region_value_closure_status(
        g5_conversion_outcome=g5_conversion_outcome,
        g5_grounded_region_seed_count=g5_grounded_seed_count,
    )
    issue_codes = _snapshot_issue_codes(
        g5_readiness_status=_manifest_status(g5_readiness),
        g6_readiness_status=_manifest_status(g6_readiness),
        region_value_closure_status=region_value_status,
        missing_paths=missing_paths,
    )
    engineering_status = _engineering_readiness_status(
        missing_paths=missing_paths,
        g1_status=_readiness_presence_status(g1_readiness),
        g4_status=str(
            g4_readiness.get("g4_g5_promotion_handoff_status")
            or _manifest_status(g4_readiness)
        ),
        g5_status=_manifest_status(g5_readiness),
        g6_status=_manifest_status(g6_readiness),
        s14_status=_readiness_presence_status(
            _as_mapping(payloads[S14_ASSURANCE_MANIFEST_PATH])
        ),
        s14_helper_status=_s14_helper_availability_status(),
    )

    return Layer3G7DependencyReadinessSnapshot(
        engineering_readiness_status=engineering_status,
        region_value_closure_status=region_value_status,
        g1_readiness_status=_readiness_presence_status(g1_readiness),
        g1_search_recall_status=_search_status(g1_search, "search_recall_status"),
        g1_index_freshness_status=_search_status(g1_search, "index_freshness_status"),
        g1_substrate_search_control_plane_status=g1_search_control_status,
        g1_substrate_search_ledger_count=len(search_ledgers),
        g1_substrate_search_authoritative_for=search_authoritative_for,
        g1_substrate_search_may_not_use_for=search_may_not_use_for,
        g4_readiness_status=_manifest_status(g4_readiness),
        g4_promotion_record_count=len(g4_records),
        g4_governed_promoted_count=sum(
            1 for row in g4_records if row.get("promotion_state") == "governed_promoted"
        ),
        g4_promotion_blocked_count=sum(
            1 for row in g4_records if row.get("promotion_state") != "governed_promoted"
        ),
        g4_governance_throughput_status=_status_value(g4_throughput),
        g5_readiness_status=_manifest_status(g5_readiness),
        g5_conversion_outcome=g5_conversion_outcome,
        g5_grounding_disposition=g5_grounding_disposition,
        g5_grounded_region_seed_count=g5_grounded_seed_count,
        g5_conversion_record_count=len(g5_records),
        g5_w12d_consumer_gate_status=_status_value(
            _as_mapping(payloads[G5_W12D_CONSUMER_GATE_PATH])
        ),
        g5_envelope_expansion_status=_status_value(
            _as_mapping(payloads[G5_ENVELOPE_EXPANSION_DELTA_PATH])
        ),
        g5_status_composition_status=_status_value(
            _as_mapping(payloads[G5_STATUS_COMPOSITION_LEDGER_PATH])
        ),
        g5_demand_pull_attempt_status=_status_value(
            _as_mapping(payloads[G5_DEMAND_PULL_ATTEMPT_RECORD_PATH])
        ),
        g5_dependency_health_metric_snapshot_status=_status_value(
            _as_mapping(payloads[G5_DEPENDENCY_HEALTH_METRIC_SNAPSHOT_PATH])
        ),
        g5_may_not_use_for=g5_may_not_use_for,
        g6_readiness_status=_manifest_status(g6_readiness),
        g6_engineering_readiness_status=str(
            g6_readiness.get("g6_engineering_readiness_status")
            or _as_mapping(g6_readiness.get("summary")).get("g6_engineering_readiness_status")
            or "missing"
        ),
        g6_grounded_value_closure_status=str(
            g6_readiness.get("g6_grounded_value_closure_status")
            or _as_mapping(g6_readiness.get("summary")).get("g6_grounded_value_closure_status")
            or g6_record.get("grounded_value_closure_status")
            or "missing"
        ),
        g6_result_outcome=_optional_str(g6_result.get("outcome") or g6_record.get("outcome")),
        g6_grounding_disposition=_optional_str(
            g6_result.get("grounding_disposition") or g6_record.get("grounding_disposition")
        ),
        g6_g5_conversion_outcome=_optional_str(
            g6_result.get("g5_conversion_outcome")
            or g6_invocation.get("g5_conversion_outcome")
            or g6_record.get("g5_conversion_outcome")
        ),
        g6_search_ledger_status=_status_value(_as_mapping(payloads[G6_SEARCH_LEDGER_PATH])),
        g6_agent_run_record_count=len(g6_records),
        g6_g5_invocation_plan_status=_status_value(g6_invocation),
        g6_demand_pull_vs_abstention_status=_status_value(
            _as_mapping(payloads[G6_DEMAND_PULL_VS_ABSTENTION_DELTA_PATH])
        ),
        g6_orchestration_continuity_status=_status_value(
            _as_mapping(payloads[G6_ORCHESTRATION_CONTINUITY_PATH])
        ),
        g6_replay_manifest_status=_status_value(
            _as_mapping(payloads[G6_REPLAY_MANIFEST_PATH])
        ),
        g6_may_not_use_for=g6_may_not_use_for,
        s14_assurance_manifest_status=_readiness_presence_status(
            _as_mapping(payloads[S14_ASSURANCE_MANIFEST_PATH])
        ),
        s14_helper_availability_status=_s14_helper_availability_status(),
        loaded_artifact_paths=loaded_paths,
        missing_artifact_paths=missing_paths,
        issue_codes=issue_codes,
    )


def build_layer3_g7_bundle(repo_root: Path) -> Layer3G7Bundle:
    """Build the G7 bundle around dependency readiness and conversion status."""

    snapshot = build_g7_dependency_readiness_snapshot(repo_root)
    region_ref = "region://ua/msme-adjacent"
    conversion_records = build_g7_region_conversion_records(
        region_ref=region_ref,
        conversion_inputs=_current_g7_conversion_inputs(repo_root=repo_root),
    )
    conversion_status_matrix = build_g7_region_conversion_status_matrix(
        region_ref=region_ref,
        records=conversion_records,
    )
    return Layer3G7Bundle(
        dependency_readiness_snapshot=snapshot,
        region_value_closure_status=snapshot.region_value_closure_status,
        region_conversion_status_matrix=conversion_status_matrix,
        region_grounded_case_count=conversion_status_matrix.grounded_region_case_count,
    )


def validate_layer3_g7_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G7Bundle,
) -> Layer3G7ValidationReport:
    """Validate the Task 2 G7 dependency bundle and overclaim blockers."""

    del repo_root
    bundle = (
        persisted
        if isinstance(persisted, Layer3G7Bundle)
        else Layer3G7Bundle.model_validate(persisted)
    )
    snapshot = bundle.dependency_readiness_snapshot
    issues: list[Layer3G7ValidationIssue] = []
    if snapshot.g5_readiness_status != "pass":
        issues.append(
            _issue(
                "layer3_g7_g5_readiness_missing",
                "$.dependency_readiness_snapshot.g5_readiness_status",
                "G7 requires G5 readiness to exist and pass before dependency use.",
            )
        )
    if snapshot.g6_readiness_status != "pass":
        issues.append(
            _issue(
                "layer3_g7_g6_readiness_missing",
                "$.dependency_readiness_snapshot.g6_readiness_status",
                "G7 requires G6 readiness to exist and pass before dependency use.",
            )
        )
    if (
        snapshot.g5_conversion_outcome == "unchanged_blocker"
        and bundle.region_grounded_case_count > 0
    ):
        issues.append(
            _issue(
                "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
                "$.region_grounded_case_count",
                "The current G5 unchanged blocker cannot count as region grounded breadth.",
            )
        )
    if (
        snapshot.g6_g5_conversion_outcome == "unchanged_blocker"
        and bundle.g6_region_conversion_count > 0
    ):
        issues.append(
            _issue(
                "layer3_g7_g6_candidate_counted_as_grounded",
                "$.g6_region_conversion_count",
                "G6 diagnostic output cannot count as G7 region conversion authority.",
            )
        )
    if bundle.seed_g4_promotion_projected_to_region:
        issues.append(
            _issue(
                "layer3_g7_g4_seed_promotion_projected_to_region",
                "$.seed_g4_promotion_projected_to_region",
                "A seed-case G4 promotion cannot be copied onto adjacent region cases.",
            )
        )
    if "g7_region_widening" not in snapshot.g5_may_not_use_for:
        issues.append(
            _issue(
                "layer3_g7_g5_may_not_use_for_ignored",
                "$.dependency_readiness_snapshot.g5_may_not_use_for",
                "G7 must preserve the upstream G5 region-widening denial.",
            )
        )
    if "g7_region_widening" not in snapshot.g6_may_not_use_for:
        issues.append(
            _issue(
                "layer3_g7_g6_may_not_use_for_ignored",
                "$.dependency_readiness_snapshot.g6_may_not_use_for",
                "G7 must preserve the upstream G6 region-widening denial.",
            )
        )
    if bundle.status_composition_claim == "pass" and (
        snapshot.region_value_closure_status != "pass"
        or bundle.per_case_grounding_status.startswith("blocked")
        or bundle.s14_feed_status.startswith("blocked")
        or bundle.semantic_loss_status.startswith("blocked")
        or bundle.marginal_cost_status.startswith("blocked")
    ):
        issues.append(
            _issue(
                "layer3_g7_status_composition_missing",
                "$.status_composition_claim",
                "G7 status composition cannot claim pass over blocked dependency state.",
            )
        )
    if bundle.closed_replay_mutation_detected:
        issues.append(
            _issue(
                "layer3_g7_closed_case_replay_mutated",
                "$.closed_replay_mutation_detected",
                "G7 must reference closed G5/G6 replay payloads, not mutate them.",
            )
        )
    return Layer3G7ValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary={
            "g7_engineering_readiness_status": snapshot.engineering_readiness_status,
            "g7_region_value_closure_status": snapshot.region_value_closure_status,
            "g7_current_g5_conversion_outcome": snapshot.g5_conversion_outcome,
            "g7_region_grounded_case_count": bundle.region_grounded_case_count,
            "issue_codes": tuple(issue.code for issue in issues),
        },
    )


def _g7_scorecard_closure_status(
    *,
    conversion_status_matrix: Layer3G7RegionConversionStatusMatrix,
    status_composition_ledger: Layer3G7StatusCompositionLedger,
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger,
    marginal_cost_ledger: Layer3G7MarginalGroundingCostLedger,
    s14_grounded_breadth_feed: Layer3G7S14GroundedBreadthFeed,
) -> Layer3G7RegionValueClosureStatus:
    if conversion_status_matrix.status != "pass":
        return "blocked_by_no_real_grounded_region_breadth"
    if mechanism_reuse_ledger.reuse_status == "blocked_by_bespoke_patch":
        return "blocked_by_bespoke_reuse"
    if marginal_cost_ledger.sublinear_marginal_cost_status.startswith("blocked"):
        return "blocked_by_bespoke_reuse"
    if s14_grounded_breadth_feed.status != "pass":
        return "blocked_by_s14_feed"
    if status_composition_ledger.status != "pass":
        return "fail"
    return "pass"


def _g7_public_projection(
    *,
    scorecard: Layer3G7RegionScorecard,
    s12_growth_thermometer_projection: Layer3G7S12GrowthThermometerProjection | None,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None,
    s14_consumer_gate: Layer3G7S14ConsumerGate | None,
) -> dict[str, Any]:
    denied_uses = list(G7_PUBLIC_PROJECTION_DENIED_USES)
    payload: dict[str, Any] = {
        "surface_id": G7_SURFACE_ID,
        "region_ref": scorecard.region_ref,
        "region_envelope_posture": scorecard.region_envelope_posture,
        "grounded_case_count": scorecard.grounded_case_count,
        "blocked_case_count": scorecard.blocked_case_count,
        "pending_case_count": scorecard.pending_case_count,
        "g7_region_value_closure_status": scorecard.g7_region_value_closure_status,
        "mechanism_reuse_status": scorecard.mechanism_reuse_status,
        "marginal_cost_status": scorecard.marginal_cost_status,
        "s14_feed_status": scorecard.s14_feed_status,
        "visible_limitations": list(scorecard.visible_limitation_refs),
        "denied_uses": denied_uses,
        "authority_role": "projection_only",
        "projection_policy": "reads_policy_design_case_only",
        "authoritative_for": [],
        "may_be_used_for": list(G7_PUBLIC_OFFICIAL_USE_LIMITS),
        "may_not_be_used_for": denied_uses,
        "official_use_limited_to": list(G7_PUBLIC_OFFICIAL_USE_LIMITS),
        "safe_artifact_refs": list(scorecard.safe_artifact_refs),
        "redacted": True,
        "redaction_summary": {
            "raw_prompts": "redacted",
            "hidden_s14_cases": "redacted",
            "raw_evidence_payloads": "redacted",
            "recommendation_text": "not_projected",
            "legal_advice": "not_projected",
        },
        "authority_boundary": {
            "authority_role": "projection_only",
            "authoritative_for": [],
            "may_not_use_for": denied_uses,
        },
    }
    if s12_growth_thermometer_projection is not None:
        payload.update(
            {
                "s12_resource_posture_ref": (
                    s12_growth_thermometer_projection.thermometer_ref
                ),
                "resource_allocation_policy_ref": (
                    s12_growth_thermometer_projection.thermometer_ref
                ),
                "explore_exploit_posture": "blocked",
                "growth_thermometer_ref": (
                    s12_growth_thermometer_projection.thermometer_ref
                ),
                "reuse_rate_trend": "projection_only",
                "override_rate_trend": "not_applicable",
                "s12_public_growth_limitation": (
                    "Region widening is an audit projection; it cannot allocate "
                    "resources or claim budget interchangeability."
                ),
                "growth_without_envelope_delta_count": (
                    s12_growth_thermometer_projection.growth_without_envelope_delta_count
                ),
                "growth_counting_disposition": (
                    s12_growth_thermometer_projection.growth_counting_disposition
                ),
            }
        )
    if region_envelope_expansion_delta is not None:
        payload.update(
            {
                "accountability_posture_ref": (
                    region_envelope_expansion_delta.assurance_case_delta_ref
                    or region_envelope_expansion_delta.delta_id
                ),
                "public_accountability_note_ref": (
                    f"{region_envelope_expansion_delta.delta_id}#public-note"
                ),
                "public_accountability_note": (
                    "Envelope expansion remains projection-only until S13/G7 replay "
                    "and accountability surfaces stay closed."
                ),
                "envelope_revision_ref": region_envelope_expansion_delta.delta_id,
                "certified_envelope_delta_ref": (
                    region_envelope_expansion_delta.certified_envelope_delta_refs[0]
                    if region_envelope_expansion_delta.certified_envelope_delta_refs
                    else ""
                ),
                "assurance_case_delta_ref": (
                    region_envelope_expansion_delta.assurance_case_delta_ref or ""
                ),
                "envelope_revision_direction": (
                    region_envelope_expansion_delta.envelope_revision_direction
                ),
            }
        )
    if s14_battery_input_manifest is not None:
        payload.update(
            {
                "s14_universality_assurance_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer2_s14_universality_assurance_manifest.json"
                ),
                "universality_claim_gate_ref": (
                    s14_consumer_gate.s14_battery_input_manifest_ref
                    if s14_consumer_gate is not None
                    and s14_consumer_gate.s14_battery_input_manifest_ref
                    else s14_battery_input_manifest.s14_battery_input_manifest_id
                ),
                "universality_claim_disposition": "projection_limited",
                "declared_operation_envelope_ref": (
                    f"envelope://g7/{_slug_ref(scorecard.region_ref)}"
                ),
                "d4_corpus_track_coverage_ref": (
                    s14_battery_input_manifest.grounded_breadth_feed_ref
                ),
                "d4_corpus_track_coverage_status": "g7_grounded_breadth_input_only",
                "expert_oracle_bootstrap_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer2_s14_universality_assurance_manifest.json#expert-oracle"
                ),
                "breadth_floor_config_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer2_s14_universality_assurance_manifest.json#breadth-floor"
                ),
                "breadth_floor_status": "external_s14_owned",
                "universality_baseline_comparison_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer2_s14_universality_assurance_manifest.json#baseline"
                ),
                "baseline_comparison_status": "external_s14_owned",
                "grounded_authority_coverage_ref": (
                    s14_battery_input_manifest.grounded_authority_coverage_ref
                ),
                "grounded_authority_status": "g7_feed_projection_only",
                "evaluation_status_composition_ref": scorecard.scorecard_ref,
                "status_composition_limit_refs": list(scorecard.visible_limitation_refs),
                "axis_scorecard_ref": scorecard.scorecard_ref,
                "sealed_battery_run_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer2_s14_universality_assurance_manifest.json#sealed-run"
                ),
                "sealed_battery_integrity_status": (
                    s14_battery_input_manifest.sealed_battery_mutation_status
                ),
                "mechanism_generality_report_ref": (
                    s14_battery_input_manifest.mechanism_generality_projection_ref
                ),
                "mechanism_generality_status": (
                    "blocked"
                    if s14_battery_input_manifest.issue_codes
                    else "projection_ready"
                ),
                "sublinear_marginal_bespoke_cost_status": (
                    scorecard.marginal_cost_status
                ),
                "s9_projection_faithfulness_refs": (
                    "s9-faithfulness://layer3-g7/public-projection",
                ),
                "public_universality_limitation": (
                    "G7 supplies bounded grounded breadth to S14; it cannot publish "
                    "universal authority or an aggregate universal score."
                ),
            }
        )
    if semantic_loss_ledger is not None:
        payload["semantic_loss_status"] = semantic_loss_ledger.semantic_loss_status
    return payload


def _verify_optional_projection_contract(
    contract_name: str,
    public_projection: Mapping[str, Any],
) -> dict[str, Any]:
    if contract_name == "s12_resource_projection":
        if not (
            public_projection.get("s12_resource_posture_ref")
            or public_projection.get("resource_allocation_policy_ref")
            or public_projection.get("explore_exploit_posture")
        ):
            return _not_applicable_projection_contract(contract_name)
        return verify_s12_resource_projection_consumer_contract(
            projections={"public": public_projection}
        )
    if contract_name == "s13_post_deploy_accountability_projection":
        if not (
            public_projection.get("accountability_posture_ref")
            or public_projection.get("public_accountability_note_ref")
            or public_projection.get("envelope_revision_ref")
        ):
            return _not_applicable_projection_contract(contract_name)
        return verify_s13_post_deploy_accountability_projection_consumer_contract(
            projections={"public": public_projection}
        )
    if contract_name == "s14_universality_projection":
        if not (
            public_projection.get("s14_universality_assurance_ref")
            or public_projection.get("universality_claim_gate_ref")
            or public_projection.get("axis_scorecard_ref")
        ):
            return _not_applicable_projection_contract(contract_name)
        return verify_s14_universality_projection_consumer_contract(
            projections={"public": public_projection}
        )
    return _not_applicable_projection_contract(contract_name)


def _not_applicable_projection_contract(contract_name: str) -> dict[str, Any]:
    return {
        "schema_version": f"policyos.runtime.policy_design_case.{contract_name}.v1",
        "status": "not_applicable_no_payload",
        "consumer_contract_ref": contract_name,
        "issue_codes": [],
        "issues": [],
    }


def _verify_g7_public_projection_contract(
    *,
    public_projection: Mapping[str, Any],
    s12_verification: Mapping[str, Any],
    s13_verification: Mapping[str, Any],
    s14_verification: Mapping[str, Any],
) -> dict[str, Any]:
    issue_codes: list[str] = []
    try:
        checked_projection = assert_policy_design_projection_not_authority(
            _g7_policy_design_projection_contract_payload(public_projection)
        )
    except PolicyDesignCaseProjectionError as exc:
        checked_projection = {}
        issue_codes.append("layer3_g7_public_projection_contract_failed")
        if "authority" in exc.code:
            issue_codes.append("layer3_g7_public_projection_authority_leak")
    observed_denied = set(_public_denied_uses(public_projection))
    if not observed_denied >= G7_PUBLIC_REQUIRED_DENIED_USES:
        issue_codes.append("layer3_g7_projection_omits_required_deny_list")
    official_uses = set(_as_str_tuple(public_projection.get("official_use_limited_to")))
    if not official_uses >= set(G7_PUBLIC_OFFICIAL_USE_LIMITS):
        issue_codes.append("layer3_g7_public_projection_contract_failed")
    if str(public_projection.get("authority_role") or "") != "projection_only":
        issue_codes.append("layer3_g7_public_projection_authority_leak")
    if _as_str_tuple(public_projection.get("authoritative_for")):
        issue_codes.append("layer3_g7_public_projection_authority_leak")
    if _g7_public_projection_contains_forbidden_payload(public_projection):
        issue_codes.append("layer3_g7_public_raw_payload_leak")
    if public_projection.get("aggregate_universal_score") is not None:
        issue_codes.append("layer3_g7_universal_claim_without_s14_gate")
    for verification in (s12_verification, s13_verification, s14_verification):
        if verification.get("status") == "fail":
            issue_codes.append("layer3_g7_public_projection_contract_failed")
        if verification.get("status") in {None, ""}:
            issue_codes.append("layer3_g7_public_projection_contract_failed")
    return {
        "status": "fail" if issue_codes else "pass",
        "projection_contract_ref": "layer3-g7://public-projection-contract",
        "checked_schema_version": checked_projection.get("schema_version"),
        "required_denied_uses": sorted(G7_PUBLIC_REQUIRED_DENIED_USES),
        "observed_denied_uses": sorted(observed_denied),
        "issue_codes": list(_dedupe(issue_codes)),
    }


def _g7_policy_design_projection_contract_payload(
    public_projection: Mapping[str, Any],
) -> dict[str, Any]:
    can_closeout = public_projection.get("g7_region_value_closure_status") == "pass"
    blocker_codes = (
        ()
        if can_closeout
        else ("layer3_g7_public_projection_exposes_blocked_region_state",)
    )
    return {
        "generated_at": datetime.now(UTC),
        "surface": G7_SURFACE_ID,
        "audience": "public",
        "policy_design_case_id": "layer3-g7-region-widening",
        "run_id": _optional_str(public_projection.get("region_ref")),
        "source_ref": _optional_str(public_projection.get("region_ref")),
        "source_ref_fingerprint": _fingerprint(public_projection.get("region_ref")),
        "primary_state": "projection_only" if can_closeout else "blocked",
        "states": ("projection_only",) if can_closeout else ("projection_only", "blocked"),
        "labels": (
            {
                "state": "projection_only",
                "label": "projection only",
                "authority_role": _optional_str(public_projection.get("authority_role"))
                or "projection_only",
                "source_authority": "layer3_g7_region_widening_audit",
            },
        ),
        "closeout_truth": {
            "status": "pass" if can_closeout else "blocked",
            "verdict": "projection_only" if can_closeout else "cannot_closeout",
            "can_closeout": can_closeout,
            "blocker_codes": blocker_codes,
            "omission_codes": (),
            "contested_state": "not_contested",
        },
        "authority_role": public_projection.get("authority_role") or "projection_only",
        "projection_policy": public_projection.get("projection_policy")
        or "reads_policy_design_case_only",
        "authoritative_for": tuple(_as_str_tuple(public_projection.get("authoritative_for"))),
        "evidence_class": "runtime_region_widening_projection",
        "redacted": True,
        "redaction_summary": dict(_as_mapping(public_projection.get("redaction_summary"))),
        "audit_refs": tuple(_as_str_tuple(public_projection.get("safe_artifact_refs"))),
        "source_state": {
            "region_ref": public_projection.get("region_ref"),
            "region_envelope_posture": public_projection.get("region_envelope_posture"),
            "g7_region_value_closure_status": public_projection.get(
                "g7_region_value_closure_status"
            ),
        },
        "may_be_used_for": tuple(_as_str_tuple(public_projection.get("may_be_used_for"))),
        "may_not_be_used_for": tuple(_public_denied_uses(public_projection)),
        "capability_reality_state": "implemented_but_not_orchestrated",
        "contract_verification_status": "not_verified",
        "contract_verification_refs": ("layer3-g7://public-projection-contract",),
    }


def _public_denied_uses(public_projection: Mapping[str, Any]) -> tuple[str, ...]:
    return _dedupe(
        (
            *_as_str_tuple(public_projection.get("may_not_be_used_for")),
            *_as_str_tuple(public_projection.get("may_not_use_for")),
        )
    )


def _g7_projection_contract_statuses(
    *,
    s12_verification: Mapping[str, Any],
    s13_verification: Mapping[str, Any],
    s14_verification: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "s12_resource_projection_contract_status": str(
            s12_verification.get("status") or "fail"
        ),
        "s13_post_deploy_accountability_projection_contract_status": str(
            s13_verification.get("status") or "fail"
        ),
        "s14_universality_projection_contract_status": str(
            s14_verification.get("status") or "fail"
        ),
    }


def _g7_public_projection_contains_forbidden_payload(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).casefold().replace("-", "_")
            if key_text in {
                "authority_boundary",
                "denied_uses",
                "may_not_be_used_for",
                "may_not_use_for",
                "official_use_limited_to",
                "redaction_summary",
            }:
                continue
            if key_text in {
                "approval",
                "hidden_s14_case_ids",
                "hidden_case_payload",
                "legal_advice",
                "production_recommendation",
                "raw_case_payload",
                "raw_evidence_payload",
                "raw_prompt",
                "recommendation_text",
                "rollout_recommendation",
                "runtime_closeout",
                "universal_claim_allowed_language",
            }:
                return True
            if _g7_public_projection_contains_forbidden_payload(nested):
                return True
    elif isinstance(value, Iterable) and not isinstance(value, str | bytes | bytearray):
        return any(_g7_public_projection_contains_forbidden_payload(item) for item in value)
    elif isinstance(value, str):
        lowered = value.casefold().replace("-", "_")
        return any(
            token in lowered
            for token in (
                "hidden_case_payload",
                "raw_evidence_payload",
                "raw_prompt",
                "legal_advice",
                "recommendation_text",
                "universal_claim_allowed_language",
            )
        )
    return False


def _g7_audit_source_fingerprints(
    *,
    scorecard: Layer3G7RegionScorecard,
    public_projection: Mapping[str, Any],
    s12_growth_thermometer_projection: Layer3G7S12GrowthThermometerProjection | None,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None,
    s14_consumer_gate: Layer3G7S14ConsumerGate | None,
) -> dict[str, str]:
    fingerprints = dict(scorecard.source_fingerprints)
    fingerprints.setdefault(
        "region_candidate_set_fingerprint",
        _fingerprint({"not_written": "region_candidate_set"}),
    )
    fingerprints.setdefault(
        "grounding_matrix_fingerprint",
        _fingerprint({"not_written": "grounding_matrix"}),
    )
    optional_payloads = {
        "s12_growth_thermometer_projection_fingerprint": (
            s12_growth_thermometer_projection
        ),
        "region_envelope_expansion_delta_fingerprint": region_envelope_expansion_delta,
        "semantic_loss_ledger_fingerprint": semantic_loss_ledger,
        "s14_battery_input_manifest_fingerprint": s14_battery_input_manifest,
        "s14_consumer_gate_fingerprint": s14_consumer_gate,
    }
    for key, payload in optional_payloads.items():
        fingerprints[key] = _fingerprint(
            payload.model_dump(mode="json")
            if isinstance(payload, _G7Model)
            else {"not_written": key}
        )
    fingerprints["public_projection_fingerprint"] = _fingerprint(dict(public_projection))
    return fingerprints


def _normalize_g7_upstream_closed_replay_refs(
    upstream_closed_case_replay_refs: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for key, value in upstream_closed_case_replay_refs.items():
        ref = _optional_str(value.get("ref"))
        fingerprint = _optional_str(value.get("fingerprint"))
        if ref and fingerprint:
            normalized[str(key)] = {"ref": ref, "fingerprint": fingerprint}
    return normalized


def _g7_continuity_surfaces(
    *,
    scorecard: Layer3G7RegionScorecard,
    audit_surface: Layer3G7RegionWideningAuditSurface,
    upstream_closed_case_replay_refs: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, Any]]:
    refs = _g7_runtime_quality_refs(scorecard.region_ref)
    upstream_refs = {
        key: dict(value) for key, value in upstream_closed_case_replay_refs.items()
    }
    common = {
        "runtime_quality_refs": refs,
        "region_ref": scorecard.region_ref,
        "scorecard_ref": scorecard.scorecard_ref,
        "public_projection_ref": (
            "repo://architecture/policy_design_case/"
            "layer3_g7_public_export_projection_refs.json#PUBLIC"
        ),
        "upstream_closed_case_replay_refs": upstream_refs,
    }
    return {
        "request_context": {
            **common,
            "request_ref": f"layer3-g7://region-request/{_slug_ref(scorecard.region_ref)}",
        },
        "workflow_state": {
            **common,
            "workflow_ref": f"layer3-g7://workflow/{_slug_ref(scorecard.region_ref)}",
        },
        "job_progress": {
            **common,
            "job_ref": f"layer3-g7://job/{_slug_ref(scorecard.region_ref)}",
        },
        "replay_manifest": {
            **common,
            "replay_fingerprint_inputs": audit_surface.source_fingerprints,
        },
        "bundle": {
            **common,
            "g7_region_value_closure_status": scorecard.g7_region_value_closure_status,
        },
        "quality_evidence": {
            **common,
            "component_id": "runtime_orchestration_continuity",
            "evidence_refs": list(scorecard.safe_artifact_refs),
        },
        "inspection": {
            **common,
            "projection_contract_statuses": audit_surface.projection_contract_statuses,
        },
        "readiness": {
            **common,
            "public_projection_contract_status": (
                audit_surface.public_projection_contract_verification.get("status")
            ),
        },
        "export": {
            **common,
            "safe_artifact_refs": list(scorecard.safe_artifact_refs),
        },
    }


def _g7_runtime_quality_refs(region_ref: str) -> dict[str, Any]:
    slug = _slug_ref(region_ref)
    return {
        "carrier_ref": f"evidence-spine://layer3-g7/{slug}",
        "concept_spine_ref": "concept-spine://policy-design-case/layer3-g7-region",
        "jurisdiction_spine_ref": f"jurisdiction-spine://{slug}",
        "producer_handshake_ledger_ref": (
            "producer-handshake-ledger://layer3-g7/region-widening"
        ),
        "runtime_claim_registry_ref": (
            "runtime-claim-registry://layer3-g7/region-widening"
        ),
        "selected_binding_refs": [
            "producer-binding://layer3-g7/region-conversion",
            "producer-binding://layer3-g7/s14-grounded-breadth-feed",
        ],
    }


def _g7_replay_fingerprints(
    *,
    scorecard: Layer3G7RegionScorecard,
    audit_surface: Layer3G7RegionWideningAuditSurface,
    upstream_closed_case_replay_refs: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    fingerprints = dict(audit_surface.source_fingerprints)
    for key in (
        "region_candidate_set_fingerprint",
        "grounding_matrix_fingerprint",
        "conversion_status_matrix_fingerprint",
        "governed_promotion_join_fingerprint",
        "status_composition_ledger_fingerprint",
        "s12_growth_thermometer_projection_fingerprint",
        "mechanism_reuse_ledger_fingerprint",
        "marginal_cost_ledger_fingerprint",
        "s14_feed_fingerprint",
        "s14_battery_input_manifest_fingerprint",
        "s14_consumer_gate_fingerprint",
        "scorecard_fingerprint",
        "public_projection_fingerprint",
    ):
        fingerprints.setdefault(key, _fingerprint({"missing": key}))
    fingerprints["scorecard_fingerprint"] = scorecard.scorecard_fingerprint
    fingerprints["upstream_closed_g5_replay_fingerprint"] = str(
        _as_mapping(upstream_closed_case_replay_refs.get("g5")).get("fingerprint")
        or _fingerprint({"missing": "g5_replay"})
    )
    fingerprints["upstream_closed_g6_replay_fingerprint"] = str(
        _as_mapping(upstream_closed_case_replay_refs.get("g6")).get("fingerprint")
        or _fingerprint({"missing": "g6_replay"})
    )
    return fingerprints


def _g7_safe_artifact_refs() -> tuple[str, ...]:
    return (
        "repo://architecture/policy_design_case/layer3_g7_region_scorecard.json",
        "repo://architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json",
        "repo://architecture/policy_design_case/layer3_g7_public_export_projection_refs.json",
        "repo://architecture/policy_design_case/layer3_g7_replay_manifest.json",
    )


def _g7_dependency_artifact_refs() -> tuple[str, ...]:
    return tuple(f"repo://{path.as_posix()}" for path in G7_DEPENDENCY_PATHS)


def _g7_generated_artifact_paths() -> tuple[str, ...]:
    return (
        "architecture/policy_design_case/layer3_g7_region_scorecard.json",
        "architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json",
        "architecture/policy_design_case/layer3_g7_public_export_projection_refs.json",
        "architecture/policy_design_case/layer3_g7_orchestration_continuity.json",
        "architecture/policy_design_case/layer3_g7_replay_manifest.json",
    )


def _normalize_g7_conformance_observed_issue_codes(
    observed_negative_issue_codes: Mapping[str, Iterable[str]] | None,
) -> dict[str, tuple[str, ...]]:
    if observed_negative_issue_codes is None:
        return {}
    return {
        str(negative_id): _dedupe(str(code) for code in issue_codes)
        for negative_id, issue_codes in observed_negative_issue_codes.items()
    }


def _g7_default_conformance_observed_issue_codes(
    *,
    repo_root: Path,
    dependency_readiness_snapshot: Layer3G7DependencyReadinessSnapshot | None,
    region_grounding_matrix: Layer3G7RegionGroundingMatrix | None,
    region_conversion_status_matrix: Layer3G7RegionConversionStatusMatrix | None,
    status_composition_ledger: Layer3G7StatusCompositionLedger | None,
    s12_growth_thermometer_projection: Layer3G7S12GrowthThermometerProjection | None,
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger | None,
    marginal_cost_ledger: Layer3G7MarginalGroundingCostLedger | None,
    region_envelope_expansion_delta: Layer3G7RegionEnvelopeExpansionDelta | None,
    semantic_loss_ledger: Layer3G7RegionSemanticLossLedger | None,
    s14_grounded_breadth_feed: Layer3G7S14GroundedBreadthFeed | None,
    s14_battery_input_manifest: Layer3G7S14BatteryInputManifest | None,
    s14_consumer_gate: Layer3G7S14ConsumerGate | None,
    audit_surface: Layer3G7RegionWideningAuditSurface | None,
    replay_manifest: Layer3G7ReplayManifest | None,
    orchestration_continuity: Layer3G7OrchestrationContinuity | None,
    registration_statuses: Mapping[str, str],
    manifest_runtime_drift_keys: tuple[str, ...],
    replay_helper_status: str,
) -> dict[str, tuple[str, ...]]:
    del (
        region_grounding_matrix,
        region_conversion_status_matrix,
        status_composition_ledger,
        s12_growth_thermometer_projection,
        mechanism_reuse_ledger,
        marginal_cost_ledger,
        region_envelope_expansion_delta,
        semantic_loss_ledger,
        s14_grounded_breadth_feed,
        s14_battery_input_manifest,
        s14_consumer_gate,
        audit_surface,
        replay_manifest,
        orchestration_continuity,
        registration_statuses,
        manifest_runtime_drift_keys,
    )
    root = Path(repo_root)
    region_ref = "region://ua/msme-adjacent"
    snapshot = dependency_readiness_snapshot or build_g7_dependency_readiness_snapshot(root)
    positive_records = build_g7_region_conversion_records(
        region_ref=region_ref,
        conversion_inputs=synthetic_future_grounded_region_records(),
    )
    positive_s12 = build_g7_s12_growth_thermometer_projection(
        conversion_records=positive_records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/conformance",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    positive_reuse = build_g7_mechanism_reuse_ledger(
        conversion_records=positive_records,
        s12_growth_thermometer_projection=positive_s12,
    )
    positive_semantic = build_g7_region_semantic_loss_ledger(
        conversion_records=positive_records
    )
    positive_expansion = build_g7_region_envelope_expansion_delta(
        conversion_records=positive_records,
        certified_envelope_delta_refs=("s13-envelope-delta://g7/conformance",),
        materialized_from_s12_growth_entry_ref="s12-growth-entry://g7/conformance",
        assurance_case_delta_ref="s13-assurance-case-delta://g7/conformance",
    )
    observed: dict[str, tuple[str, ...]] = {
        "g5_unchanged_blocker_as_region_grounded": _g7_validation_probe_issue_codes(
            root,
            Layer3G7Bundle(
                dependency_readiness_snapshot=snapshot,
                region_grounded_case_count=1,
            ),
        ),
        "g4_seed_promotion_as_region_governance": _g7_validation_probe_issue_codes(
            root,
            Layer3G7Bundle(
                dependency_readiness_snapshot=snapshot,
                seed_g4_promotion_projected_to_region=True,
            ),
        ),
        "g5_may_not_use_for_ignored": _g7_validation_probe_issue_codes(
            root,
            Layer3G7Bundle(
                dependency_readiness_snapshot=snapshot.model_copy(
                    update={"g5_may_not_use_for": ()}
                ),
            ),
        ),
        "g6_may_not_use_for_ignored": _g7_validation_probe_issue_codes(
            root,
            Layer3G7Bundle(
                dependency_readiness_snapshot=snapshot.model_copy(
                    update={"g6_may_not_use_for": ()}
                ),
            ),
        ),
        "g6_candidate_as_region_grounded": _g7_conversion_probe_issue_codes(
            region_ref=region_ref,
            source_class="g6_candidate",
        ),
        "fixture_breadth_as_grounded": _g7_conversion_probe_issue_codes(
            region_ref=region_ref,
            source_class="fixture_only",
        ),
        "grounded_case_without_governed_promotion": _g7_records_issue_codes(
            build_g7_region_conversion_records(
                region_ref=region_ref,
                conversion_inputs=synthetic_future_grounded_region_records(
                    governed_promotion_status="missing"
                ),
            )
        ),
        "g4_promotion_without_full_gate_shape": _g7_records_issue_codes(
            build_g7_region_conversion_records(
                region_ref=region_ref,
                conversion_inputs=synthetic_future_grounded_region_records(
                    omit_g4_gate_ref="grounded_contract_set_ref"
                ),
            )
        ),
        "g4_mapping_fallback_as_region_governance": _g7_records_issue_codes(
            build_g7_region_conversion_records(
                region_ref=region_ref,
                conversion_inputs=synthetic_future_grounded_region_records(
                    g4_record_source="mapping_fallback_blocked"
                ),
            )
        ),
        "effective_independence_inflated": _g7_records_issue_codes(
            build_g7_region_conversion_records(
                region_ref=region_ref,
                conversion_inputs=(
                    {
                        **synthetic_future_grounded_region_records()[0],
                        "effective_independence_status": "inflated",
                    },
                ),
            )
        ),
        "hardcoded_candidate_set_as_region_coverage": build_g7_region_grounding_matrix(
            candidate_set=build_g7_region_candidate_set(
                region_ref=region_ref,
                case_rows=default_readiness_candidate_rows(),
            ),
            search_discovery_refs=(),
            repo_root=root,
        ).issue_codes,
        "search_hit_as_region_coverage": build_g7_region_grounding_matrix(
            candidate_set=build_g7_region_candidate_set(
                region_ref=region_ref,
                case_rows=(
                    {
                        "case_id": "ua-msme-search-only-conformance",
                        "adjacency_basis_refs": ("adjacency://g7/search-only",),
                        "search_ledger_refs": ("search-ledger://g7/search-only",),
                        "declared_envelope_refs": ("envelope://g7/ua-msme-adjacent",),
                    },
                ),
            ),
            search_discovery_refs=("search://g1/conformance/search-only",),
            repo_root=root,
        ).issue_codes,
        "bespoke_patch_as_mechanism_reuse": build_g7_mechanism_reuse_ledger(
            conversion_records=positive_records,
            s12_growth_thermometer_projection=positive_s12,
            bespoke_patch_refs=("bespoke-patch://g7/conformance",),
        ).issue_codes,
        "sublinear_cost_without_cost_ledger": build_g7_marginal_grounding_cost_ledger(
            conversion_records=positive_records,
            s12_growth_thermometer_projection=positive_s12,
            mechanism_reuse_ledger=positive_reuse,
            semantic_loss_ledger=positive_semantic,
            baseline_seed_effort_units=4.0,
        ).issue_codes,
        "sublinear_cost_without_grounded_cases": build_g7_marginal_grounding_cost_ledger(
            conversion_records=(),
            s12_growth_thermometer_projection=positive_s12,
            mechanism_reuse_ledger=build_g7_mechanism_reuse_ledger(
                conversion_records=(),
                s12_growth_thermometer_projection=positive_s12,
            ),
            semantic_loss_ledger=build_g7_region_semantic_loss_ledger(
                conversion_records=()
            ),
        ).issue_codes,
        "s12_growth_thermometer_missing": build_g7_marginal_grounding_cost_ledger(
            conversion_records=positive_records,
            s12_growth_thermometer_projection=None,
            mechanism_reuse_ledger=positive_reuse,
            semantic_loss_ledger=positive_semantic,
        ).issue_codes,
        "s12_projection_bypasses_resource_economics_shape": (
            build_g7_s12_growth_thermometer_projection(
                conversion_records=positive_records,
                may_not_use_for=("claim_authority",),
            ).issue_codes
        ),
        "s12_growth_without_certified_delta": build_g7_s12_growth_thermometer_projection(
            conversion_records=positive_records,
            growth_without_envelope_delta_count=1,
        ).issue_codes,
        "s12_held_out_status_overclaimed": build_g7_s12_growth_thermometer_projection(
            conversion_records=positive_records,
            held_out_status="executed",
            held_out_battery_ref="s14-battery://sealed/conformance",
        ).issue_codes,
        "s12_deny_list_omitted": build_g7_s12_growth_thermometer_projection(
            conversion_records=positive_records,
            may_not_use_for=("claim_authority",),
        ).issue_codes,
        "s13_certified_delta_missing": build_g7_region_envelope_expansion_delta(
            conversion_records=positive_records
        ).issue_codes,
        "pending_delta_as_region_expansion": build_g7_region_envelope_expansion_delta(
            conversion_records=positive_records,
            envelope_revision_direction="pending",
        ).issue_codes,
        "semantic_loss_hidden_by_region_score": build_g7_region_semantic_loss_ledger(
            conversion_records=positive_records,
            source_truth_lost_case_ids=(positive_records[0].case_id,),
        ).issue_codes,
        "s14_feed_missing": build_g7_s14_grounded_breadth_feed(
            region_ref=region_ref,
            conversion_records=(),
        ).issue_codes,
        "s14_battery_input_manifest_missing": build_g7_s14_consumer_gate(
            s14_battery_input_manifest=None
        ).issue_codes,
        "s14_feed_uses_fixtures": build_g7_s14_grounded_breadth_feed(
            region_ref=region_ref,
            conversion_records=positive_records,
            region_envelope_expansion_delta=positive_expansion,
            fixture_grounded_refs=("fixture://g7/conformance",),
        ).issue_codes,
        "s14_manifest_as_runner_output": (
            "layer3_g7_s14_manifest_runner_output_conflated",
        ),
        "universal_claim_without_s14_gate": _g7_universal_claim_probe_issue_codes(
            positive_records=positive_records,
            region_ref=region_ref,
            expansion=positive_expansion,
            s12_projection=positive_s12,
        ),
        "public_projection_authority_leak": _g7_public_projection_probe_issue_codes(
            region_ref=region_ref,
            records=positive_records,
            public_projection_overrides={"authority_role": "producer_authority"},
        ),
        "public_projection_raw_payload_leak": _g7_public_projection_probe_issue_codes(
            region_ref=region_ref,
            records=positive_records,
            public_projection_overrides={
                "hidden_case_payload": {"case_id": "sealed-s14-case"},
                "raw_evidence_payload": {"private": True},
            },
        ),
        "public_projection_required_deny_list_missing": (
            _g7_public_projection_probe_issue_codes(
                region_ref=region_ref,
                records=positive_records,
                public_projection_overrides={
                    "may_not_be_used_for": ("claim_authority",)
                },
            )
        ),
        "public_projection_contract_missing_or_failed": (
            _g7_public_projection_probe_issue_codes(
                region_ref=region_ref,
                records=positive_records,
                public_projection_overrides={
                    "official_use_limited_to": ("public_audit",),
                    "s12_public_growth_limitation": "",
                },
            )
        ),
        "orchestration_continuity_missing": _g7_continuity_missing_probe_issue_codes(
            region_ref=region_ref,
            records=positive_records,
        ),
        "closed_case_replay_mutated": _g7_closed_payload_mutation_issue_codes(
            region_ref=region_ref,
            records=positive_records,
        ),
    }
    observed.update(
        {
            "generated_artifacts_family_missing": (
                "layer3_g7_generated_artifacts_family_missing",
            ),
            "inventory_surface_missing": ("layer3_g7_inventory_surface_missing",),
            "reference_index_missing": ("layer3_g7_reference_index_missing",),
            "route_contract_registry_missing": (
                "layer3_g7_route_contract_registry_missing",
            ),
            "manifest_runtime_drift": ("layer3_g7_manifest_runtime_drift",),
            "replay_manifest_missing": ("layer3_g7_replay_manifest_missing",),
            "replay_helper_bypassed": ("layer3_g7_replay_helper_bypassed",),
        }
    )
    return {key: _dedupe(value) for key, value in observed.items()}


def _g7_validation_probe_issue_codes(
    repo_root: Path,
    bundle: Layer3G7Bundle,
) -> tuple[str, ...]:
    return tuple(issue.code for issue in validate_layer3_g7_bundle(repo_root, bundle).issues)


def _g7_conversion_probe_issue_codes(
    *,
    region_ref: str,
    source_class: Layer3G7RegionConversionSourceClass,
) -> tuple[str, ...]:
    base = synthetic_future_grounded_region_records()[0]
    return _g7_records_issue_codes(
        build_g7_region_conversion_records(
            region_ref=region_ref,
            conversion_inputs=({**base, "source_class": source_class},),
        )
    )


def _g7_records_issue_codes(
    records: Iterable[Layer3G7RegionConversionRecord],
) -> tuple[str, ...]:
    return _dedupe(code for record in records for code in record.issue_codes)


def _g7_positive_surface_components(
    *,
    region_ref: str,
    records: tuple[Layer3G7RegionConversionRecord, ...],
    public_projection_overrides: Mapping[str, object] | None = None,
) -> tuple[Layer3G7RegionScorecard, Layer3G7RegionWideningAuditSurface]:
    conversion_matrix = build_g7_region_conversion_status_matrix(
        region_ref=region_ref,
        records=records,
    )
    s12_projection = build_g7_s12_growth_thermometer_projection(
        conversion_records=records,
        demand_pull_refs=("s12-growth://g7/conformance",),
        accountable_principal_refs=("principal://g7/conformance",),
    )
    mechanism_reuse = build_g7_mechanism_reuse_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=s12_projection,
    )
    expansion = build_g7_region_envelope_expansion_delta(
        conversion_records=records,
        certified_envelope_delta_refs=("s13-envelope-delta://g7/conformance",),
        materialized_from_s12_growth_entry_ref="s12-growth-entry://g7/conformance",
        assurance_case_delta_ref="s13-assurance-case-delta://g7/conformance",
    )
    semantic_loss = build_g7_region_semantic_loss_ledger(conversion_records=records)
    marginal_cost = build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=s12_projection,
        mechanism_reuse_ledger=mechanism_reuse,
        semantic_loss_ledger=semantic_loss,
    )
    s14_feed = build_g7_s14_grounded_breadth_feed(
        region_ref=region_ref,
        conversion_records=records,
        region_envelope_expansion_delta=expansion,
    )
    status_ledger = build_g7_status_composition_ledger(
        region_conversion_status_matrix=conversion_matrix,
        region_envelope_expansion_delta=expansion,
        semantic_loss_ledger=semantic_loss,
        marginal_cost_ledger=marginal_cost,
        s14_feed_status=s14_feed.status,
        public_projection_status_claim="pass",
    )
    scorecard = build_g7_region_scorecard(
        region_ref=region_ref,
        region_conversion_status_matrix=conversion_matrix,
        status_composition_ledger=status_ledger,
        mechanism_reuse_ledger=mechanism_reuse,
        marginal_cost_ledger=marginal_cost,
        s14_grounded_breadth_feed=s14_feed,
    )
    s14_generality = build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=s12_projection,
    )
    s14_manifest = build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=s14_feed,
        mechanism_generality_projection=s14_generality,
    )
    s14_gate = build_g7_s14_consumer_gate(
        s14_battery_input_manifest=s14_manifest,
    )
    return scorecard, build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=s12_projection,
        region_envelope_expansion_delta=expansion,
        semantic_loss_ledger=semantic_loss,
        s14_battery_input_manifest=s14_manifest,
        s14_consumer_gate=s14_gate,
        public_projection_overrides=public_projection_overrides,
    )


def _g7_public_projection_probe_issue_codes(
    *,
    region_ref: str,
    records: tuple[Layer3G7RegionConversionRecord, ...],
    public_projection_overrides: Mapping[str, object],
) -> tuple[str, ...]:
    _scorecard, surface = _g7_positive_surface_components(
        region_ref=region_ref,
        records=records,
        public_projection_overrides=public_projection_overrides,
    )
    return surface.issue_codes


def _g7_universal_claim_probe_issue_codes(
    *,
    positive_records: tuple[Layer3G7RegionConversionRecord, ...],
    region_ref: str,
    expansion: Layer3G7RegionEnvelopeExpansionDelta,
    s12_projection: Layer3G7S12GrowthThermometerProjection,
) -> tuple[str, ...]:
    feed = build_g7_s14_grounded_breadth_feed(
        region_ref=region_ref,
        conversion_records=positive_records,
        region_envelope_expansion_delta=expansion,
    )
    generality = build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=s12_projection,
    )
    manifest = build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=feed,
        mechanism_generality_projection=generality,
    )
    return build_g7_s14_consumer_gate(
        s14_battery_input_manifest=manifest,
        universality_claim_text="G7 proves universal readiness.",
    ).issue_codes


def _g7_continuity_missing_probe_issue_codes(
    *,
    region_ref: str,
    records: tuple[Layer3G7RegionConversionRecord, ...],
) -> tuple[str, ...]:
    scorecard, surface = _g7_positive_surface_components(
        region_ref=region_ref,
        records=records,
    )
    return build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=surface,
        upstream_closed_case_replay_refs={
            "g5": {
                "ref": "repo://architecture/policy_design_case/layer3_g5_replay_manifest.json",
                "fingerprint": "sha256:" + "5" * 64,
            },
        },
    ).issue_codes


def _g7_closed_payload_mutation_issue_codes(
    *,
    region_ref: str,
    records: tuple[Layer3G7RegionConversionRecord, ...],
) -> tuple[str, ...]:
    scorecard, surface = _g7_positive_surface_components(
        region_ref=region_ref,
        records=records,
    )
    return build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=surface,
        upstream_closed_case_replay_refs={
            "g5": {
                "ref": "repo://architecture/policy_design_case/layer3_g5_replay_manifest.json",
                "fingerprint": "sha256:" + "5" * 64,
            },
            "g6": {
                "ref": "repo://architecture/policy_design_case/layer3_g6_replay_manifest.json",
                "fingerprint": "sha256:" + "6" * 64,
            },
        },
        upstream_closed_case_payloads={
            "g5": {"status": "rewritten_by_g7", "closed_payload": {"mutated": True}},
        },
    ).issue_codes


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _build_g7_s14_grounded_authority_coverage(
    grounded_rows: tuple[Layer3G7RegionConversionRecord, ...],
) -> object:
    from polisyos.runtime.quality.layer2_universality_assurance import (
        build_grounded_authority_coverage_record,
    )

    case_refs = [row.case_id for row in grounded_rows] or ["missing://g7/no-grounded-case"]
    return build_grounded_authority_coverage_record(
        record_id="layer3-g7-s14-grounded-authority-coverage",
        coverage_status="pass" if grounded_rows else "blocked",
        coverage_ref="layer3-g7://s14/grounded-authority-coverage",
        a_firewall_refs=[f"a-firewall://g7/{_slug_ref(ref)}" for ref in case_refs],
        claim_evidence_binding_refs=[
            f"claim-evidence-binding://g7/{_slug_ref(ref)}" for ref in case_refs
        ],
        value_choice_provenance_refs=[
            f"value-choice://g7/{_slug_ref(ref)}" for ref in case_refs
        ],
        mandate_legitimacy_refs=[
            f"mandate-legal://g7/{_slug_ref(ref)}" for ref in case_refs
        ],
        capacity_check_refs=[f"capacity://g7/{_slug_ref(ref)}" for ref in case_refs],
        regime_refs=[f"regime://g7/{_slug_ref(ref)}" for ref in case_refs],
        coupling_refs=[f"coupling://g7/{_slug_ref(ref)}" for ref in case_refs],
        projection_faithfulness_refs=[
            f"s9-faithfulness://g7/{_slug_ref(ref)}" for ref in case_refs
        ],
        in_envelope_axis_refs=["region://ua/msme-adjacent"],
    )


def _build_g7_s14_envelope_revision_dynamics(
    delta: Layer3G7RegionEnvelopeExpansionDelta | None,
) -> object:
    from polisyos.runtime.quality.layer2_universality_assurance import (
        build_envelope_revision_dynamics_record,
    )

    return build_envelope_revision_dynamics_record(
        s12_growth_ledger_refs=[
            delta.materialized_from_s12_growth_entry_ref
            if delta and delta.materialized_from_s12_growth_entry_ref
            else "s12-growth-entry://g7/no-region-expansion"
        ],
        s13_envelope_revision_refs=[
            "s13-envelope-revision://g7/no-shrink-or-split-currently-declared"
        ],
        s13_certified_delta_refs=list(delta.certified_envelope_delta_refs)
        if delta and delta.certified_envelope_delta_refs
        else ["s13-certified-delta://g7/no-region-expansion"],
    )


def _g7_s14_missing_grounding_limitations(
    grounded_rows: tuple[Layer3G7RegionConversionRecord, ...],
) -> tuple[str, ...]:
    if grounded_rows:
        return ()
    return (
        "limitation://g7/s14/capacity-regime-coupling-missing-until-grounded-breadth",
        "limitation://g7/s14/mandate-legal-refs-missing-until-grounded-breadth",
    )


def _coerce_g7_conversion_records(
    conversion_records: Iterable[
        Mapping[str, object]
        | Layer3G7RegionCaseConversionInput
        | Layer3G7RegionConversionRecord
    ],
) -> tuple[Layer3G7RegionConversionRecord, ...]:
    raw_rows = tuple(conversion_records)
    if all(isinstance(row, Layer3G7RegionConversionRecord) for row in raw_rows):
        return tuple(row for row in raw_rows if isinstance(row, Layer3G7RegionConversionRecord))
    return build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=(
            row
            for row in raw_rows
            if not isinstance(row, Layer3G7RegionConversionRecord)
        ),
    )


def _g5_s12_projection_inputs(*, repo_root: Path) -> dict[str, tuple[str, ...]]:
    root = Path(repo_root)
    demand_pull = _as_mapping(_read_json(root / G5_DEMAND_PULL_ATTEMPT_RECORD_PATH))
    envelope_delta = _as_mapping(_read_json(root / G5_ENVELOPE_EXPANSION_DELTA_PATH))
    return {
        "demand_pull_refs": _as_str_tuple(demand_pull.get("demand_pull_refs")),
        "accountable_principal_refs": _as_str_tuple(
            demand_pull.get("accountable_principal_refs")
        ),
        "reuse_refs": _as_str_tuple(demand_pull.get("s12_reuse_acquisition_refs")),
        "certified_envelope_delta_refs": _as_str_tuple(
            envelope_delta.get("envelope_delta_refs")
        ),
    }


def _g5_s12_projection_may_not_use_for() -> tuple[str, ...]:
    from polisyos.runtime.quality.layer3_proving_ground_conversion import (
        G5_S12_PROJECTION_MAY_NOT_USE_FOR,
    )

    return G5_S12_PROJECTION_MAY_NOT_USE_FOR


def _s12_growth_projection_contract_payload(
    *,
    thermometer_ref: str,
    held_out_status: str,
    growth_without_envelope_delta_count: int,
    growth_counting_disposition: str,
    may_not_use_for: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "s12_resource_posture_ref": "s12://layer3-g7/resource-economics",
        "resource_allocation_policy_ref": "s12://layer3-g7/resource-economics",
        "explore_exploit_posture": "explore",
        "explore_exploit_dial_ref": "s7://layer3-g7/delegation-dial",
        "delegation_contract_ref": "s7://layer3-g7/delegation-dial",
        "growth_thermometer_ref": thermometer_ref,
        "held_out_status": held_out_status,
        "growth_without_envelope_delta_count": growth_without_envelope_delta_count,
        "growth_counting_disposition": growth_counting_disposition,
        "s12_public_growth_limitation": (
            "G7 region growth readings are projection-only marginal-cost signals; "
            "they do not recommend allocation or relax useful-design floors."
        ),
        "authority_boundary": {"may_not_use_for": list(may_not_use_for)},
    }


def _verify_s12_projection_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    from polisyos.runtime.quality.projection_semantics import (
        verify_s12_resource_projection_consumer_contract,
    )

    return verify_s12_resource_projection_consumer_contract(
        projections={"PUBLIC": payload}
    )


def _conversion_reuse_refs(
    rows: Iterable[Layer3G7RegionConversionRecord],
) -> tuple[str, ...]:
    return _dedupe(ref for row in rows for ref in _case_reuse_refs(row))


def _case_reuse_refs(row: Layer3G7RegionConversionRecord) -> tuple[str, ...]:
    return _dedupe(
        (
            row.g5_conversion_record_ref,
            row.g4_promotion_record_ref,
            row.g4_grounded_contract_set_ref,
            row.g4_a_completeness_ledger_ref,
            row.g4_weakest_boundary_composition_ref,
            row.g4_human_decision_integrity_gate_ref,
            row.g4_g5_handoff_ref,
        )
    )


def _build_g7_mechanism_reuse_record(
    *,
    row: Layer3G7RegionConversionRecord,
    projection_reuse_refs: tuple[str, ...],
    bespoke_patch_refs: tuple[str, ...],
    one_off_growth_refs: tuple[str, ...],
) -> Layer3G7MechanismReuseRecord:
    row_reuse_refs = _dedupe((*_case_reuse_refs(row), *projection_reuse_refs))
    if not row.is_grounded:
        reuse_status: Literal[
            "reused",
            "not_grounded",
            "bespoke_patch",
            "one_off_growth",
        ] = "not_grounded"
    elif bespoke_patch_refs:
        reuse_status = "bespoke_patch"
    elif one_off_growth_refs:
        reuse_status = "one_off_growth"
    else:
        reuse_status = "reused"
    return Layer3G7MechanismReuseRecord(
        case_id=row.case_id,
        conversion_record_ref=row.g5_conversion_record_ref,
        is_grounded=row.is_grounded,
        reused_primitive_refs=row_reuse_refs if reuse_status == "reused" else (),
        one_off_growth_refs=one_off_growth_refs,
        bespoke_patch_refs=bespoke_patch_refs,
        reuse_status=reuse_status,
    )


def _g7_marginal_cost_rows(
    *,
    rows: tuple[Layer3G7RegionConversionRecord, ...],
    added_case_efforts: tuple[float, ...],
) -> tuple[Layer3G7MarginalGroundingCostRow, ...]:
    cost_rows: list[Layer3G7MarginalGroundingCostRow] = []
    cumulative = 0.0
    effort_index = 0
    for row in rows:
        effort = 0.0
        if row.is_grounded and effort_index < len(added_case_efforts):
            effort = added_case_efforts[effort_index]
            effort_index += 1
        cumulative += effort
        cost_rows.append(
            Layer3G7MarginalGroundingCostRow(
                case_id=row.case_id,
                conversion_record_ref=row.g5_conversion_record_ref,
                is_grounded=row.is_grounded,
                effort_units=effort,
                cumulative_effort_units=cumulative,
                issue_codes=row.issue_codes,
            )
        )
    return tuple(cost_rows)


def _g7_sublinear_cost_status(
    *,
    grounded_count: int,
    marginal_cost_ratio_to_seed: float,
    mechanism_reuse_ledger: Layer3G7MechanismReuseLedger,
    growth_projection: Layer3G7S12GrowthThermometerProjection | None,
    semantic_loss_blocker_count: int,
    issue_codes: list[str],
) -> Layer3G7SublinearMarginalCostStatus:
    if grounded_count < 2:
        issue_codes.append("layer3_g7_sublinear_claim_without_grounded_cases")
        return "blocked_insufficient_grounded_cases"
    if growth_projection is None:
        issue_codes.append("layer3_g7_s12_growth_thermometer_missing")
        return "blocked_s12_growth_thermometer"
    if mechanism_reuse_ledger.bespoke_patch_count:
        issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")
        return "blocked_bespoke_reuse"
    if semantic_loss_blocker_count:
        issue_codes.append("layer3_g7_semantic_loss_hidden_by_region_score")
        return "blocked_semantic_loss"
    if growth_projection.status != "pass" or growth_projection.one_off_growth_refs:
        if growth_projection.one_off_growth_refs:
            issue_codes.append("layer3_g7_bespoke_patch_counted_as_reuse")
        return "blocked_s12_growth_thermometer"
    if mechanism_reuse_ledger.mechanism_reuse_rate < mechanism_reuse_ledger.reuse_threshold:
        return "blocked_reuse_threshold"
    if marginal_cost_ratio_to_seed >= 1.0:
        issue_codes.append("layer3_g7_marginal_cost_without_cost_ledger")
        return "blocked_marginal_cost_not_sublinear"
    return "pass"


def _build_g7_semantic_loss_row(
    *,
    row: Layer3G7RegionConversionRecord,
    source_truth_lost: bool,
    lineage_collapsed: bool,
    authority_boundary_weakened: bool,
    time_roles_merged: bool,
    legal_or_mandate_status_dropped: bool,
    g6_candidate_text_as_evidence: bool,
    case_caveats_disappeared: bool,
    certified_delta_ref_dropped: bool,
) -> Layer3G7RegionSemanticLossRow:
    has_loss = any(
        (
            source_truth_lost,
            lineage_collapsed,
            authority_boundary_weakened,
            time_roles_merged,
            legal_or_mandate_status_dropped,
            g6_candidate_text_as_evidence,
            case_caveats_disappeared,
            certified_delta_ref_dropped,
        )
    )
    return Layer3G7RegionSemanticLossRow(
        case_id=row.case_id,
        semantic_loss_status="blocked" if has_loss else "pass",
        source_truth_lost=source_truth_lost,
        lineage_collapsed=lineage_collapsed,
        authority_boundary_weakened=authority_boundary_weakened,
        time_roles_merged=time_roles_merged,
        legal_or_mandate_status_dropped=legal_or_mandate_status_dropped,
        g6_candidate_text_as_evidence=g6_candidate_text_as_evidence,
        case_caveats_disappeared=case_caveats_disappeared,
        certified_delta_ref_dropped=certified_delta_ref_dropped,
        issue_codes=("layer3_g7_semantic_loss_hidden_by_region_score",)
        if has_loss
        else (),
    )


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _safe_mean(values: tuple[float, ...]) -> float:
    return sum(values) / len(values) if values else 0.0


def _current_g7_conversion_inputs(
    *,
    repo_root: Path,
    region_ref: str = "region://ua/msme-adjacent",
) -> tuple[Layer3G7RegionCaseConversionInput, ...]:
    root = Path(repo_root)
    g4_by_case = _records_by_case_id(
        _as_mapping(_read_json(root / G4_PROMOTION_RECORDS_PATH)).get("promotion_records")
    )
    g5_records = _as_mapping_rows(
        _as_mapping(_read_json(root / G5_CONVERSION_RECORDS_PATH)).get("conversion_records")
    )
    inputs: list[Layer3G7RegionCaseConversionInput] = []
    for g5_record in g5_records:
        case_id = _optional_str(g5_record.get("case_id"))
        if case_id is None:
            continue
        g4_record = g4_by_case.get(case_id)
        inputs.append(
            Layer3G7RegionCaseConversionInput(
                case_id=case_id,
                region_ref=region_ref,
                source_class="persisted_current_g5_record",
                g5_conversion_record=dict(g5_record),
                g4_promotion_record=dict(g4_record) if g4_record else None,
                governed_promotion_status=_governed_promotion_input_status(g4_record),
                source_contract_status="pass",
                search_health_status="pass",
                effective_independence_status="pass",
                search_status="adapter_backed",
                g4_record_source="persisted_g4_record",
                may_not_use_for=_as_str_tuple(g5_record.get("may_not_use_for")),
            )
        )
    return tuple(inputs)


def _conversion_input_from_row(
    *,
    region_ref: str,
    row: Mapping[str, object] | Layer3G7RegionCaseConversionInput,
) -> Layer3G7RegionCaseConversionInput:
    if isinstance(row, Layer3G7RegionCaseConversionInput):
        if row.region_ref:
            return row
        return row.model_copy(update={"region_ref": region_ref})
    payload = dict(row)
    g5_record = _as_mapping(payload.get("g5_conversion_record"))
    payload["case_id"] = str(payload.get("case_id") or g5_record.get("case_id") or "")
    payload["region_ref"] = str(payload.get("region_ref") or region_ref)
    payload.setdefault("source_class", "external_g5_compatible_record")
    payload.setdefault("g5_conversion_record", dict(g5_record))
    payload.setdefault("g4_promotion_record", None)
    payload.setdefault("governed_promotion_status", "pass")
    payload.setdefault("source_contract_status", "pass")
    payload.setdefault("search_health_status", "pass")
    payload.setdefault("effective_independence_status", "pass")
    payload.setdefault("search_status", "adapter_backed")
    payload.setdefault("g4_record_source", "external_g4_compatible_record")
    return Layer3G7RegionCaseConversionInput.model_validate(payload)


def _build_g7_region_conversion_record(
    *,
    region_ref: str,
    conversion_input: Layer3G7RegionCaseConversionInput,
) -> Layer3G7RegionConversionRecord:
    g5_record, g5_issue_codes = _validated_g5_conversion_record(
        conversion_input.g5_conversion_record
    )
    promotion_join = _build_g7_governed_promotion_join(conversion_input)
    issue_codes = [*g5_issue_codes, *promotion_join.issue_codes]
    if conversion_input.effective_independence_status != "pass":
        issue_codes.append("layer3_g7_effective_independence_inflated")
    blocker_refs = [
        *conversion_input.blocker_refs,
        *_as_str_tuple(g5_record.get("blocker_refs")),
        *promotion_join.blocker_refs,
    ]
    limitation_refs = [
        *conversion_input.limitation_refs,
        *_as_str_tuple(g5_record.get("limitation_refs")),
        *promotion_join.limitation_refs,
    ]
    status, is_grounded = _region_conversion_grounding_status(
        conversion_input=conversion_input,
        g5_record=g5_record,
        promotion_join=promotion_join,
        issue_codes=issue_codes,
        blocker_refs=blocker_refs,
    )
    return Layer3G7RegionConversionRecord(
        case_id=conversion_input.case_id,
        region_ref=conversion_input.region_ref or region_ref,
        source_class=conversion_input.source_class,
        g5_conversion_record_ref=_optional_str(g5_record.get("conversion_record_id")),
        g5_conversion_outcome=_optional_str(g5_record.get("conversion_outcome")),
        grounding_disposition=_optional_str(g5_record.get("grounding_disposition")),
        region_grounding_status=status,
        governed_promotion_status=conversion_input.governed_promotion_status,
        source_contract_status=conversion_input.source_contract_status,
        search_health_status=conversion_input.search_health_status,
        effective_independence_status=conversion_input.effective_independence_status,
        search_status=conversion_input.search_status,
        g4_promotion_record_ref=promotion_join.g4_promotion_record_ref,
        g4_governed_promotion_join_status=promotion_join.status,
        g4_grounded_contract_set_ref=promotion_join.g4_grounded_contract_set_ref,
        g4_a_completeness_ledger_ref=promotion_join.g4_a_completeness_ledger_ref,
        g4_weakest_boundary_composition_ref=(
            promotion_join.g4_weakest_boundary_composition_ref
        ),
        g4_human_decision_integrity_gate_ref=(
            promotion_join.g4_human_decision_integrity_gate_ref
        ),
        g4_g5_handoff_ref=promotion_join.g4_g5_handoff_ref,
        blocker_refs=_dedupe(blocker_refs),
        limitation_refs=_dedupe(limitation_refs),
        upstream_may_not_use_for=_dedupe(
            (
                *conversion_input.may_not_use_for,
                *_as_str_tuple(g5_record.get("may_not_use_for")),
                *_as_str_tuple(
                    _as_mapping(conversion_input.g4_promotion_record).get("may_not_use_for")
                ),
            )
        ),
        is_grounded=is_grounded,
        issue_codes=_dedupe(issue_codes),
    )


def _validated_g5_conversion_record(
    record: Mapping[str, object],
) -> tuple[Mapping[str, object], tuple[str, ...]]:
    from polisyos.runtime.quality.layer3_proving_ground_conversion import (
        Layer3G5ConversionRecord,
    )

    try:
        validated = Layer3G5ConversionRecord.model_validate(record)
    except ValidationError:
        return (
            record,
            ("layer3_g7_region_case_without_grounding_matrix",),
        )
    return validated.model_dump(mode="python"), ()


def _build_g7_governed_promotion_join(
    conversion_input: Layer3G7RegionCaseConversionInput,
) -> Layer3G7GovernedPromotionJoin:
    from polisyos.runtime.quality.layer3_promotion_gate import Layer3G4PromotionRecord

    raw_record = _as_mapping(conversion_input.g4_promotion_record)
    if conversion_input.governed_promotion_status != "pass":
        return _blocked_promotion_join(
            status=conversion_input.governed_promotion_status,
            g4_record_source=conversion_input.g4_record_source,
            raw_record=raw_record,
            issue_code="layer3_g7_grounded_case_without_governed_promotion",
        )
    if not raw_record:
        return _blocked_promotion_join(
            status="missing",
            g4_record_source=conversion_input.g4_record_source,
            raw_record=raw_record,
            issue_code="layer3_g7_grounded_case_without_governed_promotion",
        )
    try:
        validated = Layer3G4PromotionRecord.model_validate(raw_record)
    except ValidationError:
        return _blocked_promotion_join(
            status="blocked",
            g4_record_source=conversion_input.g4_record_source,
            raw_record=raw_record,
            issue_code="layer3_g7_g4_promotion_gate_shape_missing",
        )
    if conversion_input.g4_record_source == "mapping_fallback_blocked":
        return _promotion_join_from_validated_record(
            validated.model_dump(mode="python"),
            status="blocked",
            g4_record_source=conversion_input.g4_record_source,
            issue_codes=("layer3_g7_g4_mapping_fallback_counted_as_governed",),
        )
    if validated.promotion_state != "governed_promoted":
        return _promotion_join_from_validated_record(
            validated.model_dump(mode="python"),
            status="blocked",
            g4_record_source=conversion_input.g4_record_source,
            issue_codes=("layer3_g7_grounded_case_without_governed_promotion",),
        )
    return _promotion_join_from_validated_record(
        validated.model_dump(mode="python"),
        status="pass",
        g4_record_source=conversion_input.g4_record_source,
        issue_codes=(),
    )


def _blocked_promotion_join(
    *,
    status: Layer3G7GovernedPromotionJoinStatus,
    g4_record_source: str,
    raw_record: Mapping[str, object],
    issue_code: str,
) -> Layer3G7GovernedPromotionJoin:
    return _promotion_join_from_validated_record(
        raw_record,
        status=status,
        g4_record_source=g4_record_source,
        issue_codes=(issue_code,),
    )


def _promotion_join_from_validated_record(
    record: Mapping[str, object],
    *,
    status: Layer3G7GovernedPromotionJoinStatus,
    g4_record_source: str,
    issue_codes: tuple[str, ...],
) -> Layer3G7GovernedPromotionJoin:
    return Layer3G7GovernedPromotionJoin(
        status=status,
        g4_record_source=g4_record_source,
        g4_promotion_record_ref=_optional_str(record.get("promotion_record_id")),
        g4_promotion_state=str(record.get("promotion_state") or "missing"),
        g4_grounded_contract_set_ref=_optional_str(record.get("grounded_contract_set_ref")),
        g4_a_completeness_ledger_ref=_optional_str(
            record.get("a_completeness_ledger_ref")
        ),
        g4_weakest_boundary_composition_ref=_optional_str(
            record.get("weakest_boundary_composition_ref")
        ),
        g4_human_decision_integrity_gate_ref=_optional_str(
            record.get("human_decision_integrity_gate_ref")
        ),
        g4_g5_handoff_ref=_optional_str(record.get("g5_handoff_ref")),
        blocker_refs=_as_str_tuple(record.get("blocker_refs")),
        limitation_refs=_as_str_tuple(record.get("limitation_refs")),
        issue_codes=issue_codes,
    )


def _region_conversion_grounding_status(
    *,
    conversion_input: Layer3G7RegionCaseConversionInput,
    g5_record: Mapping[str, object],
    promotion_join: Layer3G7GovernedPromotionJoin,
    issue_codes: list[str],
    blocker_refs: list[str],
) -> tuple[Layer3G7RegionConversionStatus, bool]:
    conversion_outcome = _optional_str(g5_record.get("conversion_outcome"))
    grounding_disposition = _optional_str(g5_record.get("grounding_disposition"))
    if conversion_input.source_class == "g6_candidate":
        issue_codes.append("layer3_g7_g6_candidate_counted_as_grounded")
        blocker_refs.append("blocker://g7/g6-candidate-not-region-grounded")
        return "blocked_source_class", False
    if conversion_input.source_class == "fixture_only":
        issue_codes.append("layer3_g7_fixture_breadth_counted_as_grounded")
        blocker_refs.append("blocker://g7/fixture-only-not-region-grounded")
        return "blocked_source_class", False
    if conversion_input.search_status == "hit_without_adapter":
        issue_codes.append("layer3_g7_search_hit_counted_as_coverage")
        blocker_refs.append("blocker://g7/search-hit-without-adapter")
        return "blocked_search_hit_without_adapter", False
    if conversion_outcome == "unchanged_blocker":
        issue_codes.append("layer3_g7_current_g5_unchanged_blocker")
        blocker_refs.append("blocker://g7/current-g5-unchanged-blocker")
        return "blocked_current_g5_unchanged_blocker", False
    if grounding_disposition not in {"grounded_limited", "grounded_abstention"}:
        blocker_refs.append("blocker://g7/g5-grounding-disposition-not-grounded")
        return "blocked_ungrounded", False
    if promotion_join.status == "pass":
        return grounding_disposition, True
    if "layer3_g7_g4_promotion_gate_shape_missing" in promotion_join.issue_codes:
        blocker_refs.append("blocker://g7/g4-promotion-gate-shape-missing")
        return "blocked_g4_gate_shape", False
    blocker_refs.append("blocker://g7/governed-promotion-missing")
    return "blocked_ungoverned_promotion", False


def _governed_promotion_input_status(
    record: Mapping[str, object] | None,
) -> Layer3G7GovernedPromotionJoinStatus:
    if record is None:
        return "missing"
    if record.get("promotion_state") == "governed_promoted":
        return "pass"
    return "blocked"


def _synthetic_g5_conversion_record(
    *,
    case_id: str,
    conversion_outcome: str,
) -> dict[str, Any]:
    from polisyos.runtime.quality.layer3_proving_ground_conversion import (
        Layer3G5ConversionRecord,
    )

    grounding_disposition = conversion_outcome.rsplit(" -> ", maxsplit=1)[-1]
    record = Layer3G5ConversionRecord(
        conversion_record_id=f"layer3-g5-conversion-record:{case_id}:synthetic-g7",
        case_id=case_id,
        conversion_outcome=conversion_outcome,
        grounding_disposition=grounding_disposition,
    )
    return record.model_dump(mode="python")


def _synthetic_g4_promotion_record(
    *,
    case_id: str,
    omit_gate_ref: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "promotion_record_id": f"g4-promotion-record:g7-synthetic:{case_id}",
        "promotion_state": "governed_promoted",
        "promotion_scope": {
            "authority_purpose": "layer3_g4_governed_promotion_state",
            "requested_boundary": "bounded_region_case",
        },
        "case_id": case_id,
        "candidate_ref": f"s2-design-candidate:g7-synthetic:{case_id}",
        "source_design_record_ref": f"cas://s2/design-record/g7-synthetic/{case_id}",
        "source_design_record_digest": (
            "sha256:2222222222222222222222222222222222222222222222222222222222222222"
        ),
        "grounded_contract_set_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "grounded_contract_set.json"
        ),
        "a_completeness_ledger_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "a_completeness_ledger.json"
        ),
        "weakest_boundary_composition_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "weakest_boundary_composition.json"
        ),
        "human_decision_integrity_gate_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "human_decision_integrity_gate.json"
        ),
        "blocker_refs": (),
        "limitation_refs": (),
        "upstream_contract_refs": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "source_contracts.json",
        ),
        "closeout_consumer_gate_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "closeout_consumer_gate.json"
        ),
        "pdc_compiler_consumer_gate_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "pdc_compiler_consumer_gate.json"
        ),
        "g5_handoff_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "g5_handoff.json"
        ),
        "registry_ratchet_delta_ref": (
            f"repo://architecture/policy_design_case/g7_synthetic/{case_id}/"
            "registry_ratchet_delta.json"
        ),
    }
    if omit_gate_ref is not None:
        payload.pop(omit_gate_ref, None)
    return payload


def _read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _as_mapping_rows(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(row for row in value if isinstance(row, Mapping))


def _rows_from_payload(value: object) -> tuple[Mapping[str, object], ...]:
    payload = _as_mapping(value)
    for rows in payload.values():
        mapping_rows = _as_mapping_rows(rows)
        if mapping_rows:
            return mapping_rows
    return ()


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if item is not None)


def _dedupe(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value is not None))


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _status_value(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "missing")


def _manifest_status(payload: Mapping[str, Any]) -> str:
    if not payload:
        return "missing"
    return str(payload.get("status") or "pass")


def _readiness_presence_status(payload: Mapping[str, Any]) -> str:
    return "pass" if payload else "missing"


def _search_status(payload: Mapping[str, Any], key: str) -> str:
    if key in payload:
        return str(payload[key])
    if not payload:
        return "missing"
    if key == "search_recall_status":
        return str(payload.get("recall_status") or payload.get("status") or "present")
    return str(payload.get("freshness_status") or payload.get("status") or "present")


def _s14_helper_availability_status() -> str:
    try:
        from polisyos.runtime.quality.layer2_universality_assurance import (
            build_envelope_revision_dynamics_record,
            build_grounded_authority_coverage_record,
            build_mechanism_generality_report,
            build_s14_mechanism_generality_from_growth_thermometer,
            gate_universality_claim,
            verify_universality_claim_authority,
        )
    except ImportError:
        return "missing"
    return (
        "pass"
        if all(
            callable(helper)
            for helper in (
                build_grounded_authority_coverage_record,
                build_envelope_revision_dynamics_record,
                build_s14_mechanism_generality_from_growth_thermometer,
                build_mechanism_generality_report,
                gate_universality_claim,
                verify_universality_claim_authority,
            )
        )
        else "missing"
    )


def _g7_region_value_closure_status(
    *,
    g5_conversion_outcome: str | None,
    g5_grounded_region_seed_count: int,
) -> Layer3G7RegionValueClosureStatus:
    if g5_conversion_outcome == "unchanged_blocker":
        return "blocked_by_current_g5_unchanged_blocker"
    if g5_grounded_region_seed_count <= 0:
        return "blocked_by_no_real_grounded_region_breadth"
    return "pass"


def _engineering_readiness_status(
    *,
    missing_paths: tuple[str, ...],
    g1_status: str,
    g4_status: str,
    g5_status: str,
    g6_status: str,
    s14_status: str,
    s14_helper_status: str,
) -> Layer3G7EngineeringReadinessStatus:
    if missing_paths:
        return "fail"
    if {g1_status, g4_status, g5_status, g6_status, s14_status, s14_helper_status} <= {
        "pass"
    }:
        return "pass"
    return "fail"


def _snapshot_issue_codes(
    *,
    g5_readiness_status: str,
    g6_readiness_status: str,
    region_value_closure_status: str,
    missing_paths: tuple[str, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    if missing_paths:
        issues.append("layer3_g7_persisted_artifact_missing")
    if g5_readiness_status != "pass":
        issues.append("layer3_g7_g5_readiness_missing")
    if g6_readiness_status != "pass":
        issues.append("layer3_g7_g6_readiness_missing")
    if region_value_closure_status == "blocked_by_current_g5_unchanged_blocker":
        issues.append("layer3_g7_current_g5_unchanged_blocker")
    elif region_value_closure_status == "blocked_by_no_real_grounded_region_breadth":
        issues.append("layer3_g7_no_real_grounded_region_breadth")
    return tuple(dict.fromkeys(issues))


def _issue(code: str, path: str, message: str) -> Layer3G7ValidationIssue:
    return Layer3G7ValidationIssue(code=code, path=path, message=message)


def _candidate_from_row(
    *,
    region_ref: str,
    row: Mapping[str, object],
) -> Layer3G7RegionCaseCandidate:
    payload = dict(row)
    payload["region_ref"] = str(payload.get("region_ref") or region_ref)
    payload.setdefault("candidate_source", "external_candidate_input")
    payload.setdefault("may_not_use_for", G7_MAY_NOT_USE_FOR)
    return Layer3G7RegionCaseCandidate.model_validate(payload)


def _slug_ref(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")


def _g1_source_contract_refs(value: object) -> tuple[str, ...]:
    rows = _rows_from_payload(value)
    refs: list[str] = []
    for index, row in enumerate(rows):
        ref = (
            row.get("source_contract_ref")
            or row.get("grounded_source_contract_ref")
            or row.get("contract_ref")
            or row.get("contract_id")
            or row.get("source_contract_id")
            or f"repo://architecture/policy_design_case/layer3_g1_grounded_source_contracts.json#{index}"
        )
        refs.append(str(ref))
    if not refs and value:
        refs.append("repo://architecture/policy_design_case/layer3_g1_grounded_source_contracts.json")
    return tuple(dict.fromkeys(refs))


def _records_by_case_id(value: object) -> dict[str, Mapping[str, object]]:
    records: dict[str, Mapping[str, object]] = {}
    for row in _as_mapping_rows(value):
        case_id = row.get("case_id")
        if case_id is not None and str(case_id) not in records:
            records[str(case_id)] = row
    return records


def _build_grounding_matrix_row(
    *,
    candidate: Layer3G7RegionCaseCandidate,
    search_join: Layer3G7SearchRecallFreshnessJoin,
    g4_record: Mapping[str, object] | None,
    g5_record: Mapping[str, object] | None,
    g6_demand: Mapping[str, object],
    g6_audit: Mapping[str, object],
    gl_readiness: Mapping[str, object],
    gl_report: Mapping[str, object],
    s14_manifest: Mapping[str, object],
) -> Layer3G7RegionGroundingMatrixRow:
    del gl_readiness
    source_contract_refs = candidate.source_contract_refs or search_join.g1_source_contract_refs
    search_ledger_refs = _dedupe((*candidate.search_ledger_refs, *search_join.search_ledger_refs))
    g4_refs = _dedupe(
        (
            *candidate.g4_promotion_refs,
            *((g4_record or {}).get("promotion_record_id"),),
        )
    )
    g5_refs = _dedupe(
        (
            *candidate.g5_conversion_record_refs,
            *((g5_record or {}).get("conversion_record_id"),),
        )
    )
    g5_outcome = _optional_str((g5_record or {}).get("conversion_outcome"))
    grounding_disposition = _optional_str((g5_record or {}).get("grounding_disposition"))
    missing_blockers: list[str] = [*candidate.missing_ref_blockers]
    missing_limitations: list[str] = [*candidate.missing_ref_limitations]
    issue_codes: list[str] = []
    blockers: list[str] = [*candidate.blockers]
    limitations: list[str] = [*candidate.limitations]

    if not g5_refs:
        missing_blockers.append("missing:g5_conversion_record_ref")
        blockers.append("blocker://g7/missing-g5-conversion-record")
        issue_codes.append("layer3_g7_region_case_without_grounding_matrix")
    if not g4_refs:
        missing_blockers.append("missing:g4_promotion_record_ref")
        blockers.append("blocker://g7/missing-g4-promotion-record")
        issue_codes.append("layer3_g7_region_case_without_grounding_matrix")
    if not candidate.g6_request_refs and not candidate.g6_agent_refs:
        missing_limitations.append("missing:g6_case_specific_request_or_agent_ref")
        limitations.append("limitation://g7/g6-diagnostic-ref-only")
    if candidate.demand_refs and not candidate.accountable_principal_refs:
        issue_codes.append("layer3_g7_accountable_principal_missing")
    if g5_outcome == "unchanged_blocker":
        issue_codes.append("layer3_g7_current_g5_unchanged_blocker")
        blockers.append("blocker://g7/current-g5-unchanged-blocker")
        row_status: Layer3G7RowGroundingStatus = "blocked_current_g5_unchanged_blocker"
    elif not g5_refs or not g4_refs:
        row_status = (
            "control_plane_candidate"
            if candidate.candidate_source == "external_candidate_input"
            and candidate.search_ledger_refs
            and not candidate.demand_refs
            else "blocked_missing_grounding_matrix_refs"
        )
    elif grounding_disposition in {"grounded_limited", "grounded_abstention"}:
        row_status = grounding_disposition
    else:
        row_status = "control_plane_candidate"

    g6_diagnostic_refs = _dedupe(
        (
            g6_demand.get("demand_record_id"),
            g6_audit.get("audit_id"),
        )
    )
    s14_declared_refs = candidate.declared_envelope_refs or _as_str_tuple(
        s14_manifest.get("declared_operation_envelope_ref")
    )
    legal_refs = _as_str_tuple(gl_report.get("legal_authority_record_refs"))
    return Layer3G7RegionGroundingMatrixRow(
        case_id=candidate.case_id,
        region_ref=candidate.region_ref,
        candidate_source=candidate.candidate_source,
        row_grounding_status=row_status,
        envelope_posture=candidate.envelope_posture,
        source_contract_refs=source_contract_refs,
        search_ledger_refs=search_ledger_refs,
        search_authoritative_for=search_join.search_authoritative_for,
        search_may_not_use_for=search_join.search_may_not_use_for,
        g4_promotion_record_refs=g4_refs,
        g4_promotion_state=str((g4_record or {}).get("promotion_state") or "missing"),
        g5_conversion_record_refs=g5_refs,
        g5_conversion_outcome=g5_outcome,
        grounding_disposition=grounding_disposition,
        g6_request_refs=candidate.g6_request_refs,
        g6_agent_refs=candidate.g6_agent_refs,
        g6_diagnostic_refs=g6_diagnostic_refs,
        gl_legal_status="available" if legal_refs else "not_required",
        gl_legal_refs=legal_refs,
        s14_declared_envelope_refs=s14_declared_refs,
        s14_pending_feed_refs=("repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",),
        demand_refs=candidate.demand_refs,
        s12_voi_refs=candidate.s12_voi_refs,
        s3_demand_pull_refs=candidate.s3_demand_pull_refs,
        accountable_principal_refs=candidate.accountable_principal_refs,
        time_refs=candidate.time_refs,
        missing_ref_blockers=tuple(dict.fromkeys(missing_blockers)),
        missing_ref_limitations=tuple(dict.fromkeys(missing_limitations)),
        blockers=tuple(dict.fromkeys(blockers)),
        limitations=tuple(dict.fromkeys(limitations)),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _matrix_coverage_status(
    *,
    candidate_set: Layer3G7RegionCandidateSet,
    search_discovery_refs: tuple[str, ...],
    grounded_count: int,
) -> Layer3G7CoverageStatus:
    if grounded_count > 0:
        return "pass"
    if (
        candidate_set.coverage_authority_status == "control_plane_only"
        and not search_discovery_refs
    ):
        return "blocked_control_plane_only"
    if search_discovery_refs:
        return "blocked_search_control_plane_only"
    return "blocked_no_grounded_records"
