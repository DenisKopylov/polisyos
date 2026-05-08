"""Machine-readable report contract for formal metric-comparison validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import MetricValidationReportRef


class ValidationIssue(BaseModel):
    """Machine-readable issue emitted while validating a metric-comparison family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    field_path: str | None = None
    hint: str | None = None


class SignificanceRecord(BaseModel):
    """Significance metadata for a single baseline-vs-candidate metric comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str
    null_hypothesis: str
    alternative: str
    statistic: float | None = None
    effect_size: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    ci_level: float | None = None
    p_value_raw: float | None = None
    p_value_adj: float | None = None
    alpha: float
    reject_null_raw: bool | None = None
    reject_null_adj: bool | None = None
    assumption_flags: tuple[str, ...] = ()
    calibration_flags: tuple[str, ...] = ()


class MetricComparisonResult(BaseModel):
    """Structured result for one metric comparison inside a validation family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    metric_direction: Literal["higher_is_better", "lower_is_better"]
    baseline_model_id: str
    candidate_model_id: str
    baseline_value: float
    candidate_value: float
    delta_value: float
    significance: SignificanceRecord
    resampling_method: str | None = None
    sample_size_effective: int | None = None
    family_id: str
    family_scope: str


class FamilyAdjustment(BaseModel):
    """Family-level multiplicity metadata applied to raw p-values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    alpha: float
    hypotheses_total: int
    error_rate_target: Literal["FWER", "FDR"]
    dependency_assumption: str | None = None


class MetricValidationReport(BaseModel):
    """Persisted formal validation report for metric-comparison hypotheses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["scientist.metric_validation_report"] = "scientist.metric_validation_report"
    report_id: str
    run_id: str | None = None
    dataset_id: str
    task: str
    is_valid: bool = True
    checked_at: str
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    family_adjustment: FamilyAdjustment
    comparisons: tuple[MetricComparisonResult, ...]
    notes: tuple[str, ...] = ()


def persist_metric_validation_report(
    store: ArtifactStore,
    report: MetricValidationReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.scientist.metric_validation_report",
    schema_version: str = "1.0",
) -> MetricValidationReportRef:
    """Persist a metric validation report and return its typed CAS reference."""

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="scientist.metric_validation_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MetricValidationReportRef.model_validate(ref)


def load_metric_validation_report(
    store: ArtifactStore,
    ref: MetricValidationReportRef,
) -> MetricValidationReport:
    """Load a persisted metric validation report from CAS."""

    payload = get_json_artifact(store, ref.artifact_id)
    return MetricValidationReport.model_validate(payload)


__all__ = [
    "FamilyAdjustment",
    "MetricComparisonResult",
    "MetricValidationReport",
    "SignificanceRecord",
    "ValidationIssue",
    "load_metric_validation_report",
    "persist_metric_validation_report",
]
