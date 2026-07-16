"""Typed evidence and read-only catalog primitives for the GY-N13a census.

This module owns the census boundary schema and the smallest read path needed to
identify the acquisition catalog.  It does not execute fetch plans, call connectors,
or write to the catalog.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "policyos.policy_design_case.gy_n13a.acquisition_census.v1"
RULE_VERSION = "policyos.layer3.gy.n13a.acquisition_census.v1"
CONTENT_HASH_EXCLUDED_FIELDS = frozenset(
    {"capture_wall_time_seconds", "observed_at"}
)
EXECUTABLE_BINDING_TIERS = frozenset({"fetchable", "transport_ready"})

_REQUIRED_CATALOG_COLUMNS: dict[str, frozenset[str]] = {
    "ds_datasets": frozenset(
        {"id", "access_license", "access_auth_required", "execution_tier"}
    ),
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
    "ds_observations": frozenset(
        {"observation_id", "dataset_id", "raw_variable", "canonical_var"}
    ),
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
        if self.binding_count == 0 and (
            self.connector_ids or self.best_binding_confidence != 0.0
        ):
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


class RouteEvidence(_StrictBoundaryModel):
    """Measured inputs and derived class for one actual N10 route."""

    route_id: str = Field(min_length=1)
    demanded_metrics: tuple[str, ...] = Field(min_length=1)
    local_observation_count: int = Field(ge=0)
    binding_tier_counts: dict[str, int]
    alignment_count: int = Field(ge=0)
    planner_gap_kind: str = Field(min_length=1)
    planner_strategy_kind: str = Field(min_length=1)
    blocker_codes: tuple[str, ...]
    missing_link: str = Field(min_length=1)
    route_class: RouteClass

    @field_validator("binding_tier_counts")
    @classmethod
    def _counts_must_be_nonnegative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_nonnegative_count_map(value)


class FetchPlanProjection(_StrictBoundaryModel):
    """Narrow proof projected from a real owner-generated FetchPlan."""

    metric_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    filters: dict[str, Any]
    owner_type: str = Field(min_length=1)


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
    fetch_plan_proofs: tuple[FetchPlanProjection, ...]
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
                connection.execute(
                    "SELECT COUNT(*) FROM query_table(?)", [table]
                ).fetchone()[0]
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
                proxy_only=bool(candidates) and all(
                    candidate.is_proxy for candidate in candidates
                ),
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
        _projection_binding(
            "capstone_cycle_demands", capstone_source, capstone_items
        ),
        _projection_binding(
            "intervention_substrate_world_slots",
            intervention_substrate_source,
            substrate_items,
        ),
        _projection_binding(
            "value_gate_target_requirements", value_gate_source, value_gate_items
        ),
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
    observation_counts = {
        str(variable_id): int(count) for variable_id, count in observation_rows
    }
    alignment_counts = {
        str(variable_id): int(count) for variable_id, count in alignment_rows
    }

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


def _extract_capstone_demand_items(
    capstone: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    runs = _required_mapping(capstone, "domain_runs", "capstone.domain_runs")
    if not runs:
        raise CatalogContractError(
            "demand_projection_empty", "capstone.domain_runs is empty"
        )
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
                    "variable_id": _required_text(
                        objective, "metric_id", field_path
                    ),
                }
            )

        lever_space_path = f"{problem_path}.candidate_lever_space"
        lever_space = _required_mapping(
            problem, "candidate_lever_space", lever_space_path
        )
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
        raise CatalogContractError(
            "demand_projection_empty", f"{proofs_path} is empty"
        )
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
                    "variable_id": _required_text(
                        node, "target_variable", field_path
                    ),
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


def _required_mapping(
    owner: Mapping[str, Any], key: str, path: str
) -> Mapping[str, Any]:
    if key not in owner:
        raise CatalogContractError(
            "demand_projection_missing_field", f"missing {path}"
        )
    return _as_mapping(owner[key], path)


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalogContractError(
            "demand_projection_invalid_field", f"{path} must be an object"
        )
    return value


def _required_sequence(
    owner: Mapping[str, Any], key: str, path: str
) -> Sequence[Any]:
    if key not in owner:
        raise CatalogContractError(
            "demand_projection_missing_field", f"missing {path}"
        )
    value = owner[key]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CatalogContractError(
            "demand_projection_invalid_field", f"{path} must be an array"
        )
    return value


def _required_text(owner: Mapping[str, Any], key: str, path: str) -> str:
    if key not in owner:
        raise CatalogContractError(
            "demand_projection_missing_field", f"missing {path}"
        )
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
        raise CatalogContractError(
            "demand_projection_owner_unreadable", f"{owner}: {exc}"
        ) from exc
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
        raise CatalogContractError(
            "catalog_schema_missing_tables", ", ".join(missing_tables)
        )

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
            f"{table}.{column}"
            for column in sorted(required_columns - actual_columns)
        )
    if missing_columns:
        raise CatalogContractError(
            "catalog_schema_missing_columns", ", ".join(missing_columns)
        )


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
        return {
            key: item
            for key, item in value.items()
            if key not in CONTENT_HASH_EXCLUDED_FIELDS
        }
    return value


def _validate_nonnegative_count_map(
    value: dict[Any, int],
) -> dict[Any, int]:
    negative_keys = sorted(str(key) for key, count in value.items() if count < 0)
    if negative_keys:
        raise ValueError(f"count map has negative values for: {', '.join(negative_keys)}")
    return value
