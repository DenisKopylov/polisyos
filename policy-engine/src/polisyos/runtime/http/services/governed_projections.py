"""Lazy, content-addressed HTTP projections of governed repository artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, model_validator

from polisyos.common import serialization
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.acquisition_surface_contracts import (
    AcquisitionGrowthPayload,
)
from polisyos.runtime.http.services.acquisition_surface_projection import (
    build_acquisition_growth_projection,
)
from polisyos.runtime.http.services.channel_contracts import (
    RUNS_CHANNEL_DATA_EVENT_CONTRACT,
    ReviewPresenceSnapshot,
)
from polisyos.runtime.http.services.export_replay import (
    EXPORT_REPLAY_CONTRACT,
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.governed_projection_dependencies import (
    dependency_manifest_matches,
)
from polisyos.runtime.quality.design_problem import DesignProblem

_PROJECTION_BASE_PATH = "/api/v1/exports/governed-projections"


class AudienceClass(StrEnum):
    """Declare the intended consumer class without enforcing it in DS3."""

    REVIEWER = "REVIEWER"
    EXPERT = "EXPERT"
    MACHINE = "MACHINE"


class ProjectionAvailability(StrEnum):
    """Describe whether a governed source can back a projection."""

    AVAILABLE = "available"
    ARTIFACT_MISSING = "artifact_missing"
    INVALID_SOURCE = "invalid_source"


class ProjectionId(StrEnum):
    """Stable addresses for the DS3 governed projection denominator."""

    DEPTH_N_CYCLE_BOARD = "depth-n-cycle-board"
    VALUE_GATE = "value-gate"
    GENERATION_CYCLE_DISPOSITION = "generation-cycle-disposition"
    ENGINE_CENSUS = "engine-census"
    FORK_B_RELATION_CENSUS = "fork-b-relation-census"
    ACQUISITION_ROUTING_CONTRACT = "acquisition-routing-contract"
    N13A_ACQUISITION_CENSUS = "n13a-acquisition-census"
    N13A_LIVE_PROBE_JOURNAL = "n13a-live-probe-journal"
    ACQUISITION_GROWTH = "acquisition-growth"
    CAPABILITY_REALITY = "capability-reality"
    CLUSTER_OWNERSHIP = "cluster-ownership"
    LAYER3_HEALTH_METRICS = "layer3-health-metrics"
    LEGACY_PROVING_GROUND = "legacy-proving-ground"
    SURFACE_READINESS = "surface-readiness"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectionOwnerBinding(_StrictModel):
    """Resolve an owner-declared semantic hash without calling it byte identity."""

    binding_name: str
    relation: Literal["semantic_projection"] = "semantic_projection"
    relative_path: str
    owner_semantic_hash: str
    semantic_hash_rule_version: str
    resolved_artifact_content_hash: str


class ProjectionSourceValidation(_StrictModel):
    """Bind an owner-validator result to the exact source identity projected."""

    validator_id: str
    validator_version: str
    status: Literal["passed", "failed", "not_run"]
    bound_artifact_content_hash: str
    bound_dependency_aggregate_identity: str
    bound_dependency_count: int = Field(ge=0)
    semantic_projection_hash: str | None = None
    semantic_projection_hash_rule_version: str | None = None
    issue_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _passed_receipt_is_complete(self) -> Self:
        if self.status == "passed" and (
            self.bound_dependency_count < 1
            or self.semantic_projection_hash is None
            or self.semantic_projection_hash_rule_version is None
        ):
            raise ValueError("passed owner validation requires dependency and semantic hashes")
        if self.status != "passed" and self.semantic_projection_hash is not None:
            raise ValueError("non-passing owner validation cannot publish a semantic hash")
        return self


class ProjectionSourceIdentity(_StrictModel):
    """Bind a packet to the exact source bytes observed by the producer."""

    relative_path: str
    artifact_content_hash: str
    declared_content_hash: str | None = None
    validation: ProjectionSourceValidation
    related_artifact_bindings: tuple[ProjectionOwnerBinding, ...] = ()


class ProjectionFreshness(_StrictModel):
    """Separate source time from the time the HTTP producer observed it."""

    state: Literal["observed", "artifact_missing", "invalid_source"]
    basis: Literal["source_timestamp", "filesystem_mtime", "request_observation"]
    observed_at: datetime
    source_as_of: datetime | None = None


class ProjectionCatalogEntry(_StrictModel):
    """Describe one stable projection without reading its source artifact."""

    projection_id: ProjectionId
    expected_source_path: str
    source_policy: Literal["required", "presence_gated", "fixture_identity_only"]
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    expected_source_schema_version: str | None
    expected_source_rule_version: str | None
    owner_validator_id: str
    owner_validator_version: str
    stable_address: str


type ProjectionJsonValue = Annotated[
    object,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "array", "items": {}},
                {"type": "object", "additionalProperties": True},
                {"type": "null"},
            ]
        }
    ),
]

JsonObject = dict[str, ProjectionJsonValue]
JsonObjectTuple = tuple[JsonObject, ...]


class DepthNAcquisitionRouteReference(_StrictModel):
    """Content-bound owner route reference carried by the depth-N artifact."""

    owner_content_hash: str
    owner_schema: str
    planner_report_content_hash: str
    requirement_gap_id: str


class DepthNAcquisitionEconomicsProjection(_StrictModel):
    """Hash-resolved N7 planner economics, separate from its route reference."""

    planner_report_content_hash: str
    planner_status: str
    missing_requirement_fields: tuple[str, ...]
    recommended_strategy: str
    expected_cost: float | None
    expected_voi: float | None
    voi_rank: int | None
    decision_owner_ref: str
    producer_expected: str
    next_action: str


class DepthNDomainRunProjection(_StrictModel):
    """Narrow recorded fields for one depth-N domain run."""

    generation_cycle_run_id: str
    design_problem_ref: str
    design_problem: DesignProblem
    domain_role: str
    search_terminal_kind: str
    terminal_distribution: JsonObject
    evidence_class: str
    evidence_witness: JsonObject
    weakest_links: tuple[str, ...]
    acquisition_route: DepthNAcquisitionRouteReference | None = None
    acquisition_economics: DepthNAcquisitionEconomicsProjection | None = None


class DepthNCycleBoardPayload(_StrictModel):
    """Cycle Board dependency projection from the depth-N capstone."""

    depth_evidence: JsonObject
    domain_runs: dict[str, DepthNDomainRunProjection]
    terminal_distributions: JsonObject


class ValueGatePayload(_StrictModel):
    """Value-gate dependency projection."""

    denominators: JsonObject
    education_refusal: JsonObject
    production_refusal: JsonObject
    advisor_receipts: JsonObject
    value_outer_set_contract: JsonObjectTuple
    mode_gates: JsonObject
    acquisition_routing: JsonObject
    disposition: JsonObject


class GenerationCycleDispositionPayload(_StrictModel):
    """Generation-cycle task and owner disposition projection."""

    tasks: JsonObject
    owners: JsonObjectTuple
    task_owner_mapping: JsonObject
    bridge_artifacts: JsonObject
    method_availability_gate: JsonObject
    known_residuals: JsonObjectTuple
    parallel_world_reconciliation: JsonObjectTuple


class EngineCensusPayload(_StrictModel):
    """Engine census summary without the row table."""

    row_count: int
    execution_status_vocabulary: JsonObject
    critical_findings: tuple[str, ...]
    subcensus_summary: JsonObject
    gap_taxonomy_extensions: JsonObject
    verb_gap_consistency: JsonObject
    evidence_reproducibility: JsonObject
    discipline: str
    scope: str


class ForkBRelationCensusPayload(_StrictModel):
    """Fork-B relation census projection without relation rows."""

    relation_counts: dict[str, int]
    relation_denominator_formula: str
    authority: str
    coverage_manifest: JsonObject
    certificate_summaries: JsonObject
    transport_floor: float
    transport_floor_rule: str
    known_bridge_limits: tuple[str, ...]
    normalization: str


class AcquisitionRoutingPayload(_StrictModel):
    """Acquisition routing contract projection."""

    denominators: JsonObject
    positive_receipt: JsonObject
    no_result_receipt: JsonObject
    fail_closed_receipt: JsonObject
    fail_closed_probes: JsonObjectTuple
    grounding_acquisition_request: JsonObject
    recorded_rederive_inputs: JsonObject
    compute_economics: JsonObject
    known_residuals: JsonObjectTuple


class N13AAcquisitionCensusPayload(_StrictModel):
    """N13a census dependency projection."""

    catalog_identity: JsonObject
    projection_bindings: JsonObjectTuple
    family_scorecards: JsonObjectTuple
    metric_resolutions: JsonObjectTuple
    route_evidence: JsonObjectTuple
    growth_backlog: JsonObjectTuple
    fetch_plan_generation: JsonObject
    reverse_demand_residuals: JsonObjectTuple


class N13ALiveProbeJournalPayload(_StrictModel):
    """N13a live-probe journal dependency projection."""

    selection_plan: JsonObject
    family_receipts: JsonObjectTuple
    records: JsonObjectTuple


class CapabilityRealityPayload(_StrictModel):
    """Owner-reported capability reality projection."""

    summary: JsonObject
    readiness: JsonObject
    capability_claims: JsonObjectTuple
    blockers: JsonObjectTuple
    issues: JsonObjectTuple
    chain_clusters: JsonObjectTuple
    ratchet_integrity_status: str
    debt_algebra: JsonObject


class ClusterOwnershipPayload(_StrictModel):
    """Cluster/cell ownership projection."""

    status: str
    owner: str
    purpose: str
    ratchet_state_vocabulary: tuple[str, ...]
    required_clusters: tuple[str, ...]
    required_cell_fields: tuple[str, ...]
    capability_chain_steps: tuple[str, ...]
    stop_rule: JsonObject
    open_cell_closure: JsonObject
    handshake_graph: JsonObject
    architecture_core: JsonObject
    clusters: JsonObject


class Layer3HealthMetricsPayload(_StrictModel):
    """Recorded health metric ledger projection."""

    health_metric_ledgers: JsonObjectTuple


class ProvingGroundFixtureIdentity(_StrictModel):
    """Manifest-owned identity for one legacy proving-ground case."""

    case_id: str
    domain: str
    split: str
    authority_levels: tuple[str, ...]


class ProvingGroundFixtureRecord(_StrictModel):
    """Narrow fixture expectation projection without producer metadata."""

    case_id: str
    title: str
    domain: str
    split: str
    schema_version: str
    intent: JsonObject
    input_intent_ref: str
    compilation_intent_text: str
    concept_spine_refs: JsonObject
    expected_adapter_bindings: JsonObject
    expected_claim_families: JsonObject
    expected_closeout_states: JsonObject
    expected_facets: JsonObject
    expected_obligation_graph: JsonObject
    expected_projection_truthfulness: JsonObject
    expected_requirement_specs: JsonObject
    expert_adjudication: JsonObject
    claim_evidence_annotations: JsonObject


class ProvingGroundRuntimeOutcomes(_StrictModel):
    """Explicitly absent runtime result slot for fixture-only records."""

    availability: Literal["artifact_missing"] = "artifact_missing"
    reason: str


class LegacyProvingGroundPayload(_StrictModel):
    """Fixture-only identity and semantic expectations."""

    fixture_authority: Literal["fixture_only"] = "fixture_only"
    fixture_identities: tuple[ProvingGroundFixtureIdentity, ...]
    fixture_records: tuple[ProvingGroundFixtureRecord, ...]
    runtime_outcomes: ProvingGroundRuntimeOutcomes


class SurfaceReadinessPayload(_StrictModel):
    """Owner-versioned surface readiness projection once a live schema exists."""

    ledger_id: str
    authority: JsonObject
    controlled_vocabulary_source: str
    entries: tuple[ProjectionJsonValue, ...]


ProjectionPayload = (
    DepthNCycleBoardPayload
    | ValueGatePayload
    | GenerationCycleDispositionPayload
    | EngineCensusPayload
    | ForkBRelationCensusPayload
    | AcquisitionRoutingPayload
    | N13AAcquisitionCensusPayload
    | N13ALiveProbeJournalPayload
    | AcquisitionGrowthPayload
    | CapabilityRealityPayload
    | ClusterOwnershipPayload
    | Layer3HealthMetricsPayload
    | LegacyProvingGroundPayload
    | SurfaceReadinessPayload
)


class _GovernedProjectionPacketBase(_StrictModel):
    """Fields common to every typed governed-projection state."""

    packet_schema_version: Literal["policyos.runtime.governed_projection_packet.v1"] = (
        "policyos.runtime.governed_projection_packet.v1"
    )
    export_replay_contract: Literal["policyos.runtime.export_replay_binding.v1"] = (
        EXPORT_REPLAY_CONTRACT
    )
    projection_id: ProjectionId
    projection_rule_version: Literal["policyos.runtime.governed_projection.v1"] = (
        "policyos.runtime.governed_projection.v1"
    )
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    source_schema_version: str | None = None
    source_rule_version: str | None = None
    as_of: datetime
    freshness: ProjectionFreshness
    stable_address: str


class AvailableGovernedProjectionPacket(_GovernedProjectionPacketBase):
    """Projection state with a source-specific typed payload."""

    availability: Literal[ProjectionAvailability.AVAILABLE]
    source: ProjectionSourceIdentity
    source_dependency_hash: str
    projection_hash: str
    replay_address: str
    payload: ProjectionPayload
    absence_reason: None = None

    @model_validator(mode="after")
    def _payload_matches_projection(self) -> Self:
        expected_model = _PAYLOAD_MODEL_BY_ID[self.projection_id]
        if not isinstance(self.payload, expected_model):
            raise ValueError(f"{self.projection_id.value} requires {expected_model.__name__}")
        return self


class ArtifactMissingGovernedProjectionPacket(_GovernedProjectionPacketBase):
    """Projection state for an absent governed source."""

    availability: Literal[ProjectionAvailability.ARTIFACT_MISSING]
    source: None = None
    source_dependency_hash: None = None
    source_schema_version: None = None
    source_rule_version: None = None
    projection_hash: None = None
    replay_address: None = None
    payload: None = None
    absence_reason: str


class InvalidGovernedProjectionPacket(_GovernedProjectionPacketBase):
    """Projection state for present bytes that fail source validation."""

    availability: Literal[ProjectionAvailability.INVALID_SOURCE]
    source: ProjectionSourceIdentity
    source_dependency_hash: None = None
    projection_hash: None = None
    replay_address: None = None
    payload: None = None
    absence_reason: str


GovernedProjectionPacket = Annotated[
    AvailableGovernedProjectionPacket
    | ArtifactMissingGovernedProjectionPacket
    | InvalidGovernedProjectionPacket,
    Field(discriminator="availability"),
]


class ProjectionCatalogResponse(_StrictModel):
    """Return the complete DS3 producer denominator."""

    schema_version: Literal["policyos.runtime.governed_projection_catalog.v1"] = (
        "policyos.runtime.governed_projection_catalog.v1"
    )
    projections: tuple[ProjectionCatalogEntry, ...]


class ChannelRegistryEntry(_StrictModel):
    """Govern a non-OpenAPI realtime channel and its existing security contract."""

    registry_id: str
    path_template: str
    transport: Literal["sse", "websocket"]
    channels: tuple[str, ...] = ()
    message_contract: str
    producer_contract_ref: str
    auth_class: str
    consumers: tuple[str, ...] = Field(min_length=1)
    owner: str
    capability_state: Literal["verification_missing"] = "verification_missing"
    include_in_schema: Literal[False] = False
    status: Literal["active"] = "active"


class ChannelRegistryResponse(_StrictModel):
    """Return all active hidden runtime channels."""

    schema_version: Literal["policyos.runtime.channel_registry.v1"] = (
        "policyos.runtime.channel_registry.v1"
    )
    channels: tuple[ChannelRegistryEntry, ...]


CHANNEL_REGISTRY: tuple[ChannelRegistryEntry, ...] = (
    ChannelRegistryEntry(
        registry_id="runs-list-live",
        path_template="/api/v1/runs/live",
        transport="sse",
        message_contract=RUNS_CHANNEL_DATA_EVENT_CONTRACT,
        producer_contract_ref=(
            "polisyos.runtime.http.services.channel_contracts:RunsChannelDataEvent"
        ),
        auth_class="runtime_tenant_access+stream_rate_limit",
        consumers=("apps/runtime-dashboard:RunsLiveProvider",),
        owner="polisyos.runtime.http.routes.runs",
    ),
    ChannelRegistryEntry(
        registry_id="run-detail-live",
        path_template="/api/v1/runs/{run_id}/live",
        transport="sse",
        message_contract=RUNS_CHANNEL_DATA_EVENT_CONTRACT,
        producer_contract_ref=(
            "polisyos.runtime.http.services.channel_contracts:RunsChannelDataEvent"
        ),
        auth_class="runtime_run_tenant_access+stream_rate_limit",
        consumers=("apps/runtime-dashboard:useRunLiveUpdates",),
        owner="polisyos.runtime.http.routes.runs",
    ),
    ChannelRegistryEntry(
        registry_id="review-live",
        path_template="/api/v1/review/live",
        transport="websocket",
        channels=("review.cursor", "review.lock", "review.presence"),
        message_contract=str(ReviewPresenceSnapshot.model_fields["schema_version"].default),
        producer_contract_ref=("polisyos.runtime.http.services.channel_contracts:ReviewSnapshot"),
        auth_class="runtime_review_socket_auth+tenant_opa_action+stream_rate_limit",
        consumers=("apps/runtime-dashboard:useReviewCollaborationSurface",),
        owner="polisyos.runtime.http.routes.review",
    ),
)


class ReplayPinMismatchError(ValueError):
    """Report that a stable address no longer matches requested replay pins."""

    def __init__(self, field: str, *, expected: str, actual: str | None) -> None:
        self.field = field
        self.expected = expected
        self.actual = actual
        super().__init__(f"{field} replay pin {expected!r} does not match {actual!r}")


class InvalidProjectionSourceError(ValueError):
    """Report a missing owner-recorded field without deriving a replacement."""


@dataclass(frozen=True, slots=True)
class _ProjectionDefinition:
    projection_id: ProjectionId
    source_path: str
    source_format: Literal["json", "toml", "proving_ground", "acquisition_growth"]
    source_policy: Literal["required", "presence_gated", "fixture_identity_only"]
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    expected_source_schema_version: str | None
    expected_source_rule_version: str | None
    owner_validator_id: str
    owner_validator_version: str


@dataclass(frozen=True, slots=True)
class _FileObservation:
    relative_path: str
    signature: tuple[int, int, int, int]
    content_hash: str
    raw: bytes
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class _LoadedSource:
    relative_path: str
    content_hash: str
    parsed: dict[str, Any]
    modified_at: datetime
    declared_content_hash: str | None
    component_bindings: tuple[tuple[str, str], ...]


class _OwnerValidationWorkerResult(_StrictModel):
    """Strictly decode the isolated owner-validator worker result."""

    schema_version: Literal["policyos.runtime.governed_projection.owner_validation.v2"]
    projection_id: ProjectionId
    validator_id: str
    validator_version: str
    status: Literal["passed", "failed"]
    bound_aggregate_identity: str
    bound_source_identities: dict[str, str]
    bound_projection_payload_hash: str
    semantic_projection_hash: str | None
    semantic_projection_hash_rule_version: str | None
    dependency_aggregate_identity: str
    dependency_bindings: dict[str, str]
    issue_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _OwnerValidationCacheEntry:
    validation: ProjectionSourceValidation
    dependency_bindings: tuple[tuple[str, str], ...]


class _InvalidProjectionLoadError(ValueError):
    """Carry present source identity when decoding or composite loading fails."""

    def __init__(self, loaded: _LoadedSource, reason: str) -> None:
        self.loaded = loaded
        super().__init__(reason)


_COMMON_NOT_PUBLIC = (
    "public_claim",
    "publication_authority",
    "audience_authorization",
)

_DEFINITIONS: tuple[_ProjectionDefinition, ...] = (
    _ProjectionDefinition(
        ProjectionId.DEPTH_N_CYCLE_BOARD,
        "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("cycle_board_domain_runs", "terminal_distributions", "recorded_evidence_classes"),
        (*_COMMON_NOT_PUBLIC, "recompute_generation_cycle_semantics"),
        "policyos.policy_design_case.gy_n10.depth_n_universality.v1",
        "policyos.layer3.gy.n10.depth_n_universality.v1",
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract",
        "policyos.policy_design_case.gy_n10.depth_n_universality.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.VALUE_GATE,
        "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("value_denominators", "advisor_receipts", "value_outer_set_contract_proofs"),
        (*_COMMON_NOT_PUBLIC, "method_validity"),
        "policyos.policy_design_case.layer3_gy.value_gate_contract.v2",
        "policyos.layer3.gy.n8.value_gate.v2",
        "tools.quality.validation.check_layer3_gy_value_gate_contract:validate_payload",
        "policyos.policy_design_case.layer3_gy.value_gate_contract.v2",
    ),
    _ProjectionDefinition(
        ProjectionId.GENERATION_CYCLE_DISPOSITION,
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json",
        "json",
        "required",
        AudienceClass.EXPERT,
        ("generation_cycle_task_disposition", "known_residuals"),
        _COMMON_NOT_PUBLIC,
        "policyos.policy_design_case.layer3_gy.generation_cycle_disposition_ledger.v1",
        None,
        "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger:validate_ledger",
        "policyos.policy_design_case.layer3_gy.generation_cycle_disposition_ledger.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.ENGINE_CENSUS,
        "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json",
        "json",
        "required",
        AudienceClass.EXPERT,
        ("engine_census_summary", "critical_findings"),
        (*_COMMON_NOT_PUBLIC, "row_level_engine_export"),
        "policyos.policy_design_case.layer3_gy_engine_census.v1",
        "policyos.layer3.gy.engine_reality_census.v1",
        "tools.quality.validation.check_layer3_gy_engine_census:validate",
        "policyos.policy_design_case.layer3_gy_engine_census.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.FORK_B_RELATION_CENSUS,
        "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("fork_b_relation_counts", "coverage_manifest", "transport_floor"),
        (*_COMMON_NOT_PUBLIC, "relation_table_export"),
        "policyos.gy_n10.cg1_l2_prior_census.compact.v1",
        "policyos.layer3.gy.n10.cg1_relation_extension.v1",
        "tools.quality.validation.check_layer3_gy_n10_cg1_l2_relation_census:_validate",
        "policyos.gy_n10.cg1_l2_prior_census.compact.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.ACQUISITION_ROUTING_CONTRACT,
        "architecture/policy_design_case/layer3_gy_acquisition_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("acquisition_receipts", "fail_closed_acquisition_behavior"),
        (*_COMMON_NOT_PUBLIC, "source_family_satisfaction"),
        "policyos.policy_design_case.layer3_gy.acquisition_contract.v1",
        None,
        "tools.quality.validation.check_layer3_gy_acquisition_contract:validate_payload",
        "policyos.policy_design_case.layer3_gy.acquisition_contract.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.N13A_ACQUISITION_CENSUS,
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "json",
        "presence_gated",
        AudienceClass.MACHINE,
        ("acquisition_family_scorecards", "metric_resolution", "route_evidence"),
        (*_COMMON_NOT_PUBLIC, "closeout_pass"),
        "policyos.policy_design_case.gy_n13a.acquisition_census.v1",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
        "tools.quality.validation.check_layer3_gy_n13a_acquisition_census:main",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.N13A_LIVE_PROBE_JOURNAL,
        "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
        "json",
        "presence_gated",
        AudienceClass.EXPERT,
        ("live_probe_records", "family_receipts", "selection_plan"),
        (*_COMMON_NOT_PUBLIC, "source_success_inference"),
        "policyos.layer3.gy.n13a.live_probe_journal.v1",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
        "tools.quality.validation.check_layer3_gy_n13a_acquisition_census:main",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.ACQUISITION_GROWTH,
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "acquisition_growth",
        "presence_gated",
        AudienceClass.EXPERT,
        ("acquisition_growth_audit_history", "acquisition_gap_shape"),
        (*_COMMON_NOT_PUBLIC, "current_action_authority", "execute_acquisition"),
        "policyos.policy_design_case.gy_n13a.acquisition_census.v1",
        "policyos.layer3.gy.n13a.acquisition_census.v1",
        "polisyos.runtime.http.services."
        "governed_projection_validation_worker:validate_acquisition_growth",
        "policyos.runtime.acquisition_growth_projection.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.CAPABILITY_REALITY,
        "architecture/policy_design_case/capability_reality_report.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("reported_capability_readiness", "reported_blockers", "ratchet_integrity"),
        (*_COMMON_NOT_PUBLIC, "recompute_capability_readiness"),
        "policyos.runtime.policy_design_case.capability_ratchet.v1",
        None,
        "tools.quality.validation.check_policy_design_case_capability_ratchet:validate_capability_reality_report",
        "policyos.runtime.policy_design_case.capability_ratchet.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.CLUSTER_OWNERSHIP,
        "architecture/policy_design_case/cluster_ownership_map.toml",
        "toml",
        "required",
        AudienceClass.EXPERT,
        ("cluster_cell_ownership", "ratchet_state", "authority_firewall"),
        (*_COMMON_NOT_PUBLIC, "ownership_reassignment"),
        "policyos.policy_design_case.cluster_ownership_map.v1",
        None,
        "tools.quality.validation.check_policy_design_case_cluster_ownership_map:validate_cluster_ownership_map",
        "policyos.policy_design_case.cluster_ownership_map.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.LAYER3_HEALTH_METRICS,
        "architecture/policy_design_case/layer3_health_metric_ledgers.toml",
        "toml",
        "required",
        AudienceClass.MACHINE,
        ("recorded_health_metric_freezes", "metric_update_rules"),
        (*_COMMON_NOT_PUBLIC, "metric_recomputation"),
        "policyos.policy_design_case.layer3_g0_discovery_search.v2",
        "policyos.layer3.g0.discovery_search_free_growth.v2",
        "polisyos.runtime.quality.proving_ground.pre_adapter_grounding_inventory:HealthMetricLedger",
        "policyos.policy_design_case.layer3_g0_discovery_search.v2",
    ),
    _ProjectionDefinition(
        ProjectionId.LEGACY_PROVING_GROUND,
        "tests/fixtures/universal-corpus/manifest.json",
        "proving_ground",
        "fixture_identity_only",
        AudienceClass.EXPERT,
        ("legacy_case_identity", "fixture_semantic_expectation"),
        (
            *_COMMON_NOT_PUBLIC,
            "readiness",
            "runtime_outcome",
            "admissibility",
        ),
        "policyos.universal_corpus_manifest.v1",
        None,
        "polisyos.corpus:load_universal_corpus_fixtures",
        "policyos.universal_corpus_manifest.v1",
    ),
    _ProjectionDefinition(
        ProjectionId.SURFACE_READINESS,
        "architecture/atlas_surfaces/surface-readiness-ledger.json",
        "json",
        "presence_gated",
        AudienceClass.MACHINE,
        ("validated_surface_readiness_entries",),
        (*_COMMON_NOT_PUBLIC, "derive_readiness_from_route_presence"),
        None,
        None,
        "unregistered:surface-readiness-owner-validator",
        "unregistered",
    ),
)

_DEFINITION_BY_ID = {definition.projection_id: definition for definition in _DEFINITIONS}

_PAYLOAD_MODEL_BY_ID: dict[ProjectionId, type[_StrictModel]] = {
    ProjectionId.DEPTH_N_CYCLE_BOARD: DepthNCycleBoardPayload,
    ProjectionId.VALUE_GATE: ValueGatePayload,
    ProjectionId.GENERATION_CYCLE_DISPOSITION: GenerationCycleDispositionPayload,
    ProjectionId.ENGINE_CENSUS: EngineCensusPayload,
    ProjectionId.FORK_B_RELATION_CENSUS: ForkBRelationCensusPayload,
    ProjectionId.ACQUISITION_ROUTING_CONTRACT: AcquisitionRoutingPayload,
    ProjectionId.N13A_ACQUISITION_CENSUS: N13AAcquisitionCensusPayload,
    ProjectionId.N13A_LIVE_PROBE_JOURNAL: N13ALiveProbeJournalPayload,
    ProjectionId.ACQUISITION_GROWTH: AcquisitionGrowthPayload,
    ProjectionId.CAPABILITY_REALITY: CapabilityRealityPayload,
    ProjectionId.CLUSTER_OWNERSHIP: ClusterOwnershipPayload,
    ProjectionId.LAYER3_HEALTH_METRICS: Layer3HealthMetricsPayload,
    ProjectionId.LEGACY_PROVING_GROUND: LegacyProvingGroundPayload,
    ProjectionId.SURFACE_READINESS: SurfaceReadinessPayload,
}

_OWNER_VALIDATION_CACHE: dict[
    tuple[str, ProjectionId, str, tuple[tuple[str, str], ...], str],
    _OwnerValidationCacheEntry,
] = {}
_OWNER_VALIDATION_LOCK = Lock()
_OWNER_VALIDATION_TIMEOUT_SECONDS = 120


def _source_schema_version(source: dict[str, Any]) -> str | None:
    direct = _optional_string(source.get("schema_version"))
    if direct is not None:
        return direct
    manifest = source.get("manifest")
    if isinstance(manifest, dict):
        return _optional_string(manifest.get("schema_version"))
    return None


def _component_dependency_bindings(loaded: _LoadedSource) -> dict[str, str]:
    return {path: f"file:{content_hash}" for path, content_hash in loaded.component_bindings}


def _not_run_source_validation(
    loaded: _LoadedSource,
    *issue_codes: str,
) -> ProjectionSourceValidation:
    dependency_bindings = _component_dependency_bindings(loaded)
    return ProjectionSourceValidation(
        validator_id="polisyos.runtime.http.services.governed_projections:source_projection",
        validator_version="policyos.runtime.governed_projection.v1",
        status="not_run",
        bound_artifact_content_hash=loaded.content_hash,
        bound_dependency_aggregate_identity=hash_export_projection(dependency_bindings),
        bound_dependency_count=len(dependency_bindings),
        issue_codes=tuple(sorted(set(issue_codes))),
    )


def _owner_bridge_failure(
    loaded: _LoadedSource,
    *issue_codes: str,
) -> ProjectionSourceValidation:
    dependency_bindings = _component_dependency_bindings(loaded)
    return ProjectionSourceValidation(
        validator_id=(
            "polisyos.runtime.http.services.governed_projection_validation_worker:main"
        ),
        validator_version="policyos.runtime.governed_projection.owner_validation.v2",
        status="failed",
        bound_artifact_content_hash=loaded.content_hash,
        bound_dependency_aggregate_identity=hash_export_projection(dependency_bindings),
        bound_dependency_count=len(dependency_bindings),
        issue_codes=tuple(sorted(set(issue_codes))),
    )


def _run_owner_validation(
    *,
    repository_root: Path,
    definition: _ProjectionDefinition,
    loaded: _LoadedSource,
    payload: _StrictModel,
) -> ProjectionSourceValidation:
    observed_schema = _source_schema_version(loaded.parsed)
    if (
        definition.expected_source_schema_version is not None
        and observed_schema != definition.expected_source_schema_version
    ):
        return _not_run_source_validation(
            loaded,
            "source_schema_version_unrecognized",
        )
    observed_rule = _optional_string(loaded.parsed.get("rule_version"))
    if (
        definition.expected_source_rule_version is not None
        and observed_rule != definition.expected_source_rule_version
    ):
        return _not_run_source_validation(
            loaded,
            "source_rule_version_unrecognized",
        )
    resolved_root = repository_root.resolve()
    payload_data = payload.model_dump(mode="json")
    payload_hash = hash_export_projection(payload_data)
    cache_key = (
        str(resolved_root),
        definition.projection_id,
        loaded.content_hash,
        loaded.component_bindings,
        payload_hash,
    )
    cached = _OWNER_VALIDATION_CACHE.get(cache_key)
    if cached is not None and dependency_manifest_matches(
        resolved_root,
        dict(cached.dependency_bindings),
    ):
        return cached.validation
    with _OWNER_VALIDATION_LOCK:
        cached = _OWNER_VALIDATION_CACHE.get(cache_key)
        if cached is not None and dependency_manifest_matches(
            resolved_root,
            dict(cached.dependency_bindings),
        ):
            return cached.validation
        _OWNER_VALIDATION_CACHE.pop(cache_key, None)
        request = {
            "projection_id": definition.projection_id.value,
            "repository_root": str(resolved_root),
            "component_bindings": dict(loaded.component_bindings),
            "projection_payload": payload_data,
        }
        worker_path = Path(__file__).with_name("governed_projection_validation_worker.py")
        environment = os.environ.copy()
        source_root = Path(__file__).resolve().parents[4]
        python_paths = [str(source_root), str(source_root.parent)]
        existing_pythonpath = environment.get("PYTHONPATH")
        if existing_pythonpath:
            python_paths.append(existing_pythonpath)
        environment["PYTHONPATH"] = os.pathsep.join(python_paths)
        try:
            completed = subprocess.run(  # noqa: S603 - fixed interpreter and worker argv
                [sys.executable, str(worker_path)],
                cwd=repository_root,
                env=environment,
                input=json.dumps(request, separators=(",", ":"), sort_keys=True),
                capture_output=True,
                check=False,
                text=True,
                timeout=_OWNER_VALIDATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _owner_bridge_failure(
                loaded,
                f"owner_validator_{type(exc).__name__}",
            )
        if completed.returncode != 0:
            return _owner_bridge_failure(
                loaded,
                "owner_validator_process_failed",
            )
        try:
            result = _OwnerValidationWorkerResult.model_validate_json(completed.stdout)
        except (ValueError, TypeError):
            return _owner_bridge_failure(
                loaded,
                "owner_validator_receipt_invalid",
            )
        expected_bindings = dict(loaded.component_bindings)
        expected_dependency_bindings = _component_dependency_bindings(loaded)
        receipt_mismatch = (
            result.projection_id is not definition.projection_id
            or result.validator_id != definition.owner_validator_id
            or result.validator_version != definition.owner_validator_version
            or result.bound_aggregate_identity != hash_export_projection(expected_bindings)
            or result.bound_source_identities != expected_bindings
            or result.bound_projection_payload_hash != payload_hash
            or result.dependency_aggregate_identity
            != hash_export_projection(result.dependency_bindings)
            or any(
                result.dependency_bindings.get(path) != identity
                for path, identity in expected_dependency_bindings.items()
            )
        )
        if receipt_mismatch:
            return _owner_bridge_failure(
                loaded,
                "owner_validator_receipt_mismatch",
            )
        validation = ProjectionSourceValidation(
            validator_id=result.validator_id,
            validator_version=result.validator_version,
            status=result.status,
            bound_artifact_content_hash=loaded.content_hash,
            bound_dependency_aggregate_identity=result.dependency_aggregate_identity,
            bound_dependency_count=len(result.dependency_bindings),
            semantic_projection_hash=result.semantic_projection_hash,
            semantic_projection_hash_rule_version=(
                result.semantic_projection_hash_rule_version
            ),
            issue_codes=result.issue_codes,
        )
        if validation.status == "passed":
            _OWNER_VALIDATION_CACHE[cache_key] = _OwnerValidationCacheEntry(
                validation=validation,
                dependency_bindings=tuple(sorted(result.dependency_bindings.items())),
            )
        return validation


class GovernedProjectionService:
    """Project governed files lazily and cache their parsed content by SHA-256."""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root
        self._path_cache: dict[Path, _FileObservation] = {}
        self._parsed_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._projection_cache: dict[tuple[ProjectionId, str], bytes] = {}

    def catalog(self) -> tuple[ProjectionCatalogEntry, ...]:
        """Return the full denominator without touching artifact bytes."""
        return tuple(
            ProjectionCatalogEntry(
                projection_id=definition.projection_id,
                expected_source_path=definition.source_path,
                source_policy=definition.source_policy,
                intended_audience=definition.intended_audience,
                authoritative_for=definition.authoritative_for,
                may_not_use_for=definition.may_not_use_for,
                expected_source_schema_version=definition.expected_source_schema_version,
                expected_source_rule_version=definition.expected_source_rule_version,
                owner_validator_id=definition.owner_validator_id,
                owner_validator_version=definition.owner_validator_version,
                stable_address=_stable_address(definition.projection_id),
            )
            for definition in _DEFINITIONS
        )

    def get(
        self,
        projection_id: ProjectionId | str,
        *,
        artifact_content_hash: str | None = None,
        projection_hash: str | None = None,
        source_dependency_hash: str | None = None,
        source_as_of: datetime | None = None,
    ) -> GovernedProjectionPacket:
        """Return one packet and optionally enforce byte and projection replay pins."""
        resolved_id = ProjectionId(projection_id)
        definition = _DEFINITION_BY_ID[resolved_id]
        observed_at = datetime.now(UTC)
        try:
            loaded = self._load(definition)
        except FileNotFoundError:
            packet = self._absence_packet(
                definition,
                reason=f"governed source is absent: {definition.source_path}",
                observed_at=observed_at,
            )
        except _InvalidProjectionLoadError as exc:
            packet = self._invalid_packet(
                definition,
                loaded=exc.loaded,
                reason=str(exc),
                observed_at=observed_at,
                validation=_not_run_source_validation(
                    exc.loaded,
                    "source_decode_or_composite_load_failed",
                ),
            )
        else:
            try:
                payload = self._project(definition, loaded)
            except (InvalidProjectionSourceError, KeyError, TypeError, ValueError) as exc:
                packet = self._invalid_packet(
                    definition,
                    loaded=loaded,
                    reason=str(exc),
                    observed_at=observed_at,
                    validation=_not_run_source_validation(
                        loaded,
                        "projection_contract_invalid",
                    ),
                )
            else:
                validation = _run_owner_validation(
                    repository_root=self._repository_root,
                    definition=definition,
                    loaded=loaded,
                    payload=payload,
                )
                if validation.status != "passed":
                    packet = self._invalid_packet(
                        definition,
                        loaded=loaded,
                        reason=("owner validation failed: " + ", ".join(validation.issue_codes)),
                        observed_at=observed_at,
                        validation=validation,
                    )
                else:
                    resolved_projection_hash = validation.semantic_projection_hash
                    if resolved_projection_hash is None:  # guarded by the receipt model
                        raise RuntimeError("passed owner receipt omitted semantic projection hash")
                    as_of, basis = _resolve_as_of(loaded.parsed, loaded.modified_at)
                    source = ProjectionSourceIdentity(
                        relative_path=loaded.relative_path,
                        artifact_content_hash=loaded.content_hash,
                        declared_content_hash=loaded.declared_content_hash,
                        validation=validation,
                        related_artifact_bindings=_related_artifact_bindings(
                            resolved_id,
                            loaded,
                        ),
                    )
                    packet = AvailableGovernedProjectionPacket(
                        projection_id=resolved_id,
                        availability=ProjectionAvailability.AVAILABLE,
                        intended_audience=definition.intended_audience,
                        authoritative_for=definition.authoritative_for,
                        may_not_use_for=definition.may_not_use_for,
                        source=source,
                        source_dependency_hash=(
                            validation.bound_dependency_aggregate_identity
                        ),
                        source_schema_version=_source_schema_version(loaded.parsed),
                        source_rule_version=_optional_string(loaded.parsed.get("rule_version")),
                        projection_hash=resolved_projection_hash,
                        as_of=as_of,
                        freshness=ProjectionFreshness(
                            state="observed",
                            basis=basis,
                            observed_at=observed_at,
                            source_as_of=as_of,
                        ),
                        stable_address=_stable_address(resolved_id),
                        replay_address=_replay_address(
                            resolved_id,
                            artifact_content_hash=source.artifact_content_hash,
                            projection_hash=resolved_projection_hash,
                            source_dependency_hash=(
                                validation.bound_dependency_aggregate_identity
                            ),
                            source_as_of=as_of,
                        ),
                        payload=payload,
                    )
        _enforce_replay_pins(
            packet,
            artifact_content_hash=artifact_content_hash,
            projection_hash=projection_hash,
            source_dependency_hash=source_dependency_hash,
            source_as_of=source_as_of,
        )
        return packet

    def _load(self, definition: _ProjectionDefinition) -> _LoadedSource:
        if definition.source_format == "acquisition_growth":
            n13a_paths = (
                definition.source_path,
                "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
                "architecture/policy_design_case/"
                "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json",
            )
            observations = {path: self._read_file(path) for path in n13a_paths}
            census = self._parse(observations[n13a_paths[0]], "json")
            journal = self._parse(observations[n13a_paths[1]], "json")
            carrier = self._parse(observations[n13a_paths[2]], "json")
            lifecycle_path = (
                "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
            )
            lifecycle_observation = self._read_file(lifecycle_path)
            lifecycle = self._parse(lifecycle_observation, "json")
            registrations = _required_list(lifecycle, "registrations")
            component_observations = dict(observations)
            component_observations[lifecycle_path] = lifecycle_observation
            for registration in registrations:
                row = _mapping(registration, "registrations[]")
                path = _required_string(row, "path")
                observed = self._read_file(path)
                status = _required_string(row, "registration_status")
                if status == "content_bound" and (
                    row.get("byte_sha256") != observed.content_hash
                    or row.get("byte_size") != len(observed.raw)
                ):
                    raise InvalidProjectionSourceError(
                        f"registered acquisition source drift: {path}"
                    )
                if status not in {"content_bound", "writer_managed"}:
                    raise InvalidProjectionSourceError(
                        f"registered acquisition status invalid: {path}"
                    )
                component_observations[path] = observed
            executor_path = (
                "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
            )
            reentry_path = "architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json"
            executor = self._parse(component_observations[executor_path], "json")
            reentry = self._parse(component_observations[reentry_path], "json")
            bindings = tuple(
                sorted(
                    (path, observed.content_hash)
                    for path, observed in component_observations.items()
                )
            )
            return _LoadedSource(
                relative_path="acquisition-growth:N13a+N13b",
                content_hash=hash_export_projection(dict(bindings)),
                parsed={
                    "schema_version": census.get("schema_version"),
                    "rule_version": census.get("rule_version"),
                    "observed_at": census.get("observed_at"),
                    "census": census,
                    "journal": journal,
                    "carrier_liveness": carrier,
                    "executor_contract": executor,
                    "lifecycle_manifest": lifecycle,
                    "reentry_trace": reentry,
                },
                modified_at=max(
                    observed.modified_at for observed in component_observations.values()
                ),
                declared_content_hash=None,
                component_bindings=bindings,
            )
        if definition.source_format == "proving_ground":
            manifest_observation = self._read_file(definition.source_path)
            manifest: dict[str, Any] = {}
            try:
                manifest = self._parse(manifest_observation, "json")
                return self._load_proving_ground(
                    definition.source_path,
                    manifest_observation,
                    manifest,
                )
            except (FileNotFoundError, InvalidProjectionSourceError, ValueError) as exc:
                loaded = _LoadedSource(
                    relative_path=definition.source_path,
                    content_hash=manifest_observation.content_hash,
                    parsed={"manifest": manifest},
                    modified_at=manifest_observation.modified_at,
                    declared_content_hash=None,
                    component_bindings=(
                        (definition.source_path, manifest_observation.content_hash),
                    ),
                )
                raise _InvalidProjectionLoadError(loaded, str(exc)) from exc
        observation = self._read_file(definition.source_path)
        try:
            parsed = self._parse(observation, definition.source_format)
        except (InvalidProjectionSourceError, ValueError) as exc:
            loaded = _LoadedSource(
                relative_path=definition.source_path,
                content_hash=observation.content_hash,
                parsed={},
                modified_at=observation.modified_at,
                declared_content_hash=None,
                component_bindings=((definition.source_path, observation.content_hash),),
            )
            raise _InvalidProjectionLoadError(loaded, str(exc)) from exc
        component_bindings = [(definition.source_path, observation.content_hash)]
        if definition.projection_id is ProjectionId.N13A_ACQUISITION_CENSUS:
            try:
                journal = self._read_file(
                    "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
                )
            except FileNotFoundError:
                pass
            else:
                component_bindings.append((journal.relative_path, journal.content_hash))
        return _LoadedSource(
            relative_path=definition.source_path,
            content_hash=observation.content_hash,
            parsed=parsed,
            modified_at=observation.modified_at,
            declared_content_hash=_declared_content_hash(parsed),
            component_bindings=tuple(sorted(component_bindings)),
        )

    def _read_file(self, relative_path: str) -> _FileObservation:
        path = self._repository_root / relative_path
        stat = path.stat()
        signature = (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
        cached = self._path_cache.get(path)
        if cached is not None and cached.signature == signature:
            return cached
        raw = path.read_bytes()
        stable_stat = path.stat()
        stable_signature = (
            stable_stat.st_ino,
            stable_stat.st_mtime_ns,
            stable_stat.st_ctime_ns,
            stable_stat.st_size,
        )
        if stable_signature != signature:
            raw = path.read_bytes()
            stable_stat = path.stat()
            stable_signature = (
                stable_stat.st_ino,
                stable_stat.st_mtime_ns,
                stable_stat.st_ctime_ns,
                stable_stat.st_size,
            )
        observation = _FileObservation(
            relative_path=relative_path,
            signature=stable_signature,
            content_hash=_sha256(raw),
            raw=raw,
            modified_at=datetime.fromtimestamp(stable_stat.st_mtime, tz=UTC),
        )
        self._path_cache[path] = observation
        return observation

    def _parse(
        self,
        observation: _FileObservation,
        source_format: Literal["json", "toml", "proving_ground", "acquisition_growth"],
    ) -> dict[str, Any]:
        cache_key = (observation.content_hash, source_format)
        cached = self._parsed_cache.get(cache_key)
        if cached is not None:
            return cached
        if source_format == "json":
            value = json.loads(observation.raw)
        elif source_format == "toml":
            value = tomllib.loads(observation.raw.decode("utf-8"))
        else:  # pragma: no cover - composite sources have a dedicated loader
            raise AssertionError("proving-ground sources use the composite loader")
        if not isinstance(value, dict):
            raise InvalidProjectionSourceError(
                f"{observation.relative_path} must contain a top-level object"
            )
        normalized = _mapping(_json_ready(value), observation.relative_path)
        self._parsed_cache[cache_key] = normalized
        return normalized

    def _load_proving_ground(
        self,
        manifest_path: str,
        manifest_observation: _FileObservation,
        manifest: dict[str, Any],
    ) -> _LoadedSource:
        fixtures = _required_list(manifest, "fixtures")
        manifest_parent = Path(manifest_path).parent
        cases: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        content_bindings = {manifest_path: manifest_observation.content_hash}
        modified_at = manifest_observation.modified_at
        for fixture in fixtures:
            fixture_record = _mapping(fixture, "fixtures[]")
            relative_case_path = (
                manifest_parent / _required_string(fixture_record, "path")
            ).as_posix()
            case_observation = self._read_file(relative_case_path)
            case = self._parse(case_observation, "json")
            if case.get("case_id") != fixture_record.get("case_id"):
                raise InvalidProjectionSourceError(f"case_id mismatch for {relative_case_path}")
            identities.append(
                {
                    "case_id": fixture_record.get("case_id"),
                    "domain": fixture_record.get("domain"),
                    "split": fixture_record.get("split"),
                    "authority_levels": fixture_record.get("authority_levels", []),
                }
            )
            cases.append(case)
            content_bindings[relative_case_path] = case_observation.content_hash
            modified_at = max(modified_at, case_observation.modified_at)
        parsed = {
            "manifest": manifest,
            "fixture_identities": identities,
            "fixture_records": cases,
        }
        return _LoadedSource(
            relative_path=f"{manifest_path}+cases/*",
            content_hash=hash_export_projection(content_bindings),
            parsed=parsed,
            modified_at=modified_at,
            declared_content_hash=None,
            component_bindings=tuple(sorted(content_bindings.items())),
        )

    def _project(
        self,
        definition: _ProjectionDefinition,
        loaded: _LoadedSource,
    ) -> _StrictModel:
        cache_key = (definition.projection_id, loaded.content_hash)
        payload_model = _PAYLOAD_MODEL_BY_ID[definition.projection_id]
        cached = self._projection_cache.get(cache_key)
        if cached is not None:
            return payload_model.model_validate_json(cached)
        projector = _PROJECTORS[definition.projection_id]
        raw_payload = _mapping(
            _json_ready(projector(loaded.parsed)),
            "projection_payload",
        )
        payload = payload_model.model_validate(raw_payload)
        payload_data = payload.model_dump(mode="json")
        payload_json = json.dumps(
            payload_data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._projection_cache[cache_key] = payload_json
        return payload_model.model_validate_json(payload_json)

    def _absence_packet(
        self,
        definition: _ProjectionDefinition,
        *,
        reason: str,
        observed_at: datetime,
    ) -> ArtifactMissingGovernedProjectionPacket:
        return ArtifactMissingGovernedProjectionPacket(
            projection_id=definition.projection_id,
            availability=ProjectionAvailability.ARTIFACT_MISSING,
            intended_audience=definition.intended_audience,
            authoritative_for=definition.authoritative_for,
            may_not_use_for=definition.may_not_use_for,
            as_of=observed_at,
            freshness=ProjectionFreshness(
                state="artifact_missing",
                basis="request_observation",
                observed_at=observed_at,
            ),
            stable_address=_stable_address(definition.projection_id),
            absence_reason=reason,
        )

    def _invalid_packet(
        self,
        definition: _ProjectionDefinition,
        *,
        loaded: _LoadedSource,
        reason: str,
        observed_at: datetime,
        validation: ProjectionSourceValidation,
    ) -> InvalidGovernedProjectionPacket:
        as_of, basis = _resolve_as_of(loaded.parsed, loaded.modified_at)
        return InvalidGovernedProjectionPacket(
            projection_id=definition.projection_id,
            availability=ProjectionAvailability.INVALID_SOURCE,
            intended_audience=definition.intended_audience,
            authoritative_for=definition.authoritative_for,
            may_not_use_for=definition.may_not_use_for,
            source=ProjectionSourceIdentity(
                relative_path=loaded.relative_path,
                artifact_content_hash=loaded.content_hash,
                declared_content_hash=loaded.declared_content_hash,
                validation=validation,
                related_artifact_bindings=(),
            ),
            source_schema_version=_source_schema_version(loaded.parsed),
            source_rule_version=_optional_string(loaded.parsed.get("rule_version")),
            as_of=as_of,
            freshness=ProjectionFreshness(
                state="invalid_source",
                basis=basis,
                observed_at=observed_at,
                source_as_of=as_of,
            ),
            stable_address=_stable_address(definition.projection_id),
            absence_reason=reason,
        )


def _depth_n_route_reference(witness: dict[str, Any]) -> dict[str, Any] | None:
    raw_reference = witness.get("acquisition_route")
    if raw_reference is None:
        return None
    try:
        reference = DepthNAcquisitionRouteReference.model_validate(raw_reference)
    except ValueError as exc:
        raise InvalidProjectionSourceError(f"acquisition_route invalid: {exc}") from exc
    return reference.model_dump(mode="json")


def _depth_n_acquisition_economics(
    run: dict[str, Any],
    *,
    route_reference: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve inline planner contents only when their producer hash matches."""

    try:
        stage_trace = _mapping(run.get("stage_trace"), "stage_trace")
        acquisition = _mapping(stage_trace.get("acquisition"), "stage_trace.acquisition")
        planner_report_content_hash = _required_string(
            acquisition,
            "planner_report_content_hash",
        )
        if (
            route_reference is not None
            and route_reference["planner_report_content_hash"] != planner_report_content_hash
        ):
            return None
        terminal = _mapping(run.get("terminal"), "terminal")
        costed_plan = _mapping(terminal.get("costed_plan"), "terminal.costed_plan")
        planner_report = _mapping(
            costed_plan.get("canonical_planner_report"),
            "canonical_planner_report",
        )
        if gy_content_hash(planner_report) != planner_report_content_hash:
            return None
        acquisition_records = _required_list(planner_report, "acquisition_records")
        if len(acquisition_records) != 1:
            return None
        acquisition_record = _mapping(
            acquisition_records[0],
            "canonical_planner_report.acquisition_records[0]",
        )
        if (
            route_reference is not None
            and _required_string(acquisition_record, "gap_id")
            != route_reference["requirement_gap_id"]
        ):
            return None
        recommended_strategy = _required_string(acquisition_record, "recommended_strategy")
        strategy_records = [
            _mapping(item, "acquisition_record.strategy_records[]")
            for item in _required_list(acquisition_record, "strategy_records")
        ]
        matching_strategies = [
            item for item in strategy_records if item.get("strategy") == recommended_strategy
        ]
        if len(matching_strategies) != 1:
            return None
        strategy_record = matching_strategies[0]
        next_actions = [
            _mapping(item, "acquisition_record.next_actions[]")
            for item in _required_list(acquisition_record, "next_actions")
        ]
        if len(next_actions) != 1:
            return None
        next_action = next_actions[0]
        economics = DepthNAcquisitionEconomicsProjection(
            planner_report_content_hash=planner_report_content_hash,
            planner_status=_required_string(planner_report, "status"),
            missing_requirement_fields=tuple(
                _required_non_empty_string_list(
                    acquisition_record,
                    "missing_requirement_fields",
                )
            ),
            recommended_strategy=recommended_strategy,
            expected_cost=_required_value(strategy_record, "voi_expected_cost"),
            expected_voi=_required_value(strategy_record, "voi_expected_value"),
            voi_rank=_required_value(strategy_record, "voi_rank"),
            decision_owner_ref=_required_string(acquisition_record, "decision_owner_ref"),
            producer_expected=_required_string(acquisition_record, "producer_expected"),
            next_action=_required_string(next_action, "action"),
        )
    except (InvalidProjectionSourceError, ValueError, TypeError):
        return None
    return economics.model_dump(mode="json")


def _project_depth_n(source: dict[str, Any]) -> dict[str, Any]:
    domain_runs = _required_mapping(source, "domain_runs")
    projected_runs: dict[str, Any] = {}
    for domain, raw_run in sorted(domain_runs.items()):
        run = _mapping(raw_run, f"domain_runs.{domain}")
        witness = _required_mapping(run, "evidence_witness")
        evidence_class = _required_string(witness, "kind")
        terminal = _required_mapping(run, "terminal")
        weakest_links = _required_list(terminal, "blocking_obligations")
        terminal_distribution = _required_mapping(run, "terminal_distribution")
        try:
            design_problem = DesignProblem.model_validate(_required_mapping(run, "design_problem"))
        except ValueError as exc:
            raise InvalidProjectionSourceError(f"design_problem invalid: {exc}") from exc
        route_reference = _depth_n_route_reference(witness)
        acquisition_economics = _depth_n_acquisition_economics(
            run,
            route_reference=route_reference,
        )
        projected_runs[str(domain)] = {
            "generation_cycle_run_id": _required_value(run, "generation_cycle_run_id"),
            "design_problem_ref": _required_value(run, "design_problem_ref"),
            "design_problem": design_problem,
            "domain_role": _required_value(run, "domain_role"),
            "search_terminal_kind": _required_string(terminal, "kind"),
            "terminal_distribution": terminal_distribution,
            "evidence_class": evidence_class,
            "evidence_witness": witness,
            "weakest_links": weakest_links,
            "acquisition_route": route_reference,
            "acquisition_economics": acquisition_economics,
        }
    return {
        "depth_evidence": _required_mapping(source, "depth_evidence"),
        "domain_runs": projected_runs,
        "terminal_distributions": _required_mapping(source, "terminal_distributions"),
    }


def _project_value_gate(source: dict[str, Any]) -> dict[str, Any]:
    education = _required_mapping(source, "education_refusal")
    production = _required_mapping(source, "production_refusal")
    mutations = _required_list(source, "decisive_mutation_expectations")
    outer_set_contract = [
        item
        for item in mutations
        if "value_outer_set"
        in str(_mapping(item, "decisive_mutation_expectations[]").get("mutation_id", ""))
    ]
    if not outer_set_contract:
        raise InvalidProjectionSourceError("missing recorded ValueOuterSet contract proofs")
    return {
        "denominators": _required_mapping(source, "denominators"),
        "education_refusal": education,
        "production_refusal": production,
        "advisor_receipts": {
            "education": _required_value(education, "method_selection_receipt"),
            "production": _required_value(production, "method_selection_receipt"),
        },
        "value_outer_set_contract": outer_set_contract,
        "mode_gates": _required_mapping(source, "mode_gates"),
        "acquisition_routing": _required_value(source, "acquisition_routing"),
        "disposition": _required_value(source, "disposition"),
    }


def _select(source: dict[str, Any], *fields: str) -> dict[str, Any]:
    return {field: source[field] for field in fields if field in source}


def _required_projection_fields(
    source: dict[str, Any],
    *fields: str,
) -> dict[str, Any]:
    return {field: _required_value(source, field) for field in fields}


def _project_disposition(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "tasks",
        "owners",
        "task_owner_mapping",
        "bridge_artifacts",
        "method_availability_gate",
        "known_residuals",
        "parallel_world_reconciliation",
    )


def _project_engine_census(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "row_count",
        "execution_status_vocabulary",
        "critical_findings",
        "subcensus_summary",
        "gap_taxonomy_extensions",
        "verb_gap_consistency",
        "evidence_reproducibility",
        "discipline",
        "scope",
    )


def _project_fork_b(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "relation_counts",
        "relation_denominator_formula",
        "authority",
        "coverage_manifest",
        "certificate_summaries",
        "transport_floor",
        "transport_floor_rule",
        "known_bridge_limits",
        "normalization",
    )


def _project_acquisition_contract(source: dict[str, Any]) -> dict[str, Any]:
    projected = _required_projection_fields(
        source,
        "denominators",
        "positive_receipt",
        "no_result_receipt",
        "fail_closed_receipt",
        "fail_closed_probes",
        "grounding_acquisition_request",
        "recorded_rederive_inputs",
        "compute_economics",
        "known_residuals",
    )
    narrowed = _mapping(
        _without_acquisition_capture_provenance(projected),
        "acquisition_projection",
    )
    positive_receipt = narrowed.get("positive_receipt")
    if isinstance(positive_receipt, dict):
        narrowed["positive_receipt"] = serialization.artifact_self_identity_projection(
            positive_receipt
        )
    return narrowed


def _without_acquisition_capture_provenance(value: object) -> object:
    """Omit provenance envelopes outside the acquisition receipt projection."""

    if isinstance(value, dict):
        return {
            key: _without_acquisition_capture_provenance(item)
            for key, item in value.items()
            if key != "capture_provenance"
        }
    if isinstance(value, list):
        return [_without_acquisition_capture_provenance(item) for item in value]
    return value


def _project_n13a_census(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "catalog_identity",
        "projection_bindings",
        "family_scorecards",
        "metric_resolutions",
        "route_evidence",
        "growth_backlog",
        "fetch_plan_generation",
        "reverse_demand_residuals",
    )


def _project_n13a_journal(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "selection_plan",
        "family_receipts",
        "records",
    )


def _project_acquisition_growth(source: dict[str, Any]) -> dict[str, Any]:
    return build_acquisition_growth_projection(
        census=_required_mapping(source, "census"),
        journal=_required_mapping(source, "journal"),
        carrier_liveness=_required_mapping(source, "carrier_liveness"),
        executor_contract=_required_mapping(source, "executor_contract"),
        lifecycle_manifest=_required_mapping(source, "lifecycle_manifest"),
        reentry_trace=_required_mapping(source, "reentry_trace"),
    ).model_dump(mode="json")


def _project_capability_reality(source: dict[str, Any]) -> dict[str, Any]:
    return _required_projection_fields(
        source,
        "summary",
        "readiness",
        "capability_claims",
        "blockers",
        "issues",
        "chain_clusters",
        "ratchet_integrity_status",
        "debt_algebra",
    )


def _project_cluster_ownership(source: dict[str, Any]) -> dict[str, Any]:
    return {
        **_required_projection_fields(
            source,
            "status",
            "owner",
            "purpose",
            "ratchet_state_vocabulary",
            "required_clusters",
            "required_cell_fields",
            "capability_chain_steps",
            "stop_rule",
            "open_cell_closure",
            "handshake_graph",
            "architecture_core",
        ),
        "clusters": _required_mapping(source, "cell"),
    }


def _project_health_metrics(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "health_metric_ledgers": _required_list(source, "health_metric_ledgers"),
    }


def _project_proving_ground(source: dict[str, Any]) -> dict[str, Any]:
    identities = _required_list(source, "fixture_identities")
    records = _required_list(source, "fixture_records")
    if len(identities) != 13 or len(records) != 13:
        raise InvalidProjectionSourceError("legacy proving ground must contain 13 fixture records")
    projected_records = [
        _required_projection_fields(
            _mapping(record, "fixture_records[]"),
            "case_id",
            "title",
            "domain",
            "split",
            "schema_version",
            "intent",
            "input_intent_ref",
            "compilation_intent_text",
            "concept_spine_refs",
            "expected_adapter_bindings",
            "expected_claim_families",
            "expected_closeout_states",
            "expected_facets",
            "expected_obligation_graph",
            "expected_projection_truthfulness",
            "expected_requirement_specs",
            "expert_adjudication",
            "claim_evidence_annotations",
        )
        for record in records
    ]
    return {
        "fixture_authority": "fixture_only",
        "fixture_identities": identities,
        "fixture_records": projected_records,
        "runtime_outcomes": {
            "availability": "artifact_missing",
            "reason": "no persisted validator-confirmed 13-case runtime result is named",
        },
    }


def _project_surface_readiness(source: dict[str, Any]) -> dict[str, Any]:
    schema_version = _required_string(source, "schema_version")
    _required_string(source, "ledger_id")
    _required_string(source, "as_of")
    _required_string(source, "controlled_vocabulary_source")
    authority = _required_mapping(source, "authority")
    _required_non_empty_string_list(authority, "authoritative_for")
    _required_non_empty_string_list(authority, "may_not_use_for")
    entries = _required_list(source, "entries")
    if not entries:
        raise InvalidProjectionSourceError("entries must contain at least one record")
    raise InvalidProjectionSourceError(
        "surface readiness schema "
        f"{schema_version!r} is not a registered Revision-3-capable owner schema"
    )


_PROJECTORS = {
    ProjectionId.DEPTH_N_CYCLE_BOARD: _project_depth_n,
    ProjectionId.VALUE_GATE: _project_value_gate,
    ProjectionId.GENERATION_CYCLE_DISPOSITION: _project_disposition,
    ProjectionId.ENGINE_CENSUS: _project_engine_census,
    ProjectionId.FORK_B_RELATION_CENSUS: _project_fork_b,
    ProjectionId.ACQUISITION_ROUTING_CONTRACT: _project_acquisition_contract,
    ProjectionId.N13A_ACQUISITION_CENSUS: _project_n13a_census,
    ProjectionId.N13A_LIVE_PROBE_JOURNAL: _project_n13a_journal,
    ProjectionId.ACQUISITION_GROWTH: _project_acquisition_growth,
    ProjectionId.CAPABILITY_REALITY: _project_capability_reality,
    ProjectionId.CLUSTER_OWNERSHIP: _project_cluster_ownership,
    ProjectionId.LAYER3_HEALTH_METRICS: _project_health_metrics,
    ProjectionId.LEGACY_PROVING_GROUND: _project_proving_ground,
    ProjectionId.SURFACE_READINESS: _project_surface_readiness,
}


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidProjectionSourceError(f"{field} must be an object")
    return value


def _required_mapping(source: dict[str, Any], field: str) -> dict[str, Any]:
    if field not in source:
        raise InvalidProjectionSourceError(f"missing owner-recorded field: {field}")
    return _mapping(source[field], field)


def _required_value(source: dict[str, Any], field: str) -> object:
    if field not in source:
        raise InvalidProjectionSourceError(f"missing owner-recorded field: {field}")
    return source[field]


def _required_list(source: dict[str, Any], field: str) -> list[Any]:
    value = source.get(field)
    if not isinstance(value, list):
        raise InvalidProjectionSourceError(f"{field} must be an array")
    return value


def _required_non_empty_string_list(
    source: dict[str, Any],
    field: str,
) -> list[str]:
    value = _required_list(source, field)
    if not value or any(not isinstance(item, str) or not item for item in value):
        raise InvalidProjectionSourceError(f"{field} must contain non-empty strings")
    return value


def _required_string(source: dict[str, Any], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value:
        raise InvalidProjectionSourceError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _declared_content_hash(source: dict[str, Any]) -> str | None:
    for field in (
        "contract_content_hash",
        "content_hash",
        "census_digest",
    ):
        value = _optional_string(source.get(field))
        if value is not None:
            return value
    return None


def _related_artifact_bindings(
    projection_id: ProjectionId,
    loaded: _LoadedSource,
) -> tuple[ProjectionOwnerBinding, ...]:
    if projection_id is not ProjectionId.N13A_ACQUISITION_CENSUS:
        return ()
    journal_semantic_hash = _optional_string(loaded.parsed.get("journal_content_sha256"))
    journal_path = "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json"
    resolved_content_hash = dict(loaded.component_bindings).get(journal_path)
    if journal_semantic_hash is None or resolved_content_hash is None:
        return ()
    return (
        ProjectionOwnerBinding(
            binding_name="live_probe_journal_content_sha256",
            relative_path=journal_path,
            owner_semantic_hash=journal_semantic_hash,
            semantic_hash_rule_version=("policyos.layer3.gy.n13a.acquisition_census.v1"),
            resolved_artifact_content_hash=resolved_content_hash,
        ),
    )


def _resolve_as_of(
    source: dict[str, Any],
    modified_at: datetime,
) -> tuple[datetime, Literal["source_timestamp", "filesystem_mtime"]]:
    candidates = [source]
    manifest = source.get("manifest")
    if isinstance(manifest, dict):
        candidates.append(manifest)
    for candidate in candidates:
        for field in ("as_of", "observed_at", "generated_at", "generated", "timestamp"):
            parsed = _parse_datetime(candidate.get(field))
            if parsed is not None:
                return parsed, "source_timestamp"
    return modified_at, "filesystem_mtime"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_ready(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _stable_address(projection_id: ProjectionId) -> str:
    return f"{_PROJECTION_BASE_PATH}/{projection_id.value}"


def _replay_address(
    projection_id: ProjectionId,
    *,
    artifact_content_hash: str,
    projection_hash: str,
    source_dependency_hash: str,
    source_as_of: datetime,
) -> str:
    return build_export_replay_address(
        _stable_address(projection_id),
        {
            "artifact_content_hash": artifact_content_hash,
            "projection_hash": projection_hash,
            "source_dependency_hash": source_dependency_hash,
            "source_as_of": _replay_datetime(source_as_of),
        },
    )


def _enforce_replay_pins(
    packet: GovernedProjectionPacket,
    *,
    artifact_content_hash: str | None,
    projection_hash: str | None,
    source_dependency_hash: str | None,
    source_as_of: datetime | None,
) -> None:
    actual_artifact_hash = (
        packet.source.artifact_content_hash if packet.source is not None else None
    )
    if artifact_content_hash is not None and artifact_content_hash != actual_artifact_hash:
        raise ReplayPinMismatchError(
            "artifact_content_hash",
            expected=artifact_content_hash,
            actual=actual_artifact_hash,
        )
    if projection_hash is not None and projection_hash != packet.projection_hash:
        raise ReplayPinMismatchError(
            "projection_hash",
            expected=projection_hash,
            actual=packet.projection_hash,
        )
    if source_dependency_hash is not None and source_dependency_hash != (
        packet.source_dependency_hash
    ):
        raise ReplayPinMismatchError(
            "source_dependency_hash",
            expected=source_dependency_hash,
            actual=packet.source_dependency_hash,
        )
    if source_as_of is not None:
        expected_as_of = _normalize_datetime(source_as_of)
        actual_as_of = _normalize_datetime(packet.as_of)
        if expected_as_of != actual_as_of:
            raise ReplayPinMismatchError(
                "source_as_of",
                expected=_replay_datetime(expected_as_of),
                actual=_replay_datetime(actual_as_of),
            )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _replay_datetime(value: datetime) -> str:
    return _normalize_datetime(value).isoformat().replace("+00:00", "Z")


__all__ = [
    "CHANNEL_REGISTRY",
    "AudienceClass",
    "ChannelRegistryEntry",
    "ChannelRegistryResponse",
    "DepthNAcquisitionEconomicsProjection",
    "DepthNAcquisitionRouteReference",
    "DepthNCycleBoardPayload",
    "DepthNDomainRunProjection",
    "GovernedProjectionPacket",
    "GovernedProjectionService",
    "ProjectionAvailability",
    "ProjectionCatalogEntry",
    "ProjectionCatalogResponse",
    "ProjectionId",
    "ReplayPinMismatchError",
]
