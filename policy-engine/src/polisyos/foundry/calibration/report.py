"""Persist calibration reports and expose the optimizer result schema.

These models describe the fitted parameter values and diagnostics produced by
`Calibrator.run()`. They intentionally separate synthetic-series comparisons,
fit quality, and uncertainty/identifiability metadata so governance passes can
inspect calibration quality without rerunning simulation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from numpy.typing import ArrayLike
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactStore
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.foundry.calibration.identifiability import IdentifiabilityReport
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

if TYPE_CHECKING:
    from polisyos.foundry.calibration.execution_basis import CalibrationSourceRead


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


def ordered_batch_fit_metrics(
    model: ArrayLike,
    real: ArrayLike,
    weights: ArrayLike,
) -> CalibrationFitMetrics:
    """Compute the profile's metric-unit residual summaries over its actual weighted rows."""
    model_arr, real_arr = (np.asarray(value, dtype=np.float64) for value in (model, real))
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        weight_arr = np.asarray(weights, dtype=np.float32).astype(np.float64)
    if np.any((np.asarray(weights) > 0) & (weight_arr == 0)):
        raise ValueError("ordered metric weights underflow in the declared float32 profile")
    if (
        model_arr.ndim != 1
        or real_arr.shape != model_arr.shape
        or weight_arr.shape != model_arr.shape
    ):
        raise ValueError("ordered fit metric inputs require exact one-dimensional row shape")
    if not all(np.all(np.isfinite(value)) for value in (model_arr, real_arr, weight_arr)) or np.any(
        weight_arr < 0
    ):
        raise ValueError("ordered fit metric inputs require finite values and nonnegative weights")
    support = float(weight_arr.sum())
    if not 0 < support < math.inf:
        raise ValueError("ordered fit metrics require positive finite support")
    diff = model_arr - real_arr
    mse = float(np.sum(weight_arr * diff**2) / support)
    mae = float(np.sum(weight_arr * np.abs(diff)) / support)
    mean = float(np.sum(weight_arr * real_arr) / support)
    denom = float(np.sum(weight_arr * (real_arr - mean) ** 2))
    r2 = None if denom <= 0 else float(1 - np.sum(weight_arr * diff**2) / denom)
    return CalibrationFitMetrics(
        mse=mse,
        rmse=float(np.sqrt(mse)),
        mae=mae,
        r2=r2,
        n=int(np.count_nonzero(weight_arr > 0)),
    )


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


class CalibrationOrderedBatchReport(BaseModel):
    """Declare the batch objective scope without granting inferential authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_kind: Literal["ordered_scalar_mse_v1"] = "ordered_scalar_mse_v1"
    objective_kind: Literal["generic_weighted_mse_curvature_only"] = (
        "generic_weighted_mse_curvature_only"
    )
    inference_status: Literal["unavailable_generic_loss"] = "unavailable_generic_loss"
    consumed_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_input_ref: ArtifactRef | None = None
    input_status: Literal["selected_input_consumed", "in_memory_input_only"]

    @model_validator(mode="after")
    def validate_selected_input(self) -> CalibrationOrderedBatchReport:
        if (self.input_status == "selected_input_consumed") != (
            self.selected_input_ref is not None
        ):
            raise ValueError("ordered_report_input_status_must_match_selected_reference")
        if self.selected_input_ref is not None and (
            self.selected_input_ref.kind != "foundry.calibration_ordered_input"
            or self.selected_input_ref.media_type != "application/json"
        ):
            raise ValueError("ordered_report_requires_selected_full_input")
        return self


class CalibrationReport(BaseModel):
    """Persist calibrated parameters, trace comparisons, and diagnostics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "2.0", "2.1"] = "2.0"
    ordered_batch_execution: CalibrationOrderedBatchReport | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def validate_ordered_scope(self) -> CalibrationReport:
        if (self.schema_version == "2.1") != (self.ordered_batch_execution is not None):
            raise ValueError("report_v2_1_requires_typed_ordered_objective_scope")
        return self

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
    coordinate_projection_status: (
        Literal["complete", "incomplete", "unsupported", "not_established"] | None
    ) = Field(
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
    if report.schema_version not in {"1.0", "2.0"} or report.ordered_batch_execution is not None:
        raise ValueError("ordered_batch_report_cannot_be_projected_as_legacy_v1")
    payload = report.model_dump(
        mode="json",
        exclude={"coordinate_projection", "coordinate_projection_status"},
    )
    payload["schema_version"] = "1.0"
    return to_canonical_bytes(payload, CanonSpec(forbid_floats=False))


def read_calibration_config_source(
    store: ArtifactStore,
    *,
    ref: object | None = None,
    inputs: Sequence[InputRef] | None = None,
) -> CalibrationSourceRead[CalibrationConfig]:
    """Admit the config through its strict model and the producer's version relation."""
    from polisyos.foundry.calibration.execution_basis import (
        _decode_versioned_calibration_model,
        read_calibration_model_source,
    )

    return read_calibration_model_source(
        store,
        role="calibration_config",
        model=CalibrationConfig,
        ref=ref,
        inputs=inputs,
        expected_kind="foundry.calibration_config",
        expected_schema="polisyos.ir.CalibrationConfig",
        decoder=lambda _ref, manifest, value: _decode_versioned_calibration_model(
            CalibrationConfig, manifest, value
        ),
    )


def put_calibration_config(
    store: ArtifactStore,
    config: CalibrationConfig,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
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
        return_selected_profile=return_selected_profile,
    )


def put_calibration_report(
    store: ArtifactStore,
    report: CalibrationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a `CalibrationReport` artifact for downstream governance/replay."""
    if report.schema_version == "2.0" and not any(
        input_ref.role == "calibration_config" for input_ref in inputs or ()
    ):
        raise ValueError("versioned calibration reports require their calibration_config input")
    if report.schema_version not in {"1.0", "2.0"} or report.ordered_batch_execution is not None:
        report = CalibrationReport.model_validate(report.model_dump(mode="python"))
    if report.ordered_batch_execution is not None:
        from polisyos.foundry.calibration.execution_basis import (
            read_calibration_execution_input_basis_source,
            read_calibration_source,
            reconcile_ordered_batch_report_identity,
        )

        basis = read_calibration_execution_input_basis_source(
            store, inputs=inputs or ()
        ).require_value()
        read_calibration_config_source(
            store, ref=basis.calibration_config_ref, inputs=inputs or ()
        ).require_value()
        reconcile_ordered_batch_report_identity(basis, report)
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
        schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version=report.schema_version),
        inputs=inputs,
        canon=CanonInfo.from_spec(canon_spec),
    )
    if report.schema_version == "1.0":
        return store.put_bytes(serialize_calibration_report_v1(report), options)
    return store.put_json(
        report,
        options,
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
