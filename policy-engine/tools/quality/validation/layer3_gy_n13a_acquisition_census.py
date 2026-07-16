"""Typed evidence and read-only catalog primitives for the GY-N13a census.

This module owns the census boundary schema and the smallest read path needed to
identify the acquisition catalog.  It does not execute fetch plans, call connectors,
or write to the catalog.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "policyos.policy_design_case.gy_n13a.acquisition_census.v1"
RULE_VERSION = "policyos.layer3.gy.n13a.acquisition_census.v1"
CONTENT_HASH_EXCLUDED_FIELDS = frozenset({"capture_wall_time_seconds", "observed_at"})
EXECUTABLE_BINDING_TIERS = frozenset({"fetchable", "transport_ready"})
_FETCH_PLAN_FORBIDDEN_OWNERS = frozenset(
    {
        "FetchExecutor.execute",
        "FetchExecutor.preview",
        "connector.fetch",
        "run_orchestrated_ingestion",
        "canonical_store.write",
    }
)

_REQUIRED_CATALOG_COLUMNS: dict[str, frozenset[str]] = {
    "ds_datasets": frozenset({"id", "access_license", "access_auth_required", "execution_tier"}),
    "ds_distributions": frozenset(
        {
            "id",
            "dataset_id",
            "url",
            "connector_type",
            "profile_id",
            "quality_score",
            "parser_supported",
        }
    ),
    "ds_metric_bindings": frozenset(
        {
            "metric_id",
            "dataset_id",
            "distribution_id",
            "connector_id",
            "profile_id",
            "request_dataset_id",
            "confidence",
            "metric_inference_confidence",
            "default_filters",
            "execution_tier",
            "source",
        }
    ),
    "ds_observations": frozenset({"observation_id", "dataset_id", "raw_variable", "canonical_var"}),
    "ds_schema_profiles": frozenset(
        {
            "distribution_id",
            "dataset_id",
            "columns_json",
            "sample_row_count",
            "preview_sample_hash",
            "inference_mode",
            "parser_mode",
        }
    ),
    "ds_variable_alignments": frozenset(
        {
            "dataset_id",
            "raw_variable",
            "canonical_var",
            "method",
            "confidence",
            "evidence",
            "is_proxy",
            "proxy_penalty",
        }
    ),
}


class ResolutionStatus(StrEnum):
    """Owner-derived metric-to-canonical-variable resolution state."""

    EXACT = "resolves_exact"
    VIA_ALIGNMENT = "resolves_via_alignment"
    UNRESOLVED = "unresolved"


class DemandGapKind(StrEnum):
    """Typed reverse-denominator acquisition residual."""

    BINDING = "binding_gap"
    CONNECTOR = "connector_gap"


class ResolutionLimitation(StrEnum):
    """Typed limitation on dataset-level metric resolution evidence."""

    CATALOG_BINDING_FIELD_EDGE_MISSING = "catalog_binding_field_edge_missing"


class ResolutionScope(StrEnum):
    """Measured catalog granularity available for metric resolution."""

    DATASET_LEVEL_IDENTITY = "dataset_level_identity"
    DISTRIBUTION_FIELD_BOUND = "distribution_field_bound"


class RouteClass(StrEnum):
    """Evidence-derived class for an N10 acquisition route."""

    LOCAL_LIFT = "local_lift"
    LIVE_FETCHABLE = "live_fetchable"
    NOT_A_DATA_GAP = "not_a_data_gap"
    UNRESOLVED = "unresolved"


class LivenessState(StrEnum):
    """Typed shadow-characterization outcome."""

    ALIVE_CONFORMANT = "alive_conformant"
    ALIVE_SCHEMA_DRIFT = "alive_schema_drift"
    ALIVE_SCHEMA_UNVERIFIED = "alive_schema_unverified"
    DEAD = "dead"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    LICENSE_UNCLEAR = "license_unclear"
    RESPONSE_BUDGET_EXCEEDED = "response_budget_exceeded"
    TRANSPORT_ERROR = "transport_error"


class _StrictBoundaryModel(BaseModel):
    """Base configuration for evidence crossing the census boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CatalogIdentity(_StrictBoundaryModel):
    """Content identity and full-denominator summary of one catalog snapshot."""

    source_locator: str = Field(min_length=1)
    catalog_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_byte_size: int = Field(ge=1)
    table_row_counts: dict[str, int]
    binding_row_count: int = Field(ge=0)
    binding_metric_count: int = Field(ge=0)
    connector_family_count: int = Field(ge=0)
    execution_tier_counts: dict[str, int]

    @field_validator("table_row_counts", "execution_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)


class AlignmentCandidate(_StrictBoundaryModel):
    """One owner-recorded candidate alignment for a bound metric."""

    dataset_id: str = Field(min_length=1)
    raw_variable: str = Field(min_length=1)
    canonical_variable: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    is_proxy: bool
    proxy_penalty: float = Field(ge=0.0, le=1.0)
    method: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    bound_observation_edge_missing: bool


class MetricResolution(_StrictBoundaryModel):
    """Recomputed resolution row for one full-denominator catalog metric."""

    metric_id: str = Field(min_length=1)
    resolution_status: ResolutionStatus
    resolution_scope: ResolutionScope
    binding_count: int = Field(ge=1)
    binding_dataset_count: int = Field(ge=1)
    exact_observation_count: int = Field(ge=0)
    alignment_candidate_count: int = Field(ge=0)
    binding_tier_counts: dict[str, int]
    connector_ids: tuple[str, ...] = Field(min_length=1)
    exact_canonical_variable: str | None = None
    best_alignment: AlignmentCandidate | None = None
    alignment_candidates: tuple[AlignmentCandidate, ...] = ()
    alignment_ambiguous: bool = False
    proxy_only: bool = False
    limitations: tuple[ResolutionLimitation, ...] = ()

    @field_validator("binding_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)

    @model_validator(mode="after")
    def _status_must_match_evidence(self) -> Self:
        if sum(self.binding_tier_counts.values()) != self.binding_count:
            raise ValueError("binding tier counts must cover every binding row")
        if self.alignment_candidate_count != len(self.alignment_candidates):
            raise ValueError("alignment_candidate_count must match candidate evidence")
        expected_best = self.alignment_candidates[0] if self.alignment_candidates else None
        if self.best_alignment != expected_best:
            raise ValueError("best_alignment must be the first deterministic candidate")
        if self.alignment_ambiguous != (len(self.alignment_candidates) > 1):
            raise ValueError("alignment_ambiguous must be derived from candidate count")
        expected_proxy_only = bool(self.alignment_candidates) and all(
            candidate.is_proxy for candidate in self.alignment_candidates
        )
        if self.proxy_only != expected_proxy_only:
            raise ValueError("proxy_only must be derived from all owner alignments")
        expected_limitations = _resolution_limitations(
            scope=self.resolution_scope,
            status=self.resolution_status,
        )
        if self.limitations != expected_limitations:
            raise ValueError("limitations must be derived from dataset-level evidence")
        if any(
            candidate.canonical_variable != self.metric_id
            for candidate in self.alignment_candidates
        ):
            raise ValueError("alignment candidates must preserve metric identity")
        if self.resolution_status is ResolutionStatus.EXACT:
            if self.exact_canonical_variable != self.metric_id:
                raise ValueError("exact resolution requires exact_canonical_variable")
            if self.exact_observation_count < 1:
                raise ValueError("exact resolution requires a bound observation")
        elif self.resolution_status is ResolutionStatus.VIA_ALIGNMENT:
            if self.exact_canonical_variable is not None:
                raise ValueError("aligned resolution cannot carry an exact variable")
            if self.exact_observation_count != 0:
                raise ValueError("aligned resolution cannot carry exact observations")
            if not self.alignment_candidates:
                raise ValueError("aligned resolution requires best and candidate alignments")
        elif self.exact_observation_count != 0 or any(
            (
                self.exact_canonical_variable is not None,
                self.best_alignment is not None,
                bool(self.alignment_candidates),
                self.alignment_ambiguous,
                self.proxy_only,
                bool(self.limitations),
            )
        ):
            raise ValueError("unresolved metric cannot carry resolution evidence")
        return self


class DemandRequirement(_StrictBoundaryModel):
    """One unique cycle-relevant variable and every declared demand source."""

    variable_id: str = Field(min_length=1)
    demand_sources: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sources_are_unique_and_sorted(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("demand sources must be unique and sorted")
        return self


class DemandVariableEvidence(_StrictBoundaryModel):
    """Measured support for every member of the reverse demand denominator."""

    variable_id: str = Field(min_length=1)
    demand_sources: tuple[str, ...] = Field(min_length=1)
    local_observation_count: int = Field(ge=0)
    alignment_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    executable_binding_count: int = Field(ge=0)
    binding_tier_counts: dict[str, int]
    connector_ids: tuple[str, ...]
    best_binding_confidence: float = Field(ge=0.0, le=1.0)
    gap_kind: DemandGapKind | None

    @field_validator("binding_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)

    @model_validator(mode="after")
    def _gap_is_recomputed_from_binding_support(self) -> Self:
        if sum(self.binding_tier_counts.values()) != self.binding_count:
            raise ValueError("binding tier counts must cover every exact binding")
        if self.executable_binding_count > self.binding_count:
            raise ValueError("executable bindings cannot exceed all bindings")
        expected_gap = (
            DemandGapKind.BINDING
            if self.binding_count == 0
            else DemandGapKind.CONNECTOR
            if self.executable_binding_count == 0
            else None
        )
        if self.gap_kind is not expected_gap:
            raise ValueError("gap_kind must be recomputed from binding support")
        if self.binding_count == 0 and (self.connector_ids or self.best_binding_confidence != 0.0):
            raise ValueError("unbound demand cannot claim connector or confidence evidence")
        return self


class ReverseDemandResidual(_StrictBoundaryModel):
    """Cycle-relevant variable with no executable catalog support."""

    variable_id: str = Field(min_length=1)
    gap_kind: DemandGapKind
    demand_sources: tuple[str, ...] = Field(min_length=1)
    local_observation_count: int = Field(ge=0)
    alignment_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    executable_binding_count: int = Field(ge=0)
    binding_tier_counts: dict[str, int]
    connector_ids: tuple[str, ...]
    best_binding_confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("binding_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)


class RouteRequirement(_StrictBoundaryModel):
    """Narrow owner projection needed to classify one capstone route."""

    route_id: str = Field(min_length=1)
    domain_role: str = Field(min_length=1)
    demanded_metrics: tuple[str, ...] = Field(min_length=1)
    witness_kind: str = Field(min_length=1)
    candidate_ref: str = Field(min_length=1)
    requirement_gap_id: str = Field(min_length=1)
    gap_source: str = Field(min_length=1)
    row_addressable_variable: str | None
    planner_gap_kind: str = Field(min_length=1)
    planner_strategy_kind: str = Field(min_length=1)
    blocker_codes: tuple[str, ...]
    missing_requirement_fields: tuple[str, ...] = Field(min_length=1)
    missing_link: str = Field(min_length=1)

    @model_validator(mode="after")
    def _owner_projection_is_canonical(self) -> Self:
        if self.demanded_metrics != tuple(sorted(set(self.demanded_metrics))):
            raise ValueError("demanded_metrics must be unique and sorted")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise ValueError("blocker_codes must be unique and sorted")
        if self.missing_requirement_fields != tuple(sorted(set(self.missing_requirement_fields))):
            raise ValueError("missing requirement fields must be unique and sorted")
        if self.missing_link not in {
            *self.blocker_codes,
            *self.missing_requirement_fields,
        }:
            raise ValueError("missing_link must come from preserved owner evidence")
        if self.witness_kind == "owner_data_gap":
            if self.gap_source != "l1_dcat_variable_availability":
                raise ValueError("owner_data_gap must come from the L1 availability owner")
            if self.row_addressable_variable is None:
                raise ValueError("owner_data_gap must identify one canonical variable")
            expected_missing_field = (
                f"canonical_variable_observations:{self.row_addressable_variable}"
            )
            if self.missing_requirement_fields != (expected_missing_field,):
                raise ValueError("owner_data_gap must preserve its exact variable gap")
        else:
            if self.row_addressable_variable is not None:
                raise ValueError("only owner_data_gap is row-addressable")
            if self.gap_source == "l1_dcat_variable_availability":
                raise ValueError("the L1 availability owner requires owner_data_gap")
        return self


class VariableSupplyEvidence(_StrictBoundaryModel):
    """Exact local/catalog supply measured for one declared variable set."""

    variable_ids: tuple[str, ...] = Field(min_length=1)
    local_observation_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    executable_binding_count: int = Field(ge=0)
    binding_tier_counts: dict[str, int]
    alignment_count: int = Field(ge=0)
    nonproxy_alignment_count: int = Field(ge=0)
    connector_ids: tuple[str, ...]

    @field_validator("binding_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)

    @model_validator(mode="after")
    def _supply_counts_are_derived(self) -> Self:
        if self.variable_ids != tuple(sorted(set(self.variable_ids))):
            raise ValueError("variable_ids must be unique and sorted")
        if sum(self.binding_tier_counts.values()) != self.binding_count:
            raise ValueError("binding tier counts must cover every binding")
        executable_count = sum(
            count
            for tier, count in self.binding_tier_counts.items()
            if tier in EXECUTABLE_BINDING_TIERS
        )
        if executable_count != self.executable_binding_count:
            raise ValueError("executable binding count must be derived from tiers")
        if self.nonproxy_alignment_count > self.alignment_count:
            raise ValueError("nonproxy alignments cannot exceed all alignments")
        if self.binding_count == 0 and self.connector_ids:
            raise ValueError("unbound variables cannot claim connectors")
        return self


class RouteEvidence(_StrictBoundaryModel):
    """Measured supply and recomputed class for one actual N10 route."""

    route: RouteRequirement
    declared_supply: VariableSupplyEvidence
    row_addressable_supply: VariableSupplyEvidence | None
    route_class: RouteClass

    @model_validator(mode="after")
    def _class_must_be_recomputed_from_owner_evidence(self) -> Self:
        if self.declared_supply.variable_ids != self.route.demanded_metrics:
            raise ValueError("declared supply must cover the route demand denominator")
        variable = self.route.row_addressable_variable
        if variable is None:
            if self.row_addressable_supply is not None:
                raise ValueError("structural routes cannot claim row-addressable supply")
        elif self.row_addressable_supply is None or self.row_addressable_supply.variable_ids != (
            variable,
        ):
            raise ValueError("row-addressable supply must cover the exact owner variable")
        expected = _derive_route_class(
            witness_kind=self.route.witness_kind,
            row_addressable_supply=self.row_addressable_supply,
        )
        if self.route_class is not expected:
            raise ValueError("route_class must be recomputed from decisive evidence")
        return self


class FetchPlanSampleRow(_StrictBoundaryModel):
    """One data-derived metric selected for owner plan generation."""

    metric_id: str = Field(min_length=1)
    resolution_status: ResolutionStatus
    executable_binding_count: int = Field(ge=1)
    selection_reasons: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sample_is_resolved_and_canonical(self) -> Self:
        if self.resolution_status is ResolutionStatus.UNRESOLVED:
            raise ValueError("unresolved metrics cannot enter the FetchPlan sample")
        if self.selection_reasons != tuple(sorted(set(self.selection_reasons))):
            raise ValueError("selection reasons must be unique and sorted")
        return self


class FetchPlanProjection(_StrictBoundaryModel):
    """Narrow proof projected from a real owner-generated FetchPlan."""

    plan_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    selection_reasons: tuple[str, ...] = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    catalog_dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    filters: dict[str, list[str]]
    execution_tier: Literal["fetchable", "transport_ready"]
    source_lane: Literal["catalog"]
    persist_payload: Literal[False]
    owner_type: Literal["polisyos.core.contracts.control.FetchPlan"]

    @model_validator(mode="after")
    def _selection_reasons_are_canonical(self) -> Self:
        if self.selection_reasons != tuple(sorted(set(self.selection_reasons))):
            raise ValueError("selection reasons must be unique and sorted")
        return self


class FetchPlanExecutionFence(_StrictBoundaryModel):
    """Behavioral receipt proving plan generation executed no acquisition owner."""

    preview_calls: Literal[0]
    execute_calls: Literal[0]
    catalog_resolution_calls: int = Field(ge=1)
    expected_catalog_resolution_calls: int = Field(ge=1)
    catalog_content_before_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_content_after_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scratch_tree_before_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scratch_tree_after_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    forbidden_owners: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _fence_must_prove_no_growth(self) -> Self:
        if self.catalog_resolution_calls != self.expected_catalog_resolution_calls:
            raise ValueError("catalog owner must be called once for every sampled metric")
        if self.catalog_content_before_sha256 != self.catalog_content_after_sha256:
            raise ValueError("FetchPlan generation must not mutate the catalog")
        if self.scratch_tree_before_sha256 != self.scratch_tree_after_sha256:
            raise ValueError("FetchPlan generation must not persist payloads")
        if self.forbidden_owners != tuple(sorted(set(self.forbidden_owners))):
            raise ValueError("forbidden owners must be unique and sorted")
        return self


class ProbeBudget(_StrictBoundaryModel):
    """Derived HTTP limits carried by one live characterization request."""

    timeout_seconds: float = Field(gt=0.0)
    max_response_bytes: int = Field(gt=0)
    minimum_interval_seconds: float = Field(ge=0.0)
    call_budget: Literal[1] = 1


class SchemaProfileContract(_StrictBoundaryModel):
    """Owner profile projected into a live probe request."""

    distribution_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    columns: tuple[str, ...]
    sample_row_count: int = Field(ge=0)
    preview_sample_hash: str | None = None
    inference_mode: str = Field(min_length=1)
    parser_mode: str = Field(min_length=1)


class ProbeRequest(_StrictBoundaryModel):
    """Quarantine-only request envelope for one live attempt."""

    attempt_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    request_variable: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    endpoint_url: str = Field(min_length=1)
    schema_profile: SchemaProfileContract
    budget: ProbeBudget
    access_license: str = Field(min_length=1)
    auth_required: bool
    dry_run_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ProbeRawResponse(_StrictBoundaryModel):
    """Bounded response evidence journaled before liveness classification."""

    attempt_id: str = Field(min_length=1)
    request_record_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    journal_sequence: int = Field(ge=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str]
    bounded_body_base64: str | None = None
    body_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    bytes_read: int = Field(ge=0)
    transport_error_code: str | None = None


class DerivedLiveness(_StrictBoundaryModel):
    """Liveness state recomputed from a journaled response and owner profile."""

    attempt_id: str = Field(min_length=1)
    liveness_state: LivenessState
    decisive_evidence_refs: tuple[str, ...] = Field(min_length=1)


class FamilyScorecard(_StrictBoundaryModel):
    """Aggregate characterization result for one data-enumerated family."""

    connector_id: str = Field(min_length=1)
    selected_probe_count: int = Field(ge=0)
    live_attempt_count: int = Field(ge=0)
    dry_run_passed: bool
    liveness_counts: dict[LivenessState, int]
    tier_decay_findings: tuple[str, ...]

    @field_validator("liveness_counts")
    @classmethod
    def _counts_must_be_nonnegative(
        cls, value: dict[LivenessState, int]
    ) -> dict[LivenessState, int]:
        return _validate_nonnegative_count_map(value)


class GrowthBacklogRow(_StrictBoundaryModel):
    """Demand-ranked residual without claiming a parallel VOI authority."""

    rank: int = Field(ge=1)
    variable_id: str = Field(min_length=1)
    gap_kind: DemandGapKind
    demand_sources: tuple[str, ...] = Field(min_length=1)
    route_demand: float = Field(ge=0.0)
    binding_confidence: float = Field(ge=0.0, le=1.0)
    ranking_score: float = Field(ge=0.0)
    ranking_method: str = Field(pattern=r"^interim_binding_demand_rank$")
    voi_owner_integration: str = Field(pattern=r"^routed_to_gy_n13b$")


class ProjectionBinding(_StrictBoundaryModel):
    """Narrow upstream projection identity bound by the census."""

    projection_id: str = Field(min_length=1)
    source_artifact: str = Field(min_length=1)
    projection_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    projected_item_count: int = Field(ge=0)


class FetchPlanGenerationProof(_StrictBoundaryModel):
    """Complete plan-only owner proof for the declared metric sample."""

    sample_binding: ProjectionBinding
    sample_rows: tuple[FetchPlanSampleRow, ...] = Field(min_length=1)
    plans: tuple[FetchPlanProjection, ...] = Field(min_length=1)
    execution_fence: FetchPlanExecutionFence
    capability_status: Literal["implemented_but_not_orchestrated"]

    @model_validator(mode="after")
    def _proof_covers_the_declared_sample(self) -> Self:
        sample_metrics = tuple(row.metric_id for row in self.sample_rows)
        if sample_metrics != tuple(sorted(set(sample_metrics))):
            raise ValueError("FetchPlan sample metrics must be unique and sorted")
        plan_metrics = tuple(plan.metric_id for plan in self.plans)
        if plan_metrics != sample_metrics:
            raise ValueError("one owner FetchPlan must cover every sampled metric")
        if self.sample_binding.projected_item_count != len(self.sample_rows):
            raise ValueError("sample projection must cover every sampled metric")
        reasons = {row.metric_id: row.selection_reasons for row in self.sample_rows}
        if any(plan.selection_reasons != reasons[plan.metric_id] for plan in self.plans):
            raise ValueError("FetchPlan selection reasons must match the sample")
        return self


class RouteProjection(_StrictBoundaryModel):
    """Narrow, content-bound acquisition-route projection from the capstone."""

    projection_binding: ProjectionBinding
    routes: tuple[RouteRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _route_denominator_is_complete_and_sorted(self) -> Self:
        route_ids = tuple(route.route_id for route in self.routes)
        if route_ids != tuple(sorted(set(route_ids))):
            raise ValueError("route IDs must be unique and sorted")
        roles = tuple(route.domain_role for route in self.routes)
        if len(roles) != len(set(roles)):
            raise ValueError("domain roles must identify unique capstone routes")
        if self.projection_binding.projected_item_count != len(self.routes):
            raise ValueError("projection count must cover every capstone route")
        return self


class DemandProjection(_StrictBoundaryModel):
    """Narrow, content-bound reverse denominator projected from upstream artifacts."""

    projection_bindings: tuple[ProjectionBinding, ...]
    demands: tuple[DemandRequirement, ...]

    @model_validator(mode="after")
    def _demand_denominator_is_unique_and_sorted(self) -> Self:
        variable_ids = tuple(demand.variable_id for demand in self.demands)
        if variable_ids != tuple(sorted(set(variable_ids))):
            raise ValueError("demand variables must be unique and sorted")
        return self


class CensusManifest(_StrictBoundaryModel):
    """Frozen semantic payload for one acquisition-layer reality census."""

    schema_version: Literal[SCHEMA_VERSION]
    rule_version: Literal[RULE_VERSION]
    producer: str = Field(min_length=1)
    catalog_identity: CatalogIdentity
    projection_bindings: tuple[ProjectionBinding, ...]
    metric_resolutions: tuple[MetricResolution, ...]
    reverse_demand_variables: tuple[DemandVariableEvidence, ...]
    reverse_demand_residuals: tuple[ReverseDemandResidual, ...]
    route_evidence: tuple[RouteEvidence, ...]
    fetch_plan_generation: FetchPlanGenerationProof
    family_scorecards: tuple[FamilyScorecard, ...]
    growth_backlog: tuple[GrowthBacklogRow, ...]
    journal_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_at: datetime
    capture_wall_time_seconds: float = Field(ge=0.0)


class CatalogSource(_StrictBoundaryModel):
    """Read-only catalog facts used to build the census denominator."""

    identity: CatalogIdentity
    metric_ids: tuple[str, ...]
    connector_families: tuple[str, ...]


class CatalogContractError(RuntimeError):
    """Raised when the supplied catalog cannot satisfy the census read contract."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class CensusExecutionFenceError(RuntimeError):
    """Raised before N13a can execute a FetchPlan or acquisition owner."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes with one trailing newline."""

    normalized = _json_value(value)
    return (
        json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def semantic_content_hash(value: object) -> str:
    """Hash semantic evidence excluding only top-level run economics."""

    stable = _without_top_level_run_economics(_json_value(value))
    return f"sha256:{hashlib.sha256(canonical_json_bytes(stable)).hexdigest()}"


def read_catalog_source(catalog_path: Path, *, source_locator: str) -> CatalogSource:
    """Read catalog identity and full denominators through a read-only connection.

    Args:
        catalog_path: DuckDB catalog file. The file is never opened writable.
        source_locator: Stable logical locator persisted in the census instead of an
            environment-specific absolute path.

    Returns:
        Strict catalog identity plus sorted metric and connector denominators.

    Raises:
        CatalogContractError: If the file or its owner schema is missing or corrupt.
    """

    if not catalog_path.is_file():
        raise CatalogContractError(
            "catalog_unreadable", f"catalog file does not exist: {catalog_path}"
        )
    if not source_locator.strip():
        raise CatalogContractError("catalog_source_locator_missing", "empty locator")

    try:
        connection = duckdb.connect(str(catalog_path), read_only=True)
    except duckdb.Error as exc:
        raise CatalogContractError("catalog_unreadable", str(exc)) from exc

    try:
        _validate_catalog_schema(connection)
        _validate_denominator_rows(connection)
        _validate_binding_owner_rows(connection)
        table_row_counts = {
            table: int(
                connection.execute("SELECT COUNT(*) FROM query_table(?)", [table]).fetchone()[0]
            )
            for table in sorted(_REQUIRED_CATALOG_COLUMNS)
        }
        metric_ids = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT TRIM(metric_id) AS metric_id
                FROM ds_metric_bindings
                WHERE metric_id IS NOT NULL AND TRIM(metric_id) <> ''
                ORDER BY metric_id
                """
            ).fetchall()
        )
        connector_families = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT TRIM(connector_id) AS connector_id
                FROM ds_metric_bindings
                WHERE connector_id IS NOT NULL AND TRIM(connector_id) <> ''
                ORDER BY connector_id
                """
            ).fetchall()
        )
        execution_tier_counts = {
            str(tier): int(count)
            for tier, count in connection.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(execution_tier), ''), 'unknown') AS tier,
                       COUNT(*) AS row_count
                FROM ds_metric_bindings
                GROUP BY tier
                ORDER BY tier
                """
            ).fetchall()
        }
    except duckdb.Error as exc:
        raise CatalogContractError("catalog_query_failed", str(exc)) from exc
    finally:
        connection.close()

    catalog_sha256 = _file_sha256(catalog_path)
    identity = CatalogIdentity(
        source_locator=source_locator,
        catalog_content_sha256=catalog_sha256,
        catalog_byte_size=catalog_path.stat().st_size,
        table_row_counts=table_row_counts,
        binding_row_count=table_row_counts["ds_metric_bindings"],
        binding_metric_count=len(metric_ids),
        connector_family_count=len(connector_families),
        execution_tier_counts=execution_tier_counts,
    )
    return CatalogSource(
        identity=identity,
        metric_ids=metric_ids,
        connector_families=connector_families,
    )


def derive_metric_resolutions(catalog_path: Path) -> tuple[MetricResolution, ...]:
    """Resolve every catalog metric through binding-linked owner evidence.

    Exact resolution requires an observation whose dataset is bound to the same
    metric and whose canonical variable equals the metric.  Alignment resolution
    requires the same binding-linked dataset predicate and an owner alignment whose
    canonical variable equals the metric.  Global name overlap and alignments from
    unrelated datasets are deliberately ignored.

    Args:
        catalog_path: Read-only DuckDB catalog snapshot.

    Returns:
        One deterministic evidence row for every distinct binding metric.

    Raises:
        CatalogContractError: If the catalog owner contract cannot be read.
    """

    connection = _open_validated_catalog(catalog_path)
    try:
        resolution_scope = _derive_resolution_scope(connection)
        exact_query, alignment_query = _resolution_queries(resolution_scope)
        binding_rows = connection.execute(
            """
            SELECT metric_id, dataset_id, connector_id, execution_tier
            FROM ds_metric_bindings
            ORDER BY metric_id, dataset_id, connector_id, execution_tier
            """
        ).fetchall()
        exact_rows = connection.execute(exact_query).fetchall()
        alignment_rows = connection.execute(alignment_query).fetchall()
    except duckdb.Error as exc:
        raise CatalogContractError("catalog_resolution_query_failed", str(exc)) from exc
    finally:
        connection.close()

    binding_counts: Counter[str] = Counter()
    binding_datasets: defaultdict[str, set[str]] = defaultdict(set)
    binding_tiers: defaultdict[str, Counter[str]] = defaultdict(Counter)
    connector_ids: defaultdict[str, set[str]] = defaultdict(set)
    for metric_id, dataset_id, connector_id, execution_tier in binding_rows:
        metric = str(metric_id)
        binding_counts[metric] += 1
        binding_datasets[metric].add(str(dataset_id))
        binding_tiers[metric][str(execution_tier)] += 1
        connector_ids[metric].add(str(connector_id))

    exact_counts = {str(metric_id): int(count) for metric_id, count in exact_rows}
    candidates_by_metric: defaultdict[str, list[AlignmentCandidate]] = defaultdict(list)
    for (
        metric_id,
        dataset_id,
        raw_variable,
        canonical_variable,
        confidence,
        is_proxy,
        proxy_penalty,
        method,
        evidence,
        bound_observation_edge_missing,
    ) in alignment_rows:
        candidates_by_metric[str(metric_id)].append(
            AlignmentCandidate(
                dataset_id=str(dataset_id),
                raw_variable=str(raw_variable),
                canonical_variable=str(canonical_variable),
                confidence=float(confidence),
                is_proxy=bool(is_proxy),
                proxy_penalty=float(proxy_penalty),
                method=str(method),
                evidence=str(evidence),
                bound_observation_edge_missing=bool(bound_observation_edge_missing),
            )
        )

    rows: list[MetricResolution] = []
    for metric_id in sorted(binding_counts):
        candidates = tuple(
            sorted(candidates_by_metric[metric_id], key=_alignment_candidate_sort_key)
        )
        exact_count = exact_counts.get(metric_id, 0)
        if exact_count:
            status = ResolutionStatus.EXACT
            exact_variable: str | None = metric_id
        elif candidates:
            status = ResolutionStatus.VIA_ALIGNMENT
            exact_variable = None
        else:
            status = ResolutionStatus.UNRESOLVED
            exact_variable = None
        limitations = _resolution_limitations(scope=resolution_scope, status=status)
        rows.append(
            MetricResolution(
                metric_id=metric_id,
                resolution_status=status,
                resolution_scope=resolution_scope,
                binding_count=binding_counts[metric_id],
                binding_dataset_count=len(binding_datasets[metric_id]),
                exact_observation_count=exact_count,
                alignment_candidate_count=len(candidates),
                binding_tier_counts=dict(sorted(binding_tiers[metric_id].items())),
                connector_ids=tuple(sorted(connector_ids[metric_id])),
                exact_canonical_variable=exact_variable,
                best_alignment=candidates[0] if candidates else None,
                alignment_candidates=candidates,
                alignment_ambiguous=len(candidates) > 1,
                proxy_only=bool(candidates) and all(candidate.is_proxy for candidate in candidates),
                limitations=limitations,
            )
        )
    return tuple(rows)


def extract_reverse_demand_projection(
    *,
    capstone: Mapping[str, Any],
    intervention_substrate: Mapping[str, Any],
    value_gate: Mapping[str, Any],
    capstone_source: str,
    intervention_substrate_source: str,
    value_gate_source: str,
) -> DemandProjection:
    """Project the complete cycle-relevant variable denominator from owners.

    The paths, rather than domain names or expected values, define the projection:
    every capstone outcome/objective/lever target, every measured L6 world slot, and
    every value-gate selection target is included.  Each upstream projection is
    hashed independently so unrelated artifact changes do not move the binding.

    Args:
        capstone: Frozen N10 capstone payload.
        intervention_substrate: Frozen L6 substrate payload.
        value_gate: Frozen N8 value-gate payload.
        capstone_source: Stable capstone artifact locator.
        intervention_substrate_source: Stable L6 artifact locator.
        value_gate_source: Stable value-gate artifact locator.

    Returns:
        Narrow projection identities and the merged, sorted demand denominator.

    Raises:
        CatalogContractError: If a declared owner path is absent or malformed.
    """

    capstone_items = _extract_capstone_demand_items(capstone)
    substrate_items = _extract_substrate_demand_items(intervention_substrate)
    value_gate_items = _extract_value_gate_demand_items(value_gate)
    projections = (
        _projection_binding("capstone_cycle_demands", capstone_source, capstone_items),
        _projection_binding(
            "intervention_substrate_world_slots",
            intervention_substrate_source,
            substrate_items,
        ),
        _projection_binding("value_gate_target_requirements", value_gate_source, value_gate_items),
    )
    demand_sources: defaultdict[str, set[str]] = defaultdict(set)
    for item in (*capstone_items, *substrate_items, *value_gate_items):
        demand_sources[item["variable_id"]].add(item["source_path"])
    if not demand_sources:
        raise CatalogContractError(
            "demand_projection_empty", "declared upstream paths produced no variables"
        )
    return DemandProjection(
        projection_bindings=projections,
        demands=tuple(
            DemandRequirement(
                variable_id=variable_id,
                demand_sources=tuple(sorted(sources)),
            )
            for variable_id, sources in sorted(demand_sources.items())
        ),
    )


def read_reverse_demand_projection(
    *,
    capstone_path: Path,
    intervention_substrate_path: Path,
    value_gate_path: Path,
    capstone_source: str,
    intervention_substrate_source: str,
    value_gate_source: str,
) -> DemandProjection:
    """Load frozen upstream owners and return their narrow demand projection."""

    return extract_reverse_demand_projection(
        capstone=_load_json_mapping(capstone_path, owner="capstone"),
        intervention_substrate=_load_json_mapping(
            intervention_substrate_path, owner="intervention_substrate"
        ),
        value_gate=_load_json_mapping(value_gate_path, owner="value_gate"),
        capstone_source=capstone_source,
        intervention_substrate_source=intervention_substrate_source,
        value_gate_source=value_gate_source,
    )


def extract_route_projection(
    *,
    capstone: Mapping[str, Any],
    capstone_source: str,
) -> RouteProjection:
    """Project every capstone route through only its decisive owner evidence.

    Route keys and domain roles remain identifiers in the evidence, but neither is
    a classifier input. Free-form request prose and reconnaissance hypotheses are
    intentionally outside this projection.
    """

    runs = _required_mapping(capstone, "domain_runs", "capstone.domain_runs")
    if not runs:
        raise CatalogContractError("route_projection_empty", "capstone.domain_runs is empty")
    routes = tuple(
        _extract_route_requirement(
            route_id=_required_identifier(route_key, "capstone.domain_runs route key"),
            run=_as_mapping(raw_run, f"capstone.domain_runs.{route_key}"),
        )
        for route_key, raw_run in sorted(runs.items(), key=lambda item: str(item[0]))
    )
    roles = tuple(route.domain_role for route in routes)
    if len(roles) != len(set(roles)):
        raise CatalogContractError(
            "route_projection_duplicate_role",
            "capstone domain_role values must identify unique routes",
        )
    binding = _projection_binding(
        "capstone_acquisition_routes",
        capstone_source,
        tuple(route.model_dump(mode="json") for route in routes),
    )
    return RouteProjection(projection_binding=binding, routes=routes)


def read_route_projection(*, capstone_path: Path, capstone_source: str) -> RouteProjection:
    """Load the frozen capstone and return its narrow route projection."""

    return extract_route_projection(
        capstone=_load_json_mapping(capstone_path, owner="capstone"),
        capstone_source=capstone_source,
    )


def measure_route_evidence(
    catalog_path: Path,
    projection: RouteProjection,
) -> tuple[RouteEvidence, ...]:
    """Measure route-declared and row-addressable supply, then derive classes."""

    connection = _open_validated_catalog(catalog_path)
    try:
        binding_rows = connection.execute(
            """
            SELECT metric_id, connector_id, execution_tier
            FROM ds_metric_bindings
            """
        ).fetchall()
        observation_rows = connection.execute(
            """
            SELECT canonical_var, COUNT(*)
            FROM ds_observations
            WHERE canonical_var IS NOT NULL AND TRIM(canonical_var) <> ''
            GROUP BY canonical_var
            """
        ).fetchall()
        alignment_rows = connection.execute(
            """
            SELECT canonical_var,
                   COUNT(*),
                   COUNT(*) FILTER (WHERE is_proxy IS FALSE)
            FROM ds_variable_alignments
            WHERE canonical_var IS NOT NULL AND TRIM(canonical_var) <> ''
            GROUP BY canonical_var
            """
        ).fetchall()
    except duckdb.Error as exc:
        raise CatalogContractError("catalog_route_query_failed", str(exc)) from exc
    finally:
        connection.close()

    binding_counts: Counter[str] = Counter()
    tier_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    connectors: defaultdict[str, set[str]] = defaultdict(set)
    for metric_id, connector_id, execution_tier in binding_rows:
        metric = str(metric_id)
        tier = str(execution_tier)
        binding_counts[metric] += 1
        tier_counts[metric][tier] += 1
        connectors[metric].add(str(connector_id))
    observation_counts = {str(variable_id): int(count) for variable_id, count in observation_rows}
    alignment_counts = {
        str(variable_id): (int(count), int(nonproxy_count))
        for variable_id, count, nonproxy_count in alignment_rows
    }

    rows: list[RouteEvidence] = []
    for route in projection.routes:
        declared_supply = _variable_supply_evidence(
            route.demanded_metrics,
            binding_counts=binding_counts,
            tier_counts=tier_counts,
            connectors=connectors,
            observation_counts=observation_counts,
            alignment_counts=alignment_counts,
        )
        row_supply = (
            _variable_supply_evidence(
                (route.row_addressable_variable,),
                binding_counts=binding_counts,
                tier_counts=tier_counts,
                connectors=connectors,
                observation_counts=observation_counts,
                alignment_counts=alignment_counts,
            )
            if route.row_addressable_variable is not None
            else None
        )
        route_class = _derive_route_class(
            witness_kind=route.witness_kind,
            row_addressable_supply=row_supply,
        )
        rows.append(
            RouteEvidence(
                route=route,
                declared_supply=declared_supply,
                row_addressable_supply=row_supply,
                route_class=route_class,
            )
        )
    return tuple(rows)


def generate_fetch_plan_proofs(
    catalog_path: Path,
    *,
    metric_resolutions: Sequence[MetricResolution],
    route_evidence: Sequence[RouteEvidence],
    scratch_dir: Path,
    source_locator: str,
    _service_factory: Callable[..., Any] | None = None,
) -> FetchPlanGenerationProof:
    """Generate real owner FetchPlans under a hard no-execution fence.

    The sample contains every resolved, executable capstone-route metric plus one
    deterministic resolved metric for every connector family that is primary for
    at least one executable binding. The existing catalog graph and retrieval
    service produce the plans; no preview, execute, connector fetch, ingestion, or
    persistence owner is invoked.
    """

    from polisyos.core.contracts.control import DataNeed
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.fabric.retrieval.service import RetrievalService

    if not source_locator.strip():
        raise CatalogContractError("fetch_plan_source_locator_missing", "empty locator")
    recomputed_resolutions = derive_metric_resolutions(catalog_path)
    if tuple(metric_resolutions) != recomputed_resolutions:
        raise CatalogContractError(
            "fetch_plan_resolution_projection_mismatch",
            "supplied W1 resolutions do not match the catalog owner",
        )
    resolution_by_metric = {row.metric_id: row for row in recomputed_resolutions}
    eligible = {
        row.metric_id: row
        for row in recomputed_resolutions
        if row.resolution_status is not ResolutionStatus.UNRESOLVED
        and sum(
            count
            for tier, count in row.binding_tier_counts.items()
            if tier in EXECUTABLE_BINDING_TIERS
        )
        > 0
    }
    route_reasons: defaultdict[str, set[str]] = defaultdict(set)
    for route_row in route_evidence:
        for metric_id in route_row.route.demanded_metrics:
            if metric_id in eligible:
                route_reasons[metric_id].add(f"capstone_route:{route_row.route.route_id}")

    scratch_dir.mkdir(parents=True, exist_ok=True)
    catalog_before = _file_sha256(catalog_path)
    scratch_before = _tree_sha256(scratch_dir)
    graph = DatasetCatalogGraph(catalog_path, catalog_path.parent)
    try:
        primary_binding_by_metric: dict[str, Any] = {}
        representative_by_connector: dict[str, str] = {}
        ordered_metrics = sorted(
            eligible,
            key=lambda metric_id: (
                eligible[metric_id].resolution_status
                is not ResolutionStatus.EXACT,
                metric_id,
            ),
        )
        for metric_id in ordered_metrics:
            bindings = graph.resolve_metric_bindings(metric_id, top_k=3)
            executable_bindings = [
                binding
                for binding in bindings
                if str(getattr(binding, "execution_tier", ""))
                in EXECUTABLE_BINDING_TIERS
                and str(getattr(binding, "connector_id", "") or "").strip()
                and str(getattr(binding, "request_dataset_id", "") or "").strip()
            ]
            if not executable_bindings:
                continue
            primary = executable_bindings[0]
            primary_binding_by_metric[metric_id] = primary
            representative_by_connector.setdefault(str(primary.connector_id), metric_id)

        missing_route_metrics = sorted(set(route_reasons) - set(primary_binding_by_metric))
        if missing_route_metrics:
            raise CatalogContractError(
                "fetch_plan_route_binding_unresolvable",
                ", ".join(missing_route_metrics),
            )
        reasons: defaultdict[str, set[str]] = defaultdict(set)
        for metric_id, values in route_reasons.items():
            reasons[metric_id].update(values)
        for connector_id, metric_id in representative_by_connector.items():
            reasons[metric_id].add(f"primary_connector:{connector_id}")
        if not reasons:
            raise CatalogContractError(
                "fetch_plan_sample_empty", "no resolved executable catalog metrics"
            )
        sample_rows = tuple(
            FetchPlanSampleRow(
                metric_id=metric_id,
                resolution_status=resolution_by_metric[metric_id].resolution_status,
                executable_binding_count=sum(
                    count
                    for tier, count in resolution_by_metric[
                        metric_id
                    ].binding_tier_counts.items()
                    if tier in EXECUTABLE_BINDING_TIERS
                ),
                selection_reasons=tuple(sorted(metric_reasons)),
            )
            for metric_id, metric_reasons in sorted(reasons.items())
        )
        sample_binding = _projection_binding(
            "catalog_fetch_plan_sample",
            source_locator,
            tuple(row.model_dump(mode="json") for row in sample_rows),
        )

        recording_catalog = _RecordingMetricCatalog(graph)
        execution_fence = _ForbiddenFetchExecutor()
        service_type = _service_factory or RetrievalService
        service = service_type(
            curated_dir=scratch_dir,
            dataset_catalog=recording_catalog,
            executor=execution_fence,
        )
        needs = [
            DataNeed(
                metric=row.metric_id,
                purpose="gy_n13a_shadow_plan_generation_only",
            )
            for row in sample_rows
        ]
        owner_plans, _ = service._resolve_via_catalog(needs)
        plan_by_metric: dict[str, Any] = {}
        for plan in owner_plans:
            metric_id = str(getattr(plan, "metric_id", "") or "")
            if metric_id in plan_by_metric:
                raise CatalogContractError(
                    "fetch_plan_owner_duplicate_metric", metric_id
                )
            plan_by_metric[metric_id] = plan
        expected_metrics = {row.metric_id for row in sample_rows}
        if set(plan_by_metric) != expected_metrics:
            missing = sorted(expected_metrics - set(plan_by_metric))
            extra = sorted(set(plan_by_metric) - expected_metrics)
            raise CatalogContractError(
                "fetch_plan_owner_coverage_mismatch",
                f"missing={missing}; extra={extra}",
            )

        projected_plans: list[FetchPlanProjection] = []
        sample_by_metric = {row.metric_id: row for row in sample_rows}
        for metric_id in sorted(plan_by_metric):
            plan = plan_by_metric[metric_id]
            bindings = recording_catalog.bindings_by_metric.get(metric_id, ())
            if not bindings:
                raise CatalogContractError(
                    "fetch_plan_catalog_owner_not_called", metric_id
                )
            owner_binding = bindings[0]
            _validate_owner_fetch_plan(plan=plan, binding=owner_binding)
            metadata = getattr(plan, "metadata", {})
            projected_plans.append(
                FetchPlanProjection(
                    plan_id=str(plan.plan_id),
                    metric_id=metric_id,
                    selection_reasons=sample_by_metric[metric_id].selection_reasons,
                    connector_id=str(plan.connector_id),
                    catalog_dataset_id=str(metadata["catalog_dataset_id"]),
                    distribution_id=str(metadata["distribution_id"]),
                    request_dataset_id=str(plan.dataset_id),
                    profile_id=str(plan.profile_id),
                    filters=dict(plan.filters),
                    execution_tier=str(metadata["execution_tier"]),
                    source_lane=str(plan.source_lane),
                    persist_payload=bool(plan.persist_payload),
                    owner_type=f"{type(plan).__module__}.{type(plan).__name__}",
                )
            )
    finally:
        graph.close()

    catalog_after = _file_sha256(catalog_path)
    scratch_after = _tree_sha256(scratch_dir)
    fence_receipt = FetchPlanExecutionFence(
        preview_calls=execution_fence.preview_calls,
        execute_calls=execution_fence.execute_calls,
        catalog_resolution_calls=len(recording_catalog.calls),
        expected_catalog_resolution_calls=len(sample_rows),
        catalog_content_before_sha256=catalog_before,
        catalog_content_after_sha256=catalog_after,
        scratch_tree_before_sha256=scratch_before,
        scratch_tree_after_sha256=scratch_after,
        forbidden_owners=tuple(sorted(_FETCH_PLAN_FORBIDDEN_OWNERS)),
    )
    return FetchPlanGenerationProof(
        sample_binding=sample_binding,
        sample_rows=sample_rows,
        plans=tuple(projected_plans),
        execution_fence=fence_receipt,
        capability_status="implemented_but_not_orchestrated",
    )


def measure_reverse_demand(
    catalog_path: Path,
    demands: Sequence[DemandRequirement],
) -> tuple[DemandVariableEvidence, ...]:
    """Measure exact binding, local, alignment, and executable support per demand."""

    variable_ids = tuple(demand.variable_id for demand in demands)
    if variable_ids != tuple(sorted(set(variable_ids))):
        raise CatalogContractError(
            "demand_denominator_invalid", "demand variables must be unique and sorted"
        )
    connection = _open_validated_catalog(catalog_path)
    try:
        binding_rows = connection.execute(
            """
            SELECT metric_id, connector_id, confidence, execution_tier
            FROM ds_metric_bindings
            """
        ).fetchall()
        observation_rows = connection.execute(
            """
            SELECT canonical_var, COUNT(*)
            FROM ds_observations
            WHERE canonical_var IS NOT NULL AND TRIM(canonical_var) <> ''
            GROUP BY canonical_var
            """
        ).fetchall()
        alignment_rows = connection.execute(
            """
            SELECT canonical_var, COUNT(*)
            FROM ds_variable_alignments
            WHERE canonical_var IS NOT NULL AND TRIM(canonical_var) <> ''
            GROUP BY canonical_var
            """
        ).fetchall()
    except duckdb.Error as exc:
        raise CatalogContractError("catalog_demand_query_failed", str(exc)) from exc
    finally:
        connection.close()

    demand_set = set(variable_ids)
    binding_counts: Counter[str] = Counter()
    executable_counts: Counter[str] = Counter()
    tier_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    connectors: defaultdict[str, set[str]] = defaultdict(set)
    best_confidence: defaultdict[str, float] = defaultdict(float)
    for metric_id, connector_id, confidence, execution_tier in binding_rows:
        metric = str(metric_id)
        if metric not in demand_set:
            continue
        tier = str(execution_tier)
        binding_counts[metric] += 1
        tier_counts[metric][tier] += 1
        connectors[metric].add(str(connector_id))
        best_confidence[metric] = max(best_confidence[metric], float(confidence))
        if tier in EXECUTABLE_BINDING_TIERS:
            executable_counts[metric] += 1
    observation_counts = {str(variable_id): int(count) for variable_id, count in observation_rows}
    alignment_counts = {str(variable_id): int(count) for variable_id, count in alignment_rows}

    rows: list[DemandVariableEvidence] = []
    for demand in demands:
        binding_count = binding_counts[demand.variable_id]
        executable_count = executable_counts[demand.variable_id]
        gap_kind = (
            DemandGapKind.BINDING
            if binding_count == 0
            else DemandGapKind.CONNECTOR
            if executable_count == 0
            else None
        )
        rows.append(
            DemandVariableEvidence(
                variable_id=demand.variable_id,
                demand_sources=demand.demand_sources,
                local_observation_count=observation_counts.get(demand.variable_id, 0),
                alignment_count=alignment_counts.get(demand.variable_id, 0),
                binding_count=binding_count,
                executable_binding_count=executable_count,
                binding_tier_counts=dict(sorted(tier_counts[demand.variable_id].items())),
                connector_ids=tuple(sorted(connectors[demand.variable_id])),
                best_binding_confidence=best_confidence[demand.variable_id],
                gap_kind=gap_kind,
            )
        )
    return tuple(rows)


def reverse_demand_residuals(
    rows: Sequence[DemandVariableEvidence],
) -> tuple[ReverseDemandResidual, ...]:
    """Project only unsupported demands while retaining the measured denominator."""

    return tuple(
        ReverseDemandResidual(
            variable_id=row.variable_id,
            gap_kind=row.gap_kind,
            demand_sources=row.demand_sources,
            local_observation_count=row.local_observation_count,
            alignment_count=row.alignment_count,
            binding_count=row.binding_count,
            executable_binding_count=row.executable_binding_count,
            binding_tier_counts=row.binding_tier_counts,
            connector_ids=row.connector_ids,
            best_binding_confidence=row.best_binding_confidence,
        )
        for row in rows
        if row.gap_kind is not None
    )


def _open_validated_catalog(catalog_path: Path) -> duckdb.DuckDBPyConnection:
    if not catalog_path.is_file():
        raise CatalogContractError(
            "catalog_unreadable", f"catalog file does not exist: {catalog_path}"
        )
    try:
        connection = duckdb.connect(str(catalog_path), read_only=True)
        _validate_catalog_schema(connection)
        _validate_denominator_rows(connection)
        _validate_binding_owner_rows(connection)
    except (duckdb.Error, CatalogContractError) as exc:
        if "connection" in locals():
            connection.close()
        if isinstance(exc, CatalogContractError):
            raise
        raise CatalogContractError("catalog_unreadable", str(exc)) from exc
    return connection


class _ForbiddenFetchExecutor:
    """Injected executor that turns every execution attempt red before effects."""

    def __init__(self) -> None:
        self.preview_calls = 0
        self.execute_calls = 0

    def preview(self, *_: object, **__: object) -> None:
        self.preview_calls += 1
        raise CensusExecutionFenceError(
            "fetch_plan_execution_forbidden",
            "FetchExecutor.preview is forbidden during N13a plan generation",
        )

    def execute(self, *_: object, **__: object) -> None:
        self.execute_calls += 1
        raise CensusExecutionFenceError(
            "fetch_plan_execution_forbidden",
            "FetchExecutor.execute is forbidden during N13a plan generation",
        )


class _RecordingMetricCatalog:
    """Narrow recording adapter over the real DatasetCatalogGraph owner."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph
        self.calls: list[tuple[str, int]] = []
        self.bindings_by_metric: dict[str, tuple[Any, ...]] = {}

    def resolve_metric_bindings(self, metric: str, *, top_k: int = 3) -> list[Any]:
        self.calls.append((metric, top_k))
        bindings = tuple(self._graph.resolve_metric_bindings(metric, top_k=top_k))
        self.bindings_by_metric[metric] = bindings
        return list(bindings)


def _validate_owner_fetch_plan(*, plan: Any, binding: Any) -> None:
    metadata = getattr(plan, "metadata", None)
    if not isinstance(metadata, Mapping):
        raise CatalogContractError(
            "fetch_plan_owner_metadata_missing", str(getattr(plan, "metric_id", ""))
        )
    expected = {
        "connector_id": str(getattr(binding, "connector_id", "") or ""),
        "request_dataset_id": str(
            getattr(binding, "request_dataset_id", "") or ""
        ),
        "profile_id": str(getattr(binding, "profile_id", "") or ""),
        "catalog_dataset_id": str(
            getattr(binding, "catalog_dataset_id", "") or ""
        ),
        "distribution_id": str(getattr(binding, "distribution_id", "") or ""),
        "execution_tier": str(getattr(binding, "execution_tier", "") or ""),
    }
    actual = {
        "connector_id": str(getattr(plan, "connector_id", "") or ""),
        "request_dataset_id": str(getattr(plan, "dataset_id", "") or ""),
        "profile_id": str(getattr(plan, "profile_id", "") or ""),
        "catalog_dataset_id": str(metadata.get("catalog_dataset_id") or ""),
        "distribution_id": str(metadata.get("distribution_id") or ""),
        "execution_tier": str(metadata.get("execution_tier") or ""),
    }
    if actual != expected:
        raise CatalogContractError(
            "fetch_plan_owner_projection_mismatch",
            f"metric={getattr(plan, 'metric_id', '')}; expected={expected}; actual={actual}",
        )
    if actual["execution_tier"] not in EXECUTABLE_BINDING_TIERS:
        raise CatalogContractError(
            "fetch_plan_catalog_tier_not_executable", actual["execution_tier"]
        )
    expected_filters = _coerce_plan_filters(
        getattr(binding, "default_filters", {}) or {}
    )
    if dict(getattr(plan, "filters", {}) or {}) != expected_filters:
        raise CatalogContractError(
            "fetch_plan_owner_filters_mismatch", str(getattr(plan, "metric_id", ""))
        )
    if getattr(plan, "source_lane", None) != "catalog":
        raise CatalogContractError(
            "fetch_plan_source_lane_invalid", str(getattr(plan, "source_lane", ""))
        )
    if bool(getattr(plan, "persist_payload", False)):
        raise CensusExecutionFenceError(
            "fetch_plan_persistence_forbidden",
            "N13a FetchPlans must keep persist_payload=false",
        )


def _coerce_plan_filters(value: object) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_values, list):
            normalized[key] = [str(item) for item in raw_values]
        elif raw_values is not None:
            normalized[key] = [str(raw_values)]
    return normalized


def _alignment_candidate_sort_key(candidate: AlignmentCandidate) -> tuple[object, ...]:
    return (
        candidate.is_proxy,
        -candidate.confidence,
        candidate.proxy_penalty,
        candidate.dataset_id,
        candidate.raw_variable,
        candidate.method,
        candidate.evidence,
    )


def _derive_route_class(
    *,
    witness_kind: str,
    row_addressable_supply: VariableSupplyEvidence | None,
) -> RouteClass:
    """Apply the route-class precedence without route-name or prose inputs."""

    if witness_kind != "owner_data_gap":
        return RouteClass.NOT_A_DATA_GAP
    if row_addressable_supply is None:
        raise ValueError("owner_data_gap requires measured row-addressable supply")
    if row_addressable_supply.local_observation_count > 0:
        return RouteClass.LOCAL_LIFT
    if row_addressable_supply.executable_binding_count > 0:
        return RouteClass.LIVE_FETCHABLE
    return RouteClass.UNRESOLVED


def _variable_supply_evidence(
    variable_ids: Sequence[str],
    *,
    binding_counts: Mapping[str, int],
    tier_counts: Mapping[str, Counter[str]],
    connectors: Mapping[str, set[str]],
    observation_counts: Mapping[str, int],
    alignment_counts: Mapping[str, tuple[int, int]],
) -> VariableSupplyEvidence:
    variables = tuple(sorted(set(variable_ids)))
    combined_tiers: Counter[str] = Counter()
    combined_connectors: set[str] = set()
    for variable in variables:
        combined_tiers.update(tier_counts.get(variable, Counter()))
        combined_connectors.update(connectors.get(variable, set()))
    binding_count = sum(binding_counts.get(variable, 0) for variable in variables)
    alignment_count = sum(alignment_counts.get(variable, (0, 0))[0] for variable in variables)
    nonproxy_alignment_count = sum(
        alignment_counts.get(variable, (0, 0))[1] for variable in variables
    )
    return VariableSupplyEvidence(
        variable_ids=variables,
        local_observation_count=sum(observation_counts.get(variable, 0) for variable in variables),
        binding_count=binding_count,
        executable_binding_count=sum(
            count for tier, count in combined_tiers.items() if tier in EXECUTABLE_BINDING_TIERS
        ),
        binding_tier_counts=dict(sorted(combined_tiers.items())),
        alignment_count=alignment_count,
        nonproxy_alignment_count=nonproxy_alignment_count,
        connector_ids=tuple(sorted(combined_connectors)),
    )


def _extract_route_requirement(*, route_id: str, run: Mapping[str, Any]) -> RouteRequirement:
    route_path = f"capstone.domain_runs.{route_id}"
    domain_role = _required_text(run, "domain_role", f"{route_path}.domain_role")
    demanded_metrics = _extract_route_demanded_metrics(run, route_path=route_path)
    witness_path = f"{route_path}.evidence_witness"
    witness = _required_mapping(run, "evidence_witness", witness_path)
    witness_kind = _required_text(witness, "kind", f"{witness_path}.kind")
    candidate_ref = _required_text(witness, "candidate_ref", f"{witness_path}.candidate_ref")
    route_owner_keys = tuple(
        key
        for key in ("acquisition_route", "grounding_route")
        if key in witness and witness[key] is not None
    )
    if len(route_owner_keys) != 1:
        raise CatalogContractError(
            "route_owner_reference_invalid",
            f"{witness_path} must carry exactly one acquisition owner reference",
        )
    route_owner_key = route_owner_keys[0]
    route_owner_path = f"{witness_path}.{route_owner_key}"
    route_owner = _as_mapping(witness[route_owner_key], route_owner_path)
    for field in ("owner_content_hash", "owner_schema", "planner_report_content_hash"):
        _required_text(route_owner, field, f"{route_owner_path}.{field}")
    owner_gap_id = _required_text(
        route_owner, "requirement_gap_id", f"{route_owner_path}.requirement_gap_id"
    )

    terminal_path = f"{route_path}.terminal"
    terminal = _required_mapping(run, "terminal", terminal_path)
    blocker_codes = _required_text_tuple(
        terminal,
        "blocking_obligations",
        f"{terminal_path}.blocking_obligations",
        allow_empty=True,
    )
    spec_path = f"{terminal_path}.data_need_spec"
    spec = _required_mapping(terminal, "data_need_spec", spec_path)
    spec_gap_id = _required_text(spec, "requirement_gap_id", f"{spec_path}.requirement_gap_id")
    if spec_gap_id != owner_gap_id:
        raise CatalogContractError(
            "route_requirement_gap_id_mismatch",
            f"{route_owner_path} and {spec_path} identify different gaps",
        )
    gap_kind = _required_text(spec, "gap_type", f"{spec_path}.gap_type")
    requirement_family = _required_text(
        spec, "requirement_family", f"{spec_path}.requirement_family"
    )
    missing_fields = _required_text_tuple(
        spec,
        "missing_requirement_fields",
        f"{spec_path}.missing_requirement_fields",
        allow_empty=False,
    )
    producer_output_ref = _required_text(
        spec, "producer_output_ref", f"{spec_path}.producer_output_ref"
    )
    metadata_path = f"{spec_path}.metadata"
    metadata = _required_mapping(spec, "metadata", metadata_path)
    gap_source = _required_text(metadata, "source", f"{metadata_path}.source")
    candidate_binding_path = f"{metadata_path}.candidate_binding"
    candidate_binding = _required_mapping(metadata, "candidate_binding", candidate_binding_path)
    if (
        _required_text(
            candidate_binding,
            "candidate_id",
            f"{candidate_binding_path}.candidate_id",
        )
        != candidate_ref
    ):
        raise CatalogContractError(
            "route_candidate_owner_mismatch",
            f"{candidate_binding_path} does not own {candidate_ref}",
        )
    _required_text(
        candidate_binding,
        "design_problem_ref",
        f"{candidate_binding_path}.design_problem_ref",
    )

    costed_path = f"{terminal_path}.costed_plan"
    costed = _required_mapping(terminal, "costed_plan", costed_path)
    report_path = f"{costed_path}.canonical_planner_report"
    report = _required_mapping(costed, "canonical_planner_report", report_path)
    records_path = f"{report_path}.acquisition_records"
    records = _required_sequence(report, "acquisition_records", records_path)
    matching_records: list[Mapping[str, Any]] = []
    for index, raw_record in enumerate(records):
        record = _as_mapping(raw_record, f"{records_path}[{index}]")
        if record.get("gap_id") == owner_gap_id:
            matching_records.append(record)
    if len(matching_records) != 1:
        raise CatalogContractError(
            "route_planner_gap_owner_missing",
            f"{records_path} must have exactly one record for {owner_gap_id}",
        )
    record = matching_records[0]
    if _required_text(record, "gap_type", f"{records_path}.gap_type") != gap_kind:
        raise CatalogContractError(
            "route_planner_gap_kind_mismatch", f"planner record for {owner_gap_id}"
        )
    if (
        _required_text(record, "requirement_family", f"{records_path}.requirement_family")
        != requirement_family
    ):
        raise CatalogContractError(
            "route_planner_requirement_family_mismatch",
            f"planner record for {owner_gap_id}",
        )
    record_missing_fields = _required_text_tuple(
        record,
        "missing_requirement_fields",
        f"{records_path}.missing_requirement_fields",
        allow_empty=False,
    )
    if record_missing_fields != missing_fields:
        raise CatalogContractError(
            "route_planner_missing_fields_mismatch",
            f"planner record for {owner_gap_id}",
        )
    planner_strategy = _required_text(
        record, "recommended_strategy", f"{records_path}.recommended_strategy"
    )
    _required_text(record, "producer_expected", f"{records_path}.producer_expected")

    row_addressable_variable: str | None = None
    if witness_kind == "owner_data_gap":
        if route_owner_key != "acquisition_route":
            raise CatalogContractError("route_data_gap_owner_reference_invalid", route_owner_path)
        if gap_source != "l1_dcat_variable_availability":
            raise CatalogContractError("route_data_gap_source_invalid", f"{metadata_path}.source")
        prefix = "canonical_variable_observations:"
        if len(missing_fields) != 1 or not missing_fields[0].startswith(prefix):
            raise CatalogContractError(
                "route_data_gap_variable_missing",
                f"{spec_path}.missing_requirement_fields",
            )
        row_addressable_variable = _as_text(
            missing_fields[0][len(prefix) :],
            f"{spec_path}.missing_requirement_fields[0] variable",
        )
        availability_path = f"{metadata_path}.availability"
        availability = _required_mapping(metadata, "availability", availability_path)
        if (
            _required_text(
                availability,
                "variable_id",
                f"{availability_path}.variable_id",
            )
            != row_addressable_variable
        ):
            raise CatalogContractError("route_data_gap_availability_mismatch", availability_path)
        owner_variable_suffix = f"#variable/{row_addressable_variable}"
        coverage_ref = _required_text(
            availability, "coverage_ref", f"{availability_path}.coverage_ref"
        )
        if not coverage_ref.endswith(owner_variable_suffix) or not producer_output_ref.endswith(
            owner_variable_suffix
        ):
            raise CatalogContractError("route_data_gap_variable_ref_mismatch", availability_path)

    if witness_kind == "estimand_binding_refusal":
        estimand_blockers = tuple(blocker for blocker in blocker_codes if "estimand" in blocker)
        if not estimand_blockers:
            raise CatalogContractError(
                "route_estimand_blocker_missing", f"{terminal_path}.blocking_obligations"
            )
        missing_link = estimand_blockers[0]
    else:
        missing_link = missing_fields[0]

    return RouteRequirement(
        route_id=route_id,
        domain_role=domain_role,
        demanded_metrics=demanded_metrics,
        witness_kind=witness_kind,
        candidate_ref=candidate_ref,
        requirement_gap_id=owner_gap_id,
        gap_source=gap_source,
        row_addressable_variable=row_addressable_variable,
        planner_gap_kind=gap_kind,
        planner_strategy_kind=planner_strategy,
        blocker_codes=blocker_codes,
        missing_requirement_fields=missing_fields,
        missing_link=missing_link,
    )


def _extract_route_demanded_metrics(run: Mapping[str, Any], *, route_path: str) -> tuple[str, ...]:
    problem_path = f"{route_path}.design_problem"
    problem = _required_mapping(run, "design_problem", problem_path)
    outcome_path = f"{problem_path}.outcome_of_interest"
    outcome = _required_mapping(problem, "outcome_of_interest", outcome_path)
    metrics = {
        _required_text(outcome, "metric_id", f"{outcome_path}.metric_id"),
        _required_text(outcome, "target_variable", f"{outcome_path}.target_variable"),
    }
    objectives_path = f"{problem_path}.objectives"
    objectives = _required_sequence(problem, "objectives", objectives_path)
    for index, raw_objective in enumerate(objectives):
        objective_path = f"{objectives_path}[{index}]"
        objective = _as_mapping(raw_objective, objective_path)
        metrics.add(_required_text(objective, "metric_id", f"{objective_path}.metric_id"))
    lever_space_path = f"{problem_path}.candidate_lever_space"
    lever_space = _required_mapping(problem, "candidate_lever_space", lever_space_path)
    levers_path = f"{lever_space_path}.candidate_levers"
    levers = _required_sequence(lever_space, "candidate_levers", levers_path)
    for index, raw_lever in enumerate(levers):
        lever_path = f"{levers_path}[{index}]"
        lever = _as_mapping(raw_lever, lever_path)
        metrics.add(_required_text(lever, "target_slot", f"{lever_path}.target_slot"))
    return tuple(sorted(metrics))


def _required_text_tuple(
    owner: Mapping[str, Any],
    key: str,
    path: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    values = _required_sequence(owner, key, path)
    normalized = tuple(
        sorted({_as_text(value, f"{path}[{index}]") for index, value in enumerate(values)})
    )
    if not normalized and not allow_empty:
        raise CatalogContractError("demand_projection_invalid_field", f"{path} must not be empty")
    return normalized


def _extract_capstone_demand_items(
    capstone: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    runs = _required_mapping(capstone, "domain_runs", "capstone.domain_runs")
    if not runs:
        raise CatalogContractError("demand_projection_empty", "capstone.domain_runs is empty")
    items: list[dict[str, str]] = []
    for route_key, raw_run in sorted(runs.items(), key=lambda item: str(item[0])):
        route = _required_identifier(route_key, "capstone.domain_runs key")
        run = _as_mapping(raw_run, f"capstone.domain_runs.{route}")
        problem_path = f"capstone.domain_runs.{route}.design_problem"
        problem = _required_mapping(run, "design_problem", problem_path)
        outcome_path = f"{problem_path}.outcome_of_interest"
        outcome = _required_mapping(problem, "outcome_of_interest", outcome_path)
        for field in ("metric_id", "target_variable"):
            path = f"{outcome_path}.{field}"
            items.append(
                {
                    "source_path": path,
                    "variable_id": _required_text(outcome, field, path),
                }
            )

        objectives_path = f"{problem_path}.objectives"
        objectives = _required_sequence(problem, "objectives", objectives_path)
        for index, raw_objective in enumerate(objectives):
            objective_path = f"{objectives_path}[{index}]"
            objective = _as_mapping(raw_objective, objective_path)
            field_path = f"{objective_path}.metric_id"
            items.append(
                {
                    "source_path": field_path,
                    "variable_id": _required_text(objective, "metric_id", field_path),
                }
            )

        lever_space_path = f"{problem_path}.candidate_lever_space"
        lever_space = _required_mapping(problem, "candidate_lever_space", lever_space_path)
        levers_path = f"{lever_space_path}.candidate_levers"
        levers = _required_sequence(lever_space, "candidate_levers", levers_path)
        for index, raw_lever in enumerate(levers):
            lever_path = f"{levers_path}[{index}]"
            lever = _as_mapping(raw_lever, lever_path)
            field_path = f"{lever_path}.target_slot"
            items.append(
                {
                    "source_path": field_path,
                    "variable_id": _required_text(lever, "target_slot", field_path),
                }
            )
    return tuple(sorted(items, key=lambda item: (item["source_path"], item["variable_id"])))


def _extract_substrate_demand_items(
    substrate: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    measured_path = "intervention_substrate.measured_coverage"
    measured = _required_mapping(substrate, "measured_coverage", measured_path)
    world_path = f"{measured_path}.world_slot"
    world = _required_mapping(measured, "world_slot", world_path)
    details_path = f"{world_path}.details"
    details = _required_sequence(world, "details", details_path)
    items: list[dict[str, str]] = []
    for detail_index, raw_detail in enumerate(details):
        detail_path = f"{details_path}[{detail_index}]"
        detail = _as_mapping(raw_detail, detail_path)
        targets_path = f"{detail_path}.target_world_slots"
        targets = _required_sequence(detail, "target_world_slots", targets_path)
        for target_index, raw_target in enumerate(targets):
            path = f"{targets_path}[{target_index}]"
            items.append(
                {
                    "source_path": path,
                    "variable_id": _as_text(raw_target, path),
                }
            )
    return tuple(sorted(items, key=lambda item: (item["source_path"], item["variable_id"])))


def _extract_value_gate_demand_items(
    value_gate: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    proofs_path = "value_gate.transport_component_proofs"
    proofs = _required_mapping(value_gate, "transport_component_proofs", proofs_path)
    if not proofs:
        raise CatalogContractError("demand_projection_empty", f"{proofs_path} is empty")
    items: list[dict[str, str]] = []
    for proof_key, raw_proof in sorted(proofs.items(), key=lambda item: str(item[0])):
        proof = _required_identifier(proof_key, f"{proofs_path} key")
        proof_path = f"{proofs_path}.{proof}"
        proof_payload = _as_mapping(raw_proof, proof_path)
        nodes_path = f"{proof_path}.selection_nodes"
        nodes = _required_sequence(proof_payload, "selection_nodes", nodes_path)
        for node_index, raw_node in enumerate(nodes):
            node_path = f"{nodes_path}[{node_index}]"
            node = _as_mapping(raw_node, node_path)
            field_path = f"{node_path}.target_variable"
            items.append(
                {
                    "source_path": field_path,
                    "variable_id": _required_text(node, "target_variable", field_path),
                }
            )
    return tuple(sorted(items, key=lambda item: (item["source_path"], item["variable_id"])))


def _projection_binding(
    projection_id: str,
    source_artifact: str,
    items: Sequence[Mapping[str, str]],
) -> ProjectionBinding:
    if not source_artifact.strip():
        raise CatalogContractError(
            "demand_projection_source_missing", f"empty source for {projection_id}"
        )
    return ProjectionBinding(
        projection_id=projection_id,
        source_artifact=source_artifact,
        projection_content_sha256=semantic_content_hash(
            {"projection_id": projection_id, "items": items}
        ),
        projected_item_count=len(items),
    )


def _required_mapping(owner: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
    if key not in owner:
        raise CatalogContractError("demand_projection_missing_field", f"missing {path}")
    return _as_mapping(owner[key], path)


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalogContractError("demand_projection_invalid_field", f"{path} must be an object")
    return value


def _required_sequence(owner: Mapping[str, Any], key: str, path: str) -> Sequence[Any]:
    if key not in owner:
        raise CatalogContractError("demand_projection_missing_field", f"missing {path}")
    value = owner[key]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CatalogContractError("demand_projection_invalid_field", f"{path} must be an array")
    return value


def _required_text(owner: Mapping[str, Any], key: str, path: str) -> str:
    if key not in owner:
        raise CatalogContractError("demand_projection_missing_field", f"missing {path}")
    return _as_text(owner[key], path)


def _required_identifier(value: Any, path: str) -> str:
    return _as_text(value, path)


def _as_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogContractError(
            "demand_projection_invalid_field", f"{path} must be non-blank text"
        )
    return value.strip()


def _load_json_mapping(path: Path, *, owner: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogContractError("demand_projection_owner_unreadable", f"{owner}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CatalogContractError(
            "demand_projection_owner_invalid", f"{owner} root must be an object"
        )
    return payload


def _validate_catalog_schema(connection: duckdb.DuckDBPyConnection) -> None:
    table_rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        """
    ).fetchall()
    actual_tables = {str(row[0]) for row in table_rows}
    missing_tables = sorted(set(_REQUIRED_CATALOG_COLUMNS) - actual_tables)
    if missing_tables:
        raise CatalogContractError("catalog_schema_missing_tables", ", ".join(missing_tables))

    missing_columns: list[str] = []
    for table, required_columns in sorted(_REQUIRED_CATALOG_COLUMNS.items()):
        column_rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table],
        ).fetchall()
        actual_columns = {str(row[0]) for row in column_rows}
        missing_columns.extend(
            f"{table}.{column}" for column in sorted(required_columns - actual_columns)
        )
    if missing_columns:
        raise CatalogContractError("catalog_schema_missing_columns", ", ".join(missing_columns))


def _validate_denominator_rows(connection: duckdb.DuckDBPyConnection) -> None:
    invalid_metric_count, invalid_connector_count = connection.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE metric_id IS NULL OR TRIM(metric_id) = ''
            ) AS invalid_metric_count,
            COUNT(*) FILTER (
                WHERE connector_id IS NULL OR TRIM(connector_id) = ''
            ) AS invalid_connector_count
        FROM ds_metric_bindings
        """
    ).fetchone()
    if int(invalid_metric_count):
        raise CatalogContractError(
            "catalog_metric_id_invalid",
            f"{invalid_metric_count} binding rows have blank/null metric_id",
        )
    if int(invalid_connector_count):
        raise CatalogContractError(
            "catalog_connector_id_invalid",
            f"{invalid_connector_count} binding rows have blank/null connector_id",
        )


def _validate_binding_owner_rows(connection: duckdb.DuckDBPyConnection) -> None:
    """Fail closed unless every binding is owned by consistent catalog records."""

    checks = (
        (
            "catalog_binding_dataset_missing",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            LEFT JOIN ds_datasets AS dataset ON dataset.id = binding.dataset_id
            WHERE dataset.id IS NULL
            """,
            "binding rows reference no owner dataset",
        ),
        (
            "catalog_binding_distribution_missing",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            LEFT JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE distribution.id IS NULL
            """,
            "binding rows reference no owner distribution",
        ),
        (
            "catalog_binding_distribution_dataset_mismatch",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE distribution.dataset_id IS DISTINCT FROM binding.dataset_id
            """,
            "binding rows disagree with their distribution dataset",
        ),
        (
            "catalog_binding_connector_mismatch",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE distribution.connector_type IS DISTINCT FROM binding.connector_id
            """,
            "binding rows disagree with their distribution connector",
        ),
        (
            "catalog_binding_profile_mismatch",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE distribution.profile_id IS DISTINCT FROM binding.profile_id
            """,
            "binding rows disagree with their distribution profile",
        ),
        (
            "catalog_binding_request_dataset_id_invalid",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings
            WHERE request_dataset_id IS NULL OR TRIM(request_dataset_id) = ''
            """,
            "binding rows have blank/null request_dataset_id",
        ),
        (
            "catalog_binding_execution_tier_invalid",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings
            WHERE execution_tier IS NULL
               OR TRIM(execution_tier) NOT IN ('catalog', 'fetchable', 'transport_ready')
            """,
            "binding rows have an unsupported execution_tier",
        ),
        (
            "catalog_binding_execution_tier_mismatch",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_datasets AS dataset ON dataset.id = binding.dataset_id
            WHERE dataset.execution_tier IS DISTINCT FROM binding.execution_tier
            """,
            "binding rows disagree with their owner dataset execution_tier",
        ),
        (
            "catalog_binding_executable_parser_unsupported",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE binding.execution_tier IN ('fetchable', 'transport_ready')
              AND distribution.parser_supported IS DISTINCT FROM TRUE
            """,
            "executable binding rows lack parser support",
        ),
        (
            "catalog_binding_executable_schema_profile_missing",
            """
            SELECT COUNT(*)
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
            WHERE binding.execution_tier IN ('fetchable', 'transport_ready')
              AND NOT EXISTS (
                    SELECT 1
                    FROM ds_schema_profiles AS schema_profile
                    WHERE schema_profile.distribution_id = distribution.id
                      AND schema_profile.dataset_id = binding.dataset_id
              )
            """,
            "executable binding rows lack an exact schema-profile owner",
        ),
    )
    for code, query, detail in checks:
        invalid_count = int(connection.execute(query).fetchone()[0])
        if invalid_count:
            raise CatalogContractError(code, f"{invalid_count} {detail}")


def _derive_resolution_scope(
    connection: duckdb.DuckDBPyConnection,
) -> ResolutionScope:
    """Derive the strongest resolvable edge from actual owner-table columns."""

    rows = connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name IN ('ds_metric_bindings', 'ds_observations')
        """
    ).fetchall()
    columns: defaultdict[str, set[str]] = defaultdict(set)
    for table_name, column_name in rows:
        columns[str(table_name)].add(str(column_name))
    if (
        "raw_variable" in columns["ds_metric_bindings"]
        and "distribution_id" in columns["ds_observations"]
    ):
        return ResolutionScope.DISTRIBUTION_FIELD_BOUND
    return ResolutionScope.DATASET_LEVEL_IDENTITY


def _resolution_queries(scope: ResolutionScope) -> tuple[str, str]:
    if scope is ResolutionScope.DISTRIBUTION_FIELD_BOUND:
        exact_query = """
            WITH bound_fields AS (
                SELECT DISTINCT
                       metric_id, dataset_id, distribution_id, raw_variable
                FROM ds_metric_bindings
            )
            SELECT bound.metric_id,
                   COUNT(DISTINCT observed.observation_id)
            FROM bound_fields AS bound
            JOIN ds_observations AS observed
              ON observed.dataset_id = bound.dataset_id
             AND observed.distribution_id = bound.distribution_id
             AND observed.raw_variable = bound.raw_variable
             AND observed.canonical_var = bound.metric_id
            GROUP BY bound.metric_id
        """
        alignment_query = """
            WITH bound_fields AS (
                SELECT DISTINCT
                       metric_id, dataset_id, distribution_id, raw_variable
                FROM ds_metric_bindings
            ), observed_edges AS (
                SELECT DISTINCT
                       dataset_id, distribution_id, raw_variable, canonical_var
                FROM ds_observations
            )
            SELECT DISTINCT
                   bound.metric_id,
                   aligned.dataset_id,
                   aligned.raw_variable,
                   aligned.canonical_var,
                   aligned.confidence,
                   aligned.is_proxy,
                   aligned.proxy_penalty,
                   aligned.method,
                   aligned.evidence,
                   edge.dataset_id IS NULL AS bound_observation_edge_missing
            FROM bound_fields AS bound
            JOIN ds_variable_alignments AS aligned
              ON aligned.dataset_id = bound.dataset_id
             AND aligned.raw_variable = bound.raw_variable
             AND aligned.canonical_var = bound.metric_id
            LEFT JOIN observed_edges AS edge
              ON edge.dataset_id = bound.dataset_id
             AND edge.distribution_id = bound.distribution_id
             AND edge.raw_variable = bound.raw_variable
             AND edge.canonical_var = bound.metric_id
        """
        return exact_query, alignment_query
    exact_query = """
        WITH bound_datasets AS (
            SELECT DISTINCT metric_id, dataset_id
            FROM ds_metric_bindings
        )
        SELECT bound.metric_id,
               COUNT(DISTINCT (observed.dataset_id, observed.observation_id))
        FROM bound_datasets AS bound
        JOIN ds_observations AS observed
          ON observed.dataset_id = bound.dataset_id
         AND observed.canonical_var = bound.metric_id
        GROUP BY bound.metric_id
    """
    alignment_query = """
        WITH bound_datasets AS (
            SELECT DISTINCT metric_id, dataset_id
            FROM ds_metric_bindings
        ), observed_edges AS (
            SELECT DISTINCT dataset_id, raw_variable, canonical_var
            FROM ds_observations
        )
        SELECT DISTINCT
               bound.metric_id,
               aligned.dataset_id,
               aligned.raw_variable,
               aligned.canonical_var,
               aligned.confidence,
               aligned.is_proxy,
               aligned.proxy_penalty,
               aligned.method,
               aligned.evidence,
               edge.dataset_id IS NULL AS bound_observation_edge_missing
        FROM bound_datasets AS bound
        JOIN ds_variable_alignments AS aligned
          ON aligned.dataset_id = bound.dataset_id
         AND aligned.canonical_var = bound.metric_id
        LEFT JOIN observed_edges AS edge
          ON edge.dataset_id = aligned.dataset_id
         AND edge.raw_variable = aligned.raw_variable
         AND edge.canonical_var = aligned.canonical_var
    """
    return exact_query, alignment_query


def _resolution_limitations(
    *, scope: ResolutionScope, status: ResolutionStatus
) -> tuple[ResolutionLimitation, ...]:
    if (
        status is not ResolutionStatus.UNRESOLVED
        and scope is ResolutionScope.DATASET_LEVEL_IDENTITY
    ):
        return (ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,)
    return ()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _without_top_level_run_economics(value: object) -> object:
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key not in CONTENT_HASH_EXCLUDED_FIELDS}
    return value


def _validate_nonnegative_count_map(
    value: dict[Any, int],
) -> dict[Any, int]:
    negative_keys = sorted(str(key) for key, count in value.items() if count < 0)
    if negative_keys:
        raise ValueError(f"count map has negative values for: {', '.join(negative_keys)}")
    return value
