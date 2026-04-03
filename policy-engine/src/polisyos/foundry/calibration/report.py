"""Public calibration report module API."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

from polisyos.foundry.calibration.identifiability import IdentifiabilityReport


class CalibrationSeriesComparison(BaseModel):
    """Calibration series comparison public type."""
    model_config = ConfigDict(extra="forbid")

    time: List[float] | None = None
    real: List[float] = Field(default_factory=list)
    model: List[float] = Field(default_factory=list)


class CalibrationFitMetrics(BaseModel):
    """Calibration fit metrics data model."""
    model_config = ConfigDict(extra="forbid")

    mse: float
    rmse: float
    mae: float
    r2: float | None = None
    n: int | None = None


class CalibrationFitQuality(BaseModel):
    """Calibration fit quality public type."""
    model_config = ConfigDict(extra="forbid")

    per_target: Mapping[str, CalibrationFitMetrics] = Field(default_factory=dict)
    aggregate: CalibrationFitMetrics | None = None


class CalibrationUncertainty(BaseModel):
    """Calibration uncertainty public type."""
    model_config = ConfigDict(extra="forbid")

    method: str = "laplace"
    params: List[str] = Field(default_factory=list)
    covariance: List[List[float]] = Field(default_factory=list)
    correlation: List[List[float]] = Field(default_factory=list)
    std: List[float] = Field(default_factory=list)
    damping: float = 0.0
    hessian_rank: int | None = None
    hessian_condition: float | None = None
    non_identifiable: List[str] = Field(default_factory=list)


class CalibrationReport(BaseModel):
    """Артефакт результатов калибровки."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    calibrated_params: Mapping[str, float] = Field(
        default_factory=dict, description="Плоский словарь (node_id.param -> value)."
    )
    total_loss: float
    per_target_loss: Mapping[str, float] = Field(default_factory=dict)
    target_weights: Mapping[str, float] = Field(default_factory=dict)
    loss_history: List[float] = Field(default_factory=list)
    grad_norm_history: List[float] = Field(default_factory=list)
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
    diagnostics: List[str] = Field(default_factory=list)
    execution_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Параметры среды исполнения (fidelity, temperature и т.п.).",
    )


def put_calibration_config(
    store: FileSystemCAS,
    config: CalibrationConfig,
    *,
    inputs: List[InputRef] | None = None,
) -> ArtifactRef:
    """Put calibration config helper."""
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
    inputs: List[InputRef] | None = None,
) -> ArtifactRef:
    """Put calibration report helper."""
    return store.put_json(
        report,
        PutOptions(
            kind="foundry.calibration_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version=report.schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
