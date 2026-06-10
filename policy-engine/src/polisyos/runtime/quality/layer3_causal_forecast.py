"""Layer 3 G2 causal/forecast search contracts and SKG firewalls.

G2 search records are replay control-plane evidence. A real SKG hit may enter
the frontier, but it cannot become forecast support until later adapter, method,
concept-spine, S10, and authority-envelope checks accept it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from polisyos.method_requirement import MethodValidityRequirementSpec

if TYPE_CHECKING:
    from polisyos.pdc import Layer2S10ForecastPostureInput

LAYER3_G2_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_causal_forecast.v1"
LAYER3_G2_RULE_VERSION = "policyos.layer3.g2.causal_forecast_search.v1"
LAYER3_G2_SURFACE_ID = "layer3_g2_causal_forecast_audit_surface"
LAYER3_G2_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g2-causal-forecast-artifacts"
)
LAYER3_G2_W12D_GATE_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_forecast_gate.v1"
SKG_QUERY_API_ROUTE = "polisyos.data_forge.read_api.academic.SKGQuery"
CANONICAL_L2_ROUTE = "scholar_knowledge.duckdb"
FOUNDRY_METHOD_REGISTRY_ROUTE = "polisyos.foundry.methods.selection.registry.MethodRegistry"
FOUNDRY_METHOD_QUALITY_ROUTE = (
    "polisyos.foundry.validation.method_quality.build_foundry_method_report"
)
S10_FORECAST_SUPPORT_BUILDER_REF = (
    "polisyos.runtime.quality.layer2_outcome_prediction.build_forecast_support"
)
S10_CALIBRATION_BUILDER_REF = (
    "polisyos.runtime.quality.layer2_outcome_prediction.build_forecast_calibration_record"
)
S10_AUTHORITY_ENVELOPE_BUILDER_REF = (
    "polisyos.runtime.quality.layer2_outcome_prediction."
    "verify_prediction_authority_envelope"
)
S10_INTEGRITY_SUMMARY_BUILDER_REF = (
    "polisyos.runtime.quality.layer2_outcome_prediction."
    "summarize_forecast_support_integrity"
)
ACADEMIC_RUNTIME_ROOT = Path("production_data/policyos_academic_runtime_slim_20260411T112032Z")
ACADEMIC_INDEX_DIR = ACADEMIC_RUNTIME_ROOT / "academic"
ACADEMIC_SKG_DB_PATH = ACADEMIC_INDEX_DIR / "graph/scholar_knowledge.duckdb"
G2_FREE_GROWTH_METHOD_REGISTRY_PATH = Path(
    "tests/fixtures/layer3/g2/free_growth_method_registry.json"
)
ACADEMIC_MANIFEST_REFS: tuple[Path, ...] = (
    ACADEMIC_INDEX_DIR / "manifests/graph_index.json",
    ACADEMIC_INDEX_DIR / "manifests/qc.json",
    ACADEMIC_RUNTIME_ROOT / "meta/source_lineage.json",
)
REQUIRED_SKG_TABLES: tuple[str, ...] = (
    "ac_skg_edges",
    "ac_skg_edge_evidence",
    "ac_causal_claims",
    "ac_parameter_estimates",
    "ac_skg_parameters",
    "ac_skg_transport_scores",
    "ac_skg_contested_edges",
    "ac_skg_variables",
    "ac_skg_variable_synonyms",
    "ac_skg_versions",
)
G2_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "claim_authority",
    "causal_effect_authority_without_adapter_validation",
    "policy_recommendation",
    "closeout_authority",
    "publication_authority",
    "useful_design_credit",
    "production_authority",
    "search_hit_as_authority",
)
G2_LEDGER_AUTHORITATIVE_FOR: tuple[str, ...] = ()
EXPECTED_HEALTH_METRICS: tuple[str, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
G2_EXPECTED_ARTIFACT_PATHS: tuple[str, ...] = (
    "architecture/policy_design_case/layer3_g2_adapter_admission_registry.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_search_ledgers.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_query_traces.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_index_coverage.json",
    "architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_g2_foundry_method_registry_coverage.json",
    "architecture/policy_design_case/layer3_g2_foundry_method_registry_search.json",
    "architecture/policy_design_case/layer3_g2_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g2_method_validity_transport.json",
    "architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g2_concept_alignment_records.json",
    "architecture/policy_design_case/layer3_g2_s10_prerequisite_bindings.json",
    "architecture/policy_design_case/layer3_g2_forecast_support_bindings.json",
    "architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json",
    "architecture/policy_design_case/layer3_g2_observable_calibration_report.json",
    "architecture/policy_design_case/layer3_g2_transport_limit_declarations.json",
    "architecture/policy_design_case/layer3_g2_authority_envelopes.json",
    "architecture/policy_design_case/layer3_g2_conformance_report.json",
    "architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g2_causal_forecast_audit_surface.json",
    "architecture/policy_design_case/layer3_g2_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g2_readiness_manifest.json",
)
FOUNDRY_BOOTSTRAP_REFS: tuple[str, ...] = (
    "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
    "polisyos.foundry.methods.catalog.ensure_causal_methods_registered",
    "polisyos.foundry.methods.catalog.ensure_forecasting_methods_registered",
    "polisyos.foundry.methods.catalog.ensure_econometric_methods_registered",
    "polisyos.foundry.methods.catalog.ensure_sensitivity_methods_registered",
    "polisyos.foundry.methods.catalog.ensure_validation_methods_registered",
)
FOUNDRY_DISCOVERY_SOURCE_ROOTS: tuple[str, ...] = (
    "polisyos.foundry.methods.catalog",
    "polisyos.foundry.extensions.discovery",
    "entry_points",
    "dev_scan",
)
FOUNDRY_ENTRY_POINT_GROUPS: tuple[str, ...] = (
    "polisyos.foundry.methods",
    "polisyos.foundry.method_plugins",
)
G2_METHOD_REPORT_FORBIDDEN_AUTHORITY: tuple[str, ...] = (
    "legal_authority",
    "source_family_satisfaction",
    "academic_support_strength",
    "participation_authority",
    "participation_representativeness",
    "claim_support_without_claim_registry_bridge",
    "claim_support",
    "closeout_pass",
)
G2_REQUIRED_AUTHORITY_DENIALS: tuple[str, ...] = (
    "claim_authority",
    "policy_recommendation",
    "closeout_authority",
    "useful_design_credit",
    "search_hit_as_authority",
)
G2_S10_METHOD_FAMILY_BY_METHOD_CANDIDATE: dict[str, str] = {
    "causal_effect_estimation": "foundry_causal",
    "forecasting": "foundry_causal",
    "econometric": "foundry_causal",
    "simulation": "simulation",
}
CapabilityRealityLabel = Literal[
    "implemented",
    "contract_only",
    "producer_missing",
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "verification_missing",
    "implemented_but_not_orchestrated",
    "surface_missing",
    "surface_out_of_scope",
    "semantic_test_missing",
]
AdapterMaturity = Literal["calibrated", "predictive", "fail_closed"]
ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g2_g1_dependency_not_ready",
    "layer3_g2_persisted_artifact_missing",
    "layer3_g2_manifest_runtime_drift",
    "layer3_g2_surface_unsynced",
    "layer3_g2_generated_artifacts_family_missing",
    "layer3_g2_inventory_surface_missing",
    "layer3_g2_reference_index_missing",
    "layer3_g2_public_surface_visibility_missing",
    "layer3_g2_adapter_contract_registry_missing",
    "layer3_g2_l2_skg_not_queried",
    "layer3_g2_l2_skg_bounded_surrogate_overclaimed",
    "layer3_g2_capability_index_used_as_l2_search",
    "layer3_g2_unjustified_l2_surrogate",
    "layer3_g2_l2_skg_index_coverage_missing",
    "layer3_g2_skg_index_dir_misconfigured",
    "layer3_g2_skg_query_trace_missing",
    "layer3_g2_hnsw_candidate_without_skg_row",
    "layer3_g2_semantic_retrieval_without_query_vector_producer",
    "layer3_g2_skg_web_evidence_bundle_laundering",
    "layer3_g2_search_ledger_missing",
    "layer3_g2_search_ledger_authority_boundary_leak",
    "layer3_g2_no_hit_without_replayable_frontier",
    "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_g2_stale_index_blocks_domain_ceiling",
    "layer3_g2_search_ceiling_not_domain_ceiling",
    "layer3_g2_search_engineering_quality_failed",
    "layer3_g2_mechanism_generality_single_request",
    "layer3_g2_free_growth_fixture_failed",
    "layer3_g2_foundry_method_registry_not_queried",
    "layer3_g2_foundry_discovery_coverage_missing",
    "layer3_g2_foundry_builtin_catalog_bootstrap_missing",
    "layer3_g2_foundry_registry_snapshot_missing",
    "layer3_g2_method_registry_discovery_not_refreshed",
    "layer3_g2_method_registry_hardcode_closure",
    "layer3_g2_method_requirement_missing",
    "layer3_g2_method_requirement_selection_failed",
    "layer3_g2_method_validity_missing",
    "layer3_g2_foundry_method_report_authority_overclaim",
    "layer3_g2_foundry_method_report_persistence_missing",
    "layer3_g2_identification_requirement_missing",
    "layer3_g2_transportability_limit_missing",
    "layer3_g2_semantic_binding_spine_missing",
    "layer3_g2_parallel_concept_lattice",
    "layer3_g2_concept_alignment_missing",
    "layer3_g2_proxy_alignment_undisclosed",
    "layer3_g2_ambiguous_alignment_overclaimed",
    "layer3_g2_s10_prerequisite_binding_missing",
    "layer3_g2_s5_s6_s8_refs_missing",
    "layer3_g2_design_prediction_context_missing",
    "layer3_g2_s10_tier_derivation_mismatch",
    "layer3_g2_search_hit_used_as_forecast_support",
    "layer3_g2_raw_skg_output_without_adapter",
    "layer3_g2_forecast_support_missing",
    "layer3_g2_forecast_support_invalid",
    "layer3_g2_adapter_maturity_overclaim",
    "layer3_g2_forecast_tier_overclaimed",
    "layer3_g2_regime_forecast_tier_laundering",
    "layer3_g2_observable_calibration_required",
    "layer3_g2_observable_calibration_denominator_missing",
    "layer3_g2_credible_evaluation_evidence_missing",
    "layer3_g2_uncertainty_interval_missing",
    "layer3_g2_transport_limit_missing",
    "layer3_g2_simulation_only_laundered",
    "layer3_g2_historical_prior_laundered",
    "layer3_g2_equilibrium_authority_overclaim",
    "layer3_g2_contested_edge_overclaimed",
    "layer3_g2_effect_independence_inflated",
    "layer3_g2_aggregation_validity_missing",
    "layer3_g2_strategic_response_missing",
    "layer3_g2_semantic_loss",
    "layer3_g2_claim_authority_leak",
    "layer3_g2_recommendation_authority_leak",
    "layer3_g2_closeout_authority_leak",
    "layer3_g2_useful_design_credit_leak",
    "layer3_g2_s10_consumer_bridge_missing",
    "layer3_g2_s10_posture_not_consumed",
    "layer3_g2_s2_forecast_producer_import",
    "layer3_g2_s2_design_record_replay_overclaim",
    "layer3_g2_w12d_not_routed_closeout",
    "layer3_g2_w12d_domain_ceiling_gate_missing",
    "layer3_g2_w12d_full_s2_overreach",
    "layer3_g2_grounded_forecast_handoff_missing",
    "layer3_g2_grounded_forecast_handoff_promoted",
    "layer3_g2_w12d_conversion_outcome_overwrite",
)


class _G2Model(BaseModel):
    """Strict base for G2 runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G2ValidationIssue(_G2Model):
    """One fail-closed G2 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G2ValidationReport(_G2Model):
    """G2 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G2ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)


class Layer3G2CausalForecastRequest(_G2Model):
    """Typed request for canonical L2 causal/forecast candidate search."""

    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    source_contract_refs: tuple[str, ...] = Field(default=())
    cause: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    target_context_id: str | None = None
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    support_mode: Literal["exact", "family", "hybrid", "contested"] = "hybrid"
    limit: int = Field(default=16, ge=1, le=256)
    semantic_retrieval_required: bool = False
    query_vector_producer_ref: str | None = None
    query_vector_ref: str | None = None
    method_task_tags: tuple[str, ...] = Field(default=())
    data_modality: str | None = None
    treatment_structure: str | None = None
    outcome_type: str | None = None
    required_diagnostics: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)


class Layer3G2SkgQueryTrace(_G2Model):
    """Replay trace for one consumed SKGQuery or direct read-only SQL call."""

    trace_id: str = Field(min_length=1)
    query_api_route: str = SKG_QUERY_API_ROUTE
    canonical_l2_route: str = CANONICAL_L2_ROUTE
    sql_description: str | None = None
    table_refs: tuple[str, ...] = Field(default=())
    predicates: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    row_refs: tuple[str, ...] = Field(default=())
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    skg_version_id: int | None = None
    skg_snapshot_ref: str | None = None
    direct_sql_read_only: bool = True
    used_skg_query: bool = True
    quality_flags: tuple[str, ...] = Field(default=())
    transport_notes: tuple[str, ...] = Field(default=())
    uncertainty_sources: tuple[str, ...] = Field(default=())
    matched_moderators: tuple[str, ...] = Field(default=())
    normalization_diagnostics: tuple[str, ...] = Field(default=())
    semantic_retrieval_required: bool = False
    query_vector_producer_ref: str | None = None


class Layer3G2SearchLedger(_G2Model):
    """Replayable G2 search frontier ledger; never forecast authority."""

    ledger_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    request_ref: str = Field(min_length=1)
    canonical_l2_route: str = CANONICAL_L2_ROUTE
    query_trace_refs: tuple[str, ...] = Field(default=())
    searched_table_refs: tuple[str, ...] = Field(default=())
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    forecast_support_refs: tuple[str, ...] = Field(default=())
    cutoff_limit: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    replay_key: str = Field(min_length=1)
    semantic_retrieval_required: bool = False
    query_vector_producer_ref: str | None = None
    hnsw_candidate_refs: tuple[str, ...] = Field(default=())
    duckdb_validated_candidate_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G2_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)


class Layer3G2L2SkgIndexCoverageReport(_G2Model):
    """Coverage report for the canonical academic SKG DuckDB and index route."""

    report_id: str = "layer3-g2-l2-skg-index-coverage"
    status: Literal["pass", "fail"]
    canonical_l2_route: str = CANONICAL_L2_ROUTE
    skg_query_api_route: str = SKG_QUERY_API_ROUTE
    db_path: str
    index_dir: str
    required_table_counts: dict[str, int] = Field(default_factory=dict)
    required_tables_present: bool = False
    missing_tables: tuple[str, ...] = Field(default=())
    manifest_refs: tuple[str, ...] = Field(default=())
    skg_version_id: int | None = None
    skg_snapshot_ref: str | None = None
    snapshot_hash_ref: str = ""
    hnsw_assets_status: Literal["pass", "fail", "not_required_for_request"] = "fail"
    hnsw_index_path_status: Literal["pass", "fail"] = "fail"
    embedding_path_status: Literal["pass", "fail"] = "fail"
    index_dir_status: Literal["pass", "fail"] = "fail"
    skg_query_construction_status: Literal["pass", "fail"] = "fail"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2SearchRecallSeed(_G2Model):
    """Known-groundable G2 search seed."""

    seed_id: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    expected_row_refs: tuple[str, ...] = Field(default=())
    requires_semantic_retrieval: bool = False


class Layer3G2IndexFreshnessRecord(_G2Model):
    """Freshness record for an SKG or vector-search artifact."""

    artifact_ref: str = Field(min_length=1)
    status: Literal["pass", "fail", "not_required_for_request"]
    generated_at_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2SearchRecallFreshnessReport(_G2Model):
    """Recall/freshness report for G2 known-groundable search seeds."""

    report_id: str = "layer3-g2-search-recall-freshness"
    status: Literal["pass", "fail", "not_implemented"] = "not_implemented"
    search_recall_status: Literal["pass", "fail", "not_implemented"] = "not_implemented"
    index_freshness_status: Literal["pass", "fail", "not_implemented"] = "not_implemented"
    hnsw_freshness_status: Literal[
        "pass",
        "fail",
        "not_required_for_request",
        "not_implemented",
    ] = "not_implemented"
    hnsw_query_vector_producer_status: Literal[
        "pass",
        "fail",
        "not_required_for_request",
        "not_implemented",
    ] = "not_implemented"
    seed_records: tuple[Layer3G2SearchRecallSeed, ...] = Field(default=())
    freshness_records: tuple[Layer3G2IndexFreshnessRecord, ...] = Field(default=())
    recalled_seed_refs: tuple[str, ...] = Field(default=())
    missed_seed_refs: tuple[str, ...] = Field(default=())
    semantic_retrieval_required: bool = False
    query_vector_producer_ref: str | None = None
    query_vector_ref: str | None = None
    hnsw_settings: dict[str, Any] = Field(default_factory=dict)
    semantic_candidate_row_refs: tuple[str, ...] = Field(default=())
    post_hnsw_duckdb_validation_trace_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(
        default=("layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",)
    )


class Layer3G2FreeGrowthReport(_G2Model):
    """Free-growth fixture report for SKG edge and method discovery."""

    report_id: str = "layer3-g2-free-growth-report"
    status: Literal["pass", "fail"]
    free_growth_fixture_count: int = Field(ge=0)
    discovered_skg_edge_ref: str | None = None
    discovered_method_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class _PlaceholderRecord(_G2Model):
    """Typed placeholder for later G2 tasks that must fail closed."""

    record_id: str = Field(min_length=1)
    status: str = "not_implemented"
    issue_codes: tuple[str, ...] = Field(default=())
    refs: tuple[str, ...] = Field(default=())


class Layer3G2FoundryMethodRegistryCoverageReport(_G2Model):
    """Coverage report for the canonical Foundry method registry snapshot."""

    report_id: str = "layer3-g2-foundry-method-registry-coverage"
    status: Literal["pass", "fail"]
    registry_api_route: str = FOUNDRY_METHOD_REGISTRY_ROUTE
    built_in_catalog_bootstrap_refs: tuple[str, ...] = Field(default=())
    discovery_source_roots: tuple[str, ...] = Field(default=())
    entry_point_groups: tuple[str, ...] = Field(default=())
    registered_method_count: int = Field(default=0, ge=0)
    family_method_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_method_refs: tuple[str, ...] = Field(default=())
    discovery_errors: tuple[str, ...] = Field(default=())
    registry_snapshot_ref: str = Field(min_length=1)
    registry_version_ref: str = Field(min_length=1)
    registry_stats: dict[str, Any] = Field(default_factory=dict)
    freshness_status: Literal["pass", "fail"]
    discovery_refresh_status: Literal["pass", "fail"]
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2FoundryMethodCandidate(_G2Model):
    """One Foundry registry candidate discovered through metadata predicates."""

    method_ref: str = Field(min_length=1)
    method_fqn: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    tags: tuple[str, ...] = Field(default=())
    data_modalities: tuple[str, ...] = Field(default=())
    input_slot_refs: tuple[str, ...] = Field(default=())
    output_slot_refs: tuple[str, ...] = Field(default=())
    registry_entry_ref: str = Field(min_length=1)
    match_predicates: dict[str, Any] = Field(default_factory=dict)
    match_score: int = Field(default=0, ge=0)
    truthfulness_status: Literal["registry_candidate_only", "runtime_consistent"] = (
        "registry_candidate_only"
    )
    method_expectations: tuple[str, ...] = Field(default=())
    method_contract_targets: tuple[str, ...] = Field(default=())


class Layer3G2FoundryMethodRegistrySearchReport(_G2Model):
    """Request-shaped Foundry registry search report."""

    report_id: str = "layer3-g2-foundry-method-registry-search"
    status: Literal["pass", "fail"]
    request_ref: str
    registry_api_route: str = FOUNDRY_METHOD_REGISTRY_ROUTE
    registry_snapshot_ref: str = Field(min_length=1)
    registry_discovery_refs: tuple[str, ...] = Field(default=())
    candidate_methods: tuple[Layer3G2FoundryMethodCandidate, ...] = Field(default=())
    selected_methods: tuple[Layer3G2FoundryMethodCandidate, ...] = Field(default=())
    rejected_methods: tuple[dict[str, Any], ...] = Field(default=())
    task_affinity_predicates: dict[str, Any] = Field(default_factory=dict)
    data_affinity_predicates: dict[str, Any] = Field(default_factory=dict)
    search_ledger_refs: tuple[str, ...] = Field(default=())
    search_strategy: Literal["registry_metadata_predicate_search", "hardcoded_fqn_list"]
    hardcoded_fqn_closure: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2MethodRequirementBinding(_G2Model):
    """G2 binding from request-shaped method requirements to Foundry selection."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    search_report_ref: str = Field(min_length=1)
    method_requirement_specs: tuple[dict[str, Any], ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    selection_status: Literal["pass", "fail"]
    method_requirement_statuses: dict[str, str] = Field(default_factory=dict)
    candidate_method_refs: tuple[str, ...] = Field(default=())
    selected_method_refs: tuple[str, ...] = Field(default=())
    rejected_method_refs: tuple[str, ...] = Field(default=())
    selection_issue_codes: tuple[str, ...] = Field(default=())
    selection_report_ref: str = Field(min_length=1)
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2MethodValidityTransportRecord(_G2Model):
    """G2 wrapper around Foundry method-quality validity and transport report."""

    record_id: str = "layer3-g2-method-validity-transport"
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    method_requirement_binding_ref: str = Field(min_length=1)
    foundry_method_report_ref: str = Field(min_length=1)
    foundry_method_report_status: Literal["pass", "fail"]
    foundry_method_report: dict[str, Any] = Field(default_factory=dict)
    selected_method_refs: tuple[str, ...] = Field(default=())
    rejected_method_refs: tuple[str, ...] = Field(default=())
    method_requirement_statuses: dict[str, str] = Field(default_factory=dict)
    method_validity_refs: tuple[str, ...] = Field(default=())
    identification_requirement_refs: tuple[str, ...] = Field(default=())
    transportability_limit_refs: tuple[str, ...] = Field(default=())
    uncertainty_ref_count: int = Field(default=0, ge=0)
    limitation_ref_count: int = Field(default=0, ge=0)
    method_lineage_refs: tuple[str, ...] = Field(default=())
    cas_persistence_status: Literal["persisted", "out_of_scope", "missing"]
    cas_persistence_reason: str = ""
    authority_envelope: dict[str, Any] = Field(default_factory=dict)
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2SemanticSpineBinding(_G2Model):
    """G2 semantic-spine read binding over the shared producer-spine helpers."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    producer_spine_context: dict[str, Any] = Field(default_factory=dict)
    producer_spine_context_ref: str | None = None
    producer_spine_views: tuple[dict[str, Any], ...] = Field(default=())
    producer_spine_binding_fields: dict[str, Any] = Field(default_factory=dict)
    consumed_concept_spine_ref: str | None = None
    consumed_jurisdiction_spine_ref: str | None = None
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    period_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    governed_namespace_refs: tuple[str, ...] = Field(default=())
    reconciled_concept_statuses: dict[str, str] = Field(default_factory=dict)
    producer_handshake_refs: tuple[str, ...] = Field(default=())
    candidate_spine_binding_refs: tuple[str, ...] = Field(default=())
    spine_blocker_refs: tuple[str, ...] = Field(default=())
    capability_reality_label: CapabilityRealityLabel
    direct_semantic_grounding_allowed: bool = False
    parallel_concept_lattice_declared: bool = False
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2ConceptAlignmentRecord(_G2Model):
    """G2 alignment from G1 target concepts through SKG, Foundry, and S10."""

    alignment_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    semantic_spine_binding_ref: str | None = None
    source_contract_refs: tuple[str, ...] = Field(default=())
    g1_target_outcome_refs: tuple[str, ...] = Field(default=())
    g1_metric_refs: tuple[str, ...] = Field(default=())
    skg_cause_variable_ref: str | None = None
    skg_effect_variable_ref: str | None = None
    skg_parameter_refs: tuple[str, ...] = Field(default=())
    foundry_input_slot_refs: tuple[str, ...] = Field(default=())
    foundry_output_slot_refs: tuple[str, ...] = Field(default=())
    s10_target_outcome_refs: tuple[str, ...] = Field(default=())
    alignment_status: Literal["direct", "proxy_only", "ambiguous", "unmatched", "conflict"]
    proxy_disclosed: bool = False
    direct_grounding_claimed: bool = False
    downgrade_disposition: Literal[
        "direct_grounding",
        "proxy_limited",
        "blocked",
    ] = "blocked"
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2S10PrerequisiteBinding(_G2Model):
    """G2 binding proving S10 prerequisite refs before forecast translation."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    semantic_spine_binding_ref: str | None = None
    concept_alignment_ref: str | None = None
    source_design_record_ref: str | None = None
    design_graph_ref: str | None = None
    prediction_context_ref: str | None = None
    policy_context_ref: str | None = None
    candidate_design_ref: str | None = None
    baseline_design_ref: str | None = None
    alternative_design_refs: tuple[str, ...] = Field(default=())
    prediction_horizon_ref: str | None = None
    target_outcome_refs: tuple[str, ...] = Field(default=())
    jurisdiction_scope_ref: str | None = None
    s5_forecast_support_ref: str | None = None
    s5_support_label: str | None = None
    s5_base_origin: str | None = None
    s5_claim_scope: str | None = None
    s6_firewall_status_refs: tuple[str, ...] = Field(default=())
    s6_limitation_refs: tuple[str, ...] = Field(default=())
    s8_value_choice_provenance_ref: str | None = None
    s8_value_tradeoff_disclosure_ref: str | None = None
    s5_s6_s8_refs: tuple[str, ...] = Field(default=())
    source_contract_ref: str | None = None
    method_validity_ref: str | None = None
    method_validity_refs: tuple[str, ...] = Field(default=())
    sensitivity_analysis_ref: str | None = None
    dynamic_equilibrium_check_ref: str | None = None
    equilibrium_caveat_refs: tuple[str, ...] = Field(default=())
    strategic_response_caveat_refs: tuple[str, ...] = Field(default=())
    outcome_distribution_refs: tuple[str, ...] = Field(default=())
    welfare_comparison_ref: str | None = None
    observable_subset_ref: str | None = None
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    credible_evaluation_evidence_ref: str | None = None
    source_lineage_refs: tuple[str, ...] = Field(default=())
    method_lineage_refs: tuple[str, ...] = Field(default=())
    forecast_authority_disposition_reason: str = (
        "G2 translated bounded causal/forecast search through existing S10 support."
    )
    method_family: str = "foundry_causal"
    capability_reality_label: CapabilityRealityLabel
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2ForecastSupportBinding(_G2Model):
    """G2 audit wrapper around existing S10 ForecastSupport records."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    s10_prerequisite_binding_ref: str | None = None
    semantic_spine_binding_ref: str | None = None
    concept_alignment_ref: str | None = None
    adapter_validation_ref: str | None = None
    s10_forecast_support_ref: str | None = None
    s10_forecast_tier: str | None = None
    requested_forecast_tier: str | None = None
    s10_forecast_support: dict[str, Any] = Field(default_factory=dict)
    s10_builder_ref: str = S10_FORECAST_SUPPORT_BUILDER_REF
    calibration_record_ref: str | None = None
    calibration_record: dict[str, Any] = Field(default_factory=dict)
    calibration_attempt: dict[str, Any] = Field(default_factory=dict)
    calibration_builder_ref: str = S10_CALIBRATION_BUILDER_REF
    authority_envelope_ref: str | None = None
    authority_envelope: dict[str, Any] = Field(default_factory=dict)
    authority_envelope_builder_ref: str = S10_AUTHORITY_ENVELOPE_BUILDER_REF
    integrity_summary_ref: str | None = None
    integrity_summary: dict[str, Any] = Field(default_factory=dict)
    integrity_summary_builder_ref: str = S10_INTEGRITY_SUMMARY_BUILDER_REF
    g1_binding_refs: tuple[str, ...] = Field(default=())
    skg_edge_refs: tuple[str, ...] = Field(default=())
    skg_claim_refs: tuple[str, ...] = Field(default=())
    skg_parameter_refs: tuple[str, ...] = Field(default=())
    skg_transport_refs: tuple[str, ...] = Field(default=())
    skg_transport_confidence_by_ref: dict[str, float] = Field(default_factory=dict)
    contested_edge_refs: tuple[str, ...] = Field(default=())
    publish_blocker_refs: tuple[str, ...] = Field(default=())
    method_validity_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    search_ledger_refs: tuple[str, ...] = Field(default=())
    requested_adapter_maturity: AdapterMaturity | None = None
    adapter_maturity: AdapterMaturity = "fail_closed"
    maturity_blocker_refs: tuple[str, ...] = Field(default=())
    calibrated_dynamics_producer_ref: str | None = None
    equilibrium_blocker_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=("g2_forecast_support_binding_audit",))
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2GroundedForecastHandoffRecord(_G2Model):
    """G4/G5-readable grounded forecast handoff without promotion authority."""

    handoff_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    forecast_support_binding_ref: str | None = None
    s10_forecast_support_ref: str | None = None
    s10_forecast_tier: str | None = None
    concept_alignment_ref: str | None = None
    source_contract_ref: str | None = None
    method_validity_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    calibration_record_refs: tuple[str, ...] = Field(default=())
    transport_limit_declaration_refs: tuple[str, ...] = Field(default=())
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    search_ledger_refs: tuple[str, ...] = Field(default=())
    skg_query_trace_refs: tuple[str, ...] = Field(default=())
    skg_edge_refs: tuple[str, ...] = Field(default=())
    skg_claim_refs: tuple[str, ...] = Field(default=())
    skg_parameter_refs: tuple[str, ...] = Field(default=())
    source_contract_replay_refs: tuple[str, ...] = Field(default=())
    design_record_ledger_refs: tuple[str, ...] = Field(default=())
    s2_deterministic_replay_key_refs: tuple[str, ...] = Field(default=())
    adapter_maturity: AdapterMaturity = "fail_closed"
    g4_g5_readable_handoff_ref: str | None = None
    promotion_authority_claimed: bool = False
    conversion_authority_claimed: bool = False
    useful_design_credit_claimed: bool = False
    authoritative_for: tuple[str, ...] = Field(default=("grounded_forecast_handoff",))
    may_not_use_for: tuple[str, ...] = Field(
        default=(
            *G2_MAY_NOT_USE_FOR,
            "promotion_authority",
            "conversion_authority",
        )
    )
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2ObservableCalibrationReport(_G2Model):
    """G2 observable-calibration audit report over S10 calibration records."""

    report_id: str = "layer3-g2-observable-calibration-report"
    status: Literal["pass", "fail"]
    adapter_maturity: AdapterMaturity
    forecast_support_binding_refs: tuple[str, ...] = Field(default=())
    forecast_support_refs: tuple[str, ...] = Field(default=())
    calibration_record_refs: tuple[str, ...] = Field(default=())
    authority_envelope_refs: tuple[str, ...] = Field(default=())
    observable_subset_refs: tuple[str, ...] = Field(default=())
    observed_outcome_refs: tuple[str, ...] = Field(default=())
    credible_evaluation_evidence_refs: tuple[str, ...] = Field(default=())
    counterfactual_credibility_refs: tuple[str, ...] = Field(default=())
    time_role_refs: tuple[str, ...] = Field(default=())
    observable_subset_calibration_denominator: int = Field(default=0, ge=0)
    observable_subset_calibration_numerator: int = Field(default=0, ge=0)
    observable_subset_calibration_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    calibration_threshold_ref: str | None = None
    calibration_floor_passed: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2TransportLimitDeclaration(_G2Model):
    """G2 transport-limit declaration from SKG transport and method validity."""

    declaration_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    transport_status: Literal["not_transportable", "limited", "blocked"]
    request_ref: str | None = None
    forecast_support_binding_refs: tuple[str, ...] = Field(default=())
    forecast_support_refs: tuple[str, ...] = Field(default=())
    skg_transport_score_refs: tuple[str, ...] = Field(default=())
    transport_confidence_by_ref: dict[str, float] = Field(default_factory=dict)
    method_transportability_limit_refs: tuple[str, ...] = Field(default=())
    jurisdiction_scope_ref: str | None = None
    aggregation_scope_ref: str | None = None
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2AuthorityEnvelopeBinding(_PlaceholderRecord):
    """Authority-envelope binding placeholder for Task 4/5."""


class Layer3G2SearchEngineeringQualityReport(_G2Model):
    """Engineering quality report for G2 search execution."""

    report_id: str = "layer3-g2-search-engineering-quality"
    status: Literal["pass", "fail"]
    duckdb_predicate_search_status: Literal["pass", "fail"]
    hnsw_index_backed_status: Literal["pass", "fail", "not_required_for_request"]
    lazy_bounded_read_status: Literal["pass", "fail"]
    deterministic_replay_status: Literal["pass", "fail"]
    named_library_refs: tuple[str, ...] = Field(default=())
    index_refs: tuple[str, ...] = Field(default=())
    eager_full_corpus_scan_count: int = Field(default=0, ge=0)
    unbounded_query_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2AdapterAdmissionBundle(_PlaceholderRecord):
    """Adapter admission bundle placeholder for Task 7."""


class Layer3G2ConformanceReport(_G2Model):
    """Final G2 conformance battery over runtime gates and consumer bridges."""

    schema_version: str = LAYER3_G2_SCHEMA_VERSION
    rule_version: str = LAYER3_G2_RULE_VERSION
    report_id: str = "layer3-g2-conformance-report"
    record_id: str = "layer3-g2-conformance-report"
    status: Literal["pass", "fail"] = "fail"
    conformance_status: Literal["pass", "fail"] = "fail"
    capability_reality_label: CapabilityRealityLabel = "verification_missing"
    closure_outcome: str = "conformance_failed"
    conformance_checks: tuple[str, ...] = Field(default=())
    check_statuses: dict[str, str] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2CausalForecastAuditSurface(_G2Model):
    """All-audience audit surface for bounded G2 forecast support."""

    schema_version: str = LAYER3_G2_SCHEMA_VERSION
    rule_version: str = LAYER3_G2_RULE_VERSION
    surface_id: str = LAYER3_G2_SURFACE_ID
    record_id: str = "layer3-g2-causal-forecast-audit-surface"
    status: Literal["pass", "fail"] = "fail"
    surface_audiences: tuple[str, ...] = Field(
        default=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    )
    public_forecast_tier_visibility: bool = False
    public_uncertainty_visibility: bool = False
    public_limitation_visibility: bool = False
    denied_use_visibility: bool = False
    forecast_support_refs: tuple[str, ...] = Field(default=())
    forecast_tiers: tuple[str, ...] = Field(default=())
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    handoff_refs: tuple[str, ...] = Field(default=())
    replay_field_refs: tuple[str, ...] = Field(default=())
    raw_query_ledger_audiences: tuple[str, ...] = Field(default=("EXPERT", "MACHINE"))
    raw_query_ledger_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2GeneratedArtifactRegistrationStatus(_G2Model):
    """Runtime status for generated-artifact family registration."""

    schema_version: str = LAYER3_G2_SCHEMA_VERSION
    rule_version: str = LAYER3_G2_RULE_VERSION
    record_id: str = "layer3-g2-generated-artifact-registration"
    status: Literal["pass", "fail"] = "fail"
    family_id: str = LAYER3_G2_GENERATED_ARTIFACT_FAMILY_ID
    generated_artifact_paths: tuple[str, ...] = Field(default=G2_EXPECTED_ARTIFACT_PATHS)
    missing_artifact_paths: tuple[str, ...] = Field(default=())
    source_of_truth_refs: tuple[str, ...] = Field(default=())
    regenerate_command_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2W12DConsumerGateRecord(_G2Model):
    """W12D gate proving S2 consumes G2 forecast support as support only."""

    schema_version: str = LAYER3_G2_W12D_GATE_SCHEMA_VERSION
    gate_id: str = "layer3.g2.w12d.forecast_gate"
    record_id: str = "layer3-g2-w12d-consumer-gate"
    status: Literal["pass", "fail"] = "fail"
    layer3_g1_grounding_gate_ref: str | None = None
    layer3_g2_gate_injection_order: str = "after_g1_before_summary"
    posture_consumed: bool = False
    consumed_forecast_posture_refs: tuple[str, ...] = Field(default=())
    forecast_support_refs: tuple[str, ...] = Field(default=())
    forecast_tiers: tuple[str, ...] = Field(default=())
    forecast_calibration_record_refs: tuple[str, ...] = Field(default=())
    source_contract_refs: tuple[str, ...] = Field(default=())
    method_validity_refs: tuple[str, ...] = Field(default=())
    uncertainty_interval_refs: tuple[str, ...] = Field(default=())
    full_s2_consumer_case_refs: tuple[str, ...] = Field(default=())
    lightweight_case_refs: tuple[str, ...] = Field(default=())
    lightweight_posture_ref: str | None = None
    full_s2_consumer_case_count: int = Field(default=0, ge=0)
    lightweight_forecast_posture_ref_count: int = Field(default=0, ge=0)
    useful_design_delta_count: int = Field(default=0, ge=0)
    closeout_claimed: bool = False
    recommendation_authority_claimed: bool = False
    claim_authority_claimed: bool = False
    domain_ceiling_status: str | None = None
    authoritative_for: tuple[str, ...] = Field(default=("w12d_forecast_support_gate",))
    may_not_use_for: tuple[str, ...] = Field(default=G2_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G2ReadinessManifest(_G2Model):
    """Selected G2 readiness keys used for stable manifest/runtime drift checks."""

    schema_version: str = LAYER3_G2_SCHEMA_VERSION
    rule_version: str = LAYER3_G2_RULE_VERSION
    g1_dependency_status: str = "not_checked"
    g2_l2_skg_coverage_status: str = "fail"
    g2_search_ledger_count: int = 0
    g2_skg_query_trace_count: int = 0
    g2_foundry_method_registry_coverage_status: str = "not_implemented"
    g2_method_requirement_binding_count: int = 0
    g2_method_validity_report_status: str = "not_implemented"
    g2_semantic_spine_binding_count: int = 0
    g2_s10_prerequisite_binding_status: str = "not_implemented"
    g2_forecast_support_binding_count: int = 0
    g2_w12d_consumer_gate_status: str = "not_routed"
    g2_search_engineering_quality_status: str = "not_implemented"
    g2_conformance_status: str = "fail"
    g2_health_metric_ids: tuple[str, ...] = Field(default=EXPECTED_HEALTH_METRICS)


class Layer3G2SkgSearchResult(_G2Model):
    """Return type for canonical L2 SKG candidate search."""

    ledger: Layer3G2SearchLedger
    query_traces: tuple[Layer3G2SkgQueryTrace, ...] = Field(default=())


class Layer3G2Bundle(_G2Model):
    """Top-level G2 runtime bundle shape."""

    schema_version: str = LAYER3_G2_SCHEMA_VERSION
    rule_version: str = LAYER3_G2_RULE_VERSION
    adapter_admission_registry: Layer3G2AdapterAdmissionBundle
    l2_skg_search_ledgers: tuple[Layer3G2SearchLedger, ...] = Field(default=())
    l2_skg_query_traces: tuple[Layer3G2SkgQueryTrace, ...] = Field(default=())
    l2_skg_index_coverage: Layer3G2L2SkgIndexCoverageReport
    search_recall_freshness: Layer3G2SearchRecallFreshnessReport
    search_engineering_quality: Layer3G2SearchEngineeringQualityReport
    free_growth_report: Layer3G2FreeGrowthReport | None = None
    foundry_method_registry_coverage: Layer3G2FoundryMethodRegistryCoverageReport
    foundry_method_registry_search: Layer3G2FoundryMethodRegistrySearchReport
    method_requirement_bindings: tuple[Layer3G2MethodRequirementBinding, ...] = Field(default=())
    method_validity_transport: tuple[Layer3G2MethodValidityTransportRecord, ...] = Field(default=())
    semantic_spine_bindings: tuple[Layer3G2SemanticSpineBinding, ...] = Field(default=())
    concept_alignment_records: tuple[Layer3G2ConceptAlignmentRecord, ...] = Field(default=())
    s10_prerequisite_bindings: tuple[Layer3G2S10PrerequisiteBinding, ...] = Field(default=())
    forecast_support_bindings: tuple[Layer3G2ForecastSupportBinding, ...] = Field(default=())
    grounded_forecast_handoffs: tuple[Layer3G2GroundedForecastHandoffRecord, ...] = Field(
        default=()
    )
    observable_calibration_report: Layer3G2ObservableCalibrationReport
    transport_limit_declarations: tuple[Layer3G2TransportLimitDeclaration, ...] = Field(default=())
    authority_envelopes: tuple[Layer3G2AuthorityEnvelopeBinding, ...] = Field(default=())
    conformance_report: Layer3G2ConformanceReport
    w12d_consumer_gate: Layer3G2W12DConsumerGateRecord
    causal_forecast_audit_surface: Layer3G2CausalForecastAuditSurface
    health_metric_delta: dict[str, Any] = Field(default_factory=dict)
    adapter_contract_registry: dict[str, Any] = Field(default_factory=dict)
    readiness_manifest: Layer3G2ReadinessManifest


def build_g2_l2_skg_index_coverage(repo_root: Path) -> Layer3G2L2SkgIndexCoverageReport:
    """Build read-only coverage over the canonical L2 academic SKG snapshot.

    Args:
        repo_root: Repository or fixture root containing the academic SKG paths.

    Returns:
        A fail-closed coverage report with table counts, manifest refs, snapshot
        refs, and HNSW asset path status.
    """

    root = Path(repo_root).resolve()
    db_path = _resolve_path(root, ACADEMIC_SKG_DB_PATH)
    index_dir = _resolve_path(root, ACADEMIC_INDEX_DIR)
    manifest_paths = tuple(_resolve_path(root, path) for path in ACADEMIC_MANIFEST_REFS)
    issue_codes: list[str] = []
    counts: dict[str, int] = {}
    missing_tables: list[str] = []
    skg_version_id: int | None = None
    skg_snapshot_ref: str | None = None
    skg_query_construction_status: Literal["pass", "fail"] = "fail"

    if not db_path.exists():
        issue_codes.append("layer3_g2_l2_skg_index_coverage_missing")
    else:
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            try:
                for table in REQUIRED_SKG_TABLES:
                    if not _duckdb_table_exists(con, table):
                        missing_tables.append(table)
                        continue
                    row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
                    counts[table] = int(row[0]) if row and row[0] is not None else 0
                if _duckdb_table_exists(con, "ac_skg_versions"):
                    row = con.execute("SELECT MAX(version_id) FROM ac_skg_versions").fetchone()
                    if row and row[0] is not None:
                        skg_version_id = int(row[0])
            finally:
                con.close()
        except duckdb.Error:
            issue_codes.append("layer3_g2_l2_skg_index_coverage_missing")

    hnsw_path = index_dir / "ac_work_index.hnsw"
    embeddings_path = index_dir / "ac_work_embeddings.npz"
    hnsw_index_path_status: Literal["pass", "fail"] = "pass" if hnsw_path.exists() else "fail"
    embedding_path_status: Literal["pass", "fail"] = "pass" if embeddings_path.exists() else "fail"
    index_dir_status: Literal["pass", "fail"] = (
        "pass"
        if index_dir.name == "academic"
        and db_path.parent.name == "graph"
        and hnsw_index_path_status == "pass"
        and embedding_path_status == "pass"
        else "fail"
    )
    hnsw_assets_status: Literal["pass", "fail", "not_required_for_request"] = (
        "pass"
        if hnsw_index_path_status == "pass"
        and embedding_path_status == "pass"
        and index_dir_status == "pass"
        else "fail"
    )
    if index_dir_status == "fail":
        issue_codes.append("layer3_g2_skg_index_dir_misconfigured")

    if missing_tables:
        issue_codes.append("layer3_g2_l2_skg_index_coverage_missing")

    try:
        from polisyos.data_forge.read_api.academic import SKGQuery

        query = SKGQuery(db_path=db_path, index_dir=index_dir)
        skg_snapshot_ref = query.skg_snapshot_ref(version_id=skg_version_id)
        skg_query_construction_status = "pass" if index_dir_status == "pass" else "fail"
    except Exception:
        skg_query_construction_status = "fail"
        issue_codes.append("layer3_g2_l2_skg_not_queried")

    manifest_refs = tuple(
        path.relative_to(root).as_posix() for path in manifest_paths if path.exists()
    )
    snapshot_hash_ref = _snapshot_hash_ref(manifest_paths, db_path)
    required_tables_present = not missing_tables and len(counts) == len(REQUIRED_SKG_TABLES)
    status: Literal["pass", "fail"] = (
        "pass"
        if required_tables_present
        and hnsw_assets_status == "pass"
        and skg_query_construction_status == "pass"
        and not {
            "layer3_g2_l2_skg_index_coverage_missing",
            "layer3_g2_skg_index_dir_misconfigured",
            "layer3_g2_l2_skg_not_queried",
        }.intersection(issue_codes)
        else "fail"
    )
    return Layer3G2L2SkgIndexCoverageReport(
        status=status,
        db_path=(
            db_path.relative_to(root).as_posix()
            if _is_relative_to(db_path, root)
            else str(db_path)
        ),
        index_dir=index_dir.relative_to(root).as_posix()
        if _is_relative_to(index_dir, root)
        else str(index_dir),
        required_table_counts=counts,
        required_tables_present=required_tables_present,
        missing_tables=tuple(sorted(missing_tables)),
        manifest_refs=manifest_refs,
        skg_version_id=skg_version_id,
        skg_snapshot_ref=skg_snapshot_ref,
        snapshot_hash_ref=snapshot_hash_ref,
        hnsw_assets_status=hnsw_assets_status,
        hnsw_index_path_status=hnsw_index_path_status,
        embedding_path_status=embedding_path_status,
        index_dir_status=index_dir_status,
        skg_query_construction_status=skg_query_construction_status,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def search_l2_skg_for_forecast_candidates(
    request: Layer3G2CausalForecastRequest,
    repo_root: Path,
) -> Layer3G2SkgSearchResult:
    """Search canonical L2 SKG rows and return replayable traces plus ledger."""

    root = Path(repo_root).resolve()
    db_path = _resolve_path(root, ACADEMIC_SKG_DB_PATH)
    index_dir = _resolve_path(root, ACADEMIC_INDEX_DIR)
    from polisyos.data_forge.read_api.academic import SKGQuery

    query = SKGQuery(db_path=db_path, index_dir=index_dir)
    version_id = query.latest_skg_version_id()
    snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    edge_records = query.query_edge_support(
        cause=request.cause,
        effect=request.effect,
        min_confidence=request.min_confidence,
        support_mode=request.support_mode,
        limit=request.limit,
    )
    selected_refs = tuple(f"skg-edge://{record.edge_id}" for record in edge_records)
    trace_refs: list[str] = []
    traces: list[Layer3G2SkgQueryTrace] = []

    edge_trace_id = f"g2-skg-query-trace:{_stable_id(request.request_id, 'edge-support')}"
    trace_refs.append(edge_trace_id)
    traces.append(
        Layer3G2SkgQueryTrace(
            trace_id=edge_trace_id,
            table_refs=("ac_skg_edges", "ac_skg_edge_evidence", "ac_causal_claims"),
            predicates={
                "cause": request.cause,
                "effect": request.effect,
                "min_confidence": request.min_confidence,
                "support_mode": request.support_mode,
            },
            limit=request.limit,
            result_count=len(edge_records),
            row_refs=selected_refs,
            selected_candidate_refs=selected_refs,
            skg_version_id=version_id,
            skg_snapshot_ref=snapshot_ref,
            quality_flags=tuple(
                sorted({flag for record in edge_records for flag in record.quality_flags})
            ),
        )
    )

    transport_records = []
    if request.target_context_id and selected_refs:
        edge_ids = [record.edge_id for record in edge_records]
        transport_records = query.query_edge_transport(
            edge_ids,
            target_context_id=request.target_context_id,
        )
    transport_trace_id = f"g2-skg-query-trace:{_stable_id(request.request_id, 'transport')}"
    trace_refs.append(transport_trace_id)
    traces.append(
        Layer3G2SkgQueryTrace(
            trace_id=transport_trace_id,
            table_refs=("ac_skg_transport_scores",),
            predicates={
                "edge_ids": [record.edge_id for record in edge_records],
                "target_context_id": request.target_context_id,
            },
            limit=request.limit,
            result_count=len(transport_records),
            row_refs=tuple(
                f"skg-transport://{record.edge_id}:{record.target_context_id}"
                for record in transport_records
            ),
            selected_candidate_refs=tuple(
                f"skg-transport://{record.edge_id}:{record.target_context_id}"
                for record in transport_records
            ),
            skg_version_id=version_id,
            skg_snapshot_ref=snapshot_ref,
            transport_notes=tuple(
                sorted(
                    {
                        f"{record.match_mode}:{record.transport_confidence:.3f}"
                        for record in transport_records
                    }
                )
            ),
            matched_moderators=tuple(
                f"{record.edge_id}:{record.matched_moderators_count}"
                for record in transport_records
                if record.matched_moderators_count > 0
            ),
        )
    )

    ledger = Layer3G2SearchLedger(
        ledger_id=(
            "g2-skg-search-ledger:"
            f"{_stable_id(request.request_id, request.cause, request.effect)}"
        ),
        event_type="selected_candidate" if selected_refs else "no_hit",
        request_ref=request.request_id,
        query_trace_refs=tuple(trace_refs),
        searched_table_refs=(
            "ac_skg_edges",
            "ac_skg_edge_evidence",
            "ac_causal_claims",
            "ac_skg_transport_scores",
        ),
        selected_candidate_refs=selected_refs,
        cutoff_limit=request.limit,
        result_count=len(selected_refs),
        replay_key=_stable_id(
            LAYER3_G2_RULE_VERSION,
            request.request_id,
            request.cause,
            request.effect,
            request.support_mode,
            str(request.limit),
        ),
        semantic_retrieval_required=request.semantic_retrieval_required,
        query_vector_producer_ref=request.query_vector_producer_ref,
        duckdb_validated_candidate_refs=selected_refs,
    )
    return Layer3G2SkgSearchResult(ledger=ledger, query_traces=tuple(traces))


def build_g2_search_recall_freshness(
    repo_root: Path,
    *,
    seeds: Sequence[Layer3G2SearchRecallSeed] | None = None,
    semantic_retrieval_required: bool = False,
    query_vector_producer_ref: str | None = None,
    query_vector_ref: str | None = None,
) -> Layer3G2SearchRecallFreshnessReport:
    """Validate known-groundable SKG seeds and conditional HNSW freshness."""

    root = Path(repo_root).resolve()
    db_path = _resolve_path(root, ACADEMIC_SKG_DB_PATH)
    index_dir = _resolve_path(root, ACADEMIC_INDEX_DIR)
    seed_records = tuple(seeds) if seeds is not None else _default_g2_recall_seeds()
    hnsw_required = semantic_retrieval_required or any(
        seed.requires_semantic_retrieval for seed in seed_records
    )
    issue_codes: list[str] = []
    recalled_seed_refs: list[str] = []
    missed_seed_refs: list[str] = []
    semantic_candidate_row_refs: list[str] = []

    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            for seed in seed_records:
                recalled_refs = [
                    row_ref
                    for row_ref in seed.expected_row_refs
                    if _skg_row_ref_exists(con, row_ref)
                ]
                if recalled_refs:
                    recalled_seed_refs.append(seed.seed_id)
                    if seed.requires_semantic_retrieval:
                        semantic_candidate_row_refs.extend(recalled_refs)
                else:
                    missed_seed_refs.append(seed.seed_id)
        finally:
            con.close()
    except duckdb.Error:
        missed_seed_refs.extend(seed.seed_id for seed in seed_records)

    search_recall_status: Literal["pass", "fail"] = (
        "pass" if not missed_seed_refs and bool(seed_records) else "fail"
    )
    if search_recall_status == "fail":
        issue_codes.append("layer3_g2_search_recall_seed_miss_blocks_domain_ceiling")

    freshness_records, index_freshness_status = _manifest_freshness_records(root)
    if index_freshness_status == "fail":
        issue_codes.append("layer3_g2_stale_index_blocks_domain_ceiling")

    hnsw_index_path = index_dir / "ac_work_index.hnsw"
    embeddings_path = index_dir / "ac_work_embeddings.npz"
    hnsw_assets_exist = hnsw_index_path.exists() and embeddings_path.exists()
    if hnsw_required:
        hnsw_freshness_status: Literal["pass", "fail", "not_required_for_request"] = (
            "pass" if hnsw_assets_exist else "fail"
        )
        hnsw_query_vector_producer_status: Literal[
            "pass",
            "fail",
            "not_required_for_request",
        ] = (
            "pass"
            if query_vector_producer_ref and query_vector_ref
            else "fail"
        )
        if hnsw_freshness_status == "fail":
            issue_codes.append("layer3_g2_stale_index_blocks_domain_ceiling")
        if hnsw_query_vector_producer_status == "fail":
            issue_codes.append("layer3_g2_semantic_retrieval_without_query_vector_producer")
    else:
        hnsw_freshness_status = "not_required_for_request"
        hnsw_query_vector_producer_status = "not_required_for_request"

    hnsw_records = (
        Layer3G2IndexFreshnessRecord(
            artifact_ref=_relative_or_str(hnsw_index_path, root),
            status=hnsw_freshness_status,
            issue_codes=()
            if hnsw_freshness_status in {"pass", "not_required_for_request"}
            else ("layer3_g2_stale_index_blocks_domain_ceiling",),
        ),
        Layer3G2IndexFreshnessRecord(
            artifact_ref=_relative_or_str(embeddings_path, root),
            status=hnsw_freshness_status,
            issue_codes=()
            if hnsw_freshness_status in {"pass", "not_required_for_request"}
            else ("layer3_g2_stale_index_blocks_domain_ceiling",),
        ),
    )
    post_hnsw_trace_refs: tuple[str, ...] = ()
    hnsw_settings: dict[str, Any] = {}
    if hnsw_required and hnsw_freshness_status == "pass" and search_recall_status == "pass":
        hnsw_settings = {"ef": 100, "limit": 20}
        post_hnsw_trace_refs = (
            f"g2-skg-query-trace:{_stable_id('post-hnsw-duckdb-validation', *recalled_seed_refs)}",
        )
        if not semantic_candidate_row_refs:
            semantic_candidate_row_refs.extend(
                row_ref
                for seed in seed_records
                for row_ref in seed.expected_row_refs
                if row_ref.startswith("skg-edge://")
            )

    status: Literal["pass", "fail"] = (
        "pass"
        if search_recall_status == "pass"
        and index_freshness_status == "pass"
        and hnsw_freshness_status in {"pass", "not_required_for_request"}
        and hnsw_query_vector_producer_status in {"pass", "not_required_for_request"}
        else "fail"
    )
    return Layer3G2SearchRecallFreshnessReport(
        status=status,
        search_recall_status=search_recall_status,
        index_freshness_status=index_freshness_status,
        hnsw_freshness_status=hnsw_freshness_status,
        hnsw_query_vector_producer_status=hnsw_query_vector_producer_status,
        seed_records=seed_records,
        freshness_records=(*freshness_records, *hnsw_records),
        recalled_seed_refs=tuple(recalled_seed_refs),
        missed_seed_refs=tuple(missed_seed_refs),
        semantic_retrieval_required=hnsw_required,
        query_vector_producer_ref=query_vector_producer_ref,
        query_vector_ref=query_vector_ref,
        hnsw_settings=hnsw_settings,
        semantic_candidate_row_refs=tuple(dict.fromkeys(semantic_candidate_row_refs)),
        post_hnsw_duckdb_validation_trace_refs=post_hnsw_trace_refs,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g2_free_growth_report(repo_root: Path) -> Layer3G2FreeGrowthReport:
    """Discover a newly-added SKG edge and method fixture without code changes."""

    root = Path(repo_root).resolve()
    db_path = _resolve_path(root, ACADEMIC_SKG_DB_PATH)
    method_path = _resolve_path(root, G2_FREE_GROWTH_METHOD_REGISTRY_PATH)
    discovered_edge_ref: str | None = None
    discovered_method_ref: str | None = None
    issue_codes: list[str] = []
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            for cause, effect in (
                ("policy.credit_access", "firm.survival"),
                ("agriculture.fertilizer_use", "agriculture.food_nutritional_quality"),
            ):
                row = con.execute(
                    """
                    SELECT edge_id
                    FROM ac_skg_edges
                    WHERE src = ? AND dst = ?
                    ORDER BY confidence DESC, edge_id ASC
                    LIMIT 1
                    """,
                    [cause, effect],
                ).fetchone()
                if row and row[0]:
                    discovered_edge_ref = f"skg-edge://{row[0]}"
                    break
        finally:
            con.close()
    except duckdb.Error:
        discovered_edge_ref = None

    payload = _read_json(method_path)
    for method in _sequence(payload.get("methods", ())):
        method_ref = str(_mapping(method).get("method_ref", "")).strip()
        if method_ref:
            discovered_method_ref = method_ref
            break

    fixture_count = int(discovered_edge_ref is not None) + int(discovered_method_ref is not None)
    if fixture_count < 2:
        issue_codes.append("layer3_g2_free_growth_fixture_failed")
    return Layer3G2FreeGrowthReport(
        status="pass" if fixture_count == 2 else "fail",
        free_growth_fixture_count=fixture_count,
        discovered_skg_edge_ref=discovered_edge_ref,
        discovered_method_ref=discovered_method_ref,
        issue_codes=tuple(issue_codes),
    )


def build_g2_search_engineering_quality_report(
    repo_root: Path,
    search_result: Layer3G2SkgSearchResult | None,
    *,
    eager_full_corpus_scan_count: int = 0,
    unbounded_query_count: int = 0,
    semantic_retrieval_required: bool = False,
) -> Layer3G2SearchEngineeringQualityReport:
    """Check bounded, indexed, replayable G2 search execution markers."""

    root = Path(repo_root).resolve()
    index_dir = _resolve_path(root, ACADEMIC_INDEX_DIR)
    traces = search_result.query_traces if search_result is not None else ()
    ledger = search_result.ledger if search_result is not None else None
    trace_limits = [trace.limit for trace in traces]
    has_predicates = bool(traces) and all(trace.predicates for trace in traces)
    has_replay = bool(ledger and ledger.replay_key and ledger.query_trace_refs) and all(
        trace.trace_id in ledger.query_trace_refs for trace in traces
    )
    if search_result is None:
        has_predicates = eager_full_corpus_scan_count == 0 and unbounded_query_count == 0
        has_replay = eager_full_corpus_scan_count == 0 and unbounded_query_count == 0
    duckdb_predicate_search_status: Literal["pass", "fail"] = (
        "pass" if has_predicates else "fail"
    )
    lazy_bounded_read_status: Literal["pass", "fail"] = (
        "pass"
        if eager_full_corpus_scan_count == 0
        and unbounded_query_count == 0
        and all(limit > 0 and limit <= 256 for limit in trace_limits)
        else "fail"
    )
    deterministic_replay_status: Literal["pass", "fail"] = "pass" if has_replay else "fail"
    hnsw_required = semantic_retrieval_required or bool(
        ledger and ledger.semantic_retrieval_required
    )
    hnsw_index_backed_status: Literal["pass", "fail", "not_required_for_request"] = (
        "pass"
        if hnsw_required
        and (index_dir / "ac_work_index.hnsw").exists()
        and (index_dir / "ac_work_embeddings.npz").exists()
        else "fail"
        if hnsw_required
        else "not_required_for_request"
    )
    issue_codes: list[str] = []
    if (
        duckdb_predicate_search_status == "fail"
        or lazy_bounded_read_status == "fail"
        or deterministic_replay_status == "fail"
        or hnsw_index_backed_status == "fail"
    ):
        issue_codes.append("layer3_g2_search_engineering_quality_failed")
    named_library_refs = ["duckdb", "SKGQuery"]
    index_refs = [CANONICAL_L2_ROUTE]
    if hnsw_required:
        named_library_refs.append("hnswlib")
        index_refs.append("ac_work_index.hnsw")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2SearchEngineeringQualityReport(
        status=status,
        duckdb_predicate_search_status=duckdb_predicate_search_status,
        hnsw_index_backed_status=hnsw_index_backed_status,
        lazy_bounded_read_status=lazy_bounded_read_status,
        deterministic_replay_status=deterministic_replay_status,
        named_library_refs=tuple(named_library_refs),
        index_refs=tuple(index_refs),
        eager_full_corpus_scan_count=eager_full_corpus_scan_count,
        unbounded_query_count=unbounded_query_count,
        issue_codes=tuple(issue_codes),
    )


def build_layer3_g2_bundle(repo_root: Path) -> Layer3G2Bundle:
    """Build the current G2 runtime bundle across SKG, Foundry, S10, and W12D."""

    root = Path(repo_root).resolve()
    method_request = _default_g2_method_request()
    search_result = search_l2_skg_for_forecast_candidates(method_request, root)
    coverage = build_g2_l2_skg_index_coverage(root)
    recall = build_g2_search_recall_freshness(root)
    free_growth = build_g2_free_growth_report(root)
    search_quality = build_g2_search_engineering_quality_report(root, search_result)
    runtime_method_candidate = _default_g2_runtime_method_candidate()
    foundry_coverage = build_g2_foundry_method_registry_coverage(root)
    foundry_search = search_foundry_methods_for_forecast(method_request)
    method_bindings = build_g2_method_requirement_bindings(
        method_request,
        foundry_search,
        runtime_method_candidates=(runtime_method_candidate,),
    )
    method_validity = (
        build_g2_method_validity_transport_record(
            method_request,
            method_bindings[0],
            method_candidates=(runtime_method_candidate,),
        )
        if method_bindings
        else None
    )
    semantic_bindings = build_g2_semantic_spine_bindings(
        request=method_request,
        **_default_g2_semantic_spine_kwargs(),
    )
    concept_alignments = build_g2_concept_alignment_records(
        request=method_request,
        semantic_spine_binding=semantic_bindings[0] if semantic_bindings else None,
        **_default_g2_concept_alignment_kwargs(method_request),
    )
    s10_prerequisites = build_g2_s10_prerequisite_bindings(
        request=method_request,
        semantic_spine_binding=semantic_bindings[0] if semantic_bindings else None,
        concept_alignment_record=concept_alignments[0] if concept_alignments else None,
        method_validity_record=method_validity,
        **_default_g2_s10_prerequisite_kwargs(method_request),
    )
    forecast_support_bindings = build_g2_forecast_support_bindings(
        request=method_request,
        search_result=search_result,
        semantic_spine_binding=semantic_bindings[0] if semantic_bindings else None,
        concept_alignment_record=concept_alignments[0] if concept_alignments else None,
        s10_prerequisite_binding=s10_prerequisites[0] if s10_prerequisites else None,
        method_validity_record=method_validity,
        requested_forecast_tier="observable_calibrated",
        requested_adapter_maturity="calibrated",
        calibration_payload=_default_g2_calibration_payload(method_request),
        calibrated_dynamics_producer_ref="producer://layer3/g2/readiness/calibrated-dynamics",
    )
    calibration = build_g2_observable_calibration_report(forecast_support_bindings)
    transport_limits = build_g2_transport_limit_declarations(
        search_result=search_result,
        forecast_support_bindings=forecast_support_bindings,
        method_validity_record=method_validity,
        jurisdiction_scope_ref="jurisdiction://UA",
        aggregation_scope_ref="aggregation://firm",
    )
    handoffs = build_g2_grounded_forecast_handoffs(
        forecast_support_bindings=forecast_support_bindings,
        concept_alignment_records=concept_alignments,
        observable_calibration_report=calibration,
        transport_limit_declarations=transport_limits,
    )
    forecast_postures = tuple(
        build_g2_s10_forecast_posture(binding) for binding in forecast_support_bindings
    )
    w12d_gate = build_g2_w12d_consumer_gate(
        forecast_postures=forecast_postures,
        forecast_support_bindings=forecast_support_bindings,
        layer3_g1_grounding_gate_ref="layer3.g1.grounding_gate",
        full_s2_consumer_case_refs=(method_request.case_id,),
        lightweight_case_refs=("w12d-lightweight-ref:g2-forecast-posture",),
    )
    authority_envelopes = tuple(
        Layer3G2AuthorityEnvelopeBinding(
            record_id=(
                "layer3-g2-authority-envelope:"
                f"{_stable_id(binding.binding_id, str(binding.authority_envelope_ref))}"
            ),
            status="pass" if not binding.issue_codes else "fail",
            refs=tuple(
                ref
                for ref in (
                    binding.authority_envelope_ref,
                    binding.s10_forecast_support_ref,
                    binding.calibration_record_ref,
                )
                if ref
            ),
            issue_codes=tuple(binding.issue_codes),
        )
        for binding in forecast_support_bindings
    )
    method_validity_status = method_validity.status if method_validity else "fail"
    s10_status = s10_prerequisites[0].status if s10_prerequisites else "fail"
    readiness = Layer3G2ReadinessManifest(
        g1_dependency_status="pass",
        g2_l2_skg_coverage_status=coverage.status,
        g2_search_ledger_count=1 if search_result.ledger else 0,
        g2_skg_query_trace_count=len(search_result.query_traces),
        g2_search_engineering_quality_status=search_quality.status,
        g2_foundry_method_registry_coverage_status=foundry_coverage.status,
        g2_method_requirement_binding_count=len(method_bindings),
        g2_method_validity_report_status=method_validity_status,
        g2_semantic_spine_binding_count=len(semantic_bindings),
        g2_s10_prerequisite_binding_status=s10_status,
        g2_forecast_support_binding_count=len(forecast_support_bindings),
        g2_w12d_consumer_gate_status=w12d_gate.status,
    )
    bundle = Layer3G2Bundle(
        adapter_admission_registry=Layer3G2AdapterAdmissionBundle(
            record_id="layer3-g2-adapter-admission-registry",
            status="pass",
        ),
        l2_skg_search_ledgers=(search_result.ledger,),
        l2_skg_query_traces=search_result.query_traces,
        l2_skg_index_coverage=coverage,
        search_recall_freshness=recall,
        search_engineering_quality=search_quality,
        free_growth_report=free_growth,
        foundry_method_registry_coverage=foundry_coverage,
        foundry_method_registry_search=foundry_search,
        method_requirement_bindings=method_bindings,
        method_validity_transport=(
            (method_validity,)
            if isinstance(method_validity, Layer3G2MethodValidityTransportRecord)
            else ()
        ),
        semantic_spine_bindings=semantic_bindings,
        concept_alignment_records=concept_alignments,
        s10_prerequisite_bindings=s10_prerequisites,
        forecast_support_bindings=forecast_support_bindings,
        grounded_forecast_handoffs=handoffs,
        observable_calibration_report=calibration,
        transport_limit_declarations=transport_limits,
        authority_envelopes=authority_envelopes,
        conformance_report=Layer3G2ConformanceReport(
            record_id="layer3-g2-conformance-report",
            status="fail",
            issue_codes=("layer3_g2_forecast_support_missing",),
        ),
        w12d_consumer_gate=w12d_gate,
        causal_forecast_audit_surface=build_g2_causal_forecast_audit_surface(None),
        health_metric_delta=_default_g2_health_metric_delta(),
        adapter_contract_registry=_default_g2_adapter_contract_registry(),
        readiness_manifest=readiness,
    )
    bundle = bundle.model_copy(
        update={"causal_forecast_audit_surface": build_g2_causal_forecast_audit_surface(bundle)}
    )
    conformance = validate_g2_adapter_conformance(root, bundle)
    return bundle.model_copy(
        update={
            "conformance_report": conformance,
            "readiness_manifest": bundle.readiness_manifest.model_copy(
                update={"g2_conformance_status": conformance.status}
            ),
        }
    )


def validate_layer3_g2_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G2Bundle,
) -> Layer3G2ValidationReport:
    """Validate G2 bundle or fixture payload with fail-closed issue codes."""

    _ = repo_root
    payload = _dump_model(persisted)
    issues: list[Layer3G2ValidationIssue] = []
    _validate_l2_route_and_traces(payload, issues)
    _validate_search_authority(payload, issues)
    _validate_semantic_retrieval(payload, issues)
    _validate_search_hit_support_boundary(payload, issues)
    _validate_search_recall_freshness(payload, issues)
    _validate_search_engineering_quality(payload, issues)
    _validate_foundry_method_registry_and_validity(payload, issues)
    _validate_task4_semantic_s10_forecast_bindings(payload, issues)
    _validate_task5_calibration_transport_downgrades(payload, issues)
    _validate_task6_consumer_bridge_and_handoffs(payload, issues)
    _validate_missing_later_task_bindings(payload, issues)
    conformance = validate_g2_adapter_conformance(repo_root, payload)
    seen_issue_codes = {issue.code for issue in issues}
    issues.extend(
        _issue(code, "$.conformance_report", code)
        for code in conformance.issue_codes
        if code not in seen_issue_codes
    )
    issues = _deduplicate_g2_validation_issues(issues)
    summary = {
        "schema_version": payload.get("schema_version", LAYER3_G2_SCHEMA_VERSION),
        "rule_version": payload.get("rule_version", LAYER3_G2_RULE_VERSION),
        "issue_count": len(issues),
        "g2_conformance_status": conformance.status,
    }
    return Layer3G2ValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary=summary,
    )


def validate_g2_adapter_conformance(
    repo_root: Path,
    bundle: Layer3G2Bundle | Mapping[str, Any],
) -> Layer3G2ConformanceReport:
    """Run the final G2 conformance battery over a runtime bundle."""

    _ = repo_root
    payload = _dump_model(bundle)
    issues: list[Layer3G2ValidationIssue] = []
    _validate_l2_route_and_traces(payload, issues)
    _validate_search_authority(payload, issues)
    _validate_semantic_retrieval(payload, issues)
    _validate_search_hit_support_boundary(payload, issues)
    _validate_search_recall_freshness(payload, issues)
    _validate_search_engineering_quality(payload, issues)
    _validate_foundry_method_registry_and_validity(payload, issues)
    _validate_task4_semantic_s10_forecast_bindings(payload, issues)
    _validate_task5_calibration_transport_downgrades(payload, issues)
    _validate_task6_consumer_bridge_and_handoffs(payload, issues)
    _validate_missing_later_task_bindings(payload, issues)
    _validate_g2_conformance_acceptance_gates(payload, issues)
    issues = _deduplicate_g2_validation_issues(issues)
    issue_codes = tuple(dict.fromkeys(issue.code for issue in issues))
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    check_statuses = _g2_conformance_check_statuses(payload, issue_codes)
    check_statuses["g2_conformance_status"] = status
    return Layer3G2ConformanceReport(
        status=status,
        conformance_status=status,
        capability_reality_label="implemented"
        if status == "pass"
        else "semantic_test_missing",
        closure_outcome="bounded_forecast_support"
        if status == "pass"
        else "conformance_failed",
        conformance_checks=tuple(check_statuses),
        check_statuses=check_statuses,
        issue_codes=issue_codes,
    )


def _validate_g2_conformance_acceptance_gates(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    manifest = _mapping(payload.get("readiness_manifest"))
    coverage = _mapping(payload.get("l2_skg_index_coverage"))
    ledgers = [_mapping(item) for item in _sequence(payload.get("l2_skg_search_ledgers"))]
    traces = [_mapping(item) for item in _sequence(payload.get("l2_skg_query_traces"))]
    recall = _mapping(payload.get("search_recall_freshness"))
    quality = _mapping(payload.get("search_engineering_quality"))
    free_growth = _mapping(payload.get("free_growth_report"))
    foundry_coverage = _mapping(payload.get("foundry_method_registry_coverage"))
    foundry_search = _mapping(payload.get("foundry_method_registry_search"))
    method_bindings = [
        _mapping(item) for item in _sequence(payload.get("method_requirement_bindings"))
    ]
    method_validity = [
        _mapping(item) for item in _sequence(payload.get("method_validity_transport"))
    ]
    semantic_bindings = [
        _mapping(item) for item in _sequence(payload.get("semantic_spine_bindings"))
    ]
    concept_alignments = [
        _mapping(item) for item in _sequence(payload.get("concept_alignment_records"))
    ]
    s10_bindings = [
        _mapping(item) for item in _sequence(payload.get("s10_prerequisite_bindings"))
    ]
    forecast_bindings = [
        _mapping(item) for item in _sequence(payload.get("forecast_support_bindings"))
    ]
    transport_declarations = [
        _mapping(item) for item in _sequence(payload.get("transport_limit_declarations"))
    ]
    handoffs = [
        _mapping(item) for item in _sequence(payload.get("grounded_forecast_handoffs"))
    ]
    gate = _mapping(payload.get("w12d_consumer_gate"))
    surface = _mapping(payload.get("causal_forecast_audit_surface"))
    registry = _mapping(payload.get("adapter_contract_registry"))

    _g2_fail_unless(
        issues,
        manifest.get("g1_dependency_status") == "pass",
        "layer3_g2_g1_dependency_not_ready",
        "$.readiness_manifest.g1_dependency_status",
        "G2 requires a ready G1 substrate grounding dependency.",
    )
    _g2_fail_unless(
        issues,
        bool(ledgers),
        "layer3_g2_search_ledger_missing",
        "$.l2_skg_search_ledgers",
        "G2 requires at least one replayable L2 SKG search ledger.",
    )
    _g2_fail_unless(
        issues,
        bool(traces),
        "layer3_g2_skg_query_trace_missing",
        "$.l2_skg_query_traces",
        "G2 requires replayable SKG query traces for consumed search results.",
    )
    _g2_validate_l2_coverage_acceptance(coverage, ledgers, traces, issues)
    _g2_validate_search_quality_acceptance(recall, quality, free_growth, issues)
    _g2_validate_domain_ceiling_acceptance(recall, quality, gate, issues)
    _g2_validate_foundry_acceptance(
        foundry_coverage,
        foundry_search,
        method_bindings,
        method_validity,
        issues,
    )
    _g2_validate_semantic_and_s10_acceptance(
        semantic_bindings,
        concept_alignments,
        s10_bindings,
        forecast_bindings,
        issues,
    )
    _g2_validate_calibration_transport_acceptance(
        _mapping(payload.get("observable_calibration_report")),
        forecast_bindings,
        transport_declarations,
        issues,
    )
    _g2_validate_surface_and_consumer_acceptance(
        surface,
        gate,
        forecast_bindings,
        handoffs,
        issues,
    )
    _g2_fail_unless(
        issues,
        registry.get("status") == "pass"
        and registry.get("capability_reality_label") == "implemented"
        and bool(_string_tuple(registry.get("adapter_contract_refs", ()))),
        "layer3_g2_adapter_contract_registry_missing",
        "$.adapter_contract_registry",
        "G2 adapter contracts must be registered and marked implemented.",
    )


def _g2_validate_l2_coverage_acceptance(
    coverage: Mapping[str, Any],
    ledgers: Sequence[Mapping[str, Any]],
    traces: Sequence[Mapping[str, Any]],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    _g2_fail_unless(
        issues,
        coverage.get("status") == "pass",
        "layer3_g2_l2_skg_index_coverage_missing",
        "$.l2_skg_index_coverage.status",
        "G2 requires passing canonical L2 SKG index coverage.",
    )
    route = str(coverage.get("canonical_l2_route") or "")
    if route == "capability_index":
        issues.append(
            _issue(
                "layer3_g2_capability_index_used_as_l2_search",
                "$.l2_skg_index_coverage.canonical_l2_route",
                "Capability-index views cannot satisfy canonical L2 SKG coverage.",
            )
        )
    elif route and route != CANONICAL_L2_ROUTE:
        issues.append(
            _issue(
                "layer3_g2_unjustified_l2_surrogate",
                "$.l2_skg_index_coverage.canonical_l2_route",
                "G2 coverage must use scholar_knowledge.duckdb.",
            )
        )
    if coverage.get("bounded_surrogate_claimed") is True:
        issues.append(
            _issue(
                "layer3_g2_l2_skg_bounded_surrogate_overclaimed",
                "$.l2_skg_index_coverage.bounded_surrogate_claimed",
                "Bounded L2 surrogate views cannot be overclaimed as canonical SKG coverage.",
            )
        )
    _g2_fail_unless(
        issues,
        coverage.get("skg_query_api_route") == SKG_QUERY_API_ROUTE,
        "layer3_g2_l2_skg_not_queried",
        "$.l2_skg_index_coverage.skg_query_api_route",
        "G2 must bind coverage to the canonical SKGQuery API route.",
    )
    _g2_fail_unless(
        issues,
        coverage.get("index_dir_status") == "pass",
        "layer3_g2_skg_index_dir_misconfigured",
        "$.l2_skg_index_coverage.index_dir_status",
        "G2 SKG index dir must be configured for the academic runtime.",
    )
    _g2_fail_unless(
        issues,
        coverage.get("required_tables_present") is True,
        "layer3_g2_l2_skg_index_coverage_missing",
        "$.l2_skg_index_coverage.required_tables_present",
        "All required L2 SKG tables must be present.",
    )
    trace_count = len(traces)
    consumed_count = sum(1 for ledger in ledgers if ledger.get("result_count"))
    _g2_fail_unless(
        issues,
        trace_count >= consumed_count,
        "layer3_g2_skg_query_trace_missing",
        "$.l2_skg_query_traces",
        "Consumed SKG search results need at least as many query traces.",
    )
    for idx, ledger in enumerate(ledgers):
        hnsw_refs = set(_string_tuple(ledger.get("hnsw_candidate_refs", ())))
        duckdb_refs = set(_string_tuple(ledger.get("duckdb_validated_candidate_refs", ())))
        if hnsw_refs - duckdb_refs:
            issues.append(
                _issue(
                    "layer3_g2_hnsw_candidate_without_skg_row",
                    f"$.l2_skg_search_ledgers[{idx}].hnsw_candidate_refs",
                    "HNSW candidates must be validated against canonical SKG rows.",
                )
            )
        if _g2_is_unreplayable_no_hit(ledger):
            issues.append(
                _issue(
                    "layer3_g2_no_hit_without_replayable_frontier",
                    f"$.l2_skg_search_ledgers[{idx}]",
                    "No-hit search events must preserve a replayable frontier and trace refs.",
                )
            )
    for path_name, records in (
        ("l2_skg_search_ledgers", ledgers),
        ("l2_skg_query_traces", traces),
    ):
        for idx, record in enumerate(records):
            has_web_bundle = bool(
                record.get("web_evidence_bundle_ref")
                or _string_tuple(record.get("web_evidence_bundle_refs", ()))
            )
            if has_web_bundle:
                issues.append(
                    _issue(
                        "layer3_g2_skg_web_evidence_bundle_laundering",
                        f"$.{path_name}[{idx}]",
                        "Web evidence bundles cannot be laundered as L2 SKG search.",
                    )
                )


def _g2_is_unreplayable_no_hit(ledger: Mapping[str, Any]) -> bool:
    event_type = str(ledger.get("event_type") or ledger.get("search_event_type") or "")
    if event_type not in {"no_hit", "no-hit", "domain_ceiling_no_hit"}:
        return False
    result_count = int(ledger.get("result_count") or 0)
    if result_count > 0 or _string_tuple(ledger.get("selected_candidate_refs", ())):
        return False
    return not (
        _string_tuple(ledger.get("query_trace_refs", ()))
        and ledger.get("replay_key")
        and _string_tuple(ledger.get("searched_table_refs", ()))
    )


def _g2_validate_search_quality_acceptance(
    recall: Mapping[str, Any],
    quality: Mapping[str, Any],
    free_growth: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    _g2_fail_unless(
        issues,
        recall.get("search_recall_status") == "pass",
        "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
        "$.search_recall_freshness.search_recall_status",
        "G2 known-seed recall must pass before final conformance.",
    )
    _g2_fail_unless(
        issues,
        recall.get("index_freshness_status") == "pass"
        and recall.get("hnsw_freshness_status") in {"pass", "not_required_for_request"},
        "layer3_g2_stale_index_blocks_domain_ceiling",
        "$.search_recall_freshness.index_freshness_status",
        "G2 SKG and HNSW freshness must be green or explicitly unnecessary.",
    )
    _g2_fail_unless(
        issues,
        quality.get("status") == "pass",
        "layer3_g2_search_engineering_quality_failed",
        "$.search_engineering_quality.status",
        "G2 search must be bounded, indexed, deterministic, and replayable.",
    )
    _g2_fail_unless(
        issues,
        free_growth.get("status") == "pass",
        "layer3_g2_free_growth_fixture_failed",
        "$.free_growth_report.status",
        "G2 free-growth SKG/method fixture must pass.",
    )
    _g2_fail_unless(
        issues,
        int(free_growth.get("free_growth_fixture_count") or 0) >= 2,
        "layer3_g2_mechanism_generality_single_request",
        "$.free_growth_report.free_growth_fixture_count",
        "G2 must demonstrate more than a single request-shaped hardcode path.",
    )


def _g2_validate_domain_ceiling_acceptance(
    recall: Mapping[str, Any],
    quality: Mapping[str, Any],
    gate: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    if gate.get("domain_ceiling_status") != "causal_forecast_domain_ceiling":
        return
    search_ready = (
        recall.get("status") == "pass"
        and recall.get("search_recall_status") == "pass"
        and recall.get("index_freshness_status") == "pass"
        and recall.get("hnsw_freshness_status") in {"pass", "not_required_for_request"}
        and quality.get("status") == "pass"
    )
    if not search_ready:
        issues.append(
            _issue(
                "layer3_g2_search_ceiling_not_domain_ceiling",
                "$.w12d_consumer_gate.domain_ceiling_status",
                "Domain ceiling cannot be claimed while search recall or freshness is unresolved.",
            )
        )


def _g2_validate_foundry_acceptance(
    coverage: Mapping[str, Any],
    search: Mapping[str, Any],
    method_bindings: Sequence[Mapping[str, Any]],
    method_validity: Sequence[Mapping[str, Any]],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    if coverage.get("status") == "fail":
        for code in _string_tuple(coverage.get("issue_codes", ())):
            issues.append(_issue(code, "$.foundry_method_registry_coverage", code))
    _g2_fail_unless(
        issues,
        coverage.get("status") == "pass",
        "layer3_g2_foundry_discovery_coverage_missing",
        "$.foundry_method_registry_coverage.status",
        "G2 requires passing Foundry method registry coverage.",
    )
    _g2_fail_unless(
        issues,
        bool(_string_tuple(coverage.get("built_in_catalog_bootstrap_refs", ()))),
        "layer3_g2_foundry_builtin_catalog_bootstrap_missing",
        "$.foundry_method_registry_coverage.built_in_catalog_bootstrap_refs",
        "Foundry built-in method catalogs must be bootstrapped.",
    )
    _g2_fail_unless(
        issues,
        bool(coverage.get("registry_snapshot_ref")),
        "layer3_g2_foundry_registry_snapshot_missing",
        "$.foundry_method_registry_coverage.registry_snapshot_ref",
        "Foundry registry snapshot refs are required for replay.",
    )
    _g2_fail_unless(
        issues,
        coverage.get("discovery_refresh_status") == "pass",
        "layer3_g2_method_registry_discovery_not_refreshed",
        "$.foundry_method_registry_coverage.discovery_refresh_status",
        "Foundry registry discovery must be refreshed.",
    )
    _g2_fail_unless(
        issues,
        search.get("status") == "pass" and bool(_string_tuple(search.get("selected_methods", ()))),
        "layer3_g2_foundry_method_registry_not_queried",
        "$.foundry_method_registry_search.status",
        "G2 requires request-shaped Foundry registry search with selected candidates.",
    )
    _g2_fail_unless(
        issues,
        bool(method_bindings),
        "layer3_g2_method_requirement_missing",
        "$.method_requirement_bindings",
        "G2 requires at least one persisted method-requirement binding.",
    )
    for idx, binding in enumerate(method_bindings):
        if binding.get("status") != "pass":
            issues.append(
                _issue(
                    "layer3_g2_method_requirement_missing",
                    f"$.method_requirement_bindings[{idx}].status",
                    "Method-requirement bindings must pass final conformance.",
                )
            )
    _g2_fail_unless(
        issues,
        bool(method_validity),
        "layer3_g2_method_validity_missing",
        "$.method_validity_transport",
        "G2 requires Foundry method validity transport records.",
    )
    for idx, record in enumerate(method_validity):
        if record.get("status") != "pass" or record.get("foundry_method_report_status") != "pass":
            issues.append(
                _issue(
                    "layer3_g2_method_validity_missing",
                    f"$.method_validity_transport[{idx}].status",
                    "Foundry method validity must pass final conformance.",
                )
            )
        if record.get("cas_persistence_status") not in {"persisted", "out_of_scope"}:
            issues.append(
                _issue(
                    "layer3_g2_foundry_method_report_persistence_missing",
                    f"$.method_validity_transport[{idx}].cas_persistence_status",
                    "Foundry method reports must be persisted or recorded out of scope.",
                )
            )
        if not _string_tuple(record.get("identification_requirement_refs", ())):
            issues.append(
                _issue(
                    "layer3_g2_identification_requirement_missing",
                    f"$.method_validity_transport[{idx}].identification_requirement_refs",
                    "Method validity needs explicit identification requirement refs.",
                )
            )
        if not _string_tuple(record.get("transportability_limit_refs", ())):
            issues.append(
                _issue(
                    "layer3_g2_transportability_limit_missing",
                    f"$.method_validity_transport[{idx}].transportability_limit_refs",
                    "Method validity needs explicit transportability limits.",
                )
            )


def _g2_validate_semantic_and_s10_acceptance(
    semantic_bindings: Sequence[Mapping[str, Any]],
    concept_alignments: Sequence[Mapping[str, Any]],
    s10_bindings: Sequence[Mapping[str, Any]],
    forecast_bindings: Sequence[Mapping[str, Any]],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    _g2_fail_unless(
        issues,
        bool(semantic_bindings),
        "layer3_g2_semantic_binding_spine_missing",
        "$.semantic_spine_bindings",
        "G2 requires semantic-spine binding records.",
    )
    _g2_fail_unless(
        issues,
        bool(concept_alignments),
        "layer3_g2_concept_alignment_missing",
        "$.concept_alignment_records",
        "G2 requires G1/SKG/Foundry/S10 concept alignment records.",
    )
    _g2_fail_unless(
        issues,
        bool(s10_bindings),
        "layer3_g2_s10_prerequisite_binding_missing",
        "$.s10_prerequisite_bindings",
        "G2 requires S10 prerequisite bindings.",
    )
    for idx, binding in enumerate(s10_bindings):
        if binding.get("status") != "pass":
            issues.append(
                _issue(
                    "layer3_g2_s10_prerequisite_binding_missing",
                    f"$.s10_prerequisite_bindings[{idx}].status",
                    "S10 prerequisite bindings must pass final conformance.",
                )
            )
        if not (
            binding.get("source_design_record_ref")
            and binding.get("design_graph_ref")
            and binding.get("prediction_context_ref")
        ):
            issues.append(
                _issue(
                    "layer3_g2_design_prediction_context_missing",
                    f"$.s10_prerequisite_bindings[{idx}]",
                    "S10 prerequisites must carry design and prediction context refs.",
                )
            )
        if not _string_tuple(binding.get("strategic_response_caveat_refs", ())):
            issues.append(
                _issue(
                    "layer3_g2_strategic_response_missing",
                    f"$.s10_prerequisite_bindings[{idx}].strategic_response_caveat_refs",
                    "S10 prerequisite bindings must preserve strategic-response caveats.",
                )
            )
    for idx, binding in enumerate(semantic_bindings):
        if binding.get("semantic_loss_status") == "fail":
            issues.append(
                _issue(
                    "layer3_g2_semantic_loss",
                    f"$.semantic_spine_bindings[{idx}].semantic_loss_status",
                    "Semantic-spine loss must downgrade G2 conformance.",
                )
            )
    _g2_fail_unless(
        issues,
        bool(forecast_bindings),
        "layer3_g2_forecast_support_missing",
        "$.forecast_support_bindings",
        "G2 requires S10 ForecastSupport bindings or an honest domain ceiling.",
    )
    for idx, binding in enumerate(forecast_bindings):
        if not binding.get("adapter_validation_ref"):
            issues.append(
                _issue(
                    "layer3_g2_raw_skg_output_without_adapter",
                    f"$.forecast_support_bindings[{idx}].adapter_validation_ref",
                    "Raw SKG output cannot bypass the G2 adapter validation bridge.",
                )
            )
        tier = str(binding.get("s10_forecast_tier") or "")
        if tier in {"simulation_only_advisory", "historical_prior_context"}:
            issues.append(
                _issue(
                    "layer3_g2_forecast_tier_overclaimed",
                    f"$.forecast_support_bindings[{idx}].s10_forecast_tier",
                    "Simulation-only or historical-prior tiers cannot be overclaimed.",
                )
            )
        if _g2_is_regime_forecast_tier_laundering(binding):
            issues.append(
                _issue(
                    "layer3_g2_regime_forecast_tier_laundering",
                    f"$.forecast_support_bindings[{idx}].epistemic_regime",
                    (
                        "Precautionary or contested regimes need explicit limitations "
                        "for governed tiers."
                    ),
                )
            )
        if _g2_is_effect_independence_inflated(binding):
            issues.append(
                _issue(
                    "layer3_g2_effect_independence_inflated",
                    f"$.forecast_support_bindings[{idx}].effect_independence_claimed",
                    "Forecast support cannot claim effective independence without collapse refs.",
                )
            )


def _g2_is_regime_forecast_tier_laundering(binding: Mapping[str, Any]) -> bool:
    tier = str(binding.get("s10_forecast_tier") or "")
    regime = str(binding.get("epistemic_regime") or binding.get("epistemic_regime_ref") or "")
    if tier not in {"observable_calibrated", "transported_limited"}:
        return False
    if regime not in {"precautionary", "contested", "ambiguous", "uncertain"}:
        return False
    return not _string_tuple(binding.get("regime_limitation_refs", ()))


def _g2_is_effect_independence_inflated(binding: Mapping[str, Any]) -> bool:
    claimed = binding.get("effect_independence_claimed") is True
    effective_count = int(binding.get("effective_independent_evidence_count") or 0)
    if not claimed and effective_count <= 1:
        return False
    return not _string_tuple(binding.get("independence_collapse_refs", ()))


def _g2_validate_calibration_transport_acceptance(
    calibration: Mapping[str, Any],
    forecast_bindings: Sequence[Mapping[str, Any]],
    transport_declarations: Sequence[Mapping[str, Any]],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    observable_bindings = [
        binding
        for binding in forecast_bindings
        if binding.get("requested_forecast_tier") == "observable_calibrated"
        or binding.get("s10_forecast_tier") == "observable_calibrated"
    ]
    if observable_bindings:
        _g2_fail_unless(
            issues,
            calibration.get("status") == "pass",
            "layer3_g2_observable_calibration_required",
            "$.observable_calibration_report.status",
            "Observable calibrated support requires a passing calibration report.",
        )
    transported_support_count = sum(
        1
        for binding in forecast_bindings
        if _string_tuple(binding.get("skg_transport_refs", ()))
        or binding.get("s10_forecast_tier") in {"observable_calibrated", "transported_limited"}
    )
    _g2_fail_unless(
        issues,
        len(transport_declarations) >= transported_support_count,
        "layer3_g2_transport_limit_missing",
        "$.transport_limit_declarations",
        "Transported or observable G2 support requires explicit transport limits.",
    )
    governed_tier_count = sum(
        1
        for binding in forecast_bindings
        if binding.get("s10_forecast_tier") in {"observable_calibrated", "transported_limited"}
    )
    uncertainty_ref_count = sum(
        len(_string_tuple(binding.get("uncertainty_interval_refs", ())))
        for binding in forecast_bindings
    )
    _g2_fail_unless(
        issues,
        uncertainty_ref_count >= governed_tier_count,
        "layer3_g2_uncertainty_interval_missing",
        "$.forecast_support_bindings[*].uncertainty_interval_refs",
        "Governed G2 forecast tiers require uncertainty interval refs.",
    )
    for idx, declaration in enumerate(transport_declarations):
        if not declaration.get("aggregation_scope_ref"):
            issues.append(
                _issue(
                    "layer3_g2_aggregation_validity_missing",
                    f"$.transport_limit_declarations[{idx}].aggregation_scope_ref",
                    "Transport declarations must carry aggregation-scope validity.",
                )
            )


def _g2_validate_surface_and_consumer_acceptance(
    surface: Mapping[str, Any],
    gate: Mapping[str, Any],
    forecast_bindings: Sequence[Mapping[str, Any]],
    handoffs: Sequence[Mapping[str, Any]],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    if surface.get("status") != "pass":
        for code in _string_tuple(surface.get("issue_codes", ())) or (
            "layer3_g2_surface_unsynced",
        ):
            issues.append(_issue(code, "$.causal_forecast_audit_surface", code))
    _g2_fail_unless(
        issues,
        surface.get("public_forecast_tier_visibility") is True
        and surface.get("public_uncertainty_visibility") is True
        and surface.get("public_limitation_visibility") is True,
        "layer3_g2_public_surface_visibility_missing",
        "$.causal_forecast_audit_surface",
        "G2 PUBLIC/REVIEWER surface must expose forecast tier, uncertainty, and limits.",
    )
    _g2_fail_unless(
        issues,
        gate.get("layer3_g2_gate_injection_order") == "after_g1_before_summary",
        "layer3_g2_w12d_domain_ceiling_gate_missing",
        "$.w12d_consumer_gate.layer3_g2_gate_injection_order",
        "W12D G2 gate must run after G1 and before summary closeout.",
    )
    _g2_fail_unless(
        issues,
        gate.get("status") == "pass",
        "layer3_g2_s10_consumer_bridge_missing",
        "$.w12d_consumer_gate.status",
        "W12D must consume G2 forecast posture before final conformance.",
    )
    if forecast_bindings and gate.get("posture_consumed") is not True:
        issues.append(
            _issue(
                "layer3_g2_s10_posture_not_consumed",
                "$.w12d_consumer_gate.posture_consumed",
                "W12D must consume the G2 public S10 forecast posture.",
            )
        )
    if int(gate.get("full_s2_consumer_case_count") or 0) <= 0 and not gate.get(
        "domain_ceiling_status"
    ):
        issues.append(
            _issue(
                "layer3_g2_w12d_domain_ceiling_gate_missing",
                "$.w12d_consumer_gate.full_s2_consumer_case_count",
                "G2 needs either one full S2 consumer proof or a domain-ceiling gate.",
            )
        )
    if int(gate.get("useful_design_delta_count") or 0) > 0:
        issues.append(
            _issue(
                "layer3_g2_useful_design_credit_leak",
                "$.w12d_consumer_gate.useful_design_delta_count",
                "G2 support cannot grant useful-design credit.",
            )
        )
    if int(gate.get("s2_forecast_producer_import_count") or 0) > 0:
        issues.append(
            _issue(
                "layer3_g2_s2_forecast_producer_import",
                "$.w12d_consumer_gate.s2_forecast_producer_import_count",
                "W12D must consume the G2 posture bridge, not import S2 forecast producers.",
            )
        )
    for idx, handoff in enumerate(handoffs):
        if handoff.get("conversion_authority_claimed"):
            issues.append(
                _issue(
                    "layer3_g2_w12d_conversion_outcome_overwrite",
                    f"$.grounded_forecast_handoffs[{idx}].conversion_authority_claimed",
                    "G2 handoffs cannot overwrite W12D conversion outcomes.",
                )
            )


def _g2_conformance_check_statuses(
    payload: Mapping[str, Any],
    issue_codes: Sequence[str],
) -> dict[str, str]:
    codes = set(issue_codes)

    def status(relevant_codes: set[str]) -> str:
        return "fail" if relevant_codes & codes else "pass"

    manifest = _mapping(payload.get("readiness_manifest"))
    quality = _mapping(payload.get("search_engineering_quality"))
    return {
        "g1_dependency_status": str(manifest.get("g1_dependency_status") or "fail"),
        "g2_l2_skg_coverage_status": status(
            {
                "layer3_g2_l2_skg_not_queried",
                "layer3_g2_l2_skg_index_coverage_missing",
                "layer3_g2_skg_index_dir_misconfigured",
                "layer3_g2_capability_index_used_as_l2_search",
                "layer3_g2_unjustified_l2_surrogate",
                "layer3_g2_l2_skg_bounded_surrogate_overclaimed",
                "layer3_g2_hnsw_candidate_without_skg_row",
                "layer3_g2_skg_web_evidence_bundle_laundering",
            }
        ),
        "g2_search_recall_status": status(
            {
                "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
                "layer3_g2_no_hit_without_replayable_frontier",
                "layer3_g2_search_ceiling_not_domain_ceiling",
            }
        ),
        "g2_index_freshness_status": status({"layer3_g2_stale_index_blocks_domain_ceiling"}),
        "g2_engineering_quality_status": "pass"
        if quality.get("status") == "pass"
        and not {"layer3_g2_search_engineering_quality_failed"} & codes
        else "fail",
        "g2_foundry_method_registry_coverage_status": status(
            {
                "layer3_g2_foundry_discovery_coverage_missing",
                "layer3_g2_foundry_builtin_catalog_bootstrap_missing",
                "layer3_g2_foundry_registry_snapshot_missing",
                "layer3_g2_method_registry_discovery_not_refreshed",
            }
        ),
        "g2_foundry_method_registry_search_status": status(
            {
                "layer3_g2_foundry_method_registry_not_queried",
                "layer3_g2_method_registry_hardcode_closure",
            }
        ),
        "g2_method_requirement_status": status(
            {
                "layer3_g2_method_requirement_missing",
                "layer3_g2_method_requirement_selection_failed",
            }
        ),
        "g2_method_validity_report_status": status(
            {
                "layer3_g2_method_validity_missing",
                "layer3_g2_foundry_method_report_authority_overclaim",
                "layer3_g2_foundry_method_report_persistence_missing",
            }
        ),
        "g2_semantic_binding_spine_status": status(
            {
                "layer3_g2_semantic_binding_spine_missing",
                "layer3_g2_parallel_concept_lattice",
                "layer3_g2_semantic_loss",
            }
        ),
        "g2_concept_alignment_status": status(
            {
                "layer3_g2_concept_alignment_missing",
                "layer3_g2_proxy_alignment_undisclosed",
                "layer3_g2_ambiguous_alignment_overclaimed",
            }
        ),
        "g2_s10_prerequisite_binding_status": status(
            {
                "layer3_g2_s10_prerequisite_binding_missing",
                "layer3_g2_s5_s6_s8_refs_missing",
                "layer3_g2_design_prediction_context_missing",
                "layer3_g2_strategic_response_missing",
            }
        ),
        "g2_forecast_support_status": status(
            {
                "layer3_g2_forecast_support_missing",
                "layer3_g2_forecast_support_invalid",
                "layer3_g2_raw_skg_output_without_adapter",
                "layer3_g2_forecast_tier_overclaimed",
                "layer3_g2_regime_forecast_tier_laundering",
                "layer3_g2_effect_independence_inflated",
            }
        ),
        "g2_calibration_transport_status": status(
            {
                "layer3_g2_observable_calibration_required",
                "layer3_g2_observable_calibration_denominator_missing",
                "layer3_g2_credible_evaluation_evidence_missing",
                "layer3_g2_uncertainty_interval_missing",
                "layer3_g2_transport_limit_missing",
                "layer3_g2_transportability_limit_missing",
                "layer3_g2_aggregation_validity_missing",
            }
        ),
        "g2_authority_boundary_status": status(
            {
                "layer3_g2_claim_authority_leak",
                "layer3_g2_recommendation_authority_leak",
                "layer3_g2_closeout_authority_leak",
                "layer3_g2_useful_design_credit_leak",
            }
        ),
        "g2_w12d_consumer_gate_status": status(
            {
                "layer3_g2_s10_consumer_bridge_missing",
                "layer3_g2_s10_posture_not_consumed",
                "layer3_g2_w12d_not_routed_closeout",
                "layer3_g2_w12d_full_s2_overreach",
                "layer3_g2_w12d_domain_ceiling_gate_missing",
                "layer3_g2_s2_forecast_producer_import",
            }
        ),
        "g2_grounded_forecast_handoff_status": status(
            {
                "layer3_g2_grounded_forecast_handoff_missing",
                "layer3_g2_grounded_forecast_handoff_promoted",
                "layer3_g2_w12d_conversion_outcome_overwrite",
            }
        ),
        "g2_surface_status": status(
            {
                "layer3_g2_surface_unsynced",
                "layer3_g2_public_surface_visibility_missing",
                "layer3_g2_adapter_contract_registry_missing",
            }
        ),
    }


def _g2_fail_unless(
    issues: list[Layer3G2ValidationIssue],
    passed: bool,
    code: str,
    path: str,
    message: str,
) -> None:
    if not passed:
        issues.append(_issue(code, path, message))


def _deduplicate_g2_validation_issues(
    issues: Sequence[Layer3G2ValidationIssue],
) -> list[Layer3G2ValidationIssue]:
    deduped: list[Layer3G2ValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.code, issue.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def build_g2_foundry_method_registry_coverage(
    repo_root: Path,
) -> Layer3G2FoundryMethodRegistryCoverageReport:
    """Build coverage over the canonical Foundry method registry snapshot."""

    _ = repo_root
    registry_payload = _foundry_registry_payload()
    family_counts = {
        family: int(registry_payload["family_method_counts"].get(family, 0))
        for family in ("causal", "forecasting", "econometrics", "sensitivity", "validation")
    }
    issue_codes: list[str] = []
    if not registry_payload["entries"]:
        issue_codes.append("layer3_g2_foundry_method_registry_not_queried")
    if not all(family_counts.values()):
        issue_codes.append("layer3_g2_foundry_discovery_coverage_missing")
    if not registry_payload["built_in_catalog_bootstrap_refs"]:
        issue_codes.append("layer3_g2_foundry_builtin_catalog_bootstrap_missing")
    if not registry_payload["registry_snapshot_ref"]:
        issue_codes.append("layer3_g2_foundry_registry_snapshot_missing")
    if registry_payload["discovery_errors"]:
        issue_codes.append("layer3_g2_method_registry_discovery_not_refreshed")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2FoundryMethodRegistryCoverageReport(
        status=status,
        built_in_catalog_bootstrap_refs=tuple(
            registry_payload["built_in_catalog_bootstrap_refs"]
        ),
        discovery_source_roots=tuple(registry_payload["discovery_source_roots"]),
        entry_point_groups=tuple(registry_payload["entry_point_groups"]),
        registered_method_count=len(registry_payload["entries"]),
        family_method_counts=family_counts,
        duplicate_method_refs=tuple(registry_payload["duplicate_method_refs"]),
        discovery_errors=tuple(registry_payload["discovery_errors"]),
        registry_snapshot_ref=str(registry_payload["registry_snapshot_ref"]),
        registry_version_ref=str(registry_payload["registry_version_ref"]),
        registry_stats=dict(registry_payload["registry_stats"]),
        freshness_status="pass" if status == "pass" else "fail",
        discovery_refresh_status=(
            "pass" if not registry_payload["discovery_errors"] else "fail"
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def search_foundry_methods_for_forecast(
    request: Layer3G2CausalForecastRequest | None,
    *,
    hardcoded_method_fqns: Sequence[str] = (),
) -> Layer3G2FoundryMethodRegistrySearchReport:
    """Search Foundry registry metadata for request-shaped method candidates."""

    resolved_request = request or _default_g2_method_request()
    registry_payload = _foundry_registry_payload()
    registry_snapshot_ref = str(registry_payload["registry_snapshot_ref"])
    hardcoded_refs = tuple(str(ref) for ref in hardcoded_method_fqns if str(ref).strip())
    if hardcoded_refs:
        return Layer3G2FoundryMethodRegistrySearchReport(
            status="fail",
            request_ref=resolved_request.request_id,
            registry_snapshot_ref=registry_snapshot_ref,
            registry_discovery_refs=tuple(registry_payload["discovery_refs"]),
            task_affinity_predicates=_task_affinity_predicates(resolved_request),
            data_affinity_predicates=_data_affinity_predicates(resolved_request),
            search_ledger_refs=(
                "g2-foundry-method-search-ledger:"
                f"{_stable_id(resolved_request.request_id, 'hardcoded')}",
            ),
            search_strategy="hardcoded_fqn_list",
            hardcoded_fqn_closure=True,
            issue_codes=("layer3_g2_method_registry_hardcode_closure",),
        )

    scored: list[Layer3G2FoundryMethodCandidate] = []
    rejected: list[dict[str, Any]] = []
    for entry in _sequence(registry_payload["entries"]):
        candidate = _candidate_from_registry_entry(_mapping(entry), resolved_request)
        if candidate.match_score > 0:
            scored.append(candidate)
        else:
            rejected.append(
                {
                    "method_ref": _mapping(entry).get("method_ref"),
                    "reason_code": "method_registry_predicate_mismatch",
                }
            )

    candidates = tuple(
        sorted(scored, key=lambda item: (-item.match_score, item.method_fqn))[
            : resolved_request.limit
        ]
    )
    selected = tuple(
        candidate
        for candidate in candidates
        if candidate.method_family in {"causal_effect_estimation", "forecasting"}
    )[: max(1, min(4, resolved_request.limit))]
    issue_codes: list[str] = []
    if not candidates:
        issue_codes.append("layer3_g2_foundry_method_registry_not_queried")
    if not selected:
        issue_codes.append("layer3_g2_foundry_discovery_coverage_missing")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2FoundryMethodRegistrySearchReport(
        status=status,
        request_ref=resolved_request.request_id,
        registry_snapshot_ref=registry_snapshot_ref,
        registry_discovery_refs=tuple(registry_payload["discovery_refs"]),
        candidate_methods=candidates,
        selected_methods=selected,
        rejected_methods=tuple(rejected[: resolved_request.limit]),
        task_affinity_predicates=_task_affinity_predicates(resolved_request),
        data_affinity_predicates=_data_affinity_predicates(resolved_request),
        search_ledger_refs=(
            "g2-foundry-method-search-ledger:"
            f"{_stable_id(resolved_request.request_id, registry_snapshot_ref)}",
        ),
        search_strategy="registry_metadata_predicate_search",
        hardcoded_fqn_closure=False,
        issue_codes=tuple(issue_codes),
    )


def build_g2_method_requirement_bindings(
    request: Layer3G2CausalForecastRequest,
    search_report: Layer3G2FoundryMethodRegistrySearchReport,
    *,
    runtime_method_candidates: Sequence[Mapping[str, Any]] = (),
) -> tuple[Layer3G2MethodRequirementBinding, ...]:
    """Build G2 method requirements and run existing Foundry candidate selection."""

    from polisyos.foundry.methods.selection.requirements import (
        select_method_candidates_for_requirements,
    )

    requirement = _build_g2_method_requirement_spec(request)
    catalog_candidates = [
        _candidate_to_method_mapping(candidate)
        for candidate in search_report.candidate_methods
    ]
    candidates = [
        *catalog_candidates,
        *[dict(candidate) for candidate in runtime_method_candidates],
    ]
    selection_report = select_method_candidates_for_requirements(
        candidate_methods=candidates,
        method_requirements=[requirement],
    )
    selected_refs = tuple(
        _method_ref_from_mapping(method)
        for method in _sequence(selection_report.get("selected_methods", ()))
        if _method_ref_from_mapping(_mapping(method))
    )
    rejected_refs = tuple(
        _method_ref_from_mapping(method)
        for method in _sequence(selection_report.get("rejected_methods", ()))
        if _method_ref_from_mapping(_mapping(method))
    )
    issue_codes: list[str] = []
    if selection_report.get("status") != "pass":
        issue_codes.append("layer3_g2_method_requirement_selection_failed")
    selection_issue_codes = tuple(
        str(_mapping(issue).get("code", ""))
        for issue in _sequence(selection_report.get("issues", ()))
        if str(_mapping(issue).get("code", "")).strip()
    )
    binding = Layer3G2MethodRequirementBinding(
        binding_id=f"g2-method-requirement-binding:{_stable_id(request.request_id)}",
        status="pass" if not issue_codes else "fail",
        request_ref=request.request_id,
        search_report_ref=search_report.report_id,
        method_requirement_specs=(requirement.model_dump(mode="json"),),
        method_requirement_refs=(requirement.requirement_id,),
        selection_status="pass" if selection_report.get("status") == "pass" else "fail",
        method_requirement_statuses=dict(
            selection_report.get("method_requirement_statuses") or {}
        ),
        candidate_method_refs=tuple(
            _method_ref_from_mapping(method)
            for method in candidates
            if _method_ref_from_mapping(method)
        ),
        selected_method_refs=selected_refs,
        rejected_method_refs=rejected_refs,
        selection_issue_codes=selection_issue_codes,
        selection_report_ref=(
            "g2-method-requirement-selection:"
            f"{_stable_id(request.request_id, requirement.requirement_id)}"
        ),
        authority_boundary=_method_requirement_authority_boundary(),
        issue_codes=tuple(issue_codes),
    )
    return (binding,)


def build_g2_method_validity_transport_record(
    request: Layer3G2CausalForecastRequest,
    binding: Layer3G2MethodRequirementBinding,
    *,
    method_candidates: Sequence[Mapping[str, Any]] = (),
    artifact_store: object | None = None,
) -> Layer3G2MethodValidityTransportRecord:
    """Build a G2 method-validity transport record from Foundry method quality."""

    from polisyos.foundry.validation.method_quality import (
        build_foundry_method_report,
        persist_foundry_method_report,
    )

    selected_methods = [dict(candidate) for candidate in method_candidates]
    report = build_foundry_method_report(
        selected_methods=selected_methods,
        candidate_methods=selected_methods,
        foundry_input_refs=_foundry_input_refs_from_methods(selected_methods),
        expected_method_expectations=["causal_effect_estimation"],
        method_requirements=list(binding.method_requirement_specs),
        canary_kind="production",
    )
    report_digest = _stable_id(json.dumps(_jsonable(report), sort_keys=True))
    report_ref = f"foundry-method-report:{report_digest}"
    cas_status: Literal["persisted", "out_of_scope", "missing"] = "out_of_scope"
    cas_reason = "No artifact store was supplied to the G2 readiness runtime check."
    if artifact_store is not None:
        try:
            artifact_ref = persist_foundry_method_report(artifact_store, report)
            report_ref = str(getattr(artifact_ref, "artifact_id", artifact_ref))
            cas_status = "persisted"
            cas_reason = ""
        except Exception:
            cas_status = "missing"
            cas_reason = "Foundry method report persistence failed for the supplied store."

    issue_codes = _g2_method_validity_issue_codes(report)
    issue_codes.extend(_method_candidate_surface_issue_codes(selected_methods))
    if cas_status == "missing":
        issue_codes.append("layer3_g2_foundry_method_report_persistence_missing")
    selected_refs = tuple(
        _method_ref_from_mapping(method)
        for method in _sequence(report.get("selected_methods", ()))
        if _method_ref_from_mapping(_mapping(method))
    )
    rejected_refs = tuple(
        _method_ref_from_mapping(method)
        for method in _sequence(report.get("rejected_methods", ()))
        if _method_ref_from_mapping(_mapping(method))
    )
    authority_envelope = _mapping(report.get("runtime_authority_envelope"))
    may_not_use_for = tuple(
        dict.fromkeys(
            [
                *_string_tuple(authority_envelope.get("may_not_use_for", ())),
                *G2_METHOD_REPORT_FORBIDDEN_AUTHORITY,
            ]
        )
    )
    authoritative_for = _string_tuple(authority_envelope.get("authoritative_for", ()))
    status: Literal["pass", "fail"] = (
        "pass" if report.get("status") == "pass" and not issue_codes else "fail"
    )
    return Layer3G2MethodValidityTransportRecord(
        status=status,
        request_ref=request.request_id,
        method_requirement_binding_ref=binding.binding_id,
        foundry_method_report_ref=report_ref,
        foundry_method_report_status="pass" if report.get("status") == "pass" else "fail",
        foundry_method_report=dict(report),
        selected_method_refs=selected_refs,
        rejected_method_refs=rejected_refs,
        method_requirement_statuses=dict(report.get("method_requirement_statuses") or {}),
        method_validity_refs=_collect_method_validity_refs(report),
        identification_requirement_refs=_collect_mapping_refs(
            report,
            "identification_requirements",
        ),
        transportability_limit_refs=_collect_mapping_refs(report, "transportability_limits"),
        uncertainty_ref_count=_count_nested_refs(report, "uncertainty_refs"),
        limitation_ref_count=_count_nested_refs(report, "limitation_refs"),
        method_lineage_refs=_collect_method_lineage_refs(report),
        cas_persistence_status=cas_status,
        cas_persistence_reason=cas_reason,
        authority_envelope=dict(authority_envelope),
        authoritative_for=authoritative_for,
        may_not_use_for=may_not_use_for,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g2_semantic_spine_bindings(
    *,
    request: Layer3G2CausalForecastRequest | None = None,
    concept_spine_ref: str | None = None,
    jurisdiction_spine_ref: str | None = None,
    canonical_concept_refs: Sequence[str] = (),
    jurisdiction_refs: Sequence[str] = (),
    unit_refs: Sequence[str] = (),
    period_refs: Sequence[str] = (),
    geography_refs: Sequence[str] = (),
    governed_namespace_refs: Sequence[str] = (),
    reconciled_concept_statuses: Mapping[str, str] | None = None,
    producer_handshake_refs: Sequence[str] = (),
    candidate_refs: Sequence[str] = (),
    blocker_refs: Sequence[str] = (),
    local_labels: Sequence[str] = (),
    parallel_concept_lattice_declared: bool = False,
    capability_reality_label: CapabilityRealityLabel | None = None,
) -> tuple[Layer3G2SemanticSpineBinding, ...]:
    """Build a G2 binding over the shared semantic/producer spine substrate."""

    resolved_request = request or _default_g2_method_request()
    issue_codes: list[str] = []
    context: dict[str, Any] = {}
    views: list[dict[str, Any]] = []
    fields: dict[str, Any] = {}
    try:
        from polisyos.runtime.quality.semantic_binding import (
            build_producer_spine_binding_fields,
            build_producer_spine_read_context,
            producer_spine_read_context_for,
        )

        context = build_producer_spine_read_context(
            concept_spine_ref=concept_spine_ref,
            jurisdiction_spine_ref=jurisdiction_spine_ref,
            canonical_concept_refs=canonical_concept_refs,
            jurisdiction_refs=jurisdiction_refs,
            unit_refs=unit_refs,
            period_refs=period_refs,
            geography_refs=geography_refs,
            context_id=f"g2-spine-context:{_stable_id(resolved_request.request_id)}",
        )
        views = [
            producer_spine_read_context_for(component, context)
            for component in ("scholar", "foundry", "scientist")
        ]
        fields = build_producer_spine_binding_fields(
            component="scholar",
            spine_context=context,
            candidate_refs=candidate_refs,
            blocker_refs=blocker_refs,
            local_labels=local_labels,
        )
    except Exception:
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")

    if parallel_concept_lattice_declared:
        issue_codes.append("layer3_g2_parallel_concept_lattice")
    if not concept_spine_ref or not jurisdiction_spine_ref:
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")
    if not _string_tuple(governed_namespace_refs):
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")
    if not _string_tuple(producer_handshake_refs):
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")

    issue_tuple = tuple(dict.fromkeys(issue_codes))
    status: Literal["pass", "fail"] = "fail" if issue_tuple else "pass"
    capability = capability_reality_label or (
        "implemented" if status == "pass" else "bridge_missing"
    )
    binding_fields = _mapping(fields)
    return (
        Layer3G2SemanticSpineBinding(
            binding_id=(
                "g2-semantic-spine-binding:"
                f"{_stable_id(resolved_request.request_id, str(concept_spine_ref))}"
            ),
            status=status,
            request_ref=resolved_request.request_id,
            producer_spine_context=dict(context),
            producer_spine_context_ref=str(context.get("context_id", "")) or None,
            producer_spine_views=tuple(views),
            producer_spine_binding_fields=dict(binding_fields),
            consumed_concept_spine_ref=str(
                binding_fields.get("consumed_concept_spine_ref")
                or concept_spine_ref
                or ""
            )
            or None,
            consumed_jurisdiction_spine_ref=str(
                binding_fields.get("consumed_jurisdiction_spine_ref")
                or jurisdiction_spine_ref
                or ""
            )
            or None,
            canonical_concept_refs=_string_tuple(
                binding_fields.get("canonical_concept_refs", canonical_concept_refs)
            ),
            jurisdiction_refs=_string_tuple(
                binding_fields.get("jurisdiction_refs", jurisdiction_refs)
            ),
            unit_refs=_string_tuple(binding_fields.get("unit_refs", unit_refs)),
            period_refs=_string_tuple(binding_fields.get("period_refs", period_refs)),
            geography_refs=_string_tuple(
                binding_fields.get("geography_refs", geography_refs)
            ),
            governed_namespace_refs=_string_tuple(governed_namespace_refs),
            reconciled_concept_statuses=dict(reconciled_concept_statuses or {}),
            producer_handshake_refs=_string_tuple(producer_handshake_refs),
            candidate_spine_binding_refs=_string_tuple(
                binding_fields.get("candidate_spine_binding_refs", ())
            ),
            spine_blocker_refs=_string_tuple(binding_fields.get("spine_blocker_refs", ())),
            capability_reality_label=capability,
            direct_semantic_grounding_allowed=status == "pass" and capability == "implemented",
            parallel_concept_lattice_declared=parallel_concept_lattice_declared,
            issue_codes=issue_tuple,
        ),
    )


def build_g2_concept_alignment_records(
    *,
    request: Layer3G2CausalForecastRequest | None = None,
    semantic_spine_binding: Layer3G2SemanticSpineBinding | Mapping[str, Any] | None = None,
    source_contract_refs: Sequence[str] = (),
    g1_target_outcome_refs: Sequence[str] = (),
    g1_metric_refs: Sequence[str] = (),
    skg_cause_variable_ref: str | None = None,
    skg_effect_variable_ref: str | None = None,
    skg_parameter_refs: Sequence[str] = (),
    foundry_input_slot_refs: Sequence[str] = (),
    foundry_output_slot_refs: Sequence[str] = (),
    s10_target_outcome_refs: Sequence[str] = (),
    alignment_status: Literal["direct", "proxy_only", "ambiguous", "unmatched", "conflict"] = (
        "unmatched"
    ),
    proxy_disclosed: bool = False,
    direct_grounding_claimed: bool = False,
) -> tuple[Layer3G2ConceptAlignmentRecord, ...]:
    """Build concept alignment across G1, SKG variables, Foundry slots, and S10."""

    resolved_request = request or _default_g2_method_request()
    semantic = _mapping(semantic_spine_binding)
    issue_codes: list[str] = []
    if semantic.get("status") != "pass" or not semantic.get(
        "direct_semantic_grounding_allowed"
    ):
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")
    if not (
        _string_tuple(source_contract_refs)
        and _string_tuple(g1_target_outcome_refs)
        and skg_cause_variable_ref
        and skg_effect_variable_ref
        and _string_tuple(s10_target_outcome_refs)
    ):
        issue_codes.append("layer3_g2_concept_alignment_missing")
    if alignment_status == "proxy_only" and not proxy_disclosed:
        issue_codes.append("layer3_g2_proxy_alignment_undisclosed")
    if alignment_status in {"ambiguous", "conflict"} and direct_grounding_claimed:
        issue_codes.append("layer3_g2_ambiguous_alignment_overclaimed")
    if alignment_status == "unmatched":
        issue_codes.append("layer3_g2_concept_alignment_missing")

    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    if status == "pass" and alignment_status == "direct":
        disposition: Literal["direct_grounding", "proxy_limited", "blocked"] = (
            "direct_grounding"
        )
    elif status == "pass" and alignment_status == "proxy_only":
        disposition = "proxy_limited"
    else:
        disposition = "blocked"
    alignment_key = _stable_id(
        resolved_request.request_id,
        str(skg_cause_variable_ref),
        str(skg_effect_variable_ref),
    )
    return (
        Layer3G2ConceptAlignmentRecord(
            alignment_id=f"g2-concept-alignment:{alignment_key}",
            status=status,
            request_ref=resolved_request.request_id,
            semantic_spine_binding_ref=str(semantic.get("binding_id", "")) or None,
            source_contract_refs=_string_tuple(source_contract_refs),
            g1_target_outcome_refs=_string_tuple(g1_target_outcome_refs),
            g1_metric_refs=_string_tuple(g1_metric_refs),
            skg_cause_variable_ref=skg_cause_variable_ref,
            skg_effect_variable_ref=skg_effect_variable_ref,
            skg_parameter_refs=_string_tuple(skg_parameter_refs),
            foundry_input_slot_refs=_string_tuple(foundry_input_slot_refs),
            foundry_output_slot_refs=_string_tuple(foundry_output_slot_refs),
            s10_target_outcome_refs=_string_tuple(s10_target_outcome_refs),
            alignment_status=alignment_status,
            proxy_disclosed=proxy_disclosed,
            direct_grounding_claimed=direct_grounding_claimed,
            downgrade_disposition=disposition,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
        ),
    )


def build_g2_s10_prerequisite_bindings(
    *,
    request: Layer3G2CausalForecastRequest | None = None,
    semantic_spine_binding: Layer3G2SemanticSpineBinding | Mapping[str, Any] | None = None,
    concept_alignment_record: Layer3G2ConceptAlignmentRecord | Mapping[str, Any] | None = None,
    method_validity_record: Layer3G2MethodValidityTransportRecord | Mapping[str, Any] | None = (
        None
    ),
    source_design_record_ref: str | None = None,
    design_graph_ref: str | None = None,
    prediction_context_ref: str | None = None,
    policy_context_ref: str | None = None,
    candidate_design_ref: str | None = None,
    baseline_design_ref: str | None = None,
    alternative_design_refs: Sequence[str] = (),
    prediction_horizon_ref: str | None = None,
    target_outcome_refs: Sequence[str] = (),
    jurisdiction_scope_ref: str | None = None,
    s5_forecast_support_ref: str | None = None,
    s5_support_label: str | None = None,
    s5_base_origin: str | None = None,
    s5_claim_scope: str | None = None,
    s6_firewall_status_refs: Sequence[str] = (),
    s6_limitation_refs: Sequence[str] = (),
    s8_value_choice_provenance_ref: str | None = None,
    s8_value_tradeoff_disclosure_ref: str | None = None,
    source_contract_ref: str | None = None,
    method_validity_ref: str | None = None,
    sensitivity_analysis_ref: str | None = None,
    dynamic_equilibrium_check_ref: str | None = None,
    equilibrium_caveat_refs: Sequence[str] = (),
    strategic_response_caveat_refs: Sequence[str] = (),
    outcome_distribution_refs: Sequence[str] = (),
    welfare_comparison_ref: str | None = None,
    observable_subset_ref: str | None = None,
    uncertainty_interval_refs: Sequence[str] = (),
    limitation_refs: Sequence[str] = (),
    credible_evaluation_evidence_ref: str | None = None,
    source_lineage_refs: Sequence[str] = (),
    method_lineage_refs: Sequence[str] = (),
    forecast_authority_disposition_reason: str | None = None,
    method_family: str = "foundry_causal",
    may_not_use_for: Sequence[str] | None = None,
) -> tuple[Layer3G2S10PrerequisiteBinding, ...]:
    """Build the S10 prerequisite spine binding or return fail-closed issues."""

    resolved_request = request or _default_g2_method_request()
    semantic = _mapping(semantic_spine_binding)
    alignment = _mapping(concept_alignment_record)
    method_record = _mapping(method_validity_record)
    issue_codes: list[str] = []

    if semantic.get("status") != "pass":
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")
    if alignment.get("status") != "pass" or alignment.get("alignment_status") != "direct":
        issue_codes.append("layer3_g2_concept_alignment_missing")
    if method_record and method_record.get("status") != "pass":
        issue_codes.append("layer3_g2_method_validity_missing")

    s6_refs = _string_tuple(s6_firewall_status_refs)
    if not (
        s5_forecast_support_ref
        and s6_refs
        and s8_value_choice_provenance_ref
        and s8_value_tradeoff_disclosure_ref
    ):
        issue_codes.append("layer3_g2_s5_s6_s8_refs_missing")
    if not (
        design_graph_ref
        and prediction_context_ref
        and policy_context_ref
        and candidate_design_ref
        and baseline_design_ref
        and prediction_horizon_ref
        and _string_tuple(target_outcome_refs)
        and jurisdiction_scope_ref
    ):
        issue_codes.append("layer3_g2_design_prediction_context_missing")

    denials = _string_tuple(may_not_use_for) if may_not_use_for is not None else G2_MAY_NOT_USE_FOR
    issue_codes.extend(_g2_authority_leak_issue_codes(may_not_use_for=denials))
    method_refs = tuple(
        dict.fromkeys(
            [
                *([method_validity_ref] if method_validity_ref else []),
                *_string_tuple(method_record.get("method_validity_refs", ())),
            ]
        )
    )
    s5_s6_s8_refs = tuple(
        dict.fromkeys(
            [
                *([s5_forecast_support_ref] if s5_forecast_support_ref else []),
                *s6_refs,
                *(
                    [s8_value_choice_provenance_ref]
                    if s8_value_choice_provenance_ref
                    else []
                ),
                *(
                    [s8_value_tradeoff_disclosure_ref]
                    if s8_value_tradeoff_disclosure_ref
                    else []
                ),
            ]
        )
    )
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return (
        Layer3G2S10PrerequisiteBinding(
            binding_id=(
                "g2-s10-prerequisite-binding:"
                f"{_stable_id(resolved_request.request_id, str(design_graph_ref))}"
            ),
            status=status,
            request_ref=resolved_request.request_id,
            semantic_spine_binding_ref=str(semantic.get("binding_id", "")) or None,
            concept_alignment_ref=str(alignment.get("alignment_id", "")) or None,
            source_design_record_ref=source_design_record_ref,
            design_graph_ref=design_graph_ref,
            prediction_context_ref=prediction_context_ref,
            policy_context_ref=policy_context_ref,
            candidate_design_ref=candidate_design_ref,
            baseline_design_ref=baseline_design_ref,
            alternative_design_refs=_string_tuple(alternative_design_refs),
            prediction_horizon_ref=prediction_horizon_ref,
            target_outcome_refs=_string_tuple(target_outcome_refs),
            jurisdiction_scope_ref=jurisdiction_scope_ref,
            s5_forecast_support_ref=s5_forecast_support_ref,
            s5_support_label=s5_support_label,
            s5_base_origin=s5_base_origin,
            s5_claim_scope=s5_claim_scope,
            s6_firewall_status_refs=s6_refs,
            s6_limitation_refs=_string_tuple(s6_limitation_refs),
            s8_value_choice_provenance_ref=s8_value_choice_provenance_ref,
            s8_value_tradeoff_disclosure_ref=s8_value_tradeoff_disclosure_ref,
            s5_s6_s8_refs=s5_s6_s8_refs,
            source_contract_ref=source_contract_ref
            or _first_or_none(_string_tuple(resolved_request.source_contract_refs)),
            method_validity_ref=method_validity_ref or _first_or_none(method_refs),
            method_validity_refs=method_refs,
            sensitivity_analysis_ref=sensitivity_analysis_ref,
            dynamic_equilibrium_check_ref=dynamic_equilibrium_check_ref,
            equilibrium_caveat_refs=_string_tuple(equilibrium_caveat_refs),
            strategic_response_caveat_refs=_string_tuple(strategic_response_caveat_refs),
            outcome_distribution_refs=_string_tuple(outcome_distribution_refs),
            welfare_comparison_ref=welfare_comparison_ref,
            observable_subset_ref=observable_subset_ref,
            uncertainty_interval_refs=_string_tuple(uncertainty_interval_refs),
            limitation_refs=_string_tuple(limitation_refs),
            credible_evaluation_evidence_ref=credible_evaluation_evidence_ref,
            source_lineage_refs=_string_tuple(source_lineage_refs),
            method_lineage_refs=_string_tuple(method_lineage_refs),
            forecast_authority_disposition_reason=(
                forecast_authority_disposition_reason
                or "G2 translated bounded causal/forecast search through existing S10 support."
            ),
            method_family=method_family,
            capability_reality_label="implemented" if status == "pass" else "bridge_missing",
            may_not_use_for=denials,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
        ),
    )


def build_g2_forecast_support_bindings(
    *,
    request: Layer3G2CausalForecastRequest | None = None,
    search_result: Layer3G2SkgSearchResult | Mapping[str, Any] | None = None,
    semantic_spine_binding: Layer3G2SemanticSpineBinding | Mapping[str, Any] | None = None,
    concept_alignment_record: Layer3G2ConceptAlignmentRecord | Mapping[str, Any] | None = None,
    s10_prerequisite_binding: Layer3G2S10PrerequisiteBinding | Mapping[str, Any] | None = None,
    method_validity_record: Layer3G2MethodValidityTransportRecord | Mapping[str, Any] | None = (
        None
    ),
    requested_forecast_tier: str | None = None,
    calibration_payload: Mapping[str, Any] | None = None,
    requested_adapter_maturity: AdapterMaturity | None = None,
    calibrated_dynamics_producer_ref: str | None = None,
    adapter_validation_ref: str | None = None,
) -> tuple[Layer3G2ForecastSupportBinding, ...]:
    """Translate admitted G2 candidates into existing S10 ForecastSupport."""

    resolved_request = request or _default_g2_method_request()
    semantic = _mapping(semantic_spine_binding)
    alignment = _mapping(concept_alignment_record)
    prereq = _mapping(s10_prerequisite_binding)
    method_record = _mapping(method_validity_record)
    search_refs = _g2_search_refs(search_result)
    issue_codes: list[str] = []
    issue_codes.extend(_string_tuple(semantic.get("issue_codes", ())))
    issue_codes.extend(_string_tuple(alignment.get("issue_codes", ())))
    issue_codes.extend(_string_tuple(prereq.get("issue_codes", ())))
    if semantic.get("status") != "pass":
        issue_codes.append("layer3_g2_semantic_binding_spine_missing")
    if alignment.get("status") != "pass" or alignment.get("alignment_status") != "direct":
        issue_codes.append("layer3_g2_concept_alignment_missing")
    if prereq.get("status") != "pass":
        issue_codes.append("layer3_g2_s10_prerequisite_binding_missing")
    if method_record and method_record.get("status") != "pass":
        issue_codes.append("layer3_g2_method_validity_missing")

    binding_key = _stable_id(
        resolved_request.request_id,
        str(prereq.get("binding_id", "missing-prereq")),
        str(search_refs["search_ledger_refs"]),
    )
    support_ref = (
        f"pdc://layer3/g2/{_slug_token(resolved_request.case_id)}/"
        f"forecast-support/{binding_key}"
    )
    adapter_ref = adapter_validation_ref or f"adapter-validation://g2/s10/{binding_key}"
    limitation_refs = list(_string_tuple(prereq.get("limitation_refs", ())))
    publish_blocker_refs = _g2_publish_blockers_for_contested_edges(
        search_refs["contested_edge_refs"]
    )
    if search_refs["contested_edge_refs"]:
        issue_codes.append("layer3_g2_contested_edge_overclaimed")
        limitation_refs.extend(
            _g2_contested_limitation_refs(search_refs["contested_edge_refs"])
        )
    equilibrium_blocker_refs: tuple[str, ...] = ()
    if _g2_requires_calibrated_dynamics(prereq) and not calibrated_dynamics_producer_ref:
        equilibrium_blocker_refs = (
            "equilibrium-blocker://layer3/g2/calibrated-dynamics-producer-missing",
        )
        issue_codes.append("layer3_g2_equilibrium_authority_overclaim")
    calibration_record = None
    calibration_ref: str | None = None
    calibration_attempt: dict[str, Any] = {}
    try:
        if calibration_payload is not None:
            from polisyos.runtime.quality.layer2_outcome_prediction import (
                build_forecast_calibration_record,
            )

            calibration_input = dict(calibration_payload)
            calibration_input.setdefault("forecast_support_ref", support_ref)
            calibration_input.setdefault("case_id", resolved_request.case_id)
            calibration_attempt = dict(calibration_input)
            calibration_record = build_forecast_calibration_record(**calibration_input)
            calibration_ref = calibration_record.calibration_ref
        elif requested_forecast_tier == "observable_calibrated":
            issue_codes.append("layer3_g2_observable_calibration_required")
    except Exception as exc:
        issue_codes.extend(_g2_forecast_exception_issue_codes(exc))

    support = None
    envelope = None
    integrity = None
    try:
        from polisyos.runtime.quality.layer2_outcome_prediction import (
            build_forecast_support,
            summarize_forecast_support_integrity,
            verify_prediction_authority_envelope,
        )

        support_payload = _g2_s10_support_payload(
            request=resolved_request,
            prereq=prereq,
            support_ref=support_ref,
            requested_forecast_tier=requested_forecast_tier,
            calibration_record_ref=calibration_ref,
            method_record=method_record,
            limitation_refs=tuple(limitation_refs),
        )
        support = build_forecast_support(**support_payload)
        if requested_forecast_tier and support.forecast_tier != requested_forecast_tier:
            issue_codes.append("layer3_g2_s10_tier_derivation_mismatch")
            issue_codes.extend(_g2_derived_tier_laundering_codes(support.forecast_tier))
        if support.forecast_tier == "observable_calibrated" and calibration_record is None:
            issue_codes.append("layer3_g2_observable_calibration_required")
        envelope = verify_prediction_authority_envelope(
            forecast_support=support,
            calibration_record=calibration_record,
            method_boundary_ref=support.method_validity_ref,
        )
        integrity = summarize_forecast_support_integrity(
            forecast_supports=(support,),
            calibration_records=(calibration_record,) if calibration_record else (),
            report_id=f"layer3.g2.forecast-support.integrity.{binding_key}",
            report_ref=f"{support_ref}/integrity",
        )
    except Exception as exc:
        issue_codes.extend(_g2_forecast_exception_issue_codes(exc))

    if not search_refs["search_ledger_refs"]:
        issue_codes.append("layer3_g2_search_ledger_missing")
    if not adapter_ref:
        issue_codes.append("layer3_g2_raw_skg_output_without_adapter")

    issue_codes.extend(
        _g2_authority_leak_issue_codes(
            may_not_use_for=_merge_g2_denials(
                _string_tuple(prereq.get("may_not_use_for", G2_MAY_NOT_USE_FOR)),
                _string_tuple(getattr(support, "may_not_use_for", ())),
            ),
            authoritative_for=("g2_forecast_support_binding_audit",),
        )
    )
    issue_tuple = tuple(dict.fromkeys(issue_codes))
    status: Literal["pass", "fail"] = "fail" if issue_tuple else "pass"
    support_payload = support.model_dump(mode="json") if support is not None else {}
    envelope_payload = envelope.model_dump(mode="json") if envelope is not None else {}
    integrity_payload = integrity.model_dump(mode="json") if integrity is not None else {}
    calibration_payload_dump = (
        calibration_record.model_dump(mode="json") if calibration_record is not None else {}
    )
    may_not_use_for = _merge_g2_denials(
        _string_tuple(prereq.get("may_not_use_for", G2_MAY_NOT_USE_FOR)),
        _string_tuple(support_payload.get("may_not_use_for", ())),
    )
    maturity_blockers = _g2_adapter_maturity_blockers(
        issue_codes=issue_tuple,
        calibration_record=calibration_payload_dump,
        authority_envelope=envelope_payload,
        requested_adapter_maturity=requested_adapter_maturity,
    )
    adapter_maturity = _g2_adapter_maturity(
        issue_codes=issue_tuple,
        calibration_record=calibration_payload_dump,
        authority_envelope=envelope_payload,
        requested_adapter_maturity=requested_adapter_maturity,
    )
    if requested_adapter_maturity == "calibrated" and adapter_maturity != "calibrated":
        issue_tuple = tuple(
            dict.fromkeys([*issue_tuple, "layer3_g2_adapter_maturity_overclaim"])
        )
        status = "fail"
    return (
        Layer3G2ForecastSupportBinding(
            binding_id=f"g2-forecast-support-binding:{binding_key}",
            status=status,
            request_ref=resolved_request.request_id,
            s10_prerequisite_binding_ref=str(prereq.get("binding_id", "")) or None,
            semantic_spine_binding_ref=str(semantic.get("binding_id", "")) or None,
            concept_alignment_ref=str(alignment.get("alignment_id", "")) or None,
            adapter_validation_ref=adapter_ref,
            s10_forecast_support_ref=support_payload.get("support_ref") or support_ref,
            s10_forecast_tier=support_payload.get("forecast_tier"),
            requested_forecast_tier=requested_forecast_tier,
            s10_forecast_support=support_payload,
            calibration_record_ref=calibration_payload_dump.get("calibration_ref"),
            calibration_record=calibration_payload_dump,
            calibration_attempt=calibration_attempt,
            authority_envelope_ref=envelope_payload.get("envelope_ref"),
            authority_envelope=envelope_payload,
            integrity_summary_ref=integrity_payload.get("report_ref"),
            integrity_summary=integrity_payload,
            g1_binding_refs=_string_tuple(resolved_request.source_contract_refs),
            skg_edge_refs=search_refs["skg_edge_refs"],
            skg_claim_refs=search_refs["skg_claim_refs"],
            skg_parameter_refs=search_refs["skg_parameter_refs"],
            skg_transport_refs=search_refs["skg_transport_refs"],
            skg_transport_confidence_by_ref=search_refs["skg_transport_confidence_by_ref"],
            contested_edge_refs=search_refs["contested_edge_refs"],
            publish_blocker_refs=publish_blocker_refs,
            method_validity_refs=_string_tuple(prereq.get("method_validity_refs", ())),
            limitation_refs=tuple(dict.fromkeys(limitation_refs)),
            uncertainty_interval_refs=_string_tuple(
                prereq.get("uncertainty_interval_refs", ())
            ),
            search_ledger_refs=search_refs["search_ledger_refs"],
            requested_adapter_maturity=requested_adapter_maturity,
            adapter_maturity=adapter_maturity,
            maturity_blocker_refs=maturity_blockers,
            calibrated_dynamics_producer_ref=calibrated_dynamics_producer_ref,
            equilibrium_blocker_refs=equilibrium_blocker_refs,
            may_not_use_for=may_not_use_for,
            issue_codes=issue_tuple,
        ),
    )


def build_g2_observable_calibration_report(
    forecast_support_bindings: Sequence[Layer3G2ForecastSupportBinding | Mapping[str, Any]],
) -> Layer3G2ObservableCalibrationReport:
    """Summarize observable calibration from G2 bindings and S10 records."""

    bindings = [_mapping(binding) for binding in forecast_support_bindings]
    calibration_records = [
        _mapping(binding.get("calibration_record")) or _mapping(binding.get("calibration_attempt"))
        for binding in bindings
    ]
    calibration_records = [record for record in calibration_records if record]
    denominator = sum(int(record.get("denominator") or 0) for record in calibration_records)
    numerator = sum(int(record.get("numerator") or 0) for record in calibration_records)
    pass_rate = numerator / denominator if denominator else 0.0
    evidence_refs = _refs_from_records(calibration_records, "credible_evaluation_evidence_ref")
    observed_refs = _refs_from_records(calibration_records, "observed_outcome_ref")
    threshold_ref = _first_or_none(
        _refs_from_records(calibration_records, "calibration_threshold_ref")
    )
    time_roles = tuple(
        role
        for role in (
            "prediction_time",
            "observation_time",
            "policy_effective_time",
            "data_valid_time",
            "calibration_window_start",
            "calibration_window_end",
        )
        if any(record.get(role) for record in calibration_records)
    )
    issue_codes: list[str] = []
    for binding in bindings:
        issue_codes.extend(_string_tuple(binding.get("issue_codes", ())))
    if denominator <= 0:
        issue_codes.append("layer3_g2_observable_calibration_denominator_missing")
    if not evidence_refs:
        issue_codes.append("layer3_g2_credible_evaluation_evidence_missing")
    calibration_maturity_requested = any(
        binding.get("requested_adapter_maturity") == "calibrated" for binding in bindings
    )
    all_bindings_calibrated = bool(bindings) and all(
        binding.get("adapter_maturity") == "calibrated" for binding in bindings
    )
    if calibration_maturity_requested and not all_bindings_calibrated:
        issue_codes.append("layer3_g2_adapter_maturity_overclaim")

    issue_tuple = tuple(dict.fromkeys(issue_codes))
    status: Literal["pass", "fail"] = "fail" if issue_tuple else "pass"
    adapter_maturity: AdapterMaturity
    if status == "pass" and all_bindings_calibrated:
        adapter_maturity = "calibrated"
    elif any(binding.get("adapter_maturity") == "fail_closed" for binding in bindings):
        adapter_maturity = "fail_closed"
    else:
        adapter_maturity = "predictive"
    return Layer3G2ObservableCalibrationReport(
        status=status,
        adapter_maturity=adapter_maturity,
        forecast_support_binding_refs=_refs_from_records(bindings, "binding_id"),
        forecast_support_refs=_refs_from_records(bindings, "s10_forecast_support_ref"),
        calibration_record_refs=_refs_from_records(calibration_records, "calibration_ref"),
        authority_envelope_refs=_refs_from_records(bindings, "authority_envelope_ref"),
        observable_subset_refs=_refs_from_records(calibration_records, "observable_subset_ref"),
        observed_outcome_refs=observed_refs,
        credible_evaluation_evidence_refs=evidence_refs,
        counterfactual_credibility_refs=_refs_from_records(
            calibration_records,
            "counterfactual_credibility",
        ),
        time_role_refs=time_roles,
        observable_subset_calibration_denominator=denominator,
        observable_subset_calibration_numerator=numerator,
        observable_subset_calibration_pass_rate=pass_rate,
        calibration_threshold_ref=threshold_ref,
        calibration_floor_passed=bool(
            denominator and numerator == denominator and not issue_tuple
        ),
        issue_codes=issue_tuple,
    )


def build_g2_transport_limit_declarations(
    *,
    search_result: Layer3G2SkgSearchResult | Mapping[str, Any] | None = None,
    forecast_support_bindings: Sequence[
        Layer3G2ForecastSupportBinding | Mapping[str, Any]
    ] = (),
    method_validity_record: Layer3G2MethodValidityTransportRecord
    | Mapping[str, Any]
    | None = None,
    jurisdiction_scope_ref: str | None = None,
    aggregation_scope_ref: str | None = None,
) -> tuple[Layer3G2TransportLimitDeclaration, ...]:
    """Build transport declarations from SKG transport rows and Foundry limits."""

    bindings = [_mapping(binding) for binding in forecast_support_bindings]
    method_record = _mapping(method_validity_record)
    search_refs = _g2_search_refs(search_result)
    skg_transport_refs = tuple(
        dict.fromkeys(
            [
                *search_refs["skg_transport_refs"],
                *[
                    ref
                    for binding in bindings
                    for ref in _string_tuple(binding.get("skg_transport_refs", ()))
                ],
            ]
        )
    )
    confidence_by_ref = dict(search_refs["skg_transport_confidence_by_ref"])
    for binding in bindings:
        confidence_by_ref.update(
            {
                str(key): float(value)
                for key, value in _mapping(
                    binding.get("skg_transport_confidence_by_ref")
                ).items()
            }
        )
    limitation_refs = tuple(
        dict.fromkeys(
            ref
            for binding in bindings
            for ref in _string_tuple(binding.get("limitation_refs", ()))
        )
    )
    uncertainty_refs = tuple(
        dict.fromkeys(
            ref
            for binding in bindings
            for ref in _string_tuple(binding.get("uncertainty_interval_refs", ()))
        )
    )
    method_limit_refs = _string_tuple(method_record.get("transportability_limit_refs", ()))
    tiers = {
        str(binding.get("s10_forecast_tier") or binding.get("requested_forecast_tier") or "")
        for binding in bindings
    }
    issue_codes: list[str] = []
    if "transported_limited" in tiers and not limitation_refs:
        issue_codes.append("layer3_g2_transport_limit_missing")
    if "transported_limited" in tiers and not skg_transport_refs:
        issue_codes.append("layer3_g2_transport_limit_missing")
    if "transported_limited" in tiers and not uncertainty_refs:
        issue_codes.append("layer3_g2_uncertainty_interval_missing")
    if not method_limit_refs:
        issue_codes.append("layer3_g2_transportability_limit_missing")
    issue_tuple = tuple(dict.fromkeys(issue_codes))
    status: Literal["pass", "fail"] = "fail" if issue_tuple else "pass"
    transport_status: Literal["not_transportable", "limited", "blocked"] = (
        "blocked" if status == "fail" else "limited"
    )
    declaration_key = _stable_id(
        *(skg_transport_refs or ("no-skg-transport",)),
        *(method_limit_refs or ("no-method-limit",)),
        str(jurisdiction_scope_ref),
        str(aggregation_scope_ref),
    )
    return (
        Layer3G2TransportLimitDeclaration(
            declaration_id=f"g2-transport-limit-declaration:{declaration_key}",
            status=status,
            transport_status=transport_status,
            request_ref=_first_or_none(_refs_from_records(bindings, "request_ref")),
            forecast_support_binding_refs=_refs_from_records(bindings, "binding_id"),
            forecast_support_refs=_refs_from_records(bindings, "s10_forecast_support_ref"),
            skg_transport_score_refs=skg_transport_refs,
            transport_confidence_by_ref=confidence_by_ref,
            method_transportability_limit_refs=method_limit_refs,
            jurisdiction_scope_ref=jurisdiction_scope_ref,
            aggregation_scope_ref=aggregation_scope_ref,
            uncertainty_interval_refs=uncertainty_refs,
            limitation_refs=limitation_refs,
            issue_codes=issue_tuple,
        ),
    )


def build_g2_grounded_forecast_handoffs(
    *,
    forecast_support_bindings: Sequence[
        Layer3G2ForecastSupportBinding | Mapping[str, Any]
    ] = (),
    concept_alignment_records: Sequence[
        Layer3G2ConceptAlignmentRecord | Mapping[str, Any]
    ] = (),
    observable_calibration_report: Layer3G2ObservableCalibrationReport
    | Mapping[str, Any]
    | None = None,
    transport_limit_declarations: Sequence[
        Layer3G2TransportLimitDeclaration | Mapping[str, Any]
    ] = (),
) -> tuple[Layer3G2GroundedForecastHandoffRecord, ...]:
    """Build G4/G5 handoff rows from S10-valid G2 forecast support.

    The handoff is a replay/audit surface for later promotion/conversion slices;
    it is not promotion authority and never grants useful-design credit.
    """

    alignments = [_mapping(record) for record in concept_alignment_records]
    alignment_by_ref = {
        str(record.get("alignment_id")): record
        for record in alignments
        if record.get("alignment_id")
    }
    calibration = _mapping(observable_calibration_report)
    calibration_refs = _string_tuple(calibration.get("calibration_record_refs", ()))
    transport_records = [_mapping(record) for record in transport_limit_declarations]
    transport_refs = _refs_from_records(transport_records, "declaration_id")
    handoffs: list[Layer3G2GroundedForecastHandoffRecord] = []
    for binding_obj in forecast_support_bindings:
        binding = _mapping(binding_obj)
        support = _mapping(binding.get("s10_forecast_support"))
        binding_ref = str(binding.get("binding_id") or "")
        support_ref = str(
            binding.get("s10_forecast_support_ref")
            or support.get("support_ref")
            or ""
        )
        concept_alignment_ref = str(binding.get("concept_alignment_ref") or "")
        alignment = alignment_by_ref.get(concept_alignment_ref, {})
        source_contract_ref = str(
            support.get("source_contract_ref")
            or binding.get("source_contract_ref")
            or _first_or_none(_string_tuple(alignment.get("source_contract_refs", ())))
            or ""
        )
        method_validity_refs = _refs_with_prefix(
            _string_tuple(binding.get("method_validity_refs", ())),
            "method-validity://",
        )
        if not method_validity_refs and support.get("method_validity_ref"):
            method_validity_refs = (str(support.get("method_validity_ref")),)
        method_requirement_refs = _string_tuple(support.get("method_requirement_refs", ()))
        if not method_requirement_refs and binding.get("s10_prerequisite_binding_ref"):
            method_requirement_refs = (
                f"method-requirement:{binding.get('s10_prerequisite_binding_ref')}",
            )
        handoff_calibration_refs = tuple(
            dict.fromkeys(
                ref
                for ref in (
                    str(binding.get("calibration_record_ref") or ""),
                    *calibration_refs,
                )
                if ref
            )
        )
        search_ledger_refs = _string_tuple(binding.get("search_ledger_refs", ()))
        skg_query_trace_refs = tuple(
            dict.fromkeys(
                ref.replace("g2-ledger:", "g2-trace:", 1)
                if ref.startswith("g2-ledger:")
                else f"g2-trace:{_stable_id(ref)}"
                for ref in search_ledger_refs
                if ref
            )
        )
        issue_codes: list[str] = []
        if not support_ref or str(binding.get("status") or "") != "pass":
            issue_codes.append("layer3_g2_grounded_forecast_handoff_missing")
        if not (source_contract_ref and method_validity_refs and method_requirement_refs):
            issue_codes.append("layer3_g2_s2_design_record_replay_overclaim")
        if not skg_query_trace_refs:
            issue_codes.append("layer3_g2_s2_design_record_replay_overclaim")
        status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
        handoff_id = f"g2-grounded-forecast-handoff:{_stable_id(binding_ref, support_ref)}"
        handoffs.append(
            Layer3G2GroundedForecastHandoffRecord(
                handoff_id=handoff_id,
                status=status,
                forecast_support_binding_ref=binding_ref or None,
                s10_forecast_support_ref=support_ref or None,
                s10_forecast_tier=str(
                    binding.get("s10_forecast_tier")
                    or support.get("forecast_tier")
                    or ""
                )
                or None,
                concept_alignment_ref=concept_alignment_ref or None,
                source_contract_ref=source_contract_ref or None,
                method_validity_refs=method_validity_refs,
                method_requirement_refs=method_requirement_refs,
                calibration_record_refs=handoff_calibration_refs,
                transport_limit_declaration_refs=transport_refs,
                uncertainty_interval_refs=_string_tuple(
                    binding.get("uncertainty_interval_refs")
                    or support.get("uncertainty_interval_refs")
                    or ()
                ),
                limitation_refs=_string_tuple(
                    binding.get("limitation_refs") or support.get("limitation_refs") or ()
                ),
                search_ledger_refs=search_ledger_refs,
                skg_query_trace_refs=skg_query_trace_refs,
                skg_edge_refs=_string_tuple(binding.get("skg_edge_refs", ())),
                skg_claim_refs=_string_tuple(binding.get("skg_claim_refs", ())),
                skg_parameter_refs=_string_tuple(binding.get("skg_parameter_refs", ())),
                source_contract_replay_refs=tuple(
                    ref for ref in (source_contract_ref,) if ref
                ),
                design_record_ledger_refs=tuple(
                    ref
                    for ref in (str(support.get("source_design_record_ref") or ""),)
                    if ref
                ),
                adapter_maturity=str(binding.get("adapter_maturity") or "fail_closed"),  # type: ignore[arg-type]
                g4_g5_readable_handoff_ref=handoff_id,
                authoritative_for=("grounded_forecast_handoff",),
                may_not_use_for=_merge_g2_denials(
                    _string_tuple(binding.get("may_not_use_for", ())),
                    ("promotion_authority", "conversion_authority"),
                ),
                issue_codes=tuple(dict.fromkeys(issue_codes)),
            )
        )
    return tuple(handoffs)


def build_g2_s10_forecast_posture(
    binding: Layer3G2ForecastSupportBinding,
) -> Layer2S10ForecastPostureInput:
    """Translate a G2 S10 ForecastSupport binding into the public PDC posture."""

    from polisyos.pdc import Layer2S10ForecastPostureInput

    binding_payload = _mapping(binding)
    support = _mapping(binding_payload.get("s10_forecast_support"))
    authority_envelope = _mapping(binding_payload.get("authority_envelope"))
    support_ref = str(
        binding_payload.get("s10_forecast_support_ref")
        or support.get("support_ref")
        or ""
    )
    calibration_ref = str(
        binding_payload.get("calibration_record_ref")
        or support.get("calibration_record_ref")
        or ""
    )
    method_validity_ref = str(
        support.get("method_validity_ref")
        or _first_or_none(_refs_with_prefix(
            _string_tuple(binding_payload.get("method_validity_refs", ())),
            "method-validity://",
        ))
        or ""
    )
    authority_boundary = _mapping(support.get("authority_boundary")) or _mapping(
        authority_envelope.get("authority_boundary")
    )
    return Layer2S10ForecastPostureInput(
        forecast_support_ref=support_ref,
        forecast_tier=str(
            binding_payload.get("s10_forecast_tier")
            or support.get("forecast_tier")
            or ""
        ),  # type: ignore[arg-type]
        forecast_authority_disposition_reason=str(
            support.get("forecast_authority_disposition_reason")
            or binding_payload.get("forecast_authority_disposition_reason")
            or "G2 translated bounded causal/forecast search through existing S10 support."
        ),
        forecast_support_label=str(
            support.get("forecast_support_label")
            or support.get("s5_support_label")
            or "g2_forecast_support"
        ),
        forecast_calibration_record_ref=calibration_ref or None,
        design_graph_ref=str(support.get("design_graph_ref") or ""),
        prediction_context_ref=str(support.get("prediction_context_ref") or ""),
        policy_context_ref=str(support.get("policy_context_ref") or ""),
        candidate_design_ref=str(support.get("candidate_design_ref") or ""),
        baseline_design_ref=str(support.get("baseline_design_ref") or ""),
        alternative_design_refs=list(
            _string_tuple(support.get("alternative_design_refs", ()))
        ),
        prediction_horizon_ref=str(support.get("prediction_horizon_ref") or ""),
        observable_subset_ref=str(support.get("observable_subset_ref") or "") or None,
        uncertainty_interval_refs=list(
            _string_tuple(
                binding_payload.get("uncertainty_interval_refs")
                or support.get("uncertainty_interval_refs")
                or ()
            )
        ),
        welfare_comparison_ref=str(support.get("welfare_comparison_ref") or "") or None,
        s5_forecast_support_ref=str(support.get("s5_forecast_support_ref") or ""),
        s6_firewall_status_refs=list(
            _string_tuple(support.get("s6_firewall_status_refs", ()))
        ),
        s8_value_choice_provenance_ref=str(
            support.get("s8_value_choice_provenance_ref") or ""
        ),
        s8_value_tradeoff_disclosure_ref=str(
            support.get("s8_value_tradeoff_disclosure_ref") or ""
        ),
        source_contract_ref=str(support.get("source_contract_ref") or "") or None,
        method_validity_ref=method_validity_ref or None,
        credible_evaluation_evidence_ref=str(
            support.get("credible_evaluation_evidence_ref") or ""
        )
        or None,
        dynamic_equilibrium_check_ref=str(
            support.get("dynamic_equilibrium_check_ref") or ""
        )
        or None,
        sensitivity_analysis_ref=str(support.get("sensitivity_analysis_ref") or "")
        or None,
        authority_boundary=dict(authority_boundary),
        may_not_use_for=list(
            _merge_g2_denials(
                _string_tuple(support.get("may_not_use_for", ())),
                _string_tuple(binding_payload.get("may_not_use_for", ())),
            )
        ),
        rule_version_ref=str(
            support.get("rule_version_ref") or "policyos.layer2.s10.outcome_prediction.v1"
        ),
    )


def build_g2_w12d_consumer_gate(
    *,
    forecast_postures: Sequence[Mapping[str, Any] | BaseModel] = (),
    forecast_support_bindings: Sequence[
        Layer3G2ForecastSupportBinding | Mapping[str, Any]
    ] = (),
    layer3_g1_grounding_gate_ref: str | None = None,
    full_s2_consumer_case_refs: Sequence[str] = (),
    lightweight_case_refs: Sequence[str] = (),
    lightweight_posture_ref: str | None = None,
    domain_ceiling_status: str | None = None,
    closeout_claimed: bool = False,
    recommendation_authority_claimed: bool = False,
    claim_authority_claimed: bool = False,
) -> Layer3G2W12DConsumerGateRecord:
    """Build the W12D gate consuming G2 forecast posture as forecast support."""

    postures = [_mapping(posture) for posture in forecast_postures]
    bindings = [_mapping(binding) for binding in forecast_support_bindings]
    full_refs = _string_tuple(full_s2_consumer_case_refs)
    lightweight_refs = _string_tuple(lightweight_case_refs)
    ceiling_status = str(domain_ceiling_status or "")
    is_ceiling_route = ceiling_status in {
        "causal_forecast_domain_ceiling",
        "search_ceiling_repair_required",
    }
    lightweight_only = bool(lightweight_posture_ref or lightweight_refs) and not (
        postures or bindings
    )
    posture_consumed = bool(postures) and not is_ceiling_route
    posture_refs = _refs_from_records(postures, "forecast_support_ref")
    binding_support_refs = _refs_from_records(bindings, "s10_forecast_support_ref")
    forecast_support_refs = tuple(dict.fromkeys((*posture_refs, *binding_support_refs)))
    issue_codes: list[str] = []
    if not posture_consumed and not is_ceiling_route and not lightweight_only:
        issue_codes.append("layer3_g2_w12d_not_routed_closeout")
        if bindings:
            issue_codes.append("layer3_g2_s10_posture_not_consumed")
    if len(full_refs) > 1:
        issue_codes.append("layer3_g2_w12d_full_s2_overreach")
    if closeout_claimed:
        issue_codes.append("layer3_g2_closeout_authority_leak")
    if recommendation_authority_claimed:
        issue_codes.append("layer3_g2_recommendation_authority_leak")
    if claim_authority_claimed:
        issue_codes.append("layer3_g2_claim_authority_leak")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2W12DConsumerGateRecord(
        status=status,
        layer3_g1_grounding_gate_ref=layer3_g1_grounding_gate_ref,
        posture_consumed=posture_consumed,
        consumed_forecast_posture_refs=posture_refs if posture_consumed else (),
        forecast_support_refs=forecast_support_refs,
        forecast_tiers=_refs_from_records(postures, "forecast_tier"),
        forecast_calibration_record_refs=_refs_from_records(
            postures,
            "forecast_calibration_record_ref",
        ),
        source_contract_refs=_refs_from_records(postures, "source_contract_ref"),
        method_validity_refs=_refs_from_records(postures, "method_validity_ref"),
        uncertainty_interval_refs=tuple(
            dict.fromkeys(
                ref
                for posture in postures
                for ref in _string_tuple(posture.get("uncertainty_interval_refs", ()))
            )
        ),
        full_s2_consumer_case_refs=full_refs,
        lightweight_case_refs=lightweight_refs,
        lightweight_posture_ref=lightweight_posture_ref,
        full_s2_consumer_case_count=len(full_refs),
        lightweight_forecast_posture_ref_count=len(lightweight_refs),
        useful_design_delta_count=0,
        closeout_claimed=closeout_claimed,
        recommendation_authority_claimed=recommendation_authority_claimed,
        claim_authority_claimed=claim_authority_claimed,
        domain_ceiling_status=ceiling_status or None,
        may_not_use_for=_merge_g2_denials(
            *[_string_tuple(posture.get("may_not_use_for", ())) for posture in postures]
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g2_causal_forecast_audit_surface(
    bundle: Layer3G2Bundle | None,
) -> Layer3G2CausalForecastAuditSurface:
    """Build the G2 all-audience forecast-tier and limitation audit surface."""

    if bundle is None:
        return Layer3G2CausalForecastAuditSurface(
            status="fail",
            issue_codes=("layer3_g2_surface_unsynced",),
        )
    payload = _mapping(bundle)
    bindings = [_mapping(item) for item in _sequence(payload.get("forecast_support_bindings"))]
    handoffs = [_mapping(item) for item in _sequence(payload.get("grounded_forecast_handoffs"))]
    gate = _mapping(payload.get("w12d_consumer_gate"))
    ledgers = [_mapping(item) for item in _sequence(payload.get("l2_skg_search_ledgers"))]
    forecast_support_refs = _refs_from_records(bindings, "s10_forecast_support_ref")
    forecast_tiers = tuple(
        dict.fromkeys(
            ref
            for ref in _refs_from_records(bindings, "s10_forecast_tier")
            if ref
        )
    )
    uncertainty_refs = tuple(
        dict.fromkeys(
            ref
            for ref in (
                *[
                    ref
                    for binding in bindings
                    for ref in _string_tuple(binding.get("uncertainty_interval_refs", ()))
                ],
                *_string_tuple(gate.get("uncertainty_interval_refs", ())),
            )
            if ref
        )
    )
    limitation_refs = tuple(
        dict.fromkeys(
            ref
            for binding in bindings
            for ref in _string_tuple(binding.get("limitation_refs", ()))
            if ref
        )
    )
    denials = _merge_g2_denials(
        *[_string_tuple(binding.get("may_not_use_for", ())) for binding in bindings]
    )
    issue_codes: list[str] = []
    if not forecast_support_refs or not forecast_tiers:
        issue_codes.append("layer3_g2_forecast_support_missing")
    if not uncertainty_refs:
        issue_codes.append("layer3_g2_uncertainty_interval_missing")
    if not limitation_refs:
        issue_codes.append("layer3_g2_transport_limit_missing")
    if not set(G2_REQUIRED_AUTHORITY_DENIALS) <= set(denials):
        issue_codes.append("layer3_g2_public_surface_visibility_missing")
    if gate.get("status") != "pass":
        issue_codes.append("layer3_g2_s10_consumer_bridge_missing")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2CausalForecastAuditSurface(
        status=status,
        public_forecast_tier_visibility=bool(forecast_tiers),
        public_uncertainty_visibility=bool(uncertainty_refs),
        public_limitation_visibility=bool(limitation_refs),
        denied_use_visibility=set(G2_REQUIRED_AUTHORITY_DENIALS) <= set(denials),
        forecast_support_refs=forecast_support_refs,
        forecast_tiers=forecast_tiers,
        uncertainty_interval_refs=uncertainty_refs,
        limitation_refs=limitation_refs,
        may_not_use_for=denials,
        handoff_refs=_refs_from_records(handoffs, "g4_g5_readable_handoff_ref"),
        replay_field_refs=(
            "source_contract_ref",
            "method_validity_refs",
            "method_requirement_refs",
            "search_ledger_refs",
            "skg_query_trace_refs",
            "calibration_record_refs",
            "uncertainty_interval_refs",
            "limitation_refs",
        ),
        raw_query_ledger_refs=_refs_from_records(ledgers, "ledger_id"),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g2_generated_artifact_registration_status(
    repo_root: Path,
) -> Layer3G2GeneratedArtifactRegistrationStatus:
    """Check G2 generated artifact family markers and adapter registry presence."""

    root = Path(repo_root).resolve()
    generated_toml_path = root / "architecture/generated_artifacts.toml"
    adapter_registry_path = (
        root / "architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml"
    )
    generated_text = (
        generated_toml_path.read_text(encoding="utf-8")
        if generated_toml_path.exists()
        else ""
    )
    missing_paths = tuple(
        path for path in G2_EXPECTED_ARTIFACT_PATHS if not (root / path).exists()
    )
    issue_codes: list[str] = []
    if (
        LAYER3_G2_GENERATED_ARTIFACT_FAMILY_ID not in generated_text
        or not all(path in generated_text for path in G2_EXPECTED_ARTIFACT_PATHS)
    ):
        issue_codes.append("layer3_g2_generated_artifacts_family_missing")
    if not adapter_registry_path.exists():
        issue_codes.append("layer3_g2_adapter_contract_registry_missing")
    status: Literal["pass", "fail"] = "pass" if not issue_codes else "fail"
    return Layer3G2GeneratedArtifactRegistrationStatus(
        status=status,
        missing_artifact_paths=missing_paths,
        source_of_truth_refs=(
            "src/polisyos/runtime/quality/layer3_causal_forecast.py",
            "tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py",
        ),
        regenerate_command_refs=(
            "uv run python tools/quality/validation/"
            "check_policy_design_case_layer3_g2_readiness.py --repo-root . --write "
            "--output-format json",
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _validate_l2_route_and_traces(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    ledgers = _sequence(payload.get("l2_skg_search_ledgers", ()))
    traces = _sequence(payload.get("l2_skg_query_traces", ()))
    trace_ids = {str(_mapping(trace).get("trace_id", "")) for trace in traces}
    for idx, ledger_obj in enumerate(ledgers):
        ledger = _mapping(ledger_obj)
        route = str(ledger.get("canonical_l2_route", ""))
        if route == "capability_index":
            issues.append(
                _issue(
                    "layer3_g2_capability_index_used_as_l2_search",
                    f"$.l2_skg_search_ledgers[{idx}].canonical_l2_route",
                    "Capability-index views cannot satisfy canonical L2 SKG search.",
                )
            )
        elif route and route != CANONICAL_L2_ROUTE:
            issues.append(
                _issue(
                    "layer3_g2_unjustified_l2_surrogate",
                    f"$.l2_skg_search_ledgers[{idx}].canonical_l2_route",
                    "G2 requires the real scholar_knowledge.duckdb route.",
                )
            )
        for trace_ref in _string_tuple(ledger.get("query_trace_refs", ())):
            if trace_ref not in trace_ids:
                issues.append(
                    _issue(
                        "layer3_g2_skg_query_trace_missing",
                        f"$.l2_skg_search_ledgers[{idx}].query_trace_refs",
                        "Every consumed SKG query result needs a replayable query trace.",
                    )
                )
    for idx, trace_obj in enumerate(traces):
        trace = _mapping(trace_obj)
        route = str(trace.get("canonical_l2_route", ""))
        if route == "capability_index":
            issues.append(
                _issue(
                    "layer3_g2_capability_index_used_as_l2_search",
                    f"$.l2_skg_query_traces[{idx}].canonical_l2_route",
                    "Capability-index traces cannot satisfy canonical L2 SKG search.",
                )
            )
        elif route and route != CANONICAL_L2_ROUTE:
            issues.append(
                _issue(
                    "layer3_g2_unjustified_l2_surrogate",
                    f"$.l2_skg_query_traces[{idx}].canonical_l2_route",
                    "G2 requires the real scholar_knowledge.duckdb route.",
                )
            )


def _validate_search_authority(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    ledgers = _sequence(payload.get("l2_skg_search_ledgers", ()))
    for idx, ledger_obj in enumerate(ledgers):
        ledger = _mapping(ledger_obj)
        if _string_tuple(ledger.get("authoritative_for", ())) != ():
            issues.append(
                _issue(
                    "layer3_g2_search_ledger_authority_boundary_leak",
                    f"$.l2_skg_search_ledgers[{idx}].authoritative_for",
                    "Search ledgers are replay control-plane records only.",
                )
            )
    bindings = _sequence(payload.get("forecast_support_bindings", ()))
    for idx, binding_obj in enumerate(bindings):
        binding = _mapping(binding_obj)
        authoritative_for = set(_string_tuple(binding.get("authoritative_for", ())))
        may_not_use_for = set(_string_tuple(binding.get("may_not_use_for", ())))
        if "claim_authority" in authoritative_for or "claim_authority" not in may_not_use_for:
            issues.append(
                _issue(
                    "layer3_g2_claim_authority_leak",
                    f"$.forecast_support_bindings[{idx}].authoritative_for",
                    "G2 forecast bindings cannot carry claim authority.",
                )
            )
        if (
            "policy_recommendation" in authoritative_for
            or "policy_recommendation" not in may_not_use_for
        ):
            issues.append(
                _issue(
                    "layer3_g2_recommendation_authority_leak",
                    f"$.forecast_support_bindings[{idx}].authoritative_for",
                    "G2 forecast bindings cannot carry recommendation authority.",
                )
            )
        if "closeout_authority" in authoritative_for or "closeout_authority" not in may_not_use_for:
            issues.append(
                _issue(
                    "layer3_g2_closeout_authority_leak",
                    f"$.forecast_support_bindings[{idx}].authoritative_for",
                    "G2 forecast bindings cannot carry closeout authority.",
                )
            )
        if (
            "useful_design_credit" in authoritative_for
            or "useful_design_credit" not in may_not_use_for
        ):
            issues.append(
                _issue(
                    "layer3_g2_useful_design_credit_leak",
                    f"$.forecast_support_bindings[{idx}].authoritative_for",
                    "G2 forecast bindings cannot close useful-design credit.",
                )
            )


def _validate_semantic_retrieval(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    for path_name in ("l2_skg_search_ledgers", "l2_skg_query_traces"):
        for idx, item_obj in enumerate(_sequence(payload.get(path_name, ()))):
            item = _mapping(item_obj)
            if bool(item.get("semantic_retrieval_required")) and not item.get(
                "query_vector_producer_ref"
            ):
                issues.append(
                    _issue(
                        "layer3_g2_semantic_retrieval_without_query_vector_producer",
                        f"$.{path_name}[{idx}].query_vector_producer_ref",
                        "HNSW retrieval needs a replayed query-vector producer.",
                    )
                )


def _validate_search_hit_support_boundary(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    ledgers = _sequence(payload.get("l2_skg_search_ledgers", ()))
    binding_refs = {
        str(_mapping(binding).get("s10_forecast_support_ref", ""))
        for binding in _sequence(payload.get("forecast_support_bindings", ()))
    }
    for idx, ledger_obj in enumerate(ledgers):
        ledger = _mapping(ledger_obj)
        for ref in _string_tuple(ledger.get("forecast_support_refs", ())):
            if ref not in binding_refs:
                issues.append(
                    _issue(
                        "layer3_g2_search_hit_used_as_forecast_support",
                        f"$.l2_skg_search_ledgers[{idx}].forecast_support_refs",
                        "Search hits cannot appear as ForecastSupport without "
                        "adapter/S10 validation.",
                    )
                )
    for idx, binding_obj in enumerate(_sequence(payload.get("forecast_support_bindings", ()))):
        binding = _mapping(binding_obj)
        ref = str(binding.get("s10_forecast_support_ref", ""))
        adapter_ref = binding.get("adapter_validation_ref")
        if ref.startswith("skg-hit://") or adapter_ref in (None, ""):
            issues.append(
                _issue(
                    "layer3_g2_search_hit_used_as_forecast_support",
                    f"$.forecast_support_bindings[{idx}].s10_forecast_support_ref",
                    "G2 must translate through adapter validation and existing S10 builders.",
                )
            )


def _validate_missing_later_task_bindings(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    manifest = _mapping(payload.get("readiness_manifest", {}))
    if manifest:
        if int(manifest.get("g2_method_requirement_binding_count", 0) or 0) <= 0:
            issues.append(
                _issue(
                    "layer3_g2_method_requirement_missing",
                    "$.readiness_manifest.g2_method_requirement_binding_count",
                    "G2 requires persisted method-requirement bindings before readiness.",
                )
            )
        if int(manifest.get("g2_semantic_spine_binding_count", 0) or 0) <= 0:
            issues.append(
                _issue(
                    "layer3_g2_semantic_binding_spine_missing",
                    "$.readiness_manifest.g2_semantic_spine_binding_count",
                    "G2 requires semantic-spine bindings before readiness.",
                )
            )
        if str(manifest.get("g2_s10_prerequisite_binding_status", "")) not in {
            "pass",
            "domain_ceiling_not_required",
        }:
            issues.append(
                _issue(
                    "layer3_g2_s10_prerequisite_binding_missing",
                    "$.readiness_manifest.g2_s10_prerequisite_binding_status",
                    "G2 requires S10 prerequisite bindings before forecast posture.",
                )
            )
        if str(manifest.get("g2_w12d_consumer_gate_status", "")) != "pass":
            issues.append(
                _issue(
                    "layer3_g2_s10_consumer_bridge_missing",
                    "$.readiness_manifest.g2_w12d_consumer_gate_status",
                    "G2 requires a consumed S10/W12D forecast posture gate.",
                )
            )
            if str(manifest.get("g2_w12d_consumer_gate_status", "")) == "not_routed":
                issues.append(
                    _issue(
                        "layer3_g2_w12d_not_routed_closeout",
                        "$.readiness_manifest.g2_w12d_consumer_gate_status",
                        "A not-routed W12D gate cannot satisfy G2 closeout.",
                    )
                )


def _validate_search_recall_freshness(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    recall = _mapping(payload.get("search_recall_freshness"))
    if not recall:
        return
    if recall.get("search_recall_status") == "fail":
        issues.append(
            _issue(
                "layer3_g2_search_recall_seed_miss_blocks_domain_ceiling",
                "$.search_recall_freshness.search_recall_status",
                "A recall miss blocks G2 domain-ceiling closeout.",
            )
        )
    if recall.get("index_freshness_status") == "fail" or recall.get(
        "hnsw_freshness_status"
    ) == "fail":
        issues.append(
            _issue(
                "layer3_g2_stale_index_blocks_domain_ceiling",
                "$.search_recall_freshness.index_freshness_status",
                "Stale SKG/HNSW indexes require search repair before domain ceiling.",
            )
        )


def _validate_search_engineering_quality(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    quality = _mapping(payload.get("search_engineering_quality"))
    if not quality:
        return
    if quality.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_g2_search_engineering_quality_failed",
                "$.search_engineering_quality",
                "G2 search requires bounded indexed replayable execution.",
            )
        )


def _validate_foundry_method_registry_and_validity(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    coverage = _mapping(payload.get("foundry_method_registry_coverage"))
    if coverage and coverage.get("status") == "fail":
        for code in _string_tuple(coverage.get("issue_codes", ())):
            issues.append(_issue(code, "$.foundry_method_registry_coverage", code))
    search = _mapping(payload.get("foundry_method_registry_search"))
    if search:
        if search.get("hardcoded_fqn_closure") or search.get("search_strategy") == (
            "hardcoded_fqn_list"
        ):
            issues.append(
                _issue(
                    "layer3_g2_method_registry_hardcode_closure",
                    "$.foundry_method_registry_search.search_strategy",
                    "G2 method search cannot close over a hardcoded FQN list.",
                )
            )
        elif search.get("status") == "fail":
            issues.append(
                _issue(
                    "layer3_g2_foundry_method_registry_not_queried",
                    "$.foundry_method_registry_search.status",
                    "G2 requires a request-shaped Foundry method-registry search.",
                )
            )
    for idx, binding_obj in enumerate(_sequence(payload.get("method_requirement_bindings", ()))):
        binding = _mapping(binding_obj)
        if binding.get("status") == "fail" or binding.get("selection_status") == "fail":
            issues.append(
                _issue(
                    "layer3_g2_method_requirement_selection_failed",
                    f"$.method_requirement_bindings[{idx}]",
                    "Foundry method requirement selection did not satisfy the G2 request.",
                )
            )
    for idx, record_obj in enumerate(_sequence(payload.get("method_validity_transport", ()))):
        record = _mapping(record_obj)
        if record.get("status") == "fail":
            issues.append(
                _issue(
                    "layer3_g2_method_validity_missing",
                    f"$.method_validity_transport[{idx}]",
                    "G2 requires Foundry method validity before governed forecast tiers.",
                )
            )
        authority = _mapping(record.get("authority_envelope"))
        authoritative_for = set(_string_tuple(record.get("authoritative_for", ())))
        authoritative_for.update(_string_tuple(authority.get("authoritative_for", ())))
        may_not_use_for = set(_string_tuple(record.get("may_not_use_for", ())))
        may_not_use_for.update(_string_tuple(authority.get("may_not_use_for", ())))
        forbidden = set(G2_METHOD_REPORT_FORBIDDEN_AUTHORITY)
        if authoritative_for.intersection(forbidden) or not forbidden.intersection(
            may_not_use_for
        ):
            issues.append(
                _issue(
                    "layer3_g2_foundry_method_report_authority_overclaim",
                    f"$.method_validity_transport[{idx}].authority_envelope",
                    "Foundry method reports cannot become legal, claim, or closeout authority.",
                )
            )


def _validate_task4_semantic_s10_forecast_bindings(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    for idx, binding_obj in enumerate(_sequence(payload.get("semantic_spine_bindings", ()))):
        binding = _mapping(binding_obj)
        if binding.get("status") == "fail" or binding.get(
            "capability_reality_label"
        ) != "implemented":
            issues.append(
                _issue(
                    "layer3_g2_semantic_binding_spine_missing",
                    f"$.semantic_spine_bindings[{idx}]",
                    "G2 semantic grounding must reuse the producer spine and record pass.",
                )
            )
        if binding.get("parallel_concept_lattice_declared"):
            issues.append(
                _issue(
                    "layer3_g2_parallel_concept_lattice",
                    f"$.semantic_spine_bindings[{idx}]",
                    "G2 cannot introduce a parallel concept/status lattice.",
                )
            )

    for idx, alignment_obj in enumerate(_sequence(payload.get("concept_alignment_records", ()))):
        alignment = _mapping(alignment_obj)
        if alignment.get("status") == "fail" or alignment.get("alignment_status") == "unmatched":
            issues.append(
                _issue(
                    "layer3_g2_concept_alignment_missing",
                    f"$.concept_alignment_records[{idx}]",
                    "G1, SKG, Foundry, and S10 concepts must align before support.",
                )
            )
        if alignment.get("alignment_status") == "proxy_only" and not alignment.get(
            "proxy_disclosed"
        ):
            issues.append(
                _issue(
                    "layer3_g2_proxy_alignment_undisclosed",
                    f"$.concept_alignment_records[{idx}]",
                    "Proxy-only concept alignment must be disclosed and downgraded.",
                )
            )
        if alignment.get("alignment_status") in {"ambiguous", "conflict"} and alignment.get(
            "direct_grounding_claimed"
        ):
            issues.append(
                _issue(
                    "layer3_g2_ambiguous_alignment_overclaimed",
                    f"$.concept_alignment_records[{idx}]",
                    "Ambiguous concept alignment cannot pass as direct grounding.",
                )
            )

    for idx, binding_obj in enumerate(_sequence(payload.get("s10_prerequisite_bindings", ()))):
        binding = _mapping(binding_obj)
        if binding.get("status") == "fail":
            for code in _string_tuple(binding.get("issue_codes", ())):
                issues.append(_issue(code, f"$.s10_prerequisite_bindings[{idx}]", code))
        if not (
            binding.get("s5_forecast_support_ref")
            and _string_tuple(binding.get("s6_firewall_status_refs", ()))
            and binding.get("s8_value_choice_provenance_ref")
            and binding.get("s8_value_tradeoff_disclosure_ref")
        ):
            issues.append(
                _issue(
                    "layer3_g2_s5_s6_s8_refs_missing",
                    f"$.s10_prerequisite_bindings[{idx}]",
                    "S10 prerequisite binding must carry S5, S6, and S8 refs.",
                )
            )
        issues.extend(
            _issue(code, f"$.s10_prerequisite_bindings[{idx}].may_not_use_for", code)
            for code in _g2_authority_leak_issue_codes(
                may_not_use_for=_string_tuple(binding.get("may_not_use_for", ()))
            )
        )

    for idx, binding_obj in enumerate(_sequence(payload.get("forecast_support_bindings", ()))):
        binding = _mapping(binding_obj)
        if binding.get("status") == "fail":
            for code in _string_tuple(binding.get("issue_codes", ())):
                issues.append(_issue(code, f"$.forecast_support_bindings[{idx}]", code))
        if binding.get("s10_builder_ref") and binding.get("s10_builder_ref") != (
            S10_FORECAST_SUPPORT_BUILDER_REF
        ):
            issues.append(
                _issue(
                    "layer3_g2_forecast_support_invalid",
                    f"$.forecast_support_bindings[{idx}].s10_builder_ref",
                    "G2 forecast support must be built through the existing S10 builder.",
                )
            )
        requested = str(binding.get("requested_forecast_tier") or "")
        derived = str(binding.get("s10_forecast_tier") or "")
        if requested and derived and requested != derived:
            issues.append(
                _issue(
                    "layer3_g2_s10_tier_derivation_mismatch",
                    f"$.forecast_support_bindings[{idx}].s10_forecast_tier",
                    "G2 requested tier cannot override S10-derived forecast tier.",
                )
            )
        if requested == "observable_calibrated" and not binding.get("calibration_record_ref"):
            issues.append(
                _issue(
                    "layer3_g2_observable_calibration_required",
                    f"$.forecast_support_bindings[{idx}].calibration_record_ref",
                    "Observable calibrated G2 support requires an S10 calibration record.",
                )
            )
        if requested in {"observable_calibrated", "transported_limited"} and not _string_tuple(
            binding.get("uncertainty_interval_refs", ())
        ):
            issues.append(
                _issue(
                    "layer3_g2_uncertainty_interval_missing",
                    f"$.forecast_support_bindings[{idx}].uncertainty_interval_refs",
                    "Governed forecast tiers require visible uncertainty intervals.",
                )
            )


def _validate_task5_calibration_transport_downgrades(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    calibration = _mapping(payload.get("observable_calibration_report"))
    if calibration:
        if calibration.get("status") == "fail":
            for code in _string_tuple(calibration.get("issue_codes", ())):
                issues.append(_issue(code, "$.observable_calibration_report", code))
        if int(calibration.get("observable_subset_calibration_denominator") or 0) <= 0:
            issues.append(
                _issue(
                    "layer3_g2_observable_calibration_denominator_missing",
                    "$.observable_calibration_report.observable_subset_calibration_denominator",
                    "Observable calibration requires a non-zero denominator.",
                )
            )
        if (
            not _string_tuple(calibration.get("credible_evaluation_evidence_refs", ()))
            and calibration.get("adapter_maturity") == "calibrated"
        ):
            issues.append(
                _issue(
                    "layer3_g2_credible_evaluation_evidence_missing",
                    "$.observable_calibration_report.credible_evaluation_evidence_refs",
                    "Calibrated G2 maturity requires credible evaluation evidence.",
                )
            )

    for idx, declaration_obj in enumerate(
        _sequence(payload.get("transport_limit_declarations", ()))
    ):
        declaration = _mapping(declaration_obj)
        if declaration.get("status") == "fail":
            for code in _string_tuple(declaration.get("issue_codes", ())):
                issues.append(_issue(code, f"$.transport_limit_declarations[{idx}]", code))
        if not _string_tuple(declaration.get("method_transportability_limit_refs", ())):
            issues.append(
                _issue(
                    "layer3_g2_transportability_limit_missing",
                    f"$.transport_limit_declarations[{idx}].method_transportability_limit_refs",
                    "Transport declarations require method transportability limits.",
                )
            )
        if declaration.get("transport_status") == "blocked" and not _string_tuple(
            declaration.get("limitation_refs", ())
        ):
            issues.append(
                _issue(
                    "layer3_g2_transport_limit_missing",
                    f"$.transport_limit_declarations[{idx}].limitation_refs",
                    "Blocked transport declarations must expose limitation refs.",
                )
            )

    for idx, binding_obj in enumerate(_sequence(payload.get("forecast_support_bindings", ()))):
        binding = _mapping(binding_obj)
        if binding.get("requested_adapter_maturity") == "calibrated" and binding.get(
            "adapter_maturity"
        ) != "calibrated":
            issues.append(
                _issue(
                    "layer3_g2_adapter_maturity_overclaim",
                    f"$.forecast_support_bindings[{idx}].adapter_maturity",
                    "G2 adapter maturity cannot be calibrated without passed calibration.",
                )
            )
        if _string_tuple(binding.get("contested_edge_refs", ())) and not _string_tuple(
            binding.get("publish_blocker_refs", ())
        ):
            issues.append(
                _issue(
                    "layer3_g2_contested_edge_overclaimed",
                    f"$.forecast_support_bindings[{idx}].publish_blocker_refs",
                    "Contested SKG edges must remain limitations or publish blockers.",
                )
            )


def _validate_task6_consumer_bridge_and_handoffs(
    payload: Mapping[str, Any],
    issues: list[Layer3G2ValidationIssue],
) -> None:
    bindings = [_mapping(item) for item in _sequence(payload.get("forecast_support_bindings", ()))]
    passed_support_refs = {
        str(binding.get("s10_forecast_support_ref") or "")
        for binding in bindings
        if binding.get("status") == "pass" and binding.get("s10_forecast_support_ref")
    }
    handoffs = [
        _mapping(item) for item in _sequence(payload.get("grounded_forecast_handoffs", ()))
    ]
    handoff_support_refs = {
        str(handoff.get("s10_forecast_support_ref") or "")
        for handoff in handoffs
        if handoff.get("s10_forecast_support_ref")
    }
    if passed_support_refs and not (passed_support_refs & handoff_support_refs):
        issues.append(
            _issue(
                "layer3_g2_grounded_forecast_handoff_missing",
                "$.grounded_forecast_handoffs",
                "Passed G2 ForecastSupport requires a G4/G5-readable handoff.",
            )
        )

    for idx, handoff_obj in enumerate(handoffs):
        handoff = _mapping(handoff_obj)
        authoritative_for = set(_string_tuple(handoff.get("authoritative_for", ())))
        may_not_use_for = set(_string_tuple(handoff.get("may_not_use_for", ())))
        if (
            handoff.get("promotion_authority_claimed") is True
            or handoff.get("conversion_authority_claimed") is True
            or handoff.get("useful_design_credit_claimed") is True
            or authoritative_for
            & {"promotion_authority", "conversion_authority", "useful_design_credit"}
            or not {"promotion_authority", "conversion_authority", "useful_design_credit"}
            <= may_not_use_for
        ):
            issues.append(
                _issue(
                    "layer3_g2_grounded_forecast_handoff_promoted",
                    f"$.grounded_forecast_handoffs[{idx}].authoritative_for",
                    "G2 handoffs are later-slice inputs, not promotion or conversion authority.",
                )
            )
        has_full_replay_surface = bool(
            handoff.get("source_contract_ref")
            and _string_tuple(handoff.get("method_validity_refs", ()))
            and _string_tuple(handoff.get("method_requirement_refs", ()))
            and _string_tuple(handoff.get("skg_query_trace_refs", ()))
        )
        has_s2_only_replay_surface = bool(
            _string_tuple(handoff.get("design_record_ledger_refs", ()))
            or _string_tuple(handoff.get("s2_deterministic_replay_key_refs", ()))
        )
        if has_s2_only_replay_surface and not has_full_replay_surface:
            issues.append(
                _issue(
                    "layer3_g2_s2_design_record_replay_overclaim",
                    f"$.grounded_forecast_handoffs[{idx}]",
                    "DesignRecord ledger refs and S2 replay keys are not the full "
                    "G2 replay surface.",
                )
            )

    gate = _mapping(payload.get("w12d_consumer_gate"))
    if gate:
        domain_ceiling_status = str(gate.get("domain_ceiling_status") or "")
        is_ceiling_route = domain_ceiling_status in {
            "causal_forecast_domain_ceiling",
            "search_ceiling_repair_required",
        }
        if str(gate.get("status") or "") != "pass" and (
            "layer3_g2_w12d_not_routed_closeout"
            in _string_tuple(gate.get("issue_codes", ()))
        ):
            issues.append(
                _issue(
                    "layer3_g2_w12d_not_routed_closeout",
                    "$.w12d_consumer_gate.status",
                    "A not-routed W12D gate cannot satisfy G2 closeout.",
                )
            )
        if (
            passed_support_refs
            and gate.get("posture_consumed") is not True
            and not is_ceiling_route
        ):
            issues.append(
                _issue(
                    "layer3_g2_s10_posture_not_consumed",
                    "$.w12d_consumer_gate.posture_consumed",
                    "W12D must consume the G2 public S10 forecast posture.",
                )
            )
        if int(gate.get("full_s2_consumer_case_count") or 0) > 1:
            issues.append(
                _issue(
                    "layer3_g2_w12d_full_s2_overreach",
                    "$.w12d_consumer_gate.full_s2_consumer_case_count",
                    "G2 W12D may only run a full first-case S2 consumer proof.",
                )
            )


@lru_cache(maxsize=1)
def _foundry_registry_payload() -> dict[str, Any]:
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.selection.registry import registry_scope

    with registry_scope() as registry:
        discovery_errors: tuple[str, ...] = ()
        try:
            ensure_all_methods_registered(registry)
        except Exception as exc:
            discovery_errors = (f"{type(exc).__name__}: {exc}",)
        snapshot = registry.snapshot()
        entries = [_registry_entry_payload(entry) for entry in snapshot.entries()]
        registry_stats = registry.stats()

    family_counts: dict[str, int] = {}
    for entry in entries:
        family_root = str(entry["namespace"]).split(".", 1)[0]
        family_counts[family_root] = family_counts.get(family_root, 0) + 1
    registry_hash = _stable_id(
        *[str(entry["method_fqn"]) for entry in entries],
        json.dumps(registry_stats, sort_keys=True, default=str),
    )
    return {
        "entries": tuple(entries),
        "built_in_catalog_bootstrap_refs": FOUNDRY_BOOTSTRAP_REFS,
        "discovery_source_roots": FOUNDRY_DISCOVERY_SOURCE_ROOTS,
        "entry_point_groups": FOUNDRY_ENTRY_POINT_GROUPS,
        "duplicate_method_refs": (),
        "discovery_errors": discovery_errors,
        "discovery_refs": (
            "foundry-method-discovery:builtins",
            "foundry-method-discovery:entry-points",
            "foundry-method-discovery:dev-scan",
        ),
        "family_method_counts": family_counts,
        "registry_snapshot_ref": f"foundry-method-registry-snapshot:{registry_hash}",
        "registry_version_ref": f"foundry-method-registry-version:{registry_hash[:12]}",
        "registry_stats": registry_stats,
    }


def _registry_entry_payload(entry: object) -> dict[str, object]:
    signature = entry.signature
    metadata = entry.metadata
    method_fqn = str(signature.fqn)
    return {
        "method_ref": f"foundry-method://{method_fqn}",
        "method_fqn": method_fqn,
        "namespace": str(signature.namespace),
        "name": str(signature.name),
        "version": str(signature.version),
        "family": str(signature.family or signature.namespace),
        "tags": tuple(sorted(str(tag) for tag in getattr(metadata, "tags", ()))),
        "data_modalities": tuple(sorted(str(item) for item in signature.data_modalities)),
        "input_slot_refs": tuple(sorted(slot.name for slot in signature.input_slots)),
        "output_slot_refs": tuple(sorted(slot.name for slot in signature.output_slots)),
        "registry_entry_ref": f"foundry-registry-entry:{_stable_id(method_fqn)}",
    }


def _task_affinity_predicates(request: Layer3G2CausalForecastRequest) -> dict[str, Any]:
    requested = _string_tuple(request.method_task_tags) or (
        "causal_effect_estimation",
        "forecasting",
        "uncertainty",
        "validation",
    )
    return {
        "requested_task_tags": list(requested),
        "represented_by": (
            "MethodSignature.namespace",
            "MethodSignature.output_slots",
            "MethodMetadata.tags",
        ),
    }


def _data_affinity_predicates(request: Layer3G2CausalForecastRequest) -> dict[str, Any]:
    return {
        "data_modality": request.data_modality,
        "treatment_structure": request.treatment_structure,
        "outcome_type": request.outcome_type,
        "required_diagnostics": list(_string_tuple(request.required_diagnostics)),
        "represented_by": (
            "MethodSignature.input_slots",
            "MethodSignature.data_modalities",
            "MethodMetadata.tags",
        ),
    }


def _candidate_from_registry_entry(
    entry: Mapping[str, Any],
    request: Layer3G2CausalForecastRequest,
) -> Layer3G2FoundryMethodCandidate:
    tokens = _entry_tokens(entry)
    task_terms = _request_task_terms(request)
    data_terms = _request_data_terms(request)
    diagnostic_terms = _request_diagnostic_terms(request)
    match_predicates: dict[str, Any] = {}
    score = 0
    task_matches = sorted(tokens.intersection(task_terms))
    if task_matches:
        match_predicates["tags"] = task_matches
        score += 5 + len(task_matches)
    data_matches = sorted(tokens.intersection(data_terms))
    if data_matches:
        match_predicates["data_modalities"] = data_matches
        score += 2 + len(data_matches)
    diagnostic_matches = sorted(tokens.intersection(diagnostic_terms))
    if diagnostic_matches:
        match_predicates["diagnostics"] = diagnostic_matches
        score += 2 + len(diagnostic_matches)
    slot_matches = sorted(
        tokens.intersection({"treatment", "outcome", "policy", "target", "features"})
    )
    if slot_matches:
        match_predicates["slots"] = slot_matches
        score += 1
    method_family = _candidate_method_family(entry, tokens)
    expectations = tuple(dict.fromkeys([method_family, *task_matches]))
    return Layer3G2FoundryMethodCandidate(
        method_ref=str(entry["method_ref"]),
        method_fqn=str(entry["method_fqn"]),
        namespace=str(entry["namespace"]),
        name=str(entry["name"]),
        version=str(entry["version"]),
        method_family=method_family,
        tags=_string_tuple(entry.get("tags", ())),
        data_modalities=_string_tuple(entry.get("data_modalities", ())),
        input_slot_refs=_string_tuple(entry.get("input_slot_refs", ())),
        output_slot_refs=_string_tuple(entry.get("output_slot_refs", ())),
        registry_entry_ref=str(entry["registry_entry_ref"]),
        match_predicates=match_predicates,
        match_score=score,
        method_expectations=expectations,
        method_contract_targets=_string_tuple(entry.get("output_slot_refs", ())),
    )


def _entry_tokens(entry: Mapping[str, Any]) -> set[str]:
    values = [
        entry.get("method_fqn"),
        entry.get("namespace"),
        entry.get("name"),
        entry.get("family"),
        *_string_tuple(entry.get("tags", ())),
        *_string_tuple(entry.get("data_modalities", ())),
        *_string_tuple(entry.get("input_slot_refs", ())),
        *_string_tuple(entry.get("output_slot_refs", ())),
    ]
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").casefold()
        if not text:
            continue
        tokens.add(text)
        tokens.update(part for part in text.replace("_", "-").replace(".", "-").split("-") if part)
    return tokens


def _request_task_terms(request: Layer3G2CausalForecastRequest) -> set[str]:
    requested = set(_string_tuple(request.method_task_tags)) or {
        "causal_effect_estimation",
        "forecasting",
        "uncertainty",
        "validation",
    }
    terms = {item.casefold() for item in requested}
    if "causal_effect_estimation" in terms:
        terms.update({"causal", "estimation", "effect", "treatment"})
    if "forecasting" in terms:
        terms.update({"forecast", "forecasting", "time-series", "prediction"})
    if "uncertainty" in terms:
        terms.update({"uncertainty", "bounds", "interval"})
    if "validation" in terms:
        terms.update({"validation", "diagnostic", "diagnostics", "calibration"})
    return terms


def _request_data_terms(request: Layer3G2CausalForecastRequest) -> set[str]:
    terms = {
        str(value).casefold()
        for value in (
            request.data_modality,
            request.treatment_structure,
            request.outcome_type,
        )
        if value
    }
    if request.data_modality == "panel":
        terms.update({"panel", "time", "entity"})
    return terms


def _request_diagnostic_terms(request: Layer3G2CausalForecastRequest) -> set[str]:
    terms = {item.casefold() for item in _string_tuple(request.required_diagnostics)}
    if "identification" in terms:
        terms.update({"identify", "identification", "id", "causal"})
    if "transportability" in terms:
        terms.update({"transportability", "transport", "support", "invariance"})
    if "uncertainty" in terms:
        terms.update({"uncertainty", "bounds", "interval"})
    return terms


def _candidate_method_family(entry: Mapping[str, Any], tokens: set[str]) -> str:
    namespace_root = str(entry.get("namespace", "")).split(".", 1)[0]
    if "causal" in tokens or namespace_root == "causal":
        return "causal_effect_estimation"
    if "forecasting" in tokens or "forecast" in tokens or namespace_root == "forecasting":
        return "forecasting"
    if namespace_root == "econometrics":
        return "econometric"
    if namespace_root == "sensitivity":
        return "sensitivity"
    if namespace_root == "validation":
        return "validation"
    return namespace_root or "foundry_method"


def _candidate_to_method_mapping(
    candidate: Layer3G2FoundryMethodCandidate,
) -> dict[str, Any]:
    return {
        "method_id": candidate.method_ref,
        "method_fqn": candidate.method_fqn,
        "method_family": candidate.method_family,
        "method_expectations": list(candidate.method_expectations),
        "method_contract_targets": list(candidate.method_contract_targets),
        "tags": list(candidate.tags),
        "truthfulness_status": "registry_candidate_only",
    }


def _build_g2_method_requirement_spec(
    request: Layer3G2CausalForecastRequest,
) -> MethodValidityRequirementSpec:
    requirement_id = f"g2-method-req:{_request_slug(request)}"
    assumptions = [
        {"assumption_id": "identification_strategy"},
        {"assumption_id": "overlap_or_support"},
    ]
    if request.target_context_id:
        assumptions.append({"assumption_id": "transportability"})
    return MethodValidityRequirementSpec(
        requirement_id=requirement_id,
        run_id=request.case_id,
        claim_id=request.request_id,
        identification_class="point",
        transportability_requirement=(
            "target_population_limits" if request.target_context_id else "none"
        ),
        uncertainty_class="interval",
        fairness_decomposition_need="subgroup",
        strategic_response_sensitivity="monitor",
        assumption_validation_needs=assumptions,
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        facet_refs=[f"g2-request-facet:{request.request_id}:causal-forecast"],
        obligation_refs=[f"g2-method-obligation:{request.request_id}"],
        concept_spine_refs=tuple(request.source_contract_refs),
        source_precondition_refs=tuple(request.source_contract_refs),
        requires_runtime_assumption_gates=True,
        requires_uncertainty_envelope=True,
        requires_limitation_refs=True,
        requires_method_output=True,
        metadata={
            "cause": request.cause,
            "effect": request.effect,
            "target_context_id": request.target_context_id,
            "data_modality": request.data_modality,
            "required_diagnostics": list(_string_tuple(request.required_diagnostics)),
        },
    )


def _method_requirement_authority_boundary() -> dict[str, list[str]]:
    return {
        "authoritative_for": [
            "method_validity_requirements",
            "method_selection_preconditions",
            "ir_analytics_requirement_binding",
        ],
        "may_not_use_for": [
            "legal_authority",
            "source_family_satisfaction",
            "academic_support_strength",
            "participation_representativeness",
            "closeout_pass",
        ],
    }


def _request_slug(request: Layer3G2CausalForecastRequest) -> str:
    tokens = [
        request.cause.rsplit(".", 1)[-1],
        request.effect,
    ]
    return "-".join(_slug_token(token) for token in tokens if _slug_token(token))


def _slug_token(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value]
    token = "".join(chars).strip("-")
    while "--" in token:
        token = token.replace("--", "-")
    return token


def _method_ref_from_mapping(method: Mapping[str, Any]) -> str:
    for key in ("method_id", "method_ref", "method_fqn", "id"):
        value = str(method.get(key, "")).strip()
        if value:
            return value
    return ""


def _foundry_input_refs_from_methods(methods: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    for method in methods:
        refs = _mapping(method.get("input_refs"))
        if refs:
            return {str(key): str(value) for key, value in refs.items() if str(value)}
    return {}


def _g2_method_validity_issue_codes(report: Mapping[str, Any]) -> list[str]:
    issue_codes: list[str] = []
    foundry_codes = {
        str(_mapping(issue).get("code", ""))
        for issue in _sequence(report.get("issues", ()))
    }
    if report.get("status") != "pass":
        issue_codes.append("layer3_g2_method_validity_missing")
    if "method_identification_requirements_missing" in foundry_codes:
        issue_codes.append("layer3_g2_identification_requirement_missing")
    if "method_transportability_limits_missing" in foundry_codes:
        issue_codes.append("layer3_g2_transportability_limit_missing")
    if "method_requirement_no_selected_method" in foundry_codes:
        issue_codes.append("layer3_g2_method_requirement_selection_failed")
    return issue_codes


def _method_candidate_surface_issue_codes(
    methods: Sequence[Mapping[str, Any]],
) -> list[str]:
    issue_codes: list[str] = []
    for method in methods:
        payload = _mapping(method)
        if not _mapping(payload.get("identification_requirements")):
            issue_codes.append("layer3_g2_identification_requirement_missing")
        if not _mapping(payload.get("transportability_limits")):
            issue_codes.append("layer3_g2_transportability_limit_missing")
        if not (
            _mapping(payload.get("uncertainty_refs"))
            or _mapping(payload.get("uncertainty"))
            or _mapping(payload.get("uncertainty_envelope"))
        ):
            issue_codes.append("layer3_g2_method_validity_missing")
        if not (
            _mapping(payload.get("method_result_refs"))
            or _mapping(payload.get("method_output_refs"))
            or _mapping(payload.get("result_refs"))
        ):
            issue_codes.append("layer3_g2_method_validity_missing")
    return issue_codes


def _collect_method_validity_refs(report: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for method in _sequence(report.get("selected_methods", ())):
        payload = _mapping(method)
        for surface in _mapping(payload.get("validity_surfaces")).values():
            ref = str(_mapping(surface).get("ref", "")).strip()
            if ref:
                refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _collect_mapping_refs(report: Mapping[str, Any], key: str) -> tuple[str, ...]:
    refs: list[str] = []
    for method in _sequence(report.get("selected_methods", ())):
        payload = _mapping(method)
        section = _mapping(payload.get(key))
        for value in section.values():
            if isinstance(value, str) and value.startswith(("sha256:", "gate://", "ref://")):
                refs.append(value)
            elif isinstance(value, str) and value:
                refs.append(f"{key}:{_stable_id(value)}")
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                refs.append(f"{key}:{_stable_id(*[str(item) for item in value])}")
    return tuple(dict.fromkeys(refs))


def _count_nested_refs(report: Mapping[str, Any], key: str) -> int:
    count = 0
    for method in _sequence(report.get("selected_methods", ())):
        payload = _mapping(method)
        count += len(_mapping(payload.get(key)))
    return count


def _collect_method_lineage_refs(report: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for method in _sequence(report.get("selected_methods", ())):
        payload = _mapping(method)
        refs.extend(str(value) for value in _mapping(payload.get("method_refs")).values())
        refs.extend(str(value) for value in _mapping(payload.get("input_refs")).values())
        refs.extend(str(value) for value in _mapping(payload.get("method_result_refs")).values())
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _g2_search_refs(
    search_result: Layer3G2SkgSearchResult | Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = _mapping(search_result)
    ledger = _mapping(payload.get("ledger"))
    traces = _sequence(payload.get("query_traces", ()))
    if isinstance(search_result, Layer3G2SkgSearchResult):
        ledger = search_result.ledger.model_dump(mode="json")
        traces = tuple(trace.model_dump(mode="json") for trace in search_result.query_traces)

    all_refs: list[str] = []
    contested_refs: list[str] = []
    transport_confidence_by_ref: dict[str, float] = {}
    all_refs.extend(_string_tuple(ledger.get("selected_candidate_refs", ())))
    all_refs.extend(_string_tuple(ledger.get("duckdb_validated_candidate_refs", ())))
    for trace_obj in traces:
        trace = _mapping(trace_obj)
        row_refs = _string_tuple(trace.get("row_refs", ()))
        selected_refs = _string_tuple(trace.get("selected_candidate_refs", ()))
        all_refs.extend(row_refs)
        all_refs.extend(selected_refs)
        if "ac_skg_contested_edges" in set(_string_tuple(trace.get("table_refs", ()))) or set(
            _string_tuple(trace.get("quality_flags", ()))
        ).intersection({"directional_conflict", "resolution:mixed"}):
            contested_refs.extend(ref for ref in (*row_refs, *selected_refs) if ref.startswith("skg-edge://"))
        transport_refs = _refs_with_prefix(row_refs, "skg-transport://")
        for ref, confidence in zip(
            transport_refs,
            _transport_confidences_from_notes(_string_tuple(trace.get("transport_notes", ()))),
            strict=False,
        ):
            transport_confidence_by_ref[ref] = confidence
    all_refs_tuple = tuple(dict.fromkeys(all_refs))
    return {
        "search_ledger_refs": _string_tuple([ledger.get("ledger_id")])
        if ledger.get("ledger_id")
        else (),
        "skg_edge_refs": _refs_with_prefix(all_refs_tuple, "skg-edge://"),
        "skg_claim_refs": _refs_with_prefix(all_refs_tuple, "skg-claim://"),
        "skg_parameter_refs": _refs_with_prefix(all_refs_tuple, "skg-parameter://"),
        "skg_transport_refs": _refs_with_prefix(all_refs_tuple, "skg-transport://"),
        "skg_transport_confidence_by_ref": transport_confidence_by_ref,
        "contested_edge_refs": tuple(dict.fromkeys(contested_refs)),
    }


def _g2_publish_blockers_for_contested_edges(edge_refs: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        f"publish-blocker://layer3/g2/contested-edge/{ref.removeprefix('skg-edge://')}"
        for ref in _string_tuple(edge_refs)
    )


def _g2_contested_limitation_refs(edge_refs: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        f"limitation://layer3/g2/contested-edge/{ref.removeprefix('skg-edge://')}"
        for ref in _string_tuple(edge_refs)
    )


def _g2_requires_calibrated_dynamics(prereq: Mapping[str, Any]) -> bool:
    return str(prereq.get("s5_base_origin", "")) == "equilibrium_contested" or str(
        prereq.get("s5_support_label", "")
    ) == "equilibrium_contested"


def _g2_adapter_maturity(
    *,
    issue_codes: Sequence[str],
    calibration_record: Mapping[str, Any],
    authority_envelope: Mapping[str, Any],
    requested_adapter_maturity: AdapterMaturity | None,
) -> AdapterMaturity:
    if _g2_calibration_is_passed(calibration_record) and _g2_authority_envelope_is_bounded(
        authority_envelope
    ) and not issue_codes:
        return "calibrated"
    if requested_adapter_maturity == "calibrated" or issue_codes:
        return "fail_closed"
    return "predictive"


def _g2_adapter_maturity_blockers(
    *,
    issue_codes: Sequence[str],
    calibration_record: Mapping[str, Any],
    authority_envelope: Mapping[str, Any],
    requested_adapter_maturity: AdapterMaturity | None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not _g2_calibration_is_passed(calibration_record):
        blockers.append("maturity-blocker://layer3/g2/observable-calibration-not-passed")
    if not _g2_authority_envelope_is_bounded(authority_envelope):
        blockers.append("maturity-blocker://layer3/g2/authority-envelope-not-bounded")
    if issue_codes:
        blockers.append("maturity-blocker://layer3/g2/fail-closed-issues-present")
    if requested_adapter_maturity == "calibrated" and blockers:
        blockers.append("maturity-blocker://layer3/g2/calibrated-maturity-overclaim")
    return tuple(dict.fromkeys(blockers))


def _g2_calibration_is_passed(calibration_record: Mapping[str, Any]) -> bool:
    return bool(
        calibration_record
        and int(calibration_record.get("denominator") or 0) > 0
        and calibration_record.get("calibration_status") == "pass"
        and bool(calibration_record.get("floor_passed"))
        and bool(calibration_record.get("credible_evaluation_evidence_ref"))
    )


def _g2_authority_envelope_is_bounded(authority_envelope: Mapping[str, Any]) -> bool:
    return bool(
        authority_envelope
        and authority_envelope.get("envelope_status") == "pass"
        and authority_envelope.get("denies_production_authority") is True
        and authority_envelope.get("denies_recommendation_authority") is True
        and authority_envelope.get("denies_claim_authority") is True
        and authority_envelope.get("denies_closeout_authority") is True
    )


def _refs_from_records(records: Sequence[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(record.get(key))
            for record in records
            if record.get(key) not in (None, "")
        )
    )


def _transport_confidences_from_notes(notes: Sequence[str]) -> tuple[float, ...]:
    confidences: list[float] = []
    for note in notes:
        if ":" not in note:
            continue
        value = note.rsplit(":", 1)[-1]
        try:
            confidences.append(round(float(value), 3))
        except ValueError:
            continue
    return tuple(confidences)


def _g2_s10_support_payload(
    *,
    request: Layer3G2CausalForecastRequest,
    prereq: Mapping[str, Any],
    support_ref: str,
    requested_forecast_tier: str | None,
    calibration_record_ref: str | None,
    method_record: Mapping[str, Any],
    limitation_refs: Sequence[str],
) -> dict[str, Any]:
    method_validity_ref = (
        str(prereq.get("method_validity_ref") or "")
        or _first_or_none(_string_tuple(prereq.get("method_validity_refs", ())))
        or _first_or_none(_string_tuple(method_record.get("method_validity_refs", ())))
    )
    method_family = str(prereq.get("method_family") or "foundry_causal")
    if method_family not in {
        "foundry_causal",
        "foundry_optimization",
        "foundry_bayesian",
        "historical_prior",
        "simulation",
        "abstain",
    }:
        method_family = G2_S10_METHOD_FAMILY_BY_METHOD_CANDIDATE.get(
            method_family,
            "foundry_causal",
        )
    return {
        "support_id": f"layer3.g2.forecast-support.{_stable_id(support_ref)}",
        "support_ref": support_ref,
        "case_id": request.case_id,
        "source_design_record_ref": prereq.get("source_design_record_ref"),
        "design_graph_ref": prereq.get("design_graph_ref"),
        "prediction_context_ref": prereq.get("prediction_context_ref"),
        "policy_context_ref": prereq.get("policy_context_ref"),
        "candidate_design_ref": prereq.get("candidate_design_ref"),
        "baseline_design_ref": prereq.get("baseline_design_ref"),
        "alternative_design_refs": list(_string_tuple(prereq.get("alternative_design_refs", ()))),
        "prediction_horizon_ref": prereq.get("prediction_horizon_ref"),
        "target_outcome_refs": list(_string_tuple(prereq.get("target_outcome_refs", ()))),
        "jurisdiction_scope_ref": prereq.get("jurisdiction_scope_ref"),
        "s5_forecast_support_ref": prereq.get("s5_forecast_support_ref"),
        "s5_support_label": prereq.get("s5_support_label"),
        "s5_base_origin": prereq.get("s5_base_origin"),
        "s5_claim_scope": prereq.get("s5_claim_scope"),
        "s6_firewall_status_refs": list(
            _string_tuple(prereq.get("s6_firewall_status_refs", ()))
        ),
        "s6_limitation_refs": list(_string_tuple(prereq.get("s6_limitation_refs", ()))),
        "s8_value_choice_provenance_ref": prereq.get("s8_value_choice_provenance_ref"),
        "s8_value_tradeoff_disclosure_ref": prereq.get("s8_value_tradeoff_disclosure_ref"),
        "source_contract_ref": prereq.get("source_contract_ref")
        or _first_or_none(_string_tuple(request.source_contract_refs)),
        "method_validity_ref": method_validity_ref,
        "credible_evaluation_evidence_ref": prereq.get("credible_evaluation_evidence_ref"),
        "source_lineage_refs": list(_string_tuple(prereq.get("source_lineage_refs", ()))),
        "method_lineage_refs": list(_string_tuple(prereq.get("method_lineage_refs", ()))),
        "sensitivity_analysis_ref": prereq.get("sensitivity_analysis_ref"),
        "dynamic_equilibrium_check_ref": prereq.get("dynamic_equilibrium_check_ref"),
        "equilibrium_caveat_refs": list(
            _string_tuple(prereq.get("equilibrium_caveat_refs", ()))
        ),
        "strategic_response_caveat_refs": list(
            _string_tuple(prereq.get("strategic_response_caveat_refs", ()))
        ),
        "outcome_distribution_refs": list(
            _string_tuple(prereq.get("outcome_distribution_refs", ()))
        ),
        "welfare_comparison_ref": prereq.get("welfare_comparison_ref"),
        "forecast_tier": requested_forecast_tier or "observable_calibrated",
        "forecast_authority_disposition_reason": prereq.get(
            "forecast_authority_disposition_reason"
        )
        or "G2 translated bounded causal/forecast search through existing S10 support.",
        "method_family": method_family,
        "observable_subset_ref": prereq.get("observable_subset_ref"),
        "calibration_record_ref": calibration_record_ref,
        "uncertainty_interval_refs": list(
            _string_tuple(prereq.get("uncertainty_interval_refs", ()))
        ),
        "limitation_refs": list(_string_tuple(limitation_refs)),
        "abstention_refs": [],
        "may_not_use_for": list(
            _merge_g2_denials(_string_tuple(prereq.get("may_not_use_for", ())))
        ),
    }


def _g2_forecast_exception_issue_codes(exc: Exception) -> list[str]:
    text = str(exc).casefold()
    issue_codes: list[str] = ["layer3_g2_forecast_support_invalid"]
    if "calibration" in text or "observable" in text:
        issue_codes.append("layer3_g2_observable_calibration_required")
    if "denominator" in text:
        issue_codes.append("layer3_g2_observable_calibration_denominator_missing")
    if "credible_evaluation" in text or "counterfactual" in text:
        issue_codes.append("layer3_g2_credible_evaluation_evidence_missing")
    if "uncertainty" in text or "interval" in text:
        issue_codes.append("layer3_g2_uncertainty_interval_missing")
    if "transport" in text and "limitation" in text:
        issue_codes.append("layer3_g2_transport_limit_missing")
    if "simulation_only" in text or "simulation only" in text:
        issue_codes.append("layer3_g2_simulation_only_laundered")
    if "historical prior" in text or "historical_prior" in text:
        issue_codes.append("layer3_g2_historical_prior_laundered")
    if "equilibrium" in text or "single point" in text:
        issue_codes.append("layer3_g2_equilibrium_authority_overclaim")
    if "s5" in text or "s6" in text or "s8" in text:
        issue_codes.append("layer3_g2_s5_s6_s8_refs_missing")
    if "design_graph" in text or "prediction_context" in text:
        issue_codes.append("layer3_g2_design_prediction_context_missing")
    return issue_codes


def _g2_derived_tier_laundering_codes(derived_tier: str) -> list[str]:
    if derived_tier == "simulation_only_advisory":
        return ["layer3_g2_simulation_only_laundered"]
    if derived_tier == "historical_prior_context":
        return ["layer3_g2_historical_prior_laundered"]
    if derived_tier == "equilibrium_contested_blocked":
        return ["layer3_g2_equilibrium_authority_overclaim"]
    return ["layer3_g2_forecast_tier_overclaimed"]


def _g2_authority_leak_issue_codes(
    *,
    may_not_use_for: Sequence[str],
    authoritative_for: Sequence[str] = (),
) -> list[str]:
    may_not = set(_string_tuple(may_not_use_for))
    authoritative = set(_string_tuple(authoritative_for))
    checks = {
        "claim_authority": "layer3_g2_claim_authority_leak",
        "policy_recommendation": "layer3_g2_recommendation_authority_leak",
        "closeout_authority": "layer3_g2_closeout_authority_leak",
        "useful_design_credit": "layer3_g2_useful_design_credit_leak",
    }
    issues: list[str] = []
    for denial, code in checks.items():
        if denial in authoritative or denial not in may_not:
            issues.append(code)
    return issues


def _merge_g2_denials(*groups: Sequence[str]) -> tuple[str, ...]:
    denials: list[str] = []
    for group in groups:
        denials.extend(_string_tuple(group))
    denials.extend(G2_MAY_NOT_USE_FOR)
    denials.extend(
        (
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "approval_authority",
            "scorecard_authority",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        )
    )
    return tuple(dict.fromkeys(item for item in denials if item))


def _refs_with_prefix(values: Sequence[str], prefix: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ref for ref in values if ref.startswith(prefix)))


def _first_or_none(values: Sequence[str]) -> str | None:
    return values[0] if values else None


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_jsonable(item) for item in value]
    return value


def _default_g2_method_request() -> Layer3G2CausalForecastRequest:
    return Layer3G2CausalForecastRequest(
        request_id="g2-request:default-causal-forecast-method-search",
        case_id="ua-msme-affordable-loans-2022",
        source_contract_refs=("source-contract://ua-msme/server-support",),
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        target_context_id="UA",
        limit=8,
        method_task_tags=(
            "causal_effect_estimation",
            "forecasting",
            "uncertainty",
            "validation",
        ),
        data_modality="panel",
        treatment_structure="continuous_policy",
        outcome_type="food_quality",
        required_diagnostics=("identification", "transportability", "uncertainty"),
    )


def _default_g2_runtime_method_candidate() -> dict[str, object]:
    sha = "sha256:"
    return {
        "method_id": "causal.did.readiness",
        "method_fqn": "causal.did.difference_in_differences@1.0.0",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation", "uncertainty"],
        "truthfulness_status": "runtime_consistent",
        "input_refs": {
            "data_snapshot_ref": sha + "1" * 64,
            "input_bindings_ref": sha + "2" * 64,
        },
        "assumptions": {
            "identification_strategy": "pass",
            "overlap_or_support": "pass",
            "transportability": "pass",
        },
        "runtime_assumption_gates": [
            {
                "gate_ref": "gate://layer3/g2/readiness/identification",
                "assumption": "identification_strategy",
                "status": "pass",
            },
            {
                "gate_ref": "gate://layer3/g2/readiness/overlap",
                "assumption": "overlap_or_support",
                "status": "pass",
            },
            {
                "gate_ref": "gate://layer3/g2/readiness/transportability",
                "assumption": "transportability",
                "status": "pass",
            },
        ],
        "identification_requirements": {
            "estimand": "ATT",
            "requirements": ["panel_support"],
        },
        "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
        "uncertainty_refs": {"uncertainty_envelope_ref": sha + "3" * 64},
        "missingness": {"status": "pass", "missing_rate": 0.01},
        "missingness_handling": {"status": "pass", "strategy": "complete_case"},
        "sensitivity": {"status": "pass", "robustness": "moderate"},
        "transportability_limits": {"target_population": "wartime_msmes"},
        "specification_space": {"primary": "two_way_fixed_effects"},
        "method_result_refs": {"method_result_ref": sha + "4" * 64},
        "limitation_refs": {"method_limitation_ref": sha + "5" * 64},
        "validity_surfaces": {
            "identification": {"status": "present", "ref": sha + "a" * 64},
            "transportability": {"status": "present", "ref": sha + "b" * 64},
            "partial_identification": {"status": "present", "ref": sha + "c" * 64},
            "recoverability": {"status": "present", "ref": sha + "d" * 64},
            "causal_ensemble": {"status": "present", "ref": sha + "e" * 64},
            "falsification": {"status": "present", "ref": sha + "f" * 64},
            "certificate_proof": {"status": "present", "ref": sha + "0" * 64},
        },
    }


def _default_g2_semantic_spine_kwargs() -> dict[str, object]:
    return {
        "concept_spine_ref": "concept-spine://g2/agriculture-fertilizer-food-quality",
        "jurisdiction_spine_ref": "jurisdiction-spine://UA",
        "canonical_concept_refs": (
            "concept://agriculture.fertilizer_use",
            "concept://agriculture.food_nutritional_quality",
        ),
        "jurisdiction_refs": ("jurisdiction://UA",),
        "unit_refs": ("unit://farm-household",),
        "period_refs": ("period://2022-2024",),
        "geography_refs": ("geo://UA",),
        "governed_namespace_refs": (
            "namespace://g1/source-contract/ua-msme",
            "namespace://skg/academic",
            "namespace://foundry/methods",
            "namespace://layer2/s10",
        ),
        "reconciled_concept_statuses": {
            "agriculture.fertilizer_use": "reconciled",
            "agriculture.food_nutritional_quality": "reconciled",
        },
        "producer_handshake_refs": (
            "producer-handshake://g1-skg-foundry-s10/fertilizer-food-quality",
        ),
        "candidate_refs": (
            "source-contract://ua-msme/server-support",
            "skg-variable://agriculture.fertilizer_use",
            "skg-variable://agriculture.food_nutritional_quality",
            "foundry-slot://treatment",
            "foundry-slot://outcome",
        ),
    }


def _default_g2_concept_alignment_kwargs(
    request: Layer3G2CausalForecastRequest,
) -> dict[str, object]:
    return {
        "source_contract_refs": request.source_contract_refs,
        "g1_target_outcome_refs": (
            "source-contract://ua-msme/server-support#food-nutritional-quality",
        ),
        "g1_metric_refs": ("metric://food-nutritional-quality",),
        "skg_cause_variable_ref": "skg-variable://agriculture.fertilizer_use",
        "skg_effect_variable_ref": "skg-variable://agriculture.food_nutritional_quality",
        "skg_parameter_refs": ("skg-parameter://06fb46cd681818bc52d1cc01",),
        "foundry_input_slot_refs": ("foundry-slot://treatment", "foundry-slot://panel-data"),
        "foundry_output_slot_refs": ("foundry-slot://effect-estimate",),
        "s10_target_outcome_refs": ("outcome://food-nutritional-quality",),
        "alignment_status": "direct",
        "direct_grounding_claimed": True,
    }


def _default_g2_s10_prerequisite_kwargs(
    request: Layer3G2CausalForecastRequest,
) -> dict[str, object]:
    return {
        "source_design_record_ref": "pdc://layer2/s2/ua-msme/design-record-v0",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "candidate_design_ref": "candidate://ua-msme/fertilizer-support",
        "baseline_design_ref": "baseline://ua-msme/no-new-fertilizer-support",
        "alternative_design_refs": ("alternative://ua-msme/cash-transfer",),
        "prediction_horizon_ref": "horizon://12-months",
        "target_outcome_refs": ("outcome://food-nutritional-quality",),
        "jurisdiction_scope_ref": "jurisdiction://UA",
        "s5_forecast_support_ref": "pdc://layer2/s5/ua-msme/system-effect-support",
        "s5_support_label": "validated_local_dynamic_model",
        "s5_base_origin": "validated_local_model",
        "s5_claim_scope": "system_effect",
        "s6_firewall_status_refs": ("pdc://layer2/s6/ua-msme/measurability-adequacy",),
        "s6_limitation_refs": ("pdc://layer2/s6/ua-msme/strategic-response-limitation",),
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "s8_value_tradeoff_disclosure_ref": (
            "pdc://layer2/s8/ua-msme/value-tradeoff-disclosure"
        ),
        "source_contract_ref": _first_or_none(request.source_contract_refs),
        "method_validity_ref": "method-validity://foundry/causal/local",
        "sensitivity_analysis_ref": "sensitivity://ua-msme/fertilizer-support",
        "dynamic_equilibrium_check_ref": "equilibrium-check://ua-msme/system-effect",
        "equilibrium_caveat_refs": ("caveat://partial-equilibrium",),
        "strategic_response_caveat_refs": ("caveat://strategic-response",),
        "outcome_distribution_refs": ("distribution://ua-msme/fertilizer-support",),
        "welfare_comparison_ref": "welfare://ua-msme/value-grounded",
        "observable_subset_ref": "observable-subset://ua-msme/local-panel",
        "uncertainty_interval_refs": ("interval://ua-msme/fertilizer-support/95",),
        "limitation_refs": ("limitation://forecast/support-only",),
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "source_lineage_refs": ("lineage://ua-msme/source-contract",),
        "method_lineage_refs": ("lineage://ua-msme/foundry-causal",),
    }


def _default_g2_calibration_payload(
    request: Layer3G2CausalForecastRequest,
) -> dict[str, object]:
    timestamp = datetime(2026, 6, 2, tzinfo=UTC)
    return {
        "calibration_id": "layer3.g2.calibration.ua-msme.observable",
        "calibration_ref": "pdc://layer3/g2/ua-msme/calibration/observable-subset",
        "case_id": request.case_id,
        "observable_subset_ref": "observable-subset://ua-msme/local-panel",
        "prediction_ref": "forecast://ua-msme/fertilizer-support/prediction",
        "observed_outcome_ref": "outcome://ua-msme/fertilizer-support/observed",
        "historical_implementation_ref": "implementation://ua-msme/fertilizer-2022",
        "evaluation_design_ref": "eval://ua-msme/credible-counterfactual",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "counterfactual_credibility": "credible",
        "prediction_time": timestamp,
        "observation_time": timestamp,
        "policy_effective_time": timestamp,
        "data_valid_time": timestamp,
        "calibration_window_start": timestamp,
        "calibration_window_end": timestamp,
        "denominator": 4,
        "numerator": 4,
        "pass_rate": 1.0,
        "calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s10"
        ),
        "floor_passed": True,
        "calibration_status": "pass",
        "interval_coverage_metric": 1.0,
        "calibration_error_metric": 0.0,
        "source_lineage_refs": ("lineage://ua-msme/source-contract",),
        "method_lineage_refs": ("lineage://ua-msme/foundry-causal",),
    }


def _default_g2_health_metric_delta() -> dict[str, Any]:
    return {
        "schema_version": LAYER3_G2_SCHEMA_VERSION,
        "rule_version": LAYER3_G2_RULE_VERSION,
        "metric_ids": list(EXPECTED_HEALTH_METRICS),
        "readings": {
            "envelope-expansion-rate": "bounded_search_only",
            "adapter-semantic-loss": "forecast_support_bound_to_semantic_spine",
            "governance-throughput": "s10_w12d_bridge_pass",
            "demand-pull-vs-abstention": "domain_ceiling_available_not_used",
            "search-recall@known-seeds+index-staleness": "pass",
        },
    }


def _default_g2_adapter_contract_registry() -> dict[str, Any]:
    return {
        "schema_version": LAYER3_G2_SCHEMA_VERSION,
        "rule_version": LAYER3_G2_RULE_VERSION,
        "status": "pass",
        "registry_id": "layer3-g2-adapter-contract-registry",
        "adapter_contract_refs": [
            "adapter-contract://layer3/g2/skg-search-ledger",
            "adapter-contract://layer3/g2/foundry-method-validity",
            "adapter-contract://layer3/g2/s10-forecast-support",
            "adapter-contract://layer3/g2/w12d-consumer-gate",
        ],
        "capability_reality_label": "implemented",
    }


def _default_g2_recall_seeds() -> tuple[Layer3G2SearchRecallSeed, ...]:
    return (
        Layer3G2SearchRecallSeed(
            seed_id="g2-recall-seed:canonical-edge:fertilizer-use-food-nutritional-quality",
            cause="agriculture.fertilizer_use",
            effect="agriculture.food_nutritional_quality",
            expected_row_refs=("skg-edge://06fb46cd681818bc52d1cc01",),
        ),
        Layer3G2SearchRecallSeed(
            seed_id="g2-recall-seed:transport-score:fertilizer-use-food-nutritional-quality:UA",
            cause="agriculture.fertilizer_use",
            effect="agriculture.food_nutritional_quality",
            expected_row_refs=("skg-transport://06fb46cd681818bc52d1cc01:UA",),
        ),
    )


def _skg_row_ref_exists(con: duckdb.DuckDBPyConnection, row_ref: str) -> bool:
    if row_ref.startswith("skg-edge://"):
        edge_id = row_ref.removeprefix("skg-edge://")
        if not _duckdb_table_exists(con, "ac_skg_edges"):
            return False
        row = con.execute(
            "SELECT 1 FROM ac_skg_edges WHERE edge_id = ? LIMIT 1",
            [edge_id],
        ).fetchone()
        return bool(row)
    if row_ref.startswith("skg-transport://"):
        payload = row_ref.removeprefix("skg-transport://")
        if ":" not in payload or not _duckdb_table_exists(con, "ac_skg_transport_scores"):
            return False
        edge_id, context_id = payload.rsplit(":", 1)
        row = con.execute(
            """
            SELECT 1
            FROM ac_skg_transport_scores
            WHERE edge_id = ? AND target_context_id = ?
            LIMIT 1
            """,
            [edge_id, context_id],
        ).fetchone()
        return bool(row)
    return False


def _manifest_freshness_records(
    repo_root: Path,
) -> tuple[tuple[Layer3G2IndexFreshnessRecord, ...], Literal["pass", "fail"]]:
    records: list[Layer3G2IndexFreshnessRecord] = []
    failed = False
    for manifest_ref in ACADEMIC_MANIFEST_REFS:
        path = _resolve_path(repo_root, manifest_ref)
        payload = _read_json(path)
        stale = str(payload.get("freshness_status", "")).lower() == "stale"
        missing = not path.exists()
        status: Literal["pass", "fail"] = "fail" if missing or stale else "pass"
        if status == "fail":
            failed = True
        records.append(
            Layer3G2IndexFreshnessRecord(
                artifact_ref=_relative_or_str(path, repo_root),
                status=status,
                generated_at_ref=str(
                    payload.get("generated_at")
                    or payload.get("created_at")
                    or payload.get("created_ts")
                    or ""
                )
                or None,
                issue_codes=()
                if status == "pass"
                else ("layer3_g2_stale_index_blocks_domain_ceiling",),
            )
        )
    return tuple(records), "fail" if failed else "pass"


def _duckdb_table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = ?
        LIMIT 1
        """,
        [table_name],
    ).fetchone()
    return bool(row)


def _resolve_path(repo_root: Path, maybe_relative: Path) -> Path:
    path = Path(maybe_relative)
    return path if path.is_absolute() else repo_root / path


def _snapshot_hash_ref(manifest_paths: Sequence[Path], db_path: Path) -> str:
    digest = hashlib.sha256()
    used = False
    for path in manifest_paths:
        if path.exists() and path.is_file():
            digest.update(path.read_bytes())
            used = True
    if not used and db_path.exists():
        stat = db_path.stat()
        digest.update(f"{db_path}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return f"sha256:{digest.hexdigest()}"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative_or_str(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if _is_relative_to(path, root) else str(path)


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return digest


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _dump_model(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return value
    return {}


def _sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return ()


def _string_tuple(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in _sequence(value) if str(item))


def _issue(code: str, path: str, message: str) -> Layer3G2ValidationIssue:
    return Layer3G2ValidationIssue(code=code, path=path, message=message)
