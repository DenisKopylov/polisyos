#!/usr/bin/env python3
"""Validate the Layer 2 S0 readiness bundle."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.proving_ground.pinned_route_demand_home import (  # noqa: E402
    load_layer3_gx_data_home,
)

DEFAULT_READINESS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_readiness_manifest.json"
)
DEFAULT_MINIMAL_SEED_PATH = Path(
    "architecture/policy_design_case/layer2_minimal_seed_manifest.json"
)
DEFAULT_DEPENDENCY_DAG_PATH = Path("architecture/policy_design_case/layer2_dependency_dag.json")
DEFAULT_SLICE_CELL_MATRIX_PATH = Path(
    "architecture/policy_design_case/layer2_slice_cell_matrix.toml"
)
DEFAULT_FLOOR_GOVERNANCE_PATH = Path("architecture/policy_design_case/layer2_floor_governance.toml")
DEFAULT_ARTIFACT_TRACEABILITY_PATH = Path(
    "architecture/policy_design_case/layer2_artifact_traceability.toml"
)
DEFAULT_CORPUS_PARTITION_PATH = Path("architecture/policy_design_case/layer2_corpus_partition.json")
DEFAULT_FIRST_PROVING_CASE_PATH = Path(
    "architecture/policy_design_case/layer2_first_proving_case.json"
)
DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"
)
DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json"
)
DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json"
)
DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json"
)
DEFAULT_S7_DELEGATION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s7_delegation_manifest.json"
)
DEFAULT_S8_VALUE_CHOICE_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s8_value_choice_manifest.json"
)
DEFAULT_S9_PROJECTION_LOWERING_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json"
)
DEFAULT_S10_OUTCOME_PREDICTION_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json"
)
DEFAULT_S11_PREDICTIVE_KNOWLEDGE_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json"
)
DEFAULT_S12_RESOURCE_ECONOMICS_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s12_resource_economics_manifest.json"
)
DEFAULT_S13_POST_DEPLOY_ACCOUNTABILITY_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json"
)
DEFAULT_S14_UNIVERSALITY_ASSURANCE_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
)
DEFAULT_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")

REQUIRED_SLICES = {f"S{number}" for number in range(15)}
REQUIRED_ARTIFACT_NAMES = {
    "MinimalSeedManifest",
    "ValueOfInformationEstimate",
    "GovernanceDecisionClass",
    "AxisPositionDeclaration",
    "AxisFirewallStatus",
    "CertifiedOperationEnvelope",
    "DesignRecord",
    "ClusterInterfaceContract",
    "ClusterHandoffRecord",
    "ConstructOntologyDelta",
    "CapabilityBindingResult",
    "CommitmentProfileRecord",
    "ClusterAuthorityDimensionRecord",
    "ForecastCalibrationRecord",
    "ProofCarryingAnalyticsRecord",
    "PredictiveAxisCalibrationRecord",
    "PredictiveAxisUpgradeRecord",
    "S11PredictiveKnowledgeIntegrityReport",
    "CertifiedEnvelopeDelta",
}
MATURITY_QUALIFIERS = {"fail_closed", "predictive"}
S5_CLOSED_CELLS = {
    "SYSTEM.connectivity_modularity",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.scale_composition",
}
S5_COUPLING_REGIMES = {
    "modular",
    "near_decomposable",
    "hierarchically_coupled",
    "entangled",
}
S5_REQUIRED_ARTIFACTS = {
    "CompositionReceipt",
    "ComputationalTractabilityBudget",
    "CouplingGraph",
    "CouplingRegimeClassification",
    "DecompositionResult",
    "DesignInterfaceContract",
    "RecursiveDesignGraph",
    "SystemDynamicsRequirement",
}
S5_REQUIRED_NESTED_RECORDS = {
    "BoundaryCouplingClassification",
    "CompositionLawCheck",
    "ForecastSupportScope",
    "ModuleDiscoveryResult",
}
S5_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "equilibrium_prediction_authority",
    "whole_design_authority_without_coupling_graph",
    "whole_design_authority_from_syntactic_decomposition",
    "whole_design_authority_from_user_supplied_module_split",
    "false_modular_decomposition",
    "weakened_authority_from_tractability_cutoff",
}
S6_CLOSED_CELLS = {
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
}
S6_REQUIRED_ARTIFACTS = {
    "MeasurabilityAdequacyRecord",
    "AggregationValidityRecord",
    "CapacityFeasibilityRecord",
    "MandateLegitimacyRecord",
    "StrategicResponseRecord",
    "ClusterAuthorityDimensionRecord",
}
S6_REQUIRED_FIREWALLS = {"P18", "P19", "P21", "P22", "P24"}
S6_REQUIRED_BRIDGE_CONSUMERS = {
    "KNOWLEDGE.epistemic_regime",
    "ACTOR.value_choice_provenance",
    "INTERVENTION.targeting",
    "INTERVENTION.feasibility",
    "DESIGNER_ITSELF.envelope_membership",
    "PUBLIC.legitimacy_disclosure",
    "INTERVENTION.design_candidate",
    "SYSTEM.post_intervention_dgp",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.robustness",
}
S6_C3_AUTHORITY_DIMENSIONS = {
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
}
S6_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "delegation_authority",
    "value_choice_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "rich_response_model_authority",
    "capacity_transfer_authority",
    "mandate_authority_from_llm",
    "proxy_construct_equivalence_without_disclosure",
    "aggregation_scope_transfer_without_validity",
    "post_policy_effect_claim_without_response_model",
}
S7_CLOSED_CELLS = {"CROSS_CUTTING.scientist_orchestration"}
S7_REQUIRED_ARTIFACTS = {
    "DelegationContract",
    "DecisionRightsMatrix",
    "HumanDecisionRequest",
    "HumanDecisionRecord",
}
S7_REQUIRED_FIREWALLS = {"P26", "P20", "P22", "P12", "P15"}
S7_REQUIRED_AUTHORITY_SCOPE = {
    "delegation_integrity",
    "decision_rights_matrix",
    "human_decision_routing",
    "human_decision_request_ranking",
    "mandate_bounded_decision_record",
    "responsibility_integrity_check",
    "governed_pilot_promotion_gate",
}
S7_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "value_choice_authority",
    "social_weight_selection",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "oversight_effectiveness_claim",
    "attention_ledger_authority",
    "resource_allocation_authority",
    "human_approval_without_decision_record",
    "ai_self_authorization",
    "delegated_autonomy_without_mandate",
    "s13_accountability_closure",
}
S7_INVENTORY_ID = "layer2_s7_delegation_manifest"
S8_CLOSED_CELLS = {"ACTOR.value_choice_provenance"}
S8_REQUIRED_ARTIFACTS = {
    "AuthorizedValueSchedule",
    "ObjectiveFunctionProvenanceRecord",
    "ParetoArchive",
    "ValueChoiceProvenanceRecord",
    "ValueTradeoffDisclosureRecord",
    "ValueChoiceIntegrityReport",
}
S8_REQUIRED_FIREWALLS = {"P20", "P22", "P12", "P15", "P26"}
S8_REQUIRED_AUTHORITY_SCOPE = {
    "value_choice_provenance",
    "authorized_value_schedule",
    "shadow_scenario_value_schedule",
    "pareto_frontier_fact",
    "value_tradeoff_disclosure",
}
S8_REQUIRED_DENY = {
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "scalar_welfare_authority",
    "preference_learning_authority",
    "mandate_creation",
    "social_weight_selection_without_authorized_schedule",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "s9_projection_maturity",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
S8_FALSE_CLEAR_FIELDS = (
    "llm_weight_false_clear_count",
    "corpus_weight_false_clear_count",
    "blocked_mandate_value_choice_false_clear_count",
    "pareto_ranking_without_value_source_false_clear_count",
    "multi_principal_silent_average_false_clear_count",
    "s7_decision_substitution_false_clear_count",
    "shadow_scenario_authority_false_clear_count",
    "missing_arrow_disclosure_false_clear_count",
)
S8_INVENTORY_ID = "layer2_s8_value_choice_manifest"
S9_REQUIRED_ARTIFACTS = {
    "CanonicalDesignRecord",
    "ProjectionAlgebraRequest",
    "ProjectionRenderRecord",
    "ProjectionFaithfulnessRecord",
    "LoweringRequestRecord",
    "LoweringAuthorityGateRecord",
    "LoweringArtifactRecord",
    "LoweringAppendReceipt",
    "DesignRecordMaturityReport",
    "ProjectionLoweringIntegrityReport",
}
S9_REQUIRED_AUTHORITY_SCOPE = {
    "canonical_design_record_maturity",
    "projection_faithfulness",
    "lowering_faithfulness",
    "verified_lowering_append_receipt",
    "reissue_reopen_routing",
}
S9_REQUIRED_DENY = {
    "production_authority",
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
S9_FALSE_CLEAR_FIELDS = {
    "public_limitation_omission_false_clear_count": "public_limitation_omission",
    "added_prose_claim_false_clear_count": "added_prose_claim",
    "tradeoff_inversion_false_clear_count": "tradeoff_inversion",
    "shadow_candidate_approval_false_clear_count": "shadow_candidate_approval",
    "legal_lowering_without_grounding_false_clear_count": "legal_lowering_without_grounding",
    "projection_authority_laundering_false_clear_count": "projection_authority_laundering",
    "redaction_hides_blocker_false_clear_count": "redaction_hides_blocker",
    "post_closeout_lowering_without_reissue_false_clear_count": (
        "post_closeout_lowering_without_reissue"
    ),
    "machine_ref_omission_false_clear_count": "machine_ref_omission",
    "revision_mismatch_false_clear_count": "revision_mismatch",
    "universal_self_claim_without_s14_false_clear_count": (
        "universal_self_claim_without_s14"
    ),
}
S9_INVENTORY_ID = "layer2_s9_projection_lowering_manifest"
S9_EXPECTED_OPEN_CELLS = {
    "DESIGNER_ITSELF.envelope_growth",
    "KNOWLEDGE.calibration",
    "KNOWLEDGE.ir_proof_carrying_analytics",
}
S9_LATER_SLICES: set[str] = set()
S10_REQUIRED_ARTIFACTS = {"ForecastSupport", "ForecastCalibrationRecord"}
S10_REQUIRED_AUTHORITY_SCOPE = {
    "forecast_support_tiering",
    "observable_subset_calibration",
    "value_grounded_welfare_comparison",
    "advisory_uncertainty_routing",
}
S10_REQUIRED_DENY = {
    "production_authority",
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "rich_simulation_authority",
    "portfolio_optimization_authority",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
S10_FALSE_CLEAR_FIELDS = {
    "equilibrium_contested_single_forecast_false_clear_count": (
        "equilibrium_contested_single_forecast"
    ),
    "simulation_only_evidence_laundering_false_clear_count": (
        "simulation_only_evidence_laundering"
    ),
    "uncalibrated_observable_promotion_false_clear_count": (
        "uncalibrated_observable_promotion"
    ),
    "welfare_without_value_provenance_false_clear_count": (
        "welfare_without_value_provenance"
    ),
    "fail_closed_axis_prediction_promotion_false_clear_count": (
        "fail_closed_axis_prediction_promotion"
    ),
    "regime_forecast_tier_laundering_false_clear_count": (
        "regime_forecast_tier_laundering"
    ),
    "transported_estimate_without_limitation_false_clear_count": (
        "transported_estimate_without_limitation"
    ),
    "hidden_uncertainty_interval_false_clear_count": "hidden_uncertainty_interval",
    "non_observable_claim_as_calibrated_false_clear_count": (
        "non_observable_claim_as_calibrated"
    ),
    "production_authority_from_forecast_false_clear_count": (
        "production_authority_from_forecast"
    ),
    "missing_design_graph_context_false_clear_count": "missing_design_graph_context",
    "observed_outcome_without_credible_evaluation_false_clear_count": (
        "observed_outcome_without_credible_evaluation"
    ),
    "validated_local_model_without_method_validity_false_clear_count": (
        "validated_local_model_without_method_validity"
    ),
    "scalar_welfare_hides_pareto_tradeoff_false_clear_count": (
        "scalar_welfare_hides_pareto_tradeoff"
    ),
    "weakest_boundary_ignored_false_clear_count": "weakest_boundary_ignored",
}
S10_INVENTORY_ID = "layer2_s10_outcome_prediction_manifest"
S11_CLOSED_CELLS = {
    "KNOWLEDGE.calibration",
    "KNOWLEDGE.ir_proof_carrying_analytics",
}
S11_EXPECTED_OPEN_CELLS = {"DESIGNER_ITSELF.envelope_growth"}
S11_MATURITY_TRANSITION_CELLS = {
    "OTHER_AGENTS.strategic_response",
    "ACTOR.state_capacity_feasibility",
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
}
S11_REQUIRED_ARTIFACTS = {
    "PredictiveAxisCalibrationRecord",
    "PredictiveAxisUpgradeRecord",
    "ProofCarryingAnalyticsRecord",
    "S11PredictiveKnowledgeIntegrityReport",
}
S11_REQUIRED_AUTHORITY_SCOPE = {
    "per_axis_predictive_calibration",
    "predictive_axis_maturity_upgrade",
    "proof_carrying_analytics_validity",
}
S11_REQUIRED_DENY = {
    "production_authority",
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "calibrated_equilibrium_prediction",
    "rich_simulation_authority",
    "portfolio_optimization_authority",
    "preference_learning_authority",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
    "mandate_legitimacy_predictive_upgrade",
    "historical_prior_current_evidence",
    "llm_method_authority",
}
S11_FALSE_CLEAR_FIELDS = (
    "stale_calibration_relaxation",
    "scope_mismatched_historical_prior",
    "unbound_ir_analytics",
    "negative_certificate_ignored",
    "missing_method_validity",
    "missing_s6_floor_ref",
    "mandate_axis_predictive_upgrade",
    "production_authority_from_predictive_upgrade",
    "rich_simulation_authority_laundering",
    "weakest_boundary_bypass",
)
S11_INVENTORY_ID = "layer2_s11_predictive_knowledge_manifest"
S12_CLOSED_CELLS = {"DESIGNER_ITSELF.envelope_growth"}
S12_REQUIRED_ARTIFACTS = {
    "KnowledgeGovernanceThroughputLedger",
    "EnvelopeGrowthLedger",
    "ResourceAllocationPolicy",
    "GrowthThermometerRecord",
    "ResourceEconomicsIntegrityReport",
}
S12_REQUIRED_AUTHORITY_SCOPE = {
    "value_of_information_allocation",
    "explore_exploit_posture",
    "envelope_growth_ledger",
    "growth_thermometers",
    "knowledge_governance_throughput",
    "allocation_priority_input",
}
S12_REQUIRED_DENY = {
    "production_authority",
    "production_claim_authority",
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
}
S12_FALSE_CLEAR_FIELDS = (
    "bespoke_one_off_growth",
    "allocation_gaming_internal_metrics",
    "floor_lowering_for_useful_design_rate",
    "b_faster_than_a_growth",
    "meta_regress_past_principal",
    "interchangeable_budget",
    "growth_without_envelope_delta",
)
S12_INVENTORY_ID = "layer2_s12_resource_economics_manifest"
S13_REQUIRED_ARTIFACTS = {
    "DeploymentDossier",
    "DivergenceRecord",
    "LearningUpdateProposal",
    "EnvelopeRevision",
    "CertifiedEnvelopeDelta",
    "AssuranceCaseDelta",
}
S13_REQUIRED_AUTHORITY_SCOPE = {
    "post_deploy_accountability",
    "deployment_monitorability",
    "divergence_attribution",
    "learning_update_proposal",
    "post_deploy_mape_k_trace",
    "envelope_revision",
    "assurance_case_delta",
    "public_accountability_note",
}
S13_REQUIRED_DENY = {
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
}
S13_FALSE_CLEAR_FIELDS = (
    "post_policy_data_as_pre_policy_evidence",
    "learned_prior_in_current_evidence_slot",
    "unattributable_updates_model",
    "silent_closed_case_rewrite",
    "learning_without_attribution",
    "envelope_shrink_without_assurance_delta",
    "b_update_before_a_baseline",
    "implementation_failure_as_theory_refutation",
    "outcome_learning_without_counterfactual",
    "s13_as_production_or_recommendation_authority",
)
S13_INVENTORY_ID = "layer2_s13_post_deploy_accountability_manifest"
S14_REQUIRED_ARTIFACTS = {
    "SealedUniversalityBatteryRun",
    "UniversalityAxisScorecard",
    "MechanismGeneralityReport",
    "SkepticDefeaterRecord",
    "UniversalityClaimAssuranceCase",
    "UniversalityClaimGateRecord",
}
S14_REQUIRED_SUPPORTING_RECORDS = {
    "D4CorpusTrackCoverage",
    "ExpertOracleBootstrapRecord",
    "UniversalityBreadthFloorConfig",
    "UniversalityBaselineComparison",
    "GroundedAuthorityCoverageRecord",
    "EvaluationStatusCompositionRecord",
    "EnvelopeRevisionDynamicsRecord",
}
S14_REQUIRED_AUTHORITY_SCOPE = {
    "s14_universality_claim_gate",
    "sealed_battery_integrity",
    "per_axis_universality_scorecard",
    "mechanism_generality_assessment",
    "skeptic_defeater_evaluation",
    "d4_corpus_track_coverage",
    "expert_oracle_bootstrap",
    "universality_breadth_floor",
    "baseline_comparison",
    "grounded_authority_coverage",
    "evaluation_status_composition",
    "envelope_revision_dynamics",
    "declared_operation_envelope",
}
S14_REQUIRED_DENY = {
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
    "sealed_battery_training",
    "development_fixture_access",
    "aggregate_universal_score",
    "untested_axis_envelope_expansion",
    "gold_label_authority",
    "weak_gold_promotion_floor",
    "shadow_candidate_oracle",
    "baseline_free_universal_claim",
    "grounded_authority_without_a_firewalls",
    "status_composition_override",
}
S14_REQUIRED_FIREWALLS = {
    "universality_claim_firewall",
    "held_out_integrity_firewall",
    "sealed_battery_freeze_hash_replay",
    "d4_breadth_floor_firewall",
    "expert_oracle_bootstrap_firewall",
    "grounded_authority_coverage_firewall",
    "evaluation_status_composition_firewall",
    "baseline_comparison_firewall",
    "envelope_revision_dynamics_firewall",
    "s9_faithfulness_required",
    "no_aggregate_universal_number",
    "no_production_authority_from_battery",
    "no_gold_label_or_hidden_fixture_leakage",
}
S14_FALSE_CLEAR_FIELDS = (
    "bare_universal_claim_without_battery",
    "sealed_battery_dev_access",
    "aggregate_universal_number_laundering",
    "untested_axis_combination_in_envelope",
    "bespoke_cost_hidden_as_generality",
    "skeptic_defeater_ignored",
    "faithfulness_claim_without_s9",
    "battery_result_as_production_authority",
    "gold_label_leak_into_dev_signal",
    "freeze_hash_mismatch_accepted",
    "d4_breadth_floor_missing",
    "expert_oracle_bootstrap_missing",
    "weak_gold_floor_laundering",
    "shadow_candidate_oracle_laundering",
    "grounded_authority_refs_missing",
    "status_composition_laundering",
    "envelope_revision_freeze_laundering",
    "baseline_comparison_missing",
)
S14_SKEPTIC_DEFEATER_MAPPING = {
    "bespoke_disguise_defeater": "This is bespoke in disguise.",
    "confident_theater_defeater": "It is confident theater.",
    "failure_boundary_defeater": "It does not know where it fails.",
    "single_axis_universality_defeater": "It is universal only on one axis.",
    "frozen_once_defeater": "It works once, then freezes.",
    "first_call_defeater": "Why call it first?",
}
S14_REQUIRED_GROUNDED_AUTHORITY_REF_TYPES = {
    "a_firewall_refs",
    "claim_evidence_binding_refs",
    "value_choice_provenance_refs",
    "mandate_legitimacy_refs",
    "capacity_check_refs",
    "regime_refs",
    "coupling_refs",
    "projection_faithfulness_refs",
}
S14_REQUIRED_BASELINE_FAMILIES = {"bespoke_tool", "raw_llm", "expert_panel"}
S14_BREADTH_FLOOR_DIMENSIONS = {
    "domain_target",
    "jurisdiction_context_target",
    "scale_class_target",
    "epistemic_regime_target",
    "coupling_regime_target",
    "lifecycle_target",
    "state_capacity_target",
    "authority_posture_target",
    "instrument_family_target",
    "system_dynamics_target",
}
S14_REQUIRED_SUBSTRATE_REUSE_REFS = {
    "src/polisyos/runtime/quality/assurance_case.py#build_universality_assurance_case",
    "src/polisyos/runtime/quality/assurance_case.py#build_assurance_case_for_scorecard",
    "src/polisyos/runtime/quality/capability_ratchet.py#build_capability_reality_report",
    "src/polisyos/runtime/quality/design_axes/resource_economics.py#GrowthThermometerRecord",
    "src/polisyos/runtime/quality/design_axes/resource_economics.py#EnvelopeGrowthLedger",
    "src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#EnvelopeRevision",
    "src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#CertifiedEnvelopeDelta",
    "src/polisyos/runtime/quality/case_lifecycle.py#status_lattice",
    "src/polisyos/runtime/quality/approval.py#closeout_status_composition",
}
S14_INVENTORY_ID = "layer2_s14_universality_assurance_manifest"


def load_layer2_readiness_payloads(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Load all governed S0 readiness payloads."""

    root = Path(repo_root)
    return {
        "readiness_manifest": _load_json(root / DEFAULT_READINESS_MANIFEST_PATH),
        "minimal_seed": _load_json(root / DEFAULT_MINIMAL_SEED_PATH),
        "dependency_dag": _load_json(root / DEFAULT_DEPENDENCY_DAG_PATH),
        "slice_cell_matrix": _load_toml(root / DEFAULT_SLICE_CELL_MATRIX_PATH),
        "floor_governance": _load_toml(root / DEFAULT_FLOOR_GOVERNANCE_PATH),
        "artifact_traceability": _load_toml(root / DEFAULT_ARTIFACT_TRACEABILITY_PATH),
        "corpus_partition": _load_json(root / DEFAULT_CORPUS_PARTITION_PATH),
        "first_proving_case": _load_json(root / DEFAULT_FIRST_PROVING_CASE_PATH),
        "s3_substrate_acquisition": _load_optional_json(
            root / DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH
        ),
        "s4_epistemic_regime": _load_optional_json(
            root / DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH
        ),
        "s5_coupling_composition": _load_optional_json(
            root / DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH
        ),
        "s6_blind_spot_firewalls": _load_optional_json(
            root / DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH
        ),
        "s7_delegation": _load_optional_json(root / DEFAULT_S7_DELEGATION_MANIFEST_PATH),
        "s8_value_choice": _load_optional_json(root / DEFAULT_S8_VALUE_CHOICE_MANIFEST_PATH),
        "s9_projection_lowering": _load_optional_json(
            root / DEFAULT_S9_PROJECTION_LOWERING_MANIFEST_PATH
        ),
        "s10_outcome_prediction": _load_optional_json(
            root / DEFAULT_S10_OUTCOME_PREDICTION_MANIFEST_PATH
        ),
        "s11_predictive_knowledge": _load_optional_json(
            root / DEFAULT_S11_PREDICTIVE_KNOWLEDGE_MANIFEST_PATH
        ),
        "s12_resource_economics": _load_optional_json(
            root / DEFAULT_S12_RESOURCE_ECONOMICS_MANIFEST_PATH
        ),
        "s13_post_deploy_accountability": _load_optional_json(
            root / DEFAULT_S13_POST_DEPLOY_ACCOUNTABILITY_MANIFEST_PATH
        ),
        "s14_universality_assurance": _load_optional_json(
            root / DEFAULT_S14_UNIVERSALITY_ASSURANCE_MANIFEST_PATH
        ),
        "inventory": _load_json(root / DEFAULT_INVENTORY_PATH),
        "cluster_map": cluster_map.load_cluster_ownership_map(root),
    }


def validate_layer2_readiness(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S0 readiness from files in the repository."""

    root = Path(repo_root)
    missing = [
        path.as_posix()
        for path in (
            DEFAULT_READINESS_MANIFEST_PATH,
            DEFAULT_MINIMAL_SEED_PATH,
            DEFAULT_DEPENDENCY_DAG_PATH,
            DEFAULT_SLICE_CELL_MATRIX_PATH,
            DEFAULT_FLOOR_GOVERNANCE_PATH,
            DEFAULT_ARTIFACT_TRACEABILITY_PATH,
            DEFAULT_CORPUS_PARTITION_PATH,
            DEFAULT_FIRST_PROVING_CASE_PATH,
        )
        if not (root / path).exists()
    ]
    if missing:
        return _result(
            [
                {
                    "code": "layer2_readiness_artifact_missing",
                    "message": "Missing S0 readiness artifacts: " + ", ".join(missing),
                }
            ],
            summary={},
        )
    return validate_layer2_readiness_payloads(load_layer2_readiness_payloads(root))


def validate_layer2_readiness_payloads(payloads: dict[str, Any]) -> dict[str, Any]:
    """Validate already-loaded S0 readiness payloads."""

    issues: list[dict[str, str]] = []
    cluster_payload = payloads["cluster_map"]
    current_open_cells = _open_cell_refs(cluster_payload)
    ratchet_states = set(cluster_payload.get("ratchet_state_vocabulary", []))

    matrix = payloads["slice_cell_matrix"]
    open_cell_count_baseline = int(matrix["open_cell_count_baseline"])
    assignments = list(matrix.get("assignment", []))
    assigned_cells = {str(entry.get("cell_ref", "")) for entry in assignments}
    if len(assigned_cells) != open_cell_count_baseline:
        issues.append(
            _issue(
                "layer2_slice_cell_matrix_baseline_count_mismatch",
                "Slice-cell matrix must preserve the S0 baseline open-cell assignments.",
            )
        )
    if not current_open_cells <= assigned_cells:
        issues.append(
            _issue(
                "layer2_slice_cell_matrix_current_open_cell_not_assigned",
                "Every current open cell must remain assigned in the S0 slice-cell baseline.",
            )
        )

    for entry in assignments:
        target_state = str(entry.get("target_state", ""))
        if target_state not in ratchet_states:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_ratchet_state",
                    f"Unknown ratchet target_state={target_state}.",
                )
            )
        if target_state in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_maturity_used_as_state",
                    f"Maturity qualifier used as ratchet state: {target_state}.",
                )
            )
        maturity = entry.get("maturity")
        if maturity is not None and str(maturity) not in MATURITY_QUALIFIERS:
            issues.append(
                _issue(
                    "layer2_slice_cell_matrix_unknown_maturity",
                    f"Unknown maturity qualifier: {maturity}.",
                )
            )

    s0_cells_closed = list(matrix.get("s0_cells_closed", []))
    if s0_cells_closed:
        issues.append(
            _issue(
                "layer2_s0_must_not_close_cells",
                "S0 readiness cannot close cluster cells.",
            )
        )

    dag_nodes = set(payloads["dependency_dag"].get("nodes", {}))
    if dag_nodes != REQUIRED_SLICES:
        issues.append(
            _issue(
                "layer2_dependency_dag_slice_set_invalid",
                "Dependency DAG must declare S0 through S14 exactly.",
            )
        )
    if "S0" not in payloads["dependency_dag"]["nodes"]["S2"].get("prerequisites", []):
        issues.append(
            _issue(
                "layer2_dependency_dag_s2_missing_s0",
                "S2 must depend on S0.",
            )
        )

    _validate_minimal_seed(payloads["minimal_seed"], issues)
    _validate_floors(payloads["floor_governance"], issues)
    _validate_artifact_traceability(payloads["artifact_traceability"], issues)
    _validate_corpus_partition(payloads["corpus_partition"], issues)
    _validate_first_proving_case(payloads["first_proving_case"], issues)
    _validate_readiness_manifest(payloads["readiness_manifest"], issues)
    _validate_s3_substrate_acquisition(
        s3=payloads.get("s3_substrate_acquisition"),
        floor_governance=payloads["floor_governance"],
        first_proving_case=payloads["first_proving_case"],
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s4_epistemic_regime(
        s4=payloads.get("s4_epistemic_regime"),
        floor_governance=payloads["floor_governance"],
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s5_coupling_composition(
        s5=payloads.get("s5_coupling_composition"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s6_blind_spot_firewalls(
        s6=payloads.get("s6_blind_spot_firewalls"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s7_delegation(
        s7=payloads.get("s7_delegation"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s8_value_choice(
        s8=payloads.get("s8_value_choice"),
        s7=payloads.get("s7_delegation"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s9_projection_lowering(
        s9=payloads.get("s9_projection_lowering"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        current_open_cells=current_open_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s10_outcome_prediction(
        s10=payloads.get("s10_outcome_prediction"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        current_open_cells=current_open_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s11_predictive_knowledge(
        s11=payloads.get("s11_predictive_knowledge"),
        s14=payloads.get("s14_universality_assurance"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        inventory=payloads["inventory"],
        slice_cell_matrix=matrix,
        issues=issues,
    )
    _validate_s12_resource_economics(
        s12=payloads.get("s12_resource_economics"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        assigned_cells=assigned_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s13_post_deploy_accountability(
        s13=payloads.get("s13_post_deploy_accountability"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    _validate_s14_universality_assurance(
        s14=payloads.get("s14_universality_assurance"),
        floor_governance=payloads["floor_governance"],
        artifact_traceability=payloads["artifact_traceability"],
        corpus_partition=payloads["corpus_partition"],
        cluster_map_payload=cluster_payload,
        current_open_cells=current_open_cells,
        inventory=payloads["inventory"],
        issues=issues,
    )
    closed_since_s0 = sorted(assigned_cells - current_open_cells)
    s3 = payloads.get("s3_substrate_acquisition")
    s3_summary = (
        {
            "s3_acquisition_branch_state": s3.get("acquisition_branch_state"),
            "s3_expected_current_open_cell_count": s3.get("expected_current_open_cell_count"),
        }
        if isinstance(s3, dict) and s3
        else {}
    )
    s4 = payloads.get("s4_epistemic_regime")
    s4_summary = (
        {
            "s4_w12_overblocking_hypothesis": s4.get("w12_overblocking_hypothesis"),
            "s4_regime_accuracy": s4.get("regime_accuracy"),
            "s4_expected_current_open_cell_count": s4.get("expected_current_open_cell_count"),
        }
        if isinstance(s4, dict) and s4
        else {}
    )
    s5 = payloads.get("s5_coupling_composition")
    s5_summary = (
        {
            "s5_coupling_accuracy": s5.get("coupling_accuracy"),
            "s5_penalized_score": s5.get("penalized_score"),
            "s5_expected_current_open_cell_count": s5.get("expected_current_open_cell_count"),
            "s5_false_modular_count": s5.get("false_modular_count"),
            "s5_false_entangled_count": s5.get("false_entangled_count"),
            "s5_coupling_regime_counts": s5.get("coupling_regime_counts"),
            "s5_boundary_regime_counts": s5.get("boundary_regime_counts"),
            "s5_system_effect_support_labels": s5.get("system_effect_support_labels"),
        }
        if isinstance(s5, dict) and s5
        else {}
    )
    s6 = payloads.get("s6_blind_spot_firewalls")
    s6_summary = (
        {
            "s6_maturity": s6.get("maturity"),
            "s6_case_count": s6.get("case_count"),
            "s6_axis_coverage_count": s6.get("axis_coverage_count"),
            "s6_bridge_consumer_coverage": s6.get("bridge_consumer_coverage"),
            "s6_c3_authority_dimension_coverage": s6.get("c3_authority_dimension_coverage"),
            "s6_fail_closed_coverage": s6.get("per_axis_fail_closed_negative_control_pass_rate"),
            "s6_false_clear_count": s6.get("false_clear_count"),
            "s6_expected_current_open_cell_count": s6.get("expected_current_open_cell_count"),
        }
        if isinstance(s6, dict) and s6
        else {}
    )
    s7 = payloads.get("s7_delegation")
    s7_summary = (
        {
            "s7_case_count": s7.get("case_count"),
            "s7_delegation_precision": s7.get("delegation_precision"),
            "s7_delegation_recall": s7.get("delegation_recall"),
            "s7_responsibility_integrity_pass_rate": s7.get("responsibility_integrity_pass_rate"),
            "s7_oversight_theater_false_clear_count": s7.get("oversight_theater_false_clear_count"),
            "s7_wrong_role_false_clear_count": s7.get("wrong_role_false_clear_count"),
            "s7_workflow_only_summary_false_clear_count": s7.get(
                "workflow_only_summary_false_clear_count"
            ),
            "s7_expected_current_open_cell_count": s7.get("expected_current_open_cell_count"),
        }
        if isinstance(s7, dict) and s7
        else {}
    )
    s8 = payloads.get("s8_value_choice")
    s8_summary = (
        {
            "s8_case_count": s8.get("case_count"),
            "s8_value_provenance_completeness": s8.get("value_provenance_completeness"),
            "s8_authorized_value_schedule_recall": s8.get("authorized_value_schedule_recall"),
            "s8_pareto_archive_coverage": s8.get("pareto_archive_coverage"),
            "s8_tradeoff_disclosure_coverage": s8.get("tradeoff_disclosure_coverage"),
            "s8_expected_current_open_cell_count": s8.get("expected_current_open_cell_count"),
            **{f"s8_{field}": s8.get(field) for field in S8_FALSE_CLEAR_FIELDS},
        }
        if isinstance(s8, dict) and s8
        else {}
    )
    s9 = payloads.get("s9_projection_lowering")
    s9_false_clear_counts = (
        {
            nested_name: s9.get(field_name)
            for field_name, nested_name in S9_FALSE_CLEAR_FIELDS.items()
        }
        if isinstance(s9, dict) and s9
        else {}
    )
    s9_summary = (
        {
            "s9_case_count": s9.get("case_count"),
            "s9_projection_render_count": s9.get("projection_render_count"),
            "s9_projection_faithfulness_denominator": s9.get(
                "projection_faithfulness_denominator"
            ),
            "s9_projection_faithfulness_numerator": s9.get(
                "projection_faithfulness_numerator"
            ),
            "s9_projection_faithfulness_pass_rate": s9.get(
                "projection_faithfulness_pass_rate"
            ),
            "s9_lowering_gate_count": s9.get("lowering_gate_count"),
            "s9_lowering_append_receipt_count": s9.get(
                "lowering_append_receipt_count"
            ),
            "s9_expected_current_open_cell_count": s9.get(
                "expected_current_open_cell_count"
            ),
            "s9_false_clear_counts": s9_false_clear_counts,
            **{f"s9_{field}": s9.get(field) for field in S9_FALSE_CLEAR_FIELDS},
        }
        if isinstance(s9, dict) and s9
        else {}
    )
    s10 = payloads.get("s10_outcome_prediction")
    s10_false_clear_counts = (
        {
            nested_name: s10.get(field_name)
            for field_name, nested_name in S10_FALSE_CLEAR_FIELDS.items()
        }
        if isinstance(s10, dict) and s10
        else {}
    )
    s10_summary = (
        {
            "s10_case_count": s10.get("case_count"),
            "s10_expected_current_open_cell_count": s10.get(
                "expected_current_open_cell_count"
            ),
            "s10_observable_subset_case_count": s10.get(
                "observable_subset_case_count"
            ),
            "s10_observable_subset_calibration_denominator": s10.get(
                "observable_subset_calibration_denominator"
            ),
            "s10_observable_subset_calibration_numerator": s10.get(
                "observable_subset_calibration_numerator"
            ),
            "s10_observable_subset_calibration_pass_rate": s10.get(
                "observable_subset_calibration_pass_rate"
            ),
            "s10_observable_subset_calibration_status": s10.get(
                "observable_subset_calibration_status"
            ),
            "s10_observable_subset_calibration_floor_passed": s10.get(
                "observable_subset_calibration_floor_passed"
            ),
            "s10_observable_subset_calibration_threshold_ref": s10.get(
                "observable_subset_calibration_threshold_ref"
            ),
            "s10_non_observable_downgrade_count": s10.get(
                "non_observable_downgrade_count"
            ),
            "s10_equilibrium_contested_single_forecast_block_count": s10.get(
                "equilibrium_contested_single_forecast_block_count"
            ),
            "s10_simulation_only_evidence_block_count": s10.get(
                "simulation_only_evidence_block_count"
            ),
            "s10_weakest_boundary_inheritance_count": s10.get(
                "weakest_boundary_inheritance_count"
            ),
            "s10_false_clear_counts": s10_false_clear_counts,
            **{f"s10_{field}": s10.get(field) for field in S10_FALSE_CLEAR_FIELDS},
        }
        if isinstance(s10, dict) and s10
        else {}
    )
    s11 = payloads.get("s11_predictive_knowledge")
    s11_false_clear_counts = (
        {
            field: s11.get(f"{field}_false_clear_count")
            for field in S11_FALSE_CLEAR_FIELDS
        }
        if isinstance(s11, dict) and s11
        else {}
    )
    s11_summary = (
        {
            "s11_case_count": s11.get("case_count"),
            "s11_expected_current_open_cell_count": s11.get(
                "expected_current_open_cell_count"
            ),
            "s11_axis_count": s11.get("axis_count"),
            "s11_per_axis_predictive_calibration_threshold_ref": s11.get(
                "per_axis_predictive_calibration_threshold_ref"
            ),
            "s11_per_axis_predictive_calibration_denominator": s11.get(
                "per_axis_predictive_calibration_denominator"
            ),
            "s11_per_axis_predictive_calibration_numerator": s11.get(
                "per_axis_predictive_calibration_numerator"
            ),
            "s11_per_axis_predictive_calibration_pass_rate": s11.get(
                "per_axis_predictive_calibration_pass_rate"
            ),
            "s11_per_axis_predictive_calibration_status": s11.get(
                "per_axis_predictive_calibration_status"
            ),
            "s11_per_axis_predictive_calibration_floor_passed": s11.get(
                "per_axis_predictive_calibration_floor_passed"
            ),
            "s11_predictive_axis_count": s11.get("predictive_axis_count"),
            "s11_reverted_fail_closed_axis_count": s11.get(
                "reverted_fail_closed_axis_count"
            ),
            "s11_proof_bound_claim_count": s11.get("proof_bound_claim_count"),
            "s11_unbound_analytics_rejected_count": s11.get(
                "unbound_analytics_rejected_count"
            ),
            "s11_negative_certificate_block_count": s11.get(
                "negative_certificate_block_count"
            ),
            "s11_forecast_quality_downgrade_count": s11.get(
                "forecast_quality_downgrade_count"
            ),
            "s11_regime_strategy_constraint_count": s11.get(
                "regime_strategy_constraint_count"
            ),
            "s11_method_infrastructure_consumed_count": s11.get(
                "method_infrastructure_consumed_count"
            ),
            "s11_weakest_boundary_inheritance_count": s11.get(
                "weakest_boundary_inheritance_count"
            ),
            "s11_false_clear_counts": s11_false_clear_counts,
            **{
                f"s11_{field}_false_clear_count": s11.get(
                    f"{field}_false_clear_count"
                )
                for field in S11_FALSE_CLEAR_FIELDS
            },
        }
        if isinstance(s11, dict) and s11
        else {}
    )
    s12 = payloads.get("s12_resource_economics")
    s12_false_clear_counts = (
        {field: s12.get(f"{field}_false_clear_count") for field in S12_FALSE_CLEAR_FIELDS}
        if isinstance(s12, dict) and s12
        else {}
    )
    s12_summary = (
        {
            "s12_case_count": s12.get("case_count"),
            "s12_expected_current_open_cell_count": s12.get(
                "expected_current_open_cell_count"
            ),
            "s12_remaining_open_cells": s12.get("remaining_open_cells"),
            "s12_burn_down_complete": s12.get("burn_down_complete"),
            "s12_voi_site_count": s12.get("voi_site_count"),
            "s12_typed_budget_count": s12.get("typed_budget_count"),
            "s12_override_rate_trend": s12.get("override_rate_trend"),
            "s12_reuse_rate_trend": s12.get("reuse_rate_trend"),
            "s12_held_out_status": s12.get("held_out_status"),
            "s12_counted_mechanism_growth_count": s12.get(
                "counted_mechanism_growth_count"
            ),
            "s12_flagged_bespoke_one_off_count": s12.get(
                "flagged_bespoke_one_off_count"
            ),
            "s12_growth_without_envelope_delta_count": s12.get(
                "growth_without_envelope_delta_count"
            ),
            "s12_false_clear_counts": s12_false_clear_counts,
            **{
                f"s12_{field}_false_clear_count": s12.get(
                    f"{field}_false_clear_count"
                )
                for field in S12_FALSE_CLEAR_FIELDS
            },
        }
        if isinstance(s12, dict) and s12
        else {}
    )
    s13 = payloads.get("s13_post_deploy_accountability")
    s13_false_clear_counts = (
        {field: s13.get(f"{field}_false_clear_count") for field in S13_FALSE_CLEAR_FIELDS}
        if isinstance(s13, dict) and s13
        else {}
    )
    s13_summary = (
        {
            "s13_case_count": s13.get("case_count"),
            "s13_expected_current_open_cell_count": s13.get(
                "expected_current_open_cell_count"
            ),
            "s13_remaining_open_cells": s13.get("remaining_open_cells"),
            "s13_burn_down_complete": s13.get("burn_down_complete"),
            "s13_required_artifact_count": len(s13.get("required_artifacts", [])),
            "s13_monitorability_rate": s13.get("monitorability_rate"),
            "s13_a_before_b_ratio": s13.get("a_before_b_ratio"),
            "s13_attribution_resolution_rate": s13.get(
                "attribution_resolution_rate"
            ),
            "s13_envelope_shrink_count": s13.get("envelope_shrink_count"),
            "s13_envelope_expansion_count": s13.get("envelope_expansion_count"),
            "s13_envelope_shrink_latency_recorded_count": s13.get(
                "envelope_shrink_latency_recorded_count"
            ),
            "s13_unattributable_accountability_without_training_count": s13.get(
                "unattributable_accountability_without_training_count"
            ),
            "s13_mape_k_trace_completeness_rate": s13.get(
                "mape_k_trace_completeness_rate"
            ),
            "s13_action_item_closure_rate": s13.get("action_item_closure_rate"),
            "s13_oversight_effectiveness_link_rate": s13.get(
                "oversight_effectiveness_link_rate"
            ),
            "s13_rubber_stamp_divergence_review_required_count": s13.get(
                "rubber_stamp_divergence_review_required_count"
            ),
            "s13_learning_without_attribution_count": s13.get(
                "learning_without_attribution_count"
            ),
            "s13_growth_without_assurance_delta_count": s13.get(
                "growth_without_assurance_delta_count"
            ),
            "s13_false_clear_counts": s13_false_clear_counts,
            **{
                f"s13_{field}_false_clear_count": s13.get(
                    f"{field}_false_clear_count"
                )
                for field in S13_FALSE_CLEAR_FIELDS
            },
        }
        if isinstance(s13, dict) and s13
        else {}
    )
    s14 = payloads.get("s14_universality_assurance")
    s14_false_clear_counts = (
        {
            field: s14.get(f"{field}_false_clear_count")
            for field in S14_FALSE_CLEAR_FIELDS
        }
        if isinstance(s14, dict) and s14
        else {}
    )
    s14_summary = (
        {
            "s14_expected_current_open_cell_count": s14.get(
                "expected_current_open_cell_count"
            ),
            "s14_remaining_open_cells": s14.get("remaining_open_cells"),
            "s14_burn_down_complete": s14.get("burn_down_complete"),
            "s14_required_artifact_count": len(s14.get("required_artifacts", [])),
            "s14_supporting_record_count": len(s14.get("supporting_records", {})),
            "s14_d4_corpus_track_count": s14.get("d4_corpus_track_count"),
            "s14_expert_oracle_layer_count": s14.get("expert_oracle_layer_count"),
            "s14_axis_scorecard_row_count": s14.get("axis_scorecard_row_count"),
            "s14_skeptic_defeater_count": s14.get("skeptic_defeater_count"),
            "s14_universal_claim_gate_status": s14.get("universal_claim_gate_status"),
            "s14_sealed_battery_integrity_status": s14.get(
                "sealed_battery_integrity_status"
            ),
            "s14_sealed_battery_freeze_hash": s14.get("sealed_battery_freeze_hash"),
            "s14_false_clear_counts": s14_false_clear_counts,
            **{
                f"s14_{field}_false_clear_count": s14.get(
                    f"{field}_false_clear_count"
                )
                for field in S14_FALSE_CLEAR_FIELDS
            },
        }
        if isinstance(s14, dict) and s14
        else {}
    )

    return _result(
        issues,
        summary={
            "open_cell_count": len(current_open_cells),
            "remaining_open_cells": sorted(current_open_cells),
            "open_cell_count_baseline": open_cell_count_baseline,
            "current_open_cell_count": len(current_open_cells),
            "assigned_open_cell_count": len(assigned_cells),
            "cells_closed_since_s0": closed_since_s0,
            "s0_cells_closed": s0_cells_closed,
            "readiness_artifact_count": len(payloads["readiness_manifest"].get("artifacts", [])),
            "inventory_artifact_count": _inventory_layer2_artifact_count(payloads["inventory"]),
            **s3_summary,
            **s4_summary,
            **s5_summary,
            **s6_summary,
            **s7_summary,
            **s8_summary,
            **s9_summary,
            **s10_summary,
            **s11_summary,
            **s12_summary,
            **s13_summary,
            **s14_summary,
        },
    )


def _open_cell_refs(payload: dict[str, Any]) -> set[str]:
    return {
        f"{cluster}.{axis}"
        for cluster, axes in payload.get("open_cell_closure", {}).items()
        for axis in axes
    }


def _inventory_layer2_artifact_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for artifact in payload.get("artifacts", [])
        if str(artifact.get("id", "")).startswith("layer2_")
    )


def _s14_manifest_owns_inventory_count(
    *,
    s14: object,
    inventory: dict[str, Any],
) -> bool:
    if not isinstance(s14, dict) or not s14:
        return False
    inventory_artifact = _inventory_artifact_by_id(inventory, S14_INVENTORY_ID)
    if not inventory_artifact:
        return False
    if s14.get("schema_version") != (
        "policyos.policy_design_case.layer2_s14_universality_assurance_manifest.v1"
    ):
        return False
    if (
        s14.get("status") != "active"
        or s14.get("owner") != "governance-board"
        or s14.get("slice") != "S14"
        or s14.get("expected_current_open_cell_count") != 0
    ):
        return False
    if set(s14.get("required_artifacts", [])) != S14_REQUIRED_ARTIFACTS:
        return False
    supporting = s14.get("supporting_records", {})
    if not isinstance(supporting, dict) or set(supporting) != S14_REQUIRED_SUPPORTING_RECORDS:
        return False
    if s14.get("universal_claim_gate_status") != "pass":
        return False
    for field in (
        "schema_version",
        "owner",
        "status",
        "authority_scope",
        "may_not_use_for",
        "validator",
        "canonical_route",
    ):
        if inventory_artifact.get(field) != s14.get(field):
            return False
    return (
        inventory_artifact.get("path")
        == DEFAULT_S14_UNIVERSALITY_ASSURANCE_MANIFEST_PATH.as_posix()
        and inventory_artifact.get("kind") == "layer2_s14_universality_assurance_manifest"
        and inventory_artifact.get("capability_reality_label") == "implemented"
    )


def _validate_minimal_seed(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if not {"P15", "P25"} <= set(payload.get("launch_firewalls", [])):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_launch_firewall",
                "Minimal seed manifest must include P15 and P25 launch firewalls.",
            )
        )
    required_budgets = {
        "compute",
        "acquisition",
        "expert_time",
        "human_attention",
        "legal_access",
    }
    if not required_budgets <= set(payload.get("budgets", {})):
        issues.append(
            _issue(
                "layer2_minimal_seed_missing_budget",
                "Minimal seed manifest must declare all launch budgets.",
            )
        )


def _validate_floors(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    floors = payload.get("floor", [])
    floor_slices = {str(floor.get("slice", "")) for floor in floors}
    required_floor_slices = {f"S{number}" for number in range(2, 15)}
    if not required_floor_slices <= floor_slices:
        issues.append(
            _issue(
                "layer2_floor_governance_missing_slice_floor",
                "Floor governance must cover S2 through S14.",
            )
        )
    for floor in floors:
        for field in ("metric", "floor_owner", "floor_artifact", "revision_rule"):
            if not floor.get(field):
                issues.append(
                    _issue(
                        "layer2_floor_governance_field_missing",
                        f"Floor {floor.get('floor_id')} omits {field}.",
                    )
                )


def _validate_artifact_traceability(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    names = {str(row.get("name", "")) for row in payload.get("artifact", [])}
    missing = REQUIRED_ARTIFACT_NAMES - names
    if missing:
        issues.append(
            _issue(
                "layer2_artifact_traceability_missing_required_artifact",
                "Artifact traceability omits: " + ", ".join(sorted(missing)),
            )
        )


def _validate_corpus_partition(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    dev = payload.get("dev_regression_corpus", {})
    sealed = payload.get("sealed_universality_battery", {})
    if dev.get("path") == sealed.get("path") or sealed.get("extensible") is not False:
        issues.append(
            _issue(
                "layer2_corpus_partition_not_sealed",
                "Sealed universality battery must be distinct and non-extensible.",
            )
        )
    if not str(sealed.get("freeze_hash", "")).startswith("sha256:"):
        issues.append(
            _issue(
                "layer2_corpus_partition_freeze_hash_missing",
                "Sealed universality battery must carry a freeze hash.",
            )
        )


def _validate_first_proving_case(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    constructs = set(payload.get("constructs", []))
    missing = _required_first_proving_constructs(REPO_ROOT) - constructs
    if missing:
        issues.append(
            _issue(
                "layer2_first_proving_case_missing_construct",
                "First proving case omits constructs: " + ", ".join(sorted(missing)),
            )
        )


def _required_first_proving_constructs(repo_root: Path) -> set[str]:
    required: set[str] = set()
    first_proving_case_path = repo_root / DEFAULT_FIRST_PROVING_CASE_PATH
    try:
        payload = json.loads(first_proving_case_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        payload = {}
    constructs = payload.get("constructs")
    if isinstance(constructs, list):
        required.update(str(value) for value in constructs if str(value))
    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return required
    required.update(row.construct_ref for row in data_home.pinned_request.requested_constructs)
    return required


def _validate_readiness_manifest(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if payload.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_readiness_manifest_closes_cells",
                "S0 readiness manifest must not claim closed cells.",
            )
        )
    if int(payload.get("open_cell_count_baseline", -1)) != 17:
        issues.append(
            _issue(
                "layer2_readiness_manifest_open_cell_count_invalid",
                "S0 readiness manifest must preserve open_cell_count_baseline=17.",
            )
        )
    if len(payload.get("readiness_items", [])) != 11:
        issues.append(
            _issue(
                "layer2_readiness_manifest_item_count_invalid",
                "S0 readiness manifest must carry the 11 roadmap readiness items.",
            )
        )


def _validate_s3_substrate_acquisition(
    *,
    s3: object,
    floor_governance: dict[str, Any],
    first_proving_case: dict[str, Any],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s3, dict) or not s3:
        return
    if s3.get("acquisition_branch_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s3_acquisition_branch_not_implemented",
                "S3 must close the acquisition branch (bridge_missing -> implemented).",
            )
        )
    if s3.get("cells_closed"):
        issues.append(
            _issue(
                "layer2_s3_must_not_close_cluster_cell",
                "S3 advances layers only; it closes no cluster cell.",
            )
        )
    if s3.get("expected_current_open_cell_count") != 15:
        issues.append(
            _issue(
                "layer2_s3_open_cell_count_drift",
                "S3 must keep current open_cell_count at 15.",
            )
        )
    deny = set(s3.get("may_not_use_for", []))
    required_deny = {
        "production_claim_authority",
        "scenario_family_authority",
        "claim_authority_from_proxy_or_simulation",
    }
    if not required_deny <= deny:
        issues.append(
            _issue(
                "layer2_s3_authority_boundary_incomplete",
                ("S3 may_not_use_for must block production/scenario-family/proxy authority."),
            )
        )
    if set(s3.get("pinned_constructs", [])) != set(first_proving_case.get("constructs", [])):
        issues.append(
            _issue(
                "layer2_s3_pinned_constructs_drift",
                "S3 pinned constructs must match the first proving case constructs.",
            )
        )
    grounded = set(s3.get("constructs_grounded_in_s3", []))
    staged = set(s3.get("constructs_staged_followup", []))
    pinned = set(s3.get("pinned_constructs", []))
    if not grounded or not grounded.isdisjoint(staged) or grounded | staged != pinned:
        issues.append(
            _issue(
                "layer2_s3_construct_partition_invalid",
                "S3 grounded and staged constructs must be disjoint and cover pinned constructs.",
            )
        )
    if "s3_acquisition_closure" not in set(s3.get("floors", [])):
        issues.append(
            _issue(
                "layer2_s3_floor_missing",
                "S3 manifest must reference the s3_acquisition_closure floor.",
            )
        )
    floor = _floor_by_id(floor_governance, "s3_acquisition_closure")
    if floor.get("metric") != "acquisition_loop_closure_rate":
        issues.append(
            _issue(
                "layer2_s3_floor_metric_invalid",
                "S3 acquisition closure floor must use acquisition_loop_closure_rate.",
            )
        )
    if floor.get("floor_owner") != "team-integration-spine":
        issues.append(
            _issue(
                "layer2_s3_floor_owner_invalid",
                "S3 acquisition closure floor owner must be team-integration-spine.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S3_SUBSTRATE_ACQUISITION_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s3_manifest_missing_from_inventory",
                "S3 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s4_epistemic_regime(
    *,
    s4: object,
    floor_governance: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s4, dict) or not s4:
        return
    expected_closed = {
        "KNOWLEDGE.epistemic_regime",
        "INTERVENTION.reversibility_lifecycle_stakes",
    }
    if set(s4.get("cells_closed", [])) != expected_closed:
        issues.append(
            _issue(
                "layer2_s4_cells_closed_invalid",
                "S4 must close exactly the epistemic_regime and reversibility cells.",
            )
        )
    if s4.get("expected_current_open_cell_count") != 13:
        issues.append(
            _issue(
                "layer2_s4_open_cell_count_drift",
                "S4 manifest must record expected_current_open_cell_count=13.",
            )
        )
    if expected_closed & current_open_cells:
        issues.append(
            _issue(
                "layer2_s4_cluster_map_not_closed",
                "S4 cells must be removed from open_cell_closure.",
            )
        )
    if not expected_closed <= assigned_cells:
        issues.append(
            _issue(
                "layer2_s4_cells_not_assigned",
                "S4 closed cells must be in the frozen slice-cell baseline.",
            )
        )
    deny = set(s4.get("may_not_use_for", []))
    required_deny = {
        "risk_regime_authority_without_risk_evidence",
        "b_side_regime_selection",
        "outcome_claim_from_ignorance",
        "low_stakes_floor_on_catastrophic_irreversible",
    }
    if not required_deny <= deny:
        issues.append(
            _issue(
                "layer2_s4_authority_boundary_incomplete",
                (
                    "S4 may_not_use_for must block false-risk, regime-shopping, "
                    "ignorance-outcome, and P23."
                ),
            )
        )
    if not _floor_by_id(floor_governance, "s4_regime_accuracy"):
        issues.append(
            _issue(
                "layer2_s4_regime_floor_missing",
                "s4_regime_accuracy floor must be registered.",
            )
        )
    if s4.get("w12_overblocking_hypothesis") not in {"confirmed", "revised"}:
        issues.append(
            _issue(
                "layer2_s4_w12_hypothesis_not_recorded",
                "S4 must record the W12 hypothesis as confirmed or revised.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S4_EPISTEMIC_REGIME_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s4_manifest_missing_from_inventory",
                "S4 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s5_coupling_composition(
    *,
    s5: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s5, dict) or not s5:
        return
    if set(s5.get("cells_closed", [])) != S5_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s5_cells_closed_invalid",
                "S5 must close exactly connectivity, dynamics feedback, and composition cells.",
            )
        )
    if s5.get("open_cell_count_baseline") != 17:
        issues.append(
            _issue(
                "layer2_s5_open_cell_count_baseline_invalid",
                "S5 must preserve open_cell_count_baseline=17.",
            )
        )
    if s5.get("expected_current_open_cell_count") != 10:
        issues.append(
            _issue(
                "layer2_s5_open_cell_count_drift",
                "S5 manifest must record expected_current_open_cell_count=10.",
            )
        )
    if S5_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s5_cluster_map_not_closed",
                "S5 cells must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) > int(s5.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s5_cluster_open_cell_count_mismatch",
                "S5 manifest expected open-cell count must not be exceeded by the cluster map.",
            )
        )
    if not assigned_cells >= S5_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s5_cells_not_assigned",
                "S5 closed cells must be in the frozen slice-cell baseline.",
            )
        )
    if "s5_coupling_accuracy" not in set(s5.get("floors", [])):
        issues.append(
            _issue(
                "layer2_s5_floor_missing",
                "S5 manifest must reference the s5_coupling_accuracy floor.",
            )
        )
    if not _floor_by_id(floor_governance, "s5_coupling_accuracy"):
        issues.append(
            _issue(
                "layer2_s5_floor_governance_missing",
                "s5_coupling_accuracy floor must be registered.",
            )
        )
    if not _number_at_least(s5.get("coupling_accuracy"), 0.9):
        issues.append(
            _issue(
                "layer2_s5_coupling_accuracy_below_floor",
                "S5 coupling accuracy must meet the seeded corpus floor.",
            )
        )
    if not _number_at_least(s5.get("penalized_score"), 0.9):
        issues.append(
            _issue(
                "layer2_s5_penalized_score_below_floor",
                "S5 penalized score must meet the false-modular penalty floor.",
            )
        )
    if s5.get("false_modular_count") != 0:
        issues.append(
            _issue(
                "layer2_s5_false_modular_present",
                "S5 false_modular_count must remain zero.",
            )
        )
    if not _non_negative_int(s5.get("false_entangled_count")):
        issues.append(
            _issue(
                "layer2_s5_false_entangled_count_invalid",
                "S5 false_entangled_count must be present and non-negative.",
            )
        )
    if s5.get("proving_ground_case_count") != 13:
        issues.append(
            _issue(
                "layer2_s5_case_count_invalid",
                "S5 proving ground must cover all 13 universal corpus cases.",
            )
        )
    for field, code in (
        ("coupling_regime_counts", "layer2_s5_coupling_regime_counts_incomplete"),
        ("boundary_regime_counts", "layer2_s5_boundary_regime_counts_incomplete"),
    ):
        counts = s5.get(field)
        if not isinstance(counts, dict) or not set(counts) >= S5_COUPLING_REGIMES:
            issues.append(
                _issue(
                    code,
                    f"S5 {field} must cover all four D2.6 coupling regimes.",
                )
            )
    labels = s5.get("system_effect_support_labels")
    if not isinstance(labels, list) or "simulation_only_system_effect" not in labels:
        issues.append(
            _issue(
                "layer2_s5_system_effect_support_labels_incomplete",
                "S5 support labels must expose simulation-only system-effect scope.",
            )
        )
    required_artifacts = set(s5.get("required_artifacts", []))
    trace_s5_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S5"
    }
    if required_artifacts != S5_REQUIRED_ARTIFACTS or required_artifacts != trace_s5_artifacts:
        issues.append(
            _issue(
                "layer2_s5_required_artifacts_missing",
                "S5 required_artifacts must match layer2_artifact_traceability S5 rows.",
            )
        )
    nested_records = set(s5.get("nested_records", []))
    if not nested_records >= S5_REQUIRED_NESTED_RECORDS:
        issues.append(
            _issue(
                "layer2_s5_nested_records_missing",
                "S5 nested_records must include boundary, discovery, forecast, and law checks.",
            )
        )
    negative_controls = set(s5.get("negative_controls", []))
    required_controls = {
        "tests/fixtures/layer2/s5/false_modular_probe.json",
        "tests/fixtures/layer2/s5/syntactic_decomposition_probe.json",
        "tests/fixtures/layer2/s5/boundary_spoof_probe.json",
    }
    if not negative_controls >= required_controls:
        issues.append(
            _issue(
                "layer2_s5_negative_control_missing",
                "S5 negative_controls must include false-modular, syntactic, and boundary-spoof probes.",
            )
        )
    if not set(s5.get("may_not_use_for", [])) >= S5_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s5_authority_deny_list_incomplete",
                "S5 may_not_use_for must block production, prediction, and P17 authority laundering.",
            )
        )
    if s5.get("authority_boundary") != (
        "shadow_governed_composition_gate_only_no_production_or_prediction_authority"
    ):
        issues.append(
            _issue(
                "layer2_s5_authority_boundary_incomplete",
                "S5 authority_boundary must stay shadow-governed and non-production.",
            )
        )
    if "P17" not in set(s5.get("relevant_patterns", [])):
        issues.append(
            _issue(
                "layer2_s5_relevant_patterns_missing_p17",
                "S5 manifest must cite P17 decomposition laundering.",
            )
        )
    inventory_paths = {
        str(artifact.get("path", ""))
        for artifact in inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if DEFAULT_S5_COUPLING_COMPOSITION_MANIFEST_PATH.as_posix() not in inventory_paths:
        issues.append(
            _issue(
                "layer2_s5_manifest_missing_from_inventory",
                "S5 manifest must be registered in the Policy Design Case inventory.",
            )
        )


def _validate_s6_blind_spot_firewalls(
    *,
    s6: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s6, dict) or not s6:
        issues.append(
            _issue(
                "layer2_s6_manifest_missing",
                "S6 blind-spot firewalls manifest must be present.",
            )
        )
        return
    if s6.get("schema_version") != (
        "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s6_schema_version_invalid",
                "S6 manifest schema_version is invalid.",
            )
        )
    if s6.get("status") != "active" or s6.get("maturity") != "fail_closed":
        issues.append(
            _issue(
                "layer2_s6_status_or_maturity_invalid",
                "S6 manifest must be active with maturity=fail_closed.",
            )
        )
    if set(s6.get("cells_closed", [])) != S6_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s6_cells_closed_invalid",
                "S6 must close exactly the five blind-spot cells.",
            )
        )
    if s6.get("expected_current_open_cell_count") != 5:
        issues.append(
            _issue(
                "layer2_s6_open_cell_count_drift",
                "S6 manifest must record expected_current_open_cell_count=5.",
            )
        )
    if S6_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s6_cluster_map_not_closed",
                "S6 cells must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) > int(s6.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s6_cluster_open_cell_count_mismatch",
                "S6 manifest expected open-cell count must not be exceeded by the cluster map.",
            )
        )
    if not assigned_cells >= S6_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s6_cells_not_assigned",
                "S6 closed cells must be in the frozen slice-cell baseline.",
            )
        )

    trace_s6_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S6"
    }
    if set(s6.get("required_artifacts", [])) != S6_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s6_required_artifacts_missing",
                "S6 required_artifacts must list the six blind-spot artifacts.",
            )
        )
    if not trace_s6_artifacts >= S6_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s6_traceability_missing",
                "S6 artifacts must be traceable in layer2_artifact_traceability.",
            )
        )
    if set(s6.get("required_firewalls", [])) != S6_REQUIRED_FIREWALLS:
        issues.append(
            _issue(
                "layer2_s6_firewalls_invalid",
                "S6 must require P18, P19, P21, P22, and P24 firewalls.",
            )
        )
    if set(s6.get("c3_authority_dimensions", [])) != S6_C3_AUTHORITY_DIMENSIONS:
        issues.append(
            _issue(
                "layer2_s6_c3_dimensions_invalid",
                "S6 C3 authority dimensions must include strategic_robustness and response_model_validity.",
            )
        )
    if set(s6.get("required_bridge_consumers", [])) != S6_REQUIRED_BRIDGE_CONSUMERS:
        issues.append(
            _issue(
                "layer2_s6_bridge_consumers_invalid",
                "S6 required_bridge_consumers must cover all five blind-spot cells.",
            )
        )
    cluster_bridge_consumers = _s6_bridge_consumers_from_cluster_map(cluster_map_payload)
    if not cluster_bridge_consumers >= S6_REQUIRED_BRIDGE_CONSUMERS:
        issues.append(
            _issue(
                "layer2_s6_cluster_bridge_consumers_missing",
                "Cluster map must expose every S6 required bridge consumer.",
            )
        )

    floor = _floor_by_id(floor_governance, "s6_fail_closed_coverage")
    if not floor or floor.get("revision_rule") != "all_five_blind_spot_axes_required":
        issues.append(
            _issue(
                "layer2_s6_floor_governance_invalid",
                "s6_fail_closed_coverage floor must require all five blind-spot axes.",
            )
        )
    if s6.get("floor_id") != "s6_fail_closed_coverage":
        issues.append(
            _issue(
                "layer2_s6_floor_missing",
                "S6 manifest must reference s6_fail_closed_coverage.",
            )
        )
    if s6.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s6_case_count_invalid",
                "S6 manifest must record all 13 universal corpus cases.",
            )
        )
    if s6.get("axis_coverage_count") != 5 or s6.get("all_five_axes_covered") is not True:
        issues.append(
            _issue(
                "layer2_s6_axis_coverage_invalid",
                "S6 manifest must record coverage for all five blind-spot axes.",
            )
        )
    if not _number_at_least(
        s6.get("per_axis_fail_closed_negative_control_pass_rate"),
        1.0,
    ):
        issues.append(
            _issue(
                "layer2_s6_fail_closed_coverage_below_floor",
                "S6 fail-closed coverage must be at least 1.0.",
            )
        )
    if s6.get("false_clear_count") != 0:
        issues.append(
            _issue(
                "layer2_s6_false_clear_count_nonzero",
                "S6 false_clear_count must stay zero.",
            )
        )
    bridge_coverage = s6.get("bridge_consumer_coverage")
    if not _coverage_has_all_true(bridge_coverage, S6_REQUIRED_BRIDGE_CONSUMERS):
        issues.append(
            _issue(
                "layer2_s6_bridge_consumer_coverage_incomplete",
                "S6 bridge_consumer_coverage must mark every required consumer true.",
            )
        )
    c3_coverage = s6.get("c3_authority_dimension_coverage")
    if not _coverage_has_all_true(c3_coverage, S6_C3_AUTHORITY_DIMENSIONS):
        issues.append(
            _issue(
                "layer2_s6_c3_authority_dimension_coverage_incomplete",
                "S6 c3_authority_dimension_coverage must mark every C3 dimension true.",
            )
        )
    if not set(s6.get("may_not_use_for", [])) >= S6_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s6_authority_deny_list_incomplete",
                "S6 may_not_use_for must block prediction, production, value, capacity, and mandate laundering.",
            )
        )

    inventory_artifact = _inventory_artifact_by_id(
        inventory,
        "layer2_s6_blind_spot_firewalls_manifest",
    )
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s6_manifest_missing_from_inventory",
                "S6 manifest must be registered in the Policy Design Case inventory.",
            )
        )
    else:
        if (
            inventory_artifact.get("path")
            != DEFAULT_S6_BLIND_SPOT_FIREWALLS_MANIFEST_PATH.as_posix()
        ):
            issues.append(
                _issue(
                    "layer2_s6_inventory_path_invalid",
                    "S6 inventory path must point at the governed manifest.",
                )
            )
        if inventory_artifact.get("maturity") != "fail_closed":
            issues.append(
                _issue(
                    "layer2_s6_inventory_maturity_invalid",
                    "S6 inventory entry must carry maturity=fail_closed.",
                )
            )


def _validate_s7_delegation(
    *,
    s7: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s7, dict) or not s7:
        issues.append(
            _issue(
                "layer2_s7_manifest_missing",
                "S7 delegation manifest must be present.",
            )
        )
        return
    if s7.get("schema_version") != ("policyos.policy_design_case.layer2_s7_delegation_manifest.v1"):
        issues.append(
            _issue(
                "layer2_s7_schema_version_invalid",
                "S7 delegation manifest schema_version is invalid.",
            )
        )
    if s7.get("status") != "active" or s7.get("owner") != "governance-board":
        issues.append(
            _issue(
                "layer2_s7_status_or_owner_invalid",
                "S7 delegation manifest must be active and owned by governance-board.",
            )
        )
    if s7.get("depends_on") != ["S2", "S6"]:
        issues.append(
            _issue(
                "layer2_s7_dependencies_invalid",
                "S7 must depend on S2 and S6 in that order.",
            )
        )
    if set(s7.get("cells_closed", [])) != S7_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s7_cells_closed_invalid",
                "S7 must close exactly CROSS_CUTTING.scientist_orchestration.",
            )
        )
    if s7.get("expected_current_open_cell_count") != 4:
        issues.append(
            _issue(
                "layer2_s7_open_cell_count_drift",
                "S7 manifest must record expected_current_open_cell_count=4.",
            )
        )
    if S7_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s7_cluster_map_not_closed",
                "S7 delegation cell must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) > int(s7.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s7_cluster_open_cell_count_mismatch",
                "S7 manifest expected open-cell count must not be exceeded by the cluster map.",
            )
        )
    if not assigned_cells >= S7_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s7_cells_not_assigned",
                "S7 closed cells must be in the frozen slice-cell baseline.",
            )
        )

    cell = (
        cluster_map_payload.get("cell", {})
        .get(
            "CROSS_CUTTING",
            {},
        )
        .get("scientist_orchestration", {})
    )
    if not isinstance(cell, dict) or cell.get("ratchet_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s7_cluster_cell_not_implemented",
                "CROSS_CUTTING.scientist_orchestration must be implemented.",
            )
        )
    else:
        if cell.get("p01_chain") != "implemented":
            issues.append(
                _issue(
                    "layer2_s7_cluster_cell_p01_chain_invalid",
                    "S7 delegation cell must have p01_chain=implemented.",
                )
            )
        if cell.get("owner_module") != s7.get("producer_module"):
            issues.append(
                _issue(
                    "layer2_s7_cluster_cell_owner_invalid",
                    "S7 delegation cell owner_module must match the producer module.",
                )
            )
        if cell.get("firewall") != "P26_responsibility_integrity_laundering":
            issues.append(
                _issue(
                    "layer2_s7_cluster_cell_firewall_invalid",
                    "S7 delegation cell must be guarded by the P26 responsibility firewall.",
                )
            )

    trace_s7_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S7"
    }
    if set(s7.get("required_artifacts", [])) != S7_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s7_required_artifacts_missing",
                "S7 required_artifacts must list the four delegation artifacts.",
            )
        )
    if trace_s7_artifacts != S7_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s7_traceability_missing",
                "S7 artifacts must match layer2_artifact_traceability S7 rows.",
            )
        )
    if not set(s7.get("required_firewalls", [])) >= S7_REQUIRED_FIREWALLS:
        issues.append(
            _issue(
                "layer2_s7_firewalls_invalid",
                "S7 must require P26, P20, P22, P12, and P15 firewalls.",
            )
        )

    floor = _floor_by_id(floor_governance, "s7_delegation_integrity")
    if (
        s7.get("floor_id") != "s7_delegation_integrity"
        or not floor
        or floor.get("metric") != s7.get("floor_metric")
        or floor.get("revision_rule") != "decision_rights_matrix_change_requires_governance_owner"
    ):
        issues.append(
            _issue(
                "layer2_s7_floor_governance_invalid",
                "S7 floor must be governed by the decision-rights matrix revision rule.",
            )
        )
    for field, code in (
        ("delegation_precision", "layer2_s7_delegation_precision_below_floor"),
        ("delegation_recall", "layer2_s7_delegation_recall_below_floor"),
        (
            "responsibility_integrity_pass_rate",
            "layer2_s7_responsibility_integrity_pass_rate_below_floor",
        ),
    ):
        if not _number_at_least(s7.get(field), 1.0):
            issues.append(
                _issue(
                    code,
                    f"S7 {field} must be at least 1.0.",
                )
            )
    for field, code in (
        (
            "oversight_theater_false_clear_count",
            "layer2_s7_oversight_theater_false_clear_count_nonzero",
        ),
        (
            "wrong_role_false_clear_count",
            "layer2_s7_wrong_role_false_clear_count_nonzero",
        ),
        (
            "workflow_only_summary_false_clear_count",
            "layer2_s7_workflow_only_summary_false_clear_count_nonzero",
        ),
    ):
        if s7.get(field) != 0:
            issues.append(
                _issue(
                    code,
                    f"S7 {field} must stay zero.",
                )
            )
    if (
        s7.get("required_handoff_artifact") != "ClusterHandoffRecord"
        or s7.get("replay_visible_handoff_ledger_required") is not True
    ):
        issues.append(
            _issue(
                "layer2_s7_handoff_ledger_invalid",
                "S7 must require replay-visible ClusterHandoffRecord handoff ledger rows.",
            )
        )
    if s7.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s7_case_count_invalid",
                "S7 manifest must record all 13 universal corpus cases.",
            )
        )
    if set(s7.get("authority_scope", [])) != S7_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s7_authority_scope_invalid",
                "S7 authority_scope must match the governed delegation scope.",
            )
        )
    if not set(s7.get("may_not_use_for", [])) >= S7_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s7_authority_deny_list_incomplete",
                "S7 may_not_use_for must block production, value, prediction, and autonomy laundering.",
            )
        )
    if s7.get("canonical_route") != "tools/quality/validation/run_universal_outcome_corpus.py":
        issues.append(
            _issue(
                "layer2_s7_canonical_route_invalid",
                "S7 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s7.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s7_validator_invalid",
                "S7 manifest must point at the layer2 readiness validator.",
            )
        )

    inventory_artifact = _inventory_artifact_by_id(inventory, S7_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s7_manifest_missing_from_inventory",
                "S7 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S7_DELEGATION_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s7_inventory_path_invalid",
                "S7 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s7_delegation_manifest":
        issues.append(
            _issue(
                "layer2_s7_inventory_kind_invalid",
                "S7 inventory entry must carry kind=layer2_s7_delegation_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s7.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s7_inventory_schema_version_invalid",
                "S7 inventory schema_version must match the manifest.",
            )
        )
    if (
        inventory_artifact.get("owner") != s7.get("owner")
        or inventory_artifact.get("status") != s7.get("status")
        or inventory_artifact.get("capability_reality_label") != "implemented"
    ):
        issues.append(
            _issue(
                "layer2_s7_inventory_status_invalid",
                "S7 inventory entry must be active, implemented, and owned by governance-board.",
            )
        )
    if inventory_artifact.get("authority_scope") != s7.get("authority_scope"):
        issues.append(
            _issue(
                "layer2_s7_inventory_authority_scope_mismatch",
                "S7 inventory authority_scope must match the manifest.",
            )
        )
    if inventory_artifact.get("may_not_use_for") != s7.get("may_not_use_for"):
        issues.append(
            _issue(
                "layer2_s7_inventory_deny_list_mismatch",
                "S7 inventory may_not_use_for must match the manifest.",
            )
        )
    if inventory_artifact.get("validator") != s7.get("validator"):
        issues.append(
            _issue(
                "layer2_s7_inventory_validator_mismatch",
                "S7 inventory validator must match the manifest.",
            )
        )
    if inventory_artifact.get("canonical_route") != s7.get("canonical_route"):
        issues.append(
            _issue(
                "layer2_s7_inventory_canonical_route_mismatch",
                "S7 inventory canonical_route must match the manifest.",
            )
        )


def _validate_s8_value_choice(
    *,
    s8: object,
    s7: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s8, dict) or not s8:
        issues.append(
            _issue(
                "layer2_s8_manifest_missing",
                "S8 value-choice provenance manifest must be present.",
            )
        )
        return
    if s8.get("schema_version") != (
        "policyos.policy_design_case.layer2_s8_value_choice_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s8_schema_version_invalid",
                "S8 value-choice manifest schema_version is invalid.",
            )
        )
    if s8.get("status") != "active" or s8.get("owner") != "governance-board":
        issues.append(
            _issue(
                "layer2_s8_status_or_owner_invalid",
                "S8 value-choice manifest must be active and owned by governance-board.",
            )
        )
    if s8.get("depends_on") != ["S2", "S6", "S7"]:
        issues.append(
            _issue(
                "layer2_s8_dependencies_invalid",
                "S8 must depend on S2, S6, and S7 in that order.",
            )
        )
    if set(s8.get("cells_closed", [])) != S8_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s8_cells_closed_invalid",
                "S8 must close exactly ACTOR.value_choice_provenance.",
            )
        )
    if s8.get("expected_current_open_cell_count") != 3:
        issues.append(
            _issue(
                "layer2_s8_open_cell_count_drift",
                "S8 manifest must record expected_current_open_cell_count=3.",
            )
        )
    if S8_CLOSED_CELLS & current_open_cells:
        issues.append(
            _issue(
                "layer2_s8_cluster_map_not_closed",
                "S8 value-choice cell must be removed from open_cell_closure.",
            )
        )
    if len(current_open_cells) > int(s8.get("expected_current_open_cell_count", -1)):
        issues.append(
            _issue(
                "layer2_s8_cluster_open_cell_count_mismatch",
                "S8 manifest expected open-cell count must not be exceeded by the cluster map.",
            )
        )
    if not assigned_cells >= S8_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s8_cells_not_assigned",
                "S8 closed cells must be in the frozen slice-cell baseline.",
            )
        )

    cell = (
        cluster_map_payload.get("cell", {})
        .get("ACTOR", {})
        .get(
            "value_choice_provenance",
            {},
        )
    )
    if not isinstance(cell, dict) or cell.get("ratchet_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s8_cluster_cell_not_implemented",
                "ACTOR.value_choice_provenance must be implemented.",
            )
        )
    else:
        if cell.get("p01_chain") != "implemented":
            issues.append(
                _issue(
                    "layer2_s8_cluster_cell_p01_chain_invalid",
                    "S8 value-choice cell must have p01_chain=implemented.",
                )
            )
        if cell.get("owner_module") != s8.get("producer_module"):
            issues.append(
                _issue(
                    "layer2_s8_cluster_cell_owner_invalid",
                    "S8 value-choice cell owner_module must match the producer module.",
                )
            )
        if cell.get("firewall") != "P20_normative_choice_laundering":
            issues.append(
                _issue(
                    "layer2_s8_cluster_cell_firewall_invalid",
                    "S8 value-choice cell must be guarded by the P20 firewall.",
                )
            )
        if cell.get("gap") != "none_for_s8_value_choice_provenance_scope":
            issues.append(
                _issue(
                    "layer2_s8_cluster_cell_gap_invalid",
                    "S8 value-choice cell must record no S8-scope gap.",
                )
            )

    trace_s8_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S8"
    }
    if set(s8.get("required_artifacts", [])) != S8_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s8_required_artifacts_missing",
                "S8 required_artifacts must list the six value-choice artifacts.",
            )
        )
    if trace_s8_artifacts != S8_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s8_traceability_missing",
                "S8 artifacts must match layer2_artifact_traceability S8 rows.",
            )
        )
    if set(s8.get("required_firewalls", [])) != S8_REQUIRED_FIREWALLS:
        issues.append(
            _issue(
                "layer2_s8_firewalls_invalid",
                "S8 must require P20, P22, P12, P15, and P26 firewalls.",
            )
        )

    floor = _floor_by_id(floor_governance, "s8_value_provenance")
    if (
        s8.get("floor_id") != "s8_value_provenance"
        or not floor
        or floor.get("metric") != s8.get("floor_metric")
        or floor.get("revision_rule") != "ranked_recommendations_require_authorized_value_source"
    ):
        issues.append(
            _issue(
                "layer2_s8_floor_governance_invalid",
                "S8 floor must govern value provenance before ranked recommendations.",
            )
        )
    if s8.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s8_case_count_invalid",
                "S8 manifest must record all 13 universal corpus cases.",
            )
        )
    for field, code in (
        (
            "value_provenance_completeness",
            "layer2_s8_value_provenance_completeness_below_floor",
        ),
        (
            "authorized_value_schedule_recall",
            "layer2_s8_authorized_value_schedule_recall_below_floor",
        ),
        ("pareto_archive_coverage", "layer2_s8_pareto_archive_coverage_below_floor"),
        (
            "tradeoff_disclosure_coverage",
            "layer2_s8_tradeoff_disclosure_coverage_below_floor",
        ),
    ):
        if not _number_at_least(s8.get(field), 1.0):
            issues.append(_issue(code, f"S8 {field} must be at least 1.0."))
    for field in S8_FALSE_CLEAR_FIELDS:
        if s8.get(field) != 0:
            issues.append(
                _issue(
                    f"layer2_s8_{field}_nonzero",
                    f"S8 {field} must stay zero.",
                )
            )
    if set(s8.get("authority_scope", [])) != S8_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s8_authority_scope_invalid",
                "S8 authority_scope must match the governed value-choice scope.",
            )
        )
    if not set(s8.get("may_not_use_for", [])) >= S8_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s8_authority_deny_list_incomplete",
                "S8 may_not_use_for must block production, prediction, and value laundering.",
            )
        )
    if s8.get("canonical_route") != "tools/quality/validation/run_universal_outcome_corpus.py":
        issues.append(
            _issue(
                "layer2_s8_canonical_route_invalid",
                "S8 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s8.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s8_validator_invalid",
                "S8 manifest must point at the layer2 readiness validator.",
            )
        )

    _validate_s8_s7_value_authorization_support(s7=s7, issues=issues)
    _validate_s8_runtime_negative_firewalls(issues)

    if _inventory_layer2_artifact_count(inventory) < 18:
        issues.append(
            _issue(
                "layer2_s8_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must include post-S10 registration.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S8_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s8_manifest_missing_from_inventory",
                "S8 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S8_VALUE_CHOICE_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s8_inventory_path_invalid",
                "S8 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s8_value_choice_manifest":
        issues.append(
            _issue(
                "layer2_s8_inventory_kind_invalid",
                "S8 inventory entry must carry kind=layer2_s8_value_choice_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s8.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s8_inventory_schema_version_invalid",
                "S8 inventory schema_version must match the manifest.",
            )
        )
    if (
        inventory_artifact.get("owner") != s8.get("owner")
        or inventory_artifact.get("status") != s8.get("status")
        or inventory_artifact.get("capability_reality_label") != "implemented"
    ):
        issues.append(
            _issue(
                "layer2_s8_inventory_status_invalid",
                "S8 inventory entry must be active, implemented, and owned by governance-board.",
            )
        )
    if inventory_artifact.get("authority_scope") != s8.get("authority_scope"):
        issues.append(
            _issue(
                "layer2_s8_inventory_authority_scope_mismatch",
                "S8 inventory authority_scope must match the manifest.",
            )
        )
    if inventory_artifact.get("may_not_use_for") != s8.get("may_not_use_for"):
        issues.append(
            _issue(
                "layer2_s8_inventory_deny_list_mismatch",
                "S8 inventory may_not_use_for must match the manifest.",
            )
        )
    if inventory_artifact.get("validator") != s8.get("validator"):
        issues.append(
            _issue(
                "layer2_s8_inventory_validator_mismatch",
                "S8 inventory validator must match the manifest.",
            )
        )
    if inventory_artifact.get("canonical_route") != s8.get("canonical_route"):
        issues.append(
            _issue(
                "layer2_s8_inventory_canonical_route_mismatch",
                "S8 inventory canonical_route must match the manifest.",
            )
        )


def _validate_s9_projection_lowering(
    *,
    s9: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    current_open_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s9, dict) or not s9:
        issues.append(
            _issue(
                "layer2_s9_manifest_missing",
                "S9 projection/lowering manifest must be present.",
            )
        )
        return
    if s9.get("schema_version") != (
        "policyos.policy_design_case.layer2_s9_projection_lowering_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s9_schema_version_invalid",
                "S9 projection/lowering manifest schema_version is invalid.",
            )
        )
    if s9.get("status") != "active" or s9.get("owner") != "team-runtime-quality":
        issues.append(
            _issue(
                "layer2_s9_status_or_owner_invalid",
                "S9 projection/lowering manifest must be active and owned by team-runtime-quality.",
            )
        )
    if s9.get("slice") != "S9" or s9.get("depends_on") != ["S2", "S5", "S8"]:
        issues.append(
            _issue(
                "layer2_s9_slice_or_dependencies_invalid",
                "S9 must depend on S2, S5, and S8 without claiming a later layer.",
            )
        )
    if s9.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_s9_cells_closed_invalid",
                "S9 advances projection maturity only; it closes no cluster cell.",
            )
        )
    if s9.get("layer_cells_advanced") != [
        "DESIGNER_ITSELF.closeout_projection_ratchet"
    ]:
        issues.append(
            _issue(
                "layer2_s9_layer_cells_advanced_invalid",
                "S9 must advance only the closeout projection ratchet.",
            )
        )
    if s9.get("expected_current_open_cell_count") != 3:
        issues.append(
            _issue(
                "layer2_s9_open_cell_count_drift",
                "S9 manifest must record expected_current_open_cell_count=3.",
            )
        )
    if current_open_cells and not current_open_cells <= S9_EXPECTED_OPEN_CELLS:
        issues.append(
            _issue(
                "layer2_s9_current_open_cells_invalid",
                "S9 live open cells must remain a subset of its manifest-local post-S8 open cells.",
            )
        )

    trace_s9_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S9"
    }
    if set(s9.get("required_artifacts", [])) != S9_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s9_required_artifacts_missing",
                "S9 required_artifacts must list the ten projection/lowering artifacts.",
            )
        )
    if trace_s9_artifacts != S9_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s9_traceability_missing",
                "S9 artifacts must match layer2_artifact_traceability S9 rows.",
            )
        )

    floor = _floor_by_id(floor_governance, "s9_projection_faithfulness")
    if (
        s9.get("floor_id") != "s9_projection_faithfulness"
        or not floor
        or floor.get("metric") != s9.get("floor_metric")
        or floor.get("floor_owner") != "team-runtime-quality"
        or floor.get("revision_rule") != "faithfulness_negative_controls_required"
    ):
        issues.append(
            _issue(
                "layer2_s9_floor_governance_invalid",
                "S9 floor must govern projection faithfulness through negative controls.",
            )
        )
    if s9.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s9_case_count_invalid",
                "S9 manifest must record all 13 universal corpus cases.",
            )
        )
    if not _number_at_least(s9.get("projection_render_count"), 52):
        issues.append(
            _issue(
                "layer2_s9_projection_render_count_below_floor",
                "S9 projection_render_count must cover all four audiences across 13 cases.",
            )
        )
    if not _number_at_least(s9.get("projection_faithfulness_denominator"), 52):
        issues.append(
            _issue(
                "layer2_s9_projection_faithfulness_denominator_below_floor",
                "S9 projection faithfulness denominator must be at least 52.",
            )
        )
    if s9.get("projection_faithfulness_numerator") != s9.get(
        "projection_faithfulness_denominator"
    ):
        issues.append(
            _issue(
                "layer2_s9_projection_faithfulness_numerator_mismatch",
                "S9 projection faithfulness numerator must equal its denominator.",
            )
        )
    if s9.get("projection_faithfulness_pass_rate") != 1.0:
        issues.append(
            _issue(
                "layer2_s9_projection_faithfulness_below_floor",
                "S9 projection_faithfulness_pass_rate must remain 1.0.",
            )
        )
    if not _number_at_least(s9.get("lowering_gate_count"), 13):
        issues.append(
            _issue(
                "layer2_s9_lowering_gate_count_below_floor",
                "S9 lowering_gate_count must cover every corpus case.",
            )
        )
    append_refs = s9.get("lowering_append_receipt_refs", [])
    append_ref_count = len(append_refs) if isinstance(append_refs, list) else -1
    if not _number_at_least(s9.get("lowering_append_receipt_count"), 1):
        issues.append(
            _issue(
                "layer2_s9_lowering_append_receipt_missing",
                "S9 must persist at least one governed lowering append receipt.",
            )
        )
    if s9.get("lowering_append_receipt_count") != append_ref_count:
        issues.append(
            _issue(
                "layer2_s9_lowering_append_receipt_count_mismatch",
                "S9 lowering_append_receipt_count must match persisted append receipt refs.",
            )
        )
    for field in S9_FALSE_CLEAR_FIELDS:
        if s9.get(field) != 0:
            issues.append(
                _issue(
                    f"layer2_s9_{field}_nonzero",
                    f"S9 {field} must stay zero.",
                )
            )
    if set(s9.get("authority_scope", [])) != S9_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s9_authority_scope_invalid",
                "S9 authority_scope must match the governed projection/lowering scope.",
            )
        )
    if not set(s9.get("may_not_use_for", [])) >= S9_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s9_authority_deny_list_incomplete",
                "S9 may_not_use_for must block production, closeout, and S10-S14 authority.",
            )
        )
    if s9.get("canonical_route") != "tools/quality/validation/run_universal_outcome_corpus.py":
        issues.append(
            _issue(
                "layer2_s9_canonical_route_invalid",
                "S9 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s9.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s9_validator_invalid",
                "S9 manifest must point at the layer2 readiness validator.",
            )
        )

    if _inventory_layer2_artifact_count(inventory) < 18:
        issues.append(
            _issue(
                "layer2_s9_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must include post-S10 registration.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S9_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s9_manifest_missing_from_inventory",
                "S9 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S9_PROJECTION_LOWERING_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s9_inventory_path_invalid",
                "S9 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s9_projection_lowering_manifest":
        issues.append(
            _issue(
                "layer2_s9_inventory_kind_invalid",
                "S9 inventory entry must carry kind=layer2_s9_projection_lowering_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s9.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s9_inventory_schema_version_invalid",
                "S9 inventory schema_version must match the manifest.",
            )
        )
    if (
        inventory_artifact.get("owner") != s9.get("owner")
        or inventory_artifact.get("status") != s9.get("status")
        or inventory_artifact.get("capability_reality_label") != "implemented"
    ):
        issues.append(
            _issue(
                "layer2_s9_inventory_status_invalid",
                "S9 inventory entry must be active, implemented, and owned by team-runtime-quality.",
            )
        )
    if inventory_artifact.get("authority_scope") != s9.get("authority_scope"):
        issues.append(
            _issue(
                "layer2_s9_inventory_authority_scope_mismatch",
                "S9 inventory authority_scope must match the manifest.",
            )
        )
    if inventory_artifact.get("may_not_use_for") != s9.get("may_not_use_for"):
        issues.append(
            _issue(
                "layer2_s9_inventory_deny_list_mismatch",
                "S9 inventory may_not_use_for must match the manifest.",
            )
        )
    if inventory_artifact.get("validator") != s9.get("validator"):
        issues.append(
            _issue(
                "layer2_s9_inventory_validator_mismatch",
                "S9 inventory validator must match the manifest.",
            )
        )
    if inventory_artifact.get("canonical_route") != s9.get("canonical_route"):
        issues.append(
            _issue(
                "layer2_s9_inventory_canonical_route_mismatch",
                "S9 inventory canonical_route must match the manifest.",
            )
        )

    later_implemented = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict)
        and row.get("slice") in S9_LATER_SLICES
        and row.get("maturity") == "implemented"
    }
    if later_implemented:
        issues.append(
            _issue(
                "layer2_s9_later_slice_maturity_invalid",
                "S9/S12 burn-down must not mark S14 artifacts implemented.",
            )
        )


def _validate_s10_outcome_prediction(
    *,
    s10: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    current_open_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s10, dict) or not s10:
        issues.append(
            _issue(
                "layer2_s10_manifest_missing",
                "S10 outcome-prediction manifest must be present.",
            )
        )
        return
    if s10.get("schema_version") != (
        "policyos.policy_design_case.layer2_s10_outcome_prediction_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s10_schema_version_invalid",
                "S10 outcome-prediction manifest schema_version is invalid.",
            )
        )
    if s10.get("status") != "active" or s10.get("owner") != "team-research":
        issues.append(
            _issue(
                "layer2_s10_status_or_owner_invalid",
                "S10 outcome-prediction manifest must be active and owned by team-research.",
            )
        )
    if s10.get("slice") != "S10" or s10.get("depends_on") != ["S5", "S6", "S8"]:
        issues.append(
            _issue(
                "layer2_s10_slice_or_dependencies_invalid",
                "S10 must depend on S5, S6, and S8 without claiming S11 calibration.",
            )
        )
    if s10.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_s10_cells_closed_invalid",
                "S10 advances forecast support only; it closes no cluster cell.",
            )
        )
    if s10.get("layer_cells_advanced") != ["outcome_prediction_welfare_comparison"]:
        issues.append(
            _issue(
                "layer2_s10_layer_cells_advanced_invalid",
                "S10 must advance only outcome_prediction_welfare_comparison.",
            )
        )
    if s10.get("expected_current_open_cell_count") != 3:
        issues.append(
            _issue(
                "layer2_s10_open_cell_count_drift",
                "S10 manifest must record expected_current_open_cell_count=3.",
            )
        )
    if current_open_cells not in (
        set(),
        S9_EXPECTED_OPEN_CELLS,
        S11_EXPECTED_OPEN_CELLS,
    ):
        issues.append(
            _issue(
                "layer2_s10_current_open_cells_invalid",
                "S10 live open cells must be the S9, post-S11, or post-S12 burn-down set.",
            )
        )

    trace_s10_artifacts = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S10"
    }
    if set(s10.get("required_artifacts", [])) != S10_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s10_required_artifacts_missing",
                "S10 required_artifacts must list ForecastSupport and ForecastCalibrationRecord.",
            )
        )
    if trace_s10_artifacts != S10_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s10_traceability_missing",
                "S10 artifacts must match layer2_artifact_traceability S10 rows.",
            )
        )

    floor = _floor_by_id(floor_governance, "s10_calibration")
    if (
        s10.get("floor_id") != "s10_calibration"
        or not floor
        or floor.get("metric") != s10.get("floor_metric")
        or floor.get("floor_owner") != "team-research"
        or floor.get("revision_rule")
        != "forecast_support_tier_change_requires_calibration_record"
    ):
        issues.append(
            _issue(
                "layer2_s10_floor_governance_invalid",
                "S10 floor must govern observable-subset calibration records.",
            )
        )
    if s10.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s10_case_count_invalid",
                "S10 manifest must record all 13 universal corpus cases.",
            )
        )
    if not _number_at_least(s10.get("observable_subset_case_count"), 4):
        issues.append(
            _issue(
                "layer2_s10_observable_subset_case_count_below_floor",
                "S10 observable subset count must be at least 4.",
            )
        )
    if not _number_at_least(
        s10.get("observable_subset_calibration_denominator"),
        4,
    ):
        issues.append(
            _issue(
                "layer2_s10_calibration_denominator_below_floor",
                "S10 observable-subset calibration denominator must be at least 4.",
            )
        )
    if s10.get("observable_subset_calibration_numerator") != s10.get(
        "observable_subset_calibration_denominator"
    ):
        issues.append(
            _issue(
                "layer2_s10_calibration_numerator_mismatch",
                "S10 calibration numerator must equal denominator.",
            )
        )
    if s10.get("observable_subset_calibration_status") != "pass":
        issues.append(
            _issue(
                "layer2_s10_calibration_status_invalid",
                "S10 observable-subset calibration status must be pass.",
            )
        )
    if s10.get("observable_subset_calibration_floor_passed") is not True:
        issues.append(
            _issue(
                "layer2_s10_calibration_floor_not_passed",
                "S10 observable-subset calibration floor must be passed.",
            )
        )
    if not s10.get("observable_subset_calibration_threshold_ref"):
        issues.append(
            _issue(
                "layer2_s10_calibration_threshold_ref_missing",
                "S10 calibration threshold ref must be present.",
            )
        )
    threshold = s10.get("observable_subset_calibration_threshold")
    if not isinstance(threshold, (int, float)):
        issues.append(
            _issue(
                "layer2_s10_calibration_threshold_missing",
                "S10 calibration threshold must be numeric.",
            )
        )
    elif not _number_at_least(
        s10.get("observable_subset_calibration_pass_rate"),
        float(threshold),
    ):
        issues.append(
            _issue(
                "layer2_s10_calibration_pass_rate_below_threshold",
                "S10 calibration pass rate must meet the governed threshold.",
            )
        )
    if not _number_at_least(s10.get("non_observable_downgrade_count"), 1):
        issues.append(
            _issue(
                "layer2_s10_non_observable_downgrade_missing",
                "S10 must record at least one non-observable downgrade.",
            )
        )
    if not _number_at_least(
        s10.get("equilibrium_contested_single_forecast_block_count"),
        1,
    ):
        issues.append(
            _issue(
                "layer2_s10_equilibrium_contested_block_missing",
                "S10 must block at least one equilibrium-contested single forecast.",
            )
        )
    if not _number_at_least(s10.get("simulation_only_evidence_block_count"), 1):
        issues.append(
            _issue(
                "layer2_s10_simulation_only_evidence_block_missing",
                "S10 must block at least one simulation-only evidence laundering case.",
            )
        )
    if s10.get("weakest_boundary_inheritance_count") != 13:
        issues.append(
            _issue(
                "layer2_s10_weakest_boundary_inheritance_count_invalid",
                "S10 must inherit weakest-boundary posture for all 13 cases.",
            )
        )
    for field in S10_FALSE_CLEAR_FIELDS:
        if s10.get(field) != 0:
            issues.append(
                _issue(
                    f"layer2_s10_{field}_nonzero",
                    f"S10 {field} must stay zero.",
                )
            )
    if set(s10.get("authority_scope", [])) != S10_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s10_authority_scope_invalid",
                "S10 authority_scope must match governed forecast-support scope.",
            )
        )
    if not set(s10.get("may_not_use_for", [])) >= S10_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s10_authority_deny_list_incomplete",
                "S10 may_not_use_for must block production, S11-S14, and future authority.",
            )
        )
    if s10.get("canonical_route") != "tools/quality/validation/run_universal_outcome_corpus.py":
        issues.append(
            _issue(
                "layer2_s10_canonical_route_invalid",
                "S10 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s10.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s10_validator_invalid",
                "S10 manifest must point at the layer2 readiness validator.",
            )
        )
    if _inventory_layer2_artifact_count(inventory) < 18:
        issues.append(
            _issue(
                "layer2_s10_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must include at least the post-S10 registration.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S10_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s10_manifest_missing_from_inventory",
                "S10 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S10_OUTCOME_PREDICTION_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s10_inventory_path_invalid",
                "S10 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s10_outcome_prediction_manifest":
        issues.append(
            _issue(
                "layer2_s10_inventory_kind_invalid",
                "S10 inventory entry must carry kind=layer2_s10_outcome_prediction_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s10.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s10_inventory_schema_version_invalid",
                "S10 inventory schema_version must match the manifest.",
            )
        )
    if (
        inventory_artifact.get("owner") != s10.get("owner")
        or inventory_artifact.get("status") != s10.get("status")
        or inventory_artifact.get("capability_reality_label") != "implemented"
    ):
        issues.append(
            _issue(
                "layer2_s10_inventory_status_invalid",
                "S10 inventory entry must be active, implemented, and owned by team-research.",
            )
        )
    if inventory_artifact.get("authority_scope") != s10.get("authority_scope"):
        issues.append(
            _issue(
                "layer2_s10_inventory_authority_scope_mismatch",
                "S10 inventory authority_scope must match the manifest.",
            )
        )
    if inventory_artifact.get("may_not_use_for") != s10.get("may_not_use_for"):
        issues.append(
            _issue(
                "layer2_s10_inventory_deny_list_mismatch",
                "S10 inventory may_not_use_for must match the manifest.",
            )
        )
    if inventory_artifact.get("validator") != s10.get("validator"):
        issues.append(
            _issue(
                "layer2_s10_inventory_validator_mismatch",
                "S10 inventory validator must match the manifest.",
            )
        )
    if inventory_artifact.get("canonical_route") != s10.get("canonical_route"):
        issues.append(
            _issue(
                "layer2_s10_inventory_canonical_route_mismatch",
                "S10 inventory canonical_route must match the manifest.",
            )
        )

    future_implemented = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict)
        and row.get("slice") in S9_LATER_SLICES
        and row.get("maturity") == "implemented"
    }
    if future_implemented:
        issues.append(
            _issue(
                "layer2_s10_future_slice_maturity_invalid",
                "S10/S12 burn-down must not mark S14 artifacts implemented.",
            )
        )


def _validate_s11_predictive_knowledge(
    *,
    s11: object,
    s14: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    inventory: dict[str, Any],
    slice_cell_matrix: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s11, dict) or not s11:
        issues.append(
            _issue(
                "layer2_s11_manifest_missing",
                "S11 predictive-knowledge manifest must be present.",
            )
        )
        return
    if s11.get("schema_version") != (
        "policyos.policy_design_case.layer2_s11_predictive_knowledge_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s11_schema_version_invalid",
                "S11 predictive-knowledge manifest schema_version is invalid.",
            )
        )
    if s11.get("status") != "active" or s11.get("owner") != "team-research":
        issues.append(
            _issue(
                "layer2_s11_status_or_owner_invalid",
                "S11 predictive-knowledge manifest must be active and owned by team-research.",
            )
        )
    if s11.get("slice") != "S11" or s11.get("depends_on") != ["S6", "S10"]:
        issues.append(
            _issue(
                "layer2_s11_slice_or_dependencies_invalid",
                "S11 must depend on S6 and S10 in that order.",
            )
        )
    if set(s11.get("cells_closed", [])) != S11_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s11_cells_closed_invalid",
                "S11 must close calibration and proof-carrying analytics cells exactly.",
            )
        )
    if set(s11.get("layer_cells_advanced", [])) != {
        "CROSS_CUTTING.method_infrastructure"
    }:
        issues.append(
            _issue(
                "layer2_s11_layer_cells_advanced_invalid",
                "S11 must advance only CROSS_CUTTING.method_infrastructure.",
            )
        )
    if s11.get("expected_current_open_cell_count") != 1:
        issues.append(
            _issue(
                "layer2_s11_open_cell_count_drift",
                "S11 manifest must record expected_current_open_cell_count=1.",
            )
        )
    if set(s11.get("remaining_open_cells", [])) != S11_EXPECTED_OPEN_CELLS:
        issues.append(
            _issue(
                "layer2_s11_remaining_open_cells_invalid",
                "S11 manifest must leave only DESIGNER_ITSELF.envelope_growth open.",
            )
        )
    if current_open_cells not in (set(), S11_EXPECTED_OPEN_CELLS):
        issues.append(
            _issue(
                "layer2_s11_current_open_cells_invalid",
                "S11 live readiness must leave only DESIGNER_ITSELF.envelope_growth open or observe the post-S12 empty set.",
            )
        )

    matrix_transitions = [
        {
            "cell_ref": str(row.get("cell_ref")),
            "from_maturity": str(row.get("from_maturity")),
            "to_maturity": str(row.get("to_maturity")),
            "slice": str(row.get("slice")),
        }
        for row in slice_cell_matrix.get("maturity_transition", [])
        if isinstance(row, dict) and row.get("slice") == "S11"
    ]
    manifest_transitions = [
        {
            "cell_ref": str(row.get("cell_ref")),
            "from_maturity": str(row.get("from_maturity")),
            "to_maturity": str(row.get("to_maturity")),
            "slice": str(row.get("slice")),
        }
        for row in s11.get("maturity_transitions", [])
        if isinstance(row, dict)
    ]
    if matrix_transitions != manifest_transitions:
        issues.append(
            _issue(
                "layer2_s11_maturity_transitions_invalid",
                "S11 manifest maturity_transitions must match the slice-cell matrix rows.",
            )
        )
    if {row["cell_ref"] for row in manifest_transitions} != S11_MATURITY_TRANSITION_CELLS:
        issues.append(
            _issue(
                "layer2_s11_maturity_transition_cells_invalid",
                "S11 maturity transitions must cover exactly the four governed predictive axes.",
            )
        )
    if any(row["cell_ref"] == "ACTOR.mandate_legitimacy" for row in manifest_transitions):
        issues.append(
            _issue(
                "layer2_s11_mandate_predictive_maturity_invalid",
                "S11 must not mark ACTOR.mandate_legitimacy as predictive maturity.",
            )
        )

    trace_s11_artifacts = {
        str(row.get("name", "")): row.get("maturity")
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S11"
    }
    if set(s11.get("required_artifacts", [])) != S11_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s11_required_artifacts_missing",
                "S11 required_artifacts must list calibration, upgrade, proof, and integrity records.",
            )
        )
    if set(trace_s11_artifacts) != S11_REQUIRED_ARTIFACTS or any(
        maturity != "implemented" for maturity in trace_s11_artifacts.values()
    ):
        issues.append(
            _issue(
                "layer2_s11_traceability_missing",
                "S11 artifacts must all be implemented in layer2_artifact_traceability.",
            )
        )

    floor = _floor_by_id(floor_governance, "s11_axis_calibration")
    if (
        s11.get("floor_id") != "s11_axis_calibration"
        or not floor
        or floor.get("metric") != s11.get("floor_metric")
        or floor.get("floor_owner") != "team-research"
        or floor.get("revision_rule")
        != "model_relaxation_requires_calibration_before_relaxation"
    ):
        issues.append(
            _issue(
                "layer2_s11_floor_governance_invalid",
                "S11 floor must govern per-axis predictive calibration before relaxation.",
            )
        )
    axis_count = s11.get("axis_count")
    if axis_count != 52:
        issues.append(
            _issue(
                "layer2_s11_axis_count_invalid",
                "S11 axis_count must be 52 across the 13-case corpus.",
            )
        )
    if s11.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s11_case_count_invalid",
                "S11 manifest must record all 13 universal corpus cases.",
            )
        )
    if not s11.get("per_axis_predictive_calibration_threshold_ref"):
        issues.append(
            _issue(
                "layer2_s11_calibration_threshold_ref_missing",
                "S11 per-axis calibration threshold ref must be present.",
            )
        )
    threshold = s11.get("per_axis_predictive_calibration_threshold")
    if not isinstance(threshold, (int, float)):
        issues.append(
            _issue(
                "layer2_s11_calibration_threshold_missing",
                "S11 per-axis calibration threshold must be numeric.",
            )
        )
    if s11.get("per_axis_predictive_calibration_denominator") != axis_count:
        issues.append(
            _issue(
                "layer2_s11_calibration_denominator_invalid",
                "S11 per-axis calibration denominator must equal axis_count.",
            )
        )
    if isinstance(threshold, (int, float)) and not _number_at_least(
        s11.get("per_axis_predictive_calibration_pass_rate"),
        float(threshold),
    ):
        issues.append(
            _issue(
                "layer2_s11_calibration_pass_rate_below_threshold",
                "S11 per-axis calibration pass rate must meet the governed threshold.",
            )
        )
    if s11.get("per_axis_predictive_calibration_status") != "pass":
        issues.append(
            _issue(
                "layer2_s11_calibration_status_invalid",
                "S11 per-axis calibration status must be pass.",
            )
        )
    if s11.get("per_axis_predictive_calibration_floor_passed") is not True:
        issues.append(
            _issue(
                "layer2_s11_calibration_floor_not_passed",
                "S11 per-axis calibration floor-passed flag must be true.",
            )
        )
    predictive_axis_count = s11.get("predictive_axis_count")
    reverted_axis_count = s11.get("reverted_fail_closed_axis_count")
    if (
        not isinstance(predictive_axis_count, int)
        or not isinstance(reverted_axis_count, int)
        or predictive_axis_count + reverted_axis_count != axis_count
    ):
        issues.append(
            _issue(
                "layer2_s11_axis_partition_invalid",
                "S11 predictive and reverted fail-closed axis counts must sum to axis_count.",
            )
        )
    if not _number_at_least(s11.get("method_infrastructure_consumed_count"), 1):
        issues.append(
            _issue(
                "layer2_s11_method_infrastructure_not_consumed",
                "S11 method-infrastructure consumed count must be non-zero.",
            )
        )
    if s11.get("weakest_boundary_inheritance_count") != axis_count:
        issues.append(
            _issue(
                "layer2_s11_weakest_boundary_inheritance_count_invalid",
                "S11 weakest-boundary inheritance count must cover every axis row.",
            )
        )
    for field in S11_FALSE_CLEAR_FIELDS:
        if s11.get(f"{field}_false_clear_count") != 0:
            issues.append(
                _issue(
                    f"layer2_s11_{field}_false_clear_count_nonzero",
                    f"S11 {field}_false_clear_count must stay zero.",
                )
            )
    false_clear_counts = s11.get("false_clear_counts")
    if not isinstance(false_clear_counts, dict) or set(false_clear_counts) != set(
        S11_FALSE_CLEAR_FIELDS
    ):
        issues.append(
            _issue(
                "layer2_s11_false_clear_counts_invalid",
                "S11 false_clear_counts must match the governed S11 false-clear fields.",
            )
        )
    elif any(value != 0 for value in false_clear_counts.values()):
        issues.append(
            _issue(
                "layer2_s11_false_clear_counts_nonzero",
                "S11 nested false_clear_counts must all stay zero.",
            )
        )
    if set(s11.get("authority_scope", [])) != S11_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s11_authority_scope_invalid",
                "S11 authority_scope must match governed predictive-knowledge scope.",
            )
        )
    if not set(s11.get("may_not_use_for", [])) >= S11_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s11_authority_deny_list_incomplete",
                "S11 may_not_use_for must block production, future-slice, and model-authority laundering.",
            )
        )
    authority_boundary = s11.get("authority_boundary")
    if not isinstance(authority_boundary, dict) or set(
        authority_boundary.get("authoritative_for", [])
    ) != S11_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s11_authority_boundary_invalid",
                "S11 authority_boundary must expose only predictive-knowledge authority.",
            )
        )
    if (
        s11.get("canonical_route")
        != "tools/quality/validation/run_universal_outcome_corpus.py"
    ):
        issues.append(
            _issue(
                "layer2_s11_canonical_route_invalid",
                "S11 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s11.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s11_validator_invalid",
                "S11 manifest must point at the layer2 readiness validator.",
            )
        )

    inventory_count = _inventory_layer2_artifact_count(inventory)
    if inventory_count not in {19, 20, 21, 22}:
        issues.append(
            _issue(
                "layer2_s11_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must be 19 after S11, 20 after S12, 21 after S13, or 22 after S14.",
            )
        )
    if inventory_count == 22 and not _s14_manifest_owns_inventory_count(
        s14=s14,
        inventory=inventory,
    ):
        issues.append(
            _issue(
                "layer2_s11_post_s14_inventory_requires_valid_s14_manifest",
                "S11 may accept inventory count 22 only when the S14 manifest is present, active, implemented, and registered.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S11_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s11_manifest_missing_from_inventory",
                "S11 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S11_PREDICTIVE_KNOWLEDGE_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s11_inventory_path_invalid",
                "S11 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s11_predictive_knowledge_manifest":
        issues.append(
            _issue(
                "layer2_s11_inventory_kind_invalid",
                "S11 inventory entry must carry kind=layer2_s11_predictive_knowledge_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s11.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s11_inventory_schema_version_invalid",
                "S11 inventory schema_version must match the manifest.",
            )
        )
    if (
        inventory_artifact.get("owner") != s11.get("owner")
        or inventory_artifact.get("status") != s11.get("status")
        or inventory_artifact.get("capability_reality_label") != "implemented"
    ):
        issues.append(
            _issue(
                "layer2_s11_inventory_status_invalid",
                "S11 inventory entry must be active, implemented, and owned by team-research.",
            )
        )
    if inventory_artifact.get("authority_scope") != s11.get("authority_scope"):
        issues.append(
            _issue(
                "layer2_s11_inventory_authority_scope_mismatch",
                "S11 inventory authority_scope must match the manifest.",
            )
        )
    if inventory_artifact.get("may_not_use_for") != s11.get("may_not_use_for"):
        issues.append(
            _issue(
                "layer2_s11_inventory_deny_list_mismatch",
                "S11 inventory may_not_use_for must match the manifest.",
            )
        )

    future_implemented = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict)
        and row.get("slice") in set()
        and row.get("maturity") == "implemented"
    }
    if future_implemented:
        issues.append(
            _issue(
                "layer2_s11_future_slice_maturity_invalid",
                "S11/S12 burn-down must not mark S14 artifacts implemented.",
            )
        )
    assignments = {
        str(row.get("cell_ref")): str(row.get("slice"))
        for row in slice_cell_matrix.get("assignment", [])
        if isinstance(row, dict)
    }
    future_cell_refs = {
        cell_ref
        for cell_ref, slice_name in assignments.items()
        if slice_name in set()
    }
    production_authority_refs = {
        f"{cluster}.{axis}"
        for cluster, axes in cluster_map_payload.get("cell", {}).items()
        if isinstance(axes, dict)
        for axis, cell in axes.items()
        if isinstance(cell, dict)
        and (
            "production_authority" in str(cell.get("authority_dim", ""))
            or "production_authority" in str(cell.get("action", ""))
        )
    }
    for cell_ref in sorted(future_cell_refs | production_authority_refs):
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cell = cluster_map_payload.get("cell", {}).get(cluster, {}).get(axis, {})
        if isinstance(cell, dict) and cell.get("ratchet_state") == "implemented":
            issues.append(
                _issue(
                    "layer2_s11_future_or_production_cell_implemented",
                    f"S11 must not mark future or production authority cell implemented: {cell_ref}.",
                )
            )


def _validate_s12_resource_economics(
    *,
    s12: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    assigned_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s12, dict) or not s12:
        issues.append(
            _issue(
                "layer2_s12_manifest_missing",
                "S12 resource-economics manifest must be present.",
            )
        )
        return
    if s12.get("schema_version") != (
        "policyos.policy_design_case.layer2_s12_resource_economics_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s12_schema_version_invalid",
                "S12 resource-economics manifest schema_version is invalid.",
            )
        )
    if (
        s12.get("status") != "active"
        or s12.get("owner") != "principal-governance"
        or s12.get("slice") != "S12"
    ):
        issues.append(
            _issue(
                "layer2_s12_status_owner_or_slice_invalid",
                "S12 manifest must be active, principal-owned, and slice=S12.",
            )
        )
    if s12.get("depends_on") != ["S3", "S7"]:
        issues.append(
            _issue(
                "layer2_s12_dependencies_invalid",
                "S12 must depend on S3 and S7 in that order.",
            )
        )
    if set(s12.get("cells_closed", [])) != S12_CLOSED_CELLS:
        issues.append(
            _issue(
                "layer2_s12_cells_closed_invalid",
                "S12 must close exactly DESIGNER_ITSELF.envelope_growth.",
            )
        )
    if s12.get("expected_current_open_cell_count") != 0:
        issues.append(
            _issue(
                "layer2_s12_open_cell_count_drift",
                "S12 manifest must record expected_current_open_cell_count=0.",
            )
        )
    if s12.get("remaining_open_cells") != [] or s12.get("burn_down_complete") is not True:
        issues.append(
            _issue(
                "layer2_s12_burn_down_not_complete",
                "S12 must declare burn_down_complete with no remaining open cells.",
            )
        )
    if current_open_cells:
        issues.append(
            _issue(
                "layer2_s12_live_open_cells_remaining",
                "S12 live readiness must have an empty current_open_cells set.",
            )
        )
    if S12_CLOSED_CELLS - assigned_cells:
        issues.append(
            _issue(
                "layer2_s12_cell_not_assigned",
                "S12 closed cell must be in the frozen slice-cell baseline.",
            )
        )

    cell = (
        cluster_map_payload.get("cell", {})
        .get("DESIGNER_ITSELF", {})
        .get("envelope_growth", {})
    )
    if not isinstance(cell, dict) or cell.get("ratchet_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s12_cluster_cell_not_implemented",
                "DESIGNER_ITSELF.envelope_growth must be implemented.",
            )
        )
    else:
        if cell.get("p01_chain") != "implemented":
            issues.append(
                _issue(
                    "layer2_s12_cluster_cell_p01_chain_invalid",
                    "S12 envelope-growth cell must have p01_chain=implemented.",
                )
            )
        if cell.get("owner_module") != (
            "src/polisyos/runtime/quality/design_axes/resource_economics.py"
        ):
            issues.append(
                _issue(
                    "layer2_s12_cluster_cell_owner_invalid",
                    "S12 envelope-growth cell owner_module must be the resource-economics producer.",
                )
            )
        if cell.get("gap") != "none_for_s12_resource_economics_scope":
            issues.append(
                _issue(
                    "layer2_s12_cluster_cell_gap_invalid",
                    "S12 envelope-growth cell must record no S12-scope gap.",
                )
            )
        if cell.get("firewall") != "P13_governance_gravity":
            issues.append(
                _issue(
                    "layer2_s12_cluster_cell_firewall_invalid",
                    "S12 envelope-growth cell must keep the P13 governance-gravity firewall.",
                )
            )

    trace_s12_artifacts = {
        str(row.get("name", "")): row.get("maturity")
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S12"
    }
    if set(s12.get("required_artifacts", [])) != S12_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s12_required_artifacts_missing",
                "S12 required_artifacts must list resource policy, growth, thermometer, throughput, and integrity artifacts.",
            )
        )
    if set(trace_s12_artifacts) != S12_REQUIRED_ARTIFACTS or any(
        maturity != "implemented" for maturity in trace_s12_artifacts.values()
    ):
        issues.append(
            _issue(
                "layer2_s12_traceability_missing",
                "S12 artifacts must all be implemented in layer2_artifact_traceability.",
            )
        )

    floor = _floor_by_id(floor_governance, "s12_growth_thermometers")
    if (
        s12.get("floor_id") != "s12_growth_thermometers"
        or not floor
        or floor.get("metric") != "reuse_rate_and_override_rate_trend"
        or floor.get("floor_owner") != "principal-governance"
        or floor.get("revision_rule") != "growth_counting_requires_envelope_delta"
    ):
        issues.append(
            _issue(
                "layer2_s12_floor_governance_invalid",
                "S12 floor must govern reuse/override thermometers and require envelope deltas for growth.",
            )
        )
    if s12.get("case_count") != 13:
        issues.append(
            _issue(
                "layer2_s12_case_count_invalid",
                "S12 manifest must record all 13 universal corpus cases.",
            )
        )
    if not _number_at_least(s12.get("voi_site_count"), 3):
        issues.append(
            _issue(
                "layer2_s12_voi_site_count_below_floor",
                "S12 must allocate VOI across at least three sites.",
            )
        )
    if s12.get("typed_budget_count") != 5:
        issues.append(
            _issue(
                "layer2_s12_typed_budget_count_invalid",
                "S12 must carry all five typed budget kinds.",
            )
        )
    if s12.get("override_rate_trend") not in {"improving", "flat"}:
        issues.append(
            _issue(
                "layer2_s12_override_rate_trend_invalid",
                "S12 override-rate trend must be improving or flat.",
            )
        )
    if s12.get("reuse_rate_trend") not in {"improving", "flat"}:
        issues.append(
            _issue(
                "layer2_s12_reuse_rate_trend_invalid",
                "S12 reuse-rate trend must be improving or flat.",
            )
        )
    if s12.get("held_out_status") != "pending_s14":
        issues.append(
            _issue(
                "layer2_s12_held_out_status_invalid",
                "S12 held-out battery status must remain pending_s14.",
            )
        )
    if s12.get("growth_without_envelope_delta_count") != 0:
        issues.append(
            _issue(
                "layer2_s12_growth_without_delta_nonzero",
                "S12 must block growth without envelope deltas.",
            )
        )
    false_clear_counts = s12.get("false_clear_counts")
    if not isinstance(false_clear_counts, dict) or set(false_clear_counts) != set(
        S12_FALSE_CLEAR_FIELDS
    ):
        issues.append(
            _issue(
                "layer2_s12_false_clear_counts_invalid",
                "S12 false_clear_counts must match the governed S12 false-clear fields.",
            )
        )
    elif any(value != 0 for value in false_clear_counts.values()):
        issues.append(
            _issue(
                "layer2_s12_false_clear_counts_nonzero",
                "S12 nested false_clear_counts must all stay zero.",
            )
        )
    for field in S12_FALSE_CLEAR_FIELDS:
        if s12.get(f"{field}_false_clear_count") != 0:
            issues.append(
                _issue(
                    f"layer2_s12_{field}_false_clear_count_nonzero",
                    f"S12 {field}_false_clear_count must stay zero.",
                )
            )

    if set(s12.get("authority_scope", [])) != S12_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s12_authority_scope_invalid",
                "S12 authority_scope must match governed resource-economics scope.",
            )
        )
    if not set(s12.get("may_not_use_for", [])) >= S12_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s12_authority_deny_list_incomplete",
                "S12 may_not_use_for must block production, future-slice, optimizer, and budget laundering.",
            )
        )
    if (
        set(s12.get("authority_scope", []))
        & {
            "production_authority",
            "production_recommendation",
            "preference_learning_authority",
            "mdp_bandit_optimizer_authority",
            "s13_envelope_shrink",
            "s13_accountability_closure",
            "s14_universality",
        }
    ):
        issues.append(
            _issue(
                "layer2_s12_future_or_production_authority_claimed",
                "S12 must not claim production, optimizer, S13, or S14 authority.",
            )
        )
    if (
        s12.get("canonical_route")
        != "tools/quality/validation/run_universal_outcome_corpus.py"
    ):
        issues.append(
            _issue(
                "layer2_s12_canonical_route_invalid",
                "S12 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s12.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s12_validator_invalid",
                "S12 manifest must point at the layer2 readiness validator.",
            )
        )

    if _inventory_layer2_artifact_count(inventory) not in {20, 21, 22}:
        issues.append(
            _issue(
                "layer2_s12_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must be 20 after S12, 21 after S13, or 22 after S14.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S12_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s12_manifest_missing_from_inventory",
                "S12 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if inventory_artifact.get("path") != DEFAULT_S12_RESOURCE_ECONOMICS_MANIFEST_PATH.as_posix():
        issues.append(
            _issue(
                "layer2_s12_inventory_path_invalid",
                "S12 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s12_resource_economics_manifest":
        issues.append(
            _issue(
                "layer2_s12_inventory_kind_invalid",
                "S12 inventory entry must carry kind=layer2_s12_resource_economics_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s12.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s12_inventory_schema_version_invalid",
                "S12 inventory schema_version must match the manifest.",
            )
        )
    for field in ("owner", "status", "authority_scope", "may_not_use_for", "validator", "canonical_route"):
        if inventory_artifact.get(field) != s12.get(field):
            issues.append(
                _issue(
                    f"layer2_s12_inventory_{field}_mismatch",
                    f"S12 inventory {field} must match the manifest.",
                )
            )
    if inventory_artifact.get("capability_reality_label") != "implemented":
        issues.append(
            _issue(
                "layer2_s12_inventory_status_invalid",
                "S12 inventory entry must carry capability_reality_label=implemented.",
            )
        )

    future_implemented = {
        str(row.get("name", ""))
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict)
        and row.get("slice") in set()
        and row.get("maturity") == "implemented"
    }
    if future_implemented:
        issues.append(
            _issue(
                "layer2_s12_future_slice_maturity_invalid",
                "S12 must not mark S14 artifacts implemented.",
            )
        )


def _validate_s13_post_deploy_accountability(
    *,
    s13: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s13, dict) or not s13:
        issues.append(
            _issue(
                "layer2_s13_manifest_missing",
                "S13 post-deploy accountability manifest must be present.",
            )
        )
        return
    if s13.get("schema_version") != (
        "policyos.policy_design_case.layer2_s13_post_deploy_accountability_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s13_schema_version_invalid",
                "S13 post-deploy accountability manifest schema_version is invalid.",
            )
        )
    if (
        s13.get("status") != "active"
        or s13.get("owner") != "governance-board"
        or s13.get("slice") != "S13"
    ):
        issues.append(
            _issue(
                "layer2_s13_status_owner_or_slice_invalid",
                "S13 manifest must be active, governance-board-owned, and slice=S13.",
            )
        )
    if s13.get("depends_on") != ["S7", "S9", "S12"]:
        issues.append(
            _issue(
                "layer2_s13_dependencies_invalid",
                "S13 must depend on S7, S9, and S12 in that order.",
            )
        )
    if s13.get("slice_label") != "post_deploy_accountability_learning":
        issues.append(
            _issue(
                "layer2_s13_slice_label_invalid",
                "S13 slice_label must be post_deploy_accountability_learning.",
            )
        )
    if s13.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_s13_cells_closed_invalid",
                "S13 must advance envelope_growth without claiming a newly closed cell.",
            )
        )
    if s13.get("layer_cells_advanced") != ["DESIGNER_ITSELF.envelope_growth"]:
        issues.append(
            _issue(
                "layer2_s13_layer_cells_advanced_invalid",
                "S13 must advance exactly DESIGNER_ITSELF.envelope_growth.",
            )
        )
    if s13.get("expected_current_open_cell_count") != 0:
        issues.append(
            _issue(
                "layer2_s13_open_cell_count_drift",
                "S13 manifest must record expected_current_open_cell_count=0.",
            )
        )
    if s13.get("remaining_open_cells") != [] or s13.get("burn_down_complete") is not True:
        issues.append(
            _issue(
                "layer2_s13_burn_down_state_invalid",
                "S13 must preserve burn_down_complete with no remaining open cells.",
            )
        )
    if current_open_cells:
        issues.append(
            _issue(
                "layer2_s13_live_open_cells_remaining",
                "S13 live readiness must keep current_open_cells empty.",
            )
        )

    cell = (
        cluster_map_payload.get("cell", {})
        .get("DESIGNER_ITSELF", {})
        .get("envelope_growth", {})
    )
    if not isinstance(cell, dict) or cell.get("ratchet_state") != "implemented":
        issues.append(
            _issue(
                "layer2_s13_cluster_cell_not_implemented",
                "DESIGNER_ITSELF.envelope_growth must remain implemented.",
            )
        )
    else:
        if cell.get("owner_module") != (
            "src/polisyos/runtime/quality/design_axes/resource_economics.py"
        ):
            issues.append(
                _issue(
                    "layer2_s13_cluster_cell_owner_drift",
                    "S13 must not move envelope_growth ownership away from S12 resource economics.",
                )
            )
        if cell.get("p01_chain") != "implemented":
            issues.append(
                _issue(
                    "layer2_s13_cluster_cell_p01_chain_invalid",
                    "S13 envelope-growth advancement must preserve p01_chain=implemented.",
                )
            )
        if cell.get("gap") != "none_for_s12_resource_economics_scope":
            issues.append(
                _issue(
                    "layer2_s13_cluster_cell_gap_invalid",
                    "S13 must preserve the S12-scoped envelope-growth gap marker.",
                )
            )
        if cell.get("firewall") != "P13_governance_gravity":
            issues.append(
                _issue(
                    "layer2_s13_cluster_cell_firewall_invalid",
                    "S13 must preserve the P13 governance-gravity firewall.",
                )
            )
        action = str(cell.get("action", ""))
        if "S13" not in action or "bidirectional" not in action:
            issues.append(
                _issue(
                    "layer2_s13_cluster_cell_action_missing_revision",
                    "DESIGNER_ITSELF.envelope_growth action must mention S13 bidirectional envelope revision.",
                )
            )

    trace_s13_artifacts = [
        row
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S13"
    ]
    trace_names = [str(row.get("name", "")) for row in trace_s13_artifacts]
    if set(s13.get("required_artifacts", [])) != S13_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s13_required_artifacts_invalid",
                "S13 required_artifacts must list the six post-deploy accountability artifacts.",
            )
        )
    if (
        set(trace_names) != S13_REQUIRED_ARTIFACTS
        or any(trace_names.count(name) != 1 for name in S13_REQUIRED_ARTIFACTS)
        or any(row.get("maturity") != "implemented" for row in trace_s13_artifacts)
    ):
        issues.append(
            _issue(
                "layer2_s13_traceability_missing",
                "S13 artifacts must be implemented exactly once in layer2_artifact_traceability.",
            )
        )
    artifact_paths = s13.get("artifact_paths")
    if not isinstance(artifact_paths, dict) or set(artifact_paths) != S13_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s13_artifact_paths_invalid",
                "S13 manifest must bind exact artifact path refs for all six artifacts.",
            )
        )

    floor = _floor_by_id(floor_governance, "s13_accountability")
    if (
        s13.get("floor_id") != "s13_accountability"
        or s13.get("floor_metric") != "a_before_b_ratio_and_attribution_resolution"
        or not floor
        or floor.get("metric") != "a_before_b_ratio_and_attribution_resolution"
        or floor.get("floor_owner") != "governance-board"
        or floor.get("revision_rule") != "post_deploy_learning_requires_attribution_gate"
    ):
        issues.append(
            _issue(
                "layer2_s13_floor_governance_invalid",
                "S13 floor must govern A-before-B and attribution-gated accountability.",
            )
        )
    exact_metrics = {
        "case_count": 13,
        "monitorability_rate": 1.0,
        "a_before_b_ratio": 1.0,
        "attribution_resolution_rate": 1.0,
        "mape_k_trace_completeness_rate": 1.0,
        "action_item_closure_rate": 1.0,
        "oversight_effectiveness_link_rate": 1.0,
        "learning_without_attribution_count": 0,
        "growth_without_assurance_delta_count": 0,
    }
    for field, expected in exact_metrics.items():
        if s13.get(field) != expected:
            issues.append(
                _issue(
                    f"layer2_s13_{field}_invalid",
                    f"S13 {field} must be {expected}.",
                )
            )
    at_least_metrics = {
        "envelope_shrink_count": 1,
        "envelope_expansion_count": 1,
        "envelope_shrink_latency_recorded_count": 1,
        "unattributable_accountability_without_training_count": 1,
        "rubber_stamp_divergence_review_required_count": 1,
    }
    for field, minimum in at_least_metrics.items():
        if not _number_at_least(s13.get(field), minimum):
            issues.append(
                _issue(
                    f"layer2_s13_{field}_below_floor",
                    f"S13 {field} must be at least {minimum}.",
                )
            )

    false_clear_counts = s13.get("false_clear_counts")
    if not isinstance(false_clear_counts, dict) or tuple(false_clear_counts) != (
        S13_FALSE_CLEAR_FIELDS
    ):
        issues.append(
            _issue(
                "layer2_s13_false_clear_counts_invalid",
                "S13 false_clear_counts must match the governed anti-learning false-clear fields.",
            )
        )
    elif any(value != 0 for value in false_clear_counts.values()):
        issues.append(
            _issue(
                "layer2_s13_false_clear_counts_nonzero",
                "S13 nested false_clear_counts must all stay zero.",
            )
        )
    for field in S13_FALSE_CLEAR_FIELDS:
        if s13.get(f"{field}_false_clear_count") != 0:
            issues.append(
                _issue(
                    f"layer2_s13_{field}_false_clear_count_nonzero",
                    f"S13 {field}_false_clear_count must stay zero.",
                )
            )

    if set(s13.get("firewalls", [])) < {
        "anti_learning_authority_boundary",
        "c41_learned_prior_current_evidence_slot",
        "a_before_b_sequence",
        "closed_case_replay_integrity",
        "lucas_post_policy_pre_policy_evidence",
        "s7_governance_decision_bypass",
    }:
        issues.append(
            _issue(
                "layer2_s13_firewalls_incomplete",
                "S13 manifest must declare all anti-learning and replay firewalls.",
            )
        )
    if set(s13.get("surfaces", [])) < {
        "public_accountability_note",
        "expert_projection",
        "machine_projection",
        "reviewer_action_reissue_view",
    }:
        issues.append(
            _issue(
                "layer2_s13_surfaces_incomplete",
                "S13 manifest must expose public, expert, machine, and reviewer surfaces.",
            )
        )
    if set(s13.get("embedded_trace_requirements", [])) < {
        "mape_k_monitor_refs",
        "mape_k_analyze_refs",
        "mape_k_plan_refs",
        "mape_k_execute_refs",
        "mape_k_knowledge_refs",
        "typed_diagnostic_record_composition_refs",
        "action_item_closure_refs",
        "oversight_effectiveness_refs",
        "oversight_accountability_state_coverage",
        "public_revision_state_refs_as_accountability_notes",
        "case_lifecycle_reissue_disposition_refs",
    }:
        issues.append(
            _issue(
                "layer2_s13_embedded_trace_requirements_incomplete",
                "S13 manifest must declare MAPE-K, diagnostic, oversight, public revision, and lifecycle reissue trace refs.",
            )
        )

    authority_scope = set(s13.get("authority_scope", []))
    deny_list = set(s13.get("may_not_use_for", []))
    if authority_scope != S13_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s13_authority_scope_invalid",
                "S13 authority_scope must match governed post-deploy accountability scope.",
            )
        )
    if not deny_list >= S13_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s13_authority_deny_list_incomplete",
                "S13 may_not_use_for must block production, evidence-slot, learning, LLM, and S14 authority.",
            )
        )
    forbidden_scope = {
        "production_rollout_authority",
        "production_authority",
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
        "universality",
        "llm_attribution_authority",
        "local_governance_enum_for_reissue",
    }
    if authority_scope & forbidden_scope:
        issues.append(
            _issue(
                "layer2_s13_forbidden_authority_claimed",
                "S13 must not claim production, evidence-slot, LLM attribution, local governance enum, or S14 universality authority.",
            )
        )
    authority_boundary = s13.get("authority_boundary")
    if (
        not isinstance(authority_boundary, dict)
        or set(authority_boundary.get("authoritative_for", [])) != S13_REQUIRED_AUTHORITY_SCOPE
        or not set(authority_boundary.get("may_not_use_for", [])) >= S13_REQUIRED_DENY
    ):
        issues.append(
            _issue(
                "layer2_s13_authority_boundary_invalid",
                "S13 authority_boundary must mirror S13 scope and anti-learning denials.",
            )
        )
    if (
        s13.get("canonical_route")
        != "tools/quality/validation/run_universal_outcome_corpus.py"
    ):
        issues.append(
            _issue(
                "layer2_s13_canonical_route_invalid",
                "S13 manifest must point at the universal outcome corpus runner.",
            )
        )
    if (
        s13.get("validator")
        != "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    ):
        issues.append(
            _issue(
                "layer2_s13_validator_invalid",
                "S13 manifest must point at the layer2 readiness validator.",
            )
        )

    if _inventory_layer2_artifact_count(inventory) not in {21, 22}:
        issues.append(
            _issue(
                "layer2_s13_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must be 21 after registering S13 or 22 after registering S14.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S13_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s13_manifest_missing_from_inventory",
                "S13 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if (
        inventory_artifact.get("path")
        != DEFAULT_S13_POST_DEPLOY_ACCOUNTABILITY_MANIFEST_PATH.as_posix()
    ):
        issues.append(
            _issue(
                "layer2_s13_inventory_path_invalid",
                "S13 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s13_post_deploy_accountability_manifest":
        issues.append(
            _issue(
                "layer2_s13_inventory_kind_invalid",
                "S13 inventory entry must carry kind=layer2_s13_post_deploy_accountability_manifest.",
            )
        )
    if inventory_artifact.get("schema_version") != s13.get("schema_version"):
        issues.append(
            _issue(
                "layer2_s13_inventory_schema_version_invalid",
                "S13 inventory schema_version must match the manifest.",
            )
        )
    for field in (
        "owner",
        "status",
        "authority_scope",
        "may_not_use_for",
        "validator",
        "canonical_route",
    ):
        if inventory_artifact.get(field) != s13.get(field):
            issues.append(
                _issue(
                    f"layer2_s13_inventory_{field}_mismatch",
                    f"S13 inventory {field} must match the manifest.",
                )
            )
    if inventory_artifact.get("capability_reality_label") != "implemented":
        issues.append(
            _issue(
                "layer2_s13_inventory_status_invalid",
                "S13 inventory entry must carry capability_reality_label=implemented.",
            )
        )
    if "s14_universality" not in set(inventory_artifact.get("may_not_use_for", [])):
        issues.append(
            _issue(
                "layer2_s13_inventory_s14_denial_missing",
                "S13 inventory must deny S14 universality authority.",
            )
        )
    if "s14_universality" in set(inventory_artifact.get("authority_scope", [])):
        issues.append(
            _issue(
                "layer2_s13_inventory_s14_authority_claimed",
                "S13 inventory must not claim S14 universality authority.",
            )
        )


def _validate_s14_universality_assurance(
    *,
    s14: object,
    floor_governance: dict[str, Any],
    artifact_traceability: dict[str, Any],
    corpus_partition: dict[str, Any],
    cluster_map_payload: dict[str, Any],
    current_open_cells: set[str],
    inventory: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(s14, dict) or not s14:
        issues.append(
            _issue(
                "layer2_s14_manifest_missing",
                "S14 universality-assurance manifest must be present.",
            )
        )
        return
    if s14.get("schema_version") != (
        "policyos.policy_design_case.layer2_s14_universality_assurance_manifest.v1"
    ):
        issues.append(
            _issue(
                "layer2_s14_schema_version_invalid",
                "S14 universality-assurance manifest schema_version is invalid.",
            )
        )
    if s14.get("status") != "active" or s14.get("owner") != "governance-board":
        issues.append(
            _issue(
                "layer2_s14_status_or_owner_invalid",
                "S14 manifest must be active and owned by governance-board.",
            )
        )
    if s14.get("slice") != "S14" or s14.get("depends_on") != [
        f"S{number}" for number in range(14)
    ]:
        issues.append(
            _issue(
                "layer2_s14_slice_or_dependencies_invalid",
                "S14 must depend on S0 through S13 in order.",
            )
        )
    if s14.get("slice_label") != "evaluation_redesign_universality_assurance_battery":
        issues.append(
            _issue(
                "layer2_s14_slice_label_invalid",
                "S14 manifest must carry the governed slice label.",
            )
        )
    if s14.get("cells_closed") != []:
        issues.append(
            _issue(
                "layer2_s14_cells_closed_invalid",
                "S14 must not close a new cluster cell.",
            )
        )
    if s14.get("layer_cells_advanced") != ["DESIGNER_ITSELF.evaluation_corpus"]:
        issues.append(
            _issue(
                "layer2_s14_layer_cells_advanced_invalid",
                "S14 must advance only DESIGNER_ITSELF.evaluation_corpus.",
            )
        )
    if (
        s14.get("expected_current_open_cell_count") != 0
        or s14.get("remaining_open_cells") != []
        or s14.get("burn_down_complete") is not True
        or current_open_cells
    ):
        issues.append(
            _issue(
                "layer2_s14_open_cell_state_invalid",
                "S14 readiness must observe zero remaining open Layer 2 cells.",
            )
        )

    floor = _floor_by_id(floor_governance, "s14_universality")
    if (
        s14.get("floor_id") != "s14_universality"
        or not floor
        or floor.get("metric") != s14.get("floor_metric")
        or floor.get("floor_owner") != "governance-board"
        or floor.get("revision_rule")
        != "sealed_battery_change_requires_freeze_hash_rotation"
    ):
        issues.append(
            _issue(
                "layer2_s14_floor_governance_invalid",
                "S14 floor must govern sealed-battery replay and breadth thresholds.",
            )
        )

    trace_s14_rows = [
        row
        for row in artifact_traceability.get("artifact", [])
        if isinstance(row, dict) and row.get("slice") == "S14"
    ]
    trace_s14_names = [str(row.get("name", "")) for row in trace_s14_rows]
    if (
        set(trace_s14_names) != S14_REQUIRED_ARTIFACTS
        or len(trace_s14_names) != len(S14_REQUIRED_ARTIFACTS)
        or any(row.get("maturity") != "implemented" for row in trace_s14_rows)
    ):
        issues.append(
            _issue(
                "layer2_s14_traceability_missing",
                "S14 artifacts must be implemented exactly once in traceability.",
            )
        )
    if set(s14.get("required_artifacts", [])) != S14_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s14_required_artifacts_invalid",
                "S14 required_artifacts must list the six governed S14 contracts.",
            )
        )
    supporting_records = s14.get("supporting_records", {})
    if not isinstance(supporting_records, dict) or set(supporting_records) != (
        S14_REQUIRED_SUPPORTING_RECORDS
    ):
        issues.append(
            _issue(
                "layer2_s14_supporting_records_invalid",
                "S14 supporting_records must list the seven governed support records.",
            )
        )
        supporting_records = {}

    artifact_records = s14.get("artifact_records", {})
    if not isinstance(artifact_records, dict):
        issues.append(
            _issue(
                "layer2_s14_artifact_records_invalid",
                "S14 artifact_records must carry refs and statuses for the six artifacts.",
            )
        )
        artifact_records = {}
    if set(artifact_records) != S14_REQUIRED_ARTIFACTS:
        issues.append(
            _issue(
                "layer2_s14_artifact_records_missing",
                "S14 artifact_records must mirror required_artifacts exactly.",
            )
        )

    sealed = corpus_partition.get("sealed_universality_battery", {})
    empty_hash = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    if (
        not isinstance(sealed, dict)
        or sealed.get("path") != s14.get("sealed_battery_path")
        or sealed.get("access") != "ci_gate_only"
        or sealed.get("owner") != "governance-board"
        or sealed.get("extensible") is not False
        or sealed.get("freeze_hash") != s14.get("sealed_battery_freeze_hash")
        or sealed.get("freeze_hash") in {"", empty_hash}
    ):
        issues.append(
            _issue(
                "layer2_s14_sealed_battery_partition_invalid",
                "S14 sealed battery partition must match the manifest freeze hash and access rules.",
            )
        )
    if s14.get("sealed_battery_integrity_status") != "pass":
        issues.append(
            _issue(
                "layer2_s14_sealed_battery_integrity_not_pass",
                "S14 sealed battery integrity status must be pass.",
            )
        )

    if s14.get("d4_corpus_track_count") != 19:
        issues.append(
            _issue(
                "layer2_s14_d4_track_count_invalid",
                "S14 D4 corpus track coverage must cover all 19 governed tracks.",
            )
        )
    if s14.get("expert_oracle_layer_count") != 4:
        issues.append(
            _issue(
                "layer2_s14_oracle_layer_count_invalid",
                "S14 expert-oracle bootstrap must register four layers.",
            )
        )
    if s14.get("breadth_floor_config_status") != "ratified":
        issues.append(
            _issue(
                "layer2_s14_breadth_floor_status_invalid",
                "S14 breadth floor config must be ratified.",
            )
        )
    for field in (
        "baseline_comparison_status",
        "grounded_authority_coverage_status",
        "evaluation_status_composition_status",
        "envelope_revision_dynamics_status",
        "mechanism_generality_status",
    ):
        if s14.get(field) != "pass":
            issues.append(
                _issue(
                    f"layer2_s14_{field}_invalid",
                    f"S14 {field} must be pass.",
                )
            )
    if s14.get("axis_scorecard_row_count") != 27:
        issues.append(
            _issue(
                "layer2_s14_axis_scorecard_row_count_invalid",
                "S14 axis scorecard must cover all 27 cluster-axis rows.",
            )
        )
    if s14.get("skeptic_defeater_count") != 6:
        issues.append(
            _issue(
                "layer2_s14_skeptic_defeater_count_invalid",
                "S14 must evaluate all six skeptic defeaters.",
            )
        )
    if (
        s14.get("universal_claim_gate_status") != "pass"
        or s14.get("universal_claim_gate_scope") != "declared_operation_envelope"
    ):
        issues.append(
            _issue(
                "layer2_s14_universal_claim_gate_status_invalid",
                "S14 gate must pass only for the declared operation envelope.",
            )
        )

    if s14.get("skeptic_defeater_mapping") != S14_SKEPTIC_DEFEATER_MAPPING:
        issues.append(
            _issue(
                "layer2_s14_skeptic_defeater_mapping_invalid",
                "S14 skeptic-defeater mapping must match the architecture attacks.",
            )
        )
    if not set(s14.get("firewalls", [])) >= S14_REQUIRED_FIREWALLS:
        issues.append(
            _issue(
                "layer2_s14_firewalls_incomplete",
                "S14 firewalls must cover sealed integrity, breadth, grounding, baselines, and authority.",
            )
        )
    if not set(s14.get("substrate_reuse_refs", [])) >= S14_REQUIRED_SUBSTRATE_REUSE_REFS:
        issues.append(
            _issue(
                "layer2_s14_substrate_reuse_refs_missing",
                "S14 must register the reused CAE, ratchet, S12, S13, status, and approval substrates.",
            )
        )
    if set(s14.get("authority_scope", [])) != S14_REQUIRED_AUTHORITY_SCOPE:
        issues.append(
            _issue(
                "layer2_s14_authority_scope_invalid",
                "S14 authority_scope must match the governed universal-claim gate surface.",
            )
        )
    if not set(s14.get("may_not_use_for", [])) >= S14_REQUIRED_DENY:
        issues.append(
            _issue(
                "layer2_s14_authority_deny_list_incomplete",
                "S14 may_not_use_for must block production, recommendation, value learning, and fixture leakage.",
            )
        )
    boundary = s14.get("authority_boundary", {})
    if not isinstance(boundary, dict) or (
        set(boundary.get("authoritative_for", [])) != S14_REQUIRED_AUTHORITY_SCOPE
        or not set(boundary.get("may_not_use_for", [])) >= S14_REQUIRED_DENY
    ):
        issues.append(
            _issue(
                "layer2_s14_authority_boundary_invalid",
                "S14 authority_boundary must mirror manifest authority and deny lists.",
            )
        )
    forbidden_authority = {
        "production_authority",
        "production_rollout_authority",
        "production_recommendation",
        "recommendation_authority",
        "publication_authority",
        "approval_authority",
        "claim_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
        "preference_learning",
        "preference_learning_authority",
        "automated_value_learning",
        "value_choice_authority",
        "aggregate_universal_score",
        "unscoped_universal_claim",
    }
    if set(s14.get("authority_scope", [])) & forbidden_authority:
        issues.append(
            _issue(
                "layer2_s14_forbidden_authority_claimed",
                "S14 authority_scope must not include production, recommendation, preference, value, or unscoped authority.",
            )
        )

    false_clear_counts = s14.get("false_clear_counts", {})
    if (
        not isinstance(false_clear_counts, dict)
        or tuple(false_clear_counts) != S14_FALSE_CLEAR_FIELDS
        or any(value != 0 for value in false_clear_counts.values())
    ):
        issues.append(
            _issue(
                "layer2_s14_false_clear_counts_invalid",
                "S14 false_clear_counts must enumerate all governed fields with zero counts.",
            )
        )
    for field in S14_FALSE_CLEAR_FIELDS:
        if s14.get(f"{field}_false_clear_count") != 0:
            issues.append(
                _issue(
                    f"layer2_s14_{field}_false_clear_count_nonzero",
                    f"S14 {field}_false_clear_count must stay zero.",
                )
            )

    if not set(s14.get("required_grounded_authority_ref_types", [])) >= (
        S14_REQUIRED_GROUNDED_AUTHORITY_REF_TYPES
    ):
        issues.append(
            _issue(
                "layer2_s14_grounded_authority_ref_types_missing",
                "S14 grounded authority must cover A-firewall, evidence, values, mandate, capacity, regime, coupling, and projection refs.",
            )
        )
    if set(s14.get("required_baseline_families", [])) != S14_REQUIRED_BASELINE_FAMILIES:
        issues.append(
            _issue(
                "layer2_s14_baseline_families_invalid",
                "S14 baseline comparison must cover bespoke_tool, raw_llm, and expert_panel.",
            )
        )
    if not set(s14.get("breadth_floor_dimensions", [])) >= S14_BREADTH_FLOOR_DIMENSIONS:
        issues.append(
            _issue(
                "layer2_s14_breadth_floor_dimensions_missing",
                "S14 breadth floor must declare all governed breadth dimensions.",
            )
        )
    if (
        s14.get("s12_growth_thermometer_ref") != "pdc://layer2/s12/s14/growth-thermometer"
        or s14.get("s12_held_out_status") != "pending_s14"
    ):
        issues.append(
            _issue(
                "layer2_s14_mechanism_s12_refs_invalid",
                "S14 mechanism-generality report must reuse S12 growth thermometers with held_out_status=pending_s14.",
            )
        )
    if not s14.get("s12_expansion_evidence_refs") or not s14.get(
        "s13_envelope_revision_refs"
    ) or not s14.get("s13_certified_envelope_delta_refs"):
        issues.append(
            _issue(
                "layer2_s14_envelope_revision_dynamics_refs_missing",
                "S14 envelope dynamics must cite S12 growth and S13 revision/delta refs.",
            )
        )

    for artifact_name, expected_field, expected_value in (
        ("UniversalityAxisScorecard", "row_count", 27),
        ("SkepticDefeaterRecord", "defeater_count", 6),
        ("MechanismGeneralityReport", "s12_held_out_status", "pending_s14"),
        ("UniversalityClaimGateRecord", "status", "pass"),
    ):
        record = artifact_records.get(artifact_name, {})
        if not isinstance(record, dict) or record.get(expected_field) != expected_value:
            issues.append(
                _issue(
                    f"layer2_s14_{artifact_name}_record_invalid",
                    f"S14 {artifact_name} must report {expected_field}={expected_value}.",
                )
            )
    for record_name, expected_field, expected_value in (
        ("D4CorpusTrackCoverage", "track_count", 19),
        ("ExpertOracleBootstrapRecord", "layer_count", 4),
        ("UniversalityBreadthFloorConfig", "dimension_count", 10),
        ("EvaluationStatusCompositionRecord", "case_count", 10),
    ):
        record = supporting_records.get(record_name, {})
        if not isinstance(record, dict) or record.get(expected_field) != expected_value:
            issues.append(
                _issue(
                    f"layer2_s14_{record_name}_support_invalid",
                    f"S14 {record_name} must report {expected_field}={expected_value}.",
                )
            )
    baseline_record = supporting_records.get("UniversalityBaselineComparison", {})
    if not isinstance(baseline_record, dict) or set(
        baseline_record.get("baseline_families", [])
    ) != S14_REQUIRED_BASELINE_FAMILIES:
        issues.append(
            _issue(
                "layer2_s14_baseline_support_invalid",
                "S14 baseline support record must carry all governed baseline families.",
            )
        )
    grounded_record = supporting_records.get("GroundedAuthorityCoverageRecord", {})
    if not isinstance(grounded_record, dict) or not _number_at_least(
        grounded_record.get("ref_type_count"), 8
    ):
        issues.append(
            _issue(
                "layer2_s14_grounded_support_invalid",
                "S14 grounded authority support record must cover at least eight ref types.",
            )
        )
    envelope_record = supporting_records.get("EnvelopeRevisionDynamicsRecord", {})
    if not isinstance(envelope_record, dict) or any(
        envelope_record.get(field, 0) < 1
        for field in (
            "s12_expansion_ref_count",
            "s13_revision_ref_count",
            "s13_certified_delta_ref_count",
        )
    ):
        issues.append(
            _issue(
                "layer2_s14_envelope_support_invalid",
                "S14 envelope support record must include S12 expansion, S13 revision, and S13 certified delta refs.",
            )
        )

    cell = (
        cluster_map_payload.get("cell", {})
        .get("DESIGNER_ITSELF", {})
        .get("evaluation_corpus", {})
    )
    action = str(cell.get("action", "")) if isinstance(cell, dict) else ""
    if (
        not isinstance(cell, dict)
        or cell.get("owner_module") != "src/polisyos/corpus"
        or cell.get("ratchet_state") != "implemented"
        or cell.get("p01_chain") != "implemented"
        or "S14" not in action
        or "sealed battery" not in action
        or "universal-claim gate" not in action
    ):
        issues.append(
            _issue(
                "layer2_s14_cluster_map_evaluation_corpus_invalid",
                "DESIGNER_ITSELF.evaluation_corpus must mention S14 sealed battery universal-claim gate readiness.",
            )
        )
    if "DESIGNER_ITSELF" in cluster_map_payload.get("open_cell_closure", {}):
        issues.append(
            _issue(
                "layer2_s14_cluster_map_reopened_evaluation_corpus",
                "S14 must not reopen DESIGNER_ITSELF cells after burn-down.",
            )
        )

    if _inventory_layer2_artifact_count(inventory) != 22:
        issues.append(
            _issue(
                "layer2_s14_inventory_artifact_count_invalid",
                "Layer 2 inventory artifact count must be 22 after registering S14.",
            )
        )
    inventory_artifact = _inventory_artifact_by_id(inventory, S14_INVENTORY_ID)
    if not inventory_artifact:
        issues.append(
            _issue(
                "layer2_s14_manifest_missing_from_inventory",
                "S14 manifest must be registered in the Policy Design Case inventory.",
            )
        )
        return
    if (
        inventory_artifact.get("path")
        != DEFAULT_S14_UNIVERSALITY_ASSURANCE_MANIFEST_PATH.as_posix()
    ):
        issues.append(
            _issue(
                "layer2_s14_inventory_path_invalid",
                "S14 inventory path must point at the governed manifest.",
            )
        )
    if inventory_artifact.get("kind") != "layer2_s14_universality_assurance_manifest":
        issues.append(
            _issue(
                "layer2_s14_inventory_kind_invalid",
                "S14 inventory entry must carry kind=layer2_s14_universality_assurance_manifest.",
            )
        )
    for field in (
        "schema_version",
        "owner",
        "status",
        "authority_scope",
        "may_not_use_for",
        "validator",
        "canonical_route",
    ):
        if inventory_artifact.get(field) != s14.get(field):
            issues.append(
                _issue(
                    f"layer2_s14_inventory_{field}_mismatch",
                    f"S14 inventory {field} must match the manifest.",
                )
            )
    if inventory_artifact.get("capability_reality_label") != "implemented":
        issues.append(
            _issue(
                "layer2_s14_inventory_status_invalid",
                "S14 inventory entry must carry capability_reality_label=implemented.",
            )
        )
    surfaces = s14.get("surfaces", {})
    if not isinstance(surfaces, dict) or set(surfaces) != {
        "public",
        "expert",
        "machine",
        "reviewer",
        "governance",
    }:
        issues.append(
            _issue(
                "layer2_s14_surfaces_invalid",
                "S14 manifest must register public, expert, machine, reviewer, and governance surfaces.",
            )
        )
    forbidden_payload_keys = {
        "hidden_case_payloads",
        "sealed_case_payloads",
        "private_oracle_notes",
        "case_payloads",
        "expected_labels",
        "label_rows",
    }
    if forbidden_payload_keys & set(s14):
        issues.append(
            _issue(
                "layer2_s14_hidden_payload_embedded",
                "S14 manifest must not embed hidden case payloads, labels, or private oracle notes.",
            )
        )


def _validate_s8_s7_value_authorization_support(
    *,
    s7: object,
    issues: list[dict[str, str]],
) -> None:
    s7_deny = set(s7.get("may_not_use_for", [])) if isinstance(s7, dict) else set()
    if not {"value_choice_authority", "social_weight_selection"} <= s7_deny:
        issues.append(
            _issue(
                "layer2_s8_s7_value_authority_boundary_missing",
                "S7 must continue denying value-choice authority while routing value authorization.",
            )
        )
    try:
        from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
            build_decision_rights_matrix,
            build_governance_decision_class_registry,
        )

        rule_version_ref = "policyos.layer2.s7.delegation.v1"
        classes = build_governance_decision_class_registry(
            "layer2-s8-readiness-probe",
            rule_version_ref,
        )
        class_ids = {row.decision_class_id for row in classes}
        matrix = build_decision_rights_matrix(
            "layer2-s8-readiness-probe",
            classes,
            rule_version_ref,
        )
        row = matrix.row_for_decision_class("value_authorization")
        if (
            "value_authorization" not in class_ids
            or row.required_role != "principal"
            or set(row.five_rights_dimensions)
            != {
                "right_decision",
                "right_person",
                "right_information",
                "right_format_channel",
                "right_time",
            }
        ):
            issues.append(
                _issue(
                    "layer2_s8_s7_value_authorization_support_invalid",
                    "S7 must export value_authorization with a matching five-rights matrix row.",
                )
            )
    except Exception as exc:  # pragma: no cover - defensive diagnostics for CLI users.
        issues.append(
            _issue(
                "layer2_s8_s7_value_authorization_support_invalid",
                f"S7 value_authorization support could not be validated: {exc}",
            )
        )


def _validate_s8_runtime_negative_firewalls(issues: list[dict[str, str]]) -> None:
    try:
        from polisyos.runtime.quality.design_axes.value_choice_provenance import (
            P20_VALUE_SCHEDULE_RESOLVER_ABSENT_CODE,
            P20NormativeChoiceError,
            build_authorized_value_schedule,
            build_pareto_archive,
            build_value_choice_provenance_record,
        )

        rule_version_ref = "policyos.layer2.s8.value_choice.v1"
        authority_boundary = {
            "authoritative_for": ["value_choice_provenance"],
            "may_not_use_for": sorted(S8_REQUIRED_DENY),
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [rule_version_ref],
        }
        authorized_schedule = build_authorized_value_schedule(
            schedule_id="layer2.s8.readiness.authorized",
            schedule_ref="pdc://layer2/s8/readiness/authorized-value-schedule",
            case_id="layer2-s8-readiness-probe",
            mandate_record_ref="pdc://layer2/s6/readiness/mandate",
            s6_mandate_firewall_disposition="pass",
            principal_refs=["principal://readiness"],
            source_class="authorized_governance_schedule",
            review_status="approved",
            effective_at="2026-06-01T00:00:00+00:00",
            social_weight_provenance_refs=["pdc://layer2/s8/readiness/social-weight"],
            authority_boundary=authority_boundary,
            rule_version_ref=rule_version_ref,
            delegation_reference_class="s7_value_authorization_record",
            s7_decision_rights_matrix_ref="pdc://layer2/s7/readiness/matrix",
            s7_value_authorization_request_ref="pdc://layer2/s7/readiness/request",
            s7_value_authorization_record_ref="pdc://layer2/s7/readiness/record",
            s7_value_authorization_decision_class_id="value_authorization",
            s7_five_rights_passed=True,
        )
        if authorized_schedule.disposition != "authorized":
            issues.append(
                _issue(
                    "layer2_s8_authorized_schedule_probe_failed",
                    "S8 must accept S7 value_authorization refs only as mandate-bounded value authorization.",
                )
            )
        try:
            build_pareto_archive(
                archive_id="layer2.s8.readiness.resolver-absent",
                archive_ref="pdc://layer2/s8/readiness/resolver-absent-pareto",
                case_id="layer2-s8-readiness-probe",
                ranking_mode="ranked_with_authorized_values",
                archive_status="probe",
                value_schedule_ref=authorized_schedule.schedule_ref,
                authority_boundary=authority_boundary,
                rule_version_ref=rule_version_ref,
            )
        except P20NormativeChoiceError as exc:
            if exc.code != P20_VALUE_SCHEDULE_RESOLVER_ABSENT_CODE:
                issues.append(
                    _issue(
                        "layer2_s8_value_schedule_resolver_absence_code_mismatch",
                        "S8 ranked admission must name the absent schedule resolver honestly.",
                    )
                )
        else:
            issues.append(
                _issue(
                    "layer2_s8_value_schedule_resolver_absence_firewall_failed",
                    "S8 must refuse ranked admission while no value-schedule resolver exists.",
                )
            )
        try:
            build_value_choice_provenance_record(
                record_id="layer2.s8.readiness.multi_principal",
                record_ref="pdc://layer2/s8/readiness/multi-principal",
                case_id="layer2-s8-readiness-probe",
                selected_alternative_ref="policy://readiness/alternative",
                objective_provenance_ref="pdc://layer2/s8/readiness/objective",
                value_schedule_ref="pdc://layer2/s8/readiness/authorized-schedule",
                pareto_archive_ref="pdc://layer2/s8/readiness/pareto",
                conflict_rows=[{"principal_ref": "principal://readiness"}],
                disposition="authorized",
                integrity_status="pass",
                authority_boundary=authority_boundary,
                rule_version_ref=rule_version_ref,
            )
        except P20NormativeChoiceError:
            pass
        else:
            issues.append(
                _issue(
                    "layer2_s8_multi_principal_negative_control_failed",
                    "S8 must block multi-principal conflicts without arrow disclosures.",
                )
            )
    except Exception as exc:  # pragma: no cover - defensive diagnostics for CLI users.
        issues.append(
            _issue(
                "layer2_s8_runtime_negative_firewall_invalid",
                f"S8 runtime negative firewall probes could not be validated: {exc}",
            )
        )


def _s6_bridge_consumers_from_cluster_map(payload: dict[str, Any]) -> set[str]:
    consumers: set[str] = set()
    for cell_ref in S6_CLOSED_CELLS:
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cell = payload.get("cell", {}).get(cluster, {}).get(axis, {})
        if isinstance(cell, dict):
            consumers.update(str(ref) for ref in cell.get("publishes", []) if ref)
    return consumers


def _coverage_has_all_true(value: object, required: set[str]) -> bool:
    return isinstance(value, dict) and all(value.get(key) is True for key in required)


def _inventory_artifact_by_id(payload: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    for artifact in payload.get("artifacts", []):
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    return {}


def _number_at_least(value: object, minimum: float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value >= minimum


def _non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _floor_by_id(payload: dict[str, Any], floor_id: str) -> dict[str, Any]:
    for floor in payload.get("floor", []):
        if isinstance(floor, dict) and floor.get("floor_id") == floor_id:
            return floor
    return {}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _result(issues: list[dict[str, str]], *, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Layer 2 readiness validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json-output", default="")
    args = parser.parse_args(argv)

    result = validate_layer2_readiness(args.repo_root)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
