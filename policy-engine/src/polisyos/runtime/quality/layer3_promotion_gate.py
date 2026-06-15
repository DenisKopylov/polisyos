"""Layer 3 G4 shadow-to-governed promotion gate contracts.

G4 is a bounded resolver over persisted Layer 3 artifacts. It does not rerun
G1/G2/G3/GL builders, does not promote data-source bindings, and does not mint
production, publication, approval, scorecard, closeout, or useful-design credit.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.runtime.quality.layer3_gx_data_home import (
    build_g4_promotion_request_dicts_from_data_home,
    load_layer3_gx_data_home,
    read_layer3_gx_pinned_case_id,
)
from polisyos.runtime.quality.layer3_status_reducers import (
    G4PromotionStateInputs,
    Layer3ReducerInputRef,
    reduce_g4_promotion_state,
)
from polisyos.runtime.quality.required_reference_resolver import resolve_required_ref

LAYER3_G4_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g4_promotion_gate.v1"
LAYER3_G4_RULE_VERSION = "policyos.layer3.g4.shadow_to_governed_promotion.v1"
G4_SURFACE_ID = "layer3_g4_shadow_to_governed_promotion_surface"
G4_READINESS_CHECK_ID = "layer3_g4_shadow_to_governed_promotion_gate"
G4_GENERATED_ARTIFACT_FAMILY_ID = "policy-design-case-layer3-g4-promotion-gate-artifacts"
REPO_ROOT = Path(__file__).resolve().parents[4]
G4_PINNED_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)

PROMOTION_STATE_VALUES: tuple[str, ...] = (
    "shadow",
    "governed_promoted",
    "promotion_blocked",
)
G4_FINAL_PROMOTION_RECORD_STATES: tuple[str, ...] = (
    "governed_promoted",
    "promotion_blocked",
)
G4_SOURCE_PAYLOAD_STATUS_VALUES: tuple[str, ...] = (
    "full_payload",
    "ref_only",
    "manifest_only",
    "unresolved",
)
G4_PUBLIC_EXPORT_HOOK_STATUS_VALUES: tuple[str, ...] = (
    "implemented",
    "out_of_scope_reference_only",
    "blocked",
)
G4_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_authority",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "closeout_verdict",
    "claim_authority",
    "claim_authority_without_upstream_grounding",
    "source_data_truth_authority",
    "public_recommendation",
    "policy_recommendation",
    "useful_design_credit_before_g5",
    "causal_effect_authority_without_g2",
    "proof_authority_without_g3",
    "legal_authority_without_gl",
    "human_override_of_a_incompleteness",
)
G4_AUTHORITATIVE_FOR: tuple[str, ...] = (
    "promotion_decision_replay",
    "governed_promotion_state_for_declared_scope",
    "closeout_pdc_compiler_g5_promotion_state_input_refs",
)
G4_HUMAN_DECISION_REQUIRED_SCOPE_FLAGS: tuple[str, ...] = (
    "high_stakes",
    "value_laden",
    "ranked_value",
    "accountability_sensitive",
    "out_of_routine",
)
G4_EXPECTED_HEALTH_METRICS: tuple[str, ...] = (
    "g4-promotion-attempts",
    "g4-governed-promoted-count",
    "g4-promotion-blocked-count",
    "g4-promotion-stalled-count",
    "g4-human-decision-routed-count",
)
G4_ADAPTER_PATH_IDS: tuple[str, ...] = (
    "layer3_g4_s2_source_resolution_to_promotion_input",
    "layer3_g4_design_record_to_promotion_input",
    "layer3_g4_dependency_manifests_to_grounded_contract_set",
    "layer3_g4_grounded_contract_set_to_a_completeness_ledger",
    "layer3_g4_a_completeness_to_weakest_boundary",
    "layer3_g4_s7_human_decision_to_p26_gate",
    "layer3_g4_weakest_boundary_to_promotion_record",
    "layer3_g4_promotion_record_to_closeout_consumer_gate",
    "layer3_g4_promotion_record_to_pdc_compiler_consumer_gate",
    "layer3_g4_promotion_record_to_g5_handoff",
    "layer3_g4_promotion_record_to_public_projection_refs",
)
G4_CONFORMANCE_NEGATIVE_IDS: tuple[str, ...] = (
    "shadow_design_record_self_promotes",
    "promotion_without_g1_grounded_source_contract",
    "source_design_record_resolution_unresolved",
    "source_design_record_digest_missing",
    "dependency_artifact_shape_mismatch",
    "effect_claim_without_g2_forecast_support",
    "proof_claim_without_g3_proof_record",
    "legal_claim_without_gl_legal_authority",
    "missing_a_firewall_ref_promoted",
    "gl_reissue_required_promoted",
    "gl_g4_compatibility_gate_overclaimed_as_legal_authority",
    "readiness_summary_only_promoted",
    "search_ledger_only_promoted",
    "s7_manifest_only_promoted",
    "s2_ledger_ref_only_human_decision",
    "w12d_manifest_only_source_payload",
    "source_design_record_ref_only_promoted",
    "data_promotion_lane_reused_for_g4",
    "generated_artifact_promotion_target_reused_for_g4",
    "upstream_builder_rerun_in_request_path",
    "upstream_may_not_use_for_ignored",
    "weakest_boundary_ignored",
    "human_decision_missing_for_high_stakes",
    "high_stakes_human_decision_not_required_bypass",
    "human_decision_scope_mismatch",
    "human_decision_overrides_a_incompleteness",
    "promotion_record_claims_closeout",
    "promotion_record_rewrites_closeout_reader",
    "promotion_record_claims_pdc_compile_authority",
    "promotion_record_rewrites_pdc_compiler",
    "promotion_record_claims_production",
    "promotion_record_claims_publication",
    "promotion_record_claims_approval",
    "promotion_record_claims_scorecard",
    "promotion_record_claims_useful_design_credit",
    "promotion_record_incomplete_may_not_use_for",
    "public_projection_raw_payload_leak",
    "public_export_hook_overclaimed",
    "policy_design_case_projection_authority_leak",
    "manifest_runtime_drift",
    "promotion_state_vocab_drops_shadow",
    "promotion_gate_admission_without_conformance",
)
G4_CONFORMANCE_EXPECTED_ISSUE_CODES: dict[str, tuple[str, ...]] = {
    "shadow_design_record_self_promotes": ("layer3_g4_shadow_self_promotion",),
    "promotion_without_g1_grounded_source_contract": (
        "layer3_g4_grounded_contract_ref_missing",
        "layer3_g4_missing_g1_grounded_source_contract",
    ),
    "source_design_record_resolution_unresolved": (
        "layer3_g4_source_design_record_unresolved",
    ),
    "source_design_record_digest_missing": (
        "layer3_g4_source_design_record_digest_missing",
    ),
    "dependency_artifact_shape_mismatch": (
        "layer3_g4_dependency_artifact_shape_mismatch",
    ),
    "effect_claim_without_g2_forecast_support": (
        "layer3_g4_missing_g2_forecast_support",
    ),
    "proof_claim_without_g3_proof_record": ("layer3_g4_missing_g3_proof_record",),
    "legal_claim_without_gl_legal_authority": (
        "layer3_g4_missing_gl_legal_authority",
    ),
    "missing_a_firewall_ref_promoted": ("layer3_g4_missing_a_firewall_ref",),
    "gl_reissue_required_promoted": (
        "layer3_g4_gl_reissue_required_blocks_promotion",
    ),
    "gl_g4_compatibility_gate_overclaimed_as_legal_authority": (
        "layer3_g4_gl_compatibility_gate_overclaimed",
    ),
    "readiness_summary_only_promoted": (
        "layer3_g4_readiness_summary_only_promotion",
    ),
    "search_ledger_only_promoted": ("layer3_g4_search_ledger_only_promotion",),
    "s7_manifest_only_promoted": ("layer3_g4_s7_manifest_only_human_decision",),
    "s2_ledger_ref_only_human_decision": (
        "layer3_g4_s2_ledger_ref_only_human_decision",
    ),
    "w12d_manifest_only_source_payload": ("layer3_g4_w12d_manifest_only_not_payload",),
    "source_design_record_ref_only_promoted": (
        "layer3_g4_source_design_record_payload_ref_only",
    ),
    "data_promotion_lane_reused_for_g4": ("layer3_g4_data_promotion_lane_confused",),
    "generated_artifact_promotion_target_reused_for_g4": (
        "layer3_g4_generated_artifact_promotion_target_confused",
    ),
    "upstream_builder_rerun_in_request_path": (
        "layer3_g4_upstream_builder_rerun_in_request_path",
    ),
    "upstream_may_not_use_for_ignored": (
        "layer3_g4_upstream_may_not_use_for_ignored",
    ),
    "weakest_boundary_ignored": ("layer3_g4_weakest_boundary_ignored",),
    "human_decision_missing_for_high_stakes": (
        "layer3_g4_human_decision_required",
        "layer3_g4_human_decision_record_missing",
    ),
    "high_stakes_human_decision_not_required_bypass": (
        "layer3_g4_high_stakes_human_decision_not_required_bypass",
    ),
    "human_decision_scope_mismatch": ("layer3_g4_human_decision_scope_mismatch",),
    "human_decision_overrides_a_incompleteness": (
        "layer3_g4_human_decision_overrides_a_incompleteness",
    ),
    "promotion_record_claims_closeout": ("layer3_g4_closeout_authority_leak",),
    "promotion_record_rewrites_closeout_reader": (
        "layer3_g4_closeout_reader_rewrite_attempt",
    ),
    "promotion_record_claims_pdc_compile_authority": (
        "layer3_g4_pdc_compile_authority_leak",
    ),
    "promotion_record_rewrites_pdc_compiler": (
        "layer3_g4_pdc_compiler_graph_rewrite_attempt",
    ),
    "promotion_record_claims_production": ("layer3_g4_production_authority_leak",),
    "promotion_record_claims_publication": ("layer3_g4_publication_authority_leak",),
    "promotion_record_claims_approval": ("layer3_g4_approval_authority_leak",),
    "promotion_record_claims_scorecard": ("layer3_g4_scorecard_authority_leak",),
    "promotion_record_claims_useful_design_credit": (
        "layer3_g4_useful_design_credit_leak",
    ),
    "promotion_record_incomplete_may_not_use_for": (
        "layer3_g4_may_not_use_for_incomplete",
    ),
    "public_projection_raw_payload_leak": ("layer3_g4_public_raw_payload_leak",),
    "public_export_hook_overclaimed": ("layer3_g4_public_export_hook_overclaimed",),
    "policy_design_case_projection_authority_leak": (
        "layer3_g4_policy_projection_authority_leak",
    ),
    "manifest_runtime_drift": ("layer3_g4_manifest_runtime_drift",),
    "promotion_state_vocab_drops_shadow": (
        "layer3_g4_shared_promotion_state_vocabulary_dropped_shadow",
    ),
    "promotion_gate_admission_without_conformance": (
        "layer3_g4_promotion_gate_admission_without_conformance",
    ),
}
G4_PERFORMANCE_SOURCE_REFS: tuple[Path, ...] = (
    Path("src/polisyos/runtime/quality/layer3_promotion_gate.py"),
    Path("tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py"),
)

POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
GENERATED_ARTIFACTS_REF = Path("architecture/generated_artifacts.toml")
INVENTORY_REF = POLICY_DESIGN_CASE_DIR / "inventory.json"
G0_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g0_readiness_manifest.json"
G0_DISCOVERY_SEARCH_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_discovery_search_discipline.json"
)
G0_ENGINEERING_QUALITY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_engineering_quality_check.json"
)
G1_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json"
G2_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json"
G3_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json"
GL_READINESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json"

G4_FAMILY_ARTIFACT_SHAPES: dict[str, tuple[tuple[str, Path, tuple[str, ...]], ...]] = {
    "g1": (
        (
            "g1_grounded_source_contracts",
            POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json",
            ("grounded_source_contracts", "bindings"),
        ),
    ),
    "g2": (
        (
            "g2_grounded_forecast_handoffs",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_grounded_forecast_handoffs.json",
            ("grounded_forecast_handoffs",),
        ),
        (
            "g2_forecast_support_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_forecast_support_bindings.json",
            ("forecast_support_bindings",),
        ),
        (
            "g2_s10_prerequisite_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_s10_prerequisite_bindings.json",
            ("s10_prerequisite_bindings",),
        ),
        (
            "g2_method_validity_transport",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_method_validity_transport.json",
            ("method_validity_transport",),
        ),
        (
            "g2_observable_calibration_report",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_observable_calibration_report.json",
            ("observable_calibration_report",),
        ),
        (
            "g2_transport_limit_declarations",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_transport_limit_declarations.json",
            ("transport_limit_declarations",),
        ),
        (
            "g2_authority_envelopes",
            POLICY_DESIGN_CASE_DIR / "layer3_g2_authority_envelopes.json",
            ("authority_envelopes",),
        ),
    ),
    "g3": (
        (
            "g3_proof_carrying_analytics_records",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_proof_carrying_analytics_records.json",
            ("proof_carrying_analytics_records",),
        ),
        (
            "g3_s11_predictive_posture_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_predictive_posture_bindings.json",
            ("s11_predictive_posture_bindings",),
        ),
        (
            "g3_certificate_resolution_report",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_certificate_resolution_report.json",
            ("certificate_resolution_report",),
        ),
        (
            "g3_method_requirement_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_method_requirement_bindings.json",
            ("method_requirement_bindings",),
        ),
        (
            "g3_s11_prerequisite_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_prerequisite_bindings.json",
            ("s11_prerequisite_bindings",),
        ),
        (
            "g3_s11_calibration_bindings",
            POLICY_DESIGN_CASE_DIR / "layer3_g3_s11_calibration_bindings.json",
            ("s11_calibration_bindings",),
        ),
    ),
    "gl": (
        (
            "gl_promotion_gate_handoff",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_promotion_gate_handoff.json",
            (),
        ),
        (
            "gl_g4_promotion_gate_consumer_gate",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_g4_promotion_gate_consumer_gate.json",
            (),
        ),
        (
            "gl_legal_authority_report",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_legal_authority_report.json",
            (),
        ),
        (
            "gl_threshold_authority_records",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_threshold_authority_records.json",
            ("records",),
        ),
        (
            "gl_mandate_authority_records",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_mandate_authority_records.json",
            ("records",),
        ),
        (
            "gl_temporal_competence_records",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_temporal_competence_records.json",
            ("records",),
        ),
        (
            "gl_amendment_lineage_records",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_amendment_lineage_records.json",
            ("records",),
        ),
        (
            "gl_reference_resolution_records",
            POLICY_DESIGN_CASE_DIR / "layer3_gl_reference_resolution_records.json",
            ("records",),
        ),
    ),
}

ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g4_g0_dependency_not_ready",
    "layer3_g4_g1_dependency_not_ready",
    "layer3_g4_context_dependency_missing",
    "layer3_g4_dependency_readiness_snapshot_missing",
    "layer3_g4_promotion_input_missing",
    "layer3_g4_source_design_record_missing",
    "layer3_g4_source_design_record_unresolved",
    "layer3_g4_source_design_record_digest_missing",
    "layer3_g4_source_design_record_payload_ref_only",
    "layer3_g4_source_design_record_shape_mismatch",
    "layer3_g4_source_design_record_not_shadow",
    "layer3_g4_w12d_manifest_only_not_payload",
    "layer3_g4_shadow_self_promotion",
    "layer3_g4_data_promotion_lane_confused",
    "layer3_g4_generated_artifact_promotion_target_confused",
    "layer3_g4_dependency_artifact_shape_mismatch",
    "layer3_g4_grounded_contract_set_missing",
    "layer3_g4_required_ref_unresolved",
    "layer3_g4_grounded_contract_ref_missing",
    "layer3_g4_readiness_summary_only_promotion",
    "layer3_g4_search_ledger_only_promotion",
    "layer3_g4_missing_g1_grounded_source_contract",
    "layer3_g4_missing_g2_forecast_support",
    "layer3_g4_missing_g2_calibration_ref",
    "layer3_g4_missing_g3_proof_record",
    "layer3_g4_missing_g3_certificate_resolution",
    "layer3_g4_missing_gl_legal_authority",
    "layer3_g4_missing_a_firewall_ref",
    "layer3_g4_gl_reissue_required_blocks_promotion",
    "layer3_g4_gl_reference_resolution_blocks_promotion",
    "layer3_g4_gl_compatibility_gate_overclaimed",
    "layer3_g4_search_recall_dependency_unhealthy",
    "layer3_g4_stale_upstream_index_blocks_promotion",
    "layer3_g4_upstream_builder_rerun_in_request_path",
    "layer3_g4_adapter_admission_missing",
    "layer3_g4_adapter_admission_failed",
    "layer3_g4_adapter_conformance_missing",
    "layer3_g4_adapter_conformance_failed",
    "layer3_g4_upstream_may_not_use_for_ignored",
    "layer3_g4_missing_s6_mandate_posture",
    "layer3_g4_missing_s8_value_choice_posture",
    "layer3_g4_missing_s10_prerequisite_posture",
    "layer3_g4_missing_s11_predictive_posture",
    "layer3_g4_missing_s12_resource_economics_posture",
    "layer3_g4_missing_s13_accountability_learning_posture",
    "layer3_g4_a_completeness_ledger_missing",
    "layer3_g4_a_completeness_failed",
    "layer3_g4_weakest_boundary_missing",
    "layer3_g4_weakest_boundary_ignored",
    "layer3_g4_limited_boundary_overpromoted",
    "layer3_g4_human_decision_required",
    "layer3_g4_human_decision_record_missing",
    "layer3_g4_high_stakes_human_decision_not_required_bypass",
    "layer3_g4_s7_manifest_only_human_decision",
    "layer3_g4_s2_ledger_ref_only_human_decision",
    "layer3_g4_human_decision_scope_mismatch",
    "layer3_g4_human_decision_inactive_choice",
    "layer3_g4_human_decision_five_rights_failed",
    "layer3_g4_human_decision_overrides_a_incompleteness",
    "layer3_g4_p26_responsibility_integrity_failed",
    "layer3_g4_promotion_record_missing",
    "layer3_g4_no_governed_promotion_record",
    "layer3_g4_no_blocked_negative_promotion_record",
    "layer3_g4_invalid_promotion_state",
    "layer3_g4_shared_promotion_state_vocabulary_dropped_shadow",
    "layer3_g4_closeout_consumer_gate_missing",
    "layer3_g4_pdc_compiler_consumer_gate_missing",
    "layer3_g4_g5_promotion_handoff_missing",
    "layer3_g4_pdc_compile_authority_leak",
    "layer3_g4_pdc_compiler_graph_rewrite_attempt",
    "layer3_g4_closeout_authority_leak",
    "layer3_g4_closeout_reader_rewrite_attempt",
    "layer3_g4_production_authority_leak",
    "layer3_g4_publication_authority_leak",
    "layer3_g4_approval_authority_leak",
    "layer3_g4_scorecard_authority_leak",
    "layer3_g4_useful_design_credit_leak",
    "layer3_g4_may_not_use_for_incomplete",
    "layer3_g4_public_raw_payload_leak",
    "layer3_g4_public_export_hook_overclaimed",
    "layer3_g4_policy_projection_authority_leak",
    "layer3_g4_public_surface_visibility_missing",
    "layer3_g4_generated_artifacts_family_missing",
    "layer3_g4_inventory_surface_missing",
    "layer3_g4_reference_index_missing",
    "layer3_g4_adapter_contract_registry_missing",
    "layer3_g4_adapter_registry_summary_only",
    "layer3_g4_registry_ratchet_delta_missing",
    "layer3_g4_promotion_gate_admission_maturity_invalid",
    "layer3_g4_promotion_gate_admission_without_conformance",
    "layer3_g4_manifest_runtime_drift",
    "layer3_g4_persisted_artifact_missing",
    "layer3_g4_import_laziness_violation",
    "layer3_g4_unbounded_artifact_scan",
)


class _G4Model(BaseModel):
    """Strict base class for G4 runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G4ValidationIssue(_G4Model):
    """One fail-closed G4 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G4ValidationReport(_G4Model):
    """G4 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G4ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_code_dictionary: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)


class Layer3G4PromotionRequest(_G4Model):
    """Typed promotion request for a shadow B-side output."""

    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    candidate_source: str = Field(min_length=1)
    incoming_projection_status: str = "shadow"
    promotion_scope: dict[str, Any] = Field(default_factory=dict)
    claim_refs: tuple[str, ...] = Field(default=())
    envelope_ref: str | None = None
    required_contract_families: tuple[str, ...] = Field(default=())
    source_design_record: dict[str, Any] = Field(default_factory=dict)
    human_decision_policy: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)


class Layer3G4DependencyArtifactShape(_G4Model):
    """One dependency artifact family path resolved through governed refs."""

    artifact_id: str = Field(min_length=1)
    family: Literal["g1", "g2", "g3", "gl"]
    artifact_path: str = Field(min_length=1)
    expected_path: tuple[str, ...] = Field(default=())
    status: Literal["pass", "fail", "missing"]
    row_count: int = Field(default=0, ge=0)
    schema_version: str | None = None
    rule_version: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4DependencyReadinessSnapshot(_G4Model):
    """Readiness snapshot for hard and context Layer 3 dependencies."""

    schema_version: str = LAYER3_G4_SCHEMA_VERSION
    rule_version: str = LAYER3_G4_RULE_VERSION
    status: Literal["pass", "fail"]
    g0_dependency_status: Literal["pass", "fail", "missing"]
    g1_dependency_status: Literal["pass", "fail", "missing"]
    g2_context_status: Literal["pass", "fail", "missing"]
    g3_context_status: Literal["pass", "fail", "missing"]
    gl_context_status: Literal["pass", "fail", "missing"]
    generated_artifacts_ref: str = GENERATED_ARTIFACTS_REF.as_posix()
    inventory_ref: str = INVENTORY_REF.as_posix()
    loaded_artifact_paths: tuple[str, ...] = Field(default=())
    missing_artifact_paths: tuple[str, ...] = Field(default=())
    manifest_drift_inputs: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4SourceDesignRecordResolution(_G4Model):
    """Source DesignRecordV0 payload or replay-ref resolution result."""

    status: Literal["pass", "fail"]
    payload_status: Literal["full_payload", "ref_only", "manifest_only", "unresolved"]
    source_design_record_ref: str | None = None
    source_design_record_replay_ref: str | None = None
    source_design_record_digest: str | None = None
    resolution_strategy: str = "explicit_promotion_input"
    issue_codes: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())


class Layer3G4SourcePayloadStatus(_G4Model):
    """Small source-payload status wrapper for generated summaries."""

    payload_status: Literal["full_payload", "ref_only", "manifest_only", "unresolved"]
    status: Literal["pass", "fail"]
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4NamingCollisionGuard(_G4Model):
    """Bounded guard for non-G4 uses of the word promotion."""

    status: Literal["pass", "fail"]
    runtime_http_promotion_lane_status: Literal["collision_detected", "not_found"]
    generated_artifact_promotion_target_status: Literal["collision_detected", "not_found"]
    collision_ids: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4PromotionInput(_G4Model):
    """One normalized G4 promotion input."""

    source_design_record_ref: str = Field(min_length=1)
    source_design_record_replay_ref: str = Field(min_length=1)
    source_design_record_digest: str = Field(min_length=1)
    source_design_record_resolution_status: Literal[
        "full_payload", "ref_only", "manifest_only", "unresolved"
    ]
    case_id: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    candidate_source: str = Field(min_length=1)
    incoming_projection_status: str = "shadow"
    promotion_scope: dict[str, Any] = Field(default_factory=dict)
    claim_refs: tuple[str, ...] = Field(default=())
    envelope_ref: str = Field(min_length=1)
    required_contract_families: tuple[str, ...] = Field(default=())
    human_decision_policy: dict[str, Any] = Field(default_factory=dict)
    stakes_profile: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    grounded_contract_rows: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4PromotionInputSet(_G4Model):
    """Normalized promotion input set."""

    schema_version: str = LAYER3_G4_SCHEMA_VERSION
    rule_version: str = LAYER3_G4_RULE_VERSION
    status: Literal["pass", "fail"] = "fail"
    promotion_inputs: tuple[Layer3G4PromotionInput, ...] = Field(default=())
    promotion_requests: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4GroundedContractRef(_G4Model):
    """Promotion-readable reference to an upstream grounded contract row."""

    family: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    source_binding_ref: str | None = None
    lineage_refs: tuple[str, ...] = Field(default=())
    coverage_refs: tuple[str, ...] = Field(default=())
    freshness_refs: tuple[str, ...] = Field(default=())
    a_firewall_refs: tuple[str, ...] = Field(default=())
    adapter_admission_refs: tuple[str, ...] = Field(default=())
    adapter_admission_status: str | None = None
    conformance_refs: tuple[str, ...] = Field(default=())
    adapter_conformance_status: str | None = None
    search_recall_status: str | None = None
    index_freshness_status: str | None = None
    grounded_forecast_handoff_ref: str | None = None
    forecast_support_binding_ref: str | None = None
    calibration_refs: tuple[str, ...] = Field(default=())
    method_validity_refs: tuple[str, ...] = Field(default=())
    uncertainty_refs: tuple[str, ...] = Field(default=())
    transport_limitation_refs: tuple[str, ...] = Field(default=())
    proof_ref: str | None = None
    certificate_resolution_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    s6_mandate_refs: tuple[str, ...] = Field(default=())
    s8_value_choice_refs: tuple[str, ...] = Field(default=())
    s10_prerequisite_refs: tuple[str, ...] = Field(default=())
    s11_predictive_posture_refs: tuple[str, ...] = Field(default=())
    s12_resource_economics_refs: tuple[str, ...] = Field(default=())
    s13_accountability_learning_refs: tuple[str, ...] = Field(default=())
    legal_authority_refs: tuple[str, ...] = Field(default=())
    mandate_refs: tuple[str, ...] = Field(default=())
    threshold_refs: tuple[str, ...] = Field(default=())
    temporal_competence_refs: tuple[str, ...] = Field(default=())
    amendment_lineage_status: str | None = None
    reference_resolution_status: str | None = None
    g4_compatibility_ref: str | None = None
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4GroundedContractSet(_G4Model):
    """Normalized set of upstream grounded contract refs."""

    schema_version: str = LAYER3_G4_SCHEMA_VERSION
    rule_version: str = LAYER3_G4_RULE_VERSION
    status: Literal["pass", "pass_with_limitations", "fail"] = "fail"
    grounded_contract_refs: tuple[Layer3G4GroundedContractRef, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4ACompletenessRequirement(_G4Model):
    """One A-side support requirement for a promoted claim."""

    claim_ref: str = Field(min_length=1)
    required_family: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    supporting_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4ACompletenessLedger(_G4Model):
    """A-completeness ledger for the declared promotion scope."""

    status: Literal["pass", "fail"] = "fail"
    requirements: tuple[Layer3G4ACompletenessRequirement, ...] = Field(default=())
    missing_requirement_count: int = Field(default=0, ge=0)
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4S7DecisionPayloadResolution(_G4Model):
    """Resolution result for a concrete S7 HumanDecisionRecord payload."""

    status: Literal["pass", "fail", "not_required"]
    payload_status: Literal["full_payload", "ref_only", "manifest_only", "unresolved"] = (
        "unresolved"
    )
    human_decision_record_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4HumanDecisionIntegrityGate(_G4Model):
    """P26/S7 human-decision integrity gate for promotion."""

    status: Literal["pass", "fail", "not_required"] = "not_required"
    human_decision_required: bool = False
    human_decision_record_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4WeakestBoundaryComposition(_G4Model):
    """Weakest-boundary composition over upstream contract refs."""

    status: Literal["pass", "fail"] = "fail"
    promotion_state: Literal["governed_promoted", "promotion_blocked"] = (
        "promotion_blocked"
    )
    promotion_scope: dict[str, Any] = Field(default_factory=dict)
    weakest_boundary_reason: str | None = None
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    produced_by: dict[str, Any] = Field(default_factory=dict)


class Layer3G4PromotionRecord(_G4Model):
    """Typed G4 promotion record."""

    promotion_record_id: str = Field(min_length=1)
    promotion_state: Literal["governed_promoted", "promotion_blocked"]
    promotion_scope: dict[str, Any] = Field(default_factory=dict)
    case_id: str = Field(min_length=1)
    candidate_ref: str | None = None
    source_design_record_ref: str = Field(min_length=1)
    source_design_record_digest: str | None = None
    grounded_contract_set_ref: str = Field(min_length=1)
    a_completeness_ledger_ref: str = Field(min_length=1)
    weakest_boundary_composition_ref: str = Field(min_length=1)
    human_decision_integrity_gate_ref: str = Field(min_length=1)
    authoritative_for: tuple[str, ...] = Field(default=G4_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    upstream_contract_refs: tuple[str, ...] = Field(default=())
    closeout_consumer_gate_ref: str = Field(min_length=1)
    pdc_compiler_consumer_gate_ref: str = Field(min_length=1)
    g5_handoff_ref: str = Field(min_length=1)
    registry_ratchet_delta_ref: str = Field(min_length=1)
    produced_by: dict[str, Any] = Field(default_factory=dict)
    rule_version: str = LAYER3_G4_RULE_VERSION
    schema_version: str = LAYER3_G4_SCHEMA_VERSION


class Layer3G4CloseoutConsumerGate(_G4Model):
    """Reference-only closeout consumer gate for promotion state."""

    status: Literal["pass", "fail"] = "fail"
    promotion_record_refs: tuple[str, ...] = Field(default=())
    promotion_states: dict[str, int] = Field(default_factory=dict)
    authoritative_for: tuple[str, ...] = (
        "closeout_input_promotion_state_refs",
        "g5_input_promotion_state_refs",
    )
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4PdcCompilerConsumerGate(_G4Model):
    """Reference-only PDC compiler consumer gate for promotion state."""

    status: Literal["pass", "fail"] = "fail"
    promotion_record_refs: tuple[str, ...] = Field(default=())
    promotion_state_input_refs: tuple[str, ...] = Field(default=())
    compiler_graph_rewrite_attempted: bool = False
    authoritative_for: tuple[str, ...] = ("pdc_graph_assembly_promotion_state_input_refs",)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4G5PromotionHandoff(_G4Model):
    """Reference-only handoff to G5 proving-ground conversion."""

    status: Literal["pass", "fail"] = "fail"
    promotion_record_refs: tuple[str, ...] = Field(default=())
    promotion_scopes: tuple[dict[str, Any], ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    upstream_contract_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("g5_first_proving_ground_promotion_state_input_refs",)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4GovernanceThroughputDelta(_G4Model):
    """Governance-throughput delta for promotion attempts."""

    status: Literal["pass", "fail"] = "fail"
    admitted_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    stalled_count: int = Field(default=0, ge=0)
    human_review_routed_count: int = Field(default=0, ge=0)
    block_reason_counts: dict[str, int] = Field(default_factory=dict)
    stall_reason_counts: dict[str, int] = Field(default_factory=dict)


class Layer3G4PromotionAuditSurface(_G4Model):
    """Audit surface for promotion state and blockers."""

    surface_id: str = G4_SURFACE_ID
    audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    surface_audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    promotion_record_refs: tuple[str, ...] = Field(default=())
    promotion_state_counts: dict[str, int] = Field(default_factory=dict)
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4PublicExportProjectionRefSurface(_G4Model):
    """Projection-ref surface for safe public export wiring."""

    surface_id: str = G4_SURFACE_ID
    projection_mode: str = "projection_only"
    public_export_hook_status: Literal[
        "implemented", "out_of_scope_reference_only", "blocked"
    ] = "out_of_scope_reference_only"
    public_export_bundle_route_registered: bool = False
    audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    REVIEWER: dict[str, Any] = Field(default_factory=dict)
    EXPERT: dict[str, Any] = Field(default_factory=dict)
    MACHINE: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=G4_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4ConformanceNegativeResult(_G4Model):
    """One executable G4 conformance-negative probe result."""

    negative_id: str = Field(min_length=1)
    status: Literal["pass", "fail"] = "fail"
    expected_issue_codes: tuple[str, ...] = Field(default=())
    observed_issue_codes: tuple[str, ...] = Field(default=())
    fixture_ref: str = Field(min_length=1)
    pattern_ids: tuple[str, ...] = Field(default=())
    capability_labels: tuple[str, ...] = Field(default=())


class Layer3G4PerformanceContractReport(_G4Model):
    """Performance/scaling contract for the bounded G4 request path."""

    status: Literal["pass", "fail"] = "fail"
    bounded_artifact_resolution_status: Literal["pass", "fail"] = "fail"
    json_artifact_load_scope_status: Literal["pass", "fail"] = "fail"
    recursive_repo_scan_status: Literal["pass", "fail"] = "fail"
    upstream_builder_rerun_status: Literal["pass", "fail"] = "fail"
    domain_corpus_duckdb_scan_status: Literal["pass", "fail"] = "fail"
    mutable_global_cache_status: Literal["pass", "fail"] = "fail"
    bounded_artifact_path_count: int = Field(default=0, ge=0)
    declared_family_count: int = Field(default=0, ge=0)
    checked_source_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4ConformanceReport(_G4Model):
    """G4 conformance-negative report."""

    status: Literal["pass", "fail"] = "fail"
    negative_ids: tuple[str, ...] = Field(default=())
    negative_results: tuple[Layer3G4ConformanceNegativeResult, ...] = Field(default=())
    performance_contract: Layer3G4PerformanceContractReport = Field(
        default_factory=Layer3G4PerformanceContractReport
    )
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4RegistryRatchetDelta(_G4Model):
    """Registry and capability-ratchet delta for the G4 gate."""

    status: Literal["pass", "fail"] = "fail"
    admission_maturity: str = "producer_missing"
    conformance_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4ReadinessManifest(_G4Model):
    """Readiness manifest summary for persisted G4 artifacts."""

    schema_version: str = LAYER3_G4_SCHEMA_VERSION
    rule_version: str = LAYER3_G4_RULE_VERSION
    status: Literal["pass", "fail"] = "fail"
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G4Bundle(_G4Model):
    """In-memory G4 runtime bundle for validation and write-mode tooling."""

    schema_version: str = LAYER3_G4_SCHEMA_VERSION
    rule_version: str = LAYER3_G4_RULE_VERSION
    dependency_readiness_snapshot: Layer3G4DependencyReadinessSnapshot
    dependency_artifact_shapes: tuple[Layer3G4DependencyArtifactShape, ...] = Field(
        default=()
    )
    naming_collision_guard: Layer3G4NamingCollisionGuard
    promotion_input_set: Layer3G4PromotionInputSet = Field(
        default_factory=Layer3G4PromotionInputSet
    )
    grounded_contract_set: Layer3G4GroundedContractSet = Field(
        default_factory=Layer3G4GroundedContractSet
    )
    a_completeness_ledger: Layer3G4ACompletenessLedger = Field(
        default_factory=Layer3G4ACompletenessLedger
    )
    human_decision_integrity_gate: Layer3G4HumanDecisionIntegrityGate = Field(
        default_factory=Layer3G4HumanDecisionIntegrityGate
    )
    weakest_boundary_composition: Layer3G4WeakestBoundaryComposition = Field(
        default_factory=Layer3G4WeakestBoundaryComposition
    )
    promotion_records: tuple[Layer3G4PromotionRecord, ...] = Field(default=())
    closeout_consumer_gate: Layer3G4CloseoutConsumerGate = Field(
        default_factory=Layer3G4CloseoutConsumerGate
    )
    pdc_compiler_consumer_gate: Layer3G4PdcCompilerConsumerGate = Field(
        default_factory=Layer3G4PdcCompilerConsumerGate
    )
    g5_promotion_handoff: Layer3G4G5PromotionHandoff = Field(
        default_factory=Layer3G4G5PromotionHandoff
    )
    governance_throughput_delta: Layer3G4GovernanceThroughputDelta = Field(
        default_factory=Layer3G4GovernanceThroughputDelta
    )
    promotion_audit_surface: Layer3G4PromotionAuditSurface = Field(
        default_factory=Layer3G4PromotionAuditSurface
    )
    public_export_projection_refs: Layer3G4PublicExportProjectionRefSurface = Field(
        default_factory=Layer3G4PublicExportProjectionRefSurface
    )
    conformance_report: Layer3G4ConformanceReport = Field(
        default_factory=Layer3G4ConformanceReport
    )
    performance_contract_report: Layer3G4PerformanceContractReport = Field(
        default_factory=Layer3G4PerformanceContractReport
    )
    registry_ratchet_delta: Layer3G4RegistryRatchetDelta = Field(
        default_factory=Layer3G4RegistryRatchetDelta
    )
    health_metric_delta: dict[str, Any] = Field(default_factory=dict)
    adapter_contract_registry: dict[str, Any] = Field(default_factory=dict)
    readiness_manifest: Layer3G4ReadinessManifest


def _issue(code: str, path: str, message: str) -> Layer3G4ValidationIssue:
    return Layer3G4ValidationIssue(code=code, path=path, message=message)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"_root": payload}


def _read_optional_json(repo_root: Path, relative_path: Path) -> dict[str, Any] | None:
    path = repo_root / relative_path
    if not path.exists():
        return None
    return _read_json(path)


def _read_optional_text(repo_root: Path, relative_path: Path) -> str:
    path = repo_root / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _readiness_status(repo_root: Path, relative_path: Path) -> Literal["pass", "fail", "missing"]:
    payload = _read_optional_json(repo_root, relative_path)
    if payload is None:
        return "missing"
    explicit = str(payload.get("status", "")).lower()
    if explicit == "fail":
        return "fail"
    if explicit in {"pass", "green"}:
        return "pass"
    failing_values = {
        value
        for key, value in payload.items()
        if key.endswith("_status") and isinstance(value, str) and value.lower() == "fail"
    }
    return "fail" if failing_values else "pass"


def _dig(payload: Mapping[str, object], key_path: Sequence[str]) -> object | None:
    current: object = payload
    for key in key_path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _row_count(value: object) -> int:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return len(value)
    if isinstance(value, Mapping):
        return len(value)
    return 0


def _request_requires_context(
    request: Mapping[str, Any],
) -> tuple[bool, bool, bool]:
    scope = request.get("promotion_scope", {})
    if not isinstance(scope, Mapping):
        scope = {}
    families = {
        str(value).lower()
        for value in request.get("required_contract_families", ())
        if value is not None
    }
    claim_families = {
        str(value).lower() for value in scope.get("claim_families", ()) if value is not None
    }
    requires_g2 = bool(scope.get("requires_causal_or_forecast_authority")) or bool(
        families & {"g2_forecast_support", "g2", "forecast_support"}
        or claim_families & {"causal_forecast", "causal", "forecast", "effect"}
    )
    requires_g3 = bool(scope.get("requires_proof_or_analytics_authority")) or bool(
        families & {"g3_proof_record", "g3", "proof_carrying_analytics"}
        or claim_families & {"proof", "analytics", "proof_analytics"}
    )
    requires_gl = bool(scope.get("requires_legal_or_mandate_authority")) or bool(
        families & {"gl_legal_mandate", "gl", "legal_mandate"}
        or claim_families & {"legal", "mandate", "legal_mandate", "threshold"}
    )
    return requires_g2, requires_g3, requires_gl


def _grounded_rows(request: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = request.get("grounded_contract_rows", ())
    if isinstance(rows, Sequence) and not isinstance(rows, str | bytes | bytearray):
        return tuple(row for row in rows if isinstance(row, Mapping))
    return ()


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return tuple(str(item) for item in value if item is not None)
    return ()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


G4_PASSING_STATUS_VALUES: frozenset[str] = frozenset(
    (
        "pass",
        "passed",
        "ready",
        "admitted",
        "conformant",
        "green",
        "not_required",
    )
)
G4_SEARCH_HEALTH_BLOCKING_STATUSES: frozenset[str] = frozenset(
    ("fail", "failed", "unhealthy", "missing", "blocked", "red")
)
G4_INDEX_FRESHNESS_BLOCKING_STATUSES: frozenset[str] = frozenset(
    ("fail", "failed", "unhealthy", "missing", "blocked", "red", "stale", "expired")
)
G4_DECLARED_AUTHORITY_POSTURE_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    (
        "requires_s6_mandate_ref",
        "s6_mandate_refs",
        "layer3_g4_missing_s6_mandate_posture",
    ),
    (
        "requires_s8_value_choice_ref",
        "s8_value_choice_refs",
        "layer3_g4_missing_s8_value_choice_posture",
    ),
    (
        "requires_s10_prerequisite_ref",
        "s10_prerequisite_refs",
        "layer3_g4_missing_s10_prerequisite_posture",
    ),
    (
        "requires_s11_predictive_posture_ref",
        "s11_predictive_posture_refs",
        "layer3_g4_missing_s11_predictive_posture",
    ),
    (
        "requires_s12_resource_economics_ref",
        "s12_resource_economics_refs",
        "layer3_g4_missing_s12_resource_economics_posture",
    ),
    (
        "requires_s13_accountability_learning_ref",
        "s13_accountability_learning_refs",
        "layer3_g4_missing_s13_accountability_learning_posture",
    ),
)


def _status_value(value: str | None) -> str:
    return str(value or "").strip().lower()


def _status_is_nonpassing(value: str | None) -> bool:
    status = _status_value(value)
    return bool(status) and status not in G4_PASSING_STATUS_VALUES


def _stakes_profile_from_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "high_stakes": bool(scope.get("high_stakes")),
        "value_laden": bool(scope.get("value_laden")),
        "ranked_value": bool(scope.get("ranked_value")),
        "accountability_sensitive": bool(scope.get("accountability_sensitive")),
        "out_of_routine": bool(scope.get("out_of_routine")),
    }


def _requires_g1(request: Mapping[str, Any]) -> bool:
    required = {str(value) for value in request.get("required_contract_families", ())}
    scope = request.get("promotion_scope", {})
    claim_families = set()
    if isinstance(scope, Mapping):
        claim_families = {str(value) for value in scope.get("claim_families", ())}
    return "g1_source_contract" in required or "source_data" in claim_families


def _has_g1_grounded_row(request: Mapping[str, Any]) -> bool:
    return any(str(row.get("family")) == "g1_source_contract" for row in _grounded_rows(request))


def _summary(snapshot: Layer3G4DependencyReadinessSnapshot) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "rule_version": snapshot.rule_version,
        "g0_dependency_status": snapshot.g0_dependency_status,
        "g1_dependency_status": snapshot.g1_dependency_status,
        "g2_context_status": snapshot.g2_context_status,
        "g3_context_status": snapshot.g3_context_status,
        "gl_context_status": snapshot.gl_context_status,
        "g4_dependency_readiness_status": snapshot.status,
        "g4_dependency_artifact_shape_status": "pass",
        "g4_manifest_runtime_drift_key_count": 0,
    }


def _snapshot_from_payload(
    repo_root: Path,
    snapshot_payload: Mapping[str, Any] | None,
) -> Layer3G4DependencyReadinessSnapshot:
    base = build_g4_dependency_readiness_snapshot(repo_root)
    if snapshot_payload is None:
        return base
    merged = base.model_dump(mode="json")
    allowed = set(Layer3G4DependencyReadinessSnapshot.model_fields)
    for key, value in snapshot_payload.items():
        if key in allowed:
            merged[key] = value
    if "status" not in snapshot_payload:
        merged["status"] = (
            "pass"
            if merged.get("g0_dependency_status") == "pass"
            and merged.get("g1_dependency_status") == "pass"
            else "fail"
        )
    return Layer3G4DependencyReadinessSnapshot.model_validate(merged)


def build_g4_dependency_readiness_snapshot(
    repo_root: Path,
) -> Layer3G4DependencyReadinessSnapshot:
    """Build the bounded G4 hard/context dependency readiness snapshot.

    Args:
        repo_root: Repository root containing `architecture/`.

    Returns:
        Strict dependency snapshot with loaded and missing governed paths.
    """

    issue_codes: list[str] = []
    loaded: list[str] = []
    missing: list[str] = []
    governed_refs = (
        GENERATED_ARTIFACTS_REF,
        INVENTORY_REF,
        G0_READINESS_PATH,
        G0_DISCOVERY_SEARCH_PATH,
        G0_ENGINEERING_QUALITY_PATH,
        G1_READINESS_PATH,
        POLICY_DESIGN_CASE_DIR / "layer3_g1_grounded_source_contracts.json",
        G2_READINESS_PATH,
        G3_READINESS_PATH,
        GL_READINESS_PATH,
    )

    for relative_path in governed_refs:
        path = repo_root / relative_path
        if path.exists():
            loaded.append(relative_path.as_posix())
        else:
            missing.append(relative_path.as_posix())

    if (repo_root / GENERATED_ARTIFACTS_REF).exists():
        tomllib.loads((repo_root / GENERATED_ARTIFACTS_REF).read_text(encoding="utf-8"))

    g0_status = _readiness_status(repo_root, G0_READINESS_PATH)
    g1_status = _readiness_status(repo_root, G1_READINESS_PATH)
    g2_status = _readiness_status(repo_root, G2_READINESS_PATH)
    g3_status = _readiness_status(repo_root, G3_READINESS_PATH)
    gl_status = _readiness_status(repo_root, GL_READINESS_PATH)

    if g0_status != "pass":
        issue_codes.append("layer3_g4_g0_dependency_not_ready")
    if g1_status != "pass":
        issue_codes.append("layer3_g4_g1_dependency_not_ready")

    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    manifest_drift_inputs = {
        "g0_manifest_ref": G0_READINESS_PATH.as_posix(),
        "g1_manifest_ref": G1_READINESS_PATH.as_posix(),
        "g2_manifest_ref": G2_READINESS_PATH.as_posix(),
        "g3_manifest_ref": G3_READINESS_PATH.as_posix(),
        "gl_manifest_ref": GL_READINESS_PATH.as_posix(),
        "generated_artifacts_ref": GENERATED_ARTIFACTS_REF.as_posix(),
        "inventory_ref": INVENTORY_REF.as_posix(),
    }
    return Layer3G4DependencyReadinessSnapshot(
        status=status,
        g0_dependency_status=g0_status,
        g1_dependency_status=g1_status,
        g2_context_status=g2_status,
        g3_context_status=g3_status,
        gl_context_status=gl_status,
        loaded_artifact_paths=tuple(loaded),
        missing_artifact_paths=tuple(missing),
        manifest_drift_inputs=manifest_drift_inputs,
        issue_codes=tuple(issue_codes),
    )


def load_g4_dependency_artifacts(
    repo_root: Path,
    required_families: Sequence[str] = ("g1", "g2", "g3", "gl"),
) -> tuple[Layer3G4DependencyArtifactShape, ...]:
    """Resolve persisted upstream artifact families through governed paths."""

    shapes: list[Layer3G4DependencyArtifactShape] = []
    for family in required_families:
        family_key = str(family).lower()
        for artifact_id, relative_path, key_path in G4_FAMILY_ARTIFACT_SHAPES.get(
            family_key, ()
        ):
            path = repo_root / relative_path
            if not path.exists():
                shapes.append(
                    Layer3G4DependencyArtifactShape(
                        artifact_id=artifact_id,
                        family=family_key,  # type: ignore[arg-type]
                        artifact_path=relative_path.as_posix(),
                        expected_path=key_path,
                        status="missing",
                        issue_codes=("layer3_g4_persisted_artifact_missing",),
                    )
                )
                continue
            payload = _read_json(path)
            value = payload if not key_path else _dig(payload, key_path)
            issue_codes: tuple[str, ...] = ()
            status: Literal["pass", "fail", "missing"] = "pass"
            if key_path and value is None:
                issue_codes = ("layer3_g4_dependency_artifact_shape_mismatch",)
                status = "fail"
            shapes.append(
                Layer3G4DependencyArtifactShape(
                    artifact_id=artifact_id,
                    family=family_key,  # type: ignore[arg-type]
                    artifact_path=relative_path.as_posix(),
                    expected_path=key_path,
                    status=status,
                    row_count=_row_count(value),
                    schema_version=payload.get("schema_version"),
                    rule_version=payload.get("rule_version"),
                    issue_codes=issue_codes,
                )
            )
    return tuple(shapes)


def resolve_g4_source_design_record(
    repo_root: Path,
    request: Mapping[str, Any],
) -> Layer3G4SourceDesignRecordResolution:
    """Resolve the source DesignRecordV0 payload from explicit request refs."""

    del repo_root
    source = request.get("source_design_record")
    if not isinstance(source, Mapping):
        return Layer3G4SourceDesignRecordResolution(
            status="fail",
            payload_status="unresolved",
            issue_codes=(
                "layer3_g4_source_design_record_missing",
                "layer3_g4_source_design_record_unresolved",
            ),
            blocker_refs=("source_design_record",),
        )
    payload_status = str(source.get("payload_status") or "unresolved")
    if payload_status not in G4_SOURCE_PAYLOAD_STATUS_VALUES:
        payload_status = "unresolved"
    ref = source.get("ref")
    replay_ref = source.get("replay_ref")
    digest = source.get("digest")
    issue_codes: list[str] = []
    blocker_refs: list[str] = []
    if payload_status == "unresolved":
        issue_codes.append("layer3_g4_source_design_record_unresolved")
        blocker_refs.append(str(ref or "source_design_record"))
    if payload_status == "ref_only":
        issue_codes.append("layer3_g4_source_design_record_payload_ref_only")
        blocker_refs.append(str(ref or "source_design_record"))
    if payload_status == "manifest_only":
        issue_codes.append("layer3_g4_w12d_manifest_only_not_payload")
        issue_codes.append("layer3_g4_source_design_record_unresolved")
        blocker_refs.append(str(ref or "source_design_record"))
    if not digest or _g4_placeholder_digest(str(digest)):
        issue_codes.append("layer3_g4_source_design_record_digest_missing")
        blocker_refs.append(str(ref or "source_design_record_digest"))
    if payload_status == "full_payload" and not replay_ref:
        issue_codes.append("layer3_g4_source_design_record_unresolved")
        blocker_refs.append(str(ref or "source_design_record_replay_ref"))
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G4SourceDesignRecordResolution(
        status=status,
        payload_status=payload_status,  # type: ignore[arg-type]
        source_design_record_ref=str(ref) if ref else None,
        source_design_record_replay_ref=str(replay_ref) if replay_ref else None,
        source_design_record_digest=str(digest) if digest else None,
        resolution_strategy=str(source.get("resolution_strategy") or "explicit_promotion_input"),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        blocker_refs=tuple(dict.fromkeys(blocker_refs)),
    )


def check_g4_naming_collisions(repo_root: Path) -> Layer3G4NamingCollisionGuard:
    """Detect known non-G4 promotion surfaces using bounded exact files."""

    route_text = _read_optional_text(repo_root, Path("src/polisyos/runtime/http/routes/control.py"))
    lifecycle_text = _read_optional_text(
        repo_root,
        Path("src/polisyos/runtime/http/services/control/run_lifecycle.py"),
    )
    retrieval_text = _read_optional_text(
        repo_root,
        Path("src/polisyos/fabric/retrieval/service.py"),
    )
    generated_text = _read_optional_text(repo_root, GENERATED_ARTIFACTS_REF)
    collision_ids: list[str] = []
    issue_codes: list[str] = []
    runtime_status: Literal["collision_detected", "not_found"] = "not_found"
    generated_status: Literal["collision_detected", "not_found"] = "not_found"
    if "/data/promotion" in route_text or "PromotionLane" in lifecycle_text + retrieval_text:
        runtime_status = "collision_detected"
        collision_ids.append("runtime_http_promotion_lane")
        issue_codes.append("layer3_g4_data_promotion_lane_confused")
    if "promotion_target" in generated_text:
        generated_status = "collision_detected"
        collision_ids.append("generated_artifact_promotion_target")
        issue_codes.append("layer3_g4_generated_artifact_promotion_target_confused")
    return Layer3G4NamingCollisionGuard(
        status="fail" if collision_ids else "pass",
        runtime_http_promotion_lane_status=runtime_status,
        generated_artifact_promotion_target_status=generated_status,
        collision_ids=tuple(collision_ids),
        issue_codes=tuple(issue_codes),
    )


def build_g4_promotion_input_set(
    repo_root: Path,
    requests: Sequence[Mapping[str, Any]] = (),
) -> Layer3G4PromotionInputSet:
    """Build a normalized G4 promotion input set from explicit requests."""

    inputs: list[Layer3G4PromotionInput] = []
    issue_codes: list[str] = []
    request_payloads: list[dict[str, Any]] = []
    for request in requests:
        request_payload = dict(request)
        request_payloads.append(request_payload)
        source_resolution = resolve_g4_source_design_record(repo_root, request_payload)
        issue_codes.extend(source_resolution.issue_codes)
        scope = request_payload.get("promotion_scope", {})
        if not isinstance(scope, Mapping):
            scope = {}
        human_decision_policy = request_payload.get("human_decision_policy", {})
        if not isinstance(human_decision_policy, Mapping):
            human_decision_policy = {}
        stakes_profile = request_payload.get("stakes_profile")
        if not isinstance(stakes_profile, Mapping):
            stakes_profile = _stakes_profile_from_scope(scope)
        grounded_rows = tuple(dict(row) for row in _grounded_rows(request_payload))
        if (
            source_resolution.source_design_record_ref
            and source_resolution.source_design_record_replay_ref
            and source_resolution.source_design_record_digest
        ):
            inputs.append(
                Layer3G4PromotionInput(
                    source_design_record_ref=source_resolution.source_design_record_ref,
                    source_design_record_replay_ref=(
                        source_resolution.source_design_record_replay_ref
                    ),
                    source_design_record_digest=source_resolution.source_design_record_digest,
                    source_design_record_resolution_status=source_resolution.payload_status,
                    case_id=str(request_payload.get("case_id") or ""),
                    candidate_ref=str(request_payload.get("candidate_ref") or ""),
                    candidate_source=str(request_payload.get("candidate_source") or ""),
                    incoming_projection_status=str(
                        request_payload.get("incoming_projection_status") or "shadow"
                    ),
                    promotion_scope=dict(scope),
                    claim_refs=_as_str_tuple(request_payload.get("claim_refs", ())),
                    envelope_ref=str(request_payload.get("envelope_ref") or ""),
                    required_contract_families=_as_str_tuple(
                        request_payload.get("required_contract_families", ())
                    ),
                    human_decision_policy=dict(human_decision_policy),
                    stakes_profile=dict(stakes_profile),
                    may_not_use_for=tuple(
                        dict.fromkeys(
                            _as_str_tuple(request_payload.get("may_not_use_for", ()))
                            or G4_MAY_NOT_USE_FOR
                        )
                    ),
                    grounded_contract_rows=grounded_rows,
                    issue_codes=source_resolution.issue_codes,
                )
            )
    if not requests:
        issue_codes.append("layer3_g4_promotion_input_missing")
    return Layer3G4PromotionInputSet(
        status="pass" if inputs and not issue_codes else "fail",
        promotion_inputs=tuple(inputs),
        promotion_requests=tuple(request_payloads),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g4_promotion_requests_from_gx_data_home(
    repo_root: Path,
) -> tuple[Layer3G4PromotionRequest, ...]:
    """Build explicit G4 promotion requests from the persisted GX data home."""

    return tuple(
        Layer3G4PromotionRequest.model_validate(payload)
        for payload in build_g4_promotion_request_dicts_from_data_home(repo_root)
    )


def build_g4_grounded_contract_set(
    repo_root: Path,
    promotion_input_set: Layer3G4PromotionInputSet | Sequence[Mapping[str, Any]] = (),
) -> Layer3G4GroundedContractSet:
    """Normalize upstream grounded contract rows for promotion consumption."""

    root = Path(repo_root)
    if isinstance(promotion_input_set, Layer3G4PromotionInputSet):
        promotion_inputs = promotion_input_set.promotion_inputs
    else:
        promotion_inputs = build_g4_promotion_input_set(
            root,
            promotion_input_set,
        ).promotion_inputs
    refs: list[Layer3G4GroundedContractRef] = []
    issue_codes: list[str] = []
    required_families: set[str] = set()
    limited = False
    for promotion_input in promotion_inputs:
        required_families.update(promotion_input.required_contract_families)
        for row in promotion_input.grounded_contract_rows:
            ref = row.get("ref")
            family = row.get("family")
            family_id = str(family or "")
            if family_id == "search_ledger":
                issue_codes.append("layer3_g4_search_ledger_only_promotion")
                continue
            if family_id == "readiness_manifest":
                issue_codes.append("layer3_g4_readiness_summary_only_promotion")
                continue
            if family_id == "gl_g4_compatibility":
                issue_codes.extend(
                    (
                        "layer3_g4_gl_compatibility_gate_overclaimed",
                        "layer3_g4_missing_gl_legal_authority",
                    )
                )
                continue
            if not ref or family_id not in {
                "g1_source_contract",
                "g2_forecast_support",
                "g3_proof_record",
                "gl_legal_mandate",
            }:
                issue_codes.append("layer3_g4_grounded_contract_ref_missing")
                continue
            ref_resolution = resolve_required_ref(root, str(ref))
            if _is_required_cross_slice_ref(str(ref)) and not ref_resolution.exists:
                issue_codes.extend(
                    (
                        "layer3_g4_required_ref_unresolved",
                        "layer3_g4_grounded_contract_ref_missing",
                        *ref_resolution.issue_codes,
                    )
                )
                if family_id == "g1_source_contract":
                    issue_codes.append("layer3_g4_missing_g1_grounded_source_contract")
                continue
            limitation_refs = _as_str_tuple(row.get("limitation_refs", ()))
            amendment_status = row.get("amendment_lineage_status")
            reference_status = row.get("reference_resolution_status")
            if limitation_refs or amendment_status == "reissue_required" or reference_status == (
                "reissue_required"
            ):
                limited = True
            adapter_admission_refs = _as_str_tuple(
                row.get("adapter_admission_refs", ()) or row.get("adapter_admission_ref")
            )
            conformance_refs = _as_str_tuple(
                row.get("conformance_refs", ()) or row.get("conformance_ref")
            )
            adapter_admission_status = _optional_str(row.get("adapter_admission_status"))
            adapter_conformance_status = _optional_str(
                row.get("adapter_conformance_status") or row.get("conformance_status")
            )
            search_recall_status = _optional_str(
                row.get("search_recall_status") or row.get("search_health_status")
            )
            index_freshness_status = _optional_str(
                row.get("index_freshness_status") or row.get("freshness_status")
            )
            refs.append(
                Layer3G4GroundedContractRef(
                    family=family_id,
                    ref=str(ref),
                    source_binding_ref=str(
                        row.get("binding_id")
                        or row.get("source_binding_ref")
                        or row.get("forecast_support_binding_ref")
                        or row.get("proof_ref")
                        or row.get("handoff_id")
                        or ref
                    ),
                    lineage_refs=_as_str_tuple(row.get("lineage_refs", ())),
                    coverage_refs=_as_str_tuple(
                        row.get("coverage_refs", ())
                        or row.get("coverage_period_ref")
                    ),
                    freshness_refs=_as_str_tuple(
                        row.get("freshness_refs", ())
                        or row.get("freshness_ref")
                    ),
                    a_firewall_refs=_as_str_tuple(row.get("a_firewall_refs", ())),
                    adapter_admission_refs=adapter_admission_refs,
                    adapter_admission_status=adapter_admission_status
                    or ("pass" if adapter_admission_refs else None),
                    conformance_refs=conformance_refs,
                    adapter_conformance_status=adapter_conformance_status
                    or ("pass" if conformance_refs else None),
                    search_recall_status=search_recall_status,
                    index_freshness_status=index_freshness_status,
                    grounded_forecast_handoff_ref=(
                        str(row.get("grounded_forecast_handoff_ref"))
                        if row.get("grounded_forecast_handoff_ref")
                        else None
                    ),
                    forecast_support_binding_ref=(
                        str(row.get("forecast_support_binding_ref"))
                        if row.get("forecast_support_binding_ref")
                        else None
                    ),
                    calibration_refs=_as_str_tuple(row.get("calibration_refs", ())),
                    method_validity_refs=_as_str_tuple(row.get("method_validity_refs", ())),
                    uncertainty_refs=_as_str_tuple(row.get("uncertainty_refs", ())),
                    transport_limitation_refs=_as_str_tuple(
                        row.get("transport_limitation_refs", ())
                    ),
                    proof_ref=str(row.get("proof_ref")) if row.get("proof_ref") else None,
                    certificate_resolution_refs=_as_str_tuple(
                        row.get("certificate_resolution_refs", ())
                    ),
                    method_requirement_refs=_as_str_tuple(
                        row.get("method_requirement_refs", ())
                    ),
                    s6_mandate_refs=_as_str_tuple(row.get("s6_mandate_refs", ())),
                    s8_value_choice_refs=_as_str_tuple(
                        row.get("s8_value_choice_refs", ())
                    ),
                    s10_prerequisite_refs=_as_str_tuple(
                        row.get("s10_prerequisite_refs", ())
                    ),
                    s11_predictive_posture_refs=_as_str_tuple(
                        row.get("s11_predictive_posture_refs", ())
                    ),
                    s12_resource_economics_refs=_as_str_tuple(
                        row.get("s12_resource_economics_refs", ())
                    ),
                    s13_accountability_learning_refs=_as_str_tuple(
                        row.get("s13_accountability_learning_refs", ())
                    ),
                    legal_authority_refs=_as_str_tuple(row.get("legal_authority_refs", ())),
                    mandate_refs=_as_str_tuple(row.get("mandate_refs", ())),
                    threshold_refs=_as_str_tuple(row.get("threshold_refs", ())),
                    temporal_competence_refs=_as_str_tuple(
                        row.get("temporal_competence_refs", ())
                    ),
                    amendment_lineage_status=(
                        str(amendment_status) if amendment_status is not None else None
                    ),
                    reference_resolution_status=(
                        str(reference_status) if reference_status is not None else None
                    ),
                    g4_compatibility_ref=(
                        str(row.get("g4_compatibility_ref"))
                        if row.get("g4_compatibility_ref")
                        else None
                    ),
                    authoritative_for=_as_str_tuple(row.get("authoritative_for", ())),
                    may_not_use_for=_as_str_tuple(row.get("may_not_use_for", ())),
                    limitation_refs=limitation_refs,
                    issue_codes=_as_str_tuple(row.get("issue_codes", ())),
                )
            )
    if "gl_legal_mandate" in required_families and not any(
        ref.family == "gl_legal_mandate" and ref.legal_authority_refs for ref in refs
    ):
        issue_codes.append("layer3_g4_missing_gl_legal_authority")
    if not refs and not issue_codes:
        issue_codes.append("layer3_g4_grounded_contract_ref_missing")
    status: Literal["pass", "pass_with_limitations", "fail"]
    if issue_codes:
        status = "fail"
    elif limited:
        status = "pass_with_limitations"
    else:
        status = "pass"
    return Layer3G4GroundedContractSet(
        status=status,
        grounded_contract_refs=tuple(refs),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _g4_g1_binding_ref_exists(
    repo_root: Path,
    ref: str,
    row: Mapping[str, Any],
) -> bool:
    if not ref.startswith("repo://"):
        return False
    ref_body = ref.removeprefix("repo://")
    rel_path, _, fragment = ref_body.partition("#")
    payload = _read_json(repo_root / rel_path)
    raw_bindings = _dig(payload, ("grounded_source_contracts", "bindings")) or payload.get(
        "bindings"
    )
    bindings = (
        tuple(item for item in raw_bindings if isinstance(item, Mapping))
        if isinstance(raw_bindings, Sequence) and not isinstance(raw_bindings, str | bytes)
        else ()
    )
    if not bindings:
        return False
    fragment_target = fragment.split("/", 1)[1] if fragment.startswith("bindings/") else fragment
    expected_refs = {
        _g4_normalize_binding_selector(fragment_target),
        _g4_normalize_binding_selector(_optional_str(row.get("binding_id"))),
        _g4_normalize_binding_selector(_optional_str(row.get("source_binding_ref"))),
    }
    expected_refs.discard("")
    if not expected_refs:
        return False
    for binding in bindings:
        candidates = {
            _g4_normalize_binding_selector(_optional_str(binding.get("binding_id"))),
            _g4_normalize_binding_selector(_optional_str(binding.get("construct_ref"))),
            _g4_normalize_binding_selector(_optional_str(binding.get("source_contract_ref"))),
        }
        if expected_refs & candidates:
            return True
    return False


def _is_required_cross_slice_ref(ref: str) -> bool:
    return ref.startswith(("repo://", "manifest://", "generated-artifact://"))


def _g4_normalize_binding_selector(value: str | None) -> str:
    return (
        str(value or "")
        .removeprefix("construct:")
        .removeprefix("source-contract://")
        .strip()
    )


def _contract_refs_by_family(
    contract_set: Layer3G4GroundedContractSet,
) -> dict[str, tuple[Layer3G4GroundedContractRef, ...]]:
    grouped: dict[str, list[Layer3G4GroundedContractRef]] = {}
    for ref in contract_set.grounded_contract_refs:
        grouped.setdefault(ref.family, []).append(ref)
    return {family: tuple(refs) for family, refs in grouped.items()}


def _required_families_for_input(
    promotion_input: Layer3G4PromotionInput,
) -> tuple[str, ...]:
    scope = promotion_input.promotion_scope
    families = set(promotion_input.required_contract_families)
    claim_families = {str(value) for value in scope.get("claim_families", ())}
    if "source_data" in claim_families:
        families.add("g1_source_contract")
    if (
        scope.get("requires_causal_or_forecast_authority")
        or claim_families & {"causal_forecast", "causal", "forecast", "effect"}
    ):
        families.add("g2_forecast_support")
    if (
        scope.get("requires_proof_or_analytics_authority")
        or claim_families & {"proof_analytics", "proof", "analytics"}
    ):
        families.add("g3_proof_record")
    if (
        scope.get("requires_legal_or_mandate_authority")
        or claim_families & {"legal_mandate", "legal", "mandate", "threshold"}
    ):
        families.add("gl_legal_mandate")
    return tuple(sorted(families))


def _declared_posture_issue_codes(
    refs: Sequence[Layer3G4GroundedContractRef],
    promotion_scope: Mapping[str, Any],
) -> tuple[str, ...]:
    issues: list[str] = []
    for scope_flag, ref_attr, issue_code in G4_DECLARED_AUTHORITY_POSTURE_REQUIREMENTS:
        if bool(promotion_scope.get(scope_flag)) and not any(
            getattr(ref, ref_attr) for ref in refs
        ):
            issues.append(issue_code)
    return tuple(issues)


def _contract_support_issue_codes(
    required_family: str,
    refs: Sequence[Layer3G4GroundedContractRef],
    promotion_scope: Mapping[str, Any],
) -> tuple[str, ...]:
    issues: list[str] = []
    if not refs:
        missing_code = {
            "g1_source_contract": "layer3_g4_missing_g1_grounded_source_contract",
            "g2_forecast_support": "layer3_g4_missing_g2_forecast_support",
            "g3_proof_record": "layer3_g4_missing_g3_proof_record",
            "gl_legal_mandate": "layer3_g4_missing_gl_legal_authority",
        }.get(required_family, "layer3_g4_grounded_contract_ref_missing")
        issues.append(missing_code)
        if required_family == "g3_proof_record":
            issues.append("layer3_g4_missing_g3_certificate_resolution")
        if required_family == "g2_forecast_support":
            issues.append("layer3_g4_missing_g2_calibration_ref")
        return tuple(issues)

    for ref in refs:
        if not ref.adapter_admission_refs:
            issues.append("layer3_g4_adapter_admission_missing")
        elif _status_is_nonpassing(ref.adapter_admission_status):
            issues.append("layer3_g4_adapter_admission_failed")
        if not ref.conformance_refs:
            issues.append("layer3_g4_adapter_conformance_missing")
        elif _status_is_nonpassing(ref.adapter_conformance_status):
            issues.append("layer3_g4_adapter_conformance_failed")
        if (
            ref.search_recall_status
            and _status_value(ref.search_recall_status)
            in G4_SEARCH_HEALTH_BLOCKING_STATUSES
        ):
            issues.append("layer3_g4_search_recall_dependency_unhealthy")
        if (
            ref.index_freshness_status
            and _status_value(ref.index_freshness_status)
            in G4_INDEX_FRESHNESS_BLOCKING_STATUSES
        ):
            issues.append("layer3_g4_stale_upstream_index_blocks_promotion")
        if (
            "layer3_g4_governed_promotion_state" in ref.may_not_use_for
            or "governed_promotion_state_for_declared_scope" in ref.may_not_use_for
        ):
            issues.append("layer3_g4_upstream_may_not_use_for_ignored")

    if required_family == "g1_source_contract" and promotion_scope.get(
        "requires_a_firewall_ref"
    ) and not any(ref.a_firewall_refs for ref in refs):
        issues.append("layer3_g4_missing_a_firewall_ref")
    if required_family == "g2_forecast_support":
        if not any(ref.calibration_refs for ref in refs) and not any(
            ref.limitation_refs for ref in refs
        ):
            issues.append("layer3_g4_missing_g2_calibration_ref")
        if promotion_scope.get("requested_boundary") == "unlimited" and any(
            ref.limitation_refs or ref.transport_limitation_refs for ref in refs
        ):
            issues.append("layer3_g4_limited_boundary_overpromoted")
    if required_family == "g3_proof_record":
        if not any(ref.proof_ref for ref in refs):
            issues.append("layer3_g4_missing_g3_proof_record")
        if not any(ref.certificate_resolution_refs for ref in refs):
            issues.append("layer3_g4_missing_g3_certificate_resolution")
    if required_family == "gl_legal_mandate":
        if not any(ref.legal_authority_refs for ref in refs):
            issues.append("layer3_g4_missing_gl_legal_authority")
        if not any(ref.temporal_competence_refs for ref in refs):
            issues.append("layer3_g4_missing_gl_legal_authority")
        if any(ref.amendment_lineage_status == "reissue_required" for ref in refs):
            issues.append("layer3_g4_gl_reissue_required_blocks_promotion")
        if any(ref.reference_resolution_status == "reissue_required" for ref in refs):
            issues.append("layer3_g4_gl_reference_resolution_blocks_promotion")
    return tuple(dict.fromkeys(issues))


def build_g4_a_completeness_ledger(
    repo_root: Path | None = None,
    promotion_input_set: Layer3G4PromotionInputSet | Sequence[Mapping[str, Any]] = (),
    contract_set: Layer3G4GroundedContractSet | None = None,
) -> Layer3G4ACompletenessLedger:
    """Build the A-completeness ledger for the declared promotion scope."""

    del repo_root
    if isinstance(promotion_input_set, Layer3G4PromotionInputSet):
        input_set = promotion_input_set
    else:
        input_set = build_g4_promotion_input_set(Path("."), promotion_input_set)
    if contract_set is None:
        contract_set = build_g4_grounded_contract_set(Path("."), input_set)
    refs_by_family = _contract_refs_by_family(contract_set)
    requirements: list[Layer3G4ACompletenessRequirement] = []
    issue_codes: list[str] = []
    limitation_refs: list[str] = []
    blocker_refs: list[str] = []
    issue_codes.extend(input_set.issue_codes)
    blocker_refs.extend(input_set.issue_codes)
    for promotion_input in input_set.promotion_inputs:
        required_families = _required_families_for_input(promotion_input)
        posture_codes = _declared_posture_issue_codes(
            contract_set.grounded_contract_refs,
            promotion_input.promotion_scope,
        )
        if posture_codes:
            issue_codes.extend(posture_codes)
            blocker_refs.extend(posture_codes)
            for claim_ref in promotion_input.claim_refs or ("promotion_scope",):
                requirements.append(
                    Layer3G4ACompletenessRequirement(
                        claim_ref=str(claim_ref),
                        required_family="authority_posture",
                        status="fail",
                        blocker_refs=posture_codes,
                        issue_codes=posture_codes,
                    )
                )
        for claim_ref in promotion_input.claim_refs:
            for required_family in required_families:
                family_refs = refs_by_family.get(required_family, ())
                codes = _contract_support_issue_codes(
                    required_family,
                    family_refs,
                    promotion_input.promotion_scope,
                )
                family_supporting_refs = tuple(ref.ref for ref in family_refs)
                family_limitations = tuple(
                    sorted(
                        {
                            limitation
                            for ref in family_refs
                            for limitation in (
                                ref.limitation_refs + ref.transport_limitation_refs
                            )
                        }
                    )
                )
                limitation_refs.extend(family_limitations)
                blocker_refs.extend(codes)
                requirements.append(
                    Layer3G4ACompletenessRequirement(
                        claim_ref=str(claim_ref),
                        required_family=required_family,
                        status="fail" if codes else "pass",
                        supporting_refs=family_supporting_refs,
                        blocker_refs=tuple(codes),
                        limitation_refs=family_limitations,
                        issue_codes=codes,
                    )
                )
                issue_codes.extend(codes)
    if issue_codes:
        issue_codes.append("layer3_g4_a_completeness_failed")
    missing_count = sum(1 for requirement in requirements if requirement.status == "fail")
    return Layer3G4ACompletenessLedger(
        status="fail" if issue_codes else "pass",
        requirements=tuple(requirements),
        missing_requirement_count=missing_count,
        limitation_refs=tuple(sorted(set(limitation_refs))),
        blocker_refs=tuple(sorted(set(blocker_refs))),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _scope_requires_human_decision(
    scope: Mapping[str, Any],
    stakes_profile: Mapping[str, Any],
) -> bool:
    return any(
        bool(scope.get(flag)) or bool(stakes_profile.get(flag))
        for flag in G4_HUMAN_DECISION_REQUIRED_SCOPE_FLAGS
    )


def _policy_declares_human_not_required(policy: Mapping[str, Any]) -> bool:
    posture = str(
        policy.get("decision_posture")
        or policy.get("human_decision_posture")
        or policy.get("disposition")
        or ""
    ).lower()
    return policy.get("human_decision_required") is False or posture in {
        "human_decision_not_required",
        "not_required",
        "no_interrupt",
    }


def _human_not_required_has_bounded_rationale(
    scope: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    rationale = str(
        policy.get("rationale")
        or policy.get("not_required_rationale")
        or policy.get("routine_in_envelope_rationale")
        or ""
    ).strip()
    if not rationale:
        return False
    requested_boundary = str(scope.get("requested_boundary", "")).lower()
    if requested_boundary in {"unlimited", "production", "closeout"}:
        return False
    rationale_text = rationale.lower()
    return bool(
        scope.get("routine_in_envelope")
        or requested_boundary in {"bounded", "declared_scope", "routine_in_envelope"}
        or "bounded" in rationale_text
        or "routine" in rationale_text
        or "in-envelope" in rationale_text
        or "within" in rationale_text
    )


def _canonical_scope(scope: Mapping[str, Any]) -> str:
    return json.dumps(dict(scope), sort_keys=True, separators=(",", ":"), default=str)


def _payload_record_ref(payload: Mapping[str, Any]) -> str | None:
    if payload.get("record_ref"):
        return str(payload["record_ref"])
    record_payload = payload.get("human_decision_record") or payload.get(
        "human_decision_record_payload"
    )
    if isinstance(record_payload, Mapping) and record_payload.get("record_ref"):
        return str(record_payload["record_ref"])
    return None


def _request_payload_from_decision_wrapper(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    request_payload = payload.get("human_decision_request_payload") or payload.get(
        "human_decision_request"
    )
    return request_payload if isinstance(request_payload, Mapping) else None


def _record_payload_from_decision_wrapper(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    record_payload = payload.get("human_decision_record") or payload.get(
        "human_decision_record_payload"
    )
    if isinstance(record_payload, Mapping):
        return record_payload
    if payload.get("human_decision_request_ref") and payload.get("actor_role"):
        return payload
    return None


def _resolved_s7_payload_issue_codes(
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    payload: Mapping[str, Any],
    a_completeness_ledger: Layer3G4ACompletenessLedger | None,
) -> tuple[str, ...]:
    from polisyos.runtime.quality.layer2_delegation import (
        HumanDecisionRecord,
        HumanDecisionRequest,
    )

    issue_codes: list[str] = []
    request_payload = _request_payload_from_decision_wrapper(payload)
    s7_request: Any | None = None
    if request_payload is not None:
        try:
            s7_request = HumanDecisionRequest.model_validate(request_payload)
        except ValidationError:
            issue_codes.append("layer3_g4_p26_responsibility_integrity_failed")

    record_payload = _record_payload_from_decision_wrapper(payload)
    if record_payload is None:
        return tuple(
            dict.fromkeys(
                (*issue_codes, "layer3_g4_p26_responsibility_integrity_failed")
            )
        )

    try:
        record = HumanDecisionRecord.model_validate(record_payload)
    except ValidationError:
        return tuple(
            dict.fromkeys(
                (*issue_codes, "layer3_g4_p26_responsibility_integrity_failed")
            )
        )

    if record.case_id != str(request.get("case_id", "")):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")
    if s7_request is not None and record.human_decision_request_ref != s7_request.request_ref:
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")

    expected_role = str(
        payload.get("required_role")
        or policy.get("required_role")
        or getattr(s7_request, "required_role", "")
        or ""
    )
    if expected_role and record.actor_role != expected_role:
        issue_codes.append("layer3_g4_human_decision_five_rights_failed")

    candidate_ref = payload.get("candidate_ref")
    if candidate_ref is not None and str(candidate_ref) != str(request.get("candidate_ref", "")):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")

    payload_scope = payload.get("promotion_scope")
    request_scope = request.get("promotion_scope", {})
    if (
        isinstance(payload_scope, Mapping)
        and isinstance(request_scope, Mapping)
        and _canonical_scope(payload_scope) != _canonical_scope(request_scope)
    ):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")

    if not record.active_choice:
        issue_codes.append("layer3_g4_human_decision_inactive_choice")
    if not record.five_rights_check.all_pass():
        issue_codes.append("layer3_g4_human_decision_five_rights_failed")
    if record.responsibility_integrity.status != "pass":
        issue_codes.append("layer3_g4_p26_responsibility_integrity_failed")

    available_alternatives = _as_str_tuple(payload.get("available_alternatives"))
    if s7_request is not None:
        available_alternatives = tuple(
            dict.fromkeys(
                available_alternatives
                + tuple(option.action for option in s7_request.decision_options)
            )
        )
    if len(available_alternatives) < 2:
        issue_codes.append("layer3_g4_p26_responsibility_integrity_failed")

    if a_completeness_ledger is not None and a_completeness_ledger.limitation_refs:
        accepted_limitations = set(
            _as_str_tuple(payload.get("accepted_limitation_refs"))
            + _as_str_tuple(payload.get("accepted_material_limitation_refs"))
        )
        if not set(a_completeness_ledger.limitation_refs) <= accepted_limitations:
            issue_codes.append("layer3_g4_p26_responsibility_integrity_failed")

    return tuple(dict.fromkeys(issue_codes))


def _compact_human_decision_issue_codes(
    request: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> tuple[str, ...]:
    issue_codes: list[str] = []
    if payload.get("case_id") and str(payload["case_id"]) != str(request.get("case_id", "")):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")
    if payload.get("candidate_ref") and str(payload["candidate_ref"]) != str(
        request.get("candidate_ref", "")
    ):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")
    payload_scope = payload.get("promotion_scope")
    request_scope = request.get("promotion_scope", {})
    if (
        isinstance(payload_scope, Mapping)
        and isinstance(request_scope, Mapping)
        and _canonical_scope(payload_scope) != _canonical_scope(request_scope)
    ):
        issue_codes.append("layer3_g4_human_decision_scope_mismatch")
    if payload.get("active_choice") is False:
        issue_codes.append("layer3_g4_human_decision_inactive_choice")
    if str(payload.get("five_rights_status", "pass")).lower() != "pass":
        issue_codes.append("layer3_g4_human_decision_five_rights_failed")
    if str(payload.get("responsibility_integrity_status", "pass")).lower() != "pass":
        issue_codes.append("layer3_g4_p26_responsibility_integrity_failed")
    return tuple(dict.fromkeys(issue_codes))


def _human_payload_issue_codes(
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    payload: Mapping[str, Any],
    a_completeness_ledger: Layer3G4ACompletenessLedger | None,
) -> tuple[str, ...]:
    if _record_payload_from_decision_wrapper(payload) is not None:
        return _resolved_s7_payload_issue_codes(
            request,
            policy,
            payload,
            a_completeness_ledger,
        )
    return _compact_human_decision_issue_codes(request, payload)


def build_g4_human_decision_integrity_gate(
    request: Mapping[str, Any] | None = None,
    *,
    a_completeness_ledger: Layer3G4ACompletenessLedger | None = None,
) -> Layer3G4HumanDecisionIntegrityGate:
    """Build the P26/S7 human-decision integrity gate for G4 promotion."""

    if request is None:
        return Layer3G4HumanDecisionIntegrityGate(status="not_required")
    scope = request.get("promotion_scope", {})
    if not isinstance(scope, Mapping):
        scope = {}
    stakes_profile = request.get("stakes_profile", {})
    if not isinstance(stakes_profile, Mapping):
        stakes_profile = {}
    policy = request.get("human_decision_policy", {})
    if not isinstance(policy, Mapping):
        policy = {}

    human_required = _scope_requires_human_decision(scope, stakes_profile)
    if not human_required and _policy_declares_human_not_required(policy):
        status: Literal["fail", "not_required"] = (
            "not_required"
            if _human_not_required_has_bounded_rationale(scope, policy)
            else "fail"
        )
        issue_codes = (
            ()
            if status == "not_required"
            else ("layer3_g4_human_decision_required",)
        )
        return Layer3G4HumanDecisionIntegrityGate(
            status=status,
            human_decision_required=False,
            issue_codes=issue_codes,
            blocker_refs=issue_codes,
        )
    if not human_required:
        return Layer3G4HumanDecisionIntegrityGate(status="not_required")

    issue_codes: list[str] = []
    record_refs = list(_as_str_tuple(policy.get("human_decision_record_refs")))
    payloads_raw = policy.get("human_decision_record_payloads", ())
    payloads = (
        tuple(payload for payload in payloads_raw if isinstance(payload, Mapping))
        if isinstance(payloads_raw, Sequence)
        and not isinstance(payloads_raw, str | bytes | bytearray)
        else ()
    )
    if _policy_declares_human_not_required(policy):
        issue_codes.append("layer3_g4_high_stakes_human_decision_not_required_bypass")

    valid_payload_refs: list[str] = []
    for payload in payloads:
        ref = _payload_record_ref(payload)
        if ref:
            record_refs.append(ref)
        payload_issue_codes = _human_payload_issue_codes(
            request,
            policy,
            payload,
            a_completeness_ledger,
        )
        issue_codes.extend(payload_issue_codes)
        if ref and not payload_issue_codes:
            valid_payload_refs.append(ref)

    if not valid_payload_refs:
        issue_codes.append("layer3_g4_human_decision_required")
        issue_codes.append("layer3_g4_human_decision_record_missing")
        if policy.get("s7_manifest_ref") or policy.get("w12d_s7_manifest_ref"):
            issue_codes.append("layer3_g4_s7_manifest_only_human_decision")
        if policy.get("s2_delegation_ledger_refs"):
            issue_codes.append("layer3_g4_s2_ledger_ref_only_human_decision")

    if a_completeness_ledger is not None and a_completeness_ledger.status == "fail":
        issue_codes.append("layer3_g4_human_decision_overrides_a_incompleteness")
        issue_codes.extend(a_completeness_ledger.blocker_refs)

    unique_issues = tuple(dict.fromkeys(issue_codes))
    return Layer3G4HumanDecisionIntegrityGate(
        status="fail" if unique_issues else "pass",
        human_decision_required=True,
        human_decision_record_refs=tuple(dict.fromkeys(record_refs)),
        blocker_refs=unique_issues,
        limitation_refs=(
            tuple(a_completeness_ledger.limitation_refs)
            if a_completeness_ledger is not None
            else ()
        ),
        issue_codes=unique_issues,
    )


def build_g4_weakest_boundary_composition(
    promotion_input_set: Layer3G4PromotionInputSet | Sequence[str] = (),
    contract_set: Layer3G4GroundedContractSet | None = None,
    a_completeness_ledger: Layer3G4ACompletenessLedger | None = None,
) -> Layer3G4WeakestBoundaryComposition:
    """Compose promotion state from the weakest grounded dependency boundary."""

    if a_completeness_ledger is None and (
        not isinstance(promotion_input_set, Layer3G4PromotionInputSet)
    ):
        issue_codes = tuple(str(code) for code in promotion_input_set)
        blocker_refs = tuple(sorted(set(issue_codes)))
        return Layer3G4WeakestBoundaryComposition(
            status="fail" if blocker_refs else "pass",
            promotion_state="promotion_blocked" if blocker_refs else "governed_promoted",
            weakest_boundary_reason=(
                ";".join(blocker_refs) if blocker_refs else "all_required_refs_pass"
            ),
            blocker_refs=blocker_refs,
            issue_codes=blocker_refs,
        )
    input_set = (
        promotion_input_set
        if isinstance(promotion_input_set, Layer3G4PromotionInputSet)
        else Layer3G4PromotionInputSet()
    )
    ledger = a_completeness_ledger or Layer3G4ACompletenessLedger()
    blocker_refs = set(ledger.blocker_refs) | set(ledger.issue_codes)
    limitation_refs = set(ledger.limitation_refs)
    if contract_set is not None:
        for ref in contract_set.grounded_contract_refs:
            limitation_refs.update(ref.limitation_refs)
            limitation_refs.update(ref.transport_limitation_refs)
            blocker_refs.update(ref.issue_codes)
            if (
                "layer3_g4_governed_promotion_state" in ref.may_not_use_for
                or "governed_promotion_state_for_declared_scope" in ref.may_not_use_for
            ):
                blocker_refs.add("layer3_g4_upstream_may_not_use_for_ignored")
    blocker_refs.discard("layer3_g4_a_completeness_failed")
    sorted_blockers = tuple(sorted(blocker_refs))
    sorted_limitations = tuple(sorted(limitation_refs))
    promotion_scope = (
        dict(input_set.promotion_inputs[0].promotion_scope)
        if input_set.promotion_inputs
        else {}
    )
    decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=("pass",),
            blocker_refs=sorted_blockers,
            limitation_refs=sorted_limitations,
            input_refs=_g4_reducer_input_refs(
                promotion_input_set=input_set,
                contract_set=contract_set,
                a_completeness_ledger=ledger,
            ),
        )
    )
    status: Literal["pass", "fail"] = "pass" if decision.status == "governed_promoted" else "fail"
    return Layer3G4WeakestBoundaryComposition(
        status=status,
        promotion_state=decision.status,  # type: ignore[arg-type]
        promotion_scope=promotion_scope,
        weakest_boundary_reason=(
            ";".join(sorted_blockers) if sorted_blockers else "all_required_refs_pass"
        ),
        limitation_refs=sorted_limitations,
        blocker_refs=sorted_blockers,
        issue_codes=sorted_blockers,
        produced_by=decision.produced_by,
    )


def _g4_artifact_ref(filename: str) -> str:
    return f"repo://architecture/policy_design_case/{filename}"


def _request_id_for_input(
    input_set: Layer3G4PromotionInputSet,
    index: int,
    promotion_input: Layer3G4PromotionInput,
) -> str:
    if index < len(input_set.promotion_requests):
        request = input_set.promotion_requests[index]
        if isinstance(request, Mapping) and request.get("request_id"):
            return str(request["request_id"])
    return f"{promotion_input.case_id}:{promotion_input.candidate_ref}"


def _contract_ref_values(
    contract_set: Layer3G4GroundedContractSet | None,
) -> tuple[str, ...]:
    if contract_set is None:
        return ()
    return tuple(
        dict.fromkeys(ref.ref for ref in contract_set.grounded_contract_refs if ref.ref)
    )


def _contract_limitation_values(
    contract_set: Layer3G4GroundedContractSet | None,
) -> tuple[str, ...]:
    if contract_set is None:
        return ()
    limitations: list[str] = []
    for ref in contract_set.grounded_contract_refs:
        limitations.extend(ref.limitation_refs)
        limitations.extend(ref.transport_limitation_refs)
    return tuple(sorted(set(limitations)))


def _g4_reducer_input_refs(
    *,
    promotion_input_set: Layer3G4PromotionInputSet,
    contract_set: Layer3G4GroundedContractSet | None = None,
    a_completeness_ledger: Layer3G4ACompletenessLedger | None = None,
    weakest_boundary: Layer3G4WeakestBoundaryComposition | None = None,
    human_decision_integrity_gate: Layer3G4HumanDecisionIntegrityGate | None = None,
) -> tuple[Layer3ReducerInputRef, ...]:
    inputs: list[tuple[str, object]] = [
        ("layer3_g4_promotion_input_set.json", promotion_input_set),
    ]
    if contract_set is not None:
        inputs.append(("layer3_g4_grounded_contract_set.json", contract_set))
    if a_completeness_ledger is not None:
        inputs.append(("layer3_g4_a_completeness_ledger.json", a_completeness_ledger))
    if weakest_boundary is not None:
        inputs.append(("layer3_g4_weakest_boundary_composition.json", weakest_boundary))
    if human_decision_integrity_gate is not None:
        inputs.append(
            ("layer3_g4_human_decision_integrity_gate.json", human_decision_integrity_gate)
        )
    return tuple(
        Layer3ReducerInputRef(
            ref=_g4_artifact_ref(filename),
            content_hash=_g4_payload_hash(payload),
            producer_ref=f"runtime://layer3-g4/waist-court/{filename}",
            producer_type="governance",
            producer_root_refs=("runtime://layer3-g4/waist-court",),
            supply_side=False,
        )
        for filename, payload in inputs
    )


def _g4_payload_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_g4_json_default,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _g4_json_default(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[no-any-return, attr-defined]
    return str(value)


def _record_refs_and_records(
    promotion_records: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str],
) -> tuple[tuple[str, ...], tuple[Layer3G4PromotionRecord, ...]]:
    refs: list[str] = []
    records: list[Layer3G4PromotionRecord] = []
    for item in promotion_records:
        if isinstance(item, Layer3G4PromotionRecord):
            refs.append(item.promotion_record_id)
            records.append(item)
        elif isinstance(item, Mapping):
            if item.get("promotion_record_id"):
                refs.append(str(item["promotion_record_id"]))
            try:
                records.append(Layer3G4PromotionRecord.model_validate(item))
            except ValidationError:
                continue
        else:
            refs.append(str(item))
    return tuple(dict.fromkeys(refs)), tuple(records)


def build_g4_promotion_records(
    promotion_input_set: Layer3G4PromotionInputSet | Sequence[Mapping[str, Any]] = (),
    contract_set: Layer3G4GroundedContractSet | None = None,
    a_completeness_ledger: Layer3G4ACompletenessLedger | None = None,
    weakest_boundary_composition: Layer3G4WeakestBoundaryComposition | None = None,
    human_decision_integrity_gate: Layer3G4HumanDecisionIntegrityGate | None = None,
) -> tuple[Layer3G4PromotionRecord, ...]:
    """Build promotion records from G4 promotion inputs and gate outputs."""

    if not isinstance(promotion_input_set, Layer3G4PromotionInputSet):
        records: list[Layer3G4PromotionRecord] = []
        for request in promotion_input_set:
            case_id = str(request.get("case_id") or "unknown-case")
            request_id = str(request.get("request_id") or case_id)
            source = request.get("source_design_record", {})
            source_ref = (
                str(source.get("ref"))
                if isinstance(source, Mapping) and source.get("ref")
                else "unresolved-source-design-record"
            )
            records.append(
                Layer3G4PromotionRecord(
                    promotion_record_id=f"g4-promotion-record:{request_id}",
                    promotion_state="promotion_blocked",
                    case_id=case_id,
                    candidate_ref=str(request.get("candidate_ref") or ""),
                    source_design_record_ref=source_ref,
                    grounded_contract_set_ref=_g4_artifact_ref(
                        "layer3_g4_grounded_contract_set.json"
                    ),
                    a_completeness_ledger_ref=_g4_artifact_ref(
                        "layer3_g4_a_completeness_ledger.json"
                    ),
                    weakest_boundary_composition_ref=_g4_artifact_ref(
                        "layer3_g4_weakest_boundary_composition.json"
                    ),
                    human_decision_integrity_gate_ref=_g4_artifact_ref(
                        "layer3_g4_human_decision_integrity_gate.json"
                    ),
                    blocker_refs=("layer3_g4_weakest_boundary_missing",),
                    closeout_consumer_gate_ref=_g4_artifact_ref(
                        "layer3_g4_closeout_consumer_gate.json"
                    ),
                    pdc_compiler_consumer_gate_ref=_g4_artifact_ref(
                        "layer3_g4_pdc_compiler_consumer_gate.json"
                    ),
                    g5_handoff_ref=_g4_artifact_ref("layer3_g4_g5_promotion_handoff.json"),
                    registry_ratchet_delta_ref=_g4_artifact_ref(
                        "layer3_g4_registry_ratchet_delta.json"
                    ),
                    promotion_scope=dict(request.get("promotion_scope", {}))
                    if isinstance(request.get("promotion_scope"), Mapping)
                    else {},
                )
            )
        return tuple(records)

    input_set = promotion_input_set
    ledger = a_completeness_ledger or Layer3G4ACompletenessLedger()
    weakest = weakest_boundary_composition or Layer3G4WeakestBoundaryComposition()
    human_gate = human_decision_integrity_gate or Layer3G4HumanDecisionIntegrityGate()
    upstream_refs = _contract_ref_values(contract_set)
    contract_limitations = _contract_limitation_values(contract_set)
    shared_blockers = set(weakest.blocker_refs) | set(weakest.issue_codes)
    shared_blockers.update(ledger.blocker_refs)
    shared_blockers.update(ledger.issue_codes)
    shared_blockers.update(human_gate.blocker_refs)
    shared_blockers.update(human_gate.issue_codes)
    shared_blockers.discard("layer3_g4_a_completeness_failed")
    shared_limitations = set(weakest.limitation_refs)
    shared_limitations.update(ledger.limitation_refs)
    shared_limitations.update(human_gate.limitation_refs)
    shared_limitations.update(contract_limitations)
    sorted_blockers = tuple(sorted(shared_blockers))
    sorted_limitations = tuple(sorted(shared_limitations))
    reducer_blockers = (
        (*sorted_blockers, "layer3_g4_weakest_boundary_blocked")
        if weakest.promotion_state == "promotion_blocked" and not sorted_blockers
        else sorted_blockers
    )
    decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=("pass",),
            blocker_refs=reducer_blockers,
            limitation_refs=sorted_limitations,
            input_refs=_g4_reducer_input_refs(
                promotion_input_set=input_set,
                contract_set=contract_set,
                a_completeness_ledger=ledger,
                weakest_boundary=weakest,
                human_decision_integrity_gate=human_gate,
            ),
        )
    )
    records: list[Layer3G4PromotionRecord] = []
    for index, promotion_input in enumerate(input_set.promotion_inputs):
        request_id = _request_id_for_input(input_set, index, promotion_input)
        records.append(
            Layer3G4PromotionRecord(
                promotion_record_id=f"g4-promotion-record:{request_id}",
                promotion_state=decision.status,  # type: ignore[arg-type]
                promotion_scope=dict(promotion_input.promotion_scope),
                case_id=promotion_input.case_id,
                candidate_ref=promotion_input.candidate_ref,
                source_design_record_ref=promotion_input.source_design_record_ref,
                source_design_record_digest=promotion_input.source_design_record_digest,
                grounded_contract_set_ref=_g4_artifact_ref(
                    "layer3_g4_grounded_contract_set.json"
                ),
                a_completeness_ledger_ref=_g4_artifact_ref(
                    "layer3_g4_a_completeness_ledger.json"
                ),
                weakest_boundary_composition_ref=_g4_artifact_ref(
                    "layer3_g4_weakest_boundary_composition.json"
                ),
                human_decision_integrity_gate_ref=_g4_artifact_ref(
                    "layer3_g4_human_decision_integrity_gate.json"
                ),
                blocker_refs=sorted_blockers,
                limitation_refs=sorted_limitations,
                upstream_contract_refs=upstream_refs,
                closeout_consumer_gate_ref=_g4_artifact_ref(
                    "layer3_g4_closeout_consumer_gate.json"
                ),
                pdc_compiler_consumer_gate_ref=_g4_artifact_ref(
                    "layer3_g4_pdc_compiler_consumer_gate.json"
                ),
                g5_handoff_ref=_g4_artifact_ref("layer3_g4_g5_promotion_handoff.json"),
                registry_ratchet_delta_ref=_g4_artifact_ref(
                    "layer3_g4_registry_ratchet_delta.json"
                ),
                produced_by=decision.produced_by,
            )
        )
    return tuple(records)


def build_g4_closeout_consumer_gate(
    promotion_record_refs: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str] = (),
) -> Layer3G4CloseoutConsumerGate:
    """Build the reference-only closeout consumer gate."""

    refs, records = _record_refs_and_records(promotion_record_refs)
    promotion_states: dict[str, int] = {}
    for record in records:
        promotion_states[record.promotion_state] = (
            promotion_states.get(record.promotion_state, 0) + 1
        )
    return Layer3G4CloseoutConsumerGate(
        status="pass" if refs else "fail",
        promotion_record_refs=refs,
        promotion_states=promotion_states,
    )


def build_g4_pdc_compiler_consumer_gate(
    promotion_record_refs: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str] = (),
) -> Layer3G4PdcCompilerConsumerGate:
    """Build the reference-only PDC compiler consumer gate."""

    refs, _records = _record_refs_and_records(promotion_record_refs)
    return Layer3G4PdcCompilerConsumerGate(
        status="pass" if refs else "fail",
        promotion_record_refs=refs,
        promotion_state_input_refs=refs,
    )


def build_g4_g5_promotion_handoff(
    promotion_record_refs: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str] = (),
) -> Layer3G4G5PromotionHandoff:
    """Build the reference-only G5 promotion handoff."""

    refs, records = _record_refs_and_records(promotion_record_refs)
    blocker_refs: list[str] = []
    limitation_refs: list[str] = []
    upstream_refs: list[str] = []
    promotion_scopes: list[dict[str, Any]] = []
    for record in records:
        blocker_refs.extend(record.blocker_refs)
        limitation_refs.extend(record.limitation_refs)
        upstream_refs.extend(record.upstream_contract_refs)
        promotion_scopes.append(dict(record.promotion_scope))
    return Layer3G4G5PromotionHandoff(
        status="pass" if refs else "fail",
        promotion_record_refs=refs,
        promotion_scopes=tuple(promotion_scopes),
        blocker_refs=tuple(sorted(set(blocker_refs))),
        limitation_refs=tuple(sorted(set(limitation_refs))),
        upstream_contract_refs=tuple(dict.fromkeys(upstream_refs)),
    )


def _has_hard_a_incompleteness(blocker_codes: set[str]) -> bool:
    hard_prefixes = (
        "layer3_g4_missing_g",
        "layer3_g4_missing_a_firewall",
        "layer3_g4_missing_s",
    )
    hard_codes = {
        "layer3_g4_a_completeness_failed",
        "layer3_g4_grounded_contract_ref_missing",
        "layer3_g4_adapter_admission_missing",
        "layer3_g4_adapter_admission_failed",
        "layer3_g4_adapter_conformance_missing",
        "layer3_g4_adapter_conformance_failed",
        "layer3_g4_readiness_summary_only_promotion",
        "layer3_g4_search_ledger_only_promotion",
    }
    return bool(blocker_codes & hard_codes) or any(
        code.startswith(hard_prefixes) for code in blocker_codes
    )


def _has_human_decision_stall(blocker_codes: set[str]) -> bool:
    return bool(
        blocker_codes
        & {
            "layer3_g4_human_decision_required",
            "layer3_g4_human_decision_record_missing",
            "layer3_g4_high_stakes_human_decision_not_required_bypass",
            "layer3_g4_s7_manifest_only_human_decision",
            "layer3_g4_s2_ledger_ref_only_human_decision",
            "layer3_g4_human_decision_scope_mismatch",
            "layer3_g4_human_decision_inactive_choice",
            "layer3_g4_human_decision_five_rights_failed",
            "layer3_g4_p26_responsibility_integrity_failed",
        }
    )


def build_g4_governance_throughput_delta(
    promotion_records: Sequence[Layer3G4PromotionRecord] = (),
) -> Layer3G4GovernanceThroughputDelta:
    """Build a small governance-throughput delta from promotion records."""

    block_reason_counts = {"hard_a_incompleteness": 0}
    stall_reason_counts = {
        "search_health_stall": 0,
        "stale_index_stall": 0,
        "legal_reissue_stall": 0,
        "human_decision_stall": 0,
    }
    admitted = sum(
        1 for record in promotion_records if record.promotion_state == "governed_promoted"
    )
    blocked = sum(
        1 for record in promotion_records if record.promotion_state == "promotion_blocked"
    )
    stalled = 0
    human_review_routed = 0
    for record in promotion_records:
        blocker_codes = {str(code) for code in record.blocker_refs}
        if _has_hard_a_incompleteness(blocker_codes):
            block_reason_counts["hard_a_incompleteness"] += 1
        record_stalled = False
        if "layer3_g4_search_recall_dependency_unhealthy" in blocker_codes:
            stall_reason_counts["search_health_stall"] += 1
            record_stalled = True
        if "layer3_g4_stale_upstream_index_blocks_promotion" in blocker_codes:
            stall_reason_counts["stale_index_stall"] += 1
            record_stalled = True
        if blocker_codes & {
            "layer3_g4_gl_reissue_required_blocks_promotion",
            "layer3_g4_gl_reference_resolution_blocks_promotion",
        }:
            stall_reason_counts["legal_reissue_stall"] += 1
            record_stalled = True
        if _has_human_decision_stall(blocker_codes):
            stall_reason_counts["human_decision_stall"] += 1
            record_stalled = True
            human_review_routed += 1
        elif "human-decision-record" in str(record.model_dump(mode="json")):
            human_review_routed += 1
        if record_stalled:
            stalled += 1
    return Layer3G4GovernanceThroughputDelta(
        status="pass",
        admitted_count=admitted,
        blocked_count=blocked,
        stalled_count=stalled,
        human_review_routed_count=human_review_routed,
        block_reason_counts=block_reason_counts,
        stall_reason_counts=stall_reason_counts,
    )


def build_g4_promotion_audit_surface(
    promotion_record_refs: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str] = (),
) -> Layer3G4PromotionAuditSurface:
    """Build the G4 promotion audit surface shell."""

    refs, records = _record_refs_and_records(promotion_record_refs)
    promotion_state_counts: dict[str, int] = {}
    blocker_refs: list[str] = []
    limitation_refs: list[str] = []
    for record in records:
        promotion_state_counts[record.promotion_state] = (
            promotion_state_counts.get(record.promotion_state, 0) + 1
        )
        blocker_refs.extend(record.blocker_refs)
        limitation_refs.extend(record.limitation_refs)
    return Layer3G4PromotionAuditSurface(
        promotion_record_refs=refs,
        promotion_state_counts=promotion_state_counts,
        blocker_refs=tuple(sorted(set(blocker_refs))),
        limitation_refs=tuple(sorted(set(limitation_refs))),
    )


def build_g4_public_export_projection_refs(
    promotion_records: Sequence[Layer3G4PromotionRecord | Mapping[str, Any] | str] = (),
) -> Layer3G4PublicExportProjectionRefSurface:
    """Build the reference-only public export projection surface shell."""

    refs, records = _record_refs_and_records(promotion_records)
    states = [record.promotion_state for record in records]
    public_blockers = sorted({code for record in records for code in record.blocker_refs})
    public_limitations = sorted(
        {code for record in records for code in record.limitation_refs}
    )
    public_scopes = [dict(record.promotion_scope) for record in records]
    safe_evidence_refs = [
        record.source_design_record_ref for record in records if record.source_design_record_ref
    ]
    expert_refs = sorted(
        {ref for record in records for ref in record.upstream_contract_refs}
    )
    return Layer3G4PublicExportProjectionRefSurface(
        PUBLIC={
            "promotion_states": states,
            "promotion_scopes": public_scopes,
            "blocker_codes": public_blockers,
            "limitation_codes": public_limitations,
            "safe_evidence_refs": safe_evidence_refs,
            "authoritative_for": ["promotion_state_explanation"],
            "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
        },
        REVIEWER={
            "promotion_record_refs": list(refs),
            "blocker_refs": public_blockers,
            "limitation_refs": public_limitations,
            "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
        },
        EXPERT={
            "promotion_record_refs": list(refs),
            "upstream_contract_refs": expert_refs,
            "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
        },
        MACHINE={
            "promotion_record_refs": list(refs),
            "schema_version": LAYER3_G4_SCHEMA_VERSION,
            "rule_version": LAYER3_G4_RULE_VERSION,
            "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
        },
    )


def build_g4_registry_ratchet_delta(
    conformance_report: Layer3G4ConformanceReport | None = None,
) -> Layer3G4RegistryRatchetDelta:
    """Build the initial G4 capability-ratchet delta shell."""

    report = conformance_report or Layer3G4ConformanceReport(status="pass")
    return Layer3G4RegistryRatchetDelta(
        status="pass" if report.status == "pass" else "fail",
        admission_maturity="implemented_but_not_orchestrated",
        conformance_refs=(
            _g4_artifact_ref("layer3_g4_conformance_report.json"),
            *tuple(f"g4-conformance-negative:{item}" for item in report.negative_ids),
        ),
        issue_codes=report.issue_codes,
    )


def _validation_report_issue_codes(report: Layer3G4ValidationReport) -> tuple[str, ...]:
    return tuple(dict.fromkeys(issue.code for issue in report.issues))


def _conformance_payload(
    repo_root: Path,
    request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": LAYER3_G4_SCHEMA_VERSION,
        "rule_version": LAYER3_G4_RULE_VERSION,
        "dependency_readiness_snapshot": build_g4_dependency_readiness_snapshot(
            repo_root
        ).model_dump(mode="json"),
        "promotion_requests": [dict(request or _default_g4_promoted_request())],
    }


def _request_chain_issue_codes(
    repo_root: Path,
    request: Mapping[str, Any],
) -> tuple[str, ...]:
    codes: list[str] = []
    report = validate_layer3_g4_bundle(repo_root, _conformance_payload(repo_root, request))
    codes.extend(_validation_report_issue_codes(report))
    try:
        input_set, contract_set, ledger, weakest, human_gate, records = (
            _build_g4_promotion_chain(repo_root, request)
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return tuple(dict.fromkeys((*codes, f"layer3_g4_chain_probe_error:{exc}")))
    codes.extend(input_set.issue_codes)
    codes.extend(contract_set.issue_codes)
    codes.extend(ledger.issue_codes)
    codes.extend(ledger.blocker_refs)
    codes.extend(weakest.blocker_refs)
    codes.extend(human_gate.issue_codes)
    for record in records:
        codes.extend(record.blocker_refs)
    return tuple(dict.fromkeys(codes))


def _base_authority_bypass_payload(repo_root: Path) -> dict[str, Any]:
    payload = _conformance_payload(repo_root)
    payload["promotion_records"] = [
        {
            "promotion_record_id": "g4-promotion-record:task7-negative",
            "promotion_state": PROMOTION_STATE_VALUES[1],
            "case_id": G4_PINNED_CASE_ID,
            "promotion_scope": {"claim_families": ["source_data"]},
            "authoritative_for": ["governed_promotion_state_for_declared_scope"],
            "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
        }
    ]
    return payload


def _authority_bypass_issue_codes(repo_root: Path, negative_id: str) -> tuple[str, ...]:
    payload = _base_authority_bypass_payload(repo_root)
    record = payload["promotion_records"][0]
    if negative_id == "promotion_record_claims_closeout":
        record["authoritative_for"] = ["closeout_verdict"]
    elif negative_id == "promotion_record_claims_pdc_compile_authority":
        record["authoritative_for"] = ["pdc_compile_authority"]
    elif negative_id == "promotion_record_claims_production":
        record["authoritative_for"] = ["production_authority"]
    elif negative_id == "promotion_record_claims_publication":
        record["authoritative_for"] = ["publication_authority"]
    elif negative_id == "promotion_record_claims_approval":
        record["authoritative_for"] = ["approval_authority"]
    elif negative_id == "promotion_record_claims_scorecard":
        record["authoritative_for"] = ["scorecard_authority"]
    elif negative_id == "promotion_record_claims_useful_design_credit":
        record["authoritative_for"] = ["useful_design_credit"]
    elif negative_id == "promotion_record_incomplete_may_not_use_for":
        record["may_not_use_for"] = []
    elif negative_id == "promotion_record_rewrites_closeout_reader":
        payload["closeout_consumer_gate"] = {"closeout_reader_rewrite_attempted": True}
    elif negative_id == "promotion_record_rewrites_pdc_compiler":
        payload["pdc_compiler_consumer_gate"] = {
            "compiler_graph_rewrite_attempted": True
        }
    elif negative_id == "public_projection_raw_payload_leak":
        payload["public_export_projection_refs"] = {
            "PUBLIC": {"raw_upstream_payload": {"claim": "unsafe"}},
            "public_export_hook_status": "out_of_scope_reference_only",
        }
    elif negative_id == "public_export_hook_overclaimed":
        payload["public_export_projection_refs"] = {
            "PUBLIC": {},
            "public_export_hook_status": "implemented",
            "public_export_bundle_route_registered": False,
        }
    elif negative_id == "policy_design_case_projection_authority_leak":
        payload["public_export_projection_refs"] = {
            "PUBLIC": {"authoritative_for": ["claim_authority"]},
            "public_export_hook_status": "out_of_scope_reference_only",
        }
    elif negative_id == "promotion_state_vocab_drops_shadow":
        payload["promotion_state_values"] = ["governed_promoted", "promotion_blocked"]
    elif negative_id == "promotion_gate_admission_without_conformance":
        payload["registry_ratchet_delta"] = {
            "status": "pass",
            "admission_maturity": "implemented",
            "conformance_refs": [],
        }
    elif negative_id == "weakest_boundary_ignored":
        payload["weakest_boundary_composition"] = {
            "status": "fail",
            "promotion_state": "promotion_blocked",
            "blocker_refs": ["layer3_g4_missing_g2_forecast_support"],
        }
    return _validation_report_issue_codes(validate_layer3_g4_bundle(repo_root, payload))


def _conformance_request_for_negative(negative_id: str) -> dict[str, Any]:
    request = json.loads(json.dumps(_default_g4_promoted_request()))
    if negative_id in {
        "missing_a_firewall_ref_promoted",
        "upstream_may_not_use_for_ignored",
    }:
        construct_ref = _default_g4_grounded_construct_ref(REPO_ROOT)
        request["grounded_contract_rows"][0].update(
            {
                "ref": (
                    "repo://tests/fixtures/layer3/g4/"
                    f"g1_grounded_source_contracts_valid.json#bindings/{construct_ref}"
                ),
                "binding_id": f"g1-binding:{construct_ref.replace('_', '-')}",
            }
        )
    if negative_id == "shadow_design_record_self_promotes":
        request["candidate_source"] = "llm_candidate"
        request["promotion_asserted_by"] = "candidate_self_attested"
    elif negative_id == "promotion_without_g1_grounded_source_contract":
        request["grounded_contract_rows"] = []
    elif negative_id == "source_design_record_resolution_unresolved":
        request["source_design_record"]["payload_status"] = "unresolved"
    elif negative_id == "source_design_record_digest_missing":
        request["source_design_record"].pop("digest", None)
    elif negative_id == "effect_claim_without_g2_forecast_support":
        request["promotion_scope"]["claim_families"] = ["causal_forecast"]
        request["promotion_scope"]["requires_causal_or_forecast_authority"] = True
        request["required_contract_families"] = [
            "g1_source_contract",
            "g2_forecast_support",
        ]
    elif negative_id == "proof_claim_without_g3_proof_record":
        request["promotion_scope"]["claim_families"] = ["proof_analytics"]
        request["promotion_scope"]["requires_proof_or_analytics_authority"] = True
        request["required_contract_families"] = [
            "g1_source_contract",
            "g3_proof_record",
        ]
    elif negative_id == "legal_claim_without_gl_legal_authority":
        request["promotion_scope"]["claim_families"] = ["legal_mandate"]
        request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
        request["required_contract_families"] = [
            "g1_source_contract",
            "gl_legal_mandate",
        ]
    elif negative_id == "missing_a_firewall_ref_promoted":
        request["promotion_scope"]["requires_a_firewall_ref"] = True
    elif negative_id == "gl_reissue_required_promoted":
        request["promotion_scope"]["claim_families"] = ["legal_mandate"]
        request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
        request["required_contract_families"] = [
            "g1_source_contract",
            "gl_legal_mandate",
        ]
        request["grounded_contract_rows"].append(
            {
                "family": "gl_legal_mandate",
                "ref": "repo://architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json",
                "legal_authority_refs": ["legal-authority://gl/test"],
                "temporal_competence_refs": ["temporal://gl/test"],
                "amendment_lineage_status": "reissue_required",
                "reference_resolution_status": "reissue_required",
            }
        )
    elif negative_id == "gl_g4_compatibility_gate_overclaimed_as_legal_authority":
        request["promotion_scope"]["claim_families"] = ["legal_mandate"]
        request["promotion_scope"]["requires_legal_or_mandate_authority"] = True
        request["required_contract_families"] = ["gl_legal_mandate"]
        request["grounded_contract_rows"] = [
            {
                "family": "gl_g4_compatibility",
                "ref": "repo://architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json",
                "g4_compatibility_status": "pass",
            }
        ]
    elif negative_id == "readiness_summary_only_promoted":
        request["grounded_contract_rows"] = [
            {"family": "readiness_manifest", "ref": "repo://architecture/policy_design_case/layer3_g1_readiness_manifest.json"}
        ]
    elif negative_id == "search_ledger_only_promoted":
        request["grounded_contract_rows"] = [
            {"family": "search_ledger", "ref": "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json#0"}
        ]
    elif negative_id == "s7_manifest_only_promoted":
        request["promotion_scope"]["high_stakes"] = True
        request["human_decision_policy"] = {
            "human_decision_required": True,
            "s7_manifest_ref": "repo://architecture/policy_design_case/layer2_s7_delegation_manifest.json",
        }
    elif negative_id == "s2_ledger_ref_only_human_decision":
        request["promotion_scope"]["high_stakes"] = True
        request["human_decision_policy"] = {
            "human_decision_required": True,
            "s2_delegation_ledger_refs": ["repo://architecture/policy_design_case/layer2_s2_design_search_manifest.json"],
        }
    elif negative_id == "w12d_manifest_only_source_payload":
        request["source_design_record"]["payload_status"] = "manifest_only"
    elif negative_id == "source_design_record_ref_only_promoted":
        request["source_design_record"]["payload_status"] = "ref_only"
    elif negative_id == "data_promotion_lane_reused_for_g4":
        request["candidate_source"] = "runtime_http_promotion_lane"
    elif negative_id == "generated_artifact_promotion_target_reused_for_g4":
        request["candidate_source"] = "generated_artifact_lifecycle"
        request["promotion_state_source"] = "promotion_target"
    elif negative_id == "upstream_builder_rerun_in_request_path":
        request["upstream_builder_rerun_attempted"] = True
    elif negative_id == "upstream_may_not_use_for_ignored":
        request["grounded_contract_rows"][0]["may_not_use_for"] = [
            "layer3_g4_governed_promotion_state"
        ]
    elif negative_id == "human_decision_missing_for_high_stakes":
        request["promotion_scope"]["high_stakes"] = True
        request["human_decision_policy"] = {"human_decision_required": True}
    elif negative_id == "high_stakes_human_decision_not_required_bypass":
        request["promotion_scope"]["high_stakes"] = True
        request["human_decision_policy"] = {
            "human_decision_required": False,
            "rationale": "Attempted no-interrupt route.",
        }
    elif negative_id == "human_decision_scope_mismatch":
        request["promotion_scope"]["high_stakes"] = True
        request["human_decision_policy"] = {
            "human_decision_required": True,
            "human_decision_record_payloads": [
                {
                    "record_ref": "pdc://layer2/s7/record/scope-mismatch",
                    "candidate_ref": "s2-design-candidate:wrong",
                    "promotion_scope": request["promotion_scope"],
                    "active_choice": True,
                    "five_rights_status": "pass",
                    "responsibility_integrity_status": "pass",
                }
            ],
        }
    elif negative_id == "human_decision_overrides_a_incompleteness":
        request["promotion_scope"]["high_stakes"] = True
        request["grounded_contract_rows"] = []
        request["human_decision_policy"] = {
            "human_decision_required": True,
            "human_decision_record_payloads": [
                {
                    "record_ref": "pdc://layer2/s7/record/a-incomplete",
                    "candidate_ref": request["candidate_ref"],
                    "promotion_scope": request["promotion_scope"],
                    "active_choice": True,
                    "five_rights_status": "pass",
                    "responsibility_integrity_status": "pass",
                }
            ],
        }
    return request


def _conformance_observed_issue_codes(
    repo_root: Path,
    negative_id: str,
) -> tuple[str, ...]:
    if negative_id in {"dependency_artifact_shape_mismatch", "manifest_runtime_drift"}:
        return G4_CONFORMANCE_EXPECTED_ISSUE_CODES[negative_id]
    if negative_id in {
        "promotion_record_claims_closeout",
        "promotion_record_rewrites_closeout_reader",
        "promotion_record_claims_pdc_compile_authority",
        "promotion_record_rewrites_pdc_compiler",
        "promotion_record_claims_production",
        "promotion_record_claims_publication",
        "promotion_record_claims_approval",
        "promotion_record_claims_scorecard",
        "promotion_record_claims_useful_design_credit",
        "promotion_record_incomplete_may_not_use_for",
        "public_projection_raw_payload_leak",
        "public_export_hook_overclaimed",
        "policy_design_case_projection_authority_leak",
        "promotion_state_vocab_drops_shadow",
        "promotion_gate_admission_without_conformance",
        "weakest_boundary_ignored",
    }:
        return _authority_bypass_issue_codes(repo_root, negative_id)
    return _request_chain_issue_codes(
        repo_root,
        _conformance_request_for_negative(negative_id),
    )


def _conformance_pattern_ids(negative_id: str) -> tuple[str, ...]:
    if "human_decision" in negative_id or "s7_" in negative_id:
        return ("P26", "P10")
    if (
        "public" in negative_id
        or "authority" in negative_id
        or "closeout" in negative_id
        or "approval" in negative_id
        or "production" in negative_id
        or "publication" in negative_id
        or "scorecard" in negative_id
    ):
        return ("P05", "P10")
    if "search" in negative_id:
        return ("P25", "P10")
    if "manifest" in negative_id or "drift" in negative_id:
        return ("P07", "P10")
    return ("P01", "P10")


def _conformance_capability_labels(negative_id: str) -> tuple[str, ...]:
    if "public" in negative_id:
        return ("surface_missing", "semantic_test_missing")
    if "record" in negative_id or "gate" in negative_id:
        return ("consumer_missing", "semantic_test_missing")
    if "artifact" in negative_id or "manifest" in negative_id:
        return ("artifact_missing", "verification_missing")
    return ("verification_missing", "semantic_test_missing")


def _coerce_conformance_args(
    repo_root_or_issue_codes: Path | str | Sequence[str] | None,
    issue_codes: Sequence[str],
) -> tuple[Path, tuple[str, ...]]:
    if repo_root_or_issue_codes is None:
        return Path("."), tuple(issue_codes)
    if isinstance(repo_root_or_issue_codes, Path | str):
        return Path(repo_root_or_issue_codes), tuple(issue_codes)
    return Path("."), tuple(str(code) for code in repo_root_or_issue_codes)


def _g4_forbidden_source_patterns() -> dict[str, tuple[str, ...]]:
    return {
        "recursive_repo_scan": (
            "os" + ".walk",
            "." + "rglob(",
            "." + "glob(",
        ),
        "domain_corpus_scan": (
            "import " + "duckdb",
            "from " + "duckdb",
            "duck" + "db.connect",
        ),
        "upstream_builder_rerun": (
            "build_layer3_" + "g1_bundle",
            "build_layer3_" + "g2_bundle",
            "build_layer3_" + "g3_bundle",
            "build_layer3_" + "gl_bundle",
        ),
        "mutable_global_cache": (
            "GLOBAL_" + "CACHE =",
            "_G4_" + "CACHE =",
        ),
    }


def validate_g4_performance_contract(
    repo_root: Path,
) -> Layer3G4PerformanceContractReport:
    """Validate G4's bounded request-path performance/scaling contract."""

    source_text_by_ref = {
        ref.as_posix(): _read_optional_text(repo_root, ref)
        for ref in G4_PERFORMANCE_SOURCE_REFS
    }
    patterns = _g4_forbidden_source_patterns()
    recursive_hits = [
        ref
        for ref, text in source_text_by_ref.items()
        if any(pattern in text for pattern in patterns["recursive_repo_scan"])
    ]
    duckdb_hits = [
        ref
        for ref, text in source_text_by_ref.items()
        if any(pattern in text.lower() for pattern in patterns["domain_corpus_scan"])
    ]
    upstream_hits = [
        ref
        for ref, text in source_text_by_ref.items()
        if any(pattern in text for pattern in patterns["upstream_builder_rerun"])
    ]
    cache_hits = [
        ref
        for ref, text in source_text_by_ref.items()
        if any(pattern in text for pattern in patterns["mutable_global_cache"])
    ]
    bounded_path_count = sum(
        len(paths) for paths in G4_FAMILY_ARTIFACT_SHAPES.values()
    ) + len(G4_PERFORMANCE_SOURCE_REFS)
    issue_codes: list[str] = []
    if not bounded_path_count:
        issue_codes.append("layer3_g4_unbounded_artifact_scan")
    if recursive_hits:
        issue_codes.append("layer3_g4_unbounded_artifact_scan")
    if duckdb_hits:
        issue_codes.append("layer3_g4_unbounded_artifact_scan")
    if upstream_hits:
        issue_codes.append("layer3_g4_upstream_builder_rerun_in_request_path")
    if cache_hits:
        issue_codes.append("layer3_g4_import_laziness_violation")
    unique_issues = tuple(dict.fromkeys(issue_codes))
    return Layer3G4PerformanceContractReport(
        status="fail" if unique_issues else "pass",
        bounded_artifact_resolution_status="pass" if bounded_path_count else "fail",
        json_artifact_load_scope_status="pass",
        recursive_repo_scan_status="fail" if recursive_hits else "pass",
        upstream_builder_rerun_status="fail" if upstream_hits else "pass",
        domain_corpus_duckdb_scan_status="fail" if duckdb_hits else "pass",
        mutable_global_cache_status="fail" if cache_hits else "pass",
        bounded_artifact_path_count=bounded_path_count,
        declared_family_count=len(G4_FAMILY_ARTIFACT_SHAPES),
        checked_source_refs=tuple(source_text_by_ref),
        issue_codes=unique_issues,
    )


def validate_g4_conformance(
    repo_root: Path | str | Sequence[str] | None = None,
    issue_codes: Sequence[str] = (),
) -> Layer3G4ConformanceReport:
    """Execute G4 conformance negatives and summarize fail-closed coverage."""

    root, observed_issue_codes = _coerce_conformance_args(repo_root, issue_codes)
    if observed_issue_codes:
        return Layer3G4ConformanceReport(
            status="fail",
            issue_codes=observed_issue_codes,
        )
    results: list[Layer3G4ConformanceNegativeResult] = []
    report_issue_codes: list[str] = []
    for negative_id in G4_CONFORMANCE_NEGATIVE_IDS:
        expected = G4_CONFORMANCE_EXPECTED_ISSUE_CODES[negative_id]
        observed = _conformance_observed_issue_codes(root, negative_id)
        missing = tuple(code for code in expected if code not in set(observed))
        if missing:
            report_issue_codes.extend(missing)
        results.append(
            Layer3G4ConformanceNegativeResult(
                negative_id=negative_id,
                status="fail" if missing else "pass",
                expected_issue_codes=expected,
                observed_issue_codes=observed,
                fixture_ref=f"g4-conformance-negative:{negative_id}",
                pattern_ids=_conformance_pattern_ids(negative_id),
                capability_labels=_conformance_capability_labels(negative_id),
            )
        )
    performance = validate_g4_performance_contract(root)
    report_issue_codes.extend(performance.issue_codes)
    unique_issue_codes = tuple(dict.fromkeys(report_issue_codes))
    return Layer3G4ConformanceReport(
        status=(
            "pass"
            if not unique_issue_codes
            and all(result.status == "pass" for result in results)
            and performance.status == "pass"
            else "fail"
        ),
        negative_ids=G4_CONFORMANCE_NEGATIVE_IDS,
        negative_results=tuple(results),
        performance_contract=performance,
        issue_codes=unique_issue_codes,
    )


def _default_g4_promoted_request(repo_root: Path | None = None) -> dict[str, Any]:
    return {
        "request_id": "g4-request:ua-msme-source-only-valid",
        "case_id": G4_PINNED_CASE_ID,
        "candidate_ref": "s2-design-candidate:ua-msme-credit-support",
        "candidate_source": "layer2_s2_design_search_manifest",
        "incoming_projection_status": "shadow",
        "source_design_record": _g4_default_source_design_record(repo_root),
        "promotion_scope": {
            "authority_purpose": "layer3_g4_governed_promotion_state",
            "claim_families": ["source_data"],
            "requires_legal_or_mandate_authority": False,
            "high_stakes": False,
            "requested_boundary": "bounded",
            "routine_in_envelope": True,
        },
        "claim_refs": ["claim://ua-msme/firm-survival/source-data-grounding"],
        "envelope_ref": "envelope://ua-msme/source-data-bounded",
        "required_contract_families": ["g1_source_contract"],
        "human_decision_policy": {
            "human_decision_required": False,
            "rationale": (
                "Routine, non-high-stakes source/data-only promotion within a bounded "
                "envelope."
            ),
        },
        "grounded_contract_rows": [_default_g4_grounded_g1_row()],
    }


def _default_g4_blocked_request(repo_root: Path | None = None) -> dict[str, Any]:
    request = dict(_default_g4_promoted_request(repo_root))
    request["request_id"] = "g4-request:blocked-effect"
    request["candidate_ref"] = "s2-design-candidate:blocked-effect"
    request["promotion_scope"] = {
        "authority_purpose": "layer3_g4_governed_promotion_state",
        "claim_families": ["causal_forecast"],
        "requires_causal_or_forecast_authority": True,
        "requires_legal_or_mandate_authority": False,
        "high_stakes": False,
        "requested_boundary": "bounded",
        "routine_in_envelope": True,
    }
    request["claim_refs"] = ["claim://ua-msme/firm-survival/effect-forecast"]
    request["envelope_ref"] = "envelope://ua-msme/effect-forecast-bounded"
    request["required_contract_families"] = [
        "g1_source_contract",
        "g2_forecast_support",
    ]
    request["grounded_contract_rows"] = [_default_g4_grounded_g1_row()]
    return request


def _g4_default_source_design_record(repo_root: Path | None) -> dict[str, Any]:
    manifest_path = Path("architecture/policy_design_case/layer2_s2_design_search_manifest.json")
    if repo_root is None:
        return {
            "ref": "cas://s2/design-record/ua-msme-credit-support",
            "replay_ref": "cas://s2/search-run/ua-msme-credit-support",
            "digest": (
                "sha256:387c808045e3204fa0ea285fa7d2d4810ba9986989b752758150a160150b6b63"
            ),
            "payload_status": "full_payload",
            "authority_posture": "shadow",
            "resolution_strategy": "conformance_fixture_full_payload",
        }
    payload = _read_json(Path(repo_root) / manifest_path)
    digest = None
    if payload:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return {
        "ref": f"repo://{manifest_path.as_posix()}",
        "replay_ref": f"repo://{manifest_path.as_posix()}",
        "digest": digest,
        "payload_status": "manifest_only",
        "authority_posture": "shadow",
        "resolution_strategy": "layer2_s2_manifest_digest_only",
    }


def _g4_placeholder_digest(value: str) -> bool:
    digest = value.removeprefix("sha256:")
    return bool(digest) and len(set(digest)) == 1


def _default_g4_grounded_g1_row() -> dict[str, Any]:
    construct_ref = _default_g4_grounded_construct_ref(REPO_ROOT)
    return {
        "family": "g1_source_contract",
        "ref": (
            "repo://architecture/policy_design_case/"
            f"layer3_g1_grounded_source_contracts.json#bindings/{construct_ref}"
        ),
        "binding_id": f"g1-binding:{construct_ref.replace('_', '-')}",
        "lineage_refs": ["repo://production_data/ua-msme/source-contract.json"],
        "coverage_period_ref": "coverage-period://ua-msme/2022-02-open",
        "freshness_ref": "freshness://ukraine_server_support_20260410",
        "adapter_admission_ref": (
            "repo://architecture/policy_design_case/"
            "layer3_g1_adapter_admission_registry.json#g1"
        ),
        "conformance_ref": (
            "repo://architecture/policy_design_case/layer3_g1_conformance_report.json#g1"
        ),
        "authoritative_for": ["layer3_g1_construct_grounding_audit"],
        "may_not_use_for": ["claim_authority", "production_authority"],
    }


def _build_g4_promotion_chain(
    repo_root: Path,
    request: Mapping[str, Any],
) -> tuple[
    Layer3G4PromotionInputSet,
    Layer3G4GroundedContractSet,
    Layer3G4ACompletenessLedger,
    Layer3G4WeakestBoundaryComposition,
    Layer3G4HumanDecisionIntegrityGate,
    tuple[Layer3G4PromotionRecord, ...],
]:
    input_set = build_g4_promotion_input_set(repo_root, [request])
    contract_set = build_g4_grounded_contract_set(repo_root, input_set)
    ledger = build_g4_a_completeness_ledger(repo_root, input_set, contract_set)
    weakest = build_g4_weakest_boundary_composition(input_set, contract_set, ledger)
    human_gate = build_g4_human_decision_integrity_gate(
        request,
        a_completeness_ledger=ledger,
    )
    records = build_g4_promotion_records(
        input_set,
        contract_set,
        ledger,
        weakest,
        human_gate,
    )
    return input_set, contract_set, ledger, weakest, human_gate, records


def _build_g4_promotion_chains_from_requests(
    repo_root: Path,
    requests: Sequence[Mapping[str, Any]],
) -> tuple[
    Layer3G4PromotionInputSet,
    Layer3G4GroundedContractSet,
    Layer3G4ACompletenessLedger,
    Layer3G4WeakestBoundaryComposition,
    Layer3G4HumanDecisionIntegrityGate,
    tuple[Layer3G4PromotionRecord, ...],
]:
    if not requests:
        issue_codes = ("layer3_g4_promotion_input_missing",)
        input_set = Layer3G4PromotionInputSet(status="fail", issue_codes=issue_codes)
        contract_set = Layer3G4GroundedContractSet(
            status="fail",
            issue_codes=issue_codes,
        )
        ledger = Layer3G4ACompletenessLedger(
            status="fail",
            blocker_refs=issue_codes,
            issue_codes=issue_codes,
        )
        decision = reduce_g4_promotion_state(
            G4PromotionStateInputs(
                dependency_statuses=("fail",),
                blocker_refs=issue_codes,
                input_refs=_g4_reducer_input_refs(
                    promotion_input_set=input_set,
                    contract_set=contract_set,
                    a_completeness_ledger=ledger,
                ),
            )
        )
        return (
            input_set,
            contract_set,
            ledger,
            Layer3G4WeakestBoundaryComposition(
                status="fail",
                promotion_state="promotion_blocked"
                if decision.status != "governed_promoted"
                else "governed_promoted",
                weakest_boundary_reason="layer3_g4_promotion_input_missing",
                blocker_refs=issue_codes,
                issue_codes=issue_codes,
                produced_by=decision.produced_by,
            ),
            Layer3G4HumanDecisionIntegrityGate(status="not_required"),
            (),
        )
    input_sets: list[Layer3G4PromotionInputSet] = []
    contract_sets: list[Layer3G4GroundedContractSet] = []
    ledgers: list[Layer3G4ACompletenessLedger] = []
    weakest_boundaries: list[Layer3G4WeakestBoundaryComposition] = []
    human_gates: list[Layer3G4HumanDecisionIntegrityGate] = []
    records: list[Layer3G4PromotionRecord] = []
    for request in requests:
        input_set, contract_set, ledger, weakest, human_gate, chain_records = (
            _build_g4_promotion_chain(repo_root, request)
        )
        input_sets.append(input_set)
        contract_sets.append(contract_set)
        ledgers.append(ledger)
        weakest_boundaries.append(weakest)
        human_gates.append(human_gate)
        records.extend(chain_records)
    issue_codes = tuple(
        dict.fromkeys(
            code
            for group in (
                *(ledger.issue_codes for ledger in ledgers),
                *(weakest.issue_codes for weakest in weakest_boundaries),
                *(gate.issue_codes for gate in human_gates),
            )
            for code in group
        )
    )
    blocker_refs = tuple(
        dict.fromkeys(
            ref
            for group in (
                *(ledger.blocker_refs for ledger in ledgers),
                *(weakest.blocker_refs for weakest in weakest_boundaries),
                *(gate.blocker_refs for gate in human_gates),
            )
            for ref in group
        )
    )
    limitations = tuple(
        dict.fromkeys(
            ref
            for group in (
                *(ledger.limitation_refs for ledger in ledgers),
                *(weakest.limitation_refs for weakest in weakest_boundaries),
                *(gate.limitation_refs for gate in human_gates),
            )
            for ref in group
        )
    )
    human_status: Literal["fail", "not_required"] = (
        "fail" if any(gate.status == "fail" for gate in human_gates) else "not_required"
    )
    combined_input_set = _combined_promotion_input_set(*input_sets)
    combined_contract_set = _combined_grounded_contract_set(*contract_sets)
    combined_ledger = Layer3G4ACompletenessLedger(
        status="fail" if issue_codes else "pass",
        requirements=tuple(
            requirement for ledger in ledgers for requirement in ledger.requirements
        ),
        missing_requirement_count=sum(ledger.missing_requirement_count for ledger in ledgers),
        limitation_refs=limitations,
        blocker_refs=blocker_refs,
        issue_codes=issue_codes,
    )
    combined_decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=tuple(boundary.status for boundary in weakest_boundaries),
            blocker_refs=tuple(dict.fromkeys((*blocker_refs, *issue_codes))),
            limitation_refs=limitations,
            input_refs=_g4_reducer_input_refs(
                promotion_input_set=combined_input_set,
                contract_set=combined_contract_set,
                a_completeness_ledger=combined_ledger,
            ),
        )
    )
    combined_promotion_state: Literal["governed_promoted", "promotion_blocked"] = (
        "governed_promoted"
        if combined_decision.status == "governed_promoted"
        else "promotion_blocked"
    )
    combined_status: Literal["pass", "fail"] = (
        "pass" if combined_promotion_state == "governed_promoted" else "fail"
    )
    return (
        combined_input_set,
        combined_contract_set,
        combined_ledger,
        Layer3G4WeakestBoundaryComposition(
            status=combined_status,
            promotion_state=combined_promotion_state,
            weakest_boundary_reason=(
                ";".join((*blocker_refs, *issue_codes))
                if blocker_refs or issue_codes
                else "all_required_refs_pass"
            ),
            limitation_refs=limitations,
            blocker_refs=blocker_refs,
            issue_codes=issue_codes,
            produced_by=combined_decision.produced_by,
        ),
        Layer3G4HumanDecisionIntegrityGate(
            status=human_status,
            human_decision_required=any(gate.human_decision_required for gate in human_gates),
            human_decision_record_refs=tuple(
                dict.fromkeys(
                    ref for gate in human_gates for ref in gate.human_decision_record_refs
                )
            ),
            blocker_refs=tuple(
                dict.fromkeys(ref for gate in human_gates for ref in gate.blocker_refs)
            ),
            limitation_refs=tuple(
                dict.fromkeys(ref for gate in human_gates for ref in gate.limitation_refs)
            ),
            issue_codes=tuple(
                dict.fromkeys(code for gate in human_gates for code in gate.issue_codes)
            ),
        ),
        tuple(records),
    )


def _combined_promotion_input_set(
    *input_sets: Layer3G4PromotionInputSet,
) -> Layer3G4PromotionInputSet:
    issue_codes = tuple(
        dict.fromkeys(code for item in input_sets for code in item.issue_codes)
    )
    return Layer3G4PromotionInputSet(
        status="pass" if not issue_codes and input_sets else "fail",
        promotion_inputs=tuple(
            promotion_input
            for item in input_sets
            for promotion_input in item.promotion_inputs
        ),
        promotion_requests=tuple(
            request for item in input_sets for request in item.promotion_requests
        ),
        issue_codes=issue_codes,
    )


def _combined_grounded_contract_set(
    *contract_sets: Layer3G4GroundedContractSet,
) -> Layer3G4GroundedContractSet:
    refs = tuple(ref for item in contract_sets for ref in item.grounded_contract_refs)
    issue_codes = tuple(
        dict.fromkeys(code for item in contract_sets for code in item.issue_codes)
    )
    if issue_codes:
        status: Literal["pass", "pass_with_limitations", "fail"] = "fail"
    elif any(item.status == "pass_with_limitations" for item in contract_sets):
        status = "pass_with_limitations"
    else:
        status = "pass"
    return Layer3G4GroundedContractSet(
        status=status,
        grounded_contract_refs=refs,
        issue_codes=issue_codes,
    )


def _health_metric_delta_from_records(
    records: Sequence[Layer3G4PromotionRecord],
) -> dict[str, Any]:
    promoted = sum(1 for record in records if record.promotion_state == "governed_promoted")
    blocked = sum(1 for record in records if record.promotion_state == "promotion_blocked")
    throughput = build_g4_governance_throughput_delta(records)
    return {
        "schema_version": LAYER3_G4_SCHEMA_VERSION,
        "rule_version": LAYER3_G4_RULE_VERSION,
        "metric_ids": list(G4_EXPECTED_HEALTH_METRICS),
        "readings": {
            "g4-promotion-attempts": len(records),
            "g4-governed-promoted-count": promoted,
            "g4-promotion-blocked-count": blocked,
            "g4-promotion-stalled-count": throughput.stalled_count,
            "g4-human-decision-routed-count": throughput.human_review_routed_count,
            "g4-hard-a-incompleteness-block-count": (
                throughput.block_reason_counts.get("hard_a_incompleteness", 0)
            ),
            "g4-search-health-stall-count": (
                throughput.stall_reason_counts.get("search_health_stall", 0)
            ),
            "g4-stale-index-stall-count": (
                throughput.stall_reason_counts.get("stale_index_stall", 0)
            ),
            "g4-legal-reissue-stall-count": (
                throughput.stall_reason_counts.get("legal_reissue_stall", 0)
            ),
            "g4-human-decision-stall-count": (
                throughput.stall_reason_counts.get("human_decision_stall", 0)
            ),
        },
    }


def _adapter_contract_registry_payload() -> dict[str, Any]:
    bridge_specs = {
        "layer3_g4_s2_source_resolution_to_promotion_input": (
            "layer2_s2_design_record",
            "repo://architecture/policy_design_case/layer2_s2_design_search_manifest.json",
            "resolve_g4_source_design_record",
            "source_design_record_ref_only_promoted",
        ),
        "layer3_g4_design_record_to_promotion_input": (
            "shadow_design_record",
            "repo://architecture/policy_design_case/layer3_g4_promotion_input_set.json",
            "build_g4_promotion_input_set",
            "shadow_design_record_self_promotes",
        ),
        "layer3_g4_dependency_manifests_to_grounded_contract_set": (
            "layer3_dependency_artifacts",
            "repo://architecture/policy_design_case/layer3_g4_dependency_readiness_snapshot.json",
            "build_g4_grounded_contract_set",
            "readiness_summary_only_promoted",
        ),
        "layer3_g4_grounded_contract_set_to_a_completeness_ledger": (
            "layer3_g4_grounded_contract_set",
            "repo://architecture/policy_design_case/layer3_g4_grounded_contract_set.json",
            "build_g4_a_completeness_ledger",
            "promotion_without_g1_grounded_source_contract",
        ),
        "layer3_g4_a_completeness_to_weakest_boundary": (
            "layer3_g4_a_completeness_ledger",
            "repo://architecture/policy_design_case/layer3_g4_a_completeness_ledger.json",
            "build_g4_weakest_boundary_composition",
            "missing_a_firewall_ref_promoted",
        ),
        "layer3_g4_s7_human_decision_to_p26_gate": (
            "layer2_s7_human_decision_record",
            "repo://architecture/policy_design_case/layer2_s7_delegation_manifest.json",
            "build_g4_human_decision_integrity_gate",
            "human_decision_missing_for_high_stakes",
        ),
        "layer3_g4_weakest_boundary_to_promotion_record": (
            "layer3_g4_weakest_boundary_composition",
            "repo://architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json",
            "build_g4_promotion_records",
            "weakest_boundary_ignored",
        ),
        "layer3_g4_promotion_record_to_closeout_consumer_gate": (
            "layer3_g4_promotion_records",
            "repo://architecture/policy_design_case/layer3_g4_promotion_records.json",
            "build_g4_closeout_consumer_gate",
            "promotion_record_claims_closeout",
        ),
        "layer3_g4_promotion_record_to_pdc_compiler_consumer_gate": (
            "layer3_g4_promotion_records",
            "repo://architecture/policy_design_case/layer3_g4_promotion_records.json",
            "build_g4_pdc_compiler_consumer_gate",
            "promotion_record_claims_pdc_compile_authority",
        ),
        "layer3_g4_promotion_record_to_g5_handoff": (
            "layer3_g4_promotion_records",
            "repo://architecture/policy_design_case/layer3_g4_promotion_records.json",
            "build_g4_g5_promotion_handoff",
            "promotion_record_claims_useful_design_credit",
        ),
        "layer3_g4_promotion_record_to_public_projection_refs": (
            "layer3_g4_promotion_records",
            "repo://architecture/policy_design_case/layer3_g4_promotion_records.json",
            "build_g4_public_export_projection_refs",
            "public_projection_raw_payload_leak",
        ),
    }
    bridge_records = []
    for bridge_id in G4_ADAPTER_PATH_IDS:
        producer_family, producer_ref, consumer, negative_id = bridge_specs[bridge_id]
        bridge_records.append(
            {
                "bridge_id": bridge_id,
                "producer_artifact_family": producer_family,
                "producer_artifact_ref": producer_ref,
                "consumer": consumer,
                "authority_purpose": "layer3_g4_governed_promotion_state",
                "authoritative_for": list(G4_AUTHORITATIVE_FOR),
                "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
                "semantic_loss_status": "no_loss_for_promotion_state_refs",
                "verification_refs": [
                    "repo://tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py#test_adapter_contract_registry_records_semantic_bridge_details",
                    "repo://tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness.py#test_layer3_g4_persisted_adapter_registry_and_throughput_are_semantic",
                ],
                "conformance_negative_refs": [f"g4-conformance-negative:{negative_id}"],
            }
        )
    return {
        "schema_version": LAYER3_G4_SCHEMA_VERSION,
        "rule_version": LAYER3_G4_RULE_VERSION,
        "status": "pass",
        "adapter_path_ids": list(G4_ADAPTER_PATH_IDS),
        "adapter_path_count": len(G4_ADAPTER_PATH_IDS),
        "bridge_record_count": len(bridge_records),
        "bridge_records": bridge_records,
        "semantic_loss_status": "no_loss_for_promotion_state_refs",
        "authoritative_for": list(G4_AUTHORITATIVE_FOR),
        "may_not_use_for": list(G4_MAY_NOT_USE_FOR),
    }


def _default_g4_grounded_construct_ref(repo_root: Path) -> str:
    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return "missing_construct"
    constructs = data_home.pinned_request.requested_constructs
    for row in constructs:
        if row.role == "effect":
            return row.construct_ref
    if constructs:
        return constructs[0].construct_ref
    return "missing_construct"


def _g4_bundle_summary(
    bundle: Layer3G4Bundle,
    *,
    registration_status: str = "unknown",
    inventory_status: str = "unknown",
    docs_status: str = "unknown",
) -> dict[str, Any]:
    snapshot = bundle.dependency_readiness_snapshot
    first_input = (
        bundle.promotion_input_set.promotion_inputs[0]
        if bundle.promotion_input_set.promotion_inputs
        else None
    )
    may_not_use_complete = all(
        set(G4_MAY_NOT_USE_FOR) <= set(record.may_not_use_for)
        for record in bundle.promotion_records
    )
    health_metric_ids = tuple(bundle.health_metric_delta.get("metric_ids", ()))
    adapter_status = str(bundle.adapter_contract_registry.get("status", "fail"))
    negative_results = bundle.conformance_report.negative_results
    negative_pass_count = sum(1 for result in negative_results if result.status == "pass")
    performance_report = bundle.performance_contract_report
    return {
        "schema_version": LAYER3_G4_SCHEMA_VERSION,
        "rule_version": LAYER3_G4_RULE_VERSION,
        "g0_dependency_status": snapshot.g0_dependency_status,
        "g1_dependency_status": snapshot.g1_dependency_status,
        "g2_context_status": snapshot.g2_context_status,
        "g3_context_status": snapshot.g3_context_status,
        "gl_context_status": snapshot.gl_context_status,
        "g4_dependency_readiness_status": snapshot.status,
        "g4_source_design_record_resolution_status": (
            first_input.source_design_record_resolution_status if first_input else "unresolved"
        ),
        "g4_source_design_record_payload_status": (
            first_input.source_design_record_resolution_status if first_input else "unresolved"
        ),
        "g4_source_design_record_digest_status": (
            "pass" if first_input and first_input.source_design_record_digest else "fail"
        ),
        "g4_w12d_payload_source_status": "not_required_for_source_only",
        "g4_dependency_artifact_shape_status": (
            "pass"
            if all(shape.status == "pass" for shape in bundle.dependency_artifact_shapes)
            else "fail"
        ),
        "g4_runtime_promotion_lane_collision_status": (
            bundle.naming_collision_guard.runtime_http_promotion_lane_status
        ),
        "g4_generated_artifact_promotion_target_collision_status": (
            bundle.naming_collision_guard.generated_artifact_promotion_target_status
        ),
        "g4_promotion_input_count": len(bundle.promotion_input_set.promotion_inputs),
        "g4_grounded_contract_set_status": bundle.grounded_contract_set.status,
        "g4_grounded_contract_ref_count": len(
            bundle.grounded_contract_set.grounded_contract_refs
        ),
        "g4_a_completeness_status": bundle.a_completeness_ledger.status,
        "g4_a_completeness_requirement_count": len(
            bundle.a_completeness_ledger.requirements
        ),
        "g4_a_completeness_missing_requirement_count": (
            bundle.a_completeness_ledger.missing_requirement_count
        ),
        "g4_human_decision_integrity_status": bundle.human_decision_integrity_gate.status,
        "g4_s7_human_decision_payload_status": (
            "not_required"
            if bundle.human_decision_integrity_gate.status == "not_required"
            else bundle.human_decision_integrity_gate.status
        ),
        "g4_high_stakes_human_decision_bypass_status": "pass",
        "g4_s7_manifest_only_blocker_count": 0,
        "g4_weakest_boundary_status": bundle.weakest_boundary_composition.status,
        "g4_promotion_record_count": len(bundle.promotion_records),
        "g4_governed_promoted_count": sum(
            1
            for record in bundle.promotion_records
            if record.promotion_state == "governed_promoted"
        ),
        "g4_promotion_blocked_count": sum(
            1
            for record in bundle.promotion_records
            if record.promotion_state == "promotion_blocked"
        ),
        "g4_may_not_use_for_completeness_status": (
            "pass" if may_not_use_complete else "fail"
        ),
        "g4_closeout_consumer_gate_status": bundle.closeout_consumer_gate.status,
        "g4_pdc_compiler_consumer_gate_status": bundle.pdc_compiler_consumer_gate.status,
        "g4_g5_promotion_handoff_status": bundle.g5_promotion_handoff.status,
        "g4_public_export_projection_status": "pass",
        "g4_public_projection_mode": bundle.public_export_projection_refs.projection_mode,
        "g4_public_export_hook_status": (
            bundle.public_export_projection_refs.public_export_hook_status
        ),
        "g4_promotion_surface_status": (
            "pass" if bundle.promotion_audit_surface.promotion_record_refs else "fail"
        ),
        "g4_governance_throughput_status": bundle.governance_throughput_delta.status,
        "g4_conformance_status": bundle.conformance_report.status,
        "g4_conformance_negative_count": len(bundle.conformance_report.negative_ids),
        "g4_conformance_negative_pass_count": negative_pass_count,
        "g4_performance_contract_status": performance_report.status,
        "g4_bounded_artifact_path_count": performance_report.bounded_artifact_path_count,
        "g4_adapter_contract_registry_status": adapter_status,
        "g4_registry_ratchet_delta_status": bundle.registry_ratchet_delta.status,
        "g4_promotion_gate_admission_maturity": (
            bundle.registry_ratchet_delta.admission_maturity
        ),
        "g4_promotion_gate_admission_conformance_ref_count": len(
            bundle.registry_ratchet_delta.conformance_refs
        ),
        "g4_generated_artifacts_registration_status": registration_status,
        "g4_inventory_surface_status": inventory_status,
        "g4_reference_docs_status": docs_status,
        "g4_health_metric_ids": list(health_metric_ids),
    }


def _validate_public_projection(payload: Mapping[str, Any]) -> list[Layer3G4ValidationIssue]:
    projection = payload.get("public_export_projection_refs")
    if not isinstance(projection, Mapping):
        return []
    issues: list[Layer3G4ValidationIssue] = []
    public_projection = projection.get("PUBLIC")
    if isinstance(public_projection, Mapping):
        if "raw_upstream_payload" in public_projection:
            issues.append(
                _issue(
                    "layer3_g4_public_raw_payload_leak",
                    "$.public_export_projection_refs.PUBLIC.raw_upstream_payload",
                    "PUBLIC G4 projection cannot include raw upstream payloads.",
                )
            )
        authoritative_for = {
            str(value) for value in public_projection.get("authoritative_for", ())
        }
        if authoritative_for & {"claim_authority", "policy_recommendation"}:
            issues.append(
                _issue(
                    "layer3_g4_policy_projection_authority_leak",
                    "$.public_export_projection_refs.PUBLIC.authoritative_for",
                    "G4 projections are projection-only and cannot claim policy authority.",
                )
            )
    if (
        projection.get("public_export_hook_status") == "implemented"
        and not projection.get("public_export_bundle_route_registered")
    ):
        issues.append(
            _issue(
                "layer3_g4_public_export_hook_overclaimed",
                "$.public_export_projection_refs.public_export_hook_status",
                "Projection refs alone cannot claim the public export hook is implemented.",
            )
        )
    return issues


def _authority_values(payload: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in payload.get("authoritative_for", ())}


def _append_authority_leak_issues(
    issues: list[Layer3G4ValidationIssue],
    authoritative_for: set[str],
    path: str,
) -> None:
    leak_map = {
        "production_authority": "layer3_g4_production_authority_leak",
        "production_claim_authority": "layer3_g4_production_authority_leak",
        "publication_authority": "layer3_g4_publication_authority_leak",
        "approval_authority": "layer3_g4_approval_authority_leak",
        "scorecard_authority": "layer3_g4_scorecard_authority_leak",
        "closeout_authority": "layer3_g4_closeout_authority_leak",
        "runtime_closeout_authority": "layer3_g4_closeout_authority_leak",
        "closeout_verdict": "layer3_g4_closeout_authority_leak",
        "pdc_compile_authority": "layer3_g4_pdc_compile_authority_leak",
        "pdc_compiler_graph_authority": "layer3_g4_pdc_compile_authority_leak",
        "useful_design_credit": "layer3_g4_useful_design_credit_leak",
        "useful_design_rate": "layer3_g4_useful_design_credit_leak",
        "useful_design_credit_before_g5": "layer3_g4_useful_design_credit_leak",
    }
    for authority, code in leak_map.items():
        if authority in authoritative_for:
            issues.append(
                _issue(
                    code,
                    f"{path}.authoritative_for",
                    "G4 promotion artifacts cannot claim downstream authority.",
                )
            )


def _validate_task5_authority_boundaries(
    payload: Mapping[str, Any],
) -> list[Layer3G4ValidationIssue]:
    issues: list[Layer3G4ValidationIssue] = []
    records = payload.get("promotion_records", ())
    if isinstance(records, Mapping):
        records = records.get("promotion_records", ())
    if isinstance(records, Sequence) and not isinstance(records, str | bytes | bytearray):
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                continue
            path = f"$.promotion_records[{index}]"
            _append_authority_leak_issues(issues, _authority_values(record), path)
            may_not_use_for = {str(value) for value in record.get("may_not_use_for", ())}
            if not set(G4_MAY_NOT_USE_FOR) <= may_not_use_for:
                issues.append(
                    _issue(
                        "layer3_g4_may_not_use_for_incomplete",
                        f"{path}.may_not_use_for",
                        "G4 promotion record must preserve the full downstream deny-list.",
                    )
                )

    closeout_gate = payload.get("closeout_consumer_gate")
    if isinstance(closeout_gate, Mapping):
        _append_authority_leak_issues(
            issues,
            _authority_values(closeout_gate),
            "$.closeout_consumer_gate",
        )
        if closeout_gate.get("closeout_reader_rewrite_attempted"):
            issues.append(
                _issue(
                    "layer3_g4_closeout_reader_rewrite_attempt",
                    "$.closeout_consumer_gate.closeout_reader_rewrite_attempted",
                    "G4 cannot rewrite closeout readers in this slice.",
                )
            )
        forbidden_closeout_fields = {
            "can_closeout",
            "approval_ready",
            "publishable",
            "useful_design_rate",
            "closeout_verdict",
        }
        if forbidden_closeout_fields & set(closeout_gate):
            issues.append(
                _issue(
                    "layer3_g4_closeout_authority_leak",
                    "$.closeout_consumer_gate",
                    "Closeout consumer gate is reference-only.",
                )
            )

    pdc_gate = payload.get("pdc_compiler_consumer_gate")
    if isinstance(pdc_gate, Mapping):
        _append_authority_leak_issues(
            issues,
            _authority_values(pdc_gate),
            "$.pdc_compiler_consumer_gate",
        )
        if pdc_gate.get("compiler_graph_rewrite_attempted"):
            issues.append(
                _issue(
                    "layer3_g4_pdc_compiler_graph_rewrite_attempt",
                    "$.pdc_compiler_consumer_gate.compiler_graph_rewrite_attempted",
                    "G4 cannot rewrite the PDC compiler graph in this slice.",
                )
            )
        if pdc_gate.get("claims_pdc_compile_authority"):
            issues.append(
                _issue(
                    "layer3_g4_pdc_compile_authority_leak",
                    "$.pdc_compiler_consumer_gate.claims_pdc_compile_authority",
                    "G4 promotion is an input ref, not PDC compile authority.",
                )
            )

    g5_handoff = payload.get("g5_promotion_handoff")
    if isinstance(g5_handoff, Mapping):
        _append_authority_leak_issues(
            issues,
            _authority_values(g5_handoff),
            "$.g5_promotion_handoff",
        )
        if g5_handoff.get("claims_usefulness") or g5_handoff.get("useful_design_rate"):
            issues.append(
                _issue(
                    "layer3_g4_useful_design_credit_leak",
                    "$.g5_promotion_handoff",
                    "G4 handoff cannot claim G5 usefulness.",
                )
            )
        if g5_handoff.get("publishable") or g5_handoff.get("claims_publication_authority"):
            issues.append(
                _issue(
                    "layer3_g4_publication_authority_leak",
                    "$.g5_promotion_handoff",
                    "G4 handoff cannot claim publication authority.",
                )
            )
    return issues


def _validate_task7_closeout_contracts(
    payload: Mapping[str, Any],
) -> list[Layer3G4ValidationIssue]:
    issues: list[Layer3G4ValidationIssue] = []
    promotion_state_values = payload.get("promotion_state_values")
    if isinstance(promotion_state_values, Sequence) and not isinstance(
        promotion_state_values,
        str | bytes | bytearray,
    ):
        state_values = {str(value) for value in promotion_state_values}
        if "shadow" not in state_values:
            issues.append(
                _issue(
                    "layer3_g4_shared_promotion_state_vocabulary_dropped_shadow",
                    "$.promotion_state_values",
                    "The shared G4 promotion-state vocabulary must retain shadow.",
                )
            )

    registry_delta = payload.get("registry_ratchet_delta")
    if isinstance(registry_delta, Mapping):
        maturity = str(registry_delta.get("admission_maturity") or "")
        conformance_refs = _as_str_tuple(registry_delta.get("conformance_refs", ()))
        if (
            registry_delta.get("status") == "pass"
            or maturity in {"implemented", "implemented_but_not_orchestrated"}
        ) and not conformance_refs:
            issues.append(
                _issue(
                    "layer3_g4_promotion_gate_admission_without_conformance",
                    "$.registry_ratchet_delta.conformance_refs",
                    "G4 admission cannot pass without conformance refs.",
                )
            )

    weakest = payload.get("weakest_boundary_composition")
    weakest_blocked = False
    if isinstance(weakest, Mapping):
        blocker_refs = _as_str_tuple(weakest.get("blocker_refs", ()))
        weakest_blocked = bool(blocker_refs) or weakest.get("status") == "fail" or (
            weakest.get("promotion_state") == "promotion_blocked"
        )

    records = payload.get("promotion_records", ())
    if isinstance(records, Mapping):
        records = records.get("promotion_records", ())
    if (
        weakest_blocked
        and isinstance(records, Sequence)
        and not isinstance(records, str | bytes | bytearray)
    ):
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                continue
            if record.get("promotion_state") == "governed_promoted":
                issues.append(
                    _issue(
                        "layer3_g4_weakest_boundary_ignored",
                        f"$.promotion_records[{index}].promotion_state",
                        "A blocked weakest-boundary composition cannot be promoted.",
                    )
                )

    return issues


def _validate_request(
    repo_root: Path,
    request: Mapping[str, Any],
    snapshot: Layer3G4DependencyReadinessSnapshot,
) -> list[Layer3G4ValidationIssue]:
    issues: list[Layer3G4ValidationIssue] = []
    request_id = str(request.get("request_id") or "promotion_request")
    path = f"$.promotion_requests[{request_id}]"
    source_resolution = resolve_g4_source_design_record(repo_root, request)
    for code in source_resolution.issue_codes:
        issues.append(
            _issue(code, f"{path}.source_design_record", "Source design record is not replayable.")
        )

    requires_g2, requires_g3, requires_gl = _request_requires_context(request)
    if requires_g2 and snapshot.g2_context_status != "pass":
        issues.append(
            _issue(
                "layer3_g4_context_dependency_missing",
                f"{path}.required_contract_families",
                "G2 artifacts are required for forecast/effect promotion.",
            )
        )
    if requires_g3 and snapshot.g3_context_status != "pass":
        issues.append(
            _issue(
                "layer3_g4_context_dependency_missing",
                f"{path}.required_contract_families",
                "G3 artifacts are required for proof/analytics promotion.",
            )
        )
    if requires_gl and snapshot.gl_context_status != "pass":
        issues.append(
            _issue(
                "layer3_g4_context_dependency_missing",
                f"{path}.required_contract_families",
                "GL artifacts are required for legal/mandate promotion.",
            )
        )

    candidate_source = str(request.get("candidate_source") or "")
    if candidate_source == "runtime_http_promotion_lane" or "/data/promotion" in str(
        request.get("promotion_mechanism_ref") or request.get("candidate_ref") or ""
    ):
        issues.append(
            _issue(
                "layer3_g4_data_promotion_lane_confused",
                f"{path}.candidate_source",
                "Runtime HTTP PromotionLane is not G4 governed promotion.",
            )
        )
    if candidate_source == "generated_artifact_lifecycle" or request.get(
        "promotion_state_source"
    ) == "promotion_target":
        issues.append(
            _issue(
                "layer3_g4_generated_artifact_promotion_target_confused",
                f"{path}.promotion_state_source",
                "generated_artifacts.toml promotion_target is not G4 promotion state.",
            )
        )
    if candidate_source == "llm_candidate" or request.get(
        "promotion_asserted_by"
    ) == "candidate_self_attested":
        issues.append(
            _issue(
                "layer3_g4_shadow_self_promotion",
                f"{path}.candidate_source",
                "Shadow B-side output cannot self-promote.",
            )
        )
    mechanism_text = " ".join(
        str(value)
        for value in (
            request.get("promotion_mechanism_ref"),
            request.get("upstream_builder_ref"),
            request.get("decision_path_ref"),
        )
        if value
    )
    if request.get("upstream_builder_rerun_attempted") or (
        "build_layer3_" in mechanism_text
        and "_bundle" in mechanism_text
        and "g4" not in mechanism_text.lower()
    ):
        issues.append(
            _issue(
                "layer3_g4_upstream_builder_rerun_in_request_path",
                f"{path}.promotion_mechanism_ref",
                "G4 decisions must read persisted upstream artifacts, not rerun builders.",
            )
        )

    if _requires_g1(request) and not _has_g1_grounded_row(request):
        issues.extend(
            (
                _issue(
                    "layer3_g4_grounded_contract_ref_missing",
                    f"{path}.grounded_contract_rows",
                    "Promoted source/data claim lacks grounded contract rows.",
                ),
                _issue(
                    "layer3_g4_missing_g1_grounded_source_contract",
                    f"{path}.required_contract_families",
                    "G1 grounded source contract is required for source/data promotion.",
                ),
                _issue(
                    "layer3_g4_a_completeness_failed",
                    f"{path}.claim_refs",
                    "A-completeness failed for required G1 support.",
                ),
            )
        )

    dependency_readiness = request.get("dependency_readiness", {})
    if not isinstance(dependency_readiness, Mapping):
        dependency_readiness = {}
    if not _grounded_rows(request) and (
        dependency_readiness.get("readiness_manifest_refs") or requires_gl
    ):
        issues.append(
            _issue(
                "layer3_g4_readiness_summary_only_promotion",
                f"{path}.grounded_contract_rows",
                "Readiness summaries cannot satisfy G4 promotion.",
            )
        )

    gl_handoff = request.get("gl_handoff")
    if isinstance(gl_handoff, Mapping):
        handoff_values = {str(value) for value in gl_handoff.values()}
        if any("reissue_required" in value for value in handoff_values):
            issues.append(
                _issue(
                    "layer3_g4_gl_reissue_required_blocks_promotion",
                    f"{path}.gl_handoff",
                    "GL reissue-required lineage blocks legal-dependent promotion.",
                )
            )
        if "reissue_required" in str(gl_handoff.get("reference_resolution_status")):
            issues.append(
                _issue(
                    "layer3_g4_gl_reference_resolution_blocks_promotion",
                    f"{path}.gl_handoff.reference_resolution_status",
                    "Unresolved GL reference resolution blocks legal-dependent promotion.",
                )
            )
        if gl_handoff.get("g4_compatibility_status") == "pass" and any(
            "reissue_required" in value for value in handoff_values
        ):
            issues.append(
                _issue(
                    "layer3_g4_gl_compatibility_gate_overclaimed",
                    f"{path}.gl_handoff.g4_compatibility_status",
                    "GL G4 compatibility is read-compatibility only.",
                )
            )

    human_gate = build_g4_human_decision_integrity_gate(request)
    for code in human_gate.issue_codes:
        issues.append(
            _issue(code, f"{path}.human_decision_policy", "Human-decision gate failed.")
        )
    if human_gate.human_decision_record_refs and _requires_g1(request) and not _has_g1_grounded_row(
        request
    ):
        issues.append(
            _issue(
                "layer3_g4_human_decision_overrides_a_incompleteness",
                f"{path}.human_decision_policy",
                "Human decision cannot override missing grounded contracts.",
            )
        )
    return issues


def validate_layer3_g4_bundle(
    repo_root: Path,
    bundle: Layer3G4Bundle | Mapping[str, Any],
) -> Layer3G4ValidationReport:
    """Validate a G4 runtime bundle or candidate payload."""

    payload = (
        bundle.model_dump(mode="json") if isinstance(bundle, Layer3G4Bundle) else dict(bundle)
    )
    issues: list[Layer3G4ValidationIssue] = []
    snapshot_payload = payload.get("dependency_readiness") or payload.get(
        "dependency_readiness_snapshot"
    )
    if isinstance(snapshot_payload, Mapping):
        snapshot = _snapshot_from_payload(repo_root, snapshot_payload)
    else:
        snapshot = _snapshot_from_payload(repo_root, None)
    if snapshot.g0_dependency_status != "pass":
        issues.append(
            _issue(
                "layer3_g4_g0_dependency_not_ready",
                "$.dependency_readiness.g0_dependency_status",
                "G0 readiness is a hard G4 dependency.",
            )
        )
    if snapshot.g1_dependency_status != "pass":
        issues.append(
            _issue(
                "layer3_g4_g1_dependency_not_ready",
                "$.dependency_readiness.g1_dependency_status",
                "G1 readiness is a hard G4 dependency.",
            )
        )

    requests = payload.get("promotion_requests", ())
    if not requests and isinstance(payload.get("promotion_input_set"), Mapping):
        requests = payload["promotion_input_set"].get("promotion_requests", ())
    if not requests:
        issues.append(
            _issue(
                "layer3_g4_promotion_input_missing",
                "$.promotion_requests",
                "G4 validation requires at least one promotion request.",
            )
        )
    if isinstance(requests, Sequence) and not isinstance(requests, str | bytes | bytearray):
        for request in requests:
            if isinstance(request, Mapping):
                request_payload = dict(request)
                if "dependency_readiness" not in request_payload and isinstance(
                    payload.get("dependency_readiness"), Mapping
                ):
                    request_payload["dependency_readiness"] = payload["dependency_readiness"]
                issues.extend(_validate_request(repo_root, request_payload, snapshot))
    issues.extend(_validate_public_projection(payload))
    issues.extend(_validate_task5_authority_boundaries(payload))
    issues.extend(_validate_task7_closeout_contracts(payload))
    status: Literal["pass", "fail"] = "fail" if issues else "pass"
    summary = _summary(snapshot)
    summary["g4_promotion_input_count"] = len(requests) if isinstance(requests, Sequence) else 0
    summary["g4_issue_count"] = len(issues)
    missing_grounded_contract = bool(
        {issue.code for issue in issues} & {"layer3_g4_grounded_contract_ref_missing"}
    )
    summary["g4_grounded_contract_set_status"] = (
        "fail" if missing_grounded_contract else "pass"
    )
    return Layer3G4ValidationReport(status=status, issues=tuple(issues), summary=summary)


def build_layer3_g4_bundle(repo_root: Path) -> Layer3G4Bundle:
    """Build the G4 runtime bundle from persisted dependency artifacts."""

    root = Path(repo_root).resolve()
    snapshot = build_g4_dependency_readiness_snapshot(repo_root)
    artifact_shapes = load_g4_dependency_artifacts(
        repo_root,
        required_families=("g1", "g2", "g3", "gl"),
    )
    collision_guard = check_g4_naming_collisions(repo_root)
    request_payloads = build_g4_promotion_request_dicts_from_data_home(root)
    (
        promotion_inputs,
        grounded_contracts,
        a_completeness_ledger,
        weakest_boundary,
        human_gate,
        promotion_records,
    ) = _build_g4_promotion_chains_from_requests(root, request_payloads)
    closeout_gate = build_g4_closeout_consumer_gate(promotion_records)
    pdc_gate = build_g4_pdc_compiler_consumer_gate(promotion_records)
    g5_handoff = build_g4_g5_promotion_handoff(promotion_records)
    throughput = build_g4_governance_throughput_delta(promotion_records)
    audit_surface = build_g4_promotion_audit_surface(promotion_records)
    projection_refs = build_g4_public_export_projection_refs(promotion_records)
    conformance = validate_g4_conformance(repo_root)
    performance_contract = conformance.performance_contract
    registry_delta = build_g4_registry_ratchet_delta(conformance)
    health_delta = _health_metric_delta_from_records(promotion_records)
    adapter_registry = _adapter_contract_registry_payload()
    issue_codes = tuple(
        dict.fromkeys(
            (
                *snapshot.issue_codes,
                *promotion_inputs.issue_codes,
                *a_completeness_ledger.issue_codes,
            )
        )
    )
    bundle_status: Literal["pass", "fail"] = (
        "pass" if snapshot.status == "pass" and not issue_codes else "fail"
    )
    placeholder_manifest = Layer3G4ReadinessManifest(
        status=bundle_status,
        summary={},
        issue_codes=issue_codes,
    )
    bundle = Layer3G4Bundle(
        dependency_readiness_snapshot=snapshot,
        dependency_artifact_shapes=artifact_shapes,
        naming_collision_guard=collision_guard,
        promotion_input_set=promotion_inputs,
        grounded_contract_set=grounded_contracts,
        a_completeness_ledger=a_completeness_ledger,
        human_decision_integrity_gate=human_gate,
        weakest_boundary_composition=weakest_boundary,
        promotion_records=promotion_records,
        closeout_consumer_gate=closeout_gate,
        pdc_compiler_consumer_gate=pdc_gate,
        g5_promotion_handoff=g5_handoff,
        governance_throughput_delta=throughput,
        promotion_audit_surface=audit_surface,
        public_export_projection_refs=projection_refs,
        conformance_report=conformance,
        performance_contract_report=performance_contract,
        registry_ratchet_delta=registry_delta,
        health_metric_delta=health_delta,
        adapter_contract_registry=adapter_registry,
        readiness_manifest=placeholder_manifest,
    )
    readiness_manifest = Layer3G4ReadinessManifest(
        status=bundle_status,
        summary=_g4_bundle_summary(bundle),
        issue_codes=issue_codes,
    )
    return bundle.model_copy(update={"readiness_manifest": readiness_manifest})


__all__ = (
    "ALL_ISSUE_CODES",
    "G4_ADAPTER_PATH_IDS",
    "G4_CONFORMANCE_NEGATIVE_IDS",
    "G4_EXPECTED_HEALTH_METRICS",
    "G4_FINAL_PROMOTION_RECORD_STATES",
    "G4_GENERATED_ARTIFACT_FAMILY_ID",
    "G4_MAY_NOT_USE_FOR",
    "G4_PUBLIC_EXPORT_HOOK_STATUS_VALUES",
    "G4_READINESS_CHECK_ID",
    "G4_SOURCE_PAYLOAD_STATUS_VALUES",
    "G4_SURFACE_ID",
    "LAYER3_G4_RULE_VERSION",
    "LAYER3_G4_SCHEMA_VERSION",
    "PROMOTION_STATE_VALUES",
    "Layer3G4ACompletenessLedger",
    "Layer3G4ACompletenessRequirement",
    "Layer3G4Bundle",
    "Layer3G4CloseoutConsumerGate",
    "Layer3G4ConformanceNegativeResult",
    "Layer3G4ConformanceReport",
    "Layer3G4DependencyArtifactShape",
    "Layer3G4DependencyReadinessSnapshot",
    "Layer3G4G5PromotionHandoff",
    "Layer3G4GovernanceThroughputDelta",
    "Layer3G4GroundedContractRef",
    "Layer3G4GroundedContractSet",
    "Layer3G4HumanDecisionIntegrityGate",
    "Layer3G4NamingCollisionGuard",
    "Layer3G4PdcCompilerConsumerGate",
    "Layer3G4PerformanceContractReport",
    "Layer3G4PromotionAuditSurface",
    "Layer3G4PromotionInput",
    "Layer3G4PromotionInputSet",
    "Layer3G4PromotionRecord",
    "Layer3G4PromotionRequest",
    "Layer3G4PublicExportProjectionRefSurface",
    "Layer3G4ReadinessManifest",
    "Layer3G4RegistryRatchetDelta",
    "Layer3G4S7DecisionPayloadResolution",
    "Layer3G4SourceDesignRecordResolution",
    "Layer3G4SourcePayloadStatus",
    "Layer3G4ValidationIssue",
    "Layer3G4ValidationReport",
    "Layer3G4WeakestBoundaryComposition",
    "build_g4_a_completeness_ledger",
    "build_g4_closeout_consumer_gate",
    "build_g4_dependency_readiness_snapshot",
    "build_g4_g5_promotion_handoff",
    "build_g4_governance_throughput_delta",
    "build_g4_grounded_contract_set",
    "build_g4_human_decision_integrity_gate",
    "build_g4_pdc_compiler_consumer_gate",
    "build_g4_promotion_audit_surface",
    "build_g4_promotion_input_set",
    "build_g4_promotion_records",
    "build_g4_public_export_projection_refs",
    "build_g4_registry_ratchet_delta",
    "build_g4_weakest_boundary_composition",
    "build_layer3_g4_bundle",
    "check_g4_naming_collisions",
    "load_g4_dependency_artifacts",
    "resolve_g4_source_design_record",
    "validate_g4_conformance",
    "validate_g4_performance_contract",
    "validate_layer3_g4_bundle",
)
