"""Canonical runtime quality-report role, file, and reference registry.

This module is deliberately dependency-light so ref intake, scorecards, and
canary assembly share one complete registry without importing a consumer.
"""

from __future__ import annotations

REQUIRED_QUALITY_REF_KEYS = (
    "production_data_quality_report_ref",
    "normative_applicability_report_ref",
    "fabric_retrieval_trace_ref",
    "foundry_method_report_ref",
    "policy_grounding_matrix_ref",
    "conflict_check_ref",
)
LIFECYCLE_QUALITY_REF_KEYS = (
    "continuous_governance_stale_report_ref",
    "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw_report_ref",
)
KNOWN_QUALITY_REF_KEYS = (
    *REQUIRED_QUALITY_REF_KEYS,
    *LIFECYCLE_QUALITY_REF_KEYS,
    "security_assurance_report_ref",
)

# These contract constants are re-exported by their former owning modules.
# Keeping their literal values here lets this registry stay below all consumers.
COST_DEGRADATION_TELEMETRY_REPORT_KEY = "cost_degradation_telemetry"
COST_DEGRADATION_TELEMETRY_FILENAME = "cost_degradation_telemetry.json"
RUN_COST_GATE_REPORT_KEY = "run_cost_gate"
RUN_COST_GATE_FILENAME = "run_cost_gate.json"
DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_FILE = "data_forge_snapshot_binding.json"
HYPOTHESIS_LEDGER_REPORT_KEY = "hypothesis_ledger"
HYPOTHESIS_LEDGER_REF_KEY = "hypothesis_ledger_ref"
HYPOTHESIS_LEDGER_FILENAME = "hypothesis_ledger.json"
PROMPT_TOOL_LEDGER_REPORT_KEY = "prompt_tool_ledger"
PROMPT_TOOL_LEDGER_REF_KEY = "prompt_tool_ledger_ref"
PROMPT_TOOL_LEDGER_FILENAME = "prompt_tool_ledger.json"

QUALITY_REPORT_FILES = {
    "golden_scenario_contract": "golden_scenario_contract.json",
    "production_data_quality": "production_data_quality.json",
    "normative_evidence": "normative_evidence.json",
    "fabric_retrieval_trace": "fabric_retrieval_trace.json",
    "foundry_method_report": "foundry_method_report.json",
    "policy_grounding_matrix": "policy_grounding_matrix.json",
    "semantic_binding_ledger": "semantic_binding_ledger.json",
    "conflict_check": "conflict_check.json",
    "causal_statistical_validity": "causal_statistical_validity.json",
    "replay_manifest": "replay_manifest.json",
    "drift_explanation": "drift_explanation.json",
    "resilience_matrix": "resilience_matrix.json",
    "human_review_calibration": "human_review_calibration_report.json",
    "decision_artifact_quality": "decision_artifact_quality.json",
    "provider_model_quality_ledger": "provider_model_quality_ledger.json",
    "prompt_tool_ledger": PROMPT_TOOL_LEDGER_FILENAME,
    HYPOTHESIS_LEDGER_REPORT_KEY: HYPOTHESIS_LEDGER_FILENAME,
    COST_DEGRADATION_TELEMETRY_REPORT_KEY: COST_DEGRADATION_TELEMETRY_FILENAME,
    RUN_COST_GATE_REPORT_KEY: RUN_COST_GATE_FILENAME,
    "security_assurance_report": "security_assurance_report.json",
    "privacy_compliance_report": "privacy_compliance_report.json",
    "policy_design_case": "policy_design_case.json",
    "claim_registry": "claim_registry.json",
    "scholar_evidence": "scholar_academic_evidence.json",
    "scenario_contract_propagation_graph": "scenario_contract_propagation_graph.json",
    "evidence_spine_handoff_ledger": "evidence_spine_handoff_ledger.json",
    "producer_pipeline": "producer_pipeline.json",
    "producer_handshake_ledger": "producer_handshake_ledger.json",
    "producer_pipeline_readiness": "producer_pipeline_readiness.json",
    "producer_pipeline_control_plane": "producer_pipeline_control_plane.json",
    "producer_pipeline_replay": "producer_pipeline_replay.json",
    "producer_pipeline_bundle_assembly": "producer_pipeline_bundle_assembly.json",
    "producer_pipeline_inspection": "producer_pipeline_inspection.json",
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY: DATA_FORGE_SNAPSHOT_BINDING_FILE,
    "continuous_governance_stale": "continuous_governance_stale_report.json",
    "continuous_governance_reissue": "continuous_governance_reissue_report.json",
    "continuous_governance_supersede": "continuous_governance_supersede_report.json",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report.json",
    "source_truth_conflicts": "source_truth_conflicts.json",
    "formal_invariants": "formal_invariants.json",
    "source_truth": "source_truth.json",
    "conflict_materialization": "conflict_materialization_closeout.json",
    "attestation": "attestation.json",
    "policy_design_case_i4_graph": "policy_design_case_i4_graph.json",
    "policy_design_portfolio_effective_support": (
        "policy_design_portfolio_effective_support.json"
    ),
    "lifecycle_reissue_report": "lifecycle_reissue_report.json",
    "policy_design_case_projection": "policy_design_case_projection.json",
    "projection_publication_state": "projection_publication_state.json",
    "policy_design_case_projection_contract_fixture": (
        "policy_design_case_projection_contract_fixture.json"
    ),
    "calibration_ledger": "calibration_ledger.json",
    "run_cost_proportionality": "run_cost_proportionality.json",
    "audit_verifier_ingestion": "audit_verifier.json",
    "can_i_closeout": "can_i_closeout.json",
}

QUALITY_REPORT_RUNTIME_REFS = {
    "production_data_quality": "production_data_quality_report_ref",
    "normative_evidence": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "semantic_binding_ledger": "semantic_binding_ledger_ref",
    "conflict_check": "conflict_check_ref",
    "causal_statistical_validity": "causal_statistical_validity_report_ref",
    "replay_manifest": "replay_manifest_ref",
    "drift_explanation": "drift_explanation_ref",
    "resilience_matrix": "resilience_report_ref",
    "human_review_calibration": "human_review_calibration_report_ref",
    "decision_artifact_quality": "decision_artifact_quality_report_ref",
    "provider_model_quality_ledger": "provider_model_quality_ledger_ref",
    HYPOTHESIS_LEDGER_REPORT_KEY: HYPOTHESIS_LEDGER_REF_KEY,
    "security_assurance_report": "security_assurance_report_ref",
    "privacy_compliance_report": "privacy_compliance_report_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
    "can_i_closeout": "can_i_closeout_ref",
}

QUALITY_REF_HINTS = {
    "production_data_quality": "production_data_quality_report_ref",
    "production.data_quality": "production_data_quality_report_ref",
    "data_quality_report": "production_data_quality_report_ref",
    "normative_applicability": "normative_applicability_report_ref",
    "normative.applicability": "normative_applicability_report_ref",
    "applicability_report": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "fabric.retrieval_trace": "fabric_retrieval_trace_ref",
    "retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "foundry.method_report": "foundry_method_report_ref",
    "method_quality_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "policy.grounding_matrix": "policy_grounding_matrix_ref",
    "grounding_matrix": "policy_grounding_matrix_ref",
    "conflict_check": "conflict_check_ref",
    "policy_conflict_check": "conflict_check_ref",
    "security_assurance_report": "security_assurance_report_ref",
    "security.assurance_report": "security_assurance_report_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "governance_lifecycle_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "governance_lifecycle_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "governance_lifecycle_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
    "governance_lifecycle_withdraw": "continuous_governance_withdraw_report_ref",
}


QUALITY_REPORT_BODY_KEYS = frozenset(
    alias
    for report_key, filename in QUALITY_REPORT_FILES.items()
    for alias in (report_key, filename.removesuffix(".json"))
)


def _build_quality_report_intake_registry() -> tuple[tuple[str, ...], dict[str, str]]:
    """Build actual report-ref roles and aliases for registered report bodies."""
    ref_keys = set(KNOWN_QUALITY_REF_KEYS)
    body_ref_keys: dict[str, str] = {}

    def add_alias(alias: str, ref_key: str) -> None:
        prior = body_ref_keys.get(alias)
        if prior is not None and prior != ref_key:
            raise ValueError(f"quality report body alias {alias!r} maps to multiple ref roles")
        body_ref_keys[alias] = ref_key

    for report_key, filename in QUALITY_REPORT_FILES.items():
        ref_key = QUALITY_REPORT_RUNTIME_REFS.get(report_key)
        if ref_key is None:
            continue
        add_alias(report_key, ref_key)
        add_alias(filename.removesuffix(".json"), ref_key)
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        ref_keys.add(ref_key)
        add_alias(report_key, ref_key)
    for alias, ref_key in QUALITY_REF_HINTS.items():
        ref_keys.add(ref_key)
        add_alias(alias, ref_key)
    return tuple(sorted(ref_keys)), body_ref_keys


QUALITY_REPORT_REF_KEYS, QUALITY_REPORT_BODY_REF_KEYS = (
    _build_quality_report_intake_registry()
)


def quality_report_ref_intake_registry() -> tuple[tuple[str, ...], dict[str, str]]:
    """Return canonical runtime-ref roles and report aliases with real owners.

    The registry identifies which supplied ref roles must be screened. Report-body
    names without a producer-owned runtime ref are listed separately in
    `QUALITY_REPORT_BODY_KEYS`; they do not acquire a synthetic ref role. This
    registry does not verify a reference or promote a report to evidence authority.
    """
    return QUALITY_REPORT_REF_KEYS, dict(QUALITY_REPORT_BODY_REF_KEYS)
