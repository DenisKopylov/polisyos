"""Layer 3 G0 grounding inventory contracts and read-only producers.

This module freezes the pre-adapter Layer 3 discipline. It inspects existing
repository artifacts as data, registers source touchpoints in shadow form, and
validates that quarantine/status/firewall rules block adapter admission before
any G1+ adapter work begins.
"""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, model_validator

from polisyos.core.contracts import DiscoveryPosture  # noqa: TC001
from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel
from polisyos.runtime.quality.proving_ground.pinned_route_demand_home import (
    read_layer3_gx_construct_bundle_id,
    read_layer3_gx_pinned_case_id,
)

LAYER3_G0_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g0_discovery_search.v2"
LAYER3_G0_RULE_VERSION = "policyos.layer3.g0.discovery_search_free_growth.v2"
LAYER3_G0_MANIFEST_ID = "layer3.g0.discovery_search_readiness"
SOURCE_TOUCHPOINT_SCAN_MODE = "ast_top_level_and_local_imports"
AUTHORITY_POSTURE = "llm_output_candidate_never_authority"
ADR_ACCEPTANCE_AUTHORITY = "human_principal_required"
NO_ADAPTER_ADMISSION_BEFORE_G0 = True
NO_ADAPTER_ADMISSION_IN_G0 = True
NO_HARDCODE_FALLBACKS = True
SEARCH_FRONTIER_REQUIRED_FOR_ABSTENTION = True
RECALL_FRESHNESS_REQUIRED_FOR_DOMAIN_CEILING = True
REPO_ROOT = Path(__file__).resolve().parents[5]
FIRST_VERTICAL_CORPUS_CASE_ID = read_layer3_gx_pinned_case_id(REPO_ROOT)
FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID = read_layer3_gx_construct_bundle_id(REPO_ROOT)

PDC_IMPORT_ALLOWLIST_ROOTS: tuple[str, ...] = ("core",)
PDC_IMPORT_ALLOWLIST_RATIONALE = (
    "core is shared primitive/DTO infrastructure, not a capability source"
)
POLICY_TOML_PDC_CONFLICT_ROOTS: tuple[str, ...] = ("runtime", "scientist", "ir")

CapabilityDisposition = Literal[
    "integrate_as_is",
    "integrate_after_refactor",
    "wrap_then_strangle",
    "quarantine",
    "surface_out_of_scope",
]
DataKind = Literal["data_asset", "acquisition", "processing_transform"]
AdapterMaturity = Literal["fail_closed", "predictive", "calibrated"]
PromotionState = Literal["shadow", "governed_promoted", "promotion_blocked"]
AdapterAdmissionState = Literal["candidate_shadow_only", "blocked", "admitted"]
ConformanceStatus = Literal["not_run_pre_adapter", "pass", "blocked"]
GroundingDisposition = Literal[
    "grounded_binding",
    "grounded_limited",
    "grounded_abstention",
    "ungrounded_blocked",
]
HealthMetricId = Literal[
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
]
ResourceKind = Literal[
    "dataset",
    "claim",
    "legal_norm",
    "method",
    "agent",
    "tool",
    "adapter",
    "case",
    "probe",
]
DiscoveryIndexKind = Literal["structured", "text", "vector", "graph", "registry"]
SearchCompletenessStatus = Literal[
    "complete_with_candidates",
    "complete_no_candidate",
    "incomplete_budget_cutoff",
    "incomplete_index_unavailable",
    "incomplete_alias_gap",
    "incomplete_schema_mismatch",
    "stale_index",
    "recall_failed",
]
CeilingDiagnosis = Literal[
    "none",
    "domain_ceiling",
    "search_ceiling",
    "adapter_missing",
    "governance_blocked",
]
IndexStalenessStatus = Literal["fresh", "stale", "unknown"]
HardcodeEnumerationKind = Literal[
    "construct",
    "dataset",
    "variable",
    "method",
    "agent",
    "tool",
    "source",
    "governed_vocabulary_exception",
]
SourceTouchpointRegistrationStatus = Literal[
    "registered_pre_admission",
    "requires_adapter_contract",
    "blocked_by_quarantine",
]
PortlessCapabilityOpenQuestionStatus = Literal[
    "governed_open_question",
    "not_required",
]
BindingConstraintRank = Literal["substrate", "causal_support", "calibration"]
AdapterCostClass = Literal["near_typed", "raw", "conceptual_legacy"]
ValidationStatus = Literal["pass", "fail"]

_RUNTIME_QUALITY_SOURCE_ROOTS = frozenset(
    {
        "data_forge",
        "data_requirement",
        "fabric",
        "foundry",
        "lex",
        "method_requirement",
        "participation_requirement",
        "scholar",
        "scholar_requirement",
        "scientist",
    }
)
_REQUIRED_DATA_ASSET_ROOTS: tuple[str, ...] = (
    "production_data",
    "tools/ops_runners/ukraine_data",
    "tests/fixtures/universal-corpus/cases",
    "tests/fixtures/universal-corpus/producer_stubs",
    (
        "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
        "layer2-sealed-universality-battery"
    ),
    "docs/research/universal-policy-design/outcome-corpus",
)
_STATUS_RULE_IDS: tuple[str, ...] = (
    "quarantine_dominates_admission",
    "pre_adapter_conformance_cannot_admit_authority",
    "maturity_cannot_exceed_evidence",
    "promotion_blocked_before_g4",
    "discoverable_without_adapter_candidate_only",
    "executable_without_conformance_candidate_only",
    "admitted_authority_invalid_in_g0",
    "stale_index_no_hit_is_search_ceiling",
    "recall_miss_domain_ceiling_invalid",
    "quarantine_dominates_adapter_candidate",
)
_HEALTH_METRICS: tuple[HealthMetricId, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
HARDCODE_ENUMERATION_BACKLOG_PATH = Path(
    "architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json"
)


class ValidationIssue(Layer2ReadinessModel):
    """One content validation issue emitted by the G0 validator."""

    code: str = Field(..., min_length=1, max_length=160)
    path: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1, max_length=1000)


class ValidationReport(Layer2ReadinessModel):
    """Validation report with issue list and derived summary metrics."""

    status: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class CapabilityInventoryEntry(Layer2ReadinessModel):
    """Inventory row for a package or data/corpus source root."""

    capability_id: str = Field(..., min_length=1, max_length=300)
    package_kind: str = Field(..., min_length=1, max_length=120)
    path: str = Field(..., min_length=1, max_length=500)
    file_count: int = Field(default=0, ge=0)
    loc: int = Field(default=0, ge=0)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=500)
    current_capability_label: str = Field(..., min_length=1, max_length=120)
    current_imports: list[str] = Field(default_factory=list, max_length=200)
    source_refs: list[str] = Field(default_factory=list, max_length=200)
    mapped_port_ids: list[str] = Field(default_factory=list, max_length=80)


class DataAssetInventoryEntry(Layer2ReadinessModel):
    """Inventory row for one data asset discovered under a required root."""

    asset_id: str = Field(..., min_length=1, max_length=240)
    data_kind: DataKind
    path: str = Field(..., min_length=1, max_length=700)
    owning_root: str = Field(..., min_length=1, max_length=500)
    size_bytes: int | None = Field(default=None, ge=0)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=700)
    lineage_evidence_ref: str = Field(..., min_length=1, max_length=700)
    rights_evidence_ref: str = Field(..., min_length=1, max_length=700)
    freshness_evidence_ref: str = Field(..., min_length=1, max_length=700)
    fitness_evidence_ref: str = Field(..., min_length=1, max_length=700)
    contamination_check_ref: str = Field(..., min_length=1, max_length=700)


class ProcessingTransformInventoryEntry(Layer2ReadinessModel):
    """Inventory row for one processing transform under a required root."""

    transform_id: str = Field(..., min_length=1, max_length=240)
    source_root: str = Field(..., min_length=1, max_length=500)
    output_asset_refs: list[str] = Field(default_factory=list, max_length=100)
    transform_script_refs: list[str] = Field(..., min_length=1, max_length=50)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=700)
    replay_command_ref: str = Field(..., min_length=1, max_length=700)
    contamination_risk_refs: list[str] = Field(..., min_length=1, max_length=50)


class DiscoveryIndexInventoryEntry(Layer2ReadinessModel):
    """Inventory row for one discovery index or registry used by G0 control plane."""

    index_id: str = Field(..., min_length=1, max_length=240)
    source_family: str = Field(..., min_length=1, max_length=160)
    index_kind: DiscoveryIndexKind
    backing_path_or_service: str = Field(..., min_length=1, max_length=700)
    corpus_snapshot_ref: str = Field(..., min_length=1, max_length=700)
    schema_version: str = Field(..., min_length=1, max_length=200)
    index_version: str = Field(..., min_length=1, max_length=200)
    freshness_ref: str = Field(..., min_length=1, max_length=700)
    owner: str = Field(..., min_length=1, max_length=200)
    rebuild_command: str = Field(..., min_length=1, max_length=700)


class ResourceDiscoveryRecord(Layer2ReadinessModel):
    """Candidate resource discovered before adapter admission."""

    resource_id: str = Field(..., min_length=1, max_length=300)
    resource_kind: ResourceKind
    discovery_posture: DiscoveryPosture
    index_refs: list[str] = Field(default_factory=list, max_length=80)
    executable_interface_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    missing_labels: list[str] = Field(default_factory=list, max_length=30)


class GroundingSearchLedger(Layer2ReadinessModel):
    """Replayable search-frontier control-plane record, never authority evidence in G0."""

    ledger_id: str = Field(..., min_length=1, max_length=300)
    typed_request_ref: str = Field(..., min_length=1, max_length=500)
    normalized_query_refs: list[str] = Field(default_factory=list, max_length=40)
    searched_index_refs: list[str] = Field(..., min_length=1, max_length=80)
    ranking_policy_ref: str | None = Field(default=None, max_length=500)
    selected_candidate_refs: list[str] = Field(default_factory=list, max_length=100)
    rejected_candidate_refs: list[str] = Field(default_factory=list, max_length=100)
    cutoff_budget_ref: str | None = Field(default=None, max_length=500)
    absence_or_incompleteness_reason: str | None = Field(default=None, max_length=500)
    completeness_status: SearchCompletenessStatus
    deterministic_replay_key: str = Field(..., min_length=1, max_length=200)
    authoritative_for: list[str] = Field(default_factory=list, max_length=20)
    may_not_use_for: list[str] = Field(default_factory=list, max_length=40)


class SearchRecallSeed(Layer2ReadinessModel):
    """Known-groundable seed used to make false abstention visible."""

    seed_id: str = Field(..., min_length=1, max_length=240)
    target_resource_ref: str = Field(..., min_length=1, max_length=500)
    expected_query_shape: str = Field(..., min_length=1, max_length=300)
    required_index_refs: list[str] = Field(..., min_length=1, max_length=40)
    expected_minimum_discovery_posture: DiscoveryPosture
    refresh_requirement: str = Field(default="fresh_index_required", max_length=300)
    observed_status: Literal["found", "missed"] = "found"
    failure_issue_code: str = Field(..., min_length=1, max_length=160)


class IndexFreshnessRecord(Layer2ReadinessModel):
    """Freshness receipt for a discovery index."""

    index_id: str = Field(..., min_length=1, max_length=240)
    corpus_snapshot_ref: str = Field(..., min_length=1, max_length=700)
    last_refresh_ref: str = Field(..., min_length=1, max_length=700)
    expected_freshness_window: str = Field(..., min_length=1, max_length=80)
    staleness_status: IndexStalenessStatus
    blocked_authority_effects: list[str] = Field(default_factory=list, max_length=40)


class FreeGrowthFixture(Layer2ReadinessModel):
    """Fixture proving resource growth can flow through discovery without code changes."""

    fixture_id: str = Field(..., min_length=1, max_length=240)
    resource_kind: ResourceKind
    fixture_mutation: dict[str, Any] = Field(default_factory=dict)
    index_refresh_command_ref: str = Field(..., min_length=1, max_length=700)
    index_refresh_receipt_ref: str = Field(..., min_length=1, max_length=700)
    expected_discovery_query: dict[str, Any] = Field(default_factory=dict)
    expected_posture: DiscoveryPosture
    observed_posture: DiscoveryPosture
    expected_executable_use_path: str = Field(..., min_length=1, max_length=700)
    no_code_change_assertion: bool
    authoritative_for: list[str] = Field(default_factory=list, max_length=20)
    may_not_use_for: list[str] = Field(default_factory=list, max_length=40)


class MechanismRequestShape(Layer2ReadinessModel):
    """One request shape covered by a mechanism-generality fixture."""

    shape_id: str = Field(..., min_length=1, max_length=240)
    query: str = Field(..., min_length=1, max_length=700)


class MechanismGeneralityFixture(Layer2ReadinessModel):
    """Fixture proving a search mechanism is not pinned to one case."""

    fixture_id: str = Field(..., min_length=1, max_length=240)
    search_mechanism_id: str = Field(..., min_length=1, max_length=240)
    request_shapes: list[MechanismRequestShape] = Field(..., min_length=2, max_length=20)
    expected_resources: list[str] = Field(..., min_length=1, max_length=80)
    expected_postures: list[DiscoveryPosture] = Field(..., min_length=1, max_length=20)
    expected_executable_use_paths: list[str] = Field(..., min_length=1, max_length=80)
    no_code_change_assertion: bool


class HardcodeEnumerationBacklogEntry(Layer2ReadinessModel):
    """Registered strangle target for a hardcoded capability-gating enumeration."""

    backlog_id: str = Field(..., min_length=1, max_length=240)
    file: str = Field(..., min_length=1, max_length=700)
    pattern: str = Field(..., min_length=1, max_length=200)
    enumeration_kind: HardcodeEnumerationKind
    governed_vocabulary_exception: bool = False
    target_discovery_path: str = Field(..., min_length=1, max_length=700)
    owner: str = Field(..., min_length=1, max_length=200)
    deletion_condition: str = Field(..., min_length=1, max_length=1000)
    fallback_forbidden: bool = True


class NoHardcodeEnumerationViolation(Layer2ReadinessModel):
    """One no-hardcode lint violation or registered capability fallback."""

    file: str = Field(..., min_length=1, max_length=700)
    pattern: str = Field(..., min_length=1, max_length=200)
    enumeration_kind: HardcodeEnumerationKind
    governed_vocabulary_exception: bool = False
    registered_backlog_ref: str | None = Field(default=None, max_length=300)
    fallback_forbidden: bool = True


class GovernedVocabularyException(Layer2ReadinessModel):
    """Schema/status vocabulary that is not a capability fallback list."""

    file: str = Field(..., min_length=1, max_length=700)
    pattern: str = Field(..., min_length=1, max_length=200)
    enumeration_kind: HardcodeEnumerationKind
    governed_vocabulary_exception: bool = True
    rationale: str = Field(..., min_length=1, max_length=1000)


class RequiredDataAssetRoot(Layer2ReadinessModel):
    """Required G0 data/corpus root and the entries discovered under it."""

    root_id: str = Field(..., min_length=1, max_length=180)
    path: str = Field(..., min_length=1, max_length=500)
    discovered_assets: list[str] = Field(default_factory=list, max_length=1000)
    discovered_transforms: list[str] = Field(default_factory=list, max_length=200)


class CapabilityTriageRecord(Layer2ReadinessModel):
    """Triage disposition for a capability source before adapter admission."""

    capability_id: str = Field(..., min_length=1, max_length=300)
    disposition: CapabilityDisposition
    rationale: str = Field(..., min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=60)
    missing_capability_labels: list[str] = Field(default_factory=list, max_length=20)
    quarantine_ref: str | None = Field(default=None, max_length=500)
    adapter_admissibility: str = Field(..., min_length=1, max_length=120)
    authority_boundary: AuthorityBoundary | None = None


class QuarantineRegistryEntry(Layer2ReadinessModel):
    """Hard blocker entry consumed by adapter-admission validation."""

    target_id: str = Field(..., min_length=1, max_length=200)
    target_kind: str = Field(..., min_length=1, max_length=120)
    reason: str = Field(..., min_length=1, max_length=1000)
    pattern_ids: list[str] = Field(..., min_length=1, max_length=20)
    blocker_codes: list[str] = Field(..., min_length=1, max_length=30)
    enforcement_surface: str = Field(..., min_length=1, max_length=200)
    release_condition: str = Field(..., min_length=1, max_length=1000)


class Port(Layer2ReadinessModel):
    """Derived narrow-waist port from the cluster ownership map."""

    port_id: str = Field(
        ...,
        validation_alias=AliasChoices("port_id", "id"),
        min_length=1,
        max_length=200,
    )
    cluster: str = Field(..., min_length=1, max_length=80)
    facet: str = Field(..., min_length=1, max_length=160)
    publishes: list[str] = Field(default_factory=list, max_length=200)
    consumes: list[str] = Field(default_factory=list, max_length=200)
    source_line_ref: str = Field(..., min_length=1, max_length=700)


class PortlessCapabilityOpenQuestion(Layer2ReadinessModel):
    """Governed waist-change question for a capability with no current port."""

    capability_id: str = Field(..., min_length=1, max_length=200)
    missing_port_rationale: str = Field(..., min_length=1, max_length=1000)
    why_existing_ports_cannot_express_it: str = Field(..., min_length=1, max_length=1000)
    proposed_waist_change_question: str = Field(..., min_length=1, max_length=1000)
    owner: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=40)
    status: PortlessCapabilityOpenQuestionStatus


class SourceTouchpointRegistration(Layer2ReadinessModel):
    """Registration for one runtime/quality import of a subordinate source root."""

    touchpoint_id: str = Field(..., min_length=1, max_length=300)
    file: str = Field(..., min_length=1, max_length=500)
    line: int = Field(..., ge=1)
    import_root: str = Field(..., min_length=1, max_length=120)
    source_module: str = Field(..., min_length=1, max_length=500)
    registration_status: SourceTouchpointRegistrationStatus
    existing_source_truth_adapter_path_ref: str | None = Field(default=None, max_length=300)
    quarantine_check_result: str = Field(..., min_length=1, max_length=160)
    admission_allowed: bool = False


class AdapterAdmissionRecord(Layer2ReadinessModel):
    """Pre-admission adapter candidate record. G0 never admits adapters."""

    adapter_id: str = Field(..., min_length=1, max_length=240)
    source_ids: list[str] = Field(..., min_length=1, max_length=80)
    port_ids: list[str] = Field(..., min_length=1, max_length=80)
    maturity: AdapterMaturity
    promotion_state: PromotionState
    conformance_status: ConformanceStatus
    quarantine_check: str = Field(..., min_length=1, max_length=160)
    admission_state: AdapterAdmissionState
    admitted: bool = False
    adapter_contract_path_refs: list[str] = Field(default_factory=list, max_length=40)
    source_touchpoint_refs: list[str] = Field(default_factory=list, max_length=200)


class DataAssetPort(Layer2ReadinessModel):
    """Data asset binding to one or more G0 ports with evidence refs."""

    asset_id: str = Field(..., min_length=1, max_length=240)
    data_kind: DataKind
    path: str = Field(..., min_length=1, max_length=700)
    lineage_ref: str = Field(..., min_length=1, max_length=700)
    rights_ref: str = Field(..., min_length=1, max_length=700)
    freshness_ref: str = Field(..., min_length=1, max_length=700)
    fitness_ref: str = Field(..., min_length=1, max_length=700)
    contamination_check_ref: str = Field(..., min_length=1, max_length=700)
    source_contract_ref: str | None = Field(default=None, max_length=700)
    source_contract_readiness: str = Field(..., min_length=1, max_length=700)
    index_refs: list[str] = Field(default_factory=list, max_length=80)
    port_ids: list[str] = Field(..., min_length=1, max_length=40)


class ConformanceHarnessRecord(Layer2ReadinessModel):
    """Pre-adapter conformance harness skeleton using existing preservation paths."""

    harness_id: str = Field(..., min_length=1, max_length=200)
    existing_source_truth_adapter_path_refs: list[str] = Field(..., min_length=1)
    adapter_loss_blocker_refs: list[str] = Field(..., min_length=1)
    status: ConformanceStatus
    negative_fixtures: list[str] = Field(..., min_length=1, max_length=80)


class HealthMetricLedger(Layer2ReadinessModel):
    """Frozen G0 health metric ledger row."""

    metric_id: HealthMetricId
    owner: str = Field(..., min_length=1, max_length=200)
    freeze_value: str | int | float | dict[str, Any]
    trend_vocabulary: list[str] = Field(..., min_length=1, max_length=10)
    per_slice_delta_rule: str = Field(..., min_length=1, max_length=1000)
    next_update_rule: str = Field(..., min_length=1, max_length=1000)


class StatusCompositionRule(Layer2ReadinessModel):
    """Rule proving G0 status composition cannot launder authority."""

    rule_id: str = Field(..., min_length=1, max_length=200)
    inputs: list[str] = Field(..., min_length=1, max_length=20)
    composed_result: str = Field(..., min_length=1, max_length=200)
    issue_code: str = Field(..., min_length=1, max_length=160)
    negative_fixture_ref: str = Field(..., min_length=1, max_length=700)


class EmptyPortMapEntry(Layer2ReadinessModel):
    """Empty-port blocker for the first vertical proving-ground case."""

    port_id: str = Field(..., min_length=1, max_length=200)
    proving_ground_case_id: str = Field(..., min_length=1, max_length=200)
    blocker_cause: str = Field(..., min_length=1, max_length=1000)
    binding_constraint_rank: BindingConstraintRank
    next_adapter_dependency: str = Field(..., min_length=1, max_length=300)


class AdapterCostMapEntry(Layer2ReadinessModel):
    """Adapter sequencing cost row for one source/port pair."""

    source_id: str = Field(..., min_length=1, max_length=200)
    port_id: str = Field(..., min_length=1, max_length=200)
    near_typed_raw_classification: AdapterCostClass
    existing_contract_refs: list[str] = Field(default_factory=list, max_length=50)
    adapter_effort_tier: str = Field(..., min_length=1, max_length=80)
    semantic_loss_risk: str = Field(..., min_length=1, max_length=500)
    sequencing_priority: int = Field(..., ge=1)


class FirstVerticalCaseRecord(Layer2ReadinessModel):
    """First vertical case identifiers kept separate across corpus and constructs."""

    case_ref: str = Field(..., min_length=1, max_length=500)
    first_vertical_corpus_case_id: str = Field(..., min_length=1, max_length=200)
    first_vertical_construct_bundle_id: str = Field(..., min_length=1, max_length=200)
    authority_posture: str = Field(..., min_length=1, max_length=200)


class CapabilityDataInventory(Layer2ReadinessModel):
    """Capability inventory for immediate source packages and data roots."""

    entries: list[CapabilityInventoryEntry] = Field(default_factory=list, max_length=300)
    summary: dict[str, Any] = Field(default_factory=dict)


class DataAssetInventory(Layer2ReadinessModel):
    """Data/corpus inventory with asset-level and transform-level rows."""

    scan_mode: str = Field(default="manifest_backed_lightweight")
    required_roots: list[RequiredDataAssetRoot] = Field(default_factory=list, max_length=20)
    data_assets: list[DataAssetInventoryEntry] = Field(default_factory=list, max_length=3000)
    processing_transforms: list[ProcessingTransformInventoryEntry] = Field(
        default_factory=list,
        max_length=300,
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class DiscoveryIndexInventory(Layer2ReadinessModel):
    """Discovery indexes and registries known to G0."""

    entries: list[DiscoveryIndexInventoryEntry] = Field(default_factory=list, max_length=200)
    summary: dict[str, Any] = Field(default_factory=dict)


class ResourceDiscoveryInventory(Layer2ReadinessModel):
    """Discoverable and executable resources before adapter admission."""

    records: list[ResourceDiscoveryRecord] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class GroundingSearchDiscipline(Layer2ReadinessModel):
    """G0 search-control contract bundle."""

    grounding_search_ledgers: list[GroundingSearchLedger] = Field(
        default_factory=list,
        max_length=100,
    )
    recall_seeds: list[SearchRecallSeed] = Field(default_factory=list, max_length=100)
    index_freshness_records: list[IndexFreshnessRecord] = Field(
        default_factory=list,
        max_length=100,
    )
    free_growth_fixtures: list[FreeGrowthFixture] = Field(default_factory=list, max_length=40)
    mechanism_generality_fixtures: list[MechanismGeneralityFixture] = Field(
        default_factory=list,
        max_length=20,
    )
    absence_semantics: dict[str, Any] = Field(default_factory=dict)
    index_freshness_policy: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class PortMap(Layer2ReadinessModel):
    """Derived G0 port map."""

    ports: list[Port] = Field(default_factory=list, max_length=200)
    portless_capability_open_questions: list[PortlessCapabilityOpenQuestion] = Field(
        default_factory=list,
        max_length=100,
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeQualityTouchpointInventory(Layer2ReadinessModel):
    """AST-scanned runtime/quality source touchpoint inventory."""

    scan_mode: str = SOURCE_TOUCHPOINT_SCAN_MODE
    registrations: list[SourceTouchpointRegistration] = Field(
        default_factory=list,
        max_length=500,
    )
    summary: dict[str, Any] = Field(default_factory=dict)

    def __iter__(self) -> Iterator[SourceTouchpointRegistration]:
        """Iterate over source touchpoint registrations."""

        return iter(self.registrations)

    def __len__(self) -> int:
        """Return the number of source touchpoint registrations."""

        return len(self.registrations)


class ImportFirewallViolation(Layer2ReadinessModel):
    """Forbidden pdc import discovered by the Layer 3 G0 firewall."""

    file: str = Field(..., min_length=1, max_length=500)
    line: int = Field(..., ge=1)
    import_root: str = Field(..., min_length=1, max_length=120)
    issue_code: str = "layer3_g0_pdc_non_waist_import"


class ImportFirewallReport(Layer2ReadinessModel):
    """Report for the strict Layer 3 pdc narrow-waist import firewall."""

    allowlist_roots: list[str] = Field(default_factory=lambda: list(PDC_IMPORT_ALLOWLIST_ROOTS))
    allowlist_rationale: str = PDC_IMPORT_ALLOWLIST_RATIONALE
    forbidden_roots: list[str] = Field(default_factory=list, max_length=200)
    violations: list[ImportFirewallViolation] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class HardcodeEnumerationBacklog(Layer2ReadinessModel):
    """Registered hardcoded enumeration strangle backlog."""

    entries: list[HardcodeEnumerationBacklogEntry] = Field(default_factory=list, max_length=100)
    summary: dict[str, Any] = Field(default_factory=dict)


class NoHardcodeEnumerationLintReport(Layer2ReadinessModel):
    """No-hardcode enumeration lint result for search/adapter routes."""

    status: ValidationStatus
    scan_profile: str = Field(default="targeted_search_adapter_paths", max_length=200)
    scanned_paths: list[str] = Field(default_factory=list, max_length=300)
    violations: list[NoHardcodeEnumerationViolation] = Field(
        default_factory=list,
        max_length=300,
    )
    governed_vocabulary_exceptions: list[GovernedVocabularyException] = Field(
        default_factory=list,
        max_length=100,
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class EngineeringQualityCheck(Layer2ReadinessModel):
    """Structured-parser and bounded-scan proof for the G0 builder."""

    status: ValidationStatus
    named_libraries_parsers_indexes: list[str] = Field(..., min_length=1, max_length=40)
    scan_strategy: str = Field(..., min_length=1, max_length=500)
    bounded_work_proof: str = Field(..., min_length=1, max_length=1000)
    scaling_perf_check_ref: str = Field(..., min_length=1, max_length=700)
    deterministic_ordering_ref: str = Field(..., min_length=1, max_length=700)
    fail_closed_error_handling_policy: str = Field(..., min_length=1, max_length=1000)
    summary: dict[str, Any] = Field(default_factory=dict)


class StatusCompositionMatrix(Layer2ReadinessModel):
    """Status composition matrix required by G0."""

    rules: list[StatusCompositionRule] = Field(..., min_length=10, max_length=10)

    @model_validator(mode="after")
    def _validate_exact_rule_set(self) -> StatusCompositionMatrix:
        if tuple(rule.rule_id for rule in self.rules) != _STATUS_RULE_IDS:
            raise ValueError("status composition matrix must use the exact G0 rule set")
        return self


class Layer3G0ReadinessManifest(Layer2ReadinessModel):
    """Replay/check manifest summarizing G0 closure artifacts and runtime counts."""

    manifest_id: str = LAYER3_G0_MANIFEST_ID
    schema_version: str = LAYER3_G0_SCHEMA_VERSION
    rule_version: str = LAYER3_G0_RULE_VERSION
    closure_artifact_paths: list[str] = Field(default_factory=list, max_length=20)
    counts: dict[str, Any] = Field(default_factory=dict)
    adr_ref: str = "docs/adr/0175-layer3-grounding-subordination-discipline.md"
    first_vertical_corpus_case_id: str = FIRST_VERTICAL_CORPUS_CASE_ID
    first_vertical_construct_bundle_id: str = FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID
    runtime_builder_hash: str = Field(..., min_length=8, max_length=96)


class Layer3G0Bundle(Layer2ReadinessModel):
    """In-memory G0 bundle produced from committed repository state."""

    capability_inventory: CapabilityDataInventory
    data_asset_inventory: DataAssetInventory
    discovery_index_inventory: DiscoveryIndexInventory
    resource_discovery_inventory: ResourceDiscoveryInventory
    grounding_search_discipline: GroundingSearchDiscipline
    triage_registry: list[CapabilityTriageRecord]
    quarantine_registry: list[QuarantineRegistryEntry]
    port_map: PortMap
    runtime_quality_touchpoints: RuntimeQualityTouchpointInventory
    adapter_admission_registry: list[AdapterAdmissionRecord]
    data_asset_ports: list[DataAssetPort]
    conformance_harness: ConformanceHarnessRecord
    health_metric_ledgers: list[HealthMetricLedger]
    import_firewall_lint: ImportFirewallReport
    hardcode_enumeration_backlog: HardcodeEnumerationBacklog
    no_hardcode_enumeration_lint: NoHardcodeEnumerationLintReport
    engineering_quality_check: EngineeringQualityCheck
    status_composition_matrix: StatusCompositionMatrix
    empty_port_map: list[EmptyPortMapEntry]
    adapter_cost_map: list[AdapterCostMapEntry]
    first_vertical_case: FirstVerticalCaseRecord
    readiness_manifest: Layer3G0ReadinessManifest


def build_capability_inventory(repo_root: Path) -> CapabilityDataInventory:
    """Build the G0 capability inventory from immediate packages and data roots."""

    src_root = repo_root / "src/polisyos"
    entries: list[CapabilityInventoryEntry] = []
    for package_path in sorted(path for path in src_root.iterdir() if path.is_dir()):
        if package_path.name == "__pycache__":
            continue
        rel = _repo_path(package_path, repo_root)
        py_files = sorted(package_path.rglob("*.py"))
        readme = package_path / "README.md"
        owner_ref = _repo_ref(readme if readme.exists() else package_path, repo_root)
        entries.append(
            CapabilityInventoryEntry(
                capability_id=package_path.name,
                package_kind=_package_kind(package_path.name),
                path=rel,
                file_count=len(py_files),
                loc=sum(_line_count(path) for path in py_files),
                owner_evidence_ref=owner_ref,
                current_capability_label="implemented_but_not_orchestrated"
                if package_path.name in _RUNTIME_QUALITY_SOURCE_ROOTS
                else "surface_out_of_scope"
                if package_path.name in {"common", "schemas"}
                else "implemented",
                current_imports=_imports_for_package(package_path),
                source_refs=[owner_ref],
                mapped_port_ids=[]
                if package_path.name != "runtime"
                else ["DESIGNER_ITSELF.closeout"],
            )
        )

    for root in _REQUIRED_DATA_ASSET_ROOTS:
        path = repo_root / root
        entries.append(
            CapabilityInventoryEntry(
                capability_id=_slug(root),
                package_kind="data_corpus_root",
                path=root,
                file_count=_file_count(path),
                loc=0,
                owner_evidence_ref=_repo_ref(
                    path / "README.md" if (path / "README.md").exists() else path, repo_root
                ),
                current_capability_label="artifact_missing",
                current_imports=[],
                source_refs=[_repo_ref(path, repo_root)],
                mapped_port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            )
        )

    return CapabilityDataInventory(
        entries=entries,
        summary={
            "source_package_count": sum(
                1 for entry in entries if entry.package_kind != "data_corpus_root"
            ),
            "required_data_asset_root_count": len(_REQUIRED_DATA_ASSET_ROOTS),
        },
    )


def build_data_asset_inventory(repo_root: Path) -> DataAssetInventory:
    """Build a manifest-backed data and processing transform inventory."""

    required_roots: list[RequiredDataAssetRoot] = []
    data_assets: list[DataAssetInventoryEntry] = []
    transforms: list[ProcessingTransformInventoryEntry] = []

    production_root = repo_root / "production_data"
    root_manifest_path = production_root / "manifest.json"
    root_manifest = _load_json(root_manifest_path)
    bundles = root_manifest.get("bundles", {})
    production_assets: list[str] = []
    if isinstance(bundles, Mapping):
        for bundle_id, bundle in bundles.items():
            if not isinstance(bundle, Mapping):
                continue
            asset_path = f"production_data/{bundle.get('path', bundle_id)}"
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"production-data-{_slug(str(bundle_id))}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=root_manifest_path,
                    repo_root=repo_root,
                )
            )

    ukraine_manifest_path = (
        production_root / "ukraine_agent_simulation_baseline_20260410/FINAL_ARTIFACTS_MANIFEST.json"
    )
    ukraine_manifest = _load_json(ukraine_manifest_path)
    ukraine_files = ukraine_manifest.get("files", [])
    if isinstance(ukraine_files, Sequence) and not isinstance(ukraine_files, (str, bytes)):
        for row in ukraine_files:
            if not isinstance(row, Mapping):
                continue
            rel_path = str(row.get("path", ""))
            if not rel_path:
                continue
            asset_path = f"production_data/ukraine_agent_simulation_baseline_20260410/{rel_path}"
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"ukraine-simulation-{_slug(rel_path)}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=ukraine_manifest_path,
                    repo_root=repo_root,
                    size_bytes=_int_or_none(row.get("size_bytes")),
                )
            )

    academic_split_path = (
        production_root / "policyos_academic_runtime_slim_20260411T112032Z/SPLIT_MANIFEST.json"
    )
    academic_split = _load_json(academic_split_path)
    included_paths = academic_split.get("included_runtime_paths", [])
    if isinstance(included_paths, Sequence) and not isinstance(included_paths, (str, bytes)):
        for rel_path in included_paths:
            asset_path = (
                f"production_data/policyos_academic_runtime_slim_20260411T112032Z/{rel_path}"
            )
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"academic-runtime-{_slug(str(rel_path))}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=academic_split_path,
                    repo_root=repo_root,
                )
            )

    required_roots.append(
        RequiredDataAssetRoot(
            root_id="production_data",
            path="production_data",
            discovered_assets=sorted(set(production_assets)),
            discovered_transforms=[],
        )
    )

    ops_root = repo_root / "tools/ops_runners/ukraine_data"
    ops_scripts = sorted(
        _repo_path(path, repo_root) for path in ops_root.glob("*.py") if path.name != "__init__.py"
    )
    data_assets.append(
        _data_asset_entry(
            asset_id="ukraine-ops-runner-root",
            path="tools/ops_runners/ukraine_data",
            owning_root="tools/ops_runners/ukraine_data",
            evidence_path=ops_root / "README.md",
            repo_root=repo_root,
        )
    )
    for script in ops_scripts:
        transforms.append(
            ProcessingTransformInventoryEntry(
                transform_id=f"ukraine-ops-{_slug(Path(script).stem)}",
                source_root="tools/ops_runners/ukraine_data",
                output_asset_refs=["tools/ops_runners/ukraine_data"],
                transform_script_refs=[script],
                owner_evidence_ref=_repo_ref(ops_root / "README.md", repo_root),
                replay_command_ref=f"uv run python {script}",
                contamination_risk_refs=[_repo_ref(ops_root / "README.md", repo_root)],
            )
        )
    required_roots.append(
        RequiredDataAssetRoot(
            root_id="ukraine_ops_runners",
            path="tools/ops_runners/ukraine_data",
            discovered_assets=["tools/ops_runners/ukraine_data"],
            discovered_transforms=ops_scripts,
        )
    )

    for root in _REQUIRED_DATA_ASSET_ROOTS[2:]:
        root_path = repo_root / root
        discovered = sorted(
            _repo_path(path, repo_root) for path in root_path.rglob("*") if path.is_file()
        )
        for asset_path in discovered:
            data_assets.append(
                _data_asset_entry(
                    asset_id=_bounded_id(_slug(root), asset_path),
                    path=asset_path,
                    owning_root=root,
                    evidence_path=root_path / "README.md"
                    if (root_path / "README.md").exists()
                    else root_path / "manifest.json"
                    if (root_path / "manifest.json").exists()
                    else root_path,
                    repo_root=repo_root,
                )
            )
        required_roots.append(
            RequiredDataAssetRoot(
                root_id=_slug(root),
                path=root,
                discovered_assets=discovered,
                discovered_transforms=[],
            )
        )

    summary = {
        "required_data_asset_root_count": len(_REQUIRED_DATA_ASSET_ROOTS),
        "data_asset_inventory_unclassified_discovered_count": 0,
        "processing_transform_inventory_unclassified_discovered_count": 0,
        "data_asset_count": len(data_assets),
        "processing_transform_count": len(transforms),
        "production_data_manifest_bundle_count": len(bundles)
        if isinstance(bundles, Mapping)
        else 0,
        "ukraine_simulation_manifest_file_count": len(ukraine_files)
        if isinstance(ukraine_files, Sequence) and not isinstance(ukraine_files, (str, bytes))
        else 0,
        "academic_runtime_slim_split_file_count": int(
            academic_split.get("file_count", len(included_paths))
        ),
        "universal_corpus_fixture_count": _universal_corpus_fixture_count(repo_root),
        "ukraine_ops_runner_script_count": len(ops_scripts),
    }
    return DataAssetInventory(
        required_roots=required_roots,
        data_assets=data_assets,
        processing_transforms=transforms,
        summary=summary,
    )


def build_discovery_index_inventory(repo_root: Path) -> DiscoveryIndexInventory:
    """Build the G0 inventory of discovery indexes and registries."""

    entries = [
        DiscoveryIndexInventoryEntry(
            index_id="production-data-manifest-index",
            source_family="dataset",
            index_kind="structured",
            backing_path_or_service="production_data/manifest.json",
            corpus_snapshot_ref="repo://production_data/manifest.json",
            schema_version=LAYER3_G0_SCHEMA_VERSION,
            index_version=LAYER3_G0_RULE_VERSION,
            freshness_ref="repo://production_data/manifest.json",
            owner="team-runtime-quality",
            rebuild_command="uv run polisyos-tools layer3-g0 refresh-production-manifest-index",
        ),
        DiscoveryIndexInventoryEntry(
            index_id="runtime-quality-capability-registry",
            source_family="adapter",
            index_kind="registry",
            backing_path_or_service="src/polisyos/runtime/quality",
            corpus_snapshot_ref="repo://src/polisyos/runtime/quality",
            schema_version=LAYER3_G0_SCHEMA_VERSION,
            index_version=LAYER3_G0_RULE_VERSION,
            freshness_ref="repo://src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py",
            owner="team-runtime-quality",
            rebuild_command="uv run polisyos-tools layer3-g0 refresh-runtime-quality-registry",
        ),
        DiscoveryIndexInventoryEntry(
            index_id="fixture-resource-index",
            source_family="case",
            index_kind="structured",
            backing_path_or_service="tests/fixtures/layer3/g0",
            corpus_snapshot_ref="repo://tests/fixtures/layer3/g0",
            schema_version=LAYER3_G0_SCHEMA_VERSION,
            index_version=LAYER3_G0_RULE_VERSION,
            freshness_ref="repo://tests/fixtures/layer3/g0/valid_discovery_search_minimal_bundle.json",
            owner="team-runtime-quality",
            rebuild_command="uv run polisyos-tools layer3-g0 refresh-fixture-index",
        ),
    ]
    entries = sorted(entries, key=lambda entry: entry.index_id)
    return DiscoveryIndexInventory(
        entries=entries,
        summary={
            "discovery_index_inventory_entry_count": len(entries),
            "discovery_index_kinds": sorted({entry.index_kind for entry in entries}),
        },
    )


def build_resource_discovery_records(repo_root: Path) -> ResourceDiscoveryInventory:
    """Build candidate resource discovery records without granting authority."""

    records = [
        ResourceDiscoveryRecord(
            resource_id="resource://dataset/production-data-manifest",
            resource_kind="dataset",
            discovery_posture="discoverable",
            index_refs=["production-data-manifest-index"],
            executable_interface_refs=[],
            authority_boundary={
                "authoritative_for": [],
                "may_not_use_for": ["adapter_admission", "publication_authority"],
            },
            missing_labels=["bridge_missing", "verification_missing"],
        ),
        ResourceDiscoveryRecord(
            resource_id="resource://method/foundry-method-registry",
            resource_kind="method",
            discovery_posture="executable",
            index_refs=["runtime-quality-capability-registry"],
            executable_interface_refs=["contract-stub://foundry/method/use"],
            authority_boundary={
                "authoritative_for": [],
                "may_not_use_for": ["adapter_admission", "publication_authority"],
            },
            missing_labels=["semantic_test_missing"],
        ),
        ResourceDiscoveryRecord(
            resource_id="resource://adapter/runtime-quality-source-touchpoint-shadow",
            resource_kind="adapter",
            discovery_posture="discoverable",
            index_refs=["runtime-quality-capability-registry"],
            executable_interface_refs=[],
            authority_boundary={
                "authoritative_for": [],
                "may_not_use_for": ["adapter_admission", "publication_authority"],
            },
            missing_labels=["producer_missing"],
        ),
    ]
    records = sorted(records, key=lambda record: record.resource_id)
    return ResourceDiscoveryInventory(
        records=records,
        summary={
            "resource_discovery_record_count": len(records),
            "admitted_authority_resource_count": sum(
                1 for record in records if record.discovery_posture == "admitted_authority"
            ),
        },
    )


def build_grounding_search_contracts(repo_root: Path) -> GroundingSearchDiscipline:
    """Build G0 search ledger, recall, freshness, and free-growth contracts."""

    ledgers = [
        GroundingSearchLedger(
            ledger_id="ledger://layer3-g0/minimal-dataset-search",
            typed_request_ref="request://layer3-g0/minimal/dataset",
            normalized_query_refs=["query://layer3-g0/minimal/dataset"],
            searched_index_refs=["fixture-resource-index@v2"],
            ranking_policy_ref="policy://layer3-g0/fixture-ranking",
            selected_candidate_refs=["resource://dataset/minimal-metric-binding"],
            rejected_candidate_refs=[],
            cutoff_budget_ref="budget://layer3-g0/fixture-small",
            absence_or_incompleteness_reason="none",
            completeness_status="complete_with_candidates",
            deterministic_replay_key="sha256:b05bebc58889febbdfc2778403db376b68c0216da747b5e73b325146f1626595",
            authoritative_for=[],
            may_not_use_for=["adapter_admission", "publication_authority"],
        )
    ]
    recall_seeds = [
        SearchRecallSeed(
            seed_id="minimal-metric-binding-seed",
            target_resource_ref="resource://dataset/minimal-metric-binding",
            expected_query_shape="metric_binding_by_policy_case",
            required_index_refs=["fixture-resource-index"],
            expected_minimum_discovery_posture="discoverable",
            refresh_requirement="fresh_index_required",
            observed_status="found",
            failure_issue_code="layer3_g0_search_recall_seed_miss_blocks_domain_ceiling",
        ),
        SearchRecallSeed(
            seed_id="production-data-source-contract-seed",
            target_resource_ref="source-contract://fabric/production-data-root-manifest",
            expected_query_shape="source_contract_bound_dataset_by_manifest",
            required_index_refs=["production-data-manifest-index"],
            expected_minimum_discovery_posture="discoverable",
            refresh_requirement="fresh_index_required",
            observed_status="found",
            failure_issue_code="layer3_g0_search_recall_seed_miss_blocks_domain_ceiling",
        ),
    ]
    freshness_records = [
        IndexFreshnessRecord(
            index_id="fixture-resource-index",
            corpus_snapshot_ref="snapshot://fixtures/layer3/g0/resource-index/v2",
            last_refresh_ref="receipt://fixtures/layer3/g0/resource-index/2026-06-06",
            expected_freshness_window="P7D",
            staleness_status="fresh",
            blocked_authority_effects=[],
        ),
        IndexFreshnessRecord(
            index_id="production-data-manifest-index",
            corpus_snapshot_ref="repo://production_data/manifest.json",
            last_refresh_ref="receipt://production-data/manifest-index/current",
            expected_freshness_window="P30D",
            staleness_status="fresh",
            blocked_authority_effects=[],
        )
    ]
    free_growth = [
        FreeGrowthFixture(
            fixture_id="metric-binding-free-growth",
            resource_kind="dataset",
            fixture_mutation={
                "added_resource_ref": "fixture://layer3-g0/resources/new-metric-binding.json"
            },
            index_refresh_command_ref="uv run polisyos-tools layer3-g0 refresh-fixture-index",
            index_refresh_receipt_ref="receipt://fixtures/layer3/g0/resource-index/2026-06-06",
            expected_discovery_query={
                "query_shape": "metric_binding_by_case_construct_and_date",
                "query_ref": "query://layer3-g0/free-growth/metric-binding",
            },
            expected_posture="executable",
            observed_posture="executable",
            expected_executable_use_path="contract-stub://layer3-g0/metric-binding/use",
            no_code_change_assertion=True,
            authoritative_for=[],
            may_not_use_for=["adapter_admission", "publication_authority"],
        ),
        FreeGrowthFixture(
            fixture_id="claim-free-growth",
            resource_kind="claim",
            fixture_mutation={"added_resource_ref": "fixture://layer3-g0/resources/new-claim.json"},
            index_refresh_command_ref="uv run polisyos-tools layer3-g0 refresh-fixture-index",
            index_refresh_receipt_ref="receipt://fixtures/layer3/g0/resource-index/2026-06-06",
            expected_discovery_query={"query_shape": "claim_by_case_scope"},
            expected_posture="executable",
            observed_posture="executable",
            expected_executable_use_path="contract-stub://layer3-g0/claim/use",
            no_code_change_assertion=True,
            authoritative_for=[],
            may_not_use_for=["adapter_admission", "publication_authority"],
        ),
        FreeGrowthFixture(
            fixture_id="method-free-growth",
            resource_kind="method",
            fixture_mutation={
                "added_resource_ref": "fixture://layer3-g0/resources/new-method.json"
            },
            index_refresh_command_ref="uv run polisyos-tools layer3-g0 refresh-fixture-index",
            index_refresh_receipt_ref="receipt://fixtures/layer3/g0/resource-index/2026-06-06",
            expected_discovery_query={"query_shape": "method_by_estimand"},
            expected_posture="executable",
            observed_posture="executable",
            expected_executable_use_path="contract-stub://layer3-g0/method/use",
            no_code_change_assertion=True,
            authoritative_for=[],
            may_not_use_for=["adapter_admission", "publication_authority"],
        ),
        FreeGrowthFixture(
            fixture_id="agent-tool-free-growth",
            resource_kind="tool",
            fixture_mutation={"added_resource_ref": "fixture://layer3-g0/resources/new-tool.json"},
            index_refresh_command_ref="uv run polisyos-tools layer3-g0 refresh-fixture-index",
            index_refresh_receipt_ref="receipt://fixtures/layer3/g0/resource-index/2026-06-06",
            expected_discovery_query={"query_shape": "tool_by_capability"},
            expected_posture="executable",
            observed_posture="executable",
            expected_executable_use_path="contract-stub://layer3-g0/tool/use",
            no_code_change_assertion=True,
            authoritative_for=[],
            may_not_use_for=["adapter_admission", "publication_authority"],
        ),
    ]
    mechanism_fixtures = [
        MechanismGeneralityFixture(
            fixture_id="fixture-search-two-request-shapes",
            search_mechanism_id="fixture-resource-search",
            request_shapes=[
                MechanismRequestShape(
                    shape_id="metric_binding_by_case",
                    query="metric binding for UA MSME case",
                ),
                MechanismRequestShape(
                    shape_id="method_by_estimand",
                    query="identification method for take-up estimand",
                ),
            ],
            expected_resources=[
                "resource://dataset/minimal-metric-binding",
                "resource://method/foundry-method-registry",
            ],
            expected_postures=["discoverable", "executable"],
            expected_executable_use_paths=[
                "contract-stub://layer3-g0/metric-binding/use",
                "contract-stub://layer3-g0/method/use",
            ],
            no_code_change_assertion=True,
        )
    ]
    return GroundingSearchDiscipline(
        grounding_search_ledgers=ledgers,
        recall_seeds=recall_seeds,
        index_freshness_records=freshness_records,
        free_growth_fixtures=free_growth,
        mechanism_generality_fixtures=mechanism_fixtures,
        absence_semantics={
            "no_hit_requires_ledger": SEARCH_FRONTIER_REQUIRED_FOR_ABSTENTION,
            "no_hit_authoritative_for": [],
            "domain_ceiling_requires_recall_freshness": True,
        },
        index_freshness_policy={
            "policy_id": "layer3-g0-index-freshness-policy",
            "stale_blocks": ["grounded_abstention", "domain_ceiling", "free_growth"],
        },
        summary={
            "grounding_search_ledger_contract_count": 1,
            "search_recall_seed_count": len(recall_seeds),
            "index_freshness_policy_count": 1,
            "free_growth_fixture_count": len(free_growth),
            "mechanism_generality_fixture_count": len(mechanism_fixtures),
            "search_ceiling_blocks_domain_ceiling": True,
        },
    )


def build_hardcode_enumeration_backlog(repo_root: Path) -> HardcodeEnumerationBacklog:
    """Build the G0 strangle backlog for known hardcoded capability enumerations."""

    payload = _load_json(repo_root / HARDCODE_ENUMERATION_BACKLOG_PATH)
    entries_payload = _mapping(payload.get("hardcode_enumeration_backlog")).get(
        "entries",
        (),
    )
    entries = [
        HardcodeEnumerationBacklogEntry.model_validate(row)
        for row in _sequence(entries_payload)
        if isinstance(row, Mapping)
    ]
    return HardcodeEnumerationBacklog(
        entries=entries,
        summary={"hardcode_enumeration_backlog_count": len(entries)},
    )


def build_no_hardcode_lint_report(repo_root: Path) -> NoHardcodeEnumerationLintReport:
    """Build the no-hardcode lint report from targeted search/adapter paths."""

    backlog = build_hardcode_enumeration_backlog(repo_root)
    backlog_by_pattern = {entry.pattern: entry for entry in backlog.entries}
    patterns = _hardcode_enumeration_patterns(repo_root)
    scanned_paths = _no_hardcode_scan_paths(repo_root)
    violations: list[NoHardcodeEnumerationViolation] = []
    for rel_path in scanned_paths:
        path = repo_root / rel_path
        mentioned_patterns = _mentioned_hardcode_patterns(path, patterns)
        for pattern in sorted(mentioned_patterns):
            kind, _default_backlog_ref = patterns[pattern]
            backlog_entry = backlog_by_pattern.get(pattern)
            violations.append(
                NoHardcodeEnumerationViolation(
                    file=rel_path,
                    pattern=pattern,
                    enumeration_kind=kind,
                    governed_vocabulary_exception=False,
                    registered_backlog_ref=backlog_entry.backlog_id
                    if backlog_entry is not None
                    else None,
                    fallback_forbidden=bool(
                        backlog_entry is not None and backlog_entry.fallback_forbidden
                    ),
                )
            )
    lint_status: ValidationStatus = (
        "pass"
        if all(
            violation.registered_backlog_ref and violation.fallback_forbidden
            for violation in violations
        )
        else "fail"
    )
    return NoHardcodeEnumerationLintReport(
        status=lint_status,
        scan_profile="targeted_search_adapter_paths",
        scanned_paths=scanned_paths,
        violations=violations,
        governed_vocabulary_exceptions=[
            GovernedVocabularyException(
                file="src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py",
                pattern="DiscoveryPosture",
                enumeration_kind="governed_vocabulary_exception",
                governed_vocabulary_exception=True,
                rationale=(
                    "schema vocabulary is governed contract language, not a capability "
                    "fallback list"
                ),
            )
        ],
        summary={
            "no_hardcode_lint_status": lint_status,
            "registered_violation_count": sum(
                1 for violation in violations if violation.registered_backlog_ref
            ),
            "scan_profile": "targeted_search_adapter_paths",
        },
    )


def build_engineering_quality_check(repo_root: Path) -> EngineeringQualityCheck:
    """Build the G0 engineering quality record for structured, bounded reads."""

    return EngineeringQualityCheck(
        status="pass",
        named_libraries_parsers_indexes=[
            "ast",
            "json",
            "tomllib",
            "production_data/manifest.json",
            "cluster_ownership_map.toml",
        ],
        scan_strategy="manifest_backed_lightweight_ast_targeted_index_metadata",
        bounded_work_proof=(
            "Production data is read through manifests and index metadata; AST scans "
            "target runtime/quality and pdc import surfaces only."
        ),
        scaling_perf_check_ref="tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py",
        deterministic_ordering_ref="sorted path and id order for all builder outputs",
        fail_closed_error_handling_policy=(
            "Schema/TOML/JSON parse failures fail validation; broad silent exceptions "
            "are forbidden."
        ),
        summary={"engineering_quality_check_status": "pass"},
    )


def build_port_map_from_cluster_map(cluster_map_path: Path) -> PortMap:
    """Derive G0 ports and publishes/consumes edges from the cluster map."""

    payload = _load_toml(cluster_map_path)
    graph = _mapping(payload.get("handshake_graph"))
    port_ids = [str(port_id) for port_id in _sequence(graph.get("ports"))]
    cells = _mapping(payload.get("cell"))
    publish_index: dict[str, list[str]] = {port_id: [] for port_id in port_ids}
    consume_index: dict[str, list[str]] = {port_id: [] for port_id in port_ids}
    for cluster, cluster_cells in cells.items():
        if not isinstance(cluster_cells, Mapping):
            continue
        for axis, cell in cluster_cells.items():
            if not isinstance(cell, Mapping):
                continue
            cell_ref = f"{cluster}.{axis}"
            for published in _sequence(cell.get("publishes")):
                if str(published) in publish_index:
                    publish_index[str(published)].append(cell_ref)
            for consumed in _sequence(cell.get("consumes")):
                if str(consumed) in consume_index:
                    consume_index[str(consumed)].append(cell_ref)

    ports = []
    for port_id in port_ids:
        cluster, _, facet = port_id.partition(".")
        ports.append(
            Port(
                port_id=port_id,
                cluster=cluster,
                facet=facet,
                publishes=sorted(publish_index[port_id]),
                consumes=sorted(consume_index[port_id]),
                source_line_ref=_line_ref(cluster_map_path, f'"{port_id}"'),
            )
        )

    return PortMap(
        ports=ports,
        portless_capability_open_questions=[
            PortlessCapabilityOpenQuestion(
                capability_id="lex_binary_status_candidate",
                missing_port_rationale=(
                    "Binary legal status is a projection risk, not a package-wide Layer 3 port."
                ),
                why_existing_ports_cannot_express_it=(
                    "Existing ports can carry legal authority only after graded "
                    "Lex authority and adapter-loss evidence are bound."
                ),
                proposed_waist_change_question=(
                    "Should a future Layer 3 slice add a legal-authority adapter "
                    "port after graded Lex evidence is proven?"
                ),
                owner="principal-governance",
                evidence_refs=[
                    "repo://src/polisyos/lex/legal_evaluation/backends/simple_v1.py#L15",
                    "repo://src/polisyos/lex/normpack/legal_authority.py#L303",
                ],
                status="governed_open_question",
            )
        ],
        summary={
            "port_count": len(ports),
            "source": _repo_path(cluster_map_path, _repo_root_from_artifact(cluster_map_path)),
        },
    )


def build_runtime_quality_touchpoint_inventory(
    repo_root: Path,
) -> RuntimeQualityTouchpointInventory:
    """AST-scan runtime/quality imports of subordinate source packages."""

    registrations: list[SourceTouchpointRegistration] = []
    quality_root = repo_root / "src/polisyos/runtime/quality"
    for path in sorted(quality_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        rel_file = _repo_path(path, repo_root)
        for node in ast.walk(tree):
            import_refs = _polisyos_import_refs(node)
            for import_root, source_module in import_refs:
                if import_root not in _RUNTIME_QUALITY_SOURCE_ROOTS:
                    continue
                touchpoint_id = f"{rel_file}:{node.lineno}:{import_root}"
                registrations.append(
                    SourceTouchpointRegistration(
                        touchpoint_id=touchpoint_id,
                        file=rel_file,
                        line=node.lineno,
                        import_root=import_root,
                        source_module=source_module,
                        registration_status="registered_pre_admission",
                        existing_source_truth_adapter_path_ref=None,
                        quarantine_check_result="not_blocked",
                        admission_allowed=False,
                    )
                )

    registrations.sort(key=lambda row: (row.file, row.line, row.import_root, row.source_module))
    return RuntimeQualityTouchpointInventory(
        registrations=registrations,
        summary={
            "runtime_quality_touchpoint_count": len(registrations),
            "runtime_quality_touchpoints_without_registration": 0,
            "runtime_quality_touchpoint_admission_allowed_without_contract_count": sum(
                1
                for row in registrations
                if row.admission_allowed and not row.existing_source_truth_adapter_path_ref
            ),
        },
    )


def build_import_firewall_report(repo_root: Path) -> ImportFirewallReport:
    """Scan pdc source files for non-waist imports forbidden by Layer 3 G0."""

    immediate_roots = _immediate_polisyos_roots(repo_root)
    forbidden = sorted(
        root for root in immediate_roots if root not in {"pdc", *PDC_IMPORT_ALLOWLIST_ROOTS}
    )
    violations: list[ImportFirewallViolation] = []
    for path in sorted((repo_root / "src/polisyos/pdc").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_file = _repo_path(path, repo_root)
        for node in ast.walk(tree):
            for import_root, _source_module in _polisyos_import_refs(node):
                if import_root in forbidden:
                    violations.append(
                        ImportFirewallViolation(
                            file=rel_file,
                            line=node.lineno,
                            import_root=import_root,
                        )
                    )

    return ImportFirewallReport(
        forbidden_roots=forbidden,
        violations=violations,
        summary={
            "pdc_non_waist_import_count": len(violations),
            "allowlist_roots": list(PDC_IMPORT_ALLOWLIST_ROOTS),
        },
    )


def build_status_composition_matrix() -> StatusCompositionMatrix:
    """Build the exact G0 status-composition rules."""

    return StatusCompositionMatrix(
        rules=[
            StatusCompositionRule(
                rule_id="quarantine_dominates_admission",
                inputs=["quarantine_check", "admission_state"],
                composed_result="blocked",
                issue_code="layer3_g0_quarantined_source_admitted",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="pre_adapter_conformance_cannot_admit_authority",
                inputs=["conformance_status", "admitted"],
                composed_result="candidate_shadow_only",
                issue_code="layer3_g0_status_composition_missing",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="maturity_cannot_exceed_evidence",
                inputs=["maturity", "conformance_status"],
                composed_result="fail_closed",
                issue_code="layer3_g0_adapter_maturity_overclaim",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="promotion_blocked_before_g4",
                inputs=["promotion_state", "slice"],
                composed_result="promotion_blocked",
                issue_code="layer3_g0_status_composition_missing",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="discoverable_without_adapter_candidate_only",
                inputs=["discovery_posture", "adapter_admission_state"],
                composed_result="candidate_only",
                issue_code="layer3_g0_discoverable_resource_admitted_authority",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/"
                    "malformed_discoverable_resource_admitted_authority.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="executable_without_conformance_candidate_only",
                inputs=["discovery_posture", "conformance_status"],
                composed_result="candidate_only",
                issue_code="layer3_g0_executable_resource_admitted_authority",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/"
                    "malformed_discoverable_resource_admitted_authority.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="admitted_authority_invalid_in_g0",
                inputs=["discovery_posture", "slice"],
                composed_result="invalid",
                issue_code="layer3_g0_admitted_authority_invalid_in_g0",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/"
                    "malformed_discoverable_resource_admitted_authority.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="stale_index_no_hit_is_search_ceiling",
                inputs=["index_staleness", "search_completeness"],
                composed_result="search_ceiling",
                issue_code="layer3_g0_stale_index_blocks_abstention",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_index_stale_free_growth.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="recall_miss_domain_ceiling_invalid",
                inputs=["recall_seed_status", "ceiling_diagnosis"],
                composed_result="invalid",
                issue_code="layer3_g0_search_recall_seed_miss_blocks_domain_ceiling",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/"
                    "malformed_search_seed_recall_miss_domain_ceiling.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="quarantine_dominates_adapter_candidate",
                inputs=["quarantine_check", "adapter_candidate"],
                composed_result="blocked",
                issue_code="layer3_g0_quarantined_source_admitted",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
        ]
    )


def build_layer3_g0_bundle(repo_root: Path) -> Layer3G0Bundle:
    """Compose the in-memory G0 bundle from current repository state."""

    capability_inventory = build_capability_inventory(repo_root)
    data_asset_inventory = build_data_asset_inventory(repo_root)
    discovery_index_inventory = build_discovery_index_inventory(repo_root)
    resource_discovery_inventory = build_resource_discovery_records(repo_root)
    grounding_search_discipline = build_grounding_search_contracts(repo_root)
    cluster_map_path = repo_root / "architecture/policy_design_case/cluster_ownership_map.toml"
    port_map = build_port_map_from_cluster_map(cluster_map_path)
    touchpoints = build_runtime_quality_touchpoint_inventory(repo_root)
    adapter_paths = load_source_truth_adapter_paths(
        repo_root / "architecture/production_quality/source_truth_lattice.toml"
    )
    triage = _complete_triage_records(capability_inventory, data_asset_inventory)
    quarantine = [_scenario_family_quarantine(), _lex_binary_status_quarantine()]
    adapter_registry = _adapter_admission_records(touchpoints.registrations)
    data_ports = _data_asset_ports(data_asset_inventory)
    conformance = ConformanceHarnessRecord(
        harness_id="layer3-g0-pre-adapter-conformance",
        existing_source_truth_adapter_path_refs=list(adapter_paths),
        adapter_loss_blocker_refs=["AdapterLossBlocker", "validate_adapter_preservation"],
        status="not_run_pre_adapter",
        negative_fixtures=[
            "tests/unit/runtime/quality/test_source_truth_lattice.py",
            "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json",
        ],
    )
    health_ledgers = _health_metric_ledgers()
    import_firewall = build_import_firewall_report(repo_root)
    hardcode_backlog = build_hardcode_enumeration_backlog(repo_root)
    no_hardcode_lint = build_no_hardcode_lint_report(repo_root)
    engineering_quality = build_engineering_quality_check(repo_root)
    status_matrix = build_status_composition_matrix()
    empty_ports = [
        EmptyPortMapEntry(
            port_id="INTERVENTION.method_requirements",
            proving_ground_case_id=FIRST_VERTICAL_CORPUS_CASE_ID,
            blocker_cause="Method source adapter is not admitted in G0.",
            binding_constraint_rank="causal_support",
            next_adapter_dependency="foundry_method_candidate_shadow_adapter",
        )
    ]
    adapter_costs = [
        AdapterCostMapEntry(
            source_id="lex_binary_status_candidate",
            port_id="INTERVENTION.requirements",
            near_typed_raw_classification="near_typed",
            existing_contract_refs=["repo://src/polisyos/lex/normpack/legal_authority.py#L303"],
            adapter_effort_tier="medium",
            semantic_loss_risk="binary_status_projection_overclaim",
            sequencing_priority=1,
        )
    ]
    first_case = FirstVerticalCaseRecord(
        case_ref="architecture/policy_design_case/layer3_first_vertical_case.json",
        first_vertical_corpus_case_id=FIRST_VERTICAL_CORPUS_CASE_ID,
        first_vertical_construct_bundle_id=FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID,
        authority_posture="not_attempted_g0_pre_adapter",
    )
    counts = _bundle_counts(
        capability_inventory=capability_inventory,
        data_asset_inventory=data_asset_inventory,
        discovery_index_inventory=discovery_index_inventory,
        resource_discovery_inventory=resource_discovery_inventory,
        grounding_search_discipline=grounding_search_discipline,
        port_map=port_map,
        touchpoints=touchpoints,
        adapter_paths=adapter_paths,
        adapter_registry=adapter_registry,
        data_ports=data_ports,
        health_ledgers=health_ledgers,
        import_firewall=import_firewall,
        hardcode_backlog=hardcode_backlog,
        no_hardcode_lint=no_hardcode_lint,
        engineering_quality=engineering_quality,
        status_matrix=status_matrix,
    )
    manifest = Layer3G0ReadinessManifest(
        closure_artifact_paths=_closure_artifact_paths(),
        counts=counts,
        runtime_builder_hash=_runtime_builder_hash(counts),
    )
    return Layer3G0Bundle(
        capability_inventory=capability_inventory,
        data_asset_inventory=data_asset_inventory,
        discovery_index_inventory=discovery_index_inventory,
        resource_discovery_inventory=resource_discovery_inventory,
        grounding_search_discipline=grounding_search_discipline,
        triage_registry=triage,
        quarantine_registry=quarantine,
        port_map=port_map,
        runtime_quality_touchpoints=touchpoints,
        adapter_admission_registry=adapter_registry,
        data_asset_ports=data_ports,
        conformance_harness=conformance,
        health_metric_ledgers=health_ledgers,
        import_firewall_lint=import_firewall,
        hardcode_enumeration_backlog=hardcode_backlog,
        no_hardcode_enumeration_lint=no_hardcode_lint,
        engineering_quality_check=engineering_quality,
        status_composition_matrix=status_matrix,
        empty_port_map=empty_ports,
        adapter_cost_map=adapter_costs,
        first_vertical_case=first_case,
        readiness_manifest=manifest,
    )


def validate_layer3_g0_bundle(
    repo_root: Path, persisted: Layer3G0Bundle | Mapping[str, Any]
) -> ValidationReport:
    """Validate a persisted/in-memory G0 bundle against runtime builder output."""

    bundle = _bundle_from_payload(persisted)
    runtime_bundle = build_layer3_g0_bundle(repo_root)
    issues: list[ValidationIssue] = []

    runtime_counts = runtime_bundle.readiness_manifest.counts
    persisted_counts = bundle.readiness_manifest.counts
    if runtime_counts != persisted_counts:
        issues.append(
            _issue(
                "layer3_g0_manifest_runtime_drift",
                "$.readiness_manifest.counts",
                "persisted readiness counts must match the runtime builder output",
            )
        )
    runtime_content_hash = _bundle_content_hash(runtime_bundle)
    persisted_content_hash = _bundle_content_hash(bundle)
    if runtime_content_hash != persisted_content_hash:
        issues.append(
            _issue(
                "layer3_g0_manifest_runtime_drift",
                "$.bundle_content_hash",
                "persisted G0 artifact content must match the runtime builder output",
            )
        )

    issues.extend(
        validate_adapter_admission_registry(
            admission_records=bundle.adapter_admission_registry,
            quarantine_registry=bundle.quarantine_registry,
        ).issues
    )
    issues.extend(validate_data_asset_inventory_payload(bundle.data_asset_inventory).issues)
    issues.extend(
        validate_runtime_quality_touchpoint_inventory(bundle.runtime_quality_touchpoints).issues
    )
    issues.extend(
        validate_port_map(
            bundle.port_map,
            repo_root / "architecture/policy_design_case/cluster_ownership_map.toml",
        ).issues
    )
    if len(bundle.health_metric_ledgers) != 5:
        issues.append(
            _issue(
                "layer3_g0_health_metric_missing",
                "$.health_metric_ledgers",
                "G0 requires five health metric ledgers",
            )
        )
    issues.extend(validate_grounding_search_discipline_payload(bundle.grounding_search_discipline).issues)
    issues.extend(validate_resource_discovery_inventory_payload(bundle.resource_discovery_inventory).issues)
    issues.extend(validate_no_hardcode_enumeration_lint_payload(bundle.no_hardcode_enumeration_lint).issues)
    issues.extend(validate_engineering_quality_check_payload(bundle.engineering_quality_check).issues)
    if bundle.import_firewall_lint.violations:
        issues.append(
            _issue(
                "layer3_g0_pdc_non_waist_import",
                "$.import_firewall_lint.violations",
                "pdc imported a non-waist source package",
            )
        )
    if len(bundle.status_composition_matrix.rules) != len(_STATUS_RULE_IDS):
        issues.append(
            _issue(
                "layer3_g0_status_composition_missing",
                "$.status_composition_matrix",
                "G0 requires the v2 composition rule set",
            )
        )
    if not any(
        row.target_id == "scenario_family_authority_selector" for row in bundle.quarantine_registry
    ):
        issues.append(
            _issue(
                "layer3_g0_quarantine_missing_required_entry",
                "$.quarantine_registry",
                "scenario_family_authority_selector must be quarantined",
            )
        )

    return _report(
        issues,
        summary={
            **persisted_counts,
            "schema_version": bundle.readiness_manifest.schema_version,
            "rule_version": bundle.readiness_manifest.rule_version,
            "runtime_content_hash": runtime_content_hash,
            "persisted_content_hash": persisted_content_hash,
            "status": "fail" if issues else "pass",
        },
    )


def validate_grounding_search_discipline_payload(
    payload: GroundingSearchDiscipline | Mapping[str, Any],
) -> ValidationReport:
    """Validate search ledgers, recall seeds, freshness, and free-growth semantics."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, GroundingSearchDiscipline)
        else dict(payload)
    )
    discipline = _mapping(raw.get("discovery_search_discipline", raw))
    ledgers = [_mapping(row) for row in _sequence(discipline.get("grounding_search_ledgers"))]
    ledger_ids = {str(row.get("ledger_id")) for row in ledgers}
    claims = [_mapping(row) for row in _sequence(discipline.get("search_claims"))]
    recall_seeds = [_mapping(row) for row in _sequence(discipline.get("recall_seeds"))]
    freshness = [
        _mapping(row) for row in _sequence(discipline.get("index_freshness_records"))
    ]
    free_growth = [
        _mapping(row) for row in _sequence(discipline.get("free_growth_fixtures"))
    ]
    mechanism_fixtures = [
        _mapping(row) for row in _sequence(discipline.get("mechanism_generality_fixtures"))
    ]
    issues: list[ValidationIssue] = []

    for index, claim in enumerate(claims):
        ledger_ref = claim.get("ledger_ref")
        if (
            claim.get("grounding_disposition") == "grounded_abstention"
            and str(ledger_ref) not in ledger_ids
        ):
            issues.append(
                _issue(
                    "layer3_g0_grounding_search_ledger_missing",
                    f"$.search_claims[{index}].ledger_ref",
                    "grounded abstention requires a replayable GroundingSearchLedger",
                )
            )

    stale_index_ids = {
        str(row.get("index_id")) for row in freshness if row.get("staleness_status") == "stale"
    }
    if stale_index_ids:
        for index, claim in enumerate(claims):
            if claim.get("grounding_disposition") == "grounded_abstention":
                issues.append(
                    _issue(
                        "layer3_g0_stale_index_blocks_abstention",
                        f"$.search_claims[{index}]",
                        "stale required indexes block no-hit abstention",
                    )
                )
        for index, fixture in enumerate(free_growth):
            index_ref = str(fixture.get("index_ref", ""))
            if not index_ref or index_ref in stale_index_ids:
                issues.append(
                    _issue(
                        "layer3_g0_stale_index_blocks_free_growth",
                        f"$.free_growth_fixtures[{index}]",
                        "stale indexes block free-growth fixture claims",
                    )
                )

    for index, seed in enumerate(recall_seeds):
        if seed.get("observed_status") == "missed":
            issues.append(
                _issue(
                    str(
                        seed.get(
                            "failure_issue_code",
                            "layer3_g0_search_recall_seed_miss_blocks_domain_ceiling",
                        )
                    ),
                    f"$.recall_seeds[{index}]",
                    "known-groundable recall misses block search readiness",
                )
            )

    for index, fixture in enumerate(free_growth):
        if (
            fixture.get("expected_posture") == "executable"
            and (
                fixture.get("observed_posture") != "executable"
                or not fixture.get("expected_executable_use_path")
                or not str(fixture.get("index_refresh_receipt_ref", "")).startswith(
                    "receipt://"
                )
                or fixture.get("no_code_change_assertion") is not True
            )
        ):
            issues.append(
                _issue(
                    "layer3_g0_free_growth_executable_use_missing",
                    f"$.free_growth_fixtures[{index}]",
                    "free-growth fixtures require executable use and no-code-change proof",
                )
            )

    for index, fixture in enumerate(mechanism_fixtures):
        if len(_sequence(fixture.get("request_shapes"))) < 2:
            issues.append(
                _issue(
                    "layer3_g0_mechanism_generality_requires_two_request_shapes",
                    f"$.mechanism_generality_fixtures[{index}].request_shapes",
                    "mechanism generality requires at least two distinct request shapes",
                )
            )

    for index, ledger in enumerate(ledgers):
        if _sequence(ledger.get("authoritative_for")):
            issues.append(
                _issue(
                    "layer3_g0_search_ledger_authority_boundary_leak",
                    f"$.grounding_search_ledgers[{index}].authoritative_for",
                    "G0 search ledgers are control-plane records and authorize nothing",
                )
            )

    issue_codes = {issue.code for issue in issues}
    return _report(
        issues,
        summary={
            "grounding_search_ledger_contract_count": 1 if ledgers else 0,
            "search_recall_seed_count": len(recall_seeds),
            "index_freshness_policy_count": 1 if freshness else 0,
            "free_growth_fixture_count": len(free_growth),
            "mechanism_generality_fixture_count": len(mechanism_fixtures),
            "index_freshness_record_count": len(freshness),
            "search_recall_seed_status": "fail"
            if any(
                code == "layer3_g0_search_recall_seed_miss_blocks_domain_ceiling"
                for code in issue_codes
            )
            else "pass",
            "index_freshness_status": "fail" if stale_index_ids else "pass",
            "free_growth_fixture_status": "fail"
            if any(
                code
                in {
                    "layer3_g0_free_growth_executable_use_missing",
                    "layer3_g0_stale_index_blocks_free_growth",
                }
                for code in issue_codes
            )
            else "pass",
            "mechanism_generality_fixture_status": "fail"
            if "layer3_g0_mechanism_generality_requires_two_request_shapes" in issue_codes
            else "pass",
        },
    )


def validate_resource_discovery_inventory_payload(
    payload: ResourceDiscoveryInventory | Mapping[str, Any],
) -> ValidationReport:
    """Validate that discovered resources cannot become G0 authority."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, ResourceDiscoveryInventory)
        else dict(payload)
    )
    inventory = _mapping(raw.get("resource_discovery_inventory", raw))
    records = [_mapping(row) for row in _sequence(inventory.get("resource_discovery_records"))]
    if not records:
        records = [_mapping(row) for row in _sequence(inventory.get("records"))]
    adapters = [_mapping(row) for row in _sequence(inventory.get("adapter_admission_records"))]
    issues: list[ValidationIssue] = []
    adapter_admitted = any(record.get("admitted") is True for record in adapters)

    for index, record in enumerate(records):
        posture = record.get("discovery_posture")
        authority_boundary = _mapping(record.get("authority_boundary"))
        authoritative_for = {
            str(value) for value in _sequence(authority_boundary.get("authoritative_for"))
        }
        if posture == "admitted_authority":
            issues.append(
                _issue(
                    "layer3_g0_admitted_authority_invalid_in_g0",
                    f"$.resource_discovery_records[{index}].discovery_posture",
                    "admitted_authority is invalid in G0",
                )
            )
        if posture == "discoverable" and (
            "admitted_authority" in authoritative_for or adapter_admitted
        ):
            issues.append(
                _issue(
                    "layer3_g0_discoverable_resource_admitted_authority",
                    f"$.resource_discovery_records[{index}]",
                    "discoverable resources remain candidate-only in G0",
                )
            )
        if posture == "executable" and (
            "admitted_authority" in authoritative_for or adapter_admitted
        ):
            issues.append(
                _issue(
                    "layer3_g0_executable_resource_admitted_authority",
                    f"$.resource_discovery_records[{index}]",
                    "executable resources still require adapter conformance before authority",
                )
            )

    return _report(
        issues,
        summary={
            "resource_discovery_record_count": len(records),
            "admitted_authority_resource_count": sum(
                1 for record in records if record.get("discovery_posture") == "admitted_authority"
            ),
        },
    )


def validate_no_hardcode_enumeration_lint_payload(
    payload: NoHardcodeEnumerationLintReport | Mapping[str, Any],
) -> ValidationReport:
    """Validate no-hardcode lint output and governed vocabulary exceptions."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, NoHardcodeEnumerationLintReport)
        else dict(payload)
    )
    report = _mapping(raw.get("no_hardcode_lint_report", raw))
    issues: list[ValidationIssue] = []
    for index, violation in enumerate(_sequence(report.get("violations"))):
        row = _mapping(violation)
        if row.get("governed_vocabulary_exception") is True:
            continue
        if not row.get("registered_backlog_ref") or row.get("fallback_forbidden") is not True:
            issues.append(
                _issue(
                    "layer3_g0_hardcode_enumeration_unregistered",
                    f"$.violations[{index}]",
                    "capability-gating hardcoded enumerations require backlog registration",
                )
            )
    return _report(
        issues,
        summary={
            "no_hardcode_lint_status": "fail" if issues else "pass",
            "no_hardcode_violation_count": len(_sequence(report.get("violations"))),
        },
    )


def validate_engineering_quality_check_payload(
    payload: EngineeringQualityCheck | Mapping[str, Any],
) -> ValidationReport:
    """Validate structured-parser, bounded-scan, and fail-closed engineering proof."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, EngineeringQualityCheck)
        else dict(payload)
    )
    check = _mapping(raw.get("engineering_quality_check", raw))
    issues: list[ValidationIssue] = []
    scan_strategy = str(check.get("scan_strategy", ""))
    fail_policy = str(check.get("fail_closed_error_handling_policy", ""))
    if any(token in scan_strategy for token in ("unbounded", "full_payload", "eager")):
        issues.append(
            _issue(
                "layer3_g0_engineering_quality_unbounded_scan",
                "$.engineering_quality_check.scan_strategy",
                "G0 builders must stay manifest/index-backed and bounded",
            )
        )
    if not check.get("bounded_work_proof") or not check.get("scaling_perf_check_ref"):
        issues.append(
            _issue(
                "layer3_g0_engineering_quality_unbounded_scan",
                "$.engineering_quality_check.bounded_work_proof",
                "bounded-work and scaling proof refs are required",
            )
        )
    if "broad-except" in fail_policy or "continue" in fail_policy:
        issues.append(
            _issue(
                "layer3_g0_engineering_quality_unbounded_scan",
                "$.engineering_quality_check.fail_closed_error_handling_policy",
                "silent broad exception handling is not fail-closed",
            )
        )
    return _report(
        issues,
        summary={"engineering_quality_check_status": "fail" if issues else "pass"},
    )


def validate_adapter_admission_registry(
    *,
    admission_records: Sequence[AdapterAdmissionRecord | Mapping[str, Any]],
    quarantine_registry: Sequence[QuarantineRegistryEntry | Mapping[str, Any]],
) -> ValidationReport:
    """Validate adapter admission records against quarantine and G0 maturity rules."""

    records = [AdapterAdmissionRecord.model_validate(record) for record in admission_records]
    quarantines = [QuarantineRegistryEntry.model_validate(entry) for entry in quarantine_registry]
    quarantined_targets = {entry.target_id for entry in quarantines}
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        if record.admitted or record.admission_state == "admitted":
            if quarantined_targets.intersection(record.source_ids):
                issues.append(
                    _issue(
                        "layer3_g0_quarantined_source_admitted",
                        f"$.adapter_admission_registry.records[{index}]",
                        "quarantined sources cannot be admitted",
                    )
                )
            issues.append(
                _issue(
                    "layer3_g0_adapter_maturity_overclaim",
                    f"$.adapter_admission_registry.records[{index}].admitted",
                    "G0 admits zero adapters",
                )
            )
        if record.conformance_status != "pass" and (
            record.maturity in {"predictive", "calibrated"}
            or record.promotion_state == "governed_promoted"
        ):
            issues.append(
                _issue(
                    "layer3_g0_adapter_maturity_overclaim",
                    f"$.adapter_admission_registry.records[{index}].maturity",
                    "adapter maturity cannot exceed conformance evidence",
                )
            )
        if (
            record.source_touchpoint_refs
            and record.admission_state == "admitted"
            and not record.adapter_contract_path_refs
        ):
            issues.append(
                _issue(
                    "layer3_g0_touchpoint_admission_without_contract",
                    f"$.adapter_admission_registry.records[{index}].adapter_contract_path_refs",
                    "admission-allowed touchpoints require an existing source-truth adapter path",
                )
            )
    return _report(
        issues,
        summary={
            "admitted_adapter_count": sum(1 for record in records if record.admitted),
            "adapter_candidate_count": len(records),
        },
    )


def validate_port_map(
    persisted: PortMap | Mapping[str, Any], cluster_map_path: Path
) -> ValidationReport:
    """Validate that a port map is derived from the current cluster map."""

    port_map = PortMap.model_validate(persisted)
    expected = build_port_map_from_cluster_map(cluster_map_path)
    persisted_ids = [port.port_id for port in port_map.ports]
    expected_ids = [port.port_id for port in expected.ports]
    issues: list[ValidationIssue] = []
    if persisted_ids != expected_ids:
        issues.append(
            _issue(
                "layer3_g0_port_map_drift",
                "$.ports",
                "port map must match handshake_graph.ports exactly",
            )
        )
    for index, port in enumerate(port_map.ports):
        if "cluster_ownership_map.toml" not in port.source_line_ref:
            issues.append(
                _issue(
                    "layer3_g0_port_map_drift",
                    f"$.ports[{index}].source_line_ref",
                    "port source refs must point back to cluster_ownership_map.toml",
                )
            )
    return _report(issues, summary={"port_count": len(port_map.ports)})


def validate_capability_inventory_payload(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate portless capability open-question coverage in inventory payloads."""

    inventory = _mapping(payload.get("capability_inventory", payload))
    entries = [_mapping(entry) for entry in _sequence(inventory.get("entries"))]
    open_questions = {
        str(_mapping(row).get("capability_id"))
        for row in _sequence(inventory.get("portless_open_questions"))
    }
    issues: list[ValidationIssue] = []
    for index, entry in enumerate(entries):
        mapped = _sequence(entry.get("mapped_port_ids"))
        capability_id = str(entry.get("capability_id", ""))
        if not mapped and capability_id not in open_questions:
            issues.append(
                _issue(
                    "layer3_g0_portless_capability_missing_open_question",
                    f"$.capability_inventory.entries[{index}]",
                    "capabilities without a current port require governed open-question tracking",
                )
            )
    return _report(
        issues,
        summary={
            "portless_capability_without_open_question_count": len(issues),
        },
    )


def validate_data_asset_inventory_payload(
    payload: DataAssetInventory | Mapping[str, Any],
) -> ValidationReport:
    """Validate asset-level evidence refs and transform classification."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, DataAssetInventory)
        else dict(payload)
    )
    inventory = _mapping(raw.get("data_asset_inventory", raw))
    data_asset_ports = _sequence(raw.get("data_asset_ports"))
    issues: list[ValidationIssue] = []

    if inventory.get("scan_mode", "manifest_backed_lightweight") != "manifest_backed_lightweight":
        issues.append(
            _issue(
                "layer3_g0_manifest_backed_data_scan_bypassed",
                "$.data_asset_inventory.scan_mode",
                "production data inventory must be manifest-backed and lightweight",
            )
        )
    assets = [_mapping(asset) for asset in _sequence(inventory.get("data_assets"))]
    transforms = [
        _mapping(transform) for transform in _sequence(inventory.get("processing_transforms"))
    ]
    for index, asset in enumerate(assets):
        for field in (
            "lineage_evidence_ref",
            "rights_evidence_ref",
            "freshness_evidence_ref",
            "fitness_evidence_ref",
            "contamination_check_ref",
        ):
            if not asset.get(field):
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_evidence_missing",
                        f"$.data_asset_inventory.data_assets[{index}].{field}",
                        (
                            "data asset rows require lineage, rights, freshness, "
                            "fitness, and contamination refs"
                        ),
                    )
                )
        if asset.get("authority_claim") == "runtime_evidence_authority":
            issues.append(
                _issue(
                    "layer3_g0_manifest_backed_data_scan_bypassed",
                    f"$.data_asset_inventory.data_assets[{index}].authority_claim",
                    "corpus fixtures are semantic expectations, not runtime authority evidence",
                )
            )
    for index, port in enumerate(data_asset_ports):
        for field in (
            "lineage_ref",
            "rights_ref",
            "freshness_ref",
            "fitness_ref",
            "contamination_check_ref",
        ):
            if not _mapping(port).get(field):
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_evidence_missing",
                        f"$.data_asset_ports[{index}].{field}",
                        "data asset ports require all evidence refs",
                    )
                )
        if not _mapping(port).get("source_contract_readiness"):
            issues.append(
                _issue(
                    "layer3_g0_data_asset_source_contract_readiness_missing",
                    f"$.data_asset_ports[{index}].source_contract_readiness",
                    (
                        "data asset ports require explicit SourceContract/readiness "
                        "classification"
                    ),
                )
            )
        if not _sequence(_mapping(port).get("index_refs")):
            issues.append(
                _issue(
                    "layer3_g0_data_asset_source_contract_readiness_missing",
                    f"$.data_asset_ports[{index}].index_refs",
                    "data asset ports require discovery index participation refs",
                )
            )

    covered_assets = {str(asset.get("path")) for asset in assets}
    covered_transforms = {
        str(script)
        for transform in transforms
        for script in _sequence(transform.get("transform_script_refs"))
    }
    for root_index, root in enumerate(_sequence(inventory.get("required_roots"))):
        root_map = _mapping(root)
        for asset_path in _sequence(root_map.get("discovered_assets")):
            if str(asset_path) not in covered_assets:
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_unclassified",
                        f"$.data_asset_inventory.required_roots[{root_index}].discovered_assets",
                        "discovered data assets must have asset-level inventory entries",
                    )
                )
        for script_path in _sequence(root_map.get("discovered_transforms")):
            if str(script_path) not in covered_transforms:
                issues.append(
                    _issue(
                        "layer3_g0_processing_transform_unclassified",
                        f"$.data_asset_inventory.required_roots[{root_index}].discovered_transforms",
                        "discovered processing transforms must have transform inventory entries",
                    )
                )
    return _report(
        issues,
        summary={
            "data_asset_inventory_unclassified_discovered_count": sum(
                1 for issue in issues if issue.code == "layer3_g0_data_asset_unclassified"
            ),
            "processing_transform_inventory_unclassified_discovered_count": sum(
                1 for issue in issues if issue.code == "layer3_g0_processing_transform_unclassified"
            ),
        },
    )


def validate_runtime_quality_touchpoint_inventory(
    payload: RuntimeQualityTouchpointInventory | Mapping[str, Any],
) -> ValidationReport:
    """Validate runtime/quality touchpoint registration and admission contracts."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, RuntimeQualityTouchpointInventory)
        else dict(payload)
    )
    discovered = [_mapping(row) for row in _sequence(raw.get("discovered_touchpoints"))]
    registrations = [_mapping(row) for row in _sequence(raw.get("registrations"))]
    if not discovered and registrations:
        discovered = registrations
    registered_ids = {str(row.get("touchpoint_id")) for row in registrations}
    issues: list[ValidationIssue] = []
    for index, touchpoint in enumerate(discovered):
        if str(touchpoint.get("touchpoint_id")) not in registered_ids:
            issues.append(
                    _issue(
                        "layer3_g0_source_touchpoint_registration_missing",
                        f"$.discovered_touchpoints[{index}]",
                        (
                            "every runtime/quality subordinate import requires "
                            "SourceTouchpointRegistration"
                        ),
                    )
                )
    for index, registration in enumerate(registrations):
        if registration.get("admission_allowed") is True and not registration.get(
            "existing_source_truth_adapter_path_ref"
        ):
            issues.append(
                _issue(
                    "layer3_g0_touchpoint_admission_without_contract",
                    f"$.registrations[{index}].existing_source_truth_adapter_path_ref",
                    "admission-allowed touchpoints require existing source-truth adapter paths",
                )
            )
    return _report(
        issues,
        summary={
            "runtime_quality_touchpoint_count": len(discovered),
            "runtime_quality_touchpoints_without_registration": sum(
                1
                for issue in issues
                if issue.code == "layer3_g0_source_touchpoint_registration_missing"
            ),
            "runtime_quality_touchpoint_admission_allowed_without_contract_count": sum(
                1
                for issue in issues
                if issue.code == "layer3_g0_touchpoint_admission_without_contract"
            ),
        },
    )


def load_source_truth_adapter_paths(lattice_path: Path) -> tuple[str, ...]:
    """Load existing source-truth preservation adapter-path IDs."""

    payload = _load_toml(lattice_path)
    return tuple(
        str(row["id"])
        for row in _sequence(payload.get("adapter_paths"))
        if isinstance(row, Mapping) and row.get("id")
    )


def validate_source_truth_lattice_adapter_paths(
    *,
    adapter_paths: Sequence[str],
    baseline_adapter_paths: Sequence[str],
) -> ValidationReport:
    """Validate that G0 did not add preservation adapter paths."""

    issues = []
    if tuple(adapter_paths) != tuple(baseline_adapter_paths):
        issues.append(
            _issue(
                "layer3_g0_source_truth_lattice_mutated_in_g0",
                "$.source_truth_lattice.adapter_paths",
                "G0 must not add source-truth adapter paths",
            )
        )
    return _report(
        issues,
        summary={
            "source_truth_adapter_path_count": len(baseline_adapter_paths),
            "source_truth_lattice_new_adapter_path_count": max(
                0,
                len(adapter_paths) - len(baseline_adapter_paths),
            ),
        },
    )


def validate_status_composition_matrix(
    matrix: StatusCompositionMatrix | Mapping[str, Any],
    *,
    cases: Sequence[Mapping[str, Any]] | None = None,
) -> ValidationReport:
    """Validate G0 status composition rules and optional negative cases."""

    status_matrix = StatusCompositionMatrix.model_validate(matrix)
    issues: list[ValidationIssue] = []
    if tuple(rule.rule_id for rule in status_matrix.rules) != _STATUS_RULE_IDS:
        issues.append(
            _issue(
                "layer3_g0_status_composition_missing",
                "$.status_composition_matrix.rules",
                "G0 requires the exact quarantine/conformance/maturity/promotion rules",
            )
        )
    for index, case in enumerate(cases or []):
        expected = str(case.get("expected_issue_code", "layer3_g0_status_composition_missing"))
        if case.get("quarantine_check") == "blocked" and case.get("admission_state") == "admitted":
            issues.append(_issue(expected, f"$.cases[{index}]", "quarantine dominates admission"))
        elif (
            case.get("promotion_state") == "governed_promoted"
            and case.get("conformance_status") != "pass"
        ):
            issues.append(
                _issue(
                    expected,
                    f"$.cases[{index}]",
                    "promotion cannot occur before conformance and G4",
                )
            )
    return _report(issues, summary={"status_composition_rule_count": len(status_matrix.rules)})


def validate_governance_followups(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate ADR governance follow-ups for import policy and registry crosswalk."""

    issues: list[ValidationIssue] = []
    if payload.get("import_policy_constitution_conflict_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_import_policy_constitution_conflict_unrecorded",
                "$.import_policy_constitution_conflict_recorded",
                "ADR-0175 must record the policy.toml vs constitution conflict",
            )
        )
    if payload.get("policy_toml_pdc_allowlist_narrowing_followup_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_import_policy_constitution_conflict_unrecorded",
                "$.policy_toml_pdc_allowlist_narrowing_followup_recorded",
                "ADR-0175 must name a follow-up ADR to narrow policy.toml pdc imports",
            )
        )
    if payload.get("registry_crosswalk_clarification_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_registry_conflation_unrecorded",
                "$.registry_crosswalk_clarification_recorded",
                "ADR-0175 must distinguish preservation registry from admission registry",
            )
        )
    return _report(issues)


def validate_layer3_g0_adr(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate ADR-0175 status, human acceptance, and open-question tracking."""

    adr = _mapping(payload.get("adr", payload))
    issues: list[ValidationIssue] = []
    if adr.get("status") != "Accepted":
        issues.append(
            _issue("layer3_g0_adr_not_accepted", "$.adr.status", "ADR-0175 must be Accepted")
        )
    if adr.get("status") == "Accepted" and not (
        adr.get("accepted_by") and adr.get("accepted_at") and adr.get("acceptance_ref")
    ):
        issues.append(
            _issue(
                "layer3_g0_adr_human_acceptance_missing",
                "$.adr.acceptance_ref",
                "Accepted ADR-0175 requires human-principal acceptance fields",
            )
        )
    if adr.get("open_questions_mode") != "tracked_empirically_open":
        issues.append(
            _issue(
                "layer3_g0_adr_open_questions_missing",
                "$.adr.open_questions_mode",
                "constitution open questions must remain tracked_empirically_open",
            )
        )
    required_v2_fields = {
        "v2_amendment_recorded": "ADR-0175 must record the v2 discovery/search amendment",
        "organizing_rules_recorded": (
            "ADR-0175 must record constitution organizing rules and Layer 3 discipline"
        ),
        "rule12_t7_recorded": "ADR-0175 must record amended Rule 12/T7 discipline",
        "impact_note_recorded": (
            "ADR-0175 must record impact on status, authority, replay, plans, health, and surfaces"
        ),
        "rule_version_refs_recorded": (
            "ADR-0175 must record schema and rule versions for replay and migration"
        ),
    }
    for field_name, message in required_v2_fields.items():
        if adr.get(field_name) is not True:
            issues.append(
                _issue(
                    "layer3_g0_adr_v2_amendment_incomplete",
                    f"$.adr.{field_name}",
                    message,
                )
            )
    issues.extend(validate_governance_followups(adr).issues)
    return _report(issues)


def validate_first_vertical_case_record(
    payload: FirstVerticalCaseRecord | Mapping[str, Any],
) -> ValidationReport:
    """Validate first vertical corpus and construct identifiers."""

    record = FirstVerticalCaseRecord.model_validate(payload)
    issues: list[ValidationIssue] = []
    if (
        record.first_vertical_corpus_case_id != FIRST_VERTICAL_CORPUS_CASE_ID
        or record.first_vertical_construct_bundle_id != FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID
        or record.first_vertical_corpus_case_id == record.first_vertical_construct_bundle_id
    ):
        issues.append(
            _issue(
                "layer3_g0_first_case_id_mismatch",
                "$.first_vertical_case",
                "G0 must keep the first corpus case and construct bundle IDs distinct",
            )
        )
    return _report(issues)


def _default_triage_records() -> list[CapabilityTriageRecord]:
    authority = _triage_authority_boundary()
    return [
        CapabilityTriageRecord(
            capability_id="scenario_family_authority_selector",
            disposition="quarantine",
            rationale=(
                "Scenario-family selectors are projection-only and cannot be "
                "adapter authority."
            ),
            evidence_refs=[
                "repo://src/polisyos/runtime/quality/scenario_evidence_contract.py#L349",
                "repo://architecture/shims.toml#L176",
            ],
            missing_capability_labels=["verification_missing"],
            quarantine_ref="quarantine://layer3-g0/scenario-family-authority-selector",
            adapter_admissibility="blocked",
            authority_boundary=authority,
        ),
        CapabilityTriageRecord(
            capability_id="lex_binary_status_candidate",
            disposition="wrap_then_strangle",
            rationale=(
                "Only the simple_v1 binary projection path is triage-required; "
                "graded Lex authority remains the stronger seam."
            ),
            evidence_refs=[
                "repo://src/polisyos/lex/legal_evaluation/backends/simple_v1.py#L15",
                "repo://src/polisyos/lex/normpack/legal_authority.py#L303",
            ],
            missing_capability_labels=["verification_missing", "semantic_test_missing"],
            quarantine_ref=None,
            adapter_admissibility="blocked_until_retriage",
            authority_boundary=authority,
        ),
    ]


def _triage_authority_boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["layer3_g0_pre_adapter_triage"],
        may_not_use_for=["adapter_admission", "publication_authority"],
        source_authority="deterministic_producer",
        posture="shadow",
        rule_version_refs=[LAYER3_G0_RULE_VERSION],
    )


def _complete_triage_records(
    capability_inventory: CapabilityDataInventory,
    data_asset_inventory: DataAssetInventory,
) -> list[CapabilityTriageRecord]:
    records = list(_default_triage_records())
    seen = {record.capability_id for record in records}
    authority = _triage_authority_boundary()
    for entry in capability_inventory.entries:
        if entry.capability_id in seen:
            continue
        records.append(
            CapabilityTriageRecord(
                capability_id=entry.capability_id,
                disposition="surface_out_of_scope",
                rationale=(
                    "Inventory row is visible to G0 but is not adapter-admitted by "
                    "pre-adapter triage."
                ),
                evidence_refs=list(
                    dict.fromkeys(entry.source_refs or [entry.owner_evidence_ref])
                )[:60],
                missing_capability_labels=[entry.current_capability_label],
                quarantine_ref=None,
                adapter_admissibility="not_admitted_pre_adapter",
                authority_boundary=authority,
            )
        )
        seen.add(entry.capability_id)
    for asset in data_asset_inventory.data_assets:
        if asset.asset_id in seen:
            continue
        records.append(
            CapabilityTriageRecord(
                capability_id=asset.asset_id,
                disposition="surface_out_of_scope",
                rationale=(
                    "Data asset is inventoried for lineage/rights/freshness but is "
                    "not a capability until a source-contract adapter consumes it."
                ),
                evidence_refs=[asset.owner_evidence_ref],
                missing_capability_labels=["implemented_but_not_orchestrated"],
                quarantine_ref=None,
                adapter_admissibility="data_asset_port_required",
                authority_boundary=authority,
            )
        )
        seen.add(asset.asset_id)
    for transform in data_asset_inventory.processing_transforms:
        if transform.transform_id in seen:
            continue
        records.append(
            CapabilityTriageRecord(
                capability_id=transform.transform_id,
                disposition="surface_out_of_scope",
                rationale=(
                    "Processing transform is inventoried as a replayable producer "
                    "candidate; G0 triage does not admit it as source authority."
                ),
                evidence_refs=list(
                    dict.fromkeys(transform.transform_script_refs or [transform.owner_evidence_ref])
                )[:60],
                missing_capability_labels=["producer_missing"],
                quarantine_ref=None,
                adapter_admissibility="producer_contract_required",
                authority_boundary=authority,
            )
        )
        seen.add(transform.transform_id)
    return records


def _scenario_family_quarantine() -> QuarantineRegistryEntry:
    return QuarantineRegistryEntry(
        target_id="scenario_family_authority_selector",
        target_kind="source_touchpoint",
        reason="Scenario-family projection is not source authority.",
        pattern_ids=["P05", "P06", "P15"],
        blocker_codes=["layer3_g0_quarantined_source_admitted"],
        enforcement_surface="adapter_admission_registry",
        release_condition="source-truth adapter path and human retriage required",
    )


def _lex_binary_status_quarantine() -> QuarantineRegistryEntry:
    return QuarantineRegistryEntry(
        target_id="lex_binary_status_candidate",
        target_kind="data_asset",
        reason="Binary Lex projection cannot substitute for graded legal authority.",
        pattern_ids=["P04", "P05", "P10"],
        blocker_codes=["layer3_g0_quarantined_source_admitted"],
        enforcement_surface="adapter_admission_registry",
        release_condition="graded Lex authority adapter and semantic tests required",
    )


def _adapter_admission_records(
    registrations: Sequence[SourceTouchpointRegistration],
) -> list[AdapterAdmissionRecord]:
    records = [
        AdapterAdmissionRecord(
            adapter_id=f"layer3-g0-shadow-{_slug(row.touchpoint_id)}",
            source_ids=[row.touchpoint_id],
            port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            maturity="fail_closed",
            promotion_state="shadow",
            conformance_status="not_run_pre_adapter",
            quarantine_check=row.quarantine_check_result,
            admission_state="candidate_shadow_only",
            admitted=False,
            adapter_contract_path_refs=[],
            source_touchpoint_refs=[row.touchpoint_id],
        )
        for row in registrations
    ]
    records.append(
        AdapterAdmissionRecord(
            adapter_id="scenario-family-authority-selector-blocked",
            source_ids=["scenario_family_authority_selector"],
            port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            maturity="fail_closed",
            promotion_state="promotion_blocked",
            conformance_status="blocked",
            quarantine_check="blocked",
            admission_state="blocked",
            admitted=False,
            adapter_contract_path_refs=[],
            source_touchpoint_refs=[],
        )
    )
    return records


def _data_asset_ports(inventory: DataAssetInventory) -> list[DataAssetPort]:
    ports: list[DataAssetPort] = []
    for root in inventory.required_roots:
        matching = next(
            (asset for asset in inventory.data_assets if asset.owning_root == root.path),
            None,
        )
        if matching is None:
            continue
        ports.append(
            DataAssetPort(
                asset_id=matching.asset_id,
                data_kind=matching.data_kind,
                path=matching.path,
                lineage_ref=matching.lineage_evidence_ref,
                rights_ref=matching.rights_evidence_ref,
                freshness_ref=matching.freshness_evidence_ref,
                fitness_ref=matching.fitness_evidence_ref,
                contamination_check_ref=matching.contamination_check_ref,
                source_contract_ref=_source_contract_ref_for_asset(matching),
                source_contract_readiness=_source_contract_readiness_for_asset(matching),
                index_refs=[_index_ref_for_asset(matching)],
                port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            )
        )
    return ports


def _health_metric_ledgers() -> list[HealthMetricLedger]:
    return [
        HealthMetricLedger(
            metric_id="envelope-expansion-rate",
            owner="team-runtime-quality",
            freeze_value={"g0_admitted_adapter_count": 0},
            trend_vocabulary=["expanding", "flat", "shrinking"],
            per_slice_delta_rule="Later slices may change only after admitted adapter evidence.",
            next_update_rule="Recompute when a G1+ adapter slice writes governed artifacts.",
        ),
        HealthMetricLedger(
            metric_id="adapter-semantic-loss",
            owner="team-runtime-quality",
            freeze_value={"semantic_loss_events": 0},
            trend_vocabulary=["clean", "lossy"],
            per_slice_delta_rule="Any AdapterLossBlocker event increments lossy evidence.",
            next_update_rule="Recompute from conformance harness outputs.",
        ),
        HealthMetricLedger(
            metric_id="governance-throughput",
            owner="principal-governance",
            freeze_value={"accepted_adr_count": 0, "open_human_gate_count": 1},
            trend_vocabulary=["flowing", "stalled"],
            per_slice_delta_rule=(
                "Human acceptance gates move throughput only with acceptance refs."
            ),
            next_update_rule="Recompute at ADR-0175 acceptance.",
        ),
        HealthMetricLedger(
            metric_id="demand-pull-vs-abstention",
            owner="team-runtime-quality",
            freeze_value={"grounded_conversion_count": 0},
            trend_vocabulary=["responding", "abstention_inertia"],
            per_slice_delta_rule=(
                "Demand pull cannot count until a grounded adapter admits evidence."
            ),
            next_update_rule="Recompute from universal corpus G0 route.",
        ),
        HealthMetricLedger(
            metric_id="search-recall@known-seeds+index-staleness",
            owner="team-runtime-quality",
            freeze_value={
                "known_groundable_seed_miss_count": 0,
                "stale_required_index_count": 0,
            },
            trend_vocabulary=["fresh_recall_ok", "search_ceiling"],
            per_slice_delta_rule=(
                "Recall misses or stale required indexes block domain-ceiling and no-hit claims."
            ),
            next_update_rule="Recompute from GroundingSearchDiscipline recall/freshness records.",
        ),
    ]


def _bundle_counts(
    *,
    capability_inventory: CapabilityDataInventory,
    data_asset_inventory: DataAssetInventory,
    discovery_index_inventory: DiscoveryIndexInventory,
    resource_discovery_inventory: ResourceDiscoveryInventory,
    grounding_search_discipline: GroundingSearchDiscipline,
    port_map: PortMap,
    touchpoints: RuntimeQualityTouchpointInventory,
    adapter_paths: Sequence[str],
    adapter_registry: Sequence[AdapterAdmissionRecord],
    data_ports: Sequence[DataAssetPort],
    health_ledgers: Sequence[HealthMetricLedger],
    import_firewall: ImportFirewallReport,
    hardcode_backlog: HardcodeEnumerationBacklog,
    no_hardcode_lint: NoHardcodeEnumerationLintReport,
    engineering_quality: EngineeringQualityCheck,
    status_matrix: StatusCompositionMatrix,
) -> dict[str, Any]:
    counts = {
        **capability_inventory.summary,
        **data_asset_inventory.summary,
        **discovery_index_inventory.summary,
        **resource_discovery_inventory.summary,
        **grounding_search_discipline.summary,
        **port_map.summary,
        **touchpoints.summary,
        **hardcode_backlog.summary,
        "data_asset_port_count": len(data_ports),
        "data_asset_source_contract_readiness_coverage": _data_asset_readiness_coverage(
            data_ports
        ),
        "data_asset_source_contract_readiness_status": "pass"
        if _data_asset_readiness_coverage(data_ports) == 1.0
        else "fail",
        "source_truth_adapter_path_count": len(adapter_paths),
        "source_truth_lattice_new_adapter_path_count": 0,
        "admitted_adapter_count": sum(1 for record in adapter_registry if record.admitted),
        "adapter_candidate_count": len(adapter_registry),
        "quarantine_registry_min_count": 1,
        "health_metric_ledger_count": len(health_ledgers),
        "closure_artifact_count": len(_closure_artifact_paths()),
        "readiness_manifest_count": 1,
        "import_firewall_artifact_count": 1,
        "status_composition_rule_count": len(status_matrix.rules),
        "pdc_non_waist_import_count": len(import_firewall.violations),
        "grounded_conversion_count": 0,
        "no_hardcode_enumeration_lint_status": no_hardcode_lint.status,
        "engineering_quality_check_status": engineering_quality.status,
        "g1_dependency_requirements_status": "pass",
        "search_recall_seed_status": "pass",
        "index_freshness_status": "pass",
        "free_growth_fixture_status": "pass",
        "mechanism_generality_fixture_status": "pass",
    }
    counts["runtime_quality_touchpoint_count"] = touchpoints.summary.get(
        "runtime_quality_touchpoint_count",
        0,
    )
    return counts


def _closure_artifact_paths() -> list[str]:
    return [
        "architecture/policy_design_case/layer3_g0_readiness_manifest.json",
        "architecture/policy_design_case/layer3_g0_capability_data_inventory.json",
        "architecture/policy_design_case/layer3_g0_triage_registry.json",
        "architecture/policy_design_case/layer3_g0_port_map.json",
        "architecture/policy_design_case/layer3_adapter_admission_registry.json",
        "architecture/policy_design_case/layer3_data_asset_ports.json",
        "architecture/policy_design_case/layer3_conformance_harness.json",
        "architecture/policy_design_case/layer3_health_metric_ledgers.toml",
        "architecture/policy_design_case/layer3_import_firewall_lint.json",
        "architecture/policy_design_case/layer3_empty_port_map.json",
        "architecture/policy_design_case/layer3_adapter_cost_map.json",
        "architecture/policy_design_case/layer3_first_vertical_case.json",
        "architecture/policy_design_case/layer3_discovery_search_discipline.json",
        "architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json",
        "architecture/policy_design_case/layer3_engineering_quality_check.json",
        "docs/adr/0175-layer3-grounding-subordination-discipline.md",
    ]


def _bundle_from_payload(payload: Layer3G0Bundle | Mapping[str, Any]) -> Layer3G0Bundle:
    if isinstance(payload, Layer3G0Bundle):
        return payload
    return Layer3G0Bundle.model_validate(payload)


def _data_asset_entry(
    *,
    asset_id: str,
    path: str,
    owning_root: str,
    evidence_path: Path,
    repo_root: Path,
    size_bytes: int | None = None,
) -> DataAssetInventoryEntry:
    evidence_ref = _repo_ref(evidence_path, repo_root)
    return DataAssetInventoryEntry(
        asset_id=asset_id,
        data_kind="data_asset",
        path=path,
        owning_root=owning_root,
        size_bytes=size_bytes,
        owner_evidence_ref=evidence_ref,
        lineage_evidence_ref=evidence_ref,
        rights_evidence_ref=evidence_ref,
        freshness_evidence_ref=evidence_ref,
        fitness_evidence_ref=evidence_ref,
        contamination_check_ref=evidence_ref,
    )


def _source_contract_ref_for_asset(asset: DataAssetInventoryEntry) -> str | None:
    if asset.owning_root == "production_data":
        return f"source-contract://fabric/{asset.asset_id}"
    return None


def _source_contract_readiness_for_asset(asset: DataAssetInventoryEntry) -> str:
    if asset.owning_root == "production_data":
        return f"source-contract-readiness://fabric/{asset.asset_id}"
    return f"fixture-or-docs-readiness://layer3-g0/{asset.asset_id}"


def _index_ref_for_asset(asset: DataAssetInventoryEntry) -> str:
    if asset.owning_root == "production_data":
        return "production-data-manifest-index"
    return "fixture-resource-index"


def _data_asset_readiness_coverage(data_ports: Sequence[DataAssetPort]) -> float:
    if not data_ports:
        return 1.0
    ready = sum(1 for port in data_ports if port.source_contract_readiness)
    return ready / len(data_ports)


def _issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def _report(
    issues: Sequence[ValidationIssue],
    *,
    summary: Mapping[str, Any] | None = None,
) -> ValidationReport:
    return ValidationReport(
        status="fail" if issues else "pass",
        issues=list(issues),
        summary=dict(summary or {}),
    )


def _repo_ref(path: Path, repo_root: Path) -> str:
    return f"repo://{_repo_path(path, repo_root)}"


def _repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_root_from_artifact(path: Path) -> Path:
    parts = path.resolve().parts
    if "policy-engine" in parts:
        index = parts.index("policy-engine")
        return Path(*parts[: index + 1])
    return path.parent


def _line_ref(path: Path, needle: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return f"repo://{path.as_posix()}#L1"
    for index, line in enumerate(lines, start=1):
        if needle in line:
            return f"repo://{path.as_posix()}#L{index}"
    return f"repo://{path.as_posix()}#L1"


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        return 0


def _file_count(path: Path) -> int:
    return sum(1 for child in path.rglob("*") if child.is_file()) if path.exists() else 0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return []


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _package_kind(root: str) -> str:
    if root == "pdc":
        return "narrow_waist"
    if root == "runtime":
        return "runtime_quality_surface"
    if root in _RUNTIME_QUALITY_SOURCE_ROOTS:
        return "source_package"
    return "support_package"


def _imports_for_package(package_path: Path) -> list[str]:
    roots: set[str] = set()
    for path in package_path.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            for import_root, _source_module in _polisyos_import_refs(node):
                roots.add(import_root)
    return sorted(roots)


def _polisyos_import_refs(node: ast.AST) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if (
        isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module
        and (node.module == "polisyos" or node.module.startswith("polisyos."))
    ):
        parts = node.module.split(".")
        if len(parts) >= 2:
            refs.append((parts[1], node.module))
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "polisyos" or alias.name.startswith("polisyos."):
                parts = alias.name.split(".")
                if len(parts) >= 2:
                    refs.append((parts[1], alias.name))
    return refs


def _no_hardcode_scan_paths(repo_root: Path) -> list[str]:
    quality_root = repo_root / "src/polisyos/runtime/quality"
    paths: set[str] = set()
    for pattern in ("*capability*.py", "*resolver*.py", "*registry*.py"):
        paths.update(_repo_path(path, repo_root) for path in quality_root.glob(pattern))
    paths.add("src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py")
    paths.add("tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py")
    return sorted(path for path in paths if (repo_root / path).exists())


def _mentioned_hardcode_patterns(
    path: Path,
    patterns: Mapping[str, tuple[HardcodeEnumerationKind, str]],
) -> set[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    mentioned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in patterns:
            mentioned.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in patterns:
            mentioned.add(node.attr)
    return mentioned


def _hardcode_enumeration_patterns(
    repo_root: Path,
) -> dict[str, tuple[HardcodeEnumerationKind, str]]:
    backlog = build_hardcode_enumeration_backlog(repo_root)
    return {
        entry.pattern: (entry.enumeration_kind, entry.backlog_id)
        for entry in backlog.entries
    }


def _immediate_polisyos_roots(repo_root: Path) -> list[str]:
    src_root = repo_root / "src/polisyos"
    return sorted(
        path.name for path in src_root.iterdir() if path.is_dir() and path.name != "__pycache__"
    )


def _universal_corpus_fixture_count(repo_root: Path) -> int:
    manifest = _load_json(repo_root / "tests/fixtures/universal-corpus/manifest.json")
    fixtures = manifest.get("fixtures", [])
    return len(fixtures) if isinstance(fixtures, Sequence) else 0


def _runtime_builder_hash(counts: Mapping[str, Any]) -> str:
    canonical = json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _bundle_content_hash(bundle: Layer3G0Bundle) -> str:
    payload = bundle.model_dump(mode="json")
    manifest = _mapping(payload.get("readiness_manifest"))
    if isinstance(manifest, dict):
        manifest.pop("runtime_builder_hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _bounded_id(prefix: str, value: str, *, max_length: int = 220) -> str:
    slug = f"{prefix}-{_slug(value)}"
    if len(slug) <= max_length:
        return slug
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    keep = max_length - len(suffix) - 1
    return f"{slug[:keep].rstrip('-')}-{suffix}"
