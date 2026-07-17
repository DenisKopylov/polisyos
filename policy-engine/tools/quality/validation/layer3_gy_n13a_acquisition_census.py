"""Typed evidence and read-only catalog primitives for the GY-N13a census.

This module owns the census boundary schema and the smallest read path needed to
identify the acquisition catalog.  It never executes FetchPlans or writes to the
catalog/canonical stores. Connector calls are limited to explicit zero-network REPLAY
dry-runs and the separately authorized, bounded live characterization capture.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self
from urllib.parse import urlsplit

import duckdb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_VERSION = "policyos.policy_design_case.gy_n13a.acquisition_census.v1"
RULE_VERSION = "policyos.layer3.gy.n13a.acquisition_census.v1"
JOURNAL_SCHEMA_VERSION = "policyos.layer3.gy.n13a.live_probe_journal.v1"
CONTENT_HASH_EXCLUDED_FIELDS = frozenset(
    {
        "attempt_wall_time_seconds",
        "capture_wall_time_seconds",
        "elapsed_seconds",
        "event_log_content_sha256",
        "heartbeat_events",
        "observed_at",
        "wall_time_seconds",
    }
)
EXECUTABLE_BINDING_TIERS = frozenset({"fetchable", "transport_ready"})
DEFAULT_PROBES_PER_FAMILY = 12
MAX_PROBE_TIMEOUT_SECONDS = 15.0
MAX_PROBE_RESPONSE_BYTES = 65_536
MAX_HEARTBEAT_INTERVAL_SECONDS = 5.0
OPEN_LICENSE_IDENTIFIERS = frozenset(
    {
        "cc-by",
        "cc-by-4.0",
        "cc-by-sa",
        "gfdl",
        "odc-by",
        "odc-odbl",
        "other-pd",
        "uk-ogl",
    }
)
_FETCH_PLAN_FORBIDDEN_OWNERS = frozenset(
    {
        "FetchExecutor.execute",
        "FetchExecutor.preview",
    }
)
_REQUIRED_CONNECTOR_HARNESS_CHECKS = frozenset(
    {
        "capability_gated_methods_present",
        "connect_returns_unique_sessions",
        "core_methods_are_async",
        "disconnect_idempotent",
        "protocol_compliance",
        "required_class_attributes",
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
            "connector_params",
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
    CATALOG_ONLY = "catalog_only"
    ENDPOINT_UNUSABLE = "endpoint_unusable"
    CONNECTOR_OWNER_MISSING = "connector_owner_missing"
    CONNECTOR_CONTRACT_INVALID = "connector_contract_invalid"
    DRY_RUN_FAILED = "dry_run_failed"
    SCHEMA_PROFILE_MISSING = "schema_profile_missing"
    SOURCE_PROFILE_MISSING = "source_profile_missing"
    SOURCE_PROFILE_MISMATCH = "source_profile_mismatch"
    RESPONSE_BUDGET_EXCEEDED = "response_budget_exceeded"
    RESPONSE_SAFETY_BLOCKED = "response_safety_blocked"
    TRANSPORT_ERROR = "transport_error"


class ProbeDisposition(StrEnum):
    """Pre-network result derived from owner, safety, and catalog evidence."""

    LIVE_ATTEMPT_AUTHORIZED = "live_attempt_authorized"
    CONNECTOR_OWNER_MISSING = "connector_owner_missing"
    CONNECTOR_CONTRACT_INVALID = "connector_contract_invalid"
    DRY_RUN_FAILED = "dry_run_failed"
    SCHEMA_PROFILE_MISSING = "schema_profile_missing"
    SOURCE_PROFILE_MISSING = "source_profile_missing"
    SOURCE_PROFILE_MISMATCH = "source_profile_mismatch"
    AUTH_REQUIRED = "auth_required"
    CATALOG_ONLY = "catalog_only"
    ENDPOINT_UNUSABLE = "endpoint_unusable"
    LICENSE_UNCLEAR = "license_unclear"


class ConnectorDryRunOutcome(StrEnum):
    """Typed result of exercising one data-derived carrier under the simulator."""

    REPLAY_FIXTURE_MISSING = "replay_fixture_missing_after_interception"
    FETCH_RESULT_VALIDATED = "fetch_result_validated"
    FETCH_COMPLETED_WITHOUT_INTERCEPTION = "fetch_completed_without_interception"
    INTERCEPTED_RESPONSE_REJECTED = "intercepted_response_rejected"
    CONNECTOR_OWNER_MISSING = "connector_owner_missing"
    CONNECTOR_PROTOCOL_INVALID = "connector_protocol_invalid"
    SOURCE_PROFILE_MISSING = "source_profile_missing"
    SOURCE_PROFILE_MISMATCH = "source_profile_mismatch"
    PRETRANSPORT_REJECTED = "pretransport_rejected"
    NETWORK_ESCAPE_BLOCKED = "network_escape_blocked"


class FamilyLivenessState(StrEnum):
    """Aggregate state that never calls a partial sample a dead family."""

    LIVE_CHARACTERIZED = "live_characterized"
    MIXED_LIVE_AND_FINDINGS = "mixed_live_and_findings"
    NO_SAFE_LIVE_ATTEMPT = "no_safe_live_attempt"
    SAMPLE_DEAD_AFTER_HONEST_LEVERS = "sample_dead_after_honest_levers"
    CHARACTERIZATION_FAILED = "characterization_failed"


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
        expected_owners = tuple(sorted(_FETCH_PLAN_FORBIDDEN_OWNERS))
        if self.forbidden_owners != expected_owners:
            raise ValueError("forbidden owners must equal the behaviorally guarded executor edge")
        return self


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


class ConnectorDryRunAttempt(_StrictBoundaryModel):
    """One actual connector fetch attempt under the zero-network simulator fence."""

    attempt_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    source_profile_family: str | None = None
    request_dataset_id: str = Field(min_length=1)
    fetch_request_key: str | None = None
    connection_config_content_sha256: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    connector_fetch_invoked: bool
    fetch_completed: bool
    outcome: ConnectorDryRunOutcome
    finding_code: str | None = None
    failure_type: str | None = None
    simulator_mode: Literal["replay"]
    simulator_call_count: int = Field(ge=0)
    transport_intercepted: bool
    network_escape_attempt_count: int = Field(ge=0)
    actual_network_call_count: Literal[0]

    @model_validator(mode="after")
    def _outcome_is_derived_from_actual_calls(self) -> Self:
        reached_simulator = self.simulator_call_count > 0
        if self.transport_intercepted != reached_simulator:
            raise ValueError("transport interception must be recomputed from simulator calls")
        if self.outcome in {
            ConnectorDryRunOutcome.REPLAY_FIXTURE_MISSING,
            ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED,
            ConnectorDryRunOutcome.INTERCEPTED_RESPONSE_REJECTED,
        }:
            if not self.connector_fetch_invoked or not reached_simulator:
                raise ValueError("simulator outcomes require an actual intercepted connector fetch")
        elif reached_simulator:
            raise ValueError("pretransport outcomes cannot claim simulator calls")
        if self.fetch_completed != (
            self.outcome
            in {
                ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED,
                ConnectorDryRunOutcome.FETCH_COMPLETED_WITHOUT_INTERCEPTION,
            }
        ):
            raise ValueError("fetch completion must be derived from the dry-run outcome")
        if self.outcome is ConnectorDryRunOutcome.NETWORK_ESCAPE_BLOCKED:
            if self.network_escape_attempt_count < 1:
                raise ValueError("network escape outcome requires a blocked escape attempt")
        elif self.network_escape_attempt_count:
            raise ValueError("blocked network escape attempts require the matching typed outcome")
        failure_expected = not self.fetch_completed
        if (self.failure_type is not None) != failure_expected:
            raise ValueError("failure type presence must be derived from the dry-run outcome")
        finding_expected = self.outcome is not ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED
        if (self.finding_code is not None) != finding_expected:
            raise ValueError("finding presence must be derived from the dry-run outcome")
        request_built = self.fetch_request_key is not None
        config_built = self.connection_config_content_sha256 is not None
        if request_built != config_built:
            raise ValueError("request and connection config evidence must resolve together")
        if self.connector_fetch_invoked and not request_built:
            raise ValueError("connector fetch invocation requires request and config evidence")
        return self


class ConnectorFamilyReceipt(_StrictBoundaryModel):
    """Actual connector, public-harness, and simulator evidence for one family."""

    connector_id: str = Field(min_length=1)
    component_id: str | None = None
    connector_class: str | None = None
    protocol_violations: tuple[str, ...]
    protocol_conformant: bool
    harness_checks_passed: tuple[str, ...]
    harness_check_failures: tuple[str, ...]
    carrier_denominator: int = Field(ge=1)
    carrier_attempt_count: int = Field(ge=1)
    dry_run_attempts: tuple[ConnectorDryRunAttempt, ...]
    outcome_counts: dict[ConnectorDryRunOutcome, int]
    safe_dry_run_passed: bool
    simulator_mode: Literal["replay"]
    simulator_intercepted: bool
    simulator_call_count: int = Field(ge=0)
    network_escape_attempt_count: int = Field(ge=0)
    simulator_network_calls: Literal[0]

    @model_validator(mode="after")
    def _receipt_status_is_derived(self) -> Self:
        owner_resolved = self.component_id is not None and self.connector_class is not None
        if (self.component_id is None) != (self.connector_class is None):
            raise ValueError("component ID and connector class must resolve together")
        expected_protocol = owner_resolved and not self.protocol_violations
        if self.protocol_conformant != expected_protocol:
            raise ValueError("protocol status must be derived from owner validation")
        if self.harness_checks_passed != tuple(sorted(set(self.harness_checks_passed))):
            raise ValueError("passed harness checks must be unique and sorted")
        if self.harness_check_failures != tuple(sorted(set(self.harness_check_failures))):
            raise ValueError("harness failures must be unique and sorted")
        if set(self.harness_checks_passed) & set(self.harness_check_failures):
            raise ValueError("a harness check cannot both pass and fail")
        if owner_resolved and (
            set(self.harness_checks_passed) | set(self.harness_check_failures)
        ) != _REQUIRED_CONNECTOR_HARNESS_CHECKS:
            raise ValueError("every required public harness check must have a typed result")
        if not owner_resolved and (self.harness_checks_passed or self.harness_check_failures):
            raise ValueError("missing connector owners cannot claim harness execution")
        attempt_ids = tuple(attempt.attempt_id for attempt in self.dry_run_attempts)
        if attempt_ids != tuple(sorted(set(attempt_ids))):
            raise ValueError("dry-run carrier attempts must be unique and sorted")
        if self.carrier_attempt_count != len(self.dry_run_attempts):
            raise ValueError("carrier attempt count must equal the nested receipts")
        if self.carrier_denominator != self.carrier_attempt_count:
            raise ValueError("every selected carrier must receive an offline dry-run receipt")
        expected_outcomes = Counter(attempt.outcome for attempt in self.dry_run_attempts)
        if self.outcome_counts != dict(sorted(expected_outcomes.items(), key=lambda item: item[0])):
            raise ValueError("outcome counts must be recomputed from carrier receipts")
        expected_call_count = sum(attempt.simulator_call_count for attempt in self.dry_run_attempts)
        if self.simulator_call_count != expected_call_count:
            raise ValueError("family simulator calls must sum the carrier attempts")
        expected_escape_count = sum(
            attempt.network_escape_attempt_count for attempt in self.dry_run_attempts
        )
        if self.network_escape_attempt_count != expected_escape_count:
            raise ValueError("family escape attempts must sum the carrier attempts")
        expected_intercepted = self.simulator_call_count > 0
        if self.simulator_intercepted != expected_intercepted:
            raise ValueError("simulator interception must be recomputed from actual calls")
        safe_outcome = any(
            attempt.outcome
            in {
                ConnectorDryRunOutcome.REPLAY_FIXTURE_MISSING,
                ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED,
            }
            for attempt in self.dry_run_attempts
        )
        expected_safe = (
            expected_protocol
            and not self.harness_check_failures
            and set(self.harness_checks_passed) == _REQUIRED_CONNECTOR_HARNESS_CHECKS
            and safe_outcome
            and expected_intercepted
            and self.network_escape_attempt_count == 0
        )
        if self.safe_dry_run_passed != expected_safe:
            raise ValueError("dry-run gate must be derived from actual harness and simulator evidence")
        return self


class FamilySamplingReceipt(_StrictBoundaryModel):
    """Full-population and selected-strata counts for one data-derived family."""

    connector_id: str = Field(min_length=1)
    available_distribution_count: int = Field(ge=1)
    target_probe_count: int = Field(ge=1, le=15)
    selected_probe_count: int = Field(ge=1, le=15)
    stratum_population_counts: dict[str, int]
    selected_stratum_counts: dict[str, int]
    open_license_available_count: int = Field(ge=0)
    auth_required_available_count: int = Field(ge=0)
    schema_profile_available_count: int = Field(ge=0)

    @field_validator("stratum_population_counts", "selected_stratum_counts")
    @classmethod
    def _stratum_counts_are_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)

    @model_validator(mode="after")
    def _selection_counts_cover_the_declared_sample(self) -> Self:
        if sum(self.stratum_population_counts.values()) != self.available_distribution_count:
            raise ValueError("stratum populations must cover every family distribution")
        if sum(self.selected_stratum_counts.values()) != self.selected_probe_count:
            raise ValueError("selected strata must cover every sampled probe")
        if self.selected_probe_count != min(
            self.target_probe_count, self.available_distribution_count
        ):
            raise ValueError("sample count must equal target or the complete smaller population")
        if self.open_license_available_count > self.available_distribution_count:
            raise ValueError("open-license count exceeds the family population")
        if self.auth_required_available_count > self.available_distribution_count:
            raise ValueError("auth-required count exceeds the family population")
        if self.schema_profile_available_count > self.available_distribution_count:
            raise ValueError("schema-profile count exceeds the family population")
        return self


class ProbeCandidate(_StrictBoundaryModel):
    """One deterministic distribution-level member of the stratified census sample."""

    attempt_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    execution_tier: str = Field(min_length=1)
    quality_score: float = Field(ge=0.0, le=1.0)
    quality_bucket: Literal["q00_24", "q25_49", "q50_74", "q75_100"]
    binding_confidence: float = Field(ge=0.0, le=1.0)
    endpoint_url: str
    connector_params: dict[str, Any]
    filters: dict[str, list[str]]
    access_license: str
    auth_required: bool
    parser_supported: bool
    schema_profile: SchemaProfileContract | None
    family_sample_rank: int = Field(ge=1, le=15)
    stratum_id: str = Field(min_length=1)
    stratum_rank: int = Field(ge=1)

    @model_validator(mode="after")
    def _candidate_edges_are_exact(self) -> Self:
        if self.schema_profile is not None:
            if self.schema_profile.distribution_id != self.distribution_id:
                raise ValueError("probe schema profile must bind the exact distribution")
            if self.schema_profile.dataset_id != self.dataset_id:
                raise ValueError("probe schema profile must bind the exact dataset")
            if self.schema_profile.profile_id != self.profile_id:
                raise ValueError("probe schema profile must bind the exact profile")
        expected_bucket = _quality_bucket(self.quality_score)
        if self.quality_bucket != expected_bucket:
            raise ValueError("quality bucket must be recomputed from owner quality")
        if self.stratum_id != f"{self.execution_tier}:{self.quality_bucket}":
            raise ValueError("stratum must be execution tier x quality bucket")
        return self


class ProbeBudget(_StrictBoundaryModel):
    """Derived HTTP limits carried by one live characterization request."""

    profile_timeout_seconds: float | None = Field(default=None, gt=0.0)
    profile_rate_limit_rps: float | None = Field(default=None, gt=0.0)
    profile_requests_per_hour: int | None = Field(default=None, gt=0)
    timeout_seconds: float = Field(gt=0.0)
    max_response_bytes: int = Field(gt=0)
    minimum_interval_seconds: float = Field(ge=0.0)
    heartbeat_interval_seconds: float = Field(gt=0.0)
    call_budget: Literal[1] = 1

    @model_validator(mode="after")
    def _limits_are_derived_from_profile_and_census_caps(self) -> Self:
        if self.profile_timeout_seconds is not None:
            expected_timeout = min(self.profile_timeout_seconds, MAX_PROBE_TIMEOUT_SECONDS)
            if self.timeout_seconds != expected_timeout:
                raise ValueError("probe timeout must be derived from profile and census cap")
        intervals = []
        if self.profile_rate_limit_rps is not None:
            intervals.append(1.0 / self.profile_rate_limit_rps)
        if self.profile_requests_per_hour is not None:
            intervals.append(3600.0 / self.profile_requests_per_hour)
        if intervals and abs(self.minimum_interval_seconds - max(intervals)) > 1e-9:
            raise ValueError("probe interval must be derived from owner rate limits")
        expected_heartbeat = min(
            MAX_HEARTBEAT_INTERVAL_SECONDS,
            self.timeout_seconds / 5.0,
        )
        if abs(self.heartbeat_interval_seconds - expected_heartbeat) > 1e-9:
            raise ValueError("heartbeat interval must be derived from the inactivity budget")
        return self


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


class ProbePreflight(_StrictBoundaryModel):
    """Fail-closed authorization decision recomputed before any network call."""

    attempt_id: str = Field(min_length=1)
    connector_owner_resolved: bool
    protocol_conformant: bool
    simulator_intercepted: bool
    schema_profile_resolved: bool
    source_profile_resolved: bool
    source_profile_family_matches: bool
    open_license_validated: bool
    auth_required: bool
    execution_tier: str = Field(min_length=1)
    endpoint_scheme: Literal["http", "https", "other", "missing"]
    disposition: ProbeDisposition

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        expected = _derive_probe_disposition(
            connector_owner_resolved=self.connector_owner_resolved,
            protocol_conformant=self.protocol_conformant,
            simulator_intercepted=self.simulator_intercepted,
            schema_profile_resolved=self.schema_profile_resolved,
            source_profile_resolved=self.source_profile_resolved,
            source_profile_family_matches=self.source_profile_family_matches,
            open_license_validated=self.open_license_validated,
            auth_required=self.auth_required,
            execution_tier=self.execution_tier,
            endpoint_scheme=self.endpoint_scheme,
        )
        if self.disposition is not expected:
            raise ValueError(
                "probe disposition must be recomputed from decisive preflight evidence"
            )
        return self


class ProbeHeartbeat(_StrictBoundaryModel):
    """Append+fsync progress evidence emitted while one live attempt is active."""

    attempt_id: str = Field(min_length=1)
    journal_sequence: int = Field(ge=2)
    phase: Literal["attempt_started", "waiting", "response_headers", "body_progress"]
    progress_bytes: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0.0)


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

    @model_validator(mode="after")
    def _body_evidence_is_self_consistent(self) -> Self:
        if self.bounded_body_base64 is None:
            if self.bytes_read != 0 or self.body_sha256 is not None:
                raise ValueError("missing response body cannot claim bytes or content hash")
        else:
            try:
                body = base64.b64decode(self.bounded_body_base64, validate=True)
            except ValueError as exc:
                raise ValueError("bounded response body must be canonical base64") from exc
            expected_hash = f"sha256:{hashlib.sha256(body).hexdigest()}"
            if self.bytes_read != len(body) or self.body_sha256 != expected_hash:
                raise ValueError("response byte count/hash must bind the journaled body")
        return self


class ProbeTransportResult(_StrictBoundaryModel):
    """One-call transport result before journal sequencing is attached."""

    status_code: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str]
    bounded_body_base64: str | None = None
    body_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    bytes_read: int = Field(ge=0)
    transport_error_code: str | None = None

    @model_validator(mode="after")
    def _transport_body_is_self_consistent(self) -> Self:
        ProbeRawResponse(
            attempt_id="transport-validation",
            request_record_sha256="sha256:" + "0" * 64,
            journal_sequence=1,
            status_code=self.status_code,
            response_headers=self.response_headers,
            bounded_body_base64=self.bounded_body_base64,
            body_sha256=self.body_sha256,
            bytes_read=self.bytes_read,
            transport_error_code=self.transport_error_code,
        )
        return self


class _ProbeHeartbeatJournal:
    """Mutable per-attempt progress owner that cannot leak loop variables."""

    def __init__(
        self,
        *,
        attempt_id: str,
        event_log_path: Path,
        initial_sequence: int,
        started: float,
        interval_seconds: float,
        heartbeat_sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        self.attempt_id = attempt_id
        self.event_log_path = event_log_path
        self.sequence = initial_sequence
        self.started = started
        self.interval_seconds = interval_seconds
        self.heartbeat_sleep = heartbeat_sleep
        self.events: list[ProbeHeartbeat] = []
        self.last_progress_bytes = 0
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()

    async def emit(self, phase: str, progress_bytes: int) -> None:
        """Append and fsync one monotone heartbeat event."""

        async with self.lock:
            self.last_progress_bytes = max(self.last_progress_bytes, progress_bytes)
            self.sequence += 1
            heartbeat = ProbeHeartbeat(
                attempt_id=self.attempt_id,
                journal_sequence=self.sequence,
                phase=phase,
                progress_bytes=self.last_progress_bytes,
                elapsed_seconds=max(time.monotonic() - self.started, 0.0),
            )
            _append_fsync_jsonl(
                self.event_log_path,
                {
                    "sequence": heartbeat.journal_sequence,
                    "event_kind": "heartbeat",
                    "heartbeat": heartbeat.model_dump(mode="json"),
                },
            )
            self.events.append(heartbeat)

    async def emit_waiting(self) -> None:
        """Emit periodic progress while the carrier remains in flight."""

        while not self.stop_event.is_set():
            await self.heartbeat_sleep(self.interval_seconds)
            if not self.stop_event.is_set():
                await self.emit("waiting", self.last_progress_bytes)

    async def stop(self, task: asyncio.Task[None]) -> None:
        """Stop the periodic emitter without masking the transport result."""

        self.stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


class DerivedLiveness(_StrictBoundaryModel):
    """Liveness state recomputed from a journaled response and owner profile."""

    attempt_id: str = Field(min_length=1)
    liveness_state: LivenessState
    decisive_evidence_refs: tuple[str, ...] = Field(min_length=1)


class ProbeJournalRecord(_StrictBoundaryModel):
    """One selected probe with ordered request, evidence, and classification receipts."""

    candidate: ProbeCandidate
    request: ProbeRequest | None
    preflight: ProbePreflight
    raw_response: ProbeRawResponse | None
    heartbeat_events: tuple[ProbeHeartbeat, ...]
    derived_liveness: DerivedLiveness
    request_journal_sequence: int = Field(ge=1)
    evidence_journal_sequence: int = Field(ge=2)
    classification_journal_sequence: int = Field(ge=3)
    attempt_wall_time_seconds: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _record_is_ordered_and_recomputed(self) -> Self:
        attempt_ids = {
            self.candidate.attempt_id,
            self.preflight.attempt_id,
            self.derived_liveness.attempt_id,
        }
        if self.request is not None:
            attempt_ids.add(self.request.attempt_id)
        if self.raw_response is not None:
            attempt_ids.add(self.raw_response.attempt_id)
        attempt_ids.update(heartbeat.attempt_id for heartbeat in self.heartbeat_events)
        if len(attempt_ids) != 1:
            raise ValueError("all probe evidence must share one attempt ID")
        if self.request is not None:
            if self.request.metric_id != self.candidate.metric_id:
                raise ValueError("probe request must preserve the selected metric")
            if self.request.request_variable != self.candidate.metric_id:
                raise ValueError("each live attempt must carry exactly one selected variable")
            if self.request.connector_id != self.candidate.connector_id:
                raise ValueError("probe request must preserve the selected connector")
            if self.request.schema_profile != self.candidate.schema_profile:
                raise ValueError("schema-profile contract must travel with the request")
        if self.preflight.execution_tier != self.candidate.execution_tier:
            raise ValueError("preflight must preserve the selected execution tier")
        if not (
            self.request_journal_sequence
            < self.evidence_journal_sequence
            < self.classification_journal_sequence
        ):
            raise ValueError("request/evidence/classification journal order is load-bearing")
        live_authorized = self.preflight.disposition is ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED
        if live_authorized and not self.heartbeat_events:
            raise ValueError("an authorized live attempt requires journaled heartbeat evidence")
        if not live_authorized and self.heartbeat_events:
            raise ValueError("a no-attempt preflight result cannot claim heartbeat evidence")
        heartbeat_sequences = tuple(
            heartbeat.journal_sequence for heartbeat in self.heartbeat_events
        )
        if heartbeat_sequences != tuple(sorted(set(heartbeat_sequences))):
            raise ValueError("heartbeat sequences must be unique and ordered")
        if heartbeat_sequences and not all(
            self.request_journal_sequence < sequence < self.evidence_journal_sequence
            for sequence in heartbeat_sequences
        ):
            raise ValueError("heartbeats must be journaled between request and terminal evidence")
        if self.heartbeat_events:
            if self.heartbeat_events[0].phase != "attempt_started":
                raise ValueError("the first heartbeat must prove the attempt started")
            progress = tuple(heartbeat.progress_bytes for heartbeat in self.heartbeat_events)
            elapsed = tuple(heartbeat.elapsed_seconds for heartbeat in self.heartbeat_events)
            if progress != tuple(sorted(progress)) or elapsed != tuple(sorted(elapsed)):
                raise ValueError("heartbeat progress and elapsed time must be monotone")
        if live_authorized and self.raw_response is None:
            raise ValueError("an authorized live result requires journaled raw response evidence")
        if live_authorized and self.request is None:
            raise ValueError("an authorized live result requires a schema-carrying request")
        if not live_authorized and self.raw_response is not None:
            raise ValueError("a no-attempt preflight result cannot claim a raw response")
        if self.raw_response is not None:
            if self.raw_response.journal_sequence != self.evidence_journal_sequence:
                raise ValueError("raw response sequence must equal the evidence sequence")
            if self.request is None:
                raise ValueError("raw response cannot exist without a request")
            if self.raw_response.request_record_sha256 != semantic_content_hash(self.request):
                raise ValueError("raw response must bind the exact journaled request")
            phases = {heartbeat.phase for heartbeat in self.heartbeat_events}
            if self.raw_response.status_code is not None and "response_headers" not in phases:
                raise ValueError("an HTTP response requires a journaled headers heartbeat")
            if self.raw_response.bytes_read > 0:
                body_progress = tuple(
                    heartbeat.progress_bytes
                    for heartbeat in self.heartbeat_events
                    if heartbeat.phase == "body_progress"
                )
                if not body_progress or body_progress[-1] != self.raw_response.bytes_read:
                    raise ValueError("response bytes must be covered by body-progress heartbeats")
        if (
            live_authorized
            and self.request is not None
            and self.attempt_wall_time_seconds
            >= self.request.budget.heartbeat_interval_seconds * 1.5
            and not any(heartbeat.phase == "waiting" for heartbeat in self.heartbeat_events)
        ):
            raise ValueError("a long live attempt requires a periodic waiting heartbeat")
        expected_state = _derive_probe_liveness_state(
            request=self.request,
            preflight=self.preflight,
            raw_response=self.raw_response,
        )
        if self.derived_liveness.liveness_state is not expected_state:
            raise ValueError("liveness state must be recomputed from paid journal evidence")
        return self


class FamilyScorecard(_StrictBoundaryModel):
    """Aggregate characterization result for one data-enumerated family."""

    connector_id: str = Field(min_length=1)
    selected_probe_count: int = Field(ge=0)
    live_attempt_count: int = Field(ge=0)
    network_call_count: int = Field(ge=0)
    response_bytes: int = Field(ge=0)
    wall_time_seconds: float = Field(ge=0.0)
    dry_run_passed: bool
    liveness_counts: dict[LivenessState, int]
    family_liveness_state: FamilyLivenessState
    tier_decay_findings: tuple[str, ...]

    @field_validator("liveness_counts")
    @classmethod
    def _counts_must_be_nonnegative(
        cls, value: dict[LivenessState, int]
    ) -> dict[LivenessState, int]:
        return _validate_nonnegative_count_map(value)

    @model_validator(mode="after")
    def _scorecard_counts_cover_the_family_sample(self) -> Self:
        if sum(self.liveness_counts.values()) != self.selected_probe_count:
            raise ValueError("liveness counts must cover every selected family probe")
        if self.live_attempt_count > self.selected_probe_count:
            raise ValueError("live attempts cannot exceed selected probes")
        if self.network_call_count != self.live_attempt_count:
            raise ValueError("one live attempt must equal one bounded network call")
        expected_family_state = _derive_family_liveness_state(
            selected_probe_count=self.selected_probe_count,
            live_attempt_count=self.live_attempt_count,
            liveness_counts=self.liveness_counts,
        )
        if self.family_liveness_state is not expected_family_state:
            raise ValueError("family liveness must be recomputed from the scorecard")
        return self


class GrowthBacklogRow(_StrictBoundaryModel):
    """Demand-ranked residual without claiming a parallel VOI authority."""

    rank: int = Field(ge=1)
    variable_id: str = Field(min_length=1)
    gap_kind: DemandGapKind
    demand_sources: tuple[str, ...] = Field(min_length=1)
    route_demand: float = Field(ge=0.0)
    binding_confidence: float = Field(ge=0.0, le=1.0)
    ranking_score: float = Field(ge=0.0)
    ranking_method: Literal["interim_binding_confidence_x_route_demand"]
    authority_boundary: Literal["ranking_only_not_voi"]
    voi_owner_fit: Literal["metric_residual_granularity_not_supported"]
    voi_owner_ref: Literal[
        "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition"
    ]
    voi_owner_integration: Literal["routed_to_gy_n13b"]

    @model_validator(mode="after")
    def _score_is_derived_from_declared_inputs(self) -> Self:
        if self.route_demand != float(len(self.demand_sources)):
            raise ValueError("route_demand must count distinct demand sources")
        expected_score = round(self.binding_confidence * self.route_demand, 12)
        if self.ranking_score != expected_score:
            raise ValueError("ranking_score must equal binding confidence times route demand")
        return self


class ProjectionBinding(_StrictBoundaryModel):
    """Narrow upstream projection identity bound by the census."""

    projection_id: str = Field(min_length=1)
    source_artifact: str = Field(min_length=1)
    projection_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    projected_item_count: int = Field(ge=0)


class ProbeSelectionPlan(_StrictBoundaryModel):
    """Data-derived family denominator and deterministic 10–15-row sample."""

    family_projection_binding: ProjectionBinding
    target_per_family: int = Field(ge=1, le=15)
    sampling_receipts: tuple[FamilySamplingReceipt, ...] = Field(min_length=1)
    candidates: tuple[ProbeCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _plan_covers_every_projected_family(self) -> Self:
        receipt_families = tuple(row.connector_id for row in self.sampling_receipts)
        if receipt_families != tuple(sorted(set(receipt_families))):
            raise ValueError("sampling receipts must be unique and sorted by family")
        if self.family_projection_binding.projected_item_count != len(receipt_families):
            raise ValueError("family projection must cover every sampling receipt")
        candidate_counts = Counter(row.connector_id for row in self.candidates)
        for receipt in self.sampling_receipts:
            if receipt.target_probe_count != self.target_per_family:
                raise ValueError("each family must use the declared sample target")
            if candidate_counts[receipt.connector_id] != receipt.selected_probe_count:
                raise ValueError("candidate rows must cover every selected family probe")
        if set(candidate_counts) != set(receipt_families):
            raise ValueError("candidate families must equal the full family denominator")
        candidate_keys = tuple(
            (row.connector_id, row.family_sample_rank) for row in self.candidates
        )
        expected_keys = tuple(sorted(candidate_keys, key=lambda item: (item[0], item[1])))
        if candidate_keys != expected_keys or len(candidate_keys) != len(set(candidate_keys)):
            raise ValueError("probe candidates must have unique canonical family ranks")
        return self


class LiveProbeJournal(_StrictBoundaryModel):
    """Frozen quarantine journal; response bytes never enter a canonical store."""

    schema_version: Literal[JOURNAL_SCHEMA_VERSION]
    rule_version: Literal[RULE_VERSION]
    producer: Literal[
        "tools.quality.validation.layer3_gy_n13a_acquisition_census.capture_probe_records"
    ]
    selection_plan: ProbeSelectionPlan
    family_receipts: tuple[ConnectorFamilyReceipt, ...]
    records: tuple[ProbeJournalRecord, ...]
    event_log_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_at: datetime
    capture_wall_time_seconds: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _journal_covers_the_plan_and_owner_receipts(self) -> Self:
        families = tuple(row.connector_id for row in self.selection_plan.sampling_receipts)
        receipt_families = tuple(row.connector_id for row in self.family_receipts)
        if receipt_families != families:
            raise ValueError("owner receipts must cover the exact data-derived family denominator")
        plan_attempts = tuple(row.attempt_id for row in self.selection_plan.candidates)
        record_attempts = tuple(row.candidate.attempt_id for row in self.records)
        if record_attempts != plan_attempts:
            raise ValueError("journal records must cover every selected probe in plan order")
        sequences = [
            sequence
            for record in self.records
            for sequence in (
                record.request_journal_sequence,
                *(heartbeat.journal_sequence for heartbeat in record.heartbeat_events),
                record.evidence_journal_sequence,
                record.classification_journal_sequence,
            )
        ]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("journal event sequences must be contiguous and ordered")
        expected_event_hash = _bytes_sha256(probe_journal_event_bytes(self.records))
        if self.event_log_content_sha256 != expected_event_hash:
            raise ValueError("event-log hash must bind the reconstructed journal evidence")
        return self


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
    producer: Literal[
        "tools.quality.validation.layer3_gy_n13a_acquisition_census.assemble_census_manifest"
    ]
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

    @model_validator(mode="after")
    def _classes_and_denominators_are_evidence_derived(self) -> Self:
        binding_ids = tuple(row.projection_id for row in self.projection_bindings)
        if binding_ids != tuple(sorted(set(binding_ids))):
            raise ValueError("projection bindings must be unique and sorted")

        metric_ids = tuple(row.metric_id for row in self.metric_resolutions)
        if metric_ids != tuple(sorted(set(metric_ids))):
            raise ValueError("metric resolution denominator must be unique and sorted")
        if len(metric_ids) != self.catalog_identity.binding_metric_count:
            raise ValueError("metric resolution denominator must cover every catalog metric")

        demand_ids = tuple(row.variable_id for row in self.reverse_demand_variables)
        if demand_ids != tuple(sorted(set(demand_ids))):
            raise ValueError("reverse demand denominator must be unique and sorted")
        expected_residuals = reverse_demand_residuals(self.reverse_demand_variables)
        if self.reverse_demand_residuals != expected_residuals:
            raise ValueError("reverse-demand residuals must be recomputed from full evidence")

        route_ids = tuple(row.route.route_id for row in self.route_evidence)
        if route_ids != tuple(sorted(set(route_ids))):
            raise ValueError("route evidence denominator must be unique and sorted")

        family_ids = tuple(row.connector_id for row in self.family_scorecards)
        if family_ids != tuple(sorted(set(family_ids))):
            raise ValueError("family scorecards must be unique and sorted")
        if len(family_ids) != self.catalog_identity.connector_family_count:
            raise ValueError("scorecards must cover every catalog connector family")

        if self.growth_backlog != derive_growth_backlog(self.reverse_demand_residuals):
            raise ValueError("growth backlog must preserve and rank every residual")
        return self


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
    """Hash semantic evidence while recursively excluding run economics."""

    stable = _without_run_economics(_json_value(value))
    return f"sha256:{hashlib.sha256(canonical_json_bytes(stable)).hexdigest()}"


def assemble_census_manifest(
    *,
    catalog_source: CatalogSource,
    projection_bindings: Sequence[ProjectionBinding],
    metric_resolutions: Sequence[MetricResolution],
    reverse_demand_variables: Sequence[DemandVariableEvidence],
    route_evidence: Sequence[RouteEvidence],
    fetch_plan_generation: FetchPlanGenerationProof,
    family_scorecards: Sequence[FamilyScorecard],
    journal_content_sha256: str,
    observed_at: datetime,
    capture_wall_time_seconds: float,
) -> CensusManifest:
    """Assemble the frozen census only from owner-derived projections and evidence."""

    demand_rows = tuple(reverse_demand_variables)
    residuals = reverse_demand_residuals(demand_rows)
    return CensusManifest(
        schema_version=SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        producer=(
            "tools.quality.validation.layer3_gy_n13a_acquisition_census."
            "assemble_census_manifest"
        ),
        catalog_identity=catalog_source.identity,
        projection_bindings=tuple(
            sorted(projection_bindings, key=lambda row: row.projection_id)
        ),
        metric_resolutions=tuple(metric_resolutions),
        reverse_demand_variables=demand_rows,
        reverse_demand_residuals=residuals,
        route_evidence=tuple(route_evidence),
        fetch_plan_generation=fetch_plan_generation,
        family_scorecards=tuple(family_scorecards),
        growth_backlog=derive_growth_backlog(residuals),
        journal_content_sha256=journal_content_sha256,
        observed_at=observed_at,
        capture_wall_time_seconds=capture_wall_time_seconds,
    )


def read_census_manifest(path: Path) -> CensusManifest:
    """Read and strictly validate one frozen census artifact."""

    try:
        return CensusManifest.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as exc:
        raise CatalogContractError("census_artifact_invalid", f"{path}: {exc}") from exc


def validate_census_manifest(
    stored: CensusManifest,
    *,
    recomputed: CensusManifest,
) -> CensusManifest:
    """Fail closed when any stored decisive field differs from live recomputation."""

    if stored != recomputed:
        raise CatalogContractError(
            "census_artifact_drift",
            "stored census differs from the catalog, upstream projections, or probe journal",
        )
    return recomputed


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
                eligible[metric_id].resolution_status is not ResolutionStatus.EXACT,
                metric_id,
            ),
        )
        for metric_id in ordered_metrics:
            bindings = graph.resolve_metric_bindings(metric_id, top_k=3)
            executable_bindings = [
                binding
                for binding in bindings
                if str(getattr(binding, "execution_tier", "")) in EXECUTABLE_BINDING_TIERS
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
                    for tier, count in resolution_by_metric[metric_id].binding_tier_counts.items()
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
                raise CatalogContractError("fetch_plan_owner_duplicate_metric", metric_id)
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
                raise CatalogContractError("fetch_plan_catalog_owner_not_called", metric_id)
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


def select_stratified_probe_candidates(
    catalog_path: Path,
    *,
    per_family: int = DEFAULT_PROBES_PER_FAMILY,
    source_locator: str,
) -> ProbeSelectionPlan:
    """Select a deterministic round-robin tier×quality sample for every family.

    The family denominator and candidate population come only from validated
    ``ds_metric_bindings`` owner rows. Within each stratum, exact schema profiles,
    recognized open licenses, no-auth endpoints, HTTP transport, parser support,
    binding confidence, and stable IDs define preference. Every excluded condition
    remains visible in the population receipts and downstream preflight evidence.
    """

    if not 1 <= per_family <= 15:
        raise CatalogContractError(
            "probe_sample_target_invalid", "per-family sample must be between 1 and 15"
        )
    if not source_locator.strip():
        raise CatalogContractError("probe_source_locator_missing", "empty locator")
    connection = _open_validated_catalog(catalog_path)
    try:
        rows = connection.execute(
            """
            SELECT binding.metric_id,
                   binding.dataset_id,
                   binding.distribution_id,
                   binding.connector_id,
                   binding.profile_id,
                   binding.request_dataset_id,
                   binding.confidence,
                   binding.default_filters,
                   binding.execution_tier,
                   distribution.url,
                   distribution.connector_params,
                   distribution.quality_score,
                   distribution.parser_supported,
                   dataset.access_license,
                   dataset.access_auth_required,
                   schema_profile.columns_json,
                   schema_profile.sample_row_count,
                   schema_profile.preview_sample_hash,
                   schema_profile.inference_mode,
                   schema_profile.parser_mode
            FROM ds_metric_bindings AS binding
            JOIN ds_distributions AS distribution
              ON distribution.id = binding.distribution_id
             AND distribution.dataset_id = binding.dataset_id
             AND distribution.connector_type = binding.connector_id
             AND distribution.profile_id = binding.profile_id
            JOIN ds_datasets AS dataset ON dataset.id = binding.dataset_id
            LEFT JOIN ds_schema_profiles AS schema_profile
              ON schema_profile.distribution_id = binding.distribution_id
             AND schema_profile.dataset_id = binding.dataset_id
            ORDER BY binding.connector_id,
                     binding.distribution_id,
                     binding.confidence DESC,
                     binding.metric_id,
                     binding.request_dataset_id
            """
        ).fetchall()
    finally:
        connection.close()

    representative_rows: dict[tuple[str, str], tuple[Any, ...]] = {}
    for row in rows:
        key = (str(row[3]), str(row[2]))
        representative_rows.setdefault(key, row)
    populations: defaultdict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for (connector_id, _), row in representative_rows.items():
        populations[connector_id].append(row)
    if not populations:
        raise CatalogContractError("probe_family_denominator_empty", "no binding families")

    receipts: list[FamilySamplingReceipt] = []
    candidates: list[ProbeCandidate] = []
    for connector_id in sorted(populations):
        population = populations[connector_id]
        strata: defaultdict[str, list[tuple[Any, ...]]] = defaultdict(list)
        for row in population:
            quality_score = float(row[11] or 0.0)
            stratum_id = f"{row[8]!s}:{_quality_bucket(quality_score)}"
            strata[stratum_id].append(row)
        for stratum_rows in strata.values():
            stratum_rows.sort(key=_probe_candidate_preference_key)

        selected: list[tuple[tuple[Any, ...], str, int]] = []
        cursors = dict.fromkeys(strata, 0)
        ordered_strata = sorted(strata, key=_probe_stratum_sort_key)
        while len(selected) < min(per_family, len(population)):
            advanced = False
            for stratum_id in ordered_strata:
                cursor = cursors[stratum_id]
                stratum_rows = strata[stratum_id]
                if cursor >= len(stratum_rows):
                    continue
                selected.append((stratum_rows[cursor], stratum_id, cursor + 1))
                cursors[stratum_id] += 1
                advanced = True
                if len(selected) == min(per_family, len(population)):
                    break
            if not advanced:  # pragma: no cover - protected by population count
                raise CatalogContractError("probe_stratification_stalled", connector_id)

        selected_strata = Counter(stratum_id for _, stratum_id, _ in selected)
        receipts.append(
            FamilySamplingReceipt(
                connector_id=connector_id,
                available_distribution_count=len(population),
                target_probe_count=per_family,
                selected_probe_count=len(selected),
                stratum_population_counts=dict(
                    sorted(
                        (stratum_id, len(stratum_rows))
                        for stratum_id, stratum_rows in strata.items()
                    )
                ),
                selected_stratum_counts=dict(sorted(selected_strata.items())),
                open_license_available_count=sum(
                    _is_open_license(str(row[13] or "")) for row in population
                ),
                auth_required_available_count=sum(bool(row[14]) for row in population),
                schema_profile_available_count=sum(row[15] is not None for row in population),
            )
        )
        for family_rank, (row, stratum_id, stratum_rank) in enumerate(selected, start=1):
            schema_profile = _schema_profile_from_catalog_row(row)
            filters = _coerce_plan_filters(_json_mapping(row[7]))
            connector_params = _json_mapping(row[10])
            attempt_hash = hashlib.sha256(
                canonical_json_bytes(
                    {
                        "connector_id": connector_id,
                        "distribution_id": str(row[2]),
                        "metric_id": str(row[0]),
                    }
                )
            ).hexdigest()[:20]
            candidates.append(
                ProbeCandidate(
                    attempt_id=f"gy-n13a-{attempt_hash}",
                    connector_id=connector_id,
                    metric_id=str(row[0]),
                    dataset_id=str(row[1]),
                    distribution_id=str(row[2]),
                    profile_id=str(row[4]),
                    request_dataset_id=str(row[5]),
                    execution_tier=str(row[8]),
                    quality_score=float(row[11] or 0.0),
                    quality_bucket=_quality_bucket(float(row[11] or 0.0)),
                    binding_confidence=float(row[6] or 0.0),
                    endpoint_url=str(row[9] or ""),
                    connector_params=connector_params,
                    filters=filters,
                    access_license=str(row[13] or ""),
                    auth_required=bool(row[14]),
                    parser_supported=bool(row[12]),
                    schema_profile=schema_profile,
                    family_sample_rank=family_rank,
                    stratum_id=stratum_id,
                    stratum_rank=stratum_rank,
                )
            )

    family_items = tuple(receipt.model_dump(mode="json") for receipt in receipts)
    return ProbeSelectionPlan(
        family_projection_binding=_projection_binding(
            "catalog_connector_families",
            source_locator,
            family_items,
        ),
        target_per_family=per_family,
        sampling_receipts=tuple(receipts),
        candidates=tuple(candidates),
    )


def validate_probe_family_denominator(
    catalog_source: CatalogSource,
    selection_plan: ProbeSelectionPlan,
) -> ProbeSelectionPlan:
    """Require probes for every family derived from binding-owner rows."""

    selected_families = tuple(
        receipt.connector_id for receipt in selection_plan.sampling_receipts
    )
    if selected_families != catalog_source.connector_families:
        raise CatalogContractError(
            "probe_family_denominator_drift",
            "probe families must equal distinct ds_metric_bindings.connector_id values",
        )
    return selection_plan


def derive_connector_family_receipts(
    selection_plan: ProbeSelectionPlan,
    *,
    fixture_root: Path,
) -> tuple[ConnectorFamilyReceipt, ...]:
    """Run every selected carrier through its actual connector under REPLAY."""

    families = tuple(row.connector_id for row in selection_plan.sampling_receipts)
    if families != tuple(sorted(set(families))):
        raise CatalogContractError(
            "connector_family_denominator_invalid",
            "families must be unique and sorted",
        )
    candidate_families = tuple(sorted({row.connector_id for row in selection_plan.candidates}))
    if candidate_families != families:
        raise CatalogContractError(
            "connector_carrier_denominator_invalid",
            "selected carriers must cover every data-derived family",
        )
    return asyncio.run(
        _derive_connector_family_receipts_async(
            selection_plan,
            fixture_root=fixture_root,
        )
    )


def prepare_probe_records(
    selection_plan: ProbeSelectionPlan,
    family_receipts: Sequence[ConnectorFamilyReceipt],
) -> tuple[tuple[ProbeCandidate, ProbeRequest | None, ProbePreflight], ...]:
    """Prepare request carriers and fail-closed no-attempt receipts without I/O."""

    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    receipts = {receipt.connector_id: receipt for receipt in family_receipts}
    expected_families = tuple(row.connector_id for row in selection_plan.sampling_receipts)
    if tuple(receipts) != expected_families:
        raise CatalogContractError(
            "probe_family_receipt_coverage_mismatch",
            "family receipts must cover the selection denominator in canonical order",
        )
    registry = SourceProfileRegistry.get_instance()
    prepared: list[tuple[ProbeCandidate, ProbeRequest | None, ProbePreflight]] = []
    dry_runs = {
        attempt.attempt_id: attempt
        for receipt in family_receipts
        for attempt in receipt.dry_run_attempts
    }
    expected_attempt_ids = {candidate.attempt_id for candidate in selection_plan.candidates}
    if set(dry_runs) != expected_attempt_ids:
        raise CatalogContractError(
            "probe_carrier_receipt_coverage_mismatch",
            "dry-run receipts must cover every selected carrier exactly once",
        )
    for candidate in selection_plan.candidates:
        receipt = receipts[candidate.connector_id]
        dry_run = dry_runs[candidate.attempt_id]
        source_profile = registry.get(candidate.profile_id)
        source_profile_family = (
            str(source_profile.connector_family) if source_profile is not None else None
        )
        family_namespace = candidate.connector_id.split(".", maxsplit=1)[0]
        family_matches = source_profile_family == family_namespace
        scheme = _endpoint_scheme(candidate.endpoint_url)
        family_harness_safe = (
            receipt.protocol_conformant
            and not receipt.harness_check_failures
            and set(receipt.harness_checks_passed) == _REQUIRED_CONNECTOR_HARNESS_CHECKS
        )
        carrier_dry_run_safe = (
            family_harness_safe
            and dry_run.outcome
            in {
                ConnectorDryRunOutcome.REPLAY_FIXTURE_MISSING,
                ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED,
            }
            and dry_run.transport_intercepted
            and dry_run.network_escape_attempt_count == 0
        )
        preflight = ProbePreflight(
            attempt_id=candidate.attempt_id,
            connector_owner_resolved=receipt.component_id is not None,
            protocol_conformant=receipt.protocol_conformant,
            simulator_intercepted=carrier_dry_run_safe,
            schema_profile_resolved=candidate.schema_profile is not None,
            source_profile_resolved=source_profile is not None,
            source_profile_family_matches=family_matches,
            open_license_validated=_is_open_license(candidate.access_license),
            auth_required=candidate.auth_required,
            execution_tier=candidate.execution_tier,
            endpoint_scheme=scheme,
            disposition=_derive_probe_disposition(
                connector_owner_resolved=receipt.component_id is not None,
                protocol_conformant=receipt.protocol_conformant,
                simulator_intercepted=carrier_dry_run_safe,
                schema_profile_resolved=candidate.schema_profile is not None,
                source_profile_resolved=source_profile is not None,
                source_profile_family_matches=family_matches,
                open_license_validated=_is_open_license(candidate.access_license),
                auth_required=candidate.auth_required,
                execution_tier=candidate.execution_tier,
                endpoint_scheme=scheme,
            ),
        )
        request: ProbeRequest | None = None
        if preflight.disposition is ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED:
            if source_profile is None or candidate.schema_profile is None:
                raise CatalogContractError(
                    "probe_authorized_without_owner_contract", candidate.attempt_id
                )
            budget = _probe_budget_from_source_profile(source_profile)
            request = ProbeRequest(
                attempt_id=candidate.attempt_id,
                metric_id=candidate.metric_id,
                request_variable=candidate.metric_id,
                connector_id=candidate.connector_id,
                request_dataset_id=candidate.request_dataset_id,
                endpoint_url=candidate.endpoint_url,
                schema_profile=candidate.schema_profile,
                budget=budget,
                access_license=candidate.access_license,
                auth_required=candidate.auth_required,
                dry_run_receipt_sha256=semantic_content_hash(receipt),
            )
        prepared.append((candidate, request, preflight))
    return tuple(prepared)


def derive_probe_liveness(
    *,
    request: ProbeRequest | None,
    preflight: ProbePreflight,
    raw_response: ProbeRawResponse | None,
    event_log_path: Path | None = None,
) -> DerivedLiveness:
    """Classify only from preflight and journaled raw response evidence."""

    del event_log_path
    state = _derive_probe_liveness_state(
        request=request,
        preflight=preflight,
        raw_response=raw_response,
    )
    refs = [f"preflight:{preflight.disposition.value}"]
    if raw_response is not None:
        refs.append(f"journal:response:{raw_response.journal_sequence}")
        if raw_response.status_code is not None:
            refs.append(f"http_status:{raw_response.status_code}")
        if raw_response.transport_error_code is not None:
            refs.append(f"transport:{raw_response.transport_error_code}")
    if request is not None:
        profile = request.schema_profile
        refs.append(f"schema_profile:{profile.inference_mode}:{profile.sample_row_count}")
    return DerivedLiveness(
        attempt_id=preflight.attempt_id,
        liveness_state=state,
        decisive_evidence_refs=tuple(sorted(set(refs))),
    )


async def capture_probe_records(
    prepared: Sequence[tuple[ProbeCandidate, ProbeRequest | None, ProbePreflight]],
    *,
    event_log_path: Path,
    transport: Callable[
        [ProbeRequest, Callable[[str, int], Awaitable[None]]],
        Awaitable[ProbeTransportResult],
    ]
    | None = None,
    classifier: Callable[..., DerivedLiveness] = derive_probe_liveness,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    heartbeat_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[ProbeJournalRecord, ...]:
    """Capture one family at a time with append+fsync before classification."""

    if event_log_path.exists() and event_log_path.stat().st_size:
        raise CatalogContractError("probe_event_log_not_empty", str(event_log_path))
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    live_transport = transport or _execute_live_probe
    records: list[ProbeJournalRecord] = []
    sequence = 0
    previous_call_finished: dict[str, float] = {}
    for candidate, request, preflight in prepared:
        sequence += 1
        request_sequence = sequence
        _append_fsync_jsonl(
            event_log_path,
            {
                "sequence": request_sequence,
                "event_kind": "request" if request is not None else "selection",
                "attempt_id": candidate.attempt_id,
                "request": request.model_dump(mode="json") if request is not None else None,
                "candidate_sha256": semantic_content_hash(candidate),
            },
        )
        raw_response: ProbeRawResponse | None = None
        heartbeat_events: list[ProbeHeartbeat] = []
        attempt_wall_time = 0.0
        if preflight.disposition is ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED:
            if request is None:
                raise CatalogContractError("probe_live_request_missing", candidate.attempt_id)
            previous = previous_call_finished.get(candidate.connector_id)
            if previous is not None:
                remaining = request.budget.minimum_interval_seconds - (time.monotonic() - previous)
                if remaining > 0:
                    await sleep(remaining)
            started = time.monotonic()
            heartbeat_journal = _ProbeHeartbeatJournal(
                attempt_id=candidate.attempt_id,
                event_log_path=event_log_path,
                initial_sequence=sequence,
                started=started,
                interval_seconds=request.budget.heartbeat_interval_seconds,
                heartbeat_sleep=heartbeat_sleep,
            )
            await heartbeat_journal.emit("attempt_started", 0)
            heartbeat_task = asyncio.create_task(heartbeat_journal.emit_waiting())
            try:
                result = await live_transport(request, heartbeat_journal.emit)
            finally:
                await heartbeat_journal.stop(heartbeat_task)
            sequence = heartbeat_journal.sequence
            heartbeat_events.extend(heartbeat_journal.events)
            attempt_wall_time = time.monotonic() - started
            previous_call_finished[candidate.connector_id] = time.monotonic()
            sequence += 1
            evidence_sequence = sequence
            raw_response = ProbeRawResponse(
                attempt_id=candidate.attempt_id,
                request_record_sha256=semantic_content_hash(request),
                journal_sequence=evidence_sequence,
                **result.model_dump(mode="python"),
            )
            _append_fsync_jsonl(
                event_log_path,
                {
                    "sequence": evidence_sequence,
                    "event_kind": "raw_response",
                    "raw_response": raw_response.model_dump(mode="json"),
                },
            )
        else:
            sequence += 1
            evidence_sequence = sequence
            _append_fsync_jsonl(
                event_log_path,
                {
                    "sequence": evidence_sequence,
                    "event_kind": "preflight_no_attempt",
                    "attempt_id": candidate.attempt_id,
                    "disposition": preflight.disposition.value,
                },
            )

        derived = classifier(
            request=request,
            preflight=preflight,
            raw_response=raw_response,
            event_log_path=event_log_path,
        )
        sequence += 1
        classification_sequence = sequence
        _append_fsync_jsonl(
            event_log_path,
            {
                "sequence": classification_sequence,
                "event_kind": "classification",
                "derived_liveness": derived.model_dump(mode="json"),
            },
        )
        records.append(
            ProbeJournalRecord(
                candidate=candidate,
                request=request,
                preflight=preflight,
                raw_response=raw_response,
                heartbeat_events=tuple(heartbeat_events),
                derived_liveness=derived,
                request_journal_sequence=request_sequence,
                evidence_journal_sequence=evidence_sequence,
                classification_journal_sequence=classification_sequence,
                attempt_wall_time_seconds=attempt_wall_time,
            )
        )
    return tuple(records)


def capture_live_probe_journal(
    selection_plan: ProbeSelectionPlan,
    family_receipts: Sequence[ConnectorFamilyReceipt],
    *,
    event_log_path: Path,
    observed_at: datetime | None = None,
) -> LiveProbeJournal:
    """Run the explicit live lane and freeze its quarantine evidence in memory."""

    started = time.monotonic()
    records = asyncio.run(
        capture_probe_records(
            prepare_probe_records(selection_plan, family_receipts),
            event_log_path=event_log_path,
        )
    )
    wall_time = time.monotonic() - started
    return assemble_live_probe_journal(
        selection_plan,
        family_receipts,
        records,
        event_log_path=event_log_path,
        observed_at=observed_at or datetime.now(UTC),
        capture_wall_time_seconds=wall_time,
    )


def assemble_live_probe_journal(
    selection_plan: ProbeSelectionPlan,
    family_receipts: Sequence[ConnectorFamilyReceipt],
    records: Sequence[ProbeJournalRecord],
    *,
    event_log_path: Path,
    observed_at: datetime,
    capture_wall_time_seconds: float,
) -> LiveProbeJournal:
    """Assemble a strict journal after the append+fsync event log is complete."""

    return LiveProbeJournal(
        schema_version=JOURNAL_SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        producer=(
            "tools.quality.validation.layer3_gy_n13a_acquisition_census.capture_probe_records"
        ),
        selection_plan=selection_plan,
        family_receipts=tuple(family_receipts),
        records=tuple(records),
        event_log_content_sha256=_file_sha256(event_log_path),
        observed_at=observed_at,
        capture_wall_time_seconds=capture_wall_time_seconds,
    )


def probe_journal_event_bytes(records: Sequence[ProbeJournalRecord]) -> bytes:
    """Reconstruct the exact append-only event stream from frozen records."""

    chunks: list[bytes] = []
    for record in records:
        chunks.append(
            canonical_json_bytes(
                {
                    "sequence": record.request_journal_sequence,
                    "event_kind": "request" if record.request is not None else "selection",
                    "attempt_id": record.candidate.attempt_id,
                    "request": (
                        record.request.model_dump(mode="json")
                        if record.request is not None
                        else None
                    ),
                    "candidate_sha256": semantic_content_hash(record.candidate),
                }
            )
        )
        for heartbeat in record.heartbeat_events:
            chunks.append(
                canonical_json_bytes(
                    {
                        "sequence": heartbeat.journal_sequence,
                        "event_kind": "heartbeat",
                        "heartbeat": heartbeat.model_dump(mode="json"),
                    }
                )
            )
        if record.raw_response is not None:
            evidence = {
                "sequence": record.evidence_journal_sequence,
                "event_kind": "raw_response",
                "raw_response": record.raw_response.model_dump(mode="json"),
            }
        else:
            evidence = {
                "sequence": record.evidence_journal_sequence,
                "event_kind": "preflight_no_attempt",
                "attempt_id": record.candidate.attempt_id,
                "disposition": record.preflight.disposition.value,
            }
        chunks.append(canonical_json_bytes(evidence))
        chunks.append(
            canonical_json_bytes(
                {
                    "sequence": record.classification_journal_sequence,
                    "event_kind": "classification",
                    "derived_liveness": record.derived_liveness.model_dump(mode="json"),
                }
            )
        )
    return b"".join(chunks)


def read_live_probe_journal(path: Path) -> LiveProbeJournal:
    """Load and strictly validate the self-contained frozen quarantine journal."""

    try:
        return LiveProbeJournal.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise CatalogContractError("probe_journal_invalid", str(exc)) from exc


def validate_live_probe_journal(
    journal: LiveProbeJournal,
    *,
    selection_plan: ProbeSelectionPlan,
    family_receipts: Sequence[ConnectorFamilyReceipt],
) -> tuple[FamilyScorecard, ...]:
    """Recompute owner/preflight/classification evidence without network access."""

    if journal.selection_plan != selection_plan:
        raise CatalogContractError(
            "probe_journal_selection_drift",
            "frozen sample differs from the current catalog-derived sample",
        )
    if journal.family_receipts != tuple(family_receipts):
        raise CatalogContractError(
            "probe_journal_owner_receipt_drift",
            "frozen connector owner receipts differ from current owners",
        )
    expected_prepared = prepare_probe_records(selection_plan, family_receipts)
    expected_by_attempt = {
        candidate.attempt_id: (candidate, request, preflight)
        for candidate, request, preflight in expected_prepared
    }
    for record in journal.records:
        expected = expected_by_attempt.get(record.candidate.attempt_id)
        if expected != (record.candidate, record.request, record.preflight):
            raise CatalogContractError("probe_journal_preflight_drift", record.candidate.attempt_id)
        recomputed = derive_probe_liveness(
            request=record.request,
            preflight=record.preflight,
            raw_response=record.raw_response,
        )
        if recomputed != record.derived_liveness:
            raise CatalogContractError("probe_journal_liveness_drift", record.candidate.attempt_id)
    return derive_family_scorecards(journal.records)


def derive_family_scorecards(
    records: Sequence[ProbeJournalRecord],
) -> tuple[FamilyScorecard, ...]:
    """Recompute per-family liveness and tier-decay findings from journal records."""

    grouped: defaultdict[str, list[ProbeJournalRecord]] = defaultdict(list)
    for record in records:
        grouped[record.candidate.connector_id].append(record)
    scorecards: list[FamilyScorecard] = []
    alive_states = {
        LivenessState.ALIVE_CONFORMANT,
        LivenessState.ALIVE_SCHEMA_DRIFT,
        LivenessState.ALIVE_SCHEMA_UNVERIFIED,
    }
    for connector_id in sorted(grouped):
        family_records = grouped[connector_id]
        counts = Counter(record.derived_liveness.liveness_state for record in family_records)
        decay_counts = Counter(
            (record.candidate.execution_tier, record.derived_liveness.liveness_state)
            for record in family_records
            if record.candidate.execution_tier in EXECUTABLE_BINDING_TIERS
            and record.derived_liveness.liveness_state not in alive_states
        )
        scorecards.append(
            FamilyScorecard(
                connector_id=connector_id,
                selected_probe_count=len(family_records),
                live_attempt_count=sum(
                    record.raw_response is not None for record in family_records
                ),
                network_call_count=sum(
                    record.raw_response is not None for record in family_records
                ),
                response_bytes=sum(
                    record.raw_response.bytes_read
                    for record in family_records
                    if record.raw_response is not None
                ),
                wall_time_seconds=sum(
                    record.attempt_wall_time_seconds for record in family_records
                ),
                dry_run_passed=all(
                    record.preflight.protocol_conformant and record.preflight.simulator_intercepted
                    for record in family_records
                ),
                liveness_counts=dict(sorted(counts.items(), key=lambda item: item[0].value)),
                family_liveness_state=_derive_family_liveness_state(
                    selected_probe_count=len(family_records),
                    live_attempt_count=sum(
                        record.raw_response is not None for record in family_records
                    ),
                    liveness_counts=dict(counts),
                ),
                tier_decay_findings=tuple(
                    f"execution_tier_decay:{tier}:{state.value}:count={count}"
                    for (tier, state), count in sorted(
                        decay_counts.items(), key=lambda item: (item[0][0], item[0][1].value)
                    )
                ),
            )
        )
    return tuple(scorecards)


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


def derive_growth_backlog(
    residuals: Sequence[ReverseDemandResidual],
) -> tuple[GrowthBacklogRow, ...]:
    """Rank the complete metric-level gap denominator without inventing VOI.

    The canonical acquisition planner consumes typed claim/requirement gaps and an
    optional VOI decision report.  Raw census metric residuals do not carry that
    authority-bearing contract, so N13a records the mismatch and uses only the
    explicitly permitted interim score: existing binding confidence multiplied by
    the number of distinct upstream demand sources.
    """

    variable_ids = tuple(row.variable_id for row in residuals)
    if len(variable_ids) != len(set(variable_ids)):
        raise CatalogContractError(
            "growth_backlog_denominator_invalid", "residual variable IDs must be unique"
        )
    unranked = [
        GrowthBacklogRow(
            rank=1,
            variable_id=row.variable_id,
            gap_kind=row.gap_kind,
            demand_sources=row.demand_sources,
            route_demand=float(len(row.demand_sources)),
            binding_confidence=row.best_binding_confidence,
            ranking_score=round(
                row.best_binding_confidence * float(len(row.demand_sources)), 12
            ),
            ranking_method="interim_binding_confidence_x_route_demand",
            authority_boundary="ranking_only_not_voi",
            voi_owner_fit="metric_residual_granularity_not_supported",
            voi_owner_ref=(
                "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition"
            ),
            voi_owner_integration="routed_to_gy_n13b",
        )
        for row in residuals
    ]
    ordered = sorted(
        unranked,
        key=lambda row: (
            -row.ranking_score,
            -row.route_demand,
            -row.binding_confidence,
            row.variable_id,
            row.gap_kind.value,
        ),
    )
    return tuple(row.model_copy(update={"rank": rank}) for rank, row in enumerate(ordered, 1))


def validate_growth_backlog(
    rows: Sequence[GrowthBacklogRow],
    *,
    residuals: Sequence[ReverseDemandResidual],
) -> tuple[GrowthBacklogRow, ...]:
    """Fail closed when a stored backlog differs from the evidence-derived order."""

    expected = derive_growth_backlog(residuals)
    observed = tuple(rows)
    if observed != expected:
        raise CatalogContractError(
            "growth_backlog_drift",
            "stored rows must cover and rank the complete reverse-demand residual denominator",
        )
    return expected


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
        "request_dataset_id": str(getattr(binding, "request_dataset_id", "") or ""),
        "profile_id": str(getattr(binding, "profile_id", "") or ""),
        "catalog_dataset_id": str(getattr(binding, "catalog_dataset_id", "") or ""),
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
    expected_filters = _coerce_plan_filters(getattr(binding, "default_filters", {}) or {})
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


async def _derive_connector_family_receipts_async(
    selection_plan: ProbeSelectionPlan,
    *,
    fixture_root: Path,
) -> tuple[ConnectorFamilyReceipt, ...]:
    import socket
    from unittest.mock import patch

    from polisyos.fabric.connectors.base import FetchRequest
    from polisyos.fabric.connectors.capabilities import validate_protocol_compliance
    from polisyos.fabric.connectors.components import __polisyos_components__
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
    from polisyos.fabric.connectors.testing.harness import ConnectorTestHarness
    from polisyos.fabric.connectors.testing.simulator import (
        APISimulator,
        MissingFixtureError,
        SimulatorMode,
    )

    components = {
        str(component.connector_class.connector_id): component
        for component in __polisyos_components__
    }
    registry = SourceProfileRegistry.get_instance()
    candidates_by_family: dict[str, list[ProbeCandidate]] = defaultdict(list)
    for candidate in selection_plan.candidates:
        candidates_by_family[candidate.connector_id].append(candidate)

    def exception_type(exc: BaseException) -> str:
        return f"{type(exc).__module__}.{type(exc).__name__}"

    def unresolved_attempt(
        candidate: ProbeCandidate,
        *,
        outcome: ConnectorDryRunOutcome,
        failure_type: str,
        finding_code: str,
        source_profile_family: str | None = None,
    ) -> ConnectorDryRunAttempt:
        return ConnectorDryRunAttempt(
            attempt_id=candidate.attempt_id,
            profile_id=candidate.profile_id,
            source_profile_family=source_profile_family,
            request_dataset_id=candidate.request_dataset_id,
            fetch_request_key=None,
            connection_config_content_sha256=None,
            connector_fetch_invoked=False,
            fetch_completed=False,
            outcome=outcome,
            finding_code=finding_code,
            failure_type=failure_type,
            simulator_mode="replay",
            simulator_call_count=0,
            transport_intercepted=False,
            network_escape_attempt_count=0,
            actual_network_call_count=0,
        )

    async def run_lifecycle_check(
        harness: ConnectorTestHarness,
        method_name: str,
        connector_class: type[Any],
        candidates: Sequence[ProbeCandidate],
    ) -> bool:
        method = getattr(harness, f"test_{method_name}")
        for candidate in candidates:
            profile = registry.get(candidate.profile_id)
            if profile is None:
                continue
            if str(profile.connector_family) != candidate.connector_id.split(".", 1)[0]:
                continue
            harness.sample_config = resolve_connection_config(profile)
            blocked_escapes: list[str] = []

            def block_network(
                *_: Any,
                _blocked_escapes: list[str] = blocked_escapes,
                _method_name: str = method_name,
                _candidate: ProbeCandidate = candidate,
                **__: Any,
            ) -> None:
                _blocked_escapes.append(_method_name)
                raise CensusExecutionFenceError(
                    "connector_dry_run_network_escape",
                    f"{_candidate.connector_id}:{_method_name}",
                )

            check_passed = False
            try:
                with (
                    patch.object(socket.socket, "connect", new=block_network),
                    patch.object(socket.socket, "connect_ex", new=block_network),
                    patch.object(socket, "create_connection", new=block_network),
                ):
                    await method(connector_class())
            except Exception:
                check_passed = False
            else:
                check_passed = not blocked_escapes
            if check_passed:
                return True
        return False

    async def run_carrier(
        candidate: ProbeCandidate,
        *,
        connector_class: type[Any],
        harness: ConnectorTestHarness,
    ) -> ConnectorDryRunAttempt:
        profile = registry.get(candidate.profile_id)
        if profile is None:
            return unresolved_attempt(
                candidate,
                outcome=ConnectorDryRunOutcome.SOURCE_PROFILE_MISSING,
                failure_type="SourceProfileMissing",
                finding_code="source_profile_missing",
            )
        source_profile_family = str(profile.connector_family)
        expected_family = candidate.connector_id.split(".", 1)[0]
        if source_profile_family != expected_family:
            return unresolved_attempt(
                candidate,
                outcome=ConnectorDryRunOutcome.SOURCE_PROFILE_MISMATCH,
                failure_type="SourceProfileFamilyMismatch",
                finding_code="source_profile_family_mismatch",
                source_profile_family=source_profile_family,
            )

        config = resolve_connection_config(profile)
        request = FetchRequest(
            dataset_id=candidate.request_dataset_id,
            filters=tuple(
                (key, tuple(values)) for key, values in sorted(candidate.filters.items())
            ),
        )
        harness.sample_config = config
        harness.sample_request = request
        simulator = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=fixture_root,
            connector_id=candidate.connector_id,
            dataset_id=candidate.request_dataset_id,
            max_call_log_entries=100,
        )
        blocked_escapes: list[str] = []
        connector_fetch_invoked = False
        fetch_completed = False
        captured_exception: BaseException | None = None

        def block_network(*_: Any, **__: Any) -> None:
            blocked_escapes.append(candidate.attempt_id)
            raise CensusExecutionFenceError(
                "connector_dry_run_network_escape",
                candidate.attempt_id,
            )

        connector = connector_class()
        handle: Any | None = None
        with (
            patch.object(socket.socket, "connect", new=block_network),
            patch.object(socket.socket, "connect_ex", new=block_network),
            patch.object(socket, "create_connection", new=block_network),
        ):
            try:
                handle = await connector.connect(config)
                async with simulator:
                    connector_fetch_invoked = True
                    await asyncio.wait_for(
                        harness.test_fetch_returns_fetch_result((connector, handle)),
                        timeout=5.0,
                    )
                fetch_completed = True
            except BaseException as exc:  # noqa: BLE001 - typed evidence boundary
                captured_exception = exc
            finally:
                if handle is not None:
                    try:
                        await connector.disconnect(handle)
                    except BaseException as exc:  # noqa: BLE001 - typed evidence boundary
                        if captured_exception is None:
                            captured_exception = exc

        call_count = simulator.call_count
        intercepted = call_count > 0
        if blocked_escapes:
            outcome = ConnectorDryRunOutcome.NETWORK_ESCAPE_BLOCKED
            finding_code = "network_escape_blocked"
            failure = captured_exception or CensusExecutionFenceError(
                "connector_dry_run_network_escape", candidate.attempt_id
            )
        elif fetch_completed and intercepted:
            outcome = ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED
            finding_code = None
            failure = None
        elif fetch_completed:
            outcome = ConnectorDryRunOutcome.FETCH_COMPLETED_WITHOUT_INTERCEPTION
            finding_code = "fetch_completed_without_simulator_interception"
            failure = None
        elif isinstance(captured_exception, MissingFixtureError) and intercepted:
            outcome = ConnectorDryRunOutcome.REPLAY_FIXTURE_MISSING
            finding_code = "replay_fixture_missing_after_interception"
            failure = captured_exception
        elif intercepted:
            outcome = ConnectorDryRunOutcome.INTERCEPTED_RESPONSE_REJECTED
            finding_code = "intercepted_response_rejected"
            failure = captured_exception or RuntimeError("intercepted response rejected")
        else:
            outcome = ConnectorDryRunOutcome.PRETRANSPORT_REJECTED
            finding_code = "connector_pretransport_rejected"
            failure = captured_exception or RuntimeError("connector fetch did not reach transport")

        return ConnectorDryRunAttempt(
            attempt_id=candidate.attempt_id,
            profile_id=candidate.profile_id,
            source_profile_family=source_profile_family,
            request_dataset_id=candidate.request_dataset_id,
            fetch_request_key=request.request_key,
            connection_config_content_sha256=semantic_content_hash(
                config.to_dict(redact=True)
            ),
            connector_fetch_invoked=connector_fetch_invoked,
            fetch_completed=fetch_completed,
            outcome=outcome,
            finding_code=finding_code,
            failure_type=exception_type(failure) if failure is not None else None,
            simulator_mode="replay",
            simulator_call_count=call_count,
            transport_intercepted=intercepted,
            network_escape_attempt_count=len(blocked_escapes),
            actual_network_call_count=0,
        )

    receipts: list[ConnectorFamilyReceipt] = []
    for sampling_receipt in selection_plan.sampling_receipts:
        connector_id = sampling_receipt.connector_id
        candidates = tuple(candidates_by_family[connector_id])
        component = components.get(connector_id)
        if component is None:
            attempts = tuple(
                unresolved_attempt(
                    candidate,
                    outcome=ConnectorDryRunOutcome.CONNECTOR_OWNER_MISSING,
                    failure_type="ConnectorComponentMissing",
                    finding_code="connector_component_missing",
                )
                for candidate in sorted(candidates, key=lambda row: row.attempt_id)
            )
            receipts.append(
                ConnectorFamilyReceipt(
                    connector_id=connector_id,
                    component_id=None,
                    connector_class=None,
                    protocol_violations=("connector_component_missing",),
                    protocol_conformant=False,
                    harness_checks_passed=(),
                    harness_check_failures=(),
                    carrier_denominator=len(candidates),
                    carrier_attempt_count=len(attempts),
                    dry_run_attempts=attempts,
                    outcome_counts=dict(Counter(row.outcome for row in attempts)),
                    safe_dry_run_passed=False,
                    simulator_mode="replay",
                    simulator_intercepted=False,
                    simulator_call_count=0,
                    network_escape_attempt_count=0,
                    simulator_network_calls=0,
                )
            )
            continue
        violations = tuple(
            sorted(
                str(violation)
                for violation in validate_protocol_compliance(component.connector_class)
            )
        )
        harness = ConnectorTestHarness()
        harness.connector_class = component.connector_class
        passed_checks: set[str] = set()
        failed_checks: set[str] = set()
        for check_name in sorted(
            _REQUIRED_CONNECTOR_HARNESS_CHECKS
            - {"connect_returns_unique_sessions", "disconnect_idempotent"}
        ):
            try:
                getattr(harness, f"test_{check_name}")()
            except Exception:
                failed_checks.add(check_name)
            else:
                passed_checks.add(check_name)
        for check_name in ("connect_returns_unique_sessions", "disconnect_idempotent"):
            if await run_lifecycle_check(
                harness,
                check_name,
                component.connector_class,
                candidates,
            ):
                passed_checks.add(check_name)
            else:
                failed_checks.add(check_name)

        if violations:
            attempts = tuple(
                unresolved_attempt(
                    candidate,
                    outcome=ConnectorDryRunOutcome.CONNECTOR_PROTOCOL_INVALID,
                    failure_type="ConnectorProtocolInvalid",
                    finding_code="connector_protocol_invalid",
                )
                for candidate in sorted(candidates, key=lambda row: row.attempt_id)
            )
        else:
            carrier_attempts = []
            for candidate in candidates:
                carrier_attempts.append(
                    await run_carrier(
                        candidate,
                        connector_class=component.connector_class,
                        harness=harness,
                    )
                )
            attempts = tuple(
                sorted(carrier_attempts, key=lambda row: row.attempt_id)
            )
        simulator_call_count = sum(row.simulator_call_count for row in attempts)
        escape_count = sum(row.network_escape_attempt_count for row in attempts)
        safe_outcome = any(
            row.outcome
            in {
                ConnectorDryRunOutcome.REPLAY_FIXTURE_MISSING,
                ConnectorDryRunOutcome.FETCH_RESULT_VALIDATED,
            }
            for row in attempts
        )
        safe_dry_run_passed = (
            not violations
            and not failed_checks
            and passed_checks == _REQUIRED_CONNECTOR_HARNESS_CHECKS
            and safe_outcome
            and escape_count == 0
        )
        receipts.append(
            ConnectorFamilyReceipt(
                connector_id=connector_id,
                component_id=str(component.metadata.component_id),
                connector_class=(
                    f"{component.connector_class.__module__}.{component.connector_class.__name__}"
                ),
                protocol_violations=violations,
                protocol_conformant=not violations,
                harness_checks_passed=tuple(sorted(passed_checks)),
                harness_check_failures=tuple(sorted(failed_checks)),
                carrier_denominator=len(candidates),
                carrier_attempt_count=len(attempts),
                dry_run_attempts=attempts,
                outcome_counts=dict(Counter(row.outcome for row in attempts)),
                safe_dry_run_passed=safe_dry_run_passed,
                simulator_mode="replay",
                simulator_intercepted=simulator_call_count > 0,
                simulator_call_count=simulator_call_count,
                network_escape_attempt_count=escape_count,
                simulator_network_calls=0,
            )
        )
    return tuple(receipts)


def _quality_bucket(score: float) -> str:
    if score < 0.25:
        return "q00_24"
    if score < 0.5:
        return "q25_49"
    if score < 0.75:
        return "q50_74"
    return "q75_100"


def _probe_stratum_sort_key(stratum_id: str) -> tuple[int, int, str]:
    tier, bucket = stratum_id.split(":", maxsplit=1)
    tier_order = {"transport_ready": 0, "fetchable": 1, "catalog": 2}
    bucket_order = {"q75_100": 0, "q50_74": 1, "q25_49": 2, "q00_24": 3}
    return tier_order.get(tier, 99), bucket_order.get(bucket, 99), stratum_id


def _probe_candidate_preference_key(row: tuple[Any, ...]) -> tuple[Any, ...]:
    return (
        row[15] is None,
        not _is_open_license(str(row[13] or "")),
        bool(row[14]),
        _endpoint_scheme(str(row[9] or "")) not in {"http", "https"},
        not bool(row[12]),
        -float(row[6] or 0.0),
        -float(row[11] or 0.0),
        str(row[2]),
        str(row[0]),
    )


def _json_mapping(value: object) -> dict[str, Any]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(parsed, Mapping):
        return {}
    return {str(key): _json_value(item) for key, item in parsed.items()}


def _schema_profile_from_catalog_row(
    row: tuple[Any, ...],
) -> SchemaProfileContract | None:
    if row[15] is None:
        return None
    raw_columns: object = row[15]
    if isinstance(raw_columns, str):
        try:
            raw_columns = json.loads(raw_columns)
        except json.JSONDecodeError as exc:
            raise CatalogContractError("probe_schema_profile_columns_invalid", str(row[2])) from exc
    columns: list[str] = []
    if isinstance(raw_columns, Sequence) and not isinstance(raw_columns, (str, bytes, bytearray)):
        for item in raw_columns:
            if isinstance(item, str) and item.strip():
                columns.append(item.strip())
            elif isinstance(item, Mapping):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    columns.append(name.strip())
    elif isinstance(raw_columns, Mapping):
        columns.extend(str(key) for key in raw_columns)
    return SchemaProfileContract(
        distribution_id=str(row[2]),
        dataset_id=str(row[1]),
        profile_id=str(row[4]),
        columns=tuple(sorted(set(columns))),
        sample_row_count=int(row[16] or 0),
        preview_sample_hash=str(row[17]) if row[17] is not None else None,
        inference_mode=str(row[18] or "metadata_only"),
        parser_mode=str(row[19] or "metadata_only"),
    )


def _normalize_license(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _is_open_license(value: str) -> bool:
    return _normalize_license(value) in OPEN_LICENSE_IDENTIFIERS


def _endpoint_scheme(value: str) -> Literal["http", "https", "other", "missing"]:
    if not value.strip():
        return "missing"
    scheme = urlsplit(value).scheme.lower()
    if scheme == "http":
        return "http"
    if scheme == "https":
        return "https"
    return "other"


def _derive_probe_disposition(
    *,
    connector_owner_resolved: bool,
    protocol_conformant: bool,
    simulator_intercepted: bool,
    schema_profile_resolved: bool,
    source_profile_resolved: bool,
    source_profile_family_matches: bool,
    open_license_validated: bool,
    auth_required: bool,
    execution_tier: str,
    endpoint_scheme: str,
) -> ProbeDisposition:
    if not connector_owner_resolved:
        return ProbeDisposition.CONNECTOR_OWNER_MISSING
    if not protocol_conformant:
        return ProbeDisposition.CONNECTOR_CONTRACT_INVALID
    if not schema_profile_resolved:
        return ProbeDisposition.SCHEMA_PROFILE_MISSING
    if not source_profile_resolved:
        return ProbeDisposition.SOURCE_PROFILE_MISSING
    if not source_profile_family_matches:
        return ProbeDisposition.SOURCE_PROFILE_MISMATCH
    if auth_required:
        return ProbeDisposition.AUTH_REQUIRED
    if execution_tier not in EXECUTABLE_BINDING_TIERS:
        return ProbeDisposition.CATALOG_ONLY
    if endpoint_scheme not in {"http", "https"}:
        return ProbeDisposition.ENDPOINT_UNUSABLE
    if not open_license_validated:
        return ProbeDisposition.LICENSE_UNCLEAR
    if not simulator_intercepted:
        return ProbeDisposition.DRY_RUN_FAILED
    return ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED


def _probe_budget_from_source_profile(profile: Any) -> ProbeBudget:
    profile_timeout = float(profile.timeout_seconds)
    rate_limit_rps = float(profile.rate_limit_rps) if profile.rate_limit_rps is not None else None
    requests_per_hour = (
        int(profile.requests_per_hour) if profile.requests_per_hour is not None else None
    )
    intervals = []
    if rate_limit_rps is not None:
        intervals.append(1.0 / rate_limit_rps)
    if requests_per_hour is not None:
        intervals.append(3600.0 / requests_per_hour)
    timeout_seconds = min(profile_timeout, MAX_PROBE_TIMEOUT_SECONDS)
    return ProbeBudget(
        profile_timeout_seconds=profile_timeout,
        profile_rate_limit_rps=rate_limit_rps,
        profile_requests_per_hour=requests_per_hour,
        timeout_seconds=timeout_seconds,
        max_response_bytes=MAX_PROBE_RESPONSE_BYTES,
        minimum_interval_seconds=max(intervals, default=0.0),
        heartbeat_interval_seconds=min(
            MAX_HEARTBEAT_INTERVAL_SECONDS,
            timeout_seconds / 5.0,
        ),
        call_budget=1,
    )


def _derive_probe_liveness_state(
    *,
    request: ProbeRequest | None,
    preflight: ProbePreflight,
    raw_response: ProbeRawResponse | None,
) -> LivenessState:
    preflight_states = {
        ProbeDisposition.CONNECTOR_OWNER_MISSING: LivenessState.CONNECTOR_OWNER_MISSING,
        ProbeDisposition.CONNECTOR_CONTRACT_INVALID: LivenessState.CONNECTOR_CONTRACT_INVALID,
        ProbeDisposition.DRY_RUN_FAILED: LivenessState.DRY_RUN_FAILED,
        ProbeDisposition.SCHEMA_PROFILE_MISSING: LivenessState.SCHEMA_PROFILE_MISSING,
        ProbeDisposition.SOURCE_PROFILE_MISSING: LivenessState.SOURCE_PROFILE_MISSING,
        ProbeDisposition.SOURCE_PROFILE_MISMATCH: LivenessState.SOURCE_PROFILE_MISMATCH,
        ProbeDisposition.AUTH_REQUIRED: LivenessState.AUTH_REQUIRED,
        ProbeDisposition.CATALOG_ONLY: LivenessState.CATALOG_ONLY,
        ProbeDisposition.ENDPOINT_UNUSABLE: LivenessState.ENDPOINT_UNUSABLE,
        ProbeDisposition.LICENSE_UNCLEAR: LivenessState.LICENSE_UNCLEAR,
    }
    if preflight.disposition is not ProbeDisposition.LIVE_ATTEMPT_AUTHORIZED:
        return preflight_states[preflight.disposition]
    if request is None or raw_response is None:
        raise ValueError("authorized probe requires request and raw response")
    if raw_response.transport_error_code is not None:
        if raw_response.transport_error_code == "response_budget_exceeded":
            return LivenessState.RESPONSE_BUDGET_EXCEEDED
        if raw_response.transport_error_code == "response_safety_blocked":
            return LivenessState.RESPONSE_SAFETY_BLOCKED
        return LivenessState.TRANSPORT_ERROR
    status = raw_response.status_code
    if status in {401, 403}:
        return LivenessState.AUTH_REQUIRED
    if status == 429:
        return LivenessState.RATE_LIMITED
    if status in {404, 410}:
        return LivenessState.DEAD
    if status is None or not 200 <= status < 300:
        return LivenessState.TRANSPORT_ERROR
    profile = request.schema_profile
    if (
        profile.sample_row_count == 0
        or profile.preview_sample_hash is None
        or profile.inference_mode == "metadata_only"
    ):
        return LivenessState.ALIVE_SCHEMA_UNVERIFIED
    observed_columns = _response_columns(raw_response, profile.parser_mode)
    if observed_columns is not None and set(profile.columns) <= observed_columns:
        return LivenessState.ALIVE_CONFORMANT
    return LivenessState.ALIVE_SCHEMA_DRIFT


def _derive_family_liveness_state(
    *,
    selected_probe_count: int,
    live_attempt_count: int,
    liveness_counts: Mapping[LivenessState, int],
) -> FamilyLivenessState:
    alive_count = sum(
        liveness_counts.get(state, 0)
        for state in (
            LivenessState.ALIVE_CONFORMANT,
            LivenessState.ALIVE_SCHEMA_DRIFT,
            LivenessState.ALIVE_SCHEMA_UNVERIFIED,
        )
    )
    if alive_count and alive_count == selected_probe_count:
        return FamilyLivenessState.LIVE_CHARACTERIZED
    if alive_count:
        return FamilyLivenessState.MIXED_LIVE_AND_FINDINGS
    if live_attempt_count == 0:
        return FamilyLivenessState.NO_SAFE_LIVE_ATTEMPT
    if (
        live_attempt_count == selected_probe_count
        and liveness_counts.get(LivenessState.DEAD, 0) == selected_probe_count
    ):
        return FamilyLivenessState.SAMPLE_DEAD_AFTER_HONEST_LEVERS
    return FamilyLivenessState.CHARACTERIZATION_FAILED


def _response_columns(raw_response: ProbeRawResponse, parser_mode: str) -> set[str] | None:
    if raw_response.bounded_body_base64 is None:
        return None
    body = base64.b64decode(raw_response.bounded_body_base64)
    if (
        "json" in parser_mode.lower()
        or "json" in raw_response.response_headers.get("content-type", "").lower()
    ):
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if isinstance(payload, Mapping):
            return {str(key) for key in payload}
        if isinstance(payload, Sequence) and payload and isinstance(payload[0], Mapping):
            return {str(key) for key in payload[0]}
        return set()
    if "csv" in parser_mode.lower():
        try:
            header = body.decode("utf-8").splitlines()[0]
        except (UnicodeDecodeError, IndexError):
            return None
        return {item.strip() for item in header.split(",") if item.strip()}
    return None


class _HeartbeatContentProxy:
    """Forward response chunks while emitting monotone progress heartbeats."""

    def __init__(
        self,
        content: Any,
        heartbeat: Callable[[str, int], Awaitable[None]],
    ) -> None:
        self._content = content
        self._heartbeat = heartbeat

    async def iter_chunked(self, chunk_size: int) -> Any:
        progress_bytes = 0
        async for chunk in self._content.iter_chunked(chunk_size):
            progress_bytes += len(chunk)
            await self._heartbeat("body_progress", progress_bytes)
            yield chunk


class _HeartbeatResponseProxy:
    """Minimal response proxy accepted by the shared bounded-body owner."""

    def __init__(
        self,
        response: Any,
        heartbeat: Callable[[str, int], Awaitable[None]],
    ) -> None:
        self.headers = response.headers
        self._response = response
        content = getattr(response, "content", None)
        self.content = (
            _HeartbeatContentProxy(content, heartbeat)
            if content is not None and hasattr(content, "iter_chunked")
            else None
        )
        self._heartbeat = heartbeat

    async def read(self) -> bytes:
        body = await self._response.read()
        if body:
            await self._heartbeat("body_progress", len(body))
        return body


async def _execute_live_probe(
    request: ProbeRequest,
    heartbeat: Callable[[str, int], Awaitable[None]],
) -> ProbeTransportResult:
    import aiohttp

    from polisyos.fabric.connectors.http_limits import read_bounded_response_body
    from polisyos.fabric.connectors.types import FetchError

    timeout = aiohttp.ClientTimeout(
        total=None,
        connect=request.budget.timeout_seconds,
        sock_connect=request.budget.timeout_seconds,
        sock_read=request.budget.timeout_seconds,
    )
    headers = {
        "Accept": "*/*",
        "Range": f"bytes=0-{request.budget.max_response_bytes - 1}",
        "User-Agent": "PolicyOS-GY-N13a-Reality-Census/1.0",
    }
    status_code: int | None = None
    response_headers: dict[str, str] = {}
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                request.endpoint_url,
                headers=headers,
                allow_redirects=False,
            ) as response,
        ):
            status_code = int(response.status)
            response_headers = _safe_response_headers(response.headers)
            await heartbeat("response_headers", 0)
            try:
                body = await read_bounded_response_body(
                    _HeartbeatResponseProxy(response, heartbeat),
                    connector_id=request.connector_id,
                    url=request.endpoint_url,
                    max_response_bytes=request.budget.max_response_bytes,
                    max_decompressed_bytes=request.budget.max_response_bytes,
                )
            except FetchError as exc:
                message = str(exc).lower()
                error_code = (
                    "response_budget_exceeded"
                    if "exceeds safe limit" in message or "decoded http body" in message
                    else "response_safety_blocked"
                    if "secret/pii" in message or "scan failed" in message
                    else "bounded_response_error"
                )
                return ProbeTransportResult(
                    status_code=status_code,
                    response_headers=response_headers,
                    bounded_body_base64=None,
                    body_sha256=None,
                    bytes_read=0,
                    transport_error_code=error_code,
                )
    except (aiohttp.ClientError, TimeoutError) as exc:
        return ProbeTransportResult(
            status_code=status_code,
            response_headers=response_headers,
            bounded_body_base64=None,
            body_sha256=None,
            bytes_read=0,
            transport_error_code=f"transport_{type(exc).__name__.lower()}",
        )
    return ProbeTransportResult(
        status_code=status_code,
        response_headers=response_headers,
        bounded_body_base64=base64.b64encode(body).decode("ascii"),
        body_sha256=f"sha256:{hashlib.sha256(body).hexdigest()}",
        bytes_read=len(body),
        transport_error_code=None,
    )


def _safe_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    exact = {"content-type", "content-length", "etag", "last-modified", "retry-after"}
    safe: dict[str, str] = {}
    for key, value in headers.items():
        normalized = key.lower()
        if normalized in exact or normalized.startswith("x-ratelimit-"):
            safe[normalized] = str(value)
    return dict(sorted(safe.items()))


def _append_fsync_jsonl(path: Path, event: Mapping[str, Any]) -> None:
    payload = canonical_json_bytes(event)
    with path.open("ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


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
    items: Sequence[Mapping[str, Any]],
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


def _bytes_sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


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


def _without_run_economics(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_run_economics(item)
            for key, item in value.items()
            if key not in CONTENT_HASH_EXCLUDED_FIELDS
        }
    if isinstance(value, list):
        return [_without_run_economics(item) for item in value]
    return value


def _validate_nonnegative_count_map(
    value: dict[Any, int],
) -> dict[Any, int]:
    negative_keys = sorted(str(key) for key, count in value.items() if count < 0)
    if negative_keys:
        raise ValueError(f"count map has negative values for: {', '.join(negative_keys)}")
    return value
