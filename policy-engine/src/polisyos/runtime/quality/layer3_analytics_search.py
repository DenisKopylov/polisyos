"""Layer 3 G3 analytics search contracts and replay ledgers.

G3 search records are control-plane evidence. They can discover proof/certificate
candidates and bind request provenance to the canonical G2 L2/SKG route, but
they do not become proof authority until later certificate resolution, S11, and
consumer gates accept them.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.quality.layer3_gx_data_home import read_layer3_gx_pinned_case_id

if TYPE_CHECKING:
    import duckdb

ArtifactStore = object
IRTypeInfo = object

LAYER3_G3_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g3_analytics_search.v1"
LAYER3_G3_RULE_VERSION = "policyos.layer3.g3.analytics_search.v1"
LAYER3_G3_SURFACE_ID = "layer3_g3_proof_carrying_audit_surface"
LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g3-analytics-search-artifacts"
)
REPO_ROOT = Path(__file__).resolve().parents[4]
G3_PINNED_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)
G3_GENERATED_ARTIFACT_PATH_REFS: tuple[str, ...] = (
    "architecture/policy_design_case/layer3_g3_adapter_admission_registry.json",
    "architecture/policy_design_case/layer3_g3_l2_skg_proof_candidate_bindings.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_search_ledgers.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_query_traces.json",
    "architecture/policy_design_case/layer3_g3_ir_catalog_coverage.json",
    "architecture/policy_design_case/layer3_g3_ir_artifact_store_index.json",
    "architecture/policy_design_case/layer3_g3_certificate_resolution_report.json",
    "architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_g3_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g3_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_claim_bridge.json",
    "architecture/policy_design_case/layer3_g3_s11_prerequisite_bindings.json",
    "architecture/policy_design_case/layer3_g3_s11_calibration_bindings.json",
    "architecture/policy_design_case/layer3_g3_s11_predictive_posture_bindings.json",
    "architecture/policy_design_case/layer3_g3_claim_registry_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_baseline_comparison_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g3_proof_carrying_audit_surface.json",
    "architecture/policy_design_case/layer3_g3_conformance_report.json",
    "architecture/policy_design_case/layer3_g3_readiness_manifest.json",
    "architecture/policy_design_case/layer3_g3_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml",
)
G3_GENERATED_ARTIFACT_DOC_MARKERS: tuple[tuple[str, str], ...] = (
    ("docs/reference/generated-artifacts.md", "layer3_g3_readiness_manifest.json"),
    (
        "docs/reference/policy-design-case-layer3-analytics-search.md",
        "layer3_g3_proof_carrying_audit_surface",
    ),
    (
        "docs/reference/policy-design-case-layer3-analytics-search.md",
        "PUBLIC/REVIEWER",
    ),
    (
        "docs/reference/documentation-inventory.md",
        "policy-design-case-layer3-analytics-search.md",
    ),
    ("docs/reference/index.md", "policy-design-case-layer3-analytics-search.md"),
)

POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
CANONICAL_G2_L2_ROUTE = "scholar_knowledge.duckdb"
IR_CATALOG_ROUTE = "ir_schema_catalog_duckdb_materialized"
IR_CATALOG_BACKEND = "duckdb_materialized"
IR_CATALOG_SEARCH_BACKEND = "duckdb"
IR_ANALYTICS_DOC_INDEX = Path("src/polisyos/ir/analytics/index.md")
FORBIDDEN_FULL_CATALOG_ROUTES: tuple[str, ...] = (
    "fixture",
    "manual_class_list",
    "curated_facade_only",
    "docs_index_only",
    "compiler_bridge_view",
)
G2_DEPENDENCY_ARTIFACT_PATHS: dict[str, Path] = {
    "search_ledgers": POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_search_ledgers.json",
    "query_traces": POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_query_traces.json",
    "index_coverage": POLICY_DESIGN_CASE_DIR / "layer3_g2_l2_skg_index_coverage.json",
    "recall_freshness": POLICY_DESIGN_CASE_DIR / "layer3_g2_search_recall_freshness.json",
}
G3_ADAPTER_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g3_adapter_contract_registry.toml"
)
G3_ADAPTER_PATH_IDS: tuple[str, ...] = (
    "layer3_g3_l2_skg_to_proof_candidate_binding",
    "layer3_g3_ir_catalog_to_search_ledger",
    "layer3_g3_artifact_index_to_certificate_resolution",
    "layer3_g3_certificate_resolution_to_proof_record",
    "layer3_g3_proof_record_to_ir_analytics_bridge",
    "layer3_g3_bridge_to_w12d_consumer_gate",
)
G3_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "claim_authority",
    "causal_effect_authority_without_adapter_validation",
    "policy_recommendation",
    "closeout_authority",
    "publication_authority",
    "useful_design_credit",
    "production_authority",
    "search_hit_as_certificate",
    "search_frontier_as_proof_authority",
)
G3_LEDGER_AUTHORITATIVE_FOR: tuple[str, ...] = ()
EXPECTED_HEALTH_METRICS: tuple[str, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g3_g0_dependency_not_ready",
    "layer3_g3_g1_dependency_not_ready",
    "layer3_g3_g2_dependency_not_ready",
    "layer3_g3_l2_skg_dependency_not_ready",
    "layer3_g3_l2_skg_proof_candidate_binding_missing",
    "layer3_g3_ir_catalog_coverage_missing",
    "layer3_g3_ir_catalog_hardcode_closure",
    "layer3_g3_ir_catalog_search_not_indexed",
    "layer3_g3_search_ledger_missing",
    "layer3_g3_query_trace_missing",
    "layer3_g3_search_hit_laundered_as_certificate",
    "layer3_g3_fixture_certificate_laundered",
    "layer3_g3_unresolved_certificate_binding",
    "layer3_g3_certificate_resolution_missing",
    "layer3_g3_negative_certificate_ignored",
    "layer3_g3_proof_composability_bypass",
    "layer3_g3_method_requirement_missing",
    "layer3_g3_method_requirement_bypass",
    "layer3_g3_uncertainty_or_bounds_ref_missing",
    "layer3_g3_bounds_dual_certificate_missing",
    "layer3_g3_proof_carrying_record_missing",
    "layer3_g3_ir_analytics_bridge_missing",
    "layer3_g3_s11_prerequisite_missing",
    "layer3_g3_s11_posture_without_s6_s10",
    "layer3_g3_s11_calibration_invalid",
    "layer3_g3_s11_predictive_upgrade_missing_proof",
    "layer3_g3_claim_registry_consumer_gate_missing",
    "layer3_g3_baseline_comparison_consumer_gate_missing",
    "layer3_g3_w12d_consumer_gate_missing",
    "layer3_g3_public_raw_proof_leak",
    "layer3_g3_production_authority_leak",
    "layer3_g3_recommendation_authority_leak",
    "layer3_g3_claim_authority_leak",
    "layer3_g3_closeout_authority_leak",
    "layer3_g3_adapter_contract_registry_missing",
    "layer3_g3_adapter_registry_summary_only",
    "layer3_g3_adapter_unknown_path",
    "layer3_g3_adapter_semantic_loss",
    "layer3_g3_adapter_touchpoint_unregistered",
    "layer3_g3_persisted_artifact_missing",
    "layer3_g3_manifest_runtime_drift",
    "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_g3_search_ceiling_repair_required",
    "layer3_g3_full_cas_listing_in_request_path",
    "layer3_g3_tenant_scoped_manifest_denied",
    "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",
    "layer3_g3_store_configuration_missing",
    "layer3_g3_replay_record_missing",
    "layer3_g3_import_laziness_violation",
)


class _G3Model(BaseModel):
    """Strict base for G3 runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G3ValidationIssue(_G3Model):
    """One fail-closed G3 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G3ValidationReport(_G3Model):
    """G3 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G3ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)
    issue_code_dictionary: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)


class Layer3G3AnalyticsRequest(_G3Model):
    """Typed request for G3 L2/SKG and IR analytics candidate search."""

    request_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    comparison_ref: str | None = None
    baseline_ref: str | None = None
    alternative_refs: tuple[str, ...] = Field(default=())
    concept_refs: tuple[str, ...] = Field(default=())
    semantic_spine_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    target_context_id: str | None = None
    catalog_query_text: str | None = None
    certificate_kinds: tuple[str, ...] = Field(default=())
    limit: int = Field(default=16, ge=1, le=256)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3L2SkgDependencyArtifacts(_G3Model):
    """Loaded G2 L2/SKG dependency artifacts for G3 proof-candidate provenance."""

    status: Literal["pass", "fail"]
    search_ledgers: tuple[dict[str, Any], ...] = Field(default=())
    query_traces: tuple[dict[str, Any], ...] = Field(default=())
    index_coverage: dict[str, Any] = Field(default_factory=dict)
    recall_freshness: dict[str, Any] = Field(default_factory=dict)
    loaded_artifact_paths: tuple[str, ...] = Field(default=())
    missing_artifact_paths: tuple[str, ...] = Field(default=())
    canonical_l2_route: str = CANONICAL_G2_L2_ROUTE
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3L2SkgProofCandidateBinding(_G3Model):
    """G3 binding from request provenance to G2 L2/SKG candidate rows."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    canonical_l2_route: str = CANONICAL_G2_L2_ROUTE
    skg_ledger_ref: str = Field(min_length=1)
    g2_query_trace_refs: tuple[str, ...] = Field(default=())
    skg_row_refs: tuple[str, ...] = Field(default=())
    transport_parameter_refs: tuple[str, ...] = Field(default=())
    concept_refs: tuple[str, ...] = Field(default=())
    semantic_spine_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    search_frontier_refs: tuple[str, ...] = Field(default=())
    certificate_refs: tuple[str, ...] = Field(default=())
    candidate_role: str = "control_plane_provenance"
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3IRCatalogEntry(_G3Model):
    """One materialized IR analytics catalog row."""

    entry_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    fqn: str = Field(min_length=1)
    module: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    schema_version: str | None = None
    public_status: str = Field(min_length=1)
    exported: bool = False
    field_refs: tuple[str, ...] = Field(default=())
    ref_field_refs: tuple[str, ...] = Field(default=())
    certificate_field_refs: tuple[str, ...] = Field(default=())
    proof_status_field_refs: tuple[str, ...] = Field(default=())
    composability_field_refs: tuple[str, ...] = Field(default=())
    persistence_helper_refs: tuple[str, ...] = Field(default=())
    producer_refs: tuple[str, ...] = Field(default=())
    certificate_kinds: tuple[str, ...] = Field(default=())
    summary: str | None = None


class Layer3G3IRAnalyticsQueryTrace(_G3Model):
    """Replay trace for one materialized IR analytics catalog query."""

    trace_id: str = Field(min_length=1)
    canonical_route: str = IR_CATALOG_ROUTE
    catalog_backend: str = IR_CATALOG_SEARCH_BACKEND
    catalog_snapshot_hash_ref: str = Field(min_length=1)
    predicate_refs: tuple[str, ...] = Field(default=())
    predicates: dict[str, Any] = Field(default_factory=dict)
    bounded_result_limit: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    no_hit_reasons: tuple[str, ...] = Field(default=())
    used_duckdb_materialized_table: bool = True
    per_request_module_walk_count: int = 0
    per_request_json_scan_count: int = 0


class Layer3G3IRCatalogSearchLedger(_G3Model):
    """Replayable G3 IR catalog search frontier; never certificate authority."""

    ledger_id: str = Field(min_length=1)
    event_type: Literal["selected_candidate", "no_hit"]
    request_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    canonical_route: str = IR_CATALOG_ROUTE
    catalog_backend: str = IR_CATALOG_SEARCH_BACKEND
    catalog_snapshot_hash_ref: str = Field(min_length=1)
    index_version: str = LAYER3_G3_RULE_VERSION
    query_trace_refs: tuple[str, ...] = Field(default=())
    query_predicates: dict[str, Any] = Field(default_factory=dict)
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    no_hit_reasons: tuple[str, ...] = Field(default=())
    cutoff_limit: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    replay_key: str = Field(min_length=1)
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3IRCatalogCoverageReport(_G3Model):
    """Coverage report for the materialized IR analytics search catalog."""

    report_id: str = "layer3-g3-ir-catalog-coverage"
    status: Literal["pass", "fail"]
    full_catalog_route: str = IR_CATALOG_ROUTE
    catalog_backend: str = IR_CATALOG_BACKEND
    materialized_table_ref: str = "duckdb://memory/layer3_g3_ir_analytics_catalog"
    catalog_snapshot_hash_ref: str = Field(min_length=1)
    docs_index_ref: str = IR_ANALYTICS_DOC_INDEX.as_posix()
    docs_index_authoritative: bool = False
    catalog_rows: tuple[Layer3G3IRCatalogEntry, ...] = Field(default=())
    analytics_type_count: int = Field(default=0, ge=0)
    exported_type_count: int = Field(default=0, ge=0)
    certificate_type_count: int = Field(default=0, ge=0)
    ref_field_count: int = Field(default=0, ge=0)
    persistence_helper_count: int = Field(default=0, ge=0)
    producer_ref_count: int = Field(default=0, ge=0)
    free_growth_entry_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3IRCatalogSearchResult(_G3Model):
    """Result of one G3 IR catalog search."""

    ledger: Layer3G3IRCatalogSearchLedger
    query_traces: tuple[Layer3G3IRAnalyticsQueryTrace, ...] = Field(default=())


class Layer3G3SearchEngineeringQualityReport(_G3Model):
    """Engineering-quality report for indexed and bounded G3 search."""

    record_id: str = "layer3-g3-search-engineering-quality"
    status: Literal["pass", "fail"]
    indexed_catalog_search_status: Literal["pass", "fail"] = "fail"
    bounded_result_status: Literal["pass", "fail"] = "fail"
    deterministic_replay_status: Literal["pass", "fail"] = "fail"
    lazy_request_path_status: Literal["pass", "fail"] = "fail"
    named_library_refs: tuple[str, ...] = Field(default=())
    index_refs: tuple[str, ...] = Field(default=())
    per_request_module_walk_count: int = Field(default=0, ge=0)
    per_request_json_scan_count: int = Field(default=0, ge=0)
    unbounded_query_count: int = Field(default=0, ge=0)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3SearchRecallSeedRecord(_G3Model):
    """Known-groundable G3 search seed replayed before proof-domain ceiling claims."""

    seed_id: str = Field(min_length=1)
    seed_kind: Literal[
        "l2_skg_dependency",
        "ir_catalog_search",
        "certificate_resolution",
    ]
    status: Literal["pass", "fail"]
    expected_route: str | None = None
    evidence_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3SearchRecallFreshnessReport(_G3Model):
    """G3 known-seed recall and index freshness gate."""

    report_id: str = "layer3-g3-search-recall-freshness"
    status: Literal["pass", "fail"]
    freshness_status: Literal["pass", "fail"] = "fail"
    l2_skg_seed_status: Literal["pass", "fail"] = "fail"
    ir_catalog_seed_status: Literal["pass", "fail"] = "fail"
    certificate_resolution_seed_status: Literal["pass", "fail"] = "fail"
    known_seed_count: int = Field(default=0, ge=0)
    recalled_seed_count: int = Field(default=0, ge=0)
    missed_seed_count: int = Field(default=0, ge=0)
    seed_records: tuple[Layer3G3SearchRecallSeedRecord, ...] = Field(default=())
    catalog_snapshot_hash_ref: str | None = None
    artifact_snapshot_hash_ref: str | None = None
    search_ledger_refs: tuple[str, ...] = Field(default=())
    query_trace_refs: tuple[str, ...] = Field(default=())
    payload_fingerprint_refs: tuple[str, ...] = Field(default=())
    freshness_evidence_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3ArtifactStoreIndex(_G3Model):
    """Selected-ref artifact-store index for G3 certificate resolution."""

    record_id: str = "layer3-g3-ir-artifact-store-index"
    status: Literal["pass", "fail", "blocked", "not_configured"]
    store_backend: str = "not_configured"
    store_root_ref: str | None = None
    index_scope: Literal["selected_refs", "bounded_listing", "not_configured"] = (
        "selected_refs"
    )
    selected_candidate_count: int = Field(default=0, ge=0)
    indexed_artifact_refs: tuple[str, ...] = Field(default=())
    manifest_refs: tuple[str, ...] = Field(default=())
    payload_fingerprint_refs: tuple[str, ...] = Field(default=())
    snapshot_hash_ref: str = Field(min_length=1)
    full_listing_used: bool = False
    listing_budget: int = Field(default=0, ge=0)
    listing_cutoff_reached: bool = False
    stale: bool = False
    tenant_scope_status: Literal["allowed", "denied", "unknown"] = "unknown"
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3CertificateCandidate(_G3Model):
    """Typed candidate ref discovered by search or deterministic producer output."""

    candidate_id: str = Field(min_length=1)
    certificate_kind: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    source: str = Field(min_length=1)
    artifact_ref: dict[str, Any] | None = None
    artifact_id: str | None = None
    producer_ref: str | None = None
    request_ref: str | None = None
    claim_id: str | None = None
    case_id: str | None = None
    selected_ref_only: bool = False
    positive_candidate: bool = True
    tenant_scope_status: Literal["allowed", "denied", "unknown"] = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3CertificateResolutionRecord(_G3Model):
    """Typed resolution result for one G3 certificate candidate."""

    record_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    status: Literal["resolved", "fail", "blocked", "limited"]
    certificate_kind: str = Field(min_length=1)
    typed_payload_kind: str | None = None
    artifact_ref: dict[str, Any] | None = None
    artifact_id: str | None = None
    manifest_ref: str | None = None
    payload_fingerprint_ref: str | None = None
    evidence_role: Literal["positive", "blocking", "limiting", "control_plane", "unknown"] = (
        "unknown"
    )
    positive_proof_closure: bool = False
    blocking: bool = False
    limiting: bool = False
    source: str = Field(min_length=1)
    loader_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3CertificateResolutionReport(_G3Model):
    """Aggregate G3 certificate-resolution status and replay fingerprints."""

    record_id: str = "layer3-g3-certificate-resolution-report"
    status: Literal["pass", "fail", "blocked"]
    records: tuple[Layer3G3CertificateResolutionRecord, ...] = Field(default=())
    resolved_certificate_count: int = Field(default=0, ge=0)
    positive_resolved_certificate_count: int = Field(default=0, ge=0)
    blocking_certificate_count: int = Field(default=0, ge=0)
    limiting_certificate_count: int = Field(default=0, ge=0)
    selected_candidate_count: int = Field(default=0, ge=0)
    no_hit_count: int = Field(default=0, ge=0)
    full_listing_used: bool = False
    stale_artifact_index: bool = False
    payload_fingerprint_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G3_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3MethodRequirementBinding(_G3Model):
    """G3 claim-bound method requirement binding reused by S11 and bridge paths."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    source_route: Literal["g2_method_requirement_bindings", "w7c_compiler", "explicit"]
    method_requirement_specs: tuple[dict[str, Any], ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    selected_method_refs: tuple[str, ...] = Field(default=())
    rejected_method_refs: tuple[str, ...] = Field(default=())
    source_binding_refs: tuple[str, ...] = Field(default=())
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3SemanticSpineBinding(_G3Model):
    """G3 semantic-spine/context refs carried into proof and method bindings."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    request_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    concept_refs: tuple[str, ...] = Field(default=())
    semantic_spine_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    certificate_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3ProofCarryingAnalyticsBinding(_G3Model):
    """G3 binding around the existing S11 ProofCarryingAnalyticsRecord waist."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "fail", "blocked"]
    request_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    proof_ref: str | None = None
    bridge_ref: str | None = None
    certificate_resolution_record_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    ir_certificate_refs: tuple[str, ...] = Field(default=())
    negative_certificate_refs: tuple[str, ...] = Field(default=())
    method_output_refs: tuple[str, ...] = Field(default=())
    uncertainty_refs: tuple[str, ...] = Field(default=())
    s11_record: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3IRAnalyticsBridgeBinding(_G3Model):
    """G3 binding around the existing ir_analytics_claim_bridge report."""

    record_id: str = "layer3-g3-ir-analytics-claim-bridge"
    status: Literal["pass", "fail", "blocked"]
    bridge_ref: str | None = None
    claim_binding_count: int = Field(default=0, ge=0)
    method_requirement_binding_count: int = Field(default=0, ge=0)
    bridge_payload: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3S11PrerequisiteBinding(_G3Model):
    """S6/S10 prerequisite binding required before G3 emits S11 posture."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "blocked", "fail"]
    request_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    s6_floor_status_refs: tuple[str, ...] = Field(default=())
    s6_axis_rows: tuple[dict[str, Any], ...] = Field(default=())
    s6_bridge_consumer_rows: tuple[dict[str, Any], ...] = Field(default=())
    s6_constraint_store_update_refs: tuple[str, ...] = Field(default=())
    s6_c3_authority_dimension_refs: tuple[str, ...] = Field(default=())
    post_intervention_dgp_update_ref: str | None = None
    system_dynamics_handoff_required: bool = False
    s10_forecast_support_ref: str | None = None
    s10_forecast_tier: str | None = None
    s10_forecast_calibration_record_ref: str | None = None
    g2_forecast_support_binding_ref: str | None = None
    source_contract_refs: tuple[str, ...] = Field(default=())
    method_validity_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3S11CalibrationBinding(_G3Model):
    """G3 binding around existing S11 calibration, upgrade, and authority records."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "blocked", "fail"]
    request_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    axis: str = Field(min_length=1)
    cell_ref: str = Field(min_length=1)
    calibration_ref: str | None = None
    upgrade_ref: str | None = None
    authority_envelope_ref: str | None = None
    integrity_report_ref: str | None = None
    proof_carrying_analytics_ref: str | None = None
    s6_floor_record_ref: str | None = None
    s10_forecast_support_ref: str | None = None
    effective_maturity: str | None = None
    relaxation_decision: str | None = None
    forecast_quality_disposition: str | None = None
    calibration_record: dict[str, Any] = Field(default_factory=dict)
    axis_upgrade_record: dict[str, Any] = Field(default_factory=dict)
    authority_envelope: dict[str, Any] = Field(default_factory=dict)
    integrity_summary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3S11PredictivePostureBinding(_G3Model):
    """G3 binding around existing S11 predictive-knowledge posture output."""

    binding_id: str = Field(min_length=1)
    status: Literal["pass", "blocked", "fail"]
    request_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    predictive_knowledge_ref: str | None = None
    proof_carrying_analytics_ref: str | None = None
    ir_analytics_bridge_ref: str | None = None
    s10_forecast_support_ref: str | None = None
    s10_forecast_tier: str | None = None
    s6_floor_status_refs: tuple[str, ...] = Field(default=())
    s11_calibration_record_refs: tuple[str, ...] = Field(default=())
    axis_upgrade_refs: tuple[str, ...] = Field(default=())
    posture_payload: dict[str, Any] = Field(default_factory=dict)
    integrity_summary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3ClaimRegistryConsumerGateRecord(_G3Model):
    """Gate proving a G3 bridge is consumed by runtime claim registry."""

    record_id: str = "layer3-g3-claim-registry-consumer-gate"
    status: Literal["pass", "fail", "blocked"]
    request_ref: str | None = None
    case_id: str | None = None
    claim_id: str | None = None
    runtime_claim_registry_ref: str | None = None
    claim_registry_status: str | None = None
    ir_analytics_bridge_ref: str | None = None
    proof_carrying_analytics_refs: tuple[str, ...] = Field(default=())
    consumed_ir_analytics_refs: tuple[str, ...] = Field(default=())
    blocked_claim_count: int = Field(default=0, ge=0)
    claim_registry_payload: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3BaselineComparisonConsumerGateRecord(_G3Model):
    """Gate proving BaselineComparisonCompiler consumes G3 as evidence only."""

    record_id: str = "layer3-g3-baseline-comparison-consumer-gate"
    status: Literal["pass", "fail", "blocked"]
    request_ref: str | None = None
    case_id: str | None = None
    claim_id: str | None = None
    comparison_record_count: int = Field(default=0, ge=0)
    comparison_evidence_refs: tuple[str, ...] = Field(default=())
    comparison_method_refs: tuple[str, ...] = Field(default=())
    ir_analytics_bridge_refs: tuple[str, ...] = Field(default=())
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    compiled_ledger_payload: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)


class Layer3G3W12DConsumerGateRecord(_G3Model):
    """W12D gate proving S11/S2 consumes a G3-resolved proof record."""

    record_id: str = "layer3-g3-w12d-consumer-gate"
    gate_id: str = "layer3.g3.w12d.analytics_search_gate"
    status: Literal["pass", "fail", "blocked"]
    case_id: str | None = None
    route_kind: Literal[
        "full_s11_s2_consumer",
        "lightweight_s11_posture_ref",
        "not_routed",
    ] = "not_routed"
    posture_consumed: bool = False
    predictive_knowledge_ref: str | None = None
    g3_proof_carrying_analytics_ref: str | None = None
    g3_ir_analytics_bridge_ref: str | None = None
    fixture_s11_regression_context_ref: str | None = None
    full_s2_consumer_case_refs: tuple[str, ...] = Field(default=())
    lightweight_case_refs: tuple[str, ...] = Field(default=())
    lightweight_posture_ref: str | None = None
    full_consumer_case_count: int = Field(default=0, ge=0)
    lightweight_posture_ref_count: int = Field(default=0, ge=0)
    g3_closure_count: int = Field(default=0, ge=0)
    fixture_certificate_closure_count: int = Field(default=0, ge=0)
    negative_certificate_block_count: int = Field(default=0, ge=0)
    useful_design_delta_count: int = Field(default=0, ge=0)
    consumer_assertions: dict[str, bool] = Field(default_factory=dict)
    authoritative_for: tuple[str, ...] = Field(default=("w12d_g3_analytics_search_gate",))
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3PublicExportProjectionRefSurface(_G3Model):
    """Projection-only G3 refs/status for public export surfaces."""

    record_id: str = "layer3-g3-public-export-projection-refs"
    status: Literal["pass", "fail", "blocked"]
    projection_ref: str = "pdc://layer3/g3/public-export-projection"
    authority_role: Literal["projection_only"] = "projection_only"
    certificate_resolution_report_ref: str | None = None
    search_ledger_refs: tuple[str, ...] = Field(default=())
    redacted_search_frontier_refs: tuple[str, ...] = Field(default=())
    proof_carrying_analytics_refs: tuple[str, ...] = Field(default=())
    ir_analytics_bridge_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    s11_predictive_posture_refs: tuple[str, ...] = Field(default=())
    resolved_certificate_count: int = Field(default=0, ge=0)
    blocked_certificate_count: int = Field(default=0, ge=0)
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)
    public_payload_redaction_status: Literal["pass", "fail"] = "pass"
    raw_proof_payload_exported: bool = False
    raw_cas_manifest_exported: bool = False
    raw_query_ledger_exported: bool = False
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3ProofCarryingAuditSurface(_G3Model):
    """Audience-tiered G3 proof-carrying audit surface."""

    record_id: str = "layer3-g3-proof-carrying-audit-surface"
    status: Literal["pass", "fail", "blocked"]
    surface_id: str = LAYER3_G3_SURFACE_ID
    surface_audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    proof_posture: str = "projection_only_resolved_proof_refs"
    public_fields: tuple[str, ...] = (
        "status",
        "proof_posture",
        "limitation_refs",
        "may_not_use_for",
    )
    reviewer_fields: tuple[str, ...] = (
        "status",
        "proof_posture",
        "certificate_resolution_status",
        "consumer_gate_status",
        "limitation_refs",
        "may_not_use_for",
    )
    expert_fields: tuple[str, ...] = Field(default=())
    machine_fields: tuple[str, ...] = Field(default=())
    certificate_resolution_report_ref: str | None = None
    proof_carrying_analytics_refs: tuple[str, ...] = Field(default=())
    ir_analytics_bridge_refs: tuple[str, ...] = Field(default=())
    search_frontier_refs: tuple[str, ...] = Field(default=())
    method_requirement_refs: tuple[str, ...] = Field(default=())
    s11_predictive_posture_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=G3_MAY_NOT_USE_FOR)
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3AdapterContractRegistryStatus(_G3Model):
    """Status of the loader-compatible G3 adapter contract registry."""

    record_id: str = "layer3-g3-adapter-contract-registry"
    status: Literal["pass", "fail", "blocked"]
    registry_ref: str | None = None
    adapter_contract_path_count: int = Field(default=0, ge=0)
    adapter_path_ids: tuple[str, ...] = Field(default=())
    adapter_admission_records: tuple[dict[str, Any], ...] = Field(default=())
    checked_field_families: tuple[str, ...] = Field(default=())
    loader_error_code: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3AdapterAdmissionBundle(_G3Model):
    """G3 adapter-admission rows compatible with the G0 registry grammar."""

    record_id: str = "layer3-g3-adapter-admission-registry"
    status: Literal["pass", "fail", "blocked"]
    records: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3GeneratedArtifactRegistrationStatus(_G3Model):
    """Status of G3 generated-artifact family registration and docs surfaces."""

    record_id: str = LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID
    status: Literal["pass", "fail"]
    generated_artifact_family_id: str = LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID
    required_artifact_paths: tuple[str, ...] = Field(
        default=G3_GENERATED_ARTIFACT_PATH_REFS
    )
    registered_artifact_paths: tuple[str, ...] = Field(default=())
    registered_doc_refs: tuple[str, ...] = Field(default=())
    missing_registration_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3ConformanceReport(_G3Model):
    """Final G3 conformance report for replay, performance, adapters, and authority."""

    record_id: str = "layer3-g3-conformance-report"
    status: Literal["pass", "fail", "blocked"]
    replay_check_status: Literal["pass", "fail"] = "fail"
    performance_check_status: Literal["pass", "fail"] = "fail"
    module_load_check_status: Literal["pass", "fail"] = "fail"
    adapter_admission_check_status: Literal["pass", "fail"] = "fail"
    artifact_store_check_status: Literal["pass", "fail", "blocked"] = "fail"
    authority_boundary_check_status: Literal["pass", "fail"] = "fail"
    replayed_certificate_count: int = Field(default=0, ge=0)
    checked_adapter_path_count: int = Field(default=0, ge=0)
    checked_issue_codes: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)
    issue_code_dictionary: tuple[str, ...] = Field(default=ALL_ISSUE_CODES)
    heavy_module_import_refs: tuple[str, ...] = Field(default=())
    missing_replay_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G3ReadinessManifest(_G3Model):
    """Selected G3 readiness keys used for runtime/persisted drift checks."""

    schema_version: str = LAYER3_G3_SCHEMA_VERSION
    rule_version: str = LAYER3_G3_RULE_VERSION
    g0_dependency_status: str = "not_checked"
    g1_dependency_status: str = "not_checked"
    g2_dependency_status: str = "not_checked"
    g3_l2_skg_dependency_status: str = "fail"
    g3_l2_skg_proof_candidate_binding_count: int = 0
    g3_ir_catalog_coverage_status: str = "fail"
    g3_ir_artifact_store_index_status: str = "not_implemented"
    g3_search_ledger_count: int = 0
    g3_query_trace_count: int = 0
    g3_certificate_resolution_status: str = "not_implemented"
    g3_resolved_certificate_count: int = 0
    g3_search_recall_freshness_status: str = "fail"
    g3_search_recall_seed_count: int = 0
    g3_search_recall_recalled_seed_count: int = 0
    g3_method_requirement_binding_count: int = 0
    g3_proof_carrying_record_count: int = 0
    g3_ir_analytics_bridge_status: str = "not_implemented"
    g3_s11_prerequisite_binding_status: str = "not_implemented"
    g3_s11_predictive_posture_binding_count: int = 0
    g3_claim_registry_consumer_gate_status: str = "not_implemented"
    g3_baseline_comparison_consumer_gate_status: str = "not_implemented"
    g3_w12d_consumer_gate_status: str = "not_implemented"
    g3_public_export_projection_status: str = "not_implemented"
    g3_search_engineering_quality_status: str = "fail"
    g3_conformance_status: str = "fail"
    g3_adapter_contract_registry_status: str = "not_implemented"
    g3_adapter_contract_path_count: int = 0
    g3_health_metric_ids: tuple[str, ...] = Field(default=EXPECTED_HEALTH_METRICS)


class Layer3G3Bundle(_G3Model):
    """Top-level G3 runtime bundle shape."""

    schema_version: str = LAYER3_G3_SCHEMA_VERSION
    rule_version: str = LAYER3_G3_RULE_VERSION
    adapter_admission_registry: Layer3G3AdapterAdmissionBundle
    l2_skg_proof_candidate_bindings: tuple[Layer3G3L2SkgProofCandidateBinding, ...]
    ir_analytics_search_ledgers: tuple[Layer3G3IRCatalogSearchLedger, ...]
    ir_analytics_query_traces: tuple[Layer3G3IRAnalyticsQueryTrace, ...]
    ir_catalog_coverage: Layer3G3IRCatalogCoverageReport
    ir_artifact_store_index: Layer3G3ArtifactStoreIndex
    certificate_resolution_report: Layer3G3CertificateResolutionReport
    search_recall_freshness: Layer3G3SearchRecallFreshnessReport
    method_requirement_bindings: tuple[Layer3G3MethodRequirementBinding, ...]
    semantic_spine_bindings: tuple[Layer3G3SemanticSpineBinding, ...]
    proof_carrying_analytics_records: tuple[Layer3G3ProofCarryingAnalyticsBinding, ...]
    ir_analytics_claim_bridge: Layer3G3IRAnalyticsBridgeBinding
    s11_prerequisite_bindings: tuple[Layer3G3S11PrerequisiteBinding, ...]
    s11_calibration_bindings: tuple[Layer3G3S11CalibrationBinding, ...]
    s11_predictive_posture_bindings: tuple[Layer3G3S11PredictivePostureBinding, ...]
    claim_registry_consumer_gate: Layer3G3ClaimRegistryConsumerGateRecord
    baseline_comparison_consumer_gate: Layer3G3BaselineComparisonConsumerGateRecord
    w12d_consumer_gate: Layer3G3W12DConsumerGateRecord
    public_export_projection_refs: Layer3G3PublicExportProjectionRefSurface
    proof_carrying_audit_surface: Layer3G3ProofCarryingAuditSurface
    search_engineering_quality: Layer3G3SearchEngineeringQualityReport
    conformance_report: Layer3G3ConformanceReport
    health_metric_delta: dict[str, Any] = Field(default_factory=dict)
    adapter_contract_registry: Layer3G3AdapterContractRegistryStatus
    readiness_manifest: Layer3G3ReadinessManifest


def load_g3_l2_skg_dependency_artifacts(repo_root: Path) -> Layer3G3L2SkgDependencyArtifacts:
    """Load and validate the canonical G2 L2/SKG dependency artifacts."""

    root = Path(repo_root).resolve()
    loaded_paths: list[str] = []
    missing_paths: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    issue_codes: list[str] = []
    for key, rel_path in G2_DEPENDENCY_ARTIFACT_PATHS.items():
        path = _resolve_repo_path(root, rel_path)
        if not path.exists():
            missing_paths.append(rel_path.as_posix())
            continue
        try:
            payloads[key] = _read_json(path)
            loaded_paths.append(rel_path.as_posix())
        except (OSError, json.JSONDecodeError):
            missing_paths.append(rel_path.as_posix())

    search_ledgers = tuple(
        _sequence(payloads.get("search_ledgers", {}).get("l2_skg_search_ledgers"))
    )
    query_traces = tuple(_sequence(payloads.get("query_traces", {}).get("l2_skg_query_traces")))
    index_coverage = _mapping(payloads.get("index_coverage", {}).get("l2_skg_index_coverage"))
    recall_freshness = _mapping(
        payloads.get("recall_freshness", {}).get("search_recall_freshness")
    )
    unhealthy = (
        bool(missing_paths)
        or not search_ledgers
        or not query_traces
        or index_coverage.get("status") != "pass"
        or index_coverage.get("canonical_l2_route") != CANONICAL_G2_L2_ROUTE
        or recall_freshness.get("status") != "pass"
        or recall_freshness.get("search_recall_status") != "pass"
        or recall_freshness.get("index_freshness_status") != "pass"
    )
    if unhealthy:
        issue_codes.extend(
            (
                "layer3_g3_l2_skg_dependency_not_ready",
                "layer3_g3_search_ceiling_repair_required",
            )
        )
    return Layer3G3L2SkgDependencyArtifacts(
        status="fail" if unhealthy else "pass",
        search_ledgers=tuple(dict(row) for row in search_ledgers if isinstance(row, Mapping)),
        query_traces=tuple(dict(row) for row in query_traces if isinstance(row, Mapping)),
        index_coverage=dict(index_coverage),
        recall_freshness=dict(recall_freshness),
        loaded_artifact_paths=tuple(loaded_paths),
        missing_artifact_paths=tuple(missing_paths),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g3_l2_skg_proof_candidate_bindings(
    request: Layer3G3AnalyticsRequest,
    dependencies: Layer3G3L2SkgDependencyArtifacts,
) -> tuple[Layer3G3L2SkgProofCandidateBinding, ...]:
    """Build G3 control-plane proof-candidate bindings from G2 ledgers."""

    if dependencies.status != "pass":
        return ()
    traces_by_id = {
        str(trace.get("trace_id")): trace
        for trace in dependencies.query_traces
        if trace.get("trace_id")
    }
    bindings: list[Layer3G3L2SkgProofCandidateBinding] = []
    for ledger in dependencies.search_ledgers:
        ledger_id = str(ledger.get("ledger_id", ""))
        trace_refs = tuple(str(ref) for ref in _sequence(ledger.get("query_trace_refs")))
        selected_refs = tuple(str(ref) for ref in _sequence(ledger.get("selected_candidate_refs")))
        row_refs = _dedupe(
            [
                *selected_refs,
                *(
                    str(ref)
                    for trace_ref in trace_refs
                    for ref in _sequence(traces_by_id.get(trace_ref, {}).get("row_refs"))
                ),
            ]
        )
        transport_refs = tuple(ref for ref in row_refs if ref.startswith("skg-transport://"))
        parameter_refs = tuple(ref for ref in row_refs if "parameter" in ref)
        search_frontier_refs = _dedupe([ledger_id, *trace_refs])
        issues = ()
        if not ledger_id or not row_refs or not trace_refs:
            issues = ("layer3_g3_l2_skg_proof_candidate_binding_missing",)
        bindings.append(
            Layer3G3L2SkgProofCandidateBinding(
                binding_id=(
                    "g3-l2-skg-proof-candidate-binding:"
                    f"{_stable_id(request.request_id, ledger_id)}"
                ),
                status="fail" if issues else "pass",
                request_ref=request.request_id,
                claim_id=request.claim_id,
                case_id=request.case_id,
                skg_ledger_ref=ledger_id or "missing-g2-ledger-ref",
                g2_query_trace_refs=trace_refs,
                skg_row_refs=row_refs,
                transport_parameter_refs=(*transport_refs, *parameter_refs),
                concept_refs=request.concept_refs,
                semantic_spine_refs=request.semantic_spine_refs,
                method_requirement_refs=request.method_requirement_refs,
                search_frontier_refs=search_frontier_refs,
                issue_codes=issues,
            )
        )
    return tuple(bindings)


def build_g3_ir_catalog_coverage(
    repo_root: Path,
    *,
    additional_entries: Sequence[Mapping[str, Any] | Layer3G3IRCatalogEntry] = (),
) -> Layer3G3IRCatalogCoverageReport:
    """Build and materialize a searchable IR analytics catalog snapshot."""

    _ = Path(repo_root).resolve()
    issue_codes: list[str] = []
    rows: list[Layer3G3IRCatalogEntry] = []
    try:
        catalog_module = importlib.import_module("polisyos.ir.schemas.catalog")
        catalog = catalog_module.get_ir_schema_catalog()
        rows.extend(
            _catalog_entry_from_ir_type(entry)
            for entry in catalog.types
            if entry.section == "analytics"
        )
    except Exception:
        issue_codes.append("layer3_g3_ir_catalog_coverage_missing")

    for entry in additional_entries:
        rows.append(
            entry
            if isinstance(entry, Layer3G3IRCatalogEntry)
            else Layer3G3IRCatalogEntry.model_validate(entry)
        )

    rows = sorted(rows, key=lambda row: (row.module, row.name, row.fqn))
    snapshot_hash = _catalog_snapshot_hash(rows)
    _materialize_catalog_rows(rows)
    certificate_type_count = sum(1 for row in rows if row.certificate_kinds)
    ref_field_count = sum(len(row.ref_field_refs) for row in rows)
    persistence_helper_count = sum(len(row.persistence_helper_refs) for row in rows)
    producer_ref_count = sum(len(row.producer_refs) for row in rows)
    if not rows or certificate_type_count <= 0 or ref_field_count <= 0:
        issue_codes.append("layer3_g3_ir_catalog_coverage_missing")
    return Layer3G3IRCatalogCoverageReport(
        status="pass" if not issue_codes else "fail",
        catalog_snapshot_hash_ref=snapshot_hash,
        catalog_rows=tuple(rows),
        analytics_type_count=len(rows),
        exported_type_count=sum(1 for row in rows if row.exported),
        certificate_type_count=certificate_type_count,
        ref_field_count=ref_field_count,
        persistence_helper_count=persistence_helper_count,
        producer_ref_count=producer_ref_count,
        free_growth_entry_count=len(additional_entries),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def search_ir_analytics_catalog(
    request: Layer3G3AnalyticsRequest,
    coverage: Layer3G3IRCatalogCoverageReport,
) -> Layer3G3IRCatalogSearchResult:
    """Search a materialized IR analytics catalog snapshot with bounded DuckDB predicates."""

    con = _materialize_catalog_rows(coverage.catalog_rows)
    query_text = (request.catalog_query_text or "").strip().lower()
    certificate_kinds = tuple(kind.strip().lower() for kind in request.certificate_kinds if kind)
    predicates: dict[str, Any] = {
        "query_text": query_text,
        "certificate_kinds": certificate_kinds,
        "limit": request.limit,
    }
    con.execute("CREATE TEMP TABLE requested_kinds (kind VARCHAR)")
    for kind in certificate_kinds:
        con.execute("INSERT INTO requested_kinds VALUES (?)", (kind,))
    sql = """
        SELECT entry_id
        FROM ir_catalog
        WHERE (? = '' OR searchable_text LIKE ?)
          AND (
            (SELECT COUNT(*) FROM requested_kinds) = 0
            OR EXISTS (
              SELECT 1
              FROM requested_kinds
              WHERE certificate_kinds_text LIKE '%' || kind || '%'
            )
          )
        ORDER BY exported DESC, certificate_kinds_text DESC, entry_id
        LIMIT ?
        """
    params = (query_text, f"%{query_text}%", request.limit)
    try:
        selected = [str(row[0]) for row in con.execute(sql, params).fetchall()]
    finally:
        con.close()
    no_hit_reasons = () if selected else ("catalog_no_hit",)
    trace_id = (
        "g3-ir-catalog-query-trace:"
        f"{_stable_id(request.request_id, coverage.catalog_snapshot_hash_ref)}"
    )
    predicate_refs = (
        *(f"certificate_kind:{kind}" for kind in certificate_kinds),
        *(("query_text",) if query_text else ()),
    )
    trace = Layer3G3IRAnalyticsQueryTrace(
        trace_id=trace_id,
        catalog_snapshot_hash_ref=coverage.catalog_snapshot_hash_ref,
        predicate_refs=predicate_refs,
        predicates=predicates,
        bounded_result_limit=request.limit,
        result_count=len(selected),
        selected_candidate_refs=tuple(selected),
        no_hit_reasons=no_hit_reasons,
    )
    ledger = Layer3G3IRCatalogSearchLedger(
        ledger_id=f"g3-ir-analytics-search-ledger:{_stable_id(request.request_id, trace_id)}",
        event_type="selected_candidate" if selected else "no_hit",
        request_ref=request.request_id,
        claim_id=request.claim_id,
        catalog_snapshot_hash_ref=coverage.catalog_snapshot_hash_ref,
        query_trace_refs=(trace_id,),
        query_predicates=predicates,
        selected_candidate_refs=tuple(selected),
        no_hit_reasons=no_hit_reasons,
        cutoff_limit=request.limit,
        result_count=len(selected),
        replay_key=_stable_id(
            LAYER3_G3_RULE_VERSION,
            request.request_id,
            coverage.catalog_snapshot_hash_ref,
            json.dumps(predicates, sort_keys=True, default=str),
        ),
    )
    return Layer3G3IRCatalogSearchResult(ledger=ledger, query_traces=(trace,))


def build_g3_search_engineering_quality_report(
    *,
    coverage: Layer3G3IRCatalogCoverageReport,
    search_result: Layer3G3IRCatalogSearchResult | None,
    per_request_module_walk_count: int = 0,
    per_request_json_scan_count: int = 0,
    unbounded_query_count: int = 0,
) -> Layer3G3SearchEngineeringQualityReport:
    """Check that G3 search used indexed, bounded, replayable request paths."""

    traces = search_result.query_traces if search_result is not None else ()
    ledger = search_result.ledger if search_result is not None else None
    indexed = (
        coverage.catalog_backend == IR_CATALOG_BACKEND
        and bool(coverage.catalog_rows)
        and bool(ledger and ledger.catalog_backend == IR_CATALOG_SEARCH_BACKEND)
    )
    bounded = (
        unbounded_query_count == 0
        and all(0 < trace.bounded_result_limit <= 256 for trace in traces)
        and bool(traces)
    )
    deterministic = bool(ledger and ledger.replay_key and ledger.query_trace_refs) and all(
        trace.trace_id in ledger.query_trace_refs for trace in traces
    )
    lazy = per_request_module_walk_count == 0 and per_request_json_scan_count == 0
    issue_codes: list[str] = []
    if not indexed:
        issue_codes.append("layer3_g3_ir_catalog_search_not_indexed")
    if not bounded:
        issue_codes.append("layer3_g3_search_ledger_missing")
    if not deterministic:
        issue_codes.append("layer3_g3_query_trace_missing")
    if not lazy:
        issue_codes.append("layer3_g3_ir_catalog_search_not_indexed")
    return Layer3G3SearchEngineeringQualityReport(
        status="pass" if not issue_codes else "fail",
        indexed_catalog_search_status="pass" if indexed else "fail",
        bounded_result_status="pass" if bounded else "fail",
        deterministic_replay_status="pass" if deterministic else "fail",
        lazy_request_path_status="pass" if lazy else "fail",
        named_library_refs=("duckdb", "polisyos.ir.schemas.catalog.get_ir_schema_catalog"),
        index_refs=(coverage.materialized_table_ref, coverage.catalog_snapshot_hash_ref),
        per_request_module_walk_count=per_request_module_walk_count,
        per_request_json_scan_count=per_request_json_scan_count,
        unbounded_query_count=unbounded_query_count,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_layer3_g3_bundle(repo_root: Path) -> Layer3G3Bundle:
    """Build the current G3 runtime bundle across search, proof, and consumers."""

    root = Path(repo_root).resolve()
    claim_ledger, request, selected_option_ref, alternative_ref = _default_g3_claim_ledger_route()
    dependencies = load_g3_l2_skg_dependency_artifacts(root)
    bindings = build_g3_l2_skg_proof_candidate_bindings(request, dependencies)
    coverage = build_g3_ir_catalog_coverage(root)
    search_result = search_ir_analytics_catalog(request, coverage)
    search_quality = build_g3_search_engineering_quality_report(
        coverage=coverage,
        search_result=search_result,
    )
    artifact_store_module = importlib.import_module("polisyos.core.artifacts.store")
    file_system_cas_cls = artifact_store_module.FileSystemCAS
    store = file_system_cas_cls(root / "_build/.tmp/production-quality/g3-cas")
    candidates = produce_g3_deterministic_first_case_certificate(request, store=store)
    artifact_index = build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
    )
    certificate_resolution = build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=artifact_index,
        store=store,
    )
    search_recall = build_g3_search_recall_freshness(
        dependencies=dependencies,
        ir_catalog_coverage=coverage,
        search_ledgers=(search_result.ledger,),
        query_traces=search_result.query_traces,
        ir_artifact_store_index=artifact_index,
        certificate_resolution_report=certificate_resolution,
    )
    method_bindings = build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(_default_g3_method_requirement(request),),
        selected_method_refs=("ir.method.g3.default_analytics_search",),
    )
    semantic_bindings = build_g3_semantic_spine_bindings(
        request=request,
        method_requirement_bindings=method_bindings,
        certificate_resolution_report=certificate_resolution,
    )
    proof_records = build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=certificate_resolution,
        method_requirement_bindings=method_bindings,
        semantic_spine_bindings=semantic_bindings,
    )
    bridge = build_g3_ir_analytics_bridge_bindings(
        proof_carrying_analytics_records=proof_records,
        method_requirement_bindings=method_bindings,
    )
    prereqs = build_g3_s11_prerequisite_bindings(
        request=request,
        repo_root=root,
        s6_floor_status_refs=(
            "pdc://layer2/s6/g3/measurability",
            "pdc://layer2/s6/g3/strategic-response",
        ),
        s6_axis_rows=(
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "record_ref": "pdc://layer2/s6/g3/measurability",
                "disposition": "limit",
            },
            {
                "axis": "strategic_response",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "record_ref": "pdc://layer2/s6/g3/strategic-response",
                "disposition": "block",
            },
        ),
        s6_bridge_consumer_rows=(
            {
                "cell_ref": "SYSTEM.measurability",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "producer_ref": "pdc://layer2/s6/g3/measurability",
                "disposition": "limit",
            },
        ),
        s6_constraint_store_update_refs=("constraint://s6/g3/measurability",),
        s6_c3_authority_dimension_refs=("pdc://layer2/s6/g3/c3/measurability",),
        s10_forecast_support_ref=f"pdc://layer3/g3/{request.case_id}/forecast-support",
        s10_forecast_tier="observable_calibrated",
        s10_forecast_calibration_record_ref=(
            f"pdc://layer3/g3/{request.case_id}/forecast-calibration"
        ),
        source_contract_refs=("source-contract://layer3/g3/default",),
        method_validity_refs=("method-validity://layer3/g3/default",),
        post_intervention_dgp_update_ref=(
            f"pdc://layer3/g3/{request.case_id}/post-intervention-dgp"
        ),
        system_dynamics_handoff_required=True,
    )
    calibrations = build_g3_s11_calibration_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        proof_carrying_analytics_records=proof_records,
    )
    postures = build_g3_s11_predictive_posture_bindings(
        request=request,
        s11_prerequisite_bindings=prereqs,
        s11_calibration_bindings=calibrations,
        proof_carrying_analytics_records=proof_records,
    )
    claim_gate = build_g3_claim_registry_consumer_gate(
        request=request,
        ir_analytics_bridge=bridge,
        proof_carrying_analytics_records=proof_records,
        claims=(_default_g3_claim_registry_claim(request),),
    )
    objective_metric = f"{request.cause.replace('.', '_')}_gain"
    baseline_gate = build_g3_baseline_comparison_consumer_gate(
        request=request,
        claim_ledger=claim_ledger,
        ir_analytics_bridge=bridge,
        selected_option_ref=selected_option_ref,
        selected_option_label="Layer 3 G3 deterministic proof-supported option",
        option_metric_values={
            selected_option_ref: {objective_metric: 0.34},
            alternative_ref: {objective_metric: 0.22},
        },
        objective_directions={objective_metric: "maximize"},
    )
    w12d_gate = build_g3_w12d_consumer_gate(
        case_id=request.case_id,
        s2_design_search=_default_g3_s2_consumer_payload(request, proof_records, postures, bridge),
        s11_predictive_knowledge=_default_g3_s11_consumer_payload(
            proof_records,
            postures,
            bridge,
        ),
        full_s2_consumer_case_refs=(request.case_id,),
    )
    projection_refs = build_g3_public_export_projection_ref_surface(
        certificate_resolution_report=certificate_resolution,
        ir_analytics_search_ledgers=(search_result.ledger,),
        proof_carrying_analytics_records=proof_records,
        ir_analytics_bridge=bridge,
        method_requirement_bindings=method_bindings,
        s11_predictive_posture_bindings=postures,
    )
    audit_surface = build_g3_proof_carrying_audit_surface(
        certificate_resolution_report=certificate_resolution,
        proof_carrying_analytics_records=proof_records,
        ir_analytics_bridge=bridge,
        method_requirement_bindings=method_bindings,
        s11_predictive_posture_bindings=postures,
    )
    adapter_registry = build_g3_adapter_contract_registry_status(repo_root=root)
    adapter_admission = Layer3G3AdapterAdmissionBundle(
        status=adapter_registry.status,
        records=adapter_registry.adapter_admission_records,
        issue_codes=adapter_registry.issue_codes,
    )
    conformance = build_g3_conformance_report(
        root,
        {
            "l2_skg_proof_candidate_bindings": bindings,
            "ir_analytics_search_ledgers": (search_result.ledger,),
            "ir_analytics_query_traces": search_result.query_traces,
            "ir_catalog_coverage": coverage,
            "ir_artifact_store_index": artifact_index,
            "certificate_resolution_report": certificate_resolution,
            "search_recall_freshness": search_recall,
            "search_engineering_quality": search_quality,
            "method_requirement_bindings": method_bindings,
            "proof_carrying_analytics_records": proof_records,
            "ir_analytics_claim_bridge": bridge,
            "s11_prerequisite_bindings": prereqs,
            "s11_calibration_bindings": calibrations,
            "s11_predictive_posture_bindings": postures,
            "claim_registry_consumer_gate": claim_gate,
            "baseline_comparison_consumer_gate": baseline_gate,
            "w12d_consumer_gate": w12d_gate,
            "public_export_projection_refs": projection_refs,
            "proof_carrying_audit_surface": audit_surface,
            "adapter_contract_registry": adapter_registry,
            "adapter_admission_registry": adapter_admission,
        },
    )
    readiness = Layer3G3ReadinessManifest(
        g0_dependency_status=_dependency_file_status(root, "layer3_g0_readiness_manifest.json"),
        g1_dependency_status=_dependency_file_status(root, "layer3_g1_readiness_manifest.json"),
        g2_dependency_status=_dependency_file_status(root, "layer3_g2_readiness_manifest.json"),
        g3_l2_skg_dependency_status=dependencies.status,
        g3_l2_skg_proof_candidate_binding_count=len(bindings),
        g3_ir_catalog_coverage_status=coverage.status,
        g3_ir_artifact_store_index_status=artifact_index.status,
        g3_search_ledger_count=1,
        g3_query_trace_count=len(search_result.query_traces),
        g3_certificate_resolution_status=certificate_resolution.status,
        g3_resolved_certificate_count=certificate_resolution.resolved_certificate_count,
        g3_search_recall_freshness_status=search_recall.status,
        g3_search_recall_seed_count=search_recall.known_seed_count,
        g3_search_recall_recalled_seed_count=search_recall.recalled_seed_count,
        g3_method_requirement_binding_count=len(method_bindings),
        g3_proof_carrying_record_count=sum(
            1 for record in proof_records if record.status == "pass"
        ),
        g3_ir_analytics_bridge_status=bridge.status,
        g3_s11_prerequisite_binding_status=prereqs[0].status if prereqs else "blocked",
        g3_s11_predictive_posture_binding_count=sum(
            1 for posture in postures if posture.status == "pass"
        ),
        g3_claim_registry_consumer_gate_status=claim_gate.status,
        g3_baseline_comparison_consumer_gate_status=baseline_gate.status,
        g3_w12d_consumer_gate_status=w12d_gate.status,
        g3_public_export_projection_status=projection_refs.status,
        g3_search_engineering_quality_status=search_quality.status,
        g3_conformance_status=conformance.status,
        g3_adapter_contract_registry_status=adapter_registry.status,
        g3_adapter_contract_path_count=adapter_registry.adapter_contract_path_count,
    )
    return Layer3G3Bundle(
        adapter_admission_registry=adapter_admission,
        l2_skg_proof_candidate_bindings=bindings,
        ir_analytics_search_ledgers=(search_result.ledger,),
        ir_analytics_query_traces=search_result.query_traces,
        ir_catalog_coverage=coverage,
        ir_artifact_store_index=artifact_index,
        certificate_resolution_report=certificate_resolution,
        search_recall_freshness=search_recall,
        method_requirement_bindings=method_bindings,
        semantic_spine_bindings=semantic_bindings,
        proof_carrying_analytics_records=proof_records,
        ir_analytics_claim_bridge=bridge,
        s11_prerequisite_bindings=prereqs,
        s11_calibration_bindings=calibrations,
        s11_predictive_posture_bindings=postures,
        claim_registry_consumer_gate=claim_gate,
        baseline_comparison_consumer_gate=baseline_gate,
        w12d_consumer_gate=w12d_gate,
        public_export_projection_refs=projection_refs,
        proof_carrying_audit_surface=audit_surface,
        search_engineering_quality=search_quality,
        conformance_report=conformance,
        health_metric_delta=_default_g3_health_metric_delta(),
        adapter_contract_registry=adapter_registry,
        readiness_manifest=readiness,
    )


def validate_layer3_g3_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G3Bundle,
) -> Layer3G3ValidationReport:
    """Validate a G3 bundle or fixture payload with fail-closed issue codes."""

    _ = repo_root
    payload = _dump_model(persisted)
    issues: list[Layer3G3ValidationIssue] = []
    _validate_task1_search(payload, issues)
    _validate_later_task_placeholders(payload, issues)
    _validate_task7_conformance(payload, issues)
    issues = _dedupe_issues(issues)
    summary = dict(_mapping(payload.get("readiness_manifest")))
    summary.update(
        {
            "schema_version": payload.get("schema_version", LAYER3_G3_SCHEMA_VERSION),
            "rule_version": payload.get("rule_version", LAYER3_G3_RULE_VERSION),
            "issue_count": len(issues),
        }
    )
    return Layer3G3ValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary=summary,
        issue_code_dictionary=ALL_ISSUE_CODES,
    )


def produce_g3_deterministic_first_case_certificate(
    request: Layer3G3AnalyticsRequest,
    *,
    store: ArtifactStore,
) -> tuple[Layer3G3CertificateCandidate, ...]:
    """Persist a deterministic typed proof bundle and return a G3 candidate ref."""

    causal_module = importlib.import_module("polisyos.ir.analytics.causal")
    proof_bundle_cls = causal_module.ProofBundle
    persist_proof_bundle = causal_module.persist_proof_bundle

    bundle = proof_bundle_cls(
        proof_status="identified",
        proof_stratum="A0_trusted",
        theorem_family="deterministic_g3_first_case_identification_fixture",
        completeness_regime="complete",
        implementation_coverage="g3_task2_deterministic_first_case",
        graph_ref=f"g3-graph://{request.case_id}",
        query_ref=f"g3-query://{request.claim_id}",
        proof_trace=(
            "candidate produced through public IR ProofBundle persistence helper",
            "G3 search may discover this ref but cannot treat search as authority",
        ),
        composability_status="reusable",
        metadata={
            "schema_version": LAYER3_G3_SCHEMA_VERSION,
            "rule_version": LAYER3_G3_RULE_VERSION,
            "request_ref": request.request_id,
            "claim_id": request.claim_id,
            "case_id": request.case_id,
            "cause": request.cause,
            "effect": request.effect,
            "authority_boundary": {
                "authoritative_for": [],
                "may_not_use_for": list(G3_MAY_NOT_USE_FOR),
            },
        },
    )
    ref = persist_proof_bundle(store, bundle)
    artifact_ref = ref.model_dump(mode="json")
    artifact_id = str(artifact_ref["artifact_id"])
    return (
        Layer3G3CertificateCandidate(
            candidate_id=(
                "g3-certificate-candidate:deterministic-first-case:"
                f"{_stable_id(request.request_id, artifact_id)}"
            ),
            certificate_kind="proof_bundle",
            candidate_ref=f"cas://{artifact_id}",
            source="polisyos.ir.analytics.causal.persist_proof_bundle",
            artifact_ref=artifact_ref,
            artifact_id=artifact_id,
            producer_ref="polisyos.ir.analytics.causal.ProofBundle",
            request_ref=request.request_id,
            claim_id=request.claim_id,
            case_id=request.case_id,
            selected_ref_only=False,
            positive_candidate=True,
            tenant_scope_status="allowed",
            metadata={
                "typed_payload_kind": "ProofBundle",
                "proof_status": "identified",
                "composability_status": "reusable",
            },
        ),
    )


def build_g3_ir_artifact_store_index(
    *,
    store: ArtifactStore | None = None,
    selected_candidates: Sequence[
        Layer3G3CertificateCandidate | Mapping[str, Any]
    ] = (),
    stale: bool = False,
    allow_full_listing: bool = False,
    listing_budget: int = 0,
) -> Layer3G3ArtifactStoreIndex:
    """Build a selected-ref CAS index without eager-walking arbitrary artifacts."""

    candidates = tuple(
        _coerce_certificate_candidate(candidate) for candidate in selected_candidates
    )
    issue_codes: list[str] = []
    indexed_refs: list[str] = []
    manifest_refs: list[str] = []
    payload_fingerprints: list[str] = []
    tenant_status = "allowed" if candidates else "unknown"
    store_backend, store_root = _store_identity(store)
    full_listing_used = False
    listing_cutoff_reached = False

    if stale:
        issue_codes.append("layer3_g3_stale_artifact_index_claimed_as_proof_ceiling")
    if any(candidate.tenant_scope_status == "denied" for candidate in candidates):
        tenant_status = "denied"
        issue_codes.append("layer3_g3_tenant_scoped_manifest_denied")
    if store is None and not candidates:
        issue_codes.append("layer3_g3_certificate_resolution_missing")
        snapshot = _json_hash_ref(
            {
                "store_backend": "not_configured",
                "selected_candidate_count": 0,
                "stale": stale,
                "issue_codes": issue_codes,
            }
        )
        return Layer3G3ArtifactStoreIndex(
            status="not_configured",
            store_backend="not_configured",
            store_root_ref=None,
            index_scope="not_configured",
            selected_candidate_count=0,
            snapshot_hash_ref=snapshot,
            stale=stale,
            tenant_scope_status=tenant_status,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
        )

    if allow_full_listing:
        full_listing_used = True
        issue_codes.append("layer3_g3_full_cas_listing_in_request_path")
        if store is not None and listing_budget > 0:
            listed_ids = tuple(str(artifact_id) for artifact_id in store.iter_artifact_ids())
            listing_cutoff_reached = len(listed_ids) > listing_budget
            for artifact_id in listed_ids[:listing_budget]:
                indexed_refs.append(artifact_id)
                manifest_refs.append(f"cas-manifest://{artifact_id}")
                payload_fingerprints.append(artifact_id)

    for candidate in candidates:
        artifact_id = _candidate_artifact_id(candidate)
        if artifact_id is None:
            continue
        indexed_refs.append(artifact_id)
        manifest_refs.append(f"cas-manifest://{artifact_id}")
        payload_fingerprints.append(artifact_id)
        if store is None:
            continue
        try:
            manifest = store.get_manifest(artifact_id)
            manifest_refs.append(_manifest_ref(artifact_id, manifest))
        except PermissionError:
            tenant_status = "denied"
            issue_codes.append("layer3_g3_tenant_scoped_manifest_denied")
        except Exception:
            issue_codes.append("layer3_g3_persisted_artifact_missing")

    snapshot = _json_hash_ref(
        {
            "store_backend": store_backend,
            "store_root_ref": store_root,
            "indexed_artifact_refs": sorted(dict.fromkeys(indexed_refs)),
            "manifest_refs": sorted(dict.fromkeys(manifest_refs)),
            "payload_fingerprint_refs": sorted(dict.fromkeys(payload_fingerprints)),
            "selected_candidate_count": len(candidates),
            "full_listing_used": full_listing_used,
            "listing_budget": listing_budget,
            "listing_cutoff_reached": listing_cutoff_reached,
            "stale": stale,
            "tenant_scope_status": tenant_status,
            "issue_codes": issue_codes,
        }
    )
    status: Literal["pass", "fail", "blocked", "not_configured"]
    if tenant_status == "denied":
        status = "blocked"
    elif issue_codes:
        status = "fail"
    else:
        status = "pass"
    return Layer3G3ArtifactStoreIndex(
        status=status,
        store_backend=store_backend,
        store_root_ref=store_root,
        index_scope="bounded_listing" if full_listing_used else "selected_refs",
        selected_candidate_count=len(candidates),
        indexed_artifact_refs=tuple(dict.fromkeys(indexed_refs)),
        manifest_refs=tuple(dict.fromkeys(manifest_refs)),
        payload_fingerprint_refs=tuple(dict.fromkeys(payload_fingerprints)),
        snapshot_hash_ref=snapshot,
        full_listing_used=full_listing_used,
        listing_budget=listing_budget,
        listing_cutoff_reached=listing_cutoff_reached,
        stale=stale,
        tenant_scope_status=tenant_status,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def resolve_g3_certificate_candidates(
    *,
    candidates: Sequence[Layer3G3CertificateCandidate | Mapping[str, Any]] = (),
    artifact_index: Layer3G3ArtifactStoreIndex | Mapping[str, Any] | None = None,
    store: ArtifactStore | None = None,
) -> tuple[Layer3G3CertificateResolutionRecord, ...]:
    """Resolve candidate refs to existing typed IR proof/certificate payloads."""

    resolved_candidates = tuple(
        _coerce_certificate_candidate(candidate) for candidate in candidates
    )
    index_payload = _dump_model(artifact_index) if isinstance(artifact_index, BaseModel) else (
        dict(artifact_index) if isinstance(artifact_index, Mapping) else {}
    )
    if index_payload.get("stale"):
        return tuple(
            _resolution_failure(
                candidate,
                issue_codes=("layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",),
            )
            for candidate in resolved_candidates
        )
    return tuple(
        _resolve_one_certificate_candidate(candidate, store)
        for candidate in resolved_candidates
    )


def build_g3_certificate_resolution_report(
    *,
    candidates: Sequence[Layer3G3CertificateCandidate | Mapping[str, Any]] = (),
    artifact_index: Layer3G3ArtifactStoreIndex | Mapping[str, Any] | None = None,
    store: ArtifactStore | None = None,
) -> Layer3G3CertificateResolutionReport:
    """Build the aggregate G3 certificate-resolution report."""

    records = resolve_g3_certificate_candidates(
        candidates=candidates,
        artifact_index=artifact_index,
        store=store,
    )
    index_payload = _dump_model(artifact_index) if isinstance(artifact_index, BaseModel) else (
        dict(artifact_index) if isinstance(artifact_index, Mapping) else {}
    )
    issue_codes = [
        str(code)
        for code in (
            *tuple(_sequence(index_payload.get("issue_codes"))),
            *(code for record in records for code in record.issue_codes),
        )
    ]
    resolved_records = tuple(record for record in records if record.payload_fingerprint_ref)
    positive_records = tuple(record for record in resolved_records if record.positive_proof_closure)
    blocking_records = tuple(record for record in resolved_records if record.blocking)
    limiting_records = tuple(record for record in resolved_records if record.limiting)
    if not records or not (positive_records or blocking_records or limiting_records):
        issue_codes.append("layer3_g3_certificate_resolution_missing")
    if any(record.status == "fail" for record in records):
        issue_codes.append("layer3_g3_certificate_resolution_missing")

    issue_codes = list(dict.fromkeys(issue_codes))
    if (
        "layer3_g3_tenant_scoped_manifest_denied" in issue_codes
        or blocking_records
        or limiting_records
    ) and not positive_records:
        status: Literal["pass", "fail", "blocked"] = "blocked"
    elif positive_records and not any(record.status == "fail" for record in records):
        status = "pass"
    else:
        status = "fail"
    if "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling" in issue_codes:
        status = "fail"

    return Layer3G3CertificateResolutionReport(
        status=status,
        records=records,
        resolved_certificate_count=len(resolved_records),
        positive_resolved_certificate_count=len(positive_records),
        blocking_certificate_count=len(blocking_records),
        limiting_certificate_count=len(limiting_records),
        selected_candidate_count=len(tuple(candidates)),
        no_hit_count=0 if candidates else 1,
        full_listing_used=bool(index_payload.get("full_listing_used", False)),
        stale_artifact_index=bool(index_payload.get("stale", False)),
        payload_fingerprint_refs=tuple(
            dict.fromkeys(
                record.payload_fingerprint_ref
                for record in resolved_records
                if record.payload_fingerprint_ref
            )
        ),
        issue_codes=tuple(issue_codes),
    )


def build_g3_search_recall_freshness(
    *,
    dependencies: Layer3G3L2SkgDependencyArtifacts | Mapping[str, Any] | None = None,
    ir_catalog_coverage: Layer3G3IRCatalogCoverageReport | Mapping[str, Any] | None = None,
    search_ledgers: Sequence[Layer3G3IRCatalogSearchLedger | Mapping[str, Any]] = (),
    query_traces: Sequence[Layer3G3IRAnalyticsQueryTrace | Mapping[str, Any]] = (),
    ir_artifact_store_index: Layer3G3ArtifactStoreIndex | Mapping[str, Any] | None = None,
    certificate_resolution_report: (
        Layer3G3CertificateResolutionReport | Mapping[str, Any] | None
    ) = None,
) -> Layer3G3SearchRecallFreshnessReport:
    """Replay known G3 seeds before allowing proof-domain ceiling claims."""

    dependency_payload = _dump_model(dependencies) if dependencies is not None else {}
    coverage_payload = (
        _dump_model(ir_catalog_coverage) if ir_catalog_coverage is not None else {}
    )
    artifact_payload = (
        _dump_model(ir_artifact_store_index) if ir_artifact_store_index is not None else {}
    )
    certificate_payload = (
        _dump_model(certificate_resolution_report)
        if certificate_resolution_report is not None
        else {}
    )
    ledger_payloads = tuple(_dump_model(ledger) for ledger in search_ledgers)
    trace_payloads = tuple(_dump_model(trace) for trace in query_traces)

    dependency_recall = _mapping(dependency_payload.get("recall_freshness"))
    dependency_ledger_refs = tuple(
        str(ledger.get("ledger_id"))
        for ledger in _sequence(dependency_payload.get("search_ledgers"))
        if ledger.get("ledger_id")
    )
    dependency_trace_refs = tuple(
        str(trace.get("trace_id"))
        for trace in _sequence(dependency_payload.get("query_traces"))
        if trace.get("trace_id")
    )
    dependency_loaded_refs = tuple(
        str(ref) for ref in _sequence(dependency_payload.get("loaded_artifact_paths"))
    )
    l2_seed_pass = (
        dependency_payload.get("status") == "pass"
        and dependency_payload.get("canonical_l2_route") == CANONICAL_G2_L2_ROUTE
        and bool(dependency_ledger_refs)
        and bool(dependency_trace_refs)
        and dependency_recall.get("status") == "pass"
        and dependency_recall.get("search_recall_status") == "pass"
        and dependency_recall.get("index_freshness_status") == "pass"
    )

    search_ledger_refs = tuple(
        str(ledger.get("ledger_id")) for ledger in ledger_payloads if ledger.get("ledger_id")
    )
    trace_refs = tuple(
        str(trace.get("trace_id")) for trace in trace_payloads if trace.get("trace_id")
    )
    trace_ref_set = set(trace_refs)
    ledger_trace_refs = tuple(
        str(ref)
        for ledger in ledger_payloads
        for ref in _sequence(ledger.get("query_trace_refs"))
        if str(ref)
    )
    selected_candidate_refs = tuple(
        str(ref)
        for ledger in ledger_payloads
        for ref in _sequence(ledger.get("selected_candidate_refs"))
        if str(ref)
    )
    catalog_snapshot_hash_ref = str(coverage_payload.get("catalog_snapshot_hash_ref") or "")
    ir_seed_pass = (
        coverage_payload.get("status") == "pass"
        and coverage_payload.get("full_catalog_route") not in FORBIDDEN_FULL_CATALOG_ROUTES
        and coverage_payload.get("catalog_backend") == IR_CATALOG_BACKEND
        and bool(catalog_snapshot_hash_ref)
        and bool(search_ledger_refs)
        and bool(trace_refs)
        and bool(selected_candidate_refs)
        and all(ref in trace_ref_set for ref in ledger_trace_refs)
    )

    payload_fingerprint_refs = tuple(
        str(ref)
        for ref in _sequence(certificate_payload.get("payload_fingerprint_refs"))
        if str(ref)
    )
    resolution_record_refs = tuple(
        str(record.get("record_id"))
        for record in _sequence(certificate_payload.get("records"))
        if _mapping(record).get("record_id")
    )
    artifact_snapshot_hash_ref = str(artifact_payload.get("snapshot_hash_ref") or "")
    certificate_seed_pass = (
        certificate_payload.get("status") == "pass"
        and int(certificate_payload.get("resolved_certificate_count") or 0) > 0
        and bool(payload_fingerprint_refs)
        and artifact_payload.get("status") == "pass"
        and bool(artifact_snapshot_hash_ref)
        and not bool(artifact_payload.get("stale"))
        and not bool(certificate_payload.get("stale_artifact_index"))
    )

    freshness_pass = (
        l2_seed_pass
        and ir_seed_pass
        and certificate_seed_pass
        and not bool(artifact_payload.get("full_listing_used"))
        and not bool(certificate_payload.get("full_listing_used"))
    )

    seed_records = (
        Layer3G3SearchRecallSeedRecord(
            seed_id="g3-known-seed:l2-skg-proof-candidate-route",
            seed_kind="l2_skg_dependency",
            status="pass" if l2_seed_pass else "fail",
            expected_route=CANONICAL_G2_L2_ROUTE,
            evidence_refs=_dedupe(
                [
                    *dependency_loaded_refs,
                    *dependency_ledger_refs,
                    *dependency_trace_refs,
                ]
            ),
            issue_codes=()
            if l2_seed_pass
            else ("layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",),
        ),
        Layer3G3SearchRecallSeedRecord(
            seed_id="g3-known-seed:ir-analytics-proof-catalog",
            seed_kind="ir_catalog_search",
            status="pass" if ir_seed_pass else "fail",
            expected_route=IR_CATALOG_ROUTE,
            evidence_refs=_dedupe(
                [
                    catalog_snapshot_hash_ref,
                    *search_ledger_refs,
                    *trace_refs,
                    *selected_candidate_refs,
                ]
            ),
            issue_codes=()
            if ir_seed_pass
            else ("layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",),
        ),
        Layer3G3SearchRecallSeedRecord(
            seed_id="g3-known-seed:resolved-proof-certificate",
            seed_kind="certificate_resolution",
            status="pass" if certificate_seed_pass else "fail",
            expected_route="ir_artifact_store:selected_refs",
            evidence_refs=_dedupe(
                [
                    artifact_snapshot_hash_ref,
                    *resolution_record_refs,
                    *payload_fingerprint_refs,
                ]
            ),
            issue_codes=()
            if certificate_seed_pass
            else ("layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",),
        ),
    )
    recalled_seed_count = sum(1 for seed in seed_records if seed.status == "pass")
    known_seed_count = len(seed_records)
    missed_seed_count = known_seed_count - recalled_seed_count
    issue_codes: list[str] = []
    if missed_seed_count:
        issue_codes.append("layer3_g3_search_recall_seed_miss_blocks_domain_ceiling")
    if not freshness_pass:
        issue_codes.append("layer3_g3_search_ceiling_repair_required")

    return Layer3G3SearchRecallFreshnessReport(
        status="pass" if recalled_seed_count == known_seed_count and freshness_pass else "fail",
        freshness_status="pass" if freshness_pass else "fail",
        l2_skg_seed_status="pass" if l2_seed_pass else "fail",
        ir_catalog_seed_status="pass" if ir_seed_pass else "fail",
        certificate_resolution_seed_status="pass" if certificate_seed_pass else "fail",
        known_seed_count=known_seed_count,
        recalled_seed_count=recalled_seed_count,
        missed_seed_count=missed_seed_count,
        seed_records=seed_records,
        catalog_snapshot_hash_ref=catalog_snapshot_hash_ref or None,
        artifact_snapshot_hash_ref=artifact_snapshot_hash_ref or None,
        search_ledger_refs=search_ledger_refs,
        query_trace_refs=trace_refs,
        payload_fingerprint_refs=payload_fingerprint_refs,
        freshness_evidence_refs=_dedupe(
            [
                *dependency_loaded_refs,
                catalog_snapshot_hash_ref,
                artifact_snapshot_hash_ref,
                *payload_fingerprint_refs,
            ]
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g3_method_requirement_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    repo_root: Path | None = None,
    method_requirements: Sequence[Mapping[str, Any] | BaseModel] = (),
    selected_method_refs: Sequence[str] = (),
) -> tuple[Layer3G3MethodRequirementBinding, ...]:
    """Build claim-bound G3 method requirements from G2 or W7.C compiler output."""

    if request is None:
        return ()
    explicit_requirements = tuple(method_requirements)
    source_route: Literal["g2_method_requirement_bindings", "w7c_compiler", "explicit"]
    source_bindings: tuple[dict[str, Any], ...] = ()
    selected_refs = tuple(str(ref) for ref in selected_method_refs if str(ref))
    rejected_refs: tuple[str, ...] = ()
    authority_boundary: dict[str, Any] = {}
    if explicit_requirements:
        source_route = "explicit"
        raw_specs = explicit_requirements
    else:
        source_bindings = _load_g2_method_requirement_bindings(repo_root)
        if source_bindings:
            source_route = "g2_method_requirement_bindings"
            first = source_bindings[0]
            raw_specs = tuple(_sequence(first.get("method_requirement_specs")))
            selected_refs = selected_refs or _string_tuple(first.get("selected_method_refs"))
            rejected_refs = _string_tuple(first.get("rejected_method_refs"))
            authority_boundary = dict(_mapping(first.get("authority_boundary")))
        else:
            source_route = "w7c_compiler"
            raw_specs = tuple(_compile_g3_fallback_method_requirements(request))

    specs = tuple(_adapt_method_requirement_spec(spec, request) for spec in raw_specs)
    refs = tuple(str(spec.get("requirement_id")) for spec in specs if spec.get("requirement_id"))
    issue_codes: list[str] = []
    if not specs or not refs:
        issue_codes.append("layer3_g3_method_requirement_missing")
    if not authority_boundary:
        authority_boundary = _method_requirement_authority_boundary()
    return (
        Layer3G3MethodRequirementBinding(
            binding_id=f"g3-method-requirement-binding:{_stable_id(request.request_id, *refs)}",
            status="pass" if not issue_codes else "fail",
            request_ref=request.request_id,
            claim_id=request.claim_id,
            source_route=source_route,
            method_requirement_specs=specs,
            method_requirement_refs=refs,
            selected_method_refs=selected_refs,
            rejected_method_refs=rejected_refs,
            source_binding_refs=tuple(
                str(binding.get("binding_id"))
                for binding in source_bindings
                if str(binding.get("binding_id", "")).strip()
            ),
            authority_boundary=authority_boundary,
            issue_codes=tuple(issue_codes),
            may_not_use_for=_merge_g3_denials(
                _sequence(authority_boundary.get("may_not_use_for"))
            ),
        ),
    )


def build_g3_semantic_spine_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    method_requirement_bindings: Sequence[Layer3G3MethodRequirementBinding] = (),
    certificate_resolution_report: Layer3G3CertificateResolutionReport | None = None,
) -> tuple[Layer3G3SemanticSpineBinding, ...]:
    """Carry semantic-spine refs into the G3 proof/bridge binding path."""

    if request is None:
        return ()
    method_refs = tuple(
        ref for binding in method_requirement_bindings for ref in binding.method_requirement_refs
    ) or request.method_requirement_refs
    certificate_refs = tuple(
        ref
        for record in (
            certificate_resolution_report.records
            if certificate_resolution_report is not None
            else ()
        )
        for ref in (record.artifact_id, record.payload_fingerprint_ref)
        if ref
    )
    issue_codes = ()
    if not method_refs:
        issue_codes = ("layer3_g3_method_requirement_missing",)
    return (
        Layer3G3SemanticSpineBinding(
            binding_id=f"g3-semantic-spine-binding:{_stable_id(request.request_id)}",
            status="pass" if not issue_codes else "fail",
            request_ref=request.request_id,
            claim_id=request.claim_id,
            concept_refs=request.concept_refs,
            semantic_spine_refs=request.semantic_spine_refs,
            method_requirement_refs=method_refs,
            certificate_refs=tuple(dict.fromkeys(certificate_refs)),
            issue_codes=issue_codes,
        ),
    )


def build_g3_proof_carrying_analytics_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    certificate_resolution_report: Layer3G3CertificateResolutionReport | None = None,
    method_requirement_bindings: Sequence[Layer3G3MethodRequirementBinding] = (),
    semantic_spine_bindings: Sequence[Layer3G3SemanticSpineBinding] = (),
) -> tuple[Layer3G3ProofCarryingAnalyticsBinding, ...]:
    """Build S11 proof-carrying analytics records from resolved G3 certificates."""

    if request is None:
        return ()
    report = certificate_resolution_report
    if report is None or report.positive_resolved_certificate_count <= 0:
        issue_codes = list(report.issue_codes if report is not None else ())
        if report is not None and report.selected_candidate_count > 0:
            issue_codes.append("layer3_g3_search_hit_laundered_as_certificate")
        for record in report.records if report is not None else ():
            if str(record.artifact_id or "").startswith("certificate://"):
                issue_codes.append("layer3_g3_fixture_certificate_laundered")
        issue_codes.append("layer3_g3_proof_carrying_record_missing")
        return (
            Layer3G3ProofCarryingAnalyticsBinding(
                binding_id=(
                    "g3-proof-carrying-analytics-binding:"
                    f"{_stable_id(request.request_id, 'fail')}"
                ),
                status="fail",
                request_ref=request.request_id,
                claim_id=request.claim_id,
                issue_codes=tuple(dict.fromkeys(issue_codes)),
            ),
        )

    method_refs = tuple(
        ref for binding in method_requirement_bindings for ref in binding.method_requirement_refs
    ) or request.method_requirement_refs
    method_output_refs = tuple(
        ref for binding in method_requirement_bindings for ref in binding.selected_method_refs
    )
    semantic_refs = tuple(
        ref for binding in semantic_spine_bindings for ref in binding.semantic_spine_refs
    ) or request.semantic_spine_refs
    uncertainty_refs = _g3_deterministic_uncertainty_refs(
        request=request,
        method_requirement_bindings=method_requirement_bindings,
    )
    bindings: list[Layer3G3ProofCarryingAnalyticsBinding] = []
    for record in report.records:
        if not record.positive_proof_closure or not record.payload_fingerprint_ref:
            continue
        certificate_ref = record.artifact_id or record.payload_fingerprint_ref
        proof_ref = f"pdc://layer3/g3/{request.case_id}/proof/{_stable_id(record.record_id)}"
        bridge_ref = f"ir-analytics-bridge://layer3/g3/{_stable_id(request.claim_id)}"
        payload = {
            "proof_id": f"layer3.g3.proof.{_stable_id(request.request_id, record.record_id)}",
            "proof_ref": proof_ref,
            "case_id": request.case_id,
            "claim_id": request.claim_id,
            "design_comparison_ref": (
                request.comparison_ref or f"comparison://layer3/g3/{request.case_id}"
            ),
            "baseline_design_ref": request.baseline_ref or f"baseline://layer3/g3/{request.case_id}",
            "alternative_design_refs": list(request.alternative_refs),
            "ir_analytics_refs": [certificate_ref],
            "method_output_refs": list(method_output_refs),
            "ir_certificate_refs": [certificate_ref],
            "negative_certificate_refs": [],
            "proof_status": "identified",
            "proof_composability_status": "reusable",
            "proof_composability_refs": [],
            "method_requirement_refs": list(method_refs),
            "uncertainty_refs": list(uncertainty_refs),
            "independence_refs": [f"independence://layer3/g3/{request.claim_id}"],
            "effective_independence_collapse_refs": [],
            "counter_evidence_refs": [],
            "limitation_refs": [],
            "blocker_refs": [],
            "ir_analytics_bridge_ref": bridge_ref,
            "claim_registry_entry_ref": f"claim-registry://layer3/g3/{request.claim_id}",
            "comparison_consumer_ref": (
                request.comparison_ref or f"comparison://layer3/g3/{request.case_id}"
            ),
            "source_lineage_refs": tuple(
                ref
                for ref in (
                    record.source,
                    record.loader_ref,
                    record.artifact_id,
                    record.payload_fingerprint_ref,
                )
                if ref
            ),
            "method_lineage_refs": [*method_output_refs, *method_refs, *semantic_refs],
        }
        try:
            from polisyos.runtime.quality.layer2_predictive_knowledge import (
                build_proof_carrying_analytics_record,
            )

            s11_record = build_proof_carrying_analytics_record(**payload)
        except Exception:
            bindings.append(
                Layer3G3ProofCarryingAnalyticsBinding(
                    binding_id=(
                        "g3-proof-carrying-analytics-binding:"
                        f"{_stable_id(request.request_id, record.record_id, 'fail')}"
                    ),
                    status="fail",
                    request_ref=request.request_id,
                    claim_id=request.claim_id,
                    certificate_resolution_record_refs=(record.record_id,),
                    ir_certificate_refs=(certificate_ref,),
                    method_requirement_refs=method_refs,
                    method_output_refs=method_output_refs,
                    issue_codes=("layer3_g3_proof_carrying_record_missing",),
                )
            )
            continue
        s11_payload = s11_record.model_dump(mode="json")
        bindings.append(
            Layer3G3ProofCarryingAnalyticsBinding(
                binding_id=(
                    "g3-proof-carrying-analytics-binding:"
                    f"{_stable_id(request.request_id, record.record_id)}"
                ),
                status="pass",
                request_ref=request.request_id,
                claim_id=request.claim_id,
                proof_ref=s11_record.proof_ref,
                bridge_ref=s11_record.ir_analytics_bridge_ref,
                certificate_resolution_record_refs=(record.record_id,),
                method_requirement_refs=tuple(s11_record.method_requirement_refs),
                ir_certificate_refs=tuple(s11_record.ir_certificate_refs),
                method_output_refs=tuple(s11_record.method_output_refs),
                uncertainty_refs=tuple(s11_record.uncertainty_refs),
                s11_record=s11_payload,
                may_not_use_for=tuple(s11_record.may_not_use_for),
            )
        )
    if not bindings:
        return (
            Layer3G3ProofCarryingAnalyticsBinding(
                binding_id=(
                    "g3-proof-carrying-analytics-binding:"
                    f"{_stable_id(request.request_id, 'missing')}"
                ),
                status="fail",
                request_ref=request.request_id,
                claim_id=request.claim_id,
                issue_codes=("layer3_g3_proof_carrying_record_missing",),
            ),
        )
    return tuple(bindings)


def build_g3_ir_analytics_bridge_bindings(
    *,
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
    method_requirement_bindings: Sequence[Layer3G3MethodRequirementBinding] = (),
    claim_bindings: Sequence[Mapping[str, Any]] = (),
) -> Layer3G3IRAnalyticsBridgeBinding:
    """Build the existing IR analytics bridge from G3/S11 proof bindings."""

    rows = [dict(row) for row in claim_bindings]
    if not rows:
        rows = [
            _claim_binding_from_g3_proof_binding(binding)
            for binding in proof_carrying_analytics_records
            if _mapping(_dump_model(binding)).get("status") == "pass"
        ]
    if not rows:
        return Layer3G3IRAnalyticsBridgeBinding(
            status="fail",
            issue_codes=("layer3_g3_ir_analytics_bridge_missing",),
        )
    raw_missing_claim_id = any(not str(row.get("claim_id", "")).strip() for row in rows)
    method_specs = tuple(
        spec
        for binding in method_requirement_bindings
        for spec in binding.method_requirement_specs
    )
    bridge_ref = _first_present_str(
        _mapping(_dump_model(binding)).get("bridge_ref")
        for binding in proof_carrying_analytics_records
    )
    from polisyos.runtime.quality.ir_analytics_bridge import build_ir_analytics_claim_bridge

    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=rows,
        method_requirements=method_specs,
        run_id=f"layer3-g3-{_stable_id(*[str(row.get('claim_id', '')) for row in rows])}",
        bridge_ref=bridge_ref,
    )
    if raw_missing_claim_id:
        bridge = dict(bridge)
        issues = list(_sequence(bridge.get("issues")))
        issues.append(
            {
                "code": "runtime_claim_registry_ir_analytics_claim_id_missing",
                "severity": "fail",
                "claim_id": "",
                "missing_evidence_type": "claim_id",
                "message": "G3 IR analytics bridge input row has no claim_id.",
                "next_action": "Bind each resolved G3 proof record to a concrete claim id.",
            }
        )
        bridge["issues"] = issues
        bridge["status"] = "fail"
    issue_codes = _g3_issue_codes_from_ir_bridge(bridge)
    return Layer3G3IRAnalyticsBridgeBinding(
        status="pass" if bridge.get("status") == "pass" and not issue_codes else "fail",
        bridge_ref=str(bridge.get("ir_analytics_bridge_ref") or ""),
        claim_binding_count=int(_mapping(bridge.get("summary")).get("binding_count", 0) or 0),
        method_requirement_binding_count=int(
            _mapping(bridge.get("summary")).get("method_requirement_binding_count", 0) or 0
        ),
        bridge_payload=dict(bridge),
        issue_codes=issue_codes,
    )


def build_g3_s11_prerequisite_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    repo_root: Path | None = None,
    s6_floor_status_refs: Sequence[str] = (),
    s6_axis_rows: Sequence[Mapping[str, Any] | BaseModel] = (),
    s6_bridge_consumer_rows: Sequence[Mapping[str, Any] | BaseModel] = (),
    s6_constraint_store_update_refs: Sequence[str] = (),
    s6_c3_authority_dimension_refs: Sequence[str] = (),
    post_intervention_dgp_update_ref: str | None = None,
    system_dynamics_handoff_required: bool = False,
    s10_forecast_support_ref: str | None = None,
    s10_forecast_tier: str | None = None,
    s10_forecast_calibration_record_ref: str | None = None,
    source_contract_refs: Sequence[str] = (),
    method_validity_refs: Sequence[str] = (),
) -> tuple[Layer3G3S11PrerequisiteBinding, ...]:
    """Bind S6 floors and G2/S10 forecast support before any S11 posture."""

    if request is None:
        return ()
    g2_binding = _load_g2_forecast_support_binding(repo_root)
    s10_support = _mapping(g2_binding.get("s10_forecast_support"))
    authority_envelope = _mapping(g2_binding.get("authority_envelope"))
    resolved_s10_ref = _first_present_str(
        (
            s10_forecast_support_ref,
            g2_binding.get("s10_forecast_support_ref"),
            s10_support.get("support_ref"),
            authority_envelope.get("forecast_support_ref"),
        )
    )
    resolved_tier = _first_present_str(
        (
            s10_forecast_tier,
            g2_binding.get("s10_forecast_tier"),
            s10_support.get("forecast_tier"),
            authority_envelope.get("forecast_tier"),
        )
    )
    resolved_calibration_ref = _first_present_str(
        (
            s10_forecast_calibration_record_ref,
            g2_binding.get("calibration_record_ref"),
            s10_support.get("calibration_record_ref"),
            authority_envelope.get("calibration_record_ref"),
        )
    )
    resolved_source_refs = _dedupe(
        [
            *source_contract_refs,
            *_sequence(g2_binding.get("source_contract_refs")),
            str(s10_support.get("source_contract_ref", "")),
            str(authority_envelope.get("source_contract_ref", "")),
        ]
    )
    if not resolved_source_refs and resolved_s10_ref:
        resolved_source_refs = (f"source-contract://layer3/g3/{request.case_id}",)
    resolved_method_refs = _dedupe(
        [
            *method_validity_refs,
            *_sequence(g2_binding.get("method_validity_refs")),
            str(s10_support.get("method_validity_ref", "")),
            str(authority_envelope.get("method_validity_ref", "")),
            *request.method_requirement_refs,
        ]
    )
    if not resolved_method_refs and resolved_s10_ref:
        resolved_method_refs = (f"method-validity://layer3/g3/{request.case_id}",)

    floor_refs = _dedupe(s6_floor_status_refs)
    issue_codes: list[str] = []
    if not floor_refs or not resolved_s10_ref:
        issue_codes.append("layer3_g3_s11_prerequisite_missing")
    if g2_binding and str(g2_binding.get("status", "pass")) != "pass":
        issue_codes.append("layer3_g3_s11_prerequisite_missing")
    return (
        Layer3G3S11PrerequisiteBinding(
            binding_id=f"g3-s11-prerequisite-binding:{_stable_id(request.request_id)}",
            status="pass" if not issue_codes else "blocked",
            request_ref=request.request_id,
            case_id=request.case_id,
            claim_id=request.claim_id,
            s6_floor_status_refs=floor_refs,
            s6_axis_rows=_dict_rows(s6_axis_rows),
            s6_bridge_consumer_rows=_dict_rows(s6_bridge_consumer_rows),
            s6_constraint_store_update_refs=_dedupe(s6_constraint_store_update_refs),
            s6_c3_authority_dimension_refs=_dedupe(s6_c3_authority_dimension_refs),
            post_intervention_dgp_update_ref=post_intervention_dgp_update_ref,
            system_dynamics_handoff_required=system_dynamics_handoff_required,
            s10_forecast_support_ref=resolved_s10_ref,
            s10_forecast_tier=resolved_tier,
            s10_forecast_calibration_record_ref=resolved_calibration_ref,
            g2_forecast_support_binding_ref=str(g2_binding.get("binding_id") or "")
            or None,
            source_contract_refs=resolved_source_refs,
            method_validity_refs=resolved_method_refs,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
        ),
    )


def build_g3_s11_calibration_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    s11_prerequisite_bindings: Sequence[
        Layer3G3S11PrerequisiteBinding | Mapping[str, Any]
    ] = (),
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
    axis: str = "measurability",
    cell_ref: str = "SYSTEM.measurability",
    calibration_status: str = "pass",
    floor_passed: bool = True,
    denominator: int = 4,
    numerator: int | None = None,
    effective_maturity: str = "predictive",
    relaxation_decision: str = "relaxed_to_predictive",
    forecast_quality_disposition: str = "unchanged_s10_tier_consumed",
    calibration_authority_boundary: Mapping[str, Any] | None = None,
) -> tuple[Layer3G3S11CalibrationBinding, ...]:
    """Build G3-bound S11 calibration and maturity-upgrade records."""

    if request is None:
        return ()
    prereq = _first_pass_s11_prerequisite(s11_prerequisite_bindings)
    if prereq is None:
        return (
            _blocked_g3_s11_calibration(
                request,
                axis=axis,
                cell_ref=cell_ref,
                issue_codes=(
                    "layer3_g3_s11_prerequisite_missing",
                    "layer3_g3_s11_posture_without_s6_s10",
                ),
            ),
        )
    proof = _first_pass_g3_proof_binding(proof_carrying_analytics_records)
    proof_ref = str(proof.get("proof_ref") or "")
    if relaxation_decision == "relaxed_to_predictive" and not proof_ref:
        return (
            _blocked_g3_s11_calibration(
                request,
                axis=axis,
                cell_ref=cell_ref,
                s6_floor_record_ref=_first_present_str(prereq.s6_floor_status_refs),
                s10_forecast_support_ref=prereq.s10_forecast_support_ref,
                issue_codes=(
                    "layer3_g3_s11_predictive_upgrade_missing_proof",
                    "layer3_g3_proof_carrying_record_missing",
                ),
            ),
        )

    proof_record = _mapping(proof.get("s11_record"))
    calibration_numerator = denominator if numerator is None else numerator
    timestamp = datetime.now(UTC)
    calibration_ref = f"pdc://layer3/g3/{request.case_id}/s11/calibration/{axis}"
    upgrade_ref = f"pdc://layer3/g3/{request.case_id}/s11/axis-upgrade/{axis}"
    source_contract_ref = _first_present_str(prereq.source_contract_refs) or (
        f"source-contract://layer3/g3/{request.case_id}"
    )
    method_validity_ref = _first_present_str(prereq.method_validity_refs) or (
        request.method_requirement_refs[0]
        if request.method_requirement_refs
        else f"method-validity://layer3/g3/{request.case_id}"
    )
    try:
        from polisyos.runtime.quality.layer2_predictive_knowledge import (
            build_predictive_axis_calibration_record,
            build_predictive_axis_upgrade_record,
            summarize_s11_predictive_knowledge_integrity,
            verify_s11_predictive_knowledge_authority_envelope,
        )

        calibration = build_predictive_axis_calibration_record(
            calibration_id=f"layer3.g3.s11.calibration.{_stable_id(request.request_id, axis)}",
            calibration_ref=calibration_ref,
            case_id=request.case_id,
            axis=axis,
            cell_ref=cell_ref,
            s6_floor_record_ref=prereq.s6_floor_status_refs[0],
            s10_forecast_support_ref=prereq.s10_forecast_support_ref,
            s10_forecast_calibration_record_ref=(
                prereq.s10_forecast_calibration_record_ref
            ),
            calibration_ledger_ref=f"calibration-ledger://layer3/g3/{request.case_id}",
            calibration_scope_ref=f"scope://layer3/g3/{request.case_id}/current",
            prediction_context_ref=f"pdc://layer3/g3/{request.case_id}/prediction-context",
            policy_context_ref="policy-context://ua-msme/2022/current",
            model_family="layer3_g3_ir_analytics_search",
            source_contract_ref=source_contract_ref,
            method_validity_ref=method_validity_ref,
            method_infrastructure_refs=[method_validity_ref],
            source_lineage_refs=[source_contract_ref],
            method_lineage_refs=list(prereq.method_validity_refs),
            effective_independence_refs=[
                f"independence://layer3/g3/{request.claim_id}"
            ],
            sensitivity_analysis_ref=f"sensitivity://layer3/g3/{request.case_id}/{axis}",
            credible_evaluation_evidence_ref=(
                f"evidence://layer3/g3/{request.case_id}/credible-evaluation"
            ),
            counterfactual_credibility_ref=(
                f"counterfactual://layer3/g3/{request.case_id}/credibility"
            ),
            prediction_time=timestamp,
            observation_time=timestamp,
            policy_effective_time=timestamp,
            data_valid_time=timestamp,
            calibration_window_start=timestamp,
            calibration_window_end=timestamp,
            denominator=denominator,
            numerator=calibration_numerator,
            pass_rate=calibration_numerator / denominator if denominator else 0.0,
            threshold=0.75,
            threshold_ref=(
                "repo://architecture/policy_design_case/"
                "layer2_floor_governance.toml#s11"
            ),
            floor_passed=floor_passed,
            calibration_status=calibration_status,
            authority_boundary=calibration_authority_boundary,
        )
        upgrade = build_predictive_axis_upgrade_record(
            upgrade_id=f"layer3.g3.s11.upgrade.{_stable_id(request.request_id, axis)}",
            upgrade_ref=upgrade_ref,
            case_id=request.case_id,
            axis=axis,
            cell_ref=cell_ref,
            effective_maturity=effective_maturity,
            relaxation_decision=relaxation_decision,
            s6_floor_record_ref=prereq.s6_floor_status_refs[0],
            s6_floor_disposition="limit",
            s10_forecast_support_ref=prereq.s10_forecast_support_ref,
            predictive_model_ref=(
                f"predictive-model://layer3/g3/{request.case_id}/{axis}"
                if effective_maturity == "predictive"
                else None
            ),
            axis_model_evidence_refs=(
                [f"axis-model-evidence://layer3/g3/{request.case_id}/{axis}"]
                if effective_maturity == "predictive"
                else []
            ),
            calibration_record_ref=calibration.calibration_ref,
            proof_carrying_analytics_ref=proof_ref or None,
            forecast_quality_disposition=forecast_quality_disposition,
            regime_strategy_constraint_ref=(
                f"regime-strategy-constraint://layer3/g3/{request.case_id}/{axis}"
                if forecast_quality_disposition == "downgraded_by_s11_calibration"
                else None
            ),
            residual_limitation_refs=[
                f"limitation://layer3/g3/{request.case_id}/{axis}/weakest-boundary"
            ],
            constraint_store_update_refs=list(prereq.s6_constraint_store_update_refs),
            authority_boundary=calibration_authority_boundary,
        )
        envelope = verify_s11_predictive_knowledge_authority_envelope(
            proof_carrying_analytics_record=proof_record,
            axis_upgrade_record=upgrade,
        )
        integrity = summarize_s11_predictive_knowledge_integrity(
            case_count=1,
            axis_upgrade_records=(upgrade,),
            calibration_records=(calibration,),
            proof_records=(proof_record,),
            method_infrastructure_refs=calibration.method_infrastructure_refs,
            cells_closed=(cell_ref,),
            report_id=f"layer3.g3.s11.integrity.{_stable_id(request.request_id, axis)}",
        )
    except Exception:
        return (
            _blocked_g3_s11_calibration(
                request,
                axis=axis,
                cell_ref=cell_ref,
                s6_floor_record_ref=_first_present_str(prereq.s6_floor_status_refs),
                s10_forecast_support_ref=prereq.s10_forecast_support_ref,
                issue_codes=("layer3_g3_s11_calibration_invalid",),
                status="fail",
            ),
        )

    calibration_payload = calibration.model_dump(mode="json")
    upgrade_payload = upgrade.model_dump(mode="json")
    envelope_payload = envelope.model_dump(mode="json")
    integrity_payload = integrity.model_dump(mode="json")
    issue_codes = [
        *envelope_payload.get("issue_codes", ()),
        *_s11_authority_issue_codes(
            calibration_payload,
            upgrade_payload,
            envelope_payload,
            integrity_payload,
        ),
    ]
    status: Literal["pass", "blocked", "fail"] = "pass" if not issue_codes else "fail"
    return (
        Layer3G3S11CalibrationBinding(
            binding_id=f"g3-s11-calibration-binding:{_stable_id(request.request_id, axis)}",
            status=status,
            request_ref=request.request_id,
            case_id=request.case_id,
            claim_id=request.claim_id,
            axis=axis,
            cell_ref=cell_ref,
            calibration_ref=calibration.calibration_ref,
            upgrade_ref=upgrade.upgrade_ref,
            authority_envelope_ref=envelope.envelope_ref,
            integrity_report_ref=integrity.report_id,
            proof_carrying_analytics_ref=proof_ref,
            s6_floor_record_ref=calibration.s6_floor_record_ref,
            s10_forecast_support_ref=calibration.s10_forecast_support_ref,
            effective_maturity=upgrade.effective_maturity,
            relaxation_decision=upgrade.relaxation_decision,
            forecast_quality_disposition=upgrade.forecast_quality_disposition,
            calibration_record=calibration_payload,
            axis_upgrade_record=upgrade_payload,
            authority_envelope=envelope_payload,
            integrity_summary=integrity_payload,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
            may_not_use_for=_merge_g3_denials(envelope_payload.get("may_not_use_for", ())),
        ),
    )


def build_g3_s11_predictive_posture_bindings(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    s11_prerequisite_bindings: Sequence[
        Layer3G3S11PrerequisiteBinding | Mapping[str, Any]
    ] = (),
    s11_calibration_bindings: Sequence[
        Layer3G3S11CalibrationBinding | Mapping[str, Any]
    ] = (),
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
) -> tuple[Layer3G3S11PredictivePostureBinding, ...]:
    """Build an S11 predictive posture without upgrading G3 proof authority."""

    if request is None:
        return ()
    prereq = _first_pass_s11_prerequisite(s11_prerequisite_bindings)
    calibration = _first_pass_s11_calibration(s11_calibration_bindings)
    proof = _first_pass_g3_proof_binding(proof_carrying_analytics_records)
    proof_ref = str(proof.get("proof_ref") or "")
    if prereq is None or calibration is None or not proof_ref:
        issue_codes = ["layer3_g3_s11_posture_without_s6_s10"]
        if not proof_ref:
            issue_codes.extend(
                (
                    "layer3_g3_s11_predictive_upgrade_missing_proof",
                    "layer3_g3_proof_carrying_record_missing",
                )
            )
        if calibration is not None:
            issue_codes.extend(calibration.issue_codes)
        return (
            Layer3G3S11PredictivePostureBinding(
                binding_id=(
                    "g3-s11-predictive-posture-binding:"
                    f"{_stable_id(request.request_id, 'blocked')}"
                ),
                status="blocked",
                request_ref=request.request_id,
                case_id=request.case_id,
                claim_id=request.claim_id,
                proof_carrying_analytics_ref=proof_ref or None,
                issue_codes=tuple(dict.fromkeys(issue_codes)),
            ),
        )

    try:
        from polisyos.runtime.quality.layer2_predictive_knowledge import (
            build_s11_predictive_knowledge_posture,
            summarize_s11_predictive_knowledge_integrity,
        )

        proof_record = _mapping(proof.get("s11_record"))
        posture = build_s11_predictive_knowledge_posture(
            case_id=request.case_id,
            calibration_records=(calibration.calibration_record,),
            proof_records=(proof_record,),
            axis_upgrade_rows=(calibration.axis_upgrade_record,),
            s6_floor_status_refs=prereq.s6_floor_status_refs,
            s6_axis_rows=prereq.s6_axis_rows,
            s6_bridge_consumer_rows=prereq.s6_bridge_consumer_rows,
            s6_constraint_store_update_refs=prereq.s6_constraint_store_update_refs,
            s6_c3_authority_dimension_refs=prereq.s6_c3_authority_dimension_refs,
            post_intervention_dgp_update_ref=prereq.post_intervention_dgp_update_ref,
            system_dynamics_handoff_required=(
                prereq.system_dynamics_handoff_required
            ),
            s10_forecast_support_ref=prereq.s10_forecast_support_ref,
            s10_forecast_tier=(
                prereq.s10_forecast_tier or "observable_calibrated"
            ),
            predictive_knowledge_ref=(
                f"pdc://layer3/g3/{request.case_id}/s11/predictive-knowledge"
            ),
        )
        integrity = summarize_s11_predictive_knowledge_integrity(
            case_count=1,
            axis_upgrade_records=(calibration.axis_upgrade_record,),
            calibration_records=(calibration.calibration_record,),
            proof_records=(proof_record,),
            method_infrastructure_refs=tuple(
                _sequence(
                    calibration.calibration_record.get("method_infrastructure_refs")
                )
            ),
            cells_closed=(calibration.cell_ref,),
            report_id=f"layer3.g3.s11.posture.integrity.{_stable_id(request.request_id)}",
        ).model_dump(mode="json")
    except Exception:
        return (
            Layer3G3S11PredictivePostureBinding(
                binding_id=(
                    "g3-s11-predictive-posture-binding:"
                    f"{_stable_id(request.request_id, 'invalid')}"
                ),
                status="blocked",
                request_ref=request.request_id,
                case_id=request.case_id,
                claim_id=request.claim_id,
                proof_carrying_analytics_ref=proof_ref,
                s10_forecast_support_ref=prereq.s10_forecast_support_ref,
                s10_forecast_tier=prereq.s10_forecast_tier,
                s6_floor_status_refs=prereq.s6_floor_status_refs,
                issue_codes=("layer3_g3_s11_posture_without_s6_s10",),
            ),
        )

    issue_codes = _s11_authority_issue_codes(posture, integrity)
    return (
        Layer3G3S11PredictivePostureBinding(
            binding_id=f"g3-s11-predictive-posture-binding:{_stable_id(request.request_id)}",
            status="pass" if not issue_codes else "fail",
            request_ref=request.request_id,
            case_id=request.case_id,
            claim_id=request.claim_id,
            predictive_knowledge_ref=str(posture.get("predictive_knowledge_ref") or ""),
            proof_carrying_analytics_ref=proof_ref,
            ir_analytics_bridge_ref=str(posture.get("ir_analytics_bridge_ref") or ""),
            s10_forecast_support_ref=prereq.s10_forecast_support_ref,
            s10_forecast_tier=prereq.s10_forecast_tier,
            s6_floor_status_refs=prereq.s6_floor_status_refs,
            s11_calibration_record_refs=tuple(
                str(ref) for ref in _sequence(posture.get("s11_calibration_record_refs"))
            ),
            axis_upgrade_refs=tuple(
                str(ref) for ref in _sequence(posture.get("axis_upgrade_refs"))
            ),
            posture_payload=dict(posture),
            integrity_summary=integrity,
            issue_codes=issue_codes,
            may_not_use_for=_merge_g3_denials(posture.get("may_not_use_for", ())),
        ),
    )


def _load_g2_forecast_support_binding(repo_root: Path | None) -> dict[str, Any]:
    if repo_root is None:
        return {}
    path = _resolve_repo_path(
        Path(repo_root).resolve(),
        POLICY_DESIGN_CASE_DIR / "layer3_g2_forecast_support_bindings.json",
    )
    if not path.exists():
        return {}
    try:
        payload = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    for binding in _sequence(payload.get("forecast_support_bindings")):
        if isinstance(binding, Mapping):
            return dict(binding)
    return {}


def _dict_rows(rows: Sequence[Mapping[str, Any] | BaseModel]) -> tuple[dict[str, Any], ...]:
    return tuple(
        _dump_model(row)
        for row in rows
        if isinstance(row, (BaseModel, Mapping))
    )


def _first_pass_s11_prerequisite(
    bindings: Sequence[Layer3G3S11PrerequisiteBinding | Mapping[str, Any]],
) -> Layer3G3S11PrerequisiteBinding | None:
    for binding in bindings:
        record = (
            binding
            if isinstance(binding, Layer3G3S11PrerequisiteBinding)
            else Layer3G3S11PrerequisiteBinding.model_validate(binding)
        )
        if (
            record.status == "pass"
            and record.s6_floor_status_refs
            and record.s10_forecast_support_ref
        ):
            return record
    return None


def _first_pass_s11_calibration(
    bindings: Sequence[Layer3G3S11CalibrationBinding | Mapping[str, Any]],
) -> Layer3G3S11CalibrationBinding | None:
    for binding in bindings:
        record = (
            binding
            if isinstance(binding, Layer3G3S11CalibrationBinding)
            else Layer3G3S11CalibrationBinding.model_validate(binding)
        )
        if (
            record.status == "pass"
            and record.calibration_record
            and record.axis_upgrade_record
        ):
            return record
    return None


def _first_pass_g3_proof_binding(
    bindings: Sequence[Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]],
) -> dict[str, Any]:
    for binding in bindings:
        payload = _dump_model(binding) if isinstance(binding, BaseModel) else (
            dict(binding) if isinstance(binding, Mapping) else {}
        )
        if (
            payload.get("status") == "pass"
            and payload.get("proof_ref")
            and _mapping(payload.get("s11_record"))
        ):
            return payload
    return {}


def _blocked_g3_s11_calibration(
    request: Layer3G3AnalyticsRequest,
    *,
    axis: str,
    cell_ref: str,
    issue_codes: Sequence[str],
    status: Literal["blocked", "fail"] = "blocked",
    s6_floor_record_ref: str | None = None,
    s10_forecast_support_ref: str | None = None,
) -> Layer3G3S11CalibrationBinding:
    return Layer3G3S11CalibrationBinding(
        binding_id=f"g3-s11-calibration-binding:{_stable_id(request.request_id, axis, status)}",
        status=status,
        request_ref=request.request_id,
        case_id=request.case_id,
        claim_id=request.claim_id,
        axis=axis,
        cell_ref=cell_ref,
        s6_floor_record_ref=s6_floor_record_ref,
        s10_forecast_support_ref=s10_forecast_support_ref,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _s11_authority_issue_codes(*records: Mapping[str, Any]) -> tuple[str, ...]:
    issues: list[str] = []
    for record in records:
        boundary = _mapping(record.get("authority_boundary")) or (
            record if "authoritative_for" in record else {}
        )
        authoritative_for = {
            str(item)
            for item in _sequence(boundary.get("authoritative_for"))
            if str(item)
        }
        if authoritative_for & {
            "production_authority",
            "publication_authority",
            "rollout_authority",
        }:
            issues.append("layer3_g3_production_authority_leak")
        if authoritative_for & {
            "policy_recommendation",
            "production_recommendation",
            "recommendation_authority",
        }:
            issues.append("layer3_g3_recommendation_authority_leak")
        if authoritative_for & {
            "claim_authority",
            "production_claim_authority",
        }:
            issues.append("layer3_g3_claim_authority_leak")
        if authoritative_for & {
            "closeout_authority",
            "runtime_closeout_authority",
        }:
            issues.append("layer3_g3_closeout_authority_leak")
    return tuple(dict.fromkeys(issues))


def _bridge_payload_from_g3(
    value: Layer3G3IRAnalyticsBridgeBinding | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if value is None:
        return {}
    payload = _dump_model(value) if isinstance(value, BaseModel) else (
        dict(value) if isinstance(value, Mapping) else {}
    )
    bridge = _mapping(payload.get("bridge_payload"))
    return dict(bridge) if bridge else payload


def _bridge_ref(bridge_payload: Mapping[str, Any]) -> str | None:
    return _first_present_str(
        (
            bridge_payload.get("ir_analytics_bridge_ref"),
            bridge_payload.get("bridge_ref"),
        )
    )


def _refs_from_records(
    records: Sequence[BaseModel | Mapping[str, Any]],
    field_name: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    for record in records:
        payload = _dump_model(record) if isinstance(record, BaseModel) else (
            dict(record) if isinstance(record, Mapping) else {}
        )
        value = payload.get(field_name)
        if isinstance(value, str):
            refs.append(value)
        else:
            refs.extend(str(ref) for ref in _sequence(value) if str(ref))
    return tuple(dict.fromkeys(refs))


def _g3_w12d_consumer_assertions(
    *,
    s2: Mapping[str, Any],
    s11: Mapping[str, Any],
    proof_ref: str | None,
    posture_ref: str | None,
) -> dict[str, bool]:
    ledger = _mapping(s2.get("search_ledger"))
    design_record = _mapping(s2.get("design_record"))
    constraint_store = _mapping(s2.get("constraint_store"))
    s11_constraints = [
        _mapping(row)
        for row in _sequence(constraint_store.get("constraint_records"))
        if str(_mapping(row).get("constraint_id", "")).startswith("layer2.s11.")
    ]
    axis_positions = [
        _mapping(row)
        for row in _sequence(design_record.get("axis_positions"))
        if _mapping(row).get("axis") == "predictive_knowledge_relaxation"
    ]
    firewall_statuses = [
        _mapping(row)
        for row in _sequence(design_record.get("firewall_status"))
        if _mapping(row).get("cell_ref") == "KNOWLEDGE.predictive_knowledge_relaxation"
    ]
    projection_audiences = set(_sequence(design_record.get("projection_audiences")))
    return {
        "search_ledger_predictive_knowledge_ref_consumed": bool(
            posture_ref and posture_ref in _sequence(ledger.get("predictive_knowledge_refs"))
        ),
        "search_ledger_g3_proof_ref_consumed": bool(
            proof_ref and proof_ref in _sequence(ledger.get("proof_carrying_analytics_refs"))
        ),
        "s11_constraint_store_entries_consumed": bool(
            proof_ref
            and s11_constraints
            and all(proof_ref in _sequence(row.get("evidence_refs")) for row in s11_constraints)
        ),
        "refinement_status_consumed": bool(
            s2.get("status")
            and _sequence(ledger.get("iterations"))
            and _sequence(ledger.get("refinement_decision_refs"))
        ),
        "axis_position_declared": bool(
            proof_ref
            and axis_positions
            and proof_ref in _sequence(axis_positions[0].get("evidence_refs"))
        ),
        "firewall_status_consumed": bool(firewall_statuses),
        "projection_fields_present": projection_audiences
        >= {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"},
    }


def build_g3_claim_registry_consumer_gate(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    ir_analytics_bridge: Layer3G3IRAnalyticsBridgeBinding | Mapping[str, Any] | None = None,
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
    claims: Sequence[Mapping[str, Any]] = (),
    run_id: str | None = None,
) -> Layer3G3ClaimRegistryConsumerGateRecord:
    """Build a gate proving the runtime claim registry consumed G3 bridge rows."""

    bridge_payload = _bridge_payload_from_g3(ir_analytics_bridge)
    proof_refs = _refs_from_records(proof_carrying_analytics_records, "proof_ref")
    issue_codes: list[str] = []
    if request is None or not bridge_payload or not claims:
        issue_codes.append("layer3_g3_claim_registry_consumer_gate_missing")
    if not proof_refs:
        issue_codes.append("layer3_g3_proof_carrying_record_missing")
    if issue_codes:
        return Layer3G3ClaimRegistryConsumerGateRecord(
            status="blocked",
            request_ref=request.request_id if request else None,
            case_id=request.case_id if request else None,
            claim_id=request.claim_id if request else None,
            ir_analytics_bridge_ref=_bridge_ref(bridge_payload),
            proof_carrying_analytics_refs=proof_refs,
            issue_codes=tuple(dict.fromkeys(issue_codes)),
        )

    from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry

    registry = build_runtime_claim_registry(
        claims=claims,
        ir_analytics_bridge=bridge_payload,
        run_id=run_id or request.case_id,
        registry_ref=f"claim-registry://layer3/g3/{request.case_id}",
    )
    registry_rows = [
        row
        for row in _sequence(registry.get("claims"))
        if _mapping(row).get("claim_id") == request.claim_id
    ]
    consumed_ir_refs = tuple(
        dict.fromkeys(
            str(ref)
            for row in registry_rows
            for ref in _sequence(_mapping(row).get("ir_analytics_refs"))
            if str(ref)
        )
    )
    issue_codes.extend(
        str(issue.get("code"))
        for issue in _sequence(registry.get("issues"))
        if isinstance(issue, Mapping)
    )
    if registry.get("status") != "pass":
        issue_codes.append("layer3_g3_claim_registry_consumer_gate_missing")
    if not consumed_ir_refs:
        issue_codes.append("layer3_g3_ir_analytics_bridge_missing")
    issue_codes = list(dict.fromkeys(issue_codes))
    return Layer3G3ClaimRegistryConsumerGateRecord(
        status="pass" if not issue_codes else "fail",
        request_ref=request.request_id,
        case_id=request.case_id,
        claim_id=request.claim_id,
        runtime_claim_registry_ref=str(registry.get("runtime_claim_registry_ref") or ""),
        claim_registry_status=str(registry.get("status") or ""),
        ir_analytics_bridge_ref=_bridge_ref(bridge_payload),
        proof_carrying_analytics_refs=proof_refs,
        consumed_ir_analytics_refs=consumed_ir_refs,
        blocked_claim_count=int(
            _mapping(registry.get("summary")).get("ir_analytics_blocked_claim_count", 0)
            or 0
        ),
        claim_registry_payload=dict(registry),
        issue_codes=tuple(issue_codes),
        may_not_use_for=_merge_g3_denials(
            _sequence(_mapping(bridge_payload.get("runtime_authority_envelope")).get("may_not_use_for"))
        ),
    )


def build_g3_baseline_comparison_consumer_gate(
    *,
    request: Layer3G3AnalyticsRequest | None = None,
    claim_ledger: object | None = None,
    ir_analytics_bridge: Layer3G3IRAnalyticsBridgeBinding | Mapping[str, Any] | None = None,
    selected_option_ref: str | None = None,
    selected_option_label: str | None = None,
    selected_option_evidence_refs: Sequence[str] = (),
    option_metric_values: Mapping[str, Mapping[str, float]] | None = None,
    objective_directions: Mapping[str, str] | None = None,
) -> Layer3G3BaselineComparisonConsumerGateRecord:
    """Build a gate proving baseline comparison consumed G3 as evidence only."""

    bridge_payload = _bridge_payload_from_g3(ir_analytics_bridge)
    issue_codes: list[str] = []
    if (
        request is None
        or claim_ledger is None
        or not bridge_payload
        or not selected_option_ref
        or not selected_option_label
    ):
        issue_codes.append("layer3_g3_baseline_comparison_consumer_gate_missing")
        return Layer3G3BaselineComparisonConsumerGateRecord(
            status="blocked",
            request_ref=request.request_id if request else None,
            case_id=request.case_id if request else None,
            claim_id=request.claim_id if request else None,
            ir_analytics_bridge_refs=(_bridge_ref(bridge_payload),)
            if _bridge_ref(bridge_payload)
            else (),
            issue_codes=tuple(issue_codes),
        )

    try:
        baseline_module = importlib.import_module(
            "polisyos.scientist.policy_design.baseline_compiler"
        )
        baseline_comparison_compiler_cls = baseline_module.BaselineComparisonCompiler
        baseline_comparison_input_cls = baseline_module.BaselineComparisonInput

        compiled = baseline_comparison_compiler_cls().compile(
            baseline_comparison_input_cls(
                claim_ledger=claim_ledger,
                selected_option_ref=selected_option_ref,
                selected_option_label=selected_option_label,
                selected_option_evidence_refs=set(selected_option_evidence_refs),
                option_metric_values=dict(option_metric_values or {}),
                objective_directions=dict(objective_directions or {}),
                ir_analytics_bridge=bridge_payload,
                metadata={"layer3_g3_request_ref": request.request_id},
            )
        )
    except Exception:
        return Layer3G3BaselineComparisonConsumerGateRecord(
            status="fail",
            request_ref=request.request_id,
            case_id=request.case_id,
            claim_id=request.claim_id,
            ir_analytics_bridge_refs=(_bridge_ref(bridge_payload),)
            if _bridge_ref(bridge_payload)
            else (),
            issue_codes=("layer3_g3_baseline_comparison_consumer_gate_missing",),
        )

    compiled_payload = compiled.model_dump(mode="json")
    comparisons = [
        _mapping(row)
        for row in _sequence(compiled_payload.get("comparison_records"))
        if _mapping(row).get("claim_id") == request.claim_id
    ]
    evidence_refs = tuple(
        dict.fromkeys(
            str(_mapping(evidence).get("evidence_ref"))
            for comparison in comparisons
            for evidence in _sequence(comparison.get("comparison_evidence"))
            if _mapping(evidence).get("evidence_ref")
        )
    )
    method_refs = tuple(
        dict.fromkeys(
            str(ref)
            for comparison in comparisons
            for ref in _sequence(comparison.get("comparison_method_refs"))
            if str(ref)
        )
    )
    authority_issues = _s11_authority_issue_codes(
        *[_mapping(comparison.get("authority_boundary")) for comparison in comparisons]
    )
    bridge_refs = tuple(
        ref for ref in (_bridge_ref(bridge_payload),) if ref
    )
    if not comparisons or not evidence_refs:
        issue_codes.append("layer3_g3_baseline_comparison_consumer_gate_missing")
    issue_codes.extend(authority_issues)
    first_boundary = dict(_mapping(comparisons[0].get("authority_boundary"))) if comparisons else {}
    return Layer3G3BaselineComparisonConsumerGateRecord(
        status="pass" if not issue_codes else "fail",
        request_ref=request.request_id,
        case_id=request.case_id,
        claim_id=request.claim_id,
        comparison_record_count=len(comparisons),
        comparison_evidence_refs=evidence_refs,
        comparison_method_refs=method_refs,
        ir_analytics_bridge_refs=bridge_refs,
        authority_boundary=first_boundary,
        compiled_ledger_payload=compiled_payload,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        may_not_use_for=_merge_g3_denials(_sequence(first_boundary.get("may_not_use_for"))),
    )


def build_g3_w12d_consumer_gate(
    *,
    case_id: str | None = None,
    s2_design_search: Mapping[str, Any] | None = None,
    s11_predictive_knowledge: Mapping[str, Any] | None = None,
    full_s2_consumer_case_refs: Sequence[str] = (),
    lightweight_case_refs: Sequence[str] = (),
    lightweight_posture_ref: str | None = None,
    useful_design_before: bool = False,
    useful_design_after: bool = False,
) -> Layer3G3W12DConsumerGateRecord:
    """Build the W12D gate over S11/S2 G3 proof consumption."""

    s2 = _mapping(s2_design_search)
    s11 = _mapping(s11_predictive_knowledge)
    ledger = _mapping(s2.get("search_ledger"))
    proof_ref = _first_present_str((s11.get("proof_carrying_analytics_ref"),))
    bridge_ref = _first_present_str((s11.get("ir_analytics_bridge_ref"),))
    posture_ref = _first_present_str((s11.get("predictive_knowledge_ref"), lightweight_posture_ref))
    full_refs = _dedupe(full_s2_consumer_case_refs)
    lightweight_refs = _dedupe(lightweight_case_refs)
    g3_resolved = bool(proof_ref and proof_ref.startswith("pdc://layer3/g3/"))
    lightweight_only = bool(lightweight_posture_ref or lightweight_refs) and not ledger
    route_kind: Literal[
        "full_s11_s2_consumer",
        "lightweight_s11_posture_ref",
        "not_routed",
    ] = (
        "full_s11_s2_consumer"
        if ledger
        else "lightweight_s11_posture_ref"
        if lightweight_only
        else "not_routed"
    )
    assertions = _g3_w12d_consumer_assertions(
        s2=s2,
        s11=s11,
        proof_ref=proof_ref,
        posture_ref=posture_ref,
    )
    issue_codes: list[str] = []
    if route_kind == "not_routed":
        issue_codes.append("layer3_g3_w12d_consumer_gate_missing")
    if route_kind == "full_s11_s2_consumer" and not g3_resolved:
        issue_codes.append("layer3_g3_w12d_consumer_gate_missing")
    if route_kind == "full_s11_s2_consumer" and not all(assertions.values()):
        issue_codes.append("layer3_g3_w12d_consumer_gate_missing")
    if (
        proof_ref
        and proof_ref.startswith("certificate://")
        and route_kind != "lightweight_s11_posture_ref"
    ):
        issue_codes.append("layer3_g3_fixture_certificate_laundered")
    status: Literal["pass", "fail", "blocked"] = "pass" if not issue_codes else "fail"
    return Layer3G3W12DConsumerGateRecord(
        status=status,
        case_id=case_id,
        route_kind=route_kind,
        posture_consumed=route_kind == "full_s11_s2_consumer",
        predictive_knowledge_ref=posture_ref,
        g3_proof_carrying_analytics_ref=proof_ref if g3_resolved else None,
        g3_ir_analytics_bridge_ref=bridge_ref if g3_resolved else None,
        fixture_s11_regression_context_ref=None if g3_resolved else proof_ref,
        full_s2_consumer_case_refs=full_refs,
        lightweight_case_refs=lightweight_refs,
        lightweight_posture_ref=lightweight_posture_ref,
        full_consumer_case_count=len(full_refs),
        lightweight_posture_ref_count=len(lightweight_refs),
        g3_closure_count=1 if g3_resolved and route_kind == "full_s11_s2_consumer" else 0,
        fixture_certificate_closure_count=0,
        negative_certificate_block_count=len(_sequence(s11.get("negative_certificate_refs"))),
        useful_design_delta_count=1 if useful_design_before != useful_design_after else 0,
        consumer_assertions=assertions,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g3_public_export_projection_ref_surface(
    *,
    certificate_resolution_report: (
        Layer3G3CertificateResolutionReport | Mapping[str, Any] | None
    ) = None,
    ir_analytics_search_ledgers: Sequence[
        Layer3G3IRCatalogSearchLedger | Mapping[str, Any]
    ] = (),
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
    ir_analytics_bridge: Layer3G3IRAnalyticsBridgeBinding | Mapping[str, Any] | None = None,
    method_requirement_bindings: Sequence[
        Layer3G3MethodRequirementBinding | Mapping[str, Any]
    ] = (),
    s11_predictive_posture_bindings: Sequence[
        Layer3G3S11PredictivePostureBinding | Mapping[str, Any]
    ] = (),
) -> Layer3G3PublicExportProjectionRefSurface:
    """Build projection-only G3 refs/status for public export."""

    certificate = _dump_model(certificate_resolution_report)
    proof_refs = _refs_from_records(proof_carrying_analytics_records, "proof_ref")
    bridge_ref = _bridge_ref(_bridge_payload_from_g3(ir_analytics_bridge))
    method_refs = tuple(
        dict.fromkeys(
            ref
            for binding in method_requirement_bindings
            for ref in _sequence(_dump_model(binding).get("method_requirement_refs"))
            if str(ref)
        )
    )
    posture_refs = _refs_from_records(
        s11_predictive_posture_bindings,
        "predictive_knowledge_ref",
    )
    search_ledger_refs = tuple(
        f"repo://architecture/policy_design_case/layer3_g3_ir_analytics_search_ledgers.json#{_dump_model(ledger).get('ledger_id')}"
        for ledger in ir_analytics_search_ledgers
        if _dump_model(ledger).get("ledger_id")
    )
    issue_codes: list[str] = []
    if certificate.get("resolved_certificate_count", 0) <= 0:
        issue_codes.append("layer3_g3_certificate_resolution_missing")
    if not proof_refs:
        issue_codes.append("layer3_g3_proof_carrying_record_missing")
    if not bridge_ref:
        issue_codes.append("layer3_g3_ir_analytics_bridge_missing")
    boundary = _g3_projection_authority_boundary()
    return Layer3G3PublicExportProjectionRefSurface(
        status="pass" if not issue_codes else "fail",
        certificate_resolution_report_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g3_certificate_resolution_report.json"
        ),
        search_ledger_refs=search_ledger_refs,
        redacted_search_frontier_refs=(
            "g3-search-frontier://layer3/g3/resolved-proof-candidates",
        )
        if search_ledger_refs
        else (),
        proof_carrying_analytics_refs=proof_refs,
        ir_analytics_bridge_refs=(bridge_ref,) if bridge_ref else (),
        method_requirement_refs=method_refs,
        s11_predictive_posture_refs=posture_refs,
        resolved_certificate_count=int(
            certificate.get("resolved_certificate_count", 0) or 0
        ),
        blocked_certificate_count=int(
            certificate.get("blocking_certificate_count", 0) or 0
        ),
        authority_boundary=boundary,
        may_not_use_for=_merge_g3_denials(_sequence(boundary.get("may_not_use_for"))),
        public_payload_redaction_status="pass",
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g3_proof_carrying_audit_surface(
    *,
    certificate_resolution_report: (
        Layer3G3CertificateResolutionReport | Mapping[str, Any] | None
    ) = None,
    proof_carrying_analytics_records: Sequence[
        Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any]
    ] = (),
    ir_analytics_bridge: Layer3G3IRAnalyticsBridgeBinding | Mapping[str, Any] | None = None,
    method_requirement_bindings: Sequence[
        Layer3G3MethodRequirementBinding | Mapping[str, Any]
    ] = (),
    s11_predictive_posture_bindings: Sequence[
        Layer3G3S11PredictivePostureBinding | Mapping[str, Any]
    ] = (),
) -> Layer3G3ProofCarryingAuditSurface:
    """Build audience-tiered proof-carrying audit semantics for G3."""

    certificate = _dump_model(certificate_resolution_report)
    proof_refs = _refs_from_records(proof_carrying_analytics_records, "proof_ref")
    bridge_ref = _bridge_ref(_bridge_payload_from_g3(ir_analytics_bridge))
    method_refs = tuple(
        dict.fromkeys(
            ref
            for binding in method_requirement_bindings
            for ref in _sequence(_dump_model(binding).get("method_requirement_refs"))
            if str(ref)
        )
    )
    posture_refs = _refs_from_records(
        s11_predictive_posture_bindings,
        "predictive_knowledge_ref",
    )
    blocker_refs = tuple(
        dict.fromkeys(
            ref
            for proof in proof_carrying_analytics_records
            for ref in _sequence(_dump_model(proof).get("s11_record", {}).get("blocker_refs"))
            if str(ref)
        )
    )
    limitation_refs = tuple(
        dict.fromkeys(
            ref
            for proof in proof_carrying_analytics_records
            for ref in _sequence(
                _dump_model(proof).get("s11_record", {}).get("limitation_refs")
            )
            if str(ref)
        )
    )
    issue_codes: list[str] = []
    if certificate.get("status") != "pass":
        issue_codes.append("layer3_g3_certificate_resolution_missing")
    if not proof_refs:
        issue_codes.append("layer3_g3_proof_carrying_record_missing")
    boundary = _g3_projection_authority_boundary()
    return Layer3G3ProofCarryingAuditSurface(
        status="pass" if not issue_codes else "fail",
        expert_fields=(
            "proof_carrying_analytics_refs",
            "certificate_resolution_report_ref",
            "ir_analytics_bridge_refs",
            "method_requirement_refs",
            "s11_predictive_posture_refs",
            "blocker_refs",
            "limitation_refs",
            "authority_boundary",
        ),
        machine_fields=(
            "search_frontier_refs",
            "certificate_resolution_report_ref",
            "proof_carrying_analytics_refs",
            "ir_analytics_bridge_refs",
            "method_requirement_refs",
            "s11_predictive_posture_refs",
            "may_not_use_for",
            "issue_codes",
        ),
        certificate_resolution_report_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g3_certificate_resolution_report.json"
        ),
        proof_carrying_analytics_refs=proof_refs,
        ir_analytics_bridge_refs=(bridge_ref,) if bridge_ref else (),
        search_frontier_refs=("g3-search-frontier://layer3/g3/resolved-proof-candidates",),
        method_requirement_refs=method_refs,
        s11_predictive_posture_refs=posture_refs,
        blocker_refs=blocker_refs,
        limitation_refs=limitation_refs,
        authority_boundary=boundary,
        may_not_use_for=_merge_g3_denials(_sequence(boundary.get("may_not_use_for"))),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g3_adapter_contract_registry_status(
    *,
    repo_root: Path | None = None,
    path: Path | None = None,
) -> Layer3G3AdapterContractRegistryStatus:
    """Load and validate the G3 adapter contract registry with existing loader."""

    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd()
    registry_path = path or _resolve_repo_path(root, G3_ADAPTER_CONTRACT_REGISTRY_PATH)
    if not registry_path.exists():
        return Layer3G3AdapterContractRegistryStatus(
            status="fail",
            registry_ref=_path_label(G3_ADAPTER_CONTRACT_REGISTRY_PATH),
            issue_codes=("layer3_g3_adapter_contract_registry_missing",),
        )
    try:
        from polisyos.runtime.quality.adapter_contracts import (
            AdapterSurfacePayload,
            load_adapter_contract_registry,
            validate_adapter_preservation,
        )

        registry = load_adapter_contract_registry(registry_path)
        if not registry.adapter_paths:
            raise ValueError("summary-only adapter registry")
        before = _g3_adapter_surface_payload(
            AdapterSurfacePayload,
            surface="layer3.g3.certificate_resolution",
        )
        after = _g3_adapter_surface_payload(
            AdapterSurfacePayload,
            surface="layer3.g3.proof_record",
        )
        preservation_issue_codes: list[str] = []
        if "layer3_g3_certificate_resolution_to_proof_record" in registry.adapter_paths:
            preservation = validate_adapter_preservation(
                adapter_path="layer3_g3_certificate_resolution_to_proof_record",
                before=before,
                after=after,
                registry=registry,
            )
            if preservation.status != "pass":
                preservation_issue_codes.append("layer3_g3_adapter_semantic_loss")
    except Exception as error:
        code = getattr(error, "code", "")
        issue = (
            "layer3_g3_adapter_registry_summary_only"
            if code
            in {
                "source_truth_table_missing",
                "source_truth_field_families_missing",
                "hds_adapter_paths_missing",
            }
            else "layer3_g3_adapter_contract_registry_missing"
        )
        return Layer3G3AdapterContractRegistryStatus(
            status="fail",
            registry_ref=_path_label(G3_ADAPTER_CONTRACT_REGISTRY_PATH),
            loader_error_code=str(code or type(error).__name__),
            issue_codes=(issue,),
        )
    path_ids = tuple(sorted(registry.adapter_paths))
    unknown_path_ids = tuple(sorted(set(path_ids) - set(G3_ADAPTER_PATH_IDS)))
    missing_path_ids = tuple(sorted(set(G3_ADAPTER_PATH_IDS) - set(path_ids)))
    issue_codes = tuple(
        dict.fromkeys(
            [
                *preservation_issue_codes,
                *(("layer3_g3_adapter_unknown_path",) if unknown_path_ids else ()),
                *(
                    ("layer3_g3_adapter_contract_registry_missing",)
                    if missing_path_ids
                    else ()
                ),
            ]
        )
    )
    records = _g3_adapter_admission_records(path_ids)
    return Layer3G3AdapterContractRegistryStatus(
        status="pass" if not issue_codes else "fail",
        registry_ref=_path_label(G3_ADAPTER_CONTRACT_REGISTRY_PATH),
        adapter_contract_path_count=len(path_ids),
        adapter_path_ids=path_ids,
        adapter_admission_records=records,
        checked_field_families=tuple(sorted(registry.lattice.field_families)),
        issue_codes=issue_codes,
    )


def build_g3_generated_artifact_registration_status(
    repo_root: Path,
    *,
    expected_artifact_paths: Sequence[str | Path] = G3_GENERATED_ARTIFACT_PATH_REFS,
) -> Layer3G3GeneratedArtifactRegistrationStatus:
    """Validate the G3 generated-artifact family and reference docs registration."""

    root = Path(repo_root).resolve()
    required_paths = tuple(
        path.as_posix() if isinstance(path, Path) else str(path)
        for path in expected_artifact_paths
        if str(path)
    )
    generated_text = _read_text_or_empty(root / "architecture/generated_artifacts.toml")
    registered_paths = tuple(path for path in required_paths if path in generated_text)
    missing_refs: list[str] = []
    if LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID not in generated_text:
        missing_refs.append(
            "architecture/generated_artifacts.toml:"
            f"{LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID}"
        )
    missing_refs.extend(
        f"architecture/generated_artifacts.toml:{path}"
        for path in required_paths
        if path not in generated_text
    )

    registered_doc_refs: list[str] = []
    for doc_path, marker in G3_GENERATED_ARTIFACT_DOC_MARKERS:
        if marker in _read_text_or_empty(root / doc_path):
            registered_doc_refs.append(doc_path)
        else:
            missing_refs.append(f"{doc_path}:{marker}")

    missing_registration_refs = tuple(dict.fromkeys(missing_refs))
    return Layer3G3GeneratedArtifactRegistrationStatus(
        status="pass" if not missing_registration_refs else "fail",
        required_artifact_paths=required_paths,
        registered_artifact_paths=registered_paths,
        registered_doc_refs=tuple(dict.fromkeys(registered_doc_refs)),
        missing_registration_refs=missing_registration_refs,
        issue_codes=()
        if not missing_registration_refs
        else ("layer3_g3_persisted_artifact_missing",),
    )


def build_g3_conformance_report(
    repo_root: Path,
    bundle: Layer3G3Bundle | Mapping[str, Any],
) -> Layer3G3ConformanceReport:
    """Build the final G3 conformance report across replay, performance, and adapters."""

    _ = repo_root
    payload = _dump_model(bundle)
    issues: list[str] = []
    missing_replay_refs: list[str] = []

    issues.extend(_g3_conformance_search_and_performance_issues(payload))
    issues.extend(_g3_conformance_artifact_store_issues(payload))
    replay_issues, replay_missing = _g3_conformance_replay_issues(payload)
    issues.extend(replay_issues)
    missing_replay_refs.extend(replay_missing)
    issues.extend(_g3_conformance_adapter_issues(payload))
    issues.extend(_g3_conformance_consumer_issues(payload))

    heavy_import_refs = _g3_module_load_heavy_import_refs()
    if heavy_import_refs:
        issues.append("layer3_g3_import_laziness_violation")

    issue_codes = tuple(dict.fromkeys(issues))
    replay_codes = {
        "layer3_g3_query_trace_missing",
        "layer3_g3_replay_record_missing",
        "layer3_g3_certificate_resolution_missing",
        "layer3_g3_proof_carrying_record_missing",
        "layer3_g3_method_requirement_missing",
    }
    performance_codes = {
        "layer3_g3_ir_catalog_search_not_indexed",
        "layer3_g3_search_ledger_missing",
        "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
        "layer3_g3_search_ceiling_repair_required",
        "layer3_g3_import_laziness_violation",
    }
    adapter_codes = {
        "layer3_g3_adapter_contract_registry_missing",
        "layer3_g3_adapter_registry_summary_only",
        "layer3_g3_adapter_unknown_path",
        "layer3_g3_adapter_semantic_loss",
        "layer3_g3_adapter_touchpoint_unregistered",
    }
    artifact_codes = {
        "layer3_g3_full_cas_listing_in_request_path",
        "layer3_g3_tenant_scoped_manifest_denied",
        "layer3_g3_stale_artifact_index_claimed_as_proof_ceiling",
        "layer3_g3_store_configuration_missing",
        "layer3_g3_persisted_artifact_missing",
    }
    authority_codes = {
        "layer3_g3_production_authority_leak",
        "layer3_g3_recommendation_authority_leak",
        "layer3_g3_claim_authority_leak",
        "layer3_g3_closeout_authority_leak",
    }
    artifact_status: Literal["pass", "fail", "blocked"]
    if "layer3_g3_tenant_scoped_manifest_denied" in issue_codes:
        artifact_status = "blocked"
    elif set(issue_codes) & artifact_codes:
        artifact_status = "fail"
    else:
        artifact_status = "pass"
    return Layer3G3ConformanceReport(
        status="pass" if not issue_codes else "fail",
        replay_check_status="fail" if set(issue_codes) & replay_codes else "pass",
        performance_check_status=(
            "fail" if set(issue_codes) & performance_codes else "pass"
        ),
        module_load_check_status="fail" if heavy_import_refs else "pass",
        adapter_admission_check_status=(
            "fail" if set(issue_codes) & adapter_codes else "pass"
        ),
        artifact_store_check_status=artifact_status,
        authority_boundary_check_status=(
            "fail" if set(issue_codes) & authority_codes else "pass"
        ),
        replayed_certificate_count=_resolved_certificate_count(payload),
        checked_adapter_path_count=len(
            _sequence(_mapping(payload.get("adapter_contract_registry")).get("adapter_path_ids"))
        ),
        heavy_module_import_refs=heavy_import_refs,
        missing_replay_refs=tuple(dict.fromkeys(missing_replay_refs)),
        issue_codes=issue_codes,
    )


def validate_g3_adapter_conformance(
    repo_root: Path,
    bundle: Layer3G3Bundle | Mapping[str, Any],
) -> Layer3G3ConformanceReport:
    """Run final G3 conformance checks."""

    return build_g3_conformance_report(repo_root, bundle)


def _g3_conformance_search_and_performance_issues(
    payload: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    coverage = _mapping(payload.get("ir_catalog_coverage"))
    if coverage.get("status") != "pass":
        issues.append("layer3_g3_ir_catalog_coverage_missing")
    if coverage.get("full_catalog_route") in FORBIDDEN_FULL_CATALOG_ROUTES:
        issues.append("layer3_g3_ir_catalog_hardcode_closure")
    ledgers = tuple(
        _mapping(ledger) for ledger in _sequence(payload.get("ir_analytics_search_ledgers"))
    )
    traces = tuple(
        _mapping(trace) for trace in _sequence(payload.get("ir_analytics_query_traces"))
    )
    trace_ids = {str(trace.get("trace_id")) for trace in traces if trace.get("trace_id")}
    if not ledgers:
        issues.append("layer3_g3_search_ledger_missing")
    if not traces:
        issues.append("layer3_g3_query_trace_missing")
    for ledger in ledgers:
        trace_refs = tuple(str(ref) for ref in _sequence(ledger.get("query_trace_refs")))
        if not trace_refs:
            issues.append("layer3_g3_query_trace_missing")
        if any(ref not in trace_ids for ref in trace_refs):
            issues.append("layer3_g3_replay_record_missing")
        cutoff = int(ledger.get("cutoff_limit") or 0)
        if cutoff <= 0 or cutoff > 256:
            issues.append("layer3_g3_search_ledger_missing")
    for trace in traces:
        if trace.get("used_duckdb_materialized_table") is not True:
            issues.append("layer3_g3_ir_catalog_search_not_indexed")
        if int(trace.get("bounded_result_limit") or 0) <= 0:
            issues.append("layer3_g3_search_ledger_missing")
        if int(trace.get("bounded_result_limit") or 0) > 256:
            issues.append("layer3_g3_search_ledger_missing")
        if int(trace.get("per_request_module_walk_count") or 0) > 0:
            issues.append("layer3_g3_ir_catalog_search_not_indexed")
        if int(trace.get("per_request_json_scan_count") or 0) > 0:
            issues.append("layer3_g3_ir_catalog_search_not_indexed")
    quality = _mapping(payload.get("search_engineering_quality"))
    if quality.get("status") != "pass":
        quality_issue_codes = _sequence(quality.get("issue_codes")) or (
            "layer3_g3_ir_catalog_search_not_indexed",
        )
        issues.extend(str(code) for code in quality_issue_codes)
    if int(quality.get("per_request_module_walk_count") or 0) > 0:
        issues.append("layer3_g3_ir_catalog_search_not_indexed")
    if int(quality.get("per_request_json_scan_count") or 0) > 0:
        issues.append("layer3_g3_ir_catalog_search_not_indexed")
    if int(quality.get("unbounded_query_count") or 0) > 0:
        issues.append("layer3_g3_search_ledger_missing")
    recall = _mapping(payload.get("search_recall_freshness"))
    if (
        recall.get("status") != "pass"
        or recall.get("freshness_status") != "pass"
        or int(recall.get("recalled_seed_count") or 0)
        != int(recall.get("known_seed_count") or 0)
    ):
        recall_issue_codes = _sequence(recall.get("issue_codes")) or (
            "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
        )
        issues.extend(str(code) for code in recall_issue_codes)
    if recall.get("freshness_status") != "pass":
        issues.append("layer3_g3_search_ceiling_repair_required")
    return issues


def _g3_conformance_artifact_store_issues(payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    artifact_index = _mapping(payload.get("ir_artifact_store_index"))
    certificate = _mapping(payload.get("certificate_resolution_report"))
    issues.extend(str(code) for code in _sequence(artifact_index.get("issue_codes")))
    issues.extend(str(code) for code in _sequence(certificate.get("issue_codes")))
    if artifact_index.get("status") == "not_configured":
        issues.append("layer3_g3_store_configuration_missing")
    if artifact_index.get("store_backend") == "not_configured":
        issues.append("layer3_g3_store_configuration_missing")
    if artifact_index.get("full_listing_used") or certificate.get("full_listing_used"):
        issues.append("layer3_g3_full_cas_listing_in_request_path")
    if artifact_index.get("stale") or certificate.get("stale_artifact_index"):
        issues.append("layer3_g3_stale_artifact_index_claimed_as_proof_ceiling")
    if artifact_index.get("tenant_scope_status") == "denied":
        issues.append("layer3_g3_tenant_scoped_manifest_denied")
    if certificate.get("status") != "pass":
        issues.append("layer3_g3_certificate_resolution_missing")
    if int(certificate.get("resolved_certificate_count") or 0) <= 0:
        issues.append("layer3_g3_certificate_resolution_missing")
    return issues


def _g3_conformance_replay_issues(
    payload: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    missing_refs: list[str] = []
    certificate = _mapping(payload.get("certificate_resolution_report"))
    resolution_records = tuple(
        _mapping(record) for record in _sequence(certificate.get("records"))
    )
    resolved_records = tuple(
        record for record in resolution_records if record.get("status") == "resolved"
    )
    resolution_record_ids = {
        str(record.get("record_id"))
        for record in resolved_records
        if record.get("record_id")
    }
    if not resolved_records:
        issues.append("layer3_g3_certificate_resolution_missing")
    for record in resolved_records:
        record_id = str(record.get("record_id") or record.get("candidate_id") or "unknown")
        if not record.get("artifact_ref") and not record.get("artifact_id"):
            issues.append("layer3_g3_replay_record_missing")
            missing_refs.append(f"{record_id}:artifact_ref")
        if not record.get("source") or not record.get("loader_ref"):
            issues.append("layer3_g3_replay_record_missing")
            missing_refs.append(f"{record_id}:producer_or_loader")
        if not record.get("payload_fingerprint_ref"):
            issues.append("layer3_g3_replay_record_missing")
            missing_refs.append(f"{record_id}:payload_fingerprint_ref")

    method_refs = {
        str(ref)
        for binding in _sequence(payload.get("method_requirement_bindings"))
        for ref in _sequence(_mapping(binding).get("method_requirement_refs"))
    }
    if not method_refs:
        issues.append("layer3_g3_method_requirement_missing")
    proof_records = tuple(
        _mapping(record) for record in _sequence(payload.get("proof_carrying_analytics_records"))
    )
    passing_proofs = tuple(record for record in proof_records if record.get("status") == "pass")
    if not passing_proofs:
        issues.append("layer3_g3_proof_carrying_record_missing")
    for proof in passing_proofs:
        proof_id = str(proof.get("binding_id") or proof.get("proof_ref") or "unknown")
        certificate_refs = tuple(
            str(ref) for ref in _sequence(proof.get("certificate_resolution_record_refs"))
        )
        if not certificate_refs:
            issues.append("layer3_g3_proof_carrying_record_missing")
            issues.append("layer3_g3_replay_record_missing")
            missing_refs.append(f"{proof_id}:certificate_resolution_record_refs")
        elif any(ref not in resolution_record_ids for ref in certificate_refs):
            issues.append("layer3_g3_replay_record_missing")
            missing_refs.append(f"{proof_id}:certificate_resolution_record_refs")
        proof_method_refs = tuple(
            str(ref) for ref in _sequence(proof.get("method_requirement_refs"))
        )
        if not proof_method_refs or any(ref not in method_refs for ref in proof_method_refs):
            issues.append("layer3_g3_method_requirement_missing")
        s11_record = _mapping(proof.get("s11_record"))
        boundary = _mapping(s11_record.get("authority_boundary"))
        if not boundary:
            issues.append("layer3_g3_claim_authority_leak")
            missing_refs.append(f"{proof_id}:authority_boundary")
        else:
            issues.extend(_s11_authority_issue_codes(boundary))
    return issues, missing_refs


def _g3_conformance_adapter_issues(payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    registry = _mapping(payload.get("adapter_contract_registry"))
    registry_path_ids = tuple(
        str(path_id) for path_id in _sequence(registry.get("adapter_path_ids"))
    )
    registry_path_id_set = set(registry_path_ids)
    if registry.get("status") != "pass":
        issues.extend(str(code) for code in _sequence(registry.get("issue_codes")))
        if not _sequence(registry.get("issue_codes")):
            issues.append("layer3_g3_adapter_contract_registry_missing")
    if set(registry_path_ids) - set(G3_ADAPTER_PATH_IDS):
        issues.append("layer3_g3_adapter_unknown_path")
    if set(G3_ADAPTER_PATH_IDS) - set(registry_path_ids):
        issues.append("layer3_g3_adapter_contract_registry_missing")
    admission = _mapping(payload.get("adapter_admission_registry"))
    if admission.get("status") != "pass":
        issues.extend(str(code) for code in _sequence(admission.get("issue_codes")))
    for record in _sequence(admission.get("records")):
        adapter_record = _mapping(record)
        path_refs = tuple(
            str(ref) for ref in _sequence(adapter_record.get("adapter_contract_path_refs"))
        )
        if any(path_ref not in registry_path_id_set for path_ref in path_refs):
            issues.append("layer3_g3_adapter_unknown_path")
        if adapter_record.get("conformance_status") not in {None, "pass"}:
            issues.append("layer3_g3_adapter_semantic_loss")
        if _sequence(adapter_record.get("semantic_loss_blockers")):
            issues.append("layer3_g3_adapter_semantic_loss")
        for touchpoint in _sequence(adapter_record.get("source_touchpoint_refs")):
            if not _g3_touchpoint_registered(str(touchpoint), registry_path_ids):
                issues.append("layer3_g3_adapter_touchpoint_unregistered")
    return issues


def _g3_conformance_consumer_issues(payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    consumer_checks = (
        ("ir_analytics_claim_bridge", "layer3_g3_ir_analytics_bridge_missing"),
        ("claim_registry_consumer_gate", "layer3_g3_claim_registry_consumer_gate_missing"),
        (
            "baseline_comparison_consumer_gate",
            "layer3_g3_baseline_comparison_consumer_gate_missing",
        ),
        ("w12d_consumer_gate", "layer3_g3_w12d_consumer_gate_missing"),
        ("public_export_projection_refs", "layer3_g3_public_raw_proof_leak"),
        ("proof_carrying_audit_surface", "layer3_g3_public_raw_proof_leak"),
    )
    for key, code in consumer_checks:
        record = _mapping(payload.get(key))
        if record.get("status") != "pass":
            issues.extend(str(issue) for issue in _sequence(record.get("issue_codes")))
            issues.append(code)
    baseline = _mapping(payload.get("baseline_comparison_consumer_gate"))
    issues.extend(_s11_authority_issue_codes(_mapping(baseline.get("authority_boundary"))))
    return issues


def _g3_module_load_heavy_import_refs() -> tuple[str, ...]:
    banned_top_level_imports = (
        "import duckdb",
        "from polisyos.core.artifacts.store import",
        "from polisyos.ir.analytics.causal import",
        "from polisyos.ir.analytics.negative_certificate import",
        "from polisyos.ir.analytics.partial_identification import",
        "from polisyos.ir.analytics.proof_composability import",
        "from polisyos.ir.analytics.dual_certificate import",
        "from polisyos.scientist.policy_design.claim_decomposition import",
        "from polisyos.scientist.policy_design.baseline_compiler import",
    )
    try:
        source_lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ("polisyos.runtime.quality.layer3_analytics_search:source_unreadable",)
    return tuple(
        line.strip()
        for line in source_lines
        if not line.startswith((" ", "\t"))
        and any(line.startswith(prefix) for prefix in banned_top_level_imports)
    )


def _g3_touchpoint_registered(touchpoint: str, adapter_path_ids: Sequence[str]) -> bool:
    if not touchpoint:
        return False
    normalized = touchpoint.replace("_", "-")
    return any(
        path_id in touchpoint or path_id.replace("_", "-") in normalized
        for path_id in adapter_path_ids
    )


def _resolved_certificate_count(payload: Mapping[str, Any]) -> int:
    certificate = _mapping(payload.get("certificate_resolution_report"))
    return int(certificate.get("resolved_certificate_count") or 0)


def _coerce_certificate_candidate(
    candidate: Layer3G3CertificateCandidate | Mapping[str, Any],
) -> Layer3G3CertificateCandidate:
    if isinstance(candidate, Layer3G3CertificateCandidate):
        return candidate
    return Layer3G3CertificateCandidate.model_validate(candidate)


def _store_identity(store: ArtifactStore | None) -> tuple[str, str | None]:
    if store is None:
        return "not_configured", None
    config = getattr(store, "artifact_store_config", None)
    if callable(config):
        try:
            payload = config()
            backend = str(getattr(payload, "backend", "configured"))
            root = getattr(payload, "root", None)
            return backend, str(root) if root is not None else None
        except Exception:
            root = getattr(store, "root", None)
            return type(store).__name__, str(root) if root is not None else None
    root = getattr(store, "root", None)
    return type(store).__name__, str(root) if root is not None else None


def _candidate_artifact_ref(candidate: Layer3G3CertificateCandidate) -> Mapping[str, Any]:
    return _mapping(candidate.artifact_ref)


def _candidate_artifact_id(candidate: Layer3G3CertificateCandidate) -> str | None:
    if candidate.artifact_id:
        return str(candidate.artifact_id)
    artifact_ref = _candidate_artifact_ref(candidate)
    artifact_id = artifact_ref.get("artifact_id")
    return str(artifact_id) if artifact_id else None


def _manifest_ref(artifact_id: str, manifest: object) -> str:
    manifest_hash = _json_hash_ref(_jsonable_payload(manifest))
    return f"cas-manifest://{artifact_id}#{manifest_hash}"


def _resolution_failure(
    candidate: Layer3G3CertificateCandidate,
    *,
    issue_codes: Sequence[str],
    status: Literal["fail", "blocked"] = "fail",
) -> Layer3G3CertificateResolutionRecord:
    return Layer3G3CertificateResolutionRecord(
        record_id=f"g3-certificate-resolution:{_stable_id(candidate.candidate_id, *issue_codes)}",
        candidate_id=candidate.candidate_id,
        status=status,
        certificate_kind=candidate.certificate_kind,
        artifact_ref=candidate.artifact_ref,
        artifact_id=_candidate_artifact_id(candidate),
        evidence_role="blocking" if status == "blocked" else "unknown",
        blocking=status == "blocked",
        source=candidate.source,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _resolve_one_certificate_candidate(
    candidate: Layer3G3CertificateCandidate,
    store: ArtifactStore | None,
) -> Layer3G3CertificateResolutionRecord:
    if candidate.tenant_scope_status == "denied":
        return _resolution_failure(
            candidate,
            issue_codes=("layer3_g3_tenant_scoped_manifest_denied",),
            status="blocked",
        )
    if (
        candidate.selected_ref_only
        or candidate.candidate_ref.startswith("certificate://")
        or candidate.candidate_ref.startswith("scientist-level2-warning://")
        or not _candidate_artifact_ref(candidate)
    ):
        return _resolution_failure(
            candidate,
            issue_codes=("layer3_g3_unresolved_certificate_binding",),
        )
    if store is None:
        return _resolution_failure(
            candidate,
            issue_codes=("layer3_g3_certificate_resolution_missing",),
        )

    try:
        typed_payload, typed_payload_kind, loader_ref = _load_typed_certificate_payload(
            candidate,
            store,
        )
    except PermissionError:
        return _resolution_failure(
            candidate,
            issue_codes=("layer3_g3_tenant_scoped_manifest_denied",),
            status="blocked",
        )
    except Exception:
        return _resolution_failure(
            candidate,
            issue_codes=("layer3_g3_certificate_resolution_missing",),
        )

    payload = _jsonable_payload(typed_payload)
    payload_fingerprint = _json_hash_ref(payload)
    artifact_id = _candidate_artifact_id(candidate)
    evidence_role, status, positive_closure, blocking, limiting, issue_codes = (
        _certificate_resolution_semantics(candidate, typed_payload, typed_payload_kind)
    )
    return Layer3G3CertificateResolutionRecord(
        record_id=(
            "g3-certificate-resolution:"
            f"{_stable_id(candidate.candidate_id, payload_fingerprint)}"
        ),
        candidate_id=candidate.candidate_id,
        status=status,
        certificate_kind=candidate.certificate_kind,
        typed_payload_kind=typed_payload_kind,
        artifact_ref=candidate.artifact_ref,
        artifact_id=artifact_id,
        manifest_ref=f"cas-manifest://{artifact_id}" if artifact_id else None,
        payload_fingerprint_ref=payload_fingerprint,
        evidence_role=evidence_role,
        positive_proof_closure=positive_closure,
        blocking=blocking,
        limiting=limiting,
        source=candidate.source,
        loader_ref=loader_ref,
        issue_codes=issue_codes,
    )


def _load_typed_certificate_payload(
    candidate: Layer3G3CertificateCandidate,
    store: ArtifactStore,
) -> tuple[object, str, str]:
    artifact_ref = dict(_candidate_artifact_ref(candidate))
    certificate_kind = candidate.certificate_kind
    artifact_kind = str(artifact_ref.get("kind", ""))
    normalized_kind = certificate_kind or artifact_kind.removeprefix("ir.")
    if normalized_kind == "proof_bundle" or artifact_kind == "ir.proof_bundle":
        causal_module = importlib.import_module("polisyos.ir.analytics.causal")
        refs_module = importlib.import_module("polisyos.ir.registry.refs")
        load_proof_bundle = causal_module.load_proof_bundle
        proof_bundle_ref_cls = refs_module.ProofBundleRef

        ref = proof_bundle_ref_cls.model_validate(artifact_ref)
        return (
            load_proof_bundle(store, ref),
            "ProofBundle",
            "polisyos.ir.analytics.causal.load_proof_bundle",
        )
    if normalized_kind == "negative_certificate" or artifact_kind == "ir.negative_certificate":
        negative_module = importlib.import_module(
            "polisyos.ir.analytics.negative_certificate"
        )
        refs_module = importlib.import_module("polisyos.ir.registry.refs")
        load_negative_certificate = negative_module.load_negative_certificate
        negative_certificate_ref_cls = refs_module.NegativeCertificateRef

        ref = negative_certificate_ref_cls.model_validate(artifact_ref)
        return (
            load_negative_certificate(store, ref),
            "NegativeCertificate",
            "polisyos.ir.analytics.negative_certificate.load_negative_certificate",
        )
    if (
        normalized_kind == "proof_composability"
        or artifact_kind == "ir.proof_composability_certificate"
    ):
        composability_module = importlib.import_module(
            "polisyos.ir.analytics.proof_composability"
        )
        refs_module = importlib.import_module("polisyos.ir.registry.refs")
        load_proof_composability_certificate = (
            composability_module.load_proof_composability_certificate
        )
        proof_composability_certificate_ref_cls = (
            refs_module.ProofComposabilityCertificateRef
        )

        ref = proof_composability_certificate_ref_cls.model_validate(artifact_ref)
        return (
            load_proof_composability_certificate(store, ref),
            "ProofComposabilityCertificate",
            "polisyos.ir.analytics.proof_composability.load_proof_composability_certificate",
        )
    if normalized_kind == "bounds_bundle" or artifact_kind == "ir.bounds_bundle":
        partial_module = importlib.import_module(
            "polisyos.ir.analytics.partial_identification"
        )
        refs_module = importlib.import_module("polisyos.ir.registry.refs")
        load_bounds_bundle = partial_module.load_bounds_bundle
        bounds_bundle_ref_cls = refs_module.BoundsBundleRef

        ref = bounds_bundle_ref_cls.model_validate(artifact_ref)
        return (
            load_bounds_bundle(store, ref),
            "BoundsBundle",
            "polisyos.ir.analytics.partial_identification.load_bounds_bundle",
        )
    if normalized_kind == "dual_certificate" or artifact_kind == "ir.dual_certificate":
        dual_module = importlib.import_module("polisyos.ir.analytics.dual_certificate")
        refs_module = importlib.import_module("polisyos.ir.registry.refs")
        load_dual_certificate_bundle = dual_module.load_dual_certificate_bundle
        dual_certificate_ref_cls = refs_module.DualCertificateRef

        ref = dual_certificate_ref_cls.model_validate(artifact_ref)
        return (
            load_dual_certificate_bundle(store, ref),
            "DualCertificateBundle",
            "polisyos.ir.analytics.dual_certificate.load_dual_certificate_bundle",
        )
    raise ValueError(f"unsupported G3 certificate kind: {certificate_kind}")


def _certificate_resolution_semantics(
    candidate: Layer3G3CertificateCandidate,
    typed_payload: object,
    typed_payload_kind: str,
) -> tuple[
    Literal["positive", "blocking", "limiting", "control_plane", "unknown"],
    Literal["resolved", "fail", "blocked", "limited"],
    bool,
    bool,
    bool,
    tuple[str, ...],
]:
    issue_codes: list[str] = []
    if typed_payload_kind == "ProofBundle":
        proof_status = str(getattr(typed_payload, "proof_status", ""))
        composability_status = str(getattr(typed_payload, "composability_status", ""))
        if proof_status == "identified" and composability_status != "rederive":
            return "positive", "resolved", True, False, False, ()
        issue_codes.append("layer3_g3_certificate_resolution_missing")
        return "blocking", "blocked", False, True, False, tuple(issue_codes)
    if typed_payload_kind == "NegativeCertificate":
        return "blocking", "resolved", False, True, False, ()
    if typed_payload_kind == "ProofComposabilityCertificate":
        payload_status = getattr(typed_payload, "status", "")
        status = str(getattr(payload_status, "value", payload_status))
        if status == "rederive":
            issue_codes.append("layer3_g3_proof_composability_bypass")
            return "blocking", "blocked", False, True, False, tuple(issue_codes)
        if status == "reusable":
            return "positive", "resolved", True, False, False, ()
        return "limiting", "limited", False, False, True, ()
    if typed_payload_kind == "BoundsBundle":
        dual_certificate_ref = getattr(typed_payload, "dual_certificate_ref", None)
        sharpness_status = str(getattr(typed_payload, "sharpness_status", ""))
        candidate_claims_certified = bool(
            candidate.metadata.get("claims_sharp_or_certified_bounds")
            or _mapping(getattr(typed_payload, "metadata", {})).get(
                "claims_sharp_or_certified_bounds"
            )
            or sharpness_status == "sharp"
        )
        if candidate_claims_certified and dual_certificate_ref is None:
            issue_codes.append("layer3_g3_bounds_dual_certificate_missing")
            return "limiting", "blocked", False, False, True, tuple(issue_codes)
        return "limiting", "resolved", False, False, True, ()
    if typed_payload_kind == "DualCertificateBundle":
        return "positive", "resolved", True, False, False, ()
    issue_codes.append("layer3_g3_certificate_resolution_missing")
    return "unknown", "fail", False, False, False, tuple(issue_codes)


def _load_g2_method_requirement_bindings(repo_root: Path | None) -> tuple[dict[str, Any], ...]:
    if repo_root is None:
        return ()
    path = _resolve_repo_path(
        Path(repo_root).resolve(),
        POLICY_DESIGN_CASE_DIR / "layer3_g2_method_requirement_bindings.json",
    )
    if not path.exists():
        return ()
    try:
        payload = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(
        dict(binding)
        for binding in _sequence(payload.get("method_requirement_bindings"))
        if isinstance(binding, Mapping)
    )


def _compile_g3_fallback_method_requirements(
    request: Layer3G3AnalyticsRequest,
) -> tuple[dict[str, Any], ...]:
    from polisyos.method_requirement import (
        MethodValidityRequirementSpec,
        compile_method_validity_requirements,
    )

    claim = {
        "claim_id": request.claim_id,
        "claim_type": "causal",
        "claim_family": "causal",
        "text": f"{request.cause} affects {request.effect}",
        "baseline_refs": [request.baseline_ref] if request.baseline_ref else [],
        "alternative_refs": list(request.alternative_refs),
        "metadata": {
            "cause": request.cause,
            "effect": request.effect,
            "target_context_id": request.target_context_id,
        },
    }
    artifact = compile_method_validity_requirements(
        run_id=request.case_id,
        claims=(claim,),
        metadata={"producer": "layer3_g3_w7c_fallback"},
    )
    if artifact.requirements:
        return tuple(requirement.model_dump(mode="json") for requirement in artifact.requirements)
    fallback = MethodValidityRequirementSpec.model_validate(
        {
            "requirement_id": (
                request.method_requirement_refs[0]
                if request.method_requirement_refs
                else f"g3-method-req:{_stable_id(request.request_id)}"
            ),
            "run_id": request.case_id,
            "claim_id": request.claim_id,
            "identification_class": "point",
            "method_expectations": ["causal_identification"],
            "required_method_families": ["causal_identification"],
            "facet_refs": list(request.concept_refs),
            "obligation_refs": [f"obligation://{request.claim_id}"],
            "baseline_refs": [request.baseline_ref] if request.baseline_ref else [],
            "alternative_refs": list(request.alternative_refs),
        }
    )
    return (fallback.model_dump(mode="json"),)


def _adapt_method_requirement_spec(
    spec: Mapping[str, Any] | BaseModel,
    request: Layer3G3AnalyticsRequest,
) -> dict[str, Any]:
    from polisyos.method_requirement import MethodValidityRequirementSpec

    payload = spec.model_dump(mode="json") if isinstance(spec, BaseModel) else dict(spec)
    metadata = dict(_mapping(payload.get("metadata")))
    metadata.update(
        {
            "g3_request_ref": request.request_id,
            "g3_claim_id": request.claim_id,
            "source_requirement_id": payload.get("requirement_id"),
        }
    )
    payload["run_id"] = request.case_id
    payload["claim_id"] = request.claim_id
    payload.setdefault(
        "requirement_id",
        request.method_requirement_refs[0]
        if request.method_requirement_refs
        else f"g3-method-req:{_stable_id(request.request_id)}",
    )
    if request.baseline_ref:
        payload["baseline_refs"] = _dedupe(
            [*list(_sequence(payload.get("baseline_refs"))), request.baseline_ref]
        )
    if request.alternative_refs:
        payload["alternative_refs"] = _dedupe(
            [*list(_sequence(payload.get("alternative_refs"))), *request.alternative_refs]
        )
    if request.concept_refs:
        payload["facet_refs"] = _dedupe(
            [*list(_sequence(payload.get("facet_refs"))), *request.concept_refs]
        )
    payload["metadata"] = metadata
    return MethodValidityRequirementSpec.model_validate(payload).model_dump(mode="json")


def _method_requirement_authority_boundary() -> dict[str, Any]:
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
            "claim_authority",
            "closeout_pass",
        ],
    }


def _merge_g3_denials(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys([*(str(value) for value in values if str(value)), *G3_MAY_NOT_USE_FOR])
    )


def _g3_projection_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["g3_projection_audit"],
        "may_not_use_for": list(G3_MAY_NOT_USE_FOR),
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": [LAYER3_G3_RULE_VERSION],
    }


def _g3_adapter_admission_records(
    adapter_path_ids: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "adapter_id": path_id,
            "source_ids": ["layer3-g3-analytics-search"],
            "port_ids": ["layer3.analytics_search_adapter"],
            "maturity": "predictive",
            "promotion_state": "shadow",
            "conformance_status": "pass",
            "quarantine_check": "not_blocked",
            "admission_state": "admitted",
            "admitted": True,
            "adapter_contract_path_refs": [path_id],
            "source_touchpoint_refs": [
                f"touchpoint://runtime-quality/{path_id.replace('_', '-')}"
            ],
        }
        for path_id in adapter_path_ids
    )


def _g3_adapter_surface_payload(surface_cls: type[BaseModel], *, surface: str) -> BaseModel:
    field_payload = {
        "status": "pass",
        "provenance": "runtime_emitted",
        "owner": "team-runtime-quality",
        "schema": LAYER3_G3_SCHEMA_VERSION,
        "rule_version": LAYER3_G3_RULE_VERSION,
        "lineage": "layer3_g3_deterministic_first_case",
        "tenant": "policy-design-case",
        "time_context": "runtime_snapshot",
        "jurisdiction": "UA",
        "source_family": "ir_analytics",
        "method_expectation": "proof_carrying_analytics",
        "claim_sets": ["g3_default_claim"],
        "rights": "internal_audit_projection",
        "freshness": "current_snapshot",
        "contamination": "none_known",
        "authority_boundary": _g3_projection_authority_boundary(),
    }
    return surface_cls(
        surface=surface,
        field_families={
            family: dict(field_payload)
            for family in (
                "runtime_refs",
                "final_claims",
                "source_data_context",
                "legal_context",
                "foundry_method_context",
                "scorecard_identity_and_gates",
                "approval_readiness_public_status",
                "mode_and_fallback_records",
            )
        },
    )


def _g3_deterministic_uncertainty_refs(
    *,
    request: Layer3G3AnalyticsRequest,
    method_requirement_bindings: Sequence[Layer3G3MethodRequirementBinding],
) -> tuple[str, ...]:
    method_specs = tuple(
        spec
        for binding in method_requirement_bindings
        for spec in binding.method_requirement_specs
        if isinstance(spec, Mapping)
    )
    if any(bool(spec.get("requires_uncertainty_envelope")) for spec in method_specs):
        return ()
    return (f"uncertainty://layer3/g3/{request.case_id}/deterministic-exact",)


def _claim_binding_from_g3_proof_binding(
    binding: Layer3G3ProofCarryingAnalyticsBinding | Mapping[str, Any],
) -> dict[str, Any]:
    payload = _dump_model(binding) if isinstance(binding, BaseModel | Mapping) else {}
    record = _mapping(payload.get("s11_record"))
    return {
        "claim_id": record.get("claim_id"),
        "analytics_ref": _first_present_str(_sequence(record.get("ir_analytics_refs"))),
        "method_output_refs": list(_sequence(record.get("method_output_refs"))),
        "certificate_refs": list(_sequence(record.get("ir_certificate_refs"))),
        "negative_certificate_refs": list(_sequence(record.get("negative_certificate_refs"))),
        "proof_status": record.get("proof_status"),
        "proof_composability_status": record.get("proof_composability_status"),
        "proof_composability_refs": list(_sequence(record.get("proof_composability_refs"))),
        "uncertainty_refs": list(_sequence(record.get("uncertainty_refs"))),
        "baseline_refs": (
            [record.get("baseline_design_ref")] if record.get("baseline_design_ref") else []
        ),
        "comparison_refs": (
            [record.get("design_comparison_ref")]
            if record.get("design_comparison_ref")
            else []
        ),
        "alternative_refs": list(_sequence(record.get("alternative_design_refs"))),
        "independence_refs": list(_sequence(record.get("independence_refs"))),
        "limitation_refs": list(_sequence(record.get("limitation_refs"))),
        "blocker_refs": list(_sequence(record.get("blocker_refs"))),
    }


def _g3_issue_codes_from_ir_bridge(bridge: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []
    for issue in _sequence(bridge.get("issues")):
        code = str(_mapping(issue).get("code", ""))
        if code == "ir_analytics_method_requirement_uncertainty_missing":
            codes.append("layer3_g3_uncertainty_or_bounds_ref_missing")
        elif code in {
            "ir_analytics_method_requirement_certificate_missing",
            "ir_analytics_method_requirement_method_output_missing",
            "ir_analytics_method_requirement_negative_certificate_missing",
            "ir_analytics_method_requirement_binding_missing",
        }:
            codes.append("layer3_g3_method_requirement_bypass")
        elif code in {
            "runtime_claim_registry_ir_analytics_claim_id_missing",
            "runtime_claim_registry_ir_analytics_proof_refs_missing",
            "runtime_claim_registry_ir_analytics_blocked",
        }:
            codes.append("layer3_g3_ir_analytics_bridge_missing")
    if bridge.get("status") != "pass" and not codes:
        codes.append("layer3_g3_ir_analytics_bridge_missing")
    return tuple(dict.fromkeys(codes))


def _string_tuple(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in _sequence(value) if str(item))


def _first_present_str(values: object) -> str | None:
    for value in _sequence(values):
        text = str(value or "").strip()
        if text:
            return text
    return None


def _catalog_entry_from_ir_type(entry: IRTypeInfo) -> Layer3G3IRCatalogEntry:
    fields = tuple(entry.fields)
    name = str(entry.name)
    fqn = str(entry.fqn)
    module = str(entry.module)
    field_refs = tuple(str(field.name) for field in fields)
    ref_field_refs = tuple(
        field.name
        for field in fields
        if "ref" in field.name.lower() or getattr(field, "references", ())
    )
    certificate_field_refs = tuple(
        field.name
        for field in fields
        if any(token in field.name.lower() for token in ("certificate", "proof", "bundle"))
    )
    proof_status_field_refs = tuple(
        field.name
        for field in fields
        if "proof_status" in field.name.lower() or field.name.lower() == "status"
    )
    composability_field_refs = tuple(
        field.name for field in fields if "composability" in field.name.lower()
    )
    persistence_helper_refs = _persistence_helper_refs(module)
    producer_refs = _producer_refs(module, name)
    certificate_kinds = _certificate_kinds_for(name, fqn, field_refs)
    return Layer3G3IRCatalogEntry(
        entry_id=f"ir-analytics-catalog-entry:{_stable_id(fqn)}",
        name=name,
        fqn=fqn,
        module=module,
        kind=str(getattr(entry.kind, "value", entry.kind)),
        schema_version=entry.schema_version,
        public_status=str(getattr(entry.public_status, "value", entry.public_status)),
        exported=bool(entry.exported_from),
        field_refs=field_refs,
        ref_field_refs=ref_field_refs,
        certificate_field_refs=certificate_field_refs,
        proof_status_field_refs=proof_status_field_refs,
        composability_field_refs=composability_field_refs,
        persistence_helper_refs=persistence_helper_refs,
        producer_refs=producer_refs,
        certificate_kinds=certificate_kinds,
        summary=entry.summary,
    )


def _certificate_kinds_for(name: str, fqn: str, field_refs: Sequence[str]) -> tuple[str, ...]:
    text = " ".join((name, fqn, *field_refs)).lower()
    kinds: list[str] = []
    if "negativecertificate" in text or "negative_certificate" in text:
        kinds.append("negative_certificate")
    if "proofbundle" in text or "proof_bundle" in text:
        kinds.append("proof_bundle")
    if "composability" in text:
        kinds.append("proof_composability")
    if "dualcertificate" in text or "dual_certificate" in text:
        kinds.append("dual_certificate")
    if "bound" in text and "certificate" in text:
        kinds.append("bounds_certificate")
    if "certificate" in text and "certificate" not in kinds:
        kinds.append("certificate")
    if "proof" in text and not any(kind.startswith("proof") for kind in kinds):
        kinds.append("proof")
    return tuple(dict.fromkeys(kinds))


def _persistence_helper_refs(module_name: str) -> tuple[str, ...]:
    refs: list[str] = []
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return ()
    for name, obj in vars(module).items():
        if not inspect.isfunction(obj):
            continue
        lowered = name.lower()
        if any(token in lowered for token in ("persist", "load", "put_", "get_")):
            refs.append(f"{module_name}.{name}")
    if "put_json_artifact" in vars(module):
        refs.append("polisyos.ir.artifacts.put_json_artifact")
    if "get_json_artifact" in vars(module):
        refs.append("polisyos.ir.artifacts.get_json_artifact")
    return tuple(sorted(dict.fromkeys(refs))[:12])


def _producer_refs(module_name: str, type_name: str) -> tuple[str, ...]:
    refs: list[str] = []
    tokens = tuple(token for token in _name_tokens(type_name) if len(token) >= 4)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return ()
    for name, obj in vars(module).items():
        if not inspect.isfunction(obj):
            continue
        lowered = name.lower()
        if not any(
            prefix in lowered
            for prefix in ("build", "create", "infer", "certify", "validate")
        ):
            continue
        if not tokens or any(token in lowered for token in tokens):
            refs.append(f"{module_name}.{name}")
    return tuple(sorted(dict.fromkeys(refs))[:8])


def _materialize_catalog_rows(
    rows: Sequence[Layer3G3IRCatalogEntry],
) -> duckdb.DuckDBPyConnection:
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE ir_catalog (
            entry_id VARCHAR,
            name VARCHAR,
            fqn VARCHAR,
            module VARCHAR,
            kind VARCHAR,
            schema_version VARCHAR,
            public_status VARCHAR,
            exported BOOLEAN,
            field_refs_text VARCHAR,
            ref_field_refs_text VARCHAR,
            certificate_field_refs_text VARCHAR,
            proof_status_field_refs_text VARCHAR,
            composability_field_refs_text VARCHAR,
            persistence_helper_refs_text VARCHAR,
            producer_refs_text VARCHAR,
            certificate_kinds_text VARCHAR,
            searchable_text VARCHAR
        )
        """
    )
    con.execute("CREATE INDEX ir_catalog_entry_id_idx ON ir_catalog(entry_id)")
    con.execute("CREATE INDEX ir_catalog_name_idx ON ir_catalog(name)")
    for row in rows:
        field_text = " ".join(row.field_refs)
        ref_text = " ".join(row.ref_field_refs)
        certificate_text = " ".join(row.certificate_field_refs)
        proof_status_text = " ".join(row.proof_status_field_refs)
        composability_text = " ".join(row.composability_field_refs)
        persistence_text = " ".join(row.persistence_helper_refs)
        producer_text = " ".join(row.producer_refs)
        kind_text = " ".join(row.certificate_kinds)
        searchable = " ".join(
            str(part)
            for part in (
                row.entry_id,
                row.name,
                row.fqn,
                row.module,
                row.kind,
                row.public_status,
                field_text,
                ref_text,
                certificate_text,
                proof_status_text,
                composability_text,
                persistence_text,
                producer_text,
                kind_text,
                row.summary or "",
            )
        ).lower()
        con.execute(
            "INSERT INTO ir_catalog VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.entry_id,
                row.name,
                row.fqn,
                row.module,
                row.kind,
                row.schema_version,
                row.public_status,
                row.exported,
                field_text.lower(),
                ref_text.lower(),
                certificate_text.lower(),
                proof_status_text.lower(),
                composability_text.lower(),
                persistence_text.lower(),
                producer_text.lower(),
                kind_text.lower(),
                searchable,
            ),
        )
    return con


def _validate_task1_search(
    payload: Mapping[str, Any],
    issues: list[Layer3G3ValidationIssue],
) -> None:
    coverage = _mapping(payload.get("ir_catalog_coverage"))
    if coverage.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_g3_ir_catalog_coverage_missing",
                "$.ir_catalog_coverage",
                "G3 requires passing IR analytics catalog coverage.",
            )
        )
    if coverage.get("full_catalog_route") in FORBIDDEN_FULL_CATALOG_ROUTES:
        issues.append(
            _issue(
                "layer3_g3_ir_catalog_hardcode_closure",
                "$.ir_catalog_coverage.full_catalog_route",
                "G3 full IR catalog coverage cannot close through a forbidden surrogate route.",
            )
        )
    if not _sequence(payload.get("l2_skg_proof_candidate_bindings")):
        issues.append(
            _issue(
                "layer3_g3_l2_skg_proof_candidate_binding_missing",
                "$.l2_skg_proof_candidate_bindings",
                "G3 requires G2 L2/SKG proof-candidate provenance bindings.",
            )
        )
    if not _sequence(payload.get("ir_analytics_search_ledgers")):
        issues.append(
            _issue(
                "layer3_g3_search_ledger_missing",
                "$.ir_analytics_search_ledgers",
                "G3 requires replayable IR analytics search ledgers.",
            )
        )
    if not _sequence(payload.get("ir_analytics_query_traces")):
        issues.append(
            _issue(
                "layer3_g3_query_trace_missing",
                "$.ir_analytics_query_traces",
                "G3 requires replayable IR analytics query traces.",
            )
        )
    quality = _mapping(payload.get("search_engineering_quality"))
    if quality.get("status") != "pass":
        issue_codes = _sequence(quality.get("issue_codes")) or (
            "layer3_g3_ir_catalog_search_not_indexed",
        )
        for code in issue_codes:
            issues.append(_issue(str(code), "$.search_engineering_quality", str(code)))
    recall = _mapping(payload.get("search_recall_freshness"))
    recall_issue_codes = tuple(str(code) for code in _sequence(recall.get("issue_codes")))
    if (
        recall.get("status") != "pass"
        or recall.get("freshness_status") != "pass"
        or int(recall.get("recalled_seed_count") or 0)
        != int(recall.get("known_seed_count") or 0)
    ):
        for code in recall_issue_codes or (
            "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
        ):
            issues.append(_issue(str(code), "$.search_recall_freshness", str(code)))
    if recall.get("freshness_status") != "pass" and (
        "layer3_g3_search_ceiling_repair_required" not in recall_issue_codes
    ):
        issues.append(
            _issue(
                "layer3_g3_search_ceiling_repair_required",
                "$.search_recall_freshness.freshness_status",
                "G3 must repair stale recall/index state before proof-domain ceiling claims.",
            )
        )


def _validate_later_task_placeholders(
    payload: Mapping[str, Any],
    issues: list[Layer3G3ValidationIssue],
) -> None:
    certificate = _mapping(payload.get("certificate_resolution_report"))
    if certificate.get("resolved_certificate_count", 0) <= 0:
        issues.append(
            _issue(
                "layer3_g3_certificate_resolution_missing",
                "$.certificate_resolution_report",
                "G3 requires at least one resolved typed proof/certificate payload.",
            )
        )
    if not _sequence(payload.get("proof_carrying_analytics_records")):
        issues.append(
            _issue(
                "layer3_g3_proof_carrying_record_missing",
                "$.proof_carrying_analytics_records",
                "G3 requires proof-carrying analytics records built from resolved certificates.",
            )
        )
    bridge = _mapping(payload.get("ir_analytics_claim_bridge"))
    if bridge.get("status") != "pass":
        issues.append(
            _issue(
                "layer3_g3_ir_analytics_bridge_missing",
                "$.ir_analytics_claim_bridge",
                "G3 requires an ir_analytics_bridge built from valid proof records.",
            )
        )


def _validate_task7_conformance(
    payload: Mapping[str, Any],
    issues: list[Layer3G3ValidationIssue],
) -> None:
    conformance = _mapping(payload.get("conformance_report"))
    if conformance.get("status") != "pass":
        issue_codes = _sequence(conformance.get("issue_codes")) or (
            "layer3_g3_replay_record_missing",
        )
        for code in issue_codes:
            issues.append(
                _issue(
                    str(code),
                    "$.conformance_report",
                    f"G3 final conformance failed: {code}",
                )
            )


def _default_g3_request() -> Layer3G3AnalyticsRequest:
    return Layer3G3AnalyticsRequest(
        request_id="g3-request:default-analytics-search",
        claim_id="claim:g3:default-analytics-search",
        case_id=G3_PINNED_CASE_ID,
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        target_context_id="UA",
        comparison_ref="comparison://layer3/g3/default-analytics-search",
        baseline_ref="baseline://layer3/g3/default-analytics-search",
        alternative_refs=("alternative://layer3/g3/default-analytics-search",),
        concept_refs=("concept://layer3/g3/default-analytics-search",),
        semantic_spine_refs=("semantic-spine://layer3/g2/default",),
        method_requirement_refs=("method-requirement://layer3/g2/default",),
        certificate_kinds=("proof_bundle", "certificate", "negative_certificate"),
        limit=16,
    )


def _default_g3_claim_ledger_route() -> tuple[Any, Layer3G3AnalyticsRequest, str, str]:
    claims_module = importlib.import_module("polisyos.scientist.evidence.claims.models")
    decomposition_module = importlib.import_module(
        "polisyos.scientist.policy_design.claim_decomposition"
    )
    claim_use_enum = claims_module.ClaimUse
    decomposition_compiler_cls = decomposition_module.ClaimDecompositionCompiler
    decomposition_facet_cls = decomposition_module.ClaimDecompositionFacet
    decomposition_input_cls = decomposition_module.ClaimDecompositionInput
    decomposition_named_alternative_cls = (
        decomposition_module.ClaimDecompositionNamedAlternative
    )
    decomposition_obligation_cls = decomposition_module.ClaimDecompositionObligation
    default_request = _default_g3_request()
    outcome_ref = default_request.cause.replace("policy.", "").replace(".", "_")
    outcome_label = outcome_ref.replace("_", " ")
    outcome_concept_ref = f"concept.{outcome_ref}"

    ledger = decomposition_compiler_cls().compile(
        decomposition_input_cls(
            run_id="run_layer3_g3_default",
            intent=(
                "Choose an MSME credit guarantee only if it beats no-action "
                "and named grant alternatives on credit access."
            ),
            facets=[
                decomposition_facet_cls(
                    facet_id="facet_instrument",
                    facet_type="instrument_type",
                    value="credit guarantee",
                    concept_spine_refs=["concept.msme_credit_guarantee"],
                    authority_profile_refs=["authority.fiscal_delegated"],
                ),
                decomposition_facet_cls(
                    facet_id="facet_outcome",
                    facet_type="outcome_channel",
                    value=outcome_label,
                    concept_spine_refs=[outcome_concept_ref],
                    authority_profile_refs=["authority.fiscal_delegated"],
                ),
            ],
            obligations=[
                decomposition_obligation_cls(
                    obligation_id="obl_compare",
                    family="welfare comparison",
                    description="Compare selected option against baselines and alternatives.",
                    facet_refs=["facet_instrument", "facet_outcome"],
                    concept_spine_refs=[outcome_concept_ref],
                    authority_profile_refs=["authority.fiscal_delegated"],
                )
            ],
            named_alternatives=[
                decomposition_named_alternative_cls(
                    alternative_id="alt_direct_grants",
                    label="Direct MSME grants",
                    description="Provide direct grants instead of guarantees.",
                )
            ],
        )
    )
    superiority_claim = next(
        claim for claim in ledger.claims if claim.claim_use is claim_use_enum.SUPERIORITY
    )
    baseline_ref = sorted(superiority_claim.baseline_refs)[0]
    alternative_ref = sorted(superiority_claim.alternative_refs)[0]
    selected_option_ref = "selected:layer3-g3-msme-credit-guarantee"
    request = default_request.model_copy(
        update={
            "claim_id": superiority_claim.claim_id,
            "baseline_ref": baseline_ref,
            "alternative_refs": (alternative_ref,),
            "comparison_ref": "comparison://layer3/g3/default-analytics-search",
            "method_requirement_refs": ("method-requirement://layer3/g3/default",),
        }
    )
    return ledger, request, selected_option_ref, alternative_ref


def _default_g3_method_requirement(request: Layer3G3AnalyticsRequest) -> dict[str, Any]:
    return {
        "requirement_id": request.method_requirement_refs[0],
        "run_id": request.case_id,
        "claim_id": request.claim_id,
        "identification_class": "point",
        "method_expectations": ["causal_identification"],
        "required_method_families": ["causal_identification"],
        "requires_uncertainty_envelope": False,
        "requires_limitation_refs": False,
        "facet_refs": list(request.concept_refs),
        "obligation_refs": [f"obligation://{request.claim_id}"],
        "baseline_refs": [request.baseline_ref],
        "alternative_refs": list(request.alternative_refs),
    }


def _default_g3_claim_registry_claim(
    request: Layer3G3AnalyticsRequest,
) -> dict[str, Any]:
    return {
        "claim_id": request.claim_id,
        "claim_family": "recommendation",
        "major": True,
        "text": "Use G3-resolved proof as limited analytics support only.",
        "requires_ir_analytics": True,
        "scenario_requirement_refs": ["scenario.req.credit_support"],
        "data_refs": ["source.msme_panel"],
        "selected_norm_refs": ["norm.ua.credit_guarantee"],
        "portfolio_refs": ["portfolio.rec_credit_guarantee"],
        "argument_refs": ["argument.rec_credit_guarantee"],
        "warrant_refs": ["warrant.rec_credit_guarantee"],
        "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
        "counter_evidence_refs": ["counter.rec_credit_guarantee"],
        "limitation_refs": ["limitation.rec_credit_guarantee"],
        "accepted_deficit_refs": ["deficit.rec_credit_guarantee"],
        "baseline_refs": [request.baseline_ref],
        "alternative_refs": list(request.alternative_refs),
        "comparison_refs": [request.comparison_ref],
    }


def _default_g3_s11_consumer_payload(
    proof_records: Sequence[Layer3G3ProofCarryingAnalyticsBinding],
    postures: Sequence[Layer3G3S11PredictivePostureBinding],
    bridge: Layer3G3IRAnalyticsBridgeBinding,
) -> dict[str, Any]:
    proof = _dump_model(proof_records[0]) if proof_records else {}
    posture = _dump_model(postures[0]) if postures else {}
    return {
        "predictive_knowledge_ref": posture.get("predictive_knowledge_ref"),
        "proof_carrying_analytics_ref": proof.get("proof_ref"),
        "ir_analytics_bridge_ref": bridge.bridge_ref,
        "negative_certificate_refs": [],
    }


def _default_g3_s2_consumer_payload(
    request: Layer3G3AnalyticsRequest,
    proof_records: Sequence[Layer3G3ProofCarryingAnalyticsBinding],
    postures: Sequence[Layer3G3S11PredictivePostureBinding],
    bridge: Layer3G3IRAnalyticsBridgeBinding,
) -> dict[str, Any]:
    s11 = _default_g3_s11_consumer_payload(proof_records, postures, bridge)
    proof_ref = str(s11.get("proof_carrying_analytics_ref") or "")
    posture_ref = str(s11.get("predictive_knowledge_ref") or "")
    return {
        "status": "limited_by_g3_predictive_knowledge",
        "search_ledger": {
            "predictive_knowledge_refs": [posture_ref],
            "proof_carrying_analytics_refs": [proof_ref],
            "iterations": ["iteration://layer3/g3/default"],
            "refinement_decision_refs": [
                f"refinement-decision://layer3/g3/{request.case_id}"
            ],
        },
        "constraint_store": {
            "constraint_records": [
                {
                    "constraint_id": "layer2.s11.g3.default",
                    "evidence_refs": [proof_ref],
                }
            ]
        },
        "design_record": {
            "axis_positions": [
                {
                    "axis": "predictive_knowledge_relaxation",
                    "evidence_refs": [proof_ref],
                }
            ],
            "firewall_status": [
                {
                    "cell_ref": "KNOWLEDGE.predictive_knowledge_relaxation",
                    "status": "limit",
                    "evidence_refs": [proof_ref],
                }
            ],
            "projection_audiences": ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
        },
    }


def _default_g3_health_metric_delta() -> dict[str, Any]:
    return {
        "schema_version": LAYER3_G3_SCHEMA_VERSION,
        "rule_version": LAYER3_G3_RULE_VERSION,
        "metric_ids": list(EXPECTED_HEALTH_METRICS),
        "readings": {
            "adapter-semantic-loss": "0",
            "demand-pull-vs-abstention": "w12d_first_case_full_route",
            "envelope-expansion-rate": "0",
            "governance-throughput": "g3_readiness_bundle_emitted",
            "search-recall@known-seeds+index-staleness": "task1_catalog_search_ready",
        },
    }


def _dependency_file_status(repo_root: Path, filename: str) -> str:
    path = _resolve_repo_path(repo_root, POLICY_DESIGN_CASE_DIR / filename)
    return "pass" if path.exists() else "fail"


def _catalog_snapshot_hash(rows: Sequence[Layer3G3IRCatalogEntry]) -> str:
    payload = [
        row.model_dump(mode="json", exclude={"summary"})
        for row in sorted(rows, key=lambda item: item.entry_id)
    ]
    return _json_hash_ref(payload)


def _json_hash_ref(payload: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(
            _jsonable_payload(payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable_payload(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable_payload(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return value


def _stable_id(*parts: str) -> str:
    joined = "|".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def _name_tokens(name: str) -> tuple[str, ...]:
    token = ""
    tokens: list[str] = []
    for char in name:
        if char.isupper() and token:
            tokens.append(token.lower())
            token = char
        elif char in {"_", "-", "."}:
            if token:
                tokens.append(token.lower())
                token = ""
        else:
            token += char
    if token:
        tokens.append(token.lower())
    return tuple(tokens)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_text_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _path_label(path: Path) -> str:
    return str(path) if path.is_absolute() else path.as_posix()


def _dump_model(value: Mapping[str, Any] | BaseModel | object) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        payload = _jsonable_payload(value)
        return dict(payload) if isinstance(payload, Mapping) else {}
    return {}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return ()


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _issue(code: str, path: str, message: str) -> Layer3G3ValidationIssue:
    return Layer3G3ValidationIssue(code=code, path=path, message=message)


def _dedupe_issues(
    issues: Sequence[Layer3G3ValidationIssue],
) -> list[Layer3G3ValidationIssue]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Layer3G3ValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.path, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


__all__ = [
    "ALL_ISSUE_CODES",
    "LAYER3_G3_GENERATED_ARTIFACT_FAMILY_ID",
    "LAYER3_G3_RULE_VERSION",
    "LAYER3_G3_SCHEMA_VERSION",
    "LAYER3_G3_SURFACE_ID",
    "Layer3G3AdapterAdmissionBundle",
    "Layer3G3AdapterContractRegistryStatus",
    "Layer3G3AnalyticsRequest",
    "Layer3G3ArtifactStoreIndex",
    "Layer3G3BaselineComparisonConsumerGateRecord",
    "Layer3G3Bundle",
    "Layer3G3CertificateCandidate",
    "Layer3G3CertificateResolutionRecord",
    "Layer3G3CertificateResolutionReport",
    "Layer3G3ClaimRegistryConsumerGateRecord",
    "Layer3G3ConformanceReport",
    "Layer3G3GeneratedArtifactRegistrationStatus",
    "Layer3G3IRAnalyticsBridgeBinding",
    "Layer3G3IRAnalyticsQueryTrace",
    "Layer3G3IRCatalogCoverageReport",
    "Layer3G3IRCatalogEntry",
    "Layer3G3IRCatalogSearchLedger",
    "Layer3G3IRCatalogSearchResult",
    "Layer3G3L2SkgDependencyArtifacts",
    "Layer3G3L2SkgProofCandidateBinding",
    "Layer3G3MethodRequirementBinding",
    "Layer3G3ProofCarryingAnalyticsBinding",
    "Layer3G3ProofCarryingAuditSurface",
    "Layer3G3PublicExportProjectionRefSurface",
    "Layer3G3ReadinessManifest",
    "Layer3G3S11CalibrationBinding",
    "Layer3G3S11PredictivePostureBinding",
    "Layer3G3S11PrerequisiteBinding",
    "Layer3G3SearchEngineeringQualityReport",
    "Layer3G3SearchRecallFreshnessReport",
    "Layer3G3SearchRecallSeedRecord",
    "Layer3G3SemanticSpineBinding",
    "Layer3G3ValidationIssue",
    "Layer3G3ValidationReport",
    "Layer3G3W12DConsumerGateRecord",
    "build_g3_adapter_contract_registry_status",
    "build_g3_baseline_comparison_consumer_gate",
    "build_g3_certificate_resolution_report",
    "build_g3_claim_registry_consumer_gate",
    "build_g3_conformance_report",
    "build_g3_generated_artifact_registration_status",
    "build_g3_ir_analytics_bridge_bindings",
    "build_g3_ir_artifact_store_index",
    "build_g3_ir_catalog_coverage",
    "build_g3_l2_skg_proof_candidate_bindings",
    "build_g3_method_requirement_bindings",
    "build_g3_proof_carrying_analytics_bindings",
    "build_g3_proof_carrying_audit_surface",
    "build_g3_public_export_projection_ref_surface",
    "build_g3_s11_calibration_bindings",
    "build_g3_s11_predictive_posture_bindings",
    "build_g3_s11_prerequisite_bindings",
    "build_g3_search_engineering_quality_report",
    "build_g3_search_recall_freshness",
    "build_g3_semantic_spine_bindings",
    "build_g3_w12d_consumer_gate",
    "build_layer3_g3_bundle",
    "load_g3_l2_skg_dependency_artifacts",
    "produce_g3_deterministic_first_case_certificate",
    "resolve_g3_certificate_candidates",
    "search_ir_analytics_catalog",
    "validate_g3_adapter_conformance",
    "validate_layer3_g3_bundle",
]
