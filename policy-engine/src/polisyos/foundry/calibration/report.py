"""Persist calibration reports and expose the optimizer result schema.

These models describe the fitted parameter values and diagnostics produced by
`Calibrator.run()`. They intentionally separate synthetic-series comparisons,
fit quality, and uncertainty/identifiability metadata so governance passes can
inspect calibration quality without rerunning simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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


class CalibrationReport(BaseModel):
    """Persist calibrated parameters, trace comparisons, and diagnostics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
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


def put_calibration_config(
    store: FileSystemCAS,
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
    store: FileSystemCAS,
    report: CalibrationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a `CalibrationReport` artifact for downstream governance/replay."""
    return store.put_json(
        report,
        PutOptions(
            kind="foundry.calibration_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.CalibrationReport", version=report.schema_version
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
