"""Persist calibration reports and expose the optimizer result schema.

These models describe the fitted parameter values and diagnostics produced by
`Calibrator.run()`. They intentionally separate synthetic-series comparisons,
fit quality, and uncertainty/identifiability metadata so governance passes can
inspect calibration quality without rerunning simulation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, InputRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.foundry.calibration.identifiability import IdentifiabilityReport
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


class CalibrationSeriesComparison(BaseModel):
    """Store one observed-vs-simulated time series pair for report rendering."""

    model_config = ConfigDict(extra="forbid")

    time: list[float] | None = None
    real: list[float] = Field(default_factory=list)
    model: list[float] = Field(default_factory=list)


class CalibrationFitMetrics(BaseModel):
    """Summarize residual fit quality for one target or an aggregate bundle."""

    model_config = ConfigDict(extra="forbid")

    mse: float
    rmse: float
    mae: float
    r2: float | None = None
    n: int | None = None


class CalibrationFitQuality(BaseModel):
    """Group per-target and aggregate fit metrics in one report section."""

    model_config = ConfigDict(extra="forbid")

    per_target: Mapping[str, CalibrationFitMetrics] = Field(default_factory=dict)
    aggregate: CalibrationFitMetrics | None = None


class CalibrationUncertainty(BaseModel):
    """Capture Hessian/Laplace uncertainty diagnostics for fitted parameters."""

    model_config = ConfigDict(extra="forbid")

    method: str = "laplace"
    params: list[str] = Field(default_factory=list)
    covariance: list[list[float]] = Field(default_factory=list)
    correlation: list[list[float]] = Field(default_factory=list)
    std: list[float] = Field(default_factory=list)
    damping: float = 0.0
    hessian_rank: int | None = None
    hessian_condition: float | None = None
    non_identifiable: list[str] = Field(default_factory=list)


class CalibrationCoordinateProjection(BaseModel):
    """Map ordered Hessian coordinates to concrete calibrated fields.

    ``matrix`` has one row per output field and one column per optimizer
    coordinate. It is persisted with the report so consumers can preserve
    shared-coordinate covariance without inferring ties from names.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_order: tuple[str, ...] = Field(min_length=1)
    coordinate_order: tuple[str, ...] = Field(min_length=1)
    matrix: tuple[tuple[float, ...], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_projection(self) -> CalibrationCoordinateProjection:
        if any(not name.strip() for name in (*self.field_order, *self.coordinate_order)):
            raise ValueError("projection names must be non-empty")
        if len(set(self.field_order)) != len(self.field_order):
            raise ValueError("field_order must contain unique field names")
        if len(set(self.coordinate_order)) != len(self.coordinate_order):
            raise ValueError("coordinate_order must contain unique coordinate names")
        if len(self.matrix) != len(self.field_order):
            raise ValueError("projection row count must match field_order")
        if any(len(row) != len(self.coordinate_order) for row in self.matrix):
            raise ValueError("projection column count must match coordinate_order")
        if any(not math.isfinite(value) for row in self.matrix for value in row):
            raise ValueError("projection matrix must contain finite values")
        return self


class CalibrationReport(BaseModel):
    """Persist calibrated parameters, trace comparisons, and diagnostics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    calibrated_params: Mapping[str, float] = Field(
        default_factory=dict,
        description="Flat parameter map keyed as `node_id.param`.",
    )
    total_loss: float
    per_target_loss: Mapping[str, float] = Field(default_factory=dict)
    target_weights: Mapping[str, float] = Field(default_factory=dict)
    loss_history: list[float] = Field(default_factory=list)
    grad_norm_history: list[float] = Field(default_factory=list)
    series_comparison: Mapping[str, CalibrationSeriesComparison] = Field(default_factory=dict)
    fit_quality: CalibrationFitQuality | None = None
    uncertainties: CalibrationUncertainty | None = None
    coordinate_projection: CalibrationCoordinateProjection | None = Field(
        default=None,
        description="Versioned map from Hessian optimizer coordinates to calibrated fields.",
    )
    coordinate_projection_status: Literal[
        "complete", "incomplete", "unsupported", "not_established"
    ] | None = Field(
        default=None,
        description=(
            "Whether the v2 optimizer-to-field map covers every reported calibrated field. "
            "Incomplete or unsupported maps are withheld from consumers."
        ),
    )
    identifiability: IdentifiabilityReport | None = Field(
        default=None,
        description="Per-parameter identifiability diagnostics from Hessian eigenstructure.",
    )
    uncertainty_envelopes: Mapping[str, UncertaintyEnvelope] | None = Field(
        default=None,
        description="Per-parameter uncertainty envelopes derived from calibration Hessian output.",
    )
    uncertainty_envelope_refs: Mapping[str, UncertaintyEnvelopeRef] | None = Field(
        default=None,
        description="Optional CAS references for persisted per-parameter uncertainty envelopes.",
    )
    diagnostics: list[str] = Field(default_factory=list)
    execution_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime settings used during calibration, such as fidelity and temperature.",
    )

    @model_validator(mode="after")
    def validate_coordinate_projection_contract(self) -> CalibrationReport:
        if self.schema_version == "1.0":
            return self

        projection = self.coordinate_projection
        status = self.coordinate_projection_status
        if projection is None:
            if status == "complete":
                raise ValueError("complete coordinate projection status requires a projection")
            if status is None:
                object.__setattr__(self, "coordinate_projection_status", "not_established")
            return self

        if status not in (None, "complete"):
            raise ValueError("only a complete coordinate projection may be persisted")
        if set(projection.field_order) != set(self.calibrated_params):
            raise ValueError("coordinate projection must cover every calibrated parameter field")
        if (
            self.uncertainties is not None
            and tuple(self.uncertainties.params) != projection.coordinate_order
        ):
            raise ValueError("coordinate projection must match ordered Hessian coordinates")
        object.__setattr__(self, "coordinate_projection_status", "complete")
        return self


def serialize_calibration_report_v1(report: CalibrationReport) -> bytes:
    """Serialize the historical v1 wire projection without v2-only fields.

    This preserves byte-exact replay of v1 report hashes after the current
    report schema gained ``coordinate_projection``.
    """
    payload = report.model_dump(
        mode="json",
        exclude={"coordinate_projection", "coordinate_projection_status"},
    )
    payload["schema_version"] = "1.0"
    return to_canonical_bytes(payload, CanonSpec(forbid_floats=False))


def put_calibration_config(
    store: ArtifactStore,
    config: CalibrationConfig,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a `CalibrationConfig` artifact with caller-supplied provenance edges."""
    return store.put_json(
        config,
        PutOptions(
            kind="foundry.calibration_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.CalibrationConfig", version=config.schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def put_calibration_report(
    store: ArtifactStore,
    report: CalibrationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a `CalibrationReport` artifact for downstream governance/replay."""
    if report.schema_version != "1.0" and not any(
        input_ref.role == "calibration_config" for input_ref in inputs or ()
    ):
        raise ValueError("versioned calibration reports require their calibration_config input")
    # V2 carries typed nulls, including `confidence_level=None` for heuristic
    # intervals. The default canonical profile omits nulls, which would make
    # the IR model's 0.95 default reappear on replay and contradict that
    # interval semantics. Keep the historical v1 profile byte-exact below.
    canon_spec = CanonSpec(
        forbid_floats=False,
        exclude_none=report.schema_version == "1.0",
    )
    options = PutOptions(
        kind="foundry.calibration_report",
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.foundry.CalibrationReport", version=report.schema_version
        ),
        inputs=inputs,
        canon=CanonInfo.from_spec(canon_spec),
    )
    if report.schema_version == "1.0":
        return store.put_bytes(serialize_calibration_report_v1(report), options)
    return store.put_json(
        report,
        options,
        canon_spec=canon_spec,
    )
