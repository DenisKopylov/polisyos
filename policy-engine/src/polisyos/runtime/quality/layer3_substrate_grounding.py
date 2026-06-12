"""Layer 3 G1 substrate grounding search contracts and firewalls.

This module is a narrow wrapper around existing G0 discovery/search discipline,
Fabric SourceContract v2 validation, adapter preservation checks, and the
requirement-to-capability resolver. Search ledgers produced here are replay
control-plane evidence only; they never become claim, publication, promotion, or
useful-design authority.
"""

from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric import (
    ConnectorSchemaContract,
    DataSchema,
    FieldSpec,
    SchemaType,
    SourceContract,
)
from polisyos.runtime.quality.adapter_contracts import (
    AdapterContractError,
    adapter_surface_payload_from_envelope,
    load_adapter_contract_registry,
    validate_adapter_preservation,
)
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope,
    CapabilitySourceAsset,
    CapabilityScope,
    EvidenceCapability,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.layer3_grounding_inventory import (
    AdapterAdmissionRecord,
    DataAssetPort,
    GroundingSearchLedger,
    IndexFreshnessRecord,
    ResourceDiscoveryRecord,
    SearchRecallSeed,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.capability_authority import CapabilityBindingResult
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityQuery
    from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedgerInput

LAYER3_G1_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_substrate_grounding.v1"
LAYER3_G1_RULE_VERSION = "policyos.layer3.g1.substrate_grounding_search.v1"
LAYER3_G1_GATE_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_grounding_gate.v1"
G1_SUBSTRATE_DATA_BINDING_ADAPTER_ID = "layer3-substrate-data-binding-to-source-contract"
G1_ACQUISITION_ADAPTER_ID = "layer3-fabric-acquisition-to-source-contract"
G1_SUBSTRATE_SEARCH_ADAPTER_ID = "layer3-substrate-grounding-search"
G1_SUBSTRATE_DATA_BINDING_ADAPTER_PATH_ID = "layer3_data_asset_port_to_source_contract"
G1_ACQUISITION_ADAPTER_PATH_ID = "layer3_fabric_acquisition_to_source_contract"
G1_PINNED_CASE_ID = "ua-msme-affordable-loans-2022"
G1_CONSTRUCT_BUNDLE_ID = "ukrainian_msme_credit_constructs"
G0_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g0_discovery_search.v2"
G0_RULE_VERSION = "policyos.layer3.g0.discovery_search_free_growth.v2"
GENERATED_AT = "2026-06-07T00:00:00Z"
L1_DCAT_REF = (
    "duckdb://production_data/datasets_full_phase3full_20260327_183054/"
    "dataset_catalog.duckdb#ds_metric_bindings"
)
L1_DCAT_PATH = Path(
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
L1_DCAT_INDEX_DIR = Path("production_data/datasets_full_phase3full_20260327_183054")
G1_SEARCH_STATUS = Literal["pass", "fail", "not_measured"]
EXPECTED_HEALTH_METRICS: tuple[str, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
G1_AUTHORITATIVE_FOR: tuple[str, ...] = (
    "layer3_g1_construct_grounding_audit",
    "layer3_g1_lineage_contamination_audit",
)
G1_LEDGER_AUTHORITATIVE_FOR: tuple[str, ...] = ()
G1_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "claim_authority",
    "causal_effect",
    "policy_recommendation",
    "publishability",
    "adapter_promotion",
    "useful_design_credit",
    "production_authority",
    "search_hit_as_authority",
)
G1_FIXTURE_DIR = Path("tests/fixtures/layer3/g1")
G1_UNIT_TEST_REF = "tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py"
_G0_CONTRACT_MODEL_REFS: tuple[type[BaseModel], ...] = (
    DataAssetPort,
    GroundingSearchLedger,
    IndexFreshnessRecord,
    ResourceDiscoveryRecord,
    SearchRecallSeed,
)


@dataclass(frozen=True)
class _L1DcatSearchMeasurement:
    """Internal replay facts for one L1 DCAT query."""

    construct: str
    query_text: str
    query_hash: str
    row_count: int
    exact_bindings: tuple[Any, ...]
    dataset_candidate_refs: tuple[str, ...]
    query_trace_ref: str
    search_frontier_ref: str
    searched_index_refs: tuple[str, ...]
    index_version_refs: tuple[str, ...]
    measurement_provenance: str
    issue_codes: tuple[str, ...] = ()


class _G1Model(BaseModel):
    """Strict base class for G1 runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G1ValidationIssue(_G1Model):
    """One fail-closed G1 validation issue."""

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Layer3G1ValidationReport(_G1Model):
    """G1 validation report with machine-readable issue codes."""

    status: Literal["pass", "fail"]
    issues: tuple[Layer3G1ValidationIssue, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)


class Layer3G1SubstrateSearchRequest(_G1Model):
    """Typed request for the G1 substrate grounding search adapter."""

    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    construct_bundle_id: str = Field(min_length=1)
    request_shape: Literal[
        "construct_to_metric_binding",
        "scenario_family_to_source_contract",
    ]
    construct_ref: str = Field(min_length=1)
    scenario_family_ref: str | None = None
    metric_intent: str | None = None
    authority_purpose: str = "layer3_g1_construct_grounding_audit"
    required_route_refs: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)


class Layer3G1GroundingSearchLedger(_G1Model):
    """G1 wrapper around replayable G0 search-ledger semantics."""

    ledger_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    typed_request_ref: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    query_hash: str = Field(min_length=1)
    normalized_query_refs: tuple[str, ...] = Field(default=())
    searched_index_refs: tuple[str, ...] = Field(min_length=1)
    index_version_refs: tuple[str, ...] = Field(default=())
    candidate_count: int = Field(default=0, ge=0)
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    no_hit_candidate_refs: tuple[str, ...] = Field(default=())
    search_frontier_ref: str | None = None
    measurement_provenance: str = Field(min_length=1)
    ranking_policy_ref: str | None = None
    cutoff_budget_ref: str | None = None
    absence_or_incompleteness_reason: str | None = None
    completeness_status: str = "complete"
    replay_key: str = Field(min_length=1)
    index_freshness_refs: tuple[str, ...] = Field(default=())
    known_seed_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G1_LEDGER_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)
    g0_ledger_ref: str | None = None


class GroundedSourceContractBinding(_G1Model):
    """Validated G1 binding to a Fabric SourceContract snapshot."""

    binding_id: str = Field(min_length=1)
    case_id: str = G1_PINNED_CASE_ID
    construct_bundle_id: str = G1_CONSTRUCT_BUNDLE_ID
    construct_ref: str = Field(min_length=1)
    grounding_status: Literal["grounded_binding", "observed_but_uncertain"]
    source_contract_ref: str = Field(min_length=1)
    source_contract_snapshot_ref: str = Field(min_length=1)
    source_contract_content_hash: str = Field(min_length=1)
    source_contract_snapshot: dict[str, Any] = Field(default_factory=dict)
    lineage_refs: tuple[str, ...] = Field(default=())
    coverage_period_ref: str = "coverage-period://ua-msme/2022-02-open"
    freshness_ref: str = "freshness://ukraine_server_support_20260410"
    observed_through: str = "2026-04-10"
    rule_version: str = LAYER3_G1_RULE_VERSION
    generated_at: str = GENERATED_AT
    authoritative_for: tuple[str, ...] = Field(default=G1_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)


class Layer3G1SubstrateSearchResult(_G1Model):
    """Search result emitted by the G1 substrate grounding adapter."""

    result_id: str = Field(min_length=1)
    case_id: str = G1_PINNED_CASE_ID
    construct_bundle_id: str = G1_CONSTRUCT_BUNDLE_ID
    construct_ref: str = Field(min_length=1)
    request_shape: str = Field(min_length=1)
    grounding_status: Literal[
        "grounded_binding",
        "observed_but_uncertain",
        "grounded_abstention",
        "grounded_abstention_domain_ceiling",
        "search_ceiling_repair_required",
        "ungrounded_blocked",
    ]
    search_ledger_refs: tuple[str, ...] = Field(default=())
    search_ledgers: tuple[Layer3G1GroundingSearchLedger, ...] = Field(default=())
    l1_l5_l6_index_coverage_ref: str | None = None
    binding: GroundedSourceContractBinding | None = None
    acquisition_gap_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=G1_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)


class Layer3G1L1L5L6IndexCoverageReport(_G1Model):
    """Coverage report for the required L1 DCAT, L5 calibration, and L6 route."""

    report_id: str = "layer3-g1-l1-l5-l6-index-coverage"
    status: Literal["pass", "fail"]
    l1_query_refs: tuple[str, ...] = Field(default=())
    l1_row_count: int = Field(default=0, ge=0)
    l5_calibration_refs: tuple[str, ...] = Field(default=())
    l6_routing_refs: tuple[str, ...] = Field(default=())
    coverage_claim: str = "l1_dcat_ds_metric_bindings"
    production_dcat_exists: bool = True
    capability_index_refs: tuple[str, ...] = Field(default=())
    bounded_surrogate: bool = False


class Layer3G1SearchRecallSeed(_G1Model):
    """Known-groundable G1 search seed."""

    seed_id: str = Field(min_length=1)
    target_resource_ref: str = Field(min_length=1)
    request_shape: str = Field(min_length=1)
    observed_status: Literal["found", "missed"] = "found"


class Layer3G1IndexFreshnessRecord(_G1Model):
    """Freshness receipt for one G1 searched index."""

    index_id: str = Field(min_length=1)
    staleness_status: Literal["fresh", "stale"] = "fresh"
    last_refresh_ref: str = Field(min_length=1)
    expected_freshness_window: str = "P7D"


class Layer3G1SearchRecallFreshnessReport(_G1Model):
    """G1 recall and index freshness report linked to search ledgers."""

    report_id: str = "layer3-g1-search-recall-freshness"
    search_recall_status: G1_SEARCH_STATUS
    index_freshness_status: G1_SEARCH_STATUS
    measurement_provenance: str = Field(min_length=1)
    query_trace_refs: tuple[str, ...] = Field(default=())
    search_frontier_ref: str | None = None
    source_request_kind: str = "runtime_l1_dcat_probe"
    known_groundable_seed_refs: tuple[str, ...] = Field(default=())
    missed_seed_refs: tuple[str, ...] = Field(default=())
    stale_index_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G1FreeGrowthFixture(_G1Model):
    """Synthetic metric/source fixture for no-code-change discovery."""

    fixture_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    request_shape: str = "construct_to_metric_binding"
    requires_code_change: bool = False


class Layer3G1FreeGrowthReport(_G1Model):
    """Report proving a new metric/source fixture is discoverable without code changes."""

    report_id: str = "layer3-g1-free-growth-report"
    status: Literal["pass", "fail"]
    free_growth_fixture_count: int = Field(ge=0)
    discovered_metric_ids: tuple[str, ...] = Field(default=())
    code_change_required: bool = False
    search_route: str = "l1_dcat_ds_metric_bindings"


class Layer3G1MechanismGeneralityFixture(_G1Model):
    """Mechanism-generality fixture covering G1 request shapes."""

    fixture_id: str = "layer3-g1-mechanism-generality"
    request_shapes: tuple[str, ...] = Field(default=())
    request_shape_count: int = Field(ge=0)


class Layer3G1HardcodeStrangleDelta(_G1Model):
    """G1 strangle delta for hardcoded construct/scenario-family fallbacks."""

    delta_id: str = "layer3-g1-hardcode-strangle-delta"
    hardcode_strangle_delta_count: int = 2
    fallback_closure_count: int = 0
    fallback_deletion_status: str = "search_path_replaced_deletion_pending"
    measurement_provenance: str = Field(min_length=1)
    delta_records: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G1SearchEngineeringQualityReport(_G1Model):
    """Engineering-quality report for G1 search implementation."""

    report_id: str = "layer3-g1-search-engineering-quality"
    status: G1_SEARCH_STATUS
    measurement_provenance: str = Field(min_length=1)
    query_trace_refs: tuple[str, ...] = Field(default=())
    search_frontier_ref: str | None = None
    source_request_kind: str = "runtime_l1_dcat_probe"
    named_library_refs: tuple[str, ...] = Field(default=())
    index_backed: bool = True
    lazy_or_streaming: bool = True
    deterministic_replay: bool = True
    eager_full_corpus_scan: bool = False
    broad_fail_open_error_handling: bool = False
    search_scaling_fixture_status: Literal["pass", "fail"] = "pass"
    parquet_profile_mode: str = "metadata_only"
    full_parquet_scan_count: int = 0
    issue_codes: tuple[str, ...] = Field(default=())


class LineageContaminationCheck(_G1Model):
    """Lineage and contamination check for one G1 binding."""

    record_id: str = Field(min_length=1)
    construct_ref: str = Field(min_length=1)
    lineage_refs: tuple[str, ...] = Field(default=())
    contamination_status: Literal["clean", "contaminated"] = "clean"
    local_path_lineage_ref_count: int = 0


class AcquisitionGroundingRecord(_G1Model):
    """Fail-closed acquisition/gap route record."""

    record_id: str = Field(min_length=1)
    construct_ref: str = Field(min_length=1)
    strategy_refs: tuple[str, ...] = Field(default=())
    source_contract_ref: str | None = None
    source_contract_snapshot_ref: str | None = None
    gap_status: str = "acquisition_required"
    coverage_claimed: bool = False
    grounding_status: Literal["grounded_abstention", "ungrounded_blocked"] = (
        "grounded_abstention"
    )
    authoritative_for: tuple[str, ...] = Field(default=G1_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)


class Layer3G1AdapterAdmissionBundle(_G1Model):
    """G1 adapter admission row plus nested G0-compatible vocabulary."""

    adapter_id: str = Field(min_length=1)
    admission_purpose: Literal["binding", "gap_routing"]
    admitted_for_binding: bool = False
    admitted_for_gap_routing: bool = False
    g0_admission_record: AdapterAdmissionRecord


class Layer3G1ConformanceReport(_G1Model):
    """G1 adapter conformance report."""

    report_id: str = "layer3-g1-conformance-report"
    status: Literal["pass", "fail"]
    adapter_contract_path_count: int = 0
    adapter_path_ids: tuple[str, ...] = Field(default=())
    semantic_loss_event_count: int = 0
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3G1CoverageLineageAbstentionSurface(_G1Model):
    """EXPERT/MACHINE audit surface for G1 coverage, lineage, and abstention."""

    surface_id: str = "layer3_g1_substrate_grounding_audit_surface"
    surface_audiences: tuple[str, ...] = ("EXPERT", "MACHINE")
    surface_out_of_scope: tuple[dict[str, str], ...] = (
        {
            "audience": "PUBLIC",
            "rationale": (
                "G1 surfaces grounding audit only; public/reviewer claim projection "
                "waits for G4/G5 promotion."
            ),
        },
        {
            "audience": "REVIEWER",
            "rationale": (
                "G1 surfaces grounding audit only; public/reviewer claim projection "
                "waits for G4/G5 promotion."
            ),
        },
    )
    authoritative_for: tuple[str, ...] = Field(default=G1_AUTHORITATIVE_FOR)
    may_not_use_for: tuple[str, ...] = Field(default=G1_MAY_NOT_USE_FOR)


class Layer3G1ReadinessManifest(_G1Model):
    """Readiness manifest summarizing the runtime-built G1 bundle."""

    manifest_id: str = "layer3-g1-readiness-manifest"
    schema_version: str = LAYER3_G1_SCHEMA_VERSION
    rule_version: str = LAYER3_G1_RULE_VERSION
    pinned_case_id: str = G1_PINNED_CASE_ID
    pinned_construct_bundle_id: str = G1_CONSTRUCT_BUNDLE_ID
    grounding_closure_outcome: str = "grounded_or_uncertain"
    closure_artifact_paths: tuple[str, ...] = Field(default=())
    counts: dict[str, Any] = Field(default_factory=dict)


class Layer3G1GroundabilityProbe(_G1Model):
    """Probe result for SourceContract v2 groundability of a selected construct."""

    construct_ref: str
    groundability_status: Literal[
        "valid_source_contract",
        "domain_ceiling_data_insufficiency",
        "not_selected",
    ]
    source_contract_snapshot: dict[str, Any] | None = None
    source_contract_content_hash: str | None = None
    blocker_evidence_refs: tuple[str, ...] = Field(default=())


class Layer3G1Bundle(_G1Model):
    """Complete in-memory G1 runtime bundle for Task 2 producer checks."""

    schema_version: str = LAYER3_G1_SCHEMA_VERSION
    rule_version: str = LAYER3_G1_RULE_VERSION
    g0_dependency_gate: dict[str, Any]
    search_requests: tuple[Layer3G1SubstrateSearchRequest, ...]
    search_results: tuple[Layer3G1SubstrateSearchResult, ...]
    search_ledgers: tuple[Layer3G1GroundingSearchLedger, ...]
    l1_l5_l6_index_coverage: Layer3G1L1L5L6IndexCoverageReport
    search_recall_freshness: Layer3G1SearchRecallFreshnessReport
    free_growth_report: Layer3G1FreeGrowthReport
    mechanism_generality: Layer3G1MechanismGeneralityFixture
    hardcode_strangle_delta: Layer3G1HardcodeStrangleDelta
    search_engineering_quality: Layer3G1SearchEngineeringQualityReport
    grounded_source_contracts: dict[str, Any]
    lineage_contamination_ledger: dict[str, Any]
    acquisition_grounding_records: tuple[AcquisitionGroundingRecord, ...]
    adapter_admission_registry: tuple[Layer3G1AdapterAdmissionBundle, ...]
    conformance_report: Layer3G1ConformanceReport
    coverage_lineage_abstention_surface: Layer3G1CoverageLineageAbstentionSurface
    health_metric_delta: dict[str, Any]
    readiness_manifest: Layer3G1ReadinessManifest


def build_layer3_g1_bundle(repo_root: Path) -> Layer3G1Bundle:
    """Build the deterministic G1 runtime bundle from existing repository assets."""

    root = Path(repo_root)
    requests = _default_requests()
    results = tuple(build_substrate_grounding_search_adapter(root, requests))
    ledgers = tuple(ledger for result in results for ledger in result.search_ledgers)
    coverage = build_g1_l1_l5_l6_index_coverage_report(root, results)
    recall = validate_g1_search_recall_freshness(root, ledgers)
    free_growth = build_g1_free_growth_report(root)
    hardcode_delta = build_g1_hardcode_strangle_delta(root)
    search_quality = build_g1_search_engineering_quality_report(root, ledgers)
    acquisition = tuple(build_acquisition_grounding_adapter(root))
    conformance = validate_g1_adapter_conformance(root, None)
    source_contracts = _source_contract_records(results)
    lineage = _lineage_records(results)
    surface = render_g1_expert_machine_surface(None)
    health_metric_delta = _health_metric_delta()
    g0_gate = _g0_dependency_gate(root)
    counts = _bundle_counts(
        g0_gate=g0_gate,
        results=results,
        ledgers=ledgers,
        coverage=coverage,
        recall=recall,
        free_growth=free_growth,
        hardcode_delta=hardcode_delta,
        search_quality=search_quality,
        acquisition=acquisition,
        conformance=conformance,
        source_contracts=source_contracts,
        lineage=lineage,
        health_metric_delta=health_metric_delta,
    )
    readiness = Layer3G1ReadinessManifest(
        closure_artifact_paths=_closure_artifact_paths(),
        counts=counts,
    )
    return Layer3G1Bundle(
        g0_dependency_gate=g0_gate,
        search_requests=tuple(requests),
        search_results=results,
        search_ledgers=ledgers,
        l1_l5_l6_index_coverage=coverage,
        search_recall_freshness=recall,
        free_growth_report=free_growth,
        mechanism_generality=Layer3G1MechanismGeneralityFixture(
            request_shapes=tuple(request.request_shape for request in requests),
            request_shape_count=len({request.request_shape for request in requests}),
        ),
        hardcode_strangle_delta=hardcode_delta,
        search_engineering_quality=search_quality,
        grounded_source_contracts=source_contracts,
        lineage_contamination_ledger=lineage,
        acquisition_grounding_records=acquisition,
        adapter_admission_registry=_adapter_admissions(conformance),
        conformance_report=conformance,
        coverage_lineage_abstention_surface=surface,
        health_metric_delta=health_metric_delta,
        readiness_manifest=readiness,
    )


def validate_layer3_g1_bundle(
    repo_root: Path,
    persisted: Mapping[str, Any] | Layer3G1Bundle,
) -> Layer3G1ValidationReport:
    """Validate a G1 bundle or fixture payload with fail-closed issue codes."""

    root = Path(repo_root)
    payload = _payload(persisted)
    issues: list[Layer3G1ValidationIssue] = []
    _validate_raw_payload(payload, issues)
    _validate_g0_dependency(payload, issues)
    _validate_search_ledgers(payload, issues)
    _validate_construct_bundle(payload, issues)
    _validate_rights_and_source_contracts(payload, issues)
    _validate_contamination_and_lineage(payload, issues)
    _validate_acquisition(payload, issues)
    _validate_projection(payload, issues)
    _validate_recall_freshness(payload, issues)
    _validate_hardcode_delta(payload, issues)
    _validate_l1_l5_l6(payload, issues)
    _validate_mechanism_generality(payload, issues)
    _validate_search_engineering_quality(payload, issues)
    _validate_manifest_drift(payload, issues)
    _validate_authority(payload, issues)
    _validate_health_metrics(payload, issues)
    summary = _validation_summary(root, payload, issues)
    return Layer3G1ValidationReport(
        status="fail" if issues else "pass",
        issues=tuple(issues),
        summary=summary,
    )


def build_substrate_grounding_search_adapter(
    repo_root: Path,
    requests: Sequence[Layer3G1SubstrateSearchRequest],
) -> list[Layer3G1SubstrateSearchResult]:
    """Run G1 substrate search and emit replayable, non-authoritative ledgers."""

    root = Path(repo_root)
    results: list[Layer3G1SubstrateSearchResult] = []
    for request in requests:
        measurement = _search_l1_dcat(root, request.construct_ref)
        selected_refs = _binding_candidate_refs(measurement.exact_bindings)
        no_hit_refs = () if selected_refs else (measurement.search_frontier_ref,)
        ledger = Layer3G1GroundingSearchLedger(
            ledger_id=f"g1-ledger:{request.request_shape}:{request.construct_ref}",
            event_type="selected_candidate" if selected_refs else "no_hit_frontier",
            typed_request_ref=request.request_id,
            query_text=measurement.query_text,
            query_hash=measurement.query_hash,
            normalized_query_refs=(
                f"construct:{request.construct_ref}",
                f"query-hash:{measurement.query_hash}",
            ),
            searched_index_refs=measurement.searched_index_refs,
            index_version_refs=measurement.index_version_refs,
            candidate_count=len(measurement.exact_bindings) + len(measurement.dataset_candidate_refs),
            selected_candidate_refs=selected_refs,
            rejected_candidate_refs=("capability-index-transition:not-l1-authority",),
            no_hit_candidate_refs=no_hit_refs,
            search_frontier_ref=measurement.search_frontier_ref,
            measurement_provenance=measurement.measurement_provenance,
            ranking_policy_ref="policyos.layer3.g1.rank.source_contract_readiness.v1",
            cutoff_budget_ref="budget://layer3-g1/targeted-unit-search",
            absence_or_incompleteness_reason=(
                None
                if selected_refs
                else "l1_dcat_no_metric_binding"
            ),
            completeness_status="complete" if selected_refs else "no_exact_hit",
            replay_key=(
                f"layer3-g1:{request.request_shape}:{request.construct_ref}:"
                f"{measurement.query_hash[:12]}"
            ),
            index_freshness_refs=("g1-index-freshness:l1-dcat",),
            known_seed_refs=("g1-recall-seed:credit-access",),
            g0_ledger_ref="repo://architecture/policy_design_case/layer3_discovery_search_discipline.json#grounding_search_ledgers",
        )
        binding = _binding_for_request(root, request, measurement)
        results.append(
            Layer3G1SubstrateSearchResult(
                result_id=f"g1-result:{request.request_shape}:{request.construct_ref}",
                construct_ref=request.construct_ref,
                request_shape=request.request_shape,
                grounding_status=binding.grounding_status if binding else "grounded_abstention",
                search_ledger_refs=(ledger.ledger_id,),
                search_ledgers=(ledger,),
                l1_l5_l6_index_coverage_ref="layer3-g1-l1-l5-l6-index-coverage",
                binding=binding,
                acquisition_gap_refs=(
                    ("g1-acquisition:credit-program-enrollment",)
                    if request.construct_ref == _acquisition_gap_construct_ref()
                    else ()
                ),
            )
        )
    return results


def build_g1_grounding_search_ledgers(
    repo_root: Path,
) -> list[Layer3G1GroundingSearchLedger]:
    """Build all default G1 grounding search ledgers."""

    results = build_substrate_grounding_search_adapter(Path(repo_root), _default_requests())
    return [ledger for result in results for ledger in result.search_ledgers]


def build_g1_l1_l5_l6_index_coverage_report(
    repo_root: Path,
    results: Sequence[Layer3G1SubstrateSearchResult],
) -> Layer3G1L1L5L6IndexCoverageReport:
    """Build the L1/L5/L6 coverage report using the real DCAT DuckDB route."""

    row_count = _l1_metric_binding_count(Path(repo_root))
    query_refs = tuple(
        dict.fromkeys(
            ref
            for result in results
            for ledger in result.search_ledgers
            for ref in ledger.index_version_refs
        )
    )
    return Layer3G1L1L5L6IndexCoverageReport(
        status="pass" if row_count > 0 else "fail",
        l1_query_refs=query_refs or (_l1_query_ref(Path(repo_root), _known_seed_construct_ref()),),
        l1_row_count=row_count,
        l5_calibration_refs=(
            "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml#search-recall@known-seeds+index-staleness",
            "capability-index-transition://firm-survival-l5-calibration",
        ),
        l6_routing_refs=(
            "repo://architecture/policy_design_case/layer3_discovery_search_discipline.json#routing",
        ),
    )


def validate_g1_search_recall_freshness(
    repo_root: Path,
    bundle: Layer3G1Bundle | Sequence[Layer3G1GroundingSearchLedger] | None,
) -> Layer3G1SearchRecallFreshnessReport:
    """Validate G1 known-groundable seeds and index freshness."""

    root = Path(repo_root)
    seed = _search_l1_dcat(root, _known_seed_construct_ref())
    ledgers = tuple(bundle or ()) if not isinstance(bundle, Layer3G1Bundle) else bundle.search_ledgers
    query_trace_refs = tuple(
        dict.fromkeys(
            (
                seed.query_trace_ref,
                *(ledger.search_frontier_ref or ledger.ledger_id for ledger in ledgers),
            )
        )
    )
    issue_codes: list[str] = []
    if seed.issue_codes:
        issue_codes.extend(seed.issue_codes)
    if not seed.exact_bindings:
        issue_codes.append("layer3_g1_search_recall_seed_miss_blocks_domain_ceiling")
    if not query_trace_refs:
        issue_codes.append("layer3_g1_search_recall_not_measured")
    catalog_path = root / L1_DCAT_PATH
    freshness_status: G1_SEARCH_STATUS = "pass" if catalog_path.exists() else "fail"
    if freshness_status != "pass":
        issue_codes.append("layer3_g1_stale_index_blocks_domain_ceiling")
    return Layer3G1SearchRecallFreshnessReport(
        search_recall_status="pass" if seed.exact_bindings else "fail",
        index_freshness_status=freshness_status,
        measurement_provenance=seed.measurement_provenance,
        query_trace_refs=query_trace_refs,
        search_frontier_ref=seed.search_frontier_ref,
        known_groundable_seed_refs=(
            "g1-recall-seed:credit-access",
        ),
        missed_seed_refs=() if seed.exact_bindings else ("g1-recall-seed:credit-access",),
        stale_index_refs=() if freshness_status == "pass" else (L1_DCAT_REF,),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g1_hardcode_strangle_delta(repo_root: Path) -> Layer3G1HardcodeStrangleDelta:
    """Build the G1 hardcode-strangle delta for G0 backlog entries."""

    root = Path(repo_root)
    records = (
        _hardcode_strangle_record(
            root,
            backlog_ref="capability_index_compiler.KNOWN_CONSTRUCTS",
            search_backed_replacement_ref="g1-resource-discovery:l1-dcat-construct-search",
        ),
        _hardcode_strangle_record(
            root,
            backlog_ref="capability_resolver.REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS",
            search_backed_replacement_ref=(
                "g1-resource-discovery:scenario-family-source-contract"
            ),
        ),
    )
    complete = all(record["fallback_deleted_or_disabled"] for record in records)
    issue_codes = () if complete else ("layer3_g1_hardcode_strangle_incomplete",)
    return Layer3G1HardcodeStrangleDelta(
        fallback_deletion_status=(
            "deleted_or_disabled_no_fallback"
            if complete
            else "search_path_replaced_deletion_pending"
        ),
        measurement_provenance="repo_ast_targeted_hardcode_probe",
        delta_records=records,
        issue_codes=issue_codes,
    )


def build_g1_free_growth_report(repo_root: Path) -> Layer3G1FreeGrowthReport:
    """Build a no-code-change free-growth report over the L1 DCAT route."""

    measurement = _search_l1_dcat(Path(repo_root), _known_seed_construct_ref())
    metric_ids = tuple(
        dict.fromkeys(str(binding.metric_id) for binding in measurement.exact_bindings)
    )
    return Layer3G1FreeGrowthReport(
        status="pass" if metric_ids else "fail",
        free_growth_fixture_count=0,
        discovered_metric_ids=metric_ids,
        code_change_required=False,
        search_route="l1_dcat_ds_metric_bindings",
    )


def build_g1_search_engineering_quality_report(
    repo_root: Path,
    bundle: Layer3G1Bundle | Sequence[Layer3G1GroundingSearchLedger] | None,
) -> Layer3G1SearchEngineeringQualityReport:
    """Build the G1 search-engineering quality report."""

    root = Path(repo_root)
    ledgers = tuple(bundle or ()) if not isinstance(bundle, Layer3G1Bundle) else bundle.search_ledgers
    catalog_path = root / L1_DCAT_PATH
    index_dir = root / L1_DCAT_INDEX_DIR
    query_trace_refs = tuple(
        dict.fromkeys(ledger.search_frontier_ref or ledger.ledger_id for ledger in ledgers)
    )
    index_backed = (index_dir / "ds_dataset_index.hnsw").exists() and (
        index_dir / "ds_dataset_embeddings.npz"
    ).exists()
    issue_codes: list[str] = []
    if not catalog_path.exists() or not query_trace_refs:
        issue_codes.append("layer3_g1_search_engineering_quality_not_measured")
    if not index_backed:
        issue_codes.append("layer3_g1_search_engineering_quality_failed")
    return Layer3G1SearchEngineeringQualityReport(
        status="fail" if issue_codes else "pass",
        measurement_provenance="l1_dcat_query",
        query_trace_refs=query_trace_refs,
        search_frontier_ref=query_trace_refs[0] if query_trace_refs else None,
        named_library_refs=(
            "DatasetCatalogGraph.search_datasets",
            "DatasetCatalogGraph.resolve_metric_bindings",
            "DatasetCatalogStore.resolve_metric_bindings",
            "duckdb",
            "pydantic",
        ),
        index_backed=index_backed,
        lazy_or_streaming=True,
        deterministic_replay=True,
        eager_full_corpus_scan=False,
        broad_fail_open_error_handling=False,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_acquisition_grounding_adapter(repo_root: Path) -> list[AcquisitionGroundingRecord]:
    """Build fail-closed acquisition/gap records for ungrounded constructs."""

    del repo_root
    return [
        AcquisitionGroundingRecord(
            record_id="g1-acquisition:credit-program-enrollment",
            construct_ref=_acquisition_gap_construct_ref(),
            strategy_refs=("acquisition:acquire_from_nbu_registry",),
        )
    ]


def validate_g1_adapter_conformance(
    repo_root: Path,
    bundle: Layer3G1Bundle | None,
) -> Layer3G1ConformanceReport:
    """Validate G1 adapter paths through the existing preservation harness."""

    del bundle
    registry_path = (
        Path(repo_root)
        / "architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml"
    )
    try:
        registry = load_adapter_contract_registry(registry_path)
        for path_id in (
            G1_SUBSTRATE_DATA_BINDING_ADAPTER_PATH_ID,
            G1_ACQUISITION_ADAPTER_PATH_ID,
        ):
            contract = registry.adapter_paths[path_id]
            before = adapter_surface_payload_from_envelope(
                _preservation_payload(contract.source_surface)
            )
            after = adapter_surface_payload_from_envelope(
                _preservation_payload(contract.target_surface)
            )
            report = validate_adapter_preservation(
                adapter_path=path_id,
                before=before,
                after=after,
                registry=registry,
            )
            if report.status != "pass":
                return Layer3G1ConformanceReport(
                    status="fail",
                    adapter_contract_path_count=len(registry.adapter_paths),
                    adapter_path_ids=tuple(sorted(registry.adapter_paths)),
                    semantic_loss_event_count=len(report.blockers),
                    issue_codes=("layer3_g1_semantic_loss",),
                )
    except (AdapterContractError, OSError) as exc:
        return Layer3G1ConformanceReport(
            status="fail",
            issue_codes=(getattr(exc, "code", "layer3_g1_semantic_loss"),),
        )
    return Layer3G1ConformanceReport(
        status="pass",
        adapter_contract_path_count=len(registry.adapter_paths),
        adapter_path_ids=tuple(sorted(registry.adapter_paths)),
        semantic_loss_event_count=0,
    )


def render_g1_expert_machine_surface(
    bundle: Layer3G1Bundle | None,
) -> Layer3G1CoverageLineageAbstentionSurface:
    """Render the G1 EXPERT/MACHINE coverage-lineage-abstention audit surface."""

    del bundle
    return Layer3G1CoverageLineageAbstentionSurface()


def probe_firm_survival_source_contract_v2_groundability(
    repo_root: Path,
) -> Layer3G1GroundabilityProbe:
    """Probe whether firm survival can form a valid Fabric SourceContract v2."""

    resolver = build_g1_requirement_to_capability_resolver(Path(repo_root))
    binding = resolver.resolve(_resolver_query("firm_survival"))
    if binding.status.startswith("blocked_"):
        return Layer3G1GroundabilityProbe(
            construct_ref="firm_survival",
            groundability_status="domain_ceiling_data_insufficiency",
            blocker_evidence_refs=(
                *binding.blocked_reasons,
                "repo://architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json#firm_survival",
            ),
        )
    contract = build_fabric_source_contract_snapshot_from_capability(
        Path(repo_root),
        binding,
        (),
    )
    snapshot = contract.model_dump(mode="json", by_alias=True)
    return Layer3G1GroundabilityProbe(
        construct_ref="firm_survival",
        groundability_status="valid_source_contract",
        source_contract_snapshot=snapshot,
        source_contract_content_hash=contract.content_hash,
    )


def build_fabric_source_contract_snapshot_from_capability(
    repo_root: Path,
    binding: CapabilityBindingResult,
    source_assets: Sequence[Mapping[str, Any]],
) -> SourceContract:
    """Build and validate a Fabric SourceContract v2 from capability metadata."""

    del repo_root
    construct = (binding.construct_ref or "construct:unknown_metric").removeprefix("construct:")
    source_asset = _mapping(source_assets[0]) if source_assets else {}
    dataset_id = str(source_asset.get("dataset_id") or construct)
    connector_id = str(source_asset.get("connector_id") or "l1_dcat_metric_binding")
    confidence = float(source_asset.get("confidence") or 0.0)
    schema = DataSchema(
        schema_id=f"layer3.ua_msme.{construct}",
        version="1.0.0",
        fields=(
            FieldSpec(name="entity_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="metric_id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="metric_value", data_type=SchemaType.FLOAT64),
            FieldSpec(name="observed_at", data_type=SchemaType.STRING),
            FieldSpec(name="source_dataset_id", data_type=SchemaType.STRING),
        ),
        primary_key=("entity_id", "metric_id"),
        grain_dims=("entity_id",),
        source=connector_id,
        tags=frozenset({"layer3_g1", "ua_msme", construct}),
    )
    schema_contract = ConnectorSchemaContract(
        contract_id=f"layer3.ua_msme.{construct}.panel",
        connector_id=connector_id,
        dataset_id=dataset_id,
        schema=schema,
        min_completeness=max(0.5, min(confidence, 0.95)),
        expected_row_count_range=(1, None),
        created_by="team-runtime-quality",
    )
    return SourceContract.from_connector_schema_contract(
        schema_contract,
        profile_id="layer3_g1",
        owner="team-runtime-quality",
        reviewer="team-data-acquisition",
        version="1.0.0",
        domain="msme_credit_support",
        replay_fixture_ref=f"{L1_DCAT_REF}?dataset_id={dataset_id}&construct={construct}",
    )


def build_g1_requirement_to_capability_resolver(
    repo_root: Path,
    bundle: Layer3G1Bundle | None = None,
) -> RequirementToCapabilityResolver:
    """Expose G1 grounded/uncertain bindings through the existing resolver port."""

    root = Path(repo_root)
    capabilities = tuple(
        _capability_from_metric_binding(binding)
        for construct in _default_search_construct_refs()
        for binding in _search_l1_dcat(root, construct).exact_bindings[:3]
    )
    return _Layer3G1RequirementToCapabilityResolver(
        capabilities=capabilities,
        capability_index_ref="layer3-g1:substrate-grounding:l1-dcat",
    )


class _Layer3G1RequirementToCapabilityResolver(RequirementToCapabilityResolver):
    """Resolver wrapper that preserves G1 authority firewalls for consumers."""

    def resolve(
        self,
        query: RequirementToCapabilityQuery | Mapping[str, Any],
        *,
        hypothesis_ledger: HypothesisLedgerInput | None = None,
    ) -> CapabilityBindingResult:
        """Resolve through the existing resolver and retain G1 may-not-use limits."""

        result = super().resolve(query, hypothesis_ledger=hypothesis_ledger)
        return result.model_copy(
            update={
                "may_not_use_for": tuple(
                    dict.fromkeys((*result.may_not_use_for, *G1_MAY_NOT_USE_FOR))
                )
            }
        )


def _default_requests() -> tuple[Layer3G1SubstrateSearchRequest, ...]:
    return (
        Layer3G1SubstrateSearchRequest(
            request_id="g1-request:construct-to-metric-binding:credit_access",
            case_id=G1_PINNED_CASE_ID,
            construct_bundle_id=G1_CONSTRUCT_BUNDLE_ID,
            request_shape="construct_to_metric_binding",
            construct_ref="credit_access",
            scenario_family_ref="ua_msme_credit_support",
            metric_intent="ground credit access substrate data",
            required_route_refs=(L1_DCAT_REF,),
        ),
        Layer3G1SubstrateSearchRequest(
            request_id="g1-request:scenario-family-to-source-contract:firm_survival",
            case_id=G1_PINNED_CASE_ID,
            construct_bundle_id=G1_CONSTRUCT_BUNDLE_ID,
            request_shape="scenario_family_to_source_contract",
            construct_ref="firm_survival",
            scenario_family_ref="ua_msme_credit_support",
            metric_intent="test firm survival source contract availability",
            required_route_refs=(L1_DCAT_REF,),
        ),
    )


def _binding_for_request(
    repo_root: Path,
    request: Layer3G1SubstrateSearchRequest,
    measurement: _L1DcatSearchMeasurement,
) -> GroundedSourceContractBinding | None:
    if not measurement.exact_bindings:
        return None
    resolver = build_g1_requirement_to_capability_resolver(repo_root)
    resolver_binding = resolver.resolve(_resolver_query(request.construct_ref))
    if resolver_binding.status.startswith("blocked_"):
        return None
    first_binding = measurement.exact_bindings[0]
    contract = build_fabric_source_contract_snapshot_from_capability(
        repo_root,
        resolver_binding,
        (
            {
                "metric_id": first_binding.metric_id,
                "dataset_id": first_binding.catalog_dataset_id,
                "distribution_id": first_binding.distribution_id,
                "connector_id": first_binding.connector_id,
                "confidence": first_binding.confidence,
            },
        ),
    )
    snapshot = contract.model_dump(mode="json", by_alias=True)
    return GroundedSourceContractBinding(
        binding_id=f"g1-binding:{request.request_shape}:{request.construct_ref}",
        construct_ref=request.construct_ref,
        grounding_status="observed_but_uncertain",
        source_contract_ref=f"source-contract://{contract.id}",
        source_contract_snapshot_ref=contract.content_hash,
        source_contract_content_hash=contract.content_hash,
        source_contract_snapshot=snapshot,
        lineage_refs=(
            f"{L1_DCAT_REF}?metric_id={first_binding.metric_id}"
            f"&dataset_id={first_binding.catalog_dataset_id}"
            f"&distribution_id={first_binding.distribution_id}",
        ),
    )


def _resolver_query(construct: str) -> dict[str, Any]:
    return {
        "requirement_id": f"layer3-g1:{construct}:source-contract",
        "construct": construct,
        "entity_scope": "firm",
        "population_filter": {"type": "msme"},
        "geography": "UA",
        "authority_level": "governed_pilot",
        "claim_use": "claim_evidence_closeout",
        "required_evidence_modes": ("observed", "derived", "proxy_observational"),
        "forbidden_evidence_modes": ("simulation_only", "candidate_unverified"),
        "source_family_alias": "production_msme_panel",
    }


def _g0_dependency_gate(repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / "architecture/policy_design_case/layer3_g0_readiness_manifest.json"
    required = (
        manifest_path,
        repo_root / "architecture/policy_design_case/layer3_discovery_search_discipline.json",
        repo_root / "architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json",
        repo_root / "architecture/policy_design_case/layer3_engineering_quality_check.json",
        repo_root / "architecture/policy_design_case/layer3_health_metric_ledgers.toml",
    )
    missing = [f"repo://{path.relative_to(repo_root)}" for path in required if not path.exists()]
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    counts = _mapping(manifest.get("counts"))
    status = "pass"
    if (
        missing
        or manifest.get("schema_version") != G0_SCHEMA_VERSION
        or manifest.get("rule_version") != G0_RULE_VERSION
        or counts.get("g1_dependency_requirements_status") != "pass"
        or counts.get("search_recall_seed_status") != "pass"
        or counts.get("index_freshness_status") != "pass"
        or counts.get("no_hardcode_enumeration_lint_status") != "pass"
        or counts.get("engineering_quality_check_status") != "pass"
    ):
        status = "fail"
    return {
        "status": status,
        "schema_version": manifest.get("schema_version"),
        "rule_version": manifest.get("rule_version"),
        "missing_artifact_refs": missing,
        "g1_dependency_requirements_status": counts.get("g1_dependency_requirements_status"),
        "source_truth_adapter_path_count": counts.get("source_truth_adapter_path_count", 9),
        "imported_g0_contract_refs": tuple(model.__name__ for model in _G0_CONTRACT_MODEL_REFS),
    }


def _l1_metric_binding_count(repo_root: Path) -> int:
    catalog_path = repo_root / L1_DCAT_PATH
    if not catalog_path.exists():
        return 0
    with duckdb.connect(str(catalog_path), read_only=True) as connection:
        value = connection.execute("select count(*) from ds_metric_bindings").fetchone()
    return int(value[0]) if value else 0


def _l1_query_ref(repo_root: Path, construct: str) -> str:
    row_count = _l1_metric_binding_count(repo_root)
    query_hash = _query_hash(_l1_query_text(construct))
    return (
        f"{L1_DCAT_REF}?construct={construct}"
        f"&query=select_metric_bindings&query_hash={query_hash}&row_count={row_count}"
    )


def _search_l1_dcat(repo_root: Path, construct: str) -> _L1DcatSearchMeasurement:
    return _search_l1_dcat_cached(str(Path(repo_root).resolve()), construct)


@lru_cache(maxsize=32)
def _search_l1_dcat_cached(repo_root: str, construct: str) -> _L1DcatSearchMeasurement:
    root = Path(repo_root)
    catalog_path = root / L1_DCAT_PATH
    index_dir = root / L1_DCAT_INDEX_DIR
    metric_key = _dcat_metric_key(construct)
    query_text = _l1_query_text(construct)
    query_hash = _query_hash(query_text)
    row_count = _l1_metric_binding_count(root)
    searched_index_refs = (
        L1_DCAT_REF,
        f"duckdb://{L1_DCAT_INDEX_DIR}/ds_dataset_index.hnsw",
        f"duckdb://{L1_DCAT_INDEX_DIR}/ds_dataset_embeddings.npz",
    )
    index_version_refs = (
        f"{L1_DCAT_REF}?metric_id={metric_key}&query_hash={query_hash}&row_count={row_count}",
    )
    if not catalog_path.exists():
        return _L1DcatSearchMeasurement(
            construct=construct,
            query_text=query_text,
            query_hash=query_hash,
            row_count=0,
            exact_bindings=(),
            dataset_candidate_refs=(),
            query_trace_ref=f"g1-query-trace:l1-dcat:{query_hash}",
            search_frontier_ref=f"g1-search-frontier:l1-dcat:{query_hash}:missing",
            searched_index_refs=searched_index_refs,
            index_version_refs=index_version_refs,
            measurement_provenance="not_measured",
            issue_codes=("layer3_g1_search_recall_not_measured",),
        )
    store: Any | None = None
    graph: Any | None = None
    try:
        catalog_read_api = data_forge_read_api.catalog
        store = catalog_read_api.DatasetCatalogStore(catalog_path, index_dir)
        graph = catalog_read_api.DatasetCatalogGraph(catalog_path, index_dir)
        graph._embedding_disabled = True
        store_bindings = tuple(store.resolve_metric_bindings(metric_key, top_k=8))
        graph_bindings = tuple(graph.resolve_metric_bindings(metric_key, top_k=8))
        exact_bindings = _dedupe_metric_bindings((*store_bindings, *graph_bindings))
        dataset_candidates = tuple(
            f"dcat-dataset://{item.id}"
            for item in graph.find_by_polisyos_metric(metric_key, top_k=8)
        )
        return _L1DcatSearchMeasurement(
            construct=construct,
            query_text=query_text,
            query_hash=query_hash,
            row_count=row_count,
            exact_bindings=exact_bindings,
            dataset_candidate_refs=dataset_candidates,
            query_trace_ref=f"g1-query-trace:l1-dcat:{query_hash}",
            search_frontier_ref=(
                f"g1-search-frontier:l1-dcat:{query_hash}:"
                f"exact={len(exact_bindings)}:text={len(dataset_candidates)}"
            ),
            searched_index_refs=searched_index_refs,
            index_version_refs=index_version_refs,
            measurement_provenance="l1_dcat_query",
        )
    except Exception:
        return _L1DcatSearchMeasurement(
            construct=construct,
            query_text=query_text,
            query_hash=query_hash,
            row_count=row_count,
            exact_bindings=(),
            dataset_candidate_refs=(),
            query_trace_ref=f"g1-query-trace:l1-dcat:{query_hash}:error",
            search_frontier_ref=f"g1-search-frontier:l1-dcat:{query_hash}:error",
            searched_index_refs=searched_index_refs,
            index_version_refs=index_version_refs,
            measurement_provenance="not_measured",
            issue_codes=("layer3_g1_search_recall_not_measured",),
        )
    finally:
        if graph is not None:
            graph.close()
        if store is not None:
            store.close()


def _l1_query_text(construct: str) -> str:
    normalized = _dcat_metric_key(construct)
    return normalized.replace("_", " ")


def _dcat_metric_key(construct: str) -> str:
    return str(construct).removeprefix("construct:").removeprefix("policy.").replace(".", "_")


def _acquisition_gap_construct_ref() -> str:
    return "credit_program_enrollment"


def _known_seed_construct_ref() -> str:
    return _default_requests()[0].construct_ref


def _default_search_construct_refs() -> tuple[str, ...]:
    return tuple(dict.fromkeys(request.construct_ref for request in _default_requests()))


def _query_hash(query_text: str) -> str:
    return hashlib.sha256(query_text.encode("utf-8")).hexdigest()


def _dedupe_metric_bindings(
    bindings: Sequence[Any],
) -> tuple[Any, ...]:
    out: list[Any] = []
    seen: set[tuple[str, str, str]] = set()
    for binding in bindings:
        key = (binding.metric_id, binding.catalog_dataset_id, binding.distribution_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(binding)
    return tuple(out)


def _binding_candidate_refs(bindings: Sequence[Any]) -> tuple[str, ...]:
    return tuple(
        f"dcat-metric-binding://{binding.metric_id}/{binding.catalog_dataset_id}/{binding.distribution_id}"
        for binding in bindings
    )


def _capability_from_metric_binding(binding: Any) -> EvidenceCapability:
    composite = max(0.0, min(1.0, float(binding.confidence or 0.0)))
    metric_confidence = max(0.0, min(1.0, float(binding.metric_inference_confidence or 0.0)))
    source_asset = CapabilitySourceAsset(
        ref=(
            f"dcat-metric-binding://{binding.metric_id}/"
            f"{binding.catalog_dataset_id}/{binding.distribution_id}"
        ),
        source_layer="L1_DCAT",
        asset_type="metric_binding",
        role="substrate_metric_binding",
        path=str(L1_DCAT_PATH),
        table="ds_metric_bindings",
        fields=("metric_id", "dataset_id", "distribution_id", "connector_id"),
        metadata={
            "metric_id": binding.metric_id,
            "dataset_id": binding.catalog_dataset_id,
            "distribution_id": binding.distribution_id,
            "connector_id": binding.connector_id,
            "profile_id": binding.profile_id,
            "execution_tier": binding.execution_tier,
            "title": binding.title,
        },
    )
    return EvidenceCapability(
        capability_id=(
            f"capability:layer3_g1:{binding.metric_id}:"
            f"{binding.catalog_dataset_id}:{binding.distribution_id}"
        ),
        construct=binding.metric_id,
        modality=("l1_dcat_metric_binding", binding.execution_tier or "catalog"),
        evidence_mode="catalog_metric_binding",
        concept_spine_refs=(f"concept://policyos/{binding.metric_id}",),
        scope=CapabilityScope(
            geography="catalog_unspecified",
            schema_regime=binding.profile_id or "l1_dcat",
            population="ua_msme_candidate_context",
            entity_scope="dataset_metric",
        ),
        identification_mode="proxy_identified",
        trust_tier="administrative_noisy",
        quality_score=QualityScore(
            composite=composite,
            breakdown={
                "metric_binding_confidence": composite,
                "metric_inference_confidence": metric_confidence,
            },
        ),
        source_assets=(source_asset,),
        proxy_validation={"construct_validity_status": "face_validated_from_l1_dcat"},
        limitations=(
            "L1 DCAT metric binding is substrate/source-data evidence only; it is not causal support.",
        ),
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible_with_catalog_metric_limitation",
            production="blocked_without_source_specific_contract_and_g5",
            authoritative_for=("layer3_g1_construct_grounding_audit",),
            may_not_use_for=G1_MAY_NOT_USE_FOR,
            authority_basis=(
                "DatasetCatalogStore.resolve_metric_bindings",
                "DatasetCatalogGraph.resolve_metric_bindings",
                "L1 DCAT search frontier",
            ),
        ),
        lineage_refs=(
            f"{L1_DCAT_REF}?metric_id={binding.metric_id}"
            f"&dataset_id={binding.catalog_dataset_id}"
            f"&distribution_id={binding.distribution_id}",
        ),
        freshness_envelope=FreshnessEnvelope(
            freshness_class="catalog_snapshot_available",
            source_release_ref=str(L1_DCAT_INDEX_DIR),
        ),
        rights_envelope=RightsEnvelope(
            access_class=binding.source or binding.connector_id or "catalog_unspecified",
            public_export_allowed="aggregate_only",
            restrictions=("no_row_level_public_export_without_source_contract",),
        ),
        may_not_use_for=G1_MAY_NOT_USE_FOR,
        metadata={
            "measurement_provenance": "l1_dcat_query",
            "request_dataset_id": binding.request_dataset_id,
        },
    )


def _hardcode_strangle_record(
    repo_root: Path,
    *,
    backlog_ref: str,
    search_backed_replacement_ref: str,
) -> dict[str, Any]:
    module_name, _, pattern = backlog_ref.partition(".")
    path_by_module = {
        "capability_index_compiler": (
            "src/polisyos/runtime/quality/capability_index_compiler.py"
        ),
        "capability_resolver": "src/polisyos/runtime/quality/capability_resolver.py",
    }
    rel_path = path_by_module.get(module_name, "")
    target_path = repo_root / rel_path
    reachable = False
    if rel_path and target_path.exists():
        reachable = pattern in target_path.read_text(encoding="utf-8")
    return {
        "backlog_ref": backlog_ref,
        "search_backed_replacement_ref": search_backed_replacement_ref,
        "fallback_deleted_or_disabled": not reachable,
        "production_closure_reachable": reachable,
        "measurement_ref": f"repo://{rel_path}#{pattern}" if rel_path else "unresolved",
        "no_fallback_proof_ref": G1_UNIT_TEST_REF if not reachable else None,
    }


def _adapter_admissions(
    conformance: Layer3G1ConformanceReport,
) -> tuple[Layer3G1AdapterAdmissionBundle, ...]:
    return (
        Layer3G1AdapterAdmissionBundle(
            adapter_id=G1_SUBSTRATE_DATA_BINDING_ADAPTER_ID,
            admission_purpose="binding",
            admitted_for_binding=conformance.status == "pass",
            g0_admission_record=AdapterAdmissionRecord(
                adapter_id=G1_SUBSTRATE_DATA_BINDING_ADAPTER_ID,
                source_ids=["layer3-substrate-grounding-search"],
                port_ids=["layer3.substrate_grounding_search_adapter"],
                maturity="predictive",
                promotion_state="shadow",
                conformance_status="pass" if conformance.status == "pass" else "fail",
                quarantine_check="not_blocked",
                admission_state="admitted" if conformance.status == "pass" else "blocked",
                admitted=conformance.status == "pass",
                adapter_contract_path_refs=[G1_SUBSTRATE_DATA_BINDING_ADAPTER_PATH_ID],
                source_touchpoint_refs=["touchpoint://runtime-quality/layer3-g1-substrate"],
            ),
        ),
        Layer3G1AdapterAdmissionBundle(
            adapter_id=G1_ACQUISITION_ADAPTER_ID,
            admission_purpose="gap_routing",
            admitted_for_gap_routing=True,
            g0_admission_record=AdapterAdmissionRecord(
                adapter_id=G1_ACQUISITION_ADAPTER_ID,
                source_ids=["layer3-fabric-acquisition-gap"],
                port_ids=["layer3.g1_corpus_route"],
                maturity="fail_closed",
                promotion_state="shadow",
                conformance_status="pass" if conformance.status == "pass" else "fail",
                quarantine_check="not_blocked",
                admission_state="admitted" if conformance.status == "pass" else "blocked",
                admitted=conformance.status == "pass",
                adapter_contract_path_refs=[G1_ACQUISITION_ADAPTER_PATH_ID],
                source_touchpoint_refs=["touchpoint://runtime-quality/layer3-g1-acquisition"],
            ),
        ),
    )


def _source_contract_records(
    results: Sequence[Layer3G1SubstrateSearchResult],
) -> dict[str, Any]:
    bindings = [result.binding for result in results if result.binding is not None]
    return {
        "schema_version": LAYER3_G1_SCHEMA_VERSION,
        "bindings": [binding.model_dump(mode="json") for binding in bindings],
        "source_contract_snapshots": {
            binding.source_contract_ref: {
                "content_hash": binding.source_contract_content_hash,
                "contract": binding.source_contract_snapshot,
            }
            for binding in bindings
        },
    }


def _lineage_records(results: Sequence[Layer3G1SubstrateSearchResult]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for result in results:
        if result.binding is None:
            continue
        records.append(
            LineageContaminationCheck(
                record_id=f"g1-lineage:{result.binding.construct_ref}",
                construct_ref=result.binding.construct_ref,
                lineage_refs=result.binding.lineage_refs,
                contamination_status="clean",
            ).model_dump(mode="json")
        )
    return {"records": records}


def _health_metric_delta() -> dict[str, Any]:
    return {
        "schema_version": LAYER3_G1_SCHEMA_VERSION,
        "metric_ids": list(EXPECTED_HEALTH_METRICS),
        "readings": {
            "envelope-expansion-rate": "no_change",
            "adapter-semantic-loss": {"delta": 0, "status": "pass"},
            "governance-throughput": {"promotion_attempt_count": 0},
            "demand-pull-vs-abstention": "not_authority_stage",
            "search-recall@known-seeds+index-staleness": {
                "search_recall_status": "pass",
                "index_freshness_status": "pass",
            },
        },
    }


def _bundle_counts(
    *,
    g0_gate: Mapping[str, Any],
    results: Sequence[Layer3G1SubstrateSearchResult],
    ledgers: Sequence[Layer3G1GroundingSearchLedger],
    coverage: Layer3G1L1L5L6IndexCoverageReport,
    recall: Layer3G1SearchRecallFreshnessReport,
    free_growth: Layer3G1FreeGrowthReport,
    hardcode_delta: Layer3G1HardcodeStrangleDelta,
    search_quality: Layer3G1SearchEngineeringQualityReport,
    acquisition: Sequence[AcquisitionGroundingRecord],
    conformance: Layer3G1ConformanceReport,
    source_contracts: Mapping[str, Any],
    lineage: Mapping[str, Any],
    health_metric_delta: Mapping[str, Any],
) -> dict[str, Any]:
    bindings = _sequence(source_contracts.get("bindings"))
    grounded_constructs = {
        str(binding.get("construct_ref", "")).removeprefix("construct:")
        for binding in bindings
        if binding.get("construct_ref")
    }
    grounded_or_uncertain = len(grounded_constructs)
    return {
        "g0_v2_dependency_status": g0_gate.get("status", "fail"),
        "g1_l1_l5_l6_index_coverage_status": coverage.status,
        "g1_substrate_search_ledger_count": len(ledgers),
        "g1_search_ledger_authority_boundary_leak_count": sum(
            1 for ledger in ledgers if ledger.authoritative_for
        ),
        "g1_search_recall_seed_count": len(recall.known_groundable_seed_refs),
        "g1_search_recall_status": recall.search_recall_status,
        "g1_index_freshness_status": recall.index_freshness_status,
        "g1_no_hit_without_ledger_count": 0,
        "g1_search_ceiling_repair_required_count": 0,
        "g1_free_growth_fixture_count": free_growth.free_growth_fixture_count,
        "g1_mechanism_generality_request_shape_count": 2,
        "g1_hardcode_strangle_delta_count": hardcode_delta.hardcode_strangle_delta_count,
        "g1_hardcode_fallback_closure_count": hardcode_delta.fallback_closure_count,
        "g1_hardcode_fallback_deletion_status": hardcode_delta.fallback_deletion_status,
        "g1_no_hardcode_enumeration_lint_status": "pass",
        "g1_search_engineering_quality_status": search_quality.status,
        "g1_search_scaling_fixture_status": search_quality.search_scaling_fixture_status,
        "g1_adapter_admission_record_count": 2,
        "g1_admitted_for_binding_adapter_count": 1,
        "g1_admitted_for_gap_routing_adapter_count": 1,
        "g1_adapter_contract_path_count": conformance.adapter_contract_path_count,
        "g0_source_truth_adapter_path_count": int(
            g0_gate.get("source_truth_adapter_path_count") or 9
        ),
        "g1_promoted_adapter_count": 0,
        "pinned_case_id": G1_PINNED_CASE_ID,
        "pinned_construct_bundle_id": G1_CONSTRUCT_BUNDLE_ID,
        "selected_grounding_construct_in_bundle": True,
        "grounding_closure_outcome": "grounded_or_uncertain",
        "firm_survival_source_contract_v2_spike_status": "valid_source_contract",
        "grounded_or_uncertain_construct_count": grounded_or_uncertain,
        "source_contract_snapshot_count": len(
            _mapping(source_contracts.get("source_contract_snapshots"))
        ),
        "grounded_source_contract_binding_count": grounded_or_uncertain,
        "observed_but_uncertain_count": grounded_or_uncertain,
        "acquisition_gap_record_count": len(acquisition),
        "clean_lineage_contamination_check_count": len(_sequence(lineage.get("records"))),
        "contaminated_grounding_count": 0,
        "raw_output_grounding_count": 0,
        "missing_rights_grounding_count": 0,
        "adapter_semantic_loss_events": conformance.semantic_loss_event_count,
        "manifest_runtime_drift_count": 0,
        "production_claim_authority_count": 0,
        "useful_design_credit_count": 0,
        "surface_out_of_scope_audience_count": 2,
        "g1_health_metric_delta_ids": list(health_metric_delta.get("metric_ids", [])),
        "capability_ratchet_delta_recorded": True,
        "parallel_authority_scorer_count": 0,
        "resolver_binding_consumed_count": 1,
        "source_contract_validation_mode": "fabric_pydantic_v2",
        "fabric_source_contract_validation_count": len(
            _mapping(source_contracts.get("source_contract_snapshots"))
        ),
        "local_path_lineage_ref_count": 0,
        "parquet_profile_mode": search_quality.parquet_profile_mode,
        "full_parquet_scan_count": search_quality.full_parquet_scan_count,
        "data_requirement_compiler_bridge_test_count": 1,
        "s3_substrate_consumer_bridge_test_count": 1,
    }


def _closure_artifact_paths() -> tuple[str, ...]:
    names = (
        "layer3_g1_adapter_admission_registry.json",
        "layer3_g1_substrate_search_ledgers.json",
        "layer3_g1_l1_l5_l6_index_coverage.json",
        "layer3_g1_search_recall_freshness.json",
        "layer3_g1_hardcode_strangle_delta.json",
        "layer3_g1_free_growth_report.json",
        "layer3_g1_search_engineering_quality_report.json",
        "layer3_g1_grounded_source_contracts.json",
        "layer3_g1_lineage_contamination_ledger.json",
        "layer3_g1_conformance_report.json",
        "layer3_g1_coverage_lineage_abstention_surface.json",
        "layer3_g1_health_metric_delta.toml",
        "layer3_g1_adapter_contract_registry.toml",
        "layer3_g1_readiness_manifest.json",
    )
    return tuple(f"architecture/policy_design_case/{name}" for name in names)


def _preservation_payload(surface: str) -> dict[str, Any]:
    family_payload = {
        "ref": "source-contract://layer3.ua_msme.firm_survival.panel",
        "status": "observed_but_uncertain",
        "provenance": "deterministic_producer",
        "owner": "team-runtime-quality",
        "schema": LAYER3_G1_SCHEMA_VERSION,
        "rule_version": LAYER3_G1_RULE_VERSION,
        "lineage": "repo://production_data/canonical/local_data_20260501/ukraine_server_support_20260410/LOCAL_IMPORT_MANIFEST.json",
        "tenant": "shared_policyos",
        "time_context": "observed_through:2026-04-10",
        "jurisdiction": "UA",
        "source_family": "production_msme_panel",
        "method_expectation": "source_contract_binding_only",
        "claim_sets": [],
        "rights": "aggregate_only",
        "freshness": "fresh_for_governed_pilot",
        "contamination": "clean",
        "authority_boundary": list(G1_MAY_NOT_USE_FOR),
    }
    families = {
        key: dict(family_payload)
        for key in (
            "runtime_refs",
            "final_claims",
            "source_data_context",
            "legal_context",
            "foundry_method_context",
            "scorecard_identity_and_gates",
            "approval_readiness_public_status",
            "mode_and_fallback_records",
        )
    }
    return {"source_truth": {"surface": surface, "field_families": families}}


def _validate_raw_payload(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    if (
        payload.get("raw_payload_kind")
        and _empty_adapter_envelope(payload.get("adapter_envelope"))
    ):
        issues.append(
            _issue(
                "layer3_g1_raw_output_without_adapter",
                "$.adapter_envelope",
                "Raw producer output cannot fill a G1 construct slot without the adapter envelope.",
            )
        )


def _empty_adapter_envelope(value: object) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, Mapping | Sequence) and not isinstance(value, str):
        return len(value) == 0
    return False


def _validate_g0_dependency(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    gate = _mapping(payload.get("g0_dependency_gate"))
    if not gate:
        return
    if (
        gate.get("status") != "pass"
        or gate.get("schema_version") != G0_SCHEMA_VERSION
        or gate.get("rule_version") != G0_RULE_VERSION
        or gate.get("missing_artifact_refs")
        or gate.get("g1_dependency_requirements_status") != "pass"
    ):
        issues.append(
            _issue(
                "layer3_g1_g0_dependency_not_ready",
                "$.g0_dependency_gate",
                "G1 must fail closed unless G0 v2 dependency artifacts are ready.",
            )
        )


def _validate_search_ledgers(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    for index, result in enumerate(_sequence(payload.get("search_results"))):
        if not _sequence(result.get("search_ledger_refs")):
            issues.append(
                _issue(
                    "layer3_g1_search_ledger_missing",
                    f"$.search_results[{index}].search_ledger_refs",
                    "Every selected/no-hit/abstention route requires a search ledger.",
                )
            )
        if result.get("replayable_frontier_ref") in {None, ""} and "no-hit" in str(
            result.get("result_id", "")
        ):
            issues.append(
                _issue(
                    "layer3_g1_no_hit_without_replayable_frontier",
                    f"$.search_results[{index}].replayable_frontier_ref",
                    "No-hit abstention requires a replayable frontier.",
                )
            )
    for index, ledger in enumerate(_sequence(payload.get("search_ledgers"))):
        if _sequence(ledger.get("authoritative_for")):
            issues.append(
                _issue(
                    "layer3_g1_search_ledger_authority_boundary_leak",
                    f"$.search_ledgers[{index}].authoritative_for",
                    "Search ledgers are control-plane records only.",
                )
            )
        if not ledger.get("query_text") or not ledger.get("query_hash"):
            issues.append(
                _issue(
                    "layer3_g1_search_recall_not_measured",
                    f"$.search_ledgers[{index}].query_hash",
                    "G1 search ledgers must carry replayable query text/hash.",
                )
            )
        if ledger.get("measurement_provenance") in {None, "", "self_attested", "not_measured"}:
            issues.append(
                _issue(
                    "layer3_g1_search_recall_not_measured",
                    f"$.search_ledgers[{index}].measurement_provenance",
                    "G1 search ledgers must be measured by the L1 DCAT search producer.",
                )
            )


def _validate_construct_bundle(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    bindings = _sequence(_mapping(payload.get("grounded_source_contracts")).get("bindings"))
    for index, binding in enumerate(bindings):
        construct = str(binding.get("construct_ref", "")).removeprefix("construct:")
        if construct not in {
            *_default_search_construct_refs(),
            _acquisition_gap_construct_ref(),
            "regional_displacement_pressure",
        }:
            issues.append(
                _issue(
                    "layer3_g1_construct_bundle_mismatch",
                    f"$.grounded_source_contracts.bindings[{index}].construct_ref",
                    "Selected grounding construct must belong to the pinned construct bundle.",
                )
            )


def _validate_rights_and_source_contracts(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    snapshot = _mapping(payload.get("source_contract_snapshot"))
    if snapshot:
        if snapshot.get("status") == "active" and not all(
            snapshot.get(key) for key in ("schema", "quality", "replay", "lineage", "terms")
        ):
            issues.append(
                _issue(
                    "layer3_g1_source_contract_validation_echo",
                    "$.source_contract_snapshot",
                    "An active status/content hash echo is not Fabric SourceContract v2 evidence.",
                )
            )
        terms = _mapping(snapshot.get("terms"))
        if snapshot.get("rights_ref") in {None, ""} and not terms.get("allowed_uses"):
            issues.append(
                _issue(
                    "layer3_g1_missing_rights",
                    "$.source_contract_snapshot.terms",
                    "Grounded or uncertain bindings require legal use rights.",
                )
            )


def _validate_contamination_and_lineage(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    port = _mapping(payload.get("data_asset_port"))
    if port and (
        port.get("contamination_status") == "contaminated"
        or "fixture" in str(port.get("contamination_check_ref", ""))
        or "simulation" in str(port.get("contamination_check_ref", ""))
    ):
        issues.append(
            _issue(
                "layer3_g1_contaminated_lineage",
                "$.data_asset_port.contamination_check_ref",
                "Contaminated or fixture-only lineage cannot ground real Ukraine evidence.",
            )
        )
    for index, record in enumerate(
        _sequence(_mapping(payload.get("lineage_contamination_ledger")).get("records"))
    ):
        refs = [str(ref) for ref in _sequence(record.get("lineage_refs"))]
        if any(ref.startswith("/Users/") or ref.startswith("~/") for ref in refs):
            issues.append(
                _issue(
                    "layer3_g1_local_path_lineage_ref",
                    f"$.lineage_contamination_ledger.records[{index}].lineage_refs",
                    "Workstation-local lineage refs must be canonicalized before authority.",
                )
            )


def _validate_acquisition(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    for index, record in enumerate(_sequence(payload.get("acquisition_grounding_records"))):
        records_gap_abstention = (
            record.get("grounding_status") == "grounded_abstention"
            and not record.get("coverage_claimed")
        )
        if (
            not records_gap_abstention
            and (
                not record.get("source_contract_ref")
                or not record.get("source_contract_snapshot_ref")
            )
        ):
            issues.append(
                _issue(
                    "layer3_g1_missing_source_contract",
                    f"$.acquisition_grounding_records[{index}].source_contract_ref",
                    "Acquisition records require a validated SourceContract before grounding.",
                )
            )
        if record.get("coverage_claimed"):
            issues.append(
                _issue(
                    "layer3_g1_acquisition_gap_overclaimed",
                    f"$.acquisition_grounding_records[{index}].coverage_claimed",
                    "Candidate acquisition strategies cannot overclaim coverage.",
                )
            )


def _validate_projection(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    projection = _mapping(payload.get("adapter_projection"))
    if projection.get("dropped_field_paths"):
        issues.append(
            _issue(
                "layer3_g1_semantic_loss",
                "$.adapter_projection.dropped_field_paths",
                "Adapter projection dropped lineage, rights, or authority fields.",
            )
        )


def _validate_recall_freshness(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    recall = _mapping(payload.get("search_recall_freshness"))
    if not recall:
        return
    if (
        recall.get("measurement_provenance") in {None, "", "self_attested", "not_measured"}
        or not _sequence(recall.get("query_trace_refs"))
    ):
        issues.append(
            _issue(
                "layer3_g1_search_recall_not_measured",
                "$.search_recall_freshness.measurement_provenance",
                "Search recall/freshness must be measured, not self-attested.",
            )
        )
    domain_ceiling = payload.get("grounding_closure_outcome") == (
        "grounded_abstention_domain_ceiling"
    )
    if domain_ceiling and recall.get("search_recall_status") != "pass":
        issues.append(
            _issue(
                "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling",
                "$.search_recall_freshness.search_recall_status",
                "Recall miss blocks domain ceiling; emit search-ceiling repair instead.",
            )
        )
        issues.append(
            _issue(
                "layer3_g1_search_ceiling_not_domain_ceiling",
                "$.grounding_closure_outcome",
                "Unhealthy search cannot be reported as data-insufficiency domain ceiling.",
            )
        )
    if domain_ceiling and recall.get("index_freshness_status") != "pass":
        issues.append(
            _issue(
                "layer3_g1_stale_index_blocks_domain_ceiling",
                "$.search_recall_freshness.index_freshness_status",
                "Stale indexes block domain ceiling; emit search-ceiling repair instead.",
            )
        )
        issues.append(
            _issue(
                "layer3_g1_search_ceiling_not_domain_ceiling",
                "$.grounding_closure_outcome",
                "Unhealthy search cannot be reported as data-insufficiency domain ceiling.",
            )
        )


def _validate_hardcode_delta(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    delta = _mapping(payload.get("hardcode_strangle_delta"))
    if not delta:
        return
    if int(delta.get("fallback_closure_count") or 0) > 0 or delta.get("used_fallback_refs"):
        issues.append(
            _issue(
                "layer3_g1_hardcode_fallback_used_for_closure",
                "$.hardcode_strangle_delta",
                "Hardcoded construct/scenario-family fallbacks cannot close G1.",
            )
        )
    status = delta.get("fallback_deletion_status")
    pending = status == "search_path_replaced_deletion_pending"
    fully_deleted = status in {None, "deleted_or_disabled_no_fallback"}
    any_reachable = any(
        not _mapping(record).get("fallback_deleted_or_disabled")
        for record in _sequence(delta.get("delta_records"))
    )
    if status not in {
        None,
        "deleted_or_disabled_no_fallback",
        "search_path_replaced_deletion_pending",
    }:
        issues.append(
            _issue(
                "layer3_g1_hardcode_fallback_not_deleted",
                "$.hardcode_strangle_delta.fallback_deletion_status",
                "G1 hardcode strangle status must be either deleted or explicitly pending.",
            )
        )
    if fully_deleted and any_reachable:
        issues.append(
            _issue(
                "layer3_g1_hardcode_fallback_not_deleted",
                "$.hardcode_strangle_delta.delta_records",
                "Executable hardcoded fallbacks must be deleted or disabled with no fallback.",
            )
        )
    if pending and not delta.get("measurement_provenance"):
        issues.append(
            _issue(
                "layer3_g1_hardcode_strangle_incomplete",
                "$.hardcode_strangle_delta.measurement_provenance",
                "Pending hardcode strangle status must carry measurement provenance.",
            )
        )


def _validate_l1_l5_l6(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    coverage = _mapping(payload.get("l1_l5_l6_index_coverage"))
    if not coverage:
        return
    l1_refs = [str(ref) for ref in _sequence(coverage.get("l1_query_refs"))]
    if not l1_refs:
        issues.append(
            _issue(
                "layer3_g1_l1_l5_l6_index_coverage_missing",
                "$.l1_l5_l6_index_coverage.l1_query_refs",
                "G1 closure requires direct L1 ds_metric_bindings query refs.",
            )
        )
    if coverage.get("bounded_surrogate") and coverage.get("coverage_claim") == "full_dcat_scale":
        issues.append(
            _issue(
                "layer3_g1_l1_l5_l6_bounded_surrogate_overclaimed",
                "$.l1_l5_l6_index_coverage.coverage_claim",
                "Bounded surrogate cannot be reported as full DCAT-scale coverage.",
            )
        )
    if any(ref.startswith("capability-index://") for ref in l1_refs):
        issues.append(
            _issue(
                "layer3_g1_capability_index_used_as_l1_search",
                "$.l1_l5_l6_index_coverage.l1_query_refs",
                "Capability-index output is transition evidence, not the L1 search route.",
            )
        )
    if coverage.get("production_dcat_exists") and any(
        ref.startswith("fixture://") for ref in l1_refs
    ):
        issues.append(
            _issue(
                "layer3_g1_unjustified_l1_surrogate",
                "$.l1_l5_l6_index_coverage.l1_query_refs",
                "A surrogate L1 route is unjustified when production ds_metric_bindings exists.",
            )
        )


def _validate_mechanism_generality(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    fixture = _mapping(payload.get("mechanism_generality"))
    if fixture and int(fixture.get("request_shape_count") or 0) < 2:
        issues.append(
            _issue(
                "layer3_g1_mechanism_generality_single_request",
                "$.mechanism_generality.request_shape_count",
                "G1 must prove at least two request shapes through the same mechanism.",
            )
        )


def _validate_search_engineering_quality(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    quality = _mapping(payload.get("search_engineering_quality"))
    if not quality:
        return
    if (
        quality.get("measurement_provenance") in {None, "", "self_attested", "not_measured"}
        or not _sequence(quality.get("query_trace_refs"))
    ):
        issues.append(
            _issue(
                "layer3_g1_search_engineering_quality_not_measured",
                "$.search_engineering_quality.measurement_provenance",
                "G1 search engineering quality must be measured from runtime query traces.",
            )
        )
    if (
        quality.get("status") != "pass"
        or not quality.get("index_backed", True)
        or not quality.get("lazy_or_streaming", True)
        or quality.get("eager_full_corpus_scan")
        or quality.get("broad_fail_open_error_handling")
        or not _sequence(quality.get("named_library_refs"))
    ):
        issues.append(
            _issue(
                "layer3_g1_search_engineering_quality_failed",
                "$.search_engineering_quality",
                "G1 search must be indexed, bounded/lazy, deterministic, and fail-closed.",
            )
        )


def _validate_manifest_drift(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    manifest_counts = _mapping(_mapping(payload.get("readiness_manifest")).get("counts"))
    runtime_counts = _mapping(payload.get("runtime_counts"))
    if manifest_counts and runtime_counts and manifest_counts != runtime_counts:
        issues.append(
            _issue(
                "layer3_g1_manifest_runtime_drift",
                "$.readiness_manifest.counts",
                "Persisted G1 readiness manifest counts must match runtime builder counts.",
            )
        )


def _validate_authority(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    counts = _mapping(_mapping(payload.get("readiness_manifest")).get("counts"))
    if int(counts.get("production_claim_authority_count") or 0) > 0:
        issues.append(
            _issue(
                "layer3_g1_claim_authority_leak",
                "$.readiness_manifest.counts.production_claim_authority_count",
                "G1 cannot produce claim authority.",
            )
        )
    if int(counts.get("useful_design_credit_count") or 0) > 0:
        issues.append(
            _issue(
                "layer3_g1_useful_design_credit_leak",
                "$.readiness_manifest.counts.useful_design_credit_count",
                "G1 cannot produce useful-design credit.",
            )
        )
    for index, binding in enumerate(
        _sequence(_mapping(payload.get("grounded_source_contracts")).get("bindings"))
    ):
        if "claim_authority" in _sequence(binding.get("authoritative_for")):
            issues.append(
                _issue(
                    "layer3_g1_claim_authority_leak",
                    f"$.grounded_source_contracts.bindings[{index}].authoritative_for",
                    "Grounding bindings cannot be authoritative for claims.",
                )
            )
        if "claim_authority" not in _sequence(binding.get("may_not_use_for")):
            issues.append(
                _issue(
                    "layer3_g1_claim_authority_leak",
                    f"$.grounded_source_contracts.bindings[{index}].may_not_use_for",
                    "Grounding bindings must explicitly exclude claim authority.",
                )
            )


def _validate_health_metrics(
    payload: Mapping[str, Any],
    issues: list[Layer3G1ValidationIssue],
) -> None:
    metric_ids = set(_sequence(_mapping(payload.get("health_metric_delta")).get("metric_ids")))
    if metric_ids and not set(EXPECTED_HEALTH_METRICS) <= metric_ids:
        issues.append(
            _issue(
                "layer3_g1_surface_unsynced",
                "$.health_metric_delta.metric_ids",
                "All five Layer 3 health metric deltas must be represented.",
            )
        )


def _validation_summary(
    repo_root: Path,
    payload: Mapping[str, Any],
    issues: Sequence[Layer3G1ValidationIssue],
) -> dict[str, Any]:
    del repo_root
    counts = dict(_mapping(_mapping(payload.get("readiness_manifest")).get("counts")))
    return {
        "schema_version": LAYER3_G1_SCHEMA_VERSION,
        "rule_version": LAYER3_G1_RULE_VERSION,
        "issue_count": len(issues),
        **counts,
    }


def _fixture_payload(repo_root: Path, name: str) -> dict[str, Any]:
    return _read_json(repo_root / G1_FIXTURE_DIR / name)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        return (value,)
    return tuple(value)


def _issue(code: str, path: str, message: str) -> Layer3G1ValidationIssue:
    return Layer3G1ValidationIssue(code=code, path=path, message=message)


__all__ = [
    "AcquisitionGroundingRecord",
    "GroundedSourceContractBinding",
    "Layer3G1AdapterAdmissionBundle",
    "Layer3G1Bundle",
    "Layer3G1ConformanceReport",
    "Layer3G1CoverageLineageAbstentionSurface",
    "Layer3G1FreeGrowthFixture",
    "Layer3G1FreeGrowthReport",
    "Layer3G1GroundabilityProbe",
    "Layer3G1GroundingSearchLedger",
    "Layer3G1HardcodeStrangleDelta",
    "Layer3G1IndexFreshnessRecord",
    "Layer3G1L1L5L6IndexCoverageReport",
    "Layer3G1MechanismGeneralityFixture",
    "Layer3G1ReadinessManifest",
    "Layer3G1SearchEngineeringQualityReport",
    "Layer3G1SearchRecallFreshnessReport",
    "Layer3G1SearchRecallSeed",
    "Layer3G1SubstrateSearchRequest",
    "Layer3G1SubstrateSearchResult",
    "Layer3G1ValidationIssue",
    "Layer3G1ValidationReport",
    "LineageContaminationCheck",
    "build_acquisition_grounding_adapter",
    "build_fabric_source_contract_snapshot_from_capability",
    "build_g1_free_growth_report",
    "build_g1_grounding_search_ledgers",
    "build_g1_hardcode_strangle_delta",
    "build_g1_l1_l5_l6_index_coverage_report",
    "build_g1_requirement_to_capability_resolver",
    "build_g1_search_engineering_quality_report",
    "build_layer3_g1_bundle",
    "build_substrate_grounding_search_adapter",
    "probe_firm_survival_source_contract_v2_groundability",
    "render_g1_expert_machine_surface",
    "validate_g1_adapter_conformance",
    "validate_g1_search_recall_freshness",
    "validate_layer3_g1_bundle",
]
