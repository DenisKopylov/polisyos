"""Strict HTTP contracts for the composed Cycle Board projection."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves the fact clocks
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.http.services.adapters import RunTerminality
from polisyos.runtime.http.services.governed_projections import (
    AudienceClass,
    DepthNAcquisitionRouteReference,
    GovernedProjectionPacket,
    ProjectionFreshness,
    ProjectionId,
    SurfaceReadinessPayload,
)
from polisyos.runtime.quality.design_problem import DesignProblem

CYCLE_BOARD_PACKET_SCHEMA_VERSION = "policyos.runtime.cycle_board_packet.v1"
CYCLE_BOARD_PROJECTION_RULE_VERSION = "policyos.runtime.depth_n_cycle_board.v2"
CYCLE_BOARD_STABLE_ADDRESS = "/api/v1/exports/governed-projections/depth-n-cycle-board"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AvailableFact[T](_StrictModel):
    """A producer-backed board value with its own source time."""

    availability: Literal["available"] = "available"
    value: T
    source_ref: str
    source_as_of: datetime | None = None


class AbsentFact(_StrictModel):
    """A typed absence whose shape cannot carry a defaulted value."""

    availability: Literal["not_established", "artifact_missing", "invalid_source"]
    reason: str
    owner_route: str


StringFact = Annotated[
    AvailableFact[str] | AbsentFact,
    Field(discriminator="availability"),
]
FloatFact = Annotated[
    AvailableFact[float] | AbsentFact,
    Field(discriminator="availability"),
]
IntegerFact = Annotated[
    AvailableFact[int] | AbsentFact,
    Field(discriminator="availability"),
]
StringTupleFact = Annotated[
    AvailableFact[tuple[str, ...]] | AbsentFact,
    Field(discriminator="availability"),
]
DesignProblemFact = Annotated[
    AvailableFact[DesignProblem] | AbsentFact,
    Field(discriminator="availability"),
]
LifecycleFact = Annotated[
    AvailableFact[RunTerminality] | AbsentFact,
    Field(discriminator="availability"),
]
ReadinessFact = Annotated[
    AvailableFact[SurfaceReadinessPayload] | AbsentFact,
    Field(discriminator="availability"),
]


class CycleBoardAcquisitionEconomics(_StrictModel):
    """Hash-resolved N7 planner contents, distinct from the route reference."""

    planner_report_content_hash: str
    planner_status: str
    missing_requirement_fields: tuple[str, ...]
    recommended_strategy: str
    expected_cost: FloatFact
    expected_voi: FloatFact
    voi_rank: IntegerFact
    decision_owner_ref: str
    producer_expected: str
    next_action: str
    execution_status: StringFact


AcquisitionRouteFact = Annotated[
    AvailableFact[DepthNAcquisitionRouteReference] | AbsentFact,
    Field(discriminator="availability"),
]
AcquisitionEconomicsFact = Annotated[
    AvailableFact[CycleBoardAcquisitionEconomics] | AbsentFact,
    Field(discriminator="availability"),
]


class CycleBoardRow(_StrictModel):
    """One known capstone or fixture-only Cycle Board row."""

    row_id: str
    cohort: Literal["n10_capstone", "legacy_fixture"]
    domain_role: str
    generation_cycle_run_id: StringFact
    design_problem: DesignProblemFact
    search_terminal_kind: StringFact
    lifecycle_terminality: LifecycleFact
    structural_evidence_class: StringFact
    weakest_links: StringTupleFact
    missing_link: StringFact
    acquisition_route: AcquisitionRouteFact
    acquisition_economics: AcquisitionEconomicsFact
    responsible_slices: tuple[str, ...]
    stage_trace_href: StringFact
    surface_readiness: ReadinessFact
    explanation_code: str
    explanation_inputs: dict[str, str]
    movement_records: tuple[dict[str, Any], ...] = ()


class CycleBoardCoverageGap(_StrictModel):
    """Render the board's unclosed production enumeration capability."""

    capability_state: Literal["absent/unallocated"] = "absent/unallocated"
    deficits: tuple[Literal["artifact_missing", "bridge_missing"], ...] = (
        "artifact_missing",
        "bridge_missing",
    )
    missing_link: Literal["production_recursive_cycle_run_enumeration"] = (
        "production_recursive_cycle_run_enumeration"
    )
    owner_route: Literal["GY-GAP5 -> runtime/quality GY-N12"] = "GY-GAP5 -> runtime/quality GY-N12"
    execution_status: Literal["not_established"] = "not_established"
    known_scope: Literal["N10 capstone + legacy fixture cohort"] = (
        "N10 capstone + legacy fixture cohort"
    )
    unknown_scope: Literal["future production recursive-cycle DesignProblems"] = (
        "future production recursive-cycle DesignProblems"
    )
    known_row_count: int = Field(ge=0)
    exhaustive: Literal[False] = False


class CycleBoardMovementGap(_StrictModel):
    """Render the absent per-row N13b re-entry binding without simulated motion."""

    capability_state: Literal["absent/unallocated"] = "absent/unallocated"
    deficits: tuple[Literal["artifact_missing", "bridge_missing"], ...] = (
        "artifact_missing",
        "bridge_missing",
    )
    missing_link: Literal["acquisition_reentry_deeper_terminal_binding"] = (
        "acquisition_reentry_deeper_terminal_binding"
    )
    producer_route: Literal["GY-GAP6 -> GY-N13b"] = "GY-GAP6 -> GY-N13b"
    chronology_route: Literal["GY-N12"] = "GY-N12"
    execution_status: Literal["not_established"] = "not_established"
    movement_records: tuple[dict[str, Any], ...] = ()


class HistoricalDS4Disposition(_StrictModel):
    """Arithmetic derived from the complete historical DS4 owner table."""

    source_class: Literal["historical_ds4_component_disposition"] = (
        "historical_ds4_component_disposition"
    )
    source_ref: str
    source_content_hash: str
    counts: dict[Literal["package", "rebind", "use_as_is", "retire"], int]
    denominator: int = Field(ge=0)


class HistoricalProducerAvailability(_StrictModel):
    """Environment-relative DS3 measurement, never current producer authority."""

    source_ref: str
    source_content_hash: str
    counts: dict[
        Literal["available", "invalid_source", "artifact_missing"],
        int,
    ]
    measurement_scope: Literal["environment_relative"] = "environment_relative"
    environment_absence: Literal["production_data"] = "production_data"


class CycleBoardCompositionSource(_StrictModel):
    """One independently timed input in the outer composition manifest."""

    source_id: str
    source_kind: Literal[
        "governed_projection",
        "control_plane_evidence",
        "historical_owner_record",
        "run_summary_lookup",
        "run_paper_projection",
    ]
    source_ref: str | None = None
    availability: Literal[
        "available",
        "artifact_missing",
        "invalid_source",
        "not_established",
    ]
    artifact_content_hash: str | None = None
    source_dependency_hash: str | None = None
    as_of: datetime | None = None
    freshness: ProjectionFreshness | None = None
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    absence_reason: str | None = None


class DepthNCycleBoardPayloadV2(_StrictModel):
    """Reviewer/Expert Cycle Board facts without a fabricated aggregate clock."""

    rows: tuple[CycleBoardRow, ...]
    coverage: CycleBoardCoverageGap
    movement_gap: CycleBoardMovementGap
    realized_ds4_disposition: HistoricalDS4Disposition
    historical_producer_availability: HistoricalProducerAvailability


class CycleBoardProjectionPacket(_StrictModel):
    """Replay-addressed outer Cycle Board projection."""

    packet_schema_version: Literal["policyos.runtime.cycle_board_packet.v1"] = (
        CYCLE_BOARD_PACKET_SCHEMA_VERSION
    )
    projection_id: Literal[ProjectionId.DEPTH_N_CYCLE_BOARD] = ProjectionId.DEPTH_N_CYCLE_BOARD
    projection_rule_version: Literal["policyos.runtime.depth_n_cycle_board.v2"] = (
        CYCLE_BOARD_PROJECTION_RULE_VERSION
    )
    intended_audiences: tuple[
        Literal[AudienceClass.REVIEWER],
        Literal[AudienceClass.EXPERT],
    ] = (AudienceClass.REVIEWER, AudienceClass.EXPERT)
    composition_manifest: tuple[CycleBoardCompositionSource, ...]
    composition_manifest_hash: str
    source_dependency_hash: str
    projection_hash: str
    projection_observed_at: datetime
    stable_address: Literal["/api/v1/exports/governed-projections/depth-n-cycle-board"] = (
        CYCLE_BOARD_STABLE_ADDRESS
    )
    replay_address: str
    payload: DepthNCycleBoardPayloadV2


CycleBoardExportResponse = GovernedProjectionPacket | CycleBoardProjectionPacket


class CycleBoardReplayConflictError(ValueError):
    """Reject partial, stale, or cross-generation Cycle Board replay pins."""


__all__ = [
    "CYCLE_BOARD_PROJECTION_RULE_VERSION",
    "CYCLE_BOARD_STABLE_ADDRESS",
    "AbsentFact",
    "AvailableFact",
    "CycleBoardAcquisitionEconomics",
    "CycleBoardCompositionSource",
    "CycleBoardCoverageGap",
    "CycleBoardExportResponse",
    "CycleBoardMovementGap",
    "CycleBoardProjectionPacket",
    "CycleBoardReplayConflictError",
    "CycleBoardRow",
    "DepthNCycleBoardPayloadV2",
    "HistoricalDS4Disposition",
    "HistoricalProducerAvailability",
]
