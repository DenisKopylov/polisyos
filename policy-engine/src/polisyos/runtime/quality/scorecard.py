"""Reusable runtime quality scorecards for production/staging canary evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.control import POLICY_AUTHORITY_PROFILES
from polisyos.fabric.catalog.source_selection_audit import normalize_fabric_retrieval_trace
from polisyos.foundry.validation.method_quality import normalize_foundry_method_report
from polisyos.lex.normpack.applicability_report import (
    normalize_normative_applicability_report,
)
from polisyos.lex.normpack.conflict_check import normalize_policy_conflict_check_report
from polisyos.runtime.quality.adapter_contracts import (
    AdapterContractError,
    adapter_surface_payload_from_envelope,
    load_adapter_contract_registry,
    validate_adapter_preservation,
)
from polisyos.runtime.quality.assurance_case import (
    PolicyDesignCaseAuthorityError,
    validate_policy_design_case_concept_spine,
    validate_policy_design_case_profile,
    validate_policy_design_jurisdiction_spine,
)
from polisyos.runtime.quality.attestation import (
    evaluate_trust_boundary_attestation,
    iter_required_production_attestation_boundaries,
    load_trust_boundary_registry,
)
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    EvidenceAuthorityEnvelope,
    assert_runtime_emitted,
    assert_same_input_closure,
    authority_envelope_ownership_issues,
    classify_authority_failure,
    deserialize_authority_envelope,
)
from polisyos.runtime.quality.case_integrity import (
    validate_evidence_graph_threat_model_record,
)
from polisyos.runtime.quality.case_lifecycle import (
    validate_policy_design_lifecycle_records,
)
from polisyos.runtime.quality.case_maturity import (
    policy_design_case_maturity_scorecard_gates,
)
from polisyos.runtime.quality.claim_argument import (
    ClaimArgumentValidationResult,
    validate_claim_argument_case_surfaces,
)
from polisyos.runtime.quality.compliance import (
    PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
    PRIVACY_COMPLIANCE_REPORT_KEY,
    PRIVACY_COMPLIANCE_REPORT_REF_KEY,
    normalize_runtime_privacy_compliance_report,
    privacy_compliance_gate_details,
)
from polisyos.runtime.quality.config_release_hardening import (
    validate_config_release_deployment_migration_hardening_record,
)
from polisyos.runtime.quality.consultation import (
    validate_policy_design_case_legitimacy_records,
)
from polisyos.runtime.quality.data_forge_binding import (
    DATA_FORGE_SNAPSHOT_BINDING_FILE,
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
    data_forge_snapshot_binding_scorecard_gates,
    normalize_data_forge_snapshot_binding_report,
)
from polisyos.runtime.quality.data_quality import (
    PRODUCTION_DATA_QUALITY_REF_KEY,
    normalize_production_data_quality_report,
)
from polisyos.runtime.quality.degradation import degradation_gate_from_payloads
from polisyos.runtime.quality.diagnostic_slos import diagnostic_slo_gates
from polisyos.runtime.quality.disconfirming_evidence import (
    DisconfirmingEvidenceLedgerError,
    disconfirming_deficit_accepted,
    disconfirming_ledger_portfolio_id,
    disconfirming_ledger_record_id,
    portfolio_design_has_disconfirming_lines,
    validate_disconfirming_evidence_ledger_record,
)
from polisyos.runtime.quality.effective_mode import (
    EffectiveModeLedger,
    ModePolicyError,
    assert_serious_mode_allowed,
)
from polisyos.runtime.quality.evidence_independence import (
    EvidenceIndependenceError,
    validate_evidence_independence_map_record,
)
from polisyos.runtime.quality.evidence_line import (
    EvidenceLineError,
    validate_evidence_line_record,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EvidencePortfolioDesignError,
    portfolio_design_claim_ids,
    portfolio_design_record_id,
    validate_evidence_portfolio_design_record,
)
from polisyos.runtime.quality.evidence_synthesis import (
    EvidenceSynthesisReportError,
    synthesis_report_record_id,
    validate_evidence_synthesis_report_record,
)
from polisyos.runtime.quality.external_audit import (
    validate_public_audit_archive_record,
)
from polisyos.runtime.quality.external_client_surface import (
    validate_external_client_surface_record,
)
from polisyos.runtime.quality.invariants import (
    InvariantRegistryError,
    load_production_invariant_registry,
)
from polisyos.runtime.quality.legacy_migration_sandbox import (
    LEGACY_MIGRATION_SEMANTIC_LOSS,
    comparison_failure_codes,
)
from polisyos.runtime.quality.multiverse_specification_curve import (
    MultiverseSpecificationCurveError,
    validate_multiverse_specification_curve_record,
)
from polisyos.runtime.quality.observability_static_audit import (
    validate_observability_orchestration_static_audit_records,
)
from polisyos.runtime.quality.pass1b_hardening import (
    policy_design_pass1b_hardening_scorecard_gates,
)
from polisyos.runtime.quality.phase_barriers import (
    PhaseBarrierId,
    PhaseBarrierRecord,
    PhaseBarrierViolation,
    assert_barrier_passed,
)
from polisyos.runtime.quality.policy_benchmarking import (
    validate_policy_design_best_in_class_benchmarking_records,
)
from polisyos.runtime.quality.policy_design_case import (
    policy_design_case_record_registry_scorecard_gates,
    policy_design_case_substrate_residual_verification_scorecard_gates,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    PROMPT_TOOL_LEDGER_FILENAME,
    PROMPT_TOOL_LEDGER_REF_KEY,
    PROMPT_TOOL_LEDGER_REPORT_KEY,
    validate_prompt_tool_parser_authority,
)
from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs
from polisyos.runtime.quality.run_cost_proportionality import (
    RunCostProportionalityError,
    build_run_cost_proportionality_ledger_from_quality_context,
    validate_run_cost_proportionality_blocker,
    validate_run_cost_proportionality_ledger,
)
from polisyos.runtime.quality.schema_compat import (
    COMPATIBLE_DECISIONS,
    SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES,
    evaluate_schema_compatibility,
)
from polisyos.runtime.quality.semantic_binding import (
    authority_envelopes_missing_semantic_binding_ref,
    deserialize_semantic_binding_ledger,
    evaluate_semantic_binding_ledger,
)
from polisyos.runtime.quality.skip_blockers import skip_blocker_gate_from_payloads
from polisyos.runtime.quality.source_truth import (
    SOURCE_TRUTH_CONFLICT_SCHEMA,
    SourceTruthContractError,
    detect_source_truth_conflict,
    load_source_truth_lattice,
)
from polisyos.runtime.security.quality_gates import (
    SECURITY_ASSURANCE_REPORT_REF_KEY,
    SECURITY_REPORT_FILE,
    security_gates_from_report,
)
from polisyos.runtime.quality.scholar_academic_evidence import (
    SCHOLAR_ACADEMIC_EVIDENCE_FILENAME,
    normalize_scholar_academic_evidence_report,
    scholar_academic_evidence_required,
)
from polisyos.scientist.validation.policy_grounding import (
    normalize_policy_grounding_matrix,
)

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
    "security_assurance_report": "security_assurance_report.json",
    "privacy_compliance_report": "privacy_compliance_report.json",
    "policy_design_case": "policy_design_case.json",
    "scholar_evidence": "scholar_academic_evidence.json",
    "scenario_contract_propagation_graph": "scenario_contract_propagation_graph.json",
    "evidence_spine_handoff_ledger": "evidence_spine_handoff_ledger.json",
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY: DATA_FORGE_SNAPSHOT_BINDING_FILE,
    "continuous_governance_stale": "continuous_governance_stale_report.json",
    "continuous_governance_reissue": "continuous_governance_reissue_report.json",
    "continuous_governance_supersede": "continuous_governance_supersede_report.json",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report.json",
    "source_truth_conflicts": "source_truth_conflicts.json",
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
    "security_assurance_report": "security_assurance_report_ref",
    "privacy_compliance_report": "privacy_compliance_report_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
}
QUALITY_REPORT_GATE_METADATA = {
    "production_data_quality": (
        "production_data_quality_present",
        "materialization",
        "fabric_materialization",
    ),
    "normative_evidence": ("normative_evidence_present", "lex", "lex"),
    "fabric_retrieval_trace": ("fabric_retrieval_trace_present", "fabric", "fabric_retrieval"),
    "foundry_method_report": ("foundry_method_evidence_present", "foundry", "foundry_methods"),
    "policy_grounding_matrix": (
        "policy_grounding_matrix_present",
        "policy_output",
        "scientist_policy_artifacts",
    ),
    "semantic_binding_ledger": (
        "semantic_binding_ledger_valid",
        "policy_output",
        "semantic_binding",
    ),
    "conflict_check": ("conflict_check_present", "lex", "normative_conflict"),
    "causal_statistical_validity": (
        "causal_statistical_validity_present",
        "foundry",
        "foundry_causal_validity",
    ),
    "replay_manifest": ("replay_manifest_present", "ops", "runtime_replay"),
    "drift_explanation": ("drift_explanation_present", "ops", "runtime_replay"),
    "resilience_matrix": ("resilience_matrix_present", "ops", "runtime_resilience"),
    "human_review_calibration": (
        "human_review_calibration_present",
        "ops",
        "human_review_calibration",
    ),
    "decision_artifact_quality": (
        "decision_artifact_quality_present",
        "policy_output",
        "scientist_decision_artifact",
    ),
    "provider_model_quality_ledger": (
        "provider_model_quality_ledger_passed",
        "llm",
        "llm_provider_quality",
    ),
    "security_assurance_report": (
        "security_assurance_report_passed",
        "ops",
        "runtime_diagnostics",
    ),
    "privacy_compliance_report": ("privacy_compliance_report_present", "ops", "privacy_compliance"),
    "continuous_governance_stale": (
        "continuous_governance_stale_report_present",
        "scientist",
        "scientist_governance_lifecycle",
    ),
    "continuous_governance_reissue": (
        "continuous_governance_reissue_report_present",
        "scientist",
        "scientist_governance_lifecycle",
    ),
    "continuous_governance_supersede": (
        "continuous_governance_supersede_report_present",
        "scientist",
        "scientist_governance_lifecycle",
    ),
    "continuous_governance_withdraw": (
        "continuous_governance_withdraw_report_present",
        "scientist",
        "scientist_governance_lifecycle",
    ),
}
CONTINUOUS_GOVERNANCE_LIFECYCLE_REPORT_KEYS = (
    "continuous_governance_stale",
    "continuous_governance_reissue",
    "continuous_governance_supersede",
    "continuous_governance_withdraw",
)
REQUIRED_MATERIALIZATION_REFS = (
    "data_snapshot_ref",
    "input_bindings_ref",
    "registry_bundle_ref",
    "quality_report_ref",
    "production_data_quality_report_ref",
)
STAGES = (
    "llm",
    "fabric",
    "materialization",
    "foundry",
    "scientist",
    "lex",
    "policy_output",
    "ops",
)
SERIOUS_CANARY_KINDS = {"production", "governed", "research"}
POLICY_DESIGN_CASE_RUNTIME_REF_KEYS = (
    "policy_intent_envelope_ref",
    "policy_design_capability_ledger_ref",
    "policy_design_case_ref",
)
POLICY_DESIGN_CASE_REQUIRED_SUBRECORDS = {
    "intent_envelope": "policy_design_intent_envelope_missing",
    "capability_ledger": "policy_design_capability_ledger_missing",
    "case_registry_entry": "policy_design_case_registry_entry_missing",
}
POLICY_DESIGN_PARALLEL_AUTHORITY_KEYS = (
    "parallel_policy_design_case_authority",
    "parallel_case_authority",
    "policy_design_case_authority_profile",
)
POLICY_DESIGN_SELF_FMEA_REQUIRED_FAILURE_MODES = (
    "schema_migration_errors",
    "partial_case_graphs",
    "contradictory_records",
    "stale_generated_surfaces",
    "operator_workarounds",
    "box_ticking_failure",
)
POLICY_DESIGN_SELF_FMEA_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.non_adversarial_self_fmea.v1"
)
POLICY_DESIGN_SELF_FMEA_PASSING_STATUSES = {
    "accepted",
    "mitigated",
    "pass",
    "passed",
    "verified",
}
POLICY_DESIGN_PARTIAL_STATE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.partial_state_consistency.v1"
)
POLICY_DESIGN_PARTIAL_STATE_PASSING_STATUSES = {
    "pass",
    "passed",
    "verified",
}
MOCK_PROVIDER_MARKERS = ("mock", "fallback", "fixture", "stub")
APPROVAL_STATES = (
    "execution_failed",
    "quality_failed",
    "quality_warn",
    "approval_ready",
    "override_required",
)
PERFORMANCE_FAIL_STATUSES = {
    "blocked",
    "error",
    "fail",
    "failed",
    "over_budget",
    "timeout",
}
PERFORMANCE_WARN_STATUSES = {"degraded", "warn", "warning"}
OVERRIDE_ACCEPTED_STATUSES = {"accepted", "approved", "overridden", "signed"}
OVERRIDE_ACCEPTED_ACTIONS = {"override"}
OVERRIDE_REJECTED_STATUSES = {
    "explanation_insufficient",
    "interrupted",
    "rejected",
    "rerun_requested",
}
OVERRIDE_REJECTED_ACTIONS = {
    "explanation_insufficient",
    "interrupt_release",
    "reject",
    "request_rerun",
}
OVERRIDE_PENDING_STATUSES = {"pending", "required", "requested"}
SCORECARD_CONTROL_PROGRESS_KEYS = (
    "schema_version",
    "generated_at",
    "execution_status",
    "quality_status",
    "performance_status",
    "approval_state",
    "canary_kind",
    "job_id",
    "run_id",
    "quality_scorecard_ref",
    "quality_evidence_bundle_path",
    "overall_score",
    "stage_scores",
    "quality_gates",
    "blocking_quality_failures",
    "operator_triage_ledger",
    "warnings",
    "approval_eligibility",
    "evidence_refs",
    "source_truth_conflicts",
)
PHASE_3_1_FAILURE_CODES = frozenset(
    {
        "hds_runtime_ref_missing",
        "hds_ref_identity_mismatch",
        "hds_bundle_ref_used_as_runtime_ref",
        "hds_schema_incompatible",
        "hds_same_input_closure_mismatch",
        "hds_disallowed_mode",
        "hds_unallowed_fallback",
        "hds_projection_used_as_authority",
        "hds_hidden_benchmark_not_authority",
        "hds_unknown_provenance",
        "hds_event_reconciliation_failed",
        "hds_adapter_semantic_loss",
        "hds_source_truth_conflict",
        "hds_semantic_binding_missing",
        LEGACY_MIGRATION_SEMANTIC_LOSS,
        "legacy_migration_legacy_used_as_authority",
    }
)


def _gate(
    *,
    name: str,
    stage: str,
    code: str | None = None,
    status: str,
    layer: str,
    phase: str | None = None,
    message: str,
    evidence_ref: str | None = None,
    next_action: str | None = None,
    blocking: bool = True,
    missing_input: str | None = None,
    conflicting_producer: str | None = None,
    affected_claim: str | None = None,
    next_command: str | None = None,
    owner: str | None = None,
    root_cause_class: str | None = None,
    first_failing_artifact_ref: str | None = None,
    producer_authority: Mapping[str, Any] | None = None,
    authority_failure_code: str | None = None,
    domain_failure_code: str | None = None,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "stage": stage,
        "code": code,
        "status": status,
        "layer": layer,
        "phase": phase,
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
        "blocking": blocking,
    }
    for key, value in (
        ("missing_input", missing_input),
        ("conflicting_producer", conflicting_producer),
        ("affected_claim", affected_claim),
        ("next_command", next_command),
        ("owner", owner),
        ("root_cause_class", root_cause_class),
        ("first_failing_artifact_ref", first_failing_artifact_ref),
        ("producer_authority", dict(producer_authority) if producer_authority else None),
        ("authority_failure_code", authority_failure_code),
        ("domain_failure_code", domain_failure_code),
    ):
        if value is not None:
            payload[key] = value
    return payload


_AUTHORITY_SPOOFING_DIAGNOSTIC_COMMAND = (
    "uv run pytest tests/unit/runtime/quality/test_authority_spoofing.py -q"
)

_SPOOF_OWNER_BY_LAYER = {
    "attestation": "team-assurance",
    "fabric_materialization": "team-runtime-quality",
    "fabric_retrieval": "team-fabric",
    "foundry_causal_validity": "team-foundry",
    "foundry_methods": "team-foundry",
    "human_review_calibration": "team-quality-closeout",
    "llm_provider_quality": "team-runtime-ops",
    "lex": "team-policy-semantics",
    "normative_conflict": "team-policy-semantics",
    "privacy_compliance": "team-assurance",
    "prompt_tool_parser_authority": "team-runtime-ops",
    "quality_benchmark_authority": "team-assurance",
    "quality_scorecard": "team-quality-closeout",
    "runtime_diagnostics": "team-observability",
    "runtime_replay": "team-runtime-ops",
    "runtime_resilience": "team-runtime-ops",
    "schema_compatibility": "team-architecture",
    "scientist_decision_artifact": "team-policy-semantics",
    "scientist_policy_artifacts": "team-policy-semantics",
    "security": "team-security",
    "semantic_binding": "team-policy-semantics",
    "source_truth": "team-architecture-governance",
}


def _authority_spoof_failure_metadata(gate: dict[str, Any]) -> dict[str, Any]:
    code = _clean_text(gate.get("code")) or _clean_text(gate.get("name")) or "quality_failure"
    layer = _clean_text(gate.get("layer")) or "quality_scorecard"
    phase = _clean_text(gate.get("phase")) or "quality_evidence"
    next_command = _next_diagnostic_command_for_gate(gate, layer=layer, phase=phase)
    return {
        "failure_code": code,
        "owner": _SPOOF_OWNER_BY_LAYER.get(layer, "team-runtime-quality"),
        "phase": phase,
        "source_surface": _source_surface_for_gate(gate, layer=layer, phase=phase),
        "attempted_authority_upgrade": _attempted_authority_upgrade_for_gate(
            gate,
            code=code,
            layer=layer,
            phase=phase,
        ),
        "downstream_impact": _downstream_impact_for_gate(gate, code=code, layer=layer),
        "next_diagnostic_command": next_command,
    }


def _source_surface_for_gate(
    gate: dict[str, Any],
    *,
    layer: str,
    phase: str,
) -> str:
    code = str(gate.get("code") or gate.get("name") or "").casefold()
    evidence_ref = _clean_text(gate.get("evidence_ref"))
    if phase == "projection_boundary" or "projection" in code:
        return "runtime.projection"
    if layer == "runtime_diagnostics" or "diagnostic_event" in code:
        return "runtime.diagnostic_event_log"
    if layer == "attestation":
        return "runtime.trust_boundary_attestations"
    if layer == "source_truth":
        return "runtime.source_truth_lattice"
    if "schema" in code:
        return "runtime.schema_compatibility"
    if layer == "semantic_binding":
        return "quality_evidence.semantic_binding_ledger"
    if layer == "quality_benchmark_authority":
        return "quality_benchmark.hidden_pack"
    if evidence_ref:
        return evidence_ref
    return f"runtime.{layer}"


def _attempted_authority_upgrade_for_gate(
    gate: dict[str, Any],
    *,
    code: str,
    layer: str,
    phase: str,
) -> str:
    del gate
    normalized = f"{code} {layer} {phase}".casefold()
    if "projection" in normalized:
        return "projection_to_scorecard_or_readiness_authority"
    if "bundle" in normalized or "packaging" in normalized:
        return "bundle_packaging_to_runtime_authority"
    if "runtime_ref" in normalized or "ref_identity" in normalized:
        return "runtime_ref_to_cas_authority"
    if "diagnostic_event" in normalized or "event_reconciliation" in normalized:
        return "diagnostic_event_to_runtime_event_authority"
    if "attestation" in normalized:
        return "attestation_record_to_trust_boundary_authority"
    if "schema" in normalized:
        return "schema_decision_to_closeout_authority"
    if "semantic" in normalized:
        return "semantic_ledger_to_claim_authority"
    if "source_truth" in normalized:
        return "losing_source_truth_surface_to_closeout_authority"
    if "provider_model" in normalized:
        return "provider_quality_ledger_to_llm_authority"
    if "benchmark" in normalized:
        return "hidden_benchmark_result_to_quality_authority"
    return "input_payload_to_scorecard_or_readiness_authority"


def _downstream_impact_for_gate(
    gate: dict[str, Any],
    *,
    code: str,
    layer: str,
) -> str:
    explicit = _clean_text(gate.get("downstream_impact"))
    if explicit is not None:
        return explicit
    normalized = f"{code} {layer}".casefold()
    if "approval" in normalized or "projection" in normalized:
        return "Readiness or approval would close from a projection instead of runtime authority."
    if "source_truth" in normalized:
        return "Scorecard would accept a losing source-of-truth surface as final authority."
    if "diagnostic" in normalized or "event" in normalized:
        return "Scorecard would close without reconcilable runtime diagnostic events."
    if "attestation" in normalized:
        return "Trust-boundary evidence would be accepted without verified attestation."
    if "schema" in normalized:
        return "Schema-incompatible evidence would satisfy production closeout."
    if "semantic" in normalized:
        return "Final claims would close without valid semantic binding lineage."
    if "benchmark" in normalized:
        return "Hidden benchmark results would become quality authority."
    return (
        "Scorecard, readiness, approval, or publication closeout would advance "
        "from spoofed authority."
    )


def _next_diagnostic_command_for_gate(
    gate: dict[str, Any],
    *,
    layer: str,
    phase: str,
) -> str:
    explicit = _clean_text(gate.get("next_diagnostic_command"))
    if explicit and explicit.startswith("uv run "):
        return explicit
    next_action = _clean_text(gate.get("next_action"))
    if next_action and next_action.startswith("uv run "):
        return next_action
    code = str(gate.get("code") or gate.get("name") or "").casefold()
    if layer == "runtime_diagnostics" or "diagnostic_event" in code:
        return (
            "uv run pytest tests/unit/runtime/quality/test_diagnostic_event_contract.py "
            "tests/unit/runtime/quality/test_runtime_event_log.py -q"
        )
    if layer == "attestation" or "attestation" in code:
        return "uv run pytest tests/unit/runtime/quality/test_attestation.py -q"
    if layer == "source_truth" or "source_truth" in code:
        return "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
    if layer == "semantic_binding" or "semantic" in code:
        return "uv run pytest tests/unit/runtime/quality/test_semantic_binding.py -q"
    if "schema" in code:
        return (
            "uv run pytest tests/repo_quality/tools/test_runtime_quality_schema_compatibility.py -q"
        )
    if layer in {"privacy_compliance", "security"}:
        return "uv run pytest tests/unit/runtime/quality/test_compliance.py tests/security -q"
    if layer == "llm_provider_quality" or "provider_model_quality" in code:
        return "uv run pytest tests/repo_quality/tools/test_provider_quality_ledger.py -q"
    if layer == "quality_benchmark_authority" or "benchmark" in code:
        return "uv run pytest tests/repo_quality/tools/test_quality_benchmark_authority.py -q"
    if phase == "projection_boundary" or "projection" in code:
        return _AUTHORITY_SPOOFING_DIAGNOSTIC_COMMAND
    return _AUTHORITY_SPOOFING_DIAGNOSTIC_COMMAND


def _blocking_failure_from_gate(gate: dict[str, Any]) -> dict[str, Any]:
    code = _clean_text(gate.get("code")) or str(gate["name"])
    spoof_metadata = _authority_spoof_failure_metadata(gate)
    classification = classify_authority_failure(
        authority_error_code=_clean_text(gate.get("authority_failure_code")) or code,
        domain_failure_code=_clean_text(gate.get("domain_failure_code")) or code,
        envelope=gate.get("producer_authority"),
        artifact_ref=(
            _sanitize_ref(gate.get("first_failing_artifact_ref"))
            or _sanitize_ref(gate.get("evidence_ref"))
            or str(gate["name"])
        ),
        owner=_clean_text(gate.get("owner")) or spoof_metadata["owner"],
        next_action=_clean_text(gate.get("next_action")),
    )
    classification_payload = classification.model_dump(mode="json", exclude_none=True)
    failure = {
        "gate": gate["name"],
        "code": code,
        "layer": gate["layer"],
        "phase": gate.get("phase"),
        "message": gate["message"],
        "evidence_ref": gate["evidence_ref"],
        "next_action": classification.next_action,
    }
    failure.update(spoof_metadata)
    failure.update(classification_payload)
    failure["failure_code"] = code
    for key in (
        "missing_input",
        "conflicting_producer",
        "affected_claim",
        "next_command",
    ):
        if gate.get(key) is not None:
            failure[key] = gate[key]
    if gate.get("layer") == "security":
        failure.update(
            {
                "retryable": bool(gate.get("retryable", False)),
                "retryability": _clean_text(gate.get("retryability")) or "not_retryable",
            }
        )
    return failure


def _operator_triage_ledger(
    blocking_quality_failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    root_causes: dict[tuple[str, str, str], dict[str, Any]] = {}
    for failure in blocking_quality_failures:
        artifact_ref = (
            _sanitize_ref(failure.get("first_failing_artifact_ref"))
            or _sanitize_ref(failure.get("evidence_ref"))
            or _clean_text(failure.get("gate"))
            or "quality_failure"
        )
        owner = _clean_text(failure.get("owner")) or "team-runtime-quality"
        root_cause_class = (
            _clean_text(failure.get("root_cause_class")) or "unknown_provenance"
        )
        key = (owner, root_cause_class, artifact_ref)
        row = root_causes.setdefault(
            key,
            {
                "triage_id": _triage_id(owner, root_cause_class, artifact_ref),
                "owner": owner,
                "root_cause_class": root_cause_class,
                "first_failing_artifact_ref": artifact_ref,
                "next_action": (
                    _clean_text(failure.get("next_action"))
                    or "Repair the first failing producer artifact and rerun closeout."
                ),
                "failure_codes": [],
                "gates": [],
                "phases": [],
                "layers": [],
                "downstream_failure_refs": [],
                "collapsed_failure_count": 0,
            },
        )
        row["collapsed_failure_count"] += 1
        _append_unique(row["failure_codes"], _clean_text(failure.get("code")))
        _append_unique(row["gates"], _clean_text(failure.get("gate")))
        _append_unique(row["phases"], _clean_text(failure.get("phase")))
        _append_unique(row["layers"], _clean_text(failure.get("layer")))
        _append_unique(
            row["downstream_failure_refs"],
            _sanitize_ref(failure.get("evidence_ref")),
        )

    rows = sorted(
        root_causes.values(),
        key=lambda row: (
            str(row["owner"]),
            str(row["root_cause_class"]),
            str(row["first_failing_artifact_ref"]),
        ),
    )
    return {
        "schema_version": "policyos.operator_triage_ledger.v1",
        "root_cause_count": len(rows),
        "root_causes": rows,
    }


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def _triage_id(owner: str, root_cause_class: str, artifact_ref: str) -> str:
    safe = (
        f"{owner}:{root_cause_class}:{artifact_ref}"
        .replace("://", ":")
        .replace("/", ":")
        .replace(" ", "_")
    )
    return f"triage:{safe}"


def _nested_get(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _nested_find_all(payload: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(payload, dict):
        if key in payload:
            found.append(payload[key])
        for value in payload.values():
            found.extend(_nested_find_all(value, key))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_nested_find_all(value, key))
    return found


def _nested_quality_ref(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for payload_key, value in payload.items():
            if payload_key == "optional_runtime_quality_refs":
                continue
            found = _nested_quality_ref(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _nested_quality_ref(value, key)
            if found is not None:
                return found
    return None


def _runtime_authority_refs(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    quality_evidence: dict[str, Any] | None = None,
) -> RuntimeQualityAuthorityRefs:
    return RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )


def _serious_canary(canary_kind: str) -> bool:
    return canary_kind.casefold() in SERIOUS_CANARY_KINDS


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    lowered = text.casefold()
    secret_markers = (
        "access_token",
        "api_key",
        "bearer ",
        "password",
        "refresh_token",
        "secret",
    )
    if any(marker in lowered for marker in secret_markers):
        return None
    return text


def _sanitize_ref(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None or len(text) > 256:
        return None
    return text


def _quality_report_status(report: Any) -> str:
    if not isinstance(report, dict):
        return "missing"
    raw_status = str(report.get("status") or report.get("quality_status") or "present").lower()
    if raw_status in {
        "accepted_drift",
        "match",
        "pass",
        "passed",
        "ok",
        "success",
    }:
        return "pass"
    if str(report.get("production_readiness") or "").casefold() == "pass":
        return "pass"
    if raw_status in {"warn", "warning", "degraded"}:
        return "warn"
    return "fail"


def _quality_report_issue_codes(report: Any) -> list[str]:
    return [
        str(issue.get("code") or "").strip()
        for issue in _quality_report_issues(report)
        if str(issue.get("code") or "").strip()
    ]


def _quality_report_issues(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    issues = report.get("issues")
    if not isinstance(issues, list):
        return []
    return [dict(issue) for issue in issues if isinstance(issue, dict)]


def _first_quality_issue(report: Any) -> dict[str, Any]:
    issues = _quality_report_issues(report)
    return issues[0] if issues else {}


def _domain_failure_code_for_report(*, report_key: str, report: Any) -> str:
    first_issue = _first_quality_issue(report)
    issue_code = _clean_text(first_issue.get("code")) if first_issue else None
    if issue_code:
        return issue_code
    return f"{report_key}_validation_failed"


def _domain_phase_for_report(*, report_key: str, report: Any) -> str:
    first_issue = _first_quality_issue(report)
    issue_phase = _clean_text(first_issue.get("phase")) if first_issue else None
    if issue_phase:
        return issue_phase
    return report_key


def _domain_next_action_for_report(*, report: Any, default: str) -> str:
    first_issue = _first_quality_issue(report)
    issue_next_action = _clean_text(first_issue.get("next_action")) if first_issue else None
    return issue_next_action or default


def _expected_source_families(quality_evidence: dict[str, Any]) -> list[str]:
    scenario_contract = quality_evidence.get("golden_scenario_contract")
    if not isinstance(scenario_contract, dict):
        return []
    expected = scenario_contract.get("expected_evidence_contract")
    if not isinstance(expected, dict):
        return []
    families = expected.get("admissible_data_source_families")
    if not isinstance(families, list):
        return []
    return [str(family) for family in families if str(family or "").strip()]


def _expected_foundry_methods(quality_evidence: dict[str, Any]) -> list[str]:
    scenario_contract = quality_evidence.get("golden_scenario_contract")
    if not isinstance(scenario_contract, dict):
        return []
    expected = scenario_contract.get("expected_evidence_contract")
    if not isinstance(expected, dict):
        return []
    method_expectations = expected.get("foundry_method_expectations")
    if not isinstance(method_expectations, list):
        return []
    return [
        str(expectation) for expectation in method_expectations if str(expectation or "").strip()
    ]


def normalize_quality_evidence(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> dict[str, Any]:
    """Normalize domain quality reports into stable scorecard input."""
    normalized = dict(quality_evidence)
    production_data_quality = normalized.get("production_data_quality")
    if isinstance(production_data_quality, dict):
        normalized["production_data_quality"] = normalize_production_data_quality_report(
            production_data_quality
        )
    normative_evidence = normalized.get("normative_evidence")
    if isinstance(normative_evidence, dict):
        normalized["normative_evidence"] = normalize_normative_applicability_report(
            normative_evidence
        )
    data_forge_snapshot_binding = normalized.get(DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY)
    if isinstance(data_forge_snapshot_binding, dict):
        normalized[DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY] = (
            normalize_data_forge_snapshot_binding_report(data_forge_snapshot_binding)
        )
    fabric_trace = normalized.get("fabric_retrieval_trace")
    if isinstance(fabric_trace, dict):
        normalized["fabric_retrieval_trace"] = normalize_fabric_retrieval_trace(
            fabric_trace,
            expected_source_families=_expected_source_families(normalized),
            canary_kind=canary_kind,
            data_forge_snapshot_binding=(
                normalized[DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY]
                if isinstance(normalized.get(DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY), dict)
                else None
            ),
        )
    foundry_report = normalized.get("foundry_method_report")
    if isinstance(foundry_report, dict):
        normalized["foundry_method_report"] = normalize_foundry_method_report(
            foundry_report,
            expected_method_expectations=_expected_foundry_methods(normalized),
            canary_kind=canary_kind,
        )
    scholar_evidence = normalized.get("scholar_evidence")
    if isinstance(scholar_evidence, dict):
        normalized["scholar_evidence"] = normalize_scholar_academic_evidence_report(
            scholar_evidence
        )
    policy_grounding_matrix = normalized.get("policy_grounding_matrix")
    if isinstance(policy_grounding_matrix, dict):
        normalized["policy_grounding_matrix"] = normalize_policy_grounding_matrix(
            policy_grounding_matrix,
            normative_evidence=(
                normalized["normative_evidence"]
                if isinstance(normalized.get("normative_evidence"), dict)
                else None
            ),
            fabric_retrieval_trace=(
                normalized["fabric_retrieval_trace"]
                if isinstance(normalized.get("fabric_retrieval_trace"), dict)
                else None
            ),
            foundry_method_report=(
                normalized["foundry_method_report"]
                if isinstance(normalized.get("foundry_method_report"), dict)
                else None
            ),
        )
    conflict_check = normalized.get("conflict_check")
    if isinstance(conflict_check, dict):
        normalized["conflict_check"] = normalize_policy_conflict_check_report(conflict_check)
    privacy_compliance_report = normalized.get(PRIVACY_COMPLIANCE_REPORT_KEY)
    if isinstance(privacy_compliance_report, dict):
        normalized[PRIVACY_COMPLIANCE_REPORT_KEY] = normalize_runtime_privacy_compliance_report(
            privacy_compliance_report
        )
    return normalized


def _materialization_refs_present(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    missing = [key for key in REQUIRED_MATERIALIZATION_REFS if not _nested_get(payload, key)]
    return not missing, missing


def _llm_variants(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        item = dict(raw)
        key = str(
            item.get("model_variant_id")
            or item.get("id")
            or item.get("model")
            or item.get("model_id")
            or len(variants)
        )
        if key in seen:
            return
        seen.add(key)
        variants.append(item)

    for payload in (job_payload, run_payload):
        for raw in _nested_find_all(payload or {}, "llm_model_variants"):
            if isinstance(raw, list):
                for item in raw:
                    _add(item)
        for raw in _nested_find_all(payload or {}, "variants"):
            if isinstance(raw, dict):
                for item in raw.values():
                    _add(item)
            elif isinstance(raw, list):
                for item in raw:
                    _add(item)
    return variants


def _provider_is_mock_like(variant: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(variant.get(key) or "")
        for key in ("provider", "model", "model_variant_id", "status", "failure_code")
    ).casefold()
    return any(marker in haystack for marker in MOCK_PROVIDER_MARKERS)


def _variant_completed(variant: dict[str, Any]) -> bool:
    status = str(variant.get("status") or "").casefold()
    return status in {"completed", "success", "pass", "selected"}


def _variant_has_usage_accounting(variant: dict[str, Any]) -> bool:
    token_keys = (
        "prompt_tokens",
        "completion_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    )
    has_tokens = any(variant.get(key) is not None for key in token_keys)
    return has_tokens and (
        variant.get("cost_usd") is not None or variant.get("estimated_cost_usd") is not None
    )


def _llm_gates(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    provider_preflight: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    serious = _serious_canary(canary_kind)
    raw_preflight_status = (
        str(provider_preflight.get("status") or "").strip().lower()
        if isinstance(provider_preflight, dict)
        else ""
    )
    preflight_status = _quality_report_status(provider_preflight)
    if preflight_status == "pass" or (raw_preflight_status == "skipped" and not serious):
        gates.append(
            _gate(
                name="provider_preflight_recorded",
                stage="llm",
                code="provider_preflight_recorded",
                status="pass",
                layer="llm_gateway",
                phase="provider_preflight",
                message=(
                    "Provider preflight evidence is present."
                    if raw_preflight_status != "skipped"
                    else "Provider preflight was intentionally skipped for a non-serious profile."
                ),
                evidence_ref="provider_preflight.json",
                blocking=False,
            )
        )
    elif provider_preflight is None:
        gates.append(
            _gate(
                name="provider_preflight_recorded",
                stage="llm",
                code="provider_preflight_missing",
                status="fail" if serious else "warn",
                layer="llm_gateway",
                phase="provider_preflight",
                message="Provider preflight evidence is missing.",
                evidence_ref=None,
                next_action="Record provider preflight evidence before long real LLM runs.",
                blocking=serious,
            )
        )
    else:
        gates.append(
            _gate(
                name="provider_preflight_recorded",
                stage="llm",
                code="provider_preflight_failed",
                status="fail",
                layer="llm_gateway",
                phase="provider_preflight",
                message="Provider preflight did not pass.",
                evidence_ref="provider_preflight.json",
                next_action="Fix provider preflight failure before judging policy quality.",
            )
        )

    variants = _llm_variants(job_payload=job_payload, run_payload=run_payload)
    if not variants:
        gates.append(
            _gate(
                name="llm_model_variants_present",
                stage="llm",
                code="llm_model_variants_missing",
                status="fail" if serious else "warn",
                layer="nl_pipeline",
                phase="llm_variants",
                message="LLM model variant evidence is missing.",
                next_action="Persist selected variant, provider, schema-healing, and usage data.",
                blocking=serious,
            )
        )
        return gates

    completed_real_variants = [
        variant
        for variant in variants
        if _variant_completed(variant) and not _provider_is_mock_like(variant)
    ]
    gates.append(
        _gate(
            name="llm_model_variants_present",
            stage="llm",
            code=(
                "llm_model_variants_present"
                if completed_real_variants
                else "llm_real_gateway_variant_missing"
            ),
            status="pass" if completed_real_variants else "fail",
            layer="nl_pipeline",
            phase="llm_variants",
            message=(
                "Real LLM model variant evidence is present."
                if completed_real_variants
                else "No completed non-mock LLM model variant was recorded."
            ),
            evidence_ref="artifacts.json",
            next_action=(
                None
                if completed_real_variants
                else "Run serious profiles with real gateway variants and no mock fallback."
            ),
        )
    )

    usage_variants = [variant for variant in variants if _variant_has_usage_accounting(variant)]
    gates.append(
        _gate(
            name="llm_usage_accounting_present",
            stage="llm",
            code=(
                "llm_usage_accounting_present" if usage_variants else "llm_usage_accounting_missing"
            ),
            status="pass" if usage_variants else "fail",
            layer="nl_pipeline",
            phase="llm_accounting",
            message=(
                "Token and cost accounting is present."
                if usage_variants
                else "Token and cost accounting is missing from LLM variants."
            ),
            evidence_ref=(
                "performance.json"
                if _nested_get(
                    {"job": job_payload or {}, "run": run_payload or {}},
                    "run_performance_summary",
                )
                else "artifacts.json"
            ),
            next_action=(
                None
                if usage_variants
                else "Record prompt/completion/total tokens and cost per model variant."
            ),
        )
    )

    strict_schema_failures = [
        variant
        for variant in variants
        if str(variant.get("failure_code") or "").strip()
        == "llm_formalizer_schema_validation_failed"
    ]
    gates.append(
        _gate(
            name="llm_schema_validation_recorded",
            stage="llm",
            code=(
                "llm_schema_validation_recorded"
                if not strict_schema_failures
                else "llm_formalizer_schema_validation_failed"
            ),
            status="pass" if not strict_schema_failures else "fail",
            layer="nl_pipeline",
            phase="schema_validation",
            message=(
                "LLM schema validation completed without strict failures."
                if not strict_schema_failures
                else "Strict LLM formalizer schema validation failed."
            ),
            evidence_ref="artifacts.json",
            next_action=(
                None
                if not strict_schema_failures
                else "Inspect schema-healing attempts and formalizer payload contracts."
            ),
        )
    )
    return gates


def _provider_model_quality_gate(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    quality_evidence: dict[str, Any],
) -> dict[str, Any] | None:
    report = quality_evidence.get("provider_model_quality_ledger")
    runtime_payload = {"job": job_payload or {}, "run": run_payload or {}}
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    serious = _serious_canary(canary_kind)
    if not isinstance(report, dict):
        if _nested_get(runtime_payload, "default_production_model_choices"):
            return _gate(
                name="provider_model_quality_ledger_passed",
                stage="llm",
                code="provider_model_quality_ledger_missing",
                status="fail" if serious else "warn",
                layer="llm_provider_quality",
                phase="provider_model_quality",
                message="Default production model choices do not have quality ledger evidence.",
                evidence_ref=None,
                next_action=(
                    "Build provider_model_quality_ledger_ref from simulated and "
                    "quarantined live lanes before production approval."
                ),
                blocking=serious,
            )
        return None

    evidence_ref = "quality_evidence/provider_model_quality_ledger.json"
    has_runtime_ref = bool(authority_refs.get("provider_model_quality_ledger_ref"))
    reviews = [
        dict(item) for item in report.get("default_model_reviews") or [] if isinstance(item, dict)
    ]
    actions = {str(review.get("action") or "").strip() for review in reviews}
    summary = report.get("summary")
    summary_status = (
        str(summary.get("status") or "").strip().lower()
        if isinstance(summary, dict)
        else str(report.get("status") or "").strip().lower()
    )

    if "block_production_approval" in actions:
        return _gate(
            name="provider_model_quality_ledger_passed",
            stage="llm",
            code="provider_model_quality_default_evidence_blocked",
            status="fail",
            layer="llm_provider_quality",
            phase="provider_model_quality",
            message="A default production model is missing fresh provider quality evidence.",
            evidence_ref=evidence_ref,
            next_action="Refresh provider/model quality evidence or choose a proven default model.",
        )
    if "demote" in actions:
        return _gate(
            name="provider_model_quality_ledger_passed",
            stage="llm",
            code="provider_model_quality_default_model_demoted",
            status="fail",
            layer="llm_provider_quality",
            phase="provider_model_quality",
            message="Provider/model drift requires demoting a default production model.",
            evidence_ref=evidence_ref,
            next_action="Select a replacement model or record a signed production override.",
        )
    if summary_status == "fail":
        return _gate(
            name="provider_model_quality_ledger_passed",
            stage="llm",
            code="provider_model_quality_drift_failed",
            status="fail",
            layer="llm_provider_quality",
            phase="provider_model_quality",
            message="Provider/model quality drift ledger failed.",
            evidence_ref=evidence_ref,
            next_action="Inspect provider/model drift before production approval.",
        )
    if "require_review" in actions or summary_status == "warn":
        return _gate(
            name="provider_model_quality_ledger_passed",
            stage="llm",
            code="provider_model_quality_requires_review",
            status="warn",
            layer="llm_provider_quality",
            phase="provider_model_quality",
            message="Provider/model quality drift requires review.",
            evidence_ref=evidence_ref,
            next_action="Review drift evidence before approving the production model choice.",
            blocking=False,
        )
    if not has_runtime_ref and serious:
        return _gate(
            name="provider_model_quality_ledger_passed",
            stage="llm",
            code="provider_model_quality_ledger_ref_missing",
            status="fail",
            layer="llm_provider_quality",
            phase="provider_model_quality_ref",
            message="Provider/model quality ledger is present but runtime ref is missing.",
            evidence_ref=evidence_ref,
            next_action="Persist provider_model_quality_ledger_ref in runtime progress.",
        )
    return _gate(
        name="provider_model_quality_ledger_passed",
        stage="llm",
        code="provider_model_quality_ledger_passed",
        status="pass",
        layer="llm_provider_quality",
        phase="provider_model_quality",
        message="Provider/model quality ledger passed.",
        evidence_ref=evidence_ref,
        blocking=False,
    )


def _model_assisted_authority_required(
    *,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> bool:
    if quality_evidence.get(PROMPT_TOOL_LEDGER_REPORT_KEY) is not None:
        return True
    if quality_evidence.get("provider_model_quality_ledger") is not None:
        return True
    variants = _llm_variants(job_payload=job_payload, run_payload=run_payload)
    authority_ref_keys = (
        "final_policy_claims_ref",
        "llm_model_adjudication_ref",
        "policy_grounding_matrix_ref",
        "trinity_bundle_ref",
    )
    return any(
        not _provider_is_mock_like(variant)
        and (
            bool(variant.get("selected_for_workflow"))
            or any(_sanitize_ref(variant.get(key)) for key in authority_ref_keys)
        )
        for variant in variants
    )


def _prompt_tool_parser_authority_gate(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    quality_evidence: dict[str, Any],
) -> dict[str, Any] | None:
    if not _serious_canary(canary_kind):
        return None
    if not _model_assisted_authority_required(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    ):
        return None

    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    runtime_ref = authority_refs.get(PROMPT_TOOL_LEDGER_REF_KEY)
    report = quality_evidence.get(PROMPT_TOOL_LEDGER_REPORT_KEY)
    evidence_ref = (
        f"quality_evidence/{PROMPT_TOOL_LEDGER_FILENAME}"
        if isinstance(report, dict)
        else runtime_ref
    )
    if not isinstance(report, dict):
        return _gate(
            name="prompt_tool_parser_authority_ledger_present",
            stage="llm",
            code="prompt_tool_parser_authority_ledger_missing",
            status="fail",
            layer="prompt_tool_parser_authority",
            phase="prompt_tool_parser_authority",
            message=(
                "Provider/model quality evidence cannot prove prompt, tool, and parser "
                "authority for model-assisted outputs."
            ),
            evidence_ref=evidence_ref,
            next_action=(
                "Persist prompt_tool_ledger_ref with prompt template/version/fingerprint, "
                "rendered input refs, tool schemas/calls, parser contract, validation refs, "
                "repair decisions, and authority handoff refs."
            ),
        )
    if runtime_ref is None:
        return _gate(
            name="prompt_tool_parser_authority_ledger_present",
            stage="llm",
            code="prompt_tool_ledger_ref_missing",
            status="fail",
            layer="prompt_tool_parser_authority",
            phase="prompt_tool_parser_authority_ref",
            message="Prompt/tool/parser ledger is present but runtime ref is missing.",
            evidence_ref=evidence_ref,
            next_action="Persist prompt_tool_ledger_ref in runtime progress.",
        )
    embedded_ref = _sanitize_ref(report.get(PROMPT_TOOL_LEDGER_REF_KEY))
    if embedded_ref is not None and embedded_ref != runtime_ref:
        return _gate(
            name="prompt_tool_parser_authority_ledger_present",
            stage="llm",
            code="prompt_tool_ledger_ref_mismatch",
            status="fail",
            layer="prompt_tool_parser_authority",
            phase="prompt_tool_parser_authority_ref",
            message="Prompt/tool/parser ledger ref does not match runtime-owned ref.",
            evidence_ref=evidence_ref,
            next_action="Reconcile prompt_tool_ledger_ref against the runtime CAS ref.",
        )

    validation = validate_prompt_tool_parser_authority(report)
    if not validation.satisfied:
        code = (
            validation.missing_codes[0]
            if validation.missing_codes
            else "prompt_tool_parser_authority_ledger_invalid"
        )
        return _gate(
            name="prompt_tool_parser_authority_ledger_present",
            stage="llm",
            code=code,
            status="fail",
            layer="prompt_tool_parser_authority",
            phase="prompt_tool_parser_authority",
            message="Prompt/tool/parser authority ledger does not satisfy serious closeout.",
            evidence_ref=evidence_ref,
            next_action=(
                "Emit a passing ledger that covers evidence, claims, scorecard, and "
                "approval handoffs."
            ),
        )
    return _gate(
        name="prompt_tool_parser_authority_ledger_present",
        stage="llm",
        code="prompt_tool_parser_authority_ledger_passed",
        status="pass",
        layer="prompt_tool_parser_authority",
        phase="prompt_tool_parser_authority",
        message="Prompt/tool/parser authority ledger passed.",
        evidence_ref=evidence_ref,
        blocking=False,
    )


def _execution_gate(
    *,
    execution_status: str,
    job_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if execution_status == "completed":
        return _gate(
            name="execution_completed",
            stage="ops",
            code="execution_completed",
            status="pass",
            layer="control_plane",
            phase="execution",
            message="Control job completed.",
            evidence_ref="job.json" if job_payload is not None else None,
        )
    return _gate(
        name="execution_completed",
        stage="ops",
        code="execution_not_completed",
        status="fail",
        layer="control_plane",
        phase="execution",
        message=f"Control job execution status is {execution_status}.",
        evidence_ref="job.json" if job_payload is not None else None,
        next_action="Fix execution failure before judging policy quality.",
    )


def _scientist_gate(
    *,
    execution_status: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    workflow_report = _nested_get(
        {"job": job_payload or {}, "run": run_payload or {}},
        "workflow_report",
    )
    workflow_status = _quality_report_status(workflow_report)
    if isinstance(workflow_report, dict) and workflow_status != "pass":
        return _gate(
            name="scientist_workflow_report_passed",
            stage="scientist",
            code="scientist_workflow_report_failed",
            status="fail",
            layer="scientist_workflow",
            phase="workflow_report",
            message="Scientist workflow report did not pass.",
            evidence_ref="run.json" if run_payload is not None else "job.json",
            next_action="Inspect Scientist workflow report status before policy approval.",
        )
    if isinstance(workflow_report, dict):
        return _gate(
            name="scientist_workflow_report_passed",
            stage="scientist",
            code="scientist_workflow_report_passed",
            status="pass",
            layer="scientist_workflow",
            phase="workflow_report",
            message="Scientist workflow report passed.",
            evidence_ref="run.json" if run_payload is not None else "job.json",
            blocking=False,
        )
    return _gate(
        name="scientist_workflow_report_passed",
        stage="scientist",
        code=(
            "scientist_workflow_completed"
            if execution_status == "completed"
            else "scientist_workflow_report_missing"
        ),
        status="pass" if execution_status == "completed" else "fail",
        layer="scientist_workflow",
        phase="workflow_report",
        message=(
            "Scientist workflow completed with no failing report."
            if execution_status == "completed"
            else "Scientist workflow report is missing."
        ),
        evidence_ref="job.json" if job_payload is not None else None,
        next_action=(
            None
            if execution_status == "completed"
            else "Persist workflow report status and subphase progress."
        ),
        blocking=execution_status != "completed",
    )


def _materialization_gate(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    has_materialization_refs, missing_refs = _materialization_refs_present(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    return _gate(
        name="data_materialization_refs_present",
        stage="materialization",
        code=(
            "data_materialization_refs_present"
            if has_materialization_refs
            else "production_data_materialization_missing"
        ),
        status="pass" if has_materialization_refs else "fail",
        layer="fabric_materialization",
        phase="materialization_refs",
        message=(
            "Required production materialization refs are present."
            if has_materialization_refs
            else f"Missing materialization refs: {', '.join(missing_refs)}."
        ),
        evidence_ref="artifacts.json",
        next_action=(
            None
            if has_materialization_refs
            else (
                "Ensure Fabric materialization writes snapshot, bindings, "
                "registry, and quality refs."
            )
        ),
    )


def _optional_runtime_quality_ref_reason(
    *,
    ref_key: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> str | None:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    optional_refs = _nested_get(payload, "optional_runtime_quality_refs")
    if not isinstance(optional_refs, dict) or ref_key not in optional_refs:
        return None
    return _clean_text(optional_refs.get(ref_key)) or "Runtime ref is optional."


def _is_bundle_local_ref(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    return (
        normalized.startswith("quality_evidence/")
        or normalized.startswith("./")
        or normalized.startswith("../")
        or (
            normalized.endswith(".json")
            and not normalized.startswith(("sha256:", "cas://", "s3://", "gs://"))
        )
    )


def _is_cas_authority_ref(value: str) -> bool:
    return value.startswith("sha256:") or value.startswith("cas://")


def _normalize_sha256_ref(value: Any) -> str | None:
    text = _sanitize_ref(value)
    if text is None:
        return None
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:")
    elif text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
    else:
        digest = text
    if len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest):
        return f"sha256:{digest.lower()}"
    return None


def _payload_hash_matches_runtime_ref(*, payload_sha256: Any, runtime_ref: str) -> bool:
    payload_hash = _normalize_sha256_ref(payload_sha256)
    ref_hash = _normalize_sha256_ref(runtime_ref)
    if payload_hash is None or ref_hash is None:
        return False
    return payload_hash == ref_hash


def _hds_authority_failure_code(code: str) -> str:
    normalized = code.casefold()
    if "legacy" in normalized or "diagnostic_only" in normalized:
        return "legacy_migration_legacy_used_as_authority"
    if (
        "projection" in normalized
        or "packaging" in normalized
        or "bundle_packaged" in normalized
        or "evidence_not_authority_bearing" in normalized
        or "public_exported" in normalized
        or "redacted_derived" in normalized
        or "scorecard_input" in normalized
        or "readiness_input" in normalized
        or "approval_input" in normalized
    ):
        return "hds_projection_used_as_authority"
    if "same_input_closure" in normalized:
        return "hds_same_input_closure_mismatch"
    if (
        "runtime_ref_mismatch" in normalized
        or "payload_mismatch" in normalized
        or "ref_not_cas" in normalized
        or "cas_missing" in normalized
        or "output_ref_missing" in normalized
    ):
        return "hds_ref_identity_mismatch"
    return "hds_unknown_provenance"


def _scorecard_invariant_ref_keys() -> frozenset[str]:
    try:
        registry = load_production_invariant_registry(strict=True)
    except (FileNotFoundError, InvariantRegistryError, ValueError):
        return frozenset()
    return frozenset(
        ref_key
        for invariant in registry.invariants
        if "runtime.scorecard" in invariant.consumers
        for ref_key in invariant.required_ref_keys
    )


def _report_authority_envelope(report: Any) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    envelope = report.get("authority_envelope")
    return dict(envelope) if isinstance(envelope, dict) else None


def _payload_without_authority_envelope(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    sanitized = dict(payload)
    sanitized.pop("authority_envelope", None)
    return sanitized


def _authority_contract_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    quality_evidence_bundle_path: str | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []

    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    registry_ref_keys = _scorecard_invariant_ref_keys()
    gates: list[dict[str, Any]] = []
    validated_envelopes: list[EvidenceAuthorityEnvelope] = []
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        if registry_ref_keys and ref_key not in registry_ref_keys:
            continue
        report = quality_evidence.get(report_key)
        if not isinstance(report, dict):
            continue

        runtime_ref = authority_refs.get(ref_key)
        if runtime_ref is None:
            continue

        gate_name, stage, layer = QUALITY_REPORT_GATE_METADATA[report_key]
        evidence_ref = f"quality_evidence/{QUALITY_REPORT_FILES[report_key]}"

        def append_failure(
            code: str,
            message: str,
            *,
            gate_name: str = gate_name,
            stage: str = stage,
            layer: str = layer,
            evidence_ref: str = evidence_ref,
            envelope: Mapping[str, Any] | None = None,
            authority_error_code: str | None = None,
            domain_failure_code: str | None = None,
            first_failing_artifact_ref: str | None = None,
            owner: str | None = None,
            next_action: str | None = None,
            phase: str = "authority_contract",
        ) -> None:
            classification = classify_authority_failure(
                authority_error_code=authority_error_code or code,
                domain_failure_code=domain_failure_code or code,
                envelope=envelope,
                artifact_ref=first_failing_artifact_ref or runtime_ref or evidence_ref,
                owner=owner,
                next_action=next_action
                or (
                    "Emit runtime authority evidence with a producer identity, "
                    "diagnostic event ref, CAS ref, and schema identity."
                ),
            )
            gates.append(
                _gate(
                    name=gate_name,
                    stage=stage,
                    code=code,
                    status="fail",
                    layer=layer,
                    phase=phase,
                    message=message,
                    evidence_ref=evidence_ref,
                    next_action=classification.next_action,
                    owner=classification.owner,
                    root_cause_class=classification.root_cause_class,
                    first_failing_artifact_ref=classification.first_failing_artifact_ref,
                    producer_authority=classification.producer_authority,
                    authority_failure_code=classification.authority_failure_code,
                    domain_failure_code=classification.domain_failure_code,
                )
            )

        if _is_bundle_local_ref(runtime_ref):
            append_failure(
                "hds_bundle_ref_used_as_runtime_ref",
                f"Runtime-owned {ref_key} points at bundle-local evidence.",
            )
        elif not _is_cas_authority_ref(runtime_ref):
            append_failure(
                "hds_ref_identity_mismatch",
                f"Runtime-owned {ref_key} is not a CAS authority ref.",
            )

        embedded_ref = _sanitize_ref(report.get(ref_key))
        if embedded_ref is not None and embedded_ref != runtime_ref:
            append_failure(
                "hds_ref_identity_mismatch",
                f"Embedded {ref_key} does not match the runtime CAS ref.",
            )

        envelope = _report_authority_envelope(report)
        if envelope is None:
            append_failure(
                "hds_unknown_provenance",
                f"Runtime-owned {ref_key} is missing an authority envelope.",
                authority_error_code="hds_unknown_provenance",
            )
            continue

        envelope_ref = _sanitize_ref(envelope.get("cas_ref") or envelope.get("artifact_ref"))
        if envelope_ref is not None and envelope_ref != runtime_ref:
            append_failure(
                "hds_ref_identity_mismatch",
                f"Authority envelope CAS ref does not match runtime-owned {ref_key}.",
            )

        ownership_issues = authority_envelope_ownership_issues(
            envelope=envelope,
            report_key=report_key,
            report=report,
            ref_key=ref_key,
            runtime_ref=runtime_ref,
        )
        if ownership_issues:
            append_failure(
                "hds_borrowed_authority_envelope",
                (
                    "Authority envelope is owned by a different report kind and "
                    "cannot satisfy this report's producer authority."
                ),
                envelope=envelope,
                authority_error_code="hds_borrowed_authority_envelope",
                first_failing_artifact_ref=runtime_ref,
                owner=_SPOOF_OWNER_BY_LAYER.get(layer),
                next_action=str(
                    ownership_issues[0].get("next_action")
                    or (
                        "Mint a report-specific authority envelope with matching "
                        "artifact kind, schema, phase, validation status, and runtime event."
                    )
                ),
            )
            continue

        envelope_evidence_class = str(envelope.get("evidence_class") or "").casefold()
        envelope_authority_role = str(envelope.get("authority_role") or "").casefold()
        envelope_provenance_kind = str(envelope.get("provenance_kind") or "").casefold()
        if "legacy" in " ".join(
            (envelope_evidence_class, envelope_authority_role, envelope_provenance_kind)
        ):
            append_failure(
                "legacy_migration_legacy_used_as_authority",
                "Legacy-compatible migration evidence cannot satisfy serious closeout.",
                envelope=envelope,
                authority_error_code="legacy_migration_legacy_used_as_authority",
            )
            continue
        if (
            envelope_evidence_class in {"public_exported", "redacted_derived"}
            or envelope_authority_role
            in {
                "approval_input",
                "diagnostic_only",
                "not_authoritative",
                "packaging_only",
                "projection_only",
                "readiness_input",
                "scorecard_input",
            }
            or envelope_provenance_kind
            in {"bundle_overlay", "bundle_packaged", "runtime_projection"}
        ):
            append_failure(
                "hds_projection_used_as_authority",
                (
                    "Projection or redacted-derived authority envelope cannot satisfy "
                    "serious closeout."
                ),
                envelope=envelope,
                authority_error_code="hds_projection_used_as_authority",
            )
            continue

        try:
            validated = assert_runtime_emitted(deserialize_authority_envelope(envelope))
        except Exception as exc:
            error_code = (
                exc.code if isinstance(exc, AuthorityEnvelopeError) else "authority_invalid"
            )
            append_failure(
                _hds_authority_failure_code(str(error_code)),
                "Authority envelope cannot satisfy serious runtime authority.",
                envelope=envelope,
                authority_error_code=str(error_code),
            )
            continue

        if not _payload_hash_matches_runtime_ref(
            payload_sha256=validated.payload_sha256,
            runtime_ref=runtime_ref,
        ):
            append_failure(
                "hds_ref_identity_mismatch",
                "Authority envelope payload hash does not match the scored CAS ref.",
            )

        if validated.validation_status != "pass" and validated.provenance_kind != "runtime_blocker":
            domain_code = _domain_failure_code_for_report(
                report_key=report_key,
                report=report,
            )
            domain_phase = _domain_phase_for_report(report_key=report_key, report=report)
            append_failure(
                domain_code,
                (
                    "Runtime-owned authority evidence failed its producer domain "
                    "validation; provenance is present."
                ),
                envelope=validated.model_dump(mode="json"),
                domain_failure_code=domain_code,
                first_failing_artifact_ref=runtime_ref,
                owner=_SPOOF_OWNER_BY_LAYER.get(layer, validated.owner),
                next_action=_domain_next_action_for_report(
                    report=report,
                    default=(
                        f"Repair producer-owned {report_key} domain evidence and "
                        "rerun scorecard aggregation."
                    ),
                ),
                phase=domain_phase,
            )
        validated_envelopes.append(validated)

    if len(validated_envelopes) > 1:
        try:
            assert_same_input_closure(validated_envelopes)
        except AuthorityEnvelopeError:
            gates.append(
                _gate(
                    name="scorecard_authority_same_input_closure",
                    stage="ops",
                    code="hds_same_input_closure_mismatch",
                    status="fail",
                    layer="quality_scorecard",
                    phase="authority_contract",
                    message="Required authority evidence does not share a closed input context.",
                    evidence_ref="quality_evidence",
                    next_action=(
                        "Rebuild required evidence from the same policy intent, run, "
                        "tenant, time, data, legal, method, mode, and fallback context."
                    ),
                )
            )
    return gates


def _diagnostic_event_records(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    events: list[dict[str, Any]] = []
    for value in _nested_find_all(payload, "diagnostic_events"):
        if isinstance(value, list):
            events.extend(dict(item) for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            events.append(dict(value))
    return events


def _diagnostic_event_log_refs(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[str]:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    return [
        ref
        for ref in (
            _sanitize_ref(value) for value in _nested_find_all(payload, "diagnostic_event_log_ref")
        )
        if ref is not None
    ]


def _event_sampling_decision(event: dict[str, Any]) -> tuple[str, float | None]:
    sampling = event.get("sampling")
    if isinstance(sampling, dict):
        decision = str(sampling.get("decision") or "").strip()
        rate = sampling.get("rate")
    else:
        decision = str(event.get("sampling_decision") or "").strip()
        rate = event.get("sampling_rate")
    try:
        parsed_rate = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        parsed_rate = None
    return decision, parsed_rate


def _event_sampled_away(event: dict[str, Any]) -> bool:
    decision, rate = _event_sampling_decision(event)
    normalized = decision.replace("-", "_").casefold()
    return normalized in {"drop", "dropped", "sampled", "sampled_away"} or (
        rate is not None and rate < 1.0
    )


def _diagnostic_event_ref_values(event: dict[str, Any]) -> list[str]:
    event_refs = [
        _sanitize_ref(event.get("artifact_ref")),
        _sanitize_ref(event.get("runtime_cas_ref")),
    ]
    raw_artifact_refs = event.get("artifact_refs")
    if isinstance(raw_artifact_refs, list):
        event_refs.extend(_sanitize_ref(item) for item in raw_artifact_refs)
    return [ref for ref in event_refs if ref is not None]


def _scorecard_event_failure_code(code: str) -> str:
    if code in {
        "authority_event_collision",
        "authority_orphan_cas",
        "authority_payload_mismatch",
        "authority_tenant_conflict",
        "diagnostic_event_ref_mismatch",
    }:
        return "hds_event_reconciliation_failed"
    return code


def _diagnostic_event_gates(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []

    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    runtime_payload = {"job": job_payload or {}, "run": run_payload or {}}
    log_refs = _diagnostic_event_log_refs(job_payload=job_payload, run_payload=run_payload)
    events = _diagnostic_event_records(job_payload=job_payload, run_payload=run_payload)
    gates: list[dict[str, Any]] = []

    if not log_refs or not events:
        gates.append(
            _gate(
                name="serious_diagnostic_event_log_present",
                stage="ops",
                code="serious_diagnostic_event_missing",
                status="fail",
                layer="runtime_diagnostics",
                phase="diagnostic_events",
                message="Serious closeout requires a runtime diagnostic event log.",
                evidence_ref=log_refs[0] if log_refs else None,
                next_action="Persist unsampled runtime diagnostic events before closeout.",
            )
        )
        return gates

    runtime_refs = {
        ref_key: runtime_ref
        for ref_key in QUALITY_REPORT_RUNTIME_REFS.values()
        if (runtime_ref := authority_refs.get(ref_key)) is not None
    }
    runtime_authority_ref_values = set(authority_refs.refs.values())
    event_ref_values: set[str] = set()
    named_runtime_event_ref_keys: set[str] = set()
    event_identity: dict[str, tuple[str | None, tuple[str, ...]]] = {}

    def append_failure(code: str, message: str, *, evidence_ref: str | None = None) -> None:
        scorecard_code = _scorecard_event_failure_code(code)
        gates.append(
            _gate(
                name="serious_diagnostic_event_log_present",
                stage="ops",
                code=scorecard_code,
                status="fail",
                layer="runtime_diagnostics",
                phase="diagnostic_events",
                message=(
                    message if scorecard_code == code else f"{message} Reconciliation code: {code}."
                ),
                evidence_ref=evidence_ref or log_refs[0],
                next_action="Reconcile diagnostic event refs against runtime CAS refs.",
            )
        )

    for event in events:
        if _event_sampled_away(event):
            append_failure(
                "serious_diagnostic_event_sampled_away",
                "Serious-run authority diagnostic events must not be sampled away.",
            )

        event_name = str(event.get("event_name") or event.get("event_type") or "")
        event_refs = _diagnostic_event_ref_values(event)
        event_ref_values.update(event_refs)
        event_id = _clean_text(event.get("event_id"))
        if event_id is not None:
            identity = (_sanitize_ref(event.get("payload_ref")), tuple(sorted(event_refs)))
            previous_identity = event_identity.get(event_id)
            if previous_identity is not None and previous_identity != identity:
                append_failure(
                    "authority_event_collision",
                    "Diagnostic event id points at different payload or artifact refs.",
                )
            else:
                event_identity[event_id] = identity

        for event_ref in event_refs:
            if not _is_cas_authority_ref(event_ref):
                append_failure(
                    "authority_ref_not_cas",
                    "Diagnostic event authority ref is not a CAS ref.",
                )
            elif runtime_authority_ref_values and event_ref not in runtime_authority_ref_values:
                append_failure(
                    "authority_cas_missing",
                    "Diagnostic event references a CAS artifact absent from runtime refs.",
                )

        event_tenant_id = _clean_text(event.get("tenant_id"))
        runtime_tenant_id = _clean_text(_nested_get(runtime_payload, "tenant_id"))
        if (
            event_tenant_id is not None
            and runtime_tenant_id is not None
            and event_tenant_id != runtime_tenant_id
        ):
            append_failure(
                "authority_tenant_conflict",
                "Diagnostic event tenant does not match the runtime authority context.",
            )

        payload_sha256 = _sanitize_ref(event.get("payload_sha256"))
        runtime_payload_sha256 = _sanitize_ref(event.get("runtime_payload_sha256"))
        if (
            payload_sha256 is not None
            and runtime_payload_sha256 is not None
            and payload_sha256 != runtime_payload_sha256
        ):
            append_failure(
                "authority_payload_mismatch",
                "Diagnostic event payload hash does not match runtime payload hash.",
            )

        event_type = str(event.get("event_type") or "").casefold()
        replay_status = str(
            event.get("replay_status") or event.get("drift_status") or ""
        ).casefold()
        if (
            "replay_result" in event_type
            and replay_status in {"drifted", "mismatched", "failed"}
            and not _sanitize_ref(event.get("drift_explanation_ref"))
        ):
            append_failure(
                "authority_replay_drift_unexplained",
                "Replay drift diagnostic event is missing an explanation ref.",
            )

        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
            if report_key not in event_name and ref_key not in event_name:
                continue
            runtime_ref = authority_refs.get(ref_key)
            if runtime_ref is None:
                continue
            if runtime_ref in event_refs:
                named_runtime_event_ref_keys.add(ref_key)
            mismatched_refs = [ref for ref in event_refs if ref != runtime_ref]
            if mismatched_refs:
                append_failure(
                    "diagnostic_event_ref_mismatch",
                    f"Diagnostic event artifact refs do not match runtime-owned {ref_key}.",
                )
    for ref_key, runtime_ref in runtime_refs.items():
        if not _is_cas_authority_ref(runtime_ref):
            append_failure(
                "authority_ref_not_cas",
                f"Runtime-owned {ref_key} is not a CAS authority ref.",
            )
        elif runtime_ref not in event_ref_values:
            append_failure(
                "authority_orphan_cas",
                f"Runtime-owned {ref_key} has no matching diagnostic event.",
            )
        elif ref_key not in named_runtime_event_ref_keys:
            append_failure(
                "authority_orphan_cas",
                f"Runtime-owned {ref_key} has no matching named diagnostic event.",
            )
    return gates


def _lex_no_norm_authority_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    report = quality_evidence.get("normative_evidence")
    if not isinstance(report, dict):
        return []
    retrieval_status = str(report.get("retrieval_status") or "").strip().casefold()
    no_norms = retrieval_status == "no_norms_retrieved" or (
        not report.get("applied_norms") and not report.get("candidate_norms")
    )
    blockers = report.get("authority_blockers")
    if not no_norms or blockers:
        return []
    return [
        _gate(
            name="normative_evidence_present",
            stage="lex",
            code="lex_no_norm_authority_blocker_missing",
            status="fail",
            layer="lex",
            phase="normative_authority",
            message="No retrieved norms must be represented as a Lex authority blocker.",
            evidence_ref="quality_evidence/normative_evidence.json",
            next_action="Emit a Lex no-norm authority blocker before scorecard closeout.",
        )
    ]


def _semantic_binding_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    ledger_payload = _payload_without_authority_envelope(
        quality_evidence.get("semantic_binding_ledger")
    )
    if isinstance(ledger_payload, dict):
        ledger_payload = {
            key: value
            for key, value in ledger_payload.items()
            if key
            not in {
                "authority_envelope_ref",
                "runtime_event_ref",
                "manifest_ref",
                "payload_sha256",
                "semantic_binding_ledger_ref",
            }
        }
    if ledger_payload:
        try:
            ledger = deserialize_semantic_binding_ledger(ledger_payload)
        except (TypeError, ValueError) as exc:
            return [
                _gate(
                    name="semantic_binding_ledger_valid",
                    stage="policy_output",
                    code="semantic_binding_ledger_invalid",
                    status="fail",
                    layer="semantic_binding",
                    phase="semantic_binding",
                    message=f"Semantic binding ledger is invalid: {exc}",
                    evidence_ref="quality_evidence/semantic_binding_ledger.json",
                    next_action=(
                        "Regenerate the semantic binding ledger with Lex, Fabric, "
                        "Foundry, Scientist, and final compiler binding records."
                    ),
                )
            ]
        evaluation = evaluate_semantic_binding_ledger(ledger)
        semantic_quality_evidence = dict(quality_evidence)
        for report_key in _semantic_binding_envelope_report_keys():
            report = semantic_quality_evidence.get(report_key)
            if not isinstance(report, dict):
                continue
            envelope = report.get("authority_envelope")
            if not isinstance(envelope, dict) or envelope.get("semantic_binding_ref"):
                continue
            updated_report = dict(report)
            updated_envelope = dict(envelope)
            updated_envelope["semantic_binding_ref"] = ledger.semantic_binding_ref
            updated_report["authority_envelope"] = updated_envelope
            semantic_quality_evidence[report_key] = updated_report
        issues = [
            *evaluation.issues,
            *authority_envelopes_missing_semantic_binding_ref(
                ledger=ledger,
                quality_evidence=semantic_quality_evidence,
                report_keys=_semantic_binding_envelope_report_keys(),
            ),
        ]
        if issues:
            return [
                _gate(
                    name="semantic_binding_ledger_valid",
                    stage="policy_output",
                    code=issue.code,
                    status="fail",
                    layer=issue.layer,
                    phase=issue.phase,
                    message=issue.message,
                    evidence_ref="quality_evidence/semantic_binding_ledger.json",
                    next_action=issue.next_action,
                    missing_input=issue.missing_input,
                    conflicting_producer=issue.conflicting_producer,
                    affected_claim=issue.affected_claim or issue.claim_id,
                    next_command=issue.next_command,
                )
                for issue in issues
            ]
        if evaluation.status == "blocked":
            code = (
                "semantic_retrieval_failure_blocker"
                if evaluation.reason_family == "retrieval_failure"
                else "semantic_no_relevant_evidence_blocker"
            )
            return [
                _gate(
                    name="semantic_binding_ledger_valid",
                    stage="policy_output",
                    code=code,
                    status="fail",
                    layer="semantic_binding",
                    phase="semantic_binding",
                    message=(
                        "Semantic binding ledger emitted a typed blocker: "
                        f"{evaluation.reason_family}."
                    ),
                    evidence_ref="quality_evidence/semantic_binding_ledger.json",
                    next_action=(
                        "Resolve the typed semantic blocker or keep the final claim "
                        "blocked instead of closing the run."
                    ),
                )
            ]
        return []
    if not _semantic_binding_required_for_serious(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    ):
        return []
    return [
        _gate(
            name="policy_grounding_matrix_present",
            stage="policy_output",
            code="hds_semantic_binding_missing",
            status="fail",
            layer="scientist_policy_artifacts",
            phase="semantic_binding",
            message="Serious policy closeout claims require a semantic binding ledger.",
            evidence_ref="quality_evidence/policy_grounding_matrix.json",
            next_action="Persist semantic binding ledger evidence before serious closeout.",
        )
    ]


def _semantic_binding_required_for_serious(
    *,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> bool:
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    grounding = quality_evidence.get("policy_grounding_matrix")
    if isinstance(grounding, dict):
        claims = [row for row in grounding.get("claims") or [] if isinstance(row, dict)]
        for claim in claims:
            if (
                claim.get("major")
                or claim.get("data_refs")
                or claim.get("method_refs")
                or claim.get("norm_refs")
                or str(claim.get("claim_type") or "").casefold()
                in {
                    "recommendation",
                    "legal",
                    "legal_assertion",
                    "budget",
                    "budget_feasibility",
                    "distributional_impact",
                    "implementation_risk",
                    "monitoring",
                    "residual_uncertainty",
                }
            ):
                return True
        if claims and authority_refs.get("policy_grounding_matrix_ref") is not None:
            return True
    normative = quality_evidence.get("normative_evidence")
    if isinstance(normative, dict) and (
        normative.get("applied_norms")
        or normative.get("candidate_norms")
        or normative.get("recommendation_claims")
    ):
        return True
    decision_quality = quality_evidence.get("decision_artifact_quality")
    return isinstance(decision_quality, dict) and bool(
        decision_quality.get("claim_evidence_contract")
        or decision_quality.get("decision_artifact_quality_report_ref")
    )


def _scholar_academic_evidence_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    if not scholar_academic_evidence_required(quality_evidence):
        return []
    report = quality_evidence.get("scholar_evidence")
    evidence_ref = f"quality_evidence/{SCHOLAR_ACADEMIC_EVIDENCE_FILENAME}"
    if not isinstance(report, dict):
        return [
            _gate(
                name="scholar_academic_evidence_present",
                stage="scientist",
                code="policy_design_scholar_academic_evidence_missing",
                status="fail",
                layer="scholar_literature",
                phase="scholar_academic_evidence",
                message=(
                    "Serious Policy Design Case literature claims require Scholar "
                    "academic and grey-literature evidence."
                ),
                evidence_ref=evidence_ref,
                next_action=(
                    "Emit Scholar research intent, query graph, provider traces, "
                    "source scoring, snippets, citations, freshness, corpus lineage, "
                    "source selection, support/conflict links, and blockers."
                ),
            )
        ]
    normalized = normalize_scholar_academic_evidence_report(report)
    issues = [issue for issue in normalized.get("issues", []) if isinstance(issue, dict)]
    if issues:
        return [
            _gate(
                name="scholar_academic_evidence_valid",
                stage="scientist",
                code=str(issue.get("code") or "policy_design_scholar_academic_evidence_invalid"),
                status="fail",
                layer="scholar_literature",
                phase=str(issue.get("phase") or "scholar_academic_evidence"),
                message=str(
                    issue.get("message")
                    or "Scholar academic evidence failed Phase 12.3 validation."
                ),
                evidence_ref=evidence_ref,
                next_action=str(
                    issue.get("next_action")
                    or "Regenerate Scholar academic and grey-literature evidence."
                ),
            )
            for issue in issues
        ]
    if normalized.get("status") == "blocked":
        return [
            _gate(
                name="scholar_academic_evidence_valid",
                stage="scientist",
                code="policy_design_scholar_literature_deficit_blocker",
                status="fail",
                layer="scholar_literature",
                phase="scholar_academic_evidence",
                message="Scholar emitted a literature-deficit blocker.",
                evidence_ref=evidence_ref,
                next_action=(
                    "Resolve the literature deficit or keep downstream claims blocked."
                ),
            )
        ]
    return [
        _gate(
            name="scholar_academic_evidence_valid",
            stage="scientist",
            code="scholar_academic_evidence_present",
            status="pass",
            layer="scholar_literature",
            phase="scholar_academic_evidence",
            message="Scholar academic and grey-literature evidence is present.",
            evidence_ref=evidence_ref,
            next_action=None,
            blocking=False,
        )
    ]


def _semantic_binding_envelope_report_keys() -> tuple[str, ...]:
    return (
        "normative_evidence",
        "fabric_retrieval_trace",
        "foundry_method_report",
        "policy_grounding_matrix",
        "conflict_check",
        "decision_artifact_quality",
    )


def _diagnostic_slo_readiness_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    return diagnostic_slo_gates(
        quality_evidence.get("diagnostic_slo_report"),
        canary_kind=canary_kind,
    )


def _assurance_case_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    report = quality_evidence.get("assurance_case")
    if not isinstance(report, dict):
        return [
            _gate(
                name="assurance_case_present",
                stage="ops",
                code="assurance_case_missing",
                status="fail",
                layer="assurance_case",
                phase="assurance_case",
                message="Serious closeout requires an assurance case.",
                evidence_ref="quality_evidence/assurance_case.json",
                next_action="Build assurance_case.json before serious closeout.",
            )
        ]
    required = {
        "claim",
        "subclaims",
        "argument",
        "argument_strategy",
        "evidence",
        "assumptions",
        "contexts",
        "defeaters",
        "blockers",
        "unresolved_uncertainty",
        "confidence_limits",
        "non_overridable_blockers",
        "reviewer_attribution",
        "owner",
        "next_diagnostic_command",
    }
    missing = sorted(required - set(report))
    if missing:
        return [
            _gate(
                name="assurance_case_valid",
                stage="ops",
                code="assurance_case_invalid",
                status="fail",
                layer="assurance_case",
                phase="assurance_case",
                message="Assurance case is missing required fields: " + ", ".join(missing),
                evidence_ref="quality_evidence/assurance_case.json",
                next_action="Regenerate assurance_case.json from the final quality scorecard.",
            )
        ]
    blockers = report.get("non_overridable_blockers")
    if isinstance(blockers, list) and blockers:
        return [
            _gate(
                name="assurance_case_non_overridable_blockers",
                stage="ops",
                code="assurance_case_non_overridable_blockers",
                status="fail",
                layer="assurance_case",
                phase="assurance_case",
                message=(
                    "Assurance case preserves non-overridable blockers: "
                    + ", ".join(sorted(str(item) for item in blockers))
                ),
                evidence_ref="quality_evidence/assurance_case.json",
                next_action="Resolve non-overridable blockers before approval/publication.",
            )
        ]
    return []


def _policy_design_case_profile_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    report = quality_evidence.get("policy_design_case")
    if not isinstance(report, dict):
        return [
            _gate(
                name="policy_design_case_present",
                stage="ops",
                code="policy_design_case_missing",
                status="fail",
                layer="assurance_case",
                phase="policy_design_case_profile",
                message="Serious policy closeout requires a runtime-owned Policy Design Case.",
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action="Build policy_design_case.json through runtime-quality assurance_case.",
            )
        ]
    gates: list[dict[str, Any]] = []
    for field_name, code in POLICY_DESIGN_CASE_REQUIRED_SUBRECORDS.items():
        if isinstance(report.get(field_name), dict):
            continue
        gates.append(
            _gate(
                name=f"policy_design_case_{field_name}_present",
                stage="ops",
                code=code,
                status="fail",
                layer="assurance_case",
                phase="policy_design_case_profile",
                message=f"Serious policy closeout requires Policy Design Case {field_name}.",
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Regenerate policy_design_case.json from "
                    "polisyos.runtime.quality.assurance_case."
                ),
            )
        )
    try:
        validate_policy_design_case_profile(report)
    except PolicyDesignCaseAuthorityError as exc:
        gates.append(
            _gate(
                name="policy_design_case_profile_valid",
                stage="ops",
                code=exc.code,
                status="fail",
                layer="assurance_case",
                phase="policy_design_case_profile",
                message=str(exc),
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Regenerate policy_design_case.json from "
                    "polisyos.runtime.quality.assurance_case."
                ),
            )
        )
    return gates


def _policy_design_wave29_self_fmea_and_partial_state_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    return [
        *_policy_design_self_fmea_gates(case),
        *_policy_design_partial_state_consistency_gates(case),
    ]


def _policy_design_self_fmea_gates(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    record = case.get("non_adversarial_self_fmea") or case.get("self_fmea")
    if not isinstance(record, Mapping):
        return [
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_record_missing",
                message=(
                    "Serious Policy Design Case closeout requires a non-adversarial "
                    "self-FMEA record."
                ),
                missing_input="non_adversarial_self_fmea",
            )
        ]

    gates: list[dict[str, Any]] = []
    if _clean_text(record.get("schema_version")) != POLICY_DESIGN_SELF_FMEA_SCHEMA_VERSION:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_schema_invalid",
                message="Non-adversarial self-FMEA must use the Phase 29.2 schema.",
                evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                missing_input="non_adversarial_self_fmea.schema_version",
            )
        )
    if _clean_text(record.get("record_family")) != "integrity_self_fmea_and_maturity.v1":
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_record_family_invalid",
                message=(
                    "Non-adversarial self-FMEA must belong to "
                    "integrity_self_fmea_and_maturity.v1."
                ),
                evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                missing_input="non_adversarial_self_fmea.record_family",
            )
        )
    if _profile_key(record.get("status")) not in POLICY_DESIGN_SELF_FMEA_PASSING_STATUSES:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_status_not_pass",
                message="Non-adversarial self-FMEA must be accepted, mitigated, or verified.",
                evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                missing_input="non_adversarial_self_fmea.status",
            )
        )
    for field in ("record_id", "case_id", "run_id", "job_id", "tenant_id"):
        if _clean_text(record.get(field)) is None:
            gates.append(
                _policy_design_wave29_gate(
                    code="policy_design_self_fmea_identity_missing",
                    message="Non-adversarial self-FMEA must include case-bound identity.",
                    evidence_ref=_clean_text(
                        record.get("evidence_ref") or record.get("cas_ref")
                    ),
                    missing_input=f"non_adversarial_self_fmea.{field}",
                )
            )
    if not _policy_design_runtime_artifact_ref(
        record.get("evidence_ref") or record.get("cas_ref")
    ):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_runtime_evidence_missing",
                message="Non-adversarial self-FMEA must cite runtime CAS/artifact evidence.",
                evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                missing_input="non_adversarial_self_fmea.evidence_ref",
            )
        )
    if not _policy_design_runtime_event_ref(record.get("runtime_event_ref")):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_runtime_event_missing",
                message="Non-adversarial self-FMEA must cite a runtime diagnostic event.",
                evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                missing_input="non_adversarial_self_fmea.runtime_event_ref",
            )
        )

    rows = _policy_design_self_fmea_rows(record)
    rows_by_mode: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        mode = _policy_design_failure_mode_key(row)
        if mode:
            rows_by_mode.setdefault(mode, []).append(row)
    for mode in POLICY_DESIGN_SELF_FMEA_REQUIRED_FAILURE_MODES:
        mode_rows = rows_by_mode.get(mode, [])
        if not mode_rows:
            gates.append(
                _policy_design_wave29_gate(
                    code="policy_design_self_fmea_failure_mode_missing",
                    message=f"Non-adversarial self-FMEA is missing {mode}.",
                    evidence_ref=_clean_text(record.get("evidence_ref") or record.get("cas_ref")),
                    missing_input=f"non_adversarial_self_fmea.failure_modes.{mode}",
                )
            )
            continue
        for row in mode_rows:
            gates.extend(_policy_design_self_fmea_row_gates(row, mode=mode))
    return gates


def _policy_design_self_fmea_rows(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in ("failure_modes", "fmea_records", "records", "failure_mode_records"):
        value = record.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return tuple(rows)


def _policy_design_failure_mode_key(row: Mapping[str, Any]) -> str | None:
    for key in ("failure_mode", "failure_mode_id", "mode", "kind", "category"):
        text = _clean_text(row.get(key))
        if text:
            return text.casefold().replace("-", "_")
    return None


def _policy_design_self_fmea_row_gates(
    row: Mapping[str, Any],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    row_ref = _clean_text(row.get("evidence_ref") or row.get("cas_ref"))
    if _profile_key(row.get("status") or row.get("mitigation_status")) not in (
        POLICY_DESIGN_SELF_FMEA_PASSING_STATUSES
    ):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_failure_mode_unmitigated",
                message=f"Self-FMEA failure mode {mode} must have accepted mitigation.",
                evidence_ref=row_ref,
                missing_input=f"non_adversarial_self_fmea.failure_modes.{mode}.status",
            )
        )
    controls = row.get("mitigation_controls") or row.get("controls")
    if not isinstance(controls, list) or not controls:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_failure_mode_controls_missing",
                message=f"Self-FMEA failure mode {mode} must list mitigation controls.",
                evidence_ref=row_ref,
                missing_input=(
                    f"non_adversarial_self_fmea.failure_modes.{mode}.mitigation_controls"
                ),
            )
        )
    if not _policy_design_runtime_artifact_ref(row.get("evidence_ref") or row.get("cas_ref")):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_failure_mode_evidence_missing",
                message=f"Self-FMEA failure mode {mode} must cite runtime evidence.",
                evidence_ref=row_ref,
                missing_input=f"non_adversarial_self_fmea.failure_modes.{mode}.evidence_ref",
            )
        )
    if not _policy_design_runtime_event_ref(row.get("runtime_event_ref")):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_self_fmea_failure_mode_event_missing",
                message=f"Self-FMEA failure mode {mode} must cite a runtime event.",
                evidence_ref=row_ref,
                missing_input=(
                    f"non_adversarial_self_fmea.failure_modes.{mode}.runtime_event_ref"
                ),
            )
        )
    return gates


def _policy_design_partial_state_consistency_gates(
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    record = case.get("partial_state_consistency") or case.get("partial_case_contradictions")
    if not isinstance(record, Mapping):
        return [
            _policy_design_wave29_gate(
                code="policy_design_partial_state_consistency_record_missing",
                message=(
                    "Serious Policy Design Case closeout requires partial-state "
                    "consistency evidence."
                ),
                missing_input="partial_state_consistency",
            )
        ]

    gates: list[dict[str, Any]] = []
    record_ref = _clean_text(record.get("evidence_ref") or record.get("cas_ref"))
    if _clean_text(record.get("schema_version")) != POLICY_DESIGN_PARTIAL_STATE_SCHEMA_VERSION:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_schema_invalid",
                message="Partial-state consistency must use the Phase 29.2 schema.",
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.schema_version",
            )
        )
    if _clean_text(record.get("record_family")) != "integrity_self_fmea_and_maturity.v1":
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_record_family_invalid",
                message=(
                    "Partial-state consistency must belong to "
                    "integrity_self_fmea_and_maturity.v1."
                ),
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.record_family",
            )
        )
    if _profile_key(record.get("status")) not in POLICY_DESIGN_PARTIAL_STATE_PASSING_STATUSES:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_status_not_pass",
                message="Partial-state consistency record must be passing.",
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.status",
            )
        )
    for field in ("record_id", "case_id", "run_id", "job_id", "tenant_id"):
        if _clean_text(record.get(field)) is None:
            gates.append(
                _policy_design_wave29_gate(
                    code="policy_design_partial_state_identity_missing",
                    message="Partial-state consistency must include case-bound identity.",
                    evidence_ref=record_ref,
                    missing_input=f"partial_state_consistency.{field}",
                )
            )
    if not _policy_design_runtime_artifact_ref(
        record.get("evidence_ref") or record.get("cas_ref")
    ):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_runtime_evidence_missing",
                message="Partial-state consistency must cite runtime CAS/artifact evidence.",
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.evidence_ref",
            )
        )
    if not _policy_design_runtime_event_ref(record.get("runtime_event_ref")):
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_runtime_event_missing",
                message="Partial-state consistency must cite a runtime diagnostic event.",
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.runtime_event_ref",
            )
        )

    rows = _policy_design_partial_state_authoritative_rows(record)
    if not rows:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_authoritative_records_missing",
                message=(
                    "Partial-state consistency must list the authoritative records "
                    "checked for contradictions."
                ),
                evidence_ref=record_ref,
                missing_input="partial_state_consistency.authoritative_records",
            )
        )
        return gates

    values_by_field: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    invalid_rows: list[Mapping[str, Any]] = []
    for row in rows:
        field = _policy_design_partial_state_field_key(row)
        if field is None or ("value" not in row and "authoritative_value" not in row):
            invalid_rows.append(row)
            continue
        value = row.get("value") if "value" in row else row.get("authoritative_value")
        fingerprint = _policy_design_value_fingerprint(value)
        values_by_field.setdefault(field, {}).setdefault(fingerprint, []).append(row)

    for row in invalid_rows:
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_authoritative_record_invalid",
                message=(
                    "Partial-state authoritative records must include a checked field "
                    "and value."
                ),
                evidence_ref=_clean_text(row.get("evidence_ref") or record_ref),
                missing_input="partial_state_consistency.authoritative_records.field",
            )
        )
    for field, values in sorted(values_by_field.items()):
        if len(values) <= 1:
            continue
        conflicting_rows = [rows_for_value[0] for rows_for_value in values.values()]
        evidence_ref = _clean_text(
            conflicting_rows[0].get("evidence_ref")
            or conflicting_rows[0].get("cas_ref")
            or record_ref
        )
        gates.append(
            _policy_design_wave29_gate(
                code="policy_design_partial_state_authority_contradiction",
                message=(
                    "Partial-state consistency found mutually inconsistent "
                    f"authoritative records for {field}."
                ),
                evidence_ref=evidence_ref,
                missing_input=f"partial_state_consistency.authoritative_records.{field}",
            )
        )
    return gates


def _policy_design_partial_state_authoritative_rows(
    record: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "authoritative_records",
        "authority_records",
        "checked_authoritative_records",
        "records",
    ):
        value = record.get(key)
        if isinstance(value, list):
            rows.extend(
                item
                for item in value
                if isinstance(item, Mapping) and _policy_design_partial_state_authoritative(item)
            )
    return tuple(rows)


def _policy_design_partial_state_authoritative(row: Mapping[str, Any]) -> bool:
    if row.get("authoritative") is True:
        return True
    role = _profile_key(row.get("authority_role") or row.get("source_role") or row.get("role"))
    if not role:
        return False
    return role == "authoritative" or ("authority" in role and role != "not_authoritative")


def _policy_design_partial_state_field_key(row: Mapping[str, Any]) -> str | None:
    for key in ("field", "field_path", "field_family", "state_field"):
        text = _clean_text(row.get(key))
        if text:
            return text
    return None


def _policy_design_value_fingerprint(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _policy_design_wave29_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave29_integrity",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_integrity_self_fmea",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit Phase 29.2 integrity records with non-adversarial self-FMEA, "
            "runtime evidence refs, and partial-state contradiction checks before "
            "serious closeout."
        ),
        missing_input=missing_input,
    )


def _policy_design_wave30_run_cost_proportionality_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []

    gates: list[dict[str, Any]] = []
    blocker_rows = _policy_design_run_cost_blocker_rows(case)
    valid_blockers: list[Mapping[str, Any]] = []
    for blocker in blocker_rows:
        try:
            valid_blockers.append(validate_run_cost_proportionality_blocker(blocker))
        except RunCostProportionalityError as exc:
            gates.append(
                _policy_design_wave30_run_cost_gate(
                    code=exc.code,
                    message=str(exc),
                    evidence_ref=_clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref")),
                    missing_input=exc.field or "run_cost_proportionality_blockers",
                )
            )

    ledgers = _policy_design_run_cost_ledger_rows(case)
    if not ledgers:
        try:
            ledgers = (
                build_run_cost_proportionality_ledger_from_quality_context(
                    quality_evidence=quality_evidence,
                    case=case,
                    job_payload=job_payload,
                    run_payload=run_payload,
                    canary_kind=canary_kind,
                ),
            )
        except RunCostProportionalityError as exc:
            gates.append(
                _policy_design_wave30_run_cost_gate(
                    code=exc.code,
                    message=str(exc),
                    missing_input=exc.field or "run_cost_proportionality_ledgers",
                )
            )
    if not ledgers:
        if valid_blockers:
            return [
                *gates,
                *(
                    _policy_design_wave30_run_cost_gate(
                        code=str(blocker["code"]),
                        message=str(blocker["message"]),
                        evidence_ref=_clean_text(blocker.get("evidence_ref")),
                        missing_input="run_cost_proportionality_ledgers",
                    )
                    for blocker in valid_blockers
                ),
            ]
        gates.append(
            _policy_design_wave30_run_cost_gate(
                code="policy_design_run_cost_proportionality_ledger_missing",
                message=(
                    "Serious Policy Design Case runs must emit a run-cost "
                    "proportionality ledger or a typed run-cost blocker."
                ),
                missing_input="run_cost_proportionality_ledgers",
            )
        )
        return gates

    for ledger in ledgers:
        try:
            validate_run_cost_proportionality_ledger(ledger)
        except RunCostProportionalityError as exc:
            gates.append(
                _policy_design_wave30_run_cost_gate(
                    code=exc.code,
                    message=str(exc),
                    evidence_ref=_clean_text(ledger.get("evidence_ref") or ledger.get("cas_ref")),
                    missing_input=exc.field or "run_cost_proportionality_ledgers",
                )
            )

    for blocker in valid_blockers:
        gates.append(
            _policy_design_wave30_run_cost_gate(
                code=str(blocker["code"]),
                message=str(blocker["message"]),
                evidence_ref=_clean_text(blocker.get("evidence_ref")),
                missing_input="run_cost_proportionality_blockers",
            )
        )
    return gates


def _policy_design_run_cost_ledger_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "run_cost_proportionality_ledgers",
        "run_cost_proportionality_ledger",
        "run_cost_ledgers",
        "run_cost_ledger",
        "run_cost_proportionality",
    ):
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type in {"run_cost_ledger", "run_cost_proportionality_ledger"} or (
                node_family in {"run_cost", "run_cost_proportionality"}
            ):
                rows.append(node)
    return tuple(rows)


def _policy_design_run_cost_blocker_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "run_cost_proportionality_blockers",
        "run_cost_blockers",
        "evidence_depth_budget_blockers",
        "budget_proportionality_blockers",
    ):
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return tuple(rows)


def _policy_design_wave30_run_cost_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave30_run_cost_proportionality",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_run_cost_proportionality",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit the Wave 30 run-cost proportionality ledger with runtime "
            "performance budgets, Foundry and Scientist cost models, DOE/search "
            "budgets, provider spend, elapsed time, human-review burden, and "
            "evidence-depth budget rules; otherwise emit a typed runtime blocker."
        ),
        missing_input=missing_input or "run_cost_proportionality_ledgers",
    )


def _policy_design_wave31_best_in_class_benchmarking_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []

    result = validate_policy_design_best_in_class_benchmarking_records(case)
    return [
        _policy_design_wave31_best_in_class_benchmarking_gate(
            code=str(gate_fields["code"]),
            message=str(gate_fields["message"]),
            evidence_ref=(
                str(gate_fields["evidence_ref"])
                if gate_fields["evidence_ref"] is not None
                else "quality_evidence/policy_design_case.json"
            ),
            missing_input=str(gate_fields["field"]),
            affected_claim=(
                str(gate_fields["affected_claim"])
                if gate_fields["affected_claim"] is not None
                else None
            ),
            next_action=str(gate_fields["next_action"]),
        )
        for gate_fields in (issue.as_gate_fields() for issue in result.issues)
    ]


def _policy_design_wave31_best_in_class_benchmarking_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave31_best_in_class_benchmarking",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_best_in_class_benchmarking",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=next_action
        or (
            "Emit a Wave 31 best-in-class benchmarking record with required "
            "metric evidence, run-cost ledger refs, and proportionality refs."
        ),
        missing_input=missing_input or "best_in_class_benchmarking_records",
        affected_claim=affected_claim,
    )


def _policy_design_concept_spine_from_case(case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    spine = case.get("concept_spine")
    if isinstance(spine, Mapping):
        return spine
    nodes = case.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        if str(node.get("node_type") or "") == "concept_spine":
            return node
    return None


def _policy_design_concept_spine_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, dict):
        return []
    spine = _policy_design_concept_spine_from_case(case)
    if not isinstance(spine, Mapping):
        return [
            _gate(
                name="policy_design_concept_spine_present",
                stage="ops",
                code="policy_design_concept_spine_missing",
                status="fail",
                layer="assurance_case",
                phase="policy_design_concept_spine",
                message=(
                    "Serious policy closeout requires a runtime-owned concept spine "
                    "or typed concept blocker."
                ),
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Project concept_spine through polisyos.runtime.quality.assurance_case."
                ),
            )
        ]
    try:
        validated = validate_policy_design_case_concept_spine(spine)
    except PolicyDesignCaseAuthorityError as exc:
        return [
            _gate(
                name="policy_design_concept_spine_valid",
                stage="ops",
                code=exc.code,
                status="fail",
                layer="assurance_case",
                phase="policy_design_concept_spine",
                message=str(exc),
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Regenerate concept_spine from Fabric, Scientist, IR linker, "
                    "IR registry, and IR world projections."
                ),
            )
        ]
    gates: list[dict[str, Any]] = []
    for blocker in validated.get("blockers", []):
        if not isinstance(blocker, Mapping):
            continue
        gates.append(
            _gate(
                name="policy_design_concept_spine_blocker",
                stage="ops",
                code=str(blocker.get("code") or "policy_design_concept_spine_blocked"),
                status="fail",
                layer="assurance_case",
                phase="policy_design_concept_spine",
                message=(
                    str(blocker.get("downstream_impact"))
                    if blocker.get("downstream_impact")
                    else "Concept spine emitted a typed blocker."
                ),
                evidence_ref=str(
                    validated.get("concept_ref")
                    or validated.get("cas_ref")
                    or "quality_evidence/policy_design_case.json"
                ),
                next_action=str(
                    blocker.get("next_diagnostic_command")
                    or "Regenerate the concept spine with resolved bindings."
                ),
            )
        )
    if not gates and validated.get("status") != "pass":
        gates.append(
            _gate(
                name="policy_design_concept_spine_blocker",
                stage="ops",
                code="policy_design_concept_spine_blocked",
                status="fail",
                layer="assurance_case",
                phase="policy_design_concept_spine",
                message="Concept spine is blocked without a typed blocker.",
                evidence_ref=str(
                    validated.get("concept_ref")
                    or validated.get("cas_ref")
                    or "quality_evidence/policy_design_case.json"
                ),
                next_action=(
                    "Resolve concept spine gaps or emit an accepted typed blocker "
                    "before serious closeout."
                ),
            )
        )
    return gates


def _policy_design_jurisdiction_spine_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, dict):
        return []
    spine = case.get("jurisdiction_spine")
    if not isinstance(spine, dict):
        return [
            _gate(
                name="policy_design_jurisdiction_spine_present",
                stage="ops",
                code="policy_design_jurisdiction_spine_missing",
                status="fail",
                layer="assurance_case",
                phase="policy_design_jurisdiction_spine",
                message=(
                    "Serious policy closeout requires a runtime-owned jurisdiction spine "
                    "or typed jurisdiction blocker."
                ),
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Project jurisdiction_spine through polisyos.runtime.quality.assurance_case."
                ),
            )
        ]
    try:
        validated = validate_policy_design_jurisdiction_spine(spine)
    except PolicyDesignCaseAuthorityError as exc:
        return [
            _gate(
                name="policy_design_jurisdiction_spine_valid",
                stage="ops",
                code=exc.code,
                status="fail",
                layer="assurance_case",
                phase="policy_design_jurisdiction_spine",
                message=str(exc),
                evidence_ref="quality_evidence/policy_design_case.json",
                next_action=(
                    "Regenerate jurisdiction_spine from Lex, IR normative "
                    "arbitration, and cross-graph conflict surfaces."
                ),
            )
        ]
    gates: list[dict[str, Any]] = []
    for blocker in validated.get("blockers", []):
        if not isinstance(blocker, Mapping):
            continue
        gates.append(
            _gate(
                name="policy_design_jurisdiction_spine_blocker",
                stage="ops",
                code=str(blocker.get("code") or "policy_design_jurisdiction_spine_blocked"),
                status="fail",
                layer="assurance_case",
                phase="policy_design_jurisdiction_spine",
                message=(
                    str(blocker.get("downstream_impact"))
                    if blocker.get("downstream_impact")
                    else "Jurisdiction spine emitted a typed blocker."
                ),
                evidence_ref=str(
                    validated.get("jurisdiction_spine_ref")
                    or "quality_evidence/policy_design_case.json"
                ),
                next_action=str(
                    blocker.get("next_command")
                    or "Regenerate the jurisdiction spine with resolved competence."
                ),
            )
        )
    if not gates and validated.get("status") != "pass":
        unresolved = validated.get("unresolved_conflicts")
        first_conflict = (
            unresolved[0]
            if isinstance(unresolved, list) and unresolved and isinstance(unresolved[0], Mapping)
            else {}
        )
        gates.append(
            _gate(
                name="policy_design_jurisdiction_spine_blocker",
                stage="ops",
                code=str(
                    first_conflict.get("code")
                    or "policy_design_jurisdiction_unresolved_conflict_blocker"
                ),
                status="fail",
                layer="assurance_case",
                phase="policy_design_jurisdiction_spine",
                message=str(
                    first_conflict.get("message") or "Jurisdiction spine has unresolved conflicts."
                ),
                evidence_ref=str(
                    validated.get("jurisdiction_spine_ref")
                    or "quality_evidence/policy_design_case.json"
                ),
                next_action=(
                    "Resolve jurisdiction conflicts or emit an accepted typed blocker "
                    "before serious closeout."
                ),
            )
        )
    return gates


_POLICY_DESIGN_OPTIONS_PHASE = "policy_design_options_objectives_tradeoffs"
_POLICY_DESIGN_OPTIONS_EVIDENCE_REF = "quality_evidence/policy_design_case.json"
_POLICY_DESIGN_OPTIONS_NEXT_ACTION = (
    "Regenerate options_objectives_tradeoffs from Foundry welfare and uncertainty, "
    "IR distributional/fairness/mobility/welfare analytics, and Scientist "
    "policy-design objectives before serious closeout."
)
_WAVE12_REQUIRED_PRODUCERS = (
    "lex",
    "data_forge",
    "scholar",
    "foundry",
    "options_objectives",
)
_WAVE12_PRODUCER_ALIASES = {
    "fabric": "fabric",
    "fabric_retrieval": "fabric",
    "source_selection": "fabric",
    "source_evidence": "fabric",
    "data": "fabric",
    "lex": "lex",
    "legal": "lex",
    "legal_authority": "lex",
    "normative_applicability": "lex",
    "data_forge": "data_forge",
    "dataforge": "data_forge",
    "data-forge": "data_forge",
    "scholar": "scholar",
    "academic": "scholar",
    "academic_evidence": "scholar",
    "grey_literature": "scholar",
    "foundry": "foundry",
    "method_quality": "foundry",
    "method_validity": "foundry",
    "options": "options_objectives",
    "objectives": "options_objectives",
    "options_objectives": "options_objectives",
    "option_objectives": "options_objectives",
    "options_objectives_tradeoffs": "options_objectives",
    "option_objective_tradeoff": "options_objectives",
}
_WAVE12_DEPENDENCY_KEYS = {
    "consumed_producer_refs",
    "input_producer_refs",
    "upstream_producer_refs",
    "dependency_producer_refs",
    "dependency_producers",
    "producer_dependencies",
    "consumes",
    "consumed_wave12_outputs",
}
_WAVE14_FINAL_CLAIM_PRODUCER_SPECS: dict[str, tuple[str, ...]] = {
    "lex": (
        "norm_refs",
        "legal_refs",
        "legal_evidence_refs",
        "normative_refs",
    ),
    "fabric": (
        "data_refs",
        "source_refs",
        "dataset_refs",
        "field_refs",
        "claim_support_feature_refs",
    ),
    "scholar": (
        "literature_refs",
        "academic_refs",
        "scholar_refs",
        "citation_refs",
    ),
    "foundry": (
        "method_refs",
        "method_evidence_refs",
        "uncertainty_refs",
    ),
    "options_objectives": (
        "objective_tradeoff_refs",
        "objective_refs",
        "tradeoff_refs",
        "welfare_refs",
    ),
}
_WAVE14_SELECTED_REF_KEYS = (
    "selected_candidate_refs",
    "selected_refs",
    "selected_evidence_refs",
    "selected_norm_refs",
    "selected_norms",
    "applied_norms",
    "selected_source_refs",
    "selected_dataset_source_refs",
    "selected_source_ids",
    "selected_sources",
    "selected_literature_refs",
    "selected_method_refs",
    "selected_methods",
    "selected_objective_refs",
    "selected_tradeoff_refs",
    "selected_option_refs",
)
_WAVE14_REJECTED_REF_KEYS = (
    "rejected_candidate_refs",
    "rejected_refs",
    "rejected_evidence_refs",
    "rejected_norm_refs",
    "rejected_norms",
    "rejected_source_refs",
    "rejected_dataset_source_refs",
    "rejected_sources",
    "rejected_literature_refs",
    "rejected_method_refs",
    "rejected_methods",
    "rejected_objective_refs",
    "rejected_tradeoff_refs",
    "rejected_option_refs",
    "rejected_options",
)
_WAVE14_SOURCE_RIGHTS_KEYS = (
    "source_rights_refs",
    "source_rights",
    "rights_refs",
    "rights",
    "license_refs",
)
_WAVE14_FRESHNESS_KEYS = (
    "freshness_refs",
    "source_freshness",
    "freshness",
    "freshness_ref",
    "as_of",
)
_WAVE14_QUALITY_KEYS = (
    "quality_refs",
    "quality",
    "quality_gates",
    "quality_gate_refs",
    "source_scoring",
)
_WAVE14_SNAPSHOT_KEYS = (
    "snapshot_refs",
    "snapshot_ref",
    "snapshot_id",
    "legal_snapshot_refs",
    "legal_corpus_snapshot",
    "data_forge_snapshot_refs",
    "corpus_lineage",
    "corpus_snapshot_ref",
    "manifest_ref",
    "manifest_artifact_id",
)
_WAVE14_BLOCKER_KEYS = (
    "blocker_refs",
    "blockers",
    "runtime_blockers",
    "authority_blockers",
    "data_gap_blocker_refs",
    "literature_deficit_blockers",
    "method_incompatibility_blocker_refs",
    "spine_blocker_refs",
)
_WAVE14_CONTRACT_REF_FIELDS = (
    "evidence_ref",
    "cas_ref",
    "runtime_event_ref",
    "static_inventory_ref",
    *_WAVE14_SELECTED_REF_KEYS,
    *_WAVE14_REJECTED_REF_KEYS,
    *_WAVE14_SOURCE_RIGHTS_KEYS,
    *_WAVE14_FRESHNESS_KEYS,
    *_WAVE14_QUALITY_KEYS,
    *_WAVE14_SNAPSHOT_KEYS,
    *_WAVE14_BLOCKER_KEYS,
)
_WAVE14_CONTRACT_TEXT_KEYS = frozenset(
    {
        "artifact_id",
        "artifact_ref",
        "cas_ref",
        "citation_id",
        "claim_support_feature_ref",
        "competence_ref",
        "evidence_id",
        "evidence_ref",
        "feature_ref",
        "id",
        "lineage_ref",
        "method_id",
        "norm_id",
        "objective_id",
        "option_id",
        "ref",
        "runtime_event_ref",
        "snapshot_id",
        "snapshot_ref",
        "source_id",
        "source_ref",
        "tradeoff_id",
        "uri",
        "value",
    }
)
_POLICY_DESIGN_LOCAL_REF_PREFIXES = (
    "/",
    "./",
    "../",
    "~",
    "file://",
    "repo://",
    "tests/",
    "tmp/",
    "var/folders/",
)
_WAVE21_REQUIRED_CLAIM_REF_SPECS = (
    (
        "concept_refs",
        ("concept_refs", "policy_concept_refs", "canonical_concept_refs"),
        "policy_design_major_claim_concept_refs_missing",
        "policy concept refs",
    ),
    (
        "legal_norm_refs",
        ("legal_norm_refs", "norm_refs", "legal_refs", "jurisdiction_refs"),
        "policy_design_major_claim_legal_norm_refs_missing",
        "legal norm refs",
    ),
    (
        "source_data_refs",
        ("source_data_refs", "data_refs", "source_refs", "dataset_refs"),
        "policy_design_major_claim_source_data_refs_missing",
        "source/data refs",
    ),
    (
        "method_refs",
        ("method_refs", "foundry_method_refs", "causal_method_refs"),
        "policy_design_major_claim_method_refs_missing",
        "method refs",
    ),
    (
        "portfolio_refs",
        ("portfolio_refs", "portfolio_design_refs", "evidence_portfolio_refs"),
        "policy_design_major_claim_portfolio_refs_missing",
        "evidence portfolio refs",
    ),
    (
        "independence_refs",
        ("independence_refs", "independence_map_refs", "evidence_independence_refs"),
        "policy_design_major_claim_independence_refs_missing",
        "independence refs",
    ),
    (
        "specification_curve_refs",
        (
            "specification_curve_refs",
            "multiverse_specification_curve_refs",
            "multiverse_curve_refs",
        ),
        "policy_design_major_claim_specification_curve_refs_missing",
        "specification-curve refs",
    ),
    (
        "disconfirming_refs",
        (
            "disconfirming_refs",
            "disconfirming_evidence_refs",
            "disconfirming_ledger_refs",
        ),
        "policy_design_major_claim_disconfirming_refs_missing",
        "disconfirming evidence refs",
    ),
    (
        "synthesis_refs",
        ("synthesis_refs", "synthesis_report_refs", "evidence_synthesis_refs"),
        "policy_design_major_claim_synthesis_refs_missing",
        "synthesis refs",
    ),
    (
        "objective_tradeoff_refs",
        (
            "objective_tradeoff_refs",
            "objective_refs",
            "tradeoff_refs",
        ),
        "policy_design_major_claim_objective_tradeoff_refs_missing",
        "objective/tradeoff refs",
    ),
    (
        "uncertainty_refs",
        ("uncertainty_refs", "residual_uncertainty_refs", "foundry_uncertainty_refs"),
        "policy_design_major_claim_uncertainty_refs_missing",
        "uncertainty refs",
    ),
    (
        "numerical_semantics_refs",
        ("numerical_semantics_refs", "number_semantics_refs", "unit_semantics_refs"),
        "policy_design_major_claim_numerical_semantics_refs_missing",
        "numerical semantics refs",
    ),
    (
        "monitoring_refs",
        (
            "monitoring_refs",
            "implementation_monitoring_refs",
            "monitoring_plan_refs",
            "implementation_refs",
        ),
        "policy_design_major_claim_monitoring_refs_missing",
        "monitoring refs",
    ),
)
_WAVE21_SCHOLAR_REF_KEYS = (
    "scholar_refs",
    "literature_refs",
    "scholar_literature_refs",
    "academic_evidence_refs",
)
_WAVE21_SCHOLAR_DEFICIT_KEYS = (
    "scholar_deficit_refs",
    "literature_deficit_refs",
    "accepted_literature_deficit_refs",
)
_WAVE21_PRODUCER_REF_SPECS = (
    ("lex", ("legal_norm_refs", "norm_refs", "legal_refs")),
    ("fabric", ("source_data_refs", "data_refs", "source_refs", "dataset_refs")),
    ("data_forge", ("source_data_refs", "data_refs", "source_refs", "dataset_refs")),
    ("scholar", _WAVE21_SCHOLAR_REF_KEYS),
    ("foundry", ("method_refs", "uncertainty_refs", "foundry_uncertainty_refs")),
    ("options_objectives", ("objective_tradeoff_refs", "objective_refs", "tradeoff_refs")),
)
_WAVE21_PROSE_BACKFILL_KEYS = (
    "support_summary",
    "evidence_summary",
    "citation_summary",
    "rationale",
    "claim_rationale",
    "grounding_rationale",
    "monitoring_plan",
    "policy_tradeoffs",
    "residual_uncertainty",
)
_POLICY_DESIGN_RESEARCH_DEFICIT_PROFILES = frozenset({"exploratory", "research"})
_POLICY_DESIGN_PROMOTED_AUTHORITY_PROFILES = frozenset(
    profile for profile in POLICY_AUTHORITY_PROFILES if profile != "research"
)
_POLICY_DESIGN_DEFICIT_PROFILE_KEYS = (
    "accepted_profiles",
    "allowed_profiles",
    "deficit_profiles",
    "effective_execution_profiles",
)
_POLICY_DESIGN_DEFICIT_SOURCE_PROFILE_KEYS = (
    "source_authority_profile",
    "accepted_under_profile",
    "accepted_profile",
    "origin_profile",
    "profile",
)
_POLICY_DESIGN_DEFICIT_PROMOTION_APPROVAL_KEYS = (
    "promotion_approval_ref",
    "governance_approval_ref",
    "authority_upgrade_ref",
    "deficit_promotion_review_ref",
)


def _policy_design_options_objectives_tradeoffs_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    record = _policy_design_options_record(case)
    if not isinstance(record, Mapping):
        gates.append(
            _policy_design_options_gate(
                code="policy_design_options_objectives_tradeoffs_missing",
                message=(
                    "Final policy recommendations require a runtime-owned options, "
                    "objectives, welfare, and tradeoff record."
                ),
                missing_input="options_objectives_tradeoffs",
            )
        )
        record = {}
    gates.extend(_policy_design_options_record_gates(record))
    gates.extend(_policy_design_final_claim_objective_ref_gates(final_claims))
    return gates


def _policy_design_wave27_lifecycle_ddm_expost_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    gates: list[dict[str, Any]] = []
    for issue in validate_policy_design_lifecycle_records(case, canary_kind=canary_kind):
        gate_fields = issue.as_gate_fields()
        gates.append(
            _gate(
                name="policy_design_lifecycle_ddm_ex_post_calibration",
                stage="ops",
                code=str(gate_fields["code"]),
                status="fail",
                layer="assurance_case",
                phase="policy_design_lifecycle_ddm_ex_post_calibration",
                message=str(gate_fields["message"]),
                evidence_ref=(
                    str(gate_fields["evidence_ref"])
                    if gate_fields["evidence_ref"] is not None
                    else "quality_evidence/policy_design_case.json"
                ),
                next_action=str(gate_fields["next_action"]),
                missing_input=str(gate_fields["field"]),
                affected_claim=(
                    str(gate_fields["affected_claim"])
                    if gate_fields["affected_claim"] is not None
                    else None
                ),
            )
        )
    return gates


def _policy_design_wave28_3_observability_static_audit_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    gates: list[dict[str, Any]] = []
    for issue in validate_observability_orchestration_static_audit_records(case):
        gate_fields = issue.as_gate_fields()
        gates.append(
            _gate(
                name="policy_design_observability_orchestration_static_audit",
                stage="ops",
                code=str(gate_fields["code"]),
                status="fail",
                layer="assurance_case",
                phase="policy_design_observability_orchestration_static_audit",
                message=str(gate_fields["message"]),
                evidence_ref=(
                    str(gate_fields["evidence_ref"])
                    if gate_fields["evidence_ref"] is not None
                    else "quality_evidence/policy_design_case.json"
                ),
                next_action=str(gate_fields["next_action"]),
                missing_input=str(gate_fields["field"]),
                affected_claim=(
                    str(gate_fields["affected_claim"])
                    if gate_fields["affected_claim"] is not None
                    else None
                ),
            )
        )
    return gates


def _policy_design_wave12_producer_evidence_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    producer_rows = _policy_design_producer_rows(case)
    final_claims = _policy_design_final_major_claims(case)
    if not producer_rows and not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    producer_by_evidence_id = _policy_design_producer_index(producer_rows)
    satisfied: set[str] = set()
    for row in producer_rows:
        producer = _policy_design_producer_name(row)
        if producer not in _WAVE12_REQUIRED_PRODUCERS:
            continue
        gates.extend(
            _policy_design_wave12_dependency_gates(
                row,
                producer=producer,
                producer_by_evidence_id=producer_by_evidence_id,
            )
        )
        row_gates, row_satisfies = _policy_design_producer_authority_gates(
            row,
            producer=producer,
        )
        gates.extend(row_gates)
        if row_satisfies:
            satisfied.add(producer)

    for producer in _WAVE12_REQUIRED_PRODUCERS:
        if producer in satisfied:
            continue
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_runtime_evidence_missing",
                message=(
                    f"Wave 12 producer {producer!r} must emit runtime-owned evidence "
                    "or a typed runtime blocker."
                ),
                producer=producer,
                missing_input=f"producer_evidence.{producer}",
            )
        )
    return gates


def _policy_design_producer_rows(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    producer_evidence = case.get("producer_evidence") or case.get("producer_records")
    if isinstance(producer_evidence, list):
        rows.extend(item for item in producer_evidence if isinstance(item, Mapping))
    for key in (
        "producer_runtime_ref_map",
        "producer_ref_map",
        "producer_contract_map",
        "producer_evidence_map",
    ):
        producer_map = case.get(key)
        if not isinstance(producer_map, Mapping):
            continue
        for raw_producer, raw_row in producer_map.items():
            if not isinstance(raw_row, Mapping):
                continue
            row = dict(raw_row)
            row.setdefault("producer", str(raw_producer))
            rows.append(row)
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type == "producer_evidence" or node_family == "producer_evidence":
                rows.append(node)
    return tuple(rows)


def _policy_design_producer_index(
    rows: tuple[Mapping[str, Any], ...],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in rows:
        producer = _policy_design_producer_name(row)
        if producer is None:
            continue
        for key in ("evidence_id", "id", "record_id", "producer_evidence_ref"):
            value = _clean_text(row.get(key))
            if value:
                index[value] = producer
        for key in ("evidence_ref", "cas_ref"):
            value = _clean_text(row.get(key))
            if value:
                index[value] = producer
    return index


def _policy_design_producer_name(row: Mapping[str, Any]) -> str | None:
    for key in ("producer", "producer_name", "producer_family", "component"):
        value = _clean_text(row.get(key))
        if value:
            normalized = _normalize_wave12_producer(value)
            if normalized is not None:
                return normalized
    component = _clean_text(row.get("producer_component"))
    if component:
        for part in reversed(component.replace("-", "_").split(".")):
            normalized = _normalize_wave12_producer(part)
            if normalized is not None:
                return normalized
    schema_name = _clean_text(row.get("schema_name"))
    if schema_name:
        for part in schema_name.replace("-", "_").split("."):
            normalized = _normalize_wave12_producer(part)
            if normalized is not None:
                return normalized
    return None


def _normalize_wave12_producer(value: str) -> str | None:
    key = value.strip().casefold().replace("-", "_")
    return _WAVE12_PRODUCER_ALIASES.get(key)


def _policy_design_wave12_dependency_gates(
    row: Mapping[str, Any],
    *,
    producer: str,
    producer_by_evidence_id: Mapping[str, str],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for key in _WAVE12_DEPENDENCY_KEYS:
        values = _policy_design_text_values(row.get(key))
        for value in values:
            referenced_producer = producer_by_evidence_id.get(value)
            if referenced_producer is None:
                referenced_producer = _policy_design_dependency_producer_hint(value)
            if referenced_producer is None or referenced_producer == producer:
                continue
            gates.append(
                _policy_design_producer_gate(
                    code="policy_design_wave12_producer_dependency_forbidden",
                    message=(
                        f"Wave 12 producer {producer!r} consumes output from peer "
                        f"producer {referenced_producer!r}."
                    ),
                    producer=producer,
                    evidence_ref=_clean_text(row.get("evidence_ref") or row.get("cas_ref")),
                    missing_input=key,
                )
            )
    return gates


def _policy_design_text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _clean_text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("producer", "producer_ref", "evidence_id", "evidence_ref", "ref", "id"):
            text = _clean_text(value.get(key))
            if text:
                values.append(text)
        return tuple(values)
    if isinstance(value, list | tuple | set):
        values = []
        for item in value:
            values.extend(_policy_design_text_values(item))
        return tuple(values)
    return ()


def _policy_design_wave14_producer_scorecard_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    producer_rows = _policy_design_producer_rows(case)
    rows_by_producer: dict[str, list[Mapping[str, Any]]] = {}
    for row in producer_rows:
        producer = _policy_design_producer_name(row)
        if producer is None:
            continue
        rows_by_producer.setdefault(producer, []).append(row)

    gates: list[dict[str, Any]] = []
    checked_producers: set[str] = set()
    emitted_missing_refs: set[tuple[str, str, str]] = set()
    emitted_contract_codes: set[tuple[str, str]] = set()

    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id")) or _clean_text(claim.get("id"))
        for producer, claim_ref_keys in _WAVE14_FINAL_CLAIM_PRODUCER_SPECS.items():
            claim_refs = _policy_design_refs_for_keys(claim, claim_ref_keys)
            if not claim_refs:
                continue
            rows = tuple(rows_by_producer.get(producer, ()))
            if not rows:
                for claim_ref in claim_refs:
                    emitted_key = (producer, claim_id or "", claim_ref)
                    if emitted_key in emitted_missing_refs:
                        continue
                    emitted_missing_refs.add(emitted_key)
                    gates.append(
                        _policy_design_wave14_producer_gate(
                            code="policy_design_final_claim_producer_ref_missing",
                            message=(
                                "Final claim evidence ref "
                                f"{claim_ref!r} uses {producer!r} evidence without a "
                                "producer-owned runtime record."
                            ),
                            producer=producer,
                            affected_claim=claim_id,
                            missing_input=f"final_major_claims.{producer}_producer_ref",
                        )
                    )
                continue

            if producer not in _WAVE12_REQUIRED_PRODUCERS:
                for row in rows:
                    authority_gates, _row_satisfies = _policy_design_producer_authority_gates(
                        row,
                        producer=producer,
                    )
                    gates.extend(authority_gates)

            runtime_rows = tuple(
                row for row in rows if _policy_design_producer_contract_row_runtime_owned(row)
            )
            if not runtime_rows:
                for claim_ref in claim_refs:
                    emitted_key = (producer, claim_id or "", claim_ref)
                    if emitted_key in emitted_missing_refs:
                        continue
                    emitted_missing_refs.add(emitted_key)
                    gates.append(
                        _policy_design_wave14_producer_gate(
                            code="policy_design_final_claim_producer_ref_missing",
                            message=(
                                "Final claim evidence ref "
                                f"{claim_ref!r} is not backed by runtime-owned "
                                f"{producer!r} producer authority."
                            ),
                            producer=producer,
                            affected_claim=claim_id,
                            missing_input=f"final_major_claims.{producer}_runtime_ref",
                        )
                    )
                continue

            selected_refs = _policy_design_refs_for_keys(
                _policy_design_merged_rows(runtime_rows),
                _WAVE14_SELECTED_REF_KEYS,
            )
            for claim_ref in claim_refs:
                if claim_ref in selected_refs:
                    continue
                emitted_key = (producer, claim_id or "", claim_ref)
                if emitted_key in emitted_missing_refs:
                    continue
                emitted_missing_refs.add(emitted_key)
                gates.append(
                    _policy_design_wave14_producer_gate(
                        code="policy_design_final_claim_producer_ref_missing",
                        message=(
                            "Final claim evidence ref "
                            f"{claim_ref!r} is absent from selected {producer!r} "
                            "producer candidates."
                        ),
                        producer=producer,
                        affected_claim=claim_id,
                        missing_input=f"producer_evidence.{producer}.selected_candidate_refs",
                    )
                )

            if producer in checked_producers:
                continue
            checked_producers.add(producer)
            for gate in _policy_design_wave14_contract_surface_gates(
                producer=producer,
                rows=runtime_rows,
            ):
                code = _clean_text(gate.get("code")) or ""
                emitted_key = (producer, code)
                if emitted_key in emitted_contract_codes:
                    continue
                emitted_contract_codes.add(emitted_key)
                gates.append(gate)

    return gates


def _policy_design_wave15_evidence_portfolio_design_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    designs = _policy_design_portfolio_design_rows(case)
    design_by_ref = _policy_design_portfolio_design_index(designs)
    producer_execution_started_at = _policy_design_earliest_producer_execution_started_at(case)
    gates: list[dict[str, Any]] = []

    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            continue
        if _policy_design_claim_portfolio_blocked_by_authority_profile(case, claim):
            continue

        portfolio_refs = _policy_design_refs_for_keys(
            claim,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
        )
        if portfolio_refs:
            matched_designs = tuple(
                design_by_ref[ref] for ref in portfolio_refs if ref in design_by_ref
            )
        else:
            matched_designs = tuple(
                design
                for design in designs
                if claim_id in set(portfolio_design_claim_ids(design))
            )

        if not matched_designs:
            gates.append(
                _policy_design_wave15_portfolio_gate(
                    code="policy_design_major_claim_portfolio_missing",
                    message=(
                        f"Major claim {claim_id!r} must have a predeclared evidence "
                        "portfolio design or an authority-profile blocker."
                    ),
                    missing_input="evidence_portfolios",
                    affected_claim=claim_id,
                )
            )
            continue

        for design in matched_designs:
            try:
                validate_evidence_portfolio_design_record(
                    design,
                    major_claim_ids=[claim_id],
                    producer_execution_started_at=producer_execution_started_at,
                )
            except EvidencePortfolioDesignError as exc:
                gates.append(
                    _policy_design_wave15_portfolio_gate(
                        code=exc.code,
                        message=str(exc),
                        evidence_ref=_clean_text(
                            design.get("evidence_ref") or design.get("cas_ref")
                        ),
                        missing_input=exc.field or "evidence_portfolios",
                        affected_claim=claim_id,
                    )
                )

    return gates


def _policy_design_portfolio_design_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "evidence_portfolio_designs",
        "portfolio_designs",
        "evidence_portfolios",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type == "portfolio" or node_family == "evidence_portfolio":
                rows.append(node)
    return tuple(rows)


def _policy_design_portfolio_design_index(
    designs: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for design in designs:
        for key in (
            "portfolio_id",
            "portfolio_design_id",
            "design_id",
            "record_id",
            "cas_ref",
            "evidence_ref",
        ):
            value = _clean_text(design.get(key))
            if value:
                index[value] = design
        try:
            index[portfolio_design_record_id(design)] = design
        except EvidencePortfolioDesignError:
            continue
    return index


def _policy_design_earliest_producer_execution_started_at(
    case: Mapping[str, Any],
) -> str | None:
    timestamps: list[str] = []
    for key in (
        "producer_execution_started_at",
        "producer_execution_at",
        "execution_started_at",
    ):
        text = _clean_text(case.get(key))
        if text:
            timestamps.append(text)
    for row in _policy_design_producer_rows(case):
        for key in (
            "producer_execution_started_at",
            "execution_started_at",
            "executed_at",
            "generated_at",
            "emitted_at",
        ):
            text = _clean_text(row.get(key))
            if text:
                timestamps.append(text)
    return min(timestamps) if timestamps else None


def _policy_design_claim_portfolio_blocked_by_authority_profile(
    case: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> bool:
    claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
    if claim_id is None:
        return False
    authority_profile = _policy_design_case_effective_authority_profile(case)
    for blocker in _policy_design_portfolio_blocker_rows(case):
        blocker_claims = set(_policy_design_text_values(blocker.get("claim_ids")))
        blocker_claim = _clean_text(blocker.get("claim_id") or blocker.get("major_claim_id"))
        if blocker_claim:
            blocker_claims.add(blocker_claim)
        if blocker_claims and claim_id not in blocker_claims:
            continue
        blocker_profile = _clean_text(
            blocker.get("authority_profile")
            or blocker.get("effective_execution_profile")
            or blocker.get("profile")
        )
        if blocker_profile and authority_profile and blocker_profile != authority_profile:
            continue
        if _policy_design_valid_portfolio_profile_blocker(blocker):
            return True
    return False


def _policy_design_case_effective_authority_profile(case: Mapping[str, Any]) -> str | None:
    authority_profile = case.get("authority_profile")
    if isinstance(authority_profile, Mapping):
        text = _clean_text(
            authority_profile.get("effective_execution_profile")
            or authority_profile.get("requested_authority_level")
        )
        if text:
            return text
    intent = case.get("intent_envelope")
    if isinstance(intent, Mapping):
        text = _clean_text(intent.get("requested_authority_level"))
        if text:
            return text
    return _clean_text(case.get("effective_execution_profile"))


def _policy_design_portfolio_blocker_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "evidence_portfolio_design_blockers",
        "portfolio_design_blockers",
        "portfolio_blockers",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return tuple(rows)


def _policy_design_valid_portfolio_profile_blocker(blocker: Mapping[str, Any]) -> bool:
    if _clean_text(blocker.get("status") or blocker.get("decision")) != "blocked":
        return False
    if not _clean_text(blocker.get("code")):
        return False
    if not _clean_text(blocker.get("message") or blocker.get("downstream_impact")):
        return False
    evidence_ref = _clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref"))
    if not _policy_design_runtime_artifact_ref(evidence_ref):
        return False
    return _policy_design_runtime_event_ref(blocker.get("runtime_event_ref"))


def _policy_design_wave15_portfolio_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave15_evidence_portfolio_design",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_portfolio_design",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.evidence_portfolios",
        next_action=(
            "Predeclare the evidence portfolio design before producer execution, "
            "including strands, candidate source and method families, inclusion and "
            "exclusion rules, disconfirming lines, synthesis, stopping, and "
            "cost/proportionality rules; otherwise emit an authority-profile blocker."
        ),
        missing_input=missing_input or "evidence_portfolios",
        affected_claim=affected_claim,
    )


def _policy_design_wave16_evidence_line_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    lines = _policy_design_evidence_line_rows(case)
    if not lines:
        return []
    designs = _policy_design_portfolio_design_rows(case)
    producer_execution_started_at = _policy_design_earliest_producer_execution_started_at(
        case
    )
    gates: list[dict[str, Any]] = []
    for line in lines:
        try:
            validate_evidence_line_record(
                line,
                portfolio_designs=designs,
                producer_execution_started_at=producer_execution_started_at,
            )
        except EvidenceLineError as exc:
            gates.append(
                _policy_design_wave16_evidence_line_gate(
                    code=exc.code,
                    message=str(exc),
                    evidence_ref=_clean_text(
                        line.get("evidence_ref") or line.get("cas_ref")
                    ),
                    missing_input=exc.field or "evidence_lines",
                    affected_claim=_clean_text(
                        line.get("claim_id") or line.get("major_claim_id")
                    ),
                )
            )
    return gates


def _policy_design_evidence_line_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "evidence_lines",
        "evidence_line_records",
        "portfolio_evidence_lines",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type == "evidence_line" or node_family == "evidence_line":
                rows.append(node)
    return tuple(rows)


def _policy_design_wave16_evidence_line_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave16_evidence_line_model",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_evidence_line",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.evidence_lines",
        next_action=(
            "Emit evidence line records as method, source lineage, assumptions, "
            "specification, producer identity, and execution-context combinations "
            "bound to a predeclared evidence portfolio design."
        ),
        missing_input=missing_input or "evidence_lines",
        affected_claim=affected_claim,
    )


def _policy_design_wave17_independence_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []

    gates: list[dict[str, Any]] = []
    lines = _policy_design_evidence_line_rows(case)
    designs = _policy_design_portfolio_design_rows(case)
    producer_execution_started_at = _policy_design_earliest_producer_execution_started_at(
        case
    )
    for map_row in _policy_design_independence_map_rows(case):
        try:
            validate_evidence_independence_map_record(
                map_row,
                evidence_lines=lines if lines else (),
                portfolio_designs=designs,
                producer_execution_started_at=producer_execution_started_at,
            )
        except EvidenceIndependenceError as exc:
            gates.append(
                _policy_design_wave17_independence_gate(
                    code=exc.code,
                    message=str(exc),
                    evidence_ref=_clean_text(
                        map_row.get("evidence_ref") or map_row.get("cas_ref")
                    ),
                    missing_input=exc.field or "independence_maps",
                    affected_claim=_clean_text(
                        map_row.get("claim_id") or map_row.get("major_claim_id")
                    ),
                )
            )

    for row, surface in _policy_design_raw_count_surfaces(case):
        has_raw_count_without_effective_count = (
            _policy_design_has_raw_evidence_count(row)
            and not _policy_design_has_effective_count(row)
        )
        if has_raw_count_without_effective_count:
            gates.append(
                _policy_design_wave17_independence_gate(
                    code="policy_design_independence_effective_count_missing",
                    message=(
                        "Raw evidence-line count cannot be reported without an "
                        "effective independent evidence count."
                    ),
                    evidence_ref=_clean_text(row.get("evidence_ref") or row.get("cas_ref")),
                    missing_input=f"{surface}.effective_independent_evidence_count",
                    affected_claim=_clean_text(row.get("claim_id") or row.get("major_claim_id")),
                )
            )
    if lines and not _policy_design_independence_map_rows(case):
        gates.append(
            _policy_design_wave17_independence_gate(
                code="policy_design_independence_map_missing",
                message=(
                    "Evidence lines must be accompanied by an independence map "
                    "that reports raw and effective independent evidence counts."
                ),
                missing_input="independence_maps",
            )
        )
    return gates


def _policy_design_independence_map_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "independence_maps",
        "evidence_independence_maps",
        "independence_map_records",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type == "independence_map" or node_family == "independence_map":
                rows.append(node)
    return tuple(rows)


def _policy_design_raw_count_surfaces(
    case: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], str], ...]:
    rows: list[tuple[Mapping[str, Any], str]] = [(case, "policy_design_case")]
    rows.extend(
        (row, "evidence_portfolios") for row in _policy_design_portfolio_design_rows(case)
    )
    rows.extend(
        (row, "independence_maps") for row in _policy_design_independence_map_rows(case)
    )
    return tuple(rows)


def _policy_design_has_raw_evidence_count(row: Mapping[str, Any]) -> bool:
    return any(
        key in row
        for key in (
            "raw_evidence_line_count",
            "raw_evidence_count",
            "raw_line_count",
        )
    )


def _policy_design_has_effective_count(row: Mapping[str, Any]) -> bool:
    return any(
        key in row
        for key in (
            "effective_independent_evidence_count",
            "effective_independent_count",
            "effective_evidence_line_count",
        )
    )


def _policy_design_wave17_independence_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave17_independence_map",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_evidence_independence",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.independence_maps",
        next_action=(
            "Emit an evidence independence map that collapses correlated source "
            "lineage, corpus ancestry, author/institution pool, preprocessing, "
            "method assumptions, identification strategy, Foundry method "
            "consensus/equivalence, and shared failure modes before synthesis."
        ),
        missing_input=missing_input or "independence_maps",
        affected_claim=affected_claim,
    )


def _policy_design_wave18_disconfirming_evidence_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    designs = _policy_design_portfolio_design_rows(case)
    design_by_ref = _policy_design_portfolio_design_index(designs)
    evidence_lines = _policy_design_evidence_line_rows(case)
    independence_maps = _policy_design_independence_map_rows(case)
    ledgers = _policy_design_disconfirming_ledger_rows(case)
    ledger_by_ref = _policy_design_disconfirming_ledger_index(ledgers)
    accepted_deficits = _policy_design_accepted_deficit_rows(case)
    authority_profile = _policy_design_case_effective_authority_profile(case) or canary_kind
    gates: list[dict[str, Any]] = []

    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            continue
        if _policy_design_claim_portfolio_blocked_by_authority_profile(case, claim):
            continue

        accepted_deficit = disconfirming_deficit_accepted(
            accepted_deficits,
            claim_ids=[claim_id],
            effective_authority_profile=authority_profile,
        )
        portfolio_refs = _policy_design_refs_for_keys(
            claim,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
        )
        if portfolio_refs:
            matched_designs = tuple(
                design_by_ref[ref] for ref in portfolio_refs if ref in design_by_ref
            )
        else:
            matched_designs = tuple(
                design
                for design in designs
                if claim_id in set(_policy_design_text_values(design.get("claim_ids")))
                or claim_id == _clean_text(design.get("claim_id"))
            )

        if matched_designs and not accepted_deficit and not any(
            portfolio_design_has_disconfirming_lines(design) for design in matched_designs
        ):
            gates.append(
                _policy_design_wave18_disconfirming_gate(
                    code="policy_design_disconfirming_lines_missing",
                    message=(
                        f"Major claim {claim_id!r} has only friendly or confirming "
                        "portfolio lines; it must predeclare disconfirming lines or "
                        "carry an accepted profile-specific deficit."
                    ),
                    missing_input="evidence_portfolios.disconfirming_lines",
                    affected_claim=claim_id,
                )
            )

        ledger_refs = _policy_design_refs_for_keys(
            claim,
            (
                "disconfirming_ledger_refs",
                "disconfirming_evidence_ledger_refs",
                "disconfirming_refs",
                "disconfirming_evidence_refs",
            ),
        )
        if ledger_refs:
            matched_ledgers = tuple(
                ledger_by_ref[ref] for ref in ledger_refs if ref in ledger_by_ref
            )
        else:
            matched_portfolio_ids = {
                _clean_text(design.get("portfolio_id") or design.get("record_id"))
                for design in matched_designs
            }
            matched_ledgers = tuple(
                ledger
                for ledger in ledgers
                if _policy_design_ledger_matches_claim_and_portfolio(
                    ledger,
                    claim_id=claim_id,
                    portfolio_ids=matched_portfolio_ids,
                )
            )

        if not matched_ledgers:
            if not accepted_deficit and matched_designs:
                gates.append(
                    _policy_design_wave18_disconfirming_gate(
                        code="policy_design_disconfirming_ledger_missing",
                        message=(
                            f"Major claim {claim_id!r} must have a disconfirming "
                            "evidence ledger or an accepted profile-specific deficit."
                        ),
                        missing_input="disconfirming_evidence_ledgers",
                        affected_claim=claim_id,
                    )
                )
            continue

        for ledger in matched_ledgers:
            try:
                validate_disconfirming_evidence_ledger_record(
                    ledger,
                    portfolio_designs=matched_designs or designs,
                    evidence_lines=evidence_lines,
                    independence_maps=independence_maps,
                    accepted_deficits=accepted_deficits,
                    effective_authority_profile=authority_profile,
                    major_claim_ids=[claim_id],
                )
            except DisconfirmingEvidenceLedgerError as exc:
                gates.append(
                    _policy_design_wave18_disconfirming_gate(
                        code=exc.code,
                        message=str(exc),
                        evidence_ref=_clean_text(
                            ledger.get("evidence_ref") or ledger.get("cas_ref")
                        ),
                        missing_input=exc.field or "disconfirming_evidence_ledgers",
                        affected_claim=claim_id,
                    )
                )
    return gates


def _policy_design_disconfirming_ledger_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "disconfirming_evidence_ledgers",
        "disconfirming_ledgers",
        "disconfirming_ledger_records",
        "disconfirming_evidence_ledger_records",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if (
                node_type in {"disconfirming_ledger", "disconfirming_evidence_ledger"}
                or node_family in {"disconfirming_ledger", "disconfirming_evidence"}
            ):
                rows.append(node)
    return tuple(rows)


def _policy_design_disconfirming_ledger_index(
    ledgers: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for ledger in ledgers:
        for key in (
            "ledger_id",
            "disconfirming_ledger_id",
            "record_id",
            "id",
            "cas_ref",
            "evidence_ref",
        ):
            value = _clean_text(ledger.get(key))
            if value:
                index[value] = ledger
        try:
            index[disconfirming_ledger_record_id(ledger)] = ledger
        except DisconfirmingEvidenceLedgerError:
            continue
    return index


def _policy_design_ledger_matches_claim_and_portfolio(
    ledger: Mapping[str, Any],
    *,
    claim_id: str,
    portfolio_ids: set[str | None],
) -> bool:
    ledger_claims = set(_policy_design_text_values(ledger.get("claim_ids")))
    ledger_claim = _clean_text(ledger.get("claim_id") or ledger.get("major_claim_id"))
    if ledger_claim:
        ledger_claims.add(ledger_claim)
    if ledger_claims and claim_id not in ledger_claims:
        return False
    clean_portfolio_ids = {value for value in portfolio_ids if value}
    if not clean_portfolio_ids:
        return True
    try:
        portfolio_id = disconfirming_ledger_portfolio_id(ledger)
    except DisconfirmingEvidenceLedgerError:
        return True
    return portfolio_id in clean_portfolio_ids


def _policy_design_accepted_deficit_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "accepted_deficits",
        "assurance_deficits",
        "deficits",
        "accepted_assurance_deficits",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type == "deficit" or node_family in {"deficit", "assurance_deficit"}:
                rows.append(node)
    return tuple(rows)


def _policy_design_wave18_disconfirming_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave18_disconfirming_evidence",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_disconfirming_evidence",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.disconfirming_evidence_ledgers",
        next_action=(
            "Emit a disconfirming evidence ledger that wires IR falsification "
            "reports, adversarial plans, and severe-test records with rationale, "
            "or record an accepted profile-specific assurance deficit."
        ),
        missing_input=missing_input or "disconfirming_evidence_ledgers",
        affected_claim=affected_claim,
    )


def _policy_design_wave18_multiverse_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    designs = _policy_design_portfolio_design_rows(case)
    design_by_ref = _policy_design_portfolio_design_index(designs)
    evidence_lines = _policy_design_evidence_line_rows(case)
    independence_maps = _policy_design_independence_map_rows(case)
    rows = _policy_design_multiverse_curve_rows(case)
    curve_by_ref = _policy_design_multiverse_curve_index(rows)
    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            continue
        if _policy_design_claim_portfolio_blocked_by_authority_profile(case, claim):
            continue
        portfolio_refs = _policy_design_refs_for_keys(
            claim,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
        )
        if portfolio_refs:
            matched_designs = tuple(
                design_by_ref[ref] for ref in portfolio_refs if ref in design_by_ref
            )
        else:
            matched_designs = tuple(
                design
                for design in designs
                if claim_id in set(portfolio_design_claim_ids(design))
            )
        if not matched_designs:
            continue

        portfolio_multiverse_refs = {
            ref
            for design in matched_designs
            for ref in _policy_design_refs_for_keys(
                design,
                (
                    "multiverse_report_ref",
                    "multiverse_report_refs",
                    "multiverse_specification_curve_ref",
                    "multiverse_specification_curve_refs",
                    "specification_curve_ref",
                    "specification_curve_refs",
                ),
            )
        }
        matched_curves = tuple(
            curve
            for curve in rows
            if _policy_design_multiverse_curve_matches_claim_and_portfolio(
                curve,
                claim_id=claim_id,
                portfolio_ids={
                    _clean_text(design.get("portfolio_id") or design.get("record_id"))
                    for design in matched_designs
                },
            )
            and (
                not portfolio_multiverse_refs
                or any(
                    ref in curve_by_ref and curve_by_ref[ref] is curve
                    for ref in portfolio_multiverse_refs
                )
            )
        )
        if not matched_curves:
            gates.append(
                _policy_design_wave18_multiverse_gate(
                    code="policy_design_multiverse_specification_curve_missing",
                    message=(
                        f"Major claim {claim_id!r} must have a multiverse "
                        "specification-curve record bound to its predeclared "
                        "portfolio."
                    ),
                    missing_input="multiverse_specification_curves",
                    affected_claim=claim_id,
                )
            )
            continue

        for row in matched_curves:
            try:
                validate_multiverse_specification_curve_record(
                    row,
                    portfolio_designs=matched_designs or designs,
                    evidence_lines=evidence_lines,
                    independence_maps=independence_maps,
                    major_claim_ids=[claim_id],
                )
            except MultiverseSpecificationCurveError as exc:
                gates.append(
                    _policy_design_wave18_multiverse_gate(
                        code=exc.code,
                        message=str(exc),
                        evidence_ref=_clean_text(
                            row.get("evidence_ref") or row.get("cas_ref")
                        ),
                        missing_input=exc.field or "multiverse_specification_curves",
                        affected_claim=claim_id,
                    )
                )
    return gates


def _policy_design_multiverse_curve_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "multiverse_specification_curves",
        "multiverse_specification_curve_records",
        "multiverse_reports",
        "specification_curve_records",
        "specification_curve_reports",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type in {
                "multiverse_specification_curve",
                "specification_curve",
            } or node_family in {
                "multiverse_specification_curve",
                "specification_curve",
            }:
                rows.append(node)
    return tuple(rows)


def _policy_design_multiverse_curve_index(
    curves: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for curve in curves:
        for key in (
            "curve_id",
            "multiverse_curve_id",
            "record_id",
            "id",
            "cas_ref",
            "evidence_ref",
        ):
            value = _clean_text(curve.get(key))
            if value:
                index[value] = curve
    return index


def _policy_design_multiverse_curve_matches_claim_and_portfolio(
    curve: Mapping[str, Any],
    *,
    claim_id: str,
    portfolio_ids: set[str | None],
) -> bool:
    curve_claims = set(_policy_design_text_values(curve.get("claim_ids")))
    curve_claim = _clean_text(curve.get("claim_id") or curve.get("major_claim_id"))
    if curve_claim:
        curve_claims.add(curve_claim)
    if curve_claims and claim_id not in curve_claims:
        return False
    clean_portfolio_ids = {value for value in portfolio_ids if value}
    if not clean_portfolio_ids:
        return True
    portfolio_id = _clean_text(curve.get("portfolio_id") or curve.get("portfolio_ref"))
    return portfolio_id in clean_portfolio_ids


def _policy_design_wave18_multiverse_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave18_multiverse_specification_curve",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_multiverse_specification_curve",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.multiverse_specification_curves",
        next_action=(
            "Project Scientist DOE, Scientist discovery, Foundry sensitivity, "
            "and backtesting outputs into a multiverse specification-curve "
            "record before marking claims robust."
        ),
        missing_input=missing_input or "multiverse_specification_curves",
        affected_claim=affected_claim,
    )


def _policy_design_wave19_synthesis_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    designs = _policy_design_portfolio_design_rows(case)
    design_by_ref = _policy_design_portfolio_design_index(designs)
    multiverse_curves = _policy_design_multiverse_curve_rows(case)
    disconfirming_ledgers = _policy_design_disconfirming_ledger_rows(case)
    reports = _policy_design_synthesis_report_rows(case)
    report_by_ref = _policy_design_synthesis_report_index(reports)
    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            continue
        if _policy_design_claim_portfolio_blocked_by_authority_profile(case, claim):
            continue
        portfolio_refs = _policy_design_refs_for_keys(
            claim,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
        )
        if portfolio_refs:
            matched_designs = tuple(
                design_by_ref[ref] for ref in portfolio_refs if ref in design_by_ref
            )
        else:
            matched_designs = tuple(
                design
                for design in designs
                if claim_id in set(portfolio_design_claim_ids(design))
            )
        if not matched_designs:
            continue

        portfolio_synthesis_refs = {
            ref
            for design in matched_designs
            for ref in _policy_design_refs_for_keys(
                design,
                (
                    "synthesis_report_ref",
                    "synthesis_report_refs",
                    "evidence_synthesis_report_ref",
                    "evidence_synthesis_report_refs",
                ),
            )
        }
        matched_reports = tuple(
            report
            for report in reports
            if _policy_design_synthesis_report_matches_claim_and_portfolio(
                report,
                claim_id=claim_id,
                portfolio_ids={
                    _clean_text(design.get("portfolio_id") or design.get("record_id"))
                    for design in matched_designs
                },
            )
            and (
                not portfolio_synthesis_refs
                or any(
                    ref in report_by_ref and report_by_ref[ref] is report
                    for ref in portfolio_synthesis_refs
                )
            )
        )
        if not matched_reports:
            gates.append(
                _policy_design_wave19_synthesis_gate(
                    code="policy_design_synthesis_report_missing",
                    message=(
                        f"Major claim {claim_id!r} must have an evidence synthesis "
                        "report bound to its predeclared portfolio."
                    ),
                    missing_input="synthesis_reports",
                    affected_claim=claim_id,
                )
            )
            continue

        for report in matched_reports:
            try:
                validate_evidence_synthesis_report_record(
                    report,
                    multiverse_curves=multiverse_curves,
                    disconfirming_ledgers=disconfirming_ledgers,
                    major_claim_ids=[claim_id],
                )
            except EvidenceSynthesisReportError as exc:
                gates.append(
                    _policy_design_wave19_synthesis_gate(
                        code=exc.code,
                        message=str(exc),
                        evidence_ref=_clean_text(
                            report.get("evidence_ref") or report.get("cas_ref")
                        ),
                        missing_input=exc.field or "synthesis_reports",
                        affected_claim=claim_id,
                    )
                )
    return gates


def _policy_design_synthesis_report_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "synthesis_reports",
        "evidence_synthesis_reports",
        "synthesis_report_records",
        "evidence_synthesis_report_records",
    ):
        value = case.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type in {"synthesis_report", "evidence_synthesis_report"} or (
                node_family in {"synthesis_report", "evidence_synthesis"}
            ):
                rows.append(node)
    return tuple(rows)


def _policy_design_synthesis_report_index(
    reports: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for report in reports:
        for key in (
            "report_id",
            "synthesis_report_id",
            "record_id",
            "id",
            "cas_ref",
            "evidence_ref",
            "stopping_rule_result_ref",
            "cost_proportionality_ref",
        ):
            value = _clean_text(report.get(key))
            if value:
                index[value] = report
        try:
            index[synthesis_report_record_id(report)] = report
        except EvidenceSynthesisReportError:
            continue
    return index


def _policy_design_synthesis_report_matches_claim_and_portfolio(
    report: Mapping[str, Any],
    *,
    claim_id: str,
    portfolio_ids: set[str | None],
) -> bool:
    report_claims = set(_policy_design_text_values(report.get("claim_ids")))
    report_claim = _clean_text(report.get("claim_id") or report.get("major_claim_id"))
    if report_claim:
        report_claims.add(report_claim)
    if report_claims and claim_id not in report_claims:
        return False
    clean_portfolio_ids = {value for value in portfolio_ids if value}
    if not clean_portfolio_ids:
        return True
    portfolio_id = _clean_text(report.get("portfolio_id") or report.get("portfolio_ref"))
    return portfolio_id in clean_portfolio_ids


def _policy_design_wave19_synthesis_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave19_evidence_synthesis",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_evidence_synthesis",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.synthesis_reports",
        next_action=(
            "Emit an evidence synthesis report with weighting, heterogeneity, "
            "certainty, publication-bias treatment, inclusion/exclusion policy, "
            "synthesis-rule sensitivity, information-saturation stopping, "
            "run-cost proportionality, and explicit divergence evidence or blockers."
        ),
        missing_input=missing_input or "synthesis_reports",
        affected_claim=affected_claim,
    )


def _policy_design_wave20_portfolio_readiness_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    designs = _policy_design_portfolio_design_rows(case)
    design_by_ref = _policy_design_portfolio_design_index(designs)
    evidence_lines = _policy_design_evidence_line_rows(case)
    evidence_line_index = _policy_design_evidence_line_index(evidence_lines)
    independence_maps = _policy_design_independence_map_rows(case)
    synthesis_reports = _policy_design_synthesis_report_rows(case)
    accepted_deficits = _policy_design_accepted_deficit_rows(case)
    authority_profile = _policy_design_case_effective_authority_profile(case) or canary_kind
    selection_rows = _policy_design_portfolio_selection_rows(case)

    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            continue
        if _policy_design_claim_portfolio_blocked_by_authority_profile(case, claim):
            continue
        matched_designs = _policy_design_matched_portfolio_designs_for_claim(
            claim,
            claim_id=claim_id,
            designs=designs,
            design_by_ref=design_by_ref,
        )
        matched_portfolio_ids = {
            portfolio_id
            for design in matched_designs
            if (portfolio_id := _policy_design_portfolio_id_or_none(design)) is not None
        }
        matched_lines = tuple(
            line
            for line in evidence_lines
            if _policy_design_row_matches_claim_and_portfolio(
                line,
                claim_id=claim_id,
                portfolio_ids=matched_portfolio_ids,
            )
        )
        if matched_designs and _policy_design_claim_is_single_line_closeout(
            claim,
            claim_id=claim_id,
            portfolio_ids=matched_portfolio_ids,
            evidence_lines=matched_lines,
            independence_maps=independence_maps,
            synthesis_reports=synthesis_reports,
        ) and not _policy_design_single_line_deficit_accepted(
            accepted_deficits,
            claim_id=claim_id,
            effective_authority_profile=authority_profile,
        ):
            gates.append(
                _policy_design_wave20_portfolio_gate(
                    code="policy_design_single_line_evidence_unaccepted",
                    message=(
                        f"Major claim {claim_id!r} has only one effective evidence "
                        "line and cannot pass production readiness without an "
                        "accepted single-line-evidence assurance deficit."
                    ),
                    missing_input="accepted_deficits.single_line_evidence_deficit",
                    affected_claim=claim_id,
                )
            )

        for selection in selection_rows:
            if not _policy_design_row_matches_claim_and_portfolio(
                selection,
                claim_id=claim_id,
                portfolio_ids=matched_portfolio_ids,
            ):
                continue
            if _policy_design_post_hoc_selection_hides_disagreement(
                selection,
                evidence_line_index=evidence_line_index,
            ):
                gates.append(
                    _policy_design_wave20_portfolio_gate(
                        code="policy_design_post_hoc_selection_hides_disagreement",
                        message=(
                            f"Major claim {claim_id!r} has a post-hoc portfolio "
                            "selection that excludes or hides disagreeing evidence "
                            "lines."
                        ),
                        evidence_ref=_clean_text(
                            selection.get("evidence_ref") or selection.get("cas_ref")
                        ),
                        missing_input="portfolio_selection_audits",
                        affected_claim=claim_id,
                    )
                )

    return gates


def _policy_design_matched_portfolio_designs_for_claim(
    claim: Mapping[str, Any],
    *,
    claim_id: str,
    designs: tuple[Mapping[str, Any], ...],
    design_by_ref: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    portfolio_refs = _policy_design_refs_for_keys(
        claim,
        (
            "portfolio_design_refs",
            "portfolio_refs",
            "evidence_portfolio_refs",
        ),
    )
    if portfolio_refs:
        return tuple(design_by_ref[ref] for ref in portfolio_refs if ref in design_by_ref)
    return tuple(
        design for design in designs if claim_id in set(portfolio_design_claim_ids(design))
    )


def _policy_design_claim_is_single_line_closeout(
    claim: Mapping[str, Any],
    *,
    claim_id: str,
    portfolio_ids: set[str],
    evidence_lines: tuple[Mapping[str, Any], ...],
    independence_maps: tuple[Mapping[str, Any], ...],
    synthesis_reports: tuple[Mapping[str, Any], ...],
) -> bool:
    effective_count = _policy_design_effective_independent_count_for_claim(
        claim_id=claim_id,
        portfolio_ids=portfolio_ids,
        independence_maps=independence_maps,
        synthesis_reports=synthesis_reports,
    )
    if effective_count is not None:
        return effective_count <= 1
    if not evidence_lines:
        return False
    if len(evidence_lines) <= 1:
        return True
    source_ids = {
        source_id
        for line in evidence_lines
        if (source_id := _policy_design_line_source_id(line)) is not None
    }
    method_ids = {
        method_id
        for line in evidence_lines
        if (
            method_id := _clean_text(line.get("method_id") or line.get("method_ref"))
        )
        is not None
    }
    claim_data_refs = set(_policy_design_text_values(claim.get("data_refs")))
    claim_method_refs = set(_policy_design_text_values(claim.get("method_refs")))
    return (
        len(source_ids or claim_data_refs) <= 1
        and len(method_ids or claim_method_refs) <= 1
    )


def _policy_design_effective_independent_count_for_claim(
    *,
    claim_id: str,
    portfolio_ids: set[str],
    independence_maps: tuple[Mapping[str, Any], ...],
    synthesis_reports: tuple[Mapping[str, Any], ...],
) -> int | None:
    map_counts = [
        count
        for row in independence_maps
        if _policy_design_row_matches_claim_and_portfolio(
            row,
            claim_id=claim_id,
            portfolio_ids=portfolio_ids,
        )
        if (count := _policy_design_effective_count(row)) is not None
    ]
    if map_counts:
        return sum(map_counts)

    synthesis_counts = [
        count
        for row in synthesis_reports
        if _policy_design_row_matches_claim_and_portfolio(
            row,
            claim_id=claim_id,
            portfolio_ids=portfolio_ids,
        )
        if (count := _policy_design_effective_count(row)) is not None
    ]
    if synthesis_counts:
        return max(synthesis_counts)
    return None


def _policy_design_effective_count(row: Mapping[str, Any]) -> int | None:
    for key in (
        "effective_independent_evidence_count",
        "effective_independent_count",
        "effective_evidence_line_count",
    ):
        value = row.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value)
        if isinstance(value, float) and value.is_integer():
            return max(0, int(value))
    saturation = row.get("information_saturation")
    if isinstance(saturation, Mapping):
        return _policy_design_effective_count(saturation)
    return None


def _policy_design_single_line_deficit_accepted(
    deficits: tuple[Mapping[str, Any], ...],
    *,
    claim_id: str,
    effective_authority_profile: str | None,
) -> bool:
    for deficit in deficits:
        if _policy_design_deficit_kind(deficit) != "single_line_evidence_deficit":
            continue
        if disconfirming_deficit_accepted(
            (deficit,),
            claim_ids=[claim_id],
            effective_authority_profile=effective_authority_profile,
        ):
            return True
    return False


def _policy_design_deficit_kind(deficit: Mapping[str, Any]) -> str | None:
    text = _clean_text(
        deficit.get("deficit_kind")
        or deficit.get("kind")
        or deficit.get("code")
        or deficit.get("deficit_code")
    )
    if text is None:
        return None
    return text.casefold().replace("-", "_")


def _policy_design_portfolio_selection_rows(
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "portfolio_selection_audits",
        "portfolio_selection_reports",
        "post_hoc_portfolio_selections",
        "post_hoc_portfolio_selection",
    ):
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type in {"portfolio_selection", "portfolio_selection_audit"} or (
                node_family in {"portfolio_selection", "portfolio_selection_audit"}
            ):
                rows.append(node)
    return tuple(rows)


def _policy_design_evidence_line_index(
    lines: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for line in lines:
        for key in (
            "line_id",
            "evidence_line_id",
            "record_id",
            "id",
            "evidence_ref",
            "cas_ref",
        ):
            value = _clean_text(line.get(key))
            if value:
                index[value] = line
    return index


def _policy_design_post_hoc_selection_hides_disagreement(
    selection: Mapping[str, Any],
    *,
    evidence_line_index: Mapping[str, Mapping[str, Any]],
) -> bool:
    if not _policy_design_selection_is_post_hoc(selection):
        return False
    if _policy_design_truthy(
        selection.get("hides_disagreeing_lines")
        or selection.get("hides_disagreement")
        or selection.get("hide_disagreeing_lines")
    ):
        return True
    if _policy_design_text_has_disagreement(selection.get("reason_code")):
        return True
    for row in _policy_design_selection_exclusion_rows(selection):
        if _policy_design_text_has_disagreement(row):
            return True
        line_id = _clean_text(
            row.get("line_id")
            or row.get("evidence_line_id")
            or row.get("line_ref")
            or row.get("evidence_ref")
        )
        if line_id and _policy_design_line_disagrees(evidence_line_index.get(line_id)):
            return True
    for line_id in _policy_design_selection_excluded_line_ids(selection):
        if _policy_design_line_disagrees(evidence_line_index.get(line_id)):
            return True
    return False


def _policy_design_selection_is_post_hoc(selection: Mapping[str, Any]) -> bool:
    if _policy_design_truthy(
        selection.get("post_hoc")
        or selection.get("is_post_hoc")
        or selection.get("declared_after_execution")
    ):
        return True
    timing = _clean_text(
        selection.get("selection_timing")
        or selection.get("timing")
        or selection.get("selection_kind")
        or selection.get("declared_timing")
    )
    return timing is not None and "post" in timing.casefold() and "hoc" in timing.casefold()


def _policy_design_selection_exclusion_rows(
    selection: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in (
        "excluded_lines",
        "excluded_evidence_lines",
        "exclusion_rationales",
        "exclusion_reasons",
        "hidden_lines",
        "hidden_disagreeing_lines",
    ):
        value = selection.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return tuple(rows)


def _policy_design_selection_excluded_line_ids(selection: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in (
        "excluded_line_ids",
        "excluded_evidence_line_ids",
        "excluded_line_refs",
        "excluded_evidence_line_refs",
        "hidden_line_ids",
        "hidden_line_refs",
    ):
        values.extend(_policy_design_text_values(selection.get(key)))
    return tuple(dict.fromkeys(values))


def _policy_design_line_disagrees(line: Mapping[str, Any] | None) -> bool:
    if line is None:
        return False
    for key in (
        "stance",
        "support_status",
        "relationship_to_claim",
        "claim_direction",
        "result_direction",
        "direction",
        "reason_code",
    ):
        if _policy_design_text_has_disagreement(line.get(key)):
            return True
    return _policy_design_text_has_disagreement(line)


def _policy_design_text_has_disagreement(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_policy_design_text_has_disagreement(item) for item in value.values())
    if isinstance(value, list | tuple | set):
        return any(_policy_design_text_has_disagreement(item) for item in value)
    text = _clean_text(value)
    if text is None:
        return False
    normalized = text.casefold()
    return any(
        token in normalized
        for token in (
            "contradict",
            "conflict",
            "counter",
            "disagree",
            "disconfirm",
            "diverg",
            "negative_control",
            "opposite",
            "refut",
            "reject",
            "revers",
        )
    )


def _policy_design_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = _clean_text(value)
    return text is not None and text.casefold() in {"1", "true", "yes", "y", "on"}


def _policy_design_row_matches_claim_and_portfolio(
    row: Mapping[str, Any],
    *,
    claim_id: str,
    portfolio_ids: set[str],
) -> bool:
    row_claims = set(_policy_design_text_values(row.get("claim_ids")))
    row_claim = _clean_text(row.get("claim_id") or row.get("major_claim_id"))
    if row_claim:
        row_claims.add(row_claim)
    if row_claims and claim_id not in row_claims:
        return False
    if not portfolio_ids:
        return True
    row_portfolio_ids = set(_policy_design_text_values(row.get("portfolio_ids")))
    row_portfolio = _clean_text(
        row.get("portfolio_id")
        or row.get("portfolio_design_id")
        or row.get("portfolio_ref")
    )
    if row_portfolio:
        row_portfolio_ids.add(row_portfolio)
    return not row_portfolio_ids or bool(row_portfolio_ids & portfolio_ids)


def _policy_design_portfolio_id_or_none(row: Mapping[str, Any]) -> str | None:
    try:
        return portfolio_design_record_id(row)
    except EvidencePortfolioDesignError:
        return _clean_text(
            row.get("portfolio_id")
            or row.get("portfolio_design_id")
            or row.get("record_id")
            or row.get("id")
        )


def _policy_design_line_source_id(line: Mapping[str, Any]) -> str | None:
    source_lineage = line.get("source_lineage")
    if isinstance(source_lineage, Mapping):
        text = _clean_text(
            source_lineage.get("source_id")
            or source_lineage.get("source_ref")
            or source_lineage.get("dataset_ref")
        )
        if text:
            return text
    return _clean_text(
        line.get("source_id")
        or line.get("source_ref")
        or line.get("dataset_id")
        or line.get("dataset_ref")
    )


def _policy_design_wave20_portfolio_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave20_portfolio_readiness",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_portfolio_readiness",
        message=message,
        evidence_ref=evidence_ref or "policy_design_case.portfolio_readiness",
        next_action=(
            "Close ADR-0160 readiness by binding each major claim to a "
            "predeclared portfolio, independence map, effective count, "
            "specification curve, disconfirming ledger, synthesis report, "
            "stopping rule, and accepted deficit for any single-line evidence."
        ),
        missing_input=missing_input or "portfolio_readiness",
        affected_claim=affected_claim,
    )


def _policy_design_wave21_claim_compiler_runtime_contract_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []

    gates: list[dict[str, Any]] = []
    for claim in final_claims:
        claim_id = _clean_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            gates.append(
                _policy_design_wave21_claim_gate(
                    code="policy_design_major_claim_id_missing",
                    message="Claim compiler output must name a major claim id.",
                    missing_input="final_major_claims.claim_id",
                )
            )

        if not _policy_design_claim_has_runtime_assurance_node(case, claim):
            gates.append(
                _policy_design_wave21_claim_gate(
                    code="policy_design_major_claim_assurance_node_missing",
                    message=(
                        "Major claims may be minted only as runtime-owned Policy "
                        "Design Case assurance nodes."
                    ),
                    missing_input="final_major_claims.assurance_node_id",
                    affected_claim=claim_id,
                )
            )

        missing_ref = False
        for field_name, ref_keys, code, label in _WAVE21_REQUIRED_CLAIM_REF_SPECS:
            if _policy_design_wave21_claim_ref_present(
                claim,
                field_name=field_name,
                ref_keys=ref_keys,
            ):
                continue
            missing_ref = True
            gates.append(
                _policy_design_wave21_claim_gate(
                    code=code,
                    message=(
                        f"Major claim {claim_id or '<unknown>'!r} must cite {label} "
                        "selected by the claim registry."
                    ),
                    missing_input=f"final_major_claims.{field_name}",
                    affected_claim=claim_id,
                )
            )

        if not _policy_design_claim_has_scholar_refs_or_deficit(claim):
            missing_ref = True
            gates.append(
                _policy_design_wave21_claim_gate(
                    code="policy_design_major_claim_scholar_refs_or_deficit_missing",
                    message=(
                        f"Major claim {claim_id or '<unknown>'!r} must cite Scholar "
                        "refs or an accepted literature deficit selected by the "
                        "claim registry."
                    ),
                    missing_input="final_major_claims.scholar_refs",
                    affected_claim=claim_id,
                )
            )

        if missing_ref and _policy_design_claim_uses_prose_backfill(claim):
            gates.append(
                _policy_design_wave21_claim_gate(
                    code="policy_design_major_claim_prose_backfill_not_authority",
                    message=(
                        f"Major claim {claim_id or '<unknown>'!r} uses prose where "
                        "producer-selected runtime refs or typed deficits are required."
                    ),
                    missing_input="final_major_claims.producer_refs",
                    affected_claim=claim_id,
                )
            )

        for producer, ref_keys in _WAVE21_PRODUCER_REF_SPECS:
            claim_refs = _policy_design_refs_for_keys(claim, ref_keys)
            if producer == "scholar" and not claim_refs:
                continue
            if not claim_refs:
                continue
            if _policy_design_claim_selected_producer_refs(claim, producer=producer):
                continue
            gates.append(
                _policy_design_wave21_claim_gate(
                    code="policy_design_major_claim_producer_refs_missing",
                    message=(
                        f"Major claim {claim_id or '<unknown>'!r} cites refs from "
                        f"{producer!r} without claim-registry producer selection refs."
                    ),
                    missing_input=f"final_major_claims.selected_producer_refs.{producer}",
                    affected_claim=claim_id,
                )
            )

    return gates


def _policy_design_wave21_claim_ref_present(
    claim: Mapping[str, Any],
    *,
    field_name: str,
    ref_keys: tuple[str, ...],
) -> bool:
    if field_name == "objective_tradeoff_refs":
        return _policy_design_claim_has_objective_tradeoff_refs(claim)
    return bool(_policy_design_refs_for_keys(claim, ref_keys))


def _policy_design_claim_has_scholar_refs_or_deficit(claim: Mapping[str, Any]) -> bool:
    return bool(
        _policy_design_refs_for_keys(claim, _WAVE21_SCHOLAR_REF_KEYS)
        or _policy_design_refs_for_keys(claim, _WAVE21_SCHOLAR_DEFICIT_KEYS)
    )


def _policy_design_claim_uses_prose_backfill(claim: Mapping[str, Any]) -> bool:
    return any(_clean_text(claim.get(key)) for key in _WAVE21_PROSE_BACKFILL_KEYS)


def _policy_design_claim_has_runtime_assurance_node(
    case: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> bool:
    expected = set(
        _policy_design_text_values(
            claim.get("assurance_node_id")
            or claim.get("assurance_node_ref")
            or claim.get("claim_ref")
        )
    )
    if not expected:
        return False
    for node in _policy_design_claim_nodes(case):
        if not expected & set(_policy_design_claim_node_ids(node)):
            continue
        return _policy_design_claim_node_runtime_owned(node)
    return False


def _policy_design_claim_nodes(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    nodes = case.get("nodes")
    if not isinstance(nodes, list):
        return ()
    return tuple(
        node
        for node in nodes
        if isinstance(node, Mapping)
        and _clean_text(node.get("node_type")) == "claim"
    )


def _policy_design_claim_node_ids(node: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in (
        "assurance_node_id",
        "assurance_node_ref",
        "node_id",
        "record_id",
        "id",
        "claim_ref",
        "cas_ref",
    ):
        values.extend(_policy_design_text_values(node.get(key)))
    return tuple(dict.fromkeys(values))


def _policy_design_claim_node_runtime_owned(node: Mapping[str, Any]) -> bool:
    runtime_ref = _clean_text(node.get("cas_ref") or node.get("evidence_ref"))
    if not _policy_design_runtime_artifact_ref(runtime_ref):
        return False
    if not _policy_design_runtime_event_ref(node.get("runtime_event_ref")):
        return False
    envelope = node.get("runtime_authority_envelope") or node.get("authority_envelope")
    if isinstance(envelope, Mapping):
        provenance = _clean_text(envelope.get("provenance_kind"))
        authority_role = _clean_text(envelope.get("authority_role"))
    else:
        provenance = _clean_text(node.get("provenance_kind"))
        authority_role = _clean_text(node.get("authority_role"))
    return provenance == "runtime_emitted" and authority_role == "producer_authority"


def _policy_design_claim_selected_producer_refs(
    claim: Mapping[str, Any],
    *,
    producer: str,
) -> tuple[str, ...]:
    selected = (
        claim.get("selected_producer_refs")
        or claim.get("claim_registry_selected_refs")
        or claim.get("producer_refs")
    )
    if isinstance(selected, Mapping):
        producer_aliases = {
            producer,
            producer.replace("_", "-"),
            producer.replace("_", "."),
        }
        values: list[str] = []
        for alias in producer_aliases:
            values.extend(_policy_design_contract_ref_values(selected.get(alias)))
        if values:
            return tuple(dict.fromkeys(values))
    keys = (
        f"{producer}_producer_refs",
        f"{producer}_runtime_refs",
        f"selected_{producer}_refs",
    )
    return _policy_design_refs_for_keys(claim, keys)


def _policy_design_wave21_claim_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_claim_compiler_runtime_contract",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_claim_compiler_runtime_contract",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Mint final major claims as runtime-owned Policy Design Case claim "
            "nodes with claim-registry selected concept, norm, producer, portfolio, "
            "challenge, synthesis, uncertainty, numerical-semantics, and monitoring refs."
        ),
        missing_input=missing_input,
        affected_claim=affected_claim,
    )


def _policy_design_wave22_claim_argument_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    final_claims = _policy_design_final_major_claims(case)
    if not final_claims:
        return []
    result = validate_claim_argument_case_surfaces(
        case,
        effective_authority_profile=(
            _policy_design_case_effective_authority_profile(case) or canary_kind
        ),
    )
    return _policy_design_wave22_claim_argument_issue_gates(result)


def _policy_design_wave22_claim_argument_issue_gates(
    result: ClaimArgumentValidationResult,
) -> list[dict[str, Any]]:
    return [
        _policy_design_wave22_claim_argument_gate(
            code=issue.code,
            message=issue.message,
            evidence_ref=issue.evidence_ref,
            missing_input=issue.field,
            affected_claim=issue.claim_id,
        )
        for issue in result.issues
    ]


def _policy_design_wave22_claim_argument_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_claim_argument_surfaces",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_claim_argument_surfaces",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit explicit argument, warrant, rebuttal, visible counter-evidence, "
            "requester-capture challenge, assurance-deficit, and blocker surfaces "
            "for every final major claim."
        ),
        missing_input=missing_input,
        affected_claim=affected_claim,
    )


def policy_design_case_claim_closeout_gates(
    case: Mapping[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    """Evaluate Policy Design Case major-claim closeout gates for readiness."""

    quality_evidence = {"policy_design_case": case}
    gates: list[dict[str, Any]] = []
    gates.extend(
        _policy_design_wave15_evidence_portfolio_design_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    gates.extend(
        _policy_design_wave20_portfolio_readiness_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    gates.extend(
        _policy_design_wave21_claim_compiler_runtime_contract_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    gates.extend(
        _policy_design_wave22_claim_argument_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    gates.extend(
        _policy_design_wave25_research_deficit_promotion_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    gates.extend(
        _policy_design_wave27_governance_legitimacy_gates(
            quality_evidence,
            canary_kind=canary_kind,
        )
    )
    return gates


def _policy_design_wave27_governance_legitimacy_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    if not _policy_design_final_major_claims(case):
        return []
    validation = validate_policy_design_case_legitimacy_records(case)
    return [
        _gate(
            name="policy_design_governance_legitimacy",
            stage="ops",
            code=str(issue.get("code") or "policy_design_governance_legitimacy_invalid"),
            status="fail",
            layer="assurance_case",
            phase="policy_design_governance_legitimacy",
            message=str(
                issue.get("message")
                or "Policy Design Case governance and legitimacy record is invalid."
            ),
            evidence_ref=str(
                issue.get("evidence_ref") or "quality_evidence/policy_design_case.json"
            ),
            next_action=(
                "Emit effective independent human oversight, producer separation "
                "attestation, structured judgement-not-data records, and visible "
                "consultation objection response records before serious closeout."
            ),
            missing_input=str(issue.get("field") or ""),
            affected_claim=(
                str(issue.get("claim_id")) if issue.get("claim_id") else None
            ),
        )
        for issue in validation.get("issues", [])
        if isinstance(issue, Mapping)
    ]


def _policy_design_wave27_external_audit_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    if not _policy_design_final_major_claims(case):
        return []
    record = _policy_design_external_audit_record(case, quality_evidence)
    if record is None:
        if _policy_design_external_audit_blocked(case):
            return []
        return [
            _policy_design_external_audit_gate(
                code="policy_design_external_audit_record_missing",
                message=(
                    "Published Policy Design Cases require a public audit archive "
                    "record or explicit runtime blocker."
                ),
                missing_input="external_audit_record",
            )
        ]
    validation = validate_public_audit_archive_record(record)
    return [
        _policy_design_external_audit_gate(
            code=str(issue.get("code") or "policy_design_external_audit_record_invalid"),
            message=str(issue.get("message") or "Public audit archive record is invalid."),
            evidence_ref=_clean_text(record.get("record_id"))
            or "quality_evidence/policy_design_case.json",
            missing_input=str(issue.get("field") or ""),
        )
        for issue in validation.get("issues", [])
        if isinstance(issue, Mapping)
    ]


def _policy_design_external_audit_record(
    case: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for source in (case, quality_evidence):
        for key in (
            "external_audit_record",
            "public_audit_archive",
            "public_audit_archive_record",
            "publication_trust_and_external_governance",
        ):
            value = source.get(key)
            if isinstance(value, Mapping):
                return value
    return None


def _policy_design_external_audit_blocked(case: Mapping[str, Any]) -> bool:
    blockers: list[Mapping[str, Any]] = []
    for key in (
        "external_audit_blockers",
        "public_archive_blockers",
        "publication_trust_blockers",
        "record_family_blockers",
    ):
        value = case.get(key)
        if isinstance(value, list):
            blockers.extend(item for item in value if isinstance(item, Mapping))
        elif isinstance(value, Mapping):
            blockers.append(value)
    families = {
        "publication_trust_and_external_governance.v1",
        "external_audit",
        "public_audit_archive",
    }
    active_statuses = {"active", "accepted", "blocked", "fail", "open", "unresolved"}
    for blocker in blockers:
        status = _clean_text(blocker.get("status") or blocker.get("blocker_status")) or "active"
        if status not in active_statuses:
            continue
        family = _clean_text(
            blocker.get("record_family")
            or blocker.get("family_id")
            or blocker.get("blocked_record_family")
        )
        code = _clean_text(blocker.get("code") or blocker.get("blocker_code")) or ""
        if not (family in families or any(family_name in code for family_name in families)):
            continue
        evidence_ref = _clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref"))
        if _policy_design_runtime_artifact_ref(
            evidence_ref
        ) and _policy_design_runtime_event_ref(blocker.get("runtime_event_ref")):
            return True
    return False


def _policy_design_external_audit_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_public_audit_archive",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_external_audit",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit a public audit archive record with PROV JSON, SLSA attestation, "
            "standalone verifier, safe archive metadata, and public exported refs."
        ),
        missing_input=missing_input,
    )


def _policy_design_wave28_5_external_client_surface_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    if not _policy_design_final_major_claims(case):
        return []

    record = _policy_design_external_client_surface_record(case, quality_evidence)
    if record is None:
        if _policy_design_external_client_surface_blocked(case):
            return []
        return [
            _policy_design_external_client_surface_gate(
                code="policy_design_external_client_surface_record_missing",
                message=(
                    "Production Policy Design Cases require external connector, plugin, "
                    "dependency, provenance, and client-surface authority records or "
                    "an explicit runtime blocker."
                ),
                missing_input="external_plugin_dependency_client_surface",
            )
        ]

    validation = validate_external_client_surface_record(record)
    return [
        _policy_design_external_client_surface_gate(
            code=str(issue.get("code") or "policy_design_external_client_surface_invalid"),
            message=str(
                issue.get("message")
                or "External/plugin/dependency/client-surface record is invalid."
            ),
            evidence_ref=_clean_text(record.get("record_id"))
            or "quality_evidence/policy_design_case.json",
            missing_input=str(issue.get("field") or ""),
        )
        for issue in validation.get("issues", [])
        if isinstance(issue, Mapping)
    ]


def _policy_design_external_client_surface_record(
    case: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for source in (case, quality_evidence):
        for key in (
            "external_plugin_dependency_client_surface",
            "external_client_surface",
            "external_client_surface_record",
            "phase_28_5_external_client_surface",
            "publication_trust_external_client_surface",
        ):
            value = source.get(key)
            if isinstance(value, Mapping):
                return value
    return None


def _policy_design_wave29_1_evidence_graph_threat_model_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    if not _policy_design_final_major_claims(case):
        return []

    record = _policy_design_evidence_graph_threat_model_record(case, quality_evidence)
    gates: list[dict[str, Any]] = []
    for issue in validate_evidence_graph_threat_model_record(record):
        gate_fields = issue.as_gate_fields()
        gates.append(
            _policy_design_evidence_graph_threat_model_gate(
                code=str(gate_fields["code"]),
                message=str(gate_fields["message"]),
                evidence_ref=gate_fields["evidence_ref"],
                missing_input=str(gate_fields["field"]),
                threat_id=gate_fields["threat_id"],
            )
        )
    return gates


def _policy_design_evidence_graph_threat_model_record(
    case: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for source in (case, quality_evidence):
        for key in (
            "evidence_graph_threat_model",
            "evidence_graph_threat_model_record",
            "integrity_threat_model",
            "phase_29_1_evidence_graph_threat_model",
        ):
            value = source.get(key)
            if isinstance(value, Mapping):
                return value
    integrity = case.get("integrity_self_fmea_and_maturity")
    if isinstance(integrity, Mapping):
        value = integrity.get("evidence_graph_threat_model")
        if isinstance(value, Mapping):
            return value
    return None


def _policy_design_evidence_graph_threat_model_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    threat_id: str | None = None,
) -> dict[str, Any]:
    gate = _gate(
        name="policy_design_evidence_graph_threat_model",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_evidence_graph_threat_model",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit Phase 29.1 evidence-graph threat model records for prompt "
            "injection, poisoned datasets, stale indexes, malicious tenants, "
            "forged provenance, compromised plugins, local-client leakage, and "
            "insider mutation before serious closeout."
        ),
        missing_input=missing_input,
    )
    if threat_id is not None:
        gate["threat_id"] = threat_id
    return gate


def _policy_design_external_client_surface_blocked(case: Mapping[str, Any]) -> bool:
    blockers: list[Mapping[str, Any]] = []
    for key in (
        "external_client_surface_blockers",
        "external_plugin_dependency_blockers",
        "publication_trust_blockers",
        "record_family_blockers",
    ):
        value = case.get(key)
        if isinstance(value, list):
            blockers.extend(item for item in value if isinstance(item, Mapping))
        elif isinstance(value, Mapping):
            blockers.append(value)
    families = {
        "external_plugin_dependency_client_surface.v1",
        "external_client_surface",
        "phase_28_5",
        "PDD-073",
        "PDD-085",
        "PDD-089",
        "PDD-091",
        "PDD-092",
        "PDD-093",
        "PDD-094",
        "PDD-102",
    }
    active_statuses = {"active", "accepted", "blocked", "fail", "open", "unresolved"}
    for blocker in blockers:
        status = _clean_text(blocker.get("status") or blocker.get("blocker_status")) or "active"
        if status not in active_statuses:
            continue
        family = _clean_text(
            blocker.get("record_family")
            or blocker.get("family_id")
            or blocker.get("blocked_record_family")
            or blocker.get("diagnostic_id")
        )
        code = _clean_text(blocker.get("code") or blocker.get("blocker_code")) or ""
        if not (family in families or any(family_name in code for family_name in families)):
            continue
        evidence_ref = _clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref"))
        if _policy_design_runtime_artifact_ref(
            evidence_ref
        ) and _policy_design_runtime_event_ref(blocker.get("runtime_event_ref")):
            return True
    return False


def _policy_design_external_client_surface_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_external_client_surface",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_external_client_surface",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit Phase 28.5 records for connector acquisition, plugin isolation, "
            "dependency/provider rights, external evidence provenance, offline "
            "mutation authority, collaboration attribution, assistant/composer "
            "provenance, bureaucratic rendering/export, and client persistence privacy."
        ),
        missing_input=missing_input,
    )


def _policy_design_wave28_config_release_hardening_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []
    if not _policy_design_final_major_claims(case):
        return []
    record = _policy_design_config_release_hardening_record(case, quality_evidence)
    issues = validate_config_release_deployment_migration_hardening_record(record)
    return [
        _policy_design_config_release_hardening_gate(
            code=issue.code,
            message=issue.message,
            evidence_ref=issue.evidence_ref,
            missing_input=issue.field,
        )
        for issue in issues
    ]


def _policy_design_config_release_hardening_record(
    case: Mapping[str, Any],
    quality_evidence: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    keys = (
        "config_release_deployment_migration_hardening",
        "config_release_hardening",
        "deployment_release_migration_hardening",
        "publication_hardening",
    )
    for source in (case, quality_evidence):
        for key in keys:
            value = source.get(key)
            if isinstance(value, Mapping):
                return value
    publication_trust = case.get("publication_trust_and_external_governance")
    if isinstance(publication_trust, Mapping):
        value = publication_trust.get("config_release_deployment_migration_hardening")
        if isinstance(value, Mapping):
            return value
    return None


def _policy_design_config_release_hardening_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_config_release_deployment_migration_hardening",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_config_release_deployment_migration_hardening",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Emit Phase 28.4 Policy Design Case evidence for deployment parity, "
            "release provenance, persisted-state migration, quarantine/shim "
            "lifecycle, generated-surface drift, runbooks, retention/deletion, "
            "and replay before serious closeout."
        ),
        missing_input=missing_input,
    )


def _policy_design_wave25_research_deficit_promotion_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    case = quality_evidence.get("policy_design_case")
    if not isinstance(case, Mapping):
        return []

    effective_profile = _policy_design_case_effective_authority_profile(case) or canary_kind
    closeout_profile = _policy_design_closeout_authority_profile(
        effective_profile=effective_profile,
        canary_kind=canary_kind,
    )
    if _profile_key(closeout_profile) not in _POLICY_DESIGN_PROMOTED_AUTHORITY_PROFILES:
        return []

    gates: list[dict[str, Any]] = []
    for deficit in _policy_design_accepted_deficit_rows(case):
        if not _policy_design_deficit_is_accepted(deficit):
            continue
        if not _policy_design_deficit_is_research_only_promotion(
            deficit,
            effective_profile=closeout_profile,
        ):
            continue
        gates.append(
            _policy_design_wave25_claim_closeout_gate(
                code="policy_design_research_deficit_promoted_to_authority",
                message=(
                    "Accepted research-profile assurance deficits cannot be "
                    f"silently promoted to {closeout_profile!r} authority."
                ),
                evidence_ref=_clean_text(deficit.get("evidence_ref") or deficit.get("cas_ref")),
                missing_input="accepted_deficits.authority_promotion_approval_ref",
                affected_claim=_clean_text(
                    deficit.get("claim_id") or deficit.get("major_claim_id")
                ),
            )
        )
    return gates


def _policy_design_closeout_authority_profile(
    *,
    effective_profile: str,
    canary_kind: str,
) -> str:
    for value in (effective_profile, canary_kind):
        if _profile_key(value) in _POLICY_DESIGN_PROMOTED_AUTHORITY_PROFILES:
            return value
    return effective_profile


def _policy_design_deficit_is_research_only_promotion(
    deficit: Mapping[str, Any],
    *,
    effective_profile: str,
) -> bool:
    if _policy_design_refs_for_keys(deficit, _POLICY_DESIGN_DEFICIT_PROMOTION_APPROVAL_KEYS):
        return False
    accepted_profiles = {
        _profile_key(value)
        for key in _POLICY_DESIGN_DEFICIT_PROFILE_KEYS
        for value in _policy_design_text_values(deficit.get(key))
    }
    source_profiles = {
        _profile_key(value)
        for key in _POLICY_DESIGN_DEFICIT_SOURCE_PROFILE_KEYS
        for value in _policy_design_text_values(deficit.get(key))
    }
    accepted_profiles.discard("")
    source_profiles.discard("")
    if source_profiles & _POLICY_DESIGN_RESEARCH_DEFICIT_PROFILES:
        return True
    if accepted_profiles:
        return accepted_profiles <= _POLICY_DESIGN_RESEARCH_DEFICIT_PROFILES
    return _profile_key(effective_profile) in _POLICY_DESIGN_PROMOTED_AUTHORITY_PROFILES


def _policy_design_deficit_is_accepted(deficit: Mapping[str, Any]) -> bool:
    return _profile_key(deficit.get("status") or deficit.get("decision")) == "accepted"


def _profile_key(value: object) -> str:
    text = _clean_text(value)
    return text.casefold().replace("-", "_") if text else ""


def _policy_design_wave25_claim_closeout_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave25_claim_closeout",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_claim_closeout",
        message=message,
        evidence_ref=evidence_ref or "quality_evidence/policy_design_case.json",
        next_action=(
            "Keep research-profile deficits visible as deficits, or emit a "
            "runtime-owned governed/production claim with fresh producer, "
            "portfolio, argument, warrant, rebuttal, counter-evidence, BERL, "
            "and approval evidence."
        ),
        missing_input=missing_input,
        affected_claim=affected_claim,
    )


def _policy_design_producer_contract_row_runtime_owned(row: Mapping[str, Any]) -> bool:
    if _clean_text(row.get("provenance_kind")) != "runtime_emitted":
        return False
    runtime_ref = _clean_text(row.get("cas_ref") or row.get("evidence_ref"))
    if not _policy_design_runtime_artifact_ref(runtime_ref):
        return False
    return _policy_design_runtime_event_ref(row.get("runtime_event_ref"))


def _policy_design_wave14_contract_surface_gates(
    *,
    producer: str,
    rows: tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    checks: tuple[tuple[tuple[str, ...], str, str, bool], ...] = (
        (
            _WAVE14_SELECTED_REF_KEYS,
            "policy_design_producer_selected_candidates_missing",
            "selected candidate refs",
            False,
        ),
        (
            _WAVE14_REJECTED_REF_KEYS,
            "policy_design_producer_rejected_candidates_missing",
            "rejected candidate refs",
            False,
        ),
        (
            _WAVE14_SOURCE_RIGHTS_KEYS,
            "policy_design_producer_source_rights_missing",
            "source rights refs",
            False,
        ),
        (
            _WAVE14_FRESHNESS_KEYS,
            "policy_design_producer_freshness_missing",
            "freshness refs",
            False,
        ),
        (
            _WAVE14_QUALITY_KEYS,
            "policy_design_producer_quality_missing",
            "quality refs",
            False,
        ),
        (
            _WAVE14_SNAPSHOT_KEYS,
            "policy_design_producer_snapshot_identity_missing",
            "snapshot identity refs",
            False,
        ),
        (
            _WAVE14_BLOCKER_KEYS,
            "policy_design_producer_blocker_missing",
            "blocker refs or explicit empty blocker list",
            True,
        ),
    )
    gates: list[dict[str, Any]] = []
    for keys, code, label, allow_empty in checks:
        if _policy_design_contract_surface_present(rows, keys, allow_empty=allow_empty):
            continue
        gates.append(
            _policy_design_wave14_producer_gate(
                code=code,
                message=(
                    f"Final claims cannot consume {producer!r} producer evidence "
                    f"without {label}."
                ),
                producer=producer,
                missing_input=f"producer_evidence.{producer}.{keys[0]}",
            )
        )
    gates.extend(_policy_design_wave14_local_ref_gates(producer=producer, rows=rows))
    return gates


def _policy_design_contract_surface_present(
    rows: tuple[Mapping[str, Any], ...],
    keys: tuple[str, ...],
    *,
    allow_empty: bool,
) -> bool:
    for row in rows:
        for key in keys:
            if key not in row:
                continue
            if allow_empty:
                return True
            if _policy_design_contract_ref_values(row.get(key)):
                return True
            value = row.get(key)
            if isinstance(value, Mapping) and value:
                return True
            if isinstance(value, list) and value:
                return True
    return False


def _policy_design_wave14_local_ref_gates(
    *,
    producer: str,
    rows: tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for row in rows:
        for field in _WAVE14_CONTRACT_REF_FIELDS:
            for value in _policy_design_contract_ref_values(row.get(field)):
                if not _policy_design_is_local_ref(value):
                    continue
                key = f"{field}:{value}"
                if key in emitted:
                    continue
                emitted.add(key)
                gates.append(
                    _policy_design_wave14_producer_gate(
                        code="policy_design_producer_local_path_not_authority",
                        message=(
                            f"Producer {producer!r} contract field {field!r} uses a "
                            "local file ref instead of runtime authority."
                        ),
                        producer=producer,
                        evidence_ref=value,
                        missing_input=f"producer_evidence.{producer}.{field}",
                    )
                )
    return gates


def _policy_design_merged_rows(
    rows: tuple[Mapping[str, Any], ...],
) -> dict[str, list[object]]:
    merged: dict[str, list[object]] = {}
    for row in rows:
        for key, value in row.items():
            merged.setdefault(str(key), []).append(value)
    return merged


def _policy_design_refs_for_keys(
    payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_policy_design_contract_ref_values(payload.get(key)))
    return tuple(dict.fromkeys(refs))


def _policy_design_contract_ref_values(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, str):
        text = _clean_text(value)
        if text:
            values.append(text)
    elif isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key in _WAVE14_CONTRACT_TEXT_KEYS or isinstance(
                child, Mapping | list | tuple | set
            ):
                values.extend(_policy_design_contract_ref_values(child))
    elif isinstance(value, list | tuple | set):
        for item in value:
            values.extend(_policy_design_contract_ref_values(item))
    return tuple(dict.fromkeys(values))


def _policy_design_wave14_producer_gate(
    *,
    code: str,
    message: str,
    producer: str,
    evidence_ref: str | None = None,
    next_action: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave14_producer_scorecard",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_producer_scorecard",
        message=message,
        evidence_ref=evidence_ref or _POLICY_DESIGN_OPTIONS_EVIDENCE_REF,
        next_action=next_action
        or (
            "Emit producer-owned runtime evidence with selected/rejected candidates, "
            "rights, freshness, quality, snapshot identity, blocker state, CAS "
            "identity, and diagnostic event linkage before portfolio or claim use."
        ),
        missing_input=missing_input or f"producer_evidence.{producer}",
        affected_claim=affected_claim,
    )


def _policy_design_dependency_producer_hint(value: str) -> str | None:
    normalized = value.casefold().replace("-", "_")
    for alias, producer in _WAVE12_PRODUCER_ALIASES.items():
        if alias in normalized:
            return producer
    return None


def _policy_design_producer_authority_gates(
    row: Mapping[str, Any],
    *,
    producer: str,
) -> tuple[list[dict[str, Any]], bool]:
    provenance_kind = _clean_text(row.get("provenance_kind"))
    status = _clean_text(row.get("status") or row.get("quality_status"))
    if provenance_kind == "runtime_blocker" or (status or "").casefold() == "blocked":
        return _policy_design_producer_blocker_gates(row, producer=producer)

    gates: list[dict[str, Any]] = []
    source_surface = _clean_text(row.get("source_surface")) or ""
    evidence_ref = _clean_text(row.get("evidence_ref"))
    cas_ref = _clean_text(row.get("cas_ref"))
    runtime_ref = cas_ref or evidence_ref

    if provenance_kind == "static_inventory" or source_surface == "architecture.inventory":
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_static_inventory_not_authority",
                message=(
                    f"Wave 12 producer {producer!r} evidence is a static inventory, "
                    "not runtime-owned evidence."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
            )
        )
        return gates, False
    if _policy_design_is_local_ref(runtime_ref) or _policy_design_is_local_ref(evidence_ref):
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_local_path_not_authority",
                message=(
                    f"Wave 12 producer {producer!r} evidence uses a local path instead "
                    "of CAS/runtime authority."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
            )
        )
        return gates, False
    if (
        provenance_kind == "narrative_citation"
        or source_surface == "narrative_citation"
        or _policy_design_looks_like_narrative(evidence_ref)
    ):
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_narrative_citation_not_authority",
                message=(
                    f"Wave 12 producer {producer!r} evidence is only narrative citation "
                    "text, not runtime-owned provenance."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
            )
        )
        return gates, False
    if provenance_kind != "runtime_emitted":
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_runtime_authority_missing",
                message=(
                    f"Wave 12 producer {producer!r} must use "
                    "provenance_kind=runtime_emitted or runtime_blocker."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
                missing_input="provenance_kind",
            )
        )
        return gates, False
    if not _policy_design_runtime_artifact_ref(runtime_ref):
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_runtime_authority_missing",
                message=(
                    f"Wave 12 producer {producer!r} must cite a CAS/artifact evidence ref."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
                missing_input="evidence_ref",
            )
        )
        return gates, False
    if not _policy_design_runtime_event_ref(row.get("runtime_event_ref")):
        gates.append(
            _policy_design_producer_gate(
                code="policy_design_producer_runtime_event_missing",
                message=(
                    f"Wave 12 producer {producer!r} must cite the runtime event that "
                    "emitted the evidence."
                ),
                producer=producer,
                evidence_ref=evidence_ref or cas_ref,
                missing_input="runtime_event_ref",
            )
        )
        return gates, False
    return gates, True


def _policy_design_producer_blocker_gates(
    row: Mapping[str, Any],
    *,
    producer: str,
) -> tuple[list[dict[str, Any]], bool]:
    blockers = row.get("blockers") or row.get("runtime_blockers")
    if not isinstance(blockers, list) or not any(isinstance(item, Mapping) for item in blockers):
        return [
            _policy_design_producer_gate(
                code="policy_design_producer_blocker_missing",
                message=(
                    f"Blocked Wave 12 producer {producer!r} must preserve typed blocker "
                    "details."
                ),
                producer=producer,
                evidence_ref=_clean_text(row.get("evidence_ref") or row.get("cas_ref")),
                missing_input="blockers",
            )
        ], False

    gates: list[dict[str, Any]] = []
    valid_blocker_seen = False
    for blocker in blockers:
        if not isinstance(blocker, Mapping):
            continue
        code = _clean_text(blocker.get("code"))
        message = _clean_text(blocker.get("message") or blocker.get("downstream_impact"))
        evidence_ref = _clean_text(
            blocker.get("evidence_ref") or blocker.get("cas_ref") or row.get("evidence_ref")
        )
        runtime_event_ref = blocker.get("runtime_event_ref") or row.get("runtime_event_ref")
        if code and message and _policy_design_runtime_artifact_ref(
            evidence_ref
        ) and _policy_design_runtime_event_ref(runtime_event_ref):
            valid_blocker_seen = True
            gates.append(
                _policy_design_producer_gate(
                    code=code,
                    message=message,
                    producer=producer,
                    evidence_ref=evidence_ref,
                    next_action=_clean_text(blocker.get("next_action")),
                )
            )
    if valid_blocker_seen:
        return gates, True
    return [
        _policy_design_producer_gate(
            code="policy_design_producer_blocker_missing",
            message=(
                f"Blocked Wave 12 producer {producer!r} has no blocker with code, "
                "message, CAS evidence ref, and runtime event ref."
            ),
            producer=producer,
            evidence_ref=_clean_text(row.get("evidence_ref") or row.get("cas_ref")),
            missing_input="blockers",
        )
    ], False


def _policy_design_runtime_artifact_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None or _policy_design_is_local_ref(text):
        return False
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    return text.startswith("artifact://")


def _policy_design_runtime_event_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None or _policy_design_is_local_ref(text):
        return False
    return _policy_design_runtime_artifact_ref(text) or text.startswith("event://")


def _policy_design_is_local_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return text.casefold().startswith(_POLICY_DESIGN_LOCAL_REF_PREFIXES)


def _policy_design_looks_like_narrative(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return not _policy_design_runtime_artifact_ref(text) and " " in text


def _policy_design_producer_gate(
    *,
    code: str,
    message: str,
    producer: str,
    evidence_ref: str | None = None,
    next_action: str | None = None,
    missing_input: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_wave12_producer_evidence",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase="policy_design_producer_evidence",
        message=message,
        evidence_ref=evidence_ref or _POLICY_DESIGN_OPTIONS_EVIDENCE_REF,
        next_action=next_action
        or (
            "Emit Wave 12 producer evidence or a typed runtime blocker from the "
            "producer runtime, with CAS identity and diagnostic event linkage."
        ),
        missing_input=missing_input or f"producer_evidence.{producer}",
    )


def _policy_design_options_record(case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    candidates = (
        case.get("options_objectives_tradeoffs"),
        case.get("options_objectives_and_tradeoffs"),
        case.get("option_objective_tradeoff_record"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _clean_text(node.get("node_type"))
            node_family = _clean_text(node.get("node_family"))
            if node_type in {
                "options_objectives_tradeoffs",
                "options_objectives_and_tradeoffs",
                "option_objective_tradeoff",
            } or node_family == "options_objectives_and_tradeoffs":
                return node
    return None


def _policy_design_options_record_gates(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    if _clean_text(record.get("status")) == "blocked":
        blockers = record.get("blockers")
        if isinstance(blockers, list) and blockers:
            for blocker in blockers:
                if not isinstance(blocker, Mapping):
                    continue
                gates.append(
                    _policy_design_options_gate(
                        code=(
                            _clean_text(blocker.get("code"))
                            or "policy_design_options_objectives_tradeoffs_blocked"
                        ),
                        message=(
                            _clean_text(blocker.get("message"))
                            or _clean_text(blocker.get("downstream_impact"))
                            or "Options/objectives/tradeoffs producer emitted a typed blocker."
                        ),
                        evidence_ref=_clean_text(blocker.get("evidence_ref")),
                        next_action=_clean_text(blocker.get("next_action")),
                    )
                )
            return gates
        gates.append(
            _policy_design_options_gate(
                code="policy_design_options_objectives_tradeoffs_blocked",
                message=(
                    "Options/objectives/tradeoffs record is blocked without typed blocker "
                    "details."
                ),
            )
        )

    if record and not _policy_design_options_has_runtime_authority(record):
        gates.append(
            _policy_design_options_gate(
                code="policy_design_options_runtime_authority_missing",
                message=(
                    "Options/objectives/tradeoffs record must be runtime-emitted and "
                    "linked to CAS evidence plus a runtime diagnostic event."
                ),
                missing_input="options_objectives_tradeoffs.runtime_authority",
            )
        )

    field_checks: tuple[tuple[str, str, str, str], ...] = (
        (
            "baseline_option",
            "policy_design_options_baseline_missing",
            "baseline/no-action option",
            "mapping",
        ),
        (
            "candidate_options",
            "policy_design_candidate_options_missing",
            "candidate options",
            "list",
        ),
        (
            "rejected_options",
            "policy_design_rejected_options_missing",
            "rejected options with rationale",
            "list",
        ),
        (
            "objective_function",
            "policy_design_objective_function_missing",
            "objective function",
            "mapping",
        ),
        (
            "tradeoff_weights",
            "policy_design_tradeoff_weights_missing",
            "tradeoff weights and source",
            "list",
        ),
        (
            "social_weights",
            "policy_design_social_weights_missing",
            "social welfare weights",
            "mapping_or_list",
        ),
        (
            "welfare_bounds",
            "policy_design_welfare_bounds_missing",
            "welfare bounds",
            "mapping",
        ),
        (
            "distributional_effects",
            "policy_design_distributional_effects_missing",
            "distributional effects",
            "list",
        ),
        (
            "qualitative_effects",
            "policy_design_qualitative_effects_missing",
            "qualitative non-monetized effects",
            "list",
        ),
        (
            "risk",
            "policy_design_risk_record_missing",
            "risk record",
            "mapping",
        ),
        (
            "uncertainty",
            "policy_design_uncertainty_record_missing",
            "uncertainty record",
            "mapping",
        ),
    )
    for field_name, code, label, expected in field_checks:
        value = _policy_design_options_field(record, field_name)
        if _policy_design_options_field_present(value, expected):
            continue
        gates.append(
            _policy_design_options_gate(
                code=code,
                message=f"Final policy recommendations require {label}.",
                missing_input=field_name,
            )
        )

    source_ref_checks: tuple[tuple[set[str], str, str], ...] = (
        (
            {"foundry_welfare_ref", "welfare_ref", "welfare_bundle_ref", "welfare_weights_ref"},
            "policy_design_foundry_welfare_ref_missing",
            "Foundry/IR welfare refs must back welfare bounds and social weights.",
        ),
        (
            {
                "foundry_uncertainty_ref",
                "uncertainty_ref",
                "uncertainty_envelope_ref",
                "interval_ref",
            },
            "policy_design_foundry_uncertainty_ref_missing",
            "Foundry uncertainty refs must back the uncertainty record.",
        ),
        (
            {
                "ir_distributional_ref",
                "distributional_report_ref",
                "distributional_bounds_ref",
            },
            "policy_design_ir_distributional_ref_missing",
            "IR distributional analytics refs must back distributional effects.",
        ),
        (
            {"ir_fairness_ref", "fairness_report_ref", "fairness_audit_ref"},
            "policy_design_ir_fairness_ref_missing",
            "IR fairness analytics refs must back distributional effects.",
        ),
        (
            {"ir_mobility_ref", "mobility_report_ref", "mobility_analysis_ref"},
            "policy_design_ir_mobility_ref_missing",
            "IR mobility analytics refs must back distributional effects.",
        ),
    )
    for keys, code, message in source_ref_checks:
        if _policy_design_nested_ref_present(record, keys):
            continue
        gates.append(_policy_design_options_gate(code=code, message=message))
    return gates


def _policy_design_options_has_runtime_authority(record: Mapping[str, Any]) -> bool:
    if _clean_text(record.get("provenance_kind")) != "runtime_emitted":
        return False
    runtime_ref = _clean_text(record.get("cas_ref") or record.get("evidence_ref"))
    if not _policy_design_runtime_artifact_ref(runtime_ref):
        return False
    return _policy_design_runtime_event_ref(record.get("runtime_event_ref"))


def _policy_design_options_field(record: Mapping[str, Any], field_name: str) -> object:
    if field_name == "baseline_option":
        for alias in ("baseline_option", "no_action_option", "baseline_no_action_option"):
            value = record.get(alias)
            if value is not None:
                return value
        return None
    if field_name == "candidate_options":
        return record.get("candidate_options") or record.get("alternatives")
    return record.get(field_name)


def _policy_design_options_field_present(value: object, expected: str) -> bool:
    if expected == "mapping":
        return isinstance(value, Mapping) and bool(value)
    if expected == "list":
        return isinstance(value, list) and bool(value)
    if expected == "mapping_or_list":
        if isinstance(value, Mapping):
            return bool(value)
        return isinstance(value, list) and bool(value)
    return False


def _policy_design_nested_ref_present(value: object, accepted_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in accepted_keys and _clean_text(child):
                return True
            if _policy_design_nested_ref_present(child, accepted_keys):
                return True
    elif isinstance(value, list):
        return any(_policy_design_nested_ref_present(item, accepted_keys) for item in value)
    return False


def _policy_design_final_claim_objective_ref_gates(
    final_claims: tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for claim in final_claims:
        if _policy_design_claim_has_objective_tradeoff_refs(claim):
            continue
        claim_id = _clean_text(claim.get("claim_id")) or _clean_text(claim.get("id"))
        gates.append(
            _policy_design_options_gate(
                code="policy_design_final_recommendation_objective_tradeoff_refs_missing",
                message=(
                    "Final policy recommendations must cite objective/tradeoff refs "
                    "from the options_objectives_tradeoffs record."
                ),
                missing_input="final_major_claims.objective_tradeoff_refs",
                affected_claim=claim_id,
            )
        )
    return gates


def _policy_design_claim_has_objective_tradeoff_refs(claim: Mapping[str, Any]) -> bool:
    if _truthy_text_refs(claim.get("objective_tradeoff_refs")):
        return True
    return _truthy_text_refs(claim.get("objective_refs")) and _truthy_text_refs(
        claim.get("tradeoff_refs")
    )


def _policy_design_final_major_claims(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    claims = case.get("final_major_claims") or case.get("major_claims") or ()
    if not isinstance(claims, list):
        return ()
    final_claims: list[Mapping[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        if claim.get("major") is False:
            continue
        final_claims.append(claim)
    return tuple(final_claims)


def _truthy_text_refs(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set):
        return any(isinstance(item, str) and bool(item.strip()) for item in value)
    return False


def _policy_design_options_gate(
    *,
    code: str,
    message: str,
    evidence_ref: str | None = None,
    next_action: str | None = None,
    missing_input: str | None = None,
    affected_claim: str | None = None,
) -> dict[str, Any]:
    return _gate(
        name="policy_design_options_objectives_tradeoffs",
        stage="ops",
        code=code,
        status="fail",
        layer="assurance_case",
        phase=_POLICY_DESIGN_OPTIONS_PHASE,
        message=message,
        evidence_ref=evidence_ref or _POLICY_DESIGN_OPTIONS_EVIDENCE_REF,
        next_action=next_action or _POLICY_DESIGN_OPTIONS_NEXT_ACTION,
        missing_input=missing_input,
        affected_claim=affected_claim,
    )


def _policy_design_case_runtime_identity_gates(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    events = _diagnostic_event_records(job_payload=job_payload, run_payload=run_payload)
    event_ref_values = {ref for event in events for ref in _diagnostic_event_ref_values(event)}
    gates: list[dict[str, Any]] = []
    for ref_key in POLICY_DESIGN_CASE_RUNTIME_REF_KEYS:
        runtime_ref = authority_refs.get(ref_key)
        if runtime_ref is None:
            gates.append(
                _gate(
                    name="policy_design_case_runtime_identity",
                    stage="ops",
                    code=f"{ref_key}_missing",
                    status="fail",
                    layer="policy_design_case_profile",
                    phase="policy_design_case_identity",
                    message=f"Serious policy closeout requires runtime {ref_key}.",
                    evidence_ref="job.json" if job_payload is not None else "run.json",
                    next_action=(
                        "Materialize policy intent, capability ledger, and Policy "
                        "Design Case refs before scorecard closeout."
                    ),
                )
            )
            continue
        if _is_bundle_local_ref(runtime_ref) or not _is_cas_authority_ref(runtime_ref):
            gates.append(
                _gate(
                    name="policy_design_case_runtime_identity",
                    stage="ops",
                    code="policy_design_case_runtime_ref_invalid",
                    status="fail",
                    layer="policy_design_case_profile",
                    phase="policy_design_case_identity",
                    message=f"Policy Design Case runtime {ref_key} is not CAS authority.",
                    evidence_ref=runtime_ref,
                    next_action="Persist Policy Design Case identity refs through runtime CAS.",
                )
            )
            continue
        if event_ref_values and runtime_ref not in event_ref_values:
            gates.append(
                _gate(
                    name="policy_design_case_runtime_identity",
                    stage="ops",
                    code="policy_design_case_runtime_event_missing",
                    status="fail",
                    layer="policy_design_case_profile",
                    phase="policy_design_case_identity",
                    message=f"Policy Design Case runtime {ref_key} has no diagnostic event.",
                    evidence_ref=runtime_ref,
                    next_action=(
                        "Emit unsampled diagnostic events for policy intent, capability "
                        "ledger, and Policy Design Case refs."
                    ),
                )
            )
    return gates


def _policy_design_parallel_authority_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    for key in POLICY_DESIGN_PARALLEL_AUTHORITY_KEYS:
        if key not in quality_evidence:
            continue
        return [
            _gate(
                name="policy_design_case_parallel_authority_absent",
                stage="ops",
                code="policy_design_parallel_case_authority",
                status="fail",
                layer="policy_design_case_profile",
                phase="policy_design_case_authority",
                message=(
                    "Serious policy closeout must use runtime/quality Policy Design "
                    "Case authority, not a parallel case authority."
                ),
                evidence_ref=f"quality_evidence/{key}.json",
                next_action=(
                    "Delete the parallel authority surface and route case identity "
                    "through polisyos.runtime.quality.assurance_case."
                ),
            )
        ]
    return []


def _projection_quality_status_gates(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    projected_status = _nested_get(payload, "quality_status")
    projected_scorecard = _nested_get(payload, "quality_scorecard")
    scorecard_status = (
        projected_scorecard.get("quality_status") if isinstance(projected_scorecard, dict) else None
    )
    has_projected_quality_pass = (
        str(projected_status or scorecard_status or "").strip().casefold() == "pass"
    )
    has_projected_readiness_closeout = any(
        _payload_projects_readiness_closeout(candidate)
        for candidate in _projection_boundary_payloads(payload)
    )
    if not (has_projected_quality_pass or has_projected_readiness_closeout):
        return []
    return [
        _gate(
            name="projection_quality_status_not_authority",
            stage="ops",
            code="projection_quality_status_not_authority",
            status="fail",
            layer="quality_scorecard",
            phase="projection_boundary",
            message=(
                "Input, progress, bundle, dashboard quality_status, or approval readiness "
                "is projection-only."
            ),
            evidence_ref="job.json" if job_payload is not None else "run.json",
            next_action="Rebuild closeout from runtime events, CAS refs, and authority envelopes.",
        )
    ]


def _projection_boundary_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for root_key in ("job", "run"):
        root = payload.get(root_key)
        if not isinstance(root, dict):
            continue
        candidates.append(root)
        progress = root.get("progress")
        if isinstance(progress, dict):
            candidates.append(progress)
            details = progress.get("details")
            if isinstance(details, dict):
                for projection_key in (
                    "api_projection",
                    "dashboard_approval_projection",
                    "dashboard_projection",
                    "quality_scorecard",
                    "readiness_projection",
                    "scorecard_projection",
                ):
                    projection = details.get(projection_key)
                    if isinstance(projection, dict):
                        candidates.append(projection)
        for projection_key in (
            "api_projection",
            "dashboard_approval_projection",
            "dashboard_projection",
            "quality_scorecard",
            "readiness_projection",
            "scorecard_projection",
        ):
            projection = root.get(projection_key)
            if isinstance(projection, dict):
                candidates.append(projection)
    return candidates


def _payload_projects_readiness_closeout(payload: dict[str, Any]) -> bool:
    approval_state = str(payload.get("approval_state") or "").strip().casefold()
    readiness = str(payload.get("readiness") or "").strip().casefold()
    eligibility = payload.get("approval_eligibility")
    return (
        approval_state == "approval_ready"
        or readiness in {"approved", "approval_ready", "pass", "ready", "readiness_closed"}
        or (isinstance(eligibility, dict) and eligibility.get("eligible") is True)
    )


def _iter_mapping_payloads(
    payload: object,
    *,
    path: str = "$",
) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(payload, dict):
        rows = [(path, payload)]
        for key, value in payload.items():
            rows.extend(_iter_mapping_payloads(value, path=f"{path}.{key}"))
        return rows
    if isinstance(payload, list):
        rows: list[tuple[str, dict[str, Any]]] = []
        for index, value in enumerate(payload):
            rows.extend(_iter_mapping_payloads(value, path=f"{path}[{index}]"))
        return rows
    return []


def _hidden_benchmark_authority_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    hidden_pack_kinds = {"hidden", "hidden_quarantined", "quarantined_hidden", "rotating"}
    pass_statuses = {"pass", "passed", "ok", "success"}
    for path, payload in _iter_mapping_payloads(quality_evidence):
        pack_kind = (
            str(
                payload.get("scenario_pack_kind")
                or payload.get("benchmark_pack_kind")
                or payload.get("pack_kind")
                or payload.get("kind")
                or ""
            )
            .strip()
            .casefold()
        )
        if pack_kind not in hidden_pack_kinds:
            continue
        status = (
            str(
                payload.get("quality_status")
                or payload.get("production_readiness")
                or payload.get("status")
                or ""
            )
            .strip()
            .casefold()
        )
        if status not in pass_statuses:
            continue
        return [
            _gate(
                name="hidden_benchmark_not_authority",
                stage="ops",
                code="hds_hidden_benchmark_not_authority",
                status="fail",
                layer="quality_benchmark_authority",
                phase="benchmark_authority",
                message=(
                    "Hidden or rotating benchmark pass output is quarantined and cannot "
                    "be promoted to scorecard authority."
                ),
                evidence_ref=path,
                next_action=(
                    "Run benchmark authority validation and expose only public or "
                    "runtime-owned non-hidden benchmark evidence to the scorecard."
                ),
            )
        ]
    return []


def _source_truth_adapter_reports(
    quality_evidence: dict[str, Any],
) -> tuple[list[Any], list[dict[str, Any]]]:
    surfaces = quality_evidence.get("source_truth_adapter_surfaces")
    adapter_paths = quality_evidence.get("source_truth_adapter_paths")
    if not isinstance(surfaces, dict) or not isinstance(adapter_paths, list):
        return [], []

    try:
        registry = load_adapter_contract_registry()
    except AdapterContractError as exc:
        return [], [
            {
                "code": exc.code,
                "message": str(exc),
                "next_action": "Fix source-truth lattice adapter contracts before scorecard.",
            }
        ]

    reports: list[Any] = []
    errors: list[dict[str, Any]] = []
    for adapter_path in adapter_paths:
        path_id = _clean_text(adapter_path)
        if path_id is None:
            continue
        contract = registry.adapter_paths.get(path_id)
        if contract is None:
            errors.append(
                {
                    "code": "hds_adapter_path_unknown",
                    "message": f"Unknown source-truth adapter path: {path_id}.",
                    "next_action": "Declare the adapter path in source_truth_lattice.toml.",
                }
            )
            continue
        before_envelope = surfaces.get(contract.source_surface)
        after_envelope = surfaces.get(contract.target_surface)
        if not isinstance(before_envelope, dict) or not isinstance(after_envelope, dict):
            errors.append(
                {
                    "code": "hds_adapter_surface_missing",
                    "message": (
                        "Source-truth adapter path "
                        f"{path_id} is missing {contract.source_surface} or "
                        f"{contract.target_surface} typed surface payloads."
                    ),
                    "next_action": (
                        "Persist typed source_truth_adapter_surfaces before scorecard input."
                    ),
                }
            )
            continue
        try:
            reports.append(
                validate_adapter_preservation(
                    adapter_path=path_id,
                    before=adapter_surface_payload_from_envelope(
                        before_envelope,
                        expected_surface=contract.source_surface,
                    ),
                    after=adapter_surface_payload_from_envelope(
                        after_envelope,
                        expected_surface=contract.target_surface,
                    ),
                    registry=registry,
                )
            )
        except AdapterContractError as exc:
            errors.append(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "next_action": (
                        "Fix malformed typed source-truth adapter payloads before scorecard."
                    ),
                }
            )
    return reports, errors


def _source_truth_adapter_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not _serious_canary(canary_kind):
        return [], []
    if not isinstance(
        quality_evidence.get("source_truth_adapter_surfaces"), dict
    ) or not isinstance(quality_evidence.get("source_truth_adapter_paths"), list):
        return [
            _gate(
                name="source_truth_adapter_preservation",
                stage="ops",
                code="hds_adapter_surface_missing",
                status="fail",
                layer="source_truth",
                phase="adapter_preservation_conflict",
                message=(
                    "Serious scorecard requires typed source-truth adapter surfaces "
                    "and adapter paths before authority can be projected."
                ),
                evidence_ref="quality_evidence/source_truth_conflicts.json",
                next_action=(
                    "Persist typed source_truth_adapter_surfaces and "
                    "source_truth_adapter_paths before scorecard input."
                ),
            )
        ], []
    reports, errors = _source_truth_adapter_reports(quality_evidence)
    gates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for error in errors:
        gates.append(
            _gate(
                name="source_truth_adapter_preservation",
                stage="ops",
                code=str(error["code"]),
                status="fail",
                layer="source_truth",
                phase="adapter_preservation_conflict",
                message=str(error["message"]),
                evidence_ref="quality_evidence/source_truth_conflicts.json",
                next_action=str(error["next_action"]),
            )
        )

    for report in reports:
        for blocker in report.blockers:
            conflict_record = _source_truth_conflict_from_losing_record(
                blocker.losing_authority_record,
                authoritative_source=blocker.source_surface,
                conflicting_source=blocker.target_surface,
                downstream_impact=(
                    "Scorecard input attempted to accept lower-authority adapter output."
                ),
            )
            conflicts.append(conflict_record)
            gates.append(
                _gate(
                    name="source_truth_adapter_preservation",
                    stage="ops",
                    code=blocker.code,
                    status="fail",
                    layer="source_truth",
                    phase="adapter_preservation_conflict",
                    message=(
                        "Source-truth conflict across "
                        f"{blocker.adapter_path} for {blocker.field_family}: "
                        f"{', '.join(blocker.lost_fields)}."
                    ),
                    evidence_ref="quality_evidence/source_truth_conflicts.json",
                    next_action=blocker.next_diagnostic_command,
                )
            )
    return gates, conflicts


def _source_truth_conflict_from_losing_record(
    record: Mapping[str, Any],
    *,
    authoritative_source: str,
    conflicting_source: str,
    downstream_impact: str,
    runtime_event_refs: Sequence[str] = (),
    cas_refs: Sequence[str] = (),
) -> dict[str, Any]:
    authoritative_ref = _sanitize_ref(record.get("authoritative_ref"))
    conflicting_ref = _sanitize_ref(record.get("losing_ref"))
    merged_cas_refs = list(
        dict.fromkeys(
            [
                *(str(item) for item in cas_refs if str(item or "").strip()),
                *(ref for ref in (authoritative_ref, conflicting_ref) if ref is not None),
            ]
        )
    )
    return {
        "schema_version": SOURCE_TRUTH_CONFLICT_SCHEMA,
        "authoritative_source": authoritative_source,
        "authoritative_surface": str(record.get("authoritative_surface") or authoritative_source),
        "conflicting_source": conflicting_source,
        "conflicting_surface": str(record.get("losing_surface") or conflicting_source),
        "field_family": str(record.get("field_family") or ""),
        "lost_fields": list(record.get("lost_fields") or []),
        "runtime_event_refs": [str(item) for item in runtime_event_refs if str(item or "").strip()],
        "cas_refs": merged_cas_refs,
        "authoritative_ref": authoritative_ref,
        "conflicting_ref": conflicting_ref,
        "losing_authority_record": dict(record),
        "failure_code": str(record.get("failure_code") or "hds_source_truth_conflict"),
        "owner": str(record.get("owner") or "team-runtime-quality"),
        "downstream_impact": downstream_impact,
        "next_diagnostic_command": str(
            record.get("next_diagnostic_command")
            or "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
        ),
        "recorded_at": record.get("recorded_at"),
        "details": dict(record.get("details") or {}),
    }


def _source_truth_declared_conflict_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    raw_conflicts = quality_evidence.get("source_truth_conflicts")
    if not isinstance(raw_conflicts, list):
        return []
    gates: list[dict[str, Any]] = []
    for conflict in raw_conflicts:
        if not isinstance(conflict, dict):
            continue
        field_family = _clean_text(conflict.get("field_family")) or "authority_field"
        failure_code = _clean_text(conflict.get("failure_code")) or "source_truth_conflict"
        lost_fields = conflict.get("lost_fields")
        lost_field_text = (
            ", ".join(str(field) for field in lost_fields if str(field).strip())
            if isinstance(lost_fields, list)
            else "unknown"
        )
        gates.append(
            _gate(
                name="source_truth_lattice_conflict",
                stage="ops",
                code="hds_source_truth_conflict",
                status="fail",
                layer="source_truth",
                phase="source_truth_conflict",
                message=(
                    f"Source-of-truth conflict for {field_family}: {lost_field_text}. "
                    f"Lattice code: {failure_code}."
                ),
                evidence_ref="quality_evidence/source_truth_conflicts.json",
                next_action=_clean_text(conflict.get("next_diagnostic_command"))
                or "Resolve source-of-truth conflict before scorecard closeout.",
            )
        )
    return gates


def _source_truth_reader_conflicts(
    *,
    quality_evidence: dict[str, Any],
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    execution_status: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    try:
        lattice = load_source_truth_lattice()
    except SourceTruthContractError as exc:
        return [
            {
                "schema_version": SOURCE_TRUTH_CONFLICT_SCHEMA,
                "authoritative_source": "source_truth_lattice",
                "authoritative_surface": "architecture.source_truth_lattice",
                "conflicting_source": "runtime.scorecard",
                "conflicting_surface": "runtime.scorecard",
                "field_family": "scorecard_identity_and_gates",
                "lost_fields": ["source_truth_lattice"],
                "runtime_event_refs": [],
                "cas_refs": [],
                "authoritative_ref": str(exc),
                "conflicting_ref": None,
                "losing_authority_record": {},
                "failure_code": exc.code,
                "owner": "team-architecture-governance",
                "downstream_impact": "Scorecard cannot accept authority-bearing values.",
                "next_diagnostic_command": (
                    "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
                ),
                "recorded_at": None,
                "details": {"message": str(exc)},
            }
        ]

    conflicts: list[dict[str, Any]] = []
    if job_payload is not None:
        progress = job_payload.get("progress")
        progress_state = progress.get("state") if isinstance(progress, dict) else None
        if progress_state is not None:
            conflict = detect_source_truth_conflict(
                field_family="approval_readiness_public_status",
                authoritative_source="runtime.job_state",
                authoritative_surface="runtime",
                authoritative_values={"state": job_payload.get("state") or execution_status},
                conflicting_source="runtime.progress",
                conflicting_surface="runtime.progress",
                conflicting_values={"state": progress_state},
                fields=("state",),
                downstream_impact=(
                    "approval and public export would read a non-authoritative state."
                ),
                lattice=lattice,
            )
            if conflict is not None:
                conflicts.append(conflict)

    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        report = quality_evidence.get(report_key)
        runtime_ref = authority_refs.get(ref_key)
        embedded_ref = _sanitize_ref(report.get(ref_key)) if isinstance(report, dict) else None
        if runtime_ref is None or embedded_ref is None:
            continue
        envelope = _report_authority_envelope(report) or {}
        event_ref = _sanitize_ref(envelope.get("runtime_event_ref"))
        conflict = detect_source_truth_conflict(
            field_family="runtime_refs",
            authoritative_source="runtime.cas",
            authoritative_surface="runtime.cas",
            authoritative_values={ref_key: runtime_ref, "cas_ref": runtime_ref},
            conflicting_source="runtime.canary_bundle",
            conflicting_surface="runtime.canary_bundle",
            conflicting_values={ref_key: embedded_ref, "cas_ref": embedded_ref},
            fields=(ref_key,),
            downstream_impact=(
                "Scorecard would trust a bundled report ref over the runtime CAS ref."
            ),
            runtime_event_refs=([event_ref] if event_ref else ()),
            cas_refs=(runtime_ref, embedded_ref),
            lattice=lattice,
        )
        if conflict is not None:
            conflicts.append(conflict)

    grounding = quality_evidence.get("policy_grounding_matrix")
    projection = quality_evidence.get("scorecard_projection")
    if isinstance(grounding, dict) and isinstance(projection, dict):
        fields = tuple(
            field
            for field in ("selected_variant_id", "final_policy_claims_ref")
            if _nested_get(grounding, field) is not None
            or _nested_get(projection, field) is not None
        )
        if fields:
            conflict = detect_source_truth_conflict(
                field_family="final_claims",
                authoritative_source="runtime.selected_variant",
                authoritative_surface="runtime",
                authoritative_values={field: _nested_get(grounding, field) for field in fields},
                conflicting_source="runtime.scorecard",
                conflicting_surface="runtime.scorecard",
                conflicting_values={field: _nested_get(projection, field) for field in fields},
                fields=fields,
                downstream_impact=(
                    "Scorecard would close out claims or refs from a losing variant."
                ),
                lattice=lattice,
            )
            if conflict is not None:
                conflicts.append(conflict)
    return conflicts


def _source_truth_conflict_gates_from_records(
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for conflict in conflicts:
        field_family = _clean_text(conflict.get("field_family")) or "authority_field"
        failure_code = _clean_text(conflict.get("failure_code")) or "source_truth_conflict"
        lost_fields = conflict.get("lost_fields")
        lost_field_text = (
            ", ".join(str(field) for field in lost_fields if str(field).strip())
            if isinstance(lost_fields, list)
            else "unknown"
        )
        gates.append(
            _gate(
                name="source_truth_lattice_conflict",
                stage="ops",
                code="hds_source_truth_conflict",
                status="fail",
                layer="source_truth",
                phase="source_truth_conflict",
                message=(
                    f"Source-of-truth conflict for {field_family}: {lost_field_text}. "
                    f"Lattice code: {failure_code}."
                ),
                evidence_ref="quality_evidence/source_truth_conflicts.json",
                next_action=_clean_text(conflict.get("next_diagnostic_command"))
                or "Resolve source-of-truth conflict before scorecard closeout.",
            )
        )
    return gates


def _legacy_migration_sandbox_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    report = quality_evidence.get("legacy_migration_sandbox")
    if not isinstance(report, dict):
        return []

    failure_codes = comparison_failure_codes(report)
    evidence_ref = _sanitize_ref(report.get("evidence_ref")) or (
        "quality_evidence/legacy_migration_sandbox.json"
    )
    if not failure_codes:
        return [
            _gate(
                name="legacy_migration_sandbox_passed",
                stage="ops",
                code="legacy_migration_sandbox_passed",
                status="pass",
                layer="legacy_migration_sandbox",
                phase="legacy_quarantine_migration",
                message=(
                    "Legacy-compatible diagnostics matched authority-bearing runtime evidence."
                ),
                evidence_ref=evidence_ref,
                blocking=False,
            )
        ]

    gates: list[dict[str, Any]] = []
    for code in sorted(failure_codes):
        gates.append(
            _gate(
                name="legacy_migration_sandbox_passed",
                stage="ops",
                code=code,
                status="fail",
                layer="legacy_migration_sandbox",
                phase="legacy_quarantine_migration",
                message=("Legacy migration sandbox comparison cannot satisfy serious closeout."),
                evidence_ref=evidence_ref,
                next_action=(
                    "Repair the authority-bearing runtime artifact and rerun the "
                    "dual-write migration comparison before production closeout."
                ),
            )
        )
    return gates


def _effective_mode_gates(
    *,
    canary_kind: str,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    payload = {
        "quality_evidence": quality_evidence,
        "job": job_payload or {},
        "run": run_payload or {},
    }
    candidates = _nested_find_all(payload, "effective_mode_ledger")
    if not candidates:
        return []
    gates: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        try:
            assert_serious_mode_allowed(EffectiveModeLedger.from_mapping(candidate))
        except (ModePolicyError, ValueError) as exc:
            raw_code = exc.code if isinstance(exc, ModePolicyError) else "mode_ledger_invalid"
            gates.append(
                _gate(
                    name="effective_mode_allowed",
                    stage="ops",
                    code="hds_disallowed_mode",
                    status="fail",
                    layer="runtime_mode",
                    phase="effective_mode",
                    message=f"Effective mode ledger cannot satisfy serious closeout: {raw_code}.",
                    evidence_ref=_sanitize_ref(candidate.get("mode_ledger_ref")),
                    next_action=(
                        "Run serious scorecard from production/governed/research mode "
                        "with no fixture, simulation, mock, overlay, or warn-accepted path."
                    ),
                )
            )
        else:
            gates.append(
                _gate(
                    name="effective_mode_allowed",
                    stage="ops",
                    code="effective_mode_allowed",
                    status="pass",
                    layer="runtime_mode",
                    phase="effective_mode",
                    message="Effective mode ledger permits serious closeout.",
                    evidence_ref=_sanitize_ref(candidate.get("mode_ledger_ref")),
                    next_action="Keep effective mode ledger attached to serious closeout evidence.",
                )
            )
    return gates


def _phase_barrier_records_from_payloads(
    *,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> tuple[PhaseBarrierRecord, ...]:
    candidates: list[Any] = []
    for payload in (quality_evidence, job_payload or {}, run_payload or {}):
        if not isinstance(payload, dict):
            continue
        raw = payload.get("phase_barrier_records")
        if isinstance(raw, list):
            candidates.extend(raw)
        progress = payload.get("progress")
        if isinstance(progress, dict):
            details = progress.get("details")
            if isinstance(details, dict):
                raw_details = details.get("phase_barrier_records")
                if isinstance(raw_details, list):
                    candidates.extend(raw_details)
    return tuple(PhaseBarrierRecord.model_validate(item) for item in candidates)


def _phase_barrier_gates(
    *,
    canary_kind: str,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    try:
        records = _phase_barrier_records_from_payloads(
            quality_evidence=quality_evidence,
            job_payload=job_payload,
            run_payload=run_payload,
        )
    except Exception as exc:
        return [
            _gate(
                name="serious_phase_barriers_closed",
                stage="ops",
                code="phase_barrier_record_malformed",
                status="fail",
                layer="phase_barriers",
                phase="scorecard_readiness",
                message=f"Phase barrier records are malformed: {exc}",
                evidence_ref="quality_evidence/phase_barrier_records.json",
                next_action="Persist typed PhaseBarrierRecord payloads before scorecard.",
            )
        ]

    gates: list[dict[str, Any]] = []
    for barrier_id in PhaseBarrierId.scorecard_required():
        try:
            assert_barrier_passed(barrier_id, barriers=records)
        except PhaseBarrierViolation as exc:
            gates.append(
                _gate(
                    name="serious_phase_barriers_closed",
                    stage="ops",
                    code=exc.code,
                    status="fail",
                    layer="phase_barriers",
                    phase=barrier_id.value,
                    message=str(exc),
                    evidence_ref="quality_evidence/phase_barrier_records.json",
                    next_action=(
                        "Persist a passed phase barrier record or typed blocker "
                        f"for {barrier_id.value} before scorecard."
                    ),
                )
            )
    return gates


def _serious_warning_gate(
    *,
    canary_kind: str,
    gates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not _serious_canary(canary_kind):
        return None
    warning_codes = [
        _clean_text(gate.get("code")) or str(gate["name"])
        for gate in gates
        if gate.get("status") == "warn"
    ]
    if not warning_codes:
        return None
    return _gate(
        name="serious_warn_closeout_blocked",
        stage="ops",
        code="serious_warn_scorecard_blocks_closeout",
        status="fail",
        layer="quality_scorecard",
        phase="serious_closeout",
        message="Warnings cannot satisfy serious deterministic closeout.",
        evidence_ref="quality_scorecard",
        next_action="Resolve warning gates or move the lane to explicit non-production closeout.",
    )


def _runtime_quality_ref_gate(
    *,
    ref_key: str,
    pass_message: str,
    default_next_action: str,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    report_status: str,
) -> dict[str, Any] | None:
    if report_status != "pass":
        return None
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    if authority_refs.get(ref_key):
        return None

    optional_reason = _optional_runtime_quality_ref_reason(
        ref_key=ref_key,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    serious = _serious_canary(canary_kind)
    status = "fail" if serious and optional_reason is None else "warn"
    code_suffix = "missing" if status == "fail" else "optional_missing"
    code = f"{ref_key}_{code_suffix}"
    if status == "fail":
        code = "hds_runtime_ref_missing"
    if ref_key == PRODUCTION_DATA_QUALITY_REF_KEY and status == "fail":
        code = "hds_runtime_ref_missing"
    next_action = f"Persist {ref_key} from the owning runtime layer before production approval."
    if optional_reason is not None:
        next_action = f"Persist {ref_key} when this profile requires it. {optional_reason}"
    return {
        "code": code,
        "status": status,
        "message": f"{pass_message} Runtime-owned {ref_key} is missing.",
        "next_action": next_action or default_next_action,
        "blocking": status == "fail",
    }


def _report_schema_compatibility_gate(
    *,
    report_key: str,
    report: Any,
    canary_kind: str,
) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    expected_schema_family = SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES.get(report_key)
    compatibility = evaluate_schema_compatibility(
        report,
        reader="scorecard",
        expected_schema_family=expected_schema_family,
    )
    if compatibility.decision in COMPATIBLE_DECISIONS:
        return None

    serious = _serious_canary(canary_kind)
    status = "fail" if serious or compatibility.decision != "legacy_quarantined" else "warn"
    expected = (
        ", ".join(compatibility.expected_schema_families)
        if compatibility.expected_schema_families
        else "a declared scorecard-readable schema"
    )
    return {
        "code": "hds_schema_incompatible",
        "status": status,
        "message": (
            "Quality report schema is not production-closeout compatible. "
            f"Decision: {compatibility.decision}; reason: {compatibility.reason}."
        ),
        "next_action": (
            f"Emit {report_key} with {expected}, or route legacy evidence through "
            "diagnostic-only quarantine instead of the serious scorecard gate."
        ),
        "blocking": status == "fail",
    }


def _report_status_authority_gate(
    *,
    report: Any,
    canary_kind: str,
) -> dict[str, Any] | None:
    if not _serious_canary(canary_kind) or not isinstance(report, dict):
        return None
    raw_status = str(report.get("status") or report.get("quality_status") or "").casefold()
    if raw_status not in {"present", "completed"}:
        return None
    return {
        "code": "hds_unknown_provenance",
        "status": "fail",
        "message": (
            "Pass-shaped report status is not runtime authority. Serious scorecards "
            "require explicit pass evidence with a runtime authority envelope."
        ),
        "next_action": (
            "Emit a runtime-owned pass/blocker report and authority envelope instead "
            f"of status={raw_status!r}."
        ),
        "blocking": True,
    }


def _published_decision_lifecycle_in_scope(
    quality_evidence: dict[str, Any],
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> bool:
    scope = quality_evidence.get("published_decision_lifecycle")
    if isinstance(scope, dict) and bool(scope.get("in_scope")):
        return True
    if bool(quality_evidence.get("published_decision_lifecycle_in_scope")):
        return True
    if any(key in quality_evidence for key in CONTINUOUS_GOVERNANCE_LIFECYCLE_REPORT_KEYS):
        return True
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    return bool(_nested_get(payload, "published_decision_lifecycle_in_scope"))


def _lifecycle_report_contract_gate(
    *,
    report_key: str,
    report: Any,
    canary_kind: str,
) -> dict[str, Any] | None:
    if report_key not in CONTINUOUS_GOVERNANCE_LIFECYCLE_REPORT_KEYS:
        return None
    if not _serious_canary(canary_kind) or not isinstance(report, dict):
        return None

    missing: list[str] = []
    if not isinstance(report.get("diagnostic_event"), dict) and not _sanitize_ref(
        report.get("diagnostic_event_ref")
    ):
        missing.append("diagnostic_event")
    if not isinstance(report.get("authority_envelope"), dict):
        missing.append("authority_envelope")
    schema_record = report.get("schema_compatibility")
    if (
        not isinstance(schema_record, dict)
        or str(schema_record.get("decision") or "").casefold() not in COMPATIBLE_DECISIONS
    ):
        missing.append("schema_compatibility")
    if not _sanitize_ref(report.get("effective_mode_ref")):
        missing.append("effective_mode_ref")
    if not (
        _sanitize_ref(report.get("fallback_degradation_ref"))
        or _sanitize_ref(report.get("degradation_ledger_ref"))
    ):
        missing.append("fallback_degradation_ref")
    cas_artifacts = report.get("cas_artifact_refs")
    if not isinstance(cas_artifacts, dict) or not any(
        _sanitize_ref(value) for value in cas_artifacts.values()
    ):
        missing.append("cas_artifact_refs")

    if not missing:
        return None
    return {
        "code": "continuous_governance_lifecycle_evidence_missing",
        "status": "fail",
        "message": (
            "Continuous governance lifecycle evidence is missing runtime-owned "
            f"authority records: {', '.join(missing)}."
        ),
        "next_action": (
            "Emit diagnostic event, CAS artifact refs, authority envelope, schema "
            "compatibility, effective mode, and fallback/degradation refs from the "
            "continuous governance runtime lifecycle emitter."
        ),
        "blocking": True,
    }


def _report_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    report_gate_specs = {
        "production_data_quality": (
            "production_data_quality_present",
            "materialization",
            "fabric_materialization",
            "Production data quality diagnostics are present.",
            "Persist production_data_quality_report_ref from real materialized production data.",
        ),
        "normative_evidence": (
            "normative_evidence_present",
            "lex",
            "lex",
            "Normative applicability evidence is present.",
            "Generate normative applicability evidence before policy approval.",
        ),
        "fabric_retrieval_trace": (
            "fabric_retrieval_trace_present",
            "fabric",
            "fabric_retrieval",
            "Fabric source-selection evidence is present.",
            "Record selected/rejected Fabric sources and relevance diagnostics.",
        ),
        "foundry_method_report": (
            "foundry_method_evidence_present",
            "foundry",
            "foundry_methods",
            "Foundry method validity evidence is present.",
            "Persist method assumptions, uncertainty, and diagnostics.",
        ),
        "policy_grounding_matrix": (
            "policy_grounding_matrix_present",
            "policy_output",
            "scientist_policy_artifacts",
            "Policy grounding matrix is present.",
            "Map final policy claims to data, method, and normative refs.",
        ),
        "conflict_check": (
            "conflict_check_present",
            "lex",
            "normative_conflict",
            "Policy conflict check is present.",
            "Run corpus compatibility and policy conflict checks.",
        ),
        "causal_statistical_validity": (
            "causal_statistical_validity_present",
            "foundry",
            "foundry_causal_validity",
            "Causal/statistical validity benchmark evidence is present.",
            "Persist causal_statistical_validity_report_ref from deterministic benchmarks.",
        ),
        "replay_manifest": (
            "replay_manifest_present",
            "ops",
            "runtime_replay",
            "Deterministic replay manifest is present.",
            "Persist replay_manifest_ref from sanitized request, dependency, data, and CAS refs.",
        ),
        "drift_explanation": (
            "drift_explanation_present",
            "ops",
            "runtime_replay",
            "Replay drift explanation evidence is present.",
            "Persist drift_explanation_ref and classify replay differences by typed drift source.",
        ),
        "resilience_matrix": (
            "resilience_matrix_present",
            "ops",
            "runtime_resilience",
            "Load, soak, and resilience matrix evidence is present.",
            (
                "Persist resilience_report_ref from deterministic overload, retry, CAS, "
                "and dashboard lanes."
            ),
        ),
        "human_review_calibration": (
            "human_review_calibration_present",
            "ops",
            "human_review_calibration",
            "Human-review calibration evidence is present.",
            (
                "Persist human_review_calibration_report_ref from approval, override, "
                "escalation, and withdrawal review flows."
            ),
        ),
        "decision_artifact_quality": (
            "decision_artifact_quality_present",
            "policy_output",
            "scientist_decision_artifact",
            "Decision-artifact quality evidence is present.",
            (
                "Persist decision_artifact_quality_report_ref for the compiled public "
                "decision artifact."
            ),
        ),
    }
    if _published_decision_lifecycle_in_scope(
        quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    ):
        report_gate_specs.update(
            {
                "continuous_governance_stale": (
                    "continuous_governance_stale_report_present",
                    "scientist",
                    "scientist_governance_lifecycle",
                    "Continuous governance stale lifecycle evidence is present.",
                    (
                        "Persist continuous_governance_stale_report_ref from the "
                        "runtime lifecycle emitter."
                    ),
                ),
                "continuous_governance_reissue": (
                    "continuous_governance_reissue_report_present",
                    "scientist",
                    "scientist_governance_lifecycle",
                    "Continuous governance reissue lifecycle evidence is present.",
                    (
                        "Persist continuous_governance_reissue_report_ref from the "
                        "runtime lifecycle emitter."
                    ),
                ),
                "continuous_governance_supersede": (
                    "continuous_governance_supersede_report_present",
                    "scientist",
                    "scientist_governance_lifecycle",
                    "Continuous governance supersede lifecycle evidence is present.",
                    (
                        "Persist continuous_governance_supersede_report_ref from the "
                        "runtime lifecycle emitter."
                    ),
                ),
                "continuous_governance_withdraw": (
                    "continuous_governance_withdraw_report_present",
                    "scientist",
                    "scientist_governance_lifecycle",
                    "Continuous governance withdraw lifecycle evidence is present.",
                    (
                        "Persist continuous_governance_withdraw_report_ref from the "
                        "runtime lifecycle emitter."
                    ),
                ),
            }
        )
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    gates: list[dict[str, Any]] = []
    for report_key, (
        gate_name,
        stage,
        layer,
        pass_message,
        next_action,
    ) in report_gate_specs.items():
        report = quality_evidence.get(report_key)
        report_status = _quality_report_status(report)
        issue_codes = _quality_report_issue_codes(report)
        first_issue = _first_quality_issue(report)
        issue_code = str(first_issue.get("code") or "").strip() if first_issue else ""
        issue_phase = str(first_issue.get("phase") or "").strip() if first_issue else ""
        issue_next_action = str(first_issue.get("next_action") or "").strip() if first_issue else ""
        evidence_ref = (
            f"quality_evidence/{QUALITY_REPORT_FILES[report_key]}"
            if isinstance(report, dict)
            else None
        )
        gate_code = (
            "production_data_quality_missing"
            if report_status == "missing" and report_key == "production_data_quality"
            else issue_code or gate_name
        )
        gate_status = report_status if report_status != "missing" else "fail"
        gate_message = (
            pass_message
            if report_status == "pass"
            else (
                f"{pass_message} Status: {report_status}."
                + (f" Issues: {', '.join(issue_codes[:5])}." if issue_codes else "")
            )
        )
        gate_next_action = None if report_status == "pass" else issue_next_action or next_action
        gate_blocking = True
        if report_key == "production_data_quality" and not _serious_canary(canary_kind):
            if gate_status == "fail":
                gate_status = "warn"
                gate_blocking = False
        if report_key in CONTINUOUS_GOVERNANCE_LIFECYCLE_REPORT_KEYS and report_status == "missing":
            ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
            gate_code = (
                "hds_runtime_ref_missing" if _serious_canary(canary_kind) else f"{ref_key}_missing"
            )
            gate_message = f"{pass_message} Runtime-owned {ref_key} is missing."
            gate_next_action = (
                f"Persist {ref_key} from the owning runtime layer before production approval."
            )
        runtime_ref_gate = _runtime_quality_ref_gate(
            ref_key=QUALITY_REPORT_RUNTIME_REFS[report_key],
            pass_message=pass_message,
            default_next_action=next_action,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
            report_status=report_status,
        )
        if runtime_ref_gate is not None:
            gate_code = str(runtime_ref_gate["code"])
            gate_status = str(runtime_ref_gate["status"])
            gate_message = str(runtime_ref_gate["message"])
            gate_next_action = str(runtime_ref_gate["next_action"])
            gate_blocking = bool(runtime_ref_gate["blocking"])
        schema_compatibility_gate = _report_schema_compatibility_gate(
            report_key=report_key,
            report=report,
            canary_kind=canary_kind,
        )
        if schema_compatibility_gate is not None:
            gate_code = str(schema_compatibility_gate["code"])
            gate_status = str(schema_compatibility_gate["status"])
            gate_message = str(schema_compatibility_gate["message"])
            gate_next_action = str(schema_compatibility_gate["next_action"])
            gate_blocking = bool(schema_compatibility_gate["blocking"])
        status_authority_gate = None
        if schema_compatibility_gate is None:
            status_authority_gate = _report_status_authority_gate(
                report=report,
                canary_kind=canary_kind,
            )
        if status_authority_gate is not None:
            gate_code = str(status_authority_gate["code"])
            gate_status = str(status_authority_gate["status"])
            gate_message = str(status_authority_gate["message"])
            gate_next_action = str(status_authority_gate["next_action"])
            gate_blocking = bool(status_authority_gate["blocking"])
        lifecycle_contract_gate = None
        if (
            runtime_ref_gate is None
            and schema_compatibility_gate is None
            and status_authority_gate is None
        ):
            lifecycle_contract_gate = _lifecycle_report_contract_gate(
                report_key=report_key,
                report=report,
                canary_kind=canary_kind,
            )
        if lifecycle_contract_gate is not None:
            gate_code = str(lifecycle_contract_gate["code"])
            gate_status = str(lifecycle_contract_gate["status"])
            gate_message = str(lifecycle_contract_gate["message"])
            gate_next_action = str(lifecycle_contract_gate["next_action"])
            gate_blocking = bool(lifecycle_contract_gate["blocking"])
        gates.append(
            _gate(
                name=gate_name,
                stage=stage,
                code=gate_code,
                status=gate_status,
                layer=layer,
                phase=issue_phase or "quality_evidence",
                message=gate_message,
                evidence_ref=evidence_ref,
                next_action=gate_next_action,
                blocking=gate_blocking,
                owner=_SPOOF_OWNER_BY_LAYER.get(layer, "team-runtime-quality"),
                first_failing_artifact_ref=(
                    authority_refs.get(QUALITY_REPORT_RUNTIME_REFS[report_key]) or evidence_ref
                ),
                domain_failure_code=(
                    gate_code
                    if gate_status == "fail" and not str(gate_code).startswith("hds_")
                    else None
                ),
            )
        )
    return gates


def _compliance_gates(
    quality_evidence: dict[str, Any],
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    report = quality_evidence.get(PRIVACY_COMPLIANCE_REPORT_KEY)
    if not isinstance(report, dict):
        if not _serious_canary(canary_kind):
            return []
        return [
            _gate(
                name="privacy_compliance_report_present",
                stage="ops",
                code="privacy_compliance_report_missing",
                status="fail",
                layer="privacy_compliance",
                phase="privacy_compliance",
                message=("Privacy, licensing, and public-export compliance evidence is missing."),
                evidence_ref=None,
                next_action=(
                    "Persist privacy_compliance_report_ref for production data inputs "
                    "and public artifact families before production approval."
                ),
            )
        ]

    gate_details = privacy_compliance_gate_details(report)
    if gate_details is None:
        return []
    report_status = str(gate_details["status"])
    gate_code = str(gate_details["code"])
    gate_status = report_status
    gate_message = str(gate_details["message"])
    gate_next_action = (
        str(gate_details["next_action"]) if gate_details.get("next_action") is not None else None
    )
    gate_blocking = bool(gate_details["blocking"])
    runtime_ref_gate = _runtime_quality_ref_gate(
        ref_key=PRIVACY_COMPLIANCE_REPORT_REF_KEY,
        pass_message="Privacy, licensing, and compliance evidence is present.",
        default_next_action=(
            "Persist privacy_compliance_report_ref from compliance evidence assembly."
        ),
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        report_status=report_status,
    )
    if runtime_ref_gate is not None:
        gate_code = str(runtime_ref_gate["code"])
        gate_status = str(runtime_ref_gate["status"])
        gate_message = str(runtime_ref_gate["message"])
        gate_next_action = str(runtime_ref_gate["next_action"])
        gate_blocking = bool(runtime_ref_gate["blocking"])
    return [
        _gate(
            name="privacy_compliance_report_present",
            stage="ops",
            code=gate_code,
            status=gate_status,
            layer="privacy_compliance",
            phase=str(gate_details["phase"]),
            message=gate_message,
            evidence_ref=str(gate_details["evidence_ref"]),
            next_action=gate_next_action,
            blocking=gate_blocking,
        )
    ]


def _attestation_candidates(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[Any]:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    candidates: list[Any] = []
    for key in ("trust_boundary_attestations", "attestation_records", "attestations"):
        for value in _nested_find_all(payload, key):
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)
    return candidates


def _attestation_gates(
    *,
    canary_kind: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not _serious_canary(canary_kind):
        return []
    try:
        registry = load_trust_boundary_registry()
        required_boundaries = iter_required_production_attestation_boundaries(registry)
    except Exception as exc:
        return [
            _gate(
                name="trust_boundary_registry_loaded",
                stage="ops",
                code="trust_boundary_registry_invalid",
                status="fail",
                layer="attestation",
                phase="trust_boundary_registry",
                message=f"Trust-boundary registry could not be loaded: {exc}",
                evidence_ref=None,
                next_action=(
                    "Fix architecture/production_quality/trust_boundaries.toml before "
                    "production closeout."
                ),
            )
        ]

    attestations = _attestation_candidates(job_payload=job_payload, run_payload=run_payload)
    gates: list[dict[str, Any]] = []
    for boundary in required_boundaries:
        try:
            result = evaluate_trust_boundary_attestation(
                boundary_id=boundary.boundary_id,
                attestations=attestations,
                registry=registry,
            )
        except Exception as exc:
            gates.append(
                _gate(
                    name=boundary.scorecard_gate_name,
                    stage=boundary.scorecard_stage,
                    code="attestation_invalid",
                    status="fail",
                    layer="attestation",
                    phase=boundary.boundary_id,
                    message=f"Trust-boundary attestation is invalid: {exc}",
                    evidence_ref=None,
                    next_action=boundary.next_action,
                )
            )
            continue

        gates.append(
            _gate(
                name=boundary.scorecard_gate_name,
                stage=boundary.scorecard_stage,
                code=result.failure_code,
                status="pass" if result.production_closeout_satisfied else "fail",
                layer="attestation",
                phase=boundary.boundary_id,
                message=result.message,
                evidence_ref=result.attestation_ref,
                next_action=result.next_action,
                blocking=not result.production_closeout_satisfied,
            )
        )
    return gates


def _scorecard_degradation_gate(gate: dict[str, Any] | None) -> dict[str, Any] | None:
    if gate is None:
        return None
    normalized = dict(gate)
    raw_code = _clean_text(normalized.get("code")) or "degradation_policy_blocked"
    normalized["code"] = "hds_unallowed_fallback"
    normalized["message"] = (
        str(normalized.get("message") or "Fallback/degradation policy blocked closeout.")
        + f" Fallback code: {raw_code}."
    )
    return normalized


def _stage_scores(gates: list[dict[str, Any]]) -> dict[str, float]:
    points = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    scores: dict[str, float] = {}
    for stage in STAGES:
        stage_gates = [gate for gate in gates if gate.get("stage") == stage]
        if not stage_gates:
            scores[stage] = 1.0
            continue
        scores[stage] = round(
            sum(points.get(str(gate.get("status")), 0.0) for gate in stage_gates)
            / len(stage_gates),
            6,
        )
    return scores


def _evidence_refs(
    *,
    provider_preflight: dict[str, Any] | None,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    if provider_preflight is not None:
        refs["provider_preflight"] = "provider_preflight.json"
    if _nested_get({"job": job_payload or {}, "run": run_payload or {}}, "run_performance_summary"):
        refs["performance_summary"] = "performance.json"
    if _materialization_refs_present(job_payload=job_payload, run_payload=run_payload)[0]:
        refs["materialization"] = "artifacts.json"
    authority_refs = _runtime_authority_refs(
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    for ref_key in QUALITY_REPORT_RUNTIME_REFS.values():
        ref_value = authority_refs.get(ref_key)
        if ref_value is not None:
            refs[ref_key] = ref_value
    provider_quality_ref = authority_refs.get("provider_model_quality_ledger_ref")
    if provider_quality_ref is not None:
        refs["provider_model_quality_ledger_ref"] = provider_quality_ref
    prompt_tool_ledger_ref = authority_refs.get(PROMPT_TOOL_LEDGER_REF_KEY)
    if prompt_tool_ledger_ref is not None:
        refs[PROMPT_TOOL_LEDGER_REF_KEY] = prompt_tool_ledger_ref
    security_ref = authority_refs.get(SECURITY_ASSURANCE_REPORT_REF_KEY)
    if security_ref is not None:
        refs[SECURITY_ASSURANCE_REPORT_REF_KEY] = security_ref
    for key, filename in QUALITY_REPORT_FILES.items():
        if key in quality_evidence:
            refs[key] = f"quality_evidence/{filename}"
    if (
        "security_assurance_report" in quality_evidence
        and SECURITY_ASSURANCE_REPORT_REF_KEY not in refs
    ):
        refs[SECURITY_ASSURANCE_REPORT_REF_KEY] = f"quality_evidence/{SECURITY_REPORT_FILE}"
    if (
        PRIVACY_COMPLIANCE_REPORT_KEY in quality_evidence
        and PRIVACY_COMPLIANCE_REPORT_REF_KEY not in refs
    ):
        refs[PRIVACY_COMPLIANCE_REPORT_REF_KEY] = PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF
    return refs


def _performance_payload(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    for key in ("canary_performance_budget", "run_performance_summary"):
        value = _nested_get(payload, key)
        if isinstance(value, dict):
            return value
    return None


def _performance_status(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> str:
    performance = _performance_payload(job_payload=job_payload, run_payload=run_payload)
    if performance is None:
        return "missing"

    budget_summary = performance.get("budget_summary")
    if isinstance(budget_summary, dict):
        try:
            over_budget_count = int(budget_summary.get("over_budget_count") or 0)
        except (TypeError, ValueError):
            over_budget_count = 0
        if over_budget_count > 0:
            return "fail"

    saw_warning = False
    phase_budgets = performance.get("phase_budgets")
    if isinstance(phase_budgets, list):
        for raw_row in phase_budgets:
            if not isinstance(raw_row, dict):
                continue
            status = str(raw_row.get("status") or "").strip().lower()
            if status in PERFORMANCE_FAIL_STATUSES:
                return "fail"
            if status in PERFORMANCE_WARN_STATUSES:
                saw_warning = True

    explicit_status = str(performance.get("status") or "").strip().lower()
    if explicit_status in PERFORMANCE_FAIL_STATUSES:
        return "fail"
    if explicit_status in PERFORMANCE_WARN_STATUSES or saw_warning:
        return "warn"
    return "pass"


def _override_candidate(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = {"job": job_payload or {}, "run": run_payload or {}}
    for key in (
        "quality_override",
        "approval_override",
        "governance_override",
        "override_evidence",
        "human_review",
    ):
        value = _nested_get(payload, key)
        if isinstance(value, dict):
            return value

    status = _nested_get(payload, "human_review_status") or _nested_get(
        payload,
        "review_status",
    )
    decision_ref = _nested_get(payload, "human_review_decision_ref") or _nested_get(
        payload,
        "reviewer_decision_ref",
    )
    packet_ref = _nested_get(payload, "human_review_packet_ref") or _nested_get(
        payload,
        "review_packet_ref",
    )
    if status is not None or decision_ref is not None or packet_ref is not None:
        return {
            "status": status,
            "decision_ref": decision_ref,
            "packet_ref": packet_ref,
        }
    return None


def _override_evidence(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = _override_candidate(job_payload=job_payload, run_payload=run_payload)
    if candidate is None:
        return {"status": "missing", "accepted": False}

    raw_status = (
        str(
            candidate.get("status")
            or candidate.get("review_status")
            or candidate.get("human_review_status")
            or ""
        )
        .strip()
        .lower()
    )
    raw_action = str(candidate.get("action") or "").strip().lower()
    decision_ref = _sanitize_ref(
        candidate.get("decision_ref")
        or candidate.get("human_review_decision_ref")
        or candidate.get("reviewer_decision_ref")
    )
    packet_ref = _sanitize_ref(
        candidate.get("packet_ref")
        or candidate.get("human_review_packet_ref")
        or candidate.get("review_packet_ref")
    )
    has_signature = any(
        bool(candidate.get(key))
        for key in ("signed", "signature", "signature_ref", "reviewer_signatures")
    )
    accepted = raw_status in OVERRIDE_ACCEPTED_STATUSES
    accepted = accepted or raw_action in OVERRIDE_ACCEPTED_ACTIONS
    rejected = raw_status in OVERRIDE_REJECTED_STATUSES
    rejected = rejected or raw_action in OVERRIDE_REJECTED_ACTIONS

    if accepted and (decision_ref is not None or has_signature):
        evidence = {"status": "accepted", "accepted": True}
    elif accepted:
        evidence = {"status": "invalid", "accepted": False}
    elif rejected:
        evidence = {"status": "rejected", "accepted": False}
    elif raw_status in OVERRIDE_PENDING_STATUSES:
        evidence = {"status": "pending", "accepted": False}
    else:
        evidence = {"status": "invalid", "accepted": False}

    if decision_ref is not None:
        evidence["decision_ref"] = decision_ref
    if packet_ref is not None:
        evidence["packet_ref"] = packet_ref
    return evidence


def _warning_summaries(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "gate": str(gate["name"]),
            "code": _clean_text(gate.get("code")) or str(gate["name"]),
            "layer": _clean_text(gate.get("layer")) or "quality_scorecard",
            "phase": _clean_text(gate.get("phase")),
            "message": _clean_text(gate.get("message")) or "Quality warning.",
            "evidence_ref": _sanitize_ref(gate.get("evidence_ref")),
            "next_action": _clean_text(gate.get("next_action")),
        }
        for gate in gates
        if gate.get("status") == "warn"
    ]


def _performance_reason(performance_status: str) -> str | None:
    if performance_status == "fail":
        return "performance_budget_failed"
    if performance_status == "warn":
        return "performance_budget_warn"
    if performance_status == "missing":
        return "performance_evidence_missing"
    return None


def _approval_readiness(
    *,
    canary_kind: str,
    execution_status: str,
    quality_status: str,
    performance_status: str,
    blocking_quality_failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    override_evidence: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    serious = _serious_canary(canary_kind)
    override_accepted = bool(override_evidence.get("accepted"))
    reasons: list[str] = []
    requires_override = False

    if execution_status != "completed":
        approval_state = "execution_failed"
        reasons = ["execution_not_completed"]
    elif blocking_quality_failures:
        requires_override = True
        reasons = [
            str(failure.get("code") or failure.get("gate")) for failure in blocking_quality_failures
        ]
        approval_state = "approval_ready" if override_accepted else "quality_failed"
    elif quality_status == "warn":
        requires_override = serious
        reasons = [str(warning.get("code") or warning["gate"]) for warning in warnings]
        if serious and override_accepted:
            approval_state = "approval_ready"
        else:
            approval_state = "quality_warn"
    elif serious and performance_status in {"fail", "warn", "missing"}:
        requires_override = True
        reason = _performance_reason(performance_status)
        reasons = [reason] if reason is not None else []
        approval_state = "approval_ready" if override_accepted else "override_required"
    else:
        approval_state = "approval_ready"

    eligibility = {
        "state": approval_state,
        "eligible": approval_state == "approval_ready",
        "requires_override": requires_override,
        "override_accepted": override_accepted,
        "missing_override": requires_override and not override_accepted,
        "execution_status": execution_status,
        "quality_status": quality_status,
        "performance_status": performance_status,
        "blocking_gate_count": len(blocking_quality_failures),
        "warning_count": len(warnings),
        "reasons": sorted(set(reasons)),
    }
    return approval_state, eligibility


def scorecard_control_progress(scorecard: dict[str, Any]) -> dict[str, Any]:
    """Project a scorecard into the durable control progress summary shape."""
    summary = {
        key: deepcopy(scorecard[key]) for key in SCORECARD_CONTROL_PROGRESS_KEYS if key in scorecard
    }
    evidence_refs = summary.get("evidence_refs")
    if isinstance(evidence_refs, dict) and "quality_scorecard_ref" not in summary:
        scorecard_ref = _sanitize_ref(evidence_refs.get("quality_scorecard"))
        if scorecard_ref is not None:
            summary["quality_scorecard_ref"] = scorecard_ref
    return summary


def build_quality_scorecard(
    *,
    canary_kind: str,
    job_id: str | None,
    run_id: Any,
    execution_status: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    provider_preflight: dict[str, Any] | None,
    quality_evidence: dict[str, Any],
    quality_scorecard_ref: str | None = None,
    quality_evidence_bundle_path: str | None = None,
) -> dict[str, Any]:
    """Build a production-quality scorecard from runtime and domain evidence."""
    source_truth_gates, source_truth_conflicts = _source_truth_adapter_gates(
        quality_evidence,
        canary_kind=canary_kind,
    )
    reader_source_truth_conflicts = _source_truth_reader_conflicts(
        quality_evidence=quality_evidence,
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        execution_status=execution_status,
    )
    source_truth_conflicts = [
        *source_truth_conflicts,
        *reader_source_truth_conflicts,
    ]
    provider_model_quality_gate = _provider_model_quality_gate(
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    prompt_tool_parser_authority_gate = _prompt_tool_parser_authority_gate(
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    degradation_gate = degradation_gate_from_payloads(
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    degradation_gate = _scorecard_degradation_gate(degradation_gate)
    skip_blocker_gate = skip_blocker_gate_from_payloads(
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        quality_evidence=quality_evidence,
    )
    gates: list[dict[str, Any]] = [
        _execution_gate(execution_status=execution_status, job_payload=job_payload),
        *_llm_gates(
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
            provider_preflight=provider_preflight,
        ),
        *([provider_model_quality_gate] if provider_model_quality_gate is not None else []),
        *(
            [prompt_tool_parser_authority_gate]
            if prompt_tool_parser_authority_gate is not None
            else []
        ),
        _materialization_gate(job_payload=job_payload, run_payload=run_payload),
        _scientist_gate(
            execution_status=execution_status,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *([skip_blocker_gate] if skip_blocker_gate is not None else []),
        *_authority_contract_gates(
            quality_evidence,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
            quality_evidence_bundle_path=quality_evidence_bundle_path,
        ),
        *_report_gates(
            quality_evidence,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *data_forge_snapshot_binding_scorecard_gates(
            quality_evidence.get(DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY),
            canary_kind=canary_kind,
            serious=_serious_canary(canary_kind),
        ),
        *security_gates_from_report(quality_evidence.get("security_assurance_report")),
        *_compliance_gates(
            quality_evidence,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_diagnostic_event_gates(
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_phase_barrier_gates(
            canary_kind=canary_kind,
            quality_evidence=quality_evidence,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_effective_mode_gates(
            canary_kind=canary_kind,
            quality_evidence=quality_evidence,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_lex_no_norm_authority_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_semantic_binding_gates(
            quality_evidence,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_scholar_academic_evidence_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_diagnostic_slo_readiness_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_assurance_case_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_case_profile_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_concept_spine_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_jurisdiction_spine_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave12_producer_evidence_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave14_producer_scorecard_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave15_evidence_portfolio_design_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave16_evidence_line_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave17_independence_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave18_multiverse_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave18_disconfirming_evidence_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave19_synthesis_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave20_portfolio_readiness_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave21_claim_compiler_runtime_contract_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave22_claim_argument_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave25_research_deficit_promotion_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave27_governance_legitimacy_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_options_objectives_tradeoffs_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave27_lifecycle_ddm_expost_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave27_external_audit_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *(
            policy_design_case_substrate_residual_verification_scorecard_gates(
                quality_evidence["policy_design_case"]
            )
            if _serious_canary(canary_kind)
            and isinstance(quality_evidence.get("policy_design_case"), Mapping)
            else []
        ),
        *_policy_design_wave29_self_fmea_and_partial_state_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *(
            policy_design_case_maturity_scorecard_gates(quality_evidence["policy_design_case"])
            if _serious_canary(canary_kind)
            and isinstance(quality_evidence.get("policy_design_case"), Mapping)
            else []
        ),
        *_policy_design_wave28_3_observability_static_audit_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave28_config_release_hardening_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave28_5_external_client_surface_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave29_1_evidence_graph_threat_model_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_policy_design_wave30_run_cost_proportionality_gates(
            quality_evidence,
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_policy_design_wave31_best_in_class_benchmarking_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *(
            policy_design_pass1b_hardening_scorecard_gates(quality_evidence["policy_design_case"])
            if _serious_canary(canary_kind)
            and isinstance(quality_evidence.get("policy_design_case"), Mapping)
            else []
        ),
        *_policy_design_case_runtime_identity_gates(
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_policy_design_parallel_authority_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *(
            policy_design_case_record_registry_scorecard_gates()
            if _serious_canary(canary_kind)
            else []
        ),
        *_projection_quality_status_gates(
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *_hidden_benchmark_authority_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_source_truth_declared_conflict_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_source_truth_conflict_gates_from_records(reader_source_truth_conflicts),
        *source_truth_gates,
        *_legacy_migration_sandbox_gates(
            quality_evidence,
            canary_kind=canary_kind,
        ),
        *_attestation_gates(
            canary_kind=canary_kind,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        *([degradation_gate] if degradation_gate is not None else []),
    ]
    serious_warning_gate = _serious_warning_gate(canary_kind=canary_kind, gates=gates)
    if serious_warning_gate is not None:
        gates.append(serious_warning_gate)
    blocking_quality_failures = [
        _blocking_failure_from_gate(gate)
        for gate in gates
        if gate["blocking"] and gate["status"] == "fail"
    ]
    operator_triage_ledger = _operator_triage_ledger(blocking_quality_failures)
    if blocking_quality_failures:
        quality_status = "fail"
    elif any(gate["status"] == "warn" for gate in gates):
        quality_status = "warn"
    else:
        quality_status = "pass"

    performance_status = _performance_status(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    warnings = _warning_summaries(gates)
    override_evidence = _override_evidence(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    approval_state, approval_eligibility = _approval_readiness(
        canary_kind=canary_kind,
        execution_status=execution_status,
        quality_status=quality_status,
        performance_status=performance_status,
        blocking_quality_failures=blocking_quality_failures,
        warnings=warnings,
        override_evidence=override_evidence,
    )
    if operator_triage_ledger["root_causes"]:
        approval_eligibility["operator_triage_ledger"] = operator_triage_ledger
    stage_scores = _stage_scores(gates)
    overall_score = round(sum(stage_scores.values()) / len(stage_scores), 6)
    refs = _evidence_refs(
        provider_preflight=provider_preflight,
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    if quality_scorecard_ref:
        refs["quality_scorecard"] = quality_scorecard_ref
    if source_truth_conflicts:
        refs["source_truth_conflicts"] = "quality_evidence/source_truth_conflicts.json"
    payload: dict[str, Any] = {
        "schema_version": "policyos.quality_scorecard.v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "canary_kind": canary_kind,
        "job_id": job_id,
        "run_id": run_id,
        "execution_status": execution_status,
        "quality_status": quality_status,
        "performance_status": performance_status,
        "approval_state": approval_state,
        "overall_score": overall_score,
        "stage_scores": stage_scores,
        "quality_gates": gates,
        "blocking_quality_failures": blocking_quality_failures,
        "operator_triage_ledger": operator_triage_ledger,
        "warnings": warnings,
        "override_evidence": override_evidence,
        "approval_eligibility": approval_eligibility,
        "evidence_refs": refs,
    }
    if quality_scorecard_ref:
        payload["quality_scorecard_ref"] = quality_scorecard_ref
    if quality_evidence_bundle_path:
        payload["quality_evidence_bundle_path"] = quality_evidence_bundle_path
    if source_truth_conflicts:
        payload["source_truth_conflicts"] = source_truth_conflicts
    return payload


__all__ = [
    "APPROVAL_STATES",
    "CONTINUOUS_GOVERNANCE_LIFECYCLE_REPORT_KEYS",
    "POLICY_DESIGN_CASE_RUNTIME_REF_KEYS",
    "QUALITY_REPORT_FILES",
    "QUALITY_REPORT_RUNTIME_REFS",
    "REQUIRED_MATERIALIZATION_REFS",
    "SCORECARD_CONTROL_PROGRESS_KEYS",
    "build_quality_scorecard",
    "normalize_quality_evidence",
    "policy_design_case_claim_closeout_gates",
    "scorecard_control_progress",
]
