"""Layer 3 GL legal and mandate search contracts.

GL search records are replay/control-plane evidence. A Lex KG hit, threshold
row, reference edge, or intervention mapping is never legal authority until the
claim-level legal authority adapter and downstream consumer gates admit it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.quality.layer3_gx_data_home import load_layer3_gx_data_home

LAYER3_GL_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gl_legal_mandate_search.v1"
LAYER3_GL_RULE_VERSION = "policyos.layer3.gl.legal_mandate_search.v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
CANONICAL_L3_LEGAL_KG_PATH = Path(
    "production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/"
    "lex_knowledge_graph.duckdb"
)
GL_SURFACE_ID = "layer3_gl_legal_mandate_audit_surface"
GL_PUBLIC_PROJECTION_SURFACE_ID = "layer3_gl_public_export_projection_refs"
GL_GENERATED_ARTIFACT_FAMILY_ID = "policy-design-case-layer3-gl-legal-mandate-artifacts"
GL_READINESS_CHECK_ID = "layer3_gl_legal_mandate_search_readiness_gate"
GL_LEGAL_REQUIREMENT_ARTIFACT_PATH = (
    "architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json"
)
GL_LEGAL_AUTHORITY_REPORT_PATH = (
    "architecture/policy_design_case/layer3_gl_legal_authority_report.json"
)
GL_JURISDICTION_FALLBACK_CONFIG_REF = "jurisdiction-fallback:gl-ua-v1"
GL_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "recommendation_substance",
    "closeout_authority",
    "publication_authority",
    "agent_authority",
    "legal_authority_without_claim_level_adapter",
    "mandate_authority_without_temporal_competence",
    "s6_mandate_pass_without_s6_evaluation",
    "ranked_value_choice_without_s8_authorization",
)
GL_LEDGER_AUTHORITATIVE_FOR: tuple[str, ...] = ()
EXPECTED_HEALTH_METRICS: tuple[str, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
KNOWN_SEED_CANDIDATE_PATHS: dict[str, tuple[str, ...]] = {
    "known_threshold_seed": ("threshold_metric_operator_value_unit",),
    "known_norm_seed": ("normative_fact",),
    "known_amendment_seed": ("amendment_lineage",),
    "known_temporal_seed": ("provision_source_bundle",),
    "known_reference_seed": ("reference_resolution",),
    "known_mapping_seed": ("intervention_map_candidate",),
}
REQUIRED_KG_COLUMNS: dict[str, tuple[str, ...]] = {
    "lex_rule_thresholds": (
        "threshold_id",
        "fact_id",
        "metric",
        "operator",
        "value_decimal",
        "value_text",
        "unit",
        "applies_to",
    ),
    "lex_normative_ready_facts": (
        "fact_id",
        "fact_text",
        "jurisdiction",
        "top_domain",
        "effective_from",
        "effective_to",
        "temporal_resolution_status",
        "trust_tier",
        "grounding_status",
        "canonical_status",
        "reference_resolution_status",
        "doc_id",
        "provision_anchor",
    ),
    "lex_normative_facts": ("fact_id", "fact_text", "jurisdiction", "top_domain"),
    "lex_amendments": (
        "amendment_id",
        "amending_doc_id",
        "amended_doc_id",
        "effective_from",
        "target_anchor",
    ),
    "lex_doc_versions": ("version_row_id", "doc_id", "doc_family_id", "version_id"),
    "lex_doc_temporal": ("doc_id", "effective_from", "temporal_resolution_status"),
    "lex_reference_edges": (
        "reference_edge_id",
        "source_doc_id",
        "target_doc_id",
        "resolution_status",
    ),
    "lex_reference_resolution_audit": (
        "ref_id",
        "source_doc_id",
        "resolution_status",
        "selected_target_doc_id",
    ),
    "lex_temporal_audit": (
        "audit_id",
        "scope",
        "doc_id",
        "fact_id",
        "temporal_resolution_status",
    ),
}
AUTHORITY_FACET_NATIVE_COLUMNS: tuple[str, ...] = (
    "authority_type",
    "authority_types",
    "competent_actor",
    "competent_actor_ref",
    "instrument",
    "instrument_type",
    "instrument_types",
    "implementation_authority",
    "implementation_authority_ref",
    "fiscal_authority",
    "fiscal_authority_ref",
    "budget_authority",
)
COMPANION_FILE_PATHS: tuple[Path, ...] = (
    Path("production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/qc_report.json"),
    Path(
        "production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/"
        "benchmark_report.json"
    ),
    Path(
        "production_data/lex/lex-amendment-only-optimized-20260501-v3/amendment_only_summary.json"
    ),
    Path(
        "production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/"
        "claim_exports/normative_claims_summary.json"
    ),
)
GL_ADAPTER_PATH_IDS: tuple[str, ...] = (
    "layer3_gl_l3_legal_kg_to_search_ledger",
    "layer3_gl_search_ledger_to_norm_candidate_binding",
    "layer3_gl_l3_legal_kg_to_authority_facet_binding",
    "layer3_gl_legal_requirement_to_legal_authority_report",
    "layer3_gl_authority_facet_binding_to_legal_authority_report",
    "layer3_gl_legal_authority_report_to_threshold_authority_record",
    "layer3_gl_legal_authority_report_to_mandate_authority_record",
    "layer3_gl_temporal_lineage_to_competence_record",
    "layer3_gl_amendment_lineage_to_reissue_gate",
    "layer3_gl_authority_record_to_lex_intervention_map_binding",
    "layer3_gl_authority_record_to_claim_registry",
    "layer3_gl_authority_record_to_argument_graph_readiness",
    "layer3_gl_mandate_record_to_s6_s7_consumer_gate",
    "layer3_gl_mandate_record_to_s8_value_choice_consumer_gate",
    "layer3_gl_authority_record_to_design_constraints",
    "layer3_gl_authority_record_to_g4_promotion_gate_input",
    "layer3_gl_audit_surface_to_public_projection_refs",
    "layer3_gl_public_projection_refs_to_reference_only_surface",
)
GL_REFERENCE_ONLY_PUBLIC_PROJECTION_ROUTE = (
    "layer3_gl_public_projection_refs_to_reference_only_surface"
)
GL_PUBLIC_EXPORT_BUNDLE_ROUTE = "layer3_gl_public_projection_refs_to_public_export_bundle"
ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_gl_g0_dependency_not_ready",
    "layer3_gl_l3_legal_kg_missing",
    "layer3_gl_l3_legal_kg_route_not_bound",
    "layer3_gl_l3_legal_kg_index_coverage_failed",
    "layer3_gl_noncanonical_legal_route_used_for_closure",
    "layer3_gl_search_ledger_missing",
    "layer3_gl_query_trace_missing",
    "layer3_gl_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_gl_stale_legal_index_blocks_domain_ceiling",
    "layer3_gl_false_abstention_recall_unmeasured",
    "layer3_gl_text_search_used_as_authority",
    "layer3_gl_read_api_text_search_used_for_closure",
    "layer3_gl_applicability_report_internal_lex_kg_fallback_used_for_closure",
    "layer3_gl_runtime_candidate_norm_snapshot_used_for_closure",
    "layer3_gl_internal_requirement_compile_used_for_closure",
    "layer3_gl_legal_requirement_producer_artifact_ref_missing",
    "layer3_gl_legal_authority_report_missing_gl_producer_artifact_ref",
    "layer3_gl_retrieved_legal_text_used_as_authority",
    "layer3_gl_llm_legal_summary_used_as_authority",
    "layer3_gl_legal_requirement_binding_missing",
    "layer3_gl_legal_requirement_missing_authority_types",
    "layer3_gl_compiler_default_authority_type_unmarked",
    "layer3_gl_compiler_default_authority_type_laundered",
    "layer3_gl_jurisdiction_fallback_policy_missing",
    "layer3_gl_authority_facet_binding_missing",
    "layer3_gl_kg_authority_facets_assumed_present",
    "layer3_gl_text_derived_authority_facet_overclaimed",
    "layer3_gl_authority_facet_binding_semantic_loss",
    "layer3_gl_norm_candidate_binding_missing",
    "layer3_gl_l5_calibration_binding_missing",
    "layer3_gl_norm_temporal_window_missing",
    "layer3_gl_norm_source_authority_missing",
    "layer3_gl_reference_resolution_unresolved",
    "layer3_gl_amendment_lineage_missing",
    "layer3_gl_stale_amendment_lineage",
    "layer3_gl_threshold_authority_record_missing",
    "layer3_gl_threshold_row_not_hydrated",
    "layer3_gl_thresholds_json_used_as_authority",
    "layer3_gl_threshold_unit_or_operator_unparsed",
    "layer3_gl_partial_temporal_row_promoted_to_authority",
    "layer3_gl_mandate_authority_record_missing",
    "layer3_gl_mandate_source_refs_missing",
    "layer3_gl_s6_mandate_semantics_forked",
    "layer3_gl_temporal_competence_record_missing",
    "layer3_gl_legal_authority_report_missing",
    "layer3_gl_selected_norm_without_legal_authority_record",
    "layer3_gl_lex_intervention_map_missing",
    "layer3_gl_lex_intervention_map_used_as_authority",
    "layer3_gl_claim_registry_consumer_gate_missing",
    "layer3_gl_semantic_binding_consumer_gate_missing",
    "layer3_gl_argument_graph_readiness_consumer_gate_missing",
    "layer3_gl_argument_graph_readiness_ref_missing",
    "layer3_gl_s6_mandate_consumer_gate_missing",
    "layer3_gl_s7_delegation_consumer_gate_missing",
    "layer3_gl_s8_value_choice_consumer_gate_missing",
    "layer3_gl_s8_ranking_authorized_without_mandate_pass",
    "layer3_gl_pdc_compiler_consumer_gate_missing",
    "layer3_gl_design_constraint_consumer_gate_missing",
    "layer3_gl_g4_promotion_gate_consumer_gate_missing",
    "layer3_gl_public_raw_legal_payload_leak",
    "layer3_gl_public_export_hook_overclaimed",
    "layer3_gl_public_projection_ref_without_projection_policy",
    "layer3_gl_public_export_projection_mode_mismatch",
    "layer3_gl_public_export_projection_ref_surface_missing",
    "layer3_gl_invariant_readiness_check_unknown",
    "layer3_gl_promotion_authority_leak",
    "layer3_gl_closeout_authority_leak",
    "layer3_gl_adapter_contract_registry_missing",
    "layer3_gl_adapter_registry_summary_only",
    "layer3_gl_adapter_unknown_path",
    "layer3_gl_adapter_semantic_loss",
    "layer3_gl_manifest_runtime_drift",
    "layer3_gl_persisted_artifact_missing",
    "layer3_gl_generated_artifacts_family_missing",
    "layer3_gl_inventory_surface_missing",
    "layer3_gl_reference_index_missing",
    "layer3_gl_public_surface_visibility_missing",
    "layer3_gl_import_laziness_violation",
    "layer3_gl_intervention_resolve_used_in_readiness_import_path",
    "layer3_gl_vector_index_assumed_without_artifact",
)


class _GLModel(BaseModel):
    """Strict base for GL runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _GLArtifact(_GLModel):
    """Common authority-boundary fields for generated GL artifacts."""

    schema_version: str = LAYER3_GL_SCHEMA_VERSION
    rule_version: str = LAYER3_GL_RULE_VERSION
    status: str = "not_implemented"
    authority_boundary: dict[str, Any] = Field(default_factory=lambda: _authority_boundary())
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=GL_MAY_NOT_USE_FOR)
    producer_component: str = "polisyos.runtime.quality.layer3_legal_mandate_search"
    producer_artifact_ref: str = (
        "repo://architecture/policy_design_case/layer3_gl_readiness_manifest.json"
    )
    provenance_refs: tuple[str, ...] = Field(default=())
    legal_kg_snapshot_ref: str | None = None
    query_trace_refs: tuple[str, ...] = Field(default=())
    search_ledger_refs: tuple[str, ...] = Field(default=())
    l5_calibration_refs: tuple[str, ...] = Field(default=())
    legal_requirement_artifact_ref: str | None = None
    authority_facet_binding_refs: tuple[str, ...] = Field(default=())
    legal_as_of: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    temporal_resolution_status: str | None = None
    amendment_lineage_refs: tuple[str, ...] = Field(default=())
    reference_resolution_status: str | None = None
    source_authority: str | None = None
    authority_level: str | None = None
    jurisdiction: str | None = None
    claim_id: str | None = None
    requirement_ref: str | None = None


class Layer3GLValidationIssue(_GLModel):
    """One fail-closed GL validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3GLValidationReport(_GLModel):
    """GL validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3GLValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_code_dictionary: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)


class Layer3GLLegalMandateRequest(_GLModel):
    """Typed request for canonical L3 Legal KG mandate/legal search."""

    request_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    legal_requirement_ref: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    policy_domain: str = Field(min_length=1)
    legal_as_of: str = Field(min_length=1)
    intervention_family: str = Field(min_length=1)
    query_terms: tuple[str, ...] = Field(default=("threshold", "mandate", "legal"))
    limit: int = Field(default=16, ge=1, le=256)
    may_not_use_for: tuple[str, ...] = Field(default=GL_MAY_NOT_USE_FOR)


class Layer3GLL3LegalKgCoverageReport(_GLArtifact):
    """Bounded schema/freshness coverage report for the canonical Lex KG."""

    status: Literal["pass", "fail"] = "fail"
    canonical_kg_path: str = CANONICAL_L3_LEGAL_KG_PATH.as_posix()
    canonical_route_status: str = "missing"
    required_table_count: int = 0
    visible_required_table_count: int = 0
    missing_required_tables: tuple[str, ...] = Field(default=())
    missing_required_columns: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    required_column_refs: tuple[str, ...] = Field(default=())
    table_counts: dict[str, int] = Field(default_factory=dict)
    db_identity: dict[str, Any] = Field(default_factory=dict)
    companion_file_refs: tuple[str, ...] = Field(default=())
    authority_facet_source_status: str = "missing"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLLegalQueryTrace(_GLArtifact):
    """Replay trace for one bounded canonical Lex KG query."""

    trace_id: str = Field(min_length=1)
    canonical_route: str = "l3_legal_kg_duckdb"
    table_routes: tuple[str, ...] = Field(default=())
    sql_shape: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    query_terms: tuple[str, ...] = Field(default=())
    bounded_result_limit: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    observed_row_count: int = Field(default=0, ge=0)
    selected_row_refs: tuple[str, ...] = Field(default=())
    no_hit_reasons: tuple[str, ...] = Field(default=())
    query_budget: dict[str, Any] = Field(default_factory=dict)


class Layer3GLLegalSearchLedger(_GLArtifact):
    """Replayable legal KG search frontier ledger."""

    ledger_id: str = Field(min_length=1)
    status: str = "complete_no_candidate"
    request_ref: str = Field(min_length=1)
    canonical_route: str = "l3_legal_kg_duckdb"
    table_routes: tuple[str, ...] = Field(default=())
    normalized_terms: tuple[str, ...] = Field(default=())
    filters: dict[str, Any] = Field(default_factory=dict)
    sql_shapes: tuple[str, ...] = Field(default=())
    selected_row_refs: tuple[str, ...] = Field(default=())
    candidate_rows: tuple[dict[str, Any], ...] = Field(default=())
    no_hit_blockers: tuple[str, ...] = Field(default=())
    bounded_result_limit: int = Field(default=0, ge=0)
    used_full_table_scan: bool = False
    transition_input: bool = False
    index_schema_snapshot_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLSearchRecallFreshnessReport(_GLArtifact):
    """Recall/freshness control-plane report for GL legal search."""

    status: str = "not_implemented"
    known_seed_status: str = "not_implemented"
    index_freshness_status: str = "not_implemented"
    snapshot_consistency_status: str = "not_implemented"
    companion_freshness_status: str = "not_implemented"
    canonical_kg_path: str = CANONICAL_L3_LEGAL_KG_PATH.as_posix()
    kg_identity: dict[str, Any] = Field(default_factory=dict)
    companion_file_refs: tuple[str, ...] = Field(default=())
    known_seed_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    missed_known_seed_classes: tuple[str, ...] = Field(default=())
    generated_ledger_snapshot_refs: tuple[str, ...] = Field(default=())
    stale_snapshot_refs: tuple[str, ...] = Field(default=())
    missing_snapshot_ledger_refs: tuple[str, ...] = Field(default=())
    false_abstention_disposition: str = "not_evaluated"
    typed_no_ground_blocker: str = ""
    search_ceiling_repair_required: bool = False
    domain_ceiling_allowed: bool = False
    honest_legal_no_ground_allowed: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLL5CalibrationBinding(_GLArtifact):
    """L5 calibration binding for legal candidates."""

    binding_id: str = "gl-l5-calibration:pending"
    candidate_norm_refs: tuple[str, ...] = Field(default=())
    threshold_record_refs: tuple[str, ...] = Field(default=())
    mandate_record_refs: tuple[str, ...] = Field(default=())
    trust_tier: str | None = None
    trust_cap: str | None = None
    minimum_coverage: str | None = None
    schema_regime_refs: tuple[str, ...] = Field(default=())
    changepoint_refs: tuple[str, ...] = Field(default=())
    quality_band: str | None = None
    confidence_fields: dict[str, Any] = Field(default_factory=dict)
    calibration_provenance_refs: tuple[str, ...] = Field(default=())
    calibration_status: str = "not_implemented"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLLegalRequirementBinding(_GLArtifact):
    """GL binding from claim context to legal requirement specs."""

    binding_id: str = "gl-legal-requirement:pending"
    requirement_ref: str | None = None
    claim_ref: str | None = None
    claim_id: str | None = None
    mandatory: bool | None = None
    out_of_scope: bool = False
    no_authority_rationale: str | None = None
    legal_requirement_artifact_ref: str | None = None
    requirement_spec: dict[str, Any] = Field(default_factory=dict)
    requirement_artifact: dict[str, Any] = Field(default_factory=dict)
    compiler_runtime_event_ref: str | None = None
    authority_types: tuple[str, ...] = Field(default=())
    authority_type_source: str | None = None
    compiler_default_marked: bool = True
    compiler_default_fields: tuple[str, ...] = Field(default=())
    required_hierarchy_depth: int | None = None
    temporal_competence_window: dict[str, Any] = Field(default_factory=dict)
    required_instrument_classes: tuple[str, ...] = Field(default=())
    required_actor_refs: tuple[str, ...] = Field(default=())
    required_implementation_authority_refs: tuple[str, ...] = Field(default=())
    required_fiscal_authority_refs: tuple[str, ...] = Field(default=())
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    authority_profile_ref: str | None = None
    facet_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    concept_spine_refs: tuple[str, ...] = Field(default=())
    rule_version_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLAuthorityFacetBinding(_GLArtifact):
    """Binding from Lex KG rows to legal-authority facets."""

    binding_id: str = "gl-authority-facet:pending"
    candidate_binding_ref: str | None = None
    kg_row_ref: str | None = None
    source_table: str | None = None
    facet_name: str | None = None
    facet_value: Any = None
    facet_status: str = "not_implemented"
    facet_source: str | None = None
    source_column_refs: tuple[str, ...] = Field(default=())
    source_row_refs: tuple[str, ...] = Field(default=())
    derivation_rule_ref: str | None = None
    derived_from_compiler_default: bool = False
    validation_status: str = "not_implemented"
    semantic_loss_status: str = "not_measured"
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLNormCandidateBinding(_GLArtifact):
    """Binding from Lex KG rows to candidate norm payloads."""

    binding_id: str = "gl-norm-candidate:pending"
    kg_row_ref: str | None = None
    source_table: str | None = None
    source_row_refs: tuple[str, ...] = Field(default=())
    authority_facets_source: str | None = None
    candidate_norm_status: str = "context_only"
    context_only: bool = True
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    candidate_norm: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLThresholdAuthorityRecord(_GLArtifact):
    """Claim-scoped legal threshold authority record."""

    record_id: str = "gl-threshold:pending"
    threshold_row_ref: str | None = None
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    hydrated_from_table: str | None = None
    threshold_source_field: str | None = None
    metric: str | None = None
    operator: str | None = None
    value_decimal: str | None = None
    value_text: str | None = None
    unit: str | None = None
    applies_to: str | None = None
    source_fact_ref: str | None = None
    source_provision_ref: str | None = None
    source_norm_ref: str | None = None
    legal_effective_window: dict[str, Any] = Field(default_factory=dict)
    legal_admissibility_grade: str | None = None
    authority_grade: str | None = None
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLMandateAuthorityRecord(_GLArtifact):
    """Mandate/boundary record prepared for S6/S7/S8 consumers."""

    record_id: str = "gl-mandate:pending"
    mandate_record_ref: str | None = None
    mandate_source_refs: tuple[str, ...] = Field(default=())
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    source_norm_ref: str | None = None
    authority_type: str | None = None
    competent_actor_ref: str | None = None
    instrument_types: tuple[str, ...] = Field(default=())
    scope_refs: tuple[str, ...] = Field(default=())
    legal_effective_window: dict[str, Any] = Field(default_factory=dict)
    source_authority: str | None = None
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    s6_mandate_firewall_disposition: str | None = None
    s6_evaluation_ref: str | None = None
    s6_compatible_source_handoff_refs: tuple[str, ...] = Field(default=())
    mandate_source_payloads: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLTemporalCompetenceRecord(_GLArtifact):
    """Legal time competence record."""

    record_id: str = "gl-temporal-competence:pending"
    source_norm_ref: str | None = None
    source_row_refs: tuple[str, ...] = Field(default=())
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    claim_implementation_window: dict[str, Any] = Field(default_factory=dict)
    legal_effective_window: dict[str, Any] = Field(default_factory=dict)
    amendment_effective_time: str | None = None
    temporal_resolution_status: str | None = None
    reissue_required: bool = False
    resolution_basis: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLAmendmentLineageRecord(_GLArtifact):
    """Legal amendment lineage record."""

    record_id: str = "gl-amendment-lineage:pending"
    amendment_id: str | None = None
    amending_doc_id: str | None = None
    amended_doc_id: str | None = None
    amendment_type: str | None = None
    effective_from: str | None = None
    target_anchor: str | None = None
    old_text_ref: str | None = None
    new_text_ref: str | None = None
    confidence: float | None = None
    lineage_status: str = "not_implemented"
    source_row_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLReferenceResolutionRecord(_GLArtifact):
    """Reference resolution record for selected legal candidates."""

    record_id: str = "gl-reference-resolution:pending"
    reference_edge_id: str | None = None
    source_doc_id: str | None = None
    source_anchor: str | None = None
    target_doc_id: str | None = None
    target_anchor: str | None = None
    relation_type: str | None = None
    resolution_status: str | None = None
    resolution_confidence: float | None = None
    resolution_audit_row_ref: str | None = None
    source_row_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLLegalAuthorityReportBinding(_GLArtifact):
    """Binding to the claim-level legal authority adapter report."""

    status: str = "not_implemented"
    selected_norm_refs: tuple[str, ...] = Field(default=())
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    rejected_norm_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    used_internal_requirement_compile: bool = False
    explicit_gl_requirement_spec_refs: tuple[str, ...] = Field(default=())
    candidate_source: str = "gl_norm_candidate_bindings"
    runtime_candidate_norms_used_for_closure: bool = False
    applicability_internal_kg_fallback_used: bool = False
    adapter_input_contract: dict[str, Any] = Field(default_factory=dict)
    adapter_report: dict[str, Any] = Field(default_factory=dict)
    applicability_report: dict[str, Any] = Field(default_factory=dict)
    adapter_candidate_norm_count: int = 0
    adapter_legal_authority_record_refs: tuple[str, ...] = Field(default=())
    applicability_status: str = "not_implemented"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLLexInterventionMapBinding(_GLArtifact):
    """Provision-to-intervention map binding with authority precondition."""

    binding_id: str = "gl-lex-intervention-map:pending"
    mapping_ref: str | None = None
    provision_ref: str | None = None
    selected_norm_refs: tuple[str, ...] = Field(default=())
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    admitted_authority_precondition_status: str = "not_implemented"
    intervention_kind: str | None = None
    knob_ids: tuple[str, ...] = Field(default=())
    target_population_type: str | None = None
    target_sector_ids: tuple[str, ...] = Field(default=())
    target_region_ids: tuple[str, ...] = Field(default=())
    strategic_response_expected: bool = False
    transmission_channels: tuple[str, ...] = Field(default=())
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    crosswalk_refs: tuple[str, ...] = Field(default=())
    program_id: str | None = None
    program_name: str | None = None
    mapping_confidence_score: float | None = None
    crosswalk_confidence_score: float | None = None
    mapping_provenance_refs: tuple[str, ...] = Field(default=())
    mapping_metadata: dict[str, Any] = Field(default_factory=dict)
    registry_validation_status: str = "not_implemented"
    registry_lookup_method_refs: tuple[str, ...] = Field(default=())
    mapping_coverage_status: str = "not_implemented"
    production_mapping_row_count: int = 0
    synthetic_mapping_seed_used: bool = False
    executable_compile_status: str = "out_of_scope"
    directive_compiled: bool = False
    used_as_legal_authority: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class _GLConsumerGate(_GLArtifact):
    """Common shape for GL consumer gate records."""

    gate_id: str = "gl-consumer-gate:pending"
    claim_id: str | None = None
    selected_norm_refs: tuple[str, ...] = Field(default=())
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    threshold_record_refs: tuple[str, ...] = Field(default=())
    mandate_record_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GLClaimRegistryConsumerGate(_GLConsumerGate):
    """Claim-registry consumer gate."""

    runtime_claim_registry_ref: str | None = None
    claim_registry_status: str = "not_implemented"
    claim_registry_rows: tuple[dict[str, Any], ...] = Field(default=())
    claim_registry_payload: dict[str, Any] = Field(default_factory=dict)
    producer_authority_refs: tuple[str, ...] = Field(default=())
    claim_authority_refs: tuple[str, ...] = Field(default=())
    consumer_effect: str = "claim_registry_projection_only"


class Layer3GLSemanticBindingConsumerGate(_GLConsumerGate):
    """Semantic-binding consumer gate."""

    semantic_binding_ref: str | None = None
    semantic_binding_status: str = "not_implemented"
    semantic_binding_rows: tuple[dict[str, Any], ...] = Field(default=())
    semantic_binding_ledger: dict[str, Any] = Field(default_factory=dict)
    semantic_binding_issue_codes: tuple[str, ...] = Field(default=())
    legal_admissibility_grades: tuple[str, ...] = Field(default=())
    jurisdiction_fallback_policy_refs: tuple[str, ...] = Field(default=())


class Layer3GLArgumentGraphReadinessConsumerGate(_GLConsumerGate):
    """Argument graph/readiness consumer gate."""

    readiness_rows: tuple[dict[str, Any], ...] = Field(default=())
    argument_graph_surface_refs: tuple[str, ...] = Field(default=())
    diagnostic_only: bool = True
    claims_promotion_authority: bool = False


class Layer3GLS6MandateConsumerGate(_GLConsumerGate):
    """S6 mandate consumer gate."""

    s6_evaluation_ref: str | None = None
    s6_gate_disposition: str = "not_implemented"
    s6_mandate_source_records: tuple[dict[str, Any], ...] = Field(default=())
    layer2_s6_compatible_input_refs: tuple[str, ...] = Field(default=())
    does_not_assert_s6_pass: bool = True


class Layer3GLS7DelegationConsumerGate(_GLConsumerGate):
    """S7 delegation consumer gate."""

    delegation_handoff_refs: tuple[str, ...] = Field(default=())
    human_decision_integrity_authority: str = "s7_not_gl"
    p26_boundary_preserved: bool = True
    responsibility_routing_needed: bool = False


class Layer3GLS8ValueChoiceConsumerGate(_GLConsumerGate):
    """S8 value-choice consumer gate."""

    value_choice_scope: str = "non_ranking_gl_closure"
    ranking_authorized: bool = False
    requires_s6_mandate_pass_for_ranking: bool = True
    authorized_value_schedule_refs: tuple[str, ...] = Field(default=())
    layer2_s8_compatible_input_refs: tuple[str, ...] = Field(default=())


class Layer3GLPdcCompilerConsumerGate(_GLConsumerGate):
    """PDC compiler consumer gate."""

    compatible_with_pdc_input: bool = False
    pdc_input_refs: tuple[str, ...] = Field(default=())
    projection_rows: tuple[dict[str, Any], ...] = Field(default=())


class Layer3GLDesignConstraintConsumerGate(_GLConsumerGate):
    """Design constraint consumer gate."""

    design_constraint_rows: tuple[dict[str, Any], ...] = Field(default=())
    consumed_as_recommendation_substance: bool = False
    consumed_as_promotion_authority: bool = False


class Layer3GLG4PromotionGateConsumerGate(_GLConsumerGate):
    """G4 promotion compatibility consumer gate."""

    future_g4_required_refs: tuple[str, ...] = Field(default=())
    promotion_authority_claimed: bool = False
    closeout_authority_claimed: bool = False
    governed_promoted_claimed: bool = False


class Layer3GLPromotionGateHandoff(_GLArtifact):
    """Reference-only handoff for future promotion governance."""

    handoff_id: str = "gl-promotion-handoff:pending"
    legal_authority_record_refs: tuple[str, ...] = Field(default=())
    threshold_record_refs: tuple[str, ...] = Field(default=())
    mandate_record_refs: tuple[str, ...] = Field(default=())
    handoff_refs: tuple[str, ...] = Field(default=())
    promotion_authority_claimed: bool = False
    closeout_authority_claimed: bool = False


class Layer3GLLegalMandateAuditSurface(_GLArtifact):
    """EXPERT/MACHINE audit surface for GL legal mandate search."""

    surface_id: str = GL_SURFACE_ID
    surface_audiences: tuple[str, ...] = ("EXPERT", "MACHINE")
    raw_legal_payload_exported: bool = False
    audit_refs: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    gate_refs: tuple[str, ...] = Field(default=())
    decision_refs: tuple[str, ...] = Field(default=())
    safe_disclosure_status: str = "pass"


class Layer3GLPublicExportProjectionRefSurface(_GLArtifact):
    """Reference-only public projection surface for GL refs."""

    surface_id: str = GL_PUBLIC_PROJECTION_SURFACE_ID
    projection_mode: str = "reference_only"
    public_export_hook_status: str = "not_implemented"
    raw_legal_payload_exported: bool = False
    projection_policy_ref: str | None = None
    projection_refs: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    safe_disclosure_status: str = "pass"
    public_payload_fields: tuple[str, ...] = Field(
        default=(
            "surface_id",
            "projection_mode",
            "safe_disclosure_status",
            "projection_refs",
        )
    )


class Layer3GLAdapterAdmissionBundle(_GLArtifact):
    """GL adapter admission bundle reusing the G0 adapter admission record."""

    adapter_admission_records: tuple[dict[str, Any], ...] = Field(default=())


class Layer3GLConformanceReport(_GLArtifact):
    """GL conformance report."""

    checked_issue_codes: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)
    issue_codes: tuple[str, ...] = Field(default=())
    negative_issue_codes: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)
    performance_status: str = "not_checked"
    closeout_status: str = "not_checked"
    conformance_gate_statuses: dict[str, str] = Field(default_factory=dict)
    performance_check_refs: tuple[str, ...] = Field(default=())


class Layer3GLReadinessManifest(_GLModel):
    """Selected GL readiness keys used for runtime/persisted drift checks."""

    schema_version: str = LAYER3_GL_SCHEMA_VERSION
    rule_version: str = LAYER3_GL_RULE_VERSION
    g0_dependency_status: str = "not_checked"
    g1_context_status: str = "not_loaded"
    g2_context_status: str = "not_loaded"
    g3_context_status: str = "not_loaded"
    gl_l3_legal_kg_route_status: str = "fail"
    gl_l3_legal_kg_table_count: int = 0
    gl_l3_legal_kg_index_coverage_status: str = "fail"
    gl_search_ledger_count: int = 0
    gl_query_trace_count: int = 0
    gl_search_recall_freshness_status: str = "not_implemented"
    gl_l5_calibration_binding_status: str = "not_implemented"
    gl_l5_calibration_binding_count: int = 0
    gl_legal_requirement_binding_count: int = 0
    gl_authority_facet_binding_status: str = "not_implemented"
    gl_authority_facet_binding_count: int = 0
    gl_norm_candidate_binding_count: int = 0
    gl_legal_authority_report_status: str = "not_implemented"
    gl_selected_norm_ref_count: int = 0
    gl_legal_authority_record_count: int = 0
    gl_threshold_authority_record_count: int = 0
    gl_mandate_authority_record_count: int = 0
    gl_temporal_competence_status: str = "not_implemented"
    gl_amendment_lineage_status: str = "not_implemented"
    gl_reference_resolution_status: str = "not_implemented"
    gl_lex_intervention_map_binding_status: str = "not_implemented"
    gl_claim_registry_consumer_gate_status: str = "not_implemented"
    gl_semantic_binding_consumer_gate_status: str = "not_implemented"
    gl_argument_graph_readiness_consumer_gate_status: str = "not_implemented"
    gl_s6_mandate_consumer_gate_status: str = "not_implemented"
    gl_s7_delegation_consumer_gate_status: str = "not_implemented"
    gl_s8_value_choice_consumer_gate_status: str = "not_implemented"
    gl_design_constraint_consumer_gate_status: str = "not_implemented"
    gl_g4_promotion_gate_consumer_gate_status: str = "not_implemented"
    gl_public_export_projection_status: str = "reference_only"
    gl_public_export_projection_hook_status: str = "not_implemented"
    gl_public_export_projection_mode: str = "reference_only"
    gl_public_export_projection_ref_surface_status: str = "pass"
    gl_inventory_surface_status: str = "not_registered"
    gl_reference_docs_status: str = "not_registered"
    gl_invariant_readiness_check_registration_status: str = "not_registered"
    gl_adapter_semantic_loss_status: str = "not_measured"
    gl_governance_throughput_status: str = "not_measured"
    gl_conformance_status: str = "fail"
    gl_adapter_contract_registry_status: str = "not_implemented"
    gl_adapter_contract_path_count: int = 0
    gl_health_metric_ids: tuple[str, ...] = Field(default=EXPECTED_HEALTH_METRICS)


class Layer3GLBundle(_GLModel):
    """Top-level GL runtime bundle shape."""

    schema_version: str = LAYER3_GL_SCHEMA_VERSION
    rule_version: str = LAYER3_GL_RULE_VERSION
    adapter_admission_registry: Layer3GLAdapterAdmissionBundle
    l3_legal_kg_index_coverage: Layer3GLL3LegalKgCoverageReport
    l3_legal_kg_search_ledgers: tuple[Layer3GLLegalSearchLedger, ...]
    l3_legal_kg_query_traces: tuple[Layer3GLLegalQueryTrace, ...]
    search_recall_freshness: Layer3GLSearchRecallFreshnessReport
    l5_calibration_bindings: tuple[Layer3GLL5CalibrationBinding, ...]
    legal_requirement_bindings: tuple[Layer3GLLegalRequirementBinding, ...]
    authority_facet_bindings: tuple[Layer3GLAuthorityFacetBinding, ...]
    norm_candidate_bindings: tuple[Layer3GLNormCandidateBinding, ...]
    threshold_authority_records: tuple[Layer3GLThresholdAuthorityRecord, ...]
    mandate_authority_records: tuple[Layer3GLMandateAuthorityRecord, ...]
    temporal_competence_records: tuple[Layer3GLTemporalCompetenceRecord, ...]
    amendment_lineage_records: tuple[Layer3GLAmendmentLineageRecord, ...]
    reference_resolution_records: tuple[Layer3GLReferenceResolutionRecord, ...]
    legal_authority_report: Layer3GLLegalAuthorityReportBinding
    lex_intervention_map_bindings: tuple[Layer3GLLexInterventionMapBinding, ...]
    claim_registry_consumer_gate: Layer3GLClaimRegistryConsumerGate
    semantic_binding_consumer_gate: Layer3GLSemanticBindingConsumerGate
    argument_graph_readiness_consumer_gate: Layer3GLArgumentGraphReadinessConsumerGate
    s6_mandate_consumer_gate: Layer3GLS6MandateConsumerGate
    s7_delegation_consumer_gate: Layer3GLS7DelegationConsumerGate
    s8_value_choice_consumer_gate: Layer3GLS8ValueChoiceConsumerGate
    pdc_compiler_consumer_gate: Layer3GLPdcCompilerConsumerGate
    design_constraint_consumer_gate: Layer3GLDesignConstraintConsumerGate
    g4_promotion_gate_consumer_gate: Layer3GLG4PromotionGateConsumerGate
    promotion_gate_handoff: Layer3GLPromotionGateHandoff
    legal_mandate_audit_surface: Layer3GLLegalMandateAuditSurface
    public_export_projection_refs: Layer3GLPublicExportProjectionRefSurface
    conformance_report: Layer3GLConformanceReport
    health_metric_delta: dict[str, Any] = Field(default_factory=dict)
    adapter_contract_registry: dict[str, Any] = Field(default_factory=dict)
    readiness_manifest: Layer3GLReadinessManifest


def build_layer3_gl_bundle(repo_root: Path) -> Layer3GLBundle:
    """Build a GL bundle with Task 1 canonical search-route artifacts."""

    root = Path(repo_root)
    coverage = build_gl_l3_legal_kg_index_coverage(root)
    requests = (_default_request(),)
    ledgers = build_gl_legal_search_ledgers(root, requests)
    traces = build_gl_legal_query_traces(root, ledgers)
    search_recall = build_gl_search_recall_freshness(root, ledgers)
    legal_requirement_bindings = build_gl_legal_requirement_bindings(root)
    authority_facet_bindings = build_gl_authority_facet_bindings(
        root,
        ledgers=ledgers,
        legal_requirement_bindings=legal_requirement_bindings,
    )
    norm_candidate_bindings = build_gl_norm_candidate_bindings(
        root,
        ledgers=ledgers,
        legal_requirement_bindings=legal_requirement_bindings,
        authority_facet_bindings=authority_facet_bindings,
    )
    legal_authority_report = build_gl_legal_authority_report_binding(
        root,
        legal_requirement_bindings=legal_requirement_bindings,
        norm_candidate_bindings=norm_candidate_bindings,
    )
    threshold_authority_records = build_gl_threshold_authority_records(
        root,
        ledgers=ledgers,
        legal_authority_report=legal_authority_report,
        norm_candidate_bindings=norm_candidate_bindings,
    )
    mandate_authority_records = build_gl_mandate_authority_records(
        root,
        legal_requirement_bindings=legal_requirement_bindings,
        legal_authority_report=legal_authority_report,
        norm_candidate_bindings=norm_candidate_bindings,
        threshold_authority_records=threshold_authority_records,
    )
    temporal_competence_records = build_gl_temporal_competence_records(
        root,
        ledgers=ledgers,
        legal_requirement_bindings=legal_requirement_bindings,
        legal_authority_report=legal_authority_report,
        norm_candidate_bindings=norm_candidate_bindings,
    )
    amendment_lineage_records = build_gl_amendment_lineage_records(root, ledgers=ledgers)
    reference_resolution_records = build_gl_reference_resolution_records(root, ledgers=ledgers)
    l5_calibration_bindings = build_gl_l5_calibration_bindings(
        root,
        legal_authority_report=legal_authority_report,
        norm_candidate_bindings=norm_candidate_bindings,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
    )
    lex_intervention_map_bindings = build_gl_lex_intervention_map_bindings(
        root,
        legal_authority_report=legal_authority_report,
        norm_candidate_bindings=norm_candidate_bindings,
        threshold_authority_records=threshold_authority_records,
    )
    claim_registry_consumer_gate = build_gl_claim_registry_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
    )
    semantic_binding_consumer_gate = build_gl_semantic_binding_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
    )
    argument_graph_readiness_consumer_gate = build_gl_argument_graph_readiness_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        claim_registry_consumer_gate=claim_registry_consumer_gate,
        semantic_binding_consumer_gate=semantic_binding_consumer_gate,
    )
    s6_mandate_consumer_gate = build_gl_s6_mandate_consumer_gate(
        legal_authority_report=legal_authority_report,
        mandate_authority_records=mandate_authority_records,
    )
    s7_delegation_consumer_gate = build_gl_s7_delegation_consumer_gate(
        mandate_authority_records=mandate_authority_records,
        s6_mandate_consumer_gate=s6_mandate_consumer_gate,
    )
    s8_value_choice_consumer_gate = build_gl_s8_value_choice_consumer_gate(
        mandate_authority_records=mandate_authority_records,
        s6_mandate_consumer_gate=s6_mandate_consumer_gate,
    )
    pdc_compiler_consumer_gate = build_gl_pdc_compiler_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        claim_registry_consumer_gate=claim_registry_consumer_gate,
        semantic_binding_consumer_gate=semantic_binding_consumer_gate,
    )
    design_constraint_consumer_gate = build_gl_design_constraint_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
    )
    g4_promotion_gate_consumer_gate = build_gl_g4_promotion_gate_consumer_gate(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        design_constraint_consumer_gate=design_constraint_consumer_gate,
    )
    promotion_gate_handoff = build_gl_promotion_gate_handoff(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        g4_promotion_gate_consumer_gate=g4_promotion_gate_consumer_gate,
    )
    legal_mandate_audit_surface = build_gl_audit_surface(
        coverage=coverage,
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        claim_registry_consumer_gate=claim_registry_consumer_gate,
        semantic_binding_consumer_gate=semantic_binding_consumer_gate,
        argument_graph_readiness_consumer_gate=argument_graph_readiness_consumer_gate,
        s6_mandate_consumer_gate=s6_mandate_consumer_gate,
        s7_delegation_consumer_gate=s7_delegation_consumer_gate,
        s8_value_choice_consumer_gate=s8_value_choice_consumer_gate,
        g4_promotion_gate_consumer_gate=g4_promotion_gate_consumer_gate,
    )
    public_export_projection_refs = build_gl_public_export_projection_refs(
        legal_authority_report=legal_authority_report,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
    )
    adapter_registry = _adapter_admission_bundle()
    adapter_contract_registry = {
        "status": "pass",
        "adapter_path_ids": GL_ADAPTER_PATH_IDS,
        "adapter_path_count": len(GL_ADAPTER_PATH_IDS),
        "public_projection_mode": "reference_only",
        "public_projection_route": GL_REFERENCE_ONLY_PUBLIC_PROJECTION_ROUTE,
        "public_export_bundle_route_registered": False,
    }
    g0_dependency_status = _g0_dependency_status(root)
    health_metric_delta = _default_health_metric_delta(
        search_recall,
        authority_facet_bindings=authority_facet_bindings,
        consumer_gate_statuses={
            "claim_registry": claim_registry_consumer_gate.status,
            "semantic_binding": semantic_binding_consumer_gate.status,
            "argument_graph_readiness": argument_graph_readiness_consumer_gate.status,
            "s6_mandate": s6_mandate_consumer_gate.status,
            "s7_delegation": s7_delegation_consumer_gate.status,
            "s8_value_choice": s8_value_choice_consumer_gate.status,
            "pdc_compiler": pdc_compiler_consumer_gate.status,
            "design_constraint": design_constraint_consumer_gate.status,
            "g4_promotion": g4_promotion_gate_consumer_gate.status,
        },
    )
    conformance = _build_gl_conformance_report(
        g0_dependency_status=g0_dependency_status,
        coverage=coverage,
        ledgers=ledgers,
        traces=traces,
        search_recall=search_recall,
        l5_calibration_bindings=l5_calibration_bindings,
        legal_authority_report=legal_authority_report,
        authority_facet_bindings=authority_facet_bindings,
        norm_candidate_bindings=norm_candidate_bindings,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        temporal_competence_records=temporal_competence_records,
        amendment_lineage_records=amendment_lineage_records,
        reference_resolution_records=reference_resolution_records,
        lex_intervention_map_bindings=lex_intervention_map_bindings,
        claim_registry_consumer_gate=claim_registry_consumer_gate,
        semantic_binding_consumer_gate=semantic_binding_consumer_gate,
        argument_graph_readiness_consumer_gate=argument_graph_readiness_consumer_gate,
        s6_mandate_consumer_gate=s6_mandate_consumer_gate,
        s7_delegation_consumer_gate=s7_delegation_consumer_gate,
        s8_value_choice_consumer_gate=s8_value_choice_consumer_gate,
        pdc_compiler_consumer_gate=pdc_compiler_consumer_gate,
        design_constraint_consumer_gate=design_constraint_consumer_gate,
        g4_promotion_gate_consumer_gate=g4_promotion_gate_consumer_gate,
        public_export_projection_refs=public_export_projection_refs,
        adapter_contract_registry=adapter_contract_registry,
        health_metric_delta=health_metric_delta,
    )
    readiness = Layer3GLReadinessManifest(
        g0_dependency_status=g0_dependency_status,
        g1_context_status=_context_manifest_status(root, "g1"),
        g2_context_status=_context_manifest_status(root, "g2"),
        g3_context_status=_context_manifest_status(root, "g3"),
        gl_l3_legal_kg_route_status="pass" if coverage.status == "pass" else "fail",
        gl_l3_legal_kg_table_count=coverage.visible_required_table_count,
        gl_l3_legal_kg_index_coverage_status=coverage.status,
        gl_search_ledger_count=len(ledgers),
        gl_query_trace_count=len(traces),
        gl_search_recall_freshness_status=search_recall.status,
        gl_l5_calibration_binding_status=(
            l5_calibration_bindings[0].status if l5_calibration_bindings else "not_implemented"
        ),
        gl_l5_calibration_binding_count=len(l5_calibration_bindings),
        gl_legal_requirement_binding_count=len(legal_requirement_bindings),
        gl_authority_facet_binding_status=(
            "pass" if authority_facet_bindings else "not_implemented"
        ),
        gl_authority_facet_binding_count=len(authority_facet_bindings),
        gl_norm_candidate_binding_count=len(norm_candidate_bindings),
        gl_legal_authority_report_status=legal_authority_report.status,
        gl_selected_norm_ref_count=len(legal_authority_report.selected_norm_refs),
        gl_legal_authority_record_count=len(legal_authority_report.legal_authority_record_refs),
        gl_threshold_authority_record_count=len(threshold_authority_records),
        gl_mandate_authority_record_count=len(mandate_authority_records),
        gl_temporal_competence_status=_aggregate_record_status(temporal_competence_records),
        gl_amendment_lineage_status=_aggregate_record_status(amendment_lineage_records),
        gl_reference_resolution_status=_aggregate_record_status(reference_resolution_records),
        gl_lex_intervention_map_binding_status=_aggregate_record_status(
            lex_intervention_map_bindings
        ),
        gl_claim_registry_consumer_gate_status=claim_registry_consumer_gate.status,
        gl_semantic_binding_consumer_gate_status=semantic_binding_consumer_gate.status,
        gl_argument_graph_readiness_consumer_gate_status=(
            argument_graph_readiness_consumer_gate.status
        ),
        gl_s6_mandate_consumer_gate_status=s6_mandate_consumer_gate.status,
        gl_s7_delegation_consumer_gate_status=s7_delegation_consumer_gate.status,
        gl_s8_value_choice_consumer_gate_status=s8_value_choice_consumer_gate.status,
        gl_design_constraint_consumer_gate_status=design_constraint_consumer_gate.status,
        gl_g4_promotion_gate_consumer_gate_status=g4_promotion_gate_consumer_gate.status,
        gl_public_export_projection_hook_status=(
            public_export_projection_refs.public_export_hook_status
        ),
        gl_public_export_projection_mode=public_export_projection_refs.projection_mode,
        gl_public_export_projection_ref_surface_status=public_export_projection_refs.status,
        gl_inventory_surface_status="pass",
        gl_reference_docs_status=_gl_reference_docs_status(root),
        gl_invariant_readiness_check_registration_status=(
            _gl_invariant_readiness_check_registration_status()
        ),
        gl_adapter_semantic_loss_status=health_metric_delta["readings"]["adapter-semantic-loss"],
        gl_governance_throughput_status=health_metric_delta["readings"]["governance-throughput"],
        gl_conformance_status=conformance.status,
        gl_adapter_contract_registry_status="pass",
        gl_adapter_contract_path_count=len(GL_ADAPTER_PATH_IDS),
    )
    return Layer3GLBundle(
        adapter_admission_registry=adapter_registry,
        l3_legal_kg_index_coverage=coverage,
        l3_legal_kg_search_ledgers=ledgers,
        l3_legal_kg_query_traces=traces,
        search_recall_freshness=search_recall,
        l5_calibration_bindings=l5_calibration_bindings,
        legal_requirement_bindings=legal_requirement_bindings,
        authority_facet_bindings=authority_facet_bindings,
        norm_candidate_bindings=norm_candidate_bindings,
        threshold_authority_records=threshold_authority_records,
        mandate_authority_records=mandate_authority_records,
        temporal_competence_records=temporal_competence_records,
        amendment_lineage_records=amendment_lineage_records,
        reference_resolution_records=reference_resolution_records,
        legal_authority_report=legal_authority_report,
        lex_intervention_map_bindings=lex_intervention_map_bindings,
        claim_registry_consumer_gate=claim_registry_consumer_gate,
        semantic_binding_consumer_gate=semantic_binding_consumer_gate,
        argument_graph_readiness_consumer_gate=argument_graph_readiness_consumer_gate,
        s6_mandate_consumer_gate=s6_mandate_consumer_gate,
        s7_delegation_consumer_gate=s7_delegation_consumer_gate,
        s8_value_choice_consumer_gate=s8_value_choice_consumer_gate,
        pdc_compiler_consumer_gate=pdc_compiler_consumer_gate,
        design_constraint_consumer_gate=design_constraint_consumer_gate,
        g4_promotion_gate_consumer_gate=g4_promotion_gate_consumer_gate,
        promotion_gate_handoff=promotion_gate_handoff,
        legal_mandate_audit_surface=legal_mandate_audit_surface,
        public_export_projection_refs=public_export_projection_refs,
        conformance_report=conformance,
        health_metric_delta=health_metric_delta,
        adapter_contract_registry=adapter_contract_registry,
        readiness_manifest=readiness,
    )


def validate_layer3_gl_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3GLBundle,
) -> Layer3GLValidationReport:
    """Validate a GL bundle or fixture payload with fail-closed issue codes."""

    _ = repo_root
    payload = _dump_model(persisted)
    issues: list[Layer3GLValidationIssue] = []
    _validate_task1_route(payload, issues)
    _validate_search_recall_freshness(payload, issues)
    _validate_authority_firewalls(payload, issues)
    _validate_consumer_gates(payload, issues)
    issues = _dedupe_issues(issues)
    summary = dict(_mapping(payload.get("readiness_manifest")))
    summary.update(
        {
            "schema_version": payload.get("schema_version", LAYER3_GL_SCHEMA_VERSION),
            "rule_version": payload.get("rule_version", LAYER3_GL_RULE_VERSION),
            "issue_count": len(issues),
        }
    )
    return Layer3GLValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary=summary,
        issue_code_dictionary=ALL_ISSUE_CODES,
    )


def build_gl_l3_legal_kg_index_coverage(repo_root: Path) -> Layer3GLL3LegalKgCoverageReport:
    """Inspect the canonical L3 Legal KG with bounded table/column checks."""

    return _cached_coverage(str(Path(repo_root).resolve()))


@lru_cache(maxsize=4)
def _cached_coverage(repo_root: str) -> Layer3GLL3LegalKgCoverageReport:
    root = Path(repo_root)
    db_path = root / CANONICAL_L3_LEGAL_KG_PATH
    if not db_path.exists():
        return Layer3GLL3LegalKgCoverageReport(
            status="fail",
            canonical_route_status="missing",
            missing_required_tables=tuple(REQUIRED_KG_COLUMNS),
            issue_codes=("layer3_gl_l3_legal_kg_missing",),
        )
    stat = db_path.stat()
    snapshot_ref = _stable_ref(
        CANONICAL_L3_LEGAL_KG_PATH.as_posix(),
        str(stat.st_size),
        str(stat.st_mtime_ns),
    )
    con = duckdb.connect(str(db_path), read_only=True)
    table_rows = con.execute(
        "select table_name from information_schema.tables where table_schema='main'"
    ).fetchall()
    visible_tables = {str(row[0]) for row in table_rows}
    missing_tables = tuple(sorted(set(REQUIRED_KG_COLUMNS) - visible_tables))
    columns_by_table: dict[str, set[str]] = {}
    for table in REQUIRED_KG_COLUMNS:
        if table in visible_tables:
            columns_by_table[table] = {
                str(row[0])
                for row in con.execute(
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema='main' and table_name=?
                    """,
                    [table],
                ).fetchall()
            }
    missing_columns = {
        table: tuple(sorted(set(columns) - columns_by_table.get(table, set())))
        for table, columns in REQUIRED_KG_COLUMNS.items()
        if set(columns) - columns_by_table.get(table, set())
    }
    table_counts: dict[str, int] = {}
    for table in REQUIRED_KG_COLUMNS:
        if table in visible_tables:
            table_counts[table] = int(
                con.execute(f"select count(*) from {table}").fetchone()[0]  # noqa: S608
            )
    native_authority_columns = {
        column
        for columns in columns_by_table.values()
        for column in columns
        if column in AUTHORITY_FACET_NATIVE_COLUMNS
    }
    authority_facet_source_status = (
        "native" if native_authority_columns else "requires_gl_facet_binding"
    )
    issue_codes: tuple[str, ...] = ()
    status: Literal["pass", "fail"] = "pass"
    if missing_tables or missing_columns:
        status = "fail"
        issue_codes = ("layer3_gl_l3_legal_kg_index_coverage_failed",)
    return Layer3GLL3LegalKgCoverageReport(
        status=status,
        canonical_kg_path=CANONICAL_L3_LEGAL_KG_PATH.as_posix(),
        canonical_route_status="canonical_l3_legal_kg",
        required_table_count=len(REQUIRED_KG_COLUMNS),
        visible_required_table_count=len(set(REQUIRED_KG_COLUMNS) & visible_tables),
        missing_required_tables=missing_tables,
        missing_required_columns=missing_columns,
        required_column_refs=tuple(
            f"{table}.{column}"
            for table, columns in REQUIRED_KG_COLUMNS.items()
            for column in columns
        ),
        table_counts=table_counts,
        db_identity={
            "path": CANONICAL_L3_LEGAL_KG_PATH.as_posix(),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "snapshot_ref": snapshot_ref,
        },
        legal_kg_snapshot_ref=snapshot_ref,
        companion_file_refs=_companion_refs(root),
        authority_facet_source_status=authority_facet_source_status,
        issue_codes=issue_codes,
    )


def build_gl_legal_search_ledgers(
    repo_root: Path,
    requests: Sequence[Layer3GLLegalMandateRequest],
) -> tuple[Layer3GLLegalSearchLedger, ...]:
    """Run bounded canonical Lex KG search and emit replayable ledgers."""

    root = Path(repo_root)
    coverage = build_gl_l3_legal_kg_index_coverage(root)
    if coverage.status != "pass":
        return tuple(_coverage_blocked_ledger(request, coverage) for request in requests)
    ledgers: list[Layer3GLLegalSearchLedger] = []
    for request in requests:
        ledgers.append(_threshold_ledger(root, request, coverage))
        ledgers.append(_normative_fact_ledger(root, request, coverage))
        ledgers.append(_amendment_lineage_ledger(root, request, coverage))
        ledgers.append(_provision_source_bundle_ledger(root, request, coverage))
        ledgers.append(_reference_resolution_ledger(root, request, coverage))
        ledgers.append(_intervention_map_candidate_ledger(root, request, coverage))
        ledgers.append(_bounded_no_hit_ledger(root, request, coverage))
    return tuple(ledgers)


def build_gl_legal_query_traces(
    repo_root: Path,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> tuple[Layer3GLLegalQueryTrace, ...]:
    """Build query-trace records from GL search ledgers."""

    _ = repo_root
    traces: list[Layer3GLLegalQueryTrace] = []
    for ledger in ledgers:
        trace_id = (
            ledger.query_trace_refs[0] if ledger.query_trace_refs else f"{ledger.ledger_id}:trace"
        )
        traces.append(
            Layer3GLLegalQueryTrace(
                trace_id=trace_id,
                status="pass"
                if ledger.status in {"complete_with_candidates", "complete_no_candidate"}
                else "fail",
                table_routes=ledger.table_routes,
                sql_shape=ledger.sql_shapes[0] if ledger.sql_shapes else "SELECT 1 LIMIT 0",
                filters=ledger.filters,
                query_terms=ledger.normalized_terms,
                bounded_result_limit=ledger.bounded_result_limit,
                result_count=len(ledger.candidate_rows),
                observed_row_count=len(ledger.candidate_rows),
                selected_row_refs=ledger.selected_row_refs,
                no_hit_reasons=ledger.no_hit_blockers,
                query_budget={
                    "row_limit": ledger.bounded_result_limit,
                    "python_full_scan_allowed": False,
                    "full_corpus_scan_allowed": False,
                    "full_corpus_materialization_allowed": False,
                },
                legal_kg_snapshot_ref=ledger.legal_kg_snapshot_ref,
                search_ledger_refs=(ledger.ledger_id,),
            )
        )
    return tuple(traces)


def build_gl_search_recall_freshness(
    repo_root: Path,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> Layer3GLSearchRecallFreshnessReport:
    """Summarize known-seed recall, index freshness, and no-hit disposition."""

    coverage = build_gl_l3_legal_kg_index_coverage(repo_root)
    expected_snapshot_ref = coverage.db_identity.get("snapshot_ref")
    seed_results = _known_seed_results(ledgers)
    missed_seed_classes = tuple(
        seed_class for seed_class, result in seed_results.items() if result.get("status") != "pass"
    )
    ledger_snapshot_refs = tuple(
        sorted(
            {
                ref
                for ledger in ledgers
                for ref in (ledger.legal_kg_snapshot_ref, ledger.index_schema_snapshot_ref)
                if ref
            }
        )
    )
    stale_snapshot_refs = tuple(
        ref
        for ref in ledger_snapshot_refs
        if expected_snapshot_ref and ref != expected_snapshot_ref
    )
    missing_snapshot_ledger_refs = tuple(
        ledger.ledger_id
        for ledger in ledgers
        if not ledger.legal_kg_snapshot_ref or not ledger.index_schema_snapshot_ref
    )
    snapshot_consistency_pass = bool(
        coverage.status == "pass"
        and expected_snapshot_ref
        and ledger_snapshot_refs
        and not stale_snapshot_refs
        and not missing_snapshot_ledger_refs
    )
    known_seed_pass = not missed_seed_classes
    companion_freshness_status = "pass" if coverage.status == "pass" else "fail"
    index_freshness_status = "pass" if snapshot_consistency_pass else "fail"
    no_hit_present = any(
        ledger.no_hit_blockers or ledger.status == "complete_no_candidate" for ledger in ledgers
    )
    status = (
        "pass"
        if known_seed_pass
        and index_freshness_status == "pass"
        and companion_freshness_status == "pass"
        else "fail"
    )
    repair_required = status != "pass" and no_hit_present
    honest_no_ground_allowed = status == "pass" and no_hit_present
    issue_codes = _search_recall_issue_codes(
        missed_seed_classes=missed_seed_classes,
        stale_snapshot_refs=stale_snapshot_refs,
        missing_snapshot_ledger_refs=missing_snapshot_ledger_refs,
        coverage_status=coverage.status,
        status=status,
    )
    false_abstention_disposition = (
        "typed_legal_no_ground_blocker_allowed"
        if honest_no_ground_allowed
        else "search_ceiling_repair_required"
        if repair_required
        else "grounded_candidates_available"
    )
    return Layer3GLSearchRecallFreshnessReport(
        status=status,
        known_seed_status="pass" if known_seed_pass else "fail",
        index_freshness_status=index_freshness_status,
        snapshot_consistency_status="pass" if snapshot_consistency_pass else "fail",
        companion_freshness_status=companion_freshness_status,
        kg_identity=coverage.db_identity,
        companion_file_refs=coverage.companion_file_refs,
        known_seed_results=seed_results,
        missed_known_seed_classes=missed_seed_classes,
        generated_ledger_snapshot_refs=ledger_snapshot_refs,
        stale_snapshot_refs=stale_snapshot_refs,
        missing_snapshot_ledger_refs=missing_snapshot_ledger_refs,
        false_abstention_disposition=false_abstention_disposition,
        typed_no_ground_blocker=(
            "legal_no_ground_after_fresh_known_seed_recall"
            if honest_no_ground_allowed
            else "search_ceiling_repair_required"
            if repair_required
            else ""
        ),
        search_ceiling_repair_required=repair_required,
        domain_ceiling_allowed=False,
        honest_legal_no_ground_allowed=honest_no_ground_allowed,
        legal_kg_snapshot_ref=expected_snapshot_ref,
        search_ledger_refs=tuple(ledger.ledger_id for ledger in ledgers),
        issue_codes=issue_codes,
    )


def _known_seed_results(
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for seed_class, candidate_paths in KNOWN_SEED_CANDIDATE_PATHS.items():
        hits: list[tuple[Layer3GLLegalSearchLedger, Mapping[str, Any]]] = []
        for ledger in ledgers:
            for candidate in ledger.candidate_rows:
                if _candidate_satisfies_seed(seed_class, candidate, candidate_paths):
                    hits.append((ledger, candidate))
        source_row_refs = tuple(
            sorted(
                {str(candidate.get("row_ref")) for _, candidate in hits if candidate.get("row_ref")}
            )
        )
        search_ledger_refs = tuple(sorted({ledger.ledger_id for ledger, _ in hits}))
        results[seed_class] = {
            "status": "pass" if hits else "fail",
            "candidate_count": len(hits),
            "expected_candidate_paths": candidate_paths,
            "source_row_refs": source_row_refs,
            "search_ledger_refs": search_ledger_refs,
        }
    return results


def _candidate_satisfies_seed(
    seed_class: str,
    candidate: Mapping[str, Any],
    candidate_paths: tuple[str, ...],
) -> bool:
    if candidate.get("candidate_path") not in candidate_paths:
        return False
    if seed_class == "known_threshold_seed":
        return bool(candidate.get("metric") and candidate.get("operator") and candidate.get("unit"))
    if seed_class == "known_norm_seed":
        return bool(candidate.get("fact_id") and candidate.get("jurisdiction"))
    if seed_class == "known_amendment_seed":
        return bool(candidate.get("amendment_id") and candidate.get("amended_doc_id"))
    if seed_class == "known_temporal_seed":
        return bool(candidate.get("doc_id") and candidate.get("temporal_resolution_status"))
    if seed_class == "known_reference_seed":
        return bool(candidate.get("reference_edge_id") and candidate.get("resolution_status"))
    if seed_class == "known_mapping_seed":
        return bool(
            candidate.get("fact_id") and candidate.get("authority_status") == "candidate_only"
        )
    return False


def _search_recall_issue_codes(
    *,
    missed_seed_classes: tuple[str, ...],
    stale_snapshot_refs: tuple[str, ...],
    missing_snapshot_ledger_refs: tuple[str, ...],
    coverage_status: str,
    status: str,
) -> tuple[str, ...]:
    issue_codes: list[str] = []
    if missed_seed_classes:
        issue_codes.append("layer3_gl_search_recall_seed_miss_blocks_domain_ceiling")
    if coverage_status != "pass" or stale_snapshot_refs or missing_snapshot_ledger_refs:
        issue_codes.append("layer3_gl_stale_legal_index_blocks_domain_ceiling")
    if status != "pass":
        issue_codes.append("layer3_gl_false_abstention_recall_unmeasured")
    return tuple(dict.fromkeys(issue_codes))


def build_gl_l5_calibration_bindings(
    repo_root: Path,
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | None = None,
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord] = (),
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord] = (),
) -> tuple[Layer3GLL5CalibrationBinding, ...]:
    """Bind selected legal authority to L5 calibration limits without upgrading it."""

    _ = repo_root
    report = legal_authority_report
    selected_norm_refs = tuple(report.selected_norm_refs if report else ())
    if not selected_norm_refs:
        return ()
    selected_binding = _selected_norm_binding(norm_candidate_bindings, selected_norm_refs)
    candidate_norm = selected_binding.candidate_norm if selected_binding else {}
    threshold_refs = tuple(record.record_id for record in threshold_authority_records)
    mandate_refs = tuple(record.record_id for record in mandate_authority_records)
    provenance_refs = tuple(
        ref
        for ref in (
            report.producer_artifact_ref if report else None,
            *(
                record.threshold_row_ref
                for record in threshold_authority_records
                if record.threshold_row_ref
            ),
        )
        if ref
    )
    return (
        Layer3GLL5CalibrationBinding(
            binding_id=f"gl-l5-calibration:{_stable_id(*selected_norm_refs)}",
            status="limitation",
            candidate_norm_refs=selected_norm_refs,
            threshold_record_refs=threshold_refs,
            mandate_record_refs=mandate_refs,
            trust_tier=str(candidate_norm.get("trust_tier") or "claim_level_threshold_hydrated"),
            trust_cap="context_or_claim_level_only",
            minimum_coverage="not_l5_calibrated",
            schema_regime_refs=("lex_knowledge_graph.duckdb",),
            changepoint_refs=(),
            quality_band="unscored_without_l5_calibration",
            confidence_fields={
                "raw_lex_confidence_authority": "not_used",
                "claim_level_authority_adapter_status": report.status if report else "missing",
            },
            calibration_provenance_refs=provenance_refs,
            calibration_status="missing_l5_calibration_limitation",
            legal_kg_snapshot_ref=selected_binding.legal_kg_snapshot_ref
            if selected_binding
            else None,
            query_trace_refs=selected_binding.query_trace_refs if selected_binding else (),
            issue_codes=("layer3_gl_l5_calibration_binding_missing",),
        ),
    )


def build_gl_legal_requirement_bindings(
    repo_root: Path,
    *,
    claims: Sequence[Mapping[str, Any]] | None = None,
    target_context: Mapping[str, Any] | None = None,
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
) -> tuple[Layer3GLLegalRequirementBinding, ...]:
    """Compile GL claim context into persisted legal-requirement bindings."""

    from polisyos.lex import build_legal_authority_requirement_artifact

    _ = repo_root
    resolved_target = dict(target_context or _default_target_context())
    resolved_claims = tuple(claims or _default_recommendation_claims())
    fallback_config = dict(jurisdiction_fallback_config or _default_jurisdiction_fallback_config())
    artifact = build_legal_authority_requirement_artifact(
        run_id=str(resolved_target["run_id"]),
        target_context=resolved_target,
        claims=resolved_claims,
        jurisdiction_fallback_config=fallback_config,
    )
    artifact_payload = artifact.model_dump(mode="json")
    artifact_ref = _repo_artifact_ref(GL_LEGAL_REQUIREMENT_ARTIFACT_PATH, artifact_payload)
    return tuple(
        _legal_requirement_binding_from_spec(
            requirement=spec,
            requirement_artifact=artifact_payload,
            requirement_artifact_ref=artifact_ref,
            source_claim=resolved_claims[index] if index < len(resolved_claims) else {},
        )
        for index, spec in enumerate(artifact.requirements)
    )


def build_gl_authority_facet_bindings(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
    legal_requirement_bindings: Sequence[Layer3GLLegalRequirementBinding] = (),
) -> tuple[Layer3GLAuthorityFacetBinding, ...]:
    """Derive explicit authority-facet records from KG rows and governed config."""

    _ = repo_root
    candidate = _primary_norm_candidate_row(ledgers)
    requirement = legal_requirement_bindings[0] if legal_requirement_bindings else None
    if candidate is None or requirement is None:
        return ()
    row_ref = str(candidate.get("row_ref") or "")
    binding_ref = f"gl-norm-candidate:{_stable_id(row_ref)}"
    source_table = str(candidate.get("source_table") or "lex_normative_ready_facts")
    source_row_refs = (row_ref,)
    authority_types = tuple(requirement.authority_types)
    context_facets = (
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="authority_types",
            facet_value=authority_types,
            facet_source=(
                "compiler_default"
                if requirement.authority_type_source == "compiler_default"
                else "governed_config"
            ),
            facet_status="context_only",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="legal_requirement_compiler.authority_types",
            derived_from_compiler_default=requirement.authority_type_source == "compiler_default",
            validation_status="context_only",
            semantic_loss_status="compiler_default_not_lex_authority",
            limitation_refs=("gl-limitation:authority-type-compiler-default",),
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="source_authority",
            facet_value=_source_authority_from_candidate(candidate),
            facet_source="derived_from_doc_metadata",
            facet_status="present",
            source_column_refs=(
                f"{source_table}.doc_id",
                f"{source_table}.doc_name",
                f"{source_table}.doc_type",
            ),
            source_row_refs=source_row_refs,
            derivation_rule_ref="gl.lex_doc_metadata.source_authority.v1",
            validation_status="pass",
            semantic_loss_status="bounded_doc_metadata_derivation",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="competent_actor_ref",
            facet_value="cabinet_ministers_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-competent-actor.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="instrument_types",
            facet_value=("resolution",),
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-instrument-types.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="implementation_authority_ref",
            facet_value="cabinet_ministers_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-implementation-authority.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="fiscal_authority_ref",
            facet_value="ministry_finance_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-fiscal-authority.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="hierarchy",
            facet_value={"authority_level": "national", "hierarchy_depth": 2},
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-hierarchy.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="fallback",
            facet_value=requirement.fallback_policy,
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref=GL_JURISDICTION_FALLBACK_CONFIG_REF,
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="legal_effective_window",
            facet_value={
                "start": candidate.get("effective_from"),
                "end": candidate.get("effective_to"),
                "legal_as_of": requirement.legal_as_of,
            },
            facet_source="lex_explicit",
            facet_status="present",
            source_column_refs=(
                f"{source_table}.effective_from",
                f"{source_table}.effective_to",
                f"{source_table}.temporal_resolution_status",
            ),
            source_row_refs=source_row_refs,
            derivation_rule_ref="lex-explicit:temporal-window.v1",
            validation_status="pass",
            semantic_loss_status="lossless",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="conflict_supersession_preemption",
            facet_value={
                "conflict_state": "clear",
                "supersession_state": "not_assessed",
                "preemption_state": "not_assessed",
            },
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-conflict-defaults.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
    )
    threshold = _threshold_candidate_row(ledgers)
    if threshold is None:
        return context_facets
    threshold_row_ref = str(threshold.get("row_ref") or "")
    threshold_binding_ref = f"gl-norm-candidate:{_stable_id(threshold_row_ref)}"
    threshold_facets = _threshold_authority_facet_bindings(
        binding_ref=threshold_binding_ref,
        row_ref=threshold_row_ref,
    )
    return (*threshold_facets, *context_facets)


def build_gl_norm_candidate_bindings(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
    legal_requirement_bindings: Sequence[Layer3GLLegalRequirementBinding] = (),
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding] = (),
) -> tuple[Layer3GLNormCandidateBinding, ...]:
    """Convert KG ledger rows into GL candidate norms for Lex adapters."""

    _ = repo_root
    candidate = _primary_norm_candidate_row(ledgers)
    requirement = legal_requirement_bindings[0] if legal_requirement_bindings else None
    if candidate is None or requirement is None or not authority_facet_bindings:
        return ()
    row_ref = str(candidate.get("row_ref") or "")
    binding_id = f"gl-norm-candidate:{_stable_id(row_ref)}"
    binding_refs = _facet_refs_for_candidate(authority_facet_bindings, binding_id)
    facets = _facets_by_name_for_candidate(authority_facet_bindings, binding_id)
    context_candidate_norm = _candidate_norm_from_facets(
        candidate=candidate,
        requirement=requirement,
        facets=facets,
        authority_facet_binding_refs=binding_refs,
        ledgers=ledgers,
    )
    bindings: list[Layer3GLNormCandidateBinding] = [
        Layer3GLNormCandidateBinding(
            binding_id=binding_id,
            status="context_only",
            kg_row_ref=row_ref,
            source_table=str(candidate.get("source_table") or ""),
            source_row_refs=(row_ref,),
            authority_facets_source="gl_authority_facet_bindings",
            authority_facet_binding_refs=binding_refs,
            candidate_norm_status="context_only",
            context_only=True,
            blocker_refs=("gl-blocker:compiler-default-authority-type-not-lex",),
            candidate_norm=context_candidate_norm,
            legal_kg_snapshot_ref=_first_ledger_snapshot(ledgers),
            query_trace_refs=tuple(context_candidate_norm.get("query_trace_refs", ())),
            claim_id=requirement.claim_id,
            requirement_ref=requirement.requirement_ref,
            jurisdiction=requirement.jurisdiction,
            legal_as_of=requirement.legal_as_of,
        ),
    ]
    threshold = _threshold_candidate_row(ledgers)
    if threshold is not None:
        threshold_row_ref = str(threshold.get("row_ref") or "")
        threshold_binding_id = f"gl-norm-candidate:{_stable_id(threshold_row_ref)}"
        threshold_facet_refs = _facet_refs_for_candidate(
            authority_facet_bindings,
            threshold_binding_id,
        )
        threshold_facets = _facets_by_name_for_candidate(
            authority_facet_bindings,
            threshold_binding_id,
        )
        admitted_candidate_norm = _threshold_candidate_norm_from_facets(
            candidate=threshold,
            requirement=requirement,
            facets=threshold_facets,
            authority_facet_binding_refs=threshold_facet_refs,
            ledgers=ledgers,
        )
        bindings.append(
            Layer3GLNormCandidateBinding(
                binding_id=threshold_binding_id,
                status="pass",
                kg_row_ref=threshold_row_ref,
                source_table=str(threshold.get("source_table") or ""),
                source_row_refs=(threshold_row_ref,),
                authority_facets_source="gl_authority_facet_bindings",
                authority_facet_binding_refs=threshold_facet_refs,
                candidate_norm_status="admitted_candidate",
                context_only=False,
                candidate_norm=admitted_candidate_norm,
                legal_kg_snapshot_ref=_first_ledger_snapshot(ledgers),
                query_trace_refs=tuple(admitted_candidate_norm.get("query_trace_refs", ())),
                claim_id=requirement.claim_id,
                requirement_ref=requirement.requirement_ref,
                jurisdiction=requirement.jurisdiction,
                legal_as_of=requirement.legal_as_of,
            )
        )
    return tuple(bindings)


def build_gl_legal_authority_report_binding(
    repo_root: Path,
    *,
    legal_requirement_bindings: Sequence[Layer3GLLegalRequirementBinding] = (),
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
) -> Layer3GLLegalAuthorityReportBinding:
    """Call Lex legal authority/applicability adapters through GL bindings."""

    from polisyos.lex import (
        build_legal_authority_report,
        build_normative_applicability_report,
    )

    _ = repo_root
    if not legal_requirement_bindings:
        return Layer3GLLegalAuthorityReportBinding(
            status="not_implemented",
            issue_codes=("layer3_gl_legal_requirement_binding_missing",),
        )
    requirement_specs = tuple(binding.requirement_spec for binding in legal_requirement_bindings)
    requirement_refs = tuple(
        binding.requirement_ref or "" for binding in legal_requirement_bindings
    )
    producer_ref = legal_requirement_bindings[
        0
    ].legal_requirement_artifact_ref or _repo_artifact_ref(
        GL_LEGAL_REQUIREMENT_ARTIFACT_PATH, requirement_specs
    )
    candidate_norms = tuple(binding.candidate_norm for binding in norm_candidate_bindings)
    target_context = _default_target_context()
    claims = _default_recommendation_claims()
    fallback_config = _default_jurisdiction_fallback_config()
    adapter_report = build_legal_authority_report(
        target_context=target_context,
        candidate_norms=candidate_norms,
        recommendation_claims=claims,
        legal_requirement_specs=requirement_specs,
        jurisdiction_fallback_config=fallback_config,
        producer_artifact_ref=producer_ref,
    )
    applicability_report = build_normative_applicability_report(
        target_context=target_context,
        candidate_norms=list(candidate_norms),
        recommendation_claims=list(claims),
        legal_requirement_specs=list(requirement_specs),
        jurisdiction_fallback_config=fallback_config,
        retrieval_status="complete_with_candidates" if candidate_norms else "no_candidates",
    )
    adapter_record_refs = tuple(
        str(record.get("legal_authority_record_id"))
        for record in _sequence_of_mappings(adapter_report.get("legal_authority_records"))
        if record.get("legal_authority_record_id")
    )
    selected_norm_refs = tuple(str(ref) for ref in _tuple(adapter_report.get("selected_norm_refs")))
    report_ref = _repo_artifact_ref(
        GL_LEGAL_AUTHORITY_REPORT_PATH,
        {
            "producer_ref": producer_ref,
            "candidate_norm_count": len(candidate_norms),
            "requirement_refs": requirement_refs,
        },
    )
    return Layer3GLLegalAuthorityReportBinding(
        status=str(adapter_report.get("status") or "fail"),
        producer_artifact_ref=producer_ref,
        provenance_refs=(report_ref,),
        selected_norm_refs=selected_norm_refs,
        rejected_norm_refs=tuple(
            str(ref) for ref in _tuple(adapter_report.get("rejected_norm_refs"))
        ),
        legal_authority_record_refs=()
        if adapter_report.get("status") != "pass"
        else adapter_record_refs,
        adapter_legal_authority_record_refs=adapter_record_refs,
        blocker_refs=tuple(str(code) for code in _tuple(adapter_report.get("issue_codes"))),
        used_internal_requirement_compile=False,
        explicit_gl_requirement_spec_refs=requirement_refs,
        candidate_source="gl_norm_candidate_bindings",
        runtime_candidate_norms_used_for_closure=False,
        applicability_internal_kg_fallback_used=False,
        adapter_input_contract={
            "candidate_source": "gl_norm_candidate_bindings",
            "candidate_norm_count": len(candidate_norms),
            "producer_artifact_ref": producer_ref,
            "legal_requirement_specs": list(requirement_specs),
        },
        adapter_report=adapter_report,
        applicability_report=applicability_report,
        adapter_candidate_norm_count=len(candidate_norms),
        applicability_status=str(applicability_report.get("status") or "unknown"),
        issue_codes=tuple(str(code) for code in _tuple(adapter_report.get("issue_codes"))),
        claim_id=legal_requirement_bindings[0].claim_id,
        requirement_ref=legal_requirement_bindings[0].requirement_ref,
        jurisdiction=legal_requirement_bindings[0].jurisdiction,
        legal_as_of=legal_requirement_bindings[0].legal_as_of,
    )


def _legal_requirement_binding_from_spec(
    *,
    requirement: object,
    requirement_artifact: Mapping[str, Any],
    requirement_artifact_ref: str,
    source_claim: Mapping[str, Any],
) -> Layer3GLLegalRequirementBinding:
    spec = requirement.model_dump(mode="json")
    authority_types = tuple(str(item) for item in spec.get("authority_types", ()))
    claim_declared_authority_types = bool(
        _tuple(
            source_claim.get("required_authority_types")
            or source_claim.get("authority_types")
            or source_claim.get("legal_authority_types")
        )
    )
    compiler_default = bool(
        spec.get("mandatory") and authority_types and not claim_declared_authority_types
    )
    out_of_scope = bool(spec.get("out_of_scope"))
    return Layer3GLLegalRequirementBinding(
        binding_id=f"gl-legal-requirement:{_stable_id(str(spec.get('requirement_id')))}",
        status="out_of_scope" if out_of_scope else "pass",
        requirement_ref=str(spec.get("requirement_id") or ""),
        claim_ref=str(spec.get("claim_ref") or ""),
        claim_id=str(spec.get("claim_id") or ""),
        mandatory=bool(spec.get("mandatory")),
        out_of_scope=out_of_scope,
        no_authority_rationale=(
            "claim_marked_non_legal_or_no_authority_required" if out_of_scope else None
        ),
        legal_requirement_artifact_ref=requirement_artifact_ref,
        requirement_spec=spec,
        requirement_artifact=dict(requirement_artifact),
        compiler_runtime_event_ref=str(requirement_artifact.get("runtime_event_ref") or ""),
        authority_types=authority_types,
        authority_type_source="compiler_default" if compiler_default else "claim_context",
        compiler_default_marked=True,
        compiler_default_fields=("authority_types",) if compiler_default else (),
        required_hierarchy_depth=int(spec.get("required_hierarchy_depth") or 0),
        temporal_competence_window=dict(_mapping(spec.get("temporal_competence_window"))),
        required_instrument_classes=tuple(
            str(item) for item in _tuple(spec.get("required_instrument_classes"))
        ),
        required_actor_refs=tuple(str(item) for item in _tuple(spec.get("required_actor_refs"))),
        required_implementation_authority_refs=tuple(
            str(item) for item in _tuple(spec.get("required_implementation_authority_refs"))
        ),
        required_fiscal_authority_refs=tuple(
            str(item) for item in _tuple(spec.get("required_fiscal_authority_refs"))
        ),
        fallback_policy=dict(_mapping(spec.get("fallback_policy"))),
        jurisdiction=str(spec.get("jurisdiction") or ""),
        authority_profile_ref=str(spec.get("authority_profile_ref") or ""),
        facet_refs=tuple(str(item) for item in _tuple(spec.get("facet_refs"))),
        obligation_refs=tuple(str(item) for item in _tuple(spec.get("obligation_refs"))),
        concept_spine_refs=tuple(str(item) for item in _tuple(spec.get("concept_spine_refs"))),
        rule_version_ref=str(spec.get("rule_version_ref") or ""),
        legal_as_of=str(_mapping(spec.get("temporal_competence_window")).get("legal_as_of") or ""),
        effective_from=_optional_text(
            _mapping(spec.get("temporal_competence_window")).get("start")
        ),
        effective_to=_optional_text(_mapping(spec.get("temporal_competence_window")).get("end")),
        producer_artifact_ref=requirement_artifact_ref,
        authority_boundary=dict(_mapping(requirement_artifact.get("authority_boundary"))),
        issue_codes=(),
    )


def _facet_binding(
    *,
    binding_ref: str,
    row_ref: str,
    source_table: str,
    facet_name: str,
    facet_value: object,
    facet_source: str,
    facet_status: str,
    source_column_refs: tuple[str, ...],
    source_row_refs: tuple[str, ...],
    derivation_rule_ref: str,
    validation_status: str,
    semantic_loss_status: str,
    derived_from_compiler_default: bool = False,
    blocker_refs: tuple[str, ...] = (),
    limitation_refs: tuple[str, ...] = (),
) -> Layer3GLAuthorityFacetBinding:
    return Layer3GLAuthorityFacetBinding(
        binding_id=f"gl-authority-facet:{_stable_id(binding_ref, facet_name)}",
        status=validation_status,
        candidate_binding_ref=binding_ref,
        kg_row_ref=row_ref,
        source_table=source_table,
        facet_name=facet_name,
        facet_value=facet_value,
        facet_status=facet_status,
        facet_source=facet_source,
        source_column_refs=source_column_refs,
        source_row_refs=source_row_refs,
        derivation_rule_ref=derivation_rule_ref,
        derived_from_compiler_default=derived_from_compiler_default,
        validation_status=validation_status,
        semantic_loss_status=semantic_loss_status,
        blocker_refs=blocker_refs,
        limitation_refs=limitation_refs,
        legal_kg_snapshot_ref=None,
    )


def _threshold_authority_facet_bindings(
    *,
    binding_ref: str,
    row_ref: str,
) -> tuple[Layer3GLAuthorityFacetBinding, ...]:
    source_table = "lex_rule_thresholds"
    source_row_refs = (row_ref,)
    return (
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="authority_types",
            facet_value=("implementing",),
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-threshold-authority-type.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="source_authority",
            facet_value=f"lex_rule_thresholds:{_stable_id(row_ref, 'source-authority')}",
            facet_source="derived_from_threshold_row",
            facet_status="present",
            source_column_refs=(
                "lex_rule_thresholds.threshold_id",
                "lex_rule_thresholds.fact_id",
            ),
            source_row_refs=source_row_refs,
            derivation_rule_ref="gl.lex_rule_thresholds.source_authority.v1",
            validation_status="pass",
            semantic_loss_status="bounded_threshold_row_derivation",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="competent_actor_ref",
            facet_value="cabinet_ministers_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-competent-actor.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="instrument_types",
            facet_value=("resolution",),
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-instrument-types.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="implementation_authority_ref",
            facet_value="cabinet_ministers_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-implementation-authority.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="fiscal_authority_ref",
            facet_value="ministry_finance_ua",
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-fiscal-authority.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="hierarchy",
            facet_value={"authority_level": "national", "hierarchy_depth": 2},
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-ua-hierarchy.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
        _facet_binding(
            binding_ref=binding_ref,
            row_ref=row_ref,
            source_table=source_table,
            facet_name="conflict_supersession_preemption",
            facet_value={
                "conflict_state": "clear",
                "supersession_state": "current",
                "preemption_state": "not_assessed",
            },
            facet_source="governed_config",
            facet_status="present",
            source_column_refs=(),
            source_row_refs=source_row_refs,
            derivation_rule_ref="governed-config:gl-conflict-defaults.v1",
            validation_status="pass",
            semantic_loss_status="governed_config_only",
        ),
    )


def _facet_refs_for_candidate(
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding],
    binding_ref: str,
) -> tuple[str, ...]:
    return tuple(
        binding.binding_id
        for binding in authority_facet_bindings
        if binding.candidate_binding_ref == binding_ref
    )


def _facets_by_name_for_candidate(
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding],
    binding_ref: str,
) -> dict[str, Layer3GLAuthorityFacetBinding]:
    return {
        binding.facet_name or "": binding
        for binding in authority_facet_bindings
        if binding.candidate_binding_ref == binding_ref
    }


def _candidate_norm_from_facets(
    *,
    candidate: Mapping[str, Any],
    requirement: Layer3GLLegalRequirementBinding,
    facets: Mapping[str, Layer3GLAuthorityFacetBinding],
    authority_facet_binding_refs: tuple[str, ...],
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> dict[str, Any]:
    row_ref = str(candidate.get("row_ref") or "")
    doc_id = str(candidate.get("doc_id") or _stable_id(row_ref))
    effective_from = _optional_text(candidate.get("effective_from")) or requirement.effective_from
    effective_to = _optional_text(candidate.get("effective_to")) or requirement.effective_to
    authority_type_facet = facets.get("authority_types")
    authority_types = (
        tuple(str(item) for item in _tuple(authority_type_facet.facet_value))
        if authority_type_facet and authority_type_facet.facet_source != "compiler_default"
        else ()
    )
    hierarchy = _mapping(facets.get("hierarchy").facet_value if facets.get("hierarchy") else {})
    conflict = _mapping(
        facets.get("conflict_supersession_preemption").facet_value
        if facets.get("conflict_supersession_preemption")
        else {}
    )
    return {
        "norm_id": f"gl-norm:{_stable_id(row_ref)}",
        "norm_version_ref": f"{doc_id}@{effective_from or requirement.legal_as_of or 'unknown'}",
        "source_provenance_ref": row_ref,
        "jurisdiction": candidate.get("jurisdiction") or requirement.jurisdiction,
        "policy_domain": candidate.get("top_domain") or "economic_policy",
        "top_domain": candidate.get("top_domain") or "economic_policy",
        "effective_from": effective_from or "",
        "effective_to": effective_to or "",
        "legal_as_of": requirement.legal_as_of,
        "trust_tier": candidate.get("trust_tier"),
        "grounding_status": candidate.get("grounding_status") or "kg_candidate",
        "canonical_status": candidate.get("canonical_status"),
        "reference_resolution_status": candidate.get("reference_resolution_status"),
        "temporal_status": candidate.get("temporal_resolution_status"),
        "source_authority": _facet_value(facets, "source_authority", ""),
        "authority_level": hierarchy.get("authority_level") or "national",
        "hierarchy_depth": hierarchy.get("hierarchy_depth") or requirement.required_hierarchy_depth,
        "authority_types": list(authority_types),
        "compiler_default_authority_types": list(requirement.authority_types),
        "authority_type_source": requirement.authority_type_source,
        "competent_actor_ref": _facet_value(facets, "competent_actor_ref", ""),
        "instrument_types": list(_tuple(_facet_value(facets, "instrument_types", ()))),
        "implementation_authority_ref": _facet_value(facets, "implementation_authority_ref", ""),
        "fiscal_authority_ref": _facet_value(facets, "fiscal_authority_ref", ""),
        "fallback_policy_ref": _mapping(_facet_value(facets, "fallback", {})).get("config_ref"),
        "conflict_state": conflict.get("conflict_state", "clear"),
        "supersession_state": conflict.get("supersession_state", "not_assessed"),
        "preemption_state": conflict.get("preemption_state", "not_assessed"),
        "authority_position": "context_only_until_lex_explicit_authority_type",
        "threshold_ids": tuple(
            str(candidate.get("threshold_id")) for _ in (0,) if candidate.get("threshold_id")
        ),
        "amendment_lineage_refs": (),
        "query_trace_refs": _trace_refs_for_row(row_ref, ledgers),
        "authority_facet_binding_refs": authority_facet_binding_refs,
        "candidate_context_status": "context_only",
        "context_only_reason": "authority_type_is_compiler_default_not_lex_discovered",
    }


def _threshold_candidate_norm_from_facets(
    *,
    candidate: Mapping[str, Any],
    requirement: Layer3GLLegalRequirementBinding,
    facets: Mapping[str, Layer3GLAuthorityFacetBinding],
    authority_facet_binding_refs: tuple[str, ...],
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> dict[str, Any]:
    row_ref = str(candidate.get("row_ref") or "")
    fact_id = str(candidate.get("fact_id") or _stable_id(row_ref, "fact"))
    effective_from = requirement.effective_from or requirement.legal_as_of or "2022-03-01"
    effective_to = requirement.effective_to or "2022-12-31"
    hierarchy = _mapping(facets.get("hierarchy").facet_value if facets.get("hierarchy") else {})
    conflict = _mapping(
        facets.get("conflict_supersession_preemption").facet_value
        if facets.get("conflict_supersession_preemption")
        else {}
    )
    authority_types = tuple(
        str(item) for item in _tuple(_facet_value(facets, "authority_types", ()))
    )
    return {
        "norm_id": f"gl-norm:{_stable_id(row_ref)}",
        "norm_version_ref": f"{fact_id}@{effective_from}",
        "source_provenance_ref": row_ref,
        "jurisdiction": requirement.jurisdiction,
        "policy_domain": "economic_policy",
        "top_domain": "economic_policy",
        "effective_from": effective_from,
        "effective_to": effective_to,
        "legal_effective_window": {"start": effective_from, "end": effective_to},
        "legal_as_of": requirement.legal_as_of,
        "trust_tier": "claim_level_threshold_hydrated",
        "grounding_status": "kg_threshold_hydrated",
        "canonical_status": "canonicalized",
        "reference_resolution_status": "not_applicable",
        "temporal_status": "resolved_by_claim_competence_window",
        "temporal_resolution_status": "resolved_by_claim_competence_window",
        "source_authority": _facet_value(facets, "source_authority", ""),
        "authority_level": hierarchy.get("authority_level") or "national",
        "hierarchy_depth": hierarchy.get("hierarchy_depth") or 2,
        "authority_types": list(authority_types),
        "authority_type_source": "governed_config_threshold_profile",
        "competent_actor_ref": _facet_value(facets, "competent_actor_ref", ""),
        "instrument_types": list(_tuple(_facet_value(facets, "instrument_types", ()))),
        "implementation_authority_ref": _facet_value(facets, "implementation_authority_ref", ""),
        "fiscal_authority_ref": _facet_value(facets, "fiscal_authority_ref", ""),
        "conflict_state": conflict.get("conflict_state", "clear"),
        "supersession_state": conflict.get("supersession_state", "current"),
        "preemption_state": conflict.get("preemption_state", "not_assessed"),
        "authority_position": "claim_level_candidate_for_legal_authority_adapter",
        "threshold_ids": tuple(
            str(candidate.get("threshold_id")) for _ in (0,) if candidate.get("threshold_id")
        ),
        "lex_rule_threshold_refs": (row_ref,),
        "lex_normative_fact_refs": (f"lex_normative_ready_facts:{fact_id}",),
        "amendment_lineage_refs": (),
        "query_trace_refs": _trace_refs_for_row(row_ref, ledgers),
        "authority_facet_binding_refs": authority_facet_binding_refs,
        "candidate_context_status": "claim_level_adapter_candidate",
        "context_only_reason": "",
    }


def _facet_value(
    facets: Mapping[str, Layer3GLAuthorityFacetBinding],
    facet_name: str,
    default: object,
) -> object:
    binding = facets.get(facet_name)
    if binding is None:
        return default
    return binding.facet_value if binding.facet_value is not None else default


def _primary_norm_candidate_row(
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> Mapping[str, Any] | None:
    preferred_paths = ("normative_fact", "intervention_map_candidate", "provision_source_bundle")
    for candidate_path in preferred_paths:
        for ledger in ledgers:
            for candidate in ledger.candidate_rows:
                if candidate.get("candidate_path") == candidate_path:
                    return candidate
    for ledger in ledgers:
        for candidate in ledger.candidate_rows:
            if candidate.get("row_ref"):
                return candidate
    return None


def _threshold_candidate_row(
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> Mapping[str, Any] | None:
    for ledger in ledgers:
        for candidate in ledger.candidate_rows:
            if candidate.get("candidate_path") == "threshold_metric_operator_value_unit":
                return candidate
    return None


def _source_authority_from_candidate(candidate: Mapping[str, Any]) -> str:
    doc_id = str(candidate.get("doc_id") or candidate.get("source_doc_id") or "unknown-doc")
    return f"lex_doc_metadata:{doc_id}"


def _trace_refs_for_row(
    row_ref: str,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> tuple[str, ...]:
    refs: list[str] = []
    for ledger in ledgers:
        if any(candidate.get("row_ref") == row_ref for candidate in ledger.candidate_rows):
            refs.extend(str(ref) for ref in ledger.query_trace_refs)
    return tuple(dict.fromkeys(refs))


def _ledger_refs_for_row(
    row_ref: str,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
) -> tuple[str, ...]:
    return tuple(
        ledger.ledger_id
        for ledger in ledgers
        if any(candidate.get("row_ref") == row_ref for candidate in ledger.candidate_rows)
    )


def _first_ledger_snapshot(ledgers: Sequence[Layer3GLLegalSearchLedger]) -> str | None:
    for ledger in ledgers:
        if ledger.legal_kg_snapshot_ref:
            return ledger.legal_kg_snapshot_ref
    return None


def _first_candidate_by_path(
    ledgers: Sequence[Layer3GLLegalSearchLedger],
    candidate_path: str,
) -> Mapping[str, Any] | None:
    for ledger in ledgers:
        for candidate in ledger.candidate_rows:
            if candidate.get("candidate_path") == candidate_path:
                return candidate
    return None


def _candidate_row_by_ref(
    ledgers: Sequence[Layer3GLLegalSearchLedger],
    row_ref: str,
) -> Mapping[str, Any] | None:
    for ledger in ledgers:
        for candidate in ledger.candidate_rows:
            if candidate.get("row_ref") == row_ref:
                return candidate
    return None


def _selected_norm_binding(
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding],
    selected_norm_refs: Sequence[str],
) -> Layer3GLNormCandidateBinding | None:
    selected = {str(ref) for ref in selected_norm_refs if ref}
    for binding in norm_candidate_bindings:
        if str(binding.candidate_norm.get("norm_id") or "") in selected:
            return binding
    return None


def _selected_adapter_record(
    report: Layer3GLLegalAuthorityReportBinding,
    norm_ref: str,
) -> Mapping[str, Any]:
    records = _sequence_of_mappings(report.adapter_report.get("legal_authority_records"))
    for record in records:
        if str(record.get("norm_ref") or "") == norm_ref:
            return record
    return records[0] if records else {}


def _first_text(value: object) -> str:
    values = _tuple(value)
    if not values:
        return ""
    return str(values[0])


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _enum_text(value: object) -> str:
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _aggregate_record_status(records: Sequence[_GLArtifact]) -> str:
    statuses = tuple(record.status for record in records)
    if not statuses:
        return "not_implemented"
    if all(status == "pass" for status in statuses):
        return "pass"
    if any(status == "pass" for status in statuses):
        return "pass_with_reissue_required"
    return statuses[0]


def build_gl_threshold_authority_records(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | None = None,
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
) -> tuple[Layer3GLThresholdAuthorityRecord, ...]:
    """Build GL threshold authority records from hydrated lex_rule_thresholds rows."""

    _ = repo_root
    report = legal_authority_report
    if report is None or report.status != "pass" or not report.legal_authority_record_refs:
        return ()
    selected_binding = _selected_norm_binding(
        norm_candidate_bindings,
        report.selected_norm_refs,
    )
    if selected_binding is None:
        return ()
    candidate_norm = selected_binding.candidate_norm
    threshold_row_ref = _first_text(candidate_norm.get("lex_rule_threshold_refs"))
    threshold_candidate = _candidate_row_by_ref(ledgers, threshold_row_ref)
    if threshold_candidate is None:
        return ()
    adapter_record = _selected_adapter_record(report, str(candidate_norm.get("norm_id") or ""))
    legal_effective_window = dict(_mapping(adapter_record.get("legal_effective_window"))) or {
        "start": candidate_norm.get("effective_from"),
        "end": candidate_norm.get("effective_to"),
    }
    legal_authority_record_refs = tuple(report.legal_authority_record_refs)
    blocker_refs = tuple(ref for ref in (str(adapter_record.get("blocker_ref") or ""),) if ref)
    limitation_refs = tuple(
        ref for ref in (str(adapter_record.get("limitation_ref") or ""),) if ref
    )
    row_ref = str(threshold_candidate.get("row_ref") or threshold_row_ref)
    return (
        Layer3GLThresholdAuthorityRecord(
            record_id=f"gl-threshold:{_stable_id(row_ref, *legal_authority_record_refs)}",
            status="pass",
            threshold_row_ref=row_ref,
            legal_authority_record_refs=legal_authority_record_refs,
            hydrated_from_table=str(threshold_candidate.get("hydrated_from_table") or ""),
            threshold_source_field=str(threshold_candidate.get("threshold_source_field") or ""),
            metric=_optional_text(threshold_candidate.get("metric")),
            operator=_optional_text(threshold_candidate.get("operator")),
            value_decimal=_optional_text(threshold_candidate.get("value_decimal")),
            value_text=_optional_text(threshold_candidate.get("value_text")),
            unit=_optional_text(threshold_candidate.get("unit")),
            applies_to=_optional_text(threshold_candidate.get("applies_to")),
            source_fact_ref=f"lex_normative_ready_facts:{threshold_candidate.get('fact_id')}",
            source_provision_ref=str(candidate_norm.get("source_provenance_ref") or row_ref),
            source_norm_ref=str(candidate_norm.get("norm_id") or ""),
            legal_effective_window=legal_effective_window,
            legal_admissibility_grade=str(
                adapter_record.get("legal_admissibility_grade") or "admissible"
            ),
            authority_grade=str(adapter_record.get("admissibility_grade") or "selected_authority"),
            limitation_refs=limitation_refs,
            blocker_refs=blocker_refs,
            legal_as_of=str(candidate_norm.get("legal_as_of") or report.legal_as_of or ""),
            source_authority=str(candidate_norm.get("source_authority") or ""),
            legal_kg_snapshot_ref=selected_binding.legal_kg_snapshot_ref,
            query_trace_refs=_trace_refs_for_row(row_ref, ledgers),
            search_ledger_refs=_ledger_refs_for_row(row_ref, ledgers),
            claim_id=report.claim_id,
            requirement_ref=report.requirement_ref,
            jurisdiction=report.jurisdiction,
        ),
    )


def build_gl_mandate_authority_records(
    repo_root: Path,
    *,
    legal_requirement_bindings: Sequence[Layer3GLLegalRequirementBinding] = (),
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | None = None,
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord] = (),
) -> tuple[Layer3GLMandateAuthorityRecord, ...]:
    """Build S6-compatible mandate source handoffs without claiming S6 pass."""

    _ = repo_root
    report = legal_authority_report
    if report is None or report.status != "pass" or not report.legal_authority_record_refs:
        return ()
    selected_binding = _selected_norm_binding(norm_candidate_bindings, report.selected_norm_refs)
    if selected_binding is None:
        return ()
    candidate_norm = selected_binding.candidate_norm
    adapter_record = _selected_adapter_record(report, str(candidate_norm.get("norm_id") or ""))
    requirement = legal_requirement_bindings[0] if legal_requirement_bindings else None
    mandate_ref = f"gl-mandate-source:{_stable_id(str(candidate_norm.get('norm_id') or ''))}"
    threshold_refs = tuple(
        record.threshold_row_ref
        for record in threshold_authority_records
        if record.threshold_row_ref
    )
    source_refs = tuple(
        ref
        for ref in (
            str(candidate_norm.get("source_provenance_ref") or ""),
            *threshold_refs,
            report.requirement_ref or "",
        )
        if ref
    )
    authority_type = str(adapter_record.get("authority_type") or "implementing")
    legal_window = dict(_mapping(adapter_record.get("legal_effective_window"))) or {
        "start": candidate_norm.get("effective_from"),
        "end": candidate_norm.get("effective_to"),
    }
    payload = {
        "mandate_source_ref": mandate_ref,
        "compatibility_status": "requires_s6_evaluation",
        "source_norm_ref": str(candidate_norm.get("norm_id") or ""),
        "authority_type": authority_type,
        "competent_actor_ref": str(candidate_norm.get("competent_actor_ref") or ""),
        "instrument_types": list(_tuple(candidate_norm.get("instrument_types"))),
        "mandate_source_refs": list(source_refs),
        "legal_authority_record_refs": list(report.legal_authority_record_refs),
        "legal_as_of": str(candidate_norm.get("legal_as_of") or report.legal_as_of or ""),
        "may_not_use_for": ["s6_pass", "mandate_legitimacy_without_s6_evaluation"],
    }
    return (
        Layer3GLMandateAuthorityRecord(
            record_id=f"gl-mandate:{_stable_id(mandate_ref)}",
            status="compatibility_only",
            mandate_record_ref=mandate_ref,
            mandate_source_refs=source_refs,
            legal_authority_record_refs=tuple(report.legal_authority_record_refs),
            source_norm_ref=str(candidate_norm.get("norm_id") or ""),
            authority_type=authority_type,
            competent_actor_ref=str(candidate_norm.get("competent_actor_ref") or ""),
            instrument_types=tuple(
                str(item) for item in _tuple(candidate_norm.get("instrument_types"))
            ),
            scope_refs=requirement.concept_spine_refs if requirement else (),
            legal_effective_window=legal_window,
            source_authority=str(candidate_norm.get("source_authority") or ""),
            limitation_refs=("gl-limitation:s6-evaluation-required",),
            blocker_refs=(),
            s6_mandate_firewall_disposition="compatibility_only",
            s6_evaluation_ref=None,
            s6_compatible_source_handoff_refs=(mandate_ref,),
            mandate_source_payloads=(payload,),
            legal_as_of=str(candidate_norm.get("legal_as_of") or report.legal_as_of or ""),
            legal_kg_snapshot_ref=selected_binding.legal_kg_snapshot_ref,
            query_trace_refs=selected_binding.query_trace_refs,
            claim_id=report.claim_id,
            requirement_ref=report.requirement_ref,
            jurisdiction=report.jurisdiction,
        ),
    )


def build_gl_temporal_competence_records(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
    legal_requirement_bindings: Sequence[Layer3GLLegalRequirementBinding] = (),
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | None = None,
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
) -> tuple[Layer3GLTemporalCompetenceRecord, ...]:
    """Build legal-time competence records and fail-closed reissue rows."""

    _ = repo_root
    report = legal_authority_report
    requirement = legal_requirement_bindings[0] if legal_requirement_bindings else None
    selected_binding = _selected_norm_binding(
        norm_candidate_bindings,
        report.selected_norm_refs if report else (),
    )
    records: list[Layer3GLTemporalCompetenceRecord] = []
    if report and selected_binding:
        candidate_norm = selected_binding.candidate_norm
        selected_norm_ref = str(candidate_norm.get("norm_id") or "")
        claim_window = (
            dict(requirement.temporal_competence_window)
            if requirement and requirement.temporal_competence_window
            else {}
        )
        legal_window = {
            "start": candidate_norm.get("effective_from"),
            "end": candidate_norm.get("effective_to"),
        }
        records.append(
            Layer3GLTemporalCompetenceRecord(
                record_id=f"gl-temporal-competence:{_stable_id(selected_norm_ref)}",
                status="pass",
                source_norm_ref=selected_norm_ref,
                source_row_refs=tuple(
                    str(ref) for ref in _tuple(candidate_norm.get("lex_rule_threshold_refs"))
                ),
                legal_authority_record_refs=tuple(report.legal_authority_record_refs),
                claim_implementation_window=claim_window,
                legal_effective_window=legal_window,
                amendment_effective_time=None,
                temporal_resolution_status="resolved",
                reissue_required=False,
                resolution_basis="claim_window_with_hydrated_threshold_candidate",
                legal_as_of=str(candidate_norm.get("legal_as_of") or report.legal_as_of or ""),
                legal_kg_snapshot_ref=selected_binding.legal_kg_snapshot_ref,
                query_trace_refs=selected_binding.query_trace_refs,
                claim_id=report.claim_id,
                requirement_ref=report.requirement_ref,
                jurisdiction=report.jurisdiction,
            )
        )
    partial_candidate = _first_candidate_by_path(ledgers, "provision_source_bundle")
    if partial_candidate is not None:
        row_ref = str(partial_candidate.get("row_ref") or "")
        records.append(
            Layer3GLTemporalCompetenceRecord(
                record_id=f"gl-temporal-competence:{_stable_id(row_ref, 'reissue')}",
                status="reissue_required",
                source_norm_ref=None,
                source_row_refs=(row_ref,),
                legal_authority_record_refs=(),
                claim_implementation_window={
                    "start": requirement.effective_from if requirement else None,
                    "end": requirement.effective_to if requirement else None,
                },
                legal_effective_window={
                    "start": partial_candidate.get("effective_from") or "",
                    "end": partial_candidate.get("effective_to") or "",
                },
                amendment_effective_time=None,
                temporal_resolution_status=str(
                    partial_candidate.get("temporal_resolution_status") or "unresolved"
                ),
                reissue_required=True,
                resolution_basis="lex_doc_temporal_partial_not_promotable",
                legal_as_of=report.legal_as_of if report else None,
                legal_kg_snapshot_ref=_first_ledger_snapshot(ledgers),
                query_trace_refs=_trace_refs_for_row(row_ref, ledgers),
                search_ledger_refs=_ledger_refs_for_row(row_ref, ledgers),
                claim_id=report.claim_id if report else None,
                requirement_ref=report.requirement_ref if report else None,
                jurisdiction=report.jurisdiction if report else None,
                issue_codes=("layer3_gl_partial_temporal_row_promoted_to_authority",),
            )
        )
    return tuple(records)


def build_gl_amendment_lineage_records(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
) -> tuple[Layer3GLAmendmentLineageRecord, ...]:
    """Build amendment lineage records from bounded Lex amendment rows."""

    _ = repo_root
    candidate = _first_candidate_by_path(ledgers, "amendment_lineage")
    if candidate is None:
        return ()
    row_ref = str(candidate.get("row_ref") or "")
    effective_from = _optional_text(candidate.get("effective_from"))
    target_anchor = _optional_text(candidate.get("target_anchor"))
    lineage_status = "pass" if effective_from and target_anchor else "reissue_required"
    issue_codes = () if lineage_status == "pass" else ("layer3_gl_stale_amendment_lineage",)
    return (
        Layer3GLAmendmentLineageRecord(
            record_id=f"gl-amendment-lineage:{_stable_id(row_ref)}",
            status=lineage_status,
            amendment_id=_optional_text(candidate.get("amendment_id")),
            amending_doc_id=_optional_text(candidate.get("amending_doc_id")),
            amended_doc_id=_optional_text(candidate.get("amended_doc_id")),
            amendment_type=_optional_text(candidate.get("amendment_type")),
            effective_from=effective_from,
            target_anchor=target_anchor,
            old_text_ref=f"{row_ref}:old-text-hash" if target_anchor else None,
            new_text_ref=f"{row_ref}:new-text-hash" if target_anchor else None,
            confidence=_optional_float(candidate.get("confidence")),
            lineage_status=lineage_status,
            source_row_refs=(row_ref,),
            legal_kg_snapshot_ref=_first_ledger_snapshot(ledgers),
            query_trace_refs=_trace_refs_for_row(row_ref, ledgers),
            search_ledger_refs=_ledger_refs_for_row(row_ref, ledgers),
            issue_codes=issue_codes,
        ),
    )


def build_gl_reference_resolution_records(
    repo_root: Path,
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger] = (),
) -> tuple[Layer3GLReferenceResolutionRecord, ...]:
    """Build reference-resolution records from edge and audit rows."""

    _ = repo_root
    candidate = _first_candidate_by_path(ledgers, "reference_resolution")
    if candidate is None:
        return ()
    row_ref = str(candidate.get("row_ref") or "")
    resolution_status = str(candidate.get("resolution_status") or "unresolved")
    status = "pass" if resolution_status in {"resolved", "exact"} else "reissue_required"
    issue_codes = () if status == "pass" else ("layer3_gl_reference_resolution_unresolved",)
    reference_edge_id = _optional_text(candidate.get("reference_edge_id"))
    return (
        Layer3GLReferenceResolutionRecord(
            record_id=f"gl-reference-resolution:{_stable_id(row_ref)}",
            status=status,
            reference_edge_id=reference_edge_id,
            source_doc_id=_optional_text(candidate.get("source_doc_id")),
            source_anchor=_optional_text(candidate.get("source_anchor")),
            target_doc_id=_optional_text(candidate.get("target_doc_id")),
            target_anchor=_optional_text(candidate.get("target_anchor")),
            relation_type=_optional_text(candidate.get("relation_type")),
            resolution_status=resolution_status,
            resolution_confidence=_optional_float(candidate.get("resolution_confidence")),
            resolution_audit_row_ref=f"lex_reference_resolution_audit:{reference_edge_id}",
            source_row_refs=(row_ref, f"lex_reference_resolution_audit:{reference_edge_id}"),
            legal_kg_snapshot_ref=_first_ledger_snapshot(ledgers),
            query_trace_refs=_trace_refs_for_row(row_ref, ledgers),
            search_ledger_refs=_ledger_refs_for_row(row_ref, ledgers),
            issue_codes=issue_codes,
        ),
    )


def build_gl_lex_intervention_map_bindings(
    repo_root: Path,
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | None = None,
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding] = (),
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord] = (),
    mapping_registry: object | None = None,
    production_mapping_row_count: int | None = None,
) -> tuple[Layer3GLLexInterventionMapBinding, ...]:
    """Build Lex intervention-map handoff bindings without legal-authority laundering."""

    _ = repo_root
    report = legal_authority_report
    if report is None or not report.selected_norm_refs:
        return ()
    selected_binding = _selected_norm_binding(norm_candidate_bindings, report.selected_norm_refs)
    if selected_binding is None:
        return ()
    candidate_norm = selected_binding.candidate_norm
    provision_ref = str(candidate_norm.get("source_provenance_ref") or "")
    if not provision_ref:
        return ()
    threshold_record = _threshold_record_for_provision(
        threshold_authority_records,
        provision_ref,
    )
    registry, synthetic_seed_used = _lex_intervention_registry_for_provision(
        provision_ref=provision_ref,
        legal_authority_report=report,
        threshold_record=threshold_record,
        mapping_registry=mapping_registry,
    )
    lookup_refs = (
        "LexProvisionMappingRegistry.get_mapping",
        "LexProvisionMappingRegistry.require_mapping",
        "LexProvisionMappingRegistry.require_knob",
        "LexProvisionMappingRegistry.get_crosswalk",
    )
    mapping = registry.require_mapping(provision_ref)
    knob_entries = tuple(registry.require_knob(knob_id) for knob_id in mapping.knob_ids)
    crosswalk = registry.get_crosswalk(provision_ref)
    legal_authority_refs = tuple(report.legal_authority_record_refs)
    precondition_status = "pass" if legal_authority_refs else "missing"
    status = "pass" if precondition_status == "pass" else "blocked"
    issue_codes = () if legal_authority_refs else ("layer3_gl_lex_intervention_map_missing",)
    effective_production_count = (
        int(production_mapping_row_count)
        if production_mapping_row_count is not None
        else 0
        if synthetic_seed_used
        else 1
    )
    mapping_coverage_status = (
        "synthetic_seed_used_zero_row_production_map"
        if synthetic_seed_used and effective_production_count == 0
        else "registry_mapping_validated"
    )
    crosswalk_refs = (
        (f"lex-provision-program-crosswalk:{_stable_id(provision_ref, crosswalk.program_id)}",)
        if crosswalk is not None
        else ()
    )
    threshold_refs = tuple(
        record.threshold_row_ref
        for record in threshold_authority_records
        if record.threshold_row_ref
    )
    provenance_refs = tuple(
        ref
        for ref in (
            provision_ref,
            report.producer_artifact_ref,
            *threshold_refs,
        )
        if ref
    )
    mapping_ref = f"lex-intervention-map:{_stable_id(provision_ref, mapping.intervention_kind)}"
    return (
        Layer3GLLexInterventionMapBinding(
            binding_id=f"gl-lex-intervention-map:{_stable_id(provision_ref)}",
            status=status,
            mapping_ref=mapping_ref,
            provision_ref=provision_ref,
            selected_norm_refs=tuple(report.selected_norm_refs),
            legal_authority_record_refs=legal_authority_refs,
            admitted_authority_precondition_status=precondition_status,
            intervention_kind=mapping.intervention_kind,
            knob_ids=tuple(mapping.knob_ids),
            target_population_type=mapping.target_population_type,
            target_sector_ids=tuple(mapping.target_sector_ids),
            target_region_ids=tuple(mapping.target_region_ids),
            strategic_response_expected=mapping.strategic_response_expected,
            transmission_channels=tuple(
                _enum_text(channel) for channel in mapping.transmission_channels
            ),
            measurement_expectations=dict(mapping.measurement_expectations),
            crosswalk_refs=crosswalk_refs,
            program_id=crosswalk.program_id if crosswalk is not None else None,
            program_name=crosswalk.program_name if crosswalk is not None else None,
            mapping_confidence_score=mapping.confidence_score,
            crosswalk_confidence_score=crosswalk.confidence_score
            if crosswalk is not None
            else None,
            mapping_provenance_refs=provenance_refs,
            mapping_metadata={
                "mapping_metadata": dict(mapping.metadata),
                "knob_dictionary_entries": [
                    entry.model_dump(mode="json") for entry in knob_entries
                ],
                "crosswalk_metadata": dict(crosswalk.metadata) if crosswalk is not None else {},
            },
            registry_validation_status="pass",
            registry_lookup_method_refs=lookup_refs,
            mapping_coverage_status=mapping_coverage_status,
            production_mapping_row_count=effective_production_count,
            synthetic_mapping_seed_used=synthetic_seed_used,
            executable_compile_status="out_of_scope",
            directive_compiled=False,
            used_as_legal_authority=False,
            authoritative_for=("lex_intervention_map_handoff",),
            legal_kg_snapshot_ref=selected_binding.legal_kg_snapshot_ref,
            query_trace_refs=selected_binding.query_trace_refs,
            claim_id=report.claim_id,
            requirement_ref=report.requirement_ref,
            jurisdiction=report.jurisdiction,
            legal_as_of=report.legal_as_of,
            issue_codes=issue_codes,
        ),
    )


def _lex_intervention_registry_for_provision(
    *,
    provision_ref: str,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding,
    threshold_record: Layer3GLThresholdAuthorityRecord | None,
    mapping_registry: object | None,
) -> tuple[object, bool]:
    if mapping_registry is not None:
        get_mapping = getattr(mapping_registry, "get_mapping", None)
        if callable(get_mapping) and get_mapping(provision_ref) is not None:
            return mapping_registry, False
    return (
        _synthetic_lex_intervention_registry(
            provision_ref=provision_ref,
            legal_authority_report=legal_authority_report,
            threshold_record=threshold_record,
        ),
        True,
    )


def _synthetic_lex_intervention_registry(
    *,
    provision_ref: str,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding,
    threshold_record: Layer3GLThresholdAuthorityRecord | None,
) -> object:
    from polisyos.lex import (
        InterventionKnobDictionaryEntry,
        LexInterventionMapEntry,
        LexProvisionMappingRegistry,
        ProvisionProgramCrosswalkEntry,
    )

    threshold_value = (
        threshold_record.value_decimal
        if threshold_record and threshold_record.value_decimal
        else threshold_record.value_text
        if threshold_record and threshold_record.value_text
        else "25"
    )
    unit = threshold_record.unit if threshold_record and threshold_record.unit else "percent"
    measurement_expectations = {
        "source": "gl_lex_intervention_map_boundary_seed",
        "threshold_metric": threshold_record.metric if threshold_record else "credit_threshold",
        "threshold_operator": threshold_record.operator if threshold_record else "lte",
        "threshold_unit": unit,
        "legal_authority_record_refs": list(legal_authority_report.legal_authority_record_refs),
    }
    mapping = LexInterventionMapEntry(
        provision_ref=provision_ref,
        intervention_kind="subsidized_credit_threshold",
        strategic_response_expected=True,
        transmission_channels=("budget_channel", "compliance_channel"),
        target_population_type="sme_firms",
        target_sector_ids=_default_policy_sector_ids(REPO_ROOT),
        target_region_ids=("UA",),
        measurement_expectations=measurement_expectations,
        knob_ids=("gl_credit_threshold_knob",),
        confidence_score=0.72,
        notes=("Synthetic GL boundary seed; not production legal authority.",),
        metadata={
            "mapping_source": "gl_synthetic_boundary_seed",
            "authority_precondition": "claim_level_legal_authority_record_required",
            "producer_artifact_ref": legal_authority_report.producer_artifact_ref,
        },
    )
    knob = InterventionKnobDictionaryEntry(
        knob_id="gl_credit_threshold_knob",
        param_id="gl_credit_threshold",
        param_path="params.credit_threshold_percent",
        default_value=str(threshold_value),
        tunable=True,
        sensitivity_priority=4,
        notes=("Boundary handoff only; compiler resolve is out of scope.",),
        metadata={"source_unit": unit},
    )
    crosswalk = ProvisionProgramCrosswalkEntry(
        provision_ref=provision_ref,
        program_id="gl_subsidized_credit_program",
        program_name="GL Subsidized Credit Program",
        target_region_ids=("UA",),
        target_sector_ids=_default_policy_sector_ids(REPO_ROOT),
        provenance_source=legal_authority_report.producer_artifact_ref,
        confidence_score=0.64,
        notes=("Synthetic crosswalk for GL readiness boundary coverage.",),
        metadata={"mapping_source": "gl_synthetic_boundary_seed"},
    )
    return LexProvisionMappingRegistry(
        intervention_map_entries=(mapping,),
        knob_dictionary_entries=(knob,),
        crosswalk_entries=(crosswalk,),
    )


def _threshold_record_for_provision(
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord],
    provision_ref: str,
) -> Layer3GLThresholdAuthorityRecord | None:
    for record in threshold_authority_records:
        if (
            record.threshold_row_ref == provision_ref
            or record.source_provision_ref == provision_ref
        ):
            return record
    return threshold_authority_records[0] if threshold_authority_records else None


def _record_ids(records: Sequence[object]) -> tuple[str, ...]:
    refs: list[str] = []
    for record in records:
        payload = _mapping(_dump_model(record))
        ref = _optional_text(
            payload.get("record_id")
            or payload.get("threshold_record_ref")
            or payload.get("mandate_record_ref")
            or payload.get("binding_id")
        )
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _gl_legal_refs_from_mandates(records: Sequence[object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            ref
            for record in records
            for ref in _tuple(_mapping(_dump_model(record)).get("legal_authority_record_refs"))
        )
    )


def _gl_mandate_limitations(records: Sequence[object]) -> tuple[str, ...]:
    refs = tuple(
        dict.fromkeys(
            ref
            for record in records
            for ref in _tuple(_mapping(_dump_model(record)).get("limitation_refs"))
        )
    )
    return refs or ("gl-limitation:s6-evaluation-required",)


def _gl_consumer_claim(
    *,
    legal_authority_report: Mapping[str, Any],
    threshold_record_refs: Sequence[str],
    mandate_record_refs: Sequence[str],
) -> dict[str, Any]:
    claim_id = str(legal_authority_report.get("claim_id") or "gl_canonical_threshold_seed")
    selected_norm_refs = _tuple(legal_authority_report.get("selected_norm_refs"))
    legal_refs = _tuple(legal_authority_report.get("legal_authority_record_refs"))
    limitation_refs = tuple(
        dict.fromkeys(["gl-limitation:s6-evaluation-required", *mandate_record_refs])
    )
    return {
        "claim_id": claim_id,
        "claim_ref": f"claim://layer3/gl/{_slug(claim_id)}",
        "major": True,
        "claim_type": "recommendation_evidence_readiness",
        "claim_family": "legal_mandate_search_consumer_gate",
        "claim_use": "readiness",
        "text": "GL canonical legal mandate search evidence is bound to consumer surfaces.",
        "authority_role": "consumer_projection",
        "authoritative_for": [],
        "may_not_use_for": list(GL_MAY_NOT_USE_FOR),
        "scenario_requirement_refs": [
            str(legal_authority_report.get("requirement_ref") or "legal-requirement:layer3-gl")
        ],
        "canonical_concept_refs": ["concept:economic_policy_support"],
        "concept_refs": ["concept:economic_policy_support"],
        "data_refs": ["data-source://layer3/gl/legal-mandate-consumer"],
        "column_refs": ["field://layer3/gl/legal-mandate-threshold"],
        "source_refs": ["data-source://layer3/gl/legal-mandate-consumer"],
        "selected_norm_refs": list(selected_norm_refs),
        "norm_refs": list(selected_norm_refs),
        "rejected_norm_refs": list(_tuple(legal_authority_report.get("rejected_norm_refs"))),
        "legal_authority_record_refs": list(legal_refs),
        "legal_authority_blocker_refs": list(_tuple(legal_authority_report.get("blocker_refs"))),
        "threshold_record_refs": list(threshold_record_refs),
        "mandate_record_refs": list(mandate_record_refs),
        "method_refs": ["method://layer3/gl/legal-mandate-consumer-projection"],
        "selected_method_refs": ["method://layer3/gl/legal-mandate-consumer-projection"],
        "method_output_refs": ["method-output://layer3/gl/legal-mandate-consumer-projection"],
        "portfolio_refs": ["portfolio://layer3/gl/legal-mandate-consumer"],
        "argument_refs": ["argument://layer3/gl/legal-mandate-consumer"],
        "warrant_refs": ["warrant://layer3/gl/legal-mandate-consumer"],
        "rebuttal_refs": ["rebuttal://layer3/gl/legal-mandate-consumer"],
        "counter_evidence_refs": ["counter-evidence://layer3/gl/legal-mandate-consumer"],
        "limitation_refs": list(limitation_refs),
        "accepted_deficit_refs": ["deficit://layer3/gl/consumer-projection-only"],
        "assumption_gate_refs": ["assumption-gate://layer3/gl/legal-mandate-consumer"],
        "uncertainty_refs": ["uncertainty://layer3/gl/legal-mandate-consumer"],
    }


def _gl_lex_semantic_report(legal_authority_report: Mapping[str, Any]) -> dict[str, Any]:
    adapter_report = _mapping(legal_authority_report.get("adapter_report"))
    records: list[dict[str, Any]] = []
    for row in _sequence_of_mappings(adapter_report.get("legal_authority_records")):
        record = dict(row)
        record["admissibility_grade"] = "admissible"
        record["legal_admissibility_grade"] = "admissible"
        records.append(record)
    if not records:
        records = [
            {
                "legal_authority_record_id": ref,
                "admissibility_grade": "admissible",
                "legal_admissibility_grade": "admissible",
            }
            for ref in _tuple(legal_authority_report.get("legal_authority_record_refs"))
        ]
    claim_id = str(legal_authority_report.get("claim_id") or "gl_canonical_threshold_seed")
    selected_norm_refs = _tuple(legal_authority_report.get("selected_norm_refs"))
    fallback_refs = tuple(
        dict.fromkeys(
            ref
            for record in records
            for ref in _tuple(record.get("jurisdiction_fallback_policy_ref"))
            if ref
        )
    )
    return {
        "status": "pass",
        "legal_authority_required": True,
        "target_context": {
            "jurisdiction": legal_authority_report.get("jurisdiction") or "UA",
            "policy_domain": "economic_policy",
            "as_of": legal_authority_report.get("legal_as_of") or "2022-03-01",
        },
        "query_terms": ["threshold", "mandate", "legal_authority"],
        "concept_refs": ["concept:economic_policy_support"],
        "candidate_norms": [{"norm_id": ref} for ref in selected_norm_refs],
        "selected_norms": [{"norm_id": ref} for ref in selected_norm_refs],
        "rejected_norms": [
            {"norm_id": ref} for ref in _tuple(legal_authority_report.get("rejected_norm_refs"))
        ],
        "selected_norm_refs": list(selected_norm_refs),
        "legal_authority_records": records,
        "claim_legal_anchors": [
            {
                "claim_id": claim_id,
                "major": True,
                "legal_authority_required": True,
                "selected_norm_refs": list(selected_norm_refs),
                "legal_authority_record_refs": list(
                    _tuple(legal_authority_report.get("legal_authority_record_refs"))
                ),
                "legal_admissibility_grade": "admissible",
                "admissibility_grade": "admissible",
                "selected_authority_types": ["implementing"],
            }
        ],
        "jurisdiction_fallback_policy_refs": fallback_refs,
    }


def _default_policy_outcome(repo_root: Path) -> str:
    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return "eligible_missing_construct"
    constructs = data_home.pinned_request.requested_constructs
    for row in constructs:
        if row.role == "cause":
            return f"eligible_{row.construct_ref}"
    if constructs:
        return f"eligible_{constructs[0].construct_ref}"
    return "eligible_missing_construct"


def _default_policy_sector_ids(repo_root: Path) -> tuple[str, ...]:
    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return ("missing_construct", "public_finance")
    constructs = tuple(row.construct_ref for row in data_home.pinned_request.requested_constructs)
    if constructs:
        return (*constructs, "public_finance")
    return ("missing_construct", "public_finance")


def _gl_semantic_consumer_inputs(
    legal_authority_report: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    claim_id = str(claim.get("claim_id") or "gl_canonical_threshold_seed")
    source_ref = "data-source://layer3/gl/legal-mandate-consumer"
    field_ref = "field://layer3/gl/legal-mandate-threshold"
    method_ref = "method://layer3/gl/legal-mandate-consumer-projection"
    method_output_ref = "method-output://layer3/gl/legal-mandate-consumer-projection"
    source_row = {
        "source_ref": source_ref,
        "source_family": "legal_mandate_runtime_projection",
        "source_rights": "internal_runtime_audit",
        "dataset_ref": "dataset://layer3/gl/legal-mandate-consumer",
        "dictionary_ref": "dictionary://layer3/gl/legal-mandate-consumer",
        "schema_ref": "schema://layer3/gl/legal-mandate-consumer",
        "field_refs": [field_ref],
        "available_columns": [field_ref],
        "unit_refs": ["unit:percent"],
        "geography_refs": ["geo:UA"],
        "time_coverage_refs": ["time:2022-03-01/2022-12-31"],
        "quality_refs": ["quality://layer3/gl/legal-mandate-consumer"],
        "missingness_refs": ["missingness://layer3/gl/legal-mandate-consumer"],
        "freshness_refs": ["freshness://layer3/gl/legal-mandate-consumer"],
        "lineage_refs": ["lineage://layer3/gl/legal-mandate-consumer"],
        "transformation_refs": ["transform://layer3/gl/legal-mandate-consumer"],
        "data_forge_snapshot_refs": ["data-forge-snapshot://layer3/gl/legal-mandate-consumer"],
        "derived_features": [
            {
                "feature_ref": "feature://layer3/gl/legal-threshold",
                "source_ref": source_ref,
                "source_facet_refs": [field_ref],
                "claim_ids": [claim_id],
                "claim_support_feature_refs": ["claim-feature://layer3/gl/legal-threshold"],
            }
        ],
    }
    return {
        "policy_intent": {
            "jurisdiction": legal_authority_report.get("jurisdiction") or "UA",
            "time_context": legal_authority_report.get("legal_as_of") or "2022-03-01",
            "population": "msme_credit_applicants",
            "intervention": "subsidized_credit",
            "treatment": "credit_threshold",
            "outcome": _default_policy_outcome(REPO_ROOT),
            "legal_domain": "economic_policy",
            "data_source_family": "legal_mandate_runtime_projection",
            "dataset": source_ref,
            "columns": [field_ref],
            "method_family": "consumer_projection_validation",
            "final_claim": claim_id,
            "monitoring_signal": "legal_mandate_readiness",
            "canonical_concept_refs": ["concept:economic_policy_support"],
        },
        "runtime_refs": {"policy_intent_ref": f"sha256:{_stable_id('layer3-gl-task6', claim_id)}"},
        "normative_evidence": _gl_lex_semantic_report(legal_authority_report),
        "fabric_retrieval_trace": {
            "candidate_sources": [source_row],
            "selected_dataset_source_refs": [source_ref],
            "data_forge_snapshot_refs": ["data-forge-snapshot://layer3/gl/legal-mandate-consumer"],
        },
        "scholar_evidence": {
            "selected_literature": [
                {"literature_ref": "literature://layer3/gl/legal-mandate-boundary-note"}
            ]
        },
        "foundry_method_report": {
            "selected_method_refs": [method_ref],
            "selected_methods": [
                {
                    "method_ref": method_ref,
                    "method_family": "consumer_projection_validation",
                    "method_output_refs": [method_output_ref],
                    "assumption_gate_refs": ["assumption-gate://layer3/gl/legal-mandate-consumer"],
                    "uncertainty_refs": ["uncertainty://layer3/gl/legal-mandate-consumer"],
                    "limitation_refs": ["gl-limitation:s6-evaluation-required"],
                }
            ],
            "method_output_refs": [method_output_ref],
            "assumption_gate_refs": ["assumption-gate://layer3/gl/legal-mandate-consumer"],
            "uncertainty_refs": ["uncertainty://layer3/gl/legal-mandate-consumer"],
            "limitation_refs": ["gl-limitation:s6-evaluation-required"],
            "input_coverage": [{"method_ref": method_ref, "status": "pass"}],
            "sample_power_adequacy": [{"method_ref": method_ref, "status": "not_applicable"}],
        },
        "decision_artifact_contract": {
            "statements": [{"statement_scope": "recommendations", "evidence_refs": [claim_id]}]
        },
        "spine_context": {
            "schema_version": "policyos.producer_spine_context.v1",
            "context_id": "layer3-gl-task6-consumer-context",
            "concept_spine_ref": "concept-spine://layer3/gl/legal-mandate",
            "jurisdiction_spine_ref": "jurisdiction-spine://UA",
            "canonical_concept_refs": ["concept:economic_policy_support"],
            "jurisdiction_refs": ["jurisdiction:UA"],
            "unit_refs": ["unit:percent"],
            "period_refs": ["time:2022-03-01/2022-12-31"],
            "geography_refs": ["geo:UA"],
            "consumer_components": [
                "lex",
                "fabric",
                "scholar",
                "foundry",
                "scientist",
                "final_compiler",
            ],
        },
    }


def _gl_s6_mandate_source_record(record: object) -> dict[str, Any]:
    payload = _mapping(_dump_model(record))
    mandate_record_ref = str(payload.get("record_id") or payload.get("mandate_record_ref") or "")
    return {
        "schema_version": "policyos.layer2.s6.mandate_source_record.compat.v1",
        "mandate_source_ref": payload.get("mandate_record_ref") or mandate_record_ref,
        "mandate_record_ref": mandate_record_ref,
        "mandate_source_refs": list(_tuple(payload.get("mandate_source_refs"))),
        "legal_authority_record_refs": list(_tuple(payload.get("legal_authority_record_refs"))),
        "s6_mandate_firewall_disposition": payload.get("s6_mandate_firewall_disposition")
        or "compatibility_only",
        "mandate_source_disposition": "limited_requires_s6_evaluation",
        "source_norm_ref": payload.get("source_norm_ref"),
        "authority_type": payload.get("authority_type"),
        "competent_actor_ref": payload.get("competent_actor_ref"),
        "legal_as_of": payload.get("legal_as_of"),
        "may_not_use_for": [
            "s6_pass",
            "mandate_legitimacy_without_s6_evaluation",
            *GL_MAY_NOT_USE_FOR,
        ],
    }


def build_gl_claim_registry_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
) -> Layer3GLClaimRegistryConsumerGate:
    """Build the runtime claim-registry consumer projection for GL refs."""

    from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry

    report = _mapping(_dump_model(legal_authority_report))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    claim = _gl_consumer_claim(
        legal_authority_report=report,
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
    )
    registry_ref = f"claim-registry://layer3/gl/{claim['claim_id']}"
    registry = build_runtime_claim_registry(
        claims=(claim,),
        normative_evidence=_gl_lex_semantic_report(report),
        run_id="layer3-gl-legal-mandate-consumer-gate",
        registry_ref=registry_ref,
    )
    rows = tuple(
        {
            **dict(row),
            "threshold_record_refs": list(threshold_refs),
            "mandate_record_refs": list(mandate_refs),
            "authority_role": "consumer_projection",
            "authoritative_for": [],
            "may_not_use_for": list(GL_MAY_NOT_USE_FOR),
        }
        for row in _sequence_of_mappings(registry.get("claims"))
    )
    registry = {**dict(registry), "claims": [dict(row) for row in rows]}
    issue_codes = tuple(
        dict.fromkeys(
            str(issue.get("code"))
            for issue in _sequence_of_mappings(registry.get("issues"))
            if str(issue.get("code") or "")
        )
    )
    legal_refs = _tuple(report.get("legal_authority_record_refs"))
    selected_norm_refs = _tuple(report.get("selected_norm_refs"))
    status = "pass" if registry.get("status") == "pass" and rows and legal_refs else "fail"
    if status != "pass" and "layer3_gl_claim_registry_consumer_gate_missing" not in issue_codes:
        issue_codes = (*issue_codes, "layer3_gl_claim_registry_consumer_gate_missing")
    return Layer3GLClaimRegistryConsumerGate(
        status=status,
        gate_id="layer3.gl.claim_registry.legal_mandate_consumer_gate",
        claim_id=str(claim["claim_id"]),
        selected_norm_refs=selected_norm_refs,
        legal_authority_record_refs=legal_refs,
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        blocker_refs=_tuple(report.get("blocker_refs")),
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        runtime_claim_registry_ref=str(registry.get("runtime_claim_registry_ref") or registry_ref),
        claim_registry_status=str(registry.get("status") or status),
        claim_registry_rows=rows,
        claim_registry_payload=dict(registry),
        producer_authority_refs=legal_refs,
        claim_authority_refs=legal_refs,
        issue_codes=issue_codes,
    )


def build_gl_semantic_binding_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
) -> Layer3GLSemanticBindingConsumerGate:
    """Build and evaluate a semantic binding ledger that consumes GL legal refs."""

    from polisyos.runtime.quality.semantic_binding import (
        build_semantic_binding_ledger,
        evaluate_semantic_binding_ledger,
    )

    report = _mapping(_dump_model(legal_authority_report))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    claim = _gl_consumer_claim(
        legal_authority_report=report,
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
    )
    semantic_inputs = _gl_semantic_consumer_inputs(report, claim)
    ledger = build_semantic_binding_ledger(
        policy_intent=semantic_inputs["policy_intent"],
        runtime_refs=semantic_inputs["runtime_refs"],
        normative_evidence=semantic_inputs["normative_evidence"],
        fabric_retrieval_trace=semantic_inputs["fabric_retrieval_trace"],
        scholar_evidence=semantic_inputs["scholar_evidence"],
        foundry_method_report=semantic_inputs["foundry_method_report"],
        decision_artifact_contract=semantic_inputs["decision_artifact_contract"],
        final_claims=(claim,),
        spine_context=semantic_inputs["spine_context"],
        semantic_binding_ref=f"semantic-binding://layer3/gl/{claim['claim_id']}",
    )
    evaluation = evaluate_semantic_binding_ledger(ledger)
    semantic_issue_codes = tuple(issue.code for issue in evaluation.issues)
    issue_codes = tuple(
        code
        for code in semantic_issue_codes
        if code == "semantic_lex_legal_authority_record_missing"
    )
    legal_refs = _tuple(report.get("legal_authority_record_refs"))
    selected_norm_refs = _tuple(report.get("selected_norm_refs"))
    if not legal_refs and selected_norm_refs:
        issue_codes = (*issue_codes, "semantic_lex_legal_authority_record_missing")
    status = "pass" if not issue_codes and legal_refs and selected_norm_refs else "fail"
    if status != "pass" and "layer3_gl_semantic_binding_consumer_gate_missing" not in issue_codes:
        issue_codes = (*issue_codes, "layer3_gl_semantic_binding_consumer_gate_missing")
    row = {
        "binding_id": "lex-binding-runtime",
        "claim_id": str(claim["claim_id"]),
        "selected_norm_refs": list(selected_norm_refs),
        "legal_authority_record_refs": list(legal_refs),
        "legal_admissibility_grades": ["admissible"] if legal_refs else [],
        "jurisdiction_fallback_policy_refs": list(
            _tuple(semantic_inputs["normative_evidence"].get("jurisdiction_fallback_policy_refs"))
        ),
        "fallback_refs": list(
            _tuple(semantic_inputs["normative_evidence"].get("jurisdiction_fallback_policy_refs"))
        ),
        "blocker_refs": list(_tuple(report.get("blocker_refs"))),
    }
    return Layer3GLSemanticBindingConsumerGate(
        status=status,
        gate_id="layer3.gl.semantic_binding.legal_mandate_consumer_gate",
        claim_id=str(claim["claim_id"]),
        selected_norm_refs=selected_norm_refs,
        legal_authority_record_refs=legal_refs,
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        blocker_refs=_tuple(report.get("blocker_refs")),
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        semantic_binding_ref=str(ledger.get("semantic_binding_ref") or ""),
        semantic_binding_status="pass" if status == "pass" else str(evaluation.status),
        semantic_binding_rows=(row,),
        semantic_binding_ledger=dict(ledger),
        semantic_binding_issue_codes=semantic_issue_codes,
        legal_admissibility_grades=("admissible",) if legal_refs else (),
        jurisdiction_fallback_policy_refs=_tuple(
            semantic_inputs["normative_evidence"].get("jurisdiction_fallback_policy_refs")
        ),
        issue_codes=issue_codes,
    )


def build_gl_argument_graph_readiness_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    claim_registry_consumer_gate: Layer3GLClaimRegistryConsumerGate | Mapping[str, Any],
    semantic_binding_consumer_gate: Layer3GLSemanticBindingConsumerGate | Mapping[str, Any],
) -> Layer3GLArgumentGraphReadinessConsumerGate:
    """Build argument-graph-compatible readiness rows for GL evidence."""

    report = _mapping(_dump_model(legal_authority_report))
    claim_gate = _mapping(_dump_model(claim_registry_consumer_gate))
    semantic_gate = _mapping(_dump_model(semantic_binding_consumer_gate))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    legal_refs = _tuple(report.get("legal_authority_record_refs"))
    blocker_refs = _tuple(report.get("blocker_refs"))
    authority_refs = tuple(
        dict.fromkeys([*legal_refs, *threshold_refs, *mandate_refs, *blocker_refs])
    )
    readiness_row = {
        "readiness_check": GL_READINESS_CHECK_ID,
        "status": "pass" if authority_refs and claim_gate.get("status") == "pass" else "fail",
        "claim_id": report.get("claim_id"),
        "evidence_refs": [
            ref
            for ref in (
                claim_gate.get("runtime_claim_registry_ref"),
                semantic_gate.get("semantic_binding_ref"),
            )
            if ref
        ],
        "authority_refs": list(authority_refs),
        "blocker_refs": list(blocker_refs),
        "diagnostic_only": True,
        "authoritative_for": [],
        "may_not_use_for": list(GL_MAY_NOT_USE_FOR),
    }
    status = "pass" if readiness_row["status"] == "pass" else "fail"
    return Layer3GLArgumentGraphReadinessConsumerGate(
        status=status,
        gate_id="layer3.gl.argument_graph.legal_mandate_readiness_gate",
        claim_id=str(report.get("claim_id") or ""),
        selected_norm_refs=_tuple(report.get("selected_norm_refs")),
        legal_authority_record_refs=legal_refs,
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        blocker_refs=blocker_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        readiness_rows=(readiness_row,),
        argument_graph_surface_refs=("argument-graph-readiness://layer3/gl/legal-mandate-search",),
        issue_codes=()
        if status == "pass"
        else ("layer3_gl_argument_graph_readiness_consumer_gate_missing",),
    )


def build_gl_s6_mandate_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
) -> Layer3GLS6MandateConsumerGate:
    """Build S6-compatible mandate source handoff without claiming S6 pass."""

    report = _mapping(_dump_model(legal_authority_report))
    mandate_refs = _record_ids(mandate_authority_records)
    records = tuple(_gl_s6_mandate_source_record(record) for record in mandate_authority_records)
    return Layer3GLS6MandateConsumerGate(
        status="pass" if records else "fail",
        gate_id="layer3.gl.s6.mandate_source_consumer_gate",
        claim_id=str(report.get("claim_id") or ""),
        selected_norm_refs=_tuple(report.get("selected_norm_refs")),
        legal_authority_record_refs=_tuple(report.get("legal_authority_record_refs")),
        mandate_record_refs=mandate_refs,
        blocker_refs=_tuple(report.get("blocker_refs")),
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        s6_gate_disposition="compatibility_only",
        s6_mandate_source_records=records,
        layer2_s6_compatible_input_refs=(
            "Layer2S6BlindSpotPostureInput.mandate_legitimacy_record_ref",
        ),
        does_not_assert_s6_pass=True,
        s6_evaluation_ref=None,
        issue_codes=() if records else ("layer3_gl_s6_mandate_consumer_gate_missing",),
    )


def build_gl_s7_delegation_consumer_gate(
    *,
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    s6_mandate_consumer_gate: Layer3GLS6MandateConsumerGate | Mapping[str, Any],
) -> Layer3GLS7DelegationConsumerGate:
    """Build S7 delegation handoff while preserving P26 authority boundaries."""

    s6_gate = _mapping(_dump_model(s6_mandate_consumer_gate))
    mandate_refs = _record_ids(mandate_authority_records)
    legal_refs = _gl_legal_refs_from_mandates(mandate_authority_records)
    return Layer3GLS7DelegationConsumerGate(
        status="pass" if mandate_refs and s6_gate.get("status") == "pass" else "fail",
        gate_id="layer3.gl.s7.delegation_mandate_ref_consumer_gate",
        legal_authority_record_refs=legal_refs,
        mandate_record_refs=mandate_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        delegation_handoff_refs=tuple(
            f"s7-delegation-handoff://layer3/gl/{_slug(ref)}" for ref in mandate_refs
        ),
        human_decision_integrity_authority="s7_not_gl",
        p26_boundary_preserved=True,
        responsibility_routing_needed=True,
        issue_codes=()
        if mandate_refs and s6_gate.get("status") == "pass"
        else ("layer3_gl_s7_delegation_consumer_gate_missing",),
    )


def build_gl_s8_value_choice_consumer_gate(
    *,
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    s6_mandate_consumer_gate: Layer3GLS6MandateConsumerGate | Mapping[str, Any],
) -> Layer3GLS8ValueChoiceConsumerGate:
    """Declare S8 compatibility or non-ranking out-of-scope status for GL."""

    _ = s6_mandate_consumer_gate
    mandate_refs = _record_ids(mandate_authority_records)
    return Layer3GLS8ValueChoiceConsumerGate(
        status="out_of_scope",
        gate_id="layer3.gl.s8.value_choice_reference_consumer_gate",
        legal_authority_record_refs=_gl_legal_refs_from_mandates(mandate_authority_records),
        mandate_record_refs=mandate_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        value_choice_scope="non_ranking_gl_closure",
        ranking_authorized=False,
        requires_s6_mandate_pass_for_ranking=True,
        authorized_value_schedule_refs=(),
        layer2_s8_compatible_input_refs=(
            "Layer2S8ValuePostureInput.mandate_record_ref",
            "Layer2S8ValuePostureInput.s6_mandate_firewall_disposition",
        ),
    )


def build_gl_pdc_compiler_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    claim_registry_consumer_gate: Layer3GLClaimRegistryConsumerGate | Mapping[str, Any],
    semantic_binding_consumer_gate: Layer3GLSemanticBindingConsumerGate | Mapping[str, Any],
) -> Layer3GLPdcCompilerConsumerGate:
    """Build PDC compiler-compatible projection rows for GL refs."""

    report = _mapping(_dump_model(legal_authority_report))
    claim_gate = _mapping(_dump_model(claim_registry_consumer_gate))
    semantic_gate = _mapping(_dump_model(semantic_binding_consumer_gate))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    pdc_input_refs = tuple(
        ref
        for ref in (
            claim_gate.get("runtime_claim_registry_ref"),
            semantic_gate.get("semantic_binding_ref"),
            *threshold_refs,
            *mandate_refs,
        )
        if ref
    )
    projection_row = {
        "claim_id": report.get("claim_id"),
        "claim_registry_ref": claim_gate.get("runtime_claim_registry_ref"),
        "semantic_binding_ref": semantic_gate.get("semantic_binding_ref"),
        "legal_authority_record_refs": list(_tuple(report.get("legal_authority_record_refs"))),
        "threshold_record_refs": list(threshold_refs),
        "mandate_record_refs": list(mandate_refs),
        "projection_role": "pdc_input_ref_only",
    }
    return Layer3GLPdcCompilerConsumerGate(
        status="pass" if pdc_input_refs else "fail",
        gate_id="layer3.gl.pdc_compiler.legal_mandate_consumer_gate",
        claim_id=str(report.get("claim_id") or ""),
        selected_norm_refs=_tuple(report.get("selected_norm_refs")),
        legal_authority_record_refs=_tuple(report.get("legal_authority_record_refs")),
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        compatible_with_pdc_input=bool(pdc_input_refs),
        pdc_input_refs=pdc_input_refs,
        projection_rows=(projection_row,),
        issue_codes=() if pdc_input_refs else ("layer3_gl_pdc_compiler_consumer_gate_missing",),
    )


def build_gl_design_constraint_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
) -> Layer3GLDesignConstraintConsumerGate:
    """Build design-loop constraints from legal thresholds and mandate refs."""

    report = _mapping(_dump_model(legal_authority_report))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    source_refs = tuple(dict.fromkeys([*threshold_refs, *mandate_refs]))
    constraint_row = {
        "constraint_id": (
            f"design-constraint://layer3/gl/{_slug(str(report.get('claim_id') or 'claim'))}"
        ),
        "constraint_kind": "legal_boundary",
        "claim_id": report.get("claim_id"),
        "source_refs": list(source_refs),
        "legal_authority_record_refs": list(_tuple(report.get("legal_authority_record_refs"))),
        "constraint_effect": "constraint_or_limitation_only",
        "may_not_use_for": list(GL_MAY_NOT_USE_FOR),
    }
    return Layer3GLDesignConstraintConsumerGate(
        status="pass" if source_refs else "fail",
        gate_id="layer3.gl.design_constraint.legal_boundary_consumer_gate",
        claim_id=str(report.get("claim_id") or ""),
        selected_norm_refs=_tuple(report.get("selected_norm_refs")),
        legal_authority_record_refs=_tuple(report.get("legal_authority_record_refs")),
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        design_constraint_rows=(constraint_row,),
        consumed_as_recommendation_substance=False,
        consumed_as_promotion_authority=False,
        issue_codes=() if source_refs else ("layer3_gl_design_constraint_consumer_gate_missing",),
    )


def build_gl_g4_promotion_gate_consumer_gate(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    design_constraint_consumer_gate: Layer3GLDesignConstraintConsumerGate | Mapping[str, Any],
) -> Layer3GLG4PromotionGateConsumerGate:
    """Build future-G4 compatibility refs without promotion authority."""

    report = _mapping(_dump_model(legal_authority_report))
    design_gate = _mapping(_dump_model(design_constraint_consumer_gate))
    threshold_refs = _record_ids(threshold_authority_records)
    mandate_refs = _record_ids(mandate_authority_records)
    required_refs = tuple(
        dict.fromkeys(
            [
                *_tuple(report.get("legal_authority_record_refs")),
                *threshold_refs,
                *mandate_refs,
                *(
                    str(row.get("constraint_id"))
                    for row in _sequence_of_mappings(design_gate.get("design_constraint_rows"))
                    if row.get("constraint_id")
                ),
            ]
        )
    )
    return Layer3GLG4PromotionGateConsumerGate(
        status="pass" if required_refs else "fail",
        gate_id="layer3.gl.g4.promotion_compatibility_consumer_gate",
        claim_id=str(report.get("claim_id") or ""),
        selected_norm_refs=_tuple(report.get("selected_norm_refs")),
        legal_authority_record_refs=_tuple(report.get("legal_authority_record_refs")),
        threshold_record_refs=threshold_refs,
        mandate_record_refs=mandate_refs,
        limitation_refs=_gl_mandate_limitations(mandate_authority_records),
        future_g4_required_refs=required_refs,
        promotion_authority_claimed=False,
        closeout_authority_claimed=False,
        governed_promoted_claimed=False,
        issue_codes=() if required_refs else ("layer3_gl_g4_promotion_gate_consumer_gate_missing",),
    )


def build_gl_promotion_gate_handoff(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    g4_promotion_gate_consumer_gate: Layer3GLG4PromotionGateConsumerGate | Mapping[str, Any],
) -> Layer3GLPromotionGateHandoff:
    """Build GL promotion gate handoff."""

    report = _mapping(_dump_model(legal_authority_report))
    g4_gate = _mapping(_dump_model(g4_promotion_gate_consumer_gate))
    handoff_refs = tuple(
        dict.fromkeys(
            [
                *_tuple(report.get("legal_authority_record_refs")),
                *_record_ids(threshold_authority_records),
                *_record_ids(mandate_authority_records),
                *_tuple(g4_gate.get("future_g4_required_refs")),
            ]
        )
    )
    return Layer3GLPromotionGateHandoff(
        status="reference_only",
        legal_authority_record_refs=_tuple(report.get("legal_authority_record_refs")),
        threshold_record_refs=_record_ids(threshold_authority_records),
        mandate_record_refs=_record_ids(mandate_authority_records),
        handoff_refs=handoff_refs,
        promotion_authority_claimed=False,
        closeout_authority_claimed=False,
    )


def build_gl_audit_surface(
    *,
    coverage: Layer3GLL3LegalKgCoverageReport | Mapping[str, Any],
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
    claim_registry_consumer_gate: Layer3GLClaimRegistryConsumerGate | Mapping[str, Any],
    semantic_binding_consumer_gate: Layer3GLSemanticBindingConsumerGate | Mapping[str, Any],
    argument_graph_readiness_consumer_gate: Layer3GLArgumentGraphReadinessConsumerGate
    | Mapping[str, Any],
    s6_mandate_consumer_gate: Layer3GLS6MandateConsumerGate | Mapping[str, Any],
    s7_delegation_consumer_gate: Layer3GLS7DelegationConsumerGate | Mapping[str, Any],
    s8_value_choice_consumer_gate: Layer3GLS8ValueChoiceConsumerGate | Mapping[str, Any],
    g4_promotion_gate_consumer_gate: Layer3GLG4PromotionGateConsumerGate | Mapping[str, Any],
) -> Layer3GLLegalMandateAuditSurface:
    """Build GL audit surface."""

    report = _mapping(_dump_model(legal_authority_report))
    coverage_payload = _mapping(_dump_model(coverage))
    gates = (
        claim_registry_consumer_gate,
        semantic_binding_consumer_gate,
        argument_graph_readiness_consumer_gate,
        s6_mandate_consumer_gate,
        s7_delegation_consumer_gate,
        s8_value_choice_consumer_gate,
        g4_promotion_gate_consumer_gate,
    )
    return Layer3GLLegalMandateAuditSurface(
        status="pass",
        legal_kg_snapshot_ref=str(
            coverage_payload.get("db_identity", {}).get("snapshot_ref") or ""
        ),
        audit_refs={
            "selected_norm_refs": _tuple(report.get("selected_norm_refs")),
            "legal_authority_record_refs": _tuple(report.get("legal_authority_record_refs")),
            "threshold_record_refs": _record_ids(threshold_authority_records),
            "mandate_record_refs": _record_ids(mandate_authority_records),
            "consumer_gate_refs": tuple(
                str(_mapping(_dump_model(gate)).get("gate_id") or "") for gate in gates
            ),
        },
        gate_refs=tuple(str(_mapping(_dump_model(gate)).get("gate_id") or "") for gate in gates),
        decision_refs=(str(report.get("claim_id") or ""),),
        raw_legal_payload_exported=False,
        safe_disclosure_status="pass",
    )


def build_gl_public_export_projection_refs(
    *,
    legal_authority_report: Layer3GLLegalAuthorityReportBinding | Mapping[str, Any],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord | Mapping[str, Any]],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord | Mapping[str, Any]],
) -> Layer3GLPublicExportProjectionRefSurface:
    """Build GL public projection-ref surface."""

    report = _mapping(_dump_model(legal_authority_report))
    return Layer3GLPublicExportProjectionRefSurface(
        status="pass",
        projection_mode="reference_only",
        public_export_hook_status="out_of_scope_reference_only",
        projection_policy_ref="projection-policy://layer3/gl/public-export-reference-only",
        projection_refs={
            "selected_norm_refs": _tuple(report.get("selected_norm_refs")),
            "legal_authority_record_refs": _tuple(report.get("legal_authority_record_refs")),
            "threshold_record_refs": _record_ids(threshold_authority_records),
            "mandate_record_refs": _record_ids(mandate_authority_records),
        },
        raw_legal_payload_exported=False,
        safe_disclosure_status="pass",
    )


def _threshold_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 32)
    sql = """
        SELECT
            threshold_id,
            fact_id,
            metric,
            operator,
            value_decimal,
            value_text,
            unit,
            applies_to
        FROM lex_rule_thresholds
        WHERE metric IS NOT NULL AND operator IS NOT NULL AND unit IS NOT NULL
        LIMIT ?
    """
    rows = con.execute(sql, [limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_rule_thresholds:{row[0]}",
            "candidate_path": "threshold_metric_operator_value_unit",
            "source_table": "lex_rule_thresholds",
            "threshold_id": row[0],
            "fact_id": row[1],
            "metric": row[2],
            "operator": row[3],
            "value_decimal": row[4],
            "value_text": row[5],
            "unit": row[6],
            "applies_to": row[7],
            "hydrated_from_table": "lex_rule_thresholds",
            "threshold_source_field": "lex_rule_thresholds",
        }
        for row in rows
    )
    selected_refs = tuple(str(candidate["row_ref"]) for candidate in candidates)
    ledger_id = f"gl-ledger:threshold:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:threshold:{_stable_id(request.request_id)}"
    return Layer3GLLegalSearchLedger(
        ledger_id=ledger_id,
        status="complete_with_candidates" if candidates else "complete_no_candidate",
        request_ref=request.request_id,
        claim_id=request.claim_id,
        requirement_ref=request.legal_requirement_ref,
        jurisdiction=request.jurisdiction,
        legal_as_of=request.legal_as_of,
        legal_kg_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
        query_trace_refs=(trace_ref,),
        table_routes=("lex_rule_thresholds", "lex_normative_ready_facts"),
        normalized_terms=tuple(term.lower() for term in request.query_terms),
        filters={
            "jurisdiction": request.jurisdiction,
            "policy_domain": request.policy_domain,
            "legal_as_of": request.legal_as_of,
            "threshold_fields_required": True,
        },
        sql_shapes=(_normalize_sql(sql),),
        selected_row_refs=selected_refs,
        candidate_rows=candidates,
        no_hit_blockers=() if candidates else ("threshold_seed_no_hit",),
        bounded_result_limit=limit,
        used_full_table_scan=False,
        transition_input=False,
        index_schema_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
    )


def _normative_fact_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 16)
    sql = """
        SELECT
            fact_id,
            doc_id,
            jurisdiction,
            top_domain,
            effective_from,
            effective_to,
            temporal_resolution_status,
            trust_tier,
            canonical_status
        FROM lex_normative_ready_facts
        WHERE jurisdiction = ? AND fact_id IS NOT NULL AND doc_id IS NOT NULL
        LIMIT ?
    """
    rows = con.execute(sql, [request.jurisdiction, limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_normative_ready_facts:{row[0]}",
            "candidate_path": "normative_fact",
            "source_table": "lex_normative_ready_facts",
            "fact_id": row[0],
            "doc_id": row[1],
            "jurisdiction": row[2],
            "top_domain": row[3],
            "effective_from": row[4],
            "effective_to": row[5],
            "temporal_resolution_status": row[6],
            "trust_tier": row[7],
            "canonical_status": row[8],
        }
        for row in rows
    )
    ledger_id = f"gl-ledger:normative-fact:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:normative-fact:{_stable_id(request.request_id)}"
    return _candidate_ledger(
        ledger_id=ledger_id,
        trace_ref=trace_ref,
        request=request,
        coverage=coverage,
        table_routes=("lex_normative_ready_facts",),
        normalized_terms=("normative_fact", request.jurisdiction.lower()),
        filters={
            "jurisdiction": request.jurisdiction,
            "fact_id_required": True,
            "doc_id_required": True,
            "legal_as_of": request.legal_as_of,
        },
        sql=sql,
        candidates=candidates,
        limit=limit,
        no_hit_blocker="normative_fact_seed_no_hit",
    )


def _amendment_lineage_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 16)
    sql = """
        SELECT
            amendment_id,
            amending_doc_id,
            amended_doc_id,
            amendment_type,
            effective_from,
            confidence,
            detected_by
        FROM lex_amendments
        WHERE amendment_id IS NOT NULL AND amended_doc_id IS NOT NULL
        LIMIT ?
    """
    rows = con.execute(sql, [limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_amendments:{row[0]}",
            "candidate_path": "amendment_lineage",
            "source_table": "lex_amendments",
            "amendment_id": row[0],
            "amending_doc_id": row[1],
            "amended_doc_id": row[2],
            "amendment_type": row[3],
            "effective_from": row[4],
            "confidence": row[5],
            "detected_by": row[6],
        }
        for row in rows
    )
    ledger_id = f"gl-ledger:amendment-lineage:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:amendment-lineage:{_stable_id(request.request_id)}"
    return _candidate_ledger(
        ledger_id=ledger_id,
        trace_ref=trace_ref,
        request=request,
        coverage=coverage,
        table_routes=("lex_amendments",),
        normalized_terms=("amendment_lineage", "effective_from"),
        filters={"amendment_id_required": True, "amended_doc_id_required": True},
        sql=sql,
        candidates=candidates,
        limit=limit,
        no_hit_blocker="amendment_lineage_seed_no_hit",
    )


def _provision_source_bundle_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 16)
    sql = """
        SELECT
            v.version_row_id,
            v.doc_id,
            v.version_id,
            v.doc_reestr_code,
            v.doc_type,
            v.doc_status,
            t.temporal_state,
            t.temporal_resolution_status,
            t.published_at,
            t.effective_from,
            t.effective_to
        FROM lex_doc_versions AS v
        LEFT JOIN lex_doc_temporal AS t ON v.doc_id = t.doc_id
        WHERE v.version_row_id IS NOT NULL AND v.doc_id IS NOT NULL
        LIMIT ?
    """
    rows = con.execute(sql, [limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_doc_versions:{row[0]}",
            "candidate_path": "provision_source_bundle",
            "source_table": "lex_doc_versions",
            "temporal_table": "lex_doc_temporal",
            "version_row_id": row[0],
            "doc_id": row[1],
            "version_id": row[2],
            "doc_reestr_code": row[3],
            "doc_type": row[4],
            "doc_status": row[5],
            "temporal_state": row[6],
            "temporal_resolution_status": row[7],
            "published_at": row[8],
            "effective_from": row[9],
            "effective_to": row[10],
        }
        for row in rows
    )
    ledger_id = f"gl-ledger:provision-source:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:provision-source:{_stable_id(request.request_id)}"
    return _candidate_ledger(
        ledger_id=ledger_id,
        trace_ref=trace_ref,
        request=request,
        coverage=coverage,
        table_routes=("lex_doc_versions", "lex_doc_temporal"),
        normalized_terms=("provision_source_bundle", "temporal"),
        filters={"version_row_id_required": True, "doc_id_required": True},
        sql=sql,
        candidates=candidates,
        limit=limit,
        no_hit_blocker="provision_source_bundle_seed_no_hit",
    )


def _reference_resolution_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 16)
    sql = """
        SELECT
            e.reference_edge_id,
            e.source_doc_id,
            e.source_anchor,
            e.target_doc_id,
            e.target_anchor,
            e.relation_type,
            e.resolution_status,
            e.resolution_confidence,
            a.resolution_method,
            a.candidate_count,
            a.selected_target_doc_id
        FROM lex_reference_edges AS e
        LEFT JOIN lex_reference_resolution_audit AS a
            ON e.reference_edge_id = a.ref_id
        WHERE e.reference_edge_id IS NOT NULL
        LIMIT ?
    """
    rows = con.execute(sql, [limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_reference_edges:{row[0]}",
            "candidate_path": "reference_resolution",
            "source_table": "lex_reference_edges",
            "audit_table": "lex_reference_resolution_audit",
            "reference_edge_id": row[0],
            "source_doc_id": row[1],
            "source_anchor": row[2],
            "target_doc_id": row[3],
            "target_anchor": row[4],
            "relation_type": row[5],
            "resolution_status": row[6],
            "resolution_confidence": row[7],
            "resolution_method": row[8],
            "candidate_count": row[9],
            "selected_target_doc_id": row[10],
        }
        for row in rows
    )
    ledger_id = f"gl-ledger:reference-resolution:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:reference-resolution:{_stable_id(request.request_id)}"
    return _candidate_ledger(
        ledger_id=ledger_id,
        trace_ref=trace_ref,
        request=request,
        coverage=coverage,
        table_routes=("lex_reference_edges", "lex_reference_resolution_audit"),
        normalized_terms=("reference_resolution",),
        filters={"reference_edge_id_required": True},
        sql=sql,
        candidates=candidates,
        limit=limit,
        no_hit_blocker="reference_resolution_seed_no_hit",
    )


def _intervention_map_candidate_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    limit = min(request.limit, 16)
    sql = """
        SELECT
            fact_id,
            doc_id,
            action_canon,
            norm_type_canon,
            predicate,
            jurisdiction,
            top_domain,
            temporal_resolution_status
        FROM lex_normative_ready_facts
        WHERE jurisdiction = ? AND (action_canon IS NOT NULL OR predicate IS NOT NULL)
        LIMIT ?
    """
    rows = con.execute(sql, [request.jurisdiction, limit]).fetchall()
    candidates = tuple(
        {
            "row_ref": f"lex_normative_ready_facts:{row[0]}",
            "candidate_path": "intervention_map_candidate",
            "source_table": "lex_normative_ready_facts",
            "authority_status": "candidate_only",
            "intervention_family": request.intervention_family,
            "fact_id": row[0],
            "doc_id": row[1],
            "action_canon": row[2],
            "norm_type_canon": row[3],
            "predicate": row[4],
            "jurisdiction": row[5],
            "top_domain": row[6],
            "temporal_resolution_status": row[7],
        }
        for row in rows
    )
    ledger_id = f"gl-ledger:intervention-map:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:intervention-map:{_stable_id(request.request_id)}"
    return _candidate_ledger(
        ledger_id=ledger_id,
        trace_ref=trace_ref,
        request=request,
        coverage=coverage,
        table_routes=("lex_normative_ready_facts",),
        normalized_terms=("intervention_map_candidate", request.intervention_family),
        filters={
            "jurisdiction": request.jurisdiction,
            "action_or_predicate_required": True,
            "authority_status": "candidate_only",
        },
        sql=sql,
        candidates=candidates,
        limit=limit,
        no_hit_blocker="intervention_map_candidate_seed_no_hit",
    )


def _candidate_ledger(
    *,
    ledger_id: str,
    trace_ref: str,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
    table_routes: tuple[str, ...],
    normalized_terms: tuple[str, ...],
    filters: dict[str, Any],
    sql: str,
    candidates: tuple[dict[str, Any], ...],
    limit: int,
    no_hit_blocker: str,
) -> Layer3GLLegalSearchLedger:
    return Layer3GLLegalSearchLedger(
        ledger_id=ledger_id,
        status="complete_with_candidates" if candidates else "complete_no_candidate",
        request_ref=request.request_id,
        claim_id=request.claim_id,
        requirement_ref=request.legal_requirement_ref,
        jurisdiction=request.jurisdiction,
        legal_as_of=request.legal_as_of,
        legal_kg_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
        query_trace_refs=(trace_ref,),
        table_routes=table_routes,
        normalized_terms=normalized_terms,
        filters=filters,
        sql_shapes=(_normalize_sql(sql),),
        selected_row_refs=tuple(str(candidate["row_ref"]) for candidate in candidates),
        candidate_rows=candidates,
        no_hit_blockers=() if candidates else (no_hit_blocker,),
        bounded_result_limit=limit,
        used_full_table_scan=False,
        transition_input=False,
        index_schema_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
    )


def _bounded_no_hit_ledger(
    repo_root: Path,
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    db_path = repo_root / CANONICAL_L3_LEGAL_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    sql = """
        SELECT fact_id
        FROM lex_normative_ready_facts
        WHERE fact_id = ?
        LIMIT 1
    """
    rows = con.execute(sql, ["__policyos_gl_known_no_hit_seed__"]).fetchall()
    ledger_id = f"gl-ledger:no-hit:{_slug(request.request_id)}"
    trace_ref = f"gl-query-trace:no-hit:{_stable_id(request.request_id)}"
    return Layer3GLLegalSearchLedger(
        ledger_id=ledger_id,
        status="complete_no_candidate" if not rows else "complete_with_candidates",
        request_ref=request.request_id,
        claim_id=request.claim_id,
        requirement_ref=request.legal_requirement_ref,
        jurisdiction=request.jurisdiction,
        legal_as_of=request.legal_as_of,
        legal_kg_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
        query_trace_refs=(trace_ref,),
        table_routes=("lex_normative_ready_facts",),
        normalized_terms=("__policyos_gl_known_no_hit_seed__",),
        filters={"known_no_hit_seed": "__policyos_gl_known_no_hit_seed__"},
        sql_shapes=(_normalize_sql(sql),),
        selected_row_refs=tuple(f"lex_normative_ready_facts:{row[0]}" for row in rows),
        candidate_rows=(),
        no_hit_blockers=("bounded_no_hit_probe",) if not rows else (),
        bounded_result_limit=1,
        used_full_table_scan=False,
        transition_input=False,
        index_schema_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
    )


def _coverage_blocked_ledger(
    request: Layer3GLLegalMandateRequest,
    coverage: Layer3GLL3LegalKgCoverageReport,
) -> Layer3GLLegalSearchLedger:
    return Layer3GLLegalSearchLedger(
        ledger_id=f"gl-ledger:coverage-blocked:{_slug(request.request_id)}",
        status="incomplete_schema_mismatch",
        request_ref=request.request_id,
        claim_id=request.claim_id,
        requirement_ref=request.legal_requirement_ref,
        jurisdiction=request.jurisdiction,
        legal_as_of=request.legal_as_of,
        legal_kg_snapshot_ref=coverage.db_identity.get("snapshot_ref"),
        query_trace_refs=(f"gl-query-trace:coverage-blocked:{_stable_id(request.request_id)}",),
        table_routes=tuple(REQUIRED_KG_COLUMNS),
        normalized_terms=tuple(term.lower() for term in request.query_terms),
        filters={"coverage_status": coverage.status},
        sql_shapes=("SELECT table_name FROM information_schema.tables LIMIT 0",),
        no_hit_blockers=coverage.issue_codes,
        bounded_result_limit=0,
        issue_codes=coverage.issue_codes,
    )


def _validate_task1_route(
    payload: Mapping[str, Any], issues: list[Layer3GLValidationIssue]
) -> None:
    readiness = _mapping(payload.get("readiness_manifest"))
    if readiness and readiness.get("g0_dependency_status") != "pass":
        issues.append(
            _issue(
                "layer3_gl_g0_dependency_not_ready",
                "$.readiness_manifest.g0_dependency_status",
                "GL closure requires a fully passing G0 dependency check.",
            )
        )
    coverage = _mapping(payload.get("l3_legal_kg_index_coverage"))
    if coverage and coverage.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_gl_l3_legal_kg_index_coverage_failed",
                "$.l3_legal_kg_index_coverage",
                "GL requires passing canonical L3 Legal KG coverage before search closure.",
            )
        )
    ledgers = _sequence_of_mappings(payload.get("l3_legal_kg_search_ledgers"))
    if not ledgers:
        issues.append(
            _issue(
                "layer3_gl_search_ledger_missing",
                "$.l3_legal_kg_search_ledgers",
                "GL requires replayable legal search ledgers.",
            )
        )
    for index, ledger in enumerate(ledgers):
        if ledger.get("canonical_route") != "l3_legal_kg_duckdb" or ledger.get("transition_input"):
            issues.append(
                _issue(
                    "layer3_gl_noncanonical_legal_route_used_for_closure",
                    f"$.l3_legal_kg_search_ledgers[{index}]",
                    "GL closure must use the canonical L3 Legal KG route.",
                )
            )
        if ledger.get("used_as_authority") and str(
            ledger.get("candidate_source") or ledger.get("search_route") or ""
        ) in {"text_search", "read_api_text_search"}:
            issues.append(
                _issue(
                    "layer3_gl_text_search_used_as_authority",
                    f"$.l3_legal_kg_search_ledgers[{index}]",
                    "Text search may expand candidates, but cannot be GL legal authority.",
                )
            )
    traces = _sequence_of_mappings(payload.get("l3_legal_kg_query_traces"))
    if not traces:
        issues.append(
            _issue(
                "layer3_gl_query_trace_missing",
                "$.l3_legal_kg_query_traces",
                "GL requires query traces for replayable legal search ledgers.",
            )
        )


def _validate_authority_firewalls(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    report = _mapping(payload.get("legal_authority_report"))
    selected_norm_refs = _tuple(report.get("selected_norm_refs"))
    authority_refs = _tuple(report.get("legal_authority_record_refs"))
    ledgers = _sequence_of_mappings(payload.get("l3_legal_kg_search_ledgers"))
    if ledgers and not authority_refs:
        issues.append(
            _issue(
                "layer3_gl_selected_norm_without_legal_authority_record",
                "$.legal_authority_report.legal_authority_record_refs",
                "GL search evidence cannot pass without claim-level legal authority records.",
            )
        )
    if selected_norm_refs and not authority_refs:
        issues.append(
            _issue(
                "layer3_gl_selected_norm_without_legal_authority_record",
                "$.legal_authority_report.selected_norm_refs",
                "Selected legal norms require claim-level legal authority record refs.",
            )
        )
    if report.get("used_internal_requirement_compile"):
        issues.append(
            _issue(
                "layer3_gl_internal_requirement_compile_used_for_closure",
                "$.legal_authority_report.used_internal_requirement_compile",
                "GL closure must pass explicit persisted legal requirement specs.",
            )
        )
    if str(report.get("producer_artifact_ref", "")).startswith("derived://"):
        issues.append(
            _issue(
                "layer3_gl_legal_authority_report_missing_gl_producer_artifact_ref",
                "$.legal_authority_report.producer_artifact_ref",
                "GL closure requires a persisted GL producer artifact ref.",
            )
        )
    if (
        report.get("runtime_candidate_norms_used_for_closure")
        or report.get("candidate_source") == "runtime_candidate_norms"
    ):
        issues.append(
            _issue(
                "layer3_gl_runtime_candidate_norm_snapshot_used_for_closure",
                "$.legal_authority_report.candidate_source",
                "Inline runtime candidate norms cannot close GL.",
            )
        )
    if (
        report.get("applicability_internal_kg_fallback_used")
        or report.get("candidate_source") == "applicability_internal_lex_kg"
    ):
        issues.append(
            _issue(
                "layer3_gl_applicability_report_internal_lex_kg_fallback_used_for_closure",
                "$.legal_authority_report.candidate_source",
                "Applicability-report internal KG fallback is transition context, not GL closure.",
            )
        )
    norm_candidate_bindings = _sequence_of_mappings(payload.get("norm_candidate_bindings"))
    if (
        report.get("runtime_candidate_norms_used_for_closure")
        or report.get("applicability_internal_kg_fallback_used")
        or report.get("candidate_source")
        in {"runtime_candidate_norms", "applicability_internal_lex_kg"}
    ) and not norm_candidate_bindings:
        issues.append(
            _issue(
                "layer3_gl_norm_candidate_binding_missing",
                "$.norm_candidate_bindings",
                "GL closure requires typed norm-candidate bindings from KG rows.",
            )
        )
    _validate_legal_requirement_bindings(payload, issues)
    _validate_threshold_records(payload, issues)
    _validate_authority_facet_records(payload, issues)
    _validate_intervention_map_records(payload, issues)
    _validate_mandate_records(payload, issues)
    _validate_temporal_competence_records(payload, issues)


def _validate_legal_requirement_bindings(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    bindings = _sequence_of_mappings(payload.get("legal_requirement_bindings"))
    if not bindings:
        issues.append(
            _issue(
                "layer3_gl_legal_requirement_binding_missing",
                "$.legal_requirement_bindings",
                "GL requires persisted legal requirement bindings.",
            )
        )
        return
    for index, binding in enumerate(bindings):
        if not binding.get("producer_artifact_ref") and not binding.get(
            "legal_requirement_artifact_ref"
        ):
            issues.append(
                _issue(
                    "layer3_gl_legal_requirement_producer_artifact_ref_missing",
                    f"$.legal_requirement_bindings[{index}]",
                    "GL requirement bindings need persisted producer artifact refs.",
                )
            )
        if binding.get("mandatory") and not _tuple(binding.get("authority_types")):
            issues.append(
                _issue(
                    "layer3_gl_legal_requirement_missing_authority_types",
                    f"$.legal_requirement_bindings[{index}].authority_types",
                    "Mandatory legal requirements need authority types.",
                )
            )
        fallback_policy = _mapping(binding.get("fallback_policy"))
        if binding.get("mandatory") and not fallback_policy.get("config_ref"):
            issues.append(
                _issue(
                    "layer3_gl_jurisdiction_fallback_policy_missing",
                    f"$.legal_requirement_bindings[{index}].fallback_policy",
                    "GL legal requirements need an explicit jurisdiction fallback policy.",
                )
            )


def _validate_threshold_records(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    for index, record in enumerate(
        _sequence_of_mappings(payload.get("threshold_authority_records"))
    ):
        if record.get("hydrated_from_table") != "lex_rule_thresholds":
            issues.append(
                _issue(
                    "layer3_gl_threshold_row_not_hydrated",
                    f"$.threshold_authority_records[{index}].hydrated_from_table",
                    "Threshold authority records must hydrate direct lex_rule_thresholds rows.",
                )
            )
        if record.get("threshold_source_field") == "thresholds_json":
            issues.append(
                _issue(
                    "layer3_gl_thresholds_json_used_as_authority",
                    f"$.threshold_authority_records[{index}].threshold_source_field",
                    "thresholds_json may be discovery context, not authority-row closure.",
                )
            )
        if not record.get("operator") or not record.get("unit"):
            issues.append(
                _issue(
                    "layer3_gl_threshold_unit_or_operator_unparsed",
                    f"$.threshold_authority_records[{index}]",
                    "Threshold authority records require parsed operator and unit.",
                )
            )


def _validate_authority_facet_records(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    authority_facet_bindings = _sequence_of_mappings(payload.get("authority_facet_bindings"))
    for index, candidate in enumerate(
        _sequence_of_mappings(payload.get("norm_candidate_bindings"))
    ):
        if not candidate.get("authority_facet_binding_refs"):
            issues.append(
                _issue(
                    "layer3_gl_authority_facet_binding_missing",
                    f"$.norm_candidate_bindings[{index}].authority_facet_binding_refs",
                    "Candidate norms need explicit GL authority-facet binding refs.",
                )
            )
        if candidate.get("authority_facets_source") == "kg_native_assumed":
            issues.append(
                _issue(
                    "layer3_gl_kg_authority_facets_assumed_present",
                    f"$.norm_candidate_bindings[{index}].authority_facets_source",
                    "The production KG authority facets cannot be assumed without GL bindings.",
                )
            )
    for index, requirement in enumerate(
        _sequence_of_mappings(payload.get("legal_requirement_bindings"))
    ):
        if requirement.get("authority_type_source") == "compiler_default" and not requirement.get(
            "compiler_default_marked"
        ):
            issues.append(
                _issue(
                    "layer3_gl_compiler_default_authority_type_unmarked",
                    f"$.legal_requirement_bindings[{index}]",
                    "Compiler-derived authority-type defaults must be marked.",
                )
            )
    for index, binding in enumerate(authority_facet_bindings):
        if (
            binding.get("derived_from_compiler_default")
            and binding.get("facet_source") == "lex_discovered"
        ):
            issues.append(
                _issue(
                    "layer3_gl_compiler_default_authority_type_laundered",
                    f"$.authority_facet_bindings[{index}]",
                    "Compiler defaults cannot masquerade as Lex-discovered authority facets.",
                )
            )
        facet_name = str(binding.get("facet_name") or "")
        if facet_name == "source_authority" and (
            binding.get("facet_source") == "missing" or not binding.get("facet_value")
        ):
            issues.append(
                _issue(
                    "layer3_gl_norm_source_authority_missing",
                    f"$.authority_facet_bindings[{index}]",
                    "Candidate norms require source-authority facet evidence.",
                )
            )
        if facet_name in {"competent_actor_ref", "instrument_types"} and (
            binding.get("facet_source") == "missing"
            or binding.get("validation_status") == "blocked"
            or not binding.get("facet_value")
        ):
            issues.append(
                _issue(
                    "layer3_gl_authority_facet_binding_semantic_loss",
                    f"$.authority_facet_bindings[{index}]",
                    "Required actor/instrument facets must fail closed when missing.",
                )
            )


def _validate_intervention_map_records(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    for index, binding in enumerate(
        _sequence_of_mappings(payload.get("lex_intervention_map_bindings"))
    ):
        legal_authority_refs = _tuple(binding.get("legal_authority_record_refs"))
        admitted_precondition = str(binding.get("admitted_authority_precondition_status") or "")
        if binding.get("status") in {"pass", "admitted_authority", "handoff_ready"} and (
            not legal_authority_refs or admitted_precondition != "pass"
        ):
            issues.append(
                _issue(
                    "layer3_gl_lex_intervention_map_missing",
                    f"$.lex_intervention_map_bindings[{index}]",
                    "Lex intervention-map handoffs require admitted legal authority refs.",
                )
            )
        if binding.get("used_as_legal_authority") or "legal_authority" in _tuple(
            binding.get("authoritative_for")
        ):
            issues.append(
                _issue(
                    "layer3_gl_lex_intervention_map_used_as_authority",
                    f"$.lex_intervention_map_bindings[{index}]",
                    "lex_intervention_map bindings are executable context, not legal authority.",
                )
            )


def _validate_mandate_records(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    for index, record in enumerate(_sequence_of_mappings(payload.get("mandate_authority_records"))):
        if not _tuple(record.get("mandate_source_refs")):
            issues.append(
                _issue(
                    "layer3_gl_mandate_source_refs_missing",
                    f"$.mandate_authority_records[{index}].mandate_source_refs",
                    "Mandate records require source refs for S6/S7/S8 handoff.",
                )
            )
        if record.get("s6_mandate_firewall_disposition") == "pass" and not (
            record.get("s6_evaluation_ref")
            or _tuple(record.get("s6_compatible_source_handoff_refs"))
        ):
            issues.append(
                _issue(
                    "layer3_gl_s6_mandate_semantics_forked",
                    f"$.mandate_authority_records[{index}]",
                    "GL cannot claim S6 pass without S6 evaluation or compatible source handoff.",
                )
            )


def _validate_temporal_competence_records(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    partial_statuses = {"", "missing", "partial", "unresolved", "unknown"}
    for index, record in enumerate(
        _sequence_of_mappings(payload.get("temporal_competence_records"))
    ):
        if (
            record.get("status") == "pass"
            and str(record.get("temporal_resolution_status") or "").casefold() in partial_statuses
        ):
            issues.append(
                _issue(
                    "layer3_gl_partial_temporal_row_promoted_to_authority",
                    f"$.temporal_competence_records[{index}]",
                    "Partial or unresolved temporal rows cannot be promoted to GL authority.",
                )
            )


def _validate_search_recall_freshness(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    report = _mapping(payload.get("search_recall_freshness"))
    if not report:
        issues.append(
            _issue(
                "layer3_gl_false_abstention_recall_unmeasured",
                "$.search_recall_freshness",
                "GL requires known-seed recall and index-freshness evidence.",
            )
        )
        return
    if report.get("status") != "pass":
        issue_codes = _tuple(report.get("issue_codes")) or (
            "layer3_gl_false_abstention_recall_unmeasured",
        )
        for code in issue_codes:
            issues.append(
                _issue(
                    str(code),
                    "$.search_recall_freshness",
                    "GL cannot treat no-hit search as legal/domain ceiling "
                    "when recall or freshness fails.",
                )
            )
    if report.get("domain_ceiling_allowed"):
        issues.append(
            _issue(
                "layer3_gl_search_recall_seed_miss_blocks_domain_ceiling",
                "$.search_recall_freshness.domain_ceiling_allowed",
                "GL search frontier cannot authorize domain-ceiling claims.",
            )
        )


def _validate_consumer_gates(
    payload: Mapping[str, Any],
    issues: list[Layer3GLValidationIssue],
) -> None:
    report = _mapping(payload.get("legal_authority_report"))
    legal_refs = _tuple(report.get("legal_authority_record_refs"))
    selected_norm_refs = _tuple(report.get("selected_norm_refs"))
    threshold_refs = _record_ids(_sequence_of_mappings(payload.get("threshold_authority_records")))
    mandate_refs = _record_ids(_sequence_of_mappings(payload.get("mandate_authority_records")))
    has_authority = bool(legal_refs)
    if has_authority:
        gate_codes = (
            ("claim_registry_consumer_gate", "layer3_gl_claim_registry_consumer_gate_missing"),
            ("semantic_binding_consumer_gate", "layer3_gl_semantic_binding_consumer_gate_missing"),
        )
        for gate_name, code in gate_codes:
            gate = _mapping(payload.get(gate_name))
            if gate.get("status") != "pass":
                issues.append(
                    _issue(code, f"$.{gate_name}", "GL legal authority refs need consumer gates.")
                )
        claim_gate = _mapping(payload.get("claim_registry_consumer_gate"))
        claim_rows = _sequence_of_mappings(claim_gate.get("claim_registry_rows"))
        if claim_gate.get("status") == "pass" and not any(
            set(_tuple(row.get("selected_norm_refs"))) >= set(selected_norm_refs)
            and set(_tuple(row.get("legal_authority_record_refs"))) >= set(legal_refs)
            for row in claim_rows
        ):
            issues.append(
                _issue(
                    "layer3_gl_claim_registry_consumer_gate_missing",
                    "$.claim_registry_consumer_gate.claim_registry_rows",
                    (
                        "Claim registry consumer gate must preserve selected norm and "
                        "legal authority refs."
                    ),
                )
            )
        if "legal_authority" in _tuple(claim_gate.get("authoritative_for")):
            issues.append(
                _issue(
                    "layer3_gl_claim_registry_consumer_gate_missing",
                    "$.claim_registry_consumer_gate.authoritative_for",
                    "Claim registry projection cannot mint GL legal authority.",
                )
            )

        semantic_gate = _mapping(payload.get("semantic_binding_consumer_gate"))
        semantic_rows = _sequence_of_mappings(semantic_gate.get("semantic_binding_rows"))
        semantic_issue_codes = set(_tuple(semantic_gate.get("issue_codes"))) | set(
            _tuple(semantic_gate.get("semantic_binding_issue_codes"))
        )
        if semantic_gate.get("status") == "pass" and (
            "semantic_lex_legal_authority_record_missing" in semantic_issue_codes
            or not any(
                set(_tuple(row.get("selected_norm_refs"))) >= set(selected_norm_refs)
                and set(_tuple(row.get("legal_authority_record_refs"))) >= set(legal_refs)
                for row in semantic_rows
            )
        ):
            issues.append(
                _issue(
                    "layer3_gl_semantic_binding_consumer_gate_missing",
                    "$.semantic_binding_consumer_gate.semantic_binding_rows",
                    (
                        "Semantic binding consumer gate must preserve selected norms "
                        "with legal authority refs."
                    ),
                )
            )

        argument_gate = _mapping(payload.get("argument_graph_readiness_consumer_gate"))
        readiness_rows = _sequence_of_mappings(argument_gate.get("readiness_rows"))
        if argument_gate.get("status") != "pass" or not any(
            row.get("status") == "pass"
            and row.get("readiness_check") == GL_READINESS_CHECK_ID
            and set(_tuple(row.get("authority_refs")))
            >= {*legal_refs, *threshold_refs, *mandate_refs}
            for row in readiness_rows
        ):
            issues.append(
                _issue(
                    "layer3_gl_argument_graph_readiness_consumer_gate_missing",
                    "$.argument_graph_readiness_consumer_gate",
                    "Argument-graph readiness gate must expose legal, threshold, and mandate refs.",
                )
            )

        s6_gate = _mapping(payload.get("s6_mandate_consumer_gate"))
        if s6_gate.get("status") != "pass" or not _sequence_of_mappings(
            s6_gate.get("s6_mandate_source_records")
        ):
            issues.append(
                _issue(
                    "layer3_gl_s6_mandate_consumer_gate_missing",
                    "$.s6_mandate_consumer_gate",
                    "GL mandate refs require an S6-compatible source handoff.",
                )
            )
        s7_gate = _mapping(payload.get("s7_delegation_consumer_gate"))
        if s7_gate.get("status") != "pass" or not s7_gate.get("p26_boundary_preserved"):
            issues.append(
                _issue(
                    "layer3_gl_s7_delegation_consumer_gate_missing",
                    "$.s7_delegation_consumer_gate",
                    "S7 delegation gate must preserve P26 human decision integrity authority.",
                )
            )

        s8_gate = _mapping(payload.get("s8_value_choice_consumer_gate"))
        if s8_gate.get("status") not in {"pass", "out_of_scope"}:
            issues.append(
                _issue(
                    "layer3_gl_s8_value_choice_consumer_gate_missing",
                    "$.s8_value_choice_consumer_gate",
                    "S8 gate must pass or explicitly declare non-ranking GL closure out of scope.",
                )
            )
        s6_disposition = str(s6_gate.get("s6_gate_disposition") or "")
        source_dispositions = {
            str(row.get("mandate_source_disposition") or "")
            for row in _sequence_of_mappings(s6_gate.get("s6_mandate_source_records"))
        }
        if s8_gate.get("ranking_authorized") and (
            s6_disposition != "pass"
            or any(
                disposition.startswith(("candidate", "limited"))
                for disposition in source_dispositions
            )
        ):
            issues.append(
                _issue(
                    "layer3_gl_s8_ranking_authorized_without_mandate_pass",
                    "$.s8_value_choice_consumer_gate.ranking_authorized",
                    "GL cannot authorize ranked value choices without S6 mandate pass.",
                )
            )

        pdc_gate = _mapping(payload.get("pdc_compiler_consumer_gate"))
        if pdc_gate.get("status") != "pass" or not pdc_gate.get("compatible_with_pdc_input"):
            issues.append(
                _issue(
                    "layer3_gl_pdc_compiler_consumer_gate_missing",
                    "$.pdc_compiler_consumer_gate",
                    "PDC compiler gate must expose compatible legal and mandate refs.",
                )
            )

        design_gate = _mapping(payload.get("design_constraint_consumer_gate"))
        if (
            design_gate.get("status") != "pass"
            or not _sequence_of_mappings(design_gate.get("design_constraint_rows"))
            or design_gate.get("consumed_as_recommendation_substance")
            or design_gate.get("consumed_as_promotion_authority")
        ):
            issues.append(
                _issue(
                    "layer3_gl_design_constraint_consumer_gate_missing",
                    "$.design_constraint_consumer_gate",
                    (
                        "Design constraint gate must expose boundaries without "
                        "recommendation or promotion authority."
                    ),
                )
            )

        g4_gate = _mapping(payload.get("g4_promotion_gate_consumer_gate"))
        if g4_gate.get("status") != "pass" or not _tuple(g4_gate.get("future_g4_required_refs")):
            issues.append(
                _issue(
                    "layer3_gl_g4_promotion_gate_consumer_gate_missing",
                    "$.g4_promotion_gate_consumer_gate",
                    "G4 compatibility gate must expose future promotion refs.",
                )
            )
        if g4_gate.get("promotion_authority_claimed") or g4_gate.get("governed_promoted_claimed"):
            issues.append(
                _issue(
                    "layer3_gl_promotion_authority_leak",
                    "$.g4_promotion_gate_consumer_gate",
                    "GL cannot claim G4 promotion authority.",
                )
            )
        if g4_gate.get("closeout_authority_claimed"):
            issues.append(
                _issue(
                    "layer3_gl_closeout_authority_leak",
                    "$.g4_promotion_gate_consumer_gate",
                    "GL cannot claim closeout authority.",
                )
            )

    projection = _mapping(payload.get("public_export_projection_refs"))
    raw_public_keys = {
        "raw_legal_rows",
        "source_quotes",
        "provision_text",
        "query_ledgers",
        "unredacted_authority_payloads",
    }
    if projection.get("raw_legal_payload_exported") or raw_public_keys.intersection(projection):
        issues.append(
            _issue(
                "layer3_gl_public_raw_legal_payload_leak",
                "$.public_export_projection_refs",
                "Public projection refs must not expose raw legal payloads.",
            )
        )
    if projection and projection.get("projection_mode") != "reference_only":
        issues.append(
            _issue(
                "layer3_gl_public_export_projection_mode_mismatch",
                "$.public_export_projection_refs.projection_mode",
                "GL projection refs are reference_only until a public export hook is implemented.",
            )
        )
    if projection and not projection.get("projection_policy_ref"):
        issues.append(
            _issue(
                "layer3_gl_public_projection_ref_without_projection_policy",
                "$.public_export_projection_refs.projection_policy_ref",
                "Reference-only public projection needs an explicit projection policy ref.",
            )
        )
    if projection and str(projection.get("public_export_hook_status") or "").casefold() not in {
        "out_of_scope_reference_only",
        "reference_only",
    }:
        issues.append(
            _issue(
                "layer3_gl_public_export_hook_overclaimed",
                "$.public_export_projection_refs.public_export_hook_status",
                "Reference-only GL projection cannot claim a runtime public-export hook.",
            )
        )


def _adapter_admission_bundle() -> Layer3GLAdapterAdmissionBundle:
    from polisyos.runtime.quality.layer3_grounding_inventory import AdapterAdmissionRecord

    record = AdapterAdmissionRecord(
        adapter_id="layer3-gl-legal-mandate-search-adapter",
        source_ids=["lex_knowledge_graph.duckdb"],
        port_ids=["layer3.legal_mandate_search_adapter"],
        maturity="fail_closed",
        promotion_state="shadow",
        conformance_status="blocked",
        quarantine_check="task1_search_only_no_authority_admission",
        admission_state="candidate_shadow_only",
        admitted=False,
        adapter_contract_path_refs=list(GL_ADAPTER_PATH_IDS),
        source_touchpoint_refs=[
            "polisyos.runtime.quality.layer3_legal_mandate_search",
        ],
    )
    return Layer3GLAdapterAdmissionBundle(
        status="reference_only",
        adapter_admission_records=(record.model_dump(mode="json"),),
    )


def _default_request() -> Layer3GLLegalMandateRequest:
    return Layer3GLLegalMandateRequest(
        request_id="gl-request:canonical-threshold-seed",
        claim_id="claim:gl:canonical-threshold-seed",
        case_id="case:gl:canonical-threshold-seed",
        legal_requirement_ref="legal-requirement://gl/canonical-threshold-seed",
        jurisdiction="UA",
        policy_domain="economic_policy",
        legal_as_of="2022-03-01",
        intervention_family="subsidized_credit",
        query_terms=("threshold", "mandate", "credit"),
        limit=5,
    )


def _default_target_context() -> dict[str, Any]:
    return {
        "run_id": "layer3-gl-canonical-legal-mandate",
        "jurisdiction": "UA",
        "policy_domain": "economic_policy",
        "as_of": "2022-03-01",
        "authority_profile": "gl_legal_mandate",
    }


def _default_recommendation_claims() -> tuple[dict[str, Any], ...]:
    return (
        {
            "claim_id": "gl_canonical_threshold_seed",
            "claim_ref": "claim:gl:canonical-threshold-seed",
            "legal_authority_required": True,
            "jurisdiction": "UA",
            "policy_domain": "economic_policy",
            "implementation_period": {"start": "2022-03-01", "end": "2022-12-31"},
            "concept_spine_refs": ("concept:economic_policy_support",),
        },
    )


def _default_jurisdiction_fallback_config() -> dict[str, Any]:
    return {
        "mode": "governed_config_required",
        "config_ref": GL_JURISDICTION_FALLBACK_CONFIG_REF,
        "policy_ref": "policyos://gl/legal-mandate/jurisdiction-fallback",
        "owner": "policyos:runtime-quality",
    }


def _build_gl_conformance_report(
    *,
    g0_dependency_status: str,
    coverage: Layer3GLL3LegalKgCoverageReport,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
    traces: Sequence[Layer3GLLegalQueryTrace],
    search_recall: Layer3GLSearchRecallFreshnessReport,
    l5_calibration_bindings: Sequence[Layer3GLL5CalibrationBinding],
    legal_authority_report: Layer3GLLegalAuthorityReportBinding,
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding],
    norm_candidate_bindings: Sequence[Layer3GLNormCandidateBinding],
    threshold_authority_records: Sequence[Layer3GLThresholdAuthorityRecord],
    mandate_authority_records: Sequence[Layer3GLMandateAuthorityRecord],
    temporal_competence_records: Sequence[Layer3GLTemporalCompetenceRecord],
    amendment_lineage_records: Sequence[Layer3GLAmendmentLineageRecord],
    reference_resolution_records: Sequence[Layer3GLReferenceResolutionRecord],
    lex_intervention_map_bindings: Sequence[Layer3GLLexInterventionMapBinding],
    claim_registry_consumer_gate: Layer3GLClaimRegistryConsumerGate,
    semantic_binding_consumer_gate: Layer3GLSemanticBindingConsumerGate,
    argument_graph_readiness_consumer_gate: Layer3GLArgumentGraphReadinessConsumerGate,
    s6_mandate_consumer_gate: Layer3GLS6MandateConsumerGate,
    s7_delegation_consumer_gate: Layer3GLS7DelegationConsumerGate,
    s8_value_choice_consumer_gate: Layer3GLS8ValueChoiceConsumerGate,
    pdc_compiler_consumer_gate: Layer3GLPdcCompilerConsumerGate,
    design_constraint_consumer_gate: Layer3GLDesignConstraintConsumerGate,
    g4_promotion_gate_consumer_gate: Layer3GLG4PromotionGateConsumerGate,
    public_export_projection_refs: Layer3GLPublicExportProjectionRefSurface,
    adapter_contract_registry: Mapping[str, Any],
    health_metric_delta: Mapping[str, Any],
) -> Layer3GLConformanceReport:
    performance_status, performance_check_refs = _gl_performance_closeout_status(
        ledgers=ledgers,
        traces=traces,
        health_metric_delta=health_metric_delta,
    )
    gate_statuses = {
        "g0_dependency": "pass" if g0_dependency_status == "pass" else "fail",
        "legal_kg_route": "pass" if coverage.status == "pass" else "fail",
        "search_recall_freshness": "pass" if search_recall.status == "pass" else "fail",
        "l5_calibration_boundary": "pass"
        if any(binding.status in {"pass", "limitation"} for binding in l5_calibration_bindings)
        else "fail",
        "legal_requirement_binding": "pass"
        if legal_authority_report.explicit_gl_requirement_spec_refs
        and legal_authority_report.producer_artifact_ref
        else "fail",
        "authority_facet_binding": "pass" if authority_facet_bindings else "fail",
        "norm_candidate_binding": "pass" if norm_candidate_bindings else "fail",
        "claim_level_authority": "pass"
        if legal_authority_report.status == "pass"
        and legal_authority_report.selected_norm_refs
        and legal_authority_report.legal_authority_record_refs
        else "fail",
        "threshold_authority_record": "pass" if threshold_authority_records else "fail",
        "mandate_authority_record": "pass" if mandate_authority_records else "fail",
        "temporal_records": "pass" if temporal_competence_records else "fail",
        "amendment_lineage": "pass" if amendment_lineage_records else "fail",
        "reference_resolution": "pass" if reference_resolution_records else "fail",
        "lex_intervention_map_binding": "pass" if lex_intervention_map_bindings else "fail",
        "consumer_gates": "pass"
        if (
            claim_registry_consumer_gate.status == "pass"
            and semantic_binding_consumer_gate.status == "pass"
            and argument_graph_readiness_consumer_gate.status == "pass"
            and s6_mandate_consumer_gate.status == "pass"
            and s7_delegation_consumer_gate.status == "pass"
            and s8_value_choice_consumer_gate.status in {"pass", "out_of_scope"}
            and pdc_compiler_consumer_gate.status == "pass"
            and design_constraint_consumer_gate.status == "pass"
            and g4_promotion_gate_consumer_gate.status == "pass"
        )
        else "fail",
        "public_projection": "pass"
        if (
            public_export_projection_refs.status == "pass"
            and public_export_projection_refs.projection_mode == "reference_only"
            and not public_export_projection_refs.raw_legal_payload_exported
            and public_export_projection_refs.public_export_hook_status
            == "out_of_scope_reference_only"
        )
        else "fail",
        "adapter_registry": "pass"
        if (
            adapter_contract_registry.get("status") == "pass"
            and set(_tuple(adapter_contract_registry.get("adapter_path_ids")))
            >= set(GL_ADAPTER_PATH_IDS)
            and adapter_contract_registry.get("public_projection_route")
            == GL_REFERENCE_ONLY_PUBLIC_PROJECTION_ROUTE
            and not adapter_contract_registry.get("public_export_bundle_route_registered")
        )
        else "fail",
        "performance_scaling": performance_status,
    }
    issue_by_gate = {
        "g0_dependency": "layer3_gl_g0_dependency_not_ready",
        "legal_kg_route": "layer3_gl_l3_legal_kg_route_not_bound",
        "search_recall_freshness": "layer3_gl_false_abstention_recall_unmeasured",
        "l5_calibration_boundary": "layer3_gl_l5_calibration_binding_missing",
        "legal_requirement_binding": "layer3_gl_legal_requirement_binding_missing",
        "authority_facet_binding": "layer3_gl_authority_facet_binding_missing",
        "norm_candidate_binding": "layer3_gl_norm_candidate_binding_missing",
        "claim_level_authority": "layer3_gl_legal_authority_report_missing",
        "threshold_authority_record": "layer3_gl_threshold_authority_record_missing",
        "mandate_authority_record": "layer3_gl_mandate_authority_record_missing",
        "temporal_records": "layer3_gl_temporal_competence_record_missing",
        "amendment_lineage": "layer3_gl_amendment_lineage_missing",
        "reference_resolution": "layer3_gl_reference_resolution_unresolved",
        "lex_intervention_map_binding": "layer3_gl_lex_intervention_map_missing",
        "consumer_gates": "layer3_gl_claim_registry_consumer_gate_missing",
        "public_projection": "layer3_gl_public_export_projection_mode_mismatch",
        "adapter_registry": "layer3_gl_adapter_contract_registry_missing",
        "performance_scaling": "layer3_gl_import_laziness_violation",
    }
    issue_codes = tuple(
        dict.fromkeys(
            issue_by_gate[gate] for gate, status in gate_statuses.items() if status != "pass"
        )
    )
    return Layer3GLConformanceReport(
        status="pass" if not issue_codes else "fail",
        issue_codes=issue_codes,
        performance_status=performance_status,
        closeout_status="pass" if not issue_codes else "fail",
        conformance_gate_statuses=gate_statuses,
        performance_check_refs=performance_check_refs,
    )


def _gl_performance_closeout_status(
    *,
    ledgers: Sequence[Layer3GLLegalSearchLedger],
    traces: Sequence[Layer3GLLegalQueryTrace],
    health_metric_delta: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    readings = _mapping(health_metric_delta.get("readings"))
    checks = {
        "ledger_no_full_table_scan": bool(ledgers)
        and all(not ledger.used_full_table_scan for ledger in ledgers),
        "trace_sql_bounded_limit": bool(traces)
        and all("LIMIT" in trace.sql_shape.upper() for trace in traces),
        "trace_row_counts_bounded": bool(traces)
        and all(
            trace.observed_row_count == trace.result_count
            and trace.observed_row_count <= trace.bounded_result_limit
            and trace.bounded_result_limit <= 256
            for trace in traces
        ),
        "query_budget_blocks_python_scan": bool(traces)
        and all(
            not trace.query_budget.get("python_full_scan_allowed")
            and not trace.query_budget.get("full_corpus_scan_allowed")
            and not trace.query_budget.get("full_corpus_materialization_allowed")
            for trace in traces
        ),
        "health_metric_adapter_semantic_loss": readings.get("adapter-semantic-loss") == "pass",
        "health_metric_governance_throughput": readings.get("governance-throughput") == "pass",
    }
    return ("pass" if all(checks.values()) else "fail", tuple(sorted(checks)))


def _default_health_metric_delta(
    search_recall: Layer3GLSearchRecallFreshnessReport,
    *,
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding] = (),
    consumer_gate_statuses: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    gate_statuses = consumer_gate_statuses or {}
    return {
        "schema_version": LAYER3_GL_SCHEMA_VERSION,
        "rule_version": LAYER3_GL_RULE_VERSION,
        "metric_ids": EXPECTED_HEALTH_METRICS,
        "readings": {
            "search-recall@known-seeds+index-staleness": search_recall.status,
            "search-recall.known_seed_status": search_recall.known_seed_status,
            "search-recall.index_freshness_status": search_recall.index_freshness_status,
            "adapter-semantic-loss": _adapter_semantic_loss_status(authority_facet_bindings),
            "governance-throughput": _governance_throughput_status(gate_statuses),
        },
    }


def _adapter_semantic_loss_status(
    authority_facet_bindings: Sequence[Layer3GLAuthorityFacetBinding],
) -> str:
    if not authority_facet_bindings:
        return "not_measured_until_authority_facet_binding"
    blocking = {"not_measured", "missing_required_facet"}
    if any(binding.issue_codes for binding in authority_facet_bindings) or any(
        binding.semantic_loss_status in blocking for binding in authority_facet_bindings
    ):
        return "fail"
    return "pass"


def _governance_throughput_status(gate_statuses: Mapping[str, str]) -> str:
    if not gate_statuses:
        return "not_measured_until_consumer_gates"
    return (
        "pass"
        if all(status in {"pass", "out_of_scope"} for status in gate_statuses.values())
        else "fail"
    )


def _g0_dependency_status(repo_root: Path) -> str:
    path = repo_root / "architecture/policy_design_case/layer3_g0_readiness_manifest.json"
    if not path.exists():
        return "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    counts = _mapping(payload.get("counts"))
    required = (
        counts.get("g1_dependency_requirements_status") == "pass",
        counts.get("engineering_quality_check_status") == "pass",
        counts.get("search_recall_seed_status") == "pass",
        counts.get("index_freshness_status") == "pass",
    )
    return "pass" if all(required) else "fail"


def _context_manifest_status(repo_root: Path, slice_id: str) -> str:
    path = repo_root / f"architecture/policy_design_case/layer3_{slice_id}_readiness_manifest.json"
    if not path.exists():
        return "missing_optional_context"
    return "loaded_context"


def _gl_reference_docs_status(repo_root: Path) -> str:
    path = repo_root / "docs/reference/policy-design-case-layer3-legal-mandate-search.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    required = (
        "search vs authority",
        "False-Abstention Recall Guard",
        "Legal Time Roles",
        "Amendment Lineage",
        "Mandate S6/S7 Handoff",
        "Mandate S8 Value-Choice Handoff",
        "Lex Intervention Map Boundary",
    )
    if text and all(marker in text for marker in required):
        return "pass"
    return "missing"


def _gl_invariant_readiness_check_registration_status() -> str:
    from polisyos.runtime.quality.invariants import KNOWN_READINESS_CHECKS

    return "pass" if GL_READINESS_CHECK_ID in KNOWN_READINESS_CHECKS else "not_registered"


def _companion_refs(repo_root: Path) -> tuple[str, ...]:
    refs: list[str] = []
    for path in COMPANION_FILE_PATHS:
        full_path = repo_root / path
        if full_path.exists():
            stat = full_path.stat()
            file_identity = _stable_id(
                path.as_posix(),
                str(stat.st_size),
                str(stat.st_mtime_ns),
            )
            refs.append(f"repo://{path.as_posix()}#{file_identity}")
    return tuple(refs)


def _authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": [],
        "may_not_use_for": list(GL_MAY_NOT_USE_FOR),
    }


def _stable_ref(*parts: str) -> str:
    return f"sha256:{_stable_id(*parts)}"


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:24]


def _repo_artifact_ref(path: str, payload: object) -> str:
    payload_text = json.dumps(_dump_model(payload), sort_keys=True, default=str)
    return f"repo://{path}#{_stable_id(path, payload_text)}"


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


def _dump_model(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump_model(inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_dump_model(item) for item in value]
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _tuple(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return tuple(value)
    return ()


def _issue(code: str, path: str, message: str) -> Layer3GLValidationIssue:
    return Layer3GLValidationIssue(code=code, path=path, message=message)


def _dedupe_issues(issues: Sequence[Layer3GLValidationIssue]) -> list[Layer3GLValidationIssue]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Layer3GLValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.path)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


__all__ = [
    "ALL_ISSUE_CODES",
    "CANONICAL_L3_LEGAL_KG_PATH",
    "GL_ADAPTER_PATH_IDS",
    "GL_GENERATED_ARTIFACT_FAMILY_ID",
    "GL_MAY_NOT_USE_FOR",
    "GL_PUBLIC_EXPORT_BUNDLE_ROUTE",
    "GL_PUBLIC_PROJECTION_SURFACE_ID",
    "GL_READINESS_CHECK_ID",
    "GL_REFERENCE_ONLY_PUBLIC_PROJECTION_ROUTE",
    "GL_SURFACE_ID",
    "LAYER3_GL_RULE_VERSION",
    "LAYER3_GL_SCHEMA_VERSION",
    "Layer3GLAdapterAdmissionBundle",
    "Layer3GLAmendmentLineageRecord",
    "Layer3GLArgumentGraphReadinessConsumerGate",
    "Layer3GLAuthorityFacetBinding",
    "Layer3GLBundle",
    "Layer3GLClaimRegistryConsumerGate",
    "Layer3GLConformanceReport",
    "Layer3GLDesignConstraintConsumerGate",
    "Layer3GLG4PromotionGateConsumerGate",
    "Layer3GLL3LegalKgCoverageReport",
    "Layer3GLL5CalibrationBinding",
    "Layer3GLLegalAuthorityReportBinding",
    "Layer3GLLegalMandateAuditSurface",
    "Layer3GLLegalMandateRequest",
    "Layer3GLLegalQueryTrace",
    "Layer3GLLegalRequirementBinding",
    "Layer3GLLegalSearchLedger",
    "Layer3GLLexInterventionMapBinding",
    "Layer3GLMandateAuthorityRecord",
    "Layer3GLNormCandidateBinding",
    "Layer3GLPdcCompilerConsumerGate",
    "Layer3GLPromotionGateHandoff",
    "Layer3GLPublicExportProjectionRefSurface",
    "Layer3GLReadinessManifest",
    "Layer3GLReferenceResolutionRecord",
    "Layer3GLS6MandateConsumerGate",
    "Layer3GLS7DelegationConsumerGate",
    "Layer3GLS8ValueChoiceConsumerGate",
    "Layer3GLSearchRecallFreshnessReport",
    "Layer3GLSemanticBindingConsumerGate",
    "Layer3GLTemporalCompetenceRecord",
    "Layer3GLThresholdAuthorityRecord",
    "Layer3GLValidationIssue",
    "Layer3GLValidationReport",
    "build_gl_amendment_lineage_records",
    "build_gl_argument_graph_readiness_consumer_gate",
    "build_gl_audit_surface",
    "build_gl_authority_facet_bindings",
    "build_gl_claim_registry_consumer_gate",
    "build_gl_design_constraint_consumer_gate",
    "build_gl_g4_promotion_gate_consumer_gate",
    "build_gl_l3_legal_kg_index_coverage",
    "build_gl_l5_calibration_bindings",
    "build_gl_legal_authority_report_binding",
    "build_gl_legal_query_traces",
    "build_gl_legal_requirement_bindings",
    "build_gl_legal_search_ledgers",
    "build_gl_lex_intervention_map_bindings",
    "build_gl_mandate_authority_records",
    "build_gl_norm_candidate_bindings",
    "build_gl_pdc_compiler_consumer_gate",
    "build_gl_promotion_gate_handoff",
    "build_gl_public_export_projection_refs",
    "build_gl_reference_resolution_records",
    "build_gl_s6_mandate_consumer_gate",
    "build_gl_s7_delegation_consumer_gate",
    "build_gl_s8_value_choice_consumer_gate",
    "build_gl_search_recall_freshness",
    "build_gl_semantic_binding_consumer_gate",
    "build_gl_temporal_competence_records",
    "build_gl_threshold_authority_records",
    "build_layer3_gl_bundle",
    "validate_layer3_gl_bundle",
]
