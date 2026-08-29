"""Strict contracts for the read-only DS15 acquisition-growth projection."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GapClass(StrEnum):
    """Classify a route only from reconciled owner evidence."""

    DATA_GAP = "data_gap"
    STRUCTURAL_GAP = "structural_gap"
    NOT_ESTABLISHED = "not_established"


class AcquisitionGrowthSummary(_StrictModel):
    """Complete N13a denominators projected without relabeling."""

    family_scorecard_count: int = Field(ge=0)
    actual_network_call_count: int = Field(ge=0)
    selected_record_count: int = Field(ge=0)
    metric_resolution_count: int = Field(ge=0)
    backlog_count: int = Field(ge=0)
    structural_route_count: int = Field(ge=0)


class AcquisitionBacklogProjection(_StrictModel):
    """One ranking-only residual with independently reconciled gap shape."""

    variable_id: str
    rank: int
    binding_confidence: float
    ranking_score: float
    route_demand: float
    ranking_method: str
    authority_boundary: str
    voi_owner_fit: str
    voi_owner_integration: str
    voi_owner_ref: str
    gap_class: GapClass
    classification_basis: Literal["independently_reconciled", "not_established"]


class StructuralRouteProjection(_StrictModel):
    """One capstone structural route with no data-acquisition action."""

    route_id: str
    route_class: str
    witness_kind: str
    missing_link: str
    gap_class: GapClass
    action_eligibility: Literal["not_applicable", "blocked"]


class EpochQualificationDisclosure(_StrictModel):
    """Fail-closed production qualification for the historical pending epoch."""

    epoch_state: Literal["pending_epoch_activation"]
    status: Literal["not_established"]
    code: Literal["policy_admission_missing"]
    authority_role: Literal["semantic epoch policy-admission qualifier"]
    authority_owner_ref: None = None
    appointment_state: Literal["unappointed"]
    appointment_would_establish: str
    appointment_would_not_establish: tuple[str, ...]

    @model_validator(mode="after")
    def _appointment_effect_is_exact(self) -> Self:
        if self.appointment_would_establish != (
            "authority to qualify native semantic production, append its history head "
            "and permit overlay activation"
        ):
            raise ValueError("qualification_appointment_effect_mismatch")
        if self.appointment_would_not_establish != (
            "gap shape",
            "passport validity",
            "positive delta",
            "re-entry",
        ):
            raise ValueError("qualification_appointment_non_effect_mismatch")
        return self


class N13bHistoryProjection(_StrictModel):
    """Historical execution facts that cannot authorize a current action."""

    attempt_count: int = Field(ge=0)
    raw_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    terminal_count: int = Field(ge=0)
    quarantine_count: int = Field(ge=0)
    overlay_epoch_count: int = Field(ge=0)
    execution_phase: Literal["executing", "terminal"]
    admission: Literal["not_reached", "not_established"]
    quarantine: Literal["none", "raw_terminal"]
    world_growth: Literal["not_established", "no_growth"]
    reentry: Literal["not_established", "deeper_terminal"]
    epoch_qualification: EpochQualificationDisclosure


class AcquisitionGrowthPayload(_StrictModel):
    """Strict composite read packet for acquisition growth and non-growth truth."""

    schema_version: Literal["policyos.runtime.acquisition_growth_projection.v1"] = (
        "policyos.runtime.acquisition_growth_projection.v1"
    )
    summary: AcquisitionGrowthSummary
    backlog: tuple[AcquisitionBacklogProjection, ...]
    structural_routes: tuple[StructuralRouteProjection, ...]
    carrier_liveness: dict[str, object]
    n13b_history: N13bHistoryProjection


__all__ = [
    "AcquisitionBacklogProjection",
    "AcquisitionGrowthPayload",
    "AcquisitionGrowthSummary",
    "EpochQualificationDisclosure",
    "GapClass",
    "N13bHistoryProjection",
    "StructuralRouteProjection",
]
