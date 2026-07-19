"""Recomputing owner for the GY-N13b demanding-stage re-entry trace."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.fabric.data_plane import content_sha256
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlannerReport,
    AcquisitionRequirementGap,
)
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from tools.quality.validation.layer3_gy_acquisition_executor import (
    D6RouteSelection,
    MetadataProbeExecutionEvidence,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    AcceptanceCaseReceipt,
)

ReentryDisposition = Literal[
    "gap_closed_by_acquisition",
    "deeper_terminal_primary_carrier_characterization_failed",
    "deeper_terminal_catalog_binding_absent",
]
DEFAULT_N13B_REENTRY_TRACE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json"
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class N7CatalogResolutionProjection(_StrictModel):
    """Narrow result of the real DatasetCatalogGraph/RetrievalService path."""

    target_variable: str = Field(min_length=1)
    mode: Literal["hybrid"]
    fetch_plan_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    warnings: tuple[str, ...]
    fetch_plan_execution_count: Literal[0]

    @model_validator(mode="after")
    def _zero_plan_terminal_is_explicit(self) -> Self:
        if self.fetch_plan_count == 0 and "no_fetch_plans_resolved" not in self.warnings:
            raise ValueError("zero-plan catalog resolution requires its owner warning")
        return self


class OverlayStateProjection(_StrictModel):
    """Durable observation-overlay state seen by the runtime union path."""

    overlay_ref: str = Field(min_length=1)
    exists: bool
    content_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    epoch_count: int = Field(ge=0)
    registration_count: int = Field(ge=0)
    admitted_observation_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _absent_overlay_cannot_claim_rows(self) -> Self:
        if not self.exists and (
            self.content_sha256 is not None
            or self.epoch_count
            or self.registration_count
            or self.admitted_observation_count
        ):
            raise ValueError("absent overlay cannot claim durable world growth")
        if self.exists and self.content_sha256 is None:
            raise ValueError("existing overlay requires a content identity")
        return self


class N13bReentryTrace(_StrictModel):
    """Frozen re-entry result for the selected D2 backlog requirement."""

    schema_version: Literal["policyos.layer3.gy.n13b.reentry_trace.v1"] = (
        "policyos.layer3.gy.n13b.reentry_trace.v1"
    )
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    demanding_stage: Literal["intervention_substrate.measured_coverage.world_slot"]
    target_variable: str = Field(min_length=1)
    substrate_slot_projection: dict[str, Any]
    substrate_slot_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    d6_route_selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    primary_metadata_evidence_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    primary_terminal_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    primary_terminal_failure_code: str = Field(min_length=1)
    primary_response_admitted: bool
    acceptance_case_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    availability_before: L1VariableAvailability
    availability_after: L1VariableAvailability
    availability_count_before: int = Field(ge=0)
    availability_count_after: int = Field(ge=0)
    availability_count_delta: int
    requirement_gap: AcquisitionRequirementGap
    planner_report_projection: dict[str, Any]
    planner_report_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_resolution: N7CatalogResolutionProjection
    overlay_state: OverlayStateProjection
    world_growth_event_count: int = Field(ge=0, le=1)
    world_growth_status: Literal["grew", "no_growth"]
    reentry_disposition: ReentryDisposition
    reentry_network_call_count: Literal[0]
    remaining_resumption_call_budget: Literal[3]
    trace_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _trace_is_recomputed(self) -> Self:
        if self.target_variable != self.availability_before.variable_id or (
            self.target_variable != self.availability_after.variable_id
        ):
            raise ValueError("reentry target and availability owner differ")
        expected_slot_sha = content_sha256(self.substrate_slot_projection)
        if self.substrate_slot_projection_sha256 != expected_slot_sha:
            raise ValueError("reentry substrate slot projection drift")
        before = _availability_count(self.availability_before)
        after = _availability_count(self.availability_after)
        if (
            self.availability_count_before != before
            or self.availability_count_after != after
            or self.availability_count_delta != after - before
        ):
            raise ValueError("reentry availability delta must be recomputed")
        metadata = self.requirement_gap.metadata
        availability = metadata.get("availability")
        if (
            metadata.get("source") != "l1_dcat_variable_availability"
            or not isinstance(availability, dict)
            or availability.get("variable_id") != self.target_variable
            or availability.get("status") != self.availability_after.status
        ):
            raise ValueError("reentry requirement gap must come from the availability owner")
        if self.planner_report_projection_sha256 != content_sha256(self.planner_report_projection):
            raise ValueError("reentry N7 planner projection drift")
        planner = AcquisitionPlannerReport.model_validate(
            {
                **self.planner_report_projection,
                "generated_at": datetime(2000, 1, 1, tzinfo=UTC),
            }
        )
        if len(planner.acquisition_records) != 1 or (
            planner.acquisition_records[0].requirement_gap_ref
            != self.requirement_gap.requirement_gap_id
        ):
            raise ValueError("reentry N7 planner did not preserve the exact requirement")
        expected_disposition = derive_reentry_disposition(
            availability_before=self.availability_before,
            availability_after=self.availability_after,
            route_disposition="derivation_requirement",
            primary_response_admitted=self.primary_response_admitted,
            primary_terminal_failure_code=self.primary_terminal_failure_code,
        )
        if self.reentry_disposition != expected_disposition:
            raise ValueError("reentry disposition must derive from paid owner evidence")
        expected_growth = int(expected_disposition == "gap_closed_by_acquisition")
        if self.world_growth_event_count != expected_growth or self.world_growth_status != (
            "grew" if expected_growth else "no_growth"
        ):
            raise ValueError("world-growth receipt must derive from the availability delta")
        if expected_growth and self.overlay_state.admitted_observation_count == 0:
            raise ValueError("world growth requires admitted overlay observations")
        if not expected_growth and self.overlay_state.admitted_observation_count != 0:
            raise ValueError("no-growth trace cannot hide admitted overlay observations")
        if self.trace_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("reentry trace identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the timestamp-free re-entry evidence without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "trace_sha256"
        }


def derive_reentry_disposition(
    *,
    availability_before: L1VariableAvailability,
    availability_after: L1VariableAvailability,
    route_disposition: str,
    primary_response_admitted: bool,
    primary_terminal_failure_code: str | None,
) -> ReentryDisposition:
    """Classify the real availability delta without inflating world growth."""

    before = L1VariableAvailability.model_validate(availability_before.model_dump(mode="python"))
    after = L1VariableAvailability.model_validate(availability_after.model_dump(mode="python"))
    if before.variable_id != after.variable_id:
        raise ValueError("reentry_availability_variable_drift")
    if after.status == "available" and (
        after.dataset_count > before.dataset_count
        or after.metric_binding_count > before.metric_binding_count
        or after.observation_count > before.observation_count
    ):
        return "gap_closed_by_acquisition"
    if (
        route_disposition == "derivation_requirement"
        and not primary_response_admitted
        and primary_terminal_failure_code
    ):
        return "deeper_terminal_primary_carrier_characterization_failed"
    return "deeper_terminal_catalog_binding_absent"


def build_reentry_trace(
    *,
    baseline_sha256: str,
    substrate_slot_projection: dict[str, Any],
    d6_route: D6RouteSelection,
    primary_metadata_evidence: MetadataProbeExecutionEvidence,
    acceptance_case: AcceptanceCaseReceipt,
    availability_before: L1VariableAvailability,
    availability_after: L1VariableAvailability,
    requirement_gap: AcquisitionRequirementGap,
    planner_report: AcquisitionPlannerReport,
    catalog_resolution: N7CatalogResolutionProjection,
    overlay_state: OverlayStateProjection,
) -> N13bReentryTrace:
    """Bind owner evidence into one recomputing, timestamp-free re-entry trace."""

    route = D6RouteSelection.model_validate(d6_route.model_dump(mode="python"))
    primary = MetadataProbeExecutionEvidence.model_validate(
        primary_metadata_evidence.model_dump(mode="python")
    )
    acceptance = AcceptanceCaseReceipt.model_validate(acceptance_case.model_dump(mode="python"))
    before = L1VariableAvailability.model_validate(availability_before.model_dump(mode="python"))
    after = L1VariableAvailability.model_validate(availability_after.model_dump(mode="python"))
    gap = AcquisitionRequirementGap.model_validate(requirement_gap.model_dump(mode="python"))
    planner = AcquisitionPlannerReport.model_validate(planner_report.model_dump(mode="python"))
    catalog = N7CatalogResolutionProjection.model_validate(
        catalog_resolution.model_dump(mode="python")
    )
    overlay = OverlayStateProjection.model_validate(overlay_state.model_dump(mode="python"))
    if baseline_sha256 != route.baseline_sha256 or (
        primary.baseline_after_sha256 != baseline_sha256
    ):
        raise ValueError("reentry baseline owner drift")
    if route.target_variable != before.variable_id or route.target_variable != after.variable_id:
        raise ValueError("reentry D6 target drift")
    if route.substrate_slot_projection_sha256 != content_sha256(substrate_slot_projection):
        raise ValueError("reentry demanded slot projection drift")
    if catalog.target_variable != route.target_variable:
        raise ValueError("reentry catalog target drift")
    planner_projection = planner.model_dump(mode="json")
    planner_projection.pop("generated_at", None)
    disposition = derive_reentry_disposition(
        availability_before=before,
        availability_after=after,
        route_disposition=route.route_disposition,
        primary_response_admitted=primary.response_admitted,
        primary_terminal_failure_code=primary.terminal.failure_code,
    )
    before_count = _availability_count(before)
    after_count = _availability_count(after)
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.reentry_trace.v1",
        "baseline_sha256": baseline_sha256,
        "demanding_stage": "intervention_substrate.measured_coverage.world_slot",
        "target_variable": route.target_variable,
        "substrate_slot_projection": substrate_slot_projection,
        "substrate_slot_projection_sha256": content_sha256(substrate_slot_projection),
        "d6_route_selection_sha256": route.selection_sha256,
        "primary_metadata_evidence_sha256": primary.evidence_sha256,
        "primary_terminal_sha256": primary.terminal.terminal_sha256,
        "primary_terminal_failure_code": primary.terminal.failure_code,
        "primary_response_admitted": primary.response_admitted,
        "acceptance_case_receipt_sha256": acceptance.receipt_sha256,
        "availability_before": before,
        "availability_after": after,
        "availability_count_before": before_count,
        "availability_count_after": after_count,
        "availability_count_delta": after_count - before_count,
        "requirement_gap": gap,
        "planner_report_projection": planner_projection,
        "planner_report_projection_sha256": content_sha256(planner_projection),
        "catalog_resolution": catalog,
        "overlay_state": overlay,
        "world_growth_event_count": int(disposition == "gap_closed_by_acquisition"),
        "world_growth_status": (
            "grew" if disposition == "gap_closed_by_acquisition" else "no_growth"
        ),
        "reentry_disposition": disposition,
        "reentry_network_call_count": 0,
        "remaining_resumption_call_budget": 3,
    }
    return N13bReentryTrace(
        **values,
        trace_sha256=content_sha256(_json_values(values)),
    )


def _availability_count(value: L1VariableAvailability) -> int:
    return value.dataset_count + value.metric_binding_count + value.observation_count


def _json_values(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_values(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_values(item) for item in value]
    return value


__all__ = [
    "DEFAULT_N13B_REENTRY_TRACE",
    "N7CatalogResolutionProjection",
    "N13bReentryTrace",
    "OverlayStateProjection",
    "ReentryDisposition",
    "build_reentry_trace",
    "derive_reentry_disposition",
]
