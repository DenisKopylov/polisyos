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
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
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
    bound_inputs = list(inputs or ())
    objective_profile = report.execution_context.get("objective_profile")
    if report.schema_version != "1.0" and objective_profile is not None:
        profile_ref = store.put_json(
            objective_profile,
            PutOptions(
                kind="foundry.calibration_objective_profile",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.foundry.GaussianObservationProfile", version="1.0"
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        bound_inputs = [
            item for item in bound_inputs if item.role != "calibration_objective_profile"
        ]
        bound_inputs.append(
            InputRef(
                artifact_id=profile_ref.artifact_id,
                role="calibration_objective_profile",
                manifest_profile_sha256=profile_ref.manifest_profile_sha256,
            )
        )
    options = PutOptions(
        kind="foundry.calibration_report",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version=report.schema_version),
        inputs=bound_inputs,
        canon=CanonInfo.from_spec(canon_spec),
    )
    if report.schema_version == "1.0":
        return store.put_bytes(serialize_calibration_report_v1(report), options)
    return store.put_json(
        report,
        options,
        canon_spec=canon_spec,
    )


def load_calibration_report(store: ArtifactStore, ref: ArtifactRef) -> CalibrationReport:
    """Resolve a Foundry report only through its exact CAS kind/schema/payload.

    A payload matching the report model under a different artifact kind is not
    a calibration report. V2 reports also require their persisted configuration
    edge. This loader establishes content integrity, not producer authority.
    """
    exact_ref = ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=getattr(ref, "manifest_profile_sha256", None),
    )
    manifest = store.get_manifest(exact_ref)
    schema = manifest.artifact_schema
    if (
        manifest.kind != "foundry.calibration_report"
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != "polisyos.foundry.CalibrationReport"
        or schema.version not in {"1.0", "2.0"}
    ):
        raise ValueError("calibration report manifest kind/schema mismatch")
    if not store.verify(exact_ref).ok:
        raise ValueError("calibration report content integrity failed")
    report = CalibrationReport.model_validate(from_canonical_bytes(store.get_bytes(exact_ref)))
    if report.schema_version != schema.version:
        raise ValueError("calibration report payload/schema version mismatch")
    if report.schema_version != "1.0":
        configuration_inputs = [x for x in manifest.inputs if x.role == "calibration_config"]
        if len(configuration_inputs) != 1:
            raise ValueError("calibration report requires one calibration_config input")
        configuration_input = configuration_inputs[0]
        configuration_ref = ArtifactRef(
            artifact_id=configuration_input.artifact_id,
            kind="foundry.calibration_config",
            media_type="application/json",
            manifest_profile_sha256=configuration_input.manifest_profile_sha256,
        )
        try:
            configuration_manifest = store.get_manifest(configuration_ref)
        except ValueError as exc:
            raise ValueError("calibration_config manifest admission failed") from exc
        configuration_schema = configuration_manifest.artifact_schema
        if (
            configuration_manifest.kind != "foundry.calibration_config"
            or configuration_manifest.media_type != "application/json"
            or configuration_schema is None
            or configuration_schema.name != "polisyos.ir.CalibrationConfig"
        ):
            raise ValueError("calibration_config manifest kind/schema mismatch")
        if not store.verify(configuration_ref).ok:
            raise ValueError("calibration_config content integrity failed")
        configuration = CalibrationConfig.model_validate(
            from_canonical_bytes(store.get_bytes(configuration_ref))
        )
        if configuration.schema_version != configuration_schema.version:
            raise ValueError("calibration_config payload/schema version mismatch")
        objective_profile = report.execution_context.get("objective_profile")
        if objective_profile is not None:
            profile_inputs = [
                x for x in manifest.inputs if x.role == "calibration_objective_profile"
            ]
            if len(profile_inputs) != 1:
                raise ValueError("calibration report objective profile input is missing")
            profile_input = profile_inputs[0]
            profile_ref = ArtifactRef(
                artifact_id=profile_input.artifact_id,
                kind="foundry.calibration_objective_profile",
                media_type="application/json",
                manifest_profile_sha256=profile_input.manifest_profile_sha256,
            )
            try:
                profile_manifest = store.get_manifest(profile_ref)
            except ValueError as exc:
                raise ValueError("calibration report objective profile binding mismatch") from exc
            if (
                profile_manifest.kind != "foundry.calibration_objective_profile"
                or profile_manifest.media_type != "application/json"
                or profile_manifest.artifact_schema is None
                or profile_manifest.artifact_schema.name
                != "polisyos.foundry.GaussianObservationProfile"
                or profile_manifest.artifact_schema.version != "1.0"
                or not store.verify(profile_ref).ok
                or from_canonical_bytes(store.get_bytes(profile_ref)) != objective_profile
            ):
                raise ValueError("calibration report objective profile binding mismatch")
    return report
