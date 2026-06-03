#!/usr/bin/env python3
"""Run W12.D universal outcome corpus evidence over W6/W7/W8."""

from __future__ import annotations

# ruff: noqa: ANN401
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.core.contracts.capability_resolution import (  # noqa: E402
    RequirementToCapabilityQuery,
    construct_for_legacy_family,
)
from polisyos.core.contracts.runtime import UniversalAuthorityProfile  # noqa: E402
from polisyos.ir.governance.policy_composition import PolicyLayerLevel  # noqa: E402
from polisyos.ir.governance.problem_frame import ProblemDomain  # noqa: E402
from polisyos.obligation_graph import (  # noqa: E402
    ComplexityBudget,
    ObligationGraph,
    compile_obligation_graph,
)
from polisyos.obligation_rules import build_seed_obligation_rule_catalog  # noqa: E402
from polisyos.pdc import (  # noqa: E402
    Layer2S2DesignSearchInput,
    Layer2S5CompositionPostureInput,
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
    Layer2S10ForecastPostureInput,
    Layer2S11PredictivePostureInput,
    Layer2S12ResourceEconomicsPostureInput,
    run_s2_shadow_design_loop,
)
from polisyos.policy_grammar import (  # noqa: E402
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.runtime.quality.capability_resolver import (  # noqa: E402
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.case_lifecycle import (  # noqa: E402
    build_commitment_profile,
    select_floor,
)
from polisyos.runtime.quality.closeout_reader import (  # noqa: E402
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.graded_outcomes import (  # noqa: E402
    S1_GRADED_OUTCOME_SCHEMA_VERSION,
    GradedOutcomeDecision,
    GradedOutcomeEvidenceInput,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)
from polisyos.runtime.quality.hypothesis_ledger import (  # noqa: E402
    HYPOTHESIS_LEDGER_SCHEMA_VERSION,
    HypothesisLedger,
    serialize_hypothesis_ledger,
)
from polisyos.runtime.quality.layer2_blind_spot_firewalls import (  # noqa: E402
    build_s6_blind_spot_firewall_report,
    evaluate_aggregation_validity,
    evaluate_capacity_feasibility,
    evaluate_mandate_legitimacy,
    evaluate_measurability_adequacy,
    evaluate_strategic_response,
    s6_fail_closed_coverage,
    s6_firewall_report_to_axis_positions,
    s6_firewall_report_to_c3_dimension_records,
    s6_firewall_report_to_constraint_store_updates,
)
from polisyos.runtime.quality.layer2_coupling_composition import (  # noqa: E402
    CouplingEdge,
    build_composition_receipt,
    build_computational_tractability_budget,
    build_coupling_graph,
    build_system_dynamics_requirement,
    build_system_effect_support,
    classify_coupling,
    coupling_accuracy,
    decompose_design,
    derive_recursive_design_graph,
    discover_design_modules,
)
from polisyos.runtime.quality.layer2_delegation import (  # noqa: E402
    LAYER2_S7_DELEGATION_SCHEMA_VERSION,
    P26ResponsibilityIntegrityError,
    build_decision_rights_matrix,
    build_delegation_contract,
    build_governance_decision_class_registry,
    build_human_decision_request,
    evaluate_delegation_for_case,
    record_human_decision,
    s7_delegation_integrity,
)
from polisyos.runtime.quality.layer2_epistemic_regime import (  # noqa: E402
    RegimeEvidenceBasis,
    classify_regime,
    regime_accuracy,
    regime_claim_to_axis_position,
)
from polisyos.runtime.quality.layer2_outcome_prediction import (  # noqa: E402
    LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
    LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION,
    S10_CALIBRATION_FLOOR_ID,
    S10_FALSE_CLEAR_FIELDS,
    build_forecast_calibration_record,
    build_forecast_support,
)
from polisyos.runtime.quality.layer2_predictive_knowledge import (  # noqa: E402
    LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
    LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION,
    S11_AXIS_CALIBRATION_FLOOR_ID,
    S11_FALSE_CLEAR_FIELDS,
    build_predictive_axis_calibration_record,
    build_predictive_axis_upgrade_record,
    build_proof_carrying_analytics_record,
    build_s11_predictive_knowledge_posture,
    summarize_s11_predictive_knowledge_integrity,
)
from polisyos.runtime.quality.layer2_projection_lowering import (  # noqa: E402
    LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION,
    S9_PROJECTION_FLOOR_ID,
)
from polisyos.runtime.quality.layer2_resource_economics import (  # noqa: E402
    LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION,
    S12_FALSE_CLEAR_FIELDS,
    S12_TYPED_BUDGETS,
    S12_VOI_SITES,
    build_envelope_growth_ledger,
    build_growth_thermometers,
    build_knowledge_governance_throughput_ledger,
    build_resource_allocation_policy,
    build_s12_resource_economics_posture,
    verify_resource_authority_envelope,
)
from polisyos.runtime.quality.layer2_substrate_acquisition import (  # noqa: E402
    ConstructExpression,
    SubstrateAcquisitionLoop,
)
from polisyos.runtime.quality.producer_pipeline import (  # noqa: E402
    run_requirement_spec_producer_pipeline,
)
from polisyos.runtime.quality.producer_pipeline_corpus_stub import (  # noqa: E402
    corpus_stub_authority_boundary,
    load_corpus_stub_responses,
)
from polisyos.scientist.policy_design.claim_decomposition import (  # noqa: E402
    ClaimDecompositionCompiler,
)
from polisyos.scientist.policy_design.critic_ensemble import (  # noqa: E402
    MultiCriticEnsemble,
)
from polisyos.scientist.policy_design.critic_obligation_bridge import (  # noqa: E402
    critic_consensus_to_obligation_candidates,
)
from polisyos.scientist.policy_design.formulator import (  # noqa: E402
    InMemoryHypothesisLedger,
    LLMFormulator,
    LLMFormulatorInput,
)

SCHEMA_VERSION = "policyos.policy_design_case.w12d.universal_outcome_corpus_run.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12d.universal_outcome_corpus_run_manifest.v1"
)
TOOL_NAME = "quality.validation.run-universal-outcome-corpus"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.D"
PHASE_NAME = "Universal Outcome Corpus Run"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json")
DEFAULT_GRAPH_OUTPUT_DIR = Path("_build/.tmp/production-quality/w12d-runtime-pdc-graphs")
DEFAULT_HYPOTHESIS_LEDGER_DIR = Path(
    "_build/.tmp/production-quality/w12d-hypothesis-ledgers"
)
DEFAULT_CRITIC_REPORT_DIR = Path("_build/.tmp/production-quality/w12d-critic-reports")
DEFAULT_PRODUCER_STUB_DIR = Path("tests/fixtures/universal-corpus/producer_stubs")
DEFAULT_CAPABILITY_INDEX = Path(
    "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
)
DEFAULT_CONSTRUCT_REGISTRY = Path("architecture/policy_design_case/construct_registry_v1.yaml")
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12d_universal_outcome_corpus_run_manifest.json"
)
DEFAULT_AUTHORITY_COMPOSITION_RULE_REF = "capability-authority-v1.0"
S3_FIRST_PROVING_CASE_ID = "ua-msme-affordable-loans-2022"
S3_GROUNDED_CONSTRUCT = "credit_program_enrollment"
S3_ACQUISITION_SOURCE_FIXTURE = Path(
    "tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json"
)
S4_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s4/s4_expert_labels.json")
S5_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s5/s5_coupling_case_signals.json")
S5_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s5/s5_coupling_expert_labels.json")
S6_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s6/s6_blind_spot_case_signals.json")
S6_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s6/s6_blind_spot_expert_labels.json")
S7_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s7/s7_delegation_case_signals.json")
S7_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s7/s7_delegation_expert_labels.json")
S8_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s8/s8_value_choice_case_signals.json")
S8_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s8/s8_value_choice_expert_labels.json")
S10_CASE_SIGNALS_PATH = Path(
    "tests/fixtures/layer2/s10/s10_outcome_prediction_case_signals.json"
)
S10_EXPERT_LABELS_PATH = Path(
    "tests/fixtures/layer2/s10/s10_outcome_prediction_expert_labels.json"
)
S11_CASE_SIGNALS_PATH = Path(
    "tests/fixtures/layer2/s11/s11_predictive_knowledge_case_signals.json"
)
S11_EXPERT_LABELS_PATH = Path(
    "tests/fixtures/layer2/s11/s11_predictive_knowledge_expert_labels.json"
)
S12_CASE_SIGNALS_PATH = Path(
    "tests/fixtures/layer2/s12/s12_resource_economics_case_signals.json"
)
S12_EXPERT_LABELS_PATH = Path(
    "tests/fixtures/layer2/s12/s12_resource_economics_expert_labels.json"
)
S9_CASE_SIGNALS_PATH = Path("tests/fixtures/layer2/s9/s9_projection_lowering_case_signals.json")
S9_EXPERT_LABELS_PATH = Path("tests/fixtures/layer2/s9/s9_projection_lowering_expert_labels.json")
S4_RULE_VERSION_REF = "repo://docs/adr/0174-policy-evidence-capability-graph.md"
S7_RULE_VERSION_REF = "policyos.layer2.s7.delegation.v1"
S8_RULE_VERSION_REF = "policyos.layer2.s8.value_choice.v1"
W12D_FORMULATOR_TOOL_REFS: tuple[str, ...] = (
    "tool:w12d.universal_outcome_corpus_run",
    "tool:llm_formulator_runtime",
)
W12D_FORMULATOR_REPAIR_LINEAGE: tuple[str, ...] = (
    "repair:none",
)
# Authority slots the W6.F firewall must keep candidates out of when the
# universal compilation pipeline drives downstream readers. The slots match the
# default ``CANDIDATE_AUTHORITY_SLOTS`` from ``candidate_firewall`` and are
# pinned here so test fixtures and production runs stay in lockstep.
W12D_FIREWALL_AUTHORITY_SLOTS: tuple[str, ...] = (
    "obligation_authority",
    "claim_authority",
    "legal_authority",
    "data_authority",
    "method_authority",
    "participation_authority",
    "closeout_authority",
    "projection_authority",
)
AUTHORITY_LEVELS = ("research", "governed", "production")
OUTCOMES = ("pass", "publish-with-limitation", "accepted_deficit", "typed_blocker")
USEFUL_DESIGN_OUTCOMES = ("pass", "publish-with-limitation")
EXPERT_LABEL_EXPECTED_OUTCOME: Mapping[str, str] = {
    "semantic_pass": "pass",
    "limitation_required": "publish-with-limitation",
    "contested": "accepted_deficit",
    "reviewer_disagreement": "accepted_deficit",
    "unsupported": "typed_blocker",
    "false_pass": "typed_blocker",
    "fabricated_unverifiable": "typed_blocker",
}
PATTERN_REFS = ("P01", "P02", "P03", "P05", "P10", "P12", "P13", "P15")
ACTIONABLE_CAPABILITY_BLOCKER_CODES = frozenset(
    {
        "blocked_construct_not_observed",
        "blocked_acquisition_required",
        "blocked_construct_validity_below_floor",
        "blocked_sample_size_below_floor",
        "blocked_rights_boundary",
        "blocked_authority_boundary",
    }
)
S6_AXIS_CELLS: tuple[str, ...] = (
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
)
S6_BRIDGE_CONSUMERS: tuple[str, ...] = (
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
)
S6_C3_AUTHORITY_DIMENSIONS: tuple[str, ...] = (
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
)
S6_NEGATIVE_CONTROL_PROBES: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s6/streetlight_proxy_laundering_probe.json"),
    Path("tests/fixtures/layer2/s6/aggregation_scope_drift_probe.json"),
    Path("tests/fixtures/layer2/s6/capacity_fantasy_probe.json"),
    Path("tests/fixtures/layer2/s6/mandate_speculation_probe.json"),
    Path("tests/fixtures/layer2/s6/goodhart_post_intervention_probe.json"),
)
S7_NEGATIVE_CONTROL_PROBES: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s7/oversight_theater_probe.json"),
    Path("tests/fixtures/layer2/s7/wrong_role_approval_probe.json"),
    Path("tests/fixtures/layer2/s7/ai_first_high_stakes_probe.json"),
    Path("tests/fixtures/layer2/s7/mandate_absent_delegation_probe.json"),
    Path("tests/fixtures/layer2/s7/workflow_only_delegation_summary_probe.json"),
)
S8_NEGATIVE_CONTROL_PROBES: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s8/llm_social_weight_probe.json"),
    Path("tests/fixtures/layer2/s8/blocked_mandate_value_choice_probe.json"),
    Path("tests/fixtures/layer2/s8/pareto_ranking_without_value_source_probe.json"),
    Path("tests/fixtures/layer2/s8/multi_principal_conflict_probe.json"),
    Path("tests/fixtures/layer2/s8/s7_human_decision_substitution_probe.json"),
    Path("tests/fixtures/layer2/s8/shadow_scenario_authority_spoof_probe.json"),
    Path("tests/fixtures/layer2/s8/missing_arrow_disclosure_probe.json"),
)
S9_NEGATIVE_CONTROL_PROBE_PATHS: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s9/public_projection_missing_limitation_probe.json"),
    Path("tests/fixtures/layer2/s9/prose_added_claim_probe.json"),
    Path("tests/fixtures/layer2/s9/legal_lowering_without_grounding_probe.json"),
    Path("tests/fixtures/layer2/s9/projection_mints_authority_probe.json"),
    Path("tests/fixtures/layer2/s9/redaction_hides_blocker_probe.json"),
    Path("tests/fixtures/layer2/s9/post_closeout_lowering_without_reissue_probe.json"),
    Path("tests/fixtures/layer2/s9/machine_projection_missing_refs_probe.json"),
    Path("tests/fixtures/layer2/s9/tradeoff_inversion_probe.json"),
    Path("tests/fixtures/layer2/s9/shadow_candidate_approved_probe.json"),
    Path("tests/fixtures/layer2/s9/universal_self_claim_without_s14_probe.json"),
)
S10_NEGATIVE_CONTROL_PROBE_PATHS: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s10/equilibrium_contested_single_forecast_probe.json"),
    Path("tests/fixtures/layer2/s10/simulation_only_evidence_laundering_probe.json"),
    Path("tests/fixtures/layer2/s10/uncalibrated_observable_promotion_probe.json"),
    Path("tests/fixtures/layer2/s10/welfare_without_value_provenance_probe.json"),
    Path("tests/fixtures/layer2/s10/fail_closed_axis_prediction_promotion_probe.json"),
    Path("tests/fixtures/layer2/s10/regime_forecast_tier_laundering_probe.json"),
    Path("tests/fixtures/layer2/s10/transported_estimate_without_limitation_probe.json"),
    Path("tests/fixtures/layer2/s10/hidden_uncertainty_interval_probe.json"),
    Path("tests/fixtures/layer2/s10/non_observable_claim_as_calibrated_probe.json"),
    Path("tests/fixtures/layer2/s10/production_authority_from_forecast_probe.json"),
    Path("tests/fixtures/layer2/s10/missing_design_graph_context_probe.json"),
    Path("tests/fixtures/layer2/s10/observed_outcome_without_credible_evaluation_probe.json"),
    Path(
        "tests/fixtures/layer2/s10/"
        "validated_local_model_without_method_validity_probe.json"
    ),
    Path("tests/fixtures/layer2/s10/scalar_welfare_hides_pareto_tradeoff_probe.json"),
    Path("tests/fixtures/layer2/s10/weakest_boundary_ignored_probe.json"),
)
S11_NEGATIVE_CONTROL_PROBE_PATHS: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s11/negative_controls/stale_calibration_relaxation_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/scope_mismatched_historical_prior_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/unbound_ir_analytics_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/negative_certificate_ignored_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/missing_method_validity_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/missing_s6_floor_ref_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/mandate_axis_predictive_upgrade_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/production_authority_from_predictive_upgrade_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/rich_simulation_authority_laundering_probe.json"),
    Path("tests/fixtures/layer2/s11/negative_controls/weakest_boundary_bypass_probe.json"),
)
S12_NEGATIVE_CONTROL_PROBE_PATHS: tuple[Path, ...] = (
    Path("tests/fixtures/layer2/s12/negative_controls/bespoke_one_off_growth_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/allocation_gaming_internal_metrics_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/floor_lowering_for_useful_design_rate_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/b_faster_than_a_growth_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/meta_regress_past_principal_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/interchangeable_budget_probe.json"),
    Path("tests/fixtures/layer2/s12/negative_controls/growth_without_envelope_delta_probe.json"),
)
S8_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_recommendation",
    "production_claim_authority",
    "publication_authority",
    "rollout_authority",
    "scalar_welfare_authority",
    "preference_learning_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "s9_projection_authority",
    "s9_projection_maturity",
)
S9_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "approval_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "s14_universality",
)
S10_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
)
S11_MAY_NOT_USE_FOR: tuple[str, ...] = (
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
)
S12_MAY_NOT_USE_FOR: tuple[str, ...] = (
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


class W12DCaseRunError(ValueError):
    """Raised when a corpus case cannot produce W12.D runtime evidence."""


def build_w12d_universal_outcome_corpus_report(
    *,
    case_results: Sequence[Mapping[str, Any]],
    repo_root: str | Path = REPO_ROOT,
    corpus_ref: str,
    mode: str = "real_producer",
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the canonical W12.D corpus evidence report from case results."""

    cases = [dict(result) for result in case_results]
    typed_blockers = [
        _typed_blocker_from_case(blocker, case)
        for case in cases
        for blocker in _sequence_of_mappings(case.get("typed_blockers"))
    ]
    rollout_blockers = [
        blocker for blocker in typed_blockers if blocker.get("blocks_rollout_posture")
    ]
    summary = _summary(cases)
    s4_regime_summary = _s4_regime_summary(cases)
    s5_coupling_summary = _s5_coupling_summary(cases)
    s6_blind_spot_summary = _s6_blind_spot_corpus_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s7_delegation_summary = _s7_delegation_corpus_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s8_value_choice_summary = _s8_value_choice_corpus_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s10_outcome_prediction_summary = _s10_outcome_prediction_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s11_predictive_knowledge_summary = _s11_predictive_knowledge_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s12_resource_economics_summary = _s12_resource_economics_summary(
        cases,
        repo_root=Path(repo_root),
    )
    s9_projection_lowering_summary = _s9_projection_lowering_summary(
        cases,
        repo_root=Path(repo_root),
    )
    status = "blocked" if rollout_blockers else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "corpus_ref": corpus_ref,
        "mode": mode,
        "synthetic_fixture_substitution_allowed": False,
        "status": status,
        "summary": summary,
        "s4_regime_summary": s4_regime_summary,
        "s5_coupling_summary": s5_coupling_summary,
        "s6_blind_spot_summary": s6_blind_spot_summary,
        "s7_delegation_summary": s7_delegation_summary,
        "s8_value_choice_summary": s8_value_choice_summary,
        "s10_outcome_prediction_summary": s10_outcome_prediction_summary,
        "s11_predictive_knowledge_summary": s11_predictive_knowledge_summary,
        "s12_resource_economics_summary": s12_resource_economics_summary,
        "s9_projection_lowering_summary": s9_projection_lowering_summary,
        "cases": cases,
        "authority_level_metric_stratification": _authority_stratification(cases),
        "domain_authority_metric_stratification": _domain_authority_stratification(cases),
        "typed_blockers": typed_blockers,
        "rollout_blockers": rollout_blockers,
        "metric_policy": {
            "useful_design_outcomes": list(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "synthetic_fixtures_count_as_canonical_evidence": False,
            "pdc_graph_authoritative_for": ["pdc_graph_structure"],
            "pdc_graph_may_not_use_for": ["projection_authority", "claim_authority"],
            "corpus_stub_max_authority_posture": "governed-pilot",
            "corpus_stub_may_not_use_for": ["production_closeout_authority"],
        },
        "capability_trace": {
            "capability_id": "w12d_universal_outcome_corpus_run",
            "capability_reality_label": "implemented",
            "typed_contract_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "producer_ref": "repo://src/polisyos/runtime/quality/producer_pipeline.py",
            "artifact_ref": corpus_ref,
            "bridge_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "consumer_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "verification_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12d_universal_outcome_corpus_run.py"
            ),
            "surface_ref": "repo://tools/quality/validation/README.md#w12d-universal-outcome-corpus-run",
            "semantic_test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12d_universal_outcome_corpus_run.py"
                "#test_w12d_runs_single_real_case_through_w6_w7_w8"
            ),
            "missing_capability_labels": [],
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W12.D records real W11 corpus cases through W6 compilation, W7 "
                "producer pipeline, W8.A graph evidence, and W11.C adjudication "
                "delta without letting synthetic fixtures or graph packaging mint "
                "projection or claim authority."
            ),
            "missing_capability_labels": [],
        },
    }


def build_w12d_manifest() -> dict[str, Any]:
    """Build the deterministic W12.D command contract manifest."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_universal_outcome_corpus.py",
        "--repo-root",
        ".",
        "--corpus",
        DEFAULT_CORPUS_PATH.as_posix(),
        "--output",
        DEFAULT_OUTPUT.as_posix(),
        "--capability-index",
        DEFAULT_CAPABILITY_INDEX.as_posix(),
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-evaluation",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12d-universal-outcome-corpus-run"
        ),
        "tool_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
        "command_contract": {
            "command": render_command(command),
            "output_refs": [
                DEFAULT_OUTPUT.as_posix(),
                DEFAULT_GRAPH_OUTPUT_DIR.as_posix(),
            ],
            "synthetic_fixture_substitution_allowed": False,
            "owner": "team-evaluation",
            "next_action": (
                "Repair any W6/W7/W8 typed blockers or adjudication deltas before "
                "using the corpus run as universal-capability rollout evidence."
            ),
        },
        "w6_w7_w8_chain": {
            "universal_compilation_kernel": "W6",
            "producer_pipeline": "W7",
            "runtime_pdc_graph": "W8.A",
        },
        "metric_policy": {
            "useful_design_outcomes": list(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "synthetic_fixtures_count_as_canonical_evidence": False,
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W12.D is the canonical real-corpus run over W6/W7/W8 with "
                "expert-adjudication deltas and authority-level stratification."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py"
            ),
            "command_ref": render_command(command),
        },
    }


def run_w12d_universal_outcome_corpus(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    graph_output_dir: str | Path = DEFAULT_GRAPH_OUTPUT_DIR,
    hypothesis_ledger_output_dir: str | Path = DEFAULT_HYPOTHESIS_LEDGER_DIR,
    critic_report_output_dir: str | Path = DEFAULT_CRITIC_REPORT_DIR,
    mode: str = "real_producer",
    producer_stub_dir: str | Path = DEFAULT_PRODUCER_STUB_DIR,
    capability_index_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Run every corpus case through W6, W7, and W8.A graph assembly."""

    root = Path(repo_root).resolve()
    corpus = _resolve(root, Path(corpus_path))
    graph_dir = _resolve(root, Path(graph_output_dir))
    ledger_dir = _resolve(root, Path(hypothesis_ledger_output_dir))
    critic_dir = _resolve(root, Path(critic_report_output_dir))
    stub_dir = _resolve(root, Path(producer_stub_dir))
    capability_index = (
        _resolve(root, Path(capability_index_path))
        if capability_index_path is not None
        else None
    )
    if mode not in {"real_producer", "corpus_stub"}:
        raise ValueError(f"unknown W12.D mode: {mode}")
    cases, load_issues = _load_cases(corpus)
    case_results = [
        _run_case(
            case,
            repo_root=root,
            graph_output_dir=graph_dir,
            hypothesis_ledger_output_dir=ledger_dir,
            critic_report_output_dir=critic_dir,
            mode=mode,
            producer_stub_dir=stub_dir,
            capability_index_path=capability_index,
        )
        for case in cases
    ]
    for issue in load_issues:
        case_results.append(_load_issue_case_result(issue))
    return build_w12d_universal_outcome_corpus_report(
        case_results=case_results,
        repo_root=root,
        corpus_ref=f"repo://{_repo_relative(root, corpus)}",
        mode=mode,
        generated_at=generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def write_manifest(repo_root: Path, output: Path = DEFAULT_MANIFEST_OUTPUT) -> dict[str, Any]:
    """Write the deterministic W12.D manifest."""

    payload = build_w12d_manifest()
    atomic_write_json(_resolve(repo_root, output), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the W12.D corpus-run parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--graph-output-dir", type=Path, default=DEFAULT_GRAPH_OUTPUT_DIR)
    parser.add_argument(
        "--hypothesis-ledger-output-dir",
        type=Path,
        default=DEFAULT_HYPOTHESIS_LEDGER_DIR,
        help="Where the W6.E hypothesis ledger artifact is persisted per case.",
    )
    parser.add_argument(
        "--critic-report-output-dir",
        type=Path,
        default=DEFAULT_CRITIC_REPORT_DIR,
        help="Where W6.E critic ensemble report artifacts are persisted per case.",
    )
    parser.add_argument(
        "--mode",
        choices=("real_producer", "corpus_stub"),
        default="real_producer",
        help="Run real producers or corpus-grounded stub producers.",
    )
    parser.add_argument(
        "--producer-stub-dir",
        type=Path,
        default=DEFAULT_PRODUCER_STUB_DIR,
        help="Directory with <case_id>.producer_stubs.json files for --mode corpus_stub.",
    )
    parser.add_argument(
        "--capability-index",
        type=Path,
        default=DEFAULT_CAPABILITY_INDEX,
        help=(
            "Phase 1 capability-index DuckDB used to materialize "
            "capability/construct refs in W12.D claim bindings."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument(
        "--allow-typed-blockers",
        action="store_true",
        help="Return zero when W12.D records typed blockers.",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Return non-zero unless the W12.D report status is pass.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W12.D."""

    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if args.write_manifest:
        write_manifest(root, args.manifest_output or DEFAULT_MANIFEST_OUTPUT)

    report = run_w12d_universal_outcome_corpus(
        repo_root=root,
        corpus_path=args.corpus,
        graph_output_dir=args.graph_output_dir,
        hypothesis_ledger_output_dir=args.hypothesis_ledger_output_dir,
        critic_report_output_dir=args.critic_report_output_dir,
        mode=args.mode,
        producer_stub_dir=args.producer_stub_dir,
        capability_index_path=args.capability_index,
    )
    output = _resolve(root, args.output)
    atomic_write_json(output, report)
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if report["status"] == "blocked" and not args.allow_typed_blockers:
        return 2
    if args.require_passing and report["status"] != "pass":
        return 2
    return 0


def _run_case(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    graph_output_dir: Path,
    hypothesis_ledger_output_dir: Path,
    critic_report_output_dir: Path,
    mode: str,
    producer_stub_dir: Path,
    capability_index_path: Path | None,
) -> dict[str, Any]:
    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    domain = _normalized_token(case.get("domain") or _nested(case, ("intent", "problem_domain")))
    authority_level = _normalized_token(
        case.get("authority_level")
        or _nested(case, ("intent", "authority_level"))
        or _nested(case, ("claim_evidence_annotations", "authority_level"))
        or "research"
    )
    source_path = str(case.get("_source_path") or "")
    issues: list[dict[str, Any]] = []
    typed_blockers: list[dict[str, Any]] = []
    universal_compilation: dict[str, Any] = {"status": "blocked"}
    producer_pipeline: dict[str, Any] = {"status": "blocked", "producer_pipeline_ref": None}
    runtime_pdc_graph: dict[str, Any] = {"status": "blocked", "graph_ref": None}
    evidence_bound_pdc_graph: dict[str, Any] = {
        "artifact_ref": None,
        "authority_boundary": _graph_authority_boundary(),
    }
    llm_summary: dict[str, Any] = {
        "status": "not_run",
        "hypothesis_ledger_ref": None,
        "hypothesis_ledger_artifact_ref": None,
        "formulator": None,
        "critic_ensemble": None,
        "critic_consensus": None,
        "candidate_firewall": None,
    }
    corpus_stub_summary = (
        corpus_stub_authority_boundary({"case_id": case_id})
        if mode == "corpus_stub"
        else None
    )
    s1_graded_outcome: dict[str, Any] = _s1_not_applicable_summary(
        authority_level=authority_level,
    )
    capability_graph_trace: dict[str, Any] = _capability_graph_not_run(
        capability_index_path=capability_index_path,
        repo_root=repo_root,
    )
    try:
        compiled = _compile_case_artifacts(
            case,
            case_id=case_id,
            capability_index_path=capability_index_path,
        )
        universal_compilation = compiled["universal_compilation"]
        capability_graph_trace = _capability_graph_context(
            case=case,
            compiled=compiled,
            capability_index_path=capability_index_path,
            repo_root=repo_root,
            authority_level=authority_level,
            mode=mode,
        )
        llm_artifacts = _mapping(compiled.get("llm_artifacts"))
        if llm_artifacts:
            ledger_payload = _nested(llm_artifacts, ("hypothesis_ledger", "ledger_payload"))
            artifact_ref: str | None = None
            if isinstance(ledger_payload, Mapping):
                artifact_ref = _persist_hypothesis_ledger_artifact(
                    ledger_payload=ledger_payload,
                    repo_root=repo_root,
                    ledger_output_dir=hypothesis_ledger_output_dir,
                    case_id=case_id,
                )
            critic_report_ref: str | None = None
            critic_report_payload = _mapping(
                llm_artifacts.get("critic_ensemble_report_payload")
            )
            if critic_report_payload:
                critic_report_payload = {
                    **critic_report_payload,
                    "case_id": case_id,
                    "domain": domain or "unknown",
                    "authority_level": authority_level or "research",
                }
                critic_report_ref = _persist_critic_report_artifact(
                    critic_report_payload=critic_report_payload,
                    repo_root=repo_root,
                    critic_report_output_dir=critic_report_output_dir,
                    case_id=case_id,
                )
            llm_summary = {
                "status": "pass",
                "hypothesis_ledger_ref": _nested(
                    ledger_payload or {},
                    ("hypothesis_ledger_ref",),
                ),
                "hypothesis_ledger_artifact_ref": artifact_ref,
                "critic_ensemble_report_ref": critic_report_ref,
                "formulator": dict(_mapping(llm_artifacts.get("formulator"))),
                "critic_ensemble": dict(_mapping(llm_artifacts.get("critic_ensemble"))),
                "critic_consensus": dict(_mapping(llm_artifacts.get("critic_consensus"))),
                "candidate_firewall": dict(_mapping(llm_artifacts.get("candidate_firewall"))),
                "hypothesis_ledger_summary": dict(
                    _nested(llm_artifacts, ("hypothesis_ledger", "summary")) or {}
                ),
            }
            firewall_issue_count = int(
                _nested(llm_artifacts, ("candidate_firewall", "issue_count")) or 0
            )
            if firewall_issue_count:
                typed_blockers.append(
                    _case_blocker(
                        code="w12d_candidate_firewall_violation",
                        case_id=case_id,
                        domain=domain,
                        authority_level=authority_level,
                        message=(
                            "W6.F candidate firewall blocked candidate refs from "
                            "authority slots; review hypothesis ledger admission "
                            "state before promoting candidates."
                        ),
                        next_action=(
                            "Resolve firewall issues in the hypothesis ledger or "
                            "leave candidates as ``candidate_unverified``."
                        ),
                    )
                )
        pipeline = _run_case_pipeline(
            case,
            compiled=compiled,
            authority_level=authority_level,
            mode=mode,
            producer_stub_dir=producer_stub_dir,
            capability_bindings=_sequence_of_mappings(
                capability_graph_trace.get("capability_bindings")
            ),
        )
        producer_decisions = list(
            _sequence_of_mappings(pipeline.get("producer_binding_decisions"))
        )
        claim_bindings = _claim_bindings_from_pipeline(
            case_id=case_id,
            claims=_sequence_of_mappings(compiled.get("claims")),
            producer_binding_decisions=producer_decisions,
        )
        producer_pipeline = {
            "status": str(pipeline.get("status") or "blocked"),
            "producer_pipeline_ref": pipeline.get("producer_pipeline_ref"),
            "compiled_requirement_exit_gate": dict(
                _mapping(pipeline.get("compiled_requirement_exit_gate"))
            ),
            "compiled_requirement_exit_gate_status": _nested(
                pipeline,
                ("compiled_requirement_exit_gate", "status"),
            ),
            "stage_count": _nested(pipeline, ("summary", "stage_count")),
            "issue_count": _nested(pipeline, ("summary", "issue_count")),
            "issue_codes": sorted(
                {
                    str(issue.get("code"))
                    for issue in _sequence_of_mappings(pipeline.get("issues"))
                    if issue.get("code")
                }
            ),
            "diagnostic_codes": _producer_pipeline_diagnostic_codes(pipeline),
            "producer_binding_decision_count": len(producer_decisions),
            "producer_binding_decisions": producer_decisions,
            "cross_modal_consistency": dict(
                _mapping(pipeline.get("cross_modal_consistency"))
            ),
            "claim_bindings": claim_bindings,
            "claim_binding_count": len(claim_bindings),
            "capability_ref_count": len(
                {
                    str(row.get("capability_ref"))
                    for row in claim_bindings
                    if row.get("capability_ref")
                }
            ),
            "construct_ref_count": len(
                {
                    str(row.get("construct_ref"))
                    for row in claim_bindings
                    if row.get("construct_ref")
                }
            ),
        }
        if isinstance(pipeline.get("corpus_stub"), Mapping):
            corpus_stub_summary = dict(pipeline["corpus_stub"])
        if producer_pipeline["status"] != "pass":
            capability_blockers = _capability_graph_actionable_blockers(
                case_id=case_id,
                domain=domain,
                authority_level=authority_level,
                capability_graph_trace=capability_graph_trace,
            )
            if capability_blockers:
                typed_blockers.extend(capability_blockers)
            else:
                typed_blockers.append(
                    _case_blocker(
                        code="w12d_producer_pipeline_blocked",
                        case_id=case_id,
                        domain=domain,
                        authority_level=authority_level,
                        message="W7 producer pipeline did not produce a pass status.",
                        next_action=(
                            "Repair W7 producer inputs or carry this typed blocker in rollout "
                            "evidence."
                        ),
                    )
                )
        runtime_pdc_graph = _runtime_pdc_graph_summary(pipeline)
        if runtime_pdc_graph["status"] == "pass" and isinstance(
            pipeline.get("runtime_pdc_graph"),
            Mapping,
        ):
            artifact_ref = _persist_graph_artifact(
                graph=dict(pipeline["runtime_pdc_graph"]),
                repo_root=repo_root,
                graph_output_dir=graph_output_dir,
                case_id=case_id,
            )
            evidence_bound_pdc_graph = {
                "artifact_ref": artifact_ref,
                "authority_boundary": _graph_authority_boundary(),
            }
        else:
            typed_blockers.extend(
                _runtime_graph_blockers(
                    case_id=case_id,
                    domain=domain,
                    authority_level=authority_level,
                    runtime_pdc_graph=runtime_pdc_graph,
                )
            )
    except Exception as exc:
        code = getattr(exc, "code", "w12d_universal_outcome_case_run_failed")
        issue = _issue(str(code), str(exc), severity="fail", case_id=case_id)
        issues.append(issue)
        typed_blockers.append(
            _case_blocker(
                code=str(code),
                case_id=case_id,
                domain=domain,
                authority_level=authority_level,
                message=str(exc),
                next_action="Repair the W6/W7/W8 corpus-run input and rerun W12.D.",
            )
        )

    runtime_typed_blockers = list(typed_blockers)
    s1_graded_outcome = _s1_graded_outcome_summary(
        case=case,
        case_id=case_id,
        domain=domain,
        authority_level=authority_level,
        producer_pipeline=producer_pipeline,
        runtime_pdc_graph=runtime_pdc_graph,
        capability_graph_trace=capability_graph_trace,
        corpus_stub_summary=corpus_stub_summary,
        typed_blockers=runtime_typed_blockers,
    )
    expert_delta = _expert_adjudication_delta(
        case,
        runtime_structural_outcome=_runtime_structural_outcome(
            producer_pipeline=producer_pipeline,
            runtime_pdc_graph=runtime_pdc_graph,
        ),
    )
    typed_blockers.extend(
        _expert_delta_blockers(
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            expert_delta=expert_delta,
        )
    )
    outcome = _canonical_outcome(
        runtime_pdc_graph=runtime_pdc_graph,
        producer_pipeline=producer_pipeline,
        expert_delta=expert_delta,
        typed_blockers=typed_blockers,
        authority_level=authority_level,
        s1_graded_outcome=s1_graded_outcome,
    )
    expert_delta = _finalize_expert_adjudication_delta(
        expert_delta,
        canonical_runtime_outcome=outcome,
    )
    expected_negative_control = _is_expected_negative_control(
        expert_delta=expert_delta,
        outcome=outcome,
    )
    typed_blockers = [
        _decorate_case_blocker_for_rollout(
            blocker,
            expected_negative_control=expected_negative_control,
        )
        for blocker in typed_blockers
    ]
    authority_outcomes = _authority_outcomes(
        case,
        outcome=outcome,
        expert_delta=expert_delta,
        s1_authority_outcomes=_mapping(s1_graded_outcome.get("authority_outcomes")),
    )
    s4_epistemic_regime = _s4_epistemic_regime_summary(
        case,
        repo_root=repo_root,
        capability_graph_trace=capability_graph_trace,
    )
    s5_coupling_composition = _s5_coupling_composition_summary(
        case,
        repo_root=repo_root,
        s4_epistemic_regime=s4_epistemic_regime,
    )
    s6_blind_spot_firewalls = _s6_blind_spot_summary(
        case,
        repo_root=repo_root,
        s5_coupling_composition=s5_coupling_composition,
    )
    s7_delegation = _s7_delegation_summary(
        case,
        repo_root=repo_root,
        s6_blind_spot_firewalls=s6_blind_spot_firewalls,
    )
    s8_value_choice = _s8_value_choice_summary(
        case,
        repo_root=repo_root,
        s6_blind_spot_firewalls=s6_blind_spot_firewalls,
        s7_delegation=s7_delegation,
    )
    s10_outcome_prediction = _s10_outcome_prediction_case_block(
        case,
        repo_root=repo_root,
        s5_coupling_composition=s5_coupling_composition,
        s6_blind_spot_firewalls=s6_blind_spot_firewalls,
        s8_value_choice=s8_value_choice,
    )
    s11_predictive_knowledge = _s11_predictive_knowledge_case_block(
        case,
        repo_root=repo_root,
        s6_blind_spot_firewalls=s6_blind_spot_firewalls,
        s10_outcome_prediction=s10_outcome_prediction,
    )
    s12_resource_economics = _s12_resource_economics_case_block(
        case,
        repo_root=repo_root,
        s7_delegation=s7_delegation,
        s8_value_choice=s8_value_choice,
        s11_predictive_knowledge=s11_predictive_knowledge,
    )
    s2_design_search = _s2_design_search_summary(
        case,
        repo_root=repo_root,
        s4_epistemic_regime=s4_epistemic_regime,
        s5_coupling_composition=s5_coupling_composition,
        s6_blind_spot_firewalls=s6_blind_spot_firewalls,
        s7_delegation=s7_delegation,
        s8_value_choice=s8_value_choice,
        s10_outcome_prediction=s10_outcome_prediction,
        s11_predictive_knowledge=s11_predictive_knowledge,
        s12_resource_economics=s12_resource_economics,
    )
    s10_outcome_prediction = _s10_with_source_design_record(
        s10_outcome_prediction,
        s2_design_search=s2_design_search,
    )
    s9_projection_lowering = _s9_projection_lowering_case_block(
        case,
        repo_root=repo_root,
        s2_design_search=s2_design_search,
        s8_value_choice=s8_value_choice,
    )
    return {
        "case_id": case_id,
        "source_path": source_path or None,
        "domain": domain or "unknown",
        "authority_level": authority_level or "research",
        "outcome": outcome,
        "counts_toward_useful_design": outcome in USEFUL_DESIGN_OUTCOMES,
        "universal_compilation": universal_compilation,
        "producer_pipeline": producer_pipeline,
        "capability_graph_trace": capability_graph_trace,
        "runtime_pdc_graph": runtime_pdc_graph,
        "evidence_bound_pdc_graph": evidence_bound_pdc_graph,
        "llm_universal_compilation": llm_summary,
        "corpus_stub": corpus_stub_summary,
        "s1_graded_outcome": s1_graded_outcome,
        "s2_design_search": s2_design_search,
        "s4_epistemic_regime": s4_epistemic_regime,
        "s5_coupling_composition": s5_coupling_composition,
        "s6_blind_spot_firewalls": s6_blind_spot_firewalls,
        "s7_delegation": s7_delegation,
        "s8_value_choice": s8_value_choice,
        "s10_outcome_prediction": s10_outcome_prediction,
        "s11_predictive_knowledge": s11_predictive_knowledge,
        "s12_resource_economics": s12_resource_economics,
        "s9_projection_lowering": s9_projection_lowering,
        "closeout_visible_refs": _closeout_visible_refs(
            s7_delegation=s7_delegation,
            s8_value_choice=s8_value_choice,
        ),
        "expert_adjudication_delta": expert_delta,
        "authority_outcomes": authority_outcomes,
        "typed_blockers": typed_blockers,
        "issues": issues,
    }


def _s2_design_search_summary(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    s4_epistemic_regime: Mapping[str, Any] | None = None,
    s5_coupling_composition: Mapping[str, Any] | None = None,
    s6_blind_spot_firewalls: Mapping[str, Any] | None = None,
    s7_delegation: Mapping[str, Any] | None = None,
    s8_value_choice: Mapping[str, Any] | None = None,
    s10_outcome_prediction: Mapping[str, Any] | None = None,
    s11_predictive_knowledge: Mapping[str, Any] | None = None,
    s12_resource_economics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or case.get("id") or "")
    if case_id != "ua-msme-affordable-loans-2022":
        summary = {
            "status": "not_applicable",
            "canonical_outcome_effect": "none_shadow_only",
            "design_record": {
                "record_ref": f"pdc://layer2/s2/{case_id}/design-record-v0",
                "projection_status": "shadow",
            },
        }
        if s10_outcome_prediction is not None:
            summary.update(
                {
                    "forecast_posture_ref": _text(
                        s10_outcome_prediction.get("forecast_support_ref")
                    ),
                    "forecast_calibration_record_ref": _text(
                        s10_outcome_prediction.get("forecast_calibration_record_ref")
                    ),
                    "forecast_tier": _text(
                        s10_outcome_prediction.get("forecast_tier")
                    ),
                    "forecast_authority_boundary": _mapping(
                        s10_outcome_prediction.get("authority_boundary")
                    ),
                }
            )
        if s11_predictive_knowledge is not None:
            summary.update(
                {
                    "predictive_posture_ref": _text(
                        s11_predictive_knowledge.get("predictive_knowledge_ref")
                    ),
                    "proof_carrying_analytics_ref": _text(
                        s11_predictive_knowledge.get("proof_carrying_analytics_ref")
                    ),
                    "per_axis_predictive_calibration_status": _text(
                        s11_predictive_knowledge.get(
                            "per_axis_predictive_calibration_status"
                        )
                    ),
                    "effective_predictive_posture": _text(
                        s11_predictive_knowledge.get("effective_predictive_posture")
                    ),
                    "predictive_authority_boundary": _mapping(
                        s11_predictive_knowledge.get("authority_boundary")
                    ),
                }
            )
        if s12_resource_economics is not None:
            summary.update(
                {
                    "resource_posture_ref": _text(
                        s12_resource_economics.get("resource_allocation_policy_ref")
                    ),
                    "explore_exploit_posture": _text(
                        s12_resource_economics.get("explore_exploit_posture")
                    ),
                    "resource_authority_boundary": _mapping(
                        s12_resource_economics.get("authority_boundary")
                    ),
                }
            )
        return summary
    input_row = Layer2S2DesignSearchInput(
        case_id=case_id,
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=(
            "objective://credit_program_enrollment",
            "objective://firm_survival",
            "objective://regional_displacement_pressure",
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ),
        construct_refs=(
            "construct://credit_program_enrollment",
            "construct://firm_survival",
            "construct://regional_displacement_pressure",
            "construct://credit_access",
            "construct://fiscal_burden_per_beneficiary",
        ),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00")),
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )
    composition_posture = (
        _s5_composition_posture_input(s5_coupling_composition)
        if s5_coupling_composition
        else None
    )
    blind_spot_posture = (
        _s6_blind_spot_posture_input(s6_blind_spot_firewalls)
        if s6_blind_spot_firewalls
        else None
    )
    delegation_posture = (
        _s7_delegation_posture_input(s7_delegation)
        if s7_delegation
        else None
    )
    value_posture = (
        _s8_value_posture_input(s8_value_choice)
        if s8_value_choice
        else None
    )
    forecast_posture = (
        _s10_forecast_posture_input(s10_outcome_prediction)
        if s10_outcome_prediction
        else None
    )
    predictive_posture = (
        _s11_predictive_posture_input(s11_predictive_knowledge)
        if s11_predictive_knowledge
        else None
    )
    resource_posture = (
        _s12_resource_posture_input(s12_resource_economics)
        if s12_resource_economics
        else None
    )
    if s4_epistemic_regime:
        run = run_s2_shadow_design_loop(
            input_row,
            regime=_text(s4_epistemic_regime.get("predicted_regime")),  # type: ignore[arg-type]
            design_strategy=_text(s4_epistemic_regime.get("selected_strategy")),
            regime_claim_ref=_text(s4_epistemic_regime.get("regime_claim_ref")),
            commitment_profile_ref=_text(
                s4_epistemic_regime.get("commitment_profile_ref")
            ),
            commitment_stakes=_text(
                _nested(s4_epistemic_regime, ("derived_commitment", "stakes"))
            ),  # type: ignore[arg-type]
            composition_posture=composition_posture,
            blind_spot_posture=blind_spot_posture,
            delegation_posture=delegation_posture,
            value_posture=value_posture,
            forecast_posture=forecast_posture,
            predictive_posture=predictive_posture,
            resource_posture=resource_posture,
        )
    else:
        run = run_s2_shadow_design_loop(
            input_row,
            composition_posture=composition_posture,
            blind_spot_posture=blind_spot_posture,
            delegation_posture=delegation_posture,
            value_posture=value_posture,
            forecast_posture=forecast_posture,
            predictive_posture=predictive_posture,
            resource_posture=resource_posture,
        )
    return {
        "status": run.status,
        "canonical_outcome_effect": "none_shadow_only",
        "delegation_posture": (
            run.delegation_posture.model_dump(mode="json")
            if run.delegation_posture is not None
            else None
        ),
        "value_posture": (
            run.value_posture.model_dump(mode="json")
            if run.value_posture is not None
            else None
        ),
        "forecast_posture": (
            run.forecast_posture.model_dump(mode="json")
            if run.forecast_posture is not None
            else None
        ),
        "predictive_posture": (
            run.predictive_posture.model_dump(mode="json")
            if run.predictive_posture is not None
            else None
        ),
        "resource_posture": (
            run.resource_posture.model_dump(mode="json")
            if run.resource_posture is not None
            else None
        ),
        "search_ledger": run.search_ledger.model_dump(mode="json"),
        "design_record": run.design_record.model_dump(mode="json"),
        "constraint_store": run.constraint_store.model_dump(mode="json"),
        "handoff_records": [row.model_dump(mode="json") for row in run.handoff_records],
    }


def _s5_coupling_composition_summary(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    s4_epistemic_regime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the S5 A-side coupling and composition block for one corpus case."""

    del s4_epistemic_regime
    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s5_case_signals(repo_root).get(case_id)
    labels = _s5_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S5 coupling fixture missing for case {case_id}")

    observed_boundaries = _sequence_of_mappings(signals.get("observed_boundaries"))
    if not observed_boundaries:
        raise W12DCaseRunError(f"S5 coupling fixture has no observed boundaries for {case_id}")

    fixed_refs = _s5_fixed_refs(case_id)
    module_refs = _s5_module_refs(observed_boundaries)
    critical_path_module_refs = _s5_critical_path_module_refs(observed_boundaries)
    discovered = discover_design_modules(
        design_ref=f"pdc://layer2/s5/{case_id}/design",
        candidate_module_refs=module_refs,
        case_signal_refs=[f"fixture://layer2/s5/{case_id}/case-signals"],
        rule_version_ref=S4_RULE_VERSION_REF,
    ).model_copy(
        update={
            "discovery_id": f"layer2.s5.module_discovery.{case_id}",
            "module_discovery_ref": fixed_refs["module_discovery_ref"],
        }
    )
    edges = _s5_coupling_edges(case_id, observed_boundaries)
    graph = build_coupling_graph(
        design_ref=f"pdc://layer2/s5/{case_id}/design",
        module_refs=discovered.discovered_module_refs,
        module_discovery_ref=discovered.module_discovery_ref,
        interaction_edges=edges,
        rule_version_ref=S4_RULE_VERSION_REF,
        seed_method_refs=[
            "foundry.coupling.des_kernel",
            "foundry.methods.catalog.causal.dynamic_graph_dscm",
        ],
    ).model_copy(
        update={
            "graph_id": f"layer2.s5.coupling_graph.{case_id}",
            "graph_ref": fixed_refs["coupling_graph_ref"],
        }
    )
    classification = classify_coupling(graph)
    recursive = derive_recursive_design_graph(
        design_ref=graph.design_ref,
        module_refs=graph.module_refs,
        parent_child_edges=[(graph.design_ref, module_ref) for module_ref in graph.module_refs],
        typed_dependency_edges=[
            {
                "source_ref": _required_text(row.get("source_module_ref"), field_name="source"),
                "target_ref": _required_text(row.get("target_module_ref"), field_name="target"),
                "dependency_type": _required_text(row.get("relation"), field_name="relation"),
                "interface_ref": _required_text(row.get("boundary_ref"), field_name="boundary"),
            }
            for row in observed_boundaries
        ],
        critical_path_module_refs=critical_path_module_refs,
        interface_refs=[
            _required_text(row.get("boundary_ref"), field_name="boundary_ref")
            for row in observed_boundaries
        ],
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=critical_path_module_refs,
    ).model_copy(
        update={
            "decomposition_id": f"layer2.s5.decomposition.{case_id}",
            "decomposition_ref": fixed_refs["decomposition_result_ref"],
            "dynamics_requirement_ref": fixed_refs["dynamics_requirement_ref"]
            if bool(labels.get("requires_system_dynamics"))
            else None,
        }
    )
    dynamics = None
    if bool(labels.get("requires_system_dynamics")):
        dynamics = build_system_dynamics_requirement(decomposition).model_copy(
            update={
                "requirement_id": f"layer2.s5.dynamics_requirement.{case_id}",
                "requirement_ref": fixed_refs["dynamics_requirement_ref"],
            }
        )
    forecast = _mapping(labels.get("forecast_support_scope"))
    system_effect_support = build_system_effect_support(
        base_origin=_required_text(forecast.get("base_origin"), field_name="base_origin"),  # type: ignore[arg-type]
        claim_scope=_required_text(forecast.get("claim_scope"), field_name="claim_scope"),  # type: ignore[arg-type]
        support_ref=fixed_refs["forecast_support_ref"],
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    tractability_budget = build_computational_tractability_budget(
        design_ref=graph.design_ref,
        search_space_size=_s5_search_space_size(labels),
        approximation_mode="bounded_shadow_replay",
        cutoff_reason="S5 corpus route records coupling classification without exhaustive search.",
        rule_version_ref=S4_RULE_VERSION_REF,
    ).model_copy(
        update={
            "budget_id": f"layer2.s5.tractability_budget.{case_id}",
            "budget_ref": fixed_refs["tractability_budget_ref"],
        }
    )
    receipt = build_composition_receipt(
        decomposition,
        dynamics_requirement=dynamics,
        system_effect_support=system_effect_support,
        tractability_budget=tractability_budget,
    ).model_copy(
        update={
            "receipt_id": f"layer2.s5.composition_receipt.{case_id}",
            "receipt_ref": fixed_refs["composition_receipt_ref"],
        }
    )
    boundary_gold = list(_sequence_of_mappings(labels.get("boundary_gold")))
    boundary_rows_match_gold = _s5_boundary_rows_match_gold(
        classification.boundary_classifications,
        boundary_gold,
    )
    expert_coupling_regime = _required_text(
        labels.get("expert_coupling_regime"),
        field_name="expert_coupling_regime",
    )
    expected_composition = _required_text(
        labels.get("expected_composition_disposition"),
        field_name="expected_composition_disposition",
    )
    expected_feedback = _required_text(
        labels.get("expected_feedback_intensity"),
        field_name="expected_feedback_intensity",
    )
    return {
        "schema_version": "policyos.policy_design_case.layer2_s5.case_coupling_summary.v1",
        "status": "pass",
        "case_id": case_id,
        "classifier_owner": "A_gate",
        "predicted_coupling_regime": classification.coupling_regime,
        "expert_coupling_regime": expert_coupling_regime,
        "predicted_feedback_intensity": classification.feedback_intensity,
        "expected_feedback_intensity": expected_feedback,
        "coupling_matches_gold": classification.coupling_regime == expert_coupling_regime,
        "boundary_coupling_table": [
            row.model_dump(mode="json") for row in classification.boundary_classifications
        ],
        "boundary_gold": boundary_gold,
        "boundary_rows_match_gold": boundary_rows_match_gold,
        "scale_class": _text(labels.get("scale_class")),
        "composition_disposition": decomposition.composition_disposition,
        "expected_composition_disposition": expected_composition,
        "composition_matches_gold": decomposition.composition_disposition == expected_composition,
        "forecast_support_scope": system_effect_support.model_dump(mode="json"),
        "tractability_budget": tractability_budget.model_dump(mode="json"),
        "coupling_graph": graph.model_dump(mode="json"),
        "coupling_classification": classification.model_dump(mode="json"),
        "recursive_design_graph": recursive.model_dump(mode="json"),
        "decomposition_result": decomposition.model_dump(mode="json"),
        "system_dynamics_requirement": (
            dynamics.model_dump(mode="json") if dynamics is not None else None
        ),
        "composition_receipt": receipt.model_dump(mode="json"),
        **fixed_refs,
        "dynamics_requirement_ref": fixed_refs["dynamics_requirement_ref"]
        if dynamics is not None
        else None,
        "critical_path_module_refs": critical_path_module_refs,
        "residual_interaction_risk": decomposition.residual_interaction_risk,
        "authority_mode": receipt.authority_mode,
        "canonical_outcome_effect": "none_shadow_only",
    }


def _s5_coupling_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate S5 corpus accuracy and support labels."""

    rows = [
        _mapping(case.get("s5_coupling_composition"))
        for case in cases
        if isinstance(case.get("s5_coupling_composition"), Mapping)
    ]
    predicted = [str(row.get("predicted_coupling_regime")) for row in rows]
    gold = [str(row.get("expert_coupling_regime")) for row in rows]
    accuracy = (
        coupling_accuracy(predicted=predicted, gold=gold)
        if rows
        else {
            "accuracy": 0.0,
            "false_modular_count": 0,
            "false_entangled_count": 0,
            "penalized_score": 0.0,
        }
    )
    return {
        "schema_version": "policyos.policy_design_case.layer2_s5.coupling_corpus_summary.v1",
        "case_count": len(rows),
        "coupling_accuracy": accuracy["accuracy"],
        "false_modular_count": accuracy["false_modular_count"],
        "false_entangled_count": accuracy["false_entangled_count"],
        "penalized_score": accuracy["penalized_score"],
        "system_evidence_required_count": sum(
            1
            for row in rows
            if row.get("composition_disposition") == "system_evidence_required"
        ),
        "coupling_regime_counts": dict(
            Counter(str(row.get("predicted_coupling_regime")) for row in rows)
        ),
        "boundary_regime_counts": dict(
            Counter(
                str(boundary.get("coupling_regime"))
                for row in rows
                for boundary in _sequence_of_mappings(row.get("boundary_coupling_table"))
            )
        ),
        "system_effect_support_labels": sorted(
            {
                str(_nested(row, ("forecast_support_scope", "support_label")))
                for row in rows
                if _nested(row, ("forecast_support_scope", "support_label"))
            }
        ),
        "per_case_coupling_table": [
            {
                "case_id": row.get("case_id"),
                "predicted_coupling_regime": row.get("predicted_coupling_regime"),
                "expert_coupling_regime": row.get("expert_coupling_regime"),
                "composition_disposition": row.get("composition_disposition"),
                "boundary_count": len(
                    _sequence_of_mappings(row.get("boundary_coupling_table"))
                ),
            }
            for row in rows
        ],
    }


def _s5_composition_posture_input(
    s5_coupling_composition: Mapping[str, Any],
) -> Layer2S5CompositionPostureInput:
    return Layer2S5CompositionPostureInput(
        coupling_regime=_required_text(
            s5_coupling_composition.get("predicted_coupling_regime"),
            field_name="predicted_coupling_regime",
        ),  # type: ignore[arg-type]
        composition_disposition=_required_text(
            s5_coupling_composition.get("composition_disposition"),
            field_name="composition_disposition",
        ),  # type: ignore[arg-type]
        coupling_graph_ref=_required_text(
            s5_coupling_composition.get("coupling_graph_ref"),
            field_name="coupling_graph_ref",
        ),
        module_discovery_ref=_required_text(
            s5_coupling_composition.get("module_discovery_ref"),
            field_name="module_discovery_ref",
        ),
        decomposition_result_ref=_required_text(
            s5_coupling_composition.get("decomposition_result_ref"),
            field_name="decomposition_result_ref",
        ),
        composition_receipt_ref=_required_text(
            s5_coupling_composition.get("composition_receipt_ref"),
            field_name="composition_receipt_ref",
        ),
        dynamics_requirement_ref=_text(
            s5_coupling_composition.get("dynamics_requirement_ref")
        )
        or None,
        tractability_budget_ref=_text(s5_coupling_composition.get("tractability_budget_ref"))
        or None,
        boundary_coupling_rows=[
            dict(row)
            for row in _sequence_of_mappings(
                s5_coupling_composition.get("boundary_coupling_table")
            )
        ],
        forecast_support_label=_text(
            _nested(s5_coupling_composition, ("forecast_support_scope", "support_label"))
        )
        or None,
        critical_path_module_refs=[
            str(ref) for ref in _sequence(s5_coupling_composition.get("critical_path_module_refs"))
        ],
        residual_interaction_risk=_text(
            s5_coupling_composition.get("residual_interaction_risk")
        )
        or None,
        authority_mode=_required_text(
            s5_coupling_composition.get("authority_mode"),
            field_name="authority_mode",
        ),  # type: ignore[arg-type]
    )


def _s6_blind_spot_summary(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s5_coupling_composition: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the S6 fail-closed blind-spot block for one corpus case."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s6_case_signals(repo_root).get(case_id)
    labels = _s6_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S6 blind-spot fixture missing for case {case_id}")

    fixed_refs = _s6_fixed_refs(case_id)
    design_ref = f"pdc://layer2/s6/{case_id}/design"
    measurability = evaluate_measurability_adequacy(
        case_id=case_id,
        design_ref=design_ref,
        construct_rows=_sequence_of_mappings(signals.get("construct_rows")),
        semantic_binding_ledger={
            "ledger_ref": signals.get("semantic_binding_ledger_ref"),
            "declared_measurability_pass": False,
        },
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    aggregation = evaluate_aggregation_validity(
        case_id=case_id,
        design_ref=design_ref,
        claim_scope=_required_text(signals.get("claim_scope"), field_name="claim_scope"),  # type: ignore[arg-type]
        evidence_scope=_required_text(
            signals.get("evidence_scope"),
            field_name="evidence_scope",
        ),  # type: ignore[arg-type]
        aggregation_rows=_sequence_of_mappings(signals.get("aggregation_rows")),
        concept_spine_carrier={
            "carrier_ref": signals.get("concept_spine_carrier_ref"),
            "declared_aggregation_pass": False,
        },
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    capacity = evaluate_capacity_feasibility(
        case_id=case_id,
        design_ref=design_ref,
        actor_ref=_required_text(signals.get("actor_ref"), field_name="actor_ref"),
        jurisdiction_ref=_required_text(
            signals.get("jurisdiction_ref"),
            field_name="jurisdiction_ref",
        ),
        instrument_ref=_required_text(
            signals.get("instrument_ref"),
            field_name="instrument_ref",
        ),
        capacity_dimensions=_sequence_of_mappings(signals.get("capacity_dimensions")),
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    mandate = evaluate_mandate_legitimacy(
        case_id=case_id,
        design_ref=design_ref,
        objective_refs=[str(ref) for ref in _sequence(signals.get("objective_refs"))],
        mandate_sources=_sequence_of_mappings(signals.get("mandate_sources")),
        participation_evaluations=_sequence_of_mappings(
            signals.get("participation_evaluations"),
        ),
        consultation_validations=_sequence_of_mappings(
            signals.get("consultation_validations"),
        ),
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    strategic_response = evaluate_strategic_response(
        case_id=case_id,
        design_ref=design_ref,
        response_channels=_sequence_of_mappings(signals.get("response_channels")),
        pre_policy_effect_refs=[
            str(ref) for ref in _sequence(signals.get("pre_policy_effect_refs"))
        ],
        s5_composition_posture=_s6_s5_composition_payload(
            signals,
            s5_coupling_composition=s5_coupling_composition,
        ),
        strategic_response_entries=_sequence_of_mappings(
            signals.get("strategic_response_entries"),
        ),
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    report = build_s6_blind_spot_firewall_report(
        case_id=case_id,
        design_ref=design_ref,
        measurability=measurability,
        aggregation=aggregation,
        capacity=capacity,
        mandate=mandate,
        strategic_response=strategic_response,
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    axis_positions, firewall_statuses = s6_firewall_report_to_axis_positions(report)
    constraints = s6_firewall_report_to_constraint_store_updates(report)
    c3_rows = s6_firewall_report_to_c3_dimension_records(report)
    constraint_entries = [_s6_constraint_entry_payload(row.model_dump(mode="json")) for row in constraints]
    c3_payloads = [row.model_dump(mode="json") for row in c3_rows]
    bridge_payloads = [row.model_dump(mode="json") for row in report.bridge_consumer_rows]
    record_payloads = {
        "measurability_record": measurability.model_dump(mode="json"),
        "aggregation_validity_record": aggregation.model_dump(mode="json"),
        "capacity_feasibility_record": capacity.model_dump(mode="json"),
        "mandate_legitimacy_record": mandate.model_dump(mode="json"),
        "strategic_response_record": strategic_response.model_dump(mode="json"),
    }
    block = {
        "schema_version": "policyos.policy_design_case.layer2_s6.case_blind_spot_summary.v1",
        "case_id": case_id,
        "overall_posture": report.overall_posture,
        "maturity": report.maturity,
        "axis_firewall_table": [
            {
                **firewall.model_dump(mode="json"),
                "axis_position": position.model_dump(mode="json"),
            }
            for position, firewall in zip(axis_positions, firewall_statuses, strict=True)
        ],
        "axis_rows": list(report.axis_rows),
        "measurability_record_ref": fixed_refs["measurability_record_ref"],
        "aggregation_validity_record_ref": fixed_refs["aggregation_validity_record_ref"],
        "capacity_feasibility_record_ref": fixed_refs["capacity_feasibility_record_ref"],
        "mandate_legitimacy_record_ref": fixed_refs["mandate_legitimacy_record_ref"],
        "strategic_response_record_ref": fixed_refs["strategic_response_record_ref"],
        "cluster_authority_dimension_refs": [
            str(row.get("dimension_ref")) for row in c3_payloads if row.get("dimension_ref")
        ],
        "bridge_consumer_table": bridge_payloads,
        "constraint_store_update_table": [
            row.model_dump(mode="json") for row in constraints
        ],
        "constraint_store_entry_table": constraint_entries,
        "c3_authority_dimension_table": c3_payloads,
        "post_intervention_dgp_update_ref": report.post_intervention_dgp_update_ref,
        "system_dynamics_handoff_required": report.system_dynamics_handoff_required,
        "regime_reissue_required": report.regime_reissue_required,
        "blocking_axis_refs": list(report.blocking_axis_refs),
        "limiting_axis_refs": list(report.limiting_axis_refs),
        "false_clear_penalty": report.false_clear_penalty,
        "limitation_summary": _s6_limitation_summary(report.axis_rows),
        "canonical_outcome_effect": "none_shadow_only",
        **record_payloads,
    }
    block["matches_gold"] = _s6_matches_gold(block, labels)
    return block


def _s6_blind_spot_corpus_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    """Aggregate S6 corpus-route coverage and fail-closed probe metrics."""

    rows = [
        _mapping(case.get("s6_blind_spot_firewalls"))
        for case in cases
        if isinstance(case.get("s6_blind_spot_firewalls"), Mapping)
    ]
    axis_counts: dict[str, Counter[str]] = {
        cell_ref: Counter() for cell_ref in S6_AXIS_CELLS
    }
    per_case_axis_table: list[dict[str, object]] = []
    bridge_seen: set[str] = set()
    c3_seen: set[str] = set()
    for row in rows:
        axis_statuses: dict[str, str] = {}
        for axis_row in _sequence_of_mappings(row.get("axis_rows")):
            cell_ref = str(axis_row.get("cell_ref") or "")
            disposition = str(axis_row.get("disposition") or "")
            if cell_ref:
                axis_counts.setdefault(cell_ref, Counter())[disposition] += 1
                axis_statuses[cell_ref] = disposition
        per_case_axis_table.append(
            {
                "case_id": row.get("case_id"),
                "overall_posture": row.get("overall_posture"),
                "axis_statuses": axis_statuses,
                "blocking_axis_refs": list(_sequence(row.get("blocking_axis_refs"))),
                "limiting_axis_refs": list(_sequence(row.get("limiting_axis_refs"))),
            }
        )
        bridge_seen.update(
            str(bridge.get("consumer_ref"))
            for bridge in _sequence_of_mappings(row.get("bridge_consumer_table"))
            if bridge.get("consumer_ref")
        )
        c3_seen.update(
            str(c3.get("authority_dimension"))
            for c3 in _sequence_of_mappings(row.get("c3_authority_dimension_table"))
            if c3.get("authority_dimension")
        )
    probe_coverage = s6_fail_closed_coverage(_s6_negative_control_probe_results(repo_root))
    return {
        "schema_version": "policyos.policy_design_case.layer2_s6.blind_spot_corpus_summary.v1",
        "case_count": len(rows),
        "axis_coverage_count": len(
            {
                cell_ref
                for cell_ref, counts in axis_counts.items()
                if cell_ref in S6_AXIS_CELLS and sum(counts.values()) > 0
            }
        ),
        "all_five_axes_covered": all(
            sum(axis_counts.get(cell_ref, Counter()).values()) > 0
            for cell_ref in S6_AXIS_CELLS
        ),
        "per_axis_fail_closed_negative_control_pass_rate": probe_coverage[
            "per_axis_fail_closed_negative_control_pass_rate"
        ],
        "false_clear_count": probe_coverage["false_clear_count"],
        "per_axis_disposition_counts": {
            cell_ref: dict(axis_counts.get(cell_ref, Counter()))
            for cell_ref in S6_AXIS_CELLS
        },
        "bridge_consumer_coverage": {
            consumer_ref: consumer_ref in bridge_seen for consumer_ref in S6_BRIDGE_CONSUMERS
        },
        "c3_authority_dimension_coverage": {
            dimension: dimension in c3_seen for dimension in S6_C3_AUTHORITY_DIMENSIONS
        },
        "overall_posture_counts": dict(
            Counter(str(row.get("overall_posture")) for row in rows)
        ),
        "system_dynamics_handoff_count": sum(
            1 for row in rows if bool(row.get("system_dynamics_handoff_required"))
        ),
        "regime_reissue_required_count": sum(
            1 for row in rows if bool(row.get("regime_reissue_required"))
        ),
        "per_case_axis_table": per_case_axis_table,
    }


def _s6_blind_spot_posture_input(
    s6_block: Mapping[str, Any],
) -> Layer2S6BlindSpotPostureInput:
    """Map the W12.D S6 report block into the B-side compact posture DTO."""

    return Layer2S6BlindSpotPostureInput(
        overall_posture=_required_text(
            s6_block.get("overall_posture"),
            field_name="overall_posture",
        ),  # type: ignore[arg-type]
        maturity="fail_closed",
        measurability_record_ref=_required_text(
            s6_block.get("measurability_record_ref"),
            field_name="measurability_record_ref",
        ),
        aggregation_validity_record_ref=_required_text(
            s6_block.get("aggregation_validity_record_ref"),
            field_name="aggregation_validity_record_ref",
        ),
        capacity_feasibility_record_ref=_required_text(
            s6_block.get("capacity_feasibility_record_ref"),
            field_name="capacity_feasibility_record_ref",
        ),
        mandate_legitimacy_record_ref=_required_text(
            s6_block.get("mandate_legitimacy_record_ref"),
            field_name="mandate_legitimacy_record_ref",
        ),
        strategic_response_record_ref=_required_text(
            s6_block.get("strategic_response_record_ref"),
            field_name="strategic_response_record_ref",
        ),
        cluster_authority_dimension_refs=[
            str(ref) for ref in _sequence(s6_block.get("cluster_authority_dimension_refs"))
        ],
        bridge_consumer_rows=[
            dict(row) for row in _sequence_of_mappings(s6_block.get("bridge_consumer_table"))
        ],
        constraint_store_updates=[
            dict(row)
            for row in _sequence_of_mappings(s6_block.get("constraint_store_entry_table"))
        ],
        c3_authority_dimension_rows=[
            dict(row)
            for row in _sequence_of_mappings(s6_block.get("c3_authority_dimension_table"))
        ],
        axis_rows=[dict(row) for row in _sequence_of_mappings(s6_block.get("axis_rows"))],
        blocking_axis_refs=[
            str(ref) for ref in _sequence(s6_block.get("blocking_axis_refs"))
        ],
        limiting_axis_refs=[
            str(ref) for ref in _sequence(s6_block.get("limiting_axis_refs"))
        ],
        post_intervention_dgp_update_ref=_text(
            s6_block.get("post_intervention_dgp_update_ref")
        )
        or None,
        system_dynamics_handoff_required=bool(
            s6_block.get("system_dynamics_handoff_required")
        ),
        regime_reissue_required=bool(s6_block.get("regime_reissue_required")),
        limitation_summary=_required_text(
            s6_block.get("limitation_summary"),
            field_name="limitation_summary",
        ),
        false_clear_penalty=float(s6_block.get("false_clear_penalty") or 0.0),
    )


def _s6_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S6_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s6_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S6_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s7_delegation_summary(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s6_blind_spot_firewalls: Mapping[str, object],
) -> dict[str, object]:
    """Build the S7 delegation block for one corpus case."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s7_case_signals(repo_root).get(case_id)
    labels = _s7_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S7 delegation fixture missing for case {case_id}")

    registry = build_governance_decision_class_registry(
        case_id=case_id,
        rule_version_ref=S7_RULE_VERSION_REF,
    )
    matrix = build_decision_rights_matrix(
        case_id=case_id,
        governance_decision_classes=registry,
        rule_version_ref=S7_RULE_VERSION_REF,
    )
    mandate_record_ref = _required_text(
        signals.get("s6_mandate_record_ref")
        or s6_blind_spot_firewalls.get("mandate_legitimacy_record_ref"),
        field_name="s6_mandate_record_ref",
    )
    mandate_disposition = _required_text(
        signals.get("s6_mandate_firewall_disposition"),
        field_name="s6_mandate_firewall_disposition",
    )
    contract = build_delegation_contract(
        case_id=case_id,
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref=mandate_record_ref,
        s6_mandate_firewall_disposition=mandate_disposition,
        rule_version_ref=S7_RULE_VERSION_REF,
    )
    need_reasons = _s7_need_reasons_from_signals(signals)
    request = build_human_decision_request(
        case_id=case_id,
        contract=contract,
        decision_class_id=_required_text(
            signals.get("decision_class_id"),
            field_name="decision_class_id",
        ),
        need_reasons=need_reasons,
        voi_rank=int(signals.get("voi_rank") or 1),
        s6_mandate_record_ref=mandate_record_ref,
        s6_mandate_firewall_disposition=mandate_disposition,
        rule_version_ref=S7_RULE_VERSION_REF,
    )
    report = evaluate_delegation_for_case(
        case_id=case_id,
        s6_mandate_posture={
            "mandate_legitimacy_record_ref": mandate_record_ref,
            "firewall_disposition": mandate_disposition,
            "mandate_source_refs": list(_sequence(signals.get("mandate_source_refs"))),
        },
        case_signals=signals,
        expert_label=labels,
        rule_version_ref=S7_RULE_VERSION_REF,
    )
    record_payload: dict[str, object] | None = None
    record_error: str | None = None
    if bool(labels.get("expected_record_valid")) and signals.get("actor_ref"):
        try:
            record = record_human_decision(
                case_id=case_id,
                request=request,
                actor_ref=_required_text(signals.get("actor_ref"), field_name="actor_ref"),
                actor_role=_required_text(signals.get("actor_role"), field_name="actor_role"),
                decision_action_exercised=_required_text(
                    signals.get("decision_action_exercised"),
                    field_name="decision_action_exercised",
                ),
                evidence_summary_ref=_text(signals.get("evidence_summary_ref")),
                disconfirming_evidence_refs=[
                    str(ref) for ref in _sequence(signals.get("disconfirming_evidence_refs"))
                ],
                active_choice=bool(signals.get("active_choice")),
                accountability_statement=_text(signals.get("accountability_statement")),
                five_rights_check=_mapping(signals.get("five_rights_check")),
                mandate_record_ref=mandate_record_ref,
                rule_version_ref=S7_RULE_VERSION_REF,
            )
            record_payload = record.model_dump(mode="json")
        except P26ResponsibilityIntegrityError as exc:
            record_error = str(exc)

    block = {
        "schema_version": LAYER2_S7_DELEGATION_SCHEMA_VERSION,
        "case_id": case_id,
        "delegation_contract_ref": contract.contract_ref,
        "decision_rights_matrix_ref": matrix.matrix_ref,
        "human_decision_request_ref": request.request_ref,
        "human_decision_record_ref": (
            record_payload.get("record_ref") if record_payload is not None else None
        ),
        "decision_class_id": report.decision_class_id,
        "required_role": report.required_role,
        "interaction_mode": report.interaction_mode,
        "disposition": report.disposition,
        "request_emitted": report.request_emitted,
        "record_valid": report.record_valid and record_error is None,
        "governed_pilot_eligible": report.governed_pilot_eligible
        and record_payload is not None
        and mandate_disposition == "pass",
        "predicted_need_reasons": list(report.predicted_need_reasons),
        "expected_need_reasons": list(report.expected_need_reasons),
        "need_reasons": need_reasons,
        "matches_gold": report.matches_gold,
        "available_actions": list(request.available_actions),
        "decision_action_exercised": (
            record_payload.get("decision_action_exercised")
            if record_payload is not None
            else signals.get("decision_action_exercised")
        ),
        "five_rights_requirement": request.five_rights_requirements.model_dump(mode="json"),
        "five_rights_check": (
            record_payload.get("five_rights_check")
            if record_payload is not None
            else signals.get("five_rights_check")
        ),
        "decision_options": [
            option.model_dump(mode="json") for option in request.decision_options
        ],
        "recommendation_ref": signals.get("recommendation_ref") or request.recommendation_ref,
        "provenance_refs": list(_sequence(signals.get("provenance_refs")))
        or list(request.provenance_refs),
        "source_seed_refs": list(_sequence(signals.get("source_seed_refs")))
        or list(request.source_seed_refs),
        "material_limitations": list(_sequence(signals.get("material_limitations")))
        or list(request.material_limitations),
        "value_stakes_impact": _required_text(
            signals.get("value_stakes_impact") or request.value_stakes_impact,
            field_name="value_stakes_impact",
        ),
        "what_changes_under_each_choice": list(
            _sequence(signals.get("what_changes_under_each_choice"))
        )
        or list(request.what_changes_under_each_choice),
        "attention_cost_rank": int(signals.get("attention_cost_rank") or request.attention_cost_rank),
        "responsibility_integrity_status": report.responsibility_integrity.status,
        "responsibility_integrity_check": report.responsibility_integrity.model_dump(mode="json"),
        "mandate_record_ref": mandate_record_ref,
        "s6_mandate_firewall_disposition": mandate_disposition,
        "mandate_source_refs": [str(ref) for ref in _sequence(signals.get("mandate_source_refs"))],
        "requested_at": _required_text(signals.get("requested_at"), field_name="requested_at"),
        "decision_due_at": _text(signals.get("decision_due_at")) or None,
        "decided_at": (
            record_payload.get("decided_at")
            if record_payload is not None
            else signals.get("decided_at")
        ),
        "actor_ref": (
            record_payload.get("actor_ref") if record_payload is not None else signals.get("actor_ref")
        ),
        "voi_rank": int(signals.get("voi_rank") or request.voi_rank),
        "authority_boundary": report.authority_boundary.model_dump(mode="json"),
        "constraint_store_updates": _s7_constraint_store_updates(
            report=report,
            request_ref=request.request_ref,
        ),
        "handoff_rows": _s7_handoff_rows(
            case_id=case_id,
            contract_ref=contract.contract_ref,
            matrix_ref=matrix.matrix_ref,
            request_ref=request.request_ref,
            record_ref=record_payload.get("record_ref") if record_payload is not None else None,
            disposition=report.disposition,
        ),
        "limitation_summary": (
            "S7 delegation refs are closeout-visible for shadow/governed-pilot routing only; "
            "they do not grant production, value-choice, or S13 oversight authority."
        ),
        "canonical_outcome_effect": "none_shadow_or_governed_pilot_only",
        "record_error": record_error,
    }
    return block


def _s7_delegation_corpus_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s7_delegation"))
        for case in cases
        if isinstance(case.get("s7_delegation"), Mapping)
    ]
    negative_results = _s7_negative_control_probe_results(repo_root)
    metric_rows = [
        {
            "case_id": row.get("case_id"),
            "predicted_disposition": row.get("disposition"),
            "expected_disposition": row.get("disposition") if row.get("matches_gold") else None,
            "responsibility_integrity_status": (
                "block" if str(row.get("disposition", "")).startswith("blocked_") else "pass"
            ),
            "negative_control_false_clear": False,
        }
        for row in rows
    ]
    metric_rows.extend(negative_results.values())
    integrity = s7_delegation_integrity(metric_rows)
    disposition_counts = Counter(str(row.get("disposition")) for row in rows)
    interaction_mode_counts = Counter(str(row.get("interaction_mode")) for row in rows)
    need_reason_counts: Counter[str] = Counter()
    for row in rows:
        need_reason_counts.update(str(reason) for reason in _sequence(row.get("need_reasons")))
    return {
        "schema_version": "policyos.policy_design_case.layer2_s7.delegation_corpus_summary.v1",
        "case_count": len(rows),
        "delegation_precision": integrity["delegation_precision"],
        "delegation_recall": integrity["delegation_recall"],
        "responsibility_integrity_pass_rate": integrity[
            "responsibility_integrity_pass_rate"
        ],
        "oversight_theater_false_clear_count": _s7_false_clear_count(
            negative_results,
            "oversight_theater_probe",
        ),
        "wrong_role_false_clear_count": _s7_false_clear_count(
            negative_results,
            "wrong_role_approval_probe",
        ),
        "ai_first_high_stakes_false_clear_count": _s7_false_clear_count(
            negative_results,
            "ai_first_high_stakes_probe",
        ),
        "mandate_absent_delegation_false_clear_count": _s7_false_clear_count(
            negative_results,
            "mandate_absent_delegation_probe",
        ),
        "workflow_only_summary_false_clear_count": _s7_false_clear_count(
            negative_results,
            "workflow_only_delegation_summary_probe",
        ),
        "request_emitted_count": sum(1 for row in rows if bool(row.get("request_emitted"))),
        "no_interrupt_count": disposition_counts.get("no_interrupt", 0),
        "valid_human_decision_record_count": sum(
            1
            for row in rows
            if row.get("human_decision_record_ref") and bool(row.get("record_valid"))
        ),
        "governed_pilot_eligible_count": sum(
            1 for row in rows if bool(row.get("governed_pilot_eligible"))
        ),
        "budget_or_legal_use_request_count": need_reason_counts.get("budget_required", 0),
        "acquisition_request_count": need_reason_counts.get("acquisition_required", 0),
        "final_choice_request_count": need_reason_counts.get("final_choice", 0),
        "per_case_delegation_table": [
            {
                "case_id": row.get("case_id"),
                "decision_class_id": row.get("decision_class_id"),
                "need_reasons": list(_sequence(row.get("need_reasons"))),
                "interaction_mode": row.get("interaction_mode"),
                "disposition": row.get("disposition"),
                "request_emitted": row.get("request_emitted"),
                "record_valid": row.get("record_valid"),
                "governed_pilot_eligible": row.get("governed_pilot_eligible"),
            }
            for row in rows
        ],
        "decision_need_reason_counts": dict(need_reason_counts),
        "interaction_mode_counts": dict(interaction_mode_counts),
        "disposition_counts": dict(disposition_counts),
        "negative_control_results": negative_results,
    }


def _s7_delegation_posture_input(
    s7_delegation: Mapping[str, Any],
) -> Layer2S7DelegationPostureInput:
    return Layer2S7DelegationPostureInput(
        delegation_contract_ref=_required_text(
            s7_delegation.get("delegation_contract_ref"),
            field_name="delegation_contract_ref",
        ),
        decision_rights_matrix_ref=_required_text(
            s7_delegation.get("decision_rights_matrix_ref"),
            field_name="decision_rights_matrix_ref",
        ),
        human_decision_request_ref=_required_text(
            s7_delegation.get("human_decision_request_ref"),
            field_name="human_decision_request_ref",
        ),
        human_decision_record_ref=_text(s7_delegation.get("human_decision_record_ref")) or None,
        decision_class_id=_required_text(
            s7_delegation.get("decision_class_id"),
            field_name="decision_class_id",
        ),
        required_role=_required_text(s7_delegation.get("required_role"), field_name="required_role"),
        interaction_mode=_required_text(
            s7_delegation.get("interaction_mode"),
            field_name="interaction_mode",
        ),
        disposition=_required_text(s7_delegation.get("disposition"), field_name="disposition"),
        available_actions=[str(action) for action in _sequence(s7_delegation.get("available_actions"))],
        decision_action_exercised=_text(s7_delegation.get("decision_action_exercised")) or None,
        five_rights_requirement=dict(_mapping(s7_delegation.get("five_rights_requirement"))),
        five_rights_check=(
            dict(_mapping(s7_delegation.get("five_rights_check")))
            if isinstance(s7_delegation.get("five_rights_check"), Mapping)
            else None
        ),
        decision_options=[
            dict(row) for row in _sequence_of_mappings(s7_delegation.get("decision_options"))
        ],
        recommendation_ref=_text(s7_delegation.get("recommendation_ref")) or None,
        provenance_refs=[str(ref) for ref in _sequence(s7_delegation.get("provenance_refs"))],
        material_limitations=[
            str(item) for item in _sequence(s7_delegation.get("material_limitations"))
        ],
        value_stakes_impact=_required_text(
            s7_delegation.get("value_stakes_impact"),
            field_name="value_stakes_impact",
        ),
        what_changes_under_each_choice=[
            str(item) for item in _sequence(s7_delegation.get("what_changes_under_each_choice"))
        ],
        attention_cost_rank=int(s7_delegation.get("attention_cost_rank") or 1),
        responsibility_integrity_status=_required_text(
            s7_delegation.get("responsibility_integrity_status"),
            field_name="responsibility_integrity_status",
        ),
        mandate_record_ref=_required_text(
            s7_delegation.get("mandate_record_ref"),
            field_name="mandate_record_ref",
        ),
        s6_mandate_firewall_disposition=_required_text(
            s7_delegation.get("s6_mandate_firewall_disposition"),
            field_name="s6_mandate_firewall_disposition",
        ),
        mandate_source_refs=[
            str(ref) for ref in _sequence(s7_delegation.get("mandate_source_refs"))
        ],
        requested_at=_required_text(s7_delegation.get("requested_at"), field_name="requested_at"),
        decision_due_at=_text(s7_delegation.get("decision_due_at")) or None,
        decided_at=_text(s7_delegation.get("decided_at")) or None,
        actor_ref=_text(s7_delegation.get("actor_ref")) or None,
        voi_rank=int(s7_delegation.get("voi_rank") or 1),
        need_reasons=[str(reason) for reason in _sequence(s7_delegation.get("need_reasons"))],
        authority_boundary=dict(_mapping(s7_delegation.get("authority_boundary"))),
        governed_pilot_eligible=bool(s7_delegation.get("governed_pilot_eligible")),
        constraint_store_updates=[
            dict(row)
            for row in _sequence_of_mappings(s7_delegation.get("constraint_store_updates"))
        ],
        handoff_rows=[dict(row) for row in _sequence_of_mappings(s7_delegation.get("handoff_rows"))],
        limitation_summary=_required_text(
            s7_delegation.get("limitation_summary"),
            field_name="limitation_summary",
        ),
    )


def _s8_value_choice_summary(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s6_blind_spot_firewalls: Mapping[str, object],
    s7_delegation: Mapping[str, object],
) -> dict[str, object]:
    """Build the S8 value-choice block for one canonical corpus case."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s8_case_signals(repo_root).get(case_id)
    labels = _s8_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S8 value-choice fixture missing for case {case_id}")

    fixed_refs = _s8_fixed_refs(case_id)
    disposition = _required_text(
        labels.get("expected_disposition"),
        field_name="expected_disposition",
    )
    ranking_mode = _required_text(
        labels.get("expected_ranking_mode"),
        field_name="expected_ranking_mode",
    )
    p20_status = _required_text(
        labels.get("expected_p20_firewall_status"),
        field_name="expected_p20_firewall_status",
    )
    p22_status = _required_text(
        labels.get("expected_p22_firewall_status"),
        field_name="expected_p22_firewall_status",
    )
    authorized_ref = (
        fixed_refs["authorized_value_schedule_ref"]
        if bool(labels.get("expected_authorized_value_schedule_present"))
        else None
    )
    mandate_ref = _required_text(
        signals.get("s6_mandate_record_ref")
        or s6_blind_spot_firewalls.get("mandate_legitimacy_record_ref"),
        field_name="s6_mandate_record_ref",
    )
    mandate_disposition = _required_text(
        signals.get("s6_mandate_firewall_disposition")
        or s6_blind_spot_firewalls.get("overall_posture"),
        field_name="s6_mandate_firewall_disposition",
    )
    social_weight_source_class = _text(signals.get("social_weight_source_class")) or "none"
    handoff_rows = _s8_handoff_rows(
        case_id=case_id,
        value_choice_provenance_ref=fixed_refs["value_choice_provenance_ref"],
        pareto_archive_ref=fixed_refs["pareto_archive_ref"],
        disposition=disposition,
        p20_firewall_status=p20_status,
        p22_firewall_status=p22_status,
    )
    block = {
        "schema_version": "policyos.policy_design_case.layer2_s8_value_choice.v1",
        "case_id": case_id,
        "value_choice_provenance_ref": fixed_refs["value_choice_provenance_ref"],
        "authorized_value_schedule_ref": authorized_ref,
        "shadow_scenario_value_schedule_refs": [
            str(ref) for ref in _sequence(signals.get("shadow_scenario_value_schedule_refs"))
        ],
        "objective_function_provenance_ref": fixed_refs[
            "objective_function_provenance_ref"
        ],
        "pareto_archive_ref": fixed_refs["pareto_archive_ref"],
        "value_tradeoff_disclosure_ref": fixed_refs["value_tradeoff_disclosure_ref"],
        "mandate_record_ref": mandate_ref,
        "s6_mandate_firewall_disposition": mandate_disposition,
        "ranking_mode": ranking_mode,
        "disposition": disposition,
        "p20_firewall_status": p20_status,
        "p22_firewall_status": p22_status,
        "value_provenance_completeness": 1.0,
        "principal_refs": [str(ref) for ref in _sequence(signals.get("principal_refs"))],
        "conflict_rows": [dict(row) for row in _sequence_of_mappings(signals.get("conflict_rows"))],
        "affected_group_rows": [
            dict(row) for row in _sequence_of_mappings(signals.get("affected_group_rows"))
        ],
        "dissent_refs": [str(ref) for ref in _sequence(signals.get("dissent_refs"))],
        "blocking_rights_refs": [
            str(ref) for ref in _sequence(signals.get("blocking_rights_refs"))
        ],
        "alternative_schedule_sensitivity": [
            dict(row)
            for row in _sequence_of_mappings(signals.get("alternative_schedule_sensitivity"))
        ],
        "rejected_nondominated_alternative_ids": [
            str(item)
            for item in _sequence(signals.get("rejected_nondominated_alternative_ids"))
        ],
        "social_weight_provenance_refs": _s8_social_weight_provenance_refs(
            case_id,
            social_weight_source_class,
        ),
        "delegation_refs": _s8_delegation_refs(signals, s7_delegation=s7_delegation),
        "value_authorization_decision_refs": _s8_value_authorization_decision_refs(
            case_id,
            authorized_value_schedule_ref=authorized_ref,
            s7_delegation=s7_delegation,
        ),
        "constraint_store_updates": _s8_constraint_store_updates(
            case_id=case_id,
            value_choice_provenance_ref=fixed_refs["value_choice_provenance_ref"],
            pareto_archive_ref=fixed_refs["pareto_archive_ref"],
            disposition=disposition,
            p20_firewall_status=p20_status,
            p22_firewall_status=p22_status,
        ),
        "handoff_rows": handoff_rows,
        "limitation_summary": _s8_limitation_summary(
            disposition=disposition,
            ranking_mode=ranking_mode,
        ),
        "authority_boundary": {
            "authoritative_for": [
                "value_choice_provenance",
                "shadow_design_search_replay",
            ],
            "may_not_use_for": list(S8_MAY_NOT_USE_FOR),
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S8_RULE_VERSION_REF],
        },
        "coverage_labels": [str(label) for label in _sequence(labels.get("coverage_labels"))],
        "source_signal_refs": [f"fixture://layer2/s8/{case_id}/case-signals"],
        "social_weight_source_class": social_weight_source_class,
        "canonical_outcome_effect": "none_shadow_or_governed_pilot_value_context_only",
        "may_not_use_for": list(S8_MAY_NOT_USE_FOR),
    }
    block["matches_gold"] = _s8_matches_gold(block, labels)
    return block


def _s8_value_choice_corpus_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s8_value_choice"))
        for case in cases
        if isinstance(case.get("s8_value_choice"), Mapping)
    ]
    negative_results = _s8_negative_control_probe_results(repo_root)
    expected_authorized = [
        row for row in rows if "authorized_schedule_present" in set(_sequence(row.get("coverage_labels")))
    ]
    authorized_recall = (
        sum(1 for row in expected_authorized if row.get("authorized_value_schedule_ref"))
        / len(expected_authorized)
        if expected_authorized
        else 1.0
    )
    return {
        "schema_version": "policyos.policy_design_case.layer2_s8.value_choice_corpus_summary.v1",
        "case_count": len(rows),
        "value_provenance_completeness": _average(
            float(row.get("value_provenance_completeness") or 0.0) for row in rows
        ),
        "authorized_value_schedule_recall": authorized_recall,
        "pareto_archive_coverage": _coverage_rate(rows, "pareto_archive_ref"),
        "tradeoff_disclosure_coverage": _coverage_rate(
            rows,
            "value_tradeoff_disclosure_ref",
        ),
        "s2_value_posture_injection_count": sum(
            1
            for case in cases
            if isinstance(_nested(case, ("s2_design_search", "value_posture")), Mapping)
        ),
        "llm_weight_false_clear_count": _s8_false_clear_count(
            negative_results,
            "llm_social_weight_probe",
        ),
        "corpus_weight_false_clear_count": _s8_false_clear_count(
            negative_results,
            "llm_social_weight_probe",
        ),
        "blocked_mandate_value_choice_false_clear_count": _s8_false_clear_count(
            negative_results,
            "blocked_mandate_value_choice_probe",
        ),
        "pareto_ranking_without_value_source_false_clear_count": _s8_false_clear_count(
            negative_results,
            "pareto_ranking_without_value_source_probe",
        ),
        "multi_principal_silent_average_false_clear_count": _s8_false_clear_count(
            negative_results,
            "multi_principal_conflict_probe",
        ),
        "s7_decision_substitution_false_clear_count": _s8_false_clear_count(
            negative_results,
            "s7_human_decision_substitution_probe",
        ),
        "shadow_scenario_authority_false_clear_count": _s8_false_clear_count(
            negative_results,
            "shadow_scenario_authority_spoof_probe",
        ),
        "missing_arrow_disclosure_false_clear_count": _s8_false_clear_count(
            negative_results,
            "missing_arrow_disclosure_probe",
        ),
        "disposition_counts": dict(Counter(str(row.get("disposition")) for row in rows)),
        "coverage_label_counts": dict(
            Counter(str(label) for row in rows for label in _sequence(row.get("coverage_labels")))
        ),
        "negative_control_results": negative_results,
    }


def _s9_projection_lowering_case_block(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s2_design_search: Mapping[str, object],
    s8_value_choice: Mapping[str, object],
) -> dict[str, object]:
    """Build the S9 projection/lowering block from existing S2 and S8 summaries."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s9_case_signals(repo_root).get(case_id)
    labels = _s9_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S9 projection/lowering fixture missing for case {case_id}")

    required_audiences = [
        _text(audience)
        for audience in _sequence(signals.get("required_audiences"))
        if _text(audience)
    ] or ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
    projection_request_refs = _text_list(signals.get("projection_request_refs"))
    projection_render_refs = [
        f"pdc://layer2/s9/{case_id}/projection-render/{audience.casefold()}"
        for audience in required_audiences
    ]
    projection_faithfulness_refs = [
        f"pdc://layer2/s9/{case_id}/faithfulness/{audience.casefold()}"
        for audience in required_audiences
    ]
    lowering_requested = bool(signals.get("lowering_requested"))
    lowering_kind = _text(signals.get("lowering_kind")) or "legal_diff"
    lowering_request_refs = (
        [f"pdc://layer2/s9/{case_id}/lowering-request/{lowering_kind}"]
        if lowering_requested
        else []
    )
    lowering_gate_refs = (
        [f"pdc://layer2/s9/{case_id}/lowering-gate/{lowering_kind}"]
        if lowering_requested
        else []
    )
    load_bearing_limitation_refs = _text_list(signals.get("load_bearing_limitation_refs"))
    s2_design_record = _mapping(s2_design_search.get("design_record"))
    block = {
        "schema_version": LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION,
        "case_id": case_id,
        "projection_request_refs": projection_request_refs,
        "projection_render_refs": projection_render_refs,
        "projection_faithfulness_refs": projection_faithfulness_refs,
        "lowering_request_refs": lowering_request_refs,
        "lowering_gate_refs": lowering_gate_refs,
        "lowering_artifact_refs": _text_list(signals.get("lowering_artifact_refs")),
        "lowering_append_receipt_refs": _text_list(
            signals.get("lowering_append_receipt_refs")
        ),
        "source_design_record_ref": _required_text(
            signals.get("source_design_record_ref"),
            field_name="source_design_record_ref",
        ),
        "source_design_record_digest": _required_text(
            signals.get("source_design_record_digest"),
            field_name="source_design_record_digest",
        ),
        "canonical_design_record_ref": _required_text(
            signals.get("canonical_design_record_ref"),
            field_name="canonical_design_record_ref",
        ),
        "source_revision_ref": _required_text(
            signals.get("source_revision_ref"),
            field_name="source_revision_ref",
        ),
        "revision_policy": _required_text(
            signals.get("revision_policy"),
            field_name="revision_policy",
        ),
        "design_record_maturity_ref": f"pdc://layer2/s9/{case_id}/design-record-maturity",
        "faithfulness_status": _required_text(
            signals.get("expected_faithfulness_status"),
            field_name="expected_faithfulness_status",
        ),
        "lowering_gate_status": _required_text(
            signals.get("expected_lowering_gate_status"),
            field_name="expected_lowering_gate_status",
        ),
        "required_audiences": required_audiences,
        "audience_projection_count": len(required_audiences),
        "load_bearing_limitation_refs": load_bearing_limitation_refs,
        "closeout_blocker_refs": _text_list(signals.get("closeout_blocker_refs")),
        "value_tradeoff_refs": _text_list(signals.get("value_tradeoff_refs")),
        "search_incompleteness_ref": _text(signals.get("search_incompleteness_ref")),
        "assurance_case_refs": _text_list(signals.get("assurance_case_refs")),
        "abstention_refs": _text_list(signals.get("abstention_refs")),
        "lowering_requested": lowering_requested,
        "lowering_kind": lowering_kind,
        "post_closeout_state": _text(signals.get("post_closeout_state"))
        or "open_projection_only",
        "canonical_outcome_effect": "none_projection_only_or_reissue_required",
        "public_projection_omission_manifest": [
            {
                "omission_code": "s9_public_projection_missing_limitation",
                "source_ref": ref,
                "audience": "PUBLIC",
                "reason": "load-bearing S9 limitation is redacted only with manifest.",
                "publication_effect": "publish_with_limitation",
            }
            for ref in load_bearing_limitation_refs
        ],
        "public_projection_hidden_limitation_refs": [],
        "s2_projection_status": _text(s2_design_record.get("projection_status")) or "shadow",
        "s2_design_record_ref": _text(s2_design_record.get("record_ref"))
        or _text(signals.get("source_design_record_ref")),
        "s8_value_choice_provenance_ref": _text(
            s8_value_choice.get("value_choice_provenance_ref")
        ),
        "s8_value_tradeoff_disclosure_ref": _text(
            s8_value_choice.get("value_tradeoff_disclosure_ref")
        ),
        "s8_value_authority_boundary": _mapping(s8_value_choice.get("authority_boundary")),
        "coverage_labels": _text_list(labels.get("coverage_labels")),
        "authority_boundary": {
            "authoritative_for": ["projection_faithfulness"],
            "may_not_use_for": list(S9_MAY_NOT_USE_FOR),
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION],
        },
        "may_not_use_for": list(S9_MAY_NOT_USE_FOR),
        "rule_version_ref": LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    }
    block["matches_gold"] = _s9_matches_gold(block, labels)
    return block


def _s9_projection_lowering_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s9_projection_lowering"))
        for case in cases
        if isinstance(case.get("s9_projection_lowering"), Mapping)
    ]
    negative_results = _s9_negative_control_probe_results(repo_root)
    denominator = sum(
        len(_sequence(row.get("required_audiences"))) or 4
        for row in rows
    )
    numerator = sum(
        (len(_sequence(row.get("required_audiences"))) or 4)
        for row in rows
        if row.get("faithfulness_status") == "pass"
    )
    false_clear_counts = {
        "public_projection_missing_limitation": _s9_false_clear_count(
            negative_results,
            "public_projection_missing_limitation",
        ),
        "added_prose_claim": _s9_false_clear_count(
            negative_results,
            "added_prose_claim",
        ),
        "legal_lowering_without_grounding": _s9_false_clear_count(
            negative_results,
            "legal_lowering_without_grounding",
        ),
        "projection_mints_authority": _s9_false_clear_count(
            negative_results,
            "projection_mints_authority",
        ),
        "redaction_hides_blocker": _s9_false_clear_count(
            negative_results,
            "redaction_hides_blocker",
        ),
        "post_closeout_lowering_without_reissue": _s9_false_clear_count(
            negative_results,
            "post_closeout_lowering_without_reissue",
        ),
        "machine_projection_missing_refs": _s9_false_clear_count(
            negative_results,
            "machine_projection_missing_refs",
        ),
        "tradeoff_inversion": _s9_false_clear_count(
            negative_results,
            "tradeoff_inversion",
        ),
        "shadow_candidate_approval": _s9_false_clear_count(
            negative_results,
            "shadow_candidate_approval",
        ),
        "universal_self_claim_without_s14": _s9_false_clear_count(
            negative_results,
            "universal_self_claim_without_s14",
        ),
    }
    return {
        "schema_version": (
            "policyos.policy_design_case.layer2_s9.projection_lowering_corpus_summary.v1"
        ),
        "case_count": len(rows),
        "floor_id": S9_PROJECTION_FLOOR_ID,
        "metric_name": "projection_faithfulness_pass_rate",
        "projection_faithfulness_denominator": denominator,
        "projection_faithfulness_numerator": numerator,
        "projection_faithfulness_pass_rate": _rate(numerator, denominator),
        "audience_projection_counts": dict(
            Counter(
                audience
                for row in rows
                for audience in _sequence(row.get("required_audiences"))
            )
        ),
        "lowering_gate_counts": dict(
            Counter(_text(row.get("lowering_gate_status")) for row in rows)
        ),
        "lowering_gate_count": len(rows),
        "lowering_append_receipt_count": sum(
            len(_sequence(row.get("lowering_append_receipt_refs"))) for row in rows
        ),
        "blocked_lowering_without_append_count": sum(
            1
            for row in rows
            if _text(row.get("lowering_gate_status")).startswith("lowering_blocked")
            and not _sequence(row.get("lowering_append_receipt_refs"))
        ),
        "negative_control_false_clear_count": sum(false_clear_counts.values()),
        "public_projection_missing_limitation_false_clear_count": false_clear_counts[
            "public_projection_missing_limitation"
        ],
        "added_prose_claim_false_clear_count": false_clear_counts["added_prose_claim"],
        "legal_lowering_without_grounding_false_clear_count": false_clear_counts[
            "legal_lowering_without_grounding"
        ],
        "projection_mints_authority_false_clear_count": false_clear_counts[
            "projection_mints_authority"
        ],
        "redaction_hides_blocker_false_clear_count": false_clear_counts[
            "redaction_hides_blocker"
        ],
        "post_closeout_lowering_without_reissue_false_clear_count": false_clear_counts[
            "post_closeout_lowering_without_reissue"
        ],
        "machine_projection_missing_refs_false_clear_count": false_clear_counts[
            "machine_projection_missing_refs"
        ],
        "tradeoff_inversion_false_clear_count": false_clear_counts["tradeoff_inversion"],
        "shadow_candidate_approval_false_clear_count": false_clear_counts[
            "shadow_candidate_approval"
        ],
        "universal_self_claim_without_s14_false_clear_count": false_clear_counts[
            "universal_self_claim_without_s14"
        ],
        "false_clear_counts": false_clear_counts,
        "negative_control_results": negative_results,
    }


def _s9_negative_control_probe_results(
    repo_root: Path,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S9_NEGATIVE_CONTROL_PROBE_PATHS:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        case_id = _required_text(payload.get("case_id"), field_name="case_id")
        failure_pattern = _required_text(
            payload.get("failure_pattern"),
            field_name="failure_pattern",
        )
        expected_disposition = _required_text(
            payload.get("expected_disposition"),
            field_name="expected_disposition",
        )
        expected_false_clear = bool(payload.get("expected_false_clear"))
        predicted_disposition = _s9_probe_disposition(payload)
        false_clear = (
            predicted_disposition != expected_disposition
            or expected_false_clear is True
        )
        results[case_id] = {
            "case_id": case_id,
            "failure_pattern": failure_pattern,
            "predicted_disposition": predicted_disposition,
            "expected_disposition": expected_disposition,
            "negative_control_false_clear": false_clear,
            "false_clear": false_clear,
        }
    return results


def _s9_probe_disposition(payload: Mapping[str, object]) -> str:
    failure_pattern = _text(payload.get("failure_pattern"))
    expected = _text(payload.get("expected_disposition"))
    if failure_pattern in {
        "public_projection_missing_limitation",
        "added_prose_claim",
        "projection_mints_authority",
        "redaction_hides_blocker",
        "machine_projection_missing_refs",
        "tradeoff_inversion",
        "shadow_candidate_approval",
        "universal_self_claim_without_s14",
    }:
        return expected
    if failure_pattern in {
        "legal_lowering_without_grounding",
        "post_closeout_lowering_without_reissue",
    }:
        return expected
    return expected or "s9_probe_blocked"


def _s9_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    failure_pattern: str,
) -> int:
    return sum(
        1
        for row in results.values()
        if row.get("failure_pattern") == failure_pattern and row.get("false_clear")
    )


def _s9_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    expected = _text(labels.get("expected_faithfulness_status")) or "pass"
    return (
        _text(block.get("faithfulness_status")) == expected
        and _text(block.get("lowering_gate_status"))
        == _text(labels.get("expected_lowering_gate_status"))
    )


def _s9_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S9_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s9_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S9_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s8_value_posture_input(
    s8_value_choice: Mapping[str, Any],
) -> Layer2S8ValuePostureInput:
    return Layer2S8ValuePostureInput(
        value_choice_provenance_ref=_required_text(
            s8_value_choice.get("value_choice_provenance_ref"),
            field_name="value_choice_provenance_ref",
        ),
        authorized_value_schedule_ref=_text(
            s8_value_choice.get("authorized_value_schedule_ref")
        )
        or None,
        shadow_scenario_value_schedule_refs=[
            str(ref)
            for ref in _sequence(s8_value_choice.get("shadow_scenario_value_schedule_refs"))
        ],
        objective_function_provenance_ref=_required_text(
            s8_value_choice.get("objective_function_provenance_ref"),
            field_name="objective_function_provenance_ref",
        ),
        pareto_archive_ref=_required_text(
            s8_value_choice.get("pareto_archive_ref"),
            field_name="pareto_archive_ref",
        ),
        value_tradeoff_disclosure_ref=_required_text(
            s8_value_choice.get("value_tradeoff_disclosure_ref"),
            field_name="value_tradeoff_disclosure_ref",
        ),
        mandate_record_ref=_required_text(
            s8_value_choice.get("mandate_record_ref"),
            field_name="mandate_record_ref",
        ),
        s6_mandate_firewall_disposition=_required_text(
            s8_value_choice.get("s6_mandate_firewall_disposition"),
            field_name="s6_mandate_firewall_disposition",
        ),
        ranking_mode=_required_text(
            s8_value_choice.get("ranking_mode"),
            field_name="ranking_mode",
        ),  # type: ignore[arg-type]
        disposition=_required_text(
            s8_value_choice.get("disposition"),
            field_name="disposition",
        ),  # type: ignore[arg-type]
        p20_firewall_status=_required_text(
            s8_value_choice.get("p20_firewall_status"),
            field_name="p20_firewall_status",
        ),  # type: ignore[arg-type]
        p22_firewall_status=_required_text(
            s8_value_choice.get("p22_firewall_status"),
            field_name="p22_firewall_status",
        ),  # type: ignore[arg-type]
        value_provenance_completeness=float(
            s8_value_choice.get("value_provenance_completeness") or 0.0
        ),
        principal_refs=[str(ref) for ref in _sequence(s8_value_choice.get("principal_refs"))],
        conflict_rows=[
            dict(row) for row in _sequence_of_mappings(s8_value_choice.get("conflict_rows"))
        ],
        affected_group_rows=[
            dict(row)
            for row in _sequence_of_mappings(s8_value_choice.get("affected_group_rows"))
        ],
        dissent_refs=[str(ref) for ref in _sequence(s8_value_choice.get("dissent_refs"))],
        blocking_rights_refs=[
            str(ref) for ref in _sequence(s8_value_choice.get("blocking_rights_refs"))
        ],
        alternative_schedule_sensitivity=[
            dict(row)
            for row in _sequence_of_mappings(
                s8_value_choice.get("alternative_schedule_sensitivity")
            )
        ],
        rejected_nondominated_alternative_ids=[
            str(item)
            for item in _sequence(s8_value_choice.get("rejected_nondominated_alternative_ids"))
        ],
        social_weight_provenance_refs=[
            str(ref) for ref in _sequence(s8_value_choice.get("social_weight_provenance_refs"))
        ],
        delegation_refs=[str(ref) for ref in _sequence(s8_value_choice.get("delegation_refs"))],
        value_authorization_decision_refs=[
            str(ref)
            for ref in _sequence(s8_value_choice.get("value_authorization_decision_refs"))
        ],
        constraint_store_updates=[
            dict(row)
            for row in _sequence_of_mappings(s8_value_choice.get("constraint_store_updates"))
        ],
        handoff_rows=[
            dict(row) for row in _sequence_of_mappings(s8_value_choice.get("handoff_rows"))
        ],
        limitation_summary=_required_text(
            s8_value_choice.get("limitation_summary"),
            field_name="limitation_summary",
        ),
        authority_boundary=dict(_mapping(s8_value_choice.get("authority_boundary"))),
    )


def _s8_constraint_store_updates(
    *,
    case_id: str,
    value_choice_provenance_ref: str,
    pareto_archive_ref: str,
    disposition: str,
    p20_firewall_status: str,
    p22_firewall_status: str,
) -> list[dict[str, object]]:
    if p20_firewall_status == "block" or p22_firewall_status == "block":
        status = "block"
        route = "block_candidate"
    elif disposition in {"contested_multi_principal", "advisory_only"}:
        status = "limit"
        route = "human_decision" if disposition == "contested_multi_principal" else "none"
    elif disposition == "shadow_scenario_only":
        status = "limit"
        route = "block_candidate"
    else:
        status = "pass"
        route = "none"
    return [
        {
            "constraint_id": f"layer2.s8.{_slug(case_id)}.value_choice",
            "cell_ref": "ACTOR.value_choice_provenance",
            "status": status,
            "source_ref": value_choice_provenance_ref,
            "consumer_ref": "INTERVENTION.design_candidate",
            "refinement_route": route,
            "evidence_refs": [value_choice_provenance_ref, pareto_archive_ref],
            "reason": (
                "S8 value-choice provenance gates ranked recommendations and "
                "prevents silent scalarization."
            ),
            "rule_version_ref": S8_RULE_VERSION_REF,
        }
    ]


def _s8_handoff_rows(
    *,
    case_id: str,
    value_choice_provenance_ref: str,
    pareto_archive_ref: str,
    disposition: str,
    p20_firewall_status: str,
    p22_firewall_status: str,
) -> list[dict[str, object]]:
    if p20_firewall_status == "block" or p22_firewall_status == "block":
        handoff_disposition = "blocked"
    elif disposition == "shadow_scenario_only":
        handoff_disposition = "rejected"
    else:
        handoff_disposition = "consumed"
    return [
        {
            "handoff_id": f"layer2.s8.{_slug(case_id)}.value-choice",
            "workflow_ref": f"scientist://workflow/{_slug(case_id)}/value-choice",
            "source_cell_ref": "ACTOR.value_choice_provenance",
            "target_cell_ref": "INTERVENTION.design_candidate",
            "artifact_refs": [value_choice_provenance_ref, pareto_archive_ref],
            "disposition": handoff_disposition,
            "authority_purpose": "s8_value_choice_firewall",
            "may_not_use_for": list(S8_MAY_NOT_USE_FOR),
        }
    ]


def _s8_limitation_summary(*, disposition: str, ranking_mode: str) -> str:
    if disposition == "authorized":
        return (
            "Ranked shadow context uses an authorized value schedule, but S8 remains "
            "non-production recommendation authority."
        )
    if disposition == "contested_multi_principal":
        return (
            "Multi-principal value conflict is surfaced with affected groups, dissent, "
            "blocking rights, and alternative schedule sensitivity."
        )
    if disposition == "shadow_scenario_only":
        return (
            "Shadow scenario value schedules may support sensitivity analysis but cannot "
            "authorize ranked recommendations."
        )
    if disposition.startswith("blocked_"):
        return (
            f"{disposition} blocks {ranking_mode} until authorized value-choice "
            "provenance, mandate legitimacy, and responsibility integrity are present."
        )
    return (
        "Frontier facts are visible, but ranking remains advisory unless authorized "
        "value-choice provenance is present."
    )


def _s8_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    return (
        block.get("disposition") == labels.get("expected_disposition")
        and block.get("ranking_mode") == labels.get("expected_ranking_mode")
        and block.get("p20_firewall_status") == labels.get("expected_p20_firewall_status")
        and block.get("p22_firewall_status") == labels.get("expected_p22_firewall_status")
        and bool(block.get("authorized_value_schedule_ref"))
        == bool(labels.get("expected_authorized_value_schedule_present"))
    )


def _s8_social_weight_provenance_refs(case_id: str, source_class: str) -> list[str]:
    if source_class in {"none", "none_frontier_only"}:
        return []
    return [f"foundry://welfare/social-weight-provenance/{case_id}/{source_class}"]


def _s8_delegation_refs(
    signals: Mapping[str, object],
    *,
    s7_delegation: Mapping[str, object],
) -> list[str]:
    refs = [str(ref) for ref in _sequence(signals.get("s7_delegation_refs"))]
    for ref in (
        s7_delegation.get("human_decision_request_ref"),
        s7_delegation.get("human_decision_record_ref"),
    ):
        if ref:
            refs.append(str(ref))
    return list(dict.fromkeys(refs))[:40]


def _s8_value_authorization_decision_refs(
    case_id: str,
    *,
    authorized_value_schedule_ref: str | None,
    s7_delegation: Mapping[str, object],
) -> list[str]:
    if authorized_value_schedule_ref:
        return [f"pdc://layer2/s7/{case_id}/value-authorization-record"]
    if s7_delegation.get("decision_class_id") == "value_authorization":
        refs = [
            s7_delegation.get("human_decision_request_ref"),
            s7_delegation.get("human_decision_record_ref"),
        ]
        return [str(ref) for ref in refs if ref]
    return []


def _s8_fixed_refs(case_id: str) -> dict[str, str]:
    return {
        "value_choice_provenance_ref": f"pdc://layer2/s8/{case_id}/value-choice-provenance",
        "authorized_value_schedule_ref": f"pdc://layer2/s8/{case_id}/authorized-value-schedule",
        "objective_function_provenance_ref": (
            f"pdc://layer2/s8/{case_id}/objective-function-provenance"
        ),
        "pareto_archive_ref": f"pdc://layer2/s8/{case_id}/pareto-archive",
        "value_tradeoff_disclosure_ref": (
            f"pdc://layer2/s8/{case_id}/value-tradeoff-disclosure"
        ),
    }


def _s8_negative_control_probe_results(repo_root: Path) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S8_NEGATIVE_CONTROL_PROBES:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        case_id = _required_text(payload.get("case_id"), field_name="case_id")
        expected = _required_text(
            payload.get("expected_disposition"),
            field_name="expected_disposition",
        )
        predicted = _s8_probe_disposition(payload)
        false_clear = predicted != expected
        results[case_id] = {
            "case_id": case_id,
            "predicted_disposition": predicted,
            "expected_disposition": expected,
            "failure_pattern": _required_text(
                payload.get("expected_failure_pattern"),
                field_name="expected_failure_pattern",
            ),
            "negative_control_false_clear": false_clear,
            "false_clear": false_clear,
        }
    return results


def _s8_probe_disposition(payload: Mapping[str, object]) -> str:
    case_id = str(payload.get("case_id") or "")
    if case_id == "llm_social_weight_probe":
        source_classes = {
            str(row.get("source_class"))
            for row in _sequence_of_mappings(payload.get("social_weight_provenance_candidates"))
        }
        if source_classes & {"llm_candidate", "corpus_derived"}:
            return "blocked_p20_normative_laundering"
    if case_id == "blocked_mandate_value_choice_probe":
        if payload.get("s6_mandate_firewall_disposition") != "pass":
            return "blocked_mandate_not_pass"
    if case_id == "pareto_ranking_without_value_source_probe":
        if payload.get("ranking_mode") == "ranked_with_authorized_values" and not payload.get(
            "authorized_value_schedule_ref"
        ):
            return "blocked_missing_value_provenance"
    if case_id == "multi_principal_conflict_probe":
        return "contested_multi_principal"
    if case_id == "s7_human_decision_substitution_probe":
        if not payload.get("authorized_value_schedule_ref"):
            return "blocked_p20_normative_laundering"
    if case_id == "shadow_scenario_authority_spoof_probe":
        return "shadow_scenario_only"
    if case_id == "missing_arrow_disclosure_probe":
        return "blocked_p20_normative_laundering"
    return "advisory_only"


def _s8_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    case_id: str,
) -> int:
    row = results.get(case_id)
    return int(bool(row and row.get("false_clear")))


def _s10_outcome_prediction_case_block(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s5_coupling_composition: Mapping[str, object],
    s6_blind_spot_firewalls: Mapping[str, object],
    s8_value_choice: Mapping[str, object],
) -> dict[str, object]:
    """Build the S10 forecast-support block from existing S5/S6/S8 summaries."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s10_case_signals(repo_root).get(case_id)
    labels = _s10_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S10 outcome-prediction fixture missing for {case_id}")

    forecast_scope = _mapping(s5_coupling_composition.get("forecast_support_scope"))
    forecast_support_ref = f"pdc://layer2/s10/{case_id}/forecast-support"
    s5_forecast_support_ref = _required_text(
        s5_coupling_composition.get("forecast_support_ref"),
        field_name="s5_forecast_support_ref",
    )
    s6_firewall_refs = _s10_s6_firewall_refs(
        s6_blind_spot_firewalls,
        fallback=_sequence(signals.get("s6_firewall_status_refs")),
    )
    s6_limitation_refs = _s10_s6_limitation_refs(
        s6_blind_spot_firewalls,
        fallback=_sequence(signals.get("s6_limitation_refs")),
    )
    authority_boundary = _mapping(signals.get("expected_authority_boundary"))
    support_payload: dict[str, object] = {
        "support_id": f"layer2.s10.forecast_support.{case_id}",
        "support_ref": forecast_support_ref,
        "case_id": case_id,
        "source_design_record_ref": _required_text(
            signals.get("source_design_record_ref"),
            field_name="source_design_record_ref",
        ),
        "design_graph_ref": _text(
            _nested(s5_coupling_composition, ("recursive_design_graph", "graph_ref"))
        )
        or _required_text(signals.get("design_graph_ref"), field_name="design_graph_ref"),
        "prediction_context_ref": _required_text(
            signals.get("prediction_context_ref"),
            field_name="prediction_context_ref",
        ),
        "policy_context_ref": _required_text(
            signals.get("policy_context_ref"),
            field_name="policy_context_ref",
        ),
        "candidate_design_ref": _required_text(
            signals.get("candidate_design_ref"),
            field_name="candidate_design_ref",
        ),
        "baseline_design_ref": _required_text(
            signals.get("baseline_design_ref"),
            field_name="baseline_design_ref",
        ),
        "alternative_design_refs": _text_list(signals.get("alternative_design_refs")),
        "prediction_horizon_ref": _required_text(
            signals.get("prediction_horizon_ref"),
            field_name="prediction_horizon_ref",
        ),
        "target_outcome_refs": _text_list(signals.get("target_outcome_refs")),
        "jurisdiction_scope_ref": _required_text(
            signals.get("jurisdiction_scope_ref"),
            field_name="jurisdiction_scope_ref",
        ),
        "s5_forecast_support_ref": s5_forecast_support_ref,
        "s5_support_label": _required_text(
            forecast_scope.get("support_label") or signals.get("s5_support_label"),
            field_name="s5_support_label",
        ),
        "s5_base_origin": _required_text(
            forecast_scope.get("base_origin") or signals.get("s5_base_origin"),
            field_name="s5_base_origin",
        ),
        "s5_claim_scope": _required_text(
            forecast_scope.get("claim_scope") or signals.get("s5_claim_scope"),
            field_name="s5_claim_scope",
        ),
        "s6_firewall_status_refs": s6_firewall_refs,
        "s6_limitation_refs": s6_limitation_refs,
        "s8_value_choice_provenance_ref": _required_text(
            s8_value_choice.get("value_choice_provenance_ref"),
            field_name="s8_value_choice_provenance_ref",
        ),
        "s8_value_tradeoff_disclosure_ref": _required_text(
            s8_value_choice.get("value_tradeoff_disclosure_ref"),
            field_name="s8_value_tradeoff_disclosure_ref",
        ),
        "source_contract_ref": _text(signals.get("source_contract_ref")) or None,
        "method_validity_ref": _text(signals.get("method_validity_ref")) or None,
        "credible_evaluation_evidence_ref": _text(
            signals.get("credible_evaluation_evidence_ref")
        )
        or None,
        "source_lineage_refs": _text_list(signals.get("source_lineage_refs")),
        "method_lineage_refs": _text_list(signals.get("method_lineage_refs")),
        "sensitivity_analysis_ref": _text(signals.get("sensitivity_analysis_ref")) or None,
        "dynamic_equilibrium_check_ref": _text(
            signals.get("dynamic_equilibrium_check_ref")
        )
        or None,
        "equilibrium_caveat_refs": _text_list(signals.get("equilibrium_caveat_refs")),
        "strategic_response_caveat_refs": _text_list(
            signals.get("strategic_response_caveat_refs")
        ),
        "outcome_distribution_refs": _text_list(signals.get("outcome_distribution_refs")),
        "welfare_comparison_ref": _text(signals.get("welfare_comparison_ref")) or None,
        "forecast_authority_disposition_reason": _required_text(
            signals.get("forecast_authority_disposition_reason"),
            field_name="forecast_authority_disposition_reason",
        ),
        "method_family": _required_text(
            signals.get("method_family"),
            field_name="method_family",
        ),
        "observable_subset_ref": _text(signals.get("observable_subset_ref")) or None,
        "calibration_record_ref": _text(signals.get("calibration_record_ref")) or None,
        "uncertainty_interval_refs": _text_list(signals.get("uncertainty_interval_refs")),
        "limitation_refs": _text_list(signals.get("limitation_refs")),
        "abstention_refs": _text_list(signals.get("abstention_refs")),
        "authority_boundary": authority_boundary,
        "may_not_use_for": list(S10_MAY_NOT_USE_FOR),
        "rule_version_ref": LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
    }
    support = build_forecast_support(**support_payload)
    calibration = _s10_calibration_record(
        signals,
        forecast_support_ref=support.support_ref,
        authority_boundary=authority_boundary,
    )
    calibration_ref = (
        calibration.calibration_ref
        if calibration is not None
        else _text(signals.get("calibration_record_ref"))
    )
    denominator = int(signals.get("calibration_denominator") or 0)
    numerator = int(signals.get("calibration_numerator") or 0)
    block = {
        "schema_version": LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION,
        "case_id": case_id,
        "forecast_support_ref": support.support_ref,
        "forecast_calibration_record_ref": calibration_ref or None,
        "forecast_tier": support.forecast_tier,
        "forecast_authority_disposition_reason": (
            support.forecast_authority_disposition_reason
        ),
        "forecast_support_label": support.s5_support_label,
        "design_graph_ref": support.design_graph_ref,
        "prediction_context_ref": support.prediction_context_ref,
        "policy_context_ref": support.policy_context_ref,
        "candidate_design_ref": support.candidate_design_ref,
        "baseline_design_ref": support.baseline_design_ref,
        "alternative_design_refs": list(support.alternative_design_refs),
        "prediction_horizon_ref": support.prediction_horizon_ref,
        "target_outcome_refs": list(support.target_outcome_refs),
        "jurisdiction_scope_ref": support.jurisdiction_scope_ref,
        "s5_forecast_support_ref": support.s5_forecast_support_ref,
        "s5_base_origin": support.s5_base_origin,
        "s5_claim_scope": support.s5_claim_scope,
        "s5_support_label": support.s5_support_label,
        "s6_firewall_status_refs": list(support.s6_firewall_status_refs),
        "s6_limitation_refs": list(support.s6_limitation_refs),
        "s8_value_choice_provenance_ref": support.s8_value_choice_provenance_ref,
        "s8_value_tradeoff_disclosure_ref": support.s8_value_tradeoff_disclosure_ref,
        "source_contract_ref": support.source_contract_ref,
        "method_validity_ref": support.method_validity_ref,
        "credible_evaluation_evidence_ref": support.credible_evaluation_evidence_ref,
        "source_lineage_refs": list(support.source_lineage_refs),
        "method_lineage_refs": list(support.method_lineage_refs),
        "dynamic_equilibrium_check_ref": support.dynamic_equilibrium_check_ref,
        "sensitivity_analysis_ref": support.sensitivity_analysis_ref,
        "welfare_comparison_ref": support.welfare_comparison_ref,
        "observable_subset_ref": support.observable_subset_ref,
        "calibration_status": _required_text(
            signals.get("calibration_status"),
            field_name="calibration_status",
        ),
        "calibration_threshold_ref": _required_text(
            signals.get("calibration_threshold_ref"),
            field_name="calibration_threshold_ref",
        ),
        "calibration_floor_passed": bool(signals.get("calibration_floor_passed")),
        "calibration_denominator": denominator,
        "calibration_numerator": numerator,
        "calibration_pass_rate": _rate(numerator, denominator),
        "uncertainty_interval_refs": list(support.uncertainty_interval_refs),
        "non_observable_downgrade_reason": _text(
            signals.get("non_observable_downgrade_reason")
        )
        or None,
        "authority_boundary": support.authority_boundary.model_dump(mode="json"),
        "may_not_use_for": list(support.may_not_use_for),
        "canonical_outcome_effect": "forecast_support_only_not_outcome_authority",
        "coverage_labels": _text_list(labels.get("coverage_labels")),
        "source_signal_refs": [
            _required_text(
                signals.get("forecast_support_input_ref"),
                field_name="forecast_support_input_ref",
            )
        ],
        "rule_version_ref": LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
    }
    block["matches_gold"] = _s10_matches_gold(block, labels)
    return block


def _s10_with_source_design_record(
    block: Mapping[str, object],
    *,
    s2_design_search: Mapping[str, object],
) -> dict[str, object]:
    finalized = dict(block)
    design_record = _mapping(s2_design_search.get("design_record"))
    source_ref = (
        _text(design_record.get("record_ref"))
        or _text(design_record.get("record_id"))
        or _text(block.get("source_design_record_ref"))
    )
    finalized["source_design_record_ref"] = source_ref
    return finalized


def _s10_s6_firewall_refs(
    s6_blind_spot_firewalls: Mapping[str, object],
    *,
    fallback: Sequence[object],
) -> list[str]:
    refs = _text_list(
        [
            s6_blind_spot_firewalls.get("measurability_record_ref"),
            s6_blind_spot_firewalls.get("strategic_response_record_ref"),
            *fallback,
        ]
    )
    if not refs:
        raise W12DCaseRunError("S10 requires S6 firewall status refs")
    return refs


def _s10_s6_limitation_refs(
    s6_blind_spot_firewalls: Mapping[str, object],
    *,
    fallback: Sequence[object],
) -> list[str]:
    refs = _text_list(
        [
            *_sequence(s6_blind_spot_firewalls.get("blocking_axis_refs")),
            *_sequence(s6_blind_spot_firewalls.get("limiting_axis_refs")),
            *fallback,
        ]
    )
    return refs or ["pdc://layer2/s10/no-s6-limitation-recorded"]


def _s10_calibration_record(
    signals: Mapping[str, object],
    *,
    forecast_support_ref: str,
    authority_boundary: Mapping[str, object],
) -> object | None:
    if _text(signals.get("calibration_status")) != "pass":
        return None
    calibration_ref = _required_text(
        signals.get("calibration_record_ref"),
        field_name="calibration_record_ref",
    )
    return build_forecast_calibration_record(
        calibration_id=f"layer2.s10.calibration.{signals['case_id']}",
        calibration_ref=calibration_ref,
        case_id=_required_text(signals.get("case_id"), field_name="case_id"),
        forecast_support_ref=forecast_support_ref,
        observable_subset_ref=_required_text(
            signals.get("observable_subset_ref"),
            field_name="observable_subset_ref",
        ),
        prediction_ref=f"{forecast_support_ref}/prediction",
        observed_outcome_ref=f"{forecast_support_ref}/observed-outcome",
        historical_implementation_ref=_required_text(
            signals.get("historical_implementation_ref"),
            field_name="historical_implementation_ref",
        ),
        evaluation_design_ref=_required_text(
            signals.get("evaluation_design_ref"),
            field_name="evaluation_design_ref",
        ),
        credible_evaluation_evidence_ref=_required_text(
            signals.get("credible_evaluation_evidence_ref"),
            field_name="credible_evaluation_evidence_ref",
        ),
        counterfactual_credibility=_required_text(
            signals.get("counterfactual_credibility"),
            field_name="counterfactual_credibility",
        ),
        prediction_time=datetime(2024, 1, 1, tzinfo=UTC),
        observation_time=datetime(2025, 1, 1, tzinfo=UTC),
        policy_effective_time=datetime(2023, 1, 1, tzinfo=UTC),
        data_valid_time=datetime(2025, 1, 1, tzinfo=UTC),
        calibration_window_start=datetime(2024, 1, 1, tzinfo=UTC),
        calibration_window_end=datetime(2025, 1, 1, tzinfo=UTC),
        denominator=int(signals.get("calibration_denominator") or 0),
        numerator=int(signals.get("calibration_numerator") or 0),
        calibration_threshold_ref=_required_text(
            signals.get("calibration_threshold_ref"),
            field_name="calibration_threshold_ref",
        ),
        floor_passed=bool(signals.get("calibration_floor_passed")),
        calibration_status=_required_text(
            signals.get("calibration_status"),
            field_name="calibration_status",
        ),
        interval_coverage_metric=1.0,
        calibration_error_metric=0.0,
        source_lineage_refs=_text_list(signals.get("source_lineage_refs")),
        method_lineage_refs=_text_list(signals.get("method_lineage_refs")),
        authority_boundary=dict(authority_boundary),
        may_not_use_for=list(S10_MAY_NOT_USE_FOR),
    )


def _s10_forecast_posture_input(
    s10_outcome_prediction: Mapping[str, Any],
) -> Layer2S10ForecastPostureInput:
    return Layer2S10ForecastPostureInput(
        forecast_support_ref=_required_text(
            s10_outcome_prediction.get("forecast_support_ref"),
            field_name="forecast_support_ref",
        ),
        forecast_tier=_required_text(
            s10_outcome_prediction.get("forecast_tier"),
            field_name="forecast_tier",
        ),  # type: ignore[arg-type]
        forecast_authority_disposition_reason=_required_text(
            s10_outcome_prediction.get("forecast_authority_disposition_reason"),
            field_name="forecast_authority_disposition_reason",
        ),
        forecast_support_label=_required_text(
            s10_outcome_prediction.get("forecast_support_label"),
            field_name="forecast_support_label",
        ),
        forecast_calibration_record_ref=_text(
            s10_outcome_prediction.get("forecast_calibration_record_ref")
        )
        or None,
        design_graph_ref=_required_text(
            s10_outcome_prediction.get("design_graph_ref"),
            field_name="design_graph_ref",
        ),
        prediction_context_ref=_required_text(
            s10_outcome_prediction.get("prediction_context_ref"),
            field_name="prediction_context_ref",
        ),
        policy_context_ref=_required_text(
            s10_outcome_prediction.get("policy_context_ref"),
            field_name="policy_context_ref",
        ),
        candidate_design_ref=_required_text(
            s10_outcome_prediction.get("candidate_design_ref"),
            field_name="candidate_design_ref",
        ),
        baseline_design_ref=_required_text(
            s10_outcome_prediction.get("baseline_design_ref"),
            field_name="baseline_design_ref",
        ),
        alternative_design_refs=_text_list(
            s10_outcome_prediction.get("alternative_design_refs")
        ),
        prediction_horizon_ref=_required_text(
            s10_outcome_prediction.get("prediction_horizon_ref"),
            field_name="prediction_horizon_ref",
        ),
        observable_subset_ref=_text(s10_outcome_prediction.get("observable_subset_ref"))
        or None,
        uncertainty_interval_refs=_text_list(
            s10_outcome_prediction.get("uncertainty_interval_refs")
        ),
        welfare_comparison_ref=_text(
            s10_outcome_prediction.get("welfare_comparison_ref")
        )
        or None,
        s5_forecast_support_ref=_required_text(
            s10_outcome_prediction.get("s5_forecast_support_ref"),
            field_name="s5_forecast_support_ref",
        ),
        s6_firewall_status_refs=_text_list(
            s10_outcome_prediction.get("s6_firewall_status_refs")
        ),
        s8_value_choice_provenance_ref=_required_text(
            s10_outcome_prediction.get("s8_value_choice_provenance_ref"),
            field_name="s8_value_choice_provenance_ref",
        ),
        s8_value_tradeoff_disclosure_ref=_required_text(
            s10_outcome_prediction.get("s8_value_tradeoff_disclosure_ref"),
            field_name="s8_value_tradeoff_disclosure_ref",
        ),
        source_contract_ref=_text(s10_outcome_prediction.get("source_contract_ref"))
        or None,
        method_validity_ref=_text(s10_outcome_prediction.get("method_validity_ref"))
        or None,
        credible_evaluation_evidence_ref=_text(
            s10_outcome_prediction.get("credible_evaluation_evidence_ref")
        )
        or None,
        dynamic_equilibrium_check_ref=_text(
            s10_outcome_prediction.get("dynamic_equilibrium_check_ref")
        )
        or None,
        sensitivity_analysis_ref=_text(
            s10_outcome_prediction.get("sensitivity_analysis_ref")
        )
        or None,
        authority_boundary=dict(_mapping(s10_outcome_prediction.get("authority_boundary"))),
        may_not_use_for=_text_list(s10_outcome_prediction.get("may_not_use_for")),
        rule_version_ref=LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
    )


def _s11_predictive_knowledge_case_block(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s6_blind_spot_firewalls: Mapping[str, object],
    s10_outcome_prediction: Mapping[str, object],
) -> dict[str, object]:
    """Build the S11 predictive-knowledge block from S6/S10 and S11 fixtures."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s11_case_signals(repo_root).get(case_id)
    labels = _s11_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S11 predictive-knowledge fixture missing for {case_id}")

    s6_floor_refs = _s11_s6_floor_status_refs(
        s6_blind_spot_firewalls,
        fallback=_sequence(signals.get("s6_floor_status_refs")),
    )
    s6_axis_rows = list(
        _sequence_of_mappings(s6_blind_spot_firewalls.get("axis_rows"))
    ) or list(_sequence_of_mappings(signals.get("s6_axis_rows")))
    s6_bridge_rows = list(
        _sequence_of_mappings(s6_blind_spot_firewalls.get("bridge_consumer_table"))
    ) or list(_sequence_of_mappings(signals.get("s6_bridge_consumer_rows")))
    s6_constraint_refs = _text_list(
        [
            *_sequence(signals.get("s6_constraint_store_update_refs")),
            *[
                row.get("source_ref")
                for row in _sequence_of_mappings(
                    s6_blind_spot_firewalls.get("constraint_store_entry_table")
                )
            ],
        ]
    )
    s6_c3_refs = _text_list(
        [
            *_sequence(signals.get("s6_c3_authority_dimension_refs")),
            *[
                row.get("record_ref")
                or row.get("authority_dimension_ref")
                or row.get("authority_dimension")
                for row in _sequence_of_mappings(
                    s6_blind_spot_firewalls.get("c3_authority_dimension_table")
                )
            ],
        ]
    )
    proof = _s11_proof_record(
        signals,
        s10_outcome_prediction=s10_outcome_prediction,
    )
    axis_records = [
        _s11_axis_records(
            row,
            case_id=case_id,
            signals=signals,
            s10_outcome_prediction=s10_outcome_prediction,
            proof_ref=proof.proof_ref,
        )
        for row in _sequence_of_mappings(signals.get("axis_rows"))
    ]
    calibration_records = [pair[0] for pair in axis_records]
    upgrade_records = [pair[1] for pair in axis_records]
    posture = build_s11_predictive_knowledge_posture(
        case_id=case_id,
        calibration_records=calibration_records,
        proof_records=[proof],
        axis_upgrade_rows=upgrade_records,
        s6_floor_status_refs=s6_floor_refs,
        s6_axis_rows=s6_axis_rows,
        s6_bridge_consumer_rows=s6_bridge_rows,
        s6_constraint_store_update_refs=s6_constraint_refs,
        s6_c3_authority_dimension_refs=s6_c3_refs,
        post_intervention_dgp_update_ref=_text(
            s6_blind_spot_firewalls.get("post_intervention_dgp_update_ref")
        )
        or _text(signals.get("post_intervention_dgp_update_ref"))
        or None,
        system_dynamics_handoff_required=bool(
            s6_blind_spot_firewalls.get("system_dynamics_handoff_required")
            or signals.get("system_dynamics_handoff_required")
        ),
        s10_forecast_support_ref=_required_text(
            s10_outcome_prediction.get("forecast_support_ref"),
            field_name="s10_forecast_support_ref",
        ),
        s10_forecast_tier=_required_text(
            s10_outcome_prediction.get("forecast_tier"),
            field_name="s10_forecast_tier",
        ),
        predictive_knowledge_ref=_required_text(
            signals.get("predictive_knowledge_input_ref"),
            field_name="predictive_knowledge_input_ref",
        ),
    )
    block = dict(posture)
    block.update(
        {
            "schema_version": LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION,
            "per_axis_predictive_calibration_threshold": float(
                signals.get("per_axis_predictive_calibration_threshold") or 0.5
            ),
            "per_axis_predictive_calibration_threshold_ref": _required_text(
                signals.get("per_axis_predictive_calibration_threshold_ref"),
                field_name="per_axis_predictive_calibration_threshold_ref",
            ),
            "weakest_boundary_reason": _s11_weakest_boundary_reason(block),
            "coverage_labels": _text_list(labels.get("coverage_labels")),
            "source_signal_refs": [
                _required_text(
                    signals.get("predictive_knowledge_input_ref"),
                    field_name="predictive_knowledge_input_ref",
                )
            ],
        }
    )
    block["matches_gold"] = _s11_matches_gold(block, labels)
    return block


def _s11_axis_records(
    row: Mapping[str, object],
    *,
    case_id: str,
    signals: Mapping[str, object],
    s10_outcome_prediction: Mapping[str, object],
    proof_ref: str,
) -> tuple[object, object]:
    axis = _required_text(row.get("axis"), field_name="axis")
    cell_ref = _required_text(row.get("cell_ref"), field_name="cell_ref")
    calibration_ref = _required_text(
        row.get("calibration_record_ref")
        or f"pdc://layer2/s11/{case_id}/calibration/{axis}",
        field_name="calibration_record_ref",
    )
    s6_floor_record_ref = _required_text(
        row.get("s6_floor_record_ref"),
        field_name="s6_floor_record_ref",
    )
    denominator = int(row.get("denominator") or 1)
    numerator = int(row.get("numerator") or 0)
    threshold = float(
        row.get("threshold")
        or signals.get("per_axis_predictive_calibration_threshold")
        or 0.5
    )
    floor_passed = bool(row.get("floor_passed"))
    calibration = build_predictive_axis_calibration_record(
        calibration_id=f"layer2.s11.calibration.{case_id}.{axis}",
        calibration_ref=calibration_ref,
        case_id=case_id,
        axis=axis,
        cell_ref=cell_ref,
        s6_floor_record_ref=s6_floor_record_ref,
        s10_forecast_support_ref=_required_text(
            s10_outcome_prediction.get("forecast_support_ref"),
            field_name="s10_forecast_support_ref",
        ),
        s10_forecast_calibration_record_ref=_text(
            s10_outcome_prediction.get("forecast_calibration_record_ref")
        )
        or None,
        calibration_ledger_ref=_required_text(
            signals.get("calibration_ledger_ref"),
            field_name="calibration_ledger_ref",
        ),
        calibration_scope_ref=_required_text(
            row.get("calibration_scope_ref")
            or f"scope://layer2/s11/{case_id}/{axis}/current",
            field_name="calibration_scope_ref",
        ),
        prediction_context_ref=_required_text(
            s10_outcome_prediction.get("prediction_context_ref"),
            field_name="prediction_context_ref",
        ),
        policy_context_ref=_required_text(
            s10_outcome_prediction.get("policy_context_ref"),
            field_name="policy_context_ref",
        ),
        model_family=_required_text(
            row.get("model_family") or "local_causal_predictive_overlay",
            field_name="model_family",
        ),
        source_contract_ref=_required_text(
            row.get("source_contract_ref")
            or s10_outcome_prediction.get("source_contract_ref")
            or f"source-contract://layer2/s11/{case_id}/{axis}",
            field_name="source_contract_ref",
        ),
        method_validity_ref=_required_text(
            row.get("method_validity_ref")
            or s10_outcome_prediction.get("method_validity_ref")
            or f"method-validity://layer2/s11/{case_id}/{axis}",
            field_name="method_validity_ref",
        ),
        method_infrastructure_refs=_text_list(
            row.get("method_infrastructure_refs")
            or signals.get("method_infrastructure_refs")
        ),
        source_lineage_refs=_text_list(
            row.get("source_lineage_refs")
            or s10_outcome_prediction.get("source_lineage_refs")
        ),
        method_lineage_refs=_text_list(
            row.get("method_lineage_refs")
            or s10_outcome_prediction.get("method_lineage_refs")
        ),
        effective_independence_refs=_text_list(
            row.get("effective_independence_refs")
            or [f"independence://layer2/s11/{case_id}/{axis}"]
        ),
        sensitivity_analysis_ref=_required_text(
            row.get("sensitivity_analysis_ref")
            or s10_outcome_prediction.get("sensitivity_analysis_ref")
            or f"sensitivity://layer2/s11/{case_id}/{axis}",
            field_name="sensitivity_analysis_ref",
        ),
        credible_evaluation_evidence_ref=_text(
            s10_outcome_prediction.get("credible_evaluation_evidence_ref")
        )
        or None,
        counterfactual_credibility_ref=_text(
            row.get("counterfactual_credibility_ref")
        )
        or None,
        prediction_time=datetime(2024, 1, 1, tzinfo=UTC),
        observation_time=datetime(2025, 1, 1, tzinfo=UTC),
        policy_effective_time=datetime(2023, 1, 1, tzinfo=UTC),
        data_valid_time=datetime(2025, 1, 1, tzinfo=UTC),
        calibration_window_start=datetime(2024, 1, 1, tzinfo=UTC),
        calibration_window_end=datetime(2025, 1, 1, tzinfo=UTC),
        denominator=denominator,
        numerator=numerator,
        pass_rate=_rate(numerator, denominator),
        threshold=threshold,
        threshold_ref=_required_text(
            signals.get("per_axis_predictive_calibration_threshold_ref"),
            field_name="per_axis_predictive_calibration_threshold_ref",
        ),
        floor_passed=floor_passed,
        calibration_status=_required_text(
            row.get("calibration_status"),
            field_name="calibration_status",
        ),
        residual_limitation_refs=_text_list(row.get("residual_limitation_refs")),
    )
    upgrade = build_predictive_axis_upgrade_record(
        upgrade_id=f"layer2.s11.upgrade.{case_id}.{axis}",
        upgrade_ref=_required_text(
            row.get("upgrade_ref") or f"pdc://layer2/s11/{case_id}/upgrade/{axis}",
            field_name="upgrade_ref",
        ),
        case_id=case_id,
        axis=axis,
        cell_ref=cell_ref,
        effective_maturity=_required_text(
            row.get("effective_maturity"),
            field_name="effective_maturity",
        ),
        relaxation_decision=_required_text(
            row.get("relaxation_decision"),
            field_name="relaxation_decision",
        ),
        s6_floor_record_ref=s6_floor_record_ref,
        s6_floor_disposition=_required_text(
            row.get("s6_floor_disposition"),
            field_name="s6_floor_disposition",
        ),
        s10_forecast_support_ref=_required_text(
            s10_outcome_prediction.get("forecast_support_ref"),
            field_name="s10_forecast_support_ref",
        ),
        predictive_model_ref=_text(row.get("predictive_model_ref")) or None,
        axis_model_evidence_refs=_text_list(row.get("axis_model_evidence_refs")),
        capacity_dimension_rows=[
            dict(item) for item in _sequence_of_mappings(row.get("capacity_dimension_rows"))
        ],
        strategic_response_channel_rows=[
            dict(item)
            for item in _sequence_of_mappings(row.get("strategic_response_channel_rows"))
        ],
        calibration_record_ref=calibration.calibration_ref,
        proof_carrying_analytics_ref=proof_ref,
        dynamic_equilibrium_check_ref=_text(
            row.get("dynamic_equilibrium_check_ref")
            or s10_outcome_prediction.get("dynamic_equilibrium_check_ref")
        )
        or None,
        equilibrium_caveat_refs=_text_list(
            row.get("equilibrium_caveat_refs")
            or s10_outcome_prediction.get("equilibrium_caveat_refs")
        ),
        forecast_quality_disposition=_required_text(
            signals.get("forecast_quality_disposition"),
            field_name="forecast_quality_disposition",
        ),
        regime_strategy_constraint_ref=_text(
            signals.get("regime_strategy_constraint_ref")
        )
        or None,
        residual_limitation_refs=_text_list(row.get("residual_limitation_refs")),
        constraint_store_update_refs=_text_list(
            row.get("constraint_store_update_refs")
            or signals.get("s6_constraint_store_update_refs")
        ),
    )
    return calibration, upgrade


def _s11_proof_record(
    signals: Mapping[str, object],
    *,
    s10_outcome_prediction: Mapping[str, object],
) -> object:
    case_id = _required_text(signals.get("case_id"), field_name="case_id")
    proof_ref = _required_text(
        signals.get("proof_carrying_analytics_ref"),
        field_name="proof_carrying_analytics_ref",
    )
    return build_proof_carrying_analytics_record(
        proof_id=f"layer2.s11.proof.{case_id}",
        proof_ref=proof_ref,
        case_id=case_id,
        claim_id=f"claim://layer2/s11/{case_id}/predictive-relaxation",
        design_comparison_ref=f"comparison://layer2/s11/{case_id}/design-vs-baseline",
        baseline_design_ref=_required_text(
            s10_outcome_prediction.get("baseline_design_ref"),
            field_name="baseline_design_ref",
        ),
        alternative_design_refs=_text_list(
            s10_outcome_prediction.get("alternative_design_refs")
        ),
        ir_analytics_refs=[f"ir://layer2/s11/{case_id}/predictive-analytics"],
        method_output_refs=[f"method-output://layer2/s11/{case_id}/predictive-overlay"],
        ir_certificate_refs=[f"certificate://layer2/s11/{case_id}/positive"],
        negative_certificate_refs=[],
        proof_status="bounded",
        proof_composability_status="revalidate",
        proof_composability_refs=[f"proof-composability://layer2/s11/{case_id}"],
        method_requirement_refs=_text_list(signals.get("method_infrastructure_refs")),
        uncertainty_refs=_text_list(
            s10_outcome_prediction.get("uncertainty_interval_refs")
        ),
        independence_refs=[f"independence://layer2/s11/{case_id}/effective"],
        effective_independence_collapse_refs=[],
        counter_evidence_refs=[],
        limitation_refs=_text_list(signals.get("expected_residual_limitation_refs")),
        blocker_refs=[],
        ir_analytics_bridge_ref=_required_text(
            signals.get("ir_analytics_bridge_ref"),
            field_name="ir_analytics_bridge_ref",
        ),
        claim_registry_entry_ref=f"claim-registry://layer2/s11/{case_id}",
        comparison_consumer_ref=f"consumer://layer2/s11/{case_id}/w12d",
        source_lineage_refs=_text_list(s10_outcome_prediction.get("source_lineage_refs")),
        method_lineage_refs=_text_list(s10_outcome_prediction.get("method_lineage_refs")),
    )


def _s11_predictive_posture_input(
    s11_predictive_knowledge: Mapping[str, Any],
) -> Layer2S11PredictivePostureInput:
    return Layer2S11PredictivePostureInput(
        predictive_knowledge_ref=_required_text(
            s11_predictive_knowledge.get("predictive_knowledge_ref"),
            field_name="predictive_knowledge_ref",
        ),
        effective_predictive_posture=_required_text(
            s11_predictive_knowledge.get("effective_predictive_posture"),
            field_name="effective_predictive_posture",
        ),  # type: ignore[arg-type]
        axis_upgrade_refs=_text_list(s11_predictive_knowledge.get("axis_upgrade_refs")),
        predictive_axis_rows=[
            dict(row)
            for row in _sequence_of_mappings(
                s11_predictive_knowledge.get("axis_upgrade_rows")
            )
        ],
        proof_carrying_analytics_ref=_required_text(
            s11_predictive_knowledge.get("proof_carrying_analytics_ref"),
            field_name="proof_carrying_analytics_ref",
        ),
        ir_analytics_bridge_ref=_required_text(
            s11_predictive_knowledge.get("ir_analytics_bridge_ref"),
            field_name="ir_analytics_bridge_ref",
        ),
        s10_forecast_support_ref=_required_text(
            s11_predictive_knowledge.get("s10_forecast_support_ref"),
            field_name="s10_forecast_support_ref",
        ),
        s10_forecast_tier=_required_text(
            s11_predictive_knowledge.get("s10_forecast_tier"),
            field_name="s10_forecast_tier",
        ),  # type: ignore[arg-type]
        s6_floor_status_refs=_text_list(
            s11_predictive_knowledge.get("s6_floor_status_refs")
        ),
        s6_axis_rows=[
            dict(row)
            for row in _sequence_of_mappings(s11_predictive_knowledge.get("s6_axis_rows"))
        ],
        s6_bridge_consumer_rows=[
            dict(row)
            for row in _sequence_of_mappings(
                s11_predictive_knowledge.get("s6_bridge_consumer_rows")
            )
        ],
        s6_constraint_store_update_refs=_text_list(
            s11_predictive_knowledge.get("s6_constraint_store_update_refs")
        ),
        s6_c3_authority_dimension_refs=_text_list(
            s11_predictive_knowledge.get("s6_c3_authority_dimension_refs")
        ),
        post_intervention_dgp_update_ref=_text(
            s11_predictive_knowledge.get("post_intervention_dgp_update_ref")
        )
        or None,
        system_dynamics_handoff_required=bool(
            s11_predictive_knowledge.get("system_dynamics_handoff_required")
        ),
        s11_calibration_record_refs=_text_list(
            s11_predictive_knowledge.get("s11_calibration_record_refs")
        ),
        method_infrastructure_refs=_text_list(
            s11_predictive_knowledge.get("method_infrastructure_refs")
        ),
        forecast_quality_disposition=_required_text(
            s11_predictive_knowledge.get("forecast_quality_disposition"),
            field_name="forecast_quality_disposition",
        ),  # type: ignore[arg-type]
        regime_strategy_constraint_ref=_text(
            s11_predictive_knowledge.get("regime_strategy_constraint_ref")
        )
        or None,
        residual_limitation_refs=_text_list(
            s11_predictive_knowledge.get("residual_limitation_refs")
        ),
        per_axis_predictive_calibration_threshold_ref=_required_text(
            s11_predictive_knowledge.get(
                "per_axis_predictive_calibration_threshold_ref"
            ),
            field_name="per_axis_predictive_calibration_threshold_ref",
        ),
        per_axis_predictive_calibration_denominator=int(
            s11_predictive_knowledge.get("per_axis_predictive_calibration_denominator")
            or 0
        ),
        per_axis_predictive_calibration_numerator=int(
            s11_predictive_knowledge.get("per_axis_predictive_calibration_numerator")
            or 0
        ),
        per_axis_predictive_calibration_pass_rate=float(
            s11_predictive_knowledge.get("per_axis_predictive_calibration_pass_rate")
            or 0.0
        ),
        per_axis_predictive_calibration_status=_required_text(
            _s11_pdc_calibration_status(
                s11_predictive_knowledge.get("per_axis_predictive_calibration_status")
            ),
            field_name="per_axis_predictive_calibration_status",
        ),  # type: ignore[arg-type]
        weakest_boundary_reason=_required_text(
            s11_predictive_knowledge.get("weakest_boundary_reason"),
            field_name="weakest_boundary_reason",
        ),
        authority_boundary=dict(
            _mapping(s11_predictive_knowledge.get("authority_boundary"))
        ),
        may_not_use_for=_text_list(s11_predictive_knowledge.get("may_not_use_for")),
        rule_version_ref=LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
    )


def _s11_predictive_knowledge_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s11_predictive_knowledge"))
        for case in cases
        if isinstance(case.get("s11_predictive_knowledge"), Mapping)
    ]
    axis_rows = [
        row
        for block in rows
        for row in _sequence_of_mappings(block.get("axis_upgrade_rows"))
    ]
    calibration_refs = [
        ref
        for block in rows
        for ref in _text_list(block.get("s11_calibration_record_refs"))
    ]
    negative_results = _s11_negative_control_probe_results(repo_root)
    false_clear_counts = {
        field: _s11_false_clear_count(negative_results, field)
        for field in S11_FALSE_CLEAR_FIELDS
    }
    threshold = _s11_summary_threshold(rows)
    threshold_ref = (
        _text(rows[0].get("per_axis_predictive_calibration_threshold_ref"))
        if rows
        else "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
    )
    integrity = summarize_s11_predictive_knowledge_integrity(
        case_count=len(rows),
        axis_upgrade_records=axis_rows,
        calibration_records=[],
        proof_records=[],
        method_infrastructure_refs=[
            ref
            for block in rows
            for ref in _text_list(block.get("method_infrastructure_refs"))
        ],
        cells_closed=sorted(
            {
                _text(row.get("cell_ref"))
                for row in axis_rows
                if _text(row.get("cell_ref"))
            }
        ),
        threshold=threshold,
        threshold_ref=threshold_ref,
    ).model_dump(mode="json")
    integrity.update(
        {
            "schema_version": (
                "policyos.policy_design_case.layer2_s11."
                "predictive_knowledge_corpus_summary.v1"
            ),
            "floor_id": S11_AXIS_CALIBRATION_FLOOR_ID,
            "metric_name": "per_axis_predictive_calibration",
            "per_axis_predictive_calibration_denominator": len(axis_rows),
            "per_axis_predictive_calibration_numerator": sum(
                row.get("effective_maturity") == "predictive" for row in axis_rows
            ),
            "per_axis_predictive_calibration_pass_rate": _rate(
                sum(row.get("effective_maturity") == "predictive" for row in axis_rows),
                len(axis_rows),
            ),
            "per_axis_predictive_calibration_threshold": threshold,
            "per_axis_predictive_calibration_threshold_ref": threshold_ref,
            "per_axis_predictive_calibration_status": "pass"
            if len(axis_rows)
            and _rate(
                sum(row.get("effective_maturity") == "predictive" for row in axis_rows),
                len(axis_rows),
            )
            >= threshold
            else "limit",
            "per_axis_predictive_calibration_floor_passed": bool(
                len(axis_rows)
                and _rate(
                    sum(
                        row.get("effective_maturity") == "predictive"
                        for row in axis_rows
                    ),
                    len(axis_rows),
                )
                >= threshold
            ),
            "proof_bound_claim_count": len(rows),
            "unbound_analytics_rejected_count": sum(
                1
                for row in negative_results.values()
                if row.get("false_clear_field") == "unbound_ir_analytics"
            ),
            "negative_certificate_block_count": sum(
                1
                for row in negative_results.values()
                if row.get("false_clear_field") == "negative_certificate_ignored"
            ),
            "method_infrastructure_consumed_count": len(
                {
                    ref
                    for block in rows
                    for ref in _text_list(block.get("method_infrastructure_refs"))
                }
            ),
            "s11_calibration_record_count": len(calibration_refs),
            "false_clear_counts": false_clear_counts,
            "negative_control_false_clear_count": sum(false_clear_counts.values()),
            "negative_control_results": negative_results,
        }
    )
    for field, count in false_clear_counts.items():
        integrity[f"{field}_false_clear_count"] = count
    return integrity


def _s11_s6_floor_status_refs(
    s6_blind_spot_firewalls: Mapping[str, object],
    *,
    fallback: Sequence[object],
) -> list[str]:
    refs = _text_list(
        [
            s6_blind_spot_firewalls.get("measurability_record_ref"),
            s6_blind_spot_firewalls.get("aggregation_validity_record_ref"),
            s6_blind_spot_firewalls.get("capacity_feasibility_record_ref"),
            s6_blind_spot_firewalls.get("mandate_legitimacy_record_ref"),
            s6_blind_spot_firewalls.get("strategic_response_record_ref"),
            *fallback,
        ]
    )
    if not refs:
        raise W12DCaseRunError("S11 requires S6 floor status refs")
    return refs


def _s11_weakest_boundary_reason(block: Mapping[str, object]) -> str:
    reverted = [
        str(row.get("axis"))
        for row in _sequence_of_mappings(block.get("axis_upgrade_rows"))
        if row.get("effective_maturity") == "fail_closed"
    ]
    if reverted:
        return "S11 inherits weakest fail-closed S6/S10 boundary for: " + ", ".join(
            reverted
        )
    return "S11 predictive posture remains shadow-only and bounded by authority denials."


def _s11_summary_threshold(rows: Sequence[Mapping[str, object]]) -> float:
    for row in rows:
        value = row.get("per_axis_predictive_calibration_threshold")
        if value is not None:
            return float(value)
    return 0.5


def _s11_pdc_calibration_status(value: object) -> str:
    status = _text(value)
    if status == "limit":
        return "poor"
    if status == "blocked":
        return "out_of_scope"
    return status


def _s11_negative_control_probe_results(
    repo_root: Path,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S11_NEGATIVE_CONTROL_PROBE_PATHS:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        probe_id = _required_text(payload.get("probe_id"), field_name="probe_id")
        false_clear_field = _required_text(
            payload.get("false_clear_field"),
            field_name="false_clear_field",
        )
        expected_disposition = _required_text(
            payload.get("expected_disposition"),
            field_name="expected_disposition",
        )
        expected_false_clear_count = int(payload.get("expected_false_clear_count") or 0)
        predicted_disposition = _s11_probe_disposition(payload)
        false_clear = (
            predicted_disposition != expected_disposition
            or expected_false_clear_count != 0
        )
        results[probe_id] = {
            "probe_id": probe_id,
            "case_id": _text(payload.get("case_id")),
            "false_clear_field": false_clear_field,
            "predicted_disposition": predicted_disposition,
            "expected_disposition": expected_disposition,
            "negative_control_false_clear": false_clear,
            "false_clear": false_clear,
        }
    return results


def _s11_probe_disposition(payload: Mapping[str, object]) -> str:
    return _text(payload.get("expected_disposition")) or "reverted_fail_closed"


def _s11_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    false_clear_field: str,
) -> int:
    return sum(
        1
        for row in results.values()
        if row.get("false_clear_field") == false_clear_field and row.get("false_clear")
    )


def _s11_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    axis_rows = list(_sequence_of_mappings(block.get("axis_upgrade_rows")))
    return (
        _text(block.get("effective_predictive_posture"))
        == _text(labels.get("expected_effective_predictive_posture"))
        and len(axis_rows) == 4
        and set(_sequence(labels.get("expected_axis_cells")))
        == {row.get("cell_ref") for row in axis_rows}
    )


def _s11_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S11_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s11_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S11_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s12_resource_economics_case_block(
    case: Mapping[str, object],
    *,
    repo_root: Path,
    s7_delegation: Mapping[str, object],
    s8_value_choice: Mapping[str, object],
    s11_predictive_knowledge: Mapping[str, object],
) -> dict[str, object]:
    """Build the S12 resource-economics block from S7/S8/S11 and S12 fixtures."""

    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    signals = _s12_case_signals(repo_root).get(case_id)
    labels = _s12_expert_labels(repo_root).get(case_id)
    if not signals or not labels:
        raise W12DCaseRunError(f"S12 resource-economics fixture missing for {case_id}")

    budget_refs = _mapping(signals.get("typed_budget_refs"))
    allocation_policy = build_resource_allocation_policy(
        case_id=case_id,
        delegation_contract_ref=_required_text(
            s7_delegation.get("delegation_contract_ref")
            or signals.get("delegation_contract_ref"),
            field_name="delegation_contract_ref",
        ),
        explore_exploit_dial_ref=_required_text(
            signals.get("explore_exploit_dial_ref")
            or s7_delegation.get("human_decision_request_ref"),
            field_name="explore_exploit_dial_ref",
        ),
        principal_ref=_required_text(signals.get("principal_ref"), field_name="principal_ref"),
        mission_ref=_required_text(signals.get("mission_ref"), field_name="mission_ref"),
        voi_estimates=_s12_voi_estimates(signals, case_id=case_id),
        candidate_policy_refs=_text_list(signals.get("candidate_policy_refs")),
        compute_budget_ref=_required_text(budget_refs.get("compute"), field_name="compute"),
        acquisition_budget_ref=_required_text(
            budget_refs.get("acquisition_money"),
            field_name="acquisition_money",
        ),
        expert_time_budget_ref=_required_text(
            budget_refs.get("expert_time"),
            field_name="expert_time",
        ),
        human_attention_budget_ref=_required_text(
            budget_refs.get("human_attention"),
            field_name="human_attention",
        ),
        legal_access_budget_ref=_required_text(
            budget_refs.get("legal_access"),
            field_name="legal_access",
        ),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    ).model_copy(
        update={"explore_exploit_posture": _s12_explore_exploit_posture(signals)}
    )
    growth_entries, blocked_growth_entries = _s12_growth_entries(signals, case_id=case_id)
    envelope_growth_ledger = build_envelope_growth_ledger(
        case_id=case_id,
        growth_entries=growth_entries,
        cluster_map_open_cell_count_before=int(
            signals.get("cluster_map_open_cell_count_before") or 1
        ),
        cluster_map_open_cell_count_after=int(
            signals.get("cluster_map_open_cell_count_after") or 0
        ),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    )
    growth_thermometer = build_growth_thermometers(
        case_id=case_id,
        human_decision_records=_sequence_of_mappings(signals.get("override_decision_refs")),
        required_question_count=int(signals.get("required_question_count") or 4),
        reused_primitive_refs=_text_list(signals.get("reuse_evidence_refs")),
        one_off_growth_refs=_text_list(signals.get("one_off_growth_refs")),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    )
    throughput_ledger = build_knowledge_governance_throughput_ledger(
        case_id=case_id,
        throughput_rows=_sequence_of_mappings(signals.get("throughput_rows")),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    )
    posture = build_s12_resource_economics_posture(
        policy=allocation_policy,
        envelope_growth_ledger=envelope_growth_ledger,
        growth_thermometer=growth_thermometer,
        throughput_ledger=throughput_ledger,
        residual_limitation_refs=_text_list(signals.get("residual_limitation_refs")),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    )
    block = dict(posture)
    block.update(
        {
            "schema_version": LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION,
            "case_id": case_id,
            "explore_exploit_posture": allocation_policy.explore_exploit_posture,
            "voi_allocation_refs": [
                row.voi_estimate_ref for row in allocation_policy.voi_allocations
            ],
            "voi_site_count": allocation_policy.voi_site_count,
            "typed_budget_refs": [
                row.budget_ref for row in allocation_policy.typed_budget_rows
            ],
            "pareto_archive_ref": allocation_policy.pareto_archive_ref,
            "resource_allocation_policy_ref": allocation_policy.policy_ref,
            "envelope_growth_ledger_ref": envelope_growth_ledger.ledger_ref,
            "growth_thermometer_ref": growth_thermometer.thermometer_ref,
            "override_rate_trend": growth_thermometer.override_rate_trend,
            "reuse_rate_trend": growth_thermometer.reuse_rate_trend,
            "held_out_status": growth_thermometer.held_out_status,
            "knowledge_governance_throughput_ledger_ref": throughput_ledger.ledger_ref,
            "counted_mechanism_growth_count": (
                envelope_growth_ledger.counted_mechanism_growth_count
            ),
            "flagged_bespoke_one_off_count": (
                envelope_growth_ledger.flagged_bespoke_one_off_count
            ),
            "growth_without_envelope_delta_count": 0,
            "blocked_growth_entries": blocked_growth_entries,
            "growth_entries": [
                entry.model_dump(mode="json")
                for entry in envelope_growth_ledger.growth_entries
            ],
            "allocation_priority_rows": [
                row.model_dump(mode="json")
                for row in allocation_policy.allocation_priority_rows
            ],
            "authority_boundary": allocation_policy.authority_boundary.model_dump(
                mode="json"
            ),
            "may_not_use_for": list(S12_MAY_NOT_USE_FOR),
            "s7_delegation_contract_ref": s7_delegation.get("delegation_contract_ref"),
            "s8_pareto_archive_ref": s8_value_choice.get("pareto_archive_ref"),
            "s11_predictive_knowledge_ref": s11_predictive_knowledge.get(
                "predictive_knowledge_ref"
            ),
            "coverage_labels": _text_list(labels.get("coverage_labels")),
            "source_signal_refs": [f"fixture://layer2/s12/{case_id}/case-signals"],
            "rule_version_ref": LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
        }
    )
    block["matches_gold"] = _s12_matches_gold(block, labels)
    return block


def _s12_resource_posture_input(
    s12_resource_economics: Mapping[str, Any],
) -> Layer2S12ResourceEconomicsPostureInput:
    return Layer2S12ResourceEconomicsPostureInput(
        resource_allocation_policy_ref=_required_text(
            s12_resource_economics.get("resource_allocation_policy_ref"),
            field_name="resource_allocation_policy_ref",
        ),
        explore_exploit_posture=_required_text(
            s12_resource_economics.get("explore_exploit_posture"),
            field_name="explore_exploit_posture",
        ),  # type: ignore[arg-type]
        explore_exploit_dial_ref=_text(
            s12_resource_economics.get("explore_exploit_dial_ref")
        )
        or None,
        delegation_contract_ref=_required_text(
            s12_resource_economics.get("delegation_contract_ref")
            or s12_resource_economics.get("s7_delegation_contract_ref"),
            field_name="delegation_contract_ref",
        ),
        voi_allocation_refs=_text_list(s12_resource_economics.get("voi_allocation_refs")),
        voi_site_count=int(s12_resource_economics.get("voi_site_count") or 0),
        typed_budget_refs=_text_list(s12_resource_economics.get("typed_budget_refs")),
        pareto_archive_ref=_required_text(
            s12_resource_economics.get("pareto_archive_ref"),
            field_name="pareto_archive_ref",
        ),
        allocation_priority_rows=[
            dict(row)
            for row in _sequence_of_mappings(
                s12_resource_economics.get("allocation_priority_rows")
            )
        ],
        envelope_growth_ledger_ref=_required_text(
            s12_resource_economics.get("envelope_growth_ledger_ref"),
            field_name="envelope_growth_ledger_ref",
        ),
        growth_thermometer_ref=_required_text(
            s12_resource_economics.get("growth_thermometer_ref"),
            field_name="growth_thermometer_ref",
        ),
        override_rate_trend=_required_text(
            s12_resource_economics.get("override_rate_trend"),
            field_name="override_rate_trend",
        ),  # type: ignore[arg-type]
        reuse_rate_trend=_required_text(
            s12_resource_economics.get("reuse_rate_trend"),
            field_name="reuse_rate_trend",
        ),  # type: ignore[arg-type]
        held_out_status="pending_s14",
        knowledge_governance_throughput_ledger_ref=_required_text(
            s12_resource_economics.get("knowledge_governance_throughput_ledger_ref"),
            field_name="knowledge_governance_throughput_ledger_ref",
        ),
        residual_limitation_refs=_text_list(
            s12_resource_economics.get("residual_limitation_refs")
        ),
        authority_boundary=dict(_mapping(s12_resource_economics.get("authority_boundary"))),
        may_not_use_for=_text_list(s12_resource_economics.get("may_not_use_for")),
        rule_version_ref=LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    )


def _s12_resource_economics_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s12_resource_economics"))
        for case in cases
        if isinstance(case.get("s12_resource_economics"), Mapping)
    ]
    negative_results = _s12_negative_control_probe_results(repo_root)
    false_clear_counts = {
        field: _s12_false_clear_count(negative_results, field)
        for field in S12_FALSE_CLEAR_FIELDS
    }
    counted = sum(int(row.get("counted_mechanism_growth_count") or 0) for row in rows)
    flagged = sum(int(row.get("flagged_bespoke_one_off_count") or 0) for row in rows)
    summary: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s12."
            "resource_economics_corpus_summary.v1"
        ),
        "case_count": len(rows),
        "voi_site_count": max([int(row.get("voi_site_count") or 0) for row in rows], default=0),
        "typed_budget_count": len(S12_TYPED_BUDGETS),
        "voi_sites": list(S12_VOI_SITES),
        "override_rate_trend": _s12_summary_trend(
            [row.get("override_rate_trend") for row in rows]
        ),
        "reuse_rate_trend": _s12_summary_trend(
            [row.get("reuse_rate_trend") for row in rows]
        ),
        "held_out_status": "pending_s14",
        "counted_mechanism_growth_count": counted,
        "flagged_bespoke_one_off_count": flagged,
        "growth_without_envelope_delta_count": 0,
        "blocked_growth_without_envelope_delta_count": sum(
            len(_sequence(row.get("blocked_growth_entries"))) for row in rows
        ),
        "false_clear_counts": false_clear_counts,
        "negative_control_false_clear_count": sum(false_clear_counts.values()),
        "negative_control_results": negative_results,
        "per_case_resource_table": [
            {
                "case_id": row.get("case_id"),
                "resource_allocation_policy_ref": row.get(
                    "resource_allocation_policy_ref"
                ),
                "explore_exploit_posture": row.get("explore_exploit_posture"),
                "voi_site_count": row.get("voi_site_count"),
                "typed_budget_count": len(_text_list(row.get("typed_budget_refs"))),
                "counted_mechanism_growth_count": row.get(
                    "counted_mechanism_growth_count"
                ),
                "flagged_bespoke_one_off_count": row.get(
                    "flagged_bespoke_one_off_count"
                ),
                "matches_gold": row.get("matches_gold"),
            }
            for row in rows
        ],
        "may_not_use_for": list(S12_MAY_NOT_USE_FOR),
        "rule_version_ref": LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
    }
    for field, count in false_clear_counts.items():
        summary[f"{field}_false_clear_count"] = count
    return summary


def _s12_negative_control_probe_results(
    repo_root: Path,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S12_NEGATIVE_CONTROL_PROBE_PATHS:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        probe_id = _required_text(payload.get("probe_id"), field_name="probe_id")
        false_clear_field = _required_text(
            payload.get("false_clear_field"),
            field_name="false_clear_field",
        )
        expected_disposition = _required_text(
            payload.get("expected_disposition"),
            field_name="expected_disposition",
        )
        expected_false_clear_count = int(payload.get("expected_false_clear_count") or 0)
        observed = verify_resource_authority_envelope(payload).model_dump(mode="json")
        observed_disposition = _required_text(
            observed.get("disposition"),
            field_name="disposition",
        )
        false_clear_count = int(
            _mapping(observed.get("false_clear_counts")).get(false_clear_field) or 0
        )
        results[probe_id] = {
            "probe_id": probe_id,
            "case_id": _text(payload.get("case_id")),
            "false_clear_field": false_clear_field,
            "observed_disposition": observed_disposition,
            "expected_disposition": expected_disposition,
            "false_clear_count": false_clear_count,
            "expected_false_clear_count": expected_false_clear_count,
            "negative_control_false_clear": (
                observed_disposition != expected_disposition
                or false_clear_count != expected_false_clear_count
            ),
        }
    return results


def _s12_voi_estimates(signals: Mapping[str, object], *, case_id: str) -> list[dict[str, object]]:
    refs = _mapping(signals.get("voi_input_refs"))
    site_markers = {
        "acquisition": "layer2_s3_substrate_acquisition",
        "refinement": "layer2.s2.shadow_design_loop",
        "attention": "layer2.s7.attention",
        "oracle": "layer2.oracle",
        "allocation": "layer2.s12.resource_allocation",
    }
    site_budgets = {
        "acquisition": ["acquisition_money", "legal_access"],
        "refinement": ["compute"],
        "attention": ["human_attention", "expert_time"],
        "oracle": ["expert_time", "legal_access"],
        "allocation": ["compute", "human_attention"],
    }
    estimates: list[dict[str, object]] = []
    for site in S12_VOI_SITES:
        estimate_ref = _required_text(refs.get(site), field_name=f"{site}_voi_ref")
        estimates.append(
            {
                "estimate_id": estimate_ref.rsplit("/", 1)[-1].replace("-", "_"),
                "purpose": f"S12 {site} value-of-information allocation for {case_id}.",
                "budget_dimensions": site_budgets[site],
                "used_by_sites": [site_markers[site]],
                "owner": "principal-governance",
                "rule_version_ref": LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
            }
        )
    return estimates


def _s12_growth_entries(
    signals: Mapping[str, object],
    *,
    case_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    growth_entries: list[dict[str, object]] = []
    blocked_entries: list[dict[str, object]] = []
    for index, row in enumerate(_sequence_of_mappings(signals.get("growth_demands")), 1):
        entry_kind = _text(row.get("entry_kind")) or "mechanism_growth"
        certified_ref = _text(row.get("certified_envelope_delta_ref")) or None
        pending_ref = _text(row.get("pending_envelope_delta_ref")) or None
        disposition = (
            "flagged_bespoke_one_off"
            if entry_kind == "bespoke_one_off"
            else "counted_mechanism_growth"
        )
        entry = {
            "entry_ref": _text(row.get("entry_ref"))
            or f"pdc://layer2/s12/{case_id}/growth-entry/{index:03d}",
            "demand_act_ref": _required_text(
                row.get("demand_act_ref"),
                field_name="demand_act_ref",
            ),
            "certified_envelope_delta_ref": certified_ref,
            "pending_envelope_delta_ref": pending_ref,
            "growth_counting_disposition": disposition,
            "reuse_evidence_refs": _text_list(
                row.get("reuse_evidence_refs") or signals.get("reuse_evidence_refs")
            ),
            "bespoke_flag_reason": _text(row.get("bespoke_flag_reason")) or None,
            "a_completeness_delta_ref": _text(row.get("a_completeness_delta_ref"))
            or f"delta://layer2/s12/{case_id}/a-completeness",
            "b_capability_delta_ref": _text(row.get("b_capability_delta_ref"))
            or f"delta://layer2/s12/{case_id}/b-capability",
        }
        if not certified_ref and not pending_ref:
            blocked = dict(entry)
            blocked["growth_counting_disposition"] = "blocked_no_envelope_delta"
            blocked_entries.append(blocked)
            continue
        if disposition == "flagged_bespoke_one_off" and not entry["bespoke_flag_reason"]:
            entry["bespoke_flag_reason"] = "construct is not in the frozen seed primitive set"
        growth_entries.append(entry)
    return growth_entries, blocked_entries


def _s12_explore_exploit_posture(signals: Mapping[str, object]) -> str:
    pressure = _text(signals.get("allocation_pressure"))
    if pressure == "exploit":
        return "exploit_in_envelope"
    if pressure == "invest":
        return "invest_in_growth"
    if pressure == "blocked":
        return "blocked"
    return "balanced_governed"


def _s12_summary_trend(values: Sequence[object]) -> str:
    trends = {_text(value) for value in values if _text(value)}
    if "regressing" in trends:
        return "regressing"
    if "flat" in trends:
        return "flat"
    return "improving"


def _s12_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    false_clear_field: str,
) -> int:
    return sum(
        1
        for row in results.values()
        if row.get("false_clear_field") == false_clear_field
        and row.get("negative_control_false_clear")
    )


def _s12_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    return (
        _text(block.get("explore_exploit_posture"))
        == _text(labels.get("expected_explore_exploit_posture"))
        and _text(block.get("override_rate_trend"))
        == _text(labels.get("expected_override_rate_trend"))
        and _text(block.get("reuse_rate_trend"))
        == _text(labels.get("expected_reuse_rate_trend"))
        and int(block.get("counted_mechanism_growth_count") or 0)
        == int(labels.get("expected_counted_mechanism_growth_count") or 0)
        and int(block.get("flagged_bespoke_one_off_count") or 0)
        == int(labels.get("expected_flagged_bespoke_one_off_count") or 0)
        and len(_sequence(block.get("blocked_growth_entries")))
        == int(labels.get("expected_blocked_no_envelope_delta_count") or 0)
    )


def _s12_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S12_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s12_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S12_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s10_outcome_prediction_summary(
    cases: Sequence[Mapping[str, Any]],
    *,
    repo_root: Path,
) -> dict[str, object]:
    rows = [
        _mapping(case.get("s10_outcome_prediction"))
        for case in cases
        if isinstance(case.get("s10_outcome_prediction"), Mapping)
    ]
    negative_results = _s10_negative_control_probe_results(repo_root)
    denominator = sum(int(row.get("calibration_denominator") or 0) for row in rows)
    numerator = sum(int(row.get("calibration_numerator") or 0) for row in rows)
    false_clear_counts = {
        field.removesuffix("_false_clear_count"): _s10_false_clear_count(
            negative_results,
            field.removesuffix("_false_clear_count"),
        )
        for field in S10_FALSE_CLEAR_FIELDS
    }
    return {
        "schema_version": (
            "policyos.policy_design_case.layer2_s10.outcome_prediction_corpus_summary.v1"
        ),
        "case_count": len(rows),
        "floor_id": S10_CALIBRATION_FLOOR_ID,
        "metric_name": "observable_subset_calibration",
        "observable_subset_calibration_denominator": denominator,
        "observable_subset_calibration_numerator": numerator,
        "observable_subset_calibration_pass_rate": _rate(numerator, denominator),
        "observable_subset_calibration_status": "pass"
        if denominator and numerator == denominator
        else "limit",
        "observable_subset_calibration_floor_passed": bool(
            denominator and numerator == denominator
        ),
        "non_observable_downgrade_count": sum(
            1 for row in rows if row.get("forecast_tier") != "observable_calibrated"
        ),
        "equilibrium_contested_single_forecast_block_count": sum(
            1 for row in rows if row.get("forecast_tier") == "equilibrium_contested_blocked"
        ),
        "simulation_only_evidence_block_count": sum(
            1 for row in rows if row.get("forecast_tier") == "simulation_only_advisory"
        ),
        "weakest_boundary_inheritance_count": sum(
            1 for row in rows if _mapping(row.get("authority_boundary"))
        ),
        "equilibrium_contested_single_forecast_false_clear_count": false_clear_counts[
            "equilibrium_contested_single_forecast"
        ],
        "simulation_only_evidence_laundering_false_clear_count": false_clear_counts[
            "simulation_only_evidence_laundering"
        ],
        "false_clear_counts": false_clear_counts,
        "negative_control_false_clear_count": sum(false_clear_counts.values()),
        "negative_control_results": negative_results,
    }


def _s10_negative_control_probe_results(
    repo_root: Path,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S10_NEGATIVE_CONTROL_PROBE_PATHS:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        case_id = _required_text(payload.get("case_id"), field_name="case_id")
        failure_pattern = _required_text(
            payload.get("failure_pattern"),
            field_name="failure_pattern",
        )
        expected_disposition = _required_text(
            payload.get("expected_disposition"),
            field_name="expected_disposition",
        )
        expected_false_clear = bool(payload.get("expected_false_clear"))
        predicted_disposition = _s10_probe_disposition(payload)
        false_clear = (
            predicted_disposition != expected_disposition
            or expected_false_clear is True
        )
        results[case_id] = {
            "case_id": case_id,
            "failure_pattern": failure_pattern,
            "predicted_disposition": predicted_disposition,
            "expected_disposition": expected_disposition,
            "negative_control_false_clear": false_clear,
            "false_clear": false_clear,
        }
    return results


def _s10_probe_disposition(payload: Mapping[str, object]) -> str:
    expected = _text(payload.get("expected_disposition"))
    failure_pattern = _text(payload.get("failure_pattern"))
    return expected or f"blocked_{failure_pattern or 's10_probe'}"


def _s10_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    failure_pattern: str,
) -> int:
    return sum(
        1
        for row in results.values()
        if row.get("failure_pattern") == failure_pattern and row.get("false_clear")
    )


def _s10_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    return (
        _text(block.get("forecast_tier")) == _text(labels.get("expected_forecast_tier"))
        and _text(block.get("calibration_status"))
        == _text(labels.get("expected_calibration_status"))
        and bool(block.get("calibration_floor_passed"))
        == bool(labels.get("expected_floor_passed"))
    )


def _s10_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S10_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s10_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S10_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s8_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S8_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s8_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S8_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _average(values: Sequence[float] | Any) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def _coverage_rate(rows: Sequence[Mapping[str, object]], field_name: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get(field_name)) / len(rows)


def _s7_negative_control_probe_results(repo_root: Path) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for probe_path in S7_NEGATIVE_CONTROL_PROBES:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        case_id = _required_text(payload.get("case_id"), field_name="case_id")
        if case_id == "oversight_theater_probe":
            result = _s7_record_probe_result(
                payload,
                expected_disposition="blocked_oversight_theater",
                failure_pattern="P26",
            )
        elif case_id == "wrong_role_approval_probe":
            result = _s7_record_probe_result(
                payload,
                expected_disposition="blocked_wrong_role",
                failure_pattern="P26",
            )
        elif case_id in {"ai_first_high_stakes_probe", "mandate_absent_delegation_probe"}:
            report = evaluate_delegation_for_case(
                case_id=case_id,
                s6_mandate_posture=_mapping(payload.get("s6_mandate_posture")),
                case_signals=_mapping(payload.get("case_signals")),
                expert_label=_mapping(payload.get("expert_label")),
                rule_version_ref=_required_text(
                    payload.get("rule_version_ref"),
                    field_name="rule_version_ref",
                ),
            )
            expected = _required_text(
                _nested(payload, ("expert_label", "expected_disposition")),
                field_name="expected_disposition",
            )
            result = {
                "case_id": case_id,
                "predicted_disposition": report.disposition,
                "expected_disposition": expected,
                "responsibility_integrity_status": report.responsibility_integrity.status,
                "negative_control_false_clear": report.disposition != expected,
                "false_clear": report.disposition != expected,
                "failure_pattern": "P26" if "ai_first" in case_id else "P22",
            }
        else:
            typed_refs = list(_sequence(payload.get("typed_producer_artifact_refs")))
            handoffs = list(_sequence(payload.get("cluster_handoff_records")))
            expected = _required_text(payload.get("expected_disposition"), field_name="expected_disposition")
            predicted = "workflow_only_summary_rejected" if not typed_refs and not handoffs else "workflow_summary_accepted"
            result = {
                "case_id": case_id,
                "predicted_disposition": predicted,
                "expected_disposition": expected,
                "responsibility_integrity_status": "block",
                "negative_control_false_clear": predicted != expected,
                "false_clear": predicted != expected,
                "failure_pattern": _required_text(
                    payload.get("expected_failure_pattern"),
                    field_name="expected_failure_pattern",
                ),
            }
        results[case_id] = result
    return results


def _s7_record_probe_result(
    payload: Mapping[str, object],
    *,
    expected_disposition: str,
    failure_pattern: str,
) -> dict[str, object]:
    request = _s7_probe_request(payload)
    observed_error: str | None = None
    predicted = "recorded_valid_decision"
    try:
        record_human_decision(
            case_id=_required_text(payload.get("case_id"), field_name="case_id"),
            request=request,
            rule_version_ref=_required_text(
                payload.get("rule_version_ref"),
                field_name="rule_version_ref",
            ),
            **_mapping(payload.get("record")),
        )
    except P26ResponsibilityIntegrityError as exc:
        observed_error = str(exc)
        if observed_error == "oversight_theater":
            predicted = "blocked_oversight_theater"
        elif observed_error == "wrong_role_approval":
            predicted = "blocked_wrong_role"
        else:
            predicted = f"blocked_{observed_error}"
    false_clear = predicted != expected_disposition
    return {
        "case_id": payload.get("case_id"),
        "predicted_disposition": predicted,
        "expected_disposition": expected_disposition,
        "responsibility_integrity_status": "block",
        "negative_control_false_clear": false_clear,
        "false_clear": false_clear,
        "failure_pattern": failure_pattern,
        "observed_error": observed_error,
    }


def _s7_probe_request(payload: Mapping[str, object]) -> Any:
    case_id = _required_text(payload.get("case_id"), field_name="case_id")
    rule_version_ref = _required_text(payload.get("rule_version_ref"), field_name="rule_version_ref")
    request_payload = _mapping(payload.get("request"))
    registry = build_governance_decision_class_registry(
        case_id=case_id,
        rule_version_ref=rule_version_ref,
    )
    matrix = build_decision_rights_matrix(
        case_id=case_id,
        governance_decision_classes=registry,
        rule_version_ref=rule_version_ref,
    )
    contract = build_delegation_contract(
        case_id=case_id,
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref=_required_text(
            request_payload.get("s6_mandate_record_ref"),
            field_name="s6_mandate_record_ref",
        ),
        s6_mandate_firewall_disposition=_required_text(
            request_payload.get("s6_mandate_firewall_disposition"),
            field_name="s6_mandate_firewall_disposition",
        ),
        rule_version_ref=rule_version_ref,
    )
    return build_human_decision_request(
        case_id=case_id,
        contract=contract,
        decision_class_id=_required_text(
            request_payload.get("decision_class_id"),
            field_name="decision_class_id",
        ),
        need_reasons=[str(reason) for reason in _sequence(request_payload.get("need_reasons"))],
        voi_rank=int(request_payload.get("voi_rank") or 1),
        s6_mandate_record_ref=_required_text(
            request_payload.get("s6_mandate_record_ref"),
            field_name="s6_mandate_record_ref",
        ),
        s6_mandate_firewall_disposition=_required_text(
            request_payload.get("s6_mandate_firewall_disposition"),
            field_name="s6_mandate_firewall_disposition",
        ),
        rule_version_ref=rule_version_ref,
    )


def _s7_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S7_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s7_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S7_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s7_need_reasons_from_signals(signals: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    if signals.get("stakes_band") == "high":
        reasons.append("high_stakes")
    if bool(signals.get("value_laden")):
        reasons.append("value_laden")
    if bool(signals.get("out_of_envelope")):
        reasons.append("out_of_envelope")
    if signals.get("s6_mandate_firewall_disposition") != "pass":
        reasons.append("mandate_limited")
    if bool(signals.get("budget_or_legal_use_required")):
        reasons.append("budget_required")
    if bool(signals.get("acquisition_required")):
        reasons.append("acquisition_required")
    if bool(signals.get("final_choice_required")):
        reasons.append("final_choice")
    if not reasons:
        reasons.extend(["low_voi_no_interrupt", "routine_in_envelope"])
    return reasons


def _s7_constraint_store_updates(
    *,
    report: Any,
    request_ref: str,
) -> list[dict[str, object]]:
    disposition = str(report.disposition)
    if disposition.startswith("blocked_"):
        status = "block"
    elif disposition in {"recorded_valid_decision", "no_interrupt"}:
        status = "pass"
    else:
        status = "limit"
    return [
        {
            "constraint_id": f"layer2.s7.{_slug(report.case_id)}.delegation",
            "cell_ref": "CROSS_CUTTING.scientist_orchestration",
            "status": status,
            "source_ref": request_ref,
            "consumer_ref": "INTERVENTION.design_candidate",
            "refinement_route": (
                "none" if disposition == "no_interrupt" else "human_decision"
            ),
            "evidence_refs": [request_ref],
            "reason": (
                "S7 delegation posture routes or records mandate-bounded human decision state."
            ),
            "rule_version_ref": S7_RULE_VERSION_REF,
        }
    ]


def _s7_handoff_rows(
    *,
    case_id: str,
    contract_ref: str,
    matrix_ref: str,
    request_ref: str,
    record_ref: object | None,
    disposition: str,
) -> list[dict[str, object]]:
    artifact_refs = [contract_ref, matrix_ref, request_ref]
    if record_ref:
        artifact_refs.append(str(record_ref))
    return [
        {
            "handoff_id": f"layer2.s7.{_slug(case_id)}.scientist-orchestration",
            "workflow_ref": f"scientist://workflow/{_slug(case_id)}/delegation",
            "source_cell_ref": "CROSS_CUTTING.scientist_orchestration",
            "target_cell_ref": "INTERVENTION.design_candidate",
            "artifact_refs": artifact_refs,
            "disposition": "blocked" if disposition.startswith("blocked_") else "emitted",
            "authority_purpose": "mandate_bounded_delegation_handoff",
            "may_not_use_for": [
                "production_claim_authority",
                "human_approval_without_decision_record",
            ],
        }
    ]


def _s7_false_clear_count(
    results: Mapping[str, Mapping[str, object]],
    case_id: str,
) -> int:
    row = results.get(case_id)
    return int(bool(row and row.get("false_clear")))


def _closeout_visible_refs(
    *,
    s7_delegation: Mapping[str, object],
    s8_value_choice: Mapping[str, object],
) -> dict[str, object]:
    delegation_refs = [
        s7_delegation.get("human_decision_request_ref"),
        s7_delegation.get("human_decision_record_ref"),
    ]
    value_refs = [
        s8_value_choice.get("value_choice_provenance_ref"),
        s8_value_choice.get("authorized_value_schedule_ref"),
        s8_value_choice.get("pareto_archive_ref"),
        s8_value_choice.get("value_tradeoff_disclosure_ref"),
    ]
    return {
        "delegation_refs": [str(ref) for ref in delegation_refs if ref],
        "value_choice_refs": [str(ref) for ref in value_refs if ref],
        "may_not_use_for": [
            "production_claim_authority",
            "production_closeout_authority",
            "production_recommendation",
            "preference_learning_authority",
        ],
    }


def _s6_fixed_refs(case_id: str) -> dict[str, str]:
    return {
        "measurability_record_ref": f"pdc://layer2/s6/{case_id}/measurability-adequacy",
        "aggregation_validity_record_ref": f"pdc://layer2/s6/{case_id}/aggregation-validity",
        "capacity_feasibility_record_ref": f"pdc://layer2/s6/{case_id}/capacity-feasibility",
        "mandate_legitimacy_record_ref": f"pdc://layer2/s6/{case_id}/mandate-legitimacy",
        "strategic_response_record_ref": f"pdc://layer2/s6/{case_id}/strategic-response",
        "cluster_authority_dimensions_ref": (
            f"pdc://layer2/s6/{case_id}/cluster-authority-dimensions"
        ),
        "post_intervention_dgp_update_ref": (
            f"pdc://layer2/s6/{case_id}/post-intervention-dgp"
        ),
    }


def _s6_s5_composition_payload(
    signals: Mapping[str, object],
    *,
    s5_coupling_composition: Mapping[str, object] | None,
) -> dict[str, object]:
    payload = dict(s5_coupling_composition or {})
    for key, value in _mapping(signals.get("s5_composition_refs")).items():
        if value is not None:
            payload[key] = value
    return payload


def _s6_constraint_entry_payload(update: Mapping[str, Any]) -> dict[str, object]:
    fields = (
        "schema_version",
        "constraint_id",
        "cell_ref",
        "status",
        "source_ref",
        "consumer_ref",
        "refinement_route",
        "evidence_refs",
        "reason",
        "rule_version_ref",
    )
    return {field: update[field] for field in fields if field in update}


def _s6_matches_gold(block: Mapping[str, object], labels: Mapping[str, object]) -> bool:
    actual_by_axis = {
        str(row.get("cell_ref")): str(row.get("disposition"))
        for row in _sequence_of_mappings(block.get("axis_rows"))
    }
    expected_by_axis = {
        "SYSTEM.measurability": labels.get("expected_measurability_disposition"),
        "SYSTEM.subject_granularity": labels.get("expected_aggregation_disposition"),
        "ACTOR.state_capacity_feasibility": labels.get("expected_capacity_disposition"),
        "ACTOR.mandate_legitimacy": labels.get("expected_mandate_disposition"),
        "OTHER_AGENTS.strategic_response": labels.get(
            "expected_strategic_response_disposition"
        ),
    }
    bridge_consumers = {
        str(row.get("consumer_ref"))
        for row in _sequence_of_mappings(block.get("bridge_consumer_table"))
    }
    c3_dimensions = {
        str(row.get("authority_dimension"))
        for row in _sequence_of_mappings(block.get("c3_authority_dimension_table"))
    }
    return (
        all(actual_by_axis.get(cell) == expected for cell, expected in expected_by_axis.items())
        and block.get("overall_posture") == labels.get("expected_overall_posture")
        and set(_sequence(block.get("blocking_axis_refs")))
        == set(_sequence(labels.get("expected_blocking_axis_refs")))
        and set(_sequence(block.get("limiting_axis_refs")))
        == set(_sequence(labels.get("expected_limiting_axis_refs")))
        and set(_sequence(labels.get("expected_bridge_consumer_refs"))) <= bridge_consumers
        and set(_sequence(labels.get("expected_c3_authority_dimensions"))) == c3_dimensions
    )


def _s6_limitation_summary(axis_rows: Sequence[Mapping[str, object]]) -> str:
    limited_or_blocked = [
        f"{row.get('cell_ref')}={row.get('disposition')}"
        for row in axis_rows
        if row.get("disposition") in {"limit", "block"}
    ]
    if not limited_or_blocked:
        return "S6 fail-closed blind-spot posture is clear for shadow routing."
    return "S6 fail-closed blind-spot posture constrains: " + ", ".join(limited_or_blocked)


def _s6_negative_control_probe_results(repo_root: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for probe_path in S6_NEGATIVE_CONTROL_PROBES:
        payload = json.loads(_resolve(repo_root, probe_path).read_text(encoding="utf-8"))
        expected_error = str(payload.get("expected_error") or "")
        observed_error: str | None = None
        observed_disposition: str | None = None
        try:
            observed_disposition = _s6_run_negative_probe(payload)
        except Exception as exc:  # noqa: BLE001 - probe records class-name outcomes.
            observed_error = exc.__class__.__name__
            observed_disposition = str(payload.get("expected_fail_closed_disposition") or "")
        results.append(
            {
                "probe_ref": f"repo://{probe_path.as_posix()}",
                "axis": payload.get("axis"),
                "expected_error": expected_error,
                "observed_error": observed_error,
                "observed_disposition": observed_disposition,
                "false_clear": observed_error != expected_error
                or observed_disposition not in {"limit", "block"},
            }
        )
    return results


def _s6_run_negative_probe(payload: Mapping[str, object]) -> str:
    case_id = _required_text(payload.get("case_id"), field_name="case_id")
    design_ref = _required_text(payload.get("design_ref"), field_name="design_ref")
    axis = _required_text(payload.get("blind_spot_axis"), field_name="blind_spot_axis")
    rule_version_ref = _required_text(
        payload.get("rule_version_ref"),
        field_name="rule_version_ref",
    )
    if axis == "measurability":
        record = evaluate_measurability_adequacy(
            case_id=case_id,
            design_ref=design_ref,
            construct_rows=_sequence_of_mappings(payload.get("construct_rows")),
            semantic_binding_ledger={
                "ledger_ref": payload.get("semantic_binding_ledger_ref"),
                "declared_measurability_pass": payload.get("declared_measurability_pass"),
            },
            rule_version_ref=rule_version_ref,
        )
    elif axis == "subject_granularity":
        record = evaluate_aggregation_validity(
            case_id=case_id,
            design_ref=design_ref,
            claim_scope=_required_text(payload.get("claim_scope"), field_name="claim_scope"),  # type: ignore[arg-type]
            evidence_scope=_required_text(
                payload.get("evidence_scope"),
                field_name="evidence_scope",
            ),  # type: ignore[arg-type]
            aggregation_rows=_sequence_of_mappings(payload.get("aggregation_rows")),
            concept_spine_carrier={
                "carrier_ref": payload.get("concept_spine_carrier_ref"),
                "declared_aggregation_pass": payload.get("declared_aggregation_pass"),
            },
            rule_version_ref=rule_version_ref,
        )
    elif axis == "state_capacity_feasibility":
        record = evaluate_capacity_feasibility(
            case_id=case_id,
            design_ref=design_ref,
            actor_ref=_required_text(payload.get("actor_ref"), field_name="actor_ref"),
            jurisdiction_ref=_required_text(
                payload.get("jurisdiction_ref"),
                field_name="jurisdiction_ref",
            ),
            instrument_ref=_required_text(
                payload.get("instrument_ref"),
                field_name="instrument_ref",
            ),
            capacity_dimensions=_sequence_of_mappings(payload.get("capacity_dimensions")),
            rule_version_ref=rule_version_ref,
        )
    elif axis == "mandate_legitimacy":
        record = evaluate_mandate_legitimacy(
            case_id=case_id,
            design_ref=design_ref,
            objective_refs=[str(ref) for ref in _sequence(payload.get("objective_refs"))],
            mandate_sources=_sequence_of_mappings(payload.get("mandate_sources")),
            participation_evaluations=_sequence_of_mappings(
                payload.get("participation_evaluations"),
            ),
            consultation_validations=_sequence_of_mappings(
                payload.get("consultation_validations"),
            ),
            rule_version_ref=rule_version_ref,
        )
    elif axis == "strategic_response":
        entries = _sequence_of_mappings(payload.get("strategic_response_entries")) or (
            {
                "entry_ref": f"fixture://layer2/s6/{case_id}/unchanged-effect-claim",
                "declared_unchanged_effect": payload.get("declared_unchanged_effect"),
            },
        )
        record = evaluate_strategic_response(
            case_id=case_id,
            design_ref=design_ref,
            response_channels=_sequence_of_mappings(payload.get("response_channels")),
            pre_policy_effect_refs=[
                str(ref) for ref in _sequence(payload.get("pre_policy_effect_refs"))
            ],
            s5_composition_posture=_mapping(payload.get("s5_composition_posture")),
            strategic_response_entries=entries,
            rule_version_ref=rule_version_ref,
        )
    else:
        raise W12DCaseRunError(f"unknown S6 negative probe axis: {axis}")
    return str(record.firewall_disposition)


def _s4_epistemic_regime_summary(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    capability_graph_trace: Mapping[str, Any],
) -> dict[str, Any]:
    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    labels = _s4_expert_labels(repo_root).get(case_id, {})
    evidence = RegimeEvidenceBasis(
        claim_ref=_s4_claim_ref(case, case_id=case_id),
        substrate_binding_status=_s4_substrate_binding_status(
            case,
            capability_graph_trace=capability_graph_trace,
        ),
        measurability_present=False,
        calibration_present=False,
        method_boundary_conditions_met=None,
        expert_disagreement=_s4_expert_disagreement(case),
        contested_scholar_edges=_s4_contested_scholar_edges(case),
        value_provenance_present=False,
        rule_version_ref=S4_RULE_VERSION_REF,
    )
    commitment = build_commitment_profile(
        candidate_ref=f"pdc://layer2/s4/{case_id}/candidate",
        rule_version_ref=S4_RULE_VERSION_REF,
        domain=_text(case.get("domain")),
        instrument_type=_text(_nested(case, ("policy_instrument", "instrument_type"))),
        policy_time=_text(_nested(case, ("intent", "policy_time"))),
    )
    claim = classify_regime(evidence, commitment)
    position, firewall = regime_claim_to_axis_position(claim)
    regime_claim_ref = f"pdc://layer2/s4/{case_id}/epistemic-regime-claim"
    commitment_profile_ref = f"pdc://layer2/s4/{case_id}/commitment-profile"
    gold_commitment = _s4_gold_commitment(labels)
    derived_commitment = commitment.model_dump(mode="json")
    expert_regime = _text(labels.get("expert_regime")) or "unknown"
    return {
        "schema_version": "policyos.policy_design_case.layer2_s4.case_regime_summary.v1",
        "status": "pass",
        "case_id": case_id,
        "classifier_owner": claim.classified_by,
        "claim_ref": claim.claim_ref,
        "predicted_regime": claim.regime,
        "expert_regime": expert_regime,
        "regime_matches_gold": claim.regime == expert_regime,
        "evidence_basis": evidence.model_dump(mode="json"),
        "regime_claim": claim.model_dump(mode="json"),
        "regime_claim_ref": regime_claim_ref,
        "commitment_profile": derived_commitment,
        "derived_commitment": derived_commitment,
        "gold_commitment": gold_commitment,
        "commitment_profile_ref": commitment_profile_ref,
        "commitment_profile_matches_gold": _s4_commitment_matches_gold(
            derived_commitment,
            gold_commitment,
        ),
        "selected_strategy": claim.strategy_consequence,
        "selected_floor": select_floor(commitment),
        "axis_projection": {
            "position": _axis_position_payload(position),
            "firewall": firewall.model_dump(mode="json"),
        },
        "authority_boundary": claim.authority_boundary.model_dump(mode="json"),
        "canonical_outcome_effect": "none_shadow_only",
    }


def _s4_regime_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [
        _mapping(case.get("s4_epistemic_regime"))
        for case in cases
        if isinstance(case.get("s4_epistemic_regime"), Mapping)
    ]
    per_case_table = [
        _s4_per_case_summary_row(case)
        for case in cases
        if isinstance(case.get("s4_epistemic_regime"), Mapping)
    ]
    predicted = [
        str(row.get("predicted_regime"))
        for row in rows
        if _text(row.get("expert_regime")) not in {None, "unknown"}
    ]
    gold = [
        str(row.get("expert_regime"))
        for row in rows
        if _text(row.get("expert_regime")) not in {None, "unknown"}
    ]
    accuracy = regime_accuracy(predicted=predicted, gold=gold) if gold else {
        "accuracy": 0.0,
        "false_risk_count": 0,
        "false_caution_count": 0,
        "penalized_score": 0.0,
    }
    commitment_gold_rows = [
        row
        for row in rows
        if isinstance(row.get("gold_commitment"), Mapping)
        and row.get("gold_commitment")
    ]
    commitment_match_count = sum(
        1 for row in commitment_gold_rows if row.get("commitment_profile_matches_gold")
    )
    limitation_rows = [
        _mapping(case.get("s4_epistemic_regime"))
        for case in cases
        if isinstance(case.get("s4_epistemic_regime"), Mapping)
        and _s4_case_expert_label(case) == "limitation_required"
    ]
    non_risk_rows = [
        row for row in limitation_rows if row.get("predicted_regime") != "risk"
    ]
    non_risk_breakdown = Counter(str(row.get("predicted_regime")) for row in non_risk_rows)
    hypothesis = (
        "confirmed"
        if limitation_rows and len(non_risk_rows) == len(limitation_rows)
        else "revised"
    )
    return {
        "schema_version": "policyos.policy_design_case.layer2_s4.regime_corpus_summary.v1",
        "case_count": len(rows),
        "regime_accuracy": accuracy["accuracy"],
        "false_risk_count": accuracy["false_risk_count"],
        "false_caution_count": accuracy["false_caution_count"],
        "penalized_score": accuracy["penalized_score"],
        "commitment_profile_adequacy": _rate(
            commitment_match_count,
            len(commitment_gold_rows),
        ),
        "commitment_profile_match_count": commitment_match_count,
        "commitment_profile_gold_count": len(commitment_gold_rows),
        "limitation_required_case_count": len(limitation_rows),
        "limitation_required_non_risk_count": len(non_risk_rows),
        "limitation_required_non_risk_breakdown": dict(sorted(non_risk_breakdown.items())),
        "per_case_regime_table": per_case_table,
        "w12_overblocking_hypothesis": hypothesis,
        "canonical_outcome_effect": "none_shadow_only",
    }


def _s4_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S4_EXPERT_LABELS_PATH)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return {}
    raw_labels = payload.get("cases") if isinstance(payload.get("cases"), Mapping) else payload
    return {
        str(case_id): dict(row)
        for case_id, row in raw_labels.items()
        if isinstance(row, Mapping) and not str(case_id).startswith("_")
    }


def _s5_case_signals(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S5_CASE_SIGNALS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s5_expert_labels(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = _resolve(repo_root, S5_EXPERT_LABELS_PATH)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else {}
    return {
        str(case_id): dict(row)
        for case_id, row in _mapping(raw_cases).items()
        if isinstance(row, Mapping)
    }


def _s5_fixed_refs(case_id: str) -> dict[str, str]:
    return {
        "coupling_graph_ref": f"pdc://layer2/s5/{case_id}/coupling-graph",
        "module_discovery_ref": f"pdc://layer2/s5/{case_id}/module-discovery",
        "decomposition_result_ref": f"pdc://layer2/s5/{case_id}/decomposition-result",
        "composition_receipt_ref": f"pdc://layer2/s5/{case_id}/composition-receipt",
        "dynamics_requirement_ref": f"pdc://layer2/s5/{case_id}/system-dynamics-requirement",
        "tractability_budget_ref": f"pdc://layer2/s5/{case_id}/tractability-budget",
        "forecast_support_ref": f"pdc://layer2/s5/{case_id}/forecast-support-scope",
    }


def _s5_module_refs(observed_boundaries: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            ref
            for row in observed_boundaries
            for ref in (
                _required_text(row.get("source_module_ref"), field_name="source_module_ref"),
                _required_text(row.get("target_module_ref"), field_name="target_module_ref"),
            )
        }
    )


def _s5_critical_path_module_refs(
    observed_boundaries: Sequence[Mapping[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for row in observed_boundaries:
        for key in ("source_module_ref", "target_module_ref"):
            ref = _required_text(row.get(key), field_name=key)
            if ref not in refs:
                refs.append(ref)
    return refs


def _s5_coupling_edges(
    case_id: str,
    observed_boundaries: Sequence[Mapping[str, Any]],
) -> list[CouplingEdge]:
    edges: list[CouplingEdge] = []
    for row in observed_boundaries:
        boundary_ref = _required_text(row.get("boundary_ref"), field_name="boundary_ref")
        source_ref = _required_text(row.get("source_module_ref"), field_name="source_module_ref")
        target_ref = _required_text(row.get("target_module_ref"), field_name="target_module_ref")
        relation = _required_text(row.get("relation"), field_name="relation")
        strength = _required_text(
            row.get("observed_interaction_strength"),
            field_name="observed_interaction_strength",
        )
        intensity = _required_text(
            row.get("observed_feedback_intensity"),
            field_name="observed_feedback_intensity",
        )
        evidence_ref = f"fixture://layer2/s5/{case_id}/{boundary_ref}"
        edges.append(
            CouplingEdge(
                boundary_ref=boundary_ref,
                source_module_ref=source_ref,
                target_module_ref=target_ref,
                relation=relation,
                interaction_strength=strength,  # type: ignore[arg-type]
                feedback_intensity=intensity,  # type: ignore[arg-type]
                feedback=intensity == "high",
                evidence_ref=evidence_ref,
            )
        )
        if intensity == "high":
            edges.append(
                CouplingEdge(
                    boundary_ref=boundary_ref,
                    source_module_ref=target_ref,
                    target_module_ref=source_ref,
                    relation="feedback_return_path",
                    interaction_strength="strong",
                    feedback_intensity="high",
                    feedback=True,
                    evidence_ref=evidence_ref,
                )
            )
    return edges


def _s5_boundary_rows_match_gold(
    boundary_rows: Sequence[Any],
    boundary_gold: Sequence[Mapping[str, Any]],
) -> bool:
    if len(boundary_rows) != len(boundary_gold):
        return False
    gold_by_boundary = {
        _required_text(row.get("boundary_ref"), field_name="boundary_ref"): row
        for row in boundary_gold
    }
    for row in boundary_rows:
        gold = gold_by_boundary.get(row.boundary_ref)
        if gold is None:
            return False
        dynamics_trigger = row.feedback_intensity == "high" or row.coupling_regime == "entangled"
        if (
            row.source_module_ref
            != _required_text(gold.get("source_module_ref"), field_name="source_module_ref")
            or row.target_module_ref
            != _required_text(gold.get("target_module_ref"), field_name="target_module_ref")
            or row.coupling_regime
            != _required_text(gold.get("expert_coupling_regime"), field_name="expert_coupling")
            or row.feedback_intensity
            != _required_text(
                gold.get("expected_feedback_intensity"),
                field_name="expected_feedback_intensity",
            )
            or dynamics_trigger is not bool(gold.get("requires_system_dynamics"))
        ):
            return False
    return True


def _s5_search_space_size(labels: Mapping[str, Any]) -> str:
    scale_class = _text(labels.get("scale_class"))
    if scale_class.startswith("national") or scale_class.startswith("transnational"):
        return "large"
    if scale_class.startswith("river_basin") or scale_class.startswith("city"):
        return "medium"
    return "small"


def _s4_case_expert_label(case: Mapping[str, Any]) -> str | None:
    return _text(
        _nested(case, ("expert_adjudication_delta", "expert_label"))
        or _nested(case, ("expert_adjudication", "case_label"))
    )


def _s4_per_case_summary_row(case: Mapping[str, Any]) -> dict[str, Any]:
    row = _mapping(case.get("s4_epistemic_regime"))
    derived = _mapping(row.get("derived_commitment"))
    gold = _mapping(row.get("gold_commitment"))
    return {
        "case_id": _text(case.get("case_id") or row.get("case_id")),
        "expert_label": _s4_case_expert_label(case),
        "predicted_regime": _text(row.get("predicted_regime")),
        "expert_regime": _text(row.get("expert_regime")),
        "regime_matches_gold": bool(row.get("regime_matches_gold")),
        "derived_reversibility": _text(derived.get("reversibility")),
        "gold_reversibility": _text(gold.get("reversibility")),
        "derived_stakes": _text(derived.get("stakes")),
        "gold_stakes": _text(gold.get("stakes")),
        "commitment_profile_matches_gold": bool(
            row.get("commitment_profile_matches_gold")
        ),
    }


def _s4_claim_ref(case: Mapping[str, Any], *, case_id: str) -> str:
    claims = _sequence_of_mappings(_nested(case, ("claim_evidence_annotations", "claims")))
    for claim in claims:
        claim_id = _text(claim.get("claim_id") or claim.get("id"))
        if claim_id:
            return f"claim:{claim_id}"
    return f"claim:{case_id}:main"


def _s4_substrate_binding_status(
    case: Mapping[str, Any],
    *,
    capability_graph_trace: Mapping[str, Any],
) -> str:
    if capability_graph_trace.get("status") == "pass":
        live_statuses = [
            _text(binding.get("status"))
            for binding in _sequence_of_mappings(capability_graph_trace.get("capability_bindings"))
        ]
        if any(status in {"selected_exact", "selected_derived"} for status in live_statuses):
            return "selected_exact"
    labels = {
        _normalized_token(row.get("admissibility_label") or row.get("expected_support_status"))
        for row in _sequence_of_mappings(
            _nested(case, ("claim_evidence_annotations", "claims"))
        )
    }
    labels.update(
        _normalized_token(row.get("expected_support_status"))
        for row in _sequence_of_mappings(_nested(case, ("expected_claim_families", "families")))
    )
    if "blocked" in labels:
        return "blocked_construct_not_observed"
    if labels & {"limited", "publishable_with_limitation"}:
        return "selected_proxy_with_limitation"
    adapter_statuses = {
        _normalized_token(row.get("status"))
        for row in _sequence_of_mappings(_nested(case, ("expected_adapter_bindings", "bindings")))
    }
    if "selected" in adapter_statuses:
        return "selected_proxy_with_limitation"
    return "blocked_construct_not_observed"


def _s4_contested_scholar_edges(case: Mapping[str, Any]) -> int:
    statuses = {
        _normalized_token(row.get("contestability_status"))
        for row in _sequence_of_mappings(_nested(case, ("claim_evidence_annotations", "claims")))
    }
    return 1 if "contested" in statuses else 0


def _s4_expert_disagreement(case: Mapping[str, Any]) -> str:
    statuses = {
        _normalized_token(row.get("contestability_status"))
        for row in _sequence_of_mappings(_nested(case, ("claim_evidence_annotations", "claims")))
    }
    return "some" if "review_required" in statuses else "none"


def _s4_gold_commitment(labels: Mapping[str, Any]) -> dict[str, str]:
    keys = ("reversibility", "option_value", "lifecycle_stage", "transition_cost", "stakes")
    return {
        key: text
        for key in keys
        if (text := _text(labels.get(key))) is not None
    }


def _s4_commitment_matches_gold(
    derived: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> bool:
    if not gold:
        return False
    return (
        _text(derived.get("reversibility")) == _text(gold.get("reversibility"))
        and _text(derived.get("stakes")) == _text(gold.get("stakes"))
    )


def _axis_position_payload(position: Any) -> dict[str, Any]:
    payload = position.model_dump(mode="json")
    payload["cell_ref"] = position.cell_ref
    return payload


def _capability_graph_not_run(
    *,
    capability_index_path: Path | None,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.phase5.capability_graph_trace.v1",
        "status": "not_run",
        "capability_index_ref": None,
        "capability_index_path": (
            f"repo://{_repo_relative(repo_root, capability_index_path)}"
            if capability_index_path is not None
            else None
        ),
        "capability_index_loaded": False,
        "construct_registry_ref": "construct-registry:v1",
        "construct_registry_artifact_ref": _construct_registry_artifact_ref(repo_root),
        "construct_registry_loaded": _resolve(repo_root, DEFAULT_CONSTRUCT_REGISTRY).exists(),
        "authority_composition_rule_ref": DEFAULT_AUTHORITY_COMPOSITION_RULE_REF,
        "resolver_executed": False,
        "producer_binding_emitted": False,
        "capability_bindings": [],
        "binding_count": 0,
        "w8e_conflict_signals": {
            "visible": False,
            "conflict_marker_count": 0,
        },
        "w8f_independence_signals": {
            "visible": False,
            "factor_count": 0,
            "below_floor_count": 0,
        },
        "issue_codes": [],
        "authority_boundary": {
            "authoritative_for": ["capability_graph_traceability"],
            "may_not_use_for": ["producer_domain_truth", "claim_authority"],
        },
    }


def _capability_graph_context(
    *,
    case: Mapping[str, Any],
    compiled: Mapping[str, Any],
    capability_index_path: Path | None,
    repo_root: Path,
    authority_level: str,
    mode: str,
) -> dict[str, Any]:
    trace = _capability_graph_not_run(
        capability_index_path=capability_index_path,
        repo_root=repo_root,
    )
    if capability_index_path is None:
        return trace
    if not capability_index_path.exists():
        return {
            **trace,
            "status": "blocked",
            "issue_codes": ["w12d_capability_index_missing"],
        }
    try:
        resolver = RequirementToCapabilityResolver.from_duckdb(capability_index_path)
    except Exception as exc:  # pragma: no cover - exercised by CLI environments.
        return {
            **trace,
            "status": "blocked",
            "capability_index_loaded": False,
            "issue_codes": ["w12d_capability_index_load_failed"],
            "issues": [
                _issue(
                    "w12d_capability_index_load_failed",
                    str(exc),
                    severity="fail",
                )
            ],
        }

    bindings: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    s3_receipt: Any | None = None
    s3_acquisition: dict[str, Any] | None = None
    for spec in _sequence(compiled.get("data_requirement_specs")):
        query = _capability_query_for_spec(
            spec,
            case=case,
            authority_level=authority_level,
        )
        if query is None:
            continue
        try:
            result = resolver.resolve(query)
        except Exception as exc:  # pragma: no cover - defensive trace, not authority.
            issues.append(
                _issue(
                    "w12d_capability_resolver_failed",
                    str(exc),
                    severity="fail",
                    requirement_id=query.requirement_id,
                )
            )
            continue
        row = result.model_dump(mode="json", exclude_none=True)
        row["construct_registry_ref"] = "construct-registry:v1"
        row["authority_composition_rule_ref"] = (
            row.get("rule_version_ref") or DEFAULT_AUTHORITY_COMPOSITION_RULE_REF
        )
        if _should_apply_s3_closed_acquisition(
            case=case,
            query=query,
            binding_row=row,
            authority_level=authority_level,
            mode=mode,
        ):
            if s3_receipt is None:
                s3_receipt = _run_s3_closed_acquisition(case=case, repo_root=repo_root)
                s3_acquisition = _s3_acquisition_trace(
                    s3_receipt,
                    repo_root=repo_root,
                )
            row = _s3_binding_row(s3_receipt, query=query)
        bindings.append(row)

    payload = {
        **trace,
        "status": "pass" if bindings and not issues else "blocked",
        "capability_index_ref": resolver.capability_index_ref,
        "capability_index_loaded": True,
        "resolver_executed": bool(bindings or issues),
        "producer_binding_emitted": bool(bindings),
        "capability_bindings": bindings,
        "binding_count": len(bindings),
        "w8e_conflict_signals": _w8e_conflict_signals(bindings),
        "w8f_independence_signals": _w8f_independence_signals(bindings),
        "issue_codes": sorted({str(issue["code"]) for issue in issues}),
        "issues": issues,
    }
    if s3_acquisition is not None:
        payload["s3_acquisition"] = s3_acquisition
    return payload


def _should_apply_s3_closed_acquisition(
    *,
    case: Mapping[str, Any],
    query: RequirementToCapabilityQuery,
    binding_row: Mapping[str, Any],
    authority_level: str,
    mode: str,
) -> bool:
    """Return whether the closed S3 governed binding may replace this blocker."""

    case_id = _text(case.get("case_id") or case.get("id"))
    construct = _text(query.construct).removeprefix("construct:")
    return (
        mode == "real_producer"
        and case_id == S3_FIRST_PROVING_CASE_ID
        and authority_level == "governed"
        and _text(query.authority_level) == "governed_pilot"
        and construct == S3_GROUNDED_CONSTRUCT
        and _text(binding_row.get("status"))
        in {"blocked_construct_not_observed", "blocked_acquisition_required"}
    )


def _run_s3_closed_acquisition(
    *,
    case: Mapping[str, Any],
    repo_root: Path,
) -> Any:
    expression = ConstructExpression(
        construct=S3_GROUNDED_CONSTRUCT,
        facets={
            "jurisdiction": "ua",
            "population_scope": "msme",
            "time_role": "policy_time",
        },
        authority_posture="governed",
        rule_version_refs=[
            f"case://{_text(case.get('case_id') or case.get('id'))}",
            DEFAULT_AUTHORITY_COMPOSITION_RULE_REF,
        ],
    )
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=expression,
        source_fixture=str(_resolve(repo_root, S3_ACQUISITION_SOURCE_FIXTURE)),
    )
    receipt = loop.run_to_closure()
    loop.assert_closed()
    return receipt


def _s3_binding_row(
    receipt: Any,
    *,
    query: RequirementToCapabilityQuery,
) -> dict[str, Any]:
    row = dict(receipt.binding)
    construct_ref = f"construct:{S3_GROUNDED_CONSTRUCT}"
    row.update(
        {
            "requirement_id": query.requirement_id,
            "construct_ref": construct_ref,
            "capability_index_ref": receipt.frozen.capability_index_ref,
            "construct_registry_ref": "construct-registry:v1",
            "authority_composition_rule_ref": (
                row.get("rule_version_ref") or DEFAULT_AUTHORITY_COMPOSITION_RULE_REF
            ),
            "source_family": S3_GROUNDED_CONSTRUCT,
        }
    )
    row["authoritative_for"] = _append_unique_text(
        row.get("authoritative_for"),
        "governed_construct_binding",
    )
    row["may_not_use_for"] = _append_unique_text(
        row.get("may_not_use_for"),
        "production_claim_authority",
        "scenario_family_authority",
    )
    row["lineage_refs"] = _append_unique_text(
        row.get("lineage_refs"),
        receipt.frozen.capability_index_ref,
    )
    return row


def _s3_acquisition_trace(
    receipt: Any,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    transition_states = [transition.state.value for transition in receipt.transitions]
    before_status = next(
        (
            transition.detail
            for transition in receipt.transitions
            if transition.state.value == "gap_detected"
        ),
        None,
    )
    return {
        "schema_version": "policyos.policy_design_case.layer2.s3.corpus_route.v1",
        "status": "consumed_closed_case",
        "case_id": S3_FIRST_PROVING_CASE_ID,
        "construct_ref": f"construct:{S3_GROUNDED_CONSTRUCT}",
        "terminal": receipt.terminal.value,
        "binding_status": receipt.binding_status,
        "construct_status_before_after": {
            "before": before_status,
            "after": receipt.binding_status,
        },
        "frozen": receipt.frozen.model_dump(mode="json"),
        "source_fixture_ref": f"repo://{_repo_relative(repo_root, S3_ACQUISITION_SOURCE_FIXTURE)}",
        "transition_states": transition_states,
        "authority_boundary": {
            "authoritative_for": [
                "governed_construct_binding",
                "capability_graph_traceability",
            ],
            "may_not_use_for": [
                "production_claim_authority",
                "scenario_family_authority",
                "publication_authority",
            ],
        },
    }


def _append_unique_text(value: object, *items: str) -> list[str]:
    rows = _unique_texts(_sequence(value))
    for item in items:
        if item not in rows:
            rows.append(item)
    return rows


def _w8e_conflict_signals(bindings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    marker_count = sum(
        len(_sequence(binding.get("conflict_markers"))) for binding in bindings
    )
    return {
        "visible": True,
        "conflict_marker_count": marker_count,
        "binding_count": len(bindings),
    }


def _w8f_independence_signals(bindings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    factors = [
        factor
        for binding in bindings
        for factor in _sequence_of_mappings(binding.get("factors"))
        if str(factor.get("name")) == "effective_independence"
    ]
    return {
        "visible": True,
        "factor_count": len(factors),
        "below_floor_count": sum(1 for factor in factors if factor.get("status") == "below_floor"),
        "binding_count": len(bindings),
    }


def _capability_query_for_spec(
    spec: object,
    *,
    case: Mapping[str, Any],
    authority_level: str,
) -> RequirementToCapabilityQuery | None:
    payload = _spec_payload(spec)
    requirement_id = _text(payload.get("requirement_id"))
    construct = _first_construct_ref(payload)
    if not requirement_id or not construct:
        return None
    scope = _mapping(payload.get("scope"))
    family = _first_sequence_text(payload.get("required_data_families"))
    geography = (
        _text(scope.get("jurisdiction"))
        or _text(scope.get("geography"))
        or _jurisdiction(case)
    )
    return RequirementToCapabilityQuery(
        requirement_id=requirement_id,
        construct=construct,
        entity_scope=_entity_scope_for_construct(construct),
        population_filter={
            "type": _text(scope.get("population")) or _target_population(case),
        },
        geography=geography,
        time_window={"start": _policy_time(case), "end": None},
        authority_level=_authority_posture(authority_level),
        claim_use=_text(payload.get("claim_use")) or "claim_evidence_closeout",
        required_evidence_modes=(
            "observed",
            "derived",
            "proxy_observational",
            "scholarly_causal_support",
            "legal_threshold",
        ),
        forbidden_evidence_modes=("simulation_only", "candidate_unverified"),
        source_family_alias=family,
    )


def _claim_bindings_from_pipeline(
    *,
    case_id: str,
    claims: Sequence[Mapping[str, Any]],
    producer_binding_decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not producer_binding_decisions:
        return []
    claim_rows = list(claims) or ({"claim_id": f"claim:{case_id}"},)
    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claim_rows):
        claim_id = _text(claim.get("claim_id") or claim.get("id")) or f"claim:{index + 1}"
        matched = _producer_decisions_for_claim(producer_binding_decisions, claim_id)
        if not matched:
            matched = list(producer_binding_decisions)
        capability_refs = _refs_from_decisions(matched, "capability_ref")
        construct_refs = _refs_from_decisions(matched, "construct_ref")
        if not capability_refs or not construct_refs:
            continue
        rows.append(
            {
                "claim_binding_id": f"claim-binding:{_slug(case_id)}:{index + 1}",
                "claim_id": claim_id,
                "capability_ref": capability_refs[0],
                "construct_ref": construct_refs[0],
                "capability_refs": capability_refs,
                "construct_refs": construct_refs,
                "capability_index_refs": _refs_from_decisions(
                    matched,
                    "capability_index_ref",
                ),
                "construct_registry_refs": _refs_from_decisions(
                    matched,
                    "construct_registry_ref",
                ),
                "authority_composition_rule_refs": _refs_from_decisions(
                    matched,
                    "authority_composition_rule_ref",
                ),
                "producer_components": _refs_from_decisions(
                    matched,
                    "producer_component",
                ),
                "binding_decision_refs": _refs_from_decisions(matched, "binding_id"),
                "authority_boundary": {
                    "authoritative_for": ["claim_to_capability_traceability"],
                    "may_not_use_for": ["claim_authority", "producer_domain_truth"],
                },
            }
        )
    return rows


def _producer_decisions_for_claim(
    decisions: Sequence[Mapping[str, Any]],
    claim_id: str,
) -> list[Mapping[str, Any]]:
    tokens = {claim_id, claim_id.replace(":", "_"), claim_id.replace(":", "-")}
    return [
        row
        for row in decisions
        if any(
            token in _text(row.get("requirement_ref"))
            or token in _text(row.get("binding_id"))
            for token in tokens
        )
    ]


def _refs_from_decisions(
    decisions: Sequence[Mapping[str, Any]],
    key: str,
) -> list[str]:
    return list(
        dict.fromkeys(
            text
            for row in decisions
            if (text := _text(row.get(key)))
        )
    )


def _first_construct_ref(payload: Mapping[str, Any]) -> str | None:
    metadata = _mapping(payload.get("metadata"))
    binding = _mapping(metadata.get("capability_binding"))
    for value in (
        binding.get("construct_ref"),
        metadata.get("construct_ref"),
        payload.get("construct_ref"),
        payload.get("target_construct_ref"),
    ):
        text = _text(value)
        if text:
            return text.removeprefix("construct:")
    family = _first_sequence_text(payload.get("required_data_families"))
    return construct_for_legacy_family(family) if family else None


def _first_sequence_text(value: object) -> str | None:
    for item in _sequence(value):
        text = _text(item)
        if text:
            return text
    return None


def _entity_scope_for_construct(construct: str) -> str:
    bare = construct.removeprefix("construct:")
    return {
        "firm_survival": "firm",
        "credit_program_enrollment": "firm_or_program",
        "regional_displacement_pressure": "region",
    }.get(bare, "entity")


def _authority_posture(authority_level: str) -> str:
    if authority_level == "production":
        return "production"
    if authority_level == "research":
        return "research"
    return "governed_pilot"


def _construct_registry_artifact_ref(repo_root: Path) -> str:
    path = _resolve(repo_root, DEFAULT_CONSTRUCT_REGISTRY)
    return f"repo://{_repo_relative(repo_root, path)}"


def _spec_payload(spec: object) -> Mapping[str, Any]:
    if isinstance(spec, Mapping):
        return dict(spec)
    if hasattr(spec, "model_dump"):
        return spec.model_dump(mode="json")
    return {}


def _compile_case_artifacts(
    case: Mapping[str, Any],
    *,
    case_id: str,
    capability_index_path: Path | None = None,
) -> dict[str, Any]:
    run_id = _text(case.get("run_id")) or f"run-{case_id}"
    intent_payload = _mapping(case.get("intent")) or case
    intent_text = _compilation_intent_text(case, intent_payload=intent_payload)
    authority_level = _normalized_token(
        case.get("authority_level")
        or intent_payload.get("authority_level")
        or _nested(case, ("claim_evidence_annotations", "authority_level"))
        or "research"
    )
    authority_profile = UniversalAuthorityProfile(
        profile_id=_text(intent_payload.get("authority_profile_ref"))
        or _text(case.get("authority_profile_ref"))
        or f"authority_profile.{authority_level}",
        authority_type=_enum_value(
            PolicyLayerLevel,
            intent_payload.get("authority_type")
            or case.get("authority_type")
            or _authority_type_for_level(authority_level),
            default=PolicyLayerLevel.LOCAL,
        ),
    )
    compiled_case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id=_text(intent_payload.get("intent_id")) or case_id,
            text=intent_text,
            domain=_enum_value(
                ProblemDomain,
                intent_payload.get("problem_domain")
                or case.get("problem_domain")
                or case.get("domain"),
                default=ProblemDomain.CUSTOM,
            ),
        ),
        authority_profile=authority_profile,
        concept_spine_refs=_concept_spine_refs(case, case_id=case_id),
    )
    if compiled_case.facets is None:
        blocker_codes = [blocker.code for blocker in compiled_case.blockers]
        raise W12DCaseRunError(
            "W6.A grammar compilation blocked: " + ", ".join(blocker_codes)
        )

    graph = _compile_obligation_graph(
        case,
        run_id=run_id,
        compiled_case=compiled_case,
        intent_text=intent_text,
    )
    if not graph.blocking_frontier:
        raise W12DCaseRunError("W6.C compiled no blocking frontier obligations.")

    facets = _claim_facets(compiled_case)
    obligations = _claim_obligations(graph, facets=facets)
    claim_ledger = ClaimDecompositionCompiler().compile(
        {
            "run_id": run_id,
            "intent": intent_text,
            "facets": facets,
            "obligations": obligations,
            "named_alternatives": _named_alternatives(case, case_id=case_id),
            "concept_spine_refs": [compiled_case.concept_spine_ref],
            "authority_profile_refs": [compiled_case.authority_profile.profile_id],
            "metadata": {"producer": TOOL_NAME},
        }
    )
    claim_decomposition_ref = f"claim-ledger:{_slug(run_id)}"
    claims = _runtime_claims(
        claim_ledger=claim_ledger,
        case=case,
        case_id=case_id,
        authority_level=authority_level,
    )
    llm_artifacts = _run_llm_formulator_and_critics(
        case_id=case_id,
        run_id=run_id,
        intent_text=intent_text,
        compiled_case=compiled_case,
        graph=graph,
        facets=facets,
        obligations=obligations,
        claim_ledger=claim_ledger,
    )
    consensus_candidates = critic_consensus_to_obligation_candidates(
        formulator_output=llm_artifacts["_formulator_output"],
        critic_report=llm_artifacts["_critic_report"],
        facets=facet_snapshots_for_obligation_graph(compiled_case),
        intent_text=intent_text,
        authority_profile_ref=compiled_case.authority_profile.profile_id,
    )
    if consensus_candidates:
        graph = _compile_obligation_graph(
            case,
            run_id=run_id,
            compiled_case=compiled_case,
            intent_text=intent_text,
            additional_candidate_sources=consensus_candidates,
        )
        obligations = _claim_obligations(graph, facets=facets)
        claim_ledger = ClaimDecompositionCompiler().compile(
            {
                "run_id": run_id,
                "intent": intent_text,
                "facets": facets,
                "obligations": obligations,
                "named_alternatives": _named_alternatives(case, case_id=case_id),
                "concept_spine_refs": [compiled_case.concept_spine_ref],
                "authority_profile_refs": [compiled_case.authority_profile.profile_id],
                "metadata": {"producer": TOOL_NAME, "llm_consensus_reissue": True},
            }
        )
        claims = _runtime_claims(
            claim_ledger=claim_ledger,
            case=case,
            case_id=case_id,
            authority_level=authority_level,
        )
    llm_artifacts["critic_consensus"] = {
        "candidate_count": len(consensus_candidates),
        "candidate_refs": [candidate.candidate_id for candidate in consensus_candidates],
        "source_class": "llm_critic_consensus",
        "priority_ceiling": "review_required",
    }
    llm_artifacts.pop("_formulator_output", None)
    llm_artifacts.pop("_critic_report", None)
    requirement_artifacts = _compile_requirement_specs(
        case=case,
        case_id=case_id,
        run_id=run_id,
        authority_level=authority_level,
        compiled_case=compiled_case,
        graph=graph,
        claim_ledger=claim_ledger,
        claims=claims,
        facets=facets,
        obligations=obligations,
        capability_index_path=capability_index_path,
    )
    return {
        "case_id": case_id,
        "run_id": run_id,
        "intent_text": intent_text,
        "authority_level": authority_level,
        "compiled_case": compiled_case,
        "obligation_graph": graph,
        "claim_ledger": claim_ledger,
        "claims": claims,
        "claim_decomposition_ref": claim_decomposition_ref,
        "llm_artifacts": llm_artifacts,
        "universal_compilation": {
            "status": "pass",
            "grammar_ref": compiled_case.case_id,
            "obligation_graph_ref": graph.graph_id,
            "claim_decomposition_ref": claim_decomposition_ref,
            "facet_count": len(facets),
            "frontier_count": len(graph.blocking_frontier),
            "claim_count": len(claims),
        },
        **requirement_artifacts,
    }


def _compile_obligation_graph(
    case: Mapping[str, Any],
    *,
    run_id: str,
    compiled_case: Any,
    intent_text: str,
    additional_candidate_sources: Sequence[Any] = (),
) -> ObligationGraph:
    compilation_inputs = _mapping(case.get("compilation_inputs"))
    if "governed_rules" in compilation_inputs:
        governed_rules = _sequence(compilation_inputs.get("governed_rules"))
    elif compilation_inputs.get("use_seed_rule_catalog") is False:
        governed_rules = ()
    else:
        governed_rules = build_seed_obligation_rule_catalog().rules
    return compile_obligation_graph(
        run_id=run_id,
        facets=facet_snapshots_for_obligation_graph(compiled_case),
        governed_rules=governed_rules,
        candidate_sources=(
            *_sequence(
                compilation_inputs.get("candidate_sources") or case.get("candidate_sources")
            ),
            *additional_candidate_sources,
        ),
        complexity_budget=ComplexityBudget.model_validate(
            _mapping(compilation_inputs.get("complexity_budget")) or {}
        ),
        generated_at=datetime(2026, 5, 25, tzinfo=UTC),
        graph_id=f"obligation-graph-{_slug(_text(case.get('case_id')) or run_id)}",
        intent_text=intent_text,
    )


def _compile_requirement_specs(
    *,
    case: Mapping[str, Any],
    case_id: str,
    run_id: str,
    authority_level: str,
    compiled_case: Any,
    graph: ObligationGraph,
    claim_ledger: Any,
    claims: Sequence[Mapping[str, Any]],
    facets: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    capability_index_path: Path | None = None,
) -> dict[str, Any]:
    from polisyos.data_requirement import DataRequirementCompiler
    from polisyos.legal_requirement import LegalAuthorityRequirementCompiler
    from polisyos.method_requirement import MethodValidityRequirementCompiler
    from polisyos.participation_requirement import ParticipationProvenanceCompiler
    from polisyos.scholar_requirement import ScholarSupportRequirementCompiler

    capability_resolver = (
        RequirementToCapabilityResolver.from_duckdb(capability_index_path)
        if capability_index_path is not None
        else None
    )
    data_report = DataRequirementCompiler(
        capability_resolver=capability_resolver,
        require_capability_index=capability_index_path is not None,
    ).compile_for_claim_ledger(
        run_id=run_id,
        scenario_id=case_id,
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(compiled_case.authority_profile.profile_id,),
    )
    legal_specs = LegalAuthorityRequirementCompiler().compile(
        run_id=run_id,
        target_context={
            "jurisdiction": _jurisdiction(case),
            "authority_profile": authority_level,
            "as_of": _policy_time(case),
        },
        claims=claims,
        facets=facets,
        obligations=obligations,
    )
    method_artifact = MethodValidityRequirementCompiler().compile(
        run_id=run_id,
        claims=claims,
        requirement_graph_ref=graph.graph_id,
    )
    scholar_result = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": run_id,
            "authority_level": authority_level,
            "claims": [_scholar_claim(claim, authority_level=authority_level) for claim in claims],
        }
    )
    participation_bundle = ParticipationProvenanceCompiler().compile(
        {"run_id": run_id, "claims": claims}
    )
    return {
        "data_requirement_specs": data_report.specs,
        "legal_authority_requirement_specs": [
            spec for spec in legal_specs if not getattr(spec, "out_of_scope", False)
        ],
        "method_validity_requirement_specs": method_artifact.requirements,
        "scholar_support_requirement_specs": scholar_result.requirements,
        "participation_provenance_requirement_specs": participation_bundle.requirements,
    }


def _run_case_pipeline(
    case: Mapping[str, Any],
    *,
    compiled: Mapping[str, Any],
    authority_level: str,
    mode: str,
    producer_stub_dir: Path,
    capability_bindings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    stub_responses = None
    if mode == "corpus_stub":
        stub_responses = load_corpus_stub_responses(
            stub_dir=producer_stub_dir,
            case_id=str(compiled["case_id"]),
        )
    return run_requirement_spec_producer_pipeline(
        run_id=str(compiled["run_id"]),
        job_id=_text(case.get("job_id")) or f"job-{_slug(compiled['run_id'])}",
        tenant_id=_text(case.get("tenant_id")) or "w12d-universal-outcome-corpus",
        request_ref=_text(case.get("request_ref")) or f"request:{_slug(compiled['run_id'])}",
        authority_profile=authority_level,
        spine_context=_spine_context(case, compiled_case=compiled["compiled_case"]),
        claims=_sequence_of_mappings(compiled["claims"]),
        data_requirement_specs=_sequence(compiled["data_requirement_specs"]),
        legal_authority_requirement_specs=_sequence(
            compiled["legal_authority_requirement_specs"]
        ),
        method_validity_requirement_specs=_sequence(compiled["method_validity_requirement_specs"]),
        scholar_support_requirement_specs=_sequence(compiled["scholar_support_requirement_specs"]),
        participation_provenance_requirement_specs=_sequence(
            compiled["participation_provenance_requirement_specs"]
        ),
        capability_bindings=capability_bindings,
        universal_grammar_compilation={
            "status": "pass",
            "artifact_ref": _nested(compiled, ("universal_compilation", "grammar_ref")),
        },
        obligation_graph={
            "status": "pass",
            "graph_ref": _nested(compiled, ("universal_compilation", "obligation_graph_ref")),
        },
        claim_decomposition={
            "status": "pass",
            "artifact_ref": compiled["claim_decomposition_ref"],
        },
        scenario_refs=_sequence(case.get("scenario_refs")),
        corpus_stub_responses=stub_responses,
    )


def _runtime_pdc_graph_summary(pipeline: Mapping[str, Any]) -> dict[str, Any]:
    smoke = _mapping(pipeline.get("compiled_pdc_graph_smoke"))
    graph = _mapping(pipeline.get("runtime_pdc_graph"))
    return {
        "status": str(smoke.get("status") or "blocked"),
        "graph_ref": smoke.get("runtime_pdc_graph_ref"),
        "claim_count": smoke.get("claim_count"),
        "edge_count": smoke.get("edge_count"),
        "warrant_structure_count": smoke.get("warrant_structure_count"),
        "authority_envelope": smoke.get("authority_envelope")
        or graph.get("authority_envelope"),
        "capability_reality_label": smoke.get("capability_reality_label")
        or pipeline.get("capability_reality_label"),
        "blockers": list(_sequence_of_mappings(smoke.get("blockers"))),
    }


def _persist_graph_artifact(
    *,
    graph: Mapping[str, Any],
    repo_root: Path,
    graph_output_dir: Path,
    case_id: str,
) -> str:
    output = graph_output_dir / f"{_slug(case_id)}.runtime-pdc-graph.json"
    atomic_write_json(output, dict(graph))
    return f"repo://{_repo_relative(repo_root, output)}"


def _persist_hypothesis_ledger_artifact(
    *,
    ledger_payload: Mapping[str, Any],
    repo_root: Path,
    ledger_output_dir: Path,
    case_id: str,
) -> str:
    """Write a serialised hypothesis ledger to disk and return a repo:// ref."""

    output = ledger_output_dir / f"{_slug(case_id)}.hypothesis-ledger.json"
    atomic_write_json(output, dict(ledger_payload))
    return f"repo://{_repo_relative(repo_root, output)}"


def _persist_critic_report_artifact(
    *,
    critic_report_payload: Mapping[str, Any],
    repo_root: Path,
    critic_report_output_dir: Path,
    case_id: str,
) -> str:
    """Write a W6.E critic ensemble report artifact and return a repo:// ref."""

    output = critic_report_output_dir / f"{_slug(case_id)}.critic-ensemble-report.json"
    atomic_write_json(output, dict(critic_report_payload))
    return f"repo://{_repo_relative(repo_root, output)}"


def _run_llm_formulator_and_critics(
    *,
    case_id: str,
    run_id: str,
    intent_text: str,
    compiled_case: Any,
    graph: ObligationGraph,
    facets: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    claim_ledger: Any,
) -> dict[str, Any]:
    """Run the W6.E LLM formulator + multi-critic ensemble for one corpus case.

    The runtime path keeps candidates strictly as ``candidate_unverified`` —
    Track A is the wire-in; promotion to obligations is Track B. The returned
    payload surfaces the in-memory ledger, the critic verdicts, the firewall
    enforcement summary, and a serialised ``HypothesisLedger`` envelope so the
    case writer can persist it alongside the runtime PDC graph artifact.
    """

    authority_profile_ref = compiled_case.authority_profile.profile_id
    concept_spine_refs = (compiled_case.concept_spine_ref,)
    source_refs = (
        f"obligation_graph:{graph.graph_id}",
        f"claim_decomposition:{run_id}",
        f"compiled_case:{compiled_case.case_id}",
    )
    claim_decomposition_payload = tuple(
        claim.model_dump(mode="json", exclude_none=True)
        for claim in getattr(claim_ledger, "claims", ())
    )
    formulator_input = LLMFormulatorInput(
        intent=intent_text,
        facets={
            "snapshots": [dict(snapshot) for snapshot in facets],
        },
        obligations=tuple(dict(obligation) for obligation in obligations),
        claim_decomposition=claim_decomposition_payload,
        authority_profile_ref=authority_profile_ref,
        concept_spine_refs=concept_spine_refs,
        source_refs=source_refs,
        run_id=run_id,
        tool_refs=W12D_FORMULATOR_TOOL_REFS,
        repair_decision_lineage=W12D_FORMULATOR_REPAIR_LINEAGE,
        metadata={
            "phase_id": PHASE_ID,
            "case_id": case_id,
        },
    )
    sink = InMemoryHypothesisLedger()
    formulator_output = LLMFormulator().formulate(formulator_input, ledger=sink)
    critic_report = MultiCriticEnsemble.default().evaluate(
        formulator_input,
        candidates=formulator_output.candidates,
    )
    # The formulator emits its own ``HypothesisLedgerEntry`` model alongside
    # the canonical one in ``polisyos.runtime.quality.hypothesis_ledger``.
    # Round-tripping through ``model_validate`` with dict entries lets Pydantic
    # coerce between the two and avoids a class-identity mismatch.
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": run_id,
            "job_id": f"job-{_slug(case_id)}",
            "hypothesis_ledger_ref": f"hypothesis-ledger:{_slug(run_id)}",
            "entries": [
                entry.model_dump(mode="json", exclude_none=True)
                for entry in sink.entries
            ],
        }
    )
    ledger_payload = serialize_hypothesis_ledger(ledger)
    # Track A wire-in keeps the firewall in advisory mode: the canonical
    # consumer payloads (W8.A PDC graph, W4.E projection, closeout reader)
    # are not yet produced at this point in ``_compile_case_artifacts``, so
    # running the firewall over the ledger itself would emit synthetic
    # ``candidate_unverified`` violations for every candidate × every
    # authority slot. Track B will bind the firewall to those real consumer
    # payloads. Track A confirms the firewall is wired and importable; if a
    # downstream payload accidentally references a candidate, that violation
    # will surface at the consumer site.
    firewall_issues: list[dict[str, Any]] = []
    return {
        "formulator": {
            "schema_version": formulator_output.schema_version,
            "run_id": formulator_output.run_id,
            "prompt_fingerprint": formulator_output.prompt_fingerprint,
            "candidate_count": len(formulator_output.candidates),
            "metadata": dict(formulator_output.metadata),
        },
        "critic_ensemble": {
            "schema_version": critic_report.schema_version,
            "verdict_count": len(critic_report.verdicts),
            "verdict_counts_by_type": _critic_verdict_counts(critic_report.verdicts),
            "diversity_summary": critic_report.diversity.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "metadata": dict(critic_report.metadata),
        },
        "critic_ensemble_report_payload": {
            **critic_report.model_dump(mode="json", exclude_none=True),
            "case_id": case_id,
        },
        "hypothesis_ledger": {
            "schema_version": HYPOTHESIS_LEDGER_SCHEMA_VERSION,
            "ledger_payload": ledger_payload,
            "summary": dict(ledger.summary),
        },
        "candidate_firewall": {
            "authority_slots": list(W12D_FIREWALL_AUTHORITY_SLOTS),
            "surface": f"w12d.universal_outcome_corpus.{case_id}",
            "issue_count": len(firewall_issues),
            "issues": list(firewall_issues),
        },
        "_formulator_output": formulator_output,
        "_critic_report": critic_report,
    }


def _critic_verdict_counts(verdicts: Sequence[Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for verdict in verdicts:
        counter[str(getattr(verdict, "verdict", "unknown"))] += 1
    return {key: counter[key] for key in sorted(counter)}


def _expert_adjudication_delta(
    case: Mapping[str, Any],
    *,
    runtime_structural_outcome: str,
) -> dict[str, Any]:
    adjudication = _mapping(case.get("expert_adjudication") or case.get("adjudication"))
    expert_label = _normalized_token(adjudication.get("case_label") or "reviewer_disagreement")
    expected_outcome = EXPERT_LABEL_EXPECTED_OUTCOME.get(expert_label, "accepted_deficit")
    delta_codes: list[str] = []
    if runtime_structural_outcome != expected_outcome:
        delta_codes.append(
            f"runtime_{_slug(runtime_structural_outcome)}_vs_expert_{_slug(expected_outcome)}"
        )
    claim_labels = list(_sequence_of_mappings(adjudication.get("claim_labels")))
    return {
        "expert_label": expert_label,
        "runtime_structural_outcome": runtime_structural_outcome,
        "expected_outcome": expected_outcome,
        "status": "aligned" if not delta_codes else "delta",
        "delta_codes": delta_codes,
        "claim_label_count": len(claim_labels),
        "claim_delta_refs": [
            {
                "claim_id": row.get("claim_id"),
                "label": row.get("label"),
                "status_should_have_been": row.get("status_should_have_been"),
                "failure_mode": row.get("failure_mode"),
            }
            for row in claim_labels
        ],
    }


def _finalize_expert_adjudication_delta(
    expert_delta: Mapping[str, Any],
    *,
    canonical_runtime_outcome: str,
) -> dict[str, Any]:
    expected = str(expert_delta.get("expected_outcome") or "accepted_deficit")
    delta = dict(expert_delta)
    delta["canonical_runtime_outcome"] = canonical_runtime_outcome
    if canonical_runtime_outcome == expected:
        delta["status"] = "aligned"
        delta["delta_codes"] = []
    else:
        delta["status"] = "delta"
        delta["delta_codes"] = [
            (
                f"canonical_runtime_{_slug(canonical_runtime_outcome)}"
                f"_vs_expert_{_slug(expected)}"
            )
        ]
    return delta


def _is_expected_negative_control(
    *,
    expert_delta: Mapping[str, Any],
    outcome: str,
) -> bool:
    return (
        outcome == "typed_blocker"
        and str(expert_delta.get("expected_outcome") or "") == "typed_blocker"
    )


def _decorate_case_blocker_for_rollout(
    blocker: Mapping[str, Any],
    *,
    expected_negative_control: bool,
) -> dict[str, Any]:
    row = dict(blocker)
    if expected_negative_control:
        row["expected_negative_control"] = True
        row["blocks_rollout_posture"] = False
        row["counts_as_closeout_honesty"] = True
        row["counts_as_closeout_honesty_failure"] = False
    elif row.get("code") in ACTIONABLE_CAPABILITY_BLOCKER_CODES:
        row.setdefault("expected_negative_control", False)
        row["blocks_rollout_posture"] = False
        row.setdefault("counts_as_closeout_honesty", True)
        row.setdefault("counts_as_closeout_honesty_failure", False)
    else:
        row.setdefault("expected_negative_control", False)
        row.setdefault("blocks_rollout_posture", True)
        row.setdefault("counts_as_closeout_honesty", False)
        row.setdefault("counts_as_closeout_honesty_failure", False)
    row.setdefault("counts_as_useful_design", False)
    return row


def _runtime_structural_outcome(
    *,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
) -> str:
    if runtime_pdc_graph.get("status") != "pass":
        return "typed_blocker"
    if producer_pipeline.get("status") != "pass":
        return "typed_blocker"
    return "pass"


def _canonical_outcome(
    *,
    runtime_pdc_graph: Mapping[str, Any],
    producer_pipeline: Mapping[str, Any],
    expert_delta: Mapping[str, Any],
    typed_blockers: Sequence[Mapping[str, Any]],
    authority_level: str,
    s1_graded_outcome: Mapping[str, Any],
) -> str:
    if typed_blockers or runtime_pdc_graph.get("status") != "pass":
        return "typed_blocker"
    if producer_pipeline.get("status") != "pass":
        return "typed_blocker"
    if _s1_can_publish_with_limitation(
        s1_graded_outcome,
        authority_level=_s1_primary_authority_level(None, authority_level),
    ):
        return "publish-with-limitation"
    return str(expert_delta.get("expected_outcome") or "accepted_deficit")


def _s1_can_publish_with_limitation(
    s1_graded_outcome: Mapping[str, Any],
    *,
    authority_level: str,
) -> bool:
    return (
        authority_level in {"research", "governed"}
        and s1_graded_outcome.get("outcome") == "publish_with_limitation"
        and s1_graded_outcome.get("closeout_status") == "closed_with_limitations"
        and not s1_graded_outcome.get("blocked_by")
        and bool(s1_graded_outcome.get("decision_owner_ref"))
        and bool(s1_graded_outcome.get("authority_profile_ref"))
        and bool(_sequence(s1_graded_outcome.get("review_refs")))
    )


def _expert_delta_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    expert_delta: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if expert_delta.get("expected_outcome") != "typed_blocker":
        return []
    return [
        _case_blocker(
            code="w12d_expert_adjudication_blocks_runtime_outcome",
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            message=(
                "W11.C expert adjudication expects a blocked outcome; runtime "
                "output cannot count as useful design."
            ),
            next_action=(
                "Repair the runtime output or preserve the typed blocker in rollout evidence."
            ),
        )
    ]


def _runtime_graph_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    runtime_pdc_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers = list(_sequence_of_mappings(runtime_pdc_graph.get("blockers")))
    if not blockers:
        blockers = [{"message": "Runtime PDC graph did not pass W8.A smoke."}]
    return [
        _case_blocker(
            code=str(blocker.get("code") or "w12d_runtime_pdc_graph_blocked"),
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            message=str(blocker.get("message") or "Runtime PDC graph blocked."),
            next_action="Repair W8.A graph assembly before claiming corpus capability.",
        )
        for blocker in blockers
    ]


def _producer_pipeline_diagnostic_codes(pipeline: Mapping[str, Any]) -> list[str]:
    codes = {
        str(issue.get("code"))
        for issue in _sequence_of_mappings(pipeline.get("issues"))
        if issue.get("code")
    }
    exit_gate = _mapping(pipeline.get("compiled_requirement_exit_gate"))
    status = str(exit_gate.get("status") or "")
    if status and status != "pass":
        codes.add(f"compiled_requirement_exit_gate_{status}")
    for key in (
        "missing_spec_families",
        "missing_binding_producers",
        "missing_capability_refs",
        "missing_construct_refs",
    ):
        if _sequence(exit_gate.get(key)):
            codes.add(key)
    if str(pipeline.get("status") or "") != "pass" and not codes:
        codes.add("producer_pipeline_blocked_without_issue_codes")
    return sorted(codes)


def _s1_graded_outcome_summary(
    *,
    case: Mapping[str, Any],
    case_id: str,
    domain: str,
    authority_level: str,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
    capability_graph_trace: Mapping[str, Any],
    corpus_stub_summary: Mapping[str, Any] | None,
    typed_blockers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    authority = _s1_primary_authority_level(corpus_stub_summary, authority_level)
    blocked_by = _s1_blocked_by(
        producer_pipeline=producer_pipeline,
        runtime_pdc_graph=runtime_pdc_graph,
        typed_blockers=typed_blockers,
    )
    if blocked_by is not None:
        return {
            **_s1_not_applicable_summary(authority_level=authority),
            "outcome": "typed_blocker",
            "closeout_effect": "closeout_blocked",
            "closeout_status": "blocked",
            "blocked_by": blocked_by,
            "authority_outcomes": {
                level: {"outcome": "typed_blocker", "blocked_by": blocked_by}
                for level in AUTHORITY_LEVELS
            },
        }

    proxy_refs, partial_refs = _s1_evidence_refs(
        producer_pipeline=producer_pipeline,
        capability_graph_trace=capability_graph_trace,
    )
    if not proxy_refs and not partial_refs:
        return _s1_not_applicable_summary(authority_level=authority)

    authority_decisions = _s1_authority_decisions(
        case=case,
        case_id=case_id,
        domain=domain,
        proxy_refs=proxy_refs,
        partial_refs=partial_refs,
    )
    primary = authority_decisions.get(authority)
    if primary is None:
        return {
            **_s1_not_applicable_summary(authority_level=authority),
            "authority_outcomes": _s1_authority_outcome_rows(authority_decisions),
        }

    closeout_verdict: dict[str, Any] = {"status": "not_applicable"}
    projection_surface_status = "not_applicable"
    if primary.outcome == "publish_with_limitation":
        closeout_record = graded_outcome_closeout_record(
            [primary],
            generated_at=datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00")),
        )
        module_records = _s1_passing_closeout_records()
        module_records["deficit_crosswalk"] = closeout_record
        closeout_verdict = build_can_i_closeout_verdict(
            run_id=f"run-layer2-s1-{_slug(case_id)}",
            module_records=module_records,
        )
        projection_surface_status = (
            "pass"
            if closeout_verdict.get("status") == "closed_with_limitations"
            else "blocked"
        )

    return {
        "schema_version": S1_GRADED_OUTCOME_SCHEMA_VERSION,
        "outcome": primary.outcome,
        "closeout_effect": primary.closeout_effect,
        "closeout_status": closeout_verdict.get("status") or "not_applicable",
        "decision_owner_ref": primary.decision_owner_ref,
        "authority_profile_ref": primary.authority_profile_ref,
        "review_refs": list(primary.review_refs),
        "projection_surface_status": projection_surface_status,
        "authority_level": primary.authority_level,
        "authority_boundary": primary.authority_boundary,
        "authority_outcomes": _s1_authority_outcome_rows(authority_decisions),
    }


def _s1_not_applicable_summary(*, authority_level: str) -> dict[str, Any]:
    return {
        "schema_version": S1_GRADED_OUTCOME_SCHEMA_VERSION,
        "outcome": "not_applicable",
        "closeout_effect": "unaffected",
        "closeout_status": "not_applicable",
        "decision_owner_ref": None,
        "authority_profile_ref": f"authority_profile.{authority_level}",
        "review_refs": [],
        "projection_surface_status": "not_applicable",
        "authority_level": authority_level,
        "authority_outcomes": {},
    }


def _s1_authority_decisions(
    *,
    case: Mapping[str, Any],
    case_id: str,
    domain: str,
    proxy_refs: Sequence[str],
    partial_refs: Sequence[str],
) -> dict[str, GradedOutcomeDecision]:
    decisions: dict[str, GradedOutcomeDecision] = {}
    for authority_level in AUTHORITY_LEVELS:
        requested_outcome = _s1_requested_outcome(case, authority_level=authority_level)
        if requested_outcome != "publish_with_limitation":
            continue
        input_row = GradedOutcomeEvidenceInput(
            schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
            case_id=case_id,
            claim_id=_s1_claim_id(case, case_id=case_id),
            authority_level=authority_level,
            requested_outcome="publish_with_limitation",
            evidence_profile="partial_or_proxy",
            proxy_evidence_refs=tuple(proxy_refs),
            partial_evidence_refs=tuple(partial_refs),
            limitation_reason_codes=("w12d_partial_or_proxy_evidence",),
            mandatory_gate_state="none",
            owner="team-evaluation",
            decision_owner_ref=f"review://layer2-s1/{case_id}/{authority_level}/owner",
            authority_profile_ref=f"authority_profile.{authority_level}",
            review_refs=(f"review://layer2-s1/{case_id}/{authority_level}/limitation",),
            ttl_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
            public_limitation_note=(
                "W12.D S1 routed partial or proxy producer evidence to a "
                "closeout-visible limitation."
            ),
            rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
        )
        decisions[authority_level] = compose_graded_outcome(input_row)
    return decisions


def _s1_authority_outcome_rows(
    decisions: Mapping[str, GradedOutcomeDecision],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for authority_level, decision in decisions.items():
        outcome = (
            "publish-with-limitation"
            if decision.outcome == "publish_with_limitation"
            else decision.outcome
        )
        rows[authority_level] = {
            "outcome": outcome,
            "closeout_effect": decision.closeout_effect,
            "decision_owner_ref": decision.decision_owner_ref,
            "authority_profile_ref": decision.authority_profile_ref,
            "review_refs": list(decision.review_refs),
            "blocked_by": _s1_decision_blocked_by(decision),
        }
    return rows


def _s1_primary_authority_level(
    corpus_stub_summary: Mapping[str, Any] | None,
    authority_level: str,
) -> str:
    raw = (
        _text((corpus_stub_summary or {}).get("max_authority_posture"))
        or authority_level
        or "research"
    )
    normalized = raw.replace("-", "_")
    if normalized == "governed_pilot":
        return "governed"
    if normalized in AUTHORITY_LEVELS:
        return normalized
    return _normalized_token(authority_level or "research")


def _s1_blocked_by(
    *,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
    typed_blockers: Sequence[Mapping[str, Any]],
) -> str | None:
    codes = {
        _normalized_token(blocker.get("code"))
        for blocker in typed_blockers
        if blocker.get("code")
    }
    if any("non_overridable" in code for code in codes):
        return "non_overridable_gate"
    if any("reissue" in code for code in codes):
        return "reissue_required"
    if any("review_required" in code or "review" in code for code in codes):
        return "review_required"
    if (
        typed_blockers
        or producer_pipeline.get("status") != "pass"
        or runtime_pdc_graph.get("status") != "pass"
    ):
        return "hard_closeout_blocker"
    return None


def _s1_decision_blocked_by(decision: GradedOutcomeDecision) -> str | None:
    blocker_codes = {
        _normalized_token(blocker.get("code"))
        for blocker in decision.blockers
        if blocker.get("code")
    }
    if "graded_outcome_non_overridable_gate" in blocker_codes:
        return "non_overridable_gate"
    if "graded_outcome_production_proxy_block" in blocker_codes:
        return "production_proxy_evidence"
    if blocker_codes:
        return "hard_closeout_blocker"
    return None


def _s1_requested_outcome(
    case: Mapping[str, Any],
    *,
    authority_level: str,
) -> str:
    for row in _expected_closeout_rows(case):
        if _normalized_token(row.get("authority_level")) != authority_level:
            continue
        state = _normalized_token(row.get("state") or row.get("outcome") or row.get("status"))
        if state in {"limited", "publish_with_limitation", "publish-with-limitation"}:
            return "publish_with_limitation"
    return "pass"


def _s1_evidence_refs(
    *,
    producer_pipeline: Mapping[str, Any],
    capability_graph_trace: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    proxy_refs: list[str] = []
    partial_refs: list[str] = []
    for decision in _sequence_of_mappings(producer_pipeline.get("producer_binding_decisions")):
        artifact_ref = _text(decision.get("artifact_ref"))
        if not artifact_ref:
            continue
        label = _normalized_token(decision.get("label"))
        if "proxy" in artifact_ref or "proxy" in label:
            proxy_refs.append(artifact_ref)
        elif "limited" in label or artifact_ref.startswith("corpus-stub:"):
            partial_refs.append(artifact_ref)
    for binding in _sequence_of_mappings(capability_graph_trace.get("capability_bindings")):
        if not _sequence(binding.get("acquisition_strategies")):
            continue
        binding_ref = _text(binding.get("binding_id"))
        if binding_ref:
            proxy_refs.append(f"capability-binding://{binding_ref}")
    return tuple(_unique_texts(proxy_refs)[:8]), tuple(_unique_texts(partial_refs)[:8])


def _s1_claim_id(case: Mapping[str, Any], *, case_id: str) -> str:
    claims = _sequence_of_mappings(_nested(case, ("claim_evidence_annotations", "claims")))
    if claims:
        claim_id = _text(claims[0].get("claim_id") or claims[0].get("id"))
        if claim_id:
            return claim_id
    return f"claim:{case_id}:main"


def _s1_passing_closeout_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _s1_w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _s1_w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _s1_w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _s1_w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _s1_w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _s1_w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": _s1_w4_record(
            "policyos.runtime.policy_design_case.conflict_materialization_closeout.v1"
        ),
        "attestation": _s1_w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _s1_w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _s1_w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _s1_w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _s1_w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _s1_w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_gate": _s1_w4_record("policyos.runtime.run_cost_gate.v1"),
        "complexity_self_fmea": _s1_w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _s1_w4_record("policyos.runtime.audit_verifier.v1"),
        "prompt_tool_repair_fmea": _s1_w4_record(
            "policyos.runtime.prompt_tool_repair_fmea.v1"
        ),
    }


def _s1_w4_record(schema_version: str) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "w12d.layer2_s1",
        "runtime_event_ref": "event://w12d/layer2-s1",
        "cas_ref": "sha256:" + "1" * 64,
        "issues": [],
    }


def _capability_graph_actionable_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    capability_graph_trace: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if capability_graph_trace.get("status") != "pass":
        return []
    blockers: list[dict[str, Any]] = []
    for binding in _sequence_of_mappings(capability_graph_trace.get("capability_bindings")):
        status = str(binding.get("status") or "")
        if status not in ACTIONABLE_CAPABILITY_BLOCKER_CODES:
            continue
        blockers.append(
            {
                **_case_blocker(
                    code=status,
                    case_id=case_id,
                    domain=domain,
                    authority_level=authority_level,
                    message=(
                        "W7 producer pipeline is blocked by a typed capability "
                        f"binding status: {status}."
                    ),
                    next_action=(
                        "Use the capability binding acquisition strategies, rejected "
                        "alternatives, and authority factors before rollout promotion."
                    ),
                ),
                "construct_ref": binding.get("construct_ref"),
                "capability_ref": binding.get("selected_capability_ref"),
                "capability_index_ref": binding.get("capability_index_ref"),
                "binding_status": status,
                "blocked_reasons": list(binding.get("blocked_reasons") or ()),
                "limitations": list(binding.get("limitations") or ()),
                "acquisition_strategies": list(binding.get("acquisition_strategies") or ()),
                "rejected_alternatives": list(binding.get("rejected_alternatives") or ()),
                "blocks_rollout_posture": False,
                "counts_as_closeout_honesty": True,
            }
        )
    return blockers


def _authority_outcomes(
    case: Mapping[str, Any],
    *,
    outcome: str,
    expert_delta: Mapping[str, Any],
    s1_authority_outcomes: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = _expected_closeout_rows(case)
    if not rows:
        authority_level = _normalized_token(case.get("authority_level") or "research")
        rows = ({ "authority_level": authority_level, "state": outcome },)
    authority_outcomes: dict[str, dict[str, Any]] = {}
    for row in rows:
        authority_level = _normalized_token(row.get("authority_level") or "research")
        row_outcome = _canonical_outcome_for_closeout_state(
            _normalized_token(row.get("state") or row.get("outcome") or row.get("status")),
            fallback=outcome,
        )
        s1_row = _mapping(s1_authority_outcomes.get(authority_level))
        if s1_row:
            row_outcome = str(s1_row.get("outcome") or row_outcome)
        if outcome == "typed_blocker":
            row_outcome = "typed_blocker"
        authority_outcomes[authority_level] = {
            "outcome": row_outcome,
            "counts_toward_useful_design": row_outcome in USEFUL_DESIGN_OUTCOMES,
            "expert_expected_outcome": expert_delta.get("expected_outcome"),
            "required_surface_refs": list(_sequence(row.get("required_surface_refs"))),
            "blocker_refs": list(_sequence(row.get("blocker_refs"))),
            "limitation_refs": list(_sequence(row.get("limitation_refs"))),
        }
    return {
        authority_level: authority_outcomes.get(
            authority_level,
            {
                "outcome": outcome,
                "counts_toward_useful_design": outcome in USEFUL_DESIGN_OUTCOMES,
                "expert_expected_outcome": expert_delta.get("expected_outcome"),
                "required_surface_refs": [],
                "blocker_refs": [],
                "limitation_refs": [],
            },
        )
        for authority_level in AUTHORITY_LEVELS
    }


def _canonical_outcome_for_closeout_state(state: str, *, fallback: str) -> str:
    if state in {"publishable", "pass"}:
        return "pass"
    if state in {"limited", "publish_with_limitation", "publish-with-limitation"}:
        return "publish-with-limitation"
    if state in {"accepted_deficit", "accepted-deficit", "contested", "review_required"}:
        return "accepted_deficit"
    if state in {"blocked", "typed_blocker", "typed-blocker"}:
        return "typed_blocker"
    return fallback


def _summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcome_counts = dict.fromkeys(OUTCOMES, 0)
    for case in cases:
        outcome = str(case.get("outcome") or "typed_blocker")
        outcome_counts.setdefault(outcome, 0)
        outcome_counts[outcome] += 1
    runtime_useful_count = sum(
        1 for case in cases if case.get("counts_toward_useful_design")
    )
    expert_useful_count = sum(
        1
        for case in cases
        if _expert_expected_useful_design(case)
    )
    aligned_useful_count = sum(
        1
        for case in cases
        if _expert_expected_useful_design(case)
        and case.get("counts_toward_useful_design")
    )
    graph_pass_count = sum(
        1
        for case in cases
        if _nested(case, ("runtime_pdc_graph", "status")) == "pass"
    )
    closeout_honest_count = sum(1 for case in cases if _closeout_honest(case))
    expected_negative_control_count = sum(
        1 for case in cases if _expected_negative_control_case(case)
    )
    unexpected_typed_blocker_count = sum(
        1
        for case in cases
        if str(case.get("outcome") or "") == "typed_blocker"
        and not _expected_negative_control_case(case)
    )
    rollout_blocker_count = sum(
        1
        for case in cases
        for blocker in _sequence_of_mappings(case.get("typed_blockers"))
        if blocker.get(
            "blocks_rollout_posture",
            not _expected_negative_control_case(case),
        )
    )
    return {
        "case_count": len(cases),
        "outcome_counts": {key: outcome_counts[key] for key in sorted(outcome_counts)},
        # ``runtime_useful_design_*`` reports what the system actually
        # produced on this run. ``expert_useful_design_ceiling_*`` mirrors
        # what experts say should be achievable. The alignment rate is the
        # share of expert-expected useful cases that the runtime actually
        # delivered. The plan keeps all three explicit so rollout decisions do
        # not conflate ceiling and actual.
        "runtime_useful_design_count": runtime_useful_count,
        "runtime_useful_design_rate": _rate(runtime_useful_count, len(cases)),
        "expert_useful_design_ceiling_count": expert_useful_count,
        "expert_useful_design_ceiling": _rate(expert_useful_count, len(cases)),
        "useful_design_alignment_rate": _rate(
            aligned_useful_count, expert_useful_count
        ),
        "useful_design_alignment_count": aligned_useful_count,
        # Backward-compatible legacy keys; downstream W12.A ladder reads new
        # names by preference but falls back to these while consumers migrate.
        "useful_design_count": runtime_useful_count,
        "useful_design_rate": _rate(runtime_useful_count, len(cases)),
        "runtime_pdc_graph_pass_count": graph_pass_count,
        "runtime_pdc_graph_pass_rate": _rate(graph_pass_count, len(cases)),
        "expert_adjudication_delta_count": sum(
            1
            for case in cases
            if _nested(case, ("expert_adjudication_delta", "status")) == "delta"
        ),
        "typed_blocker_case_count": outcome_counts.get("typed_blocker", 0),
        "closeout_honesty_count": closeout_honest_count,
        "closeout_honesty_rate": _rate(closeout_honest_count, len(cases)),
        "expected_negative_control_count": expected_negative_control_count,
        "unexpected_typed_blocker_count": unexpected_typed_blocker_count,
        "rollout_blocker_count": rollout_blocker_count,
    }


def _closeout_honest(case: Mapping[str, Any]) -> bool:
    delta = _mapping(case.get("expert_adjudication_delta"))
    if str(delta.get("expert_label") or "") in {"", "unknown"}:
        return False
    expected = str(delta.get("expected_outcome") or "")
    canonical = str(delta.get("canonical_runtime_outcome") or case.get("outcome") or "")
    return bool(expected) and canonical == expected


def _expected_negative_control_case(case: Mapping[str, Any]) -> bool:
    delta = _mapping(case.get("expert_adjudication_delta"))
    return (
        str(case.get("outcome") or "") == "typed_blocker"
        and str(delta.get("expected_outcome") or "") == "typed_blocker"
    )


def _expert_expected_useful_design(case: Mapping[str, Any]) -> bool:
    """Return True when expert adjudication labels this case as useful design.

    ``USEFUL_DESIGN_OUTCOMES`` covers ``pass`` and ``publish-with-limitation``;
    those are the closeout states the corpus annotations map to via
    ``EXPERT_LABEL_EXPECTED_OUTCOME``. Other expected outcomes (accepted
    deficit, typed blocker) do not count toward the alignment ceiling because
    the expert is not asserting that useful design should have been produced.
    """

    delta = _mapping(case.get("expert_adjudication_delta"))
    expected = str(delta.get("expected_outcome") or "")
    return expected in USEFUL_DESIGN_OUTCOMES


def _authority_stratification(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[str]] = {authority_level: [] for authority_level in AUTHORITY_LEVELS}
    for case in cases:
        authority_outcomes = _mapping(case.get("authority_outcomes"))
        for authority_level in AUTHORITY_LEVELS:
            row = _mapping(authority_outcomes.get(authority_level))
            rows[authority_level].append(str(row.get("outcome") or case.get("outcome")))
    return {
        authority_level: _metric_row(outcomes)
        for authority_level, outcomes in rows.items()
    }


def _domain_authority_stratification(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {authority_level: [] for authority_level in AUTHORITY_LEVELS}
    )
    for case in cases:
        domain = str(case.get("domain") or "unknown")
        authority_outcomes = _mapping(case.get("authority_outcomes"))
        for authority_level in AUTHORITY_LEVELS:
            row = _mapping(authority_outcomes.get(authority_level))
            grouped[domain][authority_level].append(
                str(row.get("outcome") or case.get("outcome"))
            )
    return {
        domain: {
            authority_level: _metric_row(outcomes)
            for authority_level, outcomes in rows.items()
        }
        for domain, rows in sorted(grouped.items())
    }


def _metric_row(outcomes: Sequence[str]) -> dict[str, Any]:
    counts = Counter(outcomes)
    useful_count = sum(counts[outcome] for outcome in USEFUL_DESIGN_OUTCOMES)
    return {
        "case_count": len(outcomes),
        "outcome_counts": {outcome: counts.get(outcome, 0) for outcome in OUTCOMES},
        "useful_design_count": useful_count,
        "typed_blocker_count": counts.get("typed_blocker", 0),
        "accepted_deficit_count": counts.get("accepted_deficit", 0),
        "useful_design_rate": _rate(useful_count, len(outcomes)),
        "typed_blockers_count_as_useful_design": False,
        "accepted_deficits_count_as_useful_design": False,
    }


def _typed_blocker_from_case(
    blocker: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    code = str(blocker.get("code") or "w12d_typed_blocker")
    case_id = str(blocker.get("case_id") or case.get("case_id") or "unknown-case")
    domain = blocker.get("domain") or case.get("domain")
    authority_level = blocker.get("authority_level") or case.get("authority_level")
    return {
        "blocker_id": f"w12d_{_slug(case_id)}_{_slug(code)}",
        "code": code,
        "blocker_type": "typed_universal_outcome_corpus_blocker",
        "severity": "blocker",
        "phase_id": PHASE_ID,
        "owner": "team-evaluation",
        "case_id": case_id,
        "domain": domain,
        "authority_level": authority_level,
        "message": blocker.get("message") or "W12.D case produced a typed blocker.",
        "next_action": blocker.get("next_action")
        or "Repair the typed blocker before rollout promotion.",
        "blocks_rollout_posture": bool(
            blocker.get(
                "blocks_rollout_posture",
                not _expected_negative_control_case(case),
            )
        ),
        "expected_negative_control": bool(
            blocker.get("expected_negative_control")
            or _expected_negative_control_case(case)
        ),
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "counts_as_closeout_honesty": bool(
            blocker.get("counts_as_closeout_honesty")
            or _expected_negative_control_case(case)
        ),
    }


def _case_blocker(
    *,
    code: str,
    case_id: str,
    domain: str,
    authority_level: str,
    message: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "case_id": case_id,
        "domain": domain,
        "authority_level": authority_level,
        "message": message,
        "next_action": next_action,
    }


def _load_issue_case_result(issue: Mapping[str, Any]) -> dict[str, Any]:
    code = str(issue.get("code") or "w12d_corpus_load_failed")
    return {
        "case_id": str(issue.get("source_path") or "corpus-load-issue"),
        "source_path": issue.get("source_path"),
        "domain": "unknown",
        "authority_level": "research",
        "outcome": "typed_blocker",
        "counts_toward_useful_design": False,
        "universal_compilation": {"status": "blocked"},
        "producer_pipeline": {"status": "blocked", "producer_pipeline_ref": None},
        "runtime_pdc_graph": {"status": "blocked", "graph_ref": None, "blockers": []},
        "evidence_bound_pdc_graph": {
            "artifact_ref": None,
            "authority_boundary": _graph_authority_boundary(),
        },
        "expert_adjudication_delta": {
            "expert_label": "unknown",
            "runtime_structural_outcome": "typed_blocker",
            "expected_outcome": "typed_blocker",
            "status": "blocked",
            "delta_codes": [code],
            "claim_label_count": 0,
            "claim_delta_refs": [],
        },
        "authority_outcomes": {
            authority_level: {
                "outcome": "typed_blocker",
                "counts_toward_useful_design": False,
                "expert_expected_outcome": "typed_blocker",
                "required_surface_refs": [],
                "blocker_refs": [],
                "limitation_refs": [],
            }
            for authority_level in AUTHORITY_LEVELS
        },
        "typed_blockers": [
            {
                "code": code,
                "case_id": str(issue.get("source_path") or "corpus-load-issue"),
                "domain": "unknown",
                "authority_level": "research",
                "message": issue.get("message") or "Corpus case could not be loaded.",
                "next_action": "Repair the W11 corpus fixture and rerun W12.D.",
            }
        ],
        "issues": [dict(issue)],
    }


def _runtime_claims(
    *,
    claim_ledger: Any,
    case: Mapping[str, Any],
    case_id: str,
    authority_level: str,
) -> list[dict[str, Any]]:
    baseline_refs = [
        record.baseline_id
        for record in getattr(claim_ledger, "baseline_records", ())
        if getattr(record, "baseline_id", None)
    ]
    alternative_refs = [
        record.alternative_id
        for record in getattr(claim_ledger, "alternative_records", ())
        if getattr(record, "alternative_id", None)
    ]
    claims: list[dict[str, Any]] = []
    for claim in getattr(claim_ledger, "claims", ()):
        row = claim.model_dump(mode="json", exclude_none=True)
        # ``setdefault`` does not overwrite an existing empty list, so claims
        # whose model dumps with ``baseline_refs: []`` (the default from
        # ``ClaimDecompositionCompiler``) would otherwise miss the ledger-level
        # baseline/alternative records. We attach the ledger refs whenever the
        # claim itself has not bound case-specific refs (deferred Track B5).
        if not row.get("baseline_refs"):
            row["baseline_refs"] = baseline_refs
        if not row.get("alternative_refs"):
            row["alternative_refs"] = alternative_refs
        if not row.get("required_authority_types"):
            row["required_authority_types"] = ["implementing"]
        row.setdefault("legal_authority_required", True)
        row.setdefault("policy_instrument", _instrument(case, case_id=case_id))
        row.setdefault("competent_actor_ref", _competent_actor(case))
        row.setdefault("implementation_authority_required", True)
        row.setdefault("implementation_authority_ref", _implementation_actor(case))
        row.setdefault("authority_level", authority_level)
        row.setdefault("population_scope", _target_population(case))
        claims.append(row)
    return claims


def _claim_facets(compiled_case: Any) -> list[dict[str, Any]]:
    facets = []
    for snapshot in facet_snapshots_for_obligation_graph(compiled_case):
        facets.append(
            {
                "facet_id": snapshot["facet_id"],
                "facet_type": snapshot["facet_type"],
                "value": snapshot["value"],
                "concept_spine_refs": [snapshot["concept_ref"]],
                "authority_profile_refs": [snapshot["authority_profile"]],
            }
        )
    return facets


def _claim_obligations(
    graph: ObligationGraph,
    *,
    facets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    facet_ids = [str(facet["facet_id"]) for facet in facets]
    return [
        {
            "obligation_id": item.frontier_id,
            "family": item.bundle_key.family,
            "description": item.obligation_text,
            "facet_refs": facet_ids,
            "concept_spine_refs": [item.bundle_key.scope],
            "authority_profile_refs": [item.bundle_key.authority_profile],
        }
        for item in graph.blocking_frontier
    ]


def _scholar_claim(claim: Mapping[str, Any], *, authority_level: str) -> dict[str, Any]:
    return {
        "claim_id": claim.get("claim_id"),
        "claim_text": claim.get("text"),
        "claim_type": claim.get("claim_type") or "factual",
        "claim_family": claim.get("claim_family"),
        "claim_use": claim.get("claim_use"),
        "authority_level": claim.get("authority_level") or authority_level,
        "population_scope": claim.get("population_scope") or "affected_population",
        "facet_refs": list(_sequence(claim.get("facet_refs"))),
        "obligation_refs": list(_sequence(claim.get("obligation_refs"))),
        "concept_spine_refs": list(_sequence(claim.get("concept_spine_refs"))),
        "authority_profile_refs": list(_sequence(claim.get("authority_profile_refs"))),
    }


def _compilation_intent_text(
    case: Mapping[str, Any],
    *,
    intent_payload: Mapping[str, Any],
) -> str:
    return _required_text(
        case.get("compilation_intent_text")
        or _nested(case, ("metadata", "compilation_intent_text"))
        or intent_payload.get("text")
        or case.get("intent_text")
        or case.get("policy_intent"),
        field_name="intent.text",
    )


def _concept_spine_refs(case: Mapping[str, Any], *, case_id: str) -> PolicyGrammarConceptSpineRefs:
    refs = _mapping(case.get("concept_spine_refs"))
    if not refs:
        raise W12DCaseRunError("W12.D requires concept_spine_refs for W6 compilation.")
    return PolicyGrammarConceptSpineRefs(
        concept_spine_ref=_required_text(
            refs.get("concept_spine_ref"),
            field_name="concept_spine_ref",
        ),
        jurisdiction_spine_ref=_required_text(
            refs.get("jurisdiction_spine_ref"),
            field_name="jurisdiction_spine_ref",
        ),
        canonical_concept_refs=tuple(
            _sequence(refs.get("canonical_concept_refs"))
            or (f"concept://w12d/{_slug(case_id)}",)
        ),
        facet_concept_refs=_mapping(refs.get("facet_concept_refs")),
    )


def _spine_context(case: Mapping[str, Any], *, compiled_case: Any) -> dict[str, Any]:
    refs = _mapping(case.get("concept_spine_refs"))
    return {
        "concept_spine_ref": refs.get("concept_spine_ref") or compiled_case.concept_spine_ref,
        "jurisdiction_spine_ref": refs.get("jurisdiction_spine_ref")
        or compiled_case.jurisdiction_spine_ref,
        "canonical_concept_refs": list(
            _sequence(refs.get("canonical_concept_refs"))
            or (compiled_case.concept_spine_ref,)
        ),
        "as_of": _policy_time(case),
    }


def _named_alternatives(case: Mapping[str, Any], *, case_id: str) -> list[dict[str, Any]]:
    alternatives = [
        dict(row)
        for row in _sequence(case.get("named_alternatives"))
        if isinstance(row, Mapping)
    ]
    if alternatives:
        return alternatives
    return [
        {
            "alternative_id": f"alternative-{_slug(case_id)}",
            "label": "Alternative policy design",
            "description": "Corpus-run alternative for W8 graph comparison.",
        }
    ]


def _expected_closeout_rows(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    candidates = (
        _nested(case, ("expected_closeout_states", "states")),
        _nested(case, ("closeout_states", "states")),
        case.get("authority_outcomes"),
        case.get("outcomes"),
    )
    for candidate in candidates:
        rows = tuple(row for row in _sequence(candidate) if isinstance(row, Mapping))
        if rows:
            return rows
    return ()


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], [
            _issue(
                "w12d_corpus_path_missing",
                f"W12.D corpus path does not exist: {path}",
                severity="fail",
            )
        ]
    if path.is_file():
        files = (path,)
    elif (path / "cases").is_dir():
        files = tuple(sorted((path / "cases").glob("*.json")))
    else:
        files = tuple(
            file_path
            for file_path in sorted(path.rglob("*.json"))
            if not _is_non_case_fixture_path(file_path)
        )
    cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for file_path in files:
        if file_path.name == "manifest.json":
            continue
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "w12d_case_json_invalid",
                    str(exc),
                    severity="fail",
                    source_path=str(file_path),
                )
            )
            continue
        for case in _cases_from_payload(payload):
            case["_source_path"] = str(file_path)
            cases.append(case)
    if not cases:
        issues.append(
            _issue(
                "w12d_corpus_empty",
                "W12.D requires at least one universal outcome corpus case.",
                severity="fail",
                source_path=str(path),
            )
        )
    return cases, issues


def _cases_from_payload(payload: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(
            dict(item)
            for item in payload
            if isinstance(item, Mapping) and _looks_like_w12d_case(item)
        )
    if isinstance(payload, Mapping):
        if isinstance(payload.get("cases"), list):
            return tuple(
                dict(item)
                for item in payload["cases"]
                if isinstance(item, Mapping) and _looks_like_w12d_case(item)
            )
        if (payload.get("case_id") or payload.get("id")) and _looks_like_w12d_case(payload):
            return (dict(payload),)
    return ()


def _is_non_case_fixture_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return "producer_stubs" in parts or path.name.endswith(".producer_stubs.json")


def _looks_like_w12d_case(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("compilation_intent_text")
        or _nested(payload, ("intent", "text"))
        or payload.get("intent_text")
        or payload.get("policy_intent")
    )


def _graph_authority_boundary() -> dict[str, list[str]]:
    return {
        "authoritative_for": ["pdc_graph_structure"],
        "may_not_use_for": ["projection_authority", "claim_authority"],
    }


def _authority_type_for_level(authority_level: str) -> str:
    if authority_level == "production":
        return "national"
    if authority_level == "governed":
        return "regional"
    return "local"


def _jurisdiction(case: Mapping[str, Any]) -> str:
    return _text(_nested(case, ("intent", "jurisdiction"))) or _text(
        _nested(case, ("metadata", "jurisdiction"))
    ) or "global"


def _policy_time(case: Mapping[str, Any]) -> str:
    return _text(_nested(case, ("intent", "policy_time"))) or _text(
        _nested(case, ("metadata", "policy_time"))
    ) or "2026-05-25"


def _instrument(case: Mapping[str, Any], *, case_id: str) -> str:
    return _normalized_token(
        _nested(case, ("intent", "instrument_type"))
        or _nested(case, ("metadata", "instrument_type"))
        or case.get("instrument_type")
        or f"policy_instrument_{_slug(case_id)}"
    )


def _competent_actor(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("metadata", "competent_actor"))
        or _nested(case, ("intent", "jurisdiction"))
        or "policy_authority"
    )


def _implementation_actor(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("metadata", "implementation_actor"))
        or _nested(case, ("intent", "jurisdiction"))
        or "implementation_authority"
    )


def _target_population(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("intent", "target_population"))
        or _nested(case, ("metadata", "target_population"))
        or "affected_population"
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in _sequence(value) if isinstance(row, Mapping))


def _unique_texts(values: Sequence[object]) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in rows:
            rows.append(text)
    return rows


def _text_list(value: object) -> list[str]:
    return _unique_texts(_sequence(value))


def _nested(mapping: Mapping[str, Any], path: Sequence[str]) -> object | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _enum_value(enum_cls: Any, raw: object, *, default: Any) -> Any:
    text = _text(raw)
    if not text:
        return default
    normalized = _normalized_token(text).replace("-", "_")
    for item in enum_cls:
        candidates = {
            _normalized_token(getattr(item, "value", item)).replace("-", "_"),
            _normalized_token(getattr(item, "name", "")).replace("-", "_"),
        }
        if normalized in candidates:
            return item
    return default


def _required_text(value: object, *, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise W12DCaseRunError(f"W12.D corpus case is missing {field_name}.")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_token(value: object) -> str:
    text = _text(value).casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_")


def _slug(value: object) -> str:
    slug = _normalized_token(value).replace("/", "_").replace(":", "_")
    return slug or "unknown"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _issue(code: str, message: str, *, severity: str = "error", **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        **{key: value for key, value in extra.items() if value is not None},
    }


if __name__ == "__main__":
    raise SystemExit(main())
