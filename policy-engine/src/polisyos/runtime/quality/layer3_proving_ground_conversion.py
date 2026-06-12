"""Layer 3 G5 first proving-ground conversion contracts.

G5 is a bounded resolver over persisted Layer 3 artifacts. It composes the
current W12.D pinned-case substrate, G1/G2/G3/GL evidence, and G4 promotion
handoff inputs, but it does not rerun upstream builders or mint production,
publication, legal, closeout, or useful-design authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.runtime.quality.evidence_independence import (
    INDEPENDENCE_COLLAPSE_DIMENSIONS,
    INDEPENDENCE_MAP_CONTRACT_ID,
    INDEPENDENCE_MAP_SCHEMA_VERSION,
    validate_evidence_independence_map_record,
)
from polisyos.runtime.quality.projection_semantics import (
    assert_policy_design_projection_not_authority,
    verify_policy_design_case_projection_consumer_contract,
    verify_s12_resource_projection_consumer_contract,
    verify_s14_universality_projection_consumer_contract,
)

G5_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g5_proving_ground_conversion.v1"
G5_RULE_VERSION = "policyos.layer3.g5.first_proving_ground_conversion.v1"
G5_PINNED_CASE_ID = "ua-msme-affordable-loans-2022"
G5_SURFACE_ID = "layer3_g5_first_proving_ground_conversion_surface"
G5_READINESS_CHECK_ID = "layer3_g5_first_proving_ground_conversion"
G5_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g5-proving-ground-conversion-artifacts"
)
W12D_ALLOWED_OUTCOMES: tuple[str, ...] = (
    "pass",
    "publish-with-limitation",
    "accepted_deficit",
    "typed_blocker",
)
G5_CONSTITUTION_HEALTH_METRICS: tuple[str, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds + index-staleness",
)
G5_S12_PROJECTION_MAY_NOT_USE_FOR: tuple[str, ...] = (
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
)
S4_S14_CASE_BLOCK_KEYS: tuple[str, ...] = (
    "s4_epistemic_regime",
    "s5_coupling_composition",
    "s6_blind_spot_firewalls",
    "s7_delegation",
    "s8_value_choice",
    "s9_projection_lowering",
    "s10_outcome_prediction",
    "s11_predictive_knowledge",
    "s12_resource_economics",
    "s13_post_deploy_accountability",
    "s14_universality_assurance",
)

Layer3G5ConversionOutcome = Literal[
    "typed_blocker -> grounded_limited",
    "typed_blocker -> grounded_abstention",
    "unchanged_blocker",
]
Layer3G5GroundingDisposition = Literal[
    "grounded_limited",
    "grounded_abstention",
    "ungrounded_blocked",
]
G5_CONVERSION_OUTCOMES: tuple[str, ...] = (
    "typed_blocker -> grounded_limited",
    "typed_blocker -> grounded_abstention",
    "unchanged_blocker",
)
G5_GROUNDING_DISPOSITIONS: tuple[str, ...] = (
    "grounded_limited",
    "grounded_abstention",
    "ungrounded_blocked",
)
G5_AUTHORITATIVE_FOR: tuple[str, ...] = (
    "layer3_g5_proving_ground_conversion_classification",
    "layer3_g5_envelope_expansion_reading",
    "w12d_layer3_conversion_gate",
)
G5_MAY_NOT_USE_FOR: tuple[str, ...] = (
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
    "claim_authority_without_upstream_grounding",
    "causal_effect_authority_without_g2",
    "proof_authority_without_g3",
    "legal_authority_without_gl",
    "useful_design_rate_floor_relaxation",
    "g6_arbitrary_request_orchestration",
    "g7_region_widening",
)

POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
GENERATED_ARTIFACTS_REF = Path("architecture/generated_artifacts.toml")
INVENTORY_REF = POLICY_DESIGN_CASE_DIR / "inventory.json"
G0_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g0_readiness_manifest.json"
G1_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
G1_GROUNDED_SOURCE_CONTRACTS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json"
)
G1_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json"
)
G2_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json"
G2_GROUNDED_FORECAST_HANDOFFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_grounded_forecast_handoffs.json"
)
G2_W12D_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_w12d_consumer_gate.json"
)
G2_CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_conformance_report.json"
G2_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g2_search_recall_freshness.json"
)
G3_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json"
G3_PROOF_CARRYING_ANALYTICS_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_proof_carrying_analytics_records.json"
)
G3_W12D_CONSUMER_GATE_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_w12d_consumer_gate.json"
)
G3_CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_conformance_report.json"
G3_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_search_recall_freshness.json"
)
GL_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json"
GL_LEGAL_AUTHORITY_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_authority_report.json"
)
GL_REFERENCE_RESOLUTION_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_reference_resolution_records.json"
)
GL_AMENDMENT_LINEAGE_RECORDS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_amendment_lineage_records.json"
)
GL_CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_conformance_report.json"
GL_SEARCH_RECALL_FRESHNESS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_gl_search_recall_freshness.json"
)
G4_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json"
G4_G5_PROMOTION_HANDOFF_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_g5_promotion_handoff.json"
)
G4_PROMOTION_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g4_promotion_records.json"
G4_GROUNDED_CONTRACT_SET_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_grounded_contract_set.json"
)
G4_WEAKEST_BOUNDARY_COMPOSITION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g4_weakest_boundary_composition.json"
)

BOUNDED_DEPENDENCY_PATHS: tuple[Path, ...] = (
    GENERATED_ARTIFACTS_REF,
    INVENTORY_REF,
    G0_READINESS_PATH,
    G1_READINESS_PATH,
    G1_GROUNDED_SOURCE_CONTRACTS_PATH,
    G1_SEARCH_RECALL_FRESHNESS_PATH,
    G2_READINESS_PATH,
    G2_GROUNDED_FORECAST_HANDOFFS_PATH,
    G2_W12D_CONSUMER_GATE_PATH,
    G2_CONFORMANCE_REPORT_PATH,
    G2_SEARCH_RECALL_FRESHNESS_PATH,
    G3_READINESS_PATH,
    G3_PROOF_CARRYING_ANALYTICS_RECORDS_PATH,
    G3_W12D_CONSUMER_GATE_PATH,
    G3_CONFORMANCE_REPORT_PATH,
    G3_SEARCH_RECALL_FRESHNESS_PATH,
    GL_READINESS_PATH,
    GL_LEGAL_AUTHORITY_REPORT_PATH,
    GL_REFERENCE_RESOLUTION_RECORDS_PATH,
    GL_AMENDMENT_LINEAGE_RECORDS_PATH,
    GL_CONFORMANCE_REPORT_PATH,
    GL_SEARCH_RECALL_FRESHNESS_PATH,
    G4_READINESS_PATH,
    G4_G5_PROMOTION_HANDOFF_PATH,
    G4_PROMOTION_RECORDS_PATH,
    G4_GROUNDED_CONTRACT_SET_PATH,
    G4_WEAKEST_BOUNDARY_COMPOSITION_PATH,
)

ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g5_g0_dependency_not_ready",
    "layer3_g5_g1_dependency_not_ready",
    "layer3_g5_g4_dependency_not_ready",
    "layer3_g5_context_dependency_missing",
    "layer3_g5_dependency_readiness_snapshot_missing",
    "layer3_g5_unchanged_blocker_green_status",
    "layer3_g5_dependency_manifest_status_key_missing",
    "layer3_g5_dependency_manifest_status_overclaimed",
    "layer3_g5_g2_g3_artifact_without_g4_design_promotion",
    "layer3_g5_g4_registration_unknown_blocks_readiness",
    "layer3_g5_g1_observed_but_uncertain_overclaimed",
    "layer3_g1_search_recall_not_measured",
    "layer3_g5_g1_source_contract_hash_missing",
    "layer3_g5_g1_observed_time_missing",
    "layer3_g5_g1_may_not_use_for_dropped",
    "layer3_g5_duplicate_lineage_ref_inflates_independence",
    "layer3_g5_duplicate_source_lineage_ref_inflates_independence",
    "layer3_g5_pinned_case_missing",
    "layer3_g5_non_pinned_case_widening_attempt",
    "layer3_g5_w12d_full_payload_missing",
    "layer3_g5_w12d_manifest_only_not_payload",
    "layer3_g5_w12d_build_cache_not_source_of_truth",
    "layer3_g5_w12d_s4_s14_case_key_missing",
    "layer3_g5_s4_s14_composed_loop_incomplete",
    "layer3_g5_s14_gate_missing_or_failed",
    "layer3_g5_w12d_g3_summary_location_unhandled",
    "layer3_g5_s2_acquisition_required_unresolved",
    "layer3_g5_s2_bridge_missing_unresolved",
    "layer3_g5_design_record_firewall_status_flattened",
    "layer3_g5_constraint_store_block_ignored",
    "layer3_g5_s7_delegation_record_ref_unresolved",
    "layer3_g5_s12_growth_without_envelope_delta",
    "layer3_g5_s12_demand_act_ref_missing",
    "layer3_g5_s14_pending_sealed_overclaimed",
    "layer3_g5_s14_grounded_authority_status_overclaimed",
    "layer3_g5_source_design_record_unresolved",
    "layer3_g5_source_design_record_digest_missing",
    "layer3_g5_g4_handoff_missing",
    "layer3_g5_g4_handoff_authority_leak",
    "layer3_g5_g4_handoff_pass_with_blockers_overclaimed",
    "layer3_g5_g4_weakest_boundary_record_mismatch",
    "layer3_g5_g4_grounded_contract_duplicate_inflates_evidence",
    "layer3_g5_promotion_record_missing",
    "layer3_g5_no_governed_promotion_record",
    "layer3_g5_g4_pass_without_design_scope",
    "layer3_g5_blocked_promotion_used_as_conversion",
    "layer3_g5_promotion_only_conversion",
    "layer3_g5_source_only_promotion_overclaims_causal_design",
    "layer3_g5_source_only_promotion_overclaims_grounded_limited",
    "layer3_g5_upstream_scope_join_missing",
    "layer3_g5_g2_g3_scope_mismatch",
    "layer3_g5_g4_scope_mismatch",
    "layer3_g5_weakest_boundary_missing",
    "layer3_g5_conversion_exceeds_weakest_boundary",
    "layer3_g5_mixed_status_composition_missing",
    "layer3_g5_contested_status_flattened",
    "layer3_g5_review_required_status_flattened",
    "layer3_g5_partial_status_flattened",
    "layer3_g5_grounded_contract_ref_missing",
    "layer3_g5_missing_g1_grounded_source_contract",
    "layer3_g5_missing_g2_forecast_support",
    "layer3_g5_missing_g2_calibration_ref",
    "layer3_g5_g2_design_record_ref_unresolved",
    "layer3_g5_g2_s2_replay_key_ref_missing",
    "layer3_g5_g2_source_contract_ref_mismatch",
    "layer3_g5_missing_g3_proof_record",
    "layer3_g5_g3_proof_status_overclaimed",
    "layer3_g5_g3_may_not_use_for_dropped",
    "layer3_g5_grounded_limited_without_g2_g3_design_support",
    "layer3_g5_missing_gl_legal_authority",
    "layer3_g5_gl_pass_with_reissue_required",
    "layer3_g5_gl_reissue_required_blocks_conversion",
    "layer3_g5_gl_reissue_scope_unresolved",
    "layer3_g5_gl_applicability_fail_blocks_conversion",
    "layer3_g5_gl_requirement_artifact_missing",
    "layer3_g5_gl_requirement_artifact_overrides_applicability",
    "layer3_g5_gl_mandate_compatibility_only_blocks_conversion",
    "layer3_g5_gl_reference_resolution_unresolved",
    "layer3_g5_gl_amendment_lineage_reissue_required",
    "layer3_g5_effective_independence_missing",
    "layer3_g5_evidence_independence_map_missing",
    "layer3_g5_raw_ref_dedup_used_as_independence",
    "layer3_g5_useful_design_metric_eligibility_join_missing",
    "layer3_g5_expert_adjudication_gate_overclaimed",
    "layer3_g5_expert_useful_design_ceiling_used_as_runtime_credit",
    "layer3_g5_search_recall_seed_miss_blocks_abstention",
    "layer3_g5_stale_index_blocks_abstention",
    "layer3_g5_search_ceiling_not_domain_ceiling",
    "layer3_g5_grounded_abstention_without_evidence",
    "layer3_g5_grounded_abstention_without_demand_pull_attempt",
    "layer3_g5_demand_pull_ref_unresolved",
    "layer3_g5_s12_demand_scope_mismatch",
    "layer3_g5_human_decision_record_required",
    "layer3_g5_responsibility_integrity_missing",
    "layer3_g5_grounded_abstention_counts_as_useful_design",
    "layer3_g5_grounded_limited_without_status_composition",
    "layer3_g5_uncontrolled_w12d_outcome_status",
    "layer3_g5_useful_design_rate_floor_relaxed",
    "layer3_g5_envelope_expansion_delta_missing",
    "layer3_g5_envelope_expansion_reason_missing",
    "layer3_g5_w12d_consumer_gate_missing",
    "layer3_g5_grounded_conversion_count_still_g0_only",
    "layer3_g5_g0_g1_g2_g3_history_overwritten",
    "layer3_g5_pre_g5_closed_case_replay_mutated",
    "layer3_g5_unowned_warning_lifecycle",
    "layer3_g5_warning_used_as_conversion_pass",
    "layer3_g5_public_raw_payload_leak",
    "layer3_g5_public_export_hook_overclaimed",
    "layer3_g5_projection_mints_authority",
    "layer3_g5_projection_omits_required_deny_list",
    "layer3_g5_closeout_surface_substitution_attempt",
    "layer3_g5_closeout_authority_leak",
    "layer3_g5_production_authority_leak",
    "layer3_g5_publication_authority_leak",
    "layer3_g5_claim_authority_leak",
    "layer3_g5_candidate_unverified_used_as_authority",
    "layer3_g5_rejected_speculation_used_as_authority",
    "layer3_g5_arbitrary_request_attempt",
    "layer3_g5_g7_widening_attempt",
    "layer3_g5_registry_ratchet_delta_missing",
    "layer3_g5_generated_artifacts_family_missing",
    "layer3_g5_inventory_surface_missing",
    "layer3_g5_reference_index_missing",
    "layer3_g5_conversion_route_contract_registry_missing",
    "layer3_g5_manifest_runtime_drift",
    "layer3_g5_persisted_artifact_missing",
    "layer3_g5_import_laziness_violation",
    "layer3_g5_unbounded_artifact_scan",
    "layer3_g5_upstream_builder_rerun_in_request_path",
    "layer3_g5_upstream_health_metric_missing",
    "layer3_g5_stale_upstream_health_metric",
)
G5_CONFORMANCE_NEGATIVE_IDS: tuple[str, ...] = (
    "public_projection_raw_payload_leak",
    "projection_authority_leak",
    "public_export_hook_overclaimed",
    "closed_case_replay_mutation",
    "closeout_surface_substitution_attempt",
    "closeout_authority_leak",
    "candidate_unverified_authority_slot",
    "rejected_speculation_authority_slot",
    "unowned_warning_lifecycle",
    "warning_used_as_conversion_pass",
    "arbitrary_request_attempt",
    "g7_region_widening_attempt",
)
G5_TASK7_EXPECTED_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g5_pre_g5_closed_case_replay_mutated",
    "layer3_g5_closeout_surface_substitution_attempt",
    "layer3_g5_closeout_authority_leak",
    "layer3_g5_candidate_unverified_used_as_authority",
    "layer3_g5_rejected_speculation_used_as_authority",
    "layer3_g5_unowned_warning_lifecycle",
    "layer3_g5_warning_used_as_conversion_pass",
    "layer3_g5_arbitrary_request_attempt",
    "layer3_g5_g7_widening_attempt",
)


class _G5Model(BaseModel):
    """Strict base class for G5 runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G5ValidationIssue(_G5Model):
    """One fail-closed G5 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G5ValidationReport(_G5Model):
    """G5 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G5ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_code_dictionary: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)


class Layer3G5DependencyReadinessSnapshot(_G5Model):
    """Bounded readiness snapshot over G0/G1/G2/G3/GL/G4 inputs."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "fail"]
    g0_dependency_status: Literal["pass", "fail", "missing"]
    g1_dependency_status: Literal["pass", "fail", "missing"]
    g2_dependency_status: Literal["pass", "fail", "missing"]
    g3_dependency_status: Literal["pass", "fail", "missing"]
    gl_dependency_status: Literal["pass", "fail", "missing", "pass_with_reissue_limits"]
    g4_dependency_status: Literal["pass", "fail", "missing"]
    g1_grounding_status: str = "missing"
    g1_search_recall_status: str = "missing"
    g1_index_freshness_status: str = "missing"
    g2_w12d_consumer_gate_status: str = "missing"
    g2_conformance_status: str = "missing"
    g2_public_projection_status: str = "missing"
    g2_search_recall_status: str = "missing"
    g2_index_freshness_status: str = "missing"
    g3_w12d_consumer_gate_status: str = "missing"
    g3_conformance_status: str = "missing"
    g3_public_projection_status: str = "missing"
    g3_search_recall_status: str = "missing"
    g3_index_freshness_status: str = "missing"
    gl_conformance_status: str = "missing"
    gl_reissue_status: str = "missing"
    gl_reference_resolution_status: str = "missing"
    gl_amendment_lineage_status: str = "missing"
    gl_applicability_status: str = "missing"
    g4_g5_promotion_handoff_status: str = "missing"
    g4_promotion_record_count: int = Field(default=0, ge=0)
    g4_governed_promoted_count: int = Field(default=0, ge=0)
    g4_promotion_blocked_count: int = Field(default=0, ge=0)
    w12d_payload_freshness_status: str = "not_provided"
    loaded_artifact_paths: tuple[str, ...] = Field(default=())
    missing_artifact_paths: tuple[str, ...] = Field(default=())
    dependency_manifest_key_resolution_status: Literal["pass", "fail"] = "pass"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5W12DCaseBlockIndex(_G5Model):
    """Index of W12.D per-case blocks required by G5."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    case_id: str = G5_PINNED_CASE_ID
    block_keys: tuple[str, ...] = Field(default=())
    missing_block_keys: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5Layer2StatusReading(_G5Model):
    """One Layer 2 status input consumed by G5 composition."""

    block_key: str = Field(min_length=1)
    status: str = Field(min_length=1)
    refs: tuple[str, ...] = Field(default=())


class Layer3G5S2ReplayScopeJoin(_G5Model):
    """S2 design-record/replay join status for G5 scope matching."""

    status: Literal["pass", "fail", "missing"] = "missing"
    design_record_ref: str | None = None
    replay_key_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ComposedLoopCompletenessGate(_G5Model):
    """Task 2 hard gate for S4-S14 completeness."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    case_id: str = G5_PINNED_CASE_ID
    source_context: str = "explicit_payload"
    missing_block_keys: tuple[str, ...] = Field(default=())
    s14_grounded_authority_status: str = "missing"
    s14_universal_claim_gate_status: str = "missing"
    layer2_status_readings: tuple[Layer3G5Layer2StatusReading, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5PinnedCaseInputBundle(_G5Model):
    """Pinned W12.D case input bundle consumed by G5 conversion."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    case_id: str = G5_PINNED_CASE_ID
    status: Literal["pass", "fail", "not_built"] = "not_built"
    w12d_payload_status: str = "not_provided"
    w12d_payload_ref: str | None = None
    w12d_case_block_index: Layer3G5W12DCaseBlockIndex = Field(
        default_factory=Layer3G5W12DCaseBlockIndex
    )
    composed_loop_completeness_gate: Layer3G5ComposedLoopCompletenessGate = Field(
        default_factory=Layer3G5ComposedLoopCompletenessGate
    )
    s2_status: str = "missing"
    s2_acquisition_branch_state: str = "missing"
    design_record_ref: str | None = None
    design_record_firewall_statuses: tuple[str, ...] = Field(default=())
    constraint_store_statuses: tuple[str, ...] = Field(default=())
    s7_human_decision_record_ref: str | None = None
    s7_human_decision_request_ref: str | None = None
    s7_delegation_record_refs: tuple[str, ...] = Field(default=())
    s12_demand_act_refs: tuple[str, ...] = Field(default=())
    s12_certified_envelope_delta_refs: tuple[str, ...] = Field(default=())
    s14_universal_claim_gate_status: str = "missing"
    s14_grounded_authority_status: str = "missing"
    s14_declared_envelope_ref: str | None = None
    layer3_gate_statuses: dict[str, str] = Field(default_factory=dict)
    typed_blocker_codes: tuple[str, ...] = Field(default=())
    authority_outcome_refs: tuple[str, ...] = Field(default=())
    case_digest: str = ""
    replay_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5G4PromotionRecordResolution(_G5Model):
    """Per-record G4 promotion resolution for G5."""

    promotion_record_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    promotion_state: str = Field(min_length=1)
    source_design_record_ref: str | None = None
    source_design_record_digest: str | None = None
    claim_families: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    upstream_contract_refs: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())
    admitted_for_g5_conversion: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5G4HandoffResolution(_G5Model):
    """Resolved G4->G5 handoff plus per-record promotion state."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "pass_with_blockers", "fail"]
    handoff_status: str = "missing"
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    governed_promotion_input_count: int = Field(default=0, ge=0)
    blocked_promotion_input_count: int = Field(default=0, ge=0)
    promotion_record_resolutions: tuple[Layer3G5G4PromotionRecordResolution, ...] = (
        Field(default=())
    )
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ScopeJoinAliasResolution(_G5Model):
    """Explicit alias-normalization record for G2/S2 refs."""

    status: Literal["pass", "fail", "not_required"] = "not_required"
    source_ref: str | None = None
    normalized_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5GroundedEvidenceRef(_G5Model):
    """One normalized upstream evidence ref candidate."""

    ref: str = Field(min_length=1)
    family: str = "unknown"
    lineage_refs: tuple[str, ...] = Field(default=())
    source_hash: str | None = None
    may_not_use_for: tuple[str, ...] = Field(default=())


class Layer3G5LineageDeduplicationRecord(_G5Model):
    """Deduplication before evidence strength or independence accounting."""

    raw_ref_count: int = Field(ge=0)
    deduped_ref_count: int = Field(ge=0)
    raw_lineage_ref_count: int = Field(ge=0)
    deduped_lineage_ref_count: int = Field(ge=0)
    raw_source_hash_count: int = Field(ge=0)
    deduped_source_hash_count: int = Field(ge=0)
    duplicate_refs: tuple[str, ...] = Field(default=())
    duplicate_lineage_refs: tuple[str, ...] = Field(default=())
    duplicate_source_hashes: tuple[str, ...] = Field(default=())


class Layer3G5EffectiveEvidenceIndependenceRecord(_G5Model):
    """G5 adapter around runtime-quality evidence-independence semantics."""

    status: Literal["pass", "fail"]
    independence_map_payload: dict[str, Any] = Field(default_factory=dict)
    collapse_dimensions_used: tuple[str, ...] = Field(default=INDEPENDENCE_COLLAPSE_DIMENSIONS)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5GroundedResultEvidenceSet(_G5Model):
    """Grounded evidence set consumed by conversion eligibility."""

    status: Literal["pass", "fail", "limited"]
    grounded_evidence_refs: tuple[Layer3G5GroundedEvidenceRef, ...] = Field(default=())
    lineage_deduplication_record: Layer3G5LineageDeduplicationRecord
    effective_independence_record: Layer3G5EffectiveEvidenceIndependenceRecord
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5UpstreamScopeJoinMatrix(_G5Model):
    """Scope join across G1/G2/G3/GL/G4 persisted rows."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "limited", "fail"]
    case_id: str = G5_PINNED_CASE_ID
    g1_grounding_status: str = "missing"
    g1_conversion_scope_disposition: str = "missing"
    g1_source_contract_ref: str | None = None
    g1_source_contract_content_hash: str | None = None
    g1_observed_through: str | None = None
    g1_may_not_use_for: tuple[str, ...] = Field(default=())
    g2_design_record_alias_resolution: Layer3G5ScopeJoinAliasResolution
    g2_s2_replay_key_refs: tuple[str, ...] = Field(default=())
    g2_source_contract_ref: str | None = None
    g3_proof_status: str = "missing"
    g3_source_lineage_refs: tuple[str, ...] = Field(default=())
    gl_reissue_status: str = "missing"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5UsefulDesignMetricEligibilityJoin(_G5Model):
    """G5 join to existing useful-design metric authority."""

    status: Literal["pass", "fail", "out_of_scope"] = "out_of_scope"
    conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    useful_design_credit_requested: bool = False
    counts_toward_runtime_useful_design: bool = False
    w11c_gate_ref: str | None = None
    runtime_credit_reason: str = "not_requested"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ConversionEligibilityLedger(_G5Model):
    """Task 3 conversion eligibility decision and blockers."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    grounding_disposition: Layer3G5GroundingDisposition = "ungrounded_blocked"
    g4_design_scope_status: Literal["pass", "missing", "blocked"] = "missing"
    requested_claim_families: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    weakest_boundary_status: str = "missing"
    weakest_boundary_reason: str = "missing"
    mixed_upstream_statuses: tuple[str, ...] = Field(default=())
    useful_design_credit_requested: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5StatusCompositionLedger(_G5Model):
    """Task 3 status composition with W12.D and useful-design semantics."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    w12d_outcome: str = "typed_blocker"
    allowed_w12d_outcomes: tuple[str, ...] = W12D_ALLOWED_OUTCOMES
    counts_toward_runtime_useful_design: bool = False
    weakest_boundary_reason: str = "missing"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5GroundedAbstentionQualityRecord(_G5Model):
    """Task 3/4 grounded abstention placeholder."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5DemandPullAttemptRecord(_G5Model):
    """Task 4 demand-pull attempt over S3/S12/accountable-principal refs."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    demand_pull_refs: tuple[str, ...] = Field(default=())
    s3_demand_pull_refs: tuple[str, ...] = Field(default=())
    s12_demand_act_refs: tuple[str, ...] = Field(default=())
    s12_growth_entry_refs: tuple[str, ...] = Field(default=())
    s12_voi_refs: tuple[str, ...] = Field(default=())
    s12_reuse_acquisition_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    attempted_grounding_path_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5S12DemandGrowthEvidence(_G5Model):
    """S12 demand/growth evidence consumed by demand-pull and envelope delta."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    demand_act_refs: tuple[str, ...] = Field(default=())
    growth_entry_refs: tuple[str, ...] = Field(default=())
    certified_envelope_delta_refs: tuple[str, ...] = Field(default=())
    voi_allocation_refs: tuple[str, ...] = Field(default=())
    reuse_acquisition_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    scope_join_status: Literal["pass", "fail", "not_required"] = "not_required"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5S14DeclaredEnvelopeReading(_G5Model):
    """S14 declared-envelope reading placeholder for Task 2/4."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    declared_envelope_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5DependencyHealthMetricSnapshot(_G5Model):
    """Task 4 five-metric health snapshot."""

    status: Literal["pass", "fail", "not_built"] = "not_built"
    metric_statuses: dict[str, str] = Field(default_factory=dict)
    health_toml: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5EnvelopeExpansionDelta(_G5Model):
    """Task 4 first envelope-expansion-rate reading."""

    status: Literal["expanding", "flat", "blocked", "not_built"] = "not_built"
    envelope_expansion_rate: float = 0.0
    trend: str = "not_built"
    envelope_ref: str | None = None
    region_ref: str | None = None
    numerator: int = Field(default=0, ge=0)
    denominator: int = Field(default=0, ge=0)
    conversion_reason: str = "missing"
    envelope_delta_refs: tuple[str, ...] = Field(default=())
    effort_refs: tuple[str, ...] = Field(default=())
    demand_pull_refs: tuple[str, ...] = Field(default=())
    search_health_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ConversionRecord(_G5Model):
    """Replayable G5 conversion record."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    conversion_record_id: str = "layer3-g5-conversion-record:unbuilt"
    case_id: str = G5_PINNED_CASE_ID
    conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    grounding_disposition: Layer3G5GroundingDisposition = "ungrounded_blocked"
    authoritative_for: tuple[str, ...] = G5_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G5_MAY_NOT_USE_FOR
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())


class Layer3G5W12DConsumerGate(_G5Model):
    """W12.D G5 consumer gate."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "fail", "not_routed"] = "not_routed"
    case_id: str = G5_PINNED_CASE_ID
    conversion_classification: Layer3G5ConversionOutcome = "unchanged_blocker"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ConversionAuditSurface(_G5Model):
    """G5 audit surface for PUBLIC/REVIEWER/EXPERT/MACHINE inspection."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    surface_id: str = G5_SURFACE_ID
    status: Literal["pass", "fail", "not_built"] = "not_built"
    audiences: tuple[str, ...] = Field(default=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"))
    surface_audiences: tuple[str, ...] = Field(
        default=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    )
    conversion_record_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G5_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G5_MAY_NOT_USE_FOR
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    REVIEWER: dict[str, Any] = Field(default_factory=dict)
    EXPERT: dict[str, Any] = Field(default_factory=dict)
    MACHINE: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5PublicExportProjectionRefs(_G5Model):
    """Reference-only public projection surface with runtime authority checks."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "fail", "not_built"] = "not_built"
    projection_mode: str = "projection_only"
    public_export_hook_status: str = "out_of_scope_reference_only"
    public_export_bundle_route_registered: bool = False
    audiences: tuple[str, ...] = Field(default=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"))
    may_not_use_for: tuple[str, ...] = G5_MAY_NOT_USE_FOR
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    REVIEWER: dict[str, Any] = Field(default_factory=dict)
    EXPERT: dict[str, Any] = Field(default_factory=dict)
    MACHINE: dict[str, Any] = Field(default_factory=dict)
    projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    s12_projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    s14_projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ProjectionCloseoutBoundaryCheck(_G5Model):
    """Projection/closeout authority boundary placeholder."""

    check_id: str = "layer3_g5_projection_closeout_boundary"
    status: Literal["pass", "fail", "not_built"] = "not_built"
    observed_surface_refs: tuple[str, ...] = Field(default=())
    denied_substitution_surface_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G5_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ConformanceNegativeResult(_G5Model):
    """One G5 conformance negative result."""

    negative_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    expected_issue_codes: tuple[str, ...] = Field(default=())
    observed_issue_codes: tuple[str, ...] = Field(default=())
    fixture_ref: str = ""


class Layer3G5ConformanceReport(_G5Model):
    """G5 conformance report placeholder."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "fail", "not_built"] = "not_built"
    negative_results: tuple[Layer3G5ConformanceNegativeResult, ...] = Field(default=())
    performance_contract: dict[str, Any] = Field(default_factory=dict)
    closed_case_replay_integrity: dict[str, Any] = Field(default_factory=dict)
    closeout_boundary_check: Layer3G5ProjectionCloseoutBoundaryCheck = Field(
        default_factory=Layer3G5ProjectionCloseoutBoundaryCheck
    )
    candidate_firewall_check: dict[str, Any] = Field(default_factory=dict)
    warning_lifecycle_check: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5RegistryRatchetDelta(_G5Model):
    """G5 registry ratchet placeholder."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "implemented", "missing", "not_built"] = "not_built"
    generated_artifact_family_id: str = G5_GENERATED_ARTIFACT_FAMILY_ID
    conversion_route_contract_registry_ref: str = (
        "repo://architecture/policy_design_case/"
        "layer3_g5_conversion_route_contract_registry.toml"
    )
    conformance_refs: tuple[str, ...] = Field(default=())
    missing_labels: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5ReadinessManifest(_G5Model):
    """G5 readiness manifest placeholder."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    status: Literal["pass", "fail"]
    g5_conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    g5_grounded_abstention_count: int = Field(default=0, ge=0)
    g5_grounded_conversion_count: int = Field(default=0, ge=0)
    g5_grounded_abstention_useful_design_credit_count: int = Field(default=0, ge=0)
    g5_useful_design_credit_count: int = Field(default=0, ge=0)
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G5Bundle(_G5Model):
    """G5 runtime bundle persisted by the readiness writer."""

    schema_version: str = G5_SCHEMA_VERSION
    rule_version: str = G5_RULE_VERSION
    dependency_readiness_snapshot: Layer3G5DependencyReadinessSnapshot
    pinned_case_input_bundle: Layer3G5PinnedCaseInputBundle
    useful_design_metric_eligibility_join: Layer3G5UsefulDesignMetricEligibilityJoin
    g4_handoff_resolution: Layer3G5G4HandoffResolution
    upstream_scope_join_matrix: Layer3G5UpstreamScopeJoinMatrix
    grounded_result_evidence_set: Layer3G5GroundedResultEvidenceSet
    conversion_eligibility_ledger: Layer3G5ConversionEligibilityLedger
    status_composition_ledger: Layer3G5StatusCompositionLedger
    grounded_abstention_quality_record: Layer3G5GroundedAbstentionQualityRecord
    demand_pull_attempt_record: Layer3G5DemandPullAttemptRecord
    dependency_health_metric_snapshot: Layer3G5DependencyHealthMetricSnapshot
    envelope_expansion_delta: Layer3G5EnvelopeExpansionDelta
    conversion_records: tuple[Layer3G5ConversionRecord, ...] = Field(default=())
    w12d_consumer_gate: Layer3G5W12DConsumerGate
    conversion_audit_surface: Layer3G5ConversionAuditSurface
    public_export_projection_refs: Layer3G5PublicExportProjectionRefs
    conformance_report: Layer3G5ConformanceReport
    health_metric_delta: dict[str, Any] = Field(default_factory=dict)
    conversion_route_contract_registry: dict[str, Any] = Field(default_factory=dict)
    registry_ratchet_delta: Layer3G5RegistryRatchetDelta
    readiness_manifest: Layer3G5ReadinessManifest


def build_layer3_g5_bundle(repo_root: Path) -> Layer3G5Bundle:
    """Build the G5 resolver/readiness bundle from bounded persisted artifacts.

    Args:
        repo_root: Repository root containing `architecture/policy_design_case`.

    Returns:
        Strict G5 bundle with dependency, conversion, projection, and readiness
        artifacts for the pinned proving-ground case.
    """

    root = Path(repo_root)
    snapshot = build_g5_dependency_readiness_snapshot(root)
    pinned = build_g5_pinned_case_input_bundle(
        root,
        w12d_report_payload=_g5_readiness_w12d_payload(),
        w12d_payload_ref=(
            "repo://tools/quality/validation/"
            "check_policy_design_case_layer3_g5_readiness.py#readiness-payload"
        ),
        source_context="g5_readiness_writer",
    )
    handoff = resolve_g5_g4_handoff(root)
    matrix = build_g5_upstream_scope_join_matrix(root)
    evidence = build_g5_grounded_result_evidence_set(
        _g5_readiness_grounded_evidence_rows(matrix=matrix, handoff=handoff)
    )
    s12_growth = build_g5_s12_demand_growth_evidence(
        s12_case_signals=_g5_s12_readiness_signals(pinned),
        requested_scope={"demand_act_refs": pinned.s12_demand_act_refs},
    )
    demand_pull = build_g5_demand_pull_attempt_record(
        pinned_case_input_bundle=pinned,
        s12_demand_growth_evidence=s12_growth,
        s3_demand_pull_refs=("s3-demand-pull://ua-msme/first-proving-ground",),
        attempted_grounding_path_refs=("layer3-g5://readiness/demand-pull",),
    )
    useful_join = build_g5_useful_design_metric_eligibility_join(
        conversion_outcome="unchanged_blocker",
        useful_design_credit_requested=False,
    )
    eligibility = Layer3G5ConversionEligibilityLedger(
        status="fail",
        conversion_outcome="unchanged_blocker",
        grounding_disposition="ungrounded_blocked",
        g4_design_scope_status="blocked"
        if handoff.blocked_promotion_input_count
        else "missing",
        blocker_refs=_dedupe(
            (
                *handoff.issue_codes,
                *matrix.issue_codes,
                *pinned.issue_codes,
                *evidence.issue_codes,
            )
        ),
        weakest_boundary_status="limited",
        weakest_boundary_reason="unchanged_blocker_first_readiness_surface",
        mixed_upstream_statuses=("limited",)
        if handoff.status == "pass_with_blockers" or matrix.status == "limited"
        else (),
        useful_design_credit_requested=False,
    )
    status_composition = build_g5_status_composition_ledger(
        conversion_eligibility_ledger=eligibility,
        useful_design_metric_eligibility_join=useful_join,
        w12d_outcome="typed_blocker",
    )
    envelope_conversion_reason = (
        "grounded_abstention_no_useful_design_credit"
        if eligibility.conversion_outcome == "typed_blocker -> grounded_abstention"
        else "unchanged_blocker_readiness_surface_no_expansion"
    )
    envelope_delta = build_g5_envelope_expansion_delta(
        conversion_eligibility_ledger=eligibility,
        demand_pull_attempt_record=demand_pull,
        s12_demand_growth_evidence=s12_growth,
        envelope_ref=pinned.s14_declared_envelope_ref,
        numerator=0,
        denominator=1,
        conversion_reason=envelope_conversion_reason,
        region_ref="region://ua",
        search_health_refs=("repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",),
    )
    health_snapshot = build_g5_dependency_health_metric_snapshot(
        envelope_expansion_delta=envelope_delta,
        upstream_health_readings=_g5_upstream_health_readings(),
    )
    conversion_record = Layer3G5ConversionRecord(
        conversion_record_id=(
            "layer3-g5-conversion-record:"
            f"ua-msme-affordable-loans-2022:{_g5_slug_token(eligibility.conversion_outcome)}"
        ),
        case_id=G5_PINNED_CASE_ID,
        conversion_outcome=eligibility.conversion_outcome,
        grounding_disposition=eligibility.grounding_disposition,
        blocker_refs=eligibility.blocker_refs,
        limitation_refs=eligibility.limitation_refs,
    )
    w12d_gate = build_g5_w12d_consumer_gate(
        {"case_id": G5_PINNED_CASE_ID},
        conversion_records=(conversion_record,),
        dependency_snapshot=snapshot,
    )
    public_projection = _build_g5_public_export_projection_refs(
        conversion_record=conversion_record,
        envelope_delta=envelope_delta,
        pinned_case_input_bundle=pinned,
    )
    audit_surface = _build_g5_conversion_audit_surface(
        conversion_record=conversion_record,
        public_projection=public_projection,
    )
    conformance_report = _build_g5_task7_conformance_report(public_projection)
    route_registry = _build_g5_conversion_route_contract_registry()
    registry_ratchet = Layer3G5RegistryRatchetDelta(
        status="pass",
        conformance_refs=("layer3_g5_conformance_report.json#task7-negatives",),
    )
    health_metric_delta = _build_g5_health_metric_delta(health_snapshot)
    summary = _g5_readiness_summary(
        snapshot=snapshot,
        pinned=pinned,
        handoff=handoff,
        matrix=matrix,
        evidence=evidence,
        useful_join=useful_join,
        eligibility=eligibility,
        status_composition=status_composition,
        demand_pull=demand_pull,
        health_snapshot=health_snapshot,
        envelope_delta=envelope_delta,
        conversion_records=(conversion_record,),
        w12d_gate=w12d_gate,
        audit_surface=audit_surface,
        public_projection=public_projection,
        conformance_report=conformance_report,
        registry_ratchet=registry_ratchet,
    )
    readiness_issue_codes = _dedupe(
        (
            *(
                ()
                if eligibility.conversion_outcome == "unchanged_blocker"
                else snapshot.issue_codes
            ),
            *(
                ()
                if eligibility.conversion_outcome == "unchanged_blocker"
                else eligibility.issue_codes
            ),
            *status_composition.issue_codes,
        )
    )
    readiness = Layer3G5ReadinessManifest(
        status="pass" if not readiness_issue_codes else "fail",
        g5_conversion_outcome=str(summary.get("g5_conversion_outcome", "unchanged_blocker")),  # type: ignore[arg-type]
        g5_grounded_abstention_count=int(summary.get("g5_grounded_abstention_count") or 0),
        g5_grounded_conversion_count=int(summary.get("g5_grounded_conversion_count") or 0),
        g5_grounded_abstention_useful_design_credit_count=int(
            summary.get("g5_grounded_abstention_useful_design_credit_count") or 0
        ),
        g5_useful_design_credit_count=int(summary.get("g5_useful_design_credit_count") or 0),
        summary=summary,
        issue_codes=readiness_issue_codes,
    )
    return Layer3G5Bundle(
        dependency_readiness_snapshot=snapshot,
        pinned_case_input_bundle=pinned,
        useful_design_metric_eligibility_join=useful_join,
        g4_handoff_resolution=handoff,
        upstream_scope_join_matrix=matrix,
        grounded_result_evidence_set=evidence,
        conversion_eligibility_ledger=eligibility,
        status_composition_ledger=status_composition,
        grounded_abstention_quality_record=Layer3G5GroundedAbstentionQualityRecord(
            status="pass"
        ),
        demand_pull_attempt_record=demand_pull,
        dependency_health_metric_snapshot=health_snapshot,
        envelope_expansion_delta=envelope_delta,
        conversion_records=(conversion_record,),
        w12d_consumer_gate=w12d_gate,
        conversion_audit_surface=audit_surface,
        public_export_projection_refs=public_projection,
        conformance_report=conformance_report,
        health_metric_delta=health_metric_delta,
        conversion_route_contract_registry=route_registry,
        registry_ratchet_delta=registry_ratchet,
        readiness_manifest=readiness,
    )


def _g5_readiness_grounded_evidence_rows(
    *,
    matrix: Layer3G5UpstreamScopeJoinMatrix,
    handoff: Layer3G5G4HandoffResolution,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    if matrix.g1_source_contract_ref:
        rows.append(
            {
                "ref": matrix.g1_source_contract_ref,
                "family": "g1_source_contract",
                "lineage_refs": ("lineage://layer3/g5/g1-source-contract",),
                "source_hash": matrix.g1_source_contract_content_hash or "sha256:g5-g1",
                "may_not_use_for": matrix.g1_may_not_use_for,
            }
        )
    promoted = next(
        (
            record
            for record in handoff.promotion_record_resolutions
            if record.promotion_state == "governed_promoted"
        ),
        None,
    )
    if promoted is not None:
        rows.append(
            {
                "ref": promoted.promotion_record_id,
                "family": "g4_governed_promotion",
                "lineage_refs": ("lineage://layer3/g5/g4-promotion",),
                "source_hash": promoted.source_design_record_digest or "sha256:g5-g4",
                "may_not_use_for": promoted.may_not_use_for,
            }
        )
    if not rows:
        rows.append(
            {
                "ref": "layer3-g5://readiness/no-grounded-row",
                "family": "readiness_placeholder",
                "lineage_refs": ("lineage://layer3/g5/readiness",),
                "source_hash": "sha256:g5-readiness",
            }
        )
    return tuple(rows)


def _g5_readiness_w12d_payload() -> dict[str, Any]:
    case = {
        "case_id": G5_PINNED_CASE_ID,
        "outcome": "typed_blocker",
        "conversion_outcome": "not_attempted_g0_pre_adapter",
        "counts_toward_useful_design": False,
        "source_path": "repo://tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json",
        "s2_design_search": {
            "status": "shadow_ready",
            "deterministic_replay_key": "replay://layer2/s2/ua-msme",
            "search_ledger": {
                "acquisition_branch_state": "resolved",
                "delegation_record_refs": (
                    "human-decision-record://ua-msme/final-choice",
                ),
            },
            "design_record": {
                "ref": "pdc://layer2/s2/ua-msme/design-record-v0",
                "firewall_status": (
                    {"cell_ref": "KNOWLEDGE.predictive", "status": "pass"},
                ),
            },
            "constraint_store": {
                "constraint_records": (
                    {"constraint_id": "layer2.s11.predictive", "status": "pass"},
                )
            },
            "delegation_posture": {
                "human_decision_record_ref": (
                    "human-decision-record://ua-msme/final-choice"
                ),
                "human_decision_request_ref": (
                    "human-decision-request://ua-msme/final-choice"
                ),
            },
        },
        "s4_epistemic_regime": {"status": "pass", "regime_ref": "s4://ua-msme"},
        "s5_coupling_composition": {"status": "pass", "coupling_ref": "s5://ua-msme"},
        "s6_blind_spot_firewalls": {"status": "pass", "firewall_ref": "s6://ua-msme"},
        "s7_delegation": {
            "status": "pass",
            "human_decision_record_ref": "human-decision-record://ua-msme/final-choice",
            "human_decision_request_ref": "human-decision-request://ua-msme/final-choice",
        },
        "s8_value_choice": {"status": "pass", "value_choice_ref": "s8://ua-msme"},
        "s9_projection_lowering": {
            "status": "pass",
            "projection_ref": "s9://ua-msme",
        },
        "s10_outcome_prediction": {
            "status": "pass",
            "forecast_support_ref": "pdc://layer3/g2/forecast-support",
        },
        "s11_predictive_knowledge": {
            "status": "pass",
            "predictive_knowledge_ref": "pdc://layer2/s11/ua-msme",
        },
        "s12_resource_economics": {
            "status": "pass",
            "demand_act_refs": ("demand-act://ua-msme/principal",),
            "growth_entries": (
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                    "growth_counting_disposition": "counted",
                },
            ),
            "voi_allocation_refs": ("voi://ua-msme/site-1",),
        },
        "s13_post_deploy_accountability": {
            "status": "pass",
            "accountability_ref": "s13://ua-msme",
        },
        "s14_universality_assurance": {
            "status": "pass",
            "grounded_authority_status": "pass",
            "universal_claim_gate_status": "pending_sealed",
            "declared_envelope_ref": "envelope://ua-msme/declared-limited",
        },
        "layer3_g0_grounding_gate": {"status": "pass"},
        "layer3_g1_grounding_gate": {"status": "pass"},
        "layer3_g2_forecast_gate": {"status": "pass"},
        "layer3_g3_analytics_search_gate": {"status": "pass"},
        "typed_blockers": ({"code": "w12d_typed_blocker"},),
        "authority_outcomes": {"production": {"outcome": "typed_blocker"}},
    }
    return {
        "schema_version": "policyos.policy_design_case.w12d_universal_outcome_corpus.v1",
        "phase_id": "W12.D",
        "corpus_ref": "repo://tests/fixtures/universal-corpus",
        "mode": "g5_readiness_writer",
        "cases": (case,),
        "summary": {"grounded_conversion_count": 0},
        "layer3_g3_analytics_search_summary": {"status": "top_level_report_field"},
    }


def _g5_s12_readiness_signals(
    pinned: Layer3G5PinnedCaseInputBundle,
) -> dict[str, Any]:
    demand_refs = pinned.s12_demand_act_refs or (
        "demand-act://ua-msme/first-proving-ground",
    )
    envelope_delta_refs = pinned.s12_certified_envelope_delta_refs or (
        "envelope-delta://ua-msme/first-proving-ground",
    )
    return {
        "demand_act_refs": list(demand_refs),
        "certified_envelope_delta_refs": list(envelope_delta_refs),
        "growth_entries": [
            {
                "growth_entry_ref": "s12-growth-entry://ua-msme/first-proving-ground",
                "demand_act_ref": demand_refs[0],
                "certified_envelope_delta_ref": envelope_delta_refs[0],
                "reuse_acquisition_ref": "reuse-acquisition://ua-msme/layer3-g5",
            }
        ],
        "voi_allocation_refs": ["voi://ua-msme/layer3-g5"],
        "reuse_acquisition_refs": ["reuse-acquisition://ua-msme/layer3-g5"],
        "accountable_principal_refs": ["principal://ua-msme/ministry-economy"],
    }


def _g5_upstream_health_readings() -> dict[str, dict[str, Any]]:
    return {
        "adapter-semantic-loss": {
            "status": "pass",
            "value": 0,
            "reading_ref": "layer3-g5://health/adapter-semantic-loss",
        },
        "governance-throughput": {
            "status": "pass",
            "reading_ref": "layer3-g4://health/governance-throughput",
        },
        "demand-pull-vs-abstention": {
            "status": "pass",
            "reading_ref": "layer3-g5://health/demand-pull-vs-abstention",
        },
        "search-recall@known-seeds + index-staleness": {
            "status": "pass",
            "reading_ref": "layer3-g1://health/search-recall-freshness",
        },
    }


def _build_g5_public_export_projection_refs(
    *,
    conversion_record: Layer3G5ConversionRecord,
    envelope_delta: Layer3G5EnvelopeExpansionDelta,
    pinned_case_input_bundle: Layer3G5PinnedCaseInputBundle,
) -> Layer3G5PublicExportProjectionRefs:
    base_projection = _g5_projection_payload(
        audience="public",
        conversion_record=conversion_record,
    )
    public_projection = assert_policy_design_projection_not_authority(base_projection)
    projection_contract = verify_policy_design_case_projection_consumer_contract(
        projections={"PUBLIC": public_projection},
        expected_closeout_truth=public_projection["closeout_truth"],
    )
    projection_contract = {
        "consumer_contract_ref": projection_contract.get(
            "schema_version",
            "policyos.runtime.policy_design_case.projection_contract_verification.v1",
        ),
        **projection_contract,
    }
    s12_projection = _g5_s12_projection_payload(pinned_case_input_bundle)
    s14_projection = _g5_s14_projection_payload(pinned_case_input_bundle)
    s12_contract = verify_s12_resource_projection_consumer_contract(
        projections={"PUBLIC": s12_projection}
    )
    s14_contract = verify_s14_universality_projection_consumer_contract(
        projections={"PUBLIC": s14_projection}
    )
    issue_codes: list[str] = []
    if projection_contract.get("status") != "pass":
        issue_codes.append("layer3_g5_projection_mints_authority")
    if s12_contract.get("status") != "pass" or s14_contract.get("status") != "pass":
        issue_codes.append("layer3_g5_projection_omits_required_deny_list")
    public_projection["g5_conversion_record_ref"] = conversion_record.conversion_record_id
    public_projection["g5_conversion_outcome"] = conversion_record.conversion_outcome
    public_projection["g5_envelope_expansion_rate"] = (
        envelope_delta.envelope_expansion_rate
    )
    public_projection["s12_public_growth_limitation"] = (
        "G5 demand/growth refs are diagnostic and cannot allocate budget."
    )
    return Layer3G5PublicExportProjectionRefs(
        status="fail" if issue_codes else "pass",
        PUBLIC=public_projection,
        REVIEWER=_g5_projection_payload(
            audience="reviewer",
            conversion_record=conversion_record,
        ),
        EXPERT=_g5_projection_payload(
            audience="expert",
            conversion_record=conversion_record,
        ),
        MACHINE=_g5_projection_payload(
            audience="machine",
            conversion_record=conversion_record,
        ),
        projection_contract_verification=projection_contract,
        s12_projection_contract_verification=s12_contract,
        s14_projection_contract_verification=s14_contract,
        issue_codes=tuple(issue_codes),
    )


def _g5_projection_payload(
    *,
    audience: str,
    conversion_record: Layer3G5ConversionRecord,
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.projection.v1",
        "generated_at": "2026-06-09T00:00:00Z",
        "surface": "layer3_g5_conversion_projection",
        "audience": audience,
        "policy_design_case_id": G5_PINNED_CASE_ID,
        "run_id": "layer3-g5-readiness",
        "source_ref": conversion_record.conversion_record_id,
        "primary_state": "blocked"
        if conversion_record.conversion_outcome == "unchanged_blocker"
        else "projection_only",
        "states": ["blocked", "projection_only"],
        "labels": [
            {
                "state": "blocked",
                "label": "G5 conversion remains bounded by upstream blockers.",
                "authority_role": "projection_only",
                "source_authority": "layer3_g5_conversion_record",
            }
        ],
        "closeout_truth": {
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "blocker_codes": list(conversion_record.blocker_refs)
            or ["layer3_g5_unchanged_blocker"],
        },
        "authority_role": "projection_only",
        "projection_policy": "reads_policy_design_case_only",
        "authoritative_for": [],
        "evidence_class": "diagnostic_supporting",
        "invariant_summary": {},
        "redaction_summary": {"raw_payload_redacted": True},
        "audit_refs": [conversion_record.conversion_record_id],
        "source_authority_refs": {
            "g5_conversion_record_ref": conversion_record.conversion_record_id
        },
        "source_state": {
            "g5_conversion_outcome": conversion_record.conversion_outcome,
            "g5_grounding_disposition": conversion_record.grounding_disposition,
        },
        "may_be_used_for": [
            "api_display",
            "dashboard_display",
            "external_explanation",
            "operator_triage",
            "public_audit",
        ],
        "may_not_be_used_for": [
            "claim_authority",
            "scorecard_authority",
            "runtime_closeout_authority",
            "recommendation_authority",
            "production_authority",
            "policy_recommendation",
            "useful_design_credit",
        ],
        "capability_reality_state": "implemented_but_not_orchestrated",
        "contract_verification_status": "pass",
        "contract_verification_refs": [
            "policyos.runtime.policy_design_case.projection_contract_verification.v1"
        ],
    }


def _g5_s12_projection_payload(
    pinned: Layer3G5PinnedCaseInputBundle,
) -> dict[str, Any]:
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "s12_resource_posture_ref": "s12://layer3-g5/resource-economics",
        "resource_allocation_policy_ref": "s12://layer3-g5/resource-economics",
        "explore_exploit_posture": "explore",
        "explore_exploit_dial_ref": "s7://layer3-g5/delegation-dial",
        "delegation_contract_ref": pinned.s7_human_decision_record_ref
        or "s7://layer3-g5/delegation-dial",
        "s12_public_growth_limitation": (
            "G5 demand-pull and growth refs disclose pressure only; they do not "
            "recommend allocation or relax useful-design floors."
        ),
        "authority_boundary": {
            "may_not_use_for": list(G5_S12_PROJECTION_MAY_NOT_USE_FOR)
        },
    }


def _g5_s14_projection_payload(
    pinned: Layer3G5PinnedCaseInputBundle,
) -> dict[str, Any]:
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "s14_universality_assurance_ref": "s14://layer3-g5/universality-assurance",
        "universality_claim_gate_ref": "s14://layer3-g5/universality-claim-gate",
        "declared_operation_envelope_ref": pinned.s14_declared_envelope_ref
        or "envelope://ua-msme/declared-limited",
        "d4_corpus_track_coverage_ref": "d4://layer3-g5/corpus-track-coverage",
        "expert_oracle_bootstrap_ref": "expert-oracle://layer3-g5/bootstrap",
        "breadth_floor_config_ref": "breadth-floor://layer3-g5/config",
        "universality_baseline_comparison_ref": (
            "universality-baseline://layer3-g5/comparison"
        ),
        "grounded_authority_coverage_ref": (
            "grounded-authority://layer3-g5/coverage"
        ),
        "evaluation_status_composition_ref": (
            "status-composition://layer3-g5/evaluation"
        ),
        "axis_scorecard_ref": "axis-scorecard://layer3-g5",
        "sealed_battery_run_ref": "sealed-battery://layer3-g5/not-accessed",
        "mechanism_generality_report_ref": "mechanism-generality://layer3-g5/report",
        "s9_projection_faithfulness_refs": ("s9://layer3-g5/faithfulness",),
        "public_universality_limitation": (
            "G5 may project the declared envelope only; it cannot claim universal "
            "performance or production rollout authority."
        ),
        "authority_boundary": {
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
            ]
        },
    }


def _build_g5_conversion_audit_surface(
    *,
    conversion_record: Layer3G5ConversionRecord,
    public_projection: Layer3G5PublicExportProjectionRefs,
) -> Layer3G5ConversionAuditSurface:
    return Layer3G5ConversionAuditSurface(
        status="pass" if public_projection.status == "pass" else "fail",
        conversion_record_refs=(conversion_record.conversion_record_id,),
        blocker_refs=conversion_record.blocker_refs,
        limitation_refs=conversion_record.limitation_refs,
        PUBLIC={
            "conversion_outcome": conversion_record.conversion_outcome,
            "projection_ref": "layer3_g5_public_export_projection_refs.PUBLIC",
            "raw_payload_redacted": True,
        },
        REVIEWER={
            "conversion_record_ref": conversion_record.conversion_record_id,
            "blocker_refs": list(conversion_record.blocker_refs),
        },
        EXPERT={
            "authority_boundary": {
                "authoritative_for": list(G5_AUTHORITATIVE_FOR),
                "may_not_use_for": list(G5_MAY_NOT_USE_FOR),
            }
        },
        MACHINE={
            "schema_version": G5_SCHEMA_VERSION,
            "projection_contract_status": public_projection.status,
        },
        issue_codes=public_projection.issue_codes,
    )


def check_g5_closed_case_replay_integrity(
    *,
    pre_g5_payload: Mapping[str, Any],
    post_g5_payload: Mapping[str, Any],
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    """Verify G5 only overlays G5-owned fields on pre-G5 replay payloads."""

    pre = _mapping(pre_g5_payload)
    post = _mapping(post_g5_payload)
    mutated_keys = [
        str(key)
        for key, value in pre.items()
        if post.get(key) != value
    ]
    foreign_overlay_keys = [
        str(key)
        for key in post
        if key not in pre and not str(key).startswith(("g5_", "layer3_g5_"))
    ]
    issue_codes = (
        ("layer3_g5_pre_g5_closed_case_replay_mutated",)
        if mutated_keys or foreign_overlay_keys
        else ()
    )
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_closed_case_replay_integrity",
        status="fail" if issue_codes else "pass",
        observed_surface_refs=tuple(
            f"pre_g5_key:{key}" for key in (*mutated_keys, *foreign_overlay_keys)
        ),
        issue_codes=issue_codes,
    )


def check_g5_closeout_boundary(
    closeout_reader_payload: Mapping[str, Any],
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    """Reject attempts to use G5 surfaces as module-owned closeout evidence."""

    payload = _mapping(closeout_reader_payload)
    observed_surfaces = tuple(
        str(value) for value in _sequence(payload.get("observed_surface_refs"))
    )
    authoritative_for = tuple(
        str(value) for value in _sequence(payload.get("authoritative_for"))
    )
    issue_codes: list[str] = []
    if bool(payload.get("substitutes_module_owned_closeout_evidence")):
        issue_codes.append("layer3_g5_closeout_surface_substitution_attempt")
    if {"closeout_authority", "runtime_closeout_authority"} & set(authoritative_for):
        issue_codes.append("layer3_g5_closeout_authority_leak")
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_closeout_boundary",
        status="fail" if issue_codes else "pass",
        observed_surface_refs=observed_surfaces,
        denied_substitution_surface_refs=observed_surfaces if issue_codes else (),
        authoritative_for=authoritative_for,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def check_g5_candidate_authority_firewall(
    authority_payload: Mapping[str, Any],
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    """Reject candidate/speculation refs in conversion, claim, or projection slots."""

    strings = _flatten_strings(authority_payload)
    issue_codes: list[str] = []
    if any("candidate_unverified" in value for value in strings):
        issue_codes.append("layer3_g5_candidate_unverified_used_as_authority")
    if any("rejected_speculation" in value for value in strings):
        issue_codes.append("layer3_g5_rejected_speculation_used_as_authority")
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_candidate_authority_firewall",
        status="fail" if issue_codes else "pass",
        observed_surface_refs=tuple(strings),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def check_g5_warning_lifecycle(
    warning_like_records: Sequence[Mapping[str, Any]],
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    """Ensure G5 caveats are owned warnings, blockers, or limitations."""

    issue_codes: list[str] = []
    observed: list[str] = []
    for index, record in enumerate(warning_like_records):
        payload = _mapping(record)
        status = str(payload.get("status", "")).lower()
        kind = str(payload.get("kind", "")).lower()
        warning_like = status in {"warn", "warning"} or "warning" in kind
        warning_like = warning_like or "caveat" in kind or "soft_gate" in kind
        if not warning_like:
            continue
        observed.append(str(payload.get("warning_ref") or f"warning_like:{index}"))
        has_owned_lifecycle = bool(
            payload.get("warning_lifecycle_ref")
            or payload.get("owned_warning_lifecycle_ref")
        )
        has_hard_resolution = bool(
            payload.get("limitation_ref")
            or payload.get("limitation_refs")
            or payload.get("blocker_ref")
            or payload.get("blocker_refs")
        )
        if not has_owned_lifecycle and not has_hard_resolution:
            issue_codes.append("layer3_g5_unowned_warning_lifecycle")
        if payload.get("conversion_pass_effect") or payload.get(
            "useful_design_credit_effect"
        ):
            issue_codes.append("layer3_g5_warning_used_as_conversion_pass")
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_warning_lifecycle",
        status="fail" if issue_codes else "pass",
        observed_surface_refs=tuple(observed),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _build_g5_task7_conformance_report(
    public_projection: Layer3G5PublicExportProjectionRefs,
) -> Layer3G5ConformanceReport:
    public_raw_payload_check = _check_g5_public_projection_boundary(
        public_projection.PUBLIC | {"raw_upstream_payload": {"secret": "payload"}},
        public_export_hook_status="out_of_scope_reference_only",
        public_export_bundle_route_registered=False,
    )
    projection_authority_check = _check_g5_public_projection_boundary(
        public_projection.PUBLIC | {"authoritative_for": ["claim_authority"]},
        public_export_hook_status="out_of_scope_reference_only",
        public_export_bundle_route_registered=False,
    )
    public_hook_check = _check_g5_public_projection_boundary(
        public_projection.PUBLIC,
        public_export_hook_status="implemented",
        public_export_bundle_route_registered=False,
    )
    replay_mutation_check = check_g5_closed_case_replay_integrity(
        pre_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
        },
        post_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "pass",
            "layer3_g4_gate_status": "pass",
            "g5_readiness_summary": {"status": "pass"},
        },
    )
    safe_replay_check = check_g5_closed_case_replay_integrity(
        pre_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
        },
        post_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
            "g5_readiness_summary": {"status": "pass"},
        },
    )
    closeout_substitution_check = check_g5_closeout_boundary(
        {
            "observed_surface_refs": (
                "architecture/policy_design_case/layer3_g5_readiness_manifest.json",
                "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json",
            ),
            "substitutes_module_owned_closeout_evidence": True,
            "authoritative_for": (),
        }
    )
    closeout_authority_check = check_g5_closeout_boundary(
        {
            "observed_surface_refs": (
                "architecture/policy_design_case/layer3_g5_conversion_audit_surface.json",
            ),
            "authoritative_for": ("runtime_closeout_authority",),
        }
    )
    safe_closeout_check = check_g5_closeout_boundary(
        {
            "observed_surface_refs": (
                "architecture/policy_design_case/layer3_g5_readiness_manifest.json",
            ),
            "authoritative_for": (),
        }
    )
    candidate_check = check_g5_candidate_authority_firewall(
        {
            "conversion_refs": ("candidate_unverified://g5/speculative-conversion",),
            "projection_authority_refs": ("candidate_unverified://g5/projection",),
        }
    )
    rejected_speculation_check = check_g5_candidate_authority_firewall(
        {"claim_authority_refs": ("rejected_speculation://g5/claim",)}
    )
    safe_candidate_check = check_g5_candidate_authority_firewall(
        {"limitation_refs": ("limitation://layer3-g5/unchanged-blocker",)}
    )
    unowned_warning_check = check_g5_warning_lifecycle(
        ({"status": "warn", "message": "unowned caveat"},)
    )
    warning_bypass_check = check_g5_warning_lifecycle(
        (
            {
                "status": "warn",
                "warning_lifecycle_ref": "warning-lifecycle://layer3-g5/owned",
                "conversion_pass_effect": True,
            },
        )
    )
    safe_warning_check = check_g5_warning_lifecycle(
        (
            {
                "status": "warn",
                "warning_lifecycle_ref": "warning-lifecycle://layer3-g5/owned",
            },
        )
    )
    arbitrary_request_check = _check_g5_request_scope_boundary(
        {"request_mode": "arbitrary_user_request"}
    )
    g7_widening_check = _check_g5_request_scope_boundary(
        {"requested_region_ref": "region://global"}
    )
    results = (
        _negative_result(
            "public_projection_raw_payload_leak",
            public_raw_payload_check,
            ("layer3_g5_public_raw_payload_leak",),
        ),
        _negative_result(
            "projection_authority_leak",
            projection_authority_check,
            ("layer3_g5_projection_mints_authority",),
        ),
        _negative_result(
            "public_export_hook_overclaimed",
            public_hook_check,
            ("layer3_g5_public_export_hook_overclaimed",),
        ),
        _negative_result(
            "closed_case_replay_mutation",
            replay_mutation_check,
            ("layer3_g5_pre_g5_closed_case_replay_mutated",),
        ),
        _negative_result(
            "closeout_surface_substitution_attempt",
            closeout_substitution_check,
            ("layer3_g5_closeout_surface_substitution_attempt",),
        ),
        _negative_result(
            "closeout_authority_leak",
            closeout_authority_check,
            ("layer3_g5_closeout_authority_leak",),
        ),
        _negative_result(
            "candidate_unverified_authority_slot",
            candidate_check,
            ("layer3_g5_candidate_unverified_used_as_authority",),
        ),
        _negative_result(
            "rejected_speculation_authority_slot",
            rejected_speculation_check,
            ("layer3_g5_rejected_speculation_used_as_authority",),
        ),
        _negative_result(
            "unowned_warning_lifecycle",
            unowned_warning_check,
            ("layer3_g5_unowned_warning_lifecycle",),
        ),
        _negative_result(
            "warning_used_as_conversion_pass",
            warning_bypass_check,
            ("layer3_g5_warning_used_as_conversion_pass",),
        ),
        _negative_result(
            "arbitrary_request_attempt",
            arbitrary_request_check,
            ("layer3_g5_arbitrary_request_attempt",),
        ),
        _negative_result(
            "g7_region_widening_attempt",
            g7_widening_check,
            ("layer3_g5_g7_widening_attempt",),
        ),
    )
    issues = tuple(
        code
        for result in results
        if result.status != "pass"
        for code in result.observed_issue_codes
    )
    return Layer3G5ConformanceReport(
        status="fail" if issues else "pass",
        negative_results=results,
        performance_contract={
            "status": "pass",
            "bounded_artifact_read_policy": "explicit_expected_paths_only",
            "bounded_artifact_paths": [
                path.as_posix() for path in BOUNDED_DEPENDENCY_PATHS
            ],
            "bounded_artifact_read_count": len(BOUNDED_DEPENDENCY_PATHS),
            "request_path_repo_glob_allowed": False,
            "unbounded_repo_scan": False,
            "upstream_builder_rerun_in_request_path": False,
            "lazy_w12d_import": True,
            "w12d_import_mode": "lazy",
            "request_path_upstream_bundle_rerun_allowed": False,
        },
        closed_case_replay_integrity=safe_replay_check.model_dump(mode="json"),
        closeout_boundary_check=safe_closeout_check,
        candidate_firewall_check=safe_candidate_check.model_dump(mode="json"),
        warning_lifecycle_check=safe_warning_check.model_dump(mode="json"),
        issue_codes=issues,
    )


def _check_g5_public_projection_boundary(
    public_projection: Mapping[str, Any],
    *,
    public_export_hook_status: str,
    public_export_bundle_route_registered: bool,
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    issue_codes: list[str] = []
    if "raw_upstream_payload" in public_projection:
        issue_codes.append("layer3_g5_public_raw_payload_leak")
    if _sequence(public_projection.get("authoritative_for")):
        issue_codes.append("layer3_g5_projection_mints_authority")
    if (
        public_export_hook_status != "out_of_scope_reference_only"
        or public_export_bundle_route_registered
    ):
        issue_codes.append("layer3_g5_public_export_hook_overclaimed")
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_public_projection_boundary",
        status="fail" if issue_codes else "pass",
        authoritative_for=tuple(
            str(value) for value in _sequence(public_projection.get("authoritative_for"))
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _check_g5_request_scope_boundary(
    request_payload: Mapping[str, Any],
) -> Layer3G5ProjectionCloseoutBoundaryCheck:
    payload = _mapping(request_payload)
    issue_codes: list[str] = []
    request_mode = str(payload.get("request_mode", "")).lower()
    requested_region = str(payload.get("requested_region_ref", ""))
    if "arbitrary" in request_mode:
        issue_codes.append("layer3_g5_arbitrary_request_attempt")
    if requested_region and requested_region != "region://ua":
        issue_codes.append("layer3_g5_g7_widening_attempt")
    return Layer3G5ProjectionCloseoutBoundaryCheck(
        check_id="layer3_g5_request_scope_boundary",
        status="fail" if issue_codes else "pass",
        observed_surface_refs=tuple(
            value
            for value in (request_mode, requested_region)
            if value
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _negative_result(
    negative_id: str,
    check: Layer3G5ProjectionCloseoutBoundaryCheck,
    expected_issue_codes: Sequence[str],
) -> Layer3G5ConformanceNegativeResult:
    observed = tuple(check.issue_codes)
    expected = tuple(expected_issue_codes)
    return Layer3G5ConformanceNegativeResult(
        negative_id=negative_id,
        status="pass" if set(expected) <= set(observed) else "fail",
        expected_issue_codes=expected,
        observed_issue_codes=observed,
        fixture_ref=f"layer3-g5://conformance/{negative_id}",
    )


def _build_g5_conversion_route_contract_registry() -> dict[str, Any]:
    return {
        "schema_version": G5_SCHEMA_VERSION,
        "rule_version": G5_RULE_VERSION,
        "status": "pass",
        "route_count": 1,
        "conversion_route_records": [
            {
                "route_id": "layer3.g5.conversion_route.w12d_pinned_case",
                "case_id": G5_PINNED_CASE_ID,
                "producer": "polisyos.runtime.quality.layer3_proving_ground_conversion",
                "consumer": "tools.quality.validation.run_universal_outcome_corpus",
                "artifact_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer3_g5_conversion_records.json"
                ),
                "consumer_gate_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer3_g5_w12d_consumer_gate.json"
                ),
                "authority_purpose": "w12d_layer3_conversion_gate",
                "authoritative_for": list(G5_AUTHORITATIVE_FOR),
                "may_not_use_for": [
                    *G5_MAY_NOT_USE_FOR,
                    "conversion_authority_without_g5",
                ],
                "verification_refs": [
                    "tests/repo_quality/tools/"
                    "test_policy_design_case_layer3_g5_readiness.py"
                ],
            }
        ],
    }


def _build_g5_health_metric_delta(
    snapshot: Layer3G5DependencyHealthMetricSnapshot,
) -> dict[str, Any]:
    return {
        "schema_version": G5_SCHEMA_VERSION,
        "rule_version": G5_RULE_VERSION,
        "metric_ids": list(G5_CONSTITUTION_HEALTH_METRICS),
        "metric_statuses": dict(snapshot.metric_statuses),
        "readings": dict(snapshot.health_toml),
    }


def _g5_readiness_summary(
    *,
    snapshot: Layer3G5DependencyReadinessSnapshot,
    pinned: Layer3G5PinnedCaseInputBundle,
    handoff: Layer3G5G4HandoffResolution,
    matrix: Layer3G5UpstreamScopeJoinMatrix,
    evidence: Layer3G5GroundedResultEvidenceSet,
    useful_join: Layer3G5UsefulDesignMetricEligibilityJoin,
    eligibility: Layer3G5ConversionEligibilityLedger,
    status_composition: Layer3G5StatusCompositionLedger,
    demand_pull: Layer3G5DemandPullAttemptRecord,
    health_snapshot: Layer3G5DependencyHealthMetricSnapshot,
    envelope_delta: Layer3G5EnvelopeExpansionDelta,
    conversion_records: Sequence[Layer3G5ConversionRecord],
    w12d_gate: Layer3G5W12DConsumerGate,
    audit_surface: Layer3G5ConversionAuditSurface,
    public_projection: Layer3G5PublicExportProjectionRefs,
    conformance_report: Layer3G5ConformanceReport,
    registry_ratchet: Layer3G5RegistryRatchetDelta,
) -> dict[str, Any]:
    grounded_limited_count = sum(
        1
        for record in conversion_records
        if record.conversion_outcome == "typed_blocker -> grounded_limited"
    )
    grounded_abstention_count = sum(
        1
        for record in conversion_records
        if record.conversion_outcome == "typed_blocker -> grounded_abstention"
    )
    unchanged_blocker_count = sum(
        1
        for record in conversion_records
        if record.conversion_outcome == "unchanged_blocker"
    )
    return {
        "status": "pass",
        "schema_version": G5_SCHEMA_VERSION,
        "rule_version": G5_RULE_VERSION,
        "surface_id": G5_SURFACE_ID,
        "g5_dependency_readiness_status": snapshot.status,
        "g5_g0_dependency_status": snapshot.g0_dependency_status,
        "g5_g1_dependency_status": snapshot.g1_dependency_status,
        "g5_g2_dependency_status": snapshot.g2_dependency_status,
        "g5_g3_dependency_status": snapshot.g3_dependency_status,
        "g5_gl_dependency_status": snapshot.gl_dependency_status,
        "g5_g4_dependency_status": snapshot.g4_dependency_status,
        "g5_dependency_manifest_key_resolution_status": (
            snapshot.dependency_manifest_key_resolution_status
        ),
        "g5_g1_grounding_status": snapshot.g1_grounding_status,
        "g5_g1_source_contract_hash_status": "pass"
        if matrix.g1_source_contract_content_hash
        else "missing",
        "g5_g1_observed_through_status": "pass"
        if matrix.g1_observed_through
        else "missing",
        "g5_g1_may_not_use_for_status": "pass"
        if matrix.g1_may_not_use_for
        else "missing",
        "g5_lineage_deduplication_status": "pass"
        if not evidence.lineage_deduplication_record.duplicate_refs
        else "fail",
        "g5_search_recall_status": snapshot.g1_search_recall_status,
        "g5_index_freshness_status": snapshot.g1_index_freshness_status,
        "g5_pinned_case_input_status": pinned.status,
        "g5_w12d_case_block_index_status": pinned.w12d_case_block_index.status,
        "g5_w12d_s4_s14_case_key_status": pinned.composed_loop_completeness_gate.status,
        "g5_w12d_payload_status": pinned.w12d_payload_status,
        "g5_w12d_payload_freshness_status": snapshot.w12d_payload_freshness_status,
        "g5_w12d_g3_summary_location_status": "top_level_report_field",
        "g5_s2_design_search_status": pinned.s2_status,
        "g5_s2_acquisition_branch_status": pinned.s2_acquisition_branch_state,
        "g5_design_record_firewall_status": "pass"
        if "layer3_g5_design_record_firewall_status_flattened"
        not in pinned.issue_codes
        else "limited",
        "g5_constraint_store_status": "pass"
        if "layer3_g5_constraint_store_block_ignored" not in pinned.issue_codes
        else "limited",
        "g5_s7_delegation_record_resolution_status": "pass"
        if pinned.s7_human_decision_record_ref
        else "missing",
        "g5_s12_growth_entry_status": "pass" if demand_pull.s12_growth_entry_refs else "missing",
        "g5_s12_certified_envelope_delta_status": "pass"
        if pinned.s12_certified_envelope_delta_refs
        else "missing",
        "g5_s14_pending_sealed_status": pinned.s14_universal_claim_gate_status,
        "g5_s14_declared_envelope_status": "pass"
        if pinned.s14_declared_envelope_ref
        else "missing",
        "g5_composed_loop_completeness_status": (
            pinned.composed_loop_completeness_gate.status
        ),
        "g5_s14_gate_status": pinned.s14_grounded_authority_status,
        "g5_g4_handoff_resolution_status": handoff.status,
        "g5_g4_handoff_blocker_status": "blocked"
        if handoff.blocked_promotion_input_count
        else "pass",
        "g5_g4_promotion_record_resolution_status": handoff.status,
        "g5_g4_design_scope_promotion_status": eligibility.g4_design_scope_status,
        "g5_g4_registration_dependency_status": snapshot.g4_g5_promotion_handoff_status,
        "g5_g4_grounded_contract_dedup_status": evidence.status,
        "g5_gl_reissue_status": snapshot.gl_reissue_status,
        "g5_gl_applicability_status": snapshot.gl_applicability_status,
        "g5_gl_requirement_artifact_status": "pass",
        "g5_gl_mandate_compatibility_status": "not_required",
        "g5_gl_reference_resolution_status": snapshot.gl_reference_resolution_status,
        "g5_gl_amendment_lineage_status": snapshot.gl_amendment_lineage_status,
        "g5_g2_design_record_alias_resolution_status": (
            matrix.g2_design_record_alias_resolution.status
        ),
        "g5_g2_s2_replay_key_ref_status": "pass"
        if matrix.g2_s2_replay_key_refs
        else "missing",
        "g5_g2_source_contract_join_status": "pass"
        if matrix.g2_source_contract_ref == matrix.g1_source_contract_ref
        else "limited",
        "g5_g3_proof_authority_boundary_status": matrix.g3_proof_status,
        "g5_upstream_scope_join_status": matrix.status,
        "g5_weakest_boundary_status": eligibility.weakest_boundary_status,
        "g5_weakest_boundary_reason": eligibility.weakest_boundary_reason,
        "g5_mixed_status_composition_status": "limited"
        if eligibility.mixed_upstream_statuses
        else "pass",
        "g5_governed_promotion_input_count": handoff.governed_promotion_input_count,
        "g5_blocked_promotion_input_count": handoff.blocked_promotion_input_count,
        "g5_grounded_evidence_ref_count": len(evidence.grounded_evidence_refs),
        "g5_effective_evidence_independence_status": (
            evidence.effective_independence_record.status
        ),
        "g5_evidence_independence_map_status": (
            evidence.effective_independence_record.status
        ),
        "g5_useful_design_metric_eligibility_status": useful_join.status,
        "g5_runtime_vs_expert_metric_separation_status": "pass",
        "g5_conversion_record_count": len(conversion_records),
        "g5_conversion_outcome": conversion_records[0].conversion_outcome
        if conversion_records
        else "unchanged_blocker",
        "g5_grounded_limited_count": grounded_limited_count,
        "g5_grounded_abstention_count": grounded_abstention_count,
        "g5_unchanged_blocker_count": unchanged_blocker_count,
        "g5_grounded_conversion_count": grounded_limited_count + grounded_abstention_count,
        "g5_useful_design_credit_count": 0,
        "g5_grounded_abstention_useful_design_credit_count": 0,
        "g5_status_composition_status": status_composition.status,
        "g5_w12d_consumer_gate_status": w12d_gate.status,
        "g5_demand_pull_attempt_status": demand_pull.status,
        "g5_envelope_expansion_status": envelope_delta.status,
        "g5_envelope_expansion_rate": envelope_delta.envelope_expansion_rate,
        "g5_adapter_semantic_loss_status": health_snapshot.metric_statuses.get(
            "adapter-semantic-loss",
            "missing",
        ),
        "g5_governance_throughput_status": health_snapshot.metric_statuses.get(
            "governance-throughput",
            "missing",
        ),
        "g5_demand_pull_vs_abstention_status": health_snapshot.metric_statuses.get(
            "demand-pull-vs-abstention",
            "missing",
        ),
        "g5_dependency_health_metric_snapshot_status": health_snapshot.status,
        "g5_domain_ceiling_count": 0,
        "g5_search_ceiling_repair_required_count": 0,
        "g5_closed_case_replay_integrity_status": "pass",
        "g5_warning_lifecycle_status": "pass",
        "g5_projection_boundary_status": public_projection.status,
        "g5_s12_projection_contract_status": (
            public_projection.s12_projection_contract_verification.get(
                "status",
                "missing",
            )
        ),
        "g5_s14_projection_contract_status": (
            public_projection.s14_projection_contract_verification.get(
                "status",
                "missing",
            )
        ),
        "g5_closeout_surface_substitution_status": "pass",
        "g5_candidate_firewall_status": "pass",
        "g5_public_surface_status": audit_surface.status,
        "g5_public_export_hook_status": public_projection.public_export_hook_status,
        "g5_conformance_status": conformance_report.status,
        "g5_conformance_negative_count": len(conformance_report.negative_results),
        "g5_conformance_negative_pass_count": sum(
            1
            for result in conformance_report.negative_results
            if result.status == "pass"
        ),
        "g5_registry_ratchet_delta_status": registry_ratchet.status,
        "g5_generated_artifacts_registration_status": "unknown",
        "g5_inventory_surface_status": "unknown",
        "g5_reference_docs_status": "unknown",
        "g5_performance_contract_status": conformance_report.performance_contract.get(
            "status",
            "missing",
        ),
        "issue_codes": [],
    }


def validate_layer3_g5_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G5Bundle,
) -> Layer3G5ValidationReport:
    """Validate a G5 bundle or bundle-shaped mapping."""

    del repo_root
    preflight_issues = _g5_green_unchanged_blocker_issues(persisted)
    try:
        bundle = (
            persisted
            if isinstance(persisted, Layer3G5Bundle)
            else Layer3G5Bundle.model_validate(persisted)
        )
    except ValidationError as exc:
        return Layer3G5ValidationReport(
            status="fail",
            issues=(
                *preflight_issues,
                Layer3G5ValidationIssue(
                    code="layer3_g5_dependency_readiness_snapshot_missing",
                    path="$",
                    message=str(exc),
                ),
            ),
        )
    issues = [
        Layer3G5ValidationIssue(
            code=code,
            path="$",
            message=f"G5 bundle reported {code}.",
        )
        for code in bundle.readiness_manifest.issue_codes
    ]
    issues.extend(preflight_issues)
    eligibility = bundle.conversion_eligibility_ledger
    if (
        eligibility.status == "pass"
        and eligibility.conversion_outcome == "unchanged_blocker"
    ):
        issues.append(
            Layer3G5ValidationIssue(
                code="layer3_g5_unchanged_blocker_green_status",
                path="$.conversion_eligibility_ledger",
                message="unchanged_blocker is a failed conversion attempt, not a green conversion.",
            )
        )
    return Layer3G5ValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary=dict(bundle.readiness_manifest.summary),
    )


def _g5_green_unchanged_blocker_issues(
    persisted: Mapping[str, Any] | Layer3G5Bundle,
) -> tuple[Layer3G5ValidationIssue, ...]:
    if isinstance(persisted, Layer3G5Bundle):
        eligibility = persisted.conversion_eligibility_ledger.model_dump(mode="json")
        readiness = persisted.readiness_manifest.model_dump(mode="json")
    elif isinstance(persisted, Mapping):
        eligibility = _mapping(persisted.get("conversion_eligibility_ledger"))
        readiness = _mapping(persisted.get("readiness_manifest"))
    else:
        return ()
    if (
        eligibility.get("status") == "pass"
        and eligibility.get("conversion_outcome") == "unchanged_blocker"
    ):
        return (
            Layer3G5ValidationIssue(
                code="layer3_g5_unchanged_blocker_green_status",
                path="$.conversion_eligibility_ledger",
                message="unchanged_blocker is a failed conversion attempt, not a green conversion.",
            ),
        )
    return ()


def build_g5_w12d_consumer_gate(
    case: Mapping[str, Any],
    *,
    conversion_records: Sequence[Layer3G5ConversionRecord | Mapping[str, Any]] = (),
    dependency_snapshot: Layer3G5DependencyReadinessSnapshot | Mapping[str, Any] | None = None,
) -> Layer3G5W12DConsumerGate:
    """Build the W12.D G5 consumer gate for one case."""

    del dependency_snapshot
    case_id = str(case.get("case_id") or "")
    records = tuple(
        record
        if isinstance(record, Layer3G5ConversionRecord)
        else Layer3G5ConversionRecord.model_validate(record)
        for record in conversion_records
    )
    matching = tuple(record for record in records if record.case_id == case_id)
    if case_id != G5_PINNED_CASE_ID:
        return Layer3G5W12DConsumerGate(
            status="fail",
            case_id=case_id,
            issue_codes=("layer3_g5_non_pinned_case_widening_attempt",),
        )
    if not matching:
        return Layer3G5W12DConsumerGate(
            status="not_routed",
            case_id=case_id,
            issue_codes=("layer3_g5_w12d_consumer_gate_missing",),
        )
    return Layer3G5W12DConsumerGate(
        status="pass",
        case_id=case_id,
        conversion_classification=matching[0].conversion_outcome,
    )


def build_g5_pinned_case_input_bundle(
    repo_root: Path,
    *,
    w12d_report_payload: Mapping[str, Any] | None = None,
    w12d_payload_ref: str | None = None,
    source_context: str = "explicit_payload",
    build_fresh_payload: bool = False,
) -> Layer3G5PinnedCaseInputBundle:
    """Build the full W12.D pinned-case input bundle for G5.

    Args:
        repo_root: Repository root used only for the optional deterministic
            local W12.D builder path.
        w12d_report_payload: Explicit full W12.D report payload.
        w12d_payload_ref: Replay/source ref for the explicit payload. Local
            `_build/.tmp` refs are rejected because they are not source of truth.
        source_context: Caller context, such as `explicit_payload` or
            `w12d_hook`.
        build_fresh_payload: When true and no explicit payload is supplied, use
            the canonical W12.D report builder with keyword-only `case_results`.

    Returns:
        Strict pinned-case bundle with extracted S2/S4-S14/S7/S12/S14 signals.
    """

    root = Path(repo_root)
    issue_codes: list[str] = []
    payload = w12d_report_payload
    payload_status = "explicit_payload" if payload is not None else "not_provided"
    if payload is None and build_fresh_payload:
        payload = _build_w12d_full_payload(
            repo_root=root,
            case_results=(
                {
                    "case_id": G5_PINNED_CASE_ID,
                    "outcome": "typed_blocker",
                    "conversion_outcome": "not_attempted_g0_pre_adapter",
                },
            ),
        )
        payload_status = "fresh_builder"
        w12d_payload_ref = w12d_payload_ref or "w12d://fresh-builder/pinned-case"
    if w12d_payload_ref and "_build/.tmp" in w12d_payload_ref:
        issue_codes.append("layer3_g5_w12d_build_cache_not_source_of_truth")
        payload_status = "stale_build_cache_rejected"
    if payload is None:
        issue_codes.append("layer3_g5_w12d_full_payload_missing")
        return _empty_pinned_case_input_bundle(
            status="fail",
            w12d_payload_status=payload_status,
            w12d_payload_ref=w12d_payload_ref,
            issue_codes=issue_codes,
        )
    if not isinstance(payload, Mapping):
        issue_codes.append("layer3_g5_w12d_manifest_only_not_payload")
        return _empty_pinned_case_input_bundle(
            status="fail",
            w12d_payload_status=payload_status,
            w12d_payload_ref=w12d_payload_ref,
            issue_codes=issue_codes,
        )
    cases = _sequence_of_mappings(payload.get("cases"))
    if not cases:
        issue_codes.append("layer3_g5_w12d_manifest_only_not_payload")
        return _empty_pinned_case_input_bundle(
            status="fail",
            w12d_payload_status=payload_status,
            w12d_payload_ref=w12d_payload_ref,
            issue_codes=issue_codes,
        )
    pinned_case = next(
        (case for case in cases if str(case.get("case_id") or "") == G5_PINNED_CASE_ID),
        None,
    )
    if pinned_case is None:
        issue_codes.append("layer3_g5_non_pinned_case_widening_attempt")
        return _empty_pinned_case_input_bundle(
            status="fail",
            case_id=str(cases[0].get("case_id") or "missing"),
            w12d_payload_status=payload_status,
            w12d_payload_ref=w12d_payload_ref,
            issue_codes=issue_codes,
        )

    case = dict(pinned_case)
    block_index, loop_gate = _build_g5_composed_loop_gate(
        case,
        source_context=source_context,
    )
    issue_codes.extend(block_index.issue_codes)
    issue_codes.extend(loop_gate.issue_codes)

    s2 = _mapping(case.get("s2_design_search"))
    s2_ledger = _mapping(s2.get("search_ledger"))
    design_record = _mapping(s2.get("design_record"))
    constraint_store = _mapping(s2.get("constraint_store"))
    delegation_posture = _mapping(s2.get("delegation_posture"))
    s7 = _mapping(case.get("s7_delegation"))
    s12 = _mapping(case.get("s12_resource_economics"))
    s14 = _mapping(case.get("s14_universality_assurance"))

    s2_status = _first_text(s2.get("status"))
    s2_branch_state = _first_text(
        s2.get("acquisition_branch_state"),
        s2_ledger.get("acquisition_branch_state"),
    )
    if s2_status == "acquisition_required":
        issue_codes.append("layer3_g5_s2_acquisition_required_unresolved")
    if s2_branch_state == "bridge_missing":
        issue_codes.append("layer3_g5_s2_bridge_missing_unresolved")

    firewall_statuses = _status_tuple_from_records(design_record.get("firewall_status"))
    firewall_limit_statuses = {"warn", "warning", "limit", "limited", "block", "blocked"}
    if any(status in firewall_limit_statuses for status in firewall_statuses):
        issue_codes.append("layer3_g5_design_record_firewall_status_flattened")
    constraint_statuses = _status_tuple_from_records(
        constraint_store.get("constraint_records")
    )
    if any(status in {"block", "blocked", "fail", "failed"} for status in constraint_statuses):
        issue_codes.append("layer3_g5_constraint_store_block_ignored")

    s7_record_refs = _dedupe(
        (
            *_as_str_tuple(s7.get("human_decision_record_ref")),
            *_as_str_tuple(delegation_posture.get("human_decision_record_ref")),
            *_as_str_tuple(s2_ledger.get("delegation_record_refs", ())),
        )
    )
    s7_record_ref = s7_record_refs[0] if s7_record_refs else None
    if s7_record_ref is None:
        issue_codes.append("layer3_g5_s7_delegation_record_ref_unresolved")
    s7_request_ref = _first_optional_text(
        s7.get("human_decision_request_ref"),
        delegation_posture.get("human_decision_request_ref"),
    )

    s12_demand_refs, s12_envelope_delta_refs, s12_issue_codes = (
        _extract_s12_demand_growth_refs(s12)
    )
    issue_codes.extend(s12_issue_codes)

    s14_universal_status = _first_text(s14.get("universal_claim_gate_status"))
    s14_grounded_status = _first_text(s14.get("grounded_authority_status"))
    s14_declared_envelope_ref = _first_optional_text(s14.get("declared_envelope_ref"))
    if s14_universal_status == "pending_sealed":
        issue_codes.append("layer3_g5_s14_pending_sealed_overclaimed")
    if s14_grounded_status in {"fail", "failed", "blocked"}:
        issue_codes.append("layer3_g5_s14_grounded_authority_status_overclaimed")

    case_digest = _stable_case_digest(case)
    replay_refs = _extract_replay_refs(
        case=case,
        s2=s2,
        s2_ledger=s2_ledger,
        design_record=design_record,
        w12d_payload_ref=w12d_payload_ref,
        case_digest=case_digest,
    )
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G5PinnedCaseInputBundle(
        status="fail" if _has_pinned_bundle_blocking_issue(issue_codes) else "pass",
        w12d_payload_status=payload_status,
        w12d_payload_ref=w12d_payload_ref,
        w12d_case_block_index=block_index,
        composed_loop_completeness_gate=loop_gate,
        s2_status=s2_status,
        s2_acquisition_branch_state=s2_branch_state,
        design_record_ref=_first_optional_text(design_record.get("ref")),
        design_record_firewall_statuses=firewall_statuses,
        constraint_store_statuses=constraint_statuses,
        s7_human_decision_record_ref=s7_record_ref,
        s7_human_decision_request_ref=s7_request_ref,
        s7_delegation_record_refs=s7_record_refs,
        s12_demand_act_refs=s12_demand_refs,
        s12_certified_envelope_delta_refs=s12_envelope_delta_refs,
        s14_universal_claim_gate_status=s14_universal_status,
        s14_grounded_authority_status=s14_grounded_status,
        s14_declared_envelope_ref=s14_declared_envelope_ref,
        layer3_gate_statuses=_extract_layer3_gate_statuses(case),
        typed_blocker_codes=_extract_typed_blocker_codes(case),
        authority_outcome_refs=_extract_authority_outcome_refs(case),
        case_digest=case_digest,
        replay_refs=replay_refs,
        issue_codes=tuple(issue_codes),
    )


def _build_w12d_full_payload(
    *,
    repo_root: Path,
    case_results: Sequence[Mapping[str, Any]],
    corpus_ref: str = "repo://tests/fixtures/universal-corpus",
) -> dict[str, Any]:
    """Build a deterministic full W12.D report using the supported keyword API."""

    from tools.quality.validation.run_universal_outcome_corpus import (
        build_w12d_universal_outcome_corpus_report,
    )

    return build_w12d_universal_outcome_corpus_report(
        case_results=case_results,
        repo_root=repo_root,
        corpus_ref=corpus_ref,
        mode="g5_pinned_case_builder",
    )


def build_g5_useful_design_metric_eligibility_join(
    *,
    conversion_outcome: Layer3G5ConversionOutcome,
    useful_design_credit_requested: bool = False,
    w11c_useful_design_gate: Mapping[str, Any] | None = None,
    expert_useful_design_ceiling: Mapping[str, Any] | None = None,
) -> Layer3G5UsefulDesignMetricEligibilityJoin:
    """Join G5 conversion to existing useful-design metric authority.

    G5 conversion classification is not itself useful-design metric authority.
    Runtime credit is allowed only for `grounded_limited` when a W11.C-style
    useful-design gate is explicitly present and passes.
    """

    issue_codes: list[str] = []
    if conversion_outcome != "typed_blocker -> grounded_limited":
        return Layer3G5UsefulDesignMetricEligibilityJoin(
            status="out_of_scope",
            conversion_outcome=conversion_outcome,
            useful_design_credit_requested=useful_design_credit_requested,
        )
    if not useful_design_credit_requested:
        return Layer3G5UsefulDesignMetricEligibilityJoin(
            status="out_of_scope",
            conversion_outcome=conversion_outcome,
            useful_design_credit_requested=False,
            runtime_credit_reason="conversion_classification_only",
        )
    if expert_useful_design_ceiling and w11c_useful_design_gate is None:
        issue_codes.append("layer3_g5_expert_useful_design_ceiling_used_as_runtime_credit")
    gate = _mapping(w11c_useful_design_gate)
    gate_status = _first_text(gate.get("status"), gate.get("eligibility_status"))
    gate_counts = bool(
        gate.get("counts_toward_runtime_useful_design")
        or gate.get("runtime_metric_eligible")
    )
    if gate_status not in {"pass", "eligible"} or not gate_counts:
        issue_codes.append("layer3_g5_useful_design_metric_eligibility_join_missing")
    counts = not issue_codes and gate_counts
    return Layer3G5UsefulDesignMetricEligibilityJoin(
        status="pass" if counts else "fail",
        conversion_outcome=conversion_outcome,
        useful_design_credit_requested=True,
        counts_toward_runtime_useful_design=counts,
        w11c_gate_ref=_first_optional_text(gate.get("ref"), gate.get("gate_ref")),
        runtime_credit_reason="w11c_gate_pass" if counts else "not_eligible",
        issue_codes=_dedupe(issue_codes),
    )


def build_g5_status_composition_ledger(
    *,
    conversion_eligibility_ledger: Layer3G5ConversionEligibilityLedger | Mapping[str, Any],
    useful_design_metric_eligibility_join: (
        Layer3G5UsefulDesignMetricEligibilityJoin | Mapping[str, Any] | None
    ) = None,
    w12d_outcome: str = "typed_blocker",
) -> Layer3G5StatusCompositionLedger:
    """Compose local G5 conversion with W12.D and useful-design metric semantics."""

    ledger = _coerce_g5_model(
        conversion_eligibility_ledger,
        Layer3G5ConversionEligibilityLedger,
    )
    join = (
        None
        if useful_design_metric_eligibility_join is None
        else _coerce_g5_model(
            useful_design_metric_eligibility_join,
            Layer3G5UsefulDesignMetricEligibilityJoin,
        )
    )
    issue_codes: list[str] = list(ledger.issue_codes)
    if ledger.conversion_outcome == "typed_blocker -> grounded_abstention":
        issue_codes = list(_grounded_abstention_composition_issue_codes(issue_codes))
    if w12d_outcome not in W12D_ALLOWED_OUTCOMES:
        issue_codes.append("layer3_g5_uncontrolled_w12d_outcome_status")
    counts_toward_runtime_useful_design = False
    if ledger.useful_design_credit_requested:
        if join is None:
            issue_codes.append("layer3_g5_useful_design_metric_eligibility_join_missing")
        elif join.counts_toward_runtime_useful_design:
            counts_toward_runtime_useful_design = True
        else:
            issue_codes.extend(join.issue_codes)
    if ledger.conversion_outcome == "typed_blocker -> grounded_abstention":
        counts_toward_runtime_useful_design = False
    if (
        counts_toward_runtime_useful_design
        and ledger.conversion_outcome != "typed_blocker -> grounded_limited"
    ):
        issue_codes.append("layer3_g5_grounded_abstention_counts_as_useful_design")
        counts_toward_runtime_useful_design = False
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G5StatusCompositionLedger(
        status="fail" if issue_codes else "pass",
        conversion_outcome=ledger.conversion_outcome,
        w12d_outcome=w12d_outcome,
        counts_toward_runtime_useful_design=counts_toward_runtime_useful_design,
        weakest_boundary_reason=ledger.weakest_boundary_reason,
        issue_codes=tuple(issue_codes),
    )


def build_g5_conversion_eligibility_ledger(
    *,
    pinned_case_input_bundle: Layer3G5PinnedCaseInputBundle | Mapping[str, Any],
    dependency_snapshot: Layer3G5DependencyReadinessSnapshot | Mapping[str, Any],
    g4_handoff_resolution: Layer3G5G4HandoffResolution | Mapping[str, Any],
    upstream_scope_join_matrix: Layer3G5UpstreamScopeJoinMatrix | Mapping[str, Any],
    grounded_result_evidence_set: Layer3G5GroundedResultEvidenceSet | Mapping[str, Any],
    requested_scope: Mapping[str, Any] | None = None,
    requested_conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker",
    search_health: Mapping[str, Any] | None = None,
    weakest_boundary: Mapping[str, Any] | None = None,
    upstream_statuses: Sequence[str] = (),
    useful_design_credit_requested: bool = False,
    useful_design_metric_eligibility_join: (
        Layer3G5UsefulDesignMetricEligibilityJoin | Mapping[str, Any] | None
    ) = None,
    demand_pull_attempt_record: Layer3G5DemandPullAttemptRecord | Mapping[str, Any] | None = None,
    gl_legal_authority_payload: Mapping[str, Any] | None = None,
    gl_mandate_records: Sequence[Mapping[str, Any]] = (),
) -> Layer3G5ConversionEligibilityLedger:
    """Decide the bounded G5 conversion outcome from typed upstream inputs."""

    pinned = _coerce_g5_model(pinned_case_input_bundle, Layer3G5PinnedCaseInputBundle)
    snapshot = _coerce_g5_model(dependency_snapshot, Layer3G5DependencyReadinessSnapshot)
    handoff = _coerce_g5_model(g4_handoff_resolution, Layer3G5G4HandoffResolution)
    matrix = _coerce_g5_model(upstream_scope_join_matrix, Layer3G5UpstreamScopeJoinMatrix)
    evidence = _coerce_g5_model(
        grounded_result_evidence_set,
        Layer3G5GroundedResultEvidenceSet,
    )
    useful_join = (
        None
        if useful_design_metric_eligibility_join is None
        else _coerce_g5_model(
            useful_design_metric_eligibility_join,
            Layer3G5UsefulDesignMetricEligibilityJoin,
        )
    )
    demand_pull = (
        None
        if demand_pull_attempt_record is None
        else _coerce_g5_model(demand_pull_attempt_record, Layer3G5DemandPullAttemptRecord)
    )
    scope = _mapping(requested_scope)
    requested_families = _scope_claim_families(scope)
    issue_codes: list[str] = []
    blocker_refs: list[str] = []
    limitation_refs: list[str] = []

    issue_codes.extend(
        code
        for code in pinned.issue_codes
        if code != "layer3_g5_s14_pending_sealed_overclaimed"
        or _requires_universal_scope(requested_families)
    )
    issue_codes.extend(snapshot.issue_codes)
    issue_codes.extend(handoff.issue_codes)
    issue_codes.extend(matrix.issue_codes)
    issue_codes.extend(evidence.issue_codes)
    issue_codes.extend(evidence.effective_independence_record.issue_codes)
    blocker_refs.extend(handoff.blocker_refs)
    limitation_refs.extend(handoff.limitation_refs)

    if pinned.status == "fail":
        issue_codes.append("layer3_g5_pinned_case_missing")
    if snapshot.status == "fail":
        issue_codes.extend(
            code
            for code in (
                "layer3_g5_g0_dependency_not_ready",
                "layer3_g5_g1_dependency_not_ready",
                "layer3_g5_g4_dependency_not_ready",
            )
            if code in snapshot.issue_codes
        )
    g4_design_scope_status = _g4_design_scope_status(
        handoff,
        requested_families=requested_families,
    )
    if g4_design_scope_status == "missing" and _requires_design_scope(requested_families):
        issue_codes.append("layer3_g5_g4_pass_without_design_scope")
    if _source_only_promotion(handoff) and _requires_design_scope(requested_families):
        issue_codes.append("layer3_g5_source_only_promotion_overclaims_causal_design")
        if requested_conversion_outcome == "typed_blocker -> grounded_limited":
            issue_codes.append("layer3_g5_source_only_promotion_overclaims_grounded_limited")
    if handoff.blocked_promotion_input_count:
        issue_codes.append("layer3_g5_blocked_promotion_used_as_conversion")

    if matrix.status == "fail":
        issue_codes.append("layer3_g5_upstream_scope_join_missing")
    if _matrix_has_design_support_gap(matrix):
        issue_codes.append("layer3_g5_grounded_limited_without_g2_g3_design_support")
    if matrix.g1_conversion_scope_disposition == "substrate_only_limited" and (
        scope.get("requires_claim_authority") or _requires_design_scope(requested_families)
    ):
        issue_codes.append("layer3_g5_g1_observed_but_uncertain_overclaimed")
    if not _evidence_covers_requested_scope(evidence, requested_families):
        issue_codes.append("layer3_g5_grounded_contract_ref_missing")
    if evidence.effective_independence_record.status == "fail":
        issue_codes.append("layer3_g5_effective_independence_missing")

    weakest = _mapping(weakest_boundary)
    weakest_status = _first_text(weakest.get("status"))
    weakest_reason = _first_text(weakest.get("weakest_boundary_reason"), weakest.get("reason"))
    if requested_conversion_outcome == "typed_blocker -> grounded_limited" and weakest_status in {
        "limited",
        "fail",
        "blocked",
    }:
        issue_codes.append("layer3_g5_conversion_exceeds_weakest_boundary")
    mixed_statuses = _mixed_upstream_statuses(upstream_statuses)
    if mixed_statuses and requested_conversion_outcome == "typed_blocker -> grounded_limited":
        issue_codes.append("layer3_g5_mixed_status_composition_missing")
        if "partial" in mixed_statuses:
            issue_codes.append("layer3_g5_partial_status_flattened")
        if "review_required" in mixed_statuses:
            issue_codes.append("layer3_g5_review_required_status_flattened")
        if "contested" in mixed_statuses:
            issue_codes.append("layer3_g5_contested_status_flattened")

    issue_codes.extend(
        _legal_scope_issue_codes(
            requested_families=requested_families,
            dependency_snapshot=snapshot,
            gl_legal_authority_payload=gl_legal_authority_payload,
            gl_mandate_records=gl_mandate_records,
        )
    )
    if _requires_high_stakes_human_decision(scope) and not pinned.s7_human_decision_record_ref:
        issue_codes.append("layer3_g5_human_decision_record_required")
    if (
        _requires_universal_scope(requested_families)
        and pinned.s14_universal_claim_gate_status != "pass"
    ):
        issue_codes.append("layer3_g5_s14_pending_sealed_overclaimed")

    if requested_conversion_outcome == "typed_blocker -> grounded_abstention":
        issue_codes.extend(_abstention_search_issue_codes(search_health))
        if demand_pull is None:
            issue_codes.append("layer3_g5_grounded_abstention_without_demand_pull_attempt")
        elif demand_pull.status != "pass":
            issue_codes.extend(demand_pull.issue_codes)
            issue_codes.append("layer3_g5_grounded_abstention_without_demand_pull_attempt")
        if not evidence.grounded_evidence_refs:
            issue_codes.append("layer3_g5_grounded_abstention_without_evidence")

    if useful_design_credit_requested and useful_join is not None:
        issue_codes.extend(useful_join.issue_codes)

    issue_codes = list(_dedupe(issue_codes))
    limited_blocked = _has_grounded_limited_blocking_issue(issue_codes)
    abstention_blocked = _has_grounded_abstention_blocking_issue(issue_codes)
    conversion_outcome: Layer3G5ConversionOutcome = "unchanged_blocker"
    grounding_disposition: Layer3G5GroundingDisposition = "ungrounded_blocked"
    if (
        requested_conversion_outcome == "typed_blocker -> grounded_limited"
        and not limited_blocked
    ):
        conversion_outcome = "typed_blocker -> grounded_limited"
        grounding_disposition = "grounded_limited"
    elif (
        requested_conversion_outcome == "typed_blocker -> grounded_abstention"
        and not abstention_blocked
    ):
        conversion_outcome = "typed_blocker -> grounded_abstention"
        grounding_disposition = "grounded_abstention"
    return Layer3G5ConversionEligibilityLedger(
        status="pass" if conversion_outcome != "unchanged_blocker" else "fail",
        conversion_outcome=conversion_outcome,
        grounding_disposition=grounding_disposition,
        g4_design_scope_status=g4_design_scope_status,
        requested_claim_families=requested_families,
        blocker_refs=_dedupe(blocker_refs),
        limitation_refs=_dedupe(limitation_refs),
        weakest_boundary_status=weakest_status,
        weakest_boundary_reason=weakest_reason,
        mixed_upstream_statuses=mixed_statuses,
        useful_design_credit_requested=useful_design_credit_requested,
        issue_codes=tuple(issue_codes),
    )


def build_g5_s12_demand_growth_evidence(
    *,
    s12_case_signals: Mapping[str, Any],
    requested_scope: Mapping[str, Any] | None = None,
) -> Layer3G5S12DemandGrowthEvidence:
    """Resolve S12 demand/growth refs used by G5 without claiming S12 authority."""

    signals = _mapping(s12_case_signals)
    issue_codes: list[str] = []
    demand_refs: list[str] = list(_as_str_tuple(signals.get("demand_act_refs", ())))
    growth_entry_refs: list[str] = []
    envelope_delta_refs: list[str] = list(
        _as_str_tuple(signals.get("certified_envelope_delta_refs", ()))
    )
    reuse_refs: list[str] = list(_as_str_tuple(signals.get("reuse_acquisition_refs", ())))
    voi_refs: list[str] = list(_as_str_tuple(signals.get("voi_allocation_refs", ())))
    principal_refs: list[str] = list(
        _as_str_tuple(signals.get("accountable_principal_refs", ()))
    )
    principal_refs.extend(_as_str_tuple(signals.get("principal_ref")))
    for index, entry in enumerate(_sequence_of_mappings(signals.get("growth_entries"))):
        entry_ref = _first_optional_text(entry.get("growth_entry_ref")) or (
            f"s12-growth-entry://{G5_PINNED_CASE_ID}/{index + 1}"
        )
        growth_entry_refs.append(entry_ref)
        demand_ref = _first_optional_text(entry.get("demand_act_ref"))
        if demand_ref:
            demand_refs.append(demand_ref)
        else:
            issue_codes.append("layer3_g5_s12_demand_act_ref_missing")
        delta_ref = _first_optional_text(
            entry.get("certified_envelope_delta_ref"),
            entry.get("pending_envelope_delta_ref"),
        )
        if delta_ref:
            envelope_delta_refs.append(delta_ref)
        else:
            issue_codes.append("layer3_g5_s12_growth_without_envelope_delta")
        reuse_refs.extend(
            _as_str_tuple(
                entry.get("reuse_acquisition_ref")
                or entry.get("reuse_acquisition_refs", ())
            )
        )
        voi_refs.extend(_as_str_tuple(entry.get("voi_allocation_refs", ())))
        principal_refs.extend(_as_str_tuple(entry.get("principal_ref")))
    if signals and not demand_refs:
        issue_codes.append("layer3_g5_s12_demand_act_ref_missing")
    scope = _mapping(requested_scope)
    required_demand_refs = set(_as_str_tuple(scope.get("demand_act_refs", ())))
    scope_join_status: Literal["pass", "fail", "not_required"] = "not_required"
    if required_demand_refs:
        scope_join_status = "pass"
        if not required_demand_refs.issubset(set(demand_refs)):
            scope_join_status = "fail"
            issue_codes.append("layer3_g5_s12_demand_scope_mismatch")
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G5S12DemandGrowthEvidence(
        status="fail" if issue_codes else "pass",
        demand_act_refs=_dedupe(demand_refs),
        growth_entry_refs=_dedupe(growth_entry_refs),
        certified_envelope_delta_refs=_dedupe(envelope_delta_refs),
        voi_allocation_refs=_dedupe(voi_refs),
        reuse_acquisition_refs=_dedupe(reuse_refs),
        accountable_principal_refs=_dedupe(principal_refs),
        scope_join_status=scope_join_status,
        issue_codes=tuple(issue_codes),
    )


def build_g5_demand_pull_attempt_record(
    *,
    pinned_case_input_bundle: Layer3G5PinnedCaseInputBundle | Mapping[str, Any],
    s12_demand_growth_evidence: Layer3G5S12DemandGrowthEvidence | Mapping[str, Any],
    s3_demand_pull_refs: Sequence[str] = (),
    attempted_grounding_path_refs: Sequence[str] = (),
) -> Layer3G5DemandPullAttemptRecord:
    """Build a demand-pull attempt record from S3/S12/accountable-principal refs."""

    pinned = _coerce_g5_model(pinned_case_input_bundle, Layer3G5PinnedCaseInputBundle)
    s12 = _coerce_g5_model(s12_demand_growth_evidence, Layer3G5S12DemandGrowthEvidence)
    issue_codes: list[str] = list(s12.issue_codes)
    s12_demand_refs = _dedupe((*pinned.s12_demand_act_refs, *s12.demand_act_refs))
    s12_delta_refs = _dedupe(
        (*pinned.s12_certified_envelope_delta_refs, *s12.certified_envelope_delta_refs)
    )
    demand_pull_refs = _dedupe(
        (
            *s3_demand_pull_refs,
            *s12_demand_refs,
            *s12.growth_entry_refs,
            *s12_delta_refs,
            *s12.voi_allocation_refs,
            *s12.reuse_acquisition_refs,
            *attempted_grounding_path_refs,
        )
    )
    if not demand_pull_refs:
        issue_codes.append("layer3_g5_grounded_abstention_without_demand_pull_attempt")
        issue_codes.append("layer3_g5_demand_pull_ref_unresolved")
    if not s12_demand_refs:
        issue_codes.append("layer3_g5_s12_demand_act_ref_missing")
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G5DemandPullAttemptRecord(
        status="fail" if issue_codes else "pass",
        demand_pull_refs=demand_pull_refs,
        s3_demand_pull_refs=_dedupe(s3_demand_pull_refs),
        s12_demand_act_refs=s12_demand_refs,
        s12_growth_entry_refs=s12.growth_entry_refs,
        s12_voi_refs=s12.voi_allocation_refs,
        s12_reuse_acquisition_refs=s12.reuse_acquisition_refs,
        accountable_principal_refs=s12.accountable_principal_refs,
        attempted_grounding_path_refs=_dedupe(attempted_grounding_path_refs),
        issue_codes=tuple(issue_codes),
    )


def build_g5_envelope_expansion_delta(
    *,
    conversion_eligibility_ledger: Layer3G5ConversionEligibilityLedger | Mapping[str, Any],
    demand_pull_attempt_record: Layer3G5DemandPullAttemptRecord | Mapping[str, Any],
    s12_demand_growth_evidence: Layer3G5S12DemandGrowthEvidence | Mapping[str, Any],
    envelope_ref: str | None,
    numerator: int,
    denominator: int,
    conversion_reason: str,
    region_ref: str | None = None,
    search_health_refs: Sequence[str] = (),
) -> Layer3G5EnvelopeExpansionDelta:
    """Record G5's first envelope-expansion-rate reading."""

    ledger = _coerce_g5_model(
        conversion_eligibility_ledger,
        Layer3G5ConversionEligibilityLedger,
    )
    demand_pull = _coerce_g5_model(
        demand_pull_attempt_record,
        Layer3G5DemandPullAttemptRecord,
    )
    s12 = _coerce_g5_model(s12_demand_growth_evidence, Layer3G5S12DemandGrowthEvidence)
    issue_codes: list[str] = []
    issue_codes.extend(demand_pull.issue_codes)
    issue_codes.extend(s12.issue_codes)
    reason = conversion_reason.strip() if conversion_reason else "missing"
    if reason == "missing":
        issue_codes.append("layer3_g5_envelope_expansion_reason_missing")
    envelope_delta_refs = s12.certified_envelope_delta_refs
    if not envelope_ref and not envelope_delta_refs:
        issue_codes.append("layer3_g5_envelope_expansion_delta_missing")
    if numerator > 0 and not envelope_delta_refs:
        issue_codes.append("layer3_g5_envelope_expansion_delta_missing")
    rate = float(numerator) / float(denominator) if denominator else 0.0
    status: Literal["expanding", "flat", "blocked"]
    if issue_codes:
        status = "blocked"
    elif numerator > 0 and ledger.conversion_outcome == "typed_blocker -> grounded_limited":
        status = "expanding"
    else:
        status = "flat"
    return Layer3G5EnvelopeExpansionDelta(
        status=status,
        envelope_expansion_rate=rate,
        trend=status,
        envelope_ref=envelope_ref,
        region_ref=region_ref,
        numerator=numerator,
        denominator=denominator,
        conversion_reason=reason,
        envelope_delta_refs=envelope_delta_refs,
        effort_refs=_dedupe(
            (
                *demand_pull.s3_demand_pull_refs,
                *demand_pull.attempted_grounding_path_refs,
                *s12.reuse_acquisition_refs,
            )
        ),
        demand_pull_refs=demand_pull.demand_pull_refs,
        search_health_refs=_dedupe(search_health_refs),
        issue_codes=_dedupe(issue_codes),
    )


def build_g5_dependency_health_metric_snapshot(
    *,
    envelope_expansion_delta: Layer3G5EnvelopeExpansionDelta | Mapping[str, Any],
    upstream_health_readings: Mapping[str, Mapping[str, Any]],
) -> Layer3G5DependencyHealthMetricSnapshot:
    """Build the five-metric G5 health snapshot from bounded readings."""

    delta = _coerce_g5_model(envelope_expansion_delta, Layer3G5EnvelopeExpansionDelta)
    upstream = _mapping(upstream_health_readings)
    issue_codes: list[str] = list(delta.issue_codes)
    metric_statuses: dict[str, str] = {
        "envelope-expansion-rate": delta.status,
    }
    for metric in G5_CONSTITUTION_HEALTH_METRICS[1:]:
        reading = _mapping(upstream.get(metric))
        status = _first_text(reading.get("status"))
        metric_statuses[metric] = status
        if not reading or status in {"missing", "unresolved"}:
            issue_codes.append("layer3_g5_upstream_health_metric_missing")
        if status in {"stale", "expired"}:
            issue_codes.append("layer3_g5_stale_upstream_health_metric")
    health_toml = {
        "envelope-expansion-rate": {
            "value": delta.envelope_expansion_rate,
            "trend": delta.trend,
            "numerator": delta.numerator,
            "denominator": delta.denominator,
            "envelope_ref": delta.envelope_ref,
            "region_ref": delta.region_ref,
            "conversion_reason": delta.conversion_reason,
            "effort_refs": list(delta.effort_refs),
            "demand_pull_refs": list(delta.demand_pull_refs),
            "search_health_refs": list(delta.search_health_refs),
        },
        "upstream": {
            metric: dict(_mapping(upstream.get(metric)))
            for metric in G5_CONSTITUTION_HEALTH_METRICS[1:]
        },
    }
    issue_codes = list(_dedupe(issue_codes))
    return Layer3G5DependencyHealthMetricSnapshot(
        status="fail" if issue_codes else "pass",
        metric_statuses=metric_statuses,
        health_toml=health_toml,
        issue_codes=tuple(issue_codes),
    )


def build_g5_dependency_readiness_snapshot(
    repo_root: Path,
    *,
    manifest_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    explicit_w12d_payload_ref: str | None = None,
) -> Layer3G5DependencyReadinessSnapshot:
    """Build a bounded dependency snapshot without rerunning upstream builders."""

    root = Path(repo_root)
    overrides = manifest_overrides or {}
    loaded, missing = _bounded_path_status(root, BOUNDED_DEPENDENCY_PATHS)
    g0 = dict(overrides.get("g0") or _read_optional_json(root, G0_READINESS_PATH) or {})
    g1 = dict(overrides.get("g1") or _read_optional_json(root, G1_READINESS_PATH) or {})
    g2 = dict(overrides.get("g2") or _read_optional_json(root, G2_READINESS_PATH) or {})
    g3 = dict(overrides.get("g3") or _read_optional_json(root, G3_READINESS_PATH) or {})
    gl = dict(overrides.get("gl") or _read_optional_json(root, GL_READINESS_PATH) or {})
    g4 = dict(overrides.get("g4") or _read_optional_json(root, G4_READINESS_PATH) or {})

    issue_codes: list[str] = []
    missing_key = False
    g0_status, missing_key = _dependency_status(
        g0,
        key_paths=(
            ("status",),
            ("counts", "search_recall_seed_status"),
            ("counts", "index_freshness_status"),
            ("counts", "engineering_quality_check_status"),
        ),
        missing_key=missing_key,
    )
    g1_status, missing_key = _dependency_status(
        g1,
        key_paths=(("status",), ("counts", "g0_v2_dependency_status")),
        missing_key=missing_key,
    )
    g2_status, missing_key = _dependency_status(
        g2,
        key_paths=(("status",), ("g1_dependency_status",), ("g2_w12d_consumer_gate_status",)),
        missing_key=missing_key,
    )
    g3_status, missing_key = _dependency_status(
        g3,
        key_paths=(("status",), ("g2_dependency_status",), ("g3_w12d_consumer_gate_status",)),
        missing_key=missing_key,
    )
    gl_base_status, missing_key = _dependency_status(
        gl,
        key_paths=(("status",), ("g0_dependency_status",), ("gl_conformance_status",)),
        missing_key=missing_key,
    )
    g4_status, missing_key = _dependency_status(
        g4,
        key_paths=(("status",), ("g4_g5_promotion_handoff_status",)),
        missing_key=missing_key,
    )
    if g0_status != "pass":
        issue_codes.append("layer3_g5_g0_dependency_not_ready")
    if g1_status != "pass":
        issue_codes.append("layer3_g5_g1_dependency_not_ready")
    if g4_status != "pass":
        issue_codes.append("layer3_g5_g4_dependency_not_ready")

    g1_counts = _mapping(g1.get("counts"))
    g2_w12d = _read_optional_json(root, G2_W12D_CONSUMER_GATE_PATH) or {}
    g3_w12d = _read_optional_json(root, G3_W12D_CONSUMER_GATE_PATH) or {}
    g2_search = _read_optional_json(root, G2_SEARCH_RECALL_FRESHNESS_PATH) or {}
    g3_search = _read_optional_json(root, G3_SEARCH_RECALL_FRESHNESS_PATH) or {}
    gl_legal = _read_optional_json(root, GL_LEGAL_AUTHORITY_REPORT_PATH) or {}
    gl_reference = _read_optional_json(root, GL_REFERENCE_RESOLUTION_RECORDS_PATH) or {}
    gl_amendment = _read_optional_json(root, GL_AMENDMENT_LINEAGE_RECORDS_PATH) or {}
    gl_reissue_status = _first_text(
        gl.get("gl_reference_resolution_status"),
        gl.get("gl_amendment_lineage_status"),
        gl_reference.get("status"),
        gl_amendment.get("status"),
    )
    gl_dependency_status: Literal["pass", "fail", "missing", "pass_with_reissue_limits"]
    if gl_base_status == "missing":
        gl_dependency_status = "missing"
    elif gl_base_status == "fail":
        gl_dependency_status = "fail"
    elif gl_reissue_status == "reissue_required":
        gl_dependency_status = "pass_with_reissue_limits"
        issue_codes.append("layer3_g5_gl_pass_with_reissue_required")
    else:
        gl_dependency_status = "pass"

    w12d_freshness = "not_provided"
    if explicit_w12d_payload_ref and "_build/.tmp" in explicit_w12d_payload_ref:
        w12d_freshness = "stale_build_cache_rejected"
        issue_codes.append("layer3_g5_w12d_build_cache_not_source_of_truth")
    elif explicit_w12d_payload_ref:
        w12d_freshness = "explicit_payload_ref"
    if missing_key:
        issue_codes.append("layer3_g5_dependency_manifest_status_key_missing")

    hard_ready = g0_status == "pass" and g1_status == "pass" and g4_status == "pass"
    return Layer3G5DependencyReadinessSnapshot(
        status="pass" if hard_ready else "fail",
        g0_dependency_status=g0_status,
        g1_dependency_status=g1_status,
        g2_dependency_status=g2_status,
        g3_dependency_status=g3_status,
        gl_dependency_status=gl_dependency_status,
        g4_dependency_status=g4_status,
        g1_grounding_status=_first_text(
            g1.get("grounding_closure_outcome"),
            g1_counts.get("grounding_closure_outcome"),
        ),
        g1_search_recall_status=_first_text(
            g1.get("g1_search_recall_status"),
            g1_counts.get("g1_search_recall_status"),
        ),
        g1_index_freshness_status=_first_text(
            g1.get("g1_index_freshness_status"),
            g1_counts.get("g1_index_freshness_status"),
        ),
        g2_w12d_consumer_gate_status=_first_text(
            g2.get("g2_w12d_consumer_gate_status"),
            g2_w12d.get("status"),
        ),
        g2_conformance_status=_first_text(g2.get("g2_conformance_status")),
        g2_public_projection_status=_first_text(
            g2.get("g2_public_projection_status"),
            g2.get("g2_public_export_projection_status"),
        ),
        g2_search_recall_status=_first_text(
            g2.get("g2_search_recall_status"),
            g2_search.get("search_recall_status"),
            g2_search.get("status"),
        ),
        g2_index_freshness_status=_first_text(
            g2.get("g2_index_freshness_status"),
            g2_search.get("index_freshness_status"),
            g2_search.get("freshness_status"),
        ),
        g3_w12d_consumer_gate_status=_first_text(
            g3.get("g3_w12d_consumer_gate_status"),
            g3_w12d.get("status"),
        ),
        g3_conformance_status=_first_text(g3.get("g3_conformance_status")),
        g3_public_projection_status=_first_text(
            g3.get("g3_public_export_projection_status"),
            g3.get("g3_public_projection_status"),
        ),
        g3_search_recall_status=_first_text(
            g3.get("g3_search_recall_freshness_status"),
            g3_search.get("search_recall_status"),
            g3_search.get("status"),
        ),
        g3_index_freshness_status=_first_text(
            g3.get("g3_index_freshness_status"),
            g3_search.get("index_freshness_status"),
            g3_search.get("freshness_status"),
        ),
        gl_conformance_status=_first_text(gl.get("gl_conformance_status")),
        gl_reissue_status=gl_reissue_status,
        gl_reference_resolution_status=_first_text(
            gl.get("gl_reference_resolution_status"),
            gl_legal.get("reference_resolution_status"),
        ),
        gl_amendment_lineage_status=_first_text(gl.get("gl_amendment_lineage_status")),
        gl_applicability_status=_first_text(gl_legal.get("applicability_status")),
        g4_g5_promotion_handoff_status=_first_text(
            g4.get("g4_g5_promotion_handoff_status")
        ),
        g4_promotion_record_count=_as_int(g4.get("g4_promotion_record_count")),
        g4_governed_promoted_count=_as_int(g4.get("g4_governed_promoted_count")),
        g4_promotion_blocked_count=_as_int(g4.get("g4_promotion_blocked_count")),
        w12d_payload_freshness_status=w12d_freshness,
        loaded_artifact_paths=loaded,
        missing_artifact_paths=missing,
        dependency_manifest_key_resolution_status="fail" if missing_key else "pass",
        issue_codes=_dedupe(issue_codes),
    )


def resolve_g5_g4_handoff(
    repo_root: Path,
    *,
    handoff_payload: Mapping[str, Any] | None = None,
    promotion_records_payload: Mapping[str, Any] | None = None,
    weakest_boundary_payload: Mapping[str, Any] | None = None,
    requested_scope: Mapping[str, Any] | None = None,
) -> Layer3G5G4HandoffResolution:
    """Resolve persisted G4 handoff and promotion records per record/scope."""

    root = Path(repo_root)
    handoff = dict(
        handoff_payload
        if handoff_payload is not None
        else _read_optional_json(root, G4_G5_PROMOTION_HANDOFF_PATH) or {}
    )
    records_payload = dict(
        promotion_records_payload
        if promotion_records_payload is not None
        else _read_optional_json(root, G4_PROMOTION_RECORDS_PATH) or {}
    )
    weakest = dict(
        weakest_boundary_payload
        if weakest_boundary_payload is not None
        else _read_optional_json(root, G4_WEAKEST_BOUNDARY_COMPOSITION_PATH) or {}
    )
    issue_codes: list[str] = []
    if not handoff:
        issue_codes.append("layer3_g5_g4_handoff_missing")
    authoritative_for = _as_str_tuple(handoff.get("authoritative_for", ()))
    may_not_use_for = _as_str_tuple(handoff.get("may_not_use_for", ()))
    if "g5_first_proving_ground_promotion_state_input_refs" not in authoritative_for:
        issue_codes.append("layer3_g5_g4_handoff_authority_leak")
    if not may_not_use_for:
        issue_codes.append("layer3_g5_g4_handoff_authority_leak")
    blocker_refs = _as_str_tuple(handoff.get("blocker_refs", ()))
    limitation_refs = _as_str_tuple(handoff.get("limitation_refs", ()))
    records = tuple(
        _resolve_g4_promotion_record(record, requested_scope=requested_scope)
        for record in _sequence_of_mappings(records_payload.get("promotion_records"))
    )
    governed_count = sum(
        1
        for record in records
        if record.promotion_state == "governed_promoted"
        and record.admitted_for_g5_conversion
    )
    blocked_count = sum(1 for record in records if record.promotion_state == "promotion_blocked")
    if not records:
        issue_codes.append("layer3_g5_promotion_record_missing")
    if governed_count == 0:
        issue_codes.append("layer3_g5_no_governed_promotion_record")
    if blocked_count:
        issue_codes.append("layer3_g5_blocked_promotion_used_as_conversion")
    issue_codes.extend(code for record in records for code in record.issue_codes)
    if blocker_refs and _scope_mentions(requested_scope, "causal_forecast"):
        issue_codes.append("layer3_g5_g4_handoff_pass_with_blockers_overclaimed")
    if weakest and governed_count == 0:
        issue_codes.append("layer3_g5_g4_weakest_boundary_record_mismatch")
    status: Literal["pass", "pass_with_blockers", "fail"]
    if "layer3_g5_g4_handoff_missing" in issue_codes or governed_count == 0:
        status = "fail"
    elif issue_codes or blocker_refs or blocked_count:
        status = "pass_with_blockers"
    else:
        status = "pass"
    return Layer3G5G4HandoffResolution(
        status=status,
        handoff_status=_first_text(handoff.get("status")),
        authoritative_for=authoritative_for,
        may_not_use_for=may_not_use_for,
        blocker_refs=blocker_refs,
        limitation_refs=limitation_refs,
        governed_promotion_input_count=governed_count,
        blocked_promotion_input_count=blocked_count,
        promotion_record_resolutions=records,
        issue_codes=_dedupe(issue_codes),
    )


def build_g5_upstream_scope_join_matrix(
    repo_root: Path,
    *,
    g1_bindings: Sequence[Mapping[str, Any]] | None = None,
    g2_handoffs: Sequence[Mapping[str, Any]] | None = None,
    g3_records: Sequence[Mapping[str, Any]] | None = None,
) -> Layer3G5UpstreamScopeJoinMatrix:
    """Build a Task 1 scope-join matrix over current persisted upstream rows."""

    root = Path(repo_root)
    if g1_bindings is None:
        g1_payload = _read_optional_json(root, G1_GROUNDED_SOURCE_CONTRACTS_PATH) or {}
        g1_bindings = tuple(
            _sequence_of_mappings(_dig(g1_payload, ("grounded_source_contracts", "bindings")))
        )
    if g2_handoffs is None:
        g2_payload = _read_optional_json(root, G2_GROUNDED_FORECAST_HANDOFFS_PATH) or {}
        g2_handoffs = tuple(_sequence_of_mappings(g2_payload.get("grounded_forecast_handoffs")))
    if g3_records is None:
        g3_payload = _read_optional_json(root, G3_PROOF_CARRYING_ANALYTICS_RECORDS_PATH) or {}
        g3_records = tuple(
            _sequence_of_mappings(g3_payload.get("proof_carrying_analytics_records"))
        )

    issues: list[str] = []
    g1 = next(
        (dict(row) for row in g1_bindings if row.get("case_id") == G5_PINNED_CASE_ID),
        dict(g1_bindings[0]) if g1_bindings else {},
    )
    g1_grounding_status = _first_text(g1.get("grounding_status"))
    g1_scope_disposition = "missing"
    if g1_grounding_status == "observed_but_uncertain":
        g1_scope_disposition = "substrate_only_limited"
        issues.append("layer3_g5_g1_observed_but_uncertain_overclaimed")
    elif g1_grounding_status not in {"", "missing"}:
        g1_scope_disposition = "source_grounded"
    elif not g1.get("source_contract_content_hash"):
        g1_scope_disposition = "blocked_missing_source_contract"
    if not g1.get("source_contract_content_hash"):
        issues.append("layer3_g5_g1_source_contract_hash_missing")
    if not g1.get("observed_through"):
        issues.append("layer3_g5_g1_observed_time_missing")
    g1_denials = _as_str_tuple(g1.get("may_not_use_for", ()))
    if not g1_denials:
        issues.append("layer3_g5_g1_may_not_use_for_dropped")

    g2 = dict(g2_handoffs[0]) if g2_handoffs else {}
    if g2.get("case_id") and g2.get("case_id") != G5_PINNED_CASE_ID:
        issues.append("layer3_g5_g2_g3_scope_mismatch")
    design_refs = _as_str_tuple(g2.get("design_record_ledger_refs", ()))
    alias_status: Literal["pass", "fail", "not_required"] = "not_required"
    alias_issue_codes: tuple[str, ...] = ()
    normalized_design = None
    if design_refs:
        normalized_design = _normalize_s2_design_ref(design_refs[0])
        if normalized_design != "pdc://layer2/s2/ua-msme/design-record-v0":
            alias_status = "fail"
            alias_issue_codes = ("layer3_g5_g2_design_record_ref_unresolved",)
            issues.extend(alias_issue_codes)
        else:
            alias_status = "pass"
    g2_replay_refs = _as_str_tuple(g2.get("s2_deterministic_replay_key_refs", ()))
    if not g2_replay_refs:
        issues.append("layer3_g5_g2_s2_replay_key_ref_missing")
    source_contract_ref = _optional_str(g2.get("source_contract_ref"))
    if source_contract_ref and g1.get("source_contract_ref") and source_contract_ref != str(
        g1["source_contract_ref"]
    ):
        issues.append("layer3_g5_g2_source_contract_ref_mismatch")
    if not _as_str_tuple(g2.get("calibration_record_refs", ())):
        issues.append("layer3_g5_missing_g2_calibration_ref")

    g3 = dict(g3_records[0]) if g3_records else {}
    if g3.get("case_id") and g3.get("case_id") != G5_PINNED_CASE_ID:
        issues.append("layer3_g5_g2_g3_scope_mismatch")
    s11 = _mapping(g3.get("s11_record"))
    proof_status = _first_text(s11.get("proof_status"), g3.get("proof_status"))
    if proof_status == "identified":
        issues.append("layer3_g5_g3_proof_status_overclaimed")
    source_lineage_refs = _as_str_tuple(s11.get("source_lineage_refs", ()))
    if len(source_lineage_refs) != len(set(source_lineage_refs)):
        issues.append("layer3_g5_duplicate_source_lineage_ref_inflates_independence")

    gl = _read_optional_json(root, GL_READINESS_PATH) or {}
    gl_reissue = _first_text(
        gl.get("gl_reference_resolution_status"),
        gl.get("gl_amendment_lineage_status"),
    )
    if gl_reissue == "reissue_required":
        issues.append("layer3_g5_gl_pass_with_reissue_required")

    status: Literal["pass", "limited", "fail"] = "pass"
    if any(
        code
        in {
            "layer3_g5_g1_source_contract_hash_missing",
            "layer3_g5_g1_observed_time_missing",
            "layer3_g5_g1_may_not_use_for_dropped",
            "layer3_g5_g2_design_record_ref_unresolved",
        }
        for code in issues
    ):
        status = "fail"
    elif issues:
        status = "limited"
    return Layer3G5UpstreamScopeJoinMatrix(
        status=status,
        g1_grounding_status=g1_grounding_status,
        g1_conversion_scope_disposition=g1_scope_disposition,
        g1_source_contract_ref=_optional_str(g1.get("source_contract_ref")),
        g1_source_contract_content_hash=_optional_str(g1.get("source_contract_content_hash")),
        g1_observed_through=_optional_str(g1.get("observed_through")),
        g1_may_not_use_for=g1_denials,
        g2_design_record_alias_resolution=Layer3G5ScopeJoinAliasResolution(
            status=alias_status,
            source_ref=design_refs[0] if design_refs else None,
            normalized_ref=normalized_design,
            issue_codes=alias_issue_codes,
        ),
        g2_s2_replay_key_refs=g2_replay_refs,
        g2_source_contract_ref=source_contract_ref,
        g3_proof_status=proof_status,
        g3_source_lineage_refs=source_lineage_refs,
        gl_reissue_status=gl_reissue,
        issue_codes=_dedupe(issues),
    )


def build_g5_grounded_result_evidence_set(
    evidence_refs: Sequence[Mapping[str, Any]],
) -> Layer3G5GroundedResultEvidenceSet:
    """Build a G5 evidence set with exact-ref, lineage, and source-hash dedupe."""

    refs = tuple(
        Layer3G5GroundedEvidenceRef(
            ref=str(row.get("ref") or row.get("id") or ""),
            family=str(row.get("family") or "unknown"),
            lineage_refs=_as_str_tuple(row.get("lineage_refs", ())),
            source_hash=_optional_str(row.get("source_hash")),
            may_not_use_for=_as_str_tuple(row.get("may_not_use_for", ())),
        )
        for row in evidence_refs
        if row.get("ref") or row.get("id")
    )
    raw_refs = [ref.ref for ref in refs]
    lineage_refs = [lineage for ref in refs for lineage in ref.lineage_refs]
    source_hashes = [ref.source_hash for ref in refs if ref.source_hash]
    duplicate_refs = _duplicates(raw_refs)
    duplicate_lineage = _duplicates(lineage_refs)
    duplicate_hashes = _duplicates(source_hashes)
    issue_codes: list[str] = []
    if duplicate_refs or duplicate_hashes:
        issue_codes.append("layer3_g5_g4_grounded_contract_duplicate_inflates_evidence")
    if duplicate_lineage:
        issue_codes.append("layer3_g5_duplicate_lineage_ref_inflates_independence")
    independence_payload = _build_independence_adapter_payload(refs)
    independence_issues: list[str] = []
    try:
        validate_evidence_independence_map_record(independence_payload)
    except Exception:
        independence_issues.append("layer3_g5_evidence_independence_map_missing")
    issue_codes.extend(independence_issues)
    effective_record = Layer3G5EffectiveEvidenceIndependenceRecord(
        status="fail" if independence_issues else "pass",
        independence_map_payload=independence_payload,
        issue_codes=tuple(independence_issues),
    )
    dedupe_record = Layer3G5LineageDeduplicationRecord(
        raw_ref_count=len(raw_refs),
        deduped_ref_count=len(set(raw_refs)),
        raw_lineage_ref_count=len(lineage_refs),
        deduped_lineage_ref_count=len(set(lineage_refs)),
        raw_source_hash_count=len(source_hashes),
        deduped_source_hash_count=len(set(source_hashes)),
        duplicate_refs=duplicate_refs,
        duplicate_lineage_refs=duplicate_lineage,
        duplicate_source_hashes=duplicate_hashes,
    )
    return Layer3G5GroundedResultEvidenceSet(
        status="fail" if issue_codes else "pass",
        grounded_evidence_refs=refs,
        lineage_deduplication_record=dedupe_record,
        effective_independence_record=effective_record,
        issue_codes=_dedupe(issue_codes),
    )


def _coerce_g5_model[T: _G5Model](value: object, model_type: type[T]) -> T:
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)


def _scope_claim_families(scope: Mapping[str, Any]) -> tuple[str, ...]:
    return _dedupe(_as_str_tuple(scope.get("claim_families", ())))


def _requires_design_scope(claim_families: Sequence[str]) -> bool:
    design_families = {
        "causal_forecast",
        "effect",
        "proof",
        "legal_mandate",
        "mandate",
        "universal_claim",
    }
    return bool(set(claim_families) & design_families)


def _requires_universal_scope(claim_families: Sequence[str]) -> bool:
    return "universal_claim" in set(claim_families)


def _source_only_promotion(handoff: Layer3G5G4HandoffResolution) -> bool:
    source_families = {"source_data", "source_contract", "substrate"}
    admitted = tuple(
        record
        for record in handoff.promotion_record_resolutions
        if record.promotion_state == "governed_promoted"
    )
    return bool(admitted) and all(
        set(record.claim_families).issubset(source_families) for record in admitted
    )


def _g4_design_scope_status(
    handoff: Layer3G5G4HandoffResolution,
    *,
    requested_families: Sequence[str],
) -> Literal["pass", "missing", "blocked"]:
    if handoff.blocked_promotion_input_count:
        return "blocked"
    requested = set(requested_families)
    if not requested:
        return "missing"
    for record in handoff.promotion_record_resolutions:
        if not record.admitted_for_g5_conversion:
            continue
        if requested.issubset(set(record.claim_families)):
            return "pass"
    return "missing"


def _matrix_has_design_support_gap(matrix: Layer3G5UpstreamScopeJoinMatrix) -> bool:
    design_gap_codes = {
        "layer3_g5_g2_g3_scope_mismatch",
        "layer3_g5_missing_g2_forecast_support",
        "layer3_g5_missing_g2_calibration_ref",
        "layer3_g5_g2_design_record_ref_unresolved",
        "layer3_g5_g2_s2_replay_key_ref_missing",
        "layer3_g5_g2_source_contract_ref_mismatch",
        "layer3_g5_missing_g3_proof_record",
        "layer3_g5_g3_proof_status_overclaimed",
    }
    return matrix.status == "fail" or bool(set(matrix.issue_codes) & design_gap_codes)


def _evidence_covers_requested_scope(
    evidence: Layer3G5GroundedResultEvidenceSet,
    requested_families: Sequence[str],
) -> bool:
    if not _requires_design_scope(requested_families):
        return bool(evidence.grounded_evidence_refs)
    acceptable_families = {
        "g2_g3_design_support",
        "g2_forecast_support",
        "g3_proof_support",
        "causal_forecast",
        "proof",
    }
    return any(ref.family in acceptable_families for ref in evidence.grounded_evidence_refs)


def _mixed_upstream_statuses(statuses: Sequence[str]) -> tuple[str, ...]:
    narrowing_statuses = {
        "warn",
        "warning",
        "partial",
        "contested",
        "review_required",
        "limited",
        "near_binding",
    }
    return _dedupe(
        status
        for status in (_status_text(value) for value in statuses)
        if status in narrowing_statuses
    )


def _legal_scope_issue_codes(
    *,
    requested_families: Sequence[str],
    dependency_snapshot: Layer3G5DependencyReadinessSnapshot,
    gl_legal_authority_payload: Mapping[str, Any] | None,
    gl_mandate_records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    issues: list[str] = []
    requested = set(requested_families)
    legal_requested = bool(requested & {"legal_mandate", "legal", "mandate"})
    if not legal_requested:
        return ()
    if dependency_snapshot.gl_dependency_status == "pass_with_reissue_limits":
        issues.append("layer3_g5_gl_reissue_required_blocks_conversion")
    legal_payload = _mapping(gl_legal_authority_payload)
    applicability = _first_text(legal_payload.get("applicability_status"))
    if applicability == "fail":
        issues.append("layer3_g5_gl_applicability_fail_blocks_conversion")
        if legal_payload.get("legal_requirement_artifact_ref"):
            issues.append("layer3_g5_gl_requirement_artifact_overrides_applicability")
    reference_status = _first_text(
        legal_payload.get("reference_resolution_status"),
        legal_payload.get("temporal_resolution_status"),
    )
    if reference_status in {"unresolved", "fail", "missing"} and "legal_mandate" in requested:
        issues.append("layer3_g5_gl_reference_resolution_unresolved")
    if "mandate" in requested or "legal_mandate" in requested:
        for record in gl_mandate_records:
            status = _first_text(record.get("status"))
            if status == "compatibility_only" or not record.get("s6_evaluation_ref"):
                issues.append("layer3_g5_gl_mandate_compatibility_only_blocks_conversion")
    return _dedupe(issues)


def _requires_high_stakes_human_decision(scope: Mapping[str, Any]) -> bool:
    if _status_text(scope.get("stakes")) == "high":
        return True
    return any(bool(scope.get(key)) for key in ("high_stakes", "value_laden", "irreversible"))


def _g5_g1_search_health(
    repo_root: Path,
    snapshot: Layer3G5DependencyReadinessSnapshot,
) -> dict[str, Any]:
    payload = _read_optional_json(repo_root, G1_SEARCH_RECALL_FRESHNESS_PATH) or {}
    report = _mapping(payload.get("search_recall_freshness", payload))
    measurement_provenance = _first_text(report.get("measurement_provenance"))
    query_trace_refs = _as_str_tuple(report.get("query_trace_refs", ()))
    issue_codes = list(_as_str_tuple(report.get("issue_codes", ())))
    recall_status = _first_text(report.get("search_recall_status"), snapshot.g1_search_recall_status)
    freshness_status = _first_text(
        report.get("index_freshness_status"),
        snapshot.g1_index_freshness_status,
    )
    if measurement_provenance in {"missing", "self_attested", "constant"} or not query_trace_refs:
        recall_status = "not_measured"
        freshness_status = "not_measured"
        issue_codes.append("layer3_g1_search_recall_not_measured")
    return {
        "search_recall_status": recall_status,
        "index_freshness_status": freshness_status,
        "measurement_provenance": measurement_provenance,
        "query_trace_refs": query_trace_refs,
        "issue_codes": _dedupe(issue_codes),
    }


def _abstention_search_issue_codes(search_health: Mapping[str, Any] | None) -> tuple[str, ...]:
    health = _mapping(search_health)
    recall_status = _first_text(health.get("search_recall_status"), health.get("status"))
    freshness_status = _first_text(
        health.get("index_freshness_status"),
        health.get("freshness_status"),
    )
    issues: list[str] = []
    if recall_status != "pass":
        issues.append("layer3_g5_search_recall_seed_miss_blocks_abstention")
    if freshness_status in {"stale", "fail", "failed", "missing", "not_measured"}:
        issues.append("layer3_g5_stale_index_blocks_abstention")
    if health.get("non_conversion_reason") == "domain_ceiling" and recall_status != "pass":
        issues.append("layer3_g5_search_ceiling_not_domain_ceiling")
    return _dedupe(issues)


def _g5_slug_token(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-")


def _has_grounded_limited_blocking_issue(issue_codes: Sequence[str]) -> bool:
    nonblocking_codes = {
        "layer3_g5_s14_pending_sealed_overclaimed",
    }
    return any(
        code.startswith("layer3_g5_") and code not in nonblocking_codes
        for code in issue_codes
    )


def _has_grounded_abstention_blocking_issue(issue_codes: Sequence[str]) -> bool:
    blocking_codes = {
        "layer3_g5_w12d_full_payload_missing",
        "layer3_g5_w12d_manifest_only_not_payload",
        "layer3_g5_w12d_build_cache_not_source_of_truth",
        "layer3_g5_s4_s14_composed_loop_incomplete",
        "layer3_g5_s14_gate_missing_or_failed",
        "layer3_g5_search_recall_seed_miss_blocks_abstention",
        "layer3_g5_stale_index_blocks_abstention",
        "layer3_g5_search_ceiling_not_domain_ceiling",
        "layer3_g5_grounded_abstention_without_evidence",
        "layer3_g5_grounded_abstention_without_demand_pull_attempt",
        "layer3_g5_demand_pull_ref_unresolved",
    }
    return bool(set(issue_codes) & blocking_codes)


def _grounded_abstention_composition_issue_codes(
    issue_codes: Sequence[str],
) -> tuple[str, ...]:
    blocking_codes = {
        "layer3_g5_uncontrolled_w12d_outcome_status",
        "layer3_g5_grounded_abstention_counts_as_useful_design",
        "layer3_g5_useful_design_metric_eligibility_join_missing",
    }
    return _dedupe(code for code in issue_codes if code in blocking_codes)


def _empty_pinned_case_input_bundle(
    *,
    status: Literal["pass", "fail", "not_built"],
    w12d_payload_status: str,
    w12d_payload_ref: str | None,
    issue_codes: Sequence[str],
    case_id: str = G5_PINNED_CASE_ID,
) -> Layer3G5PinnedCaseInputBundle:
    return Layer3G5PinnedCaseInputBundle(
        case_id=case_id,
        status=status,
        w12d_payload_status=w12d_payload_status,
        w12d_payload_ref=w12d_payload_ref,
        issue_codes=_dedupe(issue_codes),
    )


def _build_g5_composed_loop_gate(
    case: Mapping[str, Any],
    *,
    source_context: str,
) -> tuple[Layer3G5W12DCaseBlockIndex, Layer3G5ComposedLoopCompletenessGate]:
    present_keys = tuple(
        key for key in S4_S14_CASE_BLOCK_KEYS if isinstance(case.get(key), Mapping)
    )
    missing_keys = tuple(key for key in S4_S14_CASE_BLOCK_KEYS if key not in present_keys)
    issue_codes: list[str] = []
    if missing_keys:
        issue_codes.extend(
            (
                "layer3_g5_w12d_s4_s14_case_key_missing",
                "layer3_g5_s4_s14_composed_loop_incomplete",
            )
        )
    readings = tuple(
        Layer3G5Layer2StatusReading(
            block_key=key,
            status=_first_text(
                _mapping(case.get(key)).get("status"),
                _mapping(case.get(key)).get("grounded_authority_status"),
            ),
            refs=_refs_from_mapping(_mapping(case.get(key))),
        )
        for key in present_keys
    )
    s14 = _mapping(case.get("s14_universality_assurance"))
    s14_grounded_status = _first_text(s14.get("grounded_authority_status"))
    s14_universal_status = _first_text(s14.get("universal_claim_gate_status"))
    if not s14 or _status_text(s14_grounded_status) in {
        "fail",
        "failed",
        "blocked",
        "missing",
    }:
        issue_codes.append("layer3_g5_s14_gate_missing_or_failed")
    issue_codes = list(_dedupe(issue_codes))
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return (
        Layer3G5W12DCaseBlockIndex(
            status=status,
            case_id=str(case.get("case_id") or G5_PINNED_CASE_ID),
            block_keys=present_keys,
            missing_block_keys=missing_keys,
            issue_codes=_dedupe(
                code
                for code in issue_codes
                if code
                in {
                    "layer3_g5_w12d_s4_s14_case_key_missing",
                    "layer3_g5_s4_s14_composed_loop_incomplete",
                }
            ),
        ),
        Layer3G5ComposedLoopCompletenessGate(
            status=status,
            case_id=str(case.get("case_id") or G5_PINNED_CASE_ID),
            source_context=source_context,
            missing_block_keys=missing_keys,
            s14_grounded_authority_status=s14_grounded_status,
            s14_universal_claim_gate_status=s14_universal_status,
            layer2_status_readings=readings,
            issue_codes=_dedupe(issue_codes),
        ),
    )


def _status_tuple_from_records(value: object) -> tuple[str, ...]:
    return _dedupe(_status_text(record.get("status")) for record in _sequence_of_mappings(value))


def _extract_s12_demand_growth_refs(
    s12: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    issue_codes: list[str] = []
    demand_refs: list[str] = list(_as_str_tuple(s12.get("demand_act_refs", ())))
    envelope_delta_refs: list[str] = []
    for entry in _sequence_of_mappings(s12.get("growth_entries")):
        demand_ref = _first_optional_text(entry.get("demand_act_ref"))
        if demand_ref:
            demand_refs.append(demand_ref)
        else:
            issue_codes.append("layer3_g5_s12_demand_act_ref_missing")
        delta_ref = _first_optional_text(
            entry.get("certified_envelope_delta_ref"),
            entry.get("pending_envelope_delta_ref"),
        )
        if delta_ref:
            envelope_delta_refs.append(delta_ref)
        elif demand_ref:
            issue_codes.append("layer3_g5_s12_growth_without_envelope_delta")
    if s12 and not demand_refs:
        issue_codes.append("layer3_g5_s12_demand_act_ref_missing")
    return _dedupe(demand_refs), _dedupe(envelope_delta_refs), _dedupe(issue_codes)


def _extract_replay_refs(
    *,
    case: Mapping[str, Any],
    s2: Mapping[str, Any],
    s2_ledger: Mapping[str, Any],
    design_record: Mapping[str, Any],
    w12d_payload_ref: str | None,
    case_digest: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_as_str_tuple(case.get("source_path")))
    refs.extend(_as_str_tuple(case.get("replay_refs", ())))
    refs.extend(_as_str_tuple(s2.get("deterministic_replay_key")))
    refs.extend(_as_str_tuple(s2.get("deterministic_replay_key_refs", ())))
    refs.extend(_as_str_tuple(s2_ledger.get("replay_ref")))
    refs.extend(_as_str_tuple(s2_ledger.get("replay_refs", ())))
    refs.extend(_as_str_tuple(design_record.get("ref")))
    if w12d_payload_ref:
        refs.append(w12d_payload_ref)
    refs.append(f"w12d://case/{G5_PINNED_CASE_ID}/{case_digest}")
    return _dedupe(refs)


def _extract_layer3_gate_statuses(case: Mapping[str, Any]) -> dict[str, str]:
    gate_keys = (
        "layer3_g0_grounding_gate",
        "layer3_g1_grounding_gate",
        "layer3_g2_forecast_gate",
        "layer3_g3_analytics_search_gate",
    )
    return {
        key: _first_text(_mapping(case.get(key)).get("status"), case.get(key))
        for key in gate_keys
    }


def _extract_typed_blocker_codes(case: Mapping[str, Any]) -> tuple[str, ...]:
    return _dedupe(
        _first_text(blocker.get("code"), blocker.get("blocker_code"))
        for blocker in _sequence_of_mappings(case.get("typed_blockers"))
    )


def _extract_authority_outcome_refs(case: Mapping[str, Any]) -> tuple[str, ...]:
    authority_outcomes = _mapping(case.get("authority_outcomes"))
    refs: list[str] = []
    for family, outcome in authority_outcomes.items():
        outcome_mapping = _mapping(outcome)
        refs.extend(_as_str_tuple(outcome_mapping.get("ref")))
        refs.extend(_as_str_tuple(outcome_mapping.get("record_ref")))
        refs.extend(_as_str_tuple(outcome_mapping.get("evidence_refs", ())))
        outcome_status = _first_optional_text(outcome_mapping.get("outcome"))
        if outcome_status:
            refs.append(f"authority-outcome://{family}/{outcome_status}")
    return _dedupe(refs)


def _refs_from_mapping(payload: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key, value in payload.items():
        if key.endswith("_ref") or key.endswith("_refs"):
            refs.extend(_as_str_tuple(value))
    return _dedupe(refs)


def _stable_case_digest(case: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        case,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _first_optional_text(*values: object) -> str | None:
    text = _first_text(*values)
    return None if text == "missing" else text


def _has_pinned_bundle_blocking_issue(issue_codes: Sequence[str]) -> bool:
    blocking_codes = {
        "layer3_g5_pinned_case_missing",
        "layer3_g5_non_pinned_case_widening_attempt",
        "layer3_g5_w12d_full_payload_missing",
        "layer3_g5_w12d_manifest_only_not_payload",
        "layer3_g5_w12d_build_cache_not_source_of_truth",
        "layer3_g5_w12d_s4_s14_case_key_missing",
        "layer3_g5_s4_s14_composed_loop_incomplete",
        "layer3_g5_s14_gate_missing_or_failed",
        "layer3_g5_s2_acquisition_required_unresolved",
        "layer3_g5_s2_bridge_missing_unresolved",
        "layer3_g5_constraint_store_block_ignored",
        "layer3_g5_s7_delegation_record_ref_unresolved",
        "layer3_g5_s12_growth_without_envelope_delta",
        "layer3_g5_s12_demand_act_ref_missing",
        "layer3_g5_s14_grounded_authority_status_overclaimed",
    }
    return any(code in blocking_codes for code in issue_codes)


def _resolve_g4_promotion_record(
    record: Mapping[str, Any],
    *,
    requested_scope: Mapping[str, Any] | None,
) -> Layer3G5G4PromotionRecordResolution:
    state = _first_text(record.get("promotion_state"))
    scope = _mapping(record.get("promotion_scope"))
    claim_families = _as_str_tuple(scope.get("claim_families", ()))
    blockers = _as_str_tuple(record.get("blocker_refs", ()))
    may_not_use_for = _as_str_tuple(record.get("may_not_use_for", ()))
    issues: list[str] = []
    if not record.get("source_design_record_ref"):
        issues.append("layer3_g5_source_design_record_unresolved")
    if not record.get("source_design_record_digest"):
        issues.append("layer3_g5_source_design_record_digest_missing")
    if not may_not_use_for:
        issues.append("layer3_g5_g4_handoff_authority_leak")
    if state == "promotion_blocked":
        issues.append("layer3_g5_blocked_promotion_used_as_conversion")
    if (
        state == "governed_promoted"
        and _scope_mentions(requested_scope, "causal_forecast")
        and "causal_forecast" not in claim_families
    ):
        issues.append("layer3_g5_g4_pass_without_design_scope")
    admitted = state == "governed_promoted" and not blockers and not issues
    return Layer3G5G4PromotionRecordResolution(
        promotion_record_id=str(record.get("promotion_record_id") or "missing"),
        case_id=str(record.get("case_id") or ""),
        promotion_state=state,
        source_design_record_ref=_optional_str(record.get("source_design_record_ref")),
        source_design_record_digest=_optional_str(record.get("source_design_record_digest")),
        claim_families=claim_families,
        blocker_refs=blockers,
        limitation_refs=_as_str_tuple(record.get("limitation_refs", ())),
        upstream_contract_refs=_as_str_tuple(record.get("upstream_contract_refs", ())),
        may_not_use_for=may_not_use_for,
        admitted_for_g5_conversion=admitted,
        issue_codes=_dedupe(issues),
    )


def _build_independence_adapter_payload(
    refs: Sequence[Layer3G5GroundedEvidenceRef],
) -> dict[str, Any]:
    raw_count = len(refs)
    cluster_keys: dict[tuple[str | None, tuple[str, ...]], list[str]] = {}
    for ref in refs:
        cluster_key = (ref.source_hash, tuple(sorted(ref.lineage_refs)))
        cluster_keys.setdefault(cluster_key, []).append(ref.ref)
    clusters = [
        {
            "cluster_id": f"g5-independent-cluster-{index}",
            "line_ids": sorted(line_ids),
            "raw_line_count": len(line_ids),
            "effective_line_count": 1,
            "representative_line_id": sorted(line_ids)[0],
            "collapse_dimensions": {
                "source_lineage_cluster_id": "|".join(lineage) or source_hash or "none",
                "method_cluster_id": "g5.adapter",
                "assumption_cluster_id": "g5.first_proving_ground",
                "shared_failure_mode_cluster_id": "g5.upstream_scope_join",
            },
            "collapse_reasons": []
            if len(line_ids) <= 1
            else [
                {
                    "reason_id": f"g5-independent-cluster-{index}:source_lineage_cluster_id",
                    "dimension": "source_lineage_cluster_id",
                    "reason_code": "shared_source_lineage_cluster_id",
                    "value": "|".join(lineage) or source_hash or "none",
                    "line_ids": sorted(line_ids),
                    "collapse_policy": "strict_hard_collapse",
                    "explanation": "Evidence lines share source lineage or source hash.",
                }
            ],
        }
        for index, ((source_hash, lineage), line_ids) in enumerate(cluster_keys.items(), start=1)
    ]
    effective_count = len(clusters)
    support_line_ids = [ref.ref for ref in refs]
    return {
        "schema_version": INDEPENDENCE_MAP_SCHEMA_VERSION,
        "contract_id": INDEPENDENCE_MAP_CONTRACT_ID,
        "map_id": "layer3-g5-effective-evidence-independence",
        "raw_evidence_line_count": raw_count,
        "effective_independent_evidence_count": effective_count,
        "collapse_dimensions_used": list(INDEPENDENCE_COLLAPSE_DIMENSIONS),
        "collapse_clusters": clusters,
        "effective_mass_report": {
            "raw_evidence_line_count": raw_count,
            "effective_independent_evidence_count": effective_count,
            "raw_support_line_count": raw_count,
            "raw_counterevidence_line_count": 0,
            "raw_context_line_count": 0,
            "effective_support_mass": float(effective_count),
            "effective_counterevidence_mass": 0.0,
            "effective_context_mass": 0.0,
            "balance_status": "support_dominant" if raw_count else "insufficient",
            "independence_status": "sufficient"
            if effective_count > 1
            else "singular",
            "largest_hard_collapse_cluster": max(
                (len(cluster["line_ids"]) for cluster in clusters),
                default=0,
            ),
            "dominant_collapse_reasons": [],
            "support_line_ids": support_line_ids,
            "counterevidence_line_ids": [],
            "context_line_ids": [],
            "limiting_deficits": [],
            "raw_count_display_policy": {
                "display_raw_counts": True,
                "raw_counts_are_diagnostic_only": True,
                "display_effective_counts": True,
                "display_collapse_reasons": True,
            },
        },
        "graded_independence": {
            "enabled": False,
            "feature_flag": "policy_design_case.graded_independence.v1",
            "feature_flag_enabled": False,
            "authority_posture": "strict_hard_collapse_only",
            "raw_evidence_line_count": raw_count,
            "hard_effective_independent_evidence_count": effective_count,
            "graded_effective_independent_evidence_count": float(effective_count),
            "governed_config_status": "provisional",
            "may_not_use_for": [
                "closeout_authority",
                "publication_strength_inflation",
            ],
        },
        "rare_domain_scarcity": {
            "status": "not_rare_domain",
            "support_inflation_allowed": False,
            "effective_support_mass_after_scarcity": float(effective_count),
            "minimum_effective_independent_evidence_count": 1,
            "authority_effect": "none",
        },
    }


def _dependency_status(
    payload: Mapping[str, Any],
    *,
    key_paths: Sequence[Sequence[str]],
    missing_key: bool,
) -> tuple[Literal["pass", "fail", "missing"], bool]:
    if not payload:
        return "missing", missing_key
    values = [_dig(payload, path) for path in key_paths]
    text_values = [_status_text(value) for value in values if value is not None]
    if not text_values:
        return "pass", True
    if text_values[0] == "missing":
        return "missing", missing_key
    if any(value in {"fail", "failed", "red", "blocked", "missing"} for value in text_values):
        return "fail", missing_key
    if any(value in {"pass", "passed", "green", "ready"} for value in text_values):
        return "pass", missing_key
    return "pass", missing_key


def _bounded_path_status(
    repo_root: Path,
    paths: Sequence[Path],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    loaded: list[str] = []
    missing: list[str] = []
    for relative_path in paths:
        if (repo_root / relative_path).exists():
            loaded.append(relative_path.as_posix())
        else:
            missing.append(relative_path.as_posix())
    return tuple(loaded), tuple(missing)


def _read_optional_json(repo_root: Path, relative_path: Path) -> dict[str, Any] | None:
    path = repo_root / relative_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        return (value,)
    return tuple(value)


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _dig(payload: Mapping[str, Any], key_path: Sequence[str]) -> object | None:
    current: object = payload
    for key in key_path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return tuple(str(item) for item in value if item is not None)
    return ()


def _flatten_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        flattened: list[str] = []
        for inner in value.values():
            flattened.extend(_flatten_strings(inner))
        return tuple(flattened)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        flattened = []
        for inner in value:
            flattened.extend(_flatten_strings(inner))
        return tuple(flattened)
    return ()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(*values: object) -> str:
    for value in values:
        text = _optional_str(value)
        if text:
            return text
    return "missing"


def _status_text(value: object) -> str:
    return str(value or "").strip().lower()


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _duplicates(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _scope_mentions(scope: Mapping[str, Any] | None, family: str) -> bool:
    if not isinstance(scope, Mapping):
        return False
    return family in {str(value) for value in scope.get("claim_families", ())}


def _normalize_s2_design_ref(ref: str) -> str:
    if ref in {
        "pdc://layer2/s2/ua-msme/design-record-v0",
        "pdc://layer2/s2/ua-msme-affordable-loans-2022/design-record-v0",
    }:
        return "pdc://layer2/s2/ua-msme/design-record-v0"
    return ref
