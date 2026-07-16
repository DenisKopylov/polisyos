"""Typed evidence and read-only catalog primitives for the GY-N13a census.

This module owns the census boundary schema and the smallest read path needed to
identify the acquisition catalog.  It does not execute fetch plans, call connectors,
or write to the catalog.
"""

from __future__ import annotations

import hashlib
import json
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

    canonical_variable: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    is_proxy: bool
    proxy_penalty: float = Field(ge=0.0, le=1.0)
    method: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class MetricResolution(_StrictBoundaryModel):
    """Recomputed resolution row for one full-denominator catalog metric."""

    metric_id: str = Field(min_length=1)
    resolution_status: ResolutionStatus
    binding_count: int = Field(ge=1)
    exact_canonical_variable: str | None = None
    best_alignment: AlignmentCandidate | None = None
    alignment_candidates: tuple[AlignmentCandidate, ...] = ()
    alignment_ambiguous: bool = False

    @model_validator(mode="after")
    def _status_must_match_evidence(self) -> Self:
        if self.resolution_status is ResolutionStatus.EXACT:
            if not self.exact_canonical_variable:
                raise ValueError("exact resolution requires exact_canonical_variable")
            if self.best_alignment is not None or self.alignment_candidates:
                raise ValueError("exact resolution cannot carry alignment evidence")
            if self.alignment_ambiguous:
                raise ValueError("exact resolution cannot be alignment_ambiguous")
        elif self.resolution_status is ResolutionStatus.VIA_ALIGNMENT:
            if self.exact_canonical_variable is not None:
                raise ValueError("aligned resolution cannot carry an exact variable")
            if self.best_alignment is None or not self.alignment_candidates:
                raise ValueError("aligned resolution requires best and candidate alignments")
            if self.best_alignment not in self.alignment_candidates:
                raise ValueError("best alignment must be one of the alignment candidates")
        elif any(
            (
                self.exact_canonical_variable is not None,
                self.best_alignment is not None,
                bool(self.alignment_candidates),
                self.alignment_ambiguous,
            )
        ):
            raise ValueError("unresolved metric cannot carry resolution evidence")
        return self


class ReverseDemandResidual(_StrictBoundaryModel):
    """Cycle-relevant variable with no executable catalog support."""

    variable_id: str = Field(min_length=1)
    gap_kind: DemandGapKind
    demand_sources: tuple[str, ...] = Field(min_length=1)
    local_observation_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    executable_binding_count: int = Field(ge=0)
    best_binding_confidence: float = Field(ge=0.0, le=1.0)


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


class CensusManifest(_StrictBoundaryModel):
    """Frozen semantic payload for one acquisition-layer reality census."""

    schema_version: Literal[SCHEMA_VERSION]
    rule_version: Literal[RULE_VERSION]
    producer: str = Field(min_length=1)
    catalog_identity: CatalogIdentity
    projection_bindings: tuple[ProjectionBinding, ...]
    metric_resolutions: tuple[MetricResolution, ...]
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
